// ============================================================================
// Layer 7a — ICD-10-CM coding (T-M6)
// ----------------------------------------------------------------------------
// Reads the polished SOAP + extracted entities and returns a list of
// evidence-backed ICD-10 codes for billing. No code is included unless
// it can be supported by a verbatim quote from the SOAP, and confidence
// is emitted per-code so the UI can surface uncertainty visually.
// ============================================================================

import { z } from 'zod';
import {
  modelClient,
  isValidIcd10,
  isIcd10Header,
  billableDescendantsOf,
} from '@meddoc/ai';
import prisma from '@meddoc/db';
import { logAudit } from '@/lib/audit';
import { buildIcdDropRecords } from '@/lib/icd-drops';

const MODEL = 'claude-sonnet-4-6';

export const IcdCode = z.object({
  code: z
    .string()
    // ⚠️ POSITION 2 ACCEPTS A LETTER. It used to be `[0-9]`, which was true of
    // every ICD-10-CM code until FY2026 introduced the QA0 neurodevelopmental
    // chapter — 13 valid-for-submission codes (QA0.0101 … QA0.8, the SCN2A- /
    // CACNA1A- / SLC6A1- / STXBP1- / DLG4- / FOXG1-related disorders) with a
    // LETTER there. Found by the adversarial pass on the FY2026 ingestion:
    // against the 604-code starter set the invariant "every allowlist member
    // satisfies this regex" held with 0 violations; against the complete CMS
    // set it had 13. That mattered because `IcdResult` parses the model's
    // WHOLE array at once, so a single QA0 code failed the parse and discarded
    // every OTHER code in the same response.
    //
    // This only widens the SHAPE pre-filter. `isValidIcd10` remains the actual
    // floor, and `gate-icd-schema-allowlist-parity.test.ts` now pins the two
    // together so this cannot silently drift again.
    .regex(/^[A-Z][0-9A-Z][0-9A-Z](?:\.[0-9A-Z]{1,4})?$/i, 'ICD-10-CM format'),
  description: z.string().min(1),
  evidence_quote: z.string().min(1),
  /** 0-1 confidence — the UI maps <0.5 red, 0.5-0.8 amber, >0.8 green. */
  confidence: z.number().min(0).max(1),
  /** Q2 fix-pack §06.6 — categorical companion to the numeric
   *  confidence. Derived from the number (>=0.8 = high, 0.5-0.8 =
   *  medium, <0.5 = low). The dual representation lets the UI render
   *  the gradient AND the post-processor flag low-confidence codes
   *  for `needsReview` without re-deriving thresholds. */
  confidenceLevel: z.enum(['high', 'medium', 'low']),
});
export type IcdCode = z.infer<typeof IcdCode>;

export const IcdResult = z.object({
  codes: z.array(IcdCode).default([]),
});
export type IcdResult = z.infer<typeof IcdResult>;

/**
 * Clinical-coherence floor for varicose-vein codes. An ASYMPTOMATIC / unspecified
 * varicose code (I83.9x — I83.90 unspecified, I83.91/92/93) cannot coexist with a
 * SYMPTOMATIC varicose code (I83.8x, "…with other complications/pain/…") in the
 * same study: a patient coded symptomatic is not simultaneously "asymptomatic
 * varicose", and a normal-findings limb warrants no varicose code at all.
 *
 * The symptomatic/complicated varicose families are I83.0x (with ulcer), I83.1x
 * (with inflammation), I83.2x (with both), and I83.8x (with other complications) —
 * the same taxonomy the L7A prompt teaches; I83.9x is the asymptomatic family.
 *
 * ONLY-REMOVE semantics: when any symptomatic varicose code is present, drop any
 * asymptomatic/unspecified I83.9x that rode along. A supported symptomatic code is
 * never touched, no code is ever added, and — with no symptomatic code present —
 * a genuine asymptomatic code (a truly asymptomatic-but-present varicosity) is
 * left untouched. Pure + deterministic. Preserves input order.
 */
/**
 * RULING #180 — split one exit's refusals into its two sub-reasons.
 *
 * ⚠️ EXPORTED AND PURE SO A GATE CAN DRIVE IT. An earlier draft did this inline
 * and the mutation proof caught the consequence: collapsing the split changed
 * NOTHING the gate could see, because the gate reproduced the classification in
 * a local helper. *A copy of the logic cannot witness the logic.* It follows the
 * pattern this file already uses for its three coherence floors.
 *
 * ⚠️ AND IT LIVES HERE, NOT IN `icd-drops.ts`, because that module is a
 * CLIENT-SAFE LEAF — `icd-coding-view.tsx` is a `'use client'` component that
 * imports from it, and no client file imports `@meddoc/ai` today. Doing this
 * there would pull the Anthropic/OpenAI/Deepgram SDKs and ~700 KB of ICD data
 * into a browser bundle.
 *
 * Total by construction: every input lands in exactly one bucket.
 */
