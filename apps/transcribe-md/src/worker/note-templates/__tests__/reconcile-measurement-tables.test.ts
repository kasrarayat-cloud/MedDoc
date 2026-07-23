// Regression for the prod styled-export bug: asymmetric venous-duplex tables
// that dropped dictated measurements into prose (right SSV proximal-calf 2.8,
// left GSV knee 3.4). The reconciler rebuilds one canonical symmetric row set
// per leg and recovers dropped, prose-documented values; never invents.
import { describe, expect, it } from 'vitest';

import {
  reconcileMeasurementTables,
  extractLegMeasurements,
} from '../reconcile-measurement-tables';

const PROD_NOTE = [
  '## FINDINGS',
  'There is reflux in the superficial system. At the saphenofemoral junction the great saphenous vein measures 6.2 mm with reflux of 3.4 seconds. At the proximal thigh it measures 5.8 mm with reflux of 3.1 seconds. At the knee it measures 4.1 mm with reflux of 1.8 seconds. The small saphenous vein is competent — at the saphenopopliteal junction it measures 3.2 mm with reflux of 0.3 seconds, and at the proximal calf 2.8 mm.',
  '',
  'The great saphenous vein at the saphenofemoral junction measures 4.2 mm with reflux of 0.3 seconds; at the knee it measures 3.4 mm. The small saphenous vein is competent.',
  '',
  '## DIAMETER AND REFLUX TIME — Right Leg',
  '| DIAMETER (mm) | REFLUX TIME (seconds) |',
  '| --- | --- |',
  '| GSV at the SFJ | 6.2 | 3.4 |',
  '| GSV at the Proximal Thigh | 5.8 | 3.1 |',
  '| GSV at the Knee | 4.1 | 1.8 |',
  '| SSV at the SPJ | 3.2 | 0.3 |',
  '',
  '## DIAMETER AND REFLUX TIME — Left Leg',
  '| DIAMETER (mm) | REFLUX TIME (seconds) |',
  '| --- | --- |',
  '| GSV at the SFJ | 4.2 | 0.3 |',
  '| SSV at the Proximal Calf | [not documented] |',
  '',
  '## PROCEDURES / E&M',
].join('\n');

