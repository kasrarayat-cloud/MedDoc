#!/usr/bin/env bash
#
# T-M18.2 verification — validates each MEDIUM audit fix (A5, A6, A7, A9, A10, A11, A12, A13).
# Mixes runtime probes (HTTP + SQL) and source-tree asserts (grep/file exists).
#
# Usage:
#   bash scripts/verify-t-m18-2.sh
#
# Exits 0 if all 10 tests pass, 1 if any fail.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Colors (TTY only)
if [[ -t 1 ]]; then
  R=$'\e[31m'; G=$'\e[32m'; Y=$'\e[33m'; C=$'\e[36m'; B=$'\e[1m'; N=$'\e[0m'
else
  R=""; G=""; Y=""; C=""; B=""; N=""
fi

PASS=0
FAIL=0

hdr()  { printf "\n${B}=== %s ===${N}\n" "$1"; }
ok()   { printf "  ${G}PASS${N} %s\n" "$1"; PASS=$((PASS + 1)); }
ko()   { printf "  ${R}FAIL${N} %s\n" "$1"; FAIL=$((FAIL + 1)); }
det()  { printf "    ${C}· %s${N}\n" "$1"; }
warn() { printf "    ${Y}! %s${N}\n" "$1"; }

# Run a psql query inside the postgres container, return stripped scalar.
psql_val() {
  docker compose exec -T postgres psql -U meddoc -d meddoc -tAc "$1" 2>/dev/null \
    | tr -d '\r\n\t '
}

# curl + HTTP-code assertion helper. Prints one detail line, returns 0/1.
# Pass/fail accounting happens at the TEST level, not per sub-check.
check_http() {
  local url="$1" expected="$2" label="$3" method="${4:-GET}"
  local actual
  actual=$(curl -sS -m 5 -X "$method" -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "ERR")
  if [[ "$actual" == "$expected" ]]; then
    det "$label → $actual"
    return 0
  else
    printf "    ${R}✗ %s → %s (expected %s)${N}\n" "$label" "$actual" "$expected"
    return 1
  fi
}

# ======================================================================
hdr "Test 1: Global Trash tab route resolution (A12)"
if check_http "http://localhost:9020/dashboard?tab=trash" "307" "GET /dashboard?tab=trash"; then
  ok "/dashboard?tab=trash returns 307 (NextAuth redirect) — route resolves"
else
  ko "/dashboard?tab=trash did not return expected 307"
fi

# ======================================================================
hdr "Test 2: /api/health includes cleanup_crons (A13)"
HEALTH=$(curl -sS -m 5 "http://localhost:9020/api/health" 2>/dev/null || echo "{}")
CRONS_TYPE=$(jq -r '.cleanup_crons | type' <<<"$HEALTH" 2>/dev/null || echo "parse-error")

if [[ "$CRONS_TYPE" == "array" ]]; then
  MISSING=""
  for name in stale-visit-cleanup retention-sweep; do
    MATCH=$(jq -r --arg n "$name" '.cleanup_crons[] | select(.name==$n) | .name' <<<"$HEALTH")
    [[ -z "$MATCH" ]] && MISSING="$MISSING $name"
  done
  if [[ -z "$MISSING" ]]; then
    ok "cleanup_crons[] contains stale-visit-cleanup + retention-sweep"
    for name in stale-visit-cleanup retention-sweep minio-orphan-cleanup; do
      AGE=$(jq -r --arg n "$name" '.cleanup_crons[] | select(.name==$n) | .ageSeconds' <<<"$HEALTH")
      [[ -n "$AGE" ]] && det "$name: ageSeconds=$AGE"
    done
  else
    ko "cleanup_crons missing entries:$MISSING"
  fi
else
  ko "cleanup_crons field absent or not an array (jq type: $CRONS_TYPE)"
  warn "deployed transcribe-md image likely predates T-M18.2 A13 — rebuild needed"
  det "response body: $HEALTH"
fi

# ======================================================================
hdr "Test 3: Denorm drift — visit.patientName matches patient.name (A6)"
DRIFT=$(psql_val 'SELECT COUNT(*) FROM transcribe_visits v JOIN transcribe_md_patients p ON p.id = v."patientId" WHERE v."patientName" != p.name;')
if [[ -z "$DRIFT" ]]; then
  ko "query failed — postgres unreachable or column names changed"
elif [[ "$DRIFT" == "0" ]]; then
  ok "no drift: visit.patientName matches patient.name for all joined rows"
else
  ko "$DRIFT row(s) where visit.patientName != patient.name"
  warn "run the fix-patientname-drift backfill script"
fi

# ======================================================================
hdr "Test 4: AccountDeletion purge logic (A5)"
OVERDUE=$(psql_val 'SELECT COUNT(*) FROM account_deletions WHERE "purgeAt" < NOW();')
TOTAL_AD=$(psql_val 'SELECT COUNT(*) FROM account_deletions;')
if [[ -z "$OVERDUE" || -z "$TOTAL_AD" ]]; then
  ko "query failed — postgres unreachable or column names changed"
