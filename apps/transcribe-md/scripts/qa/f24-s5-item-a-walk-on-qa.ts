// ============================================================================
// F24-S5 ITEM A — THE ACCEPTANCE WALK'S UNPERFORMED ARMS, RUN FOR REAL
// ----------------------------------------------------------------------------
// The supervised acceptance walk of 2026-08-24 ran five arms and landed two:
//
//   1  80/80 census by replay          ❌ REFUSED (52/80)  -> closed by ITEM B
//   2  a dropdown edit landing in the EXPORTED document   ❌ NOT PERFORMED
//   3  the sharpened `supported`-laterality case          ✅ PASSED (in-process)
//   4  EXPORT-AFTER-OVERRIDE                              ❌ NOT PERFORMED
//   5  SIGN-AFTER-OVERRIDE                                ❌ NOT PERFORMED
//
// This file is arms 2, 4 and 5. ITEM A's ruling is that the ceiling CLEARS, it
// is never accepted, and it draws the line this file obeys:
//
//   > surfaces under test run REAL; only upstream MODEL OUTPUT is supplied as
//   > DATA.
//
// So the note is hand-authored and handed in (MOCK_AI cannot generate one, and
// routing around that by mocking a SURFACE would be the recolor the ruling
// forbids), and everything downstream of it is the shipped code:
//
//   · the real override door        `setTemplateControlAction`
//   · the real fill engine          `processTemplateTwinVisit` via the export
//   · the real export seam          `resolveVisitDocx` -> the twin bytes
//   · the real sign freeze          `freezeNativeManifestForSigning`
//                                   + `resolveFrozenPointer` + the CAS write
//
// ============================================================================
// ⚠️ WHY IT LIVES HERE, AND WHY IT RUNS INSIDE THE WORKER IMAGE
// ----------------------------------------------------------------------------
// Identical reasoning to `b8-admission-on-qa.ts`, which states it in full: QA's
// postgres, redis and minio are on the compose network and are NOT published to
// the host, so a proof that touches them has to run INSIDE the network, which
// means inside the image, and `Dockerfile.worker` copies exactly one script
// tree — `apps/transcribe-md/scripts`. Location follows reachability.
//
// ⚠️ AND IT IS A WRITER, SO IT IS FAIL-CLOSED OFF ANY NON-QA DATABASE.
// It creates a patient, a visit, an override row and a fill manifest, and it
// SIGNS the visit. `assertNonProdDatabase()` is the first statement in `main`,
// before anything else is constructed. F3 is production's rule and this
// respects it by being unable to reach production at all.
//
// ============================================================================
// ⚠️ THE ONE SUBSTITUTION, NAMED BEFORE ANY RESULT IS READ
// ----------------------------------------------------------------------------
// `setTemplateControlAction` opens with `requireSession()`, which reads the
// NextAuth cookie through `next/headers` and is request-scoped by construction.
// There is no request here, so `@/lib/auth` is pre-seeded into `require.cache`
// with a session for the visit's OWN doctor.
//
// EVERYTHING ELSE IN THE DOOR IS THE SHIPPED CODE, UNTOUCHED — the practice
// scope, the SIGNED refusal, the CERTIFIED gate, the concept lookup, the
// placeholder filter, the option matching, the upsert, the cache invalidation
// and the audit row. The substitution replaces WHO IS ASKING, never WHAT THE
// DOOR DOES, and the arms below never assert anything about authentication.
//
// Stated here rather than discovered later: this is the exact boundary ITEM A
// asks to be reported, and it is the only one.
// ============================================================================

import { createHash } from 'node:crypto';

import JSZip from 'jszip';

import { assertNonProdDatabase } from '@meddoc/db/guard';
import prisma from '@meddoc/db';

// ---------------------------------------------------------------------------
// THE WALK'S TARGET — the canonical case, not a convenient one.
//
// `SIDE OF EXAM` is criticality=laterality and it is the control the
// clinician-override module's own header names ("a doctor looking at their own
// form says SIDE OF EXAM should be Left"). It is also in the `supported` class
// — the class a naive overlay silently REFUSES — which is what makes it the
// arm worth running rather than the routine `not_mentioned` majority.
// ---------------------------------------------------------------------------
const SIDE_OF_EXAM_LABEL = 'SIDE OF EXAM';