describe('reconcileMeasurementTables', () => {
  const out = reconcileMeasurementTables(PROD_NOTE);

  it('recovers the right-leg SSV proximal-calf 2.8 that was dropped into prose', () => {
    expect(out).toMatch(/SSV at the Proximal Calf \| 2\.8 \|/);
  });

  it('recovers the left-leg GSV knee 3.4 that was dropped into prose', () => {
    expect(out).toMatch(/GSV at the Knee \| 3\.4 \|/);
  });

  it('makes both leg tables the SAME canonical symmetric row set, in order', () => {
    const rightBlock = out.split('— Left Leg')[0];
    const leftBlock = out.split('— Left Leg')[1];
    const rowLabels = (block: string) =>
      (block.match(/^\| ([A-Z][^|]*?) \|/gm) || []).map((m) => m.replace(/^\| | \|$/g, '').trim());
    const r = rowLabels(rightBlock);
    const l = rowLabels(leftBlock);
    expect(r).toEqual(l); // symmetric
    expect(r).toContain('SSV at the SPJ');
    // SSV proximal calf sits right after SSV SPJ, not appended.
    expect(r.indexOf('SSV at the Proximal Calf')).toBe(r.indexOf('SSV at the SPJ') + 1);
  });

  it('keeps existing filled cells (diameter AND reflux) intact', () => {
    expect(out).toMatch(/GSV at the SFJ \| 6\.2 \| 3\.4 \|/);
  });

  it('leaves undictated segments as [not documented] — never invents a value', () => {
    // Left GSV proximal thigh was never dictated → blank both cells.
    expect(out).toMatch(/GSV at the Proximal Thigh \| \[not documented\] \| \[not documented\] \|/);
    expect(out).not.toMatch(/\| 9\.9 \|/);
  });

  it('is a no-op for a note with no measurement table', () => {
    const soap = '## SUBJECTIVE\nx\n\n## ASSESSMENT & PLAN\ny';
    expect(reconcileMeasurementTables(soap)).toBe(soap);
  });

  it('NEVER overwrites a documented cell (units / qualitative) with [not documented] — B2', () => {
    const note = [
      '## FINDINGS', 'right leg only', '',
      '## DIAMETER AND REFLUX TIME — Right Leg',
      '| DIAMETER (mm) | REFLUX TIME (seconds) |',
      '| --- | --- |',
      '| GSV at the SFJ | 6.2 mm | competent |', // unit-bearing + qualitative
      '',
    ].join('\n');
    const out = reconcileMeasurementTables(note);
    expect(out).toMatch(/\| GSV at the SFJ \| 6\.2 mm \| competent \|/);
    // Anchor the leading pipe so "GSV at the SFJ" can't match inside "AAGSV at the SFJ".
    expect(out).not.toMatch(/\| GSV at the SFJ \| \[not documented\]/);
  });

  it('does NOT cross-attribute a value to the wrong leg when prose is unmarked/ambiguous — W1', () => {
    // Left table missing GSV Knee; only the RIGHT leg documented a knee (4.1),
    // the left knee was never dictated. The right value must NOT land in the
    // left cell — content-attribution picks the right paragraph for the right
    // table only; the left knee stays [not documented].
    const note = [
      '## FINDINGS',
      'The great saphenous vein at the saphenofemoral junction measures 6.2 mm with reflux of 3.4 seconds. At the knee it measures 4.1 mm.',
      '',
      'The great saphenous vein at the saphenofemoral junction measures 4.2 mm with reflux of 0.3 seconds. The rest of the left leg is normal.',
      '',
      '## DIAMETER AND REFLUX TIME — Right Leg',
      '| DIAMETER (mm) | REFLUX TIME (seconds) |', '| --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |', '| GSV at the Knee | 4.1 | [not documented] |',
      '',
      '## DIAMETER AND REFLUX TIME — Left Leg',
      '| DIAMETER (mm) | REFLUX TIME (seconds) |', '| --- | --- |',
      '| GSV at the SFJ | 4.2 | 0.3 |',
      '',
    ].join('\n');
    const out = reconcileMeasurementTables(note);
    const left = out.split('— Left Leg')[1];
    // Left GSV Knee was never dictated → stays blank, does NOT borrow right's 4.1.
    expect(left).toMatch(/GSV at the Knee \| \[not documented\] \| \[not documented\] \|/);
    expect(left).not.toMatch(/GSV at the Knee \| 4\.1/);
  });

  it('MIXED marking: never borrows from an explicitly-other-leg paragraph even on a coincident value — W1', () => {
    // The LEFT-marked paragraph shares the coincident value 4.1 with the right
    // table's GSV knee, but is explicitly the other leg — it must NOT be a
    // content-match candidate for the right table's empty SSV cell.
    const note = [
      '## FINDINGS',
      'On the left: the great saphenous vein at the knee measures 4.1 mm; the small saphenous vein at the proximal calf measures 9.9 mm.',
      '',
      'The great saphenous vein at the saphenofemoral junction measures 6.2 mm.',
      '',
      '## DIAMETER AND REFLUX TIME — Right Leg',
      '| DIAMETER (mm) | REFLUX TIME (seconds) |', '| --- | --- |',
      '| GSV at the SFJ | 6.2 | [not documented] |',
      '| GSV at the Knee | 4.1 | [not documented] |',
      '| SSV at the Proximal Calf | [not documented] | [not documented] |',
      '',
    ].join('\n');
    const out = reconcileMeasurementTables(note);
    const right = out.split('## PROCEDURES')[0].split('— Right Leg')[1] ?? out;
    // The left-leg SSV proximal-calf 9.9 must NOT be recovered into the right cell.
    expect(right).toMatch(/SSV at the Proximal Calf \| \[not documented\] \| \[not documented\] \|/);
    expect(out).not.toMatch(/SSV at the Proximal Calf \| 9\.9/);
  });

  it('preserves a stated-normal "—" the model wrote', () => {
    const note = [
      '## FINDINGS', 'right leg only', '',
      '## DIAMETER AND REFLUX TIME — Right Leg',
      '| DIAMETER (mm) | REFLUX TIME (seconds) |',
      '| --- | --- |',
      '| GSV at the SFJ | 6.2 | — |',
      '',
    ].join('\n');
    expect(reconcileMeasurementTables(note)).toMatch(/GSV at the SFJ \| 6\.2 \| — \|/);
  });
});

