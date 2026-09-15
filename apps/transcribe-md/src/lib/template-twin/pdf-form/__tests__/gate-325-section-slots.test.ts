// ============================================================================
// #325 — the S2 PDF path binds numbered-slot sections to their concept. The
// owner's colon form's POSTOPERATIVE FINDINGS / RECOMMENDATIONS slots derive as
// bare `Fill-in` controls (anchoring is by order over the ORIGINAL PDF markers,
// so the alias MUST stay `Fill-in`), but carry a `pdfsec:<concept>` tag that pins
// the section concept and makes the slots BULLET-GROUP (distribute one item per
// slot). PREOPERATIVE DIAGNOSIS (single) is fielded and tagged too; DD/DT map
// through their parenthetical suffix.
// ============================================================================
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { getDocumentProxy } from 'unpdf';

import { pdfToProseDocx, annotateAffordancesWithGroups, type LineBox } from '../pdf-to-prose-docx';
import { visitMetadataConceptFor } from '../../concept-registry';
import { deriveProseTwin, derivedTwinProbeIsValid, FILL_IN_LABEL } from '../../prose-form/derive-prose-twin';
import { compileTemplateDocx } from '@/lib/note-template-docx';
import { compilerDecidedConcept } from '../../semantic-mapping';
import { bulletGroups } from '../../bullet-groups';
import type { SemanticMapping, TemplateField } from '../../ir';

const FIX = join(
  dirname(fileURLToPath(import.meta.url)),
  '..', '..', '..', 'pdf-native', '__tests__', '__fixtures__', 'colon-operative-reportlab.pdf',
);

const verify = async (b: Uint8Array, expected: number): Promise<boolean> => {
  try {
    return derivedTwinProbeIsValid(compileTemplateDocx(b), expected);
  } catch {
    return false;
  }
};

async function compiledColonTwin() {
  const prose = await pdfToProseDocx(new Uint8Array(readFileSync(FIX)).slice());
  if (!prose) throw new Error('pdfToProseDocx returned null');
  const derived = await deriveProseTwin(prose.bytes, verify, prose.directives);
  if (!derived) throw new Error('deriveProseTwin returned null');
  return compileTemplateDocx(derived.bytes);
}

/** A minimal list-valued mapping for a field, using its compiler-decided concept
 *  (or a fallback). The bullet-group check only reads alias/tag + concept keys. */
function mappingFor(f: TemplateField): SemanticMapping {
  const concept = compilerDecidedConcept(f, []) ?? 'plan';
  return {
    fieldId: f.fieldId,
    clinicalConcept: concept,
    sourceType: 'extraction',
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: null,
    laterality: 'not_applicable',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    conceptScope: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
  } as unknown as SemanticMapping;
}

