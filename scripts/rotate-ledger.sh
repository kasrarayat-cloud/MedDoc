#!/usr/bin/env bash
# ============================================================================
# ROTATE-LEDGER — keep the FOUNDATION ledgers readable, forever, without hands.
# ----------------------------------------------------------------------------
# The 2026-08-26 split made RELAY.md and RULINGS.md readable once. This keeps
# them readable. Measured that day: the ledger adds MORE THAN THE ENTIRE READ
# BUDGET PER DAY — a head keeping only "2026-08-25 onward" was already 155,689
# chars. A one-time split without rotation is a treadmill, and the second lap
# arrives within the week.
#
# ⚠️ IT IS BANNER-TRIGGERED, NOT CALENDAR-TRIGGERED. The authority on "is this
# file too big" is check-read-budget.sh (F32). This script DELEGATES to it and
# never re-implements the budget — the same reasoning that keeps the pre-push
# hook and merge-pr.sh sharing one inflight check, and that keeps F32 itself
# shelling out to check-agents-md-size.sh. A second copy of a threshold drifts
# from the first the day either is fixed.
#
# ⚠️ IT NEVER MERGES AND NEVER DEPLOYS. It produces a working-tree change for
# the loop to land as a NORMAL item: PR, citation, ledger row. Rotation is not
# a privileged operation and must not become one.
#
# EXIT CODES
#   0  nothing to rotate — every watched ledger is inside its budget
#   1  rotation PERFORMED (or, with --check, rotation is NEEDED)
#   2  CANNOT TELL — fail-closed. A missing delegate, an unparseable manifest,
#      or a splitter that refused. Never treated as "nothing to do".
# ============================================================================
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || { echo "🔴 rotate-ledger: cannot cd to repo root"; exit 2; }

MODE="${1:---check}"
TARGET="${ROTATE_TARGET:-90000}"     # deliberately under F32's limit, so rotation
                                     # fires BEFORE the banner is needed, not after
BUDGET_CHECK="scripts/check-read-budget.sh"
SPLITTER="scripts/lib/split-ledger.py"

# ── THE MANIFEST — which ledgers rotate, and what must STAY LIVE in each head ──
# An anchor that does not match is a FATAL, never a skip: a silent no-op here
# archives the live queue, which is the one outcome worse than an oversize file.
rotatable() {
  case "$1" in
    docs/foundation/RELAY.md)
      printf '%s\n' \
        '# FOUNDATION — the relay ledger' \
        '## HOW THIS FILE IS ORGANISED — read this once' \
        '## ⏭️ THE LIVE QUEUE' \
        '## Rules' \
        '## Invariants re-checked every item' \
        '## RECONCILIATION — REUSED ITEM IDS' \
        '## THE ARCHIVE INDEX' ;;
    docs/foundation/RULINGS.md)
      printf '%s\n' \
        '# RULINGS INDEX — every war-room decision, one line each' \
        '## ⚠️ THE NUMBER-CLAIM PROTOCOL — a number is CLAIMED by LANDING, and only then' \
        '## How to use it' \
        '## The index' \
        '## What is NOT in here, deliberately' \
        '## THE ARCHIVE INDEX' ;;
    *) return 1 ;;
  esac
}

# ── STEP 1 · ASK THE AUTHORITY, DO NOT GUESS ────────────────────────────────
if [ ! -x "$BUDGET_CHECK" ] && [ ! -f "$BUDGET_CHECK" ]; then
  echo "🔴 rotate-ledger: CANNOT TELL — $BUDGET_CHECK is absent."
  echo "   The budget authority is F32's check. This script refuses to invent one."
  exit 2
fi
BUDGET_OUT="$(bash "$BUDGET_CHECK" 2>&1)"; BUDGET_RC=$?
if [ "$BUDGET_RC" -eq 2 ]; then
  echo "🔴 rotate-ledger: CANNOT TELL — the budget check itself returned 2."
  printf '%s\n' "$BUDGET_OUT" | sed 's/^/   | /'
  exit 2
