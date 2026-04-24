#!/usr/bin/env bash
# tests/automated/setup-cron.sh — install the recurring checks as cron.
#
# Idempotent: rewrites a single block in the user's crontab delimited
# by # MEDDOC-TESTS-START / # MEDDOC-TESTS-END. Rerunning upgrades the
# schedule without leaving stale entries.
#
# Usage:
#   bash tests/automated/setup-cron.sh          # install + show
#   bash tests/automated/setup-cron.sh --dry    # print block, don't install
#   bash tests/automated/setup-cron.sh --remove # uninstall
#
# IMPORTANT: the cron entries invoke scripts with absolute paths, so
# the repo must stay at the current location for cron to resolve them.
# If you move /opt/meddoc-pro, re-run this script.

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"

MODE=install
for arg in "$@"; do
  case "$arg" in
    --dry)    MODE=dry ;;
    --remove) MODE=remove ;;
    -h|--help) head -n 18 "$0" | sed 's/^# \?//'; exit 0 ;;
  esac
done

START_MARK='# MEDDOC-TESTS-START'
END_MARK='# MEDDOC-TESTS-END'

# Pick a log path the crontab user can actually write to. If /var/log
# is open to this uid we use it; otherwise fall back to a dotfile under
# $HOME. Cron's `>>` redirection opens the path BEFORE the command
# runs, so a permission error there silently kills the whole job —
# this check prevents the foot-gun.
if touch /var/log/meddoc-cron.log 2>/dev/null; then
  CRON_LOG=/var/log/meddoc-cron.log
else
  CRON_LOG="$HOME/.meddoc-cron.log"
  touch "$CRON_LOG" 2>/dev/null || true
fi

# Build the block. PATH is explicit so cron finds node/npx/docker even
# when the login shell isn't sourced.
read -r -d '' BLOCK <<EOF || true
$START_MARK
# Managed by tests/automated/setup-cron.sh — do not edit manually.
# Remove with: bash $HERE/setup-cron.sh --remove
# Log sink picked at install time based on what this user can write to.
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
*/5  *   * * *   bash $HERE/monitoring/uptime-check.sh      >> $CRON_LOG 2>&1
0    *   * * *   bash $HERE/monitoring/disk-monitor.sh      >> $CRON_LOG 2>&1
*/10 *   * * *   bash $HERE/monitoring/container-health.sh  >> $CRON_LOG 2>&1
0    2   * * *   cd $REPO_ROOT && bash $HERE/run-all.sh --smoke --e2e >> $CRON_LOG 2>&1
$END_MARK
EOF

install_block() {
  local existing
  existing=$(crontab -l 2>/dev/null || true)
  local cleaned
  # Strip any previous managed block.
  cleaned=$(printf '%s\n' "$existing" | awk "
    /^$START_MARK$/ { skip=1; next }
    /^$END_MARK$/   { skip=0; next }
    !skip { print }
  ")
  printf '%s\n%s\n' "$cleaned" "$BLOCK" | crontab -
  echo "→ crontab updated. Current managed block:"
  crontab -l | awk "/^$START_MARK$/,/^$END_MARK$/"
}

remove_block() {
  local existing cleaned
  existing=$(crontab -l 2>/dev/null || true)
  cleaned=$(printf '%s\n' "$existing" | awk "
    /^$START_MARK$/ { skip=1; next }
    /^$END_MARK$/   { skip=0; next }
    !skip { print }
  ")
  printf '%s' "$cleaned" | crontab -
  echo "→ removed MEDDOC-TESTS block from crontab"
}

case "$MODE" in
  dry)     echo "$BLOCK" ;;
  remove)  remove_block ;;
  install) install_block ;;
esac
