// ============================================================================
// B8 — THE BEHAVIOURAL PROOF, ON THE LIVE QA STACK, THROUGH THE REAL WORKER
// ----------------------------------------------------------------------------
// RELAY has carried this debt across FOUR items — B8 step 1, B8 step 2, B7 step
// 3a and B7 step 3b — each naming it and none discharging it. Its wording, from
// B8 step 2's ledger row:
//
//   "What exists is a unit-level gate over the decision logic plus a
//    type-checked wiring; what does not exist is A VISIT WALKED END TO END
//    THROUGH THE REAL WORKER WITH THE FLAG ON, watching admission refuse and
//    the visit land FAILED with a transient/permanent category."
//
// And B7 step 3a widened it:
//
//   "It is now BROADER than B8 step 2 left it: my change makes a promo-funded
//    wallet ADMIT, so the proof should walk BOTH DIRECTIONS."
//
// This is that walk. It is not a test of `decideAdmission` — that exists and
// passes. It creates real rows, enqueues a real BullMQ job, and watches the
// real worker process decide.
//
// ============================================================================
// ⚠️ WHY IT LIVES HERE AND NOT BESIDE `scripts/qa/b6-writer-refuses-on-qa.ts`
// ----------------------------------------------------------------------------
// B6's proof runs on the HOST, and it can, because the thing it demonstrates —
// `assertProdDatabase()` refusing — happens BEFORE Prisma is touched. It never
// needs a connection.
//
// This one does. QA's postgres and redis are on the compose network and are
// NOT published to the host (`docker ps` shows `5432/tcp` and `6379/tcp` with
// no host binding, deliberately — the stack is isolated). So the proof has to
// run INSIDE the network, which means inside the image, and
// `Dockerfile.worker:96` copies exactly one script tree:
//
//     COPY apps/transcribe-md/scripts ./apps/transcribe-md/scripts
//
// The top-level `scripts/` directory is not in the worker image at all. Putting
// this file in `scripts/qa/` for tidiness would put it somewhere it can never
// run. Location follows reachability.
//
// ============================================================================
// ⚠️ IT IS A WRITER, SO IT IS FAIL-CLOSED OFF ANY NON-QA DATABASE
// ----------------------------------------------------------------------------
// Unlike B6's proof this one CREATES rows — a practice, a user, a patient, two
// visits, and (in the ADMIT arm) a `grant` row in `ledger_entries`, which is
// APPEND-ONLY and cannot be removed. `assertNonProdDatabase()` is the first
// statement in `main`, before anything is constructed.
//
// F3 is production's rule and this respects it by being unable to reach
// production at all. `grantPromoCredit` is deliberately NOT prod-only (ruling
// #97(c)) precisely so this proof can exist; that makes the guard THIS file's
// responsibility rather than the writer's, and #97(c) says so in as many words.
//
// ============================================================================
// ⚠️ THE ARMS ARE A PAIR, AND NEITHER IS EVIDENCE ALONE
// ----------------------------------------------------------------------------
// "The visit FAILED" is worthless on its own. A visit can fail for a missing
// audio key, a dead database, a bad fixture, a typo in this file — every one of
// those produces `status=FAILED` and most produce `permanent`. AGENTS.md's rule
// is the one that matters here: A REFUSAL IS EVIDENCE ONLY WHEN YOU KNOW WHAT
// REFUSED.
//
// So the two arms are the SAME VISIT SHAPE, built by the same function, and
// differ in EXACTLY ONE FACT: whether the practice holds a `grant` row. If the
// unfunded one dies and the funded one completes, the wallet is the variable
// and nothing else can be.
//
// And the refusal carries a STRUCTURAL discriminator on top of the pair:
// `admitVisitOrThrow` is called at `worker.ts:368`, BEFORE the status update at
// :377 that sets `processingStartedAt`. So a visit refused at admission has
//
//     status = FAILED   AND   processingStartedAt IS NULL
//
// which no later failure can imitate — anything that dies after admission has
// necessarily stamped that column on its way past. That is the assertion which
// says the block BLOCKED THE WORK rather than merely reported on it.
//
// ⚠️ `ai_calls` IS NOT USABLE AS THAT DISCRIMINATOR, and the reason is worth
// writing down so nobody adds it later thinking it strengthens the proof: under
// `MOCK_AI_CALLS=true` the mocked path suppresses `ai_calls` rows by ruling, so
// "zero vendor rows" is the state of EVERY QA visit, refused or not. It would
// be a check that cannot go red — the decoration this programme keeps catching.
//
// ============================================================================
// Usage, from the repo root, against the running QA stack:
//
//   docker exec meddoc-qa-transcribe-md-worker-1 \
//     npx tsx scripts/qa/b8-admission-on-qa.ts
//
//   (the worker's WORKDIR is /app/apps/transcribe-md, and it must have been
//    recreated with BILLING_ENFORCED=true — see docker-compose.qa.billing.yml)
//
// Exit: 0 = both arms behaved · 1 = FINDING · 2 = cannot tell
// ============================================================================

