// ============================================================================
// Deepgram keyterm vocabulary — medication lexicon for Nova-3 Medical.
// ----------------------------------------------------------------------------
// Fixes the "abirrobing" transcription class (generic → phonetic mush) by
// prompting Nova-3 with a curated medication lexicon. Deepgram `keyterm`
// prompting (SDK @4.11.3, docs at https://developers.deepgram.com/docs/keyterm)
// raises the prior on these tokens so near-homophones decode the drug
// name instead of an invented word.
//
// HARD LIMIT: Deepgram caps keyterms at 500 SUBWORD tokens TOTAL, not
// keyterms-as-strings. Medical names tokenize aggressively — e.g.
// "trimethoprim-sulfamethoxazole" is ~9 tokens on its own — so a list
// of even 150 short generics can blow the budget. We saw this in prod:
// a doctor's 7-min recording 400'd from Deepgram with "Keyterm limit
// exceeded" because the previous 180-entry working set was estimated
// at ~588 tokens.
//
// Today's list aims for ~75 entries / under 450 tokens (10% headroom
// below the 500 cap). The tail array below preserves the long form
// for any future per-specialty caller that has narrowed the domain
// enough to send a smaller subset; the working set wired to
// 01-transcribe.ts stays defensively trimmed.
//
// A unit test in deepgram-vocabulary.test.ts asserts the working set
// stays under 450 estimated tokens — break the budget and the test
// fails before the transcription path silently regresses.
//
// Trim policy (in priority order):
//   1. Keep all controlled substances (clinical-safety + spelling).
//   2. Keep pain / NSAID / opioids (pilot is pain-management focused).
//   3. Keep Iranian / ME brand spellings (pilot context).
//   4. Keep common cardiac, antibiotics, anticoagulants.
//   5. Drop tail-of-the-distribution generics that nova-3-medical
//      recognises out of the box.
// ============================================================================

/** Working set — sent on every nova-3-medical call. Stays under
 *  ~450 estimated subword tokens (10% headroom below Deepgram's 500
 *  cap). Order is by clinical priority, not alphabetical. */
export const MEDICATION_KEYTERMS: readonly string[] = [
  // ── Pain / NSAID / opioids — pilot focus + controlled substances ──
  'ibuprofen',
  'acetaminophen',
  'naproxen',
  'meloxicam',
  'celecoxib',
  'ketorolac',
  'diclofenac',
  'gabapentin',
  'tramadol',
  'morphine',
  'oxycodone',
  'hydrocodone',
  'codeine',
  'fentanyl',
  'buprenorphine',
  'naloxone',
  // ── Iranian / Middle-East common brand spellings (pilot context) ──
  'brufen',
  'profen',
  'voltaren',
  'panadol',
  'paracetamol',
  // ── Common controlled / behavioral-health (commonly spoken by brand) ──
  'alprazolam',
  'lorazepam',
  'clonazepam',
  'diazepam',
  'sertraline',
  'fluoxetine',
  'duloxetine',
  'xanax',
  'ambien',
  'adderall',
  // ── Top cardiac generics (high prescription volume) ──
  'atorvastatin',
  'lisinopril',
  'amlodipine',
  'metoprolol',
  'losartan',
  'carvedilol',
  'spironolactone',
  // ── Anticoagulants — safety-critical, easy to mis-transcribe ──
  'warfarin',
  'apixaban',
  'rivaroxaban',
  'clopidogrel',
  'eliquis',
  'xarelto',
  // ── Diabetes essentials (high volume + newer GLP-1s mis-spell) ──
  'metformin',
  'semaglutide',
  'liraglutide',
  'insulin glargine',
  'insulin aspart',
  'ozempic',
  // ── Common antibiotics ──
  'amoxicillin',
  'azithromycin',
  'doxycycline',
  'ciprofloxacin',
  'cephalexin',
  'clindamycin',
  'metronidazole',
  'penicillin',
  // ── Respiratory ──
  'albuterol',
  'fluticasone',
  'prednisone',
  // ── Endocrine / GI / diuretics — high-volume essentials ──
  'levothyroxine',
  'omeprazole',
  'pantoprazole',
  'ondansetron',
  'furosemide',
  'hydrochlorothiazide',
];

