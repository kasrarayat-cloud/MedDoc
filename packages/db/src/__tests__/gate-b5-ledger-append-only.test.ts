// @vitest-environment node
// ============================================================================
// B5 GATE — THE LEDGER IS APPEND-ONLY, THE BALANCE IS DERIVED, AND THE MONEY
// IS AN INTEGER.
// ----------------------------------------------------------------------------
// RELAY's gate for B5: "append-only enforced at the DATABASE, not by
// convention — an UPDATE and a DELETE are both attempted and both refused.
// `balanceAfter` consistency proven across a generated sequence."
//
// ⚠️ THAT SENTENCE DESCRIBES A BEHAVIOURAL PROOF, AND A BEHAVIOURAL PROOF
// CANNOT RUN IN THIS SUITE. CI has no Postgres, and the triggers only exist in
// a database. So the proof is split, deliberately, and BOTH halves are required:
//
//   · THE BEHAVIOURAL HALF lives in `scripts/check-ledger-append-only.sh
//     --qa --attempt`, which attempts the UPDATE, the DELETE and the TRUNCATE
//     against the live QA stack inside BEGIN … ROLLBACK and requires each to be
//     refused BY NAME — plus the positive control that the one permitted update
//     (the S4c detach) still succeeds.
//   · THIS FILE IS THE HALF THAT CAN REGRESS SILENTLY. The triggers are
//     invisible to Prisma: there is no `schema.prisma` syntax for one, so a
//     regenerated migration omits all four and `prisma migrate diff` reports no
//     drift. Nothing anywhere would go red. What this file guards is that the
//     MIGRATION still declares them, and that the shapes which make them
//     un-decayable are still the shapes in the file.
//
// ⚠️ WHAT THIS FILE DOES NOT CLAIM. It does not claim the triggers are INSTALLED
// on any database — a source file cannot know that. `assert-migrations-applied`
// and the script above answer that question. It does not claim anything is
// billed: nothing writes this table (asserted below, by enumeration).
//
// ── THE SIX THINGS THIS FILE ASSERTS ───────────────────────────────────────
//
//   1. THE FOUR TRIGGERS   present, with the right timing AND the right level
//   2. THE UN-DECAYABLE    the UPDATE guard compares the row WHOLESALE via
//      COMPARISON          jsonb, never a hand-written column list
//   3. INTEGER MONEY       no float type reaches the ledger's columns
//   4. TWO DELIBERATE      the `balanceAfter >= 0` CHECK is ABSENT, and the
//      ABSENCES            sign rule deliberately does not cover refund/adjustment
//   5. THE DETACH          the practice FK is ON DELETE SET NULL, not RESTRICT
//   6. THE DRIFT RECORD    every raw object the migration creates is documented
//      + THE WRITER SET    beside the model, and nothing writes the table yet
// ============================================================================

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const HERE = dirname(fileURLToPath(import.meta.url));
/** packages/db/src/__tests__ → repo root */
const ROOT = resolve(HERE, '..', '..', '..', '..');

const MIGRATION = join(
  ROOT,
  'packages/db/prisma/migrations/20260811070000_b5_ledger_entries/migration.sql',
);
const SCHEMA = join(ROOT, 'packages/db/prisma/schema.prisma');

const migrationSql = readFileSync(MIGRATION, 'utf8');
const schemaText = readFileSync(SCHEMA, 'utf8');

// ---------------------------------------------------------------------------
// STRIPPING COMMENTS — and why this helper exists rather than a bare `.includes`
// ---------------------------------------------------------------------------
// ⚠️ THE SUBSTRING TRAP, FOURTH-SIGHTING FAMILY (AGENTS.md). This migration's
// header is ~180 lines of prose that says "float" (five times), "RESTRICT",
// "DELETE", "UPDATE" and "TRUNCATE" — because it EXPLAINS why those are refused.
// A check for "no float type in the ledger" run against the whole file matches
// the sentence "no float ever touches a price" and reports a defect in its own
// explanation; a check for "the FK is not RESTRICT" matches the paragraph
// arguing against RESTRICT. Prose is the one place the words you are grepping
// for are guaranteed to appear.
//
// So every assertion about SQL runs against `sqlOnly`, and the two assertions
// that are genuinely ABOUT the prose say so.
function stripSqlComments(sql: string): string {
  return sql
    .split('\n')
    .map((line) => {
      const i = line.indexOf('--');
      return i === -1 ? line : line.slice(0, i);
    })
    .join('\n');
}

const sqlOnly = stripSqlComments(migrationSql);

