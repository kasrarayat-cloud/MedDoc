#!/usr/bin/env bash
# ============================================================================
# EVERY FILE STEP 0 TELLS A SESSION TO READ IS EITHER READABLE, OR SAYS IT IS
# NOT. READ-ONLY.
#   0 = every named file is accounted for
#   1 = a FINDING (a file over the read limit that does not declare it, or a
#       readable file wearing the oversize banner it has no right to)
#   2 = can't tell
# ----------------------------------------------------------------------------
# WHY THIS EXISTS, AND WHY IT IS NOT check-agents-md-size.sh's JOB.
#
# On 2026-08-26 AGENTS.md was split because 243,023 characters against a
# 150,000-character tool read limit meant a session could load a TRUNCATED
# rulebook and never be told. That cure shipped with a guard — and the guard
# watches ONE file.
#
# MASTER STEP 0.3 names FOUR:
#
#     "Read docs/foundation/SPEC.md, RELAY.md, RULINGS.md, and AGENTS.md."
#
# Measured the next day, on the very commit that landed the split:
#
#     AGENTS.md      87,383 chars    readable
#     SPEC.md        28,340 chars    readable
#     RULINGS.md    371,533 chars    2.5x the limit
#     RELAY.md    1,793,436 chars    12.0x the limit
#
# ⚠️ SO TWO OF THE FOUR FILES THE PROGRAMME ORDERS EVERY SESSION TO READ COULD
# NOT BE READ, ONE OF THEM BY TWELVE TIMES, AND NOTHING ANYWHERE SAID SO. That
# is the gate's WATCHED SET being narrower than the rule's NAMED SET — the
# split's own lesson, arriving one file over.
#
# ⚠️ AND THE LEDGER'S TRUNCATION IS WORSE THAN THE RULEBOOK'S, WHICH IS THE
# PART WORTH THE PARAGRAPH. A rulebook truncated at the top still hands back
# SOME live rules. RELAY.md is APPEND-ONLY and chronological, so the front of
# the file is its OLDEST content: a default read returns the stale end and
# omits every current arc. The reader gets a confident, well-formed, obsolete
# answer — and no signal that anything is missing.
#
# THE CURE IS NOT A BUDGET. A ledger that may not grow is not a ledger, and a
# ratchet set at today's size fails on tonight's first append. The cure is that
# an oversize file must SAY SO where a truncated reader still sees it:
#
#     an OVERSIZE file must carry the READ-PROTOCOL banner in its head.
#
# ⚠️ AND THE CHECK PINS BOTH DIRECTIONS, because a banner that outlives its
# reason is a lie that reads like a warning. A file UNDER the limit carrying
# the banner is a finding too — that is the direction a one-sided check is
# blind to, and it is the direction this one will actually meet, on the day
# somebody finally splits RELAY.md by arc and forgets to remove the notice.
#
# ⚠️ THE AGENTS.md ROW IS DELEGATED, NEVER RE-IMPLEMENTED. Its budget lives in
# scripts/check-agents-md-size.sh and this script SHELLS OUT to it, for the
# same reason the pre-push hook and merge-pr.sh share one inflight check: a
# second copy of a threshold drifts from the first the day either is changed.
#
# ⚠️ TREE-RELATIVE ON PURPOSE. It resolves the files from its OWN location, so
# it judges the checkout it ships in — the correct universe for a check CI runs
# on a PR head. This is not the F28 defect; the standing PRODUCTION checks must
# run from /opt/meddoc-pro because they make claims about production, and this
# one makes a claim about files in a tree.
# ============================================================================
set -uo pipefail

# The tool read limit these files are measured against. Overridable ONLY so the
# gate can drive the red arms; nothing in normal operation sets it.
LIMIT="${READ_BUDGET_LIMIT:-150000}"

# How far into a file the banner may sit and still be seen by a truncated read.
HEAD_LINES="${READ_BUDGET_HEAD_LINES:-60}"

# The exact token. LINE-ANCHORED at column 0 as an HTML comment, deliberately:
# prose that NAMES this token — MASTER.md's own instructions, this script, the
# gate that drives it — must never be mistaken for a file that CARRIES it.
# That is the probe-that-matches-itself failure, and anchoring is the cure.
BANNER_RE='^<!-- READ-PROTOCOL: OVERSIZE'

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# THE MANIFEST: every file a STANDING INSTRUCTION tells a session to READ.
# Adding a file to any such instruction means adding a row here, in the same
# commit.
#
# ⚠️ IT IS NOT "the files STEP 0.3 names", AND THAT DISTINCTION WAS EARNED THE
# HARD WAY — BY THIS SCRIPT MAKING THE EXACT MISTAKE IT EXISTS TO CATCH.
# The first draft scoped itself to MASTER STEP 0.3's four files and wrote, in
# its own ledger row, "it does not widen to the Rounds ledger, which STEP 0 does
# not name." STEP 0 does not. **`AGENTS.md` does** — § "Multi-session programs
# have relay ledgers — READ THEM FIRST" names all four program ledgers — and
# `docs/rounds/RELAY.md` measured 235,184 chars, 1.57x the limit. A guard whose
# watched set is narrower than the rule's named set, written by the guard that
# exists to diff watched sets against named sets, one file over. Caught before
# merge; recorded because in this programme the correction is the point.
FILES=(
  "docs/foundation/MASTER.md"
  "docs/foundation/SPEC.md"
  "docs/foundation/RELAY.md"
  "docs/foundation/RULINGS.md"
  "docs/foundation/DISCOVERY.md"
  "docs/foundation/INBOX.md"
  "docs/rounds/SPEC.md"
  "docs/rounds/RELAY.md"
)

