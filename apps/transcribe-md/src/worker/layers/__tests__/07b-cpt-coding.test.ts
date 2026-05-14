// ============================================================================
// L7b CPT coding — single-update atomicity (FIND-P1-004)
// ----------------------------------------------------------------------------
// Pre-fix: L7b made two `prisma.update` calls on the same row — one for
// `{ needsReview: true, reviewReason: ... }` when any procedure landed
// at low confidence, then another for `{ cptCodes: filtered }`. A
// worker crash between the two updates left the visit with the warning
// banner but no codes to verify (BullMQ retry + watchdog rescued it,
// but the inconsistent window existed).
//
// Post-fix: ONE atomic `prisma.update` with conditional spread —
// `{ cptCodes, ...reviewFields }`. These tests pin the post-fix shape
// so the dual-write pattern can't regress in a future refactor.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelComplete: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
  isValidCpt: vi.fn(() => true),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    modelClient: { complete: mocks.modelComplete },
    isValidCpt: mocks.isValidCpt,
  };
});

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: { update: mocks.prismaUpdate },
  },
}));

vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { runLayer7bCptCoding } from '../07b-cpt-coding';

const baseInput = {
  visitId: 'vis-1',
  practiceId: 'p1',
  userId: 'u1',
  specialty: 'primary-care',
  soapFinal: '## Subjective\nRoutine follow-up for hypertension.',
  entitiesJson: '{}',
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.prismaUpdate.mockResolvedValue({});
  mocks.logAudit.mockResolvedValue(undefined);
  mocks.isValidCpt.mockReturnValue(true);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('L7b — single-update atomicity (FIND-P1-004)', () => {
  it('writes cptCodes + review flags in ONE atomic update when any procedure is low-confidence', async () => {
    mocks.modelComplete.mockResolvedValueOnce({
      em: {
        code: '99213',
        confidence: 'high',
        confidenceLevel: 'high',
        reasoning: { problems: [], data: '', risk: 'low' },
        totalMinutes: 20,
      },
      procedures: [
        {
          code: '93000',
          description: 'ECG',
          confidence: 0.5,
          confidenceLevel: 'low',
        },
      ],
      modifiers: [],
    });

    await runLayer7bCptCoding(baseInput);

    // Pre-fix: 2 separate updates. Post-fix: ONE atomic update.
    expect(mocks.prismaUpdate).toHaveBeenCalledTimes(1);

    const updateArgs = mocks.prismaUpdate.mock.calls[0][0];
    expect(updateArgs.where).toEqual({ id: 'vis-1' });
    // Both fields land in the same update payload — no crash window
    // between them.
    expect(updateArgs.data.cptCodes).toBeDefined();
    expect(updateArgs.data.needsReview).toBe(true);
    expect(updateArgs.data.reviewReason).toMatch(/CPT procedure code/);
    expect(updateArgs.data.reviewReason).toMatch(/93000/);
    expect(updateArgs.data.reviewReason).toMatch(/verify before billing/);
  });

  it('writes only cptCodes (no review flag) when all procedures are high-confidence', async () => {
    mocks.modelComplete.mockResolvedValueOnce({
      em: {
        code: '99214',
        confidence: 'high',
        confidenceLevel: 'high',
        reasoning: { problems: [], data: '', risk: 'moderate' },
        totalMinutes: 25,
      },
      procedures: [
        {
          code: '93000',
          description: 'ECG',
          confidence: 0.95,
          confidenceLevel: 'high',
        },
      ],
      modifiers: [],
    });

    await runLayer7bCptCoding(baseInput);

    // Still one atomic update; review fields just absent.
    expect(mocks.prismaUpdate).toHaveBeenCalledTimes(1);

    const updateArgs = mocks.prismaUpdate.mock.calls[0][0];
    expect(updateArgs.data.cptCodes).toBeDefined();
    expect(updateArgs.data.needsReview).toBeUndefined();
    expect(updateArgs.data.reviewReason).toBeUndefined();
  });

  it('writes cptCodes + review when MULTIPLE procedures are low-confidence (reason lists all)', async () => {
    mocks.modelComplete.mockResolvedValueOnce({
      em: {
        code: '99213',
        confidence: 'medium',
        confidenceLevel: 'medium',
        reasoning: { problems: [], data: '', risk: 'low' },
        totalMinutes: 20,
      },
      procedures: [
        {
          code: '93000',
          description: 'ECG',
          confidence: 0.4,
          confidenceLevel: 'low',
        },
        {
          code: '36415',
          description: 'Venipuncture',
          confidence: 0.45,
          confidenceLevel: 'low',
        },
      ],
      modifiers: [],
    });

    await runLayer7bCptCoding(baseInput);

    expect(mocks.prismaUpdate).toHaveBeenCalledTimes(1);
    const updateArgs = mocks.prismaUpdate.mock.calls[0][0];
    expect(updateArgs.data.needsReview).toBe(true);
    expect(updateArgs.data.reviewReason).toMatch(/93000/);
    expect(updateArgs.data.reviewReason).toMatch(/36415/);
    // Plural form for >1 low-conf code
    expect(updateArgs.data.reviewReason).toMatch(/2 CPT procedure codes/);
  });

  it('writes cptCodes + review with singular grammar when exactly ONE procedure is low-confidence', async () => {
    mocks.modelComplete.mockResolvedValueOnce({
      em: {
        code: '99213',
        confidence: 'medium',
        confidenceLevel: 'medium',
        reasoning: { problems: [], data: '', risk: 'low' },
        totalMinutes: 15,
      },
      procedures: [
        {
          code: '93000',
          description: 'ECG',
          confidence: 0.4,
          confidenceLevel: 'low',
        },
      ],
      modifiers: [],
    });

    await runLayer7bCptCoding(baseInput);

    const updateArgs = mocks.prismaUpdate.mock.calls[0][0];
    expect(updateArgs.data.reviewReason).toMatch(/1 CPT procedure code\b/);
    expect(updateArgs.data.reviewReason).not.toMatch(/1 CPT procedure codes/);
  });
});
