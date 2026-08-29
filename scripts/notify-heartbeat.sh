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
# Install (owner-local 08:00; the box runs UTC, so adjust the hour if the owner
# is not on UTC):
#   0 8 * * *  cd /opt/meddoc-pro && bash scripts/notify-heartbeat.sh
# ============================================================================
set -uo pipefail
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
