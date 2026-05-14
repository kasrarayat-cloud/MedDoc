// ============================================================================
// ISMP confused-drug-names safety floor (2026-05-13 — Issues #202 + #206 PR-2)
// ----------------------------------------------------------------------------
// Source: ISMP List of Confused Drug Names, June 2024 edition.
//   - Landing: https://home.ecri.org/blogs/ismp-resources/list-of-confused-drug-names
//   - PDF: https://online.ecri.org/hubfs/ISMP/Resources/ISMP_ConfusedDrugNames.pdf
//
// ISMP's stated methodology: each pair derives from a published case
// in ISMP Medication Safety Alert! Acute Care, ISMP Medication
// Safety Alert! Community/Ambulatory Care, or the FDA/ISMP Tall Man
// Letter list — i.e. every pair represents at least one real
// reported confusion event.
//
// QuillMD-specific curation: ~42 pairs filtered to QuillMD's
// specialty wedge (endocrine + weight management + bariatrics +
// primary care + ob_gyn + functional medicine + psychiatry + pain
// management). The ~700-pair full ISMP list is too dilutive to send
// wholesale; this curated subset goes into the keyterm builder's
// safety-floor layer and rides on EVERY visit regardless of
// specialty.
//
// SEED CASE — Issue #206: Implanon → insulin
// ---------------------------------------------
// Not in the ISMP 2024 list. This is a TTS/ASR phonetic artifact
// unique to dictation pipelines, not historical pharmacy literature.
// Both names have 3 syllables and live in the same medication-context
// prosody; ASR substitutes one for the other in continuous speech.
// Documented internally (Issue #206) and surfaced via post-deploy
// audit; worth submitting to ISMP for the next list update.
//
// Wire-in: passed to `buildKeytermsForVisit({ safetyFloor: ... })`
// from L1 + L1b. Builder gives this layer first-occurrence-wins
// precedence in the dedupe so the audit row correctly attributes
// hits to "safetyFloor" rather than a specialty bundle.
//
// Sources cited per pair:
//   - ISMP: ISMP List of Confused Drug Names, June 2024
//   - FDA-TML: FDA/ISMP Tall Man Letter list
//   - Issue #206: internal QuillMD observation
//   - PT: Pharmacy Times, https://www.pharmacytimes.com/view/2005-08-9751
// ============================================================================

export interface ConfusedDrugPair {
  /** Canonical name to boost. Cased as Deepgram should see it. */
  primary: string;
  /** Alternatives known to be misheard. Boosting `primary` is the
   *  defensive bias; these are listed so audit attribution can
   *  correlate a regression to the cluster. */
  confusedWith: string[];
  /** Why this pair matters (ISMP citation OR phonetic note). */
  rationale: string;
  /** Severity: high = cross-class substitution (insulin vs implant);
   *  medium = within-class (Ozempic vs Mounjaro); low = spelling/
   *  formulation variant. */
  severity: 'high' | 'medium' | 'low';
  /** 1–5 boost preference. The keyterm builder doesn't have per-term
   *  weighting (Deepgram's keyterm API is unweighted today), but
   *  this signal is preserved for future tuning + audit/forensics. */
  boostWeight: number;
}

/** Curated 42-pair list. Order is by clinical priority (high
 *  severity first), not alphabetical. Sources cited inline. */
