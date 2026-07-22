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
    expect(out).toMatch(/GSV at the SFJ \| 6\.2 mm \| competent \|/);
    expect(out).not.toMatch(/GSV at the SFJ \| \[not documented\]/);
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
});
