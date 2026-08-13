// ============================================================================
// B8 step 3 — THE BEHAVIOURAL PROOF OF `observeFailedVisitUsage`, ON QA
// ----------------------------------------------------------------------------
// RELAY carried this debt out of B8 step 3 in these words:
//
//   "This item's seam runs UNFLAGGED, and it has never executed against a real
//    database in any environment. Every sibling seam in B8 ships inert behind
//    `BILLING_ENFORCED`, so a deploy of one is provably a no-op. This one is
//    not: it runs on every production failure the moment it lands, doing a
//    drain, an indexed read and a pricing pass on a path where a hang is a
//    stuck chart. The unit gate proves it cannot throw and cannot hang. THAT IS
//    NOT THE SAME AS HAVING RUN."
//
// This is that run. It is not a test of `classifyFailureAccountability` — that
// is pure and `gate-b8-failure-accountability.test.ts` covers every arm. It
// creates real rows, enqueues real `process_visit` jobs, and watches the real
// worker process fail a visit and price what the failure cost.
//
// ⚠️ WHY THE UNIT GATE IS NOT ENOUGH, IN ONE SENTENCE: ruling #98(b) — "a stub
// is a statement of what its author believes, and it agrees with the matcher
// because the same person wrote both." Every mock in that gate is mine,
// INCLUDING the one standing in for the loader whose real behaviour is the
// entire risk. B8 step 2's first behavioural run found THREE shipped defects
// that 3,601 unit tests could not see.
//
// ============================================================================
// ⚠️ IT REFUSES TO RUN WITH `BILLING_ENFORCED=true`, WHICH LOOKS BACKWARDS
// ----------------------------------------------------------------------------
// Its sibling `b8-admission-on-qa.ts` refuses WITHOUT the flag. This one
// refuses WITH it, and the asymmetry is the point rather than an inconsistency.
//
// The central claim of B8 step 3 — provisional ruling #103(c) — is that the
// observation runs UNFLAGGED. A run with the flag on cannot distinguish "the
// seam runs unconditionally" from "the seam runs because the flag is on", and
// the second is the thing #103(c) would be wrong about. So the posture under
// which the claim is falsifiable is the flag ABSENT, and that is the posture
// this file demands.
//
// The `not_started` arm is the exception and lives in ARM 3, which is the only
// arm that needs the flag — a `BillingAdmissionError` cannot be raised without
// it. ARM 3 therefore runs in a SECOND invocation, against a worker recreated
// with `docker-compose.qa.billing.yml`, and this file selects its arms from the
// live flag rather than from an argument nobody would keep in sync.
//
// ============================================================================
// ⚠️ WHAT THE `priced` ARM SEEDS, AND WHY SEEDING IS NOT CHEATING HERE
// ----------------------------------------------------------------------------
// ARM 2 inserts one `api_usage_events` row with `unitsSource: 'vendor'` before
// the visit fails. That row did not come from a vendor call, and it cannot:
// **the QA stack is REQUIRED to be incapable of reaching a vendor** — that is a
// standing rule with its own check (`check-qa-mock-posture.sh`), written after
// this stack made 298 real Anthropic calls on 2026-07-28. Under `MOCK_AI_CALLS`
// every row the pipeline writes carries `unitsSource: 'mock'`, and ruling 66
// makes `priceUsageRows` skip exactly those. So on QA the `priced` arm is
// UNREACHABLE through the pipeline, by design, forever.
//
// The honest options are therefore: seed the row, or leave the priced arm
// unproven and say so. Seeding is chosen because what is under test here is
// **the loader, the mapping and the pricer** — `loadVisitChargeableUsage`'s
// `timestamp` → `createdAt` translation, `priceUsageRows`' rate lookup against
// the REAL `price_rates` table, and B6's ×1.5 margin — none of which care where
// the row came from. What seeding does NOT prove is that the pipeline emits
// vendor rows in this shape; that is B4's territory and is not claimed here.
//
// ⚠️ AND THE EXPECTED NUMBER IS COMPUTED FROM THE RATE TABLE, NOT PINNED. A
// hardcoded micro-USD figure would go red the day a rate is re-versioned, which
// is a maintenance trap AND a check that fails for the wrong reason. ARM 2
// reads the rates it seeded units against and derives what the answer must be.
//
// ============================================================================
// ⚠️ WHAT THIS FILE CANNOT SEE, AND WHO SEES IT
// ----------------------------------------------------------------------------
// The product of this item is a LOG LINE — `log.info('...', 'failure cost')` in
// `worker.ts`. It is written to the worker process's stdout. This harness runs
// as a separate process under `docker exec`, so it CANNOT read that stdout: a
// sibling process does not share a container's log stream.
//
// So the proof is deliberately split, and each half asserts only what it can
// actually reach:
//
//   this file      — creates, drives, and asserts everything visible in the
//                    DATABASE, then writes a manifest of what the log must say
//   the manifest   — /tmp/b8-failure-cost-manifest.tsv, inside the container
//   the asserter   — scripts/qa/b8-failure-cost-log-assert.py, on the HOST,
//                    which is handed the manifest and a `docker logs` dump and
//                    checks the manifest's claims against it
//
// ⚠️ THE MANIFEST IS AN EXPECTATION WRITTEN BEFORE THE LOG IS READ, and that
// ordering is the whole value of splitting it this way — it is the §2.5
// "declare the delta first" discipline applied to an assertion. A harness that
// read the log and then decided what it should have said would be
// unfalsifiable.
//
// ============================================================================
// ⚠️ IT IS A WRITER, SO IT IS FAIL-CLOSED OFF ANY NON-QA DATABASE
// ----------------------------------------------------------------------------
// It creates a practice, a user, a patient, visits and (ARM 2) an
// `api_usage_events` row. `assertNonProdDatabase()` is the first statement in
// `main`, before anything else runs. F3 is production's rule and this respects
// it by being unable to reach production at all.
//
// ⚠️ IT NEVER WRITES `ledger_entries`, AND THAT IS AN ASSERTION RATHER THAN A
// HABIT. The item's central claim is that a failed visit is FREE, so the ledger
// count is captured before the first arm and re-read after the last one. On an
// APPEND-ONLY table a debit written by mistake could only be offset, never
// removed — so this is also the arm with the most expensive failure mode.
//
// ============================================================================
// Usage, from the repo root, against the running QA stack:
//
//   # PHASE 1 — arms 1 and 2, flag ABSENT (the resting posture)
//   docker exec -w /app/apps/transcribe-md meddoc-qa-transcribe-md-worker-1 \
//     npx tsx scripts/qa/b8-failure-cost-on-qa.ts
//   docker exec meddoc-qa-transcribe-md-worker-1 \
//     cat /tmp/b8-failure-cost-manifest.tsv > .b8-s3qa-manifest.tsv
//   docker logs meddoc-qa-transcribe-md-worker-1 > .b8-s3qa-worker.log 2>&1
//   python3 scripts/qa/b8-failure-cost-log-assert.py \
//     .b8-s3qa-manifest.tsv .b8-s3qa-worker.log
//
//   # PHASE 2 — arm 3, flag ON. Same three reads afterwards.
//   docker compose -p meddoc-qa -f docker-compose.qa.yml \
//     -f docker-compose.qa.billing.yml up -d --force-recreate transcribe-md-worker
//   docker exec -w /app/apps/transcribe-md meddoc-qa-transcribe-md-worker-1 \
//     npx tsx scripts/qa/b8-failure-cost-on-qa.ts
//
//   # restore the resting posture — flag ABSENT
//   docker compose -p meddoc-qa -f docker-compose.qa.yml \
//     up -d --force-recreate transcribe-md-worker
//
// ⚠️ THE HARNESS IS RUN FROM THE IMAGE, SO REBUILD BEFORE EACH RUN —
// `docker compose -p meddoc-qa -f docker-compose.qa.yml build transcribe-md-worker`.
// `docker cp` is not available to the unattended loop and the container's /app
// is not writable by its own user, so a hand-copied file is not an option; and
// a proof that ran a file the image does not contain would be describing a tree
// that does not exist. The QA IMAGE is checked, not only the migrations — see
// AGENTS.md, where a green `--qa` schema check sat over a worker image that
// predated the code it was supposed to exercise.
//
// ⚠️ AND WAIT FOR EVERY BullMQ ATTEMPT BEFORE READING THE LOG. A `transient`
// visit is only allowed to land FAILED on the final attempt, and a `permanent`
// one re-enters the failure branch on every attempt (B8 step 3c). Reading the
// stream too early sees fewer lines than were emitted and passes an
// exactly-once assertion for the wrong reason. The tell that all three ran is
// two `fail-fast` lines — that message is logged only on NON-final attempts.
//
// Exit: 0 = every arm this posture can run behaved · 1 = FINDING · 2 = cannot tell
// ============================================================================

