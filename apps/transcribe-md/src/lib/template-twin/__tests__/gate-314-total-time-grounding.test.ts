// ============================================================================
// #314 v2 — A TOTAL TIME IS GROUNDED BEFORE IT BECOMES A FACT.
// ----------------------------------------------------------------------------
// The claims, each with the arm that fails if it is false:
//   · every attack the refutation pass drove through v1 is refused, with its
//     own reason token — a refusal for the WRONG reason is a rule that is not
//     doing its job and another rule covering for it
//   · a total that WAS stated, in each accepted construction, still grounds —
//     reflowed across a newline, in another case, with an attached unit
//   · the SENTENCE is judged, not the quote the model chose
//   · every rule has an arm where it is the ONLY thing standing between a wrong
//     figure and a billing line (the mutation-kill arms at the bottom)
//   · a refused total projects EXACTLY as if L3 had returned no total at all
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { projectEncounterFacts } from '../encounter-facts';
import {
  groundTotalTime,
  judgeTotalTimeSentence,
  parseSpokenCardinal,
  sentenceSpans,
  statedMinuteQuantities,
  type TotalTimeRefusal,
} from '../total-time-grounding';

const SELF_TEST =
  'A total time of forty five minutes was spent on this encounter, including counselling and coordination of care.';

/** Ground `quote` against `context` (default: the quote is the whole transcript). */
const ground = (quote: string, minutes: number, context: string = quote) =>
  groundTotalTime({ contextText: context, quote, minutes });
const refused = (reason: TotalTimeRefusal) => ({ ok: false, reason });

