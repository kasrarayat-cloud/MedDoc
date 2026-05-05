---
id: A07-P1-003
title: Unprivileged 'claude' user is in docker group → root-equivalent on host
severity: P1
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

The `claude` user (uid 1000) is a member of the `docker` group. Group
membership of `docker` is a documented full-root-equivalence path on the
host: any `docker` group member can `docker run -v /:/host -u root` to
read/write every host file, including `/etc/meddoc/postgres-volume.key`,
`/etc/shadow`, `/root/.ssh/`, etc.

## Evidence

```
$ getent group docker
docker:x:110:claude

$ id claude
uid=1000(claude) gid=1000(claude) groups=1000(claude),100(users),110(docker)
```

```
$ ls -la /var/run/docker.sock
(default 660 root:docker — anyone in 'docker' group has full API access)
```

Demonstration of root-equivalence (NOT executed, just documented):
`docker run --rm -v /etc:/etc-host alpine cat /etc-host/shadow` works for
any docker-group member.

## Risk

- The launch-readiness model treats `claude` as the unprivileged operator
  ("normal user, can't read /etc/meddoc"). docker-group membership
  silently breaks that invariant — `claude` can in fact read everything.
- Phase 6.2 keeps the age **private** key offline by design; that
  protection holds. But every other "host-only" secret (LUKS key, .env,
  pgdata.luks LUKS image at `/opt/meddoc-pro/secrets/pgdata.luks`) is in
  scope of `claude` once you account for the docker socket.
- The `claude` user has automation (cron entries — see `crontab -l`
  output documented in this round's deliverable bundle) and an SSH
  authorized_keys file. Any compromise of claude's key is a host
  compromise.

## Recommended fix

Pre-pilot, choose ONE of:

A) **Remove `claude` from docker group** and use `sudo -u root docker ...`
for the few tasks that need it (but operator's tooling assumes
docker-without-sudo currently — significant workflow change).

B) **Run rootless docker** (`dockerd-rootless-setuptool.sh install` for
the `claude` user) so the `docker` group buys you only your own user's
namespace, not host root. This is the documented mitigation path.

C) **Accept the risk explicitly** in the threat model and put compensating
controls everywhere `claude`'s authorized_keys live (hardware token, FIDO2
SK-key in authorized_keys, no password fallback). Treat `claude` as a
named admin account with full audit logging.

Whichever path is chosen, document it in `docs/runbooks/THREAT_MODEL.md`
so the next operator does not regress the invariant.
