// ============================================================================
// POST /api/visits/[id]/sign — E/M visible-confirm gate (prod smoke #311).
// ----------------------------------------------------------------------------
// All collaborators mocked (prisma / auth / audit / delivery stack); the
// gate logic + the em-pending-change coercion are REAL. Pins the hard
// requirement — a silent suggestion-caused E/M level change must be
// IMPOSSIBLE to sign through:
//   - an UNACKNOWLEDGED recorded change + no `acknowledgedEmChange` in the
//     body → 400 { ok:false, error, code:'EM_CHANGE_UNACKNOWLEDGED' }, NO
//     status write, EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE audit
//   - a STALE acknowledgement (echoing different codes than the record)
//     is refused the same way — content-identity, not a bare boolean
//   - a MATCHING acknowledgement signs; the record is MARKED acknowledged
//     (not cleared) in the same READY→SIGNED update, and the VISIT_SIGNED
//     audit metadata carries emChangeAcknowledged {from, to}
//   - no record / already-acknowledged record → no gate (sign as before)
//   - a malformed-but-present record fails CLOSED ('unknown' sentinel)
//   - already-SIGNED visits (re-deliver path) skip the gate
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
}));

// Minimal NextResponse stand-in — deterministic across vitest
// environments (the route + api-error only use NextResponse.json and
// response.headers.set).
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
      // T5: the sign route's reads are practice-scoped, so they use findFirst
      // (findUnique cannot carry a non-unique predicate). Same mock, same rows.
      findFirst: mocks.findUnique,
      updateMany: mocks.updateMany,
    },
    // T6: the sign gate reads the SIGNER's practice role. Without this the
    // route throws before any gate under test runs, and 13 specs report 500.
    user: { findUnique: mocks.userFindUnique },
    rxWarningOverride: { findMany: mocks.rxOverrideFindMany },
    // F5-h: the signature write now runs inside a transaction so the E/M blob
    // is RE-READ next to the CAS-guarded update — a concurrent override must
    // not be erased by a whole-blob overwrite built from a stale capture.
    // The interactive callback gets the same client, so these specs observe the
    // identical calls they did before.
    $transaction: (fn: (tx: unknown) => unknown) =>
      typeof fn === 'function' ? fn(prisma) : Promise.all(fn as never),
  };
  return { default: prisma, prisma };
});
vi.mock('@/lib/nextauth', () => ({ auth: mocks.auth }));
// T5: the by-id routes now source practiceId from the DB-refreshed session.
vi.mock('@/lib/auth', () => ({ getSession: mocks.auth }));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/lib/log', () => ({
  log: { warn: mocks.logWarn, info: vi.fn(), error: vi.fn() },
}));
vi.mock('@meddoc/ai', () => ({ redactPhi: (x: unknown) => x }));
vi.mock('@/lib/visit-export', () => ({ formatVisitDate: () => '2026-06-12' }));
vi.mock('@/lib/visit-export-server', () => ({
  loadVisitExportData: mocks.loadVisitExportData,
}));
vi.mock('@/lib/ehr-formatters', () => ({ formatForEhr: () => 'formatted' }));
// Ruling #116(b) — `POST /sign` no longer renders a PDF at all, so there is no
// generator left to stub. The render that used to happen here existed only to
// read `.byteLength` into a write-only column.
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

const DOCTOR = 'doc1';
const VISIT = 'visit-1';

const PENDING = {
  from: '99213',
  to: '99214',
  cause: 'suggestion_adopted',
  at: '2026-06-12T10:00:00.000Z',
};

const BLOCK_ERROR =
  'Documentation level changed (99213 → 99214) by an AI-suggestion action — confirm the new level before signing.';

function visitRow(over: Record<string, unknown> = {}) {
  return {
    id: VISIT,
    userId: DOCTOR,
    status: TranscribeVisitStatus.READY,
    soapFinal: '## Subjective\nElbow pain.\n\n## Plan\nNSAIDs.',
    rxDrafts: null,
    signedAt: null,
    deletedAt: null,
    archivedAt: null,
    emPendingChange: null,
    ...over,
  };
}

/** ⚠️ EVERY SIGN IN THIS FILE NOW ATTESTS.
 *  `POST /sign` gained a required `attestation` term on 2026-08-02 (see
 *  `sign-gates.ts` — the gate stopped being UI-only after a second sign control
 *  shipped that could walk past it). These tests are about the E/M gate, so
 *  they attest by default and stay about their own subject; the attestation
 *  refusal has its own tests. A caller that wants to prove the refusal passes
 *  `{ attestation: undefined }` explicitly. */
