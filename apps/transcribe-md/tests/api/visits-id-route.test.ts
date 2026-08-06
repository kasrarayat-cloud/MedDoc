// ============================================================================
// Unit tests for /api/visits/[id] (smoke F-B-003 fix).
// ----------------------------------------------------------------------------
// Covers GET (added in this PR) plus a PATCH happy-path regression so the
// new GET handler can't accidentally break the existing edit handler.
//
// Mocks:
//   @meddoc/db        — prisma.transcribeVisit.findUnique / update,
//                       prisma.user.findUnique
//   @/lib/nextauth    — auth() returning a session
//   @/lib/rate-limit  — rateLimitOr429 returning null (always allow)
//   @/lib/log         — log.info no-op
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TranscribeVisitStatus } from '@prisma/client';

const mocks = vi.hoisted(() => ({
  visitFindUnique: vi.fn(),
  visitUpdate: vi.fn(),
  userFindUnique: vi.fn(),
  patientFindUnique: vi.fn(),
  auth: vi.fn(),
  rateLimitOr429: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: {
      findUnique: mocks.visitFindUnique,
      findFirst: mocks.visitFindUnique,
      update: mocks.visitUpdate,
    },
    user: { findUnique: mocks.userFindUnique },
    transcribeMdPatient: { findUnique: mocks.patientFindUnique },
  },
}));

vi.mock('@/lib/nextauth', () => ({ auth: mocks.auth }));
// T5: the by-id routes now source practiceId from the DB-refreshed session.
vi.mock('@/lib/auth', () => ({ getSession: mocks.auth }));

vi.mock('@/lib/rate-limit', () => ({
  RATE_LIMITS: { VISIT_OPS: { bucket: 'visit-ops', limit: 30, windowMs: 3_600_000 } },
  rateLimitOr429: mocks.rateLimitOr429,
}));

vi.mock('@/lib/log', () => ({ log: { info: vi.fn(), error: vi.fn(), warn: vi.fn() } }));

import { GET, PATCH } from '@/app/api/visits/[id]/route';

const FAKE_USER_ID = 'user_owner_1';
// T5: getSession() never returns a session without a practice — it fails closed
// rather than hand back one the accessor would refuse. The fixture matches.
const FAKE_PRACTICE_ID = 'prac_owner_1';
const FAKE_VISIT_ID = 'cmoqn96fe001501l543vfe1u2';

function makeReq(method: string, body?: unknown) {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers = { 'content-type': 'application/json' };
  }
  return new Request(`http://localhost/api/visits/${FAKE_VISIT_ID}`, init) as unknown as Parameters<
    typeof GET
  >[0];
}

const ctx = { params: Promise.resolve({ id: FAKE_VISIT_ID }) };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.rateLimitOr429.mockReturnValue(null);
});

describe('GET /api/visits/[id]', () => {
  it('returns 200 + visit JSON for the owner', async () => {
    mocks.auth.mockResolvedValue({ user: { id: FAKE_USER_ID, practiceId: FAKE_PRACTICE_ID } });
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT_ID,
      userId: FAKE_USER_ID,
      patientId: 'pat_1',
      patientName: 'Smoke Patient',
      specialty: 'primary-care',
      chiefComplaint: 'chest pain',
      inputMode: 'audio_upload',
      status: TranscribeVisitStatus.READY,
      needsReview: true,
      reviewReason: 'missing red-flag screening',
      audioDurationSec: 56,
      soapFinal: '## Subjective\n...',
      transcriptText: 'Doctor: ...',
      icdCodes: { codes: [] },
      cptCodes: { codes: [] },
      rxDrafts: { prescriptions: [] },
      patient: { id: 'pat_1', name: 'Smoke Patient', dateOfBirth: new Date('1965-03-15') },
      createdAt: new Date('2026-05-04T03:32:46.155Z'),
      deletedAt: null,
      archivedAt: null,
    });

    const res = await GET(makeReq('GET'), ctx);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { visit: { id: string; status: string } };
    expect(body.visit.id).toBe(FAKE_VISIT_ID);

    // ⚠️ T5 — THE PREDICATE REACHED THE QUERY, not just the session.
    // Without this the route could drop `practiceId` entirely and every test
    // above would still pass, because the mock returns a row regardless of what
    // it is asked for. Asserting on the mock's ARGUMENT is the only way to see
    // the tenancy filter at all.
    expect(mocks.visitFindUnique).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ id: FAKE_VISIT_ID, practiceId: FAKE_PRACTICE_ID }),
      }),
    );
    expect(body.visit.status).toBe('READY');
  });

  it('returns 404 for a foreign visit (anti-enumeration: same code as not-found)', async () => {
    mocks.auth.mockResolvedValue({ user: { id: FAKE_USER_ID, practiceId: FAKE_PRACTICE_ID } });
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT_ID,
      userId: 'user_owner_2', // different owner
      patientId: 'pat_2',
      patientName: 'Other',
      specialty: 'primary-care',
      chiefComplaint: 'x',
      inputMode: 'audio_upload',
      status: TranscribeVisitStatus.READY,
    });

    const res = await GET(makeReq('GET'), ctx);
    expect(res.status).toBe(404);
  });

  it('returns 404 when the visit row does not exist', async () => {
    mocks.auth.mockResolvedValue({ user: { id: FAKE_USER_ID, practiceId: FAKE_PRACTICE_ID } });
    mocks.visitFindUnique.mockResolvedValue(null);

    const res = await GET(makeReq('GET'), ctx);
    expect(res.status).toBe(404);
  });

  it('returns 401 for unauthenticated callers', async () => {
    mocks.auth.mockResolvedValue(null);

    const res = await GET(makeReq('GET'), ctx);
    expect(res.status).toBe(401);
    expect(mocks.visitFindUnique).not.toHaveBeenCalled();
  });
});

describe('PATCH /api/visits/[id] (regression)', () => {
  it('updates the chief complaint of a draft visit', async () => {
    mocks.auth.mockResolvedValue({ user: { id: FAKE_USER_ID, practiceId: FAKE_PRACTICE_ID } });
    mocks.userFindUnique.mockResolvedValue({ practiceId: 'practice_1' });
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT_ID,
      userId: FAKE_USER_ID,
      status: TranscribeVisitStatus.QUEUED,
      audioKey: null,
      dictationAudioKey: null,
      rawTextInput: null,
      deletedAt: null,
      archivedAt: null,
      patientId: 'pat_1',
    });
    mocks.visitUpdate.mockResolvedValue({
      id: FAKE_VISIT_ID,
      patientId: 'pat_1',
      specialty: 'primary-care',
      chiefComplaint: 'updated CC',
      inputMode: 'audio_upload',
      updatedAt: new Date(),
    });

    const res = await PATCH(makeReq('PATCH', { chiefComplaint: 'updated CC' }), ctx);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { visit: { chiefComplaint: string } };
    expect(body.visit.chiefComplaint).toBe('updated CC');
  });
});
