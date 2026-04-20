// ============================================================================
// Dashboard pagination types + constants (T-M16.4 M5)
// ----------------------------------------------------------------------------
// Split out of actions/visits.ts because Next 16's 'use server' directive
// requires every export of a server-action file to be an async function.
// Exporting a const (DASHBOARD_PAGE_SIZE) or an interface
// (DashboardCursor / LoadMoreVisitsResult) from that file fails the
// build with "Export X doesn't exist in target module" on the
// client-side import. Pure types + constants belong here; the action
// that consumes them stays in actions/visits.ts.
// ============================================================================

import type { TranscribeVisitStatus } from '@prisma/client';

export const DASHBOARD_PAGE_SIZE = 20;

export interface DashboardCursor {
  /** ISO string — JSON-safe across the server-action boundary. */
  createdAt: string;
  id: string;
}

export interface LoadMoreVisitsResult {
  visits: Array<{
    id: string;
    patientName: string | null;
    specialty: string;
    status: TranscribeVisitStatus;
    createdAt: Date;
  }>;
  /** Null when this was the last page. */
  nextCursor: DashboardCursor | null;
}
