// ============================================================================
// Admin overview dashboard — shared types
// ----------------------------------------------------------------------------
// Imported by both the server-side data layer (`_lib/dashboard-data.ts`) and
// the client component (`_components/AdminOverview.client.tsx`). Types are
// normalised to what the UI actually consumes — the server-side helpers
// transform raw Prisma rows / API shapes into these.
// ============================================================================

export type HealthStatus = 'healthy' | 'degraded' | 'down';
export type ServiceKey = 'database' | 'redis' | 'minio' | 'externalAPIs';

export interface ServiceHealth {
  status: HealthStatus;
  /** Short metric line displayed under the status badge — e.g. "p95 8ms" or "12.4 GB used". */
  metric: string;
}

export type SystemHealth = Record<ServiceKey, ServiceHealth>;

export type ActivityCategory = 'auth' | 'visit' | 'export' | 'admin';
export type FilterKey = 'all' | ActivityCategory;

export interface ActivityRow {
  id: string;
  /** Local-time clock formatted as "HH:MM:SS" — already lower-resolution than ISO. */
  timestamp: string;
  action: string;
  category: ActivityCategory;
  actorEmail: string;
  /** Visit/resource id, formatted "TargetType:short_id" — undefined when none. */
  target?: string;
  ip: string;
  success: boolean;
  /** Briefly true after an SSE arrival so the row can fade in. */
  isNew?: boolean;
}

export type ThreatSeverity = 'amber' | 'red';

export interface Threat {
  id: string;
  type: string;
  severity: ThreatSeverity;
  summary: string;
  detail: string;
}

export type ThreatResolutionKind = 'RESOLVED' | 'FALSE_POSITIVE';

export interface ResolvedThreat extends Threat {
  resolutionKind: ThreatResolutionKind;
  resolvedAt: string;
  resolvedByEmail: string | null;
  note: string | null;
}

export interface TimelineBucket {
  /** Local hour 0..23. */
  hour: number;
  total: number;
  failed: number;
}

export interface PipelineMetrics {
  successRate: number;
  /** Pre-formatted human strings — e.g. "4.2s", "14.1s", or "—" when no data. */
  p50: string;
  p95: string;
  total: number;
  succeeded: number;
  failed: number;
  pending: number;
}

export interface HipaaFinding {
  severity: 'critical' | 'high' | 'medium';
  total: number;
  resolved: number;
}

export interface HipaaState {
  findings: HipaaFinding[];
  auditCoverage: { covered: number; total: number };
  /** Free-form short label — e.g. "today", "2 days ago". */
  lastReview: string;
}

/** Bundled props passed from the server page to the client overview. */
export interface AdminOverviewInitialData {
  systemHealth: SystemHealth;
  activity: ActivityRow[];
  threats: Threat[];
  timeline: TimelineBucket[];
  pipeline: PipelineMetrics;
  hipaa: HipaaState;
}
