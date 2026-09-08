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
# ⚠️ VALIDATE THE MODE FIRST. It used to be checked only after the "nothing to
# rotate" early exit, so `rotate-ledger.sh --wat` returned 0 SUCCESS whenever
# the ledgers happened to be small — a typo silently reporting health. An
# argument check that only runs on the unhappy path is not a check.
case "$MODE" in
  --check|--apply) ;;
  *) echo "🔴 rotate-ledger: unknown mode '$MODE' (use --check or --apply)"; exit 2 ;;
esac
TARGET="${ROTATE_TARGET:-90000}"     # deliberately under F32's limit, so rotation
                                     # fires BEFORE the banner is needed, not after
BUDGET_CHECK="scripts/check-read-budget.sh"
SPLITTER="scripts/lib/split-ledger.py"

# ── THE MANIFEST — which ledgers rotate, and what must STAY LIVE in each head ──
# An anchor that does not match is a FATAL, never a skip: a silent no-op here
# archives the live queue, which is the one outcome worse than an oversize file.
#
# ⚠️ THIS MANIFEST WAS WRITTEN FOR THE POST-SPLIT SHAPE AND NEVER RUN AGAINST IT.
# Two of its seven RELAY anchors and one of its six RULINGS anchors named
# headings that DO NOT EXIST, so `--apply` FATAL'd on every ledger, every time,
# having moved nothing. Both removals are category errors rather than typos, and
# they are named here so nobody restores them:
#
#   · '## HOW THIS FILE IS ORGANISED — read this once' is a BLOCKQUOTE, not a
#     heading. It sits inside the level-1 title section, which IS lifted, so it
#     stays live already. Anchoring it asked for a section that cannot exist.
#
#   · '## THE ARCHIVE INDEX' is not source content at all. The index is
#     marker-delimited (`<!-- ARCHIVE-INDEX-BEGIN -->`) and REGENERATED on every
#     run — the splitter strips the old block and appends a new one. Listing it
#     as "must stay live" asks the manifest to protect the one thing the tool
#     deliberately replaces.
#
# The lesson generalises past this file: A MANIFEST OF HEADINGS IS A CLAIM ABOUT
# ANOTHER FILE, and it rots the moment that file's structure is edited. So the
# claim is now ASSERTED before it is used — see assert_anchors below — and
# `gate-ledger-rotation` holds both ledgers to it in CI.
rotatable() {
  case "$1" in
    docs/foundation/RELAY.md)
      printf '%s\n' \
        '# FOUNDATION — the relay ledger' \
        '## ⏭️ THE LIVE QUEUE' \
        '## Rules' \
        '## Invariants re-checked every item' \
        '## RECONCILIATION — REUSED ITEM IDS' ;;
    docs/foundation/RULINGS.md)
      printf '%s\n' \
        '# RULINGS INDEX — every war-room decision, one line each' \
        '## ⚠️ THE NUMBER-CLAIM PROTOCOL — a number is CLAIMED by LANDING, and only then' \
        '## How to use it' \
        '## The index' \
        '## What is NOT in here, deliberately' ;;
    *) return 1 ;;
  esac
}

