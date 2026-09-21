"""Own-account sandbox ingress; synthetic signatures, no provider requests."""
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from core.billing import record_stripe_event
from core.models import LedgerEntry, Payment, Wallet, WebhookEvent
from core.stripe_validation import validate_event_environment
from core.tests.test_security import SyntheticFixture
from core.views import webhook

SECRET = 'whsec_synthetic_environment_tests'


def signed_request(event, *, key=SECRET, timestamp=None):
    body = json.dumps(event).encode()
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    signature = hmac.new(key.encode(), stamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
    return RequestFactory().post('/billing/webhook/', body, content_type='application/json',
                                 HTTP_STRIPE_SIGNATURE=f't={stamp},v1={signature}')


def event_for(obj=None, **extra):
    return {'id': 'evt_synthetic_environment', 'object': 'event',
            'type': 'checkout.session.completed', 'livemode': False,
            'data': {'object': obj or {}}, **extra}


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET)
class StripeEnvironmentIngress(SimpleTestCase):
    def test_explicit_own_account_sandbox_is_the_only_supported_namespace(self):
        for fields in ({}, {'account': None, 'context': None}, {'account': '', 'context': ''}):
            with self.subTest(fields=fields):
                validate_event_environment(event_for(**fields))
        for invalid in ({}, {'livemode': True}, {'livemode': None}, {'livemode': 0}, [], None):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                validate_event_environment(invalid)
        for field in ('account', 'context'):
            for value in ('acct_synthetic_other', [], {}, False, 0):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    validate_event_environment(event_for(**{field: value}))

    def test_signed_unsupported_namespaces_stop_before_the_recorder(self):
        for field in ('account', 'context'):
            with self.subTest(field=field), \
                    patch('core.billing.record_stripe_event') as record, \
                    patch('core.billing.process_stripe_event') as process:
                response = webhook(signed_request(event_for(**{field: 'acct_synthetic_other'})))
                self.assertEqual(response.status_code, 400)
                record.assert_not_called()
                process.assert_not_called()

    def test_mode_signature_and_timestamp_refusal_precede_persistence(self):
        requests = [signed_request(event_for(livemode=True)),
                    signed_request(event_for(livemode=None)),
                    signed_request(event_for(), key='whsec_synthetic_wrong'),
                    signed_request(event_for(), timestamp=int(time.time()) - 900)]
        for request in requests:
            with self.subTest(signature=request.headers.get('Stripe-Signature')), \
                    patch('core.billing.record_stripe_event') as record, \
                    patch('core.billing.process_stripe_event') as process:
                self.assertEqual(webhook(request).status_code, 400)
                record.assert_not_called()
                process.assert_not_called()

    def test_own_account_signed_event_still_reaches_existing_processing(self):
        with patch('core.billing.record_stripe_event', return_value=SimpleNamespace(pk='synthetic-row')) as record, \
                patch('core.billing.process_stripe_event', return_value=True) as process:
            response = webhook(signed_request(event_for()))
        self.assertEqual(response.status_code, 200)
        record.assert_called_once()
        process.assert_called_once_with('synthetic-row')

    def test_direct_recorder_refuses_wrong_environment_before_any_database_call(self):
        invalid = [event_for(livemode=True), event_for(livemode=None),
                   event_for(account='acct_synthetic_other'), event_for(context='acct_synthetic_other')]
        for event in invalid:
            with self.subTest(event=event), \
                    patch('core.billing.WebhookEvent.objects.get_or_create') as create, \
                    self.assertRaises(ValidationError):
                record_stripe_event(event, 'synthetic-hash')
            create.assert_not_called()


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET)
class StripeEnvironmentLedger(SyntheticFixture, TestCase):
    def setUp(self):
        self.scope = self.make_scope('stripe-environment')
        self.wallet = Wallet.objects.get(user=self.scope[0], kind='paid')
        self.payment = Payment.objects.create(user=self.scope[0], wallet=self.wallet,
                                              amount_cents=500, stripe_session='cs_test_environment')
        self.obj = {'id': self.payment.stripe_session, 'payment_status': 'paid', 'currency': 'usd',
                    'amount_total': 500, 'metadata': {'payment_id': str(self.payment.pk)},
                    'payment_intent': 'pi_test_environment', 'mode': 'payment'}

    def test_foreign_namespace_cannot_consume_event_id_or_credit_registered_payment(self):
        original_ledger = LedgerEntry.objects.count()
        for field in ('account', 'context'):
            response = webhook(signed_request(event_for(self.obj, **{field: 'acct_synthetic_other'})))
            self.assertEqual(response.status_code, 400)
            self.wallet.refresh_from_db()
            self.payment.refresh_from_db()
            self.assertEqual(self.wallet.balance, 0)
            self.assertEqual(self.payment.status, 'pending')
            self.assertEqual(LedgerEntry.objects.count(), original_ledger)
            self.assertFalse(WebhookEvent.objects.exists())
        # The same ID is usable by a valid own-account delivery, then remains
        # idempotent; a later foreign-context collision cannot alter the receipt.
        request = lambda: signed_request(event_for(self.obj))
        self.assertEqual(webhook(request()).status_code, 200)
        receipt = WebhookEvent.objects.get()
        original_hash = receipt.semantic_hash
        self.assertEqual(webhook(request()).status_code, 200)
        self.assertEqual(webhook(signed_request(event_for(self.obj, account='acct_synthetic_other'))).status_code, 400)
        self.wallet.refresh_from_db()
        receipt.refresh_from_db()
        self.assertEqual(self.wallet.balance, 5)
        self.assertEqual(receipt.semantic_hash, original_hash)
        self.assertEqual(WebhookEvent.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.filter(kind='payment').count(), 1)
