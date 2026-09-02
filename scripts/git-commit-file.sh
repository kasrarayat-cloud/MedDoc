#!/usr/bin/env bash
# ============================================================================
# THE ONLY DOOR TO A COMMIT MESSAGE. `git commit -m` IS DENIED.
#   usage: bash scripts/git-commit-file.sh <message-file> [extra git args…]
#   0 = committed   1 = refused   2 = cannot tell
# ----------------------------------------------------------------------------
# ⚠️ WHY THIS IS MECHANISM AND NOT A REMINDER. "PROSE IS NEVER A SHELL ARGUMENT"
# has been standing since 2026-08-10 with two recorded occurrences, and on
# 2026-09-02 it happened a THIRD time — a commit message describing laundered
# test guards was passed as a quoted `-m`, the shell evaluated the backticks
# around three identifiers, `.slice(0,1)` threw a syntax error, the commit did
# not happen, and git received fragments of prose as pathspecs.
#
# The rule's own entry says it fails on the one message you dash off, not on the
# ones you disagree with. Ruling #171: the third occurrence is where a rule
# becomes a script.
#
# ⚠️ TWO COSTS, AND THE SECOND IS THE QUIET ONE: a substitution RUNS, and the
# artifact is SILENTLY CORRUPTED. On 2026-08-21 a `-m` message lost a word to
# the shell and committed successfully with a hole in the sentence.
# ============================================================================
set -uo pipefail

MSG="${1:-}"
[ -n "$MSG" ] || { echo "🔴 commit-file: no message file given." >&2; exit 1; }
[ -r "$MSG" ] || { echo "🔴 commit-file: '$MSG' is not readable." >&2; exit 1; }
[ -s "$MSG" ] || { echo "🔴 commit-file: '$MSG' is empty — a commit needs a message." >&2; exit 1; }
shift

# ⚠️ A SUBJECT LINE IS NOT OPTIONAL. An accidental leading blank line makes git
# use the first non-empty line as the subject, silently reshaping the message.
head -1 "$MSG" | grep -q '[^[:space:]]' || {
  echo "🔴 commit-file: the first line of '$MSG' is blank." >&2
  exit 1
}

git commit -F "$MSG" "$@"
rc=$?
# ⚠️ READ THE OUTCOME FROM THE SYSTEM THAT OWNS IT, not from the exit code
# alone — canon 22. A wrapper's status describes its last command.
if [ "$rc" -eq 0 ]; then
  echo "🟢 commit-file: $(git rev-parse --short HEAD) $(git log -1 --pretty=%s)"
fi
exit "$rc"
