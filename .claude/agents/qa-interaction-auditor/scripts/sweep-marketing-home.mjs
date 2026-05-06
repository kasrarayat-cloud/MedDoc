#!/usr/bin/env node
// sweep-marketing-home.mjs — quillmd.com/ landing page (gate-check tier, v3.3).
//
// Tier: gate-check (server-rendered marketing, no DB writes — see
// site-map.md "Walker tiers" section). Adding fake transactional
// assertions on a static landing page would be theatre, so the
// "deepest honest test" here is render + chrome + content presence.
//
// Asserts: page renders + home-page Nav (the home uses <nav class="top">
// rather than the sub-page <header><nav>) + Footer + hero h1 + at least
// one outbound CTA. Also emits outboundLinkCount as a regression-detector
// — if the count drifts unexpectedly, the report folds that into the diff.

import { emit, launchBrowser, newMarketingContext, smokeLoad } from './lib/walker-base.mjs';

const NAME = 'marketing-home';
const URL = '/';

const browser = await launchBrowser();
try {
  const ctx = await newMarketingContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: NAME });
  const result = await smokeLoad(page, URL);

  // Gate-check assertions: render + chrome + content. The home page's
  // chrome is <nav class="top"> (Hero/Nav.tsx), NOT the <header><nav>
  // shape used by sub-pages — match either so this stays robust if the
  // home Nav is ever harmonized with NavBar.
  const checks = await page.evaluate(() => ({
    hasNavBar: !!document.querySelector('header nav, [data-testid="nav-bar"], nav.top'),
    hasFooter: !!document.querySelector('footer'),
    hasHeroH1: !!document.querySelector('main h1'),
    hasGetStartedCta: !!Array.from(document.querySelectorAll('a, button'))
      .find((el) => /get started|start free|free trial/i.test((el.textContent ?? '').trim())),
    outboundLinks: Array.from(document.querySelectorAll('a[href]'))
      .map((a) => a.getAttribute('href'))
      .filter((h) => typeof h === 'string' && (h.startsWith('http') || h.startsWith('/'))),
  }));

  emit({
    event: 'walker-result',
    name: NAME,
    url: URL,
    ok:
      !result.loadErr &&
      checks.hasNavBar &&
      checks.hasFooter &&
      checks.hasHeroH1 &&
      checks.hasGetStartedCta,
    ...result,
    chrome: { hasNavBar: checks.hasNavBar, hasFooter: checks.hasFooter },
    content: {
      hasHeroH1: checks.hasHeroH1,
      hasGetStartedCta: checks.hasGetStartedCta,
    },
    outboundLinkCount: checks.outboundLinks.length,
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
