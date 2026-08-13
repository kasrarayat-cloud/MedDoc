// ============================================================================
// B8 step 3c — THE BEHAVIOURAL PROOF THAT "fail-fast" IS NOW TRUE, ON QA
// ----------------------------------------------------------------------------
// RELAY carried this debt out of B8 step 3's QA proof, in these words:
//
//   "The worker logs, verbatim, `permanent failure, fail-fast (skipping BullMQ
//    retries)` — and then BullMQ retries. Observed at `attemptsMade` 0 and 1 of
//    3, five seconds apart, on the admission-refusal arm."
//
// This file is the instrument for both halves of that: it measures the retry
// count BEFORE the fix (expect 3) and AFTER it (expect 1), from BullMQ's own
// job record rather than from a log line.
//
// ============================================================================
// ⚠️ WHY A QA WALK AT ALL, WHEN THE FIX HAS A UNIT GATE
// ----------------------------------------------------------------------------
// `unrecoverable.test.ts` asserts the marker against a predicate TRANSCRIBED
// from `bullmq/dist/cjs/classes/job.js:486`. That transcription is a statement
// of what I believe bullmq does — ruling #98(b), "a stub is a statement of what
// its author believes, and it agrees with the matcher because the same person
// wrote both", applied to a copied `if`. If bullmq consults something else, or
// consults it somewhere this code path does not reach, the unit test passes and
// the retries continue.
//
// Only a real `Worker` failing a real job and a real Redis record can answer
// it. That is what this file reads.
//
// ============================================================================
// ⚠️ WHAT IS MEASURED, AND WHY IT IS `attemptsMade` AND NOT A LOG LINE
// ----------------------------------------------------------------------------
// The `failure cost` line is guarded to once-per-visit (B8 step 3 DEFECT 1), so
// counting IT can no longer distinguish one attempt from three — the guard that
// fixed one defect blinded the obvious instrument for this one. The
// `permanent failure, fail-fast` line is emitted only while `!isFinalAttempt`,
// so it reads 2 before the fix and 1 after: a real signal, but an indirect one
// that moves for two different reasons.
//
// BullMQ's own `job.attemptsMade` is the ground truth and moves 3 → 1. It is
// read from Redis after the job reaches a terminal state; `queue.ts` sets
// `removeOnFail: { count: 500 }`, so a failed job survives long enough to be
// read back.
//
// ============================================================================
// ⚠️ THE PERMANENT FAILURE USED HERE IS AN ADMISSION REFUSAL, WHICH IS
//    PRE-SPEND — AND THAT LIMIT IS STATED RATHER THAN PAPERED OVER
// ----------------------------------------------------------------------------
// `BillingAdmissionError/insufficient_balance` is `permanent` (structurally, by
// `error-categorize.ts`'s property read) and it is the cheapest permanent
// failure this stack can produce on demand. It happens BEFORE the first vendor
// call, so this walk proves the RETRY COUNT and says nothing about re-spend.
//
// A POST-spend permanent failure is not reachable on QA at all, and the reason
// is structural rather than a gap in this harness — see the RELAY row. Every
// permanent door that sits below a meter (`ModelOutputMalformedError`,
// `ZodError`, `AnthropicRefusalError`) is opened by the VENDOR's response, and
// under `MOCK_AI_CALLS` the response is a fixture that is valid by
// construction. Producing one would mean injecting a fault into the mock, and a
// fault I wrote proves what I believe rather than what the pipeline does.
//
// The fix makes the distinction moot in the direction that matters: with ONE
// attempt there is no second execution of anything, spent or unspent.
// ============================================================================

import { randomUUID } from 'node:crypto';

import { prisma } from '@meddoc/db';
import { assertNonProdDatabase } from '@meddoc/db/guard';
import { getTranscribeMdQueue, JOB_PROCESS_VISIT } from '../../src/lib/queue';

type Verdict = 0 | 1 | 2;

const RUN_TAG = `b8s3c-${randomUUID().slice(0, 8)}`;
const POLL_INTERVAL_MS = 1_000;
// Pre-fix the job needs attempt 0 → 5s backoff → attempt 1 → 10s → attempt 2.
// 120s leaves generous headroom over that ~15s floor without letting a genuine
// hang masquerade as a slow run.
const TERMINAL_TIMEOUT_MS = 120_000;
// After the visit row goes FAILED the job still has to be written back to
// Redis, and on the PRE-fix path it has two more attempts to burn. Poll the job
// record rather than sleeping a guessed constant.
const JOB_SETTLE_TIMEOUT_MS = 90_000;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const j = (v: unknown) => JSON.stringify(v);

function section(title: string): void {
  console.log(`\n── ${title} ${'─'.repeat(Math.max(0, 62 - title.length))}`);
}
function ok(msg: string): void {
  console.log(`   ✅ ${msg}`);
}
function bad(msg: string): void {
  console.log(`   ❌ ${msg}`);
}
function unknown(msg: string): void {
  console.log(`   ⚪ ${msg}`);
}

