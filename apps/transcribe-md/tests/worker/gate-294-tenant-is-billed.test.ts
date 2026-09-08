// ============================================================================
// GATE — #294: THE TENANT IS BILLED.
// ----------------------------------------------------------------------------
// ⚠️ ONE LINE FED TWENTY-FIVE SITES WITH THE WRONG PRACTICE.
// `worker.ts` bound `const practiceId = visit.user.practiceId` — the AUTHOR's
// practice — and handed it to admission, to every AI layer's usage metering, to
// the audit rows and to the charge. `TranscribeVisit.practiceId` is a different
// column, derived from the PATIENT, and the schema comment on it says exactly
// when the two diverge:
//
//     "A locum from practice B seeing a patient of practice A creates a note
//      in A. Deriving from `user.practiceId` would file it in B."
//
// So for a locum visit the pipeline admitted against B's balance, metered every
// vendor call to B, filed the audit under B, and CHARGED B for a note living in
// A's chart.
//
// ⚠️ AND NO TEST COULD HAVE SEEN IT, WHICH THE FILE ITSELF SAYS. `worker.ts`'s
// comment above the admission call records a stuck-chart incident and its cause:
// *"THE JOIN BETWEEN THEM WAS NEVER EXERCISED, because no unit test runs
// `processVisit`"* — two individually-correct billing steps with the defect in
// the seam. This file is that missing harness, and #294 is what finally needed
// it.
//
// ⚠️ THE FIXTURE GIVES THREE IDENTITIES THREE DIFFERENT VALUES — ruling #260. A
// fixture where the tenant, the author and the author's practice all agree
// cannot witness them being confused, and that agreement is exactly why this
// survived: production holds 58/58 visits where author practice == tenant.
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

const TENANT = 'practice-A-owns-the-chart';
const AUTHOR = 'user-locum-visiting-from-B';
const AUTHOR_PRACTICE = 'practice-B-the-locums-own';
const VISIT = 'visit-of-A-patient';

const h = vi.hoisted(() => ({
  admit: vi.fn(async (..._a: unknown[]) => undefined),
  charge: vi.fn(async (..._a: unknown[]) => ({ ok: true })),
  observe: vi.fn(async (..._a: unknown[]) => undefined),
  audit: vi.fn(async (..._a: unknown[]) => undefined),
  visitFindUnique: vi.fn(),
  visitUpdate: vi.fn(async (..._a: unknown[]) => ({})),
  visitUpdateMany: vi.fn(async (..._a: unknown[]) => ({ count: 1 })),

}));

// ── the pipeline is stubbed; the SUBJECT is which practice reaches the seams ──
vi.mock('bullmq', () => ({
  Worker: class {
    on() {
      return this;
    }
    close() {
      return Promise.resolve();
    }
  },
  Queue: class {},
}));
// ⚠️ PERMISSIVE BY DEFAULT, EXPLICIT WHERE THE FIXTURE MATTERS. Naming every
// model the pipeline touches would be a second, hand-kept inventory that goes
// stale the day a layer reads a new table — the shape #289 spent a whole ruling
// removing. Anything not named answers with an empty result.
vi.mock('@meddoc/db', () => {
  // The default answer is shaped by the METHOD NAME, because "null for
  // everything" broke on the first `.reduce` — a permissive stub still has to
  // return the KIND of thing Prisma returns.
  const model = () =>
    new Proxy(
      {},
      {
        get: (_t, k: string) => async () => {
          if (k === 'findMany') return [];
          if (k === 'count') return 0;
          if (k.endsWith('Many')) return { count: 0 };
          if (k.startsWith('find')) return null;
          return {};
        },
      },
    );
  const base: Record<string, unknown> = {
    transcribeVisit: {
      findUnique: (...a: unknown[]) => h.visitFindUnique(...(a as [])),
      findFirst: async () => null,
      update: (...a: unknown[]) => h.visitUpdate(...(a as [])),
      updateMany: (...a: unknown[]) => h.visitUpdateMany(...(a as [])),
    },
    user: { findUnique: async () => ({ email: 'locum@b.example' }) },
    $executeRaw: async () => 0,
    $executeRawUnsafe: async () => 0,
    $queryRaw: async () => [],
    $transaction: async (fn: unknown) =>
      typeof fn === 'function' ? (fn as (tx: unknown) => unknown)(client) : [],
  };
  const client: unknown = new Proxy(base, {
    get: (t, k: string) => (k in t ? (t as Record<string, unknown>)[k] : model()),
  });
  return { default: client, Prisma: { DbNull: null, JsonNull: null } };
});
// ⚠️ THE REAL MODULE, WITH THREE FUNCTIONS OVERRIDDEN. Replacing `@meddoc/ai`
// wholesale removed `delimiterSystemSuffix` from every other consumer and the
// template-twin module graph failed at import — a mock that breaks the tree it
// is supposed to be measuring.
vi.mock('@meddoc/ai', async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  admitVisitOrThrow: (...a: unknown[]) => h.admit(...(a as [])),
  chargeVisitUsage: (...a: unknown[]) => h.charge(...(a as [])),
  observeFailedVisitUsage: (...a: unknown[]) => h.observe(...(a as [])),
}));
vi.mock('@/lib/audit', () => ({ logAudit: (...a: unknown[]) => h.audit(...(a as [])) }));
vi.mock('@/lib/minio', () => ({ ensureBucket: vi.fn(async () => undefined) }));
vi.mock('@/lib/cleanup-heartbeat', () => ({ recordCleanupHeartbeat: vi.fn() }));
vi.mock('@/lib/queue', () => ({
  QUEUE_NAME: 'q',
  JOB_PROCESS_VISIT: 'process-visit',
  CLEANUP_QUEUE_NAME: 'cq',
  JOB_MINIO_ORPHAN_CLEANUP: 'a',
  JOB_STALE_VISIT_CLEANUP: 'b',
  JOB_RETENTION_SWEEP: 'c',
  JOB_STUCK_VISIT_WATCHDOG: 'd',
  JOB_AUTO_CERTIFY_TWIN: 'e',
  enqueueDlq: vi.fn(),
  getSharedRedisConnection: () => ({}),
  getCleanupQueue: () => ({ add: vi.fn(), upsertJobScheduler: vi.fn() }),
}));

