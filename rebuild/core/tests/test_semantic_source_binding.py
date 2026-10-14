"""Independent offline boundaries for prospective source-binding v6.

All provider replies are local synthetic fixtures, including an intentionally
passing checker on unsafe inputs. No private case artifacts are loaded here.
The separately retained all34 Casey diagnostic is not actual clinical acceptance.
"""
from copy import deepcopy
from itertools import product
import hashlib
import json

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import generation
from core import semantic_generation as semantic
from core.tests.test_semantic_generation import FixtureSender, assignments, fact, span
from documents.semantic_preparation_roles import default_definitions


V6 = 'positioned-source-binding-v6'
PATIENT = 'Synthetic Rowan Vale'
BARE_DOCTOR = 'Taylor Lane'
REFERENCES = (semantic.LEGACY_REFERENCE_CONTRACT, semantic.REFERENCE_INVENTORY_CONTRACT)
CHOICES = ['In-person', 'telephone', 'video telehealth']
# Exact complete three-stage payload/schema/instruction and answer digests from
# frozen installed f927 semantics, captured before the new v6 runtime existed.
V5_REPLAY_DIGESTS = {
    'honorific_asymmetry': (
        '8eef98adda193b0bdef7fce65e53bfcc602e21b9b5dffdb804ee7104d916949c',
        'd8ac067e1e2ee5f00889a1a97f9106ee8b3ccb61312e93b195419c3bf1e50fd6'),
    'auxiliary_negative': (
        '7594157132bb0c7c0f1e8d7ec43375065e2279c6c67baabf498d646fd5eb3740',
        '87ab8168514195c209c8ecd07e1b1d8d39988305b9c235715a9f1700ed56f319'),
    'video_literal': (
        'cd5667658d09e96bd37f7ea4cfa15c628a82bbce9addb0246795281f03288acc',
        'dfb2ddc1970244f70a290692c62588b28e5be7ecf1a1783043f5d84f4703724f'),
}


def prepared(notes, quote, *, doctor_value=BARE_DOCTOR, doctor_name=None,
             patient=PATIENT, clinical_name=None, polarity='affirmed', kind='finding',
             value_type='text', choices=(), subject='patient', timing='current',
             include_identities=True, answer_scope='patient', label='Clinical findings'):
    fields = [
        {'key': 'referrer', 'kind': 'text', 'label': 'Referring physician', 'locator': {'cell': 0}},
        {'key': 'answer', 'kind': 'text', 'label': label, 'locator': {'cell': 1}},
    ]
    definitions = default_definitions(fields)
    for definition in definitions.values():
        definition.update(version=2, answer_mode='atomic')
        definition['scope'].update(subject='patient', polarity='any', temporality='any')
    definitions['referrer'].update(value_type='person_name', meaning='The documented referring physician name.')
    definitions['referrer']['scope']['subject'] = 'other'
    definitions['answer'].update(value_type=value_type, choices=list(choices),
                                answer_mode='narrative' if value_type == 'text' else 'atomic')
    definitions['answer']['scope']['subject'] = answer_scope
    values = []
    if include_identities:
        values.append(fact(notes, fields, 'patient', patient, kind='identity',
                           name_quote=patient, timing='unspecified'))
        values.append(fact(notes, fields, 'referrer', doctor_value, kind='identity',
                           name_quote=doctor_name or doctor_value, subject='other', timing='unspecified'))
    values.append(fact(notes, fields, 'clinical', quote, kind=kind, polarity=polarity,
                       subject=subject, timing=timing, name_quote=clinical_name))
    units = generation.source_units(notes, fields)[0]
    for value in values:
        name = value['subject']['name_span']
        if name:
            name_unit = next(unit['id'] for unit in units
                             if unit['start'] <= name['start'] < name['end'] <= unit['end'])
            value['source_unit_ids'] = sorted(set(value['source_unit_ids'] + [name_unit]))
    selected = {'answer': ['clinical']}
    if include_identities:
        selected['referrer'] = ['referrer']
    return notes, fields, definitions, values, assignments(fields, selected)