export function classifyAllowlistRefusals(codes: readonly string[]): {
  headers: Array<{ code: string; children: readonly string[] }>;
  notCodes: string[];
} {
  const headers: Array<{ code: string; children: readonly string[] }> = [];
  const notCodes: string[] = [];
  for (const code of codes) {
    if (isIcd10Header(code)) {
      headers.push({ code, children: billableDescendantsOf(code) });
    } else {
      notCodes.push(code);
    }
  }
  return { headers, notCodes };
}

export function dropIncoherentVaricoseCodes(codes: readonly IcdCode[]): IcdCode[] {
  const hasSymptomaticVaricose = codes.some((c) => /^I83\.[0128]/i.test(c.code));
  if (!hasSymptomaticVaricose) return [...codes];
  return codes.filter((c) => !/^I83\.9/i.test(c.code));
}

/**
 * Clinical-coherence floor (generalized) — drop a code that the note EXPLICITLY
 * CONTRADICTS by documenting a denial of the very condition the code encodes.
 * The classic case is a MED-INFERRED code: the L7A prompt hoists K21.9 (GERD)
 * from chronic PPI use, but the note documents "no reflux symptoms / denies
 * heartburn" — the code is then incoherent with the record.
 *
 * ONLY-REMOVE, support-preserving: never adds a code; only fires when the
 * condition appears in the text AND *every* mention sits inside a negation
 * clause. A single affirmative (non-negated) mention — an explicit diagnosis,
 * problem-list entry, or assessment line — marks the code as SUPPORTED and it is
 * never dropped, so a truly-diagnosed-but-asymptomatic-today condition survives.
 * Pure + deterministic; preserves input order. `clinicalText` is the final note
 * (optionally plus structured negation context).
 */
const DENIAL_NEGATION_CUE =
  /\b(no|not|non|denies|denied|deny|without|w\/o|negative for|absence of|absent|ruled out|r\/o|free of|none|resolved)\b/i;

const DENIAL_CONTRADICTION_RULES: ReadonlyArray<{
  readonly prefix: RegExp;
  readonly condition: RegExp;
  readonly label: string;
}> = [
  {
    // GERD (K21.x). The L7A prompt intentionally hoists this from chronic PPI
    // use, so an explicit reflux denial is what makes an unsupported K21.x
    // incoherent — the guard removes only the med-inferred, contradicted code.
    prefix: /^K21(\b|\.)/i,
    // "regurgitation" alone collides with cardiac (mitral/aortic) regurgitation,
    // so it is qualified to "acid regurgitation" — the GERD-specific sense.
    condition: /\b(reflux|gerd|heartburn|acid regurgitation|pyrosis)\b/i,
    label: 'GERD',
  },
];

// An adversative conjunction RESETS the negation scope inside a clause, so a
// negation cue before it does not reach a mention after it: "no history of GERD
// but now has reflux" — the affirmative "reflux" is NOT under the "no".
const ADVERSATIVE_RESET = /\b(but|however|although|though|yet|whereas|aside from|other than|except)\b/gi;

/** True iff `condition` occurs in `text` AND every occurrence is negated within
 *  its own clause (a negation cue earlier in the same clause, not cut off by an
 *  adversative conjunction). A boundary of `.;:,\n` starts a new clause. Commas
 *  ARE boundaries: a serial "no A, no B, and no C" still drops because each item
 *  carries its own cue, but a leading cue is NOT allowed to leak across a comma
 *  onto a later AFFIRMATIVE mention ("denies heartburn, GERD stable on PPI" must
 *  KEEP the supported code). Any affirmative occurrence returns false. */
function conditionExplicitlyDenied(text: string, condition: RegExp): boolean {
  const scan = new RegExp(condition.source, 'gi');
  let match: RegExpExecArray | null;
  let sawMention = false;
  while ((match = scan.exec(text)) !== null) {
    sawMention = true;
    const before = text.slice(0, match.index);
    // The current clause = the trailing run of non-boundary chars before the
    // mention (last `.;:,\n` resets it)…
    let clause = before.slice(before.search(/[^.;:,\n]*$/));
    // …then trim to after the last adversative conjunction in that clause, so a
    // "no X but has X" affirmation is not read as negated.
    ADVERSATIVE_RESET.lastIndex = 0;
    let am: RegExpExecArray | null;
    let cut = -1;
    while ((am = ADVERSATIVE_RESET.exec(clause)) !== null) cut = am.index + am[0].length;
    if (cut >= 0) clause = clause.slice(cut);
    if (!DENIAL_NEGATION_CUE.test(clause)) return false; // affirmative → supported
  }
  return sawMention;
}

