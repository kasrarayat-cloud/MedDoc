// ============================================================================
// B0 STEP 2 — a usage row without a provenance is unrepresentable.
// ----------------------------------------------------------------------------
// B0-a made `unitsSource` required in TYPESCRIPT and nullable in the DATABASE,
// on purpose and for exactly one deploy (see the step-1 migration header). This
// gate is what proves the second half landed: from here the database refuses
// what the type refuses.
//
// ⚠️ WHY A TYPE IS NOT ENOUGH, STATED SO NOBODY "SIMPLIFIES" THIS AWAY.
// The single ORM writer is `(prisma as any).apiUsageEvent.create(...)` — the
// shared client is untyped at that call, so `tsc` cannot see the insert at all.
// A green type-check says nothing about this table. The obligation is enforced
// one layer up at `logApiUsage(event: UsageEvent)`, and one layer up is exactly
// where a future writer can step around it. The database is the layer whose
// answer counts — the AuditAction lesson, where a TS union and a Prisma enum
// both passed while the Postgres enum was empty and the write threw at runtime.
//
// ── WHAT THIS GATE ASSERTS ────────────────────────────────────────────────
//   SHAPE     the column is NOT NULL and carries NO DEFAULT
//   NO-NULL   an insert omitting the provenance is REFUSED
//   NO-JUNK   an insert with an off-domain value is REFUSED by CONSTRAINT NAME
//   CONTROL   the SAME insert with 'vendor' SUCCEEDS
//   BUCKETS   every existing row is in a named bucket, and they sum to the total
//
// ⚠️ THE CONTROL IS NOT DECORATION — IT IS THE ARM THAT MAKES THE OTHERS MEAN
// ANYTHING. `api_usage_events` has eight NOT NULL columns with no default, so a
// malformed INSERT is refused for reasons that have nothing to do with
// provenance. This repo has already banked that exact error once: an
// attempt-proof "passed" because `specialty NOT NULL` rejected the row before
// the FK under test was ever consulted. So every refusal below is matched
// against WHAT refused, and the control proves the row is otherwise valid.
//
// Every mutation runs inside BEGIN … ROLLBACK. During a mutation run — with the
// constraint deliberately dropped to prove this gate can go red — these inserts
// SUCCEED, and a bare insert would then leave junk rows in the usage table that
// the money code reads. ROLLBACK makes the attempt observable without ever
// being consequential.
// ============================================================================

import { execSync } from 'node:child_process';

import { expect, test } from '@playwright/test';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from '../helpers/qa-compose';

function trySql(sql: string): { ok: boolean; out: string } {
  try {
    const out = execSync(
      `${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -v ON_ERROR_STOP=1 -A -t -f -`,
      { input: sql, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] },
    );
    return { ok: true, out: String(out) };
  } catch (err) {
    const e = err as { stdout?: string; stderr?: string };
    return { ok: false, out: `${e.stdout ?? ''}${e.stderr ?? ''}` };
  }
}
const num = (sql: string) => Number.parseInt(trySql(sql).out.trim(), 10);

/** Every NOT NULL column that has no default, so the only thing under test is
 *  the provenance. `userId`/`practiceId`/`visitId` stay NULL — they are
 *  nullable and FK-bearing, and a tenancy error here would be a second reason
 *  for a refusal we are trying to attribute to exactly one cause. */
const ROW = (unitsSource: string | null) => `
  INSERT INTO api_usage_events
    ("id", "provider", "operation", "unitCount", "unitType",
     "unitCostUsd", "totalCostUsd", "requestId", "unitsSource")
  VALUES
    ('b0gate-${unitsSource ?? 'null'}', 'anthropic', 'gate-probe', 1, 'tokens_in',
     0, 0, 'b0gate-req', ${unitsSource === null ? 'NULL' : `'${unitsSource}'`});
`;

