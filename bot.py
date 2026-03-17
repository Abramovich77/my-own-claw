import asyncio
import logging
import os
import signal
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

load_dotenv(Path(__file__).resolve().parent / ".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN is not set in .env")

CLAUDE_BIN = os.getenv("CLAUDE_BIN", os.path.expanduser("~/.local/bin/claude"))
WORK_DIR = str(Path(__file__).resolve().parent)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = None
if GROQ_API_KEY:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

active_sessions: dict[int, asyncio.subprocess.Process] = {}

MAX_MSG_LEN = 4000


def split_message(text: str, max_len: int = MAX_MSG_LEN) -> list[str]:
    chunks: list[str] = []
    while len(text) > max_len:
        split_at = text.rfind("\n", 0, max_len)
        if split_at <= 0:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


async def send_long(update: Update, text: str) -> None:
    for chunk in split_message(text):
        if not chunk.strip():
            continue
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            try:
                await update.message.reply_text(chunk)
            except Exception as exc:
                log.error("Failed to send message: %s", exc)


async def cmd_start(update: Update, _) -> None:
    await update.message.reply_text(
        "Hi! Send me any task and I'll run Claude Code on it.\n"
        "Use /cancel to stop a running task."
    )


async def cmd_cancel(update: Update, _) -> None:
    chat_id = update.effective_chat.id
    proc = active_sessions.get(chat_id)
    if proc is None:
        await update.message.reply_text("No active task to cancel.")
        return

    try:
        proc.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        pass
    active_sessions.pop(chat_id, None)
    await update.message.reply_text("Task cancelled.")


async def run_claude(update: Update, chat_id: int, prompt: str) -> None:
    if chat_id in active_sessions:
        await update.message.reply_text(
            "A task is already running. Use /cancel to stop it first."
        )
        return

    await update.message.reply_text("Running Claude Code...")

    try:
        proc = await asyncio.create_subprocess_exec(
            CLAUDE_BIN,
            "--print",
            "--dangerously-skip-permissions",
            prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=WORK_DIR,
        )
    except FileNotFoundError:
        await update.message.reply_text(
            f"Claude Code binary not found at: {CLAUDE_BIN}\n"
            "Set CLAUDE_BIN in .env to the correct path."
        )
        return

    active_sessions[chat_id] = proc

    stdout_bytes, _ = await proc.communicate()

    active_sessions.pop(chat_id, None)

    output = stdout_bytes.decode(errors="replace").strip()

    if output:
        await send_long(update, output)
    else:
        code = proc.returncode
        await update.message.reply_text(
            f"Claude Code finished with no output (exit code {code})."
        )


async def handle_message(update: Update, _) -> None:
    chat_id = update.effective_chat.id
    prompt = update.message.text
    log.info("[msg] chat_id=%s text=%r", chat_id, prompt[:80])
    await run_claude(update, chat_id, prompt)


async def handle_voice(update: Update, _) -> None:
    chat_id = update.effective_chat.id

    if groq_client is None:
        await update.message.reply_text(
            "Voice messages are not configured. Set GROQ_API_KEY in .env."
        )
        return

    if chat_id in active_sessions:
        await update.message.reply_text(
            "A task is already running. Use /cancel to stop it first."
        )
        return

    await update.message.reply_text("Transcribing voice...")

    voice = update.message.voice
    tg_file = await voice.get_file()

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
            await tg_file.download_to_drive(tmp_path)

        with open(tmp_path, "rb") as audio:
            transcription = groq_client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio,
            )

        text = transcription.text.strip()
        if not text:
            await update.message.reply_text("Could not transcribe the voice message.")
            return

        log.info("[voice] chat_id=%s transcribed=%r", chat_id, text[:80])
        await update.message.reply_text(f"Transcribed: {text}")
        await run_claude(update, chat_id, text)

    except Exception as exc:
        log.error("Voice transcription failed: %s", exc)
        await update.message.reply_text(f"Voice transcription failed: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main() -> None:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    log.info("Bot started. Working directory: %s", WORK_DIR)
    if groq_client:
        log.info("Voice transcription enabled (Groq Whisper)")
    else:
        log.info("Voice transcription disabled (no GROQ_API_KEY)")
    app.run_polling()


if __name__ == "__main__":
    main()
