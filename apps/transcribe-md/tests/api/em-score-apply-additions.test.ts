// ============================================================================
// /api/visits/[id]/em-score/apply-additions — Phase 5.2 stub completion
// ----------------------------------------------------------------------------
// Covers the bump-additions persistence route that the BumpModal calls
// through CodingRail's onApplyAdditions prop. Tests:
//   - 401 when unauthenticated
//   - 404 when ownership mismatch (consistent with rest of /api/visits)
//   - 409 when visit is signed/locked
//   - 409 when visit isn't READY (still processing)
//   - 200 + new UI score on success; persists merged soapDraft +
//     soapFinal; emits the EM_BUMP_APPLIED audit row
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TranscribeVisitStatus } from '@prisma/client';

const mocks = vi.hoisted(() => ({
  visitFindUnique: vi.fn(),
  visitUpdate: vi.fn(),
  auth: vi.fn(),
  logAudit: vi.fn(),
  computeEmScore: vi.fn(),
  engineToUiScore: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: {
      findUnique: mocks.visitFindUnique,
      update: mocks.visitUpdate,
    },
  },
}));

vi.mock('@/lib/nextauth', () => ({ auth: mocks.auth }));
vi.mock('@/lib/log', () => ({
  log: { info: vi.fn(), error: vi.fn(), warn: vi.fn() },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/lib/em-coding/score', () => ({
  computeEmScore: mocks.computeEmScore,
}));
vi.mock('@/lib/em-coding/to-ui-score', () => ({
  engineToUiScore: mocks.engineToUiScore,
}));

import { POST } from '@/app/api/visits/[id]/em-score/apply-additions/route';

const FAKE_USER = 'u1';
const FAKE_PRACTICE = 'p1';
const FAKE_VISIT = 'cmotxxxxx';

const READY_VISIT = {
  id: FAKE_VISIT,
  userId: FAKE_USER,
  status: TranscribeVisitStatus.READY,
  deletedAt: null,
  archivedAt: null,
  signedAt: null,
  soapDraft: `## Subjective
**HPI:** Patient reports cough.

## Objective
Lungs clear.

## Assessment
URI.

## Plan
Symptomatic care.`,
  soapFinal: null,
  audioDurationSec: 600,
  dictationDurationSec: null,
  inputMode: 'audio_upload',
  icdCodes: { codes: [{ code: 'J06.9' }] },
  rxDrafts: { drafts: [] },
};

function makeReq(body: unknown) {
  return new Request(
    `http://localhost/api/visits/${FAKE_VISIT}/em-score/apply-additions`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    },
  ) as unknown as Parameters<typeof POST>[0];
}

const ctx = { params: Promise.resolve({ id: FAKE_VISIT }) };

beforeEach(() => {
  vi.clearAllMocks();
  // engineToUiScore returns a stub UI score per call; tests assert
  // on the wrapper-route behavior, not the score's exact shape.
  mocks.computeEmScore.mockResolvedValue({
    code: '99214',
    bumpableTo: null,
    bumpGaps: [],
    visitType: 'established',
    mdmTier: 'moderate',
    satisfied: {
      hpiElements: 4,
      rosSystems: 2,
      pfshCategories: 1,
      examSystems: 2,
      problems: 'moderate',
      data: 'moderate',
      risk: 'moderate',
    },
    perElementConfidence: { hpi: 0.9 },
    timeFitScore: null,
    llmJudged: false,
    rubricVersion: 1,
    computedAt: new Date().toISOString(),
    cacheHit: false,
    mdmRationale: 'test',
    mdmConfidence: 0.85,
  });
  mocks.engineToUiScore.mockReturnValue({
    suggestedCode: '99214',
    visitType: 'established',
    mdmTier: 'moderate',
    llmJudged: false,
    confidence: 0.85,
    timeBand: { code: '99214', min: 1800, max: 2340 },
    visitTimeSec: 600,
    groups: [],
    bump: null,
    computedAt: new Date().toISOString(),
  });
});

describe('POST /api/visits/[id]/em-score/apply-additions', () => {
  it('401 when unauthenticated', async () => {
    mocks.auth.mockResolvedValue(null);
    const res = await POST(
      makeReq({ additions: [{ criterionId: 'hpi.elements', text: 'X' }] }),
      ctx,
    );
    expect(res.status).toBe(401);
  });

  it('400 on invalid body shape (missing additions)', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    const res = await POST(makeReq({}), ctx);
    expect(res.status).toBe(400);
  });

  it('404 when the visit belongs to a different user', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue({
      ...READY_VISIT,
      userId: 'someone_else',
    });
    const res = await POST(
      makeReq({ additions: [{ criterionId: 'hpi.elements', text: 'X' }] }),
      ctx,
    );
    expect(res.status).toBe(404);
  });

  it('409 when the visit is signed', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue({
      ...READY_VISIT,
      status: TranscribeVisitStatus.SIGNED,
      signedAt: new Date(),
    });
    const res = await POST(
      makeReq({ additions: [{ criterionId: 'hpi.elements', text: 'X' }] }),
      ctx,
    );
    expect(res.status).toBe(409);
  });

  it('409 when visit is still processing (not READY)', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue({
      ...READY_VISIT,
      status: TranscribeVisitStatus.DRAFTING,
    });
    const res = await POST(
      makeReq({ additions: [{ criterionId: 'hpi.elements', text: 'X' }] }),
      ctx,
    );
    expect(res.status).toBe(409);
  });

  it('200 + persists merged SOAP + emits audit row on success', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue(READY_VISIT);
    mocks.visitUpdate.mockResolvedValue({});

    const res = await POST(
      makeReq({
        additions: [
          { criterionId: 'hpi.elements', text: 'Severity 5/10.' },
          { criterionId: 'ros.systems', text: 'GI: denies nausea.' },
        ],
      }),
      ctx,
    );

    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      ok: boolean;
      newScore: { suggestedCode: string };
      applied: number;
    };
    expect(body.ok).toBe(true);
    expect(body.newScore.suggestedCode).toBe('99214');
    expect(body.applied).toBe(2);

    // Persisted: soapDraft + soapFinal both updated.
    expect(mocks.visitUpdate).toHaveBeenCalledTimes(1);
    const updateArgs = mocks.visitUpdate.mock.calls[0][0];
    expect(updateArgs.where.id).toBe(FAKE_VISIT);
    expect(updateArgs.data.soapDraft).toContain('Severity 5/10');
    expect(updateArgs.data.soapDraft).toContain('GI: denies nausea');
    expect(updateArgs.data.soapFinal).toContain('Severity 5/10');

    // Audit row.
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    const audit = mocks.logAudit.mock.calls[0][0];
    expect(audit.action).toBe('EM_BUMP_APPLIED');
    expect(audit.metadata.appliedCount).toBe(2);
    expect(audit.metadata.criterionIds).toEqual([
      'hpi.elements',
      'ros.systems',
    ]);
  });
});
