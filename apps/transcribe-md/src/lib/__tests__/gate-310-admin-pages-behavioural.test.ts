// @vitest-environment node
// ============================================================================
// RULING #310 — EVERY /admin PAGE GATES ITSELF, BEFORE ANY DATA CALL.
// ----------------------------------------------------------------------------
// The defect: Next 16 renders ONLY the page on an RSC subtree refetch, so
// `app/admin/layout.tsx` — once the sole gate — never ran, and an
// unauthenticated `RSC: 1` request to /admin/hipaa returned the hipaaFinding
// rows with a 200 and no audit row (reproduced on the shipped QA image).
//
// These arms DRIVE each page component the way an RSC refetch does — the
// page function alone, no layout — and assert the page itself refuses, and
// that it refuses BEFORE any data function is invoked (every data function is
// a recording spy). Then they drive layout + page together, the way a full
// render does, and assert ONE audit row and ONE verdict read (React cache()).
//
// React's client build ships `cache` as a pass-through (no request scope
// outside an RSC render), so this file substitutes a per-request memo —
// `beginRequest()` opens a fresh scope, exactly like one server request.
// ============================================================================
import { readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { isValidElement } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => {
  const calls: string[] = [];
  const spy = (name: string, value: unknown) =>
    vi.fn(async () => {
      calls.push(name);
      return value;
    });
  return {
    calls,
    spy,
    memo: new Map<unknown, unknown>(),
    auth: vi.fn(),
    userFindUnique: vi.fn(),
    sessionFindUnique: vi.fn(),
    logAudit: vi.fn(),
  };
});

vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    // One memo per simulated request (see beginRequest()).
    cache: <A extends unknown[], R>(fn: (...a: A) => R) => {
      const wrapped = (...args: A): R => {
        if (!h.memo.has(wrapped)) h.memo.set(wrapped, fn(...args));
        return h.memo.get(wrapped) as R;
      };
      return wrapped;
    },
  };
});
vi.mock('server-only', () => ({}));
vi.mock('@/lib/nextauth', () => ({ auth: h.auth }));
vi.mock('@meddoc/db', () => ({
  default: {
    user: { findUnique: h.userFindUnique },
    userSession: { findUnique: h.sessionFindUnique },
  },
}));
vi.mock('@/lib/audit', () => ({ logAudit: h.logAudit }));
vi.mock('next/headers', () => ({
  headers: async () => new Headers({ 'next-url': '/admin/some-page?x=1' }),
}));

// ── every data entry point a page can reach, as a recording spy ────────────
vi.mock('@/app/admin/_lib/dashboard-data', () => ({
  getSystemHealth: h.spy('getSystemHealth', {}),
  getRecentActivity: h.spy('getRecentActivity', []),
  getThreats: h.spy('getThreats', []),
  getResolvedThreats: h.spy('getResolvedThreats', []),
  getTimeline: h.spy('getTimeline', []),
  getPipelineMetrics: h.spy('getPipelineMetrics', {}),
  getHipaaState: h.spy('getHipaaState', {}),
}));
vi.mock('@/app/admin/hipaa/_lib/hipaa-data', () => ({
  getAllFindings: h.spy('getAllFindings', []),
}));
vi.mock('@/app/admin/threats/_lib/threats-data', () => ({
  getThreatsPageData: h.spy('getThreatsPageData', { active: [], resolved: [] }),
}));
vi.mock('@/app/admin/usage/_lib/usage-data', () => ({
  fetchUsageSummary: h.spy('fetchUsageSummary', {}),
  fetchTimeline: h.spy('fetchTimeline', {}),
  fetchTopUsers: h.spy('fetchTopUsers', {}),
  fetchAnomalies: h.spy('fetchAnomalies', []),
}));
vi.mock('@/app/admin/users/_lib/users-data', () => ({
  fetchUserListPage: h.spy('fetchUserListPage', { rows: [] }),
  fetchUserStats: h.spy('fetchUserStats', {}),
}));
vi.mock('@/lib/queue', () => {
  const q = (name: string) => ({
    name,
    getJobCounts: async () => {
      h.calls.push(`${name}.getJobCounts`);
      return {};
    },
    getJobs: async () => {
      h.calls.push(`${name}.getJobs`);
      return [];
    },
  });
  return {
    QUEUE_NAME: 'transcribe-md',
    CLEANUP_QUEUE_NAME: 'transcribe-md-cleanup',
    DLQ_QUEUE_NAME: 'dlq-permanent-failures',
    getTranscribeMdQueue: () => {
      h.calls.push('getTranscribeMdQueue');
      return q('transcribe-md');
    },
    getCleanupQueue: () => {
      h.calls.push('getCleanupQueue');
      return q('transcribe-md-cleanup');
    },
    getDlqQueue: () => {
      h.calls.push('getDlqQueue');
      return q('dlq-permanent-failures');
    },
  };
});

