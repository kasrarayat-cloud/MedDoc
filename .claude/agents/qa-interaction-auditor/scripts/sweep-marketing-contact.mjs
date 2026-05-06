#!/usr/bin/env node
// sweep-marketing-contact.mjs — quillmd.com/contact (gate-check tier, v3.3).
//
// Tier: gate-check (server-rendered marketing contact page, no DB
// writes — see site-map.md "Walker tiers" section). NOTE: the spec
// described this as "the one marketing walker that has a destructive
// affordance" expecting a real form with a destination select. The
// page actually ships as a <dl> of mailto: links (no form, no submit
// button) — so the gate-check shape is "enumerate the mailto
// destinations and assert the four canonical categories are present."
// If the page is later upgraded to a real form, this walker grows from
// gate-check → preview-only and starts asserting form-field shape.
//
// Asserts: page renders + NavBar + Footer + "Get in touch" h1 + four
// canonical destination email addresses (support / sales / compliance
// / security) appear as mailto: links. Does NOT click the mailto links
// (would launch the OS mail client).

import { emit, launchBrowser, newMarketingContext, smokeLoad } from './lib/walker-base.mjs';

const NAME = 'marketing-contact';
const URL = '/contact';

const REQUIRED_DESTINATIONS = [
  'support@ashtechgroup.com',
  'sales@ashtechgroup.com',
  'compliance@ashtechgroup.com',
  'security@ashtechgroup.com',
];

const browser = await launchBrowser();
try {
  const ctx = await newMarketingContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: NAME });
  const result = await smokeLoad(page, URL);

  const checks = await page.evaluate(() => {
    const mailtos = Array.from(document.querySelectorAll('a[href^="mailto:"]'))
      .map((a) => (a.getAttribute('href') ?? '').replace(/^mailto:/i, '').trim());
    const formCount = document.querySelectorAll('form').length;
    const submitCount = document.querySelectorAll(
      'button[type="submit"], input[type="submit"]'
    ).length;
    const selectCount = document.querySelectorAll('select').length;
    return {
      hasNavBar: !!document.querySelector('header nav, [data-testid="nav-bar"], nav.top'),
      hasFooter: !!document.querySelector('footer'),
      hasH1: !!document.querySelector('main h1'),
      mailtoEmails: mailtos,
      // Surface form-shape so a future redesign that adds a form is
      // visible in the report (and prompts a tier promotion).
      formShape: { formCount, submitCount, selectCount },
    };
  });

  const presentDestinations = REQUIRED_DESTINATIONS.filter((d) =>
    checks.mailtoEmails.includes(d)
  );
  const missingDestinations = REQUIRED_DESTINATIONS.filter(
    (d) => !checks.mailtoEmails.includes(d)
  );

  emit({
    event: 'walker-result',
    name: NAME,
    url: URL,
    ok:
      !result.loadErr &&
      checks.hasNavBar &&
      checks.hasFooter &&
      checks.hasH1 &&
      missingDestinations.length === 0,
    ...result,
    chrome: { hasNavBar: checks.hasNavBar, hasFooter: checks.hasFooter },
    content: {
      hasH1: checks.hasH1,
      mailtoCount: checks.mailtoEmails.length,
      mailtoEmails: checks.mailtoEmails,
      requiredDestinations: REQUIRED_DESTINATIONS,
      presentDestinations,
      missingDestinations,
      formShape: checks.formShape,
    },
    note:
      checks.formShape.formCount === 0
        ? 'page is a mailto-link list, not a form — walker stays gate-check'
        : 'a real <form> appeared on /contact — promote walker to preview-only and assert field shape',
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
