#!/usr/bin/env bash
# ============================================================================
# ARE THE REQUIRED CONTEXTS SATISFIED ON THIS SHA?
#   exit 0 = SATISFIED   exit 1 = FAILED   exit 2 = NOT SATISFIED / CANNOT TELL
# ----------------------------------------------------------------------------
# ⚠️ GATE ON THE OBJECT THE GATE READS. Branch protection reads CHECK-RUNS, per
# REQUIRED CONTEXT. It does not read the workflow-run view and it does not care
# how many check-runs exist in total.
#
# ⚠️ AND THE FLOOR IS THE REQUIRED SET, NEVER A TOTAL COUNT. A "7 of 7" floor
# was always the wrong quantity — it counts non-required checks and moves the
# moment a job is added or split. It only became visible when a same-named skip
# arm took the total from 7 to 9. Read the required contexts from protection so
# the floor cannot drift from what actually gates a merge.
#
# ⚠️ TWO-SIDED BY CONSTRUCTION — `skipped` is NON-FAILURE and NON-SATISFYING:
#
#     per required context, SATISFIED  <=>  A SUCCESS EXISTS under that name
#
#   * a skipped arm beside a successful one  -> SATISFIED  (the normal case)
#   * a skipped arm ALONE                    -> NOT SATISFIED  (never "clean")
#   * any failure under the name             -> FAILED, whatever else exists
#
#   The second line is the one that matters: if BOTH arms of a same-named pair
#   ever skip — a predicate bug, a bad `if:` — the context has no success and
#   this refuses. Fail-closed survives the fix.
# ============================================================================
set -uo pipefail

REPO="${REPO:-kasrarayat-cloud/MedDoc}"
SHA="${1:-}"
say() { echo "[required-contexts] $*" >&2; }

[ -z "$SHA" ] && { say "no sha given -> CANNOT TELL"; exit 2; }
[ "${#SHA}" -ne 40 ] && { say "sha is not 40 chars ('$SHA') -> CANNOT TELL (abbreviated ids are never query keys)"; exit 2; }

CTX="$(gh api "repos/$REPO/branches/main/protection" -q '.required_status_checks.contexts[]?' 2>/dev/null)"
[ -z "$CTX" ] && { say "could not read required contexts -> CANNOT TELL"; exit 2; }

RUNS="$(gh api "repos/$REPO/commits/$SHA/check-runs" --paginate -q '.check_runs[]|"\(.name)\t\(.status)\t\(.conclusion // "-")"' 2>/dev/null)"
[ -z "$RUNS" ] && { say "no check-runs on $SHA -> CANNOT TELL (absent is not passing)"; exit 2; }

BAD_CONCL='failure|timed_out|cancelled|action_required|stale'
sat=0; unsat=0; failed=0
while IFS= read -r c; do
  [ -z "$c" ] && continue
  rows="$(printf '%s\n' "$RUNS" | awk -F'\t' -v n="$c" '$1==n')"
  if [ -z "$rows" ]; then say "  $c : ABSENT"; unsat=$((unsat+1)); continue; fi
  if printf '%s\n' "$rows" | awk -F'\t' '{print $3}' | grep -qE "^($BAD_CONCL)$"; then
    say "  $c : FAILED"; failed=$((failed+1)); continue
  fi
  if printf '%s\n' "$rows" | awk -F'\t' '{print $3}' | grep -qx 'success'; then
    say "  $c : satisfied"; sat=$((sat+1))
  else
    st="$(printf '%s\n' "$rows" | awk -F'\t' '{print $2"/"$3}' | tr '\n' ' ')"
    say "  $c : NOT SATISFIED ($st)"; unsat=$((unsat+1))
  fi
done <<< "$CTX"

TOTAL=$(printf '%s\n' "$CTX" | grep -c .)
say "required=$TOTAL satisfied=$sat unsatisfied=$unsat failed=$failed"
# the partition must reconcile, or the classification lost a context
[ $((sat+unsat+failed)) -ne "$TOTAL" ] && { say "PARTITION DOES NOT RECONCILE -> CANNOT TELL"; exit 2; }

[ "$failed" -gt 0 ] && { say "FAILED"; exit 1; }
[ "$unsat" -gt 0 ] && { say "NOT SATISFIED"; exit 2; }
say "SATISFIED — every required context has a success"
exit 0
