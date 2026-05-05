---
id: A03-P3-002
severity: P3
title: TranscribeVisit reads are user-scoped, not practice-scoped — STAFF role cannot view DOCTOR visits in same practice
domain: authz
agent: agent-03
---

## Issue

Every TranscribeVisit endpoint enforces ownership via `visit.userId !== userId` rather than `practiceId`. This is a deliberate choice (per auth.ts:283-393 the role taxonomy says DOCTOR / STAFF are per-user, ADMIN per-practice, SUPER_ADMIN platform), but it has a few sharp edges worth surfacing for the pilot:

1. A STAFF account in the same practice as a DOCTOR cannot view the DOCTOR's signed visits, even for compliance/billing audit. There is no per-practice read tier.
2. ADMIN role bypass exists on the CRM Patient model via `patientAccessWhere(session)` (packages/auth/src/index.ts:372-393) but is **not** consulted anywhere in TranscribeMD — the TM API never branches on `session.user.role`. So an ADMIN user gets the same visit visibility as a DOCTOR (their own visits only), contradicting the role-policy comment.
3. SUPER_ADMIN cannot view a doctor's TM visits via the doctor surface — only via /admin (which doesn't expose visit content). Acceptable but undocumented.

## Evidence

Patterns surveyed (every dynamic [id] visit route checks `visit.userId !== userId`):

- apps/transcribe-md/src/app/api/visits/[id]/route.ts:135 (GET)
- apps/transcribe-md/src/app/api/visits/[id]/route.ts:190 (PATCH)
- apps/transcribe-md/src/app/api/visits/[id]/sign/route.ts:151
- apps/transcribe-md/src/app/api/visits/[id]/delete/route.ts:69
- apps/transcribe-md/src/app/api/visits/[id]/archive/route.ts:49
- apps/transcribe-md/src/app/api/visits/[id]/restore/route.ts:51
- apps/transcribe-md/src/app/api/visits/[id]/retry/route.ts:98
- apps/transcribe-md/src/app/api/visits/[id]/upload/route.ts:81
- apps/transcribe-md/src/app/api/visits/[id]/text/route.ts:68
- apps/transcribe-md/src/app/api/visits/[id]/dictation/audio/route.ts:39
- apps/transcribe-md/src/app/api/visits/[id]/dictation/upload/route.ts:72
- apps/transcribe-md/src/app/api/visits/[id]/em-score/route.ts:64
- apps/transcribe-md/src/app/api/visits/[id]/export/{pdf,docx,clipboard,email}/route.ts (via loadVisitExportData(visitId, userId) in apps/transcribe-md/src/lib/visit-export-server.ts:57)
- apps/transcribe-md/src/app/visits/[id]/page.tsx:238 (RSC)
- apps/transcribe-md/src/app/visits/[id]/record/page.tsx:53 (RSC)

Patient routes use `practiceId` correctly — that asymmetry is the right design (patients are practice-shared records; visits are personal physician artifacts) but the role policy in auth.ts implies an ADMIN can override. They cannot, on this surface.

## Risk

Functional gap, not a security gap. Listed as P3 because:
- For the solo-doctor pilot, every account is its own Practice → the gap doesn't materialise.
- If a multi-doctor practice signs up post-pilot expecting their practice ADMIN to audit DOCTOR notes, they will be confused.

## Recommended fix

Either:

1. Add a comment block at the top of `apps/transcribe-md/src/app/api/visits/[id]/route.ts` explicitly documenting "TM visits are per-user, not per-practice; ADMIN does not bypass". Cheap, makes intent clear.

2. Or, if multi-seat practices are in scope: introduce a helper `assertVisitReadable(session, visit)` that lets ADMIN in same practice and SUPER_ADMIN bypass:

```ts
function canReadVisit(session: Session, visit: { userId: string; user: { practiceId: string } }): boolean {
  if (session.user.role === 'SUPER_ADMIN') return true;
  if (visit.userId === session.user.id) return true;
  if (session.user.role === 'ADMIN' && visit.user.practiceId === session.user.practiceId) return true;
  return false;
}
```

For the pilot, option 1 is sufficient.
