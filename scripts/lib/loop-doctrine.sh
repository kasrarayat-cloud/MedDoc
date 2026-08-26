#!/usr/bin/env bash
# ============================================================================
# THE LOOP RESILIENCE DOCTRINE — owner ruling, 2026-08-26.
# ----------------------------------------------------------------------------
# > THE LOOP IS NEVER DARK EXCEPT IN A TRUE EMERGENCY.
#
# A blocker on ONE work item PARKS THAT ITEM and the loop continues on other
# queue work. The reference case is the GitHub Actions budget wall: refusing to
# spend was correct, going dark was not — merges were blocked, RECON WAS NOT.
#
#   "Never dark on paperwork" generalises to: NEVER DARK ON A SINGLE BLOCKED ITEM.
#
# ⚠️ TWO HALT CLASSES SURVIVE DELIBERATELY, AND THEY ARE NOT EMERGENCIES:
#
#   STOP FILE   — a deliberate operator act. Unchanged.
#   SPINNING    — sessions running and NOTHING landing. The anti-zombie guard:
#                 "a loop that parks every item and continues forever, landing
#                 nothing, is worse than a stopped one BECAUSE IT LOOKS ALIVE."
#
# ⚠️ AND SPINNING IS NOT STARVED — DIFFERENT WORLDS, DIFFERENT WORDS:
#
#   SPINNING  sessions run, no item lands, unparked work REMAINS  -> HALT loudly
#   STARVED   every unparked item is exhausted; all remaining work is parked on
#             owner-class -> exit WAITING-ON-OWNER + ping. NOT a malfunction.
#
# A loop that stops because it has nothing left it is ALLOWED to do has not
# failed; reporting that as a malfunction halt trains everyone to ignore halts.
# ============================================================================
set -uo pipefail

# ── marker classification ────────────────────────────────────────────────────
# CONTINUE | PARK | PARK_OWNER | HALT | EMERGENCY
doctrine_classify_marker() {
  local m="${1:-}"
  case "$m" in
    EMERGENCY:*)                echo "EMERGENCY" ;;
    CONTINUE|"PHASE CLOSED")    echo "CONTINUE" ;;
    # ⚠️ THESE USED TO HALT THE WHOLE LOOP. They are single-ITEM blockers:
    # the item cannot proceed without the owner, every OTHER queue item can.
    "OWNER ACTION"|"RULING NEEDED") echo "PARK_OWNER" ;;
    STOP-CONDITION|PARKED:*)    echo "PARK" ;;
    *)                          echo "UNREADABLE" ;;
  esac
}

# ── emergency probes — STRUCTURED ONLY ───────────────────────────────────────
# ⚠️ NEVER BY PROSE ANALYSIS OF SESSION OUTPUT. An emergency detector that halts
# on RESEMBLANCE recreates the disease this doctrine cures — a loop going dark
# because something *looked* alarming.
#
# ⚠️ THE BIAS IS EXPLICITLY CONSERVATIVE, AND HERE IS THE TRADE:
#   a MISSED exotic emergency still meets the downstream fail-closed gates, the
#   §2.5 declaration gate, merge-pr.sh, the pre-push hook and the permission
#   layer — several independent nets.
#   a FALSE-POSITIVE detector halts the loop weekly on phantoms, and a halt
#   nobody trusts is a halt nobody reads.
# So: detect only what can be MEASURED, and let the nets catch the rest.
#
# exit 0 = clear · exit 1 = EMERGENCY (prints the class)
doctrine_emergency_probe() {
  local compose="${1:-/opt/meddoc-pro/docker-compose.yml}"

  # (iii) production down — container state is structure, not prose
  if command -v docker >/dev/null 2>&1 && [ -f "$compose" ]; then
    local total unhealthy
    # ⚠️ NO `|| echo 0`. `grep -c` PRINTS 0 and EXITS 1 on no-match, so the
    # fallback fires TOO and the variable becomes "0\n0" — which then errors in
    # `[ ]` and silently takes the else branch. The first draft of this probe had
    # exactly that bug and reported CLEAR on a stack it never measured: a false
    # green from the very trap this repo files as canon. `wc -l` always exits 0
    # and always prints one number.
    total="$(docker compose -f "$compose" ps --format '{{.Service}}' 2>/dev/null | grep -c . )" || total=0
    total="$(printf '%s' "$total" | tr -dc '0-9')"; total="${total:-0}"
    if [ "$total" -gt 0 ]; then
      unhealthy="$(docker compose -f "$compose" ps --format '{{.State}}' 2>/dev/null | grep -vE '^running$' | wc -l)"
      unhealthy="$(printf '%s' "$unhealthy" | tr -dc '0-9')"; unhealthy="${unhealthy:-0}"
      # ⚠️ A THRESHOLD, NOT A SINGLE CONTAINER. One restarting sidecar is not an
      # outage; the whole stack down is. A one-container trigger would fire on
      # every routine recreate.
      if [ "$unhealthy" -ge "$(( (total + 1) / 2 ))" ]; then
        echo "iii:production-down (${unhealthy}/${total} services not running)"; return 1
      fi
    fi
  fi
  return 0
}

# ── progress verdict — SPINNING vs STARVED ───────────────────────────────────
# args: <ledger_moved 0|1> <consecutive_no_progress> <unparked_items_remaining>
# echoes: OK | SPINNING | STARVED
doctrine_progress_verdict() {
  local moved="${1:-0}" streak="${2:-0}" unparked="${3:-1}"
  if [ "$moved" = "1" ]; then echo "OK"; return 0; fi
  if [ "$streak" -lt 2 ]; then echo "OK"; return 0; fi
  # nothing landed twice running. WHICH WORLD?
  if [ "${unparked:-1}" -le 0 ]; then echo "STARVED"; else echo "SPINNING"; fi
}
