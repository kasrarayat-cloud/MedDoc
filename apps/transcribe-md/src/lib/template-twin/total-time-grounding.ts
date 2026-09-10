// ============================================================================
// #314 — A TOTAL TIME IS GROUNDED BEFORE IT BECOMES A FACT. Pure.
// ----------------------------------------------------------------------------
// `total_time_minutes` fills two BILLING lines on the owner's consult form.
// `projectEncounterFacts` keeps a fact whose quote cannot be located (the
// offsets fall back to null), so before #314 nothing but a sentence in the L3
// prompt stood between a model's arithmetic and those lines.
//
// ⚠️ VERSION 2. Version 1 tested the QUOTE the model chose: "total"/"spent"
// anywhere in it, `includes()` with no word boundary, the quantity read from the
// quote, a `Set` for the count, and hours ignored. A refutation pass drove all
// of these onto both billing lines:
//
//   "I spent 45 minutes in traffic getting here."                -> 45
//   "Total cholesterol was 240 and she waited 45 minutes ..."    -> 45
//   "This was not a total of 45 minutes; I did not track time."  -> 45
//   "Last visit the total time was 45 minutes."                  -> 45
//   "Total time spent today was one hour and fifteen minutes."   -> 15
//   quote "5 minutes total" inside "We spent 145 minutes total." -> 5
//   "Total time spent 30-45 minutes." -> 45    "Total 4.5 minutes" -> 5
//   "20 minutes reviewing records and 20 minutes with the patient" -> 20
//
// THE RULE, VERSION 2 — every step must hold, or NO fact:
//   1 · LOCATE. Both sides are normalised (whitespace runs -> one space,
//       lowercase, curly apostrophes -> '). The quote must occur in the context
//       at a WORD BOUNDARY at both ends. Every such occurrence is judged.
//   2 · READ THE TRANSCRIPT, NOT THE QUOTE. For each occurrence, take the
//       SENTENCE(S) of the context it spans — split on . ; ! ? ONLY (a line
//       break does NOT end one; see sentenceSpans), a '.' followed by a digit
//       being a decimal point, not an end — and judge
//       that text. The model chooses the quote; it does not choose the sentence.
//   3 · QUANTITIES, counted as OCCURRENCES, never a Set:
//       any hour or seconds quantity refuses (no conversion); any decimal or clock time
//       refuses; any range (N-M, N to/or/through M, between N and M) refuses;
//       exactly ONE minute quantity, a number directly followed by its unit,
//       and it must EQUAL the value.
//   4 · NO negation and NO past-visit marker in the sentence.
//   5 · AN EXPLICIT TOTAL CONSTRUCTION TIED TO THAT ONE QUANTITY:
//         total [visit|encounter|face-to-face] time [spent] [today] [was|of|is|:] N minutes
//         a total of N minutes · total [of] N minutes · N minutes [in] total
//         time spent [was|is|:] N minutes
//       Bare "spent" is not a marker, and "total" modifying another noun
//       ("total cholesterol") is not one either.
//
// ⚠️ EVERY REFUSAL IS A BLANK, NEVER A GUESS. A withheld fact leaves both
// controls to the bounded clear, COUNTED as still blank, so the doctor is told
// and types the figure. The strictness is deliberate and one-sided: a blank a
// doctor fills is recoverable; a wrong billing figure on a signed note is not.
// The refusal reason is a fixed token — no quote, no number — so the log is not
// a PHI surface.
//
// ⚠️ WHICH CONTEXT IS "THE TRANSCRIPT" IS NOT DECIDED HERE. It is decided once,
// for the worker and every re-fill door, by `groundingContextFor`
// (./grounding-context.ts). A grounding rule judged against two different texts
// is two rules.
//
//   PROOF: __tests__/gate-314-total-time-grounding.test.ts
//          __tests__/gate-314-grounding-context-doors.test.ts
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

// ── 1 · NORMALISE, KEEPING THE WAY BACK ─────────────────────────────────────

export interface NormalisedText {
  readonly text: string;
  /** `origin[i]` is the index in the SOURCE of normalised character `i`. */
  readonly origin: readonly number[];
}

const WHITESPACE = /^\s$/u;
const CURLY_APOSTROPHE = /^[\u2018\u2019\u02bc]$/u;

