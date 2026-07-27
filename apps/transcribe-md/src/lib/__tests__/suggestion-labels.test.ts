// ============================================================================
// The normaliser parity invariant, enforced by a test rather than a comment.
// ----------------------------------------------------------------------------
// normalizeSectionLabel MUST behave identically to normalizeHeading in
// actions/suggestion-actions.ts. It drifted once already — a stray whitespace
// collapse on the client would have placed a claim inline that the server then
// appended somewhere else, so the doctor reviews it in one place and signs it
// in another. A comment cannot stop that happening again.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  emChangeEq,
  normalizeSectionLabel,
  sectionLabelForClaim,
} from '../suggestion-labels';

/** Verbatim copy of the server's rule (suggestion-actions.ts). If this test
 *  ever needs editing to pass, the two have diverged — that IS the finding. */
const serverNormalizeHeading = (s: string): string =>
  s.replace(/\*\*/g, '').replace(/:\s*$/, '').trim().toLowerCase();

describe('normaliser parity with the adopt action', () => {
  it.each([
    'Findings',
    '**Findings**',
    'Findings:',
    '**Findings:**',
    '  Assessment  ',
    'PLAN',
    'Right   Leg',          // internal double space — the exact drift case
    'Diameter and Reflux Time — ** Right Leg **',
    '',
  ])('%j normalises identically on both sides', (input) => {
    expect(normalizeSectionLabel(input)).toBe(serverNormalizeHeading(input));
  });
});

describe('a claim under a ### sub-heading finds its owning section', () => {
  const sections = [
    { label: 'FINDINGS', body: '### Right\nGSV incompetent.\n\n### Left\nNormal.' },
    { label: 'IMPRESSION', body: 'Bilateral GSV incompetence.' },
  ];

  it('matches a top-level heading directly', () => {
    expect(sectionLabelForClaim('IMPRESSION', sections)).toBe('impression');
  });

  it('resolves a ### sub-heading to the section that owns it', () => {
    // The ultrasound template, live in prod: the verifier tags the claim
    // "Right", the client's parser folds ### into the parent body.
    expect(sectionLabelForClaim('Right', sections)).toBe('findings');
    expect(sectionLabelForClaim('Left', sections)).toBe('findings');
  });

  it('returns null when nothing owns it, so the claim is shown as an orphan', () => {
    expect(sectionLabelForClaim('Nowhere', sections)).toBeNull();
  });
});

describe('emChangeEq', () => {
  it('compares by value, not identity', () => {
    expect(emChangeEq({ from: '99213', to: '99214' }, { from: '99213', to: '99214' })).toBe(true);
    expect(emChangeEq({ from: '99213', to: '99214' }, { from: '99213', to: '99215' })).toBe(false);
    expect(emChangeEq(null, null)).toBe(true);
    expect(emChangeEq(null, { from: '99213', to: '99214' })).toBe(false);
  });
});