export function dropDenialContradictedCodes(
  codes: readonly IcdCode[],
  clinicalText: string
): IcdCode[] {
  if (!clinicalText) return [...codes];
  return codes.filter((c) => {
    const rule = DENIAL_CONTRADICTION_RULES.find((r) => r.prefix.test(c.code));
    if (!rule) return true;
    return !conditionExplicitlyDenied(clinicalText, rule.condition);
  });
}

/**
 * Clinical-coherence floor (deficiency family, principle-level) — drop an
 * ICD-10 deficiency-family code (E50–E64: vitamin, mineral, and other
 * nutritional-deficiency codes) whose ONLY support in the note is one of the
 * contexts that does NOT establish a deficiency DIAGNOSIS:
 *   - PROPHYLACTIC supplementation — a bariatric multivitamin / B12 / vitamin-D /
 *     iron regimen is given to PREVENT deficiency, not because one is documented;
 *   - a MISSED / skipped dose — non-adherence, not a measured deficiency;
 *   - an ORDERED-BUT-UNRESULTED lab — a pending workup, not a result.
 * The classic false-positive is a post-bariatric plan: "started on chewable
 * multivitamin and vitamin D3 to prevent nutritional deficiency" hoists E63.9 /
 * E55.9 / E53.8 with no deficiency ever diagnosed.
 *
 * ONLY-REMOVE, support-preserving. A code is dropped only when ALL hold: it is in
 * the E50–E64 family, its cited evidence_quote is a prophylactic/ordered/missed
 * context, AND the note does not AFFIRMATIVELY document a deficiency anywhere. Any
 * affirmative, non-preventive deficiency statement in the note (an assessment
 * line, "B12 deficiency", a documented low level) VETOES the drop for the whole
 * family — a real, documented deficiency is never suppressed. Evidence that is
 * itself a deficiency claim is kept; ambiguous evidence (neither clearly
 * prophylactic nor a deficiency claim) is kept. Pure + deterministic; preserves
 * input order.
 */
const DEFICIENCY_FAMILY = /^E(5[0-9]|6[0-4])(\b|\.)/i;

// Deficiency-DIAGNOSIS language — the words that mark a family code as SUPPORTED
// when they sit in a clause that is not framed as prevention/risk/negation.
const DEFICIENCY_DX_WORD =
  /\b(deficien\w*|deplet\w*|insufficien\w*|hypovitaminosis|malnutrition|malnourish\w*)\b/i;

// Framing that turns a "deficiency" word into a NON-diagnosis (prevention, risk,
// screening, or negation) — a mention under this framing is not an active
// diagnosis, so it must not protect a family code. Deliberately NARROW: only
// genuinely preventive/negating cues, NOT incidental exam words like "lower
// (extremity)" / "reduce" / "monitor" that can co-occur with a real deficiency
// clause and wrongly defeat the support-preserving veto.
const NON_DIAGNOSTIC_FRAMING =
  /\b(prevent\w*|prophyla\w*|avoid\w*|guard against|reduce the risk|at risk|risk of|risk for|screen\w* for|rule out|r\/o|no|not|non|denies|deny|without|w\/o|negative for|absence of|absent)\b/i;

// Support that does NOT, on its own, establish a deficiency diagnosis:
// prophylactic supplementation, ordered-but-unresulted labs, or missed doses.
const NON_DIAGNOSTIC_SUPPORT =
  /\b(prophyla\w*|supplement\w*|multi-?vitamin|MVI|repletion|maintenance doses?|started on|continu\w*|prescrib\w*|recommend\w*|advis\w*|encourag\w*|daily (?:oral )?(?:vitamin|calcium|iron|b-?12|folate|folic|zinc|thiamine)|missed (?:a |several )?doses?|skipped (?:a )?doses?|non-?adheren\w*|noncompli\w*|not taking|order\w*|obtain\w*|check\w*|draw\w*|pending|await\w*|to be drawn|will (?:monitor|recheck|check|follow|repeat|obtain)|recheck\w*)/i;

// A deficiency word is only DEFEATED as a diagnosis when the preventive/negation
// framing SCOPES it: preventive cues sit BEFORE the word ("prevent/risk of/screen
// for/no/denies … deficiency"), or an immediate resolution qualifier follows it
// ("deficiency ruled out/resolved/excluded"). A later clause-local token that
// modifies a DIFFERENT verb — "B12 deficiency NOT fully CORRECTED" ("not" negates
// "corrected", not the deficiency) — must NOT defeat the affirmation. Checking the
// pre-word text (plus a tight post-word resolution qualifier) instead of the whole
// clause errs toward KEEPING a documented deficiency (support-preserving).
const RESOLUTION_AFTER = /^\s+(ruled out|resolved|excluded|no longer\b|not present)/i;

/** True iff `text` AFFIRMATIVELY documents a deficiency — a deficiency-diagnosis
 *  word that is NOT framed (preventive cue before it, or a resolution qualifier
 *  right after it). Used for both the note-level veto and per-code evidence. */
