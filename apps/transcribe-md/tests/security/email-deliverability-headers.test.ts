// ============================================================================
// Email deliverability headers (2026-05-13 — pre-pilot deliverability fix)
// ----------------------------------------------------------------------------
// Corporate domain deliverability investigation found that the apex
// SPF was missing (fixed via DNS) AND that we weren't sending
// `List-Unsubscribe` / `Reply-To` headers. Microsoft Exchange Online
// + Gmail measurably score senders higher when these headers are
// present, even on transactional mail. RFC 8058 § 3.2.
//
// The send-side helper builds the headers via `buildDeliverabilityHeaders`
// in `lib/email.ts`. The /api/email/unsubscribe endpoint is what
// receives the one-click POST from Gmail / Yahoo / Outlook. This file
// pins (a) the header shape, (b) the unsubscribe URL's POST response,
// (c) source-pin guards so a future edit can't drop the headers.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { buildDeliverabilityHeaders } from '@/lib/email';

const REPO_ROOT = resolve(__dirname, '..', '..', '..', '..');
function readSrc(rel: string): string {
  return readFileSync(resolve(REPO_ROOT, rel), 'utf-8');
}

describe('buildDeliverabilityHeaders — runtime shape (2026-05-13)', () => {
  it('emits List-Unsubscribe with mailto + https options (RFC 8058 §3.1)', () => {
    const h = buildDeliverabilityHeaders({ category: 'verify_email' });
    expect(h['List-Unsubscribe']).toMatch(/^<mailto:.+?>,\s*<https?:\/\/.+?>$/);
    expect(h['List-Unsubscribe']).toContain('mailto:');
    expect(h['List-Unsubscribe']).toContain('/api/email/unsubscribe?category=');
  });

  it('emits List-Unsubscribe-Post = One-Click (RFC 8058 §3.2)', () => {
    const h = buildDeliverabilityHeaders({ category: 'verify_email' });
    expect(h['List-Unsubscribe-Post']).toBe('List-Unsubscribe=One-Click');
  });

  it('emits X-Entity-Ref-ID with non-empty short random value', () => {
    const h1 = buildDeliverabilityHeaders({ category: 'verify_email' });
    const h2 = buildDeliverabilityHeaders({ category: 'verify_email' });
    expect(h1['X-Entity-Ref-ID']).toMatch(/^[a-z0-9]{8,32}$/i);
    // Two consecutive calls must produce different IDs (collision
    // resistance — purely operational, not security-load-bearing).
    expect(h1['X-Entity-Ref-ID']).not.toBe(h2['X-Entity-Ref-ID']);
  });

  it('scopes the unsubscribe URL to the category (escaped)', () => {
    const h = buildDeliverabilityHeaders({ category: 'password_reset' });
    expect(h['List-Unsubscribe']).toContain('category=password_reset');
  });

  it('produces stable header keys (case-sensitive per RFC 5322)', () => {
    const h = buildDeliverabilityHeaders({ category: 'verify_email' });
    expect(Object.keys(h).sort()).toEqual([
      'List-Unsubscribe',
      'List-Unsubscribe-Post',
      'X-Entity-Ref-ID',
    ]);
  });
});