/**
 * Lowercase, collapse every whitespace run (newlines included) to one space,
 * and fold curly apostrophes to `'`. Nothing else — punctuation, hyphens and
 * digits are untouched, so a quote that differs from the transcript in anything
 * but case and spacing is still not in it.
 */
export function normaliseForGrounding(source: string): NormalisedText {
  let text = '';
  const origin: number[] = [];
  let inSpace = false;
  for (let i = 0; i < source.length; ) {
    const ch = String.fromCodePoint(source.codePointAt(i)!);
    if (WHITESPACE.test(ch)) {
      if (!inSpace) {
        text += ' ';
        origin.push(i);
      }
      inSpace = true;
    } else {
      inSpace = false;
      const folded = CURLY_APOSTROPHE.test(ch) ? "'" : ch.toLowerCase();
      for (let k = 0; k < folded.length; k += 1) {
        text += folded[k];
        origin.push(i);
      }
    }
    i += ch.length;
  }
  return { text, origin };
}

const WORD_CHAR = /[\p{L}\p{N}]/u;
const isWordChar = (c: string | undefined): boolean => c !== undefined && WORD_CHAR.test(c);

interface SourceSpan {
  start: number;
  end: number;
}

/**
 * Every occurrence of the (normalised) quote in the (normalised) context, as a
 * SOURCE span — and how many occurrences were refused for starting or ending
 * inside a word ("5 minutes total" inside "145 minutes total").
 */
function locateQuote(context: NormalisedText, quote: string): { spans: SourceSpan[]; midWord: number } {
  const spans: SourceSpan[] = [];
  let midWord = 0;
  for (let at = context.text.indexOf(quote); at >= 0; at = context.text.indexOf(quote, at + 1)) {
    const end = at + quote.length;
    const opensMidWord = isWordChar(quote[0]) && isWordChar(context.text[at - 1]);
    const closesMidWord = isWordChar(quote[quote.length - 1]) && isWordChar(context.text[end]);
    if (opensMidWord || closesMidWord) {
      midWord += 1;
      continue;
    }
    spans.push({ start: context.origin[at]!, end: context.origin[end - 1]! + 1 });
  }
  return { spans, midWord };
}

// ── 2 · THE SENTENCE, NOT THE QUOTE ─────────────────────────────────────────

const DIGIT = /^[0-9]$/;

/**
 * Sentence spans of the SOURCE. Ends at . ; ! ? — and NOWHERE ELSE. ⚠️ A '.'
 * FOLLOWED BY A DIGIT IS A DECIMAL POINT, NOT AN END — otherwise "It took 4.5
 * minutes total." splits into "It took 4." and "5 minutes total.", and a quote
 * of the second grounds as 5.
 *
 * ⚠️ A LINE BREAK DOES NOT END A SENTENCE, AND THAT IS A DECIDED TRADE. v2 as
 * first built ended one at every line break, so list-style notes would not be
 * refused — and measured, both of these then GROUNDED as 45, because the
 * negation / past-visit marker sat on the line before the total:
 *
 *     "This was not⏎a total of 45 minutes."
 *     "Last visit,⏎total time was 45 minutes."
 *
 * A line that carries its own terminal punctuation still ends its sentence
 * ("No fever.⏎Total time 45 minutes." grounds). An unpunctuated one joins the
 * next, so a negation above an unpunctuated total refuses it: a blank the doctor
 * fills is recoverable, a wrong billing figure on a signed note is not.
 */
export function sentenceSpans(source: string): SourceSpan[] {
  const spans: SourceSpan[] = [];
  let start = 0;
  for (let i = 0; i < source.length; i += 1) {
    const c = source[i]!;
    const ends =
      c === ';' ||
      c === '!' ||
      c === '?' ||
      (c === '.' && !DIGIT.test(source[i + 1] ?? ''));
    if (ends) {
      spans.push({ start, end: i + 1 });
      start = i + 1;
    }
  }
  if (start < source.length) spans.push({ start, end: source.length });
  return spans;
}

function sentencesSpannedBy(source: string, sentences: readonly SourceSpan[], span: SourceSpan): string {
  const hit = sentences.filter((s) => s.start < span.end && s.end > span.start);
  return source.slice(hit[0]!.start, hit[hit.length - 1]!.end);
}

// ── 3 · TOKENS AND QUANTITIES ───────────────────────────────────────────────

