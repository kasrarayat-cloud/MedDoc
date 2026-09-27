# V1 application settings

The settings that take QuillMD from the private synthetic system to an invited, real-patient V1.
**Every default is the private synthetic system exactly as it was.** An unrecognised value makes the
process refuse to start; it never selects a mode by accident. Refusal messages name settings,
never their values.

Code: `rebuild/quillmd/application_profile.py` (parsing and startup checks) and
`rebuild/quillmd/settings.py`. Tests: `rebuild/core/tests/test_v1_*.py`.

## The settings

| Setting | Default (today) | V1 production value | What it gates |
|---|---|---|---|
| `QUILLMD_DATA_MODE` | `synthetic` | `real` | `synthetic`: synthetic attestations, the "Synthetic data only" banner, synthetic copy, `/health/` `data_mode: synthetic-only`. `real`: attestations, banner and synthetic copy removed; `/health/` reports `real`; **the process refuses to start** unless every row marked *required by real* below is set as shown. |
| `QUILLMD_REGISTRATION` | `open` | `invite` (required by real) | `invite`: `/register/` answers 404 on both surfaces and is not linked from sign-in. New clinics arrive only through a console **Invite clinic owner** invitation; colleagues through the existing department invitations, unchanged. A verification link of an account registered before the switch still proves the mailbox, but no longer creates a personal organization or grants credit: that account joins a clinic by invitation. |
| `QUILLMD_WELCOME_CREDIT` | `10` | owner's decision | The one-time promotional grant per newly verified account, US dollars in whole cents, 0 to 500. `0` grants nothing, writes no ledger entry and removes the promise from every screen and message (sign-up, clinic invitation, verification, Billing, Organization); any other value is the amount those screens state. Ledger entries already written keep the amount they record; the console's **Promotional credit granted** sums those entries and its definition states no per-account amount, so a later change to this setting cannot contradict it. |
| `QUILLMD_MFA_REQUIRED_ALL` | `0` | `1` (required by real) | `1`: every sign-in needs a confirmed TOTP authenticator, not only administrators'. An account without one signs in with its password only far enough to enrol (every other page redirects to `/mfa/`); enrolment shows the otpauth URI and the same key as grouped manual-entry text. Enables the console **Reset MFA** action. |
| `QUILLMD_STRIPE_MODE` | `test` | `live` once live payments are approved; until then `STRIPE_SECRET_KEY` unset (payments off) — required by real | `test`: byte-identical to before (sandbox keys only, `livemode=false` events only, `http://localhost:9130` return URLs, "(test)" product label). `live`: `sk_live_`/`rk_live_` keys only, `livemode=true` events only (a sandbox event or object is refused before any write), return URLs built from `QUILLMD_APP_BASE_URL`, product "QuillMD one-time wallet credit". A key of the other mode is refused at checkout in both modes, before authorization and before any provider call. Live mode **refuses to start** without a live key, a well-formed `STRIPE_WEBHOOK_SECRET` (exactly `whsec_` followed by letters and digits, no spaces — checked as the webhook uses it, unstripped), and a public HTTPS `QUILLMD_APP_BASE_URL`, and **with `QUILLMD_PREVIEW_AUTH_ENABLED=1`**: the preview gate answers 403 to Stripe's webhook, so a live payment would be charged and never credited. **Real data mode refuses to start in `test` mode while `STRIPE_SECRET_KEY` is set** (any value): a payment made with Stripe's public test card would otherwise become paid balance that funds real provider calls. As a second wall, in real data mode checkout is refused before any Payment row or provider call unless the mode is `live`, and the webhook refuses every event that is not `livemode=true` — with `test` mode and no key (payments off) it refuses every event. |
| `QUILLMD_DEEPGRAM_MIP_OPT_OUT` | unset: follows the data mode | `true` (required by real; unset means `true` in real mode) | Unset in synthetic mode: **no `mip_opt_out` parameter is sent**, the request exactly as before V1. Unset in real mode: `mip_opt_out=true` on every request; `false` refuses the start, and a real-mode worker sends nothing for a job recorded without `true`. Set explicitly, the value is recorded and sent as given. **The price effect of opting out is unverified** — see *Deepgram parameters*. |
| `QUILLMD_DEEPGRAM_SMART_FORMAT` | `false` | `true` | Deepgram smart formatting (punctuation, paragraphs, and for English dates, times, amounts and numerals as digits). `false` is the request as it always was. |
| `QUILLMD_HTTPS` | `0` | `1` (required by real) | Secure session and CSRF cookies, HTTPS redirect, HSTS. Real mode also checks the computed `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE`. |
| `QUILLMD_TRUST_PROXY` | `0` | `1` behind the host proxy | Believe the proxy's `X-Forwarded-Proto` and key per-address rate limits on the right-most `X-Forwarded-For` entry. **On the administrator surface it takes effect only with `QUILLMD_HTTPS=1`** — see below. |
| `QUILLMD_EMAIL_MODE` | `file` | `resend` (required by real) | Real mode requires `resend`: every other value, not only `file`, writes account email to the private outbox on the host, so nobody would receive a link. |
| `QUILLMD_PREVIEW_AUTH_ENABLED` | `0` | `0` (required by real) | The shared private-preview gate. Real mode refuses it, and so does live Stripe mode: it also blocks the Stripe webhook. |
| `QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME` / `_PASSWORD` | unset | unset (required by real) | The preview gate's shared login, appended to invitation and recovery email with "use only synthetic information" copy. Real mode refuses either being set to anything, whitespace included (an empty `NAME=` is unset). |
| `QUILLMD_EMAIL_ALLOWED_RECIPIENTS` | unset | unset, or a deliberate list | Not refused in real mode. When set, account email reaches only the listed addresses and every other recipient is recorded as `email.failed` and staged to the private outbox — an invited pilot with an allowlist must list every invitee. |
| `QUILLMD_APP_BASE_URL` | `http://localhost:9130` | `https://app.quillmd.com` (required by real) | The origin in every emailed link and, in live Stripe mode, the Checkout return URLs. Real and live modes require it set explicitly, `https`, origin only (no path, query, fragment or credentials — a `?` or `#` anywhere is refused, even empty), not port 0, not loopback or `testserver`, and the **doctor host only** — `https://app.quillmd.com`, optionally with `:port`, spelled exactly (lower case; no empty user or port, leading zeros, control characters or extra slashes). `admin.quillmd.com` is in `ALLOWED_HOSTS` but is refused: a clinician or payer sent there lands on the administrator surface, which answers 404 to doctor pages. |

