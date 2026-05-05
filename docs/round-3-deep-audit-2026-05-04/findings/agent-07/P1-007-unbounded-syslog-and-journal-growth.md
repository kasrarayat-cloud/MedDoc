---
id: A07-P1-007
title: /var/log/journal at 3.8 GB and active syslog at 76 MB — log growth not bounded
severity: P1
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

System log directories are growing without an effective ceiling. The
systemd journal under `/var/log/journal/` is 3.8 GB. The active
`/var/log/syslog` is 76 MB. The largest rotated `syslog.1` is 205 MB.
`/var/log/btmp.1` is 94 MB (suggesting an ongoing brute-force-attempt
log). Container json-file logs are correctly capped via the compose
`logging:` blocks (10 MB × 3 files = 30 MB ceiling per container) — that
configuration is good.

System logs:
- `/etc/logrotate.d/rsyslog` rotates weekly, retains 4 cycles → in theory
  bounded, but the live syslog grows to 200+ MB *between* rotations.
- The systemd journal has no `SystemMaxUse=` or `MaxFileSec=` configured
  via `/etc/systemd/journald.conf` (file is unreadable to claude — but
  3.8 GB usage on a 296 GB disk shows it is unconfigured or set high).
- `/var/log/btmp` rotates monthly (94 MB rotated copy means a lot of
  failed-login activity, which ties to the no-fail2ban finding
  A07-P1-002).

## Evidence

```
$ du -sh /var/log/* | sort -h | tail -10
12M     /var/log/sysstat
21M     /var/log/auth.log.1
22M     /var/log/syslog.2.gz
23M     /var/log/syslog.4.gz
24M     /var/log/syslog.3.gz
76M     /var/log/syslog
94M     /var/log/btmp.1
205M    /var/log/syslog.1
3.8G    /var/log/journal

$ ls -la /var/log/auth.log /var/log/syslog
-rw-r----- 1 syslog adm  3966411 May  4 23:40 /var/log/auth.log
-rw-r----- 1 syslog adm 79442501 May  4 23:40 /var/log/syslog
```

`/etc/logrotate.d/rsyslog` is `rotate 4 weekly` — a single bad week (e.g.
log-amplifying probe) easily fills 800+ MB before rotation kicks in.

## Risk

- **Disk-pressure DoS:** if `ai-deal-hunter` or any future log-spamming
  bug fills `/var/log` (296 GB total disk, but `/` is unitary), postgres
  WAL writes can fail and the LUKS sparse loop file can fail to extend
  (its sparse semantics depend on the FS having space). Backups also
  share `/`.
- **Forensic gap:** if a noisy attack preceded a stealthy one, weekly
  rotation can overwrite the noisy logs before the operator gets to
  them. Phase 6.2 alerts via Slack on backup failures, but there is no
  alert for "log-volume anomaly".
- **journald's 3.8 GB cap-less behaviour** is not strictly unbounded
  (defaults to 10% of disk = ~30 GB on /), but at 296 GB total that's
  29 GB ceiling — a meaningful chunk that should be tightened.

## Recommended fix

Three small operations:

1. **Bound the journal** in `/etc/systemd/journald.conf`:
   ```
   [Journal]
   SystemMaxUse=500M
   SystemKeepFree=20G
   MaxFileSec=1week
   Compress=yes
   ```
   Then `systemctl restart systemd-journald`.

2. **Daily rotate for high-volume system logs.** Override
   `/etc/logrotate.d/rsyslog` with `daily`, `rotate 14`, `compress`,
   `size 50M`. The current `weekly rotate 4` is too sparse for a host
   with active probe traffic.

3. **Audit /var/log/btmp.1's 94 MB.** Before fixing, run
   `sudo last -f /var/log/btmp.1 | head -100` to confirm what's
   triggering it (likely SSH brute-force from internet, see
   A07-P1-002). Use that audit to prioritize the fail2ban install.

Phase 6.2 backup-offsite-sync.sh already implements per-run log
rotation (10 000-line tail) — that pattern is the model. Apply it to
host-level logs too.