describe('#314 v2 · every attack on v1 is refused, for its OWN reason', () => {
  it.each<[string, string, number, string, TotalTimeRefusal]>([
    // D1 — "total"/"spent" was tested anywhere in the quote, never tied to the quantity.
    ['D1 · the patient spent 45 minutes in traffic', 'I spent 45 minutes in traffic getting here.', 45, 'Patient: I spent 45 minutes in traffic getting here.', 'not_stated_as_a_total'],
    ['D1 · "total" modifies cholesterol, not the wait', 'Total cholesterol was 240 and she waited 45 minutes in the lobby.', 45, 'Total cholesterol was 240 and she waited 45 minutes in the lobby.', 'not_stated_as_a_total'],
    ['D1 · a NEGATED total', 'This was not a total of 45 minutes; I did not track time.', 45, 'This was not a total of 45 minutes; I did not track time.', 'negation_in_sentence'],
    ['D1 · LAST visit\'s total', 'Last visit the total time was 45 minutes.', 45, 'Last visit the total time was 45 minutes.', 'past_visit_marker'],
    // D2 — hours were ignored.
    ['D2 · one hour and fifteen minutes, read as 15', 'Total time spent today was one hour and fifteen minutes.', 15, 'Total time spent today was one hour and fifteen minutes.', 'hour_quantity_stated'],
    ['D2 · 1 hour 45 minutes, read as 45', 'Total time 1 hour 45 minutes.', 45, 'Total time 1 hour 45 minutes.', 'hour_quantity_stated'],
    ['D2 · "1h" is an hour too', 'Total time 1h 45 minutes.', 45, 'Total time 1h 45 minutes.', 'hour_quantity_stated'],
    ['D2 · "an hour" is refused, never converted', 'We spent an hour together in total.', 60, 'We spent an hour together in total.', 'hour_quantity_stated'],
    // D3 — no word boundary, and the number was read from the model's quote.
    ['D3 · "5 minutes total" inside "145 minutes total"', '5 minutes total', 5, 'We spent 145 minutes total.', 'quote_splits_a_word'],
    ['D3 · "five minutes total" inside "twenty-five minutes total"', 'five minutes total', 5, 'We spent twenty-five minutes total.', 'stated_quantity_differs_from_value'],
    // D4 — ranges and decimals.
    ['D4 · a digit range 30-45', 'Total time spent 30-45 minutes.', 45, 'Total time spent 30-45 minutes.', 'quantity_is_a_range'],
    ['D4 · an en-dash range', 'Total time 30–45 minutes.', 45, 'Total time 30–45 minutes.', 'quantity_is_a_range'],
    ['D4 · a spoken range', 'Thirty to forty-five minutes total.', 45, 'Thirty to forty-five minutes total.', 'quantity_is_a_range'],
    ['D4 · "30 or 45"', 'Total 30 or 45 minutes.', 45, 'Total 30 or 45 minutes.', 'quantity_is_a_range'],
    ['D4 · "between 30 and 45"', 'Total between 30 and 45 minutes.', 45, 'Total between 30 and 45 minutes.', 'quantity_is_a_range'],
    ['D4 · 4.5 minutes, read as 5', 'Total 4.5 minutes', 5, 'Total 4.5 minutes', 'quantity_not_an_integer'],
    ['D4 · 1.45 minutes, read as 45', 'Total 1.45 minutes.', 45, 'Total 1.45 minutes.', 'quantity_not_an_integer'],
    ['D4 · a clock time', 'Total time 1:30 minutes.', 90, 'Total time 1:30 minutes.', 'quantity_not_an_integer'],
    // D5 — a Set collapsed two quantities into one.
    ['D5 · 20 and 20, collapsed to 20', 'I spent 20 minutes reviewing records and 20 minutes with the patient.', 20, 'I spent 20 minutes reviewing records and 20 minutes with the patient.', 'several_minute_quantities_stated'],
    // The two attacks that motivated #314 in the first place.
    ['#314 (3c) · a SUMMED total', 'I spent twenty minutes reviewing outside records and twenty five minutes with the patient.', 45, 'Dr: I spent twenty minutes reviewing outside records and twenty five minutes with the patient.', 'several_minute_quantities_stated'],
    ['#314 (3d) · a quote that is not in the transcript', 'We spent an hour together.', 60, 'Chief complaint: dysphagia.', 'quote_not_in_transcript'],
  ])('%s', (_what, quote, minutes, context, reason) => {
    expect(ground(quote, minutes, context)).toEqual(refused(reason));
  });

  it('D6 · a door that grounds against "" (transcriptText ?? \'\' on a typed visit) finds nothing', () => {
    // The door side of D6 is gate-314-grounding-context-doors; this pins what
    // the old doors' context did to a total the worker had grounded.
    expect(ground('Total time 45 minutes.', 45, 'Total time 45 minutes.')).toEqual({ ok: true });
    expect(ground('Total time 45 minutes.', 45, '')).toEqual(refused('quote_not_in_transcript'));
  });
});

