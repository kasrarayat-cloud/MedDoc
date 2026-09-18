#!/usr/bin/env bash
# /usr/local/bin/quillmd-fresh-volume — open, bind, verify and close the QuillMD
# fresh encrypted volume. Installed root:root 0755 from rebuild/deploy by the
# declared storage migration; invoked only by quillmd-fresh-volume.service and
# quillmd-fresh-database.service.
#
# The LUKS2 container is a sparse loop file; its filesystem carries three roots:
#   postgres/  bound over the docker named-volume directory of quillmd-fresh-postgres
#   state/     bound over /var/lib/quillmd (originals, exports, receipts, mail, proofs, tmp)
# A marker file proves the filesystem is the migrated one before anything is bound.
# When the volume is closed, both bind targets are empty, root-owned, immutable
# directories: nothing can write plaintext into them by mistake.
set -euo pipefail

IMAGE=/opt/meddoc-pro/secrets/quillmd-fresh.luks
KEY=/etc/quillmd/quillmd-fresh-luks.key
NAME=quillmd-fresh-encrypted
MOUNT=/mnt/quillmd-fresh-encrypted
MARKER="$MOUNT/.quillmd-fresh-volume"
PG_BIND=/var/lib/docker/volumes/quillmd_fresh_pg/_data
STATE_BIND=/var/lib/quillmd

refuse() { echo "quillmd-fresh-volume: $1" >&2; exit 1; }

is_mounted() { mountpoint -q "$1"; }

case "${1:-}" in
  open)
    [ -f "$KEY" ] || refuse "key file missing: $KEY"
    [ -f "$IMAGE" ] || refuse "encrypted image missing: $IMAGE"
    [ -d "$MOUNT" ] || refuse "mount point missing: $MOUNT"
    if [ ! -e "/dev/mapper/$NAME" ]; then
      cryptsetup open --key-file "$KEY" "$IMAGE" "$NAME"
    fi
    if ! is_mounted "$MOUNT"; then
      mount -o nodev,nosuid "/dev/mapper/$NAME" "$MOUNT"
    fi
    if [ ! -f "$MARKER" ]; then
      umount "$MOUNT" || true
      cryptsetup close "$NAME" || true
      refuse "volume marker missing; refusing to bind an unrecognised filesystem"
    fi
    [ -d "$MOUNT/postgres" ] && [ -d "$MOUNT/state" ] || refuse "migrated roots missing on the volume"
    if ! is_mounted "$PG_BIND"; then
      mount --bind "$MOUNT/postgres" "$PG_BIND"
    fi
    if ! is_mounted "$STATE_BIND"; then
      mount --bind "$MOUNT/state" "$STATE_BIND"
    fi
    ;;
  close)
    if is_mounted "$STATE_BIND"; then umount "$STATE_BIND"; fi
    if is_mounted "$PG_BIND"; then umount "$PG_BIND"; fi
    if is_mounted "$MOUNT"; then umount "$MOUNT"; fi
    if [ -e "/dev/mapper/$NAME" ]; then cryptsetup close "$NAME"; fi
    ;;
  status)
    is_mounted "$MOUNT" || refuse "encrypted volume is not mounted"
    [ -f "$MARKER" ] || refuse "volume marker missing"
    is_mounted "$PG_BIND" || refuse "database directory is not bound to the encrypted volume"
    is_mounted "$STATE_BIND" || refuse "state directory is not bound to the encrypted volume"
    src=$(findmnt -no SOURCE "$MOUNT")
    case "$src" in /dev/mapper/$NAME*) ;; *) refuse "unexpected mount source: $src" ;; esac
    echo "quillmd-fresh-volume: open, marker present, database and state bound"
    ;;
  wait-database)
    for i in $(seq 1 90); do
      if docker exec quillmd-fresh-postgres pg_isready -U quillmd_fresh -d quillmd_fresh >/dev/null 2>&1; then
        echo "quillmd-fresh-volume: database ready"
        exit 0
      fi
      sleep 1
    done
    refuse "database did not become ready within 90s"
    ;;
  *)
    echo "usage: quillmd-fresh-volume open|close|status|wait-database" >&2
    exit 2
    ;;
esac
