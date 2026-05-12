// ============================================================================
// Round 3 PR-D — CPT allowlist (audit A06-P0-002)
// ----------------------------------------------------------------------------
// Closes the same False Claims Act vector the ICD-10 allowlist closes, on
// the procedure-coding side. The 07b-cpt-coding layer's validator drops
// codes not in this list and emits CODING_COACH_REJECTED_INVALID_CPT.
//
// SCOPE LIMITATION (intentional for pre-pilot)
// --------------------------------------------
// CPT codes are AMA-licensed for commercial redistribution. Shipping the
// full CPT canonical list in this repo would require an AMA agreement
// that we don't yet have at pre-pilot scale. This file is a HAND-CURATED
// top-N covering the M5 specialties (E&M, common procedures, vaccines,
// modifiers).
//
// Codes here are common-knowledge (publicly documented in CMS PFS RVU
// files, AAPC public references, MedicareNCD lookup, etc). The allowlist
// is therefore safe to ship pre-pilot without an AMA license, while
// providing the same fail-closed safety floor.
//
// PHASE 7 PATH: AMA license + swap this file for a full CPT canonical
// set OR rely on the CMS PFS RVU file (which contains the codes that
// have RVUs assigned, ~95% of E&M and procedures). Validator API stays
// the same.
// ============================================================================

const STARTER_CPT_CODES: ReadonlyArray<string> = [
  // === E&M — Office / Outpatient — established patient ===
  '99211', // Min, no/min presenting problem
  '99212', // Self-limited / minor (10 min)
  '99213', // Low-moderate (15 min)
  '99214', // Moderate (25 min)
  '99215', // High (40 min)

  // === E&M — Office / Outpatient — new patient ===
  '99202', // Straightforward (15 min)
  '99203', // Low (30 min)
  '99204', // Moderate (45 min)
  '99205', // High (60 min)

  // === E&M — Inpatient/observation — initial ===
  '99221', // Low MDM (40 min)
  '99222', // Moderate MDM (55 min)
  '99223', // High MDM (75 min)

  // === E&M — Inpatient/observation — subsequent ===
  '99231', // Low MDM (25 min)
  '99232', // Moderate MDM (35 min)
  '99233', // High MDM (50 min)

  // === E&M — ER ===
  '99281', // Minimal
  '99282', // Low
  '99283', // Moderate
  '99284', // High
  '99285', // High complexity (life/limb threat)

  // === E&M — Critical care ===
  '99291', // Critical care, first 30-74 min
  '99292', // Critical care, each additional 30 min

  // === E&M — Preventive ===
  '99381', // Preventive, new pt, infant
  '99382', // Preventive, new pt, age 1-4
  '99383', // Preventive, new pt, age 5-11
  '99384', // Preventive, new pt, age 12-17
  '99385', // Preventive, new pt, age 18-39
  '99386', // Preventive, new pt, age 40-64
  '99387', // Preventive, new pt, 65+
  '99391', // Preventive, est pt, infant
  '99392', // Preventive, est pt, age 1-4
  '99393', // Preventive, est pt, age 5-11
  '99394', // Preventive, est pt, age 12-17
  '99395', // Preventive, est pt, age 18-39
  '99396', // Preventive, est pt, age 40-64
  '99397', // Preventive, est pt, 65+

  // === Telephone / online ===
  '99441', // Telephone E&M, 5-10 min (legacy)
  '99442', // Telephone E&M, 11-20 min (legacy)
  '99443', // Telephone E&M, 21-30 min (legacy)

  // === Psychiatry / behavioral health ===
  '90791', // Psychiatric diagnostic eval (no medical services)
  '90792', // Psychiatric diagnostic eval with medical services
  '90832', // Psychotherapy 30 min
  '90834', // Psychotherapy 45 min
  '90837', // Psychotherapy 60 min
  '90846', // Family psychotherapy without patient
  '90847', // Family psychotherapy with patient
  '96127', // Brief emotional / behavioral assessment
  '96130', // Psychological testing eval, first hour
  '96131', // Psychological testing eval, each addl hour
  '96136', // Psych test admin/scoring, first 30 min
  '96137', // Psych test admin/scoring, each addl 30 min

  // === Vaccines + administration ===
  '90460', // Immunization admin first/only component, age <= 18
  '90461', // Immunization admin each addl component, age <= 18
  '90471', // Immunization admin one vaccine
  '90472', // Immunization admin each addl vaccine
  '90686', // Influenza vaccine, quadrivalent IIV4
  '90715', // Tdap vaccine
  '90734', // Meningococcal MCV4
  '90740', // Hep B vaccine

  // === Common labs / point-of-care ===
  '36415', // Routine venipuncture
  '81002', // Urinalysis dip-stick (non-auto)
  '81003', // Urinalysis dip-stick automated
  '85027', // Complete CBC, automated
  '85610', // Prothrombin time
  '99173', // Visual acuity screening
  '94010', // Spirometry
  '94060', // Bronchodilation responsiveness
  '93000', // ECG with interpretation/report
  '93005', // ECG, tracing only
  '93010', // ECG, interpretation/report only

  // === Behavioral / SDOH screening (HEDIS-aligned) ===
  '96160', // Health risk assessment instrument
  '96161', // Caregiver-focused health risk assessment

  // === Office procedures (most common in family/IM) ===
  '11042', // Debridement, subq tissue, first 20 cm²
  '11043', // Debridement, muscle/fascia, first 20 cm²
  '11055', // Paring/cutting of benign hyperkeratotic lesion (1)
  '17000', // Destruction premalignant lesion (1)
  '17110', // Destruction benign lesion (up to 14)
  '17111', // Destruction benign lesion (15+)
  '69210', // Cerumen removal, one or both ears

  // === Ortho / MSK ===
  '20550', // Injection tendon sheath/ligament
  '20551', // Injection tendon origin/insertion
  '20552', // Injection trigger point, 1-2 muscles
  '20553', // Injection trigger point, 3+ muscles
  '20600', // Arthrocentesis, small joint
  '20605', // Arthrocentesis, intermediate joint
  '20610', // Arthrocentesis, major joint

  // === Bariatric Surgery (2026-05-12) — laparoscopic + open ===
  // Captures the procedure codes a bariatric surgeon would bill on the
  // operative day. Added with the `bariatric-surgery` specialty so the
  // L7b validator accepts these instead of dropping them as "not in
  // allowlist." Open codes carried because revisional / complication
  // cases routinely convert from lap to open.
  '43644', // Laparoscopic Roux-en-Y gastric bypass (RYGB), with ≤ 150 cm Roux limb
  '43645', // Laparoscopic RYGB with small intestine reconstruction for malabsorption
  '43775', // Laparoscopic sleeve gastrectomy
  '43770', // Laparoscopic adjustable gastric band, placement
  '43771', // Adjustable gastric band, revision
  '43772', // Adjustable gastric band, removal of subcutaneous port only
  '43773', // Adjustable gastric band, removal and replacement of subcutaneous port only
  '43774', // Adjustable gastric band, removal (entire device, complete)
  '43842', // Open vertical-banded gastroplasty
  '43843', // Open gastric restrictive procedure NEC
  '43845', // Open biliopancreatic diversion with duodenal switch (BPD-DS)
  '43846', // Open Roux-en-Y gastric bypass (≤ 150 cm Roux limb)
  '43847', // Open RYGB with small intestine reconstruction for malabsorption
  '43848', // Revision, open, of bariatric bypass procedure
  '43886', // Gastric restrictive procedure, open; revision of subcutaneous port
  '43887', // Gastric restrictive procedure, open; removal of subcutaneous port
  '43888', // Gastric restrictive procedure, open; removal and replacement of subcutaneous port

  // === Modifiers (tracked separately from codes) ===
  // These are appended to a CPT code (e.g. "99213-25"). The validator
  // accepts a code with or without a trailing "-NN" modifier.
  // See isValidCpt() below — modifier suffix is stripped before lookup.
];

