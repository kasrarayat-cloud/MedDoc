# shellcheck shell=bash
# ============================================================================
# citation-state.sh — "what do these runs SAY about this sha?", in one place.
#
# ⚠️ WHY THIS IS A LIB AND NOT A FUNCTION INSIDE `gh-runs.sh`.
#
# Two scripts answer this question and they DRIFTED, which is the whole reason
# this file exists:
#
#   · `check-citation.sh` — produces the citation block a ledger row pastes.
#     It has understood SUPERSESSION since it was written (`:301-309`).
#   · `gh-runs.sh`         — the waiter, and (since ruling #134) the input to
#     `lib/citation-gate.sh`, which gates every production deploy.
#     It did NOT. For as long as both existed they returned OPPOSITE verdicts
#     on the same commit.
#
# `lib/inflight.sh` already exists because a second copy of the in-flight check
# would drift from the first. This is that lesson, applied to the other pair,
# after the drift had already happened rather than before.
#
# ⚠️ IT IS ALSO WHAT MAKES THE BEHAVIOUR TESTABLE. `gh-runs.sh` parses argv and
# reaches the network at load time, so a gate cannot drive its verdict without
# an API. A sourced lib can be handed synthetic rows and asserted on, which is
# what `gate-f26-citation-supersession.test.ts` does.
#
# INPUT  — rows as `[{name,status,conclusion}]`, the shape `gh run list
#          --json name,status,conclusion` produced and `runs-api.sh` still
#          projects back to.
# OUTPUT — a human line on stdout; the verdict is the EXIT CODE.
# ============================================================================

