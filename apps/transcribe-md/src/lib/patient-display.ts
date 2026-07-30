// ============================================================================
// Patient-facing display derivations — age and audio duration.
// ----------------------------------------------------------------------------
// Both of these existed as module-private copies: `ageYearsOf` inside
// DemographicsCard and `formatDurationLabel` inside visit-ready-view. Rounds
// Screen 2's identity header needs both, and a THIRD copy of a derivation is
// how the E/M specialty predicate ended up open-coded in seven places, one of
// them spelled wrong and silently false for every ultrasound visit.
//
// So they move here rather than being duplicated, and this module is
// deliberately skin-neutral: it is not under `lib/rounds/`, which item F
// deletes.
//
// No PHI leaves here that did not come in — these are pure formatters over
// values the caller already holds.
// ============================================================================

/**
 * Whole years between `dob` and now, or `null` when there is no usable date.
 *
 * Returns `null` rather than 0 for a future or unparseable DOB: "0" reads as a
 * newborn, and a bad date should show nothing at all rather than a plausible
 * wrong number on a clinical header.
 */
export function ageYearsOf(dob: string | Date | null | undefined): number | null {
  if (!dob) return null;
  const d = dob instanceof Date ? dob : new Date(dob);
  if (Number.isNaN(d.getTime())) return null;
  const years = (Date.now() - d.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
  return years > 0 ? Math.floor(years) : null;
}

/** `"7m 03s"`. Negative and fractional inputs clamp rather than render junk. */
export function formatDurationLabel(totalSec: number): string {
  const t = Math.max(0, Math.floor(totalSec));
  const m = Math.floor(t / 60);
  const s = (t % 60).toString().padStart(2, '0');
  return `${m}m ${s}s`;
}
