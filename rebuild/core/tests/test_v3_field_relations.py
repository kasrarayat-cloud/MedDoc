"""Closed ordinary interpretation transport; provider decisions are simulated."""
import copy
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from .test_v3_ordinary_notes import LIVE, field


def relation_body(notes, fields, picks, *, choices=None, overrides=None):
    asked, context, _ = g.v3_generation_fields(fields)
    units = g.source_units(notes, asked, context_labels=context)[0]
    by_quote = {u['quote']: u['id'] for u in units}
    body = []
    for f in asked:
        chosen = [by_quote[q] for q in picks.get(f['key'], [])]
        body.append({'key': f['key'], 'unit_ids': chosen, 'conflict': False,
                     'option_ids': (choices or {}).get(f['key'], []),
                     'context': [(overrides or {}).get((f['key'], u['quote']),
                                 'answer' if u['id'] in chosen else 'independent') for u in units]})
    return {'fields': body}


def keyed(body, asked, units, keys=None):
    """The keyed v2 WIRE body for an internal list-shaped `body` (relation_body's): fields keyed by field key, context
    keyed by unit ID, option_ids only on option fields. `keys`: the requested subset (a batch part)."""
    by_key = {f['key']: f for f in asked}
    fields = {}
    for item in body['fields']:
        if keys is not None and item['key'] not in keys:
            continue
        entry = {'unit_ids': item['unit_ids'], 'conflict': item['conflict']}
        if r.options(by_key[item['key']]):
            entry['option_ids'] = item['option_ids']
        entry['context'] = {str(u['id']): relation for u, relation in zip(units, item['context'])}
        fields[item['key']] = entry
    return {'fields': fields}


def relation_wire(notes, fields, picks, *, choices=None, overrides=None, keys=None):
    """What a model returning these picks sends under the keyed contract (the wire; relation_body is internal)."""
    asked, context, _ = g.v3_generation_fields(fields)
    units = g.source_units(notes, asked, context_labels=context)[0]
    return keyed(relation_body(notes, fields, picks, choices=choices, overrides=overrides), asked, units, keys)


def offered(notes, fields, picks, *, choices=None, overrides=None):
    asked, context, _ = g.v3_generation_fields(fields)
    units = g.source_units(notes, asked, context_labels=context)[0]
    selections = r.FieldSelections.model_validate(relation_body(notes, fields, picks, choices=choices, overrides=overrides))
    records = r.records(notes, fields, context, units, selections, g.SONNET_5)
    answers = g.validate_selections(notes, asked, selections, context_labels=context,
        evidence_contract=g.TAB_CONTRACT, ordinary_records=records, catalogue=fields)
    return g.v3_adopted(fields, answers, notes, asked, context)


def repeated():
    first, second = field('sensation', 'Other:'), field('prodrome', 'Other:')
    first['context'] = 'Current headache > What does your headache usually feel like?'
    second['context'] = 'Current headache > Which symptoms occur before the headache begins?'
    return [first, second]


