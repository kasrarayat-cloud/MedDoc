# FOUNDATION — SPEC

**Status: CONTRACT, Phase 0. Nothing here has been built.**
Written 2026-08-04. Owner brief carried verbatim; see "Provenance" at the end.

This document is the architecture. It is deliberately separate from
`DISCOVERY.md` (what is true about the system today) and `RELAY.md` (the order
in which the work happens). When the three disagree, **SPEC states the intent,
DISCOVERY states the facts, and RELAY states the sequence** — and a conflict
between SPEC and DISCOVERY is a finding, not a typo.

Three programs, in dependency order:

| Program | What it establishes | Depends on |
|---|---|---|
| **TEAMS** | A practice is a real tenant, with members, roles and a fail-closed data boundary | — |
| **BILLING** | Metered usage, a practice wallet, and money that reconciles | TEAMS (the wallet is per-practice) |
| **ADMIN** | One platform-operator surface; the legacy CRM deleted last | TEAMS + BILLING (admin shows what they produce) |

---

## 1. TEAMS

### 1.1 The practice is the tenant

- **Practice entity.** Already exists (`model Practice`, `packages/db/prisma/schema.prisma:491`). This is a completion, not a greenfield build — see DISCOVERY §B.
- **Personal-practice backfill for every existing user.** Every user gets a
  practice. Today 196 of 196 users already have one; the backfill is therefore
  about the rows *below* the user, not the user row itself.
- **`practiceId` on Patient and Visit.** `TranscribeMdPatient` already carries
  it. `TranscribeVisit` does not, and that is the gap the whole program turns
  on: a visit's tenant is currently *derived* (two independent paths), never
  *stored*, so no database-level constraint can exist.
- **`createdBy` / `signedBy` attribution.** Neither column exists on
  `transcribe_visits` today. `signedAt` exists; the signer does not. In a solo
  practice the owner and the signer are the same person and the absence is
  invisible. In a multi-seat practice they stop being the same person, and the
  row will silently claim the owner signed it. **This is why attribution is in
  the same phase as the tenant column, not a later polish item.**

### 1.2 Roles

Three roles: **OWNER**, **CLINICIAN**, **TECH**.

- **Signing is role-gated, server-side, fail-closed.** The gate lives in the
  server action / route handler, not in the UI, and the default for an
  unrecognised or absent role is *refuse*. The existing precedent is
  `POST /api/visits/[id]/sign` — already the sole SIGNED-writer, already the
  place the attestation refusal lives.
- A UI that hides the Sign button is not the gate. The gate is the refusal, and
  the refusal is audited.

### 1.3 Invites

- **Invites extend to carry practice + role.** An invite code today mints a
  user; after this it mints a *member of a named practice with a named role*.
- Invite issuance already exists as a script and is already audited. The change
  is the payload, plus the UI in ADMIN §4.3.

### 1.4 The data boundary

- **ONE practice-scoped data accessor.** Every read and write of a clinical
  table goes through it. It takes the practice as an argument; it does not read
  the session itself.
- **A guard test forbids raw clinical-table access outside it.** This is the
  load-bearing piece — the accessor without the guard is a convention, and
  conventions decay. The guard is a source-level test (the house pattern:
  `gate-*` specs that grep the tree), and it must be **negative-controlled** —
  introduce a raw `prisma.transcribeVisit.findMany` outside the accessor and
  watch it redden, then restore.
- **Audit rows gain `practiceId`.** They already have the column. What they do
  not have is a trustworthy value — see DISCOVERY §B.14, the `'clinic_main'`
  fail-open fallback. **The fallback must become a refusal or an explicit
  `null`, never a silent write into the largest shared practice.**

### 1.5 Fail-closed backfill

The stated end state: **no clinical row without a `practiceId` after migration.**

Two named exclusions, both of which must be written into the migration rather
than discovered by whoever runs it:

- `audit_logs.practiceId` is **deliberately nullable** (S4c — an audit row must
  outlive the practice it describes). It is excluded by name, with the S4c
  reasoning cited, so that a future tidy-up does not "fix" it and re-break
  account deletion.
- `note_templates` has two platform-global rows with `doctorId = NULL`. Either
  the rule carries an explicit carve-out for platform-global templates, or
  those two rows get a sentinel practice. A blanket `NOT NULL` breaks them.

---

## 2. BILLING

### 2.1 Money

- **Integer micro-unit money.** No floats anywhere in the ledger. The unit is
  fixed once and never re-scaled.
- **Append-only `LedgerEntry`**, with kinds: `grant`, `topup`, `usage`,
  `refund`, `adjustment`, and a **`balanceAfter`** on every row. Append-only
  means no `UPDATE`, no `DELETE` — a correction is another row.
- **Practice wallet.** The balance is a property of the practice, not the user.

### 2.2 The meter

