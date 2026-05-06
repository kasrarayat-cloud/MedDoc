#!/usr/bin/env node
// sweep-admin-dashboard.mjs — /admin (gate-check tier, v3.3).
// SUPER_ADMIN-gated; QA test user is DOCTOR → admin/layout.tsx
// notFound() should fire. A 200 here = gate broken = finding.
// Read-only walker — page-load smoke + `looksGated` assertion
// (title contains "404"/"Not Found" OR body text < 200 chars).
// No clicks; no DB writes expected (the layout's access-audit log
// row is fired by the gate itself, not by the walker).
// Uses fresh `login(page)` not `getOrCreateAuthState` — the gate
// also enforces ≤12h session-freshness, so cached storageState
// risks tripping the freshness check rather than the role check.

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
