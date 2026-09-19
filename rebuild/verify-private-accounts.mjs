/** The private onboarding and recovery checks, and nothing else.
 *
 * ⚠️ WHY THIS EXISTS SEPARATELY FROM verify-private-release.mjs. That harness proves a whole release and, to
 * do it, spends money on two real provider jobs. These checks failed there for a reason that had nothing to
 * do with the release — its mail helper ran as the operator account and could not read the application's
 * private outbox — so re-running the whole thing to retry them would pay for a transcription and a
 * generation again and create a second finalized document nobody asked for. This reruns only what did not
 * finish: no recording, no generation, no provider contact at all.
 *
 * The mail access is the repair. ops/private_mail reads through the confined SERVICE-identity reader in
 * ops/private_storage — no permission is widened, no sudo, no endpoint, no directory mode changed. It is
 * narrowed twice beyond that: to the files this run actually changed (a before/after inventory diff, not a
 * clock), and then to the single message RECORD addressed to this run's unique synthetic address.
 *
 * ⚠️ THE ROUTE IS THE TOKEN. core/email_delivery.py builds `{origin}/{route}/{raw_token}/`, so the link and
 * the secret are one string. It is navigated to and never recorded: it is not logged, not written to the
 * report, not passed as a process argument, and never an operand of an assertion — assert failures print
 * both operands. The report keeps describe(): that a route was found, of what kind, of what length.
 *
 * ⚠️ A PRIVATE-OUTBOX READ DEMONSTRATES THE APPLICATION'S BEHAVIOUR, NOT EMAIL DELIVERY. Nothing here shows
 * that a message would reach a real mailbox; QUILLMD_EMAIL_MODE is `file` and no transport is exercised.
 *
 * Usage: QUILLMD_ACCOUNTS_LIVE=1 node rebuild/verify-private-accounts.mjs --expected-release FULL_SHA
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const require = createRequire(import.meta.url);
const appRoot = path.dirname(fileURLToPath(import.meta.url));
const runtime = path.join(appRoot, '.runtime');
const doctorBase = process.env.QUILLMD_BROWSER_BASE_URL || 'http://127.0.0.1:9130';
const adminBase = process.env.QUILLMD_ADMIN_BASE_URL || 'http://127.0.0.1:9131';
for (const value of [doctorBase, adminBase]) { const url = new URL(value); assert(['127.0.0.1', 'localhost'].includes(url.hostname) && !url.username && !url.password); }
const report = { startedAt: new Date().toISOString(), checks: [], mailRoutes: [], providerJobs: 0, complete: false };
let currentCheck = 'startup', browser;

async function check(name, action) { currentCheck = name; await action(); report.checks.push({ name, passed: true }); console.log(`PASS ${name}`); }

/** A bounded synthetic read/act against the application's own models. The payload travels on STDIN, never
 * in argv: argv is world-readable in `ps`. Nothing this returns is echoed on a failure path. */
function python(code, payload = {}) {
  const header = "import os,json,sys\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')\nimport django\ndjango.setup()\npayload=json.loads(sys.stdin.read() or '{}')\n";
  const result = spawnSync(process.env.QUILLMD_TEST_PYTHON || path.join(appRoot, '.venv/bin/python'), ['-B', '-c', header + code],
    { cwd: appRoot, encoding: 'utf8', input: JSON.stringify(payload), timeout: 120000, maxBuffer: 8 * 1024 * 1024 });
  assert.equal(result.status, 0, 'Bounded synthetic account operation failed.');
  return result.stdout.trim() ? JSON.parse(result.stdout.trim().split('\n').pop()) : {};
}
function totp(hexKey) { const counter = Buffer.alloc(8); counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000))); const digest = crypto.createHmac('sha1', Buffer.from(hexKey, 'hex')).update(counter).digest(); return String((digest.readUInt32BE(digest[digest.length - 1] & 15) & 0x7fffffff) % 1000000).padStart(6, '0'); }

/** Names and sha256 of the private outbox as the confined reader sees it. Never any content.
 *
 * This is also the instrument's positive control. ops/private_storage collapses every failure — a stray
 * mode, a closed volume, a missing docker, a changed root inode — into one generic string, so an empty
 * result must never be read as "the application sent nothing". A snapshot that cannot be taken throws. */
