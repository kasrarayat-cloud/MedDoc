#!/usr/bin/env bash
# ============================================================================
# Post-reboot proof — the one property a hand-started unit cannot demonstrate.
# ----------------------------------------------------------------------------
# Both PHI stores are unlocked at boot by systemd units ordered
# `Before=docker.service`, and both containers now FAIL CLOSED if their volume
# is missing. Those two facts together mean a boot-ordering race no longer
# corrupts anything — it just takes the stack down. That is the right trade, but
# it is only a trade if the ordering actually works, and starting a unit by hand
# proves nothing about ordering.
#
# So this runs AFTER a real reboot and asserts the whole chain:
#
#   units started at boot → mappings open → mounts live on the dm devices →
#   Postgres and MinIO healthy ON those devices → guards intact → app up →
#   co-tenants up
#
# It also checks the two KNOWN side effects of a reboot on this host, because
# they are expected and should be handled as part of the proof rather than
# discovered as surprises:
#
#   - the QA stack does NOT self-restart (prod does)
#   - a stale `@reboot` cron dirties the working tree
#
# READ-ONLY. Reports; never fixes. Fixing is a decision.
#
# Usage:  bash scripts/verify-post-reboot.sh
# Exit:   0 = everything came back · 1 = something did not
# ============================================================================
set -uo pipefail

inhost() {
  docker run --rm --privileged --ipc=host --pid=host -v /:/host \
    alpine chroot /host bash -c "$1" 2>/dev/null
}

fail=0
note() { printf '   %s\n' "$1"; }
bad()  { printf '🔴 %s\n' "$1"; fail=1; }

echo "── uptime ──────────────────────────────────────────────────────────"
inhost "uptime -p; echo 'booted: '\$(uptime -s)"
echo

echo "── 1. the units started AT BOOT, not by hand ───────────────────────"
# THE ASSERTION THIS WHOLE SCRIPT EXISTS FOR, and the first draft got it wrong:
# it printed the two timestamps with a comment telling the reader to compare
# them, and passed either way. A hand-started unit reads `active` exactly like a
# boot-started one — which is the ONE case this proof is meant to catch — so a
# check that only displays the values is decorative. Caught on the dry-run,
# where miniodata-encrypted had been started by hand two days after boot and
# condition 1 went green.
#
# So: compare in the script, and fail on drift. A unit ordered
# Before=docker.service lands within seconds of boot; anything past the grace
# window was started by a human and proves nothing about ordering.
BOOT_GRACE=120
boot_epoch=$(inhost "date -d \"\$(uptime -s)\" +%s")
for u in pgdata-encrypted miniodata-encrypted; do
  st=$(inhost "systemctl is-active $u.service")
  since=$(inhost "systemctl show -p ActiveEnterTimestamp --value $u.service")
  if [ "$st" != "active" ]; then
    bad "$u.service is '$st' after boot — Before=docker.service did not hold"
    continue
  fi
  since_epoch=$(inhost "date -d '$since' +%s" 2>/dev/null)
  if [ -z "$since_epoch" ] || [ -z "$boot_epoch" ]; then
    bad "$u.service: could not parse start time ('$since') — cannot prove it started at boot"
    continue
  fi
  delta=$(( since_epoch - boot_epoch ))
  if [ "$delta" -lt 0 ] || [ "$delta" -gt "$BOOT_GRACE" ]; then
    bad "$u.service started ${delta}s after boot (grace ${BOOT_GRACE}s) — that is a HAND START, not boot ordering. This proof is invalid until the host is actually rebooted."
  else
    note "🟢 $u.service started ${delta}s after boot — boot ordering held"
  fi
done
echo

echo "── 2. mappings + mounts ────────────────────────────────────────────"
inhost "lsblk -o NAME,TYPE,FSTYPE,MOUNTPOINT | grep -E 'loop|crypt' || echo '(no crypt devices!)'"
for m in /mnt/pgdata-encrypted /mnt/miniodata-encrypted; do
  s=$(inhost "findmnt -no SOURCE $m")
  [ -n "$s" ] && note "🟢 $m ← $s" || bad "$m is NOT mounted"
done
echo

echo "── 3. the stores are on those devices (the real check) ─────────────"
for s in check-pg-encrypted-mount check-minio-encrypted-mount; do
  if bash "$(dirname "$0")/$s.sh" >/tmp/prb 2>&1; then
    note "🟢 $s → 0"
  else
    bad "$s → $? "; sed 's/^/      /' /tmp/prb
  fi
done
rm -f /tmp/prb
echo

echo "── 4. prod stack ───────────────────────────────────────────────────"
unhealthy=$(docker ps -a --filter "name=meddoc-pro-" --format '{{.Names}} {{.Status}}' | grep -viE "healthy|Up [0-9]" || true)
if [ -n "$unhealthy" ]; then bad "prod containers not healthy:"; echo "$unhealthy" | sed 's/^/      /'
else note "🟢 every meddoc-pro container is up"; fi
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 https://quillmd.com || echo 000)
[ "$code" = "200" ] && note "🟢 quillmd.com → 200" || bad "quillmd.com → $code"
echo

echo "── 5. co-tenants (this host is shared) ─────────────────────────────"
for p in leathererp voiceassistmain openclaw; do
  n=$(docker ps --filter "name=$p" --format '{{.Names}}' | wc -l)
  [ "$n" -gt 0 ] && note "🟢 $p: $n container(s) up" || bad "$p has NO containers up"
done
echo

echo "── 6. KNOWN reboot side effects — expected, handle them ────────────"
qa=$(docker ps --filter "name=meddoc-qa-" --format '{{.Names}}' | wc -l)
if [ "$qa" -eq 0 ]; then
  note "⚠️  QA stack is down — EXPECTED, it does not self-restart. Bring it back:"
  note "     docker compose -f docker-compose.qa.yml up -d"
  note "   Then re-run: bash scripts/check-qa-mock-posture.sh"
else
  note "🟢 QA stack: $qa container(s) up"
fi
dirty=$(git -C "$(dirname "$0")/.." status --porcelain | grep -v '^?? ' || true)
if [ -n "$dirty" ]; then
  note "⚠️  working tree dirty — a stale @reboot cron does this. Inspect, do NOT clobber:"
  echo "$dirty" | sed 's/^/      /'
  note "   (only 'M Caddyfile' is an expected standing modification)"
else
  note "🟢 working tree clean"
fi
echo

if [ "$fail" = "0" ]; then
  echo "🟢 POST-REBOOT PROOF PASSED — both encrypted stores came back on their"
  echo "   own, in the right order, with both fail-closed guards intact."
  exit 0
fi
echo "🔴 POST-REBOOT PROOF FAILED — see the red lines above."
echo "   If a store is down because its unit did not run, that is the guard"
echo "   working: nothing wrote plaintext. Unlock, then investigate ordering."
exit 1
