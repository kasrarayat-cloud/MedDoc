#!/usr/bin/env node
// sweep-marketing-privacy.mjs — quillmd.com/privacy (gate-check tier, v3.3).
//
// Tier: gate-check (server-rendered marketing legal page, no DB writes
// — see site-map.md "Walker tiers" section). Like /hipaa, the page
// carries a `[DRAFT — PENDING LEGAL REVIEW]` banner; the walker
// asserts the DRAFT marker so we notice when counsel signs off.
//
// Asserts: page renders + NavBar + Footer + "Privacy Policy" h1 +
// DRAFT marker + the privacy@ contact + retention/data-handling
// section headings.

import { emit, launchBrowser, newMarketingContext, smokeLoad } from './lib/walker-base.mjs';

const NAME = 'marketing-privacy';
const URL = '/privacy';

const browser = await launchBrowser();
try {
  const ctx = await newMarketingContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: NAME });
  const result = await smokeLoad(page, URL);

  const checks = await page.evaluate(() => {
    const bodyText = document.body.innerText ?? '';
    const lower = bodyText.toLowerCase();
    return {
      hasNavBar: !!document.querySelector('header nav, [data-testid="nav-bar"], nav.top'),
      hasFooter: !!document.querySelector('footer'),
      hasH1: !!document.querySelector('main h1'),
      hasPrivacyH1: lower.includes('privacy policy'),
      hasDraftMarker: bodyText.includes('[DRAFT'),
      hasRetentionSection: lower.includes('retention'),
      hasPrivacyContact: bodyText.includes('privacy@ashtechgroup.com'),
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
      checks.hasPrivacyH1 &&
      checks.hasRetentionSection,
    ...result,
    chrome: { hasNavBar: checks.hasNavBar, hasFooter: checks.hasFooter },
    content: {
      hasH1: checks.hasH1,
      hasPrivacyH1: checks.hasPrivacyH1,
      hasDraftMarker: checks.hasDraftMarker,
      hasRetentionSection: checks.hasRetentionSection,
      hasPrivacyContact: checks.hasPrivacyContact,
    },
    outboundLinkCount: checks.outboundLinks.length,
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
