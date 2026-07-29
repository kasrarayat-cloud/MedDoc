#!/usr/bin/env bash
# ============================================================================
# Is Postgres's cluster ACTUALLY on the encrypted mapping?
# ----------------------------------------------------------------------------
# Sibling of scripts/check-minio-encrypted-mount.sh, and it exists because the
# same bug class sat under the live clinical database.
#
# On 2026-07-29 MinIO was found writing patient audio to the plaintext root
# filesystem: its compose bind pointed at /mnt/miniodata-encrypted, the unit was
# enabled but never started, and A MOUNTPOINT DIRECTORY EXISTS WHETHER OR NOT
# ANYTHING IS MOUNTED ON IT — so the bind fell through to /dev/sda2 with every
# layer reporting success. Postgres was bound the same way, by compose SHORT-FORM
# syntax, which additionally AUTO-CREATES the host path.
#
# Postgres's version of that failure is worse than MinIO's:
#
#   unmounted /mnt/pgdata-encrypted → docker creates an empty dir on /dev/sda2
#   → the postgres image sees no PG_VERSION → it runs INITDB
#   → a brand-new EMPTY cluster starts, healthy, on plaintext storage
#   → the app connects to an empty database and the real cluster sits
#     unmounted underneath, untouched and invisible
#
# Nothing in that sequence errors. `pg_isready` returns fine. The health check
# goes green. It is a silent, total, apparently-successful data outage.
#
# So the volume now binds /mnt/pgdata-encrypted/pgdata — the cluster SUBDIR,
# which exists only on the encrypted filesystem — via driver_opts, which docker
# will NOT create if missing. Absent mount → docker refuses → Postgres fails
# closed. Negative-controlled in a throwaway compose project (never against this
# data): missing device refuses, present device runs.
#
# FIVE CONDITIONS:
#   1. /mnt/pgdata-encrypted is a mountpoint            (the unit ran)
#   2. …from /dev/mapper/pg-encrypted                   (the RIGHT mount)
#   3. the LIVE container's data dir is on that device  (the container agrees)
#   4. PG_VERSION is present in it                      (a real cluster, not a
#      fresh initdb — this is the condition that catches the failure above)
#   5. pgdata-encrypted.service is ENABLED              (survives a reboot)
#
# READ-ONLY. Never mutates anything.
#
# Usage:  bash scripts/check-pg-encrypted-mount.sh
# Exit:   0 = on the encrypted mapping · 1 = DRIFT · 2 = cannot tell
#
# Invoke with `bash scripts/...` — this repo sets core.fileMode=false, so the
# executable bit is not tracked and `./scripts/...` gives "Permission denied".
# ============================================================================
set -uo pipefail

MOUNT=/mnt/pgdata-encrypted
DM=/dev/mapper/pg-encrypted
UNIT=pgdata-encrypted.service
CONTAINER=meddoc-pro-postgres-1
VOL=/var/lib/docker/volumes/meddoc-pro_pgdata_encrypted/_data

# --ipc=host is not optional for anything touching device-mapper: dm's udev sync
# uses SysV semaphores, so a container with its own IPC namespace waits forever
# on a cookie host udev signals elsewhere. This script only READS, but it keeps
# the flag so a copy-paste into a mutating command inherits the right form.
inhost() {
  docker run --rm --privileged --ipc=host --pid=host -v /:/host \
    alpine chroot /host bash -c "$1" 2>/dev/null
}

if ! docker info >/dev/null 2>&1; then
  echo "⚠️  no docker — run this on the VPS host"
  exit 2
fi

fail=0

# ── 1 + 2 ────────────────────────────────────────────────────────────────
src=$(inhost "findmnt -no SOURCE $MOUNT")
if [ -z "$src" ]; then
  echo "🔴 $MOUNT is NOT MOUNTED. If Postgres is (re)started in this state the"
  echo "   image will INITDB A NEW EMPTY CLUSTER on the plaintext root"
  echo "   filesystem and come up healthy. Do not restart it — mount first."
  fail=1
elif [ "$src" != "$DM" ]; then
  echo "🔴 $MOUNT is mounted from '$src', not $DM"
  fail=1
else
  echo "   🟢 $MOUNT ← $DM"
fi

# ── 3 ────────────────────────────────────────────────────────────────────
if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "⚠️  $CONTAINER is not running — cannot check the live data path"
  exit 2
fi
data=$(inhost "findmnt -no SOURCE $VOL")
case "$data" in
  "$DM"\[/pgdata\]|"$DM")
    echo "   🟢 Postgres data ← $data" ;;
  "")
    echo "🔴 Postgres's data volume is not a separate mount at all — the"
    echo "   cluster is on the root filesystem, UNENCRYPTED."
    fail=1 ;;
  *)
    echo "🔴 Postgres data ← '$data' — NOT the encrypted mapping"
    fail=1 ;;
esac

# ── 4: a REAL cluster, not a fresh initdb ────────────────────────────────
# The distinguishing artefact. An initdb-on-plaintext incident produces a
# perfectly healthy Postgres, so "is it running" proves nothing; "is this the
# cluster we have been writing to since May" is the question.
ver=$(inhost "cat $MOUNT/pgdata/PG_VERSION 2>/dev/null")
if [ -z "$ver" ]; then
  echo "🔴 no PG_VERSION at $MOUNT/pgdata — either the mount is absent or this"
  echo "   is not the real cluster"
  fail=1
else
  echo "   🟢 cluster present on the encrypted fs (PG_VERSION $ver)"
fi

# ── 5 ────────────────────────────────────────────────────────────────────
enabled=$(inhost "systemctl is-enabled $UNIT")
if [ "$enabled" != "enabled" ]; then
  echo "🔴 $UNIT is '$enabled', not enabled — the mapping will not come back"
  echo "   after a reboot. Postgres then fails closed (correctly) rather than"
  echo "   initdb-ing onto plaintext, but the stack stays down until unlocked."
  fail=1
else
  echo "   🟢 $UNIT enabled — unlocks at boot, before docker"
fi

echo
if [ "$fail" = "0" ]; then
  echo "🟢 Postgres rests on the encrypted mapping — verified against the"
  echo "   kernel, not against the compose file"
  exit 0
fi

echo "🔴 POSTGRES ENCRYPTION-AT-REST DRIFT. Structured PHI may be at risk."
echo "   Recover (see docs/DEPLOYMENT_RUNBOOK.md §5.7):"
echo "     systemctl start $UNIT      # as a HOST process, never in a container"
echo "     docker compose up -d postgres"
echo "   NEVER 'fix' a failed Postgres start by creating $MOUNT/pgdata by hand."
echo "   On an unmounted volume that directory lands on plaintext storage and"
echo "   the next start initdb's an empty cluster into it — which looks like a"
echo "   successful recovery and is total, silent data loss."
exit 1
