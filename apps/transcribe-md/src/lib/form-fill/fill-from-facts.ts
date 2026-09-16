// ============================================================================
// ONE-PIPELINE (ruling #326, Slice B) — TIER 1 value source: a detected box
// mapped to a CLINICAL concept fills from the visit's PROJECTED FACTS for that
// concept, through the ruled resolver (polarity / temporality / denial). Owner
// decision 2026-09-16.
// ----------------------------------------------------------------------------
// ⚠️ HOW THIS REUSES THE RULED LOGIC WITHOUT THE DOCX RENDERER. The resolver
// (`resolveTemplateFields`) applies the ruled polarity/temporality/denial logic
// per field and NEVER reads `rendererBinding` — that field is the DOCX renderer's
// locator, and a detected form does not render into Word, it draws into PDF boxes.
// So we synthesise a SCHEMA-VALID but INERT `rendererBinding` (a `/detected/...`
// path, zero content hashes) purely to satisfy `TemplateFieldSchema.parse`; the
// resolver's value resolution is identical to a real twin field's. This is the
// half of the twin pipeline that IS right for a detected box (the ruled fact
// logic), kept, while the DOCX-render half is dropped.
//
// A "denied finding" therefore renders BLANK here, exactly as the twin renders it
// — the note-heading split (tier 2) could not do that, which is why a
// clinical-concept box must NOT fall through to it. Tier 2 is only for a box whose
// concept has NO candidate facts this visit (a genuine free-prose section).
// ============================================================================
import { resolveTemplateFields } from '@/lib/template-twin/resolver';
import { conceptCandidateFacts } from '@/lib/template-twin/fact-mapping-match';
import { resolvedValueToText } from '@/lib/pdf-native/twin-value-bridge';
import type { EncounterFact, SemanticMapping, TemplateField } from '@/lib/template-twin/ir';
import { createHash } from 'node:crypto';

import type { StoredDetectedField } from './detected-form-store';

const ZERO_SHA = '0'.repeat(64);

/** A stable `ttf_<24 hex>` field id derived from the detected box id — the twin
 *  fieldId shape the resolver's schema requires, deterministic per box so a
 *  re-resolve of the same box maps to the same synthetic field. */
export function syntheticFieldId(boxId: string): string {
  return `ttf_${createHash('sha256').update(boxId).digest('hex').slice(0, 24)}`;
}

/** Synthesise a schema-valid, resolver-inert `TemplateField` for a detected box.
 *  The binding is a placeholder the resolver never reads (see the header). */
export function synthesizeTemplateField(box: StoredDetectedField, displayOrder: number): TemplateField {
  return {
    fieldId: syntheticFieldId(box.id),
    kind: 'narrative_text',
    originalLabel: box.label.trim() || box.id,
    labelSource: 'generated',
    displayOrder,
    detectionStatus: 'certified',
    allowedOptions: [],
    rendererBinding: {
      partName: 'detected/form.pdf',
      bindingType: 'content_control',
      path: `/detected/${box.id}`,
      ordinal: displayOrder,
      sdtId: null,
      tag: null,
      alias: null,
      legacyName: null,
      tableIndex: null,
      rowLaterality: 'unknown',
      rowIndex: null,
      cellIndex: null,
      repeatAncestorPath: null,
      sourceControlSha256: ZERO_SHA,
      originalContentSha256: ZERO_SHA,
    },
    required: false,
    unknownPolicy: 'blank',
    // false so a denial-withheld / unmentioned clinical box renders BLANK without
    // BLOCKING the synthetic certify (the twin blocks only on clinically-material
    // fields; a detected box carries no such per-field ruling yet — the doctor's
    // confirmed mapping is a #326 step-3 refinement).
    clinicallyMaterial: false,
    criticality: 'routine',
    tableId: null,
    rowPrototype: false,
  };
}

/** Synthesise the `SemanticMapping` for a fact-concept box. `explicit_denial_allowed`
 *  is the safe default — it RESPECTS a dictated denial (renders blank) rather than
 *  stamping the affirmative, honouring "the ruled denial logic". (An AI-proposed,
 *  doctor-confirmed per-concept polarity is the #326 step-3 refinement.) */
export function synthesizeMapping(field: TemplateField, concept: string): SemanticMapping {
  return {
    fieldId: field.fieldId,
    sourceType: 'extraction',
    clinicalConcept: concept,
    expectedDataType: 'text',
    polarityBehavior: 'explicit_denial_allowed',
    temporality: 'any',
    laterality: 'optional',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
  };
}

export interface FactValueResult {
  /** boxId → the resolved value text (only boxes that resolved to a placeable,
   *  non-empty value appear). */
  values: Map<string, string>;
  /** boxIds whose concept HAD ≥1 candidate fact this visit — a fact-covered box,
   *  whether it resolved to a value or to a ruled blank (denial/unmentioned). The
   *  caller must NOT fall such a box through to the note-heading split. */
  factCovered: Set<string>;
}

/**
 * Resolve every fact-concept detected box against the projected facts, through
 * the ruled resolver. `allowUncertified` is true for the synthetic certify proof
 * (the fields are not yet certified); at export the form IS certified, so the
 * synthesised ids are passed as `certifiedFieldIds`.
 */
export function fillFromFacts(
  factFields: ReadonlyArray<StoredDetectedField>,
  facts: ReadonlyArray<EncounterFact>,
  opts: { allowUncertified: boolean },
): FactValueResult {
  const values = new Map<string, string>();
  const factCovered = new Set<string>();
  if (factFields.length === 0) return { values, factCovered };

  const fields: TemplateField[] = [];
  const mappings: SemanticMapping[] = [];
  const idToBox = new Map<string, string>();
  factFields.forEach((box, i) => {
    const field = synthesizeTemplateField(box, i);
    const mapping = synthesizeMapping(field, box.concept as string);
    fields.push(field);
    mappings.push(mapping);
    idToBox.set(field.fieldId, box.id);
    // A concept with ≥1 candidate fact is fact-covered — record BEFORE resolution
    // so a ruled blank (denied/unmentioned) still suppresses the tier-2 fallback.
    if (conceptCandidateFacts(mapping, facts).length > 0) factCovered.add(box.id);
  });

  const resolutions = resolveTemplateFields({
    fields,
    mappings,
    facts,
    allowUncertifiedForSyntheticTest: opts.allowUncertified,
    certifiedFieldIds: opts.allowUncertified ? undefined : fields.map((f) => f.fieldId),
  });

  for (const r of resolutions) {
    const boxId = idToBox.get(r.fieldId);
    if (!boxId) continue;
    if (r.value === null || r.value === undefined) continue;
    const text = resolvedValueToText(r.value);
    if (text === null) continue; // a non-scalar (table/boolean) cannot draw as box text
    if (text.trim() === '') continue;
    values.set(boxId, text);
  }

  return { values, factCovered };
}
