"""Retained raw-ASR responses and source-heading/clinical-qualifier controls.

The provider response fixtures are synthetic, unchanged first outputs. New
selections are explicit offline counterfactuals, never a regraded provider run.
"""
import json
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from .test_transcript_context import proof
from .test_v3_field_relations import relation_wire
from .test_v3_supersession_floor import SONNET_55_DEFAULT, raw


FIXTURES = Path(__file__).parents[3] / 'docs/rebuild/v1/voice-retained-20261003/raw-asr-response-fixtures.json'


@override_settings(**SONNET_55_DEFAULT)
class SourceHeadingAndSelection(SimpleTestCase):
    def setUp(self):
        self.cases = json.loads(FIXTURES.read_text())['cases']
        self.fields = self.cases[0]['catalogue']

    def answers(self, notes, label, picks, relations=None, context=True):
        field = next(f for f in self.fields if f['label'] == label)
        wire = relation_wire(notes, self.fields, {field['key']: picks},
                             overrides={(field['key'], quote): relation for quote, relation in (relations or {}).items()})
        result = raw(notes, self.fields, wire, g.SONNET_5_5)
        if context:
            result['patient_default_context'] = proof(notes)
        return field, r.validated(result)[field['key']]

    def supported(self, notes, label, picks, relations=None):
        field, answer = self.answers(notes, label, picks, relations)
        self.assertEqual((answer['status'], answer['text']), ('supported', '\n'.join(picks)), answer)
        self.assertEqual([e['quote'] for e in answer['evidence']], picks)
        self.assertEqual(g.governed_decisions(notes, self.fields, {field['key']: answer}), [])
        page = g.as_currently_governed(g.governance_for(notes, self.fields), notes, {**field, **answer})
        self.assertEqual((page['status'], page['text']), ('supported', answer['text']))

    def held(self, notes, label, picks, relations=None):
        field, answer = self.answers(notes, label, picks, relations)
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''), answer)
        stored = {**answer, 'status': 'supported', 'text': '\n'.join(picks)}
        self.assertEqual(g.governed_decisions(notes, self.fields, {field['key']: stored}), [label])
        page = g.as_currently_governed(g.governance_for(notes, self.fields), notes, {**field, **stored})
        self.assertEqual((page['status'], page['text']), ('conflict', ''))

    def test_retained_provider_responses_preserve_first_results_and_invalid_selections(self):
        for case in self.cases:
            with self.subTest(attempt=case['attempt']):
                notes = case['notes']
                review = case['persisted_review_evidence']
                self.assertTrue(review['patient_context_review_verified'])
                self.assertTrue(review['applied'][0]['patient_default_context'])
                self.assertFalse(review['applied'][0]['corrected'])
                self.assertEqual(case['reviewed_context_payload']['reviewed_sha256'], review['notes_sha256'])
                result = {'anthropic_response': SimpleNamespace(model=case['response_model'],
                    stop_reason=case['response_stop_reason'],
                    content=[SimpleNamespace(type='text', text=case['response_text'])]),
                    'ordinary_field_contract': r.CONTRACT, 'notes': notes, 'fields': case['catalogue'],
                    'full_catalogue': case['catalogue'], 'context_labels': case['context_labels'],
                    'requested_model': case['request_model'], 'patient_default_context': proof(notes)}
                answers = r.validated(result)
                self.assertEqual(sum(a['status'] == 'supported' for a in case['first_answers'].values()), 1)
                for key, first in case['first_answers'].items():
                    if case['attempt'] == '003' and key == 'v3_3':
                        # Offline validation preserves the literal reviewed raw
                        # ASR "strain" and its documented clinician speaker.
                        # The audio says "sprain": this is source fidelity,
                        # not audio accuracy or a new successful paid outcome.
                        self.assertEqual(first['status'], 'conflict')
                        self.assertEqual((answers[key]['status'], answers[key]['text']),
                            ('supported', 'The clinician explicitly documents a left ankle strain.'))
                        self.assertEqual([e['quote'] for e in answers[key]['evidence']],
                            ['The clinician explicitly documents a left ankle strain.'])
                        continue
                    if case['attempt'] == '005' and key in ('v3_6', 'v3_7', 'v3_8', 'v3_10', 'v3_11'):
                        # A new offline revalidation can recover five faithful
                        # observations. The historical first result is retained
                        # verbatim, not replaced or regraded as a provider run.
                        self.assertEqual(first['status'], 'conflict')
                        self.assertEqual(answers[key]['status'], 'supported', (key, answers[key]))
                        self.assertTrue(answers[key]['evidence'])
                        if key == 'v3_11':
                            self.assertEqual(answers[key]['text'],
                                'Recommendation, follow-up with the referring clinician in two weeks.')
                        if key == 'v3_6':
                            self.assertEqual(answers[key]['text'],
                                'Sigmoid diverticulosis and small internal hemorrhoids.\nNo polyps were seen.')
                        continue
                    self.assertEqual({name: answers[key].get(name) for name in ('status', 'text', 'evidence')}, first)

    def test_the_application_request_explains_the_exact_selection_union(self):
        compiled = r.compile_request('The patient reports knee pain.', self.fields, g.configuration(self.fields))
        instructions = compiled['wire']['system']
        self.assertIn('unit_ids must be exactly the union of context.answer and context.qualifier', instructions)
        self.assertIn('context.answer [2] and context.qualifier [1] require unit_ids [1,2], not [2]', instructions)
        self.assertIn('Never select independent, contrary or unresolved units', instructions)
        self.assertIn('A heading that adds a subject, negation, time, uncertainty or other clinical qualification', instructions)

    def test_an_exact_bare_heading_keeps_its_own_complete_patient_answer_useful(self):
        for label, source in (('Assessment', 'The patient has a left ankle sprain.'),
                              ('Plan', 'The patient will rest.')):
            with self.subTest(label=label):
                self.supported(label + '. ' + source, label, [source])

    def test_a_complete_clinical_qualifier_remains_in_the_headed_answer(self):
        first = 'The patient reports knee pain.'
        second = 'The patient reports that the pain is worse on stairs.'
        notes = 'Subjective. ' + first + ' ' + second
        self.supported(notes, 'Subjective', [first, second], {second: 'qualifier'})

    def test_no_declared_qualifier_is_adopted_without_its_complete_source(self):
        first = 'The patient reports knee pain.'
        second = 'The patient reports that the pain is worse on stairs.'
        self.held('Subjective. ' + first + ' ' + second, 'Subjective', [first], {second: 'qualifier'})
        # Even an exact bare heading declared a qualifier remains governed by
        # the existing selection contract. The application never repairs it.
        self.held('Assessment. The patient has a left ankle sprain.', 'Assessment',
                  ['The patient has a left ankle sprain.'], {'Assessment.': 'qualifier'})

    def test_a_heading_supplies_neither_an_actor_nor_a_clinical_fact(self):
        for source in ('Her father has a left ankle sprain.', 'She has a left ankle sprain.'):
            with self.subTest(source=source):
                self.held('Assessment. ' + source, 'Assessment', [source])
        self.held('Assessment. If the patient has a left ankle sprain, the patient will need review.',
                  'Assessment', ['If the patient has a left ankle sprain, the patient will need review.'])

    def test_a_documented_uncertain_assessment_keeps_its_uncertainty(self):
        source = 'The patient may have a left ankle sprain.'
        self.supported('Assessment. ' + source, 'Assessment', [source])

    def test_clinical_heading_modifiers_and_other_field_boundaries_still_hold(self):
        source = 'The patient has a left ankle sprain.'
        self.held('Assessment possible diagnosis. ' + source, 'Assessment', [source])
        self.held('Assessment. Plan. ' + source, 'Assessment', [source])

    def test_contradictions_and_corrections_still_govern_a_headed_answer(self):
        source = 'The patient has a left ankle sprain.'
        self.held('Assessment. ' + source + ' The patient does not have a left ankle sprain.',
                  'Assessment', [source])
        self.held('Assessment. ' + source + ' Correction: the earlier assessment was entered in error.',
                  'Assessment', [source])


