// ============================================================================
// Specialty key normalization (2026-05-13 — Issues #202 + #206 fix-pack)
// ----------------------------------------------------------------------------
// Production audit found 17 distinct values in `transcribe_visits.specialty`
// with case + separator drift (`Orthopedics` vs `orthopedics`,
// `family_medicine` vs `Primary Care / Family Medicine`, etc.). Before the
// per-specialty keyterm dispatch can work, the free-text column needs a
// canonical-key mapping.
//
// This module is THE single normalization point. It's intentionally lenient
// — unknown values map to `unspecified` rather than throwing, because
// keyterm bias is a quality optimization, not a safety gate. A visit with
// an unrecognized specialty still transcribes, just without the
// specialty-specific term boost.
// ============================================================================

/** Canonical specialty keys. Match the per-specialty bundle keys in
 *  `deepgram-vocabulary.ts`. Adding a new specialty: also add a bundle
 *  there, and update `SPECIALTY_VARIANTS` below. */
export const SPECIALTY_KEYS = [
  'bariatric_surgery',
  'weight_management',
  'primary_care',
  'cardiology',
  'orthopedics',
  'dermatology',
  'ob_gyn',
  'urgent_care',
  'pain_management',
  'pediatrics',
  'vascular_surgery',
  'gastroenterology',
  'endocrinology',
  'functional_medicine',
  'psychiatry',
  'unspecified',
] as const;

export type SpecialtyKey = (typeof SPECIALTY_KEYS)[number];

/** Variant strings observed in production → canonical key. Add
 *  defensively — the column is free-text and new variants land
 *  occasionally. */
export const SPECIALTY_VARIANTS: Record<string, SpecialtyKey> = {
  // Bariatric surgery
  'bariatric-surgery': 'bariatric_surgery',
  'bariatric_surgery': 'bariatric_surgery',
  'bariatrics': 'bariatric_surgery',
  'bariatric surgery': 'bariatric_surgery',

  // Weight management
  'weight-management': 'weight_management',
  'weight_management': 'weight_management',
  'weight management': 'weight_management',
  'medical-weight-loss': 'weight_management',
  'metabolic-medicine': 'weight_management',

  // Primary care / family med / internal med — collapsed to a single
  // bundle. They share ~95% of relevant vocabulary.
  // Includes legacy short-ids `primary` from
  // packages/shared/src/specialties.ts:LEGACY_TO_ID
  'primary-care': 'primary_care',
  'primary_care': 'primary_care',
  'primary care': 'primary_care',
  'family-medicine': 'primary_care',
  'family_medicine': 'primary_care',
  'family medicine': 'primary_care',
  'family practice': 'primary_care',
  'internal-medicine': 'primary_care',
  'internal_medicine': 'primary_care',
  'internal medicine': 'primary_care',
  'general-practice': 'primary_care',
  'primary care / family medicine': 'primary_care',
  'primary': 'primary_care',

  // Cardiology
  'cardiology': 'cardiology',
  'cardiologist': 'cardiology',
  'cardiovascular': 'cardiology',

  // Orthopedics
  'orthopedics': 'orthopedics',
  'orthopaedics': 'orthopedics',
  'ortho': 'orthopedics',
  'orthopedic-surgery': 'orthopedics',
  'orthopedic_surgery': 'orthopedics',
  'sports-medicine': 'orthopedics',
  'sports_medicine': 'orthopedics',

  // Dermatology
  'dermatology': 'dermatology',
  'dermatologist': 'dermatology',
  'derm': 'dermatology',

  // OB-GYN — includes legacy display names from
  // `packages/shared/src/specialties.ts:LEGACY_TO_ID`
  'ob-gyn': 'ob_gyn',
  'ob_gyn': 'ob_gyn',
  'obgyn': 'ob_gyn',
  'ob/gyn': 'ob_gyn',
  'obstetrics': 'ob_gyn',
  'gynecology': 'ob_gyn',
  'obstetrics and gynecology': 'ob_gyn',
  'obstetrics & gynecology': 'ob_gyn',
  'obstetrics-gynecology': 'ob_gyn',
  'womens-health': 'ob_gyn',

  // Urgent care
  'urgent-care': 'urgent_care',
  'urgent_care': 'urgent_care',
  'urgent care': 'urgent_care',
  'walk-in': 'urgent_care',

  // Pain management — `pain` is the legacy short-id from
  // packages/shared/src/specialties.ts:LEGACY_TO_ID
  'pain-management': 'pain_management',
  'pain_management': 'pain_management',
  'pain management': 'pain_management',
  'pain-medicine': 'pain_management',
  'pain': 'pain_management',

  // Pediatrics
  'pediatrics': 'pediatrics',
  'pediatric': 'pediatrics',
  'peds': 'pediatrics',

  // Vascular surgery
  'vascular-surgery': 'vascular_surgery',
  'vascular_surgery': 'vascular_surgery',
  'vascular surgery': 'vascular_surgery',
  'vascular': 'vascular_surgery',

  // Endocrinology — separate from weight_management because the
  // vocabulary is broader (thyroid, adrenal, pituitary).
  'endocrinology': 'endocrinology',
  'endocrinologist': 'endocrinology',
  'endo': 'endocrinology',

  // Functional medicine — Charm Health's target segment per the
  // 2026-05-13 EHR roadmap. Supplements + GI-MAP / DUTCH terms.
  'functional-medicine': 'functional_medicine',
  'functional_medicine': 'functional_medicine',
  'functional medicine': 'functional_medicine',
  'integrative-medicine': 'functional_medicine',
  'integrative_medicine': 'functional_medicine',
  'integrative medicine': 'functional_medicine',

  // Gastroenterology — added 2026-08-14 with the GI catalog row. Without
  // this bridge normalizeSpecialty('gastroenterology') returns
  // 'unspecified', whose bundle EXISTS and is EMPTY — so the miss is
  // silent: a real key, a real lookup, zero terms, no error.
  'gastroenterology': 'gastroenterology',
  'gastroenterologist': 'gastroenterology',
  'gastro': 'gastroenterology',
  'gi': 'gastroenterology',
  'digestive-health': 'gastroenterology',
  'digestive_health': 'gastroenterology',
  'digestive health': 'gastroenterology',

  // Psychiatry — antidepressant + antipsychotic confused-name density
  // (the Celexa/Celebrex/Cerebyx/Zyprexa cluster from ISMP).
  'psychiatry': 'psychiatry',
  'psychiatrist': 'psychiatry',
  'psych': 'psychiatry',
  'mental-health': 'psychiatry',
  'mental_health': 'psychiatry',
  'behavioral-health': 'psychiatry',
};

/** Normalize an arbitrary specialty string to a canonical key.
 *  Unrecognized values return 'unspecified' rather than throwing —
 *  keyterm bias is a quality optimization, not a safety gate. */
export function normalizeSpecialty(
  raw: string | null | undefined,
): SpecialtyKey {
  if (!raw) return 'unspecified';
  const k = raw.trim().toLowerCase();
  return SPECIALTY_VARIANTS[k] ?? 'unspecified';
}