/** Reference tail — specialty-scoped callers can opt into this. */
export const MEDICATION_KEYTERMS_TAIL: readonly string[] = [
  // ── Additional brand names (EU + Middle East variants) ──
  'advil',
  'motrin',
  'tylenol',
  'aleve',
  'bayer',
  'excedrin',
  'mucinex',
  'robitussin',
  'sudafed',
  'claritin',
  'zyrtec',
  'allegra',
  'benadryl',
  'imodium',
  'pepto-bismol',
  'miralax',
  'colace',
  'tums',
  'mylanta',
  'maalox',
  'dulcolax',
  'aspirin bayer',
  'cataflam',
  'solpadeine',
  'nurofen',
  'panadeine',
  'perkocet',
  'percocet',
  'vicodin',
  'norco',
  'ultram',
  'soma',
  'flexeril',
  'skelaxin',
  'robaxin',
  'baclofen',
  'tizanidine',
  'cyclobenzaprine',
  // ── Additional US Rx generics (top 200 tail) ──
  'rosuvastatin',
  'ezetimibe',
  'fenofibrate',
  'gemfibrozil',
  'niacin',
  'omega-3',
  'colesevelam',
  'alirocumab',
  'evolocumab',
  'icosapent ethyl',
  'cholestyramine',
  'hydralazine',
  'doxazosin',
  'terazosin',
  'prazosin',
  'clonidine',
  'methyldopa',
  'minoxidil',
  'bumetanide',
  'torsemide',
  'chlorthalidone',
  'indapamide',
  'triamterene',
  'eplerenone',
  'glyburide',
  'tolbutamide',
  'rosiglitazone',
  'miglitol',
  'exenatide',
  'albiglutide',
  'pramlintide',
  'bromocriptine',
  'colesevelam',
  // ── Additional antimicrobials ──
  'penicillin v',
  'penicillin g',
  'ampicillin',
  'oxacillin',
  'nafcillin',
  'dicloxacillin',
  'piperacillin-tazobactam',
  'cefazolin',
  'cefuroxime',
  'ceftriaxone',
  'cefepime',
  'cefdinir',
  'cefpodoxime',
  'erythromycin',
  'clarithromycin',
  'minocycline',
  'tetracycline',
  'vancomycin',
  'linezolid',
  'daptomycin',
  'moxifloxacin',
  'ofloxacin',
  'gentamicin',
  'tobramycin',
  'amikacin',
  'nystatin',
  'terbinafine',
  'itraconazole',
  'ketoconazole',
  'miconazole',
  'clotrimazole',
  'famciclovir',
  'ganciclovir',
  'ribavirin',
  'remdesivir',
  'paxlovid',
  'nirmatrelvir-ritonavir',
  'molnupiravir',
  'isoniazid',
  'rifampin',
  'pyrazinamide',
  'ethambutol',
  // ── Specialty cardio ──
  'ticagrelor',
  'prasugrel',
  'cangrelor',
  'eptifibatide',
  'tirofiban',
  'alteplase',
  'tenecteplase',
  'heparin',
  'enoxaparin',
  'fondaparinux',
  'protamine',
  'phytonadione',
  'ranolazine',
  'ivabradine',
  'sacubitril',
  'dapagliflozin',
  'empagliflozin',
  'tafamidis',
  'milrinone',
  'dobutamine',
  'dopamine',
  'norepinephrine',
  'epinephrine',
  'vasopressin',
  'nitroglycerin',
  'nitroprusside',
  'nicardipine',
  'clevidipine',
  'labetalol',
  'esmolol',
  // ── Respiratory — specialty ──
  'mometasone',
  'ciclesonide',
  'beclomethasone',
  'arformoterol',
  'indacaterol',
  'olodaterol',
  'glycopyrrolate',
  'umeclidinium',
  'aclidinium',
  'roflumilast',
  'omalizumab',
  'mepolizumab',
  'benralizumab',
  'dupilumab',
  'cromolyn',
  'theophylline',
  // ── Neuro / psychiatry tail ──
  'amitriptyline',
  'nortriptyline',
  'imipramine',
  'desipramine',
  'doxepin',
  'mirtazapine',
  'vortioxetine',
  'vilazodone',
  'levomilnacipran',
  'desvenlafaxine',
  'phenelzine',
  'selegiline',
  'tranylcypromine',
  'carbamazepine',
  'oxcarbazepine',
  'topiramate',
  'levetiracetam',
  'phenytoin',
  'valproic acid',
  'divalproex',
  'zonisamide',
  'pregabalin',
  'vigabatrin',
  'perampanel',
  'lacosamide',
  'donepezil',
  'rivastigmine',
  'galantamine',
  'memantine',
  'ropinirole',
  'pramipexole',
  'carbidopa-levodopa',
  'selegiline',
  'entacapone',
  'rasagiline',
  // ── Endocrine tail ──
  'testosterone',
  'estradiol',
  'progesterone',
  'medroxyprogesterone',
  'norethindrone',
  'drospirenone',
  'ethinyl estradiol',
  'levonorgestrel',
  'tamoxifen',
  'raloxifene',
  'anastrozole',
  'letrozole',
  'exemestane',
  'leuprolide',
  'goserelin',
  'spironolactone',
  'finasteride',
  'dutasteride',
  'sildenafil',
  'tadalafil',
  'vardenafil',
  // ── GI tail ──
  'dicyclomine',
  'hyoscyamine',
  'mesalamine',
  'sulfasalazine',
  'infliximab',
  'adalimumab',
  'vedolizumab',
  'ustekinumab',
  'tofacitinib',
  'budesonide ec',
  'rifaximin',
  'linaclotide',
  'lubiprostone',
  'plecanatide',
  'misoprostol',
  'sucralfate',
  // ── Renal ──
  'tolvaptan',
  'calcitriol',
  'paricalcitol',
  'sevelamer',
  'lanthanum',
  'cinacalcet',
  // ── Immunosuppressants / rheumatology ──
  'methotrexate',
  'hydroxychloroquine',
  'leflunomide',
  'azathioprine',
  'mycophenolate',
  'cyclosporine',
  'tacrolimus',
  'sirolimus',
  'etanercept',
  'tocilizumab',
  'rituximab',
  'abatacept',
  'secukinumab',
  'ixekizumab',
  // ── Dermatology ──
  'isotretinoin',
  'adapalene',
  'tretinoin',
  'clobetasol',
  'triamcinolone',
  'hydrocortisone',
  'tacrolimus ointment',
  'pimecrolimus',
  'permethrin',
  'mupirocin',
  // ── Ophthalmology ──
  'timolol',
  'latanoprost',
  'bimatoprost',
  'travoprost',
  'brimonidine',
  'dorzolamide',
  'olopatadine',
  'ketotifen',
  // ── Oncology (high volume) ──
  'imatinib',
  'dasatinib',
  'nilotinib',
  'ibrutinib',
  'venetoclax',
  'rituximab',
  'obinutuzumab',
  'pembrolizumab',
  'nivolumab',
  'ipilimumab',
  'atezolizumab',
  'trastuzumab',
  'bevacizumab',
  'cetuximab',
];

