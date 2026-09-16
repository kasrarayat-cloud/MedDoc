// ============================================================================
// #319 REGISTRY-2 — certify the colon operative-note twin under the new registry,
// then supersede the PDF-native operative note. ONE-SHOT RULED ACT.
// ----------------------------------------------------------------------------
// This drives the SAME production lifecycle the worker uses (createTemplateTwinDraft
// -> updateTemplateTwinMappings -> runTemplateTwinSyntheticTest -> certifyAndActivate)
// but replaces `planAutoConfirm` with an EXPLICIT, owner-authorised mapping set:
//
//   • ruling #319 fixes the mapping BY CONSTRUCTION, so the concepts are set from
//     the ruling's own table rather than trusted to a model run — deterministic,
//     and the whole point of REGISTRY-2;
//   • the record-derived header fields (visit_metadata) are CONFIRMED here, which
//     the auto path deliberately declines (decideAutoConfirm) so a human sees a
//     control that prints a patient value — the ruled act IS that human act;
//   • the three Findings and three Recommendations slots are given BYTE-IDENTICAL
//     mappings so they satisfy bullet-group rule G7 and DISTRIBUTE one item per
//     slot instead of printing the whole joined list in every slot.
//
// It first PRINTS the model's own proposal (evidence the registry fix now maps a
// colon note correctly) and the practice's template state, then certifies, then
// retires the PDF-native operative note (status 'inactive' — demoted, never
// deleted) and pins the practice default to the GI consult. Every step reports
// its outcome for the judgement; it certifies NOTHING on its own if the real
// round-trip proof throws.
//
// Args (positional; docker exec forwards args, not env):
//   npx tsx scripts/certify-colon-twin-319.ts \
//     <docxPath> <userId> <userEmail> <practiceId> <pdfNativeTemplateId> <defaultTemplateId>
// Run inside transcribe-md-worker via scripts/run-ruled-mutation.sh --in transcribe-md-worker.
// ============================================================================
import { readFileSync } from 'node:fs';
import { exitCleanly } from './lib/exit-cleanly';
import { createHash } from 'node:crypto';

import { createTemplateTwinDraft } from '@/lib/template-twin/create-draft';
import { readTemplateTwinWorkspace } from '@/lib/template-twin/workspace-read';
import {
  updateTemplateTwinMappings,
  certifyAndActivateTemplateTwin,
} from '@/lib/template-twin/certification-lifecycle';
import { runTemplateTwinSyntheticTest } from '@/lib/template-twin/synthetic-test';
import { extractTemplateTwinEntities } from '@/worker/layers/03-extract-entities';
import { createEphemeralVisitNoteGenerator } from '@/worker/template-twin-note-generator';
import { deriveVerificationEncounter } from '@/lib/template-twin/verification-encounter';
import type { SemanticMapping } from '@/lib/template-twin/ir';
import prisma from '@meddoc/db';

// Ruling #319's mapping table, keyed by the twin's compiled label. The numbered
// slots share a label by design (their bullet-group identity), so both entries
// resolve here.
const CONCEPT_BY_LABEL: Record<string, string> = {
  'Patient Name': 'visit_metadata.patient_name',
  'Patient DOB': 'visit_metadata.date_of_birth',
  'Patient ID': 'visit_metadata.patient_id',
  'Date of Surgery': 'visit_metadata.date_of_service',
  Surgeon: 'procedure.surgeon',
  Procedure: 'procedure.performed',
  'Preoperative Diagnosis': 'procedure.preop_diagnosis',
  Consent: 'procedure.consent',
  'Description of Procedure': 'procedure.description',
  Findings: 'procedure.findings',
  Recommendations: 'procedure.recommendations',
  DD: 'visit_metadata.dictated_at',
  DT: 'visit_metadata.transcribed_at',
};

// The numbered slots are given a byte-identical mapping (except fieldId, the one
// key bullet-group G7 excludes) so the three slots group and distribute.
const IDENTICAL_LIST_MAPPING = (fieldId: string, concept: string): SemanticMapping =>
  ({
    fieldId,
    clinicalConcept: concept,
    sourceType: 'extraction',
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: null,
    laterality: 'not_applicable',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    conceptScope: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
  }) as unknown as SemanticMapping;

async function ownerTemplates(practiceId: string) {
  return prisma.noteTemplate.findMany({
    where: { practiceId },
    select: {
      id: true,
      name: true,
      status: true,
      encounterType: true,
      templateTwinCompiledVersion: { select: { certificationStatus: true } },
    },
    orderBy: { createdAt: 'asc' },
  });
}

