"""A complete mixed assessment retains both meanings without broadening old contracts."""
from copy import deepcopy
import hashlib
import json

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import semantic_generation as semantic
from core.tests.test_semantic_generation import FixtureSender, assignments, fact
from documents.semantic_preparation_roles import default_definitions


MIXED = 'no current gastrointestinal symptoms and a family history of colon polyps'
PREFIX = "The clinician's impression was "
REFERENCES = (semantic.LEGACY_REFERENCE_CONTRACT, semantic.REFERENCE_INVENTORY_CONTRACT)
HISTORICAL_SCOPES = (semantic.LEGACY_SCOPE_CONTRACT, semantic.POSITIONED_SCOPE_CONTRACT,
                     semantic.DURATION_SCOPE_CONTRACT, semantic.FAMILY_SCOPE_CONTRACT)
# Canonical schema bytes from installed baseline 053a156f, before mixed was added.
HISTORICAL_SCHEMA_SHA256 = {
    'FACT_SCHEMA': 'b149df29e842d82c2ce7bd801aebbc62c33d8d90dfa212fcd2b22bee6f902443',
    'API_FACT_SCHEMA': '08d11fcf4e2cc0d89a559181adee19c9fecfe22f008d5df1e40c7966498418f7',
    'API_FACT_INVENTORY_SCHEMA': '151b38a909b05d15bf97d64445214a49ae74b67f580f77deeb948e34cb915549',
    'ASSIGN_SCHEMA': '82ec5b269d0d8f84a31435cf5c055ca3b3604ef0dc558de20611ad5e530f57a7',
    'CHECK_SCHEMA': '624e0289f7058770e1d0a00b3c7fb66a6ad29c100125f0faa390f6c07395d3b9',
}


