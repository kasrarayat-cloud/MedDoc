// ============================================================================
// (d) — CERTIFY THE OWNER'S LIVE TEMPLATE, WITH THE REAL CHAIN.
// ----------------------------------------------------------------------------
// Ruling #159's fourth step: compile -> derive -> REAL fill -> CERTIFIED.
//
//   report only (default):  npx tsx scripts/certify-live-template.ts
//   certify:                ... --commit
//
// ⚠️ THE FILL MAP IS PRINTED FIRST, ALWAYS, AND THAT IS RULING #159'S ORDER.
// "If filled coverage still lands under 10 after (a)-(d), the session REPORTS
// THE PER-FIELD FILL MAP BEFORE TOUCHING THE FLOOR. The floor never lowers
// without its own ruling." So this script cannot reach a floor decision without
// having printed the evidence a human would need to disagree with it.
//
// ⚠️ IT USES THE PRODUCTION WIRING VERBATIM — the same thunk, the same
// `extractTemplateTwinEntities`, the same `createEphemeralVisitNoteGenerator`
// that `src/actions/template-twin-certify.ts` passes. A self-test that runs a
// DIFFERENT chain from the one a doctor's visit runs is a proof about the wrong
// universe, and this programme has paid for that mistake already.
// ============================================================================
import prisma from '@meddoc/db';

import { certifyAndActivateTemplateTwin } from '../src/lib/template-twin/certification-lifecycle';
import { readTemplateTwinWorkspace } from '../src/lib/template-twin/workspace-read';
import { runTemplateTwinSyntheticTest } from '../src/lib/template-twin/synthetic-test';
import { deriveVerificationEncounter } from '../src/lib/template-twin/verification-encounter';
import { MIN_CERTIFIED_FILLED_FIELDS } from '../src/lib/template-twin/certification-thresholds';
import { extractTemplateTwinEntities } from '../src/worker/layers/03-extract-entities';
import { createEphemeralVisitNoteGenerator } from '../src/worker/template-twin-note-generator';

/**
 * ⚠️ PARAMETERISED, AND THE HARD-CODED CONSTANT IS GONE — the same treatment
 * #1055 gave the transfer tool, for the same reason.
 *
 * It read `'9e758c45-ac65-4996-bea8-6fc1f8b1c96c'`, a PAST act's target. A
 * one-shot script pinned to the version it was written for cannot certify the
 * next one, and the failure is quiet in the worst way: point it at today's
 * problem and it silently certifies YESTERDAY'S template, reporting success.
 *
 * ⚠️ REQUIRED, NEVER DEFAULTED — no "the active one", no "the newest". A default
 * here picks a clinical template on the operator's behalf. `--compiled-version`
 * must be stated, and `--expect-fields` must match what is found, so the
 * declaration and the act have to agree about which document is being
 * certified before anything is written.
 */
function requiredArg(name: string): string {
  const i = process.argv.indexOf(`--${name}`);
  if (i < 0 || i + 1 >= process.argv.length) {
    console.error(`🔴 certify: missing required argument --${name}`);
    console.error('   Nothing was certified.');
    process.exit(2);
  }
  const v = process.argv[i + 1]!;
  if (v.startsWith('--') || v.trim() === '') {
    console.error(`🔴 certify: --${name} needs a value`);
    console.error('   Nothing was certified.');
    process.exit(2);
  }
  return v;
}

function requiredInt(name: string): number {
  const raw = requiredArg(name);
  // ⚠️ STRICT — `parseInt('53x')` is 53, and a count that accepts garbage is a
  // guard reporting a number nobody meant.
  if (!/^\d+$/.test(raw)) {
    console.error(`🔴 certify: --${name} must be a plain integer, got '${raw}'`);
    console.error('   Nothing was certified.');
    process.exit(2);
  }
  return Number(raw);
}

const COMPILED_VERSION_ID = requiredArg('compiled-version');
const EXPECT_FIELDS = requiredInt('expect-fields');
const COMMIT = process.argv.includes('--commit');
// ⚠️ CERTIFY AGAINST THE PROOF ALREADY STORED, RATHER THAN MINTING A NEW ONE.
// The first --commit run was killed (SIGTERM) AFTER the synthetic test wrote its
// manifest and output sha and BEFORE certification. Re-running the whole chain
// would spend a second model generation and OVERWRITE a proof that is already
// stored and verified — replacing evidence for no reason. This path re-uses it;
// `certifyAndActivateTemplateTwin` re-verifies the stored proof itself, so
// nothing is taken on trust.
const CERTIFY_ONLY = process.argv.includes('--certify-only');

