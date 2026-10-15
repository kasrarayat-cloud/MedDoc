"""New jobs freeze v10; retained jobs continue their original scope contract."""
from copy import deepcopy
import json
import os
from unittest.mock import patch

from django.test import TestCase, override_settings

from core import ai_stages, generation, semantic_generation as semantic
from core.jobs import enqueue, run_one
from core.models import Job
from core.security import private_path


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', TESTING_AUTHORITY_MODE='',
    TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='', ADMIN_SITE=False, STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class SourceContextWorkerTests(TestCase):
    def setUp(self):
        from core.tests.test_semantic_reference_contract import SemanticReferenceContractDatabaseTests
        SemanticReferenceContractDatabaseTests.setUp(self)

    def exercise(self, stored_scope):
        from core.tests.test_ai_stages import IndependentStageTests
        config = {**generation.configuration(), 'mode': 'live', 'model': 'synthetic-model',
                  'input_rate': '1', 'cached_rate': '0.1', 'output_rate': '1'}
        create = Job.objects.create
        def historical_insert(**values):
            if stored_scope is None:
                values['config'].pop('semantic_fact_scope_contract')
            else:
                values['config']['semantic_fact_scope_contract'] = stored_scope
            return create(**values)
        if stored_scope == semantic.DOCUMENT_IDENTITY_SCOPE_CONTRACT:
            job = enqueue(self.encounter, self.user, config=config)
        else:
            # Construct the historical snapshot at insertion, without updating
            # an existing immutable job or recomputing it with current rules.
            with patch('core.jobs.Job.objects.create', side_effect=historical_insert):
                job = enqueue(self.encounter, self.user, config=config)
        before = deepcopy(job.config)
        expected = stored_scope or semantic.POSITIONED_SCOPE_CONTRACT
        self.assertEqual(job.config.get('semantic_fact_scope_contract'), stored_scope)
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'synthetic-offline-placeholder'}), \
                patch.object(ai_stages, '_response', side_effect=IndependentStageTests.provider(self)) as transport:
            self.assertTrue(run_one())
            self.assertFalse(run_one())
        job.refresh_from_db()
        self.encounter.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(job.config, before)
        self.assertEqual(transport.call_count, 3)
        self.assertEqual(enqueue(self.encounter, self.user, config=config).pk, job.pk)
        self.assertTrue(self.encounter.answers)
        self.assertTrue(all(answer['fact_scope_contract'] == expected
                            for answer in self.encounter.answers.values()))
        rows = list(job.ai_stage_receipts.order_by('created_at'))
        self.assertEqual([row.stage for row in rows], ['extractor', 'assigner', 'checker'])
        suffixes = (semantic.SOURCE_CONTEXT_EXTRACT_INSTRUCTIONS,
                    semantic.SOURCE_CONTEXT_ASSIGN_INSTRUCTIONS,
                    semantic.SOURCE_CONTEXT_CHECK_INSTRUCTIONS)
        if expected in semantic.SOURCE_BINDING_SCOPE_CONTRACTS:
            suffixes = (semantic.SOURCE_BINDING_EXTRACT_INSTRUCTIONS,
                        semantic.SOURCE_BINDING_ASSIGN_INSTRUCTIONS,
                        semantic.SOURCE_BINDING_CHECK_INSTRUCTIONS)
        if expected in semantic.OBSERVATION_CONTEXT_SCOPE_CONTRACTS:
            suffixes = (semantic.OBSERVATION_CONTEXT_EXTRACT_INSTRUCTIONS,
                        semantic.OBSERVATION_CONTEXT_ASSIGN_INSTRUCTIONS,
                        semantic.OBSERVATION_CONTEXT_CHECK_INSTRUCTIONS)
        if expected in semantic.CONSENT_CONTEXT_SCOPE_CONTRACTS:
            suffixes = (semantic.CONSENT_CONTEXT_EXTRACT_INSTRUCTIONS,
                        semantic.CONSENT_CONTEXT_ASSIGN_INSTRUCTIONS,
                        semantic.CONSENT_CONTEXT_CHECK_INSTRUCTIONS)
        if expected == semantic.DOCUMENT_IDENTITY_SCOPE_CONTRACT:
            suffixes = (semantic.DOCUMENT_IDENTITY_INSTRUCTIONS,) * 3
        for row, suffix in zip(rows, suffixes):
            request = json.loads(private_path(row.request_path).read_text())
            self.assertEqual(request['max_output_tokens'], 16000)
            self.assertEqual(request['timeout_seconds'], 120)
            current = expected in semantic.SOURCE_CONTEXT_SCOPE_CONTRACTS
            self.assertEqual(request['instructions'].endswith(suffix), current)
            self.assertEqual('source_context_review' in request['payload'], current)
            self.assertEqual('observation_qualifier_inventory' in request['payload'],
                             expected in semantic.OBSERVATION_CONTEXT_SCOPE_CONTRACTS)
            self.assertEqual('consent_qualifier_inventory' in request['payload'],
                             expected in semantic.CONSENT_CONTEXT_SCOPE_CONTRACTS)
            if stored_scope is not None:
                self.assertEqual(request['payload']['fact_scope_contract'], expected)

    def test_new_enqueue_freezes_v10_and_worker_uses_it_without_extra_calls(self):
        self.exercise(semantic.DOCUMENT_IDENTITY_SCOPE_CONTRACT)

    def test_retained_v9_job_keeps_old_requests_and_answer_contract(self):
        self.exercise(semantic.CONSENT_CONTEXT_SCOPE_CONTRACT)

    def test_retained_v8_job_keeps_old_requests_and_answer_contract(self):
        self.exercise(semantic.OBSERVATION_CONTEXT_SCOPE_CONTRACT)

    def test_retained_v7_job_keeps_old_requests_and_answer_contract(self):
        self.exercise(semantic.REFERRAL_CITATION_SCOPE_CONTRACT)

    def test_retained_v6_job_keeps_old_requests_and_answer_contract(self):
        self.exercise(semantic.SOURCE_BINDING_SCOPE_CONTRACT)

    def test_retained_v5_job_keeps_old_requests_and_answer_contract(self):
        self.exercise(semantic.SOURCE_CONTEXT_SCOPE_CONTRACT)

    def test_retained_v4_job_keeps_old_requests_and_answer_contract(self):
        self.exercise(semantic.FAMILY_SCOPE_CONTRACT)

    def test_unversioned_job_keeps_original_positioned_scope(self):
        self.exercise(None)
