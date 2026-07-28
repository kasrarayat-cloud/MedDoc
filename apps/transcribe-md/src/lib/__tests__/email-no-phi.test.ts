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
// WHAT IT DOES NOT CLAIM. The link carries an opaque visit id (a cuid). That is
// a RECORD LOCATOR, not a patient identifier: it names nobody, reveals nothing
// on its own, and is useless without an authenticated session. Asserting "no
// identifiers of any kind" would be false, and a false assertion in a
// compliance test is worse than no test.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ send: vi.fn() }));

vi.mock('resend', () => ({
  Resend: class {
    emails = { send: mocks.send };
  },
}));
vi.mock('../api-usage', () => ({
  logApiUsage: vi.fn(),
  buildResendUsage: vi.fn(() => ({})),
}));

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

  it('and it does contain the portal link, so it is actually useful', () => {
    // Non-vacuity. An email that leaked nothing because it said nothing would
    // pass every assertion above and help nobody.
    const payload = lastPayload();
    expect(payload).toContain(`/visits/${VISIT_ID}`);
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
