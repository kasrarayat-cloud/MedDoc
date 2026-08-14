// ============================================================================
// RC-1 — THE ASSEMBLED NOTE, WALKED ON THE LIVE QA STACK.
// Ruling #106(a)/(f)/(g), SPEC §4.3a.
// ----------------------------------------------------------------------------
// A unit test proves the modules. This points the REAL layers at the REAL QA
// database and reads back what a doctor would be shown: a template loaded from
// `note_templates`, a transcript, and the persisted note.
//
//     stored template → slot values → assembly → document, past the polisher.
//
// ⚠️ IT RUNS THE WORKING TREE, NOT THE QA IMAGE, AND SAYS SO. AGENTS.md's
// standing warning is that a green `--qa` migrations check says nothing about
// the QA IMAGES, which rot behind it — the B8 case found a QA worker built
// before the code it was supposed to exercise even existed. This walk sidesteps
// that class entirely by executing the source under test rather than a build of
// it. What it therefore does NOT prove is that the shipped image contains this
// code; that is the deploy's own structural check, on a build from this commit.
//
// ⚠️ FAIL-CLOSED ON THE DATABASE NAME. It WRITES — a visit's soapDraft and
// soapFinal — so pointing it at production would be editing clinical rows to
// prove a change works, which is the one thing the standing law forbids by
// name. It refuses any database whose name does not carry a qa/test marker.
//
// ⚠️ THE FIXTURE IS SANITIZED, PER SPEC §4.3a(e): the structural twin of the
// real customer form, no real clinic / physician / technologist names, with
// `500 milliseconds` as the permitted verbatim tripwire.
//
// Usage: run inside a node container on the QA network, repo bind-mounted.
// Exit:  0 = every arm passed · 1 = FINDING · 2 = cannot tell
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import prisma from '@meddoc/db';
import { runLayer4GenerateSoap } from '../../apps/transcribe-md/src/worker/layers/04-generate-soap';
import { runLayer6Polish } from '../../apps/transcribe-md/src/worker/layers/06-polish';
import { normalizeTemplate } from '../../apps/transcribe-md/src/worker/note-templates/build-soap-prompt';
import { staticDivergenceCount } from '../../apps/transcribe-md/src/worker/note-templates/static-divergence-counter';

const TPL_ID = 'qa_rc1_tpl';
const VISIT_ID = 'qa_rc1_visit';
const TRIPWIRE = '500 milliseconds';
const DOCTOR_ID = 'cmrya5nwb00000tmhmszo5pnn';
const PATIENT_ID = 'qa_pt_01';

/**
 * ⚠️ `ultrasound`, NOT `primary-care`, AND THE SPECIALTY IS THE WHOLE POINT.
 *
 * The first version of this walk used `primary-care`, which routes L4 through
 * `buildSoapSystemPrompt`. **Every production visit bound to a reclassified
 * template is an IMAGING visit** and routes through
 * `buildUltrasoundSystemPrompt` — a second builder that did not carry the
 * slot-values contract. So fifteen green arms were measured on the one path
 * production never takes, against an imaging-shaped fixture that made them read
 * as an imaging proof. The gate was flawless over a universe containing none of
 * the rows it was written for.
 */
const SPECIALTY = 'ultrasound';

/** The fixture, in its PRE-migration shape. SANITIZED per SPEC §4.3a(e): the
 *  structural twin of the real customer form — a fixed protocol paragraph
 *  carrying one dropdown, a `LABEL: <slot>` field block, a per-leg scaffold the
 *  model extends — with no real clinic, physician or technologist names. */
const SECTIONS = [
  {
    key: 'exam_metadata',
    label: 'EXAM',
    order: 1,
    formatHint: 'prose',
    styleInstructions: 'Field block.',
    defaultText: 'SIDE OF EXAM: {{one of: right | left}}\nMACHINE: [not documented]',
    defaultTextMode: 'scaffold_confirm',
    structure: null,
  },
  {
    key: 'technique',
    label: 'TECHNIQUE',
    order: 2,
    formatHint: 'prose',
    styleInstructions: 'Protocol paragraph.',
    defaultText:
      'A duplex Doppler color flow ultrasound study was performed in the upright position, documenting the condition of the {{one of: deep and superficial | superficial}} venous systems of the extremity. This study documents reflux as lasting more than 500 milliseconds in either the saphenous veins or the perforator veins.',
    defaultTextMode: 'scaffold_confirm',
    structure: null,
  },
  {
    key: 'findings',
    label: 'FINDINGS',
    order: 3,
    formatHint: 'prose',
    styleInstructions: 'Per leg.',
    defaultText: 'Right Leg:\nThe {{one of: great saphenous vein | small saphenous vein}} was assessed.',
    defaultTextMode: 'scaffold_confirm',
    structure: null,
  },
  {
    key: 'impression',
    label: 'IMPRESSION',
    order: 4,
    formatHint: 'numbered',
    styleInstructions: 'Numbered.',
    defaultText: null,
    defaultTextMode: 'omit_unless_supported',
    structure: null,
  },
];

