"""Real isolated worker/adoption/reload boundaries, without provider transport."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core import ai_stages, generation, semantic_preparation, semantic_review
from core import source_assertion_graph as graph
from core.billing import welcome_credit
from core.document_review import review_token
from core.jobs import enqueue, run_one
from core.models import Encounter, Patient, SourceInterpretation, Usage, Wallet


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', ADMIN_SITE=False,
    TESTING_AUTHORITY_MODE='', TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='',
    STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
              'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class SourceAssertionWorkerTests(TestCase):
    def setUp(self):
        from core.tests.test_semantic_preparation import DefinitionPreparationDatabaseTests
        DefinitionPreparationDatabaseTests.setUp(self)
        welcome_credit(self.user)
        prep = semantic_preparation.create_preparation(self.source, self.user)
        self.assertEqual(prep.config['semantic_definition_version'], 4)
        self.assertTrue(semantic_preparation.run_one()); prep.refresh_from_db()
        self.version = semantic_preparation.approve(prep.pk, self.user, prep.revision,
            prep.inventory['inventory_sha256'], [f['key'] for f in self.source.fields], True)
        self.patient = Patient.objects.create(department=self.department, display_name='Synthetic Worker Arden',
            reference='WORKER-BOUNDARY', created_by=self.user)
        self.encounter = Encounter.objects.create(department=self.department, patient=self.patient,
            template_version=self.version, created_by=self.user, service_date=date(2026,10,19),
            notes='Retained synthetic worker source.\r\n')
        self.client.force_login(self.user)

    def execute(self, **options):
        with patch('core.coding_hooks.after_saved_document') as hook, \
             patch.object(ai_stages, '_response', side_effect=AssertionError('No provider transport permitted')):
            self.assertTrue(run_one())
        return hook

    def test_prospective_job_adopts_one_append_only_graph_and_reloads_every_answer(self):
        job = enqueue(self.encounter, self.user)
        config = deepcopy(job.config)
        self.assertEqual(config['semantic_fact_scope_contract'], graph.CONTRACT)
        self.assertEqual(config['semantic_encounter_binding']['patient_display_name'], self.patient.display_name)
        hook = self.execute()
        job.refresh_from_db(); self.encounter.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(job.config, config)
        self.assertEqual(job.ai_stage_receipts.count(), 3)
        self.assertEqual(Usage.objects.get(job=job).actual_cost, 0)
        row = SourceInterpretation.objects.get(job=job)
        self.assertEqual(len(row.stage_receipts), 3)
        self.assertEqual(row.encounter_id, self.encounter.pk)
        hook.assert_called_once_with(self.encounter.pk, self.user.pk)
        for field in self.version.fields:
            answer = self.encounter.answers[field['key']]
            self.assertEqual(answer['source_interpretation'], {'generation_job_id':str(job.pk),
                'interpretation_sha256':row.interpretation_sha256})
            self.assertEqual(semantic_review.validate_answer(self.encounter, field, answer), answer)
            self.assertEqual(semantic_review.displayed_answer(self.encounter, field, answer, self.version.semantic_definitions), answer)
        self.assertEqual(enqueue(self.encounter, self.user).pk, job.pk)
        self.assertFalse(run_one()); self.assertEqual(SourceInterpretation.objects.count(), 1)

    def test_mocked_live_anthropic_v4_job_adopts_and_reloads_nullable_transport(self):
        self.assert_mocked_live_v4_adoption(historical=False, nullable=True)

    def test_mocked_live_anthropic_v4_job_adopts_and_reloads_evidence_transport(self):
        self.assert_mocked_live_v4_adoption(historical=False)

    def test_historical_absent_marker_v4_job_adopts_and_reloads_shared_transport(self):
        self.assert_mocked_live_v4_adoption(historical=True)

    def assert_mocked_live_v4_adoption(self, *, historical, nullable=False):
        from core import clinical_schema_transport as codec, clinical_evidence_transport, source_assertion_generation
        from core.security import private_path
        from core.tests.test_billing_policy import fund
        fund(Wallet.objects.get(user=self.user, kind='paid'), Decimal('100'), 'payment:worker-v4-offline')
        config = {**generation.configuration(), 'mode': 'live', 'provider': 'anthropic',
            'model': 'claude-sonnet-5-5', 'input_rate': '1', 'cached_rate': '0.1', 'output_rate': '1',
            'discount_rate': '0'}
        if historical or nullable:
            prospective_configuration = ai_stages.pipeline_config
            def historical_configuration(value):
                retained = prospective_configuration(value)
                if historical:retained.pop(codec.CONFIG_KEY, None)
                else:retained[codec.CONFIG_KEY]=codec.TRANSPORT
                return retained
            # Recreate an already-queued old configuration only in this test.
            with patch.object(ai_stages, 'pipeline_config', side_effect=historical_configuration):
                job = enqueue(self.encounter, self.user, config=config)
            if historical:self.assertNotIn(codec.CONFIG_KEY, job.config)
            else:self.assertEqual(job.config[codec.CONFIG_KEY],codec.TRANSPORT)
        else:
            job = enqueue(self.encounter, self.user, config=config)
            self.assertEqual(job.config[codec.CONFIG_KEY], codec.CURRENT_TRANSPORT)
        frozen_config = deepcopy(job.config)
        calls = []
        provider_values = {}

        def provider(payload, schema, instructions, stage_config, maximum, timeout, on_response):
            role = ('extractor', 'assigner', 'checker')[len(calls)]
            calls.append(role)
            self.assertEqual((maximum, timeout), (32000, 240))
            self.assertEqual(stage_config, frozen_config)
            output = source_assertion_generation.fixture_stage(role, payload)
            wire = output if historical else (codec if nullable else clinical_evidence_transport).encode(schema, output)
            text = json.dumps(wire)
            provider_values[role] = {'canonical': deepcopy(output), 'wire': deepcopy(wire),
                'text': text, 'schema': deepcopy(schema), 'payload': deepcopy(payload),
                'instructions': instructions}
            number = len(calls)
            body = {'id': 'msg_shared_v4_' + str(number), 'model': stage_config['model'],
                'content': [{'type': 'text', 'text': text}], 'stop_reason': 'end_turn',
                'usage': {'input_tokens': 10, 'output_tokens': 0}}
            response = SimpleNamespace(id=body['id'], _request_id='req_shared_v4_' + str(number),
                model=stage_config['model'], model_dump=lambda **kwargs: deepcopy(body))
            on_response(response)
            rate_values = generation.rates(stage_config)
            list_cost = Decimal('10') * rate_values['input_per_million'] / 1000000
            discount = generation.discount_rate(stage_config)
            return (response, generation.discounted_cost(list_cost, discount),
                {'input_tokens': 10, 'cached_input_tokens': 0, 'cache_creation_tokens': 0, 'output_tokens': 0},
                generation.cost_rates(rate_values, list_cost, discount), text, True)

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'synthetic-offline-only'}), \
             patch.object(ai_stages, '_response', side_effect=provider) as send, \
             patch('core.coding_hooks.after_saved_document') as hook:
            self.assertTrue(run_one())
            self.assertFalse(run_one())
        job.refresh_from_db(); self.encounter.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(job.config, frozen_config)
        self.assertEqual(calls, ['extractor', 'assigner', 'checker'])
        self.assertEqual(send.call_count, 3)
        self.assertEqual(Usage.objects.get(job=job).actual_cost, Decimal('0.00003'))
        lineage = SourceInterpretation.objects.get(job=job)
        self.assertEqual(len(lineage.stage_receipts), 3)
        snapshots = []
        for row in job.ai_stage_receipts.order_by('created_at', 'pk'):
            raw = private_path(row.request_path).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row.request_sha256)
            request = json.loads(raw)
            value = provider_values[row.stage]
            expected_marker = ai_stages.ANTHROPIC_SCHEMA_TRANSPORT if historical else codec.TRANSPORT if nullable else codec.CURRENT_TRANSPORT
            self.assertEqual(request['schema_transport'], expected_marker)
            if not historical and not nullable:
                self.assertEqual(request['transmitted_schema'], json.dumps(codec.transmitted_schema(
                    value['schema'],codec.CURRENT_TRANSPORT),ensure_ascii=False,separators=(',',':'),allow_nan=False))
            self.assertEqual(request['schema'], value['schema'])
            self.assertEqual(request['payload'], value['payload'])
            self.assertEqual(request['instructions'], value['instructions'])
            result = private_path(row.result_path).read_bytes()
            self.assertEqual(hashlib.sha256(result).hexdigest(), row.result_sha256)
            wrapper = json.loads(result)
            self.assertEqual(wrapper['provider_output']['content'],
                [{'type': 'text', 'text': value['text']}])
            self.assertEqual(json.loads(value['text']), value['wire'])
            self.assertEqual(codec.response_value(value['text'], request, config=frozen_config,
                provider=row.provider, simulated=row.simulated), value['canonical'])
            self.assertEqual(row.provider, 'anthropic'); self.assertFalse(row.simulated)
            snapshots.extend(((row.request_path, raw), (row.result_path, result)))
        for field in self.version.fields:
            answer = self.encounter.answers[field['key']]
            self.assertEqual(semantic_review.validate_answer(self.encounter, field, answer), answer)
            self.assertEqual(semantic_review.displayed_answer(self.encounter, field, answer, self.version.semantic_definitions), answer)
        lineage_before = deepcopy(lineage.interpretation)
        lineage.refresh_from_db()
        self.assertEqual(lineage.interpretation, lineage_before)
        self.assertEqual(SourceInterpretation.objects.filter(job=job).count(), 1)
        for path, raw in snapshots:
            self.assertEqual(private_path(path).read_bytes(), raw)
        hook.assert_called_once_with(self.encounter.pk, self.user.pk)
        self.assertEqual(enqueue(self.encounter, self.user, config=config).pk, job.pk)

    def test_unknown_mock_source_cannot_approve_a_clinical_document_or_export(self):
        enqueue(self.encounter, self.user); self.execute(); self.encounter.refresh_from_db()
        post = {'intent':'approve', 'review_token':review_token(self.encounter,self.user,self.version.semantic_definitions)}
        for field in self.version.fields:
            post['answer_'+field['key']] = self.encounter.answers[field['key']]['text']
            post['decision_'+field['key']] = 'keep'
        response = self.client.post(reverse('document_review',args=[self.encounter.pk]),post)
        self.assertEqual(response.status_code,409)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.status,'review'); self.assertEqual(self.encounter.export_path,'')

    def test_identity_change_before_send_is_refused_without_stages_or_adoption(self):
        job = enqueue(self.encounter, self.user)
        Patient.objects.filter(pk=self.patient.pk).update(display_name='Synthetic Different Worker')
        hook = self.execute(); job.refresh_from_db(); self.encounter.refresh_from_db()
        self.assertEqual(job.state,'failed'); self.assertEqual(job.ai_stage_receipts.count(),0)
        self.assertFalse(SourceInterpretation.objects.exists()); self.assertEqual(self.encounter.answers,{})
        hook.assert_not_called()

    def test_identity_change_during_generation_preserves_stages_and_refuses_adoption(self):
        job = enqueue(self.encounter,self.user)
        execute = ai_stages.execute_stage
        def changed(**kwargs):
            output = execute(**kwargs)
            if kwargs['stage']=='checker':
                Patient.objects.filter(pk=self.patient.pk).update(reference='OTHER-WORKER')
            return output
        with patch.object(ai_stages,'execute_stage',side_effect=changed):
            hook = self.execute()
        job.refresh_from_db(); self.encounter.refresh_from_db()
        self.assertEqual(job.state,'failed'); self.assertEqual(job.ai_stage_receipts.count(),3)
        self.assertTrue(job.result_path); self.assertTrue(job.result_sha256)
        self.assertFalse(SourceInterpretation.objects.exists()); self.assertEqual(self.encounter.answers,{})
        hook.assert_not_called()

    def test_clinician_edit_keeps_generated_lineage_and_cannot_resolve_other_held_fields(self):
        enqueue(self.encounter,self.user); self.execute(); self.encounter.refresh_from_db()
        field = self.version.fields[1]
        prior = self.encounter.answers[field['key']]
        edited = semantic_review.save_answer(self.encounter,field,prior,
            'Explicit synthetic clinician correction.',self.user,False,False,1,self.version.semantic_definitions,
            document_level=True)
        self.encounter.answers[field['key']] = edited; self.encounter.revision += 1
        self.encounter.save(); self.encounter.refresh_from_db()
        self.assertEqual(edited['source_interpretation'],prior['source_interpretation'])
        self.assertEqual(edited['semantic_edit_history'][-1]['previous'],prior)
        self.assertEqual(semantic_review.validate_answer(self.encounter,field,edited),edited)
        other = self.version.fields[2]
        self.assertIn(self.encounter.answers[other['key']]['status'],('ambiguous','conflict'))
        forged = deepcopy(edited); forged['source_interpretation']['interpretation_sha256']='0'*64
        with self.assertRaises(ValidationError): semantic_review.validate_answer(self.encounter,field,forged)
