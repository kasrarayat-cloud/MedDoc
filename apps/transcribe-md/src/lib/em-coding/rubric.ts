// ============================================================================
// E&M Coding — AMA 2021 rubric constants (Phase 5.2)
// ----------------------------------------------------------------------------
// Constants that mirror docs/em-coding-rubric-2021.md exactly. When AMA
// publishes 2026 updates the doc gets edited first, then these values
// cascade. Keep this file pure data — no I/O, no DB, no Redis. The
// scoring engine and the test corpus both read from here so bugs in the
// rubric show up identically in product + tests.
// ============================================================================

import type { ElementLevel, EmCode, MdmTier, VisitType } from './types';

/** Rubric version stamp — recorded on every EmScore for audit. */
export const RUBRIC_VERSION = '2021.1' as const;

// ============================================================================
// 1. Code ladder
// ============================================================================

/** MDM-tier ↔ CPT code map (per rubric §1.1, §1.2). */
export const MDM_TO_CODE: Record<VisitType, Record<MdmTier, EmCode>> = {
  established: {
    straightforward: '99212',
    low: '99213',
    moderate: '99214',
    high: '99215',
  },
  new: {
    straightforward: '99202',
    low: '99203',
    moderate: '99204',
    high: '99205',
  },
};

/** Time band per code (rubric §1.1, §1.2). band = [min, max]. */
export const TIME_BAND: Record<EmCode, { min: number; max: number; label: string }> = {
  '99202': { min: 15, max: 29, label: '15-29 min' },
  '99203': { min: 30, max: 44, label: '30-44 min' },
  '99204': { min: 45, max: 59, label: '45-59 min' },
  '99205': { min: 60, max: 74, label: '60-74 min' },
  '99211': { min: 0, max: 9, label: '<10 min' },
  '99212': { min: 10, max: 19, label: '10-19 min' },
  '99213': { min: 20, max: 29, label: '20-29 min' },
  '99214': { min: 30, max: 39, label: '30-39 min' },
  '99215': { min: 40, max: 54, label: '40-54 min' },
};

/** Ladder ordering for "next level up" lookups. */
export const ESTABLISHED_LADDER: EmCode[] = ['99212', '99213', '99214', '99215'];
export const NEW_LADDER: EmCode[] = ['99202', '99203', '99204', '99205'];

/** ElementLevel rank used by resolveTier (descending sort). */
export const LEVEL_RANK: Record<ElementLevel, number> = {
  minimal: 0,
  low: 1,
  moderate: 2,
  high: 3,
};

/** ElementLevel → MdmTier collapse (used after 2-of-3 sort). */
export const LEVEL_TO_TIER: Record<ElementLevel, MdmTier> = {
  minimal: 'straightforward',
  low: 'low',
  moderate: 'moderate',
  high: 'high',
};

// ============================================================================
// 2. Revenue delta table (rubric §5)
// ============================================================================

export const REVENUE_DELTA: Record<string, number> = {
  '99213->99214': 32,
  '99214->99215': 44,
  '99203->99204': 52,
  '99204->99205': 76,
  '99212->99213': 20,
  '99202->99203': 28,
};

// ============================================================================
// 3. Deterministic counter constants (rubric §3)
// ============================================================================

/** 8 standard HPI elements (1995/1997 taxonomy). */
export const HPI_ELEMENTS = [
  'location',
  'quality',
  'severity',
  'duration',
  'timing',
  'context',
  'modifyingFactors',
  'associatedSignsSymptoms',
] as const;

export type HpiElement = (typeof HPI_ELEMENTS)[number];

/** Per-HPI-element keyword/regex family. The regex is intentionally
 *  loose — the corpus is the calibration mechanism. False positives at
 *  the tail are acceptable; missing a subtle prose-buried element is
 *  tolerable per rubric §3.1.
 *
 *  Each pattern is matched against the lowercased Subjective body.
 *  Order matters within each family: the FIRST matching pattern's
 *  index drives `scoreHpiElement` confidence (idx===0 → 1.0, else 0.65). */
