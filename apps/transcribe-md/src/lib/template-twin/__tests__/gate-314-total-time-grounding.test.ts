// ============================================================================
// #314 v3 — A TOTAL TIME IS GROUNDED BEFORE IT BECOMES A FACT.
// ----------------------------------------------------------------------------
// v3 flips the rule from a refusal lexicon to an ANCHORED ALLOWLIST: the whole
// sentence must be one canonical form. The claims, each with the arm that
// fails if it is false:
//   · every input round two drove through v2 (findings 0 and 3–11, with the
//     verifiers' own wider variants) and every earlier attack leaves BOTH
//     billing controls unfilled, in text AND dictation mode;
//   · every canonical total fills both, on the SAME harness — the
//     opposite-answer discipline, so a module that refuses everything fails
//     as loudly as one that accepts too much;
//   · each canonical form is the ONLY form its witness matches, so dropping a
//     form reds its witness;
//   · the certification encounter's own sentence grounds — IMPORTED from
//     verification-encounter, never copied;
//   · conversation mode never yields a total;
//   · a refused total projects exactly as if L3 had returned no total, and the
//     log carries a token, never a quote or a number.
// ============================================================================
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { projectEncounterFacts, type EncounterInputMode } from '../encounter-facts';
import { resolveTemplateFields } from '../resolver';
import {
  CANONICAL_TOTAL_FORMS,
  canonicalSentence,
  groundTotalTime,
  judgeTotalTimeSentence,
  parseSpokenCardinal,
  sentenceSpans,
  type TotalTimeRefusal,
} from '../total-time-grounding';
import { narrativeSentence } from '../verification-encounter';
import { field as probeField, mapping as probeMapping } from './resolver-probe';

/** The certification encounter's own total sentence — imported, never copied. */
const CERT = narrativeSentence('total_time_minutes') as string;

const NS: TotalTimeRefusal = 'not_stated_as_a_total';
const refused = (reason: TotalTimeRefusal) => ({ ok: false, reason });
const ground = (quote: string, minutes: number, context: string = quote) =>
  groundTotalTime({ contextText: context, quote, minutes });

// ── THE HARNESS: the two production billing controls ──────────────────────
// Controls 70 and 71 of the owner's form (compiled version d2120cdd): both
// narrative_text, both mapped extraction / total_time_minutes / current /
// value_only / unit optional — copied column for column from the read-only
// SELECT round two made. Every table below runs through this same harness.
const LINE_70 = probeField('7', {
  fieldId: 'ttf_e2bdb95b03283f39388ca07b',
  originalLabel: 'Total minutes spent with patient',
  displayOrder: 70,
});
const LINE_71 = probeField('8', {
  fieldId: 'ttf_ef6e199276f1691e18cf84d8',
  originalLabel: 'Total time minutes',
  displayOrder: 71,
});
const billingMapping = (f: typeof LINE_70) =>
  probeMapping(f, 'total_time_minutes', {
    laterality: 'not_applicable',
    unitPolicy: 'optional',
    approvedSynonyms: [],
  });

type Entities = Parameters<typeof projectEncounterFacts>[0]['entities'];

function billingLines(mode: EncounterInputMode, contextText: string, entities: Record<string, unknown>) {
  const facts = projectEncounterFacts({ mode, contextText, entities: entities as unknown as Entities });
  return resolveTemplateFields({
    fields: [LINE_70, LINE_71],
    mappings: [billingMapping(LINE_70), billingMapping(LINE_71)],
    facts,
    certifiedFieldIds: [LINE_70.fieldId, LINE_71.fieldId],
  }).map((r) => [r.status, r.value] as const);
}
const totalLines = (mode: EncounterInputMode, context: string, quote: string, minutes: number) =>
  billingLines(mode, context, { total_time_minutes: { minutes, evidence_quote: quote } });

/** Both controls with NO total key at all — what a refusal must equal. */
const BLANK = billingLines('text', 'Chief complaint: dysphagia.', {});
const FILLED = (minutes: number) => [
  ['supported', String(minutes)],
  ['supported', String(minutes)],
];
const MODES: readonly EncounterInputMode[] = ['text', 'dictation'];

describe('#314 v3 · the harness can say BOTH answers', () => {
  it('a blank is null on both controls, and a grounded total fills both', () => {
    expect(BLANK.map(([, value]) => value)).toEqual([null, null]);
    expect(totalLines('text', 'Total time 45 minutes.', 'Total time 45 minutes.', 45)).toEqual(FILLED(45));
    expect(FILLED(45)).not.toEqual(BLANK);
  });
});

// ── MUST NOT GROUND ─────────────────────────────────────────────────────────
// [what, context, quote, minutes, reason]. Where the quote is the whole
// context, `whole()` saves repeating it.
type Row = readonly [string, string, string, number, TotalTimeRefusal];
const whole = (what: string, sentence: string, minutes: number, reason: TotalTimeRefusal = NS): Row => [
  what,
  sentence,
  sentence,
  minutes,
  reason,
];

