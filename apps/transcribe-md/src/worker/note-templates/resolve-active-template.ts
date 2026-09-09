// ============================================================================
// resolveActiveTemplate — pick the note template L4 should generate against
// ----------------------------------------------------------------------------
// Phase 0: ships DORMANT. Nothing in the pipeline calls this yet, and no
// behavior depends on it. It is written + tested now so Phase 1 can wire it
// into L4 (04-generate-soap.ts) with confidence.
//
// Two pieces, "functional core / imperative shell":
//   - selectTemplate(...)        — PURE. Deterministic fallback-chain logic
//                                  over an already-loaded candidate set.
//                                  Fully unit-tested.
//   - resolveActiveTemplate(...) — thin async wrapper that loads the
//                                  candidate set from the DB then delegates
//                                  to selectTemplate.
//
// Fallback chain (most → least specific):
//   1. the doctor's ACTIVE template whose encounterType matches the request
//   2. the doctor's ACTIVE catch-all template (encounterType === null)
//   3. the SYSTEM DEFAULT (the seeded singleton)
//
// In Phase 0 no doctor has a custom template, so this always resolves to the
// system default — which is exactly today's L4 SOAP format. Hence: zero
// behavior change.
// ============================================================================

import type { NoteTemplate } from '@prisma/client';
import prisma from '@meddoc/db';

export interface ResolveTemplateInput {
  /** The signing/owning doctor (User.id). ⚠️ #302 — ATTRIBUTION, and a
   *  PREFERENCE. It is no longer the scope: see `tenantPracticeId`. */
  doctorId: string;
  /**
   * ⚠️ #302 — THE CHART'S PRACTICE, AND IT IS THE SCOPE.
   *
   * #287 ruled that the tenant "scopes the visit AND selects/validates the
   * template". Only the VALIDATION half had been applied: `fill-engine.ts`
   * rejected a template the tenant did not own while this resolver still chose
   * one by `doctorId`. Two ends of one decision on two axes — and the
   * half-application is worse than neither half, because on `main` both ends
   * agreed on the author and a locum's visit merely rendered the wrong
   * practice's form, which is recoverable.
   *
   * Optional so the many call sites that legitimately resolve a doctor's own
   * format (settings previews, sample renders) do not have to invent a tenant.
   * When absent, behaviour is exactly as before.
   */
  tenantPracticeId?: string | null;
  /** Encounter type to match (a specialty / visit-type slug). Null or
   *  omitted = resolve the doctor's catch-all (or the system default). */
  encounterType?: string | null;
}

/**
 * Thrown when the candidate set contains no system-default template. This is
 * an invariant violation — the Phase-0 seed guarantees exactly one row with
 * isSystemDefault = true, and the partial unique index keeps it singular.
 * Surfacing loudly beats silently generating an unstructured note.
 */
export class MissingSystemDefaultTemplateError extends Error {
  constructor() {
    super(
      'No system-default NoteTemplate found in the candidate set. The Phase-0 ' +
        'seed (migration add_note_templates_phase0) must insert exactly one ' +
        'row with isSystemDefault = true.'
    );
    this.name = 'MissingSystemDefaultTemplateError';
  }
}

/**
 * PURE resolver core. Selects the active template from a candidate set per
 * the fallback chain documented above. No I/O — deterministic and directly
 * unit-testable. The caller need not pre-filter: this applies the
 * `status === 'active'` filter itself so the function is self-contained.
 *
 * @throws {MissingSystemDefaultTemplateError} if no system default is present.
 */
/**
 * Deterministic ordering for candidate templates: newest first, id as the
 * final tie-break.
 *
 * S6 — this used to be absent, and it mattered. `resolveActiveTemplate` loads
 * candidates with an unordered `findMany`, so Postgres returns them in
 * whatever physical order the heap happens to have. The `.find()` calls below
 * take the FIRST match. With two active catch-alls for one doctor, which
 * template generated a note therefore depended on row layout — and could
 * change after any UPDATE moved a row. Two visits, same doctor, same input,
 * different note format, no way to explain why from the data.
 *
 * A unique index now prevents that state from being created at all (see
 * migration 20260725050000). This ordering is the belt to that suspenders: the
 * pure core must be deterministic on ANY candidate set, including one loaded
 * by a future caller that forgets to order, or one built by a test.
 */
function deterministic(rows: readonly NoteTemplate[]): NoteTemplate[] {
  return [...rows].sort((a, b) => {
    const t = b.updatedAt.getTime() - a.updatedAt.getTime();
    return t !== 0 ? t : (a.id < b.id ? 1 : a.id > b.id ? -1 : 0);
  });
}

