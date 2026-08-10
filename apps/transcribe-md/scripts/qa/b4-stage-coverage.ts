/* eslint-disable no-console */
// ============================================================================
// B4's CLOSING GATE — THE RUN. One full mocked pipeline per input mode, counted
// against the enumerated stage list.
// ----------------------------------------------------------------------------
// B4's gate, verbatim: *"one full QA pipeline run produces one event per stage,
// counted against the enumerated stage list, not eyeballed. The audio path must
// be exercised on QA — it is unexercised in production (all 26 visits are
// `text_notes`), so production cannot be the proof."*
//
// The list half runs in CI (`src/lib/billing/__tests__/gate-b4-stage-
// enumeration.test.ts`). This is the run half. It needs a worker, a queue, a
// bucket and a database, so it lives on the isolated `meddoc-qa` stack.
//
//   docker compose -f docker-compose.qa.yml run --rm \
//     -e DATABASE_URL=postgresql://meddoc:qa_test_pw@postgres:5432/meddoc_qa_test?schema=public \
//     -e REDIS_URL=redis://redis:6379 \
//     -e MINIO_ENDPOINT=minio:9000 -e MINIO_ACCESS_KEY=qa_minio \
//     -e MINIO_SECRET_KEY=qa_minio_pw -e MINIO_USE_SSL=false \
//     -e TRANSCRIBE_MD_MINIO_BUCKET=transcribe-md-audio \
//     --entrypoint sh db-migrate \
//     -c 'cd /app/apps/transcribe-md && npx tsx scripts/qa/b4-stage-coverage.ts'
//
// ⚠️ FAIL-CLOSED ON THE DATABASE. `assertNonProdDatabase()` first, before any
// write. This script CREATES VISITS; pointed at production it would be a
// clinical mutation. The guard proceeds only for a positively-marked qa/test
// database, and there is deliberately no force flag.
//
// ⚠️ AND IT SCOPES ITS COUNTS TO THE VISITS IT CREATED. QA's
// `api_usage_events` holds 977 rows, every one `unitsSource='vendor'`, the
// newest dated 2026-07-28 — the day of the 298-real-calls incident. They are
// entirely PRE-REGIME: no mocked run has ever metered on this stack, because
// the mock boundary only moved below the meter on 2026-08-08. A gate that
// measured the existing population would report `mock = 0` for every stage and
// read as *"the meters are all broken"*.
// ============================================================================

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { prisma } from '@meddoc/db';
import { assertNonProdDatabase } from '@meddoc/db/guard';

import {
  COUPLED_STAGES,
  PIPELINE_STAGES,
  PIPELINE_INPUT_MODES,
  canonicalOperation,
  isEnumeratedOperation,
  stagesForMode,
  violation,
  type PipelineInputMode,
} from '../../src/lib/billing/pipeline-stages';
import { captureEditPattern } from '../../src/lib/edit-tracking';
import { putAudioStream } from '../../src/lib/minio';
import { enqueueProcessVisit, getTranscribeMdQueue } from '../../src/lib/queue';

const TAG = '[b4-coverage]';

/** A 1,044-byte committed silence fixture. Under `MOCK_AI_CALLS` the bytes are
 *  never transcribed — the fixture supplies the RESPONSE — but L1 still stats
 *  and streams the object, so a real object of non-zero size has to exist. */
const AUDIO_FIXTURE = resolve(
  __dirname,
  '../../tests/e2e/fixtures/audio/silence-3sec.mp3'
);

const PATIENT_NAME = 'B4 Coverage Patient';
const SPECIALTY = 'primary-care';
const SCRIPT_TEXT = [
  'Patient is a 54 year old with a two week history of dry cough and intermittent',
  'wheeze, worse at night. No fever, no haemoptysis, no chest pain. Past history of',
  'seasonal allergic rhinitis. Currently on loratadine ten milligrams daily. On',
  'examination the chest is clear with scattered expiratory wheeze bilaterally.',
  'Oxygen saturation is ninety eight percent on room air. Plan is to start an',
  'inhaled corticosteroid, review in four weeks, and arrange spirometry.',
].join(' ');

const TERMINAL = new Set(['READY', 'SIGNED', 'FAILED']);
const POLL_MS = 10_000;
const DEADLINE_MS = 30 * 60 * 1000;

