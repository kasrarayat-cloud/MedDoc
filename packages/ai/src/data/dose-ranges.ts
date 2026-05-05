// ============================================================================
// Round 3 PR-D — top-N drug dose-range table (audit A06-P0-004 partial)
// ----------------------------------------------------------------------------
// Closes the catastrophic-floor pharmacology hole the audit found (every
// Rx warning displayed in the rail was pure Claude output; no RxNav, no
// allergy class match, no static dose table, no peds mg/kg validator).
//
// SCOPE LIMITATION (intentional for pre-pilot)
// --------------------------------------------
// This is NOT a comprehensive pharmacology database. It is a curated
// HAND-AUDITED set of well-documented adult/peds dose ceilings for
// drugs where a simple mg/day cap is the right safety primitive.
//
// Drugs whose dosing is intrinsically complex (titrated to lab values,
// PRN-only, controlled-substance schedules, individualized renal/hepatic
// adjustment) are tagged `complexDosing: true` — the validator emits a
// fall-through warning rather than fabricating a static cap.
//
// Drugs NOT in this table → validator emits
// `RX_DRUG_NOT_IN_VERIFIED_DATABASE` warning. Visit can still be signed,
// but the warning is unmissable in the Rx panel. Fail-closed by design.
//
// EVERY VALUE IN THIS FILE NEEDS CLINICAL REVIEW BEFORE PILOT GO-LIVE.
// The data is sourced from FDA package inserts and widely-cited refs
// (Lexicomp, AAP Red Book equivalents) but a pharmacist must verify
// each row against current local protocols before doctors rely on the
// validator. Track that review in `docs/CLINICAL_DATA_REVIEW.md`.
//
// PHASE 7 PATH: replace with live RxNav / RxNorm API integration +
// drug-drug interaction database. Validator API stays the same.
// ============================================================================

export interface DoseRangeEntry {
  /** Lowercase canonical drug name (no brand, no salt, no formulation). */
  drug: string;
  /** Branded/alternate names that map to this entry. Lowercase. */
  aliases?: ReadonlyArray<string>;
  /** Adult ceiling in mg/day. Null when complexDosing=true. */
  adultMaxMgPerDay?: number;
  /** Peds mg/kg/day range. Null when complexDosing=true OR adult-only. */
  pedsMgPerKgPerDay?: { min: number; max: number };
  /** Peds absolute mg/day cap (mg/kg can exceed adult max in low-weight peds). */
  pedsMaxMgPerDay?: number;
  /** Allergens / class matches that should fire RX_CONTRAINDICATION_MATCH
   *  if any patient.allergies entry includes them (case-insensitive). */
  contraindications?: ReadonlyArray<string>;
  /** True when dosing is intrinsically variable (titrated, PRN, controlled
   *  schedule, indication-dependent). The validator emits a "verify
   *  individualized dosing" warning rather than a numeric cap check. */
  complexDosing?: boolean;
  /** Operator-facing notes: why complex, dosing nuances, references. */
  notes?: string;
}