@override_settings(**dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=True))
class OrdinaryFieldRelations(SimpleTestCase):
    def assert_stored_clear(self, notes, fields, answers):
        self.assertEqual(g.governed_decisions(notes, fields, answers), [])
        governance = g.governance_for(notes, fields)
        for f in fields:
            value = answers[f['key']]
            if value['status'] != 'supported': continue
            row = g.as_currently_governed(governance, notes, {**f, **value})
            self.assertEqual((row['status'], row['text']), ('supported', value['text']))

    def test_different_complete_questions_can_own_an_ordinary_other_answer(self):
        notes = 'The patient reports that the headache usually feels like intermittent buzzing.'
        fields = repeated(); answers = offered(notes, fields, {'sensation': [notes]})
        self.assertEqual((answers['sensation']['status'], answers['sensation']['text']), ('supported', notes))
        self.assertEqual(answers['prodrome']['status'], 'missing')
        self.assert_stored_clear(notes, fields, answers)

    def test_complete_patient_copular_complements_retain_every_source_word(self):
        question = 'Please confirm that this patient is subject to Multi-Agency Public Protection Arrangements (MAPPA)'
        for notes, label in (
            ('The patient is subject to Multi-Agency Public Protection Arrangements (MAPPA).', question),
            ('The patient is not subject to Multi-Agency Public Protection Arrangements (MAPPA).', question),
            ('The patient is responsive to physiotherapy.', 'Response to physiotherapy'),
            ('The patient is not responsive to physiotherapy.', 'Response to physiotherapy'),
            ('The patient is dependent on assistance.', 'Support needs'),
        ):
            with self.subTest(notes=notes):
                fields = [field('f', label)]
                answers = offered(notes, fields, {'f': [notes]})
                self.assertEqual((answers['f']['status'], answers['f']['text']), ('supported', notes))
                self.assertEqual(answers['f']['evidence'], [{'quote': notes, 'start': 0, 'end': len(notes)}])
                self.assert_stored_clear(notes, fields, answers)

    def test_copular_allowance_cannot_invent_actor_certainty_or_a_complete_complement(self):
        fields = [field('f', 'Status under the arrangements')]
        for notes in (
            'The father is subject to the arrangements.',
            "The patient's father is subject to the arrangements.",
            'The patient advocate is subject to the arrangements.',
            'She is subject to the arrangements.',
            'The patient may be subject to the arrangements.',
            'If discharged, the patient is subject to the arrangements.',
            'The patient is apparently subject to the arrangements.',
            'The patient is possibly subject to the arrangements.',
            'The patient is subject to possible arrangements.',
            'The patient is subject to.',
            'The patient is subject to the.',
            'The patient is subject to the arrangements tomorrow.',
        ):
            with self.subTest(notes=notes):
                answer = offered(notes, fields, {'f': [notes]})['f']
                self.assertNotEqual(answer['status'], 'supported')
                self.assertEqual(answer['text'], '')

    def test_copular_source_still_requires_complete_context_and_original_contract(self):
        first = 'The patient is subject to the arrangements.'
        tail = 'The arrangements cease tomorrow.'
        fields = [field('f', 'Status under the arrangements')]
        for relation in ('contrary', 'unresolved', 'qualifier'):
            with self.subTest(relation=relation):
                answer = offered(first + ' ' + tail, fields, {'f': [first]}, overrides={('f', tail): relation})['f']
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
        answers = offered(first, fields, {'f': [first]})
        changed = {**answers['f'], 'text': 'The patient is not subject to the arrangements.'}
        self.assertEqual(g.governed_decisions(first, fields, {'f': changed}), [fields[0]['label']])
        # The kill switch: an explicit QUILLMD_V3_FIELD_RELATIONS other than '1' turns off new generations AND the stored
        # records (2026-09-30: a model-string rollback alone turns off only the first).
        with override_settings(V3_FIELD_RELATIONS=False, V3_FIELD_RELATIONS_RECORDS=False):
            self.assertEqual(g.governed_decisions(first, fields, answers), [fields[0]['label']])

    def test_direct_opposite_copular_source_cannot_be_declared_independent(self):
        first = 'The patient is subject to Multi-Agency Public Protection Arrangements (MAPPA).'
        negative = first.replace(' is ', ' is not ')
        fields = [field('f', 'Please confirm that this patient is subject to Multi-Agency Public Protection Arrangements (MAPPA)')]
        for other in (negative, negative.replace('The patient', 'This patient'), negative.replace('is not', "isn't")):
            for notes in (first + ' ' + other, other + ' ' + first):
                for picks in ([first], [other], [first, other]):
                    with self.subTest(notes=notes, picks=picks):
                        # Unselected units default to the adversarial "independent" relation.
                        answer = offered(notes, fields, {'f': picks})['f']
                        self.assertEqual((answer['status'], answer['text']), ('conflict', ''))

    def test_copular_context_keeps_standalone_polarity_and_distinct_time_or_topic(self):
        first = 'The patient is responsive to physiotherapy.'
        negative = first.replace(' is ', ' is not ')
        fields = [field('f', 'Clinical observation')]
        for notes, selected in (
            (first, first), (negative, negative),
            (first + ' The patient was not responsive to physiotherapy.', first),
            ('The patient was responsive to physiotherapy. ' + negative, negative),
            (first + ' The patient is not responsive to medication.', first),
            (first + ' The patient is not allergic to penicillin.', first),
        ):
            with self.subTest(notes=notes):
                answers = offered(notes, fields, {'f': [selected]})
                self.assertEqual((answers['f']['status'], answers['f']['text']), ('supported', selected))
                self.assert_stored_clear(notes, fields, answers)

    def assert_opposed(self, selected, other, label='Status under the arrangements', orders=None):
        """Held on generation, and a stored supported copy is held on review/save."""
        fields = [field('f', label)]
        for notes in orders or (selected + ' ' + other, other + ' ' + selected):
            with self.subTest(notes=notes):
                # Unselected units default to the adversarial "independent" relation.
                answer = offered(notes, fields, {'f': [selected]})['f']
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                start = notes.index(selected)
                stored = {k: v for k, v in answer.items() if k != 'held_candidate'}
                stored.update(status='supported', text=selected,
                              evidence=[{'quote': selected, 'start': start, 'end': start + len(selected)}])
                self.assertEqual(g.governed_decisions(notes, fields, {'f': stored}), [label])
                row = g.as_currently_governed(g.governance_for(notes, fields), notes, {**fields[0], **stored})
                self.assertEqual((row['status'], row['text']), ('conflict', ''))

    def test_direct_opposite_holds_whichever_reader_admitted_the_selected_statement(self):
        # Every reader's admission is covered: "isn't" is admitted by the sentence-syntax
        # reader, "stable" by the generic one. Negation is the parser's neg dependency
        # in every form, never a list of words.
        positive = 'The patient is subject to the arrangements.'
        for selected, other in (
                (positive, "The patient isn't subject to the arrangements."),
                ("The patient isn't subject to the arrangements.", positive),
                # Admitted only by the sentence-syntax reader (an adverb is outside
                # the copular reader's syntax), so the hold cannot live in either reader.
                ("The patient isn't currently subject to the arrangements.", positive),
                (positive, "The patient's not subject to the arrangements."),
                (positive, 'The patient is never subject to the arrangements.'),
                (positive, 'The patient is no longer subject to the arrangements.'),
                (positive, 'The patient is not currently subject to the arrangements.'),
                (positive, 'The patient is possibly not subject to the arrangements.'),
                (positive, 'The patient may not be subject to the arrangements.'),
                (positive, 'The patient has not been subject to the arrangements.'),
                ('The patient is stable.', 'The patient is not stable.'),
                ('The patient is not stable.', 'The patient is stable.')):
            self.assert_opposed(selected, other)
        # An unterminated final statement, an elliptical or telegraphic one, and
        # compatibility readings of the same words are complete opposites too.
        self.assert_opposed(positive, 'The patient is not subject to the arrangements',
                            orders=[positive + ' The patient is not subject to the arrangements'])
        for other in ('Not subject to the arrangements.', 'Patient not subject to the arrangements.',
                      'The patient not subject to the arrangements.', 'Pt is not subject to the arrangements.',
                      'She is not subject to the arrangements.', 'The client is not subject to the arrangements.',
                      'The patient is not sub\u200bject to the arrangements.',
                      'The patient is not \uff53\uff55\uff42\uff4a\uff45\uff43\uff54 to the arrangements.'):
            self.assert_opposed(positive, other)

    def test_same_topic_is_the_complete_predicate_with_its_coordinated_and_renamed_readings(self):
        full = 'The patient is subject to Multi-Agency Public Protection Arrangements (MAPPA).'
        question = 'Please confirm that this patient is subject to Multi-Agency Public Protection Arrangements (MAPPA)'
        for other in ('The patient is not subject to MAPPA.',
                      'The patient is not subject to Multi-Agency Public Protection Arrangements.',
                      'The patient is not subject to the Multi-Agency Public Protection Arrangements (MAPPA).',
                      'Subject to Multi-Agency Public Protection Arrangements (MAPPA): No.'):
            self.assert_opposed(full, other, question)
        physiotherapy = 'The patient is responsive to physiotherapy.'
        for selected, other in ((physiotherapy, 'The patient is not responsive to physiotherapy or medication.'),
                                (physiotherapy, 'The patient is neither responsive to physiotherapy nor to medication.'),
                                ('The patient is not responsive to physiotherapy.',
                                 'The patient is responsive to physiotherapy and medication.'),
                                (physiotherapy, 'The patient is not responsive to physiotherapy today.'),
                                (physiotherapy, 'The patient is not responsive enough to physiotherapy.'),
                                ('The patient is subject to the arrangements.',
                                 'The patient is not subject to arrangements.'),
                                ('The patient is not subject to the arrangements.', 'Patient subject to the arrangements.'),
                                (physiotherapy, 'The patient is calm and not responsive to physiotherapy.'),
                                (physiotherapy, 'The patient is calm and is not responsive to physiotherapy.')):
            self.assert_opposed(selected, other, 'Clinical observation')
        # Positive controls: a different complete predicate is a different topic,
        # and an agreeing restatement or a generic attributive use is not opposition.
        for selected, other, label in (
                (full, 'The patient is not subject to MAPPA level 2.', question),
                (full, 'The patient is not subject to a restriction order.', question),
                (full, 'The patient is subject to MAPPA.', question),
                (full, 'Patients subject to MAPPA are reviewed monthly.', question),
                (physiotherapy, 'The patient is responsive to physiotherapy and medication.', 'Clinical observation'),
                (physiotherapy, 'The patient is calm and responsive to physiotherapy.', 'Clinical observation'),
                (physiotherapy, 'The patient is not responsive to medication or hydrotherapy.', 'Clinical observation')):
            fields = [field('f', label)]
            for notes in (selected + ' ' + other, other + ' ' + selected):
                with self.subTest(notes=notes):
                    answers = offered(notes, fields, {'f': [selected]})
                    self.assertEqual((answers['f']['status'], answers['f']['text']), ('supported', selected))
                    self.assert_stored_clear(notes, fields, answers)

    def test_copular_complement_is_read_by_its_role_not_its_part_of_speech(self):
        # The pinned tagger reads "well" as an adverb in one sentence and an
        # adjective in the other; a nominal complement and a participle
        # coordinated into the complement are copular claims too.
        for selected, other in (('The patient is well.', 'The patient is not well.'),
                                ('The patient is not well.', 'The patient is well.'),
                                ('The patient is a smoker.', 'The patient is not a smoker.'),
                                ('The patient is not a smoker.', 'The patient is a smoker.'),
                                ('The patient is alert and oriented.', 'The patient is not oriented.')):
            self.assert_opposed(selected, other, 'Clinical observation')
        fields = [field('f', 'Clinical observation')]
        for selected, other in (('The patient is well.', 'The patient was not well.'),
                                ('The patient is a smoker.', 'Her husband is not a smoker.'),
                                ('The patient is a smoker.', 'The patient is not a drinker.'),
                                # The same noun as an ordinary argument is not a predication.
                                ('The patient is a nurse.', 'The nurse did not review the wound.'),
                                ('The patient is a smoker.', 'The patient does not live with a smoker.'),
                                ('The patient is alert and oriented.', 'The patient is not agitated.')):
            for notes in (selected + ' ' + other, other + ' ' + selected):
                with self.subTest(notes=notes):
                    answers = offered(notes, fields, {'f': [selected]})
                    self.assertEqual((answers['f']['status'], answers['f']['text']), ('supported', selected))
                    self.assert_stored_clear(notes, fields, answers)

    def test_embedded_reported_or_conditional_opposites_never_count_as_agreement(self):
        positive = 'The patient is subject to the arrangements.'
        for other in ('The patient reports that she is not subject to the arrangements.',
                      'It is not true that the patient is subject to the arrangements.',
                      'The patient denies being subject to the arrangements.',
                      'If discharged, the patient is not subject to the arrangements.',
                      'Is the patient not subject to the arrangements?',
                      'The patient is either subject to the arrangements or on licence.',
                      # Reported speech shifts tense: an embedded past is not a proven other time.
                      'The patient said that she was not subject to the arrangements.',
                      'The officer reported that the patient was not subject to the arrangements.'):
            self.assert_opposed(positive, other)

    def test_opposite_actor_and_time_bounds_keep_ordinary_answers_useful(self):
        allergy = 'The patient is not allergic to penicillin.'
        # Another actor is only an explicit possessed nominal; the same complete
        # predicate for an unresolved actor (possibly the patient) still holds.
        for other in ('Her mother is allergic to penicillin.', "The patient's father is allergic to penicillin.",
                      'The patient was allergic to penicillin.'):
            for notes in (allergy + ' ' + other, other + ' ' + allergy):
                with self.subTest(notes=notes):
                    answers = offered(notes, [field('f', 'Allergies')], {'f': [allergy]})
                    self.assertEqual((answers['f']['status'], answers['f']['text']), ('supported', allergy))
                    self.assert_stored_clear(notes, [field('f', 'Allergies')], answers)
        for other in ('Mother is allergic to penicillin.', 'He is allergic to penicillin.',
                      'The patient and her mother are allergic to penicillin.',
                      'Mr Smith is allergic to penicillin.'):
            self.assert_opposed(allergy, other, 'Allergies')

    def test_opposite_reader_fails_closed_beyond_its_bounds_or_on_parser_error(self):
        from core import v3_literal_facts as literal
        positive = 'The patient is subject to the arrangements.'
        fields = [field('f', 'Status under the arrangements')]
        # More same-word statements than the bounded reader parses, or one too long.
        many = ' '.join(f'The arrangements subject note {i} is filed.' for i in range(65))
        long = 'The patient is subject to the arrangements ' + 'and review ' * 120 + 'today.'
        for notes in (positive + ' ' + many, positive + ' ' + long):
            with self.subTest(notes=notes[:80]):
                self.assertEqual(offered(notes, fields, {'f': [positive]})['f']['status'], 'conflict')
        control = positive + ' ' + ' '.join(f'The review note {i} is filed.' for i in range(65))
        self.assertEqual(offered(control, fields, {'f': [positive]})['f']['status'], 'supported')
        reading = {'units': [{'id': 1, 'quote': positive, 'start': 0, 'end': len(positive)}]}

        class Broken:
            def pipe(self, texts, batch_size=16):
                raise RuntimeError('parser failure')
        with patch.object(literal.syntax, '_parser', return_value=Broken()):
            self.assertEqual(literal.opposed_ids(reading['units'], reading), {1})

    def assert_useful(self, selected, other, label):
        """Kept on generation and on review/save, in both source orders."""
        fields = [field('f', label)]
        for notes in (selected + ' ' + other, other + ' ' + selected):
            with self.subTest(notes=notes):
                answers = offered(notes, fields, {'f': [selected]})
                self.assertEqual((answers['f']['status'], answers['f']['text']), ('supported', selected))
                self.assert_stored_clear(notes, fields, answers)

    MAPPA = 'Please confirm that this patient is subject to Multi-Agency Public Protection Arrangements (MAPPA)'
    FULL = 'The patient is subject to Multi-Agency Public Protection Arrangements (MAPPA).'

    def test_a_labelled_or_dashed_answer_is_never_part_of_the_topic(self):
        # CL-1/F1: the answer word after a label colon or a spaced dash, and a label
        # naming only the object, are an unread answer about the same predicate.
        for other in ('Subject to MAPPA: no.', 'Subject to MAPPA: No.', 'Subject to the arrangements: No.',
                      'Patient subject to MAPPA: no.', 'MAPPA subject: no.', 'Subject to MAPPA - no.',
                      'Subject to MAPPA - No.', 'MAPPA: No.'):
            self.assert_opposed(self.FULL, other, self.MAPPA)
        self.assert_opposed('The patient is allergic to penicillin.', 'Allergic to penicillin: no.', 'Allergies')

    def test_a_question_or_a_negative_inversion_is_never_agreement(self):
        # CL-2: the pinned tagger reads the inverted predicate as a noun subject.
        for other in ('Is the patient subject to MAPPA? No.', 'Is she subject to MAPPA? No.',
                      'Is the patient currently subject to MAPPA? No.',
                      'Is the patient subject to MAPPA? Not applicable.'):
            self.assert_opposed(self.FULL, other, self.MAPPA)
        self.assert_opposed('The patient is subject to the arrangements.',
                            'Nor is the patient subject to the arrangements.')

    def test_a_first_or_second_person_possessor_may_be_the_patient(self):
        # CL-3: "our service user", "my client" name the clinician's own patient.
        for other in ('Our service user is not subject to MAPPA.', 'Our client is not subject to MAPPA.',
                      'My client is not subject to MAPPA.'):
            self.assert_opposed(self.FULL, other, self.MAPPA)

    def test_an_adjunct_quantifier_modifier_or_acronym_is_not_a_different_topic(self):
        # CL-4: a prepositional phrase the other statement lacks is a qualifier, not a topic.
        for other in ('The patient is not subject to MAPPA at present.', 'The patient is not subject to MAPPA at this time.',
                      'The patient is not subject to MAPPA as of this week.',
                      'The patient is not subject to MAPPA since her discharge.',
                      'The patient is not subject to MAPPA in the community.',
                      'The patient is not subject to MAPPA per the probation officer.',
                      'The patient is not subject to MAPPA arrangements.',
                      'The patient is not subject to any MAPPA arrangements.'):
            self.assert_opposed(self.FULL, other, self.MAPPA)
        # An acronym names its full name without any apposition in the note.
        self.assert_opposed('The patient is subject to Multi-Agency Public Protection Arrangements.',
                            'The patient is not subject to MAPPA.', self.MAPPA)
        # A more specific positive entails the general one it opposes.
        self.assert_opposed('The patient is not subject to MAPPA.', 'The patient is subject to MAPPA level 2.', self.MAPPA)

    def test_a_universal_negative_opposes_any_positive_instance(self):
        # CL-5, in both selection directions.
        self.assert_opposed('The patient is allergic to penicillin.', 'The patient is not allergic to any medication.', 'Allergies')
        self.assert_opposed('The patient is not allergic to any medication.', 'The patient is allergic to penicillin.', 'Allergies')
        self.assert_opposed('The patient is allergic to penicillin.', 'The patient is not allergic to anything.', 'Allergies')

    def test_a_past_statement_with_a_time_adjunct_or_an_elided_present_negation_is_not_another_time(self):
        # CL-6: only a bare simple tense proves a different time.
        for other in ('Today the patient was not subject to MAPPA.',
                      "The patient was not subject to MAPPA at today's review.",
                      'The patient was previously subject to MAPPA but is not now.'):
            self.assert_opposed(self.FULL, other, self.MAPPA)

    def test_a_negative_determiner_or_negative_adverbial_phrase_is_not_agreement(self):
        # CL-7/F2: negation outside the neg dependency.
        positive = 'The patient is subject to the arrangements.'
        for other in ('The patient is subject to no arrangements.',
                      'The patient is in no way subject to the arrangements.'):
            self.assert_opposed(positive, other)
        self.assert_opposed(self.FULL, 'The patient is subject to no MAPPA arrangements.', self.MAPPA)

    def test_a_prefixed_form_of_the_same_predicate_word_is_a_direct_opposite(self):
        # CL-8/F2: withheld on the structural relation only; nothing is adopted from it.
        for selected, other, label in (
                ('The patient is allergic to penicillin.', 'The patient is non-allergic to penicillin.', 'Allergies'),
                ('The patient is allergic to penicillin.', 'The patient is nonallergic to penicillin.', 'Allergies'),
                ('The patient is responsive to physiotherapy.', 'The patient is non-responsive to physiotherapy.',
                 'Clinical observation'),
                ('The patient is stable.', 'The patient is unstable.', 'Clinical observation'),
                ('The patient is unstable.', 'The patient is stable.', 'Clinical observation'),
                ('The patient is conscious.', 'The patient is unconscious.', 'Clinical observation'),
                ('The patient is responsive.', 'The patient is unresponsive.', 'Clinical observation'),
                ('The patient is a smoker.', 'The patient is a non-smoker.', 'Clinical observation'),
                ('The patient is a smoker.', 'The patient is a nonsmoker.', 'Clinical observation'),
                ('The patient is compliant with medication.', 'The patient is non-compliant with medication.',
                 'Clinical observation')):
            self.assert_opposed(selected, other, label)

    def test_an_unavailable_parser_or_an_overlong_selected_statement_withholds(self):
        from core import v3_literal_facts as literal
        # CL-9: another reader still admits the statement, so the hold must not fail open.
        with patch.object(literal.syntax, '_parser', return_value=None):
            for selected, other in (('The patient is stable.', 'The patient is not stable.'),
                                    ('The patient is not stable.', 'The patient is stable.')):
                notes = selected + ' ' + other
                with self.subTest(notes=notes):
                    answer = offered(notes, [field('f', 'Clinical observation')], {'f': [selected]})['f']
                    self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
        # CL-10: an over-long selected unit is withheld as an over-long other unit is.
        for count in (80, 120):
            selected = 'The patient is stable, ' + 'comfortable, ' * count + 'and calm.'
            self.assertGreater(len(selected), literal.syntax.MAX_CHARACTERS)
            answer = offered(selected + ' The patient is not stable.', [field('f', 'Clinical observation')],
                             {'f': [selected]})['f']
            self.assertEqual((answer['status'], answer['text']), ('conflict', ''))

    def test_attributive_adverbial_and_different_site_uses_keep_ordinary_answers_useful(self):
        # FH-1: a restrictor of a plural class and another person's possessed noun are
        # no claim about the patient. (An attributive use of the same word otherwise
        # withholds, whichever way its verb reads it: see R2-1 below.)
        self.assert_useful('The patient is not subject to MAPPA.', 'Patients subject to MAPPA are reviewed monthly.', self.MAPPA)
        self.assert_useful('The patient is not suicidal.', "Her mother's suicidal ideation was discussed.", 'Risk assessment')
        # FH-2: an adverb of another verb with the same polarity, or a noun modifier, is no opposite.
        for other in ('Blood glucose is well controlled.', 'The wound is well healed.', 'She is eating and drinking well.',
                      'She tolerated the procedure well.', 'The patient is well known to the service.',
                      'Her pain is well managed.', 'The patient is eating and drinking well.'):
            self.assert_useful('The patient is well.', other, 'Clinical observation')
        self.assert_useful('The patient is a smoker.', 'Smoker status was reviewed.', 'Smoking status')
        # FH-3: the same preposition with a different object is a different site,
        # whether the parser attaches it to the adjective or to the copula.
        for selected, other in (('The patient is tender over the lateral epicondyle.',
                                 'She is not tender over the medial epicondyle.'),
                                ('The patient is not tender over the medial epicondyle.',
                                 'She is tender over the lateral epicondyle.'),
                                ('The patient is tender over the lateral joint line.',
                                 'She is not tender over the medial joint line.'),
                                ('The patient is tender over the anterior talofibular ligament.',
                                 'She is not tender over the deltoid ligament.')):
            self.assert_useful(selected, other, 'Examination findings')

    def test_further_spellings_of_the_same_opposites_found_against_this_repair(self):
        # Answers after an unspaced dash, a semicolon or a comma, or in the next unit;
        # a question naming the object; a singular/plural object; a neither/nor subject;
        # and a predicate the tagger reads as a passive participle ("is oriented").
        for other in ('Subject to MAPPA—no.', 'Subject to MAPPA; no.', 'Subject to MAPPA, no.',
                      'Subject to MAPPA. No.', 'MAPPA. No.', 'MAPPA? No.', 'Is the patient on MAPPA? No.',
                      'The patient is not subject to MAPPA arrangement.',
                      # a telegraphic question, and the predicate read as a noun subject
                      # that carries its own complement
                      'Patient subject to MAPPA?', 'Patient subject to MAPPA review was declined.'):
            self.assert_opposed(self.FULL, other, self.MAPPA)
        self.assert_opposed('The patient is allergic to penicillin.', 'The patient is not allergic to penicillins.', 'Allergies')
        self.assert_opposed('The patient is a smoker.', 'Neither the patient nor her husband are smokers.', 'Smoking status')
        for selected, other in (('The patient is oriented.', 'The patient is not oriented.'),
                                ('The patient is oriented.', 'The patient is disoriented.'),
                                ('The patient is not oriented.', 'The patient is oriented to person.')):
            self.assert_opposed(selected, other, 'Mental state')
        self.assert_opposed('The patient is registered with a GP.', 'The patient is not registered with a GP.', 'Registration')
        # A negative inversion that is not a question; the full name opposing a selected
        # acronym; and an answer the parser reads as the object ("MAPPA - no") against a
        # more specific selected statement.
        self.assert_opposed('The patient is subject to the arrangements.', 'Nor is she subject to the arrangements.')
        self.assert_opposed('The patient is subject to MAPPA.',
                            'The patient is not subject to Multi-Agency Public Protection Arrangements.', self.MAPPA)
        for other in ('Subject to MAPPA - no.', 'Patient subject to MAPPA: no.'):
            self.assert_opposed('The patient is subject to MAPPA level 2.', other, self.MAPPA)
        # Positive controls: a label or a negative that adds its own words, a bare past,
        # and a different object stay useful.
        for other in ('MAPPA level: 2.', 'The patient is not subject to MAPPA level 3.',
                      'Her partner is not subject to MAPPA.', 'The patient was not subject to MAPPA.'):
            self.assert_useful(self.FULL, other, self.MAPPA)
        self.assert_useful('The patient is not subject to Multi-Agency Public Protection Arrangements (MAPPA).',
                           'The patient was subject to MAPPA.', self.MAPPA)
        self.assert_useful('The patient is oriented.', 'The patient was not oriented.', 'Mental state')
        self.assert_useful('The patient is registered with a GP.', 'The patient is not registered with a dentist.', 'Registration')
        self.assert_useful('The patient is allergic to penicillin.', 'The patient is not allergic to latex.', 'Allergies')
        # A qualifier both state is compared, never dropped: another side is another site.
        self.assert_useful('The patient is tender over the medial aspect of the left knee.',
                           'She is not tender over the medial aspect of the right knee.', 'Examination findings')

    RISK = 'Risk to self'

    def test_an_attributive_use_whose_polarity_the_syntax_does_not_fix_withholds(self):
        # R2-1: an adjective modifying another noun ("suicidal ideation") states the
        # property of that noun, at a polarity only the governing verb's meaning fixes
        # ("reports" or "denies"); it is never read as no claim at all.
        for selected, other in (('The patient is not suicidal.', 'She reports suicidal ideation with a plan.'),
                                ('The patient is not suicidal.', 'Active suicidal ideation is present.'),
                                ('The patient is not suicidal.', 'She has suicidal thoughts.'),
                                ('The patient is not suicidal.', 'The patient has suicidal intent.'),
                                ('The patient is not suicidal.', 'She expressed suicidal intent today.'),
                                ('The patient is not psychotic.', 'Psychotic symptoms were elicited.'),
                                ('The patient is not depressed.', 'Depressed mood was observed.'),
                                ('The patient is not febrile.', 'A febrile episode occurred this morning.'),
                                ('The patient is not homeless.', 'She sleeps rough as a homeless person.')):
            self.assert_opposed(selected, other, self.RISK)
        # The same syntax with an agreeing verb is no different to the reader: "denies",
        # "not observed", a negative determiner or a classifying use ("outreach team")
        # would each need a word's meaning to agree, and no word list decides that.
        # These were useful at 050fa1da (FH-1) and are held again, as at c8f22ac6.
        for selected, other in (('The patient is not suicidal.', 'She denies suicidal ideation.'),
                                ('The patient is not suicidal.', 'No suicidal ideation was reported.'),
                                ('The patient is not suicidal.', 'She has no suicidal thoughts.'),
                                ('The patient is not psychotic.', 'No psychotic symptoms were elicited.'),
                                ('The patient is not depressed.', 'Depressed mood was not observed.'),
                                ('The patient is not homeless.', 'The homeless outreach team closed his case.'),
                                ('The patient is not febrile.', 'A febrile illness last month was treated by the GP.'),
                                ('The patient is not violent.', 'He has a history of violent offending.'),
                                ('The patient is not diabetic.', 'Diabetic eye screening letters were sent in error.'),
                                ('The patient is suicidal.', 'No suicidal ideation was reported.'),
                                ('The patient is not suicidal.', 'Her suicidal ideation persists.'),
                                # an adjective modifier of a nominal predicate's word, and a noun
                                # modifier of an adjectival one (the role decides, not the tag)
                                ('The patient is not a diabetic.', 'Diabetic retinopathy was found.'),
                                ('The patient is not tender over the knee.', 'Tender points were examined over the knee.')):
            self.assert_opposed(selected, other, self.RISK)

    def test_a_prepositional_copular_predicate_is_a_claim(self):
        # R2-2: "is on MAPPA" / "is not on MAPPA" is the same copular claim with a
        # prepositional predicate, whichever statement is selected.
        for selected, other in (('The patient is on MAPPA.', 'The patient is not on MAPPA.'),
                                ('The patient is not on MAPPA.', 'The patient is on MAPPA.'),
                                ('The patient is on a community treatment order.',
                                 'The patient is not on a community treatment order.'),
                                ('The patient is on the child protection register.',
                                 'The patient is not on the child protection register.'),
                                ('The patient is at risk of falls.', 'The patient is not at risk of falls.'),
                                ('The patient is under the care of the community team.',
                                 'The patient is not under the care of the community team.'),
                                ('The patient is on methadone.', 'The patient is not on methadone.')):
            self.assert_opposed(selected, other, self.MAPPA)
        # Telegraphic, contracted, adverbial, labelled and more specific spellings of it.
        for selected, other in (('The patient is on methadone.', 'Patient not on methadone.'),
                                ('The patient is on methadone.', "The patient isn't on methadone."),
                                ('The patient is on MAPPA.', 'The patient is no longer on MAPPA.'),
                                ('The patient is on MAPPA.', 'On MAPPA: no.'),
                                ('The patient is on MAPPA.', 'The patient is not on MAPPA at present.'),
                                ('The patient is not on methadone.', 'The patient is on methadone treatment.'),
                                ('The patient is not on the child protection register.',
                                 'The patient is on the CP register.'),
                                # subject and copula omitted, and a coordinated preposition
                                ('The patient is on methadone.', 'Not on methadone.'),
                                ('The patient is on methadone.', 'No longer on methadone.'),
                                ('The patient is on MAPPA.', 'The patient is not on a curfew or on MAPPA.')):
            self.assert_opposed(selected, other, self.MAPPA)
        # Positive controls: another object or preposition, an ordinary argument or a
        # classifying noun, a bare past and an agreeing coordination stay useful. A
        # preposition beside another complement is that complement's part ("tender
        # over the lateral epicondyle", above), not a predicate.
        for other in ('The patient is not on diazepam.', 'Methadone was collected from the pharmacy.',
                      'Methadone dose was reviewed.', 'The patient was not on methadone.',
                      'The patient is not off methadone.', 'The patient is on methadone and diazepam.',
                      'Methadone 60 ml daily.'):
            self.assert_useful('The patient is on methadone.', other, self.MAPPA)
        for other in ('The patient is not at risk of self-harm.', 'Risk of falls was discussed at the meeting.'):
            self.assert_useful('The patient is at risk of falls.', other, self.MAPPA)

    def test_a_one_word_answer_in_the_next_unit_is_an_answer_whatever_its_tag(self):
        # R2-3: the tagger reads "None." as a noun and "Denied." as a verb, not an interjection.
        for answer in ('None.', 'Negative.', 'Nil.', 'Not applicable.', 'Denied.'):
            self.assert_opposed(self.FULL, 'Subject to MAPPA. ' + answer, self.MAPPA)
        # "A. The patient ..." is read as one unit, so only the refuter's order applies.
        self.assert_opposed(self.FULL, 'Subject to MAPPA. N/A.', self.MAPPA,
                            orders=[self.FULL + ' Subject to MAPPA. N/A.'])
        for answer in ('Yes.', '0.'):
            self.assert_opposed(self.FULL, 'Subject to MAPPA. ' + answer, self.MAPPA)
        # A following unit too long to read may be the answer too.
        long = 'The patient attends the clinic and ' * 30 + 'is well.'
        self.assertGreater(len(long), 1000)
        self.assert_opposed(self.FULL, 'Subject to MAPPA. ' + long, self.MAPPA,
                            orders=[self.FULL + ' Subject to MAPPA. ' + long])
        # A telegraphic agreeing statement, alone or before a clause with a subject or
        # a finite verb of its own, is no prompt.
        for other in ('Subject to MAPPA.', 'Subject to MAPPA. The patient attends monthly reviews.',
                      'Subject to MAPPA. Attends monthly reviews.', 'Subject to MAPPA. Officer to attend reviews.'):
            self.assert_useful(self.FULL, other, self.MAPPA)

    def test_a_time_phrase_nested_in_the_predicate_is_not_a_bare_past(self):
        # R2-4: the parser hangs the time phrase inside the complement's own phrase.
        for other in ('The patient was not subject to MAPPA as of this week.',
                      "The patient was not subject to MAPPA or to a curfew at today's review."):
            self.assert_opposed(self.FULL, other, self.MAPPA)
        self.assert_opposed('The patient is not agitated.', 'The patient was agitated and aggressive on the ward today.',
                            'Mental state')
        # An adverbial anywhere in the past clause, a subordinate clause included.
        for other in ('The patient was subject to MAPPA today.', 'The patient was subject to MAPPA when she was discharged.'):
            self.assert_opposed('The patient is not subject to MAPPA.', other, self.MAPPA)
        self.assert_opposed(self.FULL, 'The patient was not subject to MAPPA, having been discharged.', self.MAPPA)
        # An elided present clause ("but is not") is no bare past either.
        self.assert_opposed(self.FULL, 'The patient was subject to MAPPA but is not.', self.MAPPA)

    def test_a_prefix_written_with_a_space_or_any_dash_is_a_prefixed_form(self):
        # R2-5: "non smoker", "non\u2013smoker" and "non\u2212compliant" are the prefixed words of CL-8.
        for selected, other, label in (
                ('The patient is allergic to penicillin.', 'The patient is non allergic to penicillin.', 'Allergies'),
                ('The patient is a smoker.', 'The patient is a non smoker.', 'Smoking status'),
                ('The patient is a smoker.', 'Non smoker.', 'Smoking status'),
                ('The patient is a smoker.', 'The patient is a non\u2013smoker.', 'Smoking status'),
                ('The patient is tender over the left knee.', 'The patient is non tender over the left knee.',
                 'Examination findings'),
                ('The patient is compliant with medication.', 'The patient is non compliant with medication.',
                 'Clinical observation'),
                ('The patient is compliant with medication.', 'The patient is non\u2212compliant with medication.',
                 'Clinical observation'),
                ('The patient is a smoker.', 'The patient is an ex smoker.', 'Smoking status'),
                ('The patient is conscious.', 'The patient is semi conscious.', 'Clinical observation'),
                ('The patient is allergic to penicillin.', 'Non allergic to penicillin.', 'Allergies'),
                ('The patient is a smoker.', 'The patient is a non \u2013 smoker.', 'Smoking status'),
                # the parser leaves "non" unlinked: only the written word joins them
                ('The patient is allergic to penicillin.', 'The patient is non\u2013allergic to penicillin.', 'Allergies')):
            self.assert_opposed(selected, other, label)
        # An adverb of the copula, or a longer word before the predicate, is no prefix.
        for selected, other, label in (
                ('The patient is allergic to penicillin.', 'The patient is also allergic to latex.', 'Allergies'),
                ('The patient is a smoker.', 'The patient is a cigarette smoker.', 'Smoking status'),
                ('The patient is stable.', 'She is now stable.', 'Clinical observation')):
            self.assert_useful(selected, other, label)
        # Every dash that may join a word: Unicode's Pd category and the minus sign.
        import unicodedata
        from core import v3_literal_facts as literal
        self.assertEqual(set(literal._DASHES), {chr(c) for c in range(0x110000)
                                                if unicodedata.category(chr(c)) == 'Pd'} | {'\u2212'})

    def test_an_acronym_followed_by_the_word_it_ends_with_is_the_acronym(self):
        # R2-6: "MAPPA arrangements" restates the final word MAPPA stands for.
        self.assert_opposed('The patient is subject to MAPPA.', 'The patient is not subject to MAPPA arrangements.',
                            self.MAPPA)
        self.assert_opposed('The patient is not subject to MAPPA arrangements.', 'The patient is subject to MAPPA.',
                            self.MAPPA)
        # A word the acronym does not end with, or one after a word that is no acronym,
        # stays another topic.
        self.assert_useful('The patient is subject to MAPPA.', 'The patient is not subject to MAPPA level 3.', self.MAPPA)
        self.assert_useful('The patient is subject to the order.', 'The patient is not subject to the order restrictions.',
                           'Status under the order')

    def test_a_label_naming_the_topic_with_an_unread_answer_withholds(self):
        # R2-7: a label word that names no value of its own ("status") does not make
        # the answer after it another topic.
        for other in ('MAPPA status: none.', 'MAPPA status: not applicable.'):
            self.assert_opposed(self.FULL, other, self.MAPPA)
        # Only a plain nonzero number is read as a value after such a label: a name
        # or any word may carry the polarity ("Nil", "Case Closed"), so it withholds.
        for other in ('MAPPA coordinator: Jane Smith.', 'MAPPA coordinator: none.', 'MAPPA level: 0.',
                      'MAPPA status: none now.'):
            self.assert_opposed(self.FULL, other, self.MAPPA)
        # The acronym the predicate's own words spell names it too.
        for other in ('MAPPA status: none.', 'MAPPA: No.'):
            self.assert_opposed('The patient is subject to Multi-Agency Public Protection Arrangements.', other,
                                self.MAPPA)
        for other in ('MAPPA level: 2.', 'Child protection plan: none.'):
            self.assert_useful(self.FULL, other, self.MAPPA)
        self.assert_useful('The patient is subject to Multi-Agency Public Protection Arrangements.',
                           'MAPPA level: 2.', self.MAPPA)

    def test_an_adverb_of_another_predicate_is_not_a_prefixed_form(self):
        # R2-8: "less" in "less severe" qualifies "severe"; it is no reading of "homeless".
        self.assert_useful('The patient is homeless.', 'Pain is less severe today.', 'Social circumstances')

    def test_each_guard_of_the_opposite_reader_is_pinned(self):
        # R2-9: each of these survived as a mutant of the reader's guards.
        self.assert_opposed(self.FULL, 'The patient was no longer subject to MAPPA.', self.MAPPA)
        self.assert_opposed('The patient is conscious.', 'The patient is semiconscious.', 'Clinical observation')
        self.assert_opposed(self.FULL, 'Subject to MAPPA. Nope.', self.MAPPA)
        self.assert_opposed('The patient is not aggressive.', 'The patient is an aggressive man.', 'Mental state')
        self.assert_opposed('The patient is not suicidal.', 'The suicidal patient was admitted overnight.', self.RISK)

    def test_identical_contexts_and_ambiguous_labelled_answers_stay_held(self):
        notes = 'The patient reports intermittent buzzing.'
        fields = repeated(); fields[1]['context'] = fields[0]['context']
        self.assertEqual(offered(notes, fields, {'sensation': [notes]})['sensation']['status'], 'conflict')
        notes = 'The patient reports intermittent buzzing.'
        answers = offered(notes, repeated(), {'sensation': [notes], 'prodrome': [notes]})
        self.assertEqual({a['status'] for a in answers.values()}, {'conflict'})
        fields = repeated(); notes = 'Other: buzzing.'
        self.assertEqual(offered(notes, fields, {'sensation': [notes]})['sensation']['status'], 'conflict')

    def test_explicit_same_side_is_useful_and_opposite_unknown_or_mixed_sides_hold(self):
        fields = [field('site', 'Right knee')]
        notes = 'The patient has right knee pain.'
        answer = offered(notes, fields, {'site': [notes]})
        self.assertEqual((answer['site']['status'], answer['site']['text']), ('supported', notes))
        self.assert_stored_clear(notes, fields, answer)
        for notes in ('The patient has left knee pain.', 'The patient has knee pain.',
                      'The patient has right and left knee pain.'):
            with self.subTest(notes=notes):
                self.assertEqual(offered(notes, fields, {'site': [notes]})['site']['status'], 'conflict')

    def test_ordinary_predicate_selects_the_original_option_and_keeps_full_evidence(self):
        notes = 'The patient does not smoke.'
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No'])]
        answers = offered(notes, fields, {'smoking': [notes]}, choices={'smoking': ['smoking:1']})
        self.assertEqual((answers['smoking']['status'], answers['smoking']['text']), ('supported', 'No'))
        self.assertEqual(answers['smoking']['evidence'], [{'quote': notes, 'start': 0, 'end': len(notes)}])
        self.assert_stored_clear(notes, fields, answers)

    def test_wrong_binary_polarity_and_an_omitted_opposite_predicate_cannot_be_model_permissions(self):
        for label, yes, no in (('Smoker', 'The patient smokes.', 'The patient does not smoke.'),
                               ('Pain', 'The patient has pain.', 'The patient has no pain.'),
                               ('Do you smoke?', 'The patient smokes.', 'The patient does not smoke.')):
            fields = [field('predicate', label, 'choice', ['Yes', 'No'])]
            for notes, option, status in ((yes, 'predicate:0', 'supported'), (no, 'predicate:1', 'supported'),
                                          (yes, 'predicate:1', 'conflict'), (no, 'predicate:0', 'conflict')):
                with self.subTest(label=label, notes=notes, option=option):
                    answer = offered(notes, fields, {'predicate': [notes]}, choices={'predicate': [option]})
                    self.assertEqual(answer['predicate']['status'], status)
                    if status == 'supported': self.assert_stored_clear(notes, fields, answer)
            note = no + ' ' + yes
            self.assertEqual(offered(note, fields, {'predicate': [no]},
                choices={'predicate': ['predicate:1']})['predicate']['status'], 'conflict')
            old = {'status': 'supported', 'text': 'Yes', 'evidence': [{'quote': no, 'start': 0, 'end': len(no)}]}
            self.assertEqual(g.governed_decisions(no, fields, {'predicate': old}), [label])
        fields = [field('predicate', 'Smoker', 'choice', ['Yes', 'No'])]
        for notes in ('The patient does not smoke daily.', 'The patient does not drink.',
                      'The patient formerly smoked.', 'The patient is not a nonsmoker.'):
            self.assertEqual(offered(notes, fields, {'predicate': [notes]},
                choices={'predicate': ['predicate:1']})['predicate']['status'], 'conflict')

    def test_event_relative_destination_requires_explicit_matching_source_scope(self):
        fields = repeated()
        current = 'The patient reports that the headache usually feels like intermittent buzzing.'
        before = 'The patient reports intermittent buzzing before the headache begins.'
        after = 'The patient reports intermittent buzzing after the headache begins.'
        for notes, key, status in ((current, 'sensation', 'supported'), (current, 'prodrome', 'conflict'),
                                   (before, 'prodrome', 'supported'), (after, 'prodrome', 'conflict')):
            with self.subTest(notes=notes, key=key):
                answers = offered(notes, fields, {key: [notes]})
                self.assertEqual(answers[key]['status'], status)
                if status == 'supported': self.assert_stored_clear(notes, fields, answers)
        target = field('symptoms', 'Symptoms before treatment')
        for notes, status in (('The patient reports nausea before treatment.', 'supported'),
                              ('The patient reports nausea after treatment.', 'conflict'),
                              ('The patient reports nausea.', 'conflict')):
            self.assertEqual(offered(notes, [target], {'symptoms': [notes]})['symptoms']['status'], status)
        first = 'The patient reports nausea before treatment.'
        for second in ('The patient reports chest pain today.', 'The patient reports dizziness after surgery.'):
            notes = first + ' ' + second
            self.assertEqual(offered(notes, [target], {'symptoms': [first, second]})['symptoms']['status'], 'conflict')
        second = 'The patient reports dizziness before treatment.'
        self.assertEqual(offered(first + ' ' + second, [target], {'symptoms': [first, second]})['symptoms']['status'], 'supported')

    def test_affirmative_checkbox_cannot_discard_an_explicit_negative(self):
        for label, notes in (('Consent obtained', 'The patient did not consent to the procedure.'),
                             ('Diabetes', 'The patient has no diabetes.'),
                             ('Smoker', 'The patient does not smoke.')):
            fields = [field('f', label, 'checkbox', [label])]
            with self.subTest(label=label):
                self.assertEqual(offered(notes, fields, {'f': [notes]}, choices={'f': ['f:0']})['f']['status'], 'conflict')
                old = {'status': 'supported', 'text': 'checked', 'evidence': [{'quote': notes, 'start': 0, 'end': len(notes)}]}
                self.assertEqual(g.governed_decisions(notes, fields, {'f': old}), [label])
        for label, notes in (('Diabetes', 'The patient has diabetes.'), ('Smoker', 'The patient smokes.'),
                             ('Consent obtained', 'Consent obtained: yes.')):
            fields = [field('f', label, 'checkbox', [label])]
            answers = offered(notes, fields, {'f': [notes]}, choices={'f': ['f:0']})
            self.assertEqual((answers['f']['status'], answers['f']['text']), ('supported', 'checked'))
            self.assert_stored_clear(notes, fields, answers)

    def test_qualifier_cannot_disappear_into_a_fixed_option(self):
        first, last = 'The patient does not smoke.', 'The patient stopped yesterday.'
        notes = first + ' ' + last
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No'])]
        answers = offered(notes, fields, {'smoking': [first, last]}, choices={'smoking': ['smoking:1']},
                          overrides={('smoking', last): 'qualifier'})
        self.assertEqual(answers['smoking']['status'], 'conflict')

    def test_duplicate_printed_options_and_reordered_identical_occurrences(self):
        notes = 'The patient does not smoke.'
        fields = [field('smoking', 'Smoker', 'choice', ['No', 'No.'])]
        self.assertEqual(offered(notes, fields, {'smoking': [notes]},
            choices={'smoking': ['smoking:0']})['smoking']['status'], 'conflict')
        quote = 'The patient reports persistent aching.'; notes = quote + ' ' + quote
        fields = [field('hpi', 'History of present illness')]
        units = g.source_units(notes, fields)[0]
        selections = r.FieldSelections(fields=[r.FieldSelection(key='hpi', unit_ids=[2, 1], conflict=False,
            option_ids=[], context=['answer', 'answer'])])
        records = r.records(notes, fields, [], units, selections, g.SONNET_5)
        answers = g.validate_selections(notes, fields, selections, evidence_contract=g.TAB_CONTRACT,
            ordinary_records=records, catalogue=fields)
        answers = g.v3_adopted(fields, answers, notes, fields)
        self.assertEqual((answers['hpi']['status'], answers['hpi']['text']), ('supported', quote + '\n' + quote))
        self.assertEqual([e['start'] for e in answers['hpi']['evidence']], [0, len(quote) + 1])

    def test_source_printed_patient_authorship_and_review_attestation_have_literal_prerequisites(self):
        source = {'part': 'word/document.xml', 'slot': 'b/p[0]', 'fingerprint': 'a' * 64, 'text': 'For the patient:'}
        target = field('comments', 'Additional comments')
        target['answer_policy'] = {'source_author': 'patient', 'source': source}
        for notes, expected in (('The patient reports feeling adequately supported.', 'supported'),
                                ('The patient is clinically stable.', 'conflict'),
                                ('The patient had the procedure.', 'conflict'),
                                ('The clinician reports that the patient is stable.', 'conflict')):
            with self.subTest(notes=notes):
                answer = offered(notes, [target], {'comments': [notes]})
                self.assertEqual(answer['comments']['status'], expected)
                if expected == 'supported': self.assert_stored_clear(notes, [target], answer)
                else:
                    old = {'text': notes, 'status': 'supported', 'evidence': [{'quote': notes, 'start': 0, 'end': len(notes)}]}
                    self.assertEqual(g.governed_decisions(notes, [target], {'comments': old}), ['Additional comments'])
        target['answer_policy'] = {'attestation': 'document_review', 'attestation_source': {**source, 'text': 'Confirm patient reviewed report.'}}
        for notes, expected in (('The patient has reviewed the report.', 'supported'),
                                ('The patient was given an opportunity to comment on the report.', 'conflict'),
                                ('The patient has not reviewed the report.', 'conflict'),
                                ('The patient will review the report.', 'conflict'),
                                ('The patient had the procedure.', 'conflict')):
            with self.subTest(notes=notes):
                self.assertEqual(offered(notes, [target], {'comments': [notes]})['comments']['status'], expected)
        for notes in ('The patient reviewed only the title of the report.',
                      'The patient read the report summary.', 'The patient reviewed part of the report.'):
            self.assertEqual(offered(notes, [target], {'comments': [notes]})['comments']['status'], 'conflict')
        both = {**target['answer_policy'], 'source_author': 'patient', 'source': source}
        target['answer_policy'] = both
        notes = 'The patient has reviewed the report.'
        self.assertEqual(offered(notes, [target], {'comments': [notes]})['comments']['status'], 'conflict')
        notes = 'The patient reports having read the report.'
        self.assertEqual(offered(notes, [target], {'comments': [notes]})['comments']['status'], 'supported')
        target['answer_policy'] = {'attestation': 'document_review', 'source': source}
        self.assertEqual(offered(notes, [target], {'comments': [notes]})['comments']['status'], 'conflict')

    def test_document_review_uses_exact_printed_object_and_conjunction(self):
        source = {'part': 'word/document.xml', 'slot': 'b/p[0]', 'fingerprint': 'a' * 64}
        target = field('f', 'Additional comments')
        instructions = (
            ('Please confirm that the patient has had sight of this report and/or had an opportunity to add their comments, if appropriate or necessary.', 'report', False),
            ('Please confirm that the patient has had sight of this application and had an opportunity to add their comments', 'application', True),
            ('Confirm patient reviewed the form and had an opportunity to comment on the form.', 'form', True),
            ('Confirm patient reviewed the document or had an opportunity to comment on the document.', 'document', False),
        )
        for instruction, obj, both in instructions:
            target['answer_policy'] = {'attestation': 'document_review', 'attestation_source': {**source, 'text': instruction}}
            coordinated = f'The patient has read the {obj} and had an opportunity to add comments about the {obj}.'
            # The first report sentence is the unchanged predeclared D30 positive.
            review = f'The patient has read the {obj}.'
            opportunity = f'The patient was given an opportunity to comment on the {obj}.'
            cases = [(coordinated, 'supported'), (review, 'conflict' if both else 'supported'),
                     (opportunity, 'conflict' if both else 'supported'),
                     (f'The patient has read the {obj} and had an opportunity to add their comments.', 'supported'),
                     (f'The patient reviewed only the title of the {obj}.', 'conflict'),
                     (f'The patient read part of the {obj} and had an opportunity to comment on the {obj}.', 'conflict'),
                     (f'The patient has not read the {obj} and had an opportunity to comment on the {obj}.', 'conflict'),
                     (f'The patient will read the {obj} and have an opportunity to comment on the {obj}.', 'conflict'),
                     (f'The patient has read the {obj} and the clinician had an opportunity to comment on the {obj}.', 'conflict'),
                     ('The patient has read the letter and had an opportunity to comment on the letter.', 'conflict')]
            for notes, expected in cases:
                with self.subTest(instruction=instruction, notes=notes):
                    answers = offered(notes, [target], {'f': [notes]})
                    self.assertEqual(answers['f']['status'], expected)
                    if expected == 'supported': self.assert_stored_clear(notes, [target], answers)
                    else:
                        old = {'text': notes, 'status': 'supported', 'reviewed': True,
                               'evidence': [{'quote': notes, 'start': 0, 'end': len(notes)}]}
                        self.assertEqual(g.governed_decisions(notes, [target], {'f': old}), ['Additional comments'])
            notes = review + ' ' + opportunity
            answers = offered(notes, [target], {'f': [review, opportunity]})
            self.assertEqual(answers['f']['status'], 'supported')
            self.assert_stored_clear(notes, [target], answers)
        # Unknown conditional obligations cannot be replaced by the simple rule.
        target['answer_policy']['attestation_source']['text'] = 'Confirm patient reviewed the report unless sharing it is inappropriate.'
        notes = 'The patient has read the report.'
        self.assertEqual(offered(notes, [target], {'f': [notes]})['f']['status'], 'conflict')

    def test_additional_preserved_instructions_cannot_be_ignored_by_attestation(self):
        source = {'part': 'word/document.xml', 'slot': 'b/tbl[0]/tr[0]/tc[0]', 'fingerprint': 'a' * 64,
                  'text': 'Confirm patient reviewed the application and had an opportunity to comment on the application.'}
        target = field('f', 'Additional comments')
        target['answer_policy'] = {'attestation': 'document_review', 'attestation_source': source}
        notes = 'The patient has read the application and had an opportunity to comment on the application.'
        self.assertEqual(offered(notes, [target], {'f': [notes]})['f']['status'], 'supported')
        target['source_instructions'] = [{**source, 'slot': 'b/tbl[0]/tr[0]/tc[1]',
            'text': 'Third-party information should not be shared with the patient. The patient should still have an opportunity to comment whether or not seeing the full application.'}]
        self.assertEqual(offered(notes, [target], {'f': [notes]})['f']['status'], 'conflict')
        old = {'text': notes, 'status': 'supported', 'reviewed': True,
               'evidence': [{'quote': notes, 'start': 0, 'end': len(notes)}]}
        self.assertEqual(g.governed_decisions(notes, [target], {'f': old}), ['Additional comments'])
        target.pop('answer_policy')
        ordinary = 'The patient reports intermittent buzzing.'
        self.assertEqual(offered(ordinary, [target], {'f': [ordinary]})['f']['status'], 'supported')

    def test_correction_subject_omission_contradiction_and_consent_guards_survive(self):
        first = 'The patient reports intermittent buzzing.'
        fields = repeated()
        for prefix in ('Family history:\n', 'The following symptoms are denied:\n'):
            self.assertEqual(offered(prefix + first, fields, {'sensation': [first]})['sensation']['status'], 'conflict')
        tail = 'Correction: this history belongs to another patient.'
        self.assertEqual(offered(first + ' ' + tail, fields, {'sensation': [first]})['sensation']['status'], 'conflict')
        for relation in ('qualifier', 'contrary', 'unresolved'):
            tail = 'The buzzing resolved yesterday.'
            self.assertEqual(offered(first + ' ' + tail, fields, {'sensation': [first]},
                overrides={('sensation', tail): relation})['sensation']['status'], 'conflict')
        fields = [field('consent', 'Consent obtained', 'checkbox', ['Consent obtained'])]
        note = 'The patient had the procedure.'
        self.assertEqual(offered(note, fields, {'consent': [note]}, choices={'consent': ['consent:0']})['consent']['status'], 'conflict')

    def test_partition_and_original_option_references_are_closed(self):
        notes = 'The patient does not smoke.'
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No'])]
        original = relation_body(notes, fields, {'smoking': [notes]}, choices={'smoking': ['smoking:1']})
        units = g.source_units(notes, fields)[0]
        mutations = [lambda b: b['fields'].append(copy.deepcopy(b['fields'][0])),
                     lambda b: b['fields'][0].update(context=[]),
                     lambda b: b['fields'][0].update(unit_ids=[999]),
                     lambda b: b['fields'][0].update(option_ids=['other:1']),
                     lambda b: b['fields'][0].update(option_ids=['smoking:1', 'smoking:1']),
                     lambda b: b['fields'][0].update(conflict='false')]
        for mutate in mutations:
            body = copy.deepcopy(original); mutate(body)
            with self.subTest(body=body), self.assertRaises((ValueError, ValidationError)):
                r.records(notes, fields, [], units, r.FieldSelections.model_validate(body), g.SONNET_5)
        # A context that covers the source exactly but disagrees with the selection (the selected unit called
        # independent) is not malformed: it was in the list above until live attempt 020 failed a whole job on it.
        # It is recorded as the model returned it, and THIS field is held.
        body = copy.deepcopy(original); body['fields'][0].update(context=['independent'])
        held = r.records(notes, fields, [], units, r.FieldSelections.model_validate(body), g.SONNET_5)
        self.assertEqual(list(held), ['smoking'])
        answer = offered(notes, fields, {'smoking': [notes]}, choices={'smoking': ['smoking:1']},
                         overrides={('smoking', notes): 'independent'})['smoking']
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''))

    def test_stored_record_binds_source_mapping_destination_output_and_enablement(self):
        notes = 'The patient reports that the headache usually feels like intermittent buzzing.'
        fields = repeated(); original = offered(notes, fields, {'sensation': [notes]})
        for mutate in (lambda a: a['sensation'].update(text=notes + ' Changed.'),
                       lambda a: a['sensation'].update(ordinary_relation=a['sensation']['ordinary_relation'] + 'bad'),
                       lambda a: a['sensation']['evidence'][0].update(end=1),
                       lambda a: a['sensation'].pop('ordinary_relation')):
            answers = copy.deepcopy(original); mutate(answers)
            self.assertIn('Other:', g.governed_decisions(notes, fields, answers))
        moved = {'sensation': original['prodrome'], 'prodrome': original['sensation']}
        self.assertIn('Other:', g.governed_decisions(notes, fields, moved))
        altered = copy.deepcopy(fields); altered[0]['locator']['fingerprint'] = '1' * 64
        self.assertIn('Other:', g.governed_decisions(notes, altered, original))
        self.assertIn('Other:', g.governed_decisions(notes + ' New source.', fields, original))
        # The kill switch (an explicit QUILLMD_V3_FIELD_RELATIONS other than '1') refuses stored records (2026-09-30).
        with override_settings(V3_FIELD_RELATIONS=False, V3_FIELD_RELATIONS_RECORDS=False):
            self.assertIn('Other:', g.governed_decisions(notes, fields, original))

    def test_complete_catalogue_actual_wire_and_price_share_one_compiler(self):
        fields = repeated(); fields.append(field('signature', 'Clinician signature', 'signature'))
        fields[0]['source_relationships'] = [{'relation': 'previous_question', 'complete_question': 'Full original wording'}]
        notes = 'The patient reports intermittent buzzing.'
        config = g.configuration(); prepared = r.compile_request(notes, fields, config)
        wire = prepared['wire']; payload = json.loads(wire['messages'][0]['content'])
        self.assertEqual(payload['catalogue'], fields)
        self.assertEqual(payload['requested_field_ids'], ['sensation', 'prodrome'])
        self.assertNotIn('questions', payload)
        rate = g.rates(config)
        required = (Decimal(len(json.dumps(wire).encode()) + 12000) * rate['input_per_million']
                    + Decimal(wire['max_tokens']) * rate['output_per_million']) / 1000000
        self.assertGreaterEqual(g.maximum_cost(notes, fields, config), required)
        self.assertLessEqual(prepared['response_byte_bound'], wire['max_tokens'])
        with patch('anthropic.Anthropic') as sdk:
            sdk.return_value.messages.create.side_effect = RuntimeError('stop at actual SDK boundary')
            with self.assertRaisesRegex(RuntimeError, 'actual SDK boundary'):
                g.generate(notes, fields, config)
            self.assertEqual(sdk.return_value.messages.create.call_args.kwargs, wire)
        with override_settings(V3_FIELD_RELATIONS=False):
            old = g.configuration()
            self.assertNotIn('ordinary_field_contract', old)
            self.assertNotEqual(old['pricing_version'], config['pricing_version'])
            with self.assertRaises(ValidationError): r.compile_request(notes, fields, config)

    def test_closed_response_capacity_refuses_before_any_provider(self):
        fields = [field('f' + str(i), 'Finding ' + str(i)) for i in range(100)]
        notes = ' '.join('The patient reports pain.' for _ in range(129))
        with patch('anthropic.Anthropic') as sdk:
            with self.assertRaises(ValidationError): g.maximum_cost(notes, fields)
            sdk.assert_not_called()
