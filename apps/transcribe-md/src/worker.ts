// ============================================================================
// apps/transcribe-md — BullMQ worker entrypoint (T-M4 + T-M5)
// ----------------------------------------------------------------------------
// Runs as a separate container (transcribe-md-worker). Pulls jobs off the
// shared `transcribe-md` queue and drives each visit through the pipeline.
//
// Pipeline branches by visit.inputMode:
//   audio_upload    → L1 (diarize) + L2 + L3 (conversation) + L4 + L5 + L6
//   voice_dictation → L1' (single-speaker) + L3 (dictation) + L4 + L5 + L6
//   text_notes      →                         L3 (text)     + L4 + L5 + L6
//
// Layers 4-6 are mode-agnostic: they consume (entities, contextText) and
// produce SOAP draft → critique → polish. That uniformity is the point —
// the doctor gets the same output quality regardless of input shape.
// ============================================================================

import 'dotenv/config';
// T-M16.3: init @sentry/node via side-effect import BEFORE any layer
// code runs. An early throw in Prisma / Redis init still flows to
// Sentry via global exception handlers.
import './worker-sentry';
import { captureWorkerException } from './worker-sentry';
import { Worker, type Job } from 'bullmq';
import prisma, { Prisma } from '@meddoc/db';
import { evidenceAnchorsEnabled } from './worker/evidence-anchors-flag';
import { ANCHOR_GENERATION_ADDENDUM } from './worker/layers/04b-anchor-verify';
import { TranscribeVisitStatus } from '@prisma/client';
import type { DeepgramBatchResponse, DeepgramUtterance } from '@meddoc/ai';
import { redactPhi } from '@meddoc/ai';
// B8 step 2 — the money seam. Both are no-ops unless `BILLING_ENFORCED=true`;
// see `billing-pipeline.ts` for why it ships off and what turns it on.
// B8 step 3 — `observeFailedVisitUsage` is the odd one out and is NOT flagged:
// it writes nothing anywhere, and it exists to inform the decision to enable
// the flag. See its header.
import {
  admitVisitOrThrow,
  chargeVisitUsage,
  observeFailedVisitUsage,
  type FailedVisitObservation,
} from '@meddoc/ai';
import { log } from '@/lib/log';
import {
  shouldDeadLetter,
  shouldDiscardPermanentJob,
  shouldMarkVisitFailed,
  shouldObserveFailureCost,
} from './worker/retry-decision';
import {
  asUnrecoverable,
  isUnrecoverableMarker,
} from './worker/unrecoverable';
import {
  categorizeError,
  type ErrorCategory,
} from './worker/error-categorize';
import { loadResumeState, VisitNotFoundError } from './worker/resume-state';
import { persistFailedState } from './worker/persist-failed';
import { sanitizeConfidenceScores } from './worker/confidence-scores';
import { notifyAdminOnFailure } from './lib/admin-notifications';

import {
  QUEUE_NAME,
  JOB_PROCESS_VISIT,
  CLEANUP_QUEUE_NAME,
  JOB_MINIO_ORPHAN_CLEANUP,
  JOB_STALE_VISIT_CLEANUP,
  JOB_RETENTION_SWEEP,
  JOB_STUCK_VISIT_WATCHDOG,
  JOB_AUTO_CERTIFY_TWIN,
  enqueueDlq,
  getSharedRedisConnection,
  getCleanupQueue,
  type ProcessVisitPayload,
} from '@/lib/queue';
import { ensureBucket } from '@/lib/minio';
import { runMinioOrphanCleanup } from '@/worker/cleanup/minio-orphans';
import { runStaleVisitCleanup } from '@/worker/cleanup/stale-visits';
import {
  runRetentionSweep,
  resolveRetentionDays,
} from '@/worker/cleanup/retention-sweep';
import { applyAdditiveReviewState } from '@/worker/finalize-review-state';
import { countUnclearMarkers } from '@/worker/layers/transcript-clarity';
import { runStuckVisitWatchdog } from '@/worker/cleanup/stuck-visit-watchdog';
import { recordCleanupHeartbeat } from '@/lib/cleanup-heartbeat';
import {
  isLayerComplete,
  logSkipSummary,
  logSkippedLayer,
  type PipelineLayer,
} from '@/worker/layer-skip';
import { runLayer1Transcribe } from '@/worker/layers/01-transcribe';
import { runLayer1bTranscribeDictation } from '@/worker/layers/01b-transcribe-dictation';
import {
  assertSufficientTranscript,
  isPipelineRejectError,
} from '@/worker/layers/guards';
import {
  runLayer2SpeakerRoles,
  type SpeakerMap,
} from '@/worker/layers/02-speaker-roles';
import {
  runLayer3ExtractEntities,
  buildRoleLabeledTranscript,
  type ExtractedEntities,
} from '@/worker/layers/03-extract-entities';
import { runLayer4GenerateSoap } from '@/worker/layers/04-generate-soap';
import { runLayer5SelfCritique } from '@/worker/layers/05-self-critique';
import type { AudioConfidenceStats } from '@/worker/layers/audio-confidence';
import { runLayer6Polish } from '@/worker/layers/06-polish';
import { resolveActiveTemplate } from '@/worker/note-templates/resolve-active-template';
import { imagingReportBuilderFor } from '@/worker/note-templates/imaging-report-builders';
import { runTemplateTwinFillStep } from '@/worker/template-twin-fill-step';
import {
  normalizeTemplate,
  type ResolvedNoteTemplate,
} from '@/worker/note-templates/build-soap-prompt';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from '@/worker/note-templates/system-default-template';
import { detectTemplateFallback } from '@/worker/note-templates/detect-template-fallback';
import { runLayer7aIcdCoding } from '@/worker/layers/07a-icd-coding';
import { runLayer7bCptCoding } from '@/worker/layers/07b-cpt-coding';
import { runLayer7cRxDrafting } from '@/worker/layers/07c-rx-drafting';
import { runLayer7dReferrals } from '@/worker/layers/07d-referrals';
import { runLayer7ePatientSummary } from '@/worker/layers/07e-patient-summary';
import { logAudit } from '@/lib/audit';
import {
  detectIncompleteAutomation,
  type AutomationConfidenceScores,
} from '@/worker/automation-incomplete';
import { isImagingReportSpecialty } from '@meddoc/shared/specialties';
import { emAppliesToVisit } from '@/lib/note-shape';

const CONCURRENCY = Number.parseInt(
  process.env.TRANSCRIBE_MD_WORKER_CONCURRENCY ?? '2',
  10
);

/** T-M11 — hard cap per job attempt. Typical pipeline completes in
 *  3-5 min; a 45-min recording comfortably fits under 15. Anything
 *  past that is a genuine hang (stuck fetch, deadlocked query) and
 *  should fail-fast rather than occupy a worker slot indefinitely.
 *  The layer promises keep resolving in the background after timeout
 *  — their writes land on an already-FAILED row, which is harmless.
 *  Configurable via env so ops can tune without redeploy. */
// 2026-05-12 stuck-visit fix: bumped from 15 min → 20 min so the per-
// minute watchdog (15-min threshold) catches a stuck visit FIRST and
// transitions it to FAILED with a clear reviewReason. BullMQ's
// JOB_TIMEOUT_MS is now the belt-and-braces backstop, hitting only on
// a worker too wedged to be touched by the DB-side sweep.
const JOB_TIMEOUT_MS = Number.parseInt(
  process.env.TRANSCRIBE_MD_JOB_TIMEOUT_MS ?? String(20 * 60 * 1000),
  10
);

// T-M12 — cleanup config. All three env vars default to "off" /
// "30-day retention" / "Sunday 3am UTC" / "dry-run yes" so a fresh
// deploy doesn't start deleting anything until ops explicitly opts in.
const CLEANUP_ENABLED =
  process.env.MINIO_ORPHAN_CLEANUP_ENABLED === 'true';
const CLEANUP_DRY_RUN =
  (process.env.MINIO_ORPHAN_CLEANUP_DRY_RUN ?? 'true').toLowerCase() !==
  'false';
const CLEANUP_RETENTION_DAYS = Number.parseInt(
  process.env.MINIO_ORPHAN_CLEANUP_RETENTION_DAYS ?? '30',
  10
);
const CLEANUP_CRON =
  process.env.MINIO_ORPHAN_CLEANUP_CRON?.trim() || '0 3 * * 0';
// 5 min ceiling on the sweep itself. A cleanly-run sweep on our
// current bucket size takes seconds; 5 min gives head-room for a
// high-object-count bucket and auto-fails a hung MinIO connection.
const CLEANUP_TIMEOUT_MS = 5 * 60 * 1000;

// T-M17.3 — stale visit cleanup (abandoned QUEUED + expired trash).
// Defaults to enabled; flip STALE_VISIT_CLEANUP_ENABLED=false to
// keep the worker alive without the sweep. Cron defaults to daily
// at 3am UTC, which offsets from the weekly MinIO sweep so the two
// don't fight for DB connections.
const STALE_VISIT_CLEANUP_ENABLED =
  (process.env.STALE_VISIT_CLEANUP_ENABLED ?? 'true').toLowerCase() !==
  'false';
const STALE_VISIT_CLEANUP_CRON =
  process.env.STALE_VISIT_CLEANUP_CRON?.trim() || '0 3 * * *';
const STALE_VISIT_CLEANUP_TIMEOUT_MS = 5 * 60 * 1000;

// T-M18.1 A3 — audio retention sweep (SIGNED visits past the audio
// retention window; default 90d — see retention-sweep.ts).
// Opt-out via env. Cron offset 1h from the T-M17.3 stale-visit sweep
// so the two don't contend for DB + MinIO connections.
const RETENTION_SWEEP_ENABLED =
  (process.env.RETENTION_SWEEP_ENABLED ?? 'true').toLowerCase() !== 'false';
const RETENTION_SWEEP_CRON =
  process.env.RETENTION_SWEEP_CRON?.trim() || '0 4 * * *';
const RETENTION_SWEEP_TIMEOUT_MS = 10 * 60 * 1000;

// 2026-05-12 stuck-visit watchdog. Runs every minute by default so a
// pipeline stall is caught within ~1 min of crossing the threshold.
// Default cron `* * * * *` = every minute UTC.
// Default opt-IN (the failure mode it catches is silent + serious —
// visits stuck at status=POLISHING/etc for hours). Flip
// STUCK_VISIT_WATCHDOG_ENABLED=false to disable in dev environments
// where intentional long sleeps are common.
const STUCK_VISIT_WATCHDOG_ENABLED =
  (process.env.STUCK_VISIT_WATCHDOG_ENABLED ?? 'true').toLowerCase() !== 'false';
const STUCK_VISIT_WATCHDOG_CRON =
  process.env.STUCK_VISIT_WATCHDOG_CRON?.trim() || '* * * * *';
const STUCK_VISIT_WATCHDOG_TIMEOUT_MS = 60_000;
/** RULING #127 — auto-certification's budget.
 *
 * ⚠️ MINUTES, NOT SECONDS, AND DELIBERATELY. The round-trip proof runs an
 * ephemeral visit through the real L4 and the real bridge fill — a live model
 * generation. The sweeps above are database work measured in seconds; this is
 * not, and giving it a sweep-sized budget would time out every certification on
 * a large form and report it as a failure the doctor cannot act on.
 *
 * The bound still exists: a generation that hangs must not hold a worker
 * forever. On timeout the template stays NEEDS_CONFIRMATION, which is a state
 * the banner names and the manual screen resolves. */
const AUTO_CERTIFY_TIMEOUT_MS = 8 * 60_000;

function withTimeout<T>(p: Promise<T>, ms: number, tag: string): Promise<T> {
  return Promise.race([
    p,
    new Promise<never>((_, reject) =>
      setTimeout(
        () =>
          reject(
            new Error(
              `${tag} exceeded ${ms}ms hard cap — fail-fast, retry per BullMQ attempts`
            )
          ),
        ms
      )
    ),
  ]);
}

/** Null-out the persisted column for a failed automation layer so a
 *  partially-written row can't mislead the UI. Each L7x layer writes
 *  its own column inside the fulfilled path; if the call threw (e.g.
 *  schema-fail after a Prisma write already landed — vanishingly rare
 *  but possible), this wipes the column clean. */
async function clearAutomationColumn(
  visitId: string,
  key:
    | 'icd_coding'
    | 'cpt_coding'
    | 'rx_drafting'
    | 'referrals'
    | 'patient_summary'
): Promise<void> {
  const map: Record<typeof key, Record<string, null>> = {
    icd_coding: { icdCodes: null },
    cpt_coding: { cptCodes: null },
    rx_drafting: { rxDrafts: null },
    referrals: { referrals: null },
    patient_summary: { patientSummary: null },
  };
  await prisma.transcribeVisit.update({
    where: { id: visitId },
    data: map[key],
  });
}