/** Full corpus = working set ∪ tail. Order preserved; duplicates removed. */
export const MEDICATION_KEYTERMS_FULL: readonly string[] = Array.from(
  new Set<string>([...MEDICATION_KEYTERMS, ...MEDICATION_KEYTERMS_TAIL])
);

// ============================================================================
// Q2 fix-pack — clinical-vocabulary expansion (audit findings 01.9 + 03.4)
// ----------------------------------------------------------------------------
// MEDICATION_KEYTERMS biased Nova-3-medical for drug names; anatomy,
// labs, procedures, and common-diagnosis terms still mistranscribe.
// These four small lists ride alongside the medications so the same
// keyterm payload covers the full clinical surface. L1 (conversation)
// + L1b (dictation) both consume CLINICAL_KEYTERMS below.
//
// Sizing discipline: each list is hand-curated to ~12 highest-yield
// terms. The brief asked for 20-30 per category, but Deepgram's
// 500-subword-token per-request cap (summed across all keyterms)
// makes that infeasible without giving up medication coverage.
// Rather than swap one cohort for another, we ship the densest-yield
// 48 new terms across these categories. The test below enforces the
// combined CLINICAL_KEYTERMS payload stays under the 450-token
// internal cap.
// ============================================================================

/** Most-commonly-mistranscribed body parts + anatomical regions.
 *  Trimmed to fit the 450-token combined cap with MEDICATION_KEYTERMS.
 *
 *  2026-05-11 expansion (issue #202): added common body-part terms
 *  after the PriMock57 eval surfaced systematic "elbow" → "eyebrow"
 *  substitutions from Deepgram nova-3-medical. The keyterm bias makes
 *  the ASR prior favour these common anatomical surface forms in
 *  ambiguous decoder paths.
 *
 *  Design notes:
 *  - Include BOTH the confusable pair (`elbow` + `eyebrow`,
 *    `cheek` + `chest`) so neither side is biased against the other —
 *    the goal is "make anatomy recognisable", not "force elbow."
 *  - Bias toward terms patients use in their own dialogue (knee,
 *    shoulder), not Latinate-only forms (genu, articulatio humeri).
 *  - Medical-anatomical terms (auscultation, periumbilical) kept
 *    because they're high-value in O / Exam sections; nova-3-medical
 *    drifts on them too.
 *
 *  Budget: 88 estimated tokens across 33 entries (was 28 tokens / 7
 *  entries). Projected CLINICAL_KEYTERMS total ≈ 426 / 450 cap → 24-
 *  token headroom; the budget test asserts < 450 with the same
 *  heuristic (ceil(chunk.len / 3.5)).
 */
