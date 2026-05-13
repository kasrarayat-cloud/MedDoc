// ============================================================================
// Sentry event scrubber (Security Audit P1-B, 2026-05-13)
// ----------------------------------------------------------------------------
// scrubSentryEvent extends the redactPhi posture to every field on
// the Sentry event that the Next.js integration auto-attaches:
//   event.request.{data, url, query_string, headers, cookies}
//   event.user.{email, ip_address, username}
//   event.contexts
//   event.tags
// (event.message, event.extra, event.breadcrumbs.message were already
// covered before this fix.)
// ============================================================================

import { describe, expect, it, vi } from 'vitest';

import { scrubSentryEvent } from '@/lib/sentry-scrub';

// Stub redactPhi — returns a tagged marker so we can verify it was
// applied to each scrubbed field.
const redactPhi = vi.fn((input: unknown) => `[R:${String(input).slice(0, 40)}]`);

describe('scrubSentryEvent — request body / query / url', () => {
  it('strips query string from event.request.url', () => {
    const event: Record<string, unknown> = {
      request: { url: 'http://app.example.com/api/patients?search=Jane%20Doe' },
    };
    scrubSentryEvent(event, redactPhi);
    expect((event.request as { url: string }).url).toBe(
      'http://app.example.com/api/patients',
    );
  });

  it('drops event.request.query_string entirely', () => {
    const event: Record<string, unknown> = {
      request: { query_string: 'search=Jane' },
    };
    scrubSentryEvent(event, redactPhi);
    expect(event.request).not.toHaveProperty('query_string');
  });

  it('redacts event.request.data (POST body)', () => {
    const event: Record<string, unknown> = {
      request: { data: 'patient transcript and SOAP note contents here' },
    };
    scrubSentryEvent(event, redactPhi);
    expect((event.request as { data: string }).data).toMatch(/^\[R:/);
  });

  it('redacts event.request.data when it is an object (stringifies first)', () => {
    const event: Record<string, unknown> = {
      request: { data: { transcript: 'patient described back pain' } },
    };
    scrubSentryEvent(event, redactPhi);
    expect((event.request as { data: string }).data).toMatch(/^\[R:/);
  });
});

describe('scrubSentryEvent — request headers / cookies', () => {
  it('drops the full credential + IP-identifier header family (case-insensitive)', () => {
    const event: Record<string, unknown> = {
      request: {
        headers: {
          // Credential family
          Authorization: 'Bearer secret',
          'Proxy-Authorization': 'Bearer proxy',
          cookie: 'session=abc',
          'Set-Cookie': 'session=def',
          'X-CSRF-Token': 'token123',
          'x-api-key': 'apikey',
          'x-amz-security-token': 'sts',
          // IP-identifier family — HIPAA §164.514(b)
          'X-Forwarded-For': '203.0.113.42, 10.0.0.5',
          'x-real-ip': '203.0.113.99',
          Forwarded: 'for=192.0.2.43',
          'CF-Connecting-IP': '198.51.100.7',
          'True-Client-IP': '198.51.100.8',
          // Allowed (redacted, not dropped)
          'User-Agent': 'Mozilla/5.0',
        },
      },
    };
    scrubSentryEvent(event, redactPhi);
    const h = (event.request as { headers: Record<string, string> }).headers;
    expect(h).not.toHaveProperty('Authorization');
    expect(h).not.toHaveProperty('Proxy-Authorization');
    expect(h).not.toHaveProperty('cookie');
    expect(h).not.toHaveProperty('Set-Cookie');
    expect(h).not.toHaveProperty('X-CSRF-Token');
    expect(h).not.toHaveProperty('x-api-key');
    expect(h).not.toHaveProperty('x-amz-security-token');
    expect(h).not.toHaveProperty('X-Forwarded-For');
    expect(h).not.toHaveProperty('x-real-ip');
    expect(h).not.toHaveProperty('Forwarded');
    expect(h).not.toHaveProperty('CF-Connecting-IP');
    expect(h).not.toHaveProperty('True-Client-IP');
    // Survivors are redacted, not removed
    expect(h['User-Agent']).toMatch(/^\[R:/);
  });

  it('drops event.request.cookies entirely', () => {
    const event: Record<string, unknown> = {
      request: { cookies: { session: 'abc', mfa: 'def' } },
    };
    scrubSentryEvent(event, redactPhi);
    expect(event.request).not.toHaveProperty('cookies');
  });
});

describe('scrubSentryEvent — user PII', () => {
  it('drops email + ip_address + username from event.user (keeps short-string id)', () => {
    const event: Record<string, unknown> = {
      user: {
        id: 'cuid-123',
        email: 'doctor@clinic.com',
        username: 'jdoe',
        ip_address: '1.2.3.4',
      },
    };
    scrubSentryEvent(event, redactPhi);
    expect(event.user).toEqual({ id: 'cuid-123' });
  });

  it('strips user.id when it is suspiciously long (defense against future misuse)', () => {
    // Audit-recommended guard: a future caller passing an email or
    // free-text identifier as user.id would smuggle PII through the
    // scrubber. Reject any id longer than a typical cuid/uuid.
    const event: Record<string, unknown> = {
      user: { id: 'doctor@long-email-passed-as-id-which-is-much-too-long.example.com' },
    };
    scrubSentryEvent(event, redactPhi);
    expect(event.user).not.toHaveProperty('id');
  });

  it('strips user.id when it is not a string', () => {
    const event: Record<string, unknown> = { user: { id: { weird: true } } };
    scrubSentryEvent(event, redactPhi);
    expect(event.user).not.toHaveProperty('id');
  });
});

describe('scrubSentryEvent — contexts + tags', () => {
  it('walks event.contexts one level deep and redacts string values', () => {
    const event: Record<string, unknown> = {
      contexts: {
        visit: { id: 'v-1', transcript: 'long sentence here' },
      },
    };
    scrubSentryEvent(event, redactPhi);
    const ctx = (event.contexts as { visit: Record<string, string> }).visit;
    expect(ctx.id).toMatch(/^\[R:/);
    expect(ctx.transcript).toMatch(/^\[R:/);
  });

  it('redacts string values in event.tags', () => {
    const event: Record<string, unknown> = {
      tags: { practiceId: 'p1', patientName: 'Jane Doe' },
    };
    scrubSentryEvent(event, redactPhi);
    const t = event.tags as Record<string, string>;
    expect(t.practiceId).toMatch(/^\[R:/);
    expect(t.patientName).toMatch(/^\[R:/);
  });
});

describe('scrubSentryEvent — backwards compat (pre-existing scrubbing)', () => {
  it('still scrubs event.message + event.extra + breadcrumbs.message', () => {
    const event: Record<string, unknown> = {
      message: 'failure detail',
      extra: { hint: 'patient context blob' },
      breadcrumbs: [
        { message: 'crumb one' },
        { data: { note: 'inline note' } },
      ],
    };
    scrubSentryEvent(event, redactPhi);
    expect(event.message).toMatch(/^\[R:/);
    expect((event.extra as Record<string, string>).hint).toMatch(/^\[R:/);
    const crumbs = event.breadcrumbs as Array<{
      message?: string;
      data?: Record<string, string>;
    }>;
    expect(crumbs[0].message).toMatch(/^\[R:/);
    expect(crumbs[1].data?.note).toMatch(/^\[R:/);
  });

  it('no-ops on null/undefined fields without throwing', () => {
    const event: Record<string, unknown> = { request: { url: null } };
    expect(() => scrubSentryEvent(event, redactPhi)).not.toThrow();
  });
});
