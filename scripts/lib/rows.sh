#!/usr/bin/env bash
# ============================================================================
# ROWS-FILE IDENTITY — does a §2.5 rows file belong to THIS pull request?
# ----------------------------------------------------------------------------
# ⚠️ IT IS ITS OWN FILE SO A TEST CAN DRIVE IT WITHOUT A GIT RANGE, and that is
# the whole reason it exists. The gate itself must be anchored to its own
# location and must resolve a real merge-base (F28), which makes it awkward to
# exercise from a unit test — so the one DECISION inside it that a future edit
# could quietly widen lives here, as a pure function over strings. Same shape as
# `scripts/lib/inflight.sh` and `scripts/lib/declaration.sh`: one
# implementation, two callers, because a second copy drifts from the first the
# day either is fixed.
#
# ⚠️ AND THE DEFECT IT EXISTS TO PREVENT WAS FOUND IN THE GATE'S OWN BRANCH.
# The first cut accepted ANY `docs/foundation/deploys/rows/PR-<n>.md` appearing
# in the diff, without checking that `<n>` was the PR being gated. The branch it
# was written on then carried a rows file named `PR-1008.md` — describing the
# GATE, while PR #1008 is another lane's `fix/citation-sigpipe`. Had it merged,
# two things would have been true at once:
#
#   · the gate would have passed its own PR on a file naming a different one; and
#   · PR #1008 — a runtime PR belonging to a lane that never wrote those rows —
#     would have been passed by the gate FOREVER, on rows describing a shell
#     script, because `docs/foundation/deploys/rows/PR-1008.md` would exist.
#
# The second is the one that matters: a gate that can be satisfied by somebody
# else's artifact does not gate. And "only the author can say what would be a
# FINDING" is the entire premise of ruling #184 — a rows file is bound to a
# CHANGE, exactly as a §2.5 declaration is, and inheriting one is the same
# overtaken-not-overridden failure one level down.
# ============================================================================

# rows_file_pr_number <path>
#   Echoes the PR number a rows-file path names, or nothing if the path is not
#   a rows file at all. Never matches a nested path or a suffixed name.
rows_file_pr_number() {
  local path="${1:-}"
  case "$path" in
    docs/foundation/deploys/rows/PR-*.md) ;;
    *) return 1 ;;
  esac
  local base="${path#docs/foundation/deploys/rows/PR-}"
  base="${base%.md}"
  # digits only — `PR-1008-draft.md` and `PR-abc.md` are NOT rows files
  case "$base" in
    ''|*[!0-9]*) return 1 ;;
  esac
  printf '%s' "$base"
}

# rows_file_matches_pr <pr_number> <path...>
#   0 when at least one path is a rows file naming EXACTLY <pr_number>.
#   1 otherwise — including when rows files are present but all name other PRs,
#   which is the case worth refusing loudly.
#
#   ⚠️ AN EMPTY <pr_number> RETURNS 1, NOT 0. The caller decides what to do when
#   the PR number is unknown; this function never answers "yes" on the strength
#   of not knowing. A predicate that passes when its input is missing is the
#   fail-open shape, and this house has paid for that one already.
rows_file_matches_pr() {
  local want="${1:-}"; shift || true
  case "$want" in
    ''|*[!0-9]*) return 1 ;;
  esac
  local path got
  for path in "$@"; do
    got="$(rows_file_pr_number "$path")" || continue
    [ "$got" = "$want" ] && return 0
  done
  return 1
}
