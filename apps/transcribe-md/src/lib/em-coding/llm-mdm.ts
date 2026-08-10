// ============================================================================
// E&M Coding — LLM MDM judge (Phase 5.2)
// ----------------------------------------------------------------------------
// The LLM half of the engine. Calls Claude Sonnet directly via the
// Anthropic SDK so we can attach `cache_control: { type: 'ephemeral' }`
// to the rubric system prompt block (Anthropic prompt caching, rubric
// §4.2). Caches the JUDGEMENT result in Redis with a 7-day TTL on top
// of that. Cache key is SHA-256 of the normalized SOAP body
// (whitespace-collapsed, lowercased). Cache bypass triggers when the
// SOAP edit changes >20% of characters since the cached version.
//
// Why bypass ModelClient? The shared CompleteTextArgs.system field is
// typed as `string` (packages/ai/src/model-client.ts:53). Adding the
// Anthropic prompt-cache control requires an array of content blocks.
// Bypassing keeps the change scoped to this file (no cross-branch type
// drift on the shared package). Telemetry (logAiCall + logApiUsage) is
// preserved by importing the same helpers ModelClient uses internally.
//
// Cost shape (rubric §4.2 + Anthropic prompt caching pricing):
//   - Cache miss   (cold call):    full input tokens billed
//   - Cache hit    (≤5 min repeat): 90% input-token cost reduction
// The same ~1.5K-token rubric system prompt on every call → typical
// re-score traffic hits the warm cache.
//
// Failure modes (rubric §4.3):
//   * 5xx / timeout → fall back to deterministicMdm with llmJudged:false
//   * JSON parse error → retry once with stricter prompt; then fall back
//
// The output schema matches MdmJudgement exactly (rubric §4.1).
// ============================================================================

import { createHash } from 'node:crypto';
import Anthropic from '@anthropic-ai/sdk';
import {
  hashPrompt,
  logAiCall,
  logApiUsage,
  buildAnthropicUsage,
  claudeCostCents,
  readAnthropicRequestId,
  // B4 step 3 — the mocked judge call still meters. See the block in
  // `callClaudeMdm`; the shared constant is what stops the two mock meters
  // drifting apart.
  MOCK_FIXTURE_USAGE,
} from '@meddoc/ai';
import { getRedis, isRedisReady } from '@/lib/redis';
import { log } from '@/lib/log';
import {
  deterministicMdm,
  type IcdCodeRow,
  type RxDraftRow,
} from './fallback-mdm';
import type { ElementLevel, MdmJudgement, MdmTier } from './types';

const MODEL = 'claude-sonnet-4-6';
// Phase 5.2 fix: bumped 8_000 → 30_000. Cold-call MDM judgement with
// the full ~1.5K-token rubric system prompt + structured JSON output
// realistically takes 6-10s on Sonnet 4-6; 8s missed ~50% of cold
// calls and silently degraded Path C to Path A. 30s matches the
// effective budget the worker SOAP-draft path uses (no explicit cap
// → SDK default ~600s; we cap at 30s here because the rail re-scores
// during reading and we want to bail to deterministic if the call is
// genuinely stuck rather than block the UI for minutes).
const TIMEOUT_MS = 30_000;
const CACHE_TTL_SECONDS = 7 * 24 * 60 * 60; // 7 days
const CACHE_KEY_PREFIX = 'em_mdm_cache:';
const REJUDGE_DRIFT_THRESHOLD = 0.20; // 20% character drift forces re-judge

/** Build the system prompt per rubric §4.1.
 *  The prompt is intentionally elaborated past the Anthropic prompt-cache
 *  1024-token minimum so cache_control: ephemeral actually engages.
 *  Every section below is substantive AMA 2021 guidance — no filler. */
