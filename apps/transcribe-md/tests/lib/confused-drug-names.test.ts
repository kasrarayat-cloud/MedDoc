// ============================================================================
// ISMP confused-drug-names safety floor (PR-2: Issues #202 + #206)
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  CONFUSED_DRUG_NAMES,
  CONFUSED_DRUG_NAMES_FLAT,
  type ConfusedDrugPair,
} from '@/lib/confused-drug-names';

describe('CONFUSED_DRUG_NAMES — invariants', () => {
  it('exports a non-empty curated list (~40 pairs)', () => {
    expect(CONFUSED_DRUG_NAMES.length).toBeGreaterThanOrEqual(35);
    expect(CONFUSED_DRUG_NAMES.length).toBeLessThan(60);
  });

  it('every entry has primary + non-empty confusedWith + rationale + severity + boostWeight', () => {
    for (const pair of CONFUSED_DRUG_NAMES) {
      expect(pair.primary.trim()).not.toBe('');
      expect(pair.confusedWith.length).toBeGreaterThan(0);
      expect(pair.rationale.length).toBeGreaterThanOrEqual(10);
      expect(['high', 'medium', 'low']).toContain(pair.severity);
      expect(pair.boostWeight).toBeGreaterThanOrEqual(1);
      expect(pair.boostWeight).toBeLessThanOrEqual(5);
    }
  });

  it('no primary name is empty or duplicated', () => {
    const primaries = CONFUSED_DRUG_NAMES.map((p) => p.primary.toLowerCase());
    const unique = new Set(primaries);
    expect(unique.size).toBe(primaries.length);
  });

  it('majority are high severity (clinical-safety justification for the floor)', () => {
    const high = CONFUSED_DRUG_NAMES.filter((p) => p.severity === 'high').length;
    // At least half of the list should be high-severity wrong-class
    // collisions. The whole point of the safety floor is the
    // catastrophic cases.
    expect(high).toBeGreaterThan(CONFUSED_DRUG_NAMES.length / 2);
  });
});

describe('CONFUSED_DRUG_NAMES — load-bearing pairs', () => {
  // These specific pairs are non-negotiable. If a future edit drops
  // one of them, the test fails before the regression ships.

  const lookup = (name: string): ConfusedDrugPair | undefined =>
    CONFUSED_DRUG_NAMES.find((p) => p.primary === name);

  it('Implanon (Issue #206 seed) → confusedWith insulin', () => {
    const implanon = lookup('Implanon');
    expect(implanon).toBeDefined();
    expect(implanon!.confusedWith).toContain('insulin');
    expect(implanon!.severity).toBe('high');
  });

  it('Nexplanon (Implanon sibling) → confusedWith insulin', () => {
    const nexplanon = lookup('Nexplanon');
    expect(nexplanon).toBeDefined();
    expect(nexplanon!.confusedWith).toContain('insulin');
    expect(nexplanon!.severity).toBe('high');
  });

  it('Tresiba T-cluster (ISMP highest-density) → 5+ confused alternatives', () => {
    const tresiba = lookup('Tresiba');
    expect(tresiba).toBeDefined();
    expect(tresiba!.confusedWith.length).toBeGreaterThanOrEqual(5);
    expect(tresiba!.confusedWith).toEqual(
      expect.arrayContaining(['Toujeo', 'Tradjenta', 'Trulicity', 'Tanzeum']),
    );
  });

  it('tramadol → trazodone (canonical ISMP sound-alike pair)', () => {
    const tramadol = lookup('tramadol');
    expect(tramadol).toBeDefined();
    expect(tramadol!.confusedWith).toContain('trazodone');
    expect(tramadol!.severity).toBe('high');
  });

  it('metformin → metoprolol (canonical TTS phonetic collision)', () => {
    const metformin = lookup('metformin');
    expect(metformin).toBeDefined();
    expect(metformin!.confusedWith).toContain('metoprolol');
  });

  it('Celexa → 4-way wrong-class psych cluster', () => {
    const celexa = lookup('Celexa');
    expect(celexa).toBeDefined();
    expect(celexa!.confusedWith).toEqual(
      expect.arrayContaining(['Celebrex', 'Cerebyx', 'Zyprexa']),
    );
  });

  it('levothyroxine → liothyronine (T4 vs T3, 4x potency)', () => {
    const levo = lookup('levothyroxine');
    expect(levo).toBeDefined();
    expect(levo!.confusedWith).toContain('liothyronine');
  });

  it('Ozempic → GLP-1 brand cluster (Wegovy + Mounjaro + Zepbound)', () => {
    const ozempic = lookup('Ozempic');
    expect(ozempic).toBeDefined();
    expect(ozempic!.confusedWith).toEqual(
      expect.arrayContaining(['Wegovy', 'Mounjaro', 'Zepbound']),
    );
  });
});

