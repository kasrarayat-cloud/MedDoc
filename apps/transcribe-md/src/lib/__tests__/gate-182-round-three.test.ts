// ============================================================================
// #182 ROUND THREE — THE WATCHED SET IS THE TREE, AND THE MIDDLEWARE IS IN IT
// ----------------------------------------------------------------------------
// ⚠️ TWO ROUNDS OF THE ADVERSARIAL PASS EACH FOUND THE SAME SHAPE: a shared
// contract changed, and only the callers the author had opened changed with it.
//
//   round one   `signOutAction` began returning early on failure; two doors it
//               never opened discarded the result, so the cookie was never
//               cleared and nothing was shown. One was mounted in the ROOT
//               LAYOUT.
//   round two   the jwt callback began RETAINING a marked token, so `auth()`
//               returned a populated session for a token whose validity was
//               unknown. A suspended doctor reached a patient chart in
//               apps/meddoc-pro; six account-control routes accepted a
//               force-logged-out attacker. All refused at the parent commit.
//
// Both were cured at the SOURCE — the second by withholding the identity, so
// every consumer's existing `if (!userId) return 401` refuses with no edit.
// This gate exists so the third instance is caught by a test rather than by a
// third pass: the consumer list is GREPPED FROM THE TREE, and a consumer that
// appears tomorrow is watched tomorrow.
// ============================================================================
import { execSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));

const { authConfig } = await import('@meddoc/auth');
const REPO = join(__dirname, '..', '..', '..', '..', '..');

/**
 * ⚠️ CONSUMERS THAT LEGITIMATELY MAKE NO IDENTITY CHECK, EACH WITH ITS REASON
 * AND ITS RETIREMENT CONDITION. A new consumer is NOT here, so it must gate —
 * the list fails closed.
 */
const NO_IDENTITY_CHECK_REQUIRED: Record<string, string> = {
  'apps/transcribe-md/src/components/ui/app-frame.tsx':
    'display chrome only — reads a name for the header and makes no authorization ' +
    'decision. Safe because an unverified session now carries NO name or email ' +
    'either, so it falls back to "Doctor". RETIRES if this file ever reads ' +
    'practiceId, role, or any patient data.',
};

/**
 * ⚠️ ONE STRING, USED TWICE — the argument grep receives, and the thing the
 * SCOPE arm measures. That sharing is what lets the arm fail: a rescope moves
 * the population AND the measurement together, so the two derivations below
 * stop agreeing. Never re-spell it at either use site.
 */
const CONSUMER_SCAN_ROOTS = 'apps/*/src';

/**
 * The directories the scan ACTUALLY reaches: the same roots string, handed to
 * the same shell, from the same cwd grep runs in — so this expansion IS grep's
 * expansion. ⚠️ Deliberately NOT read off this file's own source; that is the
 * defect being repaired.
 */
function scannedDirs(roots: string): string[] {
  return execSync(`ls -d ${roots} 2>/dev/null || true`, { cwd: REPO, encoding: 'utf8' })
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
    // sh leaves an unmatched glob as its own literal, and a path that does not
    // exist was never scanned.
    .filter((p) => existsSync(join(REPO, p)))
    .sort();
}

/** Every app that HAS sources — enumerated from the tree, never from a name. */
function appSourceDirs(): string[] {
  return readdirSync(join(REPO, 'apps'), { withFileTypes: true })
    // sh globs skip dot-directories, so RIGHT must skip them too — otherwise a
    // stray `apps/.something/src` reds this arm for a reason that has nothing
    // to do with the scan's scope.
    .filter((d) => d.isDirectory() && !d.name.startsWith('.'))
    .map((d) => `apps/${d.name}/src`)
    .filter((p) => existsSync(join(REPO, p)))
    .sort();
}

/**
 * The consumer enumeration, over whatever roots it is given.
 * `|| true` because grep exits 1 on no match, and an app with no session
 * consumers (apps/marketing) is a legitimate answer, not an error.
 */