const SYSTEM_PROMPT = [
  'You are an expert AMA 2021 E&M auditor. Given a SOAP note from an outpatient (Office or Other Outpatient) encounter, judge the MDM (medical decision making) tier per the AMA 2021 Office E&M guidelines. Use the 2-of-3 rule: tier = the 2nd-highest of (A) problems addressed, (B) data reviewed/analyzed, (C) risk of complications/morbidity from patient management. The 2021 changes removed history and exam from MDM scoring; you must score MDM based ONLY on these three elements as documented in the note.',
  '',
  'Output ONLY a JSON object matching this exact schema:',
  '',
  '{',
  '  "tier": "straightforward" | "low" | "moderate" | "high",',
  '  "elements": {',
  '    "problems": {',
  '      "level": "minimal" | "low" | "moderate" | "high",',
  '      "summary": "<1-2 sentence justification>"',
  '    },',
  '    "data": {',
  '      "level": "minimal" | "low" | "moderate" | "high",',
  '      "summary": "<1-2 sentence justification>"',
  '    },',
  '    "risk": {',
  '      "level": "minimal" | "low" | "moderate" | "high",',
  '      "summary": "<1-2 sentence justification>"',
  '    }',
  '  },',
  '  "confidence": 0.0..1.0,',
  '  "rationale": "<2-4 sentences explaining how 2-of-3 was resolved>"',
  '}',
  '',
  '== Element A: Problems addressed at the encounter ==',
  'minimal: 1 self-limited or minor problem (e.g., insect bite, simple URI without complication).',
  'low: 2+ self-limited problems; OR 1 stable chronic illness; OR 1 acute uncomplicated illness or injury.',
  'moderate: 1 chronic illness with exacerbation, progression, or side effects of treatment; OR 2+ stable chronic illnesses; OR 1 undiagnosed new problem with uncertain prognosis; OR 1 acute illness with systemic symptoms; OR 1 acute complicated injury.',
  'high: 1 chronic illness with severe exacerbation, progression, or side effects that pose threat to life or bodily function; OR 1 acute or chronic illness or injury that poses threat to life or bodily function (e.g., MI, pulmonary embolism, severe respiratory distress, progressive severe rheumatoid arthritis, psychiatric illness with potential threat to self or others, peritonitis, acute renal failure).',
  '',
  '== Element B: Amount and complexity of data to be reviewed and analyzed ==',
  'minimal: minimal or no data reviewed.',
  'low: any combination of 2 from: review of prior external notes from each unique source; review of result(s) of each unique test; ordering of each unique test; assessment requiring an independent historian.',
  'moderate: any combination of 3 from the same set as low; OR independent interpretation of a test performed by another physician/QHP not separately reported; OR discussion of management or test interpretation with external physician/QHP/source.',
  'high: any combination of 3 from the low-set, AND independent interpretation of a test, AND discussion of management with external physician/QHP. (Effectively the most complex data work-up.)',
  '',
  '== Element C: Risk of complications and/or morbidity or mortality of patient management ==',
  'minimal: minimal risk of morbidity from additional diagnostic testing or treatment.',
  'low: low risk (e.g., OTC drugs, minor surgery without identified risk factors, PT/OT, IV fluids without additives).',
  'moderate: moderate risk of morbidity. Examples: prescription drug management; decision regarding minor surgery with identified patient or procedure risk factors; decision regarding elective major surgery without identified risk factors; diagnosis or treatment significantly limited by social determinants of health.',
  'high: high risk of morbidity. Examples: drug therapy requiring intensive monitoring for toxicity; decision regarding elective major surgery with identified risk factors; decision regarding emergency major surgery; decision regarding hospitalization or escalation of hospital-level care; decision not to resuscitate or to de-escalate care because of poor prognosis; parenteral controlled substances.',
  '',
  '== Hard rules (override element narratives if these apply) ==',
  '- "Prescription drug management" = ANY new Rx, dose change, increase, decrease, discontinuation, or class switch. → automatic moderate-risk floor. Do NOT assign "low" risk to any encounter that initiates or adjusts a medication.',
  '- "Routine refill of long-stable medication" with no dose change and no symptom change → low-risk (NOT moderate).',
  '- Decision regarding hospitalization, ICU transfer, or DNR/de-escalation → automatic high-risk floor.',
  '- Parenteral controlled substances administration or order → automatic high-risk floor.',
  '- New diagnostic uncertainty (workup launched without a leading diagnosis) → at least moderate-problems.',
  '- Drug therapy requiring intensive monitoring (warfarin INR, lithium levels, methotrexate, chemotherapy, cyclosporine, etc.) → high-risk.',
  '- Social determinants of health that significantly limit treatment options (housing instability blocking refrigerated insulin storage, financial barrier to a needed medication) → moderate-risk if explicitly documented.',
  '',
  '== Tier resolution (2-of-3) ==',
  'After scoring problems / data / risk independently, the tier MUST equal the 2nd-highest of those three levels. Examples:',
  '- [low, low, moderate] → 2nd-highest = low → tier = low',
  '- [moderate, low, moderate] → 2nd-highest = moderate → tier = moderate',
  '- [high, high, moderate] → 2nd-highest = high → tier = high',
  '- [moderate, minimal, high] → 2nd-highest = moderate → tier = moderate',
  '- [low, minimal, minimal] → 2nd-highest = minimal → tier = straightforward',
  'Map element-level → tier-level: minimal→straightforward, low→low, moderate→moderate, high→high.',
  '',
  '== Confidence calibration ==',
  '- 0.95+: textbook unambiguous case (e.g., simple URI follow-up; or florid DKA admission decision).',
  '- 0.85-0.94: typical PCP encounter with one or two minor judgment calls.',
  '- 0.70-0.84: meaningful judgment required (e.g., is this a "stable" chronic problem? does this lab review constitute "independent interpretation"?).',
  '- 0.50-0.69: genuinely ambiguous; reasonable auditors would disagree on at least one element.',
  '- < 0.50: documentation is too sparse to score reliably; flag low confidence in rationale.',
  '',
  '== Worked examples ==',
  '',
  'Example A — established patient, stable HTN refill (low MDM, → 99213):',
  '  S: 58F, established, HTN well-controlled on lisinopril 10mg × 3 yrs, BP 124/78, no symptoms, here for refill.',
  '  O: BP 124/78, HR 72, BMI 27. Heart RRR no murmur. Lungs CTA. No edema.',
  '  A/P: 1) Essential HTN, stable. Continue lisinopril 10mg daily. Recheck BP in 6 mo.',
  '  Scoring: problems=low (1 stable chronic illness). data=minimal (no labs/imaging this visit, no external records). risk=low (routine refill, no dose change, long-stable medication). 2-of-3: [low, minimal, low] → 2nd-highest=low → tier=low.',
  '',
  'Example B — established patient, multi-condition with adjustment (moderate MDM, → 99214):',
  '  S: 65M, established, T2DM + HTN + hyperlipidemia. A1c up from 7.1 to 7.8 over 6 mo. Reports occasional dizziness on standing. BP 142/88.',
  '  O: BP 142/88 sitting, 128/76 standing. Foot exam normal. Recent labs: A1c 7.8, LDL 96, BMP normal.',
  '  A/P: 1) T2DM, A1c uptrending — increase metformin to 1000mg BID, recheck A1c in 3 mo. 2) HTN — add HCTZ 12.5mg daily. 3) Hyperlipidemia — continue atorvastatin.',
  '  Scoring: problems=moderate (2+ stable chronic illnesses, plus 1 chronic illness with progression — A1c rise). data=low (2 from set: review of labs from external lab + ordering A1c recheck). risk=moderate (prescription drug management — metformin dose increase + new HCTZ). 2-of-3: [moderate, low, moderate] → 2nd-highest=moderate → tier=moderate.',
  '',
  'Example C — acute decompensation requiring hospitalization decision (high MDM, → 99215):',
  '  S: 72F with known CHF, presents with progressive dyspnea × 3 days, orthopnea, 6 lb weight gain. Chest pain denied. SOB at rest now.',
  '  O: HR 108, BP 156/92, SpO2 89% on room air, RR 24. JVD 12 cm. Crackles bilateral bases. 2+ pitting edema. BNP 1840 (prior baseline ~400).',
  '  A/P: 1) Acute on chronic CHF exacerbation, NYHA class IV. Plan: admit to hospital for IV diuresis, telemetry, echo. Discussed risk/benefits of hospitalization vs. outpatient with patient and family — admission elected. 2) Continue home meds; will adjust diuretic in-house.',
  '  Scoring: problems=high (chronic illness with severe exacerbation posing threat to bodily function — class IV CHF, hypoxic). data=moderate (review of recent BNP + prior baseline + ordering echo, plus discussion w/ family — independent historian element). risk=high (decision regarding hospitalization, plus drug therapy — IV diuretics — req intensive monitoring). 2-of-3: [high, moderate, high] → 2nd-highest=high → tier=high.',
  '',
  '== Documentation traps to watch for ==',
  '- "Stable on current regimen" + dose change in same visit → still moderate-risk (Rx mgmt rule overrides).',
  '- "Reviewed labs from outside ED visit last week" without any specifics → counts as 1 data-element only if ATTRIBUTABLE to a specific external source; otherwise treat as low-data.',
  '- "Discussed with cardiology" without specifying that cardiology is a separate physician/QHP → ambiguous; default to NOT counting as data-discussion unless clearly external.',
  '- "Considered admission, declined" → counts as decision regarding hospitalization → high-risk (the deliberation itself qualifies, regardless of outcome).',
  '- New chronic diagnosis at this visit (not a follow-up) → at least moderate-problems (undiagnosed → diagnosed counts as new problem with established diagnosis but moderate baseline).',
  '- Multiple problems where ONE is high — final tier follows the 2-of-3 rule, not the maximum element.',
  '',
  'In the rationale field, name each element\'s level and justify with a phrase from the note. State the 2-of-3 resolution arithmetic plainly: "[problems-level, data-level, risk-level] → 2nd-highest = X → tier=X". Keep rationale to 2-4 sentences.',
].join('\n');

