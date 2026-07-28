// ============================================================================
// HIPAA Audit Logger — transcribe-md (§164.312(b))
// ----------------------------------------------------------------------------
// Mirror of apps/meddoc-pro/src/lib/audit.ts, ported to close the H2 finding
// from the ultra-final audit: transcribe-md was writing ZERO rows to the
// `audit_logs` table despite 15+ mutation surfaces that touch PHI.
//
// Same table, same schema, same AuditAction enum — consumers on the
// admin side can query both products uniformly.
//
// IMPORTANT — never put raw PHI in `metadata`. Use field NAMES, not
// values:
//   GOOD: { changedFields: ['specialty', 'chiefComplaint'] }
//   BAD:  { newName: 'Sarah Mitchell' }
//
// Never throws. Failures log to stderr and swallow — audit logging is
// defense-in-depth; it must not break the calling request.
// ============================================================================

import { headers } from 'next/headers';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import {
  getRedis,
  isRedisReady,
  ADMIN_AUDIT_STREAM_CHANNEL,
} from './redis';

// AuditAction is a Prisma enum — we mirror the relevant slice for
// transcribe-md-side call sites. Keeping this as a union rather than
// importing the Prisma enum spares us a cross-boundary-type issue with
// the `@meddoc/db` barrel (which intentionally uses `any`).
export type AuditAction =
  // Anchored verifier — AUDIT-ONLY. It still runs and still judges, but
  // nothing it finds becomes pending state; this row is the durable record.
  // Metadata is category counts only (visitId + {reason: n}), never note text.
  | 'ANCHOR_FLAGS_RECORDED'
  // Auth
  | 'LOGIN_SUCCESS'
  | 'LOGIN_FAILED'
  | 'LOGOUT'
  | 'PASSWORD_CHANGED'
  | 'SESSION_EXPIRED'
  // MFA — added closing shadow-audit HIPAA_FINDING_001. Already in
  // the Prisma AuditAction enum; surfaced here so call sites typecheck.
  | 'MFA_ENABLED'
  | 'MFA_DISABLED'
  | 'MFA_CHALLENGE_PASSED'
  | 'MFA_CHALLENGE_FAILED'
  // Admin
  | 'ADMIN_DASHBOARD_ACCESS'
  | 'ADMIN_API_ACCESS'
  // Phase 6 — admin user-management actions
  | 'USER_SUSPENDED'
  | 'USER_UNSUSPENDED'
  | 'USER_SOFT_DELETED'
  | 'USER_FORCE_LOGOUT'
  | 'USER_PASSWORD_RESET_TRIGGERED'
  | 'USER_GRANTED_SUPER_ADMIN'
  | 'USER_REVOKED_SUPER_ADMIN'
  // Phase 6H — threat-management actions on /admin/threats
  | 'THREAT_INVESTIGATED'
  | 'THREAT_RESOLVED'
  | 'THREAT_DISMISSED_FALSE_POSITIVE'
  // Phase 7B — HIPAA-finding workflow on /admin/hipaa
  | 'HIPAA_FINDING_RESOLVED'
  | 'HIPAA_FINDING_REOPENED'
  // Visit lifecycle
  | 'VISIT_SIGNED'
  | 'VISIT_DELETED'
  | 'VISIT_ARCHIVED'
  | 'VISIT_UNARCHIVED'
  | 'VISIT_RESTORED'
  | 'VISIT_RETRY'
  | 'VISIT_RETRY_BUDGET_EXHAUSTED'
  // Exports
  | 'EXPORT_EMAIL_SENT'
  | 'EXPORT_EMAIL_BLOCKED_DESTINATION'
  | 'EXPORT_PDF_DOWNLOADED'
  | 'EXPORT_DOCX_DOWNLOADED'
  | 'EXPORT_CLIPBOARD_COPIED'
  | 'EXPORT_ACCOUNT_ARCHIVE_DOWNLOADED'
  | 'EXPORT_PATIENT_ARCHIVE_DOWNLOADED'
  // Patient CRUD (TranscribeMdPatient)
  | 'TM_PATIENT_CREATED'
  | 'TM_PATIENT_UPDATED'
  | 'TM_PATIENT_DELETED'
  // Settings + account
  | 'EMAIL_CHANGE_REQUESTED'
  | 'EMAIL_CHANGE_CONFIRMED'
  | 'ACCOUNT_DELETED'
  // Rx safety
  | 'RX_OVERRIDE_RECORDED'
  | 'RX_SIGN_BLOCKED_NO_OVERRIDE'
  // Phase 17 — §164.312(b) audit-completeness fixes
  | 'AUDIO_UPLOADED'
  | 'DOC_EDITOR_SAVED'
  | 'DOC_EDITOR_AI_SUGGESTED'
  | 'PHI_EXTRACTED_FROM_VOICE'
  // Round 3 PR-C — §164.312(b) PHI-READ audit gap (A05-P0-004)
  | 'VIEWED_VISIT'
  | 'VIEWED_VISIT_LIST'
  | 'VIEWED_VISIT_AUDIO'
  // Round 3 PR-C — read actions for VIEWED_PATIENT_LIST and
  // VIEWED_PATIENT_FILE already exist in the Prisma enum (Phase 1
  // legacy), but were never emitted by transcribe-md's PHI reads.
  // Mirror them into the TS union so the call sites typecheck.
  | 'VIEWED_PATIENT_LIST'
  | 'VIEWED_PATIENT_FILE'
  // Round 3 PR-D — AI safety deterministic-backstop audit emits
  | 'PIPELINE_REJECTED_TOO_SHORT'
  | 'PIPELINE_REJECTED_INSUFFICIENT_TRANSCRIPT'
  | 'PIPELINE_FABRICATION_FLAGGED'
  | 'CODING_COACH_REJECTED_INVALID_ICD'
  | 'CODING_COACH_REJECTED_INVALID_CPT'
  | 'RX_DOSE_EXCEEDS_VERIFIED_RANGE'
  | 'RX_CONTRAINDICATION_MATCH'
  | 'RX_DRUG_NOT_IN_VERIFIED_DATABASE'
  // Round 3 PR-J — input validation audit (A07-P0/P1)
  | 'PIPELINE_REJECTED_INJECTION_DELIMITER'
  | 'AUDIO_REJECTED_INVALID_MAGIC_BYTES'
  | 'AUDIO_REJECTED_FILE_TOO_LARGE'
  | 'TEXT_INPUT_REJECTED_TOO_LARGE'
  // Coding-coach bump persistence (Phase 5.2 stub completion)
  | 'EM_BUMP_APPLIED'
  // Coding-coach override persistence (Phase 5.2 orphan-completion)
  | 'EM_OVERRIDE_APPLIED'
  // §164.312(b) audit-row coverage extension (QA agent v3.2 F-09/F-10/F-11)
  | 'VIEWED_DASHBOARD'
  | 'VISIT_CREATED'
  | 'VIEWED_SETTINGS'
  // PR-L follow-up: Whisper-fallback canary. Layer-1 (and 1b dictation)
  // emit this when the transcribe() orchestrator's primary Deepgram
  // call failed and Whisper saved the visit.
  | 'TRANSCRIPTION_PROVIDER_FALLBACK'
  // Q1 #09.1 (2026-06-10) — Anthropic content-policy refusal
  // (stop_reason=refusal). Emitted by the worker's outer catch when a
  // layer's model call was declined; categorized PERMANENT so the visit
  // fails fast into the DLQ. Metadata carries { layer, model, purpose? } —
  // never model output. Operators count refusals in /admin/audit.
  | 'AI_REFUSAL'
  // Deep-audit G9 (2026-05-12) — partial automation failure. Emitted
  // when at least one load-bearing L7 layer (icd-coding / cpt-coding /
  // rx-drafting) errored during the fan-out + the worker flipped
  // needsReview on the visit. Metadata carries the failedLayers list
  // + per-layer reasons (truncated). Forensics surface in /admin/audit.
  | 'VISIT_AUTOMATION_INCOMPLETE'
  // 2026-05-12 stuck-visit watchdog. Emitted by the per-minute sweep
  // when a visit is force-failed because its status has been in an
  // in-flight state (TRANSCRIBING / EXTRACTING / DRAFTING / etc.) past
  // the global 15-min budget. Metadata carries { prevStatus, elapsedMin,
  // thresholdMin, processingStartedAt } for admin forensics.
  | 'VISIT_PROCESSING_TIMEOUT'
  // FIND-P1-003 (2026-05-14) — Layer-2 manual speaker-role override
  // closure. Was emitted by reassignSpeakerAction when a doctor reassigned a
  // speaker on the Transcript tab. Metadata carries { source, speakerId,
  // previousRole, newRole } — no PHI.
  //
  // RETIRED 2026-07-28: nothing writes this any more. The action was deleted
  // with the transcript panel (see the note in actions/soap.ts). The VALUE
  // stays — rows written before that date still carry it, and an audit enum
  // that forgets its own history makes its own records unreadable.
  | 'SPEAKER_ROLE_REASSIGNED'
  // FIND-P1-015 + FIND-P1-016 (2026-05-14) — emitted by L4 / L6 when
  // the lenient SOAP-structure validator (soap-structure-validator.ts)
  // rejects the model output (empty / JSON-shape / missing sections).
  // Metadata: { layer, reason, outputLength, missingSections } — no PHI.
  | 'MODEL_OUTPUT_VALIDATION_FAIL'
  // L6 fabrication gate (2026-06-11 — hallucination-reconciliation RED
  // finding). Post-polish fidelity gate rejected L6's output (new
  // clinical claims vs its input / meaning flip / ANY gate failure —
  // fail-closed) → fell back to the pre-L6 (L4) draft. Metadata:
  // { layer, violationCount, kinds, novelTermCount, gateError?,
  // fellBackToDraft } — counts + class strings only, no note content.
  | 'L6_FABRICATION_REJECTED'
  // Hybrid anchored generation (2026-06-11) — explicit doctor adoption of a
  // verifier-demoted claim ("Suggested by AI" lane). Metadata: { section,
  // reason, remaining } — never claim text.
  | 'SUGGESTION_ADOPTED'
  // One row per chat-editor turn. Its EFFECTS are audited by the actions it
  // dispatches into, but those rows are byte-identical to a button click —
  // this one records that the chat was what did it.
  | 'CHAT_EDIT_TURN'
  // A header field on an unsigned visit was corrected — the patient's name or
  // the chief complaint. Present in the DB enum since the original schema;
  // added to this union when updateVisitHeaderAction gave it a caller.
  // Metadata: { via, field, affectsOtherVisits? } — field NAMES only, never the
  // value, because the value is the patient's name.
  | 'EDITED_NOTE'
  // Sign refused because the note changed since the E/M level was scored.
  | 'EM_SIGN_BLOCKED_STALE'
  // The E/M level was re-scored against a changed note.
  | 'EM_RESCORED'
  | 'SUGGESTION_DISMISSED'
  // E/M recompute on adoption — visible-confirm, never silent (2026-06-12,
  // prod smoke #311). EM_LEVEL_CHANGED: an adopt/dismiss suggestion action
  // changed the computed E/M level. Metadata: EXACTLY { from, to, cause }
  // where cause ∈ {'suggestion_adopted','suggestion_dismissed'} — CPT codes
  // + cause class only, never note text.
  // EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE: a sign request was rejected
  // because a recorded E/M change had not been acknowledged. Metadata:
  // { from, to, cause } of the pending change.
  | 'EM_LEVEL_CHANGED'
  | 'EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE'
  // F-8 audit leg (2026-07-02) — deterministic drug-pair floor (L7c).
  // RX_DRUG_PAIR_* metadata: { ruleId, primaryDrug, otherDrug, severity,
  // doseMgPerDay? }. RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY carries the
  // single-drug validator shape { drug } (table-derived name). Drug names +
  // rule class only, never note/transcript content.
  | 'RX_DRUG_PAIR_INTERACTION'
  | 'RX_DRUG_PAIR_DOSE_CAP'
  | 'RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY';