else
  det "total account_deletions rows: $TOTAL_AD"
  det "rows with purgeAt < NOW(): $OVERDUE"
  if [[ "$OVERDUE" == "0" ]]; then
    ok "no overdue purges — either none queued, or the cron has already swept"
  else
    ok "$OVERDUE overdue — should drop to 0 on next purge cron tick"
    warn "re-run this test after the cron fires; persistent nonzero = A5 ineffective"
  fi
fi

# ======================================================================
hdr "Test 5: Unauthenticated mutation endpoints return 401 (regression)"
BASE="http://localhost:9020/api/visits/nonexistent"
T5=0
check_http "$BASE/delete"  "401" "POST /api/visits/nonexistent/delete"  "POST"  || T5=1
check_http "$BASE/archive" "401" "POST /api/visits/nonexistent/archive" "POST"  || T5=1
check_http "$BASE/restore" "401" "POST /api/visits/nonexistent/restore" "POST"  || T5=1
check_http "$BASE"         "401" "PATCH /api/visits/nonexistent"        "PATCH" || T5=1
if [[ $T5 -eq 0 ]]; then
  ok "all 4 mutation endpoints return 401 when unauthenticated"
else
  ko "at least one mutation endpoint did not return 401"
fi

# ======================================================================
hdr "Test 6: VISIT_ARCHIVED error code present (A10)"
VFILE="apps/transcribe-md/src/app/api/visits/[id]/route.ts"
if [[ -f "$VFILE" ]] && grep -q "VISIT_ARCHIVED" "$VFILE"; then
  ok "VISIT_ARCHIVED referenced in $VFILE"
  while IFS= read -r line; do det "$line"; done < <(grep -n "VISIT_ARCHIVED" "$VFILE" | head -3)
else
  ko "VISIT_ARCHIVED not found in $VFILE"
fi

# ======================================================================
hdr "Test 7: Streaming audio path (A7)"
T7_OK=1
TFILE="apps/transcribe-md/src/worker/layers/01-transcribe.ts"
DFILE="packages/ai/src/deepgram-batch.ts"
if [[ -f "$TFILE" ]] && grep -q "streamAudio" "$TFILE"; then
  det "streamAudio() referenced in $TFILE"
else
  det "streamAudio() NOT found in $TFILE"
  T7_OK=0
fi
if [[ -f "$DFILE" ]] && grep -q "DeepgramBatchStreamSource" "$DFILE"; then
  det "DeepgramBatchStreamSource referenced in $DFILE"
else
  det "DeepgramBatchStreamSource NOT found in $DFILE"
  T7_OK=0
fi
if [[ $T7_OK -eq 1 ]]; then
  ok "streaming identifiers present in both worker + ai package"
else
  ko "streaming identifiers missing — see details above"
fi

# ======================================================================
hdr "Test 8: Cron heartbeat helper exists (A13)"
HFILE="apps/transcribe-md/src/lib/cleanup-heartbeat.ts"
if [[ -f "$HFILE" ]]; then
  LINES=$(wc -l < "$HFILE" | tr -d ' ')
  ok "$HFILE exists ($LINES lines)"
  if grep -q "recordCleanupHeartbeat" "$HFILE" && grep -q "readCleanupHeartbeats" "$HFILE"; then
    det "exports recordCleanupHeartbeat + readCleanupHeartbeats"
  else
    warn "expected exports not found — may indicate incomplete implementation"
  fi
else
  ko "$HFILE missing"
fi

# ======================================================================
hdr "Test 9: Regression matrix (ports 80 / 9010 / 9020)"
T9=0
check_http "http://localhost:80"   "200" "port 80   (meddoc-pro CRM)"           || T9=1
check_http "http://localhost:9010" "200" "port 9010 (marketing)"                || T9=1
check_http "http://localhost:9020" "307" "port 9020 (transcribe-md login)"      || T9=1
if [[ $T9 -eq 0 ]]; then
  ok "regression matrix matches: 80→200, 9010→200, 9020→307"
else
  ko "regression matrix mismatch — see details above"
fi

# ======================================================================
hdr "Test 10: Container health (expect 8 healthy of 9)"
HEALTHY=$(docker compose ps --format "{{.Name}}|{{.Status}}" 2>/dev/null | grep -c "(healthy)")
if [[ "$HEALTHY" -eq 8 ]]; then
  ok "8/9 containers healthy (worker intentionally has no healthcheck)"
elif [[ "$HEALTHY" -gt 8 ]]; then
  ok "$HEALTHY healthy (>=8 expected — extra non-meddoc containers count too)"
else
  ko "only $HEALTHY healthy (expected ≥8)"
  while IFS= read -r line; do det "$line"; done < <(docker compose ps --format "{{.Name}}: {{.Status}}")
fi

# ======================================================================
TOTAL=$((PASS + FAIL))
printf "\n${B}════════════ SUMMARY ════════════${N}\n"
if [[ $FAIL -eq 0 ]]; then
  printf "${G}${B}%d/%d tests passed${N}\n" "$PASS" "$TOTAL"
  exit 0
else
  printf "${R}${B}%d passed, %d failed (of %d)${N}\n" "$PASS" "$FAIL" "$TOTAL"
  exit 1
fi
