// ============================================================================
// C3 list pagination — types + page sizes for the calm-skin scalable lists
// (dashboard "Ready to sign" inbox + the Patients list).
// ----------------------------------------------------------------------------
// Split out of the 'use server' action files because Next 16 requires every
// export of a 'use server' module to be an async function — pure types +
// consts live here (same reason as @/lib/dashboard-pagination).
//
// READ-ONLY: these describe paged reads (OFFSET pages for the inbox work
// queue, cursor pages for the patients list) over the SAME user/practice-
// scoped reads the existing UI already runs. No write path, no behavior change.
// ============================================================================

import type { TranscribeVisitStatus } from '@prisma/client';

// Queue-v2: a sign queue is a FINITE work list, not an endless feed — so the
// inbox uses bounded OFFSET pages (Page X of N + prev/next) capped at ~15-20
// rows, never a flat list that runs off the screen.
export const C3_INBOX_PAGE_SIZE = 18;
export const C3_PATIENTS_PAGE_SIZE = 24;

/** A visit row as the calm inbox renders it (no PHI beyond what the list
 *  already shows). Dates are ISO strings for the client boundary.
 *  `createdAt` powers the Today / This week / Older date grouping. */
export interface C3InboxRow {
  id: string;
  patientName: string | null;
  specialty: string;
  status: TranscribeVisitStatus;
  needsReview: boolean;
  chiefComplaint: string | null;
  createdAt: string;
}

/** One bounded page of the inbox, plus the totals the pager needs. `page` is
 *  1-based and already clamped to [1, totalPages] by the server. */
export interface C3InboxPageResult {
  rows: C3InboxRow[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

/** Cursor over (updatedAt desc, id desc) for the patients list. */
export interface C3PatientsCursor {
  updatedAt: string;
  id: string;
}

export interface C3PatientRow {
  id: string;
  name: string;
  dateOfBirth: string | null;
  visitCount: number;
  lastVisitAt: string | null;
  lastVisitSpecialty: string | null;
  lastVisitStatus: TranscribeVisitStatus | null;
  lastVisitNeedsReview: boolean;
  lastVisitSignedAt: string | null;
}

export interface C3PatientsPage {
  rows: C3PatientRow[];
  nextCursor: C3PatientsCursor | null;
}
