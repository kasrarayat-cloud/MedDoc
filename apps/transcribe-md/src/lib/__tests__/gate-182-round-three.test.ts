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
import { readFileSync } from 'node:fs';
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

describe('#182 round 3 — every session consumer refuses an unverified token', () => {
  const consumers = execSync(
    "grep -rln 'await auth()' apps/*/src --include='*.ts' --include='*.tsx' " +
      "| grep -v '__tests__' | grep -v '\\.test\\.'",
    { cwd: REPO, encoding: 'utf8' },
  )
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean);

  it('NON-VACUITY: the enumeration finds the real population, across apps', () => {
    expect(consumers.length, 'the consumer grep found nothing — every arm below is vacuous').toBeGreaterThan(12);
    // it must reach BEYOND transcribe-md, or the cross-app blindness of round
    // two is simply re-created inside the gate
    expect(
      consumers.some((c) => c.startsWith('apps/meddoc-pro/')),
      'the enumeration does not cross app boundaries — round two lived exactly there',
    ).toBe(true);
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

  it('⚠️ an UNVERIFIED session is ALLOWED THROUGH — a redirect here is eject-on-a-blip', async () => {
    // It must reach the page, whose getSession() refuses 503 with the cookie
    // intact. Returning false would send the doctor to /login and tell them
    // they are signed out — which they are not, and the next request may
    // succeed. This behaviour was CORRECT BY ACCIDENT before round three:
    // `!!auth?.user` is truthy for an identity-less user object, so tightening
    // it to `?.user?.id` — an obvious-looking improvement — would have broken it.
    expect(
      await run({ user: { sessionVerifyFailed: true } }),
      'an unverifiable session is being redirected to /login',
    ).toBe(true);
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
    const src = readFileSync(join(REPO, 'apps/meddoc-pro/src/lib/auth.ts'), 'utf8');
    expect(src, 'meddoc-pro now reads the marker — update this note').not.toContain(
      'sessionVerifyFailed',
    );
  });
});
