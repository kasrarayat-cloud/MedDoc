#!/usr/bin/env node
// sweep-login.mjs — /login (sign-in form).
// Public route; the agent walks it as anonymous. v2 stub confirms the
// page renders + has the expected email + password fields. Does NOT
// submit (that's exercised by every authenticated walker).

import { emit, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: 'login', url: '/login' });
  const result = await smokeLoad(page, '/login');
  const fieldCheck = await page.evaluate(() => ({
    hasEmailInput: !!document.querySelector('input[type="email"]'),
    hasPasswordInput: !!document.querySelector('input[type="password"]'),
    hasSubmit: !!document.querySelector('button[type="submit"]'),
  }));
  emit({
    event: 'walker-result',
    name: 'login',
    url: '/login',
    ok: !result.loadErr && fieldCheck.hasEmailInput && fieldCheck.hasPasswordInput,
    ...result,
    ...fieldCheck,
  });
  emit({ event: 'walker-end', name: 'login' });
  await ctx.close();
} finally {
  await browser.close();
}
