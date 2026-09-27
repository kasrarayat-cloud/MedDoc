"""Account email copy: no 'test account' or 'synthetic' in real mode, and never clinical content.

Two proofs of the second property. Structurally, every subject and body template may carry exactly one
substitution field, {link}, so nothing from a patient, encounter, department or organization CAN be
interpolated. Behaviourally, every purpose is sent while records full of canary text exist, and none of
that text reaches the outbox. Email goes to a temporary private file outbox; nothing is sent.
"""
from pathlib import Path
from string import Formatter
import tempfile

from django.test import TestCase, override_settings
from django.utils import timezone

from core import email_delivery
from core.email_delivery import COPY, ROUTES, deliver_account_email
from core.models import Department, Encounter, Membership, Organization, Patient, Template, TemplateVersion, User

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
#: The exact synthetic-mode copy before this change. Default mode must not move a byte.
BEFORE = {
    'verification': ('Verify your QuillMD test account', 'Open {link} to verify your synthetic test account.'),
    'invitation': ('QuillMD department invitation', 'Accept your QuillMD department invitation at {link}'),
    'recovery': ('Recover your QuillMD test account', 'Recover your QuillMD test account at {link}. This link expires in 30 minutes. Administrators also need their enrolled authenticator.'),
}
CANARY = 'CANARYPHI'


def fields(template):
    return {name for _, name, _, _ in Formatter().parse(template) if name is not None}


class EmailTemplatesCannotCarryRecords(TestCase):
    def test_every_template_substitutes_only_the_link(self):
        self.assertEqual(set(COPY), {'synthetic', 'real'})
        for mode, purposes in COPY.items():
            self.assertEqual(set(purposes), set(ROUTES), mode)
            for purpose, (subject, body) in purposes.items():
                with self.subTest(mode=mode, purpose=purpose):
                    self.assertEqual(fields(subject), set())
                    self.assertEqual(fields(body), {'link'})

    def test_synthetic_copy_is_unchanged(self):
        for purpose, copy in BEFORE.items():
            with self.subTest(purpose=purpose):
                self.assertEqual(COPY['synthetic'][purpose], copy)

    def test_real_copy_drops_test_account_and_synthetic(self):
        for purpose, (subject, body) in COPY['real'].items():
            with self.subTest(purpose=purpose):
                for text in (subject, body):
                    self.assertNotIn('test account', text.lower())
                    self.assertNotIn('synthetic', text.lower())


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, QUILLMD_EMAIL_MODE='file',
                   EMAIL_BACKEND='core.email_backend.PrivateFileEmailBackend', QUILLMD_APP_BASE_URL='http://localhost:9130')
class SentEmailCarriesNoClinicalText(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.outbox = Path(directory.name)
        mail = override_settings(EMAIL_FILE_PATH=self.outbox)
        mail.enable()
        self.addCleanup(mail.disable)
        self.user = User.objects.create_user(username='mail@synthetic.invalid', email='mail@synthetic.invalid',
                                             first_name=f'{CANARY}first', last_name=f'{CANARY}last', verified_at=timezone.now())
        org = Organization.objects.create(name=f'{CANARY} organization')
        self.department = Department.objects.create(organization=org, name=f'{CANARY} department')
        Membership.objects.create(user=self.user, department=self.department, role='owner')
        patient = Patient.objects.create(department=self.department, display_name=f'{CANARY} patient name',
                                         reference=f'{CANARY}-MRN', created_by=self.user)
        template = Template.objects.create(department=self.department, name=f'{CANARY} form', format='docx',
                                           original_name='x.docx', original_path='originals/x.docx', sha256='0' * 64,
                                           created_by=self.user)
        version = TemplateVersion.objects.create(template=template, number=1, fields=[], created_by=self.user)
        Encounter.objects.create(department=self.department, patient=patient, template_version=version, created_by=self.user,
                                 service_date=timezone.localdate(), notes=f'{CANARY} chest pain history')

    def send_every_purpose(self):
        for purpose in ROUTES:
            delivery = deliver_account_email(self.user, self.user.pk, self.user.email, purpose, f'token-{purpose}',
                                             department=self.department)
            self.assertEqual(delivery.status, 'outbox')
        return '\n'.join(path.read_text() for path in self.outbox.glob('*.log'))

    def test_no_record_text_reaches_any_email_in_either_mode(self):
        for mode in (dict(SYNTHETIC_ONLY=True, QUILLMD_DATA_MODE='synthetic'), dict(SYNTHETIC_ONLY=False, QUILLMD_DATA_MODE='real')):
            with self.subTest(mode=mode['QUILLMD_DATA_MODE']), override_settings(**mode):
                for path in self.outbox.glob('*.log'):
                    path.unlink()
                sent = self.send_every_purpose()
                self.assertNotIn(CANARY, sent)
                for purpose, route in ROUTES.items():
                    self.assertIn(f'http://localhost:9130/{route}/token-{purpose}/', sent)

    @override_settings(SYNTHETIC_ONLY=False, QUILLMD_DATA_MODE='real')
    def test_real_mode_email_never_says_test_account_or_synthetic(self):
        sent = self.send_every_purpose().lower()
        self.assertNotIn('test account', sent)
        self.assertNotIn('synthetic', sent.replace('mail@synthetic.invalid', ''))
        self.assertIn('verify your quillmd account', sent)

    def test_default_mode_email_is_unchanged(self):
        sent = self.send_every_purpose()
        self.assertIn('Subject: Verify your QuillMD test account', sent)
        self.assertIn('Open http://localhost:9130/verify/token-verification/ to verify your synthetic test account.', sent)
        self.assertIs(email_delivery.account_copy('recovery'), COPY['synthetic']['recovery'])
