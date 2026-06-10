// ============================================================================
// Round 3 PR-D — Rx dose-range validator (audit A06-P0-004)
// ----------------------------------------------------------------------------
// Pure function. Takes a single Rx draft (drug + dose + patient context)
// and returns a list of warnings. The 07c-rx-drafting layer (or a future
// validator pass) emits the corresponding audit rows + surfaces warnings
// in the visit Rx panel.
//
// Warning taxonomy (each maps to a Round 3 PR-D AuditAction):
//   RX_DOSE_EXCEEDS_VERIFIED_RANGE   — dose > adultMax / pedsMax
//   RX_CONTRAINDICATION_MATCH        — patient.allergies hits a contraindication
//   RX_DRUG_NOT_IN_VERIFIED_DATABASE — drug not in dose-ranges.ts
//   complex_dosing_verify_individually  — drug present but complexDosing=true
//
// FAIL-CLOSED SEMANTICS: a drug that's NOT in the table emits the
// `RX_DRUG_NOT_IN_VERIFIED_DATABASE` warning — visit can still be signed,
// but the warning is unmissable in the Rx panel. We never "silently pass"
// a drug just because it's outside our verified set.
// ============================================================================

import { getDoseRange, type DoseRangeEntry } from './dose-ranges';

export type RxValidationWarningCode =
  | 'RX_DOSE_EXCEEDS_VERIFIED_RANGE'
  | 'RX_CONTRAINDICATION_MATCH'
  | 'RX_DRUG_NOT_IN_VERIFIED_DATABASE'
  | 'RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY';

export interface RxValidationWarning {
  code: RxValidationWarningCode;
  /** Doctor-facing message. Surfaced verbatim in the Rx panel. */
  message: string;
  /** Audit metadata field-NAMES (no PHI values). */
  metadata: Record<string, string | number | boolean | null | undefined>;
}

export interface RxValidationInput {
  /** Drug name as Claude emitted it. Brand or generic. */
  drug: string;
  /** Daily dose in mg. Caller must convert from mg/dose × frequency. */
  doseMgPerDay: number | null;
  /** Patient context for peds vs adult + allergy match. */
  patient: {
    /** ISO date or null. Validator converts to age in years. */
    dateOfBirth: string | Date | null;
    /** Kilograms. Required for peds mg/kg cap check. */
    weightKg: number | null;
    /** Free-text allergies. Matched against each contraindication needle by
     *  full-needle substring OR (for "<substance> allergy" needles) the bare
     *  substance as a whole word. See allergyMatchesContraindication. */
    allergies: ReadonlyArray<string>;
  };
}

export interface RxValidationResult {
  drug: string;
  /** True when validator could complete a numeric check. False when
   *  drug is missing/unknown OR complex-dosing OR dose unparseable. */
  validated: boolean;
  warnings: RxValidationWarning[];
}

const PEDS_AGE_THRESHOLD_YEARS = 18;

/**
 * Compute age in completed years from a DOB. Returns null if DOB is
 * missing/invalid. The validator falls back to treating the patient as
 * adult-with-unknown-age when null — peds-cap-only checks are skipped.
 */
function computeAgeYears(dob: string | Date | null): number | null {
  if (!dob) return null;
  const d = dob instanceof Date ? dob : new Date(dob);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age--;
  return age;
}

/** Escape a string for safe literal use inside a RegExp. */
function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Derive the bare substance from an `"<substance> allergy[…]"` contraindication
 * needle by stripping the ` allergy` token and everything after it.
 *
 *   "penicillin allergy"                     → "penicillin"
 *   "penicillin allergy (cross-reactivity …)" → "penicillin"
 *   "ace inhibitor allergy"                  → "ace inhibitor"
 *   "iodine contrast allergy"                → "iodine contrast"
 *   "glp-1 allergy"                          → "glp-1"
 *
 * Returns null for needles that are NOT substance-allergy patterns (clinical
 * states/conditions like "active bleeding", "men-2", "egfr <30") — those keep
 * their existing full-string substring semantics.
 */
function deriveAllergySubstance(needleLower: string): string | null {
  const m = needleLower.match(/^(.+?)\s+allergy\b/);
  if (!m) return null;
  const substance = m[1].trim();
  return substance.length > 0 ? substance : null;
}

/**
 * Does any patient allergy string match this contraindication needle?
 *
 * Two complementary, purely ADDITIVE rules (either fires the warning):
 *
 *  1) Full-needle substring (legacy behaviour, preserved) — covers the
 *     clinical-state needles ("active bleeding", "pregnancy") and exact
 *     chart phrasings. No regression: this is the original matcher.
 *
 *  2) Substance word-match (the N-2 fix) — for "<substance> allergy" needles
 *     we derive the bare substance and match it as a whole word (plural
 *     tolerated) anywhere in the patient string. This makes the deterministic
 *     backstop fire on the natural phrasings L3 actually extracts and that
 *     charts actually carry: bare "penicillin", "Penicillin (childhood rash)",
 *     "penicillins", "allergic to penicillin — hives".
 *
 * Word-boundary anchoring is what keeps (2) from over-firing: substance "iron"
 * matches "iron" / "irons" / "iron-dextran" but NOT "environmental". We err
 * toward WARNING (a false positive is doctor-reviewable through the override
 * gate; a false negative is the danger), but never so loosely that a substring
 * collision invents an allergy that isn't written.
 *
 * Cross-reactivity classes (penicillin↔cephalosporin, sulfa↔sulfonamide) are
 * intentionally OUT of scope here — those live in the curated needle lists
 * (e.g. amoxicillin already lists "beta-lactam allergy"), not in the matcher.
 */
