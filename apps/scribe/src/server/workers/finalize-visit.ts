// ============================================================================
// Worker: finalize_visit (M2 — SOAP only)
// ----------------------------------------------------------------------------
// Spec §11 fan-out is:
//   1. transcript cleanup + diarization  (this file, Pass 1)
//   2. SOAP note                          (this file, Pass 2)
//   3. ICD-10 + CPT coding                (M4)
//   4. Prescription draft                 (M4)
//   5. Referral letters                   (M4)
//   6. Patient-facing summary             (M4)
//
// M2 ships only 1 + 2 serially. The other four land in M4 as parallel
// fan-out inside this same job.
// ============================================================================

import fs from 'node:fs/promises';
import path from 'node:path';
import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';
import {
  CleanedTranscriptSchema,
  SoapNoteSchema,
  type SoapNote,
} from '@meddoc/types';
import type { FinalizeVisitPayload } from '@/lib/queue';

const PROMPTS_DIR = path.join(process.cwd(), 'apps', 'scribe', 'src', 'server', 'prompts');

async function loadPrompt(name: 'cleanup-transcript' | 'generate-soap'): Promise<string> {
  const byCwd = path.join(PROMPTS_DIR, `${name}.md`);
  // When running under tsx from the apps/scribe cwd, prompts are relative
  // to src/server/prompts. When running from the monorepo root, they're
  // under apps/scribe/src/server/prompts. Try both.
  try {
    return await fs.readFile(byCwd, 'utf8');
  } catch {
    const fallback = path.join(__dirname, '..', 'prompts', `${name}.md`);
    return fs.readFile(fallback, 'utf8');
  }
}

export async function runFinalizeVisit(payload: FinalizeVisitPayload): Promise<void> {
  const { visitId } = payload;

  const visit = await prisma.scribeVisit.findUnique({
    where: { id: visitId },
    select: { id: true, practiceId: true, userId: true, status: true, specialtyId: true },
  });
  if (!visit) {
    console.error(`[finalize_visit] visit ${visitId} not found; dropping job`);
    return;
  }

  const [transcript, specialty] = await Promise.all([
    prisma.scribeTranscript.findUnique({ where: { visitId } }),
    prisma.scribeSpecialtyTemplate.findUnique({ where: { id: visit.specialtyId } }),
  ]);
  if (!transcript) {
    throw new Error(`No transcript for visit ${visitId}`);
  }
  if (!specialty) {
    throw new Error(`Specialty ${visit.specialtyId} not found`);
  }

  const cleanupPrompt = await loadPrompt('cleanup-transcript');
  const soapPrompt = await loadPrompt('generate-soap');

  const cleanupModel = process.env.MODEL_FOR_CLEANUP?.trim() || 'claude-sonnet-4-6';
  const soapModel = process.env.MODEL_FOR_SOAP?.trim() || 'claude-sonnet-4-6';

  // --- Pass 1: cleanup + diarize ---
  const cleaned = await modelClient.complete({
    provider: 'anthropic',
    model: cleanupModel,
    system: cleanupPrompt,
    user: transcript.rawFullText,
    schema: CleanedTranscriptSchema,
    purpose: 'cleanup',
    practiceId: visit.practiceId,
    visitId,
    maxTokens: 4096,
  });

  // Persist the cleaned segments back onto the transcript so downstream
  // review + M3 realtime can reuse the same shape.
  await prisma.scribeTranscript.update({
    where: { visitId },
    data: {
      segments: cleaned.segments,
      language: cleaned.language,
      provider: `${transcript.provider} → cleaned-by-${cleanupModel}`,
    },
  });

  // --- Pass 2: SOAP ---
  const cleanedText = cleaned.segments.map((s) => `${s.speaker}: ${s.text}`).join('\n');
  const soap: SoapNote = await modelClient.complete({
    provider: 'anthropic',
    model: soapModel,
    system: `${soapPrompt}\n\n---\nSPECIALTY-SPECIFIC GUIDANCE:\n${specialty.systemPrompt}\n\nSPECIALTY SOAP SCHEMA:\n${JSON.stringify(
      specialty.soapSchema,
      null,
      2
    )}\n\nREQUIRED EXAM ELEMENTS:\n${JSON.stringify(specialty.requiredExamElements)}`,
    user: cleanedText,
    schema: SoapNoteSchema,
    purpose: 'soap',
    practiceId: visit.practiceId,
    visitId,
    maxTokens: 4096,
  });

  await prisma.scribeOutput.create({
    data: {
      practiceId: visit.practiceId,
      visitId,
      type: 'SOAP',
      content: soap,
      modelUsed: soapModel,
      templateVersion: specialty.version,
    },
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
      action: 'SOAP_GENERATED',
      diff: {
        soapConfidence: soap.confidence,
        missingRequired: soap.missing_required_elements,
        ambiguityCount: soap.ambiguities.length,
      },
    },
  });
}