/** The `CREATE TABLE "ledger_entries" ( … );` body, comments already stripped. */
const createTableBody = (() => {
  const start = sqlOnly.indexOf('CREATE TABLE "ledger_entries"');
  expect(start, 'CREATE TABLE "ledger_entries" not found').toBeGreaterThan(-1);
  const end = sqlOnly.indexOf(');', start);
  return sqlOnly.slice(start, end);
})();

describe('B5 — the comment stripper is positive-controlled before anything trusts it', () => {
  // AGENTS.md: positive-control every zero. A stripper that returned "" would
  // make every "the SQL does not contain X" assertion below pass vacuously, and
  // a broken check and a clean file produce identical output.
  it('removes prose but keeps SQL', () => {
    expect(sqlOnly).toContain('CREATE TABLE "ledger_entries"');
    expect(sqlOnly.length).toBeGreaterThan(1000);

    // The words that appear ONLY in the header prose must be gone…
    expect(migrationSql).toContain('NO FLOAT EVER TOUCHES MONEY');
    expect(sqlOnly).not.toContain('NO FLOAT EVER TOUCHES MONEY');

    // …and a line whose SQL precedes a trailing comment keeps its SQL.
    expect(sqlOnly).toContain('"amountMicroUsd"     BIGINT NOT NULL');
  });
});

// ---------------------------------------------------------------------------
// 1. THE FOUR TRIGGERS
// ---------------------------------------------------------------------------
describe('B5 (1) — the four triggers, with the right timing AND the right level', () => {
  const TRIGGERS = [
    { name: 'ledger_entries_derive_before_insert', when: 'BEFORE INSERT', level: 'FOR EACH ROW' },
    { name: 'ledger_entries_append_only_before_update', when: 'BEFORE UPDATE', level: 'FOR EACH ROW' },
    { name: 'ledger_entries_append_only_before_delete', when: 'BEFORE DELETE', level: 'FOR EACH ROW' },
    // ⚠️ THE ONE MOST LIKELY TO BE LEFT OUT, AND THE ONLY ONE THAT IS
    // STATEMENT-LEVEL. TRUNCATE fires NEITHER row trigger and is not a DELETE,
    // so a table protected only by BEFORE DELETE can still be emptied in one
    // statement. Mutation-proved 2026-08-11: with this trigger dropped inside a
    // transaction, `TRUNCATE ledger_entries` succeeded and the row count went
    // 1 → 0.
    { name: 'ledger_entries_append_only_before_truncate', when: 'BEFORE TRUNCATE', level: 'FOR EACH STATEMENT' },
  ];

  for (const t of TRIGGERS) {
    it(`declares ${t.name} as ${t.when} ${t.level}`, () => {
      const re = new RegExp(
        `CREATE TRIGGER "${t.name}"\\s*\\n?\\s*${t.when} ON "ledger_entries"\\s*\\n?\\s*${t.level}`,
      );
      expect(sqlOnly).toMatch(re);
    });
  }

  it('declares exactly four triggers — no more, no fewer', () => {
    const found = [...sqlOnly.matchAll(/CREATE TRIGGER "([^"]+)"/g)].map((m) => m[1]).sort();
    expect(found).toEqual(TRIGGERS.map((t) => t.name).sort());
  });

  it('the migration asserts its own trigger count, so a half-applied run cannot report success', () => {
    // AGENTS.md rule 8 — a migration that half-ran and reported success.
    expect(sqlOnly).toContain('n_triggers <> 4');
  });
});