function mailSnapshot() {
  return python("from ops import private_mail\nfrom django.conf import settings\n"
    + "assert settings.QUILLMD_EMAIL_MODE=='file', 'the private outbox is only written in file email mode'\n"
    + "assert str(settings.EMAIL_FILE_PATH)==str(private_mail.OUTBOX), 'the outbox is not where the reader looks'\n"
    + "print(json.dumps({'files':private_mail.snapshot()}))\n").files;
}

/** The invitation or recovery route for THIS run. Returns a secret: navigate to it, record nothing. */
function mailRoute(kind, email, before) {
  const found = python(
    "from ops import private_mail\nnotes={}\n"
    + "route=private_mail.route(payload['kind'],payload['email'],payload['before'],notes=notes)\n"
    + "print(json.dumps({'route':route,'described':private_mail.describe(route),'notes':notes}))\n",
    { kind, email, before });
  // describe() and the counts only. `found.route` never reaches the report, a log line or an assertion.
  report.mailRoutes.push({ kind, ...found.described, ...found.notes });
  // ⚠️ NOT `described.found`: route() only ever returns `/<kind>/<token>/` and describe() answers true for
  // every such string, so that assertion cannot fail — a control that passes by construction. The failure
  // it claimed to catch is already a MailUnavailable inside route(). These are measured facts instead.
  assert.equal(found.notes.records_for_this_run, 1, 'the run did not own exactly one message');
  assert.equal(found.notes.records_outside_synthetic, 0, 'a non-synthetic message shared the outbox file');
  assert.equal(found.described.kind, kind, 'the extracted route is a different kind than was asked for');
  assert(found.described.token_characters >= 16, 'the extracted token is implausibly short');
  return found.route;
}

async function login(page, account, base = doctorBase, otp) {
  await page.goto(base + '/login/');
  await page.locator('[name=email]').fill(account.email);
  await page.locator('[name=password]').fill(account.password);
  if (otp) await page.locator('[name=otp]').fill(otp);
  await page.getByRole('button', { name: base === adminBase ? 'Sign in to administration' : 'Sign in', exact: true }).click();
}
async function statusOf(page, url) { const response = await page.request.get(url, { maxRedirects: 0 }); return response.status(); }
/** A sign-in refused by the rate limiter never reaches the authenticator, so it cannot evidence anything
 * about MFA. Named here so the check fails honestly instead of recording a refusal it did not earn. */
async function assertNotRateLimited(page, what) {
  assert(!(await page.content()).includes('Too many sign-in attempts'),
    `sign-in was rate limited, so ${what} was not exercised; wait ten minutes and rerun`);
}

