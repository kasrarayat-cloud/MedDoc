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

// ============================================================================
// BRANDED IDS — T5's closing hardening.
// ----------------------------------------------------------------------------
// ⚠️ THE BUG THESE EXIST TO MAKE IMPOSSIBLE, stated exactly.
// `loadVisitExportData(visitId, userId)` had its second parameter renamed to
// `practiceId`. NINE call sites kept passing a user id. `tsc` accepted all nine,
// because `practiceId: string` and `userId: string` are the same type. It failed
// CLOSED — a user id matches no practice, so exports returned not-found — but
// the next rename of this shape might not, and a tenancy predicate built from
// the wrong id is the failure this whole file exists to prevent.
//
// A brand is a compile-time-only marker: `PracticeId` IS a `string` at runtime
// and flows into Prisma's `where` unchanged, but a plain `string` is NOT
// assignable to it. So the mistake stops being a silent success.
//
// ⚠️ SCOPE IS THE ACCESSOR SURFACE AND ITS CALLERS — deliberately not a
// repo-wide crusade. The brands are applied at ONE place, `getSession()`, which
// is the single point where an untyped string becomes an identity in this app.
// Every existing call site inherits them with no edit, which is why this is a
// small commit rather than a 52-site sweep.
// ============================================================================

declare const BRAND: unique symbol;

/** A practice id, as produced by `getSession()`. Never a user id. */
export type PracticeId = string & { readonly [BRAND]: 'PracticeId' };

/** A user id, as produced by `getSession()`. Never a practice id. */
export type UserId = string & { readonly [BRAND]: 'UserId' };

/**
 * ⚠️ THE ONLY BLESSED WAY TO MINT A `PracticeId`, and it belongs to the session
 * boundary alone. Calling it anywhere else re-opens the hole: a brand is only
 * worth what its constructor's discipline is worth.
 *
 * It validates rather than merely asserting, so the brand carries a real
 * guarantee — a `PracticeId` is never empty.
 */
export function asPracticeId(value: string): PracticeId {
  return requirePractice(value) as PracticeId;
}

/** The same, for user ids. See `asPracticeId` — mint at the session boundary. */
export function asUserId(value: string): UserId {
  if (typeof value !== 'string' || value.length === 0) {
    throw new Error('practice-scope: empty userId');
  }
  return value as UserId;
}

/**
 * ⚠️ THE SILENT-SCOPE-LOSS GUARD, AND WHY A TYPE IS NOT ENOUGH.
 *
 * Prisma DROPS a `where` key whose value is `undefined`. So
 * `{ practiceId: undefined }` is not "match nothing" — it is `{}`, which
 * matches EVERY TENANT. The single most dangerous failure this file can have
 * produces no error, no log line and a wider result set.
 *
 * `practiceId: string` stops that at compile time for honest callers, and
 * `getSession()` already returns null rather than a session without a practice.
 * This is the third line: an `as any`, a widened generic, or a JSON-parsed value
 * that slips past both still fails LOUDLY here instead of quietly returning
 * another practice's charts.
 */
function requirePractice(practiceId: string): string {
  if (typeof practiceId !== 'string' || practiceId.length === 0) {
    throw new Error(
      'practice-scope: empty practiceId — refusing to build a predicate that ' +
        'Prisma would treat as "all tenants". The caller must source it from ' +
        'getSession(), which fails closed.',
    );
  }
  return practiceId;
}

/**
 * Visits belonging to a practice.
 *
 * ⚠️ SCOPES ON THE COLUMN, NOT THE JOIN. `transcribe_visits.practiceId` exists
 * as of T3 and is derived from the PATIENT (the chart owns the note). Scoping
 * `{ user: { practiceId } }` instead would scope by the AUTHOR's practice — a
 * different question, and one that gives the wrong answer the moment a locum
 * writes in a practice that is not their own.
 */
export function visitScope(practiceId: PracticeId): Prisma.TranscribeVisitWhereInput {
  return { practiceId: requirePractice(practiceId) };
}

/** Patients belonging to a practice. Natively practice-scoped since before T3. */
export function patientScope(practiceId: PracticeId): Prisma.TranscribeMdPatientWhereInput {
  return { practiceId: requirePractice(practiceId) };
}

