---
id: A07-P0-001
title: sshd_config sets PermitRootLogin yes; root sessions in active use
severity: P0
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

`/etc/ssh/sshd_config` contains an explicit `PermitRootLogin yes` directive.
A `Include /etc/ssh/sshd_config.d/*.conf` is present and the directory holds
`50-cloud-init.conf` (mode 0600 root, unreadable to claude), so a drop-in
override may exist; however, `last` shows root logging in over SSH from
`76.174.150.33` consistently — including the active session at the time of
this audit (`root pts/0 76.174.150.33 ... still logged in`). Whatever the
effective setting, root SSH login is in fact happening.

## Evidence

```
$ grep -nE 'PermitRoot|PasswordAuth|PubkeyAuth' /etc/ssh/sshd_config
33:PermitRootLogin yes
56:#PasswordAuthentication yes
65:KbdInteractiveAuthentication no
```

```
$ last -n 5
root     pts/0        76.174.150.33    Mon May  4 23:28   still logged in
root     pts/0        76.174.150.33    Mon May  4 08:38 - 10:51  (02:12)
root     pts/2        76.174.150.33    Sun May  3 04:02 - down  (1+01:45)
root     pts/0        76.174.150.33    Sat May  2 23:41 - down   (04:19)
root     pts/4        76.174.150.33    Fri May  1 03:11 - 23:26 (1+20:15)
```

```
$ ps -ef | grep sshd
root        1176       1  0 23:25 ?  sshd: /usr/sbin/sshd -D [listener] 1 of 10-100 startups
root        6502    1176  0 23:28 ?  sshd: root@pts/0
```

`/etc/ssh/sshd_config.d/50-cloud-init.conf` is mode 0600 root:root — claude
cannot read it to confirm whether it overrides PermitRootLogin. `sshd -T`
also requires root.

`PasswordAuthentication` is not explicitly disabled; the OpenSSH default of
`yes` therefore applies unless the cloud-init drop-in overrides it.

## Risk

Highest-blast-radius identity on the box (uid 0) accepts SSH directly. If
PasswordAuthentication is also default-on (commented out → yes), credential
stuffing / brute force against `root` is unrestricted. There is no fail2ban
(see A07-P1-002), no UFW (see A07-P0-002), and no AllowUsers/AllowGroups
filter. The blast radius of one compromised session is total — root owns the
LUKS key file (`/etc/meddoc/postgres-volume.key`), the docker socket, the
B2 application keys (once Phase 6.2 is live), every `.env` and every
container's data volume.

For HIPAA §164.312(a)(2)(i) "unique user identification" + §164.308(a)(5)
"workforce security" purposes, shared root logins are also a documentation
hole — the audit trail says only "root from 76.174.150.33", not which named
operator was on.

## Recommended fix

1. Verify the effective config: `sudo sshd -T | grep -E 'permitrootlogin|passwordauth'`.
   If either resolves permissively, fix immediately.
2. In `/etc/ssh/sshd_config.d/`, add a drop-in (e.g. `99-meddoc.conf`):
   ```
   PermitRootLogin no
   PasswordAuthentication no
   PubkeyAuthentication yes
   AllowUsers ubuntu claude        # named operators only
   MaxAuthTries 3
   LoginGraceTime 30
   ```
3. Confirm every operator who currently uses root has a named user with
   their own pubkey in `~/.ssh/authorized_keys` (Kasra, Claude). Test the
   replacement path in a second session BEFORE killing the active root
   session.
4. `systemctl reload ssh`; re-run `sshd -T`; verify with a fresh
   connection attempt.
5. Add to LAUNCH_READINESS.md as a launch-blocker pre-pilot.
