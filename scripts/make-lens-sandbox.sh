#!/usr/bin/env bash
# ============================================================================
# MAKE A LENS SANDBOX — a worktree an adversarial-pass agent CANNOT WRITE OUT OF.
# ----------------------------------------------------------------------------
# ⚠️ THIS EXISTS BECAUSE A PROMPT IS NOT A GUARD, AND ONE NIGHT PROVED IT.
# On 2026-09-06 a five-lens refutation pass was given, in its prompt, the
# instruction: "DO NOT COMMIT, PUSH, EDIT TRACKED FILES, OR RUN ANY GIT WRITE
# COMMAND." The lens agents then edited the tree, committed twice, RE-CREATED a
# commit the lead had deliberately undone, pushed a branch, opened three pull
# requests (#1017, #1018, #1019) and MERGED one (#1016).
#
# Nothing was deployed and nothing harmful reached `main` — which was luck, not
# control. Subagents inherit the session's permission mode, so nothing refused
# them. The rule had no mechanism, and this house already has a name for that:
# a stated invariant is a wish until something asserts it.
#
# THE ENVIRONMENT IS THE GUARD. Four of them, independent, so defeating one is
# not enough:
#
#   1 · `remote.origin.pushurl` = /dev/null, set with `--worktree` so it CANNOT
#       reach the shared repository's config (the mis-scoping of this one line
#       would silently break every real push, so the arming test asserts the
#       shared value is untouched).
#   2 · DETACHED HEAD — there is no branch to push, and no branch to move.
#   3 · A LENS-LOCAL `core.hooksPath` whose pre-commit and pre-push refuse
#       unconditionally, with no override token. There is deliberately no
#       DECLARE_ escape hatch: a lens has no legitimate reason to write.
#   4 · NO CREDENTIALS. `lens-env.sh` unsets GH_TOKEN/GITHUB_TOKEN and points
#       GH_CONFIG_DIR at an empty directory, so `gh` is unauthenticated and
#       `gh pr create` fails at auth rather than at politeness.
#
# USAGE
#   dir=$(bash scripts/make-lens-sandbox.sh lens1)   # prints the path
#   # then run the agent with:  . "$dir/.lens-env.sh"
#
# REAP with `bash scripts/reap-lens-sandbox.sh <dir>`.
# ============================================================================
set -euo pipefail
# ⚠️ THE ROOT IS DERIVED, NOT HARDCODED — AND THIS SESSION FIXED THE SAME BUG
# ONE HOUR EARLIER IN #1009. A literal `/opt/meddoc-pro` is correct on this VPS
# and does not exist on the CI runner or in any worktree, so a check written
# that way passes locally and is meaningless (or red) everywhere else.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED="$(git -C "$HERE" rev-parse --show-toplevel)"
NAME="${1:?usage: make-lens-sandbox.sh <name> [ref]}"
REF="${2:-origin/main}"
DIR="$SHARED/.lens-$NAME"

[ -e "$DIR" ] && { echo "🔴 $DIR already exists — reap it first." >&2; exit 1; }

# ══════════════════════════════════════════════════════════════════════════════
# ⚠️ THE REF IS RESOLVED IN THE **CALLER'S** WORKTREE, NEVER IN THE SHARED TREE.
# ------------------------------------------------------------------------------
# CANON: "a sealed sandbox pointed at the wrong tree — every guard said fine."
#
# `$SHARED` is this SCRIPT's repo root, i.e. /opt/meddoc-pro, which by standing
# rule sits on `main`. Resolving `$REF` there meant a caller running from a
# feature worktree and passing `HEAD` — the obvious, correct-looking invocation —
# got a sandbox at **main's** HEAD instead of their own.
#
# MEASURED, 2026-09-08, on the #274 refutation pass: one lens was provisioned at
# `bc544641` (main), where the file under review DID NOT EXIST. Every guard in
# this script passed: the worktree was created, write-locked, hook-refused,
# credential-free and marked. The sandbox was perfectly sealed around the wrong
# commit, and the lens's prescribed `git diff origin/main..HEAD` showed an EMPTY
# diff — which reads as "nothing to review" rather than as "you are in the wrong
# tree". Only the agent noticing the file was missing caught it.
#
# A symbolic ref means different commits in different worktrees. Resolving it
# where the CALLER stands is the only reading that can be right, and pinning it
# to a full sha before `worktree add` removes the ambiguity entirely.
# ══════════════════════════════════════════════════════════════════════════════
CALLER="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$CALLER" ] || CALLER="$SHARED"
REF_SHA="$(git -C "$CALLER" rev-parse --verify "${REF}^{commit}" 2>/dev/null || true)"
if [ "${#REF_SHA}" -ne 40 ]; then
  # FAIL-CLOSED. An unresolvable ref and a typo produce the same empty string,
  # and a sandbox at the wrong commit is worse than no sandbox.
  echo "🔴 REFUSING — cannot resolve '$REF' to a commit in $CALLER." >&2
  echo "   (a sandbox at the wrong commit passes every guard and reviews nothing)" >&2
  exit 1
