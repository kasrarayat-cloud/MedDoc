#!/usr/bin/env bash
# ============================================================================
# Phase 5.2 — 48h cache verification (one-shot)
# ----------------------------------------------------------------------------
# Runs ~48h after the 2026-05-02 Phase 5.2 deploy. Queries the Anthropic
# usage telemetry on the prod postgres for purpose='judge' rows and
# computes whether the prompt cache is actually engaging.
#
# Schema reality (checked 2026-05-02): neither ai_calls nor
# api_usage_events stores the SDK's cache_creation_input_tokens or
# cache_read_input_tokens fields directly. We use input_tokens as the
# cache-engagement proxy:
#
#   With cache_control engaged:    Anthropic's response.usage.input_tokens
#                                  excludes both cached AND created
#                                  tokens, so a call that includes the
#                                  ~2.6K-token rubric system prompt
#                                  returns input_tokens ≈ user-prompt
#                                  size only (~500-1500).
#   With cache_control NOT engaged: input_tokens = system + user
#                                  ≈ 3000-4500 every time.
#
# So avg(inputTokens) << 2000 → cache engaging. avg(inputTokens) >> 2500 →
# cache silently broken.
#
# Verdict thresholds:
#   🟢  avg input < 1800 (cache engaging) AND avg cost ≤ $0.012/call
#   🟡  avg input 1800-2500 OR cost > 1.5x typical-cache-engaged baseline
#   🔴  avg input ≥ 2500 (cache NOT engaging — full system prompt billed
#                         every call → silent fail of the Phase 5.2 fix)
#
# Cost projection caveat: per-API-call cost ~$0.008 is normal even WITH
# cache because output tokens dominate ($15/MTok × ~400 = $0.006). The
# weighted cost projection of $0.001-0.003/visit assumed Redis cache
# hits skipping the API entirely (key = SHA-256 of normalized SOAP, 7d
# TTL). At low traffic (~6 calls/day post-deploy) Redis warmth is low.
#
# After firing once, the script removes its own crontab entry so the
# cron job doesn't accumulate.
# ============================================================================
set -euo pipefail

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

REPO=/opt/meddoc-pro
TS_UTC=$(date -u +%Y%m%dT%H%M%SZ)
REPORT_DIR="$REPO/docs/cache-verify-reports"
REPORT_FILE="$REPORT_DIR/cache-verify-${TS_UTC}.md"
LOG_FILE=/tmp/quillmd-cache-verify-${TS_UTC}.log

if [ "$DRY_RUN" = "1" ]; then
  REPORT_FILE=/tmp/cache-verify-dryrun.md
  LOG_FILE=/tmp/cache-verify-dryrun.log
fi

mkdir -p "$REPORT_DIR"

cd "$REPO"

# --- 1. Pull telemetry ----------------------------------------------------

# Use a single SQL query that returns one row of aggregates, tab-separated.
# Schema source of truth: api_usage_events (jsonb metadata + native cols).
# Dollar amounts come from totalCostUsd which the buildAnthropicUsage helper
# computes at log time.
SQL=$(cat <<'EOSQL'
SELECT
  COUNT(*)::text                                                        AS total_calls,
  COALESCE(SUM(CASE WHEN "inputTokens" < 1500 THEN 1 ELSE 0 END), 0)::text AS warm_calls,
  COALESCE(SUM(CASE WHEN "inputTokens" >= 2500 THEN 1 ELSE 0 END), 0)::text AS cold_calls_full_system,
  COALESCE(ROUND(AVG("inputTokens")::numeric, 1)::text, '0')              AS avg_input_tokens,
  COALESCE(ROUND(AVG("outputTokens")::numeric, 1)::text, '0')             AS avg_output_tokens,
  COALESCE(MIN("inputTokens")::text, '0')                                  AS min_input,
  COALESCE(MAX("inputTokens")::text, '0')                                  AS max_input,
  COALESCE(ROUND(AVG((metadata->>'latencyMs')::int)::numeric, 0)::text, '0') AS avg_latency_ms,
  COALESCE(ROUND(AVG("totalCostUsd")::numeric, 6)::text, '0')              AS avg_cost_per_call,
  COALESCE(ROUND(SUM("totalCostUsd")::numeric, 4)::text, '0')              AS total_48h_cost,
  COALESCE(MIN("timestamp")::text, 'n/a')                                   AS first_call,
  COALESCE(MAX("timestamp")::text, 'n/a')                                   AS last_call
FROM api_usage_events
WHERE provider='anthropic'
  AND operation='judge'
  AND "timestamp" > NOW() - INTERVAL '48 hours';
EOSQL
)

ROW=$(docker compose -f "$REPO/docker-compose.yml" exec -T postgres \
  psql -U meddoc -d meddoc -A -F $'\t' -t -v ON_ERROR_STOP=1 -c "$SQL" 2>&1)

