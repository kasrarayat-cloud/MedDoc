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

# ── THE MARKER — #206 as amended by #213 ────────────────────────────────────
#
# ⚠️ WRITTEN IMMEDIATELY AFTER THE WORKTREE EXISTS, AND BEFORE ANYTHING THAT CAN
# FAIL. The `setup-worktree.sh` block below is explicitly non-fatal, so a sandbox
# whose install failed must still be attributable — an unmarked tree is exactly
# the state that makes twenty of them un-reapable by anyone.
#
# ⚠️ `CLAUDE_PID`, NEVER `$$` — #213, and measured first-hand in this shell:
#
#     CLAUDE_PID = 2204890        $$ = 3555429
#
# `$$` in a tool shell is a FRESH SUBSHELL. The pid it records belongs to a
# process that was already dead when the file was written, so an aliveness check
# against it answers "dead" — the direction that costs somebody their tree.
#
# ⚠️ AND THE START-TIME BINDS THE PID TO AN IDENTITY. Three sessions share one
# account on this box; a bare pid is reused, and a reused pid reads as ALIVE for
# a session that ended hours ago. Field 22 of /proc/<pid>/stat is the process's
# own start tick — it cannot be inherited by a later process wearing the same
# number.
_marker_pid="${CLAUDE_PID:-}"
_marker_start=""
if [ -n "$_marker_pid" ] && [ -r "/proc/$_marker_pid/stat" ]; then
  _marker_start="$(awk '{print $22}' "/proc/$_marker_pid/stat" 2>/dev/null || true)"
fi
_marker_sha="$(git -C "$SHARED" rev-parse --verify --quiet "${REF}^{commit}" 2>/dev/null || true)"
_marker_now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat > "$DIR/.lens-marker" <<MARKER
# A LENS SANDBOX'S PROVENANCE — #206, as amended by #213.
# Read by scripts/reap-lens-sandbox.sh. Machine-readable: key=value, one per line.
owner_session=${CLAUDE_CODE_SESSION_ID:-unknown}
owner_pid=${_marker_pid:-unknown}
owner_starttime=${_marker_start:-unknown}
created_utc=$_marker_now
heartbeat_utc=$_marker_now
ref_under_test=$REF
ref_sha=${_marker_sha:-unknown}
MARKER

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

echo "$DIR"
