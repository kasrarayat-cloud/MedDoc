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

# ⚠️ AND IT REFUSES TO BE DRIVEN BY A WHOLE-TREE SWEEP — 2026-09-29, twice.
#
#   find <whole session scratchpad> -type f | xargs bash scripts/reap-session-scratch.sh
#       -> a subagent shredded 30 files OTHER agents had written
#   find … -print0 | xargs -0 -n 200 bash scripts/reap-session-scratch.sh   (three passes)
#       -> the lead shredded 6,537 files, including the cleanup's own lists and logs
#
# Every path was inside the sandbox, untracked and not a symlink escape, so every
# refusal below passed — correctly. None of them is OWNERSHIP: the sandbox is one
# uid's, shared by every agent in it. So more than REAP_SESSION_BULK_BOUND paths
# in any 5 minutes — counted ACROSS calls in a per-uid window under
# ${XDG_STATE_HOME:-$HOME/.local/state}/scratch-sweep-guard/, whatever process
# drives them — or a find/xargs/parallel ancestor, is REFUSED unless
# REAP_SESSION_BULK_DECLARATION says why (12+ visible characters of prose, echoed
# to stderr — the DECLARE_CANCELLATION check, sourced not copied).
#
# ⚠️ SUBAGENTS DO NOT USE THIS DOOR FOR CLOSE-OUT. Record each disposable file
# once it is written (`bash scripts/scratch-ledger.sh record …`) and reap only the
# ledger (`bash scripts/reap-recorded-scratch.sh <ledger>`), which shreds nothing
# it did not record and nothing that changed since.
REAP_SESSION_BULK_BOUND=16
_reap_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || _reap_here=""
if [ -z "$_reap_here" ] || [ ! -r "$_reap_here/lib/sweep-guard.sh" ]; then
  echo "🔴 reap: CANNOT TELL — scripts/lib/sweep-guard.sh is missing, so a sweep cannot be"
  echo "   told from a deliberate call. Refusing."
  exit 1
fi
# shellcheck source=lib/sweep-guard.sh
. "$_reap_here/lib/sweep-guard.sh"
# ⚠️ THE BOUND IS COUNTED ACROSS CALLS (2026-09-29 refutation, F2). A per-call bound
# plus a process-NAME check was defeated by `busybox xargs`, xargs under another
# name and `setsid -f`, each feeding 16 paths at a time. The count now lives in a
# per-uid window outside the sandbox, so at most $REAP_SESSION_BULK_BOUND undeclared
# paths pass per window whatever drives the calls.
_reap_window="$(sweep_guard_state_file reap-session-scratch)" || exit 1
sweep_guard "reap-session-scratch" "$#" "$REAP_SESSION_BULK_BOUND" REAP_SESSION_BULK_DECLARATION "$_reap_window" || exit 1

# A caller's GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE would make `git -C <dir>`
# answer about ANOTHER repository, so none of them reaches the checks below.
for _reap_var in $(compgen -e); do
  case "$_reap_var" in GIT_*) unset "$_reap_var" ;; esac
done

# Walk up from a path to the sandbox root looking for a repository marker. A
# `.git` FILE (a worktree) counts as much as a `.git` DIRECTORY: the whole point
# is that the marker survives the worktree registration it points at.
git_marker_above() {
  local d="$1"
  while [ -n "$d" ] && [ "$d" != "/" ]; do
    case "$d" in "$SANDBOX"*) : ;; *) return 1 ;; esac
    { [ -e "$d/.git" ] || [ -L "$d/.git" ]; } && return 0
    # A bare repository (or a .git directory git no longer recognises) has no
    # `.git` marker of its own: its SHAPE is the marker.
    [ -f "$d/HEAD" ] && [ -d "$d/objects" ] && [ -d "$d/refs" ] && return 0
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
  # ⚠️ NEVER A SHARED INODE (2026-09-29 refutation, F1). `realpath` answers for ONE
  # name; a hard link is another name for the same data, and it can live OUTSIDE
  # the sandbox on the same filesystem. A local `git clone <path on /opt> <scratch>`
  # makes exactly that: the clone's .git/objects are hard links to the SOURCE's,
  # and shredding one overwrites the other in place. So only a regular file with
  # exactly one link is taken. (Honest limit: a link made between this check and
  # shred's own open is not seen; the recorded reaper re-checks on the open file.)
  _reap_info="$(stat -c '%h:%F' -- "$resolved" 2>/dev/null)" || _reap_info=""
  case "${_reap_info#*:}" in
    'regular file'|'regular empty file') ;;
    '') echo "🔴 REFUSED (CANNOT TELL — the file cannot be inspected): $resolved"; rc=1; continue ;;
    *) echo "🔴 REFUSED (not a regular file: ${_reap_info#*:}): $resolved"; rc=1; continue ;;
  esac
  if [ "${_reap_info%%:*}" != "1" ]; then
    echo "🔴 REFUSED (SHARED HARD LINK: link count ${_reap_info%%:*} — another name, possibly outside"
    echo "   the sandbox, reaches the same data): $resolved"
    rc=1; continue
  fi
  # ⚠️ GIT'S OWN FILES ARE NEVER SCRATCH (F6). `ls-files` answers for the work tree,
  # not for .git/: a file inside it read as "untracked" and was shredded.
  case "/$resolved/" in
    */.git/*) echo "🔴 REFUSED (INSIDE A .git DIRECTORY — git's own data, never scratch): $resolved"; rc=1; continue ;;
  esac
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
  if _reap_gitdir="$(git -c core.fsmonitor=false -C "$target_dir" rev-parse --is-inside-git-dir 2>/dev/null)"; then
    if [ "$_reap_gitdir" != "false" ]; then
      echo "🔴 REFUSED (INSIDE A GIT DIRECTORY — a bare repository's own data, never scratch): $resolved"
      rc=1; continue
    fi
    # ⚠️ THREE ANSWERS, NOT TWO (F6): 0 = tracked, 1 = untracked, anything else
    # (128: an unreadable index, a dubious-ownership refusal) = git could not say.
    git -c core.fsmonitor=false -C "$target_dir" ls-files --error-unmatch -- "$resolved" >/dev/null 2>&1
    _reap_git_rc=$?
    case "$_reap_git_rc" in
      0) echo "🔴 REFUSED (TRACKED by git — a committed fixture, not scratch): $resolved"
         rc=1; continue ;;
      1) : ;;
      *) echo "🔴 REFUSED (CANNOT TELL — git exited $_reap_git_rc when asked whether this is tracked): $resolved"
         rc=1; continue ;;
    esac
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
