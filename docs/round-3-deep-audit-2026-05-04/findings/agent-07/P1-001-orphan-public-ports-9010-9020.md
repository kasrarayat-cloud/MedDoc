---
id: A07-P1-001
title: docker-compose publishes :9010 / :9020 publicly but Caddy MODE B has no listeners
severity: P1
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

`docker-compose.yml` lines 249 and 251 publish ports `9010:9010` and
`9020:9020` from the Caddy container to the host's `0.0.0.0`. The current
Caddyfile (288 lines, MODE B since T-M19) has zero `:9010` or `:9020` blocks
— the only matchers are `quillmd.com`, `app.quillmd.com`,
`admin.quillmd.com`, `pro.quillmd.com` (and a `:80` HTTP→HTTPS redirect
implied by Caddy auto-https). The MODE A blocks for those ports are kept as
commented rollback reference only.

Net effect: external probes that hit `5.231.107.93:9010` or `:9020` reach a
running TCP socket and get either a TLS handshake failure (no SNI match) or
the `unknown host` default response. They learn the host is alive on those
ports — useful reconnaissance — and the unused publishes are an attack
surface for any future Caddy 0-day affecting unmatched-host handling.

## Evidence

```
$ grep -nE '"\d+:\d+"' /opt/meddoc-pro/docker-compose.yml | grep -E ':(9010|9020)'
249:      - "9010:9010"
251:      - "9020:9020"

$ grep -E '^[a-z\.0-9].*\{' /opt/meddoc-pro/Caddyfile | grep -v '^#'
quillmd.com, www.quillmd.com {
app.quillmd.com {
admin.quillmd.com {
pro.quillmd.com {

# No :9010 / :9020 blocks — they are commented MODE-A rollback only.
```

```
$ docker ps --format '{{.Names}}\t{{.Ports}}' | grep caddy
meddoc-pro-caddy-1  ...,0.0.0.0:9010->9010/tcp,...,0.0.0.0:9020->9020/tcp,...
```

## Risk

- Reconnaissance signal: external scanners learn QuillMD's footprint on
  ports that should be closed.
- Bug-class exposure: any future "Caddy unmatched-host crash on plaintext
  byte sequence X" CVE applies to QuillMD on these ports for no operational
  benefit.
- Combined with A07-P0-002 (no UFW), there is no compensating layer.

## Recommended fix

In `docker-compose.yml`, remove lines 249 and 251 from the `caddy:` ports
block. Keep `80:80` and `443:443`.

```diff
     ports:
       - "80:80"
       - "443:443"
-      # T-M1: public entry for TranscribeMD marketing site. 9001 was
-      # ...
-      - "9010:9010"
-      # T-M2: the TranscribeMD solo app itself. ...
-      - "9020:9020"
```

Recreate Caddy: `docker compose up -d --force-recreate caddy`. Verify
externally: `curl -I http://5.231.107.93:9010` should now `Connection
refused` instead of receiving anything.

Document in the MODE A rollback section of Caddyfile that re-enabling the
plaintext blocks ALSO requires re-adding the compose port publishes.
