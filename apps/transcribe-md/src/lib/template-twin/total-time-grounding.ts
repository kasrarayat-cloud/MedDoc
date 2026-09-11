// ============================================================================
// #314 — A TOTAL TIME IS GROUNDED BEFORE IT BECOMES A FACT. Pure.
// ----------------------------------------------------------------------------
// `total_time_minutes` fills two BILLING lines on the owner's consult form.
// `projectEncounterFacts` keeps a fact whose quote cannot be located (the
// offsets fall back to null), so before #314 nothing but a sentence in the L3
// prompt stood between a model's arithmetic and those lines.
//
// ⚠️ VERSION 3 — AN ANCHORED ALLOWLIST, NOT A REFUSAL LEXICON. Versions 1 and 2
// accepted any sentence that contained a total construction and then tried to
// REFUSE the bad ones with word lists (hours, seconds, ranges, negations, past
// visits). Round two of the refutation pass broke v2 in both directions, 12 of
// 13 verified findings confirmed. Every list had a missing member, and every
// construction accepted words before or after it:
//
//   "Less than 45 minutes total."                         -> 45
//   "The chest pain lasted 20 minutes total."             -> 20
//   "Last week, total time was 45 minutes."               -> 45
//   quote "15 minutes in total." in "Seen for 1 hr. 15 minutes in total." -> 15
//   "Total time 45 minutes. Correction, total time 30 minutes."  -> 45
//   "30 and 15 minutes in total."                          -> 15
//
// THE ERRORS ARE ASYMMETRIC. A wrong billing quantity on a signed note cannot
// be recovered; a blank with a named reason can, because the doctor sets the
// control at review. So a sentence now grounds only when the WHOLE of it is
// one of a short list of canonical forms, and everything else is a blank.
//
// THE RULE, VERSION 3 — every step must hold, or NO fact:
//   1 · LOCATE. The quote occurs in the context at a word boundary at both
//       ends (normalised: whitespace runs -> one space, lowercase, curly
//       apostrophes -> '). Every occurrence is judged.
//   2 · ONE SENTENCE. Each occurrence lies inside exactly one sentence.
//       ; ! ? end a sentence. A '.' ends one ONLY when the next non-whitespace
//       character is an uppercase letter, or there is none. A line break alone
//       does not. So "1 hr. 15", "approx. 45" and "4.5" never split.
//   3 · THE WHOLE SENTENCE IS CANONICAL. Normalised, a hyphen between number
//       words made a space, one trailing '.' stripped: a sentence ending in ?
//       or ! is not a statement; otherwise the ENTIRE sentence must match one
//       of CANONICAL_TOTAL_FORMS, whose one quantity must read as a positive
//       integer equal to the value.
//   4 · NOT RETRACTED. The sentence after each occurrence must not begin with
//       a retraction ("correction", "strike that", "actually", "no, ...").
//   5 · ONE TOTAL. Every sentence of the whole context that matches a
//       canonical form states the same minutes as the value.
//
// Conversation mode is refused outright, in ONE place: the call site in
// `encounter-facts/index.ts`. The doors cannot read the role-labelled text the
// worker read, so no grounding answer would be the same everywhere.
//
// ⚠️ EVERY REFUSAL IS A BLANK, NEVER A GUESS. A withheld fact leaves both
// controls to the bounded clear, COUNTED as still blank, so the doctor is told
// and types the figure. The refusal reason is a fixed token — no quote, no
// number — so the log is not a PHI surface.
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
const CURLY_APOSTROPHE = /^[‘’ʼ]$/u;

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

// ── 2 · SENTENCES ───────────────────────────────────────────────────────────

const UPPERCASE_LETTER = /^\p{Lu}$/u;

/** The first non-whitespace character at or after `from`, or undefined. */
function nextVisibleCharacter(source: string, from: number): string | undefined {
  for (let j = from; j < source.length; ) {
    const ch = String.fromCodePoint(source.codePointAt(j)!);
    if (!WHITESPACE.test(ch)) return ch;
    j += ch.length;
  }
  return undefined;
}

/**
 * Sentence spans of the SOURCE. `;` `!` `?` end a sentence. ⚠️ A `.` ENDS ONE
 * ONLY WHEN THE NEXT NON-WHITESPACE CHARACTER IS AN UPPERCASE LETTER, OR THERE
 * IS NONE. v2 ended one at any '.' not followed by a digit, so an abbreviation
 * period let the model's narrow quote choose which half was judged:
 *
 *     quote "15 minutes in total." in "Seen for 1 hr. 15 minutes in total." -> 15
 *
 * Now "hr.", "approx.", "prev." and "4.5" do not split. "Dr. Patel" still does,
 * and the half it leaves ("Patel, total time was ...") is not a canonical form,
 * so it refuses. Joining two sentences can only cost a blank, never a figure.
 *
 * A LINE BREAK DOES NOT END A SENTENCE (amendment 2), so a line with no
 * terminal punctuation joins the next and the joined text is judged whole.
 */
