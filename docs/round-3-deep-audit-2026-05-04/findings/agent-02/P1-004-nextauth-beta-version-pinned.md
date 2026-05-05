---
id: A02-P1-004
severity: P1
title: NextAuth pinned to a v5 beta (5.0.0-beta.31) for production launch — Auth.js v5 is not yet GA
domain: Auth & session security
files:
  - apps/transcribe-md/package.json:33
  - packages/auth/package.json:14-17
---

## Issue

The auth surface depends on `next-auth@5.0.0-beta.31` (resolved
from the `^5.0.0-beta.30` range). Auth.js v5 has been in beta since
2023 and is not yet marked GA. Beta releases for the auth library
mean:

1. Behavior is allowed to change between betas — the codebase has
   already absorbed several breaking-callback-shape changes in
   prior milestones (per the comments in `lib/nextauth.ts` and
   `packages/auth/src/index.ts`).
2. CVE-disclosure cadence for beta software is inconsistent with the
   stable channel; security fixes may land but go un-tagged or
   require chasing the `next` dist-tag.
3. The `@auth/core` peer dependency surface is also still beta-class.
4. There is no LTS guarantee — the project can drop the entire beta
   branch in favour of a redesigned v5 final without backporting
   fixes.

For a HIPAA-touching medical SaaS heading into pilot, "we ship
production atop a beta auth library" is a posture concern, not a
specific exploit.

## Evidence

`apps/transcribe-md/package.json`:
```json
"next-auth": "^5.0.0-beta.30",
```

`apps/transcribe-md/node_modules/next-auth/package.json`:
```json
"name": "next-auth",
"version": "5.0.0-beta.31",
```

`packages/auth/package.json`:
```json
"peerDependencies": {
  "next-auth": "^5.0.0-beta.30"
},
"devDependencies": {
  "next-auth": "^5.0.0-beta.30"
}
```

Behavioral risk evidence — `apps/transcribe-md/src/actions/auth.ts:104`
already comments around v5 quirks the codebase has had to work
around:
```ts
/** Email + password login. On success returns `ok: true, redirect: '/dashboard'`
 *  so the client can router.push — we don't throw `redirect()` inside the
 *  action because NextAuth's internal signIn() redirect breaks the
 *  useActionState cycle in Next 16. */
```

## Risk

- **Reactive supply-chain risk.** A regression or CVE in a future
  beta forces an emergency upgrade with potentially breaking
  callback-shape changes. The shared `authConfig` at
  `packages/auth/src/index.ts:141` is heavily customized and would
  bear the brunt of any v5-final API delta.
- **Auditor optics.** A SOC 2 Type II / HIPAA tabletop reviewer
  will flag "beta auth library in production" without further
  qualification.
- **Coverage gaps.** Many security-tool advisory databases (Snyk,
  GitHub Advisory) treat pre-1.0 beta versions as best-effort for
  CVE assignment — known issues may not light up automated
  dependency scans.

## Recommended fix

Two paths, in order of preference:

1. **Wait for v5 GA before pilot launch.** Auth.js v5 has been "soon"
   for a while; check the project's release radar and pin to the GA
   tag once it lands. The migration cost from beta.31 → final should
   be small; the public surface this codebase uses (Credentials
   provider, jwt/session callbacks, signIn/signOut, handlers) has
   stabilized in recent betas.

2. **If GA isn't out by pilot:** explicitly pin to the *exact* beta
   (`5.0.0-beta.31`, not `^5.0.0-beta.30`) so a `npm install` six
   weeks from now doesn't pull a beta.32 with a breaking change. Add
   an upgrade-window note to the launch runbook.

Additionally:

- Wire the `AUTH_SECRET_1/2/3` rolling-secret support that
  `@auth/core/src/lib/utils/env.ts:38` already plumbs through. The
  current single-secret config (`packages/auth/src/index.ts:107-115`)
  has no rotation story — `openssl rand`-and-redeploy mints all
  prior cookies invalid, which kicks every signed-in user.
