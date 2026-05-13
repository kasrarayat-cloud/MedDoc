// ============================================================================
// POST/GET /api/email/unsubscribe — one-click unsubscribe (RFC 8058)
// ----------------------------------------------------------------------------
// Every transactional email we send carries a `List-Unsubscribe` header
// pointing at this endpoint (set in `apps/transcribe-md/src/lib/email.ts`
// via `buildDeliverabilityHeaders`). Gmail / Yahoo / Microsoft check
// that the URL responds with 2xx — both periodically to keep the
// sender's reputation healthy, and on user click (Gmail's
// "Unsubscribe" button next to the From address). Missing or broken
// endpoint here measurably hurts deliverability even though no real
// user ever clicks for a transactional flow.
//
// What we DON'T do here:
//   - Record the recipient in a suppression list. Our outbound is 100%
//     transactional (signup verification, password reset, email change
//     confirmation, account-deletion confirmation, signed-visit PDF).
//     A user can't opt out of "please verify your email" — the
//     alternative is account abandonment. The honest UX is to delete
//     the account, which is offered on /settings.
//
// What we DO:
//   - Return 200 for the POST so Gmail's one-click probe + actual
//     click both succeed cleanly.
//   - Log every attempt (no PHI — we don't know the recipient identity
//     from this surface; only the category passed in the URL). This
//     gives ops a signal if a flood of unsubscribe clicks suddenly
//     appears on one category — that's a content / frequency problem
//     worth investigating.
//   - Render a polite GET page that explains the situation + points
//     to /settings for the actual account-management path.
//
// Security audit P1-K-adjacent: this endpoint is intentionally
// unauthenticated. Gmail's prefetch will hit it without a session
// cookie. We don't accept any PII via this endpoint — the category is
// the only param and it's just a string label.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import { withApiHandler } from '@/lib/api-error';
import {
  RATE_LIMITS,
  clientIpFromRequest,
  rateLimitOr429,
} from '@/lib/rate-limit';
import { log } from '@/lib/log';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const CategorySchema = z
  .string()
  .min(1)
  .max(40)
  .regex(/^[a-z_]+$/i, 'category must be lowercase letters + underscores');

function logAttempt(req: Request, source: 'GET' | 'POST'): string {
  const url = new URL(req.url);
  const rawCat = url.searchParams.get('category');
  const parsed = CategorySchema.safeParse(rawCat);
  const category = parsed.success ? parsed.data : '(missing)';
  log.info('email:unsubscribe', `${source} click`, {
    category,
    // No recipient identifier — this endpoint doesn't know who
    // clicked. That's intentional; we don't tie the click to a user.
    userAgent: req.headers.get('user-agent')?.slice(0, 200) ?? null,
  });
  return category;
}

export const POST = withApiHandler('api:email:unsubscribe', async (req) => {
  // RFC 8058 one-click: Gmail / Yahoo / Outlook POST here. The IP-
  // scoped rate limit is generous — these endpoints get probed by
  // mail providers AND clicked by humans; both are legitimate.
  const blocked = rateLimitOr429(
    RATE_LIMITS.CLIENT_ERRORS,
    clientIpFromRequest(req)
  );
  if (blocked) return blocked;

  logAttempt(req, 'POST');
  // Any 2xx is fine per RFC 8058 §3.2. We return 200 with an empty
  // body — the user agent here is a mail provider, no UI needed.
  return new NextResponse(null, { status: 200 });
});

export const GET = withApiHandler('api:email:unsubscribe', async (req) => {
  const blocked = rateLimitOr429(
    RATE_LIMITS.CLIENT_ERRORS,
    clientIpFromRequest(req)
  );
  if (blocked) return blocked;

  logAttempt(req, 'GET');
  // Polite landing page when a human clicks the mailto: / link.
  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex, nofollow" />
  <title>QuillMD — Unsubscribe</title>
  <style>
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; background: #fafafa; color: #111; }
    .wrap { max-width: 480px; margin: 96px auto; padding: 32px; background: #fff; border: 1px solid #eaeaea; border-radius: 10px; }
    h1 { font-size: 19px; margin: 0 0 12px; font-weight: 600; }
    p { font-size: 14px; line-height: 1.5; color: #444; margin: 0 0 16px; }
    a { color: #5b21b6; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>QuillMD — about that unsubscribe</h1>
    <p>QuillMD only sends transactional email tied to your account: signup verification, password reset, and confirmation of changes you initiated. We don't have marketing newsletters or recurring digests to unsubscribe from.</p>
    <p>If you'd like to stop receiving any QuillMD email, you can delete your account on the <a href="/settings">settings page</a>. That removes the account and ends the transactional thread.</p>
    <p>If you got an email you didn't expect (e.g., someone tried to sign up with your address), no further action is required — that email is the only one you'll receive unless they successfully verify and you set a password.</p>
  </div>
</body>
</html>`;
  return new NextResponse(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'X-Robots-Tag': 'noindex, nofollow',
    },
  });
});