const MUST_NOT_GROUND: readonly Row[] = [
  // Finding 3 — thresholds and approximations, and the verifier's own.
  whole('[3] less than … total', 'Less than 45 minutes total.', 45),
  whole('[3] more than … total', 'More than 45 minutes total.', 45),
  whole('[3] >45', '>45 minutes total.', 45),
  whole('[3] about … total', 'About 45 minutes total.', 45),
  whole('[3] under … in total', 'Under 45 minutes in total.', 45),
  whole('[3] … or more', 'Total time 45 minutes or more.', 45),
  whole('[3] minutes+', 'Total time 45 minutes+.', 45),
  whole('[3] … or less', 'Total time is 45 minutes or less.', 45),
  whole('[3] at least a total of', 'At least a total of 45 minutes.', 45),
  whole('[3] maybe 50', 'Total time 45 minutes, maybe 50.', 45),
  whole('[3] 45+', '45+ minutes total.', 45),
  whole('[3] about N inside a form', 'Total time about 45 minutes.', 45),
  whole('[3] over N inside a form', 'Total time over 45 minutes.', 45),
  whole('[3]v approximately', 'Approximately 45 minutes total.', 45),
  whole('[3]v nearly', 'Nearly 45 minutes total.', 45),
  whole('[3]v up to', 'Up to 45 minutes total.', 45),
  whole('[3]v over … in total', 'Over 45 minutes in total.', 45),
  whole('[3]v roughly', 'Roughly a total of 45 minutes.', 45),
  whole('[3]v or so', 'Total 45 minutes or so.', 45),
  whole('[3]v estimated', 'Estimated 45 minutes total.', 45),
  // Finding 4 — a total of something that is not this visit.
  whole('[4] physical therapy per week', 'Patient does physical therapy for a total of 45 minutes per week.', 45),
  whole('[4] an infusion', 'The infusion runs a total of 45 minutes.', 45),
  whole('[4] care management this month', 'A total of 45 minutes of care management time was spent this month.', 45),
  whole('[4] wait time spent', 'Wait time spent was 45 minutes.', 45),
  whole('[4] travel time spent', 'Travel time spent: 45 minutes.', 45),
  whole('[4] anesthesia total time', 'Anesthesia total time 45 minutes.', 45),
  whole('[4] sub-total', 'Sub-total 45 minutes for counselling.', 45),
  whole('[4] per session', 'Total 45 minutes per session.', 45),
  whole('[4] walks … daily', 'She walks 45 minutes total, daily.', 45),
  ['[4] the patient drove', 'Doctor: How long was the drive?\nPatient: I drove a total of 45 minutes to get here.', 'a total of 45 minutes', 45, NS],
  ['[4]v the patient drove, labelled', 'Patient: I drove a total of 45 minutes to get here.', 'I drove a total of 45 minutes to get here.', 45, NS],
  whole('[4]v an MRI', 'The MRI takes a total of 45 minutes.', 45),
  whole('[4]v screen time', 'Screen time spent was 45 minutes a day.', 45),
  whole('[4]v seizures', 'Her seizures lasted a total of 45 minutes.', 45),
  whole('[4]v a labelled therapy total', 'Physical therapy: total time 45 minutes.', 45),
  whole('[4]v exercise daily', 'Total 45 minutes of exercise daily.', 45),
  // Finding 5 — an abbreviation period no longer lets the quote pick a half.
  ['[5a] 1 hr. 15', 'Seen for 1 hr. 15 minutes in total.', '15 minutes in total.', 15, NS],
  ['[5b] 1 hr. 45 min', 'Total time 1 hr. 45 min total.', '45 min total', 45, NS],
  ['[5c] Dr. Patel, last visit', 'At the last visit with Dr. Patel, total time was 45 minutes.', 'total time was 45 minutes', 45, NS],
  ['[5d] approx.', 'Last visit approx. 45 minutes total.', '45 minutes total.', 45, NS],
  ['[5]v 2 hrs. 30', 'Spent 2 hrs. 30 minutes in total with patient.', '30 minutes in total with patient.', 30, NS],
  ['[5]v prev. visit', 'Per prev. visit note total time was 40 minutes.', 'total time was 40 minutes.', 40, NS],
  ['[5]v a negation before approx.', 'Did not track, approx. 45 minutes total.', '45 minutes total.', 45, NS],
  ['[5]v a range across approx.', 'Approx. 30 to approx. 45 minutes total.', '45 minutes total.', 45, NS],
  ['[5]v 1 h. 20', 'Seen 1 h. 20 minutes total.', '20 minutes total.', 20, NS],
  // Finding 6 — mood: future, booked, conditional, reported, questioned.
  whole('[6] next visit', 'Next visit: total time 45 minutes.', 45),
  whole('[6] booked', 'The appointment was booked for a total of 45 minutes.', 45),
  whole('[6] if', 'If total time is 45 minutes, bill 99215.', 45),
  whole('[6] she said', 'She said the total time was 45 minutes.', 45),
  ['[6] a question, answered no', 'Was total time 45 minutes? No, closer to thirty.', 'Was total time 45 minutes?', 45, 'not_a_statement'],
  ['[6]v the same question, a narrower quote', 'Was total time 45 minutes? No, closer to thirty.', 'total time 45 minutes', 45, 'not_a_statement'],
  whole('[6]v a bare question', 'Total time 45 minutes?', 45, 'not_a_statement'),
  whole('an exclamation', 'Total time 45 minutes!', 45, 'not_a_statement'),
  whole('[6]v should aim for', 'We should aim for a total of 45 minutes next time.', 45),
  whole('[6]v unless', 'Unless it runs over, total time 45 minutes.', 45),
  whole('[6]v reported at urgent care', 'The patient reports the total time was 45 minutes at urgent care.', 45),
  whole('[6]v next appointment', 'Next appointment: a total of 45 minutes.', 45),
  whole('[6]v in case of', 'In case of complications, total time 45 minutes.', 45),
  ['[6]v actually, closer to thirty', 'Total time 45 minutes. Actually, closer to thirty.', 'Total time 45 minutes.', 45, 'corrected_in_next_sentence'],
  whole('[6]v scheduled for next week', 'Scheduled a total of 45 minutes for next week.', 45),
  whole('[6]v will be', 'Next time the total time will be 45 minutes.', 45),
  // Finding 7 — a past total.
  whole('[7] last week', 'Last week total time was 45 minutes.', 45),
  whole('[7] two weeks ago', 'Two weeks ago, total time was 45 minutes.', 45),
  whole("[7] yesterday's", "Yesterday's total time was 45 minutes.", 45),
  ['[7] last week, a narrower quote', 'Last week total time was 45 minutes.', 'total time was 45 minutes', 45, NS],
  whole('[7]v last month', 'Last month the total time was 45 minutes.', 45),
  whole("[7]v last week's", "Last week's total time was 45 minutes.", 45),
  whole('[7]v in March', 'In March the total time was 45 minutes.', 45),
  whole('[7]v back in the spring', 'Back in the spring, total time was 45 minutes.', 45),
  whole('[7]v the time before', 'The time before, total time was 45 minutes.', 45),
  whole('[7]v an earlier visit', 'At her earlier visit total time was 45 minutes.', 45),
  whole('[7]v a month ago', 'A month ago total time was 45 minutes.', 45),
  whole('[7]v on Monday', 'On Monday total time was 45 minutes.', 45),
  whole('[7]v last Tuesday', 'Last Tuesday, a total of 45 minutes.', 45),
  whole('[7]v last week she spent', 'Last week she spent 45 minutes in total.', 45),
  whole('[7]v the last follow-up', 'At the last follow-up, total time was 45 minutes.', 45),
  whole('[7]v the prior appt', 'At the prior appt, total time was 45 minutes.', 45),
  // Finding 8 — a total the sentence contradicts.
  whole('[8] instead of … twenty', 'Instead of a total of 45 minutes, we only had twenty.', 45),
  whole('[8] nowhere near', 'Nowhere near a total of 45 minutes.', 45),
  ['[8] nowhere near, a narrower quote', 'Nowhere near a total of 45 minutes.', 'a total of 45 minutes', 45, NS],
  ['[8] instead of, a narrower quote', 'Instead of a total of 45 minutes, we only had twenty.', 'a total of 45 minutes', 45, NS],
  whole('[8]v a bare digit', 'Instead of a total of 45 minutes, we only had 20.', 45),
  whole('[8]v rather than', 'Rather than a total of 45 minutes, it was about twenty.', 45),
  whole('[8]v far from', 'Far from a total of 45 minutes.', 45),
  whole('[8]v hardly', 'Hardly a total of 45 minutes.', 45),
  whole('[8]v less than a total of', 'Less than a total of 45 minutes.', 45),
  whole('[8]v planned but managed twenty', 'We planned a total of 45 minutes but only managed twenty.', 45),
  whole('[8]v scheduled but finished in twenty', 'She was scheduled for a total of 45 minutes but we finished in twenty.', 45),
  ['[8]v actually, it was twenty', 'Total time 45 minutes. Actually, it was twenty.', 'Total time 45 minutes.', 45, 'corrected_in_next_sentence'],
  // Finding 9 — a correction, and two totals.
  ['[9] correction, 30', 'Total time 45 minutes. Correction, total time 30 minutes.', 'Total time 45 minutes.', 45, 'corrected_in_next_sentence'],
  ['[9] strike that', 'Total time 45 minutes. Strike that.', 'Total time 45 minutes.', 45, 'corrected_in_next_sentence'],
  whole('[9]v , strike that', 'Total time 45 minutes, strike that.', 45),
  whole('[9]v , scratch that', 'Total time 45 minutes, scratch that.', 45),
  ['[9]v two totals, the first', 'Total time 45 minutes. Total time 30 minutes.', 'Total time 45 minutes.', 45, 'several_totals_stated'],
  ['[9]v two totals, the second', 'Total time 45 minutes. Total time 30 minutes.', 'Total time 30 minutes.', 30, 'several_totals_stated'],
  ['[9]v a semicolon, then a correction', 'Total time 45 minutes; correction, total time 30 minutes.', 'Total time 45 minutes', 45, NS],
  ['[9]v no, that is wrong', 'Total time 45 minutes. No, that is wrong.', 'Total time 45 minutes.', 45, 'corrected_in_next_sentence'],
  ['[9]v actually, 30', 'Total time 45 minutes. Actually, total time was 30 minutes.', 'Total time 45 minutes.', 45, 'corrected_in_next_sentence'],
  ['[9]v sorry, on a new line', 'Total time 45 minutes.\nSorry, I meant 30 minutes.', 'Total time 45 minutes.', 45, 'corrected_in_next_sentence'],
  ['[9]v an unpunctuated line, then strike that', 'Total time 45 minutes\nStrike that', 'Total time 45 minutes', 45, NS],
  ['[9]v lowercase dictation', 'total time 45 minutes. scratch that. total time 30 minutes.', 'total time 45 minutes.', 45, NS],
  // Finding 10 — a possessive hour, and joined numbers.
  whole("[10] an hour's discussion", "An hour's discussion and 15 minutes in total.", 15),
  whole('[10] forty and five', 'Forty and five minutes total.', 5, 'minute_quantity_unreadable'),
  whole('[10] 20 + 25', '20 + 25 minutes total.', 25),
  ["[10] an hour's, a narrower quote", "An hour's discussion and 15 minutes in total.", '15 minutes in total', 15, NS],
  ['[10] forty and five, a narrower quote', 'Forty and five minutes total.', 'five minutes total', 5, 'minute_quantity_unreadable'],
  ['[10] 20 + 25, a narrower quote', '20 + 25 minutes total.', '25 minutes total', 25, NS],
  whole("[10]v an hour's visit plus", "Total time, an hour's visit plus 15 minutes in total.", 15),
  whole('[10]v a curly possessive', 'An hour’s counselling and 15 minutes total.', 15),
  whole('[10]v twenty plus twenty-five', 'Twenty plus twenty-five minutes total.', 25),
  whole('[10]v 30 and 15', '30 and 15 minutes in total.', 15),
  whole("[10]v half an hour's", "Half an hour's review and 10 minutes total.", 10),
  // Finding 11 — C1 end to end, and the rule-level rows.
  ['[11] chest pain lasted', 'HPI. The chest pain lasted 20 minutes total. Plan: stress test.', 'The chest pain lasted 20 minutes total.', 20, NS],
  whole('[11] next visit slot', 'Plan: schedule a total of 60 minutes for the next visit.', 60),
  ['[11] last week, inside a note', 'Follow-up. Last week, total time was 45 minutes. Doing well today.', 'total time was 45 minutes', 45, NS],
  whole('[11] walks every day', 'Social history: she walks a total of 30 minutes every day.', 30),
  whole('[11] yesterday', 'Yesterday, total time was 45 minutes.', 45),
  whole('[11] planned', 'Planned total time 45 minutes.', 45),
  whole('[11] next visit total', 'Next visit total time 60 minutes.', 60),
  whole('[11] the initial consultation', 'At the initial consultation total time was 60 minutes.', 60),
  whole('[11] a seizure', 'The seizure lasted 3 minutes in total.', 3),
  whole('[11] the waiting room', 'Her husband spent a total of 45 minutes in the waiting room.', 45),
  whole('[11]v an MRI took', 'the MRI took a total of 40 minutes.', 40),
  whole('[11]v two weeks ago', 'Two weeks ago total time was 35 minutes.', 35),
  whole('[11]v the ER', 'She was seen in the ER where total time was 90 minutes.', 90),
  whole('[11]v three times weekly', 'Plan: physical therapy, a total of 30 minutes three times weekly.', 30),
  // v1 and v2 attacks and survivors, kept so none reopens.
  ['D1 · traffic', 'Patient: I spent 45 minutes in traffic getting here.', 'I spent 45 minutes in traffic getting here.', 45, NS],
  whole('D1 · total cholesterol', 'Total cholesterol was 240 and she waited 45 minutes in the lobby.', 45),
  ['D1 · a negated total', 'This was not a total of 45 minutes; I did not track time.', 'This was not a total of 45 minutes;', 45, NS],
  whole('D1 · last visit', 'Last visit the total time was 45 minutes.', 45),
  whole('D2 · one hour and fifteen', 'Total time spent today was one hour and fifteen minutes.', 15),
  whole('D2 · 1 hour 45', 'Total time 1 hour 45 minutes.', 45),
  whole('D2 · 1h 45', 'Total time 1h 45 minutes.', 45),
  whole('D2 · an hour', 'We spent an hour together in total.', 60),
  ['D3 · 5 inside 145', 'We spent 145 minutes total.', '5 minutes total', 5, 'quote_splits_a_word'],
  ['D3 · five inside twenty-five', 'We spent twenty-five minutes total.', 'five minutes total', 5, NS],
  whole('D4 · 30-45', 'Total time spent 30-45 minutes.', 45),
  whole('D4 · an en dash', 'Total time 30–45 minutes.', 45),
  whole('D4 · a spoken range', 'Thirty to forty-five minutes total.', 45),
  whole('D4 · 30 or 45', 'Total 30 or 45 minutes.', 45),
  whole('D4 · between', 'Total between 30 and 45 minutes.', 45),
  whole('D4 · 4.5', 'Total 4.5 minutes', 5),
  whole('D4 · 1.45', 'Total 1.45 minutes.', 45),
  whole('D4 · a clock time', 'Total time 1:30 minutes.', 90),
  whole('D5 · 20 and 20', 'I spent 20 minutes reviewing records and 20 minutes with the patient.', 20),
  ['#314 · a summed total', 'Dr: I spent twenty minutes reviewing outside records and twenty five minutes with the patient.', 'I spent twenty minutes reviewing outside records and twenty five minutes with the patient.', 45, NS],
  ['#314 · an absent quote', 'Chief complaint: dysphagia.', 'We spent an hour together.', 60, 'quote_not_in_transcript'],
  whole('[12] never', 'I never spent a total of 45 minutes.', 45),
  whole('[12] wasnt', 'It wasnt a total of 45 minutes.', 45),
  whole('[12] 1 hr 45', '1 hr 45 minutes total.', 45),
  whole('[12] 2 hours 45', '2 hours 45 minutes total.', 45),
  whole('[12] 30 secs', 'Total time 45 minutes and 30 secs.', 45),
  whole('[12] 1 second', 'Total time 44 minutes and 1 second.', 44),
  whole('[12] through', '30 through 45 minutes total.', 45),
  whole('[12] prior visit', 'Prior visit total time 30 minutes.', 30),
  whole('[12] last appointment', 'Last appointment total time 45 minutes.', 45),
  whole('[12] last encounter', 'Last encounter total time 45 minutes.', 45),
  whole('[12] subtotal', 'Subtotal 45 minutes.', 45),
  whole('[12] subtotal time', 'Subtotal time 45 minutes.', 45),
  whole('[12] downtime spent', 'Downtime spent 45 minutes.', 45),
  whole('[12] a quote across a semicolon', 'Total time 45 minutes; not counting the procedure.', 45),
  whole('v2 cost · no fever, total', 'No fever, total time 25 minutes.', 25),
  whole('v2 cost · not including', 'Total time 45 minutes, not including the procedure.', 45),
  whole('v2 cost · minutes: 45', 'Total minutes spent with patient: 45.', 45),
  whole('v2 cost · face-to-face minutes', 'Total 45 face-to-face minutes.', 45),
  whole('v2 cost · a 45-minute visit', 'This was a 45-minute visit, total time spent.', 45),
  ['line break · a negation above', 'This was not\na total of 45 minutes.', 'a total of 45 minutes.', 45, NS],
  ['line break · last visit above', 'Last visit,\ntotal time was 45 minutes.', 'total time was 45 minutes.', 45, NS],
  ['line break · an unpunctuated list line', 'ROS: no fever\nTotal time 45 minutes', 'Total time 45 minutes', 45, NS],
  // The brief's named refusals (round two's false-rejection list kept two).
  whole('[13] office hours', 'Total time 45 minutes after office hours.', 45),
  whole('[13] a parenthesised digit', 'Total time spent: forty-five (45) minutes.', 45),
  // F7's tail carries no quantity.
  whole('F7 · a number word in the tail', 'A total time of 45 minutes was spent on this encounter, including twenty minutes of counselling.', 45),
  whole('F7 · a digit in the tail', 'A total time of 45 minutes was spent on this encounter, including 20 minutes of counselling.', 45),
  whole('F7 · a time unit in the tail', 'A total time of 45 minutes was spent on this encounter, including an hour of counselling.', 45),
  // A quote that crosses a sentence end is not one sentence.
  ['a quote across a full stop', 'Total time 45 minutes. Follow up in two weeks.', 'minutes. Follow up', 45, NS],
];