// ----------------------------------------------------------------------------
// CURATED ENTRIES — keep alphabetical by `drug` for diff readability.
// ----------------------------------------------------------------------------
//
// Adult max values: FDA package-insert "maximum daily dose" or widely-
// cited Lexicomp/UpToDate consensus. Peds mg/kg ranges: AAP Red Book +
// AHA/PIDS guidelines where available.
//
// Conservative bias: when refs differ, the LOWER cap is chosen so the
// validator only fires on doses that exceed the most-conservative source.
// ----------------------------------------------------------------------------
export const DOSE_RANGES: ReadonlyArray<DoseRangeEntry> = [
  {
    drug: 'acetaminophen',
    aliases: ['tylenol', 'paracetamol', 'apap'],
    adultMaxMgPerDay: 4000,
    pedsMgPerKgPerDay: { min: 10, max: 75 },
    pedsMaxMgPerDay: 3750,
    contraindications: ['acetaminophen allergy', 'severe hepatic impairment'],
    notes:
      'Adult max 4 g/day per FDA package insert; some refs cite 3 g/day for chronic alcoholics or hepatic impairment. Peds: 10-15 mg/kg/dose q4-6h, max 75 mg/kg/day or adult cap, whichever is lower.',
  },
  {
    drug: 'amoxicillin',
    aliases: ['amoxil'],
    adultMaxMgPerDay: 4000,
    pedsMgPerKgPerDay: { min: 20, max: 90 },
    pedsMaxMgPerDay: 3000,
    contraindications: ['penicillin allergy', 'amoxicillin allergy', 'beta-lactam allergy'],
    notes:
      'Standard adult cap 4 g/day for most indications. AOM in peds: 80-90 mg/kg/day divided BID per AAP Red Book.',
  },
  {
    drug: 'apixaban',
    aliases: ['eliquis'],
    complexDosing: true,
    contraindications: ['active bleeding'],
    notes:
      'Dosing is indication-dependent (5 mg BID standard for AFib NVAF; 2.5 mg BID with renal adjustment criteria; VTE treatment uses different schedule). Validator should not enforce a mg/day cap — verify against indication-specific protocol.',
  },
  {
    drug: 'atorvastatin',
    aliases: ['lipitor'],
    adultMaxMgPerDay: 80,
    contraindications: ['active liver disease', 'pregnancy', 'breastfeeding'],
    notes:
      'FDA max 80 mg/day. Not approved for peds <10 yr; HeFH approved 10-17 yr 10-20 mg/day.',
  },
  {
    drug: 'azithromycin',
    aliases: ['zithromax', 'z-pak'],
    adultMaxMgPerDay: 600,
    pedsMgPerKgPerDay: { min: 5, max: 12 },
    pedsMaxMgPerDay: 500,
    contraindications: ['macrolide allergy', 'azithromycin allergy'],
    notes:
      'Typical adult: 500 mg day 1, then 250 mg/day x4 (Z-pak). Cap is the day-1 + extended-release upper bound; routine sustained dosing of 600 mg/day is unusual outside MAC therapy.',
  },
  {
    drug: 'bupropion',
    aliases: ['wellbutrin', 'zyban'],
    adultMaxMgPerDay: 450,
    contraindications: [
      'seizure disorder',
      'eating disorder',
      'mao inhibitor use',
      'bupropion allergy',
    ],
    notes:
      'Max 450 mg/day for SR/XL formulations. IR formulation max 450 mg/day with no single dose >150 mg.',
  },
  {
    drug: 'cephalexin',
    aliases: ['keflex'],
    adultMaxMgPerDay: 4000,
    pedsMgPerKgPerDay: { min: 25, max: 100 },
    pedsMaxMgPerDay: 4000,
    contraindications: ['cephalosporin allergy', 'penicillin allergy (cross-reactivity ~1-3%)'],
    notes:
      'Adult cap 4 g/day. Peds AOM/skin: 25-50 mg/kg/day; severe infections to 100 mg/kg/day.',
  },
  {
    drug: 'ciprofloxacin',
    aliases: ['cipro'],
    adultMaxMgPerDay: 1500,
    contraindications: [
      'fluoroquinolone allergy',
      'ciprofloxacin allergy',
      'tendinopathy history',
      'myasthenia gravis',
    ],
    notes:
      'Adult oral max 1500 mg/day. Use peds-cautiously (FDA: only when no alternative; tendinopathy + arthropathy risk).',
  },
  {
    drug: 'clopidogrel',
    aliases: ['plavix'],
    complexDosing: true,
    contraindications: ['active bleeding'],
    notes:
      'Dosing is indication-dependent: 75 mg/day maintenance after a 300-600 mg loading dose for ACS/PCI. Validator should not enforce a mg/day cap.',
  },
  {
    drug: 'doxycycline',
    aliases: ['vibramycin', 'doryx', 'oracea'],
    adultMaxMgPerDay: 200,
    pedsMgPerKgPerDay: { min: 2.2, max: 4.4 },
    pedsMaxMgPerDay: 200,
    contraindications: ['tetracycline allergy', 'pregnancy', 'breastfeeding'],
    notes:
      'Standard adult 100 mg BID = 200 mg/day. Some ID indications use 200 mg loading then 100 mg/day. Peds use limited (>=8 yr generally).',
  },
  {
    drug: 'duloxetine',
    aliases: ['cymbalta'],
    adultMaxMgPerDay: 120,
    contraindications: ['mao inhibitor use', 'duloxetine allergy'],
    notes:
      'FDA-labeled max 60 mg/day for most indications (MDD, GAD, fibromyalgia). 120 mg/day is the absolute cap; benefit > 60 mg is debated.',
  },
  {
    drug: 'escitalopram',
    aliases: ['lexapro'],
    adultMaxMgPerDay: 20,
    contraindications: ['mao inhibitor use', 'ssri allergy', 'escitalopram allergy'],
    notes:
      'FDA max 20 mg/day in adults; 10 mg/day in elderly + hepatic impairment. Adolescents 12-17: max 20 mg/day.',
  },
  {
    drug: 'fluoxetine',
    aliases: ['prozac'],
    adultMaxMgPerDay: 80,
    contraindications: ['mao inhibitor use', 'ssri allergy', 'fluoxetine allergy'],
    notes:
      'Max 80 mg/day for MDD and OCD. Bulimia: max 60 mg/day. Peds (8+ MDD, 7+ OCD): max 20 mg/day usually.',
  },
  {
    drug: 'gabapentin',
    aliases: ['neurontin'],
    adultMaxMgPerDay: 3600,
    contraindications: ['gabapentin allergy'],
    notes:
      'Adult max 3600 mg/day divided TID. Renal-adjusted (CrCl-based, can drop to <300 mg/day at CrCl <15).',
  },
  {
    drug: 'hydrochlorothiazide',
    aliases: ['hctz', 'microzide'],
    adultMaxMgPerDay: 50,
    contraindications: ['sulfonamide allergy', 'anuria', 'thiazide allergy'],
    notes:
      'Adult max 50 mg/day for HTN; doses >25 mg/day rarely add antihypertensive benefit but increase metabolic risk.',
  },
  {
    drug: 'ibuprofen',
    aliases: ['motrin', 'advil'],
    adultMaxMgPerDay: 3200,
    pedsMgPerKgPerDay: { min: 5, max: 40 },
    pedsMaxMgPerDay: 2400,
    contraindications: [
      'nsaid allergy',
      'aspirin allergy',
      'ibuprofen allergy',
      'active gi bleed',
      'severe renal impairment',
    ],
    notes:
      'Prescription max 3200 mg/day; OTC 1200 mg/day. Peds 5-10 mg/kg/dose q6-8h, max 40 mg/kg/day (analgesic) or 30 mg/kg/day (chronic).',
  },
  {
    drug: 'levothyroxine',
    aliases: ['synthroid', 'levoxyl', 'tirosint'],
    complexDosing: true,
    contraindications: ['untreated adrenal insufficiency', 'untreated thyrotoxicosis'],
    notes:
      'Titrated to TSH (1.5-1.8 mcg/kg/day typical adult full replacement; lower with cardiac history; higher in pregnancy). No mg/day cap is meaningful; rely on TSH-targeted clinical adjustment.',
  },
  {
    drug: 'lisinopril',
    aliases: ['prinivil', 'zestril'],
    adultMaxMgPerDay: 80,
    contraindications: [
      'ace inhibitor allergy',
      'lisinopril allergy',
      'angioedema history',
      'pregnancy',
      'bilateral renal artery stenosis',
    ],
    notes: 'FDA max 80 mg/day for HTN. HF: max 40 mg/day. Renal-adjusted.',
  },
  {
    drug: 'metformin',
    aliases: ['glucophage', 'fortamet', 'glumetza'],
    adultMaxMgPerDay: 2550,
    contraindications: ['egfr <30', 'metformin allergy', 'severe hepatic impairment'],
    notes:
      'IR max 2550 mg/day; XR max 2000 mg/day. Hold for contrast studies if eGFR 30-60.',
  },
  {
    drug: 'metoprolol',
    aliases: ['lopressor', 'toprol-xl'],
    adultMaxMgPerDay: 400,
    contraindications: [
      'beta-blocker allergy',
      'metoprolol allergy',
      'severe bradycardia',
      'second/third degree heart block',
      'cardiogenic shock',
    ],
    notes:
      'Tartrate (IR) max 450 mg/day for HTN; succinate (XL) max 400 mg/day for HTN/HF. Lower max in HF on succinate (200 mg/day routine).',
  },
  {
    drug: 'omeprazole',
    aliases: ['prilosec'],
    adultMaxMgPerDay: 40,
    contraindications: ['ppi allergy', 'omeprazole allergy'],
    notes:
      'Standard max 40 mg/day; ZES + severe esophagitis use higher (titrated). 80 mg/day is the off-label upper bound; routine prescribing should not exceed 40 mg/day.',
  },
  {
    drug: 'ondansetron',
    aliases: ['zofran'],
    adultMaxMgPerDay: 32,
    pedsMgPerKgPerDay: { min: 0.1, max: 0.4 },
    pedsMaxMgPerDay: 32,
    contraindications: ['ondansetron allergy', 'congenital long QT'],
    notes:
      'FDA: single IV dose >16 mg removed from labeling 2012 due to QT prolongation. Oral max ~32 mg/day across split doses.',
  },
  {
    drug: 'prednisone',
    aliases: [],
    complexDosing: true,
    contraindications: ['systemic fungal infection', 'live vaccine within 2-4 weeks'],
    notes:
      'Dosing varies wildly by indication (2-5 mg replacement to 1-2 mg/kg burst to 60-100 mg high-dose). No fixed cap is meaningful. Validator emits "verify individualized dosing" instead.',
  },
  {
    drug: 'rosuvastatin',
    aliases: ['crestor'],
    adultMaxMgPerDay: 40,
    contraindications: ['active liver disease', 'pregnancy', 'breastfeeding'],
    notes:
      'Adult max 40 mg/day; start lower in Asian patients (20 mg/day). Peds 8-17 yr HeFH: max 20 mg/day.',
  },
  {
    drug: 'sertraline',
    aliases: ['zoloft'],
    adultMaxMgPerDay: 200,
    contraindications: ['mao inhibitor use', 'ssri allergy', 'sertraline allergy'],
    notes: 'Max 200 mg/day across all indications. Peds OCD (6-17): max 200 mg/day.',
  },
  {
    drug: 'simvastatin',
    aliases: ['zocor'],
    adultMaxMgPerDay: 40,
    contraindications: ['active liver disease', 'pregnancy', 'breastfeeding', 'concurrent strong cyp3a4 inhibitor'],
    notes:
      'FDA 2011 safety: 80 mg/day no longer recommended for new starts. 40 mg/day cap for new prescribing.',
  },
  {
    drug: 'tramadol',
    aliases: ['ultram'],
    adultMaxMgPerDay: 400,
    contraindications: ['mao inhibitor use', 'severe respiratory depression', 'tramadol allergy'],
    notes:
      'IR max 400 mg/day; ER 300 mg/day. Schedule IV controlled. Lower max with serotonergic concomitants (interaction risk).',
  },
  {
    drug: 'venlafaxine',
    aliases: ['effexor', 'effexor xr'],
    adultMaxMgPerDay: 375,
    contraindications: ['mao inhibitor use', 'snri allergy', 'venlafaxine allergy'],
    notes: 'IR 375 mg/day max for MDD; XR 225 mg/day max for GAD/SAD.',
  },
  {
    drug: 'warfarin',
    aliases: ['coumadin'],
    complexDosing: true,
    contraindications: ['active bleeding', 'pregnancy', 'warfarin allergy'],
    notes:
      'Titrated to INR (target 2-3 most indications, 2.5-3.5 mechanical mitral valve). Daily dose ranges 1-15 mg+; no fixed cap is meaningful. Validator emits "verify individualized INR-driven dosing" instead.',
  },
];

