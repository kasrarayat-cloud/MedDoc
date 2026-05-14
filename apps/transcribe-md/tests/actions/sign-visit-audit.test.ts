// ============================================================================
// signVisitAction — VISIT_SIGNED audit-row guard (FIND-P1-001 closure)
// ----------------------------------------------------------------------------
// Comprehensive-audit FIND-P1-001 (2026-05-14): the action-path signing
// surface at apps/transcribe-md/src/actions/soap.ts:131 mutates status=
// SIGNED + freezes signedSoap + writes signedAt — the legal-record signing
// event — without emitting a VISIT_SIGNED audit row. The parallel
// route-path at app/api/visits/[id]/sign/route.ts DOES emit, and
// production has 7 rows from it. This test pins the post-fix shape so
// future refactors keep both surfaces audit-symmetric:
//
//   - Successful sign writes ONE audit row with action='VISIT_SIGNED' +
//     targetType='TranscribeVisit' + targetId=<visit id> + metadata
//     carrying { source: 'server_action' } to disambiguate the surface
//   - PHI is excluded (no signedSoap content, no patient identifiers)
//   - The audit call is fire-and-forget — a logAudit failure never
//     breaks the user-facing sign flow
//   - Early-return branches (visit-not-found, already-signed,
//     not-READY, empty soapFinal) do NOT emit
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  visitFindUnique: vi.fn(),
  visitUpdate: vi.fn(),
  requireSession: vi.fn(),
  logAudit: vi.fn(),
  captureEditPattern: vi.fn(),
  revalidatePath: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: {
      findUnique: mocks.visitFindUnique,
      update: mocks.visitUpdate,
    },
  },
}));
vi.mock('@/lib/auth', () => ({ requireSession: mocks.requireSession }));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/lib/edit-tracking', () => ({
  captureEditPattern: mocks.captureEditPattern,
}));
vi.mock('next/cache', () => ({ revalidatePath: mocks.revalidatePath }));

import { signVisitAction } from '@/actions/soap';

const FAKE_USER = 'u1';
const FAKE_PRACTICE = 'p1';
const FAKE_VISIT = 'vis1';
const FAKE_SOAP = '# Subjective\n\nPatient reports headache.\n\n# Objective...';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({
    user: { id: FAKE_USER, practiceId: FAKE_PRACTICE, email: 'doc@example.com' },
  });
  mocks.visitFindUnique.mockResolvedValue({
    id: FAKE_VISIT,
    userId: FAKE_USER,
    status: 'READY',
    soapFinal: FAKE_SOAP,
    signedAt: null,
    deletedAt: null,
    archivedAt: null,
  });
  mocks.visitUpdate.mockResolvedValue({ id: FAKE_VISIT });
  mocks.captureEditPattern.mockResolvedValue(undefined);
  mocks.logAudit.mockResolvedValue(undefined);
});

describe('signVisitAction VISIT_SIGNED audit guard (FIND-P1-001)', () => {
  it('emits VISIT_SIGNED with the right targetType + targetId on success', async () => {
    const result = await signVisitAction(FAKE_VISIT);

    expect(result).toEqual({ ok: true });
    expect(mocks.visitUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.action).toBe('VISIT_SIGNED');
    expect(auditArgs.targetType).toBe('TranscribeVisit');
    expect(auditArgs.targetId).toBe(FAKE_VISIT);
  });

  it('audit metadata carries source=server_action; no PHI in payload', async () => {
    await signVisitAction(FAKE_VISIT);

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.metadata).toEqual({ source: 'server_action' });

    // PHI guard: the SOAP body must never leak into metadata, even by
    // accident (it's the legal-record content, the worst possible
    // PHI surface to audit-row).
    const metadataString = JSON.stringify(auditArgs.metadata);
    expect(metadataString).not.toContain('headache');
    expect(metadataString).not.toContain('Subjective');
    expect(metadataString).not.toContain(FAKE_USER);
  });

  it('audit emits AFTER the visit row is updated (not before)', async () => {
    const order: string[] = [];
    mocks.visitUpdate.mockImplementation(async () => {
      order.push('visit-update');
      return { id: FAKE_VISIT };
    });
    mocks.logAudit.mockImplementation(async () => {
      order.push('log-audit');
    });

    await signVisitAction(FAKE_VISIT);

    expect(order).toEqual(['visit-update', 'log-audit']);
  });

  it('audit failure does NOT break the sign flow (fire-and-forget)', async () => {
    // logAudit rejects — the action must still complete successfully.
    mocks.logAudit.mockRejectedValue(new Error('audit DB down'));

    const result = await signVisitAction(FAKE_VISIT);

    expect(result).toEqual({ ok: true });
    expect(mocks.visitUpdate).toHaveBeenCalledTimes(1);
  });

  it('does NOT emit when visit is not found (ownership/existence check fails)', async () => {
    mocks.visitFindUnique.mockResolvedValue(null);

    const result = await signVisitAction(FAKE_VISIT);

    expect(result).toEqual({ ok: false, error: 'Visit not found.' });
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('does NOT emit when visit belongs to a different user', async () => {
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT,
      userId: 'other-user',
      status: 'READY',
      soapFinal: FAKE_SOAP,
      signedAt: null,
      deletedAt: null,
      archivedAt: null,
    });

    const result = await signVisitAction(FAKE_VISIT);

    expect(result).toEqual({ ok: false, error: 'Visit not found.' });
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('does NOT re-emit when visit is already SIGNED (idempotent no-op)', async () => {
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT,
      userId: FAKE_USER,
      status: 'SIGNED',
      soapFinal: FAKE_SOAP,
      signedAt: new Date(),
      deletedAt: null,
      archivedAt: null,
    });

    const result = await signVisitAction(FAKE_VISIT);

    // Per the action's contract: idempotent — already signed returns ok.
    expect(result).toEqual({ ok: true });
    // But no row was written and no audit fired (no transition occurred).
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('does NOT emit when visit is still processing (status !== READY)', async () => {
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT,
      userId: FAKE_USER,
      status: 'POLISHING',
      soapFinal: FAKE_SOAP,
      signedAt: null,
      deletedAt: null,
      archivedAt: null,
    });

    const result = await signVisitAction(FAKE_VISIT);

    expect(result).toEqual({ ok: false, error: 'Note is still processing.' });
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('does NOT emit when soapFinal is empty (no content to sign)', async () => {
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT,
      userId: FAKE_USER,
      status: 'READY',
      soapFinal: '   ',
      signedAt: null,
      deletedAt: null,
      archivedAt: null,
    });

    const result = await signVisitAction(FAKE_VISIT);

    expect(result).toEqual({ ok: false, error: 'No SOAP content to sign.' });
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('does NOT emit when visit is trashed/archived', async () => {
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT,
      userId: FAKE_USER,
      status: 'READY',
      soapFinal: FAKE_SOAP,
      signedAt: null,
      deletedAt: new Date(),
      archivedAt: null,
    });

    const result = await signVisitAction(FAKE_VISIT);

    expect(result).toEqual({
      ok: false,
      error: 'Visit is no longer active. Restore it first.',
    });
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});
