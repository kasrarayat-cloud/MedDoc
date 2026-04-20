// ============================================================================
// Date-of-birth validator (shared client helper)
// ----------------------------------------------------------------------------
// Used by the T-M17.2 Commit 9 inline-create flow (/visits/new patient
// picker) and the Commit 10 Edit Patient dialog.
//
// Catches three common typo shapes that a bare `type=date` input still
// accepts: year-out-of-range (5000-01-01, 1899-12-31), future dates,
// and impossible calendar days (2024-02-30 — which HTML would parse
// as 2024-03-01 silently).
//
// `validateDob('')` returns an error — callers that treat empty as
// "unset DOB" should branch on empty-string BEFORE calling this.
// ============================================================================

/** Floor year for a plausible patient DOB. Anything earlier is almost
 *  certainly a typo (oldest living humans are ~120 years old). */
export const MIN_DOB_YEAR = 1900;

export type DobValidationResult =
  | { ok: true; iso: string }
  | { ok: false; error: string };

export function validateDob(input: string): DobValidationResult {
  if (!input) return { ok: false, error: 'Date of birth is required.' };

  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(input);
  if (!m) return { ok: false, error: 'Use YYYY-MM-DD.' };

  const year = Number(m[1]);
  const month = Number(m[2]);
  const day = Number(m[3]);

  // Parse as UTC to avoid TZ shifts; roundtrip-check catches
  // impossible dates (Date.UTC wraps silently so Feb-30 becomes
  // March-1 without this guard).
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    Number.isNaN(date.getTime()) ||
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return { ok: false, error: 'Not a real date.' };
  }

  if (year < MIN_DOB_YEAR) {
    return { ok: false, error: `Year must be ${MIN_DOB_YEAR} or later.` };
  }
  if (date.getTime() > Date.now()) {
    return { ok: false, error: 'DOB cannot be in the future.' };
  }

  return { ok: true, iso: input };
}
