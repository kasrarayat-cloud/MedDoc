#!/usr/bin/env bash
# ============================================================================
# THE RULED-MUTATION RUNNER — the only door to an irreversible production act.
#   0 = the mutation ran and exited 0   1 = REFUSED (nothing ran)   n = its code
#
#   bash scripts/run-ruled-mutation.sh --declaration <path> [--in <service>] -- <command…>
# ----------------------------------------------------------------------------
# WHY
#
# `deploy-prod.sh` has refused to run without a §2.5 declaration since 2026-08-11.
# Ruled MUTATIONS had no such gate: the order lived in a ruling and in whoever
# was executing. That is survivable while a person types the command and it is
# not survivable now that an unattended loop can.
#
# ⚠️ THE REFERENCE CASE IS WHY THE GATE IS STRICTER HERE THAN FOR A DEPLOY.
# B7 step 3c's backfill wrote **175 irreversible rows at 22:50:16Z**, and its
# declaration's only commit is **22:52:13Z** — 1m57s later. All eight declared
# quantities matched exactly and nothing suggests bad faith. **The record simply
# cannot distinguish an honest declaration from one written once the outcome was
# known** — and that distinction was the entire product §2.5 was buying.
#
# So for a mutation the declaration must be COMMITTED before this runs. The act
# has not happened yet, so its commit timestamp provably precedes the rows.
# Nothing else in the record can carry that proof.
#
# The two reference shapes this generalises:
#   · GATE 0.1's `scripts/execute-gate0-deactivation.sql` — owner-ruled, one-shot
#   · B7 step 3c's `apps/transcribe-md/scripts/backfill-promo-grants.ts`
#
# The child is handed two variables so it can refuse to run outside this door:
#   RULED_MUTATION_DECLARATION  path of the committed declaration
#   RULED_MUTATION_DECL_COMMIT  the commit that carries it
#
# ── `--in <service>` — THE ACT RUNS INSIDE THE CONTAINER (ruling #262) ───────
# ⚠️ WITHOUT IT, EVERY TYPESCRIPT RULED MUTATION RAN ON THE HOST, and a host
# `npx tsx` needs `DATABASE_URL`, which lives in `/opt/meddoc-pro/.env` — a file
# `.claude/settings.json` DENIES READING. So the door existed and the room
# behind it did not, and a session meeting that wall reported a BLOCKER.
#
#     A SESSION THAT CANNOT PERFORM AN ACT HAS TWO INDISTINGUISHABLE
#     EXPLANATIONS — *the system forbids it* and *I have not found the door*.
#
# `deploy-prod.sh` already had the shape and nothing generalised it: it never
# runs a migration on the host, it uses `docker compose run --rm db-migrate`
# (:348) and `docker exec meddoc-pro-postgres-1 psql` (:206), and both rely on
# the CONTAINER's own environment, which compose populates from `.env` without
# any agent ever reading it. `--in` is that move, made available to a ruled act.
#
# ⚠️ THE APP CONTAINER IS NOT THE ANSWER, MEASURED RATHER THAN ASSUMED.
# `meddoc-pro-transcribe-md-1` is the Next.js standalone runner: `node_modules/.bin`
# DOES NOT EXIST, there is no `tsx`, and `/app/apps/transcribe-md` holds only
# `fonts package.json public server.js`. It cannot run a `.ts` file. The WORKER
# can — `Dockerfile.worker` ships `apps/transcribe-md/scripts`, the workspace
# sources and the root manifests, its own CMD is `npx tsx src/worker.ts`, and it
# carries `env_file: .env`. So the ruling's "inside the app container" resolves,
# on this stack, to `--in transcribe-md-worker`.
#
# ── WHY THIS RE-IMPLEMENTS A GUARD RATHER THAN MERELY BEING CAREFUL ──────────
# `scripts/dc.sh` REFUSES `exec` against the production compose file, and it
# says why: *a deny matches the AGENT, not the SCRIPT, so a wrapper that
# bypasses a guard must RE-IMPLEMENT it.* This script reaches production with a
# raw `docker exec`, so it owes a guard of its own — and it is a stronger one
# than the shell dc.sh refuses:
#
#   1 · the declaration is TRACKED, UNMODIFIED and COMMITTED (already true);
#   2 · the service resolves to EXACTLY ONE running container;
#   3 · ⚠️ THE CONTAINER'S IMAGE REVISION EQUALS THIS TREE'S HEAD.
#
# ⚠️ (3) IS THE ONE THAT IS NOT OBVIOUS, AND IT IS THE POINT OF THE MODE.
# A container carries the repository AS OF ITS BUILD. Run a script `--in` a
# container built at an older commit and **the program that runs is not the
# program the declaration's author read** — while every timestamp, every guard
# and every printed count looks correct. That is the deploy hazard *"a
# declaration naming the wrong commit is worse than no declaration, because it
# looks like evidence"*, one layer down and irreversible.
#
# ⚠️ AND `docker exec` DOES NOT FORWARD THE HOST ENVIRONMENT. The two provenance
# variables are therefore passed EXPLICITLY with `-e`. Exporting them and hoping
# would leave a child that refuses to run outside this door unable to see that
# it is inside it.
# ============================================================================
set -uo pipefail

