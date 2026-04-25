// ============================================================================
// Shared types for the /admin/usage surface
// ----------------------------------------------------------------------------
// Mirrors the response shapes of /api/admin/usage/* endpoints (so the
// client can swap between SSR-seed and client-fetch without a transform)
// + a small extra `Anomaly` type computed server-side here, since the
// Phase 6A backend doesn't have a dedicated endpoint for it yet.
// ============================================================================

export type WindowKey = '24h' | '7d' | '30d' | 'month';

export interface UsageSummary {
  window: string;
  since: string;
  until: string;
  totalCostUsd: number;
  totalEvents: number;
  byProvider: Record<string, number>;
  byOperation: Record<string, number>;
  vsLastPeriod: { totalCostUsd: number; percentChange: number | null };
}

export interface TimelineBucket {
  /** ISO timestamp at the start of the bucket. */
  time: string;
  totalCostUsd: number;
  events: number;
  byProvider: Record<string, number>;
}

export interface TimelineResponse {
  window: string;
  granularity: 'hour' | 'day';
  since: string;
  until: string;
  buckets: TimelineBucket[];
}

export interface TopUserRow {
  userId: string | null;
  userEmail: string;
  totalCostUsd: number;
  events: number;
}

export interface TopUsersResponse {
  window: string;
  since: string;
  until: string;
  sortBy: 'cost' | 'events';
  rows: TopUserRow[];
}

export type Anomaly =
  | {
      kind: 'user_spike';
      userId: string;
      userName: string;
      todayUsd: number;
      avgDailyUsd: number;
    }
  | {
      kind: 'api_failure_burst';
      provider: string;
      count: number;
      windowLabel: string;
    };

export interface AdminUsageInitialData {
  summary: UsageSummary;
  timeline: TimelineResponse;
  topUsers: TopUsersResponse;
  anomalies: Anomaly[];
}
