// ============================================================================
// (d), STEP 1 — RUN THE SYNTHETIC TEST **FRESH**, AND CERTIFY NOTHING.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS IS SPLIT FROM THE FLIP. The banked proof on this compiled version
// was produced by the OLD renderer, before the #165–#175 arc changed what the
// clear does and what a proof may claim. Certifying from it would attest a
// round-trip that the shipped code no longer performs. So the proof is minted
// FRESH here, inspected, and only then is the flip run separately via
// `certify-live-template.ts --certify-only`, which re-verifies the stored proof
// rather than taking it on trust.
//
// ⚠️ IT USES THE PRODUCTION WIRING VERBATIM — the same thunk, the same
// `extractTemplateTwinEntities`, the same `createEphemeralVisitNoteGenerator`
// that `src/actions/template-twin-certify.ts` passes on a doctor's own click. A
// self-test that runs a DIFFERENT chain from the one a visit runs is a proof
// about the wrong universe.
//
// This spends ONE real model generation. MOCK_AI_CALLS is false in production.
// ============================================================================
import prisma from '@meddoc/db';

import { readTemplateTwinWorkspace } from '../src/lib/template-twin/workspace-read';
import { runTemplateTwinSyntheticTest } from '../src/lib/template-twin/synthetic-test';
import { deriveVerificationEncounter } from '../src/lib/template-twin/verification-encounter';
import { extractTemplateTwinEntities } from '../src/worker/layers/03-extract-entities';
import { createEphemeralVisitNoteGenerator } from '../src/worker/template-twin-note-generator';

const COMPILED_VERSION_ID = '9e758c45-ac65-4996-bea8-6fc1f8b1c96c';

async function main() {
  console.log(`db target: ${new URL(process.env.DATABASE_URL ?? 'postgres://x/x').hostname}`);
  console.log(`MOCK_AI_CALLS: ${process.env.MOCK_AI_CALLS ?? '<unset>'}  (must be false for a REAL fill)`);

  const compiled = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: COMPILED_VERSION_ID },
    include: {
      noteTemplate: {
        select: { id: true, name: true, encounterType: true, doctorId: true, practiceId: true },
      },
      fields: { include: { mapping: true }, orderBy: { displayOrder: 'asc' } },
    },
  });
  if (!compiled) throw new Error('compiled version not found');

  const doctorId = compiled.noteTemplate.doctorId!;
  const practiceId = compiled.noteTemplate.practiceId!;
  const doctor = await prisma.user.findUnique({
    where: { id: doctorId },
    select: { id: true, email: true },
  });
  if (!doctor) throw new Error('owning doctor not found');
  const actor = { userId: doctor.id, userEmail: doctor.email, practiceId };

  const rows = compiled.fields;
  console.log(`\ntemplate : ${compiled.noteTemplate.name}`);
  console.log(`fields   : ${rows.length}`);
  console.log(`status   : ${compiled.certificationStatus}`);

  // ── THE PROOF THAT IS ABOUT TO BE REPLACED, so the swap is visible ────────
  const before = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: COMPILED_VERSION_ID },
    select: { latestSyntheticTestManifest: true, latestTestOutputSha256: true },
  });
  const beforeSha = before?.latestTestOutputSha256 ?? null;
  console.log(`\n── THE BANKED PROOF (produced by the OLD renderer) ──`);
  console.log(`  outputSha256: ${beforeSha ? beforeSha.slice(0, 16) + '…' : '<none>'}`);

  const ws = await readTemplateTwinWorkspace({
    noteTemplateId: compiled.noteTemplate.id,
    doctorId,
    practiceId,
  });
  if (!ws) throw new Error('workspace not readable for the owning doctor');
  const expectedMappingsSha256 = (ws as unknown as { mappingsSha256: string }).mappingsSha256;

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

  // ── THE FRESH PROOF ───────────────────────────────────────────────────────
  const after = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: COMPILED_VERSION_ID },
    select: {
      latestSyntheticTestManifest: true,
      latestTestOutputSha256: true,
      certificationStatus: true,
    },
  });
  const afterSha = after?.latestTestOutputSha256 ?? null;
  console.log(`\n── THE FRESH PROOF ──`);
  console.log(`  outputSha256: ${afterSha ? afterSha.slice(0, 16) + '…' : '<none>'}`);
  console.log(`  MOVED off the banked proof: ${beforeSha !== afterSha}`);
  console.log(`  certificationStatus still: ${after?.certificationStatus}  (nothing was flipped here)`);

  // ⚠️ THE KEY IS `fields`, NOT `resolutions`. Reading the wrong one reports
  // "FILLED 0" for a manifest that holds fifteen, and a zero from a missing key
  // is indistinguishable from a zero that is true.
  const manifest = (after?.latestSyntheticTestManifest ?? null) as
    | {
        fields?: Array<{
          fieldId: string;
          status?: string;
          value?: unknown;
          reasonCode?: string;
          kind?: string;
        }>;
      }
    | null;
  const entries = manifest?.fields ?? [];
  if (entries.length === 0) {
    throw new Error(
      'REFUSING to print a fill map from an EMPTY manifest — either the test did ' +
        'not run or this reader is looking at the wrong key. A zero here must ' +
        'never be mistaken for "nothing filled".',
    );
  }

  const byField = new Map(entries.map((r) => [r.fieldId, r]));

  console.log(`\n═══ FILL MAP — every field, before any flip ═══`);
  let filled = 0;
  for (const f of rows) {
    const r = byField.get(f.fieldId);
    const v = r?.value;
    const isFilled = r != null && v !== null && v !== undefined;
    if (isFilled) filled += 1;
    console.log(
      `  ${String(f.displayOrder).padStart(2)} ${f.originalLabel.slice(0, 28).padEnd(30)}` +
        `${(f.mapping?.clinicalConcept ?? 'NULL').padEnd(24)}` +
        `${(f.mapping?.sourceType ?? '?').padEnd(10)}` +
        `${isFilled ? 'FILLED  ' : 'blank   '}${String(r?.reasonCode ?? '-').slice(0, 30)}`,
    );
  }
  console.log(`\n  FILLED ${filled} / ${rows.length}`);

  await prisma.$disconnect();
}

main().catch(async (e) => {
  console.error('🔴', e instanceof Error ? e.message : e);
  await prisma.$disconnect();
  process.exitCode = 1;
});