describe("#325 — the owner's colon form's section slots bind + group", () => {
  it('findings/recommendations slots are Fill-in + tagged with their concept', async () => {
    const ir = await compiledColonTwin();
    const slots = ir.fields.filter((f) => f.originalLabel === FILL_IN_LABEL);
    // Six bare slots: three findings, three recommendations.
    expect(slots.length).toBe(6);
    const findings = slots.filter((f) => compilerDecidedConcept(f, []) === 'procedure.findings');
    const recs = slots.filter((f) => compilerDecidedConcept(f, []) === 'procedure.recommendations');
    expect(findings.length).toBe(3);
    expect(recs.length).toBe(3);
    // Anchoring invariant: every slot keeps the generic Fill-in alias (zipped to the
    // PDF's bare markers BY ORDER, never matched as a label).
    expect(slots.every((f) => f.originalLabel === FILL_IN_LABEL)).toBe(true);
    // Each section's three slots share ONE tag (so they group).
    expect(new Set(findings.map((f) => f.rendererBinding.tag))).toEqual(
      new Set(['pdfsec:procedure.findings']),
    );
    expect(new Set(recs.map((f) => f.rendererBinding.tag))).toEqual(
      new Set(['pdfsec:procedure.recommendations']),
    );
  });

  it('the six slots form exactly TWO bullet groups of three (they distribute)', async () => {
    const ir = await compiledColonTwin();
    const mappings = ir.fields.map(mappingFor);
    const groups = bulletGroups(ir.fields, mappings);
    expect(groups.map((g) => g.memberFieldIds.length).sort()).toEqual([3, 3]);
  });

  it('PREOPERATIVE DIAGNOSIS is fielded as a single block → procedure.preop_diagnosis', async () => {
    const ir = await compiledColonTwin();
    const preop = ir.fields.find((f) => /preoperative diagnosis/i.test(f.originalLabel));
    expect(preop).toBeDefined();
    expect(compilerDecidedConcept(preop!, [])).toBe('procedure.preop_diagnosis');
    expect(preop!.rendererBinding.tag).toBe('pdfsec:procedure.preop_diagnosis');
  });

  it('DD/DT with a parenthetical suffix map to the dictation/transcription dates', async () => {
    const ir = await compiledColonTwin();
    const dd = ir.fields.find((f) => /^dd\b/i.test(f.originalLabel));
    const dt = ir.fields.find((f) => /^dt\b/i.test(f.originalLabel));
    expect(compilerDecidedConcept(dd!, [])).toBe('visit_metadata.dictated_at');
    expect(compilerDecidedConcept(dt!, [])).toBe('visit_metadata.transcribed_at');
  });

  // ── ADVERSARIAL FIXES: no cross-specialty over-reach ────────────────────────
  it('⚠️ a radiology-style bare FINDINGS / free-text RECOMMENDATIONS is NOT tagged operative', () => {
    // An ultrasound/radiology report: colon-less "FINDINGS" and "RECOMMENDATIONS"
    // headings over a free-text writing area (no numbered markers), deep in the body.
    // procedure.findings/.recommendations are OPERATIVE concepts — they must not bind
    // an imaging section (which would override the model + auto-confirm).
    const row = (text: string, y: number, x0 = 44, x1 = 200): LineBox => ({ text, page: 0, y, x0, x1, height: 10 });
    const boxes: LineBox[] = [
      row('SPRINGFIELD IMAGING', 760),
      row('PATIENT NAME:', 740, 44, 120),
      row('DOB:', 720, 44, 80),
      row('MRN:', 700, 44, 80),
      row('DATE:', 680, 44, 90),
      row('STUDY:', 660, 44, 100),
      row('FINDINGS', 620), // bare — radiology style, deep (>= 6 rows above)
      row('IMPRESSION', 520),
      row('RECOMMENDATIONS', 480), // free-text, no markers below
      row('SIGNATURE', 380),
    ];
    const annotated = annotateAffordancesWithGroups(boxes, [], () => 612);
    const byText = new Map(boxes.map((b, i) => [b.text, annotated[i]]));
    // Neither imaging heading acquires a pdfsec tag.
    expect(byText.get('FINDINGS')?.group).toBeNull();
    expect(byText.get('RECOMMENDATIONS')?.group).toBeNull();
  });

  it('⚠️ "DD (differential diagnosis)" is NOT a dictation date (only the literal clarifier)', () => {
    expect(visitMetadataConceptFor('DD (dictated)')).toBe('visit_metadata.dictated_at');
    expect(visitMetadataConceptFor('DT (transcribed)')).toBe('visit_metadata.transcribed_at');
    expect(visitMetadataConceptFor('DD (differential diagnosis)')).toBeNull();
  });

  it('every field is now conceptable — no bare Fill-in with a null concept remains', async () => {
    const ir = await compiledColonTwin();
    // The remaining `Fill-in` fields all resolve a concept (via the section tag);
    // there is no longer an unmappable slot to make auto-certify decline.
    const orphanBlanks = ir.fields.filter(
      (f) => f.originalLabel === FILL_IN_LABEL && compilerDecidedConcept(f, []) === null,
    );
    expect(orphanBlanks).toEqual([]);
  });
});
