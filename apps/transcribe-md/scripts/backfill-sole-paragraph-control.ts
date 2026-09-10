// ============================================================================
// #313 O5 — WRITE `soleParagraphControl` INTO ONE DRAFT'S STORED COMPILED IR.
// ----------------------------------------------------------------------------
// A RULED MUTATION. The only door is:
//
//   bash scripts/run-ruled-mutation.sh --declaration <path> \
//     --in transcribe-md-worker -- \
//     npx tsx scripts/backfill-sole-paragraph-control.ts \
//       --compiled-version <uuid> --expect-fields <n> \
//       --expect-groups <n> --expect-members <n> --commit
//
// The path is RELATIVE TO `apps/transcribe-md` — the worker image's WORKDIR —
// for the reason `transfer-certification-to-active.ts` records: from the repo
// root the `@/*` alias does not resolve and the script dies before line one.
//
// DRY RUN IS THE DEFAULT. Without `--commit` it reads everything, runs every
// guard, prints the groups the new IR would form, and writes nothing.
//
// ── WHAT IT DOES ────────────────────────────────────────────────────────────
// Reads the stored `compiledDocumentIr` and the stored source bytes (through
// the artifact store's verified read), recompiles those bytes with THIS
// compiler, and — only if the recompile is the same document in every property
// but the new one — writes the stored JSON back with `soleParagraphControl:
// true` added to exactly the fields the compiler flags. Nothing else moves:
// not the structure hash, not the static hash, not a field id, not a mapping.
//
// ── WHAT IT REFUSES ─────────────────────────────────────────────────────────
// A CERTIFIED version or one with a certification record (ruling #313 O5: the
// active `18a7ae19` is not touched, and a certified row is immutable anyway), a
// template that is not a DRAFT, any fill manifest stored against the version
// (the #247 review-vs-signed window), any drift between the stored IR and the
// recompile, and any disagreement with the declared counts.
//
// Every decision is in `src/lib/template-twin/sole-paragraph-backfill.ts`, pure
// and proved by `gate-313-backfill.test.ts`. This file reads, prints, writes.
//
// ── THE AUDIT ROW ───────────────────────────────────────────────────────────
// One append-only row, action `TEMPLATE_TWIN_COMPILED`: of the eleven twin
// actions it is the only one whose meaning is "the compiled IR of this version
// was produced/changed by the compiler". `MAPPING_UPDATED` would be false (no
// mapping moves) and a new action would need a Prisma enum migration for one
// row. The metadata names ruling #313 and the declaration.
// ============================================================================
import { createHash } from 'node:crypto';

import prisma from '@meddoc/db';

import { compileTemplateDocx } from '../src/lib/note-template-docx/compiler';
import { fromPersistedMapping } from '../src/lib/template-twin/certification-lifecycle';
import { canonicalSha256 } from '../src/lib/template-twin/canonical';
import { createTemplateTwinArtifactStore } from '../src/lib/template-twin/storage';
import { logTwinAudit } from '../src/lib/template-twin/twin-audit';
import {
  parseSoleParagraphBackfillArgs,
  planSoleParagraphBackfill,
} from '../src/lib/template-twin/sole-paragraph-backfill';
import type { Prisma } from '@prisma/client';

function die(message: string): never {
  console.error(`🔴 backfill-313: ${message}`);
  console.error('   Nothing was written.');
  process.exit(1);
}