`STRIPE_LIVE_ENABLED` is no longer a constant: it reports `QUILLMD_STRIPE_MODE == 'live'` on the
console Services page and in `manage.py configuration_status`, which also print the four new modes.

## Startup refusals, as the operator sees them

`quillmd.settings` raises `ImproperlyConfigured` before any request is served, listing every gap
at once:

```
QuillMD refuses to start: QUILLMD_HTTPS must be 1; SESSION_COOKIE_SECURE must be on (set QUILLMD_HTTPS=1); ...
```

`manage.py check` shows the same message, so a configuration can be tried before a restart.

## Real mode never spends sandbox money

**Real data mode runs on a database that has never held sandbox payments.** A database that took
sandbox (test-card) payments keeps that money in paid wallets, and real mode refuses the sandbox
refund that could remove it — so the only safe path is a database with no sandbox payment history.

- Every `Payment` records the Stripe mode its checkout was created in, and every `WebhookEvent` the
  `livemode` it was validated with (`livemode`, migration `0020`). Rows written before this change
  carry `NULL` and count as sandbox: live mode did not exist then.
- **The evidence real mode reads cannot be relabelled by the runtime database role.** Real mode
  decides from each `Payment`'s existence, wallet, status, `stripe_intent` and `livemode`, each
  `WebhookEvent`'s `livemode`, and the `payment` ledger credits. Database triggers refuse, for every
  role that has not first dropped or disabled them:
  - deleting a `Payment` (`0020`), a `WebhookEvent` (`0008`) or a ledger row (`0003`, which also
    refuses updating one);
  - changing a `Payment`'s `wallet_id`, `amount_cents` or `livemode`, or its `stripe_intent` once
    set, and any status change on a `Payment` that is `paid` (`0020`);
  - changing a `WebhookEvent`'s `livemode` (`0020`);
  - `TRUNCATE` of `core_payment`, `core_webhookevent` or `core_ledgerentry`, however reached
    (`CASCADE` from another table included): statement-level `BEFORE TRUNCATE` triggers (`0020`),
    because row-level `DELETE` triggers do not fire on `TRUNCATE`.

  Every write the application makes to a `Payment` still works: creating → pending or uncertain;
  any unpaid status → processing, failed, expired, or paid (with its `stripe_intent` in the same
  write); `stripe_session`, `checkout_url` and `request_key` where the application sets them.
