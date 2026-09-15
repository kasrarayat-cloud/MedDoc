// ============================================================================
// #324 — a BOLD HEADING FOLLOWED BY AN EMPTY MULTI-LINE GAP derives ONE
// multi-line control (CONSENT, DESCRIPTION OF PROCEDURE); a heading with no gap
// stays prose (owner ruling, 2026-09-15).
//
// "Bold" is approximated structurally — unpdf's text layer carries no font
// weight — so the affordance is: a colon-less, label-shaped line, IN THE BODY,
// with a multi-line empty gap beneath it. The BODY gate is load-bearing: the
// same shape ABOVE the topmost labelled row is a document TITLE (OPERATIVE NOTE,
// COLONOSCOPY) and must stay prose, or every title with spacing beneath it mints
// a phantom control.
// ============================================================================
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { getDocumentProxy } from 'unpdf';

import { annotateAffordances, groupLineBoxes, type LineBox } from '../pdf-to-prose-docx';
import { extractRuleSegments } from '../pdf-geometry';

// A page ~612pt wide (US Letter). No drawn rule segments — the gap is the only
// affordance under test, so the multi-line-gap heuristic is exercised in
// isolation from `hasDrawnLine`.
const W = 612;
const pageWidth = () => W;

/** A colon label near the left margin; `wantsBlank` fires on the trailing colon,
 *  so this counts as a "real label" for the topmost-label computation. */
function label(text: string, y: number): LineBox {
  return { text, page: 0, y, x0: 44, x1: 140, height: 10 };
}
/** A colon-less heading near the left margin (no drawn line, no colon). */
function heading(text: string, y: number): LineBox {
  return { text, page: 0, y, x0: 44, x1: 200, height: 10 };
}

function annotate(boxes: LineBox[]): Map<string, boolean> {
  const out = annotateAffordances(boxes, [], pageWidth);
  const m = new Map<string, boolean>();
  boxes.forEach((b, i) => m.set(b.text, out[i].endsWith('______')));
  return m;
}

describe('#324 — multi-line-gap heading affordance (body-gated)', () => {
  it('a body heading with a multi-line gap beneath it becomes ONE control', () => {
    // A colon label at the top establishes the body; CONSENT sits below it with a
    // large empty gap before the next line → the writing area is a control.
    const got = annotate([
      label('PATIENT NAME:', 700),
      heading('CONSENT', 600),
      heading('SPECIMENS:', 540), // colon label — the "next line" 60pt below CONSENT
    ]);
    expect(got.get('CONSENT')).toBe(true);
  });

  it('⚠️ THE BODY GATE: the SAME heading ABOVE the topmost label stays prose (it is a title)', () => {
    // Identical gap, identical shape — only its position relative to the first
    // labelled row differs. Above it → title → prose. This is the mutation that
    // distinguishes the fix from an ungated multi-line-gap rule.
    const asTitle = annotate([
      heading('COLONOSCOPY', 730), // ABOVE the first label, big gap beneath
      label('PATIENT NAME:', 698),
      label('PROCEDURE:', 629),
    ]);
    expect(asTitle.get('COLONOSCOPY')).toBe(false);

    const asBody = annotate([
      label('PATIENT NAME:', 730), // now the label is on top…
      heading('COLONOSCOPY', 698), // …and the identical heading is in the body
      label('PROCEDURE:', 629),
    ]);
    expect(asBody.get('COLONOSCOPY')).toBe(true); // proves the ONLY difference is position
  });

  it('a heading whose fill is its own numbered slots (small gap) stays prose', () => {
    // POSTOPERATIVE FINDINGS with 1./2./3. immediately below: the slots are the
    // fields, the heading is not. Gap to the next line is one line, not many.
    const got = annotate([
      label('PATIENT NAME:', 700),
      heading('POSTOPERATIVE FINDINGS', 516),
      { text: '1.', page: 0, y: 496, x0: 46, x1: 55, height: 10 }, // 20pt below → no multi-line gap
      { text: '2.', page: 0, y: 477, x0: 46, x1: 55, height: 10 },
    ]);
    expect(got.get('POSTOPERATIVE FINDINGS')).toBe(false);
    expect(got.get('1.')).toBe(true); // the numbered slot IS the field (marker branch)
  });

  it('a page with NO labels never over-derives a heading (safe-biased)', () => {
    // firstLabelY is undefined for the page → inBody is false → no gap rule fires.
    const got = annotate([heading('COVER PAGE', 700), heading('SUBTITLE', 600)]);
    expect(got.get('COVER PAGE')).toBe(false);
    expect(got.get('SUBTITLE')).toBe(false);
  });
});

// ── End-to-end: the owner's colonoscopy operative form, the ruling's fixture ──
const FIXTURE = join(
  dirname(fileURLToPath(import.meta.url)),
  '..',
  '..',
  '..',
  'pdf-native',
  '__tests__',
  '__fixtures__',
  'colon-operative-reportlab.pdf',
);

async function annotateFixture(): Promise<Map<string, boolean>> {
  const bytes = new Uint8Array(readFileSync(FIXTURE));
  const proxy = (await getDocumentProxy(bytes.slice())) as never;
  const segments = await extractRuleSegments(proxy).catch(() => []);
  const p = await (proxy as { getPage(n: number): Promise<any> }).getPage(1);
  const content = await p.getTextContent();
  const items: Array<{ str: string; x: number; y: number; height: number; page: number }> = [];
  for (const it of content.items) {
    if (!it.str || !it.str.trim()) continue;
    const t = it.transform;
    items.push({ str: it.str, x: t[4], y: t[5], height: Math.abs(t[3]) || it.height, page: 0 });
  }
  const boxes = groupLineBoxes(items as never);
  const widths = new Map<number, number>();
  widths.set(0, p.getViewport({ scale: 1 }).width);
  const annotated = annotateAffordances(boxes, segments, (pg) => widths.get(pg) ?? 612);
  const m = new Map<string, boolean>();
  boxes.forEach((b, i) => m.set(b.text, annotated[i].endsWith('______')));
  return m;
}

describe("#324 — owner's colonoscopy operative form (the ruling's fixture)", () => {
  it('CONSENT and DESCRIPTION OF PROCEDURE derive controls; titles and slot-headings stay prose', async () => {
    const got = await annotateFixture();

    // The ruling's named targets — multi-line writing areas → controls.
    expect(got.get('CONSENT')).toBe(true);
    expect(got.get('DESCRIPTION OF PROCEDURE')).toBe(true);

    // Titles — a colon-less heading ABOVE the first labelled row stays prose.
    expect(got.get('OPERATIVE NOTE')).toBe(false);
    expect(got.get('COLONOSCOPY')).toBe(false);

    // Slot-headings — their fill is the numbered slots below, so the heading is prose.
    expect(got.get('POSTOPERATIVE FINDINGS')).toBe(false);
    expect(got.get('RECOMMENDATIONS')).toBe(false);

    // The colon labels are still controls (branch (a) unaffected by #324).
    expect(got.get('SPECIMENS:')).toBe(true);
    expect(got.get('COMPLICATIONS:')).toBe(true);
    expect(got.get('BOWEL PREPARATION / BBPS:')).toBe(true);
  });
});
