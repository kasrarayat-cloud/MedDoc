"""Internal diagnostic redaction and the real post-extractor worker boundary."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import UUID

from django.core.exceptions import ValidationError

from core.clinical_validation_diagnostics import (
    SourceAssertionValidationError, safe_validation_diagnostic,
)


class ClinicalValidationDiagnosticTests(TestCase):
    def test_trusted_single_code_preserves_existing_validation_interface(self):
        error = SourceAssertionValidationError('unit_not_attached')
        self.assertIsInstance(error, ValidationError)
        self.assertEqual(error.code, 'unit_not_attached')
        self.assertEqual(error.messages, ['Source assertion graph: unit_not_attached'])
        self.assertEqual(safe_validation_diagnostic(error), {
            'namespace': 'source_assertion_graph', 'code': 'unit_not_attached'})

    def test_plain_or_matching_provider_errors_do_not_acquire_internal_authority(self):
        class UntrustedSubclass(SourceAssertionValidationError):
            pass

        for error in (ValidationError('Source assertion graph: unit_not_attached',
                code='unit_not_attached', params={'source': 'PRIVATE_CANARY'}),
                ValidationError(['unit_not_attached', 'PRIVATE_CANARY']),
                ValidationError({'unit_not_attached': ['PRIVATE_CANARY']}),
                ValueError('unit_not_attached'), UntrustedSubclass('unit_not_attached'), None):
            with self.subTest(error_type=type(error).__name__):
                self.assertIsNone(safe_validation_diagnostic(error))

    def test_malformed_codes_are_refused_without_interpolating_them(self):
        class Unprintable:
            def __str__(self):
                raise AssertionError('An untrusted value must not be formatted')

        for code in (None, True, 1, [], {}, Unprintable(), '', 'UPPER', 'two codes',
                'source.value', 'private\nsource', 'private\x00source', 'a' * 81, 'évidence'):
            with self.subTest(code_type=type(code).__name__), self.assertRaises(ValueError):
                SourceAssertionValidationError(code)
        for code in ('a', 'a' * 80, 'fact_2'):
            self.assertEqual(safe_validation_diagnostic(SourceAssertionValidationError(code))['code'], code)

    def test_mutated_or_multicode_error_shapes_fail_closed(self):
        for change in ({'code': ['unit_not_attached', 'PRIVATE_CANARY']}, {'code': None},
                {'code': 'a' * 81}, {'error_list': []}, {'error_list': ()},
                {'error_list': [ValidationError('PRIVATE_CANARY')]},
                {'error_dict': {'source': ['PRIVATE_CANARY']}}):
            error = SourceAssertionValidationError('unit_not_attached')
            error.__dict__.update(change)
            self.assertIsNone(safe_validation_diagnostic(error))
        error = SourceAssertionValidationError('unit_not_attached')
        error.error_list.append(error)
        self.assertIsNone(safe_validation_diagnostic(error))

    def test_only_code_and_static_namespace_are_serialized(self):
        class Unprintable:
            def __str__(self):
                raise AssertionError('Do not format source-bearing parameters')

        error = SourceAssertionValidationError('unit_not_attached')
        error.message = Unprintable()
        error.params = {'source': 'PRIVATE_CANARY', 'provider_body': Unprintable()}
        diagnostic = safe_validation_diagnostic(error)
        self.assertEqual(json.dumps(diagnostic, sort_keys=True),
            '{"code": "unit_not_attached", "namespace": "source_assertion_graph"}')


class ClinicalValidationWorkerDiagnosticTests(TestCase):
    def run_failed_worker(self, *, plain_error=False):
        from core import ai_stages, jobs, semantic_generation, semantic_review, word_contract
        from core import source_assertion_graph as graph
        from core.tests.test_source_assertion_graph import (
            IDENTITY, assertion, base_case, extraction, fact, ref,
        )

        notes, fields, definitions, raw, _ = base_case(
            'The patient is a 44-year-old woman. PRIVATE_DIAGNOSTIC_CANARY.')
        age = fact(notes, 'f2', '44-year-old', kind='identity')
        age.update(unit='year', unit_span=ref(notes, 'year'))
        raw = extraction(notes, [*raw['facts'], age], [*raw['assertions'],
            assertion(notes, 'a2', ['f2'], '44-year-old', kind='context', consumer_role='none')])
        frozen_raw = deepcopy(raw)
        identity = deepcopy(IDENTITY)
        department_id = UUID(identity['department_id'])
        version = SimpleNamespace(pk=UUID(identity['template_version_id']), fields=fields,
            template=SimpleNamespace(department_id=department_id))
        encounter = SimpleNamespace(pk=UUID(identity['encounter_id']), notes=notes,
            template_version=version, template_version_id=version.pk, department_id=department_id,
            department=SimpleNamespace(pk=department_id), patient_id=UUID(identity['patient_id']),
            patient=SimpleNamespace(department_id=department_id,
                display_name=identity['patient_display_name'], reference=identity['patient_reference']),
            service_date=date.fromisoformat(identity['service_date']), answers={})
        config = {'mode': 'live', 'semantic_template_version': str(version.pk),
            'semantic_source_sha256': hashlib.sha256(notes.encode()).hexdigest(),
            'semantic_definitions_sha256': semantic_generation.digest(definitions),
            'semantic_fact_scope_contract': graph.CONTRACT,
            'semantic_encounter_binding': {k: v for k, v in identity.items() if k != 'generation_job_id'}}
        rows = []
        job = SimpleNamespace(pk=UUID(identity['generation_job_id']), encounter=encounter,
            config=config, ai_stage_receipts=SimpleNamespace(all=lambda: rows), user=object(),
            request_key='synthetic-diagnostic-job', save=Mock(), state='running')
        usage_exists = False
        events, calls = [], []

        def execute(**kwargs):
            calls.append((kwargs['stage'], kwargs['attempt']))
            self.assertEqual(calls, [('extractor', 1)])
            rows.append(SimpleNamespace(started_at=object(), state='succeeded',
                actual_cost=Decimal('.1')))
            if plain_error:
                raise ValidationError('Source assertion graph: unit_not_attached',
                    code='unit_not_attached', params={'source': 'PRIVATE_DIAGNOSTIC_CANARY'})
            return deepcopy(raw)

        def settle(_job):
            nonlocal usage_exists
            usage_exists = True

        def audit(actor, action, object_id, **data):
            events.append((action, data))

        usage_query = SimpleNamespace(exists=lambda: usage_exists)
        with patch.object(word_contract, 'require_generation', return_value=definitions), \
                patch.object(semantic_review, 'definitions_for', return_value=definitions), \
                patch.object(ai_stages, 'execute_stage', side_effect=execute), \
                patch.object(ai_stages, 'retain', side_effect=AssertionError('No result adoption')), \
                patch.object(jobs.Usage.objects, 'filter', return_value=usage_query), \
                patch.object(jobs, 'settle_semantic_stages', side_effect=settle) as settlement, \
                patch.object(jobs, 'absorb_failed_job') as absorb, \
                patch.object(jobs, 'audit', side_effect=audit):
            self.assertTrue(jobs.run_semantic_job(job))
        settlement.assert_called_once_with(job)
        absorb.assert_called_once_with(job)
        self.assertTrue(usage_exists)
        self.assertEqual(raw, frozen_raw)
        self.assertEqual(encounter.answers, {})
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.error,
            'platform_failure: Output could not be adopted (ValidationError); review required.')
        self.assertEqual(calls, [('extractor', 1)])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], 'job.failed')
        data = events[0][1]
        self.assertEqual(data['error_class'], 'ValidationError')
        self.assertEqual(data['billing'], 'platform_failure')
        safe = {k: v for k, v in data.items() if k != 'department'}
        self.assertNotIn('PRIVATE_DIAGNOSTIC_CANARY', json.dumps(safe))
        self.assertNotIn('44-year-old', json.dumps(safe))
        return data

    def test_real_graph_failure_records_code_after_settlement_without_assignment(self):
        data = self.run_failed_worker()
        self.assertEqual(data['validation_diagnostic'], {
            'namespace': 'source_assertion_graph', 'code': 'unit_not_attached'})

    def test_matching_plain_validation_error_keeps_original_redacted_failure(self):
        self.assertNotIn('validation_diagnostic', self.run_failed_worker(plain_error=True))
