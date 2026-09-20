"""Controlled private-email tests. Provider requests are mocked; no real mail."""

from pathlib import Path
import json
import subprocess
import sys
import tempfile
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.test import SimpleTestCase, override_settings
import httpx

from core.email_backend import (
    EmailDeliveryError, ResendEmailBackend, application_origin,
    private_access_instructions,
)
from core.email_delivery import deliver_account_email


RECIPIENT = "approved@synthetic.invalid"
GATE_USER = "synthetic-preview"
GATE_PASSWORD = "Synthetic-gate-only-5298!"
SETTINGS = {
    "QUILLMD_EMAIL_MODE": "resend",
    "EMAIL_BACKEND": "core.email_backend.ResendEmailBackend",
    "RESEND_API_KEY": "re_synthetic_test_credential",
    "QUILLMD_EMAIL_FROM": "QuillMD <verification@synthetic.invalid>",
    "QUILLMD_EMAIL_VERIFIED_DOMAIN": "synthetic.invalid",
    "QUILLMD_RESEND_ENV_FILE": "",
    "QUILLMD_APP_BASE_URL": "https://app.quillmd.com:9443",
    "QUILLMD_EMAIL_ALLOWED_RECIPIENTS": RECIPIENT,
    "QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME": GATE_USER,
    "QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD": GATE_PASSWORD,
}


def accepted():
    return httpx.Response(200, json={"id": "synthetic-provider-message-id"})


