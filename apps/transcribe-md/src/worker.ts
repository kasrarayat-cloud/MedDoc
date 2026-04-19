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
import { Worker, type Job } from 'bullmq';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import type { DeepgramBatchResponse, DeepgramUtterance } from '@meddoc/ai';

import {
  QUEUE_NAME,
  JOB_PROCESS_VISIT,
  CLEANUP_QUEUE_NAME,
  JOB_MINIO_ORPHAN_CLEANUP,
  getSharedRedisConnection,
  getCleanupQueue,
  type ProcessVisitPayload,
} from '@/lib/queue';
import { ensureBucket } from '@/lib/minio';
import { runMinioOrphanCleanup } from '@/worker/cleanup/minio-orphans';
import { runLayer1Transcribe } from '@/worker/layers/01-transcribe';
import { runLayer1bTranscribeDictation } from '@/worker/layers/01b-transcribe-dictation';
import {
  runLayer2SpeakerRoles,
  type SpeakerMap,
} from '@/worker/layers/02-speaker-roles';
import { runLayer3ExtractEntities } from '@/worker/layers/03-extract-entities';
import { runLayer4GenerateSoap } from '@/worker/layers/04-generate-soap';
import { runLayer5SelfCritique } from '@/worker/layers/05-self-critique';
import { runLayer6Polish } from '@/worker/layers/06-polish';
import { runLayer7aIcdCoding } from '@/worker/layers/07a-icd-coding';
import { runLayer7bCptCoding } from '@/worker/layers/07b-cpt-coding';
import { runLayer7cRxDrafting } from '@/worker/layers/07c-rx-drafting';
import { runLayer7dReferrals } from '@/worker/layers/07d-referrals';
import { runLayer7ePatientSummary } from '@/worker/layers/07e-patient-summary';

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
const JOB_TIMEOUT_MS = Number.parseInt(
  process.env.TRANSCRIBE_MD_JOB_TIMEOUT_MS ?? String(15 * 60 * 1000),
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

async function processVisit(job: Job<ProcessVisitPayload>): Promise<void> {
  const { visitId } = job.data;

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
      user: { select: { practiceId: true } },
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
      // T-M6: a retry should clear any prior-run automation outputs +
      // confidence ledger so a previously-failed layer doesn't carry
      // its stale 'failed' status through to the fresh run.
      icdCodes: null,
      cptCodes: null,
      rxDrafts: null,
      referrals: null,
      patientSummary: null,
      confidenceScores: null,
    },
  });

  try {
    // -------------------------------------------------------------------
    // Per-mode input stage — produces (entities, contextText).
    // -------------------------------------------------------------------
    let entities: Awaited<ReturnType<typeof runLayer3ExtractEntities>>['entities'];
    let contextText: string;

    if (visit.inputMode === 'audio_upload') {
      // L1 — Deepgram with diarize on.
      await runLayer1Transcribe({
        visitId,
        practiceId,
        audioKey: visit.audioKey!,
        audioMimeType: visit.audioMimeType!,
      });
      const withTranscript = await prisma.transcribeVisit.findUnique({
        where: { id: visitId },
        select: { transcriptRaw: true },
      });
      const raw = withTranscript?.transcriptRaw as
        | DeepgramBatchResponse
        | null
        | undefined;
      const utterances: DeepgramUtterance[] = raw?.results?.utterances ?? [];

      // L2 — speaker roles.
      await prisma.transcribeVisit.update({
        where: { id: visitId },
        data: { status: TranscribeVisitStatus.EXTRACTING },
      });
      const { speakerMap } = await runLayer2SpeakerRoles({
        visitId,
        practiceId,
        utterances,
      });

      // L3 — conversation entities.
      const l3 = await runLayer3ExtractEntities({
        visitId,
        practiceId,
        mode: 'conversation',
        utterances,
        speakerMap: speakerMap as SpeakerMap,
      });
      entities = l3.entities;
      contextText = l3.contextText;
    } else if (visit.inputMode === 'voice_dictation') {
      // L1' — single-speaker Deepgram.
      const l1b = await runLayer1bTranscribeDictation({
        visitId,
        practiceId,
        dictationAudioKey: visit.dictationAudioKey!,
        // Dictations come from browser MediaRecorder → webm/opus.
        // Deepgram auto-detects encoding from the Content-Type header.
        dictationMimeType:
          process.env.TRANSCRIBE_MD_DICTATION_MIME ?? 'audio/webm',
      });

      // L3 — dictation entities.
      await prisma.transcribeVisit.update({
        where: { id: visitId },
        data: { status: TranscribeVisitStatus.EXTRACTING },
      });
      const l3 = await runLayer3ExtractEntities({
        visitId,
        practiceId,
        mode: 'dictation',
        dictationText: l1b.transcript,
      });
      entities = l3.entities;
      contextText = l3.contextText;
    } else {
      // text_notes — no transcription step.
      const l3 = await runLayer3ExtractEntities({
        visitId,
        practiceId,
        mode: 'text',
        rawText: visit.rawTextInput!,
      });
      entities = l3.entities;
      contextText = l3.contextText;
    }

    // -------------------------------------------------------------------
    // Layers 4-6 — mode-agnostic.
    // -------------------------------------------------------------------
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.DRAFTING },
    });
    const soapDraft = await runLayer4GenerateSoap({
      visitId,
      practiceId,
      specialty: visit.specialty,
      roleLabeledTranscript: contextText,
      entities,
    });

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.CRITIQUING },
    });
    const critique = await runLayer5SelfCritique({
      visitId,
      practiceId,
      specialty: visit.specialty,
      soapDraft,
      roleLabeledTranscript: contextText,
      entities,
    });

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.POLISHING },
    });
    const polished = await runLayer6Polish({
      visitId,
      practiceId,
      soapDraft,
      critique,
    });

    // -------------------------------------------------------------------
    // T-M6 — parallel automation fan-out. Each L7x layer runs
    // independently against the same polished SOAP + entities; a single
    // layer failing never fails the visit. Missing outputs show up as
    // empty columns + a confidenceScores note.
    // -------------------------------------------------------------------
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.AUTOMATING },
    });

    const soapFinalForFanout = polished.soapFinal;
    const entitiesJson = JSON.stringify(entities);

    // Env feature flags — operators can disable any layer without a
    // code change if costs spike or a layer misbehaves in prod.
    const flags = {
      icd: process.env.TM_ENABLE_ICD_CPT !== 'false',
      cpt: process.env.TM_ENABLE_ICD_CPT !== 'false',
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
            specialty: visit.specialty,
            soapFinal: soapFinalForFanout,
            entitiesJson,
          }),
      },
      {
        key: 'rx_drafting',
        enabled: flags.rx,
        run: () =>
          runLayer7cRxDrafting({
            visitId,
            practiceId,
            soapFinal: soapFinalForFanout,
            entitiesJson,
          }),
      },
      {
        key: 'referrals',
        enabled: flags.referrals,
        run: () =>
          runLayer7dReferrals({
            visitId,
            practiceId,
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
            specialty: visit.specialty,
            soapFinal: soapFinalForFanout,
            entitiesJson,
          }),
      },
    ];

    const enabled = tasks.filter((t) => t.enabled);
    const results = await Promise.allSettled(enabled.map((t) => t.run()));

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
      const idx = enabled.indexOf(t);
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
        // stale "almost-populated" row can't mislead the UI.
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

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: {
        status: TranscribeVisitStatus.READY,
        processingFinishedAt: new Date(),
        processingCostCents: totalCents,
        confidenceScores: confidenceScores as unknown as object,
      },
    });
  } catch (err) {
    console.error(`[transcribe-md-worker] visit ${visitId} failed:`, err);
    await prisma.transcribeVisit
      .update({
        where: { id: visitId },
        data: {
          status: TranscribeVisitStatus.FAILED,
          processingFinishedAt: new Date(),
          needsReview: true,
          reviewReason:
            err instanceof Error
              ? err.message.slice(0, 500)
              : 'Unknown error during processing. Try again or contact support.',
        },
      })
      .catch((writeErr: unknown) => {
        console.error(
          '[transcribe-md-worker] failed to write FAILED state:',
          writeErr
        );
      });
    throw err;
  }
}