describe('#314 v2 · the rest of the refusals', () => {
  it.each<[string, string, number, TotalTimeRefusal]>([
    ['a value the sentence does not state', 'Total time spent was thirty minutes.', 45, 'stated_quantity_differs_from_value'],
    ['a symptom duration', 'The pain lasts about forty five minutes after meals.', 45, 'not_stated_as_a_total'],
    ['two quantities, one of them the value', 'Total time 45 minutes, including 20 minutes of counselling.', 45, 'several_minute_quantities_stated'],
    ['an unreadable spoken number', 'Total time forty forty minutes.', 80, 'minute_quantity_unreadable'],
    ['a number kept apart from its unit ("or more")', 'Total time 45 or more minutes.', 45, 'minute_quantity_unreadable'],
    ['a number kept apart from its unit (adjectives)', 'Total 45 face-to-face minutes.', 45, 'minute_quantity_unreadable'],
    ['a number AFTER the unit', 'Total minutes: 45.', 45, 'minute_quantity_unreadable'],
    ['"45 minutes 30" — one more quantity', 'Total time 45 minutes 30.', 45, 'several_minute_quantities_stated'],
    ['a second windowed quantity', 'Total 45 minutes and another 20 additional minutes.', 45, 'several_minute_quantities_stated'],
    ['seconds', 'Total time 45 minutes and 30 seconds.', 45, 'seconds_quantity_stated'],
    ['a contraction', "Total time wasn't 45 minutes.", 45, 'negation_in_sentence'],
    ['⚠️ an unrelated "no" in the same sentence — refused, one-sided on purpose', 'No fever, total time 25 minutes.', 25, 'negation_in_sentence'],
    ['"not including"', 'Total time 45 minutes, not including the procedure.', 45, 'negation_in_sentence'],
    ['a previous visit', 'Previous visit total time 30 minutes.', 30, 'past_visit_marker'],
    // ⚠️ A LINE BREAK DOES NOT END A SENTENCE. v2 as first built split on every
    // line break, and these two then GROUNDED as 45. An unpunctuated line joins
    // the next, so its negation / past-visit marker reaches the total.
    ['"same as last time"', 'Same as last time, total time 30 minutes.', 30, 'past_visit_marker'],
    ['a 45-minute visit is not a stated total', 'This was a 45-minute visit, total time spent.', 45, 'not_stated_as_a_total'],
    ['an approximation', 'Total time about 45 minutes.', 45, 'not_stated_as_a_total'],
    ['bare "spent"', 'Spent 45 minutes.', 45, 'not_stated_as_a_total'],
    ['no minute quantity at all', 'Total time was long.', 45, 'no_minute_quantity_stated'],
  ])('%s', (_what, quote, minutes, reason) => {
    expect(ground(quote, minutes)).toEqual(refused(reason));
  });

  it.each([
    ['an empty quote', '', 45, 'quote_empty'],
    ['a whitespace quote', '  \n ', 45, 'quote_empty'],
    ['a zero value', 'Total time 0 minutes.', 0, 'minutes_not_a_positive_integer'],
    ['a fractional value', 'Total time 45 minutes.', 45.5, 'minutes_not_a_positive_integer'],
  ])('refuses %s', (_what, quote, minutes, reason) => {
    expect(groundTotalTime({ contextText: `x ${quote} x`, quote, minutes })).toEqual({ ok: false, reason });
  });
});

describe('#314 v2 · a total that WAS stated still becomes a fact', () => {
  it.each<[string, string, number, string?]>([
    ['the certification self-test sentence', SELF_TEST, 45, `Doctor: ${SELF_TEST} Patient: thank you.`],
    ['"Total time 45 minutes."', 'Total time 45 minutes.', 45],
    ['"Total time: 45 min."', 'Total time: 45 min.', 45],
    ['"a total of forty-five minutes"', 'I spent a total of forty-five minutes with the patient today.', 45],
    ['"Total face-to-face time was 30 minutes."', 'Total face-to-face time was 30 minutes.', 30],
    ['"45 minutes total."', '45 minutes total.', 45],
    ['"Time spent: 40 minutes."', 'Time spent: 40 minutes.', 40],
    ['an attached unit, "45min"', 'Total time 45min.', 45],
    ['REFLOWED across a newline in the transcript', 'Total time 45 minutes.', 45, 'Chief complaint: dysphagia.\nTotal time\n45 minutes.\nFollow up.'],
    ['reflowed, spoken, hyphenated', 'I spent a total of forty-five minutes with the patient today.', 45, 'I spent a total of\n   forty-five minutes with the patient today.'],
    ['⚠️ a different CASE in the transcript', 'total time 45 minutes.', 45, 'TOTAL TIME 45 MINUTES.'],
    ['a curly apostrophe in the transcript', "Patient's total time was 45 minutes.", 45, 'Patient’s total time was 45 minutes.'],
    ['a list-style note whose line ENDS in punctuation: that line is its own sentence', 'Total time 45 minutes', 45, 'ROS: no fever.\nTotal time 45 minutes'],
    ['"Total time today was 45 minutes."', 'Total time today was 45 minutes.', 45],
    ['"forty-five minutes in total with her"', 'I spent forty-five minutes in total with her.', 45],
    ['"Total 25 mins face to face."', 'Total 25 mins face to face.', 25],
    ['one hundred and twenty', 'Total time spent: one hundred and twenty minutes.', 120],
    ['a hundred', 'A total of a hundred minutes was spent.', 100],
    ['a total encounter time', 'Total encounter time was 30 minutes.', 30],
    ['a role-labelled conversation', 'Total time 45 minutes.', 45, 'Doctor: Total time 45 minutes.\nPatient: Thank you.'],
  ])('%s', (_what, quote, minutes, context) => {
    expect(ground(quote, minutes, context ?? `Doctor: ${quote}\nPatient: thank you.`)).toEqual({ ok: true });
  });
});

