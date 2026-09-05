// ============================================================================
// RULING #187(a) — A SERIALIZATION FAILURE IS NOT A VANISHED MANIFEST.
// ----------------------------------------------------------------------------
// THE DEFECT. `sign/route.ts` wraps its signature in a `Serializable`
// transaction. A concurrent coding decision on the same visit is enough for
// Postgres to abort it with SQLSTATE 40001 — Prisma's `P2034` — and that abort
// fell into the manifest-fallback catch, which:
//
//     nativeFreeze = { state: 'failed', reason: 'frozen_manifest_vanished' }
//     updated = await signWrite(null)          // ← STYLED, FOREVER
//
// Three things wrong, and none recoverable:
//
//   · the manifest never vanished. `resolveFrozenPointer` had just returned it
//     and the retry threw it away;
//   · a visit signed styled is styled FOREVER — canon 02 records that there is
//     no re-attestation path — so a doctor loses their own letterhead because
//     somebody clicked a code at the wrong moment;
//   · the audit row and the doctor-facing notice both name a cause that did not
//     happen, which is worse than naming none.
//
// ⚠️ AND THE SECOND ORDERING IS WORSE THAN THE FIRST. A 40001 raised on the
// RETRY escaped the try entirely and surfaced as a 500 with the note left
// READY — on a route whose whole job is to be precise about why a signature did
// not happen.
//
// THE FIX. 40001 is the one error class here that is EXPECTED and RETRYABLE; it
// is how Serializable says "take your snapshot again". Three bounded attempts,
// each re-running the WHOLE transaction so it re-reads everything, KEEPING the
// pointer. Exhausted retries REFUSE with a 409 — err toward the edge, because
// the edge has a fence: a refusal is loud, recoverable and honest, and a styled
// signature is silent, permanent, and blames the wrong thing.
//
// ARMED WITH A FORCED 40001, as the ruling requires.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findUnique: vi.fn(),
  userFindUnique: vi.fn(),
  updateMany: vi.fn(),
  rxOverrideFindMany: vi.fn(),
  auth: vi.fn(),
  logAudit: vi.fn(),
  logWarn: vi.fn(),
  loadVisitExportData: vi.fn(),
  criticalWarningRefs: vi.fn(),
  logDelivery: vi.fn(),
  captureEditPattern: vi.fn(),
  computeDisplayedEmCode: vi.fn(),
  resolveFrozenPointer: vi.fn(),
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
      findUnique: mocks.findUnique,
      findFirst: mocks.findUnique,
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
  log: { warn: mocks.logWarn, info: vi.fn(), error: vi.fn() },
}));
vi.mock('@meddoc/ai', () => ({ redactPhi: (x: unknown) => x }));
vi.mock('@/lib/visit-export', () => ({ formatVisitDate: () => '2026-08-27' }));
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
// ⚠️ THE POINTER RESOLVES. That is the premise: the manifest is THERE, so any
// "frozen_manifest_vanished" the route reaches is false by construction.
vi.mock('@/lib/template-twin/sign-freeze', () => ({
  resolveFrozenPointer: mocks.resolveFrozenPointer,
}));

import type { NextRequest } from 'next/server';
import { Prisma, TranscribeVisitStatus } from '@prisma/client';

import { POST } from '../route';
// NOT mocked — the shipped predicate, so the fixtures below are classified by
// the same function the route and the export seam use.
import { emAppliesToVisit } from '@/lib/note-shape';

const DOCTOR = 'doc1';
const VISIT = 'visit-f12e';
const FROZEN = '99214';

/** Office-shaped: full SOAP skeleton, zero operative markers. */
const OFFICE_NOTE = [
  '## Subjective',
  'Routine follow-up for hypertension.',
  '## Objective',
  'BP 148/92.',
  '## Assessment',
  'Hypertension not at goal.',
  '## Plan',
  'Increase lisinopril.',
].join('\n');

/** Operative-shaped: the F12-c fixture, verbatim in structure. */
const OPERATIVE_NOTE = [
  '## Preoperative Diagnosis',
  'Screening colonoscopy.',
  '## Description of Procedure',
  'The scope was advanced to the cecum.',
  '## Postoperative Findings',
  'One sessile polyp removed by snare.',
].join('\n');

