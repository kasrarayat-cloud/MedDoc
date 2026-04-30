#!/usr/bin/env bash
# infra/setup-encrypted-volume.sh
#
# Phase 3 / HIPAA h8 — Encrypted-at-rest postgres data volume.
#
# Idempotent host-level setup script that provisions a LUKS-on-loop-file
# encrypted block device for postgres data. Designed for the Zap Hosting
# VPS where Hetzner managed encrypted volumes are NOT available — the
# loop-file approach is portable and works on any Linux host with
# cryptsetup + a kernel that has dm-crypt.
#
# What it does (exactly once, even if re-run):
#   1. Allocates a 50 GB sparse file at IMG_PATH.
#   2. luksFormat with a random 4 KB key file at KEY_PATH (mode 0400, root).
#   3. Opens the LUKS device as MAPPER_NAME.
#   4. mkfs.ext4 the inner block device.
#   5. Mounts at MOUNT_POINT.
#   6. Installs a systemd unit that re-opens + re-mounts on boot, ordered
#      Before=docker.service so the postgres bind mount has its data dir
#      ready before the container starts.
#
# What it does NOT do:
#   - It does NOT migrate existing postgres data. See
#     docs/RUNBOOK_ENCRYPTED_VOLUME.md for the operator migration steps.
#   - It does NOT start/stop postgres or docker. The operator runs this
#     during a planned maintenance window with postgres already stopped.
#   - It does NOT back up the key. Operator MUST escrow KEY_PATH off-host
#     immediately — see HIPAA §164.312(a)(2)(iv) and the runbook.
#
# Safety:
#   - set -euo pipefail + ERR trap that rolls back partial state.
#   - Detects "already done" at every step and skips → re-running is safe.
#   - Will NOT overwrite an existing IMG_PATH or KEY_PATH.

set -euo pipefail

# ── Tunables ──────────────────────────────────────────────────────────
IMG_PATH="${IMG_PATH:-/var/lib/meddoc-postgres-encrypted.img}"
IMG_SIZE_GB="${IMG_SIZE_GB:-50}"
KEY_PATH="${KEY_PATH:-/etc/meddoc/postgres-volume.key}"
MAPPER_NAME="${MAPPER_NAME:-meddoc-postgres-encrypted}"
MOUNT_POINT="${MOUNT_POINT:-/var/lib/meddoc-postgres-data}"
SYSTEMD_UNIT="/etc/systemd/system/meddoc-postgres-volume.service"

# ── Helpers ───────────────────────────────────────────────────────────
log()  { printf '[setup-encrypted-volume] %s\n' "$*" >&2; }
die()  { printf '[setup-encrypted-volume] ERROR: %s\n' "$*" >&2; exit 1; }

# Track partial state so the ERR trap can roll back cleanly.
CREATED_IMG=0
CREATED_KEY=0
LUKS_FORMATTED=0
LUKS_OPENED=0
MKFS_DONE=0
MOUNTED=0

rollback() {
  local rc=$?
  log "FAILED (exit=$rc) — rolling back partial state"
  if [[ "$MOUNTED" -eq 1 ]]; then
    umount "$MOUNT_POINT" 2>/dev/null || true
  fi
  if [[ "$LUKS_OPENED" -eq 1 ]]; then
    cryptsetup close "$MAPPER_NAME" 2>/dev/null || true
  fi
  # Only delete the image if WE created it on this run AND luksFormat
  # didn't run. After luksFormat the image is "real" data; deleting it
  # would silently destroy whatever the operator was trying to recover.
  if [[ "$CREATED_IMG" -eq 1 && "$LUKS_FORMATTED" -eq 0 ]]; then
    rm -f "$IMG_PATH"
  fi
  if [[ "$CREATED_KEY" -eq 1 && "$LUKS_FORMATTED" -eq 0 ]]; then
    shred -u "$KEY_PATH" 2>/dev/null || rm -f "$KEY_PATH"
  fi
  log "rollback complete; address the error above and re-run"
  exit "$rc"
}
trap rollback ERR

