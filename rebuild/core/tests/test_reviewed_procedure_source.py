"""Reviewed procedure observations remain literal, attributed and retractable."""
import hashlib
import json
import copy
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from .test_v3_field_relations import relation_wire, answer_of, relate
from .test_v3_supersession_floor import SONNET_55_DEFAULT, raw
from .test_transcript_context import proof

CASE = json.loads((Path(__file__).parent/'reviewed_procedure_first_pass_control.json').read_text())
EXTENT = 'The scope was advanced to the cecum.'
FINDINGS = 'Sigmoid diverticulosis and small internal hemorrhoids.'
NO_POLYPS = 'No polyps were seen.'
RECOMMENDATION = 'Recommendation, follow-up with the referring clinician in two weeks.'


@override_settings(**SONNET_55_DEFAULT)
class ReviewedProcedureSource(SimpleTestCase):
    def check(self, notes, key, selected, expected='conflict', *, context=True, start=0, end=None, overrides=None):
        fields = CASE['fields']
        result = raw(notes, fields, relation_wire(notes, fields, {key: selected}, overrides=overrides), g.SONNET_5_5)
        if context: result['patient_default_context'] = proof(notes, start=start, end=end)
        answer = r.validated(result)[key]
        self.assertEqual(answer['status'], expected, (notes, key, answer))
        field = next(f for f in fields if f['key'] == key)
        page = g.as_currently_governed(g.governance_for(notes, fields), notes, {**field, **answer})
        self.assertEqual((page['status'], page['text']), (answer['status'], answer['text']))
        if expected == 'supported':
            self.assertEqual(answer['text'], '\n'.join(selected))
            self.assertEqual([ev['quote'] for ev in answer['evidence']], selected)
            self.assertEqual(g.governed_decisions(notes, fields, {key: answer}), [])
        else:
            self.assertEqual(answer['text'], '')

    def test_unchanged_complete_reviewed_voice_wire_and_original_first_result(self):
        notes = CASE['notes']; span = CASE['review_span']
        self.assertEqual(hashlib.sha256(notes[span['start']:span['end']].encode()).hexdigest(), span['reviewed_sha256'])
        result = raw(notes, CASE['fields'], CASE['model_body'], g.SONNET_5_5)
        result['patient_default_context'] = proof(notes, start=span['start'], end=span['end'])
        answers = r.validated(result)
        self.assertEqual({k: a['status'] for k, a in answers.items()},
            {k: 'conflict' if k == 'v3_9' else 'supported' for k in CASE['original_statuses']})
        self.assertEqual([CASE['original_statuses'][k] for k in ('v3_4', 'v3_6', 'v3_11')], ['conflict']*3)
        self.assertEqual(answers['v3_4']['text'], EXTENT)
        self.assertEqual(answers['v3_6']['text'], FINDINGS+'\n'+NO_POLYPS)
        self.assertEqual(answers['v3_11']['text'], RECOMMENDATION)
        gov = g.governance_for(notes, CASE['fields'])
        for field in CASE['fields']:
            answer = answers[field['key']]
            page = g.as_currently_governed(gov, notes, {**field, **answer})
            self.assertEqual((page['status'], page['text']), (answer['status'], answer['text']))
        self.assertEqual(g.governed_decisions(notes, CASE['fields'], answers), [])

    def test_exact_review_scope_and_complete_relation_are_required(self):
        for key, source in (('v3_4', EXTENT), ('v3_6', FINDINGS), ('v3_11', RECOMMENDATION)):
            with self.subTest(key=key):
                self.check(source, key, [source], 'supported')
                self.check(source, key, [source], context=False)
                self.check(source, key, [source], end=3)
                self.check('Her father underwent colonoscopy. '+source, key, [source])
                self.check('The doctor underwent colonoscopy. '+source, key, [source])
        notes = FINDINGS+' '+NO_POLYPS
        self.check(notes, 'v3_6', [FINDINGS, NO_POLYPS], 'supported')
        self.check(notes, 'v3_6', [FINDINGS], overrides={('v3_6', NO_POLYPS): 'qualifier'})

    def test_extent_instrument_structure_cannot_invent_subject_possessor_or_time(self):
        for source in ('The doctor was advanced to the cecum.', 'The dog was advanced to the cecum.',
                       'Her scope was advanced to the cecum.', 'That scope was advanced to the cecum.',
                       'The scope was advanced to that cecum.', 'The scope was advanced to the cecum last year.',
                       'The scope may be advanced to the cecum.', 'The scope was advanced to an unknown location.',
                       'The scope was advanced to.', 'The scope was advanced to the cecum if safe.',
                       'The scope was advanced to the cecum and the doctor took warfarin.'):
            with self.subTest(source=source): self.check(source, 'v3_4', [source])

    def test_nominal_observation_cannot_erase_actor_condition_or_source_invalidation(self):
        for source in ("Her father's sigmoid diverticulosis and small internal hemorrhoids.",
                       'Alex has sigmoid diverticulosis and small internal hemorrhoids.',
                       'Possible sigmoid diverticulosis and small internal hemorrhoids.',
                       'Sigmoid diverticulosis or small internal hemorrhoids.',
                       'Sigmoid diverticulosis and small internal hemorrhoids if bleeding worsens.'):
            with self.subTest(source=source): self.check(source, 'v3_6', [source])
        for tail in ('The earlier findings were wrong.', 'The report was entered in error.',
                     'The clinician invalidated the earlier report.', 'Do not use the earlier findings.',
                     'The earlier report cannot be relied upon.', 'Sorry, wrong patient.'):
            for key, source in (('v3_4', EXTENT), ('v3_6', FINDINGS), ('v3_11', RECOMMENDATION)):
                with self.subTest(key=key, tail=tail): self.check(source+' '+tail, key, [source])
        self.check(NO_POLYPS+' Polyps were seen.', 'v3_6', [NO_POLYPS])

    def test_own_care_caption_has_recipient_not_foreign_bearer_or_medication_transition(self):
        for source in ('Recommendation, follow-up with her father in two weeks.',
                       'Recommendation, follow-up with Alex in two weeks.',
                       'Recommendation, follow-up with my clinician in two weeks.',
                       'Recommendation, follow-up with the clinician if symptoms worsen.',
                       'Recommendation, follow-up with the clinician last year.',
                       'Recommendation, stop warfarin and take an unknown medicine.',
                       'Recommendation, follow-up with the referring clinician and the doctor takes warfarin.'):
            with self.subTest(source=source): self.check(source, 'v3_11', [source])

    def test_blood_loss_and_bare_unknown_quantity_remain_held(self):
        notes = 'Estimated blood loss was zero milliliters. Less than one milliliter.'
        # C08's retained whole wire above supplies its actual opposition. The
        # model must not omit the second amount's qualifier/contrary relation.
        # Zero and less-than-one are not a mathematical contradiction; the
        # independently marked artificial wire also supports zero on 7907.
        self.check(notes, 'v3_9', ['Estimated blood loss was zero milliliters.'],
                   overrides={('v3_9', 'Less than one milliliter.'): 'qualifier'})
        self.check('Less than one milliliter.', 'v3_9', ['Less than one milliliter.'])

    def test_original_destination_actor_time_and_wrong_field_are_not_supplied_by_review(self):
        for key, source in (('v3_4', EXTENT), ('v3_6', FINDINGS), ('v3_11', RECOMMENDATION)):
            for context in ('Family history > Mother', 'Other patient > Findings',
                            'Previous visit > Findings', 'Alex > Findings'):
                with self.subTest(key=key, context=context):
                    fields = copy.deepcopy(CASE['fields'])
                    next(f for f in fields if f['key'] == key)['context'] = context
                    result = raw(source, fields, relation_wire(source, fields, {key: [source]}), g.SONNET_5_5)
                    result['patient_default_context'] = proof(source)
                    self.assertEqual(r.validated(result)[key]['status'], 'conflict')
        self.check(FINDINGS, 'v3_2', [FINDINGS])

    def test_no_printed_context_still_requires_review_and_literal_current_source(self):
        fields = copy.deepcopy(CASE['fields'])
        for field in fields:
            field['context'] = ''
        result = raw(FINDINGS, fields, relation_wire(FINDINGS, fields, {'v3_6': [FINDINGS]}), g.SONNET_5_5)
        result['patient_default_context'] = proof(FINDINGS)
        answer = r.validated(result)['v3_6']
        self.assertEqual((answer['status'], answer['text']), ('supported', FINDINGS))
