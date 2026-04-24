#!/usr/bin/env bash
# Shared bash helpers for the automated test suite. Source this at the
# top of every script:
#   source "$(dirname "$0")/../lib/common.sh"
#
# Contract:
#   - No script exits on its own — main() decides.
#   - All output is line-based; structured JSON goes to stdout ONLY when
#     $OUTPUT_MODE = "json". Otherwise human-readable colored text.
#   - Every script must produce an array `results[]` of JSON objects with
#     at least: {name, status, durationMs, details?}

set -o pipefail

# --- colors (skipped if not a tty or $NO_COLOR set) -----------------------
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'
  C_BLUE=$'\033[34m'; C_DIM=$'\033[2m'; C_RESET=$'\033[0m'
else
  C_RED=; C_GREEN=; C_YELLOW=; C_BLUE=; C_DIM=; C_RESET=
fi

# --- env loader -----------------------------------------------------------
# Populate from tests/automated/.env.test if present. Scripts can rely on
# variables from that file being defined (even if empty).
load_test_env() {
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  if [[ -f "$root/.env.test" ]]; then
    # shellcheck disable=SC1091
    set -a; source "$root/.env.test"; set +a
  fi
  TEST_MARKETING_URL="${TEST_MARKETING_URL:-https://quillmd.com}"
  TEST_APP_URL="${TEST_APP_URL:-https://app.quillmd.com}"
  TEST_PRO_URL="${TEST_PRO_URL:-https://pro.quillmd.com}"
  SMOKE_DISK_MIN_GB="${SMOKE_DISK_MIN_GB:-5}"
  SMOKE_MEM_MIN_MB="${SMOKE_MEM_MIN_MB:-200}"
  OUTPUT_MODE="${OUTPUT_MODE:-text}"
}

# --- results accumulator --------------------------------------------------
# Usage:
#   record_result "check name" pass 123 "optional detail"
#   record_result "check name" fail 456 "error message"
RESULTS_JSON=()
record_result() {
  local name="$1" status="$2" duration_ms="$3" details="${4:-}"
  local escaped_name escaped_details
  escaped_name=$(json_string "$name")
  escaped_details=$(json_string "$details")
  RESULTS_JSON+=(
    "{\"name\":$escaped_name,\"status\":\"$status\",\"durationMs\":$duration_ms,\"details\":$escaped_details}"
  )

  if [[ "$OUTPUT_MODE" != "json" ]]; then
    local color="$C_GREEN" badge="PASS"
    case "$status" in
      fail) color="$C_RED"; badge="FAIL" ;;
      warn) color="$C_YELLOW"; badge="WARN" ;;
      skip) color="$C_DIM"; badge="SKIP" ;;
    esac
    printf "  %s[%s]%s %-50s %s%4dms%s" \
      "$color" "$badge" "$C_RESET" "$name" "$C_DIM" "$duration_ms" "$C_RESET"
    if [[ -n "$details" ]]; then
      printf " %s%s%s" "$C_DIM" "$details" "$C_RESET"
    fi
    printf "\n"
  fi
}

# --- helpers --------------------------------------------------------------
json_string() {
  # Portable JSON string escape (quotes, backslash, newlines, tabs).
  python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

now_ms() { echo "$(($(date +%s%N) / 1000000))"; }

# --- structured finalizer -------------------------------------------------
# Call at the very end of main() to emit the results either as JSON or as
# a human-readable trailing summary. Returns 1 if any result was "fail".
emit_and_exit() {
  local suite="$1"
  local fail_count=0 pass_count=0 warn_count=0 skip_count=0
  for r in "${RESULTS_JSON[@]}"; do
    case "$r" in
      *\"status\":\"fail\"*) ((fail_count++)) ;;
      *\"status\":\"pass\"*) ((pass_count++)) ;;
      *\"status\":\"warn\"*) ((warn_count++)) ;;
      *\"status\":\"skip\"*) ((skip_count++)) ;;
    esac
  done

  if [[ "$OUTPUT_MODE" == "json" ]]; then
    local joined
    joined=$(IFS=,; echo "${RESULTS_JSON[*]}")
    printf '{"suite":"%s","pass":%d,"fail":%d,"warn":%d,"skip":%d,"results":[%s]}\n' \
      "$suite" "$pass_count" "$fail_count" "$warn_count" "$skip_count" "$joined"
  else
    echo
    if [[ $fail_count -gt 0 ]]; then
      printf "%s→ %s: %d pass, %d fail%s\n" "$C_RED" "$suite" "$pass_count" "$fail_count" "$C_RESET"
    else
      printf "%s→ %s: %d pass%s\n" "$C_GREEN" "$suite" "$pass_count" "$C_RESET"
    fi
  fi

  [[ $fail_count -eq 0 ]]
}
