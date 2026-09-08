#!/usr/bin/env bash
# ============================================================================
# ARM THE LENS SANDBOX — plant a commit, a push and a `gh pr create`, and prove
# every one of them FAILS.
# ----------------------------------------------------------------------------
# ⚠️ A GUARD NOBODY FIRED IS A GUESS. The pass that made this necessary was
# governed by a prompt that read exactly like a control and stopped nothing, so
# this file exists to make the same mistake impossible twice: the sandbox is not
# "configured", it is DEMONSTRATED.
#
# ⚠️ AND THE FOURTH ARM IS THE ONE THAT PROTECTS EVERYONE ELSE. Scoping
# `remote.origin.pushurl` wrongly would disable pushes for the SHARED tree and
# every other worktree, silently, and the symptom would be somebody else's push
# failing an hour later. So the shared repo's own config is read back and
# asserted unchanged.
#
# Exit 0 = all arms refused as required. Exit 1 = a breach got through.
# ============================================================================
set -uo pipefail
# ⚠️ THE ROOT IS DERIVED, NOT HARDCODED — AND THIS SESSION FIXED THE SAME BUG
# ONE HOUR EARLIER IN #1009. A literal `/opt/meddoc-pro` is correct on this VPS
# and does not exist on the CI runner or in any worktree, so a check written
# that way passes locally and is meaningless (or red) everywhere else.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED="$(git -C "$HERE" rev-parse --show-toplevel)"
NAME="lens-armtest-$$"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

fail=0
say() { printf '%s\n' "$*"; }

# Record the shared config BEFORE, so the comparison is against a measurement
# rather than an expectation.
before_push="$(git -C "$SHARED" config --get remote.origin.pushurl || echo UNSET)"
before_hooks="$(git -C "$SHARED" config --get core.hooksPath || echo UNSET)"

DIR="$(bash "$SHARED/scripts/make-lens-sandbox.sh" "$NAME")" || { say "🔴 could not build the sandbox"; exit 1; }
say "sandbox: $DIR"
say ""

# shellcheck disable=SC1091
. "$DIR/.lens-env.sh"

# ── ARM 0 · POSITIVE CONTROL ────────────────────────────────────────────────
# ⚠️ WITHOUT THIS, EVERY ARM BELOW PASSES IN A TREE WHERE GIT IS SIMPLY BROKEN.
# A read must work, or "the write failed" means nothing.
if git -C "$DIR" log --oneline -1 >/dev/null 2>&1; then
  say "🟢 ARM 0  positive control — git READS fine in the sandbox"
else
  say "🔴 ARM 0  git cannot even read here; every refusal below is meaningless"; fail=1
fi

# ── ARM 1 · a planted COMMIT must fail ──────────────────────────────────────
echo "a lens wrote this" > "$DIR/LENS-BREACH.txt"
git -C "$DIR" add LENS-BREACH.txt >/dev/null 2>&1
if git -C "$DIR" commit -m "breach: a lens committing" > "$OUT/commit" 2>&1; then
  say "🔴 ARM 1  THE COMMIT SUCCEEDED — the pre-commit hook did not fire"; fail=1
else
  say "🟢 ARM 1  commit refused: $(head -1 "$OUT/commit")"
fi

# ── ARM 2 · a planted PUSH must fail ────────────────────────────────────────
# Detached HEAD means there is no branch; push an explicit refspec so the test
# is about the GUARD and not about git having nothing to do.
# ⚠️ AND IT MUST BE REFUSED **BY THE PUSHURL**, NOT BY ANYTHING ELSE.
# Found by mutation: with both guards removed this arm still passed, on
# `could not read Username for 'https://github.com'` — the absence of
# credentials, which is ARM 3's job. Two refusals that read identically in a
# report and mean completely different things; this house has paid for that
# confusion before. So the arm matches the pushurl's OWN signature, and a
# refusal for any other reason is reported as a FAILURE of this arm.
if git -C "$DIR" push origin HEAD:refs/heads/lens-breach > "$OUT/push" 2>&1; then
  say "🔴 ARM 2  THE PUSH SUCCEEDED — pushurl and pre-push both failed"; fail=1
elif grep -qiE "'/dev/null' does not appear to be a git repository|REFUSED — this is a LENS SANDBOX" "$OUT/push"; then
  say "🟢 ARM 2  push refused BY THE SANDBOX: $(grep -m1 -iE "/dev/null|REFUSED" "$OUT/push")"
