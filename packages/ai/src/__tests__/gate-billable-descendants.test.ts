// ============================================================================
// GATE — billableDescendantsOf, the derivation ruling #149(f) deleted
// ----------------------------------------------------------------------------
// #149(f) refused this feature and wrote its own re-arming condition: "the
// allowlist becoming the full CMS billable set … at which point membership and
// billability coincide, and (f)'s derivation becomes sound." T8 met it. This
// gate exists to make that soundness falsifiable rather than asserted.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL, stated first so the assertions can be read
// against an intent rather than taken as self-evidently correct:
//   · the list is TRUNCATED anywhere            -> the completeness block
//   · a HEADER is returned as a substitute       -> the every-entry-billable block
//   · a code is returned as its own descendant   -> the strictness block
//   · a string we cannot characterise gets an answer -> the refusal block
//   · normalisation drifts from isValidIcd10     -> the normalisation block
//   · the upcoding vector reopens                -> the #149(f) reference block
// ============================================================================

import { describe, it, expect } from 'vitest';
import {
  ICD10_ALLOWLIST,
  ICD10_HEADERS,
  billableDescendantsOf,
  isValidIcd10,
  isIcd10Header,
} from '../data/icd10-allowlist';

// ── AN INDEPENDENT DERIVATION, BY THE OPPOSITE ROUTE ────────────────────────
// The shipped function scans DESCENDANTS of a header. This one enumerates the
// ANCESTORS of every billable code and groups them. Different direction,
// different data structure, no shared failure mode — so agreement between them
// is a reconciliation and not an echo. AGENTS.md: "CONFIRM A FIGURE YOU WILL
// BUILD ON BY A SECOND, INDEPENDENT ROUTE."
const expected = (() => {
  const m = new Map<string, string[]>();
  for (const b of ICD10_ALLOWLIST) {
    for (let len = 3; len < b.length; len++) {
      const p = b.slice(0, len);
      if (!ICD10_HEADERS.has(p)) continue;
      const cur = m.get(p);
      if (cur) cur.push(b);
      else m.set(p, [b]);
    }
  }
  for (const v of m.values()) v.sort();
  return m;
})();

describe('billableDescendantsOf — the #149(f) reference case', () => {
  it('returns BOTH obesity siblings — the upcoding vector is closed', () => {
    // The measurement that killed the feature: billableChildrenOf('E66.0')
    // returned ['E66.01'] alone, offering MORBID obesity as the only child of
    // plain obesity. Both are present now, so a singleton is no longer a lie.
    expect(billableDescendantsOf('E66.0')).toEqual(['E66.01', 'E66.09']);
  });

  it('offers the full diabetes-complication family, not just hyperglycaemia', () => {
    // The ruling's second example: E11.6 -> ['E11.65'] "offers hyperglycemia
    // where the record may say hypoglycemia". E11.649 IS hypoglycaemia.
    const d = billableDescendantsOf('E11.6');
    expect(d).toContain('E11.65');
    expect(d).toContain('E11.649');
    expect(d.length).toBeGreaterThan(2);
  });

  it('answers the header cases this codebase already documented', () => {
    expect(billableDescendantsOf('K21.0')).toEqual(['K21.00', 'K21.01']);
    expect(billableDescendantsOf('M54.5')).toEqual(['M54.50', 'M54.51', 'M54.59']);
    expect(billableDescendantsOf('Z83.71')).toEqual([
      'Z83.710', 'Z83.711', 'Z83.718', 'Z83.719',
    ]);
  });
});

describe('billableDescendantsOf — completeness, the property that failed before', () => {
  it('matches an independently derived set for EVERY one of the 23,467 headers', () => {
    // Not a sample. The defect being guarded against is a list that is right
    // 236 times and wrong once, so a sample cannot discharge it.
    const wrong: string[] = [];
    for (const h of ICD10_HEADERS) {
      const got = billableDescendantsOf(h);
      const want = expected.get(h) ?? [];
      if (got.length !== want.length || got.some((c, i) => c !== want[i])) {
        wrong.push(`${h}: got ${got.length}, expected ${want.length}`);
      }
    }
    expect(wrong.slice(0, 20)).toEqual([]);
    expect(wrong).toHaveLength(0);
  });

  it('is non-vacuous — the independent map actually covers the headers', () => {
    // A comparison against an empty map would pass while proving nothing.
    expect(expected.size).toBe(ICD10_HEADERS.size);
    let total = 0;
    for (const v of expected.values()) total += v.length;
    expect(total).toBe(242_114); // measured against the CMS release
  });

  it('does not truncate the largest expansion', () => {
    let max = 0;
    let maxHeader = '';
    for (const h of ICD10_HEADERS) {
      const n = billableDescendantsOf(h).length;
      if (n > max) { max = n; maxHeader = h; }
    }
    // ⚠️ "All of them, never one" is the contract. 3,096 is the real number;
    // any capping or slicing in the implementation moves it.
    expect(max).toBe(3096);
    expect(billableDescendantsOf(maxHeader)).toHaveLength(3096);
  });
});