interface Created {
  mode: PipelineInputMode;
  visitId: string;
}

// ---------------------------------------------------------------------------

async function pickActor(): Promise<{ userId: string; practiceId: string }> {
  const explicitUser = process.env.B4_USER_ID;
  if (explicitUser) {
    const u = await prisma.user.findUnique({
      where: { id: explicitUser },
      select: { id: true, practiceId: true },
    });
    if (!u?.practiceId) throw new Error(`${TAG} B4_USER_ID=${explicitUser} has no practice`);
    return { userId: u.id, practiceId: u.practiceId };
  }
  // Otherwise the oldest user — on the QA fixture stack that is the seeded
  // clinic, which already owns patients. No null filter: T6 made
  // `User.practiceId` REQUIRED (schema.prisma:713), so every user has one and
  // a `{ not: null }` filter does not even type-check.
  const u = await prisma.user.findFirst({
    orderBy: { createdAt: 'asc' },
    select: { id: true, practiceId: true },
  });
  if (!u) throw new Error(`${TAG} no user on this database`);
  return { userId: u.id, practiceId: u.practiceId };
}

async function findOrCreatePatient(practiceId: string): Promise<string> {
  const existing = await prisma.transcribeMdPatient.findFirst({
    where: { practiceId, name: PATIENT_NAME, deletedAt: null },
    select: { id: true },
  });
  if (existing) return existing.id;
  const created = await prisma.transcribeMdPatient.create({
    data: { practiceId, name: PATIENT_NAME },
    select: { id: true },
  });
  return created.id;
}

async function createVisit(
  mode: PipelineInputMode,
  actor: { userId: string; practiceId: string },
  patientId: string
): Promise<string> {
  const data: any = {
    userId: actor.userId,
    // T4 — the author. `data` is typed `any`, so `tsc` cannot catch a missing
    // required column here; this line is verified by reading, as T3/T4's own
    // sweep required of every raw create.
    createdBy: actor.userId,
    // T3 — the visit's tenant. The patient is created under the same practice,
    // so the composite FK (patientId, practiceId) is satisfied by construction.
    practiceId: actor.practiceId,
    patientId,
    patientName: PATIENT_NAME,
    specialty: SPECIALTY,
    chiefComplaint: 'Cough and wheeze — B4 stage coverage',
    inputMode: mode,
    interpreterMode: false,
    status: 'QUEUED',
  };
  if (mode === 'text_notes') data.rawTextInput = SCRIPT_TEXT;

  const v = await prisma.transcribeVisit.create({ data, select: { id: true } });

  if (mode !== 'text_notes') {
    const buf = readFileSync(AUDIO_FIXTURE);
    if (buf.byteLength === 0) throw new Error(`${TAG} audio fixture is empty: ${AUDIO_FIXTURE}`);
    const key = `${actor.userId}/${v.id}/b4-${mode}.mp3`;
    await putAudioStream(key, buf, buf.byteLength, 'audio/mpeg');
    await prisma.transcribeVisit.update({
      where: { id: v.id },
      data:
        mode === 'audio_upload'
          ? {
              audioKey: key,
              audioMimeType: 'audio/mpeg',
              audioSizeBytes: buf.byteLength,
              audioUploadedAt: new Date(),
            }
          : { dictationAudioKey: key },
    });
  }
  return v.id;
}

async function pollToTerminal(ids: string[]): Promise<Map<string, string>> {
  const deadline = Date.now() + DEADLINE_MS;
  const final = new Map<string, string>();
  while (Date.now() < deadline && final.size < ids.length) {
    await new Promise((r) => setTimeout(r, POLL_MS));
    const rows = await prisma.transcribeVisit.findMany({
      where: { id: { in: ids } },
      select: { id: true, status: true, failureCategory: true },
    });
    for (const r of rows) {
      if (TERMINAL.has(r.status as string) && !final.has(r.id)) {
        final.set(r.id, r.status as string);
        console.log(
          `${TAG} ${r.id} → ${r.status}${r.failureCategory ? ` (${r.failureCategory})` : ''}`
        );
      }
    }
    if (final.size < ids.length) {
      const pending = rows
        .filter((r) => !TERMINAL.has(r.status as string))
        .map((r) => `${r.id}=${r.status}`)
        .join(' ');
      console.log(`${TAG} waiting: ${pending}`);
    }
  }
  return final;
}

