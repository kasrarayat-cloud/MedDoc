/**
 * Administration console — real-browser walk, assertions and screenshots.
 *
 * Reproduces the evidence in docs/rebuild/admin-console-screenshots-20260921/ and asserts the
 * things that only a rendered page can establish. Two defects in this console reached a browser
 * before anything else caught them:
 *
 *   - `/console/audit/` returned a 500 because `audit()` takes `action` positionally and a detail
 *     named `action` collided with it. No unit test of the view's logic would have noticed.
 *   - `/console/?from=...` returned a 500 because `User` has `date_joined`, not `created_at`.
 *
 * so this walk requests every console route and fails on any status that is not 200.
 *
 * NOT WIRED INTO CI. It needs a running server, a seeded database and Playwright; the CI job that
 * has all three (`private-browser`) runs the clinician walk. Run it by hand against the isolated
 * stack:
 *
 *   cd rebuild && set -a && . <env> && set +a
 *   python manage.py migrate && python manage.py seed_private && python manage.py seed_admin_demo
 *   QUILLMD_ADMIN_SITE=1 gunicorn quillmd.wsgi:application --bind 127.0.0.1:9161 &
 *   node admin-console-browser.mjs .runtime/admin-console-browser
 *
 * Administrator MFA is NOT bypassed: it computes a real TOTP code from the confirmed authenticator
 * `seed_private` writes, exactly as browser-tests.mjs does.
 */
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';

const base = process.env.QUILLMD_ADMIN_BASE || 'http://127.0.0.1:9161';
const artifacts = process.argv[2] || path.join(process.cwd(), '.runtime', 'admin-console-browser');
const credentialPath = process.env.QUILLMD_BROWSER_CREDENTIALS
  || path.join(process.cwd(), '.runtime', 'private-access.json');

const results = [];
async function check(name, body) {
  try {
    await body();
    results.push({ name, ok: true });
    console.log(`  ok   ${name}`);
  } catch (error) {
    results.push({ name, ok: false, error: String(error && error.message || error) });
    console.log(`  FAIL ${name}\n       ${error && error.message}`);
  }
}

function totp(hex) {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const digest = crypto.createHmac('sha1', Buffer.from(hex, 'hex')).update(counter).digest();
  return String((digest.readUInt32BE(digest[digest.length - 1] & 15) & 0x7fffffff) % 1000000).padStart(6, '0');
}

const credentials = JSON.parse(await fs.readFile(credentialPath, 'utf8'));
await fs.mkdir(artifacts, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

await check('Administrator signs in with a real authenticator code', async () => {
  await page.goto(new URL('/login/', base).href);
  await page.locator('[name=email]').fill(credentials.admin.email);
  await page.locator('[name=password]').fill(credentials.admin.password);
  await page.locator('[name=otp]').fill(totp(credentials.admin.totp_key_hex));
  await Promise.all([page.waitForNavigation(), page.locator('form button[type=submit]').first().click()]);
  // `redirect('admin_dashboard')` resolves by NAME, and that name is registered on
  // `console/` before the bare `''` route, so the admin surface lands on /console/.
  // Both paths serve the same view when QUILLMD_ADMIN_SITE=1.
  assert.ok(['/', '/console/'].includes(new URL(page.url()).pathname), `landed on ${page.url()}`);
});

const account = await page.locator('#accounts a[href^="/console/accounts/"]').first().getAttribute('href');
const job = await page.locator('#jobs a[href^="/console/jobs/"]').first().getAttribute('href');

const routes = [
  ['01-overview', '/'],
  ['02-overview-dated', '/?from=2026-01-01&to=2036-01-01'],
  ['03-services', '/console/services/'],
  ['04-organizations', '/console/organizations/'],
  ['05-account', account],
  ['06-charge-evidence', job],
  ['07-audit', '/console/audit/'],
  ['08-jobs-awaiting-decision', '/?job_state=reconciliation'],
  ['09-unreadable-date', '/?from=banana&to=2026-09-21'],
];

for (const [name, target] of routes) {
  await check(`${name} answers 200 and is captured`, async () => {
    assert.ok(target, `${name}: no link found on the dashboard to follow`);
    const response = await page.goto(new URL(target, base).href, { waitUntil: 'networkidle' });
    assert.equal(response.status(), 200, `${target} answered ${response.status()}`);
    await page.screenshot({ path: path.join(artifacts, `${name}.png`), fullPage: true });
  });
}

await check('The reconciliation evidence picker offers BOTH authenticated evidence types', async () => {
  // A malformed closing tag (`</option value="provider_report">`) once left only 'invoice'
  // selectable, so a provider cost report could only be recorded as an invoice.
  await page.goto(new URL('/', base).href);
  const values = await page.$$eval('select[name=evidence_kind] option', (nodes) => nodes.map((n) => n.value));
  assert.ok(values.includes('provider_report'), `evidence types offered: ${JSON.stringify(values)}`);
  assert.ok(values.includes('invoice'));
});

await check('An unreadable date narrows nothing and the page says so', async () => {
  await page.goto(new URL('/?from=banana&to=2026-09-21', base).href);
  const body = await page.locator('#overview').innerText();
  assert.ok(body.includes('every record (no date window)'), 'the scope line still names a window');
  assert.ok(body.includes('The window was ignored'), 'no banner explaining why nothing narrowed');
});

await check('Backup status is never rendered as health when it was not published', async () => {
  await page.goto(new URL('/console/services/', base).href);
  const panel = await page.locator('#backups').innerText();
  assert.ok(/Never published|Computed|STALE/.test(panel),
    'the backup panel states none of the three outcomes it must distinguish');
  assert.ok(!/^\s*healthy\s*$/m.test(panel) || /Computed/.test(panel),
    'a healthy reading with no computed-at is not evidence of anything');
});

await check('No console page renders clinical text', async () => {
  for (const [, target] of routes) {
    if (!target) continue;
    await page.goto(new URL(target, base).href);
    const body = await page.locator('body').innerText();
    for (const marker of ['History:', 'Findings:', 'Synthetic Example']) {
      assert.ok(!body.includes(marker), `${target} rendered ${marker}`);
    }
  }
});

await browser.close();
await fs.writeFile(path.join(artifacts, 'result.json'), JSON.stringify({ base, results }, null, 2));
const failed = results.filter((row) => !row.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed; artifacts in ${artifacts}`);
if (failed.length) process.exit(1);
