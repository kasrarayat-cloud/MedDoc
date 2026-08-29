#!/usr/bin/env bash
# ============================================================================
# THE DAILY HEARTBEAT — one line, once, so SILENCE IS NEVER AMBIGUOUS.
# ----------------------------------------------------------------------------
# Without this, "no notifications" has two meanings that look identical on a
# phone: nothing needed you, or the channel is dead. One of those is fine and
# the other is a park nobody is coming to. This separates them.
#
# READ-ONLY. Exits 0 always — it inherits notify.sh's contract and adds nothing
# that can fail loudly.
#
# ⚠️ THE OWNER IS IN BURBANK, CALIFORNIA — 08:00 America/Los_Angeles.
#
# ⚠️ AND `CRON_TZ` IS NOT AVAILABLE HERE, WHICH IS WHY THE HOUR IS CHECKED IN THE
# SCRIPT. Measured on this box: `cron 3.0pl1-184ubuntu2`, whose `man 5 crontab`
# (302 lines) never mentions CRON_TZ and whose BINARY does not contain the
# string — so setting it is SILENTLY IGNORED and the job fires at 08:00 UTC,
# which is 01:00 Pacific. A scheduling bug that looks scheduled is the worst kind.
#
# So cron fires at BOTH UTC hours that can be 08:00 in Los Angeles —
#   08:00 PDT (summer) = 15:00 UTC  ·  08:00 PST (winter) = 16:00 UTC
# — and this script exits silently unless it really is the 08:00 hour there.
# Exactly one of the two fires per day, and DST is tracked by the tz database
# rather than by anyone remembering to shift a crontab twice a year.
#
# Install:
#   0 15,16 * * *  [ -x /opt/meddoc-pro/scripts/notify-heartbeat.sh ] && \
#                  bash /opt/meddoc-pro/scripts/notify-heartbeat.sh
# ============================================================================
set -uo pipefail

# The hour gate. Silent by design — no output means cron sends nothing.
# HEARTBEAT_FORCE=1 bypasses it for a manual test.
if [ "${HEARTBEAT_FORCE:-}" != "1" ]; then
  hour_local="$(TZ=America/Los_Angeles date +%H 2>/dev/null || echo '')"
  [ "$hour_local" = "08" ] || exit 0
fi
cd "$(dirname "$(dirname "$(readlink -f "$0")")")" 2>/dev/null || exit 0

# LIVE vs DARK — `tmux has-session` is the authority. `pgrep -f` matched itself
# once and called a dark loop LIVE for three hours; that mistake is not repeated.
if tmux has-session -t foundation 2>/dev/null; then
  loop="loop LIVE"
elif [ -f docs/foundation/STOP ]; then
  loop="loop STOPPED (STOP present)"
else
  loop="loop DARK"
fi

# Open board items, counted from the ledger's own queue table rather than guessed.
items=$(grep -cE '^\| \*\*[A-Z]' docs/foundation/RELAY.md 2>/dev/null || echo '?')
open_prs=$(gh pr list --state open --json number --jq 'length' 2>/dev/null || echo '?')

bash scripts/notify.sh heartbeat "alive · ${loop} · board ${items} items · ${open_prs} open PRs" || true
exit 0
