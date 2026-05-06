#!/usr/bin/env node
// sweep-marketing-hipaa.mjs — quillmd.com/hipaa (gate-check tier, v3.3).
//
// Tier: gate-check (server-rendered marketing compliance page, no DB
// writes — see site-map.md "Walker tiers" section). The page carries a
// `[DRAFT — PENDING LEGAL REVIEW]` banner that must stay until counsel
// signs off on the BAA template. The walker explicitly asserts the
// DRAFT marker is still present, so the day it's removed without a
// matching site-map.md update we get a finding.
//
// Asserts: page renders + NavBar + Footer + "HIPAA Compliance" h1 +
// the DRAFT marker + at least one BAA-related section heading.

import { emit, launchBrowser, newMarketingContext, smokeLoad } from './lib/walker-base.mjs';

const NAME = 'marketing-hipaa';
const URL = '/hipaa';

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
      hasHipaaH1: lower.includes('hipaa compliance'),
      hasDraftMarker: bodyText.includes('[DRAFT'),
      hasBaaSection: lower.includes('business associate agreement'),
      hasComplianceContact: bodyText.includes('compliance@ashtechgroup.com'),
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
      checks.hasHipaaH1 &&
      checks.hasDraftMarker &&
      checks.hasBaaSection,
    ...result,
    chrome: { hasNavBar: checks.hasNavBar, hasFooter: checks.hasFooter },
    content: {
      hasH1: checks.hasH1,
      hasHipaaH1: checks.hasHipaaH1,
      hasDraftMarker: checks.hasDraftMarker,
      hasBaaSection: checks.hasBaaSection,
      hasComplianceContact: checks.hasComplianceContact,
    },
    outboundLinkCount: checks.outboundLinks.length,
    note: checks.hasDraftMarker
      ? 'DRAFT banner still present — counsel review pending'
      : 'DRAFT banner removed without site-map update — verify legal review landed',
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