describe('#314 v3 · every input round two drove through v2 leaves BOTH billing controls unfilled', () => {
  it.each(MUST_NOT_GROUND)('%s', (_what, context, quote, minutes, reason) => {
    expect(ground(quote, minutes, context)).toEqual(refused(reason));
    for (const mode of MODES) {
      expect(totalLines(mode, context, quote, minutes), `${mode} mode filled a billing line`).toEqual(BLANK);
    }
  });
});

// ── MUST GROUND — the same harness, the opposite answer ─────────────────────
type Accept = readonly [string, string, string, number];
const plain = (what: string, sentence: string, minutes = 45): Accept => [what, sentence, sentence, minutes];

const MUST_GROUND: readonly Accept[] = [
  // Round two's false rejections that v3 must accept.
  plain('[13] Total: 45 minutes.', 'Total: 45 minutes.'),
  plain('[13] Total time, 45 minutes.', 'Total time, 45 minutes.'),
  plain('[13] Total time spent, 45 minutes.', 'Total time spent, 45 minutes.'),
  plain('[13] 45 minutes total time.', '45 minutes total time.'),
  plain('[13] Time spent today: 45 minutes.', 'Time spent today: 45 minutes.'),
  plain('[13] 45 minutes spent in total.', '45 minutes spent in total.'),
  // The canonical controls.
  plain('Total time 45 minutes.', 'Total time 45 minutes.'),
  plain('I spent a total of 45 minutes with the patient.', 'I spent a total of 45 minutes with the patient.'),
  plain('Total time was forty five minutes.', 'Total time was forty five minutes.'),
  plain('45 minutes total.', '45 minutes total.'),
  plain('A total of 45 minutes.', 'A total of 45 minutes.'),
  plain('⚠️ the certification sentence, imported', CERT),
  // More of each form, and the shapes a real transcript takes.
  plain('F2 · with the patient', 'Total time spent with the patient was 45 minutes.'),
  plain('F5 · time spent:', 'Time spent: 40 minutes.', 40),
  plain('F1 · a total encounter time', 'Total encounter time was 30 minutes.', 30),
  plain('F1 · face-to-face', 'Total face-to-face time was 30 minutes.', 30),
  plain('F1 · min., with a colon', 'Total time: 45 min.'),
  plain('F1 · an attached unit', 'Total time 45min.'),
  plain('F1 · one hundred and twenty', 'Total time spent: one hundred and twenty minutes.', 120),
  plain('F4 · a hundred', 'A total of a hundred minutes.', 100),
  plain('F3 · forty-five, today', 'I spent a total of forty-five minutes with the patient today.'),
  plain('F7 · a plain tail', 'A total time of 45 minutes was spent with the patient, including counselling, education and coordination of care.'),
  ['inside a note', 'Exam normal. Total time 45 minutes. Follow up in two weeks.', 'Total time 45 minutes.', 45],
  ['REFLOWED across line breaks', 'Chief complaint: dysphagia.\nTotal time\n45 minutes.\nFollow up.', 'Total time 45 minutes.', 45],
  ['a different case in the transcript', 'TOTAL TIME 45 MINUTES.', 'total time 45 minutes.', 45],
  ['a list line ending in a full stop is its own sentence', 'ROS: no fever.\nTotal time 45 minutes', 'Total time 45 minutes', 45],
  ['the same total stated twice', 'Total time 45 minutes. Plan as above. Total time 45 minutes.', 'Total time 45 minutes.', 45],
  ['⚠️ "Waiting" is not the retraction "wait"', 'Total time 45 minutes. Waiting room was quiet.', 'Total time 45 minutes.', 45],
  ['⚠️ "Nothing" is not the retraction "no,"', 'Total time 45 minutes. Nothing further.', 'Total time 45 minutes.', 45],
  ['⚠️ the certification sentence inside certification-shaped text', [narrativeSentence('social_history.marital_status'), CERT, narrativeSentence('family_history')].join(' '), CERT, 45],
];