/**
 * The transcript.
 *
 * ⚠️ IT DELIBERATELY NAMES NO SIDE. It supports the TECHNIQUE slot
 * ("superficial") and supports NEITHER option of the EXAM field block's
 * `SIDE OF EXAM` menu — so one ASSEMBLED section fills and another fails
 * closed in the SAME run, and the output tells them apart.
 *
 * ⚠️ The first version of this walk said "the left leg" and then asserted a
 * visible hole. Every assembled slot filled, `unfilled` was 0, and the
 * assertion was measuring the FINDINGS section — which is `scaffold_confirm`
 * and therefore not assembled at all. A check whose subject is a section the
 * mechanism does not touch is a check about nothing; it went red, correctly,
 * and the fix was the transcript rather than the assertion.
 */
const TRANSCRIPT =
  'Doctor #0: Today we studied the superficial venous system of the extremity.\n' +
  'Patient #1: Understood, thank you.';

const results: { arm: string; ok: boolean; detail: string }[] = [];
function check(arm: string, ok: boolean, detail: string): void {
  results.push({ arm, ok, detail });
  console.log(`${ok ? '  🟢' : '  🔴'} ${arm} — ${detail}`);
}

async function soap(): Promise<{ draft: string; final: string | null }> {
  const v = await prisma.transcribeVisit.findUniqueOrThrow({
    where: { id: VISIT_ID },
    select: { soapDraft: true, soapFinal: true },
  });
  return { draft: v.soapDraft ?? '', final: v.soapFinal };
}

async function runL4(): Promise<string> {
  const row = await prisma.noteTemplate.findUniqueOrThrow({ where: { id: TPL_ID } });
  const visit = await prisma.transcribeVisit.findUniqueOrThrow({ where: { id: VISIT_ID } });
  return runLayer4GenerateSoap({
    visitId: VISIT_ID,
    practiceId: visit.practiceId,
    userId: visit.userId,
    specialty: visit.specialty,
    roleLabeledTranscript: TRANSCRIPT,
    entities: {} as never,
    audioConfidenceStats: null,
    interpreterMode: false,
    noteTemplate: normalizeTemplate(row as never),
  });
}

async function runL6(): Promise<{ polishRejected: boolean; soapFinal: string; reviewReason: string | null }> {
  const row = await prisma.noteTemplate.findUniqueOrThrow({ where: { id: TPL_ID } });
  const visit = await prisma.transcribeVisit.findUniqueOrThrow({ where: { id: VISIT_ID } });
  const out = await runLayer6Polish({
    visitId: VISIT_ID,
    practiceId: visit.practiceId,
    userId: visit.userId,
    soapDraft: visit.soapDraft ?? '',
    // ONE fixable, rewording-class issue — enough to make L6 actually call its
    // model. With no fixable issue L6 takes its passthrough branch, the
    // polisher never runs, and "the statics survived the polisher" would be a
    // claim about a step that did not happen.
    critique: {
      issues: [
        {
          severity: 'minor',
          location: 'IMPRESSION',
          description: 'Wording is clumsy.',
          suggested_fix: 'Reword the impression line more clearly.',
        },
      ],
      overall_quality: 'medium',
      safe_to_sign_without_review: true,
    },
    noteTemplate: normalizeTemplate(row as never),
  });
  return { polishRejected: out.polishRejected, soapFinal: out.soapFinal, reviewReason: out.reviewReason };
}

const MIGRATION = path.join(
  process.cwd(),
  '../../packages/db/prisma/migrations/20260813231500_rc1_reclassify_fixed_blocks/migration.sql'
);

/**
 * Seed the fixture in its PRE-migration shape, then run the real migration.
 *
 * ⚠️ THE WALK USED TO ASSERT A HAND-SEEDED ROW. ARM 0 is titled "the migration
 * moved the fixed blocks" and its whole measurement was reading modes that were
 * already in the database — so it could not distinguish "the migration flipped
 * it" from "somebody seeded it flipped", and the 15-of-15 verdict could not be
 * re-earned from the repository. The report even claimed the script re-created
 * these rows; it did not. Now it does, and the migration is applied HERE, from
 * the file, so ARM 0 measures an act rather than a state.
 *
 * The migration is one `DO` block — one statement — which is what makes it
 * runnable through `$executeRawUnsafe` at all.
 */
