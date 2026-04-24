#!/usr/bin/env bash
# tests/automated/monitoring/container-health.sh — 10-minute container watch.
#
# Flags any meddoc-pro-* container in an "exited" or "unhealthy" state.
# Caddy's healthcheck is known-broken (wget fork EAGAIN on a full-forks
# VPS; tracked separately) and gets ignored.
#
# Cron: */10 * * * *

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/../lib/common.sh"
load_test_env

LOG=/var/log/meddoc-alerts.log
STATE=/var/log/meddoc-containers.state
if ! touch "$LOG" 2>/dev/null; then
  LOG="$HOME/.meddoc-alerts.log"
  STATE="$HOME/.meddoc-containers.state"
fi
touch "$LOG" "$STATE"

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
  if ! command -v docker >/dev/null 2>&1; then
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] docker not installed; skipping" >> "$LOG"
    return 0
  fi

  local problems=()
  while IFS=$'\t' read -r name status; do
    [[ "$name" == meddoc-pro-* ]] || continue
    # Ignore caddy — known wget-fork healthcheck flake, service
    # functions correctly (all smoke tests pass).
    [[ "$name" == meddoc-pro-caddy-* ]] && continue

    if [[ "$status" == *"(unhealthy)"* ]]; then
      problems+=("$name is unhealthy")
    elif [[ "$status" != Up* ]]; then
      problems+=("$name is $status")
    fi
  done < <(docker ps -a --format '{{.Names}}	{{.Status}}')

  local prev current
  prev=$(cat "$STATE" 2>/dev/null || echo OK)
  if (( ${#problems[@]} )); then current=DOWN; else current=OK; fi
  echo "$current" > "$STATE"

  if [[ "$current" == "DOWN" && "$prev" == "OK" ]]; then
    send_alert "MedDoc container alert" "$(printf '%s\n' "${problems[@]}")"
  fi
  if [[ "$current" == "OK" && "$prev" == "DOWN" ]]; then
    send_alert "MedDoc containers recovered" "All meddoc-pro containers Up and healthy."
  fi

  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] containers state=$current problems=${#problems[@]}" >> "$LOG"
}

main "$@"