- **What these triggers do not cover.** The database **owner** role (and any superuser) can drop or
  disable them, and can then delete or truncate anything; they bind the runtime role, which owns no
  table, cannot alter one, and is not granted `TRUNCATE`. They do not stop the runtime role adding
  rows or changing other tables (a wallet's balance, for one): that is not relabelling sandbox
  evidence, and the launcher's check below compares every paid wallet's balance with its ledger.
- **Reversing `0020`** refuses while any row is recorded as live: dropping the column would erase
  that evidence, and re-applying records every row `NULL`, which real mode treats as sandbox money
  it never spends. A database with no live rows still reverses, even with a trigger already missing:
  the reverse drops every trigger `IF EXISTS`, including `payment_livemode_immutable`, the name an
  earlier version used. Two earlier versions of `0020` reached `release/v1` (one installed no
  trigger, one only the two `livemode` triggers); a database that applied either never receives the
  rest (`migrate` plans nothing). It can reverse and re-apply only if it has no live rows. If live
  payments or Stripe events were recorded after the earlier `0020`, reversal refuses and a
  separately reviewed forward migration is required to install the missing guards while keeping
  that evidence. Never delete or relabel live rows to make reversal pass. The launcher check
  reports missing/altered guards until they are installed.
- A paid wallet is **sandbox-funded** when any payment not recorded as live funded it: a paid
  non-live `Payment` on it, or a `payment` ledger credit with no live `Payment`. A checkout nobody
  paid (pending, expired, failed, uncertain) put no money in the wallet and does not count.
- In real data mode **no money leaves a sandbox-funded wallet** (`core.billing.real_mode_refuses`):
  - `reserve()` refuses the whole request, before any hold, when the payer's paid wallet is
    sandbox-funded;
  - **checkout** refuses, before any `Payment` row or Stripe call, to take live money into such a
    wallet (it could never be spent), telling the payer to contact support;
  - the **worker** refuses, before any provider request, a job that any wallet holding its funds or
    its payer's paid wallet makes sandbox-funded — so a job whose hold was taken before the switch
    is refused even when that hold is wholly promotional, exactly as `reserve()` would refuse its
    payer (not processed, nothing charged, the hold released, audited as
    `usage.sandbox_hold_refused`);
  - **settlement** never debits such a wallet: if a debit would reach one it refuses before any
    write, nothing is charged, the provider receipt is kept and the job is held for reconciliation
    (audited as `job.reconciliation` with `error_class` `SandboxFundsRefused`); a sandbox hold the
    charge does not reach is released unspent;
  - a **reconciled charge** (`reconcile_usage`, and every later attempt to apply a pending one, on
    release, settlement, top-up or absorption) never comes from such a wallet: it stays
    `pending_funds`, and each attempt is audited as `usage.reconciliation_sandbox_refused`.

  A Stripe refund of a live payment is still debited: it returns live money, it spends nothing.
  Synthetic mode is unchanged.
- **`manage.py real_mode_payment_check`** is read-only (it runs in a `READ ONLY` transaction and rolls
  back) and is stricter than the per-wallet rule: it exits 1 when the database holds any payment
  (paid or not) or Stripe event row not recorded as live,
  or any paid wallet whose balance live payments do not wholly explain (a non-live credit, or a
  balance that differs from its ledger), or when any of the seven triggers above
  (`core.billing.PAYMENT_EVIDENCE_GUARDS`) is missing, disabled, replica-only, or differs from its
  installed full `pg_get_triggerdef` definition, schema-qualified function identity or `prosrc`
  SHA256. This also catches an `UPDATE OF` column restriction and a same-named function in another
  schema. The expected hashes are pinned to migration source, not learned from the inspected
  database. Any additional row or statement trigger on those three tables refuses; the only exceptions are
  PostgreSQL's internal foreign-key constraint triggers. Django creates no other row triggers
  there in this schema. Unexpected trigger names and function bodies are never printed.

  It also requires `session_replication_role=origin` both in the current connection and in the
  effective persistent default for the active runtime role/database, read from `pg_db_role_setting`:
  role+database overrides role, which overrides database, which overrides all roles/databases.
  An unrelated role's setting does not apply. `SET ROLE` alone does not apply login defaults, so
  reading only `current_setting` would miss a newly configured refusal condition. See PostgreSQL's
  [role setting precedence](https://www.postgresql.org/docs/current/sql-alterrole.html) and
  [replication setting behavior](https://www.postgresql.org/docs/current/runtime-config-client.html#GUC-SESSION-REPLICATION-ROLE).

  These are read-only catalog checks, since an amended migration never re-runs where it was
  applied. Output is counts and fixed guard/check labels only. **The launcher must run the command
  on the target database as its runtime role before starting real mode.** The result is evidence
  at that moment, not a lock against an owner/superuser who can modify both the guards and the
  checker, change permissions/configuration, or alter the database after it runs. A check inside
  every process start is not used instead: settings and
  `AppConfig.ready()` also run for `migrate`, `makemigrations`, the test runner and `collectstatic`,
  often before the database exists or is migrated, and Django advises against queries there.

## The administrator surface behind a TLS proxy

Before: `QUILLMD_ADMIN_SITE=1` forced `SECURE_PROXY_SSL_HEADER=None`, so behind a TLS-terminating
proxy with `QUILLMD_HTTPS=1` every request looked like plain HTTP — a 301 to itself, forever, and a
CSRF 403 on every HTTPS form post (demonstrated by the investigators' probe, now
`core/tests/test_v1_admin_tls.py`).

Now the administrator surface honours the proxy header when `QUILLMD_TRUST_PROXY=1` **and**
`QUILLMD_HTTPS=1`. The second condition is what keeps today's deployment unchanged: the shared
environment file sets `QUILLMD_TRUST_PROXY=1` for the doctor's proxy, while the administrator
surface is reached by an SSH tunnel straight to its loopback port, where nothing overwrites the
header. With `QUILLMD_HTTPS=1` a tunnel cannot serve that surface at all (every request redirects
to https), so the only working admin deployment with HTTPS on is behind the proxy — the case that
must trust it. The existing assertion that `TRUST_PROXY=1` alone does not change admin loopback
behaviour still holds.

## Rate limits behind the proxy

Sign-in (40 per address, 8 per email), registration (5 per address), recovery (20 per address,
3 per email) and verification resend (20 per address, 3 per email), per 10 minutes. Behind the
loopback proxy every request arrived from 127.0.0.1, so each per-address limit was one bucket for
the whole platform. With trusted-proxy mode (as effective on the surface) the key is the
**right-most** `X-Forwarded-For` entry — the one our proxy wrote; nothing to its left is read, so
a forged entry cannot buy a fresh bucket. A missing or non-address entry falls back to
`REMOTE_ADDR`, the stricter shared bucket.

⚠️ **This changes the private deployment on its next restart**, because its environment already
sets `QUILLMD_TRUST_PROXY=1` (`ops/email_activation.py` requires it): doctor-surface limits become
per client instead of platform-wide. The installed proxy (`deploy/email-private-https.conf`) sets
`X-Forwarded-For $remote_addr`, overwriting whatever the client sent, so its single entry is the
real client. A production proxy must also set it from `$remote_addr` (or append with
`$proxy_add_x_forwarded_for`); a proxy that passes the client's header through unmodified would
let a client choose its own bucket.

## Invite clinic owner

Console → **Clinic invitations** (shown in invite mode; also linked from Organizations and the
Overview). MFA-verified staff only, like every console route. The invitation records the owner's
email, the clinic (organization) name and its first department; the token is 7 days, stored only
as a sha256, and single use. Accepting (`/invite/clinic/<token>/`, doctor surface) creates the
organization, the department and the owner membership, verifies the mailbox, and grants the
welcome credit once. An existing account must be signed in as the invited address. Acceptance is
refused if the issuer is no longer an active administrator. Revoking sets `revoked_at` and ends
the link at once. Creating is available only in invite mode; listing and revoking in either.
Audit: `admin.clinic_invitation_created`, `admin.clinic_invitation_revoked`,
`clinic.invitation_accepted` — the invitation id only, no address or clinic name.

## Reset MFA

Console → an account → **Reset MFA** (shown only with `QUILLMD_MFA_REQUIRED_ALL=1`, never for an
administrator). Requires a written account of how the holder's identity was checked (at least 12
characters, kept in the audit entry) and a confirmation. Removes every authenticator on the
account, invalidates every session, and the holder enrols again after their next password sign-in.
Audit: `admin.mfa_reset` with `devices_removed`, `sessions_invalidated`, `reason`.

## Deepgram parameters

New transcription jobs record `deepgram_parameters` in `Job.config` at enqueue
(`{"model": "nova-3-medical", "smart_format": ...}`, plus `"mip_opt_out": ...` when the setting has a
value — in synthetic mode with it unset there is no such key); the worker sends exactly those. A
job queued before this change sends the request it was queued for (no smart formatting) plus the
current opt-out setting, if it has a value. An unrecognised recorded value sends nothing
(`NoProviderRequest`, nothing billable), and so does, in real data mode, any recorded request
without `mip_opt_out=true` (for example a job queued while the system was synthetic).

Sources, read 2026-09-27:

- `mip_opt_out` — <https://developers.deepgram.com/trust-security/your-data>: requests join the
  Model Improvement Program by default and are retained; "Set `mip_opt_out=true` and the request
  is excluded from model improvement"; opting out gives zero data retention. The pre-recorded API
  reference (<https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded>) lists
  `mip_opt_out` as a boolean query parameter, default false, and describes it as: "Opts out requests
  from the Deepgram Model Improvement Program. Refer to our Docs for pricing impacts before setting
  this to true. https://dpgr.am/deepgram-mip" (quoted by the refutation pass from its fetch of
  2026-09-27; not re-fetched for this correction, which made no network request).
- ⚠️ **The price effect of opting out is UNVERIFIED.** The API reference points to pricing impacts;
  the linked Model Improvement Program page and <https://deepgram.com/pricing>, as fetched, state no
  figure. An earlier version of this document said neither page states a price effect; that was
  wrong about the API reference. The quote, the charge limit and the recorded provider cost all use
  the unchanged configured `voice_rate_minute`. **If opted-out requests carry a premium, recorded
  provider cost — and the 1.5× charge computed from it — understate actual cost on every opted-out
  job.** Confirming the price (Deepgram account terms or a billing check) is an owner/account check
  before real mode. This is also why synthetic mode no longer sends the parameter by default.
- `smart_format` — same API reference: boolean, default false, "Apply formatting to transcript
  output". <https://developers.deepgram.com/docs/smart-format> describes punctuation, paragraphs,
  and for English dates, times, currency amounts, phone numbers, emails and URLs.
- Pricing — <https://deepgram.com/pricing> lists Smart Formatting as **Included** on Pay As You Go
  and Growth. It is therefore not part of the priced configuration and changes no quote; this is
  asserted in `test_v1_deepgram.py`. The pricing page does not list Nova-3 Medical separately and
  does not mention the opt-out.

## Account email copy

Subjects and bodies live in `core/email_delivery.py` `COPY`, per data mode. Synthetic copy is
unchanged byte for byte; real copy drops "test account" and "synthetic". Every template may carry
exactly one substitution field, `{link}` — a test fails if any other field is added — so nothing
from a patient, encounter, department, organization or the recipient's record can be interpolated.
A second test sends every purpose while records full of canary text exist and finds none of it in
the outbox.

## Deliberate decisions

- **The template upload attestation stays in real mode.** "This is a blank form with no patient
  data" is true and required in both modes: a template must be blank.
- **`/health/` keeps three values.** `synthetic-only`, `real`, and `live` for the guard switched
  off without the declared real profile — reachable only by overriding settings — so the existing
  positive control keeps a value that cannot pass for either mode.
- **Test-mode Stripe starts as before whatever key is present, in synthetic data mode**; a live
  key there is refused at checkout, as it always was. In real data mode any key refuses the start
  unless the mode is `live` (see `QUILLMD_STRIPE_MODE`).
- **`QUILLMD_WELCOME_CREDIT` is bounded at 500** to stop a typo minting credit that is spent on
  real provider calls. Whether V1 grants any credit is the owner's policy decision.

## Not covered here (owner or operations)

- Signed BAAs (Anthropic, Deepgram, hosting, backup storage) and the move off a host whose terms
  exclude HIPAA use. Resend cannot sign a BAA: V1 email must stay free of clinical content (it is),
  or move to a covered provider.
- A `STRIPE_WEBHOOK_SECRET` copied from the **wrong endpoint** is well formed and cannot be detected
  at start: every live event would be refused (charged, never credited). It shows up only at the
  bounded live payment test, which must be run and checked before live payments are opened.
- The production launcher must run `manage.py real_mode_payment_check` before starting real mode
  (see *Real mode never spends sandbox money*); nothing in this change wires it in.
- Backup, offsite and alert configurations (`ops/offsite_backup.py`, `ops/backup_alerts.py`) still
  require `synthetic_only: true` and will refuse to run for real data until requalified.
- The launcher, units and role tools remain pinned to this host's private target.
- The production proxy's `X-Forwarded-For` handling (see *Rate limits*).
- Deepgram opt-out pricing: confirm with Deepgram (account terms or a billing check) whether
  `mip_opt_out=true` requests are priced differently, before real mode (see *Deepgram parameters*).


## Required V1 feature configuration — 2026-09-27 continuation

The production secret renderer now accepts `QUILLMD_WM_NARRATIVE`,
`QUILLMD_MAPPING_ASSISTANCE` and `QUILLMD_MAPPING_ASSISTANCE_LIVE` only as explicit string `0` or `1`.
They remain absent/off by default. A reviewed activation may set them only after their workflow,
compatibility and exact-model qualification gates; allowing a setting does not authorize its activation.
Previously the renderer refused all three names as unknown, so the required paths could not have been
enabled on the prepared production target. Six focused renderer checks now pass.

`QUILLMD_AI_REPLAY_DIR` remains a private fixture-only setting and is refused by the production renderer.
`ANTHROPIC_BASE_URL` is also refused: the production environment cannot silently redirect native Anthropic
requests to another endpoint. Actual served-worker model/endpoint/usage evidence is still required.


### Production voice configuration correction — 2026-09-27

The environment renderer previously refused the two documented voice keys as unknown. It now accepts
`QUILLMD_DEEPGRAM_SMART_FORMAT` as literal `true` or `false`, and accepts an explicit
`QUILLMD_DEEPGRAM_MIP_OPT_OUT` only as `true`. Real mode already defaults the opt-out to true and refuses
a false value; this repairs explicit configuration without changing historical voice jobs or making a call.
The V1 smart-format value remains true, subject to actual reviewed dictation acceptance.

The backup status root operator is now explicitly represented beside the secret renderer in the unit
metadata-access check. Both must run as root; every doctor/admin/worker/heartbeat unit must still deny
both metadata addresses. The full expected six-unit set is asserted. Original five-unit failure is retained.
All fourteen renderer/unit agreement checks pass. Evidence: `integration-evidence-20260927`.