def schema_digest(schema):
    return hashlib.sha256(json.dumps(schema, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


class SourceContextMixedAssessmentTests(SimpleTestCase):
    def prepare(self, notes=None, quote=MIXED, *, polarity='mixed', kind='assessment'):
        notes = PREFIX + MIXED + '.' if notes is None else notes
        fields = [{'key': 'impression', 'label': 'Impression', 'kind': 'text', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        definitions['impression'].update(version=2, answer_mode='atomic')
        definitions['impression']['scope'].update(subject='patient', temporality='any', polarity='any')
        values = [fact(notes, fields, 'assessment', quote, kind=kind,
                       concept='clinical impression', polarity=polarity)]
        return notes, fields, definitions, values

    def generate(self, prepared, *, selected=('assessment',), reference=semantic.REFERENCE_INVENTORY_CONTRACT,
                 scope=semantic.SOURCE_CONTEXT_SCOPE_CONTRACT):
        notes, fields, definitions, values = prepared
        original = deepcopy(values)
        sender = FixtureSender(values, assignments(fields, {'impression': selected}))
        answer = semantic.run(notes, fields, definitions, sender,
                              reference_contract=reference, scope_contract=scope)['impression']
        self.assertEqual(values, original)
        self.assertEqual([call[:2] for call in sender.calls],
                         [('extractor', 1), ('assigner', 1), ('checker', 1)])
        self.assertEqual([f['id'] for f in answer['facts']], [f['id'] for f in values])
        semantic.validate_stored_answer(notes, fields[0], definitions['impression'], answer)
        return answer, sender

    def assert_held(self, answer):
        self.assertEqual(answer['status'], 'conflict')
        self.assertEqual(answer['text'], '')
        self.assertFalse(answer['reviewed'])
        self.assertTrue(answer['review_reasons'])

    def test_one_atomic_mixed_assessment_retains_both_components_and_round_trips(self):
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                prepared = self.prepare()
                answer, sender = self.generate(prepared, reference=reference)
                self.assertEqual((answer['status'], answer['text']), ('supported', MIXED.capitalize()))
                self.assertEqual(answer['fact_ids'], ['assessment'])
                self.assertEqual(prepared[2]['impression']['answer_mode'], 'atomic')
                retained = answer['facts'][0]
                self.assertEqual(retained['polarity'], 'mixed')
                self.assertEqual(retained['value_evidence']['quote'], MIXED)
                self.assertEqual(retained['issues'], [])
                self.assertFalse(answer['reviewed'])
                offered = sender.calls[0][3]['properties']['facts']['items']['properties']['polarity']['enum']
                self.assertIn('mixed', offered)

    def test_historical_profiles_reject_mixed_before_assignment(self):
        for scope in HISTORICAL_SCOPES:
            for reference in REFERENCES:
                with self.subTest(scope=scope, reference=reference):
                    notes, fields, definitions, values = self.prepare()
                    sender = FixtureSender(values, assignments(fields, {'impression': ['assessment']}))
                    with self.assertRaises(ValidationError):
                        semantic.run(notes, fields, definitions, sender,
                                     reference_contract=reference, scope_contract=scope)
                    self.assertEqual([call[:2] for call in sender.calls], [('extractor', 1)])
                    offered = sender.calls[0][3]['properties']['facts']['items']['properties']['polarity']['enum']
                    self.assertNotIn('mixed', offered)

    def test_complete_mixed_assessment_cannot_be_flattened_to_one_polarity(self):
        for polarity in ('affirmed', 'negated'):
            for reference in REFERENCES:
                with self.subTest(polarity=polarity, reference=reference):
                    answer, _ = self.generate(self.prepare(polarity=polarity), reference=reference)
                    self.assert_held(answer)

    def test_historical_request_schemas_keep_their_baseline_bytes(self):
        for name, expected in HISTORICAL_SCHEMA_SHA256.items():
            self.assertEqual(schema_digest(getattr(semantic, name)), expected, name)
        for scope in HISTORICAL_SCOPES:
            for reference in REFERENCES:
                with self.subTest(scope=scope, reference=reference):
                    prepared = self.prepare('The patient reports normal bowel movements.',
                                            'normal bowel movements', polarity='affirmed', kind='finding')
                    _, sender = self.generate(prepared, scope=scope, reference=reference)
                    schema_name = ('API_FACT_SCHEMA' if reference == semantic.LEGACY_REFERENCE_CONTRACT
                                   else 'API_FACT_INVENTORY_SCHEMA')
                    self.assertEqual([schema_digest(call[3]) for call in sender.calls],
                        [HISTORICAL_SCHEMA_SHA256[name] for name in (schema_name, 'ASSIGN_SCHEMA', 'CHECK_SCHEMA')])
                    self.assertEqual(sender.calls[0][4], semantic.EXTRACT_INSTRUCTIONS
                        if reference == semantic.LEGACY_REFERENCE_CONTRACT else semantic.EXTRACT_INVENTORY_INSTRUCTIONS)

    def test_mixed_cannot_populate_nontext_or_single_polarity_destinations(self):
        for reference in REFERENCES:
            for value_type in ('integer', 'number', 'date', 'choice', 'person_name', 'identifier'):
                with self.subTest(reference=reference, value_type=value_type):
                    prepared = self.prepare()
                    definition = prepared[2]['impression']
                    definition['value_type'] = value_type
                    if value_type == 'choice':
                        definition['choices'] = [MIXED.capitalize()]
                    answer, _ = self.generate(prepared, reference=reference)
                    self.assert_held(answer)
            for polarity in ('positive', 'negative'):
                with self.subTest(reference=reference, polarity=polarity):
                    prepared = self.prepare()
                    prepared[2]['impression']['scope']['polarity'] = polarity
                    answer, _ = self.generate(prepared, reference=reference)
                    self.assert_held(answer)

    def test_clipped_relationship_or_disease_only_is_not_a_complete_mixed_assessment(self):
        for quote in ('no current gastrointestinal symptoms', 'family history of colon polyps', 'colon polyps'):
            for reference in REFERENCES:
                with self.subTest(quote=quote, reference=reference):
                    answer, _ = self.generate(self.prepare(quote=quote), reference=reference)
                    self.assert_held(answer)

    def test_other_ownership_uncertainty_and_source_governance_remain_held(self):
        statements = (
            PREFIX + 'no current gastrointestinal symptoms and a family history of colon polyps in another patient.',
            PREFIX + "no current gastrointestinal symptoms and the doctor's own family history of colon polyps.",
            PREFIX + 'possibly ' + MIXED + '.',
            PREFIX + MIXED + ' remains unconfirmed.',
            'If ' + PREFIX.lower() + MIXED + ', further review would be needed.',
            '"' + PREFIX + MIXED + '."',
            PREFIX + MIXED + '?',
            'The patient denies that the impression was ' + MIXED + '.',
        )
        for notes in statements:
            # Preserve the complete offered wording where an owner or qualifier
            # is inside the value; clipping the qualifier is tested separately.
            quote = notes[notes.index('no current'):].rstrip('.?"')
            for reference in REFERENCES:
                with self.subTest(notes=notes, reference=reference):
                    answer, _ = self.generate(self.prepare(notes, quote), reference=reference)
                    self.assert_held(answer)

    def test_mixed_is_not_a_generic_label_for_other_compound_clinical_findings(self):
        for phrase in ('no abdominal pain and normal bowel movements',
                       'no evidence of gastrointestinal symptoms and a family history of colon polyps',
                       'no knowledge of gastrointestinal symptoms and a family history of colon polyps',
                       'no confirmation of gastrointestinal symptoms and a family history of colon polyps'):
            for reference in REFERENCES:
                with self.subTest(phrase=phrase, reference=reference):
                    answer, _ = self.generate(self.prepare(PREFIX + phrase + '.', phrase), reference=reference)
                    self.assert_held(answer)

    def test_a_denied_or_unestablished_family_component_cannot_be_asserted_as_positive(self):
        for qualification in ('was denied', 'is not confirmed', 'has not been established',
                              'was not denied', 'was ruled out', 'requires further verification'):
            notes = PREFIX + MIXED + ' ' + qualification + '.'
            for quote in (MIXED, MIXED + ' ' + qualification):
                for reference in REFERENCES:
                    with self.subTest(qualification=qualification, clipped=quote == MIXED, reference=reference):
                        answer, _ = self.generate(self.prepare(notes, quote), reference=reference)
                        self.assert_held(answer)

    def test_uncertain_family_diagnosis_does_not_become_an_affirmed_component(self):
        for qualification in ('unproven', 'probable', 'likely', 'questionable', 'presumed'):
            phrase = ('no current gastrointestinal symptoms and a family history of '
                      + qualification + ' colon polyps')
            for reference in REFERENCES:
                with self.subTest(qualification=qualification, reference=reference):
                    answer, _ = self.generate(self.prepare(PREFIX + phrase + '.', phrase), reference=reference)
                    self.assert_held(answer)
                    self.assertEqual(answer['facts'][0]['value_evidence']['quote'], phrase)
        notes = PREFIX + MIXED + ' in question.'
        for quote in (MIXED, MIXED + ' in question'):
            for reference in REFERENCES:
                with self.subTest(qualification='in question', clipped=quote == MIXED, reference=reference):
                    answer, _ = self.generate(self.prepare(notes, quote), reference=reference)
                    self.assert_held(answer)

    def test_affirmed_and_negated_peers_cannot_silently_replace_a_mixed_assessment(self):
        for polarity, phrase in (('affirmed', 'current gastrointestinal symptoms'),
                                 ('negated', 'no current gastrointestinal symptoms')):
            notes = PREFIX + MIXED + '. ' + PREFIX + phrase + '.'
            for reference in REFERENCES:
                for selected in ('assessment', 'peer'):
                    with self.subTest(polarity=polarity, reference=reference, selected=selected):
                        prepared = self.prepare(notes)
                        prepared[3].append(fact(notes, prepared[1], 'peer', phrase, kind='assessment',
                            concept='clinical impression', polarity=polarity, occurrence=1))
                        answer, _ = self.generate(prepared, selected=(selected,), reference=reference)
                        self.assert_held(answer)
                        self.assertEqual({f['id'] for f in answer['facts']}, {'assessment', 'peer'})

    def test_an_unrelated_documented_fact_does_not_block_the_mixed_assessment(self):
        notes = PREFIX + MIXED + '. The patient currently feels well.'
        prepared = self.prepare(notes)
        prepared[3].append(fact(notes, prepared[1], 'wellbeing', 'currently feels well',
                               concept='current wellbeing', kind='history'))
        answer, _ = self.generate(prepared)
        self.assertEqual((answer['status'], answer['text']), ('supported', MIXED.capitalize()))

    def test_corrections_involving_mixed_in_either_direction_retain_both_facts_for_review(self):
        for mixed_first in (True, False):
            first, second = (MIXED, 'no current gastrointestinal symptoms') if mixed_first else (
                'no current gastrointestinal symptoms', MIXED)
            notes = PREFIX + first + '. Correction: ' + PREFIX.lower() + second + '.'
            for reference in REFERENCES:
                for selected in ('original', 'replacement'):
                    with self.subTest(mixed_first=mixed_first, reference=reference, selected=selected):
                        prepared = self.prepare(notes, first, polarity='mixed' if mixed_first else 'negated')
                        prepared[3][0]['id'] = 'original'
                        prepared[3].append(fact(notes, prepared[1], 'replacement', second,
                            kind='assessment', concept='clinical impression',
                            polarity='negated' if mixed_first else 'mixed',
                            occurrence=1 if mixed_first else 0, supersedes=('original',)))
                        answer, _ = self.generate(prepared, selected=(selected,), reference=reference)
                        self.assert_held(answer)
                        retained = {f['id']: f for f in answer['facts']}
                        self.assertEqual(set(retained), {'original', 'replacement'})
                        self.assertEqual(retained['replacement']['supersedes'], ['original'])
                        self.assertTrue(retained['original']['issues'])
                        self.assertTrue(retained['replacement']['issues'])
                        self.assertNotIn('This fact was explicitly corrected by later source documentation.',
                                         answer['review_reasons'])

    def test_stored_mixed_proof_cannot_be_relabelled_or_downgraded(self):
        prepared = self.prepare()
        answer, _ = self.generate(prepared)
        for polarity in ('affirmed', 'negated'):
            changed = deepcopy(answer)
            changed['facts'][0]['polarity'] = polarity
            with self.subTest(polarity=polarity), self.assertRaises(ValidationError):
                semantic.validate_stored_answer(prepared[0], prepared[1][0], prepared[2]['impression'], changed)
        for scope in HISTORICAL_SCOPES:
            changed = deepcopy(answer)
            changed['fact_scope_contract'] = scope
            with self.subTest(scope=scope), self.assertRaises(ValidationError):
                semantic.validate_stored_answer(prepared[0], prepared[1][0], prepared[2]['impression'], changed)