# ⚠️ THREE TERMINAL STATES, NOT TWO — AND THAT IS THE WHOLE FIX.
# This function used to collapse "some runs are still PENDING" and "a run has
# FAILED" into one exit code (1). A caller cannot tell them apart, so the
# canonical `until bash scripts/gh-runs.sh cited "$SHA"` loop polls FOREVER on a
# commit whose run has already concluded `failure` and can never reach 4 of 4.
#
# Measured 2026-08-17 on PR #705: `e2e` concluded FAILURE at 06:59Z
# (npm ECONNRESET in the image build). `cited` printed "3 of 4 success" and
# exited 1 — true, and indistinguishable from three-done-one-running. The waiter
# would have polled until the session ended.
#
# ⚠️ THIS IS THE SECOND TIME THIS SCRIPT COLLAPSED TWO STATES INTO ONE EXIT.
# The first was a fabricated sha vs a real sha with pending runs, fixed above by
# adding 2 = CANNOT TELL. Same author, same file, same shape — which is why the
# states are now enumerated in one place instead of being re-derived per branch.
#
#   0 = CITED       every required workflow carries a success
#   1 = PENDING     at least one run not completed; no live failures — retryable
#   2 = CANNOT TELL no runs, no such commit, broken instrument, timeout
#   3 = FAILED      a workflow concluded non-success and was never re-run —
#                   TERMINAL, will never cite
#
# ⚠️ AND A FOURTH STATE WAS COLLAPSED INTO `3` UNTIL 2026-08-24: A CANCELLED
# RUN THAT A RE-RUN ALREADY REPLACED. See the SUPERSESSION note below. That is
# THREE occurrences of one shape in this one function — which is why the states
# are enumerated here, in a lib, with a gate that drives each of them.
citation_state() {
  local rows="$1" sha="$2" total ok done_ failed wf_total wf_green sup
  total=$(echo "$rows"  | jq -r 'length')
  ok=$(echo "$rows"     | jq -r '[.[]|select(.conclusion=="success")]|length')
  done_=$(echo "$rows"  | jq -r '[.[]|select(.status=="completed")]|length')

  # ⚠️ SUPERSESSION — THE UNIT OF A CITATION IS THE WORKFLOW, NOT THE RUN.
  #
  # A completed non-success run whose WORKFLOW also carries a success on this
  # same sha is DESTROYED EVIDENCE THAT A RE-RUN ALREADY REPLACED. It is not a
  # failure, and it can never become one: nothing about it is retryable,
  # because the retry already happened and passed.
  #
  # `check-citation.sh:301-309` has carried this rule since it was written —
  #     "Without this the normal push-cancels-then-reruns pattern would make
  #      every such commit un-citable."
  # — and `gh-runs.sh` never got it.
  #
  # ⚠️ THE COST IS NOT COSMETIC, BECAUSE RULING #134 PUT THIS FUNCTION ON THE
  # DEPLOY PATH. `lib/citation-gate.sh:44` maps `3 -> REFUSE` and prints "the
  # sha can never reach a full citation", so a commit whose `a11y-ci` was
  # cancelled and re-run to success was PERMANENTLY UNDEPLOYABLE — and the only
  # escape was `--declare-citation-override`, i.e. certifying past a gate on a
  # premise that is false. A waiter that tells you to destroy the evidence it is
  # waiting for is worse than no waiter.
  #
  # ⚠️ AND THE TRIGGER IS ROUTINE, NOT EXOTIC: `gh pr ready` emits
  # `ready_for_review`, `a11y.yml` subscribes to it, and `cancel-in-progress`
  # kills the push-triggered run. Every PR opened as a draft and then converted
  # — the loop's own documented habit, and what produced the reference sha
  # below — lands in this shape.
  #
  # Measured 2026-08-24 on two REAL shas, opposite directions:
  #   f76242c4…  a11y-ci cancelled + a11y-ci success  -> superseded, NOT terminal
  #   82158f90…  CI + e2e cancelled, neither re-run   -> still terminal (unchanged)
  failed=$(echo "$rows" | jq -r '
    ([.[] | select(.conclusion=="success") | .name] | unique) as $green
    | [ .[]
        | select(.status=="completed" and .conclusion!="success")
        | . as $r | select(($green | index($r.name)) == null)
      ] | length')
  sup=$(echo "$rows" | jq -r '
    ([.[] | select(.conclusion=="success") | .name] | unique) as $green
    | [ .[]
        | select(.status=="completed" and .conclusion!="success")
        | . as $r | select(($green | index($r.name)) != null)
      ] | length')
  # The CITED test is per WORKFLOW for the same reason. `ok -eq total` counts
  # RUNS, so a superseded row keeps the two totals apart forever and the verdict
  # falls through to `2` = CANNOT TELL — which #134 also refuses.
  #
  # ⚠️ SO FIXING THE `failed` COUNT ALONE LEAVES THE DEPLOY BLOCKED, ONE STATE
  # OVER. That is the half-landed version of this very fix, and it is the one a
  # tired session lands, because `failed` is where the symptom is visible.
  wf_total=$(echo "$rows" | jq -r '[.[].name] | unique | length')
  wf_green=$(echo "$rows" | jq -r '[.[] | select(.conclusion=="success") | .name] | unique | length')

  # ⚠️ A ZERO-RUN COMMIT IS NOT CITED. Without this, a sha nothing ever ran
  # against reports "all runs succeeded" — vacuously, which is the same
  # false all-clear one layer up.
  total_seen="$total"
  if [ "$total" -lt 1 ]; then
    echo "NOT CITED — no runs exist for $sha (vacuous, not clean)."
    return 2
  fi
  if [ "$sup" -gt 0 ]; then
    echo "$ok of $total success ($wf_green of $wf_total workflows green; $sup superseded by a re-run of the same workflow)"
  else
    echo "$ok of $total success"
  fi
  if [ "$failed" -gt 0 ]; then
    echo "🔴 TERMINAL — $failed of $total concluded NON-SUCCESS with NO success of the" >&2
    echo "   same workflow to supersede them. This sha can NEVER reach a full" >&2
    echo "   citation; waiting on it is an infinite loop. Re-run the failed job" >&2
    echo "   (and SAY WHY in the row — canon forbids re-run-and-hope), or push a" >&2
    echo "   fix. Offending runs:" >&2
    echo "$rows" | jq -r '
      ([.[] | select(.conclusion=="success") | .name] | unique) as $green
      | .[]
      | select(.status=="completed" and .conclusion!="success")
      | . as $r | select(($green | index($r.name)) == null)
      | "     \(.name): \(.conclusion)"' >&2
    return 3
  fi
  # PENDING before CITED: a run still in flight is not answered by the fact
  # that its workflow already carries a green from an earlier attempt. The
  # in-flight one may yet fail, and this is a citation, not an optimism engine.
  [ "$done_" -lt "$total" ] && return 1
  [ "$wf_green" -eq "$wf_total" ] && return 0
  return 2
}
