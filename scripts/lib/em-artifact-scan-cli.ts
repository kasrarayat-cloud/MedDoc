// ============================================================================
// F12-g — the CLI half of the E/M artifact watcher. THIN BY DESIGN.
// ----------------------------------------------------------------------------
// Every decision lives in `apps/transcribe-md/src/lib/em-artifact-scan.ts`,
// which is inside the app and therefore type-checked by `tsc` and covered by
// the unit gate (`gate-f12g-em-artifact-scan.test.ts`). This file does I/O,
// universe controls, and exit codes — nothing that a test would want to assert.
//
// Reads JSON on stdin, in either of two shapes:
//   { "flags": {...}, "rows": [...] }   — what check-em-note-shape-artifacts.sh
//                                          sends, flags read from the container
//   [ ...rows... ]  + `--flags '<json>'` — a bare projection, so the extract can
//                                          be piped STRAIGHT out of psql
//
// ⚠️ THE SECOND FORM EXISTS BECAUSE THE FIRST CANNOT BE ASSEMBLED WITHOUT A
// SHELL, AND IT IS STRICTLY WEAKER: the flag universe is then whatever the
// caller TYPED, not what the container holds. The wrapper always uses the first
// form. If you use the second, read the flag from the running container in the
// same pass and say so — a typed flag is a claim about production, not a
// measurement of it.
//
// Writes a report on stdout. Writes NO FILE, ever: the payload carries
// production-derived data and a scratch file is how that class escapes.
//
// Exit codes, and they are three because there are three answers:
//   0 = clean       — no visit carries E/M state under a false verdict
//   1 = FOUND       — report, classify, DO NOT remediate from here
//   2 = CANNOT TELL — wrong universe, vacuous corpus, or a projection that
//                     failed its own control. Never collapsed into 0.
// ============================================================================

import { emAppliesToSpecialty } from '@meddoc/shared/specialties';
import {
  scanEmArtifacts,
  assertNoBodyText,
  EM_STATE_FIELDS,
  type EmScanRow,
} from '../../apps/transcribe-md/src/lib/em-artifact-scan';

const CANNOT_TELL = 2;
const FOUND = 1;

function die(msg: string): never {
  console.error(`\n🟡 CANNOT TELL — ${msg}`);
  process.exit(CANNOT_TELL);
}

function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    let buf = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (c) => (buf += c));
    process.stdin.on('end', () => resolve(buf));
    process.stdin.on('error', reject);
  });
}