describe('CONFUSED_DRUG_NAMES_FLAT — derived flat list (primaries only)', () => {
  it('includes every primary, deduped (PR-2 audit fix: primaries only, not confusedWith)', () => {
    // Asymmetric-boost rationale: the primary is the term we WANT
    // transcribed; the confusedWith alternatives are what Deepgram
    // outputs by default. We only need to bias toward the primary.
    // Boosting both sides pushed the floor to ~93 names / ~280 tokens
    // and forced the builder to drop the specialty layer entirely.
    const expectedPrimaries = new Set<string>(
      CONFUSED_DRUG_NAMES.map((p) => p.primary),
    );
    expect(CONFUSED_DRUG_NAMES_FLAT.length).toBe(expectedPrimaries.size);
    for (const p of expectedPrimaries) {
      expect(CONFUSED_DRUG_NAMES_FLAT).toContain(p);
    }
  });

  it('does NOT include confusedWith-only alternatives (asymmetric boost)', () => {
    // The flat list is primaries only. `insulin` is a confusedWith
    // alternative for Implanon/Nexplanon but NOT itself a primary —
    // we want the model to bias toward Implanon/Nexplanon, not insulin
    // (which it already defaults to). `trazodone` is confusedWith for
    // tramadol (no primary entry of its own). `Latuda` is confusedWith
    // for Lantus.
    expect(CONFUSED_DRUG_NAMES_FLAT).not.toContain('insulin');
    expect(CONFUSED_DRUG_NAMES_FLAT).not.toContain('trazodone');
    expect(CONFUSED_DRUG_NAMES_FLAT).not.toContain('Latuda');
  });

  it('contains Implanon + Nexplanon (Issue #206 seed — primaries only)', () => {
    // The primaries we want boosted to defeat the Implanon→insulin
    // substitution. `insulin` itself is deliberately NOT boosted
    // (see asymmetric-boost rationale above).
    expect(CONFUSED_DRUG_NAMES_FLAT).toContain('Implanon');
    expect(CONFUSED_DRUG_NAMES_FLAT).toContain('Nexplanon');
  });

  it('contains the T-cluster primaries (Trulicity / Tradjenta / Toujeo / Tresiba)', () => {
    // Tanzeum is a confusedWith only (no primary entry — it's
    // discontinued), so it shouldn't appear. Tresiba/Toujeo/Trulicity/
    // Tradjenta are all primaries in our list.
    expect(CONFUSED_DRUG_NAMES_FLAT).toContain('Trulicity');
    expect(CONFUSED_DRUG_NAMES_FLAT).toContain('Tradjenta');
    expect(CONFUSED_DRUG_NAMES_FLAT).toContain('Toujeo');
    expect(CONFUSED_DRUG_NAMES_FLAT).toContain('Tresiba');
  });

  it('contains tramadol (primary; trazodone is confusedWith only)', () => {
    expect(CONFUSED_DRUG_NAMES_FLAT).toContain('tramadol');
  });

  it('total count matches primary count (~44 entries / ~150 tokens)', () => {
    // Each primary contributes exactly 1 name to the flat list.
    expect(CONFUSED_DRUG_NAMES_FLAT.length).toBe(CONFUSED_DRUG_NAMES.length);
    expect(CONFUSED_DRUG_NAMES_FLAT.length).toBeGreaterThanOrEqual(35);
    expect(CONFUSED_DRUG_NAMES_FLAT.length).toBeLessThan(60);
  });

  it('CONFUSED_DRUG_NAMES_FLAT entries are strings with no whitespace-only / empty', () => {
    for (const name of CONFUSED_DRUG_NAMES_FLAT) {
      expect(typeof name).toBe('string');
      expect(name.trim()).toBe(name);
      expect(name.length).toBeGreaterThan(0);
    }
  });
});

