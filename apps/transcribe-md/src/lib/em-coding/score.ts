// ============================================================================
// E&M Coding — master scoring entry-point (Phase 5.2)
// ----------------------------------------------------------------------------
// The single function the API route + server action call. Combines:
//   1. Deterministic counts (HPI / ROS / PFSH / exam, time hints)
//   2. LLM-judged MDM (or fallback heuristic) → satisfied.{problems,data,risk}
//   3. CPT code derivation from MDM tier + visit type
//   4. Bump-CTA computation
//
// Read-only on SOAP data — never writes back to soapNote / soapFinal
// (preservation rule from spec).
// ============================================================================

import {
  countExamSystems,
  countHpiElements,
  countPfshCategories,
  countRosSystems,
  detectTimeBasedHints,
} from './deterministic';
import { _internal as bumpInternal } from './bump-suggestion';
import {
  judgeMdm,
  type JudgeMdmArgs,
} from './llm-mdm';
import {
  deterministicMdm,
  type IcdCodeRow,
  type RxDraftRow,
} from './fallback-mdm';
import { parseSoapSections } from '@/lib/parse-soap-sections';

/** Best-effort extract of ICD-10-format codes mentioned in the
 *  Assessment section. Used when callers (test corpus, ad-hoc API
 *  callers) don't pass structured icdCodes — the fallback heuristic
 *  needs problem-count signal to lift `problems` above 'minimal'. */
function extractIcdsFromAssessment(soap: string): IcdCodeRow[] {
  const sections = parseSoapSections(soap);
  const assessment = sections.find((s) => s.key === 'A')?.body ?? '';
  const codes = new Set<string>();
  // ICD-10 shape: a letter, 2 digits, optional dot + 1-4 alphanumerics
  // (the 4-char extension covers injury codes like S93.401A and the
  // expanded subcategory codes like H66.001).
  // Match inside parentheses: "(J20.9)", "(I10)", "(S93.401A)".
  const re = /\(([A-Z]\d{2}(?:\.[A-Z\d]{1,4})?)\)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(assessment))) {
    codes.add(m[1]);
  }
  return Array.from(codes).map((code) => ({ code }));
}
import {
  MDM_TO_CODE,
  RUBRIC_VERSION,
  TIME_BAND,
  ESTABLISHED_LADDER,
  NEW_LADDER,
} from './rubric';
import type {
  EmCode,
  EmScore,
  MdmJudgement,
  TimeFitScore,
  VisitType,
} from './types';

export interface ComputeEmScoreOptions {
  /** New patient vs established (drives 99202-99205 vs 99211-99215). */
  visitType?: VisitType;
  /** Pre-cached LLM judgement (per server action: load Redis cache, pass
   *  it in to skip the async LLM call entirely if present). When
   *  undefined, the engine calls judgeMdm() which handles its own cache
   *  + fallback path internally. When null, the deterministic fallback
   *  is used directly (no LLM call). */
  mdmCachedJudgement?: MdmJudgement | null;
  /** Tenant for AiCall logging — required when judgeMdm is invoked. */
  practiceId?: string;
  visitId?: string;
  userId?: string | null;
  /** Structured signals — used by the deterministic fallback path. */
  icdCodes?: IcdCodeRow[];
  rxDrafts?: RxDraftRow[];
  /** When the SOAP has been edited, pass the prior body so the cache
   *  can apply its >20% drift bypass. */
  priorSoap?: string;
}

/** Master scoring entry-point. Pure async; returns EmScore.
 *
 *  Three modes for MDM:
 *    1. opts.mdmCachedJudgement provided        → use it verbatim, llmJudged=true
 *    2. opts.mdmCachedJudgement === null        → deterministic fallback, llmJudged=false
 *    3. opts.mdmCachedJudgement === undefined   → call judgeMdm (cache+LLM+fallback) */
