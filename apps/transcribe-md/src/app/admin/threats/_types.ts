// ============================================================================
// /admin/threats — page-local types
// ----------------------------------------------------------------------------
// Re-exports the shared Threat / ResolvedThreat shapes from the parent
// admin _types module, plus the response shapes for the investigate
// endpoint (only used on this page).
// ============================================================================

import type { Threat, ResolvedThreat, ThreatResolutionKind } from '../_types';

export type { Threat, ResolvedThreat, ThreatResolutionKind };

export type ThreatTab = 'active' | 'resolved' | 'false_positive';

export type HistoryWindow = '7d' | '30d';

export interface AuditTimelineRow {
  id: string;
  timestamp: string;
  action: string;
  userEmailSnapshot: string | null;
  ipAddress: string | null;
  targetType: string | null;
  targetId: string | null;
  success: boolean | null;
  errorCode: string | null;
}

export interface UserProfile {
  id: string;
  email: string | null;
  fullName: string | null;
  practiceId: string | null;
  isActive: boolean;
  lastLoginAt: string | null;
}

export interface IpContext {
  ipAddress: string;
  totalEventsLast7d: number;
  failedLoginsLast7d: number;
  distinctUsersLast7d: number;
  firstSeen: string | null;
  lastSeen: string | null;
}

export interface InvestigateResponse {
  threatId: string;
  kind: string;
  timeline: AuditTimelineRow[];
  user: UserProfile | null;
  ip: IpContext | null;
}

export interface AdminThreatsInitialData {
  active: Threat[];
  resolved: ResolvedThreat[];
}
