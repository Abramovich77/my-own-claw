#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="claude-bot"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_USER="${SUDO_USER:-$USER}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo:  sudo bash install-service.sh"
    exit 1
fi

echo "Installing ${SERVICE_NAME} service..."
echo "  User: ${APP_USER}"
echo "  Dir:  ${APP_DIR}"

cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Telegram Claude Code Bot
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/.venv/bin/python bot.py
Restart=on-failure
RestartSec=5
EnvironmentFile=${APP_DIR}/.env

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

echo ""
echo "Done. Service is running."
echo "  Status:  sudo systemctl status ${SERVICE_NAME}"
echo "  Logs:    journalctl -u ${SERVICE_NAME} -f"
