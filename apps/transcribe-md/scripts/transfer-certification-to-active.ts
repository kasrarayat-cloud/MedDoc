// ============================================================================
// TRANSFER THE CERTIFIED DISPOSITIONS ONTO THE ACTIVE COMPILED VERSION.
// ----------------------------------------------------------------------------
// A RULED MUTATION. The only door is:
//
//   bash scripts/run-ruled-mutation.sh --declaration <path> -- \
//     npx tsx apps/transcribe-md/scripts/transfer-certification-to-active.ts --commit
//
// DRY RUN IS THE DEFAULT. Without `--commit` it derives the population, runs
// every guard, prints the exact per-field before -> after, and writes nothing.
//
// ── WHY THIS EXISTS ────────────────────────────────────────────────────────
// The owner's Gastroenterology Consultation was certified at 16:06:21 on
// compiled version 87223c49. He re-uploaded the SAME FILE at 16:29:26, which
// minted a new note-template row and a new compiled version 9e758c45, made it
// ACTIVE, and left the certification stranded on a row that is now INACTIVE.
// His next visit bound to the active, UNCERTIFIED copy — so the export could
// not take the twin path at all.
//
//     CERTIFICATION KEYED TO A ROW ID, AND THE ROW ID ROTATES ON UPLOAD.
//
// The product fix — idempotent upload, inheritance by content, auto-certify —
// is the next board item. THIS script is the recovery for the doctor in front
// of us, and it is deliberately narrow.
//
// ── WHY THE DISPOSITIONS ARE TRANSFERRED, NOT RE-DERIVED ───────────────────
// `confirm-live-template-mappings.ts` re-derives each disposition with
// `decide(label, {concept, sourceType})` from the field's CURRENT mapping. On a
// freshly compiled version that input is the fresh PROPOSAL, not the confirmed
// decision, so re-deriving would not reproduce what was certified. Measured
// between the two versions: 31 of 35 concepts and only 27 of 35 sourceTypes
// agree. The 8 that differ are exactly the administrative fields certification
// set to `manual`, and the concept differences are the sub-concept refinements
// (`allergy` -> `allergy.substance`, `medication` -> `medication.name`).
//
// So the certified copy is the SOURCE OF TRUTH and its rows are copied across.
//
// ── WHY THAT IS SOUND, MEASURED ────────────────────────────────────────────
// The two compiled versions are content-identical in every dimension checked:
//   field count            35 / 35
//   match on order+label+kind  35
//   match on fieldId           35   <- the ids themselves are identical
//   structureSha256            identical
//   staticContentSha256        identical
// Only the row id differs. The transfer is therefore not an approximation; it
// is the same field set, addressed by the same ids.
//
// ── WHOSE AUTHORITY, WHOSE HANDS — ruling #158, amended 2026-08-31 ─────────
//   · `approvedById` answers UNDER WHOSE AUTHORITY -> the owning doctor
//   · the audit metadata answers BY WHOSE HANDS    -> the machine
//     (`machineConfirmed`, `onOwnerAuthorization`)
// ============================================================================
import prisma from '@meddoc/db';

import { updateTemplateTwinMappings } from '../src/lib/template-twin/certification-lifecycle';
import { templateTwinMappingsSha256 } from '../src/lib/template-twin/mapping-hash';
import { REGISTRY_SUBCONCEPTS } from '../src/lib/template-twin/concept-registry';
import { logTwinAudit } from '../src/lib/template-twin/twin-audit';
import type { SemanticMapping } from '../src/lib/template-twin/ir';

/** The CERTIFIED copy — the source of truth for the dispositions. */
const SOURCE_VERSION_ID = '87223c49-cf2b-4d7f-a905-3e6e595863ad';
/** The ACTIVE copy — where the doctor's visits actually bind. */
const TARGET_VERSION_ID = '9e758c45-ac65-4996-bea8-6fc1f8b1c96c';
const EXPECT_FIELDS = 35;
const COMMIT = process.argv.includes('--commit');

