"""Bounded v7 same-unit attribution; every provider response is a local fixture.

The passing checker is deliberately permissive on adversarial inputs. Source
ownership, complete identity spans and exact purpose components remain gates.
No saved clinical case or generated output is loaded by these tests.
"""
from copy import deepcopy
from itertools import product

from django.test import SimpleTestCase

from core import generation, semantic_generation as semantic
from core.tests.test_semantic_generation import FixtureSender, assignments, checker, fact, span
from core.tests.test_semantic_source_binding import trace_digest
from documents.semantic_preparation_roles import default_definitions


V7 = 'positioned-referral-citation-v7'
PATIENT = 'Synthetic Robin Hart'
DOCTOR = 'Jamie Quinn'
REFERENCES = (semantic.LEGACY_REFERENCE_CONTRACT, semantic.REFERENCE_INVENTORY_CONTRACT)
PURPOSE = 'in-person gastroenterology visit to review previous GI records'
# Complete request/schema/instruction/answer traces from frozen v6 source
# 2647c3d520ca6a5f0579efec465adebcf0be23e584e125fbb8d4ae94ba518584.
# Each tuple follows REFERENCES order, and covers the same titled-referrer case.
HISTORICAL_TRACES = {
    'note-wide-offer-scope-v1': ('af085e0cd542a7ea9998abf4ec67ff3a09c11cde5e992f129c6c1f31da8cf0fa',
        '19bf39efe232061f4bb2211779c1881dbe78a04365dca6839576af01a975522d'),
    'positioned-fact-scope-v2': ('c0bbfef4125de2040d9a6ccf102666713d21ecc0ca8456ef4f7055696e60fe2f',
        'c5a8d3d5a2e25e285b1eb9e9cc002f07040f48601966eef50d8a1558f5b5b475'),
    'dimension-aware-duration-scope-v3': ('02194ae5b16160aa2bea51a78afdb9d6a2513d01b30a11f222d375d44188ed37',
        '2d90b55d58055e40b05e3abd60c74a72acf18c32a5cbc2af31d7d4ac6ef811e8'),
    'positioned-family-context-v4': ('e1447c1b5dc6bfcef90758666eb10704429cdb15b0ed26188ad22c7601671a62',
        'efb0c8b01e45d1b187a8b524ad188d36f6f0b035f3cf68459452ba8efb98d652'),
    'positioned-source-context-v5': ('18e8e0d4671fe70638779786c243d95e198c188fc5e089418cac1f47a5e103ef',
        '77dcedd2555aec51f96fd5d483d321b22889d38ca5b0ce345fa03c816e85445d'),
    'positioned-source-binding-v6': ('25ee52d6a62c9b6b0a1bb0183d5707d811cc34eff326cdbd82d9926ae5480de9',
        '40cae2d9890097aea35713f34d8bbf34a5cf1811434e7ded45492fedeb6d2930'),
}


def referral_case(*, title='Dr.', reverse=False, exact=False, source_name=None,
                  prefix=None, suffix='', visit=PURPOSE, modality='in-person',
                  selected_purpose=None, clinical_name=PATIENT):
    titled = title+' '+DOCTOR
    prefix = PATIENT+' is 47 years old and was referred by ' if prefix is None else prefix
    notes = prefix+(source_name or titled)+' for an '+visit+'.'+suffix
    fields = [
        {'key':'referrer', 'kind':'text', 'label':'Referring physician', 'locator':{'cell':0}},
        {'key':'modality', 'kind':'text', 'label':'Visit modality', 'locator':{'cell':1}},
        {'key':'purpose', 'kind':'text', 'label':'Reason for evaluation', 'locator':{'cell':2}},
    ]
    definitions = default_definitions(fields)
    for definition in definitions.values():
        definition.update(version=2, answer_mode='atomic')
        definition['scope'].update(subject='patient', polarity='any', temporality='any')
    definitions['referrer'].update(value_type='person_name', meaning='The complete referring physician identity.')
    definitions['referrer']['scope']['subject'] = 'other'
    definitions['modality'].update(value_type='choice', choices=['In-person','telephone','video telehealth'])
    definitions['modality']['scope']['subject'] = 'encounter'
    definitions['purpose'].update(answer_mode='narrative', meaning='The complete reason for the patient evaluation.')
    value, name = (titled, DOCTOR) if reverse else (DOCTOR, titled)
    if exact:
        value = name = DOCTOR
    facts = [
        fact(notes, fields, 'patient', PATIENT, kind='identity', name_quote=PATIENT, timing='unspecified'),
        fact(notes, fields, 'referrer', value, kind='identity', subject='other', name_quote=name, timing='unspecified'),
        fact(notes, fields, 'modality', modality, kind='other', name_quote=clinical_name),
        fact(notes, fields, 'purpose', selected_purpose or visit, kind='reason', name_quote=clinical_name),
    ]
    units = generation.source_units(notes, fields)[0]
    for value in facts:
        name = value['subject']['name_span']
        if name:
            name_unit = next(unit['id'] for unit in units
                             if unit['start'] <= name['start'] < name['end'] <= unit['end'])
            value['source_unit_ids'] = sorted(set(value['source_unit_ids']+[name_unit]))
    return notes, fields, definitions, facts, assignments(fields,
        {'referrer':['referrer'], 'modality':['modality'], 'purpose':['purpose']})


