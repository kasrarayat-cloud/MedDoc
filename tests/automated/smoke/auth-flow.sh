#!/usr/bin/env bash
# tests/automated/smoke/auth-flow.sh — transcribe-md login/logout round-trip.
#
# Skips cleanly if TEST_APP_EMAIL / TEST_APP_PASSWORD are not set in
# tests/automated/.env.test (useful during local bootstrap).
#
# The NextAuth v5 credentials flow on app.quillmd.com is:
#   1. GET /api/auth/csrf                 → { csrfToken }
#   2. POST /api/auth/callback/credentials { csrfToken, email, password, callbackUrl }
#      with Cookie: __Host-authjs.csrf-token=… from step 1
#   3. Follow the redirect — success lands on /dashboard with a
#      __Secure-authjs.session-token cookie.
# That's what this script verifies end-to-end.

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/../lib/common.sh"
load_test_env

COOKIES="$(mktemp -t meddoc-auth-cookies.XXXXXX)"
trap 'rm -f "$COOKIES"' EXIT

main() {
  [[ "$OUTPUT_MODE" != "json" ]] && echo "${C_BLUE}smoke / auth-flow${C_RESET}"

  if [[ -z "${TEST_APP_EMAIL:-}" || -z "${TEST_APP_PASSWORD:-}" ]]; then
    record_result "auth-flow" skip 0 "TEST_APP_EMAIL / TEST_APP_PASSWORD not set"
    emit_and_exit "smoke-auth-flow"
    return
  fi

  login
  dashboard_accessible
  logout
  dashboard_gated

  emit_and_exit "smoke-auth-flow"
}

login() {
  local t0; t0=$(now_ms)

  # 1) Prime the CSRF cookie.
  local csrf_json csrf_token
  csrf_json=$(curl -sk --max-time 10 -c "$COOKIES" \
    "$TEST_APP_URL/api/auth/csrf")
  csrf_token=$(printf '%s' "$csrf_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("csrfToken",""))' 2>/dev/null || echo '')

  if [[ -z "$csrf_token" ]]; then
    record_result "login (CSRF)" fail $(( $(now_ms) - t0 )) "couldn't read csrfToken"
    return 1
  fi

  # 2) Post credentials. NextAuth returns a 302; -L would follow into
  # /dashboard, but we want to verify the intermediate state first.
  local code
  code=$(curl -sk --max-time 15 -b "$COOKIES" -c "$COOKIES" \
    -o /dev/null -w '%{http_code}' \
    -X POST "$TEST_APP_URL/api/auth/callback/credentials" \
    --data-urlencode "csrfToken=$csrf_token" \
    --data-urlencode "email=$TEST_APP_EMAIL" \
    --data-urlencode "password=$TEST_APP_PASSWORD" \
    --data-urlencode "callbackUrl=$TEST_APP_URL/dashboard")

  local dur=$(( $(now_ms) - t0 ))
  # 302 = success landing at /dashboard. 200 = form re-rendered → creds bad.
  if [[ "$code" == "302" ]]; then
    record_result "login" pass "$dur" "→ 302 → /dashboard"
  else
    record_result "login" fail "$dur" "expected 302, got $code (creds invalid?)"
    return 1
  fi

  # 3) Confirm the session cookie actually made it into the jar.
  if grep -q 'authjs.session-token' "$COOKIES"; then
    record_result "session cookie set" pass 0
  else
    record_result "session cookie set" fail 0 "no authjs.session-token in cookie jar"
  fi
}

dashboard_accessible() {
  local t0; t0=$(now_ms)
  local code
  code=$(curl -sk --max-time 10 -b "$COOKIES" \
    -o /dev/null -w '%{http_code}' \
    "$TEST_APP_URL/dashboard")
  local dur=$(( $(now_ms) - t0 ))
  if [[ "$code" == "200" ]]; then
    record_result "GET /dashboard (authed)" pass "$dur"
  else
    record_result "GET /dashboard (authed)" fail "$dur" "got $code"
  fi
}

logout() {
  local t0; t0=$(now_ms)
  # Signing out = POST /api/auth/signout with the csrf token + cookie jar.
  local csrf_token
  csrf_token=$(curl -sk --max-time 10 -b "$COOKIES" -c "$COOKIES" \
    "$TEST_APP_URL/api/auth/csrf" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("csrfToken",""))' 2>/dev/null || echo '')
  local code
  code=$(curl -sk --max-time 10 -b "$COOKIES" -c "$COOKIES" \
    -o /dev/null -w '%{http_code}' \
    -X POST "$TEST_APP_URL/api/auth/signout" \
    --data-urlencode "csrfToken=$csrf_token" \
    --data-urlencode "callbackUrl=$TEST_APP_URL/login")
  local dur=$(( $(now_ms) - t0 ))
  if [[ "$code" == "302" || "$code" == "200" ]]; then
    record_result "logout" pass "$dur"
  else
    record_result "logout" fail "$dur" "got $code"
  fi
}

dashboard_gated() {
  local t0; t0=$(now_ms)
  # After logout, /dashboard should 307/302 to /login. NextAuth uses 307
  # server-side redirect today.
  local code
  code=$(curl -sk --max-time 10 -b "$COOKIES" \
    -o /dev/null -w '%{http_code}' \
    "$TEST_APP_URL/dashboard")
  local dur=$(( $(now_ms) - t0 ))
  if [[ "$code" == "302" || "$code" == "307" ]]; then
    record_result "GET /dashboard (unauth) → redirect" pass "$dur" "→ $code"
  else
    record_result "GET /dashboard (unauth) → redirect" fail "$dur" "expected 302/307, got $code"
  fi
}

main "$@"
