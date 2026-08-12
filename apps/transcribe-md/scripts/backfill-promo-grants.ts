// ============================================================================
// FOUNDATION B7 STEP 3c — THE ONE-SHOT PROMO BACKFILL. DOOR 2 OF 3.
// ----------------------------------------------------------------------------
// Ruling #99 (the owner's written authorization, recorded verbatim in
// RULINGS.md and RELAY.md) authorized this in full. Its execution shape is not
// a matter of taste — it is quoted here because the script has to obey it:
//
//   "rehearse the same script on QA first; population re-derived at execution
//    time, never copied from this text; abort-on-mismatch guards proven to fire
//    before being trusted; idempotent — exactly one PROMO_GRANT row per
//    practice, a re-run refuses; amount in integer micro-dollars from the ruled
//    constant; balanceAfter computed by the ledger's own arithmetic; one audit
//    row per grant; the §2.5 declaration states the expected delta BEFORE
//    running."
//
// ⚠️ THIS IS THE FIRST ACT IN THE PROGRAMME THAT CANNOT BE REVERTED.
// `ledger_entries` refuses DELETE and UPDATE by trigger. ~175 rows written here
// are permanent; the only instrument afterwards is an `adjustment` row per
// practice, which offsets the balance and then lives beside the grant forever.
// Every guard below exists because there is no second chance to get the
// population right.
//
// ----------------------------------------------------------------------------
// USAGE
// ----------------------------------------------------------------------------
//   npx tsx scripts/backfill-promo-grants.ts --target=qa   --expect=<N>
//   npx tsx scripts/backfill-promo-grants.ts --target=prod --expect=<N> --commit
//
// DRY RUN IS THE DEFAULT. Without `--commit` the script derives the population,
// runs every guard, performs the writes inside a transaction and then ROLLS
// BACK — so a rehearsal exercises the real code path rather than a description
// of it, and still writes nothing. AGENTS.md: "any write inside a gate that a
// constraint is supposed to refuse belongs in BEGIN; … ROLLBACK;".
//
// ----------------------------------------------------------------------------
// THE POPULATION, AND WHY IT IS 175 AND NOT 197
// ----------------------------------------------------------------------------
// "Active-member practices only" — a practice with at least one `isActive` user.
// Ruling #99 records the anatomy of the exclusion and it reconciles exactly:
//
//   active member         175   backfilled HERE
//   members, all inactive   6   funded at REACTIVATION (door 3)
//   no members at all      16   structurally dead — no reactivation to fund
//   total                 197
//
// The 6 are excluded because pre-minting credit for an account nobody can log
// into puts undrawable money on a table that refuses deletes. Door 3 funds them
// at arrival instead. ⚠️ SEE THE FINDING IN RELAY: door 3's only site lives in
// `apps/meddoc-pro`, which is DECOMMISSIONED — so that path is structurally
// correct and operationally unreachable today.
// ============================================================================

import prisma from '@meddoc/db';
import type { TransactionClient } from '@meddoc/db';
import {
  grantPromoCredit,
  PROMO_GRANT_MICRO_USD,
  promoGrantKey,
} from '@meddoc/ai/billing-grant';
import { describeDbTarget, checkProdDb } from '@meddoc/db/guard';

import { logAudit } from '../src/lib/audit';

/** A qa/test/e2e/ci marker — the same vocabulary `db-guard` refuses production
 *  writers on, used here in the opposite direction to confirm a REHEARSAL is
 *  really pointed at a rehearsal database. */
const QA_MARKER = /(^|[_-])(qa|test|e2e|ci)([_-]|$)/;

type Target = 'qa' | 'prod';

