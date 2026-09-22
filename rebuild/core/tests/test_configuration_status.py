"""The configuration report must be incapable of printing a secret."""
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

SECRET = 'sk_test_thisvaluemustneverbeprinted'


class ConfigurationStatusDisclosesNothing(SimpleTestCase):
    def report(self):
        out = StringIO()
        call_command('configuration_status', stdout=out)
        return out.getvalue()

    @override_settings(STRIPE_SECRET_KEY=SECRET, STRIPE_WEBHOOK_SECRET='whsec_alsosecret',
                       RESEND_API_KEY='re_alsosecret')
    def test_no_configured_secret_appears_in_the_output(self):
        report = self.report()
        for secret in (SECRET, 'whsec_alsosecret', 're_alsosecret'):
            self.assertNotIn(secret, report)
            self.assertNotIn(secret[8:], report)

    @override_settings(STRIPE_SECRET_KEY='sk_test_synthetic1234', RESEND_API_KEY='re_x')
    def test_a_configured_credential_is_reported_as_present_with_its_shape(self):
        report = self.report()
        self.assertIn('STRIPE_SECRET_KEY: present, recognised shape', report)
        self.assertIn('RESEND_API_KEY: present', report)

    @override_settings(STRIPE_SECRET_KEY='sk_live_realkeyshapewrongmode', RESEND_API_KEY='')
    def test_an_unexpected_shape_is_named_as_unrecognised_rather_than_shown(self):
        report = self.report()
        self.assertIn('STRIPE_SECRET_KEY: present, UNRECOGNISED shape', report)
        self.assertNotIn('sk_live', report)
        self.assertIn('RESEND_API_KEY: absent', report)

    def test_the_release_gates_are_reported(self):
        report = self.report()
        self.assertIn('SYNTHETIC_ONLY: True', report)
        self.assertIn('STRIPE_LIVE_ENABLED: False', report)

    def test_both_media_tools_are_named_whether_present_or_missing(self):
        """The degraded path works, which is why its cause has to be on an operator's screen.

        Without ffprobe every recording reports coverage UNKNOWN; without ffmpeg every recording is submitted exactly as
        uploaded. Both are correct behaviour and neither raises anything, so the only way anyone learns which one is in
        effect is by being told here.
        """
        import shutil
        from unittest.mock import patch
        report = self.report()
        self.assertIn('ffprobe:', report)
        self.assertIn('ffmpeg:', report)
        with patch.object(shutil, 'which', return_value=None):
            missing = self.report()
        # ⚠️ The sentences these assertions pinned became FALSE when the fallback was removed, and the assertions
        # happily kept pinning them. A test that locks in a screen's wording is only ever as true as the wording.
        self.assertEqual(missing.count('EVERY recording is refused before the provider'), 2)
        self.assertNotIn('submitted exactly as uploaded', missing)


class HealthReportsTheGuardRatherThanAsserting(SimpleTestCase):
    """⚠️ `data_mode` WAS A HARDCODED LITERAL AND WAS BEING READ AS PROOF OF THE GUARD.

    `/health/` printed `synthetic-only` unconditionally. It would have kept printing it with
    `SYNTHETIC_ONLY` set to False, so every check that cited `/health/` as evidence of
    synthetic-only operation — including this programme's own post-reboot and post-activation
    checks — was reading a label that could not disagree with itself.

    A field that cannot report the bad case is not evidence; it is decoration that looks like
    evidence, which is worse than no field at all.
    """

    @override_settings(SYNTHETIC_ONLY=True)
    def test_it_reports_synthetic_only_when_the_guard_is_on(self):
        self.assertEqual(self.client.get('/health/').json()['data_mode'], 'synthetic-only')

    @override_settings(SYNTHETIC_ONLY=False)
    def test_it_reports_live_when_the_guard_is_off(self):
        """⚠️ THE POSITIVE CONTROL, AND THE WHOLE POINT. Before the repair this assertion was
        impossible to satisfy: the literal could not move."""
        self.assertEqual(self.client.get('/health/').json()['data_mode'], 'live')

    @override_settings(SYNTHETIC_ONLY=True)
    def test_the_configuration_report_names_the_same_setting_the_health_field_derives_from(self):
        """Two surfaces, one fact. If they ever disagree, one of them is lying, and the point of
        deriving the field was to make that impossible."""
        self.assertIn('SYNTHETIC_ONLY: True', self.report())

    def report(self):
        out = StringIO()
        call_command('configuration_status', stdout=out)
        return out.getvalue()
