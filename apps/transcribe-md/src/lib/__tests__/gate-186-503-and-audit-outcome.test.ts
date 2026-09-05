// ============================================================================
// #186 — THE 503 IS ACTUALLY SENT, AND THE AUDIT ROW AGREES WITH ITSELF
// ----------------------------------------------------------------------------
// Two defects found by an adversarial verification lens re-reading the AUTHOR'S
// OWN PROSE against the code, while composing §2.5 rows for a deploy. Neither
// was a regression; both were a fix that stopped one step short.
//
//   (a) `SessionUnverifiableError` declared `readonly status = 503` and three
//       comments said the request was "REFUSED (503)". NOTHING MAPPED IT TO A
//       RESPONSE. API callers got a generic 500 from the catch-all; page
//       requests got Next's 500 error boundary. The prose asserted a status the
//       system did not send, and a client could not tell "retry shortly" from
//       "this is broken".
//
//   (b) `recordLogoutAttempt` never passed `success`, and `logAudit` applies
//       `success: input.success ?? true`. So a FAILED sign-out was filed with
//       `success = true` while its own `metadata.outcome` said FAILED — the
//       indexed, greppable column disagreeing with the payload, silently.
//
// ⚠️ BOTH ARE THE SAME SHAPE: a claim that lived in a comment or a field and was
// never carried to the thing that answers. "A fix whose throw cannot escape its
// own function is not a fix" — this is the same rule one layer further out.
// ============================================================================
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));

const { SessionUnverifiableError, authConfig } = await import('@meddoc/auth');
const REPO = join(__dirname, '..', '..', '..', '..', '..');
const read = (p: string) => readFileSync(join(REPO, p), 'utf8');

describe('#186(a) — the 503 reaches the wire', () => {
  it('THE PAGE BOUNDARY: middleware answers with a real 503 Response', async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const authorized = (authConfig as any).callbacks.authorized;
    const prev = process.env.AUTH_USE_MOCK;
    process.env.AUTH_USE_MOCK = 'false';
    const res = await authorized({
      auth: { user: { sessionVerifyFailed: true } },
      request: { nextUrl: { pathname: '/dashboard' } },
    });
    process.env.AUTH_USE_MOCK = prev;

    expect(res).toBeInstanceOf(Response);
    expect((res as Response).status).toBe(503);
    expect((res as Response).headers.get('retry-after')).toBe('2');
  });

  it('THE API BOUNDARY maps the error to 503 rather than the catch-all 500', () => {
    // ⚠️ ASSERTED ON THE MAPPING'S SHAPE, and the wire status is asserted
    // behaviourally above. What matters here is that the branch exists BEFORE
    // the catch-all, because a catch-all placed first swallows it.
    const src = read('apps/transcribe-md/src/lib/api-error.ts');
    expect(src).toContain('err instanceof SessionUnverifiableError');
    const at503 = src.indexOf('err instanceof SessionUnverifiableError');
    const at500 = src.indexOf("apiError('internal server error', 500)");
    expect(at503).toBeGreaterThan(0);
    expect(
      at503 < at500,
      'the 503 branch is AFTER the catch-all 500, so it can never be reached',
    ).toBe(true);
    expect(src).toContain("apiError(\n          'session could not be verified");
    expect(src).toContain("'Retry-After', '2'");
  });

  it('the declared status and the sent status are the SAME number', () => {
    // The field that started the confusion is still there; now it must agree
    // with what is actually emitted, or the next reader inherits the same trap.
    const e = new SessionUnverifiableError('probe');
    expect(e.status).toBe(503);
  });
});

describe('#186(b) — a failed sign-out is audited as a failure', () => {
  const src = read('apps/transcribe-md/src/actions/session.ts');

  it('success is passed EXPLICITLY and derived from the outcome', () => {
    // ⚠️ NOT just "success appears somewhere" — it must be DERIVED from the
    // same value that fills metadata.outcome, or the two can drift apart again.
    expect(src).toContain("success: outcome === 'SUCCESS'");
  });

  it('⚠️ the row cannot disagree with itself — outcome and success share one source', () => {
    // Both fields must come from the single `outcome` parameter. If somebody
    // later hardcodes either one, this reds.
    const fn = src.slice(
      src.indexOf('async function recordLogoutAttempt'),
      src.indexOf('/** Who is signing out'),
    );
    expect(fn.length, 'recordLogoutAttempt was not located').toBeGreaterThan(200);
    expect(fn).toContain('metadata: { outcome, detail }');
    expect(fn).toContain("success: outcome === 'SUCCESS'");
    expect(fn, 'success is hardcoded — it can no longer track the outcome').not.toMatch(
      /success:\s*(true|false)\s*,/,
    );
  });

  it('NON-VACUITY: both outcomes are actually reachable in the caller', () => {
    // An arm about SUCCESS-vs-FAILED means nothing if only one is ever passed.
    expect(src).toMatch(/recordLogoutAttempt\('SUCCESS'/);
    expect(src).toMatch(/recordLogoutAttempt\('FAILED'/);
  });
});
