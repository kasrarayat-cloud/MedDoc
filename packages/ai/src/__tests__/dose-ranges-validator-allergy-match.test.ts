// ============================================================================
// N-2 follow-up to PR #296 — allergy-match boundary normalization.
// ----------------------------------------------------------------------------
// The deterministic Rx contraindication backstop (validateRxDose) used to
// require the patient allergy string to contain the FULL curated needle
// verbatim — needle "penicillin allergy" only fired when the patient string
// literally contained "penicillin allergy". But L3 extracts the bare substance
// ("penicillin") and charts commonly write it bare, so the deterministic net
// missed exactly the case the model is supposed to be backstopped on.
//
// The fix (dose-ranges-validator.ts → allergyMatchesContraindication) derives
// the bare substance from each "<substance> allergy" needle and matches it as
// a whole word (plural tolerated). It is purely ADDITIVE — it can only widen
// matching, never remove a previously-firing match — and word-boundary
// anchored so it over-warns on natural phrasings WITHOUT inventing allergies
// from substring collisions ("iron" must not match "environmental").
//
// We err toward WARNING: a false positive is doctor-reviewable through the
// existing override gate; a false negative is the danger this fix removes.
//
// Cross-reactivity classes (penicillin↔cephalosporin, sulfa↔sulfonamide) are
// OUT of scope — those are curated into the needle lists, not the matcher.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { validateRxDose } from '../data/dose-ranges-validator';
import { DOSE_RANGES, getDoseRange } from '../data/dose-ranges';

const ADULT = {
  dateOfBirth: '1980-01-01',
  weightKg: 80,
};

/** Does `drug` raise a contraindication warning for a single `allergy` string? */
function contraindicates(drug: string, allergy: string): boolean {
  return validateRxDose({
    drug,
    doseMgPerDay: null, // allergy check runs independent of dose
    patient: { ...ADULT, allergies: [allergy] },
  }).warnings.some((w) => w.code === 'RX_CONTRAINDICATION_MATCH');
}

// Mirror of the private deriveAllergySubstance in dose-ranges-validator.ts —
// used here only to AUDIT the data (assert every substance-allergy needle
// fires on its bare substance). Kept in lockstep with the source by the audit
// test below: if the source regex changes, these assertions are the canary.
function deriveAllergySubstance(needleLower: string): string | null {
  const m = needleLower.match(/^(.+?)\s+allergy\b/);
  if (!m) return null;
  const s = m[1].trim();
  return s.length > 0 ? s : null;
}

describe('validateRxDose allergy match — N-2 required behaviors (amoxicillin)', () => {
  it('bare "penicillin" WARNS on amoxicillin (THE GAP BEING FIXED)', () => {
    expect(contraindicates('amoxicillin', 'penicillin')).toBe(true);
  });

  it('"penicillin allergy" still WARNS (no regression)', () => {
    expect(contraindicates('amoxicillin', 'penicillin allergy')).toBe(true);
  });

  it('"Penicillin (childhood rash)" WARNS (case + trailing reaction note)', () => {
    expect(contraindicates('amoxicillin', 'Penicillin (childhood rash)')).toBe(true);
  });

  it('"penicillins" (plural) WARNS', () => {
    expect(contraindicates('amoxicillin', 'penicillins')).toBe(true);
  });

  it('"allergic to penicillin — hives" WARNS (substance mid-string)', () => {
    expect(contraindicates('amoxicillin', 'allergic to penicillin — hives')).toBe(true);
  });

  it('"no known drug allergies" does NOT warn', () => {
    expect(contraindicates('amoxicillin', 'no known drug allergies')).toBe(false);
  });

  it('an unrelated allergy ("sulfa") does NOT warn on amoxicillin', () => {
    expect(contraindicates('amoxicillin', 'sulfa')).toBe(false);
  });
});

