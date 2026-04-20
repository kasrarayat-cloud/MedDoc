// ============================================================================
// Shared types for the T-M17.2 Commit 9 patient picker.
// ----------------------------------------------------------------------------
// Kept in a non-'use client' file so the server page (page.tsx) can import
// SelectedPatient to shape the initialPatient prop without pulling in the
// client bundle.
// ============================================================================

/** Normalised patient record carried from Step 1 → Step 2. DOB is an
 *  ISO-ish YYYY-MM-DD string (what the API serialises from the Prisma
 *  DATE column), or null for legacy patients who never had a DOB
 *  recorded. */
export interface SelectedPatient {
  id: string;
  name: string;
  dateOfBirth: string | null;
  externalId: string | null;
}

/** Shape of a row from POST /api/patients/fuzzy-match. */
export interface FuzzyMatch {
  patient: {
    id: string;
    name: string;
    dateOfBirth: string | null;
    externalId: string | null;
  };
  score: number;
  dobMatches: boolean | null;
}
