// ============================================================================
// GATE — FOUNDATION B8 step 2: the pipeline seam
// ----------------------------------------------------------------------------
// Ruling 90(e), verbatim: "B8 is where money is assessed, so the debit and the
// block belong in ONE CHANGE AND IN THAT ORDER" — and, on the hazard it moved
// here deliberately: "whoever wires this must solve the ordering, and CANNOT DO
// IT BY ACCIDENT."
//
// So this gate is mostly about ORDERING and about DEFAULTS, not about
// arithmetic — B8 step 1's gate already owns the arithmetic.
//
// ⚠️ WHAT WOULD MAKE THIS GATE FAIL, SAID BEFORE IT WAS MADE TO FAIL:
//
//   · `loadVisitChargeableUsage` reading before the meter has settled, so a
//     visit is charged for fewer rows than it consumed  (arm 3)
//   · `drainApiUsage` hanging forever the first time a usage write throws,
//     turning a best-effort meter into a pipeline halt                (arm 4)
//   · the `timestamp` → `createdAt` mapping being dropped or spread   (arm 5)
//   · `billingEnforced` reading `!== 'false'`, so an UNSET variable means
//     ENFORCED and every visit blocks on a container nobody configured (arm 1)
//   · either seam doing database work while the flag is off           (arm 2)
//   · `chargeVisitUsage` throwing, which would fail a READY visit over a
//     billing write                                                   (arm 7)
//   · `categorizeError` classifying the refusal by MESSAGE TEXT rather than
//     structurally, so a reworded message silently changes retry behaviour
//                                                                     (arm 8)
//   · the loader growing its own copy of the mock / provider exclusions, which
//     would then drift from the ruled ones in `priceUsageRows`        (arm 9)
//
// ⚠️ ONE PROOF IS NOT IN THIS FILE, AND IT IS THE `createdAt` ONE. That defect
// is caught by `tsc`, not by vitest, so it was mutation-proved against the type
// checker instead: replacing `createdAt: row.timestamp` with `timestamp:
// row.timestamp` produces
//
//     billing-usage-source.ts(128,3): error TS2322 … Property 'createdAt' is
//     missing in type … but required in type 'ChargeableUsageRow'
//
// and the source was restored. Arm 5 below is the behavioural half — it asserts
// the value actually travels — because the type check alone cannot see a
// mapping that compiles and carries the wrong FIELD's value.
//
// ⚠️ AND WHAT THIS GATE DOES NOT CLAIM. It never touches a real ledger, a real
// price table or a real practice. `commitVisitCharge` refuses off production by
// ruling 90(c), so the debit's success path is UNPROVEN here and is unprovable
// anywhere a test may run — arm 7 proves only that the refusal is absorbed
// rather than thrown. That is stated rather than glossed: the end-to-end debit
// has never executed, in any environment, and this item does not change that.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// A stub `@meddoc/db` that actually STORES, so the ordering claims are real.
// ---------------------------------------------------------------------------

interface StoredRow {
  id: string;
  visitId: string | null;
  provider: string;
  modelName: string | null;
  unitsSource: string;
  timestamp: Date;
  audioSeconds: number | null;
  inputTokens: number | null;
  outputTokens: number | null;
  cacheReadInputTokens: number | null;
  cacheCreationInputTokens: number | null;
}

const store: StoredRow[] = [];
/** When set, the next `apiUsageEvent.create` rejects. Arm 4. */
let createRejectsWith: Error | null = null;
/** Every call the stub received, so "the flag was off and nothing was read"
 *  can be asserted as an ABSENCE rather than assumed. */
const dbCalls: string[] = [];

vi.mock('@meddoc/db', () => {
  const client = {
    apiUsageEvent: {
      create: async ({ data }: { data: Record<string, unknown> }) => {
        dbCalls.push('apiUsageEvent.create');
        if (createRejectsWith) {
          const err = createRejectsWith;
          createRejectsWith = null;
          throw err;
        }
        store.push({
          id: `evt_${store.length + 1}`,
          visitId: (data.visitId as string) ?? null,
          provider: data.provider as string,
          modelName: (data.modelName as string) ?? null,
          unitsSource: data.unitsSource as string,
          timestamp: new Date('2026-08-01T12:00:00Z'),
          audioSeconds: (data.audioSeconds as number) ?? null,
          inputTokens: (data.inputTokens as number) ?? null,
          outputTokens: (data.outputTokens as number) ?? null,
          cacheReadInputTokens: (data.cacheReadInputTokens as number) ?? 0,
          cacheCreationInputTokens: (data.cacheCreationInputTokens as number) ?? 0,
        });
        return { id: `evt_${store.length}` };
      },
      findMany: async ({ where }: { where: { visitId: string } }) => {
        dbCalls.push('apiUsageEvent.findMany');
        return store.filter((r) => r.visitId === where.visitId);
      },
    },
    $queryRawUnsafe: async () => {
      dbCalls.push('$queryRawUnsafe');
      return balanceRows;
    },
    ledgerEntry: {
      create: async () => {
        dbCalls.push('ledgerEntry.create');
        return { id: 'ledger_1' };
      },
    },
  };
  return { __esModule: true, default: client, prisma: client };
});

