// ============================================================================
// Layer 3 — Medical entity extraction with evidence quotes (T-M4 + T-M5)
// ----------------------------------------------------------------------------
// Takes whatever the upstream layer produced (full conversation from L1+L2,
// a single-speaker dictation from L1', or raw typed text from the doctor)
// and turns it into a structured entity set. Every item still carries an
// evidence_quote so Layer 4 can never invent findings.
//
// Three modes:
//   - conversation (audio_upload)   — role-labeled lines, speaker + ts required
//   - dictation    (voice_dictation) — one doctor-only block, speaker = "Doctor"
//   - text         (text_notes)     — raw typed bullets, no timestamps
// ============================================================================

import { z } from 'zod';
import { modelClient, type DeepgramUtterance } from '@meddoc/ai';
import prisma from '@meddoc/db';
import type { SpeakerMap } from './02-speaker-roles';

const MODEL = 'claude-sonnet-4-6';

// ---------------------------------------------------------------------------
// Schema — evidence_quote is always required (no hallucination rule), but
// speaker + timestamp are optional so dictation/text modes don't have to
// fake them. In conversation mode the prompt still demands both.
// ---------------------------------------------------------------------------

export const Evidence = z.object({
  evidence_quote: z.string().min(1),
  speaker: z.string().optional(),
  /** seconds from audio start; only conversation + dictation populate this. */
  timestamp: z.number().nonnegative().optional(),
});
export type Evidence = z.infer<typeof Evidence>;

