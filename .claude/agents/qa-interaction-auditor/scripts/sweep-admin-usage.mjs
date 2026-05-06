#!/usr/bin/env node
// sweep-admin-usage.mjs — /admin/usage (SUPER_ADMIN-gated; DOCTOR → 404).

import { emit, login, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: 'admin-usage' });
  try { await login(page); } catch (err) {
    emit({ event: 'walker-result', name: 'admin-usage', ok: false, stage: 'login', loadErr: err.message });
    emit({ event: 'walker-end', name: 'admin-usage' });
    await ctx.close();
    process.exit(0);
  }
  const result = await smokeLoad(page, '/admin/usage');
  const looksGated = result.title?.includes('404') || (result.bodyTextLength ?? 0) < 200;
  emit({
    event: 'walker-result',
    name: 'admin-usage',
    url: '/admin/usage',
    ok: looksGated,
    note: looksGated ? 'expected 404 — SUPER_ADMIN gate working' : 'unexpected 200 — gate broken',
    ...result,
  });
  emit({ event: 'walker-end', name: 'admin-usage' });
  await ctx.close();
} finally {
  await browser.close();
}
