// ============================================================================
// ONE-PIPELINE (ruling #326, Slice B) — the 3-TIER value orchestrator. Given the
// mapped detected fields + a visit's projected facts + the note, produce the
// { boxId → text } map the fill engine draws. Owner decision 2026-09-16:
//   TIER 1  a box mapped to a CLINICAL concept  → the projected FACTS for that
//           concept, through the ruled resolver (polarity/temporality/denial).
//   TIER 2  a SECTION box (its concept has NO candidate facts this visit) → the
//           note-heading split.
//   TIER 3  a METADATA box (record-derived: name/date/surgeon/…) → the record.
//
// certify (synthetic facts) and export (the visit's projected `entities`) both
// call THIS — one value path, so a real export takes exactly what certification
// proved (the synthetic-test.ts doctrine).
//
// ⚠️ TIER-1 NEVER FALLS THROUGH TO TIER-2. A fact-covered box that the resolver
// left BLANK did so for a ruled reason (a dictated denial, an unmentioned value);
// routing it to the raw note-heading split would overwrite that ruled blank with
// prose and defeat the polarity logic. `factCovered` (not "produced a value")
// governs the split.
// ============================================================================
import type { EncounterFact } from '@/lib/template-twin/ir';

import type { StoredDetectedField } from './detected-form-store';
import { fillFromFacts } from './fill-from-facts';
import { fillFromNote, type NoteFillContext } from './fill-from-note';

export interface DeriveValuesResult {
  values: Map<string, string>;
  /** Note sections with content matching NO detected box — carried by the caller
   *  so real clinical content is never silently dropped. */
  addenda: Array<{ label: string; text: string }>;
}

export function deriveDetectedFormValues(input: {
  fields: ReadonlyArray<StoredDetectedField>;
  facts: ReadonlyArray<EncounterFact>;
  noteCtx: NoteFillContext;
  /** true only for the synthetic certify proof (fields not yet certified). */
  allowUncertified: boolean;
}): DeriveValuesResult {
  const metadata = input.fields.filter((f) => f.headerKey !== null); // tier 3
  const conceptBoxes = input.fields.filter((f) => f.headerKey === null && f.concept !== null);

  // ── TIER 1 — fact-concept resolution (ruled).
  const { values: factValues, factCovered } = fillFromFacts(conceptBoxes, input.facts, {
    allowUncertified: input.allowUncertified,
  });

  // ── TIER 2 + 3 — the note-heading split for the concept boxes NOT covered by
  // facts, and the record for metadata. `fillFromNote` routes headerKey vs body.
  const sectionBoxes = conceptBoxes.filter((f) => !factCovered.has(f.id));
  const { values: noteValues, addenda } = fillFromNote([...metadata, ...sectionBoxes], input.noteCtx);

  // Merge — tier 1 wins. (No key overlap by construction: a fact-covered box is
  // excluded from the note-split set; the explicit precedence guards a refactor.)
  const values = new Map(noteValues);
  for (const [boxId, text] of factValues) values.set(boxId, text);

  return { values, addenda };
}