async function main() {
  const raw = await readStdin();
  if (!raw.trim()) die('the extract delivered nothing on stdin');

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    die(`the extract is not JSON: ${(e as Error).message}`);
  }

  // ⚠️ THE REPORT NAMES WHERE THE FLAGS CAME FROM, RATHER THAN ASSERTING AN
  // INTENDED PROVENANCE. The first draft printed "flags read from the running
  // container" unconditionally — true of the wrapper's path and FALSE of the
  // piped one, in the line a reader would quote as evidence. A document that
  // states an intended state in the present tense gets read as a description of
  // the running system; this house has a §5.6 that was false for two months.
  let flagSource = 'the running container (via the wrapper)';

  // A bare array is the piped-from-psql form; the flags then come from argv.
  let payload: { flags?: Record<string, string>; rows?: EmScanRow[] };
  if (Array.isArray(parsed)) {
    const i = process.argv.indexOf('--flags');
    if (i === -1 || !process.argv[i + 1]) {
      die('stdin is a bare row array, so --flags \'{"NAME":"value"}\' is required');
    }
    let argvFlags: Record<string, string>;
    try {
      argvFlags = JSON.parse(process.argv[i + 1]);
    } catch (e) {
      die(`--flags is not JSON: ${(e as Error).message}`);
    }
    payload = { flags: argvFlags, rows: parsed as EmScanRow[] };
    flagSource = '--flags on the command line (TYPED, not measured)';
    console.error(
      '⚠  flags came from --flags, not from the running container. Weaker: read ' +
        'them from the container in the same pass, or use the wrapper.'
    );
  } else {
    payload = parsed as { flags?: Record<string, string>; rows?: EmScanRow[] };
  }

  // ── THE FLAG UNIVERSE, FROM THE RUNNING CONTAINER ────────────────────────
  // Assigned before any accessor is CALLED (they all read `process.env` at call
  // time, never at import time). A test that defaults a flag OFF while
  // production runs it ON is testing the rollback.
  const flags = payload.flags ?? {};
  if (Object.keys(flags).length === 0) {
    die('no flag universe was supplied — refusing to scan in a guessed configuration');
  }
  for (const [k, v] of Object.entries(flags)) process.env[k] = v;

  // ── UNIVERSE CONTROL. Both directions, so the control can discriminate. ──
  // With NEXT_PUBLIC_ULTRASOUND_SPECIALTY on (production), imaging is
  // suppressed by the specialty axis and gastroenterology is not. If either
  // reads the other way, this process is not running production's classifier
  // and every number below would be about a system nobody ships.
  const usSuppressed = emAppliesToSpecialty('ultrasound') === false;
  const giAdmitted = emAppliesToSpecialty('gastroenterology') === true;
  if (!usSuppressed || !giAdmitted) {
    die(
      `WRONG UNIVERSE — emAppliesToSpecialty('ultrasound')=${emAppliesToSpecialty('ultrasound')} ` +
        `(want false), ('gastroenterology')=${emAppliesToSpecialty('gastroenterology')} (want true). ` +
        `NEXT_PUBLIC_ULTRASOUND_SPECIALTY=${String(process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY)}`
    );
  }

  const rows = payload.rows ?? [];
  if (rows.length === 0) {
    die('the corpus is EMPTY — an empty scan and a clean scan are the same output');
  }

  // ── THE PROJECTION'S OWN CONTROL: no body text arrived. ──────────────────
  const lines = assertNoBodyText(rows);
  if (lines.deliveredLines !== lines.headingLines) {
    die(
      `the extract delivered ${lines.deliveredLines} non-blank lines but only ` +
        `${lines.headingLines} survive NOTE_SECTION_HEADING_RE — the filter ` +
        `OVER-SELECTED, so the projection carries text that is not a heading`
    );
  }

  const r = scanEmArtifacts(rows);

  console.log(`E/M artifact scan — ${r.control.rows} production visits`);
  console.log(`   · universe: ultrasound suppressed ✔ · gastroenterology admitted ✔`);
  console.log(
    `   · flag universe, from ${flagSource}: ` +
      Object.entries(flags)
        .map(([k, v]) => `${k}=${v}`)
        .join(' · ')
  );
  console.log(
    `   · projection control: ${lines.deliveredLines} lines delivered = ` +
      `${lines.headingLines} headings — no body text`
  );
  console.log(
    `   · shape: cptCodes ${JSON.stringify(r.control.cptCodesTypes)} · ` +
      `sections ${JSON.stringify(r.control.templateSectionsTypes)}`
  );
  console.log(
    `   · non-vacuity: ${r.control.specialtyEligible} specialty-eligible · ` +
      `${r.control.rowsWithHeadings} with headings · ` +
      `${r.control.rowsWithTemplateLabels} with template labels`
  );
  console.log(`   · watched fields: ${EM_STATE_FIELDS.join(', ')}`);
  console.log('');
  console.log('   THE PARTITION — every row lands in exactly one bucket:');
  console.log(`     verdict FALSE + carries E/M state   ${r.buckets.verdictFalseWithState}   <- F12-g`);
  console.log(`     verdict FALSE + clean               ${r.buckets.verdictFalseClean}`);
  console.log(`     verdict TRUE  + carries E/M state   ${r.buckets.verdictTrueWithState}`);
  console.log(`     verdict TRUE  + clean               ${r.buckets.verdictTrueClean}`);
  console.log(`                                        ---`);
  console.log(`                                        ${r.total}   == ${r.control.rows} rows`);

  // The partition is disjoint and exhaustive by construction; asserting it
  // anyway is what turns "by construction" from a claim into a measurement.
  if (r.total !== r.control.rows) {
    die(`the partition does not reconcile: ${r.total} bucketed vs ${r.control.rows} rows`);
  }

  // ⚠️ NON-VACUITY, AND IT IS NOT THE ROW COUNT. A corpus of 48 rows in which
  // NOTHING is specialty-eligible cannot produce a note-shape finding however
  // many artifacts exist — the scan would be flawless over a set that cannot
  // contain what it is looking for.
  if (r.control.specialtyEligible === 0) {
    die(
      'ZERO rows are specialty-eligible — the note-shape axis is unreachable for ' +
        'this corpus, so a zero here would say nothing about F12-g'
    );
  }

  if (r.artifacts.length === 0) {
    console.log('');
    console.log('🟢 no production visit carries office E/M state under a false verdict.');
    process.exit(0);
  }

  console.log('');
  console.log(
    `🔴 ${r.artifacts.length} VISIT(S) CARRY OFFICE E/M STATE UNDER A FALSE VERDICT` +
      ` — ${r.byAxis['note-shape']} by NOTE SHAPE, ${r.byAxis.specialty} by SPECIALTY`
  );
  console.log('');
  for (const a of r.artifacts) {
    console.log(
      `    ${a.visitId}  ${(a.specialty ?? '(null)').padEnd(20)} ` +
        `signed=${String(a.signed).padEnd(5)} axis=${a.axis.padEnd(10)} ` +
        `${a.frozenOnSigned ? 'FROZEN ' : ''}${a.fields.join(', ')}`
    );
  }
  console.log(`
    DO NOT auto-fix from here. The three classes are not one finding:
      • emScoredCode / cptCodes.em.code — a COMPUTED baseline. Stale state left
        by a verdict that flipped after it was written.
      • cptCodes.em.override.code       — a DOCTOR-SET code. A recorded clinical
        judgement; clearing it deletes what somebody chose.
      • cptCodes.em.signedCode on a signed record — FROZEN into a signed
        document. Never touch.

    axis=specialty rows are ALREADY owned by check-imaging-em-artifacts.sh.
    axis=note-shape rows are F12-g's class, and nothing else watches them.

    Remediation is a deliberate transactional act through
    scripts/run-ruled-mutation.sh with its own §2.5 declaration and an audit
    row — never a side effect of a check. The disposition is a war-room
    question; this script exists so the number stops being invisible.
`);
  process.exit(FOUND);
}

main().catch((e) => die(`the scan threw: ${(e as Error).stack ?? String(e)}`));
