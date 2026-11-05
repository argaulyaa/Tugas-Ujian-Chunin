#!/usr/bin/env bash
# Ringkasan status CI/CD: build Jenkins terakhir, image yang jalan, health, webhook terakhir.
set -uo pipefail

JENKINS_URL="${JENKINS_URL:-http://127.0.0.1:8080}"
JOB="${JOB:-visitor-log-pipeline}"
PW_FILE="${PW_FILE:-$HOME/.config/tugas-chunin/jenkins_admin}"
APP_URL="${APP_URL:-http://127.0.0.1:8000}"
GH_REPO="${GH_REPO:-argaulyaa/Tugas-Ujian-Chunin}"
HOOK_ID="${HOOK_ID:-707893621}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

PW="$(cat "$PW_FILE" 2>/dev/null)"
if [ -z "${PW:-}" ]; then
  echo "!! password Jenkins tidak ditemukan di $PW_FILE" >&2
  exit 1
fi

echo "== Build Jenkins terakhir =="
curl -s -u "admin:$PW" "$JENKINS_URL/job/$JOB/api/json" | python3 -c '
import sys, json
d = json.load(sys.stdin)
builds = d.get("builds", [])[:5]
for b in builds:
    print("  #%-4s %-8s %s" % (b["number"], b.get("result"), b.get("timestamp")))
print("  antrean: %s" % ("ada job menunggu" if d.get("inQueue") else "kosong"))
'

echo
echo "== Container yang jalan =="
(cd "$REPO_DIR" && sudo docker compose ps --format '  {{.Name}}  {{.Image}}  {{.Status}}')

echo
echo "== Commit terakhir di repo =="
(cd "$REPO_DIR" && echo "  $(git log -1 --format='%h %s')")

echo
echo "== Health aplikasi =="
printf "  %s -> %s\n" "$APP_URL/api/health" "$(curl -s --max-time 10 "$APP_URL/api/health" || echo TIDAK MERESPON)"

echo
echo "== Delivery webhook terakhir =="
TOKEN="${GITHUB_TOKEN:-}"
if [ -z "$TOKEN" ] && [ -f "$HOME/.hermes/.env" ]; then
  TOKEN="$(grep -m1 '^GITHUB_TOKEN=' "$HOME/.hermes/.env" | cut -d= -f2-)"
fi
if [ -n "$TOKEN" ]; then
  curl -s -H "Authorization: token $TOKEN" \
    "https://api.github.com/repos/$GH_REPO/hooks/$HOOK_ID/deliveries?per_page=3" |
    python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("  (tidak bisa membaca delivery)")
    sys.exit()
for x in d:
    print("  %-6s %-6s HTTP %s  %s" % (x["event"], x["status"], x["status_code"], x["delivered_at"]))
'
else
  echo "  (GITHUB_TOKEN tidak tersedia, lewati)"
fi
