import asyncio
import logging
import logging.handlers
import os
import signal
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

import db

load_dotenv(Path(__file__).resolve().parent / ".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN is not set in .env")

CLAUDE_BIN = os.path.expanduser(os.getenv("CLAUDE_BIN", "~/.local/bin/claude"))
BOT_DIR = str(Path(__file__).resolve().parent)
CLAUDE_WORK_DIR = os.path.expanduser(os.getenv("CLAUDE_WORK_DIR", BOT_DIR))
UPLOADS_DIR = Path(CLAUDE_WORK_DIR) / "uploads"
DB_DIR = Path(BOT_DIR) / "data"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

_allowed_raw = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = {
    int(uid.strip()) for uid in _allowed_raw.split(",") if uid.strip()
}

groq_client = None
if GROQ_API_KEY:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)

LOG_DIR = Path(BOT_DIR) / "logs"
LOG_DIR.mkdir(exist_ok=True)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_console = logging.StreamHandler()
_console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

LOG_MAX_MB = int(os.getenv("LOG_MAX_MB", "5"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

_file = logging.handlers.RotatingFileHandler(
    LOG_DIR / "bot.log",
    maxBytes=LOG_MAX_MB * 1024 * 1024,
    backupCount=LOG_BACKUP_COUNT,
    encoding="utf-8",
)
_file.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_console, _file])

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

log = logging.getLogger(__name__)

active_sessions: dict[int, asyncio.subprocess.Process] = {}

HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "15"))

MAX_MSG_LEN = 4000


async def check_authorized(update: Update) -> bool:
    if not ALLOWED_USERS:
        return True
    if update.effective_user.id in ALLOWED_USERS:
        return True
    log.warning(
        "[auth] Rejected user_id=%s username=%s",
        update.effective_user.id,
        update.effective_user.username,
    )
    await update.message.reply_text("Unauthorized. Your user ID is not in ALLOWED_USERS.")
    return False


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
        "Use /skills to see all commands and supported input types."
    )


async def cmd_skills(update: Update, _) -> None:
    await update.message.reply_text(
        "*Available commands:*\n"
        "/start — Welcome message\n"
        "/new — Start a fresh conversation (clears session)\n"
        "/cancel — Stop a currently running task\n"
        "/skills — Show this list\n"
        "\n"
        "*Supported input types:*\n"
        "• Text — sent directly to Claude Code\n"
        "• Voice — transcribed via Whisper, then sent to Claude Code\n"
        "• Photo — saved to disk, then you describe what to do with it\n"
        "• Photo + caption — processed immediately",
        parse_mode="Markdown",
    )


async def cmd_new(update: Update, _) -> None:
    if not await check_authorized(update):
        return
    chat_id = update.effective_chat.id
    db.clear_session(chat_id)
    await update.message.reply_text("New conversation started.")


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

    status_msg = await update.message.reply_text("Running Claude Code...")

    session_uuid = db.get_session(chat_id)
    is_new_session = session_uuid is None
    if is_new_session:
        session_uuid = str(uuid.uuid4())

    cmd = [CLAUDE_BIN, "--print", "--dangerously-skip-permissions"]
    cmd += ["--session-id" if is_new_session else "--resume", session_uuid]
    cmd.append(prompt)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=CLAUDE_WORK_DIR,
        )
    except FileNotFoundError:
        await status_msg.edit_text(
            f"Claude Code binary not found at: {CLAUDE_BIN}\n"
            "Set CLAUDE_BIN in .env to the correct path."
        )
        return

    active_sessions[chat_id] = proc

    # heartbeat: edit the status message every HEARTBEAT_INTERVAL seconds
    async def heartbeat() -> None:
        elapsed = 0
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            elapsed += HEARTBEAT_INTERVAL
            try:
                await status_msg.edit_text(f"Running Claude Code... ({elapsed}s)")
            except Exception:
                pass

    hb_task = asyncio.create_task(heartbeat())
    stdout_bytes, stderr_bytes = await proc.communicate()
    hb_task.cancel()

    active_sessions.pop(chat_id, None)

    if stderr_bytes:
        log.warning("[claude stderr] chat_id=%s: %s", chat_id, stderr_bytes.decode(errors="replace").strip())

    if proc.returncode != 0 and not is_new_session:
        log.warning("[session] --resume failed for %s, starting fresh", session_uuid)
        session_uuid = str(uuid.uuid4())
        try:
            proc = await asyncio.create_subprocess_exec(
                CLAUDE_BIN, "--print", "--dangerously-skip-permissions",
                "--session-id", session_uuid, prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=CLAUDE_WORK_DIR,
            )
        except FileNotFoundError:
            return
        active_sessions[chat_id] = proc
        stdout_bytes, stderr_bytes = await proc.communicate()
        active_sessions.pop(chat_id, None)
        if stderr_bytes:
            log.warning("[claude stderr] chat_id=%s (retry): %s", chat_id, stderr_bytes.decode(errors="replace").strip())
        is_new_session = True

    db.set_session(chat_id, session_uuid)

    output = stdout_bytes.decode(errors="replace").strip()

    try:
        await status_msg.delete()
    except Exception:
        pass

    if output:
        await send_long(update, output)
    else:
        await update.message.reply_text(
            f"Claude Code finished with no output (exit code {proc.returncode})."
        )