import { randomUUID } from 'node:crypto';
import { writeFileSync } from 'node:fs';

import {
  billingEnforced,
  BILLING_ENFORCED_ENV,
  classifyFailureAccountability,
} from '@meddoc/ai';
import { prisma } from '@meddoc/db';
import { assertNonProdDatabase } from '@meddoc/db/guard';

import { getTranscribeMdQueue, JOB_PROCESS_VISIT } from '../../src/lib/queue';

// ⚠️ STATIC IMPORTS. `b8-admission-on-qa.ts` records why in full: dynamic
// `await import('@meddoc/ai')` inside a guard block returned a namespace whose
// members were not callable under tsx's CJS interop — `billingEnforced is not a
// function`, at runtime, after two guards had printed green. The static form is
// what `worker.ts` itself uses, so it is the shape actually exercised.

/** How long to wait for one visit to reach a terminal state.
 *
 *  ⚠️ GENEROUS BECAUSE A TRANSIENT FAILURE IS NOT ALLOWED TO FAIL FAST. The
 *  worker persists FAILED only on the FINAL BullMQ attempt unless the category
 *  is `permanent` (`worker.ts`'s `shouldFailNow`), and the queue is configured
 *  `attempts: 3, backoff: exponential, delay: 5_000` — so an `ours` visit
 *  spends ~15s in backoff before it is allowed to land. A timeout here is a `2`
 *  (cannot tell), never a pass. */