async function seedPreMigration(): Promise<void> {
  await prisma.$executeRawUnsafe(`DELETE FROM transcribe_visits WHERE id = '${VISIT_ID}'`);
  await prisma.$executeRawUnsafe(`DELETE FROM note_templates WHERE id = '${TPL_ID}'`);
  await prisma.$executeRawUnsafe(`
    INSERT INTO note_templates (id, "doctorId", name, "encounterType", sections, "styleProfile", version, status, "isSystemDefault", "createdAt", "updatedAt", "practiceId")
    VALUES ('${TPL_ID}', '${DOCTOR_ID}', 'RC-1 walk — sanitized venous duplex', 'ultrasound',
      $$${JSON.stringify(SECTIONS)}$$::jsonb,
      '{"tense":"past","tone":"clinical","abbreviations":"expand"}'::jsonb,
      1, 'active', false, now(), now(),
      (SELECT "practiceId" FROM users WHERE id = '${DOCTOR_ID}'))`);
  await prisma.$executeRawUnsafe(`
    INSERT INTO transcribe_visits (id, "userId", specialty, "inputMode", status, "createdAt", "updatedAt", "needsReview", "patientId", "manualRetryCount", "soapVersion", "interpreterMode", "emStale", "practiceId", "createdBy", "noteTemplateId")
    VALUES ('${VISIT_ID}', '${DOCTOR_ID}', '${SPECIALTY}', 'text_note', 'DRAFTING', now(), now(), false,
      '${PATIENT_ID}', 0, 1, false, false,
      (SELECT "practiceId" FROM transcribe_md_patients WHERE id = '${PATIENT_ID}'),
      '${DOCTOR_ID}', '${TPL_ID}')`);
}

