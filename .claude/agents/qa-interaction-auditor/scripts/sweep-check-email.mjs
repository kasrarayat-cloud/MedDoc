#!/usr/bin/env node
// sweep-check-email.mjs — /check-email (post-signup verification confirmation).

import { emit, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: 'check-email' });
  const result = await smokeLoad(
    page,
    '/check-email?email=qa-auditor%40quillmd.test'
  );
  emit({ event: 'walker-result', name: 'check-email', url: '/check-email', ok: !result.loadErr, ...result });
  emit({ event: 'walker-end', name: 'check-email' });
  await ctx.close();
} finally {
  await browser.close();
}
