"""Account-email integration tests. Every provider request is mocked."""

from datetime import timedelta
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
import httpx

from core.email_backend import EmailDeliveryError, PrivateFileEmailBackend, ResendEmailBackend, resend_configuration
from core.models import AuditEvent, Department, Invitation, Membership, Organization, User, Verification, Wallet


RESEND_SETTINGS = {
    "QUILLMD_EMAIL_MODE": "resend",
    "EMAIL_BACKEND": "core.email_backend.ResendEmailBackend",
    "RESEND_API_KEY": "re_synthetic_test_credential",
    "QUILLMD_EMAIL_FROM": "QuillMD <verification@synthetic.invalid>",
    "QUILLMD_EMAIL_VERIFIED_DOMAIN": "synthetic.invalid",
    "QUILLMD_RESEND_ENV_FILE": "",
    "QUILLMD_APP_BASE_URL": "https://app.quillmd.com",
    "ADMIN_SITE": False,
    "STORAGES": {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
}


def accepted():
    return httpx.Response(200, json={"id": "synthetic-provider-message-id"})


@override_settings(**RESEND_SETTINGS)
class ResendAdapterTests(SimpleTestCase):
    def message(self):
        return EmailMessage("Synthetic verification", "https://app.quillmd.com/verify/synthetic-link-only/", to=["person@synthetic.invalid"])

    @patch("core.email_backend.httpx.post", return_value=accepted())
    def test_documented_api_payload_and_stable_idempotency(self, post):
        first, second = self.message(), self.message()
        backend = ResendEmailBackend()
        self.assertEqual(backend.send_messages([first]), 1)
        self.assertEqual(backend.send_messages([second]), 1)
        self.assertEqual(first.provider_message_id, "synthetic-provider-message-id")
        kwargs = post.call_args.kwargs
        self.assertEqual(post.call_args.args[0], "https://api.resend.com/emails")
        self.assertEqual(kwargs["json"], {"from": RESEND_SETTINGS["QUILLMD_EMAIL_FROM"], "to": first.to, "subject": first.subject, "text": first.body})
        self.assertFalse(kwargs["follow_redirects"])
        self.assertEqual(post.call_args_list[0].kwargs["headers"]["Idempotency-Key"], post.call_args_list[1].kwargs["headers"]["Idempotency-Key"])
        self.assertNotIn("synthetic-link-only", kwargs["headers"]["Idempotency-Key"])

    @override_settings(QUILLMD_EMAIL_MODE="file")
    @patch("core.email_backend.httpx.post")
    def test_file_mode_cannot_accidentally_call_provider(self, post):
        with self.assertRaises(ImproperlyConfigured):
            ResendEmailBackend().send_messages([self.message()])
        post.assert_not_called()

    @patch("core.email_backend.httpx.post")
    def test_missing_verified_sender_or_https_origin_prevents_send(self, post):
        for settings in ({"QUILLMD_EMAIL_VERIFIED_DOMAIN": ""}, {"QUILLMD_EMAIL_VERIFIED_DOMAIN": "wrong.invalid"}, {"QUILLMD_APP_BASE_URL": "http://localhost:9130"}, {"QUILLMD_APP_BASE_URL": "https://attacker.invalid"}):
            with self.subTest(settings=settings), override_settings(**settings), self.assertRaises(ImproperlyConfigured):
                ResendEmailBackend().send_messages([self.message()])
        post.assert_not_called()

    @patch("core.email_backend.httpx.post", side_effect=httpx.ReadTimeout("provider error containing re_synthetic_test_credential"))
    def test_timeout_is_safe_and_not_retried(self, post):
        with self.assertRaises(EmailDeliveryError) as caught:
            ResendEmailBackend().send_messages([self.message()])
        self.assertEqual(post.call_count, 1)
        self.assertNotIn("re_synthetic_test_credential", str(caught.exception))
        self.assertIn("uncertain", str(caught.exception))

    def test_error_and_malformed_success_never_claim_acceptance(self):
        for response in (httpx.Response(422, json={"message": "secret provider error body"}), httpx.Response(200, json={"missing": "id"}), httpx.Response(200, text="not JSON")):
            with self.subTest(status=response.status_code), patch("core.email_backend.httpx.post", return_value=response), self.assertRaises(EmailDeliveryError) as caught:
                ResendEmailBackend().send_messages([self.message()])
            self.assertNotIn("secret provider", str(caught.exception))

    @patch("core.email_backend.httpx.post")
    def test_unsupported_attachments_are_rejected_not_silently_dropped(self, post):
        message = self.message()
        message.attach("synthetic.txt", "do not silently drop", "text/plain")
        with self.assertRaises(EmailDeliveryError):
            ResendEmailBackend().send_messages([message])
        post.assert_not_called()

    @patch("core.email_backend.httpx.post", return_value=accepted())
    def test_selected_credentials_can_use_protected_preserved_file(self, post):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.env"
            path.write_text("RESEND_API_KEY=re_synthetic_preserved\nRESEND_FROM=QuillMD <verification@synthetic.invalid>\nDATABASE_URL=never-import-this-old-setting\n")
            path.chmod(0o600)
            with override_settings(RESEND_API_KEY="", QUILLMD_EMAIL_FROM="", QUILLMD_RESEND_ENV_FILE=str(path)):
                self.assertEqual(ResendEmailBackend().send_messages([self.message()]), 1)
                self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer re_synthetic_preserved")
                path.chmod(0o644)
                with self.assertRaises(ImproperlyConfigured):
                    resend_configuration()

    def test_private_outbox_permissions_precede_sensitive_content(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = PrivateFileEmailBackend(file_path=Path(directory) / "outbox")
            self.assertEqual(backend.send_messages([self.message()]), 1)
            path = next((Path(directory) / "outbox").glob("*.log"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            self.assertIn("synthetic-link-only", path.read_text())


@override_settings(**RESEND_SETTINGS)
class AccountDeliveryTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.override = override_settings(EMAIL_FILE_PATH=Path(self.directory.name) / "mail")
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.directory.cleanup)

    def registration(self):
        return self.client.post("/register/", {"email": "newemail@synthetic.invalid", "first_name": "Synthetic", "last_name": "Email", "password1": "Synthetic-Only-4821!private", "password2": "Synthetic-Only-4821!private", "synthetic_only": "on"})

    @patch("core.email_backend.httpx.post", return_value=httpx.Response(503, json={"message": "synthetic unavailable"}))
    def test_signup_delivery_failure_keeps_unverified_account_without_500(self, post):
        response = self.registration()
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="newemail@synthetic.invalid")
        self.assertIsNone(user.verified_at)
        self.assertEqual(Verification.objects.filter(user=user).count(), 1)
        self.assertFalse(Wallet.objects.filter(user=user).exists())
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(any("could not be confirmed" in message for message in messages))
        audit = AuditEvent.objects.get(action="email.failed")
        self.assertTrue(audit.details["recovery_staged"])
        self.assertNotIn(user.email, str(audit.details))
        path = next((Path(self.directory.name) / "mail").glob("*.log"))
        self.assertIn("https://app.quillmd.com/verify/", path.read_text())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(post.call_count, 1)

    @patch("core.email_backend.httpx.post", return_value=accepted())
    def test_signup_acceptance_is_recorded_without_claiming_inbox_delivery(self, post):
        response = self.registration()
        self.assertEqual(response.status_code, 302)
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(any("submitted to the email provider" in message for message in messages))
        self.assertTrue(any("not yet confirmed" in message for message in messages))
        self.assertEqual(AuditEvent.objects.get(action="email.accepted").details["provider_message_id"], "synthetic-provider-message-id")
        self.assertFalse(Wallet.objects.exists())

    @patch("core.email_backend.httpx.post", side_effect=httpx.ReadTimeout("synthetic only"))
    def test_invitation_timeout_keeps_invitation_with_honest_status(self, post):
        owner = User.objects.create_user(username="email-owner", email="owner@synthetic.invalid", verified_at=timezone.now())
        org = Organization.objects.create(name="Synthetic email practice")
        dept = Department.objects.create(organization=org, name="X-ray")
        Membership.objects.create(user=owner, department=dept, role="owner")
        self.client.force_login(owner)
        response = self.client.post("/team/", {"department": dept.pk, "email": "employee@synthetic.invalid", "role": "employee"})
        self.assertEqual(response.status_code, 302)
        invite = Invitation.objects.get(email="employee@synthetic.invalid")
        self.assertIsNone(invite.accepted_at)
        self.assertEqual(AuditEvent.objects.get(action="email.failed").target, str(invite.pk))
        self.assertTrue(any("could not be confirmed" in str(message) for message in get_messages(response.wsgi_request)))
        self.assertEqual(post.call_count, 1)

    @patch("core.email_delivery.PrivateFileEmailBackend", side_effect=OSError("synthetic local storage unavailable"))
    @patch("core.email_backend.httpx.post", side_effect=httpx.ReadTimeout("synthetic provider timeout"))
    def test_signup_survives_transport_and_recovery_storage_failure(self, post, private_backend):
        response = self.registration()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AuditEvent.objects.get(action="email.failed").details["recovery_staged"])
        self.assertEqual(User.objects.filter(email="newemail@synthetic.invalid").count(), 1)
