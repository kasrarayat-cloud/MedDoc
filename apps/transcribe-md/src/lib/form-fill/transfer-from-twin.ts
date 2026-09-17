// ============================================================================
// ONE-PIPELINE (#326) — TRANSFER-BY-IDENTITY from a doctor's certified DOCX twin
// onto a detected form (owner directive, Slice D acceptance 2026-09-17).
// ----------------------------------------------------------------------------
// The detector labels a detected form's boxes, but the CLINICAL concept for each
// is the doctor's decision. Rather than guess, we TRANSFER the concept the doctor
// ALREADY approved on their certified twin of the same form (S3 transfer-by-identity,
// applied to the detect pipeline). The map is PURE IDENTITY — the twin's own
// label→concept, never the shared registry:
//   • SECTIONS  → label-match (normalized) to the twin's approved label→concept.
//   • NUMBERED  → the Nth numbered-slot GROUP on the detected form takes the Nth
//     numbered-list concept the twin approved (its `Fill-in` slots, de-duped by run).
//
// ⚠️ WHY NOT THE REGISTRY (deterministicConceptFor). An adversarial pass showed a
// registry-FIRST lookup silently OVERRIDES the doctor's own decision: the registry
// maps "POST-OPERATIVE FINDINGS"→procedure.findings while the twin approved
// procedure.recommendations for that exact label, and registry-first wins. That is
// the RULING-C class this transfer exists to defend against. So the twin's own
// label→concept is the ONLY source; the registry is not consulted here.
//
// ⚠️ NUMBERED GROUPS ARE MATCHED BY ORDER WITH A COUNT GUARD. Two clinically
// distinct lists that are ADJACENT (no non-numbered box between — a heading with no
// blank produces no box) would otherwise collapse into one run and the second list
// would inherit the first's concept. So when the number of detected numbered GROUPS
// does not equal the number of twin numbered LISTS, EVERY numbered slot is REFUSED
// (left unmapped) rather than guessed — the caller then declines.
//
// ⚠️ EVERY TRANSFERRED CONCEPT MUST BE ONE THE TWIN APPROVED — REFUSE OTHERWISE.
//   • a LABELED box left unmapped is a real gap → the ruled act REFUSES;
//   • an UNLABELED box (a signature rule, a stray) is EXCLUDED, never guessed.
// ============================================================================
import { classifyFieldSource } from '@/lib/template-twin/concept-registry';

import type { FormField } from './types';
import type { StoredDetectedField } from './detected-form-store';
import { headerKeyForConcept } from './fill-from-note';

/** A field the doctor approved on their certified twin. */
export interface TwinApprovedField {
  originalLabel: string;
  concept: string | null;
  displayOrder: number;
}

export interface TransferResult {
  fields: StoredDetectedField[];
  /** LABELED boxes with no approved twin concept — a real gap; caller REFUSES. */
  unmappedLabeled: Array<{ id: string; label: string }>;
  /** UNLABELED boxes excluded from the fillable set (not a doctor-mapped field). */
  excludedUnlabeled: Array<{ id: string; page: number }>;
}

// ⚠️ SAME numbered-slot pattern group-fields.ts uses (it decides a box is a list
// slot); a narrower one here would send "2)"/"(3)" to the label path and refuse a
// mappable form.
const NUMBERED = /^\s*\(?\d+\s*[.)]?\s*$/;
const FILL_IN = /^\s*fill-?in\s*$/i;

/** Normalize a label for identity matching: lower, collapse spaces, strip trailing
 *  punctuation the detector varies on. */
export function normalizeLabel(s: string): string {
  return s
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[:#*_/\\.\-]+$/g, '')
    .trim();
}

/** The twin's numbered-list concepts, in displayOrder, de-duped by run — e.g.
 *  [procedure.findings, procedure.recommendations]. */
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

  // The doctor's OWN label→concept (identity). First-wins on a normalize collision.
  const labelMap = new Map<string, string>();
  for (const t of twin) {
    if (!t.concept) continue;
    if (FILL_IN.test(t.originalLabel) || NUMBERED.test(t.originalLabel)) continue;
    const k = normalizeLabel(t.originalLabel);
    if (!labelMap.has(k)) labelMap.set(k, t.concept);
  }
  const lists = numberedListConcepts(twin);

  // ── PRE-PASS: count the detected numbered GROUPS (runs of consecutive slots).
  let detectedGroups = 0;
  {
    let inRun = false;
    for (const g of grouped) {
      if (NUMBERED.test(g.label.trim())) {
        if (!inRun) {
          detectedGroups += 1;
          inRun = true;
        }
      } else inRun = false;
    }
  }
  // Numbered structure must line up with the twin's list count, or every numbered
  // slot is refused (never guessed) — this is the count guard for the adjacency
  // collapse. Also refuses "some numbered slots but the twin has no numbered list".
  const numberedOk = detectedGroups > 0 && detectedGroups === lists.length;

  const fields: StoredDetectedField[] = [];
  const unmappedLabeled: Array<{ id: string; label: string }> = [];
  const excludedUnlabeled: Array<{ id: string; page: number }> = [];

  let groupIdx = -1;
  let inRun = false;

  for (const g of grouped) {
    const label = g.label.trim();
    let concept: string | null = null;

    if (NUMBERED.test(label)) {
      if (!inRun) {
        groupIdx += 1;
        inRun = true;
      }
      concept = numberedOk ? (lists[groupIdx] ?? null) : null;
    } else {
      inRun = false;
      concept = labelMap.get(normalizeLabel(label)) ?? null; // twin IDENTITY only
    }

    // Defensive — labelMap/lists are approved by construction; never transfer past it.
    if (concept && !approved.has(concept)) concept = null;

    if (!concept) {
      if (label === '') {
        excludedUnlabeled.push({ id: g.id, page: g.page });
        continue;
      }
      unmappedLabeled.push({ id: g.id, label: g.label });
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
