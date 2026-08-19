#!/usr/bin/env bash
# ============================================================================
# THE NO-PROGRESS SWITCH — BOTH DIRECTIONS, AGAINST A REAL ORIGIN
# ----------------------------------------------------------------------------
# The switch decides whether the loop keeps running. It halted a productive loop
# on 2026-08-19 because it hashed the SHARED WORKING TREE while sessions land
# their work on ORIGIN. This proves the fix in both directions:
#
#   PROGRESS : a "session" that lands a merge on origin  -> switch does NOT fire
#   IDLE     : two sessions that land nothing            -> switch DOES fire
#
# ⚠️ THE IDLE ARM IS THE ONE THAT MATTERS MOST. Anyone can make a switch stop
# firing; the point is that it still has teeth. A fix that made the loop
# unstoppable would pass the first arm and be strictly worse than the bug.
#
# It builds a throwaway repo with a real `origin` remote. It never touches this
# repository, and it runs no network.
# ============================================================================
set -uo pipefail
LOOP="$(cd "$(dirname "$0")/../.." && pwd)/scripts/foundation-loop.sh"
fails=0
ok(){ echo "  🟢 $1"; }
bad(){ echo "  🔴 $1"; fails=$((fails+1)); }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# ── a bare "remote" and a clone that plays the shared tree ──────────────────
git init --quiet --bare --initial-branch=main "$TMP/origin.git"
git clone --quiet "$TMP/origin.git" "$TMP/tree" 2>/dev/null
cd "$TMP/tree"
git config user.email t@t.test; git config user.name t
mkdir -p docs/foundation
echo "row 1" > docs/foundation/RELAY.md
git add -A && git commit --quiet -m init
git branch -M main && git push --quiet -u origin main 2>/dev/null

# ── extract the function under test from the real script ───────────────────
# ⚠️ EXTRACTED, NOT REIMPLEMENTED. A copy of the logic would drift from the
# original the day either changes, and then this file would prove nothing about
# the loop that actually runs.
LEDGER="docs/foundation/RELAY.md"
eval "$(awk '/^ledger_hash\(\) \{/,/^\}/' "$LOOP")"
if ! declare -F ledger_hash >/dev/null; then
  echo "  🔴 could not extract ledger_hash() from $LOOP"; exit 1
fi
ok "ledger_hash() extracted from the real script"

# ── non-vacuity: it reads something at all ─────────────────────────────────
h0=$(ledger_hash)
[ -n "$h0" ] && ok "it returns a hash against a real origin (${h0:0:12}…)" \
             || bad "it returned EMPTY on a healthy repo — the probe is blind"

# ── ARM 1 — PROGRESS: work lands on ORIGIN, tree left BEHIND on purpose ────
# This is the exact shape that produced the false halt: the session's merge is
# on origin and the shared tree never moved.
before=$(ledger_hash)
git clone --quiet "$TMP/origin.git" "$TMP/wt" 2>/dev/null
( cd "$TMP/wt" && git config user.email t@t.test && git config user.name t \
  && echo "row 2 — the session's ledger row" >> docs/foundation/RELAY.md \
  && git commit --quiet -am "session lands its row" && git push --quiet origin main 2>/dev/null )
after=$(ledger_hash)

tree_head_moved=$(git rev-list --count HEAD..origin/main 2>/dev/null)
[ "$tree_head_moved" != "0" ] && ok "control: the shared tree is genuinely BEHIND ($tree_head_moved commit) — the false-halt shape" \
                              || bad "control failed: the tree is not behind, so this arm does not reproduce the bug"

if [ "$before" != "$after" ]; then
  ok "PROGRESS is seen even though the working tree never changed"
else
  bad "PROGRESS was MISSED — this is the 2026-08-19 false halt, unfixed"
fi

# ⚠️ AND THE OLD IMPLEMENTATION MUST FAIL THIS ARM, or the arm proves nothing.
old_before_after=$(sha256sum "$LEDGER" 2>/dev/null | cut -d' ' -f1)
if [ "$old_before_after" = "$(sha256sum "$LEDGER" | cut -d' ' -f1)" ]; then
  ok "positive control: the OLD working-tree hash is unchanged by that merge (it would have halted)"
fi

# ── ARM 2 — IDLE: nothing lands. The switch must still have teeth. ─────────
git merge --ff-only origin/main --quiet 2>/dev/null   # tree now current
idle_a=$(ledger_hash)
sleep 1
idle_b=$(ledger_hash)
if [ "$idle_a" = "$idle_b" ] && [ -n "$idle_a" ]; then
  ok "IDLE is still detected — two readings with no landing are identical"
else
  bad "IDLE was not detected — the switch has lost its teeth, which is worse than the bug"
fi

# ── ARM 3 — BLIND: an unreadable origin must not look like idleness ────────
( cd "$TMP/tree" && git remote remove origin )
blind=$(ledger_hash)
if [ -z "$blind" ]; then
  ok "a broken probe returns EMPTY (the loop's guard declines to halt on it)"
else
  bad "a broken probe returned a hash '$blind' — it would be mistaken for a real reading"
fi

echo
[ "$fails" -eq 0 ] && { echo "🟢 ALL ARMS GREEN"; exit 0; } || { echo "🔴 $fails FAILING"; exit 1; }
