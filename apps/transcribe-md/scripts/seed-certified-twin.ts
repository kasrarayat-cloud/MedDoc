// ============================================================================
// Seed a GENUINE CERTIFIED Template Twin into a non-prod stack, with NO model
// calls. This is the fixture the visit-doc E2E project needs.
// ----------------------------------------------------------------------------
// WHY THIS EXISTS
//
// visit-document.spec.ts refuses to skip: "no CERTIFIED twin in this stack —
// fixture missing" FAILS the run. That is the right posture — a Phase-2 suite
// that quietly skipped because its fixture was absent proved nothing — but CI
// had no way to produce a certified twin, so all 14 specs failed on the
// fixture rather than on the code.
//
// WHAT THIS RUNS — the REAL path, end to end:
//
//   createTemplateTwinDraft   the REAL docx compiler, over the committed
//                             fixture form (80 fields, 28 content controls)
//   updateTemplateTwinMappings  the REAL mapping write + sha guard
//   runTemplateTwinSyntheticTest  the REAL fill -> render -> roundtrip proof
//   certifyAndActivateTemplateTwin  the REAL certification gate, unmodified
//
// Nothing about the certification gate is relaxed, and no row is forced to
// CERTIFIED behind its back. The template certifies because it genuinely
// passes — coverage floors, blank-verification, roundtrip integrity and all.
//
// WHAT IS PINNED, AND WHY THAT IS NOT A SHORTCUT
//
// Two inputs to that path are models: Layer-3 extraction, and constrained-fill
// note generation. Both are stochastic, and certification was a coin flip
// because of it — one run filled a control, the next left it
// NEEDS_CLINICIAN_INPUT and blocked. Production already solved this: the
// compiled version carries a CONTENT-ADDRESSED pin of (note, entities,
// contextText) keyed by (encounterSha256, templateSha256), and
// synthetic-test.ts reuses it whenever both hashes match.
//
// This seeder writes that pin from a committed fixture minted once on QA
// against the live models. The pinned note still flows through
// bridge -> matcher -> validator -> renderer -> roundtrip exactly as a fresh
// one would; only the stochastic INPUT is fixed. That is the mechanism
// production ships, used for the purpose it was built for.
//
// FAIL-CLOSED, EVERYWHERE
//
// Every hash is re-verified before use, and the injected extractor and note
// generator THROW if they are ever reached. So if the compiler's structure
// hash moves, or the fixture drifts from the docx, this script dies loudly
// with the reason — it can never quietly fall through to a live model call
// (which in CI would mean dummy keys, or a mocked brain attesting itself).
//
//   DATABASE_URL=<non-prod> npx tsx scripts/seed-certified-twin.ts
//
// Never prod: @meddoc/db/guard fails closed on a non-marked database, and the
// actor is always a synthetic fixture account.
// ============================================================================

process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX = 'true';

import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { Prisma, prisma } from '@meddoc/db';

const say = (s: string) => console.log(`[twin-seed] ${s}`);
const sha256 = (b: Uint8Array | string) =>
  createHash('sha256')
    .update(typeof b === 'string' ? Buffer.from(b, 'utf8') : Buffer.from(b))
    .digest('hex');

/** The committed pin, and the form it was minted against. */
const FIXTURES = join(__dirname, '..', 'tests', 'e2e', 'fixtures');
const PINS_PATH = join(FIXTURES, 'twin-certified-pins.json');
const DOCX_PATH = join(FIXTURES, 'sample-form.docx');

/** The visit seedVisitDocVisit() clones. Owned by the synthetic actor, NOT a
 *  qa-e2e-* user, so afterEach cleanup cannot cascade it away. */
const DONOR_VISIT_ID = 'qa_twin_donor';

interface PinnedMapping {
  fieldId: string;
  [key: string]: unknown;
}

interface PinFixture {
  sourceDocxSha256: string;
  encounterSha256: string;
  templateSha256: string;
  noteModelVersion: string;
  encounterText: string;
  note: string;
  contextText: string;
  entities: unknown;
  mappings: PinnedMapping[];
}

