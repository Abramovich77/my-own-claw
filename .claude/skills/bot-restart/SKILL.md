---
name: bot-restart
description: Restart the Telegram bot process. Use after editing bot.py or db.py to apply changes.
disable-model-invocation: true
---

Restart the Telegram bot:

1. Check if bot is running: `pgrep -f "python.*bot.py"`
2. If running, kill it: `pkill -f "python.*bot.py"`
3. Wait a moment for clean shutdown
4. Start the bot: `cd /Users/olegab/git/my_claude_code_claw && source .venv/bin/activate && python bot.py &`
5. Confirm it started by checking for the "Bot started" log line in `logs/bot.log`

Report whether restart succeeded or failed.