/** What the balance query returns next. Empty = a zero wallet. */
let balanceRows: Record<string, string>[] = [];

import {
  drainApiUsage,
  logApiUsage,
  pendingApiUsageWrites,
  type UsageEvent,
} from '../api-usage';
import {
  BILLING_ENFORCED_ENV,
  BillingAdmissionError,
  admitVisitOrThrow,
  billingEnforced,
  chargeVisitUsage,
} from '../billing-pipeline';
import { loadVisitChargeableUsage } from '../billing-usage-source';

const SRC = join(__dirname, '..');

/** Executable source only — prose must never satisfy a code assertion. The
 *  canonical form, byte-identical to `gate-mock-suite-stubs-the-db.test.ts`. */
const strip = (s: string) =>
  s
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//'))
    .join('\n');

function vendorEvent(visitId: string, overrides: Partial<UsageEvent> = {}): UsageEvent {
  return {
    unitsSource: 'vendor',
    provider: 'anthropic',
    operation: 'tm_soap_draft',
    modelName: 'claude-sonnet-4-6',
    inputTokens: 1000,
    outputTokens: 500,
    unitCount: 1500,
    unitType: 'tokens_in',
    unitCostUsd: 0.001,
    totalCostUsd: 0.0015,
    visitId,
    ...overrides,
  };
}

beforeEach(async () => {
  // Drain anything a previous arm left pending, so arms cannot leak into each
  // other through the module-level in-flight set.
  await drainApiUsage();
  store.length = 0;
  dbCalls.length = 0;
  createRejectsWith = null;
  balanceRows = [];
  delete process.env[BILLING_ENFORCED_ENV];
});

