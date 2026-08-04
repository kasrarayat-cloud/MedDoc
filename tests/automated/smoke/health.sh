#!/usr/bin/env bash
# tests/automated/smoke/health.sh — the fast post-deploy check.
#
# Covers: public URLs, docker container states, disk, memory.
# Runs in ~5 seconds on a healthy VPS.
#
# Usage:
#   bash tests/automated/smoke/health.sh              # colored text
#   OUTPUT_MODE=json bash .../health.sh               # JSON for runner

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/../lib/common.sh"
load_test_env

main() {
  [[ "$OUTPUT_MODE" != "json" ]] && echo "${C_BLUE}smoke / health${C_RESET}"

  check_url "$TEST_MARKETING_URL"            200
  check_url "$TEST_APP_URL/api/health"       200
  check_url "$TEST_APP_URL/login"            200
  # ⚠️ RETIRED-AND-INVERTED 2026-08-04, DECLARED — these two asserted 200.
  #
  # pro.quillmd.com (the decommissioned MedDoc Pro CRM) was taken OFFLINE on
  # 2026-08-04: it was a publicly reachable, PHI-capable WRITE path into the
  # production clinical database, sharing one DATABASE_URL with the live app,
  # with no owner, no CI and no audits by its own README. Owner ruling — the
  # capability dies now; the code deletion is item A6 in
  # docs/foundation/RELAY.md. Full detail: DEPLOYMENT_RUNBOOK §3.5.
  #
  # The assertions are INVERTED rather than deleted, and that is the point. A
  # deleted check tells you nothing tomorrow; a 410 check tells you the host is
  # still down. If either of these ever reads 200 again, someone has restored a
  # PHI-capable write path — which is exactly the thing worth waking up for.
  check_url "$TEST_PRO_URL/api/health"       410
  check_url "$TEST_PRO_URL/login"            410

  check_containers
  check_disk
  check_memory

  emit_and_exit "smoke-health"
}

check_url() {
  local url="$1" want="$2"
  local t0; t0=$(now_ms)
  local code
  code=$(curl --max-time 10 -sk -o /dev/null -w '%{http_code}' "$url" || echo 000)
  local dur=$(( $(now_ms) - t0 ))
  if [[ "$code" == "$want" ]]; then
    record_result "GET $url" pass "$dur" "→ $code"
  else
    record_result "GET $url" fail "$dur" "expected $want, got $code"
  fi
}

check_containers() {
  local t0; t0=$(now_ms)
  if ! command -v docker >/dev/null 2>&1; then
    record_result "docker containers" skip 0 "docker not installed on this host"
    return
  fi

  # Parse `docker ps` into "name status" lines. Skip anything not under
  # the meddoc-pro project (openclaw etc) so this script is scoped.
  local bad=0 total=0 detail=""
  while IFS=$'\t' read -r name status; do
    [[ "$name" == meddoc-pro-* ]] || continue
    # ⚠️ meddoc-pro-meddoc-pro-1 IS EXPECTED TO BE STOPPED since 2026-08-04.
    # The decommissioned CRM was taken offline deliberately — see the 410
    # assertions above and DEPLOYMENT_RUNBOOK §3.5. Counting it as "bad" would
    # make this smoke fail on every run for an intended state, which is how a
    # real container failure gets waved through.
    #
    # It is EXCLUDED here rather than asserted-stopped because this loop only
    # knows how to say "Up", and the honest 410 assertion above already proves
    # the capability is gone from the outside. When item A6 deletes the
    # service, this branch and the 410 checks go together.
    if [[ "$name" == meddoc-pro-meddoc-pro-* ]]; then
      continue
    fi
    ((total++))
    # "Up X (healthy)" = OK. "Up X" (no healthcheck) = OK.
    # "Up X (unhealthy)" = bad UNLESS it's caddy (known wget-fork issue
    # tracked separately).
    if [[ "$status" == *"(unhealthy)"* ]]; then
      if [[ "$name" == meddoc-pro-caddy-* ]]; then
        continue  # known, ignored
      fi
      ((bad++))
      detail+="$name:unhealthy "
    elif [[ "$status" != Up* ]]; then
      ((bad++))
      detail+="$name:$status "
    fi
  done < <(docker ps -a --format '{{.Names}}	{{.Status}}')

  local dur=$(( $(now_ms) - t0 ))
  if [[ $bad -eq 0 ]]; then
    record_result "docker containers ($total checked, caddy ignored)" pass "$dur"
  else
    record_result "docker containers" fail "$dur" "${detail% }"
  fi
}

check_disk() {
  local t0; t0=$(now_ms)
  # Free space on / in GB (integer, floor).
  local free_gb
  free_gb=$(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
  local dur=$(( $(now_ms) - t0 ))
  if [[ "$free_gb" =~ ^[0-9]+$ && $free_gb -ge $SMOKE_DISK_MIN_GB ]]; then
    record_result "disk ≥ ${SMOKE_DISK_MIN_GB}GB free" pass "$dur" "${free_gb}GB free"
  else
    record_result "disk ≥ ${SMOKE_DISK_MIN_GB}GB free" fail "$dur" "${free_gb:-unknown}GB free"
  fi
}

check_memory() {
  local t0; t0=$(now_ms)
  # `free -m` → MB. MemAvailable column 7 on modern util-linux.
  local free_mb
  free_mb=$(free -m | awk '/^Mem:/ {print $7}')
  local dur=$(( $(now_ms) - t0 ))
  if [[ "$free_mb" =~ ^[0-9]+$ && $free_mb -ge $SMOKE_MEM_MIN_MB ]]; then
    record_result "memory ≥ ${SMOKE_MEM_MIN_MB}MB available" pass "$dur" "${free_mb}MB available"
  else
    record_result "memory ≥ ${SMOKE_MEM_MIN_MB}MB available" fail "$dur" "${free_mb:-unknown}MB available"
  fi
}

main "$@"
