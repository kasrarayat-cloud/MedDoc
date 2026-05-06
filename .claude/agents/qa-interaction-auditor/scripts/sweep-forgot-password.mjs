#!/usr/bin/env node
// sweep-forgot-password.mjs — /forgot-password (email-based recovery request).
// v2 stub: smoke-load anonymous. Never submits (would mail the test
// account; test inboxes don't exist for .test TLD anyway).

import { emit, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: 'forgot-password' });
  const result = await smokeLoad(page, '/forgot-password');
  emit({ event: 'walker-result', name: 'forgot-password', url: '/forgot-password', ok: !result.loadErr, ...result });
  emit({ event: 'walker-end', name: 'forgot-password' });
  await ctx.close();
} finally {
  await browser.close();
}
