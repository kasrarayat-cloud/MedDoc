// ============================================================================
// Vascular Surgery Rx safety table — antiplatelet / anticoagulant /
// claudication agents + iodinated contrast media. This cohort introduces
// two classes of safety guard the validator now enforces:
//
//   1. CV-context contraindications — prasugrel + vorapaxar are CONTRA-
//      INDICATED in any patient with prior TIA / stroke. Both entries
//      carry the literal contraindication string so a Rx draft against
//      a documented stroke history triggers RX_CONTRAINDICATION_MATCH.
//
//   2. Renal / thyroid screening — iohexol + iodixanol require eGFR
//      checks and untreated hyperthyroidism exclusion. The Rx rail
//      surfaces "Verify eGFR" warnings on every contrast draft for
//      patients without documented kidney function.
//
// Cilostazol's heart-failure contraindication is the third load-bearing
// rule (boxed warning, mortality signal from milrinone HF trials carries
// over to all PDE-III inhibitors).
// ============================================================================

import { describe, expect, it } from 'vitest';

import { getDoseRange } from '../data/dose-ranges';
import { isValidCpt as isValidCptImport } from '../data/cpt-allowlist';

describe('Vascular Surgery dose-range entries', () => {
  it.each([
    'aspirin',
    'prasugrel',
    'ticagrelor',
    'rivaroxaban',
    'edoxaban',
    'dabigatran',
    'cilostazol',
    'pentoxifylline',
    'vorapaxar',
    'iohexol',
    'iodixanol',
  ])('%s is in the catalog', (drug) => {
    expect(getDoseRange(drug)).toBeTruthy();
  });

  it('aspirin caps at 4 g/day with reye + bleeding contraindications', () => {
    const entry = getDoseRange('aspirin');
    expect(entry?.adultMaxMgPerDay).toBe(4000);
    const c = entry?.contraindications ?? [];
    expect(c.some((x) => /reye|viral illness/i.test(x))).toBe(true);
    expect(c.some((x) => /gi bleed/i.test(x))).toBe(true);
    expect(getDoseRange('asa')?.drug).toBe('aspirin');
    expect(getDoseRange('ecotrin')?.drug).toBe('aspirin');
  });

  it('prasugrel is contraindicated in prior TIA / stroke (TRITON-TIMI-38 signal)', () => {
    const entry = getDoseRange('prasugrel');
    expect(entry?.adultMaxMgPerDay).toBe(10);
    expect(
      entry?.contraindications?.some((x) => /history of tia or stroke/i.test(x)),
    ).toBe(true);
    expect(getDoseRange('effient')?.drug).toBe('prasugrel');
  });

  it('vorapaxar is contraindicated in prior TIA / stroke / ICH', () => {
    const entry = getDoseRange('vorapaxar');
    expect(entry?.adultMaxMgPerDay).toBe(2.5);
    const c = entry?.contraindications ?? [];
    expect(c.some((x) => /history of stroke or tia/i.test(x))).toBe(true);
    expect(c.some((x) => /intracranial hemorrhage/i.test(x))).toBe(true);
  });

  it('ticagrelor caps at 180 mg/day with brand alias', () => {
    expect(getDoseRange('ticagrelor')?.adultMaxMgPerDay).toBe(180);
    expect(getDoseRange('brilinta')?.drug).toBe('ticagrelor');
  });

  it('DOACs resolve with brand aliases + carry renal contraindications', () => {
    expect(getDoseRange('xarelto')?.drug).toBe('rivaroxaban');
    expect(getDoseRange('savaysa')?.drug).toBe('edoxaban');
    expect(getDoseRange('pradaxa')?.drug).toBe('dabigatran');
    for (const d of ['rivaroxaban', 'edoxaban', 'dabigatran']) {
      const entry = getDoseRange(d);
      expect(
        entry?.contraindications?.some((x) =>
          /creatinine clearance|renal impairment/i.test(x),
        ),
        d,
      ).toBe(true);
    }
  });

  it('dabigatran is contraindicated in mechanical heart valve (RE-ALIGN halt)', () => {
    const c = getDoseRange('dabigatran')?.contraindications ?? [];
    expect(c.some((x) => /mechanical heart valve/i.test(x))).toBe(true);
  });

  it('cilostazol carries the CHF boxed-warning contraindication', () => {
    const entry = getDoseRange('cilostazol');
    expect(entry?.adultMaxMgPerDay).toBe(200);
    const c = entry?.contraindications ?? [];
    expect(c.some((x) => /heart failure|congestive heart failure/i.test(x))).toBe(true);
    expect(entry?.notes).toMatch(/boxed warning|PDE-3|phosphodiesterase-3/i);
    expect(getDoseRange('pletal')?.drug).toBe('cilostazol');
  });

  it('pentoxifylline is the fallback for claudication when cilostazol contraindicated', () => {
    const entry = getDoseRange('pentoxifylline');
    expect(entry?.adultMaxMgPerDay).toBe(1200);
    expect(getDoseRange('trental')?.drug).toBe('pentoxifylline');
  });

  it('iodinated contrast agents flagged complexDosing + carry eGFR contraindications', () => {
    for (const d of ['iohexol', 'iodixanol']) {
      const entry = getDoseRange(d);
      expect(entry?.complexDosing, d).toBe(true);
      expect(entry?.adultMaxMgPerDay, d).toBeUndefined();
      const c = entry?.contraindications ?? [];
      expect(c.some((x) => /creatinine clearance|renal impairment/i.test(x)), d).toBe(true);
      expect(c.some((x) => /iodine contrast allergy/i.test(x)), d).toBe(true);
    }
    expect(getDoseRange('omnipaque')?.drug).toBe('iohexol');
    expect(getDoseRange('visipaque')?.drug).toBe('iodixanol');
  });

  it('every vascular entry carries operator notes (visibility on Rx rail)', () => {
    for (const d of [
      'aspirin',
      'prasugrel',
      'ticagrelor',
      'rivaroxaban',
      'edoxaban',
      'dabigatran',
      'cilostazol',
      'pentoxifylline',
      'vorapaxar',
      'iohexol',
      'iodixanol',
    ]) {
      expect(getDoseRange(d)?.notes, `${d} notes`).toBeTruthy();
    }
  });

  it('pre-existing antiplatelet / statin / DOAC entries still resolve (smoke check)', () => {
    // Sanity that the vascular batch didn't accidentally clobber an
    // existing row. clopidogrel was already present (M5); warfarin +
    // apixaban + atorvastatin + rosuvastatin from Round 3 PR-D.
    expect(getDoseRange('clopidogrel')).toBeTruthy();
    expect(getDoseRange('warfarin')).toBeTruthy();
    expect(getDoseRange('apixaban')).toBeTruthy();
    expect(getDoseRange('atorvastatin')).toBeTruthy();
    expect(getDoseRange('rosuvastatin')).toBeTruthy();
  });
});