function visitRow(over: Record<string, unknown> = {}) {
  return {
    id: VISIT,
    userId: DOCTOR,
    status: TranscribeVisitStatus.READY,
    specialty: 'gastroenterology',
    // No bound template -> `templateIsSilent`, so the NOTE TEXT decides. This
    // is the axis F12-e lives on, and it keeps the fixtures independent of
    // `ultrasoundSpecialtyEnabled()`, which is a flag.
    noteTemplate: null,
    soapFinal: OFFICE_NOTE,
    cptCodes: null,
    icdCodes: null,
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

/** The `data` payload of the SIGNED write. Separated from `writtenCpt()`
 *  deliberately — see the vacuity note below. */
// ── THE ARMS ─────────────────────────────────────────────────────────────────

/** A real Prisma serialization abort, by code. */
function serializationError(): Error {
  const e = new Error('\nInvalid `prisma.transcribeVisit.updateMany()` invocation:\n\nTransaction failed due to a write conflict or a deadlock. Please retry your transaction');
  (e as unknown as { code: string }).code = 'P2034';
  Object.defineProperty(e, 'name', { value: 'PrismaClientKnownRequestError' });
  return e;
}

/** The same abort as the raw driver reports it, with no Prisma mapping. */
function rawSqlstate40001(): Error {
  return new Error('could not serialize access due to concurrent update (SQLSTATE 40001)');
}

/**
 * ⚠️ `mock.calls` RECORDS ATTEMPTS, NOT WRITES — including the ones that threw.
 *
 * The first version of these arms used `.find()` over every recorded call, and
 * both failing assertions were the instrument rather than the route: a run
 * where every `updateMany` REJECTED still "found" a SIGNED row, and a run whose
 * successful styled write came last was judged by its failed first attempt.
 *
 * The write that actually landed is the LAST one, because every earlier attempt
 * threw. `attemptedWrites()` is kept separate and named for what it is, so an
 * assertion about attempts can never be mistaken for one about outcomes.
 */
const attemptedWrites = () =>
  mocks.updateMany.mock.calls
    .map((c) => (c[0] as { data?: Record<string, unknown> })?.data)
    .filter((d) => d?.status === TranscribeVisitStatus.SIGNED);

const signedWrite = () => attemptedWrites().at(-1);

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({ user: { id: DOCTOR, email: 'doc@test.dev', practiceId: 'p1' } });
  mocks.userFindUnique.mockResolvedValue({ practiceRole: 'CLINICIAN' });
  mocks.findUnique.mockResolvedValue(visitRow());
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.rxOverrideFindMany.mockResolvedValue([]);
  mocks.criticalWarningRefs.mockReturnValue([]);
  mocks.computeDisplayedEmCode.mockResolvedValue(FROZEN);
  mocks.resolveFrozenPointer.mockResolvedValue('manifest-42');
  mocks.loadVisitExportData.mockResolvedValue({
    clinicianName: 'Dr. Test',
    patientName: 'P',
    signedAt: new Date('2026-09-05T11:00:00.000Z'),
    createdAt: new Date('2026-09-05T09:00:00.000Z'),
  });
});

