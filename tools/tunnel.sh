#!/usr/bin/env bash
# Buka Jenkins (port 8080) ke internet supaya webhook GitHub bisa masuk.
# Arsitektur wajib memakai ngrok; cloudflared hanya cadangan bila ngrok diblokir jaringan.
set -uo pipefail

PORT="${1:-8080}"

if command -v ngrok >/dev/null 2>&1; then
  echo "== ngrok -> localhost:$PORT ==" >&2
  exec ngrok http "$PORT"
fi

echo "!! ngrok tidak ditemukan, memakai cloudflared sebagai cadangan" >&2
exec cloudflared tunnel --url "http://127.0.0.1:$PORT"