/**
 * `tm_embed` is OUT OF BAND. `captureEditPattern` fires from the sign route
 * after the pipeline is done, and only for a visit that carries BOTH
 * `soapL6Original` and `signedSoap`.
 *
 * ⚠️ WHAT THIS EXERCISES, STATED PLAINLY: the metering function at its own
 * boundary, not the sign route. It writes `signedSoap` directly and calls
 * `captureEditPattern` with the same three arguments `sign/route.ts:603`
 * passes. It does NOT touch `signedAt`/`signedBy` — so no signature is
 * fabricated, and the `signed_requires_signer` constraint is never in play.
 * That the sign route calls this function is the sign route's own tests'
 * business; this proves only that the call meters.
 */
async function exerciseEmbed(visitId: string, actor: { userId: string; practiceId: string }) {
  const v = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: { soapL6Original: true, signedSoap: true },
  });
  if (!v?.soapL6Original) {
    console.log(`${TAG} embed: visit ${visitId} has no soapL6Original — skipping`);
    return false;
  }
  if (!v.signedSoap) {
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { signedSoap: `${v.soapL6Original}\n\n(reviewed)` },
    });
  }
  await captureEditPattern({
    visitId,
    doctorId: actor.userId,
    practiceId: actor.practiceId as any,
  });
  // `captureEditPattern` is fire-and-forget INTERNALLY (it awaits its own work
  // but the sign route does not await it), and `logApiUsage` is itself
  // fire-and-forget. Give the detached write a moment to land before counting.
  await new Promise((r) => setTimeout(r, 3_000));
  return true;
}

// ---------------------------------------------------------------------------