@override_settings(**SONNET_55_DEFAULT)
class ReviewedSourceOwnership(SimpleTestCase):
    answers = SourceHeadingAndSelection.answers
    supported = SourceHeadingAndSelection.supported
    held = SourceHeadingAndSelection.held

    def setUp(self):
        self.cases = json.loads(FIXTURES.read_text())['cases']
        self.procedure = next(c for c in self.cases if c['attempt'] == '005')
        self.fields = self.procedure['catalogue']

    def test_six_clear_original_procedure_facts_keep_complete_source_evidence(self):
        for label, source in (('Procedure', 'Diagnostic colonoscopy.'),
                ('Anesthesia', 'Monitored anesthesia care.'),
                ('Bowel preparation score', 'BBPS eight.'),
                ('Polyps', 'No polyps were seen.'),
                ('Specimens', 'No specimens were collected.'),
                ('Immediate complications', 'There were no immediate complications.')):
            with self.subTest(label=label):
                self.supported(self.procedure['notes'], label, [source])

    def test_whole_original_response_requires_the_complete_selection_union(self):
        case = self.procedure
        notes = case['notes']
        units = g.source_units(notes, self.fields)[0]
        known = {u['id']: u for u in units}
        by_key = {f['key']: f for f in self.fields}
        supported = {'Procedure', 'Anesthesia', 'Bowel preparation score', 'Indication',
                     'Polyps', 'Specimens', 'Immediate complications', 'Findings', 'Recommendation'}
        for mode in ('complete-declared-union', 'bare-own-heading-independent'):
            with self.subTest(mode=mode):
                wire = json.loads(case['response_text'])
                for item in wire['fields']:
                    if mode == 'bare-own-heading-independent':
                        own = by_key[item['key']]['label'].strip().rstrip(':').casefold() + '.'
                        headings = [uid for uid in item['context']['qualifier']
                                    if known[uid]['quote'].casefold() == own]
                        for uid in headings:
                            item['context']['qualifier'].remove(uid)
                            item['context']['independent'].append(uid)
                        item['context']['independent'].sort()
                    item['unit_ids'] = sorted(set(item['context']['answer']) | set(item['context']['qualifier']))
                result = raw(notes, self.fields, wire, g.SONNET_5_5)
                result['patient_default_context'] = proof(notes)
                answers = r.validated(result)
                selected = {item['key']: item['unit_ids'] for item in wire['fields']}
                # The immutable original response and its seven earlier useful
                # answers remain recorded. Complete reviewed source can now
                # prove Findings and the own Recommendation; garbled Extent
                # and C08's blood-loss ambiguity still hold.
                self.assertEqual(sum(a['status'] == 'supported' for a in answers.values()), 9)
                adopted = {}
                for field in self.fields:
                    answer = answers[field['key']]
                    if field['label'] in supported:
                        quotes = [known[uid]['quote'] for uid in selected[field['key']]]
                        self.assertEqual((answer['status'], answer['text']), ('supported', '\n'.join(quotes)))
                        self.assertEqual([e['quote'] for e in answer['evidence']], quotes)
                        adopted[field['key']] = answer
                    else:
                        self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                    page = g.as_currently_governed(g.governance_for(notes, self.fields), notes, {**field, **answer})
                    self.assertEqual((page['status'], page['text']), (answer['status'], answer['text']))
                self.assertEqual(g.governed_decisions(notes, self.fields, adopted), [])

    def test_review_confirmation_and_exact_span_are_prerequisites(self):
        for label, notes, source in (('Procedure', 'Procedure. Diagnostic colonoscopy.', 'Diagnostic colonoscopy.'),
                ('Polyps', 'No polyps were seen.', 'No polyps were seen.')):
            with self.subTest(label=label):
                field, answer = self.answers(notes, label, [source], context=False)
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                wire = relation_wire(notes, self.fields, {field['key']: [source]})
                result = raw(notes, self.fields, wire, g.SONNET_5_5)
                result['patient_default_context'] = proof(notes, end=notes.index(source) + 2)
                self.assertEqual(r.validated(result)[field['key']]['status'], 'conflict')

    def test_a_bare_heading_never_grants_another_person_or_speaker(self):
        for source in ('Her father has a colonoscopy.', 'The doctor has a colonoscopy.',
                'Alex has a colonoscopy.', 'She has a colonoscopy.', 'I have a colonoscopy.',
                'We have a colonoscopy.', 'You have a colonoscopy.', '"Diagnostic colonoscopy."'):
            with self.subTest(source=source):
                self.held('Procedure. ' + source, 'Procedure', [source])
        self.held('Her father reports rectal bleeding. Procedure. Diagnostic colonoscopy.',
                  'Procedure', ['Diagnostic colonoscopy.'])

    def test_heading_modifiers_multiple_headings_and_following_roles_stay_unresolved(self):
        source = 'Diagnostic colonoscopy.'
        for notes in ('Possible procedure. ' + source, 'Procedure tomorrow. ' + source,
                'Procedure. Procedure. ' + source, 'Procedure. Endoscopist. ' + source,
                'Procedure. Diagnostic colonoscopy on her father.'):
            with self.subTest(notes=notes):
                selected = source if source in notes else 'Diagnostic colonoscopy on her father.'
                self.held(notes, 'Procedure', [selected])

    def test_completed_observations_do_not_infer_a_name_time_or_hypothetical_event(self):
        for label, source in (('Polyps', 'No polyps were seen in her father.'),
                ('Polyps', 'No polyps were seen by Dr Alex.'),
                ('Polyps', 'No polyps may be seen.'),
                ('Polyps', 'If no polyps were seen, review would be needed.'),
                ('Polyps', 'No polyps were seen last year.'),
                ('Specimens', 'No specimens were collected from her father.')):
            with self.subTest(source=source):
                self.held(source, label, [source])

    def test_qualifiers_contradictions_and_corrections_cannot_be_independent_permissions(self):
        source = 'No polyps were seen.'
        for tail in ('Polyps were seen.', 'Correction: polyps were seen.',
                     'Possible polyps.', 'No polyps were seen in the previous examination.'):
            with self.subTest(tail=tail):
                self.held(source + ' ' + tail, 'Polyps', [source])
        self.held(source + ' The examination was entered in error.', 'Polyps', [source])

    def test_finished_diff_invalid_source_counterexamples_remain_held(self):
        source = 'No polyps were seen.'
        for annotation in ('The report was entered in error.',
                'The observation was entered in error.', 'The finding was entered in error.',
                'The results were entered in error.', 'The endoscopy record was entered in error.',
                'The clinician entered the report in error.'):
            with self.subTest(annotation=annotation):
                self.held(source + ' ' + annotation, 'Polyps', [source])
        # The complete passive frame supplies the invalidation. A numeric
        # correction is a different source shape, not a new noun whitelist.
        self.supported(source + ' The earlier six out of ten was entered in error.', 'Polyps', [source])
        self.supported(source + ' The report was not entered in error.', 'Polyps', [source])

    def test_human_source_scope_survives_bare_headings_until_explicit_patient_reanchor(self):
        source = 'Diagnostic colonoscopy.'
        for lead in ('The doctor underwent colonoscopy.', 'The nurse underwent colonoscopy.',
                     'Alex underwent colonoscopy.', 'Her husband underwent colonoscopy.'):
            with self.subTest(lead=lead):
                self.held(lead + ' Procedure. ' + source, 'Procedure', [source])
        self.supported('The doctor underwent colonoscopy. The patient reports rectal bleeding. '
                       'Procedure. ' + source, 'Procedure', [source])

    def test_numeric_metadata_is_distinct_from_clinical_qualifiers(self):
        source = 'Diagnostic colonoscopy.'
        self.supported('Procedure date, 09/21/2026. Procedure. ' + source, 'Procedure', [source])
        for metadata in ('Procedure cancelled.', 'Procedure possible.', 'Procedure date, tomorrow.',
                         'Her father has a procedure.'):
            with self.subTest(metadata=metadata):
                self.held(metadata + ' Procedure. ' + source, 'Procedure', [source])

    def test_medication_start_stop_replacement_and_ambiguity_are_not_nominal_values(self):
        for source in ('Warfarin was stopped.', 'Stop warfarin.', 'Start warfarin tomorrow.',
                'Unknown medication.'):
            with self.subTest(source=source):
                self.held('Procedure. ' + source, 'Procedure', [source])
        # The historical explicit-patient reader already preserves a complete
        # switch statement as source text. The concrete safety query is whether
        # its superseded drug can still appear as a current medication.
        from io import BytesIO
        from docx import Document
        from documents import word_v3
        original = Document()
        table = original.add_table(rows=2, cols=2)
        table.cell(0, 0).text = 'Current medications'
        table.cell(1, 0).text = 'Plan'
        buffer = BytesIO()
        original.save(buffer)
        self.fields = word_v3.inspect(buffer.getvalue())['fields']
        source = 'The patient takes warfarin 5 mg daily.'
        for change in ('The patient switched from warfarin to apixaban.',
                       'Warfarin was stopped.', 'Warfarin was replaced by apixaban.'):
            with self.subTest(change=change):
                self.held('Current medications. ' + source + ' ' + change, 'Current medications', [source])

    def test_garbled_extent_and_ambiguous_blood_loss_are_not_released_by_review(self):
        self.held(self.procedure['notes'], 'Extent reached', ['The scope one advanced ten o second.'])
        self.held(self.procedure['notes'], 'Estimated blood loss',
                  ['Estimated blood loss was zero milliliters.', 'Less than one milliliter.'])