# Tab-split into vars
IFS=$'\t' read -r TOTAL_CALLS WARM_CALLS COLD_CALLS AVG_INPUT AVG_OUTPUT \
  MIN_INPUT MAX_INPUT AVG_LATENCY AVG_COST TOTAL_COST FIRST_CALL LAST_CALL \
  <<<"$ROW"

# --- Per-hour breakdown for the report's appendix ------------------------
HOURLY_SQL=$(cat <<'EOSQL'
SELECT
  DATE_TRUNC('hour', "timestamp")::text             AS hour,
  COUNT(*)::text                                     AS calls,
  COALESCE(ROUND(AVG("inputTokens")::numeric, 0)::text, '0')   AS avg_in,
  COALESCE(ROUND(AVG("totalCostUsd")::numeric, 4)::text, '0')  AS avg_cost
FROM api_usage_events
WHERE provider='anthropic'
  AND operation='judge'
  AND "timestamp" > NOW() - INTERVAL '48 hours'
GROUP BY hour
ORDER BY hour DESC;
EOSQL
)
HOURLY=$(docker compose -f "$REPO/docker-compose.yml" exec -T postgres \
  psql -U meddoc -d meddoc -A -F $'\t' -t -v ON_ERROR_STOP=1 -c "$HOURLY_SQL" 2>&1 || echo "(hourly query failed)")

# --- 2. Verdict ----------------------------------------------------------

# Bash arithmetic doesn't handle decimals; route via awk.
verdict() {
  local total=$1 avg_in=$2 cold=$3 cost=$4
  if [ "$total" -eq 0 ]; then
    echo '🟡 NO_DATA — zero judge calls in last 48h. Either nobody opened a SOAP tab, or the engine is still falling back to deterministic-only.'
    return
  fi
  awk -v ai="$avg_in" -v cold="$cold" -v cost="$cost" -v total="$total" 'BEGIN {
    if (cold > 0 && cold == total) {
      print "🔴 CACHE NOT ENGAGING — every call shows full system prompt in input_tokens (≥2500). Anthropic prompt cache silently broken. URGENT: rubric tokens may have dropped below ~2048 threshold OR cache_control attribute lost during a redeploy. Investigate via /opt/meddoc-pro/apps/transcribe-md/scripts/llm-mdm-smoke.ts."
    } else if (ai >= 2500) {
      print "🔴 CACHE NOT ENGAGING — average input_tokens (" ai ") indicates the system prompt is being billed every call. URGENT: same investigation as above."
    } else if (ai < 1800 && cost <= 0.012) {
      print "🟢 CACHE ENGAGING — average input_tokens (" ai ") well below the 2500 threshold; system prompt is being cached on the Anthropic side. Cost ($" cost "/call) consistent with cache-engaged baseline."
    } else if (ai < 2500) {
      print "🟡 CACHE PARTIAL — average input_tokens (" ai ") below the 2500 cliff but above the 1800 confidence band, OR cost slightly elevated ($" cost "/call). Cache is engaging on most calls but watch the next 7-day window for trend."
    } else {
      print "🟡 INDETERMINATE — review the per-hour breakdown manually."
    }
  }'
}

VERDICT=$(verdict "$TOTAL_CALLS" "$AVG_INPUT" "$COLD_CALLS" "$AVG_COST")

# Cost-vs-projection note
COST_NOTE=$(awk -v c="$AVG_COST" 'BEGIN {
  if (c == 0) { print "no calls — n/a"; exit }
  if (c <= 0.003) { print "below projection ($0.001-0.003) — Redis cache likely warmed"; exit }
  if (c <= 0.010) { print "consistent with cache-engaged API path; Redis cache underweighted at this traffic level"; exit }
  if (c <= 0.020) { print "elevated — Redis hit rate low (expected at low-traffic; trend should improve at 7d)"; exit }
  print "high — flag for investigation"
}')

# --- 3. Write report -----------------------------------------------------

cat > "$REPORT_FILE" <<EOREPORT
# Phase 5.2 — 48h Cache Verification — ${TS_UTC}

**Generated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Window:** 48 hours preceding generation
**Source:** api_usage_events (provider='anthropic', operation='judge')
**Deploy reference:** Phase 5.2 shipped 2026-05-02T21:18Z (merge SHA 7f8e351, tag phase-5.2-soap-coding-coach)

## Verdict

${VERDICT}

## Aggregates (last 48h)

| Metric | Value |
|---|---|
| Total judge calls | ${TOTAL_CALLS} |
| Warm calls (input_tokens < 1500) | ${WARM_CALLS} |
| Cold calls full-system (input_tokens ≥ 2500) | ${COLD_CALLS} |
| Avg input tokens | ${AVG_INPUT} |
| Avg output tokens | ${AVG_OUTPUT} |
| Min input / Max input | ${MIN_INPUT} / ${MAX_INPUT} |
| Avg latency (ms) | ${AVG_LATENCY} |
| Avg cost / call | \$${AVG_COST} |
| Total 48h API cost | \$${TOTAL_COST} |
| First call | ${FIRST_CALL} |
| Last call | ${LAST_CALL} |

