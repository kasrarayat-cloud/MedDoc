#!/usr/bin/env node
// sweep-marketing-demo.mjs — quillmd.com/demo (gate-check tier, v3.3).
//
// Tier: gate-check (server-rendered marketing placeholder, no DB writes
// — see site-map.md "Walker tiers" section). The page is currently a
// "Coming soon" placeholder with a CTA back to APP_SIGNUP_URL; when
// the real demo video lands, this walker should grow content checks
// for the player wrapper.
//
// Asserts: page renders + NavBar + Footer + hero h1 + the "Coming soon"
// placeholder copy is present (so we notice when the demo finally
// ships and this assertion starts to fail).

import { emit, launchBrowser, newMarketingContext, smokeLoad } from './lib/walker-base.mjs';

const NAME = 'marketing-demo';
const URL = '/demo';

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
      // "Coming soon" badge + "Video coming soon" copy live in the
      // placeholder card. Either is fine as the marker; presence of
      // both is the steady-state.
      hasComingSoonBadge: bodyText.includes('coming soon'),
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
      checks.hasComingSoonBadge,
    ...result,
    chrome: { hasNavBar: checks.hasNavBar, hasFooter: checks.hasFooter },
    content: {
      hasH1: checks.hasH1,
      hasComingSoonBadge: checks.hasComingSoonBadge,
    },
    outboundLinkCount: checks.outboundLinks.length,
    note: checks.hasComingSoonBadge
      ? 'placeholder still in place — promote walker when real demo lands'
      : 'coming-soon copy missing — demo may have shipped; review walker assertions',
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
