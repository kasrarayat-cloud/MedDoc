---
id: A07-P0-002
title: No host firewall — UFW installed but inactive, no nftables/iptables rules
severity: P0
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

The VPS has no host-level packet filter active. UFW is installed
(`ufw/noble,now 0.36.2-6 all [installed,automatic]`) but reports
`Status: inactive` (and `systemctl is-enabled ufw → disabled`). The kernel's
nftables ruleset is unmanaged. Every Docker `0.0.0.0:<port>` publish goes
straight to the public IP with no ingress filter in front of it.

This combines with finding A07-P1-001 (port 9010 + 9020 publicly bound but
have NO Caddy listener after the MODE-A → MODE-B cut-over).

## Evidence

```
$ systemctl is-active ufw
inactive
$ systemctl is-enabled ufw
disabled
$ ufw status
ERROR: You need to be root to run this script
```

```
$ ss -tlnp | awk '$4 ~ /^0.0.0.0/'
LISTEN 0 4096 0.0.0.0:18789  openclaw-gateway          # external sandbox tool
LISTEN 0 4096 0.0.0.0:18790  openclaw-gateway
LISTEN 0 4096 0.0.0.0:9020   meddoc-pro-caddy-1        # ORPHAN: no Caddy block
LISTEN 0 4096 0.0.0.0:9010   meddoc-pro-caddy-1        # ORPHAN: no Caddy block
LISTEN 0 4096 0.0.0.0:443    meddoc-pro-caddy-1        # legitimate
LISTEN 0 4096 0.0.0.0:22     sshd                      # legitimate
LISTEN 0 4096 0.0.0.0:80     meddoc-pro-caddy-1        # legitimate (→ 308 to https)
LISTEN 0 2048 0.0.0.0:8000   /root/ai-deal-hunter/.../uvicorn    # OUT-OF-SCOPE app
```

Three categories of unintended public exposure:
- Ports 18789/18790 belong to an `openclaw-gateway` container (sandbox
  harness running outside QuillMD scope).
- Port 8000 is a separate Python `uvicorn` server running as **root** under
  `/root/ai-deal-hunter/` — completely unrelated to QuillMD, but on the
  same VPS, with no firewall isolating it from the public IP.
- Ports 9010 + 9020 are bound by Caddy because docker-compose still
  publishes them publicly (compose.yml lines 249, 251), but Caddyfile MODE B
  has no `:9010` / `:9020` blocks (see A07-P1-001) — anything reaching
  Caddy on those ports gets the auto-generated default-host TLS error or a
  bare-IP cert mismatch.

## Risk

- **Direct DB / Redis / MinIO bypass:** all three are bound to 127.0.0.1
  inside the container, but a host firewall is the line of defence if a
  future compose edit or a third-party tool ever publishes to 0.0.0.0.
  Right now, one misedit is one `:` away from world exposure with no net.
- **Tenant cross-contamination:** the `ai-deal-hunter` and `openclaw`
  processes share the same public IP and the same host-network namespace.
  No firewall to enforce "only QuillMD ports public, others loopback" at
  the host level. An RCE in `ai-deal-hunter` (running as root!) is a
  full-host pivot.
- **Brute-force mitigation:** SSH on :22 has no rate-limit at the network
  layer (no fail2ban either — A07-P1-002).
- **HIPAA §164.312(c) integrity / §164.312(e) transmission security:** a
  default-allow ingress posture on a PHI-bearing host is hard to defend in
  a §164.308(a)(8) evaluation.

## Recommended fix

Pre-pilot, before live PHI:

1. Enable UFW with a default-deny ingress, allow only what's published by
   QuillMD's Caddy:
   ```
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw allow 22/tcp comment 'ssh'
   sudo ufw allow 80/tcp comment 'caddy http→https redirect'
   sudo ufw allow 443/tcp comment 'caddy tls'
   sudo ufw enable
   ```
2. Remove the `9010:9010` and `9020:9020` publishes from
   `docker-compose.yml` (lines 249, 251) — they are dead since the MODE B
   cut-over and only widen the attack surface. Caddy now exclusively
   handles 80/443.
3. Coordinate with the operator about `ai-deal-hunter` and `openclaw`:
   either move them to a separate VPS (preferred — different blast
   radius), bind them to 127.0.0.1, or whitelist their ports in UFW
   explicitly. Today they are silent accomplices in a HIPAA boundary
   violation.
4. Document in `docs/runbooks/` that publishing a docker port to
   `0.0.0.0:*` requires a paired UFW rule + a security review.
