#!/usr/bin/env node
// sweep-signup.mjs — /signup (self-service; 14-day trial).
// v2 stub: smoke-load anonymous; assert form fields present. Never
// SUBMITS — would create real users in the dev DB.

import { emit, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: 'signup' });
  const result = await smokeLoad(page, '/signup');
  emit({ event: 'walker-result', name: 'signup', url: '/signup', ok: !result.loadErr, ...result });
  emit({ event: 'walker-end', name: 'signup' });
  await ctx.close();
} finally {
  await browser.close();
}
