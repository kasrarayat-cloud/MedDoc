"""The configuration report must be incapable of printing a secret."""
import json
import os
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from core import generation as g
from core.tests.test_sonnet5_profile import (PRICE_ENV, ROLLBACK_FINGERPRINT, SONNET_5, SONNET_5_DISABLED_MEDIUM,
                                             SONNET_46)

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


class ConfigurationStatusNamesTheModel(SimpleTestCase):
    """The language-model section: which model, at which rates, sending which request, under which pricing version.

    Plain configuration values, printed so the owner can confirm a model switch or a rollback from the one screen built for
    it (docs/rebuild/v1/sonnet5-migration.md). The credential beside them stays status-only.
    """

    def report(self, **overrides):
        out = StringIO()
        with override_settings(**overrides), patch.dict(os.environ, {**PRICE_ENV,
                                                                     'ANTHROPIC_API_KEY': 'sk-ant-canary-never-shown'}):
            call_command('configuration_status', stdout=out)
            config = g.configuration()
        return out.getvalue(), config

    def test_the_model_rates_profile_and_pricing_version_are_printed(self):
        report, config = self.report(**SONNET_5)
        for line in ('QUILLMD_AI_MODEL: claude-sonnet-5', 'QUILLMD_AI_INPUT_RATE: 2', 'QUILLMD_AI_OUTPUT_RATE: 10',
                     'QUILLMD_AI_CACHED_RATE: 0.20', 'QUILLMD_AI_THINKING: disabled', 'QUILLMD_AI_EFFORT: medium',
                     'QUILLMD_AI_INFERENCE_GEO: (unset)',
                     'request profile: explicit ' + json.dumps(config['request_profile'], sort_keys=True),
                     f'pricing_version: {SONNET_5_DISABLED_MEDIUM}'):
            self.assertIn(line, report)
        self.assertNotIn('canary', report)
        self.assertIn('ANTHROPIC_API_KEY: present', report)

    def test_the_rollback_profile_is_named_as_the_unchanged_legacy_request(self):
        report, config = self.report(**SONNET_46)
        self.assertEqual(config['request_profile'], g.LEGACY_PROFILE)
        self.assertIn('request profile: legacy (the pre-profile request, unchanged) '
                      + json.dumps(g.LEGACY_PROFILE, sort_keys=True), report)
        self.assertIn(f'pricing_version: {ROLLBACK_FINGERPRINT}', report)

    def test_the_4_6_model_with_us_geography_is_not_called_the_pre_profile_request(self):
        """S5-R2. The rollback values with QUILLMD_AI_INFERENCE_GEO=us left in place send `inference_geo`, hold 1.1x and
        fingerprint away from fcc80267 — and the screen called that 'legacy (the pre-profile request, unchanged)', which is
        the very line the rollback check looks for. 'legacy' is printed only when the profile IS the legacy profile."""
        report, config = self.report(**dict(SONNET_46, AI_INFERENCE_GEO='us'))
        self.assertNotEqual(config['request_profile'], g.LEGACY_PROFILE)
        self.assertNotIn('request profile: legacy', report)
        self.assertNotIn('the pre-profile request, unchanged', report)
        self.assertIn('request profile: NOT the pre-profile request: legacy-v1 plus inference_geo us '
                      + json.dumps(config['request_profile'], sort_keys=True), report)
        self.assertNotIn(ROLLBACK_FINGERPRINT, report)

    def test_an_invalid_profile_is_named_as_refusing_every_generation(self):
        report, _ = self.report(**dict(SONNET_5, AI_EFFORT='max'))
        self.assertIn('request profile: INVALID — every generation is refused before any request: '
                      'QUILLMD_AI_EFFORT must be one of: low, medium, high.', report)

    def test_the_browser_mirror_carries_every_language_model_line(self):
        """S5-R3. `admin_console.configuration_rows()` — what the services page renders — says it is everything this
        command prints, and after the language-model section landed it carried none of it: no model, no rates, no
        request profile, no pricing_version, and no INVALID state that refuses every generation. Each line the terminal
        prints under 'Language model' must be a row of the browser mirror, in the same order, for every profile state."""
        from core import admin_console
        cases = {'sonnet 5': SONNET_5, 'invalid effort': dict(SONNET_5, AI_EFFORT='max'), 'rollback': SONNET_46,
                 'rollback + us': dict(SONNET_46, AI_INFERENCE_GEO='us'),
                 'unlisted claude id': dict(SONNET_46, AI_MODEL='claude-mythos-preview')}
        for label, overrides in cases.items():
            for discount in ('0', 'x'):
                with self.subTest(case=label, discount=discount), override_settings(**overrides), \
                        patch.dict(os.environ, {**PRICE_ENV, 'QUILLMD_PROVIDER_DISCOUNT_RATE': discount,
                                                'ANTHROPIC_API_KEY': 'sk-ant-canary-never-shown'}):
                    out = StringIO()
                    call_command('configuration_status', stdout=out)
                    rows = admin_console.configuration_rows()
                    lines = out.getvalue().splitlines()
                    start = lines.index('Language model (plain configuration values, shown so a model switch can be '
                                        'confirmed):')
                    section = [line.strip() for line in lines[start + 1:lines.index('Media tools:')]]
                    mirror = [f"{row['name']}: {row['value']}" for row in rows.get('language_model', [])]
                    self.assertEqual(len(section), 9)                  # 7 settings + request profile + pricing_version
                    self.assertEqual(mirror, section)
                    self.assertNotIn('canary', repr(rows))
                    by_name = {row['name']: row for row in rows.get('language_model', [])}
                    profile = by_name.get('request profile', {})
                    if label in ('invalid effort', 'unlisted claude id') or discount == 'x':
                        self.assertEqual(profile.get('severity'), 'error')
                        self.assertTrue(profile.get('value', '').startswith(('INVALID — every generation is refused',
                                                                              'UNAVAILABLE')))

    def test_a_refused_discount_is_reported_without_stopping_the_screen(self):
        out = StringIO()
        with override_settings(**SONNET_5), patch.dict(os.environ, {**PRICE_ENV, 'QUILLMD_PROVIDER_DISCOUNT_RATE': 'x'}):
            call_command('configuration_status', stdout=out)
        self.assertIn('pricing_version: UNAVAILABLE', out.getvalue())
        self.assertIn('Release gates:', out.getvalue())
