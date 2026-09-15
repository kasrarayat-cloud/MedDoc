// ============================================================================
// S2-4 END-TO-END (ruling #322): the certified twin's values, on the owner's
// ORIGINAL colon page. Derive anchors from the twin fields → bridge the twin's
// resolutions → fill the doctor's page → the values are present, in place.
// ============================================================================
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';
import { getDocumentProxy, extractText } from 'unpdf';

import { deriveTwinAnchors, type TwinAnchorField } from '../twin-anchor-derivation';
import { buildTwinFillTexts } from '../twin-value-bridge';
import { fillPdfTemplate } from '../fill-engine';
import type { FieldResolution } from '@/lib/template-twin/ir';

const FIXTURE = join(
  dirname(fileURLToPath(import.meta.url)),
  '__fixtures__',
  'colon-operative-reportlab.pdf',
);
const canvas = () => new Uint8Array(readFileSync(FIXTURE));

// 3 header fields + ALL 6 numbered slots (the count guard requires the full
// Fill-in set to match the form's 6 markers; a partial set falls back by design).
const FIELDS: TwinAnchorField[] = [
  { fieldId: 'ttf_000000000000000000000002', label: 'PATIENT NAME', displayOrder: 2 },
  { fieldId: 'ttf_000000000000000000000005', label: 'DATE OF PROCEDURE', displayOrder: 5 },
  { fieldId: 'ttf_000000000000000000000007', label: 'PROCEDURE', displayOrder: 7 },
  { fieldId: 'ttf_00000000000000000000000b', label: 'Fill-in', displayOrder: 13 },
  { fieldId: 'ttf_00000000000000000000000c', label: 'Fill-in', displayOrder: 14 },
  { fieldId: 'ttf_00000000000000000000000d', label: 'Fill-in', displayOrder: 15 },
  { fieldId: 'ttf_000000000000000000000011', label: 'Fill-in', displayOrder: 22 },
  { fieldId: 'ttf_000000000000000000000012', label: 'Fill-in', displayOrder: 23 },
  { fieldId: 'ttf_000000000000000000000013', label: 'Fill-in', displayOrder: 24 },
];

const res = (fieldId: string, value: string | null): FieldResolution => ({
  fieldId,
  status: value === null ? 'not_mentioned' : 'supported',
  value,
  sourceFactIds: value === null ? [] : ['ttfact_000000000000000000000001'],
  evidenceAnchorIds: value === null ? [] : ['a1'],
  selectedOptionOrdinal: null,
  reasonCode: 'x',
  clinicianReviewed: false,
});

async function pageText(bytes: Uint8Array): Promise<string> {
  const { text } = await extractText(await getDocumentProxy(bytes.slice()), { mergePages: true });
  return (Array.isArray(text) ? text.join('\n') : text).replace(/\s+/g, ' ');
}

describe('S2-4 — twin values fill the doctor original colon page', () => {
  it('draws the twin resolved values onto the original page (labelled + numbered slot)', async () => {
    const proxy = await getDocumentProxy(canvas());
    const { anchors, unlocatable } = await deriveTwinAnchors(proxy as never, FIELDS);
    expect(unlocatable).toEqual([]);

    const resolutions = [
      res('ttf_000000000000000000000002', 'Jane Q Testpatient'),
      res('ttf_000000000000000000000005', '2026-09-14'),
      res('ttf_000000000000000000000007', 'Screening colonoscopy with polypectomy'),
      res('ttf_00000000000000000000000b', 'Adenomatous polyp, sigmoid colon'),
    ];
    const { texts, unplaceable } = buildTwinFillTexts(resolutions, anchors, unlocatable);
    expect(unplaceable).toEqual([]);
    // Each RESOLVED value routed to its fieldId-keyed anchor (the other Fill-in
    // slots have no resolution here, so they stay blank — nothing to place).
    expect(Object.keys(texts).sort()).toEqual(resolutions.map((r) => r.fieldId).sort());

    const out = await fillPdfTemplate({ canvasPdf: canvas(), anchors, texts });
    const text = await pageText(out);
    // The doctor's own labels survive (verbatim canvas)…
    expect(text).toContain('PATIENT NAME');
    expect(text).toContain('OPERATIVE NOTE');
    // …and the twin's resolved values are drawn onto it.
    expect(text).toContain('Jane Q Testpatient');
    expect(text).toContain('Screening colonoscopy with polypectomy');
    expect(text).toContain('Adenomatous polyp, sigmoid colon');
  });

  it('a resolved value with no anchor is UNPLACEABLE → the caller falls back (never a partial page)', async () => {
    const proxy = await getDocumentProxy(canvas());
    const { anchors, unlocatable } = await deriveTwinAnchors(proxy as never, FIELDS);
    // A resolution for a field that is not in the derived anchors at all.
    const resolutions = [
      res('ttf_000000000000000000000002', 'Jane'),
      res('ttf_ffffffffffffffffffffffff', 'a value with nowhere to go'),
    ];
    const { unplaceable } = buildTwinFillTexts(resolutions, anchors, unlocatable);
    expect(unplaceable).toContain('ttf_ffffffffffffffffffffffff');
  });
});
