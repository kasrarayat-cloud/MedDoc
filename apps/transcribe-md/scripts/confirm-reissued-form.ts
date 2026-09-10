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
// ⚠️ THIS FILE IS DELIBERATELY THIN. Every decision about WHAT a row becomes
// lives in `../src/lib/template-twin/confirm-plan.ts`, pure and proved by
// `gate-312-confirm-plan.test.ts`. This wrapper reads, states guards, calls the
// planner and the ONE writer, and prints. A second place deciding what a
// mapping becomes is the "one rule, many readers" failure.
//
// ── WHOSE AUTHORITY, WHOSE HANDS — #158 as amended, and #311(d) ─────────────
//   · `approvedById` answers UNDER WHOSE AUTHORITY -> the owning doctor. The
//     schema's FK cannot name a ruling, and minting a machine user would weaken
//     the ownership check `loadOwnedCompilation` performs.
//   · the audit metadata answers BY WHOSE HANDS -> `confirmingActor: 'ruling
//     #311(d)'`, one append-only row per CONFIRMED field, and no row for a field
//     this act did not confirm. An audit row claiming a confirmation that did not
//     happen is a false record.
// ============================================================================
import prisma from '@meddoc/db';

import {
  fromPersistedMapping,
  updateTemplateTwinMappings,
} from '../src/lib/template-twin/certification-lifecycle';
import { isRegisteredConcept } from '../src/lib/template-twin/concept-registry';
import {
  RULING_312,
  countFailedGuards,
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

async function main() {
  const db = new URL(process.env.DATABASE_URL ?? 'postgres://x/x');
  console.log(`db target: ${db.hostname}${db.pathname}`);
  console.log(`mode     : ${ARGS.commit ? '⚠️  COMMIT (writes)' : 'DRY RUN'}`);
  console.log(`ruling   : #311(d) authority, ${RULING_312.ruling} decisions`);

  const compiled = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: ARGS.compiledVersion },
    include: {
      noteTemplate: { select: { id: true, name: true, status: true, doctorId: true, practiceId: true } },
      certification: { select: { id: true } },
      fields: { include: { mapping: true }, orderBy: { displayOrder: 'asc' } },
    },
  });
  if (!compiled) throw new Error(`compiled version ${ARGS.compiledVersion} not found`);
  console.log(
    `target   : ${compiled.noteTemplate.name} [${compiled.noteTemplate.status}]  ` +
      `${compiled.certificationStatus}  (${compiled.fields.length} fields)`,
  );

  // ── THE I/O-SIDE PREMISES — the planner cannot see these ─────────────────
  const unmapped = compiled.fields.filter((f) => !f.mapping).length;
  const confirmedConcepts = RULING_312.decisions
    .map((d) => d.confirmAs.clinicalConcept)
    .filter((c): c is string => c !== null);
  const offRegistry = confirmedConcepts.filter((c) => !isRegisteredConcept(c));
  const premises: Guard[] = [
    ['the template is a DRAFT (nothing active is touched)', compiled.noteTemplate.status, 'draft'],
    ['the version awaits confirmation', compiled.certificationStatus, 'NEEDS_CONFIRMATION'],
    ['a certification row exists for the version', compiled.certification !== null, false],
    ['fields with no persisted mapping', unmapped, 0],
    // An off-registry concept is nulled by the next compile, so writing one is a
    // confirmation that silently un-confirms itself. Measured in THIS runtime.
    ['confirmed concepts THIS runtime\'s registry refuses', offRegistry, []],
  ];

  // ⚠️ EVERY ROW IS PROJECTED BY `fromPersistedMapping` — the writer's own
  // reader — so the optimistic lock below hashes exactly what the writer will
  // hash, and no column (`unmentionedPolicy`, `conceptScope`) is dropped by a
  // hand-rolled projection. The transfer tool lost two columns that way.
  const project = (fieldId: string, row: NonNullable<(typeof compiled.fields)[number]['mapping']>) =>
    fromPersistedMapping(fieldId, row as unknown as Parameters<typeof fromPersistedMapping>[1]);
  const fields = compiled.fields
    .filter((f) => f.mapping)
    .map((f) => ({
      fieldId: f.fieldId,
      displayOrder: f.displayOrder,
      originalLabel: f.originalLabel,
      mapping: project(f.fieldId, f.mapping!),
    }));

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

  const doctorId = compiled.noteTemplate.doctorId!;
  const practiceId = compiled.noteTemplate.practiceId!;
  const doctor = await prisma.user.findUnique({ where: { id: doctorId }, select: { id: true, email: true } });
  if (!doctor) throw new Error('owning doctor not found');

  if (!ARGS.commit) {
    console.log('\nDRY RUN — nothing written. Re-run with --commit through run-ruled-mutation.sh.');
    return;
  }

  // ── THE ACT, THROUGH THE ONE WRITER ──────────────────────────────────────
  const expectedMappingsSha256 = templateTwinMappingsSha256(fields.map((f) => f.mapping));
  await updateTemplateTwinMappings({
    noteTemplateId: compiled.noteTemplate.id,
    actor: { userId: doctor.id, userEmail: doctor.email, practiceId },
    expectedMappingsSha256,
    mappings: plan.payload,
  });

  // ── BY WHOSE HANDS: one append-only row per CONFIRMED field ─────────────
  const mappingIdByField = new Map(compiled.fields.map((f) => [f.fieldId, f.mapping!.id]));
  for (const m of plan.moves) {
    await logTwinAudit({
      action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
      targetType: 'TemplateTwinSemanticMapping',
      targetId: mappingIdByField.get(m.fieldId)!,
      userId: doctor.id,
      userEmail: doctor.email,
      practiceId,
      metadata: {
        machineConfirmed: true,
        confirmingActor: 'ruling #311(d)',
        onOwnerAuthorization:
          'ruling #311(d): the owner authorised confirmation on his behalf; approvedById is the ' +
          'owning doctor (#158 as amended: under whose authority, not by whose hands)',
        decisionRuling: RULING_312.ruling,
        from: m.from,
        to: m.to,
        visitMetadata: m.to.sourceType === 'visit_metadata',
        reason:
          'ruled mutation: the re-issued form\'s re-proposed rows confirmed. The declaration is the ' +
          'account of why: ' +
          (process.env.RULED_MUTATION_DECLARATION ?? '<not run through run-ruled-mutation.sh>'),
        declarationCommit: process.env.RULED_MUTATION_DECL_COMMIT ?? null,
        compiledVersionId: compiled.id,
        fieldId: m.fieldId,
        displayOrder: m.displayOrder,
      },
    });
  }

  // ── END STATE — asserted, never assumed ──────────────────────────────────
  const after = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: compiled.id },
    include: {
      certification: { select: { id: true } },
      fields: { include: { mapping: true } },
    },
  });
  if (!after) throw new Error('compiled version vanished after the write');
  const rows = after.fields;
  const certified = rows.filter((f) => f.mapping?.mappingStatus === 'CERTIFIED').length;
  const approved = rows.filter((f) => f.mapping?.approvedById === doctor.id && f.mapping?.approvedAt).length;
  const wrong = plan.moves.filter((m) => {
    const r = rows.find((f) => f.fieldId === m.fieldId)?.mapping;
    return !r || r.sourceType !== m.to.sourceType || r.clinicalConcept !== m.to.clinicalConcept;
  }).length;
  const end: Guard[] = [
    ['fields present', rows.length, ARGS.expectFields],
    ['mappings CERTIFIED', certified, ARGS.expectFields],
    ['mappings approved by the owning doctor, with a time', approved, ARGS.expectFields],
    ['confirmed rows not carrying their decision', wrong, 0],
    ['version still awaiting its proof (certification is a separate act)', after.certificationStatus, 'NEEDS_CONFIRMATION'],
    ['a certification row exists', after.certification !== null, false],
  ];
  console.log('\n── END STATE ──');
  printGuards(end);
  if (countFailedGuards(end) > 0) throw new Error('END-STATE ASSERTION FAILED — see the numbers above.');
  console.log(`🟢 confirm complete: ${plan.moves.length} confirmed under #311(d). Certification runs separately.`);
}

main()
  .catch((e) => {
    console.error('🔴', e instanceof Error ? e.message : e);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
