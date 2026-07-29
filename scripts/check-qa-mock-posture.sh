#!/usr/bin/env bash
# ============================================================================
# Is the QA stack actually incapable of reaching a vendor?
# ----------------------------------------------------------------------------
# IT CHECKS THE RUNNING CONTAINERS, NOT THE COMPOSE FILE, and that distinction
# is the entire reason it exists. On 2026-07-28 docker-compose.qa.yml said
# `MOCK_AI_CALLS: "${MOCK_AI_CALLS:-true}"` and
# `ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY:-mock-key-qa}"` — both of which READ
# as safe. Neither was. `:-` applies only when a variable is UNSET, and
# /opt/meddoc-pro/.env sets both because PRODUCTION needs them. Compose reads
# that same .env. So the "isolated" stack ran with MOCK_AI_CALLS=false, a live
# `sk-ant-api03-…` and a live Deepgram key, and made 298 real Anthropic calls
# plus real Deepgram requests — burning the same balance production depends on,
# for weeks, while the file's own header promised it could not.
#
# TWO INDEPENDENT CONDITIONS, because either alone is a single point of failure:
#
#   1. MOCK_AI_CALLS=true    — no code path tries to call out
#   2. dummy credentials     — and if one does anyway, it fails auth
#
# Condition 2 is what survives a code regression. A new layer, a retry helper or
# a one-off script that forgets the flag is a normal mistake; it should cost an
# auth error, not a vendor bill and a synthetic transcript leaving the box.
#
# READ-ONLY. Never mutates anything.
#
# Usage:  bash scripts/check-qa-mock-posture.sh
# Exit:   0 = mock-only · 1 = LIVE CREDENTIALS OR MOCK OFF · 2 = stack not running
#
# Invoke with `bash scripts/...` — this repo sets core.fileMode=false, so the
# executable bit is not tracked and `./scripts/...` gives "Permission denied".
# ============================================================================
set -uo pipefail

CONTAINERS="meddoc-qa-transcribe-md-1 meddoc-qa-transcribe-md-worker-1"
# Every vendor credential the codebase reads. Keep in step with the compose file
# — a key that is unset today is one .env line away from being real.
KEYS="ANTHROPIC_API_KEY DEEPGRAM_API_KEY OPENAI_API_KEY RESEND_API_KEY"

fail=0
checked=0

for c in $CONTAINERS; do
  if ! docker inspect "$c" >/dev/null 2>&1; then
    echo "⚠️  $c is not running — cannot check"
    continue
  fi
  checked=$((checked + 1))

  mock=$(docker exec "$c" printenv MOCK_AI_CALLS 2>/dev/null || echo "")
  if [ "$mock" = "true" ]; then
    echo "🟢 $c: MOCK_AI_CALLS=true"
  else
    echo "🔴 $c: MOCK_AI_CALLS=${mock:-(unset)} — REAL CALLS ARE POSSIBLE"
    fail=1
  fi

  for k in $KEYS; do
    val=$(docker exec "$c" printenv "$k" 2>/dev/null || echo "")
    if [ -z "$val" ]; then
      # Unset is acceptable — nothing to leak — but say so, because it means
      # this container is relying on absence rather than on a dummy.
      echo "   ⚪ $k unset"
    elif printf '%s' "$val" | grep -qiE '^(qa-)?(dummy|mock|test|ci-dummy)'; then
      echo "   🟢 $k is a dummy"
    else
      # Print a SHORT prefix only. Enough to recognise the vendor, never enough
      # to use — this output goes in reports.
      echo "   🔴 $k LOOKS REAL (${val:0:8}…) — a mock regression could spend it"
      fail=1
    fi
  done
done

if [ "$checked" = "0" ]; then
  echo "⚠️  QA stack is not running — nothing to check"
  exit 2
fi

if [ "$fail" = "0" ]; then
  echo
  echo "🟢 QA mock posture holds — flag true AND credentials severed, in the live containers"
  exit 0
fi

echo
echo "🔴 QA MOCK POSTURE BROKEN. This stack can reach a real vendor."
echo "   Check docker-compose.qa.yml for a \`\${VAR:-default}\` that inherits from"
echo "   the shared .env — that is how this broke before. Then recreate:"
echo "     docker compose -f docker-compose.qa.yml up -d --force-recreate \\"
echo "       --no-deps transcribe-md transcribe-md-worker"
exit 1