import { randomUUID } from 'node:crypto';

import {
  billingEnforced,
  BILLING_ENFORCED_ENV,
  decideAdmission,
  grantPromoCredit,
  PROMO_GRANT_MICRO_USD,
  readPracticeBalance,
} from '@meddoc/ai';
import { prisma } from '@meddoc/db';
import { assertNonProdDatabase } from '@meddoc/db/guard';

import { getTranscribeMdQueue, JOB_PROCESS_VISIT } from '../../src/lib/queue';

// ⚠️ STATIC IMPORTS, AND THE FIRST ATTEMPT AT THIS FILE USED DYNAMIC ONES.
// `await import('@meddoc/ai')` inside the guard block looked stricter — nothing
// loaded until the database had been vouched for — and it silently returned a
// namespace whose members were not callable under tsx's CJS interop:
// `billingEnforced is not a function`, at runtime, after two guards had already
// printed green. The static form is what `worker.ts` itself uses, so it is the
// shape actually exercised in production.
//
// It costs nothing here: `assertNonProdDatabase()` is still the first statement
// in `main()`, and importing a Prisma client CONSTRUCTS it without connecting.
// The guard exists to refuse before a WRITE, and no write can precede it.

/** How long to wait for the worker to reach a terminal state on one visit.
 *  A mocked `text_notes` visit is the cheapest walk the pipeline has — no
 *  transcription — and the QA fixtures that reached READY did so in seconds.
 *  Generous, because a timeout here is a `2` (cannot tell) and never a pass. */
const TERMINAL_TIMEOUT_MS = 240_000;
const POLL_INTERVAL_MS = 2_000;

/** Everything this proof creates is prefixed so a later reader can find it,
 *  and so nothing collides with the QA fixtures other suites depend on. */
const RUN_TAG = `b8proof-${randomUUID().slice(0, 8)}`;

type Verdict = 0 | 1 | 2;

// ────────────────────────────────────────────────────────────────────────────
// ⚠️ THE SUBSTRING TRAP, FIFTH SIGHTING, AND IT WAS IN THIS FILE'S OWN CHECK
// ----------------------------------------------------------------------------
// The first version of the negative assertion below read
//
//     /corrupt|unsupported format|re-upload/i
//
// which is the obvious way to say "does not blame the recording", and it is
// wrong in the most expensive direction. The fixed copy says, deliberately,
// **"re-uploading will not help"** — the clause that exists to stop the doctor
// wasting the work. The bare token `re-upload` matched it, so the check went
// RED for the fix SUCCEEDING.
//
// That is both families AGENTS.md names, at once: the substring trap
// (`'dashboard'` contains `'board'`; `'practice-scope'` matching
// `"practice-scoped"`), and "a check that fails when the thing it guards starts
// working is a check nobody keeps".
//
// So the matcher names the MISLEADING CLAIM, not a word that appears in it. The
// legacy string this exists to exclude is, verbatim from
// `buildUserFacingFailureReason`'s fall-through:
//
//     "Processing failed during setup. The audio file may be corrupt or in an
//      unsupported format — please re-upload to try again."
//
// ⚠️ AND IT IS POSITIVE-CONTROLLED BELOW, against that exact sentence. A
// matcher that can no longer recognise the bad copy would let the defect return
// while reporting green, and a negative assertion is precisely the kind that is
// believed without scrutiny.
// ────────────────────────────────────────────────────────────────────────────
const BLAMES_THE_RECORDING =
  /audio file may be corrupt|unsupported format|please re-upload to try again/i;

