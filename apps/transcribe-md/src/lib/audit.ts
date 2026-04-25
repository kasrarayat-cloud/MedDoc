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
import { getSharedRedisConnection } from './queue';

/** Channel name shared with apps/meddoc-pro/src/lib/redis.ts. Hard-
 *  coded here rather than imported because the two apps don't share a
 *  workspace package for Redis primitives. Keep them in sync. */
const ADMIN_AUDIT_STREAM_CHANNEL = 'admin:audit-stream';

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
  | 'RX_SIGN_BLOCKED_NO_OVERRIDE';

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
    // Phase 1B — fire-and-forget pub/sub. Awaiting publish() with the
    // BullMQ-style maxRetriesPerRequest:null connection can stall for
    // tens of seconds when Redis is briefly unreachable, blocking
    // whatever caller awaited logAudit (e.g., signing). Detach.
    void getSharedRedisConnection()
      .publish(ADMIN_AUDIT_STREAM_CHANNEL, JSON.stringify(entry))
      .catch((pubErr) => {
        console.warn(
          '[audit] redis publish failed (audit row still saved):',
          pubErr instanceof Error ? pubErr.message : pubErr
        );
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