/** Normalize SOAP body for cache-key + drift comparison: collapse
 *  whitespace, lowercase, strip line numbers. The result is stable
 *  across cosmetic edits so the cache hit rate stays high. */
export function normalizeSoap(soap: string): string {
  return soap
    .replace(/^\s*\d+[.):]\s+/gm, '') // strip "1. " / "1) " / "1: " line numbers
    .replace(/\s+/g, ' ')
    .toLowerCase()
    .trim();
}

/** SHA-256 cache key over the normalized SOAP. */
export function buildCacheKey(soap: string): string {
  const norm = normalizeSoap(soap);
  const hash = createHash('sha256').update(norm).digest('hex');
  return `${CACHE_KEY_PREFIX}${hash}`;
}

/** Compute the character-level drift ratio between two SOAP bodies.
 *  Used to decide whether to re-judge a cached entry (rubric §4.2:
 *  >20% drift forces re-judge). The implementation is intentionally
 *  cheap — we count the absolute difference in length normalized by
 *  the max length, plus a sample of mid-string char mismatches.
 *  Fast O(n) approximation; not a true Levenshtein distance.  */
export function charDistanceRatio(a: string, b: string): number {
  const an = normalizeSoap(a);
  const bn = normalizeSoap(b);
  if (an === bn) return 0;
  const maxLen = Math.max(an.length, bn.length);
  if (maxLen === 0) return 0;

  // Length component.
  const lenDiff = Math.abs(an.length - bn.length);
  // Sample comparison every Nth char (to keep it cheap on very long
  // notes). For a typical 2000-char SOAP this samples 200 positions.
  const minLen = Math.min(an.length, bn.length);
  let mismatch = lenDiff;
  const step = Math.max(1, Math.floor(minLen / 200));
  for (let i = 0; i < minLen; i += step) {
    if (an[i] !== bn[i]) mismatch += step;
  }
  return Math.min(1, mismatch / maxLen);
}