export const ANATOMY_TERMS: readonly string[] = [
  // Medical-anatomical (high-value in O/Exam; pre-2026-05-11 set).
  'auscultation',
  'palpation',
  'epigastric',
  'periumbilical',
  'pharyngeal',
  'tympanic membrane',
  'conjunctiva',
  // Joints + major extremities — the "elbow → eyebrow" class from
  // issue #202.
  'elbow',
  'knee',
  'wrist',
  'ankle',
  'shoulder',
  'hip',
  'jaw',
  // Face / head — clinically-common surface terms.
  //
  // **`eyebrow` is deliberately EXCLUDED** despite the initial design
  // intuition that "including both confusables is neutral." Empirical
  // test against the PriMock57 case-02 audio (issue #202) showed
  // Deepgram nova-3-medical picks "eyebrows" over "elbows" when BOTH
  // are in the keyterm list, but correctly picks "elbows" when only
  // "elbow" is in the list. The keyterm boost is influence, not
  // neutral inclusion. "Eyebrow" in a clinical SOAP context is
  // exceptionally rare (alopecia, dermatitis of the brow), so the
  // safer prior is to *not* boost it — the few legitimate cases will
  // still decode from the acoustic model alone.
  'eyelid',
  'forehead',
  'cheek',
  // Trunk regions — chest/abdomen drift in conversation.
  'chest',
  'abdomen',
  'flank',
  'groin',
  'pelvis',
  // Limb segments.
  'thigh',
  'calf',
  'shin',
  'forearm',
  'foot',
  'hand',
  // Back regions — frequent in pain-management contexts.
  'lower back',
  'upper back',
  // Medical-anatomical confusables (drift to lay surface forms).
  'inguinal',
  'suprapubic',
];

/** Common labs / panels / individual tests. Acronyms used over full
 *  forms where the acronym has a unique pronunciation (CBC, ESR) —
 *  saves token budget without losing recognition power. */
export const LAB_TESTS: readonly string[] = [
  'hemoglobin a1c',
  'basic metabolic panel',
  'complete blood count',
  'lipid panel',
  'troponin',
  'creatinine',
  'electrolytes',
  'urinalysis',
  'prothrombin time',
];

/** Common in-office + inpatient procedures. */
export const PROCEDURES: readonly string[] = [
  'electrocardiogram',
  'echocardiogram',
  'spirometry',
  'arthrocentesis',
  'punch biopsy',
  'cryotherapy',
  'cerumen removal',
  'venipuncture',
];

/** Top chronic + acute diagnoses where transcription drift produces
 *  miscoded conditions (e.g. "hypertension" → "high pretension"). */
export const COMMON_DIAGNOSES: readonly string[] = [
  'hypertension',
  'hyperlipidemia',
  'hypothyroidism',
  'diabetes mellitus',
  'osteoarthritis',
  'atrial fibrillation',
  'cellulitis',
  'pneumonia',
];

/** Q2 fix-pack — unified keyterm payload used by L1 (conversation) and
 *  L1b (dictation) transcription calls. Order: medications first
 *  (highest-stakes — a wrong drug name is a clinical-safety event),
 *  then anatomy / labs / procedures / diagnoses. Deduped (rare
 *  overlap) so the budget test sees what the runtime sees.
 *
 *  2026-05-13 (Issues #202 + #206): production paths shifted to
 *  `buildKeytermsForVisit` (see deepgram-keyterm-builder.ts) — this
 *  global constant is kept for the eval harness and back-compat but
 *  L1 + L1b no longer use it directly. The eval harness still wants
 *  a deterministic global baseline to compare against. */
export const CLINICAL_KEYTERMS: readonly string[] = Array.from(
  new Set<string>([
    ...MEDICATION_KEYTERMS,
    ...ANATOMY_TERMS,
    ...LAB_TESTS,
    ...PROCEDURES,
    ...COMMON_DIAGNOSES,
  ])
);