function parseArgs(argv: string[]) {
  const get = (name: string): string | undefined => {
    const hit = argv.find((a) => a.startsWith(`--${name}=`));
    return hit ? hit.slice(name.length + 3) : undefined;
  };
  const target = get('target');
  if (target !== 'qa' && target !== 'prod') {
    throw new Error(
      '--target=qa|prod is REQUIRED and has no default.\n' +
        '  A default here would mean the difference between a rehearsal and an\n' +
        '  irreversible production write is a flag somebody forgot to type.',
    );
  }
  const expectRaw = get('expect');
  if (expectRaw === undefined || !/^\d+$/.test(expectRaw)) {
    throw new Error(
      '--expect=<N> is REQUIRED and must be a non-negative integer.\n' +
        '  §2.5: the expected delta is declared BEFORE the run. This flag is what\n' +
        '  makes that declaration BINDING rather than decorative — the population is\n' +
        '  re-derived here and the run ABORTS if it disagrees with N.',
    );
  }
  return {
    target: target as Target,
    expect: Number(expectRaw),
    commit: argv.includes('--commit'),
  };
}

/**
 * GUARD 1 — THE DATABASE IS THE ONE THE OPERATOR NAMED.
 *
 * ⚠️ IT REFUSES IN BOTH DIRECTIONS, WHICH IS THE WHOLE POINT. `--target=prod`
 * against a QA database would rehearse while reporting a production run;
 * `--target=qa` against production would write 175 irreversible rows during
 * what its operator believed was a rehearsal. The second is the one that
 * cannot be undone, so neither is allowed to be a warning.
 */
function assertTargetMatchesDatabase(target: Target): { host: string; database: string } {
  const url = process.env.DATABASE_URL;
  if (!url || !url.trim()) throw new Error('GUARD 1 ABORT: DATABASE_URL is not set.');

  const parsed = describeDbTarget(url);
  const db = parsed.database.trim().toLowerCase();

  if (target === 'prod') {
    const res = checkProdDb(parsed.database, parsed.host);
    if (!res.ok) {
      throw new Error(
        `GUARD 1 ABORT: --target=prod but ${res.reason}.\n` +
          `  Refusing: this run would not be the run it says it is.`,
      );
    }
  } else {
    if (!QA_MARKER.test(db)) {
      throw new Error(
        `GUARD 1 ABORT: --target=qa but database "${db}" carries no qa/test/e2e/ci\n` +
          `  marker. Refusing — a "rehearsal" against production writes rows that\n` +
          `  cannot be deleted.`,
      );
    }
  }
  return { host: parsed.host, database: db };
}

/**
 * THE POPULATION, RE-DERIVED HERE AND NOWHERE ELSE.
 *
 * ⚠️ NEVER READ FROM A LIST, A REPORT OR A LEDGER ROW. Ruling #99 says so in as
 * many words, and AGENTS.md has the reason: "a count carried forward from
 * another session's report and then incremented by assumption is a fabricated
 * number". The number this returns was observed by this process, seconds before
 * it was used.
 */
async function derivePopulation(client: TransactionClient | typeof prisma): Promise<string[]> {
  const rows = await client.practice.findMany({
    where: { users: { some: { isActive: true } } },
    select: { id: true },
    orderBy: { id: 'asc' },
  });
  return rows.map((r: { id: string }) => r.id);
}

/** Sum of a bucket across the whole ledger, in micro-dollars. `null` sums to 0n. */
async function bucketSum(
  client: TransactionClient | typeof prisma,
  bucket: string,
): Promise<bigint> {
  const agg = await client.ledgerEntry.aggregate({
    where: { bucket },
    _sum: { amountMicroUsd: true },
  });
  return agg._sum.amountMicroUsd ?? 0n;
}

/** Counts of the tables a wallet backfill must NOT touch. §2.5's clinical row is
 *  never omitted: "a deploy that moves a visit, patient or signature count has
 *  done something nobody asked for". */