try {
  assert.equal(process.env.QUILLMD_ACCOUNTS_LIVE, '1', 'Set QUILLMD_ACCOUNTS_LIVE=1 to run against the private services.');
  const cli = process.argv.slice(2);
  assert(cli.length === 2 && cli[0] === '--expected-release');
  const expectedRelease = cli[1];
  assert(/^[0-9a-f]{40}$/.test(expectedRelease));
  report.release = expectedRelease;

  const credentialsPath = process.env.QUILLMD_BROWSER_CREDENTIALS || path.join(runtime, 'private-access.json');
  const meta = await fs.lstat(credentialsPath);
  assert(meta.isFile() && (meta.mode & 0o077) === 0, 'Credentials must be a private regular file.');
  const credentials = JSON.parse(await fs.readFile(credentialsPath, 'utf8'));
  for (const key of ['doctor', 'admin', 'ultrasound']) assert(credentials[key].email.endsWith('@synthetic.quillmd.invalid'));
  const { chromium } = process.env.PLAYWRIGHT_MODULE_DIR
    ? require(path.resolve(process.env.PLAYWRIGHT_MODULE_DIR, '@playwright/test')) : require('@playwright/test');

  const email = `accounts-${Date.now()}@synthetic.quillmd.invalid`;
  const password = crypto.randomBytes(24).toString('base64url');
  const invited = { email, password };

  browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  await check('Both permanent services serve the exact revision under test', async () => {
    const served = [];
    for (const base of [doctorBase, adminBase]) {
      const answer = await (await page.request.get(base + '/health/')).json();
      assert.equal(answer.release, expectedRelease, 'a service is serving a different revision');
      // ⚠️ `data_mode` is a hard-coded literal in core/views.py — it is a DECLARATION by the build, not a
      // measurement of the database, and a service pointed at real records would answer it too. Asserted
      // because a build that stopped declaring it would be a finding; never cited as evidence of what the
      // database contains.
      assert.equal(answer.data_mode, 'synthetic-only');
      served.push(answer.release);
    }
    // The MEASURED value, not the argument echoed back. `--expected-release` is an input; recording it as
    // `servedRelease` would make a typo look like a reading.
    assert.deepEqual([...new Set(served)], [expectedRelease]);
    report.servedRelease = served[0];
  });

  // ⚠️ THE READER IS POSITIVE-CONTROLLED BEFORE THE FIRST MESSAGE IS SENT. Taken after, an unreadable
  // outbox and a silent application produce the same empty answer.
  let outboxBefore;
  await check('The confined outbox reader answers before anything is sent', async () => {
    outboxBefore = mailSnapshot();
    assert(Object.keys(outboxBefore).length > 0, 'the reader returned an empty outbox; it cannot be distinguished from a reader that cannot see');
    report.outboxFilesBefore = Object.keys(outboxBefore).length;
  });

  let invitationDepartment;
  /** Create one departmental invitation as the signed-in doctor. Used twice: once for the account, once to
   * reach the welcome grant's idempotency key a second time. */
  async function createInvitation(target) {
    await page.goto(doctorBase + '/team/');
    const form = page.locator('form').filter({ has: page.getByRole('button', { name: 'Create invitation', exact: true }) });
    // ⚠️ SELECTED BY VALUE, NOT BY LABEL. Two departments in this fixture are both named "X-ray" — one in
    // each organization — so a label match is a coin toss that would silently invite into the wrong
    // organization. The option count is asserted first: one option is what makes the id unambiguous.
    const options = await form.locator('[name=department] option').evaluateAll(
      nodes => nodes.map(n => n.value).filter(v => v));
    assert.equal(options.length, 1, 'the inviting doctor administers more than one department; pick one explicitly');
    if (invitationDepartment) assert.equal(options[0], invitationDepartment, 'the offered department changed mid-run');
    invitationDepartment = options[0];
    await form.locator('[name=email]').fill(target);
    await form.locator('[name=department]').selectOption(invitationDepartment);
    await form.locator('[name=role]').selectOption('employee');
    await page.getByRole('button', { name: 'Create invitation', exact: true }).click();
    await page.waitForLoadState();
  }

  await check('Doctor signs in and creates a departmental invitation', async () => {
    await login(page, credentials.doctor);
    await page.waitForURL(doctorBase + '/');
    await createInvitation(email);
    report.invitation = python(
      "from core.models import Invitation\ni=Invitation.objects.get(email=payload['email'])\n"
      + "print(json.dumps({'department':str(i.department_id),'role':i.role,'accepted':bool(i.accepted_at)}))\n",
      { email });
    assert.equal(report.invitation.department, invitationDepartment, 'the invitation names a different department than the form offered');
    assert.equal(report.invitation.accepted, false);
  });

  let invitationRoute;
  await check('Invitation acceptance creates the user and its department membership', async () => {
    invitationRoute = mailRoute('invite', email, outboxBefore);
    const ctx = await browser.newContext();
    const acceptor = await ctx.newPage();
    await acceptor.goto(doctorBase + invitationRoute);
    await acceptor.locator('[name=email]').fill(email);
    await acceptor.locator('[name=first_name]').fill('Synthetic');
    await acceptor.locator('[name=last_name]').fill('Accounts Check');
    await acceptor.locator('[name=password1]').fill(password);
    await acceptor.locator('[name=password2]').fill(password);
    await acceptor.locator('[name=synthetic_only]').check();
    await acceptor.getByRole('button', { name: 'Accept invitation', exact: true }).click();
    await acceptor.waitForURL(doctorBase + '/login/');
    report.account = python(
      "from core.models import User,Membership\nu=User.objects.get(email=payload['email'])\n"
      + "m=list(Membership.objects.filter(user=u,active=True).select_related('department'))\n"
      + "print(json.dumps({'verified':bool(u.verified_at),'memberships':len(m),"
      + "'department':str(m[0].department_id) if m else '','role':m[0].role if m else ''}))\n",
      { email });
    assert.equal(report.account.verified, true, 'the invited account was not verified by accepting');
    assert.equal(report.account.memberships, 1);
    assert.equal(report.account.department, invitationDepartment, 'the new membership is in a different department than the invitation');
    assert.equal(report.account.role, 'employee');
    await ctx.close();
  });

  await check('Exactly one $10 welcome credit is issued, and a retried acceptance does not issue a second', async () => {
    const before = python(
      "from core.models import User,Wallet,LedgerEntry\nu=User.objects.get(email=payload['email'])\n"
      + "w=Wallet.objects.get(user=u,kind='promo')\n"
      + "print(json.dumps({'balance':format(w.balance,'f'),'reserved':format(w.reserved,'f'),'welcome_entries':LedgerEntry.objects.filter(wallet=w,kind='welcome').count()}))\n",
      { email });
    // ⚠️ THE DECIMAL IS FORMATTED FIXED-POINT ON THE PYTHON SIDE, AND THAT IS NOT COSMETIC. `str()` on a
    // Decimal uses SCIENTIFIC notation once the exponent is negative and the value is zero: a wallet with
    // nothing reserved stringifies as `0E-12`, not `0.000000000000`. So a string comparison against a zero
    // literal fails for exactly the value a money assertion most needs to check — nothing reserved,
    // nothing charged — and it fails ONLY there, which is why it survived review. Measured on this host:
    // str(Decimal('0.000000000000')) == '0E-12'; format(..., 'f') == '0.000000000000'.
    assert.equal(before.balance, '10.000000000000');
    assert.equal(before.reserved, '0.000000000000');
    assert.equal(before.welcome_entries, 1);
    // ⚠️ THE RETRY IS THE CHECK — AND A GET ON THE SPENT LINK IS NOT A RETRY. core/views.py's
    // `invite_accept` opens with get_object_or_404(..., accepted_at__isnull=True), so a consumed link
    // answers 404 before one line of the acceptance path runs. That is worth asserting, but it exercises
    // the LINK, not the grant: a build whose welcome key was re-keyed per invitation would fund the wallet
    // twice and still pass it. The grant's idempotency key is `welcome:{user.pk}`, and the only way to
    // reach it a second time is a SECOND invitation accepted by the now-existing, signed-in user.
    const ctx = await browser.newContext();
    const retry = await ctx.newPage();
    assert.equal(await statusOf(retry, doctorBase + invitationRoute), 404, 'a consumed invitation link is still live');

    const secondOutbox = mailSnapshot();
    await createInvitation(email);
    const secondRoute = mailRoute('invite', email, secondOutbox);
    await login(retry, invited);
    await retry.waitForURL(doctorBase + '/');
    await retry.goto(doctorBase + secondRoute);
    await retry.getByRole('button', { name: 'Accept invitation', exact: true }).click();
    await retry.waitForURL(doctorBase + '/login/');
    // The acceptance really ran — otherwise welcome_credit() was never called a second time and the
    // assertions below would be measuring nothing.
    report.secondAcceptance = python(
      "from core.models import Invitation\ni=list(Invitation.objects.filter(email=payload['email']).order_by('created_at'))\n"
      + "print(json.dumps({'invitations':len(i),'accepted':sum(1 for x in i if x.accepted_at)}))\n",
      { email });
    assert.deepEqual(report.secondAcceptance, { invitations: 2, accepted: 2 },
      'the second invitation was not accepted, so the welcome grant was never retried');
    const after = python(
      "from core.models import User,Wallet,LedgerEntry,Membership\nu=User.objects.get(email=payload['email'])\n"
      + "w=Wallet.objects.get(user=u,kind='promo')\n"
      + "print(json.dumps({'balance':format(w.balance,'f'),'welcome_entries':LedgerEntry.objects.filter(wallet=w,kind='welcome').count(),"
      + "'wallets':Wallet.objects.filter(user=u,kind='promo').count(),"
      + "'memberships':Membership.objects.filter(user=u,active=True).count()}))\n",
      { email });
    assert.equal(after.welcome_entries, 1, 'a retried acceptance issued a second welcome grant');
    assert.equal(after.balance, before.balance, 'the promotional balance moved on a retried acceptance');
    assert.equal(after.wallets, 1);
    assert.equal(after.memberships, 1, 'a retried acceptance created a second membership');
    report.welcome = { before, after };
    await ctx.close();
  });

  await check('Cross-department access remains denied to the invited employee', async () => {
    const ctx = await browser.newContext();
    const employee = await ctx.newPage();
    await login(employee, invited);
    await employee.waitForURL(doctorBase + '/');
    const listed = (await (await employee.request.get(doctorBase + '/api/patients/')).json()).patients;
    assert(Array.isArray(listed), 'the patients API did not answer with a list');
    // ⚠️ SHARING THE INVITING DOCTOR'S PATIENTS IS THE DESIGN, NOT A LEAK — the employee was invited INTO
    // that department, and the README says a same-department colleague shares its patients. So the check
    // is not "sees something different from the doctor"; it is "sees this department and no other".
    report.isolation = python(
      "from core.models import User,Membership,Patient,Encounter\nfrom core.security import scoped\n"
      + "u=User.objects.get(email=payload['email'])\n"
      + "mine=set(Membership.objects.filter(user=u,active=True).values_list('department_id',flat=True))\n"
      + "seen=set(scoped(Patient,u).values_list('department_id',flat=True))\n"
      + "print(json.dumps({'own_departments':len(mine),'patient_departments_seen':len(seen),"
      + "'outside_own':len(seen-mine),'departments_total':Membership.objects.values('department_id').distinct().count(),"
      + "'patients_visible':scoped(Patient,u).count(),'patients_total':Patient.objects.count(),"
      + "'encounters_visible':scoped(Encounter,u).count(),'encounters_total':Encounter.objects.count(),"
      + "'encounter_in_own_department':str(scoped(Encounter,u).values_list('pk',flat=True).first() or '')}))\n",
      { email });
    const i = report.isolation;
    assert.equal(i.outside_own, 0, 'the employee can see a department they do not belong to');
    // ⚠️ AND THE ENCOUNTER SURFACE IS THE ONE THAT CARRIES THE NOTES, SO IT IS REQUESTED, NOT INFERRED.
    // Comparing scoped(Patient) in-process to /api/patients/ compares one function to itself: both call
    // the same scoped(). Deleting scoped() from api_encounter — every authenticated user reading every
    // department's notes and answers — would not move either number. So a real foreign reader asks for a
    // real encounter over HTTP. The Ultrasound clinician belongs to a different department in the same
    // organization; all twelve encounters are in the employee's.
    const foreignContext = await browser.newContext();
    const outsider = await foreignContext.newPage();
    await login(outsider, credentials.ultrasound);
    await outsider.waitForURL(doctorBase + '/');
    assert.equal(await statusOf(outsider, doctorBase + `/api/encounters/${i.encounter_in_own_department}/`), 404,
      'a clinician in another department read an encounter through the API');
    assert.equal(await statusOf(employee, doctorBase + `/api/encounters/${i.encounter_in_own_department}/`), 200,
      'the employee cannot read an encounter in their OWN department, so the denial above proves nothing');
    await foreignContext.close();
    // Positive controls: an empty scope and a single-department fixture would both pass vacuously.
    assert(i.patients_visible > 0, 'the employee sees no patients at all, so scoping proves nothing');
    assert(i.patients_total > i.patients_visible, 'every patient is visible, so isolation could not be observed');
    assert(i.departments_total > i.own_departments, 'the fixture has one department, so isolation could not be observed');
    assert(i.encounter_in_own_department, 'there is no encounter to request, so the API denial proves nothing');
    // Through HTTP as the employee, not only through scoped() in-process: every row the API hands back
    // must belong to a department they are a member of.
    assert.equal(listed.length, i.patients_visible, 'the API and the in-process scope disagree');
    assert.deepEqual([...new Set(listed.map(row => row.department_id))], [invitationDepartment],
      'the patients API returned a row outside the employee\'s own department');
    await ctx.close();
  });

  await check('Password recovery succeeds, invalidates the existing session, and its link is one-time', async () => {
    const oldContext = await browser.newContext();
    const oldPage = await oldContext.newPage();
    await login(oldPage, invited);
    await oldPage.waitForURL(doctorBase + '/');
    const outboxBeforeRecovery = mailSnapshot();
    const ctx = await browser.newContext();
    const recovery = await ctx.newPage();
    await recovery.goto(doctorBase + '/recovery/');
    await recovery.locator('[name=email]').fill(email);
    await recovery.getByRole('button', { name: 'Prepare recovery link', exact: true }).click();
    // core/recovery.py answers identically for unknown, unverified, inactive and rate-limited addresses —
    // deliberately. So this asserts the FORM was accepted and nothing more; that a message was actually
    // written is proved by the outbox diff below, which is the only evidence here that can fail.
    assert((await recovery.locator('[role=status]').innerText()).includes('If this address is eligible'));
    const resetRoute = mailRoute('recovery/confirm', email, outboxBeforeRecovery);
    await recovery.goto(doctorBase + resetRoute);
    assert(new URL(recovery.url()).pathname.endsWith('/set-password/'), 'the recovery link did not open the set-password step');
    const replacement = crypto.randomBytes(24).toString('base64url');
    await recovery.locator('[name=new_password1]').fill(replacement);
    await recovery.locator('[name=new_password2]').fill(replacement);
    await recovery.getByRole('button', { name: 'Update password', exact: true }).click();
    await recovery.waitForURL(doctorBase + '/recovery/complete/');
    // The session that existed before the reset must be gone.
    await oldPage.goto(doctorBase + '/patients/');
    await oldPage.waitForURL(/\/login\//);
    // The old password must no longer work, the new one must.
    await login(recovery, invited);
    assert.equal(new URL(recovery.url()).pathname, '/login/', 'the old password still signs in');
    invited.password = replacement;
    await login(recovery, invited);
    await recovery.waitForURL(doctorBase + '/');
    // And the link is spent.
    await recovery.goto(doctorBase + resetRoute);
    assert.equal(await recovery.getByRole('heading', { name: 'Recovery link unavailable', exact: true }).count(), 1,
      'a used recovery link was accepted again');
    report.recovery = { oldSessionInvalidated: true, oldPasswordRejected: true, linkSingleUse: true };
    await oldContext.close();
    await ctx.close();
  });

  await check('Administrator MFA remains enforced and a replayed code is refused', async () => {
    const ctx = await browser.newContext();
    const admin = await ctx.newPage();
    await login(admin, credentials.admin, adminBase);
    assert.equal(new URL(admin.url()).pathname, '/login/', 'the administrator signed in without a second factor');
    await assertNotRateLimited(admin, 'the second-factor requirement');
    // ⚠️ THE WAIT HAS A FLOOR, AND THE FLOOR IS NOT ABOUT THE TOTP STEP. `31000 - now % 30000` crosses into
    // the next 30-second step, but its minimum is 1001 ms — and the empty-OTP attempt just above is a
    // django-otp verification FAILURE, which arms verify_is_allowed's throttle for 2 s (and doubles on
    // each further failure). Landing inside that window makes a correct application look broken and
    // escalates the next run's delay.
    await admin.waitForTimeout(Math.max(2500, 31000 - Date.now() % 30000));
    const otp = totp(credentials.admin.totp_key_hex);
    await login(admin, credentials.admin, adminBase, otp);
    await admin.waitForURL(adminBase + '/console/');
    const replayContext = await browser.newContext();
    const replay = await replayContext.newPage();
    await login(replay, credentials.admin, adminBase, otp);
    assert.equal(new URL(replay.url()).pathname, '/login/', 'a replayed one-time code was accepted');
    // ⚠️ AND THE REFUSAL MUST BE THE RIGHT REFUSAL. core/views.py rate-limits by email at 8 POSTs per 600
    // seconds and this check spends three per run, so from the third run inside ten minutes every sign-in
    // is refused before the TOTP device is ever consulted — and a bare "we ended up on /login/" would
    // record `replayRefused: true` for a code that was never replayed.
    await assertNotRateLimited(replay, 'the replay refusal');
    assert.equal(await statusOf(replay, adminBase + '/console/'), 302);
    report.adminMfa = { secondFactorRequired: true, replayRefused: true };
    await replayContext.close();
    await ctx.close();
  });

  report.complete = true;
} catch (error) {
  // ⚠️ THE MESSAGE IS SUPPRESSED DELIBERATELY. An assertion over a page body, or a Python traceback, can
  // carry a raw token; the check name and the error class say enough to diagnose without that risk.
  report.failedCheck = currentCheck;
  report.failureClass = error?.constructor?.name || 'Error';
  console.error(`FAIL ${currentCheck}; sensitive exception details suppressed.`);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  report.finishedAt = new Date().toISOString();
  const destination = process.env.QUILLMD_ACCOUNTS_REPORT || path.join(runtime, 'private-accounts-verification.json');
  await fs.writeFile(destination, JSON.stringify(report, null, 2) + '\n', { mode: 0o600 });
  console.log(`${report.checks.filter(r => r.passed).length} checks passed; complete=${report.complete}`);
}
