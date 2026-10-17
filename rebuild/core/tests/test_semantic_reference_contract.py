"""Persist the reference protocol before queueing; never reinterpret old jobs.

All stages use the offline fixture transport and an isolated PostgreSQL database.
Historical configurations are supplied at insertion, never by changing a row.
"""
from copy import deepcopy
from unittest.mock import patch

from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings

from core import ai_stages, semantic_generation as semantic
from core.jobs import enqueue, run_one
from core.models import Encounter, Job, ProviderReceipt, TemplateDefinitionPreparation, Usage
from core.tests import test_ai_stages as stage_fixtures


ABSENT = object()


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture',
    TESTING_AUTHORITY_MODE='', TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='',
    ADMIN_SITE=False, STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class SemanticReferenceContractDatabaseTests(TestCase):
    def setUp(self):
        # Reference-protocol replay needs a genuinely historical definition
        # contract, supplied before insertion rather than rewriting approval.
        create = TemplateDefinitionPreparation.objects.create
        def insert(**values):
            values['config'] = {**values['config'], 'semantic_definition_version': 2}
            return create(**values)
        with patch('core.semantic_preparation.TemplateDefinitionPreparation.objects.create', side_effect=insert):
            stage_fixtures.IndependentStageTests.setUp(self)
        self.assertEqual({d['version'] for d in self.version.semantic_definitions.values()}, {2})

    def historical_job(self, marker=ABSENT, encounter=None, *,
                       scope_contract=semantic.FAMILY_SCOPE_CONTRACT):
        """Freeze the baseline v4 scope alongside the supplied reference marker."""
        create = Job.objects.create
        def insert(**values):
            values['config'] = deepcopy(values['config'])
            values['config']['semantic_fact_scope_contract'] = scope_contract
            if marker is ABSENT:
                values['config'].pop('semantic_fact_reference_contract')
            else:
                values['config']['semantic_fact_reference_contract'] = marker
            return create(**values)
        with patch('core.jobs.Job.objects.create', side_effect=insert):
            return enqueue(encounter or self.encounter, self.user)

    def another_encounter(self):
        return Encounter.objects.create(department=self.encounter.department,
            patient=self.encounter.patient, template_version=self.version,
            created_by=self.user, service_date=self.encounter.service_date,
            notes=self.encounter.notes)

    def test_new_semantic_job_pins_v2_before_insertion_and_config_is_immutable(self):
        create = Job.objects.create
        observed = []
        def insert(**values):
            observed.append(deepcopy(values['config']))
            return create(**values)
        with patch('core.jobs.Job.objects.create', side_effect=insert):
            job = enqueue(self.encounter, self.user)
        self.assertEqual(observed[0]['semantic_fact_reference_contract'], semantic.REFERENCE_INVENTORY_CONTRACT)
        self.assertEqual(observed[0]['semantic_fact_scope_contract'], semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT)
        self.assertEqual(job.config, observed[0])
        self.assertEqual(job.config['semantic_template_version'], str(self.version.pk))
        original = deepcopy(job.config)
        modified = {**job.config, 'semantic_fact_reference_contract': semantic.LEGACY_REFERENCE_CONTRACT}
        with self.assertRaises(DatabaseError), transaction.atomic():
            Job.objects.filter(pk=job.pk).update(config=modified)
        job.refresh_from_db()
        self.assertEqual(job.config, original)

    def test_new_semantic_execution_uses_v2_schema_and_returns_three_observable_stages(self):
        job = enqueue(self.encounter, self.user)
        original = deepcopy(job.config)
        with patch.object(semantic, 'run', wraps=semantic.run) as dispatch, \
             patch.object(ai_stages, 'execute_stage', wraps=ai_stages.execute_stage) as stages:
            self.assertTrue(run_one())
        job.refresh_from_db(); self.encounter.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(dispatch.call_args.kwargs['reference_contract'], semantic.REFERENCE_INVENTORY_CONTRACT)
        self.assertEqual(dispatch.call_args.kwargs['scope_contract'], semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT)
        first = stages.call_args_list[0].kwargs
        self.assertEqual(first['payload']['reference_contract'], semantic.REFERENCE_INVENTORY_CONTRACT)
        self.assertEqual(first['payload']['fact_scope_contract'], semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT)
        self.assertEqual(first['schema'], semantic.SOURCE_CONTEXT_API_FACT_INVENTORY_SCHEMA)
        self.assertEqual(first['instructions'], semantic.EXTRACT_INVENTORY_INSTRUCTIONS
                         + ' ' + semantic.SOURCE_CONTEXT_EXTRACT_INSTRUCTIONS
                         + ' ' + semantic.SOURCE_BINDING_EXTRACT_INSTRUCTIONS
                         + ' ' + semantic.OBSERVATION_CONTEXT_EXTRACT_INSTRUCTIONS
                         + ' ' + semantic.CONSENT_CONTEXT_EXTRACT_INSTRUCTIONS
                         + ' ' + semantic.DOCUMENT_IDENTITY_INSTRUCTIONS + semantic.LITERAL_SOURCE_INSTRUCTIONS)
        self.assertEqual(job.ai_stage_receipts.count(), 3)
        self.assertEqual(Usage.objects.get(job=job).actual_cost, 0)
        self.assertTrue(all(answer['status'] == 'missing' and not answer['reviewed']
                            for answer in self.encounter.answers.values()))
        self.assertEqual(job.config, original)

    def test_unmarked_queued_job_dispatches_strict_legacy_and_replays_never_add_v2(self):
        job = self.historical_job()
        original = deepcopy(job.config)
        replay = enqueue(self.encounter, self.user)
        self.assertEqual(replay.pk, job.pk)
        self.assertEqual(replay.config, original)
        self.assertNotIn('semantic_fact_reference_contract', replay.config)
        self.assertEqual(replay.config['semantic_fact_scope_contract'], semantic.FAMILY_SCOPE_CONTRACT)
        with patch.object(semantic, 'run', wraps=semantic.run) as dispatch, \
             patch.object(ai_stages, 'execute_stage', wraps=ai_stages.execute_stage) as stages:
            self.assertTrue(run_one())
        self.assertEqual(dispatch.call_args.kwargs['reference_contract'], semantic.LEGACY_REFERENCE_CONTRACT)
        self.assertEqual(dispatch.call_args.kwargs['scope_contract'], semantic.FAMILY_SCOPE_CONTRACT)
        first = stages.call_args_list[0].kwargs
        self.assertNotIn('reference_contract', first['payload'])
        self.assertEqual(first['schema'], semantic.API_FACT_SCHEMA)
        self.assertEqual(first['instructions'], semantic.EXTRACT_INSTRUCTIONS)
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(job.config, original)
        count = job.ai_stage_receipts.count()
        self.assertEqual(enqueue(self.encounter, self.user).pk, job.pk)
        self.assertFalse(run_one())
        job.refresh_from_db()
        self.assertEqual(job.config, original)
        self.assertEqual(job.ai_stage_receipts.count(), count)

    def test_explicit_legacy_marker_keeps_legacy_dispatch(self):
        job = self.historical_job(semantic.LEGACY_REFERENCE_CONTRACT)
        with patch.object(semantic, 'run', wraps=semantic.run) as dispatch:
            self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(dispatch.call_args.kwargs['reference_contract'], semantic.LEGACY_REFERENCE_CONTRACT)
        self.assertEqual(job.config['semantic_fact_reference_contract'], semantic.LEGACY_REFERENCE_CONTRACT)

    def test_legacy_reference_marker_and_v5_scope_dispatch_independently(self):
        job = self.historical_job(semantic.LEGACY_REFERENCE_CONTRACT,
                                  scope_contract=semantic.SOURCE_CONTEXT_SCOPE_CONTRACT)
        original = deepcopy(job.config)
        with patch.object(semantic, 'run', wraps=semantic.run) as dispatch, \
             patch.object(ai_stages, 'execute_stage', wraps=ai_stages.execute_stage) as stages:
            self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(dispatch.call_args.kwargs['reference_contract'], semantic.LEGACY_REFERENCE_CONTRACT)
        self.assertEqual(dispatch.call_args.kwargs['scope_contract'], semantic.SOURCE_CONTEXT_SCOPE_CONTRACT)
        first = stages.call_args_list[0].kwargs
        self.assertNotIn('reference_contract', first['payload'])
        self.assertEqual(first['payload']['fact_scope_contract'], semantic.SOURCE_CONTEXT_SCOPE_CONTRACT)
        self.assertEqual(first['schema'], semantic.SOURCE_CONTEXT_API_FACT_SCHEMA)
        self.assertEqual(first['instructions'], semantic.EXTRACT_INSTRUCTIONS
                         + ' ' + semantic.SOURCE_CONTEXT_EXTRACT_INSTRUCTIONS)
        self.assertEqual(job.ai_stage_receipts.count(), 3)
        self.assertEqual(job.config, original)

    def test_explicit_null_and_unknown_markers_refuse_without_stage_cost_or_fallback(self):
        for marker in (None, 'unknown-reference-contract', ''):
            encounter = self.another_encounter()
            job = self.historical_job(marker, encounter)
            original = deepcopy(job.config)
            with self.subTest(marker=marker), \
                 patch.object(ai_stages, 'execute_stage', side_effect=AssertionError('Nothing may be sent')) as stages:
                self.assertTrue(run_one())
            stages.assert_not_called()
            job.refresh_from_db(); encounter.refresh_from_db()
            self.assertEqual(job.state, 'failed', job.error)
            self.assertIn('refused before any provider request', job.error)
            self.assertEqual(job.ai_stage_receipts.count(), 0)
            self.assertFalse(Usage.objects.filter(job=job).exists())
            self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
            self.assertEqual(encounter.answers, {})
            self.assertEqual(job.config, original)
            self.assertEqual(enqueue(encounter, self.user).pk, job.pk)
            self.assertFalse(run_one())
            job.refresh_from_db()
            self.assertEqual(job.config, original)