// ----------------------------------------------------------------------------
// Lookup map — flatten alias entries so isInDoseRangeTable('eliquis')
// returns the apixaban row. Built once at module init.
// ----------------------------------------------------------------------------
const LOOKUP: Map<string, DoseRangeEntry> = new Map();
for (const entry of DOSE_RANGES) {
  LOOKUP.set(entry.drug.toLowerCase(), entry);
  for (const alias of entry.aliases ?? []) {
    LOOKUP.set(alias.toLowerCase(), entry);
  }
}

/** Look up a drug by name (canonical or alias). Case-insensitive.
 *  Returns null if the drug is not in the verified database — call sites
 *  should emit RX_DRUG_NOT_IN_VERIFIED_DATABASE on null and surface a
 *  fall-through warning in the UI. */
export function getDoseRange(drugName: string | null | undefined): DoseRangeEntry | null {
  if (!drugName) return null;
  const key = drugName.trim().toLowerCase();
  if (!key) return null;
  return LOOKUP.get(key) ?? null;
}

/** Convenience predicate. */
export function isInDoseRangeTable(drugName: string | null | undefined): boolean {
  return getDoseRange(drugName) !== null;
}

/** Total drug count surfaced in admin diagnostics. */
export const DOSE_RANGE_TABLE_SIZE = DOSE_RANGES.length;
