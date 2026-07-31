// ============================================================================
// SPEC.md:161 — "Green lock banner". Pinned, because it was grey for two items.
// ----------------------------------------------------------------------------
// Screen 4's lock banner shipped styled from `--rounds-signed` (#6b7480), the
// token for a signed CARD ON THE BOARD. That token's own comment records the
// asymmetry it belongs to: a signed card recedes in grey because it is finished
// business, while a completed track RUN draws in `--rounds-ready` green because
// it is a successful journey. The lock banner is a run, not a card — it is the
// confirmation that the thing succeeded.
//
// It survived B3's merge because nothing tested colour and nothing re-read the
// spec against the component. B4's verification is what found it, by reading
// SPEC.md:161 beside the CSS. SPEC.md:4-6 settles it: "If this file and a
// component disagree, this file is right and the component is a bug."
//
// A screenshot would not catch a regression here either — Gate B's captures are
// uploaded for a human to look at, not diffed. So it is asserted.
//
// ⚠️ THE COMPANION CLAUSE, and the reason a text variant exists at all:
// `--rounds-ready` is #187a4e, which is ~2.3:1 on the dark stage. Using it as
// the TITLE colour would trade a spec deviation for an AA failure — the fourth
// instance of one lesson in this palette (`--rounds-em`/`-em-fill`,
// `--rounds-accent`/`-accent-text`, `--rounds-signed`/`-signed-text`). So the
// test pins BOTH halves: green, and not the fill green as text.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const CSS = readFileSync('src/app/rounds-tokens.css', 'utf8');

/** The declaration block for one selector, comments stripped.
 *
 *  Comment-stripped because this file EXPLAINS the old grey immediately above
 *  the rule that replaced it — a naive `includes('--rounds-signed')` matches
 *  the explanation and passes on a reverted component. That is A2 defect 2, and
 *  it has now caught four guards in this repo. */
function ruleBody(selector: string): string {
  const stripped = CSS.replace(/\/\*[\s\S]*?\*\//g, '');
  const i = stripped.indexOf(selector);
  if (i === -1) return '';
  const open = stripped.indexOf('{', i);
  const close = stripped.indexOf('}', open);
  if (open === -1 || close === -1) return '';
  return stripped.slice(open + 1, close);
}

describe("SPEC.md:161 — Screen 4's lock banner is GREEN", () => {
  it('the comment-stripper works — negative control', () => {
    // The prose DOES name the grey token, right above the rule. If stripping
    // ever stops working, every assertion below silently starts reading it.
    expect(CSS).toContain('--rounds-signed');
    expect(ruleBody(".qm-rounds-signed-lock {")).not.toContain('--rounds-signed');
  });

  it('the extractor finds a real rule body — positive control', () => {
    // A selector that does not exist returns '', and '' satisfies every
    // `not.toContain` below. Without this, a renamed class turns the whole
    // suite into a no-op that reports success.
    const body = ruleBody(".qm-rounds-signed-lock {");
    expect(
      body.length,
      'no rule body found for .qm-rounds-signed-lock — the selector was renamed, ' +
        'and every absence assertion in this file is now vacuous',
    ).toBeGreaterThan(20);
    expect(body).toContain('border');
  });

  it('the banner is drawn from the READY green, not the signed grey', () => {
    const body = ruleBody(".qm-rounds-signed-lock {");
    expect(body).toContain('--rounds-ready');
    expect(body).not.toContain('--rounds-signed');
  });

  it('the banner TITLE uses the text variant, never the fill green', () => {
    const body = ruleBody(".qm-rounds-signed-lock-title {");
    expect(
      body.length,
      'no rule body for .qm-rounds-signed-lock-title',
    ).toBeGreaterThan(10);
    expect(body).toContain('--rounds-ready-text');
    // `color: var(--rounds-ready)` would be ~2.3:1 on the stage. The whole
    // point of the variant is that this cannot happen by copy-paste.
    expect(body).not.toMatch(/color:\s*var\(--rounds-ready\)/);
  });

  it('--rounds-ready-text is defined, and is not the fill value', () => {
    const m = CSS.match(/--rounds-ready-text:\s*([^;]+);/);
    expect(m, '--rounds-ready-text is not defined').toBeTruthy();
    expect(m![1].trim().toLowerCase()).not.toBe('#187a4e');
  });
});
