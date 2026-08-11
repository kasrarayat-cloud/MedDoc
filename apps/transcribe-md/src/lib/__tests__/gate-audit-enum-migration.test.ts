// ============================================================================
// THE THIRD LAYER — every AuditAction in the schema must be REACHABLE IN THE
// DATABASE, which means a migration must create it.
// ----------------------------------------------------------------------------
// ⚠️ THIS IS THE SIBLING OF `gate-audit-action-parity.test.ts`, AND THE GAP
// BETWEEN THEM IS WHERE THE BUG LIVED TWICE.
//
// That gate compares the TypeScript union against `schema.prisma`. It is
// correct and it is not sufficient, because `schema.prisma` IS NOT THE
// DATABASE either. A Prisma enum VALUE needs its own
// `ALTER TYPE … ADD VALUE` migration, and nothing in the build says so:
//
//   the TS union in `lib/audit.ts`      → `tsc` passes without the migration
//   the enum in `schema.prisma`         → `prisma validate` passes without it
//   an ALTER TYPE migration             → the ONLY layer the database reads
//
// Measured, 2026-08-06, adding `SIGN_BLOCKED_ROLE_NOT_PERMITTED`: attempt 2
// landed in BOTH source files and still not in the database. `prisma validate`
// passed. `tsc` passed. **3192 unit tests passed.** The refusal fired correctly
// with a 403. The app logged `invalid input value for enum "AuditAction"` and
// SWALLOWED it, because `logAudit` is deliberately fire-and-forget so an audit
// failure can never break a clinical action.
//
// The only thing that caught it was an E2E that queried `audit_logs` for the
// row. That is expensive and slow and runs late. This is the same question
// asked of the SOURCE, so it fails in the unit suite instead — before the
// commit, not after the deploy.
//
// ⚠️ WHAT THIS GATE DOES **NOT** CLAIM. It proves a migration EXISTS that would
// create each label. It does not prove that migration has been APPLIED to any
// particular database — that is `scripts/assert-migrations-applied.sh`, and the
// two together are what the claim needs. Stated because a green here reads like
// "the label is in the database", and it is not that.
// ============================================================================

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, it, expect } from 'vitest';

const MIGRATIONS_DIR = '../../packages/db/prisma/migrations';
const SCHEMA_PATH = '../../packages/db/prisma/schema.prisma';

/** Strip `--` line comments before parsing. A migration's PROSE names labels
 *  too — this file's own header does — and the substring family in AGENTS.md is
 *  four sightings deep precisely because comments are where the words you are
 *  grepping for are guaranteed to appear. */
function stripSqlComments(sql: string): string {
  return sql.replace(/--[^\n]*/g, '');
}

/** The labels declared in `enum AuditAction { … }` in the Prisma schema. */
function schemaLabels(): string[] {
  const src = readFileSync(SCHEMA_PATH, 'utf8');
  const start = src.indexOf('enum AuditAction {');
  if (start === -1) throw new Error('enum AuditAction not found in schema.prisma');
  const end = src.indexOf('\n}', start);
  const body = src.slice(start, end);
  return [...body.matchAll(/^\s{2}([A-Z][A-Z0-9_]*)\s*$/gm)].map((m) => m[1]);
}

/**
 * Every label the MIGRATION HISTORY can create: the initial
 * `CREATE TYPE "AuditAction" AS ENUM (…)` plus every
 * `ALTER TYPE "AuditAction" ADD VALUE [IF NOT EXISTS] 'X';`.
 *
 * ⚠️ PARSED PER STATEMENT, UP TO THE SEMICOLON — not by grepping for quoted
 * words anywhere in the file. Both forms occur in this repo, including a
 * multi-line one where `ALTER TYPE "AuditAction"` and its value sit on
 * different lines, so a line-oriented matcher would miss it and report a
 * perfectly clean false alarm.
 */