## Cost-vs-projection

Per-call API cost: \$${AVG_COST} — ${COST_NOTE}

The \$0.001-0.003/visit projection in PR #94 assumed Redis cache hits dominating (skipping the API call entirely). At low post-deploy traffic the API path runs more often than the eventual steady state will see; this number should drop over the next 7-day window as Redis warms.

## Methodology note

Neither \`ai_calls\` nor \`api_usage_events\` stores Anthropic SDK \`cache_creation_input_tokens\` / \`cache_read_input_tokens\` directly. The script uses the input_tokens distribution as the cache-engagement proxy: with \`cache_control\` engaged, Anthropic's response.usage.input_tokens excludes the cached system prompt entirely, so a call that includes the ~2.6K-token rubric returns input_tokens ≈ user-prompt size only (~500-1500). With cache_control NOT engaged, input_tokens = system + user ≈ 3000-4500 every time. The 2500-token threshold was chosen as the unambiguous "all system tokens billed" boundary.

If a future need wants direct cache stats, extend \`buildAnthropicUsage\` in \`packages/ai/src/api-usage.ts\` to thread \`response.usage.cache_creation_input_tokens\` and \`cache_read_input_tokens\` into the metadata jsonb, and patch the call site in \`apps/transcribe-md/src/lib/em-coding/llm-mdm.ts\`.

## Hourly breakdown

| Hour (UTC) | Calls | Avg input tokens | Avg cost (\$) |
|---|---|---|---|
$(echo "$HOURLY" | awk -F'\t' 'NF==4 {printf "| %s | %s | %s | %s |\n", $1, $2, $3, $4}')

EOREPORT

# --- 4. Commit + push ----------------------------------------------------

if [ "$DRY_RUN" = "0" ]; then
  cd "$REPO"
  # Avoid noisy commits if branch isn't main (e.g. mid-feature)
  CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
  if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "WARN: not on main (currently $CURRENT_BRANCH); committing report anyway but you may want to cherry-pick to main"
  fi
  git add "$REPORT_FILE"
  # Append §11.5 to POST_MERGE_TODO.md if not already there for this run
  if ! grep -q "11.5 Phase 5.2 — 48h cache verification" docs/POST_MERGE_TODO.md 2>/dev/null; then
    {
      echo ""
      echo "## 11.5 Phase 5.2 — 48h cache verification"
      echo ""
      echo "Verdict: ${VERDICT}"
      echo ""
      echo "Total judge calls: ${TOTAL_CALLS}  |  Cache-engaged calls: ${WARM_CALLS}  |  Cold (full-system): ${COLD_CALLS}"
      echo "Avg input/output tokens: ${AVG_INPUT}/${AVG_OUTPUT}  |  Avg latency: ${AVG_LATENCY}ms"
      echo "Avg cost per call: \$${AVG_COST}  |  Total 48h cost: \$${TOTAL_COST}"
      echo ""
      echo "Full report: \`docs/cache-verify-reports/cache-verify-${TS_UTC}.md\`."
    } >> docs/POST_MERGE_TODO.md
    git add docs/POST_MERGE_TODO.md
  fi
  # Get verdict emoji for commit message
  VERDICT_EMOJI=$(echo "$VERDICT" | grep -oE '🟢|🟡|🔴' | head -1)
  git commit -m "report(phase5.2): 48h cache verification — ${VERDICT_EMOJI}

Total judge calls: ${TOTAL_CALLS}
Cache-engaged calls: ${WARM_CALLS}
Cold (full-system): ${COLD_CALLS}
Avg input/output tokens: ${AVG_INPUT}/${AVG_OUTPUT}
Avg latency: ${AVG_LATENCY}ms
Avg cost per call: \$${AVG_COST}
Total 48h API cost: \$${TOTAL_COST}

Full report: docs/cache-verify-reports/cache-verify-${TS_UTC}.md
Methodology: input_tokens proxy (cache stats not directly persisted)." 2>&1 | tail -5

  git push origin "$CURRENT_BRANCH" 2>&1 | tail -3
fi

# --- 5. Self-remove cron (only on real run, not dry-run) -----------------

if [ "$DRY_RUN" = "0" ]; then
  ( crontab -l 2>/dev/null | grep -v 'cache-verify-48h.sh' ) | crontab - || true
  echo "cron entry removed; this script will not auto-fire again"
fi

# --- 6. Logfile + final stdout ------------------------------------------

echo "==="
echo "Verdict: $VERDICT"
echo "Report: $REPORT_FILE"
echo "Total calls: $TOTAL_CALLS  |  Avg input: $AVG_INPUT  |  Avg cost: \$$AVG_COST"
echo "==="

if [ "$DRY_RUN" = "1" ]; then
  echo
  echo "[dry-run] No commit, no push, no cron-removal performed."
  echo "[dry-run] To run for real: $0   (no flags)"
fi