async function main() {
  const dbHost = new URL(process.env.DATABASE_URL ?? 'postgres://x/x').hostname;
  const dbName = new URL(process.env.DATABASE_URL ?? 'postgres://x/x').pathname.replace('/', '');
  console.log(`db target: ${dbHost}/${dbName}`);
  console.log(`mode     : ${COMMIT ? '⚠️  COMMIT (writes)' : 'DRY RUN'}`);

  const load = (id: string) =>
    prisma.templateTwinCompiledVersion.findUnique({
      where: { id },
      include: {
        noteTemplate: {
          select: { id: true, name: true, status: true, doctorId: true, practiceId: true },
        },
        fields: { include: { mapping: true }, orderBy: { displayOrder: 'asc' } },
      },
    });

  const source = await load(SOURCE_VERSION_ID);
  const target = await load(TARGET_VERSION_ID);
  if (!source) throw new Error(`source version ${SOURCE_VERSION_ID} not found`);
  if (!target) throw new Error(`target version ${TARGET_VERSION_ID} not found`);

  console.log(`\nsource : ${source.noteTemplate.name} [${source.noteTemplate.status}]  ${source.certificationStatus}`);
  console.log(`target : ${target.noteTemplate.name} [${target.noteTemplate.status}]  ${target.certificationStatus}`);

  // ── GUARDS. Every premise this act rests on, asserted before anything runs ──
  const srcCertified = source.fields.filter((f) => f.mapping?.mappingStatus === 'CERTIFIED').length;
  const tgtCertified = target.fields.filter((f) => f.mapping?.mappingStatus === 'CERTIFIED').length;
  const srcIds = source.fields.map((f) => f.fieldId).sort();
  const tgtIds = target.fields.map((f) => f.fieldId).sort();

  const guards: Array<[string, unknown, unknown]> = [
    ['source field count', source.fields.length, EXPECT_FIELDS],
    ['target field count', target.fields.length, EXPECT_FIELDS],
    ['source CERTIFIED mappings', srcCertified, EXPECT_FIELDS],
    ['target CERTIFIED mappings (must be none)', tgtCertified, 0],
    ['fieldId sets identical', JSON.stringify(srcIds) === JSON.stringify(tgtIds), true],
    ['structureSha256 identical', source.structureSha256 === target.structureSha256, true],
    ['staticContentSha256 identical', source.staticContentSha256 === target.staticContentSha256, true],
    ['same owning doctor', source.noteTemplate.doctorId === target.noteTemplate.doctorId, true],
    ['same practice', source.noteTemplate.practiceId === target.noteTemplate.practiceId, true],
    ['target template is ACTIVE', target.noteTemplate.status, 'active'],
  ];
  let bad = 0;
  for (const [name, got, want] of guards) {
    const ok = JSON.stringify(got) === JSON.stringify(want);
    if (!ok) bad += 1;
    console.log(`  guard ${ok ? '✓' : '🔴'} ${name}: ${JSON.stringify(got)} (expect ${JSON.stringify(want)})`);
  }
  if (bad > 0) throw new Error(`${bad} guard(s) failed — refusing. Nothing was written.`);

  // ⚠️ THE SAME RUNTIME CHECK (c) CARRIES. Sub-concept mappings written by a
  // runtime whose registry has never heard of them are off-registry, and the
  // next compile nulls them. This transfer writes `allergy.substance` and
  // `medication.name`, so it refuses on a runtime without the registry.
  const families = REGISTRY_SUBCONCEPTS ? Object.keys(REGISTRY_SUBCONCEPTS) : [];
  console.log(`  registry sub-concept families in THIS runtime: ${families.length} [${families.join(', ')}]`);
  if (families.length === 0) {
    throw new Error(
      'REFUSING — this runtime has no REGISTRY_SUBCONCEPTS, so the sub-concepts ' +
        'this transfer writes would be off-registry and the next compile nulls them.',
    );
  }

  const doctorId = target.noteTemplate.doctorId!;
  const practiceId = target.noteTemplate.practiceId!;
  const doctor = await prisma.user.findUnique({
    where: { id: doctorId },
    select: { id: true, email: true },
  });
  if (!doctor) throw new Error('owning doctor not found');

  // ── THE PAYLOAD: the CERTIFIED copy's rows, addressed by fieldId ───────────
  const byFieldId = new Map(source.fields.map((f) => [f.fieldId, f.mapping!]));
  const before = target.fields.map((f) => f.mapping!);
  const payload: SemanticMapping[] = target.fields.map((f) => {
    const src = byFieldId.get(f.fieldId)!;
    return {
      fieldId: f.fieldId,
      sourceType: src.sourceType,
      clinicalConcept: src.clinicalConcept,
      expectedDataType: src.expectedDataType,
      polarityBehavior: src.polarityBehavior,
      temporality: src.temporality,
      laterality: src.laterality,
      unitPolicy: src.unitPolicy,
      // ⚠️ VERBATIM. `updateTemplateTwinMappings` persists these as given and
      // never re-seeds them from the registry, so they must be carried across
      // explicitly or the certified spellings are silently lost.
      approvedSynonyms: Array.isArray(src.approvedSynonyms) ? src.approvedSynonyms : [],
      required: src.required,
      blankPolicy: src.blankPolicy,
      unknownPolicy: src.unknownPolicy,
      practiceDefault: src.practiceDefault,
      status: 'certified',
    } as unknown as SemanticMapping;
  });

  console.log(`\n── PER-FIELD, target BEFORE -> AFTER ──`);
  let moved = 0;
  target.fields.forEach((f, i) => {
    const b = before[i]!;
    const a = payload[i]! as unknown as {
      clinicalConcept: string | null;
      sourceType: string;
      approvedSynonyms: string[];
    };
    const move = b.clinicalConcept !== a.clinicalConcept || b.sourceType !== a.sourceType;
    if (move) moved += 1;
    console.log(
      `  ${String(f.displayOrder).padStart(2)} ${f.originalLabel.slice(0, 26).padEnd(28)} ` +
        `${String(b.clinicalConcept ?? 'NULL').padEnd(20)}/${b.sourceType.padEnd(10)} -> ` +
        `${String(a.clinicalConcept ?? 'NULL').padEnd(22)}/${a.sourceType.padEnd(10)} ${move ? '★' : ' '} ` +
        `syn=${a.approvedSynonyms.length}`,
    );
  });
  console.log(`  fields whose concept or sourceType MOVES: ${moved}`);

  if (!COMMIT) {
    console.log('\nDRY RUN — nothing written. Re-run with --commit through run-ruled-mutation.sh.');
    await prisma.$disconnect();
    return;
  }

  // ── THE ACT, THROUGH THE APPLICATION PATH (#158(a), amended) ──────────────
  const expectedSha = templateTwinMappingsSha256(
    before.map((m) => ({
      fieldId: target.fields.find((f) => f.mapping?.id === m.id)!.fieldId,
      sourceType: m.sourceType,
      clinicalConcept: m.clinicalConcept,
      expectedDataType: m.expectedDataType,
      polarityBehavior: m.polarityBehavior,
      temporality: m.temporality,
      laterality: m.laterality,
      unitPolicy: m.unitPolicy,
      approvedSynonyms: Array.isArray(m.approvedSynonyms) ? m.approvedSynonyms : [],
      required: m.required,
      blankPolicy: m.blankPolicy,
      unknownPolicy: m.unknownPolicy,
      practiceDefault: m.practiceDefault,
      status:
        m.mappingStatus === 'CERTIFIED'
          ? 'certified'
          : m.mappingStatus === 'RECOGNIZED'
            ? 'recognized'
            : 'needs_confirmation',
    })) as unknown as SemanticMapping[],
  );

  const actor = { userId: doctor.id, userEmail: doctor.email, practiceId };
  await updateTemplateTwinMappings({
    noteTemplateId: target.noteTemplate.id,
    actor,
    expectedMappingsSha256: expectedSha,
    mappings: payload,
  });

  // ── BY WHOSE HANDS. One append-only audit row per transferred mapping. ────
  for (const f of target.fields) {
    await logTwinAudit({
      action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
      targetType: 'TemplateTwinSemanticMapping',
      targetId: f.mapping!.id,
      userId: doctor.id,
      userEmail: doctor.email,
      practiceId,
      metadata: {
        machineConfirmed: true,
        onOwnerAuthorization:
          'ruling #158, amended 2026-08-31 — actor is the owning doctor identity',
        transferredFromCompiledVersionId: SOURCE_VERSION_ID,
        reason:
          'certification stranded by re-upload: identical source bytes minted a new ' +
          'row and the certified copy went inactive',
        compiledVersionId: TARGET_VERSION_ID,
        fieldId: f.fieldId,
        displayOrder: f.displayOrder,
      },
    });
  }

  // ── END-STATE ASSERTIONS ─────────────────────────────────────────────────
  const after = await prisma.templateTwinFieldDefinition.findMany({
    where: { compiledVersionId: TARGET_VERSION_ID },
    include: { mapping: true },
  });
  const approved = after.filter((f) => f.mapping?.approvedById === doctor.id).length;
  const certified = after.filter((f) => f.mapping?.mappingStatus === 'CERTIFIED').length;
  const withTs = after.filter((f) => f.mapping?.approvedAt).length;
  console.log(`\n── END STATE (target ${TARGET_VERSION_ID}) ──`);
  console.log(`  CERTIFIED mappings          : ${certified} (expect ${EXPECT_FIELDS})`);
  console.log(`  approvedById = owning doctor: ${approved} (expect ${EXPECT_FIELDS})`);
  console.log(`  approvedAt set              : ${withTs} (expect ${EXPECT_FIELDS})`);
  if (certified !== EXPECT_FIELDS || approved !== EXPECT_FIELDS || withTs !== EXPECT_FIELDS) {
    throw new Error('END-STATE ASSERTION FAILED — see the numbers above.');
  }
  console.log('🟢 transfer complete. The synthetic chain and certification run separately.');
  await prisma.$disconnect();
}

main()
  .catch(async (e) => {
    console.error('🔴', e instanceof Error ? e.message : e);
    await prisma.$disconnect();
    process.exitCode = 1;
  });
