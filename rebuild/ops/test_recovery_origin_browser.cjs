/* Real-browser recovery regression for the isolated seeded CI application.
 * node rebuild/ops/test_recovery_origin_browser.cjs /absolute/fresh/private-output-dir
 * Tokens stay in captured memory. No password submission, mail, traces or screenshots.
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require('@playwright/test');

const base = path.resolve(__dirname, '..');
const origin = process.env.QUILLMD_RECOVERY_BROWSER_ORIGIN || 'http://127.0.0.1:9130';
const output = process.argv[2];
const report = {
  format: 'quillmd-recovery-origin-browser-v1',
  complete: false,
  provider_calls: 0,
  password_changes: 0,
  cases: {},
};
let browser;
let stage = 'output-guard';
let checkName = 'initialization';
let outputReady = false;
let rejectedRequests = 0;

function requireCheck(condition, name = 'fixture-guard') {
  checkName = name;
  if (!condition) throw new Error('Recovery browser guard failed.');
}

// Import only managed fixture settings, and refuse unsafe settings before opening
// a database connection. Neither child stdout nor stderr is forwarded to a log.
const fixtureCode = String.raw`
import hashlib,json,os,sys
try:
    os.environ['QUILLMD_ENV_MANAGED']='1'
    os.environ['DJANGO_SETTINGS_MODULE']='quillmd.settings'
    import django
    from django.conf import settings
    db=settings.DATABASES['default']
    name=db['NAME']
    assert name!='quillmd_fresh' and (name=='quillmd_browser_ci' or name.startswith('quillmd_recovery_origin_') or name.startswith('test_quillmd_'))
    assert db['HOST'] in ('127.0.0.1','localhost')
    assert settings.AI_MODE=='fixture' and settings.SYNTHETIC_ONLY and not settings.ADMIN_SITE
    assert settings.QUILLMD_EMAIL_MODE=='file' and settings.SESSION_COOKIE_SAMESITE=='Strict'
    assert settings.RELEASE_SHA=='development-unrecorded' or settings.RELEASE_SHA.startswith('recovery-origin-fixture-')
    django.setup()
    from django.db import connection,transaction
    from django.urls import reverse
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode
    from django_otp.plugins.otp_totp.models import TOTPDevice
    from core.models import User,Membership
    from core.recovery import recovery_token_generator
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
            cursor.execute('SELECT current_database()')
            assert cursor.fetchone()[0]==name
        user=User.objects.get(email='doctor@synthetic.quillmd.invalid')
        assert user.is_active and user.verified_at and user.has_usable_password() and not user.is_staff
        assert Membership.objects.filter(user=user,active=True).exists()
        state={'password':user.password,'active':user.is_active,'verified':user.verified_at.isoformat(),
               'staff':user.is_staff,'session_version':user.session_version,
               'memberships':list(Membership.objects.filter(user=user).order_by('pk').values('id','department_id','role','active')),
               'mfa':list(TOTPDevice.objects.filter(user=user).order_by('pk').values('id','confirmed','last_t'))}
        result={'state_fingerprint':hashlib.sha256(json.dumps(state,sort_keys=True,default=str).encode()).hexdigest(),
                'release':settings.RELEASE_SHA}
        if sys.argv[1]=='bootstrap':
            uid=urlsafe_base64_encode(force_bytes(user.pk))
            raw=recovery_token_generator.make_token(user)
            result.update(raw_token=raw,
                raw_path=reverse('recovery_confirm',kwargs={'uidb64':uid,'token':raw}),
                clean_path=reverse('recovery_confirm',kwargs={'uidb64':uid,'token':'set-password'}))
        print(json.dumps(result))
except Exception:
    sys.exit(2)
`;

function fixtureState(action) {
  const child = spawnSync(process.env.QUILLMD_RECOVERY_BROWSER_PYTHON || 'python3', ['-c', fixtureCode, action], {
    cwd: base,
    env: {...process.env, QUILLMD_ENV_MANAGED: '1', DJANGO_SETTINGS_MODULE: 'quillmd.settings'},
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    timeout: 20000,
    maxBuffer: 65536,
  });
  requireCheck(!child.error && child.status === 0);
  const result = JSON.parse(child.stdout);
  requireCheck(typeof result.state_fingerprint === 'string' && /^[a-f0-9]{64}$/.test(result.state_fingerprint));
  return result;
}

async function newContext() {
  const context = await browser.newContext({serviceWorkers: 'block'});
  await context.route('**/*', route => {
    const request = route.request();
    if (request.url().startsWith(origin + '/') && request.method() === 'GET') return route.continue();
    rejectedRequests += 1;
    return route.abort();
  });
  return context;
}

