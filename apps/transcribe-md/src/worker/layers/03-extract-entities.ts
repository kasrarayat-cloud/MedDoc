// ============================================================================
// Layer 3 — Medical entity extraction with evidence quotes (T-M4)
// ----------------------------------------------------------------------------
// Input: the role-labeled transcript.
// Output: structured entities (HPI, meds, allergies, exam findings, plan…)
// where every item carries a verbatim evidence_quote + speaker + timestamp.
//
// The prompt's #1 rule is: if you cannot cite evidence, DO NOT include
// the entity. Claude is explicitly told that hallucinating is a
// critical failure — this is the layer that prevents the SOAP note from
// inventing history.
// ============================================================================

import { z } from 'zod';
import { modelClient, type DeepgramUtterance } from '@meddoc/ai';
import prisma from '@meddoc/db';
import type { SpeakerMap } from './02-speaker-roles';

const MODEL = 'claude-sonnet-4-6';

// ---------------------------------------------------------------------------
// Schema — every leaf entity has an evidence_quote + speaker + timestamp.
// Nested fields within HPI / social history use the same shape.
// ---------------------------------------------------------------------------

export const Evidence = z.object({
  evidence_quote: z.string().min(1),
  speaker: z.string(),
  /** seconds from audio start; Deepgram provides this on every utterance. */
  timestamp: z.number().nonnegative().optional(),
});
export type Evidence = z.infer<typeof Evidence>;

// A "fact plus evidence" wrapper used everywhere there's a single
// textual finding to capture.
function factWithEvidence<K extends string>(
  key: K
): z.ZodObject<{ [P in K | 'evidence_quote' | 'speaker' | 'timestamp']: z.ZodTypeAny }> {
  return z.object({
    [key]: z.string(),
    evidence_quote: z.string().min(1),
    speaker: z.string(),
    timestamp: z.number().nonnegative().optional(),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  }) as any;
}

const HpiDimensions = z.object({
  onset: z.string().optional(),
  duration: z.string().optional(),
  quality: z.string().optional(),
  severity: z.string().optional(),
  location: z.string().optional(),
  timing: z.string().optional(),
  context: z.string().optional(),
  modifying_factors: z.string().optional(),
  associated_symptoms: z.string().optional(),
  // Evidence for the HPI as a whole (the dimensions above can be
  // inferred from the same few utterances — we don't require per-
  // dimension evidence, just the HPI paragraph).
  evidence_quote: z.string().min(1),
  speaker: z.string(),
  timestamp: z.number().nonnegative().optional(),
});

