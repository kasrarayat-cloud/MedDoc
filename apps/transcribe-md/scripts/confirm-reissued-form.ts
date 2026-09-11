// ============================================================================
// THE CONFIRM — ruling #311(d), carrying #312. A RULED MUTATION.
// ----------------------------------------------------------------------------
// The only door:
//
//   bash scripts/run-ruled-mutation.sh --declaration <path> \
//     --in transcribe-md-worker -- \
//     npx tsx scripts/confirm-reissued-form.ts \
//       --compiled-version <uuid> --expect-fields <n> \
//       --expect-certified <n> --expect-confirm <n> --commit
//
// ⚠️ THE PATH IS RELATIVE TO `apps/transcribe-md` — the worker's WORKDIR — for
// the reason `transfer-certification-to-active.ts` records at length: from the
// repo root the `@/*` alias does not resolve and the script dies before line 1.
//
// DRY RUN IS THE DEFAULT. Without `--commit` it runs every guard, prints the
// per-field before -> after, and writes nothing.
//
// ⚠️ THERE IS NO RECOVERY DOOR, AND ROUND TWO IS WHY. A `--reissue-audit` path
// existed for one commit: it wrote the audit rows a failed insert had left
// missing. Round two drove it on a state it could not tell apart — the doctor
// confirming the same ten rows in the panel — and it wrote eleven rows saying
// ruling #311(d)'s hands had confirmed rows the doctor confirmed himself. A
// recovery that cannot tell WHO acted is a false-record generator, so it is
// DELETED rather than patched. If the read-back below ever finds a shortfall,
// the act exits 1, the judgement records it, and any recovery is its own
// declared act, written after reading what actually happened.
//
// ⚠️ THIS FILE IS DELIBERATELY THIN. Every decision about WHAT a row becomes
// lives in `../src/lib/template-twin/confirm-plan.ts`, pure and proved by
// `gate-312-confirm-plan.test.ts`. A second place deciding what a mapping
// becomes is the "one rule, many readers" failure.
//
// ── WHOSE AUTHORITY, WHOSE HANDS — #158 as amended, and #311(d) ─────────────
//   · `approvedById` answers UNDER WHOSE AUTHORITY -> the owning doctor. The
//     writer stamps it on EVERY row of the full set it certifies — all 53, the
//     43 transferred rows included, which had none. That is the approval of the
//     mapping SET the certification will bind to.
//   · the audit metadata answers BY WHOSE HANDS -> one row per CONFIRMED field,
//     plus ONE aggregate row carrying the resulting set sha and certified count,
//     which names the 43 carried over from the transfer so their new approval
//     stamp is attributable rather than reading as ten more confirmations.
// ============================================================================
import prisma from '@meddoc/db';

import {
  fromPersistedMapping,
  updateTemplateTwinMappings,
} from '../src/lib/template-twin/certification-lifecycle';
import { isRegisteredConcept } from '../src/lib/template-twin/concept-registry';
import {
  CONFIRMING_ACTOR,
  RULING_312,
  countFailedGuards,
  missingAuditTargets,
  parseConfirmArgs,
  planConfirmation,
  type Guard,
} from '../src/lib/template-twin/confirm-plan';
import { templateTwinMappingsSha256 } from '../src/lib/template-twin/mapping-hash';
import { logTwinAudit } from '../src/lib/template-twin/twin-audit';

// Parsed BEFORE a connection is opened, so a bad argument and an unreachable
// database can never produce the same failure.
const PARSED = parseConfirmArgs(process.argv.slice(2));
if (!PARSED.ok) {
  console.error(`🔴 confirm: ${PARSED.reason}`);
  console.error('   Nothing was written.');
  process.exit(2);
}
const ARGS = PARSED.args;

function printGuards(guards: readonly Guard[]) {
  for (const [name, got, want] of guards) {
    const ok = JSON.stringify(got) === JSON.stringify(want);
    console.log(`  guard ${ok ? '✓' : '🔴'} ${name}: ${JSON.stringify(got)} (expect ${JSON.stringify(want)})`);
  }
}

