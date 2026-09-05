// ============================================================================
// CLINICAL PROSE IS LEGIBLE ON THE SURFACE IT IS ACTUALLY PAINTED ON.
// ----------------------------------------------------------------------------
// ⚠️ OWNER-REPORTED, 2026-09-03, on the first test of his newly certified form:
// the HPI and GI ROS prose rendered near-black on black. Measured:
//
//     --rounds-ink  #191e26   on   --color-linear-surface-1  #0d0e10
//                        =  1.15 : 1
//
// Below the 1.16:1 that `docs/canon/67-*` records as the worst contrast failure
// this programme had ever found, and it stood for roughly a month.
//
// ⚠️ THE MECHANISM WAS TWO DEFENSIBLE DECISIONS COMPOSING. `.rounds-clinical` is
// a TYPE class — font, size, leading — and it also bound `--rounds-ink`, on the
// stated reasoning that its consumer "renders inside `.rounds-paper`". That
// premise was false: `.rounds-paper` has exactly ONE consumer in the app, the
// signed document, and the SOAP view is not inside it. Meanwhile the section
// card `.qm-lin-soap-section-v6` paints `--color-linear-surface-1` underneath
// the prose. Neither decision is wrong alone.
//
// ⚠️ AND AN AXE SWEEP WOULD NOT NECESSARILY HAVE CAUGHT IT. `docs/canon/67-*`
// records that axe reported 5 contrast failures while the true worst — 1.16:1 —
// sat in its `incomplete` bucket, the set the tool ADMITS it could not judge.
// A ratio computed from the tokens cannot land in that bucket. This gate is the
// arithmetic; the axe sweep in `tests/e2e/helpers/rounds-axe.ts` is the other
// instrument, and neither substitutes for the other.
//
// WHAT THIS GATE ASSERTS is the pairing, not a spelling: for each surface a
// clinical-prose class is painted on, the resulting ratio clears WCAG AA for
// body text. If somebody improves a token, this still passes. If somebody
// re-binds paper ink to a dark surface, it fails with the number.
// ============================================================================
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const APP = resolve(__dirname, '..', '..', '..');
const TOKENS = readFileSync(join(APP, 'src', 'app', 'rounds-tokens.css'), 'utf8');
const GLOBALS = readFileSync(join(APP, 'src', 'app', 'globals.css'), 'utf8');
const SOAP_BODY = readFileSync(
  join(APP, 'src', 'app', 'visits', '[id]', 'soap', 'SoapBody.tsx'),
  'utf8',
);

/** WCAG relative luminance. */
function luminance(hex: string): number {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? [...h].map((c) => c + c).join('') : h;
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255);
  const f = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * f(r!) + 0.7152 * f(g!) + 0.0722 * f(b!);
}
function ratio(fg: string, bg: string): number {
  const [a, b] = [luminance(fg), luminance(bg)];
  const [hi, lo] = a > b ? [a, b] : [b, a];
  return (hi + 0.05) / (lo + 0.05);
}
/** Read a `--token: #hex;` declaration out of a stylesheet. */
function token(css: string, name: string): string {
  const m = new RegExp(`--${name}\\s*:\\s*(#[0-9a-fA-F]{3,8})\\s*;`).exec(css);
  if (!m) throw new Error(`token --${name} not found — this gate is reading the wrong file`);
  return m[1]!;
}

describe('clinical prose contrast — the ratio, computed from the tokens', () => {
  // ⚠️ NON-VACUITY FIRST. If the token reader silently returned nothing, every
  // ratio below would be computed from a default and the gate would measure its
  // own fallback. Prove the values were actually read.
  it('⚠️ the tokens were actually read, and are distinct', () => {
    const inkPaper = token(TOKENS, 'rounds-ink');
    const darkText = token(GLOBALS, 'color-linear-text');
    const darkSurface = token(GLOBALS, 'color-linear-surface-1');
    const paperSurface = token(TOKENS, 'rounds-paper-1');
    expect(new Set([inkPaper, darkText, darkSurface, paperSurface]).size).toBe(4);
    expect(inkPaper.toLowerCase()).toBe('#191e26');
    expect(darkSurface.toLowerCase()).toBe('#0d0e10');
  });

  it('⚠️ the SOAP section body clears AA on the card it is painted on', () => {
    const fg = token(GLOBALS, 'color-linear-text');
    const bg = token(GLOBALS, 'color-linear-surface-1');
    const r = ratio(fg, bg);
    expect(
      Number(r.toFixed(2)),
      `clinical prose ${fg} on the section card ${bg} is ${r.toFixed(2)}:1 — ` +
        'a doctor cannot read their own note',
    ).toBeGreaterThanOrEqual(4.5);
  });

  it('paper ink still clears AA on paper — the other way to be wrong', () => {
    // The fix must not have "solved" contrast by breaking the signed document.
    const r = ratio(token(TOKENS, 'rounds-ink'), token(TOKENS, 'rounds-paper-1'));
    expect(Number(r.toFixed(2))).toBeGreaterThanOrEqual(4.5);
  });

  // ⚠️ THE REGRESSION ARM, AND IT PINS THE PROPERTY RATHER THAN THE SPELLING.
  // `.rounds-clinical` is a TYPE class. The moment it declares a colour it is
  // asserting something about a surface it cannot see, which is exactly how the
  // owner's note became unreadable.
  it('⚠️ `.rounds-clinical` declares TYPE only — never a colour', () => {
    const block = /\[data-skin='rounds'\]\s*\.rounds-clinical\s*\{([^}]*)\}/.exec(TOKENS);
    expect(block, '.rounds-clinical is gone — this gate is anchored on it').not.toBeNull();
    const body = block![1]!;
    expect(body, 'it still sets font/size/leading').toMatch(/font-family|font-size|line-height/);
    expect(
      /(^|[\s;])color\s*:/.test(body),
      'a font/size/leading class cannot know what surface it will be laid on; ' +
        'the SURFACE owns the ink',
    ).toBe(false);
  });

  it('⚠️ the dark section body binds its own ink, rather than inheriting', () => {
    const block = /\.qm-lin-soap-body-v6\s*\{([^}]*)\}/.exec(GLOBALS);
    expect(block, '.qm-lin-soap-body-v6 is gone — this gate is anchored on it').not.toBeNull();
    expect(
      block![1]!,
      'the body carries no colour of its own, so it inherits — which is exactly ' +
        'how it picked up paper ink from a type class',
    ).toMatch(/color\s*:/);
  });

  // ⚠️ THE FALSE PREMISE IS PINNED SO IT CANNOT RETURN. The original
  // justification was that this prose sits inside `.rounds-paper`. It does not:
  // that class has one consumer, the signed document.
  it('⚠️ the SOAP view is NOT inside .rounds-paper — the premise that failed', () => {
    expect(
      /className="[^"]*\brounds-paper\b/.test(SOAP_BODY),
      'SoapBody now claims to be inside .rounds-paper — if that became true, the ' +
        'ink reasoning changes and this gate must be revisited deliberately',
    ).toBe(false);
  });
});
