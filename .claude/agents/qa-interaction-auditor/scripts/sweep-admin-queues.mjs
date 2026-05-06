#!/usr/bin/env node
// sweep-admin-queues.mjs — /admin/queues (gate-check tier, v3.3).
// New in PR-L (BullMQ queue health dashboard). SUPER_ADMIN-gated;
// QA test user is DOCTOR → admin/layout.tsx notFound() should fire.
// A 200 here = gate broken = finding.
// Reference walker for the gate-check tier (see site-map.md
// "Walker tiers"). Read-only — page-load smoke + `looksGated`
// assertion (title contains "404" OR body text < 200 chars).
// No clicks; uses fresh `login(page)` to keep the ≤12h session-
// freshness check satisfied (so a 404 here means the role gate
// fired, not the freshness gate).

import { emit, login, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: 'admin-queues' });
  try { await login(page); } catch (err) {
    emit({ event: 'walker-result', name: 'admin-queues', ok: false, stage: 'login', loadErr: err.message });
    emit({ event: 'walker-end', name: 'admin-queues' });
    await ctx.close();
    process.exit(0);
  }
  const result = await smokeLoad(page, '/admin/queues');
  const looksGated = result.title?.includes('404') || (result.bodyTextLength ?? 0) < 200;
  emit({
    event: 'walker-result',
    name: 'admin-queues',
    url: '/admin/queues',
    ok: looksGated,
    note: looksGated ? 'expected 404 — SUPER_ADMIN gate working' : 'unexpected 200 — gate broken',
    ...result,
  });
  emit({ event: 'walker-end', name: 'admin-queues' });
  await ctx.close();
} finally {
  await browser.close();
}