describe('#314 v3 · a canonical total FILLS both billing controls — the same harness', () => {
  it.each(MUST_GROUND)('%s', (_what, context, quote, minutes) => {
    expect(ground(quote, minutes, context)).toEqual({ ok: true });
    for (const mode of MODES) {
      expect(totalLines(mode, context, quote, minutes), `${mode} mode`).toEqual(FILLED(minutes));
    }
  });

  it('NON-VACUITY — the certification sentence really is the imported one, and says forty five', () => {
    expect(CERT).toMatch(/^A total time of forty five minutes was spent on this encounter, including /);
  });

  it('OPPOSITE ANSWER — both tables are populated, so neither verdict can pass alone', () => {
    expect(MUST_NOT_GROUND.length).toBeGreaterThanOrEqual(150);
    expect(MUST_GROUND.length).toBeGreaterThanOrEqual(25);
  });
});

// ── THE FORMS ───────────────────────────────────────────────────────────────
// One witness per form, matched by THAT form and no other — so deleting any
// form reds its own witness, and a new form cannot land without a row here.
const WITNESS: Readonly<Record<string, string>> = {
  F1: 'Total time 45 minutes.',
  F2: 'Total time spent with the patient was 45 minutes.',
  F3: 'I spent a total of 45 minutes with the patient.',
  F4: 'A total of 45 minutes.',
  F5: 'Time spent today: 45 minutes.',
  F6: '45 minutes total.',
  'F6-spent': '45 minutes spent in total.',
  F7: CERT,
};