describe('#314 v2 · the SENTENCE is judged, not the quote the model chose', () => {
  it('a past-visit marker OUTSIDE the quote still refuses', () => {
    expect(ground('the total time was 45 minutes.', 45, 'Last visit the total time was 45 minutes.')).toEqual(
      refused('past_visit_marker'),
    );
  });

  it('a negation OUTSIDE the quote still refuses', () => {
    expect(ground('a total of 45 minutes', 45, 'This was not a total of 45 minutes.')).toEqual(
      refused('negation_in_sentence'),
    );
  });

  it('a second quantity OUTSIDE the quote still refuses', () => {
    expect(ground('Total time 45 minutes', 45, 'Total time 45 minutes, including 20 minutes of counselling.')).toEqual(
      refused('several_minute_quantities_stated'),
    );
  });

  it('⚠️ a decimal point is not a sentence end — "4.5" is not "4." then "5"', () => {
    expect(sentenceSpans('It took 4.5 minutes total. Next.').map((s) => s.end)).toEqual([26, 32]);
    expect(ground('5 minutes total.', 5, 'It took 4.5 minutes total.')).toEqual(refused('quantity_not_an_integer'));
    expect(ground('5 minutes total.', 5, 'It took .5 minutes total.')).toEqual(refused('quantity_not_an_integer'));
  });

  it('⚠️ EVERY occurrence counts — the model does not pick the harmless one', () => {
    expect(
      ground('total time was 45 minutes.', 45, 'Total time was 45 minutes. Last visit total time was 45 minutes.'),
    ).toEqual(refused('past_visit_marker'));
  });

  it('a quote that starts or ends inside a word is not located', () => {
    expect(ground('otal time 45 minutes.', 45, 'Total time 45 minutes.')).toEqual(refused('quote_splits_a_word'));
    expect(ground('Total time 4', 4, 'Total time 45 minutes.')).toEqual(refused('quote_splits_a_word'));
  });
});

describe('#314 v2 · MUTATION-KILL arms — each rule is the ONLY stop', () => {
  // Each input here grounds, WRONGLY, if exactly one rule is removed. They are
  // written so that no other rule refuses them for another reason.
  it.each<[string, string, number, TotalTimeRefusal]>([
    ['the hour rule', '45 minutes total and 1 hour of chart review.', 45, 'hour_quantity_stated'],
    ['the seconds rule', '45 minutes total and 30 seconds.', 45, 'seconds_quantity_stated'],
    ['the range rule', '30-45 minutes total.', 45, 'quantity_is_a_range'],
    ['the decimal tokeniser', '4.5 minutes total.', 5, 'quantity_not_an_integer'],
    ['the several-quantities rule', 'Total time 45 minutes, including 20 minutes of counselling.', 45, 'several_minute_quantities_stated'],
    ['⚠️ OCCURRENCES, NOT A SET', 'Total 20 minutes reviewing records and 20 minutes with the patient.', 20, 'several_minute_quantities_stated'],
    ['the negation rule', 'This was not a total of 45 minutes.', 45, 'negation_in_sentence'],
    ['the past-visit rule', 'Last visit the total time was 45 minutes.', 45, 'past_visit_marker'],
    ['the total construction', 'I spent 45 minutes in traffic getting here.', 45, 'not_stated_as_a_total'],
    ['"total" modifying a noun after the quantity', 'Patient waited 45 minutes total cholesterol was drawn.', 45, 'not_stated_as_a_total'],
    ['the value-equality rule', 'Total time spent was thirty minutes.', 45, 'stated_quantity_differs_from_value'],
    ['the windowed quantity', 'Total 45 face-to-face minutes and 20 minutes total.', 20, 'several_minute_quantities_stated'],
  ])('%s', (_rule, quote, minutes, reason) => {
    expect(ground(quote, minutes)).toEqual(refused(reason));
  });
});

