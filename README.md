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
| `/new` | Start a fresh conversation (clears session history) |
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

## Auto-Deploy (CI/CD)

Every push to `main` automatically deploys to your VM via GitHub Actions.

**One-time setup:**

1. On your VM, allow passwordless restart:

```bash
echo "olegab ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart claude-bot" | sudo tee /etc/sudoers.d/claude-bot
```

2. In GitHub, go to **Settings > Secrets and variables > Actions** and add:

| Secret | Value |
|--------|-------|
| `VM_HOST` | Your VM's IP or hostname |
| `VM_USER` | SSH username (e.g. `olegab`) |
| `VM_SSH_KEY` | Contents of your private SSH key (`~/.ssh/id_ed25519`) |
| `VM_APP_DIR` | Absolute path to the project on the VM (e.g. `/home/olegab/my_claude_code_claw`) |

After that, every `git push` to `main` will pull the code on the VM, install deps, and restart the bot.

## Logs

Logs are written to `logs/bot.log` with automatic rotation (5 MB per file, 5 backups kept).

Useful commands:

```bash
# Follow logs in real time
tail -f logs/bot.log

# Show only errors
grep ERROR logs/bot.log

# Show errors and warnings
grep -E 'ERROR|WARNING' logs/bot.log

# Errors from today
grep "$(date +%Y-%m-%d)" logs/bot.log | grep ERROR

# Search across all rotated log files
grep ERROR logs/bot.log*
```

## Notes

- Conversations are persistent -- Claude remembers previous messages in the same chat.
- Use `/new` to start a fresh conversation when you want a clean slate.
- One task runs per chat at a time. Use `/cancel` to abort.
- Claude Code runs with `--dangerously-skip-permissions` in the configured working directory.
- Long replies are automatically split into multiple messages.
- Session data is stored in `data/bot.db` (SQLite).
