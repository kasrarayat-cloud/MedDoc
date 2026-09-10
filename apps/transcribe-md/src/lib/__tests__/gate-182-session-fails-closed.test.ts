// ============================================================================
// #182 — "CANNOT TELL" IS NOT "INVALID", AND NEITHER IS "FINE"
// ----------------------------------------------------------------------------
// ⚠️ THIS GATE EXISTS BECAUSE THE SAME BRANCH WAS SHIPPED WRONG TWICE, IN
// OPPOSITE DIRECTIONS, AND BOTH TIMES A SOURCE-TEXT ARM WAS GREEN.
//
//   before #181(d)  a validateSession THROW failed OPEN — the JWT was honoured
//                   and every revocation gate was skipped. A deactivated,
//                   suspended or signed-out account kept being served.
//   #181(d)         made it `return null`. That fixed the honouring and broke
//                   the other end: @auth/core answers a null token with
//                   `sessionStore.clean()`, so a TRANSIENT pool timeout DELETED
//                   the cookie and ejected a working doctor permanently.
//   #182(1)         separates the two answers. A DEFINITIVE "revoked/inactive"
//                   returns null and the cookie goes. A "the database could not
//                   answer" RETAINS the token, MARKS it, and the request is
//                   refused 503 — a blip costs one retry, not a re-login.
//
// ⚠️ THESE ARMS DRIVE THE REAL CALLBACK AND ASSERT ITS RETURN. The previous
// gate asserted LOG TEXT, which the adversarial pass showed would stay green
// while the pre-fix pass-through was restored verbatim. A rule about what a
// function RETURNS has to be tested by calling it.
//
// The mock seam is `@meddoc/db` — a package specifier — so the REAL
// `validateSession` runs against a controllable prisma. Mocking
// `validateSession` itself would test the mock.
// ============================================================================
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { beforeEach, describe, expect, it, vi } from 'vitest';

const findUnique = vi.fn();

// ⚠️ THE MOCK IS COMPLETE BECAUSE THE POSITIVE CONTROL REFUSED AN INCOMPLETE
// ONE. The first version supplied only `findUnique` and `deleteMany`; the real
// `validateSession` also calls `update` (it touches lastSeenAt), so EVERY call
// threw `userSession.update is not a function` and every token came back marked
// — including the healthy one. Read quickly that is "the fix works". It is the
// mock failing, and the control is the only arm that could tell the difference.
// ⚠️ `next/headers` IS MOCKED BECAUSE THE SIGN-IN BRANCH READS IT, AND WITHOUT
// IT EVERY SIGN-IN THREW `headers was called outside a request scope` — which
// looks EXACTLY like the fail-closed refusal under test. Three mock layers had
// to be completed before the success path ran once (`userSession.update`, the
// transaction's `tx` shape, and this), and at each layer the refusal arms were
// green and the single success arm was the only thing objecting.
vi.mock('next/headers', () => ({
  headers: async () => new Map<string, string>(),
}));

const recordSession = vi.fn(async () => ({}));
type UserUpdateArg = { where: { id: string }; data: { mfaBackupCodes: { set: string[] } } };
// ⚠️ TYPED WITH ITS ARGUMENT, because the arm READS the argument. `vi.fn(async
// () => ({}))` infers a zero-arg mock, so `calls[0][0]` does not typecheck —
// and vitest never noticed, because vitest does not typecheck. tsc did.
const userUpdate = vi.fn(async (_arg: UserUpdateArg) => ({}));

vi.mock('@meddoc/db', () => ({
  default: {
    userSession: {
      findUnique,
      create: recordSession,
      update: vi.fn(async () => ({})),
      updateMany: vi.fn(async () => ({})),
      deleteMany: vi.fn(async () => ({})),
    },
    user: { update: userUpdate },
    // ⚠️ THE TRANSACTION HANDS A REAL-SHAPED `tx`, AND THE FIRST VERSION DID
    // NOT. `recordSessionLogin` runs `prisma.$transaction(tx => { tx.userSession
    // .deleteMany(...); tx.userSession.create(...) })`. Passing `{}` made EVERY
    // sign-in throw — so the "a refused sign-in does not consume the code" arm
    // passed while proving nothing, and only the success arm disagreed. A
    // broken mock and a working fail-closed guard produce the same observable.
    $transaction: vi.fn(async (fn: unknown) =>
      typeof fn === 'function'
        ? (fn as (t: unknown) => unknown)({
            userSession: { deleteMany: vi.fn(async () => ({})), create: recordSession },
          })
        : fn,
    ),
  },
}));

const { authConfig } = await import('@meddoc/auth');

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const jwt = (authConfig as any).callbacks.jwt as (a: {
  token: Record<string, unknown>;
  user?: unknown;
}) => Promise<Record<string, unknown> | null>;

