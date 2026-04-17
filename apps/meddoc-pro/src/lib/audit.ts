// ============================================================================
// HIPAA Audit Logger (§164.312(b))
// ----------------------------------------------------------------------------
// Append-only log of every PHI-touching action. Call from server actions,
// API routes, and server components. NEVER call from a client component
// (the IP/user-agent would be wrong and the user could spoof it).
//
// IMPORTANT — never put raw PHI in `metadata`. Use field NAMES, not values.
//   GOOD: { changedFields: ['firstName', 'mrn'] }
//   BAD:  { newName: 'Sarah Mitchell' }
// ============================================================================

import prisma, { isDatabaseHealthy } from '@meddoc/db';
import { getSession, getRequestContext, type Session } from './auth';
import { tenantScope } from './tenancy';

// Mirror Prisma enum (kept here so client/server tools can import w/o full Prisma)
export type AuditAction =
  | 'LOGIN_SUCCESS'
  | 'LOGIN_FAILED'
  | 'LOGOUT'
  | 'MFA_ENABLED'
  | 'MFA_DISABLED'
  | 'MFA_CHALLENGE_PASSED'
  | 'MFA_CHALLENGE_FAILED'
  | 'PASSWORD_CHANGED'
  | 'PASSWORD_RESET_BY_ADMIN'
  | 'SESSION_EXPIRED'
  | 'VIEWED_PATIENT_LIST'
  | 'VIEWED_PATIENT_FILE'
  | 'CREATED_PATIENT'
  | 'UPDATED_PATIENT'
  | 'ARCHIVED_PATIENT'
  | 'VIEWED_DOCUMENT'
  | 'CREATED_DOCUMENT'
  | 'CREATED_CLINICAL_NOTE'
  | 'GENERATED_DRAFT_DOCUMENT'
  | 'EDITED_NOTE'
  | 'DOWNLOADED_DOCUMENT'
  | 'DELETED_DOCUMENT'
  | 'UPLOADED_TO_DROPBOX'
  | 'SCHEDULED_VISIT'
  | 'UPDATED_APPOINTMENT_STATUS'
  | 'DELETED_APPOINTMENT'
  | 'CREATED_ALLERGY'
  | 'UPDATED_ALLERGY'
  | 'DELETED_ALLERGY'
  | 'CREATED_MEDICATION'
  | 'UPDATED_MEDICATION'
  | 'DELETED_MEDICATION'
  | 'SYNCED_FROM_DRCHRONO'
  | 'PUSHED_TO_DRCHRONO'
  // M6 — CRM loop-closing
  | 'CREATED_TASK'
  | 'CREATED_BILLING_EVENT'
  | 'USER_CREATED'
  | 'USER_UPDATED'
  | 'USER_ROLE_CHANGED'
  | 'USER_DEACTIVATED'
  | 'USER_DELETED'
  | 'EXPORTED_AUDIT_LOG';

export interface AuditLogInput {
  action: AuditAction;
  targetId?: string | null;
  targetType?: string | null;
  /** Field NAMES only — never raw PHI values */
  metadata?: Record<string, unknown>;
  success?: boolean;
  errorCode?: string | null;
  /** Override userId. Useful when called from `events.signIn` where the
   *  session cookie hasn't been set on the outgoing response yet, so
   *  `getSession()` inside logAudit would return null. */
  userId?: string | null;
  /** Override user email snapshot — same rationale as userId. */
  userEmail?: string | null;
  /** Override practiceId. Required for pre-authenticated events (e.g.,
   *  failed logins for unknown emails) where there's no session to pull
   *  from. Falls back to session's practiceId, then to 'clinic_main'. */
  practiceId?: string | null;
}

/**
 * In-memory audit log buffer used when DB is not available.
 * Capped at 1000 entries (oldest dropped) to prevent unbounded growth.
 * In production this should NEVER be reached — DB must be available.
 */
const memoryAuditLog: Array<Record<string, unknown>> = [];
const MAX_MEMORY_LOGS = 1000;

/**
 * Write a single audit log entry. Pulls userId/IP/UA from the current request
 * automatically. Designed to be fire-and-forget — never throws so it can't
 * break the calling action.
 */
