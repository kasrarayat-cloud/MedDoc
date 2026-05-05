// ============================================================================
// Round 3 PR-D — ICD-10-CM allowlist (audit A06-P0-002)
// ----------------------------------------------------------------------------
// Closes False Claims Act exposure: the AI codes layer (07a-icd-coding)
// previously emitted whatever code Claude picked subject only to a regex-
// shape check, so `Z99.999` (not a real code) and `Q9X.XX` (made up) would
// pass through to the doctor's billing-ready code list.
//
// SCOPE LIMITATION (intentional for pre-pilot)
// --------------------------------------------
// This is a STARTER SET — ~120 of the most-common ICD-10-CM codes covering
// pilot specialties (family medicine, internal medicine, pediatrics, OB/GYN,
// orthopedics, cardiology, psychiatry, pain management). It does NOT replace
// the full CMS list (~70 000 codes).
//
// PRE-PILOT SAFETY POSTURE: the validator drops codes NOT in this list,
// emits an audit row (CODING_COACH_REJECTED_INVALID_ICD), and surfaces the
// rejection in the UI as "AI suggested a code (XYZ) that's not on our
// verified list — removed". A code that is real but missing from the
// allowlist gets dropped (false negative) — clinically safer than letting
// hallucinated codes through (false positive on validity).
//
// PHASE 7 PATH (post-pilot): swap this file for a fs-loaded subset of
// the full CMS canonical list (icd10cm_codes_2026.txt, ~1.4 MB). Same
// validator API; the call sites don't change.
// ============================================================================

