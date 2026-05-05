---
id: A07-P3-003
title: postscript.sh downloads `mc` from dl.min.io with no checksum verification
severity: P3
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

`infra/postgres-backup/postscript.sh` (the original h16 offsite-mirror
script that runs as `POST_BACKUP_COMMAND` inside the postgres-backup
sidecar) downloads the MinIO `mc` client over HTTPS:

```bash
curl -fsSL --max-time 60 \
  https://dl.min.io/client/mc/release/linux-amd64/mc \
  -o "$MC_BIN.tmp"
chmod +x "$MC_BIN.tmp"
mv "$MC_BIN.tmp" "$MC_BIN"
```

There is no checksum verification. `dl.min.io` is HTTPS so the channel is
authenticated to the certificate, but a compromise of the MinIO release
infrastructure (or a Caddy/CDN cache poisoning between MinIO and us) would
deliver an attacker-controlled `mc` that runs in the postgres-backup
container with read access to `/backups/` (= every plaintext PHI dump).

## Evidence

```
$ grep -n 'curl' /opt/meddoc-pro/infra/postgres-backup/postscript.sh
50:  curl -fsSL --max-time 60 \
51:    https://dl.min.io/client/mc/release/linux-amd64/mc \
52:    -o "$MC_BIN.tmp"
```

There is no `sha256sum -c` step before the `chmod +x`. The cached binary
at `/backups/.mc-bin` survives container restarts.

The Phase 6.2 sync script (`infra/backup-offsite-sync.sh`) by contrast uses
`b2` from pip and `age` from apt — both go through package managers with
their own integrity guarantees, so this finding is specific to
postscript.sh.

## Risk

- Supply-chain compromise of `mc` → postgres-backup container's
  `/backups/` (PHI dumps) is the blast radius. Defence-in-depth is poor:
  the container drops all caps and runs as 999:999, but it still has the
  data dir bind-mounted.
- `dl.min.io` itself has not been reported compromised; this is a
  forward-looking concern.

## Recommended fix

Pin a checksum and verify before chmod:

```bash
MC_SHA="<verified sha256 of the current release>"
curl -fsSL --max-time 60 \
  https://dl.min.io/client/mc/release/linux-amd64/mc \
  -o "$MC_BIN.tmp"
echo "$MC_SHA  $MC_BIN.tmp" | sha256sum -c -
chmod +x "$MC_BIN.tmp"
mv "$MC_BIN.tmp" "$MC_BIN"
```

MinIO publishes per-release SHA256SUMS at
`https://dl.min.io/client/mc/release/linux-amd64/SHA256SUMS` — fetch and
compare against the known-good pin (don't blindly use the file itself
since it has the same trust model).

Better: ship `mc` baked into the postgres-backup image via a build step
that pins by digest, eliminating the runtime download entirely. This
also removes the need for `/backups/.mc-bin` cache and the
`/backups/.mc-config` directory inside the PHI-bearing dir.

Lower-priority because Phase 6.2 supersedes the postscript.sh path
operationally; some operators may turn off `mc mirror` once B2 is live.
But while postscript.sh is in `POST_BACKUP_COMMAND`, the gap is real.
