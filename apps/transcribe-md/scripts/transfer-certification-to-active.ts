// ============================================================================
// TRANSFER THE CERTIFIED DISPOSITIONS ONTO THE ACTIVE COMPILED VERSION.
// ----------------------------------------------------------------------------
// A RULED MUTATION. The only door is:
//
//   bash scripts/run-ruled-mutation.sh --declaration <path> \
//     --in transcribe-md-worker -- \
//     npx tsx scripts/transfer-certification-to-active.ts \
//       --source <compiledVersionId> --target <compiledVersionId> \
//       --expect-fields <n> --target-status <draft|active> \
//       --transfer-source-types <all|type[,type...]> --expect-transfer <n> --commit
//
// ⚠️ THE PATH IS RELATIVE TO `apps/transcribe-md`, AND THAT IS NOT COSMETIC.
// THE INVOCATION DOCUMENTED HERE BEFORE DID NOT WORK — MEASURED, NOT SUSPECTED.
// It read `npx tsx apps/transcribe-md/scripts/…` and `run-ruled-mutation.sh:48`
// does `cd "$(git rev-parse --show-toplevel)"` unconditionally, so the child ran
// from the REPO ROOT. From there tsx picks up the root tsconfig, the `@/*` alias
// is undefined, and this script dies before its first line:
//
//     Error: Cannot find module '@/lib/audit'
//     Require stack: …/template-twin/twin-audit.ts
//
// Reproduced both ways: from `/app` inside the container it FAILS; from
// `/app/apps/transcribe-md` it resolves. `--in transcribe-md-worker` gets this
// right for free, because the worker image's WORKDIR already IS
// `/app/apps/transcribe-md` — so the ruled door (#262) happens to be the only
// one that works, and the relative path is what makes it work.
//
// ⚠️ ON THE HOST the same constraint applies and nothing corrects it for you:
//
//     bash scripts/run-ruled-mutation.sh --declaration <path> -- \
//       sh -c 'cd apps/transcribe-md && npx tsx scripts/transfer-… --commit'
//
// but the host route also needs DATABASE_URL from `.env`, which is denied — the
// whole reason #262 exists. Use `--in`.
//
// ── PARAMETERISED, RULING #263 ─────────────────────────────────────────────
// Source, target and expected count were FILE CONSTANTS naming one doctor's
// stranded Gastroenterology Consultation. The 53-control consult form re-issue
// is a second act of the same shape, so they are REQUIRED arguments — required
// rather than defaulted, so this tool can never act on a target nobody named.
// Parsing and the guard set live in `../src/lib/template-twin/transfer-args.ts`,
// pure, proved by `gate-transfer-args.test.ts` without a database.
//
// ⚠️ EVERY ORIGINAL GUARD IS KEPT AND FOUR ARE ADDED. Four of the ten compare
// NULLABLE columns for equality, so two rows recording nothing about their
// structure agreed perfectly about it. Two hardcoded ids made that unreachable;
// a caller-supplied pair does not.
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

import {
  updateTemplateTwinMappings,
  fromPersistedMapping,
} from '../src/lib/template-twin/certification-lifecycle';
import { templateTwinMappingsSha256 } from '../src/lib/template-twin/mapping-hash';
import { REGISTRY_SUBCONCEPTS } from '../src/lib/template-twin/concept-registry';
import { logTwinAudit } from '../src/lib/template-twin/twin-audit';
import type { SemanticMapping } from '../src/lib/template-twin/ir';
import {
  parseTransferArgs,
  buildTransferGuards,
  countFailedGuards,
  selectTransferFieldIds,
} from '../src/lib/template-twin/transfer-args';

