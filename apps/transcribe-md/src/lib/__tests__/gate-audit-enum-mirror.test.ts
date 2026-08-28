// ============================================================================
// THE AUDIT ENUM HAS TWO SOURCES OF TRUTH, AND NOTHING WAS CHECKING THEM
// ----------------------------------------------------------------------------
// `AuditAction` exists twice: as a real Postgres enum in `schema.prisma`, and as
// a hand-mirrored union in `lib/audit.ts` (deliberately — the comment there
// explains the `@meddoc/db` barrel's `any`).
//
// ⚠️ THE TWO FAILURE MODES ARE ASYMMETRIC, WHICH IS WHY THIS GATE EXISTS.
//   · label in schema only  -> type-checks NOWHERE, caught immediately.
//   · label in mirror only  -> type-checks FINE and fails at the DATABASE, at
//     run time, on a write path that "never throws" — so it fails SILENTLY.
// The second is the dangerous direction: an audit row that was supposed to
// record something and instead recorded nothing, which is the exact shape the
// template-deletion gap already cost this programme once.
//
// Found while adding four labels: the schema change alone left tsc red, and the
// mirror was only discovered because of it. Nothing would have caught the
// reverse.
// ============================================================================
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = join(__dirname, '..', '..', '..', '..', '..');
const SCHEMA = join(REPO, 'packages', 'db', 'prisma', 'schema.prisma');
const AUDIT = join(__dirname, '..', 'audit.ts');

function schemaLabels(): string[] {
  const src = readFileSync(SCHEMA, 'utf8');
  const start = src.indexOf('enum AuditAction {');
  expect(start, 'enum AuditAction not found in schema.prisma').toBeGreaterThan(-1);
  const body = src.slice(start, src.indexOf('\n}', start));
  return [...body.matchAll(/^ {2}([A-Z][A-Z0-9_]*)$/gm)].map((m) => m[1]);
}

function mirrorLabels(): string[] {
  // ⚠️ COMMENTS ARE STRIPPED FIRST, AND THAT IS NOT TIDINESS. The first version
  // sliced to the next `;` after the last known label — and the explanatory
  // comment written directly above that label contains the word "time;". The
  // probe truncated at a semicolon inside PROSE and reported 105 of 109 labels,
  // silently dropping exactly the four this gate was written to check. A parser
  // that reads comments as code is measuring the wrong document.
  const src = readFileSync(AUDIT, 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');
  const start = src.indexOf('export type AuditAction =');
  expect(start, 'the mirrored union was not found').toBeGreaterThan(-1);
  const body = src.slice(start, src.indexOf(';', start) + 1);
  return [...body.matchAll(/\|\s*'([A-Z][A-Z0-9_]*)'/g)].map((m) => m[1]);
}

describe('AuditAction — schema and mirror cannot drift', () => {
  it('both sides are populated — the arm is not vacuous', () => {
    // A regex that stops matching would make every assertion below pass by
    // having nothing to compare. This is the arm that guards the arms.
    expect(schemaLabels().length).toBeGreaterThan(100);
    expect(mirrorLabels().length).toBeGreaterThan(100);
  });

  it('every MIRRORED label exists in the schema — the silent-failure direction', () => {
    const schema = new Set(schemaLabels());
    const orphans = mirrorLabels().filter((l) => !schema.has(l));
    expect(
      orphans,
      'these labels type-check but would fail at the DATABASE on write',
    ).toEqual([]);
  });

  it('the four batched labels are present on BOTH sides', () => {
    const schema = new Set(schemaLabels());
    const mirror = new Set(mirrorLabels());
    for (const l of [
      'EM_OMITTED_IN_SIGNED_ARTIFACT',
      'TEMPLATE_DELETED',
      'TEMPLATE_ARCHIVED',
      'ICD_CODE_AUTO_ACCEPTED',
    ]) {
      expect(schema.has(l), `${l} missing from schema.prisma`).toBe(true);
      expect(mirror.has(l), `${l} missing from the audit.ts mirror`).toBe(true);
    }
  });

  it('the migration that adds them is present and idempotent', () => {
    const sql = readFileSync(
      join(REPO, 'packages', 'db', 'prisma', 'migrations',
           '20260829000000_batched_audit_enum_labels', 'migration.sql'),
      'utf8',
    );
    for (const l of ['EM_OMITTED_IN_SIGNED_ARTIFACT', 'TEMPLATE_DELETED',
                     'TEMPLATE_ARCHIVED', 'ICD_CODE_AUTO_ACCEPTED']) {
      expect(sql).toContain(`ADD VALUE IF NOT EXISTS '${l}'`);
    }
    // Postgres has no DROP VALUE; a migration that is not idempotent can wedge
    // a four-statement change half-way through.
    expect(sql.match(/ADD VALUE IF NOT EXISTS/g)?.length).toBe(4);
  });
});
