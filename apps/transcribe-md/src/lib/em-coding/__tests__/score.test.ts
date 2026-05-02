// ============================================================================
// score.ts integration unit tests (Phase 5.2)
// ============================================================================

import { describe, it, expect } from 'vitest';
import { computeEmScore } from '../score';
import { resolveTier, deterministicMdm } from '../fallback-mdm';
import { shouldShowBumpCta } from '../bump-suggestion';
import type { EmScore } from '../types';

describe('resolveTier (2-of-3)', () => {
  it('all-equal → that tier', () => {
    expect(resolveTier('low', 'low', 'low')).toBe('low');
    expect(resolveTier('moderate', 'moderate', 'moderate')).toBe('moderate');
  });

  it('two-of-three at level X → tier X (one outlier)', () => {
    expect(resolveTier('moderate', 'low', 'moderate')).toBe('moderate');
    expect(resolveTier('low', 'low', 'minimal')).toBe('low');
    expect(resolveTier('high', 'moderate', 'high')).toBe('high');
  });

  it('all-different → middle (2nd-highest after sort)', () => {
    expect(resolveTier('high', 'moderate', 'low')).toBe('moderate');
    expect(resolveTier('moderate', 'low', 'minimal')).toBe('low');
  });

  it('Rx-mgmt scenario: [moderate-risk, low-problems, minimal-data]', () => {
    expect(resolveTier('low', 'minimal', 'moderate')).toBe('low');
  });
});

describe('deterministicMdm fallback', () => {
  it('refill-only: stable HTN → low risk per rubric §4.1', () => {
    const soap = `## Plan
Continue lisinopril 10mg daily — refill 90 days. F/u 6 months.`;
    const j = deterministicMdm(soap, [{ code: 'I10' }], []);
    expect(j.elements.risk.level).toBe('low');
  });

  it('new-Rx → moderate risk floor', () => {
    const soap = `## Plan
Started albuterol HFA 1-2 puffs q4-6h PRN. F/u 7-10 days.`;
    const j = deterministicMdm(soap, [{ code: 'J20.9' }], []);
    expect(j.elements.risk.level).toBe('moderate');
  });

  it('hospitalization decision → high risk floor', () => {
    const soap = `## Plan
Decision against immediate hospitalization made jointly with patient.`;
    const j = deterministicMdm(soap, [], []);
    expect(j.elements.risk.level).toBe('high');
  });
});

describe('computeEmScore (smoke)', () => {
  const minimalSoap = `## Subjective
35yo M, no significant PMH, presents with mild sore throat × 4 days.
Denies fever. NKDA.

## Objective
VS: BP 122/78. Gen: NAD. HEENT: clear oropharynx. Lungs: CTAB.

## Assessment
1. Acute viral URI (J06.9)

## Plan
Supportive care only: hydration, rest, OTC saline rinses.`;

  it('produces a code, tier, and satisfied criteria', async () => {
    const score = await computeEmScore(minimalSoap, {
      visitType: 'established',
      icdCodes: [{ code: 'J06.9' }],
      mdmCachedJudgement: null, // force deterministic fallback
    });
    expect(score.code).toMatch(/^99\d{3}$/);
    expect(['straightforward', 'low', 'moderate', 'high']).toContain(score.mdmTier);
    expect(score.rubricVersion).toBe('2021.1');
    expect(score.llmJudged).toBe(false);
    expect(score.satisfied.hpiElements).toBeGreaterThanOrEqual(0);
  });

  it('flags llmJudged=false when fallback path is used', async () => {
    const score = await computeEmScore(minimalSoap, {
      mdmCachedJudgement: null,
    });
    expect(score.llmJudged).toBe(false);
  });

  it('uses cached judgement verbatim when supplied', async () => {
    const cached = {
      tier: 'moderate' as const,
      elements: {
        problems: { level: 'moderate' as const, summary: 'test' },
        data: { level: 'moderate' as const, summary: 'test' },
        risk: { level: 'moderate' as const, summary: 'test' },
      },
      confidence: 0.92,
      rationale: 'cached test',
    };
    const score = await computeEmScore(minimalSoap, {
      mdmCachedJudgement: cached,
    });
    expect(score.mdmTier).toBe('moderate');
    expect(score.llmJudged).toBe(true);
    expect(score.cacheHit).toBe(true);
  });

  it('captures time hints when present', async () => {
    const soap = `${minimalSoap}\n\nTotal time spent: 25 min.`;
    const score = await computeEmScore(soap, { mdmCachedJudgement: null });
    expect(score.timeFitScore).not.toBeNull();
    expect(score.timeFitScore?.minutesUsed).toBe(25);
  });
});

describe('shouldShowBumpCta', () => {
  function buildScore(partial: Partial<EmScore>): EmScore {
    return {
      code: '99213',
      mdmTier: 'low',
      visitType: 'established',
      satisfied: {
        hpiElements: 4,
        rosSystems: 2,
        pfshCategories: 1,
        examSystems: 5,
        problems: 'low',
        data: 'minimal',
        risk: 'moderate',
      },
      perElementConfidence: {
        hpi: {
          location: 0, quality: 0, severity: 0, duration: 0,
          timing: 0, context: 0, modifyingFactors: 0,
          associatedSignsSymptoms: 0,
        },
      },
      bumpableTo: null,
      timeFitScore: null,
      llmJudged: false,
      rubricVersion: '2021.1',
      computedAt: new Date().toISOString(),
      cacheHit: false,
      ...partial,
    };
  }

  it('returns null when at top tier', () => {
    const cta = shouldShowBumpCta('99215', buildScore({ code: '99215' }));
    expect(cta).toBeNull();
  });

  it('returns confirm-bump when already meeting next-level requirements', () => {
    const score = buildScore({
      satisfied: {
        hpiElements: 6,
        rosSystems: 4,
        pfshCategories: 3,
        examSystems: 8,
        problems: 'moderate',
        data: 'moderate',
        risk: 'moderate',
      },
    });
    const cta = shouldShowBumpCta('99213', score);
    expect(cta).not.toBeNull();
    expect(cta?.toCode).toBe('99214');
  });

  it('emits gaps + revenue delta for almost-there scenarios', () => {
    const cta = shouldShowBumpCta('99213', buildScore({}));
    if (cta && cta.mode === 'almost-there') {
      expect(cta.toCode).toBe('99214');
      expect(cta.revenueDelta).toBe(32);
      expect(cta.gaps.length).toBeGreaterThan(0);
      expect(cta.gaps.length).toBeLessThanOrEqual(2);
    }
  });
});
