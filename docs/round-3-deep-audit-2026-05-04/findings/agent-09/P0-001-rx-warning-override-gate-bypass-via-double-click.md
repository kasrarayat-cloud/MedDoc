---
id: A09-P0-001
title: Rx critical-warning sign gate bypassable via duplicate override clicks (count-based, not coverage-based)
severity: P0
domain: data-integrity / patient-safety
---

## Issue
The `/api/visits/[id]/sign` route gates the READY → SIGNED transition behind
"every critical Rx warning has at least one override audit row". The check is
a SQL `COUNT(*)` against `rx_warning_overrides` filtered by `visitId` +
`severity='critical'`, compared to the count of critical warnings in
`visit.rxDrafts.warnings`. A doctor (or scripted client) can satisfy the gate
WITHOUT overriding every warning by submitting two override rows for the SAME
warning — e.g. by double-clicking the override modal — because:

1. `RxWarningOverride` has NO `@@unique([visitId, warningId])` constraint at
   the DB level (`packages/db/prisma/schema.prisma` lines 1756-1791).
2. `recordOverride()` in `apps/transcribe-md/src/lib/rx-warning-audit.ts:91`
   uses `prisma.rxWarningOverride.create({ data: ... })` with no upsert / no
   pre-flight check on `(visitId, warningId)`.
3. The gate counts **rows**, not **distinct warningIds**.

## Evidence
`apps/transcribe-md/src/app/api/visits/[id]/sign/route.ts:194-197`:
```ts
const overrideCount = await prisma.rxWarningOverride.count({
  where: { visitId, severity: 'critical' },
});
if (overrideCount < criticalWarnings.length) {
  // block sign
}
```

Concrete exploit (no malicious intent required — a flaky network double-click
on the override modal is enough): visit has 2 critical warnings (`warning-A`
and `warning-B`). Doctor clicks "Override" on warning A, network blip causes
the modal to re-submit, two rows land in `rx_warning_overrides` both with
`warningId='warning-A'`. `overrideCount === 2`, `criticalWarnings.length ===
2`, gate passes, sign succeeds. Warning B was NEVER overridden but the visit
is signed and frozen.

## Risk
P0 patient safety + audit-trail integrity. The override audit is the
clinical-safety record that proves the doctor consciously accepted each
critical warning. A bypass means a SIGNED visit may carry an Rx that
contradicts a critical contraindication (e.g. NSAID + chronic kidney
disease, opioid + benzodiazepine). The HIPAA audit emits a
`RX_OVERRIDE_RECORDED` row per call; from compliance's perspective those rows
do exist, but neither the audit log nor the override table records that a
SECOND warning was silently waved through.

Severity is P0 not P1 because:
- Pre-pilot is exactly when this surfaces: doctors in early-pilot tooling
  click fast, networks stutter, and the same warningId gets submitted twice.
- The override modal sits behind a single button click; no rate limit, no
  CSRF re-validation, no client-side disable on the second click that I can
  see in `recordOverride` (server-side only).
- Loss is silent: the failed warning leaves no trace anywhere — the count
  is satisfied, audit row exists for the duplicate, gate is happy.

## Recommended fix
Two layers, ship both:

1. **DB constraint (defence in depth)** — add
   `@@unique([visitId, warningId])` to `RxWarningOverride` so a duplicate
   insert throws `P2002` and the action returns "already overridden" idem-
   potently. Migration is purely additive and behind an expand-contract:
   first dedupe existing rows (group by `(visitId, warningId)`, keep MIN(id)),
   then add the unique index.

2. **Gate fix (correctness)** — change the sign route from
   `prisma.rxWarningOverride.count({ where: { visitId, severity: 'critical' }})`
   to a `findMany({ select: { warningId: true } })` then a Set-based check
   that `criticalWarnings.every(w => overriddenIds.has(w.warningId))`. This
   makes the gate coverage-based regardless of duplicate row existence.

Also add a server-side dedupe inside `recordOverride()` itself:
```ts
const existing = await prisma.rxWarningOverride.findFirst({
  where: { visitId, warningId, severity },
  select: { id: true },
});
if (existing) return { ok: true, auditId: existing.id };
```
so the duplicate doesn't land in the table at all.
