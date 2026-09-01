#!/usr/bin/env bash
# ============================================================================
# EVERY §2.5 DEPLOY RECORD IS TRACKED. READ-ONLY.
#   0 = every record is tracked   1 = one or more are UNTRACKED   2 = CANNOT TELL
# ----------------------------------------------------------------------------
# ⚠️ WHY THIS EXISTS, WITH THE CASE THAT CAUSED IT. Ruling #163 C.
#
# The §2.5 declaration and judgement for the deploy of `a8ead1cb` were written,
# placed and printed into the deploy transcript — and never committed. They sat
# UNTRACKED in the shared tree while `20260831-11dfaf8a`'s pair, one deploy
# earlier, was tracked on `main`. Nothing said so. A session reporting on the
# arc stated both pairs had landed, because both were present on disk and
# presence is what a human eye checks.
#
#     A DEPLOY THAT REACHED PRODUCTION WITH NO TRACKED RECORD HAS NO EVIDENCE
#     THAT ITS DECLARATION PRECEDED THE ACT — which is the entire product §2.5
#     buys. The file being on somebody's disk is not the record.
#
# It is the sibling of the already-recorded hazard that `docs/deploy-reports/`
# is tracked while `docs/deploy-logs/` is gitignored — one word apart in meaning
# and opposite in behaviour. There the evidence was written to an ignored path;
# here it was written to a tracked path and never added. Same outcome: the work
# was done and the record does not exist.
#
# ⚠️ IT IS DELIBERATELY A LOCAL CHECK, AND SAYING SO IS THE POINT. A CI checkout
# is clean by construction, so an untracked file CANNOT exist there — a CI-only
# arm would be green forever and prove nothing. The bite is here, at the deploy,
# in the tree where records are actually written.
# ============================================================================
set -uo pipefail

DIR="${1:-docs/foundation/deploys}"
REPO="${DEPLOY_RECORDS_REPO:-/opt/meddoc-pro}"

command -v git >/dev/null 2>&1 || { echo "🔴 deploy-records: no git. CANNOT TELL."; exit 2; }
git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1 || {
  echo "🔴 deploy-records: $REPO is not a git repository. CANNOT TELL."; exit 2; }
[ -d "$REPO/$DIR" ] || { echo "🔴 deploy-records: $REPO/$DIR does not exist. CANNOT TELL."; exit 2; }

# ⚠️ POSITIVE CONTROL BEFORE BELIEVING ANY ZERO. If `ls-files` cannot see the
# records directory at all, an empty untracked list means the instrument is
# pointed somewhere useless — not that everything is tracked.
TRACKED_COUNT="$(git -C "$REPO" ls-files "$DIR" | wc -l | tr -d ' ')"
if [ "$TRACKED_COUNT" -eq 0 ]; then
  echo "🔴 deploy-records: git tracks NOTHING under $DIR. Refusing to read an"
  echo "   empty untracked list as 'all clear'. CANNOT TELL."
  exit 2
fi

UNTRACKED="$(git -C "$REPO" ls-files --others --exclude-standard "$DIR")"
if [ -n "$UNTRACKED" ]; then
  echo "🔴 deploy-records: UNTRACKED §2.5 record(s) under $DIR —"
  echo "$UNTRACKED" | sed 's/^/     /'
  echo "   A deploy record that is not in git is not a record. Land it (its own"
  echo "   docs PR is fine) before the next deploy, and state any lateness in"
  echo "   the body: a retrospective recovers the EVIDENCE, never the GATE."
  exit 1
fi

echo "🟢 deploy-records: $TRACKED_COUNT tracked under $DIR, 0 untracked."
exit 0
