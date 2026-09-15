// ============================================================================
// S2-4 — re-derive anchors FROM the certified twin's fields, on the owner's
// colon form (ruling #322). The 21 twin fields (labels + displayOrder captured
// from the compiled colon twin in prod) must each get an anchor on the doctor's
// original page: 15 by label, 6 numbered "Fill-in" slots by marker order.
// ============================================================================
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';
import { getDocumentProxy } from 'unpdf';

import { deriveTwinAnchors, type TwinAnchorField } from '../twin-anchor-derivation';

const FIXTURE = join(
  dirname(fileURLToPath(import.meta.url)),
  '__fixtures__',
  'colon-operative-reportlab.pdf',
);

// The owner's colon compiled twin — 21 narrative_text fields, label + displayOrder
// as stored in template_twin_field_definitions (read-only, 2026-09-14).
const COLON_TWIN_FIELDS: TwinAnchorField[] = [
  { fieldId: 'ttf_000000000000000000000002', label: 'PATIENT NAME', displayOrder: 2 },
  { fieldId: 'ttf_000000000000000000000003', label: 'PATIENT DOB', displayOrder: 3 },
  { fieldId: 'ttf_000000000000000000000004', label: 'PATIENT ID #', displayOrder: 4 },
  { fieldId: 'ttf_000000000000000000000005', label: 'DATE OF PROCEDURE', displayOrder: 5 },
  { fieldId: 'ttf_000000000000000000000006', label: 'SURGEON / ENDOSCOPIST', displayOrder: 6 },
  { fieldId: 'ttf_000000000000000000000007', label: 'PROCEDURE', displayOrder: 7 },
  { fieldId: 'ttf_000000000000000000000008', label: 'ANESTHESIA', displayOrder: 8 },
  { fieldId: 'ttf_000000000000000000000009', label: 'BOWEL PREPARATION / BBPS', displayOrder: 9 },
  { fieldId: 'ttf_00000000000000000000000a', label: 'EXTENT OF EXAMINATION', displayOrder: 10 },
  { fieldId: 'ttf_00000000000000000000000b', label: 'Fill-in', displayOrder: 13 },
  { fieldId: 'ttf_00000000000000000000000c', label: 'Fill-in', displayOrder: 14 },
  { fieldId: 'ttf_00000000000000000000000d', label: 'Fill-in', displayOrder: 15 },
  { fieldId: 'ttf_00000000000000000000000e', label: 'SPECIMENS', displayOrder: 18 },
  { fieldId: 'ttf_00000000000000000000000f', label: 'ESTIMATED BLOOD LOSS', displayOrder: 19 },
  { fieldId: 'ttf_000000000000000000000010', label: 'COMPLICATIONS', displayOrder: 20 },
  { fieldId: 'ttf_000000000000000000000011', label: 'Fill-in', displayOrder: 22 },
  { fieldId: 'ttf_000000000000000000000012', label: 'Fill-in', displayOrder: 23 },
  { fieldId: 'ttf_000000000000000000000013', label: 'Fill-in', displayOrder: 24 },
  { fieldId: 'ttf_000000000000000000000014', label: 'Electronically signed by', displayOrder: 25 },
  { fieldId: 'ttf_000000000000000000000015', label: 'DD (dictated)', displayOrder: 26 },
  { fieldId: 'ttf_000000000000000000000016', label: 'DT (transcribed)', displayOrder: 27 },
];

async function proxy() {
  return getDocumentProxy(new Uint8Array(readFileSync(FIXTURE)));
}

describe('deriveTwinAnchors — the colon form, from its own twin fields', () => {
  it('derives an anchor for every twin field (keyed by fieldId), none unlocatable', async () => {
    const { anchors, unlocatable } = await deriveTwinAnchors((await proxy()) as never, COLON_TWIN_FIELDS);
    // Every field placed on the doctor's page — the whole point of #322.
    expect(unlocatable).toEqual([]);
    expect(anchors).toHaveLength(COLON_TWIN_FIELDS.length);
    // Keyed by fieldId, so the value bridge is 1:1.
    expect(new Set(anchors.map((a) => a.key))).toEqual(new Set(COLON_TWIN_FIELDS.map((f) => f.fieldId)));
  });

  it('places the 6 numbered "Fill-in" slots at distinct marker positions in reading order', async () => {
    const { anchors } = await deriveTwinAnchors((await proxy()) as never, COLON_TWIN_FIELDS);
    const slotIds = COLON_TWIN_FIELDS.filter((f) => f.label === 'Fill-in').map((f) => f.fieldId);
    const slotAnchors = slotIds.map((id) => anchors.find((a) => a.key === id)!);
    expect(slotAnchors.every(Boolean)).toBe(true);
    // Distinct y positions (6 real slots, not all collapsed onto one marker).
    const ys = slotAnchors.map((a) => `${a.page}:${Math.round(a.yTop)}`);
    expect(new Set(ys).size).toBe(6);
    // Reading order: the first three (displayOrder 13-15) sit ABOVE the last
    // three (22-24) on the page (higher y), matching the twin's field order.
    const firstGroupMinY = Math.min(...slotAnchors.slice(0, 3).map((a) => a.yTop));
    const secondGroupMaxY = Math.max(...slotAnchors.slice(3).map((a) => a.yTop));
    expect(firstGroupMinY).toBeGreaterThan(secondGroupMaxY);
  });

  it('a labelled field absent from the page is UNLOCATABLE, not misplaced', async () => {
    const withGhost: TwinAnchorField[] = [
      ...COLON_TWIN_FIELDS,
      { fieldId: 'ttf_ffffffffffffffffffffffff', label: 'NONEXISTENT LABEL XYZ', displayOrder: 99 },
    ];
    const { anchors, unlocatable } = await deriveTwinAnchors((await proxy()) as never, withGhost);
    expect(unlocatable).toContain('ttf_ffffffffffffffffffffffff');
    expect(anchors.find((a) => a.key === 'ttf_ffffffffffffffffffffffff')).toBeUndefined();
  });

  it('a surplus Fill-in with no marker is UNLOCATABLE (never zipped onto an unrelated marker)', async () => {
    const withExtraSlot: TwinAnchorField[] = [
      ...COLON_TWIN_FIELDS,
      { fieldId: 'ttf_eeeeeeeeeeeeeeeeeeeeeeee', label: 'Fill-in', displayOrder: 30 },
    ];
    const { unlocatable } = await deriveTwinAnchors((await proxy()) as never, withExtraSlot);
    // 7 Fill-in fields, only 6 markers → the 7th (last by order) is unlocatable.
    expect(unlocatable).toContain('ttf_eeeeeeeeeeeeeeeeeeeeeeee');
  });
});

