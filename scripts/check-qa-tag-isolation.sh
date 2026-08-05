#!/usr/bin/env bash
# ============================================================================
# READ-ONLY. Asserts the QA stack never runs an image that production's `:latest`
# tag points at.
#
# WHY THIS EXISTS. DEPLOYMENT_RUNBOOK says "never rebuild prod's `:latest` to
# stage something — tag a separate image and point a compose override at it."
# Until 2026-08-05 `docker-compose.qa.yml` pinned `meddoc-pro-transcribe-md:latest`
# — the SAME tag production builds to, on the SAME daemon — so the only way to
# get the QA stack onto a candidate build was to retag `:latest`, which silently
# re-points the tag prod's compose would deploy. The rule was stated as a
# prohibition and the default path violated it.
#
# A rule nobody can follow is a rule that gets broken, and it was: a ~1h window
# on 2026-08-05 where a prod `docker compose up -d` would have shipped an
# untested image. Nothing ran and the rollback tags were verified intact, but the
# window was real. This check turns the prohibition into something a machine
# enforces.
#
# ⚠️ IT COMPARES DIGESTS, NOT TAG STRINGS. A QA container started before a retag
# holds an image ID, not a tag, so "the compose file says :qa" proves nothing
# about what is actually running. The question is only answerable from the
# running container's image ID versus what `:latest` resolves to right now.
#
# EXIT: 0 = isolated · 1 = a QA container is running prod's :latest image
#       2 = cannot tell (docker unavailable, or no QA containers up)
# ============================================================================
set -uo pipefail

command -v docker >/dev/null 2>&1 || { echo "[qa-tag] docker unavailable"; exit 2; }

QA_CONTAINERS=$(docker ps --filter "name=meddoc-qa" --format '{{.Names}}' 2>/dev/null)
if [ -z "$QA_CONTAINERS" ]; then
  echo "[qa-tag] no meddoc-qa containers running — nothing to check"
  exit 2
fi

FAIL=0
CHECKED=0
for base in meddoc-pro-transcribe-md meddoc-pro-transcribe-md-worker meddoc-pro-db-migrate meddoc-pro-marketing; do
  prod_id=$(docker image inspect "${base}:latest" --format '{{.Id}}' 2>/dev/null) || continue
  [ -z "$prod_id" ] && continue
  for c in $QA_CONTAINERS; do
    run_id=$(docker inspect "$c" --format '{{.Image}}' 2>/dev/null) || continue
    CHECKED=$((CHECKED + 1))
    if [ "$run_id" = "$prod_id" ]; then
      echo "[qa-tag] ✗ $c is running ${base}:latest (${prod_id:7:12}) — PRODUCTION'S IMAGE"
      FAIL=1
    fi
  done
done

# ⚠️ POSITIVE CONTROL. Without it a zero here is indistinguishable from a loop
# that compared nothing — which is exactly what happens if the tags are absent
# on a fresh daemon.
if [ "$CHECKED" -eq 0 ]; then
  echo "[qa-tag] compared 0 pairs — no prod :latest tags on this daemon, so the"
  echo "[qa-tag] result would be a free pass. Reporting 'cannot tell' instead."
  exit 2
fi

if [ "$FAIL" -eq 0 ]; then
  echo "[qa-tag] ✓ isolated — $CHECKED container/tag pairs compared by DIGEST, none shared"
  exit 0
fi
echo "[qa-tag] a QA container is running production's image. Rebuild QA with its"
echo "[qa-tag] own tag: docker compose -f docker-compose.qa.yml build"
exit 1