// T-M13 / FIND-P1-011 — `loadResumeState` was extracted to
// `./worker/resume-state.ts` so it could be unit-tested for the
// "visit deleted during retry" race (worker.ts has module-level side
// effects — Worker creation, Redis connect, Sentry init — which make
// it un-importable from tests).

/** Does the review lane currently hold anything?
 *
 *  Read FRESH and with the column named explicitly — see the call site. */
async function laneHasSuggestions(visitId: string): Promise<boolean> {
  const row = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: { suggestedClaims: true },
  });
  const claims = row?.suggestedClaims;
  return Array.isArray(claims) && claims.length > 0;
}

/** Runtime proof that a value may be handed to a Prisma `Json` column.
 *
 *  F-TYPE 2026-08-07. `sanitizeConfidenceScores` already GUARANTEES this — it
 *  returns the output of a `JSON.parse(JSON.stringify(...))` round-trip, or
 *  null (FIND-P1-012). Its TYPE cannot say so: `LayerStatus.metadata` is
 *  `z.unknown()`, and `unknown` is not assignable to `Prisma.InputJsonValue`.
 *
 *  So the fact is re-established by CHECKING rather than by asserting it away
 *  with a cast — a cast here would restore exactly the silence the typed
 *  Prisma client was introduced to remove. The false branch is unreachable
 *  under the sanitizer's contract; should that contract ever drift, this
 *  degrades the same way a sanitizer null already does (warn + write JSON
 *  null) instead of throwing at the database.
 *
 *  ⚠️ This helper is a SCOPE WORKAROUND, not the preferred fix. The right
 *  repair is to narrow `metadata` in `worker/confidence-scores.ts` from
 *  `z.unknown()` to a JSON schema, at which point delete this and assign
 *  `safeConfidenceScores` directly. */
function isJsonInput(value: unknown): value is Prisma.InputJsonValue {
  if (value === null) return false;
  if (typeof value === 'string') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (typeof value === 'boolean') return true;
  if (typeof value !== 'object') return false;
  // `Object.values` on a bare object widens to unknown[] without a cast.
  const members: unknown[] = Array.isArray(value) ? value : Object.values(value);
  return members.every(
    (m) => m === null || m === undefined || isJsonInput(m)
  );
}

