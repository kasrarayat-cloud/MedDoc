#!/usr/bin/env bash
# tests/automated/monitoring/disk-monitor.sh — hourly disk check.
#
# Alerts when / drops below 10 GB free OR crosses 90% used. Uses the
# same Resend-backed alert hook as uptime-check.sh and dedupes via a
# state file so you don't get hourly pages for the same condition.
#
# Cron: 0 * * * *

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/../lib/common.sh"
load_test_env

LOG=/var/log/meddoc-alerts.log
STATE=/var/log/meddoc-disk.state
if ! touch "$LOG" 2>/dev/null; then
  LOG="$HOME/.meddoc-alerts.log"
  STATE="$HOME/.meddoc-disk.state"
fi
touch "$LOG" "$STATE"

THRESHOLD_GB=10
THRESHOLD_PCT=90

send_alert() {
  local subject="$1" body="$2"
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] ALERT $subject: $body" >> "$LOG"
  [[ -z "${TEST_ALERT_RESEND_API_KEY:-}" || -z "${TEST_ALERT_TO:-}" ]] && return 0
  curl --max-time 10 -sk -o /dev/null \
    -X POST https://api.resend.com/emails \
    -H "Authorization: Bearer $TEST_ALERT_RESEND_API_KEY" \
    -H 'Content-Type: application/json' \
    -d "$(python3 -c '
import json, sys, os
print(json.dumps({
  "from": os.environ.get("TEST_ALERT_FROM","alerts@quillmd.com"),
  "to":   [os.environ["TEST_ALERT_TO"]],
  "subject": sys.argv[1],
  "text":    sys.argv[2],
}))' "$subject" "$body")"
}

main() {
  local free_gb used_pct
  free_gb=$(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
  used_pct=$(df -P / | awk 'NR==2 {print $5}' | tr -d '%')

  local problem=""
  if [[ "$free_gb" =~ ^[0-9]+$ && $free_gb -lt $THRESHOLD_GB ]]; then
    problem+="free < ${THRESHOLD_GB}GB (actual ${free_gb}GB); "
  fi
  if [[ "$used_pct" =~ ^[0-9]+$ && $used_pct -gt $THRESHOLD_PCT ]]; then
    problem+="used > ${THRESHOLD_PCT}% (actual ${used_pct}%); "
  fi

  local prev=OK current=OK
  prev=$(cat "$STATE" 2>/dev/null || echo OK)
  [[ -n "$problem" ]] && current=DOWN
  echo "$current" > "$STATE"

  if [[ "$current" == "DOWN" && "$prev" == "OK" ]]; then
    send_alert "MedDoc disk pressure" "${problem%; }"
  fi
  if [[ "$current" == "OK" && "$prev" == "DOWN" ]]; then
    send_alert "MedDoc disk recovered" "free=${free_gb}GB, used=${used_pct}%"
  fi

  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] disk free=${free_gb}GB used=${used_pct}% state=$current" >> "$LOG"
}

main "$@"
