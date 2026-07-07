import { describe, expect, it } from 'vitest';
import {
  detectContextFields,
  applyContextDefaults,
  matchContextField,
} from '../note-template-context';

// A WM_IOV-shaped metadata section: dictatable (side of exam, indications,
// diagnosis) + the 5 context markers + a findings carrier.
const META =
  '{{one of: 250 E. Yale Loop, Suite E, Irvine, CA 92604 | 2572 Atlantic Avenue, Long Beach, CA 90806}}\n' +
  'SIDE OF EXAM: {{one of: Bilateral Detailed | Bilateral Screening}}\n' +
  'REFERRING PHYSICIAN: {{one of: Maged S. Mikhail, MD, RPVI, RVT | Khashayar Sarabi, MD, RPVI}}\n' +
  'ULTRASOUND TECHNOLOGIST: {{one of: Yana Bennett, RVT, RDMS | Beatriz Tena, RVS}}\n' +
  'MACHINE: {{one of: GE Logiq V2, 6-12 MHz Transducer | Mindray M7, L12-4s MHz Transducer}}\n' +
  'LOCATION: {{one of: Irvine, CA | Long Beach, CA}}\n' +
  'DIAGNOSIS: {{one of: Varicose veins of lower extremity with other complications of right lower extremity | Chronic venous hypertension with other complications of left lower extremity}}';
const FINDINGS =
  'The {{one of: great saphenous vein | small saphenous vein}} is refluxing.';

const sections = [
  { key: 'meta', defaultText: META },
  { key: 'findings', defaultText: FINDINGS },
];

describe('detectContextFields', () => {
  it('finds the 5 context fields (incl. label-less address), skips dictatable', () => {
    const found = detectContextFields(sections);
    const keys = found.map((f) => f.key);
    expect(keys).toEqual(['clinicAddress', 'referringPhysician', 'sonographer', 'machine', 'location']);
    expect(found.find((f) => f.key === 'sonographer')!.perVisit).toBe(true);
    expect(found.find((f) => f.key === 'machine')!.options).toContain('GE Logiq V2, 6-12 MHz Transducer');
    // NOT side of exam / diagnosis / findings vein
    expect(keys).not.toContain('sideOfExam');
  });
});

describe('applyContextDefaults', () => {
  it('fills context markers from valid defaults; leaves dictatable markers', () => {
    const out = applyContextDefaults(sections, {
      clinicAddress: '250 E. Yale Loop, Suite E, Irvine, CA 92604',
      referringPhysician: 'Maged S. Mikhail, MD, RPVI, RVT',
      machine: 'GE Logiq V2, 6-12 MHz Transducer',
      location: 'Irvine, CA',
    });
    const meta = out[0].defaultText!;
    // context resolved to fixed text, markers gone
    expect(meta).toContain('REFERRING PHYSICIAN: Maged S. Mikhail, MD, RPVI, RVT');
    expect(meta).toContain('MACHINE: GE Logiq V2, 6-12 MHz Transducer');
    expect(meta).toContain('LOCATION: Irvine, CA');
    expect(meta).toContain('250 E. Yale Loop, Suite E, Irvine, CA 92604');
    // sonographer is per-visit → [not documented]
    expect(meta).toContain('ULTRASOUND TECHNOLOGIST: [not documented]');
    // DICTATABLE markers untouched
    expect(meta).toContain('SIDE OF EXAM: {{one of: Bilateral Detailed');
    expect(meta).toContain('DIAGNOSIS: {{one of:');
    expect(out[1].defaultText).toContain('{{one of: great saphenous vein'); // findings untouched
    // no context marker survives
    expect(meta).not.toContain('REFERRING PHYSICIAN: {{one of:');
    expect(meta).not.toContain('MACHINE: {{one of:');
  });

  it('leaves a context field BLANK when its default is not one of the template options', () => {
    const out = applyContextDefaults(sections, { machine: 'Some Machine Not In The List' });
    expect(out[0].defaultText).toContain('MACHINE: [not documented]');
  });

  it('with no defaults set, ALL context fields resolve to [not documented] (safe, no regression)', () => {
    const out = applyContextDefaults(sections, null);
    const meta = out[0].defaultText!;
    expect(meta).toContain('REFERRING PHYSICIAN: [not documented]');
    expect(meta).toContain('MACHINE: [not documented]');
    expect(meta).toContain('LOCATION: [not documented]');
    // dictatable still markers
    expect(meta).toContain('SIDE OF EXAM: {{one of:');
  });

  it('does not touch sections without markers', () => {
    const plain = [{ key: 'a', defaultText: 'Plain prose, no markers.' }];
    expect(applyContextDefaults(plain, { machine: 'x' })).toEqual(plain);
  });

  it('matchContextField: dictatable labels return null', () => {
    expect(matchContextField('SIDE OF EXAM:', ['Bilateral Detailed'])).toBeNull();
    expect(matchContextField('DIAGNOSIS:', ['Varicose veins'])).toBeNull();
    expect(matchContextField('MACHINE:', ['GE Logiq'])!.key).toBe('machine');
  });
});
