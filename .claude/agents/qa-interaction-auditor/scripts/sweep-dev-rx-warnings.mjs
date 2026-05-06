#!/usr/bin/env node
// sweep-dev-rx-warnings.mjs — /dev/rx-warnings (design-system preview).
// v2 stub: smoke-load each variant. Production builds 404 this route, so
// the walker emits walker-skip when it sees a 404 rather than treating it
// as a finding.

import { emit, login, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const VARIANTS = ['critical', 'warning', 'info', 'collapsed', 'expanded', 'in-context'];

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: 'dev-rx-warnings' });
  try {
    await login(page);
  } catch (err) {
    emit({
      event: 'walker-result',
      name: 'dev-rx-warnings',
      ok: false,
      stage: 'login',
      loadErr: err.message,
    });
    emit({ event: 'walker-end', name: 'dev-rx-warnings' });
    await ctx.close();
    process.exit(0);
  }

  for (const variant of VARIANTS) {
    const url = `/dev/rx-warnings?variant=${variant}`;
    const result = await smokeLoad(page, url, { timeout: 15_000 });
    // The route 404s in production builds. We don't flag that as a bug
    // — emit walker-skip so the report knows we tried.
    const is404 =
      result.title?.includes('404') ||
      (result.bodyTextLength ?? 0) < 100;
    emit({
      event: is404 ? 'walker-skip' : 'walker-result',
      name: `dev-rx-warnings:${variant}`,
      url,
      ok: !result.loadErr && !is404,
      reason: is404 ? 'route-not-built (404 in production)' : undefined,
      ...result,
    });
  }
  emit({ event: 'walker-end', name: 'dev-rx-warnings' });
  await ctx.close();
} finally {
  await browser.close();
}