function consumersUnder(roots: string): string[] {
  return execSync(
    `grep -rln 'await auth()' ${roots} --include='*.ts' --include='*.tsx' ` +
      "| grep -v '__tests__' | grep -v '\\.test\\.' || true",
    { cwd: REPO, encoding: 'utf8' },
  )
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
    .sort();
}

describe('#182 round 3 — every session consumer refuses an unverified token', () => {
  const consumers = consumersUnder(CONSUMER_SCAN_ROOTS);

  it('NON-VACUITY: the enumeration finds the real population', () => {
    expect(consumers.length, 'the consumer grep found nothing — every arm below is vacuous').toBeGreaterThan(12);
  });

  it('⚠️ POSITIVE CONTROL: the tree can still EXPRESS a cross-app claim', () => {
    // Without this, "the scan covers every app" is satisfied by a tree holding
    // exactly ONE app, and the SCOPE arm below becomes a tautology of a new
    // shape rather than a check. `apps/` is enumerated, never named.
    expect(
      appSourceDirs().length,
      'apps/ holds fewer than two source trees, so there is no cross-app ' +
        'property left to assert. RETIRE this describe deliberately — do not ' +
        'let it pass empty.',
    ).toBeGreaterThan(1);
  });

  it('⚠️ POSITIVE CONTROL: the comparison REJECTS a single-app scope', () => {
    // Aimed where the answer is NOT predetermined — it plants the exact defect
    // the SCOPE arm names and requires the comparison to say NO. The planted
    // scope is DERIVED from the tree, so no app name is hard-coded here either.
    const oneApp = appSourceDirs()[0];
    expect(
      scannedDirs(oneApp),
      `the planted single-app scope ${oneApp} resolves to nothing — this control is vacuous`,
    ).toEqual([oneApp]);
    expect(
      scannedDirs(oneApp),
      'a one-app scope compared EQUAL to the whole tree — the SCOPE arm below cannot fail',
    ).not.toEqual(appSourceDirs());
  });

  it('SCOPE: the enumeration scans EVERY app, not one', () => {
    // ⚠️ DMP-a — THE CLAIM IS ABOUT THE ENUMERATION'S **SCOPE**, NOT ITS HITS.
    //
    // This asserted a consumer exists under `apps/meddoc-pro/`, which is right
    // while that app has one and turns CI RED on `main` the moment
    // DELETE-MEDDOC-PRO removes it. A6, the nine-row recon and #307's own
    // filing all reasoned from "CI never touches meddoc-pro" — measured off the
    // BUILD lines, true and incomplete: this is a MERGE-GATING test that reads
    // it and asserts the directory is in the population.
    //
    // ⚠️ AND THE FIRST REWRITE OF THIS ARM WAS ALSO WRONG — it demanded a hit
    // in whatever other app exists, so with `meddoc-pro` gone it failed on
    // `apps/marketing`, which has no session consumers and never will. Found by
    // actually deleting the app and re-running, not by reading.
    //
    // ⚠️ AND THE SECOND REWRITE WAS THE WORST OF THE THREE — IT COULD NOT FAIL.
    // It did `readFileSync(__filename)` and asserted the file CONTAINED the
    // literal `apps/*/src`, while the assertion's own argument was the third
    // occurrence of that literal in the file. A probe whose pattern appears in
    // the searcher cannot return false: rescoping the grep to one app left it
    // GREEN, in the merge-gating `unit` job, on the very defect its failure
    // message names. Refutation round, upheld 2 of 2.
    //
    // What round two's blindness was about is the SCAN. So the property is
    // MEASURED, from two independent derivations that must agree:
    //   LEFT   what the scan reaches — the same roots string, expanded by the
    //          same shell from the same cwd that grep runs in.
    //   RIGHT  what exists — `apps/` enumerated off the filesystem.
    // Rescoping the roots moves LEFT and not RIGHT, so the arm reds. Deleting
    // an app moves BOTH, so DELETE-MEDDOC-PRO stays green — which is the whole
    // point of DMP-a.
    expect(
      scannedDirs(CONSUMER_SCAN_ROOTS),
      'the enumeration is scoped to one app — the cross-app blindness of round two, re-created inside the gate',
    ).toEqual(appSourceDirs());
  });

  it('POPULATION: the enumeration finds every consumer any app holds', () => {
    // ⚠️ THE SCOPE ARM ABOVE MEASURES THE DECLARED ROOTS, AND THAT IS A HOLE
    // ONE LAYER UP — re-spell the path at the CALL SITE and leave the constant
    // alone, and it stays green while the population silently loses an app.
    // Found by refuting the repair rather than by trusting it; the previous two
    // rewrites of this arm both failed on the step after the one they fixed.
    //
    // So the POPULATION is compared too, and this side does not care how the
    // scan is spelled: LEFT is whatever `consumers` actually contains, RIGHT is
    // the same enumeration run once per app directory found on disk. Narrow the
    // scan ANYWHERE — the constant, an inlined literal, a bypassed helper — and
    // LEFT loses a file RIGHT still has.
    //
    // ⚠️ IT IS NOT A SUBSTITUTE FOR THE SCOPE ARM AND DOES NOT SUPERSEDE IT.
    // A scan narrowed to the apps that happen to have consumers today passes
    // THIS and fails THAT, and it is exactly round two's blindness pointed at
    // whichever app gains its first consumer tomorrow. Two arms, two defects.
    expect(
      consumers,
      'the enumeration missed a consumer that a per-app scan finds — it is not reaching every app',
    ).toEqual(appSourceDirs().flatMap((d) => consumersUnder(d)).sort());
  });

  it('each consumer gates on the IDENTITY, or is a named exemption with a reason', () => {
    const ungated = consumers.filter((c) => {
      if (c in NO_IDENTITY_CHECK_REQUIRED) return false;
      const src = readFileSync(join(REPO, c), 'utf8');
      return !/\?\.user\?\.id|user\.id\b/.test(src);
    });
    expect(
      ungated,
      'these read auth() and never check the identity, so an unverified token ' +
        'reaches them as a usable session. Gate them, or add a REASON to ' +
        'NO_IDENTITY_CHECK_REQUIRED — the default is to gate.',
    ).toEqual([]);
  });

  it('every exemption still exists — a stale allowlist row hides a deleted file', () => {
    for (const path of Object.keys(NO_IDENTITY_CHECK_REQUIRED)) {
      expect(consumers, `${path} is exempted but no longer reads auth()`).toContain(path);
    }
  });
});

