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
# Every docker call goes through `$DOCKER`, so the gate can inject a fake and
# exercise both halves — the refusals AND the happy path — without touching a
# real image.
#
#   PROOF: apps/transcribe-md/src/lib/__tests__/gate-f9-deploy-cuts-its-rollback-tag.test.ts
#
# ⚠️ IT IS A VITEST GATE, NOT A SHELL HARNESS, DELIBERATELY. The house style for
# a script proof is `scripts/test-verify-post-reboot.sh` — hand-run, and a proof
# nobody re-runs is a proof that decays. This one runs in `CI` on every PR.
#
# ⚠️ AND THE GATE RUNS IT UNDER `set -euo pipefail`, BECAUSE THAT IS THE CALLER'S
# UNIVERSE. A bare `bash -c` proved every refusal message in a shell mode
# production does not use, and hid a defect that would have killed the deploy on
# the fallback path. See the `|| true` notes below.
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
    #
    # ⚠️ `|| true` IS LOAD-BEARING AND ITS ABSENCE WAS A SHIPPING DEFECT.
    # `deploy-prod.sh` runs `set -euo pipefail`. With **pipefail**, a `grep` that
    # matches nothing makes the whole pipeline exit 1 — so `slug=$(grep | sed)`
    # is a failing command substitution and `set -e` kills the deploy ON THE
    # SPOT. That is the FALLBACK path: every declaration written before F9 has
    # no `rollback-slug:` line, so the deploy would have died at STEP 0b in the
    # COMMON case, with no message.
    #
    # ⚠️ Invisible until the gate was made to run with production's shell
    # options. Nothing else could have found it: the function is correct, the
    # logic is correct, and it is fatal only in the caller's universe.
    slug=$(grep -m1 -E '^[[:space:]]*rollback-slug:[[:space:]]*[^[:space:]]' "$decl" 2>/dev/null \
             | sed -E 's/^[[:space:]]*rollback-slug:[[:space:]]*//; s/[[:space:]]+$//' || true)
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

  # ⚠️ EVERY CAPTURE BELOW CARRIES `|| true`, AND THAT IS NOT DEFENSIVE NOISE.
  # This file is SOURCED INTO `deploy-prod.sh`, which runs `set -euo pipefail`.
  # Under `set -e` a failing `var=$(cmd)` is a simple command with non-zero
  # status and the shell EXITS THERE — so every carefully-worded refusal below
  # would never print, and the operator would get a bare non-zero from a deploy
  # that said nothing about why. Measured, not assumed:
  #
  #   set -euo pipefail; f(){ local v; v=$(docker inspect … no-such-container);
  #                           echo REACHED; }; f
  #   -> exit 1, "REACHED" never printed
  #
  # ⚠️ AND THIS WAS FOUND BY REFUTING THE GATE, NOT BY THE GATE. The gate drives
  # this library through `bash -c` — a shell WITHOUT `set -e` — so it proved
  # every refusal message in a universe production does not run. The gate now
  # sets the same options; this belt is kept so the behaviour is identical in
  # either mode rather than depending on the caller's shell settings.
  for svc in "$@"; do
    cid=$($DOCKER compose ps -q "$svc" 2>/dev/null | head -2 || true)
    # ⚠️ AMBIGUITY IS A REFUSAL, NOT A `head -1`. A scaled service returns more
    # than one container, and silently tagging whichever sorted first is an
    # answer about a set whose boundary was never established — with a rollback
    # target as the prize. This stack runs one of each; the guard is for the day
    # it does not.
    if [ "$(printf '%s' "$cid" | grep -c . || true)" -gt 1 ]; then
      echo "🔴 REFUSING — service '$svc' has MORE THAN ONE running container."
      echo "   Which one is 'the outgoing image' is then a guess, and a guessed"
      echo "   rollback target is worse than a missing one. Tag by hand."
      refused=1; continue
    fi
    if [ -z "$cid" ]; then
      echo "🔴 REFUSING — service '$svc' has no running container."
      echo "   The outgoing image can only be read from what is actually running."
      echo "   ':latest' is NOT a substitute: it is the thing about to be replaced,"
      echo "   and a build that never recreated leaves it newer than production."
      refused=1; continue
    fi

    img=$($DOCKER inspect --format '{{.Image}}' "$cid" 2>/dev/null || true)
    if ! printf '%s' "$img" | grep -qE '^sha256:[0-9a-f]{64}$'; then
      echo "🔴 REFUSING — '$svc' ($cid) did not yield a usable image id: '${img:-<empty>}'"
      refused=1; continue
    fi

    cfg=$($DOCKER inspect --format '{{.Config.Image}}' "$cid" 2>/dev/null || true)
    repo=$(_rollback_repo_of "$cfg")
    # ⚠️ A DIGEST REFERENCE (`repo@sha256:…`) IS NAMED, NOT LEFT TO FAIL LATER.
    # Stripping at the last colon turns it into `repo@sha256`, which `docker tag`
    # rejects — so it already failed closed, but with "docker tag failed" as the
    # only clue. A guard that fails for the right reason with the wrong message
    # costs the next reader an hour.
    if printf '%s' "$cfg" | grep -q '@'; then
      echo "🔴 REFUSING — '$svc' was created from a DIGEST reference ('$cfg')."
      echo "   There is no mutable tag to derive a rollback name from. Tag by hand."
      refused=1; continue
    fi
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
    # shellcheck disable=SC2015
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
