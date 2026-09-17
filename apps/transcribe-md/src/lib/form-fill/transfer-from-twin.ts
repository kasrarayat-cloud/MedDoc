// ============================================================================
// ONE-PIPELINE (#326) — TRANSFER-BY-IDENTITY from a doctor's certified DOCX twin
// onto a detected form (owner directive, Slice D acceptance 2026-09-17).
// ----------------------------------------------------------------------------
// The detector labels a detected form's boxes, but the CLINICAL concept for each
// is the doctor's decision. Rather than guess, we TRANSFER the concept the doctor
// ALREADY approved on their certified twin of the same form (S3 transfer-by-identity,
// applied to the detect pipeline). The map is:
//   • SECTIONS  → label-match (normalized) to the twin's approved label→concept.
//   • NUMBERED  → position-match: the Nth numbered-slot group on the detected form
//     takes the Nth numbered-list concept the twin approved (its `Fill-in` slots,
//     de-duped in displayOrder — e.g. FINDINGS list, then RECOMMENDATIONS list).
//
// ⚠️ EVERY TRANSFERRED CONCEPT MUST BE ONE THE TWIN APPROVED — REFUSE OTHERWISE.
// A concept that is not in the twin's approved set is never assigned. A box the
// transfer cannot resolve is left UNMAPPED, and the caller decides:
//   • a LABELED box left unmapped is a real gap → the ruled act REFUSES (never
//     certifies past a labeled field the doctor has not mapped);
//   • an UNLABELED box (the detector found a fillable region with no label — a
//     signature rule, a stray) is not a doctor-mapped field → EXCLUDED from the
//     fillable set and recorded, not guessed.
// ============================================================================
import { classifyFieldSource } from '@/lib/template-twin/concept-registry';

import type { FormField } from './types';
import type { StoredDetectedField } from './detected-form-store';
import { headerKeyForConcept } from './fill-from-note';
import { deterministicConceptFor } from './map-fields';

/** A field the doctor approved on their certified twin. */
export interface TwinApprovedField {
  originalLabel: string;
  concept: string | null;
  displayOrder: number;
}

export interface TransferResult {
  /** the mappable fields, each carrying a twin-APPROVED concept. */
  fields: StoredDetectedField[];
  /** LABELED boxes the transfer could not resolve to an approved concept — a real
   *  gap; the caller REFUSES rather than certify past them. */
  unmappedLabeled: Array<{ id: string; label: string }>;
  /** UNLABELED boxes excluded from the fillable set (not a doctor-mapped field). */
  excludedUnlabeled: Array<{ id: string; page: number }>;
}

const NUMBERED = /^\s*\d+\.?\s*$/;
const FILL_IN = /^\s*fill-?in\s*$/i;

/** Normalize a label for matching: lower, collapse spaces, strip trailing
 *  punctuation the detector varies on (`:`, `#`, `/`, `.`, `-`, `_`, `*`). */
export function normalizeLabel(s: string): string {
  return s
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[:#*_/\\.\-]+$/g, '')
    .trim();
}

/** The twin's numbered-list concepts, in displayOrder, de-duped by run — e.g.
 *  [procedure.findings, procedure.recommendations]. Derived from the `Fill-in`
 *  (or numbered) twin slots. */
export function numberedListConcepts(twin: ReadonlyArray<TwinApprovedField>): string[] {
  const out: string[] = [];
  for (const f of [...twin].sort((a, b) => a.displayOrder - b.displayOrder)) {
    if (!f.concept) continue;
    if (!(FILL_IN.test(f.originalLabel) || NUMBERED.test(f.originalLabel))) continue;
    if (out[out.length - 1] !== f.concept) out.push(f.concept);
  }
  return out;
}

export function transferFromTwin(
  grouped: ReadonlyArray<FormField>,
  twin: ReadonlyArray<TwinApprovedField>,
): TransferResult {
  const approved = new Set(twin.map((t) => t.concept).filter((c): c is string => !!c));
  const labelMap = new Map<string, string>();
  for (const t of twin) {
    if (!t.concept) continue;
    if (FILL_IN.test(t.originalLabel) || NUMBERED.test(t.originalLabel)) continue;
    labelMap.set(normalizeLabel(t.originalLabel), t.concept);
  }
  const numbered = numberedListConcepts(twin);

  const fields: StoredDetectedField[] = [];
  const unmappedLabeled: Array<{ id: string; label: string }> = [];
  const excludedUnlabeled: Array<{ id: string; page: number }> = [];

  let groupIdx = -1;
  let inNumberedRun = false;

  for (const g of grouped) {
    const label = g.label.trim();
    let concept: string | null = null;

    if (NUMBERED.test(label)) {
      if (!inNumberedRun) {
        groupIdx += 1;
        inNumberedRun = true;
      }
      concept = numbered[groupIdx] ?? null;
    } else {
      inNumberedRun = false;
      // Deterministic registry first (metadata + section headings), then the twin's
      // own approved label→concept. Either way, only an APPROVED concept survives.
      const det = deterministicConceptFor(label);
      concept = det ?? labelMap.get(normalizeLabel(label)) ?? null;
    }

    // ⚠️ REFUSE any concept the twin did not approve.
    if (concept && !approved.has(concept)) concept = null;

    if (!concept) {
      if (label === '') {
        excludedUnlabeled.push({ id: g.id, page: g.page });
        continue; // not a doctor-mapped field — never filled, never masked
      }
      unmappedLabeled.push({ id: g.id, label: g.label });
      // keep it in the field set with a null concept so the caller can see it and
      // REFUSE (certifyDetectedForm refuses on any concept===null field).
    }

    fields.push({
      id: g.id,
      label: g.label,
      page: g.page,
      boxes: g.boxes,
      multiline: g.multiline,
      concept,
      sourceType: classifyFieldSource(label, g.multiline ? { kind: 'narrative_text' } : undefined),
      headerKey: headerKeyForConcept(concept),
    });
  }

  return { fields, unmappedLabeled, excludedUnlabeled };
}
