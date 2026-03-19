---
name: bot-logs
description: Show recent bot logs and summarize errors or warnings. Use when debugging issues, checking bot activity, or when something went wrong.
---

Read bot logs and provide a useful summary:

1. Read the last 100 lines of `logs/bot.log`
2. Identify and highlight:
   - ERROR lines (show full context)
   - WARNING lines
   - Auth rejections (`[auth] Rejected`)
   - Session fallbacks (`[session] --resume failed`)
   - Recent activity (`[msg]`, `[voice]`, `[photo]` entries)
3. Summarize: how many requests, any errors, any patterns

If `$ARGUMENTS` is provided, use it as a filter (e.g., `/bot-logs error` to focus on errors only).

If `logs/bot.log` doesn't exist, report that the bot hasn't been run yet.
