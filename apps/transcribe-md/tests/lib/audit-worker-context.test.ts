// ============================================================================
// audit-worker-context.test.ts — P3 closure guards (2026-05-13)
// ----------------------------------------------------------------------------
// Cross-input-mode audit Finding 4: worker-context logAudit calls were
// silently dropping rows because `auth()` was throwing synchronously
// inside Auth.js v5's JWT callback chain (it reads `headers()` while
// computing the session, and headers() is request-scoped only). The
// previous `await auth().catch(() => null)` only catches REJECTED
// promises; synchronous throws bypassed it entirely and bubbled into
// the outer try/catch, which then bailed before the prisma write.
//
// Two-pronged fix:
//   (A) logAudit short-circuits session resolution when caller passes
//       BOTH userId AND practiceId. Worker layers already had these
//       in their Layer*Input shape; they were just missing from the
//       call site.
//   (B) When auth() IS called (request scope, or worker calls without
//       a full override), it's wrapped in
//         Promise.resolve().then(() => auth()).catch(() => null)
//       The `.then` callback re-routes synchronous throws into
//       promise rejections that `.catch` can handle — bare
//       `.catch()` only handles rejected promises, not sync throws.
//
// Plus call-site corrections at the 4 prompt-injection-delimiter audit
// emits (L2/L3/L4/L5) that were not yet passing userId+practiceId.
// ============================================================================

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const REPO_ROOT = resolve(__dirname, '..', '..', '..', '..');

function readSource(relPath: string): string {
  return readFileSync(resolve(REPO_ROOT, relPath), 'utf-8');
}

// ============================================================================
// Part A — Runtime behavior of logAudit's session resolution.
// ============================================================================

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  headers: vi.fn(),
  prismaCreate: vi.fn(),
  isRedisReady: vi.fn(() => false),
}));

