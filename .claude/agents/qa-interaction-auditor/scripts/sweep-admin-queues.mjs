#!/usr/bin/env node
// sweep-admin-queues.mjs — /admin/queues (PR-L; SUPER_ADMIN-gated; DOCTOR → 404).
//
// New in PR-L. Same gate-test as the other /admin/* walkers: the QA
// test user is DOCTOR, so the route should bounce off the SUPER_ADMIN
// gate via admin/layout.tsx's `notFound()` posture. A 200 here is a
// finding (gate broken). Read-only view; no clicks beyond the page
// load.

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
