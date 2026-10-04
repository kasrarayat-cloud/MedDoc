"""Whole-source clinical disjointness; no provider/DB or inferred negative."""
import copy

from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from .test_v3_field_relations import relation_wire, relate
from .test_v3_supersession_floor import SONNET_55_DEFAULT, raw
from .test_v3_ordinary_source_scope import CASE

HISTORY = 'The headaches started two months ago and are worse in the morning.'
DENIAL = 'She denies visual changes, nausea, or weakness.'


@override_settings(**SONNET_55_DEFAULT)
class NominalDenialDisjointness(SimpleTestCase):
    def check(self, notes, picks, expected, *, fields=None, overrides=None, wire=None):
        fields = fields or CASE['fields']
        body = wire or relation_wire(notes, fields, {'v3_2': picks}, overrides=overrides)
        answer = r.validated(raw(notes, fields, body, g.SONNET_5_5))['v3_2']
        self.assertEqual(answer['status'], expected, (notes, answer))
        field = next(f for f in fields if f['key'] == 'v3_2')
        page = g.as_currently_governed(g.governance_for(notes, fields), notes, {**field, **answer})
        self.assertEqual((page['status'], page['text']), (answer['status'], answer['text']))
        if expected == 'supported':
            self.assertEqual(answer['text'], '\n'.join(picks))
            self.assertEqual([e['quote'] for e in answer['evidence']], picks)
            self.assertEqual(g.governed_decisions(notes, fields, {'v3_2': answer}), [])
        else:
            self.assertEqual(answer['text'], '')
            # A persisted stale supported copy must also fail current page,
            # review and finalization with the complete unchanged answer.
            stale = {k: v for k, v in answer.items() if k != 'held_candidate'}
            stale.update(status='supported', text='\n'.join(picks))
            self.assertIn(field['label'], g.governed_decisions(notes, fields, {'v3_2': stale}))
            page = g.as_currently_governed(g.governance_for(notes, fields), notes, {**field, **stale})
            self.assertEqual((page['status'], page['text']), ('conflict', ''))
        return answer

    def test_retained_exact_n01_complete_source_and_model_body(self):
        original = copy.deepcopy(CASE)
        answer = self.check(CASE['notes'], [HISTORY, DENIAL], 'supported', wire=CASE['model_body'])
        self.assertEqual(CASE, original)
        self.assertEqual(answer['evidence'][0]['start'], 49)
        self.assertEqual(answer['evidence'][1]['end'], 163)

    def test_named_nominal_arguments_and_conjunction_variants_remain_literal(self):
        for denial in ('She denies nausea.', 'She denies any nausea.', 'She denies weakness.',
                       'She denies visual changes.', 'She denies nausea and weakness.',
                       'She denies weakness, visual changes, or nausea.',
                       'The patient denies visual changes, nausea, or weakness.'):
            notes = CASE['notes'].replace(DENIAL, denial)
            with self.subTest(denial=denial): self.check(notes, [HISTORY, denial], 'supported')

    def test_overlapping_generic_unknown_and_possible_aliases_stay_held(self):
        for words in ('headaches, nausea, or weakness', 'any pain', 'pain, nausea, or weakness',
                      'all symptoms', 'an unknown problem', 'migraine', 'a visual symptom',
                      'headache-related weakness', 'visual disturbances'):
            denial = 'She denies '+words+'.'
            notes = CASE['notes'].replace(DENIAL, denial)
            with self.subTest(words=words): self.check(notes, [HISTORY, denial], 'conflict')
        for positive, negative in (('diarrhoea', 'diarrhea'), ('migraine', 'headaches'),
                                    ('swelling', 'effusion'), ('fever', 'temperature')):
            history = f'The {positive} started two months ago and is worse in the morning.'
            denial = f'She denies {negative}, nausea, or weakness.'
            notes = f'A 30-year-old woman presents with {positive}. {history} {denial}'
            with self.subTest(positive=positive): self.check(notes, [history, denial], 'conflict')

    def test_person_time_uncertainty_double_negation_and_embedded_events_stay_held(self):
        for denial in ('Her mother denies visual changes, nausea, or weakness.',
                       'He denies visual changes, nausea, or weakness.',
                       'The doctor denies visual changes, nausea, or weakness.',
                       'She may deny visual changes, nausea, or weakness.',
                       'She will deny visual changes, nausea, or weakness.',
                       'She denied visual changes, nausea, or weakness last year.',
                       'She denies visual changes, nausea, or weakness if she rests.',
                       'She denies not having nausea.', 'She does not deny nausea.',
                       'She denies no nausea.', 'She denies nausea for the doctor.',
                       'She denies having headaches and reports weakness.',
                       'She denies nausea but has headaches.', 'She denies this.'):
            notes = CASE['notes'].replace(DENIAL, denial)
            with self.subTest(denial=denial): self.check(notes, [HISTORY, denial], 'conflict')

    def test_source_opposition_retraction_and_clinical_association_stay_held(self):
        for extra in ('She has nausea.', 'She has weakness.', 'She has visual changes.',
                      'The headaches cause nausea.', 'The headaches are associated with weakness.',
                      'The previous symptom statement was wrong.', 'Sorry, wrong patient.',
                      'Her sister has headaches.'):
            notes = CASE['notes']+' '+extra
            with self.subTest(extra=extra): self.check(notes, [HISTORY, DENIAL], 'conflict')

    def test_missing_qualifier_and_relation_veto_still_hold(self):
        for picks, overrides in (([HISTORY], {('v3_2', DENIAL): 'qualifier'}),
                                 ([HISTORY, DENIAL], {('v3_2', DENIAL): 'contrary'}),
                                 ([HISTORY, DENIAL], {('v3_2', HISTORY): 'unresolved'})):
            with self.subTest(picks=picks, overrides=overrides):
                self.check(CASE['notes'], picks, 'conflict', overrides=overrides)

    def test_unanchored_and_foreign_source_cannot_borrow_nominal_proof(self):
        for opener in ('Her father has headaches.', 'The doctor has headaches.',
                       'Another patient has headaches.', ''):
            notes = CASE['notes'].replace('This is a 30-year-old female seen for headaches.', opener).strip()
            with self.subTest(opener=opener): self.check(notes, [HISTORY, DENIAL], 'conflict')

    def test_named_clinical_qualifiers_are_not_discarded_by_a_partial_answer(self):
        # The positive selects the complete denial, not a synthesized negative
        # or a summary that drops its visual-change/nausea/weakness content.
        body = relation_wire(CASE['notes'], CASE['fields'], {'v3_2': [HISTORY]})
        relate(body, 'v3_2', 3, 'qualifier')
        self.check(CASE['notes'], [HISTORY], 'conflict', wire=body)

    def test_omitted_denial_stays_held_even_when_model_calls_it_independent(self):
        self.check(CASE['notes'], [HISTORY], 'conflict')

    def test_omitted_history_stays_held_even_when_model_calls_it_independent(self):
        self.check(CASE['notes'], [DENIAL], 'conflict')

    def test_cached_syntax_for_another_source_cannot_supply_disjointness(self):
        from core import ordinary_source_scope as scope, v3_syntax as syntax
        reading = scope.apply(g.governance_for(CASE['notes'], CASE['fields'])[-1]['preceding'])
        denial = next(u for u in reading['units'] if u['quote'] == DENIAL)
        opener = reading['units'][0]
        history = next(u for u in reading['units'] if u['quote'] == HISTORY)
        chosen = {denial['id'], history['id']}
        self.assertTrue(scope.clinical_denial_apart(reading, denial, opener, chosen))
        for uid, stale in ((denial['id'], 'She denies headaches.'),
                           (opener['id'], 'The patient has nausea.')):
            polluted = {**reading, '_ordinary_scope_docs': dict(reading['_ordinary_scope_docs'])}
            polluted['_ordinary_scope_docs'][uid] = syntax.docs([stale])[0]
            self.assertFalse(scope.clinical_denial_apart(polluted, denial, opener, chosen))
