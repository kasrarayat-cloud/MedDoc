// ============================================================================
// TRANSFER THE CERTIFIED DISPOSITIONS ONTO THE ACTIVE COMPILED VERSION.
// ----------------------------------------------------------------------------
// A RULED MUTATION. The only door is:
//
//   bash scripts/run-ruled-mutation.sh --declaration <path> -- \
//     npx tsx apps/transcribe-md/scripts/transfer-certification-to-active.ts \
//       --source <compiledVersionId> --target <compiledVersionId> \
//       --expect-fields <n> --commit
//
// DRY RUN IS THE DEFAULT. Without `--commit` it derives the population, runs
// every guard, prints the exact per-field before -> after, and writes nothing.
//
// ── PARAMETERISED, RULING 2 (2026-09-07) ───────────────────────────────────
// Source, target and expected count were FILE CONSTANTS naming one doctor's
// stranded Gastroenterology Consultation. The 53-control consult form re-issue
// is a second, different act of the same shape, so they are now REQUIRED
// arguments — required rather than defaulted, so this tool can never act on a
// target nobody named. Argument parsing and the guard set live in
// `../src/lib/template-twin/transfer-args.ts`, pure, and are proved by
// `gate-transfer-args.test.ts` without a database.
//
// ⚠️ EVERY ORIGINAL GUARD IS KEPT, AND FOUR ARE ADDED. Four of the ten compare
// NULLABLE columns for equality, so two rows recording nothing about their
// structure agreed perfectly about it. Two hardcoded ids made that unreachable;
// a caller-supplied pair does not. See the module header.
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
import prisma from "@meddoc/db";

import { updateTemplateTwinMappings } from "../src/lib/template-twin/certification-lifecycle";
import { templateTwinMappingsSha256 } from "../src/lib/template-twin/mapping-hash";
import { REGISTRY_SUBCONCEPTS } from "../src/lib/template-twin/concept-registry";
import { logTwinAudit } from "../src/lib/template-twin/twin-audit";
import type { SemanticMapping } from "../src/lib/template-twin/ir";
import {
  parseTransferArgs,
  buildTransferGuards,
  countFailedGuards,
  selectTransferFieldIds,
} from "../src/lib/template-twin/transfer-args";

