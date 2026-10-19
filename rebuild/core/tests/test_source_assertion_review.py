"""Manual review keeps immutable generated lineage and complete signed history."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import semantic_review as review
from core.tests.test_source_assertion_graph import base_case, run_case


@override_settings(SECRET_KEY='synthetic-review-proof-key', SECRET_KEY_FALLBACKS=[])
class SourceAssertionReviewTests(SimpleTestCase):
    def setUp(self):
        case = base_case()
        self.notes, fields, self.definitions, *_ = case
        self.field = fields[0]
        output, _ = run_case(case)
        self.generated = output['answers'][self.field['key']]
        self.interpretation = output['interpretation']
        self.encounter = SimpleNamespace(notes=self.notes, status='review', department=object())
        self.actor = SimpleNamespace(pk=UUID('20000000-0000-4000-8000-000000000001'))
        self.store = self.enterContext(patch('core.source_interpretation_store.load_for_answer',
            return_value=deepcopy(self.interpretation)))
        self.enterContext(patch.object(review, 'membership'))

    def save(self, previous=None, text='Explicit synthetic clinician answer.', revision=1, **options):
        return review.save_answer(self.encounter, self.field,
            self.generated if previous is None else previous, text, self.actor,
            options.pop('reviewed', True), options.pop('blank', False), revision,
            self.definitions, **options)

    def validate(self, answer):
        return review.validate_answer(self.encounter, self.field, answer, self.definitions)

    def test_generated_and_two_manual_edits_retain_complete_prior_content(self):
        self.assertEqual(self.validate(self.generated), self.generated)
        first = self.save()
        second = self.save(first, 'Second explicit synthetic answer.', 2)
        self.assertEqual(self.validate(second), second)
        self.assertEqual(second['semantic_edit_history'][0]['previous'], self.generated)
        self.assertEqual(second['semantic_edit_history'][1]['previous'],
            {k: v for k, v in first.items() if k != 'semantic_edit_history'})
        self.assertEqual(len(second['semantic_edit_history']), 2)

    def test_v4_cannot_downgrade_or_delete_its_contract_to_bypass_store(self):
        answer = self.save()
        for marker in ('fact_scope_contract', 'source_interpretation'):
            with self.subTest(marker=marker):
                changed = deepcopy(answer); changed.pop(marker)
                with self.assertRaises(ValidationError): self.validate(changed)

    def test_history_and_current_content_cannot_be_erased_or_changed(self):
        first = self.save()
        twice = self.save(first, 'Second explicit synthetic answer.', 2)
        variants = []
        changed = deepcopy(first)
        changed['semantic_edit_history'][0]['previous'] = {'source_interpretation':first['source_interpretation']}
        variants.append(changed)
        changed = deepcopy(twice); changed['semantic_edit_history'][0] = {'deleted_history':True}; variants.append(changed)
        changed = deepcopy(first); changed['text'] = changed['value'] = 'Forged replacement.'; variants.append(changed)
        changed = deepcopy(first); changed['reviewed_by'] = str(UUID(int=1)); variants.append(changed)
        changed = deepcopy(first); changed['review_revision'] = False; variants.append(changed)
        changed = deepcopy(first); changed.pop('semantic_manual_proof'); variants.append(changed)
        for answer in variants:
            with self.subTest(answer=answer):
                with self.assertRaises(ValidationError): self.validate(answer)

    def test_manual_proof_supports_explicit_blank_then_replacement_and_review_change(self):
        blank = self.save(text='', blank=True)
        self.assertEqual(self.validate(blank), blank)
        replacement = self.save(blank, 'Explicit replacement for the reviewed blank.', 2)
        self.assertEqual(self.validate(replacement), replacement)
        self.assertNotIn('blank_decision', replacement)
        unreviewed = self.save(replacement, replacement['text'], 3, reviewed=False)
        self.assertEqual(self.validate(unreviewed), unreviewed)
        self.assertIsNone(unreviewed['review_revision'])
        reviewed = self.save(unreviewed, unreviewed['text'], 4)
        self.assertEqual(self.validate(reviewed), reviewed)
        self.assertEqual(reviewed['review_revision'], 4)
        self.assertEqual(len(reviewed['semantic_edit_history']), 2)

    def test_document_level_edit_is_not_a_field_approval(self):
        answer = self.save(document_level=True)
        self.assertNotIn('reviewed', answer)
        self.assertNotIn('reviewed_by', answer)
        self.assertEqual(self.validate(answer), answer)

    def test_invalid_previous_answer_cannot_be_resigned_by_a_new_edit(self):
        first = self.save(); first['semantic_edit_history'][0]['previous'] = {}
        with self.assertRaises(ValidationError): self.save(first, 'Next answer.', 2)

    def test_proof_retains_validity_during_standard_signing_key_rotation(self):
        answer = self.save()
        with override_settings(SECRET_KEY='synthetic-next-key', SECRET_KEY_FALLBACKS=['synthetic-review-proof-key']):
            self.assertEqual(self.validate(answer), answer)
        with override_settings(SECRET_KEY='synthetic-next-key', SECRET_KEY_FALLBACKS=[]):
            with self.assertRaises(ValidationError): self.validate(answer)

    def test_malformed_proof_is_a_validation_refusal(self):
        for proof in (None, 42, {}, 'not-signed'):
            answer = self.save(); answer['semantic_manual_proof'] = proof
            with self.subTest(proof=proof):
                with self.assertRaises(ValidationError): self.validate(answer)
