// ============================================================================
// WHICH SECTIONS ARE THE DOCTOR'S OWN FIXED BLOCKS (ruling #106(a)).
// ----------------------------------------------------------------------------
// ONE definition, applied in TWO places that must never disagree:
//
//   - the PERSIST path (`reviewed-template.ts`, `parse-note-to-template.ts`),
//     so a template uploaded AFTER this lands is classified correctly;
//   - the RECLASSIFICATION MIGRATION, which applies the same predicate in SQL
//     to templates uploaded BEFORE it.
//
// ⚠️ IF THOSE TWO DISAGREE, THE OWNER'S RE-UPLOAD SILENTLY UNDOES THE FIX. The
// migration repairs his current template; the re-upload replaces it with a
// freshly parsed one, and a persist path still forcing `scaffold_confirm` would
// hand his fixed paragraph straight back to the model. That is not a
// hypothetical: the re-upload is the closing step of this very item.
//
// ---------------------------------------------------------------------------
// WHY THIS IS AN ALLOWLIST AND NOT A GENERAL RULE — the honest version
// ---------------------------------------------------------------------------
// #106(a) says fixed prose defaults to `always_include`. Applying that to EVERY
// prose section would be wrong, and the production data says why. Measured on
// the real imaging templates, `defaultText` is one of two entirely different
// things:
//
//   - a WHOLE FIXED BLOCK — the scan-protocol paragraph, the label:value field
//     header. The section IS its default text. Assembling it is the fix.
//   - a SCAFFOLD THE MODEL EXTENDS — a per-leg FINDINGS stub, a per-side
//     IMPRESSION stub. The visit's real content is written AROUND it.
//
// ⚠️ ASSEMBLING THE SECOND KIND WOULD REPLACE THE VISIT'S CLINICAL FINDINGS
// WITH AN EMPTY SKELETON — and it would do so while satisfying every
// static-fidelity check in this programme, because the doctor's bytes would be
// preserved perfectly and only the patient's would be gone. That is a worse
// failure than the one being fixed, and it is silent.
//
// Nothing in the schema distinguishes the two kinds. #106(a) already names the
// answer — `scaffold_confirm` becomes "an explicit, deliberate designation, a
// future doctor-facing control" — and until that control exists, the honest
// implementation is a NAMED, NARROW allowlist of the section kinds that were
// READ and confirmed to be whole fixed blocks on the real forms.
// ============================================================================

import type { NoteTemplateSection } from './system-default-template';

/**
 * Section keys whose `defaultText` is the WHOLE section on every real template
 * examined, rather than a stub the model extends.
 *
 * ⚠️ ADDING A KEY HERE IS A CLINICAL DECISION, NOT A TIDY-UP. Read the section's
 * stored `defaultText` first and ask the one question that matters: *does the
 * visit's own content go INSIDE this section?* If yes, it stays out of this
 * list, whatever its prose looks like.
 *
 * - `technique` — the scan-protocol paragraph. Fixed by the form; the sentence
 *   carrying `500 milliseconds` lives here, and it is the text the live defect
 *   normalised.
 * - `exam_metadata` — the label:value field header (side of exam, referring
 *   physician, machine, location…). Every line is `LABEL: <slot>`; there is no
 *   free prose for a model to add.
 */
export const FIXED_BLOCK_SECTION_KEYS: ReadonlySet<string> = new Set([
  'technique',
  'exam_metadata',
]);

/** True when a template belongs to the slot-bearing / imaging family — the
 *  rollout boundary #106(e) draws. Plain SOAP keeps today's classification and
 *  therefore today's byte-identical prompts. */
export function isSlotBearingFamily(
  sections: readonly NoteTemplateSection[]
): boolean {
  return sections.some((s) => {
    const t = s.defaultText ?? '';
    return t.includes('{{one of:') || t.includes('500 milliseconds');
  });
}

/**
 * The mode a parsed/reviewed section should carry.
 *
 * ⚠️ IT NEVER RETURNS `always_include` FOR A STRUCTURED SECTION. A table's cells
 * hold dictated values; see `staticSections`, which refuses the same shape at
 * render time. Two refusals, deliberately: this one protects the DATA, that one
 * protects the RENDER, and a section that slipped past either would otherwise
 * look like a mode nobody honours.
 */
export function classifyDefaultTextMode(
  section: Pick<NoteTemplateSection, 'key' | 'defaultText' | 'structure'>,
  allSections: readonly NoteTemplateSection[]
): NoteTemplateSection['defaultTextMode'] {
  const text = section.defaultText?.trim() ?? '';
  if (text.length === 0) return 'omit_unless_supported';
  if (section.structure) return 'scaffold_confirm';
  if (!FIXED_BLOCK_SECTION_KEYS.has(section.key)) return 'scaffold_confirm';
  if (!isSlotBearingFamily(allSections)) return 'scaffold_confirm';
  // ⚠️ A FIELD BLOCK IS A FIXED BLOCK ONLY WHEN ITS FIELDS ARE SLOTS, and this
  // clause was added after the allowlist's own premise was found false on a
  // real row. `exam_metadata` is justified above as "every line is
  // `LABEL: <slot>`; there is no free prose for a model to add" — but one
  // production template's is SEVEN LINES WITH ZERO SLOTS, labels awaiting
  // values the model fills as text. Assembling that one freezes seven fields at
  // the blank form's bytes forever: the scaffold-the-model-extends class this
  // function exists to exclude, wearing the right key.
  //
  // A protocol paragraph is fixed prose whether or not it carries a slot, so
  // `technique` needs no such test. Mirrored exactly in the migration.
  if (section.key === 'exam_metadata' && !text.includes('{{one of:')) {
    return 'scaffold_confirm';
  }
  return 'always_include';
}
