# Setup Guide

Full step-by-step guide to get the Telegram Claude Code Bot running on an Ubuntu VM.

## 1. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Choose a name (e.g. "My Claude Bot")
4. Choose a username (must end with `bot`, e.g. `my_claude_claw_bot`)
5. BotFather will reply with a token like `8621658784:AAHPaqzR7RUtKClQWv8NVZqiwa6NnR6BCxk`
6. Save this token -- you'll need it in step 4

## 2. Install Claude Code on the VM

SSH into your Ubuntu VM and install Node.js + Claude Code CLI:

```bash
# Install Node.js 20+ (required by Claude Code)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Verify it works
claude --version
```

Then authenticate Claude Code:

```bash
# Option A: Interactive login (opens browser)
claude auth login

# Option B: Set API key directly
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

## 3. Clone the Project

```bash
cd ~
git clone <your-repo-url> my_claude_code_claw
cd my_claude_code_claw
```

## 4. Configure Environment

```bash
cp .env.example .env
nano .env
```

Set your bot token:

```
TELEGRAM_BOT_TOKEN=8621658784:AAHPaqzR7RUtKClQWv8NVZqiwa6NnR6BCxk
```

If Claude Code is installed somewhere other than `~/.local/bin/claude`, also set:

```
CLAUDE_BIN=/usr/local/bin/claude
```

Find your Claude binary path with `which claude`.

## 5. Install Python Dependencies

```bash
sudo apt-get install -y python3 python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 6. Test It

```bash
source .venv/bin/activate
python bot.py
```

Open Telegram, find your bot, and send `/start`. If you get a reply, it's working.

Press `Ctrl+C` to stop.

## 7. Install as a System Service

This makes the bot start automatically on boot and restart if it crashes.

```bash
# Edit the service file paths if needed
nano claude-bot.service

# Install
sudo cp claude-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable claude-bot
sudo systemctl start claude-bot
```

Check it's running:

```bash
sudo systemctl status claude-bot
```

Watch live logs:

```bash
journalctl -u claude-bot -f
```

## Useful Commands

| Command | What it does |
|---------|-------------|
| `sudo systemctl start claude-bot` | Start the bot |
| `sudo systemctl stop claude-bot` | Stop the bot |
| `sudo systemctl restart claude-bot` | Restart after code changes |
| `sudo systemctl status claude-bot` | Check if running |
| `journalctl -u claude-bot -f` | Tail logs |
| `journalctl -u claude-bot --since "1 hour ago"` | Recent logs |

## Updating

After pulling new code on the VM:

```bash
cd ~/my_claude_code_claw
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart claude-bot
```

## Troubleshooting

**Bot doesn't respond in Telegram:**
- Check the token: `grep TELEGRAM_BOT_TOKEN .env`
- Check service logs: `journalctl -u claude-bot -f`
- Make sure only one instance is running (systemd + manual `python bot.py` will conflict)

**Claude Code errors:**
- Verify Claude works: `claude --print "say hi"`
- Check authentication: `claude auth status`
- Check the binary path: `which claude` and compare with `CLAUDE_BIN` in `.env`

**Service won't start:**
- Check paths in `claude-bot.service` match your VM layout
- Make sure `.venv` exists: `ls ~/my_claude_code_claw/.venv/bin/python`
- Check permissions: the `User` in the service file must own the project directory
