// Stage 3 (map) — assign each grouped field a note-model concept, once per
// template (#326 Slice B). Deterministic first: the same registry the DOCX-twin
// proposer uses (conceptOverrideFor / visitMetadataConceptFor /
// sectionHeadingConceptFor), gated by isRegisteredConcept. A field with no
// deterministic concept is left UNMAPPED with status 'needs_confirmation' — the
// doctor confirms it in the sample-value preview; nothing is guessed onto a
// clinical field. This does NOT fork the resolver: the concept is the same
// vocabulary resolveTemplateFields already understands.

import {
  classifyFieldSource,
  conceptOverrideFor,
  isRegisteredConcept,
  sectionHeadingConceptFor,
  visitMetadataConceptFor,
} from '@/lib/template-twin/concept-registry';

import type { FormField } from './types';

export interface FieldConcept {
  fieldId: string;
  label: string;
  /** the mapped note-model concept, or null when the doctor must confirm it */
  concept: string | null;
  /** provenance class (#247): visit_metadata vs dictation vs manual, etc. */
  sourceType: string;
  status: 'recognized' | 'needs_confirmation';
}

/** The deterministic concept for a label, or null. Order mirrors the DOCX-twin
 *  proposer: an explicit override, then visit-metadata, then a section heading. */
export function deterministicConceptFor(label: string): string | null {
  const c =
    conceptOverrideFor(label) ??
    visitMetadataConceptFor(label) ??
    sectionHeadingConceptFor(label);
  if (!c) return null;
  return isRegisteredConcept(c) ? c : null;
}

export function mapFieldsToConcepts(fields: FormField[]): FieldConcept[] {
  return fields.map((f) => {
    const label = f.label.trim();
    const concept = label ? deterministicConceptFor(label) : null;
    const kind = f.multiline ? 'narrative_text' : undefined;
    return {
      fieldId: f.id,
      label: f.label,
      concept,
      sourceType: classifyFieldSource(label, kind ? { kind } : undefined),
      // a deterministic registry hit is recognized; everything else waits for
      // the doctor's confirmation in the preview.
      status: concept ? 'recognized' : 'needs_confirmation',
    };
  });
}

/** fieldId → concept, only for fields that HAVE a concept. */
export function conceptMapOf(mapped: FieldConcept[]): Map<string, string> {
  const m = new Map<string, string>();
  for (const fc of mapped) if (fc.concept) m.set(fc.fieldId, fc.concept);
  return m;
}