export function selectTemplate(
  candidates: readonly NoteTemplate[],
  { doctorId, encounterType = null, tenantPracticeId = null }: ResolveTemplateInput
): NoteTemplate {
  const active = deterministic(candidates.filter((t) => t.status === 'active'));

  // ⚠️ #302 — THE AUTHOR IS TRIED FIRST, AND THAT IS DELIBERATE, NOT A HEDGE.
  // Production is 58 of 58 visits whose author practice EQUALS the tenant, so
  // for every visit that exists today the doctor's own template is also the
  // tenant's and this order changes nothing. The tenant arm below is reached
  // only when they differ — the locum case #287 was written for — where it
  // supplies the CHART's format instead of the visitor's.
  //
  // Ordering it the other way would re-point every existing visit at whichever
  // of a practice's templates sorted first, which is a change nobody asked for
  // and which no arm in this repo would have witnessed.
  const ofTenant = (t: NoteTemplate) =>
    tenantPracticeId != null && t.practiceId === tenantPracticeId;

  // ⚠️ "THE AUTHOR FIRST" MEANS **WITHIN THE TENANT**, AND THE FIRST DRAFT OF
  // THIS DID NOT. Preferring the author's template ANYWHERE let a locum's own
  // practice-B form fill practice A's chart — which is precisely the
  // wrong-practice document #287 exists to stop, re-introduced by the fix for
  // it. The arm caught it. When a tenant is given, every doctor-keyed step is
  // conjoined with it; when none is given, behaviour is exactly as before.
  const inScope = (t: NoteTemplate) => tenantPracticeId == null || ofTenant(t);

  // 1. doctor's template for this exact encounter type (only when a type
  //    was requested — a null request skips straight to the catch-all).
  if (encounterType != null) {
    const exact = active.find(
      (t) => t.doctorId === doctorId && inScope(t) && t.encounterType === encounterType
    );
    if (exact) return exact;
  }

  // 2. doctor's catch-all (encounterType === null).
  const doctorDefault = active.find(
    (t) => t.doctorId === doctorId && inScope(t) && t.encounterType === null
  );
  if (doctorDefault) return doctorDefault;

  // 2b. ⚠️ #302 — THE TENANT'S OWN FORMAT, when the author has none here.
  // `deterministic()` has already sorted, so a practice carrying several
  // doctors' active templates resolves to a STABLE one rather than an arbitrary
  // one. Which of several is "the practice's format" is a product question
  // nobody has had to answer yet, and it is named here rather than decided
  // quietly: if it ever matters, this is the line that answers it.
  if (tenantPracticeId != null) {
    if (encounterType != null) {
      const tenantExact = active.find((t) => ofTenant(t) && t.encounterType === encounterType);
      if (tenantExact) return tenantExact;
    }
    const tenantDefault = active.find((t) => ofTenant(t) && t.encounterType === null);
    if (tenantDefault) return tenantDefault;
  }

  // 3. the seeded system default — terminal fallback. Not required to be
  //    'active'-filtered (it always is), and located across ALL candidates
  //    so a mis-set status can't strand resolution.
  const systemDefault = candidates.find((t) => t.isSystemDefault);
  if (!systemDefault) throw new MissingSystemDefaultTemplateError();
  return systemDefault;
}

/**
 * DB-backed resolver. Loads the doctor's templates + the system default, then
 * delegates to {@link selectTemplate}.
 *
 * DORMANT in Phase 0 — intentionally unreferenced by the pipeline. Phase 1
 * calls this from L4 and records the result into TranscribeVisit
 * .noteTemplateId / .noteTemplateVersion.
 */
export async function resolveActiveTemplate(
  input: ResolveTemplateInput
): Promise<NoteTemplate> {
  const candidates: NoteTemplate[] = await prisma.noteTemplate.findMany({
    where: {
      // ⚠️ #302 — THE TENANT'S TEMPLATES JOIN THE CANDIDATE SET. Without this
      // the selector below cannot reach the chart's format however it is
      // ordered: a candidate that was never loaded cannot be chosen.
      OR: [
        { doctorId: input.doctorId },
        ...(input.tenantPracticeId != null ? [{ practiceId: input.tenantPracticeId }] : []),
        { isSystemDefault: true },
      ],
    },
    // S6 — an unordered findMany returns rows in physical heap order, which is
    // not stable across updates. selectTemplate() re-sorts anyway, but ordering
    // here too means the rows arrive in the same order they will be evaluated
    // in, so anything reading the query log sees what the resolver saw.
    orderBy: [{ updatedAt: 'desc' }, { id: 'desc' }],
  });
  return selectTemplate(candidates, input);
}
