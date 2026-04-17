// ============================================================================
// @meddoc/types — Clinical-safety internal API contract
// ----------------------------------------------------------------------------
// GET /api/internal/patients/:patientId/clinical-safety (M4 D3).
//
// Called by the scribe finalize_visit worker when drafting Rx, so Claude
// can see the patient's active medications + allergies as context for
// interaction / duplicate / allergy warnings. Fields mirror the Prisma
// Medication + Allergy models minus internal-only bits (ids, FKs, audit
// trail, soft-delete column) — we expose only what a clinical reasoning
// step actually needs.
// ============================================================================

import { z } from 'zod';

export const ClinicalSafetyMedicationSchema = z.object({
  name: z.string().min(1),
  dosage: z.string().nullable(),
  frequency: z.string().nullable(),
  isActive: z.boolean(),
  notes: z.string().nullable(),
});
export type ClinicalSafetyMedication = z.infer<typeof ClinicalSafetyMedicationSchema>;

export const ClinicalSafetySeverity = z.enum(['UNKNOWN', 'MILD', 'MODERATE', 'SEVERE']);
export type ClinicalSafetySeverity = z.infer<typeof ClinicalSafetySeverity>;

export const ClinicalSafetyAllergySchema = z.object({
  allergen: z.string().min(1),
  reaction: z.string().nullable(),
  severity: ClinicalSafetySeverity,
  notes: z.string().nullable(),
});
export type ClinicalSafetyAllergy = z.infer<typeof ClinicalSafetyAllergySchema>;

export const ClinicalSafetyResponseSchema = z.object({
  patientId: z.string().min(1),
  medications: z.array(ClinicalSafetyMedicationSchema),
  allergies: z.array(ClinicalSafetyAllergySchema),
});
export type ClinicalSafetyResponse = z.infer<typeof ClinicalSafetyResponseSchema>;
