// ============================================================================
// B1-b STEP 4 — the sanctioned production sizing smoke.
// ----------------------------------------------------------------------------
// Ruled 2026-08-09 (RULINGS.md, "The sizing data is GENERATED, not awaited").
// ONE visit on the SYNTHETIC account drives real vendor calls through the live
// meter and discharges three owed items: 1b's sizing (how often a real vendor
// call yields no request id), "the meter is unproven in production", and B1-a's
// capture proven on a live call.
//
// Run it from inside the compose network so the env is injected and the service
// names resolve — never by exporting secrets into a shell:
//
//   docker compose run --rm --no-deps --entrypoint sh -v /opt/meddoc-pro:/src \
//     transcribe-md -c "cd /src && node_modules/.bin/tsx \
//     apps/transcribe-md/scripts/prod-smoke/b1b-sizing-smoke.ts"
//
// ── WHY THIS IS NOT `cross-input-mode/runner.ts` ──────────────────────────────
// That runner is the obvious thing to reach for and it is the WRONG thing, on
// two independent counts, either of which is disqualifying:
//
//   1. It calls `assertNonProdDatabase()` — it refuses to run here by design.
//   2. It hardcodes a REAL DOCTOR'S `USER_ID` / `PRACTICE_ID` (the Kasra solo
//      practice). Pointing it at production would put synthetic visits in a real
//      clinician's chart list — the exact thing the smoke fixture exists to make
//      unnecessary, and a hard stop in AGENTS.md.
//
// This script is deliberately NOT guarded by `assertNonProdDatabase()` — like
// provision.ts and clean.ts, prod is its whole point. The guard is SCOPE, not
// target: every write is keyed to the fixture resolved from smoke-account.ts,
// and `assertIsSmokeFixture` checks email AND practice slug before anything.
//
// ⚠️ IT REFUSES TO RUN IF THE FIXTURE IS NOT AT BASELINE. The ruling says ONE
// clean smoke; a second visit on top of a first would blend two samples into a
// per-purpose figure that no longer describes either. Clean with clean.ts first.
//
// ⚠️ A CALL MADE WITH A WRONG `practiceId` SPENDS REAL MONEY AND WRITES NEITHER
// TELEMETRY ROW — both writes swallow their own errors. That is why the ids are
// resolved from the database by email/slug and never typed in.
// ============================================================================

import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { prisma } from '@meddoc/db';

import { enqueueProcessVisit } from '../../src/lib/queue';
import { putAudioStream } from '../../src/lib/minio';
import { SMOKE_EMAIL, SMOKE_PRACTICE_SLUG, assertIsSmokeFixture } from './smoke-account';

/**
 * Vascular-surgery dictation, ~5 minutes. Chosen to MATCH the fixture doctor's
 * own specialty ('Vascular Surgery') — a specialty mismatch would send the
 * pipeline down a template path the doctor would never see, and the call mix is
 * the thing being measured.
 */
// ⚠️ RESOLVED RELATIVE TO THIS FILE, NEVER TO AN ABSOLUTE HOST PATH. The
// documented invocation mounts the repo at /src inside the compose network, so a
// hardcoded /opt/meddoc-pro/... does not exist at runtime — the first attempt
// failed on exactly that. It failed BEFORE any write, because this check sits
// above the first create; that ordering is deliberate and worth keeping.
// `__dirname`, not `import.meta.url`: no package.json in this repo declares
// `"type": "module"`, so tsx loads these scripts as CommonJS and `import.meta`
// would throw at parse time.
const REPO_ROOT = resolve(__dirname, '../../../..');
const AUDIO_PATH =
  process.env.B1B_SMOKE_AUDIO?.trim() ||
  resolve(REPO_ROOT, '.local/cross-input-mode-audio/VS1.mp3');
const SPECIALTY = 'vascular-surgery';
const PATIENT_NAME = 'B1b Sizing Smoke Patient (synthetic)';
const CHIEF_COMPLAINT = 'TIA with carotid stenosis — B1-b sizing smoke';