function withAttestation(body: unknown): unknown {
  if (typeof body !== 'object' || body === null) return body;
  const b = body as Record<string, unknown>;
  if ('attestation' in b) return b;
  return { ...b, attestation: { acknowledged: true } };
}

function call(rawBody: unknown) {
  const body = withAttestation(rawBody);
  const req = { json: async () => body } as unknown as NextRequest;
  return POST(req, { params: Promise.resolve({ id: VISIT }) });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: { id: DOCTOR, email: 'doc@test.dev', practiceId: 'p1' },
  });
  // A CLINICIAN by default — these specs test the attestation/E-M gates, not
  // the role gate, so the role must not be what refuses them.
  mocks.userFindUnique.mockResolvedValue({ practiceRole: 'CLINICIAN' });
  mocks.findUnique.mockResolvedValue(visitRow());
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.rxOverrideFindMany.mockResolvedValue([]);
  mocks.criticalWarningRefs.mockReturnValue([]);
  mocks.computeDisplayedEmCode.mockResolvedValue('99214');
  mocks.loadVisitExportData.mockResolvedValue({
    clinicianName: 'Dr. Test',
    patientName: 'P',
    signedAt: new Date('2026-06-12T11:00:00.000Z'),
    createdAt: new Date('2026-06-12T09:00:00.000Z'),
  });
});

// ── THE THIRD REFUSAL CLASS ─────────────────────────────────────────────────
describe('sign gate — the attestation is a SERVER term (2026-08-02)', () => {
  it('REFUSES 400 ATTESTATION_REQUIRED when no attestation is sent', async () => {
    // The gate used to live only in the UI. A second sign control shipped that
    // did not count it, so a signature could pass it with no refusal and no
    // audit row — measured on production. This is that hole, closed.
    const res = await call({ destinations: [], attestation: undefined });
    expect(res.status).toBe(400);
    const body = res.body as unknown as { ok: boolean; code: string; error: string };
    expect(body.ok).toBe(false);
    expect(body.code).toBe('ATTESTATION_REQUIRED');
    expect(body.error).toMatch(/attest/i);
  });

  it('writes the SIGN_BLOCKED_NO_ATTESTATION audit row on the refusal', async () => {
    await call({ destinations: [], attestation: undefined });
    const rows = mocks.logAudit.mock.calls.map((c) => c[0] as { action: string; success?: boolean; errorCode?: string });
    const row = rows.find((r) => r.action === 'SIGN_BLOCKED_NO_ATTESTATION');
    expect(row, `no refusal row; saw ${rows.map((r) => r.action).join(', ') || '(none)'}`).toBeTruthy();
    expect(row!.success).toBe(false);
    expect(row!.errorCode).toBe('ATTESTATION_REQUIRED');
  });

  it('DOES NOT SIGN on the refusal — the status never flips', async () => {
    await call({ destinations: [], attestation: undefined });
    // `updateMany` is the READY→SIGNED writer in this route.
    const wrote = mocks.updateMany.mock.calls.some((c) =>
      JSON.stringify(c[0] ?? {}).includes('SIGNED'),
    );
    expect(wrote, 'a refused sign still wrote SIGNED').toBe(false);
  });

  it('POSITIVE CONTROL — the SAME request WITH an attestation is not refused for this reason', async () => {
    // Without this, the three assertions above would pass just as well against
    // a route that refused everything.
    const res = await call({ destinations: [] });
    const body = res.body as unknown as { code?: string };
    expect(body.code).not.toBe('ATTESTATION_REQUIRED');
  });

  it('a malformed attestation is NOT an attestation — acknowledged must be literal true', async () => {
    const res = await call({ destinations: [], attestation: { acknowledged: false } });
    expect(res.status).toBe(400);
  });
});

