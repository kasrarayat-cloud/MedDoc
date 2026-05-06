#!/usr/bin/env node
// sweep-admin-users.mjs — /admin/users (SUPER_ADMIN-gated).
// Same gate-test as sweep-admin-dashboard.mjs: DOCTOR should hit 404.

import { emit, login, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: 'admin-users' });
  try { await login(page); } catch (err) {
    emit({ event: 'walker-result', name: 'admin-users', ok: false, stage: 'login', loadErr: err.message });
    emit({ event: 'walker-end', name: 'admin-users' });
    await ctx.close();
    process.exit(0);
  }
  const result = await smokeLoad(page, '/admin/users');
  const looksGated = result.title?.includes('404') || (result.bodyTextLength ?? 0) < 200;
  emit({
    event: 'walker-result',
    name: 'admin-users',
    url: '/admin/users',
    ok: looksGated,
    note: looksGated ? 'expected 404 — SUPER_ADMIN gate working' : 'unexpected 200 — gate broken',
    ...result,
  });
  emit({ event: 'walker-end', name: 'admin-users' });
  await ctx.close();
} finally {
  await browser.close();
}