/** Validate an LLM response shape — returns null if not a valid
 *  MdmJudgement, otherwise the typed object. */
export function validateMdmJudgement(raw: unknown): MdmJudgement | null {
  if (!raw || typeof raw !== 'object') return null;
  const o = raw as Record<string, unknown>;
  const tiers: MdmTier[] = ['straightforward', 'low', 'moderate', 'high'];
  const levels: ElementLevel[] = ['minimal', 'low', 'moderate', 'high'];

  if (typeof o.tier !== 'string' || !tiers.includes(o.tier as MdmTier)) return null;
  if (!o.elements || typeof o.elements !== 'object') return null;
  const e = o.elements as Record<string, unknown>;
  for (const key of ['problems', 'data', 'risk'] as const) {
    const sub = e[key];
    if (!sub || typeof sub !== 'object') return null;
    const subO = sub as Record<string, unknown>;
    if (typeof subO.level !== 'string' || !levels.includes(subO.level as ElementLevel)) return null;
    if (typeof subO.summary !== 'string') return null;
  }
  if (typeof o.confidence !== 'number' || o.confidence < 0 || o.confidence > 1) return null;
  if (typeof o.rationale !== 'string') return null;
  return raw as MdmJudgement;
}

/** Try to parse a JSON object from the model response. Tolerates
 *  ```json fences and prose preamble before/after the JSON block. */
