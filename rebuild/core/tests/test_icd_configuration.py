"""Persisted release metadata is useful without exposing clinical or coding text."""
from datetime import date
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.context import icd_configuration, integration_status
from core.models import CodeSet, Encounter, User
from core.tests.surfaces import SurfaceClient
from core.tests.test_security import SyntheticFixture


class ICDConfiguration(TestCase):
    def release(self, version, start, end, system='ICD-10-CM'):
        return CodeSet.objects.create(system=system, version=version,
            effective_from=date.fromisoformat(start), effective_until=date.fromisoformat(end),
            source_url='https://www.cms.gov/files/synthetic.txt', sha256='a'*64)

    def test_new_fiscal_year_is_shown_and_prior_metadata_is_retained(self):
        self.release('FY2026-April', '2026-04-01', '2026-09-30')
        self.release('FY2027', '2026-10-01', '2027-09-30')
        with patch('core.context.timezone.localdate', return_value=date(2026,10,3)):
            row = icd_configuration()
        self.assertEqual(row['status'], 'Current release: FY2027')
        self.assertEqual(row['severity'], 'success')
        self.assertIn('Effective 2026-10-01 through 2027-09-30', row['detail'])
        self.assertIn('2 loaded release(s)', row['detail'])
        self.assertIn('date of service', row['detail'])
        self.assertIn('does not verify code-file integrity', row['detail'])
        self.assertEqual(CodeSet.objects.count(), 2)

    def test_both_effective_boundaries_are_inclusive(self):
        self.release('FY2027', '2026-10-01', '2027-09-30')
        for at in (date(2026,10,1),date(2027,9,30)):
            with self.subTest(at=at),patch('core.context.timezone.localdate',return_value=at):
                self.assertEqual(icd_configuration()['severity'],'success')

    def test_expired_history_and_future_release_do_not_claim_current_coverage(self):
        self.release('FY2026-April', '2026-04-01', '2026-09-30')
        self.release('FY2028', '2027-10-01', '2028-09-30')
        with patch('core.context.timezone.localdate',return_value=date(2026,10,3)):
            row=icd_configuration()
        self.assertEqual((row['status'],row['severity']),('No release covers today','warning'))
        self.assertIn('2026-10-03',row['detail'])
        self.assertIn('Historical visits can still use their applicable release',row['detail'])

    def test_no_loaded_release_or_cpt_release_cannot_mask_the_gap(self):
        self.release('synthetic-CPT','2026-01-01','2026-12-31',system='CPT')
        with patch('core.context.timezone.localdate',return_value=date(2026,10,3)):
            row=icd_configuration()
        self.assertEqual(row['status'],'No release covers today')
        self.assertIn('0 loaded release(s)',row['detail'])

    def test_overlapping_metadata_is_an_operator_error(self):
        self.release('FY2027-a','2026-10-01','2027-09-30')
        self.release('FY2027-b','2026-10-01','2027-09-30')
        with patch('core.context.timezone.localdate',return_value=date(2026,10,3)):
            row=icd_configuration()
        self.assertEqual((row['status'],row['severity']),('Overlapping current releases','error'))

    def test_unreadable_metadata_is_an_error_without_exception_text(self):
        with patch.object(CodeSet.objects,'filter',side_effect=DatabaseError('synthetic confidential diagnostic')):
            row=icd_configuration()
        self.assertEqual((row['status'],row['severity']),('Release metadata unavailable','error'))
        self.assertNotIn('confidential',str(row))

    def test_every_integrations_consumer_gets_the_same_row(self):
        with patch('core.context.icd_configuration',return_value={'name':'ICD-10-CM terminology','status':'bound','detail':'same','severity':'warning'}):
            rows=[row for row in integration_status() if row['name']=='ICD-10-CM terminology']
        self.assertEqual(rows,[{'name':'ICD-10-CM terminology','status':'bound','detail':'same','severity':'warning'}])


@override_settings(AI_MODE='fixture', ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False,
    STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
              'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ICDAdminSurface(SyntheticFixture,TestCase):
    client_class=SurfaceClient

    def test_services_shows_persisted_metadata_without_clinical_access(self):
        _user,_org,_department,_patient,_template,encounter,_blob=self.make_scope('icd-private')
        Encounter.objects.filter(pk=encounter.pk).update(notes='SYNTHETIC CLINICAL SENTINEL 20261003')
        CodeSet.objects.create(system='ICD-10-CM',version='FY2027',
            effective_from=date(2026,10,1),effective_until=date(2027,9,30),
            source_url='https://www.cms.gov/files/synthetic.txt',sha256='a'*64)
        admin=User.objects.create_user(username='icd-admin',email='icd-admin@synthetic.invalid',
                                      is_staff=True,verified_at=timezone.now())
        device=TOTPDevice.objects.create(user=admin,name='Synthetic authenticator',confirmed=True)
        self.client.force_login(admin)
        session=self.client.session;session['otp_device_id']=device.persistent_id;session.save()
        with patch('core.context.timezone.localdate',return_value=date(2026,10,3)):
            page=self.client.get('/console/services/')
        self.assertContains(page,'Current release: FY2027')
        self.assertContains(page,'2026-10-01 through 2027-09-30')
        self.assertNotContains(page,'SYNTHETIC CLINICAL SENTINEL 20261003')
        self.assertFalse(admin.membership_set.exists())
