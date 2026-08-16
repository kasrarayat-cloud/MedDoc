#!/usr/bin/env bash
# ============================================================================
# THE ROLLBACK TAG — cut by the deploy itself, from the RUNNING container.
# ----------------------------------------------------------------------------
# F9. `docs/DEPLOYMENT_RUNBOOK.md` §3.1 has said since 2026-08-02 that tagging
# the outgoing images is a MANUAL pre-step, and that forgetting it leaves
# nothing to roll back to. It was forgotten twice anyway on 2026-08-16 —
# F3's deploy at 04:02Z and F4's at 11:35Z — and the second time by a session
# that then asserted in its own §2.5 declaration that the tags HAD been cut.
# Both outgoing images were recovered by hand from dangling images. The window
# in between, during which a rollback would have required a REBUILD, is the
# cost that was actually paid.
#
#   A PRE-STEP THAT LIVES ONLY IN PROSE IS A PRE-STEP THAT GETS SKIPPED.
#
# Same argument that turned the in-flight-runs rule into `scripts/hooks/pre-push`
# and `scripts/merge-pr.sh`, and the §2.5 rule into `scripts/lib/declaration.sh`.
#
# ── WHY THE RUNNING CONTAINER AND NOT `:latest` ─────────────────────────────
# `:latest` is the thing the deploy is about to REPLACE, and it is not reliably
# what production is serving. A previous deploy that built successfully and then
# failed to recreate leaves `:latest` NEWER than the running container — so a tag
# cut from `:latest` would name an image that was never in production, and the
# rollback target would be the very build you were trying to escape.
#
# The running container cannot lie about what is running. It is the only source
# with that property, so it is the only one read here.
#
# ── WHY IT VERIFIES AFTER TAGGING ───────────────────────────────────────────
# `retire-branch.sh` passed 9 of 9 refusal tests and still printed a false green,
# because refusals were never its broken half. So this does not report success on
# `docker tag` exiting 0 — it RE-READS the tag and asserts it resolves to the
# outgoing image id. The green is earned, per deploy, not assumed.
#
# ── WHY A `pre-*` TAG IS NEVER RE-POINTED ───────────────────────────────────
# Standing guardrail: `pre-*` rollback tags are sacred — never deleted, never
# re-pointed. If the tag already exists on a DIFFERENT image, this refuses rather
# than overwriting: silently re-pointing it would destroy the only reference to
# an older production image, which is the exact loss the tag exists to prevent.
# Existing-and-identical is idempotent and fine — a deploy that aborted after
# tagging must be re-runnable.
#
# ── TESTABILITY ─────────────────────────────────────────────────────────────
# Every docker call goes through `$DOCKER`, so `scripts/test-rollback-tag.sh`
# can inject a fake and exercise both halves — the refusals AND the happy path —
# without touching a real image. Proof: `bash scripts/test-rollback-tag.sh`.
#
# Exit convention: 0 = tagged and VERIFIED · 1 = REFUSED, caller must abort.
# ============================================================================

: "${DOCKER:=docker}"

# ── the slug ────────────────────────────────────────────────────────────────
# Historic tags are descriptive (`pre-f5-20260816`, `pre-footer-20260815`), and
# the runbook's table is far more readable for it. But the §2.5 declaration is
# named `<date>-<short-sha>.md` and carries no slug, so requiring one would
# invent a NEW way for a deploy to refuse — a worse trade than a less pretty tag.
#
# So: an OPTIONAL `rollback-slug: <slug>` line in the declaration, falling back
# to the deploy's short sha. `pre-b3a55c72-20260816` reads as "production
# immediately before b3a55c72 was deployed", which is exactly what it is.
#
#   rollback_tag_slug <declaration-path> <fallback>   -> prints the slug
rollback_tag_slug() {
  local decl="${1:-}" fallback="${2:?}" slug=""

  if [ -n "$decl" ] && [ -r "$decl" ]; then
    # First match wins. Anchored at line start so a slug mentioned mid-prose —
    # "…the rollback-slug: convention…" — cannot be picked up as a value.
    slug=$(grep -m1 -E '^[[:space:]]*rollback-slug:[[:space:]]*[^[:space:]]' "$decl" 2>/dev/null \
             | sed -E 's/^[[:space:]]*rollback-slug:[[:space:]]*//; s/[[:space:]]+$//')
  fi

  # A malformed slug falls back rather than refusing: the tag must always be
  # cut, and a bad label is not a reason to leave production without a rollback
  # target. It is reported loudly by the caller.
  if [ -n "$slug" ] && printf '%s' "$slug" | grep -qE '^[a-z0-9][a-z0-9-]{0,31}$'; then
    printf '%s' "$slug"
  else
    [ -n "$slug" ] && echo "   ⚠️  declaration's rollback-slug '$slug' is not [a-z0-9-]{1,32} — using the sha instead." >&2
    printf '%s' "$fallback"
  fi
}

# ── repo from the container, not from a hardcoded list ──────────────────────
# A hand-kept service→repo table is a hand-kept list, and hand-kept lists are
# wrong eventually. `.Config.Image` is the reference the container was created
# from — `meddoc-pro-transcribe-md` (untagged) or `meddoc-pro-gotenberg:fonts`.
# Strip a trailing tag only when the last ':' is after the last '/', so a
# registry port (`registry:5000/foo/bar`) is not mistaken for one.
_rollback_repo_of() {
  local ref="${1:?}" tail
  tail="${ref##*/}"
  if [ "$tail" != "${tail%:*}" ]; then
    printf '%s' "${ref%:*}"
  else
    printf '%s' "$ref"
  fi
}

