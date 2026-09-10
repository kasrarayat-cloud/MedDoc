// ============================================================================
// ADMIN-2 (#196) — lib/practice-host.ts, the host → practice resolver.
// ----------------------------------------------------------------------------
// Every arm here was made to RED on the mutation it guards before it was
// believed; the table is in the ADMIN-2 RELAY note.
// ============================================================================
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { beforeEach, describe, expect, it, vi } from 'vitest';

const findFirst = vi.fn();
const headerBag = new Map<string, string>();
const headersFn = vi.fn(async () => headerBag);

vi.mock('@meddoc/db', () => ({
  __esModule: true,
  default: { practice: { findFirst: (...a: unknown[]) => findFirst(...a) } },
}));
vi.mock('next/headers', () => ({ headers: () => headersFn() }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
vi.mock('@/lib/nextauth', () => ({ auth: vi.fn() }));

import { SessionUnverifiableError } from '@meddoc/auth';

import {
  NEUTRAL_LABELS,
  PRACTICE_HOST_ADMITS,
  classifyHost,
  hostRefusalFor,
  loginHostRefusal,
  normalizeHost,
  practiceHostRoutingEnabled,
  requestHost,
  resolvePracticeByHost,
} from '../practice-host';

beforeEach(() => {
  vi.clearAllMocks();
  headerBag.clear();
});

describe('normalizeHost', () => {
  it.each([
    ['app.quillmd.com', 'app.quillmd.com'],
    ['APP.QuillMD.com', 'app.quillmd.com'],
    ['app.quillmd.com:443', 'app.quillmd.com'],
    ['northside.quillmd.com.', 'northside.quillmd.com'],
    ['localhost:3011', 'localhost'],
    ['[::1]:3011', '[::1]'],
    ['', null],
    ['   ', null],
    [null, null],
    [undefined, null],
  ])('%j → %j', (raw, want) => {
    expect(normalizeHost(raw as string | null | undefined)).toBe(want);
  });
});

describe('classifyHost', () => {
  it.each(['quillmd.com', 'www.quillmd.com', 'app.quillmd.com', 'admin.quillmd.com', 'localhost', '127.0.0.1', '127.0.0.9', '[::1]'])(
    'NEUTRAL: %s serves every account, as today',
    (h) => {
      expect(classifyHost(h)).toEqual({ kind: 'neutral', host: h });
    },
  );

  it('PRACTICE: one valid, unreserved label under the apex', () => {
    expect(classifyHost('northside.quillmd.com')).toEqual({
      kind: 'practice',
      host: 'northside.quillmd.com',
      label: 'northside',
    });
  });

  it.each([
    [null, 'no_host'],
    ['evil.com', 'foreign_host'],
    ['quillmd.com.evil.com', 'foreign_host'],
    ['xquillmd.com', 'foreign_host'],
    ['10.0.0.5', 'foreign_host'],
    ['a.b.quillmd.com', 'nested_label'],
    ['solo-k3j9x2-lx9q.quillmd.com', 'machine_slug'],
    ['api.quillmd.com', 'reserved_label'],
    ['staging.quillmd.com', 'reserved_label'],
    ['ab.quillmd.com', 'invalid_label'],
    ['-bad-.quillmd.com', 'invalid_label'],
    ['.quillmd.com', 'invalid_label'],
  ])('REFUSED: %j → %s', (h, reason) => {
    const c = classifyHost(h as string | null);
    expect(c.kind).toBe('refused');
    if (c.kind === 'refused') expect(c.reason).toBe(reason);
  });

  it('⚠️ solo-* is REFUSED even though the slug rule accepts it — machine slugs are unroutable', async () => {
    // Control: the write side accepts the shape, so the refusal is this file's.
    const { slugRefusal } = await import('../practice-write');
    expect(slugRefusal('solo-k3j9x2-lx9q')).toBeNull();
    expect(classifyHost('solo-k3j9x2-lx9q.quillmd.com')).toMatchObject({ kind: 'refused', reason: 'machine_slug' });
  });

  it("⚠️ the reserved set is practice-write.ts's — DERIVED from that file, every member refused here", () => {
    // Parsed from the write path's own source, so a local copy in
    // practice-host.ts that drops a name reds here rather than silently
    // routing a practice onto a platform name.
    const src = readFileSync(join(__dirname, '..', 'practice-write.ts'), 'utf8');
    const m = src.match(/const RESERVED_SLUGS = new Set\(\[([\s\S]*?)\]\)/);
    expect(m, 'could not find RESERVED_SLUGS in practice-write.ts — this arm measures nothing').not.toBeNull();
    const names = [...m![1]!.matchAll(/'([^']+)'/g)].map((x) => x[1]!);
    expect(names.length, 'positive control: the set parsed').toBeGreaterThan(20);
    // Two-letter members (`ns`, `mx`, `qa`) fail the 3–63 format rule first, so
    // they refuse as invalid_label; every member that PASSES the format rule
    // must refuse as reserved_label.
    const FORMAT = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$/;
    let reservedChecked = 0;
    for (const n of names) {
      const c = classifyHost(`${n}.quillmd.com`);
      if (NEUTRAL_LABELS.includes(n)) {
        expect(c.kind, `${n} is a neutral label`).toBe('neutral');
      } else {
        expect(c, `reserved name "${n}" was not refused as a host`).toMatchObject({
          kind: 'refused',
          reason: FORMAT.test(n) ? 'reserved_label' : 'invalid_label',
        });
        if (FORMAT.test(n)) reservedChecked += 1;
      }
    }
    expect(reservedChecked, 'positive control: reserved_label was exercised').toBeGreaterThan(20);
  });
});

describe('requestHost — Host ONLY', () => {
  it('⚠️ a client-sent X-Forwarded-Host is IGNORED', async () => {
    headerBag.set('host', 'app.quillmd.com');
    headerBag.set('x-forwarded-host', 'admin.quillmd.com');
    expect(await requestHost()).toBe('app.quillmd.com');
  });

  it('⚠️ and X-Forwarded-Host alone does not become the host', async () => {
    headerBag.set('x-forwarded-host', 'northside.quillmd.com');
    expect(await requestHost()).toBeNull();
  });
});

describe('resolvePracticeByHost', () => {
  it('a practice host resolves to an ACTIVE practice by exact slug', async () => {
    findFirst.mockResolvedValue({ id: 'prac_B' });
    const r = await resolvePracticeByHost('northside.quillmd.com');
    expect(r).toEqual({ kind: 'practice', host: 'northside.quillmd.com', label: 'northside', practiceId: 'prac_B' });
    expect(findFirst).toHaveBeenCalledTimes(1);
    const where = (findFirst.mock.calls[0]![0] as { where: Record<string, unknown> }).where;
    expect(where, 'an archived practice must not answer on its host').toEqual({ slug: 'northside', isActive: true });
    expect(PRACTICE_HOST_ADMITS).toEqual({ isActive: true });
  });

  it('no active practice carries the slug → refused unknown_practice (NOT neutral)', async () => {
    findFirst.mockResolvedValue(null);
    expect(await resolvePracticeByHost('northside.quillmd.com')).toMatchObject({
      kind: 'refused',
      reason: 'unknown_practice',
    });
  });

  it('⚠️ a lookup that cannot answer throws SessionUnverifiableError — "cannot tell" is not "no"', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    findFirst.mockRejectedValue(new Error('pool timeout'));
    await expect(resolvePracticeByHost('northside.quillmd.com')).rejects.toBeInstanceOf(SessionUnverifiableError);
    spy.mockRestore();
  });

  it('neutral and refused hosts never query the database', async () => {
    await resolvePracticeByHost('app.quillmd.com');
    await resolvePracticeByHost('solo-x1-y2.quillmd.com');
    await resolvePracticeByHost(null);
    expect(findFirst).not.toHaveBeenCalled();
  });
});

describe('hostRefusalFor / loginHostRefusal — the one reconcile predicate', () => {
  it('member of the host practice → admitted', async () => {
    findFirst.mockResolvedValue({ id: 'prac_B' });
    expect(await hostRefusalFor('prac_B', 'northside.quillmd.com')).toBeNull();
  });

  it('member of ANOTHER practice → practice_mismatch', async () => {
    findFirst.mockResolvedValue({ id: 'prac_B' });
    expect(await hostRefusalFor('prac_A', 'northside.quillmd.com')).toMatchObject({ reason: 'practice_mismatch' });
  });

  it('neutral host → admitted whatever the practice', async () => {
    expect(await hostRefusalFor('prac_A', 'app.quillmd.com')).toBeNull();
  });

  it('sign-in: a lookup that throws is refused as host_unverifiable, never admitted', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    headerBag.set('host', 'northside.quillmd.com');
    findFirst.mockRejectedValue(new Error('pool timeout'));
    expect(await loginHostRefusal('prac_B')).toEqual({ reason: 'host_unverifiable', host: null });
    spy.mockRestore();
  });
});

describe('the flag', () => {
  it.each([
    [undefined, false],
    ['', false],
    ['false', false],
    ['1', false],
    ['TRUE', false],
    ['true', true],
  ])('PRACTICE_HOST_ROUTING=%j → %s', (v, want) => {
    const prev = process.env.PRACTICE_HOST_ROUTING;
    if (v === undefined) delete process.env.PRACTICE_HOST_ROUTING;
    else process.env.PRACTICE_HOST_ROUTING = v;
    try {
      expect(practiceHostRoutingEnabled()).toBe(want);
    } finally {
      if (prev === undefined) delete process.env.PRACTICE_HOST_ROUTING;
      else process.env.PRACTICE_HOST_ROUTING = prev;
    }
  });
});
