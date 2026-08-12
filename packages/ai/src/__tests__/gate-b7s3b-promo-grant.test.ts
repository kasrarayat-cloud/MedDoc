// ============================================================================
// GATE — B7 step 3b: THE PROMO GRANT WRITER
// ----------------------------------------------------------------------------
// The item: SPEC §2.4's "$10 promo bucket" becomes a writer, keyed so that it
// can happen at most once per practice, ready for the two call sites B7 step 3c
// takes — the signup transaction and the backfill.
//
// ── WHAT THIS GATE PROVES, AND WHAT IT DELIBERATELY DOES NOT ───────────────
//
// Unlike `commitVisitCharge`, this writer is NOT production-only, so its
// behaviour IS reachable from a test — the collision arms below run the real
// function against a stub client rather than asserting on source text. That is
// the whole reason the prod-only question was answered the way it was; see
// `billing-grant.ts`'s header.
//
// What it does NOT prove: no `grant` row has ever been written, in any
// environment. `ledger_entries` holds 0 rows in production and on QA. The
// writer is unwired by design and this gate pins that as a CENSUS rather than
// as an absence, so step 3c's call sites arrive as a deliberate edit here.
//
// ⚠️ AND ONE ARM IS DELIBERATELY *NOT* WRITTEN. It would be easy to assert
// "`auth.ts` contains no grant call", which is true today and is the finding
// that created this step. It is not written because it would go RED the moment
// step 3c succeeds — AGENTS.md: "a check that fails when the thing it guards
// starts working is a check nobody keeps". The census arm below states the same
// fact in the form that survives its own cure.
// ============================================================================