describe('extractLegMeasurements', () => {
  it('maps vein + segment to canonical row labels via anaphora', () => {
    const m = extractLegMeasurements(
      'The great saphenous vein at the saphenofemoral junction measures 6.2 mm with reflux of 3.4 seconds. At the knee it measures 4.1 mm.',
    );
    expect(m.get('GSV at the SFJ')).toEqual({ diameter: '6.2', reflux: '3.4' });
    expect(m.get('GSV at the Knee')).toEqual({ diameter: '4.1', reflux: null });
  });

  it('distinguishes AAGSV / SSV from GSV and reads diameter-only mentions', () => {
    const m = extractLegMeasurements(
      'The anterior accessory great saphenous vein at the saphenofemoral junction measures 4.6 mm. The small saphenous vein at the proximal calf measures 2.8 mm.',
    );
    expect(m.get('AAGSV at the SFJ')?.diameter).toBe('4.6');
    expect(m.get('SSV at the Proximal Calf')?.diameter).toBe('2.8');
    expect(m.has('GSV at the SFJ')).toBe(false);
  });

  it('captures BOTH measurements in a VALUE-FIRST compound clause — exact prod phrasing', () => {
    // The real model wrote the right-leg SSV as one compound sentence, value
    // before segment: "measuring 3.2 mm at the saphenopopliteal junction … and
    // 2.8 mm at the proximal calf." The "and" precedes a value, not "at the", so
    // the clause never split and the trailing 2.8 was dropped (the prod bug).
    const m = extractLegMeasurements(
      'The small saphenous vein is competent, measuring 3.2 mm at the saphenopopliteal junction with reflux of 0.3 seconds and 2.8 mm at the proximal calf.',
    );
    expect(m.get('SSV at the SPJ')).toEqual({ diameter: '3.2', reflux: '0.3' });
    expect(m.get('SSV at the Proximal Calf')?.diameter).toBe('2.8');
  });

  it('does not over-split "and" that joins a qualifier rather than a measurement', () => {
    // "4.2 mm and is competent" — the "and" precedes "is competent", not a value
    // or "at the", so the SFJ measurement stays whole and the later ";"-clause
    // still yields the knee value.
    const m = extractLegMeasurements(
      'The great saphenous vein at the saphenofemoral junction measures 4.2 mm and is competent with reflux of 0.3 seconds; at the knee it measures 3.4 mm.',
    );
    expect(m.get('GSV at the SFJ')).toEqual({ diameter: '4.2', reflux: '0.3' });
    expect(m.get('GSV at the Knee')?.diameter).toBe('3.4');
  });
});

