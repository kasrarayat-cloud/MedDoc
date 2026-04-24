#!/usr/bin/env bash
# Hit every /api/** route without auth + with bad bodies. Records each
# response code + body excerpt into api-probes/*.json. Not a rate-limit
# stressor — one request per route per test class.

set -uo pipefail
OUT=/opt/meddoc-pro/audit-evidence/api-probes
mkdir -p "$OUT"

probe() {
  local label="$1" method="$2" url="$3" body="${4:-}" ctype="${5:-application/json}"
  local tmp; tmp=$(mktemp)
  local code
  if [[ -n "$body" ]]; then
    code=$(curl --max-time 10 -sk -o "$tmp" -w '%{http_code}' \
      -X "$method" -H "Content-Type: $ctype" --data "$body" "$url" || echo 000)
  else
    code=$(curl --max-time 10 -sk -o "$tmp" -w '%{http_code}' \
      -X "$method" "$url" || echo 000)
  fi
  local bodyhead
  bodyhead=$(head -c 500 "$tmp" | tr '\n' ' ' | sed 's/"/\\"/g')
  printf '{"label":"%s","method":"%s","url":"%s","status":%s,"bodyHead":"%s"}\n' \
    "$label" "$method" "$url" "$code" "$bodyhead" >> "$OUT/results.jsonl"
  printf "  %-40s %s %-50s → %s\n" "$label" "$method" "${url#https://*/}" "$code"
  rm -f "$tmp"
}

: > "$OUT/results.jsonl"
APP="https://app.quillmd.com"
PRO="https://pro.quillmd.com"

echo "=== transcribe-md: unauth probe ==="

# Health endpoints (should be open)
probe "app-health"          GET  "$APP/api/health"

# Auth flows
probe "forgot-pw-valid"     POST "$APP/api/auth/forgot-password" '{"email":"nope@example.test"}'
probe "forgot-pw-empty"     POST "$APP/api/auth/forgot-password" '{}'
probe "forgot-pw-malformed" POST "$APP/api/auth/forgot-password" 'not json'
probe "forgot-pw-xss"       POST "$APP/api/auth/forgot-password" '{"email":"<script>alert(1)</script>"}'
probe "verify-email-empty"  GET  "$APP/api/auth/verify-email"
probe "verify-email-bad"    GET  "$APP/api/auth/verify-email?token=aaaa"
probe "reset-pw-empty"      POST "$APP/api/auth/reset-password" '{}'
probe "reset-pw-bad"        POST "$APP/api/auth/reset-password" '{"token":"xxx","password":"Strong2024Pass"}'

# Patients (authed routes — expect 401/403)
probe "patients-list"       GET  "$APP/api/patients"
probe "patients-search"     GET  "$APP/api/patients?search=test"
probe "patients-by-id"      GET  "$APP/api/patients/clx0000000000"
probe "patients-fuzzy"      POST "$APP/api/patients/fuzzy-match" '{"name":"John Doe","dob":"1970-01-01"}'
probe "patient-export"      GET  "$APP/api/patients/clx0000000000/export"

# Visits
probe "visits-list"         GET  "$APP/api/visits"
probe "visit-detail"        GET  "$APP/api/visits/clx0000000000"
probe "visit-status"        GET  "$APP/api/visits/clx0000000000/status"
probe "visit-audio"         GET  "$APP/api/visits/clx0000000000/audio-upload"
probe "visit-dictation-up"  POST "$APP/api/visits/clx0000000000/dictation/upload" '{"invalid":true}'
probe "visit-dictation-au"  GET  "$APP/api/visits/clx0000000000/dictation/audio"
probe "visit-text-upload"   POST "$APP/api/visits/clx0000000000/text-upload" '{"text":"hello"}'
probe "visit-sign"          POST "$APP/api/visits/clx0000000000/sign" '{}'
probe "visit-export-email"  POST "$APP/api/visits/clx0000000000/export/email" '{"to":"attacker@evil.test"}'
probe "visit-export-pdf"    GET  "$APP/api/visits/clx0000000000/export/pdf"
probe "visit-delete"        DELETE "$APP/api/visits/clx0000000000"
probe "visit-archive"       POST "$APP/api/visits/clx0000000000/archive" '{}'

# Settings
probe "settings-change-pw"  POST "$APP/api/settings/change-password" '{"currentPassword":"x","newPassword":"y"}'
probe "settings-delete-acc" POST "$APP/api/settings/delete-account" '{}'
probe "settings-email"      POST "$APP/api/settings/change-email" '{"email":"x@y.z"}'

# Client errors sink (unauth by design)
probe "client-errors"       POST "$APP/api/client-errors" '{"message":"probe"}'

# Oversized body
BIG=$(python3 -c "print('A' * 6000000)")
probe "oversized-signup"    POST "$APP/api/auth/forgot-password" "{\"email\":\"$BIG\"}"
unset BIG

echo
echo "=== meddoc-pro: unauth probe ==="
probe "pro-health"          GET  "$PRO/api/health"
probe "pro-realtime-sess"   POST "$PRO/api/realtime/session" '{}'
probe "pro-realtime-end"    POST "$PRO/api/realtime/session/end" '{}'
probe "pro-realtime-ctx"    POST "$PRO/api/realtime/refresh-context" '{}'
probe "pro-assistant-tool"  POST "$PRO/api/assistant-tool" '{"tool":"delete_clinical_note","args":{}}'
probe "pro-transcribe"      POST "$PRO/api/transcribe" '{}'
probe "pro-tts"             POST "$PRO/api/tts" '{"text":"hi"}'
probe "pro-doc-editor"      POST "$PRO/api/doc-editor" '{"message":"hi"}'
probe "pro-doc-save"        POST "$PRO/api/doc-editor/save" '{}'
probe "pro-extract-voice"   POST "$PRO/api/patients/extract-from-voice" '{}' 'multipart/form-data'

echo
echo "=== Done — $(wc -l < $OUT/results.jsonl) probes recorded → $OUT/results.jsonl ==="