describe('sign gate — unacknowledged E/M change blocks (fail-closed)', () => {
  it('REJECTS 400 { ok:false, error } when an unacknowledged change exists and no ack is in the request', async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ emPendingChange: PENDING }));

    const res = await call({ destinations: [] });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error).toBe(BLOCK_ERROR);
    expect(body.code).toBe('EM_CHANGE_UNACKNOWLEDGED');
    expect(body.pendingEmChange).toEqual({ from: '99213', to: '99214' });

    // Fail-closed: the READY→SIGNED transition never ran.
    expect(mocks.updateMany).not.toHaveBeenCalled();

    const blocked = mocks.logAudit.mock.calls
      .map((c) => c[0])
      .find((c) => c.action === 'EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE');
    expect(blocked).toBeDefined();
    expect(blocked.success).toBe(false);
    expect(blocked.metadata).toEqual({
      from: '99213',
      to: '99214',
      cause: 'suggestion_adopted',
    });
  });

  it('REJECTS a STALE acknowledgement — the echo must match the recorded {from, to} exactly', async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ emPendingChange: PENDING }));

    const res = await call({
      destinations: [],
      acknowledgedEmChange: { from: '99212', to: '99214' },
    });
    expect(res.status).toBe(400);
    expect((await res.json()).code).toBe('EM_CHANGE_UNACKNOWLEDGED');
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it('a malformed-but-present record fails CLOSED (unknown sentinel still demands confirmation)', async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({ emPendingChange: { bogus: true } })
    );

    const res = await call({ destinations: [] });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.pendingEmChange).toEqual({ from: 'unknown', to: 'unknown' });
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe('sign gate — a change landing BETWEEN the gate and the write', () => {
  // The source gate next door asserts the STRUCTURE that makes this
  // impossible. This asserts the BEHAVIOUR: the route refuses, signs nothing,
  // and refuses with the code the confirm card already renders.
  it('REFUSES when the transaction re-read finds a change the gate never judged', async () => {
    mocks.findUnique
      // the gate sees a clean visit — nothing to acknowledge
      .mockResolvedValueOnce(visitRow({ emPendingChange: null }))
      // …and a doctor moves the level while the signature is in flight
      .mockResolvedValueOnce(
        visitRow({
          emPendingChange: {
            from: '99213',
            to: '99215',
            cause: 'doctor_override',
            at: '2026-06-12T10:30:00.000Z',
          },
        })
      )
      .mockResolvedValue({
        signedAt: new Date('2026-06-12T11:00:00.000Z'),
        status: TranscribeVisitStatus.SIGNED,
      });

    const res = await call({ destinations: [] });

    expect(res.status).toBe(409);
    const body = await res.json();
    expect(body.code).toBe('EM_CHANGE_UNACKNOWLEDGED');
    expect(body.pendingEmChange).toEqual({ from: '99213', to: '99215' });
    // ⚠️ THE LOAD-BEARING ARM: nothing was signed. A refusal that still wrote
    // the signature would be the defect wearing a 409.
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(
      mocks.logAudit.mock.calls.some(
        (c: unknown[]) =>
          (c[0] as { action?: string })?.action ===
          'EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE'
      )
    ).toBe(true);
  });
});