describe('email.ts — sendOne wiring (source-pin)', () => {
  const SRC = readSrc('apps/transcribe-md/src/lib/email.ts');

  it('sendOne passes replyTo + headers to Resend', () => {
    // Whitespace-flexible. Both `replyTo: resendReplyTo()` and
    // `headers: buildDeliverabilityHeaders(...)` must reach the
    // client.emails.send call.
    expect(SRC).toMatch(
      /client\.emails\.send\(\s*\{[\s\S]+?replyTo:\s*resendReplyTo\(\)[\s\S]+?headers:\s*buildDeliverabilityHeaders\(\s*\{\s*category:[\s\S]+?\}\s*\)/,
    );
  });

  it('sendVisitPdfEmail uses the same deliverability headers (visit_pdf category)', () => {
    expect(SRC).toMatch(
      /sendVisitPdfEmail[\s\S]+?client\.emails\.send\(\s*\{[\s\S]+?headers:\s*buildDeliverabilityHeaders\(\s*\{\s*category:\s*['"]visit_pdf['"]/,
    );
  });

  it('every public sender passes a category to sendOne', () => {
    const categories = [
      'password_reset',
      'verify_email',
      'account_exists',
      'email_change_request',
      'email_changed_notification',
      'account_deleted',
    ];
    for (const cat of categories) {
      expect(
        SRC,
        `category ${cat} should appear in a sendOne call`,
      ).toMatch(new RegExp(`category:\\s*['"]${cat}['"]`));
    }
  });
});

describe('/api/email/unsubscribe — RFC 8058 one-click receiver (source-pin)', () => {
  const SRC = readSrc(
    'apps/transcribe-md/src/app/api/email/unsubscribe/route.ts',
  );

  it('exports BOTH GET and POST handlers', () => {
    expect(SRC).toMatch(/export\s+const\s+GET\s*=/);
    expect(SRC).toMatch(/export\s+const\s+POST\s*=/);
  });

  it('POST returns 200 (any 2xx satisfies RFC 8058 §3.2)', () => {
    const postBlock = SRC.slice(SRC.indexOf('export const POST ='));
    expect(postBlock).toMatch(/new\s+NextResponse\(\s*null\s*,\s*\{\s*status:\s*200/);
  });

  it('GET renders an HTML page (human-facing landing if a user clicks the mailto)', () => {
    const getBlock = SRC.slice(SRC.indexOf('export const GET ='));
    expect(getBlock).toMatch(/Content-Type['"]\s*:\s*['"]text\/html/);
    expect(getBlock).toMatch(/QuillMD/);
  });

  it('GET page is marked noindex (anti-search-engine)', () => {
    const getBlock = SRC.slice(SRC.indexOf('export const GET ='));
    expect(getBlock).toMatch(/X-Robots-Tag['"]?\s*:\s*['"]noindex, nofollow/);
  });

  it('handler is rate-limited via CLIENT_ERRORS bucket (generous, no auth)', () => {
    expect(SRC).toMatch(/RATE_LIMITS\.CLIENT_ERRORS/);
  });

  it('category param shape is validated via Zod regex (no XSS sink)', () => {
    expect(SRC).toMatch(
      /CategorySchema[\s\S]+?regex\(\/\^\[a-z_\]\+\$\/i/,
    );
  });
});

describe('/api/email/unsubscribe — runtime handler behavior', () => {
  it('POST returns 200 even when category param is missing (mail-provider probe)', async () => {
    const { POST } = await import('@/app/api/email/unsubscribe/route');
    const req = new Request('https://app.quillmd.com/api/email/unsubscribe', {
      method: 'POST',
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const res = await (POST as any)(req, {});
    expect(res.status).toBe(200);
  });

  it('POST returns 200 when category is malformed (Zod rejects; endpoint still 2xx)', async () => {
    // Mail providers MUST get a 2xx regardless of payload — they
    // don't pass our schema validation. The logger records the
    // (missing) tag so ops can detect drift.
    const { POST } = await import('@/app/api/email/unsubscribe/route');
    const req = new Request(
      'https://app.quillmd.com/api/email/unsubscribe?category=verify%40bad',
      { method: 'POST' },
    );
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const res = await (POST as any)(req, {});
    expect(res.status).toBe(200);
  });

  it('GET returns 200 + HTML even with no params (human navigation lands here)', async () => {
    const { GET } = await import('@/app/api/email/unsubscribe/route');
    const req = new Request('https://app.quillmd.com/api/email/unsubscribe');
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const res = await (GET as any)(req, {});
    expect(res.status).toBe(200);
    expect(res.headers.get('Content-Type')).toMatch(/text\/html/);
    const body = await res.text();
    expect(body).toContain('QuillMD');
  });
});

describe('appUrl — https-only enforcement (deliverability invariant)', () => {
  // The List-Unsubscribe URL must be https. Gmail ignores http URLs
  // in this header. Re-import the helper module fresh per-case so
  // env mutations don't leak across tests.
  it('falls back to https://app.quillmd.com when AUTH_URL is http (dev override)', async () => {
    const before = process.env.AUTH_URL;
    process.env.AUTH_URL = 'http://localhost:3011';
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const m = await import('@/lib/email');
      const h = m.buildDeliverabilityHeaders({ category: 'verify_email' });
      expect(h['List-Unsubscribe']).toMatch(/<https:\/\/app\.quillmd\.com\//);
      expect(h['List-Unsubscribe']).not.toMatch(/http:\/\/localhost/);
    } finally {
      if (before === undefined) delete process.env.AUTH_URL;
      else process.env.AUTH_URL = before;
    }
  });
});