export const CONFUSED_DRUG_NAMES: readonly ConfusedDrugPair[] = [
  // ─── Endocrine — Insulin family (high-volume, narrow TI) ──────
  {
    primary: 'Lantus',
    confusedWith: ['Latuda', 'Lente'],
    rationale: 'ISMP 2024: Lantus↔Latuda (antipsychotic, wrong-class).',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'Levemir',
    confusedWith: ['Lovenox'],
    rationale: 'ISMP 2024: Levemir↔Lovenox (insulin vs LMWH — wrong-class, both SC injections).',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'Tresiba',
    confusedWith: ['Toujeo', 'Tradjenta', 'Trulicity', 'Tanzeum', 'Tarceva'],
    rationale: 'ISMP 2024: Tresiba listed as confused with all four other T-named diabetes meds plus Tarceva (oncology).',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'Toujeo',
    confusedWith: ['Tresiba', 'Tradjenta', 'Trulicity', 'Tanzeum'],
    rationale: 'ISMP 2024. Toujeo = U-300 glargine; Tresiba = degludec; substitution changes pharmacokinetics significantly.',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'Humalog',
    confusedWith: ['Humulin', 'Novolog', 'Humira'],
    rationale: 'ISMP 2024: HumaLOG↔HumuLIN, HumaLOG↔NovoLOG, HumaLOG↔Humira Pen (immunosuppressant — wrong-class).',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'Humulin',
    confusedWith: ['Humalog', 'Humira'],
    rationale: 'ISMP 2024.',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'Novolog',
    confusedWith: ['Novolin', 'Humalog'],
    rationale: 'ISMP 2024.',
    severity: 'high',
    boostWeight: 5,
  },

  // ─── Endocrine — T-cluster + DPP-4 (ISMP highest-density cluster) ──
  {
    primary: 'Trulicity',
    confusedWith: ['Tradjenta', 'Toujeo', 'Tresiba', 'Tanzeum'],
    rationale: 'ISMP 2024: 4-way confused cluster of T-named diabetes meds.',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'Tradjenta',
    confusedWith: ['Trulicity', 'Toujeo', 'Tresiba'],
    rationale: 'ISMP 2024. DPP-4 (linagliptin); Toujeo/Tresiba are basal insulins — wrong-class.',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'Januvia',
    confusedWith: ['Janumet', 'Jantoven', 'Enjuvia'],
    rationale: 'ISMP 2024. Januvia↔Jantoven is sitagliptin↔warfarin — catastrophic wrong-class.',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'sitagliptin',
    confusedWith: ['saxagliptin', 'sumatriptan'],
    rationale: 'ISMP 2024: within-class DPP-4 + SUMAtriptan (migraine — wrong-class).',
    severity: 'medium',
    boostWeight: 4,
  },
  {
    primary: 'linagliptin',
    confusedWith: ['linaclotide'],
    rationale: 'ISMP 2024: DPP-4 vs IBS-C — wrong-class.',
    severity: 'medium',
    boostWeight: 3,
  },

  // ─── GLP-1 brand confusion (not yet in ISMP; documented elsewhere) ──
  {
    primary: 'Ozempic',
    confusedWith: ['Wegovy', 'Mounjaro', 'Zepbound', 'Rybelsus'],
    rationale: 'Ozempic+Wegovy=semaglutide; Mounjaro+Zepbound=tirzepatide. PT + FDA counterfeit alerts.',
    severity: 'medium',
    boostWeight: 5,
  },
  {
    primary: 'Wegovy',
    confusedWith: ['Ozempic', 'Mounjaro', 'Zepbound'],
    rationale: 'Same molecule as Ozempic; weight-management brand of semaglutide.',
    severity: 'medium',
    boostWeight: 5,
  },
  {
    primary: 'Mounjaro',
    confusedWith: ['Zepbound', 'Ozempic', 'Wegovy', 'Trulicity'],
    rationale: 'Mounjaro/Zepbound = tirzepatide; "Mounjaro/Trulicity" co-marketed Lilly GLP-1s.',
    severity: 'medium',
    boostWeight: 5,
  },
  {
    primary: 'Zepbound',
    confusedWith: ['Mounjaro', 'Ozempic', 'Wegovy'],
    rationale: 'Tirzepatide weight-management brand.',
    severity: 'medium',
    boostWeight: 5,
  },
  {
    primary: 'Rybelsus',
    confusedWith: ['Ozempic'],
    rationale: 'Oral semaglutide; same molecule, different formulation.',
    severity: 'low',
    boostWeight: 3,
  },

  // ─── Endocrine — Diabetes orals + adjacent ──────────────────
  {
    primary: 'metformin',
    confusedWith: ['metronidazole', 'metoprolol'],
    rationale: 'ISMP 2024: metFORMIN↔metroNIDAZOLE. metFORMIN↔metoprolol is canonical TTS-collision example.',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'metoprolol',
    confusedWith: ['metformin', 'metolazone'],
    rationale: 'ISMP 2024: succinate↔tartrate formulation. Plus metoprolol↔metformin (heart vs diabetes).',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'glipizide',
    confusedWith: ['glyburide'],
    rationale: 'ISMP 2024. Both sulfonylureas, similar dosing but different potency/duration.',
    severity: 'medium',
    boostWeight: 4,
  },

  // ─── Weight management / bariatric ──────────────────────────
  {
    primary: 'Fastin',
    confusedWith: ['phentermine'],
    rationale: 'ISMP 2024: Same brand name across Rx phentermine and OTC supplement — same string, different molecule.',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'phentermine',
    confusedWith: ['phentolamine', 'fenofibrate'],
    rationale: 'Phonetic collision: phen-TER-meen / phen-TOL-a-meen. FDA pharmacy-error literature.',
    severity: 'medium',
    boostWeight: 4,
  },
  {
    primary: 'bupropion',
    confusedWith: ['buspirone'],
    rationale: 'ISMP 2024: antidepressant/smoking-cessation (and half of Contrave) vs anxiolytic.',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'naltrexone',
    confusedWith: ['naloxone', 'methylnaltrexone'],
    rationale: 'FDA Tall Man Letter. Naloxone (Narcan, acute reversal) vs naltrexone (chronic antagonist + Contrave).',
    severity: 'high',
    boostWeight: 5,
  },

  // ─── OB-GYN: contraceptive implants (Issue #206 SEED CASE) ──
  {
    primary: 'Nexplanon',
    confusedWith: ['Implanon', 'insulin'],
    rationale: 'Issue #206: ASR transcribes "Nexplanon/Implanon" as "insulin" in continuous speech — 3-syllable cadence + medication context. Cross-class substitution is catastrophic (contraceptive vs antidiabetic).',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'Implanon',
    confusedWith: ['Nexplanon', 'insulin'],
    rationale: 'Issue #206 seed case. ASR /ɪm-PLAN-on/ ↔ /IN-suh-lin/.',
    severity: 'high',
    boostWeight: 5,
  },

  // ─── Thyroid (Functional Medicine) ─────────────────────────
  {
    primary: 'levothyroxine',
    confusedWith: ['liothyronine', 'lamotrigine', 'Lanoxin'],
    rationale: 'ISMP 2024: T4 vs T3 (wrong potency by 4×), vs anticonvulsant, vs digoxin (narrow TI).',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'liothyronine',
    confusedWith: ['levothyroxine'],
    rationale: 'ISMP 2024. T3 vs T4 — same gland target, very different dosing.',
    severity: 'high',
    boostWeight: 5,
  },

  // ─── Steroids (Primary Care + Bariatric body-comp DEXA cont.) ──
  {
    primary: 'prednisone',
    confusedWith: ['prednisolone', 'methylprednisolone'],
    rationale: 'ISMP 2024: predniSONE↔prednisoLONE. Phonetically near-identical; different metabolic activation.',
    severity: 'medium',
    boostWeight: 5,
  },
  {
    primary: 'methylprednisolone',
    confusedWith: ['medroxyprogesterone', 'methyltestosterone', 'prednisolone'],
    rationale: 'ISMP 2024: methylPREDNISolone↔medroxyPROGESTERone (steroid vs hormone — wrong-class).',
    severity: 'high',
    boostWeight: 4,
  },
  {
    primary: 'dexamethasone',
    confusedWith: ['dexmedetomidine'],
    rationale: 'ISMP 2024: dexAMETHasone↔dexmedeTOMIDine. ICU sedative vs steroid. "DEXA" prefix collides with body-comp DEXA scans in bariatric notes.',
    severity: 'high',
    boostWeight: 4,
  },

  // ─── Anticoagulants (primary care + vascular) ───────────────
  {
    primary: 'heparin',
    confusedWith: ['Hespan'],
    rationale: 'ISMP 2024: heparin↔Hespan (plasma volume expander).',
    severity: 'high',
    boostWeight: 4,
  },
  {
    primary: 'Coumadin',
    confusedWith: ['Cardura', 'Avandia'],
    rationale: 'ISMP 2024: vs alpha-blocker, vs TZD diabetes.',
    severity: 'high',
    boostWeight: 4,
  },
  {
    primary: 'Jantoven',
    confusedWith: ['Janumet', 'Januvia'],
    rationale: 'ISMP 2024: Jantoven (warfarin brand)↔Janumet/Januvia. Anticoagulant vs antidiabetic — catastrophic wrong-class.',
    severity: 'high',
    boostWeight: 5,
  },

  // ─── Antidepressants / Psych ────────────────────────────────
  {
    primary: 'Celexa',
    confusedWith: ['Celebrex', 'Cerebyx', 'Zyprexa'],
    rationale: 'ISMP 2024: 4-way wrong-class cluster. Celexa (SSRI) ↔ Celebrex (NSAID) ↔ Cerebyx (anticonvulsant) ↔ Zyprexa (antipsychotic).',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'duloxetine',
    confusedWith: ['fluoxetine', 'paroxetine'],
    rationale: 'ISMP 2024: within-class SNRI/SSRI substitutions.',
    severity: 'medium',
    boostWeight: 4,
  },
  {
    primary: 'Lexapro',
    confusedWith: ['Loxitane'],
    rationale: 'ISMP 2024: SSRI vs typical antipsychotic — wrong-class.',
    severity: 'high',
    boostWeight: 3,
  },
  {
    primary: 'Cymbalta',
    confusedWith: ['Symbyax'],
    rationale: 'ISMP 2024: SNRI vs olanzapine+fluoxetine combo.',
    severity: 'medium',
    boostWeight: 3,
  },
  {
    primary: 'sertraline',
    confusedWith: ['cetirizine'],
    rationale: 'ISMP 2024: SSRI vs antihistamine — wrong-class. /SER-truh-leen/ vs /se-TEER-uh-zeen/.',
    severity: 'high',
    boostWeight: 4,
  },

  // ─── Pain meds (pain_management + primary care) ─────────────
  {
    primary: 'tramadol',
    confusedWith: ['trazodone'],
    rationale: 'ISMP 2024 — canonical sound-alike pair. Opioid vs antidepressant. Both 3-syllable, both T-r-a opening.',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'hydroxyzine',
    confusedWith: ['hydralazine', 'hydrochlorothiazide', 'hydroxyurea', 'hydromorphone'],
    rationale: 'ISMP 2024: 5-way cluster, all wrong-class (anti-emetic vs vasodilator vs diuretic vs chemo vs opioid).',
    severity: 'high',
    boostWeight: 5,
  },
  {
    primary: 'oxycodone',
    confusedWith: ['OxyContin', 'oxybutynin', 'hydrocodone', 'oxymorphone'],
    rationale: 'ISMP 2024: oxyCODONE↔HYDROcodone↔OxyCONTIN↔oxyMORphone↔oxyBUTYnin (bladder — wrong-class).',
    severity: 'high',
    boostWeight: 4,
  },

  // ─── Primary-care cluster (collide with diabetes meds) ──────
  {
    primary: 'amlodipine',
    confusedWith: ['amiloride'],
    rationale: 'ISMP 2024: amLODIPine↔aMILoride (CCB vs K+-sparing diuretic).',
    severity: 'medium',
    boostWeight: 3,
  },
  {
    primary: 'atorvastatin',
    confusedWith: ['atomoxetine'],
    rationale: 'ISMP 2024: statin vs ADHD med — wrong-class.',
    severity: 'high',
    boostWeight: 3,
  },
];