async function main() {
  assertNonProdDatabase();

  const startedAt = new Date();
  console.log(`${TAG} start ${startedAt.toISOString()}`);

  // ── THE PRE-REGIME BASELINE, stated before anything is created ───────────
  const preRegime = await prisma.$queryRaw<Array<{ unitssource: string; n: bigint }>>`
    SELECT "unitsSource" AS unitssource, count(*) AS n
      FROM api_usage_events GROUP BY 1 ORDER BY 1`;
  console.log(
    `${TAG} pre-existing api_usage_events: ` +
      preRegime.map((r) => `${r.unitssource}=${r.n}`).join(' ') || `${TAG} (empty)`
  );

  const actor = await pickActor();
  const patientId = await findOrCreatePatient(actor.practiceId);
  console.log(`${TAG} actor user=${actor.userId} practice=${actor.practiceId} patient=${patientId}`);

  const created: Created[] = [];
  for (const mode of PIPELINE_INPUT_MODES) {
    const visitId = await createVisit(mode, actor, patientId);
    await enqueueProcessVisit(visitId, actor.userId);
    created.push({ mode, visitId });
    console.log(`${TAG} enqueued ${mode} → ${visitId}`);
  }

  const ids = created.map((c) => c.visitId);
  const finalStatus = await pollToTerminal(ids);

  // ── tm_embed, on the first visit that reached READY ──────────────────────
  let embedExercised = false;
  for (const c of created) {
    if (finalStatus.get(c.visitId) === 'READY') {
      embedExercised = await exerciseEmbed(c.visitId, actor);
      if (embedExercised) {
        console.log(`${TAG} embed exercised on ${c.visitId} (${c.mode})`);
        break;
      }
    }
  }

  // ── THE COUNTS, scoped to this run's visits ──────────────────────────────
  const rows = await prisma.apiUsageEvent.findMany({
    where: { visitId: { in: ids } },
    select: { visitId: true, operation: true, unitsSource: true, requestId: true },
  });

  // POSITIVE CONTROL ON THE QUERY ITSELF. A scan that silently covers nothing
  // returns zero for every stage, and a broken gate and a broken meter produce
  // identical output.
  if (rows.length === 0) {
    console.error(
      `${TAG} ⛔ the run produced ZERO usage events for its own visits. That is ` +
        `either a total metering failure or a broken query — do not read it as ` +
        `either until the visits' statuses above are accounted for.`
    );
  }

  const byVisit = new Map<string, Map<string, number>>();
  for (const id of ids) byVisit.set(id, new Map());
  for (const r of rows) {
    const op = canonicalOperation(r.operation);
    const m = byVisit.get(r.visitId!)!;
    m.set(op, (m.get(op) ?? 0) + 1);
  }

  const findings: string[] = [];

  // 1. Every visit reached a non-FAILED terminal state.
  for (const c of created) {
    const st = finalStatus.get(c.visitId) ?? 'NOT-TERMINAL';
    if (st !== 'READY' && st !== 'SIGNED') {
      findings.push(`${c.mode} visit ${c.visitId} ended ${st} — the run did not complete`);
    }
  }

  // 2. Per mode, every enumerated stage satisfied its expectation.
  console.log(`\n${TAG} ── per-stage counts, by input mode ───────────────────`);
  for (const c of created) {
    const counts = byVisit.get(c.visitId)!;
    console.log(`\n  ${c.mode}  (${c.visitId}, ${finalStatus.get(c.visitId) ?? 'NOT-TERMINAL'})`);
    for (const stage of stagesForMode(c.mode)) {
      const n = counts.get(stage.operation) ?? 0;
      const bad = violation(stage, n);
      console.log(`    ${bad ? '✗' : '✔'} ${stage.operation.padEnd(24)} ${n}`);
      if (bad) findings.push(`${c.mode}: ${stage.operation} — ${bad}`);
    }
    // Stages the mode does NOT run must produce nothing. Asserted in both
    // directions: a table that made every stage universal would pass the
    // positive arm and be wrong.
    for (const stage of PIPELINE_STAGES) {
      if (stage.expected.kind === 'outOfBand') continue;
      if (stage.modes.includes(c.mode)) continue;
      const n = counts.get(stage.operation) ?? 0;
      if (n !== 0) {
        findings.push(
          `${c.mode}: ${stage.operation} produced ${n} events on a mode that does not run it`
        );
      } else {
        console.log(`    · ${stage.operation.padEnd(24)} 0   (not run on this mode)`);
      }
    }
  }

  // 2b. THE CROSS-STAGE COUPLING. A per-stage count cannot see this: two
  //     `{0,1}` stages could fire on DIFFERENT visits and every per-stage total
  //     would still reconcile.
  for (const c of created) {
    const counts = byVisit.get(c.visitId)!;
    for (const pair of COUPLED_STAGES) {
      const lead = counts.get(pair.leader) ?? 0;
      const follow = counts.get(pair.follower) ?? 0;
      if (lead !== follow) {
        findings.push(
          `${c.mode}: ${pair.follower}=${follow} but ${pair.leader}=${lead} on the same visit — ${pair.why}`
        );
      } else {
        console.log(
          `  ${c.mode}: coupled ${pair.leader}=${lead} ≡ ${pair.follower}=${follow}`
        );
      }
    }
  }

  // 3. Nothing outside the enumerated list appeared on this run's visits.
  const strays = [...new Set(rows.map((r) => r.operation))].filter(
    (op) => !isEnumeratedOperation(op)
  );
  for (const op of strays) {
    findings.push(`unenumerated operation '${op}' metered against this run's visits`);
  }

  // 4. Ruling 66 + 72a, on this run's own rows: a mocked row is marked mock and
  //    carries no invented correlation id.
  const notMock = rows.filter((r) => r.unitsSource !== 'mock');
  if (notMock.length > 0) {
    findings.push(
      `${notMock.length} row(s) from a MOCK_AI_CALLS run are not unitsSource='mock' — ` +
        `[${[...new Set(notMock.map((r) => r.operation))].join(', ')}]`
    );
  }
  const invented = rows.filter((r) => r.requestId !== null);
  if (invented.length > 0) {
    findings.push(`${invented.length} mocked row(s) carry a requestId — ruling 72a`);
  }

  // 5. tm_embed, counted where it actually happens.
  const embedRows = rows.filter((r) => canonicalOperation(r.operation) === 'tm_embed');
  console.log(`\n${TAG} out-of-band: tm_embed rows for this run = ${embedRows.length}`);
  if (embedExercised && embedRows.length === 0) {
    findings.push('tm_embed was exercised and metered nothing');
  }
  if (!embedExercised) {
    console.log(`${TAG} ⚠️ tm_embed NOT exercised — no visit reached READY with an L6 original`);
  }

  // 6. ⚠️ COUNTED vs MERELY PERMITTED — THE ARM THAT STOPS THIS GATE BEING A
  //    DECORATION, and the reason it exists is worth reading before trusting
  //    any green above.
  //
  //    Three stages have expectations that ADMIT ZERO, for good reasons:
  //    `tm_anchor_entailment` is `{0,3}` because a visit with no anchored claim
  //    correctly makes no call, and `tm_polish`/`tm_polish_gate` are `{0,1}`
  //    because L6 passes the draft through untouched when the critique found
  //    nothing to fix. Every one of those zeros SATISFIES its expectation.
  //
  //    So a run in which those three stages never fire is green and proves
  //    nothing about them. B4's gate says *"one event per stage"*, not *"no
  //    contradiction per stage"* — and a stage observed at zero everywhere is
  //    indistinguishable from a stage whose meter was deleted.
  //
  //    Such a stage is reported UNPROVEN and the run exits 2 (can't tell),
  //    never 0. That is the same three-code convention the repo's other checks
  //    use, and it is the difference between "we looked and it was fine" and
  //    "we never made it happen".
  const unproven: string[] = [];
  for (const stage of PIPELINE_STAGES) {
    if (stage.expected.kind === 'outOfBand') {
      if (canonicalOperation(stage.operation) === 'tm_embed' && embedRows.length === 0) {
        unproven.push(`${stage.operation} — out-of-band and not exercised by this run`);
      }
      continue;
    }
    const total = created
      .filter((c) => stage.modes.includes(c.mode))
      .reduce((n, c) => n + (byVisit.get(c.visitId)!.get(stage.operation) ?? 0), 0);
    if (total === 0) {
      unproven.push(
        `${stage.operation} — zero on every mode that runs it; its expectation ` +
          `(${stage.expected.kind}) PERMITS zero, so this run neither confirms ` +
          `nor refutes its meter`
      );
    }
  }

  console.log(`\n${TAG} ── summary ──────────────────────────────────────────`);
  console.log(`${TAG} visits: ${ids.length}   usage rows scoped to them: ${rows.length}`);
  console.log(
    `${TAG} stages enumerated: ${PIPELINE_STAGES.length}   ` +
      `COUNTED: ${PIPELINE_STAGES.length - unproven.length}   UNPROVEN: ${unproven.length}`
  );

  if (findings.length > 0) {
    console.error(`\n${TAG} 🔴 ${findings.length} FINDING(S):`);
    for (const f of findings) console.error(`   · ${f}`);
    process.exitCode = 1;
    return;
  }
  if (unproven.length > 0) {
    console.error(`\n${TAG} 🟡 ${unproven.length} STAGE(S) UNPROVEN — exit 2, not a pass:`);
    for (const u of unproven) console.error(`   · ${u}`);
    process.exitCode = 2;
    return;
  }
  console.log(
    `\n${TAG} 🟢 all ${PIPELINE_STAGES.length} enumerated stages were COUNTED — ` +
      `each observed at least once, on every mode that runs it.`
  );
}

main()
  .catch((err) => {
    console.error(`${TAG} FAILED`, err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
    // ⚠️ AND THE QUEUE, OR THIS SCRIPT NEVER EXITS. `enqueueProcessVisit` opens
    // a BullMQ Redis connection that holds the event loop open forever, so the
    // first three runs of this gate printed their whole verdict — including a
    // 🟢 — and then sat there. Three `db-migrate-run-*` containers were still
    // Up thirty-five minutes later.
    //
    // A SCRIPT THAT FINISHES BUT NEVER EXITS READS AS A HANG, and worse: its
    // exit code is the entire contract with any caller. A gate that cannot
    // return 0/1/2 cannot be run by CI, by a wrapper, or by the unattended
    // loop — which means it would have been run exactly once, by hand, by the
    // session that wrote it.
    try {
      await getTranscribeMdQueue().close();
    } catch {
      // Closing is best-effort; the explicit exit below is the real guarantee.
    }
    // The backstop. `process.exitCode` carries the verdict computed above;
    // anything still holding the loop open is not allowed to swallow it.
    process.exit(process.exitCode ?? 0);
  });