const TERMINAL_TIMEOUT_MS = 240_000;
const POLL_INTERVAL_MS = 2_000;

/** Where the log expectations are left for the host-side asserter. Inside the
 *  container, because that is the only filesystem this process can reach. */
const MANIFEST_PATH = '/tmp/b8-failure-cost-manifest.tsv';

/** Everything this proof creates is prefixed so a later reader can find it and
 *  nothing collides with the QA fixtures other suites depend on. */
const RUN_TAG = `b8s3-${randomUUID().slice(0, 8)}`;

/** The seeded vendor usage for ARM 2. Round numbers on purpose: the expected
 *  charge is derived from these and the live rate table, so a reader can check
 *  the arithmetic by hand. */
const SEEDED_MODEL = 'claude-sonnet-5';
const SEEDED_INPUT_TOKENS = 1_000;
const SEEDED_OUTPUT_TOKENS = 500;

/** B6's margin. Declared here only to DERIVE the expectation; the assertion
 *  compares against what the real pricer returned for the real rows. */
const MARGIN_NUMERATOR = 3n;
const MARGIN_DENOMINATOR = 2n;

type Verdict = 0 | 1 | 2;

const findings: string[] = [];
const cannotTell: string[] = [];

function ok(msg: string): void {
  console.log(`   ✔ ${msg}`);
}
function bad(msg: string): void {
  console.log(`   ✖ ${msg}`);
  findings.push(msg);
}
function unknown(msg: string): void {
  console.log(`   ? ${msg}`);
  cannotTell.push(msg);
}
function section(title: string): void {
  console.log(`\n── ${title} ${'─'.repeat(Math.max(0, 68 - title.length))}`);
}

