// ============================================================================
// validateSoapStructure — FIND-P1-015 + FIND-P1-016 unit tests
// ----------------------------------------------------------------------------
// Pins the lenient validator contract used by L4 (SOAP generation) and
// L6 (polish). The validator catches obvious failures (empty / JSON /
// missing sections) without locking the prompt into a specific
// header-formatting style.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { validateSoapStructure } from '../soap-structure-validator';

/** A canonical well-shaped SOAP body the validator should accept. */
const VALID_SOAP = `## Subjective
**Chief Complaint:** Headache for 3 days.
**HPI:** Patient reports throbbing pain.

## Objective
Vitals: BP 120/80. HEENT: normal.

## Assessment
Tension-type headache, primary care manageable.

## Plan
1. Trial ibuprofen 400 mg PRN
2. Return if symptoms worsen`;

describe('validateSoapStructure — happy path', () => {
  it('accepts the canonical L4 markdown shape', () => {
    const result = validateSoapStructure(VALID_SOAP);
    expect(result.ok).toBe(true);
    expect(result.reason).toBe(null);
    expect(result.missingSections).toEqual([]);
    expect(result.outputLength).toBeGreaterThan(50);
  });

  it('accepts mixed-case section headers (## subjective etc.)', () => {
    const lower = `## subjective\nAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n## objective\nBBBBBBBBBBBBBBBBBB\n## assessment\nCCCCCCCCCCCCCCCCCC\n## plan\nDDDDDDDDDDDDDDD`;
    const result = validateSoapStructure(lower);
    expect(result.ok).toBe(true);
  });

  it('accepts SHOUTY-CASE headers', () => {
    const shouty = `## SUBJECTIVE\nAAAAAAAAAAAAAAAAAAAAAAAAAAA\n## OBJECTIVE\nBBBBBBBBBBBBBBBBBB\n## ASSESSMENT\nCCCCCCCCCCCCC\n## PLAN\nDDDDDDDDDDDDDDDD`;
    const result = validateSoapStructure(shouty);
    expect(result.ok).toBe(true);
  });

  it('accepts variable whitespace between ## and section name', () => {
    const spacy = `##  Subjective\nXXXXXXXXXXXXXXXXXXXXXXXX\n##\tObjective\nYYYYYYYYYYYYYYYYYYYYY\n##   Assessment\nZZZZZZZZZZZZZZZZZ\n## Plan\nQQQQQQQQQQQQQQ`;
    const result = validateSoapStructure(spacy);
    expect(result.ok).toBe(true);
  });

  it('accepts a body with extra content between sections', () => {
    const padded = `# Visit note prelude

## Subjective
Some content here.

Extra paragraph between sections.

## Objective
Exam findings.

## Assessment
Clinical thinking.

## Plan
1. First step.

Closing remarks.`;
    const result = validateSoapStructure(padded);
    expect(result.ok).toBe(true);
  });

  it('reports the actual outputLength on the happy path', () => {
    const result = validateSoapStructure(VALID_SOAP);
    expect(result.outputLength).toBe(VALID_SOAP.trim().length);
  });
});

describe('validateSoapStructure — empty / near-empty failures', () => {
  it('rejects empty string', () => {
    const result = validateSoapStructure('');
    expect(result.ok).toBe(false);
    expect(result.reason).toBe('empty output');
    expect(result.outputLength).toBe(0);
  });

  it('rejects whitespace-only string', () => {
    const result = validateSoapStructure('   \n\t  \n  ');
    expect(result.ok).toBe(false);
    expect(result.reason).toBe('empty output');
    expect(result.outputLength).toBe(0);
  });

  it('rejects null/undefined input without throwing', () => {
    expect(() => validateSoapStructure(null)).not.toThrow();
    expect(() => validateSoapStructure(undefined)).not.toThrow();
    const nullResult = validateSoapStructure(null);
    expect(nullResult.ok).toBe(false);
    expect(nullResult.reason).toBe('empty output');
  });

  it('rejects short output (<50 chars) even if it has all section names', () => {
    // "## Subjective ## Objective ## Assessment ## Plan" is exactly
    // 48 chars — fails the min-length gate before the section check.
    const tooShort = '## Subjective ## Objective ## Assessment ## Plan';
    const result = validateSoapStructure(tooShort);
    expect(result.ok).toBe(false);
    expect(result.reason).toMatch(/output too short/);
    expect(result.outputLength).toBe(tooShort.length);
  });
});

