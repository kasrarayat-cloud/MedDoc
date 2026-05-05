---
id: A05-P1-002
title: Doctor session is 7 days with no idle-timeout — HHS guidance is 15 minutes for clinical PHI surfaces
domain: HIPAA-technical-safeguards
severity: P1
agent: 05
---

## Issue

`apps/transcribe-md/src/lib/nextauth.ts:30-54`:

```ts
/** 7 days. Longer than meddoc-pro (8hr) because TranscribeMD is a solo
 *  consumer surface, not a PHI-heavy clinical tool. */
const SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;
...
session: {
  strategy: 'jwt',
  maxAge: SESSION_MAX_AGE_SECONDS,
  updateAge: 24 * 60 * 60,
},
```

The comment claims TranscribeMD is "not a PHI-heavy clinical tool" —
this is incorrect. TranscribeMD ingests doctor-patient audio, derives
SOAP notes, and persists them. Every session is a PHI session.

There is **no idle-timeout enforcement layer**: `grep -rln "idle\|
inactivity\|lastActivity\|lastSeen" apps/transcribe-md/src/lib/` returns
zero matches. The 7-day TTL is an absolute lifetime; there is nothing
that invalidates the cookie if the doctor steps away from the laptop
for an hour.

The `/admin` surface caps at 12 hours via
`lib/admin-session-freshness.ts:30` (`ADMIN_SESSION_MAX_AGE_HOURS = 12`)
— still too long for §164.312(a)(2)(iii), and the doctor flow has no
analogous gate.

## Evidence

- `apps/transcribe-md/src/lib/nextauth.ts:30-54` — 7-day maxAge,
  24-hour updateAge.
- `apps/transcribe-md/src/lib/admin-session-freshness.ts:30` —
  admin-only 12-hour cap.
- HHS OCR guidance on §164.312(a)(2)(iii) Automatic Logoff:
  "Implement electronic procedures that terminate an electronic session
  after a predetermined time of inactivity." Industry-standard
  interpretation for clinical surfaces is 10–15 minutes idle.
- `lib/auth.config.ts` (header comment) confirms meddoc-pro CRM uses 8
  hours; the divergence to 7 days for transcribe-md is not justified
  by the PHI exposure.

## Risk

- §164.312(a)(2)(iii) — Automatic Logoff: a 7-day session over a
  shared device leaves PHI accessible to whoever picks up the laptop.
  Pilot practices typically have shared workstations (front desk,
  exam-room kiosks) — the failure mode is unauthenticated PHI access
  by the next user.
- The "single-session enforcement" inherited from `@meddoc/auth` only
  prevents a SECOND device from being logged in simultaneously; it
  does not address device-walk-away within a single session.

## Recommended fix

1. **Reduce `SESSION_MAX_AGE_SECONDS`** to 8 hours (parity with
   meddoc-pro CRM). Hard-cut to 8h, not "longer because consumer."
2. **Add an idle-timeout layer**: track `lastActivity` on each
   authed request (in `validateSession` middleware via `UserSession`
   table — `UserSession` already exists per
   `schema.prisma:line ~750`). If `now - lastActivity > 15 minutes`
   on a PHI route, force re-auth.
3. **Update the admin cap from 12h to 8h** for consistency, OR
   document the rationale for the 12h carve-out.
4. **Add a settings-page UX affordance** so the doctor can choose
   "remember me on this device" (extending to 7d) ONLY for non-PHI
   pages (signup, billing). PHI routes always get the 8h+15min-idle
   regime.
