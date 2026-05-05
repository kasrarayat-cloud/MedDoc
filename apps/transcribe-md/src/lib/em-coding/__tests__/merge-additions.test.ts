// ============================================================================
// merge-additions.test.ts — Phase 5.2 stub completion guard.
// ----------------------------------------------------------------------------
// Asserts that the BumpModal's per-criterion additions land in the
// right SOAP section under the right sub-heading, and that pathological
// inputs (empty text, unknown criterion id, missing sub-heading) don't
// silently lose the doctor's content.
// ============================================================================

import { describe, it, expect } from 'vitest';

import { mergeAdditions } from '../merge-additions';

const SOAP = `## Subjective
**Chief Complaint:** Sore throat × 3 days

**HPI:** Per patient, sore throat began Monday, worse with swallowing.

**ROS:** Constitutional: denies fever.

## Objective
Throat: erythema. No exudate.

## Assessment
Pharyngitis, likely viral.

## Plan
1. Symptomatic care, hydration.
2. Return if worsens.`;

describe('mergeAdditions — per-criterion section targeting', () => {
  it('inserts an HPI addition directly under the **HPI:** sub-heading', () => {
    const result = mergeAdditions(SOAP, [
      {
        criterionId: 'hpi.elements',
        text: 'Severity 5/10. Worse with deep breathing.',
      },
    ]);
    // Addition lands inside Subjective, immediately after **HPI:**.
    const hpiBlock = result.newSoap.match(
      /\*\*HPI:\*\*\n([\s\S]+?)(?=\n\*\*ROS:\*\*|\n\n##|$)/
    );
    expect(hpiBlock).not.toBeNull();
    expect(hpiBlock![1]).toContain('Severity 5/10');
    // Original HPI prose is preserved.
    expect(result.newSoap).toContain('sore throat began Monday');
    expect(result.applied).toHaveLength(1);
    expect(result.skipped).toHaveLength(0);
  });

  it('inserts a ROS addition under **ROS:**', () => {
    const result = mergeAdditions(SOAP, [
      { criterionId: 'ros.systems', text: 'GI: denies nausea, vomiting.' },
    ]);
    expect(result.newSoap).toContain('GI: denies nausea, vomiting.');
    // Lands inside Subjective, after the ROS sub-heading.
    const subj = result.newSoap.match(
      /## Subjective[\s\S]+?(?=## Objective)/
    );
    expect(subj![0]).toContain('GI: denies nausea, vomiting.');
  });

  it('appends an exam addition to the Objective section root', () => {
    const result = mergeAdditions(SOAP, [
      {
        criterionId: 'exam.systems',
        text: 'Cardiovascular: regular rate and rhythm, no murmurs.',
      },
    ]);
    const obj = result.newSoap.match(/## Objective[\s\S]+?(?=## Assessment)/);
    expect(obj![0]).toContain('Cardiovascular: regular rate and rhythm');
  });

  it('appends an MDM-data addition to the Plan section', () => {
    const result = mergeAdditions(SOAP, [
      {
        criterionId: 'mdm.data',
        text: 'Reviewed last A1c (6.8 → 6.4).',
      },
    ]);
    const plan = result.newSoap.match(/## Plan[\s\S]+$/);
    expect(plan![0]).toContain('Reviewed last A1c');
  });

  it('skips empty or whitespace-only additions silently', () => {
    const result = mergeAdditions(SOAP, [
      { criterionId: 'hpi.elements', text: '' },
      { criterionId: 'ros.systems', text: '   \n\n  ' },
    ]);
    expect(result.applied).toHaveLength(0);
    expect(result.skipped).toHaveLength(2);
    expect(result.skipped[0].reason).toBe('empty text');
    // SOAP is unchanged (modulo whitespace normalization on rejoin).
    expect(result.newSoap).toContain('sore throat began Monday');
  });

  it('appends a labeled bullet for an unrecognised criterion id', () => {
    const result = mergeAdditions(SOAP, [
      {
        criterionId: 'gap.99',
        text: 'Some text the engine produced an unmapped id for.',
      },
    ]);
    expect(result.applied).toHaveLength(1);
    expect(result.skipped).toHaveLength(0);
    // Lands in Plan as a labeled bullet.
    const plan = result.newSoap.match(/## Plan[\s\S]+$/);
    expect(plan![0]).toContain('(unrecognised criterion gap.99)');
  });

  it('handles multiple additions across different sections in one call', () => {
    const result = mergeAdditions(SOAP, [
      { criterionId: 'hpi.elements', text: 'Onset: gradual.' },
      { criterionId: 'ros.systems', text: 'GU: denies dysuria.' },
      { criterionId: 'exam.systems', text: 'Lungs: clear bilaterally.' },
    ]);
    expect(result.applied).toHaveLength(3);
    expect(result.newSoap).toContain('Onset: gradual.');
    expect(result.newSoap).toContain('GU: denies dysuria.');
    expect(result.newSoap).toContain('Lungs: clear bilaterally.');
  });

  it('appends sub-heading + text when the target sub-heading is missing', () => {
    const soapNoRos = `## Subjective
**HPI:** Patient reports headache.

## Objective
Vitals stable.

## Assessment
Tension headache.

## Plan
1. NSAIDs.`;
    const result = mergeAdditions(soapNoRos, [
      { criterionId: 'ros.systems', text: 'Constitutional: denies fever.' },
    ]);
    // The **ROS:** sub-heading didn't exist — addition lands at the
    // bottom of Subjective WITH the sub-heading prepended so the
    // attribution is preserved.
    expect(result.newSoap).toContain('**ROS:**');
    expect(result.newSoap).toContain('Constitutional: denies fever.');
  });

  it('preserves preamble content (anything before ## Subjective)', () => {
    const soapWithPreamble = `> **NOTE:** This is an annotated draft.

## Subjective
HPI text.

## Objective

## Assessment

## Plan`;
    const result = mergeAdditions(soapWithPreamble, [
      { criterionId: 'hpi.elements', text: 'Onset 2 days ago.' },
    ]);
    expect(result.newSoap).toContain('**NOTE:** This is an annotated draft.');
  });

  it('returns the original SOAP scaffold even when no additions are applied', () => {
    const result = mergeAdditions(SOAP, []);
    expect(result.applied).toHaveLength(0);
    // All four canonical headings still present.
    expect(result.newSoap).toContain('## Subjective');
    expect(result.newSoap).toContain('## Objective');
    expect(result.newSoap).toContain('## Assessment');
    expect(result.newSoap).toContain('## Plan');
  });
});
