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

// A REAL dictation for this form — what a vascular surgeon actually says when
// reading a bilateral venous duplex, in the vocabulary the form's own dropdowns
// use. It deliberately does NOT mention the technologist, referring physician,
// machine or location: nobody dictates those, and the proof is that they come
// back BLANK. It also leaves the SSV, accessory and below-knee segments
// unstated, so most of the grid stays blank too.
const DICTATION = [
  'Bilateral lower extremity venous duplex reflux study, bilateral detailed.',
  'Clinical indication: chronic venous insufficiency with aching, heaviness and swelling.',
  'Technique: patient examined standing, with augmentation and Valsalva maneuvers.',
  'Right leg. Great saphenous vein at the saphenofemoral junction: diameter 6.2 millimeters, reflux 3.4 seconds.',
  'Right great saphenous vein at the proximal thigh: diameter 5.5 millimeters, reflux 2.2 seconds.',
  'Right great saphenous vein at the knee: diameter 5.1 millimeters, reflux 1.5 seconds.',
  'Left leg. Great saphenous vein at the saphenofemoral junction: diameter 5.8 millimeters, reflux 3.1 seconds.',
  'Left great saphenous vein at the proximal thigh: diameter 4.1 millimeters, reflux 1.8 seconds.',
  'Left great saphenous vein at the knee: diameter 3.9 millimeters, reflux 1.1 seconds.',
  'The small saphenous veins and the accessory saphenous veins were not evaluated on this study.',
  'No deep venous thrombosis identified bilaterally. The deep system is competent.',
  'Impression: bilateral great saphenous vein incompetence, left greater than right.',
  'Diagnosis: Chronic venous hypertension with other complications of bilateral lower extremities.',
].join(' ');

async function main() {
  const out = process.argv[2] ?? '/app/twin-visit-export.docx';

  const compiled = await prisma.templateTwinCompiledVersion.findFirst({
    where: { certificationStatus: 'CERTIFIED' },
    // Newest first. QA accumulates certified versions across runs, and an
    // unordered findFirst would silently prove an older template than the one
    // just certified.
    orderBy: { compiledAt: 'desc' },
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
    // ── DIAGNOSTIC DUMP ──────────────────────────────────────────────────
    writeFileSync('/app/diag-l4-note.txt', note);
    const tableLines = note.split('\n').filter((l) => l.trim().startsWith('|'));
    say(`DIAG note pipe-lines=${tableLines.length}`);
    for (const l of tableLines.slice(0, 12)) say(`DIAG  ${l.trim().slice(0, 120)}`);
    const { parseMarkdownTables } = await import('@/lib/template-twin/bridge-fill-diag');
    const parsed = parseMarkdownTables(note);
    say(`DIAG parseMarkdownTables -> ${parsed.length} table(s)`);
    for (const t of parsed) say(`DIAG  header=[${t.header.join(' | ')}] rows=${t.rows.length} labels=[${t.rows.slice(0,4).map((r) => r.label).join(' / ')}]`);
    // IR rows the bridge wants to match
    const irCells = (await prisma.templateTwinCompiledVersion.findUnique({
      where: { id: compiled.id }, select: { compiledDocumentIr: true },
    }))!.compiledDocumentIr as { fields: { originalLabel: string; tableId: string | null; rendererBinding: { rowIndex: number | null } }[] };
    const rows = irCells.fields.filter((f) => f.tableId);
    say(`DIAG IR table cells=${rows.length}; first labels=[${rows.slice(0, 6).map((f) => f.originalLabel).join(' / ')}]`);
    // facts the picks/measurements must cite
    const facts = (extracted.entities as { facts?: unknown[] } | null);
    writeFileSync('/app/diag-facts.json', JSON.stringify(extracted.entities, null, 2).slice(0, 200000));
    say(`DIAG entities dumped`);

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
        fillManifest: true,
        validationResult: true,
      },
    });
    const { fillManifest: body, validationResult, ...counts } = manifest ?? {
      fillManifest: null,
      validationResult: null,
    };
    say(`MANIFEST ${JSON.stringify(counts)}`);
    // A NEEDS_REVIEW manifest means the fill did not validate; say WHICH fields
    // and why, rather than reporting a count and leaving the reason unstated.
    const validation = validationResult as {
      issues?: { fieldId: string; code: string; severity: string }[];
    } | null;
    const blocking = (validation?.issues ?? []).filter((i) => i.severity === 'blocking');
    say(`BLOCKING ${blocking.length}`);
    const byCode = new Map<string, number>();
    for (const i of blocking) byCode.set(i.code, (byCode.get(i.code) ?? 0) + 1);
    for (const [code, n] of byCode) say(`  blocking ${n} ${code}`);
    const irAll = (await prisma.templateTwinCompiledVersion.findUnique({
      where: { id: compiled.id }, select: { compiledDocumentIr: true },
    }))!.compiledDocumentIr as { fields: { fieldId: string; originalLabel: string }[] };
    const label = new Map(irAll.fields.map((f) => [f.fieldId, f.originalLabel]));
    const fieldsOut = (body as { fields?: { fieldId: string; status: string; value: unknown; reasonCode: string }[] } | null)?.fields ?? [];
    for (const i of blocking.slice(0, 12)) {
      const f = fieldsOut.find((x) => x.fieldId === i.fieldId);
      say(`  ${i.code} "${String(label.get(i.fieldId)).slice(0, 30)}" status=${f?.status} value=${JSON.stringify(f?.value)} reason=${f?.reasonCode}`);
    }

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