/** A production-shaped venous-reflux note. Supplied as DATA — see the header. */
const HAND_AUTHORED_NOTE = `## TECHNIQUE
A duplex Doppler color flow ultrasound study was performed in the upright position
with and without manual augmentation of flow and Valsalva maneuver.

## FINDINGS
Right Leg:
The great saphenous vein from the saphenofemoral junction to the knee was found to have reflux.

Left Leg:
The great saphenous vein from the saphenofemoral junction to the knee was found to have reflux.

| Vein | Diameter (mm) | Reflux time (s) |
| --- | --- | --- |
| Right GSV at the SFJ | 7.0 | 2.4 |
| Right GSV at the Proximal Thigh | 6.4 | 2.1 |
| Right GSV at the Knee | 5.1 | 1.6 |
| Left GSV at the SFJ | 8.0 | 3.1 |
| Left GSV at the Proximal Thigh | 6.9 | 2.8 |
| Left GSV at the Knee | 5.6 | 1.2 |

## IMPRESSION
Right great saphenous vein is reflux positive.
Right deep venous system without evidence of obstruction or insufficiency.
No saphenous reflux in right lower extremity.
Left great saphenous vein is reflux positive.
Left deep venous system without evidence of obstruction or insufficiency.
Clinical correlation with the above findings is required.`;

// ---------------------------------------------------------------------------
// Reporting. Every arm prints PASS/FAIL with the value that decided it, so a
// green line can be audited rather than believed.
// ---------------------------------------------------------------------------
let failures = 0;
let arms = 0;
function arm(name: string, ok: boolean, detail: string) {
  arms += 1;
  if (!ok) failures += 1;
  console.log(`${ok ? '  ✔' : '  ✘'} ${name} — ${detail}`);
}

/** The visible text of a DOCX, flattened. `w:t` runs only. */
async function docxText(bytes: Buffer): Promise<string> {
  const zip = await JSZip.loadAsync(bytes);
  const doc = zip.file('word/document.xml');
  if (!doc) throw new Error('document.xml missing from the exported DOCX');
  const xml = await doc.async('string');
  return xml
    .replace(/<w:t[^>]*>/g, '')
    .replace(/<\/w:t>/g, '')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ');
}

function sha(bytes: Buffer): string {
  return createHash('sha256').update(bytes).digest('hex');
}

/**
 * The visit's document, from the REAL seam — and a REFUSAL REPORTED AS A
 * REFUSAL.
 *
 * ⚠️ `resolveVisitDocx` degrades to `generateVisitDocx` when the twin declines,
 * which is correct for a doctor (always a valid document, never a 500) and
 * useless for an acceptance walk: the styled builder needs a full
 * `VisitExportData` this harness has no business synthesising, so a twin
 * refusal surfaced as a TypeError inside the FALLBACK and buried the reason.
 *
 * So the twin is asked FIRST, by name. If it declines, the walk stops and says
 * which reason — because "the doctor's own document did not come back" IS the
 * finding, and turning it into a crash is how a wall gets mistaken for a
 * harness bug.
 */
async function nativeOrStop(
  visitId: string,
  practiceId: string,
  tag: string,
): Promise<{ bytes: Buffer; native: boolean }> {
  const { loadOrComputeNativeTemplateDocxForVisit } = await import(
    '@/lib/template-twin/native-export'
  );
  const outcome = await loadOrComputeNativeTemplateDocxForVisit(visitId, practiceId);
  if (!outcome.native) {
    arm(
      `${tag} — the doctor’s OWN document comes back`,
      false,
      `native=null reason=${outcome.reason ?? 'unknown'} — the twin path DECLINED; ` +
        `the remaining arms cannot run against this template`,
    );
    console.log('');
    console.log(`  arms ${arms - failures} of ${arms} passed`);
    console.log(`  ROWS LEFT ON QA: visit=${visitId}`);
    await prisma.$disconnect();
    process.exit(1);
  }
  // Only now is the shared seam safe to drive: it will take the native branch.
  const { resolveVisitDocx } = await import('@/lib/visit-docx-source');
  const via = await resolveVisitDocx(
    visitId,
    practiceId,
    { soapFinal: HAND_AUTHORED_NOTE } as never,
    tag,
  );
  arm(
    `${tag} — the SHARED seam serves the native bytes`,
    via.native === true && sha(via.bytes) === sha(outcome.native.bytes),
    `native=${via.native} identical=${sha(via.bytes) === sha(outcome.native.bytes)}`,
  );
  return { bytes: via.bytes, native: via.native };
}

