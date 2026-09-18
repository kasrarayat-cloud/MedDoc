#!/usr/bin/env bash
# ============================================================================
# Post-reboot proof — the one property a hand-started unit cannot demonstrate.
# ----------------------------------------------------------------------------
# The preserved PostgreSQL and MinIO stores are unlocked by systemd units ordered
# `Before=docker.service`, and both containers now FAIL CLOSED if their volume
# is missing. Those two facts together mean a boot-ordering race no longer
# corrupts anything — it just takes the stack down. That is the right trade, but
# it is only a trade if the ordering actually works, and starting a unit by hand
# proves nothing about ordering.
#
# So this runs AFTER a real reboot and asserts the whole chain:
#
#   units started at boot → mappings open → mounts live on the dm devices →
#   Postgres and MinIO healthy ON those devices → guards intact → marketing up →
#   co-tenants up → fresh private services up → public maintenance intact
#
# The retired application and QA stack must not be restored. Fresh doctor/admin
# previews stay on loopback; their public hosts deliberately return HTTP 503.
# This also reports unexpected changes to the shared deployment working tree.
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

REPO=$(cd "$(dirname "$0")/.." && pwd)

# ---------------------------------------------------------------------------
# Assert a compose stack is COMPLETE, not merely non-empty.
#
# Historical false greens in stack checks shared the same shape:
# each asked "is anything wrong?" of a set whose size it never established.
#
#   §4 printed "🟢 every meddoc-pro container is up" against ZERO containers.
#      `docker ps -a` returns nothing, the grep filters nothing, the emptiness
#      test passes. That is green on a DEAD production stack — and green in
#      precisely the case this proof exists to catch, because both stores now
#      FAIL CLOSED: a lost boot race takes the stack down rather than reverting
#      to plaintext. The check was blindest exactly where it had to see.
#
#   §4 also could not see an UNHEALTHY container, twice over:
#      `grep -vi "healthy"` drops "unhealthy" as a substring, and `Up [0-9]`
#      matches any running container whatever its health says.
#
# The fix is the one section 1 already models: name what you expect, and
# compare. Derive the expected service set from the compose file, resolve each
# service to its container, and require running + (healthy | no healthcheck).
# An assertion that names its expected set cannot be satisfied by an empty one.
# ---------------------------------------------------------------------------
stack_state() {   # $1 = compose file, $2 = project prefix → "service<TAB>status|health"
  local f="$1" proj="$2" svc cname st
  for svc in $(docker compose -f "$f" config --services 2>/dev/null | sort); do
    cname="${proj}-${svc}-1"
    st=$(docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cname" 2>/dev/null) \
      || st="absent|none"
    printf '%s\t%s\n' "$svc" "$st"
  done
}

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
for u in pgdata-encrypted miniodata-encrypted quillmd-fresh-volume; do
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
for m in /mnt/pgdata-encrypted /mnt/miniodata-encrypted /mnt/quillmd-fresh-encrypted; do
  s=$(inhost "findmnt -no SOURCE $m")
  [ -n "$s" ] && note "🟢 $m ← $s" || bad "$m is NOT mounted"
done
# The fresh database directory and state directory must be BINDS of the encrypted
# volume, never the plain root filesystem: a missing bind is the plaintext case.
for b in /var/lib/docker/volumes/quillmd_fresh_pg/_data /var/lib/quillmd; do
  src=$(inhost "findmnt -no SOURCE $b")
  case "$src" in
    /dev/mapper/quillmd-fresh-encrypted*) note "🟢 $b ← $src (encrypted bind)" ;;
    *) bad "$b is NOT bound to the encrypted volume (source: '${src:-none}')" ;;
  esac
done
# The pre-migration plaintext snapshot is kept only until the owner approves its destruction. Report it every time.
if inhost "test -e /var/lib/quillmd-rollback-20260918"; then
  note "🟡 plaintext rollback snapshot /var/lib/quillmd-rollback-20260918 still present (owner approval to destroy it pending)"
fi
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

echo "── 4. preserved shared stack and public routing ────────────────────"
prod_expected=$(docker compose -f "$REPO/docker-compose.yml" config --services 2>/dev/null | sort)
if [ -z "$prod_expected" ]; then
  # Must fail loudly. An unreadable compose file means we cannot establish what
  # "complete" is, and "I could not check" must never render as "🟢".
  bad "cannot read the preserved compose service list — the stack's completeness is UNPROVEN, not fine"
else
  n_exp=$(printf '%s\n' "$prod_expected" | wc -l)
  n_ok=0; prod_bad=""
  while IFS=$'\t' read -r svc st; do
    [ -z "$svc" ] && continue
    status="${st%%|*}"; health="${st##*|}"
    if [ "$status" != "running" ]; then
      prod_bad="${prod_bad}      ${svc} → ${status}"$'\n'
    elif [ "$health" != "healthy" ] && [ "$health" != "none" ]; then
      prod_bad="${prod_bad}      ${svc} → running but ${health}"$'\n'
    else
      n_ok=$((n_ok + 1))
    fi
  done < <(stack_state "$REPO/docker-compose.yml" meddoc-pro)
  if [ -n "$prod_bad" ]; then
    bad "preserved stack incomplete — $n_ok/$n_exp services running and healthy:"
    printf '%s' "$prod_bad"
    note "   (MinIO can read 'unhealthy' after losing its mc alias while serving fine —"
    note "    classify before acting, do not assume either way)"
  else
    note "🟢 preserved stack complete — $n_ok/$n_exp services running and healthy"
  fi
