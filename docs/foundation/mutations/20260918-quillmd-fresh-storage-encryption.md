# Private fresh-storage encryption — 2026-09-18

Verified 2026-09-17/18: the fresh QuillMD database volume (docker named volume
quillmd_fresh_pg under /var/lib/docker/volumes), the state directory
/var/lib/quillmd (originals, exports, provider receipts, mail outbox, proofs),
the parser temporary workspaces under the services' private /tmp and the host
swap file all live on the plain ext4 root filesystem of a virtual disk with no
documented provider encryption. The two LUKS volumes on the host belong to the
retired stack. This act corrects the parts that are QuillMD's to correct and
names the parts that are not.

Expected delta, declared before the act. Created on the host: a sparse 16 GiB
LUKS2 loop file /opt/meddoc-pro/secrets/quillmd-fresh.luks; a random 64-byte key
file /etc/quillmd/quillmd-fresh-luks.key (root, 0400) in slot 0 and a generated
recovery passphrase /etc/quillmd/quillmd-fresh-luks.recovery-passphrase (root,
0400) in slot 1; an ext4 filesystem mounted at /mnt/quillmd-fresh-encrypted with
roots postgres/ and state/ and a marker file; the helper
/usr/local/bin/quillmd-fresh-volume and the units quillmd-fresh-volume.service
(Before=docker.service, opens and bind-mounts the roots) and
quillmd-fresh-database.service (BindsTo the volume, starts the existing
container); the three application units amended to Requires the database unit
and to use TMPDIR=/var/lib/quillmd/tmp on the encrypted state. Data: every
PostgreSQL row and every private file byte identical before and after; the
container quillmd-fresh-postgres keeps its identity, image, port and named
volume declaration (the volume directory is bound to the encrypted root), and
its restart policy changes from unless-stopped to no so only the database unit
starts it. The original plaintext copies move, not delete, to
/var/lib/quillmd-rollback-20260918 (root, 0700) and both former locations
become empty, root-owned, immutable directories. Permanent main fast-forwards
to the target and only the release line of the protected environment changes.
Zero provider calls, zero migration commands, no schema change, public statuses
unchanged, the six protected shared containers unchanged.

Drill declared as part of the act: after verification the volume unit is
stopped; the database and application units must stop with it; both bind
targets must be empty and immutable; a plaintext write probe must be refused; a
manual container start must not write into the closed directory; then the
volume, database and application units start again and rows, files, identity
proofs and health are verified a second time.

Before this act: branch and exact merge CI, the read-only preflight from
permanent main, and a validated encrypted backup with isolated restore proof
taken after the last data change. The act runs once through
run-ruled-mutation.sh with this committed declaration. Any failure stops the
application services and retains the lock, evidence and rollback material;
never rerun blindly. Rollback (--rollback under this same declaration) unbinds
the volume, restores the plaintext copies to their original locations, restores
the baseline units, re-enables the container's restart policy and leaves the
encrypted image, key and passphrase for inspection.

What this act does NOT establish: protection against a root compromise of the
running host (the key file is on the host); encryption of the host swap file,
journald logs or the shared root filesystem (host-level, outside QuillMD's
scope); off-host escrow of the key or the recovery passphrase (owner action).
No claim about Stripe, Resend, offsite restoration, invoice reconciliation or
independent testing follows from this act.
