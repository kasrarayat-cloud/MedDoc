'use strict';
/*
 * I1-13 (integrated refutation round 1, session-0) in Chromium, driven by tests/test_session_news.py against the live
 * application (its own templates, sessions and policy; static files collected and served by WhiteNoise). In each
 * experiment, one browser context (one cookie jar): tab 1 is the app, signed in as the member, with a PDF document open,
 * its copy kept and a worker waiting for the next document (R2-10, R2-15); tab 2 is a page outside the app. Tab 1 gets
 * no input at all. Its forgetMemory is wrapped to report the first end it meets: the copies it held, whether they were
 * overwritten, what was kept after, and whether the waiting worker ended.
 *   own-account     tab 2 opens the account page of the same session, then the sign-in page: tab 1 asks the server
 *                   once (the sign-in page names no session) and stays; nothing is wiped
 *   everywhere      tab 2 presses "Sign out everywhere" on the account page: tab 1 is wiped and leaves at once
 *   other-member    tab 2 opens the sign-in page (tab 1 asks, stays), then another member whose password must change
 *                   signs in there and lands on the account page: tab 1 asks, meets their session, is wiped
 *   ended-elsewhere the account's sessions end with no page of this browser's (a POST to /logout/everywhere from the
 *                   context's own request API): tab 1 hears nothing; tab 2 then opens the sign-in page: tab 1 asks,
 *                   meets the 401, is wiped
 * Output: one line 'RESULT <experiment> <json>' each, then 'DONE'; 'ERROR <text>' if the script itself failed. The
 * members' names and the synthetic password come in the environment and are never printed.
 *   node tests/frontend/session_news_browser.cjs <live server url> <document id> [experiment...]
 */
const { PLAYWRIGHT } = require('../../ops/walk.cjs');

const [base, documentId, ...asked] = process.argv.slice(2);
const MEMBER = process.env.SESSION_NEWS_MEMBER || '';
const OTHER = process.env.SESSION_NEWS_OTHER || '';
const PASSWORD = process.env.SESSION_NEWS_PASSWORD || '';
const EXPERIMENTS = ['own-account', 'everywhere', 'other-member', 'ended-elsewhere'];
const WAIT_MS = 10000;
const QUIET_MS = 1500;

function out(line) {
  process.stdout.write(`${line}\n`);
}

async function signIn(page, username) {
  await page.goto(`${base}/login/`);
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', PASSWORD);
  await Promise.all([page.waitForNavigation(), page.click('form.login-form button[type="submit"]')]);
}

// Tab 1: the member signed in, the document drawn, its copy kept and a worker waiting; its ends reported, and its
// requests to the session ping recorded with their times.
async function appTab(context) {
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  const pings = [];
  page.on('request', request => {
    if (new URL(request.url()).pathname === '/session/activity') pings.push({ at: Date.now(), poll: request.headers()['x-cpt-poll'] || '' });
  });
  const reports = [];
  await page.exposeFunction('reportWipe', report => reports.push({ ...report, at: Date.now() }));
  await signIn(page, MEMBER);
  await page.goto(`${base}/#doc/${documentId}`);
  await page.waitForFunction(() => Boolean(document.querySelector('#documentViewer .pdf-text span')), null, { timeout: 60000 });
  await page.waitForFunction(() => state.keptViews.size === 1 && Boolean(state.pdfStandby && state.pdfStandby.thread), null, { timeout: 60000 });
  await page.evaluate(() => {
    const forget = window.forgetMemory;
    let told = false;
    window.forgetMemory = function wipeAndReport(...args) {
      const copies = [...state.keptViews.values()].map(item => item.data);
      const waited = Boolean(state.pdfStandby && state.pdfStandby.thread);
      const result = forget(...args);
      if (!told) {
        told = true;
        window.reportWipe({ copies: copies.length, zeroed: copies.every(copy => copy.every(byte => byte === 0)),
          kept: state.keptViews.size, hints: state.viewHints.size, waited, waiting: Boolean(state.pdfStandby) });
      }
      return result;
    };
  });
  return { page, errors, pings, reports };
}

async function waitFor(check, ms = WAIT_MS) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (check()) return true;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  return check();
}

