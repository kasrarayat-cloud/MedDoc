---
id: A07-P0-003
title: Unrelated root-uvicorn server on 0.0.0.0:8000 shares the QuillMD VPS
severity: P0
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

A Python uvicorn process (`/root/ai-deal-hunter/backend/venv/bin/uvicorn`)
is running as **root**, bound to **0.0.0.0:8000**, completely independent of
QuillMD. This service shares the same host kernel, the same filesystem, the
same docker daemon, and the same public IP as the QuillMD production
deployment. There is no firewall (A07-P0-002), no AppArmor profile readable
to claude (`aa-status` permission denied), and no SELinux.

Port 18789 / 18790 (`openclaw-openclaw-gateway-1` container) is a similar
case at lower severity — at least it runs containerised, but still on the
same docker bridge.

## Evidence

```
$ ps -ef | grep 8000
root  947  1  0 23:25 ?  /root/ai-deal-hunter/backend/venv/bin/python3 \
                          /root/ai-deal-hunter/backend/venv/bin/uvicorn main:app \
                          --host 0.0.0.0 --port 8000

$ ss -tlnp | grep ':8000'
LISTEN 0 2048 0.0.0.0:8000  0.0.0.0:*
```

## Risk

For a HIPAA-bearing host this is a covered-entity boundary violation:

- A separate workload runs as root on the host that holds PHI. That root
  process can read `/etc/meddoc/postgres-volume.key` (the LUKS key for the
  encrypted-at-rest postgres volume), connect to the docker socket
  (`/var/run/docker.sock`), exec into the postgres container, dump pg_data
  in plaintext from inside the container's namespace.
- The 296 GB disk is shared. If `ai-deal-hunter` runs out of control, it
  can fill the disk and DOS QuillMD's pg_dump cron + the encrypted-LUKS
  loop file (which is sparse).
- A separate workload's RCE / SSRF / dependency-confusion bug becomes
  QuillMD's incident.
- Forensic trail is muddled — `auth.log` shows `root` sessions; whose root
  was it during an incident, QuillMD's or `ai-deal-hunter`'s operator?

This is not a configuration question that can be patched in QuillMD's repo;
it's an infra-tenancy question for the operator. Phase 6.2 explicitly added
encrypted backups to close the geographic-redundancy HIPAA gap, but a
shared-host root coexists at the same blast radius as the encrypted volume,
so the encryption gain is partially undone.

## Recommended fix

Pre-pilot:

1. Move `ai-deal-hunter` and `openclaw-gateway` off this VPS. Even a
   2-vCPU companion VPS for non-QuillMD workloads at $5/mo is the cheapest
   way to honor the HIPAA tenancy boundary.
2. If they MUST coexist (cost reason), run them as a non-privileged user,
   bind them to 127.0.0.1, drop them behind UFW with their port whitelisted
   only from a tunnel / VPN endpoint, and document in
   `docs/runbooks/HOST_TENANCY.md` that the BAA scope explicitly excludes
   them and any incident in those workloads triggers a QuillMD incident
   response too.
3. Add a launch-checklist line: "single-tenant host (no other root-
   running workloads)".

Out of scope for QuillMD's source tree but in scope for the launch
readiness document and operator runbook.