// ---------------------------------------------------------------------------
// 2. THE UN-DECAYABLE COMPARISON — the load-bearing assertion in this file
// ---------------------------------------------------------------------------
describe('B5 (2) — the permitted UPDATE compares the row WHOLESALE, never a column list', () => {
  // ⚠️ WHY THIS IS THE ONE THAT MATTERS. The append-only trigger must permit
  // exactly one UPDATE — `ON DELETE SET NULL` detaching `practiceId` — because
  // Postgres implements that as an UPDATE and a blanket refusal would make
  // account deletion impossible (the S4c bug, which `audit_logs` already had
  // and `RxWarningOverride` repeated).
  //
  // The OBVIOUS way to write "and nothing else changed" is a list of
  // `NEW.x IS NOT DISTINCT FROM OLD.x` conjuncts. That list is a HAND-KEPT
  // LIST, and AGENTS.md's rule is that hand-kept lists are wrong eventually:
  // a column added to this table in five years is simply not in it, and an
  // UPDATE that changes that column while nulling `practiceId` sails through.
  //
  // ⚠️ MUTATION-PROVED ON QA, 2026-08-11, INSIDE A ROLLED-BACK TRANSACTION.
  // The function was replaced with a five-conjunct hand-written list omitting
  // `amountMicroUsd` — one column, the obvious way to write it — and then:
  //
  //     UPDATE ledger_entries SET "practiceId" = NULL, "amountMicroUsd" = 999
  //     → UPDATE 1
  //     → amount 5000000 → 999, while balanceAfter stayed 5000000
  //
  // A ledger row whose amount and running balance disagree, written through a
  // guard that reported success. The jsonb form refuses the identical statement.
  it('uses to_jsonb(NEW) - practiceId, comparing every other column at once', () => {
    expect(sqlOnly).toContain("(to_jsonb(NEW) - 'practiceId') = (to_jsonb(OLD) - 'practiceId')");
  });

  it('does NOT fall back to a per-column IS NOT DISTINCT FROM list', () => {
    // The mutation's own shape, banned. If a future edit needs per-column
    // logic it must argue with this assertion first — which is the point.
    const perColumn = [...sqlOnly.matchAll(/IS NOT DISTINCT FROM/g)].length;
    expect(perColumn).toBe(0);
  });

  it('permits the detach only in the NOT NULL → NULL direction', () => {
    expect(sqlOnly).toContain('OLD."practiceId" IS NOT NULL');
    expect(sqlOnly).toContain('NEW."practiceId" IS NULL');
  });

  it('refuses DELETE and TRUNCATE with messages naming the guard', () => {
    // A refusal is evidence only when you know WHAT refused (AGENTS.md), so the
    // message carries the constraint's own name for the script to match on.
    const raises = [...sqlOnly.matchAll(/ledger_entries_append_only: (\w+)/g)].map((m) => m[1]);
    expect(new Set(raises)).toEqual(new Set(['DELETE', 'UPDATE', 'TRUNCATE']));
  });
});

// ---------------------------------------------------------------------------
// 3. INTEGER MONEY — GATE 0.4
// ---------------------------------------------------------------------------
describe('B5 (3) — no float type reaches the ledger', () => {
  it('every money column is BIGINT', () => {
    expect(createTableBody).toMatch(/"amountMicroUsd"\s+BIGINT NOT NULL/);
    expect(createTableBody).toMatch(/"balanceAfter"\s+BIGINT NOT NULL/);
    expect(createTableBody).toMatch(/"seq"\s+BIGINT NOT NULL/);
  });

  it('the table declares no floating or decimal type at all', () => {
    // Scanned against the CREATE TABLE body only — see the stripper's note.
    for (const banned of ['REAL', 'DOUBLE', 'NUMERIC', 'DECIMAL', 'FLOAT', 'MONEY']) {
      expect(createTableBody.toUpperCase()).not.toContain(banned);
    }
  });

  it('the Prisma model types both money columns as BigInt', () => {
    expect(schemaText).toMatch(/amountMicroUsd BigInt/);
    expect(schemaText).toMatch(/balanceAfter BigInt @default\(0\)/);
    expect(schemaText).toMatch(/seq\s+BigInt @default\(0\)/);
  });
});

// ---------------------------------------------------------------------------
// 4. TWO DELIBERATE ABSENCES
// ---------------------------------------------------------------------------
describe('B5 (4) — the two absences are deliberate, and asserted BECAUSE they are invisible', () => {
  // ⚠️ AN ABSENCE IS INVISIBLE TO A BEHAVIOURAL TEST — ruling 84(a)'s reasoning,
  // applied here. Nothing fails when somebody adds a "sensible" constraint. So
  // the absence is pinned, with its reason, and a future author who wants it has
  // to delete an assertion that explains why they should not.

  it('there is NO balanceAfter >= 0 CHECK', () => {
    expect(sqlOnly).not.toMatch(/"balanceAfter"\s*>=\s*0/);
    // The reason, kept next to the assertion so it cannot be deleted casually:
    // the insufficient-balance block is checked at ADMISSION (B8), before the
    // pipeline runs; `usage` rows land AFTER, when vendors report what they
    // actually charged. A visit admitted with a sufficient balance can overrun
    // it, and this CHECK would make the last usage row of such a visit
    // unrepresentable — losing the record of money already owed to a vendor.
    // Fail-closed belongs where refusing is free, not where refusing loses data.
    expect(migrationSql).toContain('WHY THERE IS NO `balanceAfter >= 0` CHECK');
  });

  it('the sign rule covers usage/topup/grant and deliberately NOT refund/adjustment', () => {
    const sign = sqlOnly.slice(
      sqlOnly.indexOf('ledger_entries_kind_sign'),
      sqlOnly.indexOf('ledger_entries_seq_positive'),
    );
    expect(sign).toContain(`"kind" = 'usage' AND "amountMicroUsd" <= 0`);
    expect(sign).toContain(`"kind" = 'topup' AND "amountMicroUsd" >  0`);
    expect(sign).toContain(`"kind" = 'grant' AND "amountMicroUsd" >  0`);
    // refund/adjustment pass unconstrained. Nothing in SPEC settles whether a
    // refund credits the wallet or debits it, and a wrong guess would have to be
    // fixed by WEAKENING a shipped constraint — the forbidden direction. Adding
    // a rule later is the allowed one.
    expect(sign).toMatch(/"kind" IN \('refund', 'adjustment'\)/);
  });
});