export const HPI_PATTERNS: Record<HpiElement, RegExp[]> = {
  location: [
    // Explicit "location:" tag wins.
    /\blocation\s*[:=]/i,
    // Specific body sites — keep tight (avoid generic anatomy mentions
    // that surface in PMH or PE prose).
    /\b(?:right|left|bilateral|substernal|retrosternal|epigastric|periumbilical|suprapubic|pharyngeal)\b/i,
    /\b(?:chest|abdom(?:en|inal)|throat|sinus(?:es)?|ear[s]?|eye[s]?|knee[s]?|shoulder[s]?|ankle[s]?|flank|joint|bladder area)\s+(?:pain|discomfort|tightness|pressure|ache|burning|swelling)/i,
  ],
  quality: [
    /\bquality\s*[:=]/i,
    // Quality adjectives — keep these specific to symptom description.
    /\b(sharp|dull|aching|burning|crushing|stabbing|throbbing|cramping|squeezing|pressure-like|gnawing|productive (?:cough|sputum)?|non-productive|tightness|pulsating)\b/i,
  ],
  severity: [
    /\bseverity\s*[:=]/i,
    // 8/10, 6 of 10
    /\b\d{1,2}\s*[\/-]\s*10\b/,
    /\b\d{1,2}\s*out of\s*10\b/i,
    /\b(?:limiting adls?|debilitating|incapacitating|profound\s+(?:fatigue|weakness)|severe(?:ly)?|intense)\b/i,
  ],
  duration: [
    /\bduration\s*[:=]/i,
    // N days/weeks/months — strict "duration of complaint" range.
    /\b\d{1,3}\s*[-]?\s*(?:days?|weeks?|hours?|months?|years?|yrs?|wks?|mos?|h\/o|hours?\s+ago)\b/i,
    /\bsince\s+(?:yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|last\s+(?:week|month|night))/i,
    /\b\d{1,2}-(?:day|week|month|year|hour|yr|mo)\s+(?:h\/o|history|hx)/i,
  ],
  timing: [
    /\btiming\s*[:=]/i,
    /\b(?:intermittent|constant(?:ly)?|continuous|episodic|sudden onset|gradual|progressive|nocturnal|paroxysmal|worse (?:in|at)\s+(?:morning|night|noon)|with exertion|at rest|on exertion|exertional|after meals|postprandial)\b/i,
  ],
  context: [
    /\bcontext\s*[:=]/i,
    // Setting / triggers — must be a clear precipitating factor.
    /\b(?:after\s+(?:eating|meals|exercise|exertion|fall|trauma|injury)|with\s+(?:exertion|exercise|movement|stairs|walking|coughing|deep breath)|triggered by|provoked by|brought on by|stairs at home|sick contacts?|exposure to|recent travel)\b/i,
  ],
  modifyingFactors: [
    /\bmodifying factors?\s*[:=]/i,
    // What helps / worsens — keep tight, must be an explicit modifier.
    /\b(?:improves? with|improved with|relieved by|relieves? with|alleviated by|aggravated by|worsens? with|exacerbated by|no relief with|minimal relief|partial relief|relieved by rest|better with|worse with)\b/i,
  ],
  associatedSignsSymptoms: [
    /\bassociated\s+(?:signs|symptoms|sx)/i,
    // "with N&V" / "denies fever" / common co-symptom prefixes.
    /\b(?:with\s+(?:nausea|fever|vomiting|cough|sob|dyspnea|diaphoresis|dizziness|chills|fatigue|weight loss|weight gain|chest pain|n[\/&]v|hemoptysis)|denies\s+(?:fever|nausea|vomiting|sob|chest pain|dyspnea|chills|hemoptysis|diarrhea|dysuria|chest pain|cough)|accompanied by|along with)\b/i,
  ],
};

/** 14 canonical ROS systems (rubric §3.2). */
export const ROS_SYSTEMS = [
  'constitutional',
  'eyes',
  'entMouth',
  'cardiovascular',
  'respiratory',
  'gastrointestinal',
  'genitourinary',
  'musculoskeletal',
  'integumentary',
  'neurological',
  'psychiatric',
  'endocrine',
  'hematologicLymphatic',
  'allergicImmunologic',
] as const;

export type RosSystem = (typeof ROS_SYSTEMS)[number];

/** Map ROS system → keyword family. Detects explicit system labels AND
 *  "denies <symptom-of-system>" patterns (rubric §3.2). */