async function processVisit(job: Job<ProcessVisitPayload>): Promise<void> {
  const { visitId } = job.data;

  // T-M16.3: tracks which pipeline layer is currently running. Updated
  // right before each `await runLayerX(...)` call so the outer catch
  // block can tag the Sentry event with an accurate `layer` value.
  // Values mirror the PipelineLayer enum in layer-skip.ts ('L1', 'L1b',
  // 'L2', 'L3', 'L4', 'L5', 'L6', 'automation') plus 'init'/'finalize'
  // bookends.
  let currentLayer: string = 'init';

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      audioKey: true,
      audioMimeType: true,
      dictationAudioKey: true,
      rawTextInput: true,
      specialty: true,
      inputMode: true,
      interpreterMode: true,
      // F-TYPE 2026-08-07 — LATENT BUG, fixed. `createdAt` was READ at the
      // Template Twin fill step below (`visitDate: visit.createdAt`) but was
      // never SELECTED here, so the property was `undefined` at runtime. The
      // parameter is optional (`visitDate?: Date | string | null`), so nothing
      // threw: `visitDateToIso(undefined)` returns null and the DATE OF
      // PROCEDURE control was silently left blank on every worker-produced
      // fill manifest. Untyped Prisma is why it was invisible.
      createdAt: true,
      // Per-visit template pick (req: end template×dictation collisions). When a
      // doctor chose a specific format on the new-visit form, it is written here
      // at create time and HONORED below over active-template resolution. NULL for
      // the default ("auto") path → resolveActiveTemplate as before.
      noteTemplateId: true,
      // ⚠️ #287 — THE VISIT'S OWN TENANT, WHICH IS NOT `user.practiceId`.
      // `practiceId` at :366 below is bound from `visit.user.practiceId` —
      // the AUTHOR's practice — and feeds ~25 sites in this pipeline. On a
      // locum visit (B seeing A's patient) those differ, and the schema
      // comment on `TranscribeVisit.practiceId` says which one owns the
      // chart: A. The Template Twin fill step is re-pointed at this column;
      // the rest of the pipeline is NOT, because it reaches admission and
      // billing and that is an owner call, not a rename.
      practiceId: true,
      user: { select: { practiceId: true } },
      // Fix-Pack 1 Q0-2 / audit Finding 01.1 — pull patient demographic
      // + safety context for L7c pediatric framing. Round 3 PR-D added
      // weightKg + allergies to TranscribeMdPatient; the FK is
      // NOT NULL since T-M17.2 so this select always populates.
      patient: {
        select: {
          dateOfBirth: true,
          weightKg: true,
          allergies: true,
        },
      },
    },
  });
  if (!visit) throw new Error(`Visit ${visitId} not found`);

  const practiceId = visit.user.practiceId;
  const startedAt = new Date();

  // Per-mode input validation. Keeps the branch bodies below simple.
  if (visit.inputMode === 'audio_upload') {
    if (!visit.audioKey)
      throw new Error(`Visit ${visitId} has no audioKey (audio_upload mode).`);
    if (!visit.audioMimeType)
      throw new Error(`Visit ${visitId} has no audioMimeType.`);
  } else if (visit.inputMode === 'voice_dictation') {
    if (!visit.dictationAudioKey)
      throw new Error(`Visit ${visitId} has no dictationAudioKey.`);
  } else if (visit.inputMode === 'text_notes') {
    if (!visit.rawTextInput?.trim())
      throw new Error(`Visit ${visitId} has no rawTextInput.`);
  } else {
    throw new Error(`Unknown inputMode: ${visit.inputMode}`);
  }

  // ── B8 step 2 — ADMISSION ────────────────────────────────────────────────
  // SPEC §2.4: "insufficient balance blocks the work; if the balance cannot be
  // read, block". A no-op unless `BILLING_ENFORCED=true`.
  //
  // ⚠️ PLACED AFTER INPUT VALIDATION AND BEFORE THE FIRST VENDOR CALL, AND BOTH
  // HALVES OF THAT ARE DELIBERATE. After validation, so a visit with no audio
  // key fails naming the missing audio rather than the wallet — the balance is
  // irrelevant to work that was never going to run. Before the status update
  // and everything below it, because the first billable call is in the
  // transcription branch a few lines down, and admission that runs after the
  // spend has not blocked anything.
  //
  // ⚠️ THE `try` OPENS HERE, ABOVE THE ADMISSION CALL, AND IT DID NOT USED TO.
  // B8 step 2 wrote at this spot: "It THROWS on refusal, so it JOINS THE
  // EXISTING CATCH BELOW: `categorizeError` reads the error's own
  // `retryCategory`, and the FAILED branch records it like any other pipeline
  // failure." Every clause of that was true about the catch and false about
  // this call — the `try` began FIFTY-THREE LINES FURTHER DOWN, so a refusal
  // unwound straight out of `processVisit` past no handler at all.
  //
  // Measured on QA 2026-08-12 with `BILLING_ENFORCED=true`, by
  // `scripts/qa/b8-admission-on-qa.ts`: the refusal fired correctly and logged
  // its exact reason three times (once per BullMQ attempt), and the visit sat
  // at **status=QUEUED, failureCategory=NULL, reviewReason=NULL** for the four
  // minutes the harness waited. Not FAILED. Not categorised. A stuck chart.
  //
  // ⚠️ WHY NOTHING CAUGHT IT: both halves were tested and both halves passed.
  // `gate-b8-pipeline-seam.test.ts` proves `admitVisitOrThrow` throws;
  // `error-categorize.test.ts` proves `categorizeError` maps the error to
  // permanent/transient. THE JOIN BETWEEN THEM WAS NEVER EXERCISED, because no
  // unit test runs `processVisit`. Ruling #96(a)'s shape for the third time in
  // this programme: two individually-correct billing steps, and the defect
  // living in the seam between them.
  //
  // ⚠️ AND THE FAILURE WAS STRICTLY WORSE THAN THE OUTAGE THE FLAG GUARDS.
  // `billing-pipeline.ts`'s header reasons about turning the flag on early as
  // "EVERY VISIT IN PRODUCTION FAILS, for every doctor, immediately" — loud,
  // diagnosable, and bounded by the flag. What actually happened is quieter and
  // worse: every refused visit hangs at QUEUED until the 15-minute stuck-visit
  // watchdog force-fails it as `transient` — filing an out-of-money refusal
  // under "server blip", which is the exact misfiling ruling 95(d) drew the
  // `balance_unreadable` distinction to prevent, and which B8 step 3's
  // auto-credit would then try to refund.
  //
  // The ordering the original comment argued for is PRESERVED: admission still
  // runs after input validation and before the status update below, so a
  // refused visit never acquires `processingStartedAt` and never claims to have
  // started. Only the handler boundary moved.
  try {
    await admitVisitOrThrow({ practiceId });

    // text_notes skips TRANSCRIBING — nothing to transcribe.
    const initialStatus =
      visit.inputMode === 'text_notes'
        ? TranscribeVisitStatus.EXTRACTING
        : TranscribeVisitStatus.TRANSCRIBING;

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: {
        status: initialStatus,
        processingStartedAt: startedAt,
        needsReview: false,
        reviewReason: null,
        // T-M13: previously cleared the five L7 columns here so a retry
        // wouldn't carry stale 'failed' entries. With per-layer resume
        // (below), successful L7 outputs are a CHECKPOINT — wiping them
        // would defeat resumability. Failed L7 layers are nulled by the
        // per-task catch (clearAutomationColumn) so the skip check
        // naturally re-runs only those. confidenceScores IS still
        // cleared because it's rebuilt from scratch in the roll-up
        // below, and stale failed entries would otherwise leak through.
        //
        // ⚠️ `Prisma.JsonNull`, NOT `Prisma.DbNull`, AND THE CHOICE WAS MEASURED
        // RATHER THAN REASONED. A bare `null` — what this line used to be — lands
        // in Postgres as the JSONB value `null`, not as SQL NULL. Determined on
        // QA by writing each variant through the client and reading back:
        //
        //     bare null        → sql_null=false  json_null=true
        //     Prisma.DbNull    → sql_null=TRUE   json_null=false
        //     Prisma.JsonNull  → sql_null=false  json_null=true   ← identical
        //
        // So `JsonNull` preserves the stored bytes exactly and `DbNull` would
        // silently change them. Production could not settle this: every visit
        // there holds a real object, because this reset is always overwritten
        // before processing ends. `DbNull` is the intuitive reading of "null"
        // and it is the wrong one.
        confidenceScores: Prisma.JsonNull,
      },
    });

    // T-M13 — load the per-layer checkpoint state BEFORE the sequential
    // stage. On attempt 1 (and after a user-triggered upload reset)
    // every column is null and the skip checks all return false, so
    // behavior matches the pre-T-M13 happy path. On BullMQ retry
    // (attempt > 1) whatever L1-L6 already succeeded is preserved in
    // columns — the checks below short-circuit those and the retry
    // resumes at the first non-populated layer.
    const attempt = job.attemptsMade + 1;
    const resumeState = await loadResumeState(visitId, job.attemptsMade);
    const skipped: PipelineLayer[] = [];

    // -------------------------------------------------------------------
    // Per-mode input stage — produces (entities, contextText).
    // -------------------------------------------------------------------
    let entities: ExtractedEntities;
    let contextText: string;
    // Round 3 quality fix-pack Q0-5 (audit Findings 02.5 + 07.3) —
    // visit-level Deepgram confidence aggregate. Populated by L1 /
    // L1b; null for text_notes (no audio) and for dictation runs
    // that disable utterance segmentation.
    let audioConfidenceStats: AudioConfidenceStats | null = null;

    if (visit.inputMode === 'audio_upload') {
      // ── L1 — Deepgram with diarize on ───────────────────────────
      if (isLayerComplete(resumeState, 'L1')) {
        logSkippedLayer(visitId, 'L1', attempt);
        skipped.push('L1');
      } else {
        currentLayer = 'L1';
        await runLayer1Transcribe({
          visitId,
          practiceId,
          userId: visit.userId,
          audioKey: visit.audioKey!,
          audioMimeType: visit.audioMimeType!,
          interpreterMode: visit.interpreterMode,
          // Issues #202 + #206 — scope keyterm payload to the visit's
          // clinical context. Free-text; builder normalizes.
          specialty: visit.specialty,
        });
      }

      // Always re-read transcriptRaw — whether L1 ran or was skipped,
      // downstream layers need the utterances.
      const withTranscript = await prisma.transcribeVisit.findUnique({
        where: { id: visitId },
        select: {
          transcriptRaw: true,
          speakerMap: true,
          // Round 3 PR-D — A06-P0-001 empty-transcript guard reads
          // these two columns. L1 wrote them; if they're missing the
          // guard fails the visit before L2 burns Anthropic budget.
          audioDurationSec: true,
          transcriptText: true,
          // Round 3 quality fix-pack Q0-5 — L1 wrote this column
          // with the Deepgram per-utterance confidence aggregate.
          // L4 + L5 read it through the worker plumbing below.
          audioConfidenceStats: true,
        },
      });
      const raw = withTranscript?.transcriptRaw as
        | DeepgramBatchResponse
        | null
        | undefined;
      const utterances: DeepgramUtterance[] = raw?.results?.utterances ?? [];
      audioConfidenceStats =
        (withTranscript?.audioConfidenceStats as
          | AudioConfidenceStats
          | null
          | undefined) ?? null;

      // Round 3 PR-D — A06-P0-001 empty-transcript guard. Throws
      // PipelineRejectError on insufficient audio/transcript; the
      // outer catch maps it to FAILED + needsReview with the
      // doctor-actionable humanReason rendered in the visit banner.
      await assertSufficientTranscript({
        visitId,
        practiceId,
        userId: visit.userId,
        durationSec: withTranscript?.audioDurationSec ?? 0,
        transcriptText: withTranscript?.transcriptText ?? '',
      });

      // ── L2 — speaker roles ──────────────────────────────────────
      await prisma.transcribeVisit.update({
        where: { id: visitId },
        data: { status: TranscribeVisitStatus.EXTRACTING },
      });
      let speakerMap: SpeakerMap;
      if (isLayerComplete(resumeState, 'L2')) {
        logSkippedLayer(visitId, 'L2', attempt);
        skipped.push('L2');
        speakerMap = (withTranscript?.speakerMap ?? {}) as SpeakerMap;
      } else {
        currentLayer = 'L2';
        const r = await runLayer2SpeakerRoles({
          visitId,
          practiceId,
          userId: visit.userId,
          utterances,
          interpreterMode: visit.interpreterMode,
        });
        speakerMap = r.speakerMap;
      }

      // ── L3 — conversation entities ──────────────────────────────
      if (isLayerComplete(resumeState, 'L3')) {
        logSkippedLayer(visitId, 'L3', attempt);
        skipped.push('L3');
        entities = resumeState.entities as ExtractedEntities;
        // contextText is a derived string (not persisted) — rebuild
        // from the same inputs L3 would have used.
        contextText = buildRoleLabeledTranscript(utterances, speakerMap);
      } else {
        currentLayer = 'L3';
        const l3 = await runLayer3ExtractEntities({
          visitId,
          practiceId,
          userId: visit.userId,
          mode: 'conversation',
          utterances,
          speakerMap,
        });
        entities = l3.entities;
        contextText = l3.contextText;
      }
      // 2026-06-11 inaudible-span hardening telemetry (audit WARN-2): the
      // per-visit marker count is the observable for threshold tuning and
      // doctor-habituation monitoring during the pilot. Clean prod audio is
      // expected at ~2-6; a flood means the mic or threshold needs review.
      {
        const unclearMarkers = countUnclearMarkers(contextText);
        if (unclearMarkers > 0) {
          log.info('transcribe-md-worker', 'unclear-span markers in transcript', {
            visitId,
            unclearMarkers,
            utterances: utterances.length,
          });
        }
      }
    } else if (visit.inputMode === 'voice_dictation') {
      // ── L1' — single-speaker Deepgram ──────────────────────────
      let dictationText: string;
      if (isLayerComplete(resumeState, 'L1b')) {
        logSkippedLayer(visitId, 'L1b', attempt);
        skipped.push('L1b');
        dictationText = resumeState.transcriptText ?? '';
      } else {
        currentLayer = 'L1b';
        const r = await runLayer1bTranscribeDictation({
          visitId,
          practiceId,
          userId: visit.userId,
          dictationAudioKey: visit.dictationAudioKey!,
          // Dictations come from browser MediaRecorder → webm/opus.
          // Deepgram auto-detects encoding from the Content-Type header.
          dictationMimeType:
            process.env.TRANSCRIBE_MD_DICTATION_MIME ?? 'audio/webm',
          interpreterMode: visit.interpreterMode,
          // Issues #202 + #206 — scope keyterm payload to the visit's
          // clinical context.
          specialty: visit.specialty,
        });
        dictationText = r.transcript;
      }

      // Round 3 PR-D — A06-P0-001 empty-transcript guard (dictation
      // path). Read the duration L1b just wrote and run the same
      // assertion the audio_upload path uses.
      // Round 3 quality fix-pack Q0-5 — also read audioConfidenceStats
      // here so L4/L5 can see it on the dictation branch (will be
      // null today since L1b runs Deepgram with utterances disabled,
      // but the wiring is parallel to the audio_upload branch).
      const withDictationDuration = await prisma.transcribeVisit.findUnique({
        where: { id: visitId },
        select: {
          dictationDurationSec: true,
          audioConfidenceStats: true,
        },
      });
      await assertSufficientTranscript({
        visitId,
        practiceId,
        userId: visit.userId,
        durationSec: withDictationDuration?.dictationDurationSec ?? 0,
        transcriptText: dictationText,
      });
      audioConfidenceStats =
        (withDictationDuration?.audioConfidenceStats as
          | AudioConfidenceStats
          | null
          | undefined) ?? null;

      // ── L3 — dictation entities ─────────────────────────────────
      await prisma.transcribeVisit.update({
        where: { id: visitId },
        data: { status: TranscribeVisitStatus.EXTRACTING },
      });
      if (isLayerComplete(resumeState, 'L3')) {
        logSkippedLayer(visitId, 'L3', attempt);
        skipped.push('L3');
        entities = resumeState.entities as ExtractedEntities;
        contextText = dictationText.trim();
      } else {
        currentLayer = 'L3';
        const l3 = await runLayer3ExtractEntities({
          visitId,
          practiceId,
          userId: visit.userId,
          mode: 'dictation',
          dictationText,
        });
        entities = l3.entities;
        contextText = l3.contextText;
      }
    } else {
      // text_notes — no transcription step. L3 is the earliest layer.
      if (isLayerComplete(resumeState, 'L3')) {
        logSkippedLayer(visitId, 'L3', attempt);
        skipped.push('L3');
        entities = resumeState.entities as ExtractedEntities;
        contextText = (visit.rawTextInput ?? '').trim();
      } else {
        currentLayer = 'L3';
        const l3 = await runLayer3ExtractEntities({
          visitId,
          practiceId,
          userId: visit.userId,
          mode: 'text',
          rawText: visit.rawTextInput!,
        });
        entities = l3.entities;
        contextText = l3.contextText;
      }
    }

    // Q1 #02.8: if the extractor flagged a conflicting/superseded allergy
    // statement, surface a visible needsReview so the doctor resolves it.
    // (The conflict also renders in the SOAP allergies via conflict_note +
    // drives the Rx contraindication warning.) COALESCE keeps any existing
    // reviewReason (low-conf / fallback) rather than clobbering it; the
    // needsReview boolean is purely additive. Never blocks the pipeline.
    if (entities.allergies?.some((a) => a.superseded === true)) {
      try {
        await prisma.$executeRaw`
          UPDATE "transcribe_visits"
          SET "needsReview" = true,
              "reviewReason" = COALESCE(
                "reviewReason",
                'Conflicting allergy statements were detected in this visit — verify the allergy list before signing.'
              )
          WHERE id = ${visitId}
        `;
      } catch {
        // Review-flag is advisory; the conflict still surfaces in the SOAP
        // + the Rx warning. Never fail the visit on this write.
      }
    }

    // -------------------------------------------------------------------
    // Layers 4-6 — mode-agnostic.
    // -------------------------------------------------------------------
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.DRAFTING },
    });
    // Phase 1: resolve the doctor's active note-format template ONCE per
    // visit and thread it to L4/L5/L6. In Phase 1 prod this always resolves
    // to the system default (no custom templates exist yet) → byte-identical
    // output + provenance populated. Defensive fallback to the constant so a
    // DB hiccup never breaks generation.
    let noteTemplate: ResolvedNoteTemplate;
    // RC-3 (#106(c)): what the VISIT asked for, captured BEFORE resolution and
    // before L4's provenance write-back overwrites the same column with the
    // template that was actually used.
    const requestedTemplateId: string | null = visit.noteTemplateId ?? null;
    let templateResolutionFailed = false;
    try {
      // Honor an explicit per-visit pick (chosen on the new-visit form) over
      // active-template resolution. A stale/invalid pick falls through to the
      // normal active resolution so generation never breaks on a bad id.
      //
      // ⚠️ #302 — THE TENANT'S TEMPLATES ARE IN SCOPE HERE TOO, AND FORGETTING
      // THIS LOOKUP IS HOW THE FIX WOULD HALF-APPLY. It is the door a per-visit
      // pick comes through; leaving it keyed on `doctorId` alone would mean the
      // resolver honoured the chart's format while an explicit pick still could
      // not name it, and the failure would appear only for visits that used the
      // new-visit form — the shape #287's own defect had.
      const picked = visit.noteTemplateId
        ? await prisma.noteTemplate.findFirst({
            where: {
              id: visit.noteTemplateId,
              // ⚠️ #302 / LENS A1 — THE AUTHOR DISJUNCT IS GONE, AND ITS
              // ABSENCE IS THE FIX. `OR` is a DISJUNCTION: keeping
              // `{ doctorId }` beside `{ practiceId }` meant a locum's own
              // practice-B template satisfied the query on `doctorId` alone,
              // `picked` short-circuited past the resolver entirely, and B's
              // sections built the L4 prompt for A's chart — the exact
              // wrong-practice document #287 exists to stop, re-entering
              // through the door #302 had just widened.
              //
              // Nothing is lost by deleting it. The T7 tenancy migration
              // backfilled `note_templates.practiceId` from the doctor and
              // enforces a BICONDITIONAL — a template has a practice IFF it
              // has a doctor — so every doctor-owned template in scope
              // ALREADY matches `{ practiceId: visit.practiceId }`. The
              // disjunct could only ever add OUT-of-scope rows.
              OR: [{ practiceId: visit.practiceId }, { isSystemDefault: true }],
            },
          })
        : null;
      noteTemplate = normalizeTemplate(
        picked ??
          (await resolveActiveTemplate({
            doctorId: visit.userId ?? '',
            // ⚠️ #302 — THE CHART'S PRACTICE SELECTS THE FORMAT. `doctorId`
            // above is attribution and a preference; this is the scope. A
            // locum from B documenting A's patient fills A's format.
            tenantPracticeId: visit.practiceId,
            encounterType: visit.specialty,
          }))
      );
    } catch (err) {
      log.warn(
        'worker:note-template',
        'resolveActiveTemplate failed; falling back to system default',
        { visitId, err: err instanceof Error ? err.message : String(err) }
      );
      noteTemplate = SYSTEM_DEFAULT_NOTE_TEMPLATE;
      templateResolutionFailed = true;
    }

    // ── RC-3 — THE FALLBACK GOES LOUD (#106(c), SPEC §4.3a(d)) ─────────────
    //
    // ⚠️ IT CHANGES NO CHOICE. Every fallback above stays exactly as it was —
    // making one throw would turn "wrong layout" into "failed visit", which is
    // worse for the doctor and is not what the ruling asks for. What changes is
    // that the doctor is TOLD, in a banner that names the cause, instead of
    // receiving a generic note indistinguishable from the product not working.
    //
    // The applicable-template probe runs ONLY when the generic layout won and
    // nothing else already explains it — one cheap count on the path where the
    // answer might be "you have a form and did not get it".
    {
      // ⚠️ THE DETECTOR IS CALLED UNCONDITIONALLY, AND THE EARLIER GATE MADE ONE
      // OF ITS ARMS UNREACHABLE. It used to run only when the GENERIC layout
      // won — but "the visit named format A and format B produced the note" is
      // a substitution the doctor never asked for and neither template is the
      // system default, so that arm could never fire. A stale pick falling
      // through to a DIFFERENT custom template is exactly the case
      // `resolveActiveTemplate`'s fallbacks produce.
      //
      // The detector returns null in the overwhelmingly common case, so calling
      // it always costs nothing. Only the PROBE — one count query — stays
      // gated, to the path where the answer might be "you have a form and did
      // not get it".
      let hasApplicableActiveTemplate = false;
      if (!templateResolutionFailed && noteTemplate.isSystemDefault) {
        try {
          hasApplicableActiveTemplate =
            (await prisma.noteTemplate.count({
              where: {
                doctorId: visit.userId ?? '',
                // ⚠️ #302 / LENS A2 — THE PROBE IS SCOPED TOO, OR IT RAISES A
                // FALSE ALARM ON CORRECT BEHAVIOUR. This asks "does the
                // clinician have a format that should have applied?" to explain
                // why the system default was used. Unscoped, it counted the
                // author's templates at OTHER practices, so a locum correctly
                // rendering practice A's standard layout was told "you have an
                // activated note format for this visit type" — about a form
                // belonging to practice B, on the note they are about to sign.
                // The comment below names the cost of exactly that.
                practiceId: visit.practiceId,
                status: 'active',
                isSystemDefault: false,
                // Their format for THIS visit type, or their catch-all. A
                // template scoped to another specialty resolving away is
                // correct behaviour, and a banner there would be a false alarm
                // — the fastest way to teach a clinician to ignore the banner
                // that matters.
                OR: [{ encounterType: visit.specialty }, { encounterType: null }],
              },
            })) > 0;
        } catch (err) {
          // A failed probe must never break generation. It means the banner is
          // not raised, which is the same as today.
          log.warn('worker:note-template', 'applicable-template probe failed', {
            visitId,
            err: err instanceof Error ? err.message : String(err),
          });
        }
      }
      const fallback = detectTemplateFallback({
        requestedTemplateId,
        effective: { id: noteTemplate.id, isSystemDefault: noteTemplate.isSystemDefault },
        resolutionFailed: templateResolutionFailed,
        hasApplicableActiveTemplate,
      });
      if (fallback) {
        log.warn('worker:note-template', 'generic layout used for a template-bound visit', {
          visitId,
          kind: fallback.kind,
          requestedTemplateId,
          effectiveTemplateId: noteTemplate.id,
        });
        // Additive + monotone + SQL-side, so it cannot clobber a
        // safety-relevant reason another layer sets later.
        await applyAdditiveReviewState(visitId, {
          needsReview: true,
          reviewReason: fallback.reason,
        });
      }
    }

    let soapDraft: string;
    if (isLayerComplete(resumeState, 'L4')) {
      logSkippedLayer(visitId, 'L4', attempt);
      skipped.push('L4');
      soapDraft = resumeState.soapDraft ?? '';
    } else {
      currentLayer = 'L4';
      soapDraft = await runLayer4GenerateSoap({
        visitId,
        practiceId,
        userId: visit.userId,
        specialty: visit.specialty,
        roleLabeledTranscript: contextText,
        entities,
        // Round 3 quality fix-pack Q0-5 — visit-level Deepgram
        // confidence aggregate. Drives the L4 hedge prompt when
        // the audio fidelity was poor.
        audioConfidenceStats,
        interpreterMode: visit.interpreterMode,
        noteTemplate,
      });
    }

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.CRITIQUING },
    });
    let critique: Awaited<ReturnType<typeof runLayer5SelfCritique>>;
    if (isLayerComplete(resumeState, 'L5')) {
      logSkippedLayer(visitId, 'L5', attempt);
      skipped.push('L5');
      critique = resumeState.critique as typeof critique;
    } else {
      currentLayer = 'L5';
      critique = await runLayer5SelfCritique({
        visitId,
        practiceId,
        userId: visit.userId,
        specialty: visit.specialty,
        soapDraft,
        roleLabeledTranscript: contextText,
        entities,
        // Round 3 quality fix-pack Q0-5 — same hedge signal L4 sees,
        // so the auditor can flag SOAP content the audio doesn't
        // clearly support as critical hallucinations.
        audioConfidenceStats,
        noteTemplate,
      });
    }

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.POLISHING },
    });
    let polished: { soapFinal: string };
    if (isLayerComplete(resumeState, 'L6')) {
      logSkippedLayer(visitId, 'L6', attempt);
      skipped.push('L6');
      polished = { soapFinal: resumeState.soapFinal ?? '' };
    } else {
      currentLayer = 'L6';
      polished = await runLayer6Polish({
        visitId,
        practiceId,
        userId: visit.userId,
        soapDraft,
        critique,
        noteTemplate,
        // Q1 audit §07.1 — the context L4 and L5 already read, and polish did
        // not. A DISAMBIGUATION source only: the L6b fidelity gate still
        // measures the polished note against the draft alone.
        specialty: visit.specialty,
        entitiesJson: JSON.stringify(entities),
        roleLabeledTranscript: contextText,
        // Only point the doctor at the review lane when there IS one.
        //
        // Read FRESH, and with the column named explicitly. The `visit` object
        // above is loaded before L4 runs and does not select this field, so
        // reading it from there would be `undefined` on every visit — prisma is
        // untyped here, so nothing would have said so and the deferred-fix
        // sentence would simply have stopped appearing.
        hasSuggestions: await laneHasSuggestions(visitId),
      });
    }

    // BUG-FIX (styled-export measurement tables): for an IMAGING REPORT only,
    // rebuild any venous-duplex measurement table to ONE canonical symmetric row
    // set for both legs and recover a dropped, prose-documented measurement into
    // its cell. Pure + deterministic. Gated on the imaging specialty (NOT content
    // sniffing) so a non-imaging custom/structured template with a similarly-named
    // column is never rebuilt against vein anatomy. The reconciled note is what
    // gets persisted below (soapFinalForFanout), so the review UI + styled export
    // + signed note all render it consistently.
    //
    // ADMIN-3 PR-1 (ruling #197): the pass is KEYED BY the catalog row's own
    // `reportBuilder` name (ultrasound → reconcileMeasurementTables), so a
    // second imaging type can never inherit the venous-duplex rebuild. Same
    // flag-agnostic exact-id predicate as before (null for every non-imaging
    // specialty); an imaging row with no registered builder THROWS.
    const imagingReportBuilder = imagingReportBuilderFor(visit.specialty);
    if (imagingReportBuilder) {
      polished = {
        ...polished,
        soapFinal: imagingReportBuilder.reconcileFinalNote(polished.soapFinal),
      };
    }

    // -------------------------------------------------------------------
    // T-M6 — parallel automation fan-out. Each L7x layer runs
    // independently against the same polished SOAP + entities; a single
    // layer failing never fails the visit. Missing outputs show up as
    // empty columns + a confidenceScores note.
    // -------------------------------------------------------------------
    currentLayer = 'automation';
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.AUTOMATING },
    });

    const soapFinalForFanout = polished.soapFinal;
    const entitiesJson = JSON.stringify(entities);

    // Env feature flags — operators can disable any layer without a
    // code change if costs spike or a layer misbehaves in prod.
    // An IMAGING REPORT (e.g. ultrasound) has no office-visit E/M level, so
    // suppress L7b (CPT/E&M) for those specialties — its task records
    // status:'skipped' (never a needsReview false-flag). ICD/Rx/referrals stay
    // on (a venous study can still carry an indication diagnosis). This is the
    // pipeline-level E/M suppression; the on-read E/M coaching score is
    // suppressed separately at the visit-detail read (see page.tsx).
    const isImagingReport = isImagingReportSpecialty(visit.specialty);

    // F12-c / ruling #123 — THE SECOND AXIS, AT THE COMPUTE LAYER.
    //
    // `flags.cpt` above is the SPECIALTY axis and it stays exactly as it is: an
    // imaging report skips the whole layer. An OPERATIVE note must NOT, because
    // the layer is also where a colonoscopy's PROCEDURE code comes from — the
    // one code that encounter genuinely bills. So the note-shape axis is not a
    // flag; it is a parameter, and it suppresses one field rather than a layer.
    //
    // ⚠️ COMPUTED ONCE, HERE, AND HANDED TO BOTH CONSUMERS. L7b needs it to drop
    // the E/M half, and `detectIncompleteAutomation` needs it so a deliberately
    // absent E/M is not reported to the doctor as a failed layer. Two consumers
    // reading one value is the point — this conjunction was open-coded in seven
    // places once already and one copy was spelled wrong.
    //
    // ⚠️ THE TEMPLATE COMES FROM THE RESOLVED OBJECT, NOT A RE-READ. Every other
    // caller passes `visit.noteTemplate?.sections`, i.e. the JOINED row for
    // `noteTemplateId` — and `noteTemplateId` is written from THIS object by L4
    // (`04-generate-soap.ts:523,562`), so the two name the same template. Using
    // the object avoids a query and cannot race the write that L4 just made.
    // `ResolvedNoteTemplate.sections` is `NoteTemplateSection[]`, whose `label`
    // is the field `normalizedSectionLabels` reads — the same shape, asserted
    // by the gate rather than assumed here.
    //
    // ⚠️ AND THE NOTE TEXT IS `soapFinalForFanout`, WHICH IS WHAT THE VISIT WILL
    // CARRY. Ruling #126c's silence clause is what makes this reachable at all:
    // L4 binds the SYSTEM DEFAULT when a doctor has no operative template, its
    // four labels are exactly the SOAP skeleton, so `templateIsSilent` is true
    // and the note body's own headings decide. Without that clause the template
    // arm would answer "office visit" for every untemplated operative note and
    // this parameter would be permanently true.
    //
    // ⚠️ STILL TRUE AFTER F12-d. An earlier draft of F12-d ungated that arm into
    // an OR, which would have made this paragraph false — and this comment was
    // edited to say so before the adversarial pass killed the OR. Both the code
    // and the sentence are back where they were; recorded because the next
    // session will have the same idea and this is the paragraph it will read.
    const emApplies = emAppliesToVisit({
      specialtyId: visit.specialty,
      templateSections: noteTemplate.sections,
      noteText: soapFinalForFanout,
    });

    const flags = {
      icd: process.env.TM_ENABLE_ICD_CPT !== 'false',
      cpt: process.env.TM_ENABLE_ICD_CPT !== 'false' && !isImagingReport,
      rx: process.env.TM_ENABLE_RX !== 'false',
      referrals: process.env.TM_ENABLE_REFERRALS !== 'false',
      summary: process.env.TM_ENABLE_PATIENT_SUMMARY !== 'false',
    };

    type AutomationTask = {
      key:
        | 'icd_coding'
        | 'cpt_coding'
        | 'rx_drafting'
        | 'referrals'
        | 'patient_summary';
      enabled: boolean;
      run: () => Promise<unknown>;
    };

    const tasks: AutomationTask[] = [
      {
        key: 'icd_coding',
        enabled: flags.icd,
        run: () =>
          runLayer7aIcdCoding({
            visitId,
            practiceId,
            userId: visit.userId,
            specialty: visit.specialty,
            soapFinal: soapFinalForFanout,
            entitiesJson,
          }),
      },
      {
        key: 'cpt_coding',
        enabled: flags.cpt,
        run: () =>
          runLayer7bCptCoding({
            visitId,
            practiceId,
            userId: visit.userId,
            specialty: visit.specialty,
            soapFinal: soapFinalForFanout,
            entitiesJson,
            emApplies,
          }),
      },
      {
        key: 'rx_drafting',
        enabled: flags.rx,
        run: () =>
          runLayer7cRxDrafting({
            visitId,
            practiceId,
            userId: visit.userId,
            soapFinal: soapFinalForFanout,
            entitiesJson,
            // Fix-Pack 1 Q0-2 / audit Finding 01.1 — patient context
            // for pediatric mg/kg/day framing. `patient` is non-null
            // because TranscribeVisit.patientId is NOT NULL since
            // T-M17.2; the field-level guards (DOB, weight) are
            // resolved inside the layer.
            patient: {
              dateOfBirth: visit.patient.dateOfBirth,
              weightKg: visit.patient.weightKg,
              allergies: visit.patient.allergies,
            },
          }),
      },
      {
        key: 'referrals',
        enabled: flags.referrals,
        run: () =>
          runLayer7dReferrals({
            visitId,
            practiceId,
            userId: visit.userId,
            soapFinal: soapFinalForFanout,
            entitiesJson,
          }),
      },
      {
        key: 'patient_summary',
        enabled: flags.summary,
        run: () =>
          runLayer7ePatientSummary({
            visitId,
            practiceId,
            userId: visit.userId,
            specialty: visit.specialty,
            soapFinal: soapFinalForFanout,
            entitiesJson,
          }),
      },
    ];

    // T-M13 — per-task resumability. For each enabled L7 task, check
    // its checkpoint column: if populated from a prior attempt, skip
    // the run and carry a bare 'ok' status. Failed L7 columns are
    // nulled by the catch below, so the skip check correctly returns
    // false for them and they re-run.
    const TASK_KEY_TO_LAYER: Record<AutomationTask['key'], PipelineLayer> = {
      icd_coding: 'L7a',
      cpt_coding: 'L7b',
      rx_drafting: 'L7c',
      referrals: 'L7d',
      patient_summary: 'L7e',
    };
    const enabled = tasks.filter((t) => t.enabled);
    const toRun: AutomationTask[] = [];
    const resumedOk = new Set<AutomationTask['key']>();
    for (const t of enabled) {
      const layer = TASK_KEY_TO_LAYER[t.key];
      if (isLayerComplete(resumeState, layer)) {
        logSkippedLayer(visitId, layer, attempt);
        skipped.push(layer);
        resumedOk.add(t.key);
      } else {
        toRun.push(t);
      }
    }
    // ── EM-score MDM judge pre-warm ────────────────────────────────
    // Populates the Redis `em_mdm_cache:<sha256(soap)>` entry so the
    // visit page's server-side render + the apply-additions route both
    // hit a warm cache instead of paying the 10-30s LLM cost at click
    // time. Fires alongside the L7 fan-out (parallel — same SOAP, no
    // dependency on L7 outputs). Soft-fail: judging is idempotent +
    // cached, so a missed pre-warm just shifts one judge call back to
    // the page render. No new Prisma column needed — the cache is
    // Redis-only with a 7-day TTL.
    const judgeWarmPromise = (async () => {
      try {
        const { judgeMdm } = await import('@/lib/em-coding/llm-mdm');
        await judgeMdm({
          soap: soapFinalForFanout,
          practiceId,
          visitId,
          userId: visit.userId,
        });
      } catch (err) {
        console.error(
          `[transcribe-md-worker] em-judge prewarm failed:`,
          redactPhi(err instanceof Error ? err.message : err),
        );
      }
    })();

    const results = await Promise.allSettled(toRun.map((t) => t.run()));
    // Wait for the judge pre-warm to finish before transitioning to
    // READY. Without this await the doctor could open the page while
    // the cache write is still in flight and trigger a duplicate judge
    // call. Awaiting after `results` keeps wall-clock the same because
    // both run in parallel; only matters if pre-warm outlives the L7
    // tasks (rare — judge p95 ~11s, L7 layers each 5-30s).
    await judgeWarmPromise;

    // Roll settled results up into confidenceScores so the UI + future
    // observability can see per-layer status without re-reading ai_calls.
    type LayerStatus =
      | { status: 'ok'; metadata?: unknown }
      | { status: 'skipped' }
      | { status: 'failed'; reason: string };
    const confidenceScores: Record<string, LayerStatus> = {};

    for (const t of tasks) {
      if (!t.enabled) {
        confidenceScores[t.key] = { status: 'skipped' };
        continue;
      }
      if (resumedOk.has(t.key)) {
        // Persisted from a prior attempt — we don't have the original
        // metadata (flesch_kincaid grade for patient_summary) in memory
        // and re-reading it isn't worth the complexity. Bare 'ok' is
        // accurate. The actual patientSummary column is intact, which
        // is what the Extras tab reads.
        confidenceScores[t.key] = { status: 'ok' };
        continue;
      }
      const idx = toRun.indexOf(t);
      const r = results[idx];
      if (r.status === 'fulfilled') {
        // Persist Layer 7e readability grade into confidenceScores so
        // the Extras tab can show the grade without re-computing.
        if (t.key === 'patient_summary') {
          const out = r.value as {
            fleschKincaid?: number;
            flagged?: boolean;
          };
          confidenceScores[t.key] = {
            status: 'ok',
            metadata: {
              flesch_kincaid: out.fleschKincaid,
              flagged: out.flagged,
            },
          };
        } else {
          confidenceScores[t.key] = { status: 'ok' };
        }
      } else {
        const reason =
          r.reason instanceof Error
            ? r.reason.message
            : String(r.reason ?? 'unknown');
        console.error(
          `[transcribe-md-worker] automation layer ${t.key} failed:`,
          reason
        );
        confidenceScores[t.key] = {
          status: 'failed',
          reason: reason.slice(0, 500),
        };
        // Clear any column the layer might have partially written so a
        // stale "almost-populated" row can't mislead the UI, AND so
        // the T-M13 skip check returns false on the next retry.
        await clearAutomationColumn(visitId, t.key).catch(() => {});
      }
    }

    // -------------------------------------------------------------------
    // Finalise. Sum per-layer costs from ai_calls (includes T-M4 layers
    // + T-M6 layers). Fail-open if AiCall read errors; the cost number
    // is observability, not load-bearing for correctness.
    // -------------------------------------------------------------------
    const costRows = await prisma.aiCall.findMany({
      where: { visitId },
      select: { costUsdCents: true },
    });
    const totalCents = costRows.reduce(
      (sum: number, r: { costUsdCents: number | null }) =>
        sum + (r.costUsdCents ?? 0),
      0
    );

    // Deep-audit G9 (2026-05-12) + cross-input-mode-audit Finding 2
    // extension (2026-05-13) — load-bearing L7 failure OR empty-codes-
    // with-status-ok flips needsReview. Helper lives at
    // worker/automation-incomplete.ts; comments there explain the
    // design (T-M6 preserved, status stays READY).
    //
    // Re-read the visit's icdCodes + cptCodes columns post-fan-out so
    // the helper can detect the "model returned nothing successfully"
    // case (UC2 audio_upload on PR #232). Includes resumed layers — if
    // a prior attempt landed empty codes the resume keeps them empty,
    // and the doctor still deserves the review banner.
    // DB-blip semantics worth noting (auditor NIT 2026-05-13): if this
    // re-read throws, we fall through with `outputs.icdCodes=null` +
    // `outputs.cptCodes=null`, which the helper interprets as empty
    // → flips needsReview=true with cause='empty'. That's intentional
    // defense-in-depth — the visit lands in review (doctor sees a
    // banner, can retry) rather than silently passing through. A
    // transient false-positive empty flag is preferable to silently
    // missing a genuine empty-codes case during a real DB hiccup. (Since the
    // 2026-07-02 icd dedup, the FRESH-run blip lands in review via the
    // cpt-null leg only — the icd leg is resumed-attempts-only; the genuine
    // fresh empty-icd case is covered by 07a's own committed flag.)
    const automationOutputs = await prisma.transcribeVisit
      .findUnique({
        where: { id: visitId },
        select: { icdCodes: true, cptCodes: true },
      })
      .catch(() => null);
    const incomplete = detectIncompleteAutomation(
      confidenceScores as AutomationConfidenceScores,
      {
        icdCodes: (automationOutputs?.icdCodes ?? null) as
          | { codes?: unknown[] }
          | null,
        cptCodes: (automationOutputs?.cptCodes ?? null) as
          | { em?: { code?: string | null } | null; procedures?: unknown[] }
          | null,
        // Fresh L7a runs always self-flag empty codes (07a post-validation);
        // pass-2's icd empty check only adds signal on RESUMED attempts,
        // where the attempt-start reset wiped that flag and L7a is skipped.
        icdResumed: resumedOk.has('icd_coding'),
        // F12-c — NOTHING IS PASSED HERE, DELIBERATELY. The helper reads
        // `cptCodes.emSuppressed`, which L7b wrote in the same run that produced
        // the blob. Handing it `emApplies` recomputed HERE would re-open the
        // resume-path banner: on a retry this value is derived from the EDITED
        // note, while the blob it judges was produced from the original.
      },
    );
    if (incomplete.needsReview) {
      void logAudit({
        action: 'VISIT_AUTOMATION_INCOMPLETE',
        targetId: visitId,
        targetType: 'TranscribeVisit',
        userId: visit.userId,
        practiceId,
        success: false,
        metadata: {
          failedLayers: incomplete.failedLayers,
          reasons: incomplete.reasonsByLayer,
          causes: incomplete.causeByLayer,
        },
      });
    }

    // FIND-P1-012 (2026-05-14): parse + JSON-round-trip
    // confidenceScores before the write. Prisma's JSONB adapter
    // silently coerces non-serializable values (Map → {}, function
    // → drop) which can leave the column with a shape that L2/L7
    // can't read back. The sanitizer returns null on schema-fail or
    // serialize-fail; null is the same shape the column carries on
    // first-attempt initial state (worker.ts:297), so downstream
    // readers handle it.
    // Template Twin native-DOCX fill step (flag-gated + FAIL-SAFE). Produces the
    // provenance-pinned native fill manifest BEFORE the visit goes READY, so
    // export serves a cached native document. A failure here NEVER blocks the
    // visit or signing — the result is advisory; native export falls back to styled.
    const twinFill = await runTemplateTwinFillStep({
      visitId,
      tenantPracticeId: visit.practiceId,
      authorUserId: visit.userId,
      noteTemplateId: noteTemplate.id,
      noteTemplateVersion: noteTemplate.version,
      inputMode: visit.inputMode,
      contextText,
      entities,
      generatedNote: soapFinalForFanout,
      visitDate: visit.createdAt,
    });
    if (twinFill.status === 'failed') {
      console.warn(
        `[transcribe-md-worker] template-twin fill non-blocking failure visit=${visitId}: ${twinFill.reason}`
      );
    }

    const safeConfidenceScores = sanitizeConfidenceScores(confidenceScores);
    if (safeConfidenceScores === null) {
      console.warn(
        `[transcribe-md-worker] confidenceScores schema/serialize fail for visit=${visitId}, writing null`
      );
    }
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: {
        status: TranscribeVisitStatus.READY,
        processingFinishedAt: new Date(),
        processingCostCents: totalCents,
        // F-TYPE 2026-08-07 — was `safeConfidenceScores as unknown as object |
        // null`. Behaviour is unchanged: `Prisma.JsonNull` writes the JSON null
        // that a bare `null` already produced here, and it matches what the
        // attempt-start reset above (search `confidenceScores IS still cleared`)
        // writes to this same column — see the measurement table there.
        // `Prisma.DbNull` (SQL NULL) would NOT be equivalent.
        confidenceScores: isJsonInput(safeConfidenceScores)
          ? safeConfidenceScores
          : Prisma.JsonNull,
        // Persist the FINAL note. L6 wrote soapFinal earlier; for an imaging
        // report it has since been reconciled (symmetric measurement tables +
        // recovered values), so re-persist it here so the review UI, styled
        // export, and eventual signedSoap all read the reconciled note. A no-op
        // rewrite for a non-imaging note (soapFinalForFanout === the L6 value).
        soapFinal: soapFinalForFanout,
      },
    });
    // 2026-06-11 audit BLOCK-2: the automation-incomplete review flag is
    // applied ADDITIVELY — assigning it in the update above clobbered
    // review state set earlier in the pipeline (the L6 fabrication-gate
    // rejection banner, L6 unfixable-criticals, the 02.8 allergy flag)
    // whenever the L7 fan-out was clean, so the doctor never saw it.
    await applyAdditiveReviewState(visitId, incomplete);

    // ── B8 step 2 — THE DEBIT ────────────────────────────────────────────────
    // A no-op unless `BILLING_ENFORCED=true`. Runs AFTER the visit is READY and
    // after the review state is applied, so nothing about the clinical outcome
    // depends on it — and it never throws (see `chargeVisitUsage`), because a
    // billing write must not be able to fail a finished note.
    //
    // ⚠️ ONLY THE SUCCESS PATH CHARGES, AND AFTER B8 STEP 3 THAT IS THE SETTLED
    // STATE RATHER THAN A GAP. The failure path is FREE and is measured instead
    // — see `billing-failure.ts` and the observation in the catch below. A
    // charging policy for failures needs a month of that measurement first;
    // production has never held a single FAILED visit to price one from.
    //
    // ⚠️ ⚠️ BUT THIS LINE HAS A DEFECT OF ITS OWN THAT B8 STEP 3 DID NOT FIX,
    // AND IT IS THE SAME SENTENCE POINTED AT THE SUCCESS PATH — "we would bill
    // doctors for our outages". `loadVisitChargeableUsage(visitId)` selects
    // EVERY usage row for the visit with NO ATTEMPT FILTER, so a visit that
    // eventually succeeds after a retry is charged for the re-run work too.
    //
    // ⚠️ SCOPED CAREFULLY, BECAUSE THE OBVIOUS READING OVERSTATES IT. This is
    // NOT "all attempts' whole-pipeline spend": per-layer resume above
    // (`isLayerComplete`) skips every layer whose output already persisted, so
    // L1–L4 are not re-spent when the failure was at L5. The over-charge is
    // every attempt of the layers that actually RE-RAN — principally the
    // failing layer, bounded by BullMQ's attempt budget. A visit that failed
    // twice at L5 on OUR transient faults pays 3× for L5.
    //
    // Smaller than it first looks, and still the doctor paying for our blips,
    // silently, into an append-only table.
    //
    // It is inert today only because `BILLING_ENFORCED` is off, which is
    // precisely the condition that stops being true when the flag is enabled.
    // Fixing it needs attempt attribution on `api_usage_events` (there is no
    // `attempt` column today), which is a schema decision and its own item.
    // **Carried as B8 step 3b, and it BLOCKS enabling the flag.**
    const charge = await chargeVisitUsage({ practiceId, visitId });
    if (charge.charged === 'failed') {
      // Loud, because this is money we consumed and did not record. Nothing
      // else in the system will notice until B9 reconciles.
      console.warn(
        `[transcribe-md-worker] usage charge FAILED to record visit=${visitId}: ${charge.detail}`
      );
    } else if (charge.charged !== 'skipped_not_enforced') {
      log.info('transcribe-md-worker', 'usage charge', {
        visitId,
        outcome: charge.charged,
      });
    }

    // T-M13 summary line — logs only when at least one layer was
    // skipped, so happy-path first attempts stay quiet.
    logSkipSummary(visitId, attempt, skipped);
  } catch (err) {
    // FIND-P1-011: visit deleted between top-level findUnique and a
    // BullMQ retry's resume-state load. Short-circuit: don't try to
    // write FAILED state to a non-existent row (P2025), don't burn
    // the admin notify, don't pretend this needs further retry.
    // Returning cleanly tells BullMQ the job is done — which it is,
    // the visit's gone. The cleanup sweep handles the orphaned audio.
    if (err instanceof VisitNotFoundError) {
      log.info(
        'transcribe-md-worker',
        'visit deleted during retry, dropping job',
        { visitId, attemptsMade: job.attemptsMade ?? 0 }
      );
      return;
    }

    // T-M16.3: Deepgram/Anthropic errors can quote audio/file metadata
    // or URLs — scrub before emitting to container stdout. Sentry path
    // (captureWorkerException below) does its own redactPhi via the
    // beforeSend hook, so double-coverage is intentional.
    console.error(
      `[transcribe-md-worker] visit ${visitId} failed:`,
      redactPhi(err instanceof Error ? err.message : err)
    );
    // T-M16.3: capture to Sentry BEFORE the re-throw so BullMQ's retry
    // still sees the original error. The {visitId, layer} tags let ops
    // filter errors by failure point without reading the stack trace.
    // Round 3 PR-H: pass userId + practiceId as tags too — IDs only,
    // never email/name/MRN.
    captureWorkerException(err, {
      visitId,
      layer: currentLayer,
      userId: visit.userId,
      practiceId: visit.user?.practiceId ?? null,
    });

    // T-M23.A: only persist FAILED on the final BullMQ attempt …
    // *unless* this fix-pass classifies the error as `permanent`. A
    // permanent error (Zod, "unsupported format", zero-byte audio,
    // etc.) will fail the same way on every retry — burning two more
    // BullMQ attempts is just two more Anthropic / Deepgram calls
    // for the same outcome. Fail-fast in that case so the doctor
    // sees the actionable banner ~5s instead of ~25s after submit.
    const category: ErrorCategory = categorizeError(err);
    // Q1 #09.1: surface Anthropic content-policy refusals as a distinct,
    // countable audit action (categorizeError maps them permanent → the
    // fail-fast path below fires on the first attempt, so this emits once).
    // Fire-and-forget; never blocks the failure path. PHI-safe metadata.
    if (err instanceof Error && err.name === 'AnthropicRefusalError') {
      const refusal = err as Error & { model?: string; purpose?: string };
      void logAudit({
        action: 'AI_REFUSAL',
        targetType: 'TranscribeVisit',
        targetId: visitId,
        userId: visit.userId,
        practiceId: visit.user?.practiceId ?? null,
        success: false,
        errorCode: 'AI_REFUSAL',
        metadata: {
          layer: currentLayer,
          model: refusal.model ?? null,
          purpose: refusal.purpose ?? null,
        },
      });
    }
    const attemptsMade = job.attemptsMade ?? 0;
    const attempts = job.opts.attempts ?? 1;
    const isFinalAttempt = shouldMarkVisitFailed(attemptsMade, attempts);
    const shouldFailNow = isFinalAttempt || category === 'permanent';
    if (!shouldFailNow) {
      log.info(
        'transcribe-md-worker',
        'transient failure, awaiting BullMQ retry',
        {
          visitId,
          layer: currentLayer,
          category,
          attemptsMade,
          attempts,
        }
      );
      throw err;
    }
    if (category === 'permanent' && !isFinalAttempt) {
      log.info(
        'transcribe-md-worker',
        'permanent failure, fail-fast (skipping BullMQ retries)',
        { visitId, layer: currentLayer, attemptsMade, attempts }
      );
    }

    // FIND-P1-014: persist FAILED-state via a helper that returns
    // a structured {persistOk, persistErr} result instead of silently
    // swallowing write failures. The original `err` already went to
    // Sentry above; the helper additionally logs + captures the
    // *secondary* (persist) failure so post-mortems have both halves.
    // Policy: re-throw `persistErr` below so BullMQ marks the job
    // failed with the persist failure as the proximate cause —
    // silent stuck-in-non-terminal is the worse failure mode.
    const { persistOk, persistErr } = await persistFailedState({
      visitId,
      category,
      layer: currentLayer,
      originalErr: err,
      reviewReason: buildUserFacingFailureReason(currentLayer, category, err),
      userId: visit.userId,
      practiceId: visit.user?.practiceId ?? null,
    });

    // ── B8 step 3 — WHAT DID THIS FAILURE COST US, AND WHOSE FAULT WAS IT? ──
    // ⚠️ IT CHARGES NOTHING. There is no ledger write in `billing-failure.ts`
    // and no path from here to one — a failed visit is FREE, and that is the
    // item's central decision rather than a gap in it. The reasoning is in that
    // file's header: production has never held a single FAILED visit, so a
    // charging policy would be chosen from zero observations, and on an
    // APPEND-ONLY ledger charging is the direction that cannot be walked back.
    // This produces the measurement that decision is waiting on.
    //
    // ⚠️ AND IT IS NOT BEHIND `BILLING_ENFORCED`, ON PURPOSE. Its whole job is
    // to inform the decision to turn that flag ON; gated behind the same flag
    // it would produce nothing until the flip it is meant to advise had already
    // happened. It is safe unflagged because it writes nothing anywhere.
    //
    // Awaited rather than fire-and-forget: it writes nothing, so there is no
    // row a later test could read back, and awaiting is what makes the outcome
    // deterministic enough to assert. It cannot throw — the seam absorbs its
    // own errors, because replacing a real pipeline error with a billing one as
    // the job's proximate cause would destroy the diagnosis of this failure.
    // ⚠️ ONCE PER VISIT, NOT ONCE PER ATTEMPT — AND THE GUARD IS NOT DECORATIVE.
    // Measured on QA 2026-08-13 by `scripts/qa/b8-failure-cost-on-qa.ts`: an
    // admission-refused visit produced **THREE** `failure cost` lines, one per
    // BullMQ attempt, 5s apart. `shouldFailNow` is `isFinalAttempt || category
    // === 'permanent'`, so a PERMANENT failure enters this branch on EVERY
    // attempt — the re-throw below still hands the error to BullMQ and nothing
    // discards the job.
    //
    // Unguarded, the observation therefore reports the same visit's cost up to
    // `attempts` times. It charges nothing either way (the ledger was 0 → 0
    // across both postures of the proof), so this is a MEASUREMENT defect, not
    // a money one — but the number it inflates is precisely the one that will
    // price the decision to enable `BILLING_ENFORCED`, and it inflates it in
    // the direction that makes failures look more expensive than they are.
    //
    // ⚠️ THE PREDICATE IS "FIRST ENTRY INTO THIS BRANCH", AND THE OBVIOUS WAY
    // TO WRITE IT IS WRONG. The first attempt at this guard read
    // `isFinalAttempt || attemptsMade === 0`, which reads like "the first one
    // or the last one" and is exactly-TWICE for a permanent failure: the branch
    // is entered at attemptsMade 0 (first disjunct) AND again at attemptsMade 2
    // (second disjunct). Re-running the QA proof measured 2 lines, 15s apart,
    // for one visit — the fix halved the defect and did not remove it.
    //
    // Caught only because the proof was re-run rather than assumed to work:
    // AGENTS.md's "mutate toward SUCCESS, not just toward failure" — a guard
    // proven only in the red direction is half-proven, and this is the half
    // that was broken.
    //
    // We are already inside `shouldFailNow = isFinalAttempt || permanent`, so
    // a non-permanent category here is necessarily the final attempt. That
    // makes the correct form a single question about the permanent case:
    //
    //   permanent  → entered on every attempt; want only attemptsMade === 0
    //   otherwise  → entered once, on the final attempt; want it
    //
    // ⚠️ B8 step 3c HAS SINCE FIXED THE RETRIES, AND THIS GUARD IS STILL LOAD-
    // BEARING — WHICH IS THE WHOLE REASON IT WAS WRITTEN THIS WAY. With the
    // discard below in place a permanent failure enters this branch exactly
    // once, at `attemptsMade === 0`, so the predicate is now describing the
    // behaviour rather than compensating for it. Its header already predicted
    // this: the obvious alternative, `isFinalAttempt` alone, would have gone
    // SILENT the day 3c landed — `attemptsMade` is 0 and `isFinalAttempt` is
    // false, so the observation would simply never run again, with nothing
    // anywhere going red. AGENTS.md's *"a check that fails when the thing it
    // guards starts working"*. Do not "simplify" this to `isFinalAttempt`.
    //
    // The guard is also what keeps the seam correct if the discard is ever
    // reverted — the reversal path in RULINGS restores the retries and this
    // predicate keeps the measurement at one line per visit either way.
    if (shouldObserveFailureCost(category, attemptsMade)) {
      const failureCost = await observeFailedVisitUsage({
        visitId,
        category,
        errorName: err instanceof Error ? err.name : null,
      });
      logFailedVisitCost(visitId, currentLayer, failureCost);
    }

    // Best-effort admin alert. notifyAdminOnFailure swallows every
    // failure path internally — a misconfigured Resend account must
    // never mask the underlying pipeline error in Sentry.
    void prisma.user
      .findUnique({
        where: { id: visit.userId },
        select: { email: true },
      })
      .then((u: { email: string } | null) =>
        notifyAdminOnFailure({
          visitId,
          userId: visit.userId,
          userEmail: u?.email ?? null,
          practiceId: visit.user?.practiceId ?? null,
          layer: currentLayer,
          category,
          scrubbedError: redactPhi(
            err instanceof Error ? err.message : String(err ?? '')
          ),
          audioDurationSec: null,
        })
      )
      .catch((notifyErr: unknown) => {
        console.error(
          '[transcribe-md-worker] admin-notify outer catch:',
          redactPhi(notifyErr instanceof Error ? notifyErr.message : notifyErr)
        );
      });

    // FIND-P1-014: if FAILED-state persist failed, surface the
    // persist error to BullMQ. The visit row remains in its
    // non-terminal status (POLISHING / AUTOMATING / etc.) until the
    // stuck-visit watchdog catches it at the 15-min threshold and
    // force-fails it. Re-throwing here (rather than the original
    // `err`) gives BullMQ the persist context as the job's proximate
    // failure; the original error is already in Sentry.
    if (!persistOk) {
      throw persistErr;
    }

    // ── B8 step 3c — AND NOW THE LOG LINE ABOVE IS TRUE ────────────────────
    // `permanent failure, fail-fast (skipping BullMQ retries)` has been emitted
    // since T-M23.A and the retries happened anyway — a bare `throw err` hands
    // the error back to BullMQ, which retries it up to `attempts`. Measured on
    // QA 2026-08-13: three attempts, five seconds apart, each one logging that
    // it was skipping them.
    //
    // The marker is what BullMQ reads to stop; see `unrecoverable.ts` for why
    // it satisfies BOTH arms of bullmq's check and why subclassing would
    // silently satisfy only one.
    //
    // ⚠️ IT IS BELOW THE `persistErr` THROW ON PURPOSE. A failed FAILED-state
    // write is a database blip, not the permanent error, and it MUST still be
    // retried — otherwise the visit sits in a non-terminal status until the
    // 15-minute watchdog force-fails it. The predicate carries `persistOk`
    // anyway so it cannot be broken by moving this call.
    if (shouldDiscardPermanentJob(category, persistOk)) {
      throw asUnrecoverable(err);
    }

    throw err;
  }
}

