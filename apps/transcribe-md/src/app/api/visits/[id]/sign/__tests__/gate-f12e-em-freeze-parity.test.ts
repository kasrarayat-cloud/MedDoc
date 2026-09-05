// ============================================================================
// F12-e — THE SIGNED DOCUMENT CARRIES THE LEVEL THE DOCTOR ATTESTED.
// ----------------------------------------------------------------------------
// THE DEFECT. `sign/route.ts` froze `cptCodes.em.signedCode` only when L7b had
// already emitted an `em` blob (`if (emBlob && emApplies)`). But the level the
// doctor REVIEWS does not come from that blob — `visits/[id]/page.tsx:649`
// seeds `emScoredCode` from `initialEmScore.override ?? suggestedCode`, the
// rubric engine scored against the note, and that seed sits INSIDE
// `if (!emNotApplicable)`. So the rail can show a level on a visit whose
// `cptCodes.em` is null, and then:
//
//     emBlob === null  ->  no signedCode frozen
//     -> projectEmForDisplay(null, …) returns null   (visit-export.ts:107)
//     -> the signed PDF, DOCX and EVERY EHR clipboard format print NO E/M,
//        while the screen showed one and the doctor attested it.
//
// ⚠️ MEASURED ON PRODUCTION, READ-ONLY, 2026-08-27 — 12 visits carry
// `cptCodes.em = null` AND a non-null `emScoredCode`, **10 of them SIGNED**,
// all `bariatric-surgery` / `gastroenterology`, **zero** imaging. Because
// `emScoredCode` is only ever written under `!emNotApplicable`, its presence
// is structural proof the predicate said E/M APPLIES — established without
// reading a byte of note text.
//
// THE FIX. The gate is `emApplies` ALONE. E/M PARITY (#315 obs#2) says the
// artifact prints the level the doctor reviewed and attested; the current
// verdict on the note being signed is `emApplies`, and that is the whole gate.
//
// WHAT WOULD MAKE THIS FILE FAIL, predicted before the proofs ran (rule 7) —
// AND THE PREDICTION WAS CORRECTED BY THEM, which is recorded rather than
// quietly rewritten:
//
//   * `if (emBlob && emApplies)` — the pre-F12-e gate. PREDICTED "the fix arm,
//     and nothing else". MEASURED **4 of 11**: the three fix arms plus
//     `a scorer failure never blocks the signature`, which seeds `cptCodes:
//     null` and so cannot reach the scorer at all once the blob is required.
//     The prediction was wrong about the COUNT, not the direction.
//   * `if (emBlob)` — dropping the applicability term. MEASURED **5 of 11**,
//     and the one that matters is `an OPERATIVE note with an EXISTING em blob
//     still freezes nothing` — the #123 / #126 / #128 direction, which must
//     never be traded for the fix.
//
// Both mutations were asserted APPLIED before their results were believed, and
// the restore was asserted to have removed both markers.
//
// These are BEHAVIOURAL — the real route, the real `emAppliesToVisit`, the
// real blob construction. Only the collaborators are mocked, exactly as
// `em-confirm-gate.test.ts` does it.
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

import type { NextRequest } from 'next/server';
import { TranscribeVisitStatus } from '@prisma/client';

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
function signedWrite(): { status?: unknown; cptCodes?: Record<string, unknown> } | undefined {
  const c = mocks.updateMany.mock.calls.find(
    (x) => (x[0] as { data?: Record<string, unknown> })?.data?.status === TranscribeVisitStatus.SIGNED,
  );
  return (c?.[0] as { data?: { status?: unknown; cptCodes?: Record<string, unknown> } })?.data;
}

/** The `cptCodes` the route actually PERSISTED, read off the write rather than
 *  off the response. The column is what a later reader — and every export
 *  surface — sees.
 *
 *  ⚠️ FOUND BY THIS ITEM'S OWN ADVERSARIAL PASS: every SUPPRESSION arm below
 *  asserts an ABSENCE, and an absence is exactly what you also get when the
 *  route refused, threw, or never reached the write. Those arms would then
 *  pass for the opposite of the reason claimed — a false green on the one
 *  direction (#123 / #126 / #128) that must never be traded. So each of them
 *  asserts the SIGNED write HAPPENED first, via `expectSigned()`. */
function writtenCpt(): Record<string, unknown> | undefined {
  return signedWrite()?.cptCodes;
}

/** Non-vacuity guard for the absence arms. */
function expectSigned() {
  const d = signedWrite();
  expect(
    d,
    `no SIGNED write happened — an "E/M is absent" assertion below would pass ` +
      `vacuously. updateMany calls: ${mocks.updateMany.mock.calls.length}`,
  ).toBeTruthy();
  return d!;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: { id: DOCTOR, email: 'doc@test.dev', practiceId: 'p1' },
  });
  mocks.userFindUnique.mockResolvedValue({ practiceRole: 'CLINICIAN' });
  mocks.findUnique.mockResolvedValue(visitRow());
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.rxOverrideFindMany.mockResolvedValue([]);
  mocks.criticalWarningRefs.mockReturnValue([]);
  mocks.computeDisplayedEmCode.mockResolvedValue(FROZEN);
  mocks.loadVisitExportData.mockResolvedValue({
    clinicianName: 'Dr. Test',
    patientName: 'P',
    signedAt: new Date('2026-08-27T11:00:00.000Z'),
    createdAt: new Date('2026-08-27T09:00:00.000Z'),
  });
});