import { readFileSync } from 'node:fs';
import { existsSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { DRAW_ORDER, SPENDABLE_BUCKETS } from '../billing-buckets';
import { grantPromoCredit, promoGrantKey, PROMO_GRANT_MICRO_USD } from '../billing-grant';

const SRC = join(__dirname, '..');
const ROOT = join(SRC, '..', '..', '..');

const grantSrc = () => readFileSync(join(SRC, 'billing-grant.ts'), 'utf8');
const chargeSrc = () => readFileSync(join(SRC, 'billing-charge.ts'), 'utf8');

/** A stub standing in for `prisma` / a `tx`. Records what it was asked to
 *  write, or throws whatever it was primed with. */
function stubClient(onCreate: (args: any) => any) {
  const calls: any[] = [];
  return {
    calls,
    client: {
      ledgerEntry: {
        create: async (args: any) => {
          calls.push(args);
          return onCreate(args);
        },
      },
    } as any,
  };
}

/**
 * A Prisma unique-violation in the `meta.target` shape.
 *
 * ⚠️ THIS COMMENT USED TO SAY "as the driver reports one", AND THAT WAS THE
 * DEFECT. It is Prisma's DOCUMENTED shape, and it is not what this repo's
 * driver emits. Under Prisma 7.9.0 with `@prisma/adapter-pg` a real P2002
 * carries `meta = { modelName, driverAdapterError }` and **no `target` at
 * all** — so every arm below passed while `grantPromoCredit` threw on every
 * real second grant.
 *
 * Nothing could have caught it here: a stub is a statement of what its author
 * believes the driver emits, and it agrees with the matcher because the same
 * person wrote both. It took a real collision against a real Postgres — the B8
 * QA behavioural proof, 2026-08-12 — to disagree.
 *
 * Kept, because a driver may legitimately produce it and the matcher reads both.
 * See {@link p2002Measured} for the shape actually observed.
 */
const p2002 = (target: string[] | string) =>
  Object.assign(new Error('Unique constraint failed'), { code: 'P2002', meta: { target } });

/**
 * THE SHAPE THIS REPO'S DRIVER ACTUALLY EMITS — transcribed from a real
 * collision on the QA stack, 2026-08-12, `ledger_entries_idempotencyKey_key`.
 *
 * ⚠️ THE QUOTE CHARACTERS ARE REAL AND ARE THE POINT. The adapter reports
 * `'"idempotencyKey"'`, with the double quotes Postgres uses to quote the
 * identifier — so even code reading the right place fails a bare
 * `=== 'idempotencyKey'`. Reproduced here verbatim rather than tidied, because
 * a fixture cleaned up to look reasonable is how the original defect survived.
 */
const p2002Measured = (fields: string[]) =>
  Object.assign(
    new Error('\nInvalid `prisma.ledgerEntry.create()` invocation:\n\n\nUnique constraint failed on the fields: (`"idempotencyKey"`)'),
    {
      code: 'P2002',
      meta: {
        modelName: 'LedgerEntry',
        driverAdapterError: {
          name: 'DriverAdapterError',
          cause: {
            originalCode: '23505',
            originalMessage:
              'duplicate key value violates unique constraint "ledger_entries_idempotencyKey_key"',
            kind: 'UniqueConstraintViolation',
            constraint: { fields },
          },
        },
      },
    },
  );

// ---------------------------------------------------------------------------
// ARM 1 — THE ROW. What a grant IS, asserted against the database's own CHECKs.
// ---------------------------------------------------------------------------

describe('the row a grant writes', () => {
  it('is $10 in micro-dollars, POSITIVE, in the promo bucket, kind=grant', async () => {
    const { calls, client } = stubClient(() => ({ id: 'led_1' }));
    const res = await grantPromoCredit('prac_1', client);

    expect(res).toEqual({
      granted: true,
      ledgerEntryId: 'led_1',
      amountMicroUsd: 10_000_000n,
    });

    const data = calls[0].data;
    // SPEC §2.4's "$10", in GATE 0.4's integer micro-dollars.
    expect(data.amountMicroUsd).toBe(10_000_000n);
    // `ledger_entries_kind_sign` CHECKs `grant > 0`. The mirror of the
    // negation `commitVisitCharge` performs for `usage`.
    expect(data.amountMicroUsd > 0n).toBe(true);
    expect(data.bucket).toBe('promo');
    expect(data.kind).toBe('grant');
  });

  it('sets NO pricing — `ledger_entries_usage_has_pricing` permits it only for usage', async () => {
    const { calls, client } = stubClient(() => ({ id: 'led_1' }));
    await grantPromoCredit('prac_1', client);
    // Ruling 90(d): a grant is money ARRIVING, not money computed. Inventing a
    // pricing object for one would be a claim nobody made.
    expect('pricing' in calls[0].data).toBe(false);
  });

  it('sends NO balanceAfter and NO seq — ruling 89(d), the trigger owns them', async () => {
    const { calls, client } = stubClient(() => ({ id: 'led_1' }));
    await grantPromoCredit('prac_1', client);
    // A caller-supplied value is not validated, it is DISCARDED — so sending
    // one is a way to believe something false about the row just written.
    expect('balanceAfter' in calls[0].data).toBe(false);
    expect('seq' in calls[0].data).toBe(false);
  });

  it('passes practiceIdSnapshot from the SAME variable as practiceId, so the pair cannot drift', async () => {
    const { calls, client } = stubClient(() => ({ id: 'led_1' }));
    await grantPromoCredit('prac_xyz', client);
    expect(calls[0].data.practiceId).toBe('prac_xyz');
    expect(calls[0].data.practiceIdSnapshot).toBe('prac_xyz');
  });
});

// ---------------------------------------------------------------------------
// ARM 2 — THE BUCKET IS SPENDABLE. The join #96 found broken, asserted here.
// ---------------------------------------------------------------------------

describe('the granted bucket is one a debit can actually reach', () => {
  // ⚠️ THIS IS THE ARM THAT WOULD HAVE CAUGHT RULING #96's DEFECT, AND IT IS
  // WHY IT IS IN THIS FILE RATHER THAN LEFT TO `billing-buckets`'s own gate.
  // Before B7 step 3a, `SPENDABLE_BUCKETS` was `['paid']` and this writer would
  // have been granting into a bucket no debit path could draw on — money that
  // reads as generosity in the ledger and funds nobody. The property is not
  // "promo is spendable"; it is "we do not grant into an unspendable bucket",
  // which stays correct if the vocabulary ever changes.
  it('grants into a bucket that appears in SPENDABLE_BUCKETS', async () => {
    const { calls, client } = stubClient(() => ({ id: 'led_1' }));
    await grantPromoCredit('prac_1', client);
    expect(SPENDABLE_BUCKETS).toContain(calls[0].data.bucket);
  });

  it('and SPENDABLE_BUCKETS is DERIVED from DRAW_ORDER, not mirrored', () => {
    // If these ever become two hand-kept lists again, the arm above can pass
    // while the debit still cannot reach the bucket.
    expect(SPENDABLE_BUCKETS).toBe(DRAW_ORDER);
  });
});

// ---------------------------------------------------------------------------
// ARM 3 — THE KEY. One grant per practice, forever.
// ---------------------------------------------------------------------------

describe('the idempotency key', () => {
  it('is stable across calls and carries no occasion', () => {
    // A date, a run id or an attempt number would make a SECOND grant a
    // different row rather than a refused one.
    expect(promoGrantKey('prac_1')).toBe(promoGrantKey('prac_1'));
    expect(promoGrantKey('prac_1')).toBe('grant:promo:practice:prac_1');
  });

  it('distinguishes practices', () => {
    expect(promoGrantKey('prac_1')).not.toBe(promoGrantKey('prac_2'));
  });

  it('is the key the writer actually sends', async () => {
    const { calls, client } = stubClient(() => ({ id: 'led_1' }));
    await grantPromoCredit('prac_1', client);
    // Asserted rather than assumed: a writer that built its key inline would
    // satisfy every arm above while drifting from the exported function that
    // step 3c's backfill uses to decide who still needs a grant.
    expect(calls[0].data.idempotencyKey).toBe(promoGrantKey('prac_1'));
  });

  it('does not collide with a usage charge key shape', async () => {
    const { visitChargeKey } = await import('../billing-charge');
    // `idempotencyKey` is GLOBALLY unique, so the two key spaces share one
    // index and a collision between them would refuse a real charge.
    expect(promoGrantKey('x')).not.toBe(visitChargeKey('x', 'promo'));
  });
});

// ---------------------------------------------------------------------------
// ARM 4 — THE COLLISION. The load-bearing behaviour, both directions.
// ---------------------------------------------------------------------------

describe('a second grant is refused, and only the right refusal is absorbed', () => {
  it('reports already_granted on the idempotencyKey unique (field-array form)', async () => {
    const { client } = stubClient(() => {
      throw p2002(['idempotencyKey']);
    });
    expect(await grantPromoCredit('prac_1', client)).toEqual({
      granted: false,
      reason: 'already_granted',
    });
  });

  it('reports already_granted on the constraint-NAME form of the same index', async () => {
    // The driver reports the CONSTRAINT, and which of the two shapes arrives
    // depends on the Prisma version — matching only one is how this arm goes
    // vacuous after an upgrade.
    const { client } = stubClient(() => {
      throw p2002('ledger_entries_idempotencyKey_key');
    });
    expect(await grantPromoCredit('prac_1', client)).toEqual({
      granted: false,
      reason: 'already_granted',
    });
  });

  // ⚠️ THE ARM THAT WOULD HAVE CAUGHT THE REAL DEFECT. Everything above stubs
  // `meta.target`; this stubs what the driver was measured to emit. Without it
  // the two arms above are a closed loop between a stub and a matcher.
  it('reports already_granted on the shape THIS DRIVER emits (measured, quotes and all)', async () => {
    const { client } = stubClient(() => {
      throw p2002Measured(['"idempotencyKey"']);
    });
    expect(await grantPromoCredit('prac_1', client)).toEqual({
      granted: false,
      reason: 'already_granted',
    });
  });

  // ⚠️ AND THE SAME SHAPE MUST STILL REFUSE TO ABSORB THE WRONG INDEX. The
  // negative control below covers the `meta.target` form; this covers the
  // measured one, because a matcher can be right about one location and
  // over-broad in the other.
  it('THROWS on the (practiceId,bucket,seq) unique in the MEASURED shape too', async () => {
    const { client } = stubClient(() => {
      throw p2002Measured(['"practiceId"', '"bucket"', '"seq"']);
    });
    await expect(grantPromoCredit('prac_1', client)).rejects.toMatchObject({ code: 'P2002' });
  });

  // ⚠️ A COLLISION NOBODY CAN IDENTIFY IS RETHROWN, NOT ABSORBED. If a future
  // driver reports neither location, "cannot tell" must fail closed: absorbing
  // an unidentified unique violation would record a practice as funded when the
  // row that failed was something else, permanently, on an append-only table.
  it('THROWS when the collision cannot be identified at all', async () => {
    const { client } = stubClient(() => {
      throw Object.assign(new Error('Unique constraint failed'), {
        code: 'P2002',
        meta: { modelName: 'LedgerEntry' },
      });
    });
    await expect(grantPromoCredit('prac_1', client)).rejects.toMatchObject({ code: 'P2002' });
  });

  // ⚠️ THE NEGATIVE CONTROL, AND IT IS THE ONE THAT MATTERS MOST.
  it('THROWS on the (practiceId,bucket,seq) unique — a lost derive lock is not "already granted"', async () => {
    // Ruling 89(d) makes this index the structural backstop for a lost advisory
    // lock. A matcher that read `err.code` alone would report this loud fault
    // as a quiet success, and the practice would end up unfunded with nothing
    // recording it.
    const { client } = stubClient(() => {
      throw p2002(['practiceId', 'bucket', 'seq']);
    });
    await expect(grantPromoCredit('prac_1', client)).rejects.toThrow();
  });

  it('THROWS on a CHECK violation', async () => {
    const { client } = stubClient(() => {
      throw Object.assign(new Error('ledger_entries_kind_sign'), { code: 'P2010' });
    });
    await expect(grantPromoCredit('prac_1', client)).rejects.toThrow();
  });

  it('THROWS on a connection failure', async () => {
    const { client } = stubClient(() => {
      throw new Error('connection refused');
    });
    await expect(grantPromoCredit('prac_1', client)).rejects.toThrow('connection refused');
  });
});

// ---------------------------------------------------------------------------
// ARM 5 — THE AMOUNT IS NOT A CALL-SITE DECISION.
// ---------------------------------------------------------------------------

describe('the grant amount', () => {
  it('is SPEC §2.4’s $10, expressed in micro-dollars', () => {
    expect(PROMO_GRANT_MICRO_USD).toBe(10_000_000n);
    // GATE 0.4 puts the whole ledger in integer micro-dollars — no float may
    // come near money.
    expect(typeof PROMO_GRANT_MICRO_USD).toBe('bigint');
  });

  it('is NOT a parameter of the writer', () => {
    // An `amountMicroUsd` argument would make the size of a grant a property of
    // each call site, so the backfill and the signup path could drift, and a
    // future caller could invent a number. Ruling #93(c) made the denomination
    // set an allowlist rather than a bound for the same reason.
    const src = grantSrc();
    const sig = src.slice(src.indexOf('export async function grantPromoCredit'));
    expect(sig.length).toBeGreaterThan(100); // the anchor matched — not a -1 slice
    const params = sig.slice(0, sig.indexOf('): Promise<GrantResult>'));
    expect(params).not.toMatch(/amount/i);
  });
});

// ---------------------------------------------------------------------------
// ARM 6 — NOT PRODUCTION-ONLY, AND THAT IS DELIBERATE.
// ---------------------------------------------------------------------------

describe('the environment posture', () => {
  it('the writer does not call assertProdDatabase', () => {
    expect(grantSrc()).not.toMatch(/^\s*assertProdDatabase\(\)/m);
  });

  it('and the matcher CAN find that call (positive control)', () => {
    // Without this, the arm above passes for a renamed guard, a moved import,
    // or a matcher that never matches anything.
    expect(chargeSrc()).toMatch(/^\s*assertProdDatabase\(\)/m);
  });
});

// ---------------------------------------------------------------------------
// ARM 7 — THE CENSUS. Who calls this writer, stated rather than assumed.
// ---------------------------------------------------------------------------

describe('B7 step 3b — the writer ships UNWIRED, enumerated rather than claimed', () => {
  // ⚠️ THIS ARM IS EXPECTED TO CHANGE WHEN STEP 3c LANDS, AND THAT IS ITS JOB.
  // It is not a ratchet. It pins step 3b's scope claim ("nothing calls this
  // yet") so the first call site arrives as a DELIBERATE edit here rather than
  // as a surprise. When you add one: append its path to CALLERS below, in the
  // same commit as the call.
  //
  // Step 3c's two call sites, named in advance so the diff is legible:
  //   · apps/transcribe-md/src/actions/auth.ts   — every practice from now on
  //   · the backfill script                      — every practice that exists
  // ⚠️ TWO LISTS, NOT ONE, AND THE SPLIT IS WHAT KEEPS THE CLAIM CHECKABLE.
  // B7 step 3b's ledger row uses this census to justify NOT DEPLOYING: "a
  // deploy would ship code that cannot execute". That claim is about
  // PRODUCTION reachability. A hand-run QA proof is a caller in the grep's
  // sense and not in the claim's sense, so folding it into one list would
  // retire the inertness assertion silently — the list would be non-empty and
  // nobody could tell which kind of caller made it so.
  //
  // PRODUCTION wiring. Still empty, and that is step 3b's scope claim intact.
  // Step 3c's two call sites, named in advance so the diff is legible:
  //   · apps/transcribe-md/src/actions/auth.ts   — every practice from now on
  //   · the backfill script                      — every practice that exists
  const CALLERS: string[] = [];

  // HAND-RUN PROOFS. Not reachable from the worker, any route, or any job —
  // they have their own `main()` and run only under `docker exec` against the
  // isolated QA stack. Every entry must live under a `scripts/qa/` path, which
  // is asserted below rather than trusted, so this list cannot quietly become a
  // place to park a real call site.
  const PROOF_CALLERS: string[] = [
    'apps/transcribe-md/scripts/qa/b8-admission-on-qa.ts',
  ];

  function sourceFiles(dir: string, acc: string[] = []): string[] {
    let entries: string[];
    try {
      entries = readdirSync(dir);
    } catch {
      return acc;
    }
    for (const e of entries) {
      if (e === 'node_modules' || e === '.next' || e === 'dist' || e === '.git') continue;
      const p = join(dir, e);
      let s;
      try {
        s = statSync(p);
      } catch {
        continue;
      }
      if (s.isDirectory()) sourceFiles(p, acc);
      else if (/\.(ts|tsx)$/.test(e)) acc.push(p);
    }
    return acc;
  }

  const files = [
    ...sourceFiles(join(ROOT, 'apps/transcribe-md/src')),
    ...sourceFiles(join(ROOT, 'apps/transcribe-md/scripts')),
    ...sourceFiles(join(ROOT, 'packages')),
    ...sourceFiles(join(ROOT, 'scripts')),
  ];

  it('scanned a real set of files (positive control)', () => {
    // A broken walker returns [] and the census below reports a clean zero over
    // a set it never entered — indistinguishable from a correct answer.
    expect(files.length).toBeGreaterThan(500);
    expect(files.some((f) => f.endsWith('billing-grant.ts'))).toBe(true);
  });

  /** Every call site in the tree, as repo-relative paths. */
  function callSites(): string[] {
    const call = /\bgrantPromoCredit\s*\(/;
    return files
      .filter((f) => {
        if (f.includes('__tests__') || f.endsWith('billing-grant.ts')) return false;
        // `index.ts` re-exports the symbol; a re-export is not a call site.
        if (f.endsWith(join('packages', 'ai', 'src', 'index.ts'))) return false;
        return call.test(readFileSync(f, 'utf8'));
      })
      .map((f) => f.slice(ROOT.length + 1))
      .sort();
  }

  it('nothing outside the writer and this gate calls grantPromoCredit', () => {
    // The whole census reconciles: every caller is accounted for as either
    // production wiring or a hand-run proof, and anything that is neither is
    // the finding.
    expect(callSites()).toEqual([...CALLERS, ...PROOF_CALLERS].sort());
  });

  it('the writer is still UNWIRED in production — step 3b’s scope claim', () => {
    // ⚠️ THE ARM THE LEDGER ROW ACTUALLY CITES. Kept separate from the census
    // above so that adding a proof can never be mistaken for wiring the writer,
    // and so the day this list stops being empty it is a deliberate, visible
    // edit rather than a line appended to a mixed list.
    const production = callSites().filter((f) => !PROOF_CALLERS.includes(f));
    expect(production).toEqual(CALLERS);
  });

  it('every declared proof caller really is a proof, and really exists', () => {
    // ⚠️ AN EXEMPTION'S REASON IS PROSE, AND PROSE DECAYS SILENTLY (AGENTS.md).
    // The reason PROOF_CALLERS is safe is "these are hand-run scripts under
    // scripts/qa/, not reachable from the worker". Both halves are asserted:
    // the path shape, so a production file cannot be parked here; and
    // existence, so a stale entry cannot keep excusing a caller that moved.
    for (const p of PROOF_CALLERS) {
      expect(p).toMatch(/(^|\/)scripts\/qa\/[^/]+\.ts$/);
      expect(existsSync(join(ROOT, p))).toBe(true);
      // It must actually call the writer — otherwise the entry is dead and is
      // silently widening the exemption for nothing.
      expect(/\bgrantPromoCredit\s*\(/.test(readFileSync(join(ROOT, p), 'utf8'))).toBe(true);
    }
  });

  it('the census pattern can actually find a call (positive control)', () => {
    const call = /\bgrantPromoCredit\s*\(/;
    expect(call.test('await grantPromoCredit(practice.id, tx)')).toBe(true);
    expect(call.test('import { grantPromoCredit } from "@meddoc/ai"')).toBe(false);
  });
});