/** Terminal states. FAILED is terminal too: a failed run still produced calls. */
const TERMINAL = new Set(['READY', 'FAILED', 'SIGNED']);
const POLL_INTERVAL_MS = 10_000;
const POLL_TIMEOUT_MS = 15 * 60_000;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function main() {
  // ── 1. Resolve the fixture, and prove it is the fixture ────────────────────
  const user = await prisma.user.findUnique({
    where: { email: SMOKE_EMAIL },
    include: { practice: { select: { id: true, slug: true } } },
  });
  if (!user || !user.practice) {
    throw new Error('[b1b-smoke] smoke fixture not found — run provision.ts first.');
  }
  assertIsSmokeFixture({ email: user.email, practice: { slug: user.practice.slug } });
  if (user.practice.slug !== SMOKE_PRACTICE_SLUG) {
    throw new Error('[b1b-smoke] resolved user is not in the smoke practice — aborting.');
  }
  const practiceId = user.practice.id;
  console.log(`[b1b-smoke] fixture user=${user.id} practice=${practiceId}`);

  // ── 2. Refuse unless at baseline. ONE clean smoke means one. ───────────────
  const existingVisits = await prisma.transcribeVisit.count({ where: { practiceId } });
  const existingPatients = await prisma.transcribeMdPatient.count({ where: { practiceId } });
  if (existingVisits > 0 || existingPatients > 0) {
    throw new Error(
      `[b1b-smoke] fixture is NOT at baseline (patients=${existingPatients} visits=${existingVisits}). ` +
        'Run clean.ts first — a second visit would blend two samples into one figure.'
    );
  }

  // ── 3. Abort guard: the real clinicians' counts, before any write. ─────────
  // Re-derived here rather than trusted from the declaration, per the standing
  // rule for owner-ruled production writes.
  const before = {
    patients: await prisma.transcribeMdPatient.count({ where: { NOT: { practiceId } } }),
    visits: await prisma.transcribeVisit.count({ where: { NOT: { practiceId } } }),
    signed: await prisma.transcribeVisit.count({
      where: { NOT: { practiceId }, signedAt: { not: null } },
    }),
  };
  console.log(
    `[b1b-smoke] non-smoke baseline patients=${before.patients} visits=${before.visits} signed=${before.signed}`
  );

  if (!existsSync(AUDIO_PATH)) {
    throw new Error(`[b1b-smoke] audio fixture missing at ${AUDIO_PATH}`);
  }

  // ── 4. Create the patient and the visit, both practice-scoped ─────────────
  const patient = await prisma.transcribeMdPatient.create({
    data: { practiceId, name: PATIENT_NAME },
    select: { id: true },
  });
  console.log(`[b1b-smoke] patient=${patient.id}`);

  // `data` is typed loosely by the client, so tsc cannot enforce the required
  // columns here — T3's practiceId and T4's createdBy are verified by reading.
  const visit = await prisma.transcribeVisit.create({
    data: {
      userId: user.id,
      createdBy: user.id,
      practiceId,
      patientId: patient.id,
      patientName: PATIENT_NAME,
      specialty: SPECIALTY,
      chiefComplaint: CHIEF_COMPLAINT,
      inputMode: 'audio_upload',
      interpreterMode: false,
      status: 'QUEUED',
    } as never,
    select: { id: true },
  });
  console.log(`[b1b-smoke] visit=${visit.id}`);

  // ── 5. Upload the audio, then enqueue ─────────────────────────────────────
  const buf = readFileSync(AUDIO_PATH);
  const audioKey = `${user.id}/${visit.id}/b1b-smoke.mp3`;
  await putAudioStream(audioKey, buf, buf.byteLength, 'audio/mpeg');
  await prisma.transcribeVisit.update({
    where: { id: visit.id },
    data: {
      audioKey,
      audioMimeType: 'audio/mpeg',
      audioSizeBytes: buf.byteLength,
      audioUploadedAt: new Date(),
    },
  });
  console.log(`[b1b-smoke] audio uploaded (${buf.byteLength} bytes) key=${audioKey}`);

  await enqueueProcessVisit(visit.id, user.id);
  console.log('[b1b-smoke] enqueued — polling to terminal status');

  // ── 6. Poll to terminal ───────────────────────────────────────────────────
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  let status = 'QUEUED';
  while (Date.now() < deadline) {
    await sleep(POLL_INTERVAL_MS);
    const row = await prisma.transcribeVisit.findUnique({
      where: { id: visit.id },
      select: { status: true },
    });
    status = String(row?.status ?? 'MISSING');
    const calls = await prisma.aiCall.count({ where: { visitId: visit.id } });
    console.log(`[b1b-smoke] status=${status} ai_calls=${calls}`);
    if (TERMINAL.has(status)) break;
  }

  // ── 7. Abort guard, re-checked AFTER the run ──────────────────────────────
  const after = {
    patients: await prisma.transcribeMdPatient.count({ where: { NOT: { practiceId } } }),
    visits: await prisma.transcribeVisit.count({ where: { NOT: { practiceId } } }),
    signed: await prisma.transcribeVisit.count({
      where: { NOT: { practiceId }, signedAt: { not: null } },
    }),
  };
  const moved =
    after.patients !== before.patients ||
    after.visits !== before.visits ||
    after.signed !== before.signed;
  if (moved) {
    console.error(
      `[b1b-smoke] 🔴 ABORT GUARD TRIPPED — non-smoke counts moved: ` +
        `${JSON.stringify(before)} → ${JSON.stringify(after)}`
    );
    process.exitCode = 1;
    return;
  }
  console.log('[b1b-smoke] ✅ abort guard: real clinicians\' counts unmoved');

  console.log(`[b1b-smoke] FINAL status=${status} visit=${visit.id}`);
  if (!TERMINAL.has(status)) {
    console.error('[b1b-smoke] ⚠️ did not reach a terminal status within the timeout.');
    process.exitCode = 1;
  }
}

main()
  .catch((err) => {
    console.error('[b1b-smoke] FAILED:', err);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