// ── THE PIPELINE IS STUBBED; THE SUBJECT IS WHICH PRACTICE REACHES THE SEAMS ──
// Every layer returns the smallest shape `worker.ts` consumes. None of them is
// what this file measures — the arms below read the arguments handed to
// `admitVisitOrThrow` and `chargeVisitUsage`, which sit either side of the
// whole pipeline and both read the ONE derivation #294 moved.
//
// ⚠️ EACH MOCK KEEPS THE MODULE'S REAL EXPORTS and overrides one function.
// Replacing a module wholesale removed a symbol other consumers import and the
// module graph failed at import — a mock that breaks the tree it measures.
const actual = <T,>(orig: () => Promise<T>) => orig();
vi.mock('@/worker/layers/03-extract-entities', async (orig) => ({
  ...(await actual(orig as never) as Record<string, unknown>),
  runLayer3ExtractEntities: vi.fn(async () => ({
    entities: { chief_complaint: null },
    contextText: 'context',
  })),
}));
vi.mock('@/worker/layers/04-generate-soap', async (orig) => ({
  ...(await actual(orig as never) as Record<string, unknown>),
  runLayer4GenerateSoap: vi.fn(async () => 'S: draft\nO: draft\nA: draft\nP: draft'),
}));
vi.mock('@/worker/layers/05-self-critique', async (orig) => ({
  ...(await actual(orig as never) as Record<string, unknown>),
  runLayer5SelfCritique: vi.fn(async () => ({ issues: [], unfixableCriticals: [] })),
}));
vi.mock('@/worker/layers/06-polish', async (orig) => ({
  ...(await actual(orig as never) as Record<string, unknown>),
  runLayer6Polish: vi.fn(async () => ({
    soapFinal: 'S: final\nO: final\nA: final\nP: final',
    fabricationRejected: false,
  })),
}));
for (const m of [
  '@/worker/layers/07a-icd-coding',
  '@/worker/layers/07b-cpt-coding',
  '@/worker/layers/07c-rx-drafting',
  '@/worker/layers/07d-referrals',
  '@/worker/layers/07e-patient-summary',
]) {
  vi.doMock(m, async (orig) => ({
    ...(await actual(orig as never) as Record<string, unknown>),
    ...Object.fromEntries(
      Object.keys(await actual(orig as never) as Record<string, unknown>)
        .filter((k) => k.startsWith('runLayer7'))
        .map((k) => [k, vi.fn(async () => ({}))]),
    ),
  }));
}
vi.mock('@/lib/em-coding/llm-mdm', () => ({ judgeMdm: vi.fn(async () => ({})) }));
vi.mock('@/worker/template-twin-fill-step', () => ({
  runTemplateTwinFillStep: vi.fn(async () => ({ status: 'skipped', reason: 'flag_off' })),
}));
vi.mock('@/worker/note-templates/resolve-active-template', () => ({
  resolveActiveTemplate: vi.fn(async () => null),
}));