/**
 * B8 step 3 — emit what a failed visit cost us, and whose fault it was.
 *
 * ⚠️ THIS IS THE ONLY PLACE THE OBSERVATION GOES, WHICH IS THE ITEM'S POINT.
 * It is a log line, not a ledger row: the number is being MEASURED, not
 * charged. When a month of these exists, the decision `billing-failure.ts`
 * defers — whether an `input`-accountable failure should ever be billed — can
 * be made from data instead of from a guess.
 *
 * ⚠️ THE `ours` TOTAL IS THE ONE THAT MATTERS AND IT IS DELIBERATELY THE EASY
 * ONE TO SUM. It is the money our own blips and outages burned; if it dwarfs
 * the `input` total then charging for failures was never the interesting
 * question and this item's refusal to charge was the whole answer.
 *
 * PHI-safe: ids, an enum, an integer and a fixed reason string. The `failed`
 * arm's detail is a caught error's message, so it is scrubbed like every other
 * error text this worker emits.
 */
function logFailedVisitCost(
  visitId: string,
  layer: string,
  observation: FailedVisitObservation
): void {
  if (observation.observed === 'failed') {
    // Loud, and deliberately not silent: this is the measurement itself
    // failing, so the absence of a cost line below is explained rather than
    // looking like a free failure.
    console.warn(
      `[transcribe-md-worker] failure-cost observation FAILED visit=${visitId}: ${redactPhi(
        observation.detail
      )}`
    );
    return;
  }
  if (observation.observed === 'not_started') {
    log.info('transcribe-md-worker', 'failure cost', {
      visitId,
      layer,
      accountability: observation.accountability,
      // Named rather than omitted — "no meter read" and "meter read as zero"
      // are different facts and a reader must not have to infer which.
      // ⚠️ A STRING, like every other arm's. The priced arms must emit
      // `.toString()` because JSON cannot serialise a bigint, so a bare `0`
      // here would give one log key two types and break any consumer that
      // parses the field rather than eyeballing it.
      wouldChargeMicroUsd: '0',
      note: 'admission refused before any vendor call',
    });
    return;
  }
  if (observation.observed === 'priced') {
    log.info('transcribe-md-worker', 'failure cost', {
      visitId,
      layer,
      accountability: observation.accountability,
      wouldChargeMicroUsd: observation.wouldChargeMicroUsd.toString(),
      componentCount: observation.componentCount,
      charged: false,
    });
    return;
  }
  log.info('transcribe-md-worker', 'failure cost', {
    visitId,
    layer,
    accountability: observation.accountability,
    unpriceable: observation.reason,
    pricedSoFarMicroUsd: observation.pricedSoFarMicroUsd.toString(),
    charged: false,
  });
}