function deficiencyAffirmedIn(text: string): boolean {
  if (!text) return false;
  const scan = new RegExp(DEFICIENCY_DX_WORD.source, 'gi');
  let m: RegExpExecArray | null;
  while ((m = scan.exec(text)) !== null) {
    // Clause bounds around the match (last `.;:,\n` before → next after).
    const start = text.slice(0, m.index).search(/[^.;:,\n]*$/);
    const before = text.slice(start, m.index);
    const rest = text.slice(m.index + m[0].length);
    const relEnd = rest.search(/[.;:,\n]/);
    const after = relEnd === -1 ? rest : rest.slice(0, relEnd);
    const framedBefore = NON_DIAGNOSTIC_FRAMING.test(before);
    const resolvedAfter = RESOLUTION_AFTER.test(after);
    if (!framedBefore && !resolvedAfter) return true; // an unframed deficiency mention = a diagnosis
  }
  return false;
}

export function dropUnsupportedDeficiencyCodes(
  codes: readonly IcdCode[],
  clinicalText: string
): IcdCode[] {
  if (deficiencyAffirmedIn(clinicalText)) return [...codes]; // a real deficiency is documented → keep the family
  return codes.filter((c) => {
    if (!DEFICIENCY_FAMILY.test(c.code)) return true;
    if (deficiencyAffirmedIn(c.evidence_quote)) return true; // its own evidence asserts one
    if (NON_DIAGNOSTIC_SUPPORT.test(c.evidence_quote)) return false; // prophylactic / ordered / missed → drop
    return true; // ambiguous evidence → conservative keep
  });
}

export interface Layer7aInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  specialty: string;
  soapFinal: string;
  entitiesJson: string;
}

/** L7a system prompt — exported for regression-guard tests. The
 *  prompt-quality checks live in
 *  apps/transcribe-md/tests/worker/icd-coding-prompt.test.ts and
 *  anchor on substrings that are load-bearing for specific clinical
 *  cohorts (e.g. "chronic GERD on PPI" anchors the K21.9 hoisting
 *  pattern that audit-finding B2 reproduced). */