describe('#314 v3 · the canonical forms, one witness each', () => {
  it('the exported list is exactly the forms that have witnesses', () => {
    expect(CANONICAL_TOTAL_FORMS.map((f) => f.id)).toEqual(Object.keys(WITNESS));
  });

  it.each(Object.entries(WITNESS))('%s is the ONLY form its witness matches, and it grounds', (id, sentence) => {
    const matching = CANONICAL_TOTAL_FORMS.flatMap((f) => (f.form.test(canonicalSentence(sentence)) ? [f.id] : []));
    expect(matching).toEqual([id]);
    expect(ground(sentence, 45)).toEqual({ ok: true });
  });

  it('a form matches the WHOLE sentence: a word before or after refuses', () => {
    expect(ground('The chest pain lasted 20 minutes total.', 20)).toEqual(refused(NS));
    expect(ground('Total time 45 minutes after office hours.', 45)).toEqual(refused(NS));
    expect(ground('Anesthesia total time 45 minutes.', 45)).toEqual(refused(NS));
  });

  it('Q is ONE quantity: no qualifier, no range, nothing between number and unit', () => {
    expect(ground('Total time about 45 minutes.', 45)).toEqual(refused(NS));
    expect(ground('Total time spent 30-45 minutes.', 45)).toEqual(refused(NS));
    expect(ground('Total 45 face-to-face minutes.', 45)).toEqual(refused(NS));
  });
});

