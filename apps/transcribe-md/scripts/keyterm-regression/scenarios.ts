// ============================================================================
// Keyterm regression scenarios — Issues #202 + #206 PR-3
// ----------------------------------------------------------------------------
// One scenario per HIGH-SEVERITY primary in the ISMP confused-drug-names
// safety floor (apps/transcribe-md/src/lib/confused-drug-names.ts). Each
// scenario is a short doctor-dictation script that uses the target
// medication in plausible clinical context, plus the alternatives we
// want to verify are NOT substituted in.
//
// The scenarios feed two scripts:
//   1. synthesize.ts — OpenAI tts-1 ("onyx" voice) → MP3 cached at
//      .local/keyterm-regression-audio/{tag}.mp3
//   2. run.ts — for each cached MP3: buildKeytermsForVisit() + direct
//      Deepgram batch call + transcript assertion + baseline report.
//
// Scope: HIGH severity only (31 entries). Medium/low pairs are out of
// scope for the regression baseline — they are still in the safety
// floor data file and benefit from the boost; they just don't have a
// dedicated TTS fixture here.
//
// Each script targets ~25-40 words / ~150-250 characters of synthesized
// audio (10-15 seconds at TTS speed=1.0). Long enough to give Deepgram
// real prosody context; short enough to keep API cost down. Voice:
// onyx, the deep deliberate voice used by the cross-input-mode runner,
// which sounds plausibly like a doctor dictating.
// ============================================================================

import type { SpecialtyKey } from '@/lib/specialty-keys';

export interface KeytermRegressionScenario {
  /** Short kebab-case ID; also the audio filename. */
  tag: string;
  /** Target medication name. The transcript MUST contain this term
   *  (case-insensitive) for the scenario to pass. */
  primary: string;
  /** Alternative names Deepgram tends to substitute when the bias is
   *  not applied. Tracked for the report — appearance is not a hard
   *  fail (a clinician might also say the alternative), but it
   *  weakens the signal. */
  confusedWith: readonly string[];
  /** Specialty key (per `@/lib/specialty-keys.ts`). The keyterm
   *  builder loads this specialty's bundle alongside the safety
   *  floor — exercising both layers per scenario. */
  specialty: SpecialtyKey;
  /** TTS script. Single doctor speaking, no patient turn. */
  dictation: string;
}

