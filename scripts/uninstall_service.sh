#!/usr/bin/env bash
set -e

SERVICE_FILE="/etc/systemd/system/chronosched.service"

if [ "$EUID" -ne 0 ]; then
  echo "[!] Please run with sudo: sudo bash scripts/uninstall_service.sh"
  exit 1
fi

echo "[+] Stopping chronosched.service..."
systemctl stop chronosched.service || true

echo "[+] Disabling chronosched.service..."
systemctl disable chronosched.service || true

if [ -f "$SERVICE_FILE" ]; then
  echo "[+] Removing service unit file..."
  rm -f "$SERVICE_FILE"
fi

echo "[+] Reloading systemd daemon..."
systemctl daemon-reload

echo "[✓] ChronoScheduler service successfully uninstalled."
