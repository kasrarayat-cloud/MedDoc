---
id: A02-P2-003
severity: P2
title: Caddy is the trusted edge but Caddy's reverse_proxy directive does not declare trusted_proxies — XFF-stripping defaults are implicit, not enforced
domain: Auth & session security
files:
  - Caddyfile:73
  - Caddyfile:90
  - apps/transcribe-md/src/lib/rate-limit.ts:183
---

## Issue

Caddy is the public terminator and the rate-limit primitive trusts
the *first* `X-Forwarded-For` value as the client IP for every
unauthenticated bucket (login, signup, forgot-password, etc.):

```ts
export function clientIpFromHeaders(headers: Headers): string {
  const xff = headers.get('x-forwarded-for');
  if (xff) {
    const first = xff.split(',')[0]?.trim();
    if (first) return first;
  }
  return headers.get('x-real-ip') || 'unknown';
}
```

Caddy's `reverse_proxy` block sets `header_up X-Forwarded-For
{remote_host}` (no `+` prefix → replace, not append) which in a
single-hop "Caddy → app" topology *is* secure. But:

1. Caddy v2's documented behaviour for `header_up X-Forwarded-For`
   is that without an explicit `trusted_proxies` block, the
   directive replaces the value seen by the upstream — that's
   *implicit* trust, not declared. If the topology ever gains a
   second proxy hop (Cloudflare, AWS ALB, a future
   load-balancer), the in-app IP-extraction code would silently
   trust whatever the new edge stamps without anybody re-auditing
   the assumption.
2. There is no `trusted_proxies` directive in the Caddyfile, so
   if Caddy ever gets fronted by another proxy, `{remote_host}`
   would resolve to the proxy IP rather than the real client.
   Without an explicit trust list at this layer, the rate-limit
   buckets become ineffective the moment topology shifts.
3. `x-real-ip` fallback at line 188 is unauthenticated — the same
   spoofing concern applies.

## Evidence

`Caddyfile:65-79` — the app.quillmd.com block:
```
app.quillmd.com {
    log {
        output stdout
        format console
    }

    import security_headers_mode_b

    reverse_proxy transcribe-md:3011 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

No `trusted_proxies` block anywhere in the Caddyfile. Caddy v2
relies on its own internal definition of trusted IPs to determine
when to pass through vs replace; the absence of an explicit
declaration means the team can't *prove* the configuration is
sound without inspecting Caddy's source-of-truth.

`apps/transcribe-md/src/lib/rate-limit.ts:182-195`:
```ts
export function clientIpFromHeaders(headers: Headers): string {
  const xff = headers.get('x-forwarded-for');
  if (xff) {
    const first = xff.split(',')[0]?.trim();
    if (first) return first;
  }
  return headers.get('x-real-ip') || 'unknown';
}
```

## Risk

Low *today* (single-hop topology, Caddy strips the header), but
this is exactly the kind of implicit assumption that breaks
silently when ops adds Cloudflare / AWS ALB / a CDN in front of
Caddy without re-running the auth audit. Once the topology
changes, the rate-limit buckets become trivially bypassable by
any attacker who can set their own `X-Forwarded-For` header.

The audit team explicitly listed Caddy → app as the trust
boundary in `KASRA_HANDOFF.md` — formalising the "I trust the
first value" decision in code keeps that contract durable across
future infra changes.

## Recommended fix

1. **Caddy side:** declare `trusted_proxies static private_ranges`
   (or the explicit Cloudflare / ALB CIDR list when those land)
   inside the `reverse_proxy` block. Forces Caddy to use the
   real-client logic deliberately.

2. **App side:** replace the IP-extraction with a strict
   "rightmost-untrusted-hop" parse. Documented pattern:

   ```ts
   const TRUSTED = ['127.0.0.1', '::1', /* docker-network CIDRs */];
   export function clientIpFromHeaders(headers: Headers): string {
     const xff = (headers.get('x-forwarded-for') ?? '').split(',').map(s => s.trim()).filter(Boolean);
     for (let i = xff.length - 1; i >= 0; i--) {
       if (!TRUSTED.includes(xff[i])) return xff[i];
     }
     return headers.get('x-real-ip') ?? 'unknown';
   }
   ```

   This walks XFF *right to left* and returns the first IP that
   isn't in the trust list — i.e., the original client even
   under multi-hop.

3. Add a smoke test in `tests/` that ships a request with
   `X-Forwarded-For: spoofed.attacker.com, real-client` and
   asserts the rate-limit key reflects `real-client`, not
   `spoofed.attacker.com`.

Cross-domain hook: this finding overlaps with infra/networking
(Caddy config) and observability (the access-log already shows
the real client_ip, but the app-side bucketing doesn't necessarily
match).
