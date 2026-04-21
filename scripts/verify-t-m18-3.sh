#!/usr/bin/env bash
#
# T-M18.3 verification — validates each LOW audit fix (A14–A27).
# Mixes runtime probes (HTTP + SQL) with source/doc greps where the
# fix isn't directly observable at runtime.
#
# Usage:
#   bash scripts/verify-t-m18-3.sh
#
# Exits 0 if all tests pass, 1 if any fail.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

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

psql_val() {
  docker compose exec -T postgres psql -U meddoc -d meddoc -tAc "$1" 2>/dev/null \
    | tr -d '\r\n\t '
}

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
hdr "Test 1: A14 — rate-limiter scale note in KNOWN_ISSUES.md"
if grep -q "KI-4 — Rate limiter buckets are process-local" docs/KNOWN_ISSUES.md; then
  ok "KI-4 entry present in docs/KNOWN_ISSUES.md"
  det "$(grep -n 'KI-4 — Rate limiter' docs/KNOWN_ISSUES.md | head -1)"
else
  ko "KI-4 rate-limiter entry missing from docs/KNOWN_ISSUES.md"
fi

# ======================================================================
hdr "Test 2: A15 — /api/health reports live APP_VERSION (not hardcoded T-M16.3)"
HEALTH=$(curl -sS -m 5 "http://localhost:9020/api/health" 2>/dev/null || echo "{}")
VERSION_STR=$(jq -r '.version // "missing"' <<<"$HEALTH")
if [[ "$VERSION_STR" == "missing" ]]; then
  ko "no .version field in /api/health response"
elif [[ "$VERSION_STR" == "T-M16.3" ]]; then
  ko "version still reads 'T-M16.3' (stale hardcode)"
  warn "Check APP_VERSION is passed through to the transcribe-md container"
else
  ok "version reads '$VERSION_STR' — no longer the T-M16.3 hardcode"
fi
# Also confirm source has the dynamic read
if grep -q "process.env.APP_VERSION" apps/transcribe-md/src/app/api/health/route.ts; then
  det "source: process.env.APP_VERSION reference present"
else
  warn "source does NOT reference process.env.APP_VERSION — runtime check may be coincidental"
fi

# ======================================================================
hdr "Test 3: A16 — reset-password stale 'no rate limiting' comment removed"
if grep -q "No rate limiting here because" apps/transcribe-md/src/app/api/auth/reset-password/route.ts; then
  ko "stale comment still present in reset-password/route.ts"
else
  ok "stale 'No rate limiting' comment no longer present"
fi

# ======================================================================
hdr "Test 4: A17 — redactPhi wraps in lib console.error calls"
T4_FAIL=0
for f in \
  apps/transcribe-md/src/lib/edit-tracking.ts \
  apps/transcribe-md/src/lib/deliveries.ts \
  apps/transcribe-md/src/lib/queue.ts \
  apps/transcribe-md/src/lib/nextauth.ts
do
  if grep -q "redactPhi" "$f"; then
    det "redactPhi used in $f"
  else
    printf "    ${R}✗ redactPhi missing from %s${N}\n" "$f"
    T4_FAIL=1
  fi
done
if [[ $T4_FAIL -eq 0 ]]; then
  ok "all 4 lib files wrap err through redactPhi"
else
  ko "redactPhi missing from at least one lib file"
fi

# ======================================================================
hdr "Test 5: A18 — NextAuth unverified path runs dummy bcrypt"
NFILE="apps/transcribe-md/src/lib/nextauth.ts"
if grep -q "DUMMY_PASSWORD_HASH" "$NFILE" \
  && grep -q "bcrypt.compare(password, DUMMY_PASSWORD_HASH)" "$NFILE"; then
  ok "nextauth.ts runs DUMMY_PASSWORD_HASH compare on unverified branch"
else
  ko "nextauth.ts missing DUMMY_PASSWORD_HASH timing equalizer"
fi

# ======================================================================
hdr "Test 6: A19 — change-email returns identical body for taken + not-taken"
CEFILE="apps/transcribe-md/src/app/api/settings/change-email/route.ts"
if grep -q "GENERIC_OK_BODY" "$CEFILE" \
  && ! grep -q "That address can't be used" "$CEFILE"; then
  ok "change-email emits GENERIC_OK_BODY in both branches; taken-specific 400 removed"
else
  ko "change-email still distinguishes taken-vs-available in response"
fi

# ======================================================================
hdr "Test 7: A20 — loginAction runs dummy bcrypt on non-unverified paths"
AFILE="apps/transcribe-md/src/actions/auth.ts"
if grep -q "DUMMY_PASSWORD_HASH" "$AFILE"; then
  ok "actions/auth.ts imports DUMMY_PASSWORD_HASH timing equalizer"
else
  ko "actions/auth.ts missing DUMMY_PASSWORD_HASH"
fi

# ======================================================================
hdr "Test 8: A21 — /api/visits/[id]/status returns deletedAt + archivedAt"
SFILE="apps/transcribe-md/src/app/api/visits/[id]/status/route.ts"
if grep -q "deletedAt" "$SFILE" && grep -q "archivedAt" "$SFILE"; then
  ok "status/route.ts selects + returns deletedAt + archivedAt"
else
  ko "status/route.ts missing deletedAt/archivedAt"