export const ROS_KEYWORDS: Record<RosSystem, RegExp[]> = {
  constitutional: [
    /\bconstitutional\b/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(fever|chills|weight (?:loss|gain|change)|fatigue|night sweats|malaise)\b/i,
  ],
  eyes: [
    /\beyes?\s*:/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(vision changes?|eye pain|drainage|blurred vision|diplopia|photophobia)\b/i,
  ],
  entMouth: [
    /\b(ent[\s\/]?mouth|ent\b|hemmt|ent\/mouth)\b/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(sore throat|ear pain|nasal congestion|oral lesions|hoarseness|earache|otalgia|sinus pain)\b/i,
  ],
  cardiovascular: [
    /\b(cardiovascular|cv\b|cardiac\b)\s*[:.]?/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(chest pain|palpitations|edema|orthopnea|pnd|syncope)\b/i,
  ],
  respiratory: [
    /\b(respiratory|resp\b|pulmonary)\s*[:.]?/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(cough|sob|shortness of breath|dyspnea|wheezing|hemoptysis)\b/i,
  ],
  gastrointestinal: [
    /\b(gastrointestinal|gi\b)\s*[:.]?/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(nausea|vomiting|abdominal pain|diarrhea|constipation|change in bowel|melena|hematemesis|reflux)\b/i,
  ],
  genitourinary: [
    /\b(genitourinary|gu\b)\s*[:.]?/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(dysuria|frequency|hematuria|urgency|incontinence|flank pain|vaginal discharge)\b/i,
  ],
  musculoskeletal: [
    /\b(musculoskeletal|msk\b|m\/s\b)\s*[:.]?/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(joint pain|stiffness|swelling|myalgia|arthralgia|back pain)\b/i,
  ],
  integumentary: [
    /\b(integumentary|skin|breast)\s*[:.]?/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(rash|lesion[s]?|pruritus|itching|breast lump|nipple discharge)\b/i,
  ],
  neurological: [
    /\b(neurological|neuro\b|neurologic)\s*[:.]?/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(headache|dizziness|weakness|paresthesias?|numbness|tingling|seizure|loss of consciousness|focal\s+(?:weakness|deficit))\b/i,
  ],
  psychiatric: [
    /\b(psychiatric|psych\b)\s*[:.]?/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(depression|anxiety|suicidal ideation|si\b|hi\b|insomnia|hallucinations|mood)\b/i,
  ],
  endocrine: [
    /\b(endocrine|endo\b)\s*[:.]?/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(polyuria|polydipsia|polyphagia|heat (?:intolerance|sensitivity)|cold (?:intolerance|sensitivity)|tremor)\b/i,
  ],
  hematologicLymphatic: [
    /\b(hematologic|heme\/lymph|heme\b|lymphatic|hematology)\s*[:.]?/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(easy bruising|bleeding|lymphadenopathy|swollen lymph nodes|night sweats)\b/i,
  ],
  allergicImmunologic: [
    /\b(allergic|allergy[\/-]immun|immunologic)\s*[:.]?/i,
    /\b(?:denies|no|negative for|reports? no)\b[^.]{0,80}\b(seasonal symptoms|hives|urticaria|recurrent infections?|allergic reactions?)\b/i,
  ],
};

/** PFSH categories (rubric §3.3). */
export const PFSH_CATEGORIES = ['past', 'family', 'social'] as const;

export type PfshCategory = (typeof PFSH_CATEGORIES)[number];

/** PFSH detection keyword families. Detects explicit prefixes (PMH/FHx/SHx)
 *  AND common content patterns. */
export const PFSH_KEYWORDS: Record<PfshCategory, RegExp[]> = {
  past: [
    /\b(pmh|past medical|past surgical|psh|surgical hx|prior surgeries|prior hospitalizations|chronic illness(?:es)? include|past illnesses?)\b/i,
    /\b(known (?:diabetes|hypertension|copd|chf|asthma|cad|cancer)|h\/o\s+(?:dm|htn|cad|chf|copd|cancer))\b/i,
  ],
  family: [
    /\b(fhx|family history|family hx|f hx|familial)\b/i,
    // father / mother / brother / sister / sibling has/had/with X
    /\b(father|mother|brother|sister|sibling|son|daughter|paternal|maternal|parents?|grandparent[s]?|family member[s]?)\b[^.]{0,40}\b(has|had|with|history|hx|died|deceased|mi\b|stroke|cancer|diabetes|t2dm|cad|chf|htn)\b/i,
  ],
  social: [
    /\b(shx|social history|social hx|sh\b|s hx)\b/i,
    /\b(tobacco|smok(?:er|ing|es?)|cigarette|pack[\s-]years?|pack-yrs|etoh|alcohol|drinks?\/(?:wk|day)|illicit drug|drug use|occupation|works? as|employed|retired|lives? (?:alone|with)|marital|monogamous|sexual(?:ly active)?|exercise|sedentary|diet|nkda|ex-smoker|never smoker)\b/i,
  ],
};