- **`UsageEvent` per pipeline stage**, carrying:
  - **vendor-reported units** — tokens as the vendor reported them, audio
    seconds as the vendor reported them. Not computed, not inferred.
  - a **versioned price-table snapshot** — the row records which price table
    priced it, so a later rate change never re-prices history.
  - **idempotency on the vendor request id.** *This does not exist today —
    no vendor request-id is captured anywhere on any success path. See
    DISCOVERY §C.6. It is the single largest build item in the meter.*
- **`charge = cost × 1.5`, exact.** Exact means the multiplication happens in
  integer micro-units with a stated rounding rule, not `Math.round(cost * 1.5)`
  on a cents float.

### 2.3 Payment

- **Stripe Checkout only.** No PAN ever reaches this system.
- **No PHI in Stripe metadata.** The permitted identifiers are `Practice.id`
  and `User.id`. Visit ids and patient ids are forbidden — a visit id
  dereferences to `patientName` in one hop.
- **⚠ `BillingEvent` is not an invoice.** It is an existing clinical *claims*
  record with a required `patientId` (`schema.prisma:1373`). Its primary key
  dereferences to a named patient. It must never appear in Stripe metadata, and
  the billing program should consider renaming it to remove the trap.

### 2.4 Behaviour

- **$10 promo bucket, separate from paid balance.** Two buckets, not one number
  with a note.
- **Fail-closed insufficient-balance block.** Insufficient balance blocks the
  work. Fail-closed here means: if the balance cannot be read, block.
- **System-fault auto-credit via DLQ classification.** A visit that fails
  because *we* broke is credited back, and the classifier that decides
  "system fault" reads the DLQ. This makes `/admin/queues` load-bearing for
  money as well as for operations — see ADMIN §4.2.
- **Prod-only billing writer — refuses in QA/mock.** The writer asserts it is
  in production and refuses otherwise. The house precedent is
  `scripts/check-qa-mock-posture.sh`, whose own header records why: a
  `${VAR:-default}` in the QA compose file inherits the production value.
  **`STRIPE_SECRET_KEY` joins that script's `KEYS` list in the same change that
  introduces it.**
- **Monthly reconciliation report.** Our ledger vs the vendors' invoices, line
  by line. This is what the vendor request id exists for.

---

## 3. ADMIN

- **Platform `ADMIN` flag.** A platform-level entitlement, not a per-practice
  role. `SUPER_ADMIN` already exists as a `Product` enum value and the current
  `/admin` surface already gates on it with MFA + a 12-hour freshness ceiling.
- **Audited `ADMIN_*` actions.** Every one. ⚠ `audit_logs.action` is a
  **Postgres enum**: a label added only to the TypeScript union is discarded
  silently by a fire-and-forget writer. Every new `ADMIN_*` label needs a
  Prisma migration in the same change. (This exact bug shipped once —
  commit `535d30d9`.)

### 3.1 Ops

- Queues / DLQ **absorbed** — the existing `/admin/queues` page becomes part of
  the admin surface properly, including a navigation entry (it currently has
  none and is reachable only by typing the URL).
- Standing checks — the five read-only scripts in AGENTS.md, surfaced.
- Audit viewer.

### 3.2 Business

- Practices / members.
- Invite issuance UI.
- Usage + revenue.
- Price-table editor — the versioned table BILLING §2.2 snapshots from.

### 3.3 The rule

**ZERO clinical content in admin.** No note text, no patient names, no
transcripts. Counts, costs, statuses, ids. This is the constraint that decides
ambiguous cases, and it is not negotiable for convenience.

---

## 4. GATE 0 rulings — decided 2026-08-04

Phase 0 deliberately did not make these. The war room did. **Recorded verbatim
from the ruling; the commentary under each is a pointer, not an amendment.**

### 4.1 The 12 `MEDDOC_PRO`-only accounts

> **EXCLUDED from backfill, DEACTIVATED (login disabled), rows retained — no
> deletion. Owner veto window is open until the TEAMS migration runs.**

Four of the twelve are on `@meddoc.com` carrying the operator's own name,
created on the project's first two days, all with a real login (DISCOVERY §A.5).
Deactivation is reversible and deletion is not, which is what makes the veto
window meaningful. **The window closes when the TEAMS migration runs** — that
is item **T7**, and whoever runs it must confirm the veto has lapsed before
excluding these rows.

### 4.2 Cross-app redirect users

> **Classify by where clinical data lives — transcribe-md data → normal
> personal-practice backfill; none → the deactivation bucket.**

The classifier is data, not entitlement: a `MEDDOC_PRO` product row says what
someone was *given*, not what they *did*. The query is "does this user own any
`transcribe_visits` / `transcribe_md_patients` row", and it must be run at
migration time, not copied from this document.

The redirect itself (`actions/auth.ts:227-241`) is retired in item **A5**, and
the two must land together — removing the redirect while a live account still
needs it leaves a login error whose only offered remedy is a dead link.

### 4.3 Templates

