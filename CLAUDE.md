# Claude Code Guide — my_claude_code_claw

## What This Project Does
Telegram bot that bridges Telegram messages to the **Claude Code CLI**. Users send text, voice, or photos via Telegram; the bot runs `claude --print --dangerously-skip-permissions` as a subprocess and replies with the output. Sessions are persisted in SQLite so multi-turn conversations work.

## Key Files
| File | Purpose |
|------|---------|
| `bot.py` | Main bot — all Telegram handlers, subprocess execution, session management |
| `db.py` | SQLite wrapper — `init_db`, `get_session`, `set_session`, `clear_session` |
| `.env` | Secrets — **never read, never modify, never commit** |
| `.env.example` | Config template — edit this when adding new env vars |
| `data/bot.db` | SQLite database (sessions table) |
| `logs/bot.log` | Rotating log file |
| `claude-bot.service` | Systemd unit for Ubuntu deployment |
| `docs/SETUP.md` | Full deployment guide |

## Running the Bot
```bash
source .venv/bin/activate
python bot.py
```
Requires `.env` with `TELEGRAM_BOT_TOKEN` set. See `.env.example` for all options.

## Environment Variables
| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `TELEGRAM_BOT_TOKEN` | YES | — | From BotFather |
| `CLAUDE_BIN` | no | `~/.local/bin/claude` | Path to claude CLI |
| `CLAUDE_WORK_DIR` | no | bot dir | Claude's working directory (isolate in prod!) |
| `GROQ_API_KEY` | no | — | Enables voice transcription |
| `ALLOWED_USERS` | no | — | Comma-separated Telegram user IDs; **set in prod** |
| `LOG_MAX_MB` | no | 5 | Log rotation size |
| `LOG_BACKUP_COUNT` | no | 5 | Log backups to keep |
| `ANTHROPIC_API_KEY` | no | — | For direct Claude API calls (future use) |

## Architecture
```
Telegram → python-telegram-bot → bot.py
                                    ├── check_authorized()  (ALLOWED_USERS whitelist)
                                    ├── db.get_session()    (resume or new UUID)
                                    └── asyncio subprocess  claude --print --dangerously-skip-permissions
                                                              [--session-id | --resume] <uuid>
                                                              cwd=CLAUDE_WORK_DIR
```

## Code Conventions
- `async/await` throughout — use `asyncio.create_subprocess_exec` for subprocesses
- Logger: `log = logging.getLogger(__name__)` at module level
- Paths: `Path(__file__).resolve().parent` for bot dir
- Session fallback: if `--resume` fails (non-zero exit), retry as new session

## Testing
No tests yet. When adding tests:
```bash
pip install pytest pytest-asyncio
python -m pytest tests/
```
Use `pytest-asyncio` for async handler tests. Mock `asyncio.create_subprocess_exec` for Claude subprocess.

## Security Notes
- `.env` must never be committed (already in `.gitignore`)
- Set `ALLOWED_USERS` in production or anyone can use the bot
- `CLAUDE_WORK_DIR` should be a dedicated isolated directory in prod, not the bot dir
- `notes/` is gitignored — safe scratch space for drafts

## Development Workflow & Skills

### Built-in skills for this project
| Skill | When to use |
|-------|-------------|
| `/update-config` | Add MCP servers, hooks, or permissions to `.claude/settings.local.json` |
| `/claude-api` | If switching from subprocess claude to direct Anthropic API calls |
| `/simplify` | After a major refactor of `bot.py` |
| `/loop 30s /bot-logs` | Watch logs continuously during development |

### Custom project skills
| Skill | What it does |
|-------|-------------|
| `/bot-restart` | Kill and restart the bot process after code changes |
| `/bot-logs` | Show recent log entries and summarize errors |
| `/bot-status` | Check if bot is running + show active sessions from SQLite |

## Deployment (Ubuntu VM)
```bash
sudo cp claude-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable claude-bot
sudo systemctl start claude-bot
journalctl -u claude-bot -f   # tail logs
```
See `docs/SETUP.md` for full setup from scratch.
