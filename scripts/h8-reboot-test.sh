#!/usr/bin/env bash
# ============================================================================
# Phase 6.1 (h8) — reboot test orchestrator (PRE-REBOOT phase)
# ----------------------------------------------------------------------------
# Fires once at 2026-05-03T04:00 UTC from /etc/cron.d/quillmd-reboot-test
# (running as root). Captures a pre-reboot snapshot, takes an insurance
# pg_dump, schedules a deferred reboot, queues a @reboot user-crontab line
# that runs the post-reboot append script, and self-removes its own cron
# entry.
#
# Why two scripts (pre + post): the cron entry runs as root because
# `shutdown -r` requires root. The post-reboot append step doesn't need
# root and runs cleaner from claude's user crontab so git operations
# stay in claude's commit identity. The post-reboot script self-removes
# its own @reboot line after firing.
# ============================================================================
set -euo pipefail

REPO=/opt/meddoc-pro
TS=$(date -u +%Y%m%dT%H%M%SZ)
REPORT_DIR="$REPO/docs/reboot-test-reports"
REPORT="$REPORT_DIR/h8-reboot-${TS}.md"
DUMP="$REPO/backups/migration/pre-reboot-${TS}.dump"
TMP_DUMP="/tmp/pre-reboot-${TS}.dump"

mkdir -p "$REPORT_DIR"

echo "=== H8 REBOOT TEST PRE-PHASE — $TS ==="

# --- 1. Pre-reboot snapshot ---
{
  echo "# Phase 6.1 (h8) — reboot test report — ${TS}"
  echo
  echo "**Pre-reboot snapshot generated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "## ⏸ Pre-reboot snapshot"
  echo
  echo "### Container state"
  echo '```'
  cd "$REPO" && docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>&1
  echo '```'
  echo
  echo "### DB row counts"
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
  echo "### Production HTTP probes"
  echo '```'
  for ep in /login /dashboard; do
    code=$(curl -sI -m 8 "https://app.quillmd.com$ep" -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
    echo "https://app.quillmd.com$ep -> $code"
  done
  echo '```'
  echo
  echo "### Host uptime + LUKS state pre-reboot"
  echo '```'
  uptime
  echo "---"
  cryptsetup status pg-encrypted 2>&1 | head -10
  echo "---"
  mountpoint /mnt/pgdata-encrypted && df -h /mnt/pgdata-encrypted | tail -1
  echo '```'
  echo
  echo "### Insurance dump"
  echo "Created: \`$DUMP\` (full pg_dump custom format, taken right before reboot)"
  echo
  echo "---"
  echo
  echo "**Reboot scheduled:** \`shutdown -r +1\` issued at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "**Expected sequence on cold boot:**"
  echo "1. systemd activates \`pgdata-encrypted.service\` (Before=docker.service)"
  echo "2. Service opens \`/dev/mapper/pg-encrypted\` with the keyfile + mounts \`/mnt/pgdata-encrypted\`"
  echo "3. Docker daemon starts; postgres container bind-mounts the now-decrypted volume"
  echo "4. claude's @reboot user-crontab fires \`h8-post-reboot.sh\` to append the post-reboot section to this report and commit"
  echo
  echo "## ⏳ Post-reboot snapshot — pending"
  echo
  echo "(The post-reboot script will append container state, row counts, /api/health, uptime, and a verdict here once the box is healthy after reboot.)"
} > "$REPORT"

echo "[1] pre-reboot report written to $REPORT"

# --- 2. Insurance dump ---
echo "[2] taking insurance pg_dump"
docker compose -f "$REPO/docker-compose.yml" exec -T postgres \
  pg_dump -U meddoc -d meddoc -Fc --no-owner --no-acl > "$TMP_DUMP"

# Move to persistent location with backup-tree perms
install -o dnsmasq -g systemd-journal -m 0640 "$TMP_DUMP" "$DUMP"
rm -f "$TMP_DUMP"
ls -la "$DUMP"

# --- 3. Queue @reboot post-reboot append in claude's crontab ---
echo "[3] adding @reboot line to claude user crontab"
sudo -u claude bash -c "( crontab -l 2>/dev/null | grep -v 'h8-post-reboot.sh' ; echo '@reboot /opt/meddoc-pro/scripts/h8-post-reboot.sh ${TS} > /tmp/h8-post-reboot.log 2>&1' ) | crontab -"
sudo -u claude crontab -l | tail -3

# --- 4. Commit + push pre-reboot report (as claude so commit identity is right) ---
echo "[4] git commit + push pre-reboot report"
sudo -u claude bash -c "cd $REPO && git add docs/reboot-test-reports/ && git commit -m 'report(phase6.1): h8 reboot test — pre-reboot snapshot ($TS)' && git push origin main" 2>&1 | tail -5

# --- 5. Self-remove the cron entry that triggered this run ---
echo "[5] removing /etc/cron.d/quillmd-reboot-test (self-strip)"
rm -f /etc/cron.d/quillmd-reboot-test

# --- 6. Schedule deferred reboot ---
echo "[6] scheduling reboot via shutdown -r +1 (60-second delay)"
shutdown -r +1 "Phase 6.1 h8 reboot test — scheduled validation of LUKS auto-mount"

echo "=== H8 PRE-REBOOT PHASE COMPLETE — reboot in 1 min ==="
