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
                'STRIPE_WEBHOOK_SECRET': 'whsec_SyntheticNeverReal0001', 'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com'}

    def test_complete_live_configuration_starts(self):
        result = start(self.COMPLETE)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'True'), result.stderr)

    def test_each_gap_refuses_and_names_the_setting_not_the_value(self):
        for name, value in (('STRIPE_SECRET_KEY', 'sk_test_synthetic_never_real'), ('STRIPE_SECRET_KEY', ''),
                            ('STRIPE_SECRET_KEY', ' rk_live_synthetic_never_real'),
                            ('STRIPE_WEBHOOK_SECRET', ''), ('QUILLMD_APP_BASE_URL', 'http://localhost:9130'),
                            ('QUILLMD_APP_BASE_URL', ''), ('QUILLMD_PREVIEW_AUTH_ENABLED', '1'),
                            ('QUILLMD_APP_BASE_URL', 'https://app.quillmd.com?'), ('QUILLMD_APP_BASE_URL', 'https://app.quillmd.com#'),
                            ('QUILLMD_APP_BASE_URL', 'https://app.quillmd.com:0')):
            with self.subTest(name=name, value=value):
                result = start({**self.COMPLETE, name: value})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(name, result.stderr.strip().splitlines()[-1])
                self.assertNotIn('synthetic_never_real', result.stderr)
                self.assertNotIn('SyntheticNeverReal', result.stderr)

    def test_live_mode_refuses_a_webhook_secret_that_can_never_verify(self):
        """F1: the webhook signs with the value exactly as configured, so a padded value or another kind of key
        refuses the start instead of charging every live payer and crediting none."""
        for value in (' whsec_SyntheticNeverReal0001', 'whsec_SyntheticNeverReal0001 ', 'whsec_SyntheticNeverReal0001\n',
                      '\twhsec_SyntheticNeverReal0001', 'whsec_Synthetic NeverReal0001', 'whsec_synthetic_never_real',
                      'whsec_', 'WHSEC_SyntheticNeverReal0001', 'rk_live_SyntheticNeverReal0001', 'pk_live_SyntheticNeverReal0001',
                      'sk_live_SyntheticNeverReal0001', 'SyntheticNeverReal0001'):
            with self.subTest(value=repr(value)):
                result = start({**self.COMPLETE, 'STRIPE_WEBHOOK_SECRET': value})
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertIn('STRIPE_WEBHOOK_SECRET must be the endpoint signing secret exactly', result.stderr.strip().splitlines()[-1])
                self.assertNotIn('SyntheticNeverReal', result.stderr)
                self.assertNotIn('synthetic_never_real', result.stderr)

    def test_live_mode_refuses_the_preview_gate_which_would_403_every_webhook(self):
        """R2: today's private deployment (gate on, the gate's :9443 origin) with live Stripe must not start: the gate
        answers 403 to Stripe's webhook, so a live payment would be charged and never credited."""
        for extra in ({'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com:9443'}, {'QUILLMD_ADMIN_SITE': '1'}, {}):
            with self.subTest(extra=extra):
                result = start({**self.COMPLETE, 'QUILLMD_PREVIEW_AUTH_ENABLED': '1', **extra})
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertIn('QUILLMD_PREVIEW_AUTH_ENABLED must be off', result.stderr.strip().splitlines()[-1])
                self.assertNotIn('synthetic_never_real', result.stderr)

    def test_test_mode_keeps_the_preview_gate(self):
        """The private synthetic deployment runs test Stripe behind the gate; that start is unchanged."""
        result = start({'QUILLMD_PREVIEW_AUTH_ENABLED': '1', 'STRIPE_SECRET_KEY': 'rk_test_synthetic_never_real',
                        'STRIPE_WEBHOOK_SECRET': 'whsec_synthetic_never_real', 'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com:9443'})
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'False'), result.stderr)

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

    @override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', QUILLMD_STRIPE_MODE='live')
    def test_live_mode_never_returns_a_payer_to_an_address_with_an_empty_query_fragment_or_port_0(self):
        """R3: 'https://app.quillmd.com?' would send the payer to 'https://app.quillmd.com?/billing/...'."""
        for base in ('https://app.quillmd.com?', 'https://app.quillmd.com#', 'https://app.quillmd.com:0'):
            with self.subTest(base=base), override_settings(QUILLMD_APP_BASE_URL=base):
                response, api = self.checkout(f'origin-click-{len(base)}-{base[-1]}')
                self.assertEqual(response.status_code, 302)
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


