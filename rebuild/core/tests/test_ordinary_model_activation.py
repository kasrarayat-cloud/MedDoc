"""The prepared profile is selected by the application's real configuration function, never by a campaign override."""
import hashlib
import json
from io import StringIO
import os
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from dotenv import dotenv_values

from core import admin_console, generation
from core.soap_document import original_bytes
from documents import word_v3
from ops import ordinary_generation_activation as activation
from quillmd.application_profile import field_relations_switch
from core.models import Encounter, Job, Template
from .test_word_v3_workflow import V3, V3Fixture


class OrdinaryModelApplicationConfiguration(SimpleTestCase):
    def configured(self, *, mode='fixture'):
        root = Path(__file__).resolve().parents[3]
        sources = {name: (root / name).read_bytes() for name in activation.SOURCE_PATHS}
        identity = {'release': 'b' * 40, 'model': activation.MODEL,
                    'ordinary_field_contract': activation.CONTRACT, 'request_profile': activation.PROFILE,
                    'sources': {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()}}
        baseline = ('QUILLMD_RELEASE_SHA=' + 'a' * 40 + '\nQUILLMD_DATA_MODE=synthetic\nQUILLMD_AI_MODE=' + mode + '\n').encode()
        prepared = activation.environment(baseline, 'a' * 40, 'b' * 40,
                                          source_identity=identity, source_bytes=sources)
        env = dotenv_values(stream=StringIO(prepared.decode()), interpolate=False)
        return {**{name[len('QUILLMD_'):]: value for name, value in env.items() if name.startswith('QUILLMD_AI_')},
                'V3_FIELD_RELATIONS_SWITCH': field_relations_switch(env), 'V3_FIELD_RELATIONS': True,
                'V3_GENERATION_BATCHES': False, 'V3_HISTORY_CONTEXT': False, 'WM_NARRATIVE': False}

    def test_prepared_settings_select_the_actual_source_bound_soap_contract_and_worker_request(self):
        fields = word_v3.inspect(original_bytes())['fields']
        with override_settings(**self.configured()):
            config = generation.configuration(fields)
            profile = generation.job_request_profile(config)
        self.assertEqual(config['model'], 'claude-sonnet-5-5')
        self.assertEqual(config['ordinary_field_contract'], 'ordinary-field-relations-v4')
        self.assertEqual(profile, {'profile': 'claude-sonnet-5-5-ordinary-v1', 'max_output_tokens': 20000,
                                   'timeout_seconds': 120, 'thinking': {'type': 'between_tools'}, 'effort': 'medium'})
        request = generation.anthropic_request(config['model'], profile, 'Synthetic system', {},
                                              {'type': 'object', 'properties': {}, 'additionalProperties': False})
        self.assertEqual(request['model'], 'claude-sonnet-5-5')
        self.assertEqual(request['max_tokens'], 20000)
        self.assertEqual(request['thinking'], {'type': 'between_tools'})
        self.assertEqual(request['output_config']['effort'], 'medium')
        self.assertNotIn('inference_geo', request)

    def test_admin_contract_row_is_configured_and_inactive_in_fixture_mode(self):
        with override_settings(**self.configured()), patch('core.admin_console.live_generation_queue_row', return_value={}):
            rows = {row['name']: row for row in admin_console.language_model_rows() if row}
        row = rows['ordinary field contract']
        self.assertIn('ordinary-field-relations-v4', row['value'])
        self.assertIn('inactive', row['value'])
        self.assertIn('does not certify', row['value'])
        self.assertEqual(row['severity'], '')

    def test_same_model_with_explicit_relations_off_is_distinct_and_preserves_stored_profile(self):
        with override_settings(**{**self.configured(mode='live'), 'V3_FIELD_RELATIONS': False,
                                  'V3_FIELD_RELATIONS_SWITCH': False}), \
                patch('core.admin_console.live_generation_queue_row', return_value={}):
            plain = generation.configuration()
            rows = {row['name']: row for row in admin_console.language_model_rows() if row}
        self.assertNotIn('ordinary_field_contract', plain)
        self.assertEqual(plain['request_profile']['profile'], 'claude-sonnet-5-5-v1')
        self.assertEqual(plain['request_profile']['max_output_tokens'], 8000)
        self.assertIn('not configured', rows['ordinary field contract']['value'])
        # Historical snapshots reconstruct under their recorded profile even after the new configuration changes.
        with override_settings(**self.configured(mode='live')):
            self.assertEqual(generation.job_request_profile(plain), plain['request_profile'])