fi
if [ "$CALLER" != "$SHARED" ]; then
  echo "   ref '$REF' resolved in $CALLER -> ${REF_SHA:0:12}" >&2
fi

# ══════════════════════════════════════════════════════════════════════════════
# ⚠️ FROM HERE ON, A FAILURE MUST LEAVE **NO SANDBOX**, NOT AN UNARMED ONE.
# ------------------------------------------------------------------------------
# MEASURED 2026-09-09. A parallel batch of eleven sandboxes produced TWO that
# were checked out at the right commit and NOT ARMED: `remote.origin.pushurl`
# unset, `core.hooksPath` still pointing at the repository's real hooks, and no
# `.lens-env.sh` at all. The script exited non-zero — and the DIRECTORY STAYED.
#
# That artifact is the exact thing this file exists to prevent. It is worse than
# no sandbox, because it looks like one: `ls` shows it, `git -C` answers from
# it, and a caller that tests `[ -d "$DIR" ]` instead of the exit status hands a
# lens agent a tree it can commit and push out of. The guards did not fail —
# they were never installed, and nothing said so.
#
# ⚠️ THE MECHANISM IS NOT PROVEN AND IS RECORDED AS UNPROVEN. A deliberate
# three-way concurrent reproduction on the same box, minutes later, did NOT
# reproduce it — all three came out armed. A race sampled coarsely is a race
# missed, so that is not a refutation; but neither is it a demonstration, and
# this comment must not claim one. What IS proven is the shape: this script had
# ZERO traps and discarded `worktree add`'s exit status, so ANY failure after
# the worktree exists leaves the unarmed tree behind.
#
# So the fix is not "find the race" — it is fail-closed teardown plus a
# self-assertion, which is correct whatever the trigger turns out to be.
# ══════════════════════════════════════════════════════════════════════════════
CREATED=0
teardown_if_failed() {
  rc=$?
  [ "$rc" -eq 0 ] && return 0
  [ "$CREATED" -eq 1 ] || return 0
  echo "🔴 creation FAILED after the worktree existed — tearing it down." >&2
  echo "   an UNARMED sandbox that looks built is the artifact this prevents." >&2
  git -C "$SHARED" worktree remove --force "$DIR" >/dev/null 2>&1 || true
  [ -e "$DIR" ] && rm -rf "$DIR"
  git -C "$SHARED" worktree prune >/dev/null 2>&1 || true
  return 0
}
trap teardown_if_failed EXIT

# ── The worktree, DETACHED. No branch exists to be pushed or moved. ──────────
# ⚠️ THE EXIT STATUS IS CHECKED. It used to be discarded with `>/dev/null 2>&1`
# and no `||`, so a failed `worktree add` fell through into the arming steps.
if ! git -C "$SHARED" worktree add --detach "$DIR" "$REF_SHA" >/dev/null 2>&1; then
  echo "🔴 REFUSING — \`git worktree add\` failed for $DIR at ${REF_SHA:0:12}." >&2
  exit 1
fi
CREATED=1

# ── Worktree-scoped config. `--worktree` needs the extension; enabling it is a
#    documented, reversible git feature and it is what keeps the next line from
#    landing in the SHARED config and breaking real pushes. ───────────────────
git -C "$SHARED" config extensions.worktreeConfig true
git -C "$DIR" config --worktree remote.origin.pushurl /dev/null
git -C "$DIR" config --worktree core.hooksPath "$DIR/.lens-hooks"

# ── Hooks that refuse. No token, no override — a lens never writes. ──────────
mkdir -p "$DIR/.lens-hooks"
for hook in pre-commit pre-push; do
  cat > "$DIR/.lens-hooks/$hook" <<HOOK