function observeRequests(page, fixture) {
  const observed = {initial_assets: true, document_assets: 0, document_asset_referrers_absent: true,
    indirect_asset_referrer_present: false, continue_requests: 0,
    continue_referrers_absent: true, token_referrers_absent: true, document_requests: 0, page_errors: 0};
  page.on('request', request => {
    const address = request.url();
    if (!address.startsWith(origin + '/')) return;
    const referer = request.headers().referer || '';
    if (referer.includes(fixture.raw_token)) observed.token_referrers_absent = false;
    if (observed.initial_assets && address.startsWith(origin + '/static/')) {
      if (['script', 'stylesheet'].includes(request.resourceType())) {
        observed.document_assets += 1;
        if (referer) observed.document_asset_referrers_absent = false;
      } else if (referer) {
        // A font loaded by app.css may refer to the stylesheet/origin. The
        // token-free check above still applies to every request, including it.
        observed.indirect_asset_referrer_present = true;
      }
    }
    if (address === origin + fixture.clean_path) {
      observed.continue_requests += 1;
      if (referer) observed.continue_referrers_absent = false;
    }
    if (request.isNavigationRequest()) observed.document_requests += 1;
  });
  // Browser exceptions can contain a token-bearing URL. Retain only their count.
  page.on('pageerror', () => { observed.page_errors += 1; });
  return observed;
}

async function validCase(fixture, crossSite) {
  const context = await newContext();
  try {
    const page = await context.newPage();
    const observed = observeRequests(page, fixture);
    let response;
    if (crossSite) {
      // An opaque data origin supplies a genuine browser-initiated cross-site
      // anchor navigation; page.goto(rawURL) alone does not reproduce the bug.
      await page.goto('data:text/html,' + encodeURIComponent(
        '<!doctype html><a href="' + origin + fixture.raw_path + '">Open recovery</a>'));
      [response] = await Promise.all([
        page.waitForNavigation({waitUntil: 'load'}),
        page.getByRole('link', {name: 'Open recovery', exact: true}).click(),
      ]);
    } else {
      response = await page.goto(origin + fixture.raw_path, {waitUntil: 'load'});
    }
    requireCheck(response && response.status() === 200, 'token-page-status');
    requireCheck(page.url() === origin + fixture.raw_path, 'token-page-location');
    requireCheck(response.headers()['referrer-policy'] === 'no-referrer', 'token-page-referrer-policy');
    requireCheck((response.headers()['cache-control'] || '').includes('no-store'), 'token-page-cache-policy');
    const continuation = page.getByRole('link', {name: 'Continue to password form', exact: true});
    requireCheck(await continuation.isVisible(), 'continue-link-visible');
    requireCheck(await continuation.getAttribute('href') === fixture.clean_path, 'continue-link-clean-relative-target');
    requireCheck(await continuation.getAttribute('referrerpolicy') === 'no-referrer', 'continue-link-referrer-policy');
    requireCheck(!(await page.content()).includes(fixture.raw_token), 'token-page-dom-secret-absent');
    requireCheck(await page.locator('form, input[type="password"], meta[http-equiv="refresh" i]').count() === 0, 'token-page-no-form-or-refresh');
    await page.waitForTimeout(250);
    requireCheck(page.url() === origin + fixture.raw_path && observed.document_requests === 1, 'token-page-no-auto-navigation');
    requireCheck(observed.document_assets > 0, 'token-page-document-assets-requested');
    requireCheck(observed.document_asset_referrers_absent, 'token-page-document-asset-referrers-absent');
    requireCheck(observed.token_referrers_absent, 'token-page-secret-referrers-absent');
    const session = (await context.cookies(origin)).find(cookie => cookie.name === 'quillmd_doctor_session');
    requireCheck(session && session.sameSite === 'Strict' && session.httpOnly, 'token-page-session-strict-http-only');
    observed.initial_assets = false;
    const [cleanResponse] = await Promise.all([
      page.waitForNavigation({waitUntil: 'load'}),
      continuation.click(),
    ]);
    requireCheck(cleanResponse && cleanResponse.status() === 200, 'clean-page-status');
    requireCheck(page.url() === origin + fixture.clean_path, 'clean-page-location');
    requireCheck(await page.locator('input[name="new_password1"]').isVisible(), 'clean-page-first-password-visible');
    requireCheck(await page.locator('input[name="new_password2"]').isVisible(), 'clean-page-second-password-visible');
    requireCheck(!(await page.content()).includes(fixture.raw_token), 'clean-page-dom-secret-absent');
    requireCheck(observed.continue_requests === 1 && observed.continue_referrers_absent, 'continue-request-referrer-absent');
    requireCheck(observed.token_referrers_absent, 'all-secret-referrers-absent');
    requireCheck(observed.page_errors === 0, 'browser-page-errors-absent');
    return {
      token_page_status: 200,
      token_page_no_referrer_policy: true,
      continue_link_no_referrer_policy: true,
      initial_document_asset_referrers_absent: true,
      initial_indirect_asset_referrer_present: observed.indirect_asset_referrer_present,
      all_asset_referrers_token_free: true,
      continue_request_referrer_absent: true,
      raw_token_absent_from_application_dom: true,
      auto_navigation_absent: true,
      session_cookie_strict: true,
      session_cookie_http_only: true,
      clean_page_status: 200,
      password_form_visible: true,
      password_submitted: false,
    };
  } finally {
    await context.close();
  }
}

