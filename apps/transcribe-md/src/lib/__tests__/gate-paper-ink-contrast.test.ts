// ============================================================================
// TEXT ON ROUNDS PAPER MUST BE LEGIBLE — AND MUST NOT VANISH ON HOVER
// ----------------------------------------------------------------------------
// `globals.css` colours the visit-document chrome for the DARK canvas it was
// designed on. Under Rounds those same elements sit on #fcfcfa paper, so a rule
// that is CORRECT in its own world lands on the wrong ground. The control this
// gate was written for is `.qm-ux-doc-disclosure` — "View original dictation" on
// a SIGNED note:
//
//     rest    #828995 on #fcfcfa   3.43:1   under the 4.5 floor
//     hover   #f7f8f8 on #fcfcfa   1.04:1   the control DISAPPEARS
//
// ⚠️ THE HOVER ROW IS THE POINT. A control that vanishes at the moment the
// pointer lands on it reads as a broken page, not a low-contrast one — and the
// chevron strokes `currentColor`, so the affordance icon goes too.
//
// ⚠️ THIS GATE COMPUTES RATIOS FROM THE TOKENS, NOT FROM A BROWSER. It is a
// units test, so it cannot see the cascade; the browser measurement against the
// CSS shipped in production lives in the PR. What it CAN do, and what a browser
// run in CI would not do reliably, is fail the moment somebody edits a token or
// re-points one of these rules at the dark ramp.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const CSS = readFileSync(
  path.resolve(__dirname, '../../app/rounds-tokens.css'),
  'utf8'
);

/** A hex token's value, read from the stylesheet rather than transcribed. */
function token(name: string): string {
  const m = CSS.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!m) throw new Error(`token --${name} not found in rounds-tokens.css`);
  return m[1];
}

const srgb = (c: number) => {
  const x = c / 255;
  return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
};
const lum = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  return (
    0.2126 * srgb((n >> 16) & 255) +
    0.7152 * srgb((n >> 8) & 255) +
    0.0722 * srgb(n & 255)
  );
};
const ratio = (a: string, b: string) => {
  const [hi, lo] = lum(a) > lum(b) ? [lum(a), lum(b)] : [lum(b), lum(a)];
  return (hi + 0.05) / (lo + 0.05);
};

const AA = 4.5;

describe('Rounds paper ink clears AA', () => {
  const paper = () => token('rounds-paper-1');

  it('the paper ink tokens clear AA on the paper ground', () => {
    // Both tokens the paper rules are allowed to use. If either stops clearing
    // AA, every rule below it is wrong and the fix is the TOKEN, not the rule.
    expect(ratio(token('rounds-ink'), paper())).toBeGreaterThanOrEqual(AA);
    expect(ratio(token('rounds-ink-muted'), paper())).toBeGreaterThanOrEqual(AA);
  });

  it('POSITIVE CONTROL — the dark-ramp values it replaces do NOT clear AA', () => {
    // Without this the assertion above is satisfiable by almost any pair and
    // proves nothing about the defect. These are the values `globals.css`
    // actually ships for this control, transcribed here as the CONTROL rather
    // than as the expectation.
    const DARK_TEXT_3 = '#828995'; // --color-linear-text-3, the rest state
    const DARK_TEXT = '#f7f8f8'; // --color-linear-text, the hover state
    expect(ratio(DARK_TEXT_3, paper())).toBeLessThan(AA);
    // The hover state is the severe one: near-white on near-white.
    expect(ratio(DARK_TEXT, paper())).toBeLessThan(1.1);
  });

  it('the disclosure takes paper ink in BOTH states, hover included', () => {
    // ⚠️ THE REST STATE ALONE IS HALF A FIX. A rule that fixes rest and leaves
    // hover pointing at `--color-linear-text` still vanishes under the pointer,
    // and that half-fix is exactly what a rest-only assertion would bless.
    const rest = CSS.match(
      /\[data-skin='rounds'\]\s+\.rounds-paper\s+\.qm-ux-doc-disclosure\s*\{[^}]*\}/
    );
    const hover = CSS.match(
      /\[data-skin='rounds'\]\s+\.rounds-paper\s+\.qm-ux-doc-disclosure:hover\s*\{[^}]*\}/
    );
    expect(rest, 'the rest-state paper rule is missing').not.toBeNull();
    expect(hover, 'the HOVER paper rule is missing — the control still vanishes').not.toBeNull();
    expect(rest![0]).toContain('--rounds-ink-muted');
    expect(hover![0]).toContain('--rounds-ink');
    // …and neither may reach back into the dark ramp.
    expect(rest![0]).not.toContain('--color-linear-');
    expect(hover![0]).not.toContain('--color-linear-');
  });

  it('hover DARKENS the control rather than lightening it', () => {
    // The property, stated where it acts: on paper, emphasis is darker. Pinning
    // the two token names alone would pass if somebody swapped them.
    expect(ratio(token('rounds-ink'), paper())).toBeGreaterThan(
      ratio(token('rounds-ink-muted'), paper())
    );
  });
});
