# Activation criteria — HIPAA Compliance Auditor

> **Status: design only.** Per-phase activation gating
> distinguishes this agent from the other two — most
> phases can run today; a few wait for pilot data.

## Per-phase gating (the novel piece)

Most agent designs are all-or-nothing. This agent is **staged**:

| Phase | Citation | Gate | Runs today? |
|---|---|---|---|
| 0 | n/a | — | ✅ |
| 1 | §164.312(a) | ≥3 active accounts | ✅ (currently met: QA test user + Kasra + ≥1 other) |
| 2 | §164.312(b) | ≥20 visits + ≥3 doctors | ❌ pilot-data-gated |
| 3 | §164.312(c) | ≥20 visits + ≥3 doctors | ❌ pilot-data-gated |
| 4 | §164.312(d) | ≥3 active accounts | ✅ |
| 5 | §164.312(e) | — | ✅ |
| 6 | §164.310 | — | ✅ |
| 7 | §164.308 | — | ✅ |
| 8 | operational hardening | — | ✅ |
| 9 | reporting | depends on which phases ran | ✅ (renders partial report) |

**Initial activation enables phases 0 / 1 / 4 / 5 / 6 / 7 /
8 / 9** — most of the agent's value, runnable today.

**Mid-pilot activation enables phases 2 + 3** when pilot
data threshold is met (same threshold as
`ai-pipeline-auditor`).

The partial-coverage report from initial activation is
itself useful — it's the fastest path from "we have
nothing" to "we have a recurring compliance signal." A
report saying "Phases 2+3 ran with NO_DATA: only N visits
in window" is an honest signal that the operator can show a
BAA reviewer alongside the rest.

## Why this gating shape

**Phases 0, 5, 6, 7, 8** read structural facts (schema,
TLS config, encryption flags, BAA tracker doc, Caddy
config) that exist regardless of pilot data. Running them
today produces real signal.

**Phases 1 + 4** need at least a few users to detect
cross-tenant patterns + auth hygiene. The current account
count meets this threshold (the QA test user + Kasra at
minimum; usually 3+).

**Phases 2 + 3** need pilot data because:
- Phase 2's "PHI-read missing audit emit" check requires
  real READ events to verify against
- Phase 3's "transcript mutated post-sign" check requires
  signed visits to baseline against

Without pilot data, these phases would emit NO_DATA across
the board — fine in principle, but the signal is weaker
than running the schema-sanity portion of those phases
which IS today-runnable. Activation defers them so the
report stays clean.

## Pre-activation safe operations

These can run **before** activation. They produce no
findings (no `SKILL.md` exists yet, so Lead can't invoke
the agent properly), but the operator can manually run the
phase-0 schema-sanity script to validate the data contract:

### Schema sanity (Phase 0 standalone)

Reads `packages/db/prisma/schema.prisma` + queries
`information_schema.columns` against the live DB. Confirms
every column the auditor depends on (`data-sources.md` §1)
exists.

**Acceptance.** Zero `SCHEMA_GAP` markers across the data
sources. Markers fail the activation runbook — fix sources
before activating.

### Doc presence check

Reads `docs/compliance/baas.md`,
`docs/compliance/contingency-plan.md`,
`docs/compliance/workforce-training.md`,
`docs/compliance/super-admins.md`. Confirms each is
present + parseable in the expected schema.

**Acceptance.** All four present + parseable. Missing docs
fail the activation runbook — Step 1 below addresses.

### Route-to-action map presence

Reads `qa-interaction-auditor/skills/site-map.md` (the
existing route inventory) + cross-references against an
expected-emit-action map maintained at
`docs/compliance/route-action-map.md` (Step 4 below).

## Activation runbook

Staged in two phases — **initial** (most of the agent
turns on) and **mid-pilot** (the remaining 2 phases turn on
when data threshold is met).

### Initial activation (no data threshold)

#### Step 1 — Author canonical compliance docs

The auditor depends on operator-maintained docs. Land
these in a single PR before initial activation:

- `docs/compliance/baas.md` — vendor BAA tracker (table
  shape in `data-sources.md` §2)
- `docs/compliance/contingency-plan.md` — backup runbook +
  last-restore-drill date
- `docs/compliance/workforce-training.md` — per-person
  training log (domain-only emails)
- `docs/compliance/super-admins.md` — allowlist of expected
  SUPER_ADMIN accounts

