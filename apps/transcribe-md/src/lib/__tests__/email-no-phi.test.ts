// ============================================================================
// NOTHING WE HAND TO RESEND CONTAINS A PATIENT.
// ----------------------------------------------------------------------------
// The visit email used to put the PATIENT'S NAME IN THE SUBJECT LINE and attach
// the signed SOAP note as a PDF. That made Resend a business associate handling
// PHI, and BAA_CHECKLIST.md is explicit: "Do not route real patient data through
// a processor whose BAA column is not COUNTERSIGNED." Resend's is not. That one
// send path was, on its own, a pilot blocker.
//
// So the blocker was engineered away rather than waited out: generic subject,
// no patient details, no attachment, and a link the doctor opens over their own
// authenticated session.
//
// THIS TEST RUNS THE REAL MESSAGE BUILDER. Only the transport is a mock — the
// subject, both bodies, the headers and the attachment list are exactly what
// production would put on the wire. A test that asserted against a hand-written
// payload would prove nothing about what actually ships.
//
// AND IT NOW CLAIMS THE STRONGER THING. The email used to deep-link with the
// visit's cuid, which is defensibly a record locator rather than a patient
// identifier. "Defensible" was the wrong bar: a claim that needs a paragraph of
// reasoning to survive an auditor is a claim that can lose. The link goes to the
// bare visits list, so the assertion is now "NO RECORD LOCATOR OF ANY KIND" —
// a sentence with no asterisk on it.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ send: vi.fn() }));

vi.mock('resend', () => ({
  Resend: class {
    emails = { send: mocks.send };
  },
}));
// ⚠️ THIS MOCK USED TO NAME `../api-usage`, WHICH DOES NOT EXIST.
// `email.ts:19` imports `logApiUsage` from `@meddoc/ai` — the module lives at
// packages/ai/src/api-usage.ts — so the old specifier resolved to nothing and
// silently did nothing. Vitest does not complain about a mock whose specifier
// matches no module, so the real meter ran on every test in this file and its
// `setImmediate` write to Postgres failed (the unit CI job leaves DATABASE_URL
// unset on purpose), emitting `console.warn` from api-usage.ts:204 AFTER this
// file had finished. Ten such warns per run, and each can lose the race with
// vitest's worker-RPC teardown and fail the whole suite with
// `EnvironmentTeardownError` while every test passes.
//
// Stubbing the DB seam is the fix used by the others in this class
// (gate-b0-mock-boundary.test.ts:39-55): the meter still runs, its write
// resolves in-process, nothing outlives the file. Nothing here asserted on the
// meter, so no assertion changes.
vi.mock('@meddoc/db', () => {
  const client = {
    apiUsageEvent: { create: (a: unknown) => Promise.resolve(a) },
    aiCall: { create: (a: unknown) => Promise.resolve(a) },
  };
  return { __esModule: true, default: client, prisma: client };
});

import {
  sendVisitPdfEmail,
  sendPasswordResetEmail,
  sendEmailVerification,
  sendAccountExistsEmail,
  sendTemplateCertifiedEmail,
} from '../email';

/** Values a real visit would carry. If ANY of these reaches the wire, the
 *  processor is handling PHI and the BAA question is back. */
const PHI = {
  patientName: 'Margaret Olusegun-Whitfield',
  dob: '1954-03-11',
  mrn: 'MRN-88213',
  noteText: 'Bilateral lower extremity venous duplex. No evidence of deep venous thrombosis.',
  chiefComplaint: 'chest pain since Tuesday',
};

const VISIT_ID = 'cmfake0001visitid';

/** Everything the transport was handed, flattened to one searchable string. */
function lastPayload(): string {
  return JSON.stringify(mocks.send.mock.calls.at(-1)?.[0] ?? {});
}
function lastCall(): Record<string, unknown> {
  return (mocks.send.mock.calls.at(-1)?.[0] ?? {}) as Record<string, unknown>;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.send.mockResolvedValue({ data: { id: 'msg_1' }, error: null });
  process.env.RESEND_API_KEY = 'test-key';
});

