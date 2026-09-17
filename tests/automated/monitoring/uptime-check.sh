#!/usr/bin/env bash
# tests/automated/monitoring/uptime-check.sh — cron-driven ping.
#
# Checks preserved marketing, intentional public maintenance, and the two
# private application listeners; logs every run; on consecutive
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

# Public clinical hosts are deliberately unavailable during private testing.
# Exact expected codes detect both an outage and accidental public reactivation.
# The retired pro.quillmd.com host remains outside this monitor’s target set.
uptime_admin_base="${TEST_ADMIN_URL:-https://admin.quillmd.com}"
uptime_doctor_private_base="${TEST_PRIVATE_DOCTOR_URL:-http://127.0.0.1:9130}"
uptime_admin_private_base="${TEST_PRIVATE_ADMIN_URL:-http://127.0.0.1:9131}"
URLS=(
  "${TEST_MARKETING_URL%/}/"
  "${TEST_APP_URL%/}/"
  "${uptime_admin_base%/}/"
  "${uptime_doctor_private_base%/}/health/"
  "${uptime_admin_private_base%/}/health/"
)
EXPECTED_CODES=(200 503 503 200 200)

ts() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }

check_one() {
  local url="$1" expected="$2"
  local code
  code=$(curl --max-time 10 -sk -o /dev/null -w '%{http_code}' "$url") || code=000
  [[ "$code" == "$expected" ]]
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
  local all_ok=true failures=() i u expected
  for i in "${!URLS[@]}"; do
    u="${URLS[$i]}"; expected="${EXPECTED_CODES[$i]}"
    if check_one "$u" "$expected"; then
      echo "[$(ts)] OK  $u (expected $expected)" >> "$LOG"
    else
      echo "[$(ts)] DOWN $u (expected $expected)" >> "$LOG"
      failures+=("$u (expected $expected)")
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
    send_alert "MedDoc recovered" "All monitored URLs returned their expected status codes."
  fi
}

main "$@"
