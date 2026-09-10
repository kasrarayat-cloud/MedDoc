// ============================================================================
// ORACLE — ADMIN-3 PR-1 (ruling #197): the imaging rule moved from the literal
// `id === 'ultrasound'` into catalog DATA (`reportKind`). The claim is
// BYTE-IDENTICAL BEHAVIOUR: for every input, in every flag state, the three
// readers answer exactly what the frozen 6fcd21d0 bodies answered.
//
//   isImagingReportSpecialty — the RAW predicate (ignores the flag): worker's
//                              CPT/E&M skip and post-L6 table rebuild
//   emAppliesToSpecialty     — the FLAG-GATED switch: L4 routing, E/M at
//                              compute/store/export, the sign gate
//   visibleSpecialties       — the picker reader
//
// The expected side is `frozen` (verbatim copies, see __test-support__); the
// input side is DERIVED from the live catalog + legacy map, so a new row joins
// the oracle automatically — and a new IMAGING row reds it, because the frozen
// literal still says only 'ultrasound' is imaging. That red is intended: a new
// imaging type is a behaviour change and must be judged as one.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import {
  LEGACY_SPECIALTY_KEYS,
  SPECIALTIES,
  emAppliesToSpecialty,
  isImagingReportSpecialty,
  ultrasoundSpecialtyEnabled,
  visibleSpecialties,
} from './specialties';
import {
  FLAG_STATES,
  FULL_UNIVERSE,
  STRING_UNIVERSE,
  frozen,
  restoreUltrasoundFlag,
  setUltrasoundFlag,
  show,
} from './__test-support__/report-kind-oracle';

const OPTS_SHAPES: readonly ({ forVisitCreate?: boolean } | undefined)[] = [
  undefined,
  {},
  { forVisitCreate: true },
  { forVisitCreate: false },
];

afterEach(restoreUltrasoundFlag);

describe.each(FLAG_STATES.map((v) => [show(v), v] as const))(
  'NEXT_PUBLIC_ULTRASOUND_SPECIALTY = %s',
  (_label, value) => {
    beforeEach(() => setUltrasoundFlag(value));

    it('control: the flag reader answers what the frozen reader answers', () => {
      expect(ultrasoundSpecialtyEnabled()).toBe(frozen.flag());
    });

    it('isImagingReportSpecialty === frozen `id === "ultrasound"` for EVERY input', () => {
      const diffs = FULL_UNIVERSE.filter(
        (u) => isImagingReportSpecialty(u) !== frozen.isImaging(u)
      ).map(show);
      expect(diffs).toEqual([]);
    });

    it('emAppliesToSpecialty === frozen `!(flag && id === "ultrasound")` for EVERY input', () => {
      const diffs = FULL_UNIVERSE.filter(
        (u) => emAppliesToSpecialty(u) !== frozen.emApplies(u)
      ).map(show);
      expect(diffs).toEqual([]);
    });

    it('visibleSpecialties returns the SAME rows, in the SAME order, for every opts shape', () => {
      for (const opts of OPTS_SHAPES) {
        const got = visibleSpecialties(opts);
        const want = frozen.visible(opts);
        expect(got.map((s) => s.id), show(opts)).toEqual(want.map((s) => s.id));
        // Identity, not just ids: the pickers render these objects.
        got.forEach((s, i) => expect(s).toBe(want[i]));
      }
    });
  }
);

describe('THE FLAG READ STAYS A LITERAL, so Next.js can still inline it', () => {
  it('ultrasoundSpecialtyEnabled reads process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY by name', () => {
    // Behaviour cannot see this: under vitest `process.env[name]` and the
    // literal read return the same value. In a Next.js CLIENT bundle only the
    // literal is replaced at build time — a computed read ships as a runtime
    // lookup of an env var the browser does not have, so the flag reads OFF
    // client-side and Ultrasound silently disappears from every picker in
    // production (where the flag is ON). So the form is pinned, not the value.
    const src = readFileSync(path.join(__dirname, 'specialties.ts'), 'utf8');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');
    const body = /export function ultrasoundSpecialtyEnabled\(\): boolean \{([\s\S]*?)\n\}/.exec(code);
    expect(body, 'ultrasoundSpecialtyEnabled must still exist').not.toBeNull();
    expect(body![1].trim()).toBe("return process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY === 'true';");
    expect(code, 'no computed process.env[...] read anywhere in the catalog').not.toMatch(
      /process\.env\s*\[/
    );
  });
});

describe('THE ORACLE IS NOT VACUOUS', () => {
  it('the universe is derived from the real catalog and the real legacy map', () => {
    expect(LEGACY_SPECIALTY_KEYS.length).toBeGreaterThan(0);
    for (const s of SPECIALTIES) expect(STRING_UNIVERSE).toContain(s.id);
    for (const k of LEGACY_SPECIALTY_KEYS) expect(STRING_UNIVERSE).toContain(k);
    for (const brief of ['', 'Ultrasound', ' ultrasound', 'ultrasound ']) {
      expect(STRING_UNIVERSE).toContain(brief);
    }
    expect(FULL_UNIVERSE).toContain(null);
    expect(FULL_UNIVERSE).toContain(undefined);
  });

  it('every predicate has inputs on BOTH sides, so agreement is not agreement on "false"', () => {
    setUltrasoundFlag('true');
    expect(FULL_UNIVERSE.filter((u) => frozen.isImaging(u)).length).toBeGreaterThan(0);
    expect(FULL_UNIVERSE.filter((u) => !frozen.isImaging(u)).length).toBeGreaterThan(0);
    expect(FULL_UNIVERSE.filter((u) => !frozen.emApplies(u)).length).toBeGreaterThan(0);
    const onLen = frozen.visible().length;
    setUltrasoundFlag(undefined);
    expect(FULL_UNIVERSE.filter((u) => !frozen.emApplies(u))).toEqual([]);
    expect(frozen.visible().length, 'flag off must hide a row').toBeLessThan(onLen);
  });

  it('the universe DISCRIMINATES every plausible wrong implementation', () => {
    // If none of these disagreed with the frozen rule on some input, the
    // oracle could not tell them apart from the right answer.
    const str = (u: unknown): u is string => typeof u === 'string';
    const WRONG: Record<string, (u: string | null | undefined) => boolean> = {
      caseInsensitive: (u) => str(u) && u.toLowerCase() === 'ultrasound',
      trimmed: (u) => str(u) && u.trim() === 'ultrasound',
      prefix: (u) => str(u) && u.startsWith('ultrasound'),
      substring: (u) => str(u) && u.includes('ultrasound'),
      labelToo: (u) => u === 'ultrasound' || u === 'Ultrasound',
      looseEquality: (u) => (u as unknown) == 'ultrasound',
      prototypeLookup: (u) =>
        Boolean(({ ultrasound: true } as Record<string, unknown>)[u as string]),
      secondImagingRow: (u) => u === 'ultrasound' || u === 'vascular-surgery',
      nothingIsImaging: () => false,
    };
    const undetected = Object.entries(WRONG)
      .filter(([, wrong]) => FULL_UNIVERSE.every((u) => wrong(u) === frozen.isImaging(u)))
      .map(([name]) => name);
    expect(undetected).toEqual([]);
  });
});