USAGE="usage: bash scripts/run-ruled-mutation.sh --declaration <path> [--in <service>] -- <command…>"
DECL=""; IN_SERVICE=""; CMD=()
while [ $# -gt 0 ]; do
  case "$1" in
    --declaration) DECL="${2:-}"; shift 2 ;;
    --declaration=*) DECL="${1#*=}"; shift ;;
    --in) IN_SERVICE="${2:-}"; shift 2 ;;
    --in=*) IN_SERVICE="${1#*=}"; shift ;;
    --) shift; CMD=("$@"); break ;;
    *) echo "$USAGE"; exit 2 ;;
  esac
done
[ -z "$DECL" ] && { echo "🔴 run-ruled-mutation: --declaration is required."; exit 2; }
[ "${#CMD[@]}" -eq 0 ] && { echo "🔴 run-ruled-mutation: no command given after --."; exit 2; }

cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || { echo "🔴 not in a git work tree"; exit 2; }
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" 2>/dev/null && pwd)/declaration.sh"
[ -r "$LIB" ] || { echo "🔴 run-ruled-mutation: $LIB missing or unreadable. Refusing."; exit 1; }
# shellcheck source=lib/declaration.sh
. "$LIB"

declaration_gate "$DECL" strict "ruled mutation" || exit 1

DECL_COMMIT=$(git log -1 --format=%H -- "$DECL" 2>/dev/null)
DECL_DATE=$(git log -1 --format=%cI -- "$DECL" 2>/dev/null)

# ⚠️ THIS TIMESTAMP IS THE OTHER HALF OF THE PROOF. The declaration's commit time
# and this line bracket the act, in the transcript, in the same units the rows
# carry. A later forensic check compares them without needing anybody's memory.
echo "═══════════════════════════════════════════════════════════════════"
echo "RULED MUTATION — ABOUT TO EXECUTE"
echo "  declaration : $DECL"
echo "  committed   : ${DECL_COMMIT:0:12} at $DECL_DATE"
echo "  command     : ${CMD[*]}"
echo "  running in  : ${IN_SERVICE:-the HOST shell}"
echo "  starting at : $(date -u +%Y-%m-%dT%H:%M:%SZ)   ← must be AFTER the commit above"
echo "═══════════════════════════════════════════════════════════════════"

export RULED_MUTATION_DECLARATION="$DECL"
export RULED_MUTATION_DECL_COMMIT="$DECL_COMMIT"

if [ -z "$IN_SERVICE" ]; then
  "${CMD[@]}"
  rc=$?