export async function computeEmScore(
  soap: string,
  opts: ComputeEmScoreOptions = {},
): Promise<EmScore> {
  const visitType: VisitType = opts.visitType ?? 'established';

  // ── 1. Deterministic counts ──────────────────────────────────────
  const hpi = countHpiElements(soap);
  const ros = countRosSystems(soap);
  const pfsh = countPfshCategories(soap);
  const exam = countExamSystems(soap);
  const timeHint = detectTimeBasedHints(soap);

  // ── 2. MDM tier ──────────────────────────────────────────────────
  let judgement: MdmJudgement;
  let llmJudged: boolean;
  let cacheHit: boolean;

  // When callers don't pass structured icdCodes, scrape the Assessment
  // section so the fallback heuristic has problem-count signal. Same
  // for tests — corpus fixtures author the SOAP with parenthesized ICDs.
  const icdCodes =
    opts.icdCodes && opts.icdCodes.length > 0
      ? opts.icdCodes
      : extractIcdsFromAssessment(soap);

  if (opts.mdmCachedJudgement === null) {
    // Caller explicitly asked for fallback (e.g. test harness or a
    // synchronous code path that can't await the LLM).
    judgement = deterministicMdm(soap, icdCodes, opts.rxDrafts ?? []);
    llmJudged = false;
    cacheHit = false;
  } else if (opts.mdmCachedJudgement) {
    // Caller pre-fetched from cache (or a prior call) — use verbatim.
    judgement = opts.mdmCachedJudgement;
    llmJudged = true;
    cacheHit = true;
  } else if (opts.practiceId) {
    // Full path: judgeMdm handles cache + LLM + fallback internally.
    const judgeArgs: JudgeMdmArgs = {
      soap,
      practiceId: opts.practiceId,
      visitId: opts.visitId,
      userId: opts.userId ?? null,
      icdCodes,
      rxDrafts: opts.rxDrafts,
      priorSoap: opts.priorSoap,
    };
    const r = await judgeMdm(judgeArgs);
    judgement = r.judgement;
    llmJudged = r.llmJudged;
    cacheHit = r.cacheHit;
  } else {
    // No practiceId provided and no cached judgement → fallback only.
    // (This is the corpus-test path: tests call with just the SOAP body.)
    judgement = deterministicMdm(soap, icdCodes, opts.rxDrafts ?? []);
    llmJudged = false;
    cacheHit = false;
  }

  // ── 3. Code derivation ──────────────────────────────────────────
  const mdmTier = judgement.tier;
  const code: EmCode = MDM_TO_CODE[visitType][mdmTier];

  // ── 4. Bump suggestion (next-level diff) ────────────────────────
  const bumpScoreInput: EmScore = {
    code,
    mdmTier,
    visitType,
    satisfied: {
      hpiElements: hpi.count,
      rosSystems: ros.count,
      pfshCategories: pfsh.count,
      examSystems: exam.count,
      problems: judgement.elements.problems.level,
      data: judgement.elements.data.level,
      risk: judgement.elements.risk.level,
    },
    perElementConfidence: { hpi: hpi.confidence },
    bumpableTo: null,
    timeFitScore: null,
    llmJudged,
    rubricVersion: RUBRIC_VERSION,
    computedAt: new Date().toISOString(),
    cacheHit,
    mdmRationale: judgement.rationale,
    mdmConfidence: judgement.confidence,
  };

  // Threshold mirrored from bump-suggestion.ts (ALMOST_THERE_GAP_THRESHOLD).
  // Raised from 2 → 4 on 2026-05-12 to surface the bump CTA on text_notes
  // and voice_dictation visits whose deterministic counters land lower
  // than transcribed audio. Pre-fix: 0 EM_BUMP_APPLIED audits across 9
  // text_notes + 4 voice_dictation visits in the 30-day window; audio
  // worked because audio SOAPs are word-for-word and hit the 4/2/2/2
  // element floor naturally. Keep this constant in sync with
  // bump-suggestion.ts ALMOST_THERE_GAP_THRESHOLD or the page render
  // and the BumpModal will disagree on whether to show the CTA.
  const BUMP_GAP_THRESHOLD = 4;
  const next = bumpInternal.nextLevelUp(code);
  let bumpableTo: EmCode | null = null;
  let bumpGaps: string[] | undefined;
  if (next) {
    const required = bumpInternal.requirementsFor(next);
    const gaps = bumpInternal.diffRequirements(bumpScoreInput.satisfied, required);
    if (gaps.length <= BUMP_GAP_THRESHOLD) {
      bumpableTo = next;
      bumpGaps = gaps;
    }
  }

  // ── 5. Time-fit score ───────────────────────────────────────────
  let timeFitScore: TimeFitScore | null = null;
  if (timeHint.minutes !== null) {
    const ladder = visitType === 'established' ? ESTABLISHED_LADDER : NEW_LADDER;
    let bestFit: EmCode = code;
    for (const c of ladder) {
      const band = TIME_BAND[c];
      if (timeHint.minutes >= band.min && timeHint.minutes <= band.max) {
        bestFit = c;
        break;
      }
    }
    timeFitScore = {
      code: bestFit,
      minutesUsed: timeHint.minutes,
      band: TIME_BAND[bestFit].label,
    };
  }

  return {
    ...bumpScoreInput,
    bumpableTo,
    bumpGaps,
    timeFitScore,
  };
}