describe('#314 v3 · one sentence judged directly', () => {
  it.each<[string, string, number, ReturnType<typeof judgeTotalTimeSentence>]>([
    ['the certification sentence', CERT, 45, null],
    ['the certification sentence, another value', CERT, 44, 'stated_quantity_differs_from_value'],
    ['an unreadable spoken number', 'Total time forty forty minutes.', 80, 'minute_quantity_unreadable'],
    ['a zero', 'Total time 0 minutes.', 45, 'minute_quantity_unreadable'],
    ['a question', 'Total time 45 minutes?', 45, 'not_a_statement'],
    ['no form', 'Spent 45 minutes.', 45, NS],
  ])('%s', (_what, sentence, minutes, verdict) => {
    expect(judgeTotalTimeSentence(sentence, minutes)).toBe(verdict);
  });
});

// ── SENTENCES ───────────────────────────────────────────────────────────────
describe('#314 v3 · a "." ends a sentence only before an uppercase letter or the end', () => {
  const ends = (s: string) => sentenceSpans(s).map((span) => span.end);
  it.each<[string, string, number]>([
    ['an abbreviation before a digit', 'Seen for 1 hr. 15 minutes in total.', 1],
    ['an abbreviation before a digit (approx.)', 'Last visit approx. 45 minutes total.', 1],
    ['a decimal point', 'It took 4.5 minutes total.', 1],
    ['a full stop before a lowercase word', 'total time 45 minutes. scratch that.', 1],
    ['a full stop before an uppercase letter', 'At the last visit with Dr. Patel, total.', 2],
    ['a line break alone', 'Total time\n45 minutes.', 1],
    ['; ! ? always end one', 'A? B! C; D.', 4],
  ])('%s', (_what, text, count) => {
    expect(ends(text)).toHaveLength(count);
  });

  it('the spans are exact', () => {
    expect(ends('It took 4.5 minutes total. Next.')).toEqual([26, 32]);
  });
});