// Client islands: stubs — the page's server logic is what is under test.
vi.mock('@/app/admin/_components/AdminOverview.client', () => ({ default: () => null }));
vi.mock('@/app/admin/hipaa/_components/AdminHipaa.client', () => ({ default: () => null }));
vi.mock('@/app/admin/threats/_components/AdminThreats.client', () => ({ default: () => null }));
vi.mock('@/app/admin/usage/_components/AdminUsage.client', () => ({ default: () => null }));
vi.mock('@/app/admin/users/_components/AdminUsers.client', () => ({ default: () => null }));

// ── fixtures ────────────────────────────────────────────────────────────────
const NOT_FOUND = 'NEXT_HTTP_ERROR_FALLBACK;404';
// Byte-for-byte the redirect the layout issued on main.
const MFA_REDIRECT =
  'NEXT_REDIRECT;replace;/settings/security/mfa?reason=super_admin_required;307;';

const ADMIN_ROW = { products: ['TRANSCRIBE_MD', 'SUPER_ADMIN'], isActive: true, mfaEnabled: true };
const HOUR = 60 * 60 * 1000;

type Caller =
  | 'anonymous'
  | 'non-admin'
  | 'inactive-admin'
  | 'unenrolled-admin'
  | 'stale-admin'
  // Un-enrolled AND stale: pins the ORDER of the two checks. On main the
  // layout sent the MFA redirect before it ever read session freshness, so
  // this caller must get the redirect, not the 404 a swapped order gives.
  | 'unenrolled-stale-admin'
  | 'no-session-id-admin'
  | 'admin';

function beginRequest(caller: Caller) {
  h.memo.clear();
  h.calls.length = 0;
  h.auth.mockReset();
  h.userFindUnique.mockReset();
  h.sessionFindUnique.mockReset();
  h.logAudit.mockReset();
  h.sessionFindUnique.mockResolvedValue({ createdAt: new Date(Date.now() - HOUR) });
  if (caller === 'anonymous') {
    h.auth.mockResolvedValue(null);
    return;
  }
  h.auth.mockResolvedValue({
    user: {
      id: 'u-1',
      email: 'ops@example.test',
      sessionId: caller === 'no-session-id-admin' ? undefined : 'sess-1',
    },
  });
  const row =
    caller === 'non-admin'
      ? { ...ADMIN_ROW, products: ['TRANSCRIBE_MD'] }
      : caller === 'inactive-admin'
        ? { ...ADMIN_ROW, isActive: false }
        : caller === 'unenrolled-admin' || caller === 'unenrolled-stale-admin'
          ? { ...ADMIN_ROW, mfaEnabled: false }
          : ADMIN_ROW;
  h.userFindUnique.mockResolvedValue(row);
  if (caller === 'stale-admin' || caller === 'unenrolled-stale-admin') {
    h.sessionFindUnique.mockResolvedValue({ createdAt: new Date(Date.now() - 13 * HOUR) });
  }
}

