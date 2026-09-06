// ============================================================================
// GATE — the generator's EDITION table, and its refusal to run unpinned
// ----------------------------------------------------------------------------
// FY2027 takes effect 2026-10-01. The generator is parameterised by fiscal year
// so that ingestion is adding a row rather than editing a constant — and the
// SAFETY property is the REFUSAL: an edition whose bytes have not been pinned
// must abort, not run against whatever the network happens to return.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL:
//   · a year-derived URL replacing the literal per-edition one -> the URL block
//   · fy2027 acquiring guessed digests or counts               -> the unpinned block
//   · the shipped data drifting from fy2026's pinned digests   -> the identity block
//   · the edition table losing fy2027 before it is ingested    -> the presence block
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, it, expect } from 'vitest';
import PROVENANCE from '../data/icd10cm-fy2026-provenance.json';

const GENERATOR = readFileSync(
  join(__dirname, '..', '..', '..', '..', 'scripts', 'data', 'build-icd10cm.mjs'),
  'utf8',
);

describe('the generator is parameterised by fiscal year', () => {
  it('carries an EDITIONS table with both fy2026 and fy2027', () => {
    expect(GENERATOR).toMatch(/const EDITIONS = \{/);
    expect(GENERATOR).toMatch(/\bfy2026:\s*\{/);
    expect(GENERATOR).toMatch(/\bfy2027:\s*\{/);
    expect(GENERATOR).toMatch(/--edition/);
  });

  it('⚠️ each edition carries a LITERAL url — none is built from the year', () => {
    // Measured 2026-09-04: CMS dropped "and-" from the code-tables filename
    // between FY2026 and FY2027, so a year-substituting helper 404s in the year
    // it matters. Both literals must be present, and no template-built URL.
    expect(GENERATOR).toContain('2026-code-descriptions-tabular-order.zip');
    expect(GENERATOR).toContain('2027-code-descriptions-tabular-order.zip');
    // no `${year}` interpolation anywhere in a cms.gov path
    expect(GENERATOR).not.toMatch(/cms\.gov[^\n'"`]*\$\{/);
  });

  it('⚠️ fy2027 is UNPINNED, and the generator refuses it', () => {
    // The block must both exist and be null-valued. If somebody guesses digits
    // in here, this fails — which is the point: provenance is pinned from an
    // archive somebody actually downloaded, never forward-filled.
    const fy27 = GENERATOR.slice(GENERATOR.indexOf('fy2027: {'));
    const body = fy27.slice(0, fy27.indexOf('\n  },'));
    for (const field of ['retrieved', 'zipSha256', 'zipBytes', 'codesSha256', 'orderSha256']) {
      expect(body, `${field} must still be null for fy2027`).toMatch(
        new RegExp(`${field}:\\s*null`),
      );
    }
    expect(body).toMatch(/expect:\s*null/);
    // and the refusal exists, naming what to do
    expect(GENERATOR).toMatch(/has no pinned \$\{?field\}?|has no pinned/);
    expect(GENERATOR).toMatch(/Provenance is pinned BEFORE the act/);
  });

  it('fy2027 still records what IS knowable — url and effective window', () => {
    const fy27 = GENERATOR.slice(GENERATOR.indexOf('fy2027: {'));
    const body = fy27.slice(0, fy27.indexOf('\n  },'));
    expect(body).toContain("effectiveFrom: '2026-10-01'");
    expect(body).toContain("effectiveTo: '2027-09-30'");
    expect(body).toContain('2027-code-descriptions-tabular-order.zip');
  });

  it('the SHIPPED data is still fy2026, and its digests are unmoved', () => {
    // Parameterising must not have altered a single code. The payload digests
    // are the ones T8 pinned; a banner change is fine, a payload change is not.
    expect(PROVENANCE.effectiveFrom).toBe('2025-10-01');
    expect(PROVENANCE.effectiveTo).toBe('2026-09-30');
    expect(PROVENANCE.payloadSha256.billable).toBe(
      'def6594909779f92e8974b8441e72d04afa57acd1bdcc5fb3739d1dd0149a939',
    );
    expect(PROVENANCE.payloadSha256.headers).toBe(
      '3b2b5c0711884186706ada712e5bf86702a6570602b01fbc80cf8b85c3e12101',
    );
    expect(PROVENANCE.counts).toEqual({ billable: 74719, headers: 23467, total: 98186 });
  });

  it('the April/October cadence is recorded, with FY2026 as a fact not a rule', () => {
    expect(GENERATOR).toMatch(/APRIL 1 mid-year update|april/i);
    // the measured FY2026 result must be labelled as edition-specific
    expect(GENERATOR).toMatch(/fact about FY2026, NOT a rule|NOT a rule/);
  });
});
