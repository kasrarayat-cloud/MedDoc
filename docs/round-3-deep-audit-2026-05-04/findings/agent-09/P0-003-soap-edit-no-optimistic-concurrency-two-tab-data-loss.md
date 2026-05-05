---
id: A09-P0-003
title: SOAP edit save is last-write-wins — two-tab edit silently drops one doctor's changes
severity: P0
domain: data-integrity / concurrency
---

## Issue
`saveSoapDraftAction()` (the only path the doctor uses to persist SOAP edits
between draft and sign) reads the visit, validates ownership + status, then
issues an unconditional `prisma.transcribeVisit.update({ where: { id }, data:
{ soapFinal } })`. There is NO `version` field, NO `updatedAt` predicate in
the WHERE, and NO row-level lock. The `TranscribeVisit` schema has
`@updatedAt` on `updatedAt` (line 1585) — it's bumped on every write, but
nothing in the write path *reads* it for compare-and-swap.

Two-tab data loss scenario:
- Doctor opens visit V on phone (Tab A) and laptop (Tab B), both at
  `soapFinal = "v1"`. Both tabs cache that value in the SOAP editor.
- Tab A makes edits → submits, server writes `soapFinal = "v1+phoneEdits"`.
- Tab B (still showing v1 on the laptop) makes edits → submits, server
  writes `soapFinal = "v1+laptopEdits"`. **Phone edits are silently
  destroyed.**

The action returns `{ ok: true }` to Tab B. The doctor has no idea another
device's work was overwritten.

## Evidence
`apps/transcribe-md/src/actions/soap.ts:23-66`:
```ts
export async function saveSoapDraftAction(
  visitId: string,
  text: string
): Promise<SaveSoapResult> {
  // … auth + status checks …
  await prisma.transcribeVisit.update({
    where: { id: visitId },
    data: { soapFinal: parsed.data.text },
  });
  // …
  return { ok: true };
}
```

Same pattern in `reassignSpeakerAction()` (lines 138-192) — the speaker map
is read, mutated in JS, written back. Two concurrent reassigns of different
speakers in the same visit BOTH succeed at write time but the second-arriving
one overwrites the first's change because `speakerMap` is loaded fully then
written fully.

Same pattern (slightly different shape) in the `/api/visits/[id]` PATCH
handler — read, validate `status === QUEUED`, update without atomic guard.

## Risk
P0 — silent destruction of the doctor's work, no warning, no recovery.
Severity is data-loss, not "race condition theatre":
- A pilot doctor will keep a desktop browser tab open while running the
  iPhone PWA in clinic — overlapping edits are the norm, not the exception.
- The `soapFinal` column is the one the doctor signs. If their phone-side
  refinements vanish because the laptop autosaved a stale draft, the
  signed note is wrong.
- The product surfaces a visit URL on the dashboard that resolves
  multi-device by design (offline draft on iPad, polish later on desktop).
- Once signed, `signedSoap` freezes whatever soapFinal happened to win —
  the loss becomes permanent at the audit level.

Compounds with the Layer 6 polish race: the worker writes `soapFinal` after
L6, and a doctor editing during AUTOMATING (a status the upload allowlist
correctly rejects but which the saveSoapDraftAction allowlist gates only via
`status === READY`) may be racing the worker's L6 write.

## Recommended fix
Two layers, ship together:

1. **Atomic compare-and-swap on the update**:
```ts
const updated = await prisma.transcribeVisit.updateMany({
  where: { id: visitId, updatedAt: visit.updatedAt },
  data: { soapFinal: parsed.data.text },
});
if (updated.count === 0) {
  return { ok: false, error: 'Visit was edited elsewhere — refresh to see the latest version, then re-apply your changes.' };
}
```
This makes the action a true CAS — the second-arriving writer detects the
first writer's update and surfaces the conflict to the UI.

2. **Surface the conflict**: the SOAP editor should keep both versions in
local storage and offer a 3-way diff so the doctor can merge instead of
restart. Not a P0 (the CAS alone closes the data-loss path), but the UX
delta is small and worth doing in the same week.

The same pattern (`updateMany` + `updatedAt` predicate) should be retro-
fitted onto `reassignSpeakerAction` and the `/api/visits/[id]` PATCH
handler.
