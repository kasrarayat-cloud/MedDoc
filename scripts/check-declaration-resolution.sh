#!/usr/bin/env bash
# ============================================================================
# READ-ONLY. Which §2.5 declaration would `deploy-prod.sh` take for THIS tree?
# ----------------------------------------------------------------------------
#   0 = a declaration covers the tree you are on
#   1 = NONE does — write one, or read what moved
#   2 = AMBIGUOUS / cannot tell
#
# ⚠️ THIS ANSWERS THE QUESTION BEFORE THE DEPLOY ASKS IT. F10's resolver is
# fail-closed, and a refusal arriving at STEP 0 of a deploy is a refusal
# arriving after somebody has already decided to ship. `deploy-prod.sh` refuses
# before it builds, migrates or recreates anything — so nothing is ever at risk
# — but the operator still finds out at the least convenient moment. Running
# this first turns that into a five-second question.
#
# It changes NOTHING and touches no container. It is the same library the deploy
# sources, not a second copy — a copy would drift from the first the day either
# is fixed, which is the whole reason `declaration.sh` is shared.
# ============================================================================
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 2

LIB="scripts/lib/declaration.sh"
if [ ! -r "$LIB" ]; then
  echo "🟡 CANNOT TELL — $LIB is missing or unreadable."
  exit 2
fi
# shellcheck source=lib/declaration.sh
. "$LIB"

DECL_DIR="docs/foundation/deploys"
if [ ! -d "$DECL_DIR" ]; then
  echo "🟡 CANNOT TELL — $DECL_DIR does not exist."
  exit 2
fi

# ⚠️ POSITIVE-CONTROL THE SCAN BEFORE BELIEVING ITS ANSWER. An empty directory
# and a broken traversal produce the same refusal, and the two mean opposite
# things. This is the house rule applied to the resolver's own input set.
CANDIDATES=$(find "$DECL_DIR" -maxdepth 1 -name '*.md' | wc -l)
echo "control     : $CANDIDATES declaration file(s) visible in $DECL_DIR"
if [ "$CANDIDATES" -eq 0 ]; then
  echo "🟡 CANNOT TELL — the directory holds no .md files at all. A refusal here"
  echo "   would say nothing about this tree; it would say the scan found nothing"
  echo "   to scan."
  exit 2
fi

declaration_resolve "$DECL_DIR"
rc=$?

case "$rc" in
  0)
    echo "🟢 a declaration covers this tree: $DECLARATION_PATH  (gate mode: $DECLARATION_MODE)"
    exit 0
    ;;
  2)
    echo "🟡 AMBIGUOUS — see above. Write a declaration naming this commit."
    exit 2
    ;;
  *)
    echo "🔴 no declaration covers this tree. Nothing is wrong with the repository;"
    echo "   this is the gate telling you what it will tell the deploy."
    exit 1
    ;;
esac