fi
# Runtime regression — unauth still 401
check_http "http://localhost:9020/api/visits/nonexistent/status" "401" "GET /api/visits/nonexistent/status" "GET" \
  && det "unauth GET still 401 (regression OK)" \
  || warn "unauth GET response changed — inspect"

# ======================================================================
hdr "Test 9: A22 — Profile form no longer shows specialty input"
PF="apps/transcribe-md/src/app/settings/profile-form.tsx"
PA="apps/transcribe-md/src/actions/profile.ts"
T9_FAIL=0
if grep -q "SpecialtyDropdown" "$PF"; then
  printf "    ${R}✗ SpecialtyDropdown still imported/rendered in profile-form.tsx${N}\n"
  T9_FAIL=1
else
  det "SpecialtyDropdown absent from profile-form.tsx"
fi
if grep -q "specialty:" "$PA"; then
  printf "    ${R}✗ specialty: still in UpdateProfileSchema in actions/profile.ts${N}\n"
  T9_FAIL=1
else
  det "specialty field absent from UpdateProfileSchema"
fi
if [[ $T9_FAIL -eq 0 ]]; then
  ok "profile specialty input + schema field both removed"
else
  ko "profile specialty remnants still present"
fi

# ======================================================================
hdr "Test 10: A23 — composite index (userId, deletedAt, archivedAt)"
IDX_A23=$(psql_val "SELECT 1 FROM pg_indexes WHERE tablename='transcribe_visits' AND indexname='transcribe_visits_userId_deletedAt_archivedAt_idx';")
if [[ "$IDX_A23" == "1" ]]; then
  ok "transcribe_visits_userId_deletedAt_archivedAt_idx exists"
else
  ko "transcribe_visits_userId_deletedAt_archivedAt_idx NOT found"
fi

# ======================================================================
hdr "Test 11: A24 — btree index on deletedAt"
IDX_A24=$(psql_val "SELECT 1 FROM pg_indexes WHERE tablename='transcribe_visits' AND indexname='transcribe_visits_deletedAt_idx';")
if [[ "$IDX_A24" == "1" ]]; then
  ok "transcribe_visits_deletedAt_idx exists"
else
  ko "transcribe_visits_deletedAt_idx NOT found"
fi

# ======================================================================
hdr "Test 12: A25 — stale eval/judge ai_calls rows cleaned up"
STALE=$(psql_val "SELECT COUNT(*) FROM ai_calls WHERE purpose IN ('eval','judge');")
if [[ "$STALE" == "0" ]]; then
  ok "0 rows remain with purpose IN ('eval','judge')"
elif [[ -z "$STALE" ]]; then
  ko "query failed — postgres unreachable?"
else
  ko "$STALE stale rows remain — run the T-M18.3 A25 cleanup DELETE again"
fi

# ======================================================================
hdr "Test 13: A26 — retry route uses VISIT_OPS (not UPLOAD)"
RFILE="apps/transcribe-md/src/app/api/visits/[id]/retry/route.ts"
if grep -q "RATE_LIMITS.VISIT_OPS" "$RFILE"; then
  ok "retry route rate-limits with RATE_LIMITS.VISIT_OPS"
  if grep -q "RATE_LIMITS.UPLOAD" "$RFILE"; then
    warn "retry route still references UPLOAD bucket somewhere — inspect"
  fi
else
  ko "retry route does NOT use RATE_LIMITS.VISIT_OPS"
fi

# ======================================================================
hdr "Test 14: A27 — TrashedBanner shares busy state across siblings"
VFILE="apps/transcribe-md/src/app/visits/[id]/visit-lifecycle-actions.tsx"
if grep -q "function TrashedBanner" "$VFILE" \
  && grep -q "const \[busy, setBusy\]" "$VFILE" \
  && grep -q "busy={busy}" "$VFILE" \
  && grep -q "setBusy={setBusy}" "$VFILE"; then
  ok "TrashedBanner lifts busy state; Restore + DeletePermanently share it"
else
  ko "TrashedBanner still lets each button own its own pending"
fi

# ======================================================================
hdr "Test 15: Regression — /api/health shape still OK + ports 80/9010/9020"
T15=0
# Re-assert cleanup_crons still there (T-M18.2 didn't regress)
CRONS_TYPE=$(jq -r '.cleanup_crons | type' <<<"$HEALTH" 2>/dev/null)
if [[ "$CRONS_TYPE" == "array" ]]; then
  det "/api/health still returns cleanup_crons[] (T-M18.2 A13 intact)"
else
  printf "    ${R}✗ /api/health lost cleanup_crons (T-M18.2 regression!)${N}\n"
  T15=1
fi
check_http "http://localhost:80"   "200" "port 80   (meddoc-pro)"      || T15=1
check_http "http://localhost:9010" "200" "port 9010 (marketing)"       || T15=1
check_http "http://localhost:9020" "307" "port 9020 (transcribe-md)"   || T15=1
if [[ $T15 -eq 0 ]]; then
  ok "regression matrix + /api/health shape unchanged"
else
  ko "regression matrix or /api/health shape changed"
fi

# ======================================================================
hdr "Test 16: Regression — container health (expect 8 healthy)"
HEALTHY=$(docker compose ps --format "{{.Name}}|{{.Status}}" 2>/dev/null | grep -c "(healthy)")
if [[ "$HEALTHY" -ge 8 ]]; then
  ok "$HEALTHY healthy (≥8 expected)"
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