async function main(): Promise<Verdict> {
  console.log('B8 step 3c — does a PERMANENT failure still get retried?');
  console.log(`run tag: ${RUN_TAG}`);

  // ── GUARD 0 — FAIL-CLOSED. This file writes rows. ────────────────────────
  section('GUARD — the target is a qa/test database, and the stack is severed');
  let target;
  try {
    target = assertNonProdDatabase();
  } catch (err) {
    console.log('\n\u{1F534} REFUSING TO RUN — the database is not a qa/test one:');
    console.log(`   ${err instanceof Error ? err.message.split('\n')[0] : String(err)}`);
    return 1;
  }
  ok(`database=${target.database} host=${target.host} — carries a qa/test marker`);

  if (process.env.MOCK_AI_CALLS !== 'true') {
    console.log(`\n\u{1F534} REFUSING TO RUN — MOCK_AI_CALLS is ${j(process.env.MOCK_AI_CALLS)}, not "true".`);
    return 1;
  }
  ok('MOCK_AI_CALLS=true in this process — read from the live container env');

  // ⚠️ CANNOT-TELL, NOT A FAILURE. Without the flag, admission does not run, the
  // visit sails through to a normal pipeline run, and there is no permanent
  // failure to count attempts on. Reporting that as a pass would be the
  // vacuous-gate failure exactly.
  if (process.env.BILLING_ENFORCED !== 'true') {
    console.log(`\n\u{1F7E1} BILLING_ENFORCED is ${j(process.env.BILLING_ENFORCED)}, not "true" — CANNOT TELL.`);
    console.log('   Admission is inert, so no permanent failure would be produced at all.');
    console.log('   Recreate the worker with docker-compose.qa.billing.yml first.');
    return 2;
  }
  ok('BILLING_ENFORCED=true in this process — an unfunded practice will be refused');

  const queue = getTranscribeMdQueue();

  // ── FIXTURE — a practice of its own, funded by nothing ───────────────────
  section('FIXTURE — an UNFUNDED practice, so admission refuses permanently');
  const practice = await prisma.practice.create({
    data: { name: `B8 3c proof (${RUN_TAG})`, slug: `b8-3c-${RUN_TAG}` },
    select: { id: true, slug: true },
  });
  ok(`practice ${practice.id} (${practice.slug})`);

  const user = await prisma.user.create({
    data: {
      email: `${RUN_TAG}@b8-3c-proof.invalid`,
      passwordHash: 'not-a-credential-this-account-cannot-log-in',
      // Two different role columns; only `practiceRole` satisfies T6's
      // `users_active_member_has_practice_role`. See b8-admission-on-qa.ts.
      role: 'DOCTOR',
      practiceRole: 'OWNER',
      isActive: true,
      practiceId: practice.id,
    },
    select: { id: true },
  });
  ok(`user ${user.id}`);

  const patient = await prisma.transcribeMdPatient.create({
    data: { practiceId: practice.id, name: `B8 3c Proof Patient ${RUN_TAG}` },
    select: { id: true },
  });
  ok(`patient ${patient.id}`);

  const visit = await prisma.transcribeVisit.create({
    data: {
      userId: user.id,
      createdBy: user.id,
      practiceId: practice.id,
      patientId: patient.id,
      specialty: 'primary-care',
      inputMode: 'text_notes',
      status: 'QUEUED',
      // Synthetic, doctor-narrated, no PHI.
      rawTextInput:
        'Patient is a 54 year old presenting for routine follow up of well ' +
        'controlled hypertension. No chest pain, no shortness of breath. ' +
        `Blood pressure today 128 over 78. [${RUN_TAG}]`,
    },
    select: { id: true },
  });
  ok(`visit ${visit.id} created QUEUED`);

  // ── THE WALK ─────────────────────────────────────────────────────────────
  section('WALK — enqueue on the real queue and let the real worker fail it');
  const job = await queue.add(JOB_PROCESS_VISIT, {
    visitId: visit.id,
    userId: user.id,
  });
  const jobId = job.id;
  if (!jobId) {
    unknown('the queue returned a job with no id — cannot read its attempt count');
    return 2;
  }
  ok(`enqueued ${JOB_PROCESS_VISIT} as job ${jobId}`);

  const declaredAttempts = job.opts.attempts ?? 1;
  console.log(`   the job is allowed ${declaredAttempts} attempt(s) by queue.ts`);

  // ⚠️ THE INSTRUMENT'S OWN CONTROL. If `attempts` were 1, this walk could not
  // tell "the fix worked" from "there was never a retry to prevent" — a
  // one-attempt job ends at attemptsMade 1 either way. That is the vacuous
  // measurement this whole item is about, so it is refused rather than reported.
  if (declaredAttempts < 2) {
    unknown(
      `queue.ts allows only ${declaredAttempts} attempt — this walk cannot ` +
        'discriminate a discard from a job that was never going to retry.',
    );
    return 2;
  }
  ok(`attempts=${declaredAttempts} — a discard and a non-retry are distinguishable`);

  const startedAt = Date.now();
  let status = 'QUEUED';
  for (;;) {
    const row = await prisma.transcribeVisit.findUnique({
      where: { id: visit.id },
      select: { status: true },
    });
    status = row?.status ?? 'GONE';
    if (status === 'FAILED' || status === 'READY' || status === 'SIGNED') break;
    if (Date.now() - startedAt > TERMINAL_TIMEOUT_MS) break;
    await sleep(POLL_INTERVAL_MS);
  }
  const visitElapsedMs = Date.now() - startedAt;

  if (status !== 'FAILED') {
    unknown(
      `the visit reached ${status} after ${visitElapsedMs}ms, not FAILED — ` +
        'there is no permanent failure here to count attempts on.',
    );
    return 2;
  }
  ok(`the visit landed FAILED after ${visitElapsedMs}ms`);

  // ── THE MEASUREMENT ──────────────────────────────────────────────────────
  // ⚠️ THE VISIT ROW GOES FAILED ON ATTEMPT 1 EVEN PRE-FIX — that is
  // `shouldFailNow`, and it is exactly why the visit's status cannot be used to
  // count attempts. The job keeps retrying behind an already-FAILED visit. So
  // wait for the JOB to settle, not the row.
  section('MEASUREMENT — BullMQ’s own attempt counter, read back from Redis');
  const settleStarted = Date.now();
  let finalAttempts: number | null = null;
  let failedReason: string | null = null;
  let finishedOn: number | null = null;
  for (;;) {
    const readBack = await queue.getJob(jobId);
    if (!readBack) {
      unknown(
        `job ${jobId} is no longer in Redis — it was evicted before it could ` +
          'be read. Cannot tell.',
      );
      return 2;
    }
    const state = await readBack.getState();
    if (state === 'failed' || state === 'completed') {
      finalAttempts = readBack.attemptsMade;
      failedReason = readBack.failedReason ?? null;
      finishedOn = readBack.finishedOn ?? null;
      break;
    }
    if (Date.now() - settleStarted > JOB_SETTLE_TIMEOUT_MS) {
      unknown(
        `job ${jobId} was still ${j(state)} after ${JOB_SETTLE_TIMEOUT_MS}ms — ` +
          'it has not settled, so its attempt count is not final. Cannot tell.',
      );
      return 2;
    }
    await sleep(POLL_INTERVAL_MS);
  }

  console.log(`   attemptsMade  : ${finalAttempts}`);
  console.log(`   failedReason  : ${j(failedReason)}`);
  console.log(`   finishedOn    : ${finishedOn === null ? 'null' : new Date(finishedOn).toISOString()}`);
  console.log(`   settle wait   : ${Date.now() - settleStarted}ms`);

  // ⚠️ THE ERROR THAT ENDED THE JOB IS ASSERTED, NOT ASSUMED. A refusal is
  // evidence only when you know WHAT refused — AGENTS.md, on the composite-FK
  // arm that "passed" because an unrelated NOT NULL fired first. If the job died
  // of something other than the admission refusal, the attempt count is a
  // measurement of a different failure.
  const looksLikeAdmission =
    failedReason !== null && /balance|admission|insufficient/i.test(failedReason);
  if (!looksLikeAdmission) {
    unknown(
      `the job's failedReason ${j(failedReason)} does not look like an admission ` +
        'refusal — this is some other failure and its attempt count answers a ' +
        'different question.',
    );
    return 2;
  }
  ok('the job died of the admission refusal, which is the permanent failure under test');

  section('VERDICT');
  if (finalAttempts === 1) {
    ok(
      `attemptsMade=1 of an allowed ${declaredAttempts} — the permanent failure ` +
        'was DISCARDED. "fail-fast (skipping BullMQ retries)" is now a ' +
        'description of what happened.',
    );
    return 0;
  }
  if (finalAttempts === declaredAttempts) {
    bad(
      `attemptsMade=${finalAttempts} of ${declaredAttempts} — the job ran every ` +
        'attempt it was allowed. The permanent failure was RETRIED and the ' +
        'fail-fast log line is still false. This is the PRE-FIX reading.',
    );
    return 1;
  }
  unknown(
    `attemptsMade=${finalAttempts} of ${declaredAttempts} — neither 1 nor the ` +
      'full allowance. Something ended the job early for a reason this walk did ' +
      'not model; do not read it as either answer.',
  );
  return 2;
}

main()
  .then(async (verdict) => {
    await prisma.$disconnect();
    process.exit(verdict);
  })
  .catch(async (err) => {
    console.error('\n\u{1F534} the harness itself threw:', err);
    await prisma.$disconnect();
    process.exit(1);
  });