class ReferralCitationTests(SimpleTestCase):
    def generate(self, case, reference, scope=V7, *, fact_findings=()):
        original = deepcopy(case)
        notes, fields, definitions, facts, selected = deepcopy(case)
        checked = checker(selected, fact_findings=fact_findings)
        sender = FixtureSender(facts, selected, checked, repaired=selected, rechecked=checked)
        result = semantic.run(notes, fields, definitions, sender,
                              reference_contract=reference, scope_contract=scope)
        self.assertEqual(case, original)
        self.assertLessEqual(len(sender.calls), 5)
        self.assertEqual(sum(call[0]=='extractor' for call in sender.calls), 1)
        for field in fields:
            semantic.validate_stored_answer(notes, field, definitions[field['key']], result[field['key']])
        return result, sender

    def assert_held(self, answer):
        self.assertIn(answer['status'], ('ambiguous','conflict'))
        self.assertEqual(answer['text'], '')
        self.assertIsNone(answer['value'])
        self.assertTrue(answer['review_reasons'])
        self.assertFalse(answer['reviewed'])

    def test_all_six_historical_profiles_keep_complete_request_answer_traces(self):
        for scope, expected in HISTORICAL_TRACES.items():
            for reference, golden in zip(REFERENCES, expected):
                with self.subTest(scope=scope, reference=reference):
                    answers, sender = self.generate(referral_case(), reference, scope)
                    self.assertEqual(trace_digest(answers, sender), golden)

    def test_same_unit_title_equivalence_releases_only_new_profile(self):
        self.assertEqual(semantic.REFERRAL_CITATION_SCOPE_CONTRACT, V7)
        for title, reference in product(('Dr.','Dr','Doctor'), REFERENCES):
            with self.subTest(title=title, reference=reference):
                case = referral_case(title=title)
                old, _ = self.generate(case, reference, semantic.SOURCE_BINDING_SCOPE_CONTRACT)
                self.assert_held(old['modality'])
                self.assert_held(old['purpose'])
                current, sender = self.generate(case, reference)
                self.assertEqual([call[:2] for call in sender.calls],
                                 [('extractor',1),('assigner',1),('checker',1)])
                self.assertTrue(all(answer['status']=='supported' for answer in current.values()))
                self.assertEqual(current['modality']['text'], 'In-person')
                self.assertEqual(current['purpose']['text'], PURPOSE[0].upper()+PURPOSE[1:])
                for answer in current.values():
                    self.assertEqual(answer['fact_scope_contract'], V7)
                referrer = next(f for f in current['referrer']['facts'] if f['id']=='referrer')
                self.assertEqual(referrer['value_evidence']['quote'], DOCTOR)
                self.assertEqual(referrer['subject']['name_evidence']['quote'], title+' '+DOCTOR)

    def test_reverse_and_exact_name_spans_keep_independent_type_rules(self):
        for title, reference in product(('Dr.','Dr','Doctor'), REFERENCES):
            with self.subTest(title=title, reference=reference):
                reverse, _ = self.generate(referral_case(title=title, reverse=True), reference)
                self.assertEqual(reverse['modality']['status'], 'supported')
                self.assertEqual(reverse['purpose']['status'], 'supported')
                if title == 'Dr.':
                    # A dotted title is still refused by the independent
                    # person_name display type; v7 changes only attribution.
                    self.assert_held(reverse['referrer'])
                else:
                    self.assertEqual(reverse['referrer']['status'], 'supported')
                for scope in (semantic.SOURCE_BINDING_SCOPE_CONTRACT, V7):
                    exact, _ = self.generate(referral_case(title=title, exact=True), reference, scope)
                    self.assertTrue(all(answer['status']=='supported' for answer in exact.values()))

    def test_complete_modality_visit_and_reason_components_are_admitted(self):
        for selected, reference in product((PURPOSE, 'to review previous GI records'), REFERENCES):
            with self.subTest(selected=selected, reference=reference):
                answers, _ = self.generate(referral_case(selected_purpose=selected), reference)
                self.assertEqual(answers['modality']['status'], 'supported')
                self.assertEqual(answers['purpose']['status'], 'supported')

    def test_purpose_fragments_and_other_same_unit_values_stay_held(self):
        for quote, reference in product(('gastroenterology', 'previous GI records', 'review previous GI records',
                                          'in-person gastroenterology'), REFERENCES):
            with self.subTest(quote=quote, reference=reference):
                answers, _ = self.generate(referral_case(selected_purpose=quote), reference)
                self.assert_held(answers['purpose'])
                self.assertEqual(answers['modality']['status'], 'supported')

    def test_clipped_names_foreign_suffixes_and_unrecognized_titles_stay_held(self):
        names = ('Dr. Jamie Quinn-Smith','Dr. Jamie Quinn Smith','Dr. Jamie Quinn SMITH',
                 'Dr. Jamie Quinn Jr','Dr. Jamie Quinn III','Senior Dr. Jamie Quinn',
                 'Professor Dr. Jamie Quinn','Dr. Jamie Quinn\nSmith',
                 'Dr. Jamie Quinn\r\n-Smith')
        for name, reference in product(names, REFERENCES):
            with self.subTest(name=name, reference=reference):
                answers, _ = self.generate(referral_case(source_name=name), reference)
                for answer in answers.values():
                    self.assert_held(answer)

    def test_partial_referrer_names_cannot_release_patient_purpose(self):
        for quote, reference in product(('Quinn','Jamie'), REFERENCES):
            with self.subTest(quote=quote, reference=reference):
                case = referral_case()
                referrer = next(f for f in case[3] if f['id']=='referrer')
                referrer['value_span'] = span(case[0], quote)
                answers, _ = self.generate(case, reference)
                self.assert_held(answers['modality'])
                self.assert_held(answers['purpose'])

    def test_referrer_reference_to_different_occurrence_is_not_equivalent(self):
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                case = referral_case(suffix=' Dr. Jamie Quinn reviewed the chart.')
                referrer = next(f for f in case[3] if f['id']=='referrer')
                referrer['subject']['name_span'] = span(case[0], 'Dr. Jamie Quinn', 1)
                referrer['source_unit_ids'] = [u['id'] for u in generation.source_units(case[0],case[1])[0]]
                answers, _ = self.generate(case, reference)
                self.assert_held(answers['modality'])
                self.assert_held(answers['purpose'])

    def test_uncertain_quoted_hypothetical_or_nonreferral_context_cannot_release(self):
        prefixes = ('Possibly, '+PATIENT+' was referred by ',
                    'If '+PATIENT+' was referred by ',
                    'The clinician quoted: "'+PATIENT+' was referred by ',
                    PATIENT+' may have been referred by ',
                    PATIENT+' was accompanied by ')
        for prefix, reference in product(prefixes, REFERENCES):
            with self.subTest(prefix=prefix, reference=reference):
                answers, _ = self.generate(referral_case(prefix=prefix), reference)
                self.assert_held(answers['modality'])
                self.assert_held(answers['purpose'])

    def test_unknown_or_foreign_owner_follow_on_blocks_title_equivalence(self):
        for suffix, reference in product((' Another patient entered the room.',
                ' Synthetic Nolan Reed reports wheezing.', ' Robin smokes.'), REFERENCES):
            with self.subTest(suffix=suffix, reference=reference):
                answers, _ = self.generate(referral_case(suffix=suffix), reference)
                self.assert_held(answers['modality'])
                self.assert_held(answers['purpose'])

    def test_wrong_or_absent_patient_name_does_not_waive_same_unit_ownership(self):
        for name, reference in product((None, DOCTOR), REFERENCES):
            with self.subTest(name=name, reference=reference):
                answers, _ = self.generate(referral_case(clinical_name=name), reference)
                self.assert_held(answers['modality'])
                self.assert_held(answers['purpose'])

    def test_checker_fact_holds_remain_authoritative_after_source_fix(self):
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answers, sender = self.generate(referral_case(), reference, fact_findings=[
                    {'fact_id':'purpose','verdict':'ambiguous','reason':'Synthetic independent unresolved review.'}])
                self.assert_held(answers['purpose'])
                self.assertEqual(answers['modality']['status'], 'supported')
                self.assertEqual(len(sender.calls), 3)

    def test_v7_uses_v6_prompts_and_schema_without_new_provider_roles(self):
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                case = referral_case(exact=True)
                old, old_sender = self.generate(case, reference, semantic.SOURCE_BINDING_SCOPE_CONTRACT)
                current, current_sender = self.generate(case, reference)
                self.assertEqual(len(old_sender.calls), 3)
                self.assertEqual(len(current_sender.calls), 3)
                for old_call,new_call in zip(old_sender.calls,current_sender.calls):
                    self.assertEqual(old_call[:2], new_call[:2])
                    self.assertEqual(old_call[3:], new_call[3:])
                    restored = deepcopy(new_call[2])
                    restored['fact_scope_contract'] = semantic.SOURCE_BINDING_SCOPE_CONTRACT
                    self.assertEqual(old_call[2], restored)
                self.assertEqual([a['status'] for a in old.values()], [a['status'] for a in current.values()])
