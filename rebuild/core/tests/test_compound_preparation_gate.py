"""Pure preparation gate integration; no database, provider or document mutation."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from django.core.exceptions import ValidationError
from core import word_contract
from documents import semantic_preparation_roles as roles
from documents.test_compound_answer_contract import definition_case


class CompoundPreparationGateTests(unittest.TestCase):
    def prep(self, contract=roles.COMPOUND_ANSWER_CONTRACT, *, label='Patient full name and clinic record number'):
        fields, values = definition_case(label)
        config = {word_contract.CONFIG_KEY: word_contract.PROFILE}
        if contract is not None:
            config[roles.MEANING_CONTRACT_KEY] = contract
        responses = {role: {'answer_definitions': {'fields': [{
            'field_key': 'answer', 'definition': deepcopy(values['answer']),
            'state': 'proposed' if role == 'proposal' else 'pass',
            'reason': 'Both requested values are documented by this blank question.'}]}}
            for role in ('proposal', 'checker')}
        prep = SimpleNamespace(config=config, inventory={'fields': fields, 'inventory_sha256': 'a'*64},
            candidate_info={'fields': deepcopy(fields)}, corrections={}, **responses)
        return prep, values

    def test_model_agreement_and_review_checkboxes_cannot_seal_atomic_compound(self):
        prep, values = self.prep()
        before = deepcopy(prep.__dict__)
        with patch.object(word_contract, 'proposed', return_value=values):
            self.assertEqual(set(word_contract.approval_issues(prep)), {'answer'})
            row = word_contract.review_rows(prep)[0]
            self.assertEqual(row['state'], 'unresolved')
            self.assertIn('multiple independent values', row['reason'])
            with self.assertRaises(ValidationError):
                word_contract.seal(prep, ['answer'], SimpleNamespace(pk='synthetic-reviewer'))
        self.assertEqual(prep.__dict__, before)

    def test_reviewed_correction_must_resolve_mode_and_preserves_proposals(self):
        prep, values = self.prep()
        prep.corrections = {'answer_definitions': deepcopy(values)}
        before_roles = deepcopy((prep.proposal, prep.checker))
        with patch.object(word_contract, 'proposed', return_value=values):
            self.assertEqual(set(word_contract.approval_issues(prep)), {'answer'})
            values['answer']['answer_mode'] = 'narrative'
            prep.corrections['answer_definitions'] = deepcopy(values)
            self.assertEqual(word_contract.approval_issues(prep), {})
            word_contract.seal(prep, ['answer'], SimpleNamespace(pk='synthetic-reviewer'))
        self.assertEqual(prep.candidate_info[word_contract.INFO_KEY]['definitions'], values)
        self.assertEqual((prep.proposal, prep.checker), before_roles)
        self.assertEqual(prep.candidate_info['fields'], prep.inventory['fields'])

    def test_legacy_approvals_and_generation_gate_do_not_acquire_new_requirement(self):
        for contract in (None, roles.COMPOSITE_MEANING_CONTRACT):
            prep, values = self.prep(contract)
            with patch.object(word_contract, 'proposed', return_value=values):
                self.assertEqual(word_contract.approval_issues(prep), {})
                word_contract.require_resolved(prep, generation=True)
                word_contract.seal(prep, ['answer'], SimpleNamespace(pk='synthetic-reviewer'))
            self.assertEqual(prep.candidate_info[word_contract.INFO_KEY]['definitions'], values)

    def test_new_contract_generation_refusal_leaves_prior_record_unchanged(self):
        prep, values = self.prep()
        before = deepcopy(prep.__dict__)
        with patch.object(word_contract, 'proposed', return_value=values):
            with self.assertRaisesRegex(ValidationError, 'new answer-definition version'):
                word_contract.require_resolved(prep, generation=True)
        self.assertEqual(prep.__dict__, before)

    def test_distinct_identity_owners_and_birth_date_cannot_seal_atomic(self):
        for label in ('Patient full name and clinician full name', 'Patient name and doctor name',
                      'Patient name and date of birth', 'Patient name and guardian name'):
            with self.subTest(label=label):
                prep, values = self.prep(label=label)
                before = deepcopy(prep.__dict__)
                with patch.object(word_contract, 'proposed', return_value=values):
                    self.assertEqual(set(word_contract.approval_issues(prep)), {'answer'})
                    with self.assertRaises(ValidationError):
                        word_contract.seal(prep, ['answer'], SimpleNamespace(pk='synthetic-reviewer'))
                    self.assertEqual(prep.__dict__, before)
                    values['answer']['answer_mode'] = 'narrative'
                    word_contract.seal(prep, ['answer'], SimpleNamespace(pk='synthetic-reviewer'))
                self.assertEqual(prep.candidate_info[word_contract.INFO_KEY]['definitions'], values)

    def test_narrative_mode_does_not_seal_an_explicit_component_exclusion(self):
        prep, values = self.prep()
        values['answer'].update(answer_mode='narrative',
            meaning='Only the patient full name. Exclude all identifiers.')
        before = deepcopy(prep.__dict__)
        with patch.object(word_contract, 'proposed', return_value=values):
            self.assertEqual(set(word_contract.approval_issues(prep)), {'answer'})
            with self.assertRaises(ValidationError):
                word_contract.seal(prep, ['answer'], SimpleNamespace(pk='synthetic-reviewer'))
            self.assertEqual(prep.__dict__, before)
            values['answer']['meaning'] = 'Only the patient full name and clinic record number.'
            word_contract.seal(prep, ['answer'], SimpleNamespace(pk='synthetic-reviewer'))
        self.assertEqual(prep.candidate_info[word_contract.INFO_KEY]['definitions'], values)


if __name__ == '__main__':
    unittest.main()
