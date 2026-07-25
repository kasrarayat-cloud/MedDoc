// ============================================================================
// FIELD_NEEDS_CLINICIAN_INPUT — blocking at VISIT time, attested at CERT time.
// ----------------------------------------------------------------------------
// Certification asks "does this template fill correctly from evidence?", not
// "did a clinician answer every prompt?". A field the resolver deliberately
// refuses to infer (an enumerated DIAGNOSIS) is behaving correctly and stays
// BLANK either way — so at certification it is attested as a blank rather than
// blocking. At visit time the question really is whether the clinician
// answered, so the severity is unchanged.
//
// Both directions pinned: a one-sided test would let the visit-time guarantee
// be quietly downgraded later.
// ============================================================================

import { describe, expect, it } from 'vitest';

const read = () => {
  const { readFileSync } = require('node:fs') as typeof import('node:fs');
  const { join } = require('node:path') as typeof import('node:path');
  return readFileSync(join(__dirname, '..', 'validation', 'index.ts'), 'utf-8');
};

describe('needs-clinician-input severity', () => {
  it('is scoped by the certification-only flag, not removed', () => {
    const src = read();
    expect(src).toContain('needsInputBlocks');
    expect(src).toMatch(/!input\.allowUncertifiedForSyntheticTest\s*&&/);
  });

  it('still BLOCKS at visit time for a material or required field', () => {
    const src = read();
    // The visit-time predicate must still consider criticality/required.
    expect(src).toMatch(/needsInputBlocks\s*=\s*\n?\s*!input\.allowUncertifiedForSyntheticTest\s*&&\s*\n?\s*\(critical \|\| field\.required \|\| mapping\.required\)/);
  });

  it('does not touch the neighbouring conflict/ambiguous rules', () => {
    const src = read();
    // FIELD_CONFLICT stays unconditionally blocking.
    expect(src).toMatch(/add\('FIELD_CONFLICT', 'blocking'/);
    // FIELD_AMBIGUOUS keeps its original predicate.
    expect(src).toMatch(/add\('FIELD_AMBIGUOUS', critical \|\| field\.required \|\| mapping\.required \? 'blocking' : 'warning'/);
  });
});
