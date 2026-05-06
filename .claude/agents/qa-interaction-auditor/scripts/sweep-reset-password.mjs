#!/usr/bin/env node
// ============================================================================
// sweep-reset-password.mjs — /reset-password (preview-only tier, v3.3).
// ----------------------------------------------------------------------------
// Public route — agent walks anonymous. Token-driven page: with a valid
// token in `?token=...` the form renders password + confirmPassword
// fields; with the empty/missing token branch the page renders a
// "missing token" fallback with a link back to /forgot-password.
//
// The walker hits the page with an obviously-fake test token so the
// FORM branch renders — that's the affordance shape we need to assert.
// Both branches must be considered "rendered without crashing"; the
// predicate accepts EITHER (a) the form-with-fields rendered or (b)
// the missing-token fallback rendered. Walker NEVER submits — that
// would either reset a real user's password (with a valid token) or
// generate noise in audit_logs (with an invalid one). **Never submits.**
// ============================================================================

import { emit, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const URL = '/reset-password?token=qa_smoke_invalid_token';
const NAME = 'reset-password';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: NAME, url: URL });
  const result = await smokeLoad(page, URL);

  // Preview-only assertions. With our test token the page renders the
  // form (token is non-empty so the early-return branch doesn't fire).
  // Submission would be rejected as invalid by the API anyway, but
  // we don't go that far.
  const shape = await page.evaluate(() => {
    const form = document.querySelector('form');
    return {
      hasForm: !!form,
      hasPasswordInput: !!document.querySelector(
        'input[name="password"][type="password"]'
      ),
      hasConfirmPasswordInput: !!document.querySelector(
        'input[name="confirmPassword"][type="password"]'
      ),
      hasSubmit: !!document.querySelector('button[type="submit"]'),
      submitText:
        document.querySelector('button[type="submit"]')?.textContent?.trim() ??
        null,
      // Missing-token fallback marker (renders only when no token in
      // the URL). With our token this should be false.
      hasMissingTokenFallback:
        (document.body.innerText ?? '').includes(
          'reset link is missing its token'
        ),
      outboundLinks: Array.from(document.querySelectorAll('a[href]'))
        .map((a) => ({
          href: a.getAttribute('href'),
          text: (a.textContent ?? '').trim().slice(0, 40),
        }))
        .filter(
          (l) => l.href && (l.href.startsWith('/') || l.href.startsWith('http'))
        ),
    };
  });

  emit({
    event: 'click-skipped',
    label: shape.submitText ?? 'Set new password',
    reason:
      'walker is read-only — submit would reset a real password (with valid token) or fire reject-noise in audit_logs (with invalid token)',
  });

  // Predicate: either the form branch rendered with both password
  // inputs, OR the missing-token fallback rendered. Anything else
  // means the page crashed or drifted shape.
  const formBranchOk =
    shape.hasForm && shape.hasPasswordInput && shape.hasConfirmPasswordInput;
  const fallbackBranchOk = shape.hasMissingTokenFallback;

  emit({
    event: 'walker-result',
    name: NAME,
    url: URL,
    ok: !result.loadErr && (formBranchOk || fallbackBranchOk),
    branch: formBranchOk ? 'form' : fallbackBranchOk ? 'missing-token' : 'unknown',
    ...result,
    shape,
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