/** Maps `currentLayer` (the worker's pipeline tracker — 'L1', 'L2',
 *  'automation', etc.) to a human-readable phrase used in the
 *  FAILED-state banner. Never includes any content from the thrown
 *  error, so PHI can't bleed into the UI. Doctors see a layer name,
 *  ops + Sentry see the full scrubbed error + stack.
 *
 *  The `category` argument tunes the call-to-action sentence so a
 *  permanent / provider-down failure says something more useful
 *  than a generic "try retrying". Falls back to the original copy
 *  for unknown / transient cases so existing UI snapshots still
 *  match. */
function buildUserFacingFailureReason(
  currentLayer: string,
  category: ErrorCategory = 'transient',
  err?: unknown
): string {
  // Round 3 PR-D — A06-P0-001 empty-transcript guard. PipelineRejectError
  // carries a doctor-actionable humanReason ("Recording is 1.4s; need at
  // least 3s ..."). Use it verbatim so the visit banner tells the doctor
  // exactly what happened, not the generic "audio may be corrupt" copy.
  if (
    err instanceof Error &&
    err.name === 'PipelineRejectError' &&
    typeof (err as unknown as { humanReason?: unknown }).humanReason === 'string'
  ) {
    return (err as unknown as { humanReason: string }).humanReason;
  }

  // Q1 #09.1: a content-policy refusal is NOT an audio/format problem —
  // the generic "permanent" copy ("file may be corrupt") would mislead.
  // Give the doctor an accurate, actionable banner.
  if (err instanceof Error && err.name === 'AnthropicRefusalError') {
    return 'Processing was declined by the AI provider’s safety system for this visit’s content. This is not an audio problem — please review the recording/notes, and if the content is clinically appropriate, contact support.';
  }

  // ── B8 — A BILLING REFUSAL IS NOT AN AUDIO PROBLEM EITHER ────────────────
  // ⚠️ THE SAME DEFECT THE BRANCH ABOVE EXISTS TO FIX, ARRIVING AGAIN THROUGH A
  // NEW ERROR CLASS. Admission refuses at `currentLayer='init'` with
  // `category='permanent'`, so without this branch the fall-through below
  // produces, verbatim:
  //
  //     "Processing failed during setup. The audio file may be corrupt or in
  //      an unsupported format — please re-upload to try again."
  //
  // Every clause of that is false for a practice that is out of credit, and the
  // instruction is actively harmful: re-uploading costs the doctor the work
  // again and fails identically, permanently, because the wallet is what is
  // empty. `visit-failed-view.tsx:130` renders this string as the banner body
  // (`{reason ?? copy.body}`), so it is what the doctor reads, not an ops note.
  //
  // ⚠️ AND IT IS THE MIRROR OF THE MISFILING RULING 95(d) ALREADY FORBADE.
  // `billing-pipeline.ts`'s header refuses to file a system fault under
  // "insufficient balance" because that "would tell a paid-up doctor they are
  // out of credit". This is the same lie pointed the other way — telling an
  // out-of-credit doctor their audio is corrupt — and the fix is symmetrical.
  //
  // Read structurally off the error, never by matching its message.
  if (err instanceof Error && err.name === 'BillingAdmissionError') {
    const reason = (err as Error & { reason?: unknown }).reason;
    // OUR fault, and it may clear on its own — `categorizeError` already makes
    // this one `transient`, so the CTA below is a retry rather than a dead end.
    if (reason === 'balance_unreadable') {
      return 'We couldn’t verify this practice’s billing balance, so processing was held rather than started. This is a problem on our side, not with your recording — please try again in a few minutes, and contact support if it persists.';
    }
    // The practice holds money no debit path can draw on. Deliberately NOT
    // folded into the copy below: `billing-balance.ts` keeps this refusal
    // separate precisely because naming it makes a configuration bug visible,
    // and "you are out of credit" said to a funded practice is a lie that
    // reconciles.
    if (reason === 'credit_not_spendable') {
      return 'This practice holds credit that can’t be applied to new visits, so processing was not started. Your recording is saved and is not the problem — please contact support so we can release the balance.';
    }
    return 'This practice is out of processing credit, so this visit was not started. Your recording is saved and is not the problem — re-uploading will not help. Add credit to the practice, then retry this visit.';
  }

  const phraseByLayer: Record<string, string> = {
    init: 'setup',
    L1: 'transcription',
    L1b: 'transcription',
    L2: 'speaker identification',
    L3: 'entity extraction',
    L4: 'SOAP drafting',
    L5: 'clinical audit',
    L6: 'polish',
    automation: 'codes / Rx / referrals generation',
    finalize: 'finalization',
  };
  const phrase = phraseByLayer[currentLayer] ?? 'processing';
  if (category === 'permanent') {
    return `Processing failed during ${phrase}. The audio file may be corrupt or in an unsupported format — please re-upload to try again.`;
  }
  if (category === 'provider_down') {
    return `Processing failed during ${phrase}. Our transcription provider is temporarily unavailable; please try again in a few minutes.`;
  }
  return `Processing failed during ${phrase}. Try retrying this visit, or contact support if it keeps failing.`;
}

