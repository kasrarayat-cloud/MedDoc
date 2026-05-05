---
id: A04-P2-003
title: ID fields validated only as `min(1)` strings — missing `.uuid()` / `.cuid()` shape gates
severity: P2
domain: Input validation
status: open
---

## Summary

Several Zod schemas accept resource IDs as `z.string().min(1)` with no shape validation. Postgres + Prisma will reject malformed IDs at query time (returning `null` from `findUnique`, which the routes already handle), so this is not a security hole today — it's a defensive-coding miss. The risk is two-fold:

1. Future migration to a different ID format (e.g. swap CUID → UUID) silently passes through the API edge instead of being caught at the boundary, creating a subtle regression.
2. Pathological inputs (10 KB of `Z`s passed as `patientId`) propagate to Prisma without an early reject. Prisma normalises and runs the query, costing a DB round-trip.

Specific cases:

- `apps/transcribe-md/src/app/api/visits/[id]/route.ts:53-65` — `patientId: z.string().trim().min(1).optional()` — should be `.uuid()` or `.cuid()` per the schema's actual ID format.
- `apps/transcribe-md/src/actions/visits.ts:28-34` — `patientId` same shape.
- `apps/transcribe-md/src/actions/soap.ts:11-14, 127-131` — `visitId`, `speakerId` both `z.string().min(1)`.
- `apps/transcribe-md/src/app/api/admin/audit-logs/route.ts:42` — `userId: z.string().optional()` — should be `.uuid().optional()` or whatever shape User.id has.
- `apps/transcribe-md/src/app/api/admin/users/route.ts:34` — `cursor: z.string().optional()` is parsed by `parseCursor` which validates the shape, fine.

## Evidence

Sample (`apps/transcribe-md/src/actions/visits.ts:24-56`):
```ts
const CreateVisitSchema = z.object({
  patientId: z.string().trim().min(1).optional()...,
  patientName: z.string().trim().max(120)...,
  specialty: z.enum(SPECIALTY_IDS, ...),
  ...
});
```

Sample (`apps/transcribe-md/src/actions/soap.ts:127-131`):
```ts
const ReassignSpeakerSchema = z.object({
  visitId: z.string().min(1),
  speakerId: z.string().min(1),
  role: SpeakerRoleKeys,
});
```

## Why P2 not P3

The cumulative effect across ~15 endpoints means any future ID-format migration would need to touch every one of these. Naming the contract at the boundary is cheap, and it prevents downstream functions from defensively sanitising what the boundary should already have done.

## Recommended fix

Pick the canonical ID shape the schema uses and tag every `id`/`patientId`/`userId`/`visitId`/`speakerId` field accordingly. Prisma's User and TranscribeMdPatient use `cuid()` (per memory note on `@meddoc/db`'s typing); use `z.string().cuid()` or build a single shared `IdSchema = z.string().regex(/^[a-z0-9]{20,30}$/)` and import it everywhere.

## Cross-domain hooks

- None significant.

## Files

- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/visits/[id]/route.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/actions/visits.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/actions/soap.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/admin/audit-logs/route.ts`