# ── Pre-flight ────────────────────────────────────────────────────────
if [[ "$EUID" -ne 0 ]]; then
  die "must run as root (try: sudo $0)"
fi
for bin in cryptsetup mkfs.ext4 dd losetup blkid systemctl; do
  command -v "$bin" >/dev/null 2>&1 || die "missing dependency: $bin"
done

log "config: IMG=$IMG_PATH SIZE=${IMG_SIZE_GB}G KEY=$KEY_PATH MAPPER=$MAPPER_NAME MOUNT=$MOUNT_POINT"

# ── 1. Key file ───────────────────────────────────────────────────────
if [[ -f "$KEY_PATH" ]]; then
  log "key file already exists at $KEY_PATH — leaving untouched"
else
  log "generating 4 KB random key at $KEY_PATH"
  install -d -m 0700 -o root -g root "$(dirname "$KEY_PATH")"
  # Pre-create with strict perms BEFORE writing key bytes so there's no
  # window where the file is world-readable.
  ( umask 0377 && dd if=/dev/urandom of="$KEY_PATH" bs=4096 count=1 status=none )
  chmod 0400 "$KEY_PATH"
  chown root:root "$KEY_PATH"
  CREATED_KEY=1
fi

# ── 2. Backing file ───────────────────────────────────────────────────
if [[ -f "$IMG_PATH" ]]; then
  log "image file already exists at $IMG_PATH — leaving untouched"
else
  log "allocating sparse ${IMG_SIZE_GB} GB image at $IMG_PATH"
  install -d -m 0700 -o root -g root "$(dirname "$IMG_PATH")"
  dd if=/dev/zero of="$IMG_PATH" bs=1G seek="$IMG_SIZE_GB" count=0 status=none
  chmod 0600 "$IMG_PATH"
  chown root:root "$IMG_PATH"
  CREATED_IMG=1
fi

# ── 3. LUKS format ────────────────────────────────────────────────────
# isLuks returns 0 if the file contains a LUKS header. Skip format if so.
if cryptsetup isLuks "$IMG_PATH" 2>/dev/null; then
  log "image already LUKS-formatted — skipping luksFormat"
else
  log "running luksFormat on $IMG_PATH (this is destructive — only runs once)"
  cryptsetup -q luksFormat \
    --type luks2 \
    --cipher aes-xts-plain64 \
    --key-size 512 \
    --hash sha256 \
    --pbkdf argon2id \
    --key-file "$KEY_PATH" \
    "$IMG_PATH"
  LUKS_FORMATTED=1
fi

# ── 4. Open mapper ────────────────────────────────────────────────────
if [[ -e "/dev/mapper/$MAPPER_NAME" ]]; then
  log "mapper /dev/mapper/$MAPPER_NAME already open — skipping luksOpen"
else
  log "opening LUKS device as $MAPPER_NAME"
  cryptsetup open --key-file "$KEY_PATH" "$IMG_PATH" "$MAPPER_NAME"
  LUKS_OPENED=1
fi

# ── 5. ext4 ───────────────────────────────────────────────────────────
# blkid prints TYPE= when the device has a known fs. Empty output → fresh.
FS_TYPE="$(blkid -o value -s TYPE "/dev/mapper/$MAPPER_NAME" 2>/dev/null || true)"
if [[ -z "$FS_TYPE" ]]; then
  log "creating ext4 on /dev/mapper/$MAPPER_NAME"
  mkfs.ext4 -q -L meddoc-pgdata "/dev/mapper/$MAPPER_NAME"
  MKFS_DONE=1
elif [[ "$FS_TYPE" != "ext4" ]]; then
  die "unexpected fs type '$FS_TYPE' on /dev/mapper/$MAPPER_NAME — refusing to format"
else
  log "ext4 already present on /dev/mapper/$MAPPER_NAME — skipping mkfs"
fi