async def handle_message(update: Update, _) -> None:
    if not await check_authorized(update):
        return
    chat_id = update.effective_chat.id
    prompt = update.message.text
    log.info("[msg] chat_id=%s text=%r", chat_id, prompt[:80])

    photo_path = db.get_pending_photo(chat_id)
    if photo_path:
        db.set_pending_photo(chat_id, None)
        prompt = f"Regarding the image at {photo_path}: {prompt}"

    await run_claude(update, chat_id, prompt)


async def handle_voice(update: Update, _) -> None:
    if not await check_authorized(update):
        return
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


async def handle_photo(update: Update, _) -> None:
    if not await check_authorized(update):
        return
    chat_id = update.effective_chat.id

    if chat_id in active_sessions:
        await update.message.reply_text(
            "A task is already running. Use /cancel to stop it first."
        )
        return

    photo = update.message.photo[-1]
    try:
        tg_file = await photo.get_file()
    except Exception as exc:
        log.error("[photo] get_file failed: %s", exc)
        await update.message.reply_text(
            "Failed to download photo from Telegram. Please try again."
        )
        return

    UPLOADS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"photo_{timestamp}.jpg"
    save_path = UPLOADS_DIR / filename

    try:
        await tg_file.download_to_drive(str(save_path))
    except Exception as exc:
        log.error("[photo] download failed: %s", exc)
        await update.message.reply_text(
            "Failed to save photo. Please try again."
        )
        return
    log.info("[photo] chat_id=%s saved=%s", chat_id, save_path)

    caption = update.message.caption
    if caption:
        prompt = f"Regarding the image at {save_path}: {caption}"
        await update.message.reply_text(f"Photo saved. Running Claude Code...")
        await run_claude(update, chat_id, prompt)
    else:
        db.set_pending_photo(chat_id, str(save_path))
        await update.message.reply_text(
            f"Photo saved to {save_path}\n"
            "What would you like me to do with it? Send a text message with your request."
        )


async def error_handler(update: object, context) -> None:
    log.error("Unhandled exception: %s", context.error)


def main() -> None:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_error_handler(error_handler)
    Path(CLAUDE_WORK_DIR).mkdir(parents=True, exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db(DB_DIR / "bot.db")
    log.info("Bot started. Claude working directory: %s", CLAUDE_WORK_DIR)
    if ALLOWED_USERS:
        log.info("Access restricted to user IDs: %s", ALLOWED_USERS)
    else:
        log.warning("ALLOWED_USERS not set -- anyone can use this bot!")
    if groq_client:
        log.info("Voice transcription enabled (Groq Whisper)")
    else:
        log.info("Voice transcription disabled (no GROQ_API_KEY)")
    async def post_init(application) -> None:
        await application.bot.set_my_commands([
            BotCommand("start", "Welcome message"),
            BotCommand("skills", "Show all commands and input types"),
            BotCommand("new", "Start a fresh conversation"),
            BotCommand("cancel", "Stop a currently running task"),
        ])

    app.post_init = post_init
    app.run_polling()


if __name__ == "__main__":
    main()
