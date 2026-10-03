"""Sandbox gating stays pure; persisted integration metadata uses an isolated database."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from core.billing import stripe_test_key_configured
from core.context import integration_status
from core.views import checkout
from core.models import CodeSet, Job, LedgerEntry, Payment, Reservation, Usage


class StripeCredentialTests(SimpleTestCase):
    def test_standard_and_restricted_sandbox_keys_are_accepted(self):
        for key in ('sk_test_synthetic_adapter', 'rk_test_synthetic_adapter'):
            with self.subTest(prefix=key[:8]):
                self.assertTrue(stripe_test_key_configured(key))

    def test_live_publishable_webhook_and_malformed_values_are_rejected(self):
        for key in ('sk_live_synthetic', 'rk_live_synthetic', 'pk_test_synthetic',
                    'pk_live_synthetic', 'whsec_synthetic', 'sk_org_synthetic',
                    'sk_test_', 'rk_test_', ' rk_test_synthetic',
                    'rk_test_synthetic\n', 'rk_test_a b', 'rk_test_é',
                    'rk_test_a;anything', 'sk_test_a/rk_live_b', '', None, 1):
            with self.subTest(value=key):
                self.assertFalse(stripe_test_key_configured(key))

    def request(self):
        request = RequestFactory().post('/billing/checkout/', {'amount': '10.00'})
        request.user = SimpleNamespace(pk='synthetic-user')
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_restricted_key_reaches_authorization_gate_without_payment_call(self):
        request = self.request()
        with override_settings(STRIPE_SECRET_KEY='rk_test_synthetic_adapter'), \
                patch('core.billing.checkout_form', return_value=SimpleNamespace(is_valid=lambda: True)), \
                patch('core.views.signing.loads', return_value={'user': 'wrong-user', 'nonce': 'synthetic'}) as token, \
                patch('stripe.checkout.Session.create') as provider:
            response = checkout(request)
        self.assertEqual(response.status_code, 302)
        token.assert_called_once()
        provider.assert_not_called()
        self.assertEqual([str(message) for message in request._messages],
                         ['Reload billing to authorize this one-time checkout.'])

    def test_live_keys_stop_before_authorization_and_provider(self):
        for key in ('sk_live_synthetic', 'rk_live_synthetic'):
            request = self.request()
            with self.subTest(prefix=key[:8]), override_settings(STRIPE_SECRET_KEY=key), \
                    patch('core.billing.checkout_form', return_value=SimpleNamespace(is_valid=lambda: True)), \
                    patch('core.views.signing.loads') as token, \
                    patch('stripe.checkout.Session.create') as provider:
                response = checkout(request)
                self.assertEqual(response.status_code, 302)
                token.assert_not_called()
                provider.assert_not_called()
                self.assertIn('test or restricted test key', str(list(request._messages)[0]))

class StripeIntegrationConfigurationTests(TestCase):
    """The full interface reads real release metadata; it still makes no payment request."""
    def test_interface_labels_configuration_without_claiming_provider_verification(self):
        for key in ('sk_test_synthetic', 'rk_test_synthetic', 'rk_live_synthetic'):
            with self.subTest(prefix=key[:8]), override_settings(STRIPE_SECRET_KEY=key), \
                    patch('stripe.checkout.Session.create') as provider:
                payments = next(row for row in integration_status() if row['name'] == 'Payments')
                self.assertEqual(payments['status'],
                                 'Not connected' if '_live_' in key else 'Stripe sandbox key configured')
                self.assertIn('does not verify payments', payments['detail'])
                provider.assert_not_called()

    def test_current_expired_and_gap_icd_metadata_are_read_without_financial_mutation(self):
        for version, first, last, digest in (
                ('Synthetic FY2026', date(2025, 10, 1), date(2026, 3, 31), 'a'),
                ('Synthetic FY2027', date(2026, 10, 1), date(2027, 9, 30), 'b')):
            CodeSet.objects.create(system='ICD-10-CM', version=version, effective_from=first,
                effective_until=last, source_url='https://example.invalid/synthetic-icd', sha256=digest * 64)
        before = list(CodeSet.objects.order_by('pk').values())
        for today, status in ((date(2026, 10, 3), 'Current release: Synthetic FY2027'),
                              (date(2027, 10, 1), 'No release covers today'),
                              (date(2026, 5, 1), 'No release covers today')):
            with self.subTest(today=today), patch('core.context.timezone.localdate', return_value=today), \
                    patch('stripe.checkout.Session.create') as provider:
                rows = integration_status()
                icd = next(row for row in rows if row['name'] == 'ICD-10-CM terminology')
                self.assertEqual(icd['status'], status)
                self.assertIn('Each encounter uses its date of service', icd['detail'])
                self.assertIn('Suggestions require clinician review', icd['detail'])
                self.assertIn('2 loaded release(s)', icd['detail'])
                self.assertIn('does not verify payments', next(row for row in rows if row['name'] == 'Payments')['detail'])
                provider.assert_not_called()
        self.assertEqual(list(CodeSet.objects.order_by('pk').values()), before)
        for model in (Job, Reservation, Usage, Payment, LedgerEntry):
            self.assertEqual(model.objects.count(), 0)
