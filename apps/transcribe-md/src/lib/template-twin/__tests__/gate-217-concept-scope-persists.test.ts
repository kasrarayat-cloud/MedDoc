// ============================================================================
// #217 — `conceptScope` GETS ITS COLUMN, WRITER AND READ-BACK.
// ----------------------------------------------------------------------------
// ⚠️ THE FIELD HAD FOUR READERS AND NO WRITER, AND EVERY ONE OF THEM WAS DEAD
// CODE IN PRODUCTION. `conceptScope` was parsed and validated at the model
// boundary, read by the fact/mapping matcher, the resolver, the value deriver
// and the auto-confirm gate, and rendered by the confirm surface — and then
// dropped on write, because nothing persisted it. Measured before this change:
// absent from `schema.prisma`, absent from the live table's 22 columns, and
// **0 of 185** production mappings carried it in any form.
//
// That is exactly what ruling #208 forbids: the proposal was "silently
// dropped", which is the failure mode it names alongside "silently kept".
//
// ⚠️ AND THE DANGEROUS HALF OF THE FIX IS THE ATTESTATION HASH, NOT THE COLUMN.
// Certification is attested by `canonicalSha256` over each mapping. It hashes
// `[]` as a value and refuses `undefined` outright. So a read-back that turned
// a NULL column into an empty array would move the sha of EVERY pre-existing
// mapping and de-certify all 185 production rows in one deploy — silently,
// because nothing would throw. The arms below pin both directions: absent must
// not move the sha, and present MUST.
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

// ⚠️ THE SAME TWO MOCKS THE SIBLING GATES CARRY. `certification-lifecycle`
// imports `@meddoc/db` and `@/lib/audit`, whose graph reaches next-auth and
// fails to resolve `next/server` under vitest. Without these the file does not
// IMPORT — and vitest reports "no tests", which is not a pass.
vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { type SemanticMapping } from '../ir';
import { fromPersistedMapping } from '../certification-lifecycle';
import { templateTwinMappingsSha256 } from '../mapping-hash';

const FIELD_ID = `ttf_${'a'.repeat(24)}`;

function base(overrides: Partial<SemanticMapping> = {}): SemanticMapping {
  return {
    fieldId: FIELD_ID,
    sourceType: 'extraction',
    clinicalConcept: 'ros.gastrointestinal.heartburn',
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: 'current',
    laterality: 'optional',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
    ...overrides,
  } as SemanticMapping;
}

/**
 * The read-back, THROUGH THE SHIPPED FUNCTION.
 *
 * ⚠️ THIS USED TO BE A COPY OF THE LOADER'S OMIT RULE, AND THAT MADE EVERY ARM
 * BELOW VACUOUS: the test and the code would have moved together, so deleting
 * the omit from `certification-lifecycle` would have left this file green.
 * `fromPersistedMapping` is exported for exactly this reason.
 */
function readBack(column: unknown): SemanticMapping {
  const b = base();
  return fromPersistedMapping(FIELD_ID, {
    sourceType: b.sourceType,
    clinicalConcept: b.clinicalConcept ?? null,
    expectedDataType: b.expectedDataType,
    polarityBehavior: b.polarityBehavior,
    temporality: b.temporality ?? null,
    laterality: b.laterality ?? null,
    unitPolicy: b.unitPolicy ?? null,
    approvedSynonyms: b.approvedSynonyms,
    required: b.required,
    blankPolicy: b.blankPolicy,
    unmentionedPolicy: null,
    conceptScope: column,
    unknownPolicy: b.unknownPolicy,
    practiceDefault: b.practiceDefault ?? null,
    mappingStatus: 'CERTIFIED',
  });
}

