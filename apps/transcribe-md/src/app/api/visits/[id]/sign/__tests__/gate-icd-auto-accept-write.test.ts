// ============================================================================
// THE SIGN-TIME AUTO-ACCEPT — THE WRITE. THE GATE.
// ----------------------------------------------------------------------------
// `gate-icd-auto-accept` pins the RULE, as a pure function. This pins that the
// ROUTE applies it, from the right snapshot, in the right statement — and the
// three are separate questions. A correct rule read from a stale row produces a
// wrong write with every unit test green.
//
// ⚠️ THE ARM THAT MATTERS IS THE RACE, AND IT IS NOT HYPOTHETICAL. The
// compare-and-swap on this write keys on `soapVersion`, and a coding decision
// does not move it. So a doctor rejecting a code between the route's entry read
// and its write is INVISIBLE to the CAS. If the auto-accept computed from the
// captured row, that rejection would be overwritten by a machine-written
// ACCEPTANCE, on a signed record, with nothing anywhere reporting it — the
// exact shape `emPendingChange` already re-reads to avoid, one column over.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findFirst: vi.fn(),
  userFindUnique: vi.fn(),
  updateMany: vi.fn(),
  rxOverrideFindMany: vi.fn(),
  auth: vi.fn(),
  logAudit: vi.fn(),
  logInfo: vi.fn(),
  loadVisitExportData: vi.fn(),
  criticalWarningRefs: vi.fn(),
  logDelivery: vi.fn(),
  captureEditPattern: vi.fn(),
  computeDisplayedEmCode: vi.fn(),
}));

vi.mock('next/server', () => {
  class FakeNextResponse {
    status: number;
    headers = new Map<string, string>();
    private body: unknown;
    constructor(body: unknown, init?: { status?: number }) {
      this.body = body;
      this.status = init?.status ?? 200;
    }
    async json() {
      return this.body;
    }
    static json(body: unknown, init?: { status?: number }) {
      return new FakeNextResponse(body, init);
    }
  }
  return { NextResponse: FakeNextResponse };
});

vi.mock('@meddoc/db', () => {
  const prisma: Record<string, unknown> = {
    transcribeVisit: {
      findFirst: mocks.findFirst,
      updateMany: mocks.updateMany,
    },
    user: { findUnique: mocks.userFindUnique },
    rxWarningOverride: { findMany: mocks.rxOverrideFindMany },
    $transaction: (fn: (tx: unknown) => unknown) =>
      typeof fn === 'function' ? fn(prisma) : Promise.all(fn as never),
  };
  return { default: prisma, prisma };
});
vi.mock('@/lib/nextauth', () => ({ auth: mocks.auth }));
vi.mock('@/lib/auth', () => ({ getSession: mocks.auth }));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/lib/log', () => ({
  log: { warn: vi.fn(), info: mocks.logInfo, error: vi.fn() },
}));
vi.mock('@meddoc/ai', () => ({ redactPhi: (x: unknown) => x }));
vi.mock('@/lib/visit-export', () => ({ formatVisitDate: () => '2026-09-05' }));
vi.mock('@/lib/visit-export-server', () => ({
  loadVisitExportData: mocks.loadVisitExportData,
}));
vi.mock('@/lib/ehr-formatters', () => ({ formatForEhr: () => 'formatted' }));
vi.mock('@/lib/email', () => ({ sendVisitPdfEmail: vi.fn() }));
vi.mock('@/lib/deliveries', () => ({ logDelivery: mocks.logDelivery }));
vi.mock('@/lib/edit-tracking', () => ({
  captureEditPattern: mocks.captureEditPattern,
}));
vi.mock('@/lib/rx-warnings', () => ({
  criticalWarningRefs: mocks.criticalWarningRefs,
}));
vi.mock('@/lib/em-coding/displayed-level', () => ({
  computeDisplayedEmCode: mocks.computeDisplayedEmCode,
}));

import type { NextRequest } from 'next/server';
import { TranscribeVisitStatus } from '@prisma/client';

import { POST } from '../route';
import type { IcdDecisionMap } from '@/lib/icd-decisions';

const DOCTOR = 'doc1';
const VISIT = 'visit-auto-icd';

const NOTE = [
  '## Subjective',
  'Routine follow-up for hypertension.',
  '## Objective',
  'BP 148/92.',
  '## Assessment',
  'Hypertension not at goal.',
  '## Plan',
  'Increase lisinopril.',
].join('\n');