// ── A synthetic proxy: positioned text items, one page. ──────────────────────
function fakeProxy(items: Array<{ str: string; x: number; y: number; h?: number }>) {
  return {
    numPages: 1,
    async getPage() {
      return {
        getViewport: () => ({ width: 612, height: 792 }),
        async getTextContent() {
          return {
            items: items.map((it) => ({
              str: it.str,
              transform: [it.h ?? 10, 0, 0, it.h ?? 10, it.x, it.y],
              width: it.str.length * (it.h ?? 10) * 0.5,
              height: it.h ?? 10,
            })),
          };
        },
      };
    },
  };
}

describe('deriveTwinAnchors — adversarial regressions (2026-09-15)', () => {
  it('a LABELLED numbered item ("1. History:") is NOT mistaken for a bare Fill-in slot', async () => {
    // The '1.' is a separate text token (as ReportLab emits it), but on the
    // reconstructed LINE it reads "1. History:" — a labelled item, not a marker.
    // Two REAL bare slots ("3."/"4.") follow. The two Fill-in fields must land on
    // the bare slots, never on the Chief Complaint / History rows.
    const px = fakeProxy([
      { str: '1.', x: 60, y: 700 }, { str: 'Chief', x: 80, y: 700 }, { str: 'Complaint:', x: 120, y: 700 },
      { str: '2.', x: 60, y: 680 }, { str: 'History:', x: 80, y: 680 },
      { str: 'FINDINGS', x: 60, y: 640 },
      { str: '3.', x: 60, y: 610 },
      { str: '4.', x: 60, y: 590 },
    ]);
    const fields: TwinAnchorField[] = [
      { fieldId: 'ttf_00000000000000000000aaaa', label: 'Chief Complaint', displayOrder: 1 },
      { fieldId: 'ttf_00000000000000000000bbbb', label: 'History', displayOrder: 2 },
      { fieldId: 'ttf_00000000000000000000cccc', label: 'Fill-in', displayOrder: 4 },
      { fieldId: 'ttf_00000000000000000000dddd', label: 'Fill-in', displayOrder: 5 },
    ];
    const { anchors, unlocatable } = await deriveTwinAnchors(px as never, fields);
    expect(unlocatable).toEqual([]);
    const slot1 = anchors.find((a) => a.key === 'ttf_00000000000000000000cccc')!;
    const slot2 = anchors.find((a) => a.key === 'ttf_00000000000000000000dddd')!;
    // The slots land on the bare markers at y=610 / 590, NOT the labelled rows.
    expect(Math.round(slot1.yTop)).toBe(610);
    expect(Math.round(slot2.yTop)).toBe(590);
  });

  it('two twin fields with the SAME label are UNLOCATABLE (no first-match overdraw)', async () => {
    const px = fakeProxy([
      { str: 'DOSE:', x: 60, y: 700 },
      { str: 'DOSE:', x: 60, y: 680 },
    ]);
    const fields: TwinAnchorField[] = [
      { fieldId: 'ttf_00000000000000000000e111', label: 'DOSE', displayOrder: 1 },
      { fieldId: 'ttf_00000000000000000000e222', label: 'DOSE', displayOrder: 2 },
    ];
    const { anchors, unlocatable } = await deriveTwinAnchors(px as never, fields);
    // Neither is placed (ambiguous position) → both fall back, no overdraw.
    expect(anchors).toHaveLength(0);
    expect(unlocatable.sort()).toEqual(['ttf_00000000000000000000e111', 'ttf_00000000000000000000e222']);
  });
});
