#!/usr/bin/env bash
# ============================================================================
# IS THIS BRANCH'S HEAD A DECLARED DEPLOY CANDIDATE? — ruling #186(3).
# ----------------------------------------------------------------------------
#   deploy_candidate_state <branch> <branch_sha>   echoes CANDIDATE | NOT | UNKNOWN
#
# WHY THIS EXISTS. `merge-pr.sh` refuses while ANY run is in flight on the PR's
# base. That is strictly safe and it costs the programme hours: most in-flight
# runs on `main` are ordinary citations that nobody is about to deploy, and
# cancelling them loses evidence for a commit that will never ship anyway.
# The runs worth protecting are the ones certifying a commit somebody is ABOUT
# TO DEPLOY.
#
# ⚠️ THIS NARROWS A SAFETY GUARD, ON THE DOOR WITH THE WORSE RECORD OF THE TWO.
# The merge side already produced a 3-of-4 citation on a DEPLOYED commit, and a
# run killed at 33m39s that another session was deliberately waiting for. So the
# narrowing is built to be one-directional: it can only ever be MORE permissive
# when it POSITIVELY establishes non-candidacy. Every doubt — a missing library,
# an unreadable tree, a sha that will not resolve, an unrecognised filename —
# returns UNKNOWN, and UNKNOWN keeps today's behaviour exactly.
#
# ⚠️ AND THERE IS NO SECOND MARKER FILE, DELIBERATELY. The obvious design is a
# tracked `DEPLOY-CANDIDATE` file naming a sha. That is a second source of truth
# about deploy intent, and it can disagree with the declaration — somebody
# forgets to write it (fail-open, the dangerous direction) or forgets to clear
# it (fail-closed forever, so it gets deleted in frustration). The §2.5
# DECLARATION already IS the tracked, reviewed, committed statement that a
# specific tree is about to ship. Candidacy is read from it.
#
#   CANDIDATE := a declaration in the BASE BRANCH's tree governs that branch's
#                head — it names the head, or an ancestor with ZERO runtime
#                drift — AND it has no `-JUDGED` companion.
#
# ⚠️ READ FROM THE BASE BRANCH'S TREE, NOT THE WORKING TREE. `merge-pr.sh` runs
# from whatever branch happens to be checked out, and that branch's
# `docs/foundation/deploys/` is not the one the deploy will use. Asking the
# working tree is the right question aimed at the wrong universe.
# ============================================================================

# Must match scripts/lib/declaration.sh. Kept as one string so a future edit
# there is a one-line edit here rather than a silent divergence.
DEPLOY_CANDIDATE_NONRUNTIME_RE='^(docs/|[^/]+\.md$)'

deploy_candidate_state() {
  local branch="${1:-}" sha="${2:-}"
  [ -n "$branch" ] && [ -n "$sha" ] || { echo UNKNOWN; return 0; }

  # A sha that is not a real commit here is a question we cannot answer.
  git rev-parse --verify --quiet "${sha}^{commit}" >/dev/null 2>&1 || { echo UNKNOWN; return 0; }

  local listing
  listing=$(git ls-tree -r --name-only "$sha" -- docs/foundation/deploys 2>/dev/null) || { echo UNKNOWN; return 0; }
  # ⚠️ POSITIVE CONTROL: an empty listing is indistinguishable from a broken
  # query, and one of those means "merge freely". If the directory does not
  # answer at all, we do not get to conclude anything.
  [ -n "$listing" ] || { echo UNKNOWN; return 0; }

  local f base shapart cand drift judged
  while IFS= read -r f; do
    case "$f" in *.md) ;; *) continue ;; esac
    base=$(basename "$f" .md)
    case "$base" in
      README|BASELINE-*|*-JUDGED|*-RETROSPECTIVE|*-backfill-declaration) continue ;;
    esac
    shapart=${base##*-}
    case "$shapart" in ""|*[!0-9a-fA-F]*) continue ;; esac
    [ "${#shapart}" -ge 7 ] || continue
    cand=$(git rev-parse --verify --quiet "${shapart}^{commit}" 2>/dev/null) || continue

    if [ "$cand" != "$sha" ]; then
      git merge-base --is-ancestor "$cand" "$sha" 2>/dev/null || continue
      drift=$(git diff --name-only "$cand" "$sha" -- | grep -Ecv "$DEPLOY_CANDIDATE_NONRUNTIME_RE" || true)
      [ "$drift" -eq 0 ] || continue
    fi

    # It governs. Judged already? Then the deploy it described has been closed
    # out and its runs are nobody's pending citation.
    judged=$(printf '%s\n' "$listing" | grep -cx "docs/foundation/deploys/${base}-JUDGED.md" || true)
    [ "$judged" -eq 0 ] && { echo CANDIDATE; return 0; }
  done <<< "$listing"

  echo NOT
}
