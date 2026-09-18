#!/usr/bin/env bash
# /usr/local/bin/quillmd-fresh-volume — open, bind, verify and close the QuillMD
# fresh encrypted volume. Installed root:root 0755 from rebuild/deploy by the
# declared storage migration; invoked by quillmd-fresh-volume.service,
# quillmd-fresh-database.service and, for manual unlock, by an operator through
# scripts/ops/unlock-fresh-volume.sh.
#
# The LUKS2 container is a sparse loop file; its filesystem carries two roots:
#   postgres/  bound over the docker named-volume directory of quillmd-fresh-postgres
#   state/     bound over /var/lib/quillmd (originals, exports, receipts, mail, proofs, tmp)
# A marker file proves the filesystem is the migrated one before anything is bound.
# When the volume is closed, both bind targets are empty, root-owned, immutable
# directories: nothing can write plaintext into them by mistake.
#
# Key slots at creation: 0 = key file (unattended boot); 1 = recovery passphrase (typed).
# If the key file is absent (kept off the host by the owner), `open` refuses and
# the volume stays closed until `unlock` is run with the passphrase on stdin.
set -euo pipefail

IMAGE=/var/lib/quillmd-encrypted/quillmd-fresh.luks
KEY=/etc/quillmd/quillmd-fresh-luks.key
NAME=quillmd-fresh-encrypted
MOUNT=/mnt/quillmd-fresh-encrypted
MARKER="$MOUNT/.quillmd-fresh-volume"
PG_BIND=/var/lib/docker/volumes/quillmd_fresh_pg/_data
STATE_BIND=/var/lib/quillmd

refuse() { echo "quillmd-fresh-volume: $1" >&2; exit 1; }

is_mounted() { mountpoint -q "$1"; }

close_all() {
  if is_mounted "$STATE_BIND"; then umount "$STATE_BIND"; fi
  if is_mounted "$PG_BIND"; then umount "$PG_BIND"; fi
  if is_mounted "$MOUNT"; then umount "$MOUNT"; fi
  if [ -e "/dev/mapper/$NAME" ]; then cryptsetup close "$NAME"; fi
}

# A failed open leaves nothing half-done: no decrypted mount, no bind, no open mapper.
fail_closed() { close_all || true; refuse "$1"; }

mount_and_bind() {
  if ! is_mounted "$MOUNT"; then
    mount -o nodev,nosuid "/dev/mapper/$NAME" "$MOUNT" || fail_closed "could not mount the encrypted filesystem"
  fi
  [ -f "$MARKER" ] || fail_closed "volume marker missing; refusing to bind an unrecognised filesystem"
  { [ -d "$MOUNT/postgres" ] && [ -d "$MOUNT/state" ]; } || fail_closed "migrated roots missing on the volume"
  if ! is_mounted "$PG_BIND"; then
    mount --bind "$MOUNT/postgres" "$PG_BIND" || fail_closed "could not bind the database directory"
  fi
  if ! is_mounted "$STATE_BIND"; then
    mount --bind "$MOUNT/state" "$STATE_BIND" || fail_closed "could not bind the state directory"
  fi
}

preconditions() {
  [ -f "$IMAGE" ] || refuse "encrypted image missing: $IMAGE"
  [ -d "$MOUNT" ] || refuse "mount point missing: $MOUNT"
}

case "${1:-}" in
  open)
    preconditions
    if [ ! -e "/dev/mapper/$NAME" ]; then
      [ -f "$KEY" ] || refuse "key file absent ($KEY); the volume stays closed. Unlock manually with the recovery passphrase: scripts/ops/unlock-fresh-volume.sh"
      cryptsetup open --key-file "$KEY" "$IMAGE" "$NAME"
    fi
    mount_and_bind
    ;;
  unlock)
    # Passphrase arrives on stdin (typed through the operator script); cryptsetup
    # reads until the first newline and strips it, exactly as at a terminal. No slot
    # is pinned: after a passphrase rotation the recovery passphrase lives in
    # whichever slot luksAddKey chose.
    preconditions
    if [ ! -e "/dev/mapper/$NAME" ]; then
      cryptsetup open "$IMAGE" "$NAME"
    fi
    mount_and_bind
    ;;
  close)
    close_all
    ;;
  status)
    is_mounted "$MOUNT" || refuse "encrypted volume is not mounted"
    [ -f "$MARKER" ] || refuse "volume marker missing"
    is_mounted "$PG_BIND" || refuse "database directory is not bound to the encrypted volume"
    is_mounted "$STATE_BIND" || refuse "state directory is not bound to the encrypted volume"
    for target in "$MOUNT" "$PG_BIND" "$STATE_BIND"; do
      src=$(findmnt -no SOURCE "$target")
      case "$src" in /dev/mapper/$NAME*) ;; *) refuse "unexpected mount source for $target: $src" ;; esac
    done
    echo "quillmd-fresh-volume: open, marker present, database and state bound"
    ;;
  wait-database)
    for i in $(seq 1 120); do
      if docker exec quillmd-fresh-postgres pg_isready -U quillmd_fresh -d quillmd_fresh >/dev/null 2>&1; then
        echo "quillmd-fresh-volume: database ready"
        exit 0
      fi
      sleep 1
    done
    refuse "database did not become ready within 120s"
    ;;
  *)
    echo "usage: quillmd-fresh-volume open|unlock|close|status|wait-database" >&2
    exit 2
    ;;
esac