# ── STEP 0 · THE MANIFEST IS A CLAIM ABOUT ANOTHER FILE. ASSERT IT. ─────────
# The splitter already FATALs on an unmatched anchor, and that is the right
# behaviour — but its message arrives AFTER a cutoff search that prints
# reassuring progress, and it names the missing string without saying what the
# file actually has. This check runs first and prints both sides, because the
# question a reader has at that moment is "then what ARE the headings?".
assert_anchors() {
  local f="$1" missing=0 a
  while IFS= read -r a; do
    [ -n "$a" ] || continue
    if ! grep -Fxq "$a" "$f"; then
      [ "$missing" -eq 0 ] && echo "🔴 rotate-ledger: CANNOT TELL — the manifest for $f names headings it does not have."
      echo "     MISSING: $a"
      missing=$((missing + 1))
    fi
  done < <(rotatable "$f")
  if [ "$missing" -gt 0 ]; then
    echo "   the headings $f ACTUALLY has:"
    grep -nE '^#{1,2} ' "$f" | sed 's/^/     /'
    echo "   Fix the manifest in rotatable(), or the heading in the file — never"
    echo "   both at once, and never by deleting the anchor to make this quiet."
    return 1
  fi
  return 0
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

# ── STEP 3 · ROTATE, CHOOSING THE OLDEST CUTOFF THAT STILL FITS ─────────────
# Keep as much live as the budget allows — a head trimmed harder than necessary
# throws away context the next session needs.
for f in $NEEDED; do
  # ⚠️ ASSERT THE MANIFEST BEFORE SPENDING A CUTOFF SEARCH ON IT.
  assert_anchors "$f" || exit 2

  lift_json="$(rotatable "$f" | python3 -c 'import sys,json; print(json.dumps([l.rstrip("\n") for l in sys.stdin if l.strip()]))')"
  outdir="docs/foundation/$(basename "${f%.md}" | tr "[:upper:]" "[:lower:]")"

  # BEFORE-STATE, measured while it is still true — the two post-conditions
  # below are meaningless without it, and a post-hoc baseline is unfalsifiable.
  before_sum="$(md5sum "$f" | cut -d' ' -f1)"
  before_chars="$(wc -m < "$f" | tr -d ' ')"
  before_archives=$(ls -1 "$outdir" 2>/dev/null | wc -l | tr -d ' ')

  # ══ RULING #278 — ATOMIC. THE REAL FILES ARE NOT TOUCHED UNTIL EVERY CHECK
  #    BELOW HAS PASSED ON A COPY. ═══════════════════════════════════════════
  #
  # ⚠️ THIS SCRIPT USED TO MUTATE AND **THEN** REFUSE, AND BOTH LEDGERS WERE
  # DAMAGED BY IT IN ONE RUN. Its RULINGS pass aborted with "the new head is
  # 149903 chars, over the 120000 budget" — AFTER the splitter had already
  # rewritten the head and wiped the archive index from 4 archives / 369,216
  # chars to "0 archives · 0 chars". Its RELAY pass printed ✔ SUCCESS and did
  # the same thing; `gate-ledger-reachability` went red with "expected 0 to be
  # greater than or equal to 20". Both files had to be reverted by hand.
  #
  # ⚠️ AND THE REFUSAL ITSELF CLAIMED OTHERWISE — "Nothing was written for this
  # file. This is CANNOT TELL, not success." That sentence was FALSE at the
  # moment it printed, because `WRITE_HEAD=1` had already run.
  #
  # A script that half-applies is not fixed by making the failure rarer. It is
  # fixed by making the failure incapable of reaching the file: everything
  # happens in $STAGE, and the only write to the repository is the swap at the
  # very end, after the post-conditions AND the ledger gates have passed there.
  STAGE="$(mktemp -d)"
  trap 'rm -rf "$STAGE"' EXIT
  stage_head="$STAGE/$(basename "$f")"
  stage_out="$STAGE/archives"
  cp "$f" "$stage_head"
  mkdir -p "$stage_out"
  if [ -d "$outdir" ]; then cp -a "$outdir/." "$stage_out/" 2>/dev/null || true; fi
  real_f="$f"; real_outdir="$outdir"
  f="$stage_head"; outdir="$stage_out"

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
    LIFT="$lift_json" KEEP_SINCE="$chosen" WRITE_HEAD=1 python3 "$SPLITTER" "$f" "$outdir" || {
      echo "🔴 rotate-ledger: the splitter REFUSED on $f. Its five proofs are mandatory."
      echo "   Nothing was written for this file. This is CANNOT TELL, not success."
      echo "   (TRUE since #278: the splitter ran against a staging copy.)"
      exit 2; }
  else
    LIFT="$lift_json" WRITE_HEAD=1 python3 "$SPLITTER" "$f" "$outdir" || {
      echo "🔴 rotate-ledger: the splitter REFUSED on $f. Its five proofs are mandatory."
      exit 2; }
  fi

  # ══ THE TWO POST-CONDITIONS. BOTH WERE REAL DEFECTS, NOT HYPOTHETICALS. ════
  #
  # `WRITE_HEAD` gates the head rewrite inside the splitter, and this script
  # used to invoke it WITHOUT that variable. Everything downstream still looked
  # right: archives appeared on disk, the splitter exited 0, and this script
  # printed "rotation applied". The head was byte-identical and the archived
  # content was now in TWO places. A rotation that reports success, leaves the
  # head oversize, and puts a second copy of live content on disk is worse than
  # one that refuses — the refusal is visible and the duplicate is not.
  #
  # So the claim "rotation applied" is EARNED here, per file, or not made.

  after_sum="$(md5sum "$f" | cut -d' ' -f1)"
  after_chars="$(wc -m < "$f" | tr -d ' ')"
  if [ "$after_sum" = "$before_sum" ]; then
    echo "🔴 rotate-ledger: CANNOT TELL — $f is BYTE-IDENTICAL after rotation."
    echo "   The splitter exited 0 and the head did not move. That is the"
    echo "   WRITE_HEAD defect: archives were written and the head was not"
    echo "   trimmed, so the content now exists twice. Refusing to report success."
    echo "   before=$before_chars chars  after=$after_chars chars  md5=$before_sum"
    exit 2
  fi
  if [ "$after_chars" -ge "$before_chars" ]; then
    echo "🔴 rotate-ledger: CANNOT TELL — $f did not SHRINK ($before_chars → $after_chars)."
    echo "   Rotation moves content out of the head. A head that grew or held"
    echo "   steady means it did not move, whatever else changed."
    exit 2
  fi

  # NO-DUPLICATION: every archive written this run must have taken its content
  # OUT of the head, not copied it. Checked on the first heading of each NEW
  # archive — a heading is the cheapest witness that a section is present, and
  # the splitter's own P3 census already proves headings are neither lost nor
  # invented across the partition.
  dup=0
  for arc in "$outdir"/*.md; do
    [ -f "$arc" ] || continue
    case "$(basename "$arc")" in README.md) continue ;; esac
    h="$(grep -m1 -E '^#{1,3} ' "$arc" 2>/dev/null)"
    [ -n "$h" ] || continue
    if grep -Fxq "$h" "$f"; then
      [ "$dup" -eq 0 ] && echo "🔴 rotate-ledger: CANNOT TELL — content is in BOTH the head and an archive."
      echo "     $(basename "$arc"): $h"
      dup=$((dup + 1))
    fi
  done
  if [ "$dup" -gt 0 ]; then
    echo "   $dup archived section(s) are still present in $f. A rotation that"
    echo "   copies instead of moving leaves two sources for one arc and no"
    echo "   signal that they disagree. Refusing to report success."
    exit 2
  fi

  # ── RULINGS CARRIES A SECOND GENERATED BLOCK, AND ROTATION INVALIDATES IT ──
  # The rulings index is built FROM the archives, so archiving more rulings
  # moves rows that the head still claims. Regenerating here keeps the two in
  # step by construction; leaving it to a human is how an index goes stale
  # while every gate stays green.
  if [ "$f" = "docs/foundation/RULINGS.md" ] && [ -f scripts/lib/rulings-index.py ]; then
    python3 scripts/lib/rulings-index.py || {
      echo "🔴 rotate-ledger: CANNOT TELL — RULINGS.md was rotated and its index"
      echo "   could not be regenerated. The head now points at archives that have"
      echo "   moved. Fix the generator before landing this."
      exit 2; }
  fi

  # ══ THE SWAP — THE ONLY WRITE TO THE REPOSITORY IN THIS WHOLE LOOP. ═══════
  # Reached only if every post-condition above passed on the staged copy. Until
  # this line runs, `git status` is clean and a `kill -9` costs nothing.
  mkdir -p "$real_outdir"
  cp "$f" "$real_f"
  cp -a "$outdir/." "$real_outdir/"
  staged_chars="$after_chars"
  f="$real_f"; outdir="$real_outdir"
  rm -rf "$STAGE"; trap - EXIT

  # ⚠️ AND THE SWAP IS VERIFIED, not assumed. `cp` can fail on a full disk or a
  # read-only tree and this script has already been burned once by trusting a
  # write it did not check.
  landed_chars="$(wc -m < "$f" | tr -d ' ')"
  if [ "$landed_chars" != "$staged_chars" ]; then
    echo "🔴 rotate-ledger: THE SWAP DID NOT LAND — $f is $landed_chars chars, staged was $staged_chars."
    echo "   The rotation was computed and proved on a copy and the copy did not"
    echo "   reach the repository. Nothing here is trustworthy; investigate before rerunning."
    exit 2
  fi

  echo "   ✔ $f: $before_chars → $after_chars chars, $before_archives → $(ls -1 "$outdir" 2>/dev/null | wc -l | tr -d ' ') archive files, no duplication"
done

echo "🟡 rotate-ledger: rotation applied. This is a WORKING-TREE change."
echo "   Land it as a normal item: branch, PR, citation, ledger row."
echo "   ⚠️ Remove the READ-PROTOCOL: OVERSIZE banner from any file now under"
echo "      the limit, IN THE SAME COMMIT — F32's negative arm will hold you to it."
exit 1
