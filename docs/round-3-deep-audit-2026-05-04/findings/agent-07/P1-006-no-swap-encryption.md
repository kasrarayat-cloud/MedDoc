---
id: A07-P1-006
title: Swap is not encrypted (4 GB plaintext /swap.img)
severity: P1
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

`/swap.img` (4 GB, mode 0600 root) is in active use as system swap and is
**not** encrypted. Phase 6.1 (h8) closed encryption-at-rest on the postgres
data volume via LUKS-on-loop-file (`/dev/mapper/pg-encrypted` on
`/mnt/pgdata-encrypted`), but did not cover swap.

Memory pressure from the LUKS workload, MinIO open-file count, and Node
runtimes (transcribe-md, transcribe-md-worker, marketing, meddoc-pro) on
an 11 GB host RAM (memory note says 5.6 GB after the hypervisor regression)
will routinely page application memory — including buffers that have just
read PHI rows from postgres or transcripts from MinIO — out to that
plaintext file.

## Evidence

```
$ cat /proc/swaps
Filename                                Type            Size  Used  Priority
/swap.img                               file            4194300  0   -2

$ ls -la /swap.img
-rw------- 1 root root 4294967296 Sep 18  2024 /swap.img

$ swapon --show
NAME      TYPE SIZE USED PRIO
/swap.img file   4G   0B   -2

$ blkid /swap.img
(no LUKS header — plain swap)
```

`vm.swappiness` is the default `60`, so the kernel will preferentially page
to swap rather than reclaim cache.

## Risk

- **HIPAA §164.312(a)(2)(iv) "Encryption and Decryption":** swap holds
  PHI in cleartext. Disk seizure (physical attacker, hosting-provider
  forensics, snapshot leak) recovers PHI even though postgres data is
  LUKS-encrypted. The encrypted-volume work loses force.
- **Backup snapshot risk:** if the operator ever rsyncs `/` or takes a
  filesystem snapshot, `/swap.img` rides along and exfiltrates whatever
  was paged at the time.

## Recommended fix

Two compatible approaches:

A) **LUKS-encrypted swap with random key per boot** — Ubuntu's standard
   `cryptsetup` random-key swap, configured via `/etc/crypttab`:
   ```
   # /etc/crypttab
   cryptswap  /swap.img  /dev/urandom  swap,cipher=aes-xts-plain64,size=512
   ```
   And in `/etc/fstab`: `/dev/mapper/cryptswap none swap sw 0 0`.
   Random key per boot means no key escrow needed and no recovery from
   a powered-off snapshot.

B) **Disable swap entirely** if the workload fits in 5.6 GB RAM (memory
   note says it's tight). `swapoff /swap.img && rm /swap.img` and remove
   the fstab entry. Any future OOM is loud + investigable.

Option B is the simplest if the system can sustain peak load without
swap. Option A is the HIPAA-rigorous path. Prefer A; benchmark first.

Also reduce `vm.swappiness` to 10 (`/etc/sysctl.d/99-meddoc.conf`) so the
kernel prefers cache reclaim over paging.
