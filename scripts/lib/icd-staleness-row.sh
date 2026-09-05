#!/usr/bin/env bash
# ============================================================================
# PR #993's DEPLOY ROW — is a stale ICD-10 edition a report, or a refusal?
# ----------------------------------------------------------------------------
#   icd_staleness_verdict <edition_rc> <icd_passenger_count>
#     echoes  pass|<why>   report|<why>   refuse|<why>
#
# ⚠️ PURE, FOR THE SAME REASON THE DEPLOY'S MIGRATION-STRICTNESS DECISION IS.
# The GATHERING is
# a subprocess and a `git diff` against a container label; the DECISION is three
# comparisons. Kept inline it cannot be driven without a deploy, and the only
# way to learn it was wrong is to break one.
#
# THE CLAUSE:
#   · edition current                  -> pass
#   · stale, no ICD changes shipping    -> REPORT. PR #993's own recommendation:
#     a hard gate here reds every lane from today, since it already says DUE at
#     25 days.
#   · stale AND shipping ICD changes    -> REFUSE. Either is survivable alone;
#     together they are new billing behaviour built on a set about to stop being
#     current, and the doctor is who finds out.
#   · passenger UNKNOWN                 -> REPORT, not refuse. Deliberately
#     against the usual fail-closed instinct: the refusal needs BOTH halves, and
#     refusing on an unknown second half would block deploys carrying no ICD
#     change at all — a watcher becoming an outage. The unknown is NAMED.
icd_staleness_verdict() {
  local rc="${1-}" passengers="${2-}"

  case "$rc" in ''|*[!0-9]*) echo "report|the edition check produced no readable exit code ('${rc}') — UNEVALUATED, name it in the declaration"; return 0 ;; esac
  if [ "$rc" -eq 0 ]; then
    echo "pass|the shipped ICD-10 edition is current"; return 0
  fi
  case "$passengers" in
    ''|*[!0-9]*) echo "report|edition NOT current (exit ${rc}), and whether this deploy ships ICD changes is UNKNOWN — the passenger clause is unevaluated"; return 0 ;;
  esac
  if [ "$passengers" -gt 0 ]; then
    echo "refuse|edition NOT current (exit ${rc}) AND this deploy ships ${passengers} ICD file(s) — new billing behaviour on an expiring set"
  else
    echo "report|edition NOT current (exit ${rc}); this deploy carries no ICD changes, so it is recorded and not blocked"
  fi
}