async function outcome(run: () => unknown) {
  try {
    const value = await run();
    return { threw: false as const, value };
  } catch (e) {
    return { threw: true as const, digest: (e as { digest?: string }).digest, error: e };
  }
}

// ── the universe: every admin page.tsx, and how to drive it ────────────────
interface PageCase {
  file: string;
  load: () => Promise<{ default: (props: never) => unknown }>;
  props: () => unknown;
  data: string[];
}
const PAGES: PageCase[] = [
  {
    file: 'page.tsx',
    load: () => import('@/app/admin/page') as never,
    props: () => ({}),
    data: ['getSystemHealth', 'getRecentActivity', 'getThreats', 'getTimeline', 'getPipelineMetrics', 'getHipaaState'],
  },
  { file: 'hipaa/page.tsx', load: () => import('@/app/admin/hipaa/page') as never, props: () => ({}), data: ['getAllFindings'] },
  { file: 'threats/page.tsx', load: () => import('@/app/admin/threats/page') as never, props: () => ({}), data: ['getThreatsPageData'] },
  {
    file: 'usage/page.tsx',
    load: () => import('@/app/admin/usage/page') as never,
    props: () => ({}),
    data: ['fetchUsageSummary', 'fetchTimeline', 'fetchTopUsers', 'fetchAnomalies'],
  },
  {
    file: 'users/page.tsx',
    load: () => import('@/app/admin/users/page') as never,
    props: () => ({ searchParams: Promise.resolve({}) }),
    data: ['fetchUserListPage', 'fetchUserStats'],
  },
  {
    file: 'queues/page.tsx',
    load: () => import('@/app/admin/queues/page') as never,
    props: () => ({}),
    data: ['getTranscribeMdQueue', 'getCleanupQueue', 'getDlqQueue'],
  },
];

const ADMIN_DIR = join(__dirname, '..', '..', 'app', 'admin');
function walkPages(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walkPages(p));
    else if (name === 'page.tsx' || name === 'page.ts' || name === 'page.jsx' || name === 'page.js') {
      out.push(relative(ADMIN_DIR, p));
    }
  }
  return out.sort();
}

describe('ruling #310 — the table covers every /admin page on disk', () => {
  it('no admin page escapes these arms (a new page must be added here)', () => {
    const onDisk = walkPages(ADMIN_DIR);
    expect(onDisk.length, 'walker found no pages — a vacuous universe').toBeGreaterThanOrEqual(6);
    expect(PAGES.map((p) => p.file).sort()).toEqual(onDisk);
  });
});

describe.each(PAGES)('ruling #310 — /admin/$file refuses on its own (RSC refetch: page only)', (pc) => {
  const refusals: Array<[Caller, string]> = [
    ['anonymous', NOT_FOUND],
    ['non-admin', NOT_FOUND],
    ['inactive-admin', NOT_FOUND],
    ['stale-admin', NOT_FOUND],
    ['no-session-id-admin', NOT_FOUND],
    ['unenrolled-admin', MFA_REDIRECT],
    // MFA before freshness, byte-identical to main's layout order.
    ['unenrolled-stale-admin', MFA_REDIRECT],
  ];

  it.each(refusals)('%s → %s, and NO data function ran', async (caller, digest) => {
    const { default: Page } = await pc.load();
    beginRequest(caller);
    const r = await outcome(() => Page(pc.props() as never));
    expect(r.threw, `${pc.file} rendered for ${caller}`).toBe(true);
    expect(r.threw && r.digest).toBe(digest);
    expect(h.calls, `${pc.file} invoked data before refusing ${caller}`).toEqual([]);
    expect(h.logAudit).not.toHaveBeenCalled();
    if (caller === 'anonymous') expect(h.userFindUnique).not.toHaveBeenCalled();
  });

  it('a valid SUPER_ADMIN renders, its data runs, and exactly ONE access audit is written', async () => {
    const { default: Page } = await pc.load();
    beginRequest('admin');
    const r = await outcome(() => Page(pc.props() as never));
    expect(r.threw, String(r.threw && r.error)).toBe(false);
    expect(isValidElement(r.threw ? null : r.value)).toBe(true);
    for (const d of pc.data) expect(h.calls, `${d} did not run`).toContain(d);
    expect(h.logAudit).toHaveBeenCalledTimes(1);
    expect(h.logAudit).toHaveBeenCalledWith({
      action: 'ADMIN_DASHBOARD_ACCESS',
      targetType: 'AdminDashboard',
      targetId: '/admin/some-page',
      metadata: { path: '/admin/some-page' },
    });
  });
});