const STARTER_ICD10_CODES: ReadonlyArray<string> = [
  // === Family / internal med — most common visit reasons ===
  'I10', // Essential (primary) hypertension
  'E11.9', // Type 2 diabetes mellitus without complications
  'E11.65', // Type 2 diabetes mellitus with hyperglycemia
  'E11.22', // Type 2 diabetes mellitus with diabetic chronic kidney disease
  'E78.5', // Hyperlipidemia, unspecified
  'E78.00', // Pure hypercholesterolemia, unspecified
  'E03.9', // Hypothyroidism, unspecified
  'E66.9', // Obesity, unspecified
  'E66.01', // Morbid (severe) obesity due to excess calories
  'I25.10', // ASCVD without angina pectoris
  'I48.91', // Unspecified atrial fibrillation
  'I50.9', // Heart failure, unspecified
  'J44.9', // COPD, unspecified
  'J45.40', // Moderate persistent asthma, uncomplicated
  'J45.909', // Unspecified asthma, uncomplicated
  'K21.9', // GERD without esophagitis
  'K57.30', // Diverticulosis of large intestine without perforation/abscess
  'K58.0', // IBS with diarrhea
  'K59.00', // Constipation, unspecified
  'N39.0', // Urinary tract infection, site not specified
  'R10.9', // Unspecified abdominal pain
  'R51.9', // Headache, unspecified
  'R50.9', // Fever, unspecified
  'R05.9', // Cough, unspecified
  'R06.02', // Shortness of breath
  'R07.9', // Chest pain, unspecified
  'R42', // Dizziness and giddiness
  'R53.83', // Other fatigue
  'R63.5', // Abnormal weight gain
  'R63.4', // Abnormal weight loss
  'Z00.00', // Encounter for general adult medical exam without abnormal findings
  'Z00.01', // Encounter for general adult medical exam with abnormal findings
  'Z23', // Encounter for immunization
  'Z11.59', // Encounter for screening for other viral diseases
  'Z79.4', // Long term (current) use of insulin
  'Z79.84', // Long term (current) use of oral hypoglycemic drugs
  'Z79.890', // Other long term (current) drug therapy
  'Z87.891', // Personal history of nicotine dependence

  // === Cardiology ===
  'I20.9', // Angina pectoris, unspecified
  'I21.9', // Acute myocardial infarction, unspecified
  'I25.2', // Old myocardial infarction
  'I63.9', // Cerebral infarction, unspecified
  'I65.29', // Occlusion/stenosis of unspecified carotid artery
  'I47.1', // Supraventricular tachycardia
  'I49.9', // Cardiac arrhythmia, unspecified

  // === Pulm / acute respiratory ===
  'J18.9', // Pneumonia, unspecified organism
  'J20.9', // Acute bronchitis, unspecified
  'J03.90', // Acute tonsillitis, unspecified
  'J02.9', // Acute pharyngitis, unspecified
  'J06.9', // Acute upper respiratory infection, unspecified
  'J21.9', // Acute bronchiolitis, unspecified
  'J11.1', // Influenza w/ other respiratory manifestations, unspecified virus
  'B34.9', // Viral infection, unspecified

  // === Pediatrics ===
  'Z00.121', // Encounter for routine child health exam w/ abnormal findings
  'Z00.129', // Encounter for routine child health exam w/o abnormal findings
  'Z00.110', // Health exam for newborn under 8 days old
  'P07.30', // Preterm newborn, unspecified weeks of gestation
  'H66.90', // Otitis media, unspecified, unspecified ear
  'H66.91', // Otitis media, unspecified, right ear
  'H66.92', // Otitis media, unspecified, left ear
  'R11.10', // Vomiting, unspecified
  'R11.2', // Nausea with vomiting, unspecified
  'A09', // Infectious gastroenteritis and colitis, unspecified
  'B07.9', // Viral wart, unspecified

  // === OB/GYN ===
  'Z34.00', // Supervision of normal first pregnancy, unspecified trimester
  'Z34.80', // Supervision of other normal pregnancy, unspecified trimester
  'O09.90', // Supervision of high-risk pregnancy, unspecified trimester
  'Z32.01', // Encounter for pregnancy test, positive
  'N91.2', // Amenorrhea, unspecified
  'N92.0', // Excessive and frequent menstruation w/ regular cycle
  'N94.6', // Dysmenorrhea, unspecified
  'N95.1', // Menopausal and female climacteric states
  'O80', // Encounter for full-term uncomplicated delivery

  // === Orthopedics / MSK ===
  'M17.9', // Osteoarthritis of knee, unspecified
  'M16.9', // Osteoarthritis of hip, unspecified
  'M19.90', // Unspecified osteoarthritis, unspecified site
  'M54.5', // Low back pain (legacy — superseded by M54.50/51/59 in 2022+)
  'M54.50', // Low back pain, unspecified
  'M54.2', // Cervicalgia
  'M25.50', // Pain in unspecified joint
  'M75.100', // Unspecified rotator cuff tear or rupture, not specified as traumatic
  'S52.501A', // Unspecified fracture of right radius, initial encounter
  'S82.001A', // Unspecified fracture of right patella, initial encounter
  'S83.20XA', // Tear of unspecified meniscus, current injury, right knee, initial enc
  'M79.7', // Fibromyalgia

  // === Psychiatry / behavioral health ===
  'F32.9', // Major depressive disorder, single episode, unspecified
  'F32.A', // Depression, unspecified
  'F33.9', // Major depressive disorder, recurrent, unspecified
  'F41.1', // Generalized anxiety disorder
  'F41.9', // Anxiety disorder, unspecified
  'F43.10', // PTSD, unspecified
  'F43.23', // Adjustment disorder with mixed anxiety and depressed mood
  'F90.0', // ADHD, predominantly inattentive type
  'F90.1', // ADHD, predominantly hyperactive type
  'F90.2', // ADHD, combined type
  'F90.9', // ADHD, unspecified type
  'F31.9', // Bipolar disorder, unspecified
  'F84.0', // Autistic disorder
  'F50.81', // Binge eating disorder
  'F51.01', // Primary insomnia
  'G47.00', // Insomnia, unspecified

  // === Pain management / neurology ===
  'G89.29', // Other chronic pain
  'G89.4', // Chronic pain syndrome
  'R52', // Pain, unspecified
  'G43.909', // Migraine, unspecified, not intractable, w/o status migrainosus
  'G44.209', // Tension-type headache, unspecified, not intractable
  'M62.830', // Muscle spasm of back

  // === Skin / common derm ===
  'L70.0', // Acne vulgaris
  'L20.9', // Atopic dermatitis, unspecified
  'L23.9', // Allergic contact dermatitis, unspecified cause
  'L30.9', // Dermatitis, unspecified
  'L40.9', // Psoriasis, unspecified

  // === Common labs / screening ===
  'Z12.11', // Encounter for screening for malignant neoplasm of colon
  'Z12.31', // Encounter for screening mammogram for malignant neoplasm of breast
  'Z01.812', // Encounter for preprocedural laboratory examination
  'Z79.01', // Long term (current) use of anticoagulants

  // === Allergic / urticaria ===
  'T78.40XA', // Allergy, unspecified, initial encounter
  'L50.9', // Urticaria, unspecified
  'J30.9', // Allergic rhinitis, unspecified
];

/**
 * Allowlist set — case-insensitive lookup. Codes are stored uppercase
 * because the CMS canonical list is uppercase and Claude's outputs vary.
 */
export const ICD10_ALLOWLIST: ReadonlySet<string> = new Set(
  STARTER_ICD10_CODES.map((c) => c.trim().toUpperCase())
);

/**
 * Validates an ICD-10-CM code against the allowlist.
 * Round 3 PR-D — A06-P0-002 deterministic floor.
 *
 * Returns true if the code is in the canonical starter set, false
 * otherwise. The 07a-icd-coding layer's validator drops codes that
 * return false and emits a CODING_COACH_REJECTED_INVALID_ICD audit row.
 *
 * @param code The ICD-10-CM code to validate (e.g. "E11.9", "I10").
 *             Whitespace + case are normalized; null/undefined/empty
 *             input returns false.
 */
export function isValidIcd10(code: string | null | undefined): boolean {
  if (!code) return false;
  const trimmed = code.trim().toUpperCase();
  if (trimmed.length === 0) return false;
  return ICD10_ALLOWLIST.has(trimmed);
}

/** Total size of the starter allowlist. Surfaced in admin diagnostics. */
export const ICD10_ALLOWLIST_SIZE = ICD10_ALLOWLIST.size;
