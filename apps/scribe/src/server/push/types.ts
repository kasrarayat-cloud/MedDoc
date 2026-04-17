// ============================================================================
// apps/scribe/src/server/push — shared types for M6 CRM loop-closing
// ----------------------------------------------------------------------------
// Every push-target module exports a runXxxPush() that returns a
// PushOutcome. The Sign orchestrator (signAndSendVisitAction) collects
// outcomes and surfaces them per-tab in the review UI. Idempotency
// lives on the MedDoc Pro side (uniqueness on sourceScribeOutputId).
// ============================================================================

/** Which push target each outcome describes. Mirrors the review-UI tab. */
export type PushTarget =
  | 'note'          // SOAP → Document (M2 — required for SIGNED)
  | 'billing'       // ICD10_CPT → BillingEvent
  | 'medications'   // RX → Medication rows
  | 'referrals'     // REFERRAL → Document (procedureType=Referral Letter)
  | 'tasks'         // SOAP-derived follow-up items → Task
  | 'problem_list'; // SOAP.assessment → Patient.briefHistory

export type PushStatus = 'ok' | 'skipped' | 'error';

export interface PushSuccess {
  target: PushTarget;
  status: 'ok';
  /** Human-readable summary for the review UI banner, e.g. "3 tasks created". */
  summary: string;
  /** IDs of rows created or reclaimed via idempotency — useful for audit diffs. */
  createdIds?: string[];
}

export interface PushSkipped {
  target: PushTarget;
  status: 'skipped';
  /** Why we didn't push (e.g. output errored, empty array, no plan items). */
  reason: string;
}

export interface PushFailure {
  target: PushTarget;
  status: 'error';
  /** Short error string for the UI banner (not the full stack). */
  message: string;
  /** HTTP status if the failure came from MedDoc Pro; 0 for transport errors. */
  httpStatus?: number;
}

export type PushOutcome = PushSuccess | PushSkipped | PushFailure;

/** Bundle of all outcomes from one Sign invocation. */
export interface SignPushResults {
  /** Zero or more outcomes; order matches the push sequence. */
  outcomes: PushOutcome[];
  /** Convenience accessor: which targets failed (excludes 'skipped'). */
  failedTargets: PushTarget[];
}