describe('#182 round 3 — an unverified session carries NOTHING usable', () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sessionCb = (authConfig as any).callbacks.session;

  it('no identity AND no display fields survive', async () => {
    const out = await sessionCb({
      session: {
        user: { id: 'u1', role: 'DOCTOR', practiceId: 'p1', sessionId: 's1', email: 'd@x.invalid', name: 'Dr X' },
      },
      token: { id: 'u1', sessionId: 's1', role: 'DOCTOR', practiceId: 'p1', sessionVerifyFailed: true },
    });
    for (const f of ['id', 'role', 'practiceId', 'sessionId', 'name', 'email']) {
      expect(out.user[f], `${f} survived an unverified session`).toBeUndefined();
    }
    expect(out.user.sessionVerifyFailed).toBe(true);
  });

  it('⚠️ POSITIVE CONTROL: the product is NOT signed out — a healthy token keeps everything', async () => {
    // Without this, every arm above is satisfied by a callback that withholds
    // the identity from EVERYONE, which signs the whole product out and would
    // read as maximally fail-closed.
    const out = await sessionCb({
      session: { user: {} },
      token: { id: 'u1', sessionId: 's1', role: 'DOCTOR', practiceId: 'p1' },
    });
    expect(out.user.id, 'a healthy session lost its identity — the product is signed out').toBe('u1');
    expect(out.user.role).toBe('DOCTOR');
    expect(out.user.practiceId).toBe('p1');
    expect(out.user.sessionId).toBe('s1');
  });
});