export function sentenceSpans(source: string): SourceSpan[] {
  const spans: SourceSpan[] = [];
  let start = 0;
  for (let i = 0; i < source.length; i += 1) {
    const c = source[i]!;
    let ends = c === ';' || c === '!' || c === '?';
    if (c === '.') {
      const next = nextVisibleCharacter(source, i + 1);
      ends = next === undefined || UPPERCASE_LETTER.test(next);
    }
    if (ends) {
      spans.push({ start, end: i + 1 });
      start = i + 1;
    }
  }
  if (start < source.length) spans.push({ start, end: source.length });
  return spans;
}

// ── 3 · THE CANONICAL FORMS ─────────────────────────────────────────────────

const NUMBER_WORD = `(?:${[...Object.keys(UNITS), ...Object.keys(TENS), 'hundred']
  .sort((a, b) => b.length - a.length)
  .join('|')})`;
/** "forty-five" -> "forty five", "one-hundred" -> "one hundred". Nothing else. */
const NUMBER_WORD_HYPHEN = new RegExp(`\\b(${NUMBER_WORD})[-\\u2010\\u2011](?=${NUMBER_WORD}\\b)`, 'gu');

/**
 * `Q` — EXACTLY ONE quantity: digits, or a run of number words, directly
 * followed by a minute unit. Nothing may sit between the number and its unit.
 */
const Q = `(?:(?<digits>\\d+) ?|(?<words>(?:a )?${NUMBER_WORD}(?: (?:${NUMBER_WORD}|and))*) )(?:minutes|minute|mins|min)`;
const THIS_VISIT = '(?:with the patient|on this visit|on this encounter)';

const anchored = (body: string): RegExp => new RegExp(`^${body}$`, 'u');

/**
 * ⚠️ THE ALLOWLIST. A normalised sentence grounds only when the WHOLE of it is
 * one of these. Adding a form is widening a billing rule: it needs an accept
 * arm and a mutation, and nothing else in this file may accept a sentence.
 *
 * `tail` (F7 only) is words, commas and "and" — see `isPlainTail`.
 */
export const CANONICAL_TOTAL_FORMS: ReadonlyArray<{ readonly id: string; readonly form: RegExp }> = [
  { id: 'F1', form: anchored(`(?:the )?total (?:visit |encounter |face[ -]to[ -]face )?time(?: spent)?(?: today)?(?: (?:was|is|of))?(?: ?[:,])? ${Q}`) },
  { id: 'F2', form: anchored(`(?:the )?total time spent ${THIS_VISIT}(?: today)?(?: (?:was|is))?(?: ?[:,])? ${Q}`) },
  { id: 'F3', form: anchored(`(?:i |we )?spent a total of ${Q}(?: ${THIS_VISIT})?(?: today)?`) },
  { id: 'F4', form: anchored(`(?:a )?total(?: of)?(?: ?[:,])? ${Q}`) },
  { id: 'F5', form: anchored(`(?:the )?time spent(?: today)?(?: (?:was|is))?(?: ?[:,])? ${Q}`) },
  { id: 'F6', form: anchored(`${Q}(?: in)? total(?: time)?`) },
  { id: 'F6-spent', form: anchored(`${Q} spent(?: in)? total`) },
  { id: 'F7', form: anchored(`a total time of ${Q} (?:was )?spent ${THIS_VISIT}(?:, including (?<tail>[\\p{L}' ,]+))?`) },
];

const TIME_UNIT_WORDS = new Set([
  'minute', 'minutes', 'min', 'mins', 'hour', 'hours', 'hr', 'hrs', 'second', 'seconds', 'sec', 'secs',
  'day', 'days', 'week', 'weeks', 'month', 'months', 'year', 'years',
]);

/** F7's "including T": no digit (the character class), no number word, no time unit. */
function isPlainTail(tail: string): boolean {
  return tail
    .split(/[ ,]+/u)
    .filter((w) => w !== '')
    .every((w) => !isNumberWord(w) && !TIME_UNIT_WORDS.has(w));
}

/** Normalised for the forms: see rule 3 in the header. */
export function canonicalSentence(sentence: string): string {
  const s = normaliseForGrounding(sentence).text.trim().replace(NUMBER_WORD_HYPHEN, '$1 ');
  return s.endsWith('.') ? s.slice(0, -1) : s;
}

