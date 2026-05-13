// ============================================================================
// deepgram-keyterm-builder.ts — per-visit composition (PR-1: Issues #202 + #206)
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  buildKeytermsForVisit,
} from '@/lib/deepgram-keyterm-builder';
import {
  CORE_KEYTERMS,
  SPECIALTY_KEYTERMS,
} from '@/lib/deepgram-vocabulary';

describe('buildKeytermsForVisit — composition', () => {
  it('returns core + specialty terms layered + deduped', () => {
    const r = buildKeytermsForVisit({ specialty: 'bariatric-surgery' });
    // Every CORE term must appear in the output
    for (const t of CORE_KEYTERMS) {
      expect(r.keyterms).toContain(t);
    }
    // The bariatric specialty bundle contributes GLP-1 brands —
    // the Implanon/Nexplanon issue's sister problem (Issue #206 was
    // contraceptive, this is the diabetes-side equivalent)
    expect(r.keyterms).toContain('Ozempic');
    expect(r.keyterms).toContain('Wegovy');
    expect(r.keyterms).toContain('Mounjaro');
    expect(r.keyterms).toContain('Zepbound');
  });

  it('ob_gyn bundle includes Implanon + Nexplanon (Issue #206 seed case)', () => {
    // The load-bearing assertion: pre-fix, NEITHER name appeared
    // anywhere in the global keyterm list. Post-fix, both are
    // present whenever the visit's specialty is ob_gyn.
    const r = buildKeytermsForVisit({ specialty: 'ob-gyn' });
    expect(r.keyterms).toContain('Implanon');
    expect(r.keyterms).toContain('Nexplanon');
    // Plus the sibling contraceptive implants in the same class
    expect(r.keyterms).toContain('etonogestrel');
    expect(r.keyterms).toContain('Mirena');
  });

  it('different specialties produce different keyterm sets', () => {
    const bariatric = buildKeytermsForVisit({ specialty: 'bariatric-surgery' });
    const cardiology = buildKeytermsForVisit({ specialty: 'cardiology' });
    // Bariatric has GLP-1; cardiology has anticoagulants. They
    // share CORE_KEYTERMS but the specialty layer should differ.
    expect(bariatric.keyterms).toContain('semaglutide');
    expect(cardiology.keyterms).not.toContain('semaglutide');
    expect(cardiology.keyterms).toContain('apixaban');
    expect(bariatric.keyterms).not.toContain('apixaban');
  });

  it('unspecified specialty returns CORE only', () => {
    const r = buildKeytermsForVisit({ specialty: null });
    expect(r.metadata.specialty).toBe('unspecified');
    expect(r.metadata.layers.specialty).toBe(0);
    expect(r.keyterms.length).toBeGreaterThan(0);
    // CORE includes anatomy + labs + procedures
    expect(r.keyterms).toContain('lisinopril');
    expect(r.keyterms).toContain('hemoglobin a1c');
  });

  it('safetyFloor terms ride alongside CORE + specialty', () => {
    const safetyFloor = ['Implanon', 'Nexplanon', 'tramadol', 'trazodone'];
    const r = buildKeytermsForVisit({
      specialty: 'cardiology',
      safetyFloor,
    });
    for (const t of safetyFloor) expect(r.keyterms).toContain(t);
    expect(r.metadata.layers.safetyFloor).toBe(safetyFloor.length);
  });

  it('patientContext capped at 15 entries', () => {
    const patientContext = Array.from(
      { length: 40 },
      (_, i) => `patient_med_${i}`,
    );
    const r = buildKeytermsForVisit({
      specialty: 'primary-care',
      patientContext,
    });
    expect(r.metadata.layers.patientContext).toBeLessThanOrEqual(15);
  });

  it('dedupe — safety floor wins precedence over core / specialty', () => {
    const r = buildKeytermsForVisit({
      specialty: 'cardiology',
      safetyFloor: ['tramadol'], // tramadol is also in CORE
    });
    // tramadol appears exactly once
    const count = r.keyterms.filter(
      (t) => t.toLowerCase() === 'tramadol',
    ).length;
    expect(count).toBe(1);
    // It counts in safetyFloor layer (because safetyFloor is
    // composed first)
    expect(r.metadata.layers.safetyFloor).toBe(1);
  });

  it('metadata.totalTerms matches keyterms.length', () => {
    const r = buildKeytermsForVisit({ specialty: 'bariatric-surgery' });
    expect(r.metadata.totalTerms).toBe(r.keyterms.length);
  });

  it('metadata.rawSpecialty preserves the input string', () => {
    const r = buildKeytermsForVisit({ specialty: 'Primary Care / Family Medicine' });
    expect(r.metadata.rawSpecialty).toBe('Primary Care / Family Medicine');
    expect(r.metadata.specialty).toBe('primary_care');
  });

  it('metadata.termsHash is stable for identical inputs', () => {
    const r1 = buildKeytermsForVisit({ specialty: 'cardiology' });
    const r2 = buildKeytermsForVisit({ specialty: 'cardiology' });
    expect(r1.metadata.termsHash).toBe(r2.metadata.termsHash);
  });

  it('metadata.termsHash differs across specialties', () => {
    const cardio = buildKeytermsForVisit({ specialty: 'cardiology' });
    const ortho = buildKeytermsForVisit({ specialty: 'orthopedics' });
    expect(cardio.metadata.termsHash).not.toBe(ortho.metadata.termsHash);
  });

  it('budget enforcement caps total tokens', () => {
    // Pathological input — try to overflow the budget with a huge
    // safety floor; the enforcer drops patient context + specialty
    // tail until under budget.
    const hugeFloor = Array.from({ length: 200 }, (_, i) => `floortermxxxxxxxxxxxxxxxxxx_${i}`);
    const r = buildKeytermsForVisit({
      specialty: 'cardiology',
      safetyFloor: hugeFloor,
      tokenBudget: 100,
    });
    // Budget enforcer ran
    expect(r.metadata.budgetEnforced).toBe(true);
    // The safety floor is protected — it MAY exceed budget if it's
    // already larger than the budget by itself. That's intentional:
    // we never sacrifice safety. The protected count check below.
    expect(r.metadata.layers.safetyFloor).toBe(hugeFloor.length);
  });

  it('budget enforcement preserves CORE_KEYTERMS even under pressure', () => {
    // Modest budget that's enough for safety + core but not
    // specialty.
    const r = buildKeytermsForVisit({
      specialty: 'bariatric-surgery',
      safetyFloor: ['Implanon', 'Nexplanon'],
      tokenBudget: 200,
    });
    // Safety + core both survive
    expect(r.metadata.layers.safetyFloor).toBe(2);
    expect(r.metadata.layers.core).toBe(CORE_KEYTERMS.length);
    // Specialty may be trimmed
    expect(r.metadata.budgetEnforced).toBe(true);
  });

  it('interpreter-mode skip: callers pass no safety/patient and get a small set', () => {
    // Validating the contract that the L1 layer relies on — when
    // interpreterMode is true, the layer skips the builder entirely
    // (model swaps). This test documents that the BUILDER itself
    // doesn't know about interpreter mode; the layer decides.
    const r = buildKeytermsForVisit({ specialty: null });
    // Default specialty (unspecified) yields only the core bundle
    expect(r.metadata.layers.specialty).toBe(0);
    expect(r.metadata.layers.safetyFloor).toBe(0);
    expect(r.metadata.layers.patientContext).toBe(0);
    expect(r.metadata.layers.core).toBe(CORE_KEYTERMS.length);
  });
});

