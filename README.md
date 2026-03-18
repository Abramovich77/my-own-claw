# Telegram Claude Code Bot

Telegram bot that runs Claude Code from your phone. Send a message, get Claude's response.

**Full setup guide:** [docs/SETUP.md](docs/SETUP.md)

## Prerequisites

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup

1. Add your token to `.env`:

```
TELEGRAM_BOT_TOKEN=your_token_here
```

2. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Run:

```bash
source .venv/bin/activate
python bot.py
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | *(required)* | Bot token from BotFather |
| `CLAUDE_BIN` | `~/.local/bin/claude` | Path to Claude Code binary |
| `CLAUDE_WORK_DIR` | `~/workspace` | Directory where Claude Code runs (isolated from bot code) |
| `GROQ_API_KEY` | *(optional)* | Groq API key for voice transcription ([get one free](https://console.groq.com)) |
| `ALLOWED_USERS` | *(optional)* | Comma-separated Telegram user IDs. If not set, anyone can use the bot |

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/cancel` | Stop the current Claude Code task |
| *(any text)* | Run as a Claude Code prompt |
| *(voice message)* | Transcribe via Groq Whisper, then run as a prompt |
| *(photo)* | Save to `uploads/`, run caption as prompt if provided |

## Run as a Service (VM)

To auto-start the bot on boot, install the systemd service:

```bash
# Edit claude-bot.service — set User, WorkingDirectory, ExecStart to match your VM
sudo cp claude-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable claude-bot
sudo systemctl start claude-bot
```

Check logs:

```bash
journalctl -u claude-bot -f
```

## Notes

- One task runs per chat at a time. Use `/cancel` to abort.
- Claude Code runs with `--dangerously-skip-permissions` in the project root.
- Long replies are automatically split into multiple messages.
