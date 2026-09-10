// ============================================================================
// #314 — A TOTAL TIME IS GROUNDED BEFORE IT BECOMES A FACT.
// ----------------------------------------------------------------------------
// The claims, each with the arm that fails if it is false:
//   · the refutation pass's two attacks now produce NO fact
//   · a total stated as digits or spelled, and said to be a total, still does
//   · the spoken-number parser reads only real cardinals, and refuses the rest
//   · end to end, `projectEncounterFacts` emits the fact exactly when grounded
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { projectEncounterFacts } from '../encounter-facts';
import {
  groundTotalTime,
  parseSpokenCardinal,
  statedMinuteQuantities,
} from '../total-time-grounding';

const SELF_TEST =
  'A total time of forty five minutes was spent on this encounter, including counselling and coordination of care.';

describe('#314 · the refutation pass\'s attacks now produce no fact', () => {
  it('⚠️ (3c) an L3 that SUMS two durations nobody stated as a total', () => {
    const quote = 'I spent twenty minutes reviewing outside records and twenty five minutes with the patient.';
    expect(groundTotalTime({ contextText: `Dr: ${quote}`, quote, minutes: 45 })).toEqual({
      ok: false,
      reason: 'several_minute_quantities_stated',
    });
  });

  it('⚠️ (3d) a quote that is not in the transcript', () => {
    expect(
      groundTotalTime({ contextText: 'Chief complaint: dysphagia.', quote: 'We spent an hour together.', minutes: 60 }),
    ).toEqual({ ok: false, reason: 'quote_not_in_transcript' });
  });

  it('a quote in the transcript whose number is not the value', () => {
    const quote = 'Total time spent was thirty minutes.';
    expect(groundTotalTime({ contextText: quote, quote, minutes: 45 })).toEqual({
      ok: false,
      reason: 'stated_quantity_differs_from_value',
    });
  });

  it('a symptom duration is not a total', () => {
    const quote = 'The pain lasts about forty five minutes after meals.';
    expect(groundTotalTime({ contextText: quote, quote, minutes: 45 })).toEqual({
      ok: false,
      reason: 'not_stated_as_a_total',
    });
  });

  it('hours are not minutes — refused, never converted', () => {
    const quote = 'We spent an hour together in total.';
    expect(groundTotalTime({ contextText: quote, quote, minutes: 60 })).toEqual({
      ok: false,
      reason: 'no_minute_quantity_stated',
    });
  });

  it('⚠️ two quantities are refused even when one of them is the value', () => {
    const quote = 'Total time 45 minutes, including 20 minutes of counselling.';
    expect(groundTotalTime({ contextText: quote, quote, minutes: 45 })).toEqual({
      ok: false,
      reason: 'several_minute_quantities_stated',
    });
  });

  it.each([
    ['an empty quote', '', 45, 'quote_empty'],
    ['a zero value', 'Total time 0 minutes.', 0, 'minutes_not_a_positive_integer'],
    ['a fractional value', 'Total time 45 minutes.', 45.5, 'minutes_not_a_positive_integer'],
  ])('refuses %s', (_what, quote, minutes, reason) => {
    expect(groundTotalTime({ contextText: `x ${quote} x`, quote, minutes })).toEqual({ ok: false, reason });
  });
});

describe('#314 · a total that WAS stated still becomes a fact', () => {
  it.each([
    ['the certification self-test sentence', SELF_TEST, 45],
    ['digits', 'Total time today was 45 minutes.', 45],
    ['a hyphenated spoken number', 'I spent forty-five minutes in total with her.', 45],
    ['"mins"', 'Total 25 mins face to face.', 25],
    ['a hundred and twenty', 'Total time spent: one hundred and twenty minutes.', 120],
    ['a hundred', 'A total of a hundred minutes was spent.', 100],
    ['a hyphenated compound unit', 'This was a 45-minute visit, total time spent.', 45],
  ])('%s', (_what, quote, minutes) => {
    expect(groundTotalTime({ contextText: `Doctor: ${quote} Patient: thank you.`, quote, minutes })).toEqual({ ok: true });
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

  it('finds every stated minute quantity, in order', () => {
    expect(statedMinuteQuantities('twenty minutes, then 25 mins, then forty-five minutes')).toEqual([20, 25, 45]);
    expect(statedMinuteQuantities('an hour and a half')).toEqual([]);
    expect(statedMinuteQuantities('and five minutes')).toEqual([5]);
  });
});

describe('#314 · end to end through projectEncounterFacts', () => {
  // Only the field the guard reads is supplied; every other entity category is
  // absent, which the projector already treats as "not dictated".
  const project = (contextText: string, quote: string, minutes: number) =>
    projectEncounterFacts({
      contextText,
      entities: { total_time_minutes: { minutes, evidence_quote: quote } },
    } as unknown as Parameters<typeof projectEncounterFacts>[0]).filter(
      (f) => f.concept === 'total_time_minutes',
    );

  it('the self-test sentence yields one fact, valued "45"', () => {
    const facts = project(`Doctor: ${SELF_TEST}`, SELF_TEST, 45);
    expect(facts).toHaveLength(1);
    expect(facts[0]!.value).toBe('45');
  });

  it('⚠️ the summed-durations attack yields NO fact', () => {
    const quote = 'I spent twenty minutes reviewing outside records and twenty five minutes with the patient.';
    expect(project(`Doctor: ${quote}`, quote, 45)).toEqual([]);
  });

  it('⚠️ an absent quote yields NO fact', () => {
    expect(project('Chief complaint: dysphagia.', 'We spent an hour together.', 60)).toEqual([]);
  });
});
