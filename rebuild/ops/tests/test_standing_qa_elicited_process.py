"""Offline controls for the generic process and its qualified elicited sends."""
from copy import deepcopy
import dataclasses
import io
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as relations
from ops import provider_campaign as pc, standing_qa as st, standing_qa_elicited as elicited


CANONICAL = Path(__file__).parents[3] / 'docs/foundation/mutations/20261004-quillmd-v1-standing-api-testing-5.md'
# Standalone ops discovery has settings but no Django application registry. Keep
# this process-only fixture independent of core workflow tests and their models.
SONNET_55_DEFAULT = dict(AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL=g.SONNET_5_5,
                        AI_INPUT_RATE='2', AI_OUTPUT_RATE='10', AI_CACHED_RATE='0.20',
                        AI_EFFORT='medium', AI_INFERENCE_GEO='', V3_FIELD_RELATIONS=False,
                        V3_HISTORY_CONTEXT=False, V3_GENERATION_BATCHES=False)


@override_settings(**dict(SONNET_55_DEFAULT, AI_THINKING='between_tools', V3_FIELD_RELATIONS_SWITCH=False,
                         SYNTHETIC_ONLY=True, QUILLMD_DATA_MODE='synthetic',
                         **st.expected_settings(elicited.STAGE)))
class ElicitedProcessPricing(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        # Materialize settings before SimpleTestCase applies the class override;
        # standalone unittest has not configured them through manage.py.
        settings.AI_MODE
        super().setUpClass()

    def setUp(self):
        self.declaration = st.declared_standing(CANONICAL, uses=('live',), out=io.StringIO())
        # Retain deterministic blank forms for inspection; no credential, database or provider is used.
        parent = os.environ.get('QUILLMD_OPS_PURE_DIR')
        self.root = (Path(parent) / self._testMethodName if parent else
                     Path(tempfile.mkdtemp(prefix='quillmd-elicited-offline-')))
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.environment = patch.dict(os.environ, {'QUILLMD_DEEPGRAM_RATE_PER_MINUTE': '0.0043',
            'QUILLMD_DEEPGRAM_RATE_PER_SECOND': '', 'QUILLMD_PROVIDER_DISCOUNT_RATE': '0'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.state = override_settings(STATE_DIR=self.root / 'qa-state', MEDIA_ROOT=self.root / 'qa-state/files')
        self.state.enable()
        self.addCleanup(self.state.disable)
        self.inputs = elicited.frozen_inputs()
        self.send = elicited.plan_sends(self.inputs)[0]

    def snapshot(self):
        snapshot = st.settings_snapshot(elicited.STAGE)
        # The pure checker is given the declared isolated database address; it never connects.
        snapshot['database'] = {'NAME': self.declaration.qa_database,
                                'HOST': st.QA_SERVER['host'], 'PORT': st.QA_SERVER['port']}
        return snapshot

    def prices(self, declaration=None):
        return elicited.price_sends([self.send], self.inputs, self.root,
                                   declaration or self.declaration, self.declaration.limits())

    def test_generic_process_admits_then_compiles_the_exact_qualified_send(self):
        snapshot = self.snapshot()
        self.assertEqual(snapshot['pricing_version'], self.declaration.pricing_version('ordinary_notes'))
        self.assertEqual(snapshot['request_profile']['max_output_tokens'], 8000)
        self.assertEqual(st.check_configuration(snapshot, self.declaration, elicited.STAGE, self.root), [])
        priced = self.prices()[self.send.id]
        case = self.inputs['elicited']['cases'][0]
        fields = self.inputs['elicited']['forms'][self.send.form]['fields']
        with override_settings(**elicited.stages.steps.PATH_FLAGS['field_relations']):
            config = g.configuration(fields)
            compiled = relations.compile_request(case['notes'], fields, config)
            wire = compiled['wire']
            self.assertEqual(config['ordinary_field_contract'], 'ordinary-field-relations-v4')
            self.assertEqual(config['pricing_version'], self.declaration.pricing_version(elicited.PRICING))
            self.assertEqual(wire['model'], self.declaration.model)
            self.assertEqual(wire['max_tokens'], 20000)
            self.assertEqual(wire['thinking'], {'type': 'between_tools'})
            self.assertEqual(wire['output_config']['effort'], 'medium')
            self.assertEqual(wire['output_config']['format']['schema'],
                             relations.response_schema(compiled['asked'], compiled['units']))
            self.assertEqual(priced['maximum_cost'], g.maximum_cost(case['notes'], fields, config))
        self.assertEqual(priced['max_output_tokens'], 20000)
        self.assertEqual(priced['pricing_version'], self.declaration.pricing_version(elicited.PRICING))
        self.assertEqual(g.configuration()['request_profile']['max_output_tokens'], 8000)

    def test_wrong_process_price_and_global_contract_flag_still_refuse(self):
        for key, value in [('pricing_version', self.declaration.pricing_version(elicited.PRICING)),
                           ('settings', {**self.snapshot()['settings'], 'V3_FIELD_RELATIONS': True})]:
            with self.subTest(key=key):
                bad = deepcopy(self.snapshot())
                bad[key] = value
                self.assertTrue(st.check_configuration(bad, self.declaration, elicited.STAGE, self.root))

    def test_wrong_qualified_price_or_eight_thousand_token_profile_still_refuse(self):
        wrong = dataclasses.replace(self.declaration, pricing_versions=tuple(
            (key, self.declaration.pricing_version('ordinary_notes') if key == elicited.PRICING else value)
            for key, value in self.declaration.pricing_versions))
        with self.assertRaisesMessage(pc.Refused, 'elicited quote/profile differs'):
            self.prices(wrong)
        actual = g.configuration

        def wrong_profile(*args, **kwargs):
            config = actual(*args, **kwargs)
            config['request_profile'] = {**config['request_profile'], 'max_output_tokens': 8000}
            return config

        with patch.object(g, 'configuration', side_effect=wrong_profile), self.assertRaisesMessage(
                pc.Refused, 'qualified Sonnet 5.5 ordinary-v4 profile'):
            self.prices()
        with self.assertRaises(pc.Refused):
            elicited.send_inputs(dataclasses.replace(self.send, path='default', pricing_key='ordinary_notes'),
                                 self.inputs)

    def test_caller_flag_cannot_replace_the_normal_scrubbed_process_flags(self):
        (self.root / 'tmp').mkdir(mode=0o700, exist_ok=True)
        door = {'declaration': str(CANONICAL), 'commit': self.declaration.commit}
        with patch.dict(os.environ, {'QUILLMD_V3_FIELD_RELATIONS': '1'}), patch.object(
                st, 'signing_identity', return_value=(None, None)):
            environment = st.request_environment('unused-synthetic-key', self.declaration, self.root,
                'unused-synthetic-password', {}, st.stage_flags(elicited.STAGE, self.declaration), door)
        self.assertEqual(environment['QUILLMD_V3_FIELD_RELATIONS'], '0')
        self.assertEqual(environment['QUILLMD_AI_THINKING'], 'between_tools')
        self.assertEqual(environment['QUILLMD_AI_MODEL'], self.declaration.model)
