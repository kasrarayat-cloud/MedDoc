#!/usr/bin/env node
// ============================================================================
// sweep-signup.mjs — /signup (preview-only tier, v3.3).
// ----------------------------------------------------------------------------
// Public route — agent walks anonymous. Page has a real self-service
// signup form (14-day trial); submitting would create a real user
// in the dev DB plus ping the verification-email pipeline. Walker
// confirms shape: name + email + password + confirmPassword fields +
// acceptTerms checkbox + submit, plus outbound link enumeration
// (back-to-login + ToS/privacy off-site). **Never submits.**
// ============================================================================

import { emit, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const URL = '/signup';
const NAME = 'signup';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: NAME, url: URL });
  const result = await smokeLoad(page, URL);

  // Preview-only assertions — shape, not behavior. Note: the form has
  // BOTH `password` and `confirmPassword` fields; client-side mismatch
  // check blocks submit, but we never click anyway.
  const shape = await page.evaluate(() => ({
    hasForm: !!document.querySelector('form'),
    hasNameInput: !!document.querySelector('input[name="name"]'),
    hasEmailInput: !!document.querySelector('input[type="email"]'),
    hasPasswordInput: !!document.querySelector('input[name="password"]'),
    hasConfirmPasswordInput: !!document.querySelector(
      'input[name="confirmPassword"]'
    ),
    hasAcceptTerms: !!document.querySelector(
      'input[type="checkbox"][name="acceptTerms"]'
    ),
    hasSubmit: !!document.querySelector('button[type="submit"]'),
    submitText:
      document.querySelector('button[type="submit"]')?.textContent?.trim() ?? null,
    outboundLinks: Array.from(document.querySelectorAll('a[href]'))
      .map((a) => ({
        href: a.getAttribute('href'),
        text: (a.textContent ?? '').trim().slice(0, 40),
      }))
      .filter(
        (l) => l.href && (l.href.startsWith('/') || l.href.startsWith('http'))
      ),
  }));

  emit({
    event: 'click-skipped',
    label: shape.submitText ?? 'Create account',
    reason:
      'walker is read-only — submit would create a real user + fire verification email',
  });

  emit({
    event: 'walker-result',
    name: NAME,
    url: URL,
    ok:
      !result.loadErr &&
      shape.hasNameInput &&
      shape.hasEmailInput &&
      shape.hasPasswordInput &&
      shape.hasConfirmPasswordInput &&
      shape.hasAcceptTerms &&
      shape.hasSubmit,
    ...result,
    shape,
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
