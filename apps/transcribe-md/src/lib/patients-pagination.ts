// ============================================================================
// Patients dashboard pagination types + constants (T-M17.2 Phase 3 Commit 7)
// ----------------------------------------------------------------------------
// Mirrors the T-M16.4 dashboard-pagination module for TranscribeMdPatient.
// Split out of actions/patients.ts for the same reason as the visits
// pagination module — Next 16's 'use server' directive only allows
// async-function exports from the action file.
//
// Sort key: `lastVisitAt DESC NULLS LAST, id DESC`.
//   - Patients with recent visits float to the top.
//   - Patients never seen in a visit (possible after soft-deleting a
//     visit, or after the Phase 3 Commit 9 inline-create flow) sort
//     last, ordered by id.
//   - The cursor carries `lastVisitAt` as an ISO string (nullable) +
//     id so a null-lastVisitAt row can still anchor the next page.
// ============================================================================

export const PATIENTS_PAGE_SIZE = 20;

export interface PatientsCursor {
  /** ISO string when the cursor row has a linked visit; null if the
   *  cursor row is in the "no visits yet" tail of the list. JSON-safe
   *  across the server-action boundary. */
  lastVisitAt: string | null;
  id: string;
}

export interface PatientListItem {
  id: string;
  name: string;
  dateOfBirth: Date | null;
  externalId: string | null;
  visitCount: number;
  lastVisitAt: Date | null;
  /** Specialty of the most recent visit for this patient, or null if
   *  the patient has no visits. Surfaced on the card so the doctor
   *  can see "oh that's the cardiology patient" without clicking. */
  lastVisitSpecialty: string | null;
}

export interface LoadMorePatientsResult {
  patients: PatientListItem[];
  /** Null when this was the last page. */
  nextCursor: PatientsCursor | null;
}