These docs are operator-maintained. Future updates land in
their own PRs as roles change, BAAs renew, drills run, etc.

#### Step 2 — Add `COMPLIANCE_AUDIT_RUN_COMPLETED` AuditAction

Schema migration to add the enum value. Hand-written per
the project's Prisma migration workflow (memory note: the
`migrate dev` path is blocked by the `t_m24_smart_inject`
checksum drift; use `migrate diff` + hand-write folder +
`db-migrate` profile / `migrate deploy`).

Also add `COMPLIANCE_FINDING_SURFACED` for per-finding
emit.

Update `apps/transcribe-md/src/lib/audit.ts`'s `AuditAction`
TypeScript union to match.

#### Step 3 — Postgres SELECT-only role

Create `hipaa_compliance_auditor` role with SELECT on the
data sources in `data-sources.md` §1 + USAGE on the
relevant schemas. Even though every query is SELECT,
enforcing it at the role level is the right defense-in-
depth.

Connection string lives in `/opt/meddoc-pro/.env` as
`HIPAA_AUDITOR_DATABASE_URL` — not committed.

#### Step 4 — Author route-to-action map

`docs/compliance/route-action-map.md` — for every
PHI-bearing route in the app, document the expected
`VIEWED_X` audit action. Used by Phase 2's PHI-read coverage
check.

The map looks like:

```
| Route | Method | PHI access? | Expected audit action |
|---|---|---|---|
| /dashboard | GET | Yes (visit list) | VIEWED_DASHBOARD |
| /visits/[id] | GET | Yes (full visit) | VIEWED_VISIT |
| /visits/[id]/record | GET | No (record interface, no read) | (none expected) |
| /patients/[id] | GET | Yes | VIEWED_PATIENT_FILE |
| ... |
```

Cross-reference against
`qa-interaction-auditor/skills/site-map.md` so the two
agents stay in sync.

#### Step 5 — Author the per-phase audit scripts

```
scripts/audit-phase-0-schema.mjs
scripts/audit-phase-1-access-control.mjs
scripts/audit-phase-4-authentication.mjs
scripts/audit-phase-5-transmission.mjs
scripts/audit-phase-6-physical-attestation.mjs
scripts/audit-phase-7-administrative.mjs
scripts/audit-phase-8-encryption-posture.mjs
scripts/audit-phase-9-report.mjs
scripts/audit-all.mjs        ← orchestrator
scripts/lib/audit-base.mjs   ← shared helpers (DB connection, NDJSON emit, bucketing, ID hashing, OCR-candidate flag)
```