else
  # ══ --in <service>: THE ACT RUNS INSIDE THE CONTAINER (ruling #262) ═══════
  SHARED_TREE="/opt/meddoc-pro"
  COMPOSE_FILE="$SHARED_TREE/docker-compose.yml"
  REVLIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" 2>/dev/null && pwd)/container-revision.sh"

  # ⚠️ FAIL-CLOSED ON A MISSING LIBRARY. A gate that cannot run is not a gate
  # that passed — the posture deploy-prod.sh takes for check-deploy-records.
  [ -r "$REVLIB" ] || {
    echo "🔴 run-ruled-mutation: $REVLIB missing or unreadable. REFUSING."
    echo "   Nothing has been run."; exit 1; }
  # ⚠️ `declaration.sh` IS ALREADY SOURCED ABOVE, AND THAT IS NOT INCIDENTAL:
  # the carry-forward test below reads its `DECLARATION_NONRUNTIME_RE`. The
  # library refuses loudly if it is not in scope rather than measuring nothing.
  # shellcheck source=lib/container-revision.sh
  . "$REVLIB"

  [ -r "$COMPOSE_FILE" ] || {
    echo "🔴 run-ruled-mutation: $COMPOSE_FILE missing. REFUSING — cannot tell."
    echo "   Nothing has been run."; exit 1; }

  command -v docker >/dev/null 2>&1 || {
    echo "🔴 run-ruled-mutation: no docker on PATH. REFUSING — cannot tell."
    echo "   Nothing has been run."; exit 1; }

  echo "═══════════════════════════════════════════════════════════════════"
  echo "IN-CONTAINER MODE — resolving '$IN_SERVICE' (ruling #262)"

  # ⚠️ RUN COMPOSE FROM THE SHARED TREE. `docker-compose.yml` carries RELATIVE
  # bind mounts, so resolving it from a worktree points them at that directory —
  # the hazard `scripts/dc.sh` exists for. `ps` creates nothing, but the habit is
  # the guard and an explicit -f costs one flag.
  CID="$(cd "$SHARED_TREE" && container_id_for_service "$COMPOSE_FILE" "$IN_SERVICE")"
  if [ -z "$CID" ]; then
    echo "🔴 REFUSING — '$IN_SERVICE' did not resolve to EXACTLY ONE running container."
    echo "   Zero means the service is not up; more than one means which container"
    echo "   would run the act is a guess, and a guessed target for an"
    echo "   irreversible act is worse than no target."
    echo "   Nothing has been run."; exit 1
  fi

  LABEL="$(container_revision_of "$CID")"
  HEAD_SHA="$(git rev-parse --verify HEAD 2>/dev/null || true)"
  VERDICT="$(container_revision_verdict "$LABEL" "$HEAD_SHA")"
  V_MODE="${VERDICT%%|*}"; V_WHY="${VERDICT#*|}"

  echo "  container   : ${CID:0:12}"
  echo "  its revision: ${LABEL:-<none>}"
  echo "  this tree   : ${HEAD_SHA:-<unreadable>}"
  echo "  verdict     : $V_MODE — $V_WHY"

  if [ "$V_MODE" != "ok" ]; then
    echo
    echo "🔴 REFUSING — the container is not running this tree."
    echo
    echo "   A container carries the repository AS OF ITS BUILD. Running the act"
    echo "   in there would execute a DIFFERENT PROGRAM from the one the"
    echo "   declaration's author read — while every guard, count and timestamp"
    echo "   in the transcript still looked correct."
    echo
    echo "   This is the deploy hazard one layer down, and irreversible:"
    echo "   a declaration naming the wrong commit is worse than no declaration,"
    echo "   because it looks like evidence."
    echo
    echo "   Land the change and deploy it, then re-run. Nothing has been run."
    exit 1
  fi
  echo "═══════════════════════════════════════════════════════════════════"

  # ⚠️ `-e` EXPLICITLY: `docker exec` DOES NOT FORWARD THE HOST ENVIRONMENT.
  # A child written to refuse outside this door would otherwise be unable to see
  # that it is inside it, and would refuse a legitimate act.
  docker exec \
    -e RULED_MUTATION_DECLARATION="$DECL" \
    -e RULED_MUTATION_DECL_COMMIT="$DECL_COMMIT" \
    -e RULED_MUTATION_IN_CONTAINER="$IN_SERVICE" \
    "$CID" "${CMD[@]}"
  rc=$?
fi

echo "═══════════════════════════════════════════════════════════════════"
echo "RULED MUTATION — FINISHED at $(date -u +%Y-%m-%dT%H:%M:%SZ), exit $rc"
echo "  declaration : $DECL @ ${DECL_COMMIT:0:12}"
# ⚠️ EXIT 2 IS "REFUSED BEFORE ACTING", AND CONFLATING IT WITH A PARTIAL FAILURE
# IS A REAL COST. The warning below tells an operator that an irreversible act
# may have landed halfway and must be reconciled by hand before anything is
# re-run. Printing it for a child that refused its own ARGUMENTS — having opened
# no connection and written no byte — sends somebody to audit a database that
# was never touched, and it teaches them to discount the warning next time.
#
# The convention this file already documents for ITSELF is `1 = REFUSED
# (nothing ran)`. It is extended to the CHILD: a child may say the same thing
# with 2, which is the conventional "usage / bad arguments" code and is what
# `transfer-certification-to-active.ts` uses for a parse refusal.
#
# ⚠️ FAIL-CLOSED ON EVERYTHING ELSE. Only 0 and 2 are treated as "nothing
# landed". Every other non-zero keeps the full warning, because a child that
# died at an unknown point is exactly the case the warning exists for.
if [ "$rc" -eq 2 ]; then
  echo "  ℹ️  EXIT 2 — the command REFUSED before acting (usage / bad arguments)."
  echo "     Nothing was opened and nothing was written. Fix the invocation and"
  echo "     re-run; there is no partial state to reconcile."
elif [ "$rc" -ne 0 ]; then
  echo "  ⚠️ NON-ZERO EXIT. Do not re-run until you know what landed — an"
  echo "     irreversible act that failed partway is not the same as one that"
  echo "     did not run. Verify against the declaration before deciding."
fi
echo "  NEXT: judge the result against the declaration above, every row of it."
echo "═══════════════════════════════════════════════════════════════════"
exit $rc
