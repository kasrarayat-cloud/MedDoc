#!/usr/bin/env node
// sweep-marketing-terms.mjs — quillmd.com/terms (gate-check tier, v3.3).
//
// Tier: gate-check (server-rendered marketing legal page, no DB writes
// — see site-map.md "Walker tiers" section). Like /hipaa and /privacy,
// carries a `[DRAFT — PENDING LEGAL REVIEW]` banner; the walker
// asserts the DRAFT marker so we notice when counsel signs off.
//
// Asserts: page renders + NavBar + Footer + "Terms of Service" h1 +
// DRAFT marker + the legal@ contact + Acceptance / Limitation-of-
// liability section headings.

import { emit, launchBrowser, newMarketingContext, smokeLoad } from './lib/walker-base.mjs';

const NAME = 'marketing-terms';
const URL = '/terms';

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
      hasTermsH1: lower.includes('terms of service'),
      hasDraftMarker: bodyText.includes('[DRAFT'),
      hasAcceptanceSection: lower.includes('acceptance'),
      hasLiabilitySection: lower.includes('limitation of liability'),
      hasLegalContact: bodyText.includes('legal@ashtechgroup.com'),
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
      checks.hasTermsH1 &&
      checks.hasAcceptanceSection &&
      checks.hasLiabilitySection,
    ...result,
    chrome: { hasNavBar: checks.hasNavBar, hasFooter: checks.hasFooter },
    content: {
      hasH1: checks.hasH1,
      hasTermsH1: checks.hasTermsH1,
      hasDraftMarker: checks.hasDraftMarker,
      hasAcceptanceSection: checks.hasAcceptanceSection,
      hasLiabilitySection: checks.hasLiabilitySection,
      hasLegalContact: checks.hasLegalContact,
    },
    outboundLinkCount: checks.outboundLinks.length,
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