// ---------------------------------------------------------------------------
describe('arm 1 — the flag is OPT-IN, and an unset variable is INERT', () => {
  // ⚠️ THE WHOLE ARM EXISTS FOR THE `undefined` CASE. Both idioms are already in
  // this worker (`=== 'true'` and `!== 'false'`), they agree on every value a
  // human would type, and they differ on exactly the one nobody sets: unset.
  // With opt-out semantics, a container that had never heard of this variable
  // would enforce a balance block against wallets that hold nothing — every
  // visit, every doctor.
  it('is false when the variable is absent', () => {
    expect(billingEnforced({})).toBe(false);
  });

  it('is true ONLY for the exact string "true"', () => {
    expect(billingEnforced({ [BILLING_ENFORCED_ENV]: 'true' })).toBe(true);
    for (const v of ['false', 'TRUE', 'True', '1', 'yes', '', ' true']) {
      expect(billingEnforced({ [BILLING_ENFORCED_ENV]: v })).toBe(false);
    }
  });

  it('the shipped default is OFF — asserted on the compose files, not on hope', () => {
    // If a future edit sets this in production's compose, the deploy that does
    // it must be a deliberate one that also lands the promo grant. This arm is
    // what makes that edit visible.
    const root = join(SRC, '..', '..', '..');
    for (const file of ['docker-compose.yml', 'docker-compose.qa.yml']) {
      const text = readFileSync(join(root, file), 'utf8');
      expect(text.includes(`${BILLING_ENFORCED_ENV}=true`)).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
describe('arm 2 — with the flag OFF, neither seam touches the database', () => {
  // Asserted as an ABSENCE of calls rather than as a return value: a seam that
  // read the balance and then discarded the answer would satisfy a
  // return-value assertion perfectly and would still be doing money work on
  // every visit in production.
  it('admission reads nothing', async () => {
    await expect(admitVisitOrThrow({ practiceId: 'p1' })).resolves.toBeUndefined();
    expect(dbCalls).toEqual([]);
  });

  it('the debit writes nothing and reports that it was skipped', async () => {
    const out = await chargeVisitUsage({ practiceId: 'p1', visitId: 'v1' });
    expect(out).toEqual({ charged: 'skipped_not_enforced' });
    expect(dbCalls).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
describe('arm 3 — THE RACE: the loader waits for the meter', () => {
  // This is the arm ruling 90(e) asked for by name.
  it('a write logged one tick ago is PENDING, and is visible after the drain', async () => {
    logApiUsage(vendorEvent('v-race'));

    // The positive control for the whole arm: if this were already 0, the
    // drain below would be draining nothing and the test would pass while
    // proving nothing at all.
    expect(pendingApiUsageWrites()).toBe(1);
    expect(store).toHaveLength(0);

    await drainApiUsage();

    expect(pendingApiUsageWrites()).toBe(0);
    expect(store).toHaveLength(1);
  });

  it('the LOADER drains by itself — a caller cannot forget', async () => {
    logApiUsage(vendorEvent('v-loader'));
    expect(pendingApiUsageWrites()).toBe(1);

    // No manual drain. If `loadVisitChargeableUsage` did not drain internally,
    // this read would happen before the write landed and return zero rows —
    // which is precisely the silent under-charge.
    const rows = await loadVisitChargeableUsage('v-loader');

    expect(rows).toHaveLength(1);
  });

  it('drains writes that arrive WHILE the drain is awaiting', async () => {
    // `Promise.all` over a snapshot would miss this one; the loop is what
    // catches it, and the pipeline's last stage really can still be metering
    // when finalize begins.
    logApiUsage(vendorEvent('v-late'));
    const draining = drainApiUsage();
    logApiUsage(vendorEvent('v-late'));
    await draining;

    expect(pendingApiUsageWrites()).toBe(0);
    expect(store).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
describe('arm 4 — a FAILED usage write still settles', () => {
  // Without the `finally`, the first refused row would leave a promise in the
  // in-flight set forever and every later `drainApiUsage()` would hang — a
  // best-effort meter converted into a pipeline halt, which is the exact
  // inversion the fire-and-forget shape exists to prevent.
  it('the drain resolves, and does not reject', async () => {
    createRejectsWith = new Error('postgres refused the row');
    logApiUsage(vendorEvent('v-boom'));
    expect(pendingApiUsageWrites()).toBe(1);

    await expect(drainApiUsage()).resolves.toBeUndefined();
    expect(pendingApiUsageWrites()).toBe(0);
    expect(store).toHaveLength(0);
  });

  it('and a later write still drains normally afterwards', async () => {
    createRejectsWith = new Error('transient');
    logApiUsage(vendorEvent('v-boom'));
    await drainApiUsage();

    logApiUsage(vendorEvent('v-ok'));
    await drainApiUsage();
    expect(store).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
describe('arm 5 — the row carries `createdAt`, and it is the timestamp', () => {
  it('maps the column onto the field the pricer reads', async () => {
    logApiUsage(vendorEvent('v-map'));
    const [row] = await loadVisitChargeableUsage('v-map');

    // Not just "is a Date" — `billing-charge.ts:294` passes this to the rate
    // lookup as `at`, so a field that exists but holds the wrong instant
    // prices the call against the wrong period.
    expect(row.createdAt).toBeInstanceOf(Date);
    expect(row.createdAt.toISOString()).toBe('2026-08-01T12:00:00.000Z');
  });

  it('returns only this visit’s rows', async () => {
    logApiUsage(vendorEvent('v-mine'));
    logApiUsage(vendorEvent('v-theirs'));
    const rows = await loadVisitChargeableUsage('v-mine');
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
describe('arm 6 — with the flag ON, admission refuses and says WHY', () => {
  beforeEach(() => {
    process.env[BILLING_ENFORCED_ENV] = 'true';
  });

  it('an empty wallet is `insufficient_balance`, and PERMANENT', async () => {
    balanceRows = []; // no ledger rows at all — a real zero
    await expect(admitVisitOrThrow({ practiceId: 'p1' })).rejects.toThrow(
      BillingAdmissionError,
    );
    try {
      await admitVisitOrThrow({ practiceId: 'p1' });
      expect.unreachable('admission should have refused');
    } catch (err) {
      const e = err as BillingAdmissionError;
      expect(e.reason).toBe('insufficient_balance');
      expect(e.retryCategory).toBe('permanent');
    }
  });

  it('a ledger that disagrees with itself is `balance_unreadable`, and TRANSIENT', async () => {
    // SUM says one thing, the derived running balance says another — ruling
    // 89(c)'s corruption shape. The practice may be perfectly solvent, so this
    // must NOT be filed as "you are out of money".
    balanceRows = [{ bucket: 'paid', sum_micro: '5000000', latest_balance: '999' }];
    try {
      await admitVisitOrThrow({ practiceId: 'p1' });
      expect.unreachable('admission should have refused');
    } catch (err) {
      const e = err as BillingAdmissionError;
      expect(e.reason).toBe('balance_unreadable');
      expect(e.retryCategory).toBe('transient');
    }
  });

  it('a funded wallet is admitted', async () => {
    balanceRows = [{ bucket: 'paid', sum_micro: '5000000', latest_balance: '5000000' }];
    await expect(admitVisitOrThrow({ practiceId: 'p1' })).resolves.toBeUndefined();
  });

  it('a promo-only wallet is now ADMITTED — B7 step 3a, end to end', async () => {
    // ⚠️ DELIBERATELY INVERTED. Until B7 step 3a this asserted a refusal under
    // `credit_not_spendable`, and that was right while the debit could only
    // reach `paid`. The whole point of step 3a is that this wallet is spendable:
    // if this arm still refused, B7 step 3's $10 grant would fund nobody.
    //
    // This is the FULL path — the stubbed `$queryRawUnsafe` through
    // `readPracticeBalance` and `decideAdmission` — not the pure decision alone,
    // so it also proves the reader now sums `promo` into `spendableMicroUsd`.
    balanceRows = [{ bucket: 'promo', sum_micro: '10000000', latest_balance: '10000000' }];
    await expect(admitVisitOrThrow({ practiceId: 'p1' })).resolves.toBeUndefined();
  });

  it('an EMPTY wallet still refuses — the inversion did not open the gate', async () => {
    // The control for the arm above. Widening the spendable set must not have
    // turned admission into "always admit"; zero still blocks.
    balanceRows = [];
    try {
      await admitVisitOrThrow({ practiceId: 'p1' });
      expect.unreachable('admission should have refused an empty wallet');
    } catch (err) {
      expect((err as BillingAdmissionError).reason).toBe('insufficient_balance');
    }
  });
});

// ---------------------------------------------------------------------------
describe('arm 7 — the debit NEVER throws', () => {
  beforeEach(() => {
    process.env[BILLING_ENFORCED_ENV] = 'true';
  });

  it('absorbs the production-only refusal instead of failing the visit', async () => {
    // `commitVisitCharge` calls `assertProdDatabase()` first (ruling 90(c)), and
    // this is not production — so the charge throws inside and the wrapper must
    // convert it. A READY visit with a finished clinical note must never be
    // failed by a billing write.
    logApiUsage(vendorEvent('v-charge'));
    const out = await chargeVisitUsage({ practiceId: 'p1', visitId: 'v-charge' });

    expect(out.charged).toBe('failed');
    expect(out).not.toHaveProperty('ledgerEntryId');
  });
});

// ⚠️ THE `categorizeError` ARM DELIBERATELY LIVES ELSEWHERE — in
// `apps/transcribe-md/src/worker/error-categorize.test.ts`. It was written here
// first, importing the app from a package by relative path, which runs under
// this repo's vitest config and is still backwards: `packages/ai` is a
// DEPENDENCY of the app and must not reach into it. The assertion is about the
// worker's classifier, so it belongs in the worker's own suite, where the
// import direction is the right way round.

// ---------------------------------------------------------------------------
describe('arm 9 — the loader does NOT re-implement the ruled exclusions', () => {
  // `priceUsageRows` already excludes mock rows (ruling 66) and non-billable
  // providers (GATE 0.5). A second copy in the loader's SQL is a hand-kept list
  // that drifts from the ruled one silently, in whichever direction a future
  // edit touches first — and the drift is invisible, because both versions
  // return plausible numbers.
  it('the query filters on visitId only', () => {
    const src = strip(readFileSync(join(SRC, 'billing-usage-source.ts'), 'utf8'));

    // ⚠️ THIS ASSERTION USED TO READ `src.includes('unitsSource:')` AND IT WAS
    // WRONG — it went red on the first run against correct code. `unitsSource:`
    // appears three times legitimately: in the row interface, in the `select`,
    // and in the mapping. SELECTING a column is not FILTERING on it, and the
    // check's name said "filters" while its body measured "mentions".
    //
    // That is AGENTS.md's "a check whose TITLE is narrower than what it
    // MEASURES", caught in this file's own first execution. The honest form
    // measures the `where` clause, which is the thing the claim is about.
    const whereClauses = src.match(/where:/g) ?? [];
    expect(whereClauses).toHaveLength(1);
    expect(src.includes('where: { visitId }')).toBe(true);

    // And no comparison against the ruled values anywhere in the loader — that
    // is the drift this arm actually guards.
    expect(src.includes('BILLABLE_PROVIDERS')).toBe(false);
    expect(/unitsSource\s*[!=]==/.test(src)).toBe(false);
  });

  it('and `priceUsageRows` still carries both exclusions', () => {
    // The other half of the same claim: dropping the filter here is only safe
    // while it exists there.
    const charge = strip(readFileSync(join(SRC, 'billing-charge.ts'), 'utf8'));
    expect(charge.includes("row.unitsSource !== 'vendor'")).toBe(true);
    expect(charge.includes('BILLABLE_PROVIDERS.includes')).toBe(true);
  });
});
