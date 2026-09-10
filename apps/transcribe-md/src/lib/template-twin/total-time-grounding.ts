// ============================================================================
// #314 — A TOTAL TIME IS GROUNDED BEFORE IT BECOMES A FACT. Pure.
// ----------------------------------------------------------------------------
// `total_time_minutes` fills two BILLING lines on the owner's consult form.
// Until this module, the only thing standing between a model's arithmetic and
// those lines was a sentence in the L3 prompt ("Do NOT compute a total").
// `projectEncounterFacts` emits a fact as `direct` evidence even when its quote
// cannot be found in the transcript — the offsets fall back to null and the
// fact is kept — so the refutation pass over the confirm door demonstrated both:
//
//   "I spent twenty minutes reviewing outside records and twenty five minutes
//    with the patient."           + L3 {minutes: 45}  -> both lines print 45
//   "Chief complaint: dysphagia."   + L3 {minutes: 60, quote: "We spent an
//    hour together."}  (a quote that is not in the transcript) -> both print 60
//
// valid=true, zero blocking, in both. A total nobody stated reached a billing
// line. The owner's standing principle is that the machine never prints an
// undictated value.
//
// THE RULE — all three, or no fact:
//   1 · the quote is IN the transcript, verbatim;
//   2 · the quote states exactly ONE minute quantity, and it EQUALS the value —
//       as digits ("45 minutes") or spelled ("forty five" / "forty-five");
//   3 · the quote says it is a total: "total" or "spent".
//
// ⚠️ EVERY REFUSAL IS A BLANK, NEVER A GUESS. A withheld fact leaves the two
// controls to the bounded clear, COUNTED as still blank, so the doctor is told
// and types the figure themselves. The strictness is deliberate and one-sided:
// "total 45 minutes including 20 minutes of counselling" is refused (two
// quantities), and "an hour" is refused (no minute quantity). A blank a doctor
// fills is recoverable; a wrong billing figure on a signed note is not.
//
// ⚠️ NARROW ON PURPOSE. The same ungrounded-quote gap exists for every concept;
// widening this rule to all of them would blank fields across every visit
// without a measurement of how many quotes are paraphrased today. That is filed
// separately. This rule covers the one concept that is a billing quantity.
//
//   PROOF: __tests__/gate-314-total-time-grounding.test.ts
// ============================================================================

const UNITS: Readonly<Record<string, number>> = {
  zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9,
  ten: 10, eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16,
  seventeen: 17, eighteen: 18, nineteen: 19,
};
const TENS: Readonly<Record<string, number>> = {
  twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90,
};

const isNumberWord = (t: string): boolean => t in UNITS || t in TENS || t === 'hundred';

/**
 * A spoken cardinal from 0 to 999 — "forty five", "one hundred and twenty",
 * "a hundred" — or null when the words do not form one.
 *
 * ⚠️ NULL, NOT A BEST GUESS. "forty forty" and "five forty" are not numbers a
 * clinician says for a total; reading them as 80 or 45 would be the parser
 * inventing the figure this module exists to stop anyone inventing.
 */
export function parseSpokenCardinal(words: readonly string[]): number | null {
  if (words.length === 0) return null;
  let hundreds = 0;
  let rest = 0;
  let sawTens = false;
  let sawUnits = false;
  let sawHundred = false;
  let sawAny = false;
  for (let i = 0; i < words.length; i += 1) {
    const w = words[i]!;
    if (w === 'and') {
      if (!sawHundred || sawTens || sawUnits || i === words.length - 1) return null;
      continue;
    }
    if (w === 'a') {
      if (i !== 0 || words[i + 1] !== 'hundred') return null;
      continue;
    }
    if (w === 'hundred') {
      if (sawHundred || sawTens) return null;
      const multiplier = sawUnits ? rest : words[i - 1] === 'a' ? 1 : 0;
      if (multiplier < 1 || multiplier > 9) return null;
      hundreds = multiplier * 100;
      rest = 0;
      sawUnits = false;
      sawHundred = true;
      sawAny = true;
      continue;
    }
    if (w in TENS) {
      if (sawTens || sawUnits) return null;
      rest += TENS[w]!;
      sawTens = true;
      sawAny = true;
      continue;
    }
    if (w in UNITS) {
      const u = UNITS[w]!;
      // "forty five" is 45; "forty fifteen" is not a number.
      if (sawUnits || (sawTens && u > 9) || (sawTens && u === 0)) return null;
      rest += u;
      sawUnits = true;
      sawAny = true;
      continue;
    }
    return null;
  }
  return sawAny ? hundreds + rest : null;
}

const MINUTE_UNIT = /^(?:minutes?|mins?)$/;

/**
 * Every minute quantity the text STATES, in order: the number immediately
 * before a minute word, as digits or as a spoken cardinal.
 */
export function statedMinuteQuantities(text: string): number[] {
  const tokens = text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, ' ')
    .split(/[\s-]+/)
    .filter(Boolean);
  const out: number[] = [];
  for (let i = 0; i < tokens.length; i += 1) {
    if (!MINUTE_UNIT.test(tokens[i]!)) continue;
    const prev = tokens[i - 1];
    if (prev !== undefined && /^\d+$/.test(prev)) {
      out.push(Number(prev));
      continue;
    }
    let j = i - 1;
    const run: string[] = [];
    while (
      j >= 0 &&
      (isNumberWord(tokens[j]!) || tokens[j] === 'and' || (tokens[j] === 'a' && tokens[j + 1] === 'hundred'))
    ) {
      run.unshift(tokens[j]!);
      j -= 1;
    }
    // A run cannot START with a connective: "and five minutes" is five.
    while (run[0] === 'and') run.shift();
    const n = parseSpokenCardinal(run);
    if (n !== null) out.push(n);
  }
  return out;
}

const TOTAL_MARKER = /\b(?:total|spent)\b/i;

export type TotalTimeRefusal =
  | 'quote_empty'
  | 'quote_not_in_transcript'
  | 'minutes_not_a_positive_integer'
  | 'no_minute_quantity_stated'
  | 'several_minute_quantities_stated'
  | 'stated_quantity_differs_from_value'
  | 'not_stated_as_a_total';

export type TotalTimeGrounding = { ok: true } | { ok: false; reason: TotalTimeRefusal };

/**
 * Whether an L3 `total_time_minutes` entity may become a fact.
 *
 * The reason is a fixed token — never a quote, never a number — so a refusal
 * can be logged without the log becoming a PHI surface.
 */
export function groundTotalTime(input: {
  contextText: string;
  quote: string | null | undefined;
  minutes: number;
}): TotalTimeGrounding {
  const quote = (input.quote ?? '').trim();
  if (!quote) return { ok: false, reason: 'quote_empty' };
  if (!Number.isSafeInteger(input.minutes) || input.minutes <= 0) {
    return { ok: false, reason: 'minutes_not_a_positive_integer' };
  }
  // The same exact-substring test `nthExactOffset` uses to locate evidence.
  if (!input.contextText.includes(quote)) return { ok: false, reason: 'quote_not_in_transcript' };
  const stated = [...new Set(statedMinuteQuantities(quote))];
  if (stated.length === 0) return { ok: false, reason: 'no_minute_quantity_stated' };
  if (stated.length > 1) return { ok: false, reason: 'several_minute_quantities_stated' };
  if (stated[0] !== input.minutes) return { ok: false, reason: 'stated_quantity_differs_from_value' };
  if (!TOTAL_MARKER.test(quote)) return { ok: false, reason: 'not_stated_as_a_total' };
  return { ok: true };
}
