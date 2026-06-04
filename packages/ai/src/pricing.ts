// ============================================================================
// @meddoc/ai — provider pricing helpers (T-M4)
// ----------------------------------------------------------------------------
// Every AiCall row can carry a costUsdCents so /settings → usage can sum
// cents for a unit-economics view later. Prices are env-overridable in
// case a provider changes their rate card mid-flight.
//
// Rates refreshed 2026-05-12 against the published Anthropic pricing
// page (https://docs.anthropic.com/en/docs/about-claude/pricing).
// Opus 4.7 launched at $15/$75 (Opus 4.x rate) and was subsequently
// cut to $5/$25 when the 4.5/4.6/4.7 family unified on the new
// pricing tier — the original constants below were 3x stale on input
// AND output, which alone explains the ~70-100% admin-dashboard
// overcount on visits where the Opus-driven layers (L4 SOAP draft,
// L5 critique, L7c Rx drafting) dominate the call mix.
//
//   Claude Sonnet 4.6   $3   / M input, $15  / M output  (unchanged)
//   Claude Opus 4.7     $5   / M input, $25  / M output  (was $15/$75)
//   Claude Haiku 4.5    $1   / M input, $5   / M output  (new — was absent)
//   Deepgram Nova-3 Med $0.0145 / min
//   (OpenAI: not used in T-M4; left unset)
//
// All values are INTEGER CENTS so summation is drift-free.
// ============================================================================

const DEFAULT_SONNET_INPUT_CENTS_PER_M = 300;   // $3.00 / M tokens
const DEFAULT_SONNET_OUTPUT_CENTS_PER_M = 1500; // $15.00 / M tokens
const DEFAULT_OPUS_INPUT_CENTS_PER_M = 500;     // $5.00  / M tokens (was 1500)
const DEFAULT_OPUS_OUTPUT_CENTS_PER_M = 2500;   // $25.00 / M tokens (was 7500)
const DEFAULT_HAIKU_INPUT_CENTS_PER_M = 100;    // $1.00  / M tokens
const DEFAULT_HAIKU_OUTPUT_CENTS_PER_M = 500;   // $5.00  / M tokens
const DEFAULT_DEEPGRAM_CENTS_PER_MIN = 1.45;    // $0.0145 / min

function envFloat(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const n = Number.parseFloat(raw);
  return Number.isFinite(n) ? n : fallback;
}

/** Per-million-tokens rate for Claude Sonnet 4.6 input. */
export function sonnetInputCentsPerM(): number {
  return envFloat('CLAUDE_SONNET_46_INPUT_CENTS_PER_M', DEFAULT_SONNET_INPUT_CENTS_PER_M);
}

/** Per-million-tokens rate for Claude Sonnet 4.6 output. */
export function sonnetOutputCentsPerM(): number {
  return envFloat('CLAUDE_SONNET_46_OUTPUT_CENTS_PER_M', DEFAULT_SONNET_OUTPUT_CENTS_PER_M);
}

/** Integer cents for a Claude Sonnet 4.6 call. Rounded half-up so we
 *  never under-report. Micro-tokens (input or output < ~3000) round to
 *  0 cents but still increment the sum via cost accumulation across
 *  multiple calls. */
export function claudeSonnet46CostCents(inputTokens: number, outputTokens: number): number {
  const inCents = (inputTokens / 1_000_000) * sonnetInputCentsPerM();
  const outCents = (outputTokens / 1_000_000) * sonnetOutputCentsPerM();
  return Math.round(inCents + outCents);
}

/** Per-million-tokens rate for Claude Opus 4.7 input. */
export function opusInputCentsPerM(): number {
  return envFloat('CLAUDE_OPUS_47_INPUT_CENTS_PER_M', DEFAULT_OPUS_INPUT_CENTS_PER_M);
}

/** Per-million-tokens rate for Claude Opus 4.7 output. */
export function opusOutputCentsPerM(): number {
  return envFloat('CLAUDE_OPUS_47_OUTPUT_CENTS_PER_M', DEFAULT_OPUS_OUTPUT_CENTS_PER_M);
}

/** Integer cents for a Claude Opus 4.7 call. Mirrors `claudeSonnet46CostCents`:
 *  rounded half-up so we never under-report; micro-token calls round to 0
 *  but accumulate honestly across summed rows. */
export function claudeOpus47CostCents(inputTokens: number, outputTokens: number): number {
  const inCents = (inputTokens / 1_000_000) * opusInputCentsPerM();
  const outCents = (outputTokens / 1_000_000) * opusOutputCentsPerM();
  return Math.round(inCents + outCents);
}

/** Per-million-tokens rate for Claude Haiku 4.5 input. */
export function haikuInputCentsPerM(): number {
  return envFloat('CLAUDE_HAIKU_45_INPUT_CENTS_PER_M', DEFAULT_HAIKU_INPUT_CENTS_PER_M);
}