describe('safety floor integration with keyterm builder', () => {
  it('builder accepts CONFUSED_DRUG_NAMES_FLAT and counts it in safetyFloor layer', async () => {
    const { buildKeytermsForVisit } = await import('@/lib/deepgram-keyterm-builder');
    const r = buildKeytermsForVisit({
      specialty: 'bariatric-surgery',
      safetyFloor: CONFUSED_DRUG_NAMES_FLAT,
    });
    // Implanon and Nexplanon must reach the output even though
    // bariatric isn't the specialty those medications associate with —
    // safety floor rides regardless.
    expect(r.keyterms).toContain('Implanon');
    expect(r.keyterms).toContain('Nexplanon');
    expect(r.metadata.layers.safetyFloor).toBeGreaterThan(0);
  });

  it('budget stays under 450 tokens with safety floor + every specialty (B1 regression guard)', async () => {
    // PR-2 audit found the safety-floor + core combined could exceed
    // Deepgram's 500-token hard cap, forcing the builder to drop the
    // specialty layer entirely. This test verifies that fix: every
    // specialty must compose under-budget WITHOUT triggering the
    // budget-enforcer trim, AND every specialty term must reach the
    // final keyterm payload (whether attributed to the specialty
    // layer or absorbed into the safety floor via dedupe).
    //
    // Note on layer accounting: when a specialty term overlaps a
    // safety-floor primary (e.g. bariatric_surgery includes Ozempic,
    // which is also in the ISMP safety floor), the dedupe credits it
    // to safetyFloor (first-occurrence wins). That's the intended
    // defense-in-depth, not specialty loss — the term is still in
    // r.keyterms. Asserting layer counts here would conflate dedupe
    // with budget trimming; the real signals are `budgetEnforced`
    // (must be false) and presence-in-payload (every specialty term
    // must appear in r.keyterms).
    const { buildKeytermsForVisit } = await import('@/lib/deepgram-keyterm-builder');
    const { SPECIALTY_KEYTERMS } = await import('@/lib/deepgram-vocabulary');
    for (const specialty of Object.keys(SPECIALTY_KEYTERMS)) {
      const r = buildKeytermsForVisit({
        specialty,
        safetyFloor: CONFUSED_DRUG_NAMES_FLAT,
      });
      expect(
        r.metadata.estimatedTokens,
        `specialty=${specialty} exceeds 450 estimated tokens (${r.metadata.estimatedTokens})`,
      ).toBeLessThanOrEqual(450);
      expect(
        r.metadata.budgetEnforced,
        `specialty=${specialty} triggered budget-enforcer trimming`,
      ).toBe(false);
      // Every specialty term must reach the payload (case-insensitive
      // membership). Dedupe may attribute it to safetyFloor, but it
      // must not be absent.
      const payloadLower = new Set(r.keyterms.map((k) => k.toLowerCase()));
      const expectedTerms = SPECIALTY_KEYTERMS[specialty as keyof typeof SPECIALTY_KEYTERMS];
      for (const term of expectedTerms) {
        expect(
          payloadLower.has(term.toLowerCase()),
          `specialty=${specialty}: term "${term}" missing from keyterm payload`,
        ).toBe(true);
      }
    }
  });

  it('ob_gyn visit + safety floor: Implanon reaches the payload via BOTH layers (defense in depth)', async () => {
    const { buildKeytermsForVisit } = await import('@/lib/deepgram-keyterm-builder');
    const r = buildKeytermsForVisit({
      specialty: 'ob-gyn',
      safetyFloor: CONFUSED_DRUG_NAMES_FLAT,
    });
    // Implanon appears in BOTH the ob_gyn specialty bundle (from PR-1)
    // AND the safety floor (from PR-2). Dedupe credits it to the
    // first-occurrence layer (safetyFloor wins). Defense-in-depth: if
    // a future edit removes Implanon from ob_gyn, the safety floor
    // still catches it.
    expect(r.keyterms).toContain('Implanon');
    expect(r.metadata.layers.safetyFloor).toBeGreaterThan(0);
  });
});
