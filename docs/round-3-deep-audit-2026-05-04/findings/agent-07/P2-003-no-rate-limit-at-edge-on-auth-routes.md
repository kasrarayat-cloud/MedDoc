---
id: A07-P2-003
title: Caddy has no rate-limit on /api/auth/* or other sensitive endpoints
severity: P2
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

The Caddyfile does not configure any rate-limiting for `/api/auth/*` (the
NextAuth credential surface), `/api/admin/*` (super-admin REST + SSE), or
`/login` / `/forgot-password` / `/reset-password`. Caddy 2 has a built-in
`rate_limit` matcher (via `caddy-rate-limit` plugin or the new
`caddy-ratelimit` module) but the current build (`caddy:2-alpine`) has
neither configured nor present in the Caddyfile.

This combines with no fail2ban (A07-P1-002): the auth/credential surfaces
on `app.quillmd.com` and `pro.quillmd.com` have *no* throttling at any
layer.

## Evidence

```
$ grep -nE '(rate_limit|throttle)' /opt/meddoc-pro/Caddyfile
(no matches)
```

In the active blocks, every path is served by an unrestricted
`reverse_proxy`. The admin host's strict allowlist (lines 124-212) is a
*correct* defence-in-depth on path matching, but neither it nor the others
restrict rate.

## Risk

- Credential brute-force at the application layer is unbounded. Even with
  fail2ban on SSH (A07-P1-002), HTTP login endpoints have no equivalent.
- `/api/auth/csrf` has no rate-limit → CSRF token grinding for downstream
  attacks.
- DoS amplification via SSE endpoints (`/api/admin/stream/activity`):
  unbounded long-lived connections from a single IP can starve the
  upstream.
- HIPAA §164.308(a)(5)(ii)(D) password management implies some form of
  account-lockout / rate-limit; relying solely on app-layer NextAuth (no
  attempt counter today by default) is thin.

## Recommended fix

Add a `rate_limit` block to the Caddyfile (requires the
`caddy-ratelimit` module — simplest is to swap the image to one that
includes it, e.g. `ghcr.io/mholt/caddy-ratelimit` or build a custom Caddy
image with `xcaddy`):

```
(rl_auth) {
    rate_limit {
        zone auth_zone {
            key {client_ip}
            events 30
            window 1m
        }
    }
}

app.quillmd.com {
    @auth path /api/auth/* /login /forgot-password /reset-password
    handle @auth {
        import rl_auth
        reverse_proxy transcribe-md:3011 { ... }
    }
    # ... rest unchanged
}
```

If the build-time effort to add a Caddy module is undesirable, an
acceptable interim is application-layer rate-limiting in the Next.js
middleware, plus a `Retry-After` header. Document in
`docs/runbooks/RATE_LIMIT.md`.

Also add a 1-second timeout on `/api/auth/csrf` upstreams to bound
single-request cost.
