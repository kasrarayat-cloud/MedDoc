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
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import type { DeepgramBatchResponse, DeepgramUtterance } from '@meddoc/ai';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';

import {
  QUEUE_NAME,
  JOB_PROCESS_VISIT,
  CLEANUP_QUEUE_NAME,
  JOB_MINIO_ORPHAN_CLEANUP,
  JOB_STALE_VISIT_CLEANUP,
  JOB_RETENTION_SWEEP,
  getSharedRedisConnection,
  getCleanupQueue,
  type ProcessVisitPayload,
} from '@/lib/queue';
import { ensureBucket } from '@/lib/minio';
import { runMinioOrphanCleanup } from '@/worker/cleanup/minio-orphans';
import { runStaleVisitCleanup } from '@/worker/cleanup/stale-visits';
import { runRetentionSweep } from '@/worker/cleanup/retention-sweep';
import {
  isLayerComplete,
  logSkipSummary,
  logSkippedLayer,
  type LayerSkipState,
  type PipelineLayer,
} from '@/worker/layer-skip';
import { runLayer1Transcribe } from '@/worker/layers/01-transcribe';
import { runLayer1bTranscribeDictation } from '@/worker/layers/01b-transcribe-dictation';
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

// T-M18.1 A3 — audio retention sweep (SIGNED visits past 180d).
// Opt-out via env. Cron offset 1h from the T-M17.3 stale-visit sweep
// so the two don't contend for DB + MinIO connections.
const RETENTION_SWEEP_ENABLED =
  (process.env.RETENTION_SWEEP_ENABLED ?? 'true').toLowerCase() !== 'false';
const RETENTION_SWEEP_CRON =
  process.env.RETENTION_SWEEP_CRON?.trim() || '0 4 * * *';
const RETENTION_SWEEP_TIMEOUT_MS = 10 * 60 * 1000;

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

/** T-M13 — load every layer's checkpoint column in one query. Returns
 *  a LayerSkipState the skip checks consume. An all-nulls shape on
 *  the first attempt ⇒ every isLayerComplete() returns false ⇒ the
 *  pipeline runs end-to-end as before. A partially-populated shape
 *  on retry ⇒ skips fire for completed layers. */