describe('CPT allowlist — vascular procedure presence (regression guards)', () => {
  // Routed through this test file because vascular procedure-code coverage
  // is the most likely surface to silently drift if a future allowlist
  // refactor batches things by alphabetical CPT and dropped a row. The
  // L7b validator would silently emit `CODING_COACH_REJECTED_INVALID_CPT`
  // and the SOAP rail would show no CPT — the same failure mode as the
  // K76.0 / G47.33 drop the L7a auditor (PR #217) caught.
  const isValidCpt = isValidCptImport;

  it.each([
    // Anchor codes from each block — one per category to detect a
    // category-wide drop without enumerating every code.
    ['35301', 'CEA'],
    ['34701', 'EVAR infrarenal'],
    ['34705', 'EVAR aorto-uni-iliac'],
    ['33880', 'TEVAR thoracic'],
    ['37224', 'fem-pop angioplasty'],
    ['37226', 'fem-pop stent'],
    ['37215', 'carotid stent + EPD'],
    ['35556', 'fem-pop vein bypass'],
    ['35654', 'fem-fem cross bypass'],
    ['35601', 'ax-fem bypass'],
    ['36818', 'AV fistula upper-arm cephalic transposition'],
    ['36821', 'AV fistula direct (Cimino)'],
    ['36830', 'AV graft (nonautogenous PTFE)'],
    ['36901', 'fistulogram'],
    ['36475', 'endovenous ablation RFA, first vein'],
    ['36478', 'endovenous ablation laser, first vein'],
    ['36465', 'foam sclerosant injection'],
    ['37761', 'open ligation of perforator veins'],
    ['37722', 'open stripping of greater saphenous'],
    ['93923', 'bilateral noninvasive physiologic studies'],
    ['93970', 'duplex extremity veins, complete bilateral'],
    ['93880', 'duplex extracranial arteries, complete bilateral'],
    ['99221', 'initial hospital care'],
    ['99232', 'subsequent hospital care'],
    ['99239', 'hospital discharge > 30 min'],
  ])('CPT %s (%s) is in the allowlist', (code) => {
    expect(isValidCpt(code)).toBe(true);
  });

  it('legacy codes from prior batches still resolve (E&M + vaccines + ortho)', () => {
    // Same anti-drift smoke check as the dose-ranges block above.
    expect(isValidCpt('99213')).toBe(true);
    expect(isValidCpt('99214')).toBe(true);
    expect(isValidCpt('20610')).toBe(true);  // arthrocentesis major joint
    expect(isValidCpt('43644')).toBe(true);  // bariatric, PR #219
  });

  it('a clearly-bogus CPT still rejects (validator floor still active)', () => {
    expect(isValidCpt('00000')).toBe(false);
    expect(isValidCpt('99999')).toBe(false);
    expect(isValidCpt('Z99.99')).toBe(false);
  });
});