const LIVE_ROW = {
  id: 'us_1',
  expiresAt: new Date(Date.now() + 60 * 60 * 1000),
  // ⚠️ ADMIN-6a — THE PRACTICE IS PART OF A LIVE SESSION NOW. `validateSession`
  // fails CLOSED on an absent practice (D2), so a fixture without one is an
  // archived member, not a healthy one — and this positive control redded the
  // moment D2 landed, which is it doing its job.
  user: {
    isActive: true,
    suspendedAt: null,
    softDeletedAt: null,
    forceLogoutAt: null,
    practice: { isActive: true },
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

describe('#182(1) — the jwt callback distinguishes CANNOT TELL from INVALID', () => {
  it('POSITIVE CONTROL: a live session is returned unmarked — the arms below are not vacuous', async () => {
    findUnique.mockResolvedValue(LIVE_ROW);
    const out = await jwt({ token: { sessionId: 'sess_live', id: 'u1' } });
    expect(out, 'a healthy session was rejected — every arm below is meaningless').not.toBeNull();
    expect(out!.sessionVerifyFailed).toBeUndefined();
  });

  it('DEFINITIVE (row gone) → null, so the cookie is cleared', async () => {
    findUnique.mockResolvedValue(null);
    const out = await jwt({ token: { sessionId: 'sess_revoked', id: 'u1' } });
    expect(out, 'a revoked session was still served').toBeNull();
  });

  it('⚠️ CANNOT TELL (the lookup THROWS) → the token is RETAINED and MARKED, never null', async () => {
    findUnique.mockRejectedValue(new Error('P2024 pool timeout'));
    const out = await jwt({ token: { sessionId: 'sess_blip', id: 'u1' } });
    // NOT null: returning null makes @auth/core clear the cookie, which turns a
    // transient blip into a permanent ejection. This is the #181(d) defect.
    expect(out, 'a transient DB blip cleared the session cookie').not.toBeNull();
    // and NOT a usable session either: the marker is what makes getSession refuse
    expect(out!.sessionVerifyFailed, 'the token was returned UNMARKED — that is the original fail-open').toBe(true);
  });

  it('a later successful verification CLEARS the marker — one blip does not stick', async () => {
    findUnique.mockRejectedValueOnce(new Error('P2024 pool timeout'));
    const blipped = await jwt({ token: { sessionId: 'sess_x', id: 'u1' } });
    expect(blipped!.sessionVerifyFailed).toBe(true);

    findUnique.mockResolvedValue(LIVE_ROW);
    const recovered = await jwt({ token: { ...blipped! } });
    expect(
      recovered!.sessionVerifyFailed,
      'the marker persisted after a clean verification — every later request 503s forever',
    ).toBeUndefined();
  });

  it('⚠️ AN UNVERIFIED TOKEN YIELDS NO IDENTITY — fail-closed at the SOURCE', async () => {
    // ⚠️ THIS ARM REPLACES ONE THAT ASSERTED THE WRONG CONTRACT. It used to
    // check only that the marker CROSSED into the session — which it did, while
    // `session.user.id` was still populated. The second adversarial pass showed
    // what that meant in the real tree: every consumer that reads `auth()`
    // WITHOUT knowing about the marker got a working session. A suspended
    // doctor was served a patient chart in apps/meddoc-pro, and six
    // account-control routes in this app accepted a force-logged-out attacker.
    // All of them refused at the parent commit.
    //
    // Checking the marker was OPT-IN. Withholding the identity is not.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sessionCb = (authConfig as any).callbacks.session as (a: {
      session: { user: Record<string, unknown> };
      token: Record<string, unknown>;
    }) => Promise<{ user: Record<string, unknown> }>;

    // ⚠️ THE FIXTURE PRE-POPULATES THE IDENTITY, AND AN EARLIER VERSION DID
    // NOT — so the arm passed whether the code stripped the id or merely never
    // set it, and deleting the strip redded NOTHING. An arm needs the input
    // that DISTINGUISHES the two explanations; here that means handing it a
    // session that already carries an identity and requiring it to be gone.
    const unverified = await sessionCb({
      session: {
        user: {
          email: 'doc@example.invalid',
          id: 'u1',
          role: 'DOCTOR',
          practiceId: 'prac_1',
          sessionId: 's1',
        },
      },
      token: {
        id: 'u1',
        sessionId: 's1',
        role: 'DOCTOR',
        practiceId: 'prac_1',
        sessionVerifyFailed: true,
      },
    });

    // THE PROPERTY EVERY CONSUMER ALREADY GATES ON — `if (!userId) return 401`
    expect(
      unverified.user.id,
      'an unverified token still yields an identity — every auth() consumer is open',
    ).toBeUndefined();
    // and nothing else usable comes through either
    expect(unverified.user.role).toBeUndefined();
    expect(unverified.user.practiceId).toBeUndefined();
    expect(unverified.user.sessionId).toBeUndefined();
    // the marker DOES survive, so getSession can raise a truthful 503 rather
    // than letting the request look like an ordinary signed-out one
    expect(unverified.user.sessionVerifyFailed).toBe(true);
  });

  it('POSITIVE CONTROL: a VERIFIED token still yields a full identity', async () => {
    // Without this, the arm above is satisfied by a session callback that
    // withholds the identity from everyone — which would sign the whole product
    // out rather than fail closed on one request.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sessionCb = (authConfig as any).callbacks.session as (a: {
      session: { user: Record<string, unknown> };
      token: Record<string, unknown>;
    }) => Promise<{ user: Record<string, unknown> }>;

    const ok = await sessionCb({
      session: { user: {} },
      token: { id: 'u1', sessionId: 's1', role: 'DOCTOR', practiceId: 'prac_1' },
    });
    expect(ok.user.id, 'a healthy session was stripped — the product is signed out').toBe('u1');
    expect(ok.user.practiceId).toBe('prac_1');
    expect(ok.user.sessionVerifyFailed).toBe(false);
  });

  it('(e) a token with NO sessionId is rejected', async () => {
    const out = await jwt({ token: { id: 'u1' } });
    expect(out).toBeNull();
  });
});

