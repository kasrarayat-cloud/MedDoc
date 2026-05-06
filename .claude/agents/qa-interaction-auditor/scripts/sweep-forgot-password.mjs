#!/usr/bin/env node
// ============================================================================
// sweep-forgot-password.mjs — /forgot-password (preview-only tier, v3.3).
// ----------------------------------------------------------------------------
// Public route — agent walks anonymous. Page is a single-field email
// recovery form. Submitting would (a) fire a real password-reset email
// via the configured mailer and (b) tick the per-IP rate-limit bucket
// (5/hour/IP — sweep-all.mjs would burn that quota fast). Walker
// confirms shape: email field + submit + back-to-login link.
// **Never submits.**
// ============================================================================

import { emit, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const URL = '/forgot-password';
const NAME = 'forgot-password';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: NAME, url: URL });
  const result = await smokeLoad(page, URL);

  // Preview-only assertions — shape, not behavior. The page swaps
  // entirely after submit (form replaced by confirmation copy), so we
  // only ever see the pre-submit form.
  const shape = await page.evaluate(() => ({
    hasForm: !!document.querySelector('form'),
    hasEmailInput: !!document.querySelector('input[type="email"]'),
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
    label: shape.submitText ?? 'Send reset link',
    reason:
      'walker is read-only — submit fires a real reset email + ticks the per-IP rate-limit bucket (5/hour/IP)',
  });

  emit({
    event: 'walker-result',
    name: NAME,
    url: URL,
    ok:
      !result.loadErr && shape.hasEmailInput && shape.hasSubmit,
    ...result,
    shape,
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