// ============================================================================
// 2026-05-13 Issues #202 + #206 — per-specialty keyterm bundles.
// ----------------------------------------------------------------------------
// The pre-2026-05-13 strategy shipped CLINICAL_KEYTERMS (~124 terms) on
// EVERY visit regardless of specialty. Production audit confirmed
// dilution: every visit got cardiothoracic terms + dermatologic terms +
// obstetric terms, etc., so each individual term received less
// attentional weight. Rare/specialty-specific terms (the Implanon /
// Nexplanon contraceptive implants from Issue #206) were entirely
// absent because they didn't make the cut for the global list.
//
// Per-specialty bundles are layered on top of a smaller core via the
// builder (see deepgram-keyterm-builder.ts). Each bundle stays small
// (~20-30 terms) so the per-visit payload sits in Deepgram's
// recommended 20-50 sweet spot rather than the historical ~124.
//
// Bundle authorship guidelines:
//   - Specialty-IDIOSYNCRATIC terms only — common cardiac meds belong
//     in the core, not in cardiology's bundle.
//   - Brand AND generic for medications likely to be dictated by brand
//     (Ozempic, Mounjaro, Zepbound, Wegovy, Implanon, Nexplanon).
//   - Procedure names this specialty uses heavily.
//   - Avoid generic English words that aren't clinical-domain.
// ============================================================================

/** Terms that ride on EVERY visit regardless of specialty — the
 *  universal clinical-vocabulary baseline.
 *
 *  Composition: anatomy (~32) + labs (~9) + procedures (~8) +
 *  common diagnoses (~8). Sized ~57 entries / ~200 estimated tokens.
 *
 *  Why no medications in CORE (2026-05-13 PR-2 audit follow-up): the
 *  per-visit token budget is ~450 estimated tokens (10% under
 *  Deepgram's 500 cap). After PR-2 wired the ISMP confused-drug
 *  safety floor (~150 tokens) + per-specialty bundles (~85 tokens),
 *  a CORE that also carried top-25 universal meds pushed the total
 *  over the cap and forced the builder to drop the specialty layer
 *  entirely (the regression caught by the auditor before merge). The
 *  specialty bundles + safety floor together cover every medication
 *  that's broadly common (primary_care carries lisinopril, losartan,
 *  metoprolol, atorvastatin, metformin; bariatric carries GLP-1s;
 *  vascular carries anticoagulants; etc.). Visits with
 *  `specialty=unspecified` get the safety floor + CORE only — which
 *  still covers the most-confused-name pairs (the safety floor IS
 *  the most-load-bearing medication coverage) and the universal
 *  anatomy/labs/procedure vocabulary. */
export const CORE_KEYTERMS: readonly string[] = Array.from(
  new Set<string>([
    ...ANATOMY_TERMS,
    ...LAB_TESTS,
    ...PROCEDURES,
    ...COMMON_DIAGNOSES,
  ]),
);

/** Specialty bundles — per-specialty term lists layered on top of
 *  CORE_KEYTERMS by the builder. Each bundle should stay under ~30
 *  terms to keep the per-visit total below Deepgram's recommended
 *  sweet spot (~50). Most entries are drawn from
 *  MEDICATION_KEYTERMS_TAIL plus specialty-specific additions
 *  (Implanon / Nexplanon for ob_gyn — these were absent from any
 *  prior list and that's the Issue #206 root cause). */
