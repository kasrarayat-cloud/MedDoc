// ============================================================================
// loadResumeState — FIND-P1-011 hardening
// ----------------------------------------------------------------------------
// Pins the post-fix behavior:
//   - Row present       → returns the LayerSkipState shape
//   - Row missing, first attempt (attemptsMade=0)  → throws plain Error
//   - Row missing, retry (attemptsMade>0)          → throws VisitNotFoundError
//
// The worker's outer catch handler keys off `err instanceof
// VisitNotFoundError` to short-circuit the FAILED-state persist (the
// row's gone, the update would just P2025) and BullMQ marks the job
// successful (no pipeline retries needed for a deleted visit).
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findUnique: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { findUnique: mocks.findUnique } },
}));

import {
  loadResumeState,
  VisitNotFoundError,
} from '@/worker/resume-state';

const VISIT_ID = 'vis-1';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('loadResumeState — happy path', () => {
  it('returns the row when present (first attempt)', async () => {
    const row = {
      transcriptRaw: null,
      transcriptText: null,
      speakerMap: null,
      entities: null,
      soapDraft: null,
      critique: null,
      soapFinal: null,
      icdCodes: null,
      cptCodes: null,
      rxDrafts: null,
      referrals: null,
      patientSummary: null,
    };
    mocks.findUnique.mockResolvedValue(row);

    const result = await loadResumeState(VISIT_ID, 0);

    expect(result).toEqual(row);
    expect(mocks.findUnique).toHaveBeenCalledWith({
      where: { id: VISIT_ID },
      select: expect.objectContaining({
        transcriptRaw: true,
        soapFinal: true,
        rxDrafts: true,
        patientSummary: true,
      }),
    });
  });

  it('returns the partial-progress shape on retry (skip checks consume it)', async () => {
    const row = {
      transcriptRaw: { utterances: [{ speaker: 0, text: 'hi' }] },
      transcriptText: 'hi',
      speakerMap: { 0: { role: 'doctor', confidence: 0.9, reasoning: 'r' } },
      entities: null, // L3 didn't finish — next attempt resumes here
      soapDraft: null,
      critique: null,
      soapFinal: null,
      icdCodes: null,
      cptCodes: null,
      rxDrafts: null,
      referrals: null,
      patientSummary: null,
    };
    mocks.findUnique.mockResolvedValue(row);

    const result = await loadResumeState(VISIT_ID, 1);

    expect(result).toEqual(row);
  });
});

describe('loadResumeState — missing row branches (FIND-P1-011)', () => {
  it('throws VisitNotFoundError on RETRY (attemptsMade > 0) when row is gone', async () => {
    mocks.findUnique.mockResolvedValue(null);

    await expect(loadResumeState(VISIT_ID, 1)).rejects.toThrow(
      VisitNotFoundError
    );

    // Verify the error carries the visit id for downstream logging.
    try {
      await loadResumeState(VISIT_ID, 1);
    } catch (err) {
      expect(err).toBeInstanceOf(VisitNotFoundError);
      expect((err as VisitNotFoundError).visitId).toBe(VISIT_ID);
      expect((err as VisitNotFoundError).name).toBe('VisitNotFoundError');
    }
  });

  it('throws VisitNotFoundError on later retries too (attemptsMade=5)', async () => {
    mocks.findUnique.mockResolvedValue(null);

    await expect(loadResumeState(VISIT_ID, 5)).rejects.toThrow(
      VisitNotFoundError
    );
  });

  it('throws plain Error on FIRST attempt (attemptsMade=0) when row is gone', async () => {
    mocks.findUnique.mockResolvedValue(null);

    // First-attempt missing means a race between top-level findUnique
    // and this load. NOT a VisitNotFoundError — that's reserved for
    // the "deleted during retry" case. Surface as a plain Error so
    // Sentry catches it (worker outer catch falls through to the
    // normal FAILED-state path, which is the right move on a race).
    await expect(loadResumeState(VISIT_ID, 0)).rejects.toThrow(
      /disappeared between top-level find and resume-state load/
    );

    // Specifically: NOT a VisitNotFoundError. The outer catch's
    // VisitNotFoundError short-circuit must not fire on first-attempt
    // races.
    try {
      await loadResumeState(VISIT_ID, 0);
    } catch (err) {
      expect(err).not.toBeInstanceOf(VisitNotFoundError);
      expect(err).toBeInstanceOf(Error);
    }
  });
});

describe('VisitNotFoundError shape', () => {
  it('is instanceof Error', () => {
    const e = new VisitNotFoundError('v1');
    expect(e).toBeInstanceOf(Error);
    expect(e).toBeInstanceOf(VisitNotFoundError);
  });

  it('carries visitId + has a useful message', () => {
    const e = new VisitNotFoundError('vis-xyz');
    expect(e.visitId).toBe('vis-xyz');
    expect(e.message).toMatch(/Visit vis-xyz no longer exists/);
    expect(e.name).toBe('VisitNotFoundError');
  });
});