/** Allowlist set — strings preserved as documented (CPT codes are
 *  always five digits; some HCPCS Level II add a letter prefix like
 *  J3490 — those aren't included in this starter set). */
export const CPT_ALLOWLIST: ReadonlySet<string> = new Set(
  STARTER_CPT_CODES.map((c) => c.trim().toUpperCase())
);

/** Common AMA modifiers. Appended to codes via "-NN" suffix; stripped
 *  before allowlist lookup. The list is small + well-known so we
 *  validate them too rather than accept any "-NN". */
const VALID_MODIFIERS: ReadonlySet<string> = new Set([
  '22', // Increased procedural services
  '24', // Unrelated E&M during postop period
  '25', // Significant, separately identifiable E&M same day
  '26', // Professional component
  '27', // Multiple outpatient hospital E&Ms same day
  '32', // Mandated services
  '33', // Preventive service
  '47', // Anesthesia by surgeon
  '50', // Bilateral procedure
  '51', // Multiple procedures
  '52', // Reduced services
  '53', // Discontinued procedure
  '54', // Surgical care only
  '55', // Postop management only
  '56', // Preop management only
  '57', // Decision for surgery
  '58', // Staged/related procedure during postop period
  '59', // Distinct procedural service
  '62', // Two surgeons
  '63', // Procedure on infant <4kg
  '76', // Repeat procedure same physician
  '77', // Repeat procedure other physician
  '78', // Unplanned return to OR
  '79', // Unrelated procedure during postop period
  '95', // Synchronous telemedicine via real-time interactive audio/video
  'GT', // Telehealth (legacy; mostly replaced by 95)
  'GQ', // Asynchronous telehealth
  'XE', // Separate encounter
  'XP', // Separate practitioner
  'XS', // Separate structure
  'XU', // Unusual non-overlapping service
]);

/**
 * Validates a CPT code against the allowlist. Strips any
 * "-MM" modifier suffix before lookup, then verifies the modifier
 * (if any) is in the canonical AMA modifier set.
 *
 * Returns true iff:
 *   - Base code (5 chars, before any "-") is in CPT_ALLOWLIST, AND
 *   - If a modifier is present, it's in VALID_MODIFIERS.
 */
export function isValidCpt(code: string | null | undefined): boolean {
  if (!code) return false;
  const trimmed = code.trim().toUpperCase();
  if (trimmed.length === 0) return false;

  const dashIdx = trimmed.indexOf('-');
  const base = dashIdx === -1 ? trimmed : trimmed.slice(0, dashIdx);
  const modifier = dashIdx === -1 ? null : trimmed.slice(dashIdx + 1);

  if (!CPT_ALLOWLIST.has(base)) return false;
  if (modifier !== null && !VALID_MODIFIERS.has(modifier)) return false;
  return true;
}

/** Total size — surfaced in admin diagnostics. */
export const CPT_ALLOWLIST_SIZE = CPT_ALLOWLIST.size;