async function main() {
  const [docxPath, userId, userEmail, practiceId, pdfNativeId, defaultTemplateId] =
    process.argv.slice(2);
  if (!docxPath || !userId || !userEmail || !practiceId) {
    throw new Error(
      'usage: certify-colon-twin-319.ts <docxPath> <userId> <userEmail> <practiceId> [pdfNativeId] [defaultTemplateId]',
    );
  }
  const actor = { userId, userEmail, practiceId };
  const source = new Uint8Array(readFileSync(docxPath));
  const sha = createHash('sha256').update(source).digest('hex');
  console.log(`[319] source ${docxPath} bytes=${source.byteLength} sha256=${sha}`);

  console.log('[319] BEFORE — practice templates:');
  for (const t of await ownerTemplates(practiceId)) console.log('   ', JSON.stringify(t));

  // 1. Draft — re-proposes under the new registry.
  const draft = await createTemplateTwinDraft({ source, actor });
  console.log(`[319] DRAFT ${draft.noteTemplateId} sourceSha=${draft.sourceSha256}`);

  // 2. Read + LOG the model's own proposal (evidence the registry fix works).
  const ws = await readTemplateTwinWorkspace({
    noteTemplateId: draft.noteTemplateId,
    doctorId: userId,
    practiceId,
  });
  if (!ws) throw new Error('workspace_not_found after draft');
  console.log('[319] MODEL PROPOSAL under REGISTRY-2:');
  for (const { field, mapping } of ws.fields) {
    console.log(
      `   ${JSON.stringify(field.originalLabel)} -> ${mapping.clinicalConcept} ` +
        `[src=${mapping.sourceType} status=${mapping.status}]`,
    );
  }

  // 3. Correct + normalize per ruling #319. Numbered slots get the byte-identical
  //    mapping; every other field keeps the compiler's sourceType/expectedDataType
  //    and takes the ruling's concept, cleared synonyms/scope, and confirmed.
  const corrected: SemanticMapping[] = ws.fields.map(({ field, mapping }) => {
    const label = field.originalLabel ?? '';
    const concept = CONCEPT_BY_LABEL[label];
    if (!concept) throw new Error(`ruling #319 has no concept for label ${JSON.stringify(label)}`);
    if (label === 'Findings' || label === 'Recommendations') {
      return IDENTICAL_LIST_MAPPING(field.fieldId, concept);
    }
    return {
      ...mapping,
      clinicalConcept: concept,
      approvedSynonyms: [],
      conceptScope: [],
      status: 'certified',
    } as unknown as SemanticMapping;
  });

  await updateTemplateTwinMappings({
    noteTemplateId: draft.noteTemplateId,
    actor,
    expectedMappingsSha256: ws.mappingsSha256,
    mappings: corrected,
  });
  console.log('[319] mappings corrected + confirmed (17 fields)');

  // 4. Re-read (persisting changed the mappings sha the proof binds to).
  const persisted = await readTemplateTwinWorkspace({
    noteTemplateId: draft.noteTemplateId,
    doctorId: userId,
    practiceId,
  });
  if (!persisted) throw new Error('reread_failed after update');

  // 5. The REAL synthetic round-trip — live L3 + fill, deriving the encounter
  //    from THIS form's confirmed fields.
  await runTemplateTwinSyntheticTest({
    noteTemplateId: draft.noteTemplateId,
    actor,
    expectedMappingsSha256: persisted.mappingsSha256,
    deriveEncounter: () =>
      deriveVerificationEncounter(
        persisted.fields.map(({ field, mapping }) => ({
          originalLabel: field.originalLabel,
          clinicalConcept: mapping.clinicalConcept,
        })),
      ),
    encounterMode: 'dictation',
    extractEntities: extractTemplateTwinEntities,
    generateNote: createEphemeralVisitNoteGenerator({
      specialty: persisted.template.encounterType ?? 'General',
    }),
  });
  console.log('[319] synthetic round-trip PASSED');

  // 6. Certify + activate.
  const reread = await readTemplateTwinWorkspace({
    noteTemplateId: draft.noteTemplateId,
    doctorId: userId,
    practiceId,
  });
  if (!reread) throw new Error('reread_failed before certify');
  await certifyAndActivateTemplateTwin({
    noteTemplateId: draft.noteTemplateId,
    actor,
    expectedMappingsSha256: reread.mappingsSha256,
  });
  console.log('[319] CERTIFIED + ACTIVATED');

  // 7. Supersede the PDF-native operative note — retire (status inactive), never
  //    delete. The picker keys on certificationStatus, not status, so this removes
  //    it from the legacy active mechanism without touching any twin's choosability.
  if (pdfNativeId) {
    const before = await prisma.noteTemplate.findUnique({
      where: { id: pdfNativeId },
      select: { id: true, name: true, status: true },
    });
    console.log(`[319] PDF-native before: ${JSON.stringify(before)}`);
    if (before && before.status !== 'inactive') {
      await prisma.noteTemplate.update({ where: { id: pdfNativeId }, data: { status: 'inactive' } });
    }
    const after = await prisma.noteTemplate.findUnique({
      where: { id: pdfNativeId },
      select: { id: true, name: true, status: true },
    });
    console.log(`[319] PDF-native RETIRED: ${JSON.stringify(after)}`);
  }

  // 8. Keep the GI consult as the practice default.
  if (defaultTemplateId) {
    await prisma.practice.update({
      where: { id: practiceId },
      data: { defaultNoteTemplateId: defaultTemplateId },
    });
    const p = await prisma.practice.findUnique({
      where: { id: practiceId },
      select: { defaultNoteTemplateId: true },
    });
    console.log(`[319] practice default set: ${JSON.stringify(p)}`);
  }

  console.log('[319] AFTER — practice templates:');
  for (const t of await ownerTemplates(practiceId)) console.log('   ', JSON.stringify(t));

  const nt = await prisma.noteTemplate.findUnique({
    where: { id: draft.noteTemplateId },
    select: {
      id: true,
      name: true,
      status: true,
      templateTwinCompiledVersion: { select: { certificationStatus: true } },
    },
  });
  console.log(`[319] TWIN now: ${JSON.stringify(nt)}`);
  console.log(`[319] DONE noteTemplateId=${draft.noteTemplateId}`);
}

main()
  .then(() => exitCleanly(0))
  .catch((e) => {
    console.error('[319] FAILED:', e?.stack ?? e?.message ?? e);
    exitCleanly(1);
  });
