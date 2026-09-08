#!/usr/bin/env bash
# ============================================================================
# prove-mutation.sh — run a mutation proof so it CANNOT eat uncommitted work,
# and CANNOT report a green it did not earn.
# ----------------------------------------------------------------------------
# ⚠️ THIS EXISTS BECAUSE THE HABIT KEPT NOT REACHING BEHAVIOUR. A mutation proof
# is: break the code on purpose, watch the arm go red, restore. The restore is
# `git checkout -- <file>`, and that is the trap:
#
#   `git checkout` restores to the COMMIT, not to the state before the mutation.
#   Any uncommitted work in that file is destroyed, silently, exit 0.
#
# It cost real work THREE times in one session — twice on a file holding a
# half-finished fix, once on a change that had been typechecked and tested but
# not committed. Each time the lesson was written down. Writing a lesson down is
# not obeying it, which is why this is a script and not a paragraph.
#
# ── WHAT IT REFUSES ─────────────────────────────────────────────────────────
#   · a DIRTY tree — the whole point; commit first, then mutate
#   · a mutation that did not APPLY — an unapplied mutation yields a green that
#     proves nothing and is indistinguishable from a guard that works
#   · a proof whose arm PASSED under mutation — that is a vacuous arm, and it is
#     the finding, not a hiccup
#
# ── FAIL-CLOSED ON CANNOT-TELL ──────────────────────────────────────────────
# No git, not a work tree, an unreadable status, a marker that cannot be found
# in the mutated file: all REFUSE. A broken instrument and a clean tree produce
# the same empty `git status`.
# ============================================================================
set -uo pipefail

usage() {
  cat >&2 <<'USAGE'
usage: bash scripts/prove-mutation.sh --file <path> --marker <text> --expect-fail <cmd...>

  --file        the file the mutation edits (restored from HEAD afterwards)
  --marker      a string that MUST appear in the file after mutating; this is
                how the script knows the mutation landed rather than no-oped
  --mutate      shell command that performs the mutation (default: read a patch
                from stdin and apply it with `git apply`)
  --expect-fail everything after this is the proof command; it MUST fail

Exit codes: 0 proof held · 1 refused before mutating · 2 the proof did not hold
USAGE
}

FILE=""; MARKER=""; MUTATE=""; declare -a CMD=()
while [ $# -gt 0 ]; do
  case "$1" in
    --file)        FILE="${2:-}"; shift 2 ;;
    --marker)      MARKER="${2:-}"; shift 2 ;;
    --mutate)      MUTATE="${2:-}"; shift 2 ;;
    --expect-fail) shift; CMD=("$@"); break ;;
    -h|--help)     usage; exit 0 ;;
    *) echo "prove-mutation: unrecognised argument: $1" >&2; usage; exit 1 ;;
  esac
done

[ -n "$FILE" ]   || { echo "prove-mutation: --file is required" >&2; exit 1; }
[ -n "$MARKER" ] || { echo "prove-mutation: --marker is required — without it an unapplied mutation reads as a pass" >&2; exit 1; }
[ -n "$MUTATE" ] || { echo "prove-mutation: --mutate is required" >&2; exit 1; }
[ "${#CMD[@]}" -gt 0 ] || { echo "prove-mutation: --expect-fail <cmd...> is required" >&2; exit 1; }

command -v git >/dev/null 2>&1 || { echo "prove-mutation: REFUSING — no git, so the tree state cannot be established" >&2; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "prove-mutation: REFUSING — not inside a git work tree" >&2; exit 1; }
[ -f "$FILE" ] || { echo "prove-mutation: REFUSING — $FILE does not exist" >&2; exit 1; }

# ── THE GUARD THIS SCRIPT EXISTS FOR ────────────────────────────────────────
# Tracked, uncommitted changes ANYWHERE are refused, not merely in $FILE: a
# proof usually spans several files, and the restore is only safe when HEAD is
# what the tree already says.
if ! STATUS="$(git status --porcelain --untracked-files=no 2>/dev/null)"; then
  echo "prove-mutation: REFUSING — git status failed; cannot tell whether the tree is clean" >&2
  exit 1
fi
if [ -n "$STATUS" ]; then
  echo "prove-mutation: REFUSING — the tree has uncommitted tracked changes." >&2
  echo "  A mutation proof restores with \`git checkout\`, which restores to the COMMIT." >&2
  echo "  Anything uncommitted in these files would be DESTROYED, silently, exit 0:" >&2
  printf '%s\n' "$STATUS" | sed 's/^/    /' >&2
  echo "  Commit first. That is the whole rule, and it is why this is a script." >&2
  exit 1
fi

BEFORE="$(git rev-parse HEAD)"
echo "prove-mutation: tree clean at ${BEFORE:0:8}; mutating $FILE"

restore() {
  git checkout -- "$FILE" 2>/dev/null || true
  if [ -n "$(git status --porcelain --untracked-files=no -- "$FILE" 2>/dev/null)" ]; then
    echo "prove-mutation: ⚠️ $FILE is STILL modified after restore — inspect it by hand" >&2
  fi
}
trap restore EXIT

# ⚠️ A SUBSHELL, DELIBERATELY. `eval "exit 3"` in the current shell exits THIS
# script with 3 and the refusal below is never printed — found by this script's
# own gate, which is the entire argument for having one.
if ! ( eval "$MUTATE" ); then
  echo "prove-mutation: REFUSING — the mutation command itself failed; nothing was proved" >&2
  exit 1
fi

# ⚠️ ASSERT THE MUTATION APPLIED, BEFORE BELIEVING ANY RESULT THAT FOLLOWS.
# `.replace()` on a non-match is a silent no-op that returns the original
# string, and the script then reports success.
if ! grep -qF -- "$MARKER" "$FILE"; then
  echo "prove-mutation: REFUSING — marker not found in $FILE after mutating." >&2
  echo "  The mutation did not apply. A suite run now would be green against" >&2
  echo "  UNMUTATED code, which is indistinguishable from a guard that works." >&2
  exit 1
fi
echo "prove-mutation: mutation applied (marker present)"

echo "prove-mutation: running the proof — it MUST fail"
"${CMD[@]}"
RC=$?

if [ "$RC" -eq 0 ]; then
  echo "prove-mutation: ⚠️ THE PROOF PASSED UNDER MUTATION — the arm is VACUOUS." >&2
  echo "  This is the finding. The guard does not measure what it claims to." >&2
  exit 2
fi

echo "prove-mutation: ✅ the arm failed under mutation (exit $RC) — the proof holds"
exit 0