/**
 * Note templates belonging to a practice.
 *
 * ⚠️ VIA THE DOCTOR, because `note_templates` carries no practiceId of its own.
 * That is a real asymmetry with the two above and it is stated rather than
 * hidden: if templates ever gain the column, this function changes and its
 * callers do not — which is the whole reason the predicate lives in one place.
 */
export function templateScope(practiceId: PracticeId): Prisma.NoteTemplateWhereInput {
  return { doctor: { practiceId: requirePractice(practiceId) } };
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
  practiceId: PracticeId,
): Prisma.TranscribeVisitWhereInput {
  return { id: visitId, practiceId: requirePractice(practiceId) };
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

// ============================================================================
// SCOPED WRITES — T5-W.
// ----------------------------------------------------------------------------
// ⚠️ `update` → `updateMany` IS NOT A FREE SWAP, AND THE DIFFERENCE IS AN ERROR
// SIGNAL.
//
// Prisma's `update` requires a UNIQUE `where`, so a practice predicate cannot be
// added to it — the same wall `findUnique` hit on the read side, where the answer
// was `findFirst`. Here the answer is `updateMany`. But:
//
//     update      no row matches  →  THROWS P2025
//     updateMany  no row matches  →  RETURNS { count: 0 }, silently
//
// So converting a site and discarding the result DELETES an error that used to
// be raised. The failure it deletes is not theoretical: several call sites in
// this codebase already read `count === 0` as "a concurrent write won", so a
// wrong predicate would wear the benign-race costume and the symptom in
// production would be **a save that silently does nothing on a chart the user is
// looking at**.
//
// `scopedUpdate` restores the signal. It is a function rather than a convention
// because a convention is a hand-kept list, and this one would be kept by
// fifteen call sites — put the behaviour where it cannot be forgotten.
// ============================================================================

/** Thrown when a practice-scoped write matched no row. Mirrors `update`'s P2025. */
export class ScopedWriteMissError extends Error {
  constructor(model: string, id: string) {
    super(
      `${model}: scoped update matched no row for id=${id}. Either the row left ` +
        `the practice between the read and the write, or the predicate is wrong. ` +
        `Refusing to report a write that did not happen.`,
    );
    this.name = 'ScopedWriteMissError';
  }
}

/**
 * A practice-scoped `updateMany` that behaves like `update` on a miss.
 *
 * ⚠️ IT TAKES THE PREDICATE, NOT AN ID PLUS A PRACTICE. The three clinical
 * models do not share one scoping shape — visits and patients carry a
 * `practiceId` column, `note_templates` scopes through `doctor: { practiceId }`
 * — so a helper that built the predicate itself would be right for two models
 * and quietly wrong for the third. The caller passes the accessor's output.
 *
 * ⚠️ IT THROWS ON `count === 0` ON PURPOSE. Callers that genuinely want to
 * tolerate a miss — the optimistic-concurrency sites that inspect `count`
 * themselves — must NOT use this; they call `updateMany` directly and keep their
 * own reasoning, which is visible in the diff rather than hidden behind a helper.
 */
// ⚠️ F-TYPE 2026-08-07 — GENERIC, NOT `unknown`, AND NOT `any`.
// This took `model: { updateMany: (args: { where: unknown; data: unknown }) => … }`.
// `unknown` is the TOP type, so under `strictFunctionTypes` that parameter is
// CONTRAVARIANT and a real Prisma delegate — whose `updateMany` accepts a
// narrow, model-specific args type — is not assignable to it. With the shared
// client typed, all 13 call sites reddened at once with
// "Argument of type 'TranscribeVisitDelegate<…>' is not assignable".
//
// The lazy fix is `args: any`, which would restore silence everywhere. Making
// it generic instead means `where` and `data` are inferred FROM THE DELEGATE,
// so the practice predicate and the update payload are now type-checked at
// every call site — which is the entire point of typing the client.
export async function scopedUpdate<
  TWhere,
  TData,
>(
  model: { updateMany: (args: { where: TWhere; data: TData }) => Promise<{ count: number }> },
  modelName: string,
  id: string,
  where: TWhere,
  data: TData,
): Promise<void> {
  const res = await model.updateMany({ where, data });
  if (res.count === 0) throw new ScopedWriteMissError(modelName, id);
}
