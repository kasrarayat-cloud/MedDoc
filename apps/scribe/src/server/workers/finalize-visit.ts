// ============================================================================
// Worker: finalize_visit (M4 — full output bundle)
// ----------------------------------------------------------------------------
// Spec §11 fan-out. Runs:
//   Pass 1: transcript cleanup + diarization  [prerequisite, throws on fail]
//   Pass 2: SOAP note                          [prerequisite, throws on fail]
//   Pass 3: parallel fan-out (Promise.allSettled) of:
//     - ICD-10 / CPT coding
//     - Prescription drafts
//     - Referral letters
//     - Patient-facing summary
//
// Each parallel output is isolated: one schema failure or provider
// error doesn't block the others (M4 D1). Failures are persisted as
// OutputError sentinels in ScribeOutput.content and flagged in the
// review UI — the visit still transitions to READY_FOR_REVIEW.
//
// Per-output feature flags (SCRIBE_EXTRACT_{CODING|RX|REFERRALS|PATIENT_SUMMARY})
// short-circuit with a FLAG_OFF sentinel + OUTPUT_SKIPPED_FLAG_OFF audit.
// ============================================================================

import prisma from '@meddoc/db';
import type { OutputType } from '@prisma/client';
import type { SoapNote } from '@meddoc/types';
import type { FinalizeVisitPayload } from '@/lib/queue';

import { runCleanupTranscript } from './pipeline/cleanup-transcript';
import { runGenerateSoap } from './pipeline/generate-soap';
import { runExtractCoding } from './pipeline/extract-coding';
import { runDraftRx } from './pipeline/draft-rx';
import { runDraftReferrals } from './pipeline/draft-referrals';
import { runPatientSummary } from './pipeline/patient-summary';
import {
  isExtractionEnabled,
  type PipelineFailure,
  type PipelineOutcome,
} from './pipeline/types';

function flagOffOutcome(): PipelineFailure {
  return {
    ok: false,
    modelUsed: 'none',
    error: {
      code: 'FLAG_OFF',
      message: 'Extraction disabled by SCRIBE_EXTRACT_* feature flag.',
      attempts: 0,
      occurredAt: new Date().toISOString(),
    },
  };
}

function unexpectedRejectionOutcome(reason: unknown): PipelineFailure {
  return {
    ok: false,
    modelUsed: 'unknown',
    error: {
      code: 'UNKNOWN',
      message: reason instanceof Error ? reason.message : String(reason),
      attempts: 1,
      occurredAt: new Date().toISOString(),
    },
  };
}

async function persistOutcome<T>(args: {
  practiceId: string;
  visitId: string;
  actorId: string;
  type: OutputType;
  outcome: PipelineOutcome<T>;
  templateVersion: string;
}): Promise<void> {
  const { practiceId, visitId, actorId, type, outcome, templateVersion } = args;

  const content = outcome.ok
    ? (outcome.output as unknown)
    : {
        _error: {
          code: outcome.error.code,
          message: outcome.error.message,
          attempts: outcome.error.attempts,
          occurredAt: outcome.error.occurredAt,
        },
      };

  await prisma.scribeOutput.create({
    data: {
      practiceId,
      visitId,
      type,
      content: content as object,
      modelUsed: outcome.modelUsed,
      templateVersion,
    },
  });

  const action = outcome.ok
    ? 'OUTPUT_GENERATED'
    : outcome.error.code === 'FLAG_OFF'
      ? 'OUTPUT_SKIPPED_FLAG_OFF'
      : 'OUTPUT_ERRORED';

  const diff = outcome.ok
    ? {
        type,
        modelUsed: outcome.modelUsed,
        confidence: (outcome.output as { confidence?: string }).confidence ?? null,
      }
    : {
        type,
        modelUsed: outcome.modelUsed,
        errorCode: outcome.error.code,
        attempts: outcome.error.attempts,
      };

  await prisma.scribeAuditEvent.create({
    data: { practiceId, visitId, actorId, action, diff },
  });
}

