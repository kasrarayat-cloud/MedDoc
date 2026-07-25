// ============================================================================
// REAL-VISIT native-WORD proof — the doctor's own WM_IOV docx, back out.
// ----------------------------------------------------------------------------
// Certification proves the template. This proves the PRODUCT: a real visit, the
// live L4 over a dense bilateral reflux dictation, the twin fill step the worker
// runs, and then the exact function the DOCX export route calls.
//
//   DATABASE_URL=<db> NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX=true \
//     npx tsx scripts/prod-smoke/twin-visit-export.ts <out.docx>
//
// Cleans up the visit + fixture patient; audit rows survive (targetId is a
// plain string, no FK).
// ============================================================================

process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX = 'true';

import { writeFileSync } from 'node:fs';

import { prisma } from '@meddoc/db';

const say = (s: string) => console.log(`[visit] ${s}`);

const DICTATION = [
  'Bilateral lower extremity venous duplex reflux study.',
  'Right great saphenous vein at the saphenofemoral junction: diameter 6.2 millimeters, reflux 3.4 seconds.',
  'Right great saphenous vein at the knee: diameter 5.1 millimeters, no reflux.',
  'Left great saphenous vein at the saphenofemoral junction: diameter 5.8 millimeters, reflux 3.1 seconds.',
  'Left great saphenous vein at the proximal thigh: diameter 4.1 millimeters, reflux 1.8 seconds.',
  'No deep venous thrombosis identified bilaterally. Deep system competent.',
  'Impression: bilateral great saphenous vein incompetence, left greater than right.',
].join(' ');

async function main() {
  const out = process.argv[2] ?? '/app/twin-visit-export.docx';

  const compiled = await prisma.templateTwinCompiledVersion.findFirst({
    where: { certificationStatus: 'CERTIFIED' },
    select: { id: true, noteTemplateId: true, sourceArtifact: { select: { practiceId: true } } },
  });
  if (!compiled) throw new Error('no CERTIFIED compiled version on this database');

  const template = await prisma.noteTemplate.findUnique({
    where: { id: compiled.noteTemplateId },
    select: { id: true, version: true, doctorId: true, name: true },
  });
  const doctorId = template?.doctorId;
  if (!doctorId) throw new Error('certified template has no doctor');
  const practiceId = compiled.sourceArtifact.practiceId;
  say(`certified template "${template!.name}" (${template!.id}) doctor=${doctorId}`);

  let patientId: string | null = null;
  let visitId: string | null = null;
  try {
    const patient = await prisma.transcribeMdPatient.create({
      data: { practiceId, name: 'ZZ SYNTHETIC — twin export proof (not a patient)' },
      select: { id: true },
    });
    patientId = patient.id;

    const visit = await prisma.transcribeVisit.create({
      data: {
        userId: doctorId,
        patientId: patient.id,
        specialty: 'Vascular Surgery',
        inputMode: 'text_notes',
        transcriptText: DICTATION,
        noteTemplateId: template!.id,
        noteTemplateVersion: template!.version,
      },
      select: { id: true },
    });
    visitId = visit.id;
    say(`visit ${visit.id} created`);

    // L3 + L4 exactly as the worker runs them.
    const { extractTemplateTwinEntities } = await import('@/worker/layers/03-extract-entities');
    const { runLayer4GenerateSoap } = await import('@/worker/layers/04-generate-soap');
    const { normalizeTemplate } = await import('@/worker/note-templates/build-soap-prompt');
    const tmplRow = await prisma.noteTemplate.findUnique({
      where: { id: template!.id },
      select: { id: true, version: true, isSystemDefault: true, sections: true, styleProfile: true },
    });

    const extracted = await extractTemplateTwinEntities({
      mode: 'text',
      text: DICTATION,
      practiceId,
      userId: doctorId,
      noteTemplateId: template!.id,
    });
    say('L3 entities extracted');

    const note = await runLayer4GenerateSoap({
      visitId: visit.id,
      practiceId,
      userId: doctorId,
      specialty: 'Vascular Surgery',
      roleLabeledTranscript: extracted.contextText,
      entities: extracted.entities as never,
      audioConfidenceStats: null,
      noteTemplate: normalizeTemplate(tmplRow!),
    });
    await prisma.transcribeVisit.update({
      where: { id: visit.id },
      data: { soapFinal: note, status: 'READY' },
    });
    say(`L4 note generated (${note.length} chars)`);

    // The twin fill step the worker runs.
    const { processTemplateTwinVisit } = await import('@/lib/template-twin/fill-engine');
    await processTemplateTwinVisit({
      visitId: visit.id,
      practiceId,
      doctorId,
      noteTemplateId: template!.id,
      noteTemplateVersion: template!.version,
      inputMode: 'text',
      contextText: extracted.contextText,
      entities: extracted.entities,
      generatedNote: note,
      validationNow: new Date(),
      visitDate: new Date(),
      resolverModelVersion: null,
    });

    const manifest = await prisma.templateTwinFillManifest.findFirst({
      where: { visitId: visit.id },
      select: {
        status: true, filledCount: true, notMentionedCount: true,
        needsReviewCount: true, conflictCount: true,
        outputObjectKey: true, outputSha256: true, outputSizeBytes: true,
      },
    });
    say(`MANIFEST ${JSON.stringify(manifest)}`);

    // The exact function GET /api/visits/[id]/export/docx calls.
    const { loadOrComputeNativeTemplateDocxForVisit } = await import(
      '@/lib/template-twin/native-export'
    );
    const outcome = await loadOrComputeNativeTemplateDocxForVisit(visit.id, doctorId);
    say(`EXPORT nativeTemplateApplied=${!!outcome.native} nativeTemplateReason=${outcome.reason ?? 'n/a'}`);
    if (outcome.native) {
      writeFileSync(out, Buffer.from(outcome.native.bytes));
      say(`WROTE ${out} (${outcome.native.bytes.byteLength} bytes)`);
    }
  } finally {
    if (visitId) {
      await prisma.transcribeVisit.delete({ where: { id: visitId } }).catch(() => {});
    }
    if (patientId) {
      await prisma.transcribeMdPatient.delete({ where: { id: patientId } }).catch(() => {});
    }
  }
}

main()
  .catch((err) => {
    say(`FAILED verbatim: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}`);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