/** BigInt-safe JSON for the log lines. */
function j(v: unknown): string {
  return JSON.stringify(v, (_k, val) => (typeof val === 'bigint' ? `${val}` : val));
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** One line of the manifest the host-side asserter checks against `docker logs`. */
interface LogExpectation {
  visitId: string;
  arm: string;
  /** The `accountability` field the log line must carry. */
  accountability: string;
  /** The arm of `FailedVisitObservation` the log line must be shaped like,
   *  identified by the field only that arm emits. */
  observed: 'priced' | 'unpriceable' | 'not_started';
  /** For `priced` — the exact `wouldChargeMicroUsd` string expected. Empty
   *  otherwise. */
  wouldChargeMicroUsd: string;
}

// ────────────────────────────────────────────────────────────────────────────
// THE VISIT SHAPE — one function, so the arms cannot differ by accident
// ----------------------------------------------------------------------------
// ⚠️ `audio_upload` WITH AN AUDIO KEY THAT POINTS AT NOTHING, AND BOTH HALVES
// OF THAT ARE DELIBERATE.
//
// It must be `audio_upload` rather than `text_notes` because the failure has to
// happen INSIDE the worker's `try`. `worker.ts` validates per-mode inputs at
// :346–:358, and the `try` opens at :409 — so a visit with a MISSING audioKey
// throws fifty lines above any handler, exactly the shape of B8 step 2's DEFECT
// 1. Such a visit never reaches the FAILED branch and never produces a failure-
// cost line, so it would prove nothing about this item.
//
// Giving it a well-formed key that resolves to no MinIO object moves the
// failure past admission and past the status update, into L1's download — which
// is inside the `try`, which is where the observation lives. `processingStartedAt`
// is therefore NON-NULL for these arms, and that is asserted: it is the
// structural proof that the visit died in the PIPELINE rather than at admission.
// ────────────────────────────────────────────────────────────────────────────
async function createFailingVisit(args: {
  userId: string;
  practiceId: string;
  patientId: string;
  label: string;
}): Promise<string> {
  const visit = await prisma.transcribeVisit.create({
    data: {
      userId: args.userId,
      createdBy: args.userId,
      practiceId: args.practiceId,
      patientId: args.patientId,
      specialty: 'primary-care',
      inputMode: 'audio_upload',
      status: 'QUEUED',
      // Well-formed and resolvable to nothing. No object was ever uploaded
      // under this key, so L1's fetch fails — a REAL pipeline failure, not a
      // simulated one, and no audio ever existed to be PHI.
      audioKey: `qa-proof/${args.label}/no-such-object.webm`,
      audioMimeType: 'audio/webm',
    },
    select: { id: true },
  });
  return visit.id;
}

interface TerminalState {
  status: string;
  failureCategory: string | null;
  reviewReason: string | null;
  processingStartedAt: Date | null;
  timedOut: boolean;
  elapsedMs: number;
}

/** Poll the visit row until the worker puts it somewhere terminal. */
async function waitForTerminal(visitId: string): Promise<TerminalState> {
  const started = Date.now();
  for (;;) {
    const v = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        status: true,
        failureCategory: true,
        reviewReason: true,
        processingStartedAt: true,
      },
    });
    if (!v) throw new Error(`visit ${visitId} vanished while polling`);

    const elapsedMs = Date.now() - started;
    if (v.status === 'FAILED' || v.status === 'READY' || v.status === 'SIGNED') {
      return { ...v, timedOut: false, elapsedMs };
    }
    if (elapsedMs > TERMINAL_TIMEOUT_MS) {
      return { ...v, timedOut: true, elapsedMs };
    }
    await sleep(POLL_INTERVAL_MS);
  }
}

/**
 * WHAT THE REAL RATE TABLE SAYS THE SEEDED ROW COSTS, READ RATHER THAN PINNED.
 *
 * Returns null if the rates this arm depends on are absent or ambiguous — which
 * is a CANNOT-TELL, not a finding. A missing rate makes the pricer decline with
 * `no_rate_for_key_at_instant`, and an arm that treated that as a defect in
 * `observeFailedVisitUsage` would be blaming the wrong module.
 */
async function expectedChargeForSeededRow(at: Date): Promise<bigint | null> {
  const rates: Array<{ unitType: string; rateMicroUsd: bigint; unitQuantity: bigint }> =
    await prisma.$queryRaw`
      SELECT "unitType", "rateMicroUsd", "unitQuantity"
      FROM price_rates
      WHERE provider = 'anthropic'
        AND "modelName" = ${SEEDED_MODEL}
        AND "unitType" IN ('tokens_input', 'tokens_output')
        AND "effectiveFrom" <= ${at}
        AND ("effectiveTo" IS NULL OR "effectiveTo" > ${at})
    `;
  const input = rates.find((r) => r.unitType === 'tokens_input');
  const output = rates.find((r) => r.unitType === 'tokens_output');
  if (!input || !output) return null;
  if (rates.length !== 2) return null;

  // cost = Σ units × rate / unitQuantity, then B6's ×1.5 margin.
  const cost =
    (BigInt(SEEDED_INPUT_TOKENS) * input.rateMicroUsd) / input.unitQuantity +
    (BigInt(SEEDED_OUTPUT_TOKENS) * output.rateMicroUsd) / output.unitQuantity;
  return (cost * MARGIN_NUMERATOR) / MARGIN_DENOMINATOR;
}