/** Flat list of CANONICAL PRIMARIES (no `confusedWith` alternatives)
 *  — passed to the keyterm builder's `safetyFloor` parameter. Why
 *  primaries only (rather than primary + alternatives)?
 *
 *  1. Token budget. Boosting both sides of every pair would push the
 *     flat list to ~90+ names = ~280 tokens. Combined with CORE
 *     (~200 tokens) + specialty (~85 tokens) that exceeded the
 *     Deepgram 500-token cap, forcing the builder to silently drop
 *     the specialty layer (regression caught in PR-2 audit, 2026-05-13).
 *
 *  2. Asymmetric value. The "primary" is the term we want correctly
 *     transcribed; biasing it raises its prior. The `confusedWith`
 *     alternatives are what Deepgram tends to OUTPUT instead — they
 *     don't need a higher prior since they're already its default
 *     guess. The structured `ConfusedDrugPair[]` keeps the
 *     `confusedWith` data for audit/forensics + future tooling that
 *     wants to surface "this primary's known collisions."
 *
 *  Net: ~44 primaries × ~3.5 tokens ≈ 150 tokens for the safety
 *  floor. Leaves headroom for CORE + specialty + patient context. */
export const CONFUSED_DRUG_NAMES_FLAT: readonly string[] = Array.from(
  new Set<string>(CONFUSED_DRUG_NAMES.map((p) => p.primary)),
);