describe('billableDescendantsOf — the population facts it rests on', () => {
  it('every header has at least one billable descendant', () => {
    // ⚠️ A POPULATION FACT ABOUT FY2026, not a property of ICD-10-CM. It is
    // asserted so a future edition that breaks it says so loudly, rather than
    // silently producing empty substitute lists nobody notices.
    const barren = [...ICD10_HEADERS].filter((h) => billableDescendantsOf(h).length === 0);
    expect(barren.slice(0, 10)).toEqual([]);
    expect(barren).toHaveLength(0);
  });

  it('45 headers are genuine singletons — and a singleton now means what it says', () => {
    const singles = [...ICD10_HEADERS].filter((h) => billableDescendantsOf(h).length === 1);
    expect(singles).toHaveLength(45);
    // Spot-check that a singleton really is the only submittable answer.
    expect(billableDescendantsOf('I1A')).toEqual(['I1A.0']);
    expect(billableDescendantsOf('S06.1X7')).toEqual(['S06.1X7A']);
  });

  it('billable codes are leaves, so a submittable code offers no substitutes', () => {
    for (const c of ['I10', 'E11.9', 'K21.00', 'M54.51', 'E66.09', 'QA0.0151']) {
      expect(isValidIcd10(c), `${c} must be billable`).toBe(true);
      expect(billableDescendantsOf(c), `${c} is a leaf`).toEqual([]);
    }
    // and the whole set, not just the six above
    const notLeaves = [...ICD10_ALLOWLIST].filter((c) => billableDescendantsOf(c).length > 0);
    expect(notLeaves.slice(0, 10)).toEqual([]);
    expect(notLeaves).toHaveLength(0);
  });
});

describe('billableDescendantsOf — every entry is a real substitute', () => {
  it('never returns a header, on any header', () => {
    const bad: string[] = [];
    for (const h of ICD10_HEADERS) {
      for (const c of billableDescendantsOf(h)) {
        if (!isValidIcd10(c) || isIcd10Header(c)) bad.push(`${h} -> ${c}`);
      }
    }
    expect(bad.slice(0, 10)).toEqual([]);
    expect(bad).toHaveLength(0);
  });

  it('never returns the input itself — asserted where the property is LIVE', () => {
    // ⚠️ AN EARLIER DRAFT ASSERTED THIS OVER HEADERS AND WAS VACUOUS. The scan
    // reads only the billable list, and the two sets are DISJOINT (asserted by
    // icd10-fy2026-ingestion.test.ts, "is disjoint from the header set"), so a
    // header can never be returned AT ALL — let alone as its own descendant.
    // The mutation `c.length > trimmed.length` -> `>=` therefore left that
    // assertion green and was caught only by a NEIGHBOURING guard, which leaves
    // the arm unproved. AGENTS.md: "A CONTROL AIMED WHERE THE ANSWER IS
    // PREDETERMINED IS NOT A CONTROL", and "STATE THE PROPERTY WHERE IT ACTS".
    //
    // The strictness is live for BILLABLE input, because a billable code IS in
    // the list being scanned and a non-strict comparison would return it.
    for (const c of ['I10', 'E11.9', 'M54.51', 'K21.00', 'E66.09']) {
      expect(isValidIcd10(c), `${c} must be in the scanned list`).toBe(true);
      expect(
        billableDescendantsOf(c),
        `${c} must not be its own descendant`
      ).not.toContain(c);
    }
    // and across the whole billable set, not just the five above
    const selfy = [...ICD10_ALLOWLIST].filter((c) => billableDescendantsOf(c).includes(c));
    expect(selfy.slice(0, 10)).toEqual([]);
    expect(selfy).toHaveLength(0);
  });

  it('is deterministic, and its sortedness is a STRUCTURAL INVARIANT not an arm', () => {
    // ⚠️ HONEST LABEL. `BILLABLE_SORTED` is built with `.sort()`, so the output
    // of a contiguous scan over it is sorted BY CONSTRUCTION — this assertion
    // can therefore never fail while that call is present, and deleting the
    // `.sort()` reds 0 of the gate because the generated payload already comes
    // out sorted. It is kept as a cheap invariant check on the property the
    // binary search depends on, and it is NOT counted among the arms that
    // constrain the derivation. AGENTS.md: "A CONTROL AIMED WHERE THE ANSWER IS
    // PREDETERMINED IS NOT A CONTROL" — so it is named as one rather than
    // presented as coverage.
    for (const h of ['M54.5', 'I83.81', 'Z83.71', 'E11.6']) {
      const a = billableDescendantsOf(h);
      expect([...a].sort()).toEqual([...a]);
      expect(billableDescendantsOf(h)).toEqual(a); // determinism IS live
    }
  });

  it('every return path is frozen — including the refusals', () => {
    // ⚠️ THE REFUSAL PATHS WERE NOT FROZEN AND NOTHING ASSERTED IT. `push()`
    // succeeded on a refused input and threw on an answered one, so a caller
    // could write a fabricated substitute into the array the function returned
    // in order to REFUSE. Mutating `Object.freeze(out)` to `out` redded 0 of
    // the then-17 assertions: the property had no arm at all.
    const answered = billableDescendantsOf('E66.0');
    const refusedUnknown = billableDescendantsOf('S82.62X');
    const refusedLeaf = billableDescendantsOf('I10');
    const refusedEmpty = billableDescendantsOf('');
    for (const [label, arr] of [
      ['answered', answered], ['unknown-refusal', refusedUnknown],
      ['leaf-refusal', refusedLeaf], ['empty-input', refusedEmpty],
    ] as const) {
      expect(Object.isFrozen(arr), `${label} must be frozen`).toBe(true);
      expect(() => (arr as string[]).push('X00.0'), `${label} must reject push`).toThrow();
    }
    // non-vacuity: the answered case really does carry entries
    expect(answered.length).toBeGreaterThan(0);
  });
});