/** 11 exam organ systems (1995 guidelines, rubric §3.4). */
export const EXAM_SYSTEMS = [
  'constitutional',
  'heent',
  'cardiovascular',
  'respiratory',
  'gastrointestinal',
  'genitourinary',
  'musculoskeletal',
  'skin',
  'neurologic',
  'psychiatric',
  'hematologicLymphaticImmunologic',
] as const;

export type ExamSystem = (typeof EXAM_SYSTEMS)[number];

/** Exam-system detection — applied to the Objective body. Matches a
 *  system label OR a vital-sign/exam-finding fingerprint. */
export const EXAM_KEYWORDS: Record<ExamSystem, RegExp[]> = {
  constitutional: [
    /\b(constitutional|gen\b|general|vs\s*:|vitals?\s*:?|vital signs?)\b/i,
    /\b(bp\s*\d+\/\d+|hr\s*\d+|t\s*\d+|spo2\s*\d+|temp\s*\d+|nad\b|well[\s-]appearing|tired-?appearing|anxious-?appearing|alert)\b/i,
  ],
  heent: [
    /\b(heent|head and neck|head, eyes|ent\b|hemmt)\b/i,
    /\b(tms?\s+(?:clear|intact|bulging)|pharyng(?:eal|itis)|conjunctivae?|sclerae?|fundi|jvd|mucous membranes|oropharynx|tympanic|nares?|nasal mucosa|posterior pharynx)\b/i,
  ],
  cardiovascular: [
    /\b(cardiac|cardiovascular|cv\b|heart)\s*[:.]?/i,
    /\b(rrr\b|s1\s*s2|s3\b|s4\b|murmur|m\/r\/g|gallop|click|jvd|pulses\s+\d\+|distal pulses|peripheral pulses|carotid|bruit)\b/i,
  ],
  respiratory: [
    /\b(lungs?|respiratory|resp\b|pulm)\s*[:.]?/i,
    /\b(ctab|clear to auscultation|crackles|rales|rhonchi|wheez(?:e|ing|ed)|breath sounds|diminished breath|bibasilar)\b/i,
  ],
  gastrointestinal: [
    /\b(abdomen|abdominal|gi\b)\s*[:.]?/i,
    /\b(soft|tender(?:ness)?|nt\b|nd\b|distended|bowel sounds|rebound|guarding|hsm\b|hepatomegaly|splenomegaly|suprapubic tenderness|cva tenderness)\b/i,
  ],
  genitourinary: [
    /\b(genitourinary|gu\b|pelvic|gyn|genital)\s*[:.]?/i,
    /\b(cervix|adnexa|uterus|prostate|testes|inguinal|hernia|bladder)\b/i,
  ],
  musculoskeletal: [
    /\b(musculoskeletal|msk\b|extremit(?:y|ies)|m\/s\b)\s*[:.]?/i,
    /\b(rom\b|range of motion|joint|tender(?:ness)? to palpation|swelling|edema(?:\s+\d\+)?|deformity|crepitus|monofilament|gait|distal pulses)\b/i,
  ],
  skin: [
    /\b(skin|integumentary|dermatologic)\s*[:.]?/i,
    /\b(rash|lesion|erythema|cyanosis|jaundice|pallor|petechiae|abrasion|ecchymosis|dry|moist)\b/i,
  ],
  neurologic: [
    /\b(neuro(?:logic)?|cn\b|cranial nerves?)\s*[:.]?/i,
    /\b(a&o(?:×|x)\s*\d|alert and oriented|cn\s*[ivx]+|reflexes\s+\d\+|focal (?:deficits?|weakness)|motor strength|sensation intact|gait normal|dysmetria|monofilament intact)\b/i,
  ],
  psychiatric: [
    /\b(psychiatric|psych\b|mental status)\s*[:.]?/i,
    /\b(mood (?:appropriate|euthymic|depressed)|affect|insight|judgment|thought process|cooperative|appropriate behavior)\b/i,
  ],
  hematologicLymphaticImmunologic: [
    /\b(heme[\s\/-]?lymph|lymphatic|lymph nodes?|hematologic|immunologic)\s*[:.]?/i,
    /\b(no\s+lymphadenopathy|cervical lymph|axillary lymph|inguinal lymph|spleen)\b/i,
  ],
};

