"""The restore preparation record and page name admission as the separate recorded step that exists, not as missing.

Before this change the page headline read "Admission unavailable" and the record carried only the 0028-pinned
`admission_available: false`, written when no admission step existed. Admission now exists (journal replay, then
core.restore_admission); the pinned fields keep their meaning for THIS record only. Synthetic data only.
"""
import uuid

from django.test import Client, TestCase, override_settings
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import disposition as d, models as m
from core.tests.test_retention_preservation import ISOLATED, Fixture


@override_settings(**ISOLATED)
class RestorePreparationSteps(Fixture, TestCase):
    def setUp(self): self.setup_records()

    def login(self):
        self.client = Client()
        device = TOTPDevice.objects.create(user=self.admin, name='Synthetic', confirmed=True)
        self.client.force_login(self.admin); session = self.client.session
        session['otp_device_id'] = device.persistent_id; session.save()

    def test_the_record_names_replay_then_admission_and_still_grants_nothing(self):
        instance = uuid.uuid4()
        with override_settings(RESTORE_QUARANTINE=True, RESTORE_INSTANCE_ID=str(instance)):
            row = d.prepare_restore(self.admin, instance, 'a'*64)
        self.assertEqual(row.report['next_steps'], ['journal_replay', 'restore_admission'])
        # 0028's pins are unchanged: this record admits nothing and proves no journal freshness.
        self.assertEqual((row.report['admission_available'], row.report['journal_freshness_verified']), (False, False))
        self.assertIn('restore_admission_pending', row.report['blockers'])

    def test_the_page_names_the_admission_step_instead_of_calling_it_unavailable(self):
        self.login()
        with override_settings(RESTORE_QUARANTINE=True, RESTORE_INSTANCE_ID=str(uuid.uuid4()), ADMIN_SITE=True):
            page = self.client.get('/console/restore-preparation/')
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'Admission unavailable')  # ac43e379: the headline
        self.assertContains(page, 'Preparation does not admit this target.')
        self.assertContains(page, 'manage.py restore_admission')
        self.assertContains(page, 'href="/console/disposition-execution/"')
        self.assertFalse(m.RestoreAdmission.objects.exists())
