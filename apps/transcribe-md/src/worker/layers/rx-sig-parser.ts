// ============================================================================
// Fix-Pack 1 Q0-1 — Rx sig parser (audit Finding 06.1)
// ----------------------------------------------------------------------------
// Pure function. Converts the L7c model's `strength` + `sig` strings into
// `mg/day` so `validateRxDose` can run its numeric range check. Returns
// `null` when either component is unparseable — the validator still runs
// the contraindication and complex-dosing checks against `doseMgPerDay:
// null`, just skips the numeric ceiling comparison.
//
// Scope is intentionally narrow:
//   * `strength` parses a single mg-dose ("20 mg", "0.5 mg", "500 mg").
//     Other units (mcg, g, IU, mL) → null. The Rx panel currently emits
//     mg for the drugs in the verified dose-ranges.ts table; non-mg
//     strengths fall through to RX_DRUG_NOT_IN_VERIFIED_DATABASE
//     anyway because the validator's table is mg-keyed.
//   * `sig` matches a curated list of common frequency patterns —
//     daily/QD, BID/Q12H, TID/Q8H, QID/Q6H, Q4H/Q3H/Q2H, weekly, PRN.
//     Patterns are checked most-specific first so "QID" doesn't match
//     "QD". PRN returns null on the dose side because PRN dosing is
//     intrinsically variable; the validator's complex-dosing codepath
//     surfaces it as a verify-individually warning.
//
// No PHI in this file; no I/O; no external calls. Unit-tested via
// `__tests__/rx-sig-parser.test.ts`.
// ============================================================================

/**
 * Parse the model's `strength` field into a per-dose mg amount.
 * Recognises forms like "20 mg", "500mg", "0.5 mg", "1.25 mg".
 * Returns null for non-mg units, malformed input, or empty/null.
 */
function parseStrengthMg(strength: string | null): number | null {
  if (!strength) return null;
  // Match "<number> mg" with flexible whitespace + case. Disallow other
  // units by requiring the unit token to be exactly "mg" and not part
  // of a longer word like "mcg" or "mg/mL".
  const m = strength.match(/(\d+(?:\.\d+)?)\s*mg(?![a-zA-Z/])/i);
  if (!m) return null;
  const n = Number(m[1]);
  if (!Number.isFinite(n) || n <= 0) return null;
  return n;
}

/**
 * Parse the model's `sig` field into a doses-per-day count.
 * Returns null for PRN, unrecognised, or empty/null sigs. Order
 * matters: longer/more-specific patterns match first so "QID" doesn't
 * collide with "QD".
 */
function parseSigDosesPerDay(sig: string | null): number | null {
  if (!sig) return null;
  const s = sig.toLowerCase();

  // PRN — variable dosing. Validator's complex-dosing path handles
  // this; numeric range check is skipped by returning null.
  if (/\bprn\b|as[- ]needed/.test(s)) return null;

  // Weekly — once every 7 days = ~0.143 doses/day.
  if (/\bweekly\b|once[- ]?(?:a[- ])?week|every[- ]week|q[- ]?week/.test(s)) {
    return 1 / 7;
  }

  // Q-N-hour patterns checked before "QD" / "QID" / etc to avoid
  // accidental partial matches against the alphabetic codes.
  if (/\bq[- ]?2[- ]?h\b/.test(s)) return 12;
  if (/\bq[- ]?3[- ]?h\b/.test(s)) return 8;
  if (/\bq[- ]?4[- ]?h\b/.test(s)) return 6;
  if (/\bq[- ]?6[- ]?h\b|every[- ]?6[- ]hours?/.test(s)) return 4;
  if (/\bq[- ]?8[- ]?h\b|every[- ]?8[- ]hours?/.test(s)) return 3;
  if (/\bq[- ]?12[- ]?h\b|every[- ]?12[- ]hours?/.test(s)) return 2;
  if (/\bq[- ]?24[- ]?h\b|every[- ]?24[- ]hours?/.test(s)) return 1;

  // Alphabetic frequency codes — order matters (QID before QD).
  if (/\bqid\b|four[- ]times?[- ](?:a[- ])?(?:day|daily)|4x\s?\/?\s?(?:day|daily)/.test(s)) return 4;
  if (/\btid\b|three[- ]times?[- ](?:a[- ])?(?:day|daily)|3x\s?\/?\s?(?:day|daily)/.test(s)) return 3;
  if (/\bbid\b|twice[- ](?:a[- ])?(?:day|daily)|2x\s?\/?\s?(?:day|daily)/.test(s)) return 2;
  if (
    /\bqd\b|\bqday\b|once[- ](?:a[- ])?(?:day|daily)|1x\s?\/?\s?(?:day|daily)|\bdaily\b/.test(
      s
    )
  ) {
    return 1;
  }
  // "Twice nightly"-family sigs must NOT fall through to the once-nightly
  // branch below (auditor N-4, 2026-07-02) — checked first.
  if (/(?:\btwice\b|\b2x?\b)[- ]?(?:a[- ]|per[- ]|each[- ]|every[- ])?night(?:ly)?\b/.test(s)) {
    return 2;
  }
  // Once-nightly phrasings (F-8, 2026-07-02): "simvastatin 40 mg nightly"
  // previously parsed to null, which silently skipped every numeric check.
  // Additive — parses MORE sigs, never fewer.
  if (/\bqhs\b|\bnightly\b|at[- ]bedtime|each[- ]night|every[- ]night|once[- ](?:a[- ])?night/.test(s)) {
    return 1;
  }

  return null;
}

/**
 * Convert a (strength, sig) pair into mg/day.
 * Returns null if either component is unparseable, OR if the sig is
 * PRN / variable. Caller (07c-rx-drafting) passes the result straight
 * to `validateRxDose`; null tells the validator to skip the numeric
 * range check while still running the contraindication / unknown-drug
 * paths.
 */
export function parseRxToMgPerDay(
  strength: string | null,
  sig: string | null
): number | null {
  const mgPerDose = parseStrengthMg(strength);
  if (mgPerDose === null) return null;
  const dosesPerDay = parseSigDosesPerDay(sig);
  if (dosesPerDay === null) return null;
  const mgPerDay = mgPerDose * dosesPerDay;
  if (!Number.isFinite(mgPerDay) || mgPerDay <= 0) return null;
  return mgPerDay;
}
