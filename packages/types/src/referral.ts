// ============================================================================
// @meddoc/types — Referral letter output
// ----------------------------------------------------------------------------
// Spec §11 item 5: "one per referral in Plan." M4 ships a single Claude
// call that returns an array (D5) — simpler fan-in for visits with >1
// referral and keeps the AiCall row count tidy.
// ============================================================================

import { z } from 'zod';
import { ConfidenceLevel } from './soap';

export const ReferralUrgency = z.enum(['routine', 'urgent', 'stat']);
export type ReferralUrgency = z.infer<typeof ReferralUrgency>;

export const ReferralLetterSchema = z.object({
  /** e.g. "Cardiology", "Dermatology" — free text so community-specific services work. */
  specialty: z.string().min(1),
  urgency: ReferralUrgency,
  /** One-paragraph clinical context for the receiving specialist. */
  clinical_summary: z.string().min(1),
  reason_for_referral: z.string().min(1),
  /** Relevant PMH / meds / allergies pulled from the visit. */
  relevant_history: z.string().min(1),
  /** Verbatim transcript quote where the referral was discussed. */
  evidence_quote: z.string().min(1),
  confidence: ConfidenceLevel,
});
export type ReferralLetter = z.infer<typeof ReferralLetterSchema>;

export const ReferralOutputSchema = z
  .object({
    confidence: ConfidenceLevel,
    referrals: z.array(ReferralLetterSchema),
    ambiguities: z.array(z.string()),
  })
  .strict();
export type ReferralOutput = z.infer<typeof ReferralOutputSchema>;