describe('#217 — the column, the round trip, and the attestation', () => {
  it('⚠️ a mapping that predates the column hashes EXACTLY as it did before', () => {
    // The de-certification arm. A NULL column must be indistinguishable from a
    // world where the column never existed.
    const beforeTheColumn = base();
    const afterTheColumn = readBack(null);
    expect(templateTwinMappingsSha256([afterTheColumn])).toBe(
      templateTwinMappingsSha256([beforeTheColumn]),
    );
  });

  it('⚠️ an EMPTY array is elided too — it is not a decision anyone made', () => {
    expect(templateTwinMappingsSha256([readBack([])])).toBe(
      templateTwinMappingsSha256([base()]),
    );
  });

  it('⚠️ NON-VACUITY: a PRESENT scope DOES move the sha', () => {
    // Without this the two arms above are satisfied by a hash that ignores
    // conceptScope entirely — which would mean a doctor's confirmed scope was
    // outside the attestation, and could be changed after certification with no
    // trace. That is the same class of defect, pointed the other way.
    const scoped = readBack([
      'ros.gastrointestinal.heartburn',
      'ros.gastrointestinal.odynophagia',
      'ros.gastrointestinal.dysphagia',
    ]);
    expect(templateTwinMappingsSha256([scoped])).not.toBe(
      templateTwinMappingsSha256([base()]),
    );
  });

  it('the scope survives the round trip intact, in order', () => {
    const scope = [
      'ros.gastrointestinal.heartburn',
      'ros.gastrointestinal.odynophagia',
      'ros.gastrointestinal.dysphagia',
    ];
    expect(readBack(scope).conceptScope).toEqual(scope);
  });

  it('⚠️ a NULL column never becomes an empty array — the key is ABSENT', () => {
    // `canonicalSha256` refuses `undefined` object values outright, so the
    // distinction between "omitted" and "present but undefined" is not
    // cosmetic: setting the key would throw on every certification.
    expect('conceptScope' in readBack(null)).toBe(false);
    expect('conceptScope' in readBack([])).toBe(false);
    expect('conceptScope' in readBack(['ros.gastrointestinal.heartburn'])).toBe(true);
  });

  it('⚠️ THE INSERT WRITES IT, NOT ONLY THE UPDATE — the column is useless without this', async () => {
    // ⚠️ THE FIRST FORM OF #217 ADDED THE COLUMN, THE UPDATE AND THE FIVE
    // READ-BACKS AND LEFT THE INSERT OUT. `create-draft`'s nested
    // `mapping: { create: … }` is the table's ONLY INSERT; the certification
    // writer is an UPDATE and can only change a row that already exists. Without
    // this line `conceptScope` would be NULL for the entire life of every row —
    // a migration that looks like it revived four readers and revived none.
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const src = readFileSync(join(__dirname, '../create-draft.ts'), 'utf-8');
    const createBlock = src.slice(src.indexOf('mapping: {'));
    expect(createBlock).toContain('conceptScope');
    // and NULL when absent, never [] — the attestation argument again
    expect(createBlock).toMatch(/conceptScope:[\s\S]{0,200}Prisma\.DbNull/);
  });

  it('the Prisma model and the migration both carry the column', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const schema = readFileSync(
      join(__dirname, '../../../../../../packages/db/prisma/schema.prisma'),
      'utf-8',
    );
    const model = schema.slice(schema.indexOf('model TemplateTwinSemanticMapping'));
    expect(model.slice(0, model.indexOf('\n}'))).toMatch(/conceptScope\s+Json\?/);

    const migration = readFileSync(
      join(
        __dirname,
        '../../../../../../packages/db/prisma/migrations/20260907000000_r217_concept_scope_column/migration.sql',
      ),
      'utf-8',
    );
    expect(migration).toContain('ADD COLUMN "conceptScope" JSONB');
    // ⚠️ NO DEFAULT CLAUSE — and the check reads the STATEMENTS, not the file.
    // Its first form matched the whole file and failed on the migration's own
    // COMMENT, which explains why a default would be catastrophic. A check that
    // cannot tell prose from the statement it describes is measuring the wrong
    // thing; a default clause here rewrites every existing row into a value and
    // de-certifies all 185 at once.
    const statements = migration
      .split('\n')
      .filter((l) => !l.trim().startsWith('--'))
      .join('\n');
    expect(statements).toContain('ADD COLUMN');
    expect(statements).not.toMatch(/DEFAULT/i);
  });
});
