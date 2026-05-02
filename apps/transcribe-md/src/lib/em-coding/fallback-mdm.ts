// ============================================================================
// E&M Coding — deterministic MDM fallback (Phase 5.2)
// ----------------------------------------------------------------------------
// Used when the LLM is unavailable OR when the engine needs a sub-5ms
// score for a synchronous render (e.g. pre-LLM placeholder while the
// async judge resolves). Implements rubric §4.4 verbatim.
//
// Tradeoff acknowledged in §4.4: this misses LLM-judged nuance like
// "uncertain prognosis" but gets the 80% case right. The score returned
// here is also what the engine downgrades to when llmJudged===false.
// ============================================================================

import {
  CHRONIC_ICD_PREFIXES,
  HIGH_RISK_PATTERNS,
  HOSPITALIZATION_PATTERNS,
  LABS_IMAGING_PATTERNS,
  LEVEL_RANK,
  LEVEL_TO_TIER,
  LIFE_THREAT_PATTERNS,
  SYSTEMIC_SX_PATTERNS,
} from './rubric';
import type { ElementLevel, MdmJudgement, MdmTier } from './types';

/** Minimal shape of an ICD code we can score against. */
export interface IcdCodeRow {
  code: string;
  description?: string;
}

/** Minimal shape of an Rx draft we can score against. */
export interface RxDraftRow {
  drug?: string;
  drug_name?: string;
  action?: 'new' | 'continue' | 'increase' | 'decrease' | 'discontinue' | string;
}

/** 2-of-3 tier resolution (rubric §2.5). Returns the MdmTier
 *  corresponding to the SECOND-highest of the three element levels.
 *  This is the canonical algorithm shared between the LLM judge and
 *  the deterministic fallback. */
export function resolveTier(
  problems: ElementLevel,
  data: ElementLevel,
  risk: ElementLevel,
): MdmTier {
  const sorted: ElementLevel[] = [problems, data, risk].sort(
    (a, b) => LEVEL_RANK[b] - LEVEL_RANK[a],
  );
  return LEVEL_TO_TIER[sorted[1]];
}

/** True when the ICD code starts with any chronic-disease prefix. */
function isChronicDisease(code: string): boolean {
  const upper = code.toUpperCase().replace(/\./g, '');
  return CHRONIC_ICD_PREFIXES.some((p) => upper.startsWith(p));
}

/** Self-limited / minor problem ICD prefixes — these are the codes
 *  that map onto rubric §2.1 "1 self-limited or minor problem" so the
 *  problems element drops to minimal even with 1 ICD on the visit.
 *  The list is intentionally narrow: viral URI, common cold, minor
 *  contusions, conjunctivitis, etc. */
const SELF_LIMITED_PREFIXES = [
  'J00',  // common cold
  'J06',  // acute URI
  'J20',  // acute bronchitis (sometimes)
  'B27',  // mononucleosis
  'B30',  // viral conjunctivitis
  'H10',  // conjunctivitis
  'L30',  // dermatitis (minor)
  'R05',  // cough symptom
  'R51',  // headache symptom
  // Preventive / wellness encounters (rubric §2.1 minimal): Z-codes
  // are encounter-for-screening / wellness, not problems per se.
  'Z00',  // general adult medical exam
  'Z01',  // exam for special purposes
  'Z23',  // immunization
  'Z30',  // contraceptive management (encounter, not problem)
  'Z39',  // postpartum care
];

/** True only when ALL provided ICDs are minor/self-limited per the
 *  narrow allow-list above. Used to downgrade problems→minimal. */
function isSelfLimitedOnly(icdCodes: IcdCodeRow[]): boolean {
  if (icdCodes.length === 0) return false;
  return icdCodes.every((c) => {
    const upper = c.code.toUpperCase().replace(/\./g, '');
    return SELF_LIMITED_PREFIXES.some((p) => upper.startsWith(p));
  });
}

/** True when the SOAP body contains an acute-systemic marker linked
 *  loosely to a problem (we don't try to associate per-problem; any
 *  systemic-marker hit anywhere in the note is enough to lift the
 *  problems level). */
function hasSystemicMarker(soap: string, _icdCode: string): boolean {
  return SYSTEMIC_SX_PATTERNS.some((p) => p.test(soap));
}

function mentionsHospitalizationDecision(soap: string): boolean {
  return HOSPITALIZATION_PATTERNS.some((p) => p.test(soap));
}

function mentionsLifeThreat(soap: string): boolean {
  return LIFE_THREAT_PATTERNS.some((p) => p.test(soap));
}

function mentionsLabsOrImaging(soap: string): boolean {
  return LABS_IMAGING_PATTERNS.some((p) => p.test(soap));
}

/** Count of *distinct* tests/imaging mentioned in the SOAP. We do this
 *  by tokenizing test names directly rather than counting regex hits;
 *  multiple patterns firing on the same test (e.g. "UA in-office" +
 *  "UA confirms") would otherwise double-count. */
