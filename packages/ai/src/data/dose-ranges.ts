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

  // ── Weight-management pharmacotherapy ──────────────────────────────
  // Added with the `weight-management` specialty. GLP-1 / GIP agonists
  // (liraglutide, semaglutide, tirzepatide) use stepwise titration over
  // weeks → `complexDosing: true` rather than a static cap; the
  // validator will emit "verify individualized titration plan" and the
  // L7c prompt is responsible for documenting the step. Phentermine
  // and the phentermine-topiramate combo carry concrete adult maxes
  // and a cardiovascular-history contraindication. Naltrexone-
  // bupropion (Contrave) has its own combined-dose ceiling (16/180
  // mg/day for naltrexone/bupropion). Orlistat is OTC at 60 mg TID
  // (Alli) and Rx at 120 mg TID (Xenical). Setmelanotide is rare-
  // disease (Imcivree) for genetically-confirmed obesity — titrated
  // SC, complexDosing.
  {
    drug: 'liraglutide',
    aliases: ['saxenda', 'victoza'],
    complexDosing: true,
    contraindications: [
      'liraglutide allergy',
      'glp-1 allergy',
      'personal history of medullary thyroid carcinoma',
      'family history of medullary thyroid carcinoma',
      'multiple endocrine neoplasia type 2',
      'men-2',
      'pregnancy',
    ],
    notes:
      'Weight management (Saxenda): titrate weekly 0.6 → 1.2 → 1.8 → 2.4 → 3.0 mg SC daily. Diabetes (Victoza): 0.6 → 1.2 → 1.8 mg SC daily. No mg/day cap is meaningful without the titration step; validator emits "verify individualized titration plan". Boxed warning: thyroid C-cell tumors (animal data). Watch: pancreatitis, gallbladder disease, severe gastroparesis.',
  },
  {
    drug: 'naltrexone-bupropion',
    aliases: ['contrave'],
    adultMaxMgPerDay: 32,
    contraindications: [
      'uncontrolled hypertension',
      'seizure disorder',
      'bulimia',
      'anorexia nervosa',
      'chronic opioid use',
      'opioid dependence',
      'mao inhibitor use',
      'naltrexone allergy',
      'bupropion allergy',
      'pregnancy',
    ],
    notes:
      'Fixed-combination tablet (8 mg naltrexone / 90 mg bupropion). Max 4 tabs/day (32 mg naltrexone + 360 mg bupropion). Titrate: week 1 = 1 tab AM; week 2 = 1 AM + 1 PM; week 3 = 2 AM + 1 PM; week 4+ = 2 AM + 2 PM. Boxed warning: bupropion suicidality in young adults.',
  },
  {
    drug: 'orlistat',
    aliases: ['xenical', 'alli'],
    adultMaxMgPerDay: 360,
    contraindications: [
      'orlistat allergy',
      'chronic malabsorption syndrome',
      'cholestasis',
      'pregnancy',
    ],
    notes:
      'Rx (Xenical) 120 mg TID with each fat-containing meal — max 360 mg/day. OTC (Alli) 60 mg TID — max 180 mg/day. Take a daily multivitamin (fat-soluble vitamin malabsorption). Rare hepatotoxicity reports.',
  },
  {
    drug: 'phentermine',
    aliases: ['adipex-p', 'lomaira', 'suprenza'],
    adultMaxMgPerDay: 37.5,
    contraindications: [
      'phentermine allergy',
      'sympathomimetic allergy',
      'cardiovascular disease',
      'coronary artery disease',
      'uncontrolled hypertension',
      'hyperthyroidism',
      'glaucoma',
      'history of drug abuse',
      'mao inhibitor use',
      'pregnancy',
      'breastfeeding',
    ],
    notes:
      'Adult max 37.5 mg/day (single dose) or 8 mg TID (Lomaira). Schedule IV controlled. Short-term use (weeks, not months) per FDA label; some clinicians extend off-label under monitoring. Screen cardiac history + baseline HR/BP before initiating.',
  },
  {
    drug: 'phentermine-topiramate',
    aliases: ['qsymia'],
    adultMaxMgPerDay: 15,
    contraindications: [
      'phentermine allergy',
      'topiramate allergy',
      'sulfonamide allergy',
      'glaucoma',
      'hyperthyroidism',
      'mao inhibitor use',
      'pregnancy',
      'breastfeeding',
      'history of nephrolithiasis',
    ],
    notes:
      'Fixed-combination ER. Max 15 mg phentermine / 92 mg topiramate daily. Titrate: 3.75/23 mg × 14 days → 7.5/46 mg (maintenance for most) → escalate to 11.25/69 mg × 14 days → 15/92 mg only if <3% weight loss at 12 weeks. Discontinue gradually (topiramate withdrawal). Cleft-palate teratogenicity → REMS, pregnancy screen monthly.',
  },
  {
    drug: 'semaglutide',
    aliases: ['wegovy', 'ozempic', 'rybelsus'],
    complexDosing: true,
    contraindications: [
      'semaglutide allergy',
      'glp-1 allergy',
      'personal history of medullary thyroid carcinoma',
      'family history of medullary thyroid carcinoma',
      'multiple endocrine neoplasia type 2',
      'men-2',
      'pregnancy',
    ],
    notes:
      'Weight management (Wegovy): titrate monthly 0.25 → 0.5 → 1.0 → 1.7 → 2.4 mg SC weekly. Diabetes (Ozempic): titrate 0.25 → 0.5 → 1.0 → 2.0 mg SC weekly. Oral (Rybelsus): 3 → 7 → 14 mg PO daily. No mg/week cap is meaningful without the titration step; validator emits "verify individualized titration plan". Boxed warning: thyroid C-cell tumors. Watch: pancreatitis, severe gastroparesis, gallbladder disease, diabetic retinopathy progression in T2DM.',
  },
  {
    drug: 'setmelanotide',
    aliases: ['imcivree'],
    complexDosing: true,
    contraindications: [
      'setmelanotide allergy',
      'pregnancy',
      'breastfeeding',
    ],
    notes:
      'MC4R agonist for genetically-confirmed obesity (POMC, PCSK1, LEPR deficiency or Bardet-Biedl syndrome). Adult: titrate 2 mg → 3 mg SC daily (max). Peds 6-11 yr: 1 mg → 2 mg → 3 mg. Requires genetic-test confirmation prior to initiation. Watch: skin hyperpigmentation, depressed mood / suicidal ideation, spontaneous penile erections.',
  },
  {
    drug: 'tirzepatide',
    aliases: ['zepbound', 'mounjaro'],
    complexDosing: true,
    contraindications: [
      'tirzepatide allergy',
      'glp-1 allergy',
      'gip allergy',
      'personal history of medullary thyroid carcinoma',
      'family history of medullary thyroid carcinoma',
      'multiple endocrine neoplasia type 2',
      'men-2',
      'pregnancy',
    ],
    notes:
      'Dual GIP / GLP-1 agonist. Both weight management (Zepbound) and diabetes (Mounjaro) titrate monthly 2.5 → 5 → 7.5 → 10 → 12.5 → 15 mg SC weekly (max 15 mg). No mg/week cap is meaningful without the titration step; validator emits "verify individualized titration plan". Boxed warning: thyroid C-cell tumors. Watch: pancreatitis, severe gastroparesis, gallbladder disease.',
  },

  // ── Bariatric Surgery supplementation + post-op prophylaxis ─────────
  // Added with the `bariatric-surgery` specialty. Most of these are
  // OTC vitamins / minerals with no FDA-published mg/day cap; the
  // clinical risk is UNDER-supplementation (chronic deficiency
  // post-malabsorption). The validator emits "verify individualized
  // post-op regimen" so the Rx rail surfaces the drug rather than
  // staying silent. The calcium-citrate vs carbonate distinction is
  // load-bearing for bypass patients — they lose the acidic gastric
  // environment that dissolves carbonate, so citrate is non-
  // substitutable; this is captured as a separate entry with the
  // explicit notes so the Rx rail emits the warning if a clinician
  // drafts "calcium carbonate" for a post-bypass patient.
  {
    drug: 'cholecalciferol',
    aliases: ['vitamin d3', 'vitamin d', 'd3', 'calciferol'],
    complexDosing: true,
    contraindications: ['hypercalcemia', 'cholecalciferol allergy'],
    notes:
      'Post-bariatric typical: 3000–6000 IU PO daily (some practices use 50,000 IU PO weekly for first 8 weeks then maintenance). Target 25-OH vitamin D > 30 ng/mL; > 50 ng/mL preferred per bariatric guidelines. Monitor levels every 3-6 months in first year post-op then annually.',
  },
  {
    drug: 'cyanocobalamin',
    aliases: ['vitamin b12', 'b12', 'methylcobalamin', 'hydroxocobalamin'],
    complexDosing: true,
    contraindications: ['cobalt allergy', 'cyanocobalamin allergy'],
    notes:
      'Post-bariatric typical: 350-500 mcg PO daily sublingual / nasal OR 1000 mcg IM monthly. Oral non-sublingual is unreliable post-bypass (loss of intrinsic factor binding site). Monitor levels every 3-6 months in first year post-op then annually. Deficiency causes irreversible peripheral neuropathy + cognitive symptoms if missed.',
  },
  {
    drug: 'calcium citrate',
    aliases: ['citracal', 'calcium-citrate'],
    complexDosing: true,
    contraindications: ['hypercalcemia', 'severe renal impairment'],
    notes:
      'Post-bariatric BYPASS patients: 1200–1500 mg elemental calcium daily, split into ≤ 500 mg doses, taken AS CITRATE (NOT carbonate — bypass eliminates the acidic gastric environment that dissolves carbonate; carbonate is functionally unabsorbed in these patients). Split doses to avoid saturating absorption. Spacing 2+ hr from iron + thyroid replacement required. Post-sleeve patients retain acidity; citrate preferred but carbonate is acceptable.',
  },
  {
    drug: 'calcium carbonate',
    aliases: ['tums', 'os-cal', 'caltrate'],
    adultMaxMgPerDay: 2500,
    contraindications: ['hypercalcemia', 'post-roux-en-y gastric bypass', 'post-duodenal switch', 'post-bpd-ds'],
    notes:
      'POST-BYPASS HARD SAFETY BULLET: calcium carbonate is unabsorbed in post-RYGB / post-BPD-DS patients because the acidic gastric environment that dissolves it is absent. Use calcium CITRATE instead. Validator emits a hard warning if a Rx draft pairs "calcium carbonate" with a documented bypass procedure or Z98.84 status code. Max 2500 mg/day elemental Ca for non-bypass adults.',
  },
  {
    drug: 'ferrous sulfate',
    aliases: ['feosol', 'iron sulfate', 'iron(ii) sulfate'],
    adultMaxMgPerDay: 325,
    contraindications: ['iron overload', 'hemochromatosis', 'iron allergy'],
    notes:
      'Post-bariatric typical: 325 mg ferrous sulfate (65 mg elemental iron) PO daily to BID. Take with vitamin C and AWAY from calcium + thyroid replacement (2+ hr spacing). Menstruating women + bypass patients often need higher dose; reassess every 3-6 months on ferritin + transferrin saturation. Ferrous bisglycinate is gentler on GI when sulfate not tolerated.',
  },
  {
    drug: 'thiamine',
    aliases: ['vitamin b1', 'b1', 'thiamine hcl'],
    complexDosing: true,
    contraindications: ['thiamine allergy'],
    notes:
      'Post-bariatric typical: 50-100 mg PO daily in first 6 months post-op then per bariatric multivitamin. Watch for Wernicke encephalopathy precipitated by persistent vomiting / dehydration / rapid weight loss (triad: confusion, ophthalmoplegia, ataxia) — IV/IM thiamine 100-500 mg for suspected acute Wernicke. The clinical risk is missing the diagnosis, not over-dosing.',
  },
  {
    drug: 'ursodiol',
    aliases: ['actigall', 'urso', 'ursodeoxycholic acid'],
    adultMaxMgPerDay: 600,
    contraindications: ['ursodiol allergy', 'calcified radiopaque stones'],
    notes:
      'Post-bariatric gallstone PROPHYLAXIS: 300 mg PO BID for 6 months post-RYGB or post-sleeve (rapid weight loss → cholelithiasis risk). Some practices extend to 12 months. Not for treatment of established symptomatic stones — that needs cholecystectomy. Max 600 mg/day for this indication.',
  },
  {
    drug: 'pantoprazole',
    aliases: ['protonix'],
    adultMaxMgPerDay: 80,
    contraindications: ['ppi allergy', 'pantoprazole allergy'],
    notes:
      'Post-bariatric prophylaxis: 40 mg PO daily for 3-6 months post-sleeve gastrectomy (residual gastric acid + small pouch increases ulcer risk) and post-RYGB (marginal ulcer at gastrojejunal anastomosis). Max 80 mg/day for severe/refractory cases. Long-term PPI use post-bariatric carries the same risks as in non-bariatric populations (B12 / Ca / Mg absorption, C. diff risk).',
  },
  {
    drug: 'bariatric multivitamin',
    aliases: ['bariatric mvi', 'bariatric advantage', 'celebrate vitamins', 'bariatric fusion', 'optisource'],
    complexDosing: true,
    contraindications: ['hypervitaminosis a', 'iron overload'],
    notes:
      'Bariatric-specific multivitamin (Bariatric Advantage / Celebrate / Fusion / OPTISOURCE / etc.) contains higher doses of B-complex / iron / vitamin D / zinc / folate than standard adult MVI. Standard adult MVI is UNDERSUPPLEMENTED for bariatric patients — typical post-op regimen needs a bariatric-formulated MVI plus separate calcium citrate + vitamin D + B12. Validator emits a warning when "multivitamin" or "MVI" is documented for a bariatric-status patient without the bariatric-specific qualifier.',
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
