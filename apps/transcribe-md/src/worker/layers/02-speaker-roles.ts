// ============================================================================
// Layer 2 — Speaker role assignment (T-M4)
// ----------------------------------------------------------------------------
// Takes Deepgram's diarized transcript and asks Claude Sonnet 4.6 to map
// each numeric speaker to a clinical role (doctor / patient / family /
// other / unknown). The prompt asks for per-speaker reasoning so that
// the Pipeline tab in the UI can show a human-auditable trail.
//
// If any speaker lands below the 0.7 confidence threshold, we flag the
// visit for review rather than silently pushing a guess through the
// downstream layers.
// ============================================================================

import { z } from 'zod';
import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';
import type { DeepgramUtterance } from '@meddoc/ai';

const MODEL = 'claude-sonnet-4-6';

// How many utterances per speaker we sample. Full transcripts are
// often thousands of utterances; 5 per speaker is enough signal for
// role classification and cheap on tokens.
const SAMPLE_SIZE = 5;

/** Threshold below which the visit gets needsReview=true in Layer 6. */
export const SPEAKER_REVIEW_THRESHOLD = 0.7;

export const SpeakerRole = z.enum([
  'doctor',
  'patient',
  'family',
  'other',
  'unknown',
]);
export type SpeakerRole = z.infer<typeof SpeakerRole>;

export const SpeakerAssignment = z.object({
  role: SpeakerRole,
  confidence: z.number().min(0).max(1),
  reasoning: z.string().min(1).max(500),
});
export type SpeakerAssignment = z.infer<typeof SpeakerAssignment>;

// Map is keyed by the numeric speaker ID Deepgram returns, stored as a
// string ("0", "1", ...) so JSON round-trips don't coerce it.
export const SpeakerMap = z.record(z.string(), SpeakerAssignment);
export type SpeakerMap = z.infer<typeof SpeakerMap>;

export interface Layer2Input {
  visitId: string;
  practiceId: string;
  utterances: DeepgramUtterance[];
}

export interface Layer2Output {
  speakerMap: SpeakerMap;
  lowestConfidence: number;
  needsReview: boolean;
}

function groupSamplesBySpeaker(
  utterances: DeepgramUtterance[]
): Map<number, string[]> {
  const out = new Map<number, string[]>();
  for (const u of utterances) {
    if (typeof u.speaker !== 'number') continue;
    const list = out.get(u.speaker) ?? [];
    if (list.length < SAMPLE_SIZE) {
      list.push(u.transcript.trim());
      out.set(u.speaker, list);
    }
  }
  return out;
}

export async function runLayer2SpeakerRoles(
  input: Layer2Input
): Promise<Layer2Output> {
  const samples = groupSamplesBySpeaker(input.utterances);
  if (samples.size === 0) {
    // Diarization failed upstream or one-speaker audio. Default to
    // single-speaker doctor with modest confidence; Layer 3 handles
    // missing role labels gracefully.
    const fallback: SpeakerMap = {
      '0': {
        role: 'doctor',
        confidence: 0.5,
        reasoning: 'Diarization returned no speaker tags; defaulting to single-speaker doctor.',
      },
    };
    await prisma.transcribeVisit.update({
      where: { id: input.visitId },
      data: { speakerMap: fallback as unknown as object, needsReview: true },
    });
    return {
      speakerMap: fallback,
      lowestConfidence: 0.5,
      needsReview: true,
    };
  }

  const blocks: string[] = [];
  for (const [speakerId, lines] of [...samples.entries()].sort((a, b) => a[0] - b[0])) {
    blocks.push(
      `Speaker ${speakerId}:\n` +
        lines.map((l, i) => `  ${i + 1}. ${l}`).join('\n')
    );
  }

  const system = [
    'You are a medical scribe assistant. You are given an anonymized',
    'transcript with diarized speakers. Your task is to assign each',
    'speaker one of these roles: doctor, patient, family, other, unknown.',
    '',
    'Rules:',
    '- Doctors ask diagnostic questions, use medical terminology, direct',
    '  the interview, and give instructions.',
    '- Patients describe symptoms in lay terms, respond to questions,',
    '  ask clarifying questions about their condition.',
    '- Family members may speak FOR the patient or provide history.',
    '- "other" covers nurses, techs, interpreters — anyone clearly',
    '  clinical-team but not the primary doctor.',
    '- If you cannot confidently determine a role, use "unknown".',
    '',
    'Respond with VALID JSON ONLY, no markdown fences. Shape:',
    '{',
    '  "0": { "role": "doctor", "confidence": 0.95, "reasoning": "..." },',
    '  "1": { "role": "patient", "confidence": 0.9, "reasoning": "..." }',
    '}',
    '',
    'Confidence is 0.0-1.0. Keep reasoning under 200 characters.',
  ].join('\n');

  const user = blocks.join('\n\n');

  const speakerMap = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    purpose: 'tm_speaker_roles',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: SpeakerMap,
    maxTokens: 2048,
  });

  const confidences = Object.values(speakerMap).map((s) => s.confidence);
  const lowestConfidence = confidences.length
    ? Math.min(...confidences)
    : 0;
  const needsReview = lowestConfidence < SPEAKER_REVIEW_THRESHOLD;

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: {
      speakerMap: speakerMap as unknown as object,
      ...(needsReview
        ? {
            needsReview: true,
            reviewReason:
              `One or more speakers were classified with confidence below ${SPEAKER_REVIEW_THRESHOLD}. ` +
              'Review the Transcript tab and reassign roles if needed.',
          }
        : {}),
    },
  });

  return { speakerMap, lowestConfidence, needsReview };
}