// ---------------------------------------------------------------------------
// 5. THE DETACH
// ---------------------------------------------------------------------------
describe('B5 (5) — the practice FK detaches, it does not restrict', () => {
  it('is ON DELETE SET NULL in the migration', () => {
    expect(sqlOnly).toMatch(
      /ADD CONSTRAINT "ledger_entries_practiceId_fkey"[\s\S]*?ON UPDATE CASCADE ON DELETE SET NULL/,
    );
  });

  it('is onDelete: SetNull in the Prisma model', () => {
    expect(schemaText).toContain(
      'practice   Practice? @relation(fields: [practiceId], references: [id], onDelete: SetNull)',
    );
  });

  it('keeps a NOT NULL tombstone so a detached row is still attributable', () => {
    expect(createTableBody).toMatch(/"practiceIdSnapshot" TEXT\s+NOT NULL/);
    expect(sqlOnly).toContain('NEW."practiceIdSnapshot" := NEW."practiceId"');
  });

  it('refuses a tenantless INSERT — nullable is for the detach, not for callers', () => {
    expect(sqlOnly).toContain('ledger_entries_insert_requires_practice');
  });
});

// ---------------------------------------------------------------------------
// 6. THE DRIFT RECORD, AND THE WRITER SET
// ---------------------------------------------------------------------------
describe('B5 (6) — every raw object is documented beside the model', () => {
  // AGENTS.md rule 7: "A RAW CREATE INDEX / ADD CONSTRAINT IS DECLARED IN THE
  // SAME COMMIT, OR ITS INEXPRESSIBILITY IS DOCUMENTED IN PLACE." Trusting the
  // author to have written that comment is exactly the hand-kept-list failure,
  // so the two are DIFFED instead — the watched-set discipline, mechanised.
  const rawObjects = [
    ...[...sqlOnly.matchAll(/ADD CONSTRAINT "(ledger_entries_[a-z_]+)"\s*\n?\s*CHECK/g)].map((m) => m[1]),
    ...[...sqlOnly.matchAll(/CREATE TRIGGER "([^"]+)"/g)].map((m) => m[1]),
  ];

  it('found the objects it is about to diff (positive control)', () => {
    // A regex that matched nothing would make the diff below pass vacuously —
    // the emptiness failure that looks identical to a clean result.
    expect(rawObjects.length).toBe(9);
  });

  for (const name of [
    'ledger_entries_bucket_vocabulary',
    'ledger_entries_kind_vocabulary',
    'ledger_entries_kind_sign',
    'ledger_entries_seq_positive',
    'ledger_entries_snapshot_agrees',
    'ledger_entries_derive_before_insert',
    'ledger_entries_append_only_before_update',
    'ledger_entries_append_only_before_delete',
    'ledger_entries_append_only_before_truncate',
  ]) {
    it(`schema.prisma names ${name} so the drift enumeration can see it`, () => {
      expect(rawObjects).toContain(name);
      expect(schemaText).toContain(name);
    });
  }

  it('declares in schema.prisma the two indexes Prisma CAN express', () => {
    expect(schemaText).toContain('@@unique([practiceId, bucket, seq])');
    expect(schemaText).toContain('idempotencyKey String? @unique');
  });
});