// ⚠️ PARSED BEFORE ANYTHING IS OPENED. A refusal here must not be reachable
// only after a database connection, or a bad argument and an unreachable
// database produce the same failure and the operator debugs the wrong one.
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
  const dbHost = new URL(process.env.DATABASE_URL ?? "postgres://x/x").hostname;
  const dbName = new URL(
    process.env.DATABASE_URL ?? "postgres://x/x",
  ).pathname.replace("/", "");
  console.log(`db target: ${dbHost}/${dbName}`);
  console.log(`mode     : ${COMMIT ? "⚠️  COMMIT (writes)" : "DRY RUN"}`);

  const load = (id: string) =>
    prisma.templateTwinCompiledVersion.findUnique({
      where: { id },
      include: {
        noteTemplate: {
          select: {
            id: true,
            name: true,
            status: true,
            doctorId: true,
            practiceId: true,
          },
        },
        fields: {
          include: { mapping: true },
          orderBy: { displayOrder: "asc" },
        },
      },
    });

  const source = await load(SOURCE_VERSION_ID);
  const target = await load(TARGET_VERSION_ID);
  if (!source) throw new Error(`source version ${SOURCE_VERSION_ID} not found`);
  if (!target) throw new Error(`target version ${TARGET_VERSION_ID} not found`);

  console.log(
    `\nsource : ${source.noteTemplate.name} [${source.noteTemplate.status}]  ${source.certificationStatus}`,
  );
  console.log(
    `target : ${target.noteTemplate.name} [${target.noteTemplate.status}]  ${target.certificationStatus}`,
  );

  // ── GUARDS. Every premise this act rests on, asserted before anything runs ──
  // ⚠️ BUILT BY THE SHARED, PURE BUILDER — not re-implemented here. A second
  // copy would drift from the arm that proves it the day either is fixed, which
  // is the same reason `declaration.sh` and `inflight.sh` are shared files.
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

  const guards = buildTransferGuards(
    asSide(source),
    asSide(target),
    EXPECT_FIELDS,
    {
      targetStatus: TARGET_STATUS,
      transferSourceTypes: TRANSFER_SOURCE_TYPES,
      expectTransfer: EXPECT_TRANSFER,
    },
  );
  for (const [name, got, want] of guards) {
    const ok = JSON.stringify(got) === JSON.stringify(want);
    console.log(
      `  guard ${ok ? "✓" : "🔴"} ${name}: ${JSON.stringify(got)} (expect ${JSON.stringify(want)})`,
    );
  }
  const bad = countFailedGuards(guards);
  if (bad > 0)
    throw new Error(`${bad} guard(s) failed — refusing. Nothing was written.`);

  // ⚠️ THE SAME RUNTIME CHECK (c) CARRIES. Sub-concept mappings written by a
  // runtime whose registry has never heard of them are off-registry, and the
  // next compile nulls them. This transfer writes `allergy.substance` and
  // `medication.name`, so it refuses on a runtime without the registry.
  const families = REGISTRY_SUBCONCEPTS
    ? Object.keys(REGISTRY_SUBCONCEPTS)
    : [];
  console.log(
    `  registry sub-concept families in THIS runtime: ${families.length} [${families.join(", ")}]`,
  );
  if (families.length === 0) {
    throw new Error(
      "REFUSING — this runtime has no REGISTRY_SUBCONCEPTS, so the sub-concepts " +
        "this transfer writes would be off-registry and the next compile nulls them.",
    );
  }

  const doctorId = target.noteTemplate.doctorId!;
  const practiceId = target.noteTemplate.practiceId!;
  const doctor = await prisma.user.findUnique({
    where: { id: doctorId },
    select: { id: true, email: true },
  });
  if (!doctor) throw new Error("owning doctor not found");

  // ── THE PAYLOAD: the CERTIFIED copy's rows, addressed by fieldId ───────────
  const byFieldId = new Map(source.fields.map((f) => [f.fieldId, f.mapping!]));
  const before = target.fields.map((f) => f.mapping!);

  // ⚠️ THE PAYLOAD IS ALWAYS THE FULL FIELD SET, AND THAT IS NOT A CHOICE.
  // `updateTemplateTwinMappings` throws `FIELD_SET_MISMATCH` unless the mappings
  // it receives are exactly the compiler's field set — `certification-lifecycle.ts:445`,
  // `byId.size !== fieldById.size`. So "transfer the 43" can never mean "send 43";
  // it means all 53 go, 43 of them carrying the SOURCE's certified row and the rest
  // carrying the TARGET's own untouched proposal.
  const TRANSFER_IDS = new Set(
    selectTransferFieldIds(asSide(source), TRANSFER_SOURCE_TYPES),
  );

  // The DB enum -> the SemanticMapping vocabulary, for the rows that stay put.
  // ⚠️ Shared with the expected-sha computation below rather than written twice:
  // the two must agree or the optimistic lock rejects a payload that is correct.
  const statusOf = (ms: string | null | undefined) =>
    ms === "CERTIFIED"
      ? "certified"
      : ms === "RECOGNIZED"
        ? "recognized"
        : "needs_confirmation";

  const payload: SemanticMapping[] = target.fields.map((f) => {
    // ── A FIELD NOT SELECTED KEEPS ITS OWN ROW, VERBATIM ──
    // ⚠️ The ten re-proposed under the new registry are the POINT of the act
    // (#246/#263). Stamping them `certified` from the source would overwrite the
    // fresh proposals with the very `manual` placeholders REGISTRY-1 exists to
    // replace — and #261 forbids certifying a patient-name row below the fold
    // regardless.
    if (!TRANSFER_IDS.has(f.fieldId)) {
      const own = f.mapping!;
      return {
        fieldId: f.fieldId,
        sourceType: own.sourceType,
        clinicalConcept: own.clinicalConcept,
        expectedDataType: own.expectedDataType,
        polarityBehavior: own.polarityBehavior,
        temporality: own.temporality,
        laterality: own.laterality,
        unitPolicy: own.unitPolicy,
        approvedSynonyms: Array.isArray(own.approvedSynonyms)
          ? own.approvedSynonyms
          : [],
        required: own.required,
        blankPolicy: own.blankPolicy,
        unknownPolicy: own.unknownPolicy,
        practiceDefault: own.practiceDefault,
        status: statusOf(own.mappingStatus),
      } as unknown as SemanticMapping;
    }
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
      approvedSynonyms: Array.isArray(src.approvedSynonyms)
        ? src.approvedSynonyms
        : [],
      required: src.required,
      blankPolicy: src.blankPolicy,
      unknownPolicy: src.unknownPolicy,
      practiceDefault: src.practiceDefault,
      status: "certified",
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
    const move =
      b.clinicalConcept !== a.clinicalConcept || b.sourceType !== a.sourceType;
    if (move) moved += 1;
    const kind = TRANSFER_IDS.has(f.fieldId) ? "xfer" : "KEEP";
    console.log(
      `  ${String(f.displayOrder).padStart(2)} ${f.originalLabel.slice(0, 26).padEnd(28)} ` +
        `${kind} ${String(b.clinicalConcept ?? "NULL").padEnd(20)}/${b.sourceType.padEnd(10)} -> ` +
        `${String(a.clinicalConcept ?? "NULL").padEnd(22)}/${a.sourceType.padEnd(10)} ${move ? "★" : " "} ` +
        `syn=${a.approvedSynonyms.length}`,
    );
  });
  console.log(`  fields whose concept or sourceType MOVES: ${moved}`);

  if (!COMMIT) {
    console.log(
      "\nDRY RUN — nothing written. Re-run with --commit through run-ruled-mutation.sh.",
    );
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
      approvedSynonyms: Array.isArray(m.approvedSynonyms)
        ? m.approvedSynonyms
        : [],
      required: m.required,
      blankPolicy: m.blankPolicy,
      unknownPolicy: m.unknownPolicy,
      practiceDefault: m.practiceDefault,
      status: statusOf(m.mappingStatus),
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
      action: "TEMPLATE_TWIN_MAPPING_UPDATED",
      targetType: "TemplateTwinSemanticMapping",
      targetId: f.mapping!.id,
      userId: doctor.id,
      userEmail: doctor.email,
      practiceId,
      metadata: {
        machineConfirmed: true,
        onOwnerAuthorization:
          "ruling #158, amended 2026-08-31 — actor is the owning doctor identity",
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
          "ruled mutation: certified dispositions transferred between compiled " +
          "versions. The declaration is the account of why: " +
          (process.env.RULED_MUTATION_DECLARATION ??
            "<not run through run-ruled-mutation.sh>"),
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
  // ⚠️ THE END STATE IS ASSERTED AGAINST THE **TRANSFERRED** COUNT, NOT THE FIELD
  // COUNT. When a selection is in play the two differ by design — the ten
  // re-proposed rows are meant to come out of this UNCERTIFIED, waiting for the
  // doctor (#261, #263). Asserting `certified === EXPECT_FIELDS` here would have
  // demanded exactly the outcome the act exists to avoid, and would have failed
  // the run AFTER the writes had already landed.
  const transferredAfter = after.filter((f) => TRANSFER_IDS.has(f.fieldId));
  const keptAfter = after.filter((f) => !TRANSFER_IDS.has(f.fieldId));

  const certified = transferredAfter.filter(
    (f) => f.mapping?.mappingStatus === "CERTIFIED",
  ).length;
  const approved = transferredAfter.filter(
    (f) => f.mapping?.approvedById === doctor.id,
  ).length;
  const withTs = transferredAfter.filter((f) => f.mapping?.approvedAt).length;
  const keptCertified = keptAfter.filter(
    (f) => f.mapping?.mappingStatus === "CERTIFIED",
  ).length;

  console.log(`\n── END STATE (target ${TARGET_VERSION_ID}) ──`);
  console.log(
    `  fields present              : ${after.length} (expect ${EXPECT_FIELDS})`,
  );
  console.log(
    `  TRANSFERRED, CERTIFIED      : ${certified} (expect ${EXPECT_TRANSFER})`,
  );
  console.log(
    `  TRANSFERRED, approvedById   : ${approved} (expect ${EXPECT_TRANSFER})`,
  );
  console.log(
    `  TRANSFERRED, approvedAt set : ${withTs} (expect ${EXPECT_TRANSFER})`,
  );
  console.log(
    `  KEPT, still NOT certified   : ${keptAfter.length - keptCertified} ` +
      `(expect ${EXPECT_FIELDS - EXPECT_TRANSFER})`,
  );

  const endStateBad =
    after.length !== EXPECT_FIELDS ||
    certified !== EXPECT_TRANSFER ||
    approved !== EXPECT_TRANSFER ||
    withTs !== EXPECT_TRANSFER ||
    keptCertified !== 0;
  if (endStateBad) {
    throw new Error("END-STATE ASSERTION FAILED — see the numbers above.");
  }
  console.log(
    `🟢 transfer complete: ${certified} disposition(s) carried across, ` +
      `${keptAfter.length} left for re-proposal. Certification runs separately.`,
  );
  await prisma.$disconnect();
}

main().catch(async (e) => {
  console.error("🔴", e instanceof Error ? e.message : e);
  await prisma.$disconnect();
  process.exitCode = 1;
});
