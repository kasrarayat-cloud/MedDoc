"""Offline provenance controls; these constructed records are not live results."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError

from core import coding_recovery as recovery, coding_output, coding_service as service
from core.tests import test_coding_output_live as live


class RetainedPredictionProvenanceTests(live.LiveOutputReferenceTests):
    # Reuse the tiny existing source/reference fixture, not its test campaign.
    def setUp(self):
        super().setUp()
        self.source = self.run
        self.source.inputs.update(encounter_id=str(self.encounter.pk),
            patient_id=str(self.encounter.patient_id), revision=0,
            template_version_id=str(uuid4()), answers={'field': {'text': ''}})
        self.source.input_digest = service.digest({'inputs': self.source.inputs,
            'context': self.source.context, 'releases': self.source.releases})
        live.bind_request(self.source)
        answers = {'field': {'text': 'Retained independently checked answer'}}
        self.result_path = Path(self.temporary.name) / 'revalidation-result.json'
        raw = json.dumps({'answers': answers}).encode()
        self.result_path.write_bytes(raw)
        self.job = SimpleNamespace(pk=uuid4(), encounter_id=self.encounter.pk,
            user_id=self.source.user_id, state='succeeded', revision=0,
            result_path='private-result.json', result_sha256=hashlib.sha256(raw).hexdigest(),
            config={'semantic_revalidation_contract': recovery.REVALIDATION_CONTRACT,
                'semantic_revalidation': {'parent_run_id': str(self.source.pk),
                    'parent_answers_sha256': service.digest(self.source.inputs['answers']),
                    'encounter_id': str(self.encounter.pk), 'actor_id': str(self.source.user_id)}})
        self.derived = deepcopy(self.source)
        self.derived.pk = uuid4()
        self.derived.inputs['answers'] = answers
        self.derived.input_digest = service.digest({'inputs': self.derived.inputs,
            'context': self.derived.context, 'releases': self.derived.releases})
        binding = {'contract': recovery.CONTRACT, 'source_run_id': str(self.source.pk),
            'source_input_digest': self.source.input_digest,
            'source_requests_digest': service.digest(self.source.requests),
            'source_result_digest': service.digest(self.source.result),
            'recovery_job_id': str(self.job.pk), 'recovery_result_sha256': self.job.result_sha256,
            'approved_answers_digest': service.digest(answers)}
        self.derived.config = {**deepcopy(self.source.config), 'mode': recovery.MODE,
            'max_calls': 0, 'retained_prediction': binding}
        self.derived.requests = []
        self.derived.actual_cost = Decimal('0')
        self.derived.result['retained_prediction'] = binding
        for target, value in [('core.coding_recovery.CodingRun.objects.get', self.source),
                              ('core.coding_recovery.Job.objects.get', self.job),
                              ('core.coding_recovery.private_path', self.result_path),
                              ('core.semantic_revalidation.validate_completed', None)]:
            mocked = patch(target, return_value=value)
            mocked.start(); self.addCleanup(mocked.stop)

    def test_original_receipt_identity_remains_only_on_source_run(self):
        original = deepcopy(self.source.requests)
        with patch('core.corti_prediction.execute', side_effect=AssertionError('No prediction allowed')) as send:
            self.assertIs(recovery.source_for(self.derived), self.source)
            assessment = coding_output.live_assessment(self.encounter, self.derived)
        self.assertEqual(assessment['selection']['code'], '99213')
        self.assertEqual(assessment['scope']['run_id'], str(self.derived.pk))
        self.assertEqual(assessment['response_sha256'], self.source.requests[0]['response_sha256'])
        self.assertEqual(self.derived.requests, [])
        self.assertEqual(self.derived.actual_cost, 0)
        self.assertEqual(self.source.requests, original)
        self.assertIn('15 MINUTES', original[0]['raw_response']['body'])
        send.assert_not_called()

    def test_different_patient_note_date_revision_template_context_or_release_refuses(self):
        cases = [('patient_id', str(uuid4())), ('encounter_id', str(uuid4())),
            ('notes', self.source.inputs['notes'] + ' Different source.'),
            ('service_date', '2026-10-17'), ('revision', 1),
            ('template_version_id', str(uuid4()))]
        for key, value in cases:
            with self.subTest(key=key):
                derived = deepcopy(self.derived); derived.inputs[key] = value
                with self.assertRaises(ValidationError): recovery.source_for(derived)
        for key, value in [('context', {'setting': 'changed'}), ('releases', [{'id': 'changed'}])]:
            with self.subTest(key=key):
                derived = deepcopy(self.derived); setattr(derived, key, value)
                with self.assertRaises(ValidationError): recovery.source_for(derived)

    def test_no_fabricated_receipt_cost_or_changed_answers_can_claim_reuse(self):
        for key, value in [('requests', deepcopy(self.source.requests)), ('actual_cost', Decimal('1')),
                           ('state', 'queued')]:
            with self.subTest(key=key):
                derived = deepcopy(self.derived); setattr(derived, key, value)
                with self.assertRaises(ValidationError): recovery.source_for(derived)
        self.derived.inputs['answers']['field']['text'] = 'Manually replaced answer'
        with self.assertRaises(ValidationError): recovery.source_for(self.derived)

    def test_changed_original_raw_response_and_missing_validation_artifact_refuse(self):
        body = self.source.requests[0]['raw_response']['body']
        self.source.requests[0]['raw_response']['body'] = body + ' '
        with self.assertRaises(ValidationError): recovery.source_for(self.derived)
        self.source.requests[0]['raw_response']['body'] = body
        self.result_path.unlink()
        with self.assertRaises(ValidationError): recovery.source_for(self.derived)

    def test_configuration_drift_and_failed_independent_proof_refuse(self):
        self.derived.config['max_calls'] = 1
        with self.assertRaises(ValidationError): recovery.source_for(self.derived)
        self.derived.config['max_calls'] = 0
        with patch('core.semantic_revalidation.validate_completed', side_effect=ValidationError('Invalid proof')):
            with self.assertRaises(ValidationError): recovery.source_for(self.derived)

    def test_unknown_revalidation_contract_never_becomes_a_pass(self):
        self.job.config['semantic_revalidation_contract'] = 'unknown'
        with self.assertRaises(ValidationError): recovery.source_for(self.derived)


# The base class is a fixture supplier. Do not rerun its unrelated campaign here.
for _name in tuple(vars(live.LiveOutputReferenceTests)):
    if _name.startswith('test_'):
        setattr(RetainedPredictionProvenanceTests, _name, None)