// ============================================================================
// 4. Time-based hint patterns (rubric §3.5)
// ============================================================================

/** Patterns that match an explicit total-time mention in SOAP body. */
export const TIME_HINT_PATTERNS: RegExp[] = [
  /visit time\s*:\s*(\d{1,3})\s*(?:min|minutes)/i,
  /total time(?:\s+spent)?\s*:\s*(\d{1,3})\s*(?:min|minutes)/i,
  /counseling\s+(?:and\s+coordination\s+of\s+care)?\s*:\s*(\d{1,3})\s*(?:min|minutes)/i,
  /time spent\s*:\s*(\d{1,3})\s*(?:min|minutes)/i,
];

// ============================================================================
// 5. Fallback heuristic helpers (rubric §4.4)
// ============================================================================

/** Chronic-disease ICD-10 prefix list — used only by the fallback heuristic. */
export const CHRONIC_ICD_PREFIXES = [
  'E10', 'E11', // diabetes
  'I10', 'I11', 'I12', 'I13', 'I15', // hypertension
  'I25', 'I50', // CAD / CHF
  'J44', 'J45', // COPD / asthma
  'N18', // CKD
  'E78', // hyperlipidemia
  'F32', 'F33', 'F41', // depression / anxiety
  'M05', 'M06', 'M15', 'M19', // RA / OA
  'C', // any cancer code
  'K70', 'K74', // chronic liver
  'G35', // MS
];

/** Acute-systemic markers (rubric §4.4 fallback). Each is a
 *  POSITIVE-context pattern; "no exacerbation" / "denies worsening"
 *  do NOT fire. Use fixed-width negative lookbehinds — keep entries
 *  precise to avoid inflating problem tier. */
export const SYSTEMIC_SX_PATTERNS: RegExp[] = [
  /(?<!denies\s)(?<!no\s)\bsystemic\s+(?:symptoms|sx|signs)\b/i,
  // "fever 101.2" or higher.
  /\bfebrile\b|\bfever\s+(?:to\s+)?\d{3}/i,
  /(?<!denies\s)(?<!no\s)\bsepsis\b/i,
  /(?<!denies\s)\bhyperglycemic crisis\b/i,
  /(?<!denies\s)(?<!no\s)\bdiabetic ketoacidosis\b/i,
  /(?<!no\s)(?<!resolving\s)(?<!resolved\s)(?<!denies\s)\b(?:acute on chronic\s+)?(?:chf|copd|asthma|dm|t2dm|cad)\s+exacerbation\b/i,
  /(?<!no\s)(?<!resolving\s)\b(?:progressive\s+)?(?:worsening|deterioration)\b/i,
];

/** Hospitalization-decision regex (rubric §4.4 fallback risk floor). */
export const HOSPITALIZATION_PATTERNS: RegExp[] = [
  /\bhospitaliz(ation|e|ed)\b/i,
  /\badmission\b|\badmit(?:ted)?\b/i,
  /\bdecision (?:not )?to (?:hospitalize|admit)/i,
  /\bdefer admission\b/i,
  /\bout(?:patient)? (?:diuresis|management).{0,30}vs\.?\s*admi/i,
];

/** Life-threat regex (rubric §4.4 fallback problems-high). Each
 *  pattern requires a POSITIVE context — "denies suicidal ideation" and
 *  "no acute distress" must NOT trip the high-problems escalation. We
 *  achieve this with a fixed-width negative lookbehind on common
 *  negation prefixes.
 *
 *  IMPORTANT: keep these focused on TRUE life-threat language. The
 *  scoring engine relies on these to be precise — false positives
 *  inflate the MDM tier. */