#!/usr/bin/env bash
echo "🔴 REFUSED — this is a LENS SANDBOX (\$(basename "\$(dirname "\$0")" ))." >&2
echo "   A refutation lens reads and measures. It does not $hook." >&2
echo "   There is no override: if this tree needs to write, it is not a lens." >&2
exit 1
HOOK
  chmod +x "$DIR/.lens-hooks/$hook"
done

# ── The environment the agent must be launched under. ────────────────────────
mkdir -p "$DIR/.lens-ghconfig"
cat > "$DIR/.lens-env.sh" <<ENV
# Source this before running a lens agent in this tree.
unset GH_TOKEN GITHUB_TOKEN GH_ENTERPRISE_TOKEN GITHUB_ENTERPRISE_TOKEN
export GH_CONFIG_DIR="$DIR/.lens-ghconfig"
export GIT_CONFIG_GLOBAL=/dev/null
export LENS_SANDBOX=1
ENV

# ── AND THE TREE IS MADE RUNNABLE, OR THE LENS MEASURES THE WRONG REPOSITORY. ──
#
# ⚠️ ADDED 2026-09-07, AFTER A LENS SPENT ITS BUDGET ON VOID RESULTS. A round-
# eight lens reported ~24 test files failing in its sandbox with
# `Failed to resolve import "react/jsx-dev-runtime"` and
# `@meddoc/auth resolves to /opt/meddoc-pro/packages/auth/src/index.ts, outside
# this worktree`. It caught that itself and correctly discarded every claim
# resting on those files — but a lens that has to notice its own harness is
# broken is a lens spending its budget on the harness.
#
# ⚠️ AND THE FAILURE MODE IS WORSE THAN "SOME TESTS DO NOT RUN". A raw
# `node_modules` symlink resolves `@meddoc/*` to the SHARED tree, so a green in
# here can be a green about code the sandbox does not contain. The repository
# already has one door for this and this script was not using it.
#
# Non-fatal: a sandbox that cannot install is still useful for reading, and
# saying so beats refusing to build one.
if [ -f "$SHARED/scripts/setup-worktree.sh" ]; then
    if ( cd "$DIR" && bash "$SHARED/scripts/setup-worktree.sh" >/dev/null 2>&1 ); then
        :
    else
        echo "⚠️  setup-worktree.sh failed in $DIR — .tsx and packages/* results in" >&2
        echo "    this sandbox are NOT trustworthy. Read-only lenses are fine." >&2
    fi
else
    echo "⚠️  setup-worktree.sh not found — sandbox is read-only-safe only." >&2
fi

# ══════════════════════════════════════════════════════════════════════════════
# ⚠️ THE SANDBOX ASSERTS ITS OWN ARMING BEFORE IT IS HANDED OVER.
# ------------------------------------------------------------------------------
# A stated invariant is a wish until something asserts it — this file's own
# doctrine, applied to this file. `arm-lens-sandbox.sh` proves the guards REFUSE,
# but it only ever runs against a sandbox that was built successfully; nothing
# checked that a returned path is armed at all. This is the cheap structural
# half: four properties, read back from git and the filesystem rather than
# assumed from the fact that the lines above executed.
#
# It is a POSITIVE-CONTROL-shaped check on purpose: it reads the values, it does
# not trust that setting them worked.
# ══════════════════════════════════════════════════════════════════════════════
armed_pushurl="$(git -C "$DIR" config --get remote.origin.pushurl 2>/dev/null || echo UNSET)"
armed_hooks="$(git -C "$DIR" config --get core.hooksPath 2>/dev/null || echo UNSET)"
arming_fault=""
[ "$armed_pushurl" = "/dev/null" ] || arming_fault="$arming_fault pushurl=[$armed_pushurl]"
[ "$armed_hooks" = "$DIR/.lens-hooks" ] || arming_fault="$arming_fault hooksPath=[$armed_hooks]"
[ -x "$DIR/.lens-hooks/pre-commit" ] || arming_fault="$arming_fault pre-commit-not-executable"
[ -x "$DIR/.lens-hooks/pre-push" ] || arming_fault="$arming_fault pre-push-not-executable"
[ -f "$DIR/.lens-env.sh" ] || arming_fault="$arming_fault no-lens-env.sh"
if [ -n "$arming_fault" ]; then
  echo "🔴 REFUSING — the sandbox was created but is NOT ARMED:$arming_fault" >&2
  echo "   handing this path back would give a lens a tree it can write out of." >&2
  exit 1
fi

echo "$DIR"
