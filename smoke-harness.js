// E2E smoke harness for QuillMD production at app.quillmd.com.
// Run as: node /tmp/smoke-harness.js <phase>
// Saves screenshots + timings under docs/smoke-test-2026-05-04/phase-<X>/.
const { chromium, devices } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

const URL = 'https://app.quillmd.com';
const MARKETING = 'https://quillmd.com';
const TS = process.env.SMOKE_TS || String(Date.now());
const EMAIL = `qa-smoke-${TS}@quillmd-test.local`;
const PASSWORD = `Smoke${TS}!Aa`;
const NAME = 'Dr. Smoke Tester';
const SMOKE_DIR = '/opt/meddoc-pro/docs/smoke-test-2026-05-04';

function shotPath(phase, step) {
  return path.join(SMOKE_DIR, `phase-${phase}`, 'screenshots', `${step}.png`);
}

function logPath(phase) {
  return path.join(SMOKE_DIR, `phase-${phase}`, 'run.log');
}

async function newSession({ mobile = false } = {}) {
  const browser = await chromium.launch({
    headless: true,
    executablePath:
      '/home/claude/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
  });
  const ctx = await browser.newContext({
    ignoreHTTPSErrors: true,
    ...(mobile ? devices['iPhone 13'] : {}),
  });
  const page = await ctx.newPage();
  return { browser, ctx, page };
}

// Phase-level state: when failFast is on, any FAIL aborts subsequent
// record() calls so we don't burn 45s timeouts cascading through dead branches.
const phaseState = new Map();

function setFailFast(phase, on = true) {
  phaseState.set(phase, { ...(phaseState.get(phase) || {}), failFast: on, aborted: false });
}

async function record(phase, label, fn) {
  const state = phaseState.get(phase) || {};
  if (state.aborted) {
    console.log(`[${phase}] ${label}: SKIP (aborted after prior FAIL)`);
    fs.appendFileSync(
      logPath(phase),
      JSON.stringify({ phase, label, status: 'SKIP', durationMs: 0, error: 'aborted after prior FAIL' }) + '\n',
    );
    return { phase, label, status: 'SKIP' };
  }
  const t0 = Date.now();
  let result = { phase, label, status: 'PASS', durationMs: 0, error: null };
  try {
    await fn();
  } catch (e) {
    result.status = 'FAIL';
    result.error = e.message || String(e);
    console.error(`[${phase}] ${label} FAIL:`, e.message);
    if (state.failFast) {
      state.aborted = true;
      phaseState.set(phase, state);
    }
  }
  result.durationMs = Date.now() - t0;
  fs.appendFileSync(
    logPath(phase),
    JSON.stringify(result) + '\n',
  );
  console.log(`[${phase}] ${label}: ${result.status} (${result.durationMs}ms)`);
  return result;
}

module.exports = {
  URL,
  MARKETING,
  TS,
  EMAIL,
  PASSWORD,
  NAME,
  SMOKE_DIR,
  shotPath,
  logPath,
  newSession,
  record,
  setFailFast,
};

// Allow direct invocation for sanity check.
if (require.main === module) {
  console.log({ URL, EMAIL, PASSWORD, TS });
}