describe('reconcileMeasurementTables — value-first prod regression', () => {
  // The exact prod shape: model documented right SSV proximal-calf 2.8 only in a
  // value-first compound prose clause and DROPPED the table row; left GSV knee
  // 3.4 only in prose. The reconciler must recover BOTH into their cells and make
  // the two leg tables symmetric.
  const NOTE = [
    '## FINDINGS',
    'Reflux is present in the superficial system. The great saphenous vein at the saphenofemoral junction measures 6.2 mm with reflux of 3.4 seconds. The small saphenous vein is competent, measuring 3.2 mm at the saphenopopliteal junction with reflux of 0.3 seconds and 2.8 mm at the proximal calf.',
    '',
    'The great saphenous vein at the saphenofemoral junction measures 4.2 mm with reflux of 0.3 seconds; at the knee it measures 3.4 mm. The small saphenous vein is competent.',
    '',
    '## DIAMETER AND REFLUX TIME — Right Leg',
    '| DIAMETER (mm) | REFLUX TIME (seconds) |',
    '| --- | --- |',
    '| GSV at the SFJ | 6.2 | 3.4 |',
    '| SSV at the SPJ | 3.2 | 0.3 |',
    '| SSV at the Proximal Calf | [not documented] | [not documented] |',
    '',
    '## DIAMETER AND REFLUX TIME — Left Leg',
    '| DIAMETER (mm) | REFLUX TIME (seconds) |',
    '| --- | --- |',
    '| GSV at the SFJ | 4.2 | 0.3 |',
    '| GSV at the Knee | [not documented] | [not documented] |',
    '',
    '## IMPRESSION',
  ].join('\n');
  const out = reconcileMeasurementTables(NOTE);

  it('recovers the value-first right SSV proximal-calf 2.8 into its cell', () => {
    expect(out).toMatch(/SSV at the Proximal Calf \| 2\.8 \|/);
  });

  it('still recovers the left GSV knee 3.4', () => {
    expect(out).toMatch(/GSV at the Knee \| 3\.4 \|/);
  });

  it('does not cross-attribute: left SSV proximal calf stays undocumented', () => {
    const left = out.split('— Left Leg')[1];
    expect(left).toMatch(/SSV at the Proximal Calf \| \[not documented\] \| \[not documented\] \|/);
  });
});

// ============================================================================
// KUK regression (2026-07-23): left-detailed / right-screening ultrasound.
// Three defects in one visit:
//  1. Both tables emitted only 9 rows (no "GSV at the Knee") — the canon was
//     DERIVED from the union of emitted rows, so a segment the model dropped
//     from BOTH legs vanished and its dictated diameters had nowhere to land.
//  2. Serial diameter-only phrasing "…at the proximal thigh 3.6 mm, and at the
//     knee 3.1 mm" — the comma-separated middle value (3.6) never extracted.
//  3. The right-leg paragraph was SET-ASIDE (in the suggestions lane, not the
//     adopted note); its right GSV-knee 3.0 must NOT be recovered — the
//     reconciler reads the adopted note ONLY.
// ============================================================================
describe('KUK regression — fixed 10-row canon + comma-serial extraction + single source', () => {
  const KUK = [
    '## FINDINGS',
    '',
    '**Left Leg:** There is reflux in the superficial system.  The small saphenous vein is incompetent from the saphenopopliteal junction to the mid calf.  At the saphenopopliteal junction the small saphenous vein measures 5.4 mm with reflux of 2.9 seconds, and at the proximal calf it measures 4.7 mm with reflux of 2.2 seconds.  The great saphenous vein is competent — at the saphenofemoral junction it measures 3.9 mm with reflux of 0.3 seconds, at the proximal thigh 3.6 mm, and at the knee 3.1 mm.  The anterior accessory great saphenous vein at the saphenofemoral junction measures 2.9 mm with no reflux.',
    '',
    '## DIAMETER AND REFLUX TIME — Right Leg',
    '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
    '| --- | --- | --- |',
    '| GSV at the SFJ | 3.8 | 0.2 |',
    '| GSV at the Proximal Thigh | [not documented] | [not documented] |',
    '| GSV Below Knee | [not documented] | [not documented] |',
    '| SSV at the SPJ | 2.6 | — |',
    '| SSV at the Proximal Calf | [not documented] | [not documented] |',
    '| AAGSV at the SFJ | [not documented] | [not documented] |',
    '| AAGSV at the Proximal Thigh | [not documented] | [not documented] |',
    '| PAGSV at the SFJ | [not documented] | [not documented] |',
    '| PAGSV at the Proximal Thigh | [not documented] | [not documented] |',
    '',
    '## DIAMETER AND REFLUX TIME — Left Leg',
    '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
    '| --- | --- | --- |',
    '| GSV at the SFJ | 3.9 | 0.3 |',
    '| GSV at the Proximal Thigh | [not documented] | [not documented] |',
    '| GSV Below Knee | [not documented] | [not documented] |',
    '| SSV at the SPJ | 5.4 | 2.9 |',
    '| SSV at the Proximal Calf | 4.7 | 2.2 |',
    '| AAGSV at the SFJ | 2.9 | [not documented] |',
    '| AAGSV at the Proximal Thigh | [not documented] | [not documented] |',
    '| PAGSV at the SFJ | [not documented] | [not documented] |',
    '| PAGSV at the Proximal Thigh | [not documented] | [not documented] |',
    '',
    '## IMPRESSION',
  ].join('\n');
  const out = reconcileMeasurementTables(KUK);

  const CANON = [
    'GSV at the SFJ', 'GSV at the Proximal Thigh', 'GSV at the Knee', 'GSV Below Knee',
    'SSV at the SPJ', 'SSV at the Proximal Calf', 'AAGSV at the SFJ',
    'AAGSV at the Proximal Thigh', 'PAGSV at the SFJ', 'PAGSV at the Proximal Thigh',
  ];
  const rowLabels = (block: string) =>
    (block.match(/^\| ([A-Z][^|]*?) \|/gm) || [])
      .map((m) => m.replace(/^\| | \|$/g, '').trim())
      .filter((label) => !/^segment$|diameter|reflux/i.test(label)); // drop the header cell

  it('rebuilds BOTH legs to the fixed canonical 10-row set, in fixed order', () => {
    const right = rowLabels(out.split('— Left Leg')[0].split('— Right Leg')[1]);
    const left = rowLabels(out.split('— Left Leg')[1]);
    expect(right).toEqual(CANON);
    expect(left).toEqual(CANON); // 10 = 10, symmetric
  });

  it('recovers the comma-serial left GSV proximal-thigh 3.6 (was prose-only)', () => {
    expect(out.split('— Left Leg')[1]).toMatch(/GSV at the Proximal Thigh \| 3\.6 \|/);
  });

  it('recovers the left GSV knee 3.1 into the now-present knee row', () => {
    expect(out.split('— Left Leg')[1]).toMatch(/GSV at the Knee \| 3\.1 \|/);
  });

  it('SINGLE SOURCE: the set-aside right GSV-knee 3.0 is NOT recovered (not in the adopted note)', () => {
    const right = out.split('— Left Leg')[0];
    expect(right).toMatch(/GSV at the Knee \| \[not documented\] \| \[not documented\] \|/);
    expect(out).not.toMatch(/\| 3\.0 \|/);
  });

  it('preserves the model right-leg table values (3.8/0.2, 2.6) verbatim', () => {
    const right = out.split('— Left Leg')[0];
    expect(right).toMatch(/GSV at the SFJ \| 3\.8 \| 0\.2 \|/);
    expect(right).toMatch(/SSV at the SPJ \| 2\.6 \| — \|/);
  });

  it('never invents — undictated left segments stay [not documented]', () => {
    expect(out.split('— Left Leg')[1]).toMatch(/GSV Below Knee \| \[not documented\] \| \[not documented\] \|/);
  });
});