export async function logAudit(input: AuditLogInput): Promise<void> {
  try {
    const session = await getSession();
    const { ipAddress, userAgent } = await getRequestContext();

    // practiceId resolution chain: explicit override → session → last-
    // resort fallback. The fallback only fires for truly-anonymous events
    // (e.g., failed login for an email that doesn't exist). Phase 2 may
    // promote this to a dedicated platform practice.
    const practiceId =
      input.practiceId ?? session?.user.practiceId ?? 'clinic_main';

    const entry = {
      userId: input.userId ?? session?.user.id ?? null,
      userEmailSnapshot: input.userEmail ?? session?.user.email ?? null,
      action: input.action,
      targetId: input.targetId ?? null,
      targetType: input.targetType ?? null,
      ipAddress,
      userAgent,
      metadata: input.metadata ?? null,
      success: input.success ?? true,
      errorCode: input.errorCode ?? null,
      timestamp: new Date(),
      practiceId,
    };

    if (await isDatabaseHealthy()) {
      // Real DB write
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await prisma.auditLog.create({ data: entry as any });
    } else {
      // Memory fallback — also mirror to console for visibility
      memoryAuditLog.push(entry);
      if (memoryAuditLog.length > MAX_MEMORY_LOGS) {
        memoryAuditLog.shift();
      }
      // Single-line format for grep-ability in dev logs
      console.log(
        `[AUDIT] ${entry.timestamp.toISOString()} user=${entry.userId} action=${entry.action} target=${entry.targetType}:${entry.targetId} ip=${entry.ipAddress ?? '-'} success=${entry.success}`
      );
    }
  } catch (err) {
    // Audit logging must never break the calling action.
    // In production this should trigger a CRITICAL alert.
    console.error('[AUDIT] Failed to write log:', err);
  }
}

/**
 * Read the in-memory audit buffer (only used when DB is unavailable).
 * For real audit log viewing in production, query the `audit_logs` table directly.
 */
export function getMemoryAuditLog(): ReadonlyArray<Record<string, unknown>> {
  return memoryAuditLog;
}

// ---------------------------------------------------------------------------
// Typed audit log view for the admin dashboard
// ---------------------------------------------------------------------------

export interface AuditLogView {
  id: string;
  userId: string | null;
  userEmail: string | null;
  action: string;
  targetId: string | null;
  targetType: string | null;
  ipAddress: string | null;
  success: boolean;
  errorCode: string | null;
  timestamp: string; // ISO
}

/**
 * Fetch audit logs, newest first. Prisma-first with memory fallback.
 * Scoped to the session's practice unless SUPER_ADMIN.
 */
export async function getAuditLogs(
  session: Session,
  limit = 200
): Promise<AuditLogView[]> {
  if (await isDatabaseHealthy()) {
    try {
      const rows = await prisma.auditLog.findMany({
        where: tenantScope(session),
        orderBy: { timestamp: 'desc' },
        take: limit,
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return rows.map((r: any) => ({
        id: r.id,
        userId: r.userId ?? null,
        userEmail: r.userEmailSnapshot ?? null,
        action: r.action,
        targetId: r.targetId ?? null,
        targetType: r.targetType ?? null,
        ipAddress: r.ipAddress ?? null,
        success: r.success ?? true,
        errorCode: r.errorCode ?? null,
        timestamp: r.timestamp.toISOString(),
      }));
    } catch (err) {
      console.warn('[audit] Prisma findMany failed, using memory:', err);
    }
  }

  // Memory fallback — reverse for newest first
  return [...memoryAuditLog]
    .reverse()
    .slice(0, limit)
    .map((entry, i) => ({
      id: `mem_${i}`,
      userId: String(entry.userId ?? ''),
      userEmail: String(entry.userEmailSnapshot ?? ''),
      action: String(entry.action ?? ''),
      targetId: entry.targetId ? String(entry.targetId) : null,
      targetType: entry.targetType ? String(entry.targetType) : null,
      ipAddress: entry.ipAddress ? String(entry.ipAddress) : null,
      success: Boolean(entry.success ?? true),
      errorCode: entry.errorCode ? String(entry.errorCode) : null,
      timestamp: entry.timestamp instanceof Date
        ? entry.timestamp.toISOString()
        : String(entry.timestamp ?? new Date().toISOString()),
    }));
}
