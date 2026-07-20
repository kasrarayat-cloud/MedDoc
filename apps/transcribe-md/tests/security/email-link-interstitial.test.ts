// ============================================================================
// Email-link interstitial (Security Audit P1-K, 2026-05-13)
// ----------------------------------------------------------------------------
// verify-email + confirm-email used to mutate on GET. A user clicking
// the email link while another tab held a hostile origin would leak
// the (single-use, but unredeemed) token via Referer. The fix moves
// the mutation to a POST handler and renders an HTML interstitial on
// GET that auto-submits a same-origin POST while suppressing Referer.
//
// Verifies: (a) the interstitial helper produces well-formed HTML
// with the expected escaping + Referrer-Policy + noscript fallback;
// (b) both route files export GET that returns HTML + POST that
// consumes the token.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { emailLinkInterstitialHtml } from '@/lib/email-link-interstitial';

describe('emailLinkInterstitialHtml — helper output', () => {
  const html = emailLinkInterstitialHtml({
    actionPath: '/api/auth/verify-email',
    token: 'abc-1234567890',
    headline: 'Verifying your email…',
    detail: 'Hold on — finishing up.',
  });

  it('renders a POST form to the configured actionPath', () => {
    expect(html).toMatch(
      /<form[^>]+action="\/api\/auth\/verify-email"[^>]+method="POST"/
    );
  });

  it('includes the token in a hidden input', () => {
    expect(html).toMatch(/<input[^>]+name="token"[^>]+value="abc-1234567890"/);
  });

  it('auto-submits after a short delay (anti-prefetch)', () => {
    expect(html).toMatch(
      /setTimeout\(function\s*\(\)\s*\{[\s\S]*?\.submit\(\)/
    );
  });

  it('includes a <noscript> fallback button', () => {
    expect(html).toMatch(
      /<noscript>[\s\S]*?<button type="submit">[\s\S]*?<\/noscript>/
    );
  });

  it('escapes HTML metacharacters in headline/detail/token (XSS guard)', () => {
    const hostile = emailLinkInterstitialHtml({
      actionPath: '/p',
      token: 'a"><script>alert(1)</script>',
      headline: '<bad>',
      detail: '"evil"',
    });
    expect(hostile).not.toContain('<script>alert(1)</script>');
    expect(hostile).not.toContain('<bad>');
    expect(hostile).toContain('&lt;script&gt;');
    expect(hostile).toContain('&lt;bad&gt;');
  });

  it('marks the page noindex (anti-search-engine, anti-link-preview)', () => {
    expect(html).toMatch(/<meta name="robots" content="noindex, nofollow"/);
  });
});

const REPO_ROOT = resolve(__dirname, '..', '..', '..', '..');
function readRoute(rel: string): string {
  return readFileSync(resolve(REPO_ROOT, rel), 'utf-8');
}

describe('verify-email route — GET = interstitial, POST = mutation', () => {
  const src = readRoute(
    'apps/transcribe-md/src/app/api/auth/verify-email/route.ts'
  );

  it('exports BOTH GET and POST handlers', () => {
    expect(src).toMatch(/export\s+const\s+GET\s*=/);
    expect(src).toMatch(/export\s+const\s+POST\s*=/);
  });

  it('GET returns the interstitial HTML (no Prisma update)', () => {
    // The GET handler must NOT call prisma.user.update.
    const getBlock = src.slice(
      src.indexOf('export const GET ='),
      src.indexOf('export const POST =')
    );
    expect(getBlock).not.toMatch(/prisma\.user\.update/);
    expect(getBlock).toMatch(/emailLinkInterstitialHtml/);
    expect(getBlock).toMatch(/Referrer-Policy['"]\s*:\s*['"]no-referrer/);
  });

  it('POST locks and consumes the token in the emailVerified transaction', () => {
    const postBlock = src.slice(src.indexOf('export const POST ='));
    expect(postBlock).toMatch(/lockCurrentAuthTokenForMutation/);
    expect(postBlock).toMatch(/consumeLockedAuthToken/);
    expect(postBlock).toMatch(/tx\.user\.update/);
    expect(postBlock).toMatch(/emailVerified:\s*locked\.now/);
  });
});

describe('confirm-email route — GET = interstitial, POST = mutation', () => {
  const src = readRoute(
    'apps/transcribe-md/src/app/api/auth/confirm-email/route.ts'
  );

  it('exports BOTH GET and POST handlers', () => {
    expect(src).toMatch(/export\s+const\s+GET\s*=/);
    expect(src).toMatch(/export\s+const\s+POST\s*=/);
  });

  it('GET returns the interstitial HTML (no Prisma update)', () => {
    const getBlock = src.slice(
      src.indexOf('export const GET ='),
      src.indexOf('export const POST =')
    );
    expect(getBlock).not.toMatch(/prisma\.user\.update/);
    expect(getBlock).toMatch(/emailLinkInterstitialHtml/);
    expect(getBlock).toMatch(/Referrer-Policy['"]\s*:\s*['"]no-referrer/);
  });

  it('POST consumes EMAIL_CHANGE in the identity-mutation transaction', () => {
    const postBlock = src.slice(src.indexOf('export const POST ='));
    expect(postBlock).toMatch(/AuthTokenPurpose\.EMAIL_CHANGE/);
    expect(postBlock).toMatch(/lockCurrentAuthTokenForMutation/);
    expect(postBlock).toMatch(/consumeLockedAuthToken/);
    expect(postBlock).toMatch(/tx\.user\.update/);
    expect(postBlock).toMatch(/email:\s*newEmail/);
    expect(postBlock).toMatch(/oldEmail\s*!==\s*locked\.user\.email/);
  });
});