/**
 * A number (digits, possibly with a decimal/clock separator, or a leading-dot
 * decimal), a word (letters, with an inner apostrophe), a dash, or any other
 * single mark. ⚠️ DIGITS AND LETTERS ARE SEPARATE TOKENS BY CONSTRUCTION, so an
 * attached unit ("45min", "1h") splits without a rewrite step.
 */
const TOKEN = /\d+(?:[.,:]\d+)*|[.,]\d+|\p{L}+(?:'\p{L}+)*|[-\u2010-\u2015\u2212]|\S/gu;
const DASH = /^[-\u2010-\u2015\u2212]$/u;
const DIGITS_ONLY = /^\d+$/;
const STARTS_WITH_DIGIT = /^[.,]?\d/;

type Unit =
  | { kind: 'num'; value: number | null; integer: boolean }
  | { kind: 'word'; w: string }
  | { kind: 'mark'; m: string }
  | { kind: 'range' };

const MINUTE_WORDS = new Set(['minute', 'minutes', 'min', 'mins']);
const HOUR_WORDS = new Set(['hour', 'hours', 'hr', 'hrs']);
const SECOND_WORDS = new Set(['second', 'seconds', 'sec', 'secs']);
const RANGE_WORDS = new Set(['to', 'or', 'through', 'thru']);
const NEGATIONS = new Set(['no', 'not', 'never', 'without', 'none', 'nor', 'neither', 'cannot', 'didnt', 'dont', 'doesnt', 'wasnt', 'isnt', 'werent']);
const PAST_WORDS = new Set(['last', 'previous', 'prior']);
const VISIT_WORDS = new Set(['visit', 'visits', 'encounter', 'encounters', 'appointment', 'appointments', 'session', 'consult', 'consultation', 'time']);

/** The sentence as units: numbers assembled (digits, or a spoken run), dashes resolved. */
function toUnits(sentence: string): Unit[] {
  const raw = normaliseForGrounding(sentence).text.match(TOKEN) ?? [];
  const isNumeric = (t: string | undefined): boolean =>
    t !== undefined && (STARTS_WITH_DIGIT.test(t) || isNumberWord(t));

  // Dashes first. Between two numbers a dash is a RANGE — unless it joins a
  // compound cardinal ("forty-five", "one-hundred"). Anywhere else it joins
  // words ("face-to-face") or a number to its unit ("45-minute"): dropped.
  const tokens: Array<string | { range: true }> = [];
  for (let i = 0; i < raw.length; i += 1) {
    const t = raw[i]!;
    if (!DASH.test(t)) {
      tokens.push(t);
      continue;
    }
    const prev = raw[i - 1];
    const next = raw[i + 1];
    if (!isNumeric(prev) || !isNumeric(next)) continue;
    const compound =
      (prev! in TENS && next! in UNITS && UNITS[next!]! >= 1 && UNITS[next!]! <= 9) ||
      (prev! in UNITS && next === 'hundred');
    if (!compound) tokens.push({ range: true });
  }

  const wordAt = (i: number): string | null => {
    const t = tokens[i];
    return typeof t === 'string' ? t : null;
  };
  const units: Unit[] = [];
  for (let i = 0; i < tokens.length; ) {
    const t = tokens[i]!;
    if (typeof t !== 'string') {
      units.push({ kind: 'range' });
      i += 1;
      continue;
    }
    if (STARTS_WITH_DIGIT.test(t)) {
      const integer = DIGITS_ONLY.test(t);
      units.push({ kind: 'num', value: integer ? Number(t) : null, integer });
      i += 1;
      continue;
    }
    if (isNumberWord(t) || (t === 'a' && wordAt(i + 1) === 'hundred')) {
      const run = [t];
      let j = i + 1;
      for (;;) {
        const w = wordAt(j);
        if (w !== null && isNumberWord(w)) {
          run.push(w);
          j += 1;
          continue;
        }
        const after = wordAt(j + 1);
        if (w === 'and' && run.includes('hundred') && after !== null && isNumberWord(after)) {
          run.push(w);
          j += 1;
          continue;
        }
        break;
      }
      // An unparseable run ("forty forty", "one thirty") is a number nobody can
      // read: value null, never a guess.
      units.push({ kind: 'num', value: parseSpokenCardinal(run), integer: true });
      i = j;
      continue;
    }
    units.push(/\p{L}/u.test(t) ? { kind: 'word', w: t } : { kind: 'mark', m: t });
    i += 1;
  }
  return units;
}

const wordOf = (u: Unit | undefined): string | null => (u?.kind === 'word' ? u.w : null);

interface MinuteQuantity {
  /** null when the number is unreadable or not directly followed by its unit. */
  value: number | null;
  /** Units `numIndex..unitIndex` ARE the quantity; only meaningful when direct. */
  numIndex: number;
  unitIndex: number;
}

/**
 * Every minute quantity the units state, as OCCURRENCES — two "20 minutes" are
 * two quantities, never one.
 *
 *   · a number DIRECTLY followed by a minute word is a readable quantity;
 *   · a number separated from its minute word by up to three words
 *     ("45 face-to-face minutes", "45 or more minutes", "20 additional
 *     minutes"), and a number directly AFTER a minute word ("minutes: 45",
 *     "45 minutes 30"), are quantities too — counted, but UNREADABLE, so they
 *     can refuse and can never ground.
 */
function minuteQuantities(units: readonly Unit[]): MinuteQuantity[] {
  const out: MinuteQuantity[] = [];
  for (let i = 0; i < units.length; i += 1) {
    const w = wordOf(units[i]);
    if (w === null || !MINUTE_WORDS.has(w)) continue;
    const prev = units[i - 1];
    if (prev?.kind === 'num') {
      out.push({ value: prev.integer ? prev.value : null, numIndex: i - 1, unitIndex: i });
    } else {
      let j = i - 1;
      let skipped = 0;
      while (skipped < 3 && j >= 0) {
        const between = wordOf(units[j]);
        if (between === null || MINUTE_WORDS.has(between) || HOUR_WORDS.has(between)) break;
        j -= 1;
        skipped += 1;
      }
      if (skipped > 0 && units[j]?.kind === 'num') out.push({ value: null, numIndex: j, unitIndex: i });
    }
    let k = i + 1;
    if (units[k]?.kind === 'mark' && (units[k] as { m: string }).m === ':') k += 1;
    if (units[k]?.kind === 'num') out.push({ value: null, numIndex: k, unitIndex: i });
  }
  return out;
}

/** Every minute quantity the text states, in order (null = unreadable). */
export function statedMinuteQuantities(text: string): Array<number | null> {
  return minuteQuantities(toUnits(text)).map((q) => q.value);
}

// ── 5 · THE TOTAL CONSTRUCTION ──────────────────────────────────────────────

const QUANTITY = '§q';
/**
 * Forms matched against the sentence with its ONE quantity replaced by `§q`,
 * so the construction is tied to that quantity and to nothing else.
 */
const TOTAL_CONSTRUCTIONS: readonly RegExp[] = [
  new RegExp(`(?:^| )total (?:(?:visit|encounter|face to face) )?time (?:spent )?(?:today )?(?:(?:was|of|is|:) )?${QUANTITY}(?= |$)`),
  new RegExp(`(?:^| )a total of ${QUANTITY}(?= |$)`),
  new RegExp(`(?:^| )total (?:of )?${QUANTITY}(?= |$)`),
  new RegExp(`(?:^| )time spent (?:(?:was|is|:) )?${QUANTITY}(?= |$)`),
  // "45 minutes total." — but not "45 minutes total cholesterol": a `total`
  // that goes on to modify a noun is not the quantity's total.
  new RegExp(
    `(?:^| )${QUANTITY} (?:in )?total(?=$| [^\\p{L}\\p{N} ]| (?:with|for|today|spent|was|is|on|in|during|including|and|of)(?: |$))`,
    'u',
  ),
];

function skeleton(units: readonly Unit[], q: MinuteQuantity): string {
  const parts: string[] = [];
  for (let i = 0; i < units.length; i += 1) {
    if (i === q.numIndex) continue;
    if (i === q.unitIndex) {
      parts.push(QUANTITY);
      continue;
    }
    const u = units[i]!;
    parts.push(u.kind === 'word' ? u.w : u.kind === 'mark' ? u.m : u.kind === 'num' ? '#' : '-');
  }
  return parts.join(' ');
}

// ── THE JUDGEMENT ───────────────────────────────────────────────────────────

export type TotalTimeRefusal =
  | 'quote_empty'
  | 'minutes_not_a_positive_integer'
  | 'quote_not_in_transcript'
  | 'quote_splits_a_word'
  | 'hour_quantity_stated'
  | 'seconds_quantity_stated'
  | 'quantity_not_an_integer'
  | 'quantity_is_a_range'
  | 'no_minute_quantity_stated'
  | 'several_minute_quantities_stated'
  | 'minute_quantity_unreadable'
  | 'stated_quantity_differs_from_value'
  | 'negation_in_sentence'
  | 'past_visit_marker'
  | 'not_stated_as_a_total';

export type TotalTimeGrounding = { ok: true } | { ok: false; reason: TotalTimeRefusal };

/** Rules 3–5 against ONE sentence text. null = this sentence grounds the value. */
export function judgeTotalTimeSentence(sentence: string, minutes: number): TotalTimeRefusal | null {
  const units = toUnits(sentence);

  for (let i = 0; i < units.length; i += 1) {
    const w = wordOf(units[i]);
    if (w !== null && (HOUR_WORDS.has(w) || (w === 'h' && units[i - 1]?.kind === 'num'))) {
      return 'hour_quantity_stated';
    }
  }
  // "45 minutes 30 seconds" is not a whole number of minutes, and no
  // conversion is attempted in either direction.
  for (let i = 1; i < units.length; i += 1) {
    const w = wordOf(units[i]);
    if (w !== null && SECOND_WORDS.has(w) && units[i - 1]?.kind === 'num') return 'seconds_quantity_stated';
  }
  if (units.some((u) => u.kind === 'num' && !u.integer)) return 'quantity_not_an_integer';
  for (let i = 0; i < units.length; i += 1) {
    const u = units[i]!;
    const next = units[i + 1];
    const connective = next?.kind === 'range' || (wordOf(next) !== null && RANGE_WORDS.has(wordOf(next)!));
    if (u.kind === 'num' && connective && units[i + 2]?.kind === 'num') return 'quantity_is_a_range';
    if (wordOf(u) === 'between' && units[i + 1]?.kind === 'num' && wordOf(units[i + 2]) === 'and' && units[i + 3]?.kind === 'num') {
      return 'quantity_is_a_range';
    }
  }

  const quantities = minuteQuantities(units);
  if (quantities.length === 0) return 'no_minute_quantity_stated';
  if (quantities.length > 1) return 'several_minute_quantities_stated';
  const only = quantities[0]!;
  if (only.value === null) return 'minute_quantity_unreadable';
  if (only.value !== minutes) return 'stated_quantity_differs_from_value';

  for (let i = 0; i < units.length; i += 1) {
    const w = wordOf(units[i]);
    if (w === null) continue;
    if (NEGATIONS.has(w) || w.endsWith("n't")) return 'negation_in_sentence';
  }
  for (let i = 0; i < units.length; i += 1) {
    const w = wordOf(units[i]);
    const next = wordOf(units[i + 1]);
    if (w !== null && next !== null && PAST_WORDS.has(w) && VISIT_WORDS.has(next)) return 'past_visit_marker';
  }

  const shape = skeleton(units, only);
  if (!TOTAL_CONSTRUCTIONS.some((form) => form.test(shape))) return 'not_stated_as_a_total';
  return null;
}

/**
 * Whether an L3 `total_time_minutes` entity may become a fact.
 *
 * `contextText` MUST be the text L3 read — `groundingContextFor` decides it for
 * every caller. The reason is a fixed token — never a quote, never a number —
 * so a refusal can be logged without the log becoming a PHI surface.
 */
export function groundTotalTime(input: {
  contextText: string;
  quote: string | null | undefined;
  minutes: number;
}): TotalTimeGrounding {
  const quote = normaliseForGrounding((input.quote ?? '').trim()).text;
  if (!quote) return { ok: false, reason: 'quote_empty' };
  if (!Number.isSafeInteger(input.minutes) || input.minutes <= 0) {
    return { ok: false, reason: 'minutes_not_a_positive_integer' };
  }
  const context = normaliseForGrounding(input.contextText);
  const { spans, midWord } = locateQuote(context, quote);
  if (spans.length === 0) {
    return { ok: false, reason: midWord > 0 ? 'quote_splits_a_word' : 'quote_not_in_transcript' };
  }
  // ⚠️ EVERY OCCURRENCE COUNTS. The same words can be today's total in one
  // sentence and last visit's in another; the model does not get to pick.
  const sentences = sentenceSpans(input.contextText);
  for (const span of spans) {
    const refusal = judgeTotalTimeSentence(sentencesSpannedBy(input.contextText, sentences, span), input.minutes);
    if (refusal !== null) return { ok: false, reason: refusal };
  }
  return { ok: true };
}