describe('billableDescendantsOf — refuses what it cannot characterise', () => {
  it('returns nothing for a string that is not a code, even a real prefix', () => {
    // ⚠️ THE DANGEROUS SHAPE. 'S82.62X' is a prefix of SIXTEEN real billable
    // codes (S82.62XA, S82.62XB, …) and is NOT itself a code — it is what you
    // get by dropping the required 7th character. Answering it would present a
    // confident substitute list for a category that does not exist.
    // ⚠️ An earlier draft used 'I83.8' here, on the assumption it was not a
    // code. It IS a header, and the assertion below caught the guess. Measured:
    // 4,553 strings in FY2026 are a prefix of a billable code while being
    // neither billable nor a header, so this refusal is load-bearing.
    for (const s of ['S82.62X', 'K58.3', 'I83.810', 'Z99.999', 'XX99.99', 'M54', 'I8']) {
      if (isValidIcd10(s) || isIcd10Header(s)) continue; // guard the fixture itself
      expect(billableDescendantsOf(s), `${s} must be refused`).toEqual([]);
    }
  });

  it('refuses ALL 6,257 prefix-shaped non-codes, not a hand-picked sample', () => {
    // ⚠️ THIS BLOCK USED TO BE A TWO-ELEMENT SAMPLE, AND THE PASS BROKE IT.
    // Weakening the guard to spare exactly the sampled points let
    // billableDescendantsOf('O33.4X') return SEVEN confident substitutes for a
    // category CMS does not define, with the gate fully green. A sample cannot
    // discharge a safety property whose population is 6,257 — so this measures
    // the population, derived here rather than hard-coded.
    const prefixes = new Set<string>();
    for (const b of ICD10_ALLOWLIST) {
      for (let n = 3; n < b.length; n++) prefixes.add(b.slice(0, n));
    }
    const refusable = [...prefixes].filter(
      (x) => !ICD10_ALLOWLIST.has(x) && !ICD10_HEADERS.has(x)
    );
    // Non-vacuity: the population must be the size we measured, or the sweep
    // below is checking a set that quietly shrank.
    expect(refusable.length).toBe(6257);
    const answered = refusable.filter((x) => billableDescendantsOf(x).length > 0);
    expect(answered.slice(0, 20)).toEqual([]);
    expect(answered).toHaveLength(0);
  });

  it('the fixture above is non-vacuous — at least one entry IS a real prefix', () => {
    // If every fixture entry were also absent as a prefix, the test would pass
    // for the wrong reason. Prove the hard case is actually exercised.
    const prefixed = [...ICD10_ALLOWLIST].filter((c) => c.startsWith('S82.62X'));
    expect(prefixed.length, 'S82.62X must really prefix billable codes').toBe(16);
    expect(isValidIcd10('S82.62X'), 'and must not itself be billable').toBe(false);
    expect(isIcd10Header('S82.62X'), 'and must not be a header either').toBe(false);
    expect(billableDescendantsOf('S82.62X'), 'so it gets NO answer').toEqual([]);
  });

  it('returns nothing for empty and nullish input', () => {
    expect(billableDescendantsOf('')).toEqual([]);
    expect(billableDescendantsOf(null)).toEqual([]);
    expect(billableDescendantsOf(undefined)).toEqual([]);
    expect(billableDescendantsOf('   ')).toEqual([]);
  });
});

describe('billableDescendantsOf — normalisation is isValidIcd10\'s, and no wider', () => {
  it('normalises case and surrounding whitespace, exactly as the validator does', () => {
    const want = billableDescendantsOf('M54.5');
    expect(want.length).toBeGreaterThan(0);
    for (const variant of ['m54.5', ' M54.5 ', 'M54.5\n', 'm54.5\t']) {
      expect(billableDescendantsOf(variant), variant).toEqual(want);
    }
  });

  it('still refuses an undotted header — the pinned decision, one layer on', () => {
    // isValidIcd10 refuses 'E119'; this must refuse 'M545' for the same reason.
    // If normalisation ever widens, it must widen in ONE place, deliberately.
    expect(isValidIcd10('M545')).toBe(false);
    expect(billableDescendantsOf('M545')).toEqual([]);
  });
});
