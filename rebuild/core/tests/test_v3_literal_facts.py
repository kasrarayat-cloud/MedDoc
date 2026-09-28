"""Full source facts preserve their actor and qualifiers; no provider interpretation."""
import copy
import json
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from core import generation as g
from core.v3_destination import destination_temporal_scopes
from .test_v3_ordinary_notes import LIVE, field
from .test_v3_field_relations import offered

FIXTURE = json.loads(Path(__file__).with_name('fixtures').joinpath('ordinary_literal_cases.json').read_text())


def fields():
    result = []
    for row in FIXTURE['cases']:
        target = field(row['key'], row['label']); target['context'] = row['context']
        if row['source_questions']: target['source_questions'] = copy.deepcopy(row['source_questions'])
        result.append(target)
    return result


@override_settings(**dict(LIVE, V3_FIELD_RELATIONS=True, V3_HISTORY_CONTEXT=False))
class OrdinaryLiteralFacts(SimpleTestCase):
    def assert_status(self, target, notes, quote, status):
        answer = offered(notes, [target], {target['key']: [quote]})[target['key']]
        self.assertEqual(answer['status'], status)
        if status == 'supported':
            self.assertEqual(answer['text'], quote)
            self.assertEqual(g.governed_decisions(notes, [target], {target['key']: answer}), [])
            governed = g.as_currently_governed(g.governance_for(notes, [target]), notes, {**target, **answer})
            self.assertEqual((governed['status'], governed['text']), ('supported', quote))
        return answer

    def test_seven_unchanged_complete_facts_work_together_in_original_twelve_unit_source(self):
        catalogue = fields(); picks = {r['key']: [r['quote']] for r in FIXTURE['cases']}
        answers = offered(FIXTURE['notes'], catalogue, picks)
        for row in FIXTURE['cases']:
            self.assertEqual((answers[row['key']]['status'], answers[row['key']]['text']), ('supported', row['quote']))
        self.assertEqual(g.governed_decisions(FIXTURE['notes'], catalogue, answers), [])

    def test_entity_scope_does_not_borrow_another_person_or_hypothetical_fact(self):
        target = next(f for f in fields() if f['key'] == 'v3_46')
        quote = 'The prescribed medication is administered by residence staff.'
        self.assert_status(target, quote, quote, 'supported')
        for prefix in ('Family history:\n', "The patient's father is receiving treatment. ",
                       'Father: takes medication.\n', 'Father: takes medication.\n\n',
                       'John is receiving treatment. ', 'The clinician has diabetes. '):
            with self.subTest(prefix=prefix): self.assert_status(target, prefix + quote, quote, 'conflict')
        for quote in ("The father's medication is administered by residence staff.",
                      'A medication is administered by residence staff.',
                      'The prescribed medication might be administered by residence staff.',
                      'The prescribed medication is generally administered by residence staff.',
                      'If needed, the prescribed medication is administered by residence staff.',
                      'The prescribed medication administered by residence staff.',
                      'The neighbour is receiving treatment.'):
            with self.subTest(quote=quote): self.assert_status(target, quote, quote, 'conflict')
        # Only an explicit grammatical patient subject resets a prior foreign actor.
        patient = 'The patient is receiving treatment.'
        quoted = 'The prescribed medication is administered by residence staff.'
        notes = 'Father: takes medication. ' + patient + ' ' + quoted
        self.assert_status(target, notes, quoted, 'supported')
        notes = 'Father: takes medication. The patient advocate is receiving treatment. ' + quoted
        self.assert_status(target, notes, quoted, 'conflict')
        notes = 'Father: takes medication. The patient potatoes. ' + quoted
        self.assert_status(target, notes, quoted, 'conflict')

    def test_clinical_actor_requires_the_patient_object_and_matching_contact_question(self):
        visit = next(f for f in fields() if f['key'] == 'v3_53')
        illness = next(f for f in fields() if f['key'] == 'v3_50')
        good = 'The clinical supervisor saw the patient at the clinic.'
        self.assert_status(visit, good, good, 'supported')
        self.assert_status(illness, good, good, 'conflict')
        for quote in ('The clinical supervisor saw another patient at the clinic.',
                      "The clinical supervisor saw the patient's father at the clinic.",
                      'The clinical supervisor has diabetes.', 'The mother saw the patient at the clinic.'):
            with self.subTest(quote=quote): self.assert_status(visit, quote, quote, 'conflict')

    def test_reported_foreign_actor_stays_inside_the_elicited_response_destination(self):
        target = next(f for f in fields() if f['key'] == 'v3_25')
        quote = next(r['quote'] for r in FIXTURE['cases'] if r['key'] == target['key'])
        self.assert_status(target, quote, quote, 'supported')
        for bad in (quote.replace('about relationships,', 'about allergies,'),
                    quote.replace('the patient said', 'the father said'),
                    quote.replace('When asked', 'If asked'),
                    quote.replace('staff also confirm', 'staff might confirm')):
            with self.subTest(quote=bad): self.assert_status(target, bad, bad, 'conflict')
        unrelated = next(f for f in fields() if f['key'] == 'v3_44')
        self.assert_status(unrelated, quote, quote, 'conflict')
        unrelated = field('f', 'What physical illness affects relationships?')
        unrelated['context'] = 'Clinical report'
        self.assert_status(unrelated, quote, quote, 'conflict')

    def test_only_valid_exact_generated_link_label_is_excluded_from_temporal_semantics(self):
        target = next(f for f in fields() if f['key'] == 'v3_25')
        quote = next(r['quote'] for r in FIXTURE['cases'] if r['key'] == target['key'])
        self.assertEqual(destination_temporal_scopes(target), [])
        for mutate in (lambda f: f.pop('source_questions'),
                       lambda f: f['source_questions'][0]['source'].update(fingerprint='bad'),
                       lambda f: f['source_questions'][0].update(question='A changed question?')):
            bad = copy.deepcopy(target); mutate(bad)
            self.assertTrue(destination_temporal_scopes(bad))
            self.assert_status(bad, quote, quote, 'conflict')
        target['source_questions'][0]['question'] += ' What happened before treatment?'
        target['context'] += ' What happened before treatment?'
        self.assertEqual([direction for direction, event in destination_temporal_scopes(target)], ['before'])
        self.assert_status(target, quote, quote, 'conflict')
        direct = field('f', 'Symptoms preceding treatment')
        self.assertTrue(destination_temporal_scopes(direct))

    def test_no_literal_fact_allowance_without_pinned_parser_or_ordinary_record(self):
        target = next(f for f in fields() if f['key'] == 'v3_21')
        quote = next(r['quote'] for r in FIXTURE['cases'] if r['key'] == target['key'])
        with patch('core.v3_syntax._parser', return_value=None): self.assert_status(target, quote, quote, 'conflict')
        old = {'status': 'supported', 'text': quote, 'reviewed': True,
               'evidence': [{'quote': quote, 'start': 0, 'end': len(quote)}]}
        self.assertEqual(g.governed_decisions(quote, [target], {target['key']: old}), [target['label']])
