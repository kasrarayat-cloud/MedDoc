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
  // Auth
  | 'LOGIN_SUCCESS'
  | 'LOGIN_FAILED'
  | 'LOGOUT'
  | 'PASSWORD_CHANGED'
  | 'SESSION_EXPIRED'
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
  | 'EM_OVERRIDE_APPLIED';

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
    const session = await auth().catch(() => null);
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