async function main(): Promise<void> {
  // ⚠️ PARSED BEFORE ANYTHING IS OPENED, so a bad argument and an unreachable
  // database cannot produce the same failure.
  const parsed = parseSoleParagraphBackfillArgs(process.argv.slice(2));
  if (!parsed.ok) {
    console.error(`🔴 backfill-313: ${parsed.reason}`);
    process.exit(2);
  }
  const args = parsed.args;
  const dbUrl = new URL(process.env.DATABASE_URL ?? 'postgres://x/x');
  console.log('=== #313 O5 — soleParagraphControl backfill ===');
  console.log(`db target : ${dbUrl.hostname}/${dbUrl.pathname.replace('/', '')}`);
  console.log(`mode      : ${args.commit ? '⚠️  COMMIT (writes one column of one row)' : 'DRY RUN'}`);
  console.log(`target    : ${args.compiledVersionId}`);
  console.log(
    `expect    : ${args.expectFields} fields, ${args.expectGroups} groups, ${args.expectMembers} members`,
  );

  const loadRow = () =>
    prisma.templateTwinCompiledVersion.findUnique({
      where: { id: args.compiledVersionId },
      select: {
        id: true,
        practiceId: true,
        compiledDocumentIr: true,
        structureSha256: true,
        staticContentSha256: true,
        certificationStatus: true,
        certification: { select: { id: true } },
        noteTemplate: { select: { id: true, status: true, doctorId: true } },
        sourceArtifact: {
          select: { id: true, objectKey: true, sha256: true, sizeBytes: true, practiceId: true },
        },
        fields: { include: { mapping: true }, orderBy: { displayOrder: 'asc' } },
        _count: { select: { fills: true } },
      },
    });
  const row = await loadRow();
  if (!row) die(`compiled version ${args.compiledVersionId} not found`);
  if (!row.sourceArtifact.objectKey) die('the source artifact has no objectKey — its bytes are unreachable');
  if (row.sourceArtifact.practiceId !== row.practiceId) die('source artifact belongs to a different practice');

  // ── the stored bytes, through the store's VERIFIED read (sha + size) ───────
  const store = createTemplateTwinArtifactStore();
  const bytes = await store.readSourceArtifact({
    practiceId: row.sourceArtifact.practiceId,
    objectKey: row.sourceArtifact.objectKey,
    expectedSha256: row.sourceArtifact.sha256,
    expectedSizeBytes: row.sourceArtifact.sizeBytes,
  });
  const bytesSha256 = createHash('sha256').update(bytes).digest('hex');
  const recompiled = compileTemplateDocx(new Uint8Array(bytes));

  const missingMapping = row.fields.filter((field) => !field.mapping);
  if (missingMapping.length > 0) die(`${missingMapping.length} field(s) have no persisted mapping`);
  const mappings = row.fields.map((field) =>
    fromPersistedMapping(
      field.fieldId,
      field.mapping as unknown as Parameters<typeof fromPersistedMapping>[1],
    ),
  );

  const plan = planSoleParagraphBackfill({
    storedIr: row.compiledDocumentIr,
    recompiled,
    mappings,
    certificationStatus: row.certificationStatus,
    hasCertificationRecord: row.certification !== null,
    templateStatus: row.noteTemplate.status,
    persistedFieldCount: row.fields.length,
    columnStructureSha256: row.structureSha256,
    columnStaticContentSha256: row.staticContentSha256,
    artifactSha256: row.sourceArtifact.sha256,
    bytesSha256,
    fillManifestCount: row._count.fills,
    expect: { fields: args.expectFields, groups: args.expectGroups, members: args.expectMembers },
  });

  console.log('\n── GUARDS ──');
  for (const [name, got, want] of plan.guards) {
    const ok = canonicalSha256(got) === canonicalSha256(want);
    console.log(`  ${ok ? '✓' : '🔴'} ${name}: ${JSON.stringify(got)} (expect ${JSON.stringify(want)})`);
  }

  const orderById = new Map(recompiled.fields.map((field) => [field.fieldId, field.displayOrder]));
  console.log(`\n── soleParagraphControl: ${plan.flaggedFieldIds.length} field(s) flagged by this compiler ──`);
  console.log(`  display orders: ${plan.flaggedFieldIds.map((id) => orderById.get(id)).join(',')}`);
  console.log(`\n── BULLET GROUPS under the current mappings: ${plan.groups.length} groups, ${plan.members} members ──`);
  for (const group of plan.groups) {
    // Display orders only: an alias is the blank form's own label, never
    // patient data, but a count and positions are all a declaration needs.
    console.log(
      `  ${group.memberFieldIds.length} × d${group.memberFieldIds.map((id) => orderById.get(id)).join(',d')}`,
    );
  }

  if (plan.failed > 0 || plan.next === null) {
    die(`${plan.failed} guard(s) failed — refusing.`);
  }
  if (!args.commit) {
    console.log('\nDRY RUN — nothing written. Re-run with --commit through run-ruled-mutation.sh.');
    return;
  }

  // ── THE ACT: one column of one row, re-checked inside the transaction ─────
  const expectedStoredSha = canonicalSha256(row.compiledDocumentIr);
  await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const again = await tx.templateTwinCompiledVersion.findUnique({
        where: { id: args.compiledVersionId },
        select: {
          compiledDocumentIr: true,
          certificationStatus: true,
          certification: { select: { id: true } },
          noteTemplate: { select: { status: true } },
        },
      });
      if (
        !again ||
        canonicalSha256(again.compiledDocumentIr) !== expectedStoredSha ||
        again.certificationStatus === 'CERTIFIED' ||
        again.certification !== null ||
        again.noteTemplate.status !== 'draft'
      ) {
        throw new Error('the row changed between the read and the write — refusing');
      }
      const updated = await tx.templateTwinCompiledVersion.updateMany({
        where: { id: args.compiledVersionId, certificationStatus: { not: 'CERTIFIED' } },
        data: { compiledDocumentIr: plan.next as Prisma.InputJsonValue },
      });
      if (updated.count !== 1) throw new Error(`expected to update 1 row, updated ${updated.count}`);
    },
    { isolationLevel: 'Serializable' },
  );

  // ── END STATE: read back and re-derive, never trust the write ─────────────
  const after = await loadRow();
  if (!after) throw new Error('row vanished after the write');
  const readBackOk = canonicalSha256(after.compiledDocumentIr) === canonicalSha256(plan.next);
  const replan = planSoleParagraphBackfill({
    storedIr: after.compiledDocumentIr,
    recompiled,
    mappings,
    certificationStatus: after.certificationStatus,
    hasCertificationRecord: after.certification !== null,
    templateStatus: after.noteTemplate.status,
    persistedFieldCount: after.fields.length,
    columnStructureSha256: after.structureSha256,
    columnStaticContentSha256: after.staticContentSha256,
    artifactSha256: after.sourceArtifact.sha256,
    bytesSha256,
    fillManifestCount: after._count.fills,
    expect: { fields: args.expectFields, groups: args.expectGroups, members: args.expectMembers },
  });
  // The re-plan MUST now refuse on exactly one guard: the property is present.
  const onlyPresenceFails =
    replan.guards.filter(([, got, want]) => canonicalSha256(got) !== canonicalSha256(want))
      .map(([name]) => name)
      .join('|') === 'stored IR carries no soleParagraphControl yet';
  console.log('\n── END STATE ──');
  console.log(`  read-back IR == written IR           : ${readBackOk}`);
  console.log(`  structureSha256 column unchanged     : ${after.structureSha256 === row.structureSha256}`);
  console.log(`  staticContentSha256 column unchanged : ${after.staticContentSha256 === row.staticContentSha256}`);
  console.log(`  re-plan refuses ONLY on "already present": ${onlyPresenceFails}`);
  if (!readBackOk || after.structureSha256 !== row.structureSha256 || !onlyPresenceFails) {
    throw new Error('END-STATE ASSERTION FAILED — see the lines above.');
  }

  await logTwinAudit({
    action: 'TEMPLATE_TWIN_COMPILED',
    targetType: 'TemplateTwinCompiledVersion',
    targetId: args.compiledVersionId,
    userId: row.noteTemplate.doctorId,
    practiceId: row.practiceId,
    metadata: {
      ruling: '#313',
      act: 'backfill-sole-paragraph-control',
      decision: 'O5 — a ruled, declared, in-place write to the DRAFT compiled IR',
      machineConfirmed: true,
      property: 'soleParagraphControl',
      fieldsFlagged: plan.flaggedFieldIds.length,
      bulletGroups: plan.groups.length,
      bulletGroupMembers: plan.members,
      structureSha256: row.structureSha256,
      staticContentSha256: row.staticContentSha256,
      storedIrSha256Before: expectedStoredSha,
      storedIrSha256After: canonicalSha256(after.compiledDocumentIr),
      declaration:
        process.env.RULED_MUTATION_DECLARATION ?? '<not run through run-ruled-mutation.sh>',
      declarationCommit: process.env.RULED_MUTATION_DECL_COMMIT ?? null,
    },
  });
  console.log(
    `🟢 backfill complete: ${plan.flaggedFieldIds.length} field(s) flagged, ` +
      `${plan.groups.length} group(s) / ${plan.members} member(s) under the current mappings.`,
  );
}

// ⚠️ ONLY WHEN INVOKED DIRECTLY — importing this module must never run the act
// (canon 143; the `re-issue-form.ts` precedent).
const invokedDirectly = (() => {
  const entry = process.argv[1];
  return Boolean(entry && /backfill-sole-paragraph-control\.(ts|js)$/.test(entry));
})();

if (invokedDirectly) {
  main()
    .catch((error) => {
      console.error('🔴 backfill-313:', error instanceof Error ? error.message : error);
      process.exitCode = 1;
    })
    .finally(() => prisma.$disconnect());
}
