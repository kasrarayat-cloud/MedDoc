#!/usr/bin/env bash
# ============================================================================
# WHAT COMMIT IS THIS CONTAINER RUNNING? — read from the container, never guessed.
# ----------------------------------------------------------------------------
# One implementation, two callers, because a second copy drifts from the first
# the day either is fixed — the same reason `declaration.sh` and `inflight.sh`
# are shared files:
#
#   · `run-ruled-mutation.sh --in <service>` — the act must run the program the
#     declaration describes, and a container carries the tree AS OF ITS BUILD.
#   · the §2.5 deploy range (ruling #265) — `production..HEAD` needs to know
#     what production IS, and `origin/main` answers a different question.
#
# ── THE SOURCE, AND WHY IT IS THIS ONE ──────────────────────────────────────
# `deploy-prod.sh:138-139` exports `GIT_REVISION=$(git rev-parse HEAD)`;
# `docker-compose.yml:381,541` pass it as a build arg; the Dockerfiles stamp it
# as `org.opencontainers.image.revision` (`Dockerfile:212-213`,
# `Dockerfile.worker:83-84`), defaulting to the literal string `unknown`.
#
# So the label on a RUNNING container is the full 40-character sha of the tree
# that was deployed, and the running container cannot lie about what is running.
# That is the same argument `rollback-tag.sh` makes for reading the container
# rather than `:latest`, and it is why this does NOT parse a rollback TAG NAME:
#
# ⚠️ A ROLLBACK TAG'S SLUG IS NOT RELIABLY A SHA. `rollback_tag_slug` accepts any
# `^[a-z0-9][a-z0-9-]{0,31}$` from an optional `rollback-slug:` line, and live
# tags include `pre-f5-20260816`, `pre-rc1-20260813` and `pre-selfhostfonts-20260811`.
# An implementation that parsed the name would resolve a WORD as a commit, or
# silently compute a seven-week range. The label has no such ambiguity.
#
# ⚠️ AND IT IS FAIL-CLOSED ON CANNOT-TELL, EVERYWHERE. No docker, no container,
# more than one container, an `unknown` label, a label that is not 40 hex, or a
# sha this repository does not contain — every one of them REFUSES. A broken
# instrument and a matching revision must never produce the same answer.
#
#   PROOF: apps/transcribe-md/src/lib/__tests__/gate-container-revision.test.ts
# ============================================================================

: "${DOCKER:=docker}"

# ── the PURE half, so an arm can drive it with injected values ──────────────
# ⚠️ SPLIT FOR THE SAME REASON `declaration_strictness_for_migrations` IS SPLIT:
# the GATHERING is I/O (a docker inspect) and the DECISION is string comparison.
# Kept together they are untestable without a running container, and the
# decision is the half that can be wrong in a way nobody notices.
#
#   container_revision_verdict <label> <head_sha>
#     echoes:  ok|<reason>   or   refuse|<reason>
container_revision_verdict() {
  local label="${1-}" head="${2-}"

  if [ -z "$label" ]; then
    echo "refuse|the image carries no org.opencontainers.image.revision label at all. This container was not built by a deploy that stamped one, so nothing here can say which commit it is running."
    return 0
  fi
  if [ "$label" = "unknown" ]; then
    echo "refuse|the image's revision label is the literal 'unknown' — the Dockerfile's ARG default. It was built without GIT_REVISION, so its provenance was never recorded and cannot be recovered now."
    return 0
  fi
  case "$label" in
    *[!0-9a-fA-F]*|"")
      echo "refuse|the revision label '${label}' is not hexadecimal. Something other than a commit sha was stamped into this image."
      return 0
      ;;
  esac
  if [ "${#label}" -ne 40 ]; then
    # ⚠️ FULL, NOT "LONG ENOUGH". An abbreviation is ambiguous by construction and
    # this library never pads, completes or guesses at an identifier — the same
    # rule `declaration_resolve` applies to a declaration's filename.
    echo "refuse|the revision label '${label}' is ${#label} hex characters, not 40. This library never completes an abbreviation."
    return 0
  fi
  if [ -z "$head" ]; then
    echo "refuse|no commit was given to compare the label against."
    return 0
  fi
  if [ "$label" != "$head" ]; then
    echo "refuse|the running container is at ${label:0:12} and this tree is at ${head:0:12}. They are DIFFERENT PROGRAMS: a container carries the tree as of its BUILD, so the code that would run is not the code that was read."
    return 0
  fi
  echo "ok|the running container's revision ${label:0:12} equals this tree's HEAD"
}

# ── the I/O half ────────────────────────────────────────────────────────────
#   container_id_for_service <compose-file> <service>   -> prints one id, or empty
#
# ⚠️ AMBIGUITY IS A REFUSAL, NOT A `head -1`. A scaled service returns more than
# one container, and silently taking whichever sorted first is an answer about a
# set whose boundary was never established — `rollback-tag.sh` refuses the same
# shape for the same reason, with a rollback target as the prize.
container_id_for_service() {
  local compose="${1:?}" svc="${2:?}" ids n
  ids=$($DOCKER compose -f "$compose" ps -q "$svc" 2>/dev/null || true)
  n=$(printf '%s' "$ids" | grep -c . || true)
  if [ "$n" -ne 1 ]; then
    echo "" ; return 0
  fi
  printf '%s' "$ids" | head -1
}

#   container_revision_of <container-id>   -> prints the label, or empty
container_revision_of() {
  local cid="${1:?}"
  $DOCKER inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' \
    "$cid" 2>/dev/null || true
}
