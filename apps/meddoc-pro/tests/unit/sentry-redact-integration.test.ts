// ============================================================================
// M7 — Sentry beforeSend PHI scrubbing (integration via redactPhi)
// ----------------------------------------------------------------------------
// Can't actually bring up the Sentry SDK in vitest cheaply; instead we
// test the shape we send to beforeSend ends up scrubbed via redactPhi.
// Both Sentry configs (MedDoc Pro + Scribe) use the same function; if
// the util contract holds, the integrations do too.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { redactPhi } from '@meddoc/ai';

// Minimal stand-in for the Sentry event shape we scrub in beforeSend.
interface SentryEventLike {
  message?: string;
  extra?: Record<string, unknown>;
  breadcrumbs?: { message?: string }[];
}

function scrub(event: SentryEventLike): SentryEventLike {
  if (typeof event.message === 'string') {
    event.message = redactPhi(event.message);
  }
  if (event.extra && typeof event.extra === 'object') {
    for (const k of Object.keys(event.extra)) {
      const v = event.extra[k];
      if (typeof v === 'string') event.extra[k] = redactPhi(v);
    }
  }
  if (Array.isArray(event.breadcrumbs)) {
    for (const c of event.breadcrumbs) {
      if (typeof c.message === 'string') c.message = redactPhi(c.message);
    }
  }
  return event;
}

describe('Sentry beforeSend PHI scrub', () => {
  it('collapses transcript-length messages to a length marker', () => {
    const transcript =
      'CLINICIAN: How long have you had this chest pain and does it radiate to your left arm or jaw. ' +
      'PATIENT: About an hour now, yes it goes to my left arm and up to my jaw.';
    const out = scrub({ message: transcript });
    expect(out.message).toMatch(/^\[REDACTED:\d+w\]$/);
    expect(out.message).not.toContain('chest pain');
  });

  it('masks email + phone + SSN in short messages without over-redacting', () => {
    const out = scrub({
      message: 'contact jane@clinic.com phone 415-555-0142 ssn 123-45-6789',
    });
    expect(out.message).toContain('[EMAIL]');
    expect(out.message).toContain('[PHONE]');
    expect(out.message).toContain('[SSN]');
    expect(out.message).not.toContain('jane@clinic.com');
  });

  it('scrubs string values in extra metadata, leaves non-string keys alone', () => {
    const out = scrub({
      extra: {
        visitId: 'v_123',
        chiefComplaint:
          'Patient reports severe chest pain radiating to the left arm and jaw, with nausea, sweating, and shortness of breath starting ten minutes ago after climbing one flight of stairs to reach the office today.',
        retryCount: 2,
      },
    });
    expect(out.extra!.visitId).toBe('v_123');
    expect(out.extra!.chiefComplaint).toMatch(/^\[REDACTED:\d+w\]$/);
    expect(out.extra!.retryCount).toBe(2);
  });

  it('scrubs breadcrumb messages', () => {
    const out = scrub({
      breadcrumbs: [
        { message: 'clicked Sign' },
        {
          message:
            'SOAP assessment: I10 Essential hypertension, E11.9 Type 2 diabetes, patient reports compliance with metformin 1000 twice daily and lisinopril 20 mg daily per history.',
        },
      ],
    });
    expect(out.breadcrumbs![0].message).toBe('clicked Sign');
    expect(out.breadcrumbs![1].message).toMatch(/^\[REDACTED:\d+w\]$/);
  });
});