export const LIFE_THREAT_PATTERNS: RegExp[] = [
  /(?<!denies\s)(?<!no\s)(?<!negative for\s)\bthreat to (?:life|bodily function)\b/i,
  /(?<!denies\s)(?<!no\s)\bsevere exacerbation\b/i,
  // Active SI ("active", "endorses", or unprefixed); never on "denies SI".
  /(?:active|endorses|reports|with)\s+suicidal ideation\b/i,
  /\bstemi\b|\bnstemi\b/i,
  /(?<!no\s)(?<!resolved\s)\bdecompensated?\s+(?:chf|heart failure|copd)\b/i,
  // Acute on chronic CHF/COPD/etc with exacerbation + clinical decline
  // markers — captures fixture 22's "acute on chronic systolic CHF
  // exacerbation" clearly.
  /\bacute on chronic\b[^.]{0,40}\b(?:exacerbation|failure|crisis)\b/i,
  /\bhfre?f\s+(?:exacerbation|crisis)\b/i,
  /\bchf\s+(?:requiring (?:admission|hospitalization)|exacerbation\s+(?:requiring|w\/|with)\s+(?:admit|hospital))/i,
  /\bcardiac arrest\b/i,
  /(?<!denies\s)(?<!no\s)\bsepsis\b/i,
  /(?<!denies\s)\bhyperglycemic crisis\b/i,
  /(?<!denies\s)(?<!no\s)\b(?:dka|diabetic ketoacidosis)\b/i,
  // T2DM with severe metabolic derangement — fixture 21's "hyperglycemic
  // crisis trajectory" + A1c 11.4% indicates threat to bodily function.
  /\b(?:hyperglycemic\s+(?:crisis|emergency))\b/i,
  /\b(?:a1c|hba1c)\s+(?:1[1-9]|2\d)\b/i, // A1c ≥ 11
  /\bdo not resuscitate\b/i,
  // Hospitalization decision is a high-risk + high-problem marker.
  /\b(?:decision (?:not )?to (?:hospitalize|admit)|defer admission|admission\s+vs\.?|outpatient\s+(?:management|diuresis)\s+vs\.?\s+admi)/i,
];

/** Labs / imaging mention regex (rubric §4.4 fallback data). Each
 *  pattern must show a CLINICAL ACT around the test name — ordered,
 *  reviewed, performed, sent, today — NOT a passing reference like
 *  "no labs needed" or "BMP within 6 months". */
export const LABS_IMAGING_PATTERNS: RegExp[] = [
  // Lab name with explicit clinical action (ordered/reviewed/sent/today/etc.).
  /\b(cbc|bmp|cmp|tsh|a1c|hba1c|lipid panel|urinalysis|troponin|bnp|pt\/ptt|inr|ldh|esr|crp|d-dimer)\b\s*(?:[:.]|—)\s*(?:[^.]{0,80}?\b(?:reviewed|ordered|sent|drawn|positive|negative|elevated|normal|stable|pending))/i,
  // Lab "today" / "in office" / "in-office" / "POC" — direct sample of the test.
  /\b(?:cbc|bmp|cmp|tsh|a1c|hba1c|lipid panel|urinalysis|troponin|bnp|d-dimer|fingerstick|ua)\b[^.]{0,30}\b(?:in[- ]?office|today\b|today's|sent|ordered|drawn)\b/i,
  // Imaging name immediately followed by action / result.
  /\b(ekg|ecg|cxr|chest x-?ray|ct scan|mri|ultrasound|x-ray|echocardiogram|stress test)\b[^.]{0,40}\b(?:reviewed|ordered|performed|today|in office|in the office|negative|positive|normal|abnormal|\bshows?\b|stable|nsr)/i,
  // Verb-led ordering language ("ordered labs", "review of test results").
  /\b(?:reviewed|review of|ordered|order|sent|performed|interpreted)\b[^.]{0,40}\b(labs?|test\s+results?|results?|imaging|study|studies|prior records?|external (?:notes?|records?)|cardiology (?:notes?|consult|echo))/i,
  // Result-shape: numeric results following lab name (e.g. "BMP: Cr 1.4").
  /\b(?:bmp|cmp|cbc|lipid panel|a1c|hba1c|tsh|troponin|bnp)\s*[:.]\s*[A-Za-z][^.]{0,50}\d/i,
  // Common in-office point-of-care tests.
  /\bua\s+(?:in[- ]?office|today|positive|negative|confirms)/i,
  /\bpoc\s+(?:fingerstick|glucose)\b/i,
  // EKG / CXR results in narrative ("EKG today shows", "CXR shows").
  /\b(?:ekg|ecg|cxr|x-ray|ct|mri)\b[^.]{0,30}\b(?:today|shows?|reveal|in[- ]?office|reviewed)/i,
];

/** Additional sanity: "decision regarding" / parenteral controlled. */
export const HIGH_RISK_PATTERNS: RegExp[] = [
  /\bparenteral controlled substance\b/i,
  /\bdrug therapy requiring intensive monitoring\b/i,
  /\bemergency major surgery\b/i,
  /\bdecision (?:re|regarding) (?:emergency|elective major) surgery\b/i,
  /\bde-?escalat(e|ion) of care\b/i,
  /\bdo not resuscitate\b|\bdnr\b/i,
];