findings=0
cannot_tell=0

echo "READ BUDGET — the tool read limit is $LIMIT characters."
echo

# --- AGENTS.md: delegated, so the budget has exactly one implementation -------
AGENTS_CHECK="$REPO_DIR/scripts/check-agents-md-size.sh"
if [ ! -f "$AGENTS_CHECK" ]; then
  echo "   🟡 AGENTS.md — CANNOT TELL: $AGENTS_CHECK is missing"
  cannot_tell=1
else
  agents_out="$(bash "$AGENTS_CHECK" 2>&1)"
  agents_rc=$?
  case "$agents_rc" in
    0) echo "   🟢 AGENTS.md — delegated to check-agents-md-size.sh: $(printf '%s' "$agents_out" | head -1)" ;;
    1) echo "   🔴 AGENTS.md — delegated check is RED:"; printf '%s\n' "$agents_out" | sed 's/^/        /'; findings=$((findings + 1)) ;;
    *) echo "   🟡 AGENTS.md — delegated check CANNOT TELL: $(printf '%s' "$agents_out" | head -1)"; cannot_tell=1 ;;
  esac
fi

# --- every other named file ---------------------------------------------------
for rel in "${FILES[@]}"; do
  path="$REPO_DIR/$rel"

  if [ ! -f "$path" ] || [ ! -r "$path" ]; then
    echo "   🟡 $rel — CANNOT TELL: missing or unreadable at $path"
    cannot_tell=1
    continue
  fi

  # Characters, not bytes: the read limit is a CHARACTER limit and these files
  # are full of multi-byte punctuation and emoji.
  chars="$(LC_ALL=C.UTF-8 wc -m < "$path" | tr -d ' ')"

  # ⚠️ NEVER NORMALISE AN IMPOSSIBLE VALUE. A zero here means the instrument
  # failed, not that the ledger is empty — calling that "well under the limit"
  # is exactly how a broken probe becomes a green.
  case "$chars" in
    ''|*[!0-9]*) echo "   🟡 $rel — CANNOT TELL: wc -m returned '$chars'"; cannot_tell=1; continue ;;
  esac
  if [ "$chars" -lt 100 ]; then
    echo "   🟡 $rel — CANNOT TELL: reads $chars chars, which cannot be right"
    cannot_tell=1
    continue
  fi

  if head -n "$HEAD_LINES" "$path" | grep -qE "$BANNER_RE"; then
    has_banner=yes
  else
    has_banner=no
  fi

  if [ "$chars" -gt "$LIMIT" ]; then
    # How much of the file a reader who just opens it actually gets.
    pct=$(( LIMIT * 100 / chars ))
    if [ "$has_banner" = yes ]; then
      echo "   🟢 $rel — $chars chars, OVERSIZE ($pct% of it fits one read) and it DECLARES the protocol"
    else
      findings=$((findings + 1))
      cat <<MSG
   🔴 $rel — $chars chars, OVER the $LIMIT read limit, AND IT DOES NOT SAY SO

        A session obeying STEP 0.3 opens this file and gets roughly $pct% of it.
        For an append-only ledger that $pct% is the OLDEST end — a confident,
        well-formed, obsolete answer with no signal that anything is missing.

        THE FIX IS A BANNER, NOT A TRIM. Nothing is deleted from a ledger.
        Put this as the first line of $rel, at column 0:

        <!-- READ-PROTOCOL: OVERSIZE - this file exceeds the tool read limit.
             A plain read is TRUNCATED and returns the OLDEST content. Read the
             head for the queue, the TAIL for the current arc, and grep for
             everything else. -->

        Deleting ledger history to pass this check is the one repair that is
        not allowed.
MSG
    fi
  else
    if [ "$has_banner" = yes ]; then
      findings=$((findings + 1))
      cat <<MSG
   🔴 $rel — $chars chars, comfortably UNDER the $LIMIT limit, and it still
        carries the READ-PROTOCOL: OVERSIZE banner.

        A warning that outlived its reason is a lie that reads like a warning.
        Remove the banner from $rel in the same commit that made it false.
MSG
    else
      echo "   🟢 $rel — $chars chars, fits one read"
    fi
  fi
done

echo
if [ "$findings" -gt 0 ]; then
  echo "🔴 READ BUDGET — $findings finding(s). A file the programme orders every session to read is misdescribed."
  exit 1
fi
if [ "$cannot_tell" -ne 0 ]; then
  echo "🟡 READ BUDGET — CANNOT TELL. An unrunnable check is 2, never a pass."
  exit 2
fi
echo "🟢 READ BUDGET — every file STEP 0 names is either readable in one read, or declares that it is not."
exit 0
