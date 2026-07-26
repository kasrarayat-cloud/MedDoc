// ============================================================================
// Template-Twin GA proof — confirm -> synthetic test -> CERTIFY -> native fill.
// ----------------------------------------------------------------------------
// QA STACK ONLY, and that is a deliberate constraint rather than convenience.
//
// Reaching CERTIFIED means marking every semantic mapping confirmed. On a real
// clinician's template that confirmation IS the safety gate — a human agreeing
// that "this dropdown means reflux time, in seconds, right leg". A script
// asserting it on their behalf would hollow the gate out completely. Here the
// doctor and the template are both synthetic fixtures, so there is no clinical
// judgement being forged; there is nothing to forge.
//
//   DATABASE_URL=<qa> npx tsx scripts/prod-smoke/twin-ga-proof.ts "<file.docx>"
//
// Prints each gate and the verbatim failure if one blocks.
// ============================================================================

process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX = 'true';

import { readFileSync, writeFileSync } from 'node:fs';

import { prisma } from '@meddoc/db';

const say = (s: string) => console.log(`[ga] ${s}`);

async function main() {
  const file = process.argv[2];
  const bytes = new Uint8Array(readFileSync(file));

  // The actor is ALWAYS a synthetic fixture. Confirming eighty mappings is the
  // clinical safety gate; a script asserting it on a real clinician's template
  // would hollow it out. On QA that is the qa- user; on prod it is the
  // smoke-doctor account, named explicitly rather than discovered.
  const actorEmail = process.env.TWIN_SMOKE_ACTOR_EMAIL;
  const user = await prisma.user.findFirst({
    where: actorEmail ? { email: actorEmail } : { email: { contains: 'qa-' } },
    select: { id: true, practiceId: true, email: true },
  });
  if (!user) throw new Error(`no synthetic actor on this database (${actorEmail ?? 'qa-*'})`);
  const actor = { userId: user.id, userEmail: user.email, practiceId: user.practiceId };
  say(`actor ${user.email}`);

  const { createTemplateTwinDraft } = await import('@/lib/template-twin/create-draft');
  const { readTemplateTwinWorkspace } = await import('@/lib/template-twin/workspace-read');
  const { updateTemplateTwinMappings, certifyAndActivateTemplateTwin } = await import(
    '@/lib/template-twin/certification-lifecycle'
  );
  const { runTemplateTwinSyntheticTest } = await import('@/lib/template-twin/synthetic-test');
  const { extractTemplateTwinEntities } = await import('@/worker/layers/03-extract-entities');
  const { createEphemeralVisitNoteGenerator } = await import('@/worker/template-twin-note-generator');

  const created = await createTemplateTwinDraft({ source: bytes, actor });
  const noteTemplateId = created.noteTemplateId;
  say(`draft ${noteTemplateId} fields=${created.fieldCount}`);

  let ws = await readTemplateTwinWorkspace({
    noteTemplateId,
    doctorId: user.id,
    practiceId: user.practiceId,
  });
  if (!ws) throw new Error('workspace not readable');
  const tmpl = await prisma.noteTemplate.findUnique({
    where: { id: noteTemplateId },
    select: { name: true, sections: true },
  });
  const labels = ((tmpl?.sections as unknown as { label?: string }[]) ?? []).map((s) => s.label);
  say(`BRIDGE  name="${tmpl?.name}" sections=[${labels.join(' | ')}]`);

  // ── confirm every mapping (see the header for why this is QA-only) ───────
  const confirmed = ws.fields.map((f) => ({ ...f.mapping, status: 'certified' as const }));
  ws = await updateTemplateTwinMappings({
    noteTemplateId,
    actor,
    expectedMappingsSha256: ws.mappingsSha256,
    mappings: confirmed,
  });
  say(`CONFIRM ${confirmed.length} mappings -> sha ${ws.mappingsSha256.slice(0, 12)}`);

  // ── synthetic roundtrip (required by the certification gate) ─────────────
  // The evidence gate REQUIRES an explicit synthetic marker (synthetic |
  // fictional | mock | test | example) so a mislabeled real encounter can
  // never be persisted as a certification proof. Satisfy it honestly rather
  // than routing around it.
  // Dense bilateral reflux narrative. Three things it must do at once:
  //   * state >= 10 enumerated picks IN THE OPTIONS' OWN WORDING, so the live
  //     brain's CHOICE_SLOT picks have facts to cite;
  //   * state multiple measurements per leg, so the measurement cells fill and
  //     the >= 1-cell floor is met by real evidence;
  //   * DELIBERATELY leave segments unmentioned (SSV, AAGSV, PAGSV, below-knee)
  //     so the >= 1-blank invariant keeps exercising blank behaviour.
  // The evidence gate still requires the explicit synthetic marker.
  const ENCOUNTER = [
    'SYNTHETIC TEST ENCOUNTER — fictional data, not a real patient.',
    'Bilateral lower extremity venous duplex reflux study, bilateral detailed.',
    'Clinical indication: chronic venous insufficiency with aching, heaviness and swelling.',
    'Technique: patient examined standing, with augmentation and Valsalva maneuvers.',
    'Right leg. Great saphenous vein at the saphenofemoral junction: diameter 7 millimeters, reflux 2.4 seconds.',
    'Right great saphenous vein at the proximal thigh: diameter 6.4 millimeters, reflux 2.1 seconds.',
    'Right great saphenous vein at the knee: diameter 5.1 millimeters, reflux 1.6 seconds.',
    'Left leg. Great saphenous vein at the saphenofemoral junction: diameter 8 millimeters, reflux 3.1 seconds.',
    'Left great saphenous vein at the proximal thigh: diameter 6.9 millimeters, reflux 2.8 seconds.',
    'Left great saphenous vein at the knee: diameter 5.6 millimeters, reflux 1.2 seconds.',
    'The small saphenous veins and the accessory saphenous veins were not evaluated on this study.',
    'No deep venous thrombosis identified bilaterally. The deep system is competent.',
    'Impression: bilateral great saphenous vein incompetence, left greater than right.',
    'Diagnosis: Chronic venous hypertension with other complications of bilateral lower extremities.',
  ].join(' ');
  try {
    await runTemplateTwinSyntheticTest({
      noteTemplateId,
      actor,
      expectedMappingsSha256: ws.mappingsSha256,
      encounterText: ENCOUNTER,
      encounterMode: 'text',
      // Use the REAL L3 extractor. An earlier run stubbed this to an empty
      // entity set, which made every field resolve "notMentioned" (filled=0)
      // and left only the 28 content controls in the roundtrip proof — a
      // measurement of the STUB, not of the renderer. Re-prove with the real
      // thing before concluding anything about table-cell fill.
      extractEntities: extractTemplateTwinEntities,
      generateNote: createEphemeralVisitNoteGenerator({ specialty: 'Vascular Surgery' }),
    });
    say('SYNTHETIC test: OK');
  } catch (err) {
    say(`SYNTHETIC test FAILED verbatim: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}`);
    return;
  }

  ws = await readTemplateTwinWorkspace({
    noteTemplateId,
    doctorId: user.id,
    practiceId: user.practiceId,
  });
  try {
    await certifyAndActivateTemplateTwin({
      noteTemplateId,
      actor,
      expectedMappingsSha256: ws!.mappingsSha256,
    });
  } catch (err) {
    say(`CERTIFY FAILED verbatim: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}`);
    return;
  }

  const compiled = await prisma.templateTwinCompiledVersion.findFirst({
    where: { noteTemplateId },
    select: {
      id: true,
      certificationStatus: true,
      latestSyntheticTestManifest: true,
      latestTestRoundTrip: true,
    },
  });
  const mf = compiled?.latestSyntheticTestManifest as { counts?: unknown; fields?: unknown[] } | null;
  const rt = compiled?.latestTestRoundTrip as { fields?: unknown[] } | null;
  say(`FILL counts=${JSON.stringify(mf?.counts)} manifestFields=${mf?.fields?.length ?? 0}`);
  say(`PROOF roundTrip.fields=${rt?.fields?.length ?? 0} (IR declares 80)`);
  say(`CERTIFY status=${compiled?.certificationStatus}`);

  // ── the payoff: the doctor's own document back, filled ──────────────────
  // The synthetic proof's artifact lives ON the compiled version — the separate
  // fill-manifest table belongs to VISITS. Reading the wrong one reported
  // "MANIFEST NONE" for a run that had in fact produced and verified a document.
  const artifact = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: compiled!.id },
    select: {
      latestTestOutputObjectKey: true,
      latestTestOutputSha256: true,
      latestTestMappingsSha256: true,
    },
  });
  const manifest = artifact?.latestTestOutputObjectKey
    ? {
        status: 'verified',
        outputObjectKey: artifact.latestTestOutputObjectKey,
        outputSha256: artifact.latestTestOutputSha256,
        outputSizeBytes: null as number | null,
      }
    : null;
  say(`MAPPINGS sha=${String(artifact?.latestTestMappingsSha256).slice(0, 12)}`);
  say(
    `MANIFEST ${manifest ? `status=${manifest.status} bytes=${manifest.outputSizeBytes} sha=${String(manifest.outputSha256).slice(0, 12)}` : 'NONE'}`
  );
  if (manifest?.outputObjectKey) {
    const { createTemplateTwinArtifactStore } = await import('@/lib/template-twin/storage');
    const store = createTemplateTwinArtifactStore();
    const out = await store.readOutputArtifact({
      practiceId: user.practiceId,
      objectKey: manifest.outputObjectKey,
      expectedSha256: manifest.outputSha256!,
    });
    writeFileSync('/app/twin-native-output.docx', Buffer.from(out));
    say(`NATIVE DOCX written: ${out.byteLength} bytes`);
  }
}

main()
  .catch((err) => {
    say(`UNCAUGHT verbatim: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}`);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
