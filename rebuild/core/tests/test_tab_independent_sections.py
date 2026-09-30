"""Cross-section prompt contract, with mocked provider responses only."""
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import generation as g
from core.tests.test_natural_tab_generation import NOTES, ORIGINAL
from documents.engine import docx_inspect


@override_settings(AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL='claude-sonnet-4-6',
                   AI_INPUT_RATE='1', AI_OUTPUT_RATE='5', AI_CACHED_RATE='0.1')
class IndependentSectionPromptTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fields = docx_inspect(ORIGINAL)[3]
        cls.keys = {field['label']: field['key'] for field in cls.fields}

    def mocked_generation(self, selections=None, version=None):
        config = g.configuration()
        if version:
            config['prompt_version'] = version
        selections = selections or {}
        response = SimpleNamespace(
            usage=SimpleNamespace(input_tokens=1, output_tokens=1), stop_reason='end_turn',
            content=[SimpleNamespace(type='text', text=json.dumps({'fields': [
                {'key': field['key'], 'unit_ids': selections.get(field['label'], []), 'conflict': False}
                for field in self.fields]}))], _request_id='isolated-no-provider')
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.return_value = response
            raw, *_ = g.generate(NOTES, self.fields, config)
            sent = client.return_value.messages.create.call_args.kwargs
        return raw, sent, config

    def test_the_current_instruction_cannot_change_without_a_version_bump(self):
        """⚠️ THE TRIPWIRE THIS FILE THOUGHT IT HAD, AND DID NOT.

        The assertion below used to read `config['prompt_version'] == CURRENT_PROMPT_VERSION`,
        with a comment explaining that a literal would turn a required bump into a failure.
        That is backwards: `configuration()` SETS that key from that constant, so the assertion
        compared the constant to itself and could never fail. The refutation pass inserted a
        whole sentence into the v5/v6 paragraph with no bump and the suite stayed green — which
        is precisely the relabelling the v6 bump was justified by.

        A literal version and a digest of the exact text sent. Editing the instruction now
        fails HERE, and the repair is to bump the version and re-pin, deliberately.
        """
        _, sent, config = self.mocked_generation()
        # Re-pinned deliberately (2026-09-30, L3:R3-1): v7 adds only the printed question context, which this form's
        # questions do not carry, so the text sent is byte for byte v6's.
        self.assertEqual(config['prompt_version'], 'extractive-v7-question-context')
        self.assertEqual(hashlib.sha256(sent['system'].encode()).hexdigest(),
                         '476768227326ce344dfe791dbbef0545da87ddd31ed037cf14aa308a78a16358')

    def test_new_prompt_clarifies_partial_description_and_independent_reuse(self):
        _, sent, config = self.mocked_generation()
        self.assertIn('independently applicable fields in different sections', sent['system'])
        self.assertIn('do not leave those steps out because other details are missing', sent['system'])
        self.assertIn('never invent the remaining steps', sent['system'])
        self.assertIn('does not permit duplicate statements in numbered slots', sent['system'])
        self.assertIn('borrowing a value from another explicitly labelled question', sent['system'])

    def test_queued_v4_prompt_payload_and_schema_remain_byte_identical(self):
        old, sent, old_config = self.mocked_generation(version='extractive-v4-tab-evidence-units')
        # Captured from qualified b6b40b02 before this repair; this guards queued jobs.
        self.assertEqual(hashlib.sha256(sent['system'].encode()).hexdigest(),
                         '9288d5029974e865b04cedf04cbe354c039e080bc9698c2cc170a18eaf0ba99e')
        self.assertEqual(hashlib.sha256(sent['messages'][0]['content'].encode()).hexdigest(),
                         'b52d6977054caddc33748989871ea4cd2f924b86f9d6732a9aea8e1cdbf4c7e4')
        self.assertIn('UnitSelection', sent['output_config']['format']['schema']['$defs'])
        self.assertEqual(old['evidence_contract'], g.TAB_CONTRACT)
        self.assertEqual(old_config['pricing_version'], g.configuration()['pricing_version'])
        fixture_config = {**old_config, 'mode': 'fixture'}
        fixture, *_ = g.generate('PATIENT NAME: Synthetic Example', self.fields, fixture_config)
        self.assertEqual(fixture[self.keys['PATIENT NAME']]['text'], 'Synthetic Example')

    def test_one_complete_unit_can_answer_extent_and_partial_procedure_without_fabrication(self):
        units, _ = g.source_units(NOTES, self.fields)
        self.assertEqual(units[9]['quote'], 'The scope was advanced to the cecum.')
        raw, _, _ = self.mocked_generation({
            'EXTENT OF EXAMINATION': [10], 'DESCRIPTION OF PROCEDURE': [10]})
        answers = g.validated(raw)
        expected = {'quote': units[9]['quote'], 'start': units[9]['start'], 'end': units[9]['end']}
        for label in ('EXTENT OF EXAMINATION', 'DESCRIPTION OF PROCEDURE'):
            answer = answers[self.keys[label]]
            self.assertEqual(answer['status'], 'supported')
            self.assertEqual(answer['text'], 'The scope was advanced to the cecum.')
            self.assertEqual(answer['evidence'], [expected])
            self.assertFalse(answer['reviewed'])
        self.assertEqual(sum(answer['status'] == 'supported' for answer in answers.values()), 2)
        # Four physical lines still represent one logical procedure answer.
        description = next(field for field in self.fields if field['label'] == 'DESCRIPTION OF PROCEDURE')
        self.assertEqual(len(description['locator']['tab_form']['anchors']), 4)

    def test_omitted_procedure_stays_missing_and_does_not_rewrite_provider_response(self):
        # Minimal counterpart of the retained first live omission. The repair changes
        # future instructions; it must not retrofit or conceal a missing model selection.
        raw, _, _ = self.mocked_generation({'EXTENT OF EXAMINATION': [10]})
        original_response = raw['anthropic_response'].content[0].text
        answers = g.validated(raw)
        self.assertEqual(answers[self.keys['EXTENT OF EXAMINATION']]['status'], 'supported')
        self.assertEqual(answers[self.keys['DESCRIPTION OF PROCEDURE']],
                         {'text': '', 'status': 'missing', 'evidence': [], 'reviewed': False})
        self.assertEqual(raw['anthropic_response'].content[0].text, original_response)

    def test_reuse_within_numbered_group_is_still_refused(self):
        raw, _, _ = self.mocked_generation({
            'POSTOPERATIVE FINDINGS — 1': [13], 'POSTOPERATIVE FINDINGS — 2': [13]})
        with self.assertRaisesRegex(ValidationError, 'multiple numbered items in the same section'):
            g.validated(raw)
