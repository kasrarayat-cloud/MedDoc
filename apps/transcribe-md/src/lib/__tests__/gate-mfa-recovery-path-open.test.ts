// @vitest-environment node
// ============================================================================
// THE MFA RECOVERY PATH IS NEVER BEHIND THE ADMIN GATE — DERIVED, NOT LISTED
// ----------------------------------------------------------------------------
// `adminApi()` refuses every SUPER_ADMIN without an enrolled factor. That is
// survivable only while enrolment stays reachable. If any route the enrolment
// surface calls were wrapped in `adminApi`, the lockout would be permanent.
//
// The previous arm (in gate-admin-api-mfa-parity.test.ts, retired by the
// commit that adds this file) checked a HAND LIST of three route files. The refutation round for PR #952 added a fourth route,
// `api/mfa/start`, wrapped in `adminApi`, pointed the enrolment panel at it,
// and stayed green: a hand list closes an instance, deriving closes the class.
//
// So the watched set is DERIVED from two sources and the arm fails closed on
// both:
//   1. every `fetch('/api/…')` target in the /settings/security/mfa surface
//   2. every route.ts under src/app/api/mfa/**
// Each route is IMPORTED with `adminApi` replaced by a spy; wrapping a handler
// calls `adminApi` at module load, however it is imported or aliased.
//
// The page itself is DRIVEN with an un-enrolled SUPER_ADMIN session and must
// render the enrolment panel: no redirect, no 404.
// ============================================================================

import { readdirSync, readFileSync, existsSync } from 'node:fs';
import path from 'node:path';

import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  adminApi: vi.fn((_key: string, handler: unknown) => handler),
  row: {} as Record<string, unknown>,
  auth: vi.fn(),
  redirect: vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`);
  }),
  notFound: vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND');
  }),
}));

vi.mock('@/lib/admin-api-gate', () => ({ adminApi: h.adminApi }));
vi.mock('@meddoc/db', () => ({
  default: {
    user: {
      findUnique: vi.fn(async () => ({ ...h.row })),
      update: vi.fn(async () => ({})),
    },
    userSession: { deleteMany: vi.fn(async () => ({ count: 0 })) },
    $transaction: vi.fn(async (ops: unknown) => ops),
  },
}));
vi.mock('@/lib/nextauth', () => ({ auth: h.auth }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
vi.mock('next/navigation', () => ({
  redirect: h.redirect,
  notFound: h.notFound,
  useRouter: () => ({ refresh: () => {} }),
}));

const APP = path.resolve(__dirname, '../../app');
const MFA_SURFACE = path.join(APP, 'settings/security/mfa');
const MFA_API = path.join(APP, 'api/mfa');

/** `/api/x/y` -> absolute path of its route.ts */
const routeFileFor = (apiPath: string) =>
  path.join(APP, apiPath.replace(/^\//, '').replace(/[?#].*$/, ''), 'route.ts');

function fetchTargets(): string[] {
  const out = new Set<string>();
  for (const f of readdirSync(MFA_SURFACE)) {
    if (!/\.(t|j)sx?$/.test(f)) continue;
    const src = readFileSync(path.join(MFA_SURFACE, f), 'utf8');
    for (const m of src.matchAll(/fetch\(\s*[`'"](\/api\/[^`'"?#]+)/g)) out.add(m[1]);
  }
  return [...out].sort();
}

function mfaRouteFiles(): string[] {
  return readdirSync(MFA_API, { recursive: true, encoding: 'utf8' })
    .filter((rel) => rel.replace(/\\/g, '/').endsWith('route.ts'))
    .map((rel) => path.join(MFA_API, rel))
    .sort();
}

const WATCHED = [...new Set([...fetchTargets().map(routeFileFor), ...mfaRouteFiles()])].sort();