def run_fixture(case, reference, scope=V6):
    notes, fields, definitions, values, selected = deepcopy(case)
    sender = FixtureSender(values, selected)
    answers = semantic.run(notes, fields, definitions, sender,
                           scope_contract=scope, reference_contract=reference)
    return answers, sender, fields, definitions


def trace_digest(answers, sender):
    return hashlib.sha256(json.dumps({'answers': answers, 'calls': sender.calls},
        sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def historical_cases():
    referral = PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '. '
    return {
        'honorific_asymmetry': prepared(referral + 'The patient reports normal bowel movements.',
            'normal bowel movements', doctor_name='Dr. ' + BARE_DOCTOR),
        'auxiliary_negative': prepared(referral + 'Rowan has never smoked and does not drink alcohol.',
            'has never smoked', polarity='negated'),
        'video_literal': prepared(referral + 'This was a video gastroenterology follow-up.',
            'video', kind='other', value_type='choice', choices=CHOICES, answer_scope='encounter'),
    }


class SemanticSourceBindingTests(SimpleTestCase):
    def generate(self, case, reference, scope=V6):
        before = deepcopy(case)
        answers, sender, fields, definitions = run_fixture(case, reference, scope)
        self.assertEqual(case, before)
        self.assertEqual([call[:2] for call in sender.calls],
                         [('extractor', 1), ('assigner', 1), ('checker', 1)])
        for field in fields:
            semantic.validate_stored_answer(case[0], field, definitions[field['key']], answers[field['key']])
        return answers, sender, fields, definitions

    def assert_held(self, answer):
        self.assertIn(answer['status'], ('conflict', 'ambiguous'))
        self.assertEqual(answer['text'], '')
        self.assertIsNone(answer['value'])
        self.assertFalse(answer['reviewed'])
        self.assertTrue(answer['review_reasons'])

    def video_case(self, statement, *, bound=True, choices=CHOICES, **kwargs):
        referral = PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '. '
        return prepared((referral if bound else '') + statement, 'video',
            include_identities=bound, kind='other', value_type='choice', choices=choices,
            answer_scope='encounter', **kwargs)

    def test_explicit_profile_constant_and_payloads(self):
        self.assertEqual(semantic.SOURCE_BINDING_SCOPE_CONTRACT, V6)
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answers, sender, _, _ = self.generate(historical_cases()['honorific_asymmetry'], reference)
                for answer in answers.values():
                    self.assertEqual(answer['fact_scope_contract'], V6)
                for call in sender.calls:
                    self.assertEqual(call[2]['fact_scope_contract'], V6)

    def test_referrer_honorific_mismatch_is_bounded_to_same_complete_identity(self):
        for title, reverse, reference in product(('Dr.', 'Dr', 'Doctor'), (False, True), REFERENCES):
            named = title + ' ' + BARE_DOCTOR
            notes = PATIENT + ' was referred by ' + named + '. Bowel sounds were normal.'
            value, name = (named, BARE_DOCTOR) if reverse else (BARE_DOCTOR, named)
            with self.subTest(title=title, reverse=reverse, reference=reference):
                case = prepared(notes, 'normal', doctor_value=value, doctor_name=name)
                answers, _, _, _ = self.generate(case, reference)
                if reverse and title == 'Dr.':
                    # The independent longstanding person_name type gate still
                    # rejects a dotted title as rendered text. Source-binding
                    # equivalence does not waive that separate contract.
                    self.assert_held(answers['referrer'])
                else:
                    self.assertEqual((answers['referrer']['status'], answers['referrer']['text']), ('supported', value))
                self.assertEqual((answers['answer']['status'], answers['answer']['text']), ('supported', 'Normal'))
                retained = next(f for f in answers['referrer']['facts'] if f['id'] == 'referrer')
                self.assertEqual(retained['value_evidence']['quote'], value)
                self.assertEqual(retained['subject']['name_evidence']['quote'], name)

    def test_partial_or_unrelated_name_equivalence_cannot_unlock_referral(self):
        cases = (
            ('Dr. Taylor Morgan Lane', 'Morgan Lane', 'Dr. Taylor Morgan Lane'),
            ('Dr. Taylor Lane SMITH', 'Taylor Lane', 'Dr. Taylor Lane SMITH'),
            ('Dr. Taylor Lane', 'Lane', 'Dr. Taylor Lane'),
            ('Professor Taylor Lane', 'Taylor Lane', 'Professor Taylor Lane'),
            ('Mr. Taylor Lane', 'Taylor Lane', 'Mr. Taylor Lane'),
            ('Dr. Taylor Lane', 'Taylor Lane', 'Dr. Taylor'),
        )
        for (source_name, value, name), reference in product(cases, REFERENCES):
            notes = PATIENT + ' was referred by ' + source_name + '. Bowel sounds were normal.'
            with self.subTest(source_name=source_name, value=value, name=name, reference=reference):
                answers, _, _, _ = self.generate(prepared(notes, 'normal', doctor_value=value,
                    doctor_name=name), reference)
                self.assert_held(answers['referrer'])
                self.assert_held(answers['answer'])

    def test_same_name_in_another_unit_cannot_supply_identity_equivalence(self):
        notes = (PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '. Dr. ' +
                 BARE_DOCTOR + ' reviewed the chart. Bowel sounds were normal.')
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                case = prepared(notes, 'normal', doctor_name='Dr. ' + BARE_DOCTOR)
                referrer = next(f for f in case[3] if f['id'] == 'referrer')
                referrer['subject']['name_span'] = span(notes, 'Dr. ' + BARE_DOCTOR, 1)
                units = generation.source_units(notes, case[1])[0]
                referrer['source_unit_ids'] = [u['id'] for u in units if u['quote'].startswith((PATIENT, 'Dr.'))]
                answers, _, _, _ = self.generate(case, reference)
                self.assert_held(answers['referrer'])
                self.assert_held(answers['answer'])

    def test_title_equivalence_requires_complete_source_referrer_boundaries(self):
        source_names = (
            'Dr. Taylor Lane-Smith', 'Dr. Taylor Lane Smith',
            'Dr. Taylor Lane SMITH', 'Dr. Taylor Lane Jr',
            'Dr. Taylor Lane III', 'Senior Dr. Taylor Lane',
            'Professor Dr. Taylor Lane',
        )
        for source_name, reference in product(source_names, REFERENCES):
            notes = PATIENT + ' was referred by ' + source_name + '. Bowel sounds were normal.'
            with self.subTest(source_name=source_name, reference=reference):
                # Both extractor spans omit the same source suffix/prefix;
                # agreement between them is not proof of a complete identity.
                case = prepared(notes, 'normal', doctor_name='Dr. ' + BARE_DOCTOR)
                answers, _, _, _ = self.generate(case, reference)
                self.assert_held(answers['referrer'])
                self.assert_held(answers['answer'])

    def test_title_equivalence_cannot_treat_a_wrapped_name_as_terminated(self):
        for separator, suffix, reference in product(
                ('\n', '\r\n', '\u2028', '\v', '\f'),
                ('Smith.', '-Smith.', 'Jr.', 'III.'), REFERENCES):
            notes = (PATIENT + ' was referred by Dr. ' + BARE_DOCTOR +
                     separator + suffix + '\nBowel sounds were normal.')
            with self.subTest(separator=separator, suffix=suffix, reference=reference):
                if separator in ('\v', '\f'):
                    with self.assertRaisesRegex(ValidationError, 'Control characters are not permitted'):
                        self.generate(prepared(notes, 'normal',
                            doctor_name='Dr. ' + BARE_DOCTOR), reference)
                    continue
                answers, _, _, _ = self.generate(prepared(notes, 'normal',
                    doctor_name='Dr. ' + BARE_DOCTOR), reference)
                self.assert_held(answers['referrer'])
                self.assert_held(answers['answer'])

    def test_title_equivalence_does_not_release_quoted_or_qualified_referral(self):
        referral = PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '.'
        sources = [prefix + referral for prefix in (
            'Possibly, ', 'According to an unverified report, ',
            'It is unclear whether ', 'Reportedly, ', 'Allegedly, ')]
        sources += ['"' + referral + '"', 'The note quotes: "' + referral + '"']
        for source, reference in product(sources, REFERENCES):
            notes = source + ' Bowel sounds were normal.'
            with self.subTest(source=source, reference=reference):
                answers, _, _, _ = self.generate(prepared(notes, 'normal',
                    doctor_name='Dr. ' + BARE_DOCTOR), reference)
                self.assert_held(answers['referrer'])
                self.assert_held(answers['answer'])

    def test_patient_identity_cannot_use_referrer_honorific_exception(self):
        notes = 'Dr. ' + PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '. Bowel sounds were normal.'
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                case = prepared(notes, 'normal')
                patient = next(f for f in case[3] if f['id'] == 'patient')
                patient['subject']['name_span'] = span(notes, 'Dr. ' + PATIENT)
                answers, _, _, _ = self.generate(case, reference)
                self.assert_held(answers['answer'])

    def test_unknown_person_and_missing_identity_still_block_honorific_referral(self):
        for interruption, omitted, reference in product(
                ('', 'A visitor entered the room. '), ('patient', 'referrer', None), REFERENCES):
            if not interruption and omitted is None:
                continue
            notes = PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '. ' + interruption + 'Bowel sounds were normal.'
            with self.subTest(interruption=interruption, omitted=omitted, reference=reference):
                case = prepared(notes, 'normal', doctor_name='Dr. ' + BARE_DOCTOR)
                if omitted:
                    case[3][:] = [f for f in case[3] if f['id'] != omitted]
                    if omitted == 'referrer':
                        case[4]['fields'][0].update(fact_ids=[], status='missing')
                answers, _, _, _ = self.generate(case, reference)
                self.assert_held(answers['answer'])

    def test_complete_auxiliary_smoking_negative_preserves_exact_literal_value(self):
        for bound, quote, reference in product((True, False), ('has never smoked', 'never smoked'), REFERENCES):
            referral = PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '. '
            statement = ('Rowan' if bound else 'The patient') + ' has never smoked and does not drink alcohol.'
            with self.subTest(bound=bound, quote=quote, reference=reference):
                case = prepared((referral if bound else '') + statement, quote,
                    include_identities=bound, polarity='negated')
                answer = self.generate(case, reference)[0]['answer']
                self.assertEqual((answer['status'], answer['text']), ('supported', quote[0].upper() + quote[1:]))
                self.assertEqual(next(f for f in answer['facts'] if f['id'] == 'clinical')['value_evidence']['quote'], quote)
                self.assertNotIn('tobacco', answer['text'].lower())

    def test_auxiliary_negative_does_not_release_uncertainty_or_other_ownership(self):
        statements = (
            ('Rowan may have never smoked.', 'never smoked'),
            ('Rowan has never explicitly denied smoking.', 'has never explicitly denied smoking'),
            ('Nolan has never smoked and does not drink alcohol.', 'has never smoked'),
            ('A visitor entered the room. The patient has never smoked.', 'has never smoked'),
            ('Rowan reportedly has never smoked.', 'has never smoked'),
            ('Rowan has never smoked cigarettes.', 'has never smoked'),
        )
        for (statement, quote), reference in product(statements, REFERENCES):
            notes = PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '. ' + statement
            with self.subTest(statement=statement, reference=reference):
                self.assert_held(self.generate(prepared(notes, quote, polarity='negated'), reference)[0]['answer'])

    def test_smoking_negative_cannot_become_bare_or_affirmed(self):
        notes = PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '. Rowan has never smoked.'
        for quote, polarity, reference in product(('smoked', 'has never smoked'), ('affirmed', 'negated'), REFERENCES):
            if quote == 'has never smoked' and polarity == 'negated':
                continue
            with self.subTest(quote=quote, polarity=polarity, reference=reference):
                self.assert_held(self.generate(prepared(notes, quote, polarity=polarity), reference)[0]['answer'])

    def test_new_auxiliary_negative_requires_complete_context_in_both_source_orders(self):
        for competing, first, reference in product(
                ('Rowan smokes.', 'A visitor entered the room.',
                 'Rowan has never smoked cigarettes.'), (False, True), REFERENCES):
            statements = ['Rowan has never smoked.', competing]
            if first:
                statements.reverse()
            notes = PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '. ' + ' '.join(statements)
            with self.subTest(competing=competing, first=first, reference=reference):
                # The competing/unknown unit is deliberately absent from facts.
                case = prepared(notes, 'has never smoked', polarity='negated')
                self.assert_held(self.generate(case, reference)[0]['answer'])

    def test_auxiliary_negative_keeps_unrelated_recognized_context(self):
        for first, reference in product((False, True), REFERENCES):
            statements = ['Rowan has never smoked.', 'The patient reports cough.']
            if first:
                statements.reverse()
            notes = PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '. ' + ' '.join(statements)
            with self.subTest(first=first, reference=reference):
                answer = self.generate(prepared(notes, 'has never smoked', polarity='negated'), reference)[0]['answer']
                self.assertEqual((answer['status'], answer['text']), ('supported', 'Has never smoked'))

    def test_title_exception_cannot_release_old_negative_heads_in_incomplete_context(self):
        clinical_frames = (
            ('Rowan has never smoked.', 'never smoked'),
            ('Rowan has never smoked.', 'has never smoked'),
            ('The patient has never used tobacco.', 'never used tobacco'),
            ('The patient does not drink alcohol.', 'does not drink alcohol'),
            ('The patient does not use recreational drugs.', 'does not use recreational drugs'),
            ('On examination, the abdomen was soft, non-tender and non-distended.', 'non-tender'),
            ('On examination, the abdomen was soft, non-tender and non-distended.', 'non-distended'),
            ('On examination, the patient was alert, oriented and in no acute distress.', 'in no acute distress'),
        )
        referral = PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + '. '
        for (statement, quote), first, extra, reference in product(
                clinical_frames, (False, True),
                ('A visitor entered the room.', 'Rowan smokes.'), REFERENCES):
            statements = [statement, extra]
            if first:
                statements.reverse()
            notes = referral + ' '.join(statements)
            with self.subTest(quote=quote, first=first, extra=extra, reference=reference):
                answers, _, _, _ = self.generate(prepared(notes, quote, polarity='negated',
                    doctor_name='Dr. ' + BARE_DOCTOR), reference)
                self.assert_held(answers['referrer'])
                self.assert_held(answers['answer'])

    def test_title_exception_keeps_complete_negative_context_and_real_name_terminators(self):
        for ending, reference in product(('. ', '.\n', '.\r\n'), REFERENCES):
            notes = (PATIENT + ' was referred by Dr. ' + BARE_DOCTOR + ending +
                     'Rowan has never smoked and does not drink alcohol.')
            for quote in ('has never smoked', 'never smoked', 'does not drink alcohol'):
                with self.subTest(ending=ending, reference=reference, quote=quote):
                    answers, _, _, _ = self.generate(prepared(notes, quote, polarity='negated',
                        doctor_name='Dr. ' + BARE_DOCTOR), reference)
                    self.assertEqual((answers['referrer']['status'], answers['referrer']['text']),
                                     ('supported', BARE_DOCTOR))
                    self.assertEqual((answers['answer']['status'], answers['answer']['text']),
                                     ('supported', quote[0].upper() + quote[1:]))

    def test_video_maps_only_to_the_unique_existing_approved_choice(self):
        for bound, specialty, visit, reference in product((True, False),
                ('gastroenterology ', 'cardiology ', ''), ('visit', 'follow-up', 'consultation'), REFERENCES):
            statement = 'This was a video ' + specialty + visit + '.'
            with self.subTest(bound=bound, statement=statement, reference=reference):
                answer = self.generate(self.video_case(statement, bound=bound), reference)[0]['answer']
                self.assertEqual((answer['status'], answer['text'], answer['value']),
                                 ('supported', 'video telehealth', 'video telehealth'))
                clinical = next(f for f in answer['facts'] if f['id'] == 'clinical')
                self.assertEqual(clinical['value_evidence']['quote'], 'video')

    def test_video_output_keeps_the_exact_approved_choice_spelling(self):
        for target, reference in product(('video telehealth', 'Video telehealth', 'Video Telehealth'), REFERENCES):
            with self.subTest(target=target, reference=reference):
                choices = ['In-person', 'telephone', target]
                answer = self.generate(self.video_case('This was a video visit.', choices=choices), reference)[0]['answer']
                self.assertEqual((answer['status'], answer['text'], answer['value']), ('supported', target, target))

    def test_video_alias_refuses_unfamiliar_choice_domains_or_ambiguous_targets(self):
        choices_list = (
            ['telephone', 'In-person'], ['video telehealth', 'telehealth'],
            ['video telehealth', 'other'], ['video telehealth', 'Video telehealth'],
            ['video telehealth', 'telephone', 'remote consultation'],
        )
        for choices, reference in product(choices_list, REFERENCES):
            with self.subTest(choices=choices, reference=reference):
                try:
                    answer = self.generate(self.video_case('This was a video visit.', choices=choices), reference)[0]['answer']
                except ValidationError:
                    continue  # Invalid approved definitions also fail closed.
                self.assert_held(answer)

    def test_video_alias_does_not_infer_unowned_denied_uncertain_or_quoted_modality(self):
        statements = (
            'This was not a video visit.', 'This may have been a video visit.',
            'A video visit was discussed.', 'The patient watched a video.',
            '"This was a video visit."', "Nolan's encounter was a video visit.",
            'A visitor entered the room. This was a video visit.',
            'This was a video visit for another patient.',
        )
        for statement, bound, reference in product(statements, (True, False), REFERENCES):
            with self.subTest(statement=statement, bound=bound, reference=reference):
                self.assert_held(self.generate(self.video_case(statement, bound=bound), reference)[0]['answer'])

    def test_video_alias_refuses_explicit_current_modality_conflicts_in_either_order(self):
        for competing, first, bound, reference in product(('telephone', 'in-person'), (False, True), (True, False), REFERENCES):
            statements = ['This was a video visit.', 'This was a ' + competing + ' visit.']
            if first:
                statements.reverse()
            with self.subTest(competing=competing, first=first, bound=bound, reference=reference):
                self.assert_held(self.generate(self.video_case(' '.join(statements), bound=bound), reference)[0]['answer'])

    def test_video_alias_cannot_bypass_fact_owner_polarity_or_current_scope(self):
        for subject, polarity, timing, reference in product(('other', 'patient'), ('affirmed', 'negated'), ('past', 'current'), REFERENCES):
            if (subject, polarity, timing) == ('patient', 'affirmed', 'current'):
                continue
            with self.subTest(subject=subject, polarity=polarity, timing=timing, reference=reference):
                case = self.video_case('This was a video visit.', subject=subject,
                    polarity=polarity, timing=timing,
                    clinical_name=BARE_DOCTOR if subject == 'other' else None)
                self.assert_held(self.generate(case, reference)[0]['answer'])

    def test_video_alias_checks_omitted_consent_and_referral_modalities(self):
        competitors = (
            'The patient gave verbal consent for this telephone consultation.',
            'The patient gave verbal consent for this in-person consultation.',
            'The patient was referred for a telephone consultation.',
            'The patient was referred for an in-person consultation.',
        )
        for competing, first, bound, reference in product(competitors, (False, True), (True, False), REFERENCES):
            statements = ['This was a video visit.', competing]
            if first:
                statements.reverse()
            with self.subTest(competing=competing, first=first, bound=bound, reference=reference):
                self.assert_held(self.generate(self.video_case(' '.join(statements), bound=bound), reference)[0]['answer'])

    def test_video_alias_keeps_compatible_consent_in_both_source_orders(self):
        for modality, first, bound, reference in product(
                ('video', 'telehealth', 'video telehealth'), (False, True), (True, False), REFERENCES):
            statements = ['This was a video visit.',
                          'The patient gave verbal consent for this ' + modality + ' consultation.']
            if first:
                statements.reverse()
            with self.subTest(modality=modality, first=first, bound=bound, reference=reference):
                case = self.video_case(' '.join(statements), bound=bound)
                if first and modality.startswith('video'):
                    # The consent occurrence is not the encounter-modality
                    # slot. Its refusal is intentional even with a later visit.
                    self.assert_held(self.generate(case, reference)[0]['answer'])
                    case[3][-1] = fact(case[0], case[1], 'clinical', 'video',
                                      kind='other', occurrence=1)
                answer = self.generate(case, reference)[0]['answer']
                self.assertEqual((answer['status'], answer['text']), ('supported', 'video telehealth'))

    def test_alias_is_not_applied_to_text_or_patient_choice_destinations(self):
        for text_destination, reference in product((True, False), REFERENCES):
            case = self.video_case('This was a video visit.')
            if text_destination:
                case[2]['answer'].update(value_type='text', choices=[])
            else:
                case[2]['answer']['scope']['subject'] = 'patient'
            with self.subTest(text_destination=text_destination, reference=reference):
                answer = self.generate(case, reference)[0]['answer']
                if text_destination:
                    self.assertEqual((answer['status'], answer['text']), ('supported', 'Video'))
                else:
                    self.assert_held(answer)

    def test_stored_alias_readback_rejects_changed_output_or_fact_evidence(self):
        case = self.video_case('This was a video visit.')
        for reference in REFERENCES:
            answers, _, fields, definitions = self.generate(case, reference)
            original = answers['answer']
            for mutation in ('text', 'value', 'scope', 'source_fact'):
                with self.subTest(reference=reference, mutation=mutation):
                    changed = deepcopy(original)
                    if mutation in ('text', 'value'):
                        changed[mutation] = 'telephone'
                    elif mutation == 'scope':
                        changed['fact_scope_contract'] = semantic.SOURCE_CONTEXT_SCOPE_CONTRACT
                    else:
                        next(f for f in changed['facts'] if f['id'] == 'clinical')['value_evidence']['quote'] = 'telephone'
                    with self.assertRaises(ValidationError):
                        semantic.validate_stored_answer(case[0], fields[1], definitions['answer'], changed)

    def test_v5_full_requests_and_answers_remain_exact(self):
        self.assertEqual(set(V5_REPLAY_DIGESTS), set(historical_cases()))
        for name, case in historical_cases().items():
            for reference_index, reference in enumerate(REFERENCES):
                with self.subTest(name=name, reference=reference):
                    answers, sender, _, _ = self.generate(case, reference, semantic.SOURCE_CONTEXT_SCOPE_CONTRACT)
                    self.assertEqual(trace_digest(answers, sender), V5_REPLAY_DIGESTS[name][reference_index])
                    self.assert_held(answers['answer'])
