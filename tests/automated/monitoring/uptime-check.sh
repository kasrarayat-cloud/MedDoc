#!/usr/bin/env bash
# tests/automated/monitoring/uptime-check.sh — cron-driven ping.
#
# Pings the three public surfaces; logs every run; on consecutive
# failures sends an alert via Resend (if configured).
#
# Cron: */5 * * * *
#
# State is tracked in /var/log/meddoc-alerts.state so two consecutive
# failures triggers exactly one alert (not one per check).

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/../lib/common.sh"
load_test_env

LOG=/var/log/meddoc-alerts.log
STATE=/var/log/meddoc-alerts.state

# Fall back to $HOME-local paths if we can't touch /var/log — keeps the
# script runnable from a non-privileged shell during manual testing.
if ! touch "$LOG" 2>/dev/null; then
  LOG="$HOME/.meddoc-alerts.log"
  STATE="$HOME/.meddoc-alerts.state"
fi
touch "$LOG" "$STATE"

URLS=(
  "$TEST_MARKETING_URL"
  "$TEST_APP_URL/api/health"
  "$TEST_PRO_URL/api/health"
)

ts() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }

check_one() {
  local url="$1"
  local code
  code=$(curl --max-time 10 -sk -o /dev/null -w '%{http_code}' "$url" || echo 000)
  [[ "$code" == 2* || "$code" == 3* ]]
}

send_alert() {
  local subject="$1" body="$2"
  echo "[$(ts)] ALERT $subject: $body" >> "$LOG"

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
  local all_ok=true failures=()
  for u in "${URLS[@]}"; do
    if check_one "$u"; then
      echo "[$(ts)] OK  $u" >> "$LOG"
    else
      echo "[$(ts)] DOWN $u" >> "$LOG"
      failures+=("$u")
      all_ok=false
    fi
  done

  local prev current
  prev=$(cat "$STATE" 2>/dev/null || echo OK)
  current=$([ "$all_ok" = true ] && echo OK || echo DOWN)
  echo "$current" > "$STATE"

  # Alert only on the DOWN → DOWN transition (second consecutive
  # failure). Stops a single transient hiccup from paging.
  if [[ "$prev" == "DOWN" && "$current" == "DOWN" ]]; then
    send_alert "MedDoc uptime alert" "$(printf '%s\n' "${failures[@]}")"
  fi
  # Recovery: announce when we flip DOWN → OK.
  if [[ "$prev" == "DOWN" && "$current" == "OK" ]]; then
    send_alert "MedDoc recovered" "All URLs back to 2xx/3xx."
  fi
}

main "$@"