function allergyMatchesContraindication(
  patientAllergies: ReadonlyArray<string>,
  contraindication: string
): boolean {
  const needle = contraindication.toLowerCase();
  const substance = deriveAllergySubstance(needle);
  const substanceRe = substance
    ? new RegExp('\\b' + escapeRegExp(substance) + '(?:s|es)?\\b', 'i')
    : null;

  return patientAllergies.some((a) => {
    const allergy = a.toLowerCase();
    if (allergy.includes(needle)) return true; // rule 1 — legacy/full-needle
    if (substanceRe && substanceRe.test(allergy)) return true; // rule 2 — N-2 fix
    return false;
  });
}

/**
 * Run the deterministic dose + allergy check on a single Rx draft.
 * Pure — no side effects. Caller integrates results into 07c output
 * and emits audit rows.
 */
export function validateRxDose(input: RxValidationInput): RxValidationResult {
  const drugLower = input.drug.trim().toLowerCase();
  const entry: DoseRangeEntry | null = getDoseRange(drugLower);

  // 1) Drug not in table → fall-through warning. Never silent.
  if (!entry) {
    return {
      drug: input.drug,
      validated: false,
      warnings: [
        {
          code: 'RX_DRUG_NOT_IN_VERIFIED_DATABASE',
          message: `Verify dosing — "${input.drug}" is not in our verified safety database. The AI's recommendation has not been cross-checked against a deterministic dose range.`,
          metadata: { drug: drugLower },
        },
      ],
    };
  }

  // 2) Allergy class match — runs even when dose is unparseable.
  const warnings: RxValidationWarning[] = [];
  for (const ci of entry.contraindications ?? []) {
    if (allergyMatchesContraindication(input.patient.allergies, ci)) {
      warnings.push({
        code: 'RX_CONTRAINDICATION_MATCH',
        message: `Allergy/contraindication match: patient is allergic to "${ci}" — ${entry.drug} should be avoided.`,
        metadata: {
          drug: entry.drug,
          contraindication: ci,
        },
      });
    }
  }

  // 3) Complex dosing → don't try to enforce a numeric cap.
  if (entry.complexDosing) {
    warnings.push({
      code: 'RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY',
      message: `${entry.drug} dosing is intrinsically variable (titrated to lab values, indication-dependent, or controlled-substance-scheduled). Verify against individualized protocol.${entry.notes ? ' ' + entry.notes : ''}`,
      metadata: { drug: entry.drug },
    });
    return { drug: input.drug, validated: false, warnings };
  }

  // 4) Numeric dose check — adult vs peds split.
  if (input.doseMgPerDay !== null && Number.isFinite(input.doseMgPerDay)) {
    const ageYears = computeAgeYears(input.patient.dateOfBirth);
    const isPeds = ageYears !== null && ageYears < PEDS_AGE_THRESHOLD_YEARS;

    if (
      isPeds &&
      input.patient.weightKg !== null &&
      Number.isFinite(input.patient.weightKg) &&
      input.patient.weightKg > 0 &&
      entry.pedsMgPerKgPerDay
    ) {
      const mgPerKg = input.doseMgPerDay / input.patient.weightKg;
      if (mgPerKg > entry.pedsMgPerKgPerDay.max) {
        warnings.push({
          code: 'RX_DOSE_EXCEEDS_VERIFIED_RANGE',
          message: `Dose ${input.doseMgPerDay} mg/day = ${mgPerKg.toFixed(1)} mg/kg/day for a ${input.patient.weightKg} kg pediatric patient (age ${ageYears}). Exceeds verified peds max of ${entry.pedsMgPerKgPerDay.max} mg/kg/day for ${entry.drug}.`,
          metadata: {
            drug: entry.drug,
            doseMgPerDay: input.doseMgPerDay,
            mgPerKg: Number(mgPerKg.toFixed(2)),
            pedsMaxMgPerKg: entry.pedsMgPerKgPerDay.max,
            ageYears,
            weightKg: input.patient.weightKg,
          },
        });
      }
      if (
        entry.pedsMaxMgPerDay !== undefined &&
        input.doseMgPerDay > entry.pedsMaxMgPerDay
      ) {
        warnings.push({
          code: 'RX_DOSE_EXCEEDS_VERIFIED_RANGE',
          message: `Dose ${input.doseMgPerDay} mg/day exceeds verified peds absolute cap of ${entry.pedsMaxMgPerDay} mg/day for ${entry.drug}.`,
          metadata: {
            drug: entry.drug,
            doseMgPerDay: input.doseMgPerDay,
            pedsMaxMgPerDay: entry.pedsMaxMgPerDay,
          },
        });
      }
    } else if (
      entry.adultMaxMgPerDay !== undefined &&
      input.doseMgPerDay > entry.adultMaxMgPerDay
    ) {
      warnings.push({
        code: 'RX_DOSE_EXCEEDS_VERIFIED_RANGE',
        message: `Dose ${input.doseMgPerDay} mg/day exceeds verified adult max of ${entry.adultMaxMgPerDay} mg/day for ${entry.drug}.`,
        metadata: {
          drug: entry.drug,
          doseMgPerDay: input.doseMgPerDay,
          adultMaxMgPerDay: entry.adultMaxMgPerDay,
        },
      });
    }
  }

  return {
    drug: input.drug,
    validated: true,
    warnings,
  };
}
