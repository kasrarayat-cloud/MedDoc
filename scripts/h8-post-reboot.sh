#!/usr/bin/env bash
# ============================================================================
# Phase 6.1 (h8) — reboot test post-reboot append (POST-REBOOT phase)
# ----------------------------------------------------------------------------
# Fires from claude's @reboot user-crontab after the box comes back up.
# Waits for postgres to be healthy, then appends the post-reboot section
# to the pre-existing report file (matched by the timestamp argument
# the pre-reboot script queued).
#
# Self-removes the @reboot crontab line after firing.
# ============================================================================
set -euo pipefail

REPO=/opt/meddoc-pro
PRE_TS="${1:-}"
POST_TS=$(date -u +%Y%m%dT%H%M%SZ)
REPORT_DIR="$REPO/docs/reboot-test-reports"
REPORT="$REPORT_DIR/h8-reboot-${PRE_TS}.md"

if [ -z "$PRE_TS" ]; then
  echo "[h8-post-reboot] no PRE_TS argument; bailing"
  exit 1
fi
if [ ! -f "$REPORT" ]; then
  echo "[h8-post-reboot] report file not found: $REPORT"
  echo "(maybe the pre-reboot script's git push didn't land before reboot — check $REPO/docs/reboot-test-reports/)"
  exit 1
fi

echo "=== H8 POST-REBOOT PHASE — $POST_TS ==="
echo "Pre-reboot timestamp: $PRE_TS"
echo "Report file: $REPORT"

# --- 1. Wait for postgres healthy (up to 5 min) ---
cd "$REPO"
echo "[1] waiting for postgres healthy (up to 5 min)"
for i in $(seq 1 60); do
  s=$(docker compose ps postgres --format '{{.Status}}' 2>/dev/null || true)
  if echo "$s" | grep -qE "\(healthy\)"; then
    echo "    postgres healthy after ${i}*5s"
    break
  fi
  sleep 5
done

# --- 2. Wait a beat for dependent services ---
sleep 30

# --- 3. Capture post-reboot snapshot ---
{
  echo "## ✅ Post-reboot snapshot"
  echo
  echo "**Post-reboot snapshot generated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "**Boot completed:** $(uptime -s)"
  echo
  echo "### Container state"
  echo '```'
  docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>&1
  echo '```'
  echo
  echo "### DB row counts (compare to pre-reboot above)"
  echo '```'
  docker compose -f "$REPO/docker-compose.yml" exec -T postgres \
    psql -U meddoc -d meddoc -A -t -F $'\t' -c "
      SELECT 'transcribe_visits',COUNT(*) FROM transcribe_visits
      UNION ALL SELECT 'transcribe_md_patients',COUNT(*) FROM transcribe_md_patients
      UNION ALL SELECT 'patients',COUNT(*) FROM patients
      UNION ALL SELECT 'users',COUNT(*) FROM users
      UNION ALL SELECT 'ai_calls',COUNT(*) FROM ai_calls
      UNION ALL SELECT 'api_usage_events',COUNT(*) FROM api_usage_events
      ORDER BY 1;" 2>&1
  echo '```'
  echo
  echo "### LUKS state post-reboot"
  echo '```'
  cryptsetup status pg-encrypted 2>&1 | head -10
  echo "---"
  mountpoint /mnt/pgdata-encrypted && df -h /mnt/pgdata-encrypted | tail -1
  echo "---"
  systemctl status pgdata-encrypted.service --no-pager 2>&1 | head -10
  echo '```'
  echo
  echo "### Production HTTP probes"
  echo '```'
  for ep in /login /dashboard /api/health; do
    code=$(curl -sI -m 8 "https://app.quillmd.com$ep" -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
    echo "https://app.quillmd.com$ep -> $code"
  done
  for ep in / /api/health; do
    code=$(curl -sI -m 8 "https://quillmd.com$ep" -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
    echo "https://quillmd.com$ep -> $code"
  done
  echo '```'
  echo
  echo "### Phase 5.2 sentinels still served"
  echo '```'
  CSS_PATH=$(curl -s https://app.quillmd.com/login -m 8 2>/dev/null | grep -oE '/_next/static/chunks/[a-z0-9]+\.css' | tail -1)
  if [ -n "$CSS_PATH" ]; then
    curl -s "https://app.quillmd.com$CSS_PATH" -m 8 2>/dev/null | grep -oE 'qm-lin-coach-grid|qm-lin-coding-rail|qm-lin-em-criterion|qm-lin-card-stream|qm-lin-app' | sort -u
  else
    echo "(could not locate CSS chunk)"
  fi
  echo '```'
  echo
  echo "### Verdict"
  echo
  CONTAINERS_HEALTHY=$(docker compose ps --format '{{.Status}}' 2>/dev/null | grep -c '(healthy)' || echo 0)
  LOGIN_OK=$(curl -sI -m 8 https://app.quillmd.com/login -o /dev/null -w '%{http_code}' 2>/dev/null || echo 000)
  if [ "$CONTAINERS_HEALTHY" -ge 8 ] && [ "$LOGIN_OK" = "200" ]; then
    echo "🟢 **PASS** — LUKS auto-mount + postgres came up cleanly across reboot."
    echo "Containers healthy: $CONTAINERS_HEALTHY/9. /login HTTP $LOGIN_OK."
  else
    echo "🟡 **PARTIAL** — Containers healthy: $CONTAINERS_HEALTHY/9. /login HTTP $LOGIN_OK."
    echo "Investigate before declaring the auto-mount validated."
  fi
  echo
  echo "Boot uptime at snapshot: $(uptime -p)"
} >> "$REPORT"

echo "[3] post-reboot section appended"

# --- 4. Self-remove the @reboot crontab line ---
echo "[4] removing @reboot line from claude user crontab"
( crontab -l 2>/dev/null | grep -v 'h8-post-reboot.sh' ) | crontab -

# --- 5. Commit + push the appended report ---
echo "[5] git commit + push post-reboot section"
cd "$REPO"
git add docs/reboot-test-reports/
git commit -m "report(phase6.1): h8 reboot test — post-reboot snapshot ($PRE_TS)" 2>&1 | tail -3
git push origin main 2>&1 | tail -3

echo "=== H8 POST-REBOOT PHASE COMPLETE — $POST_TS ==="
