// @vitest-environment node
// ============================================================================
// RULING #310 — EVERY /admin DATA FUNCTION GATES ITSELF, BEFORE ANY I/O.
// ----------------------------------------------------------------------------
// The page gate closes the RSC-refetch door; this closes the next one. A data
// helper that trusts its caller is one new page (or one new import) away from
// the same leak, so each exported async function in app/admin/**/_lib calls
// assertSuperAdminCaller() FIRST. These arms drive the REAL helpers against a
// recording prisma (every property path + call is logged) and a recording
// fetch, and assert: a refused caller gets AdminAccessDeniedError and NOTHING
// was read — not a row, not a health probe.
//
// They also drive the two adminApi routes that import dashboard-data
// (GET /api/admin/threats and /threats/history) — they run as a SUPER_ADMIN,
// so the helper's own assertion passes and the route answers 200 — and pin
// that a helper refusal inside adminApi is its usual silent 404, never a 500.
//
// No React render here, so `cache()` is the client build's pass-through: every
// assertion re-reads fresh, which is exactly how a route handler behaves.
// ============================================================================
import { NextRequest } from 'next/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => {
  const calls: string[] = [];
  const state = {
    userRow: null as unknown,
    sessionRow: null as unknown,
  };
  const respond = (path: string): Promise<unknown> => {
    if (path === 'user.findUnique') return Promise.resolve(state.userRow);
    if (path === 'userSession.findUnique') return Promise.resolve(state.sessionRow);
    if (path.endsWith('.count')) return Promise.resolve(0);
    return Promise.resolve([]);
  };
  // A prisma stand-in that records EVERY call, whatever the shape
  // (`prisma.x.y()`, `(prisma as any).x.y()`, tagged `$queryRaw`).
  const deep = (path: string[]): unknown =>
    new Proxy(
      (..._args: unknown[]) => {
        const p = path.join('.');
        calls.push(p);
        return respond(p);
      },
      {
        get(_t, key) {
          if (key === 'then') return undefined;
          return deep([...path, String(key)]);
        },
      },
    );
  return { calls, state, prisma: deep([]), auth: vi.fn(), logAudit: vi.fn(), fetch: vi.fn() };
});

vi.mock('server-only', () => ({}));
vi.mock('@meddoc/db', () => ({ default: h.prisma }));
vi.mock('@/lib/nextauth', () => ({ auth: h.auth }));
vi.mock('@/lib/audit', () => ({ logAudit: h.logAudit }));
vi.mock('@/lib/redis', () => ({ isRedisReady: () => false, getRedis: () => null }));
vi.mock('next/headers', () => ({ headers: async () => new Headers() }));

import { AdminAccessDeniedError } from '@/lib/admin-access-denied';
import * as dashboard from '@/app/admin/_lib/dashboard-data';
import * as usage from '@/app/admin/usage/_lib/usage-data';
import * as hipaa from '@/app/admin/hipaa/_lib/hipaa-data';
import * as threats from '@/app/admin/threats/_lib/threats-data';
import * as users from '@/app/admin/users/_lib/users-data';
import { GET as threatsGET } from '@/app/api/admin/threats/route';
import { GET as historyGET } from '@/app/api/admin/threats/history/route';

const HOUR = 60 * 60 * 1000;
const ADMIN_ROW = { products: ['TRANSCRIBE_MD', 'SUPER_ADMIN'], isActive: true, mfaEnabled: true };
const GATE_READS = new Set(['user.findUnique', 'userSession.findUnique']);

type Caller = 'anonymous' | 'non-admin' | 'inactive-admin' | 'unenrolled-admin' | 'stale-admin' | 'admin';

function as(caller: Caller) {
  h.calls.length = 0;
  h.auth.mockReset();
  h.logAudit.mockReset();
  h.fetch.mockReset();
  h.fetch.mockResolvedValue(new Response('', { status: 200 }));
  h.state.sessionRow = { createdAt: new Date(Date.now() - HOUR) };
  if (caller === 'anonymous') {
    h.auth.mockResolvedValue(null);
    h.state.userRow = null;
    return;
  }
  h.auth.mockResolvedValue({ user: { id: 'u-1', email: 'ops@example.test', sessionId: 'sess-1' } });
  h.state.userRow =
    caller === 'non-admin'
      ? { ...ADMIN_ROW, products: ['TRANSCRIBE_MD'] }
      : caller === 'inactive-admin'
        ? { ...ADMIN_ROW, isActive: false }
        : caller === 'unenrolled-admin'
          ? { ...ADMIN_ROW, mfaEnabled: false }
          : ADMIN_ROW;
  if (caller === 'stale-admin') h.state.sessionRow = { createdAt: new Date(Date.now() - 13 * HOUR) };
}

beforeEach(() => {
  vi.stubGlobal('fetch', h.fetch);
});