/** One code the generator states outright (0.95) and one it only implies
 *  (0.60) — the two sides of the threshold, in one visit. */
const CODES = {
  codes: [
    { code: 'I10', description: 'Essential hypertension', evidence_quote: 'q', confidence: 0.95 },
    { code: 'E11.9', description: 'T2DM', evidence_quote: 'q', confidence: 0.6 },
  ],
};

function visitRow(over: Record<string, unknown> = {}) {
  return {
    id: VISIT,
    userId: DOCTOR,
    status: TranscribeVisitStatus.READY,
    specialty: 'gastroenterology',
    noteTemplate: null,
    soapFinal: NOTE,
    cptCodes: null,
    icdCodes: CODES,
    icdDecisions: null,
    rxDrafts: null,
    signedAt: null,
    deletedAt: null,
    archivedAt: null,
    emPendingChange: null,
    ...over,
  };
}

function call() {
  const req = {
    json: async () => ({ destinations: [], attestation: { acknowledged: true } }),
  } as unknown as NextRequest;
  return POST(req, { params: Promise.resolve({ id: VISIT }) });
}

function signedWrite(): Record<string, unknown> | undefined {
  const c = mocks.updateMany.mock.calls.find(
    (x) => (x[0] as { data?: Record<string, unknown> })?.data?.status === TranscribeVisitStatus.SIGNED,
  );
  return (c?.[0] as { data?: Record<string, unknown> })?.data;
}

/** ⚠️ NON-VACUITY. Every "it did not write X" arm below is also satisfied by a
 *  route that refused, threw, or never reached the write — so each asserts the
 *  SIGNED write HAPPENED before asserting anything about its contents. */
function expectSigned(): Record<string, unknown> {
  const d = signedWrite();
  expect(
    d,
    `no SIGNED write happened — the assertions below would pass vacuously. ` +
      `updateMany calls: ${mocks.updateMany.mock.calls.length}`,
  ).toBeTruthy();
  return d!;
}

const written = () => signedWrite()?.icdDecisions as IcdDecisionMap | undefined;

/**
 * ⚠️ THE ROUTE READS THE VISIT THREE TIMES AND ALL THREE ARE `findFirst` —
 * MEASURED, NOT ASSUMED, AND THE FIRST VERSION OF THIS FILE GOT IT WRONG.
 *
 * It mocked `findUnique` for the entry read and `findFirst` for the fresh one,
 * on the assumption they were different methods. `findUnique` is NEVER CALLED.
 * So a single `mockResolvedValue` served the capture AND the re-read, both race
 * arms below saw the rejection at entry too, and they PASSED — proving the rule
 * works and saying nothing whatever about the fresh read being load-bearing.
 * A false green on the one arm the design exists for.
 *
 * The dispatch is on the SELECT rather than on call order, so it survives a
 * reordering that call indices would not:
 *
 *   entry read       — the big select, `emStale`/`soapVersion`, NO `icdDecisions`
 *   in-transaction   — `cptCodes, emPendingChange, icdCodes, icdDecisions`
 *   post-write       — `signedAt` alone
 */