describe('#182(4) — a refused sign-in costs the doctor nothing', () => {
  it('⚠️ NO RATE-LIMIT STRIKE — asserted, not assumed', () => {
    // The refusal lives in the jwt callback, which runs AFTER `authorize()` has
    // already succeeded and reset the counter. Both halves are read from source
    // rather than trusted: the increment sites must be inside authorize's
    // failure path, and the success path must zero the counter.
    const nextauth = readFileSync(
      join(__dirname, '..', 'nextauth.ts'),
      'utf8',
    );
    expect(nextauth).toContain('failedLoginCount: 0');
    // and the refusal itself must not touch the counter at all
    const shared = readFileSync(
      join(__dirname, '..', '..', '..', '..', '..', 'packages', 'auth', 'src', 'index.ts'),
      'utf8',
    );
    const refusal = shared.slice(
      shared.indexOf('SESSION_TRACKING_FAILED') - 2000,
      shared.indexOf('SESSION_TRACKING_FAILED') + 500,
    );
    expect(refusal).not.toContain('failedLoginCount');
  });

  it('the recovery code is consumed ONLY when the sign-in completes', async () => {
    findUnique.mockResolvedValue(LIVE_ROW);
    userUpdate.mockClear();
    await jwt({
      token: {},
      user: { id: 'u1', pendingRecoveryHash: 'hash_b', mfaBackupCodes: ['hash_a', 'hash_b'] },
    });
    expect(userUpdate, 'a completed sign-in did not consume the code').toHaveBeenCalled();
    const arg = userUpdate.mock.calls[0]![0];
    expect(arg.data.mfaBackupCodes.set, 'the wrong code was consumed').toEqual(['hash_a']);
  });

  it('⚠️ a REFUSED sign-in does NOT consume the code — the defect that burned a set', async () => {
    // recordSessionLogin throws -> #182(c) refuses -> the code must survive.
    // Before this, `authorize()` burned it on match, so each retry against a DB
    // blip destroyed another single-use code while reporting "Invalid recovery
    // code" to a doctor whose code was fine.
    recordSession.mockRejectedValueOnce(new Error('P2024 pool timeout'));
    userUpdate.mockClear();
    await expect(
      jwt({
        token: {},
        user: { id: 'u1', pendingRecoveryHash: 'hash_b', mfaBackupCodes: ['hash_a', 'hash_b'] },
      }),
    ).rejects.toThrow(/SESSION_TRACKING_FAILED/);
    expect(userUpdate, 'a refused sign-in still burned the recovery code').not.toHaveBeenCalled();
  });
});

describe('#182(1) — the 503 surface is reachable', () => {
  it('the boundary literal matches the class constant — they cannot drift silently', () => {
    const shared = readFileSync(
      join(__dirname, '..', '..', '..', '..', '..', 'packages', 'auth', 'src', 'index.ts'),
      'utf8',
    );
    const boundary = readFileSync(join(__dirname, '..', '..', 'app', 'error.tsx'), 'utf8');
    // ⚠️ The literal is duplicated ON PURPOSE — importing @meddoc/auth into a
    // 'use client' boundary would pull prisma into the client bundle. A
    // deliberate duplication needs a gate, or it is just a duplication.
    const m = /static readonly DIGEST = '([^']+)'/.exec(shared);
    expect(m, 'the class no longer declares a DIGEST').not.toBeNull();
    expect(boundary).toContain(`SESSION_UNVERIFIABLE_DIGEST = '${m![1]}'`);
    expect(boundary).toContain('SessionUnverifiable');
  });

  it('the surface says NOT SIGNED OUT and offers a retry', () => {
    const surface = readFileSync(
      join(__dirname, '..', '..', 'components', 'session-unverifiable.tsx'),
      'utf8',
    );
    expect(surface).toMatch(/have not been signed out/i);
    expect(surface).toContain('session-unverifiable-retry');
    expect(surface).toContain("role=\"alert\"");
  });
});