describe('#182 round 3 — the MIDDLEWARE surfaces 503, never a /login redirect', () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const authorized = (authConfig as any).callbacks.authorized;
  const run = async (auth: unknown) => {
    const prev = process.env.AUTH_USE_MOCK;
    process.env.AUTH_USE_MOCK = 'false';
    try {
      return await authorized({ auth, request: { nextUrl: { pathname: '/dashboard' } } });
    } finally {
      process.env.AUTH_USE_MOCK = prev;
    }
  };

  it('⚠️ an UNVERIFIED session is ANSWERED WITH A REAL 503 — not a redirect, not a 500', async () => {
    // ⚠️ THIS ARM'S SUBJECT CHANGED UNDER #186(a), SO IT IS REWRITTEN AND
    // RE-PROVED. Round three asserted `true` here: the request reached the page,
    // whose getSession() threw and rendered the verifying-session surface. Right
    // in substance, wrong in STATUS — a thrown error reaches Next's boundary as
    // a 500, so the system never sent the 503 that three of its own comments
    // claimed. `next-auth/lib/index.js:151` accepts a Response from this
    // callback, which makes it the boundary that ANSWERS the request.
    //
    // A redirect would be the eject-on-a-blip #182(1) forbids. A 500 would say
    // something is broken. 503 says: not now, try again, you are still signed in.
    const res = await run({ user: { sessionVerifyFailed: true } });
    expect(res, 'the middleware no longer answers the request itself').toBeInstanceOf(Response);
    expect((res as Response).status, 'an unverifiable session is not answered 503').toBe(503);
    expect((res as Response).headers.get('retry-after')).toBe('2');
    const body = await (res as Response).clone().text();
    // the body must say it is NOT a sign-out, or the doctor reads it as one
    expect(body).toMatch(/have not been signed out/i);
    // ⚠️ AND IT MUST NOT BE A REDIRECT — `next-auth` reads a Location header off
    // a returned Response and follows it, which would silently restore the
    // exact behaviour this forbids.
    expect((res as Response).headers.get('Location'), 'the 503 carries a redirect').toBeNull();
  });

  it('a genuinely SIGNED-OUT request is still refused', async () => {
    expect(await run(null), 'the middleware stopped protecting /dashboard').toBe(false);
    // and an identity-less session that is NOT marked is not a session at all
    expect(await run({ user: {} }), 'an identity-less unmarked session was admitted').toBe(false);
  });

  it('POSITIVE CONTROL: a healthy session is admitted', async () => {
    expect(await run({ user: { id: 'u1', role: 'DOCTOR' } })).toBe(true);
  });
});

describe('#182 round 3 — apps/meddoc-pro is RECORDED, not verified', () => {
  it('its fix is incidental and that is written down', () => {
    // Owner ruling: meddoc-pro serves 410 and is slated for deletion, so it is
    // recorded rather than verified. It is covered ONLY because the cure is at
    // the source — it never reads the marker itself. If that app is ever
    // revived, this is the note that says its session handling was never
    // independently checked.
    // ⚠️ DMP-a — this THREW when the file went. The note it carries is about a
    // retired app; once the app is deleted the note has served its purpose and
    // the arm must not be the thing that fails.
    const p = join(REPO, 'apps/meddoc-pro/src/lib/auth.ts');
    if (!existsSync(p)) {
      expect(existsSync(join(REPO, 'apps/meddoc-pro')), 'the app is gone — this note is discharged').toBe(false);
      return;
    }
    const src = readFileSync(p, 'utf8');
    expect(src, 'meddoc-pro now reads the marker — update this note').not.toContain(
      'sessionVerifyFailed',
    );
  });
});