describe('sign gate — explicit acknowledgement signs + leaves the trail', () => {
  it('signs with a matching ack: record MARKED acknowledged in the same update, VISIT_SIGNED metadata carries emChangeAcknowledged', async () => {
    mocks.findUnique
      .mockResolvedValueOnce(visitRow({ emPendingChange: PENDING }))
      // F5-h RESIDUAL: the signature write RE-READS the visit inside its own
      // transaction, so the gate that judged the change and the write that
      // freezes it see ONE snapshot. That is a second read of the same row,
      // and a mock answering the entry read `Once` handed the transaction the
      // POST-SIGN shape instead — which carries no `emPendingChange`, so the
      // acknowledgement write was silently skipped.
      .mockResolvedValueOnce(visitRow({ emPendingChange: PENDING }))
      .mockResolvedValue({
        signedAt: new Date('2026-06-12T11:00:00.000Z'),
        status: TranscribeVisitStatus.SIGNED,
      });

    const res = await call({
      destinations: [],
      acknowledgedEmChange: { from: '99213', to: '99214' },
    });
    expect(res.status).toBe(200);

    expect(mocks.updateMany).toHaveBeenCalledTimes(1);
    const args = mocks.updateMany.mock.calls[0][0];
    expect(args.where).toEqual({
      id: VISIT,
      // ⚠️ T5-W — the sign write is practice-scoped now. This assertion uses
      // toEqual on purpose: an objectContaining would have passed silently while
      // the tenancy predicate was absent, which is the whole failure the scoping
      // exists to prevent.
      practiceId: 'p1',
      status: TranscribeVisitStatus.READY,
    });
    expect(args.data.status).toBe(TranscribeVisitStatus.SIGNED);
    // MARKED, not cleared — the row keeps the forensic record.
    expect(args.data.emPendingChange).toEqual({
      ...PENDING,
      acknowledgedAt: expect.any(String),
    });

    const signed = mocks.logAudit.mock.calls
      .map((c) => c[0])
      .find((c) => c.action === 'VISIT_SIGNED');
    expect(signed).toBeDefined();
    expect(signed.metadata.emChangeAcknowledged).toEqual({
      from: '99213',
      to: '99214',
    });
    // No block audit on the success path.
    expect(
      mocks.logAudit.mock.calls
        .map((c) => c[0])
        .find((c) => c.action === 'EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE')
    ).toBeUndefined();
  });

  it('no recorded change → signs without an ack, never touches emPendingChange, no acknowledgement metadata', async () => {
    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);

    const args = mocks.updateMany.mock.calls[0][0];
    expect('emPendingChange' in args.data).toBe(false);

    const signed = mocks.logAudit.mock.calls
      .map((c) => c[0])
      .find((c) => c.action === 'VISIT_SIGNED');
    expect(signed).toBeDefined();
    expect('emChangeAcknowledged' in signed.metadata).toBe(false);
  });

  it('an already-ACKNOWLEDGED record does not gate (it was confirmed when recorded sign happened)', async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        emPendingChange: {
          ...PENDING,
          acknowledgedAt: '2026-06-12T10:30:00.000Z',
        },
      })
    );

    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);
    expect('emPendingChange' in mocks.updateMany.mock.calls[0][0].data).toBe(
      false
    );
  });

  it('already-SIGNED visit (re-deliver path) skips the gate even with an unacknowledged record', async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        status: TranscribeVisitStatus.SIGNED,
        signedAt: new Date('2026-06-11T11:00:00.000Z'),
        emPendingChange: PENDING,
      })
    );

    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);
    // Deliver-only: no READY→SIGNED transition attempted.
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe('sign — E/M parity freeze (#315 obs#2): the confirmed displayed level is persisted as the authoritative billing code', () => {
  const EM_BLOB = {
    em: { code: '99213', description: 'Established, low', reasoning: { problems: [], data: '', risk: '' }, evidence_quote: '' },
  };

  it('freezes cptCodes.em.signedCode = computeDisplayedEmCode(signedSoap) in the SAME READY→SIGNED update; raw em.code preserved', async () => {
    mocks.computeDisplayedEmCode.mockResolvedValue('99214');
    mocks.findUnique
      .mockResolvedValueOnce(
        visitRow({ emPendingChange: PENDING, cptCodes: EM_BLOB, icdCodes: null })
      )
      .mockResolvedValue({ signedAt: new Date(), status: TranscribeVisitStatus.SIGNED });

    const res = await call({ destinations: [], acknowledgedEmChange: { from: '99213', to: '99214' } });
    expect(res.status).toBe(200);

    const data = mocks.updateMany.mock.calls[0][0].data;
    // signedCode === the acknowledged TO-level → printed === confirmed.
    expect(data.cptCodes.em.signedCode).toBe('99214');
    expect(data.cptCodes.em.signedCode).toBe(PENDING.to);
    // The raw L7b suggestion is preserved for provenance.
    expect(data.cptCodes.em.code).toBe('99213');
    // It rode the SAME atomic transition that flips status → SIGNED.
    expect(data.status).toBe(TranscribeVisitStatus.SIGNED);
  });

  it('an OVERRIDDEN visit freezes the override level (computeDisplayedEmCode returns override ?? engine)', async () => {
    mocks.computeDisplayedEmCode.mockResolvedValue('99215');
    mocks.findUnique
      .mockResolvedValueOnce(
        visitRow({
          cptCodes: { em: { ...EM_BLOB.em, override: { code: '99215', overriddenAt: 'x' } } },
        })
      )
      .mockResolvedValue({ signedAt: new Date(), status: TranscribeVisitStatus.SIGNED });

    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);
    expect(mocks.updateMany.mock.calls[0][0].data.cptCodes.em.signedCode).toBe('99215');
  });

  it('FAIL-SAFE: a scoring error never blocks signing — no cptCodes write, status still flips', async () => {
    mocks.computeDisplayedEmCode.mockRejectedValue(new Error('judge down'));
    mocks.findUnique
      .mockResolvedValueOnce(visitRow({ cptCodes: EM_BLOB }))
      .mockResolvedValue({ signedAt: new Date(), status: TranscribeVisitStatus.SIGNED });

    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);
    const data = mocks.updateMany.mock.calls[0][0].data;
    expect(data.status).toBe(TranscribeVisitStatus.SIGNED);
    expect('cptCodes' in data).toBe(false);
  });

  it('a visit with NO em block does not compute or write a signed code (backward compatible)', async () => {
    mocks.findUnique
      .mockResolvedValueOnce(visitRow({ cptCodes: { procedures: [] } }))
      .mockResolvedValue({ signedAt: new Date(), status: TranscribeVisitStatus.SIGNED });

    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);
    expect(mocks.computeDisplayedEmCode).not.toHaveBeenCalled();
    expect('cptCodes' in mocks.updateMany.mock.calls[0][0].data).toBe(false);
  });
});