// ⚠️ ONE BUDGET, DECLARED ONCE. Each arm imports `@/worker` — a 53-import module
// graph — and drives the whole pipeline: ~3.2s warm on this box, and it blew
// vitest's 5s default in a full-suite run at load 23. A default clock that only
// fails when the machine is busy is the `gate-lens-sandbox` lesson wearing
// different clothes: the arm is not faster for having a tighter one.
const PIPELINE_BUDGET_MS = 60_000;

describe('#294 — the locum visit is admitted and charged to the CHART', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    h.visitFindUnique.mockResolvedValue({
      id: VISIT,
      userId: AUTHOR,
      // ⚠️ THE TENANT — the visit's own column, A. The author belongs to B.
      practiceId: TENANT,
      user: { practiceId: AUTHOR_PRACTICE },
      inputMode: 'text_notes',
      rawTextInput: 'patient reports right calf swelling',
      status: 'QUEUED',
      specialty: null,
      interpreterMode: null,
      noteTemplateId: null,
      createdAt: new Date('2026-09-08T00:00:00.000Z'),
      patient: { dateOfBirth: null, weightKg: null, allergies: null },
    });
  });

  const run = async () => {
    const { processVisit } = await import('@/worker');
    await processVisit({
      name: 'process-visit',
      id: 'job-1',
      data: { visitId: VISIT },
      attemptsMade: 0,
      opts: { attempts: 3 },
    } as never);
  };

  it('⚠️ ADMISSION IS ASKED ABOUT THE TENANT, never the locum’s own practice', async () => {
    await run();

    // POSITIVE CONTROL FIRST: a run that never reached admission proves nothing,
    // and every assertion below is satisfied by a pipeline that fell over early.
    expect(h.admit, 'admission was never reached — the arm is vacuous').toHaveBeenCalled();

    const arg = h.admit.mock.calls[0][0] as { practiceId?: string };
    expect(arg.practiceId).toBe(TENANT);
    expect(
      arg.practiceId,
      'admitted against the AUTHOR’s practice — a locum’s visit would draw ' +
        'down the wrong balance, and refuse when the wrong practice is out of money',
    ).not.toBe(AUTHOR_PRACTICE);
  }, PIPELINE_BUDGET_MS);

  it('⚠️ THE CHARGE LANDS ON THE TENANT — the practice that owns the chart pays', async () => {
    await run();

    // POSITIVE CONTROL: charging is on the SUCCESS path only, so an arm that
    // never got there proves nothing — and every earlier version of this file
    // stopped somewhere in the pipeline while the admission arm stayed green.
    expect(
      h.charge,
      'the pipeline never reached the charge — the arm is vacuous',
    ).toHaveBeenCalled();

    const arg = h.charge.mock.calls[0][0] as { practiceId?: string; visitId?: string };
    expect(arg.visitId).toBe(VISIT);
    expect(arg.practiceId).toBe(TENANT);
    expect(
      arg.practiceId,
      'the LOCUM’s practice was charged for a note that lives in another ' +
        'practice’s chart — B pays for A’s visit',
    ).not.toBe(AUTHOR_PRACTICE);
  }, PIPELINE_BUDGET_MS);

  it('⚠️ NO SEAM SEES THE AUTHOR’S PRACTICE — the whole run, not two call sites', async () => {
    await run();

    // #294 moved ONE derivation feeding twenty-five sites. Two arms pin the two
    // the ruling names; this one says the value never appears ANYWHERE a
    // practice is passed, so a twenty-sixth site added later cannot quietly
    // take the author's.
    const everyCall = [
      ...h.admit.mock.calls,
      ...h.charge.mock.calls,
      ...h.audit.mock.calls,
      ...h.observe.mock.calls,
    ];
    expect(everyCall.length, 'nothing was called — the arm is vacuous').toBeGreaterThan(1);
    for (const call of everyCall) {
      const seen = JSON.stringify(call ?? null);
      expect(
        seen.includes(AUTHOR_PRACTICE),
        `the author's practice reached a seam: ${seen.slice(0, 160)}`,
      ).toBe(false);
    }
    // NON-VACUITY: the fixture really does carry it, so "absent" is a finding
    // about the code rather than about a fixture that never had the value.
    expect(
      JSON.stringify(await h.visitFindUnique.mock.results[0].value).includes(AUTHOR_PRACTICE),
      'the fixture does not carry the author practice at all — the arm above ' +
        'cannot fail and proves nothing',
    ).toBe(true);
  }, PIPELINE_BUDGET_MS);
});
