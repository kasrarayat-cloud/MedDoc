// ============================================================================
// (c) — THE LIVE-TEMPLATE CONFIRMATIONS. Ruling #158, as amended 2026-08-31.
// ----------------------------------------------------------------------------
// A RULED MUTATION. The only door is:
//
//   bash scripts/run-ruled-mutation.sh --declaration <path> -- \
//     npx tsx apps/transcribe-md/scripts/confirm-live-template-mappings.ts --commit
//
// DRY RUN IS THE DEFAULT. Without `--commit` it derives the population, runs
// every guard, prints the exact per-field before -> after, and writes nothing.
//
// ── WHOSE AUTHORITY, AND WHOSE HANDS — the amendment's whole point ──────────
// #158(a) originally said "the actor is the MACHINE, carrying the owner-
// authorization flags". The schema cannot express that: `loadOwnedCompilation`
// filters `doctorId: actor.userId`, `approvedById` is a FK to users, and there
// is no machine identity among the 198 rows. Minting one would weaken an
// ownership check on a clinical write path to satisfy a phrasing.
//
// AMENDED AND RATIFIED 2026-08-31 — the two questions get two honest answers:
//   · `approvedById` answers UNDER WHOSE AUTHORITY  -> the owning doctor
//   · the audit metadata + the committed declaration answer BY WHOSE HANDS
//     -> the machine (`machineConfirmed`, `onOwnerAuthorization`)
//
// ── WHY (b) IS A HARD DEPENDENCY, MEASURED NOT ASSUMED ─────────────────────
// `updateTemplateTwinMappings` persists `approvedSynonyms` VERBATIM from its
// input and never calls `synonymsFor` — so this payload carries them
// EXPLICITLY. And the three entity-naming sub-concepts must already be on
// `ACCUMULATING_NARRATIVE_CONCEPTS` (that is (b)) or a second allergy becomes
// `multiple_distinct_supported_values` instead of listing.
// ============================================================================
import prisma from '@meddoc/db';

import {
  updateTemplateTwinMappings,
} from '../src/lib/template-twin/certification-lifecycle';
import { templateTwinMappingsSha256 } from '../src/lib/template-twin/mapping-hash';
import { synonymsFor, REGISTRY_SUBCONCEPTS } from '../src/lib/template-twin/concept-registry';
import { logTwinAudit } from '../src/lib/template-twin/twin-audit';
import type { SemanticMapping } from '../src/lib/template-twin/ir';

const COMPILED_VERSION_ID = '87223c49-cf2b-4d7f-a905-3e6e595863ad';
const EXPECT_FIELDS = 35;
const COMMIT = process.argv.includes('--commit');

/**
 * THE PER-FIELD DECISION, BY LABEL — #158(b)'s "realistic mappings, never a
 * blanket substitution", and canon 71's lesson stated as code.
 *
 * `concept: null` + `manual` is the CERTIFICATION GATE'S OWN documented class
 * (`certification-lifecycle.ts` — "A MANUAL field ... carries no clinical
 * concept because there is no evidence to cite, and it renders BLANK.
 * Requiring a concept there would block certification on a field that is
 * behaving correctly"). It is an ATTESTATION that the field is blank on
 * purpose, not a way to dodge a concept.
 */
