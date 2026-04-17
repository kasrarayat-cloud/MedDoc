// ============================================================================
// @meddoc/types — Patient-facing summary output
// ----------------------------------------------------------------------------
// Spec §11 item 6: 6th-grade reading level, clear next steps. We store
// the structured form (not a single paragraph) so the review UI can edit
// section-by-section and the client-side Flesch-Kincaid calculator (M4
// user addition) can score the concatenated body.
// ============================================================================

import { z } from 'zod';
import { ConfidenceLevel } from './soap';

export const PatientSummarySchema = z
  .object({
    confidence: ConfidenceLevel,
    /** Short personal greeting — "Hi Jane, here's a recap of today's visit." */
    greeting: z.string().min(1),
    /** Bulleted list of topics discussed, 6th-grade phrasing. */
    what_we_talked_about: z.array(z.string().min(1)),
    /** Action items the patient must do. */
    your_plan: z.array(z.string().min(1)),
    /** Simple "take X of Y daily for Z days" lines. Empty array if no meds. */
    medications: z.array(z.string()),
    /** Single line describing the next appointment / follow-up. */
    follow_up: z.string(),
    /** Red-flag symptoms that should trigger a call back. */
    when_to_call_us: z.array(z.string().min(1)),
    /**
     * Reading-level target the generator was asked to meet. Always
     * '6th_grade' in M4 — future milestones may expose a clinic setting.
     */
    reading_level_target: z.literal('6th_grade'),
    ambiguities: z.array(z.string()),
  })
  .strict();
export type PatientSummary = z.infer<typeof PatientSummarySchema>;
