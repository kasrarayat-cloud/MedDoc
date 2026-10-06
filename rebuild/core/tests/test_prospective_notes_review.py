"""Actual source-bound mapping review; synthetic original and no provider requests."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

from django.test import TestCase, override_settings
from core import import_binding
from core.models import Job, Reservation, Usage
from core.security import private_path
from core.tests.test_word_v3_workflow import V3Fixture
from core.tests.test_workflow import TEST_SETTINGS
from ops import provider_campaign as pc, sonnet5_stages as stages, standing_qa_notes_review as nr


@override_settings(**dict(TEST_SETTINGS,QUILLMD_WORD_ENGINE='v3'))
class ActualProspectiveNotesReview(V3Fixture,TestCase):
    def setUp(self):
        super().setUp()
        self.row = nr.frozen(nr.MANIFEST_SHA256)
        self.inputs = nr.inputs_with_review(stages.frozen_inputs(),self.row)
        forms = stages.build_forms(Path(self.directory.name)/'frozen-forms','ordinary_notes',self.inputs)
        self.original = forms['r1-11']
        self.template,self.version = self.uploaded(data=self.original,name='Synthetic original consent qualification')
        self.fields = self.inputs['cases']['forms']['r1-11']['fields']

    def test_actual_review_confirms_new_version_without_changing_original_or_auto_coverage(self):
        original_fields,original_manifest = deepcopy(self.version.fields),deepcopy(self.version.import_manifest)
        before = self.version.pk
        reviewed,record = nr.review_mapping(self.client,self.template,self.version,self.row,self.fields)
        self.assertNotEqual(before,reviewed.pk)
        self.assertEqual(reviewed.fields,original_fields)
        self.assertEqual(reviewed.import_manifest,original_manifest)
        self.assertFalse(reviewed.import_manifest['coverage']['automatic_complete'])
        self.assertTrue(import_binding.coverage_reviewed(reviewed))
        self.confirm(self.template,reviewed)
        reviewed.refresh_from_db();self.assertIsNotNone(reviewed.confirmed)
        self.version.refresh_from_db();self.assertIsNone(self.version.confirmed)
        self.assertTrue(record['manual_mapping_review'])
        self.assertFalse(record['corpus_qualification'])
        self.assertEqual(private_path(self.template.original_path).read_bytes(),self.original)
        self.assertEqual((Job.objects.count(),Reservation.objects.count(),Usage.objects.count()),(0,0,0))

    def test_original_unreviewed_confirmation_and_changed_physical_review_refuse(self):
        response = stages.steps.confirm_mapping(self.client,self.template.pk,self.version.pk)
        self.assertEqual(response.status_code,400)
        self.version.refresh_from_db();self.assertIsNone(self.version.confirmed)
        row = {**self.row,'slot':self.row['slot']+'/different'}
        with self.assertRaises(pc.Refused):nr.review_mapping(self.client,self.template,self.version,row,self.fields)
        self.assertEqual(self.template.versions.count(),1)
        self.assertFalse(import_binding.coverage_reviewed(self.version))
        self.assertEqual(private_path(self.template.original_path).read_bytes(),self.original)
        self.assertEqual((Job.objects.count(),Reservation.objects.count(),Usage.objects.count()),(0,0,0))
