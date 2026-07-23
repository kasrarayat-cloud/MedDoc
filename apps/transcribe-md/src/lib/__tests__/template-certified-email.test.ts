// ============================================================================
// Stage 3 — certified-template email. Plain, human copy; links to the note-
// format settings page; no internal jargon. This test captures the exact Resend
// payload and asserts the copy contract without sending anything.
// ============================================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const sendMock = vi.hoisted(() =>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  vi.fn(async (_payload: any) => ({ data: { id: 'em_test' }, error: null })),
);

vi.mock('resend', () => ({
  Resend: class {
    emails = { send: sendMock };
  },
}));
vi.mock('@meddoc/ai', () => ({
  logApiUsage: vi.fn(),
  buildResendUsage: vi.fn(() => ({})),
}));

import { sendTemplateCertifiedEmail } from '../email';

describe('sendTemplateCertifiedEmail', () => {
  beforeEach(() => {
    sendMock.mockClear();
    process.env.RESEND_API_KEY = 'test_key';
    process.env.AUTH_URL = 'https://app.quillmd.com';
  });
  afterEach(() => {
    delete process.env.RESEND_API_KEY;
  });

  it('links to the note-format settings page and greets the doctor', async () => {
    await sendTemplateCertifiedEmail({
      toEmail: 'doc@clinic.test',
      userName: 'Dr. Ada Lovelace',
      templateName: 'Venous Duplex Ultrasound Note',
    });
    expect(sendMock).toHaveBeenCalledOnce();
    const payload = sendMock.mock.calls[0][0] as unknown as { to: string; subject: string; html: string; text: string; headers: Record<string, string> };
    expect(payload.to).toBe('doc@clinic.test');
    expect(payload.html).toContain('https://app.quillmd.com/settings/note-format');
    expect(payload.text).toContain('https://app.quillmd.com/settings/note-format');
    expect(payload.html).toContain('Hi Dr. Ada Lovelace,');
    expect(payload.html).toContain('Venous Duplex Ultrasound Note');
    expect(payload.text).toContain('Venous Duplex Ultrasound Note');
    expect(payload.headers['List-Unsubscribe']).toContain('template_certified');
  });

  it('carries NO internal jargon (twin / IR / mapping / compiled / content control / synthetic)', async () => {
    await sendTemplateCertifiedEmail({
      toEmail: 'd@x.test',
      userName: null,
      templateName: 'My Note Format',
    });
    const payload = sendMock.mock.calls[0][0] as unknown as { html: string; text: string };
    const blob = `${payload.html}\n${payload.text}`;
    expect(blob).not.toMatch(/\btwin\b|\bIR\b|\bmapping\b|compiled|content control|synthetic|semantic|resolver|certif/i);
  });

  it('HTML-escapes a hostile template name (no raw markup in the body)', async () => {
    await sendTemplateCertifiedEmail({
      toEmail: 'd@x.test',
      userName: null,
      templateName: '<script>alert(1)</script>',
    });
    const payload = sendMock.mock.calls[0][0] as unknown as { html: string };
    expect(payload.html).not.toContain('<script>');
    expect(payload.html).toContain('&lt;script&gt;');
  });

  it('falls back to a neutral name when the template name is blank', async () => {
    await sendTemplateCertifiedEmail({ toEmail: 'd@x.test', userName: null, templateName: '   ' });
    const payload = sendMock.mock.calls[0][0] as unknown as { html: string };
    expect(payload.html).toContain('Your note format');
  });
});