# ── 6. Mount ──────────────────────────────────────────────────────────
install -d -m 0700 -o root -g root "$MOUNT_POINT"
if mountpoint -q "$MOUNT_POINT"; then
  log "$MOUNT_POINT already mounted — skipping mount"
else
  log "mounting /dev/mapper/$MAPPER_NAME on $MOUNT_POINT"
  mount -o noatime,nodiratime "/dev/mapper/$MAPPER_NAME" "$MOUNT_POINT"
  MOUNTED=1
fi
# postgres in the container runs as uid 999 (see docker-compose.yml).
# The bind mount inherits the host directory's owner, so chown the
# mountpoint contents to 999 so postgres can read+write its data dir.
chown 999:999 "$MOUNT_POINT"
chmod 0700 "$MOUNT_POINT"

# ── 7. systemd unit ───────────────────────────────────────────────────
# Renders idempotently — overwriting the unit file with identical bytes
# is a no-op as far as systemctl daemon-reload is concerned.
log "installing systemd unit at $SYSTEMD_UNIT"
cat > "$SYSTEMD_UNIT" <<UNIT
# /etc/systemd/system/meddoc-postgres-volume.service
# Managed by infra/setup-encrypted-volume.sh — do not hand-edit.
#
# Opens the LUKS-encrypted postgres data volume on boot and mounts it
# at $MOUNT_POINT, ordered Before=docker.service so the bind mount
# defined in docker-compose.yml has its target ready before the
# postgres container starts.

[Unit]
Description=MedDoc encrypted postgres data volume (LUKS-on-loop-file)
DefaultDependencies=no
After=local-fs.target systemd-udev-settle.service
Before=docker.service
RequiresMountsFor=$(dirname "$IMG_PATH") $(dirname "$KEY_PATH")
ConditionPathExists=$IMG_PATH
ConditionPathExists=$KEY_PATH

[Service]
Type=oneshot
RemainAfterExit=yes
# Open LUKS device (skip if already open from a previous boot cycle).
ExecStart=/bin/sh -c '[ -e /dev/mapper/$MAPPER_NAME ] || /sbin/cryptsetup open --key-file $KEY_PATH $IMG_PATH $MAPPER_NAME'
# Mount (skip if already mounted).
ExecStart=/bin/sh -c 'mountpoint -q $MOUNT_POINT || /bin/mount -o noatime,nodiratime /dev/mapper/$MAPPER_NAME $MOUNT_POINT'
# Stop is best-effort: if docker is still using the mount, leave it.
ExecStop=/bin/sh -c '/bin/umount $MOUNT_POINT 2>/dev/null || true'
ExecStop=/bin/sh -c '/sbin/cryptsetup close $MAPPER_NAME 2>/dev/null || true'
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 "$SYSTEMD_UNIT"

systemctl daemon-reload
systemctl enable meddoc-postgres-volume.service >/dev/null 2>&1 || true

# ── Summary ───────────────────────────────────────────────────────────
trap - ERR
cat >&2 <<SUMMARY

────────────────────────────────────────────────────────────────────
  meddoc encrypted postgres volume — SETUP COMPLETE

  Backing file : $IMG_PATH ($(du -h "$IMG_PATH" | awk '{print $1}') on disk, ${IMG_SIZE_GB}G logical)
  LUKS key     : $KEY_PATH (0400 root:root — ESCROW THIS OFF-HOST NOW)
  Mapper       : /dev/mapper/$MAPPER_NAME
  Mount point  : $MOUNT_POINT (owned by 999:999 for postgres uid)
  systemd unit : $SYSTEMD_UNIT (enabled, runs Before=docker.service)

  NEXT STEPS (operator):
    1. Escrow $KEY_PATH to your secrets vault. If this file is lost
       the encrypted volume is unrecoverable.
    2. Follow docs/RUNBOOK_ENCRYPTED_VOLUME.md to migrate existing
       postgres data into $MOUNT_POINT and switch the bind mount.
    3. Log the migration date in your HIPAA audit trail.
────────────────────────────────────────────────────────────────────
SUMMARY
