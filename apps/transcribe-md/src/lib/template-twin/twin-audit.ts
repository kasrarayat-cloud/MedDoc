// ============================================================================
// Template Twin audit wrapper — keeps @/lib/audit BYTE-IDENTICAL (frozen).
// ----------------------------------------------------------------------------
// The 10 TEMPLATE_TWIN_* actions ARE registered in the Prisma AuditAction enum
// (additive migration 20260722063000). The shared @/lib/audit `AuditAction`
// mirror deliberately does NOT list them, so that frozen surface stays
// byte-identical. This module owns the twin action type and widens at the single
// logAudit boundary — the only cast, localized here rather than smeared across
// call sites. Writes go to the SAME logAudit (prisma.auditLog.create) — no new
// audit writer, no enforcement gate.
// ============================================================================

import { logAudit as baseLogAudit } from '@/lib/audit';

export type TwinAuditAction =
  | 'TEMPLATE_TWIN_SOURCE_UPLOADED'
  | 'TEMPLATE_TWIN_COMPILED'
  | 'TEMPLATE_TWIN_QUARANTINED'
  | 'TEMPLATE_TWIN_MAPPING_UPDATED'
  | 'TEMPLATE_TWIN_CERTIFIED'
  | 'TEMPLATE_TWIN_ACTIVATED'
  | 'TEMPLATE_TWIN_SYNTHETIC_TESTED'
  | 'TEMPLATE_TWIN_FIELD_REVIEWED'
  | 'TEMPLATE_TWIN_SIGN_BLOCKED'
  | 'TEMPLATE_TWIN_RENDER_VERIFIED';

type BaseEntry = Parameters<typeof baseLogAudit>[0];

/** logAudit for twin actions. Same writer, twin-owned action typing. */
export function logTwinAudit(
  entry: Omit<BaseEntry, 'action'> & { action: TwinAuditAction },
): ReturnType<typeof baseLogAudit> {
  return baseLogAudit({
    ...entry,
    // Valid Prisma AuditAction (additive migration); widened here only because
    // the frozen @/lib/audit mirror intentionally omits twin actions.
    action: entry.action as BaseEntry['action'],
  });
}