export interface AuditLogInput {
  action: AuditAction;
  targetId?: string | null;
  targetType?: string | null;
  /** Field NAMES only — never raw PHI values */
  metadata?: Record<string, unknown>;
  success?: boolean;
  errorCode?: string | null;
  /** Override userId when getSession() isn't available (pre-session
   *  events like failed logins). */
  userId?: string | null;
  /** Override user email snapshot — same rationale. */
  userEmail?: string | null;
  /** Override practiceId. Required for truly-anonymous events;
   *  otherwise resolved from the session. Falls back to
   *  'clinic_main' (same sentinel as meddoc-pro). */
  practiceId?: string | null;
}

async function getRequestContext(): Promise<{
  ipAddress: string | null;
  userAgent: string | null;
}> {
  try {
    const h = await headers();
    const ipAddress =
      h.get('x-forwarded-for')?.split(',')[0]?.trim() ||
      h.get('x-real-ip') ||
      null;
    const userAgent = h.get('user-agent') || null;
    return { ipAddress, userAgent };
  } catch {
    return { ipAddress: null, userAgent: null };
  }
}

/** Write a single audit row. Never throws. */
export async function logAudit(input: AuditLogInput): Promise<void> {
  try {
    // 2026-05-13 — when callers pass both userId AND practiceId we
    // skip session resolution entirely. Two wins: (1) saves the
    // round-trip in request scope; (2) avoids the worker-context
    // failure mode where `auth()` throws synchronously inside the
    // Auth.js v5 internals (it reads `headers()` while computing the
    // JWT callback chain, and headers() is request-scoped only).
    //
    // The `Promise.resolve().then(...)` wrap is the synchronous-throw
    // belt: `.catch()` only fires for REJECTED promises, but auth()
    // can throw BEFORE returning a thenable (the worker-context
    // path); wrapping the call in a `.then` callback re-routes the
    // throw into a promise rejection that `.catch` then handles.
    const hasFullOverride = !!input.userId && !!input.practiceId;
    const session = hasFullOverride
      ? null
      : await Promise.resolve()
          .then(() => auth())
          .catch(() => null);
    const { ipAddress, userAgent } = await getRequestContext();

    const userId = input.userId ?? session?.user?.id ?? null;
    const userEmailSnapshot =
      input.userEmail ?? session?.user?.email ?? null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sessionPracticeId = (session?.user as any)?.practiceId as
      | string
      | undefined;
    const practiceId =
      input.practiceId ?? sessionPracticeId ?? 'clinic_main';

    const entry = {
      userId,
      userEmailSnapshot,
      action: input.action,
      targetId: input.targetId ?? null,
      targetType: input.targetType ?? null,
      ipAddress,
      userAgent,
      metadata: (input.metadata ?? null) as unknown as object | null,
      success: input.success ?? true,
      errorCode: input.errorCode ?? null,
      timestamp: new Date(),
      practiceId,
      // S4c tombstone. practiceId is now a nullable FK that goes NULL when the
      // practice is deleted (so an account deletion can never delete its own
      // audit trail). This copy carries no FK and therefore survives, keeping
      // "which tenant did this happen in" answerable afterwards — the same job
      // userEmailSnapshot does for the user.
      practiceIdSnapshot: practiceId,
    };

    // Prisma's shared barrel exports `any` (see memory note on typing).
    // The cast keeps the call site strict without dragging the global
    // any through the rest of the file.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    await prisma.auditLog.create({ data: entry as any });

    // Symmetric SSE fan-out — mirrors meddoc-pro/audit.ts. Uses the
    // dedicated pub/sub singleton from `./redis` (kept separate from
    // the BullMQ-shared connection in `./queue`, which uses
    // `maxRetriesPerRequest: null` and would risk blocking the
    // calling request if a publish queued indefinitely on a degraded
    // broker). Three layers keep this fire-and-forget:
    //   1. setImmediate — defer past the current request response
    //   2. isRedisReady() — skip silently if the singleton isn't live
    //   3. 100ms race — bound the publish wallclock either way
    setImmediate(() => {
      if (!isRedisReady()) return;
      const publishPromise = getRedis().publish(
        ADMIN_AUDIT_STREAM_CHANNEL,
        JSON.stringify(entry)
      );
      const timeout = new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('publish timeout')), 100)
      );
      Promise.race([publishPromise, timeout]).catch(() => {
        // Silent — best-effort, row is durable.
      });
    });
  } catch (err) {
    // Audit logging must never break the calling request. A Prisma
    // failure here likely means the audit_logs table is unreachable —
    // fall back to a single-line stderr so the event isn't lost in
    // a downstream log-parse.
    console.error(
      `[audit] write failed action=${input.action} target=${input.targetType ?? '-'}:${input.targetId ?? '-'}`,
      err instanceof Error ? err.message : err
    );
  }
}