export const ExtractedEntities = z.object({
  chief_complaint: z
    .object({
      statement: z.string(),
      evidence_quote: z.string().min(1),
      speaker: z.string(),
      timestamp: z.number().nonnegative().optional(),
    })
    .nullable(),
  hpi: HpiDimensions.nullable(),
  past_medical_history: z.array(factWithEvidence('condition')).default([]),
  medications: z
    .array(
      z.object({
        name: z.string(),
        dose: z.string().nullable().optional(),
        route: z.string().nullable().optional(),
        frequency: z.string().nullable().optional(),
        evidence_quote: z.string().min(1),
        speaker: z.string(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),
  allergies: z
    .array(
      z.object({
        substance: z.string(),
        reaction: z.string().nullable().optional(),
        evidence_quote: z.string().min(1),
        speaker: z.string(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),
  family_history: z
    .array(
      z.object({
        relation: z.string(),
        condition: z.string(),
        evidence_quote: z.string().min(1),
        speaker: z.string(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),
  social_history: z
    .object({
      smoking: factWithEvidence('status').nullable().optional(),
      alcohol: factWithEvidence('status').nullable().optional(),
      drugs: factWithEvidence('status').nullable().optional(),
      occupation: factWithEvidence('value').nullable().optional(),
    })
    .default({}),
  ros: z
    .array(
      z.object({
        system: z.string(),
        finding: z.string(),
        evidence_quote: z.string().min(1),
        speaker: z.string(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),
  exam_findings: z
    .array(
      z.object({
        system: z.string(),
        finding: z.string(),
        evidence_quote: z.string().min(1),
        speaker: z.string(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),
  tests_mentioned: z
    .array(
      z.object({
        test: z.string(),
        result_if_given: z.string().nullable().optional(),
        evidence_quote: z.string().min(1),
        speaker: z.string(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),
  assessment_discussed: z
    .array(factWithEvidence('finding'))
    .default([]),
  plan_discussed: z.array(factWithEvidence('item')).default([]),
});
export type ExtractedEntities = z.infer<typeof ExtractedEntities>;

export interface Layer3Input {
  visitId: string;
  practiceId: string;
  utterances: DeepgramUtterance[];
  speakerMap: SpeakerMap;
}

// ---------------------------------------------------------------------------
// Formatting helper — produce the role-labeled transcript the prompt
// and Layers 4+5 all consume.
// ---------------------------------------------------------------------------

/** "[Doctor, 0:05]: Tell me what brings you in today." */
function formatRoleLabeledLine(
  u: DeepgramUtterance,
  speakerMap: SpeakerMap
): string {
  const speakerKey = typeof u.speaker === 'number' ? String(u.speaker) : 'unknown';
  const role = speakerMap[speakerKey]?.role ?? 'unknown';
  const displayRole = role.charAt(0).toUpperCase() + role.slice(1);
  const ts = Math.max(0, Math.floor(u.start ?? 0));
  const mm = Math.floor(ts / 60);
  const ss = (ts % 60).toString().padStart(2, '0');
  return `[${displayRole} #${speakerKey}, ${mm}:${ss}]: ${u.transcript.trim()}`;
}

export function buildRoleLabeledTranscript(
  utterances: DeepgramUtterance[],
  speakerMap: SpeakerMap
): string {
  return utterances
    .map((u) => formatRoleLabeledLine(u, speakerMap))
    .join('\n');
}

// ---------------------------------------------------------------------------
// The layer itself.
// ---------------------------------------------------------------------------

export async function runLayer3ExtractEntities(
  input: Layer3Input
): Promise<ExtractedEntities> {
  const transcript = buildRoleLabeledTranscript(
    input.utterances,
    input.speakerMap
  );

  const system = [
    'You are a medical entity extraction system. You extract structured',
    'entities from clinical conversations for downstream SOAP-note',
    'generation.',
    '',
    'CRITICAL RULES (violating these is a pipeline failure):',
    '1. Every entity MUST include an "evidence_quote" that is verbatim',
    '   from the transcript. Do not paraphrase. Do not summarise.',
    '2. Every entity MUST include "speaker" (e.g. "Doctor #0") and the',
    '   "timestamp" in seconds from audio start.',
    '3. If you CANNOT cite evidence for an entity, OMIT IT. Never',
    '   invent. Hallucinating is a critical failure.',
    '4. If the transcript is silent on a category, return [] (or null',
    '   for singleton categories) — do not stretch to populate.',
    '',
    'Categories:',
    '- chief_complaint (single statement + evidence)',
    '- hpi: onset, duration, quality, severity, location, timing,',
    '  context, modifying_factors, associated_symptoms — each string;',
    '  all optional; one evidence quote for the paragraph.',
    '- past_medical_history: list of {condition, evidence…}',
    '- medications: list of {name, dose?, route?, frequency?, evidence…}',
    '- allergies: list of {substance, reaction?, evidence…}',
    '- family_history: list of {relation, condition, evidence…}',
    '- social_history: smoking/alcohol/drugs/occupation, each optional',
    '- ros: list of {system, finding, evidence…} (review of systems)',
    '- exam_findings: list of {system, finding, evidence…} — only what',
    '  the doctor stated/observed during the encounter',
    '- tests_mentioned: list of {test, result_if_given?, evidence…}',
    '- assessment_discussed: list of {finding, evidence…}',
    '- plan_discussed: list of {item, evidence…}',
    '',
    'Respond with VALID JSON ONLY, no markdown fences.',
  ].join('\n');

  const user = [
    'Role-labeled transcript:',
    '',
    transcript,
  ].join('\n');

  const entities = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    purpose: 'tm_entities',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: ExtractedEntities,
    maxTokens: 6144,
  });

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { entities: entities as unknown as object },
  });

  return entities;
}