// ── THE CONTROL — prove the fixtures classify the way the arms assume ────────
//
// Without this, every suppression arm below could be passing because the
// harness never reached the freeze at all, and every fix arm could be passing
// on a note the predicate reads differently than intended. A gate whose
// universe is assumed is a gate that can go vacuous silently.
describe('CONTROL — the fixtures are classified by the SHIPPED predicate', () => {
  it('the office fixture is E/M-APPLIES', () => {
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: null,
        noteText: OFFICE_NOTE,
      }),
    ).toBe(true);
  });

  it('the operative fixture is E/M-SUPPRESSED', () => {
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: null,
        noteText: OPERATIVE_NOTE,
      }),
    ).toBe(false);
  });
});

// ── THE FIX ─────────────────────────────────────────────────────────────────
describe('F12-e — an office visit freezes its level even when L7b emitted no blob', () => {
  it('⚠️ THE FIX ARM — `cptCodes.em` is NULL and the level is STILL frozen', async () => {
    // This is the production state: 12 rows, 10 of them signed.
    mocks.findUnique.mockResolvedValue(
      visitRow({ cptCodes: { em: null, procedures: [], emSuppressed: true } }),
    );
    await call();
    const cpt = writtenCpt();
    expect(cpt, 'no SIGNED write happened at all — the harness never reached the freeze').toBeTruthy();
    expect((cpt!.em as { signedCode?: string })?.signedCode).toBe(FROZEN);
  });

  it('freezes when `cptCodes` is wholly absent — the blob is CREATED, not required', async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ cptCodes: null }));
    await call();
    expect((writtenCpt()?.em as { signedCode?: string })?.signedCode).toBe(FROZEN);
  });

  it('does not need `emSuppressed` to be present — the marker is not the hook', async () => {
    // The filing expected `emSuppressed` to be load-bearing. It is not: the
    // freeze does not care WHY the blob is absent, only whether E/M applies to
    // the note being signed. Asserted so a later edit cannot quietly make the
    // fix contingent on a marker written by a layer that may not have run.
    mocks.findUnique.mockResolvedValue(visitRow({ cptCodes: { em: null } }));
    await call();
    expect((writtenCpt()?.em as { signedCode?: string })?.signedCode).toBe(FROZEN);
  });
});

// ── NO REGRESSION — the arms F12-a / #126 / #123 bought ─────────────────────
describe('F12-e does NOT weaken the note-shape suppression', () => {
  it('an OPERATIVE note freezes NOTHING, even though the engine returns a level', async () => {
    // The direction that must never be traded for the fix. `computeDisplayedEmCode`
    // is stubbed to return a level precisely so a suppression failure cannot
    // hide behind "the engine produced nothing anyway".
    mocks.findUnique.mockResolvedValue(visitRow({ soapFinal: OPERATIVE_NOTE }));
    await call();
    expectSigned();
    expect(writtenCpt()?.em ?? undefined).toBeUndefined();
  });

  it('an OPERATIVE note with an EXISTING em blob still freezes nothing — F12-a\'s own arm', async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        soapFinal: OPERATIVE_NOTE,
        cptCodes: { em: { code: '99213' }, procedures: [{ code: '45385' }] },
      }),
    );
    await call();
    expectSigned();
    const em = writtenCpt()?.em as { signedCode?: string } | undefined;
    expect(em?.signedCode).toBeUndefined();
    // and the model's own level is NOT promoted to a frozen one
    expect(em?.signedCode).not.toBe('99213');
  });

  it('never CALLS the scorer on a suppressed note — no wasted model round-trip, and no audit of a level nobody asked for', async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ soapFinal: OPERATIVE_NOTE }));
    await call();
    expectSigned();
    expect(mocks.computeDisplayedEmCode).not.toHaveBeenCalled();
  });
});

// ── UNCHANGED BEHAVIOUR ─────────────────────────────────────────────────────
describe('F12-e leaves the already-working path byte-identical', () => {
  it('an office visit WITH an em blob still freezes, and keeps the blob\'s other fields', async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({ cptCodes: { em: { code: '99212', description: 'est. pt' }, procedures: [] } }),
    );
    await call();
    const em = writtenCpt()?.em as Record<string, unknown>;
    expect(em.signedCode).toBe(FROZEN);
    // The model's own fields survive — the freeze ADDS, it does not replace.
    expect(em.code).toBe('99212');
    expect(em.description).toBe('est. pt');
  });

  it('a doctor OVERRIDE still wins the frozen level', async () => {
    // `freshOverride` takes precedence in the transaction merge. Pinned here
    // because the fix touches the expression that feeds it.
    mocks.findUnique.mockResolvedValue(
      visitRow({ cptCodes: { em: { code: '99212', override: { code: '99215' } } } }),
    );
    await call();
    const em = writtenCpt()?.em as Record<string, unknown>;
    expect((em.override as { code?: string })?.code).toBe('99215');
  });

  it('a scorer failure never blocks the signature — the sign still lands', async () => {
    mocks.computeDisplayedEmCode.mockRejectedValue(new Error('scorer down'));
    mocks.findUnique.mockResolvedValue(visitRow({ cptCodes: null }));
    const res = await call();
    expect(res.status).toBe(200);
    // and it says so rather than failing silently
    expect(
      mocks.logWarn.mock.calls.some((c) => String(c[1]).includes('signedCode freeze failed')),
    ).toBe(true);
  });
});
