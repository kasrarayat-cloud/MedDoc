"""Persisted positive/negative admission controls for the repaired test original."""
from copy import deepcopy
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from documents import DocumentError

from core import destination_roles
from core.jobs import enqueue, run_one
from core.models import Job, Reservation, Usage
from core.security import private_path
from .test_security import SyntheticFixture
from .synthetic_original import inspection


@override_settings(AI_MODE='fixture', ADMIN_SITE=False)
class SyntheticOriginalAdmission(SyntheticFixture, TestCase):
    def setUp(self):
        self.scope = self.make_scope('source-bound-positive')
        self.user, _, _, _, self.template, self.encounter, self.original = self.scope

    def test_real_original_and_exact_inspector_mapping_queue_and_adopt_once_without_charge(self):
        version = self.encounter.template_version
        self.assertEqual(version.fields, inspection()['fields'])
        self.assertEqual(version.import_manifest, inspection()['import_manifest'])
        self.assertEqual(private_path(self.template.original_path).read_bytes(), self.original)
        job = enqueue(self.encounter, self.user)
        self.assertTrue(run_one())
        job.refresh_from_db(); self.encounter.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(self.encounter.answers[version.fields[0]['key']]['text'], 'no chest pain')
        self.assertEqual(Usage.objects.get(job=job).charged_cost, 0)
        self.assertEqual(enqueue(self.encounter, self.user).pk, job.pk)
        self.assertFalse(run_one())
        self.assertEqual(Usage.objects.count(), 1)

    def test_missing_original_retains_source_unavailable_before_job_or_hold(self):
        private_path(self.template.original_path).unlink()
        with self.assertRaises(DocumentError) as failure:
            enqueue(self.encounter, self.user)
        self.assertEqual(failure.exception.code, 'source_unavailable')
        self.assertFalse(Job.objects.exists()); self.assertFalse(Reservation.objects.exists())

    def test_replaced_original_refuses_before_job_or_hold(self):
        private_path(self.template.original_path).write_bytes(b'SYNTHETIC changed original')
        with self.assertRaises((DocumentError, ValidationError)):
            enqueue(self.encounter, self.user)
        self.assertFalse(Job.objects.exists()); self.assertFalse(Reservation.objects.exists())

    def test_fabricated_destination_cannot_hide_under_the_source_bound_import(self):
        version = self.encounter.template_version
        version.fields = deepcopy(version.fields)
        version.fields[0]['locator']['cell'] = 99
        with self.assertRaisesMessage(ValidationError, 'stored import choice'):
            destination_roles.report(version)
        self.assertFalse(Job.objects.exists()); self.assertFalse(Reservation.objects.exists())