@override_settings(**{**V3, 'AI_MODE': 'live', 'AI_PROVIDER': 'anthropic', 'AI_MODEL': activation.MODEL,
                      'AI_INPUT_RATE': '2', 'AI_OUTPUT_RATE': '10', 'AI_CACHED_RATE': '0.20',
                      'AI_THINKING': 'between_tools', 'AI_EFFORT': 'medium', 'AI_INFERENCE_GEO': '',
                      'V3_FIELD_RELATIONS_SWITCH': field_relations_switch({}), 'V3_FIELD_RELATIONS': False})
class OrdinaryModelDefaultJobSnapshot(V3Fixture, TestCase):
    def test_unset_synthetic_switch_selects_default_v4_in_an_actual_queued_http_job(self):
        # Real mode requires an explicit switch. This checks the existing synthetic default, independently of the
        # explicit activation builder, using the application original and normal mapping/encounter/admission routes.
        from core.jobs import enqueue
        with patch('anthropic.Anthropic') as provider:
            self.assertEqual(self.client.post('/templates/soap/', {'department': self.department.pk}).status_code, 302)
            template = Template.objects.exclude(name='').latest('created_at')
            version = self.confirm(template)
            self.assertEqual(private_original_hash(template), hashlib.sha256(original_bytes()).hexdigest())
            self.assertEqual(self.new_encounter(version, notes='Objective: Normal heart sounds.').status_code, 302)
            encounter = Encounter.objects.latest('created_at')
            page = self.client.get(f'/encounters/{encounter.pk}/')
            response = self.client.post(f'/encounters/{encounter.pk}/generate/', {
                'revision': encounter.revision, 'usage_quote': page.context['usage_quote']})
            artifact_root = os.getenv('QUILLMD_WORD_ARTIFACTS')
            if artifact_root:
                folder = Path(artifact_root) / 'ordinary-default-job'
                folder.mkdir(parents=True, exist_ok=True)
                (folder / 'snapshot-before-assert.json').write_text(json.dumps({
                    'http_status': response.status_code, 'redirect': getattr(response, 'url', ''),
                    'original_sha256': private_original_hash(template), 'mapping': version.fields,
                    'import_manifest': version.import_manifest,
                    'jobs': list(Job.objects.filter(encounter=encounter).values('kind', 'state', 'config', 'error')),
                }, default=str, indent=2) + '\n')
            self.assertEqual(response.status_code, 302)
            job = Job.objects.get(encounter=encounter, kind='generation')
            self.assertEqual(job.state, 'queued')
            self.assertEqual(job.config['ordinary_field_contract'], activation.CONTRACT)
            self.assertEqual(job.config['request_profile'], {
                'profile': activation.PROFILE, 'max_output_tokens': 20000, 'timeout_seconds': 120,
                'thinking': {'type': 'between_tools'}, 'effort': 'medium'})
            self.assertEqual(job.config['model'], activation.MODEL)
            self.assertEqual(generation.job_request_profile(job.config), job.config['request_profile'])
            # Repeating the exact admission reuses the persisted request rather than another charge reservation.
            self.assertEqual(enqueue(encounter, self.user).pk, job.pk)
            self.assertEqual(Job.objects.filter(encounter=encounter, kind='generation').count(), 1)
            provider.assert_not_called()


def private_original_hash(template):
    from core.security import private_path
    return hashlib.sha256(private_path(template.original_path).read_bytes()).hexdigest()
