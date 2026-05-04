// Phase G — mobile (iPhone 13 viewport) (steps 38-40).
// Validates: dashboard renders, visit detail renders, navigation works on mobile.
const fs = require('node:fs');
const path = require('node:path');
const {
  URL,
  SMOKE_DIR,
  shotPath,
  newSession,
  record,
} = require('./smoke-harness');

const PHASE = 'G';
const STORAGE_STATE = path.join(SMOKE_DIR, 'test-data', 'session-storage.json');

(async () => {
  // newSession({ mobile: true }) → iPhone 13 device profile
  const { browser, ctx, page } = await newSession({ mobile: true });
  page.setDefaultTimeout(20000);
  await ctx.addCookies(JSON.parse(fs.readFileSync(STORAGE_STATE, 'utf8')).cookies);

  // Step 38 — mobile dashboard
  await record(PHASE, '38-mobile-dashboard', async () => {
    await page.goto(`${URL}/dashboard`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: shotPath(PHASE, '38a-mobile-dashboard'), fullPage: true });
    const viewport = page.viewportSize();
    const bodyText = await page.locator('body').innerText();
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-G', 'mobile-dashboard.json'),
      JSON.stringify({
        viewport,
        renderedChars: bodyText.length,
        hasNav: await page.locator('nav, [role="navigation"]').count() > 0,
        hasMobileMenuBtn: await page.locator('button[aria-label*="menu" i], button:has(svg)').count(),
      }, null, 2),
    );
  });

  // Step 39 — mobile visit detail (use Phase B's visit)
  await record(PHASE, '39-mobile-visit-detail', async () => {
    const visitB = JSON.parse(fs.readFileSync(path.join(SMOKE_DIR, 'phase-B', 'visit-id.json'), 'utf8'));
    if (!visitB.visitId) {
      fs.writeFileSync(
        path.join(SMOKE_DIR, 'phase-G', 'finding-39.json'),
        JSON.stringify({ skip: 'no Phase B visit available' }),
      );
      return;
    }
    await page.goto(`${URL}/visits/${visitB.visitId}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: shotPath(PHASE, '39a-mobile-visit'), fullPage: true });
    const bodyText = await page.locator('body').innerText();
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-G', 'mobile-visit.json'),
      JSON.stringify({
        visitId: visitB.visitId,
        soapVisible: /assessment|impression/i.test(bodyText) && /plan|recommend/i.test(bodyText),
        bodyChars: bodyText.length,
      }, null, 2),
    );
  });

  // Step 40 — mobile navigation: visits → patients → settings
  await record(PHASE, '40-mobile-navigation', async () => {
    const routes = ['/visits', '/patients', '/settings'];
    const results = [];
    for (const r of routes) {
      const t0 = Date.now();
      const resp = await page.goto(`${URL}${r}`, { waitUntil: 'networkidle' }).catch((e) => null);
      const ok = resp ? resp.ok() : false;
      await page.screenshot({ path: shotPath(PHASE, `40a-mobile-${r.replace(/\//g, '-')}`), fullPage: true });
      results.push({ route: r, ok, status: resp ? resp.status() : null, ms: Date.now() - t0 });
    }
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-G', 'mobile-nav.json'),
      JSON.stringify(results, null, 2),
    );
  });

  await browser.close();
})().catch((e) => {
  console.error('phase G FAIL:', e.stack || e.message);
  process.exit(1);
});