const PLAN: ReadonlyArray<{
  match: (label: string) => boolean;
  concept: string | null;
  sourceType: 'extraction' | 'manual';
  why: string;
}> = [
  // ── (b)'s payoff: four fields the proposer SILENTLY NULLED because the
  //    registry did not carry the sub-concept the model correctly proposed.
  { match: (l) => /^tobacco/i.test(l), concept: 'social_history.smoking', sourceType: 'extraction',
    why: '(b): the model proposed social_history.smoking and the proposer nulled it off-registry' },
  { match: (l) => /^alcohol/i.test(l), concept: 'social_history.alcohol', sourceType: 'extraction',
    why: '(b): same shape' },
  { match: (l) => /recreational drugs/i.test(l), concept: 'social_history.drugs', sourceType: 'extraction',
    why: '(b): same shape' },
  { match: (l) => /^occupation/i.test(l), concept: 'social_history.occupation', sourceType: 'extraction',
    why: '(b): same shape' },

  // ── the BARE FAMILY matches NO fact. The extractor emits `allergy.substance`,
  //    `medication.name`, `family_history.condition`; nothing emits the bare
  //    family. These three sub-concepts accumulate (that is (b)'s allowlist),
  //    so a second allergy LISTS instead of conflicting.
  { match: (l) => /^allerg/i.test(l), concept: 'allergy.substance', sourceType: 'extraction',
    why: 'bare `allergy` matches no fact; `allergy.substance` matches and accumulates' },
  { match: (l) => /medications were/i.test(l), concept: 'medication.name', sourceType: 'extraction',
    why: 'bare `medication` matches no fact; `medication.name` matches and accumulates' },
  // ⚠️ FAMILY HISTORY IS DELIBERATELY *NOT* REMAPPED, AND THE ADVERSARIAL PASS
  // ON (b) IS WHY. `family_history.condition` matches facts, but it does NOT
  // accumulate: joining conditions destroys the RELATION — "Diabetes;
  // Hypertension" with no indication of whose — so (b) removed it from the
  // accumulating set. Mapping these three fields to it would therefore turn a
  // patient with two family conditions into `multiple_distinct_supported_values`
  // -> FIELD_CONFLICT -> BLOCKING, where `main` leaves an honest blank.
  //
  // So they keep the bare `family_history` they have: it matches no fact, the
  // field renders blank, and nothing blocks — byte-identical to today. It moves
  // when relation-binding lands as a DECLARED COMPOSITION, not before.
  // A field this plan does not name keeps exactly what it has, and this one is
  // named precisely to record that the omission is a DECISION.

  // ── ATTESTED BLANK. No dictated source exists for any of these, so under
  //    `extraction` they resolve `clinical_concept_unmapped` -> BLOCKING, and
  //    certification is impossible. They are per-visit metadata or template
  //    scaffold, which is exactly the class the gate's `manual` arm names.
  { match: (l) => /^referring md/i.test(l), concept: null, sourceType: 'manual',
    why: 'practice context, never dictated — the concept-registry docstring names this class' },
  { match: (l) => /^patient$/i.test(l), concept: null, sourceType: 'manual',
    why: 'visit metadata, not evidence' },
  { match: (l) => /^age$/i.test(l), concept: null, sourceType: 'manual',
    why: 'visit metadata, not evidence' },
  { match: (l) => /is a pleasant/i.test(l), concept: null, sourceType: 'manual',
    why: 'sentence scaffold inside the letter, not a dictated value' },
  { match: (l) => /total minutes/i.test(l), concept: null, sourceType: 'manual',
    why: 'L3 emits no time concept; attested blank until one exists' },
];

function decide(label: string, current: { concept: string | null; sourceType: string }) {
  const hit = PLAN.find((p) => p.match(label));
  if (hit) return { concept: hit.concept, sourceType: hit.sourceType, why: hit.why };
  // UNCHANGED by default. A field this plan does not name keeps exactly what it
  // has — the opposite of a blanket substitution.
  return {
    concept: current.concept,
    sourceType: current.sourceType as 'extraction' | 'manual',
    why: 'unchanged — already correct, or outside this ruling',
  };
}