// A "fact plus evidence" wrapper used everywhere there's a single textual
// finding to capture.
function factWithEvidence<K extends string>(
  key: K
): z.ZodObject<{ [P in K | 'evidence_quote' | 'speaker' | 'timestamp']: z.ZodTypeAny }> {
  return z.object({
    [key]: z.string(),
    evidence_quote: z.string().min(1),
    speaker: z.string().optional(),
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
  evidence_quote: z.string().min(1),
  speaker: z.string().optional(),
  timestamp: z.number().nonnegative().optional(),
});

export const ExtractedEntities = z.object({
  chief_complaint: z
    .object({
      statement: z.string(),
      evidence_quote: z.string().min(1),
      speaker: z.string().optional(),
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
        speaker: z.string().optional(),
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
        speaker: z.string().optional(),
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
        speaker: z.string().optional(),
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
        speaker: z.string().optional(),
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
        speaker: z.string().optional(),
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
        speaker: z.string().optional(),
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

// ---------------------------------------------------------------------------
// Formatting helper for conversation mode — produces the role-labeled
// transcript that Layer 4 + 5 also consume.
// ---------------------------------------------------------------------------

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
// Layer 3 input — discriminated union by mode.
// ---------------------------------------------------------------------------

export interface Layer3ConversationInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  mode: 'conversation';
  utterances: DeepgramUtterance[];
  speakerMap: SpeakerMap;
}
export interface Layer3DictationInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  mode: 'dictation';
  /** Full text from Layer 1' (single-speaker Deepgram). */
  dictationText: string;
}
export interface Layer3TextInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  mode: 'text';
  /** Raw bullet-point / prose the doctor typed in the TextComposer UI. */
  rawText: string;
}
export type Layer3Input =
  | Layer3ConversationInput
  | Layer3DictationInput
  | Layer3TextInput;

// Bundled output — Layer 4 wants a "context text" to include alongside the
// entities. Different shape per mode (role-labeled transcript, dictation
// block, raw bullets) but we return it as a single string here so Layer 4
// doesn't have to re-branch.
export interface Layer3Output {
  entities: ExtractedEntities;
  contextText: string;
}

// ---------------------------------------------------------------------------
// Prompt builders — one per mode. Extracted to small functions so the
// surface is testable + easy to eyeball.
// ---------------------------------------------------------------------------

const COMMON_CATEGORIES = [
  'Categories:',
  '- chief_complaint: {statement, evidence_quote, speaker?, timestamp?} or null',
  '- hpi: {onset?, duration?, quality?, severity?, location?, timing?,',
  '  context?, modifying_factors?, associated_symptoms?, evidence_quote,',
  '  speaker?, timestamp?} or null — each sub-field is a string; all',
  '  sub-fields are optional; one evidence_quote covers the paragraph.',
  '- past_medical_history: list of {condition, evidence_quote, ...}',
  '- medications: list of {name, dose?, route?, frequency?, evidence_quote, ...}',
  '- allergies: list of {substance, reaction?, evidence_quote, ...}',
  '- family_history: list of {relation, condition, evidence_quote, ...}',
  //
  // T-M23.B: expanded social_history shape guidance. Prior wording
  // ("smoking/alcohol/drugs/occupation, each optional") let Claude
  // shortcut to bare strings like `"occupation": "factory operative"`
  // which fails the Zod schema with "expected object, received
  // string" — every ~1 in 50 long audio uploads triggered SCHEMA_FAIL
  // here because the content patterns that invite the shortcut (a
  // single clear occupation phrase) are common. Explicit shape +
  // side-by-side correct/wrong example makes the wrapper non-
  // negotiable.
  //
  '- social_history: an OBJECT with optional sub-fields. Each sub-field',
  '  must itself be an OBJECT (never a bare string):',
  '    smoking:    {status, evidence_quote, speaker?, timestamp?}',
  '    alcohol:    {status, evidence_quote, speaker?, timestamp?}',
  '    drugs:      {status, evidence_quote, speaker?, timestamp?}',
  '    occupation: {value,  evidence_quote, speaker?, timestamp?}',
  '  If you have no evidence quote for a sub-field, OMIT that sub-field',
  '  entirely — do not emit it as a bare string.',
  '  CORRECT:  "social_history": { "occupation": { "value": "factory',
  '            operative", "evidence_quote": "he works as a factory',
  '            operative at Simple Signs Ltd" } }',
  '  WRONG:    "social_history": { "occupation": "factory operative" }',
  '- ros: list of {system, finding, evidence_quote, ...} (review of systems)',
  '- exam_findings: list of {system, finding, evidence_quote, ...} — only',
  '  what the doctor stated/observed',
  '- tests_mentioned: list of {test, result_if_given?, evidence_quote, ...}',
  '- assessment_discussed: list of {finding, evidence_quote, ...}',
  '- plan_discussed: list of {item, evidence_quote, ...}',
].join('\n');

function buildConversationPrompt(): { system: string; userPrefix: string } {
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
    COMMON_CATEGORIES,
    '',
    'Respond with VALID JSON ONLY, no markdown fences.',
  ].join('\n');
  return { system, userPrefix: 'Role-labeled transcript:' };
}

function buildDictationPrompt(): { system: string; userPrefix: string } {
  const system = [
    'You are a medical entity extraction system. The input below is a',
    'doctor\'s own dictated summary of a visit, transcribed as a single',
    'block of text (no speakers, no patient-doctor turn-taking). Extract',
    'structured entities for downstream SOAP-note generation.',
    '',
    'CRITICAL RULES (violating these is a pipeline failure):',
    '1. Every entity MUST include an "evidence_quote" — a verbatim',
    '   snippet from the dictation. Speaker is always "Doctor". Timestamp',
    '   is optional (there\'s no meaningful time cue in a single block).',
    '2. If you CANNOT cite evidence for an entity, OMIT IT. Never invent.',
    '   Expanding shorthand is allowed (e.g. "f/u 3mo" → "Follow-up in 3',
    '   months", "bp 148/92" → systolic 148, diastolic 92). Inventing',
    '   findings that weren\'t mentioned is hallucination.',
    '3. Treat the doctor as the only narrator. Everything in the',
    '   dictation is either (a) something the doctor observed, (b)',
    '   something the patient told the doctor, or (c) the doctor\'s',
    '   plan. Use context to decide which category each point belongs',
    '   to — if ambiguous, prefer exam_findings or plan_discussed over',
    '   hpi.',
    '4. If the dictation is silent on a category, return [] (or null).',
    '',
    COMMON_CATEGORIES,
    '',
    'Respond with VALID JSON ONLY, no markdown fences.',
  ].join('\n');
  return { system, userPrefix: 'Doctor\'s dictated visit summary:' };
}

function buildTextPrompt(): { system: string; userPrefix: string } {
  const system = [
    'You are a medical entity extraction system. The input below is a',
    'doctor\'s TYPED shorthand — bullets, abbreviations, or prose — that',
    'they want expanded into a full SOAP note downstream. Extract',
    'structured entities.',
    '',
    'CRITICAL RULES (violating these is a pipeline failure):',
    '1. Every entity MUST include an "evidence_quote" — the relevant',
    '   line/phrase from the typed input, verbatim. Speaker and',
    '   timestamp are both optional and should usually be omitted (this',
    '   isn\'t a recording).',
    '2. Expand common medical shorthand sensibly:',
    '   - "yo" → "year-old", "f/u" → "follow-up", "RTC" → "return to',
    '     clinic", "ROS -" → "review of systems negative",',
    '   - "bp 148/92" → systolic 148, diastolic 92,',
    '   - "A1c 6.8" → HbA1c 6.8,',
    '   - "incr X to Y" → "increase X to Y".',
    '3. If you CANNOT cite an evidence line for an entity, OMIT IT.',
    '   Inventing findings the doctor didn\'t type is hallucination and',
    '   a critical failure.',
    '4. Short or sparse inputs are valid; empty categories stay empty.',
    '',
    COMMON_CATEGORIES,
    '',
    'Respond with VALID JSON ONLY, no markdown fences.',
  ].join('\n');
  return { system, userPrefix: 'Doctor\'s typed shorthand:' };
}

// ---------------------------------------------------------------------------
// The layer itself.
// ---------------------------------------------------------------------------

export async function runLayer3ExtractEntities(
  input: Layer3Input
): Promise<Layer3Output> {
  let contextText: string;
  let prompts: { system: string; userPrefix: string };
  if (input.mode === 'conversation') {
    contextText = buildRoleLabeledTranscript(
      input.utterances,
      input.speakerMap
    );
    prompts = buildConversationPrompt();
  } else if (input.mode === 'dictation') {
    contextText = input.dictationText.trim();
    prompts = buildDictationPrompt();
  } else {
    contextText = input.rawText.trim();
    prompts = buildTextPrompt();
  }

  const user = [prompts.userPrefix, '', contextText].join('\n');

  const entities = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    userId: input.userId,
    purpose: 'tm_entities',
    provider: 'anthropic',
    model: MODEL,
    system: prompts.system,
    user,
    schema: ExtractedEntities,
    maxTokens: 6144,
    temperature: 0.2,
  });

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { entities: entities as unknown as object },
  });

  return { entities, contextText };
}