describe('⚠️ a 40001 is RETRIED, and never signed styled', () => {
  it('a single serialization failure retries and KEEPS the manifest', async () => {
    mocks.updateMany.mockRejectedValueOnce(serializationError()).mockResolvedValue({ count: 1 });
    const res = await call();

    expect(mocks.updateMany.mock.calls.length, 'it did not retry').toBe(2);
    const d = signedWrite();
    expect(d, 'the visit never got signed at all').toBeTruthy();
    // ⚠️ THE POINTER SURVIVES. This is the whole finding: the retry used to
    // discard a manifest that was there the entire time.
    expect(d?.frozenFillManifestId).toBe('manifest-42');

    const body = (await res.json()) as { formatNotice?: { reason?: string } };
    expect(body.formatNotice?.reason).not.toBe('frozen_manifest_vanished');
  });

  it('a REAL Prisma error object is recognised — the instanceof path', async () => {
    // The duck-typed `.code` read is what makes this robust, but the real
    // article must work too, or the check passes only on my own fixture.
    const real = new Prisma.PrismaClientKnownRequestError(
      'Transaction failed due to a write conflict or a deadlock. Please retry your transaction',
      { code: 'P2034', clientVersion: 'test' },
    );
    mocks.updateMany.mockRejectedValueOnce(real).mockResolvedValue({ count: 1 });
    await call();
    expect(mocks.updateMany.mock.calls.length).toBe(2);
    expect(signedWrite()?.frozenFillManifestId).toBe('manifest-42');
  });

  it('⚠️ P2034’s own MESSAGE contains no 40001 — the two branches are both load-bearing', () => {
    // Recorded because it is why the first version of this fix failed its own
    // arming test: Prisma's mapped message says "write conflict or a deadlock"
    // and never mentions the SQLSTATE. A message-only check misses every mapped
    // abort; a code-only check misses every un-mapped one.
    const mapped = 'Transaction failed due to a write conflict or a deadlock. Please retry your transaction';
    expect(/\b40001\b/.test(mapped)).toBe(false);
    expect(/could not serialize access/i.test(mapped)).toBe(false);
  });

  it('the RAW SQLSTATE is recognised too, not only Prisma’s P2034', async () => {
    // The driver does not always map it. Recognising only `P2034` would leave
    // the un-mapped form falling straight back into the styled path.
    mocks.updateMany.mockRejectedValueOnce(rawSqlstate40001()).mockResolvedValue({ count: 1 });
    await call();
    expect(mocks.updateMany.mock.calls.length).toBe(2);
    expect(signedWrite()?.frozenFillManifestId).toBe('manifest-42');
  });

  it('two failures still succeed — the bound is THREE attempts', async () => {
    mocks.updateMany
      .mockRejectedValueOnce(serializationError())
      .mockRejectedValueOnce(serializationError())
      .mockResolvedValue({ count: 1 });
    await call();
    expect(mocks.updateMany.mock.calls.length).toBe(3);
    expect(signedWrite()?.frozenFillManifestId).toBe('manifest-42');
  });

  it('⚠️ a PERSISTENT 40001 REFUSES — it does not sign, styled or otherwise', async () => {
    mocks.updateMany.mockRejectedValue(serializationError());
    const res = await call();

    expect(res.status).toBe(409);
    const body = (await res.json()) as { code?: string; ok?: boolean };
    expect(body.code).toBe('SIGN_RACE_LOST');
    expect(body.ok).toBe(false);

    // ⚠️ THE ASSERTION THAT MATTERS, AND IT IS ABOUT WHAT WAS **ATTEMPTED**.
    // Every `updateMany` here rejects, so nothing landed — that much is
    // guaranteed by the mock and is not worth asserting. What must be true is
    // that the route never even TRIED the styled write, because that attempt is
    // the permanent downgrade and on a real database it would have succeeded.
    const styled = attemptedWrites().filter((d) => d?.frozenFillManifestId === null);
    expect(styled.length, 'it tried to sign the note STYLED on a 40001').toBe(0);
    // And every attempt it did make kept the manifest.
    expect(attemptedWrites().every((d) => d?.frozenFillManifestId === 'manifest-42')).toBe(true);
    expect(attemptedWrites().length, 'non-vacuity: it did attempt to sign').toBe(3);
    // Bounded: it did not retry forever.
    expect(mocks.updateMany.mock.calls.length).toBe(3);
  });

  it('a NON-serialization failure still falls back to styled — the fix is narrow', async () => {
    // ⚠️ THE OTHER DIRECTION, AND IT MUST NOT BE TRADED. A genuinely broken
    // freeze is what the styled fallback is FOR; narrowing it to nothing would
    // trade one silent harm for a refused signature on a real manifest failure.
    mocks.updateMany.mockRejectedValueOnce(new Error('disk on fire')).mockResolvedValue({ count: 1 });
    const res = await call();
    expect(res.status).not.toBe(409);
    const d = signedWrite();
    expect(d).toBeTruthy();
    expect(d?.frozenFillManifestId, 'a real freeze failure must still sign styled').toBeNull();
    const body = (await res.json()) as { formatNotice?: { reason?: string } };
    expect(body.formatNotice?.reason).toBe('frozen_manifest_vanished');
  });

  it('non-vacuity: with NO failure the note signs once, with its manifest', async () => {
    await call();
    expect(mocks.updateMany.mock.calls.length).toBe(1);
    expect(signedWrite()?.frozenFillManifestId).toBe('manifest-42');
  });
});
