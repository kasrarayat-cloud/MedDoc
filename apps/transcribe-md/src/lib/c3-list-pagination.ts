// ============================================================================
// C3 list pagination — types + page sizes for the calm-skin scalable lists
// (dashboard "Ready to sign" inbox + the Patients list).
// ----------------------------------------------------------------------------
// Split out of the 'use server' action files because Next 16 requires every
// export of a 'use server' module to be an async function — pure types +
// consts live here (same reason as @/lib/dashboard-pagination).
//
// READ-ONLY: these describe cursor pages over the SAME user/practice-scoped
// reads the existing UI already runs. No write path, no behavior change.
// ============================================================================

import type { TranscribeVisitStatus } from '@prisma/client';

export const C3_INBOX_PAGE_SIZE = 25;
export const C3_PATIENTS_PAGE_SIZE = 24;

/** Cursor over (updatedAt desc, id desc) — JSON-safe across the action boundary. */
export interface C3InboxCursor {
  updatedAt: string;
  id: string;
}

/** A visit row as the calm inbox renders it (no PHI beyond what the list
 *  already shows). Dates are ISO strings for the client boundary. */
export interface C3InboxRow {
  id: string;
  patientName: string | null;
  specialty: string;
  status: TranscribeVisitStatus;
  needsReview: boolean;
  chiefComplaint: string | null;
}

export interface C3InboxPage {
  rows: C3InboxRow[];
  nextCursor: C3InboxCursor | null;
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