/** The minutes a canonical sentence states (null = unreadable), or null when it is no form. */
function statedTotalOf(canonical: string): { minutes: number | null } | null {
  for (const { form } of CANONICAL_TOTAL_FORMS) {
    const m = form.exec(canonical);
    if (m === null) continue;
    const tail = m.groups?.tail;
    if (tail !== undefined && !isPlainTail(tail)) continue;
    const digits = m.groups?.digits;
    const n = digits !== undefined ? Number(digits) : parseSpokenCardinal((m.groups?.words ?? '').split(' '));
    return { minutes: n !== null && Number.isSafeInteger(n) && n > 0 ? n : null };
  }
  return null;
}

// ── THE JUDGEMENT ───────────────────────────────────────────────────────────

/** Refusals a single sentence can earn. */
export type TotalTimeSentenceRefusal =
  | 'not_a_statement'
  | 'not_stated_as_a_total'
  | 'minute_quantity_unreadable'
  | 'stated_quantity_differs_from_value';

export type TotalTimeRefusal =
  | 'quote_empty'
  | 'minutes_not_a_positive_integer'
  | 'quote_not_in_transcript'
  | 'quote_splits_a_word'
  | TotalTimeSentenceRefusal
  | 'corrected_in_next_sentence'
  | 'several_totals_stated'
  /** Emitted by the ONE call site in encounter-facts, never by this module. */
  | 'conversation_mode_not_grounded';

export type TotalTimeGrounding = { ok: true } | { ok: false; reason: TotalTimeRefusal };

/** Rule 3 against ONE sentence. null = this sentence grounds the value. */
export function judgeTotalTimeSentence(sentence: string, minutes: number): TotalTimeSentenceRefusal | null {
  const canonical = canonicalSentence(sentence);
  if (canonical.endsWith('?') || canonical.endsWith('!')) return 'not_a_statement';
  const stated = statedTotalOf(canonical);
  if (stated === null) return 'not_stated_as_a_total';
  if (stated.minutes === null) return 'minute_quantity_unreadable';
  if (stated.minutes !== minutes) return 'stated_quantity_differs_from_value';
  return null;
}

/** Rule 4: what the NEXT sentence may not begin with. */
const RETRACTION =
  /^(?:(?:correction|strike that|scratch that|sorry|no wait|wait|actually|i mean|make that|rather)\b|no(?:,|$))/u;

const refuse = (reason: TotalTimeRefusal): TotalTimeGrounding => ({ ok: false, reason });

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
  if (!quote) return refuse('quote_empty');
  if (!Number.isSafeInteger(input.minutes) || input.minutes <= 0) {
    return refuse('minutes_not_a_positive_integer');
  }
  const context = normaliseForGrounding(input.contextText);
  const { spans, midWord } = locateQuote(context, quote);
  if (spans.length === 0) return refuse(midWord > 0 ? 'quote_splits_a_word' : 'quote_not_in_transcript');

  const sentences = sentenceSpans(input.contextText);
  const canonicalAt = (i: number): string =>
    canonicalSentence(input.contextText.slice(sentences[i]!.start, sentences[i]!.end));

  // Rules 1–3. ⚠️ EVERY OCCURRENCE COUNTS: the same words can be today's total
  // in one sentence and last week's in another, and the model does not pick.
  const homes: number[] = [];
  for (const span of spans) {
    const hit = sentences.flatMap((s, i) => (s.start < span.end && s.end > span.start ? [i] : []));
    // A quote across a sentence end is not ONE sentence stating a total.
    if (hit.length !== 1) return refuse('not_stated_as_a_total');
    const refusal = judgeTotalTimeSentence(input.contextText.slice(sentences[hit[0]!]!.start, sentences[hit[0]!]!.end), input.minutes);
    if (refusal !== null) return refuse(refusal);
    homes.push(hit[0]!);
  }

  // Rule 4 — a dictated correction retracts the total before it.
  for (const home of homes) {
    for (let i = home + 1; i < sentences.length; i += 1) {
      const next = canonicalAt(i);
      if (next === '') continue;
      if (RETRACTION.test(next)) return refuse('corrected_in_next_sentence');
      break;
    }
  }

  // Rule 5 — two canonical totals that disagree: the model does not pick.
  for (let i = 0; i < sentences.length; i += 1) {
    const stated = statedTotalOf(canonicalAt(i));
    if (stated !== null && stated.minutes !== input.minutes) return refuse('several_totals_stated');
  }
  return { ok: true };
}
