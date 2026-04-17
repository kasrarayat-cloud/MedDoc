// ============================================================================
// @meddoc/types — Prescription draft output
// ----------------------------------------------------------------------------
// Spec §11 item 4: Rx input = SOAP Plan + patient's current meds. Each
// draft carries a `warnings` array (LLM-derived interaction / allergy /
// duplicate flags — M4 ships the LLM-only pass per D4; RxNorm lands in
// M7). Controlled substances require an explicit transcript quote from
// the clinician, enforced by the `clinician_requested` boolean + the
// prompt.
// ============================================================================

import { z } from 'zod';
import { ConfidenceLevel } from './soap';

/** What kind of safety concern this warning surfaces. */
export const RxWarningKind = z.enum([
  'interaction',
  'allergy',
  'duplicate',
  'controlled',
  'other',
]);
export type RxWarningKind = z.infer<typeof RxWarningKind>;

export const RxWarningSeverity = z.enum(['info', 'warning', 'critical']);
export type RxWarningSeverity = z.infer<typeof RxWarningSeverity>;

export const RxWarningSchema = z.object({
  kind: RxWarningKind,
  severity: RxWarningSeverity,
  message: z.string().min(1),
  /** Existing drugs this warning references (from patient's current meds). */
  related_drugs: z.array(z.string()).default([]),
});
export type RxWarning = z.infer<typeof RxWarningSchema>;

export const RxDraftSchema = z.object({
  drug: z.string().min(1),
  /** Dose strength + form — "10 mg", "500 mg/5 mL", etc. */
  dose: z.string().min(1),
  /** "PO", "IV", "SQ", "topical", "PR", "IM" … */
  route: z.string().min(1),
  /** "once daily", "BID", "q6h PRN pain", etc. */
  frequency: z.string().min(1),
  /** "7 days", "30 days", "ongoing", etc. */
  duration: z.string().min(1),
  /** "#30 tablets", "1 inhaler", etc. */
  quantity: z.string().min(1),
  refills: z.number().int().min(0).max(11),
  /** Full "sig" line as printed on the label. */
  sig: z.string().min(1),
  /** DEA Schedule II–V? Generator must set true whenever schedule is any of II/III/IV/V. */
  is_controlled: z.boolean(),
  /**
   * Spec §11: "Never draft controlled substances unless clinician
   * explicitly stated it." If is_controlled && !clinician_requested the
   * review UI must bold-warn.
   */
  clinician_requested: z.boolean(),
  /** Verbatim transcript quote that authorises this Rx (plan item + any controlled-request). */
  evidence_quote: z.string().min(1),
  warnings: z.array(RxWarningSchema),
  confidence: ConfidenceLevel,
});
export type RxDraft = z.infer<typeof RxDraftSchema>;

export const RxOutputSchema = z
  .object({
    confidence: ConfidenceLevel,
    prescriptions: z.array(RxDraftSchema),
    /** Broader caveats that don't attach to a single prescription. */
    ambiguities: z.array(z.string()),
  })
  .strict();
export type RxOutput = z.infer<typeof RxOutputSchema>;
