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

# ── The worktree, DETACHED. No branch exists to be pushed or moved. ──────────
git -C "$SHARED" worktree add --detach "$DIR" "$REF" >/dev/null 2>&1

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

echo "$DIR"
