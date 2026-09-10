// @vitest-environment node
// ============================================================================
// THE ADMIN MFA GATES ARE **DRIVEN**, NOT READ — BOTH DOORS
// ----------------------------------------------------------------------------
// `gate-admin-api-mfa-parity.test.ts` pinned this rule with token and regex
// arms, and is retired by the commit that adds this file. A sealed refutation
// round (PR #952, ruling #310) broke five of its six arms while every one
// stayed green:
//
//   - the PAGE gate's `!` removed (the gate inverted): 6/6 green
//   - the API refusal moved AFTER the handler, with one earlier mention of
//     `userRow.mfaEnabled`: 6/6 green (indexOf found the wrong mention)
//   - the flag read off the token through an alias (`tok.mfaEnabled`): 6/6 green
//   - the refusal wrapped in a default-off env condition: 6/6 green
//   - a second user query spelled `findFirst`: 6/6 green
//
// Every one of those is invisible to an arm that reads source, and visible to
// an arm that RUNS the door. Ruling #251 already retired text scanners as
// proofs of behaviour; this file applies it here.
//
// What is real: `adminApi()` itself, `app/admin/layout.tsx` itself, and
// `@prisma/client`'s `Product`. What is mocked: the session (`auth()`), the
// user row (`@meddoc/db`), the audit writer, the 12-h freshness helper
// (answers "fresh", so it cannot be the reason for a refusal), and Next's
// `redirect`/`notFound` (which throw, exactly as the real ones do).
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => {
  const state: { row: Record<string, unknown> | null } = { row: null };
  /** Every method called on `prisma.user`, in order, whatever its spelling —
   *  so a second read of the user row cannot hide behind `findFirst`. */
  const userCalls: string[] = [];
  const user = new Proxy(
    {},
    {
      get: (_t, prop) => {
        if (typeof prop !== 'string') return undefined;
        return (..._args: unknown[]) => {
          userCalls.push(prop);
          if (prop === 'findUnique' || prop === 'findFirst') {
            return Promise.resolve(state.row ? { ...state.row } : null);
          }
          return Promise.resolve(null);
        };
      },
    }
  );
  class Redirect extends Error {
    constructor(public url: string) {
      super('NEXT_REDIRECT');
    }
  }
  class NotFound extends Error {
    constructor() {
      super('NEXT_NOT_FOUND');
    }
  }
  return {
    state,
    userCalls,
    prisma: { user },
    auth: vi.fn(),
    logAudit: vi.fn(),
    isAdminSessionStale: vi.fn(async () => false),
    Redirect,
    NotFound,
    redirect: vi.fn((url: string) => {
      throw new Redirect(url);
    }),
    notFound: vi.fn(() => {
      throw new NotFound();
    }),
  };
});

vi.mock('@meddoc/db', () => ({ default: h.prisma }));
vi.mock('@/lib/nextauth', () => ({ auth: h.auth }));
vi.mock('@/lib/audit', () => ({ logAudit: h.logAudit }));
vi.mock('@/lib/admin-session-freshness', () => ({
  isAdminSessionStale: h.isAdminSessionStale,
}));
vi.mock('next/navigation', () => ({ redirect: h.redirect, notFound: h.notFound }));
vi.mock('next/headers', () => ({
  headers: async () => new Headers({ 'next-url': '/admin' }),
}));

import type { NextRequest } from 'next/server';
import { adminApi } from '../admin-api-gate';
import { APP_URL } from '../constants';
import AdminLayout from '../../app/admin/layout';

/** A session that CLAIMS everything — SUPER_ADMIN and an enrolled factor — in
 *  every place a lazy read might look. The DB row is the only thing that may
 *  decide, so any arm below that refuses is refusing on the row. */
const CLAIMING_SESSION = {
  user: {
    id: 'sa-1',
    email: 'sa@example.test',
    role: 'DOCTOR',
    sessionId: 'sess-1',
    products: ['SUPER_ADMIN'],
    mfaEnabled: true,
  },
  mfaEnabled: true,
  expires: '2099-01-01T00:00:00.000Z',
};

const SA_ROW = { products: ['SUPER_ADMIN'], isActive: true };

const adminAccessWrites = () =>
  h.logAudit.mock.calls.filter(
    (c) => (c[0] as { action?: string } | undefined)?.action === 'ADMIN_API_ACCESS'
  );

function drive() {
  const handler = vi.fn(async () => new Response('ok', { status: 200 }));
  const route = adminApi('mfa-behavioural:probe', handler);
  const req = new Request('https://admin.example.test/api/admin/users', {
    method: 'GET',
  }) as unknown as NextRequest;
  return { handler, run: () => route(req) };
}

/** Env vars whose NAME mentions MFA are removed for the refusal arms, so a
 *  refusal that only fires when some flag is set cannot pass. */
let savedMfaEnv: Record<string, string | undefined> = {};

