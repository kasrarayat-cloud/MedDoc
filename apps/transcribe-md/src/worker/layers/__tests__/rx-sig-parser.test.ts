// ============================================================================
// Fix-Pack 1 Q0-1 — rx-sig-parser unit tests (audit Finding 06.1)
// ----------------------------------------------------------------------------
// Locks the parser's contract: for the curated set of common frequency
// patterns the L7c model emits, (strength, sig) → mg/day must be exact.
// PRN and unparseable inputs return null so the validator skips the
// numeric range check rather than guessing.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { parseRxToMgPerDay } from '../rx-sig-parser';

describe('parseRxToMgPerDay — common frequency patterns', () => {
  it('parses "20 mg" + "daily" → 20 mg/day', () => {
    expect(parseRxToMgPerDay('20 mg', 'Take 1 tablet by mouth daily')).toBe(20);
  });

  it('parses "500 mg" + "TID" → 1500 mg/day', () => {
    expect(parseRxToMgPerDay('500 mg', 'Take 1 tablet TID')).toBe(1500);
  });

  it('parses "200 mg" + "BID" → 400 mg/day', () => {
    expect(parseRxToMgPerDay('200 mg', '1 tab BID')).toBe(400);
  });

  it('parses "250 mg" + "QID" without colliding with QD → 1000 mg/day', () => {
    expect(parseRxToMgPerDay('250 mg', '1 tablet PO QID')).toBe(1000);
  });

  it('parses "400 mg" + "Q6H" → 1600 mg/day', () => {
    expect(parseRxToMgPerDay('400 mg', 'Take 1 cap Q6H')).toBe(1600);
  });

  it('parses "0.5 mg" + "Q12H" → 1 mg/day (sub-mg dose)', () => {
    expect(parseRxToMgPerDay('0.5 mg', 'Take 1 tab Q12H')).toBe(1);
  });

  it('parses "20 mg" + "weekly" → ~0.143 mg/day (1/7)', () => {
    const v = parseRxToMgPerDay('20 mg', 'Inject 20 mg subcutaneously weekly');
    expect(v).toBeCloseTo(20 / 7, 6);
  });
});

describe('parseRxToMgPerDay — null / edge cases', () => {
  it('returns null for PRN dosing (variable)', () => {
    expect(parseRxToMgPerDay('400 mg', 'Take 1 tablet Q6H PRN pain')).toBeNull();
  });

  it('returns null when strength is missing', () => {
    expect(parseRxToMgPerDay(null, 'TID')).toBeNull();
    expect(parseRxToMgPerDay('', 'TID')).toBeNull();
  });

  it('returns null when sig is missing', () => {
    expect(parseRxToMgPerDay('20 mg', null)).toBeNull();
    expect(parseRxToMgPerDay('20 mg', '')).toBeNull();
  });

  it('returns null for non-mg units (mcg, mL, IU)', () => {
    expect(parseRxToMgPerDay('100 mcg', 'daily')).toBeNull();
    expect(parseRxToMgPerDay('5 mL', 'BID')).toBeNull();
    expect(parseRxToMgPerDay('1000 IU', 'daily')).toBeNull();
  });

  it('returns null for unrecognised sig vocabulary', () => {
    expect(parseRxToMgPerDay('20 mg', 'apply topically')).toBeNull();
    expect(parseRxToMgPerDay('20 mg', 'as directed')).toBeNull();
  });

  it('disambiguates QID vs QD (QID = 4x, not 1x)', () => {
    // The trap: if the QD branch matched first via substring, "QID"
    // would collapse to 1 dose/day. Locking the order here guards
    // against a future re-ordering regression.
    const qid = parseRxToMgPerDay('100 mg', 'QID');
    const qd = parseRxToMgPerDay('100 mg', 'QD');
    expect(qid).toBe(400);
    expect(qd).toBe(100);
  });

  it('handles "1x/day" and "2x/day" shorthand', () => {
    expect(parseRxToMgPerDay('10 mg', '1x/day')).toBe(10);
    expect(parseRxToMgPerDay('10 mg', '2x/day')).toBe(20);
  });

  it('"twice nightly" family parses to 2 doses/day, not 1 (auditor N-4)', () => {
    expect(parseRxToMgPerDay('20 mg', 'Take 1 tablet twice nightly')).toBe(40);
    expect(parseRxToMgPerDay('20 mg', '2x nightly')).toBe(40);
    expect(parseRxToMgPerDay('20 mg', 'twice a night')).toBe(40);
  });

  it('parses once-nightly phrasings → 1 dose/day (F-8: "simvastatin 40 mg nightly")', () => {
    expect(parseRxToMgPerDay('40 mg', 'Take 1 tablet by mouth nightly')).toBe(40);
    expect(parseRxToMgPerDay('40 mg', 'QHS')).toBe(40);
    expect(parseRxToMgPerDay('40 mg', '1 tab at bedtime')).toBe(40);
    expect(parseRxToMgPerDay('40 mg', 'every night')).toBe(40);
  });
});
