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

import prisma from '@meddoc/db';
import { runLayer4GenerateSoap } from '../../apps/transcribe-md/src/worker/layers/04-generate-soap';
import { runLayer6Polish } from '../../apps/transcribe-md/src/worker/layers/06-polish';
import { normalizeTemplate } from '../../apps/transcribe-md/src/worker/note-templates/build-soap-prompt';
import { staticDivergenceCount } from '../../apps/transcribe-md/src/worker/note-templates/static-divergence-counter';

const TPL_ID = 'qa_rc1_tpl';
const VISIT_ID = 'qa_rc1_visit';
const TRIPWIRE = '500 milliseconds';

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

  // ── ARM 0 — the stored template is in the ASSEMBLED shape ────────────────
  const row = await prisma.noteTemplate.findUniqueOrThrow({ where: { id: TPL_ID } });
  const sections = row.sections as { key: string; defaultTextMode: string }[];
  const modes = Object.fromEntries(sections.map((s) => [s.key, s.defaultTextMode]));
  check(
    'ARM 0 · the migration moved the fixed blocks and left the scaffold alone',
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
  const before = staticDivergenceCount(TPL_ID);
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
    staticDivergenceCount(TPL_ID) === before + 1,
    `${before} → ${staticDivergenceCount(TPL_ID)}`
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
