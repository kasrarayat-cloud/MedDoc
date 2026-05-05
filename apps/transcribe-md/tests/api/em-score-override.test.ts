// ============================================================================
// /api/visits/[id]/em-score/override — Phase 5.2 orphan-completion
// ----------------------------------------------------------------------------
// Covers the doctor-set CPT override route that the CodingRail's
// override dropdown calls through onApplyOverride. Tests:
//   - 401 when unauthenticated
//   - 400 on invalid body (unknown code, missing field)
//   - 404 when ownership mismatch
//   - 409 when visit is signed/locked
//   - 409 when visit isn't READY
//   - 200 + persists cptCodes.em.override + emits EM_OVERRIDE_APPLIED
//     audit row + returns refreshed UI score with the override hydrated
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

import { POST } from '@/app/api/visits/[id]/em-score/override/route';

const FAKE_USER = 'u1';
const FAKE_PRACTICE = 'p1';
const FAKE_VISIT = 'cmot_override_test';

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
  cptCodes: null,
  rxDrafts: { drafts: [] },
};

function makeReq(body: unknown) {
  return new Request(
    `http://localhost/api/visits/${FAKE_VISIT}/em-score/override`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }
  ) as unknown as Parameters<typeof POST>[0];
}

const ctx = { params: Promise.resolve({ id: FAKE_VISIT }) };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.computeEmScore.mockResolvedValue({
    code: '99213',
    bumpableTo: '99214',
    bumpGaps: [],
    visitType: 'established',
    mdmTier: 'low',
    satisfied: {
      hpiElements: 3,
      rosSystems: 1,
      pfshCategories: 0,
      examSystems: 1,
      problems: 'low',
      data: 'low',
      risk: 'low',
    },
    perElementConfidence: { hpi: 0.85 },
    timeFitScore: null,
    llmJudged: false,
    rubricVersion: 1,
    computedAt: new Date().toISOString(),
    cacheHit: false,
    mdmRationale: 'test',
    mdmConfidence: 0.85,
  });
  // engineToUiScore is now (engine, visitTimeSec, existingOverride);
  // when the override is supplied, mirror it into the returned score
  // so the test can assert the round-trip.
  mocks.engineToUiScore.mockImplementation(
    (
      _engine: unknown,
      _visitTimeSec: number,
      existingOverride?: { code: string; reason?: string; overriddenAt: string }
    ) => ({
      suggestedCode: '99213',
      visitType: 'established',
      mdmTier: 'low',
      llmJudged: false,
      confidence: 0.85,
      timeBand: { code: '99213', min: 1200, max: 1740 },
      visitTimeSec: 600,
      groups: [],
      bump: null,
      override: existingOverride,
      computedAt: new Date().toISOString(),
    })
  );
});

describe('POST /api/visits/[id]/em-score/override', () => {
  it('401 when unauthenticated', async () => {
    mocks.auth.mockResolvedValue(null);
    const res = await POST(
      makeReq({ overrideToCode: '99214' }),
      ctx
    );
    expect(res.status).toBe(401);
  });

  it('400 on invalid CPT code', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    const res = await POST(makeReq({ overrideToCode: '12345' }), ctx);
    expect(res.status).toBe(400);
  });

  it('400 on missing overrideToCode', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    const res = await POST(makeReq({ reason: 'no code' }), ctx);
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
      makeReq({ overrideToCode: '99214' }),
      ctx
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
      makeReq({ overrideToCode: '99214' }),
      ctx
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
      makeReq({ overrideToCode: '99214' }),
      ctx
    );
    expect(res.status).toBe(409);
  });

  it('200 + persists override + emits audit row on success', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue(READY_VISIT);
    mocks.visitUpdate.mockResolvedValue({});

    const res = await POST(
      makeReq({
        overrideToCode: '99214',
        reason: 'Higher MDM than the AI captured.',
      }),
      ctx
    );

    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      ok: boolean;
      newScore: {
        suggestedCode: string;
        override?: { code: string; reason?: string; overriddenAt: string };
      };
    };
    expect(body.ok).toBe(true);
    // The new UI score carries the override hydrated.
    expect(body.newScore.override?.code).toBe('99214');
    expect(body.newScore.override?.reason).toBe(
      'Higher MDM than the AI captured.'
    );
    expect(typeof body.newScore.override?.overriddenAt).toBe('string');

    // Persisted: cptCodes.em.override is set on the visit row.
    expect(mocks.visitUpdate).toHaveBeenCalledTimes(1);
    const updateArgs = mocks.visitUpdate.mock.calls[0][0];
    expect(updateArgs.where.id).toBe(FAKE_VISIT);
    expect(updateArgs.data.cptCodes.em.override.code).toBe('99214');
    expect(updateArgs.data.cptCodes.em.override.reason).toBe(
      'Higher MDM than the AI captured.'
    );

    // Audit row carries the from→to transition.
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    const audit = mocks.logAudit.mock.calls[0][0];
    expect(audit.action).toBe('EM_OVERRIDE_APPLIED');
    expect(audit.metadata.fromCode).toBe('99213');
    expect(audit.metadata.toCode).toBe('99214');
    expect(audit.metadata.reason).toBe('Higher MDM than the AI captured.');
  });

  it('200 + preserves existing cptCodes top-level keys', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue({
      ...READY_VISIT,
      cptCodes: {
        codes: [{ code: '99213', description: 'Established office visit' }],
        em: { previous: 'data' },
      },
    });
    mocks.visitUpdate.mockResolvedValue({});

    const res = await POST(makeReq({ overrideToCode: '99214' }), ctx);
    expect(res.status).toBe(200);

    const updateArgs = mocks.visitUpdate.mock.calls[0][0];
    // Other top-level keys (codes) are preserved.
    expect(updateArgs.data.cptCodes.codes).toEqual([
      { code: '99213', description: 'Established office visit' },
    ]);
    // em sub-blob's existing keys are preserved alongside the new override.
    expect(updateArgs.data.cptCodes.em.previous).toBe('data');
    expect(updateArgs.data.cptCodes.em.override.code).toBe('99214');
  });

  it('200 + reason is optional', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue(READY_VISIT);
    mocks.visitUpdate.mockResolvedValue({});

    const res = await POST(makeReq({ overrideToCode: '99214' }), ctx);
    expect(res.status).toBe(200);

    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    const audit = mocks.logAudit.mock.calls[0][0];
    expect(audit.metadata.reason).toBeNull();
  });
});