/** T-M12 — start the MinIO orphan cleanup worker + schedule the
 *  recurring job. No-op unless MINIO_ORPHAN_CLEANUP_ENABLED=true, so
 *  production deployments stay off until ops flips the flag. */
async function startCleanupWorker(): Promise<void> {
  // T-M17.3: the cleanup worker now handles TWO job types on the
  // shared CLEANUP_QUEUE_NAME — MinIO orphan sweeps (T-M12) and
  // stale-visit sweeps (T-M17.3). Start the worker if EITHER is
  // enabled; register each scheduler independently below.
  if (
    !CLEANUP_ENABLED &&
    !STALE_VISIT_CLEANUP_ENABLED &&
    !RETENTION_SWEEP_ENABLED &&
    !STUCK_VISIT_WATCHDOG_ENABLED
  ) {
    log.info('ops:cleanup', 'disabled', {
      reason:
        'all four cleanup flags off (MINIO_ORPHAN_CLEANUP_ENABLED, STALE_VISIT_CLEANUP_ENABLED, RETENTION_SWEEP_ENABLED, STUCK_VISIT_WATCHDOG_ENABLED)',
    });
    return;
  }

  const cleanupWorker = new Worker(
    CLEANUP_QUEUE_NAME,
    async (job) => {
      if (job.name === JOB_MINIO_ORPHAN_CLEANUP) {
        // Read env on every run so ops can toggle dryRun between
        // scheduled invocations without touching the scheduler.
        const dryRun =
          (process.env.MINIO_ORPHAN_CLEANUP_DRY_RUN ?? 'true').toLowerCase() !==
          'false';
        const retentionDays = Number.parseInt(
          process.env.MINIO_ORPHAN_CLEANUP_RETENTION_DAYS ?? '30',
          10
        );
        await withTimeout(
          runMinioOrphanCleanup({ dryRun, retentionDays }),
          CLEANUP_TIMEOUT_MS,
          'minio-orphan-cleanup'
        );
        // T-M18.2 A13: mark "I ran" so /api/health can surface a
        // silently-dead cron.
        await recordCleanupHeartbeat('minio-orphan-cleanup', {
          dryRun,
          retentionDays,
        });
        return;
      }
      if (job.name === JOB_STALE_VISIT_CLEANUP) {
        const result = await withTimeout(
          runStaleVisitCleanup(),
          STALE_VISIT_CLEANUP_TIMEOUT_MS,
          'stale-visit-cleanup'
        );
        await recordCleanupHeartbeat('stale-visit-cleanup', {
          abandoned: result.abandoned.deleted,
          trash: result.trash.deleted,
          accountDeletions: result.accountDeletions.deleted,
        });
        return;
      }
      if (job.name === JOB_RETENTION_SWEEP) {
        const result = await withTimeout(
          runRetentionSweep(),
          RETENTION_SWEEP_TIMEOUT_MS,
          'retention-sweep'
        );
        await recordCleanupHeartbeat('retention-sweep', {
          found: result.found,
          audioDeleted: result.audioDeleted,
          minioFailures: result.minioFailures,
        });
        return;
      }
      if (job.name === JOB_STUCK_VISIT_WATCHDOG) {
        const result = await withTimeout(
          runStuckVisitWatchdog(),
          STUCK_VISIT_WATCHDOG_TIMEOUT_MS,
          'stuck-visit-watchdog'
        );
        // Heartbeat write is intentionally conditional: with the cron
        // running every minute, an always-on heartbeat would generate
        // 1,440 Redis writes/day per worker just for a "scan was 0"
        // signal. Only record when something interesting happened so
        // the /api/health ageSeconds tracks real activity.
        if (result.rescued > 0 || result.errors > 0) {
          await recordCleanupHeartbeat('stuck-visit-watchdog', {
            scanned: result.scanned,
            rescued: result.rescued,
            errors: result.errors,
          });
        }
        return;
      }
      if (job.name === JOB_AUTO_CERTIFY_TWIN) {
        // RULING #127 — auto-certify a freshly compiled twin.
        //
        // ⚠️ TIMEOUT IS GENEROUS BECAUSE THE PROOF IS A LIVE GENERATION. The
        // synthetic test runs an ephemeral visit through the real L4 and the
        // real bridge fill; that is the price of attesting the real path, and it
        // is why this is a job and not part of the upload request.
        //
        // ⚠️ A FAILURE HERE IS NOT A LOST TEMPLATE. Every exit leaves the doctor
        // somewhere they can act: certified, or NEEDS_CONFIRMATION with the
        // reason named on the visit banner and in the audit row.
        const { runAutoCertifyTwin } = await import('@/worker/auto-certify-twin-job');
        const result = await withTimeout(
          runAutoCertifyTwin(job.data as never),
          AUTO_CERTIFY_TIMEOUT_MS,
          'auto-certify-twin'
        );
        console.info(
          `[auto-certify] template=${(job.data as { noteTemplateId?: string }).noteTemplateId} ` +
            `status=${result.status} confirmed=${result.confirmed}` +
            (result.declined.length ? ` declined=${result.declined.length}` : '') +
            (result.reason ? ` reason=${result.reason}` : '')
        );
        return;
      }
      throw new Error(`Unknown cleanup job name: ${job.name}`);
    },
    {
      connection: getSharedRedisConnection(),
      concurrency: 1,
    }
  );

  cleanupWorker.on('failed', (job, err) => {
    console.error(
      `[ops:cleanup] job ${job?.name}/${job?.id} failed:`,
      redactPhi(err instanceof Error ? err.message : err)
    );
  });

  // ── T-M12 MinIO orphan sweep (opt-in) ─────────────────────────
  if (CLEANUP_ENABLED) {
    await getCleanupQueue().upsertJobScheduler(
      'minio-orphan-cleanup',
      { pattern: CLEANUP_CRON, tz: 'UTC' },
      {
        name: JOB_MINIO_ORPHAN_CLEANUP,
        data: {},
        opts: { attempts: 1 },
      }
    );
    log.info('ops:minio-cleanup', 'enabled', {
      cron: CLEANUP_CRON,
      tz: 'UTC',
      retentionDays: CLEANUP_RETENTION_DAYS,
      dryRun: CLEANUP_DRY_RUN,
    });
  } else {
    log.info('ops:minio-cleanup', 'disabled', {
      reason: 'MINIO_ORPHAN_CLEANUP_ENABLED != "true"',
    });
  }

  // ── T-M17.3 stale-visit sweep (default: on) ───────────────────
  if (STALE_VISIT_CLEANUP_ENABLED) {
    await getCleanupQueue().upsertJobScheduler(
      'stale-visit-cleanup',
      { pattern: STALE_VISIT_CLEANUP_CRON, tz: 'UTC' },
      {
        name: JOB_STALE_VISIT_CLEANUP,
        data: {},
        opts: { attempts: 1 },
      }
    );
    log.info('ops:stale-visit-cleanup', 'T-M17.3 cleanup job scheduled', {
      cron: STALE_VISIT_CLEANUP_CRON,
      tz: 'UTC',
      timeoutMs: STALE_VISIT_CLEANUP_TIMEOUT_MS,
    });
  } else {
    log.info('ops:stale-visit-cleanup', 'disabled', {
      reason: 'STALE_VISIT_CLEANUP_ENABLED == "false"',
    });
  }

  // ── T-M18.1 A3 audio retention sweep (default: on) ────────────
  if (RETENTION_SWEEP_ENABLED) {
    await getCleanupQueue().upsertJobScheduler(
      'retention-sweep',
      { pattern: RETENTION_SWEEP_CRON, tz: 'UTC' },
      {
        name: JOB_RETENTION_SWEEP,
        data: {},
        opts: { attempts: 1 },
      }
    );
    log.info('ops:retention-sweep', 'T-M18.1 retention sweep scheduled', {
      cron: RETENTION_SWEEP_CRON,
      tz: 'UTC',
      timeoutMs: RETENTION_SWEEP_TIMEOUT_MS,
      // Single source of truth — same resolver the sweep uses, so the
      // logged window can't drift from the actual deletion behavior (the
      // pre-2026-06-11 duplicate hardcoded '180' here logged 180 while the
      // sweep already ran at its 90-day default).
      retentionDays: resolveRetentionDays(),
    });
  } else {
    log.info('ops:retention-sweep', 'disabled', {
      reason: 'RETENTION_SWEEP_ENABLED == "false"',
    });
  }

  // ── 2026-05-12 stuck-visit watchdog (default: on) ─────────────
  if (STUCK_VISIT_WATCHDOG_ENABLED) {
    await getCleanupQueue().upsertJobScheduler(
      'stuck-visit-watchdog',
      { pattern: STUCK_VISIT_WATCHDOG_CRON, tz: 'UTC' },
      {
        name: JOB_STUCK_VISIT_WATCHDOG,
        data: {},
        opts: { attempts: 1 },
      }
    );
    log.info('ops:stuck-visit-watchdog', 'scheduled', {
      cron: STUCK_VISIT_WATCHDOG_CRON,
      tz: 'UTC',
      timeoutMs: STUCK_VISIT_WATCHDOG_TIMEOUT_MS,
      thresholdMin: Math.round(
        Number.parseInt(
          process.env.STUCK_VISIT_THRESHOLD_MS ?? String(15 * 60 * 1000),
          10,
        ) / 60_000,
      ),
    });
  } else {
    log.info('ops:stuck-visit-watchdog', 'disabled', {
      reason: 'STUCK_VISIT_WATCHDOG_ENABLED == "false"',
    });
  }
}

