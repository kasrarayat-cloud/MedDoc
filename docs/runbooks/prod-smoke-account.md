# Runbook — authenticated production smoke account

**Status:** live since 2026-07-25
**Owner:** platform
**Related:** `apps/transcribe-md/scripts/prod-smoke/`, `docs/runbooks/edge-security.md`

## Why this exists

Production sign-up auto-confirm is gated OFF (`EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD`),
so for months there was no way to log in to production without borrowing a real
clinician's account. The consequence was structural, not theoretical: **every
deploy shipped with the authenticated clinical flows verified only on QA.** The
2026-07-25 surgery deploy is a concrete example — it was verified structurally
(bundle contents, server chunks, worker crons) and the clinical smoke was
skipped and reported as skipped.

Borrowing Kasra's account is not an acceptable substitute. It puts synthetic
visits in a real doctor's chart list, writes a real user id into the audit
trail, and makes "is this row real?" unanswerable afterwards.

So: one clearly-named synthetic doctor, permanently pre-verified, whose clinical
data is deleted after every smoke.

## The fixture

| | |
|---|---|
| Email | `smoke-doctor@smoke.quillmd.invalid` |
| Name | `QuillMD Smoke Bot (synthetic — not a clinician)` |
| Practice | `QuillMD Smoke Test Practice (synthetic)`, slug `quillmd-smoke-practice` |
| Products | `[TRANSCRIBE_MD]` — deliberately **not** `SUPER_ADMIN` |
| Credentials | `/opt/meddoc-pro/.smoke-account.env` (chmod 600, gitignored) |

Safety properties, all deliberate:

- **`.invalid` TLD** (RFC 2606) can never resolve, so no smoke run can email a
  real person even if a notification path fires unexpectedly.
- **Its own practice**, never shared with a real clinician — practice-scoped
  queries cannot surface a real patient to it.
- **No `SUPER_ADMIN` entitlement** — a smoke account must not reach `/admin`.
- The cleaner **refuses to delete anything** outside this practice/user.

## Usage

```bash
cd /opt/meddoc-pro/apps/transcribe-md
DBPW=$(grep -E '^DB_PASSWORD=' /opt/meddoc-pro/.env | cut -d= -f2-)
export DATABASE_URL="postgresql://meddoc:${DBPW}@127.0.0.1:5432/meddoc?schema=public"

# 1. Provision or reset. IDEMPOTENT — also the fix for a locked-out fixture.
../../node_modules/.bin/tsx scripts/prod-smoke/provision.ts

# 2. ... run the authenticated smoke ...

# 3. ALWAYS clean afterwards.
../../node_modules/.bin/tsx scripts/prod-smoke/clean.ts
```

`provision.ts` clears `lockedUntil`, `failedLoginCount`, `suspendedAt` and
`softDeletedAt` on every run. This matters more than it sounds: a smoke that
exercises the login rate limiter will trip the 5-failure account lock, and the
next smoke would otherwise fail for a reason unrelated to what it tests. If a
smoke run ends with "account locked", re-run provision — do not go poking at
the users table by hand.

Set `SMOKE_ACCOUNT_PASSWORD` to pin a known credential; otherwise a fresh
32-char one is generated and written to the env file.

## What the cleaner deletes — and what it must not

Deletes, scoped to the fixture: `transcribe_visits`, `transcribe_md_patients`,
`note_templates`.

**Keeps, on purpose:**

- the user + practice rows, so the next smoke can just log in;
- **`audit_logs` — never deleted.** The append-only audit trail is the record
  that the smoke happened. Deleting it would be precisely the tampering the
  audit layer exists to make impossible. Smoke rows are identifiable by the
  fixture's `userId` / `userEmailSnapshot`, which is the intended way to filter
  them out of a report — not deletion.

## Reading the audit trail afterwards

```sql
SELECT action::text, "ipAddress"::text, timestamp
FROM audit_logs
WHERE "userEmailSnapshot" = 'smoke-doctor@smoke.quillmd.invalid'
ORDER BY timestamp DESC LIMIT 50;
```

Synthetic rows are expected in production audit output. Anyone auditing the
trail should filter on this address rather than being surprised by it.

## Authenticating a smoke run — use the callback, not the login form

Since S2 gave every request a real client IP, `RATE_LIMITS.LOGIN` (10/hour,
keyed on `clientIpFromHeaders`) is genuinely per-IP. A smoke that drives the
**login form** repeatedly from one box therefore trips its own limiter — this
happened on 2026-07-25 after 12 logins in an hour, and the symptom is
misleading: `page.waitForURL(/\/dashboard/)` times out with no error text, which
reads as "the app is broken" rather than "you are rate limited".

The limiter is on the server ACTION (`loginAction`), not on the NextAuth
callback route. So authenticate through the callback and reuse the context
cookie jar:

```js
const csrf = (await (await ctx.request.get(`${BASE}/api/auth/csrf`)).json()).csrfToken;
await ctx.request.post(`${BASE}/api/auth/callback/credentials`, {
  form: { csrfToken: csrf, email: SMOKE_EMAIL, password: SMOKE_PASSWORD },
});
// page navigations now carry the session
```

This is not a way around the control — it is the same credential check, minus
the form action's abuse limiter, which exists to stop password-guessing rather
than to stop a smoke logging in. If you specifically want to TEST the limiter,
drive the form; expect "Too many attempts" on the 11th.

Note also that a burst of failed logins trips the 5-failure ACCOUNT lock on the
fixture. Re-run `provision.ts` to clear it.