const loadVersion = (id: string) =>
  prisma.templateTwinCompiledVersion.findUnique({
    where: { id },
    include: {
      noteTemplate: { select: { id: true, name: true, status: true, doctorId: true, practiceId: true } },
      certification: { select: { id: true } },
      fields: { include: { mapping: true }, orderBy: { displayOrder: 'asc' } },
    },
  });

type LoadedField = NonNullable<Awaited<ReturnType<typeof loadVersion>>>['fields'][number];

// ⚠️ EVERY ROW IS PROJECTED BY `fromPersistedMapping` — the writer's own
// reader — so the optimistic lock and the set sha hash exactly what the writer
// hashes, and no column (`unmentionedPolicy`, `conceptScope`) is dropped by a
// hand-rolled projection. The transfer tool lost two columns that way.
const project = (f: LoadedField) =>
  fromPersistedMapping(f.fieldId, f.mapping as unknown as Parameters<typeof fromPersistedMapping>[1]);

/** The audit targets this door has already written for this version. */
async function writtenAuditTargets(compiledVersionId: string): Promise<string[]> {
  const rows = await prisma.auditLog.findMany({
    where: {
      action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
      AND: [
        { metadata: { path: ['confirmingActor'], equals: CONFIRMING_ACTOR } },
        { metadata: { path: ['compiledVersionId'], equals: compiledVersionId } },
      ],
    },
    select: { targetId: true },
  });
  return rows.map((r) => r.targetId).filter((t): t is string => typeof t === 'string');
}