// ── RULE 4 — every retraction word, each on its own ─────────────────────────
describe('#314 v3 · a retraction at the start of the NEXT sentence refuses', () => {
  it.each([
    'Correction.',
    'Strike that.',
    'Scratch that.',
    'Sorry.',
    'No wait.',
    'Wait.',
    'Actually, no change.',
    'I mean it.',
    'Make that thirty.',
    'Rather not.',
    'No, thirty.',
    'No.',
  ])('"%s"', (next) => {
    expect(ground('Total time 45 minutes.', 45, `Total time 45 minutes. ${next}`)).toEqual(
      refused('corrected_in_next_sentence'),
    );
  });

  it('CONTROL — the same total with an ordinary next sentence grounds', () => {
    expect(ground('Total time 45 minutes.', 45, 'Total time 45 minutes. Follow up in two weeks.')).toEqual({ ok: true });
  });
});

// ── LOCATION AND INPUT ──────────────────────────────────────────────────────
describe('#314 · the quote and the value', () => {
  it.each<[string, string, number, TotalTimeRefusal]>([
    ['an empty quote', '', 45, 'quote_empty'],
    ['a whitespace quote', '  \n ', 45, 'quote_empty'],
    ['a zero value', 'Total time 0 minutes.', 0, 'minutes_not_a_positive_integer'],
    ['a fractional value', 'Total time 45 minutes.', 45.5, 'minutes_not_a_positive_integer'],
  ])('refuses %s', (_what, quote, minutes, reason) => {
    expect(groundTotalTime({ contextText: `x ${quote} x`, quote, minutes })).toEqual(refused(reason));
  });

  it('a quote that starts or ends inside a word is not located', () => {
    expect(ground('otal time 45 minutes.', 45, 'Total time 45 minutes.')).toEqual(refused('quote_splits_a_word'));
    expect(ground('Total time 4', 4, 'Total time 45 minutes.')).toEqual(refused('quote_splits_a_word'));
  });

  it('⚠️ EVERY occurrence counts — the model does not pick the harmless one', () => {
    expect(
      ground('total time was 45 minutes', 45, 'Total time was 45 minutes. Last week, total time was 45 minutes.'),
    ).toEqual(refused(NS));
  });

  it('D6 · a door that grounds against "" finds nothing', () => {
    expect(ground('Total time 45 minutes.', 45, '')).toEqual(refused('quote_not_in_transcript'));
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
});

// ── CONVERSATION MODE — finding 0 ───────────────────────────────────────────
describe('#314 v3 · conversation mode yields NO total, whatever the text', () => {
  const SPOKEN = 'Total time was 45 minutes.';
  const PLAIN = `No, that makes sense. ${SPOKEN}`;
  const LABELLED = `[Patient #1, 2:53]: No, that makes sense.\n[Doctor #0, 3:05]: ${SPOKEN}`;

  it.each([
    ['the plain transcript every door reads', PLAIN],
    ["the role-labelled transcript the worker's L3 read", LABELLED],
  ])('%s', (_what, context) => {
    expect(totalLines('conversation', context, SPOKEN, 45)).toEqual(BLANK);
  });

  it('OPPOSITE ANSWER — the same plain text grounds in text and dictation mode, so the MODE refuses it', () => {
    for (const mode of MODES) expect(totalLines(mode, PLAIN, SPOKEN, 45)).toEqual(FILLED(45));
  });
});

// ── RULE 6 — a refused total projects EXACTLY as if L3 had returned none ────
describe('#314 · a refused total projects exactly as if L3 had returned no total', () => {
  type AnyEntities = Record<string, unknown>;
  const projectAll = (mode: EncounterInputMode, contextText: string, entities: AnyEntities) =>
    projectEncounterFacts({ mode, contextText, entities: entities as unknown as Entities });
  // The quote is SHARED with a fact projected BEFORE the total block (referring
  // physician) and one AFTER it (ROS). `add()` numbers quote occurrences, so a
  // refusal that still touched `add()` would shift the ROS fact and fail deep
  // equality even if no total fact survived.
  const Q = 'No fever, total time 25 minutes.';
  const base = {
    referring_physician: { name: 'Dr. Alan Whitfield', evidence_quote: Q },
    ros: [{ system: 'constitutional', finding: 'fever', polarity: 'denied', evidence_quote: Q }],
  };
  const context = `Doctor: ${Q}\n${Q}`;

  it('deep-equal to the projection with the key ABSENT, and with it NULL', () => {
    expect(ground(Q, 25, context)).toEqual(refused(NS));
    const withRefused = projectAll('text', context, { ...base, total_time_minutes: { minutes: 25, evidence_quote: Q } });
    expect(withRefused).toEqual(projectAll('text', context, base));
    expect(withRefused).toEqual(projectAll('text', context, { ...base, total_time_minutes: null }));
  });

  it('⚠️ a CONVERSATION refusal is deep-equal too', () => {
    const G = 'Total time 30 minutes.';
    const ctx = `${context}\n${G}`;
    const withTotal = projectAll('conversation', ctx, { ...base, total_time_minutes: { minutes: 30, evidence_quote: G } });
    expect(withTotal).toEqual(projectAll('conversation', ctx, base));
  });

  it('NON-VACUITY — a GROUNDED total sharing the context DOES change the projection', () => {
    const G = 'Total time 30 minutes.';
    const ctx = `${context}\n${G}`;
    const b = { ...base, ros: [{ ...base.ros[0], evidence_quote: G }] };
    expect(ground(G, 30, ctx)).toEqual({ ok: true });
    const withGrounded = projectAll('text', ctx, { ...b, total_time_minutes: { minutes: 30, evidence_quote: G } });
    expect(withGrounded).not.toEqual(projectAll('text', ctx, b));
    expect(withGrounded.filter((f) => f.concept === 'total_time_minutes')).toHaveLength(1);
  });
});

// ── THE LOG IS NOT A PHI SURFACE ────────────────────────────────────────────
describe('#314 · a refusal logs a fixed token, never a quote or a number', () => {
  afterEach(() => vi.restoreAllMocks());

  it.each<[string, EncounterInputMode, string, string]>([
    ['text mode', 'text', 'Less than 45 minutes total.', 'not_stated_as_a_total'],
    ['conversation mode', 'conversation', 'Total time 45 minutes.', 'conversation_mode_not_grounded'],
  ])('%s', (_what, mode, sentence, token) => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    totalLines(mode, sentence, sentence, 45);
    const lines = warn.mock.calls.map((c) => String(c[0])).filter((l) => l.includes('total_time_minutes withheld'));
    expect(lines).toEqual([`[template-twin:facts] total_time_minutes withheld: ${token}`]);
    expect(lines.join(' ')).not.toMatch(/45|minutes total|less than/i);
  });
});
