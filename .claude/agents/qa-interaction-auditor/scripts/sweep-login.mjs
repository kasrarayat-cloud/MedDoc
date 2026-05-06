#!/usr/bin/env node
// ============================================================================
// sweep-login.mjs — /login (preview-only tier, v3.3).
// ----------------------------------------------------------------------------
// Public route — agent walks anonymous. Page has a real sign-in form;
// submitting is the agent's own happy-path entry (every authenticated
// walker exercises that flow via getOrCreateAuthState). This walker's
// job is shape-assertion only: confirm the email + password + submit
// affordances are present, capture the submit-button label, enumerate
// the outbound links to /forgot-password and /signup. **Never submits.**
// ============================================================================

import { emit, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const URL = '/login';
const NAME = 'login';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: NAME, url: URL });
  const result = await smokeLoad(page, URL);

  // Preview-only assertions — shape, not behavior.
  const shape = await page.evaluate(() => ({
    hasForm: !!document.querySelector('form'),
    hasEmailInput: !!document.querySelector('input[type="email"]'),
    hasPasswordInput: !!document.querySelector('input[type="password"]'),
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
    label: shape.submitText ?? 'Sign in',
    reason:
      'walker is read-only — submit is exercised by every authenticated walker via getOrCreateAuthState',
  });

  emit({
    event: 'walker-result',
    name: NAME,
    url: URL,
    ok:
      !result.loadErr &&
      shape.hasEmailInput &&
      shape.hasPasswordInput &&
      shape.hasSubmit,
    ...result,
    shape,
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