vi.mock('@/lib/nextauth', () => ({ auth: mocks.auth }));
vi.mock('next/headers', () => ({ headers: mocks.headers }));
vi.mock('@meddoc/db', () => ({
  default: { auditLog: { create: mocks.prismaCreate } },
}));
vi.mock('@/lib/redis', () => ({
  getRedis: () => ({ publish: vi.fn() }),
  isRedisReady: mocks.isRedisReady,
  ADMIN_AUDIT_STREAM_CHANNEL: 'admin:audit',
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.headers.mockResolvedValue({ get: () => null });
  mocks.prismaCreate.mockResolvedValue({ id: 'audit_1' });
});

describe('logAudit session resolution — worker-context safety', () => {
  it('skips auth() when caller passes both userId AND practiceId', async () => {
    const { logAudit } = await import('@/lib/audit');
    await logAudit({
      action: 'PIPELINE_REJECTED_INJECTION_DELIMITER',
      targetId: 'visit_1',
      targetType: 'transcribe_visit',
      userId: 'user_42',
      practiceId: 'practice_7',
    });
    // Critical: auth() must NOT have been called. This is the worker-
    // context safety property — even if Auth.js's session resolution
    // would throw synchronously, the row is still written.
    expect(mocks.auth).not.toHaveBeenCalled();
    expect(mocks.prismaCreate).toHaveBeenCalledTimes(1);
    const arg = mocks.prismaCreate.mock.calls[0][0];
    expect(arg.data.userId).toBe('user_42');
    expect(arg.data.practiceId).toBe('practice_7');
  });

  it('still calls auth() when caller passes ONLY userId (partial override)', async () => {
    mocks.auth.mockResolvedValue({
      user: { id: 'session_user', practiceId: 'session_practice' },
    });
    const { logAudit } = await import('@/lib/audit');
    await logAudit({
      action: 'VISIT_SIGNED',
      targetId: 'visit_1',
      userId: 'caller_user',
      // No practiceId override — session lookup needed for that.
    });
    expect(mocks.auth).toHaveBeenCalledTimes(1);
    const arg = mocks.prismaCreate.mock.calls[0][0];
    expect(arg.data.userId).toBe('caller_user');
    expect(arg.data.practiceId).toBe('session_practice');
  });

  it('survives a SYNCHRONOUS throw from auth() and still writes the row', async () => {
    // This is the failure mode that the pre-fix `.catch(() => null)`
    // did NOT cover. `.catch()` only handles rejected promises; if
    // `auth()` throws before returning a thenable (the worker-context
    // path inside Auth.js v5), `.catch()` is never invoked and the
    // exception bubbles into the outer try/catch which bails. The
    // `Promise.resolve().then(() => auth()).catch(() => null)` wrap
    // re-routes the synchronous throw into a promise rejection that
    // `.catch` then handles, returning null and letting the prisma
    // write proceed.
    mocks.auth.mockImplementation(() => {
      throw new Error('headers was called outside a request scope');
    });
    const { logAudit } = await import('@/lib/audit');
    await logAudit({
      action: 'PIPELINE_REJECTED_INJECTION_DELIMITER',
      targetId: 'visit_1',
      // Only ONE override → triggers auth() lookup → sync throw.
      userId: 'caller_user',
    });
    expect(mocks.auth).toHaveBeenCalledTimes(1);
    expect(mocks.prismaCreate).toHaveBeenCalledTimes(1);
    const arg = mocks.prismaCreate.mock.calls[0][0];
    expect(arg.data.userId).toBe('caller_user');
    // ⚠️ ASSERTION CHANGED 2026-08-04, DELIBERATELY AND DECLARED.
    //
    // This line used to read `expect(arg.data.practiceId).toBe('clinic_main')`
    // — it asserted the fail-OPEN fallback, and passed, for months. That is
    // the uncomfortable part and the reason this comment is long: the test was
    // green the whole time, faithfully pinning the wrong behaviour. A guard
    // that encodes a defect is indistinguishable from one that encodes a
    // requirement, right up until somebody reads the value.
    //
    // What was wrong with it: `clinic_main` is the largest SHARED practice in
    // production (11 users). Attributing an unresolvable write to it means a
    // tenant boundary whose answer to "whose is this?" is "the biggest one".
    // 64 production LOGOUT rows, from 64 different solo doctors, landed there.
    //
    // The contract now: unresolvable means NULL in the FK column and the
    // UNATTRIBUTED sentinel in the tombstone column, plus a console.error.
    // Enforced by `gate-audit-attribution-failclosed`, which is proven red
    // against the exact pre-fix line.
    //
    // The behaviour this test actually exists for is UNCHANGED and still
    // asserted above: a synchronous throw from `auth()` must not stop the row
    // being written.
    expect(arg.data.practiceId).toBeNull();
    expect(arg.data.practiceIdSnapshot).toBe('UNATTRIBUTED');
  });

  it('survives a REJECTED-promise throw from auth() (legacy failure mode)', async () => {
    mocks.auth.mockRejectedValue(new Error('session unreadable'));
    const { logAudit } = await import('@/lib/audit');
    await logAudit({
      action: 'VISIT_SIGNED',
      targetId: 'visit_1',
      userId: 'caller_user',
    });
    expect(mocks.prismaCreate).toHaveBeenCalledTimes(1);
    expect(mocks.prismaCreate.mock.calls[0][0].data.userId).toBe('caller_user');
  });

  it('writes the row when userId is null + auth() throws (anonymous worker hot path)', async () => {
    // Worker hot path: many BullMQ jobs run for visits whose owning
    // user is set, but the layer can be invoked with `userId: null`
    // when no user context is available (e.g., scheduled cleanups,
    // some retry paths). In that case `hasFullOverride` is false
    // even though `practiceId` is set — we fall through to the
    // auth() path. Production worker context throws synchronously
    // here. The row must still write with userId: null.
    mocks.auth.mockImplementation(() => {
      throw new Error('headers was called outside a request scope');
    });
    const { logAudit } = await import('@/lib/audit');
    await logAudit({
      action: 'PIPELINE_REJECTED_INJECTION_DELIMITER',
      targetId: 'visit_1',
      userId: null,
      practiceId: 'practice_7',
    });
    expect(mocks.auth).toHaveBeenCalledTimes(1);
    expect(mocks.prismaCreate).toHaveBeenCalledTimes(1);
    const arg = mocks.prismaCreate.mock.calls[0][0];
    expect(arg.data.userId).toBeNull();
    expect(arg.data.practiceId).toBe('practice_7');
  });

  it('never throws — even when prisma itself fails (T-M2 contract)', async () => {
    mocks.prismaCreate.mockRejectedValue(new Error('db down'));
    const { logAudit } = await import('@/lib/audit');
    await expect(
      logAudit({
        action: 'VISIT_SIGNED',
        targetId: 'visit_1',
        userId: 'u',
        practiceId: 'p',
      }),
    ).resolves.toBeUndefined();
  });
});

// ============================================================================
// Part B — Source-pinning: prove the 4 prompt-injection audit emits in
// L2/L3/L4/L5 pass userId+practiceId from `input`. Mirrors the pattern
// in tests/audit/page-rsc-audits.test.ts — full-runtime testing of
// these layers requires the entire worker stack, so we pin the source
// shape so a future refactor can't drop the override silently.
// ============================================================================

const INJECTION_AUDIT_BLOCK = (layer: 'L2' | 'L3' | 'L4' | 'L5') =>
  new RegExp(
    `void\\s+logAudit\\s*\\(\\s*\\{[\\s\\S]*?` +
      `action:\\s*['"]PIPELINE_REJECTED_INJECTION_DELIMITER['"][\\s\\S]*?` +
      `userId:\\s*input\\.userId[\\s\\S]*?` +
      `practiceId:\\s*input\\.practiceId[\\s\\S]*?` +
      `layer:\\s*['"]${layer}['"][\\s\\S]*?\\}\\s*\\)`,
    'm',
  );

describe('worker prompt-injection audit calls pass userId+practiceId', () => {
  it.each([
    ['L2', 'apps/transcribe-md/src/worker/layers/02-speaker-roles.ts'],
    ['L3', 'apps/transcribe-md/src/worker/layers/03-extract-entities.ts'],
    ['L4', 'apps/transcribe-md/src/worker/layers/04-generate-soap.ts'],
    ['L5', 'apps/transcribe-md/src/worker/layers/05-self-critique.ts'],
  ] as const)('%s injection-delimiter audit emits override fields', (layer, path) => {
    const src = readSource(path);
    expect(src).toMatch(INJECTION_AUDIT_BLOCK(layer));
  });
});
