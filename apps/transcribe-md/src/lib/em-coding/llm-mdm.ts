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
  claudeSonnet46CostCents,
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

/** Build the system prompt verbatim per rubric §4.1. */
const SYSTEM_PROMPT = [
  'You are an expert AMA 2021 E&M auditor. Given a SOAP note, judge the MDM (medical decision making) tier per the AMA 2021 Office E&M guidelines. Use the 2-of-3 rule: tier = the 2nd-highest of (A) problems addressed, (B) data reviewed, (C) risk of complications.',
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
  'Rules:',
  '- tier MUST equal the 2nd-highest of problems/data/risk levels',
  '- confidence 0.95+ for unambiguous cases (clear textbook examples)',
  '- confidence 0.70-0.94 for typical PCP encounters with some judgment calls',
  '- confidence <0.70 for genuinely ambiguous cases',
  '- Rx management = automatic moderate-risk floor (do not assign "low" risk to any encounter that prescribes a new medication or adjusts an existing one)',
  '- Decision-not-to-resuscitate, hospitalization decision, parenteral controlled substances = automatic high-risk floor',
  '- "Routine refill of long-stable medication" with no dose change = low-risk (NOT moderate)',
  '- New diagnostic uncertainty = at least moderate-problems',
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
  const userPrompt = args.soap.trim();
  const purpose = 'judge' as const;
  const aiLogContext = {
    practiceId: args.practiceId,
    visitId: args.visitId ?? null,
    userId: args.userId ?? null,
    purpose,
  };

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

      // Telemetry — same shape modelClient.completeText would have written.
      logAiCall({
        ...aiLogContext,
        provider: 'anthropic',
        model: MODEL,
        promptHash,
        latencyMs,
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
        costUsdCents: claudeSonnet46CostCents(
          response.usage.input_tokens,
          response.usage.output_tokens,
        ),
        success: true,
      });
      logApiUsage(
        buildAnthropicUsage(
          {
            userId: aiLogContext.userId,
            practiceId: aiLogContext.practiceId,
            visitId: aiLogContext.visitId,
            metadata: { purpose, latencyMs, cacheControl: 'ephemeral' },
          },
          response.usage.input_tokens,
          response.usage.output_tokens,
          MODEL,
          purpose,
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
