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

const COMPILED_VERSION_ID = '87223c49-cf2b-4d7f-a905-3e6e595863ad';
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
  const manifest = (after?.latestSyntheticTestManifest ?? null) as
    | { resolutions?: Array<{ fieldId: string; status?: string; value?: unknown; reasonCode?: string }> }
    | null;
  const byField = new Map<string, { status?: string; value?: unknown; reasonCode?: string }>();
  for (const r of manifest?.resolutions ?? []) byField.set(r.fieldId, r);

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
