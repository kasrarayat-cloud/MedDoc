"""QUILLMD_STRIPE_MODE: 'test' is byte-identical to before; 'live' is its own namespace.

No charge is made: every Checkout call is a mock, every webhook is signed locally with a synthetic secret.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

from django.core import signing
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from core.billing import record_stripe_event, stripe_key_configured
from core.models import LedgerEntry, Payment, Wallet, WebhookEvent
from core.stripe_validation import validate_event_environment
from core.tests.test_security import SyntheticFixture

SECRET = 'whsec_synthetic_live_mode'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
LIVE = dict(QUILLMD_STRIPE_MODE='live', STRIPE_LIVE_ENABLED=True, QUILLMD_APP_BASE_URL='https://app.quillmd.com')
REBUILD = Path(__file__).resolve().parents[2]


class KeysBelongToOneMode(SimpleTestCase):
    def test_test_mode_accepts_only_sandbox_keys(self):
        for key, accepted in (('sk_test_synthetic', True), ('rk_test_synthetic', True),
                              ('sk_live_synthetic', False), ('rk_live_synthetic', False), ('pk_live_synthetic', False)):
            with self.subTest(key=key[:8]):
                self.assertEqual(stripe_key_configured(key), accepted)

    @override_settings(QUILLMD_STRIPE_MODE='live')
    def test_live_mode_accepts_only_live_server_keys(self):
        for key, accepted in (('sk_live_synthetic', True), ('rk_live_synthetic', True), ('sk_test_synthetic', False),
                              ('rk_test_synthetic', False), ('pk_live_synthetic', False), ('whsec_synthetic', False),
                              ('sk_live_', False), (' sk_live_synthetic', False), ('sk_live_a\n', False), (None, False)):
            with self.subTest(key=repr(key)[:12]):
                self.assertEqual(stripe_key_configured(key), accepted)


def start(env):
    base = {'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_SECRET_KEY': 'synthetic-settings-check',
            'QUILLMD_DB_PASSWORD': 'unused-synthetic-check', 'PATH': os.environ.get('PATH', '')}
    return subprocess.run([sys.executable, '-B', '-c', 'from quillmd import settings as s; print(s.STRIPE_LIVE_ENABLED)'],
                          cwd=REBUILD, env={**base, **env}, capture_output=True, text=True, timeout=30)


class LiveModeRefusesToStartHalfConfigured(SimpleTestCase):
    COMPLETE = {'QUILLMD_STRIPE_MODE': 'live', 'STRIPE_SECRET_KEY': 'rk_live_synthetic_never_real',
                'STRIPE_WEBHOOK_SECRET': 'whsec_synthetic_never_real', 'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com'}

    def test_complete_live_configuration_starts(self):
        result = start(self.COMPLETE)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'True'), result.stderr)

    def test_each_gap_refuses_and_names_the_setting_not_the_value(self):
        for name, value in (('STRIPE_SECRET_KEY', 'sk_test_synthetic_never_real'), ('STRIPE_SECRET_KEY', ''),
                            ('STRIPE_SECRET_KEY', ' rk_live_synthetic_never_real'),
                            ('STRIPE_WEBHOOK_SECRET', ''), ('QUILLMD_APP_BASE_URL', 'http://localhost:9130'),
                            ('QUILLMD_APP_BASE_URL', '')):
            with self.subTest(name=name, value=value):
                result = start({**self.COMPLETE, name: value})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(name, result.stderr.strip().splitlines()[-1])
                self.assertNotIn('synthetic_never_real', result.stderr)

    def test_test_mode_starts_whatever_key_is_present_as_before(self):
        """Test mode's startup is today's: a live key there is refused at checkout, not at start."""
        result = start({'STRIPE_SECRET_KEY': 'sk_live_synthetic_never_real'})
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'False'), result.stderr)


def event(livemode, obj=None, event_id='evt_synthetic_live'):
    return {'id': event_id, 'object': 'event', 'type': 'checkout.session.completed', 'livemode': livemode,
            'data': {'object': obj or {}}}


class WebhookNamespaces(SimpleTestCase):
    def test_test_mode_keeps_only_livemode_false(self):
        validate_event_environment(event(False))
        with self.assertRaisesRegex(ValidationError, 'test-mode'):
            validate_event_environment(event(True))

    @override_settings(QUILLMD_STRIPE_MODE='live')
    def test_live_mode_keeps_only_livemode_true(self):
        validate_event_environment(event(True))
        for livemode in (False, None, 1, 'true'):
            with self.subTest(livemode=livemode), self.assertRaisesRegex(ValidationError, 'live-mode'):
                validate_event_environment(event(livemode))
        # Connected-account and organization-context events stay refused in live mode too.
        with self.assertRaises(ValidationError):
            validate_event_environment({**event(True), 'account': 'acct_synthetic_other'})

    @override_settings(QUILLMD_STRIPE_MODE='live')
    def test_live_recorder_refuses_a_sandbox_object_before_any_write(self):
        with patch('core.billing.WebhookEvent.objects.get_or_create') as create, self.assertRaises(ValidationError):
            record_stripe_event(event(True, {'id': 'cs_test_x', 'livemode': False}), 'synthetic-hash')
        create.assert_not_called()


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class LiveCheckoutAndSettlement(SyntheticFixture, TestCase):
    def setUp(self):
        self.user = self.make_scope('stripe-live')[0]
        self.client.force_login(self.user)

    def checkout(self, nonce):
        token = signing.dumps({'user': str(self.user.pk), 'nonce': nonce}, salt='checkout-authorization')
        session = SimpleNamespace(id=f'cs_{nonce}', url='https://checkout.stripe.com/c/pay/synthetic')
        with patch('stripe.checkout.Session.create', return_value=session) as api:
            response = self.client.post('/billing/checkout/', {'amount': '10.00', 'consent': 'on', 'checkout_token': token})
        return response, api

    @override_settings(STRIPE_SECRET_KEY='rk_test_synthetic_adapter')
    def test_test_mode_request_is_unchanged(self):
        response, api = self.checkout('test-mode-click')
        self.assertEqual(response.status_code, 302)
        kwargs = api.call_args.kwargs
        self.assertEqual(kwargs['success_url'], 'http://localhost:9130/billing/?payment=processing')
        self.assertEqual(kwargs['cancel_url'], 'http://localhost:9130/billing/')
        self.assertEqual(kwargs['line_items'][0]['price_data']['product_data']['name'], 'QuillMD one-time wallet credit (test)')

    @override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **LIVE)
    def test_live_mode_returns_to_the_public_origin_without_a_test_label(self):
        response, api = self.checkout('live-mode-click')
        self.assertEqual(response.status_code, 302)
        kwargs = api.call_args.kwargs
        self.assertEqual(kwargs['api_key'], 'rk_live_synthetic_adapter')
        self.assertEqual(kwargs['success_url'], 'https://app.quillmd.com/billing/?payment=processing')
        self.assertEqual(kwargs['cancel_url'], 'https://app.quillmd.com/billing/')
        self.assertEqual(kwargs['line_items'][0]['price_data']['product_data']['name'], 'QuillMD one-time wallet credit')
        self.assertNotIn('localhost', json.dumps(kwargs, default=str))

    @override_settings(STRIPE_SECRET_KEY='sk_test_synthetic_adapter', **LIVE)
    def test_a_test_key_in_live_mode_is_refused_before_any_provider_call(self):
        response, api = self.checkout('wrong-key-click')
        self.assertEqual(response.status_code, 302)
        api.assert_not_called()
        self.assertFalse(Payment.objects.exists())
        self.assertIn('live or restricted live key', str(list(response.wsgi_request._messages)[0]))

    @override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', QUILLMD_STRIPE_MODE='live',
                       QUILLMD_APP_BASE_URL='http://localhost:9130')
    def test_live_mode_never_returns_a_payer_to_localhost(self):
        response, api = self.checkout('localhost-click')
        api.assert_not_called()
        self.assertFalse(Payment.objects.exists())

    def signed(self, payload):
        body = json.dumps(payload).encode()
        stamp = str(int(time.time()))
        signature = hmac.new(SECRET.encode(), stamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
        return self.client.post('/billing/webhook/', body, content_type='application/json', HTTP_STRIPE_SIGNATURE=f't={stamp},v1={signature}')

    @override_settings(**LIVE)
    def test_live_mode_credits_a_live_event_and_refuses_a_sandbox_one(self):
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        payment = Payment.objects.create(user=self.user, wallet=wallet, amount_cents=1000, stripe_session='cs_live_synthetic')
        session = {'id': payment.stripe_session, 'payment_status': 'paid', 'currency': 'usd', 'amount_total': 1000,
                   'metadata': {'payment_id': str(payment.pk)}, 'payment_intent': 'pi_live_synthetic', 'mode': 'payment',
                   'livemode': True}
        self.assertEqual(self.signed(event(False, {**session, 'livemode': False}, 'evt_sandbox')).status_code, 400)
        self.assertFalse(WebhookEvent.objects.exists())
        self.assertEqual(self.signed(event(True, session, 'evt_live')).status_code, 200)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 10)
        self.assertEqual(LedgerEntry.objects.filter(wallet=wallet, kind='payment').count(), 1)