describe('#314 · the spoken-number parser reads real cardinals only', () => {
  it.each([
    [['forty', 'five'], 45],
    [['five'], 5],
    [['twenty'], 20],
    [['nineteen'], 19],
    [['one', 'hundred'], 100],
    [['one', 'hundred', 'and', 'twenty'], 120],
    [['two', 'hundred', 'five'], 205],
    [['a', 'hundred'], 100],
  ])('%j -> %i', (words, n) => {
    expect(parseSpokenCardinal(words)).toBe(n);
  });

  it.each([
    [[]],
    [['forty', 'forty']],
    [['five', 'forty']],
    [['forty', 'fifteen']],
    [['forty', 'zero']],
    [['and']],
    [['one', 'hundred', 'and']],
    [['a']],
    [['hundred', 'hundred']],
    [['ten', 'hundred']],
    [['minutes']],
  ])('%j -> null', (words) => {
    expect(parseSpokenCardinal(words)).toBeNull();
  });

  it('finds every stated minute quantity, in order, as OCCURRENCES', () => {
    expect(statedMinuteQuantities('twenty minutes, then 25 mins, then forty-five minutes')).toEqual([20, 25, 45]);
    expect(statedMinuteQuantities('an hour and a half')).toEqual([]);
    expect(statedMinuteQuantities('and five minutes')).toEqual([5]);
    // ⚠️ two, not one — D5 was a Set.
    expect(statedMinuteQuantities('20 minutes and 20 minutes')).toEqual([20, 20]);
    expect(statedMinuteQuantities('45 or more minutes')).toEqual([null]);
    expect(statedMinuteQuantities('minutes: 45')).toEqual([null]);
    expect(statedMinuteQuantities('forty forty minutes')).toEqual([null]);
  });

  it('judges one sentence directly — the unit the doors and the worker share', () => {
    expect(judgeTotalTimeSentence(SELF_TEST, 45)).toBeNull();
    expect(judgeTotalTimeSentence(SELF_TEST, 44)).toBe('stated_quantity_differs_from_value');
  });
});

