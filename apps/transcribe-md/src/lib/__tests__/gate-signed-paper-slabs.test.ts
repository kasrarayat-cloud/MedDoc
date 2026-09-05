// ============================================================================
// NO NEAR-BLACK SLAB MAY RENDER INSIDE THE WHITE SIGNED PAPER
// ----------------------------------------------------------------------------
// T3 removed the black frame around the visit DOCUMENT. It did not touch the two
// surfaces the frame was sitting next to, both emitted by `SignedDocumentView`
// and both styled from the dark ramp in `globals.css`:
//
//     .qm-ux-doc-summary    background var(--color-linear-surface-2)  #131416
//     .qm-c3-rev2-signbar   background rgba(13,14,16,0.96), sticky, full width
//
// Neither is reachable by T3's family — that is scoped to the visit-document
// classes (`qm-vdoc` / `qm-npv` / `qm-docxp`) — and neither is reachable by the
// paper-ink bridge at the foot of `rounds-tokens.css`, which enumerates
// `qm-rdoc-` / `qm-rx-` / `qm-vdoc-` and not `qm-ux-`. So they were left painting
// near-black grounds inside white paper.
//
// ⚠️ THE INK HAD TO MOVE WITH THE GROUND. `.qm-ux-sum-val` takes
// `--color-linear-text` (#f7f8f8), which is correct on #131416 and measures
// **1.04:1** on paper. Re-grounding without re-inking would have traded a dark
// slab for invisible text — the same half-fix shape as the disclosure's hover.
//
// ⚠️ AND THE BAR KEEPS ITS ALPHA. `rgba(13,14,16,0.96)` is translucent on
// purpose: content scrolls under a `backdrop-filter: blur(12px)`. An opaque
// paper fill would silently retire that, so the replacement is a `color-mix` at
// the same order of transparency.
//
// MEASURED in chromium against the CSS shipped in the running production
// container, signed paper, before → after:
//
//     .qm-ux-doc-summary ground   rgb(19,20,22)      → rgb(243,244,239)
//     .qm-c3-rev2-signbar ground  rgba(13,14,16,.96) → 92% paper, still sticky
//     sum-val                     17.32:1 on dark    → 15.14:1 on paper
//     sum-key / sum-muted          5.23:1            →  6.31:1
//     sign-msg                    10.09:1            →  6.78:1
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const CSS = readFileSync(path.resolve(__dirname, '../../app/rounds-tokens.css'), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '');

function token(name: string): string {
  const m = CSS.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!m) throw new Error(`token --${name} not found`);
  return m[1];
}
const srgb = (c: number) => {
  const x = c / 255;
  return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
};
const lum = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  return 0.2126 * srgb((n >> 16) & 255) + 0.7152 * srgb((n >> 8) & 255) + 0.0722 * srgb(n & 255);
};
const ratio = (a: string, b: string) => {
  const [hi, lo] = lum(a) > lum(b) ? [lum(a), lum(b)] : [lum(b), lum(a)];
  return (hi + 0.05) / (lo + 0.05);
};
const AA = 4.5;

/** A rule body, by its exact selector, from the comment-stripped stylesheet. */
function rule(selector: string): string | null {
  const esc = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
  const m = CSS.match(new RegExp(`${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[1] : null;
}

describe('the signed paper carries no dark slab', () => {
  it('both slabs are re-grounded on PAPER, scoped to .rounds-paper', () => {
    // Scoped to the shared paper class — not to one host — so a third paper host
    // inherits it. That is T3's property, applied to the surfaces T3 skipped.
    for (const sel of [
      "[data-skin='rounds'] .rounds-paper .qm-ux-doc-summary",
      "[data-skin='rounds'] .rounds-paper .qm-c3-rev2-signbar",
    ]) {
      const body = rule(sel);
      expect(body, `${sel} is missing — the slab is back`).not.toBeNull();
      expect(body).toMatch(/--rounds-paper/);
      expect(body, 'a paper rule must not reach back into the dark ramp').not.toMatch(
        /--color-linear-/
      );
    }
  });

  it('THE INK MOVED WITH THE GROUND — re-grounding alone is a half-fix', () => {
    // Without this arm, a change that lightened the ground and left the ink at
    // --color-linear-text (#f7f8f8) would pass every other assertion here while
    // rendering white text on white paper.
    for (const sel of [
      "[data-skin='rounds'] .rounds-paper .qm-ux-sum-val",
      "[data-skin='rounds'] .rounds-paper .qm-c3-rev2-sign-msg",
    ]) {
      const body = rule(sel);
      expect(body, `${sel} is missing — the ground moved and the ink did not`).not.toBeNull();
      expect(body).toMatch(/--rounds-ink/);
    }
  });

  it('POSITIVE CONTROL — the dark-ramp values being replaced FAIL on paper', () => {
    // Without this the arms above are satisfiable by almost any tokens and prove
    // nothing about the defect. These are the values globals.css actually ships.
    const paper = token('rounds-paper-1');
    expect(ratio('#f7f8f8', paper), '--color-linear-text on paper').toBeLessThan(1.1);
    expect(ratio('#131416', paper), 'the slab ground vs paper — near-maximum contrast')
      .toBeGreaterThan(15);
    // …and the tokens that replace them clear AA on that same ground.
    expect(ratio(token('rounds-ink'), paper)).toBeGreaterThanOrEqual(AA);
    expect(ratio(token('rounds-ink-muted'), paper)).toBeGreaterThanOrEqual(AA);
  });

  it('the export bar keeps its TRANSLUCENCY — an opaque fill retires the blur', () => {
    // `backdrop-filter: blur(12px)` on an opaque background is decoration that
    // does nothing. Pinning the alpha keeps the affordance rather than the rule.
    const body = rule("[data-skin='rounds'] .rounds-paper .qm-c3-rev2-signbar");
    // ⚠️ NOT `/color-mix\([^)]*transparent/` — the value contains `var(--…)`, so a
    // negated-paren class stops at the FIRST `)` and never reaches `transparent`.
    // That regex red this arm against a correct rule.
    expect(body, 'an opaque paper fill would silently retire the backdrop blur').toMatch(
      /color-mix\([\s\S]*?transparent\s*\)/
    );
  });

  it('neither slab is reachable by the paper-ink bridge — so these rules are load-bearing', () => {
    // The bridge enumerates three prefixes. If `qm-ux-` were ever added to it,
    // the ink arms above would become redundant and this arm would say so.
    const bridge = CSS.match(/\[class\^='qm-rdoc-'\][\s\S]*?\}/);
    expect(bridge, 'the paper-ink bridge is gone — re-check what covers qm-ux-').not.toBeNull();
    expect(bridge![0]).not.toMatch(/qm-ux-/);
  });
});