async function clinicalCounts(client: TransactionClient | typeof prisma) {
  const [visits, patients, signed] = await Promise.all([
    client.transcribeVisit.count(),
    client.transcribeMdPatient.count(),
    client.transcribeVisit.count({ where: { signedAt: { not: null } } }),
  ]);
  return { visits, patients, signed };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const where = assertTargetMatchesDatabase(args.target);

  console.log('='.repeat(74));
  console.log('B7 STEP 3c — PROMO GRANT BACKFILL');
  console.log(`  database   : ${where.database} @ ${where.host}`);
  console.log(`  target     : ${args.target}`);
  console.log(`  mode       : ${args.commit ? '⚠️  COMMIT (irreversible)' : 'DRY RUN (rolls back)'}`);
  console.log(`  --expect   : ${args.expect}`);
  console.log(`  grant      : ${PROMO_GRANT_MICRO_USD} micro-USD each`);
  console.log('='.repeat(74));

  // ---- BASELINE, captured before anything changes -------------------------
  const population = await derivePopulation(prisma);
  const beforePaid = await bucketSum(prisma, 'paid');
  const beforePromo = await bucketSum(prisma, 'promo');
  const beforeClinical = await clinicalCounts(prisma);

  console.log(`\nre-derived population : ${population.length} active-member practices`);
  console.log(`baseline paid sum     : ${beforePaid}`);
  console.log(`baseline promo sum    : ${beforePromo}`);
  console.log(
    `baseline clinical     : visits=${beforeClinical.visits} patients=${beforeClinical.patients} signed=${beforeClinical.signed}`,
  );

  // ---- GUARD 2 — the declaration is binding --------------------------------
  if (population.length !== args.expect) {
    throw new Error(
      `GUARD 2 ABORT: population is ${population.length}, --expect said ${args.expect}.\n` +
        `  The §2.5 declaration was written against a number that is no longer true.\n` +
        `  Re-derive, re-declare, re-run. Do NOT pass the new number without\n` +
        `  updating the declaration — that would make the guard a formality.`,
    );
  }

  const expectedPromoDelta = BigInt(population.length) * PROMO_GRANT_MICRO_USD;
  console.log(`\nexpected promo delta  : +${expectedPromoDelta} (= ${population.length} × ${PROMO_GRANT_MICRO_USD})`);

  // ---- THE WRITE ----------------------------------------------------------
  const granted: {
    practiceId: string;
    amountMicroUsd: bigint;
    balanceAfter: bigint;
    seq: bigint;
  }[] = [];
  let already = 0;

  const ROLLBACK = Symbol('dry-run rollback');

  try {
    await prisma.$transaction(
      async (tx: TransactionClient) => {
        // ⚠️ RE-DERIVED **INSIDE** THE TRANSACTION TOO, and compared. Between the
        // baseline read and here, a signup can create a practice — and that
        // signup now grants its own promo (door 1). Racing it is harmless
        // because the idempotency key is global, but a population that moved
        // means the number in the declaration is no longer the number being
        // written, and §2.5's comparison would have an excuse available to it.
        const inTx = await derivePopulation(tx);
        if (inTx.length !== population.length) {
          throw new Error(
            `GUARD 3 ABORT: population moved during the run — ${population.length} → ${inTx.length}.\n` +
              `  Nothing has been written. Re-derive and re-declare.`,
          );
        }

        for (const practiceId of inTx) {
          const res = await grantPromoCredit(practiceId, tx);
          if (res.granted) {
            granted.push({
              practiceId,
              amountMicroUsd: res.amountMicroUsd,
              balanceAfter: res.balanceAfter,
              seq: res.seq,
            });
          } else {
            already += 1;
          }
        }

        // ---- GUARD 4 — verify BEFORE COMMIT, inside the transaction --------
        // ⚠️ THE CHECK RUNS WHERE IT CAN STILL REFUSE. A verification after
        // COMMIT on this table is a report, not a guard: there is no statement
        // that could act on what it finds.
        const afterPromo = await bucketSum(tx, 'promo');
        const afterPaid = await bucketSum(tx, 'paid');
        const afterClinical = await clinicalCounts(tx);

        const promoDelta = afterPromo - beforePromo;
        const expectedFromWrites = BigInt(granted.length) * PROMO_GRANT_MICRO_USD;

        if (promoDelta !== expectedFromWrites) {
          throw new Error(
            `GUARD 4 ABORT: promo bucket moved by ${promoDelta}, but ${granted.length} grants ` +
              `× ${PROMO_GRANT_MICRO_USD} = ${expectedFromWrites}. Something else wrote to this bucket.`,
          );
        }
        if (afterPaid !== beforePaid) {
          throw new Error(
            `GUARD 5 ABORT: PAID balance moved (${beforePaid} → ${afterPaid}). ` +
              `A promo backfill must not touch paid money.`,
          );
        }
        if (
          afterClinical.visits !== beforeClinical.visits ||
          afterClinical.patients !== beforeClinical.patients ||
          afterClinical.signed !== beforeClinical.signed
        ) {
          throw new Error(
            `GUARD 6 ABORT: a CLINICAL count moved. ` +
              `visits ${beforeClinical.visits}→${afterClinical.visits}, ` +
              `patients ${beforeClinical.patients}→${afterClinical.patients}, ` +
              `signed ${beforeClinical.signed}→${afterClinical.signed}.`,
          );
        }

        // ---- GUARD 7 — exactly one grant row per practice in the population -
        const keys = inTx.map(promoGrantKey);
        const rows = await tx.ledgerEntry.count({
          where: { kind: 'grant', bucket: 'promo', idempotencyKey: { in: keys } },
        });
        if (rows !== inTx.length) {
          throw new Error(
            `GUARD 7 ABORT: expected exactly ${inTx.length} promo-grant rows for the ` +
              `population, found ${rows}.`,
          );
        }

        console.log(
          `\n  wrote ${granted.length} grant(s), ${already} already had one, ` +
            `promo delta ${promoDelta}`,
        );
        console.log('  guards 3-7 PASSED inside the transaction');

        if (!args.commit) {
          // Roll back a REAL run rather than skipping the writes: a dry run that
          // takes a different code path proves nothing about the real one.
          throw ROLLBACK;
        }
      },
      // 175 inserts, each firing the derive trigger. Prisma's interactive
      // default is 5s and would abort a correct run partway.
      { timeout: 180_000, maxWait: 20_000 },
    );
  } catch (err) {
    if (err === ROLLBACK) {
      console.log('\n🟡 DRY RUN — transaction rolled back. NOTHING WAS WRITTEN.');
      console.log(`   A committing run would write ${granted.length} row(s).`);
      await prisma.$disconnect();
      return;
    }
    throw err;
  }

  // ---- ONE AUDIT ROW PER GRANT, after the commit ---------------------------
  // ⚠️ AFTER, for the same reason the signup door audits after its transaction:
  // a row claiming a grant that rolled back is a false record on the one table
  // an operator trusts. `logAudit` is fire-and-forget, so these are awaited
  // here only to keep the process alive until they are issued.
  for (const g of granted) {
    await logAudit({
      action: 'PROMO_GRANT_CREDITED',
      targetType: 'Practice',
      targetId: g.practiceId,
      practiceId: g.practiceId,
      metadata: {
        door: 'backfill',
        bucket: 'promo',
        amountMicroUsd: g.amountMicroUsd.toString(),
        balanceAfter: g.balanceAfter.toString(),
        seq: g.seq.toString(),
      },
    });
  }

  const finalPromo = await bucketSum(prisma, 'promo');
  console.log(`\n🟢 COMMITTED — ${granted.length} grant(s), ${already} pre-existing.`);
  console.log(`   promo sum ${beforePromo} → ${finalPromo} (delta ${finalPromo - beforePromo})`);
  console.log(`   audit rows issued: ${granted.length}`);
  await prisma.$disconnect();
}

main().catch(async (err) => {
  console.error(`\n🔴 ${err instanceof Error ? err.message : String(err)}`);
  await prisma.$disconnect();
  process.exit(1);
});
