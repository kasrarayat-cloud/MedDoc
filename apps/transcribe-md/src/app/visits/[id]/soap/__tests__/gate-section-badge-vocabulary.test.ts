// ============================================================================
// THE SECTION BADGE SAYS WHAT IT MEASURES — AND NEVER CLAIMS REVIEW.
// ----------------------------------------------------------------------------
// ⚠️ OWNER-REPORTED, 2026-09-03, on the first test of his newly certified form:
// EVERY section already read REVIEWED, before he had looked at anything.
//
// The mechanism was not a flag set too early. THERE WAS NO FLAG. The predicate
// was `body.trim()` — "this section is not empty" — computed client-side on
// every render, persisted nowhere. Generation writes text into every section,
// so every section read REVIEWED the instant the note existed, on the PRE-SIGN
// screen where the doctor is being asked to attest that he reviewed it.
//
// MEASURED at the time: his visit carried `needsReview = true`, unsigned, with
// 14 non-empty sections — all 14 rendering REVIEWED. The same held for all 12
// most recent visits carrying a note.
//
// ⚠️ RULED, class (a) — a product decision with no precedent. Consistent with
// the attestation model already ruled for coding and confirmations:
//
//     THE DOCTOR DOES NOT CLICK FOURTEEN "REVIEWED" BUTTONS. SIGNING IS THE
//     REVIEW.
//
// So: non-empty → DRAFT, empty → EMPTY, and the review claim rides on the
// signature. No per-section machinery, no stored flag.
//
// WHAT THIS GATE PINS is the INVARIANT, not the spelling of any one label:
// the badge is a function of {non-empty, signed} only, and the word REVIEWED
// cannot appear on an unsigned section by any route.
// ============================================================================
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const APP = resolve(__dirname, '..', '..', '..', '..', '..', '..');
const SECTION = readFileSync(
  join(APP, 'src', 'app', 'visits', '[id]', 'soap', 'SoapSection.tsx'),
  'utf8',
);
const EDITOR = readFileSync(
  join(APP, 'src', 'app', 'visits', '[id]', 'soap-editor.tsx'),
  'utf8',
);

/** Source with comments stripped — a gate must not read its own documentation. */
function code(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^[ \t]*\/\/.*$/gm, '');
}

/** The label map, parsed out of the component rather than restated here. */
function labelMap(): Record<string, string> {
  const block = /const STATUS_LABEL[^{]*\{([^}]*)\}/.exec(code(SECTION));
  if (!block) throw new Error('STATUS_LABEL not found — this gate is anchored on it');
  const out: Record<string, string> = {};
  for (const m of block[1]!.matchAll(/(\w+)\s*:\s*'([^']*)'/g)) out[m[1]!] = m[2]!;
  return out;
}

describe('the section badge vocabulary', () => {
  it('⚠️ NON-VACUITY: the label map was actually parsed', () => {
    const m = labelMap();
    expect(Object.keys(m).length).toBeGreaterThanOrEqual(3);
    expect(Object.values(m).every((v) => v.length > 0)).toBe(true);
  });

  // ⚠️ THE ARM THE RULING NAMES. Any state reachable without a signature must
  // not say REVIEWED. This is stated over the WHOLE map rather than over the
  // one label that happens to be wrong today, so a future state added with the
  // word REVIEWED is caught by the same assertion.
  it('⚠️ no UNSIGNED state may say REVIEWED', () => {
    const m = labelMap();
    const offenders = Object.entries(m)
      .filter(([state]) => state !== 'signed')
      .filter(([, label]) => /REVIEW/i.test(label))
      .map(([state, label]) => `${state} => ${label}`);
    expect(
      offenders,
      'an unsigned section claims the doctor reviewed it — the predicate is ' +
        'only "this section is not empty", and signing is the review',
    ).toEqual([]);
  });

  it('the states are exactly {draft, empty, signed}', () => {
    const union = /export type SoapSectionStatus\s*=\s*([^;]+);/.exec(code(SECTION));
    expect(union, 'the status union moved — this gate is anchored on it').not.toBeNull();
    const members = [...union![1]!.matchAll(/'([^']+)'/g)].map((x) => x[1]!).sort();
    expect(members).toEqual(['draft', 'empty', 'signed']);
  });

  it('a non-empty unsigned section reads DRAFT, an empty one EMPTY', () => {
    const m = labelMap();
    expect(m.draft).toBe('DRAFT');
    expect(m.empty).toBe('EMPTY');
    expect(m.signed).toBe('SIGNED');
  });

  // ⚠️ THE DERIVATION IS {non-empty, signed} AND NOTHING ELSE. If a persisted
  // per-section flag is ever introduced, this arm should be revisited
  // DELIBERATELY rather than quietly satisfied — the ruling was that no such
  // flag is built.
  it('⚠️ the status is derived from emptiness and the signature only', () => {
    const fn = /const statusFor = useCallback\(([\s\S]*?)\n  \);/.exec(code(EDITOR));
    expect(fn, 'statusFor moved — this gate is anchored on it').not.toBeNull();
    const body = fn![1]!;
    expect(body, 'the signature short-circuit is gone').toMatch(/isSigned/);
    expect(body, 'the emptiness predicate is gone').toMatch(/\.trim\(\)/);
    expect(
      /'reviewed'/.test(body),
      'statusFor can still return a reviewed state on an unsigned section',
    ).toBe(false);
    // and it returns only the three ruled states
    const returned = [...body.matchAll(/return\s+(?:[^;]*?)'([a-z]+)'/g)].map((x) => x[1]!);
    expect(new Set(returned).size).toBeGreaterThan(0);
    for (const r of returned) expect(['draft', 'empty', 'signed']).toContain(r);
  });

  // ⚠️ THE CHROME IS UNCHANGED PER STATE, and that is deliberate: the ruling
  // called this a vocabulary correction, not a visual one. If the pill mapping
  // changes, that is the redesign arc's decision and this arm should red so it
  // is made on purpose.
  it('the pill chrome is unchanged per state — the look belongs to the redesign', () => {
    const block = /const STATUS_PILL_CLASS[^{]*\{([^}]*)\}/.exec(code(SECTION));
    expect(block).not.toBeNull();
    const pills: Record<string, string> = {};
    for (const m of block![1]!.matchAll(/(\w+)\s*:\s*'([^']*)'/g)) pills[m[1]!] = m[2]!;
    expect(pills.draft).toBe('qm-lin-pill--sage');
    expect(pills.empty).toBe('qm-lin-pill--draft');
    expect(pills.signed).toBe('qm-lin-pill--signed');
  });
});
