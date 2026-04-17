// ============================================================================
// @meddoc/types — SOAP note Zod schema
// ----------------------------------------------------------------------------
// Shared by apps/scribe (generates + validates) and apps/meddoc-pro (reads
// from Document.content when the note was signed via Scribe). Every AI
// output must validate against this before persisting — spec §11/§18.
// ============================================================================

import { z } from 'zod';

export const ConfidenceLevel = z.enum(['low', 'medium', 'high']);
export type ConfidenceLevel = z.infer<typeof ConfidenceLevel>;

/**
 * One item in the Assessment section. Every item must have an evidence
 * quote that appears VERBATIM in the transcript — the hallucination
 * detector in the eval harness uses this to verify no fabrication.
 */
export const AssessmentItemSchema = z.object({
  icd10_candidate: z.string().min(1),
  description: z.string().min(1),
  evidence_quote: z.string().min(1),
  confidence: ConfidenceLevel,
});
export type AssessmentItem = z.infer<typeof AssessmentItemSchema>;

/**
 * SOAP note — structured output of the Pass 2 generator.
 *
 * Section keys (the string keys of `subjective`/`objective`/`plan`) match
 * the `soapSchema` defined on the visit's ScribeSpecialtyTemplate. We
 * don't hard-code the keys here because each specialty has a different
 * set — see apps/scribe/specialties/*.yaml.
 */
export const SoapNoteSchema = z.object({
  confidence: ConfidenceLevel,
  subjective: z.record(z.string(), z.string()),
  objective: z.record(z.string(), z.string()),
  assessment: z.array(AssessmentItemSchema),
  plan: z.record(z.string(), z.string()),
  /**
   * Keys from the specialty's `requiredExamElements` that the clinician
   * did not document. Surfaced in the review UI so the doctor can add
   * them before signing — spec §11 "never invent findings".
   */
  missing_required_elements: z.array(z.string()),
  /**
   * Things the generator was unsure about. Surfaced as a review banner.
   * A flagged ambiguity is strictly better than a confident wrong note.
   */
  ambiguities: z.array(z.string()),
});
export type SoapNote = z.infer<typeof SoapNoteSchema>;

/**
 * Cleaned transcript (Pass 1 output). Segments carry speaker labels that
 * the Whisper pipeline couldn't assign — Claude re-diarizes during cleanup.
 */
export const TranscriptSpeaker = z.enum(['CLINICIAN', 'PATIENT', 'OTHER']);
export type TranscriptSpeaker = z.infer<typeof TranscriptSpeaker>;

export const CleanedTranscriptSegmentSchema = z.object({
  speaker: TranscriptSpeaker,
  text: z.string().min(1),
});
export type CleanedTranscriptSegment = z.infer<typeof CleanedTranscriptSegmentSchema>;

export const CleanedTranscriptSchema = z.object({
  segments: z.array(CleanedTranscriptSegmentSchema).min(1),
  language: z.string().default('en'),
  notes: z
    .string()
    .optional()
    .describe(
      'Optional notes from the cleanup pass — e.g. "chunk boundary at 24:58 may have dropped one sentence".'
    ),
});
export type CleanedTranscript = z.infer<typeof CleanedTranscriptSchema>;
