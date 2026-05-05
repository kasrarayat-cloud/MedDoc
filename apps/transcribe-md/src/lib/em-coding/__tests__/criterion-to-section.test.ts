// ============================================================================
// criterion-to-section.test.ts — Phase 5.2 stub completion
// ----------------------------------------------------------------------------
// Asserts the gap-label-prefix → criterion-id mapping that flows from
// the engine's free-text bumpGaps into the BumpModal's editable
// suggestion list. This is the contract that lets the apply-additions
// route route each addition to the right SOAP section.
// ============================================================================

import { describe, it, expect } from 'vitest';

import {
  criterionIdForGapLabel,
  sectionTargetFor,
  suggestionForCriterionId,
} from '../criterion-to-section';

describe('criterionIdForGapLabel', () => {
  it('maps "HPI: 3 of 4 elements" → hpi.elements', () => {
    expect(criterionIdForGapLabel('HPI: 3 of 4 elements')).toBe(
      'hpi.elements'
    );
  });

  it('maps "ROS: 1 of 2 systems" → ros.systems', () => {
    expect(criterionIdForGapLabel('ROS: 1 of 2 systems')).toBe('ros.systems');
  });

  it('maps "PFSH: 0 of 2 categories" → pfsh.categories', () => {
    expect(criterionIdForGapLabel('PFSH: 0 of 2 categories')).toBe(
      'pfsh.categories'
    );
  });

  it('maps "Exam: 1 of 5 systems" → exam.systems', () => {
    expect(criterionIdForGapLabel('Exam: 1 of 5 systems')).toBe(
      'exam.systems'
    );
  });

  it('maps "MDM: 1 more element(s) at moderate+" → mdm.problems', () => {
    expect(
      criterionIdForGapLabel('MDM: 1 more element(s) at moderate+')
    ).toBe('mdm.problems');
  });

  it('returns "unknown" for unrecognised label shapes', () => {
    expect(criterionIdForGapLabel('Some unrelated string')).toBe('unknown');
  });
});

describe('sectionTargetFor', () => {
  it('maps hpi.elements → Subjective with **HPI:** sub-heading', () => {
    expect(sectionTargetFor('hpi.elements')).toEqual({
      section: 'S',
      subHeading: '**HPI:**',
      humanLabel: 'HPI element',
    });
  });

  it('maps exam.systems → Objective with no sub-heading (root append)', () => {
    expect(sectionTargetFor('exam.systems')).toEqual({
      section: 'O',
      subHeading: null,
      humanLabel: 'exam system',
    });
  });

  it('maps mdm.data → Plan section', () => {
    const t = sectionTargetFor('mdm.data');
    expect(t!.section).toBe('P');
  });

  it('returns null for unknown id (caller treats as Plan-fallback)', () => {
    expect(sectionTargetFor('totally.bogus.id')).toBeNull();
  });
});

describe('suggestionForCriterionId', () => {
  it('returns a known suggestion for hpi.elements', () => {
    expect(suggestionForCriterionId('hpi.elements')).toContain('Severity');
  });

  it('returns a sane fallback for unknown ids', () => {
    expect(suggestionForCriterionId('nope')).toContain('documentation');
  });
});
