#!/usr/bin/env bash
# ============================================================================
# Assert AGENTS.md still fits in one read. READ-ONLY.
#   0 = under budget   1 = OVER BUDGET (a FINDING)   2 = can't tell
# ----------------------------------------------------------------------------
# WHY: on 2026-08-26 AGENTS.md was 243,023 characters against a 150,000-char
# tool read limit. A session could load a TRUNCATED rulebook and never be told —
# and a rule you cannot read is not a weaker rule, it is an absent one. The
# failure is silent, which is what makes it a stale-authority hazard rather
# than a formatting complaint.
#
# The cure was a SPLIT, not a trim: AGENTS.md keeps the live instruction set
# plus a one-row-per-entry CANON INDEX, and every full body lives in
# docs/canon/, verbatim. This check exists so the file cannot silently grow
# back — "a stated invariant is a WISH until something asserts it."
#
# THE BUDGET IS 120,000, DELIBERATELY BELOW THE 150,000 LIMIT. The alarm has to
# arrive with room to act in, not after truncation has already happened. A
# budget set AT the limit fires for the first time on the day it is too late.
#
# ⚠️ THIS CHECK IS TREE-RELATIVE ON PURPOSE, AND THAT IS NOT THE F28 DEFECT.
# It resolves AGENTS.md from its OWN location, so it judges the checkout it
# ships in — which is the correct universe for a check CI runs on a PR head.
# The standing PRODUCTION checks must run from /opt/meddoc-pro because they
# make claims about production; this one makes a claim about a file in a tree.
# Do not "fix" it to anchor on the shared tree — that would make CI grade the
# wrong file.
# ============================================================================
set -uo pipefail

BUDGET="${AGENTS_MD_BUDGET:-120000}"
LIMIT=150000
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$REPO_DIR/AGENTS.md"

if [ ! -f "$FILE" ]; then
  echo "🟡 CANNOT TELL — no AGENTS.md at $FILE"
  exit 2
fi
if [ ! -r "$FILE" ]; then
  echo "🟡 CANNOT TELL — $FILE is not readable"
  exit 2
fi

# Characters, not bytes: the read limit is a character limit and this file is
# full of multi-byte punctuation and emoji. `wc -m` respects the locale.
CHARS="$(LC_ALL=C.UTF-8 wc -m < "$FILE" | tr -d ' ')"

# ⚠️ NEVER NORMALISE AN IMPOSSIBLE VALUE. A zero here means the instrument
# failed, not that the rulebook is empty — reporting it as "under budget" is
# exactly how a broken probe becomes a green.
case "$CHARS" in
  ''|*[!0-9]*) echo "🟡 CANNOT TELL — wc -m returned '$CHARS'"; exit 2 ;;
esac
if [ "$CHARS" -lt 1000 ]; then
  echo "🟡 CANNOT TELL — AGENTS.md reads $CHARS chars, which cannot be right"
  exit 2
fi

if [ "$CHARS" -gt "$BUDGET" ]; then
  cat <<MSG
🔴 AGENTS.md IS OVER BUDGET — $CHARS chars, budget $BUDGET (hard limit $LIMIT)

  THE FIX IS THE SPLIT RULE, NOT A TRIM. Nothing is deleted from canon:

    1. move the entry's FULL body to docs/canon/<NN>-<slug>.md, verbatim,
       with the dated provenance header the other files carry;
    2. leave a ONE-LINE row in this file's CANON INDEX — the entry's exact
       title, its own stated tell, and the pointer — so every existing
       citation still greps and still resolves;
    3. both in the SAME commit.

  An index row is a POINTER, NEVER THE RULE. See docs/canon/README.md.
  Deleting canon to pass this check is the one repair that is not allowed.
MSG
  exit 1
fi

echo "🟢 AGENTS.md $CHARS chars — under the $BUDGET budget ($((BUDGET - CHARS)) to spare; hard limit $LIMIT)"
exit 0