/** The exact string the worker produced for a billing refusal BEFORE the fix.
 *  Kept verbatim as the positive control for {@link BLAMES_THE_RECORDING}. */
const LEGACY_MISLEADING_REASON =
  'Processing failed during setup. The audio file may be corrupt or in an ' +
  'unsupported format — please re-upload to try again.';

/** The shape the fix produces. Used as the NEGATIVE control: the matcher must
 *  not fire on it, and the clause that used to break it is still in there. */
const FIXED_REASON_SAMPLE =
  'This practice is out of processing credit, so this visit was not started. ' +
  'Your recording is saved and is not the problem — re-uploading will not help. ' +
  'Add credit to the practice, then retry this visit.';

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

// ────────────────────────────────────────────────────────────────────────────
// THE VISIT SHAPE — built ONCE, used by both arms
// ----------------------------------------------------------------------------
// ⚠️ ONE FUNCTION ON PURPOSE. If the refused visit and the admitted visit were
// constructed by two pieces of code, a difference between them could be the
// real cause of the difference in outcome, and the proof would be measuring its
// own fixture. Both arms call this; the ONLY thing that changes between them is
// the ledger.
// ────────────────────────────────────────────────────────────────────────────
async function createWalkableVisit(args: {
  prisma: typeof import('@meddoc/db').prisma;
  userId: string;
  practiceId: string;
  patientId: string;
  label: string;
}): Promise<string> {
  const visit = await args.prisma.transcribeVisit.create({
    data: {
      userId: args.userId,
      createdBy: args.userId,
      practiceId: args.practiceId,
      patientId: args.patientId,
      specialty: 'primary-care',
      inputMode: 'text_notes',
      status: 'QUEUED',
      // Synthetic, doctor-narrated, no PHI — the same shape as the QA fixture
      // visits that reach READY under MOCK.
      rawTextInput:
        'Patient is a 54 year old presenting for routine follow up of well ' +
        'controlled hypertension. No chest pain, no shortness of breath. ' +
        'Blood pressure today 128 over 78. Continue current medication and ' +
        `review in three months. [${args.label}]`,
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
async function waitForTerminal(
  prisma: typeof import('@meddoc/db').prisma,
  visitId: string,
): Promise<TerminalState> {
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

async function main(): Promise<Verdict> {
  console.log('B8 — behavioural proof of the admission seam, on the live QA stack');
  console.log(`run tag: ${RUN_TAG}`);

  // ── GUARD 0 — FAIL-CLOSED. This file writes; it must not be able to reach
  //    production. Before any import that could construct a client.
  section('GUARD — the target is a qa/test database, and the stack is severed');
  let target;
  try {
    target = assertNonProdDatabase();
  } catch (err) {
    console.log(`\n\u{1F534} REFUSING TO RUN — the database is not a qa/test one:`);
    console.log(`   ${err instanceof Error ? err.message.split('\n')[0] : String(err)}`);
    return 1;
  }
  ok(`database=${target.database} host=${target.host} — carries a qa/test marker`);

  // The vendor-severance half. This walk runs the WHOLE pipeline on the admit
  // arm, so a stack that could reach a vendor would spend real money to prove
  // a billing point — the 2026-07-28 failure exactly.
  if (process.env.MOCK_AI_CALLS !== 'true') {
    console.log(`\n\u{1F534} REFUSING TO RUN — MOCK_AI_CALLS is ${j(process.env.MOCK_AI_CALLS)}, not "true".`);
    console.log('   The ADMIT arm walks the full pipeline. Without the mock that is real vendor spend.');
    return 1;
  }
  ok('MOCK_AI_CALLS=true in this process — read from the live container env');

  if (!billingEnforced()) {
    console.log(`\n\u{1F7E1} ${BILLING_ENFORCED_ENV} is ${j(process.env[BILLING_ENFORCED_ENV])}, not "true" — CANNOT TELL.`);
    console.log('   The seam is inert, so both arms would pass for the wrong reason:');
    console.log('   an unfunded visit would sail through admission because admission did not run.');
    console.log('   Recreate the worker with docker-compose.qa.billing.yml first.');
    return 2;
  }
  ok(`${BILLING_ENFORCED_ENV}=true in this process — the seam is in effect`);

  // ── THE MATCHER'S OWN CONTROLS — both directions, before it is trusted ────
  // ARM 1's "does NOT blame the recording" is an emptiness test, and AGENTS.md
  // is explicit that those are the ones most likely to be believed without
  // scrutiny and least likely to be controlled. Two assertions, because the two
  // ways it can be wrong are independent: too NARROW (misses the bad copy and
  // reports a clean run) and too BROAD (fires on the good copy, which is what
  // the first version of it actually did).
  section('CONTROL — can the copy matcher still tell the two apart?');
  if (!BLAMES_THE_RECORDING.test(LEGACY_MISLEADING_REASON)) {
    bad(
      'the copy matcher no longer recognises the PRE-FIX string. ARM 1’s ' +
        '"does not blame the recording" would pass against the very defect it guards.',
    );
    return 1;
  }
  ok('positive control: it FIRES on the pre-fix "audio file may be corrupt" copy');
  if (BLAMES_THE_RECORDING.test(FIXED_REASON_SAMPLE)) {
    bad(
      'the copy matcher fires on the FIXED copy — it is matching a bare token again ' +
        '("re-uploading will not help" contains "re-upload"). It would go red for success.',
    );
    return 1;
  }
  ok('negative control: it stays quiet on the fixed copy, whose text still contains "re-upload"');

  const queue = getTranscribeMdQueue();

  // ── FIXTURE ──────────────────────────────────────────────────────────────
  // A DEDICATED practice, deliberately. Funding `clinic_main` would change the
  // admission behaviour of every other QA suite's visits for as long as the row
  // exists — and on an append-only table that is forever. The blast radius of
  // this proof is one practice nothing else references.
  section('FIXTURE — a practice of its own, so the grant funds nothing else');
  const practice = await prisma.practice.create({
    data: { name: `B8 proof (${RUN_TAG})`, slug: `b8-proof-${RUN_TAG}` },
    select: { id: true, slug: true },
  });
  ok(`practice ${practice.id} (${practice.slug})`);

  const user = await prisma.user.create({
    data: {
      email: `${RUN_TAG}@b8-proof.invalid`,
      // Never used — this proof never authenticates. A literal, not a hash of
      // anything, so nothing here resembles a credential.
      passwordHash: 'not-a-credential-this-account-cannot-log-in',
      // ⚠️ TWO DIFFERENT ROLE COLUMNS, AND ONLY ONE OF THEM SATISFIES THE
      // CHECK. `role` is `UserRole` (DOCTOR/STAFF/ADMIN/SUPER_ADMIN) — the
      // product-level role. T6's `users_active_member_has_practice_role` reads
      //
      //     isActive = false OR practiceId IS NULL OR "practiceRole" IS NOT NULL
      //
      // which is `PracticeRole` (OWNER/CLINICIAN/TECH), a different column
      // entirely. Setting `role` alone leaves the CHECK unsatisfied and the
      // insert is refused by the database naming a constraint whose message
      // does not distinguish the two — read from `pg_constraint`, not assumed.
      role: 'DOCTOR',
      practiceRole: 'OWNER',
      isActive: true,
      practiceId: practice.id,
    },
    select: { id: true },
  });
  ok(`user ${user.id}`);

  const patient = await prisma.transcribeMdPatient.create({
    data: { practiceId: practice.id, name: `B8 Proof Patient ${RUN_TAG}` },
    select: { id: true },
  });
  ok(`patient ${patient.id}`);

  // ── INSTRUMENT CONTROL ───────────────────────────────────────────────────
  // Before either arm: does the reader discriminate at all? A reader that
  // always said "zero" would make the REFUSAL arm pass perfectly and mean
  // nothing. This is the pre-half of the pair; the post-half runs after the
  // grant, and only the two together prove the instrument moves.
  section('INSTRUMENT — the balance reader, before any money');
  const emptyRead = await readPracticeBalance(practice.id);
  console.log(`   read: ${j(emptyRead)}`);
  if (!emptyRead.ok) {
    unknown(`the reader could not establish a balance on an EMPTY practice: ${emptyRead.reason}`);
    return 2;
  }
  if (emptyRead.spendableMicroUsd !== 0n) {
    bad(`a practice created moments ago reports spendable ${emptyRead.spendableMicroUsd} — expected 0`);
    return 1;
  }
  ok('an empty practice reads spendable=0, and reads it as a FACT (ok:true), not a failure');
  const emptyDecision = decideAdmission(emptyRead);
  console.log(`   decision: ${j(emptyDecision)}`);
  if (emptyDecision.admit) {
    bad('decideAdmission ADMITTED a practice with no money — the seam is fail-open');
    return 1;
  }
  ok(`decideAdmission refuses in-process with reason=${emptyDecision.reason}`);

  // ══ ARM 1 — THE REFUSAL, THROUGH THE REAL WORKER ═════════════════════════
  section('ARM 1 — an UNFUNDED practice: the block must block the work');
  const refusedVisitId = await createWalkableVisit({
    prisma,
    userId: user.id,
    practiceId: practice.id,
    patientId: patient.id,
    label: `${RUN_TAG}-arm1-unfunded`,
  });
  ok(`visit ${refusedVisitId} created QUEUED`);

  await queue.add(JOB_PROCESS_VISIT, { visitId: refusedVisitId, userId: user.id });
  ok(`enqueued ${JOB_PROCESS_VISIT} on the real queue — the worker owns it now`);

  const refused = await waitForTerminal(prisma, refusedVisitId);
  console.log(`   terminal after ${Math.round(refused.elapsedMs / 1000)}s: status=${refused.status} ` +
    `category=${j(refused.failureCategory)} processingStartedAt=${j(refused.processingStartedAt)}`);
  console.log(`   reviewReason: ${j(refused.reviewReason)}`);

  if (refused.timedOut) {
    unknown(`ARM 1 never reached a terminal state (stuck at ${refused.status}) — cannot tell`);
  } else if (refused.status !== 'FAILED') {
    bad(`ARM 1: an UNFUNDED practice reached ${refused.status}. The block did not block.`);
  } else {
    ok('ARM 1: the visit landed FAILED');

    // The category, which is what RELAY's wording asks for by name.
    if (refused.failureCategory !== 'permanent') {
      bad(
        `ARM 1: failureCategory=${j(refused.failureCategory)}, expected "permanent" — ` +
          'an empty wallet cannot be fixed by retrying, and a `transient` here would ' +
          'burn the whole BullMQ attempt budget against a refusal that cannot change',
      );
    } else {
      ok('ARM 1: failureCategory=permanent — a retry cannot change an empty wallet');
    }

    // THE STRUCTURAL DISCRIMINATOR. See the header: nothing that fails after
    // admission can leave this column NULL.
    if (refused.processingStartedAt !== null) {
      bad(
        'ARM 1: processingStartedAt IS SET, so the visit got PAST admission and died later. ' +
          'Whatever failed, it was not the money gate — this arm proves nothing about B8.',
      );
    } else {
      ok('ARM 1: processingStartedAt IS NULL — it died AT admission, before the pipeline started');
    }

    // ── WHAT THE DOCTOR IS TOLD ──────────────────────────────────────────
    // ⚠️ THIS ASSERTION EXISTS BECAUSE THE FIRST RUN OF THIS HARNESS FOUND THE
    // OPPOSITE. `buildUserFacingFailureReason` had no billing branch, so a
    // refusal at layer 'init' with category 'permanent' produced "The audio
    // file may be corrupt or in an unsupported format — please re-upload to
    // try again", and `visit-failed-view.tsx:130` renders that string to the
    // doctor. Re-uploading cannot fix an empty wallet; it costs the work again
    // and fails identically.
    //
    // Both directions are checked. The negative arm is the load-bearing one:
    // it is possible to add a truthful sentence and leave the misleading one
    // in place, and only an explicit "does NOT say" can see that.
    const reason = refused.reviewReason ?? '';
    if (BLAMES_THE_RECORDING.test(reason)) {
      bad(
        'ARM 1: the doctor is told the AUDIO is at fault. The wallet is empty and the ' +
          'recording is fine — re-uploading fails identically and costs the work again.',
      );
    } else {
      ok('ARM 1: the reason does NOT blame the recording');
    }
    if (!/out of processing credit/i.test(reason)) {
      bad(`ARM 1: the reason never names the actual cause. It says: ${j(reason)}`);
    } else {
      ok('ARM 1: the reason names the credit, and says re-uploading will not help');
    }
  }

  // ══ ARM 2 — THE GRANT, AND THE SAME VISIT ADMITTED ═══════════════════════
  section('ARM 2 — fund the wallet; the ONLY fact that changes between the arms');
  const grant = await grantPromoCredit(practice.id);
  console.log(`   grant: ${j(grant)}`);
  if (!grant.granted) {
    unknown(`the grant did not write on a practice created moments ago: ${grant.reason}`);
    return 2;
  }
  ok(`grant row ${grant.ledgerEntryId} — ${grant.amountMicroUsd} micro-USD into promo`);

  // The post-half of the instrument control. The reader said 0 before and must
  // now say 10_000_000: it MOVES, so its zero was an observation and not a
  // constant.
  const fundedRead = await readPracticeBalance(practice.id);
  console.log(`   read: ${j(fundedRead)}`);
  if (!fundedRead.ok) {
    unknown(`the reader could not establish a balance after the grant: ${fundedRead.reason}`);
    return 2;
  }
  if (fundedRead.spendableMicroUsd !== PROMO_GRANT_MICRO_USD) {
    bad(
      `after a ${PROMO_GRANT_MICRO_USD} grant the spendable balance reads ` +
        `${fundedRead.spendableMicroUsd}. Either the draw order does not include promo ` +
        '(ruling #96) or the derive trigger disagrees with the sum.',
    );
  } else {
    ok(
      `spendable moved 0 → ${fundedRead.spendableMicroUsd} — the reader DISCRIMINATES, ` +
        'so ARM 1’s zero was a measurement',
    );
  }

  const fundedDecision = decideAdmission(fundedRead);
  console.log(`   decision: ${j(fundedDecision)}`);
  if (!fundedDecision.admit) {
    bad(`decideAdmission still refuses a funded practice: ${j(fundedDecision)}`);
  } else {
    ok('decideAdmission admits — promo is spendable, which is ruling #96 in effect');
  }

  const admittedVisitId = await createWalkableVisit({
    prisma,
    userId: user.id,
    practiceId: practice.id,
    patientId: patient.id,
    label: `${RUN_TAG}-arm2-funded`,
  });
  ok(`visit ${admittedVisitId} created QUEUED — same shape, same function, same fixture`);

  await queue.add(JOB_PROCESS_VISIT, { visitId: admittedVisitId, userId: user.id });
  const admitted = await waitForTerminal(prisma, admittedVisitId);
  console.log(`   terminal after ${Math.round(admitted.elapsedMs / 1000)}s: status=${admitted.status} ` +
    `category=${j(admitted.failureCategory)} processingStartedAt=${j(admitted.processingStartedAt)}`);
  console.log(`   reviewReason: ${j(admitted.reviewReason)}`);

  if (admitted.timedOut) {
    unknown(`ARM 2 never reached a terminal state (stuck at ${admitted.status}) — cannot tell`);
  } else if (admitted.processingStartedAt === null) {
    bad(
      'ARM 2: processingStartedAt IS NULL — a FUNDED practice was still refused at admission. ' +
        'The grant did not fund the wallet admission reads.',
    );
  } else {
    ok('ARM 2: processingStartedAt is set — admission ADMITTED, and the pipeline ran');

    if (admitted.status === 'READY') {
      ok('ARM 2: the visit reached READY');
      // ⚠️ THE CLAIM THIS ARM MAKES THAT NOTHING ELSE CAN.
      // `commitVisitCharge` is prod-only (ruling 90(c)), so on QA the debit
      // THROWS and `chargeVisitUsage` absorbs it as `charged: 'failed'`. The
      // visit being READY anyway is `billing-pipeline.ts`'s central promise
      // observed rather than asserted: "no billing failure is worth a clinical
      // outcome". A unit test can only stub that; here the real writer really
      // refused and the real note really survived.
      ok(
        'ARM 2: READY DESPITE the debit being unable to run (prod-only, ruling 90(c)) — ' +
          '"no billing failure is worth a clinical outcome", observed',
      );
    } else {
      unknown(
        `ARM 2: got past admission but ended ${admitted.status} ` +
          `(${j(admitted.reviewReason)}). Admission is proven; the rest of the ` +
          'pipeline failed for an unrelated reason — cannot tell about the full walk.',
      );
    }
  }

  // ══ ARM 3 — IDEMPOTENCY ══════════════════════════════════════════════════
  section('ARM 3 — the grant key refuses a second grant');
  const second = await grantPromoCredit(practice.id);
  console.log(`   second grant: ${j(second)}`);
  if (second.granted) {
    bad(
      'a SECOND grant was written for the same practice. On an append-only table a ' +
        'double grant can only be offset by an `adjustment`, never removed.',
    );
  } else {
    ok(`refused with reason=${second.reason} — the global unique on idempotencyKey held`);
  }
  const rowCount = await prisma.ledgerEntry.count({ where: { practiceId: practice.id } });
  if (rowCount !== 1) {
    bad(`the practice holds ${rowCount} ledger rows after two grant calls — expected exactly 1`);
  } else {
    ok('exactly 1 ledger row for the practice');
  }

  // ── REPORT ───────────────────────────────────────────────────────────────
  section('WHAT THIS RUN CREATED (synthetic, QA-only, left in place)');
  console.log(`   practice ${practice.id} · user ${user.id} · patient ${patient.id}`);
  console.log(`   visits   ${refusedVisitId} (refused) · ${admittedVisitId} (admitted)`);
  console.log(`   ledger   ${grant.ledgerEntryId} — 1 promo grant row`);

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
  console.log('\u{1F7E2} B8 IS PROVEN ON QA, BOTH DIRECTIONS, THROUGH THE REAL WORKER.');
  console.log('   unfunded → FAILED/permanent, never started · funded → admitted, READY');
  return 0;
}

main().then(
  (code) => process.exit(code),
  (err) => {
    console.error('\u{1F7E1} harness error — cannot tell:', err);
    process.exit(2);
  },
);
