#!/usr/bin/env bash
# ============================================================================
# REAP SESSION SCRATCH — shred files, refusing anything outside the sandbox.
#   0 = every target shredded   1 = one or more REFUSED or failed
# ----------------------------------------------------------------------------
# ⚠️ WHY THIS EXISTS RATHER THAN A `shred` GRANT. Ruling #166 granted `shred`
# and the grant was written twice, wrongly, both times:
#
#   Bash(shred:*)                              — no scope at all
#   Bash(shred -u -n 3 -z:*)                   — scopes the FLAGS
#   Bash(shred -u -n 3 -z /tmp/claude-1000/:*) — scopes the TEXT, not the PATH
#
# The third looks right and is not. A permission entry is a COMMAND-TEXT PREFIX,
# so it admits everything that merely starts with those characters:
#
#   shred -u -n 3 -z /tmp/claude-1000/../../opt/meddoc-pro/.env
#       -> prefix matches, and normalises to /opt/meddoc-pro/.env, which the
#          same settings file DENIES READING
#   shred -u -n 3 -z /tmp/claude-1000/x /opt/meddoc-pro/.env
#       -> `shred` takes FILE..., so the second operand goes anywhere
#
# ⚠️ NO PREFIX PATTERN CAN FIX THAT, because the hole is in what comes AFTER the
# prefix and the matcher does not parse paths. The repository's dominant
# convention — 35 entries of `Bash(bash scripts/<named>.sh:*)` — does not have
# this weakness: nothing after the prefix can change WHICH FILE RUNS. So the
# scope moves into a script that can actually resolve a path and refuse.
#
# ⚠️ AND IT IS FAIL-CLOSED ON CANNOT-TELL. An unresolvable path, a symlink
# pointing out of the sandbox, or a missing `shred` all REFUSE.
# ============================================================================
set -uo pipefail

SANDBOX="/tmp/claude-1000/"

command -v shred >/dev/null 2>&1 || {
  echo "🔴 reap: no shred on PATH. Refusing — a reap that cannot shred must not"
  echo "   fall back to rm: unlinking turns a recoverable failure into a"
  echo "   permanent one, because the file is gone and its blocks remain."
  exit 1
}

[ "$#" -gt 0 ] || { echo "usage: reap-session-scratch.sh <file>..."; exit 1; }

# Walk up from a path to the sandbox root looking for a repository marker. A
# `.git` FILE (a worktree) counts as much as a `.git` DIRECTORY: the whole point
# is that the marker survives the worktree registration it points at.
git_marker_above() {
  local d="$1"
  while [ -n "$d" ] && [ "$d" != "/" ]; do
    case "$d" in "$SANDBOX"*) : ;; *) return 1 ;; esac
    [ -e "$d/.git" ] && return 0
    d="$(dirname -- "$d")"
  done
  return 1
}

rc=0
for target in "$@"; do
  # Resolve symlinks and `..` BEFORE deciding. `realpath -m` resolves a path
  # that may not exist, which is what makes the check honest about traversal.
  resolved="$(realpath -m -- "$target" 2>/dev/null || true)"
  if [ -z "$resolved" ]; then
    echo "🔴 REFUSED (unresolvable): $target"; rc=1; continue
  fi
  case "$resolved" in
    "$SANDBOX"*) : ;;
    *) echo "🔴 REFUSED (outside $SANDBOX): $target -> $resolved"; rc=1; continue ;;
  esac
  if [ ! -e "$resolved" ]; then
    echo "   skipped (absent): $resolved"; continue
  fi
  # ⚠️ NEVER DESTROY A FILE GIT IS TRACKING, AND THIS EXISTS BECAUSE I DID.
  #
  # A scratch sweep ran `find` over four git WORKTREES living under the sandbox
  # and shredded 27 tracked, committed BLANK FIXTURES — `sample-form.docx`,
  # `colon_blank_answers.pdf`, the adjudicated audit PDF, every
  # `tests/e2e/fixtures/**` and `__fixtures__/**` entry. Precisely the allowlist
  # AGENTS.md names, and precisely the outcome it warns of: "a sweep that eats
  # the blank fixtures breaks the twin work".
  #
  # ⚠️ THE ASSERTION THAT SHOULD HAVE CAUGHT IT RAN AGAINST THE WRONG TREE.
  # Canon 52 requires asserting what must SURVIVE, and it was asserted — in the
  # feature worktree, which was never swept — while the sweep was deleting the
  # same filenames in the four worktrees it did touch. Two paths that look
  # identical in a report and are different files on disk. Canon 87's lesson in
  # a new costume: the survival check must run in the tree that was destroyed
  # in, not in one that happens to hold a file of the same name.
  #
  # A path check cannot express this — the sandbox legitimately CONTAINS git
  # worktrees. Only git knows. So ask git, and fail closed when it cannot say.
  # ⚠️ AND THE THIRD STATE IS THE ONE THAT BIT: GIT CANNOT ANSWER.
  #
  # This guard used to be TWO states — git says tracked (refuse), git says
  # untracked (shred) — and treated "git could not answer at all" as the second.
  # That is FAIL-OPEN on cannot-tell, in the one file whose header promises the
  # opposite, and it fired: reaping a scratch directory whose worktree had been
  # PRUNED shredded `colon_blank_answers.pdf`, a tracked blank fixture.
  #
  #     $ git -C <orphaned worktree> rev-parse --git-dir
  #     fatal: not a git repository: /opt/meddoc-pro/.git/worktrees/al4
  #
  # An orphaned worktree still carries its `.git` FILE; the entry it points to is
  # gone. So `rev-parse` fails, the `if` is skipped, and the tracked check never
  # runs — on a directory that is FULL of tracked files.
  #
  # ⚠️ AND THAT STATE IS NOT EXOTIC, IT IS THE NORMAL END OF A SESSION. Scratch
  # worktrees get `git worktree remove`d or pruned and their directories linger;
  # that is precisely when someone reaches for this script. The guard was absent
  # exactly when it was needed — canon 89's incident in a new costume, in the
  # tool written to prevent canon 89's incident.
  target_dir="$(dirname -- "$resolved")"
  if git -C "$target_dir" rev-parse --git-dir >/dev/null 2>&1; then
    if git -C "$target_dir" ls-files --error-unmatch -- "$resolved" >/dev/null 2>&1; then
      echo "🔴 REFUSED (TRACKED by git — a committed fixture, not scratch): $resolved"
      rc=1; continue
    fi
  elif git_marker_above "$target_dir"; then
    echo "🔴 REFUSED (CANNOT TELL — a repository marker sits above this path but"
    echo "   git will not answer for it, so whether it is a tracked fixture is"
    echo "   UNKNOWN. Re-register or remove the worktree, then reap): $resolved"
    rc=1; continue
  fi
  if shred -u -n 3 -z -- "$resolved"; then
    echo "   shredded: $resolved"
  else
    # ⚠️ REPORTED, NEVER SWALLOWED. AGENTS.md: check exit codes, escalate the
    # failures, and only then remove a directory.
    echo "🔴 SHRED FAILED (exit $?): $resolved"; rc=1
  fi
done
exit $rc