export const KEYTERM_REGRESSION_SCENARIOS: readonly KeytermRegressionScenario[] = [
  // ─── Insulin family (Endocrinology) ───────────────────────────
  {
    tag: 'lantus',
    primary: 'Lantus',
    confusedWith: ['Latuda', 'Lente'],
    specialty: 'endocrinology',
    dictation:
      'Patient on Lantus thirty units at bedtime. Fasting glucose still running in the one-fifties. Increasing Lantus to thirty-six units nightly and rechecking A1C in three months.',
  },
  {
    tag: 'levemir',
    primary: 'Levemir',
    confusedWith: ['Lovenox'],
    specialty: 'endocrinology',
    dictation:
      'She is currently on Levemir twenty-two units twice daily. Morning hypoglycemia at three a.m. Plan to drop the evening Levemir dose to eighteen units and reassess.',
  },
  {
    tag: 'tresiba',
    primary: 'Tresiba',
    confusedWith: ['Toujeo', 'Tradjenta', 'Trulicity', 'Tanzeum', 'Tarceva'],
    specialty: 'endocrinology',
    dictation:
      'Transitioning from Lantus to Tresiba forty units daily. Tresiba has a flatter pharmacokinetic profile which should reduce nocturnal hypoglycemia. Will follow up in six weeks.',
  },
  {
    tag: 'toujeo',
    primary: 'Toujeo',
    confusedWith: ['Tresiba', 'Tradjenta', 'Trulicity', 'Tanzeum'],
    specialty: 'endocrinology',
    dictation:
      'Starting Toujeo U-three-hundred at thirty units in the morning. Toujeo is more concentrated than standard glargine so the injection volume is smaller. Counseling provided.',
  },
  {
    tag: 'humalog',
    primary: 'Humalog',
    confusedWith: ['Humulin', 'Novolog', 'Humira'],
    specialty: 'endocrinology',
    dictation:
      'Carb ratio one-to-twelve with Humalog at meals. Patient using ten units of Humalog at lunch consistently. Postprandial readings have come down nicely. Continue current regimen.',
  },
  {
    tag: 'humulin',
    primary: 'Humulin',
    confusedWith: ['Humalog', 'Humira'],
    specialty: 'endocrinology',
    dictation:
      'Switching her to Humulin R for the U-five-hundred concentration given the daily insulin requirement of over two hundred units. Humulin U-five-hundred dosing reviewed with patient.',
  },
  {
    tag: 'novolog',
    primary: 'Novolog',
    confusedWith: ['Novolin', 'Humalog'],
    specialty: 'endocrinology',
    dictation:
      'Novolog FlexPen prescribed for mealtime coverage. One unit per ten grams of carbohydrate with a correction factor of one to fifty. Will reassess Novolog dosing at next visit.',
  },

  // ─── T-cluster + DPP-4 (Endocrinology) ────────────────────────
  {
    tag: 'trulicity',
    primary: 'Trulicity',
    confusedWith: ['Tradjenta', 'Toujeo', 'Tresiba', 'Tanzeum'],
    specialty: 'endocrinology',
    dictation:
      'Starting Trulicity zero point seventy-five milligrams subcutaneously once weekly. Counseled on injection technique and expected GI side effects. Plan to titrate Trulicity to one point five in one month.',
  },
  {
    tag: 'tradjenta',
    primary: 'Tradjenta',
    confusedWith: ['Trulicity', 'Toujeo', 'Tresiba'],
    specialty: 'endocrinology',
    dictation:
      'Adding Tradjenta five milligrams daily to her metformin regimen. Tradjenta is renally safe at her current eGFR. Will recheck A1C and metabolic panel in three months.',
  },
  {
    tag: 'januvia',
    primary: 'Januvia',
    confusedWith: ['Janumet', 'Jantoven', 'Enjuvia'],
    specialty: 'endocrinology',
    dictation:
      'Continuing Januvia one hundred milligrams daily. A1C improved from eight point two to seven point one on this regimen. Patient tolerating Januvia well with no hypoglycemia reported.',
  },

  // ─── Diabetes orals + cardio adjacents (Primary Care) ─────────
  {
    tag: 'metformin',
    primary: 'metformin',
    confusedWith: ['metronidazole', 'metoprolol'],
    specialty: 'primary_care',
    dictation:
      'Increasing metformin from five hundred milligrams twice daily to one thousand milligrams twice daily. She has tolerated metformin without GI symptoms for the past three months.',
  },
  {
    tag: 'metoprolol',
    primary: 'metoprolol',
    confusedWith: ['metformin', 'metolazone'],
    specialty: 'primary_care',
    dictation:
      'Continuing metoprolol succinate fifty milligrams daily. Resting heart rate in the high sixties on this dose. Metoprolol is providing adequate rate control after the AFib episode last spring.',
  },

  // ─── Weight management / bariatric ────────────────────────────
  {
    tag: 'fastin',
    primary: 'Fastin',
    confusedWith: ['phentermine'],
    specialty: 'weight_management',
    dictation:
      'Patient asking about Fastin specifically. Clarified that prescription Fastin is phentermine hydrochloride, and the OTC Fastin sold in supplement stores contains different ingredients entirely.',
  },
  {
    tag: 'bupropion',
    primary: 'bupropion',
    confusedWith: ['buspirone'],
    specialty: 'weight_management',
    dictation:
      'Starting bupropion SR one hundred fifty milligrams in the morning as part of the Contrave combination. Bupropion has dual indications for smoking cessation and weight management which fits her goals.',
  },
  {
    tag: 'naltrexone',
    primary: 'naltrexone',
    confusedWith: ['naloxone', 'methylnaltrexone'],
    specialty: 'weight_management',
    dictation:
      'Adding low-dose naltrexone four point five milligrams nightly. Naltrexone is the opioid antagonist component of Contrave but at this dose it functions as an immune modulator. Confirmed no opioid use.',
  },

  // ─── OB-GYN contraceptive implants (Issue #206 SEED CASE) ─────
  {
    tag: 'nexplanon',
    primary: 'Nexplanon',
    confusedWith: ['Implanon', 'insulin'],
    specialty: 'ob_gyn',
    dictation:
      'Patient here for Nexplanon insertion. She has had a Nexplanon previously without complication and is requesting reinsertion. Sterile technique reviewed and Nexplanon placed in the non-dominant upper arm.',
  },
  {
    tag: 'implanon',
    primary: 'Implanon',
    confusedWith: ['Nexplanon', 'insulin'],
    specialty: 'ob_gyn',
    dictation:
      'Patient is here to discuss her Implanon. The Implanon was placed three years ago by her previous provider and she would like to discuss removal versus replacement with a newer Nexplanon device.',
  },

  // ─── Thyroid (Endocrinology + Functional Medicine) ────────────
  {
    tag: 'levothyroxine',
    primary: 'levothyroxine',
    confusedWith: ['liothyronine', 'lamotrigine', 'Lanoxin'],
    specialty: 'endocrinology',
    dictation:
      'TSH up to seven point eight on her current levothyroxine dose. Increasing levothyroxine from seventy-five micrograms to eighty-eight micrograms daily. Recheck TSH and free T4 in six weeks.',
  },
  {
    tag: 'liothyronine',
    primary: 'liothyronine',
    confusedWith: ['levothyroxine'],
    specialty: 'functional_medicine',
    dictation:
      'Adding liothyronine five micrograms daily to her current levothyroxine. Reverse T3 was elevated on her recent panel and she has continued fatigue symptoms despite a normal TSH on levothyroxine monotherapy.',
  },

  // ─── Steroids (Primary Care + Pain) ───────────────────────────
  {
    tag: 'prednisone',
    primary: 'prednisone',
    confusedWith: ['prednisolone', 'methylprednisolone'],
    specialty: 'primary_care',
    dictation:
      'Starting prednisone forty milligrams daily for five days then tapering by ten milligrams every three days. Counseled on prednisone side effects including mood changes and elevated glucose.',
  },
  {
    tag: 'dexamethasone',
    primary: 'dexamethasone',
    confusedWith: ['dexmedetomidine'],
    specialty: 'pain_management',
    dictation:
      'Cervical epidural injection with dexamethasone ten milligrams. Dexamethasone selected for its longer duration of action compared with shorter-acting steroids. Patient tolerated procedure without complication.',
  },

  // ─── Anticoagulants (Vascular Surgery / Primary Care) ─────────
  {
    tag: 'heparin',
    primary: 'heparin',
    confusedWith: ['Hespan'],
    specialty: 'vascular_surgery',
    dictation:
      'Bridging her with low molecular weight heparin while we hold Coumadin pre-procedure. Heparin dose is one milligram per kilogram subcutaneously every twelve hours. Last heparin dose forty-eight hours before surgery.',
  },
  {
    tag: 'coumadin',
    primary: 'Coumadin',
    confusedWith: ['Cardura', 'Avandia'],
    specialty: 'vascular_surgery',
    dictation:
      'Continuing Coumadin with target INR between two and three. She has been on Coumadin for the past four years for her mechanical aortic valve. Last INR was two point four which is in range.',
  },
  {
    tag: 'jantoven',
    primary: 'Jantoven',
    confusedWith: ['Janumet', 'Januvia'],
    specialty: 'primary_care',
    dictation:
      'Patient is on Jantoven five milligrams daily, which is generic warfarin under the Jantoven brand. INR target two to three for her atrial fibrillation. Will check INR weekly until stable.',
  },

  // ─── Psychiatry ───────────────────────────────────────────────
  {
    tag: 'celexa',
    primary: 'Celexa',
    confusedWith: ['Celebrex', 'Cerebyx', 'Zyprexa'],
    specialty: 'psychiatry',
    dictation:
      'Increasing Celexa from twenty milligrams to forty milligrams daily for her ongoing depressive symptoms. She has tolerated Celexa well over the past month with no concerning side effects.',
  },
  {
    tag: 'lexapro',
    primary: 'Lexapro',
    confusedWith: ['Loxitane'],
    specialty: 'psychiatry',
    dictation:
      'Starting Lexapro ten milligrams in the morning for her generalized anxiety disorder. Counseled on the typical four-to-six-week window before Lexapro reaches full therapeutic effect.',
  },
  {
    tag: 'sertraline',
    primary: 'sertraline',
    confusedWith: ['cetirizine'],
    specialty: 'psychiatry',
    dictation:
      'Sertraline fifty milligrams daily appears insufficient. Increasing sertraline to one hundred milligrams in the morning. Follow up in four weeks to assess response and tolerability.',
  },

  // ─── Pain Management ──────────────────────────────────────────
  {
    tag: 'tramadol',
    primary: 'tramadol',
    confusedWith: ['trazodone'],
    specialty: 'pain_management',
    dictation:
      'Tramadol fifty milligrams every six hours as needed for breakthrough pain. Counseled on tramadol seizure risk and the importance of not exceeding four hundred milligrams in a twenty-four-hour period.',
  },
  {
    tag: 'hydroxyzine',
    primary: 'hydroxyzine',
    confusedWith: ['hydralazine', 'hydrochlorothiazide', 'hydroxyurea', 'hydromorphone'],
    specialty: 'pain_management',
    dictation:
      'Adding hydroxyzine twenty-five milligrams at bedtime for sleep and anxiety. Hydroxyzine is non-controlled which fits her treatment plan as we taper her benzodiazepine use.',
  },
  {
    tag: 'oxycodone',
    primary: 'oxycodone',
    confusedWith: ['OxyContin', 'oxybutynin', 'hydrocodone', 'oxymorphone'],
    specialty: 'pain_management',
    dictation:
      'Continuing oxycodone five milligrams every six hours as needed. Last month she used twenty-two oxycodone tablets out of the prescribed sixty, which is consistent with appropriate use.',
  },

  // ─── Primary care (statin) ────────────────────────────────────
  {
    tag: 'atorvastatin',
    primary: 'atorvastatin',
    confusedWith: ['atomoxetine'],
    specialty: 'primary_care',
    dictation:
      'Starting atorvastatin twenty milligrams daily for primary prevention given her LDL of one-sixty-five and family history. Atorvastatin tolerated by most patients with rare myalgia at this dose.',
  },

  // ─── Empirical Deepgram findings (post-ISMP 2024) ─────────────
  // Pairs surfaced by the PR-3 regression baseline that aren't in
  // the canonical ISMP list. Each scenario verifies the symmetric
  // safety-floor entry (added in PR-5) preserves the target name.
  // Specialty key: 'unspecified' — `neurology` isn't a canonical
  // SPECIALTY_KEYTERMS bundle today, so the run exercises CORE +
  // safety floor only (no specialty layer to amplify the bias).
  // This is the strictest test of the safety floor in isolation.
  {
    tag: 'levetiracetam',
    primary: 'levetiracetam',
    confusedWith: ['Levemir', 'lamotrigine'],
    specialty: 'unspecified',
    dictation:
      'Starting levetiracetam five hundred milligrams twice daily for seizure prophylaxis following her recent traumatic brain injury. Counseled on potential mood side effects and will reassess the levetiracetam dose in three months.',
  },
];