async function main() {
  // ⚠️ NAME THE TARGET OUT LOUD. A ruled mutation that cannot say which
  // database it is about is not auditable.
  const dbHost = new URL(process.env.DATABASE_URL ?? 'postgres://unknown/unknown').hostname;
  const dbName = new URL(process.env.DATABASE_URL ?? 'postgres://unknown/unknown').pathname.replace('/', '');
  console.log(`db target: ${dbHost}/${dbName}`);
  console.log(`mode     : ${COMMIT ? '⚠️  COMMIT (writes)' : 'DRY RUN (writes nothing)'}`);

  const compiled = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: COMPILED_VERSION_ID },
    include: {
      noteTemplate: { select: { id: true, name: true, status: true, doctorId: true, practiceId: true } },
      fields: { include: { mapping: true }, orderBy: { displayOrder: 'asc' } },
    },
  });
  if (!compiled) throw new Error(`compiled version ${COMPILED_VERSION_ID} not found`);

  // ── GUARDS. Every one fires BEFORE any write, and a population that has
  //    moved since the declaration means the declaration describes another world.
  type Row = (typeof compiled.fields)[number];
  const fields: Row[] = compiled.fields;
  const g: Array<[string, unknown, unknown]> = [
    ['field count', fields.length, EXPECT_FIELDS],
    ['every field has a mapping', fields.every((f) => f.mapping), true],
    ['certificationStatus', compiled.certificationStatus, 'NEEDS_CONFIRMATION'],
    ['template status', compiled.noteTemplate.status, 'active'],
    ['already-approved rows', fields.filter((f) => f.mapping?.approvedById).length, 0],
    ['CERTIFIED rows', fields.filter((f) => f.mapping?.mappingStatus === 'CERTIFIED').length, 0],
  ];
  let bad = 0;
  for (const [name, got, want] of g) {
    const ok = JSON.stringify(got) === JSON.stringify(want);
    if (!ok) bad += 1;
    console.log(`  guard ${ok ? '✓' : '🔴'} ${name}: ${JSON.stringify(got)} (expect ${JSON.stringify(want)})`);
  }
  if (bad > 0) throw new Error(`${bad} guard(s) failed — refusing. Nothing was written.`);

  const doctorId = compiled.noteTemplate.doctorId;
  const practiceId = compiled.noteTemplate.practiceId;
  if (!doctorId || !practiceId) throw new Error('template has no owning doctor/practice');
  const doctor = await prisma.user.findUnique({ where: { id: doctorId }, select: { id: true, email: true } });
  if (!doctor) throw new Error('owning doctor not found');

  // ── BUILD THE PAYLOAD. Concepts per field; synonyms EXPLICIT because the
  //    update path never re-seeds them.
  const before = fields.map((f) => f.mapping!);
  const payload: SemanticMapping[] = fields.map((f) => {
    const m = f.mapping!;
    const d = decide(f.originalLabel, { concept: m.clinicalConcept, sourceType: m.sourceType });
    const synonyms = d.concept
      ? [...new Set([
          ...synonymsFor(d.concept),
          // A SUB-CONCEPT mapping cites its own family's members? NO — a field
          // mapped to `allergy.substance` must match ONLY substance facts.
          // Nothing else is added; this set is the registry's spellings only.
        ])]
      : [];
    return {
      fieldId: f.fieldId,
      sourceType: d.sourceType,
      clinicalConcept: d.concept,
      expectedDataType: m.expectedDataType,
      polarityBehavior: m.polarityBehavior,
      temporality: m.temporality,
      laterality: m.laterality,
      unitPolicy: m.unitPolicy,
      approvedSynonyms: synonyms,
      required: m.required,
      blankPolicy: m.blankPolicy,
      unknownPolicy: m.unknownPolicy,
      practiceDefault: null,
      status: 'certified',
    } as unknown as SemanticMapping;
  });

  console.log('\n── PER-FIELD PLAN (before -> after) ──');
  let changed = 0;
  fields.forEach((f, i) => {
    const b = before[i]!;
    const a = payload[i]! as unknown as { clinicalConcept: string | null; sourceType: string; approvedSynonyms: string[] };
    const move = b.clinicalConcept !== a.clinicalConcept || b.sourceType !== a.sourceType;
    if (move) changed += 1;
    console.log(
      `  ${String(f.displayOrder).padStart(2)} ${f.originalLabel.slice(0, 26).padEnd(28)} ` +
        `${String(b.clinicalConcept ?? 'NULL').padEnd(22)}/${b.sourceType.padEnd(10)} -> ` +
        `${String(a.clinicalConcept ?? 'NULL').padEnd(24)}/${a.sourceType.padEnd(10)} ${move ? '★' : ' '} ` +
        `syn=${a.approvedSynonyms.length}`,
    );
  });
  console.log(`  fields whose concept or sourceType MOVES: ${changed}`);
  // ⚠️ A RUNTIME CHECK, NOT A LOG LINE — and the rehearsal is why it exists.
  // The DRY RUN was executed inside the production worker, which ships the
  // DEPLOYED code, and this threw `Cannot convert undefined or null to object`
  // because `REGISTRY_SUBCONCEPTS` does not exist there yet. That is (b) not
  // being deployed, reported by an accident rather than by a check. Now it is
  // a check: (c) writes sub-concept mappings, and a runtime whose registry has
  // never heard of them is a runtime where the next compile nulls them again.
  const families = REGISTRY_SUBCONCEPTS ? Object.keys(REGISTRY_SUBCONCEPTS) : [];
  console.log(`  registry sub-concept families in THIS runtime: ${families.length} [${families.join(', ')}]`);
  if (families.length === 0) {
    throw new Error(
      'REFUSING — this runtime has no REGISTRY_SUBCONCEPTS, so ruling #159(b) is ' +
        'not deployed here. (c) must run against a runtime that carries (b), or the ' +
        'concepts it writes are off-registry and the next compile nulls them.',
    );
  }

  if (!COMMIT) {
    console.log('\nDRY RUN — nothing written. Re-run with --commit through run-ruled-mutation.sh.');
    return;
  }

  // ── THE ACT, THROUGH THE APPLICATION PATH (#158(a)). ────────────────────
  const expectedSha = templateTwinMappingsSha256(
    before.map((m) => ({
      fieldId: fields.find((f) => f.mapping?.id === m.id)!.fieldId,
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
      status: m.mappingStatus === 'CERTIFIED' ? 'certified'
        : m.mappingStatus === 'RECOGNIZED' ? 'recognized' : 'needs_confirmation',
    })) as unknown as SemanticMapping[],
  );

  const actor = { userId: doctor.id, userEmail: doctor.email, practiceId };
  await updateTemplateTwinMappings({
    noteTemplateId: compiled.noteTemplate.id,
    actor,
    expectedMappingsSha256: expectedSha,
    mappings: payload,
  });

  // ── BY WHOSE HANDS. One append-only audit row per confirmed mapping.
  for (const f of fields) {
    await logTwinAudit({
      action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
      targetType: 'TemplateTwinSemanticMapping',
      targetId: f.mapping!.id,
      userId: doctor.id,
      userEmail: doctor.email,
      practiceId,
      metadata: {
        machineConfirmed: true,
        onOwnerAuthorization: 'ruling #158, amended 2026-08-31 — actor is the owning doctor identity',
        compiledVersionId: COMPILED_VERSION_ID,
        fieldId: f.fieldId,
        displayOrder: f.displayOrder,
      },
    });
  }

  // ── END-STATE ASSERTIONS. The declaration's rows, re-derived. ───────────
  const after = await prisma.templateTwinFieldDefinition.findMany({
    where: { compiledVersionId: COMPILED_VERSION_ID },
    include: { mapping: true },
  });
  const approved = after.filter((f) => f.mapping?.approvedById === doctor.id).length;
  const certified = after.filter((f) => f.mapping?.mappingStatus === 'CERTIFIED').length;
  const withTs = after.filter((f) => f.mapping?.approvedAt).length;
  console.log(`\n── END STATE ──`);
  console.log(`  CERTIFIED mappings          : ${certified} (expect ${EXPECT_FIELDS})`);
  console.log(`  approvedById = owning doctor: ${approved} (expect ${EXPECT_FIELDS})`);
  console.log(`  approvedAt set              : ${withTs} (expect ${EXPECT_FIELDS})`);
  if (certified !== EXPECT_FIELDS || approved !== EXPECT_FIELDS || withTs !== EXPECT_FIELDS) {
    throw new Error('END-STATE ASSERTION FAILED — see the numbers above.');
  }
  console.log('🟢 (c) complete.');
}

main()
  .catch((e) => { console.error('🔴', e instanceof Error ? e.message : e); process.exitCode = 1; })
  .finally(() => prisma.$disconnect());
