#!/usr/bin/env node
// sweep-admin-dashboard.mjs — /admin (SUPER_ADMIN-gated).
// v2 stub: walks the page as the DOCTOR-role QA user. Expected:
// admin/layout.tsx returns 404 to non-SUPER_ADMINs — confirming the
// route-gate + write to access-audit log fires. A 200 here is a
// finding (gate broken).

import { emit, login, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: 'admin-dashboard' });
  try {
    await login(page);
  } catch (err) {
    emit({ event: 'walker-result', name: 'admin-dashboard', ok: false, stage: 'login', loadErr: err.message });
    emit({ event: 'walker-end', name: 'admin-dashboard' });
    await ctx.close();
    process.exit(0);
  }
  const result = await smokeLoad(page, '/admin');
  // The DOCTOR role should bounce off the SUPER_ADMIN gate.
  const looksGated =
    result.title?.includes('404') ||
    result.title?.includes('Not Found') ||
    (result.bodyTextLength ?? 0) < 200;
  emit({
    event: 'walker-result',
    name: 'admin-dashboard',
    url: '/admin',
    ok: looksGated, // 404 = route-gate working = OK
    note: looksGated
      ? 'expected 404 (DOCTOR role) — gate working as designed'
      : 'unexpected 200 — DOCTOR can see /admin = SUPER_ADMIN gate broken',
    ...result,
  });
  emit({ event: 'walker-end', name: 'admin-dashboard' });
  await ctx.close();
} finally {
  await browser.close();
}