export async function runFinalizeVisit(payload: FinalizeVisitPayload): Promise<void> {
  const { visitId } = payload;

  const visit = await prisma.scribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      practiceId: true,
      userId: true,
      patientId: true,
      status: true,
      specialtyId: true,
    },
  });
  if (!visit) {
    console.error(`[finalize_visit] visit ${visitId} not found; dropping job`);
    return;
  }

  const [transcript, specialty] = await Promise.all([
    prisma.scribeTranscript.findUnique({ where: { visitId } }),
    prisma.scribeSpecialtyTemplate.findUnique({ where: { id: visit.specialtyId } }),
  ]);
  if (!transcript) throw new Error(`No transcript for visit ${visitId}`);
  if (!specialty) throw new Error(`Specialty ${visit.specialtyId} not found`);

  // --- Pass 1: cleanup (prerequisite — throws on fail) ---
  const { cleaned, model: cleanupModel } = await runCleanupTranscript({
    rawFullText: transcript.rawFullText,
    practiceId: visit.practiceId,
    visitId,
  });

  await prisma.scribeTranscript.update({
    where: { visitId },
    data: {
      segments: cleaned.segments,
      language: cleaned.language,
      provider: `${transcript.provider} → cleaned-by-${cleanupModel}`,
    },
  });

  const cleanedText = cleaned.segments.map((s) => `${s.speaker}: ${s.text}`).join('\n');

  // --- Pass 2: SOAP (prerequisite — throws on fail) ---
  const { soap, model: soapModel } = await runGenerateSoap({
    cleanedText,
    specialtySystemPrompt: specialty.systemPrompt,
    specialtySoapSchema: specialty.soapSchema,
    specialtyRequiredExamElements: specialty.requiredExamElements,
    practiceId: visit.practiceId,
    visitId,
  });

  await persistOutcome({
    practiceId: visit.practiceId,
    visitId,
    actorId: visit.userId,
    type: 'SOAP',
    templateVersion: specialty.version,
    outcome: { ok: true, output: soap, modelUsed: soapModel },
  });

  // --- Pass 3: parallel fan-out (per-output error isolation, D1) ---
  const specialtyIcd10Hints = specialty.defaultIcd10Hints ?? [];

  const codingTask = isExtractionEnabled('CODING')
    ? runExtractCoding({
        cleanedText,
        soap: soap as SoapNote,
        specialtyDefaultIcd10Hints: specialtyIcd10Hints,
        practiceId: visit.practiceId,
        visitId,
      })
    : Promise.resolve(flagOffOutcome());

  const rxTask = isExtractionEnabled('RX')
    ? runDraftRx({
        cleanedText,
        soap: soap as SoapNote,
        patientId: visit.patientId,
        practiceId: visit.practiceId,
        visitId,
      })
    : Promise.resolve(flagOffOutcome());

  const referralsTask = isExtractionEnabled('REFERRALS')
    ? runDraftReferrals({
        cleanedText,
        soap: soap as SoapNote,
        practiceId: visit.practiceId,
        visitId,
      })
    : Promise.resolve(flagOffOutcome());

  const summaryTask = isExtractionEnabled('PATIENT_SUMMARY')
    ? runPatientSummary({
        cleanedText,
        soap: soap as SoapNote,
        practiceId: visit.practiceId,
        visitId,
      })
    : Promise.resolve(flagOffOutcome());

  const [codingResult, rxResult, referralResult, summaryResult] = await Promise.allSettled([
    codingTask,
    rxTask,
    referralsTask,
    summaryTask,
  ]);

  // Persist sequentially so audit timestamps order predictably and we
  // don't stress Postgres with concurrent writes. Each persistOutcome
  // is already fast (two inserts).
  await persistOutcome({
    practiceId: visit.practiceId,
    visitId,
    actorId: visit.userId,
    type: 'ICD10_CPT',
    templateVersion: specialty.version,
    outcome:
      codingResult.status === 'fulfilled'
        ? codingResult.value
        : unexpectedRejectionOutcome(codingResult.reason),
  });
  await persistOutcome({
    practiceId: visit.practiceId,
    visitId,
    actorId: visit.userId,
    type: 'RX',
    templateVersion: specialty.version,
    outcome:
      rxResult.status === 'fulfilled'
        ? rxResult.value
        : unexpectedRejectionOutcome(rxResult.reason),
  });
  await persistOutcome({
    practiceId: visit.practiceId,
    visitId,
    actorId: visit.userId,
    type: 'REFERRAL',
    templateVersion: specialty.version,
    outcome:
      referralResult.status === 'fulfilled'
        ? referralResult.value
        : unexpectedRejectionOutcome(referralResult.reason),
  });
  await persistOutcome({
    practiceId: visit.practiceId,
    visitId,
    actorId: visit.userId,
    type: 'PATIENT_SUMMARY',
    templateVersion: specialty.version,
    outcome:
      summaryResult.status === 'fulfilled'
        ? summaryResult.value
        : unexpectedRejectionOutcome(summaryResult.reason),
  });

  await prisma.scribeVisit.update({
    where: { id: visitId },
    data: { status: 'READY_FOR_REVIEW', endedAt: new Date() },
  });

  await prisma.scribeAuditEvent.create({
    data: {
      practiceId: visit.practiceId,
      visitId,
      actorId: visit.userId,
      action: 'VISIT_READY_FOR_REVIEW',
      diff: {
        soapConfidence: soap.confidence,
        outputsOk: [codingResult, rxResult, referralResult, summaryResult].filter(
          (r) => r.status === 'fulfilled' && r.value.ok
        ).length,
        outputsErr: [codingResult, rxResult, referralResult, summaryResult].filter(
          (r) =>
            r.status === 'rejected' || (r.status === 'fulfilled' && !r.value.ok && r.value.error.code !== 'FLAG_OFF')
        ).length,
      },
    },
  });
}
