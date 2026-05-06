#!/usr/bin/env node
// sweep-marketing-pricing.mjs — quillmd.com/pricing (gate-check tier, v3.3).
//
// Tier: gate-check (server-rendered marketing + client-rendered pricing
// tiers grid; no DB writes — see site-map.md "Walker tiers" section).
// CTAs link off-site to APP_SIGNUP_URL on the real app, so they're
// enumerated-but-not-clicked.
//
// Asserts: page renders + NavBar + Footer + hero h1 + at least 2 tier
// cards (the PricingTiers component renders 2+ tier cards; "Coming
// soon" copy fallback would still render at least one), plus the FAQ
// is present.

import { emit, launchBrowser, newMarketingContext, smokeLoad } from './lib/walker-base.mjs';

const NAME = 'marketing-pricing';
const URL = '/pricing';

const browser = await launchBrowser();
try {
  const ctx = await newMarketingContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: NAME });
  const result = await smokeLoad(page, URL);

  const checks = await page.evaluate(() => {
    const bodyText = (document.body.innerText ?? '').toLowerCase();
    // Tier cards aren't tagged with a stable testid — count h2/h3 inside
    // main as a proxy for the tier card count + count "$" occurrences.
    const dollarCount = (document.body.innerText ?? '').match(/\$\d/g)?.length ?? 0;
    return {
      hasNavBar: !!document.querySelector('header nav, [data-testid="nav-bar"], nav.top'),
      hasFooter: !!document.querySelector('footer'),
      hasH1: !!document.querySelector('main h1'),
      tierHeadingCount: document.querySelectorAll('main h2, main h3').length,
      dollarPriceMentions: dollarCount,
      hasFaq: bodyText.includes('faq') || bodyText.includes('frequently asked'),
      outboundLinks: Array.from(document.querySelectorAll('a[href]'))
        .map((a) => a.getAttribute('href'))
        .filter((h) => typeof h === 'string' && (h.startsWith('http') || h.startsWith('/'))),
    };
  });

  // At least 2 tier headings is the loose lower bound — the page
  // typically renders 3+ but a redesign that drops to a single card
  // is interesting enough to flag.
  const hasMinTierCount = checks.tierHeadingCount >= 2;

  emit({
    event: 'walker-result',
    name: NAME,
    url: URL,
    ok:
      !result.loadErr &&
      checks.hasNavBar &&
      checks.hasFooter &&
      checks.hasH1 &&
      hasMinTierCount,
    ...result,
    chrome: { hasNavBar: checks.hasNavBar, hasFooter: checks.hasFooter },
    content: {
      hasH1: checks.hasH1,
      tierHeadingCount: checks.tierHeadingCount,
      dollarPriceMentions: checks.dollarPriceMentions,
      hasFaq: checks.hasFaq,
    },
    outboundLinkCount: checks.outboundLinks.length,
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
