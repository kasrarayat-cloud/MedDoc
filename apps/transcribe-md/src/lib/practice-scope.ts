// ============================================================================
// T5 — THE ONE practice-scoped accessor.
// ----------------------------------------------------------------------------
// Every clinical read made ON BEHALF OF A SIGNED-IN USER goes through here. The
// point is not convenience; it is that a tenancy predicate written by hand at
// 101 call sites is a hand-kept list, and hand-kept lists go stale. One of them
// eventually forgets, and the one that forgets is a cross-tenant read of a
// patient's chart.
//
// ⚠️ WHY A `where` FRAGMENT AND NOT A WRAPPED CLIENT. A wrapper that owns the
// whole query (`findVisits(practiceId, opts)`) has to re-expose every Prisma
// option its callers use — select, include, orderBy, cursor, take — and the
// first option it fails to expose gets worked around with a raw call, which is
// the exact leak this exists to close. Returning the PREDICATE keeps callers in
// full command of their query and leaves them nothing to route around.
//
// ⚠️ THE TWO CLASSES OF READ, AND WHY ONLY ONE IS SCOPED HERE.
//
//   REQUEST reads   — a signed-in user asking for data. These MUST be
//                     practice-scoped, and they are what the guard polices.
//   SYSTEM reads    — the worker processing a job whose visit id came from the
//                     queue, a retention sweep walking every row, a migration
//                     script. There is no acting user, so there is no practice
//                     to scope BY. Forcing these through a practice predicate
//                     would mean inventing a practice, and an invented tenant is
//                     worse than an unscoped read that is honest about itself.
//
// The guard therefore distinguishes them explicitly rather than counting call
// sites. A system read declares itself; an undeclared read is a request read.
//
// ⚠️ ROLES ARE NOT HERE. Whether a TECH sees less than a CLINICIAN is T6's
// question, layered ON TOP of this. T5 answers "which practice", T6 answers
// "which member of it". Conflating them would put a governance decision inside
// a plumbing function.
// ============================================================================

import type { Prisma } from '@prisma/client';

/**
 * Visits belonging to a practice.
 *
 * ⚠️ SCOPES ON THE COLUMN, NOT THE JOIN. `transcribe_visits.practiceId` exists
 * as of T3 and is derived from the PATIENT (the chart owns the note). Scoping
 * `{ user: { practiceId } }` instead would scope by the AUTHOR's practice — a
 * different question, and one that gives the wrong answer the moment a locum
 * writes in a practice that is not their own.
 */
export function visitScope(practiceId: string): Prisma.TranscribeVisitWhereInput {
  return { practiceId };
}

/** Patients belonging to a practice. Natively practice-scoped since before T3. */
export function patientScope(practiceId: string): Prisma.TranscribeMdPatientWhereInput {
  return { practiceId };
}

/**
 * Note templates belonging to a practice.
 *
 * ⚠️ VIA THE DOCTOR, because `note_templates` carries no practiceId of its own.
 * That is a real asymmetry with the two above and it is stated rather than
 * hidden: if templates ever gain the column, this function changes and its
 * callers do not — which is the whole reason the predicate lives in one place.
 */
export function templateScope(practiceId: string): Prisma.NoteTemplateWhereInput {
  return { doctor: { practiceId } };
}

/**
 * A single visit, scoped.
 *
 * The common shape at call sites is `where: { id: visitId, userId }`. That is an
 * OWNERSHIP check wearing a tenancy check's clothes — it happens to isolate
 * tenants today only because every practice has one member. This is the tenancy
 * check; ownership, where it is genuinely wanted, is a separate conjunct the
 * caller adds.
 */
export function visitByIdScope(
  visitId: string,
  practiceId: string,
): Prisma.TranscribeVisitWhereInput {
  return { id: visitId, practiceId };
}

/**
 * Marks a read as SYSTEM context — no acting user, therefore no practice.
 *
 * ⚠️ THIS IS A DECLARATION, NOT A HELPER. It does nothing at runtime. It exists
 * so the guard can tell "this read is deliberately unscoped because a job is
 * running" from "somebody forgot". A comment would not survive a refactor; a
 * symbol the guard greps for does.
 *
 * Use it at the call site:
 *     // eslint-disable-next-line -- SYSTEM_READ: worker job, no acting user
 *     const visit = await prisma.transcribeVisit.findUnique({ where: { id } });
 */
export const SYSTEM_READ = 'SYSTEM_READ' as const;