// ── the universe: every exported async function of every admin data module ─
const MODULES: Record<string, Record<string, unknown>> = {
  'dashboard-data': dashboard,
  'usage-data': usage,
  'hipaa-data': hipaa,
  'threats-data': threats,
  'users-data': users,
};
const ARGS: Record<string, unknown[]> = {
  getRecentActivity: [30],
  getResolvedThreats: ['7d'],
  fetchUsageSummary: ['month'],
  fetchTimeline: ['month'],
  fetchTopUsers: ['month', 10],
  fetchUserListPage: [{ search: '', status: 'all', role: 'all', product: 'all', page: 1 }],
};
const HELPERS: Array<[string, (...a: unknown[]) => Promise<unknown>]> = [];
for (const [mod, ns] of Object.entries(MODULES)) {
  for (const [name, v] of Object.entries(ns)) {
    if (typeof v === 'function' && v.constructor.name === 'AsyncFunction') {
      HELPERS.push([`${mod}.${name}`, v as (...a: unknown[]) => Promise<unknown>]);
    }
  }
}

describe('ruling #310 — the helper universe is derived, not listed', () => {
  it('finds every exported async data function (floor guards a vacuous walk)', () => {
    expect(HELPERS.length).toBeGreaterThanOrEqual(15);
  });
});

describe.each(HELPERS)('ruling #310 — %s gates itself first', (label, fn) => {
  const args = ARGS[label.split('.')[1]] ?? [];

  it('anonymous → AdminAccessDeniedError, and NOT ONE read (no prisma, no fetch)', async () => {
    as('anonymous');
    await expect(fn(...args)).rejects.toBeInstanceOf(AdminAccessDeniedError);
    expect(h.calls).toEqual([]);
    expect(h.fetch).not.toHaveBeenCalled();
  });

  it.each(['non-admin', 'inactive-admin', 'unenrolled-admin', 'stale-admin'] as const)(
    '%s → AdminAccessDeniedError, and only the gate’s own reads happened',
    async (caller) => {
      as(caller);
      const err = await fn(...args).then(() => null, (e: unknown) => e);
      expect(err).toBeInstanceOf(AdminAccessDeniedError);
      expect(h.calls.filter((c) => !GATE_READS.has(c)), `${label} read data for ${caller}`).toEqual([]);
      expect(h.fetch).not.toHaveBeenCalled();
    },
  );

  it('valid SUPER_ADMIN → the gate reads come FIRST, then the helper reads its data', async () => {
    as('admin');
    await fn(...args).catch(() => undefined); // shape errors from the stand-in are irrelevant here
    expect(h.calls[0]).toBe('user.findUnique');
    const data = h.calls.filter((c) => !GATE_READS.has(c));
    expect(data.length + h.fetch.mock.calls.length, `${label} never reached its data`).toBeGreaterThan(0);
    const firstData = h.calls.findIndex((c) => !GATE_READS.has(c));
    if (firstData >= 0) expect(h.calls.slice(0, firstData)).toContain('userSession.findUnique');
  });
});

describe('ruling #310 — the adminApi routes that import dashboard-data still work', () => {
  it('GET /api/admin/threats as a SUPER_ADMIN → 200 with the detector output', async () => {
    as('admin');
    const res = await threatsGET(new NextRequest('http://localhost/api/admin/threats'));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ threats: [] });
    expect(h.logAudit).toHaveBeenCalledWith(expect.objectContaining({ action: 'ADMIN_API_ACCESS' }));
  });

  it('GET /api/admin/threats/history?window=30d as a SUPER_ADMIN → 200', async () => {
    as('admin');
    const res = await historyGET(new NextRequest('http://localhost/api/admin/threats/history?window=30d'));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ window: '30d', threats: [] });
  });

  it('anonymous → 404 from adminApi itself, and no detector query ran', async () => {
    as('anonymous');
    const res = await threatsGET(new NextRequest('http://localhost/api/admin/threats'));
    expect(res.status).toBe(404);
    expect(h.calls.filter((c) => !GATE_READS.has(c))).toEqual([]);
  });

  it('a helper refusal INSIDE adminApi is the silent 404, never a 500 (un-enrolled SUPER_ADMIN)', async () => {
    // adminApi on main does not check MFA; the helper's own verdict does.
    as('unenrolled-admin');
    for (const [get, url] of [
      [threatsGET, 'http://localhost/api/admin/threats'],
      [historyGET, 'http://localhost/api/admin/threats/history'],
    ] as const) {
      h.calls.length = 0;
      const res = await get(new NextRequest(url));
      expect(res.status).toBe(404);
      expect(await res.text()).toBe('Not Found');
      expect(h.calls.filter((c) => !GATE_READS.has(c))).toEqual([]);
    }
  });
});
