/**
 * Private synthetic browser regression gate.
 *
 * Start a fixture-mode doctor server and worker after migrate, collectstatic, and
 * seed_private. Run: node rebuild/browser-tests.mjs
 *
 * Optional environment:
 * QUILLMD_BROWSER_BASE_URL: loopback doctor server (default http://127.0.0.1:9130)
 * QUILLMD_BROWSER_CREDENTIALS: private seed credentials JSON, never printed
 * PLAYWRIGHT_MODULE_DIR: explicit node_modules directory if dependencies are elsewhere
 *
 * The test refuses non-loopback URLs and live generation. It only writes synthetic
 * records. Screenshots/report/export stay under rebuild/.runtime/browser-artifacts.
 */
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
function dependency(name) {
  if (process.env.PLAYWRIGHT_MODULE_DIR) {
    return require(path.resolve(process.env.PLAYWRIGHT_MODULE_DIR, name));
  }
  return require(name);
}

const appDirectory = path.dirname(fileURLToPath(import.meta.url));
const artifacts = path.join(appDirectory, '.runtime', 'browser-artifacts');
const base = new URL(process.env.QUILLMD_BROWSER_BASE_URL || 'http://127.0.0.1:9130');
assert(['localhost', '127.0.0.1', '[::1]'].includes(base.hostname), 'Browser gate requires a loopback server.');
assert(!base.username && !base.password, 'Do not put credentials in the preview URL.');
const checks = [];
let activeCheck = 'Initialize browser dependencies and private credentials';
let browser;

async function check(name, action) {
  activeCheck = name;
  await action();
  checks.push({ name, passed: true });
  console.log(`PASS ${name}`);
}