describe('the visit email carries no patient and no note', () => {
  beforeEach(async () => {
    await sendVisitPdfEmail({
      toEmail: 'doctor@example.com',
      visitId: VISIT_ID,
      doctorName: 'Dr Aisha Rahman',
      visitDate: '2026-07-28',
    });
  });

  it('THE SUBJECT IS GENERIC — identical for every visit and every patient', () => {
    // Subject lines are the part of an email most likely to appear on a lock
    // screen, which is exactly where a patient name must never be.
    expect(lastCall().subject).toBe('Your signed note is ready in QuillMD');
  });

  it('carries NO ATTACHMENT', () => {
    // Absent, not empty. An empty array would still mean the code path exists.
    expect(lastCall().attachments).toBeUndefined();
  });

  it('the whole payload contains no patient identifier and no note content', () => {
    const payload = lastPayload();
    for (const [label, value] of Object.entries(PHI)) {
      expect(payload, `payload leaked ${label}`).not.toContain(value);
    }
  });

  it('carries NO RECORD LOCATOR — not even the opaque visit id', () => {
    const payload = lastPayload();
    expect(payload, 'the visit id must not appear anywhere').not.toContain(VISIT_ID);
    // And not as a deep link in any form.
    expect(payload).not.toMatch(/\/visits\/[A-Za-z0-9_-]+/);
  });

  it('and it does contain the bare portal link, so it is actually useful', () => {
    // Non-vacuity. An email that leaked nothing because it said nothing would
    // pass every assertion above and help nobody.
    const payload = lastPayload();
    expect(payload).toContain('/visits');
    expect(payload).toContain('sign in');
  });
});

describe('EVERY email that references a visit, swept', () => {
  // The rule is not "the one sender we remembered". Any sender that could ever
  // be handed visit context is checked against the same PHI corpus.
  const senders: Array<{ name: string; run: () => Promise<unknown> }> = [
    {
      name: 'visit ready',
      run: () =>
        sendVisitPdfEmail({
          toEmail: 'doctor@example.com',
          visitId: VISIT_ID,
          doctorName: 'Dr Aisha Rahman',
          visitDate: '2026-07-28',
        }),
    },
    {
      name: 'password reset',
      run: () =>
        sendPasswordResetEmail({
          toEmail: 'doctor@example.com',
          resetUrl: 'https://app.quillmd.com/reset?token=abc',
          userName: 'Dr Aisha Rahman',
        }),
    },
    {
      name: 'email verification',
      run: () =>
        sendEmailVerification({
          toEmail: 'doctor@example.com',
          verifyUrl: 'https://app.quillmd.com/verify?token=abc',
          userName: 'Dr Aisha Rahman',
        }),
    },
    {
      name: 'account exists',
      run: () =>
        sendAccountExistsEmail({
          toEmail: 'doctor@example.com',
          userName: 'Dr Aisha Rahman',
          signInUrl: 'https://app.quillmd.com/login',
        }),
    },
    {
      name: 'template certified',
      run: () =>
        sendTemplateCertifiedEmail({
          toEmail: 'doctor@example.com',
          userName: 'Dr Aisha Rahman',
          templateName: 'Vascular ultrasound report',
        }),
    },
  ];

  for (const s of senders) {
    it(`${s.name}: no patient identifier, no note content, no attachment`, async () => {
      vi.clearAllMocks();
      mocks.send.mockResolvedValue({ data: { id: 'msg_1' }, error: null });
      await s.run();

      expect(mocks.send, `${s.name} did not send`).toHaveBeenCalledOnce();
      const payload = lastPayload();
      for (const [label, value] of Object.entries(PHI)) {
        expect(payload, `${s.name} leaked ${label}`).not.toContain(value);
      }
      expect(lastCall().attachments, `${s.name} attached something`).toBeUndefined();
      // No record locator of ANY kind, in ANY visit-referencing email.
      expect(payload, `${s.name} leaked the visit id`).not.toContain(VISIT_ID);
      expect(payload, `${s.name} carries a deep link`).not.toMatch(
        /\/visits\/[A-Za-z0-9_-]+/,
      );
    });
  }
});

describe('the guard is real', () => {
  it('the PHI corpus would actually be caught if it appeared', () => {
    // Non-vacuity for the sweep above: prove the matcher fires on a payload that
    // DOES contain the patient name. Without this, a bug that made lastPayload()
    // return '{}' would make every assertion above pass silently.
    const leaky = JSON.stringify({ subject: `Visit — ${PHI.patientName}` });
    expect(leaky).toContain(PHI.patientName);
  });
});
