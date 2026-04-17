// ============================================================================
// @meddoc/types — Cross-app internal API contracts
// ----------------------------------------------------------------------------
// Scribe ← Service Token → MedDoc Pro. Every internal call flows through
// these schemas so drift between apps is caught at request time.
// ============================================================================

import { z } from 'zod';
import { SoapNoteSchema } from './soap';
import { CodingOutputSchema } from './coding';
import { RxDraftSchema } from './rx';
import { ReferralLetterSchema } from './referral';

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

// ============================================================================
// M6 — CRM loop-closing endpoints
// ----------------------------------------------------------------------------
// Called by Scribe's Sign flow in `signAndSendVisitAction` after the
// SOAP note has been posted successfully. Every payload carries the
// `sourceScribeOutputId` so duplicate Sign clicks / retries resolve to
// the same row on the MedDoc Pro side (M6 D6 idempotency).
// ============================================================================

// ─── POST /api/internal/patients/:patientId/tasks ────────────────────────
/**
 * One actionable follow-up item from the SOAP plan. The push module
 * extracts these from SOAP.plan free-text (follow-up instructions,
 * labs to order, referrals to schedule). Multiple tasks per signed
 * visit are expected.
 */
export const CreateTaskItemSchema = z.object({
  /** Short, action-oriented title. "Schedule follow-up in 3 months." */
  title: z.string().min(1).max(240),
  /** Optional long-form context — which plan line produced this. */
  description: z.string().max(2000).optional(),
  /** Optional target due date (ISO-8601). */
  dueAt: z.string().datetime().optional(),
  /**
   * Index within the source ScribeOutput — used with sourceScribeOutputId
   * for idempotency (composite unique). One SOAP output fans out to
   * many tasks, each at a stable zero-based index.
   */
  sourceItemIndex: z.number().int().min(0),
});
export type CreateTaskItem = z.infer<typeof CreateTaskItemSchema>;

export const CreateTasksRequestSchema = z.object({
  sourceVisitId: z.string().min(1),
  /** ScribeOutput.id whose content produced these tasks (typically the SOAP row). */
  sourceScribeOutputId: z.string().min(1),
  /** Who to assign by default — the signing clinician. */
  assignedUserId: z.string().min(1),
  /** Same user; used for audit + createdByUserId on the row. */
  createdByUserId: z.string().min(1),
  tasks: z.array(CreateTaskItemSchema).min(1).max(50),
});
export type CreateTasksRequest = z.infer<typeof CreateTasksRequestSchema>;

export const CreateTasksResponseSchema = z.object({
  /** Task IDs created or reclaimed via idempotency, one per input task (same order). */
  taskIds: z.array(z.string().min(1)),
});
export type CreateTasksResponse = z.infer<typeof CreateTasksResponseSchema>;

// ─── POST /api/internal/patients/:patientId/billing-events ───────────────
export const CreateBillingEventRequestSchema = z.object({
  sourceVisitId: z.string().min(1),
  sourceScribeOutputId: z.string().min(1),
  clinicianUserId: z.string().min(1),
  /** Validated by CodingOutputSchema before persist. */
  coding: CodingOutputSchema,
});
export type CreateBillingEventRequest = z.infer<typeof CreateBillingEventRequestSchema>;

export const CreateBillingEventResponseSchema = z.object({
  billingEventId: z.string().min(1),
});
export type CreateBillingEventResponse = z.infer<typeof CreateBillingEventResponseSchema>;

// ─── POST /api/internal/patients/:patientId/medications ──────────────────
export const AppendMedicationsRequestSchema = z.object({
  sourceVisitId: z.string().min(1),
  sourceScribeOutputId: z.string().min(1),
  clinicianUserId: z.string().min(1),
  /** Rx drafts to add as active medications. Order is preserved. */
  prescriptions: z.array(RxDraftSchema).min(1).max(50),
});
export type AppendMedicationsRequest = z.infer<typeof AppendMedicationsRequestSchema>;

export const AppendMedicationsResponseSchema = z.object({
  /** Each entry is the Medication.id that was created or matched via idempotency. */
  medicationIds: z.array(z.string().min(1)),
  /**
   * Count of drafts that matched an existing active Medication (by
   * normalized drug name + sourceScribeOutputId) and were deduped.
   */
  dedupedCount: z.number().int().min(0),
});
export type AppendMedicationsResponse = z.infer<typeof AppendMedicationsResponseSchema>;

// ─── PATCH /api/internal/patients/:patientId/problem-list ────────────────
/**
 * Appends one or more problem lines to Patient.briefHistory. Each line
 * must be already formatted ("HTN (I10) — from Scribe visit <id>…").
 * Idempotency is exact-string presence check server-side; duplicates
 * are silently skipped.
 */
export const UpdateProblemListRequestSchema = z.object({
  sourceVisitId: z.string().min(1),
  sourceScribeOutputId: z.string().min(1),
  /** Pre-formatted lines to merge into briefHistory. */
  problemLines: z.array(z.string().min(1).max(400)).min(1).max(50),
});
export type UpdateProblemListRequest = z.infer<typeof UpdateProblemListRequestSchema>;

export const UpdateProblemListResponseSchema = z.object({
  /** How many new lines were actually appended (vs deduped). */
  appendedCount: z.number().int().min(0),
  /** Total size of briefHistory after append. */
  totalSize: z.number().int().min(0),
});
export type UpdateProblemListResponse = z.infer<typeof UpdateProblemListResponseSchema>;

// ─── POST /api/internal/referrals ────────────────────────────────────────
/**
 * Creates one or more Document rows (procedureType='Referral Letter')
 * per M6 D2. One request per signed visit; body carries the full set of
 * referral letters the REFERRAL output produced. Idempotent via
 * (sourceScribeOutputId, sourceItemIndex) composite uniqueness.
 */
export const CreateReferralsRequestSchema = z.object({
  sourceVisitId: z.string().min(1),
  sourceScribeOutputId: z.string().min(1),
  patientId: z.string().min(1),
  clinicianUserId: z.string().min(1),
  letters: z.array(ReferralLetterSchema).min(1).max(20),
});
export type CreateReferralsRequest = z.infer<typeof CreateReferralsRequestSchema>;

export const CreateReferralsResponseSchema = z.object({
  /** Document IDs, one per letter, same order as the input. */
  documentIds: z.array(z.string().min(1)),
});
export type CreateReferralsResponse = z.infer<typeof CreateReferralsResponseSchema>;
