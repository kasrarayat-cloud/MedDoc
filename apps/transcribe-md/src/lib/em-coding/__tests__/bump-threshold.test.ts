// ============================================================================
// Regression guard — bump CTA must surface on text_notes / voice_dictation
// visits whose deterministic counters land lower than transcribed audio.
//
// Pre-2026-05-12 the threshold was hardcoded `gaps.length <= 2` in both
// bump-suggestion.ts and score.ts, which:
//   • worked for audio_upload because Deepgram-transcribed SOAPs are
//     word-for-word and naturally hit the 4-element HPI floor;
//   • silently dropped the bump CTA for text_notes / voice_dictation
//     where doctors write concise notes that satisfy 99214 outright but
//     show 3+ gaps to 99215.
// 30-day audit-log evidence: 0 EM_BUMP_APPLIED rows across 9 text_notes
// + 4 voice_dictation visits vs 12 / 35 for audio_upload — confirming
// the threshold was acting as an unintended input-mode filter.
// Raised to 4 so the gap list surfaces and doctors can act on it.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { computeEmScore } from '../score';
import { shouldShowBumpCta } from '../bump-suggestion';
import type { EmScore } from '../types';

describe('Bump CTA threshold (regression — text_notes / dictation parity)', () => {
  // The exact satisfied shape observed on a real text_notes visit
  // (cmp202acm00003aqxl2os7h9r) running the deterministic path: 99214
  // tier with HPI/PFSH met but ROS / Exam / MDM short of 99215.
  const TEXT_NOTES_PROFILE: EmScore = {
    code: '99214',
    visitType: 'established',
    mdmTier: 'moderate',
    satisfied: {
      hpiElements: 4,
      rosSystems: 3,        // 99215 requires 10 (complete ROS)
      pfshCategories: 3,
      examSystems: 2,       // 99215 requires 8 systems
      problems: 'moderate',
      data: 'minimal',
      risk: 'moderate',
    },
    perElementConfidence: {
      hpi: {
        location: 0.9,
        quality: 0.9,
        severity: 0.9,
        duration: 0.9,
        timing: 0.9,
        context: 0.9,
        modifyingFactors: 0.9,
        associatedSignsSymptoms: 0.9,
      },
    },
    bumpableTo: null,
    timeFitScore: null,
    llmJudged: false,
    rubricVersion: '2021.1',
    computedAt: new Date().toISOString(),
    cacheHit: false,
    mdmRationale: 'test',
    mdmConfidence: 0.75,
  };

  it('surfaces an almost-there CTA on 99214 → 99215 even with 3 gaps', () => {
    const result = shouldShowBumpCta('99214', TEXT_NOTES_PROFILE);
    expect(result).not.toBeNull();
    expect(result?.mode).toBe('almost-there');
    expect(result?.toCode).toBe('99215');
    expect(result?.gaps.length).toBeGreaterThan(0);
    expect(result?.gaps.length).toBeLessThanOrEqual(4);
  });

  it('still hides CTA when gap > 4 (hopeless-rewrite case)', () => {
    const hopeless: EmScore = {
      ...TEXT_NOTES_PROFILE,
      code: '99212',
      mdmTier: 'straightforward',
      satisfied: {
        hpiElements: 1,
        rosSystems: 0,
        pfshCategories: 0,
        examSystems: 0,
        problems: 'minimal',
        data: 'minimal',
        risk: 'minimal',
      },
    };
    // 99212 → 99213 requires HPI:4 / ROS:2 / PFSH:1 / Exam:2 / MDM low.
    // Have HPI:1 / ROS:0 / PFSH:0 / Exam:0 / MDM minimal — 5 gaps → hide.
    const result = shouldShowBumpCta('99212', hopeless);
    expect(result).toBeNull();
  });

  it('surfaces a confirm-bump CTA when zero gaps (rubric already met)', () => {
    const metAll: EmScore = {
      ...TEXT_NOTES_PROFILE,
      code: '99213',
      mdmTier: 'low',
      satisfied: {
        hpiElements: 10,
        rosSystems: 10,
        pfshCategories: 3,
        examSystems: 10,
        problems: 'moderate',
        data: 'moderate',
        risk: 'moderate',
      },
    };
    const result = shouldShowBumpCta('99213', metAll);
    expect(result?.mode).toBe('confirm-bump');
    expect(result?.gaps).toEqual([]);
  });

  // End-to-end via computeEmScore — same SOAP that previously dropped
  // to bumpableTo=null now produces a non-null bumpableTo with gaps
  // listed. The SOAP is a minimal concise note that satisfies 99214
  // (moderate MDM via prescription drug management) but stays short
  // of 99215 on ROS / Exam.
  it('computeEmScore: text_notes profile now produces non-null bumpableTo', async () => {
    const soap = `## Subjective
**Chief Complaint:** Established T2DM follow-up at week 8 of metformin titration.

**HPI:** 47-year-old female with type 2 diabetes. Last visit A1c 8.1; today 7.2. Reports increased water intake, occasional polyuria. Adherent to metformin 1000 mg BID with meals. No GI side effects this cycle.

**PMH:** Type 2 diabetes mellitus, essential hypertension, dyslipidemia.

**Medications:** Metformin 1000 mg PO BID, lisinopril 20 mg daily, atorvastatin 20 mg nightly.

**ROS:**
- Constitutional: Energy stable.
- Endocrine: Mild polyuria; no polydipsia.
- Cardiac: No chest pain.

## Objective
BP 132/82, HR 76. BMI 31. Abdomen soft, non-tender. Cardiac RRR. Lungs clear.

## Assessment
1. Type 2 diabetes mellitus — improving on metformin (A1c 7.2 from 8.1); reinforce adherence + ongoing pharmacologic management.
2. Essential hypertension — at goal on lisinopril 20 mg.
3. Dyslipidemia — atorvastatin 20 mg nightly; lipid panel next visit.

## Plan
1. Continue metformin 1000 mg BID; recheck A1c in 3 months.
2. Continue lisinopril 20 mg daily; home BP log review at next visit.
3. Lipid panel + LFTs at 3 months.
4. Return precautions reviewed. F/U 3 months.`;
    const engine = await computeEmScore(soap, {
      mdmCachedJudgement: null,
      icdCodes: [{ code: 'E11.9' }, { code: 'I10' }, { code: 'E78.5' }],
      rxDrafts: [{ drug: 'metformin' }, { drug: 'lisinopril' }, { drug: 'atorvastatin' }],
    });
    expect(engine.bumpableTo).not.toBeNull();
    // bumpGaps should be populated (the surface area of what's missing).
    expect(engine.bumpGaps).toBeDefined();
    expect((engine.bumpGaps ?? []).length).toBeGreaterThan(0);
  });
});