/** Per-million-tokens rate for Claude Haiku 4.5 output. */
export function haikuOutputCentsPerM(): number {
  return envFloat('CLAUDE_HAIKU_45_OUTPUT_CENTS_PER_M', DEFAULT_HAIKU_OUTPUT_CENTS_PER_M);
}

/** Integer cents for a Claude Haiku 4.5 call. */
export function claudeHaiku45CostCents(inputTokens: number, outputTokens: number): number {
  const inCents = (inputTokens / 1_000_000) * haikuInputCentsPerM();
  const outCents = (outputTokens / 1_000_000) * haikuOutputCentsPerM();
  return Math.round(inCents + outCents);
}

/** Per-model dispatcher. Used by `anthropic.ts` so the AiCall row's
 *  `costUsdCents` reflects the model that actually ran. Unknown models
 *  return 0 (don't fabricate cost — let AiCall rows show $0 until
 *  pricing for the new model is added explicitly).
 *
 *  Cache token args (`cacheReadInputTokens`, `cacheCreationInputTokens`)
 *  apply Anthropic's prompt-caching multipliers: cache reads at 0.1x
 *  the model's base input rate (90% discount), 5-minute cache writes
 *  at 1.25x. The args default to 0 so existing callers continue to
 *  work without modification; new callers pass the SDK's
 *  response.usage.cache_*_input_tokens through.
 */
export function claudeCostCents(
  model: string,
  inputTokens: number,
  outputTokens: number,
  cacheReadInputTokens: number = 0,
  cacheCreationInputTokens: number = 0,
): number {
  let base: number;
  switch (model) {
    // Opus 4.8 shares 4.7's rate card ($5/M in, $25/M out) — same opus path.
    case 'claude-opus-4-7':
    case 'claude-opus-4-8':
      base = claudeOpus47CostCents(inputTokens, outputTokens);
      break;
    case 'claude-sonnet-4-6':
      base = claudeSonnet46CostCents(inputTokens, outputTokens);
      break;
    case 'claude-haiku-4-5':
    case 'claude-haiku-4-5-20251001':
      base = claudeHaiku45CostCents(inputTokens, outputTokens);
      break;
    default:
      return 0;
  }
  if (cacheReadInputTokens === 0 && cacheCreationInputTokens === 0) return base;
  const inputRate = modelInputCentsPerM(model);
  const cacheReadCents = (cacheReadInputTokens / 1_000_000) * inputRate * 0.10;
  const cacheWriteCents = (cacheCreationInputTokens / 1_000_000) * inputRate * 1.25;
  return Math.round(base + cacheReadCents + cacheWriteCents);
}

/** Internal: which base-input rate to use for cache-token multipliers.
 *  Returns 0 for unknown models so they don't synthesize cache cost. */
function modelInputCentsPerM(model: string): number {
  switch (model) {
    case 'claude-opus-4-7':
    case 'claude-opus-4-8':   return opusInputCentsPerM();
    case 'claude-sonnet-4-6': return sonnetInputCentsPerM();
    case 'claude-haiku-4-5':
    case 'claude-haiku-4-5-20251001':
      return haikuInputCentsPerM();
    default: return 0;
  }
}

/** Per-minute rate for Deepgram Nova-3 Medical (batch or streaming). */
export function deepgramCentsPerMin(): number {
  return envFloat('DEEPGRAM_COST_PER_MIN_CENTS', DEFAULT_DEEPGRAM_CENTS_PER_MIN);
}

/** Integer cents for a Deepgram batch call of the given duration. */
export function deepgramBatchCostCents(audioDurationSec: number): number {
  const minutes = audioDurationSec / 60;
  return Math.round(minutes * deepgramCentsPerMin());
}

// T-M14.1: OpenAI text-embedding-3-small pricing. Published rate is
// $0.020 / 1M tokens ⇒ 2 cents / M. A full SOAP note is ~1-2K tokens,
// so a single sign-time embed costs a fraction of a cent and rounds to
// 0 in the AiCall row. Kept in the pricing surface anyway so future
// aggregates-across-calls math doesn't silently skip embeds.
const DEFAULT_OPENAI_EMBED_SMALL_CENTS_PER_M = 2;

export function openaiEmbedSmallCentsPerM(): number {
  return envFloat(
    'OPENAI_EMBED_SMALL_CENTS_PER_M',
    DEFAULT_OPENAI_EMBED_SMALL_CENTS_PER_M
  );
}

export function openaiEmbedSmallCostCents(inputTokens: number): number {
  return Math.round((inputTokens / 1_000_000) * openaiEmbedSmallCentsPerM());
}