export const SPECIALTY_KEYTERMS: Record<string, readonly string[]> = {
  // ─── Bariatric surgery ────────────────────────────────────────
  // GLP-1 family + bariatric procedures. The GLP-1 brand collisions
  // (Ozempic / Wegovy / Mounjaro / Zepbound) are addressed more
  // densely by the PR-2 confused-drug-names floor; this bundle
  // pre-stages them in case the safety floor isn't yet loaded.
  bariatric_surgery: [
    'semaglutide',
    'Ozempic',
    'Wegovy',
    'tirzepatide',
    'Mounjaro',
    'Zepbound',
    'liraglutide',
    'Saxenda',
    'Victoza',
    'Trulicity',
    'dulaglutide',
    'phentermine',
    'topiramate',
    'Qsymia',
    'naltrexone',
    'Contrave',
    'orlistat',
    'gastric bypass',
    'sleeve gastrectomy',
    'duodenal switch',
    'lap band',
    'Roux-en-Y',
    'GERD',
    'dumping syndrome',
    'BMI',
    'body mass index',
  ],

  // ─── Weight management (non-surgical) ─────────────────────────
  // Overlap with bariatric_surgery on GLP-1 brands; differs by
  // including more metabolic-panel + lifestyle terms.
  weight_management: [
    'semaglutide',
    'Ozempic',
    'Wegovy',
    'tirzepatide',
    'Mounjaro',
    'Zepbound',
    'liraglutide',
    'Rybelsus',
    'phentermine',
    'Adipex',
    'topiramate',
    'Qsymia',
    'naltrexone',
    'Contrave',
    'bupropion',
    'metformin',
    'orlistat',
    'lipid panel',
    'A1C',
    'fasting glucose',
    'TSH',
    'body composition',
    'waist circumference',
    'visceral fat',
  ],

  // ─── Primary care / family medicine / internal medicine ───────
  primary_care: [
    'lisinopril',
    'losartan',
    'hydrochlorothiazide',
    'amlodipine',
    'metoprolol',
    'atorvastatin',
    'metformin',
    'glipizide',
    'glyburide',
    'Januvia',
    'sitagliptin',
    'levothyroxine',
    'liothyronine',
    'sertraline',
    'fluoxetine',
    'escitalopram',
    'duloxetine',
    'bupropion',
    'gabapentin',
    'tramadol',
    'omeprazole',
    'pantoprazole',
    'ibuprofen',
    'acetaminophen',
    'amoxicillin',
    'azithromycin',
  ],

  // ─── Cardiology ───────────────────────────────────────────────
  cardiology: [
    'apixaban',
    'rivaroxaban',
    'dabigatran',
    'warfarin',
    'Coumadin',
    'Eliquis',
    'Xarelto',
    'clopidogrel',
    'Plavix',
    'ticagrelor',
    'Brilinta',
    'metoprolol',
    'carvedilol',
    'bisoprolol',
    'atorvastatin',
    'rosuvastatin',
    'simvastatin',
    'ezetimibe',
    'amiodarone',
    'digoxin',
    'sacubitril',
    'valsartan',
    'Entresto',
    'EKG',
    'echocardiogram',
    'troponin',
    'BNP',
    'NT-proBNP',
  ],

  // ─── Orthopedics ──────────────────────────────────────────────
  orthopedics: [
    'meloxicam',
    'naproxen',
    'celecoxib',
    'cyclobenzaprine',
    'tizanidine',
    'methocarbamol',
    'tramadol',
    'oxycodone',
    'hydrocodone',
    'morphine',
    'gabapentin',
    'pregabalin',
    'arthrocentesis',
    'corticosteroid injection',
    'hyaluronic acid injection',
    'rotator cuff',
    'anterior cruciate ligament',
    'meniscus',
    'osteoarthritis',
    'rheumatoid arthritis',
    'plantar fasciitis',
    'carpal tunnel',
    'lumbar radiculopathy',
    'fracture',
    'sprain',
    'strain',
  ],

  // ─── Dermatology ──────────────────────────────────────────────
  dermatology: [
    'tretinoin',
    'adapalene',
    'tazarotene',
    'isotretinoin',
    'clindamycin topical',
    'benzoyl peroxide',
    'minocycline',
    'doxycycline',
    'spironolactone',
    'hydroquinone',
    'mupirocin',
    'fluconazole',
    'terbinafine',
    'permethrin',
    'triamcinolone',
    'clobetasol',
    'tacrolimus',
    'pimecrolimus',
    'dupilumab',
    'Dupixent',
    'biopsy',
    'excision',
    'cryotherapy',
    'melanoma',
    'basal cell carcinoma',
    'squamous cell carcinoma',
    'actinic keratosis',
    'rosacea',
    'psoriasis',
    'eczema',
  ],

  // ─── Obstetrics & Gynecology ──────────────────────────────────
  // CRITICAL: this bundle includes Implanon + Nexplanon — the seed
  // case from Issue #206. Pre-fix, these contraceptive implants
  // were ABSENT from any keyterm list, causing TTS/ASR to substitute
  // "insulin" via 3-syllable medical-context match.
  ob_gyn: [
    'Implanon',
    'Nexplanon',
    'etonogestrel',
    'levonorgestrel',
    'Mirena',
    'Kyleena',
    'Skyla',
    'Liletta',
    'Paragard',
    'medroxyprogesterone',
    'Depo-Provera',
    'norethindrone',
    'drospirenone',
    'Yaz',
    'Yasmin',
    'estradiol',
    'tranexamic acid',
    'misoprostol',
    'methotrexate',
    'colposcopy',
    'endometriosis',
    'polycystic ovary syndrome',
    'gestational diabetes',
    'preeclampsia',
    'group B strep',
    'human papillomavirus',
  ],

  // ─── Urgent care ──────────────────────────────────────────────
  urgent_care: [
    'amoxicillin',
    'azithromycin',
    'cephalexin',
    'doxycycline',
    'sulfamethoxazole',
    'trimethoprim',
    'metronidazole',
    'fluconazole',
    'oseltamivir',
    'Tamiflu',
    'albuterol',
    'methylprednisolone',
    'Medrol',
    'prednisone',
    'ondansetron',
    'Zofran',
    'sumatriptan',
    'lidocaine',
    'tetanus',
    'group A strep',
    'rapid strep',
    'urinary tract infection',
    'otitis media',
    'pneumonia',
    'cellulitis',
    'laceration',
    'sprain',
    'abscess',
  ],

  // ─── Pain management ──────────────────────────────────────────
  pain_management: [
    'oxycodone',
    'hydrocodone',
    'morphine',
    'fentanyl',
    'buprenorphine',
    'Suboxone',
    'naloxone',
    'naltrexone',
    'methadone',
    'tramadol',
    'tapentadol',
    'gabapentin',
    'pregabalin',
    'duloxetine',
    'nortriptyline',
    'amitriptyline',
    'lidocaine patch',
    'capsaicin',
    'baclofen',
    'cyclobenzaprine',
    'epidural steroid injection',
    'radiofrequency ablation',
    'nerve block',
    'PCA',
    'PDMP',
    'opioid agreement',
  ],

  // ─── Pediatrics ───────────────────────────────────────────────
  pediatrics: [
    'amoxicillin',
    'augmentin',
    'cephalexin',
    'azithromycin',
    'acetaminophen',
    'ibuprofen',
    'diphenhydramine',
    'Benadryl',
    'cetirizine',
    'Zyrtec',
    'albuterol',
    'fluticasone',
    'Flovent',
    'montelukast',
    'Singulair',
    'methylphenidate',
    'amphetamine',
    'guanfacine',
    'risperidone',
    'otitis media',
    'strep pharyngitis',
    'bronchiolitis',
    'croup',
    'viral exanthem',
    'attention deficit',
    'autism spectrum',
  ],

  // ─── Vascular surgery ─────────────────────────────────────────
  vascular_surgery: [
    'apixaban',
    'rivaroxaban',
    'dabigatran',
    'edoxaban',
    'warfarin',
    'enoxaparin',
    'Lovenox',
    'heparin',
    'aspirin',
    'clopidogrel',
    'cilostazol',
    'iohexol',
    'gadolinium',
    'eGFR',
    'creatinine clearance',
    'endovascular aneurysm repair',
    'EVAR',
    'TEVAR',
    'carotid endarterectomy',
    'angioplasty',
    'stent',
    'fistula',
    'graft',
    'deep vein thrombosis',
    'peripheral artery disease',
    'aortic aneurysm',
  ],

  // ─── Endocrinology ────────────────────────────────────────────
  // T-family insulins + GLP-1 + thyroid. Heavy overlap with
  // bariatric_surgery; the difference is broader thyroid + adrenal
  // + pituitary coverage. ISMP confused-drug pairs Trulicity /
  // Tradjenta / Toujeo / Tresiba / Tanzeum live here too.
  endocrinology: [
    'levothyroxine',
    'liothyronine',
    'levothyroxine sodium',
    'methimazole',
    'propylthiouracil',
    'hydrocortisone',
    'fludrocortisone',
    'desmopressin',
    'cabergoline',
    'bromocriptine',
    'semaglutide',
    'Ozempic',
    'Rybelsus',
    'tirzepatide',
    'Mounjaro',
    'liraglutide',
    'Trulicity',
    'Tradjenta',
    'Toujeo',
    'Tresiba',
    'Lantus',
    'Levemir',
    'Humalog',
    'Novolog',
    'insulin glargine',
    'insulin aspart',
    'TSH',
    'free T4',
    'free T3',
    'A1C',
  ],

  // ─── Functional medicine / integrative ────────────────────────
  // Charm Health's target segment per the EHR roadmap. Supplements
  // + functional labs (DUTCH, GI-MAP) heavily-dictated.
  functional_medicine: [
    'methylated folate',
    'vitamin D3',
    'vitamin B12',
    'methylcobalamin',
    'magnesium glycinate',
    'omega-3',
    'fish oil',
    'curcumin',
    'berberine',
    'ashwagandha',
    'NAD+',
    'glutathione',
    'CoQ10',
    'probiotic',
    'L-theanine',
    'melatonin',
    'GLP-1',
    'cortisol',
    'DUTCH test',
    'GI-MAP',
    'Genova',
    'hormone replacement',
    'bioidentical hormone',
    'low FODMAP',
    'autoimmune',
    'leaky gut',
  ],

  // ─── Psychiatry ───────────────────────────────────────────────
  // SSRI / SNRI / antipsychotic / mood stabilizer cluster. Many
  // ISMP confused-name pairs (Celexa/Celebrex/Cerebyx, Lexapro/
  // Loxitane) live here.
  psychiatry: [
    'sertraline',
    'Zoloft',
    'fluoxetine',
    'Prozac',
    'escitalopram',
    'Lexapro',
    'citalopram',
    'Celexa',
    'duloxetine',
    'Cymbalta',
    'venlafaxine',
    'Effexor',
    'bupropion',
    'Wellbutrin',
    'mirtazapine',
    'Remeron',
    'trazodone',
    'lithium',
    'lamotrigine',
    'Lamictal',
    'valproate',
    'aripiprazole',
    'Abilify',
    'quetiapine',
    'Seroquel',
    'olanzapine',
    'Zyprexa',
    'risperidone',
    'Risperdal',
  ],

  // ─── Unspecified — empty bundle ───────────────────────────────
  // Practice didn't tag a specialty, or the tag didn't match any
  // canonical key. Visit uses CORE_KEYTERMS only.
  // ─── Gastroenterology ─────────────────────────────────────────
  // Added 2026-08-14 with the GI catalog row.
  //
  // ⚠ SIZED BY TOKENS, NOT BY TERM COUNT — AND THE DIFFERENCE BIT.
  // The per-bundle rule everyone reads is "<= 30 terms". The rule that
  // actually binds is DEFAULT_TOKEN_BUDGET = 450 shared across core +
  // safety floor + specialty, with estimateTokens = ceil(len / 3.5).
  // A 30-term GI draft PASSED the term ceiling and came to 143 tokens
  // against a 111-token heaviest-existing bundle (dermatology), which
  // tripped the budget enforcer and would have SILENTLY TRIMMED GI terms
  // at runtime. GI is the first specialty whose vocabulary is mostly
  // multi-word anatomy ('endoscopic mucosal resection' costs 8 tokens;
  // 'omeprazole' costs 3), so the proxy and the constraint diverge here
  // for the first time. Caught by the B1 regression guard in
  // tests/lib/confused-drug-names.test.ts, which enumerates EVERY
  // specialty and asserts budgetEnforced === false.
  //
  // This bundle: 24 terms / 103 estimated tokens.
  // If you add a term, re-measure the TOKENS. The term count will lie.
  //
  // Priority order for what earned a slot: (1) mis-transcription changes
  // a DRUG, (2) the organism/condition name IS the diagnosis, (3) what
  // was actually DONE in the procedure, (4) landmarks that PROVE the
  // extent reached and the pathology words that drive the surveillance
  // interval. Dropped at the budget, recorded so it is not re-derived:
  // esophagogastroduodenoscopy (kept as 'EGD', 1 token vs 8), argon
  // plasma coagulation, eosinophilic esophagitis, esophageal varices,
  // Barrett esophagus, sphincterotomy, ustekinumab, esomeprazole,
  // sucralfate, adalimumab, lactulose, linaclotide, ursodiol,
  // pancrelipase, cold snare, hemostasis clip, adenomatous, melena,
  // hepatic/splenic flexure, hepatic encephalopathy, elastography,
  // choledocholithiasis. Upper-GI and hepatology coverage is deliberately
  // thin: the pilot's reference dictations are colonoscopy op-notes and
  // reflux clinic visits, and the reflux DRUGS are all still here. If the
  // pilot shows one of the dropped terms being mis-transcribed, SWAP —
  // do not append.
  gastroenterology: [
    'omeprazole',
    'pantoprazole',
    'famotidine',
    'mesalamine',
    'budesonide',
    'azathioprine',
    'infliximab',
    'vedolizumab',
    'rifaximin',
    'Helicobacter pylori',
    'ulcerative colitis',
    "Crohn's disease",
    'diverticulosis',
    'colonoscopy',
    'EGD',
    'polypectomy',
    'endoscopic mucosal resection',
    'retroflexion',
    'ileocecal valve',
    'appendiceal orifice',
    'terminal ileum',
    'sessile serrated lesion',
    'tubular adenoma',
    'hematochezia',
  ],

  unspecified: [],
};
