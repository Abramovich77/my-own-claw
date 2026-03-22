---
name: bot-status
description: Check if the bot process is running and show active sessions from SQLite. Use to diagnose if bot is alive or to see who has active sessions.
---

Check the bot's current status:

1. **Process check:** `pgrep -fl "python.*bot.py"` — show PID if running
2. **Session count:** Query `data/bot.db` — `SELECT COUNT(*) FROM sessions`
3. **Recent sessions:** `SELECT chat_id, session_uuid, created_at FROM sessions ORDER BY created_at DESC LIMIT 10`
4. **Log tail:** Last 5 lines of `logs/bot.log` to show recent activity

Present a clear status summary:
- Bot running: YES/NO (PID)
- Active sessions: N chats
- Most recent activity: timestamp from logs