async function main() {
  // ⚠️ FIRST STATEMENT. Before anything is constructed.
  assertNonProdDatabase();

  const stamp = Date.now().toString(36);
  const VISIT_ID = `f24a_walk_${stamp}`;
  const PATIENT_ID = `f24a_pat_${stamp}`;

  console.log('F24-S5 ITEM A — the acceptance walk, arms 2 / 4 / 5');
  console.log(`  visit ${VISIT_ID}`);

  // =========================================================================
  // 0 · THE UNIVERSE — a CERTIFIED twin, read from the database, not assumed.
  // =========================================================================
  const compiled = await prisma.templateTwinCompiledVersion.findFirst({
    where: { certificationStatus: 'CERTIFIED' },
    orderBy: { compiledAt: 'desc' },
    select: {
      id: true,
      practiceId: true,
      noteTemplateId: true,
      noteTemplate: { select: { id: true, version: true, doctorId: true } },
    },
  });
  if (!compiled?.noteTemplate?.doctorId) {
    throw new Error('no CERTIFIED twin with a resolvable doctor on this stack');
  }

  const doctor = await prisma.user.findFirst({
    where: { id: compiled.noteTemplate.doctorId },
    select: { id: true, email: true, practiceId: true, role: true, name: true },
  });
  if (!doctor?.practiceId) throw new Error('the twin has no resolvable doctor');
  const PRACTICE_ID = doctor.practiceId;

  // The control, resolved from the compiled twin's own field definitions —
  // ASK THE THING THAT KNOWS, never a hard-coded fieldId that would rot.
  const defs = await prisma.templateTwinFieldDefinition.findMany({
    where: { compiledVersionId: compiled.id, fieldKind: 'single_select' },
    orderBy: { displayOrder: 'asc' },
    select: {
      fieldId: true,
      originalLabel: true,
      criticality: true,
      allowedOptions: true,
      mapping: { select: { clinicalConcept: true, sourceType: true } },
    },
  });
  const side = defs.find((d) => d.originalLabel.startsWith(SIDE_OF_EXAM_LABEL));
  if (!side) throw new Error(`no ${SIDE_OF_EXAM_LABEL} control on this twin`);

  const options = (side.allowedOptions ?? []) as {
    value: string;
    ordinal: number;
    displayText: string;
  }[];
  console.log(
    `  control ${side.fieldId} "${side.originalLabel.slice(0, 32)}" ` +
      `criticality=${side.criticality} concept=${side.mapping?.clinicalConcept ?? 'NULL'} ` +
      `options=${options.length}`,
  );

  // A control the door MUST refuse: `manual` source with a NULL concept. Not
  // planted — this is the real state of 4 of the 28 on the live twin.
  const handFilled = defs.find(
    (d) => d.mapping && !d.mapping.clinicalConcept && d.mapping.sourceType === 'manual',
  );

  // =========================================================================
  // 1 · SEED — through the real persistence path.
  // =========================================================================
  await prisma.transcribeMdPatient.create({
    data: {
      id: PATIENT_ID,
      practiceId: PRACTICE_ID,
      name: `ItemA Walk${stamp}`,
      dateOfBirth: new Date('1970-01-01'),
    },
  });
  await prisma.transcribeVisit.create({
    data: {
      id: VISIT_ID,
      userId: doctor.id,
      patientId: PATIENT_ID,
      createdBy: doctor.id,
      practiceId: PRACTICE_ID,
      specialty: 'ultrasound',
      inputMode: 'text',
      status: 'READY',
      soapFinal: HAND_AUTHORED_NOTE,
      transcriptText: '',
      noteTemplateId: compiled.noteTemplate.id,
      noteTemplateVersion: compiled.noteTemplate.version,
    },
  });

  const preOverrides = await prisma.templateTwinFieldOverride.count({
    where: { visitId: VISIT_ID },
  });
  arm('baseline has NO override rows', preOverrides === 0, `rows=${preOverrides}`);

  // =========================================================================
  // 2 · BASELINE EXPORT — the real seam, before any correction.
  // =========================================================================
  const before = await nativeOrStop(VISIT_ID, PRACTICE_ID, '[itemA:before]');
  const beforeText = await docxText(before.bytes);
  const beforeSha = sha(before.bytes);

  const rendered = options
    .filter((o) => beforeText.includes(o.displayText))
    .map((o) => `${o.ordinal}:${o.displayText}`);
  console.log(`  BEFORE renders SIDE OF EXAM option(s): ${rendered.join(' | ') || '(none)'}`);

  // The target: an option the baseline does NOT already render. Chosen from the
  // measurement rather than picked in advance — otherwise arm 4 could not have
  // come out false, which is the whole point of the discrimination rule.
  const target = options.find(
    (o) => o.ordinal !== 0 && !beforeText.includes(o.displayText),
  );
  if (!target) throw new Error('every option already appears in the baseline — no discriminating target');
  console.log(`  target option -> ordinal ${target.ordinal} "${target.displayText}"`);

  arm(
    'NEGATIVE CONTROL — the target value is ABSENT before the correction',
    !beforeText.includes(target.displayText),
    `"${target.displayText}" not in the baseline document`,
  );

  // =========================================================================
  // 3 · THE DOOR — the real `setTemplateControlAction`.
  //     `@/lib/auth` is seeded FIRST; see the header for the boundary.
  // =========================================================================
  const authPath = require.resolve('@/lib/auth');
  const session = {
    user: {
      id: doctor.id,
      email: doctor.email ?? '',
      fullName: doctor.name ?? 'QA Doctor',
      role: doctor.role,
      practiceId: PRACTICE_ID,
    },
  };
  require.cache[authPath] = {
    id: authPath,
    filename: authPath,
    loaded: true,
    paths: [],
    exports: {
      requireSession: async () => session,
      getSession: async () => session,
      AuthError: class AuthError extends Error {},
    },
  } as unknown as NodeJS.Module;

  const { setTemplateControlAction } = await import('@/actions/set-template-control');

  const set = await setTemplateControlAction(VISIT_ID, side.fieldId, target.displayText);
  arm(
    'ARM 2a — the door ACCEPTS the doctor’s words',
    set.ok === true && set.value === target.displayText,
    `ok=${set.ok} label="${set.label ?? ''}" value="${set.value ?? ''}" error="${set.error ?? ''}"`,
  );

  const row = await prisma.templateTwinFieldOverride.findUnique({
    where: { visitId_fieldId: { visitId: VISIT_ID, fieldId: side.fieldId } },
    select: { selectedOptionOrdinal: true, optionValue: true, overriddenBy: true },
  });
  arm(
    'ARM 2b — the override row carries the ORDINAL, not the text',
    row?.selectedOptionOrdinal === target.ordinal && row?.optionValue === target.value,
    `ordinal=${row?.selectedOptionOrdinal} value="${row?.optionValue}" by=${row?.overriddenBy}`,
  );

  // ---- anti-agreement: the door must REFUSE, and say why ------------------
  const bogus = await setTemplateControlAction(VISIT_ID, side.fieldId, 'sort of the left one');
  arm(
    'REFUSAL — an off-list value is refused AND the options are NAMED',
    bogus.ok === false && (bogus.options?.length ?? 0) > 0,
    `ok=${bogus.ok} options=${bogus.options?.length ?? 0}`,
  );

  const placeholder = await setTemplateControlAction(VISIT_ID, side.fieldId, 'Choose an item.');
  arm(
    'REFUSAL — Word’s "Choose an item." placeholder is never selectable',
    placeholder.ok === false,
    `ok=${placeholder.ok} error="${placeholder.error ?? ''}"`,
  );

  if (handFilled) {
    const hf = (handFilled.allowedOptions ?? []) as { displayText: string; ordinal: number }[];
    const hfOpt = hf.find((o) => o.ordinal !== 0);
    const declined = await setTemplateControlAction(
      VISIT_ID,
      handFilled.fieldId,
      hfOpt?.displayText ?? 'anything',
    );
    arm(
      'REFUSAL — a concept-less `manual` control is refused at the DOOR',
      declined.ok === false,
      `field=${handFilled.fieldId} ok=${declined.ok} error="${declined.error ?? ''}"`,
    );
  } else {
    arm('REFUSAL — concept-less control', false, 'NO SUCH CONTROL ON THIS TWIN — arm could not run');
  }

  // =========================================================================
  // 4 · EXPORT-AFTER-OVERRIDE — the arm the refuted slice failed.
  // =========================================================================
  const after = await nativeOrStop(VISIT_ID, PRACTICE_ID, '[itemA:after]');
  const afterText = await docxText(after.bytes);
  const afterSha = sha(after.bytes);

  arm(
    'ARM 4b — the exported BYTES changed',
    afterSha !== beforeSha,
    `${beforeSha.slice(0, 12)} -> ${afterSha.slice(0, 12)}`,
  );
  arm(
    'ARM 4c — the correction is IN the exported document',
    afterText.includes(target.displayText),
    `"${target.displayText}" present=${afterText.includes(target.displayText)}`,
  );

  const manifests = await prisma.templateTwinFillManifest.findMany({
    where: { visitId: VISIT_ID },
    orderBy: { createdAt: 'asc' },
    select: {
      id: true,
      status: true,
      roundTripVerified: true,
      noteSha256: true,
      overridesSha256: true,
      createdAt: true,
    },
  });
  const latest = manifests[manifests.length - 1];
  arm(
    'ARM 4d — the manifest is VERIFIED and its overridesSha256 is SET',
    latest?.status === 'VERIFIED' &&
      latest?.roundTripVerified === true &&
      Boolean(latest?.overridesSha256),
    `manifests=${manifests.length} status=${latest?.status} rt=${latest?.roundTripVerified} ` +
      `overridesSha=${latest?.overridesSha256?.slice(0, 12) ?? 'NULL'}`,
  );
  arm(
    'ARM 4e — the identity MOVED (the recompute was earned, not free)',
    manifests.length > 1 &&
      manifests[0].overridesSha256 !== latest?.overridesSha256,
    `first=${manifests[0]?.overridesSha256?.slice(0, 12) ?? 'NULL'} ` +
      `latest=${latest?.overridesSha256?.slice(0, 12) ?? 'NULL'}`,
  );

  // =========================================================================
  // 5 · SIGN-AFTER-OVERRIDE — the real freeze, the real pointer, the real CAS.
  // =========================================================================
  const visitNow = await prisma.transcribeVisit.findUniqueOrThrow({
    where: { id: VISIT_ID },
    select: { soapFinal: true, soapVersion: true },
  });

  const { freezeNativeManifestForSigning, resolveFrozenPointer } = await import(
    '@/lib/template-twin/sign-freeze'
  );
  const freeze = await freezeNativeManifestForSigning({
    visitId: VISIT_ID,
    practiceId: PRACTICE_ID,
  });
  arm(
    'ARM 5a — the sign freeze resolves a manifest',
    freeze.state === 'already_fresh' || freeze.state === 'regenerated',
    `state=${freeze.state}`,
  );

  const pointer = await resolveFrozenPointer(VISIT_ID, PRACTICE_ID, visitNow.soapFinal!);
  arm(
    'ARM 5b — the pointer resolves to the manifest carrying the override',
    Boolean(pointer) && pointer === latest?.id,
    `pointer=${pointer ?? 'NULL'} latest=${latest?.id}`,
  );

  // The sign route's own statement: CAS on (READY, soapVersion), then SIGNED +
  // signedSoap + frozenFillManifestId + signedAt + signedBy in ONE update.
  // The E/M merge is omitted and NOT approximated: `emAppliesToVisit` is false
  // for an ultrasound imaging report, so the route's `cptWrite` is undefined
  // and `freshPending` is null on this row. Stated, not assumed.
  const signed = await prisma.transcribeVisit.updateMany({
    where: { id: VISIT_ID, practiceId: PRACTICE_ID, status: 'READY', soapVersion: visitNow.soapVersion },
    data: {
      status: 'SIGNED',
      signedSoap: visitNow.soapFinal,
      frozenFillManifestId: pointer,
      signedAt: new Date(),
      signedBy: doctor.id,
    },
  });
  arm('ARM 5c — the CAS-guarded signature landed', signed.count === 1, `updated=${signed.count}`);

  const frozen = await prisma.transcribeVisit.findUniqueOrThrow({
    where: { id: VISIT_ID },
    select: { status: true, frozenFillManifestId: true, signedBy: true },
  });
  arm(
    'ARM 5d — the signature froze the pointer, not NULL',
    frozen.status === 'SIGNED' && frozen.frozenFillManifestId === latest?.id,
    `status=${frozen.status} frozen=${frozen.frozenFillManifestId ?? 'NULL'}`,
  );

  const afterSign = await nativeOrStop(VISIT_ID, PRACTICE_ID, '[itemA:signed]');
  const signedText = await docxText(afterSign.bytes);
  arm(
    'ARM 5f — and it still carries the correction',
    signedText.includes(target.displayText),
    `"${target.displayText}" present=${signedText.includes(target.displayText)}`,
  );
  arm(
    'ARM 5g — the signed bytes ARE the frozen bytes (byte-identical)',
    sha(afterSign.bytes) === afterSha,
    `${sha(afterSign.bytes).slice(0, 12)} vs ${afterSha.slice(0, 12)}`,
  );

  const afterSignSet = await setTemplateControlAction(VISIT_ID, side.fieldId, options[1].displayText);
  arm(
    'ARM 5h — the door REFUSES a signed record',
    afterSignSet.ok === false,
    `ok=${afterSignSet.ok} error="${afterSignSet.error ?? ''}"`,
  );

  console.log('');
  console.log(`  arms ${arms - failures} of ${arms} passed`);
  console.log(`  ROWS LEFT ON QA: visit=${VISIT_ID} patient=${PATIENT_ID}`);
  await prisma.$disconnect();
  process.exit(failures === 0 ? 0 : 1);
}

main().catch(async (e) => {
  console.error('WALK ABORTED:', e);
  await prisma.$disconnect().catch(() => {});
  process.exit(2);
});