describe('validateSoapStructure — JSON-shape rejection', () => {
  it('rejects {...} JSON-object envelope', () => {
    const json = JSON.stringify({
      soap: 'irrelevant',
      filler: 'x'.repeat(500),
    });
    const result = validateSoapStructure(json);
    expect(result.ok).toBe(false);
    expect(result.reason).toBe('output is JSON-shaped, expected markdown');
  });

  it('rejects [...] JSON-array envelope', () => {
    const json = '[' + '"' + 'x'.repeat(500) + '"]';
    const result = validateSoapStructure(json);
    expect(result.ok).toBe(false);
    expect(result.reason).toBe('output is JSON-shaped, expected markdown');
  });

  it('does NOT reject markdown that happens to contain { ... } inline', () => {
    const md = `## Subjective\nPer patient, "feels like {tightness}" in chest.\n\n## Objective\nVitals stable.\n\n## Assessment\nAtypical chest pain — workup pending.\n\n## Plan\n1. EKG\n2. Trop`;
    const result = validateSoapStructure(md);
    // Doesn't start AND end with braces → not JSON-shape.
    expect(result.ok).toBe(true);
  });
});

describe('validateSoapStructure — missing-section failures', () => {
  it('rejects markdown missing Plan', () => {
    const noPlan = `## Subjective\nLong subjective content here that exceeds the min length threshold easily without any issue.\n\n## Objective\nExam findings noted.\n\n## Assessment\nClinical reasoning.`;
    const result = validateSoapStructure(noPlan);
    expect(result.ok).toBe(false);
    expect(result.reason).toMatch(/missing SOAP sections: Plan/);
    expect(result.missingSections).toEqual(['Plan']);
  });

  it('rejects markdown missing Assessment AND Plan', () => {
    const noAP = `## Subjective\nLong subjective content here that exceeds the min length threshold easily.\n\n## Objective\nExam findings noted.`;
    const result = validateSoapStructure(noAP);
    expect(result.ok).toBe(false);
    expect(result.reason).toMatch(/missing SOAP sections: Assessment, Plan/);
    expect(result.missingSections).toEqual(['Assessment', 'Plan']);
  });

  it('rejects markdown with all 4 missing (long enough to pass min-length but wrong shape)', () => {
    const wrongShape = '## Symptoms\n' + 'narrative content '.repeat(20);
    const result = validateSoapStructure(wrongShape);
    expect(result.ok).toBe(false);
    expect(result.missingSections).toEqual([
      'Subjective',
      'Objective',
      'Assessment',
      'Plan',
    ]);
  });

  it('does NOT match partial-word sections (e.g., "## Subjective findings" stays as Subjective)', () => {
    // The validator's `\b` word boundary on the section name means
    // `## Subjective findings present in HPI` correctly matches as
    // Subjective. Pin this so a future regex tightening doesn't
    // accidentally reject legitimate output that happens to put
    // descriptive text after the section header on the same line.
    const expanded = `## Subjective findings:\nNarrative here, long enough to clear the min-length gate.\n\n## Objective\nExam.\n\n## Assessment\nThinking.\n\n## Plan\nNext steps.`;
    const result = validateSoapStructure(expanded);
    expect(result.ok).toBe(true);
  });

  it('rejects markdown with a similar-but-not-matching header (e.g., "## Plan-of-care" should not match "Plan" due to word boundary)', () => {
    // Word boundary means "Plan-" still matches "Plan" because `-`
    // is a word boundary char. Document the current behavior so a
    // future tightening to require explicit space/newline after
    // the name is a deliberate choice.
    const planHyphen = `## Subjective\nLong narrative content that satisfies the min length threshold.\n\n## Objective\nExam.\n\n## Assessment\nClinical thinking.\n\n## Plan-of-care\nNext steps.`;
    const result = validateSoapStructure(planHyphen);
    // Plan matches "Plan-of-care" via the word boundary — passes.
    expect(result.ok).toBe(true);
  });
});

describe('validateSoapStructure — fail-class ordering / never-throws', () => {
  it('empty-output check fires before section check', () => {
    const result = validateSoapStructure('');
    expect(result.reason).toBe('empty output');
  });

  it('too-short check fires before section check', () => {
    const result = validateSoapStructure('## Subjective ## Objective ## Assessment ## Plan');
    expect(result.reason).toMatch(/output too short/);
  });

  it('JSON-shape check fires before section check', () => {
    // JSON body with all 4 section names inside — still rejected as JSON.
    const trickyJson = '{"## Subjective": "x".repeat(50), "## Objective": "y", "## Assessment": "z", "## Plan": "q"}';
    const result = validateSoapStructure(trickyJson);
    expect(result.ok).toBe(false);
    expect(result.reason).toBe('output is JSON-shaped, expected markdown');
  });

  it('never throws on adversarial input', () => {
    expect(() => validateSoapStructure('\\x00\\xff')).not.toThrow();
    expect(() => validateSoapStructure('💀'.repeat(100))).not.toThrow();
    expect(() => validateSoapStructure('a'.repeat(1_000_000))).not.toThrow();
  });
});