async function refusedCase(fixture, cleanOnly) {
  const context = await newContext();
  try {
    const page = await context.newPage();
    const wrongToken = fixture.raw_token.slice(0, -1) + (fixture.raw_token.endsWith('0') ? '1' : '0');
    const route = cleanOnly ? fixture.clean_path : fixture.raw_path.replace(fixture.raw_token, wrongToken);
    const response = await page.goto(origin + route, {waitUntil: 'load'});
    requireCheck(response && response.status() === 200);
    requireCheck(await page.getByRole('heading', {name: 'Recovery link unavailable', exact: true}).isVisible());
    requireCheck(await page.getByRole('link', {name: 'Continue to password form', exact: true}).count() === 0);
    requireCheck(await page.locator('input[type="password"]').count() === 0);
    return {status: 200, recovery_unavailable: true, continue_link_absent: true, password_form_absent: true};
  } finally {
    await context.close();
  }
}

(async () => {
  const runtime = path.join(base, '.runtime');
  requireCheck(output && path.isAbsolute(output) && path.resolve(output) === output);
  requireCheck(output.startsWith(runtime + path.sep) && fs.realpathSync(path.dirname(output)) === path.dirname(output));
  fs.mkdirSync(output, {mode: 0o700});
  requireCheck((fs.statSync(output).mode & 0o777) === 0o700);
  outputReady = true;
  stage = 'origin-guard';
  const parsedOrigin = new URL(origin);
  requireCheck(parsedOrigin.protocol === 'http:' && parsedOrigin.hostname === '127.0.0.1');
  requireCheck(Number(parsedOrigin.port) >= 1024 && Number(parsedOrigin.port) <= 65535);
  requireCheck(parsedOrigin.pathname === '/' && !parsedOrigin.search && !parsedOrigin.hash);
  requireCheck(!parsedOrigin.username && !parsedOrigin.password && parsedOrigin.origin === origin);
  stage = 'isolated-fixture-guard';
  const fixture = fixtureState('bootstrap');
  requireCheck(/^\/recovery\/confirm\/[A-Za-z0-9_-]+\/[0-9a-z]+-[0-9a-z]+\/$/.test(fixture.raw_path));
  requireCheck(/^\/recovery\/confirm\/[A-Za-z0-9_-]+\/set-password\/$/.test(fixture.clean_path));
  stage = 'served-fixture-guard';
  // A loopback address alone does not prove this is the isolated CI application.
  const healthResponse = await fetch(origin + '/health/', {redirect: 'error', signal: AbortSignal.timeout(10000)});
  requireCheck(healthResponse.status === 200);
  const health = await healthResponse.json();
  requireCheck(health.status === 'ok' && health.data_mode === 'synthetic-only' && health.surface === 'doctor' && health.release === fixture.release);
  report.isolated_fixture_guard_passed = true;
  browser = await chromium.launch({headless: true, timeout: 20000});
  stage = 'direct-fresh';
  report.cases.direct_fresh = await validCase(fixture, false);
  stage = 'cross-site-anchor';
  report.cases.cross_site_anchor = await validCase(fixture, true);
  stage = 'invalid-token';
  report.cases.invalid_token = await refusedCase(fixture, false);
  stage = 'clean-route-separate-context';
  report.cases.clean_route_separate_context = await refusedCase(fixture, true);
  stage = 'preservation';
  requireCheck(fixtureState('snapshot').state_fingerprint === fixture.state_fingerprint);
  requireCheck(rejectedRequests === 0);
  report.account_password_mfa_memberships_unchanged = true;
  report.external_or_non_get_requests_absent = true;
  report.complete = true;
})().catch(() => {
  // Never serialize the exception: Playwright errors include navigated URLs.
  report.failure_stage = stage;
  report.failure_check = checkName;
  process.exitCode = 1;
}).finally(async () => {
  if (browser) {
    try { await browser.close(); } catch (_) { report.complete = false; process.exitCode = 1; }
  }
  if (outputReady) {
    fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(report, null, 2) + '\n', {mode: 0o600, flag: 'wx'});
  }
});