# ── the act ─────────────────────────────────────────────────────────────────
#   rollback_tag_cut <slug> <YYYYMMDD> <service> [service...]
rollback_tag_cut() {
  local slug="${1:?}" stamp="${2:?}"; shift 2
  local svc cid img cfg repo tag existing verified
  local refused=0 cut=0

  echo "=== ROLLBACK TAG (F9 — cut from the RUNNING containers) ==="

  if [ "$#" -eq 0 ]; then
    # A zero-service run would tag nothing and report success — the emptiness
    # failure this house names on sight. There is no legitimate caller with an
    # empty set, so it is a refusal, not a no-op.
    echo "🔴 REFUSING — no services named. A tag run over an empty set would"
    echo "   report success having protected nothing."
    return 1
  fi

  for svc in "$@"; do
    cid=$($DOCKER compose ps -q "$svc" 2>/dev/null | head -1)
    if [ -z "$cid" ]; then
      echo "🔴 REFUSING — service '$svc' has no running container."
      echo "   The outgoing image can only be read from what is actually running."
      echo "   ':latest' is NOT a substitute: it is the thing about to be replaced,"
      echo "   and a build that never recreated leaves it newer than production."
      refused=1; continue
    fi

    img=$($DOCKER inspect --format '{{.Image}}' "$cid" 2>/dev/null)
    if ! printf '%s' "$img" | grep -qE '^sha256:[0-9a-f]{64}$'; then
      echo "🔴 REFUSING — '$svc' ($cid) did not yield a usable image id: '${img:-<empty>}'"
      refused=1; continue
    fi

    cfg=$($DOCKER inspect --format '{{.Config.Image}}' "$cid" 2>/dev/null)
    repo=$(_rollback_repo_of "$cfg")
    # ⚠️ THE TEST IS ON `cfg`, NOT ON `repo`, AND THE FIRST DRAFT GOT IT WRONG.
    # `_rollback_repo_of "sha256:dddd…"` strips at the last colon and returns the
    # bare word `sha256`, which matches NEITHER `^sha256:` NOR a 64-hex string —
    # so a container created from a bare image id sailed through and the deploy
    # tagged `sha256:pre-<slug>-<date>`. Caught by this gate's own bare-image arm
    # on its first execution. Ask the question of the value that can answer it.
    if [ -z "$repo" ] || [ "$repo" = "sha256" ] \
       || printf '%s' "$cfg" | grep -qE '^(sha256:)?[0-9a-f]{12,}$'; then
      # Created from a bare image id — there is no repository to hang a tag on.
      echo "🔴 REFUSING — '$svc' was created from an untagged image ('${cfg:-<empty>}')."
      echo "   There is no repository name to attach a rollback tag to."
      refused=1; continue
    fi

    tag="${repo}:pre-${slug}-${stamp}"

    # ⚠️ SACRED. Never re-point; existing-and-identical is idempotent.
    existing=$($DOCKER inspect --type=image --format '{{.Id}}' "$tag" 2>/dev/null || true)
    if [ -n "$existing" ] && [ "$existing" != "$img" ]; then
      echo "🔴 REFUSING — $tag already exists and points somewhere ELSE."
      echo "     existing : $existing"
      echo "     outgoing : $img"
      echo "   A 'pre-*' tag is never re-pointed. Overwriting it would destroy the"
      echo "   only reference to an older production image — the exact loss the tag"
      echo "   exists to prevent. Choose a different rollback-slug."
      refused=1; continue
    fi
    if [ -n "$existing" ]; then
      echo "   ↻ $tag already on the outgoing image — idempotent, left alone."
      cut=$((cut + 1)); continue
    fi

    if ! $DOCKER tag "$img" "$tag" 2>&1; then
      echo "🔴 REFUSING — 'docker tag $img $tag' failed."
      refused=1; continue
    fi

    # ⚠️ THE EARNED GREEN. `docker tag` exiting 0 is not evidence the tag
    # resolves — re-read it. This is the happy-path control, run every deploy.
    verified=$($DOCKER inspect --type=image --format '{{.Id}}' "$tag" 2>/dev/null || true)
    if [ "$verified" != "$img" ]; then
      echo "🔴 REFUSING — $tag was created but does NOT resolve to the outgoing image."
      echo "     wanted : $img"
      echo "     got    : ${verified:-<nothing>}"
      refused=1; continue
    fi

    echo "   🟢 $tag  ->  ${img#sha256:}"
    echo "      (verified by re-reading the tag, not by docker tag's exit code)"
    cut=$((cut + 1))

    # Not a refusal — but say it loudly. A ':latest' that differs from what is
    # running means a previous deploy built and did not recreate, and it is the
    # precise case that makes reading the running container load-bearing.
    local latest
    latest=$($DOCKER inspect --type=image --format '{{.Id}}' "${repo}:latest" 2>/dev/null || true)
    if [ -n "$latest" ] && [ "$latest" != "$img" ]; then
      echo "      ⚠️  NOTE: ${repo}:latest is a DIFFERENT image (${latest#sha256:})."
      echo "          Production is not running ':latest'. The tag above is correct;"
      echo "          a previous deploy appears to have built without recreating."
    fi
  done

  if [ "$refused" -ne 0 ]; then
    echo
    echo "🔴 ROLLBACK TAGGING FAILED — the deploy must not proceed."
    echo "   Deploying now would replace production with no way back, which is the"
    echo "   state F9 exists to make impossible. Nothing has been changed."
    return 1
  fi

  # A run that refused nothing and tagged nothing is not a success. Guard the
  # count as well as the errors — the two are not the same claim.
  if [ "$cut" -eq 0 ]; then
    echo "🔴 REFUSING — no tag was cut and nothing reported an error."
    return 1
  fi

  echo "🟢 $cut rollback tag(s) cut and verified against the running images."
  echo
  return 0
}