/** Round 3 PR-H — A11-P1 worker liveness heartbeat.
 *  Writes a Unix-timestamp file every 15s. The compose healthcheck reads it and
 *  treats the worker as unhealthy when the timestamp is >60s stale, so a
 *  deadlocked event loop (Prisma deadlock, infinite-loop guard, hung Anthropic
 *  stream) surfaces as an unhealthy container instead of a silently-stuck worker.
 *
 *  F6 (full-qa-20260604T202447Z) — make the heartbeat HONEST:
 *   1. START gating (in main): it is only started after worker.waitUntilReady()
 *      resolves, so a worker that fails boot (missing AUTH_SECRET → module-load
 *      crash) or can't reach Redis never writes it → healthcheck UNHEALTHY.
 *   2. Per-tick liveness: each tick SKIPS the write while the shared Redis
 *      connection isn't 'ready', so a persistent disconnect lets the file go
 *      stale (unhealthy) within the 60s window. Transient reconnects are
 *      tolerated — the 60s window absorbs ~3 missed 15s ticks, so a healthy
 *      worker (whose status is 'ready') never flaps unhealthy.
 *  Returns a handle so a graceful 'closed' can stop refreshing.
 *  (Was: a bare setInterval(...).unref() started BEFORE the Redis connection,
 *  so a crash-looping or disconnected worker still reported HEALTHY.) */