function serveReads(entry: Record<string, unknown>, fresh: Record<string, unknown>) {
  mocks.findFirst.mockImplementation(async (args: unknown) => {
    const sel = ((args as { select?: Record<string, unknown> })?.select ?? {}) as Record<string, unknown>;
    if (sel.icdDecisions) return fresh;
    if (sel.signedAt && Object.keys(sel).length === 1) return { signedAt: new Date() };
    return entry;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({ user: { id: DOCTOR, email: 'doc@test.dev', practiceId: 'p1' } });
  mocks.userFindUnique.mockResolvedValue({ practiceRole: 'CLINICIAN' });
  serveReads(visitRow(), visitRow());
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.rxOverrideFindMany.mockResolvedValue([]);
  mocks.criticalWarningRefs.mockReturnValue([]);
  mocks.computeDisplayedEmCode.mockResolvedValue('99214');
  mocks.loadVisitExportData.mockResolvedValue({
    clinicianName: 'Dr. Test',
    patientName: 'P',
    signedAt: new Date('2026-09-05T11:00:00.000Z'),
    createdAt: new Date('2026-09-05T09:00:00.000Z'),
  });
});

describe('the sign-time auto-accept WRITE', () => {
  it('writes the high-confidence code as accepted, in the SIGNED statement', async () => {
    await call();
    const d = expectSigned();
    expect(written()?.['I10']).toEqual({
      state: 'accepted',
      at: expect.any(String),
      byUserId: DOCTOR,
      auto: true,
    });
    // ⚠️ THE SAME `updateMany` AS THE SIGNATURE — a follow-up update would
    // leave a window in which the record is SIGNED and its codes undecided.
    expect(d.signedAt).toBeTruthy();
    expect(d.signedBy).toBe(DOCTOR);
  });

  it('leaves the merely-implied code UNDECIDED — it is not the machine’s call', async () => {
    await call();
    expectSigned();
    expect(written()?.['E11.9']).toBeUndefined();
    // Non-vacuity: the map exists and is not simply empty.
    expect(Object.keys(written() ?? {})).toEqual(['I10']);
  });

  it('⚠️ writes NOTHING to the column when it added nothing', async () => {
    // An unconditional write would rewrite the whole column on every signature
    // — the narrowing hazard `ICD_DECISION_RECORD_KEYS` exists for: a field a
    // deployed reader does not know about is stripped by a signature that
    // changed nothing.
    const lowOnly = { codes: [{ code: 'E11.9', description: 'x', evidence_quote: 'q', confidence: 0.6 }] };
    serveReads(visitRow({ icdCodes: lowOnly }), visitRow({ icdCodes: lowOnly }));
    await call();
    const d = expectSigned();
    expect('icdDecisions' in d).toBe(false);
  });

  it('⚠️ THE RACE — a rejection landing AFTER entry is READ AND HONOURED', async () => {
    // Entry sees the code undecided. Between then and the write, the doctor
    // rejects it. The CAS keys on `soapVersion` and cannot see that.
    serveReads(
      visitRow({ icdDecisions: null }), // entry: nothing decided
      visitRow({
        icdDecisions: {
          I10: { state: 'rejected', at: '2026-09-05T10:59:00.000Z', byUserId: DOCTOR, reason: 'not_this_encounter' },
        },
      }), // in-transaction: the doctor said NO in between
    );
    await call();
    expectSigned();
    // Nothing was added, so the column is not rewritten at all — the doctor's
    // rejection stands exactly as they left it.
    expect(written()?.['I10']?.state).not.toBe('accepted');
    expect(signedWrite()?.icdDecisions).toBeUndefined();
  });

  it('⚠️ THE RACE, OTHER DIRECTION — an acceptance landing after entry keeps THEIR attribution', async () => {
    serveReads(
      visitRow({ icdDecisions: null }),
      visitRow({
        icdDecisions: {
          I10: { state: 'accepted', at: '2026-09-05T10:59:00.000Z', byUserId: 'someone-else' },
        },
      }),
    );
    await call();
    expectSigned();
    expect(signedWrite()?.icdDecisions).toBeUndefined();
  });

  it('the fresh re-read actually SELECTS the two ICD columns', async () => {
    // The arms above are only meaningful if the route asks for these columns.
    // A `select` missing them yields `undefined` — which reads as "no prior
    // decisions" and would auto-accept straight over a rejection.
    await call();
    const selects = mocks.findFirst.mock.calls.map(
      (c) => ((c[0] as { select?: Record<string, unknown> })?.select ?? {}) as Record<string, unknown>,
    );
    // The route reads the visit three times. Named by CONTENT, not by index.
    expect(selects.length).toBe(3);
    const inTx = selects.filter((s) => s.icdDecisions === true);
    expect(inTx.length, 'exactly one read asks for the decision column').toBe(1);
    expect(inTx[0]?.icdCodes, 'the codes and the decisions must come from ONE snapshot').toBe(true);
    // And the ENTRY read does NOT carry it — which is what makes the fresh
    // read a different snapshot rather than a duplicate of the capture.
    expect(selects.some((s) => s.emStale === true && s.icdDecisions === undefined)).toBe(true);
  });

  it('logs the codes it decided for the doctor, and no note content', async () => {
    await call();
    const entry = mocks.logInfo.mock.calls.find((c) => String(c[1]).includes('auto-accept'));
    expect(entry, 'a machine-written diagnosis that logs nothing is unauditable').toBeTruthy();
    const meta = JSON.stringify(entry?.[2] ?? {});
    expect(meta).toContain('I10');
    // An ICD code is not patient context. The evidence quote is.
    expect(meta).not.toContain('evidence');
    expect(meta).not.toContain('hypertension');
  });
});