else
  say "🔴 ARM 2  the push failed, but NOT by the sandbox's guards — this arm proves nothing:"
  say "         $(head -1 "$OUT/push")"; fail=1
fi

# ── ARM 3 · `gh` must be UNAUTHENTICATED ────────────────────────────────────
if gh auth status > "$OUT/gh" 2>&1; then
  say "🔴 ARM 3  gh IS AUTHENTICATED in the lens environment"; fail=1
else
  say "🟢 ARM 3  gh unauthenticated: $(grep -m1 -iE 'not logged|no accounts|authenticat' "$OUT/gh" || head -1 "$OUT/gh")"
fi

# ── ARM 4 · `gh pr create` must fail ────────────────────────────────────────
if (cd "$DIR" && gh pr create --title "breach" --body "breach" --head lens-breach) > "$OUT/pr" 2>&1; then
  say "🔴 ARM 4  gh pr create SUCCEEDED — a lens opened a pull request"; fail=1
else
  say "🟢 ARM 4  gh pr create refused: $(grep -m1 -iE 'auth|token|not logged|fatal|error|no git remote' "$OUT/pr" || head -1 "$OUT/pr")"
fi

# ── ARM 5 · THE SHARED REPO IS UNTOUCHED ────────────────────────────────────
after_push="$(git -C "$SHARED" config --get remote.origin.pushurl || echo UNSET)"
after_hooks="$(git -C "$SHARED" config --get core.hooksPath || echo UNSET)"
if [ "$before_push" = "$after_push" ] && [ "$before_hooks" = "$after_hooks" ]; then
  say "🟢 ARM 5  shared repo untouched — pushurl [$after_push] hooksPath [$after_hooks]"
else
  say "🔴 ARM 5  THE SANDBOX LEAKED INTO THE SHARED CONFIG"
  say "         pushurl  $before_push -> $after_push"
  say "         hooksPath $before_hooks -> $after_hooks"; fail=1
fi

# ── ARM 6 · THE SANDBOX MEASURES ITSELF, NOT THE SHARED TREE ────────────────
#
# ⚠️ THIS ARM IS NOT ABOUT TESTS RUNNING. It is about WHICH TREE a green
# describes. A worktree with a raw `node_modules` symlink resolves `@meddoc/*`
# to the SHARED tree, so a lens can run a suite, watch it pass, and have proved
# something about code its sandbox does not contain — while every guard above
# this line is still 🟢. The sandbox was sealed and pointed at the wrong
# repository.
#
# Observed 2026-09-07: a round-eight lens reported ~24 files failing with
# `Failed to resolve import "react/jsx-dev-runtime"` and `@meddoc/auth resolves
# to /opt/meddoc-pro/packages/auth/src/index.ts, outside this worktree`. It
# caught that itself and discarded every claim resting on those files — but a
# lens that has to notice its own harness is broken is a lens spending its
# budget on the harness, and the QUIET half of that failure (a green about the
# wrong tree) produces no error message at all.
#
# The POSITIVE CONTROL is the first clause: the package must exist in the SHARED
# tree too. Without it this arm passes in a checkout that has no workspace
# packages at all — the vacuity this house keeps finding one input over.
if [ ! -d "$SHARED/packages/auth" ]; then
  say "🔴 ARM 6  no packages/auth in the shared tree — this arm cannot mean anything here"; fail=1
else
  resolved="$(readlink -f "$DIR/node_modules/@meddoc/auth" 2>/dev/null || echo MISSING)"
  case "$resolved" in
    "$DIR"/*)
      say "🟢 ARM 6  @meddoc/auth resolves INSIDE the sandbox: $resolved" ;;
    MISSING)
      say "🔴 ARM 6  @meddoc/auth does not resolve at all — a suite run here proves nothing"; fail=1 ;;
    *)
      say "🔴 ARM 6  @meddoc/auth resolves OUTSIDE the sandbox: $resolved"
      say "         a green in this sandbox would be a green about ANOTHER TREE'S CODE"; fail=1 ;;
  esac
fi

bash "$SHARED/scripts/reap-lens-sandbox.sh" "$DIR" >/dev/null 2>&1 || say "⚠️  could not reap $DIR"

say ""
if [ "$fail" -eq 0 ]; then say "🟢 LENS SANDBOX ARMED — every planted write was refused."; exit 0; fi
say "🔴 LENS SANDBOX IS NOT SAFE — do not run a pass until this is 🟢."; exit 1
