// ============================================================================
// F16 — the ONE readiness classifier, in a leaf module.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS IS ITS OWN FILE, AND WHY THAT IS THE POINT.
//
// This predicate decides which fields are counted in the refusal a physician
// reads. It used to live inline in `synthetic-test.ts` — TWICE, in two shapes,
// against two different row types — and `synthetic-test.ts` imports prisma,
// storage, the fill engine and the docx parser. So the predicate could not be
// loaded by a unit test at all, and the F16 gate's own header claimed to guard
// a property ("the count is of FIELDS, not of reasons") that lived entirely in
// code nothing could execute.
//
// The independent adversarial pass measured that: **no test anywhere executed
// the readiness predicate**, and three of four partial landings of F16 left the
// gate at 7 passed. Moving the predicate to a leaf is what makes it assertable
// without standing up a database.
//
// ⚠️ AND THE TWO COPIES HAD ALREADY DIVERGED, WHICH IS THE ARGUMENT FOR ONE.
// The early copy classified with a TWO-way expression —
//
//     field.mapping ? `${fieldId}:unconfirmed` : `${fieldId}:no_mapping`
//
// — while filtering on the THREE-way predicate. So a field that was genuinely
// CERTIFIED but had no clinical concept was reported to the audit row as
// `:unconfirmed`. The count was right and the REASON was false: the one reader
// of `blocking` was sent to re-confirm a field that was already confirmed,
// instead of supplying the concept it actually lacked. Two copies of one rule
// drift the day either is touched; there is now one.
// ============================================================================

/** Why a single field is not ready. `null` means it IS ready.
 *
 *  ⚠️ This union is the vocabulary `TemplateTwinSyntheticTestError.blocking`
 *  documents. It is a CLOSED set of reason codes and never free text — the
 *  entries are written to an audit row that fans out to the admin activity
 *  stream, and the customer's field labels never join them. */
export type UnreadyReason = 'no_mapping' | 'unconfirmed' | 'no_concept';

/** The normalised shape both call sites reduce to.
 *
 *  ⚠️ `status` ARRIVES ALREADY LOWERCASED. The database column is a Postgres
 *  enum (`CERTIFIED` / `NEEDS_CONFIRMATION`, uppercase); `mapping()` lowercases
 *  it when it parses a row. Taking the normalised form here means this module
 *  cannot be the place a case seam is introduced — there is exactly one
 *  `.toLowerCase()` per path and it happens before the call. */
export interface ReadinessRow {
  status: string;
  sourceType: string;
  clinicalConcept: string | null;
}

/**
 * Classify one field. **This is the whole readiness rule** — the gate refuses
 * if and only if this returns non-null for at least one field.
 *
 * ⚠️ THE ORDER OF THE CHECKS IS THE REASON CODE, NOT THE VERDICT. A field can
 * be both unconfirmed and concept-less; the verdict is the same either way and
 * only the reported reason differs. It is deliberately reported as ONE entry —
 * counting reasons would tell a physician with six blockers that there are
 * seven, and send them hunting a field that does not exist.
 */
export function unreadyReason(row: ReadinessRow | null | undefined): UnreadyReason | null {
  if (!row) return 'no_mapping';
  if (row.status !== 'certified') return 'unconfirmed';
  // A manual field has no concept BY CONSTRUCTION — nothing dictates who the
  // technologist on shift was, so there is no fact to cite. It is ready when it
  // is confirmed; it renders blank and is attested blank.
  if (row.sourceType !== 'manual' && !row.clinicalConcept) return 'no_concept';
  return null;
}

/**
 * Collect `"<fieldId>:<reason>"` for every field that is not ready.
 *
 * ⚠️ EXACTLY ONE ENTRY PER FIELD, BY CONSTRUCTION — the map returns a single
 * reason and the filter drops the ready ones, so `result.length` is a count of
 * FIELDS and can be rendered to a physician as one. That is the property the
 * gate could not previously execute.
 *
 * Ids and reason codes only. Never a label, never encounter text, never a
 * filled value.
 */
export function collectUnready(
  fields: readonly { fieldId: string; mapping: ReadinessRow | null }[],
): string[] {
  const out: string[] = [];
  for (const field of fields) {
    const reason = unreadyReason(field.mapping);
    if (reason) out.push(`${field.fieldId}:${reason}`);
  }
  return out;
}