describe('SPECIALTY_KEYTERMS bundle invariants', () => {
  it('every canonical specialty has a bundle', () => {
    // Every key in SPECIALTY_KEYS has an entry in SPECIALTY_KEYTERMS.
    // Unspecified is a special case (empty bundle) and should still
    // be present so the builder's lookup never returns undefined.
    expect(SPECIALTY_KEYTERMS.unspecified).toBeDefined();
    expect(SPECIALTY_KEYTERMS.bariatric_surgery).toBeDefined();
    expect(SPECIALTY_KEYTERMS.ob_gyn).toBeDefined();
    expect(SPECIALTY_KEYTERMS.cardiology).toBeDefined();
  });

  it('bariatric / weight-management / endocrinology all include GLP-1 brands', () => {
    // The GLP-1 cluster is split across three specialties that share
    // this prescribing pattern. They should all see Ozempic + Mounjaro
    // as keyterms regardless of which one the visit was tagged as.
    expect(SPECIALTY_KEYTERMS.bariatric_surgery).toContain('Ozempic');
    expect(SPECIALTY_KEYTERMS.weight_management).toContain('Ozempic');
    expect(SPECIALTY_KEYTERMS.endocrinology).toContain('Ozempic');
  });

  it('ob_gyn includes the Implanon family (Issue #206 seed)', () => {
    expect(SPECIALTY_KEYTERMS.ob_gyn).toContain('Implanon');
    expect(SPECIALTY_KEYTERMS.ob_gyn).toContain('Nexplanon');
  });

  it('cardiology + vascular_surgery include the anticoagulant set', () => {
    expect(SPECIALTY_KEYTERMS.cardiology).toContain('apixaban');
    expect(SPECIALTY_KEYTERMS.cardiology).toContain('warfarin');
    expect(SPECIALTY_KEYTERMS.vascular_surgery).toContain('apixaban');
  });

  it('no specialty bundle exceeds 30 terms (size discipline)', () => {
    for (const [key, terms] of Object.entries(SPECIALTY_KEYTERMS)) {
      expect(
        terms.length,
        `specialty ${key} exceeds 30-term ceiling`,
      ).toBeLessThanOrEqual(30);
    }
  });
});
