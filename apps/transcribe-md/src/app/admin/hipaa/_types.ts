// ============================================================================
// /admin/hipaa — shared types (Phase 7B)
// ----------------------------------------------------------------------------
// Same shape as the GET /api/admin/hipaa response so the client orchestrator
// can swap SSR seed data for refetched data without remapping fields.
// ============================================================================

export type FindingSeverity = 'critical' | 'high' | 'medium' | 'low';
export type FindingStatus = 'open' | 'in_progress' | 'resolved';
export type HipaaTab = 'open' | 'resolved' | 'all';

export interface HipaaFindingRow {
  id: string;
  control: string;
  /** Stored as text in DB so future severity additions don't need a
   *  migration; UI handles known values + falls back to a neutral pill. */
  severity: string;
  title: string;
  detail: string | null;
  status: string;
  resolvedAt: string | null;
  resolvedById: string | null;
  resolvedByEmail: string | null;
  resolutionNote: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface AdminHipaaInitialData {
  findings: HipaaFindingRow[];
}