#: Real data mode as settings computes it. Startup refuses real mode with a sandbox key; these tests
#: override past that refusal to prove the second wall: checkout and the webhook refuse on their own.
REAL = dict(SYNTHETIC_ONLY=False, QUILLMD_DATA_MODE='real')
REAL_SANDBOX = dict(REAL, QUILLMD_STRIPE_MODE='test', STRIPE_LIVE_ENABLED=False, STRIPE_SECRET_KEY='sk_test_synthetic_adapter')


class RealDataModeEventNamespace(SimpleTestCase):
    @override_settings(**REAL_SANDBOX)
    def test_real_mode_with_sandbox_stripe_refuses_every_event(self):
        for livemode in (False, True, None):
            with self.subTest(livemode=livemode), self.assertRaises(ValidationError):
                validate_event_environment(event(livemode))

    @override_settings(**REAL_SANDBOX)
    def test_real_mode_recorder_refuses_a_sandbox_event_before_any_write(self):
        # The stand-in row would let a write that is reached return normally, so reaching it fails an assertion.
        stored = (SimpleNamespace(semantic_hash='', kind='checkout.session.completed'), True)
        with patch('core.billing.WebhookEvent.objects.get_or_create', return_value=stored) as create:
            with self.assertRaises(ValidationError):
                record_stripe_event(event(False, {'id': 'cs_test_x', 'livemode': False}), 'synthetic-hash')
        create.assert_not_called()

    @override_settings(**REAL, **LIVE)
    def test_real_mode_with_live_stripe_keeps_only_livemode_true(self):
        validate_event_environment(event(True))
        for livemode in (False, None):
            with self.subTest(livemode=livemode), self.assertRaises(ValidationError):
                validate_event_environment(event(livemode))


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class RealDataModeTakesOnlyLivePayments(SyntheticFixture, TestCase):
    """R1: in real data mode a sandbox checkout never reaches Stripe and a livemode=false event never becomes balance."""
    setUp = LiveCheckoutAndSettlement.setUp
    checkout = LiveCheckoutAndSettlement.checkout
    signed = LiveCheckoutAndSettlement.signed

    def paid_session(self, payment, livemode):
        return {'id': payment.stripe_session, 'payment_status': 'paid', 'currency': 'usd', 'amount_total': payment.amount_cents,
                'metadata': {'payment_id': str(payment.pk)}, 'payment_intent': f'pi_{payment.stripe_session}', 'mode': 'payment',
                'livemode': livemode}

    @override_settings(**REAL_SANDBOX)
    def test_sandbox_checkout_is_refused_before_any_provider_call(self):
        response, api = self.checkout('real-sandbox-click')
        self.assertEqual(response.status_code, 302)
        api.assert_not_called()
        self.assertFalse(Payment.objects.exists())
        self.assertIn('Payments are not available', str(list(response.wsgi_request._messages)[0]))

    @override_settings(**REAL_SANDBOX)
    def test_a_sandbox_event_never_credits_a_real_mode_wallet(self):
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        before = wallet.balance
        payment = Payment.objects.create(user=self.user, wallet=wallet, amount_cents=5000, stripe_session='cs_test_real_sandbox')
        response = self.signed(event(False, self.paid_session(payment, False), 'evt_test_real_sandbox'))
        self.assertEqual(response.status_code, 400)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, before)
        self.assertFalse(WebhookEvent.objects.exists())
        self.assertFalse(LedgerEntry.objects.filter(kind='payment').exists())
        payment.refresh_from_db()
        self.assertNotEqual(payment.status, 'paid')

    @override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE)
    def test_real_mode_with_live_stripe_checks_out_and_credits_only_live_events(self):
        response, api = self.checkout('real-live-click')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(api.call_args.kwargs['success_url'], 'https://app.quillmd.com/billing/?payment=processing')
        payment = Payment.objects.get(user=self.user)
        self.assertEqual(self.signed(event(False, self.paid_session(payment, False), 'evt_sandbox_in_live')).status_code, 400)
        self.assertEqual(self.signed(event(True, self.paid_session(payment, True), 'evt_live_in_real')).status_code, 200)
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        self.assertEqual(wallet.balance, 10)
        self.assertEqual(LedgerEntry.objects.filter(wallet=wallet, kind='payment').count(), 1)
