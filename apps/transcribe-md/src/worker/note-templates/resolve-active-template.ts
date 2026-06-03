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
  /** The signing/owning doctor (User.id). */
  doctorId: string;
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
export function selectTemplate(
  candidates: readonly NoteTemplate[],
  { doctorId, encounterType = null }: ResolveTemplateInput
): NoteTemplate {
  const active = candidates.filter((t) => t.status === 'active');

  // 1. doctor's template for this exact encounter type (only when a type
  //    was requested — a null request skips straight to the catch-all).
  if (encounterType != null) {
    const exact = active.find(
      (t) => t.doctorId === doctorId && t.encounterType === encounterType
    );
    if (exact) return exact;
  }

  // 2. doctor's catch-all (encounterType === null).
  const doctorDefault = active.find(
    (t) => t.doctorId === doctorId && t.encounterType === null
  );
  if (doctorDefault) return doctorDefault;

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
      OR: [{ doctorId: input.doctorId }, { isSystemDefault: true }],
    },
  });
  return selectTemplate(candidates, input);
}