// ⚠️ PARSED BEFORE ANYTHING IS OPENED. A refusal must not be reachable only
// after a database connection, or a bad argument and an unreachable database
// produce the same failure and the operator debugs the wrong one.
const PARSED = parseTransferArgs(process.argv.slice(2));
if (!PARSED.ok) {
  console.error(`🔴 ${PARSED.reason}`);
  process.exit(2);
}
const {
  source: SOURCE_VERSION_ID,
  target: TARGET_VERSION_ID,
  expectFields: EXPECT_FIELDS,
  targetStatus: TARGET_STATUS,
  transferSourceTypes: TRANSFER_SOURCE_TYPES,
  expectTransfer: EXPECT_TRANSFER,
  commit: COMMIT,
} = PARSED.args;

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
  // ⚠️ BUILT BY THE SHARED, PURE BUILDER — not re-implemented here. A second
  // copy drifts from the arm that proves it the day either is fixed, the same
  // reason `declaration.sh` and `inflight.sh` are shared files.
  const asSide = (v: typeof source) => ({
    fields: v!.fields.map((f) => ({
      fieldId: f.fieldId,
      mappingStatus: f.mapping?.mappingStatus ?? null,
      sourceType: f.mapping?.sourceType ?? null,
    })),
    structureSha256: v!.structureSha256,
    staticContentSha256: v!.staticContentSha256,
    templateStatus: v!.noteTemplate.status,
    doctorId: v!.noteTemplate.doctorId,
    practiceId: v!.noteTemplate.practiceId,
  });

  const guards = buildTransferGuards(asSide(source), asSide(target), EXPECT_FIELDS, {
    targetStatus: TARGET_STATUS,
    transferSourceTypes: TRANSFER_SOURCE_TYPES,
    expectTransfer: EXPECT_TRANSFER,
  });
  for (const [name, got, want] of guards) {
    const ok = JSON.stringify(got) === JSON.stringify(want);
    console.log(`  guard ${ok ? '✓' : '🔴'} ${name}: ${JSON.stringify(got)} (expect ${JSON.stringify(want)})`);
  }
  const bad = countFailedGuards(guards);
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

  // ⚠️ THE PAYLOAD IS ALWAYS THE FULL FIELD SET, AND THAT IS NOT A CHOICE.
  // `updateTemplateTwinMappings` throws `FIELD_SET_MISMATCH` unless the mappings
  // it receives are EXACTLY the compiler's field set (certification-lifecycle.ts:445,
  // `byId.size !== fieldById.size`). So "transfer the 43" can never mean "send
  // 43"; it means all 53 go — 43 carrying the SOURCE's certified row, the rest
  // carrying the TARGET's own untouched proposal.
  const TRANSFER_IDS = new Set(selectTransferFieldIds(asSide(source), TRANSFER_SOURCE_TYPES));

  // ══ EVERY ROW IS PROJECTED BY `fromPersistedMapping`, NEVER BY HAND ═══════
  //
  // ⚠️ THIS FILE HAND-ROLLED THE PROJECTION AND IT DROPPED TWO COLUMNS. The
  // literal listed 14 of the 16; the two missing were `unmentionedPolicy` and
  // `conceptScope`, and the writer NULLS both when the payload omits them:
  //
  //     unmentionedPolicy: mapping.unmentionedPolicy ?? null     (:540)
  //     conceptScope:      … : Prisma.DbNull                     (:547)
  //
  // A transfer would therefore have ERASED every ruled `omit` (#192/#194) and
  // every scaffolded `conceptScope` (#217) on the target — silently, while
  // printing a full set of green guards. `conceptScope`'s own comment records
  // that the ABSENCE of its writer left four readers dead in production; this
  // would have been the same loss arriving through a tool built to preserve.
  //
  // ⚠️ AND THE LIST WAS NOT THE DEFECT — HAVING ONE WAS. A 16th column added
  // tomorrow is dropped by the identical mechanism and nothing says so.
  // `fromPersistedMapping` is EXPORTED for exactly this reason: its docstring
  // records that gate-217's first form re-implemented its omit-when-absent rule
  // inside the test file, "so the two moved together and the arm could never
  // fail". A rule with two readers drifts. This file is now the same reader as
  // the writer, and `status` comes back through it too — so `UNSUPPORTED`
  // survives instead of being flattened to `needs_confirmation`.
  const project = (fieldId: string, row: (typeof before)[number]) =>
    fromPersistedMapping(fieldId, row as unknown as Parameters<typeof fromPersistedMapping>[1]);

  const payload: SemanticMapping[] = target.fields.map((f) => {
    // ── NOT SELECTED: the field keeps its OWN row, and now actually verbatim ──
    // The ten re-proposed under the new registry are the POINT of the act
    // (#246/#263). Stamping them `certified` from the source would overwrite the
    // fresh proposals with the very `manual` placeholders REGISTRY-1 exists to
    // replace — and #261 forbids certifying a patient-name row below the fold.
    if (!TRANSFER_IDS.has(f.fieldId)) return project(f.fieldId, f.mapping!);

    // ── SELECTED: the SOURCE's certified row, stamped `certified` — the one
    // thing this act is entitled to change about it.
    return {
      ...project(f.fieldId, byFieldId.get(f.fieldId)!),
      status: 'certified',
    } as SemanticMapping;
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
    const kind = TRANSFER_IDS.has(f.fieldId) ? 'xfer' : 'KEEP';
    console.log(
      `  ${String(f.displayOrder).padStart(2)} ${f.originalLabel.slice(0, 26).padEnd(28)} ` +
        `${kind} ${String(b.clinicalConcept ?? 'NULL').padEnd(20)}/${b.sourceType.padEnd(10)} -> ` +
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
  // ⚠️ THE OPTIMISTIC LOCK IS FED BY THE SAME PROJECTION THE WRITER READS WITH.
  // It hashes the BEFORE state, and `updateTemplateTwinMappings` computes its
  // own `beforeHash` from `currentMappings(compiled)` — which is
  // `fromPersistedMapping`. A second, hand-rolled projection here produced a
  // DIFFERENT hash for the same rows, so the lock rejected correct payloads and
  // blamed a concurrent edit that had not happened. One reader, one hash.
  const expectedSha = templateTwinMappingsSha256(
    target.fields.map((f) => project(f.fieldId, f.mapping!)),
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
        // ⚠️ AN AUDIT ROW THAT CLAIMS A TRANSFER FOR A FIELD THAT KEPT ITS OWN
        // DISPOSITION IS A FALSE RECORD. The writer rewrites every field, so
        // every field gets a row; only the selected ones came from the source.
        transferred: TRANSFER_IDS.has(f.fieldId),
        transferredFromCompiledVersionId: TRANSFER_IDS.has(f.fieldId)
          ? SOURCE_VERSION_ID
          : null,
        // ⚠️ THE REASON NAMES THE DECLARATION, NOT A REMEMBERED STORY. This tool
        // now serves more than one act, and a hardcoded narrative would attach
        // the FIRST act's explanation to every later one — an audit row that
        // reads as evidence and is simply wrong about why it exists.
        reason:
          'ruled mutation: certified dispositions transferred between compiled ' +
          'versions. The declaration is the account of why: ' +
          (process.env.RULED_MUTATION_DECLARATION ??
            '<not run through run-ruled-mutation.sh>'),
        declarationCommit: process.env.RULED_MUTATION_DECL_COMMIT ?? null,
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
  // ⚠️ ASSERTED AGAINST THE **TRANSFERRED** COUNT, NOT THE FIELD COUNT. When a
  // selection is in play the two differ BY DESIGN — the ten re-proposed rows are
  // meant to come out UNCERTIFIED, waiting for the doctor (#261, #263).
  // `certified === EXPECT_FIELDS` demanded exactly the outcome the act exists to
  // avoid, and would have failed the run AFTER the writes had landed.
  const transferredAfter = after.filter((f) => TRANSFER_IDS.has(f.fieldId));
  const keptAfter = after.filter((f) => !TRANSFER_IDS.has(f.fieldId));

  const certified = transferredAfter.filter((f) => f.mapping?.mappingStatus === 'CERTIFIED').length;
  const approved = transferredAfter.filter((f) => f.mapping?.approvedById === doctor.id).length;
  const withTs = transferredAfter.filter((f) => f.mapping?.approvedAt).length;
  const keptCertified = keptAfter.filter((f) => f.mapping?.mappingStatus === 'CERTIFIED').length;

  console.log(`\n── END STATE (target ${TARGET_VERSION_ID}) ──`);
  console.log(`  fields present              : ${after.length} (expect ${EXPECT_FIELDS})`);
  console.log(`  TRANSFERRED, CERTIFIED      : ${certified} (expect ${EXPECT_TRANSFER})`);
  console.log(`  TRANSFERRED, approvedById   : ${approved} (expect ${EXPECT_TRANSFER})`);
  console.log(`  TRANSFERRED, approvedAt set : ${withTs} (expect ${EXPECT_TRANSFER})`);
  console.log(
    `  KEPT, still NOT certified   : ${keptAfter.length - keptCertified} ` +
      `(expect ${EXPECT_FIELDS - EXPECT_TRANSFER})`,
  );

  if (
    after.length !== EXPECT_FIELDS ||
    certified !== EXPECT_TRANSFER ||
    approved !== EXPECT_TRANSFER ||
    withTs !== EXPECT_TRANSFER ||
    keptCertified !== 0
  ) {
    throw new Error('END-STATE ASSERTION FAILED — see the numbers above.');
  }
  console.log(
    `🟢 transfer complete: ${certified} disposition(s) carried across, ` +
      `${keptAfter.length} left for re-proposal. Certification runs separately.`,
  );
  await prisma.$disconnect();
}

main()
  .catch(async (e) => {
    console.error('🔴', e instanceof Error ? e.message : e);
    await prisma.$disconnect();
    process.exitCode = 1;
  });