function migrationLabels(): Set<string> {
  const out = new Set<string>();
  for (const dir of readdirSync(MIGRATIONS_DIR)) {
    let sql: string;
    try {
      sql = stripSqlComments(readFileSync(join(MIGRATIONS_DIR, dir, 'migration.sql'), 'utf8'));
    } catch {
      continue; // not a migration directory
    }
    for (const m of sql.matchAll(/CREATE\s+TYPE\s+"AuditAction"\s+AS\s+ENUM\s*\(([^;]*)\)/gi)) {
      for (const v of m[1].matchAll(/'([A-Z][A-Z0-9_]*)'/g)) out.add(v[1]);
    }
    for (const m of sql.matchAll(/ALTER\s+TYPE\s+"AuditAction"[^;]*;/gi)) {
      for (const v of m[0].matchAll(/'([A-Z][A-Z0-9_]*)'/g)) out.add(v[1]);
    }
  }
  return out;
}

describe('AuditAction — the schema vs what a migration actually creates', () => {
  it('the parse is non-vacuous on BOTH sides', () => {
    // Every assertion below is quantified over these two. If either parsed to
    // nothing, the subset check would pass forever and read exactly like a
    // clean run — the emptiness defect this repo has now hit in three shapes.
    expect(schemaLabels().length, 'the schema enum parsed to (almost) nothing').toBeGreaterThan(100);
    expect(migrationLabels().size, 'the migrations parsed to (almost) nothing').toBeGreaterThan(100);
  });

  it('EVERY label in schema.prisma is created by some migration', () => {
    const creatable = migrationLabels();
    const missing = schemaLabels().filter((l) => !creatable.has(l));
    expect(
      missing,
      'these exist in schema.prisma but NO migration creates them in Postgres. ' +
        '`prisma validate` and `tsc` both pass in this state, and `logAudit` is ' +
        'fire-and-forget — so every row using one of these is REJECTED BY THE ' +
        'DATABASE and the rejection is discarded with no error anywhere. Add ' +
        "`ALTER TYPE \"AuditAction\" ADD VALUE IF NOT EXISTS '<LABEL>';` in a migration",
    ).toEqual([]);
  });

  it('POSITIVE CONTROL — the subset check can actually report a miss', () => {
    const creatable = migrationLabels();
    expect(
      creatable.has('THIS_LABEL_IS_IN_NO_MIGRATION'),
      'the migration-side set claims to contain a fabricated label — the parse is wrong',
    ).toBe(false);
    expect(
      ['THIS_LABEL_IS_IN_NO_MIGRATION'].filter((l) => !creatable.has(l)),
      'the missing-detector cannot detect a missing label',
    ).toEqual(['THIS_LABEL_IS_IN_NO_MIGRATION']);
  });

  it('POSITIVE CONTROL — the parser sees BOTH statement forms, not just one', () => {
    const creatable = migrationLabels();
    // From `0000_init`'s `CREATE TYPE … AS ENUM (…)`.
    expect(creatable, 'the CREATE TYPE arm parsed nothing').toContain('LOGIN_SUCCESS');
    // From a single-line `ALTER TYPE … ADD VALUE IF NOT EXISTS '…';`.
    expect(creatable, 'the ALTER TYPE arm parsed nothing').toContain(
      'SIGN_BLOCKED_ROLE_NOT_PERMITTED',
    );
    // From the MULTI-LINE `ALTER TYPE "AuditAction"` form, where the value sits
    // on a LATER LINE — `20260610210000_add_ai_refusal_audit_action` and
    // `20260506081720_add_transcription_provider` are the two that use it. A
    // line-oriented matcher misses exactly these and reports a clean run.
    //
    // ⚠️ THE LABEL HERE MUST BE ONE THAT **ONLY** THE MULTI-LINE FORM CREATES,
    // or this assertion is a check whose title is narrower than what it
    // measures: any label creatable by the single-line arm would satisfy it
    // while proving nothing about the arm it names. Verified against the two
    // files above before being written down.
    expect(creatable, 'the multi-line ALTER TYPE form was not parsed').toContain('AI_REFUSAL');
  });

  it("B7's own three labels are creatable — not merely declared", () => {
    const creatable = migrationLabels();
    for (const label of [
      'CHECKOUT_TOPUP_CREDITED',
      'CHECKOUT_TOPUP_REFUSED',
      'CHECKOUT_TOPUP_DUPLICATE',
    ]) {
      expect(creatable, `${label} has no ALTER TYPE migration`).toContain(label);
    }
  });
});