try {
  const { chromium } = dependency('@playwright/test');
  const axeModule = dependency('@axe-core/playwright');
  const AxeBuilder = axeModule.default || axeModule;
  const credentialPath = process.env.QUILLMD_BROWSER_CREDENTIALS || path.join(appDirectory, '.runtime', 'private-access.json');
  const credentials = JSON.parse(await fs.readFile(credentialPath, 'utf8'));
  assert(credentials.doctor?.email.endsWith('@synthetic.quillmd.invalid'), 'Use freshly seeded synthetic accounts.');
  await fs.mkdir(artifacts, { recursive: true, mode: 0o700 });
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1080 }, acceptDownloads: true });
  const page = await context.newPage();
  const scriptErrors = [];
  page.on('pageerror', () => scriptErrors.push('Client script error'));
  page.setDefaultTimeout(20_000);

  async function accessibility(name) {
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    // Report rule identifiers only, never form values or document content.
    if (result.violations.length) {
      checks.push({ name, passed: false, rules: result.violations.map(item => item.id) });
      throw new Error('Accessibility rules failed');
    }
  }

  async function noPageOverflow() {
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
  }

  await check('Desktop sign-in page and accessibility', async () => {
    const response = await page.goto(new URL('/login/', base).href);
    assert.equal(response.status(), 200);
    await accessibility('Desktop sign-in accessibility');
    await noPageOverflow();
    await page.screenshot({ path: path.join(artifacts, 'login-desktop.png'), fullPage: true });
  });
  await check('Mobile sign-in page and accessibility', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await accessibility('Mobile sign-in accessibility');
    await noPageOverflow();
    await page.screenshot({ path: path.join(artifacts, 'login-mobile.png'), fullPage: true });
  });
  await check('Individual synthetic doctor authentication', async () => {
    await page.locator('[name=email]').fill(credentials.doctor.email);
    await page.locator('[name=password]').fill(credentials.doctor.password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.waitForURL(new URL('/', base).href);
  });
  await check('Mobile workspace accessibility and navigation', async () => {
    await accessibility('Mobile workspace accessibility');
    await noPageOverflow();
    assert.equal(await page.getByRole('button', { name: 'Sign out', exact: true }).isVisible(), true);
    await page.screenshot({ path: path.join(artifacts, 'workspace-mobile.png'), fullPage: true });
  });
  await check('Desktop workspace accessibility and fixture disclosure', async () => {
    await page.setViewportSize({ width: 1440, height: 1080 });
    await accessibility('Desktop workspace accessibility');
    await noPageOverflow();
    // This assertion is a spending boundary: never run paid generation from CI.
    assert.equal(await page.locator('.integration-list .badge').filter({ hasText: /^Synthetic fixture$/ }).count(), 1);
    await page.screenshot({ path: path.join(artifacts, 'workspace-desktop.png'), fullPage: true });
  });
  await check('Create a document from seeded patient and original form', async () => {
    await page.goto(new URL('/encounters/new/', base).href);
    await page.locator('[name=patient]').selectOption({ label: 'Synthetic Example X-ray · X-ray' });
    await page.locator('[name=template_version]').selectOption({ label: 'Clinical assessment · mapping 1' });
    await page.locator('[name=notes]').fill('History: Synthetic patient reports left wrist discomfort after a fall.\nFindings: No deformity documented.\nPlan: Follow-up assessment documented.');
    await page.locator('[name=synthetic_only]').check();
    await page.getByRole('button', { name: 'Create document', exact: true }).click();
    await page.waitForURL(/\/encounters\/[0-9a-f-]+\/$/);
  });
  await check('Generate supported answers with explicit zero fixture charge', async () => {
    assert.equal(await page.getByText('Synthetic fixture · $0 charge. No live AI service is called.', { exact: true }).isVisible(), true);
    await page.getByRole('button', { name: 'Generate supported answers', exact: true }).click();
    for (let attempt = 0; attempt < 40; attempt++) {
      await page.waitForTimeout(1000);
      await page.reload();
      if (await page.locator('textarea[name^=answer_]').count()) break;
      const terminalErrors = await page.locator('.source-panel .badge').allTextContents();
      assert(!terminalErrors.some(state => ['failed', 'reconciliation'].includes(state)), 'Fixture job did not complete.');
    }
    assert.equal(await page.locator('textarea[name^=answer_]').count(), 3);
    assert.equal(await page.locator('.evidence blockquote').count(), 3);
    assert.equal(await page.getByRole('link', { name: 'Download provider result', exact: true }).count(), 1);
  });
  await check('Supported answers retain source evidence', async () => {
    const answers = await page.locator('textarea[name^=answer_]').evaluateAll(inputs => inputs.map(input => input.value));
    const evidence = await page.locator('.evidence blockquote').allTextContents();
    for (let index = 0; index < answers.length; index++) {
      assert(answers[index].trim().length > 0);
      assert.equal(answers[index], evidence[index]);
    }
    await page.screenshot({ path: path.join(artifacts, 'review-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await noPageOverflow();
    await page.screenshot({ path: path.join(artifacts, 'review-mobile.png'), fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1080 });
  });
  await check('Save clinician review decisions', async () => {
    for (const checkbox of await page.locator('input[name^=reviewed_]').all()) await checkbox.check();
    await page.getByRole('button', { name: 'Save answers and review decisions', exact: true }).click();
    await page.waitForLoadState();
    assert.equal(await page.locator('input[name^=reviewed_]:checked').count(), 3);
  });
  await check('Finalize reviewed document and export the original format', async () => {
    await page.locator('[name=reviewed]').check();
    await page.getByRole('button', { name: 'Finalize document', exact: true }).click();
    await page.waitForLoadState();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Export original format' }).click();
    const download = await downloadPromise;
    assert(download.suggestedFilename().endsWith('.docx'));
    const exportPath = path.join(artifacts, 'synthetic-export.docx');
    await download.saveAs(exportPath);
    const bytes = await fs.readFile(exportPath);
    assert(bytes.length > 1000);
    assert.equal(bytes.subarray(0, 2).toString(), 'PK');
    assert.equal(await page.locator('textarea[name^=answer_]').count(), 0);
  });
  await check('Doctor cannot access administrator console', async () => {
    const response = await page.goto(new URL('/console/', base).href);
    assert([403, 404].includes(response.status()));
  });
  await check('Administrator authenticates with MFA and has financial-only access', async () => {
    await page.goto(new URL('/login/', base).href);
    await page.locator('[name=email]').fill(credentials.admin.email);
    await page.locator('[name=password]').fill(credentials.admin.password);
    const counter = Buffer.alloc(8);
    counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
    const digest = crypto.createHmac('sha1', Buffer.from(credentials.admin.totp_key_hex, 'hex')).update(counter).digest();
    const code = String((digest.readUInt32BE(digest[digest.length - 1] & 15) & 0x7fffffff) % 1000000).padStart(6, '0');
    await page.locator('[name=otp]').fill(code);
    await Promise.all([page.waitForNavigation(), page.getByRole('button', { name: 'Sign in', exact: true }).click()]);
    const response = await page.goto(new URL('/console/', base).href);
    assert.equal(response.status(), 200);
    const patients = await page.request.get(new URL('/api/patients/', base).href);
    assert.deepEqual((await patients.json()).patients, []);
    await accessibility('Administrator overview accessibility');
    await noPageOverflow();
  });
  await check('Admin financial drill-down renders explicit fixture costs without clinical notes', async () => {
    const link = page.locator('#jobs a[href^="/console/jobs/"]').first();
    await link.click();
    await page.waitForURL(/\/console\/jobs\/[0-9a-f-]+\/$/);
    assert.equal(await page.getByRole('heading', { name: 'Explain this charge', exact: true }).count(), 1);
    const body = await page.locator('body').innerText();
    assert(body.includes('Simulated fixture') && body.includes('Not reconciled'));
    assert(!body.includes('Synthetic patient reports left wrist discomfort'));
    await accessibility('Financial evidence accessibility');
    await noPageOverflow();
    await page.screenshot({ path: path.join(artifacts, 'admin-charge-evidence.png'), fullPage: true });
  });
  await check('Admin filters disclose empty matches and audit retains readable drill-downs', async () => {
    await page.goto(new URL('/console/?q=no-such-isolated-fixture', base).href);
    assert((await page.locator('#accounts').innerText()).includes('No accounts match these filters.'));
    await page.goto(new URL('/console/audit/?q=admin.job_financial_read', base).href);
    assert.equal(await page.locator('tbody tr').count(), 1);
    await accessibility('Filtered audit accessibility');
  });
  await check('No client-side JavaScript errors', async () => assert.equal(scriptErrors.length, 0));
} catch {
  // Playwright error logs can include arguments to fill(); never log the raw
  // exception because those arguments can contain authentication credentials.
  if (!checks.some(item => item.name === activeCheck && !item.passed)) {
    checks.push({ name: activeCheck, passed: false });
  }
  console.error(`FAIL ${activeCheck}. Inspect the private test report; credentials were not logged.`);
  process.exitCode = 1;
} finally {
  await browser?.close();
  await fs.mkdir(artifacts, { recursive: true, mode: 0o700 });
  await fs.writeFile(path.join(artifacts, 'report.json'), JSON.stringify({ checks }, null, 2), { mode: 0o600 });
  console.log(`${checks.filter(item => item.passed).length} browser checks passed; ${checks.filter(item => !item.passed).length} failed.`);
}