function tryParseJson(text: string): unknown {
  // Direct parse fast-path.
  try {
    return JSON.parse(text);
  } catch {
    /* fall through */
  }
  // Strip code fences.
  const fenced = text.match(/```(?:json)?\s*\n?([\s\S]*?)\n?```/);
  if (fenced) {
    try {
      return JSON.parse(fenced[1].trim());
    } catch {
      /* fall through */
    }
  }
  // Greedy first-{ last-} grab.
  const open = text.indexOf('{');
  const close = text.lastIndexOf('}');
  if (open >= 0 && close > open) {
    try {
      return JSON.parse(text.slice(open, close + 1));
    } catch {
      /* fall through */
    }
  }
  return null;
}

/** Read an MdmJudgement from Redis cache; returns null on miss/error. */
async function readCache(key: string): Promise<MdmJudgement | null> {
  if (!isRedisReady()) return null;
  try {
    const redis = getRedis();
    const blob = await redis.get(key);
    if (!blob) return null;
    const parsed = JSON.parse(blob);
    return validateMdmJudgement(parsed);
  } catch (err) {
    log.warn('em-coding:llm-mdm', 'cache read failed', {
      key,
      error: err instanceof Error ? err.message : String(err),
    });
    return null;
  }
}

/** Write the judgement to Redis with the 7-day TTL. */
async function writeCache(key: string, j: MdmJudgement): Promise<void> {
  if (!isRedisReady()) return;
  try {
    const redis = getRedis();
    await redis.set(key, JSON.stringify(j), 'EX', CACHE_TTL_SECONDS);
  } catch (err) {
    log.warn('em-coding:llm-mdm', 'cache write failed', {
      key,
      error: err instanceof Error ? err.message : String(err),
    });
  }
}

export interface JudgeMdmArgs {
  soap: string;
  practiceId: string;
  visitId?: string;
  userId?: string | null;
  /** Optional structured signals — used only by the deterministic
   *  fallback when the LLM is unavailable. */
  icdCodes?: IcdCodeRow[];
  rxDrafts?: RxDraftRow[];
  /** When provided, the cache lookup is skipped if the new SOAP drifts
   *  by >20% from this prior body. */
  priorSoap?: string;
}

export interface JudgeMdmResult {
  judgement: MdmJudgement;
  /** True iff the cache served the response. */
  cacheHit: boolean;
  /** True iff the LLM produced this judgement (false on fallback). */
  llmJudged: boolean;
}

/** The main entry point. Looks up the cache; if miss (or drift
 *  triggered), calls Claude; on any failure falls back to the
 *  deterministic heuristic. */
export async function judgeMdm(args: JudgeMdmArgs): Promise<JudgeMdmResult> {
  const cacheKey = buildCacheKey(args.soap);

  // Drift bypass — only if a priorSoap was provided.
  let bypassCache = false;
  if (args.priorSoap !== undefined) {
    const drift = charDistanceRatio(args.priorSoap, args.soap);
    if (drift > REJUDGE_DRIFT_THRESHOLD) bypassCache = true;
  }

  if (!bypassCache) {
    const cached = await readCache(cacheKey);
    if (cached) {
      return { judgement: cached, cacheHit: true, llmJudged: true };
    }
  }

  // Cache miss / bypass: call Claude.
  const llmResult = await callClaudeMdm(args);
  if (llmResult) {
    await writeCache(cacheKey, llmResult);
    return { judgement: llmResult, cacheHit: false, llmJudged: true };
  }

  // LLM failed — fall back to deterministic heuristic.
  const fallback = deterministicMdm(
    args.soap,
    args.icdCodes ?? [],
    args.rxDrafts ?? [],
  );
  return { judgement: fallback, cacheHit: false, llmJudged: false };
}

// Singleton Anthropic client (same pattern as packages/ai/src/anthropic.ts).
// We instantiate locally so we can pass system as an array of content
// blocks with cache_control attached to the rubric block.
let anthropicClient: Anthropic | null = null;
function getAnthropicClient(): Anthropic {
  if (anthropicClient) return anthropicClient;
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY is not set.');
  anthropicClient = new Anthropic({ apiKey });
  return anthropicClient;
}

