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

import { prisma } from '@meddoc/db';

const say = (s: string) => console.log(`[twin-seed] ${s}`);
const sha256 = (b: Uint8Array | string) =>
  createHash('sha256')
    .update(typeof b === 'string' ? Buffer.from(b, 'utf8') : Buffer.from(b))
    .digest('hex');

/** The committed pin, and the form it was minted against. */
const FIXTURES = join(__dirname, '..', 'tests', 'e2e', 'fixtures');
const PINS_PATH = join(FIXTURES, 'twin-certified-pins.json');
const DOCX_PATH = join(FIXTURES, 'sample-form.docx');

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
    encounterText: pins.encounterText,
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
  say('done — this stack now has a genuine CERTIFIED twin');
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