test.describe('B0 step 2 — usage provenance is required at the database', () => {
  test('SHAPE — unitsSource is NOT NULL and has NO default', () => {
    const nullable = trySql(
      `SELECT is_nullable FROM information_schema.columns
        WHERE table_name='api_usage_events' AND column_name='unitsSource';`,
    ).out.trim();
    expect(
      nullable,
      'unitsSource is still nullable — step 2 has not been applied to this database',
    ).toBe('NO');

    // ⚠️ THIS ASSERTION IS THE RULING, NOT A DETAIL. A DEFAULT would satisfy
    // NOT NULL perfectly while reintroducing the precise fail-open the column
    // exists to close: a writer that never heard of provenance would silently
    // produce rows asserting a real vendor reported those numbers.
    const def = trySql(
      `SELECT coalesce(column_default,'<none>') FROM information_schema.columns
        WHERE table_name='api_usage_events' AND column_name='unitsSource';`,
    ).out.trim();
    expect(def, 'unitsSource has acquired a DEFAULT — that is fail-open by ruling').toBe(
      '<none>',
    );
  });

  test('NO-NULL — a usage row without a provenance is REFUSED', () => {
    const r = trySql(`BEGIN; ${ROW(null)} ROLLBACK;`);
    expect(
      r.ok,
      'a usage row with a NULL provenance was accepted — the guarantee does not exist',
    ).toBe(false);
    // Refused for the RIGHT reason. A typo, a missing column or a dead
    // connection all fail too, and all would look identical here.
    expect(r.out).toContain('unitsSource');
    expect(r.out.toLowerCase()).toContain('not-null');
  });

  test('NO-JUNK — an off-domain provenance is REFUSED by constraint name', () => {
    // 'Vendor' is the realistic mistake, not an absurd one: it satisfies NOT
    // NULL, reads correctly to a human, and matches NOTHING in
    // `WHERE "unitsSource" = 'vendor'`. Such a row is counted as neither vendor
    // nor mock — it does not error, it simply stops being money.
    const r = trySql(`BEGIN; ${ROW('Vendor')} ROLLBACK;`);
    expect(
      r.ok,
      "an off-domain provenance ('Vendor') was accepted — it would vanish from " +
        'every rollup while erroring nowhere',
    ).toBe(false);
    expect(r.out).toContain('api_usage_events_units_source_domain');
  });

  test('CONTROL — the SAME row with a valid provenance is ACCEPTED', () => {
    // Without this the two refusals above prove only that this INSERT fails,
    // which it would do for eight other NOT NULL columns, a bad table name, or
    // no database at all.
    const r = trySql(`BEGIN; ${ROW('vendor')} ROLLBACK;`);
    expect(
      r.ok,
      'a well-formed vendor row was ALSO refused — the refusals above are ' +
        'attributable to something other than the provenance guard: ' +
        r.out,
    ).toBe(true);

    // And the mock arm, so the domain is proven to admit BOTH ruled values
    // rather than having quietly collapsed to a single one.
    expect(trySql(`BEGIN; ${ROW('mock')} ROLLBACK;`).ok, "'mock' was refused").toBe(true);
  });

  test('BUCKETS — every row is in a named bucket, and they sum to the total', () => {
    // "Name every bucket the scan can sort an item into, and assert the total."
    // A count of vendor rows alone cannot distinguish a healthy table from one
    // whose other rows drifted out of the domain.
    //
    // ⚠️ THE CENSUS SUPPLIES ITS OWN NON-VACUITY, AND IT HAS TO.
    // The first version of this arm asserted `total > 0` against whatever
    // happened to be in the table. That passes on this long-lived QA stack
    // (977 rows) and would have RED in CI, where the database is created fresh
    // every run under `down -v` and NOTHING seeds `api_usage_events` — the
    // three seeders cover users, the T1 multi-seat fixture and the certified
    // twin. Any rows present at this point would be incidental output of
    // whichever pipeline specs happened to run first, which is not a fixture,
    // it is a race.
    //
    // So the census runs over rows it puts there itself: both buckets are known
    // to be occupied, the arithmetic is exercised on real data, and the whole
    // thing rolls back. Non-vacuous by construction instead of by luck.
    // ⚠️ THE CENSUS LINE IS TAGGED, NOT POSITIONAL. psql echoes a command tag
    // for every statement — `BEGIN`, `INSERT 0 1`, `ROLLBACK` — onto the same
    // stdout as the result. Splitting the output on whitespace and taking the
    // first three fields reads `BEGIN` as a number and yields NaN, which then
    // fails every numeric comparison for a reason that has nothing to do with
    // the buckets. Tag the row and find it by name.
    const r = trySql(
      `BEGIN;
       ${ROW('vendor')}
       ${ROW('mock')}
       SELECT 'CENSUS ' || count(*) || ' ' ||
              count(*) FILTER (WHERE "unitsSource"='vendor') || ' ' ||
              count(*) FILTER (WHERE "unitsSource"='mock')
         FROM api_usage_events;
       ROLLBACK;`,
    );
    expect(r.ok, `the census probe did not run: ${r.out}`).toBe(true);

    const line = r.out.split('\n').find((l) => l.startsWith('CENSUS '));
    expect(line, `no census line in psql output: ${r.out}`).toBeTruthy();
    const [total, vendor, mock] = (line as string).slice('CENSUS '.length).trim().split(/\s+/).map(Number);
    expect(vendor, 'the vendor row this test just inserted is not counted').toBeGreaterThan(0);
    expect(mock, 'the mock row this test just inserted is not counted').toBeGreaterThan(0);
    expect(
      vendor + mock,
      `${total - vendor - mock} of ${total} rows are in NO named bucket — ` +
        'they are counted as neither vendor nor mock and would be absent from the money',
    ).toBe(total);
  });
});