async function main() {
  const pins = JSON.parse(readFileSync(PINS_PATH, 'utf8')) as PinFixture;
  const docx = new Uint8Array(readFileSync(DOCX_PATH));

  // ── CONTENT-ADDRESS CHECKS #1 and #2 — before anything is written ────────
  const docxSha = sha256(docx);
  if (docxSha !== pins.sourceDocxSha256) {
    throw new Error(
      `fixture docx drifted from the pin: sample-form.docx is ${docxSha}, ` +
        `the pin was minted against ${pins.sourceDocxSha256}. Re-mint with ` +
        'scripts/prod-smoke/twin-ga-proof.ts on QA against the new form.',
    );
  }
  const encSha = sha256(pins.encounterText);
  if (encSha !== pins.encounterSha256) {
    throw new Error(
      `pin fixture is internally inconsistent: sha256(encounterText)=${encSha} ` +
        `but encounterSha256=${pins.encounterSha256}.`,
    );
  }
  say(`fixture OK docx=${docxSha.slice(0, 12)} encounter=${encSha.slice(0, 12)}`);

  // The actor is ALWAYS a synthetic fixture account. Confirming eighty
  // mappings is a clinical safety gate; asserting it for a real clinician
  // would hollow it out. Here the doctor and the form are both synthetic, so
  // there is no clinical judgement being forged.
  const actorEmail = process.env.TWIN_SEED_ACTOR_EMAIL;
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

  // ── 1. REAL COMPILE ─────────────────────────────────────────────────────
  const created = await createTemplateTwinDraft({ source: docx, actor });
  const noteTemplateId = created.noteTemplateId;
  say(`COMPILE draft=${noteTemplateId} fields=${created.fieldCount}`);

  const compiled = await prisma.templateTwinCompiledVersion.findFirst({
    where: { noteTemplateId },
    select: { id: true, structureSha256: true },
  });
  if (!compiled) throw new Error('compile produced no compiled version');

  // ── CONTENT-ADDRESS CHECK #3 — the one that protects the whole scheme ────
  // synthetic-test.ts only reuses a pin when templateSha256 matches the
  // compiled structure hash. If the compiler's output moved, the pin would be
  // silently ignored and the run would reach for a live model. Refuse first.
  if (compiled.structureSha256 !== pins.templateSha256) {
    throw new Error(
      `the compiler's structure hash moved: compiled ${compiled.structureSha256}, ` +
        `pin ${pins.templateSha256}. The pin would be IGNORED and certification ` +
        'would try to call a live model. Re-mint the pin on QA with ' +
        'scripts/prod-smoke/twin-ga-proof.ts, then commit the new fixture.',
    );
  }
  say(`STRUCTURE matches pin ${compiled.structureSha256.slice(0, 12)}`);

  // ── 2. INSTALL THE PIN (content-addressed, exactly as production stores it)
  await prisma.templateTwinCompiledVersion.update({
    where: { id: compiled.id },
    data: {
      pinnedSyntheticNote: pins.note,
      pinnedSyntheticEntities: pins.entities as never,
      pinnedSyntheticContextText: pins.contextText,
      pinnedNoteEncounterSha256: pins.encounterSha256,
      pinnedNoteTemplateSha256: pins.templateSha256,
      pinnedNoteModelVersion: pins.noteModelVersion,
      pinnedNoteGeneratedAt: new Date(),
    },
  });
  say(`PIN installed on compiled=${compiled.id}`);

  // ── 3. REAL MAPPING CONFIRMATION, from the PINNED proposal ──────────────
  // The mapping proposal is the THIRD model call on this path, and unlike the
  // note and the extraction it has no in-product pin. Under MOCK_AI_CALLS the
  // proposer returns all 80 fields as sourceType='extraction' with a NULL
  // clinicalConcept, and updateTemplateTwinMappings then rejects every one of
  // them — correctly, because a certified non-manual mapping must cite a
  // concept. So the confirmed set is pinned alongside the note.
  //
  // What is NOT bypassed: updateTemplateTwinMappings still runs in full and
  // re-validates each mapping (field-set identity, type compatibility, the
  // practice-default law, concept-presence). It is the same act twin-ga-proof
  // performs on QA — a synthetic doctor confirming a synthetic form — captured
  // once instead of regenerated per run.
  let ws = await readTemplateTwinWorkspace({
    noteTemplateId,
    doctorId: user.id,
    practiceId: user.practiceId,
  });
  if (!ws) throw new Error('workspace not readable');

  // ── CONTENT-ADDRESS CHECK #4 — the compiled field set must be EXACTLY the
  // pinned one. A compiler that adds, drops or renames a field would otherwise
  // surface as a confusing FIELD_SET_MISMATCH from deep inside the lifecycle.
  const compiledIds = [...ws.fields.map((f) => f.mapping.fieldId)].sort();
  const pinnedIds = [...pins.mappings.map((m) => m.fieldId)].sort();
  if (
    compiledIds.length !== pinnedIds.length ||
    compiledIds.some((id, i) => id !== pinnedIds[i])
  ) {
    throw new Error(
      `compiled field set differs from the pinned mapping set ` +
        `(${compiledIds.length} compiled vs ${pinnedIds.length} pinned). ` +
        'Re-mint the pin on QA with scripts/prod-smoke/twin-ga-proof.ts.',
    );
  }

  ws = await updateTemplateTwinMappings({
    noteTemplateId,
    actor,
    expectedMappingsSha256: ws.mappingsSha256,
    mappings: pins.mappings as never,
  });
  say(`CONFIRM ${pins.mappings.length} pinned mappings -> sha ${ws.mappingsSha256.slice(0, 12)}`);

  // ── 4. REAL SYNTHETIC TEST, with the models FENCED OFF ──────────────────
  // These are the proof that this seeder is deterministic. If the pin is
  // honoured, neither is ever invoked; if the pin were missed for any reason,
  // we die here instead of quietly attesting a mocked or live-model run.
  const refuseExtractor = async () => {
    throw new Error(
      'L3 EXTRACTOR REACHED — the pinned extraction was not used. The seed is ' +
        'no longer deterministic; re-check encounterSha256/templateSha256.',
    );
  };
  const refuseGenerator = async () => {
    throw new Error(
      'NOTE GENERATOR REACHED — the pinned note was not used. The seed is no ' +
        'longer deterministic; re-check encounterSha256/templateSha256.',
    );
  };

  await runTemplateTwinSyntheticTest({
    noteTemplateId,
    actor,
    expectedMappingsSha256: ws.mappingsSha256,
    // F5-i: a thunk, evaluated below the readiness gates. The seed PINS its
    // encounter (determinism is the whole contract here — see the sha warning
    // above), so it returns that pin rather than deriving.
    deriveEncounter: () => ({ ok: true, text: pins.encounterText }),
    encounterMode: 'text',
    extractEntities: refuseExtractor,
    generateNote: refuseGenerator,
  });
  say('SYNTHETIC test: OK (no model call — both seams refused and never reached)');

  // ── 5. REAL CERTIFICATION GATE ──────────────────────────────────────────
  ws = await readTemplateTwinWorkspace({
    noteTemplateId,
    doctorId: user.id,
    practiceId: user.practiceId,
  });
  await certifyAndActivateTemplateTwin({
    noteTemplateId,
    actor,
    expectedMappingsSha256: ws!.mappingsSha256,
  });

  // ── 6. PROVE IT, rather than trusting the absence of a throw ────────────
  const final = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: compiled.id },
    select: {
      certificationStatus: true,
      compiledDocumentIr: true,
      latestTestRoundTrip: true,
      latestSyntheticTestManifest: true,
    },
  });
  const ir = final?.compiledDocumentIr as { fields?: unknown[] } | null;
  const rt = final?.latestTestRoundTrip as
    | { fields?: unknown[]; verified?: unknown; packageCheck?: unknown; fieldCheck?: unknown; staticRegionCheck?: unknown }
    | null;
  const mf = final?.latestSyntheticTestManifest as { counts?: unknown } | null;

  if (final?.certificationStatus !== 'CERTIFIED') {
    throw new Error(`certification did not land: status=${final?.certificationStatus}`);
  }
  const irCount = ir?.fields?.length ?? 0;
  const rtCount = rt?.fields?.length ?? 0;
  if (irCount === 0 || rtCount !== irCount) {
    throw new Error(
      `roundtrip proof does not cover the IR: ${rtCount} proof entries vs ${irCount} IR fields`,
    );
  }
  if (
    rt?.verified !== true ||
    rt?.packageCheck !== 'verified' ||
    rt?.fieldCheck !== 'verified' ||
    rt?.staticRegionCheck !== 'verified'
  ) {
    throw new Error('roundtrip proof is not fully verified');
  }

  say(`CERTIFY status=CERTIFIED proof=${rtCount}/${irCount} fields`);
  say(`FILL counts=${JSON.stringify(mf?.counts)}`);

  // ── 7. A DONOR VISIT THAT SURVIVES CLEANUP ──────────────────────────────
  // seedVisitDocVisit() needs two things, and returns null if EITHER is
  // missing: a certified twin, and a visit row to clone. The caller reports
  // both as "no CERTIFIED twin in this stack — fixture missing", so a missing
  // donor accuses the wrong thing entirely.
  //
  // It clones rather than enumerating columns, deliberately — hand-listing this
  // table's NOT NULL columns is how a seed drifts from production. But in an
  // ephemeral stack there may be nothing to clone: cleanupTestUsers() runs in
  // afterEach and deletes every qa-e2e-* user, and visits cascade from users.
  // By the time the visit-doc project runs, every visit the earlier projects
  // made is gone. On a long-lived QA box this is invisible — months of leftover
  // visits mean a donor is always lying around — which is exactly why it took
  // an ephemeral runner to expose it.
  //
  // So: leave one behind, owned by the SYNTHETIC ACTOR rather than a qa-e2e-*
  // user, so the cleanup that removes the others cannot cascade this one away.
  // Written through Prisma, so required columns are enforced by the schema
  // instead of by hand — the drift the clone-don't-enumerate rule guards
  // against does not apply here.
  const existingDonor = await prisma.transcribeVisit.findFirst({
    where: { id: DONOR_VISIT_ID },
    select: { id: true },
  });
  if (!existingDonor) {
    let patient = await prisma.transcribeMdPatient.findFirst({
      where: { practiceId: user.practiceId, deletedAt: null },
      select: { id: true },
    });
    patient ??= await prisma.transcribeMdPatient.create({
      data: { practiceId: user.practiceId, name: 'Twin Donor (synthetic fixture)' },
      select: { id: true },
    });
    await prisma.transcribeVisit.create({
      data: {
        id: DONOR_VISIT_ID,
        userId: user.id,
        patientId: patient.id,
        // T4 — the author.
        createdBy: user.id,
        // T3 — from the PATIENT, per the stated derivation. The patient row
        // was created (or found) under `user.practiceId` a few lines up, so this
        // is the same value by construction; the patient's `select` does not
        // expose the column, and widening it just to read back what we already
        // hold would be noise. The composite FK refuses a mismatch either way.
        practiceId: user.practiceId,
        specialty: 'ultrasound',
        inputMode: 'text',
        status: 'READY',
        // THE CLONE INHERITS THESE, and three specs depend on it.
        //
        // seedVisitDocVisit overrides the note and the claims but carries the
        // donor's clinical payload through, on purpose: the STYLED twin it
        // derives explicitly NULLs rxDrafts/icdCodes/cptCodes to prove an
        // imaging report has no prescription or billing chrome, which only
        // means something if the OTHER fixture has them. Its own comment says
        // so — "the twin visit keeps its meds and its warning, so the gate is
        // still covered by a fixture that has one".
        //
        // An empty donor silently removes that coverage: the Rx gate simply
        // does not render, and `review-doc-rx-gate` is missing rather than
        // wrong. On the QA box the donor was a real visit that happened to
        // carry meds, so this too was invisible until an ephemeral runner had
        // nothing else to clone.
        //
        // Synthetic throughout — invented drugs/doses on a fixture patient.
        rxDrafts: {
          prescriptions: [
            {
              drug: 'Warfarin',
              strength: '5 mg',
              form: 'tablet',
              sig: 'Take 1 tablet by mouth once daily',
              quantity: '30',
              refills: '0',
              action: 'new',
              evidence_quote: '[SYNTHETIC] start warfarin for new atrial fibrillation',
            },
            {
              drug: 'Amoxicillin',
              strength: '500 mg',
              form: 'capsule',
              sig: 'Take 1 capsule by mouth three times daily',
              quantity: '21',
              refills: '0',
              action: 'new',
              evidence_quote: '[SYNTHETIC] treat acute bacterial sinusitis',
            },
          ],
          // DELIBERATELY NOT 'critical'. The Rx rail renders whenever there are
          // prescriptions (severity only changes its styling), but a CRITICAL
          // warning additionally blocks signing with OVERRIDE_REQUIRED — and
          // that fires BEFORE the E/M-stale gate, so the two E/M specs that
          // sign expecting 422 "confirm the new level" got 409 from a different
          // gate instead. A fixture that trips an unrelated guard does not make
          // the suite stricter, it makes it blind to the guard under test.
          //
          // The critical-override path has its own coverage: scenario 24 in the
          // rx-safety project, whose MOCK_RX_WARNINGS fixture supplies one.
          warnings: [
            {
              severity: 'major',
              rx_drug: 'Warfarin',
              message:
                '[SYNTHETIC] Major: warfarin with a new antibiotic can raise INR — plan close monitoring.',
              evidence_quote: '[SYNTHETIC] both newly started this visit',
            },
            {
              severity: 'minor',
              rx_drug: 'Amoxicillin',
              message: '[SYNTHETIC] Minor: advise taking amoxicillin with food to reduce GI upset.',
              evidence_quote: null,
            },
          ],
        },
        icdCodes: {
          codes: [
            {
              code: 'I87.2',
              confidence: 0.9,
              description: 'Venous insufficiency (chronic) (peripheral)',
              evidence_quote: '[SYNTHETIC] chronic venous insufficiency',
            },
          ],
        },
        // NO cptCodes.em — AND THIS IS THE POINT, not an omission.
        //
        // This donor used to carry an office E/M blob (99213) so the STYLED
        // twin derived from it could NULL the billing payload and prove an
        // imaging report has no billing chrome. But the donor is itself
        // `specialty: 'ultrasound'`, and an office-visit level on an imaging
        // report is wrong as DATA: it reaches the export and the signed record,
        // and it is exactly the state the specialtyLabel-vs-specialtyId fix
        // exists to prevent. A fixture that models the bug teaches every walk
        // and spec reading it that the bug is normal.
        //
        // The derived fixture's proof is intact: `rxDrafts` (2 prescriptions,
        // 2 warnings) and `icdCodes` are still here, so NULLing them downstream
        // still means something. E/M-present coverage belongs on a
        // primary-care fixture, and lives on the review-doc pack's office-visit
        // class — see REVIEW_DOC_CLASSES in tests/e2e/helpers/seedReviewDocVisit.ts.
      },
    });
    say(
      `DONOR visit ${DONOR_VISIT_ID} created (meds + a non-critical warning + ICD; ` +
        'NO office E/M — it is an imaging visit; survives qa-e2e-* cleanup)',
    );
  } else {
    say(`DONOR visit ${DONOR_VISIT_ID} already present`);
  }

  // FAIL THE SEED ON AN IMAGING VISIT THAT CARRIES A BILLING LEVEL.
  //
  // Both artifacts this catches were acquired AFTER seeding, by a page render
  // from a build that predated the specialtyLabel-vs-specialtyId fix. So the
  // check is a read of the whole imaging population, not a review of what this
  // script just wrote: the seeder was never the one lying.
  //
  // Loud on purpose. Left silent, a wrong fixture is read as truth by every
  // walk and spec that touches it, and the thing they then prove is the bug.
  //
  // `emPendingChange` is a Json column, so its `not` takes a JSON-null token
  // rather than a bare `null` — the shared client was `any`, so this argument
  // was never checked. MEASURED ON QA before changing it: bare `null` and
  // `Prisma.JsonNull` compile to the SAME sql (`"emPendingChange"::jsonb <>
  // 'null'`); `Prisma.DbNull` compiles to `IS NOT NULL` instead. `JsonNull` is
  // therefore the behaviour-preserving token and is what is written here.
  //
  // The two only diverge on a row holding the JSON null LITERAL, which is not
  // a state this system can reach: every clear-path writer
  // (`em-score/override/route.ts:270`, `actions/rescore-em.ts:198`) sets
  // `Prisma.DbNull`, i.e. sql NULL, and QA holds zero such rows. And on the
  // question this guard asks — does an imaging visit carry an E/M delta — a
  // literal `null` carries none, so excluding it is right either way.
  const emArtifacts = await prisma.transcribeVisit.findMany({
    where: {
      specialty: 'ultrasound',
      OR: [
        // String? column — a bare `null` is the correct filter here.
        { emScoredCode: { not: null } },
        { emPendingChange: { not: Prisma.JsonNull } },
      ],
    },
    select: { id: true, emScoredCode: true },
  });
  const withEmBlob = (
    await prisma.transcribeVisit.findMany({
      where: { specialty: 'ultrasound' },
      select: { id: true, cptCodes: true },
    })
  ).filter(
    (v: { id: string; cptCodes: unknown }) =>
      typeof v.cptCodes === 'object' &&
      v.cptCodes !== null &&
      !Array.isArray(v.cptCodes) &&
      'em' in (v.cptCodes as Record<string, unknown>),
  );

  if (emArtifacts.length || withEmBlob.length) {
    const named = [
      ...emArtifacts.map(
        (v: { id: string; emScoredCode: string | null }) =>
          `${v.id} (emScoredCode=${v.emScoredCode ?? 'set'})`,
      ),
      ...withEmBlob.map((v: { id: string }) => `${v.id} (cptCodes.em present)`),
    ];
    throw new Error(
      'IMAGING VISITS CARRY OFFICE E/M STATE:\n  ' +
        named.join('\n  ') +
        '\nAn office-visit level on an imaging report is wrong as data — it reaches ' +
        'the export and the signed record. Purge it (set emScoredCode = null, ' +
        "cptCodes = cptCodes - 'em') before using this stack as a fixture.",
    );
  }
  say(`imaging E/M guard: clean (${await countImagingVisits()} imaging visits checked)`);

  say('done — this stack now has a genuine CERTIFIED twin');
}

async function countImagingVisits(): Promise<number> {
  return prisma.transcribeVisit.count({ where: { specialty: 'ultrasound' } });
}

// EXIT EXPLICITLY. Disconnecting Prisma is not enough to end the process: the
// object-store client keeps a keep-alive HTTP agent open, so the event loop
// still has a live handle and node never returns. The work finishes in about
// nine seconds and then the process sits there forever — which in CI is not a
// hung script, it is a hung STEP that starves every project after it and then
// reports as a job timeout naming nothing.
//
// It is a nasty failure to read, because the log looks completely successful:
// the last line is "done — this stack now has a genuine CERTIFIED twin". The
// tell is the absence of an exit, not the presence of an error.
main()
  .then(async () => {
    await prisma.$disconnect();
    process.exit(0);
  })
  .catch(async (err) => {
    console.error(`[twin-seed] FAILED: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}`);
    await prisma.$disconnect();
    process.exit(1);
  });
