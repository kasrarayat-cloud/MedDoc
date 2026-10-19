"""Real isolated worker/adoption/reload boundaries, without provider transport."""
from copy import deepcopy
from datetime import date
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core import ai_stages, generation, semantic_preparation, semantic_review
from core import source_assertion_graph as graph
from core.billing import welcome_credit
from core.document_review import review_token
from core.jobs import enqueue, run_one
from core.models import Encounter, Patient, SourceInterpretation, Usage


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
