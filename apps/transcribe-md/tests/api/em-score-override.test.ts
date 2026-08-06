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
      findFirst: mocks.visitFindUnique,
      update: mocks.visitUpdate,
    },
  },
}));

vi.mock('@/lib/nextauth', () => ({ auth: mocks.auth }));
// T5: the by-id routes now source practiceId from the DB-refreshed session.
vi.mock('@/lib/auth', () => ({ getSession: mocks.auth }));
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
      makeReq({ overrideToCode: '99214', reason: 'Level reflects the documented exam.' }),
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
      makeReq({ overrideToCode: '99214', reason: 'Level reflects the documented exam.' }),
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
      makeReq({ overrideToCode: '99214', reason: 'Level reflects the documented exam.' }),
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
      makeReq({ overrideToCode: '99214', reason: 'Level reflects the documented exam.' }),
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

    const res = await POST(makeReq({ overrideToCode: '99214', reason: 'Level reflects the documented exam.' }), ctx);
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

  it('200 + the reason is recorded on the audit row', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue(READY_VISIT);
    mocks.visitUpdate.mockResolvedValue({});

    const res = await POST(makeReq({ overrideToCode: '99214', reason: 'Level reflects the documented exam.' }), ctx);
    expect(res.status).toBe(200);

    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    const audit = mocks.logAudit.mock.calls[0][0];
    expect(audit.action).toBe('EM_OVERRIDE_APPLIED');
    // The reason USED to be optional and this test asserted it was null. It is
    // required now: the control moved from a coding rail, where the level was
    // one of several things on screen, to the gate stack a doctor crosses on
    // the way to a signature. "Who changed it to what" without "and why" is the
    // half of the row nobody can reconstruct afterwards.
    expect(audit.metadata.reason).toBe('Level reflects the documented exam.');
    expect(audit.metadata.toCode).toBe('99214');
  });

  it('400 when no reason is given — the field is REQUIRED', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue(READY_VISIT);

    const res = await POST(makeReq({ overrideToCode: '99214' }), ctx);
    expect(res.status).toBe(400);
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('400 when the reason is only whitespace', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue(READY_VISIT);

    const res = await POST(makeReq({ overrideToCode: '99214', reason: '   ' }), ctx);
    expect(res.status).toBe(400);
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
  });

  it('ARMS THE CONFIRM GATE — an override writes a pending change', async () => {
    // Setting a level is not attesting to one. The write raises the SAME
    // pending-change record a model-driven re-score raises, so the existing
    // confirm card blocks and the sign route still refuses without a matching
    // acknowledgement. "I set it myself" must not be a shortcut past the one
    // control that records that a human looked.
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue({
      ...READY_VISIT,
      cptCodes: { em: { code: '99213' } },
      emPendingChange: null,
    });
    mocks.visitUpdate.mockResolvedValue({});

    const res = await POST(
      makeReq({ overrideToCode: '99215', reason: 'Time and complexity documented.' }),
      ctx,
    );
    expect(res.status).toBe(200);

    const data = mocks.visitUpdate.mock.calls[0][0].data;
    expect(data.emPendingChange).toMatchObject({
      cause: 'doctor_override',
      from: '99213',
      to: '99215',
    });
    const body = await res.json();
    expect(body.pendingChange).toEqual({ from: '99213', to: '99215' });
  });

  it('409 on an IMAGING report — there is no office level to override', async () => {
    // An office E/M code on an imaging report is wrong as DATA: it reaches the
    // export and the signed record. The UI never offers it there, but the route
    // owns the column and "the caller wouldn't do that" is how one lands.
    process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = 'true';
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue({ ...READY_VISIT, specialty: 'ultrasound' });

    const res = await POST(
      makeReq({ overrideToCode: '99214', reason: 'should never land' }),
      ctx,
    );
    expect(res.status).toBe(409);
    // WHICH 409, not just "a 409". Three different conditions in this route
    // answer 409, so an assertion on the status alone passes when the imaging
    // gate is deleted and some later gate catches the request by accident.
    expect((await res.json()).code).toBe('EM_NOT_APPLICABLE');
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    delete process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
  });

  it('STALENESS IS UNTOUCHED — the payload carries no soapVersion and no emStale', async () => {
    // Requirement B, asserted on the WRITE rather than grepped for. Staleness
    // keys on content change; an override is not a note edit. Bumping the note's
    // version here would gate the doctor behind their own choice — the stale
    // card would appear because they had set a level, and the only way out
    // would be re-checking a level they had just chosen.
    //
    // The previous guard for this was a source grep for the strings
    // `soapVersion: { increment` and `emStale: true`, which a reformat or a
    // computed key defeats. This reads the payload the route actually sends.
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue(READY_VISIT);
    mocks.visitUpdate.mockResolvedValue({});

    const res = await POST(
      makeReq({ overrideToCode: '99214', reason: 'Exam and MDM documented at this level.' }),
      ctx,
    );
    expect(res.status).toBe(200);

    const data = mocks.visitUpdate.mock.calls[0][0].data;
    expect(data).not.toHaveProperty('soapVersion');
    expect(data).not.toHaveProperty('emStale');
  });

  it('overriding BACK to the reviewed level clears the gate and moves the baseline with it', async () => {
    // The doctor set 99215, then thought better of it and set 99213 again — the
    // level the pending record was raised FROM. There is nothing left to
    // confirm, so the record goes; leaving it would block the signature over a
    // change that no longer exists.
    //
    // AND `emScoredCode` MOVES TOO. It still held the level the cleared record
    // was measured against, so the next re-score computed a move the doctor had
    // already resolved and raised a fresh confirm card for a level nothing had
    // changed to.
    mocks.auth.mockResolvedValue({
      user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
    });
    mocks.visitFindUnique.mockResolvedValue({
      ...READY_VISIT,
      cptCodes: { em: { code: '99213', override: { code: '99215' } } },
      emPendingChange: {
        cause: 'doctor_override',
        at: '2026-07-28T00:00:00.000Z',
        from: '99213',
        to: '99215',
      },
    });
    mocks.visitUpdate.mockResolvedValue({});

    const res = await POST(
      makeReq({ overrideToCode: '99213', reason: 'On reflection the original level was right.' }),
      ctx,
    );
    expect(res.status).toBe(200);

    const data = mocks.visitUpdate.mock.calls[0][0].data;
    expect(data.emPendingChange).toBeDefined();
    expect(data.emPendingChange).not.toMatchObject({ to: '99213' }); // DbNull, not a record
    expect(data.emScoredCode).toBe('99213');
    expect((await res.json()).pendingChange).toBeNull();
  });

  it('EVERY IN-REPO CALLER SENDS A REASON — the route rejects one that does not', async () => {
    // The reason became required with this route's rehoming, and two older
    // callers (the C3 billing card's dropdown and the coding rail's) posted
    // none. Both would have 400'd on every use: controls that look live and
    // cannot work. They were retired rather than given a fabricated rationale.
    //
    // This is the guard that keeps a reasonless caller from reappearing. It is
    // a source scan on purpose — the point is that no OTHER file posts to this
    // route at all.
    const { readFileSync, readdirSync, statSync } = await import('node:fs');
    const { join } = await import('node:path');
    const hits: string[] = [];
    const walk = (dir: string) => {
      for (const e of readdirSync(dir)) {
        const p = join(dir, e);
        if (statSync(p).isDirectory()) {
          if (e === 'node_modules' || e === '.next') continue;
          walk(p);
        } else if (/\.tsx?$/.test(e) && !/__tests__|\.test\./.test(p)) {
          // The route named INSIDE a fetch call — a doc comment that mentions
          // the endpoint is not a caller, and matching those made this fail on
          // CodingRail, whose only fetch goes to /em-score.
          const src = readFileSync(p, 'utf8');
          if (/fetch\(\s*`[^`]*em-score\/override/.test(src)) hits.push(p);
        }
      }
    };
    walk('src');

    // Exactly one caller, and it sends the reason it collected.
    expect(hits).toEqual(['src/app/visits/[id]/visit-ready-view.tsx']);
    const caller = readFileSync(hits[0], 'utf8');
    expect(caller).toContain('overrideToCode: code, reason');
  });
});
