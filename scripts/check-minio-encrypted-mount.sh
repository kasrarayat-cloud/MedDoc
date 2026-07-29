#!/usr/bin/env bash
# ============================================================================
# Is MinIO's data dir ACTUALLY on the encrypted mapping?
# ----------------------------------------------------------------------------
# IT CHECKS THE RUNNING CONTAINER'S RESOLVED MOUNT, NOT THE COMPOSE FILE, and
# that distinction is the entire reason it exists.
#
# On 2026-07-29 docker-compose.yml declared the minio_data volume as a bind to
# `/mnt/miniodata-encrypted`, the systemd unit was named
# miniodata-encrypted.service, and the runbook said "encryption at rest". All
# three READ as safe. None of it was true. `miniodata-encrypted.service` had
# never been started, so nothing was mounted at that path — and a MOUNTPOINT
# DIRECTORY EXISTS WHETHER OR NOT ANYTHING IS MOUNTED ON IT. The bind silently
# resolved to a plain directory on /dev/sda2, and MinIO wrote patient audio to
# the UNENCRYPTED root filesystem for four hours. Nothing errored. Nothing
# could have: every layer was reporting its own intent, and no layer was
# reporting the kernel's opinion.
#
# So the ONE question worth asking is the one the kernel answers:
#
#     what device backs the directory MinIO is writing into, right now?
#
# Everything else — the compose file, the unit name, the path string, a `df`
# against the mountpoint — can be right while the answer is /dev/sda2.
#
# FIVE CONDITIONS, because each covers a distinct way this reverts:
#
#   1. /mnt/miniodata-encrypted is a mountpoint       (the unit ran)
#   2. …and its source is the dm-crypt device         (it is the RIGHT mount)
#   3. MinIO's live /data resolves to that dm device  (the container agrees)
#   4. `data/` does NOT exist on the underlying dir   (the fail-closed guard is
#      intact — a stray mkdir there restores fail-open silently)
#   5. the unit is ENABLED                            (it survives a reboot)
#
# Condition 4 is the subtle one. The guard is that `data` exists only on the
# encrypted filesystem, so docker's local driver refuses to start MinIO when the
# mount is missing. Anyone who "fixes" a failed start with `mkdir -p` on the
# underlying path converts a loud refusal back into silent plaintext.
#
# READ-ONLY. Never mutates anything.
#
# Usage:  bash scripts/check-minio-encrypted-mount.sh
# Exit:   0 = on the encrypted mapping · 1 = DRIFT (plaintext or unprotected)
#         2 = cannot tell (not on the host / minio not running)
#
# Invoke with `bash scripts/...` — this repo sets core.fileMode=false, so the
# executable bit is not tracked and `./scripts/...` gives "Permission denied".
# ============================================================================
set -uo pipefail

MOUNT=/mnt/miniodata-encrypted
DM=/dev/mapper/minio-encrypted
UNIT=miniodata-encrypted.service
CONTAINER=meddoc-pro-minio-1

# Root-only reads (mountinfo of pid 1, the underlying dir, systemctl). No sudo
# on this box — see AGENTS.md. --ipc=host is NOT optional for anything touching
# device-mapper: dm's udev sync uses SysV semaphores, so a container with its
# own IPC namespace waits forever on a cookie host udev signals elsewhere. This
# script only READS, but it keeps the flag so a copy-paste into a mutating
# command inherits the right invocation.
inhost() {
  docker run --rm --privileged --ipc=host --pid=host -v /:/host \
    alpine chroot /host bash -c "$1" 2>/dev/null
}

if ! docker info >/dev/null 2>&1; then
  echo "⚠️  no docker — run this on the VPS host"
  exit 2
fi

fail=0

# ── 1 + 2: the mount exists and is the dm-crypt device ────────────────────
src=$(inhost "findmnt -no SOURCE $MOUNT")
if [ -z "$src" ]; then
  echo "🔴 $MOUNT is NOT MOUNTED — anything written there lands on the root"
  echo "   filesystem in PLAINTEXT. This is the 2026-07-29 failure exactly."
  fail=1
elif [ "$src" != "$DM" ]; then
  echo "🔴 $MOUNT is mounted from '$src', not $DM"
  fail=1
else
  echo "   🟢 $MOUNT ← $DM"
fi

# ── 3: what the RUNNING container is actually writing into ────────────────
if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "⚠️  $CONTAINER is not running — cannot check the live data path"
  exit 2
fi
data=$(inhost "findmnt -no SOURCE /var/lib/docker/volumes/meddoc-pro_minio_data/_data")
case "$data" in
  "$DM"\[/data\]|"$DM")
    echo "   🟢 MinIO /data ← $data" ;;
  "")
    echo "🔴 MinIO's data volume is not a separate mount at all — it is on the"
    echo "   root filesystem. Patient audio is resting UNENCRYPTED."
    fail=1 ;;
  *)
    echo "🔴 MinIO /data ← '$data' — NOT the encrypted mapping"
    fail=1 ;;
esac

# ── 4: the fail-closed guard is intact ────────────────────────────────────
# Read the UNDERLYING directory, which is only reachable while the mount is
# absent; with it mounted, `data` on top is the encrypted one and is correct.
# So this can only be checked meaningfully when unmounted — when mounted, assert
# instead that `data` is present ON the encrypted fs.
if [ -n "$src" ]; then
  if [ "$(inhost "test -d $MOUNT/data && echo yes")" != "yes" ]; then
    echo "🔴 $MOUNT/data is missing from the encrypted filesystem — the bind"
    echo "   target docker refuses on is gone; MinIO will not start."
    fail=1
  else
    echo "   🟢 $MOUNT/data present on the encrypted filesystem"
  fi
else
  if [ "$(inhost "test -d $MOUNT/data && echo yes")" = "yes" ]; then
    echo "🔴 A 'data' directory exists on the UNDERLYING (plaintext) path."
    echo "   That is the fail-closed guard defeated: docker will happily bind"
    echo "   it and MinIO will start writing plaintext. Remove it."
    fail=1
  fi
fi

# ── 5: it survives a reboot ───────────────────────────────────────────────
enabled=$(inhost "systemctl is-enabled $UNIT")
if [ "$enabled" != "enabled" ]; then
  echo "🔴 $UNIT is '$enabled', not enabled — the mapping will not come back"
  echo "   after a reboot, and MinIO will then refuse to start (fail-closed,"
  echo "   correctly) until someone unlocks it by hand."
  fail=1
else
  echo "   🟢 $UNIT enabled — unlocks at boot, before docker"
fi

echo
if [ "$fail" = "0" ]; then
  echo "🟢 MinIO rests on the encrypted mapping — verified against the kernel,"
  echo "   not against the compose file"
  exit 0
fi

echo "🔴 MINIO ENCRYPTION-AT-REST DRIFT. Patient audio may be resting plaintext."
echo "   Recover (see docs/DEPLOYMENT_RUNBOOK.md §5.7):"
echo "     systemctl start $UNIT      # as a HOST process, never in a container"
echo "     docker compose up -d minio"
echo "   Do NOT 'fix' a failed MinIO start by creating $MOUNT/data by hand —"
echo "   that directory is the guard, and creating it on the underlying"
echo "   filesystem is what silently restores plaintext writes."
exit 1
