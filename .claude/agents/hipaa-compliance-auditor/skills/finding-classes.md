# Finding classes — HIPAA Compliance Auditor

> **Status: design only.** Citations to 45 CFR Part 164 are
> grounded in the rule text; specific numeric thresholds are
> initial proposals subject to baseline-tuning at activation.

## Severity definitions (with regulatory exposure axis)

| Severity | Meaning | Operator action expected |
|---|---|---|
| **P1** | Active compliance breach OR weak posture that, if confirmed, may trigger §164.404 breach-notification analysis. Always carries `ocr_reportable_candidate: true` for findings against §164.312 rules. | Same-day investigation. Engage counsel if candidate flag is set. Block any deploy that touches the affected surface until resolved. |
| **P2** | Compliance drift / hygiene. Not a current breach; left unaddressed it tips into P1. | Triage within the week. |
| **P3** | Informational / future-risk. Includes physical-safeguard attestation findings (which the agent can't directly verify). | Backlog. |

The `ocr_reportable_candidate` flag is set on P1 findings
that, IF confirmed by investigation, may trigger §164.404
notification to OCR (Office for Civil Rights). The auditor
NEVER decides reportability — counsel does.

## Per-finding shape

Every finding emits these fields:

```json
{
  "severity": "P1",
  "phase": 2,
  "hipaa_section": "164.312(b)",
  "title": "AuditAction LOGIN_FAILED has zero rows in last 30 days",
  "what_the_data_says": "Enum value present in code; 0 rows emitted in audit_logs window. Emit-site grep shows 1 reference at apps/transcribe-md/src/lib/audit.ts:NN.",
  "why_it_matters": "164.312(b) requires audit-log mechanisms for activity in PHI systems. A wired-but-silent action means the mechanism is incomplete; inability to reconstruct failed-login attempts is a documented OCR finding pattern.",
  "suggested_investigation": "Verify the emit site is reachable; spot-check a deliberate failed login + look for the row.",
  "closure_criteria": "≥1 LOGIN_FAILED row in audit_logs within 24h after operator-confirmed failed login attempt.",
  "ocr_reportable_candidate": true,
  "window": { "start": "<UTC>", "end": "<UTC>" },
  "sample_count": 0,
  "metric": "audit_action_emission_count_30d"
}
```

`title` is one line, severity-grouped at the top of the
report. Bodies in the drilldown.

## P1 — active compliance breach

### §164.312(a) gaps (Phase 1)

#### P1.1.1 SUPER_ADMIN expansion without audit row

**Trigger.** A user with `role = 'SUPER_ADMIN'` whose grant
is not preceded by a `USER_GRANTED_SUPER_ADMIN` audit row
within the prior 24h window.

**Why P1.** §164.312(a) requires access controls be granted
"as specified in §164.308(a)(4)." Granting SUPER_ADMIN
without an audit trail breaks the §164.308(a)(4)(ii)(A)
authorization process. **OCR-reportable candidate.**

**Closure.** Either (a) the historical audit row is found +
linked, OR (b) the entitlement is revoked, OR (c) a
backdated audit row with operator-attested provenance is
created (last resort; should be rare).

#### P1.1.2 Cross-tenant session

**Trigger.** Active session with `practiceId` ≠ the user's
current `practiceId` at the time of issue.

**Why P1.** §164.312(a)(2)(i) — "unique user
identification." Cross-tenant session bleed allows a user to
read PHI for a practice they don't belong to. **OCR-reportable
candidate.**

**Closure.** Session terminated; root cause identified;
regression test added.

#### P1.1.3 Inactive SUPER_ADMIN (>30 days)

**Trigger.** Account with `role = 'SUPER_ADMIN'` and
`lastLogin > 30 days ago`.

**Why P1.** Admin attack surface should be minimized.
Inactive admins are credential-theft targets disproportionate
to their value. **Not directly an OCR finding** but the
posture failure compounds with any §164.312(d) MFA gap.

**Closure.** Account deactivated, role downgraded, OR
operator-attested justification documented (e.g. "this is
the on-call rotation account").

### §164.312(b) gaps (Phase 2)

#### P1.2.1 AuditAction wired-but-silent

**Trigger.** An enum value in the `AuditAction` Postgres
enum that has zero rows in `audit_logs` within the last 30
days. Excluded list maintained for actions that fire only
on rare conditions (e.g. emergency-access).

**Why P1.** §164.312(b) requires "mechanisms that record
and examine activity." A wired-but-silent action means the
mechanism is incomplete. **OCR-reportable candidate.**

**Closure.** Either (a) ≥1 row emitted by an
operator-confirmed exercise of the action, OR (b) the
action is removed from the enum (cleanup), OR (c) the
action is added to the excluded-list with documented
justification.

#### P1.2.2 PHI-read missing audit emit

**Trigger.** A route in `apps/transcribe-md/src/app/`
serving PHI (per the route-to-action map in
`activation-criteria.md`) without a corresponding
`VIEWED_X` audit emit on the render path.

**Why P1.** §164.312(b) requires audit of access to PHI.
Reads count as access. **OCR-reportable candidate.**

**Closure.** Audit emit added at the render path; the
auditor's next run confirms emission on a sample read.

#### P1.2.3 Audit-log UPDATE detected

**Trigger.** `pg_stat_user_tables.n_tup_upd` for
`audit_logs` is non-zero.

**Why P1.** Audit logs must be append-only. UPDATEs to
existing rows invalidate the §164.312(b) mechanism (a row
that can change isn't an audit row). **OCR-reportable
candidate.**

**Closure.** Find + remediate the UPDATE source; consider
adding a Postgres trigger to forbid UPDATEs at the table
level.

### §164.312(c) gaps (Phase 3)

#### P1.3.1 Transcript mutated post-sign

**Trigger.** A visit with non-NULL `signedAt` whose
`transcriptText` or `transcriptRaw` was modified after
`signedAt` (detected via `audit_logs` write trail or
column-history table when one exists).

**Why P1.** §164.312(c) — "protect electronic protected
health information from improper alteration." Modifying
post-sign content breaks the integrity of the signed
record. **OCR-reportable candidate.**

**Closure.** Investigate the mutation source; restore the
original content if recoverable; revoke + regenerate the
sign-off if not.

### §164.312(d) gaps (Phase 4)

#### P1.4.1 Admin account without MFA

**Trigger.** Any account with role `SUPER_ADMIN` or `ADMIN`
with `mfaEnabled = false`.

**Why P1.** §164.312(d) — "verify that a person … is the
one claimed." Admin-tier accounts without MFA are
credential-theft targets that, if compromised, can read
all practices' PHI.

**Closure.** MFA enforced + verified; any account that
can't or won't add MFA must be downgraded to a non-admin
role.

### §164.312(e) gaps (Phase 5)

#### P1.5.1 Plaintext transmission active

**Trigger.** `http://app.quillmd.com/` or
`http://quillmd.com/` responds with content (200/) instead
of redirecting (3xx) to https://.

**Why P1.** §164.312(e)(1) — "guard against unauthorized
access to PHI being transmitted." Plaintext-served PHI is
the textbook OCR finding pattern. **OCR-reportable
candidate.**

**Closure.** Caddy config patched to redirect; verified via
`curl -sI http://...`.

#### P1.5.2 Weak TLS

**Trigger.** Negotiated TLS version below 1.2 (verified
via `openssl s_client -tls1_1` succeeding).

**Why P1.** TLS 1.0/1.1 are deprecated; modern PHI traffic
must be 1.2+. **OCR-reportable candidate** if traffic was
served on the weak version.

**Closure.** Caddy / TLS config restricted to 1.2+; verified.

#### P1.5.3 Cert near-expiration (< 7 days)

**Trigger.** Cert expiration date < 7 days away.

**Why P1.** A cert that expires mid-business-hours causes
either an outage (trust-broken) or — worse — a lapse during
which traffic might fall back to plaintext. **OCR-reportable
candidate** if any plaintext fallback occurs.

**Closure.** Cert renewed; expiration > 30 days.

### §164.308 gaps (Phase 7)

#### P1.7.1 Vendor BAA expired

**Trigger.** `docs/compliance/baas.md` has a row with
`expiration < today` for a vendor that's actively used (per
`ai_calls.provider` or storage-destination cross-check).

**Why P1.** §164.308(b)(1) — "covered entity may permit a
business associate to … only if the covered entity obtains
satisfactory assurances … that the business associate will
appropriately safeguard the information." Expired BAA = no
satisfactory assurance. **OCR-reportable candidate.**

**Closure.** BAA renewed + executed; doc updated.

#### P1.7.2 Vendor in production without BAA

**Trigger.** A vendor present in `ai_calls.provider` or in
storage-destination config that has no row in baas.md OR a
row with `status = PENDING`.

**Why P1.** Same §164.308(b) — using a vendor without a BAA
is a textbook BA-relationship gap. **OCR-reportable
candidate.**

**Closure.** BAA executed; vendor row added to baas.md
with `status = EXECUTED`.

## P2 — drift / hygiene

### §164.312(a) drift (Phase 1)

#### P2.1.1 Inactive non-admin (>180 days)

**Trigger.** Non-admin account with no login in 180+ days.

**Why P2.** Inactive accounts accumulate attack surface;
review-and-revoke cycle should fire annually.

**Closure.** Account deactivated OR operator-attested
justification.

#### P2.1.2 Stale-session cleanup lag

**Trigger.** Sessions with `expirationAt < now() - 24h`
still present in `user_sessions`.

**Why P2.** §164.312(a)(2)(iii) implementation specification —
automatic logoff. The cleanup BullMQ job should be removing
these; lag means the job is stuck.

**Closure.** Cleanup job re-run; sessions purged; cron
liveness verified.

### §164.312(b) drift (Phase 2)

#### P2.2.1 Timestamp non-monotonic per target

**Trigger.** Per `targetId`, `audit_logs.timestamp` is not
strictly monotonic (later-timestamp row inserted before
earlier-timestamp).

**Why P2.** Likely clock skew or replication lag rather
than tampering, but worth verifying. The §164.312(b)
mechanism's evidentiary value depends on monotonicity.

**Closure.** Skew root-caused; if benign, document in the
runbook.

#### P2.2.2 Retention edge approaching

**Trigger.** Oldest `audit_logs` row's age > 5.5 years
(approaching the 6-year HIPAA retention requirement).

**Why P2.** Routine cleanup should NOT remove rows under 6
years old. Surface so the operator reviews retention policy.

**Closure.** Retention policy reviewed; documented; rows
retained per §164.316(b)(2)(i).

### §164.312(c) drift (Phase 3)

#### P2.3.1 Schema integrity weakening

**Trigger.** A previously-NOT-NULL PHI column became
NULL-able in a recent migration.

**Why P2.** Schema-level integrity is a defense layer.
Weakening it is a regression worth review.

**Closure.** Either constraint restored, OR the relaxation
is documented + signed off.

#### P2.3.2 SOAP version non-monotonic

**Trigger.** A visit's `soapVersion` decremented between
two `audit_logs` rows.

**Why P2.** SOAP versions are append-only by design.
Decrement is likely a race condition or manual rollback.

**Closure.** Root cause identified; race fixed if real; no
regression in next 7 days.

### §164.312(d) drift (Phase 4)

#### P2.4.1 Password reset audit gap

**Trigger.** `PASSWORD_RESET_REQUESTED` audit row without a
matching `PASSWORD_RESET_COMPLETED` row within 24h AND
without an expiration of the underlying token.

**Why P2.** Suspicious — partial flow. May indicate the
user abandoned the reset (benign) or an attacker triggered
the request (worth noting).

**Closure.** Per-row investigation; benign cases documented,
suspicious cases escalated.

### §164.308 drift (Phase 7)

#### P2.7.1 Vendor BAA expiring (60-day window)

**Trigger.** baas.md row with `expiration` between 30 and
60 days away.

**Why P2.** Renewal lead-time is typically 30–60 days;
catching at this window prevents the P1 expired-BAA
finding.

**Closure.** Renewal initiated.

#### P2.7.2 Restore drill stale (>90 days)

**Trigger.** Last drill date in `contingency-plan.md` >
90 days ago.

**Why P2.** §164.308(a)(7) — contingency plan must be
testable. Untested plans atrophy.

**Closure.** Drill performed; date updated.

## P3 — informational / future-risk

### §164.310 attestation (Phase 6)

All §164.310 surfaces are P3 because the agent isn't on
the hardware:

#### P3.6.1 LUKS device verification

**Trigger.** Phase 6 emits this on every run as an
informational record. Operator reviews to confirm posture.

**Why P3.** Hardware verification is operator-attested;
the auditor produces evidence of the config.

**Closure.** N/A — this is a recurring informational
record.

(Same shape for MinIO SSE, backup encryption, volume
retention.)

### Operational hardening (Phase 8)

#### P3.8.1 Sentry DSN populated without BAA

**Trigger.** `SENTRY_DSN_*` env vars have non-empty values
AND `docs/compliance/baas.md` shows Sentry BAA `status =
PENDING`.

**Why P3 (could escalate to P1).** Currently P3 because
the foundation in `docs/runbooks/sentry-setup.md` posture
is "DSNs empty until BAA." If the operator has populated
them ahead of BAA, that's a finding — but escalation
depends on whether real events have flowed (which the
auditor would surface separately via the
`Sentry-event-receipt` cross-check, not currently in scope).

**Closure.** Either (a) BAA executed + baas.md updated, OR
(b) DSN reverted to empty.

### Documentation hygiene

#### P3.D.1 Compliance doc stale (>6 months unmodified)

**Trigger.** Any file under `docs/compliance/` with
mtime > 6 months ago.

**Why P3.** Compliance documents that haven't been touched
in 6+ months may be stale relative to current operations.

**Closure.** File reviewed + either updated or
operator-attested as still current.

#### P3.D.2 Workforce training records stale

**Trigger.** `docs/compliance/workforce-training.md` has
entries for active users with last-training > 12 months.

**Why P3.** §164.308(a)(5) — security awareness + training
is a periodic obligation.

**Closure.** Training session held; record updated.

## What's NOT a finding

The auditor explicitly does NOT emit findings for:

- **Free-text content quality.** Out of scope; lives in
  ai-pipeline-auditor.
- **UI behavior bugs.** Out of scope; lives in
  qa-interaction-auditor.
- **Performance.** Latency drift is not a HIPAA concern.
- **Code style / hygiene.** This isn't a linter.
- **Apps/meddoc-pro.** Out of scope per memory #9.

## OCR-reportable candidates

Findings flagged with `ocr_reportable_candidate: true` go to
the operator + counsel, not directly to OCR. The auditor's
flag is **necessary but not sufficient** for breach
notification:

- The flag fires on **finding** of the gap
- §164.404 requires notification only on **breach**
  (unauthorized acquisition, access, use, or disclosure)
- Many flagged findings are not breaches (e.g. an MFA gap on
  an admin who never had their account compromised is a
  hardening failure but not a breach)

The flag is the auditor's contribution to the §164.404
analysis — it surfaces the candidate; the analysis happens
elsewhere.

## Reading the report

Severity-grouped + section-grouped:

```
## P1 — active compliance breach (N total, M ocr_reportable_candidates)
### §164.312(a) — Access control (n)
  - <title> — phase X — closure_criteria
  - ...
### §164.312(b) — Audit controls (n)
  - ...
[other §164.x sections]
[§164.308 vendor BAA expired]

## P2 — drift / hygiene (N)
[same shape, no ocr count]

## P3 — informational (N)
[physical safeguards attestation, doc hygiene]

## NO_DATA + SCHEMA_GAP (informational)
[phases that couldn't run]
```

A clean run produces "0 P1 / 0 P2 / 0 P3" + the standard
P3 attestation records that always fire. Reports retain
forever (compliance trace).
