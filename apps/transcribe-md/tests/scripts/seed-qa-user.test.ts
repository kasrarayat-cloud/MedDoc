// ============================================================================
// seed-qa-user.test.ts — guard for F-07 + F-08
// ----------------------------------------------------------------------------
// On 2026-05-06 the QA Interaction Auditor's first PASS B browser walk
// found two seed-script bugs that gated the entire agent (see
// docs/qa-reports/20260506T005713Z.md):
//
//   F-07 — emailVerified missing → login refuses with
//          "Please verify your email before signing in."
//   F-08 — products entitlement missing → login refuses with
//          "This account is for MedDoc Pro, not TranscribeMD."
//
// These tests pin BOTH the create AND the update branches of the user
// upsert payload to set both fields. Idempotent re-seed has to restore
// them too — a stale row with emailVerified=NULL or products=[MEDDOC_PRO]
// must come back to known-good after re-running the script.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  buildUserUpsertPayload,
  PRACTICE_ID,
  QA_EMAIL_DEFAULT,
} from '../../scripts/seed-qa-user';

describe('seed-qa-user / buildUserUpsertPayload — F-07 + F-08 guard', () => {
  const baseArgs = {
    email: QA_EMAIL_DEFAULT,
    passwordHash: 'hashed_password_stub',
  };

  it('create branch sets emailVerified to a fresh Date (F-07)', () => {
    const t0 = new Date();
    const payload = buildUserUpsertPayload(baseArgs);
    const t1 = new Date();
    expect(payload.create.emailVerified).toBeInstanceOf(Date);
    // Sanity: the timestamp is within the test window (not a zero-date
    // / not a stale fixed value imported from somewhere).
    expect(payload.create.emailVerified.getTime()).toBeGreaterThanOrEqual(
      t0.getTime()
    );
    expect(payload.create.emailVerified.getTime()).toBeLessThanOrEqual(
      t1.getTime()
    );
  });

  it('update branch sets emailVerified to a fresh Date (F-07 idempotent re-seed)', () => {
    // The update branch is what runs when the script is re-invoked on
    // an already-seeded row. It MUST overwrite emailVerified so a stale
    // null (e.g. from some other migration / fixture reset) is healed.
    const payload = buildUserUpsertPayload(baseArgs);
    expect(payload.update.emailVerified).toBeInstanceOf(Date);
  });

  it('create branch grants TRANSCRIBE_MD product entitlement (F-08)', () => {
    const payload = buildUserUpsertPayload(baseArgs);
    expect(payload.create.products).toEqual(['TRANSCRIBE_MD']);
  });

  it('update branch overwrites products to TRANSCRIBE_MD (F-08 idempotent re-seed)', () => {
    const payload = buildUserUpsertPayload(baseArgs);
    expect(payload.update.products).toEqual(['TRANSCRIBE_MD']);
  });

  it('regression: doctor / clinic_main / lockout-reset shape preserved', () => {
    const payload = buildUserUpsertPayload(baseArgs);
    expect(payload.where).toEqual({ email: QA_EMAIL_DEFAULT });

    expect(payload.create.role).toBe('DOCTOR');
    expect(payload.create.isActive).toBe(true);
    expect(payload.create.practiceId).toBe(PRACTICE_ID);
    expect(payload.create.specialty).toBe('family-medicine');

    expect(payload.update.role).toBe('DOCTOR');
    expect(payload.update.isActive).toBe(true);
    expect(payload.update.lockedUntil).toBeNull();
    expect(payload.update.failedLoginCount).toBe(0);
    expect(payload.update.passwordHash).toBe(baseArgs.passwordHash);
  });

  it('passes the supplied email through (so QA_AUDITOR_EMAIL override works)', () => {
    const payload = buildUserUpsertPayload({
      email: 'override@quillmd.test',
      passwordHash: 'h',
    });
    expect(payload.where.email).toBe('override@quillmd.test');
    expect(payload.create.email).toBe('override@quillmd.test');
  });
});
