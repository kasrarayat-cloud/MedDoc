#!/usr/bin/env bash
# ============================================================================
# A ruling cited in TRACKED SOURCE must already have a row in RULINGS.md.
# ----------------------------------------------------------------------------
#   0 = nothing cited, or everything cited is recorded
#   1 = a ruling is cited in source and has no row  (a FINDING)
#   2 = cannot tell — the ledger is missing
#
# WHY THIS IS A SCRIPT AND NOT A PARAGRAPH.
#
# `AGENTS.md` has required, since it was written, that the session receiving a
# war-room ruling records its row in RULINGS.md in the FIRST commit it makes,
# before building anything on it. The rule exists because a ruling that lives
# only in a transcript lets a later session reach the opposite conclusion just
# as confidently — a CONTRADICTION, not merely duplicated effort.
#
# ⚠️ IT FAILED THREE TIMES IN ONE SESSION, and the shape of the failure is the
# argument for mechanising it:
#
#   #162-#165   recorded after four rulings' work was built, proved and
#               committed — caught by a lens auditing an unrelated permission
#   #167        recorded after it was committed AND cited by number in shipped
#               source — caught by a lens auditing documentation
#   #168        recorded after it was committed — caught by the session itself
#
# DETECTION IMPROVED EVERY TIME. BEHAVIOUR DID NOT CHANGE ONCE. All three
# happened to a session that had just written about the previous one, and the
# second and third happened with the archive containing the apology open.
#
#   Writing a lesson down does not cause obedience to it. Nor does having just
#   written it. Nor does having been corrected for it twice.
#
# The rule is not disagreed with, not expensive, and not forgotten under load.
# It is simply not attached to any moment that forces it. Every other landing
# obligation here has a hook, a script or a CI gate. This one had a paragraph.
# ============================================================================
set -euo pipefail

# ⚠️ THE ESCAPE IS IMPLEMENTED, NOT MERELY ADVERTISED. The failure message names
# this variable; a message offering a door that does not open is worse than no
# door, because the reader believes they have one.
[ "${ALLOW_UNRECORDED_RULING:-}" = "1" ] && exit 0

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEDGER="$REPO_DIR/docs/foundation/RULINGS.md"

if [ ! -f "$LEDGER" ]; then
  echo "🟡 CANNOT TELL — no ledger at $LEDGER" >&2
  exit 2
fi

# ⚠️ THE **STAGED** DIFF, NOT THE WORKING TREE. The obvious version reads the
# tree and therefore judges a DIFFERENT SET from the one being committed: work
# in progress reds a clean commit, and a staged citation in an otherwise dirty
# tree slips through. `--cached` is the whole point.
#
# ⚠️ AND ONLY ADDED LINES. `-U0` drops context, so a citation that merely sits
# NEAR an edit is not attributed to it.
#
# ⚠️ AND `docs/` IS EXCLUDED BY CONSTRUCTION. A canon entry, a retrospective or
# a report discussing a historical ruling is describing the past, not claiming
# the ruling is current — and without this exclusion every retrospective in this
# programme reds.
#
# ⚠️ AND THE GATE DOES NOT SCAN ITSELF — which is not tidiness, it is the
# probe-that-matches-itself family. Run against its own landing commit, this
# check REFUSED, naming `#199`, `#200` and `#999`: every one of them was its own
# prose about which numeric range it matches, or a fixture in its own arms. A
# search whose pattern appears in the searcher cannot come back clean, and a
# gate that reports its own documentation teaches the next reader to silence it.
#
# ⚠️ THE LIMIT THIS BUYS, STATED: a ruling cited as live justification INSIDE
# these two files is not checked. That is narrow and deliberate — they are the
# gate — and it is the only exclusion of its kind here.
staged="$(git -C "$REPO_DIR" diff --cached -U0 --diff-filter=ACMR \
            -- . \
            ':(exclude)docs/' \
            ':(exclude)scripts/check-ruling-recorded.sh' \
            ':(exclude)apps/transcribe-md/src/lib/__tests__/gate-ruling-recorded.test.ts' \
            2>/dev/null || true)"

# Added lines only, and strip the leading '+'.
added="$(printf '%s\n' "$staged" | grep -E '^\+' | grep -vE '^\+\+\+' || true)"
[ -z "$added" ] && exit 0

# ⚠️ `PR #933` IS NOT A RULING, and both wear `#NNN`. A citation immediately
# preceded by `PR ` or `pull/` is dropped. This is a HEURISTIC and it is stated
# as one: it errs toward CHECKING, so its failure mode is a message asking you
# to confirm, never a silent pass.
#
# ⚠️ AND THE RANGE IS `#[0-9]{2,3}`, NOT `#1[0-9]{2}` — WHICH IS WHAT THE
# CANON ENTRY THAT ORDERED THIS SCRIPT ACTUALLY SPECIFIES. `#1[0-9]{2}` matches
# 100-199 and nothing else, so it covers today's rulings exactly and **stops
# matching at ruling #200**, silently, with no test failing and no message.
# Rulings stand at #175 today.
#
# That is a MEASUREMENT OF TODAY'S CORPUS baked in as though it were a property
# of the code, and the re-arming condition is stated here in the same breath as
# the fix, per the rule about population facts: this widened form covers #10
# through #999 and **breaks at #1000**. When a ruling number reaches four
# digits, this line is the one to change.
cited="$(printf '%s\n' "$added" \
  | sed -E 's/(PR|pull request|pull)[[:space:]]*#[0-9]+/ /gI' \
  | grep -oE '#[0-9]{2,3}\b' | sort -u || true)"
[ -z "$cited" ] && exit 0

missing=""
checked=0
for n in $cited; do
  checked=$((checked + 1))
  grep -q -F -- "$n" "$LEDGER" || missing="${missing}  ${n}\n"
done

if [ -z "$missing" ]; then
  echo "🟢 rulings: $checked cited in staged source, all recorded."
  exit 0
fi

cat >&2 <<MSG

  BLOCKED: a ruling is cited in staged SOURCE and has no row in the ledger.

$(printf "%b" "$missing")
  AGENTS.md requires the receiving session to record a ruling in the FIRST
  commit it makes, before building anything on it. A ruling that exists only in
  a transcript is not a ruling: the next session cannot see it, and can reach
  the opposite conclusion just as confidently.

  Add the row to docs/foundation/RULINGS.md — and the body to
  docs/foundation/rulings/ — in THIS commit.

  ⚠️ If the number is a PULL REQUEST and not a ruling, write it as "PR #NNN"
  and this check will ignore it. That is not a workaround; it is the same
  distinction the ledger makes.

  If you are certain and this is a one-off:
      ALLOW_UNRECORDED_RULING=1 git commit …

MSG
exit 1
