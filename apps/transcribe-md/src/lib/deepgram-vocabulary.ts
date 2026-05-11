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
 *  overlap) so the budget test sees what the runtime sees. */
export const CLINICAL_KEYTERMS: readonly string[] = Array.from(
  new Set<string>([
    ...MEDICATION_KEYTERMS,
    ...ANATOMY_TERMS,
    ...LAB_TESTS,
    ...PROCEDURES,
    ...COMMON_DIAGNOSES,
  ])
);
