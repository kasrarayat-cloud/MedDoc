// ============================================================================
// @meddoc/types — Cross-app internal API contracts
// ----------------------------------------------------------------------------
// Scribe ← Service Token → MedDoc Pro. Every internal call flows through
// these schemas so drift between apps is caught at request time.
// ============================================================================

import { z } from 'zod';
import { SoapNoteSchema } from './soap';

/**
 * POST /api/internal/patients/:patientId/notes
 * Called by Scribe when the clinician hits "Sign & Send". Creates a
 * Document row in MedDoc Pro with the SOAP JSON in `content` — the
 * MedDoc Pro UI renders JSON at display time (SoapNoteRenderer).
 */
export const CreateClinicalNoteRequestSchema = z.object({
  /** Scribe's ScribeVisit.id — persisted so both systems can reconcile. */
  sourceVisitId: z.string().min(1),
  /** The clinician who signed. Used for Document.createdById + audit. */
  clinicianUserId: z.string().min(1),
  /** e.g. "2026-04-17 • Primary Care visit — Jane Doe" */
  title: z.string().min(1),
  /** e.g. "Primary Care". Free-text matches existing Document.procedureType. */
  procedureType: z.string().min(1),
  /** Structured SOAP JSON, validated both sides. Stored JSON-stringified. */
  soap: SoapNoteSchema,
  /** ISO timestamp of the signing event. */
  signedAt: z.string().datetime(),
});
export type CreateClinicalNoteRequest = z.infer<typeof CreateClinicalNoteRequestSchema>;

export const CreateClinicalNoteResponseSchema = z.object({
  documentId: z.string().min(1),
});
export type CreateClinicalNoteResponse = z.infer<typeof CreateClinicalNoteResponseSchema>;