@override_settings(**SETTINGS)
class ControlledPrivateEmailTests(SimpleTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.mail_path = Path(directory.name) / "mail"
        setting = override_settings(EMAIL_FILE_PATH=self.mail_path)
        setting.enable()
        self.addCleanup(setting.disable)

    def message(self, recipient=RECIPIENT):
        return EmailMessage("Synthetic invitation", "Synthetic body", to=[recipient])

    @patch("core.email_backend.httpx.post", return_value=accepted())
    def test_approved_recipient_reaches_provider_once(self, post):
        self.assertEqual(ResendEmailBackend().send_messages([self.message()]), 1)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["json"]["to"], [RECIPIENT])

    @patch("core.email_backend.httpx.post")
    def test_wrong_recipient_is_refused_at_direct_transport_boundary(self, post):
        with self.assertRaises(EmailDeliveryError):
            ResendEmailBackend().send_messages([self.message("another@synthetic.invalid")])
        post.assert_not_called()

    @patch("core.email_backend.httpx.post")
    def test_partial_or_ambiguous_gate_configuration_never_sends(self, post):
        cases = (
            {"QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME": ""},
            {"QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD": ""},
            {"QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME": "bad:username"},
            {"QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD": "short"},
            {"QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD": GATE_PASSWORD + "\n"},
            {"QUILLMD_EMAIL_ALLOWED_RECIPIENTS": ""},
            {"QUILLMD_EMAIL_ALLOWED_RECIPIENTS": RECIPIENT + ",another@synthetic.invalid"},
            {"QUILLMD_EMAIL_ALLOWED_RECIPIENTS": RECIPIENT + ","},
        )
        for configuration in cases:
            with self.subTest(configuration_names=list(configuration)), override_settings(**configuration):
                with self.assertRaises(ImproperlyConfigured) as caught:
                    ResendEmailBackend().send_messages([self.message()])
                self.assertNotIn(GATE_PASSWORD, str(caught.exception))
                self.assertNotIn(GATE_USER, str(caught.exception))
        post.assert_not_called()

    @patch("core.email_backend.httpx.post")
    def test_private_gate_requires_same_valid_https_application_origin(self, post):
        for origin in (
            "http://app.quillmd.com:9443", "https://localhost:9443",
            "https://attacker.invalid:9443", "https://user:password@app.quillmd.com:9443",
            "https://app.quillmd.com:wrong", "https://app.quillmd.com:70000",
            "https://app.quillmd.com:9443/path", "https://app.quillmd.com:9443\n",
        ):
            with self.subTest(origin=origin), override_settings(QUILLMD_APP_BASE_URL=origin):
                with self.assertRaises(ImproperlyConfigured):
                    ResendEmailBackend().send_messages([self.message()])
        post.assert_not_called()

    @patch("core.email_delivery.audit")
    @patch("core.email_backend.httpx.post", return_value=accepted())
    def test_invitation_and_recovery_include_gate_without_rewriting_token_url(self, post, audit):
        for purpose, route in (("invitation", "invite"), ("recovery", "recovery/confirm")):
            with self.subTest(purpose=purpose):
                result = deliver_account_email(None, "synthetic-target", RECIPIENT, purpose, "synthetic-token")
                self.assertEqual(result.status, "accepted")
                body = post.call_args.kwargs["json"]["text"]
                self.assertIn(f"https://app.quillmd.com:9443/{route}/synthetic-token/", body)
                self.assertIn("Username: " + GATE_USER, body)
                self.assertIn("Password: " + GATE_PASSWORD, body)
                self.assertIn("separate from your QuillMD account password", body)
                self.assertNotIn(GATE_USER + ":" + GATE_PASSWORD + "@", body)
                details = str(audit.call_args)
                for sensitive in (GATE_PASSWORD, GATE_USER, "synthetic-token", RECIPIENT):
                    self.assertNotIn(sensitive, details)
        self.assertEqual(post.call_count, 2)
        self.assertFalse(self.mail_path.exists())

    @patch("core.email_delivery.audit")
    @patch("core.email_backend.httpx.post", return_value=accepted())
    def test_general_verification_does_not_receive_private_gate_credentials(self, post, audit):
        result = deliver_account_email(None, "synthetic-target", RECIPIENT, "verification", "synthetic-token")
        self.assertEqual(result.status, "accepted")
        body = post.call_args.kwargs["json"]["text"]
        self.assertNotIn(GATE_USER, body)
        self.assertNotIn(GATE_PASSWORD, body)

    @override_settings(QUILLMD_EMAIL_MODE="file", EMAIL_BACKEND="core.email_backend.PrivateFileEmailBackend")
    @patch("core.email_delivery.audit")
    @patch("core.email_backend.httpx.post")
    def test_private_outbox_mode_never_contains_gate_credentials(self, post, audit):
        result = deliver_account_email(None, "synthetic-target", RECIPIENT, "invitation", "synthetic-token")
        self.assertEqual(result.status, "outbox")
        post.assert_not_called()
        contents = next(self.mail_path.glob("*.log")).read_text()
        self.assertIn("synthetic-token", contents)
        self.assertNotIn(GATE_USER, contents)
        self.assertNotIn(GATE_PASSWORD, contents)

    @override_settings(QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME="")
    @patch("core.email_delivery.audit")
    @patch("core.email_backend.httpx.post")
    def test_partial_gate_is_safe_failure_with_token_recovery_and_redacted_audit(self, post, audit):
        result = deliver_account_email(None, "synthetic-target", RECIPIENT, "invitation", "synthetic-token")
        self.assertEqual(result.status, "failed")
        self.assertTrue(result.recovery_staged)
        post.assert_not_called()
        contents = next(self.mail_path.glob("*.log")).read_text()
        self.assertIn("synthetic-token", contents)
        self.assertNotIn(GATE_PASSWORD, contents)
        self.assertNotIn(GATE_PASSWORD, str(audit.call_args))
        self.assertNotIn("synthetic-token", str(audit.call_args))
        self.assertEqual(audit.call_args.args[1], "email.failed")
        self.assertEqual(audit.call_args.kwargs["error_class"], "ImproperlyConfigured")

    @patch("core.email_delivery.audit")
    @patch("core.email_backend.httpx.post", side_effect=httpx.ReadTimeout(GATE_PASSWORD))
    def test_uncertain_provider_failure_does_not_stage_or_audit_gate_credentials(self, post, audit):
        result = deliver_account_email(None, "synthetic-target", RECIPIENT, "recovery", "synthetic-token")
        self.assertEqual(result.status, "failed")
        self.assertTrue(result.recovery_staged)
        self.assertEqual(post.call_count, 1)
        contents = next(self.mail_path.glob("*.log")).read_text()
        self.assertIn("synthetic-token", contents)
        for sensitive in (GATE_USER, GATE_PASSWORD):
            self.assertNotIn(sensitive, contents)
            self.assertNotIn(sensitive, str(audit.call_args))

    @override_settings(QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME="", QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD="")
    @patch("core.email_backend.httpx.post", return_value=accepted())
    def test_allowlist_can_apply_without_private_credentials(self, post):
        self.assertEqual(private_access_instructions(RECIPIENT, "invitation"), "")
        self.assertEqual(ResendEmailBackend().send_messages([self.message()]), 1)
        with self.assertRaises(EmailDeliveryError):
            ResendEmailBackend().send_messages([self.message("another@synthetic.invalid")])
        self.assertEqual(post.call_count, 1)

    @override_settings(QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME="", QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD="", QUILLMD_EMAIL_ALLOWED_RECIPIENTS="")
    @patch("core.email_delivery.audit")
    @patch("core.email_backend.httpx.post", return_value=accepted())
    def test_normal_resend_without_private_configuration_preserves_original_body(self, post, audit):
        result = deliver_account_email(None, "synthetic-target", "another@synthetic.invalid", "invitation", "synthetic-token")
        self.assertEqual(result.status, "accepted")
        self.assertEqual(post.call_args.kwargs["json"]["text"],
                         "Accept your QuillMD department invitation at https://app.quillmd.com:9443/invite/synthetic-token/")

    def test_origin_never_embeds_gate_credentials(self):
        self.assertEqual(application_origin(), "https://app.quillmd.com:9443")


class PrivateProxySettingTests(SimpleTestCase):
    def test_proxy_trust_is_explicit_and_cannot_change_admin_loopback_behavior(self):
        for trust, admin, expected in (
            ("0", "0", None),
            ("1", "0", ["HTTP_X_FORWARDED_PROTO", "https"]),
            ("1", "1", None),
        ):
            with self.subTest(trust=trust, admin=admin):
                result = subprocess.run(
                    [sys.executable, "-c", "import json; from quillmd import settings; print(json.dumps(settings.SECURE_PROXY_SSL_HEADER))"],
                    cwd=Path(__file__).resolve().parents[2],
                    env={"QUILLMD_ENV_MANAGED": "1", "QUILLMD_SECRET_KEY": "synthetic-settings-check",
                         "QUILLMD_DB_PASSWORD": "unused-synthetic-check", "QUILLMD_TRUST_PROXY": trust,
                         "QUILLMD_ADMIN_SITE": admin},
                    capture_output=True, text=True, check=True, timeout=10,
                )
                self.assertEqual(json.loads(result.stdout), expected)
