// ============================================================================
// STAGE 4 — one vocabulary, both sides.
// ----------------------------------------------------------------------------
// The proposer invented a concept per field (test.venous_duplex.gsv_sfj_diameter).
// L3 never emits strings like that, and factSatisfiesMapping demands the fact's
// concept BE the mapping's concept or an approved synonym — so no fact could
// match any cell, permanently. That is how filledCount=0 survived four sessions
// of downstream fixes.
//
// Intersection is now true BY CONSTRUCTION rather than by loosening anything:
// the proposer may only select concepts the extractor actually emits.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { isRegisteredConcept, synonymsFor, REGISTRY_CONCEPTS } from '../concept-registry';

describe('registry membership', () => {
  it('accepts every concept observed in a real extraction run', () => {
    // Verbatim from the vocabulary dump.
    for (const c of [
      'measurement.diameter',
      'measurement.reflux_time',
      'assessment',
      'exam.vascular',
      'test.name',
      'test.bilateral_lower_extremity_venous_duplex_reflux_study.result',
    ]) {
      expect(isRegisteredConcept(c), `${c} should be registered`).toBe(true);
    }
  });

  it('REJECTS the invented per-field concepts that caused the outage', () => {
    for (const c of [
      'test.venous_duplex.gsv_sfj_diameter',
      'test.venous_duplex.gsv_sfj_reflux_time',
      'test.venous_duplex.gsv_sfj.reflux_time_ms',
    ]) {
      expect(isRegisteredConcept(c), `${c} must NOT be registered`).toBe(false);
    }
  });

  it('holds no anatomy in any concept — anatomy is fact data', () => {
    // One concept serves twenty-six template rows precisely because it does not
    // name a vein. If this ever fails, the outage is being recreated.
    for (const c of REGISTRY_CONCEPTS) {
      expect(c, `${c} bakes anatomy into a concept`).not.toMatch(
        /gsv|ssv|aagsv|pagsv|sfj|spj|thigh|knee|calf/,
      );
    }
  });

  it('supplies synonyms from the registry, not the model', () => {
    expect(synonymsFor('measurement.reflux_time')).toContain('measurement.reflux');
    expect(synonymsFor('measurement.diameter').length).toBeGreaterThan(0);
    expect(synonymsFor('not.a.concept')).toEqual([]);
  });
});

describe('proposer wiring', () => {
  const src = () => {
    const { readFileSync } = require('node:fs') as typeof import('node:fs');
    const { join } = require('node:path') as typeof import('node:path');
    return readFileSync(join(__dirname, '..', 'semantic-mapping', 'index.ts'), 'utf-8');
  };

  it('nulls an off-registry concept instead of persisting it', () => {
    expect(src()).toMatch(/isRegisteredConcept\(mapping\.clinicalConcept\)\s*\n?\s*\?\s*mapping\.clinicalConcept\s*\n?\s*:\s*null/);
  });

  it('an off-registry mapping cannot come back as recognised', () => {
    expect(src()).toMatch(/!isRegisteredConcept\(mapping\.clinicalConcept\) \|\|/);
  });

  it('reports off-registry proposals visibly at PROPOSAL time', () => {
    // Not discovered later at certification, where it looked like missing evidence.
    expect(src()).toContain('off-registry or unconcepted');
  });
});
