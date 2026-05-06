#!/usr/bin/env node
// sweep-reset-password.mjs — /reset-password (token-based; expects ?token=).
// v2 stub: smoke-load with a bogus token; the page should render the
// error state for an invalid token. Future: full forgot-password →
// reset round-trip via mailpit.

import { emit, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: 'reset-password' });
  const result = await smokeLoad(
    page,
    '/reset-password?token=qa_smoke_invalid_token'
  );
  emit({
    event: 'walker-result',
    name: 'reset-password',
    url: '/reset-password',
    ok: !result.loadErr,
    note: 'walker passes a bogus token; expect error-state copy on the page',
    ...result,
  });
  emit({ event: 'walker-end', name: 'reset-password' });
  await ctx.close();
} finally {
  await browser.close();
}