async function startHeartbeat(
  connection: ReturnType<typeof getSharedRedisConnection>
): Promise<{ stop: () => void }> {
  const HEARTBEAT_PATH = '/tmp/worker-heartbeat';
  const HEARTBEAT_INTERVAL_MS = 15_000;
  const tick = async () => {
    // Only assert liveness while Redis is genuinely up; otherwise let the file
    // go stale rather than claim a health the disconnected worker doesn't have.
    if (connection.status !== 'ready') return;
    try {
      const fs = await import('node:fs/promises');
      await fs.writeFile(HEARTBEAT_PATH, String(Date.now()));
    } catch (err) {
      console.error(
        '[transcribe-md-worker] heartbeat write failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
    }
  };
  await tick();
  const timer = setInterval(() => void tick(), HEARTBEAT_INTERVAL_MS);
  timer.unref();
  return { stop: () => clearInterval(timer) };
}

async function main() {
  log.info('transcribe-md-worker', 'booting');
  // Flag-vs-capability assertion (#311 lesson: a flag flipped ON against a
  // stale image that lacks the capability is SILENTLY inert — no error, no
  // log). This line is the operator check: after any flag flip + recreate,
  // its presence proves the image carries the capability; its ABSENCE on a
  // flag-on deploy means a stale image. A flag-on/capability-missing
  // combination logs at error level.
  {
    const flags: { flag: string; on: boolean; capability: () => boolean }[] = [
      {
        flag: 'TRANSCRIBE_MD_EVIDENCE_ANCHORS',
        on: evidenceAnchorsEnabled(),
        capability: () => ANCHOR_GENERATION_ADDENDUM.length > 0,
      },
      {
        flag: 'TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED',
        on: process.env.TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED === 'true',
        capability: () => true, // shipped with the kill-switch itself
      },
    ];
    for (const f of flags) {
      let present = false;
      try { present = f.capability(); } catch { present = false; }
      const line = { flag: f.flag, enabled: f.on, capabilityPresent: present };
      if (f.on && !present) {
        log.error('transcribe-md-worker', 'FLAG ON BUT CAPABILITY MISSING — stale image?', line);
      } else {
        log.info('transcribe-md-worker', 'feature-flag state', line);
      }
    }
  }
  await ensureBucket();
  log.info('transcribe-md-worker', 'bucket ready');

  const worker = new Worker<ProcessVisitPayload>(
    QUEUE_NAME,
    async (job) => {
      if (job.name !== JOB_PROCESS_VISIT) {
        throw new Error(`Unknown job name: ${job.name}`);
      }
      await withTimeout(
        processVisit(job),
        JOB_TIMEOUT_MS,
        `visit ${job.data.visitId}`
      );
    },
    {
      connection: getSharedRedisConnection(),
      concurrency: CONCURRENCY,
    }
  );

  worker.on('completed', (job) => {
    log.info('transcribe-md-worker', 'visit completed', {
      jobId: job.id,
      visitId: job.data.visitId,
    });
  });
  worker.on('failed', (job, err) => {
    console.error(
      `[transcribe-md-worker] job ${job?.id} visit ${job?.data.visitId} FAILED:`,
      redactPhi(err instanceof Error ? err.message : err)
    );
    // PR-L: when the job will not run again, ship it to the DLQ so an
    // operator can see + decide via /admin/queues. The `failed` event
    // fires AFTER each failed attempt. Best-effort: if Redis is unhappy
    // we log + drop rather than crash the worker (the next failure will
    // retry the DLQ enqueue too).
    //
    // ⚠️ B8 step 3c — THIS CONDITION USED TO BE `attemptsMade >= opts.attempts`
    // AND THE DISCARD BROKE IT SILENTLY. A discarded permanent failure ends at
    // `attemptsMade = 1` of 3, so `1 >= 3` is false and it never reached the
    // DLQ. Measured on QA: jobs 413/415/416 landed in
    // `bull:dlq-permanent-failures`; the discarded 414 did not — every
    // insufficient-balance refusal would have vanished from the one page B8's
    // gate calls load-bearing for money.
    //
    // "The retry budget is exhausted" and "this job will not run again" were
    // the same sentence until a job could stop for a second reason. They are
    // not now, and `shouldDeadLetter` is written against the second one.
    if (
      job &&
      typeof job.attemptsMade === 'number' &&
      typeof job.opts?.attempts === 'number' &&
      shouldDeadLetter(
        job.attemptsMade,
        job.opts.attempts,
        isUnrecoverableMarker(err)
      )
    ) {
      void enqueueDlq({
        originalQueue: QUEUE_NAME,
        originalJobId: job.id ?? null,
        originalJobName: job.name,
        originalPayload: job.data,
        // Audit P0-A (2026-05-13): the DLQ row is DURABLE storage
        // reviewed via /admin/queues. Prisma errors + Anthropic 400
        // bodies frequently quote prompt fragments (transcript +
        // SOAP draft), so an unscrubbed err.message leaks PHI into
        // an admin-visible table indefinitely. redactPhi keeps the
        // operational signal (column name, error class, generic
        // shape) and drops the verbatim content.
        lastError: redactPhi(
          err instanceof Error
            ? err.message
            : String(err ?? '(no error message)'),
        ),
        exhaustedAt: new Date().toISOString(),
        totalAttempts: job.opts.attempts,
      }).catch((dlqErr) => {
        console.error(
          `[transcribe-md-worker] DLQ enqueue failed for job ${job.id}:`,
          redactPhi(dlqErr instanceof Error ? dlqErr.message : dlqErr)
        );
      });
    }
  });

  // F6 (full-qa-20260604T202447Z) — honest heartbeat. Do NOT write the liveness
  // heartbeat until the worker is GENUINELY ready: waitUntilReady() resolves
  // only once both the main + blocking Redis connections are up (the worker can
  // fetch + process jobs). A worker that fails boot (missing AUTH_SECRET →
  // module-load crash) or can't reach Redis never reaches here → never writes
  // the heartbeat → the file-freshness healthcheck correctly reports UNHEALTHY.
  // (Was: startHeartbeat ran before the Worker connected, so a boot/Redis
  // failure still looked healthy.)
  await worker.waitUntilReady();
  log.info('transcribe-md-worker', 'ready — listening on queue', {
    queue: QUEUE_NAME,
    concurrency: CONCURRENCY,
  });
  const heartbeat = await startHeartbeat(getSharedRedisConnection());
  // Graceful shutdown stops the heartbeat so the file goes stale (unhealthy)
  // within the 60s window. A crash kills the process (→ stale too); a persistent
  // Redis disconnect is handled inside the tick (skips the write while down).
  worker.on('closed', () => heartbeat.stop());

  // T-M12 — schedule cleanup AFTER the main worker is up. Cleanup
  // failure should never block pipeline processing.
  await startCleanupWorker();
}

main().catch((err) => {
  console.error(
    '[transcribe-md-worker] fatal:',
    redactPhi(err instanceof Error ? err.message : err)
  );
  process.exit(1);
});
