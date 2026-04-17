// ============================================================================
// @meddoc/types — ICD-10 + CPT coding output
// ----------------------------------------------------------------------------
// Spec §11 item 3: "Every code must have an evidence quote from the
// transcript. No ungrounded codes." The eval harness checks substring
// containment against the transcript (same pattern as SOAP.assessment).
// ============================================================================

import { z } from 'zod';
import { ConfidenceLevel } from './soap';

/**
 * One coded item — shared shape for both ICD-10 and CPT entries. CPT
 * can carry modifiers (e.g. "-25", "-59"); we store them folded into
 * the `code` field ("99214-25") so one regex-driven renderer handles
 * both.
 */
export const CodedItemSchema = z.object({
  code: z.string().min(1),
  description: z.string().min(1),
  /** Verbatim substring of the cleaned transcript — hallucination detector checks this. */
  evidence_quote: z.string().min(1),
  confidence: ConfidenceLevel,
});
export type CodedItem = z.infer<typeof CodedItemSchema>;

export const CodingOutputSchema = z
  .object({
    confidence: ConfidenceLevel,
    icd10: z.array(CodedItemSchema),
    cpt: z.array(CodedItemSchema),
    ambiguities: z.array(z.string()),
  })
  .strict();
export type CodingOutput = z.infer<typeof CodingOutputSchema>;