> **PER-DOCTOR in TEAMS v1 (solo behavior unchanged); practice-shared library
> recorded as a post-TEAMS flag item.**

This means `note_templates_one_active_per_doctor_encounter` — the unique index
keyed on `("doctorId","encounterType")` — **stays as it is**, and DISCOVERY §B.9
should be read as "correct for v1" rather than as a defect. The two
platform-global rows with `doctorId = NULL` still need the explicit carve-out
from §1.5; that part is unchanged.

**Post-TEAMS, flag-gated:** a practice-shared template library. Filed, not
scheduled.

### 4.4 Money

> **Integer MICRO-DOLLARS ledger-wide; charge = cost_micro × 3 / 2 in integer
> math, round half-up at the micro-dollar, cent rounding at display only; rule
> goes verbatim into SPEC and the future ToS-wording task.**

Restating the two properties that a future implementer is most likely to erode:

- `× 3 / 2`, in that order, in integer arithmetic — **not** `* 1.5`, which is a
  float and reintroduces the drift the micro-dollar unit exists to prevent.
- **Cent rounding is a DISPLAY concern only.** Nothing in the ledger, the
  wallet, or the reconciliation report ever rounds to cents. A cent-rounded
  value that gets written back is a value that no longer reconciles.

**Downstream task, recorded here so it is not lost:** the ToS wording must
state the multiplier in the same terms the code uses.

### 4.5 Resend, and the price table's provenance

> **NOT metered — subscription folds into margin; only per-run vendors
> (Anthropic, Deepgram) produce UsageEvents. Price-table schema gains
> PROVENANCE per rate (published URL + date / invoice-derived /
> console-quoted); nova-3-medical seeds from invoice/console truth, never the
> undated post; the 3.4× in-code Deepgram rate is corrected by the price table
> when BILLING lands — no billing math ships before then.**

Three consequences worth spelling out:

- `UsageEvent` is for **per-run** vendors only. Resend's 219 rows in
  `api_usage_events` (all with a NULL `userId`) stop being a billing input and
  become a cost line in the monthly reconciliation.
- **PROVENANCE is a required column, not a comment.** Every rate carries one of
  `published` (URL + read-date), `invoice`, or `console`. DISCOVERY §D is a
  `published`-provenance seed for Anthropic, OpenAI and Resend — and explicitly
  **not** a valid seed for `nova-3-medical`, whose only public figure is an
  undated announcement post.
- **The in-code `$0.0145/min` Deepgram default is NOT patched now.** It is
  wrong by ~3.4× against the vendor's published figure, and it feeds only
  `costUsdCents` on observability rows today — no doctor is billed from it,
  because no billing math exists. It is corrected by the price table in item
  **B3**, with provenance, and **no billing math ships before then.** Changing
  the constant now would silently re-base a year of historical `ai_calls`
  comparisons for no benefit.

---

## 5. Still open

1. **Whether `stripe`/`@stripe/stripe-js` stay in `apps/meddoc-pro/package.json`.**
   → **RESOLVED 2026-08-04: removed.** They were unused by any import and *did*
   ship inside the live clinical worker image. BILLING reintroduces the SDK
   properly, web-side only. See DISCOVERY §E.2.
2. **`worker.ts:983` read-after-write.** The per-visit cost sum reads `ai_calls`
   in the same tick-chain that wrote it. Left UNSURE by Phase 0 — not
   reproduced either way. **Carried as a named open item on the TEAMS gate**,
   not silently dropped.

---

## Provenance

The architecture above is the owner's brief of 2026-08-04, carried across
without softening. Its own words, for the record:

> Practice entity, personal-practice backfill for every existing user,
> practiceId on Patient/Visit with createdBy/signedBy attribution, roles
> OWNER/CLINICIAN/TECH with sign role-gated server-side fail-closed, invites
> extended to carry practice+role, ONE practice-scoped data accessor with a
> guard test forbidding raw clinical-table access outside it, audit rows gain
> practiceId; billing: integer micro-unit money, append-only LedgerEntry
> (grant/topup/usage/refund/adjustment, balanceAfter), UsageEvent per pipeline
> stage with vendor-reported units + versioned price-table snapshot +
> idempotency on vendor request id, charge = cost × 1.5 exact, practice wallet,
> Stripe Checkout only (no PAN handling, no PHI in Stripe metadata), $10 promo
> bucket separate from paid balance, fail-closed insufficient-balance block,
> system-fault auto-credit via DLQ classification, prod-only billing writer
> (refuses in QA/mock), monthly reconciliation report; admin: platform ADMIN
> flag, audited ADMIN_* actions, ops (queues/DLQ absorbed, standing checks,
> audit viewer), business (practices/members, invite issuance UI, usage+revenue,
> price-table editor), ZERO clinical content in admin.

Everything in this file that is *not* in that paragraph is either a pointer
into DISCOVERY or a flagged open question in §4 — it is not a decision I made
on the owner's behalf.
