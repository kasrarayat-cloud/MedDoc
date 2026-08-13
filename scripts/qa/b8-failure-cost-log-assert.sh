#!/usr/bin/env bash
# ============================================================================
# B8 step 3 — convenience wrapper: the three reads, then the asserter
# ----------------------------------------------------------------------------
# ⚠️ THIS FILE CONTAINS NO ASSERTIONS. Every check lives in
# `b8-failure-cost-log-assert.py`, deliberately and in one place — a second copy
# of that logic would drift from the first the day either is fixed, which is the
# reasoning `scripts/lib/inflight.sh` is shared between the push and merge
# guards for.
#
# All this does is the two DOCKER reads the Python file must not do (see its
# header: it is pure, so it never shells out) and then hand it the results.
#
# ⚠️ THE UNATTENDED FOUNDATION LOOP CANNOT RUN THIS, AND THAT IS NOT A BUG TO
# ROUTE AROUND. `bash scripts/<name>.sh` is granted per-script, one line each,
# and a `scripts/` wildcard is refused on purpose — a session that may write a
# script and then run it has no allowlist at all. So the loop runs the three
# commands below individually, each independently granted and each visible in
# its transcript. This wrapper is for a SUPERVISED session, where it saves the
# dance.
#
# Usage, from the repo root, after the in-container harness has run AND every
# BullMQ attempt has completed:
#
#   bash scripts/qa/b8-failure-cost-log-assert.sh
#
# ⚠️ WAIT FOR THE ATTEMPTS FIRST. A `transient` visit only lands FAILED on the
# final attempt, and a `permanent` one re-enters the failure branch on every
# attempt (B8 step 3c). Reading the stream early sees fewer lines than were
# emitted and passes an exactly-once assertion for the wrong reason. The tell
# that all three ran is TWO `fail-fast` lines — that message is logged only on
# NON-final attempts.
#
# Exit: whatever the asserter returns — 0 held · 1 FINDING · 2 cannot tell
# ============================================================================
set -uo pipefail

CTR="${B8_QA_WORKER_CTR:-meddoc-qa-transcribe-md-worker-1}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
MANIFEST="${REPO_ROOT}/.b8-s3qa-manifest.tsv"
LOGDUMP="${REPO_ROOT}/.b8-s3qa-worker.log"

# ⚠️ THE SCRATCH NAMES MATCH `.b[0-9]*-*`, WHICH `.gitignore` ALREADY COVERS.
# The dash after the digit is load-bearing: `.b8probe.ts` does NOT match, stays
# untracked, and on 2026-08-12 three such files made the loop's own launch guard
# refuse to relight. Do not "tidy" these names.

if ! docker exec "$CTR" cat /tmp/b8-failure-cost-manifest.tsv > "$MANIFEST" 2>/dev/null; then
  echo "?  no manifest in ${CTR} — run the in-container harness first" >&2
  exit 2
fi
if ! docker logs "$CTR" > "$LOGDUMP" 2>&1; then
  echo "?  could not read docker logs for ${CTR}" >&2
  exit 2
fi

python3 "${REPO_ROOT}/scripts/qa/b8-failure-cost-log-assert.py" "$MANIFEST" "$LOGDUMP"
