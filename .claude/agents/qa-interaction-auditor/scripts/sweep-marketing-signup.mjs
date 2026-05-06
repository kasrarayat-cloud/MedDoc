#!/usr/bin/env node
// sweep-marketing-signup.mjs — quillmd.com/signup (gate-check tier, v3.3).
//
// Tier: gate-check (server-rendered redirect-only page, no DB writes —
// see site-map.md "Walker tiers" section). The route is a Next.js
// metadata-driven 1-second meta-refresh to APP_SIGNUP_URL (currently
// the IP-based public URL, will become app.quillmd.com/signup once DNS
// + TLS land). Real signup is exercised by sweep-signup.mjs against
// the app, not here.
//
// Asserts: page renders + NavBar + Footer + the meta-refresh tag
// targets the app's /signup. The walker uses domcontentloaded (NOT
// networkidle) and reads the meta tag synchronously to avoid races
// with the redirect itself.

import { emit, launchBrowser, newMarketingContext } from './lib/walker-base.mjs';

const NAME = 'marketing-signup';
const URL = '/signup';

const browser = await launchBrowser();
try {
  const ctx = await newMarketingContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: NAME });

  const t0 = Date.now();
  let loadErr = null;
  // Use domcontentloaded so we see the redirect page itself before the
  // meta-refresh kicks. networkidle would race and may bounce us off-
  // origin to the app.
  try {
    await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  } catch (e) {
    loadErr = e.message;
  }

  const checks = await page.evaluate(() => {
    const refreshMeta = document.querySelector('meta[http-equiv="refresh" i]');
    const refreshContent = refreshMeta?.getAttribute('content') ?? null;
    // Parse the URL portion of `<seconds>;url=<href>`.
    const refreshTarget = refreshContent
      ? (refreshContent.match(/url\s*=\s*(.+)$/i)?.[1] ?? '').trim()
      : null;
    return {
      hasNavBar: !!document.querySelector('header nav, [data-testid="nav-bar"], nav.top'),
      hasFooter: !!document.querySelector('footer'),
      hasMetaRefresh: !!refreshMeta,
      refreshContent,
      refreshTarget,
      // The Continue-to-signup button is the manual fallback.
      hasContinueCta: !!Array.from(document.querySelectorAll('a, button'))
        .find((el) => /continue to signup/i.test((el.textContent ?? '').trim())),
    };
  });

  // Assert the refresh targets a /signup endpoint. The current default
  // is http://5.231.107.93:9020/signup; once DNS lands it'll be
  // https://app.quillmd.com/signup. Either shape is OK — the
  // load-bearing piece is "/signup" path on the app host (not the
  // marketing host).
  const refreshTargetsAppSignup =
    typeof checks.refreshTarget === 'string' &&
    /\/signup\b/.test(checks.refreshTarget) &&
    !checks.refreshTarget.startsWith('/'); // must be absolute (cross-origin)

  emit({
    event: 'walker-result',
    name: NAME,
    url: URL,
    ok:
      !loadErr &&
      checks.hasNavBar &&
      checks.hasFooter &&
      checks.hasMetaRefresh &&
      refreshTargetsAppSignup,
    durationMs: Date.now() - t0,
    loadErr,
    chrome: { hasNavBar: checks.hasNavBar, hasFooter: checks.hasFooter },
    redirect: {
      hasMetaRefresh: checks.hasMetaRefresh,
      refreshContent: checks.refreshContent,
      refreshTarget: checks.refreshTarget,
      targetsAppSignup: refreshTargetsAppSignup,
    },
    content: { hasContinueCta: checks.hasContinueCta },
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