describe('B5 (6b) — nothing writes the ledger yet, and that is enumerated rather than claimed', () => {
  // ⚠️ THIS ASSERTION IS EXPECTED TO GO RED WHEN B6 LANDS, AND THAT IS ITS JOB.
  // It is not a ratchet and it is not measuring adoption — it pins B5's own
  // scope claim ("nothing writes this table") so that the first writer arrives
  // as a DELIBERATE edit here rather than as a surprise. When you add one:
  // append its path to WRITERS below, in the same commit as the writer, and
  // make sure it comes with the prod-only refusal B6 requires.
  // ⚠️ B6 LANDED THE FIRST WRITER, AND THIS LIST GOING FROM [] TO ONE ENTRY IS
  // THE ASSERTION DOING ITS JOB — not a regression, and not a rubber stamp
  // either. The entry is here because a human edited it in the same commit as
  // the writer, which is precisely what B5 asked for: the first writer arrives
  // as a deliberate declaration rather than as a surprise.
  //
  // The two conditions B5 attached to that arrival are both met and both
  // checked elsewhere, by name: `commitVisitCharge` calls `assertProdDatabase()`
  // as its FIRST statement (gate-b6, arms 4 and 5, including a demonstrated
  // refusal against the live QA database), and it writes `kind: 'usage'` with a
  // negative amount, which the `ledger_entries_kind_sign` CHECK also enforces.
  //
  // ⚠️ B7 ADDS THE SECOND WRITER, AND ITS REFUSAL IS A DIFFERENT SHAPE FROM
  // B6's — DELIBERATELY, AND IT IS **STRICTER**, NOT LOOSER.
  //
  // `api/stripe/webhook/route.ts` does NOT call `assertProdDatabase()`. It
  // requires the event's `livemode` flag to MATCH the database's identity:
  // production credits only a LIVE event, a non-production database credits
  // only a TEST event, and anything unidentifiable (`staging`, unset,
  // unparseable) refuses both ways. Two positive confirmations, ruling 90(c)'s
  // rule applied to an inbound fact instead of an outbound one.
  //
  // SPEC §2.4 says "prod-only billing writer — the writer asserts it is in
  // production and refuses otherwise", so this is a stated divergence rather
  // than an oversight. The reason it is a divergence UPWARD:
  //
  //   `assertProdDatabase()` ALONE WOULD ACCEPT A **TEST-MODE** STRIPE EVENT
  //   ON PRODUCTION. It looks at the database and never at the event, so a
  //   test webhook pointed at app.quillmd.com would credit a real practice's
  //   real wallet with money nobody paid — on an append-only table, forever.
  //
  // The SPEC clause was written for B6's OUTBOUND charge, where the only thing
  // to confirm is where we are. An INBOUND event carries its own mode, so the
  // guard has to read both or it is guarding half the question. Recorded as a
  // PROVISIONAL ruling; the reversal is to AND `assertProdDatabase()` on top,
  // which only ever makes it stricter.
  //
  // B5's other condition is met unchanged: the row is `kind: 'topup'` with a
  // POSITIVE amount, which `ledger_entries_kind_sign` also enforces.
  const WRITERS: string[] = [
    'apps/transcribe-md/src/app/api/stripe/webhook/route.ts',
    'packages/ai/src/billing-charge.ts',
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
    ...sourceFiles(join(ROOT, 'packages')),
  ];

  it('scanned a real set of files (positive control)', () => {
    // Without this, a broken walker returns [] and the sweep below reports a
    // clean zero over a set it never entered.
    expect(files.length).toBeGreaterThan(500);
    expect(files.some((f) => f.includes('api-usage'))).toBe(true);
  });

  it('finds no ledgerEntry ORM write and no raw INSERT INTO ledger_entries', () => {
    // BY TABLE **and** BY ORM METHOD — AGENTS.md's write-path sweep shape. One
    // of the two alone has already missed a whole class in this repo.
    const ormWrite = /\bledgerEntry\s*\.\s*(create|createMany|upsert|update|updateMany|delete|deleteMany)\b/;
    const rawWrite = /insert\s+into\s+"?ledger_entries"?/i;

    const offenders = files.filter((f) => {
      if (f.includes('__tests__')) return false;
      const src = readFileSync(f, 'utf8');
      return ormWrite.test(src) || rawWrite.test(src);
    });

    expect(offenders.map((f) => f.slice(ROOT.length + 1)).sort()).toEqual(WRITERS);
  });

  it('the sweep patterns actually match something (positive control)', () => {
    // The patterns above must be capable of finding a write. Proven against a
    // synthetic source rather than against the tree, so this control cannot be
    // satisfied by the very thing it is controlling for.
    const ormWrite = /\bledgerEntry\s*\.\s*(create|createMany|upsert|update|updateMany|delete|deleteMany)\b/;
    const rawWrite = /insert\s+into\s+"?ledger_entries"?/i;
    expect(ormWrite.test('await tx.ledgerEntry.create({ data })')).toBe(true);
    expect(rawWrite.test('INSERT INTO "ledger_entries" (id) VALUES (1)')).toBe(true);
    expect(ormWrite.test('await tx.priceRate.create({ data })')).toBe(false);
  });
});
