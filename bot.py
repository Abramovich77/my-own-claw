import asyncio
import logging
import os
import signal
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


async def handle_message(update: Update, _) -> None:
    chat_id = update.effective_chat.id
    prompt = update.message.text

    log.info("[msg] chat_id=%s text=%r", chat_id, prompt[:80])

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

    stdout_bytes, stderr_bytes = await proc.communicate()

    active_sessions.pop(chat_id, None)

    output = stdout_bytes.decode(errors="replace").strip()

    if output:
        await send_long(update, output)
    else:
        code = proc.returncode
        await update.message.reply_text(
            f"Claude Code finished with no output (exit code {code})."
        )


def main() -> None:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("Bot started. Working directory: %s", WORK_DIR)
    app.run_polling()


if __name__ == "__main__":
    main()