async function main(): Promise<Verdict> {
  console.log('B8 step 3 — behavioural proof of `observeFailedVisitUsage`, on the live QA stack');
  console.log(`run tag: ${RUN_TAG}`);

  // ── GUARD 0 — FAIL-CLOSED. This file writes; it must not reach production.
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
    console.log('   These arms enqueue real pipeline jobs. Without the mock that is real vendor spend.');
    return 1;
  }
  ok('MOCK_AI_CALLS=true in this process — read from the live container env');

  const flagOn = billingEnforced();
  console.log(`   ${BILLING_ENFORCED_ENV}=${j(process.env[BILLING_ENFORCED_ENV])} → billingEnforced()=${flagOn}`);

  const queue = getTranscribeMdQueue();
  const expectations: LogExpectation[] = [];

  // ── FIXTURE ──────────────────────────────────────────────────────────────
  // A dedicated practice. ARM 3 grants credit, and `ledger_entries` is
  // APPEND-ONLY — funding a shared practice would change the admission
  // behaviour of every other QA suite's visits for as long as the row exists,
  // which on an append-only table is forever.
  section('FIXTURE — a practice of its own, so nothing else inherits its wallet');
  const practice = await prisma.practice.create({
    data: { name: `B8s3 proof (${RUN_TAG})`, slug: `b8s3-proof-${RUN_TAG}` },
    select: { id: true, slug: true },
  });
  ok(`practice ${practice.id} (${practice.slug})`);

  const user = await prisma.user.create({
    data: {
      email: `${RUN_TAG}@b8s3-proof.invalid`,
      // Never used — this proof never authenticates. A literal, so nothing
      // here resembles a credential.
      passwordHash: 'not-a-credential-this-account-cannot-log-in',
      // ⚠️ TWO ROLE COLUMNS, AND ONLY `practiceRole` SATISFIES T6's CHECK
      // `users_active_member_has_practice_role`. See `b8-admission-on-qa.ts`,
      // which paid for this discovery.
      role: 'DOCTOR',
      practiceRole: 'OWNER',
      isActive: true,
      practiceId: practice.id,
    },
    select: { id: true },
  });
  ok(`user ${user.id}`);

  const patient = await prisma.transcribeMdPatient.create({
    data: { practiceId: practice.id, name: `B8s3 Proof Patient ${RUN_TAG}` },
    select: { id: true },
  });
  ok(`patient ${patient.id}`);

  // ── THE NEGATIVE THAT MATTERS MOST, CAPTURED BEFORE ANYTHING RUNS ────────
  // The item's central claim is that a failed visit is FREE. A count taken
  // afterwards could not tell a debit apart from a pre-existing row.
  const ledgerBefore = await prisma.ledgerEntry.count({ where: { practiceId: practice.id } });
  if (ledgerBefore !== 0) {
    unknown(`a practice created moments ago already holds ${ledgerBefore} ledger rows — cannot tell`);
    return 2;
  }
  ok('ledger_entries for this practice: 0 — the baseline for "a failed visit is free"');

  if (flagOn) {
    // ══ ARM 3 — `not_started`: ADMISSION REFUSED, AND THE METER IS NOT READ ═
    section('ARM 3 — admission refuses; the observation must SHORT-CIRCUIT');
    console.log('   (this posture runs ARM 3 only — arms 1 and 2 assert the UNFLAGGED claim)');

    const refusedVisitId = await createFailingVisit({
      userId: user.id,
      practiceId: practice.id,
      patientId: patient.id,
      label: `${RUN_TAG}-arm3`,
    });
    ok(`visit ${refusedVisitId} created QUEUED on an UNFUNDED practice`);

    await queue.add(JOB_PROCESS_VISIT, { visitId: refusedVisitId, userId: user.id });
    const refused = await waitForTerminal(refusedVisitId);
    console.log(
      `   terminal after ${Math.round(refused.elapsedMs / 1000)}s: status=${refused.status} ` +
        `category=${j(refused.failureCategory)} processingStartedAt=${j(refused.processingStartedAt)}`
    );

    if (refused.timedOut) {
      unknown(`ARM 3 never reached a terminal state (stuck at ${refused.status}) — cannot tell`);
    } else if (refused.status !== 'FAILED') {
      bad(`ARM 3: an UNFUNDED practice reached ${refused.status} — admission did not refuse`);
    } else {
      ok('ARM 3: the visit landed FAILED');
      // The structural discriminator, from B8 step 2's proof: admission runs
      // BEFORE the status update that stamps this column, so nothing that
      // fails later can imitate a NULL here.
      if (refused.processingStartedAt !== null) {
        bad(
          'ARM 3: processingStartedAt IS SET — the visit got PAST admission and died later, ' +
            'so this arm is not exercising the `not_started` path at all'
        );
      } else {
        ok('ARM 3: processingStartedAt IS NULL — it died AT admission, before the pipeline started');
        expectations.push({
          visitId: refusedVisitId,
          arm: 'arm3-not_started',
          accountability: 'not_started',
          observed: 'not_started',
          wouldChargeMicroUsd: '0',
        });
        ok('ARM 3: expectation recorded — the log must say accountability=not_started');
      }
    }
  } else {
    // ══ ARMS 1 & 2 — THE UNFLAGGED CLAIM, WHICH IS RULING #103(c) ═══════════
    // ⚠️ THESE ARE THE ARMS THAT COULD NOT EXIST IF #103(c) WERE WRONG. With
    // the flag absent, `billingEnforced()` is false and every OTHER B8 seam is
    // inert. If a `failure cost` line appears anyway, the observation ran
    // unconditionally — which is the claim, measured rather than asserted.
    section('ARM 1 — a real pipeline failure with an EMPTY meter, flag ABSENT');

    const arm1VisitId = await createFailingVisit({
      userId: user.id,
      practiceId: practice.id,
      patientId: patient.id,
      label: `${RUN_TAG}-arm1`,
    });
    ok(`visit ${arm1VisitId} created QUEUED — audio key resolves to no object`);

    await queue.add(JOB_PROCESS_VISIT, { visitId: arm1VisitId, userId: user.id });
    const arm1 = await waitForTerminal(arm1VisitId);
    console.log(
      `   terminal after ${Math.round(arm1.elapsedMs / 1000)}s: status=${arm1.status} ` +
        `category=${j(arm1.failureCategory)} processingStartedAt=${j(arm1.processingStartedAt)}`
    );
    console.log(`   reviewReason: ${j(arm1.reviewReason)}`);

    if (arm1.timedOut) {
      unknown(`ARM 1 never reached a terminal state (stuck at ${arm1.status}) — cannot tell`);
    } else if (arm1.status !== 'FAILED') {
      bad(`ARM 1: a visit whose audio does not exist reached ${arm1.status} — no failure to observe`);
    } else {
      ok('ARM 1: the visit landed FAILED');

      // ⚠️ THE OPPOSITE ASSERTION TO ARM 3's, AND IT IS WHAT MAKES THIS ARM
      // ABOUT THE PIPELINE. A NULL here would mean the visit died at admission
      // and the observation took the `not_started` short-circuit — passing for
      // a reason that has nothing to do with the loader under test.
      if (arm1.processingStartedAt === null) {
        bad(
          'ARM 1: processingStartedAt IS NULL — the visit died at or before admission, so the ' +
            'meter was never read and this arm proves nothing about the loader'
        );
      } else {
        ok('ARM 1: processingStartedAt is set — it died INSIDE the pipeline, where the seam lives');

        // ⚠️ ACCOUNTABILITY IS NOT RE-DERIVED HERE, IT IS COMPUTED BY THE REAL
        // FUNCTION. Re-implementing the permanent→input mapping in this file
        // would make the check agree with a second copy of the policy rather
        // than with the policy. What is under test is the WIRING: does the log
        // carry what the pure function returns for the category the worker
        // really produced?
        const category = arm1.failureCategory;
        if (category !== 'transient' && category !== 'permanent' && category !== 'provider_down') {
          unknown(`ARM 1: failureCategory=${j(category)} is outside the worker's vocabulary — cannot tell`);
        } else {
          const accountability = classifyFailureAccountability({ category, errorName: null });
          ok(`ARM 1: worker produced category=${category} → classifier says accountability=${accountability}`);
          expectations.push({
            visitId: arm1VisitId,
            arm: 'arm1-empty-meter',
            accountability,
            // Under MOCK every pipeline-written row is `unitsSource: 'mock'`
            // and ruling 66 makes the pricer skip them, so a failed QA visit's
            // meter holds nothing chargeable. `nothing_billable` is the honest
            // expectation here — and it is a DIFFERENT fact from a pricing gap,
            // which is why `unpriceable` carries B6's reason.
            observed: 'unpriceable',
            wouldChargeMicroUsd: '',
          });
          ok('ARM 1: expectation recorded — the log must carry a `reason`, not a charge');
        }
      }
    }

    // ══ ARM 2 — THE `priced` PATH, AGAINST THE REAL RATE TABLE ═════════════
    section('ARM 2 — the same failure with a VENDOR usage row: the pricer must run');

    const arm2VisitId = await createFailingVisit({
      userId: user.id,
      practiceId: practice.id,
      patientId: patient.id,
      label: `${RUN_TAG}-arm2`,
    });
    ok(`visit ${arm2VisitId} created QUEUED — same shape, same function as ARM 1`);

    // The seeded row. See the header: this is the only way the priced arm is
    // reachable on a stack that is REQUIRED to be unable to call a vendor.
    const seededAt = new Date();
    await prisma.apiUsageEvent.create({
      data: {
        visitId: arm2VisitId,
        userId: user.id,
        practiceId: practice.id,
        provider: 'anthropic',
        operation: 'qa-proof-seed',
        modelName: SEEDED_MODEL,
        inputTokens: SEEDED_INPUT_TOKENS,
        outputTokens: SEEDED_OUTPUT_TOKENS,
        // ⚠️ `vendor`, which is the entire point of the row. The CHECK
        // `api_usage_events_units_source_domain` allows only vendor|mock, and
        // ruling 66 makes the pricer skip everything that is not `vendor`.
        unitsSource: 'vendor',
        unitType: 'tokens',
        unitCount: SEEDED_INPUT_TOKENS + SEEDED_OUTPUT_TOKENS,
        // The legacy per-row money columns. Not read by `priceUsageRows`, which
        // prices from UNITS against `price_rates` — set to 0 so nothing here
        // can be mistaken for the answer the pricer is supposed to compute.
        unitCostUsd: 0,
        totalCostUsd: 0,
        timestamp: seededAt,
      },
    });
    ok(
      `seeded 1 vendor usage row: ${SEEDED_MODEL} ${SEEDED_INPUT_TOKENS} in / ` +
        `${SEEDED_OUTPUT_TOKENS} out at ${seededAt.toISOString()}`
    );

    const expectedCharge = await expectedChargeForSeededRow(seededAt);
    if (expectedCharge === null) {
      unknown(
        `no unambiguous tokens_input/tokens_output rate for ${SEEDED_MODEL} at ${seededAt.toISOString()} — ` +
          'the pricer would decline for a reason that is about the rate table, not about this item'
      );
    } else {
      ok(`rate table says this row prices to ${expectedCharge} micro-USD after B6's ×1.5 margin`);
    }

    await queue.add(JOB_PROCESS_VISIT, { visitId: arm2VisitId, userId: user.id });
    const arm2 = await waitForTerminal(arm2VisitId);
    console.log(
      `   terminal after ${Math.round(arm2.elapsedMs / 1000)}s: status=${arm2.status} ` +
        `category=${j(arm2.failureCategory)} processingStartedAt=${j(arm2.processingStartedAt)}`
    );

    if (arm2.timedOut) {
      unknown(`ARM 2 never reached a terminal state (stuck at ${arm2.status}) — cannot tell`);
    } else if (arm2.status !== 'FAILED') {
      bad(`ARM 2: expected FAILED, got ${arm2.status} — no failure to price`);
    } else if (arm2.processingStartedAt === null) {
      bad('ARM 2: processingStartedAt IS NULL — died at admission, so the meter was never read');
    } else {
      ok('ARM 2: the visit landed FAILED inside the pipeline');
      const category = arm2.failureCategory;
      if (category !== 'transient' && category !== 'permanent' && category !== 'provider_down') {
        unknown(`ARM 2: failureCategory=${j(category)} is outside the worker's vocabulary — cannot tell`);
      } else if (expectedCharge !== null) {
        const accountability = classifyFailureAccountability({ category, errorName: null });
        expectations.push({
          visitId: arm2VisitId,
          arm: 'arm2-priced',
          accountability,
          observed: 'priced',
          wouldChargeMicroUsd: expectedCharge.toString(),
        });
        ok(
          `ARM 2: expectation recorded — the log must say accountability=${accountability}, ` +
            `wouldChargeMicroUsd=${expectedCharge}, charged=false`
        );
      }
    }
  }

  // ── THE NEGATIVE, RE-READ ────────────────────────────────────────────────
  // ⚠️ THIS IS THE ASSERTION WITH THE MOST EXPENSIVE FAILURE MODE. Every arm
  // above ran a real failure through a seam whose whole claim is that it
  // charges nothing. `ledger_entries` is APPEND-ONLY: a debit written here
  // could only ever be offset by an `adjustment` row that then lives beside it
  // forever.
  section('THE CENTRAL CLAIM — a failed visit is FREE');
  // ⚠️ ZERO IN EVERY POSTURE, AND AN EARLIER DRAFT OF THIS LINE WAS WRONG.
  // It read `flagOn ? 1 : 0`, on the belief that ARM 3 granted promo credit
  // after its refusal — which it does not, and never needed to: the arm's whole
  // point is an UNFUNDED practice. The expectation was carried over from
  // `b8-admission-on-qa.ts`, whose ARM 2 really does grant. Caught by reading
  // this file's own ARM 3 before running it, and it would have failed the run
  // for a fact about the harness rather than about the item.
  //
  // The corrected form is also the stronger claim: NO arm in this proof, in
  // EITHER posture, writes a ledger row at all.
  const ledgerAfter = await prisma.ledgerEntry.count({ where: { practiceId: practice.id } });
  if (ledgerAfter !== 0) {
    bad(
      `ledger_entries for this practice went ${ledgerBefore} → ${ledgerAfter}, expected 0. ` +
        'A failed visit was CHARGED, and on an append-only table that can only be offset, ' +
        'never removed.'
    );
  } else {
    ok(`ledger_entries ${ledgerBefore} → ${ledgerAfter} — nothing was charged for any failed visit`);
  }

  // ── THE MANIFEST ─────────────────────────────────────────────────────────
  // Written BEFORE any log is read. See the header: this is the "declare the
  // delta first" discipline applied to an assertion.
  section('MANIFEST — what the worker log must say, written before it is read');
  if (expectations.length === 0) {
    unknown('no arm produced an expectation — there is nothing for the log asserter to check');
  } else {
    const lines = expectations.map(
      (e) => `${e.visitId}\t${e.arm}\t${e.accountability}\t${e.observed}\t${e.wouldChargeMicroUsd}`
    );
    writeFileSync(MANIFEST_PATH, `${lines.join('\n')}\n`, 'utf8');
    for (const l of lines) console.log(`   ${l.replace(/\t/g, '  ')}`);
    ok(`${expectations.length} expectation(s) → ${MANIFEST_PATH}`);
    console.log('   now, ON THE HOST — and only once every BullMQ attempt has run:');
    console.log('     python3 scripts/qa/b8-failure-cost-log-assert.py <manifest> <docker-logs-dump>');
  }

  section('WHAT THIS RUN CREATED (synthetic, QA-only, left in place)');
  console.log(`   practice ${practice.id} · user ${user.id} · patient ${patient.id}`);
  console.log(`   visits   ${expectations.map((e) => e.visitId).join(' · ') || '(none)'}`);

  await queue.close();

  console.log('');
  if (findings.length > 0) {
    console.log(`\u{1F534} ${findings.length} FINDING(S):`);
    for (const f of findings) console.log(`   • ${f}`);
    return 1;
  }
  if (cannotTell.length > 0) {
    console.log(`\u{1F7E1} ${cannotTell.length} thing(s) could not be established:`);
    for (const c of cannotTell) console.log(`   • ${c}`);
    return 2;
  }
  console.log(
    flagOn
      ? '\u{1F7E2} DB-VISIBLE HALF OK (flag ON): admission refused and nothing was charged.'
      : '\u{1F7E2} DB-VISIBLE HALF OK (flag ABSENT): real failures, nothing charged.'
  );
  console.log('   ⚠️ THE LOG LINE IS NOT PROVEN YET — run the host-side asserter.');
  return 0;
}

main().then(
  (code) => process.exit(code),
  (err) => {
    console.error('\u{1F7E1} harness error — cannot tell:', err);
    process.exit(2);
  }
);
