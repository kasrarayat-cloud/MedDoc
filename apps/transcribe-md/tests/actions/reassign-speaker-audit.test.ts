// ============================================================================
// reassignSpeakerAction — SPEAKER_ROLE_REASSIGNED audit-row guard (FIND-P1-003)
// ----------------------------------------------------------------------------
// Comprehensive-audit FIND-P1-003 (2026-05-14): the Layer-2 manual override
// at apps/transcribe-md/src/actions/soap.ts:209 mutates `speakerMap` —
// which affects the SOAP note's history-vs-plan segmentation downstream
// — without emitting a HIPAA §164.312(b) audit row. The fix adds a new
// `SPEAKER_ROLE_REASSIGNED` enum value + fire-and-forget logAudit call.
// This test pins the post-fix shape:
//
//   - Successful reassign writes ONE audit row with action=
//     'SPEAKER_ROLE_REASSIGNED' + targetType='TranscribeVisit' +
//     targetId=<visit id> + metadata { source, speakerId, previousRole,
//     newRole }
//   - PHI excluded — speakerId is an internal numeric label, role is
//     enum, no patient name / utterance content
//   - Fire-and-forget — logAudit failure does NOT break the user-facing
//     reassign flow
//   - Early-return branches (visit-not-found, foreign-user, trashed,
//     signed, invalid role) do NOT emit
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  visitFindUnique: vi.fn(),
  visitUpdate: vi.fn(),
  requireSession: vi.fn(),
  logAudit: vi.fn(),
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
  captureEditPattern: vi.fn(),
}));
vi.mock('next/cache', () => ({ revalidatePath: mocks.revalidatePath }));

import { reassignSpeakerAction } from '@/actions/soap';

const FAKE_USER = 'u1';
const FAKE_PRACTICE = 'p1';
const FAKE_VISIT = 'vis1';
const FAKE_SPEAKER = '0';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({
    user: { id: FAKE_USER, practiceId: FAKE_PRACTICE, email: 'doc@example.com' },
  });
  mocks.visitFindUnique.mockResolvedValue({
    id: FAKE_VISIT,
    userId: FAKE_USER,
    status: 'READY',
    speakerMap: {
      '0': { role: 'doctor', confidence: 0.6, reasoning: 'L2 inferred' },
      '1': { role: 'patient', confidence: 0.9, reasoning: 'L2 inferred' },
    },
    deletedAt: null,
    archivedAt: null,
  });
  mocks.visitUpdate.mockResolvedValue({ id: FAKE_VISIT });
  mocks.logAudit.mockResolvedValue(undefined);
});

describe('reassignSpeakerAction SPEAKER_ROLE_REASSIGNED audit guard (FIND-P1-003)', () => {
  it('emits SPEAKER_ROLE_REASSIGNED with the right targetType + targetId on success', async () => {
    const result = await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, 'patient');

    expect(result).toEqual({ ok: true });
    expect(mocks.visitUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.action).toBe('SPEAKER_ROLE_REASSIGNED');
    expect(auditArgs.targetType).toBe('TranscribeVisit');
    expect(auditArgs.targetId).toBe(FAKE_VISIT);
  });

  it('audit metadata carries source + speakerId + previousRole + newRole', async () => {
    await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, 'patient');

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.metadata).toEqual({
      source: 'server_action',
      speakerId: FAKE_SPEAKER,
      previousRole: 'doctor', // from the seeded speakerMap
      newRole: 'patient',
    });
  });

  it('previousRole is null when the speaker has no prior entry', async () => {
    // Reassigning a speakerId that's not in the existing speakerMap —
    // edge case but well-formed (the action creates a fresh entry).
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT,
      userId: FAKE_USER,
      status: 'READY',
      speakerMap: {}, // empty
      deletedAt: null,
      archivedAt: null,
    });

    await reassignSpeakerAction(FAKE_VISIT, 'unknown-speaker', 'doctor');

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.metadata.previousRole).toBe(null);
    expect(auditArgs.metadata.newRole).toBe('doctor');
    expect(auditArgs.metadata.speakerId).toBe('unknown-speaker');
  });

  it('no PHI in metadata — speakerId is internal, role is enum', async () => {
    await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, 'family');

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    const metadataString = JSON.stringify(auditArgs.metadata);

    // Sanity-check: nothing in metadata should resemble PHI shapes —
    // no patient names, no email-like strings, no transcript fragments.
    expect(metadataString).not.toContain('@');
    expect(metadataString).not.toContain('doc@example.com');
    expect(metadataString).not.toMatch(/Manually reassigned/i);
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

    await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, 'patient');

    expect(order).toEqual(['visit-update', 'log-audit']);
  });

  it('audit failure does NOT break the reassign flow (fire-and-forget)', async () => {
    mocks.logAudit.mockRejectedValue(new Error('audit DB down'));

    const result = await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, 'patient');

    expect(result).toEqual({ ok: true });
    expect(mocks.visitUpdate).toHaveBeenCalledTimes(1);
  });

  it('does NOT emit when role is invalid (zod rejects before any mutation)', async () => {
    const result = await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, 'not-a-role');

    expect(result).toEqual({ ok: false, error: 'Invalid speaker role.' });
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('does NOT emit when visit is not found', async () => {
    mocks.visitFindUnique.mockResolvedValue(null);

    const result = await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, 'patient');

    expect(result).toEqual({ ok: false, error: 'Visit not found.' });
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('does NOT emit when visit belongs to a different user', async () => {
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT,
      userId: 'other-user',
      status: 'READY',
      speakerMap: {},
      deletedAt: null,
      archivedAt: null,
    });

    const result = await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, 'patient');

    expect(result).toEqual({ ok: false, error: 'Visit not found.' });
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('does NOT emit when visit is trashed/archived', async () => {
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT,
      userId: FAKE_USER,
      status: 'READY',
      speakerMap: {},
      deletedAt: new Date(),
      archivedAt: null,
    });

    const result = await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, 'patient');

    expect(result).toEqual({
      ok: false,
      error: 'Visit is no longer active. Restore it first.',
    });
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('does NOT emit when visit is already SIGNED (signed notes are locked)', async () => {
    mocks.visitFindUnique.mockResolvedValue({
      id: FAKE_VISIT,
      userId: FAKE_USER,
      status: 'SIGNED',
      speakerMap: {},
      deletedAt: null,
      archivedAt: null,
    });

    const result = await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, 'patient');

    expect(result).toEqual({
      ok: false,
      error: 'Signed notes cannot be edited.',
    });
    expect(mocks.visitUpdate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});
