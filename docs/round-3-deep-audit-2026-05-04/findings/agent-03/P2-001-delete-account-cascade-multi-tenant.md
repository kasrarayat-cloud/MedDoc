---
id: A03-P2-001
severity: P2
title: delete-account hard-deletes Practice unconditionally — multi-tenant blast radius if user ever non-solo
domain: authz
agent: agent-03
---

## Issue

`POST /api/settings/delete-account` (apps/transcribe-md/src/app/api/settings/delete-account/route.ts:124-144) ends its destructive transaction with:

```ts
await tx.aiCall.deleteMany({ where: { practiceId: user.practiceId } });
await tx.user.delete({ where: { id: user.id } });
await tx.practice.delete({ where: { id: user.practiceId } });
```

The flow assumes the User → Practice relation is 1:1 — true today because TranscribeMD signupAction (apps/transcribe-md/src/actions/auth.ts:371-394) always mints a fresh "Solo — {name}" Practice per signup. The delete-account header comment acknowledges this assumption explicitly:

```ts
// User and Practice are symmetric for solo TranscribeMD users
// (1:1 synthetic Practice). Non-solo users would keep the
// Practice — but TranscribeMD signup only creates solo ones,
// so dropping it is always correct here.
```

However, **the runtime never re-verifies solo-ness**. A user moved to a real multi-seat Practice via:
- a SUPER_ADMIN re-parenting (no UI today, but `prisma.user.update` raw access exists),
- a future MEDDOC_PRO migration (the cross-app entitlement check at apps/transcribe-md/src/actions/auth.ts:185 hints multi-product accounts already exist),
- a manual SQL fix to merge two doctors,

would silently turn this endpoint into a tenant-wide PHI nuke: `tx.aiCall.deleteMany({ practiceId })` deletes every other user's AI call rows in the practice, and `tx.practice.delete({ id })` cascades through every Practice-relation in schema.prisma:1352-1407 (TranscribeMdPatient has `onDelete: Cascade` on practiceId), wiping every other doctor's patient-table catalog **and every TranscribeVisit they own** (TranscribeVisit.patientId has `onDelete: Restrict`, but only the Patient cascade fires here — wait: see Risk).

## Evidence

apps/transcribe-md/src/app/api/settings/delete-account/route.ts:135-144

```ts
await tx.accountDeletion.create({ ... });
await tx.aiCall.deleteMany({
  where: { practiceId: user.practiceId },
});
await tx.user.delete({ where: { id: user.id } });
await tx.practice.delete({ where: { id: user.practiceId } });
```

packages/db/prisma/schema.prisma:1356:
```prisma
practice   Practice @relation(fields: [practiceId], references: [id], onDelete: Cascade)
```

apps/transcribe-md/src/actions/auth.ts:371-394 (only creator path for Practice):
```ts
const practice = await tx.practice.create({
  data: { name: `Solo — ${parsed.data.name}`, slug: ... },
});
const user = await tx.user.create({
  data: { ... practiceId: practice.id, ... }
});
```

## Risk

**Today**: zero impact — every TranscribeMD Practice row has exactly one User. The assumption holds.

**On the day someone re-parents a doctor into a real practice**:
- `aiCall.deleteMany({ practiceId })` deletes EVERY user's AI cost rows in the practice (cross-tenant data deletion).
- `practice.delete()` raises a Prisma constraint error (because other Users still FK to it via User.practiceId, which has no `onDelete: Cascade`), so the TX rolls back and the deleting user is **stuck unable to delete their account** — better failure mode but still wrong.
- If User.practiceId ever gains `onDelete: Cascade` later, the Practice cascade would silently drop every TranscribeMdPatient (Patient.practiceId is `onDelete: Cascade` per schema.prisma:1356) and the FK Restrict on `TranscribeVisit.patientId` would block the cascade — so visits stay (bad, orphaned), patients vanish.

The class is "code that's correct only because of an undocumented invariant nothing enforces."

## Recommended fix

Inside the transaction, gate the Practice delete on a peer-user count:

```ts
const peers = await tx.user.count({
  where: { practiceId: user.practiceId, id: { not: user.id } },
});
if (peers === 0) {
  // Safe — solo practice, drop it.
  await tx.aiCall.deleteMany({ where: { practiceId: user.practiceId } });
  await tx.user.delete({ where: { id: user.id } });
  await tx.practice.delete({ where: { id: user.practiceId } });
} else {
  // Non-solo — keep the Practice, scope the AiCall purge to this user.
  await tx.aiCall.deleteMany({ where: { userId: user.id } });
  await tx.user.delete({ where: { id: user.id } });
  // Practice + other users + their patients/visits stay intact.
}
```

Defense-in-depth alternative: add a unique index on `Practice.id` filtered by `User.practiceId` count (Postgres won't let you, but a CHECK trigger could enforce solo-ness by name prefix `Solo —`). The runtime guard above is sufficient; the trigger is overkill.
