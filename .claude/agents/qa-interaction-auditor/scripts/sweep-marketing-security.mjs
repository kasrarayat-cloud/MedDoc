#!/usr/bin/env node
// sweep-marketing-security.mjs — quillmd.com/security (gate-check tier, v3.3).
//
// Tier: gate-check (server-rendered marketing legal-adjacent page, no
// DB writes — see site-map.md "Walker tiers" section). The page lists
// our security posture across Application / Infrastructure / Data
// handling / Operations / Certifications sections plus a security@
// contact email.
//
// Asserts: page renders + NavBar + Footer + "Security practices" h1 +
// the "Application" + "Infrastructure" section headings + the
// security@ashtechgroup.com contact code marker.

import { emit, launchBrowser, newMarketingContext, smokeLoad } from './lib/walker-base.mjs';

const NAME = 'marketing-security';
const URL = '/security';

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
      hasSecurityH1: lower.includes('security practices'),
      hasApplicationSection: lower.includes('application'),
      hasInfrastructureSection: lower.includes('infrastructure'),
      hasSecurityContact: bodyText.includes('security@ashtechgroup.com'),
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
      checks.hasSecurityH1 &&
      checks.hasApplicationSection &&
      checks.hasInfrastructureSection &&
      checks.hasSecurityContact,
    ...result,
    chrome: { hasNavBar: checks.hasNavBar, hasFooter: checks.hasFooter },
    content: {
      hasH1: checks.hasH1,
      hasSecurityH1: checks.hasSecurityH1,
      hasApplicationSection: checks.hasApplicationSection,
      hasInfrastructureSection: checks.hasInfrastructureSection,
      hasSecurityContact: checks.hasSecurityContact,
    },
    outboundLinkCount: checks.outboundLinks.length,
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