/** T-M12 — start the MinIO orphan cleanup worker + schedule the
 *  recurring job. No-op unless MINIO_ORPHAN_CLEANUP_ENABLED=true, so
 *  production deployments stay off until ops flips the flag. */
async function startCleanupWorker(): Promise<void> {
  if (!CLEANUP_ENABLED) {
    console.log(
      '[ops:minio-cleanup] disabled (MINIO_ORPHAN_CLEANUP_ENABLED != "true")'
    );
    return;
  }

  const cleanupWorker = new Worker(
    CLEANUP_QUEUE_NAME,
    async (job) => {
      if (job.name !== JOB_MINIO_ORPHAN_CLEANUP) {
        throw new Error(`Unknown cleanup job name: ${job.name}`);
      }
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
    },
    {
      connection: getSharedRedisConnection(),
      concurrency: 1,
    }
  );

  cleanupWorker.on('failed', (job, err) => {
    console.error(
      `[ops:minio-cleanup] job ${job?.id} failed:`,
      err
    );
  });

  // Register (or refresh) the cron schedule. upsertJobScheduler is
  // idempotent — redeploying the worker re-registers with no side
  // effect on in-flight jobs.
  await getCleanupQueue().upsertJobScheduler(
    'minio-orphan-cleanup',
    { pattern: CLEANUP_CRON, tz: 'UTC' },
    {
      name: JOB_MINIO_ORPHAN_CLEANUP,
      data: {},
      opts: { attempts: 1 },
    }
  );

  console.log(
    `[ops:minio-cleanup] enabled, cron="${CLEANUP_CRON}" UTC, ` +
      `retentionDays=${CLEANUP_RETENTION_DAYS}, dryRun=${CLEANUP_DRY_RUN}`
  );
}

async function main() {
  console.log('[transcribe-md-worker] booting…');
  await ensureBucket();
  console.log('[transcribe-md-worker] bucket ready');

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
    console.log(`[transcribe-md-worker] job ${job.id} visit ${job.data.visitId} OK`);
  });
  worker.on('failed', (job, err) => {
    console.error(
      `[transcribe-md-worker] job ${job?.id} visit ${job?.data.visitId} FAILED:`,
      err
    );
  });

  console.log(
    `[transcribe-md-worker] listening on queue "${QUEUE_NAME}" concurrency=${CONCURRENCY}`
  );

  // T-M12 — schedule cleanup AFTER the main worker is up. Cleanup
  // failure should never block pipeline processing.
  await startCleanupWorker();
}

main().catch((err) => {
  console.error('[transcribe-md-worker] fatal:', err);
  process.exit(1);
});