export const L7A_SYSTEM_PROMPT: string = [
    'You are a certified medical coding specialist. Extract ICD-10-CM',
    '(2025) codes from this clinician SOAP note for billing purposes.',
    '',
    'Principles:',
    '- Primary diagnosis first, then comorbidities addressed in the plan.',
    '- INCLUDE chronic comorbidities documented in PMH, imaging reports,',
    '  problem lists, or medication lists when they influence current',
    '  care planning, comorbidity reporting, HCC risk-adjustment, or',
    '  routine surveillance ordered at this visit. Examples for primary',
    '  care / weight management: NAFLD (K76.0) shown on prior imaging;',
    '  obstructive sleep apnea (G47.33) treated with CPAP; CKD (N18.x)',
    '  trended via creatinine; prior MI (I25.2); COPD (J44.x); HFrEF',
    '  (I50.22 chronic / I50.21 acute) on guideline-directed therapy;',
    '  HFpEF (I50.32 chronic / I50.31 acute) — pick the systolic vs',
    '  diastolic family based on the documented EF + clinical phenotype;',
    '  chronic GERD on PPI (K21.9) — chronic PPI use is the marker, not',
    '  active reflux symptoms this visit. The plan need not explicitly',
    '  act on each chronic condition for that condition to merit coding',
    '  — ongoing therapy, monitoring, or surveillance counts as "active".',
    '- INCLUDE chronic medication Z-codes (e.g. Z79.84 long-term oral',
    '  hypoglycemic, Z79.890 long-term hormonal therapy, Z79.01 long-term',
    '  anticoagulant, Z79.02 long-term antiplatelet) when the medication',
    '  list documents chronic use of a relevant drug class — even when',
    '  the underlying condition is coded separately.',
    '- INCLUDE personal-history Z-codes (Z86.7x family) when the PMH or',
    '  problem list documents a clinically-relevant prior event whose',
    '  history shapes current management — even when no active symptoms.',
    '  Examples: Z86.718 personal history of VTE (prior DVT/PE is the',
    '  driver of extended VTE prophylaxis post-op + the reason behind',
    '  any continued anticoagulant); Z86.73 personal history of TIA /',
    '  cerebral infarction without residual deficit (drives statin +',
    '  antiplatelet decisions); Z87.891 personal history of nicotine',
    '  dependence (former smoker — code even when not active).',
    '- INCLUDE acquired-absence Z-codes (Z90.x family) for post-surgical',
    '  anatomy on every visit at month 1+. Examples: Z90.3 acquired',
    '  absence of stomach (post-RYGB / post-sleeve / post-BPD-DS — pair',
    '  with Z98.84 bariatric-surgery-status); Z90.49 acquired absence',
    '  of other digestive-tract parts. The bariatric anatomy persists',
    '  for life, so these codes belong on every follow-up encounter.',
    '- INCLUDE acute findings documented during a workup, even when the',
    '  encounter is "evaluating" rather than "treating" them. The most',
    '  commonly missed shapes:',
    '    * AKI (N17.x) — code when creatinine has shifted from baseline',
    '      (e.g., Cr 1.4 from baseline 0.8 = N17.9), not only when AKI',
    '      is the named diagnosis. The shift IS the diagnosis.',
    '    * Dehydration / volume depletion (E86.0 / E86.9) — code when',
    '      clinical exam documents it (dry mucous membranes, orthostatic',
    '      vitals, low PO intake) even when fluid resuscitation is the',
    '      same encounter\'s treatment.',
    '    * Site-specific abdominal pain (R10.10-.84) — prefer the site-',
    '      specific code over R10.9 unspecified when the exam localizes',
    '      it (LUQ → R10.12, RUQ → R10.11, epigastric → R10.13).',
    '- PREFER the documented diagnosis over symptom codes. When the SOAP',
    '  explicitly names a diagnosis (e.g., "PROTEIN-CALORIE MALNUTRITION"',
    '  with albumin < 3.0 and sarcopenia → E43 / E44.0), code that',
    '  diagnosis directly. Symptom codes (R63.4 abnormal weight loss,',
    '  R53.83 fatigue) are appropriate ONLY when no specific diagnosis',
    '  is established. Same pattern: B12-deficiency anemia → D51.9 over',
    '  separately coding E53.8 + D50.9.',
    '- Do NOT code "rule out" / "suspected" / "differential" diagnoses',
    '  that the clinician explicitly framed as uncertain. The exclusion',
    '  is uncertainty, NOT chronicity, NOT documented acute findings.',
    '- Do NOT code one-off historical events that have no bearing on',
    '  current care (e.g. childhood appendectomy with no current sequelae).',
    '- Use the most specific code possible (e.g. I11.0 over I15.9 when',
    '  hypertensive heart failure is clearly documented).',
    '- Include Z codes for preventive or screening encounters when the',
    '  SOAP explicitly documents them.',
    '',
    'For EACH code, include:',
    '- code: valid ICD-10-CM, letter + 2-7 alphanumerics, e.g. "E11.9"',
    '- description: the ICD-10-CM official title',
    '- evidence_quote: verbatim snippet from the SOAP note supporting',
    '  this code',
    '- confidence: 0.0-1.0 based on how directly the SOAP documents it',
    '    >=0.9 explicit diagnosis statement',
    '    0.7-0.9 strongly implied by findings + plan',
    '    0.5-0.7 reasonable inference, worth doctor review',
    '    <0.5   speculative — include only if you would back it in',
    '            a billing audit',
    '- confidenceLevel: categorical view of confidence (Q2 fix-pack):',
    '    "high"   → confidence >= 0.8',
    '    "medium" → 0.5 <= confidence < 0.8',
    '    "low"    → confidence < 0.5',
    '  Always set; downstream UI flags low-confidence codes for review.',
    '',
    'CRITICAL: If you cannot cite a specific evidence_quote for a code,',
    'OMIT the code. Hallucinating ICD codes can constitute billing fraud.',
    '',
    // 2026-05-13 cross-input-mode-audit Finding 3 — procedure-dominant
    // visits (suspicious-mole biopsy, postpartum visit, acute ankle
    // sprain) were returning empty `codes: []` because the model
    // reasoned "the procedure CPT codes carry the billing here." Every
    // billable encounter has at least one diagnosis or encounter Z-code;
    // an empty diagnosis list is a billing-compliance gap. The rule
    // below is the floor.
    'MINIMUM CODING REQUIREMENT — EVERY VISIT EMITS AT LEAST ONE CODE.',
    'Every clinical encounter has at minimum ONE billable diagnosis or',
    'encounter Z-code, even when the visit\'s billing center is a',
    'procedure or routine follow-up. Returning an empty `codes` array',
    'is not an acceptable output unless the SOAP itself is empty.',
    '',
    'Specific patterns the model SHOULD match (not optional):',
    '- Routine postpartum visit / lactation check → Z39.0 / Z39.1 / Z39.2.',
    '- Suspicious-mole biopsy / nevus excision → D22.x (melanocytic nevi',
    '  by site) or D48.5 (uncertain behavior, pre-pathology). Do NOT',
    '  leave a derm-biopsy visit without a diagnosis code — the path',
    '  result is the eventual code; the day-of code is the clinical',
    '  impression at biopsy time.',
    '- Acute ankle sprain / joint sprain → S93.4xxA / S83.xxxA / S39.012A',
    '  for the lumbar strain shape. Acute injuries ALWAYS get an S-code.',
    '- Knee OA injection / aftercare visit → M17.x (OA), plus M25.x',
    '  joint-pain-by-site, plus Z47.x aftercare when relevant.',
    '- Routine well-care / preventive → Z00.00 / Z00.01 / Z12.x screening',
    '  Z-codes; pair with any chronic comorbidity codes for HCC risk.',
    '- Counseling-dominant visit (weight, smoking, diet, contraception)',
    '  → Z71.x family + the underlying condition code(s).',
    '- Lifestyle / metabolic follow-up → primary chronic-condition',
    '  code (E11.x for T2DM, E66.x for obesity) is mandatory.',
    '- Venous / varicose veins (e.g. a venous-duplex reflux study): when the',
    '  note documents varicose veins WITH any symptom or complication, use the',
    '  SYMPTOMATIC / complicated I83.8x family — NEVER the asymptomatic I83.9x',
    '  code. Map by the documented complication: pain → I83.81x; swelling /',
    '  heaviness / aching / edema / cramps / fatigue / other complications →',
    '  I83.89x. For THESE TWO families ONLY, the final digit encodes laterality',
    '  (right = ...1, left = ...2, bilateral = ...3; unspecified = I83.819 for',
    '  pain, I83.899 for other complications). With inflammation → I83.1x and',
    '  with an ulcer → I83.0x, chosen by the documented laterality and (for',
    '  ulcers) the ulcer SITE — the "final digit = laterality" shortcut does',
    '  NOT apply to the ulcer/inflammation families (an ulcer code carries',
    '  laterality in its 5th digit and the site in its last digit). If the',
    '  precise ulcer/inflammation code is unavailable, fall back to the I83.89x',
    '  other-complications code for the affected side. Reserve the asymptomatic',
    '  I83.9x family ONLY when the note EXPLICITLY documents no symptoms or',
    '  complications (a normal contralateral leg may legitimately take an',
    '  asymptomatic code even when the affected leg is symptomatic).',
    '- Imaging or procedure pre-op → encounter Z-code (Z01.81x pre-procedural',
    '  exams) + the indication condition code.',
    '',
    'If you genuinely cannot identify any diagnosis or encounter Z-code',
    'from the SOAP, return ONE confidence:0.3-0.4 Z76.89 ("other specified',
    'reason for encounter") and let the L7a post-validation layer flag',
    'the visit for review. This is preferable to returning `codes: []`.',
    '',
    'Respond with VALID JSON ONLY, no markdown fences:',
    '{ "codes": [{ "code": "...", "description": "...",',
    '              "evidence_quote": "...", "confidence": 0.0,',
    '              "confidenceLevel": "high" }] }',
].join('\n');