async function main(): Promise<number> {
  const url = process.env.DATABASE_URL ?? '';
  const dbName = (() => {
    try {
      return decodeURIComponent(new URL(url).pathname.replace(/^\//, ''));
    } catch {
      return '';
    }
  })();
  if (!/qa|test/i.test(dbName)) {
    console.error(`REFUSED: database "${dbName || '(unparseable)'}" carries no qa/test marker. This walk WRITES.`);
    return 2;
  }
  console.log(`RC-1 QA walk — database=${dbName}\n`);

  // ── ARM 0 — SEED PRE-MIGRATION, RUN THE MIGRATION, MEASURE THE MOVE ──────
  await seedPreMigration();
  const readModes = async () => {
    const row = await prisma.noteTemplate.findUniqueOrThrow({ where: { id: TPL_ID } });
    const secs = row.sections as { key: string; defaultTextMode: string }[];
    return Object.fromEntries(secs.map((x) => [x.key, x.defaultTextMode])) as Record<string, string>;
  };
  const before = await readModes();
  check(
    'ARM 0a · PRE-CONDITION — the fixture starts where a real upload leaves it',
    before.technique === 'scaffold_confirm' &&
      before.exam_metadata === 'scaffold_confirm' &&
      before.findings === 'scaffold_confirm',
    `technique=${before.technique} exam_metadata=${before.exam_metadata} findings=${before.findings}`
  );
  await prisma.$executeRawUnsafe(readFileSync(MIGRATION, 'utf8'));
  const modes = await readModes();
  check(
    'ARM 0b · the MIGRATION moved the fixed blocks and left the scaffold alone',
    modes.technique === 'always_include' &&
      modes.exam_metadata === 'always_include' &&
      modes.findings === 'scaffold_confirm',
    `technique=${modes.technique} exam_metadata=${modes.exam_metadata} findings=${modes.findings}`
  );

  // ── ARM 1 — L4: transcript → slot values → assembly ──────────────────────
  await runL4();
  const a1 = await soap();
  check('ARM 1 · the tripwire is in the draft, VERBATIM', a1.draft.includes(TRIPWIRE), TRIPWIRE);
  check(
    'ARM 1 · the transcript-supported option was filled',
    a1.draft.includes('condition of the superficial venous systems'),
    'slot s0 → "superficial"'
  );
  check(
    'ARM 1 · the paraphrase is nowhere in the note',
    !a1.draft.includes('0.5 seconds'),
    'no "0.5 seconds"'
  );
  check(
    'ARM 1 · the protocol block never reaches the note',
    !a1.draft.includes('<<<SLOT_VALUES') && !a1.draft.includes('"s0"'),
    'no wire format in clinical text'
  );
  check(
    'ARM 1 · an UNSUPPORTED slot in an ASSEMBLED section fails closed, visibly',
    a1.draft.includes('SIDE OF EXAM: —'),
    'SIDE OF EXAM → "—" (the transcript names no side)'
  );

  // ── ARM 2 — L6 GREEN: the statics survive the polisher ───────────────────
  delete process.env.MOCK_POLISH_PARAPHRASE;
  const g = await runL6();
  const a2 = await soap();
  check(
    'ARM 2 · polish RAN and was accepted',
    !g.polishRejected,
    `polishRejected=${g.polishRejected}`
  );
  check(
    'ARM 2 · ⚠️ THE TRIPWIRE IS IN soapFinal — END TO END, PAST THE POLISHER',
    (a2.final ?? '').includes(TRIPWIRE),
    TRIPWIRE
  );

  // ── ARM 3 — L6 RED: the polisher normalises, and the arm refuses ─────────
  process.env.MOCK_POLISH_PARAPHRASE = 'true';
  const counterBefore = staticDivergenceCount(TPL_ID);
  const r = await runL6();
  const a3 = await soap();
  check('ARM 3 · the polish is REJECTED', r.polishRejected, `polishRejected=${r.polishRejected}`);
  check(
    'ARM 3 · soapFinal fell back to the draft and still carries the tripwire',
    (a3.final ?? '').includes(TRIPWIRE) && !(a3.final ?? '').includes('0.5 seconds'),
    'draft served'
  );
  check(
    'ARM 3 · the banner NAMES the section',
    (r.reviewReason ?? '').includes('TECHNIQUE') && (r.reviewReason ?? '').includes('your own form'),
    'doctor-facing reason'
  );
  check(
    'ARM 3 · the per-template counter moved',
    staticDivergenceCount(TPL_ID) === counterBefore + 1,
    `${counterBefore} → ${staticDivergenceCount(TPL_ID)}`
  );
  // ⚠️ READ THE ROW BACK. logAudit is fire-and-forget by design, so asserting
  // the call asserts the call. Poll: the write is detached.
  let audit: { metadata: unknown } | null = null;
  for (let i = 0; i < 20 && audit === null; i++) {
    await new Promise((res) => setTimeout(res, 250));
    audit = (await prisma.$queryRawUnsafe<{ metadata: unknown }[]>(
      `SELECT metadata FROM audit_logs WHERE "targetId" = $1 AND action::text = 'L6_FABRICATION_REJECTED'
         AND metadata->>'gateError' = 'static_region_diverged' ORDER BY "timestamp" DESC LIMIT 1`,
      VISIT_ID
    ))[0] ?? null;
  }
  const md = (audit?.metadata ?? {}) as Record<string, unknown>;
  check(
    'ARM 3 · the audit ROW exists, with its named reason and template',
    audit !== null && md.noteTemplateId === TPL_ID && Array.isArray(md.divergedSections),
    audit === null ? 'NO ROW' : `sections=${JSON.stringify(md.divergedSections)} template=${String(md.noteTemplateId)}`
  );
  delete process.env.MOCK_POLISH_PARAPHRASE;

  // ── ARM 4 — an OUT-OF-MENU value is refused ON THE WIRE ──────────────────
  process.env.MOCK_SLOT_OUT_OF_MENU = 'true';
  await runL4();
  const a4 = await soap();
  check(
    'ARM 4 · the invented value never reaches the note',
    !a4.draft.includes('not on this menu'),
    'refused structurally'
  );
  check(
    'ARM 4 · the refused slot renders the visible marker, prose intact',
    a4.draft.includes('condition of the — venous systems') && a4.draft.includes(TRIPWIRE),
    'hole is visible; the paragraph is not'
  );
  delete process.env.MOCK_SLOT_OUT_OF_MENU;

  const failed = results.filter((r2) => !r2.ok);
  console.log(`\n${failed.length === 0 ? '🟢' : '🔴'} ${results.length - failed.length} of ${results.length} checks passed`);
  return failed.length === 0 ? 0 : 1;
}

main()
  .then(async (code) => {
    await prisma.$disconnect();
    process.exit(code);
  })
  .catch(async (err) => {
    console.error('CANNOT TELL —', err instanceof Error ? err.message : String(err));
    await prisma.$disconnect();
    process.exit(2);
  });