async function main() {
  const host = new URL(process.env.DATABASE_URL ?? 'postgres://x/x').hostname;
  console.log(`db target: ${host}`);
  console.log(`mode     : ${COMMIT ? '⚠️  COMMIT (certifies)' : 'REPORT ONLY'}`);

  const compiled = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: COMPILED_VERSION_ID },
    include: {
      noteTemplate: { select: { id: true, name: true, encounterType: true, doctorId: true, practiceId: true } },
      fields: { include: { mapping: true }, orderBy: { displayOrder: 'asc' } },
    },
  });
  if (!compiled) throw new Error('compiled version not found');
  // ⚠️ THE DECLARED SHAPE, CHECKED BEFORE ANYTHING IS WRITTEN. If the caller
  // and the database disagree about how many controls this template has, they
  // are talking about different documents — and certification is the act that
  // makes one of them fillable.
  if (compiled.fields.length !== EXPECT_FIELDS) {
    console.error(
      `🔴 certify: --expect-fields ${EXPECT_FIELDS} but ${COMPILED_VERSION_ID} has ${compiled.fields.length}`,
    );
    console.error('   Nothing was certified.');
    process.exit(2);
  }
  console.log(`target   : ${COMPILED_VERSION_ID}  (${compiled.fields.length} fields, as declared)`);
  const doctorId = compiled.noteTemplate.doctorId!;
  const practiceId = compiled.noteTemplate.practiceId!;
  const doctor = await prisma.user.findUnique({ where: { id: doctorId }, select: { id: true, email: true } });
  if (!doctor) throw new Error('owning doctor not found');
  const actor = { userId: doctor.id, userEmail: doctor.email, practiceId };

  // ── PRE-STATE, so the report is a COMPARISON and not a snapshot ──────────
  const rows = compiled.fields;
  const certified = rows.filter((f) => f.mapping?.mappingStatus === 'CERTIFIED').length;
  const manual = rows.filter((f) => f.mapping?.sourceType === 'manual').length;
  console.log(`\n── PRE-STATE ──`);
  console.log(`  fields ${rows.length} · CERTIFIED ${certified} · manual(attested blank) ${manual}`);
  console.log(`  certificationStatus: ${compiled.certificationStatus}`);
  console.log(`  MIN_CERTIFIED_FILLED_FIELDS = ${MIN_CERTIFIED_FILLED_FIELDS}  (never lowered here)`);

  // ── THE DERIVATION, through the production thunk ─────────────────────────
  const derived = deriveVerificationEncounter(
    rows.map((f) => ({
      originalLabel: f.originalLabel,
      clinicalConcept: f.mapping?.clinicalConcept ?? null,
    })),
  );
  // ⚠️ READ THE UNION PROPERLY. `DerivedEncounter` is
  // `{ok:true,text}` | `{ok:false,reason}` — an earlier version of this script
  // probed `.contextText`/`.kind`, which exist on NEITHER arm, and printed
  // "0 chars" for a derivation that was in fact fine. That zero measured my own
  // field name, not the encounter.
  console.log(`\n── DERIVED ENCOUNTER ──`);
  if (!derived.ok) {
    console.log(`  🔴 NOT DERIVABLE — reason: ${derived.reason}`);
    console.log('  The synthetic self-test cannot run, so certification cannot proceed.');
    console.log('  This is a DESIGNED refusal (#156(d)): no certification without a round-trip self-test.');
    return;
  }
  console.log(`  ok: true · dictation chars: ${derived.text.length}`);
  console.log(`  first 240: ${derived.text.slice(0, 240).replace(/\n/g, ' / ')}`);

  // ⚠️ THE SHA COMES FROM THE WORKSPACE READER, NOT FROM A HAND ROLL. It is the
  // same `templateTwinMappingsSha256` over the same mappings the lifecycle will
  // re-derive, so an optimistic-concurrency mismatch here would be a real
  // change under us rather than two implementations disagreeing.
  const ws = await readTemplateTwinWorkspace({
    noteTemplateId: compiled.noteTemplate.id,
    doctorId,
    practiceId,
  });
  if (!ws) throw new Error('workspace not readable for the owning doctor');
  const expectedMappingsSha256 = (ws as unknown as { mappingsSha256: string }).mappingsSha256;
  console.log(`  mappingsSha256: ${expectedMappingsSha256.slice(0, 16)}…`);

  if (!COMMIT && !CERTIFY_ONLY) {
    console.log('\nREPORT ONLY — no synthetic test run, nothing certified.');
    console.log('Re-run with --commit to run the REAL chain and certify.');
    return;
  }

  if (!CERTIFY_ONLY) {
  console.log(`\n── RUNNING THE REAL CHAIN (one model generation) ──`);
  await runTemplateTwinSyntheticTest({
    noteTemplateId: compiled.noteTemplate.id,
    actor,
    expectedMappingsSha256,
    deriveEncounter: () =>
      deriveVerificationEncounter(
        rows.map((f) => ({
          originalLabel: f.originalLabel,
          clinicalConcept: f.mapping?.clinicalConcept ?? null,
        })),
      ),
    encounterMode: 'dictation',
    extractEntities: extractTemplateTwinEntities,
    generateNote: createEphemeralVisitNoteGenerator({
      specialty: compiled.noteTemplate.encounterType ?? 'General',
    }),
  });
  console.log('  synthetic test: COMPLETE');
  } else {
    console.log(`\n── REUSING THE STORED PROOF (--certify-only) ──`);
  }

  // ── THE FILL MAP, FROM THE STORED MANIFEST — #159's required report ──────
  const after = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: COMPILED_VERSION_ID },
    select: { latestSyntheticTestManifest: true, certificationStatus: true },
  });
  // ⚠️ THE KEY IS `fields`, NOT `resolutions` — AND THE FIRST VERSION READ THE
  // WRONG ONE. It reported "FILLED 0 / 35" for a run whose manifest held 15
  // filled, because `manifest.resolutions` is undefined and an empty map makes
  // every field look blank. A zero from a missing key is indistinguishable from
  // a zero that is true, which is why the fill map given to the owner was taken
  // from SQL reading the right key rather than from this reader.
  const manifest = (after?.latestSyntheticTestManifest ?? null) as
    | { fields?: Array<{ fieldId: string; status?: string; value?: unknown; reasonCode?: string }> }
    | null;
  const entries = manifest?.fields ?? [];
  // NON-VACUITY: an empty manifest must announce itself rather than print a
  // plausible all-blank map.
  if (entries.length === 0) {
    throw new Error(
      'REFUSING to print a fill map from an EMPTY manifest — either the synthetic ' +
        'test has not run, or this reader is looking at the wrong key. A zero here ' +
        'must never be mistaken for "nothing filled".',
    );
  }
  const byField = new Map<string, { status?: string; value?: unknown; reasonCode?: string }>();
  for (const r of entries) byField.set(r.fieldId, r);

  console.log(`\n═══ FILL MAP — #159's REQUIRED REPORT, PRINTED BEFORE ANY FLOOR DECISION ═══`);
  let filled = 0;
  for (const f of rows) {
    const r = byField.get(f.fieldId);
    const v = r?.value;
    const isFilled = r != null && v !== null && v !== undefined;
    if (isFilled) filled += 1;
    const concept = f.mapping?.clinicalConcept ?? 'NULL';
    const src = f.mapping?.sourceType ?? '?';
    console.log(
      `  ${String(f.displayOrder).padStart(2)} ${f.originalLabel.slice(0, 26).padEnd(28)}` +
        `${concept.padEnd(24)}${src.padEnd(11)}` +
        `${isFilled ? 'FILLED  ' : 'blank   '}${String(r?.reasonCode ?? '-').slice(0, 34)}`,
    );
  }
  console.log(`\n  FILLED ${filled} / ${rows.length}   floor ${MIN_CERTIFIED_FILLED_FIELDS}` +
    `   ${filled >= MIN_CERTIFIED_FILLED_FIELDS ? '✅ meets the floor' : '🔴 UNDER THE FLOOR — report, do NOT lower it'}`);

  console.log(`\n── CERTIFY ──`);
  const wsAfter = await certifyAndActivateTemplateTwin({
    noteTemplateId: compiled.noteTemplate.id,
    actor,
    expectedMappingsSha256,
  });
  console.log(`  certificationStatus: ${(wsAfter as { template?: { certificationStatus?: string } }).template?.certificationStatus}`);
  console.log('🟢 (d) complete.');
}

main()
  .catch((e) => { console.error('🔴', e instanceof Error ? e.message : e); process.exitCode = 1; })
  .finally(() => prisma.$disconnect());