describe('extractLegMeasurements — comma-serial diameter-only + bold leg label', () => {
  it('captures each measurement in a comma-separated serial list (KUK phrasing)', () => {
    const m = extractLegMeasurements(
      'The great saphenous vein is competent — at the saphenofemoral junction it measures 3.9 mm with reflux of 0.3 seconds, at the proximal thigh 3.6 mm, and at the knee 3.1 mm.',
    );
    expect(m.get('GSV at the SFJ')).toEqual({ diameter: '3.9', reflux: '0.3' });
    expect(m.get('GSV at the Proximal Thigh')?.diameter).toBe('3.6');
    expect(m.get('GSV at the Knee')?.diameter).toBe('3.1');
  });
});

describe('non-venous imaging tables are left untouched (BLOCK fix)', () => {
  it('does NOT inject saphenous rows into an abdominal-aorta table', () => {
    const note = [
      '## FINDINGS', 'The abdominal aorta is normal in caliber.', '',
      '## AORTIC DIAMETERS',
      '| Segment | Diameter (cm) |',
      '| --- | --- |',
      '| Proximal aorta | 2.1 |',
      '| Mid aorta | 1.9 |',
      '| Distal aorta | 1.8 |',
      '',
    ].join('\n');
    const out = reconcileMeasurementTables(note);
    expect(out).toBe(note); // no reflux column, no canonical vein rows → untouched
    expect(out).not.toMatch(/GSV|SSV|AAGSV|PAGSV/);
  });

  it('still reconciles a venous table that sits alongside a non-venous one', () => {
    const note = [
      '## FINDINGS', 'On the left the great saphenous vein at the knee measures 3.4 mm.', '',
      '## AORTIC DIAMETERS',
      '| Segment | Diameter (cm) |', '| --- | --- |', '| Proximal aorta | 2.1 |', '',
      '## DIAMETER AND REFLUX TIME — Left Leg',
      '| DIAMETER (mm) | REFLUX TIME (seconds) |', '| --- | --- |',
      '| GSV at the SFJ | 4.2 | 0.3 |', '',
    ].join('\n');
    const out = reconcileMeasurementTables(note);
    // The aortic block (between its heading and the next ## heading) is untouched.
    const aorticBlock = out.split('## AORTIC DIAMETERS')[1].split('## DIAMETER')[0];
    expect(aorticBlock).toMatch(/Proximal aorta \| 2\.1 \|/);
    expect(aorticBlock).not.toMatch(/GSV|SSV|AAGSV|PAGSV/); // no vein rows injected into the aorta table
    const venous = out.split('— Left Leg')[1];
    expect(venous).toMatch(/GSV at the Knee \| 3\.4 \|/); // venous table reconciled + recovered
  });
});