describe('the MFA recovery path is not behind adminApi (derived set)', () => {
  it('CONTROL — the derived set is not vacuous and every fetch target resolves to a route file', () => {
    // A fetch target with no route file means the derivation broke or the
    // surface calls something this arm cannot see: fail closed, do not skip.
    expect(fetchTargets().length, 'no fetch targets found in the MFA surface').toBeGreaterThan(0);
    expect(mfaRouteFiles().length, 'no routes found under api/mfa').toBeGreaterThan(0);
    for (const t of fetchTargets()) {
      expect(existsSync(routeFileFor(t)), `${t} has no route.ts under src/app`).toBe(true);
    }
    expect(WATCHED.map((f) => path.relative(APP, f))).toContain('api/mfa/enroll/route.ts');
  });

  // ⚠️ IMPORTED ONCE, UP FRONT, WITH A REAL TIMEOUT. The first cold import pays
  // for bcryptjs + otplib + qrcode and measured >5s — vitest's default — so a
  // per-arm import timed out on the FIRST file only and read as a finding. The
  // per-module delta is recorded here, sequentially, so it is still exact.
  const adminApiCallsAtLoad = new Map<string, number>();
  beforeAll(async () => {
    for (const file of WATCHED) {
      h.adminApi.mockClear();
      await import(/* @vite-ignore */ file);
      adminApiCallsAtLoad.set(file, h.adminApi.mock.calls.length);
    }
  }, 60_000);

  it.each(WATCHED.map((f) => [path.relative(APP, f), f]))(
    '%s does not call adminApi at module load',
    (rel, file) => {
      expect(adminApiCallsAtLoad.has(file), `${rel} was never imported`).toBe(true);
      expect(
        adminApiCallsAtLoad.get(file),
        `${rel} wraps a handler in adminApi — an un-enrolled SUPER_ADMIN could never enrol, and the lockout is permanent`
      ).toBe(0);
    }
  );
});

describe('/settings/security/mfa is not admin-gated — driven', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(h.row, {
      id: 'sa-1',
      email: 'sa@example.test',
      role: 'DOCTOR',
      products: ['SUPER_ADMIN'],
      mfaEnabled: false,
      mfaVerifiedAt: null,
    });
    h.auth.mockResolvedValue({ user: { id: 'sa-1', email: 'sa@example.test' } });
  });

  it('an un-enrolled SUPER_ADMIN gets the ENROLMENT panel, with no redirect and no 404', async () => {
    const { default: Page } = await import('../../app/settings/security/mfa/page');
    const { MfaEnrollmentPanel } = await import(
      '../../app/settings/security/mfa/mfa-enrollment-panel'
    );
    const tree = await Page({ searchParams: Promise.resolve({ reason: 'super_admin_required' }) });
    expect(h.redirect).not.toHaveBeenCalled();
    expect(h.notFound).not.toHaveBeenCalled();

    const seen: unknown[] = [];
    const walk = (n: unknown): void => {
      if (Array.isArray(n)) return n.forEach(walk);
      if (n && typeof n === 'object' && 'type' in n) {
        seen.push((n as { type: unknown }).type);
        walk((n as { props?: { children?: unknown } }).props?.children);
      }
    };
    walk(tree);
    expect(seen, 'the enrolment panel is not rendered for an un-enrolled SUPER_ADMIN').toContain(
      MfaEnrollmentPanel
    );
  });

  it('no layout on the path to /settings/security/mfa carries an admin gate', () => {
    // Next composes every layout.tsx between app/ and the leaf. Any of them
    // gating on SUPER_ADMIN or MFA would close the path before the page runs.
    const chain = ['', 'settings', 'settings/security', 'settings/security/mfa'];
    for (const seg of chain) {
      for (const name of ['layout.tsx', 'layout.ts', 'template.tsx']) {
        const f = path.join(APP, seg, name);
        if (!existsSync(f)) continue;
        const src = readFileSync(f, 'utf8');
        expect(src, `${path.relative(APP, f)} gates the MFA recovery path`).not.toMatch(
          /SUPER_ADMIN|admin-api-gate|mfaEnabled/
        );
      }
    }
  });
});
