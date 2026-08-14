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
import { normalizeSpecialty, SPECIALTY_KEYS } from '@/lib/specialty-keys';
import { SPECIALTIES } from '@meddoc/shared/specialties';

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
    // CORE is anatomy + labs + procedures + common diagnoses; meds
    // were removed from CORE in PR-2 (the safety floor + per-specialty
    // bundles cover medication vocabulary) — see CORE_KEYTERMS doc
    // block in deepgram-vocabulary.ts.
    expect(r.keyterms).toContain('hemoglobin a1c');
    expect(r.keyterms).toContain('auscultation');
    expect(r.keyterms).toContain('hypertension');
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
    // ⚠ THIS TEST USED TO NAME FOUR KEYS BY HAND (unspecified,
    // bariatric_surgery, ob_gyn, cardiology) while its own comment
    // claimed "every key in SPECIALTY_KEYS". Fifteen bundles existed;
    // four were checked. A key added without a bundle did not redden
    // it — which is the exact half-ship this test's title promises to
    // prevent. It now ENUMERATES. (2026-08-14, GI onboarding.)
    expect(SPECIALTY_KEYS.length).toBeGreaterThan(4); // non-vacuity
    for (const k of SPECIALTY_KEYS) {
      expect(
        SPECIALTY_KEYTERMS[k],
        `SPECIALTY_KEYS has '${k}' but SPECIALTY_KEYTERMS has no bundle for it`,
      ).toBeDefined();
    }
  });

  // ── THE CROSS-CATALOG GATE ────────────────────────────────────────────
  // Neither of the two vocabulary gates compared this module to the
  // PRODUCT catalog in packages/shared. Both watched the vocabulary
  // module's internal consistency, so a specialty the product offers but
  // the vocabulary has never heard of was invisible to both — the
  // watched-set failure. `ultrasound` is exactly that: a shipped,
  // flag-ON catalog row with no SPECIALTY_KEYS entry, so every one of
  // its production visits transcribes with ZERO specialty vocabulary,
  // silently, because SPECIALTY_KEYTERMS.unspecified EXISTS and is EMPTY.
  //
  // A specialty may be exempt, but only BY NAME and WITH A REASON.
  const NO_BUNDLE_EXPECTED: Record<string, string> = {
    unspecified:
      'the "profile not set yet" sentinel, not a clinical category — an ' +
      'empty bundle is correct and the builder relies on it being present',
    ultrasound:
      'IMAGING-REPORT specialty with no vocabulary bundle as of 2026-08-14. ' +
      'This is a KNOWN GAP, not a decision that no bundle is wanted: all ' +
      'production ultrasound visits transcribe with no specialty keyterms. ' +
      'Adding one changes L1 keyterms for live visits, so it carries its own ' +
      'proof obligation and is tracked as its own item. REMOVE THIS ENTRY ' +
      'when that bundle lands — the arm below fails if it is left here.',
  };

  it('every product-catalog specialty resolves to a NON-EMPTY bundle (or is a named exemption)', () => {
    expect(SPECIALTIES.length).toBeGreaterThan(1); // non-vacuity
    const unexplained: string[] = [];
    for (const spec of SPECIALTIES) {
      if (spec.id in NO_BUNDLE_EXPECTED) continue;
      const terms = SPECIALTY_KEYTERMS[normalizeSpecialty(spec.id)] ?? [];
      if (terms.length === 0) unexplained.push(spec.id);
    }
    expect(
      unexplained,
      `catalog specialties with no vocabulary: ${unexplained.join(', ')} — ` +
        'add a bundle, or add a named entry to NO_BUNDLE_EXPECTED saying why',
    ).toEqual([]);
  });

  it('every exemption is still NECESSARY (an exemption that gained a bundle must be removed)', () => {
    // The anti-stale arm. An exclusion list goes wrong silently in the
    // direction that REMOVES coverage: once a bundle lands, the exemption
    // keeps the specialty out of the gate forever. So a stale exemption
    // is itself a failure.
    const stale: string[] = [];
    for (const id of Object.keys(NO_BUNDLE_EXPECTED)) {
      if (id === 'unspecified') continue; // legitimately empty forever
      const terms = SPECIALTY_KEYTERMS[normalizeSpecialty(id)] ?? [];
      if (terms.length > 0) stale.push(id);
    }
    expect(
      stale,
      `these now HAVE a bundle and must be dropped from NO_BUNDLE_EXPECTED: ${stale.join(', ')}`,
    ).toEqual([]);
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
