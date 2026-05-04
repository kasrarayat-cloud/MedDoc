// Phase B verify — confirm pipeline completed (READY) and outputs render.
// Skips upload (already done in retry); polls /status endpoint instead of /api/visits/[id].
const fs = require('node:fs');
const path = require('node:path');
const {
  URL,
  SMOKE_DIR,
  shotPath,
  newSession,
  record,
} = require('./smoke-harness');

const PHASE = 'B';
const STORAGE_STATE = path.join(SMOKE_DIR, 'test-data', 'session-storage.json');
const { visitId } = JSON.parse(fs.readFileSync(path.join(SMOKE_DIR, 'phase-B', 'visit-id.json'), 'utf8'));

(async () => {
  const { browser, ctx, page } = await newSession();
  page.setDefaultTimeout(30000);
  await ctx.addCookies(JSON.parse(fs.readFileSync(STORAGE_STATE, 'utf8')).cookies);

  // Step 12 — confirm pipeline READY via /status
  await record(PHASE, '12-pipeline-wait', async () => {
    const tStart = Date.now();
    const maxWaitMs = 6 * 60 * 1000;
    let last = null;
    while (Date.now() - tStart < maxWaitMs) {
      const resp = await page.request.get(`${URL}/api/visits/${visitId}/status`);
      if (resp.ok()) {
        const d = await resp.json();
        if (d.status !== last) {
          console.log(`  [B] ${d.status}`);
          fs.appendFileSync(
            path.join(SMOKE_DIR, 'phase-B', 'pipeline-progress.log'),
            `${new Date().toISOString()} ${d.status} ${d.progressHint}\n`,
          );
          last = d.status;
        }
        if (d.status === 'READY' || d.status === 'SIGNED') {
          fs.writeFileSync(
            path.join(SMOKE_DIR, 'phase-B', 'pipeline-final.json'),
            JSON.stringify({ ...d, totalMs: Date.now() - tStart }, null, 2),
          );
          return;
        }
        if (d.status === 'FAILED') throw new Error(`pipeline FAILED: ${d.reviewReason}`);
      }
      await page.waitForTimeout(3000);
    }
    throw new Error(`pipeline did not reach READY in 6 min (last: ${last})`);
  });

  // Step 13-14 — verify outputs render
  await record(PHASE, '13-14-verify-outputs', async () => {
    await page.goto(`${URL}/visits/${visitId}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: shotPath(PHASE, '13a-visit-detail'), fullPage: true });

    const bodyText = await page.locator('body').innerText();
    const checks = {
      hasSubjective: /subjective|chief complaint|HPI/i.test(bodyText),
      hasObjective: /objective|exam|vitals/i.test(bodyText),
      hasAssessment: /assessment|impression/i.test(bodyText),
      hasPlan: /plan|recommend|disposition/i.test(bodyText),
      bodyLength: bodyText.length,
    };

    const tabs = ['Transcript', 'Codes', 'Rx', 'Extras'];
    for (const tab of tabs) {
      try {
        await page.getByRole('tab', { name: new RegExp(tab, 'i') }).click({ timeout: 3000 });
        await page.waitForTimeout(800);
        await page.screenshot({ path: shotPath(PHASE, `13b-tab-${tab.toLowerCase()}`), fullPage: true });
        checks[`tab_${tab}_clicked`] = true;
      } catch {
        checks[`tab_${tab}_missing`] = true;
      }
    }
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-B', 'output-checks.json'),
      JSON.stringify(checks, null, 2),
    );
  });

  await browser.close();
})().catch((e) => {
  console.error('phase B-verify FAIL:', e.stack || e.message);
  process.exit(1);
});