export async function runLayer7aIcdCoding(
  input: Layer7aInput
): Promise<IcdResult> {
  const system = L7A_SYSTEM_PROMPT;

  const user = [
    `Specialty: ${input.specialty}`,
    '',
    'Entities (structured extract from the visit):',
    input.entitiesJson,
    '',
    'SOAP note (the authoritative source for codes):',
    input.soapFinal,
  ].join('\n');

  const result = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    userId: input.userId,
    purpose: 'tm_icd_coding',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: IcdResult,
    maxTokens: 3072,
    // Q2 fix-pack — billing codes are deterministic; tightened from
    // 0.1 to 0 so the same SOAP produces the same code list every time.
    temperature: 0,
    // 2026-05-13 SCHEMA_FAIL hardening (cross-input-mode-audit Finding 1):
    // Force Anthropic to return structured output via tool_use instead
    // of free-form text + JSON.parse. PED1 in the cross-input-mode-audit
    // hit a JSON_PARSE_FAIL at position 790 (trailing-garbage shape) which
    // exhausted the 2-retry budget; tool_use eliminates that failure
    // class because the response is a structured object, not free text.
    useToolUse: {
      name: 'submit_icd_codes',
      description:
        'Submit the final ICD-10-CM code list for this visit. Each code carries the verbatim SOAP evidence and per-code confidence.',
    },
  });

  // Round 3 PR-D — A06-P0-002 deterministic ICD-10 allowlist floor.
  // Filter Claude's output through the canonical starter set; drop any
  // code that doesn't match. Each rejection emits an audit row so the
  // admin dashboard can reason about how often the model emits invalid
  // codes (signal for prompt-tightening or expanding the allowlist).
  const accepted: typeof result.codes = [];
  const rejected: Array<{ code: string; description: string }> = [];
  for (const c of result.codes) {
    if (isValidIcd10(c.code)) {
      // Q2 fix-pack §06.6 — defensive re-derivation of confidenceLevel
      // from the numeric confidence. The model is asked to emit both
      // and they should agree; if the model drifted on the categorical
      // rule, the numeric value is the source of truth. Prevents a
      // "high" badge over a 0.4-confidence code.
      const derivedLevel: 'high' | 'medium' | 'low' =
        c.confidence >= 0.8 ? 'high' :
        c.confidence >= 0.5 ? 'medium' : 'low';
      accepted.push({ ...c, confidenceLevel: derivedLevel });
    } else {
      rejected.push({ code: c.code, description: c.description });
    }
  }
  if (rejected.length > 0) {
    void logAudit({
      action: 'CODING_COACH_REJECTED_INVALID_ICD',
      targetId: input.visitId,
      targetType: 'TranscribeVisit',
      userId: input.userId,
      practiceId: input.practiceId,
      success: false,
      metadata: {
        rejectedCount: rejected.length,
        // Only the codes (NOT the AI-emitted descriptions which can
        // include patient context). Codes alone are non-PHI structured
        // billing data.
        rejectedCodes: rejected.map((r) => r.code),
      },
    });
  }
  // Clinical-coherence floor (varicose veins) — see dropIncoherentVaricoseCodes.
  // Dropped codes are VALID (allowlist-passed) but clinically incoherent, so they
  // are NOT audited via CODING_COACH_REJECTED_INVALID_ICD (that action feeds the
  // "invalid-code rate" metric and must stay pure). A non-PHI console line keeps
  // the drop observable without polluting that metric.
  const coherent = dropIncoherentVaricoseCodes(accepted);
  const droppedIncoherent = accepted.filter((c) => !coherent.includes(c));
  if (droppedIncoherent.length > 0) {
    console.info(
      `[l7a-icd] dropped ${droppedIncoherent.length} incoherent asymptomatic varicose code(s) alongside a symptomatic one: ${droppedIncoherent.map((c) => c.code).join(', ')}`
    );
  }
  // Generalized coherence floor — drop a code the note explicitly denies (e.g.
  // med-inferred K21.9 GERD vs a documented reflux denial). Scans the final note
  // (the entities JSON is appended as a coarse, conservative fallback — its `:`
  // punctuation clause-breaks most structured negation, so it rarely fires);
  // ONLY-REMOVE and support-preserving (a code whose condition is affirmatively
  // documented is never touched). Same non-PHI-console + metric-purity treatment
  // as the varicose floor above.
  const denialText = `${input.soapFinal ?? ''}\n${input.entitiesJson ?? ''}`;
  const coherentDenial = dropDenialContradictedCodes(coherent, denialText);
  const droppedDenied = coherent.filter((c) => !coherentDenial.includes(c));
  if (droppedDenied.length > 0) {
    console.info(
      `[l7a-icd] dropped ${droppedDenied.length} code(s) contradicted by an explicit denial in the note: ${droppedDenied.map((c) => c.code).join(', ')}`
    );
  }
  // Deficiency-family floor (E50–E64) — drop a deficiency code supported ONLY by
  // prophylactic supplementation / missed doses / ordered-but-unresulted labs;
  // a documented deficiency is never suppressed. Scans the final note (the
  // diagnosis lives there); ONLY-REMOVE. Same non-PHI-console + metric-purity
  // treatment as the guards above.
  const coherentFinal = dropUnsupportedDeficiencyCodes(coherentDenial, input.soapFinal ?? '');
  const droppedDeficiency = coherentDenial.filter((c) => !coherentFinal.includes(c));
  if (droppedDeficiency.length > 0) {
    console.info(
      `[l7a-icd] dropped ${droppedDeficiency.length} deficiency-family code(s) supported only by prophylactic supplementation / ordered labs / missed doses: ${droppedDeficiency.map((c) => c.code).join(', ')}`
    );
  }
  const filtered: typeof result = { codes: coherentFinal };

  // Q2 fix-pack §06.6 — surface low-confidence codes via needsReview when one or
  // more of the FINAL (coherence-filtered) codes land at confidenceLevel='low'.
  // Doctor sees the warning before signing rather than auto-attaching a
  // speculative code to billing.
  const lowConfCodes = coherentFinal.filter((c) => c.confidenceLevel === 'low');
  if (lowConfCodes.length > 0) {
    await prisma.transcribeVisit.update({
      where: { id: input.visitId },
      data: {
        needsReview: true,
        reviewReason: `${lowConfCodes.length} ICD code${lowConfCodes.length === 1 ? '' : 's'} at low confidence — verify before billing: ${lowConfCodes.map((c) => c.code).join(', ')}.`,
      },
    });
  }

  // 2026-05-13 cross-input-mode-audit Finding 3 post-validation —
  // even with the prompt's MINIMUM CODING REQUIREMENT instruction, the
  // model can still return empty codes (it can also return one Z76.89
  // last-resort code, which we treat as semantically equivalent to
  // empty for the purposes of the doctor's review banner). Flip
  // needsReview + reviewReason so the billing-compliance gap surfaces
  // before sign-off.
  const isPlaceholderOnly =
    coherentFinal.length === 1 && coherentFinal[0].code.toUpperCase() === 'Z76.89';
  if (coherentFinal.length === 0 || isPlaceholderOnly) {
    const reason = coherentFinal.length === 0
      ? `Auto-coding returned no diagnoses for this ${input.specialty.replace(/-/g, ' ')} encounter — verify before signing. Every billable visit should carry at least one diagnosis or encounter Z-code.`
      : 'Auto-coding could not identify a specific diagnosis (placeholder Z76.89 used) — verify before signing.';
    await prisma.transcribeVisit.update({
      where: { id: input.visitId },
      data: {
        needsReview: true,
        reviewReason: reason,
      },
    });
    void logAudit({
      action: 'VISIT_AUTOMATION_INCOMPLETE',
      targetId: input.visitId,
      targetType: 'TranscribeVisit',
      userId: input.userId,
      practiceId: input.practiceId,
      success: false,
      metadata: {
        layer: 'l7a-icd',
        emptyArray: coherentFinal.length === 0,
        placeholderOnly: isPlaceholderOnly,
        specialty: input.specialty,
      },
    });
  }

  // ── F8-S1b — THE DROP RECORD ────────────────────────────────────────────
  // Every exit's losers, each with its own reason token, deduped by code and
  // EXCLUDING anything that survived into `codes[]`.
  //
  // ⚠️ THE SURVIVOR EXCLUSION IS NOT BELT-AND-BRACES. The three coherence floors
  // decide PER CANDIDATE OBJECT on that object's `evidence_quote`, while a drop
  // record is keyed by CODE — and `IcdResult` places no uniqueness constraint on
  // the model's array. So one code emitted TWICE with different evidence has one
  // instance kept and one dropped, and without this the blob would assert both
  // "E63.9 is suggested" and "E63.9 was suppressed as unsupported". Found by the
  // adversarial pass; see `lib/icd-drops.ts`.
  //
  // ⚠️ THE ACCUMULATION IS A PURE, EXPORTED FUNCTION AND NOT INLINE CODE, SO IT
  // CAN BE DRIVEN. The first draft built the list here with four inline pushes,
  // which left the gate no way to prove the reason↔exit binding except by
  // regexing this file — and a source scan cannot see two tokens SWAPPED between
  // their loops, which is this slice's entire product inverted. Named properties
  // on `IcdDropInputs` are what a reader checks; the gate checks behaviour.
  // ⚠️ RULING #180 — ONE EXIT, TWO SUB-REASONS, CLASSIFIED HERE.
  // `rejected` is the output of a SINGLE exit (`isValidIcd10` failing at the
  // accept loop above), so #149(b)'s four exits are unchanged. What #180 adds
  // is that the exit's reason is not one thing: a category HEADER is a real
  // ICD-10-CM entry with billable descendants — actionable, and one always
  // exists — while a fabrication has nothing to offer. Telling a doctor the
  // same sentence for both is the defect the ruling closes.
  //
  // ⚠️ THE SPLIT LIVES HERE AND NOT IN `icd-drops.ts` BECAUSE THAT MODULE IS A
  // CLIENT-SAFE LEAF. `icd-coding-view.tsx` is a `'use client'` component that
  // imports from it, and no client file imports `@meddoc/ai` today — doing the
  // classification there would pull the Anthropic/OpenAI/Deepgram SDKs and
  // ~700 KB of ICD data into a browser bundle. This layer is the worker.
  const { headers: rejectedHeaders, notCodes: rejectedNotCodes } =
    classifyAllowlistRefusals(rejected.map((r) => r.code));

  const dropped = buildIcdDropRecords({
    notInVerifiedAllowlist: rejectedNotCodes,
    headerUseBillableChild: rejectedHeaders,
    incoherentVaricose: droppedIncoherent.map((c) => c.code),
    contradictedByDenial: droppedDenied.map((c) => c.code),
    unsupportedDeficiency: droppedDeficiency.map((c) => c.code),
    survivors: coherentFinal.map((c) => c.code),
  });

  // ⚠️ F8-S1b — THE STORED BLOB IS WIDER THAN THE RETURN VALUE, DELIBERATELY.
  // `filtered` is what this layer RETURNS and its shape is unchanged, so
  // `automation-incomplete.ts`'s `isIcdEmpty` and everything downstream of
  // `runIcdCoding` see byte-identical input. Only the COLUMN gains `dropped`,
  // and every reader of that column takes `.codes` or goes through
  // `extractIcdRows` — enumerated by call site, and asserted by the gate rather
  // than trusted here, because *a shared noun is not a shared surface*.
  //
  // `dropped` is written UNCONDITIONALLY, empty array included. A key that
  // appears only when non-empty makes "this run dropped nothing" and "this blob
  // predates the drop record" the same observation — the absent-vs-refused
  // collapse this whole record exists to undo.
  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { icdCodes: { ...filtered, dropped } as unknown as object },
  });

  return filtered;
}
