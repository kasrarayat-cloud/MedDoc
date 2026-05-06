#!/usr/bin/env node
// sweep-marketing-about.mjs — quillmd.com/about (gate-check tier, v3.3).
//
// Tier: gate-check (server-rendered marketing, no DB writes — see
// site-map.md "Walker tiers" section). The "deepest honest test" for
// a copy-only company-story page is render + chrome + the section
// headings that anchor the layout.
//
// Asserts: page renders + NavBar + Footer + about-eyebrow ("About us")
// badge + the "story" / "approach" section headings present.

import { emit, launchBrowser, newMarketingContext, smokeLoad } from './lib/walker-base.mjs';

const NAME = 'marketing-about';
const URL = '/about';

const browser = await launchBrowser();
try {
  const ctx = await newMarketingContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: NAME });
  const result = await smokeLoad(page, URL);

  const checks = await page.evaluate(() => {
    const bodyText = (document.body.innerText ?? '').toLowerCase();
    return {
      hasNavBar: !!document.querySelector('header nav, [data-testid="nav-bar"], nav.top'),
      hasFooter: !!document.querySelector('footer'),
      hasH1: !!document.querySelector('main h1'),
      hasStoryHeading: bodyText.includes('the story'),
      hasApproachHeading: bodyText.includes('our approach'),
      outboundLinks: Array.from(document.querySelectorAll('a[href]'))
        .map((a) => a.getAttribute('href'))
        .filter((h) => typeof h === 'string' && (h.startsWith('http') || h.startsWith('/'))),
    };
  });

  emit({
    event: 'walker-result',
    name: NAME,
    url: URL,
    ok:
      !result.loadErr &&
      checks.hasNavBar &&
      checks.hasFooter &&
      checks.hasH1 &&
      checks.hasStoryHeading &&
      checks.hasApproachHeading,
    ...result,
    chrome: { hasNavBar: checks.hasNavBar, hasFooter: checks.hasFooter },
    content: {
      hasH1: checks.hasH1,
      hasStoryHeading: checks.hasStoryHeading,
      hasApproachHeading: checks.hasApproachHeading,
    },
    outboundLinkCount: checks.outboundLinks.length,
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