fi

# POSITIVE CONTROL: the delegate must actually name files. A budget check that
# names nothing is a broken instrument, and its silence reads exactly like health.
if ! printf '%s' "$BUDGET_OUT" | grep -q 'RELAY\.md'; then
  echo "🔴 rotate-ledger: CANNOT TELL — the budget check named no ledger."
  echo "   Positive control failed: its output does not mention RELAY.md at all."
  exit 2
fi

# ── STEP 2 · WHICH ROTATABLE LEDGERS ARE OVER? ──────────────────────────────
NEEDED=""
for f in docs/foundation/RELAY.md docs/foundation/RULINGS.md; do
  [ -f "$f" ] || continue
  chars=$(wc -m < "$f" | tr -d ' ')
  if [ "$chars" -gt "$TARGET" ]; then
    NEEDED="$NEEDED $f"
    echo "   · $f — ${chars} chars, over the ${TARGET} rotation target"
  else
    echo "   · $f — ${chars} chars, inside the target"
  fi
done

if [ -z "$NEEDED" ]; then
  echo "🟢 rotate-ledger: nothing to rotate."
  exit 0
fi

if [ "$MODE" = "--check" ]; then
  echo "🟡 rotate-ledger: rotation NEEDED for:$NEEDED"
  echo "   run: bash scripts/rotate-ledger.sh --apply"
  exit 1
fi

[ "$MODE" = "--apply" ] || { echo "🔴 rotate-ledger: unknown mode '$MODE' (use --check or --apply)"; exit 2; }

# ── STEP 3 · ROTATE, CHOOSING THE OLDEST CUTOFF THAT STILL FITS ─────────────
# Keep as much live as the budget allows — a head trimmed harder than necessary
# throws away context the next session needs.
for f in $NEEDED; do
  lift_json="$(rotatable "$f" | python3 -c 'import sys,json; print(json.dumps([l.rstrip("\n") for l in sys.stdin if l.strip()]))')"
  outdir="docs/foundation/$(basename "${f%.md}" | tr "[:upper:]" "[:lower:]")"

  dates=$(grep -oE '^#{1,2} .*(20[0-9]{2}-[0-9]{2}-[0-9]{2})' "$f" \
          | grep -oE '20[0-9]{2}-[0-9]{2}-[0-9]{2}' | sort -u)
  chosen=""
  for d in $dates; do
    out=$(LIFT="$lift_json" KEEP_SINCE="$d" DRY_RUN=1 python3 "$SPLITTER" "$f" /dev/null 2>&1) || continue
    hc=$(printf '%s' "$out" | python3 -c 'import sys,json
try: print(json.load(sys.stdin)["head_chars"])
except Exception: print(10**9)' 2>/dev/null)
    if [ "${hc:-1000000000}" -le "$TARGET" ]; then chosen="$d"; break; fi
  done

  echo "   → $f: cutoff $( [ -n "$chosen" ] && echo "KEEP_SINCE=$chosen" || echo "(none fits — archiving all closed arcs)" )"
  if [ -n "$chosen" ]; then
    LIFT="$lift_json" KEEP_SINCE="$chosen" python3 "$SPLITTER" "$f" "$outdir" || {
      echo "🔴 rotate-ledger: the splitter REFUSED on $f. Its five proofs are mandatory."
      echo "   Nothing was written for this file. This is CANNOT TELL, not success."
      exit 2; }
  else
    LIFT="$lift_json" python3 "$SPLITTER" "$f" "$outdir" || {
      echo "🔴 rotate-ledger: the splitter REFUSED on $f. Its five proofs are mandatory."
      exit 2; }
  fi
done

echo "🟡 rotate-ledger: rotation applied. This is a WORKING-TREE change."
echo "   Land it as a normal item: branch, PR, citation, ledger row."
echo "   ⚠️ Remove the READ-PROTOCOL: OVERSIZE banner from any file now under"
echo "      the limit, IN THE SAME COMMIT — F32's negative arm will hold you to it."
exit 1