fi
for spec in "https://quillmd.com:200" "https://app.quillmd.com:503" "https://admin.quillmd.com:503"; do
  url="${spec%:*}"; expected="${spec##*:}"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url") || code=000
  [ "$code" = "$expected" ] && note "🟢 $url → $code (expected $expected)" || bad "$url → $code (expected $expected)"
done
echo

echo "── 5. co-tenants (this host is shared) ─────────────────────────────"
# Count baselines observed 2026-07-29 on a clean boot. Weaker than §4's
# service-identity check — these are other people's stacks and we do not own
# their compose files — but strictly better than `-gt 0`, which passes on 1 of 6.
for spec in "leathererp:3" "voiceassistmain:6" "openclaw:1"; do
  p="${spec%%:*}"; want="${spec##*:}"
  n=$(docker ps --filter "name=$p" --format '{{.Names}}' | wc -l)
  if [ "$n" -eq 0 ]; then
    bad "$p has NO containers up (expected $want)"
  elif [ "$n" -lt "$want" ]; then
    bad "$p: only $n of $want container(s) up — a co-tenant lost something to the boot"
  else
    note "🟢 $p: $n/$want container(s) up"
  fi
done
echo

echo "── 6. fresh private application ────────────────────────────────────"
for u in quillmd-fresh-doctor quillmd-fresh-admin quillmd-fresh-worker; do
  st=$(inhost "systemctl is-active $u.service")
  enabled=$(inhost "systemctl is-enabled $u.service")
  if [ "$st" = "active" ] && [ "$enabled" = "enabled" ]; then
    note "🟢 $u.service → active and enabled"
  else
    bad "$u.service → $st / $enabled (expected active / enabled)"
  fi
done
fresh_db=$(docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.HostConfig.RestartPolicy.Name}}' quillmd-fresh-postgres 2>/dev/null) || fresh_db="absent|none|none"
# The database unit and the application units must also have started AT BOOT,
# in order: a hand-started chain proves nothing about ordering.
db_since=$(inhost "systemctl show -p ActiveEnterTimestamp --value quillmd-fresh-database.service")
db_epoch=$(inhost "date -d '$db_since' +%s" 2>/dev/null)
if [ -z "$db_epoch" ] || [ -z "$boot_epoch" ] || [ $(( db_epoch - boot_epoch )) -lt 0 ] || [ $(( db_epoch - boot_epoch )) -gt 300 ]; then
  bad "quillmd-fresh-database.service did not start within 300s of boot ('$db_since') — hand start or failed unlock"
else
  note "🟢 quillmd-fresh-database.service started $(( db_epoch - boot_epoch ))s after boot"
fi
for u in quillmd-fresh-doctor quillmd-fresh-admin quillmd-fresh-worker; do
  since=$(inhost "systemctl show -p ActiveEnterTimestamp --value $u.service")
  epoch=$(inhost "date -d '$since' +%s" 2>/dev/null)
  if [ -z "$epoch" ] || [ -z "$db_epoch" ] || [ "$epoch" -lt "$db_epoch" ]; then
    bad "$u.service started before the encrypted database ('$since')"
  fi
done
# Since the storage migration the container is started ONLY by
# quillmd-fresh-database.service (restart policy 'no'), so a persistent docker
# restart policy would itself be a finding: it could start the database on a
# closed volume.
db_unit=$(inhost "systemctl is-active quillmd-fresh-database.service")
case "$fresh_db" in
  'running|none|no'|'running|healthy|no')
    if [ "$db_unit" = "active" ] && docker exec quillmd-fresh-postgres pg_isready -U quillmd_fresh -d quillmd_fresh >/dev/null 2>&1; then
      note "🟢 quillmd-fresh-postgres → ready, started by quillmd-fresh-database.service (restart policy no)"
    else
      bad "quillmd-fresh-postgres → running but database unit is '$db_unit' or pg_isready failed"
    fi ;;
  *) bad "quillmd-fresh-postgres → $fresh_db (expected running / ready / restart policy no, under quillmd-fresh-database.service='$db_unit')" ;;
esac
for spec in "doctor:9130" "admin:9131"; do
  surface="${spec%%:*}"; port="${spec##*:}"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "http://127.0.0.1:$port/health/") || code=000
  [ "$code" = "200" ] && note "🟢 private $surface health → 200" || bad "private $surface health → $code"
done
echo

echo "── 7. shared deployment tree ───────────────────────────────────────"
# `git status` must be allowed to FAIL LOUDLY. Run from the boot unit this
# executes as root against a repo owned by `claude`, and git then refuses with
# "detected dubious ownership" — on stderr, with an empty stdout. The first
# version piped that straight into an emptiness test and printed
# "🟢 working tree clean" off a hard error. An unreadable tree is not a clean
# one. `safe.directory` is passed per-invocation rather than written to a global
# config, because a check should not mutate the host it is checking.
if git_out=$(git -c safe.directory="$REPO" -C "$REPO" status --porcelain 2>&1); then
  dirty=$(printf '%s\n' "$git_out" | grep -v '^?? ' | grep -v '^$' || true)
  if [ -n "$dirty" ]; then
    note "⚠️  working tree dirty — inspect the changes; do NOT clobber:"
    echo "$dirty" | sed 's/^/      /'
  else
    note "🟢 working tree clean"
  fi
else
  bad "cannot read the working tree — git said: ${git_out%%$'\n'*}"
fi
echo

if [ "$fail" = "0" ]; then
  echo "🟢 POST-REBOOT PROOF PASSED — preserved encrypted stores and shared"
  echo "   services are healthy; fresh private services and public maintenance match."
  exit 0
fi
echo "🔴 POST-REBOOT PROOF FAILED — see the red lines above."
echo "   If a store is down because its unit did not run, that is the guard"
echo "   working: nothing wrote plaintext. Unlock, then investigate ordering."
exit 1
