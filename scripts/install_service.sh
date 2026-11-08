#!/usr/bin/env bash
set -e

echo "======================================================================"
echo "  CHRONOSCHEDULER: SYSTEMD SERVICE INSTALLER"
echo "======================================================================"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_FILE="/etc/systemd/system/chronosched.service"
PYTHON_BIN="$(which python3)"

if [ "$EUID" -ne 0 ]; then
  echo "[!] Please run this installer with sudo: sudo bash scripts/install_service.sh"
  exit 1
fi

echo "[+] Generating systemd unit for directory: $REPO_DIR"
cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=ChronoScheduler: Preemptive CPU Resource Allocation Daemon
Documentation=https://github.com/shrishabarish/ChronoScheduler
After=network.target sys-kernel-debug.mount

[Service]
Type=simple
ExecStart=$PYTHON_BIN -m src.cli run
WorkingDirectory=$REPO_DIR
Restart=always
RestartSec=3
Environment="PYTHONUNBUFFERED=1"
Environment="CHRONOSCHED_CONFIDENCE_THRESHOLD=0.35"
LimitNOFILE=65535
Nice=-10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "[+] Reloading systemd daemon..."
systemctl daemon-reload

echo "[+] Enabling chronosched.service on boot..."
systemctl enable chronosched.service

echo "[+] Starting chronosched.service..."
systemctl start chronosched.service

echo ""
echo "======================================================================"
echo "  [✓] ChronoScheduler service installed and active!"
echo "  • Check status : sudo systemctl status chronosched"
echo "  • View logs    : sudo journalctl -u chronosched -f"
echo "  • Stop service : sudo systemctl stop chronosched"
echo "======================================================================"
