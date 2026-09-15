// ============================================================================
// #324 — a BOLD HEADING FOLLOWED BY AN EMPTY MULTI-LINE GAP derives ONE
// multi-line control (CONSENT, DESCRIPTION OF PROCEDURE); a heading with no gap
// stays prose (owner ruling, 2026-09-15).
//
// "Bold" is approximated structurally — unpdf's text layer carries no font
// weight — so the fill signal is THREE robust conditions, each hardened against
// an arm an adversarial pass broke on the first (topmost-label) attempt:
//   1 · IN THE BODY by DEPTH (>= MIN_ROWS_ABOVE rows above) — a title stays
//       shallow even beneath a letterhead colon-label; the old MAX-label gate was
//       defeated BOTH ways (top letterhead minted the title; bottom-only labels
//       dropped CONSENT).
//   2 · NOT a slot-heading — the next line is not a numbered/bulleted MARKER
//       (POSTOPERATIVE FINDINGS / RECOMMENDATIONS fill their 1./2./3. slots).
//   3 · a MULTI-LINE gap measured against the page MEDIAN line height, never the
//       heading's own font size (which a compact heading otherwise shrank).
// ============================================================================
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { getDocumentProxy } from 'unpdf';

import { annotateAffordances, groupLineBoxes, type LineBox } from '../pdf-to-prose-docx';
import { extractRuleSegments } from '../pdf-geometry';

const W = 612;
const pageWidth = () => W;

function label(text: string, y: number, x0 = 44, x1 = 140): LineBox {
  return { text, page: 0, y, x0, x1, height: 10 };
}
function heading(text: string, y: number, height = 12): LineBox {
  return { text, page: 0, y, x0: 44, x1: 200, height };
}
/** A demographic block of colon labels descending from `topY`, one per 20pt row —
 *  the ordinary top-of-form strip that puts a section heading deep in the body. */
function demographicBlock(topY: number, rows: number): LineBox[] {
  return Array.from({ length: rows }, (_, i) => label(`FIELD ${i}:`, topY - i * 20));
}

function annotate(boxes: LineBox[]): Map<string, boolean> {
  const out = annotateAffordances(boxes, [], pageWidth);
  const m = new Map<string, boolean>();
  boxes.forEach((b, i) => m.set(b.text, out[i].endsWith('______')));
  return m;
}

describe('#324 — multi-line-gap heading affordance (depth-gated, slot-aware)', () => {
  it('a body heading (deep) with a multi-line writing gap becomes ONE control', () => {
    // Six demographic rows put CONSENT well into the body; a 60pt empty gap to the
    // next heading is the writing area.
    const got = annotate([
      ...demographicBlock(700, 6), // rows at 700..600
      heading('CONSENT', 560),
      heading('DESCRIPTION OF PROCEDURE', 480), // 80pt gap below CONSENT
      heading('SIGNATURE', 400),
    ]);
    expect(got.get('CONSENT')).toBe(true);
    expect(got.get('DESCRIPTION OF PROCEDURE')).toBe(true);
  });

  it('⚠️ TITLE ZONE: a title beneath a top-of-page letterhead colon-label stays prose', () => {
    // Adversarial arm [2]/[5]: a top demographics strip (Patient:/Date:) sits ABOVE
    // the title, which defeated the old topmost-label gate. Depth catches it: the
    // title has only one row above it.
    const got = annotate([
      label('Patient:', 760, 60, 110),
      label('Date:', 760, 400, 440),
      heading('COLONOSCOPY REPORT', 730, 14), // colon-less title, one row above
      label('Indication:', 650, 60, 140),
    ]);
    expect(got.get('COLONOSCOPY REPORT')).toBe(false);
  });

  it('⚠️ DEPTH is the ONLY difference: the same heading deep in the body IS a control', () => {
    const got = annotate([
      ...demographicBlock(760, 6), // rows 760..660
      heading('COLONOSCOPY REPORT', 620, 14),
      heading('NEXT SECTION', 540), // 80pt writing gap below
      heading('SIGNATURE', 460),
    ]);
    expect(got.get('COLONOSCOPY REPORT')).toBe(true);
  });

  it('⚠️ SLOT-HEADING: a heading whose next line is a numbered MARKER stays prose', () => {
    // Adversarial arm [4]: POSTOPERATIVE FINDINGS with a COMPACT font (height 7)
    // over-derived under a height-based threshold. Two guards now hold it prose:
    // its fill is the 1./2./3. slots (next is a marker), and the gap is measured
    // against the page median height, not the heading's own.
    const got = annotate([
      ...demographicBlock(760, 6),
      heading('POSTOPERATIVE FINDINGS', 600, 7), // compact heading, deep in body
      { text: '1.', page: 0, y: 580, x0: 46, x1: 55, height: 10 }, // marker slot below
      { text: '2.', page: 0, y: 560, x0: 46, x1: 55, height: 10 },
      { text: '3.', page: 0, y: 540, x0: 46, x1: 55, height: 10 },
    ]);
    expect(got.get('POSTOPERATIVE FINDINGS')).toBe(false);
    expect(got.get('1.')).toBe(true); // the numbered slot itself IS the field
  });

  it('a shallow title page never over-derives (few rows above, no labels)', () => {
    const got = annotate([heading('OPERATIVE NOTE', 740, 16), heading('COLONOSCOPY', 715, 14)]);
    expect(got.get('OPERATIVE NOTE')).toBe(false);
    expect(got.get('COLONOSCOPY')).toBe(false);
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

    // Titles — colon-less headings in the shallow top zone stay prose.
    expect(got.get('OPERATIVE NOTE')).toBe(false);
    expect(got.get('COLONOSCOPY')).toBe(false);

    // Slot-headings — their fill is the numbered slots below (next is a marker).
    expect(got.get('POSTOPERATIVE FINDINGS')).toBe(false);
    expect(got.get('RECOMMENDATIONS')).toBe(false);

    // The colon labels are still controls (branch (a), unaffected by #324).
    expect(got.get('SPECIMENS:')).toBe(true);
    expect(got.get('COMPLICATIONS:')).toBe(true);
    expect(got.get('BOWEL PREPARATION / BBPS:')).toBe(true);
  });
});