beforeEach(() => {
  vi.clearAllMocks();
  h.userCalls.length = 0;
  h.state.row = null;
  h.auth.mockResolvedValue(CLAIMING_SESSION);
  savedMfaEnv = {};
  for (const k of Object.keys(process.env)) {
    if (/mfa/i.test(k)) {
      savedMfaEnv[k] = process.env[k];
      delete process.env[k];
    }
  }
});

afterEach(() => {
  vi.unstubAllEnvs();
  for (const [k, v] of Object.entries(savedMfaEnv)) {
    if (v !== undefined) process.env[k] = v;
  }
});

describe('adminApi() — MFA is enforced by the DB row, before the handler', () => {
  it('POSITIVE CONTROL — an enrolled SUPER_ADMIN is admitted and audited', async () => {
    // Without this arm every refusal below would pass against a gate that
    // refuses EVERYONE.
    h.state.row = { ...SA_ROW, mfaEnabled: true };
    const { handler, run } = drive();
    const res = await run();
    expect(res.status).toBe(200);
    expect(handler).toHaveBeenCalledTimes(1);
    expect(adminAccessWrites()).toHaveLength(1);
  });

  it.each(['test', 'production'])(
    'NODE_ENV=%s, no MFA env var set: DB mfaEnabled=false -> 404, handler NEVER runs, no ADMIN_API_ACCESS row — even though the session claims mfaEnabled=true',
    async (nodeEnv) => {
      vi.stubEnv('NODE_ENV', nodeEnv);
      expect(Object.keys(process.env).filter((k) => /mfa/i.test(k))).toEqual([]);
      h.state.row = { ...SA_ROW, mfaEnabled: false };
      const { handler, run } = drive();
      const res = await run();

      expect(res.status, 'an un-enrolled SUPER_ADMIN reached past the gate').toBe(404);
      expect(await res.text()).toBe('Not Found');
      // ⚠️ ORDER IS THE PROPERTY. A refusal that runs after the handler returns
      // the same 404 — after the write has happened. The spy is what tells the
      // two apart.
      expect(handler, 'the handler ran for an un-enrolled SUPER_ADMIN').not.toHaveBeenCalled();
      expect(adminAccessWrites(), 'an access row was written for a refused request').toHaveLength(0);
    }
  );

  it('the flag comes from the DB row, not the token: session claims true, row says false -> 404', async () => {
    // Same input as above, stated as its own claim so a failure names the
    // stale-flag bug directly.
    h.state.row = { ...SA_ROW, mfaEnabled: false };
    const { handler, run } = drive();
    expect((await run()).status).toBe(404);
    expect(handler).not.toHaveBeenCalled();
  });

  it.each([
    ['admitted', true],
    ['refused', false],
  ])('the user row is read exactly once per request (%s)', async (_label, mfa) => {
    // Counts every `prisma.user.*` call, whatever it is spelled, so a second
    // read cannot hide behind `findFirst`.
    h.state.row = { ...SA_ROW, mfaEnabled: mfa };
    await drive().run();
    expect(h.userCalls).toEqual(['findUnique']);
  });
});

describe('app/admin/layout.tsx — the PAGE gate, driven', () => {
  const render = () => AdminLayout({ children: 'ADMIN-CHILDREN' as never });

  it('an un-enrolled SUPER_ADMIN is REDIRECTED to MFA enrolment, even though the session claims mfaEnabled=true', async () => {
    h.state.row = { ...SA_ROW, mfaEnabled: false };
    const err = await render().then(
      () => null,
      (e: unknown) => e
    );
    expect(err, 'the page gate rendered /admin for an un-enrolled SUPER_ADMIN').toBeInstanceOf(
      h.Redirect
    );
    expect(h.redirect).toHaveBeenCalledTimes(1);
    // ⚠️ ABSOLUTE, ON THE APP HOST. admin.quillmd.com's Caddy allowlist 404s
    // /settings/*, so a RELATIVE redirect from an admin-host render lands on a
    // bare "Not Found" and the operator is stranded. The target is built from
    // the one APP_URL constant, imported here and never re-derived.
    const target = (err as InstanceType<typeof h.Redirect>).url;
    expect(target, 'the enrolment redirect is not the app host, so it 404s on the admin host').toBe(
      `${APP_URL.replace(/\/+$/, '')}/settings/security/mfa?reason=super_admin_required`
    );
    expect(new URL(target).origin).toBe(new URL(APP_URL).origin);
    expect(h.notFound).not.toHaveBeenCalled();
  });

  it('POSITIVE CONTROL — an enrolled SUPER_ADMIN renders, with no redirect (an INVERTED gate reds here)', async () => {
    h.state.row = { ...SA_ROW, mfaEnabled: true };
    const out = await render();
    expect(out).toBeTruthy();
    expect(h.redirect).not.toHaveBeenCalled();
    expect(h.notFound).not.toHaveBeenCalled();
  });
});