describe('validateRxDose allergy match — word-boundary guards (no substring blowups)', () => {
  it('"environmental allergies" does NOT warn on ferrous sulfate (iron ⊄ environmental)', () => {
    // The classic substring trap: "iron" appears INSIDE "envIRONmental".
    expect(contraindicates('ferrous sulfate', 'environmental allergies')).toBe(false);
  });

  it('bare "iron" DOES warn on ferrous sulfate', () => {
    expect(contraindicates('ferrous sulfate', 'iron')).toBe(true);
  });

  it('"iron-dextran" warns on ferrous sulfate (hyphen boundary)', () => {
    expect(contraindicates('ferrous sulfate', 'iron-dextran reaction')).toBe(true);
  });

  it('"sulfa" does NOT auto-warn on hydrochlorothiazide (sulfa↔sulfonamide cross-react is OUT of scope)', () => {
    expect(contraindicates('hydrochlorothiazide', 'sulfa')).toBe(false);
  });

  it('bare "sulfonamide" DOES warn on hydrochlorothiazide', () => {
    expect(contraindicates('hydrochlorothiazide', 'sulfonamide')).toBe(true);
  });

  it('class needle "beta-lactam" warns on amoxicillin (hyphenated substance)', () => {
    expect(contraindicates('amoxicillin', 'beta-lactam')).toBe(true);
  });

  it('"glp-1" warns on semaglutide (digit + hyphen substance)', () => {
    expect(contraindicates('semaglutide', 'glp-1')).toBe(true);
  });
});

describe('validateRxDose allergy match — full data audit (every substance-allergy needle)', () => {
  // Build the Type-A (substance-allergy) and Type-B (clinical-state) split
  // straight from the live data so the audit can never silently drift.
  const typeA: { drug: string; needle: string; substance: string }[] = [];
  const typeB: { drug: string; needle: string }[] = [];
  for (const e of DOSE_RANGES) {
    for (const ci of e.contraindications ?? []) {
      const substance = deriveAllergySubstance(ci.toLowerCase());
      if (substance) typeA.push({ drug: e.drug, needle: ci, substance });
      else typeB.push({ drug: e.drug, needle: ci });
    }
  }

  it('the data still HAS substance-allergy needles to protect (sanity)', () => {
    expect(typeA.length).toBeGreaterThan(40);
  });

  it('EVERY "<substance> allergy" needle fires on its bare substance', () => {
    const misses = typeA.filter((t) => !contraindicates(t.drug, t.substance));
    expect(
      misses,
      `bare substances that failed to fire:\n${misses
        .map((m) => `  [${m.drug}] "${m.needle}" → "${m.substance}"`)
        .join('\n')}`
    ).toEqual([]);
  });

  it('every canonical drug name resolves in the dose table (audit integrity)', () => {
    const unresolved = DOSE_RANGES.filter((e) => getDoseRange(e.drug)?.drug !== e.drug);
    expect(unresolved.map((e) => e.drug)).toEqual([]);
  });

  // The safety-critical half: a spread of REALISTIC benign allergy strings
  // must not raise a single contraindication across the ENTIRE drug catalog.
  const BENIGN_ALLERGIES = [
    'no known drug allergies',
    'NKDA',
    'NKA',
    'environmental allergies',
    'seasonal allergies',
    'pollen',
    'dust mites',
    'cat dander',
    'dog dander',
    'shellfish',
    'peanuts',
    'tree nuts',
    'eggs',
    'soy',
    'latex',
    'adhesive tape',
    'bee stings',
    'none reported',
    'denies allergies',
    '',
  ];

  it('ZERO false positives: no benign allergy fires on ANY drug (full matrix)', () => {
    const blowups: string[] = [];
    for (const e of DOSE_RANGES) {
      for (const benign of BENIGN_ALLERGIES) {
        if (contraindicates(e.drug, benign)) {
          blowups.push(`"${benign}" → ${e.drug}`);
        }
      }
    }
    expect(
      blowups,
      `false-positive matches (${blowups.length}):\n${blowups.map((b) => `  ${b}`).join('\n')}`
    ).toEqual([]);
  });
});