async function main() {
  const actStartedAt = new Date();
  const db = new URL(process.env.DATABASE_URL ?? 'postgres://x/x');
  console.log(`db target: ${db.hostname}${db.pathname}`);
  console.log(`mode     : ${ARGS.commit ? '⚠️  COMMIT (writes)' : 'DRY RUN'}`);
  console.log(`ruling   : ${CONFIRMING_ACTOR} authority, ${RULING_312.ruling} decisions`);

  const compiled = await loadVersion(ARGS.compiledVersion);
  if (!compiled) throw new Error(`compiled version ${ARGS.compiledVersion} not found`);
  console.log(
    `target   : ${compiled.noteTemplate.name} [${compiled.noteTemplate.status}]  ` +
      `${compiled.certificationStatus}  (${compiled.fields.length} fields)`,
  );

  const doctorId = compiled.noteTemplate.doctorId!;
  const practiceId = compiled.noteTemplate.practiceId!;
  const doctor = await prisma.user.findUnique({ where: { id: doctorId }, select: { id: true, email: true } });
  if (!doctor) throw new Error('owning doctor not found');

  // ── THE I/O-SIDE PREMISES — the planner cannot see these ─────────────────
  const unmapped = compiled.fields.filter((f) => !f.mapping).length;
  const confirmedConcepts = RULING_312.decisions
    .map((d) => d.confirmAs.clinicalConcept)
    .filter((c): c is string => c !== null);
  const offRegistry = confirmedConcepts.filter((c) => !isRegisteredConcept(c));
  const fields = compiled.fields
    .filter((f) => f.mapping)
    .map((f) => ({ fieldId: f.fieldId, displayOrder: f.displayOrder, originalLabel: f.originalLabel, mapping: project(f) }));
  // ⚠️ THE WHOLE SET, AS JUDGED — the 43 transferred rows included. The same
  // hash the writer's optimistic lock computes, compared here against the value
  // the decisions were made on rather than against this run's own read.
  const expectedMappingsSha256 = templateTwinMappingsSha256(fields.map((f) => f.mapping));
  const premises: Guard[] = [
    ['the template is a DRAFT (nothing active is touched)', compiled.noteTemplate.status, 'draft'],
    ['the version awaits confirmation', compiled.certificationStatus, 'NEEDS_CONFIRMATION'],
    ['a certification row exists for the version', compiled.certification !== null, false],
    ['fields with no persisted mapping', unmapped, 0],
    // An off-registry concept is nulled by the next compile, so writing one is a
    // confirmation that silently un-confirms itself. Measured in THIS runtime.
    ["confirmed concepts THIS runtime's registry refuses", offRegistry, []],
    ['the whole mapping set is byte-identical to the judged one', expectedMappingsSha256, RULING_312.judgedSetSha256],
    // Nothing of this act's may exist before it: a prior run, or a stray row.
    ['audit rows already naming this act for this version', (await writtenAuditTargets(compiled.id)).length, 0],
  ];

  const plan = planConfirmation({
    compiledVersionId: compiled.id,
    fields,
    table: RULING_312,
    expect: { fields: ARGS.expectFields, alreadyCertified: ARGS.expectCertified, confirm: ARGS.expectConfirm },
  });

  console.log('\n── GUARDS ──');
  printGuards(premises);
  printGuards(plan.guards);
  const bad = countFailedGuards(premises) + countFailedGuards(plan.guards);
  if (bad > 0 || !plan.ok) {
    throw new Error(`${bad} guard(s) failed — refusing. Nothing was written.`);
  }

  console.log('\n── PER-FIELD, BEFORE -> AFTER (the ten; the other rows pass through unchanged) ──');
  for (const m of plan.moves) {
    const d = RULING_312.decisions.find((x) => x.fieldId === m.fieldId)!;
    console.log(
      `  ${String(m.displayOrder).padStart(2)} ${m.label.slice(0, 32).padEnd(34)}` +
        `${String(m.from.clinicalConcept ?? 'NULL').padEnd(36)}/${m.from.sourceType.padEnd(14)}${m.from.status.padEnd(19)}-> ` +
        `${String(m.to.clinicalConcept ?? 'NULL').padEnd(36)}/${m.to.sourceType.padEnd(14)}certified`,
    );
    console.log(`       why: ${d.why}`);
  }
  console.log(`  confirmed: ${plan.moves.length} · passed through: ${plan.payload.length - plan.moves.length}`);
  console.log(`  audit rows this act will write: ${plan.moves.length + 1} (${plan.moves.length} per-field + 1 for the set)`);

  if (!ARGS.commit) {
    console.log('\nDRY RUN — nothing written. Re-run with --commit through run-ruled-mutation.sh.');
    return;
  }

  // ── THE ACT, THROUGH THE ONE WRITER ──────────────────────────────────────
  await updateTemplateTwinMappings({
    noteTemplateId: compiled.noteTemplate.id,
    actor: { userId: doctor.id, userEmail: doctor.email, practiceId },
    expectedMappingsSha256,
    mappings: plan.payload,
  });

  // ── READ THE WRITE BACK FIRST, so the audit describes what LANDED ─────────
  const after = await loadVersion(compiled.id);
  if (!after) throw new Error('compiled version vanished after the write');
  const rows = after.fields;
  const afterSha = templateTwinMappingsSha256(rows.filter((f) => f.mapping).map(project));
  const certifiedAfter = rows.filter((f) => f.mapping?.mappingStatus === 'CERTIFIED').length;
  const mappingIdByField = new Map(rows.filter((f) => f.mapping).map((f) => [f.fieldId, f.mapping!.id]));

  // ── BY WHOSE HANDS: one append-only row per CONFIRMED field, one for the set ─
  const common = {
    machineConfirmed: true,
    confirmingActor: CONFIRMING_ACTOR,
    onOwnerAuthorization:
      'ruling #311(d): the owner authorised confirmation on his behalf; approvedById is the ' +
      'owning doctor (#158 as amended: under whose authority, not by whose hands)',
    decisionRuling: RULING_312.ruling,
    reason:
      "ruled mutation: the re-issued form's re-proposed rows confirmed. The declaration is the " +
      'account of why: ' +
      (process.env.RULED_MUTATION_DECLARATION ?? '<not run through run-ruled-mutation.sh>'),
    declarationCommit: process.env.RULED_MUTATION_DECL_COMMIT ?? null,
    compiledVersionId: compiled.id,
  };
  for (const m of plan.moves) {
    await logTwinAudit({
      action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
      targetType: 'TemplateTwinSemanticMapping',
      targetId: mappingIdByField.get(m.fieldId)!,
      userId: doctor.id,
      userEmail: doctor.email,
      practiceId,
      metadata: {
        ...common,
        from: m.from,
        to: m.to,
        visitMetadata: m.to.sourceType === 'visit_metadata',
        fieldId: m.fieldId,
        displayOrder: m.displayOrder,
      },
    });
  }
  await logTwinAudit({
    action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
    targetType: 'TemplateTwinCompiledVersion',
    targetId: compiled.id,
    userId: doctor.id,
    userEmail: doctor.email,
    practiceId,
    metadata: {
      ...common,
      // ⚠️ THE SET, NOT TEN MORE CONFIRMATIONS. The writer stamps approval on
      // every row it certifies; 43 of these were certified by the transfer and
      // carry no decision of this act. This row says so, and carries the sha
      // the certification will bind to.
      approvedAsASet: rows.length,
      confirmedFieldIds: plan.moves.map((m) => m.fieldId),
      carriedOverFromTransfer: rows.length - plan.moves.length,
      mappingsSha256: afterSha,
      certifiedMappingCount: certifiedAfter,
    },
  });

  // ── END STATE — asserted, never assumed ──────────────────────────────────
  const approved = rows.filter((f) => f.mapping?.approvedById === doctor.id && f.mapping?.approvedAt).length;
  const wrong = plan.moves.filter((m) => {
    const r = rows.find((f) => f.fieldId === m.fieldId)?.mapping;
    return !r || r.sourceType !== m.to.sourceType || r.clinicalConcept !== m.to.clinicalConcept;
  }).length;
  const owedTargets = [...plan.moves.map((m) => mappingIdByField.get(m.fieldId)!), compiled.id];
  const auditMissing = missingAuditTargets(owedTargets, await writtenAuditTargets(compiled.id));
  // ⚠️ THE WRITER'S OWN SET-LEVEL ROW IS CHECKED TOO. It is written after the
  // writer's transaction and `logAudit` never throws, so its absence would
  // otherwise be silent — and it is the record of the set the certification
  // binds to.
  const writerRow = await prisma.auditLog.findFirst({
    where: {
      action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
      targetId: compiled.noteTemplate.id,
      timestamp: { gte: actStartedAt },
      metadata: { path: ['mappingsSha256'], equals: afterSha },
    },
    select: { id: true },
  });
  const end: Guard[] = [
    ['fields present', rows.length, ARGS.expectFields],
    ['mappings CERTIFIED', certifiedAfter, ARGS.expectFields],
    ['mappings approved by the owning doctor, with a time', approved, ARGS.expectFields],
    ['confirmed rows not carrying their decision', wrong, 0],
    ['version still awaiting its proof (certification is a separate act)', after.certificationStatus, 'NEEDS_CONFIRMATION'],
    ['a certification row exists', after.certification !== null, false],
    // ⚠️ `logAudit` never throws, so the only way to know the record exists is
    // to read it back. A shortfall exits 1 and becomes the judgement's finding;
    // there is deliberately no automatic re-issue (see the header).
    ["this act's audit rows owed and NOT written", auditMissing, []],
    ["the writer's set-level audit row carrying the resulting sha", writerRow !== null, true],
  ];
  console.log('\n── END STATE ──');
  console.log(`  resulting mapping-set sha: ${afterSha}`);
  printGuards(end);
  if (countFailedGuards(end) > 0) throw new Error('END-STATE ASSERTION FAILED — see the numbers above.');
  console.log(`🟢 confirm complete: ${plan.moves.length} confirmed under ${CONFIRMING_ACTOR}. Certification runs separately.`);
}

main()
  .catch((e) => {
    console.error('🔴', e instanceof Error ? e.message : e);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
