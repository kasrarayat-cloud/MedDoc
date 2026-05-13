// ============================================================================
// L7a post-validation fallback — empty-codes detection
// (cross-input-mode audit Finding 3).
// ----------------------------------------------------------------------------
// Verifies that the L7a icd-coding layer's post-validation step flips
// needsReview + populates reviewReason + writes a
// VISIT_AUTOMATION_INCOMPLETE audit row when:
//   (a) The model returns `codes: []` (genuine empty result).
//   (b) The model returns only the Z76.89 last-resort placeholder
//       (semantically the same as empty — flag for review).
//
// And does NOT trip the fallback when:
//   (c) The model returns at least one specific diagnosis code.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelComplete: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
  isValidIcd10: vi.fn((c: string) => c.startsWith('Z') || c.startsWith('E') || c.startsWith('I') || c.startsWith('K') || c.startsWith('M') || c.startsWith('D')),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    modelClient: { complete: mocks.modelComplete },
    isValidIcd10: mocks.isValidIcd10,
  };
});

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: { update: mocks.prismaUpdate },
  },
}));

vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { runLayer7aIcdCoding } from '../07a-icd-coding';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.prismaUpdate.mockResolvedValue({});
  mocks.logAudit.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

const baseInput = {
  visitId: 'cmp_test',
  practiceId: 'prac_test',
  userId: 'user_test',
  specialty: 'ob-gyn',
  soapFinal: '## Subjective\nRoutine postpartum visit at 6 weeks.',
  entitiesJson: '{}',
};

describe('L7a post-validation — empty codes triggers needsReview', () => {
  it('flips needsReview + writes audit row when model returns codes:[]', async () => {
    mocks.modelComplete.mockResolvedValueOnce({ codes: [] });

    await runLayer7aIcdCoding(baseInput);

    // Should call prisma.update TWICE: once for needsReview, once for icdCodes
    const updateCalls = mocks.prismaUpdate.mock.calls;
    const needsReviewCall = updateCalls.find(([arg]) => arg.data.needsReview === true);
    expect(needsReviewCall).toBeTruthy();
    expect(needsReviewCall![0].data.reviewReason).toMatch(/Auto-coding returned no diagnoses/);
    expect(needsReviewCall![0].data.reviewReason).toMatch(/ob.gyn/);

    // Audit row written for forensics
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    const auditCall = mocks.logAudit.mock.calls[0][0];
    expect(auditCall.action).toBe('VISIT_AUTOMATION_INCOMPLETE');
    expect(auditCall.targetId).toBe('cmp_test');
    expect(auditCall.metadata.layer).toBe('l7a-icd');
    expect(auditCall.metadata.emptyArray).toBe(true);
    expect(auditCall.metadata.placeholderOnly).toBe(false);
  });
});

describe('L7a post-validation — Z76.89 placeholder-only triggers needsReview', () => {
  it('treats a single Z76.89 emission as semantically empty', async () => {
    mocks.modelComplete.mockResolvedValueOnce({
      codes: [
        {
          code: 'Z76.89',
          description: 'Persons encountering health services in other specified circumstances',
          evidence_quote: 'visit',
          confidence: 0.4,
          confidenceLevel: 'low',
        },
      ],
    });

    await runLayer7aIcdCoding(baseInput);

    // Z76.89 confidence=0.4 (low) → the existing low-conf path fires
    // FIRST with its own reviewReason. The placeholder-only path then
    // fires SECOND with the placeholder message. Both write
    // needsReview=true. The last write wins for the visit's stored
    // value; we just verify the placeholder path executed.
    const updateCalls = mocks.prismaUpdate.mock.calls;
    const placeholderCall = updateCalls.find(([arg]) =>
      typeof arg?.data?.reviewReason === 'string' &&
      /placeholder Z76\.89/.test(arg.data.reviewReason),
    );
    expect(placeholderCall).toBeTruthy();

    const auditCall = mocks.logAudit.mock.calls.find(
      ([arg]) => arg.action === 'VISIT_AUTOMATION_INCOMPLETE',
    );
    expect(auditCall).toBeTruthy();
    expect(auditCall![0].metadata.emptyArray).toBe(false);
    expect(auditCall![0].metadata.placeholderOnly).toBe(true);
  });
});

describe('L7a post-validation — happy path (no fallback fired)', () => {
  it('does NOT fire the empty-codes fallback when model returns ≥1 specific code', async () => {
    mocks.modelComplete.mockResolvedValueOnce({
      codes: [
        {
          code: 'Z39.2',
          description: 'Encounter for routine postpartum follow-up',
          evidence_quote: 'Routine postpartum visit',
          confidence: 0.95,
          confidenceLevel: 'high',
        },
      ],
    });

    await runLayer7aIcdCoding(baseInput);

    // The needsReview flag may still flip if a separate low-confidence
    // check fires — but for confidence=0.95 high, neither path fires.
    const updateCalls = mocks.prismaUpdate.mock.calls;
    const needsReviewCall = updateCalls.find(
      ([arg]) => arg.data.needsReview === true,
    );
    expect(needsReviewCall).toBeUndefined();

    // No empty-codes audit row.
    const emptyCodesAudits = mocks.logAudit.mock.calls.filter(
      ([arg]) => arg.action === 'VISIT_AUTOMATION_INCOMPLETE',
    );
    expect(emptyCodesAudits).toHaveLength(0);
  });

  it('still writes the icdCodes column with the accepted code', async () => {
    mocks.modelComplete.mockResolvedValueOnce({
      codes: [
        {
          code: 'D22.5',
          description: 'Melanocytic nevi of trunk',
          evidence_quote: 'pigmented lesion on back',
          confidence: 0.9,
          confidenceLevel: 'high',
        },
      ],
    });

    await runLayer7aIcdCoding(baseInput);

    const icdUpdate = mocks.prismaUpdate.mock.calls.find(
      ([arg]) => arg.data.icdCodes,
    );
    expect(icdUpdate).toBeTruthy();
    const written = icdUpdate![0].data.icdCodes as { codes: Array<{ code: string }> };
    expect(written.codes).toHaveLength(1);
    expect(written.codes[0].code).toBe('D22.5');
  });
});

describe('L7a post-validation — emptied by allowlist filter (model emitted bad code)', () => {
  it('fires the empty-codes fallback when the allowlist drops the only code', async () => {
    // Model returns one code, but it's not in the allowlist.
    mocks.isValidIcd10.mockReturnValueOnce(false);
    mocks.modelComplete.mockResolvedValueOnce({
      codes: [
        {
          code: 'BOGUS.99',
          description: 'fake',
          evidence_quote: 'x',
          confidence: 0.8,
          confidenceLevel: 'high',
        },
      ],
    });

    await runLayer7aIcdCoding(baseInput);

    // Post-filter, accepted.length === 0 — fallback should fire.
    const updateCalls = mocks.prismaUpdate.mock.calls;
    const needsReviewCall = updateCalls.find(([arg]) => arg.data.needsReview === true);
    expect(needsReviewCall).toBeTruthy();
    expect(needsReviewCall![0].data.reviewReason).toMatch(/Auto-coding returned no diagnoses/);
  });
});