Phases 2 + 3 scripts are NOT authored at initial activation
(they'd emit NO_DATA across the board). Add at mid-pilot.

#### Step 6 — Cron wiring

Cron job at 03:30 UTC nightly (mirrors the existing
T-M17.3 stale-visit-cleanup cron's window). Cron emits a
heartbeat `COMPLIANCE_AUDIT_RUN_COMPLETED` audit row even
on clean runs. Cron config lives in
`apps/transcribe-md/src/worker/cron/` per the existing
pattern.

Alert routing for P1 findings: Sentry capture (when
Sentry's BAA is signed + DSN populated) OR email to
`compliance@ashtechgroup.com`. Operator picks the routing
at this step.

#### Step 7 — Add `SKILL.md`

Create `SKILL.md` in this directory with:

```yaml
---
name: hipaa-compliance-auditor
description: Audits QuillMD's HIPAA compliance posture: §164.308 (admin) + §164.310 (physical attestation) + §164.312 (technical — access control, audit controls, integrity, auth, transmission). Read-only against audit_logs + users + sessions + filesystem + container env. Does NOT read PHI content; counts bucketed; IDs hashed in reports.
---

# QuillMD HIPAA Compliance Auditor

## Identity

I am the QuillMD HIPAA Compliance Auditor. ...
```

`name` field uses the dirname (`hipaa-compliance-auditor`);
the description's first sentence is what Lead sees in the
skill list. The skill system reads the frontmatter on next
session start; its presence is how Lead becomes able to
invoke this agent.

#### Step 8 — Update `.claude/agents/README.md`

Flip this agent's status from DORMANT to **active
(initial)** in the top-level table. Once mid-pilot
activation lands, update again to **active (full)**.

#### Step 9 — First report

Run `scripts/audit-all.mjs --skip-phases 2,3` (since those
aren't implemented yet). Review the report. Ship as
`docs/compliance-audit-reports/v0-initial-<UTC>.md`.

Re-run weekly until the first nightly cron run completes
to verify the schedule + alert routing work end-to-end.

### Mid-pilot activation (when pilot threshold met)

When `ai-pipeline-auditor`'s gate is met (`≥20 visits
across ≥3 doctors` in `transcribe_visits`), run:

#### Step 10 — Author phases 2 + 3 scripts

Per `methodology.md` Phase 2 (audit controls) + Phase 3
(integrity).

#### Step 11 — Re-baseline

The first run of phases 2 + 3 publishes baselines to
`fixtures/`:

- `fixtures/audit-action-emission-rates-v1.json` — expected
  rate per action
- `fixtures/timestamp-monotonicity-tolerance-v1.json` —
  per-target acceptable skew window
- `fixtures/transcript-immutability-v1.json` — the
  signed-vs-unsigned column-write expectations

Bake into the auditor's defaults; future runs alert on
deviations.

#### Step 12 — Update SKILL.md

Update the `description:` field to remove the "(initial
coverage; phases 2+3 not yet implemented)" caveat from the
description if it's there. Re-flip status in
`.claude/agents/README.md` to `active (full)`.

## Pre-activation polish backlog

Captured here so future-Kasra has a tracked list. None are
BAA-blocking; none currently prioritized.

1. **Build `docs/compliance/baas.md`** — vendor BAA tracker
   table. Today scattered across `docs/COMPLIANCE_REGISTER.md`
   + `docs/runbooks/sentry-setup.md` + commit messages.
2. **Build `docs/compliance/contingency-plan.md`** as the
   canonical backup runbook (RPO/RTO/restore drill cadence).
3. **Build `docs/compliance/workforce-training.md`** as the
   training log template.
4. **Build `docs/compliance/super-admins.md`** as the
   SUPER_ADMIN allowlist.
5. **Build `docs/compliance/route-action-map.md`** —
   route → expected `VIEWED_X` action (Phase 2 input).
6. **Build the schema-integrity baseline** — which columns
   are expected NOT NULL, which have constraints. JSON
   snapshot at `fixtures/schema-integrity-baseline-v1.json`.
7. **Build the per-phase audit scripts** — 8 phase scripts
   + orchestrator (Step 5 above).
8. **Build the report-rendering pipeline** — markdown
   report with sections per HIPAA rule + bucketed counts +
   short-hashed IDs.
9. **Build the cron wiring** — nightly schedule + alert
   routing for P1 findings (Sentry vs email vs Slack
   decision at activation).
10. **Add the OCR-reportable-finding flagging surface** —
    findings carry the candidate flag; operator + counsel
    workflow needs documenting (where the flag goes, who
    reviews, what triggers a §164.404 analysis).
11. **Add the auditor's own self-audit** — verify the
    auditor itself emits a `COMPLIANCE_AUDIT_RUN_COMPLETED`
    audit row when it runs. Recursive but real:
    §164.312(b) requires audit-of-audit-mechanism
    reliability.
12. **Add a Postgres SELECT-only role**
    (`hipaa_compliance_auditor`) — Step 3 above.

Items 1–4 are cross-agent — they support not just this
auditor but also general compliance posture. Probably ship
in their own PR before activation work begins.

## What activation does NOT require

- **A new BAA.** This agent calls no external services. It
  reads its own DB + filesystem + Caddyfile.
- **A new container.** Runs as a one-off Node script
  (mirrors the qa-agent + ai-pipeline-auditor pattern).
- **A cost budget.** Read-only queries are free.
- **A new domain or DNS change.** Reports go to the
  filesystem under `docs/compliance-audit-reports/`.

## Decision log (filled at activation)

| Date | Decision | Rationale |
|---|---|---|
| TBD | Alert routing for P1 findings | (Sentry vs email vs Slack) |
| TBD | Postgres role created | (defense-in-depth) |
| TBD | Initial activation operator | (who pressed the button) |
| TBD | Mid-pilot activation date | (when pilot threshold met) |
| TBD | First baseline run sha + report path | |
| TBD | OCR-reportable-finding workflow | (counsel review process documented) |
| TBD | Cron schedule final | (UTC time + day-of-week if not nightly) |
