---
id: A02-P0-001
severity: P0
title: Production EMAIL_AUTO_CONFIRM_DOMAINS=quillmd-test.local enables anonymous, unverifiable trial-account farming
domain: Auth & session security
files:
  - apps/transcribe-md/src/lib/email-auto-confirm.ts:76
  - apps/transcribe-md/src/actions/auth.ts:358
  - apps/transcribe-md/src/actions/auth.ts:411
  - .env:76
  - docker-compose.yml:468
---

## Issue

The QA-only email-auto-confirm bypass is *active in production*. The
production `.env` carries `EMAIL_AUTO_CONFIRM_DOMAINS=quillmd-test.local`
(committed by docker-compose at line 468), and the `signupAction`
unconditionally consults `isAutoConfirmDomain(emailLower)` for every
signup. When the domain matches, the user row is created with
`emailVerified = new Date()` and the verification email is *skipped*.

Because the domain `quillmd-test.local` is RFC-6762 reserved (no real
mailbox can ever exist there) and the matcher uses `lastIndexOf('@')`
followed by a literal Set membership check, anyone who submits the
public signup form with an address of the form `<anything>@quillmd-test.local`
gets a fully-provisioned `DOCTOR` role + `TRANSCRIBE_MD` product +
fresh synthetic Practice, without ever owning a mailbox. The clinical
app does not gate the trial on a verified payment method, calendar
expiry, or any other server-side check (no `trialEndsAt`-style field
referenced anywhere outside marketing copy in
`apps/transcribe-md/src/app/signup/page.tsx:24`).

The QA-bypass adversarial-input matrix:

| Input                                          | match? | Why                                                  |
|------------------------------------------------|:-:|--------------------------------------------------------|
| `qa-x-1@quillmd-test.local.attacker.com`       | no | last `@` → domain `quillmd-test.local.attacker.com`    |
| `qa-1@quillmd-test.local%00@attacker.com`      | no | last `@` → domain `attacker.com`                       |
| `QA-X-1@QUILLMD-TEST.LOCAL`                    | YES | `.toLowerCase()` normalizes to allowlisted form (intended) |
| `qa-x-1@quillmd-test.locaI` (Cyrillic I, U+0406) | no | lowercases to `quillmd-test.locai` — Set lookup misses |
| `qa-x-1@quillmd-test.local@attacker.com`       | no | last `@` → domain `attacker.com`                       |
| `a@b@quillmd-test.local`                       | YES | last `@` → `quillmd-test.local`; documented behaviour at `email-auto-confirm.test.ts:89` |
| `attacker@quillmd-test.local`                  | YES | core attack — no real mailbox exists yet account succeeds |

The matcher itself is not the problem — it correctly accepts the
intended `qa-*-{ts}@quillmd-test.local` shape and rejects every
substring/lookalike/null-byte variant in the test matrix. The hard-coded
`REAL_MAIL_DENYLIST` (lines 32–62) defends against the
`gmail.com`-misconfiguration footgun. The defect is that the bypass is
*on at all* on the production deployment.

## Evidence

`docker-compose.yml:430-468` (transcribe-md service):
```yaml
env_file:
  - .env
environment:
  ...
  EMAIL_AUTO_CONFIRM_DOMAINS: ${EMAIL_AUTO_CONFIRM_DOMAINS:-}
```

`.env:76` (live deployment):
```
EMAIL_AUTO_CONFIRM_DOMAINS=quillmd-test.local
```

`apps/transcribe-md/src/actions/auth.ts:358-433` — the signup branch:
```ts
const autoConfirm = isAutoConfirmDomain(emailLower);
if (autoConfirm) {
  console.warn(`[QA-BYPASS] auto-confirmed email for ${emailLower} ...`);
}
const verifyEnabled = isEmailDeliveryEnabled() && !autoConfirm;
const nowForVerified = verifyEnabled ? null : new Date();
// ... user row created with emailVerified=now, no email dispatched ...
return { ok: true, redirect: '/dashboard' };
```

Rate-limit defence (`rate-limit.ts:84`) caps signups at 5/hour/IP. With
a botnet or Tor exit pool, an attacker can mint hundreds of trial
accounts per day, each granting `UPLOAD: 20/hour` against Deepgram +
Anthropic spend.

## Risk

1. **Unbounded API-cost farming.** Each freshly-minted
   `*@quillmd-test.local` account can drive 20 uploads/hour of paid
   Deepgram audio ingest + Anthropic SOAP-generation per the
   `RATE_LIMITS.UPLOAD` rule. No `trialEndsAt`-style lockout enforces
   the "Free for 14 days" promise from marketing copy.
2. **Audit-log poisoning.** Every fake account writes `LOGIN_SUCCESS` /
   visit-create rows to the same audit table the platform-admin uses
   to triage real incidents. A few hundred bot signups bury legitimate
   signal.
3. **Compliance footgun.** A medical-scribe SaaS billing itself as
   HIPAA-aware that allows pseudonymous signups with no email-of-record
   creates ambiguity about who's accountable for any PHI uploaded
   under those accounts during a breach investigation.
4. **Pre-pilot brand risk.** A single tweet of "Hey QuillMD, your
   signup form lets anyone in without an email" the week before
   pilot-launch is materially bad PR.

## Recommended fix

Two complementary mitigations:

1. **Remove the bypass from production env.** Set
   `EMAIL_AUTO_CONFIRM_DOMAINS=` (empty) in the live `.env`, recreate
   the `transcribe-md` container. The QA harness should run against a
   separate staging deployment that holds its own
   `EMAIL_AUTO_CONFIRM_DOMAINS=quillmd-test.local` setting; production
   never carries it.

2. **Belt-and-braces in code.** Make `isAutoConfirmDomain()` short-
   circuit to `false` whenever `process.env.NODE_ENV === 'production'`
   *unless* a second explicit opt-in like
   `EMAIL_AUTO_CONFIRM_ALLOW_PROD=true` is also set. That way an
   accidental prod env-var carry-over from a future config refactor
   still fails closed.

Optional polish: enforce a server-side trial expiry (`trialEndsAt`)
that disables `UPLOAD` once the 14-day window passes, regardless of
how the account was created. That's a CRM/billing-side fix outside
this domain but it converts this finding from "blocking attack" to
"manageable cost ceiling".