async function loadResumeState(visitId: string): Promise<LayerSkipState> {
  const row = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      transcriptRaw: true,
      transcriptText: true,
      speakerMap: true,
      entities: true,
      soapDraft: true,
      critique: true,
      soapFinal: true,
      icdCodes: true,
      cptCodes: true,
      rxDrafts: true,
      referrals: true,
      patientSummary: true,
    },
  });
  if (!row) {
    // Defensive — if the row disappeared between the top-level
    // findUnique and here, fall back to all-nulls so everything runs
    // fresh. The caller's next DB write will error, which is fine.
    return {
      transcriptRaw: null,
      transcriptText: null,
      speakerMap: null,
      entities: null,
      soapDraft: null,
      critique: null,
      soapFinal: null,
      icdCodes: null,
      cptCodes: null,
      rxDrafts: null,
      referrals: null,
      patientSummary: null,
    };
  }
  return row as LayerSkipState;
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
      // T-M13: previously cleared the five L7 columns here so a retry
      // wouldn't carry stale 'failed' entries. With per-layer resume
      // (below), successful L7 outputs are a CHECKPOINT — wiping them
      // would defeat resumability. Failed L7 layers are nulled by the
      // per-task catch (clearAutomationColumn) so the skip check
      // naturally re-runs only those. confidenceScores IS still
      // cleared because it's rebuilt from scratch in the roll-up
      // below, and stale failed entries would otherwise leak through.
      confidenceScores: null,
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
  const resumeState = await loadResumeState(visitId);
  const skipped: PipelineLayer[] = [];

  try {
    // -------------------------------------------------------------------
    // Per-mode input stage — produces (entities, contextText).
    // -------------------------------------------------------------------
    let entities: ExtractedEntities;
    let contextText: string;

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
          audioKey: visit.audioKey!,
          audioMimeType: visit.audioMimeType!,
        });
      }

      // Always re-read transcriptRaw — whether L1 ran or was skipped,
      // downstream layers need the utterances.
      const withTranscript = await prisma.transcribeVisit.findUnique({
        where: { id: visitId },
        select: { transcriptRaw: true, speakerMap: true },
      });
      const raw = withTranscript?.transcriptRaw as
        | DeepgramBatchResponse
        | null
        | undefined;
      const utterances: DeepgramUtterance[] = raw?.results?.utterances ?? [];

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
          utterances,
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
          mode: 'conversation',
          utterances,
          speakerMap,
        });
        entities = l3.entities;
        contextText = l3.contextText;
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
          dictationAudioKey: visit.dictationAudioKey!,
          // Dictations come from browser MediaRecorder → webm/opus.
          // Deepgram auto-detects encoding from the Content-Type header.
          dictationMimeType:
            process.env.TRANSCRIBE_MD_DICTATION_MIME ?? 'audio/webm',
        });
        dictationText = r.transcript;
      }

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
          mode: 'text',
          rawText: visit.rawTextInput!,
        });
        entities = l3.entities;
        contextText = l3.contextText;
      }
    }

    // -------------------------------------------------------------------
    // Layers 4-6 — mode-agnostic.
    // -------------------------------------------------------------------
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.DRAFTING },
    });
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
        specialty: visit.specialty,
        roleLabeledTranscript: contextText,
        entities,
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
        specialty: visit.specialty,
        soapDraft,
        roleLabeledTranscript: contextText,
        entities,
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
        soapDraft,
        critique,
      });
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
    const results = await Promise.allSettled(toRun.map((t) => t.run()));

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

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: {
        status: TranscribeVisitStatus.READY,
        processingFinishedAt: new Date(),
        processingCostCents: totalCents,
        confidenceScores: confidenceScores as unknown as object,
      },
    });

    // T-M13 summary line — logs only when at least one layer was
    // skipped, so happy-path first attempts stay quiet.
    logSkipSummary(visitId, attempt, skipped);
  } catch (err) {
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
    captureWorkerException(err, { visitId, layer: currentLayer });
    await prisma.transcribeVisit
      .update({
        where: { id: visitId },
        data: {
          status: TranscribeVisitStatus.FAILED,
          processingFinishedAt: new Date(),
          needsReview: true,
          // T-M18.1 A2: DO NOT write the raw err.message to reviewReason
          // — it renders as the failure banner on /visits/[id] and a
          // Prisma/Deepgram/Anthropic error can quote patient content
          // (PHI in the DB + UI). Instead, write a phase-tagged
          // user-friendly string derived only from currentLayer.
          reviewReason: buildUserFacingFailureReason(currentLayer),
        },
      })
      .catch((writeErr: unknown) => {
        console.error(
          '[transcribe-md-worker] failed to write FAILED state:',
          redactPhi(writeErr instanceof Error ? writeErr.message : writeErr)
        );
      });
    throw err;
  }
}

/** Maps `currentLayer` (the worker's pipeline tracker — 'L1', 'L2',
 *  'automation', etc.) to a human-readable phrase used in the
 *  FAILED-state banner. Never includes any content from the thrown
 *  error, so PHI can't bleed into the UI. Doctors see a layer name,
 *  ops + Sentry see the full scrubbed error + stack. */
function buildUserFacingFailureReason(currentLayer: string): string {
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
    !RETENTION_SWEEP_ENABLED
  ) {
    log.info('ops:cleanup', 'disabled', {
      reason:
        'all three cleanup flags off (MINIO_ORPHAN_CLEANUP_ENABLED, STALE_VISIT_CLEANUP_ENABLED, RETENTION_SWEEP_ENABLED)',
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
        return;
      }
      if (job.name === JOB_STALE_VISIT_CLEANUP) {
        await withTimeout(
          runStaleVisitCleanup(),
          STALE_VISIT_CLEANUP_TIMEOUT_MS,
          'stale-visit-cleanup'
        );
        return;
      }
      if (job.name === JOB_RETENTION_SWEEP) {
        await withTimeout(
          runRetentionSweep(),
          RETENTION_SWEEP_TIMEOUT_MS,
          'retention-sweep'
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
      err
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
      retentionDays: Number.parseInt(
        process.env.AUDIO_RETENTION_DAYS?.trim() || '180',
        10
      ),
    });
  } else {
    log.info('ops:retention-sweep', 'disabled', {
      reason: 'RETENTION_SWEEP_ENABLED == "false"',
    });
  }
}

async function main() {
  log.info('transcribe-md-worker', 'booting');
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
      err
    );
  });

  log.info('transcribe-md-worker', 'listening on queue', {
    queue: QUEUE_NAME,
    concurrency: CONCURRENCY,
  });

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