describe('#314 · end to end through projectEncounterFacts', () => {
  type Entities = Parameters<typeof projectEncounterFacts>[0]['entities'];
  const projectAll = (contextText: string, entities: Record<string, unknown>) =>
    projectEncounterFacts({ mode: 'text', contextText, entities: entities as unknown as Entities });
  const project = (contextText: string, quote: string, minutes: number) =>
    projectAll(contextText, { total_time_minutes: { minutes, evidence_quote: quote } }).filter(
      (f) => f.concept === 'total_time_minutes',
    );

  it('the self-test sentence yields one fact, valued "45"', () => {
    const facts = project(`Doctor: ${SELF_TEST}`, SELF_TEST, 45);
    expect(facts).toHaveLength(1);
    expect(facts[0]!.value).toBe('45');
  });

  it('a total reflowed across a newline yields one fact', () => {
    expect(project('Plan: diet.\nTotal time\n45 minutes.', 'Total time 45 minutes.', 45)).toHaveLength(1);
  });

  it('⚠️ the summed-durations attack yields NO fact', () => {
    const quote = 'I spent twenty minutes reviewing outside records and twenty five minutes with the patient.';
    expect(project(`Doctor: ${quote}`, quote, 45)).toEqual([]);
  });

  it('⚠️ an absent quote yields NO fact', () => {
    expect(project('Chief complaint: dysphagia.', 'We spent an hour together.', 60)).toEqual([]);
  });

  it('⚠️ an empty context — the old doors on a typed visit — yields NO fact', () => {
    expect(project('', 'Total time 45 minutes.', 45)).toEqual([]);
  });

  describe('⚠️ RULE 6 — a refused total projects EXACTLY as if L3 had returned no total', () => {
    // The quote is SHARED with a fact projected BEFORE the total block
    // (referring physician) and one projected AFTER it (ROS). `add()` numbers
    // quote occurrences, and a fact's id and offsets depend on that number — so
    // a refusal that still touched `add()` (or its counters) would shift the
    // ROS fact and fail deep equality even if no total fact survived.
    const Q = 'No fever, total time 25 minutes.';
    const base = {
      referring_physician: { name: 'Dr. Alan Whitfield', evidence_quote: Q },
      ros: [{ system: 'constitutional', finding: 'fever', polarity: 'denied', evidence_quote: Q }],
    };
    const context = `Doctor: ${Q}\n${Q}`;

    it('deep-equal to the projection with the key ABSENT', () => {
      expect(ground(Q, 25, context)).toEqual(refused('negation_in_sentence'));
      const withRefused = projectAll(context, { ...base, total_time_minutes: { minutes: 25, evidence_quote: Q } });
      expect(withRefused).toEqual(projectAll(context, base));
    });

    it('and deep-equal to the projection with the key NULL (the L3 schema default)', () => {
      const withRefused = projectAll(context, { ...base, total_time_minutes: { minutes: 25, evidence_quote: Q } });
      expect(withRefused).toEqual(projectAll(context, { ...base, total_time_minutes: null }));
    });

    it('NON-VACUITY — a GROUNDED total sharing the context DOES change the projection', () => {
      // ⚠️ NOT "Total time 25 minutes." — that string also occurs INSIDE `Q`,
      // whose sentence carries "no", and every occurrence counts. This one
      // occurs once.
      const G = 'Total time 30 minutes.';
      const ctx = `${context}\n${G}`;
      const b = { ...base, ros: [{ ...base.ros[0], evidence_quote: G }] };
      expect(ground(G, 30, ctx)).toEqual({ ok: true });
      const withGrounded = projectAll(ctx, { ...b, total_time_minutes: { minutes: 30, evidence_quote: G } });
      const without = projectAll(ctx, b);
      expect(withGrounded).not.toEqual(without);
      expect(withGrounded.filter((f) => f.concept === 'total_time_minutes')).toHaveLength(1);
    });
  });
});

describe('#314 v2 · a line break does NOT end a sentence (the decided trade)', () => {
  it.each<[string, string, string, TotalTimeRefusal]>([
    ['a negation on the unpunctuated line above', 'a total of 45 minutes.', 'This was not\na total of 45 minutes.', 'negation_in_sentence'],
    ['last visit on the unpunctuated line above', 'total time was 45 minutes.', 'Last visit,\ntotal time was 45 minutes.', 'past_visit_marker'],
    ['an unpunctuated list line with "no" above the total', 'Total time 45 minutes', 'ROS: no fever\nTotal time 45 minutes', 'negation_in_sentence'],
  ])('%s — refused', (_what, quote, context, reason) => {
    expect(ground(quote, 45, context)).toEqual(refused(reason));
  });

  it('the POSITIVE twin: the same lines, the first ending in a full stop, ground', () => {
    expect(ground('a total of 45 minutes.', 45, 'This was fine.\na total of 45 minutes.')).toEqual({ ok: true });
    expect(ground('Total time 45 minutes', 45, 'ROS: no fever.\nTotal time 45 minutes')).toEqual({ ok: true });
  });
});