/** Calls the LLM up to 2 times (per rubric §4.3 retry-once-on-parse-fail
 *  policy). Returns null if both attempts fail or time out. */
async function callClaudeMdm(args: JudgeMdmArgs): Promise<MdmJudgement | null> {
  // ⚠️ MOCK SHORT-CIRCUIT — ADDED 2026-08-05. THIS PATH DID NOT HONOUR
  // `MOCK_AI_CALLS` AND MADE REAL ANTHROPIC CALLS FROM CI.
  //
  // Found in the e2e job's app logs: `em-coding:llm-mdm  llm call failed
  // 401 invalid x-api-key`. They failed only because CI's key is a dummy —
  // which is the second condition doing exactly the job AGENTS.md assigns it:
  // "MOCK_AI_CALLS=true stops calls only while every code path honours the
  // flag; dummy credentials are what survives a code regression."
  //
  // ⚠️ THE COMPOSE FILE WAS NOT THE PROBLEM, AND THAT IS THE POINT.
  // `docker-compose.qa.yml` hardcodes `MOCK_AI_CALLS: "true"` for both app and
  // worker (not a `${VAR:-}` default), and the calls happened anyway. Reading
  // config proves nothing about a path that never reads it —
  // `check-qa-mock-posture.sh` inspects container env and would have reported
  // this stack GREEN while it was calling a vendor. Same shape as the 298 real
  // calls of 2026-07-28.
  //
  // RETURNING `null` IS THE CORRECT MOCK, not a stub judgement: null is the
  // established "the LLM did not produce this" signal, and `judgeMdm` already
  // routes it to a DETERMINISTIC fallback that scores from the structured
  // signals. So the mock path yields a real, reproducible MDM level with
  // `llmJudged: false` — which is true, and which the E/M fixtures can assert.
  // A fabricated judgement here would have been a mock that lies about its own
  // provenance.
  //
  // ── B4 STEP 3, 2026-08-10 — AND IT NOW METERS ON THE WAY OUT ─────────────
  //
  // The `null` above is still exactly right and is NOT what changed. What was
  // wrong is that returning it emitted ZERO `api_usage_events` rows, so B4's
  // gate — "one full QA pipeline run produces one event per stage" — was
  // UNSATISFIABLE for `judge` by construction. Same defect ruling 81 removed
  // from Deepgram and embed, and ruling 82 from `tm_anchor_entailment`.
  //
  //     ZERO USAGE EVENTS LOOKS EXACTLY LIKE A WORKING METER THAT FOUND
  //     NOTHING TO RECORD.
  //
  // ⚠️ THE TWO FACTS ARE SEPARABLE, AND SEPARATING THEM IS THE WHOLE ITEM.
  // "A judge call was made" and "the LLM produced a judgement" are different
  // claims. We record the first and decline the second. Ruling 82 forbids
  // fabricating a judgement to make the meter tick — so nothing here builds a
  // parseable `MdmJudgement`, and `llmJudged: false` stays TRUE downstream.
  //
  // ⚠️ WHY THIS SITE AND NOT THE SHARED SEAM. Every other mocked Anthropic
  // path gets its meter free from `anthropic.ts`. This file builds its own
  // client (see the header: `CompleteTextArgs.system` is typed `string` and
  // cache_control needs content blocks), so it is the ONE path that has to
  // mark its own row. It reads `MOCK_FIXTURE_USAGE` rather than its own
  // literal so the two mock meters cannot drift apart.
  //
  // ⚠️ NO `logAiCall` HERE, AND NOT BY OMISSION. `ai_calls` is a
  // REAL-VENDOR-CALLS-ONLY table (ruling 66) and `log.ts` already enforces
  // that centrally — `logAiCall` returns early under the flag. Calling it
  // would be a no-op; not calling it is the honest shape.
  //
  // ⚠️ `unitsSource: 'mock'` IS THE ONLY DISCRIMINATOR, DELIBERATELY. Ruling
  // 66 is "ONE discriminator on ONE table" — a `mocked: true` metadata key
  // would be a second one that every rollup would have to learn about. The
  // writer zeroes the money columns and NULLs `requestId` off this marker
  // alone; see `logApiUsage`.
  //
  // ⚠️ AND THE GUARD STAYS ABOVE `args.soap.trim()`. `gate-mock-ai-honored`
  // asserts that POSITION — a flag read below the prompt-building line is not
  // a short-circuit, because the request would already exist. Metering does
  // not need the prompt, so nothing here reaches for it.
  const purpose = 'judge' as const;
  const aiLogContext = {
    practiceId: args.practiceId,
    visitId: args.visitId ?? null,
    userId: args.userId ?? null,
    purpose,
  };

  if (process.env.MOCK_AI_CALLS === 'true') {
    logApiUsage(
      buildAnthropicUsage(
        {
          unitsSource: 'mock',
          userId: aiLogContext.userId,
          practiceId: aiLogContext.practiceId,
          visitId: aiLogContext.visitId,
          // Never minted. `requestId IS NOT NULL ⇒ unitsSource = 'vendor'`
          // (ruling 72a) — and because `logApiUsage` is fire-and-forget, a
          // violation would be SWALLOWED and the stage would silently return
          // to zero events with every line here looking correct.
          requestId: null,
          // No `latencyMs`, no `cacheControl` — neither happened. The real
          // path records both because both are observations there.
          metadata: { purpose },
        },
        MOCK_FIXTURE_USAGE.input_tokens,
        MOCK_FIXTURE_USAGE.output_tokens,
        MODEL,
        purpose,
      ),
    );
    return null;
  }

  const userPrompt = args.soap.trim();

  // Attempt 1 — standard prompt.
  let attempt: 'first' | 'retry' = 'first';
  let systemForAttempt = SYSTEM_PROMPT;

  const client = getAnthropicClient();

  for (let i = 0; i < 2; i++) {
    const promptHash = hashPrompt(systemForAttempt, userPrompt);
    const started = Date.now();
    try {
      // Direct SDK call so we can attach cache_control to the system
      // prompt block. The rubric is identical on every call → 5-min
      // ephemeral cache hit on warm calls, 90% input-token cost
      // reduction. See rubric §4.2.
      const response = await withTimeout(
        client.messages.create({
          model: MODEL,
          max_tokens: 1024,
          temperature: 0,
          system: [
            {
              type: 'text',
              text: systemForAttempt,
              cache_control: { type: 'ephemeral' },
            },
          ],
          messages: [{ role: 'user', content: userPrompt }],
        }),
        TIMEOUT_MS,
      );

      const latencyMs = Date.now() - started;
      const text = response.content
        .filter((b): b is Anthropic.TextBlock => b.type === 'text')
        .map((b) => b.text)
        .join('\n')
        .trim();

      // This is the only caller in the pipeline that attaches
      // `cache_control: ephemeral`, so it's the path that actually
      // produces non-zero cache_read / cache_creation usage. We have
      // to extract those fields from the SDK response and pass them
      // through to both telemetry sinks so the 0.10x / 1.25x billing
      // multipliers land on AiCall + ApiUsageEvent rows. The
      // `claudeCostCents` dispatcher applies the multipliers
      // internally — it's the same path anthropic.ts uses, just
      // invoked from outside the shared wrapper here because llm-mdm
      // needs the raw SDK to attach cache_control blocks.
      const cacheRead = response.usage.cache_read_input_tokens ?? 0;
      const cacheCreation = response.usage.cache_creation_input_tokens ?? 0;
      logAiCall({
        ...aiLogContext,
        provider: 'anthropic',
        model: MODEL,
        promptHash,
        latencyMs,
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
        cacheReadInputTokens: cacheRead,
        cacheCreationInputTokens: cacheCreation,
        costUsdCents: claudeCostCents(
          MODEL,
          response.usage.input_tokens,
          response.usage.output_tokens,
          cacheRead,
          cacheCreation,
        ),
        success: true,
        // B1-b step 1. This caller builds its own `new Anthropic(...)` to attach
        // cache_control, so it never passed through anthropic.ts's capture — and
        // B1-a's gate only watched that file. `worker.ts` pre-warms judgeMdm on
        // every visit, so this one omission made ~18% of a visit's vendor calls
        // structurally NULL, which the sizing would have read as the VENDOR's
        // silence rather than ours. Read direct off `response`; see
        // vendor-request-id.ts for why a spread would return null here.
        requestId: readAnthropicRequestId(response),
      });
      logApiUsage(
        buildAnthropicUsage(
          {
            // B0: a REAL vendor call — see UnitsSource.
            unitsSource: 'vendor',
            userId: aiLogContext.userId,
            practiceId: aiLogContext.practiceId,
            visitId: aiLogContext.visitId,
            // B1-b step 2 — the SAME id the `logAiCall` directly above records.
            // Step 1 threaded it into `ai_calls` only, so this row minted a UUID
            // and the two tables disagreed about one call. `worker.ts` pre-warms
            // judgeMdm on every visit, which makes this the highest-volume of
            // the three sites that were still fabricating.
            requestId: readAnthropicRequestId(response),
            metadata: { purpose, latencyMs, cacheControl: 'ephemeral' },
          },
          response.usage.input_tokens,
          response.usage.output_tokens,
          MODEL,
          purpose,
          cacheRead,
          cacheCreation,
        ),
      );

      const result = { text };

      const parsed = tryParseJson(result.text);
      const judgement = validateMdmJudgement(parsed);
      if (judgement) {
        // Force 2-of-3 invariant: the LLM might output a tier that
        // doesn't match its own elements. Re-resolve from elements
        // to guarantee consistency.
        const { resolveTier } = await import('./fallback-mdm');
        const resolved = resolveTier(
          judgement.elements.problems.level,
          judgement.elements.data.level,
          judgement.elements.risk.level,
        );
        if (resolved !== judgement.tier) {
          log.info('em-coding:llm-mdm', 'tier mismatch — using resolved', {
            visitId: args.visitId,
            llmTier: judgement.tier,
            resolvedTier: resolved,
          });
          judgement.tier = resolved;
        }
        return judgement;
      }

      // Parse / shape failure — retry once with a stricter system message.
      log.warn('em-coding:llm-mdm', 'parse/shape failed', {
        visitId: args.visitId,
        attempt,
        rawSnippet: result.text.slice(0, 200),
      });
      attempt = 'retry';
      systemForAttempt = `${SYSTEM_PROMPT}\n\nIMPORTANT: Output the JSON object alone, no preamble, no \`\`\` fences, no commentary. The first character of your response MUST be '{' and the last character MUST be '}'.`;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      log.warn('em-coding:llm-mdm', 'llm call failed', {
        visitId: args.visitId,
        attempt,
        error: msg,
      });
      // ── B2 — THIS BRANCH USED TO WRITE TO NEITHER TABLE.
      //
      // Every other failure path in the codebase leaves an `ai_calls` row; this
      // one left a `log.warn` and nothing else, so a failed judge was invisible
      // to both meters AND to §C.3's own diagnostic query (which reads
      // `ai_calls`). `worker.ts` pre-warms `judgeMdm` on every visit, so this is
      // not a rare path. The row is TELEMETRY — it carries no tokens, because
      // there are none to carry.
      logAiCall({
        ...aiLogContext,
        provider: 'anthropic',
        model: MODEL,
        promptHash,
        latencyMs: Date.now() - started,
        success: false,
        errorCode: err instanceof Error ? err.name.toUpperCase() : 'UNKNOWN',
      });
      // ⚠️ AND NO USAGE ROW, DELIBERATELY — with a caveat worth writing down.
      //
      // `withTimeout` RACES the SDK promise; it does not abort the HTTP request.
      // So on the timeout branch Anthropic may well finish the call and bill it,
      // and we will never see the response that would tell us the token counts.
      // That is a REAL, STRUCTURAL CEILING on meter accuracy, not an omission
      // this item can close: the units do not exist on our side of the wire.
      // Inventing them is the one thing that would make it worse. Recorded in
      // RELAY.md as a known under-count with the only instrument that can size
      // it — a vendor invoice, which B3 already needs.
      // Network/5xx/timeout — bail without retry. The deterministic
      // fallback is the contract per rubric §4.3.
      return null;
    }
  }
  return null;
}

/** Race a promise against a timeout. */
function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`em-mdm timeout after ${ms}ms`)), ms);
    p.then(
      (v) => { clearTimeout(t); resolve(v); },
      (e) => { clearTimeout(t); reject(e); },
    );
  });
}
