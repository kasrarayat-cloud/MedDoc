// ============================================================================
// @meddoc/ai — provider pricing helpers (T-M4)
// ----------------------------------------------------------------------------
// Every AiCall row can carry a costUsdCents so /settings → usage can sum
// cents for a unit-economics view later. Prices are env-overridable in
// case a provider changes their rate card mid-flight.
//
// Defaults reflect published rates as of the T-M4 implementation:
//   Claude Sonnet 4.6   $3 / M input, $15 / M output
//   Deepgram Nova-3 Med $0.0145 / min
//   (OpenAI: not used in T-M4; left unset)
//
// All values are INTEGER CENTS so summation is drift-free.
// ============================================================================

const DEFAULT_SONNET_INPUT_CENTS_PER_M = 300;   // $3.00 / M tokens
const DEFAULT_SONNET_OUTPUT_CENTS_PER_M = 1500; // $15.00 / M tokens
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