describe('ruling #310 — the layout calls the SAME verdict, and a full render audits ONCE', () => {
  it('layout alone: anonymous → 404, un-enrolled SUPER_ADMIN → the MFA redirect', async () => {
    const { default: Layout } = await import('@/app/admin/layout');
    beginRequest('anonymous');
    expect((await outcome(() => Layout({ children: null }))) ).toMatchObject({ threw: true, digest: NOT_FOUND });
    beginRequest('non-admin');
    expect(await outcome(() => Layout({ children: null }))).toMatchObject({ threw: true, digest: NOT_FOUND });
    beginRequest('stale-admin');
    expect(await outcome(() => Layout({ children: null }))).toMatchObject({ threw: true, digest: NOT_FOUND });
    beginRequest('unenrolled-admin');
    expect(await outcome(() => Layout({ children: null }))).toMatchObject({ threw: true, digest: MFA_REDIRECT });
    expect(h.logAudit).not.toHaveBeenCalled();
  });

  it('layout alone: un-enrolled AND stale SUPER_ADMIN → the MFA redirect (MFA is checked before freshness, as on main)', async () => {
    const { default: Layout } = await import('@/app/admin/layout');
    beginRequest('unenrolled-stale-admin');
    expect(await outcome(() => Layout({ children: null }))).toMatchObject({ threw: true, digest: MFA_REDIRECT });
    expect(h.logAudit).not.toHaveBeenCalled();
  });

  it('layout for a valid SUPER_ADMIN keeps its chrome byte-identical', async () => {
    const { default: Layout } = await import('@/app/admin/layout');
    beginRequest('admin');
    const el = (await Layout({ children: 'CHILD' })) as { props: { className: string; children: { props: { className: string; children: unknown } } } };
    expect(el.props.className).toBe('min-h-screen bg-linear-bg text-linear-text');
    expect(el.props.children.props.className).toBe('min-h-screen');
    expect(el.props.children.props.children).toBe('CHILD');
    expect(h.logAudit).toHaveBeenCalledTimes(1);
  });

  it.each(PAGES)('full render of /admin/$file (layout + page, one request) → one verdict read, ONE audit', async (pc) => {
    const { default: Layout } = await import('@/app/admin/layout');
    const { default: Page } = await pc.load();
    beginRequest('admin');
    // Next renders layout and page in the same request scope, possibly
    // concurrently; drive both at once.
    await Promise.all([Layout({ children: null }), Page(pc.props() as never)]);
    expect(h.logAudit).toHaveBeenCalledTimes(1);
    expect(h.userFindUnique).toHaveBeenCalledTimes(1);
    expect(h.sessionFindUnique).toHaveBeenCalledTimes(1);
  });

  it('the pages hand the verified session to their UI (users: id + email; overview: email)', async () => {
    beginRequest('admin');
    const { default: Users } = await import('@/app/admin/users/page');
    const u = (await Users({ searchParams: Promise.resolve({}) } as never)) as { props: Record<string, unknown> };
    expect(u.props.currentUserId).toBe('u-1');
    expect(u.props.currentUserEmail).toBe('ops@example.test');
    beginRequest('admin');
    const { default: Overview } = await import('@/app/admin/page');
    const o = (await Overview()) as { props: Record<string, unknown> };
    expect(o.props.userEmail).toBe('ops@example.test');
  });
});