describe('extractLegMeasurements — segment-anchored, multi-segment & connective prose', () => {
  it('captures a trailing measurement after a non-splitting connective ("tapering to")', () => {
    const m = extractLegMeasurements(
      'The great saphenous vein is competent throughout — at the saphenofemoral junction it measures 3.9 mm with reflux of 0.3 seconds, at the proximal thigh 3.6 mm, and the vein stays patent at the knee where it measures 3.2 mm, tapering to 2.8 mm below the knee.',
    );
    expect(m.get('GSV at the SFJ')).toEqual({ diameter: '3.9', reflux: '0.3' });
    expect(m.get('GSV at the Proximal Thigh')?.diameter).toBe('3.6');
    expect(m.get('GSV at the Knee')?.diameter).toBe('3.2');
    expect(m.get('GSV Below Knee')?.diameter).toBe('2.8');
  });

  it('does NOT mis-assign knee vs below-knee in a "…at the knee, while below the knee…" list', () => {
    const m = extractLegMeasurements(
      'The great saphenous vein is diffusely incompetent. It measures 4.4 mm at the saphenofemoral junction with 3.8 seconds of reflux, at the proximal thigh 3.9 mm, and 3.2 mm at the knee, while below the knee the vein tapers to 2.6 mm.',
    );
    expect(m.get('GSV at the SFJ')).toEqual({ diameter: '4.4', reflux: '3.8' });
    expect(m.get('GSV at the Proximal Thigh')?.diameter).toBe('3.9');
    expect(m.get('GSV at the Knee')?.diameter).toBe('3.2');
    expect(m.get('GSV Below Knee')?.diameter).toBe('2.6');
  });

  it('handles a semicolon serial that switches veins mid-paragraph', () => {
    const m = extractLegMeasurements(
      'The great saphenous vein was insonated in the standing position. At the saphenofemoral junction it measures 6.2 mm with 2.8 seconds of reflux; in the proximal thigh the vein is 5.4 mm and competent; at the knee it measures 4.1 mm with 1.9 seconds of reflux; turning to the small saphenous vein, at the saphenopopliteal junction it is 3.6 mm and at the proximal calf 3.2 mm.',
    );
    expect(m.get('GSV at the SFJ')?.diameter).toBe('6.2');
    expect(m.get('GSV at the Proximal Thigh')?.diameter).toBe('5.4');
    expect(m.get('GSV at the Knee')).toEqual({ diameter: '4.1', reflux: '1.9' });
    expect(m.get('SSV at the SPJ')?.diameter).toBe('3.6');
    expect(m.get('SSV at the Proximal Calf')?.diameter).toBe('3.2');
  });
});