const DISTINCT_TEST_TOKENS = [
  'cbc', 'bmp', 'cmp', 'tsh', 'a1c', 'hba1c', 'lipid panel', 'urinalysis',
  'troponin', 'bnp', 'pt/ptt', 'inr', 'ldh', 'esr', 'crp', 'd-dimer',
  'ekg', 'ecg', 'cxr', 'chest x-ray', 'ct scan', 'mri', 'ultrasound',
  'x-ray', 'echocardiogram', 'stress test',
  'fingerstick', 'ua', 'culture',
];

function countLabsImagingMentions(soap: string): number {
  // Only count when the SOAP shows the test was *actually performed,
  // ordered, or reviewed* — gated by LABS_IMAGING_PATTERNS firing at
  // least once. If no clinical action context, return 0 even if the
  // word "BMP" appears in casual narrative ("BMP within 6 months").
  const hasAction = LABS_IMAGING_PATTERNS.some((p) => p.test(soap));
  if (!hasAction) return 0;
  const lower = soap.toLowerCase();
  let n = 0;
  const matched = new Set<string>();
  for (const tok of DISTINCT_TEST_TOKENS) {
    const re = new RegExp(`\\b${tok.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g');
    if (re.test(lower) && !matched.has(tok)) {
      matched.add(tok);
      n++;
    }
  }
  return n;
}

function mentionsHighRisk(soap: string): boolean {
  return HIGH_RISK_PATTERNS.some((p) => p.test(soap));
}

/** Detect Rx events from the plan text + structured rxDrafts. The
 *  rubric is explicit: "routine refill of long-stable medication w/
 *  no dose change" is LOW risk, NOT moderate. So a plan that only
 *  says "Continue X — refill 90 days" should not trip Rx-mgmt
 *  moderate. We separate "new/dose-change" Rx (which DO trip) from
 *  pure "continue/refill" mentions (which do NOT). */
export interface RxSignals {
  /** True when the plan contains a NEW Rx OR a dose-change. */
  newOrChanged: boolean;
  /** True when only refill/continue (no dose change) — LOW risk. */
  refillOnly: boolean;
}

const NEW_RX_PATTERNS: RegExp[] = [
  /\bstart(?:ed|ing)?\b[^.]{0,40}\b(\d+\s*(?:mg|mcg|units?|g\b|ml|puffs?))/i,
  /\b(?:initiated?|begin|begun)\b[^.]{0,40}\b(?:therapy|medication|insulin|treatment|rx)/i,
  /\binitiat(?:e|ed|ion)\b[^.]{0,40}\b(?:basal|insulin|antibiotic|statin|ace|arb|beta|ssri|opioid|pain)/i,
  /\binitiat(?:e|ed|ion)\b[^.]{0,40}\b\d+\s*(?:mg|mcg|units?)/i,
  /\bnew rx\b|\bnew prescription\b|\bnew medication\b/i,
  /\b(?:added|adding)\b[^.]{0,40}\b\w+\s+(?:\d+\s*(?:mg|mcg|units?))/i,
  // T-M5/Phase 5.2 calibration: a sentence-initial drug name + dose
  // (no "continue/refill" verb in front) is a strong new-Rx signal.
  // We require:
  //   * the line does NOT contain "continue", "refill", "no change",
  //     or "ongoing" (those are refill markers)
  //   * dose unit immediately after
  // The negative lookahead handles "Continue X 10mg" without false-firing.
  /(?<!continue\s)(?<!continued\s)(?<!continuing\s)(?<!refill\s)(?<!ongoing\s)\b(albuterol|nitrofurantoin|amoxicillin|azithromycin|prednisone|ciprofloxacin|insulin glargine|insulin|empagliflozin|sertraline|fluoxetine|tramadol|gabapentin|metolazone)\b[^.]{0,40}\b\d+\s*(?:mg|mcg|units?|puffs?|po\b|qhs|qd|bid|tid|qid|prn)/i,
];

const DOSE_CHANGE_PATTERNS: RegExp[] = [
  /\bincreased? (?:to|by)\b[^.]{0,30}\b\d+\s*(?:mg|mcg|units?)/i,
  /\bdecreased? (?:to|by)\b[^.]{0,30}\b\d+\s*(?:mg|mcg|units?)/i,
  /\bup-?titrat(?:e|ed|ing|ion)\b/i,
  /\b(?:taper|titrat(?:e|ed|ing))\b/i,
  /\badjust(?:ed|ing)?\s+(?:the )?dose/i,
  /\bdose\s+(?:adjust|change|increase|decrease)/i,
];

const REFILL_ONLY_PATTERNS: RegExp[] = [
  /\bcontinue\s+\w+\b[^.]{0,40}\b(?:refill|same dose|no change)/i,
  /\brefill\s+(?:90|60|30)[\s-]days?/i,
  /\bno (?:dose )?change\b/i,
  /\bcontinue\s+lisinopril\s+\d+\s*mg\s+daily\s*[—.-]\s*refill/i,
];

/** Best-effort signal from plain SOAP text (used when no structured
 *  rxDrafts are passed). */
export function detectRxSignalsFromSoap(soap: string): RxSignals {
  const newOrChanged =
    NEW_RX_PATTERNS.some((p) => p.test(soap)) ||
    DOSE_CHANGE_PATTERNS.some((p) => p.test(soap));
  const refillOnly =
    !newOrChanged && REFILL_ONLY_PATTERNS.some((p) => p.test(soap));
  return { newOrChanged, refillOnly };
}

/** Combine SOAP-text signals with structured rxDrafts (when present).
 *  Structured action='new'|'increase'|'decrease'|'discontinue' is the
 *  authoritative signal; SOAP text fills in when Rx Layer 7c hasn't
 *  populated drafts yet. */
function detectRxSignals(soap: string, rxDrafts: RxDraftRow[]): RxSignals {
  let newOrChanged = false;
  let refillOnly = false;
  for (const d of rxDrafts) {
    const a = (d.action ?? '').toLowerCase();
    if (a === 'new' || a === 'increase' || a === 'decrease' || a === 'discontinue') {
      newOrChanged = true;
    } else if (a === 'continue') {
      refillOnly = true;
    }
  }
  if (!newOrChanged && !refillOnly) {
    return detectRxSignalsFromSoap(soap);
  }
  // Structured signal wins — don't downgrade.
  return { newOrChanged, refillOnly: refillOnly && !newOrChanged };
}

/** Deterministic MDM judgement (rubric §4.4). Returns a shape
 *  compatible with MdmJudgement so callers can swap it in for the
 *  LLM payload without branching. The summaries / rationale are
 *  explicit about the heuristic origin. */
export function deterministicMdm(
  soap: string,
  icdCodes: IcdCodeRow[] = [],
  rxDrafts: RxDraftRow[] = [],
): MdmJudgement {
  const problemCount = icdCodes.length;
  const chronicCount = icdCodes.filter((c) => isChronicDisease(c.code)).length;
  const acuteSystemicCount = icdCodes.filter((c) =>
    hasSystemicMarker(soap, c.code),
  ).length;
  const rx = detectRxSignals(soap, rxDrafts);

  // ── Risk ────────────────────────────────────────────────────────
  let risk: ElementLevel = 'minimal';
  if (rx.refillOnly) risk = 'low'; // rubric §4.1 explicit: long-stable refill = low
  if (rx.newOrChanged) risk = 'moderate'; // Rx mgmt floor
  if (mentionsHighRisk(soap)) risk = 'high';
  if (mentionsHospitalizationDecision(soap)) risk = 'high';

  // ── Problems ────────────────────────────────────────────────────
  // Rubric §2: minimal = 1 self-limited or minor problem; low = 1
  // stable chronic OR 1 acute uncomplicated illness OR 2+ minor;
  // moderate = 2+ stable chronic OR exacerbation OR uncertain prognosis;
  // high = severe exacerbation / threat to life.
  //
  // The heuristic can't reliably tag "self-limited" vs "acute uncomplicated"
  // — we approximate using the SOAP body. Default 1 ICD = low (1 acute
  // uncomplicated illness OR 1 stable chronic). Only J06.x (acute viral
  // URI) and a small allow-list of self-limited codes downgrade to
  // minimal.
  let problems: ElementLevel = 'low';
  if (problemCount === 0) problems = 'minimal';
  if (problemCount === 1 && isSelfLimitedOnly(icdCodes)) problems = 'minimal';
  if (chronicCount >= 2) problems = 'moderate';
  if (acuteSystemicCount >= 1) problems = 'moderate';
  if (mentionsLifeThreat(soap)) problems = 'high';

  // ── Data ────────────────────────────────────────────────────────
  let data: ElementLevel = 'minimal';
  const labsHits = countLabsImagingMentions(soap);
  if (labsHits >= 1) data = 'low';
  if (labsHits >= 3) data = 'moderate';

  const tier = resolveTier(problems, data, risk);

  return {
    tier,
    elements: {
      problems: {
        level: problems,
        summary: `Heuristic: ${problemCount} problem(s); ${chronicCount} chronic; ${acuteSystemicCount} acute-systemic.`,
      },
      data: {
        level: data,
        summary: `Heuristic: ${labsHits} labs/imaging mention(s).`,
      },
      risk: {
        level: risk,
        summary: rx.newOrChanged
          ? 'Heuristic: new or dose-changed Rx → Rx-mgmt moderate floor.'
          : rx.refillOnly
            ? 'Heuristic: stable-med refill only → low risk per rubric §4.1.'
            : 'Heuristic: minimal risk markers detected.',
      },
    },
    confidence: 0.55, // fallback is intentionally low-confidence
    rationale: `Deterministic fallback (rubric §4.4): problems=${problems}, data=${data}, risk=${risk}; 2-of-3 → ${tier}.`,
  };
}