const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

async function tabState(tab) {
  return tab.page.evaluate(() => ({ url: location.pathname + location.hash, kept: state.keptViews.size,
    waiting: Boolean(state.pdfStandby), gone: idle.gone })).catch(error => ({ error: String(error).slice(0, 120) }));
}

async function sessionAnswer(context) {
  return (await context.request.get(`${base}/api/session`, { headers: { 'X-CPT-Studio-Client': 'customer-2026-11-26' }, maxRedirects: 0 })).status();
}

async function run(browser, experiment) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  try {
    const one = await appTab(context);
    const two = await context.newPage();
    const result = { experiment };
    if (experiment === 'own-account') {
      const start = one.pings.length;
      await two.goto(`${base}/account/`);
      await pause(QUIET_MS);
      result.after_account = { reports: one.reports.length, pings: one.pings.slice(start).map(ping => ping.poll), tab: await tabState(one) };
      const before = one.pings.length;
      await two.goto(`${base}/login/`);
      await waitFor(() => one.pings.length > before, 5000);
      await pause(QUIET_MS);
      result.after_login = { reports: one.reports.length, pings: one.pings.slice(before).map(ping => ping.poll), tab: await tabState(one) };
      result.session = await sessionAnswer(context);
    } else if (experiment === 'everywhere') {
      await two.goto(`${base}/account/`);
      const pressed = Date.now();
      const before = one.pings.length;
      await Promise.all([two.waitForNavigation(), two.click('#everywhereForm button[type="submit"]')]);
      await waitFor(() => one.reports.length > 0);
      result.report = one.reports[0] || null;
      result.wiped_ms = result.report ? result.report.at - pressed : null;
      result.pings_before_wipe = one.pings.slice(before).filter(ping => result.report && ping.at <= result.report.at).length;
      result.two = new URL(two.url()).pathname;
      await one.page.waitForURL(url => url.pathname.startsWith('/login'), { timeout: WAIT_MS }).catch(() => {});
      result.one = new URL(one.page.url()).pathname;
      result.session = await sessionAnswer(context);
    } else if (experiment === 'other-member') {
      await two.goto(`${base}/login/`);
      await pause(QUIET_MS);
      result.after_login = { reports: one.reports.length, tab: await tabState(one) };
      const signing = Date.now();
      await two.fill('input[name="username"]', OTHER);
      await two.fill('input[name="password"]', PASSWORD);
      await Promise.all([two.waitForNavigation(), two.click('form.login-form button[type="submit"]')]);
      await waitFor(() => one.reports.length > 0);
      result.two = new URL(two.url()).pathname + new URL(two.url()).search;
      result.report = one.reports[0] || null;
      result.wiped_ms = result.report ? result.report.at - signing : null;
    } else if (experiment === 'ended-elsewhere') {
      const cookies = await context.cookies(base);
      const csrf = (cookies.find(cookie => cookie.name === 'cptstudio_csrf') || {}).value || '';
      const ended = await context.request.post(`${base}/logout/everywhere`, { headers: { 'X-CSRFToken': csrf, Referer: `${base}/` }, maxRedirects: 0 });
      result.ended = ended.status();
      result.session = await sessionAnswer(context);
      await pause(QUIET_MS);
      result.before_login = { reports: one.reports.length, tab: await tabState(one) };
      const opened = Date.now();
      await two.goto(`${base}/login/`);
      await waitFor(() => one.reports.length > 0);
      result.report = one.reports[0] || null;
      result.wiped_ms = result.report ? result.report.at - opened : null;
    }
    result.errors = one.errors;
    return result;
  } finally {
    await context.close();
  }
}

(async () => {
  const { chromium } = require(PLAYWRIGHT);
  const browser = await chromium.launch({ headless: true });
  try {
    for (const experiment of asked.length ? asked : EXPERIMENTS) out(`RESULT ${experiment} ${JSON.stringify(await run(browser, experiment))}`);
    out('DONE');
  } finally {
    await browser.close();
  }
})().catch(error => {
  out(`ERROR ${String(error && error.stack || error).replace(/\s+/g, ' ').slice(0, 2000)}`);
  process.exitCode = 1;
});
