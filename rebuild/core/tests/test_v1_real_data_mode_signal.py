"""`real_data_mode()`: anything but synthetic, and EITHER setting saying so counts (round-2 refutation F6).

settings derives SYNTHETIC_ONLY from QUILLMD_DATA_MODE, so in a real process the two always agree. The rule is
deliberately fail-closed for a partial override or a missing setting: SYNTHETIC_ONLY=False alone, or
QUILLMD_DATA_MODE='real' alone, or either setting absent, reads as real. Every guard that reads it is exercised
with only ONE of the two settings saying real: the webhook, checkout, the Deepgram opt-out and reserve().
"""
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from core.billing import reserve
from core.jobs import NoProviderRequest, request_parameters
from core.models import Job, Payment, Reservation, Wallet
from core.stripe_validation import real_data_mode, sandbox_payments_refused, validate_event_environment
from core.tests.test_security import SyntheticFixture
from core.tests import test_v1_stripe_live as stripe_live  # The module, so its TestCase is not collected twice here.

#: Only ONE of the two settings says real; the other still says synthetic.
PARTIAL = {'flag only': dict(SYNTHETIC_ONLY=False, QUILLMD_DATA_MODE='synthetic'),
           'mode only': dict(SYNTHETIC_ONLY=True, QUILLMD_DATA_MODE='real')}
SYNTHETIC = dict(SYNTHETIC_ONLY=True, QUILLMD_DATA_MODE='synthetic')


@contextmanager
def without(name, **others):
    """The setting absent altogether, the other one synthetic (Django: delete after overriding)."""
    with override_settings(**others):
        delattr(settings, name)
        yield


def partial_modes():
    """(label, context manager factory) for every one-sided way of saying real."""
    for label, values in PARTIAL.items():
        yield label, lambda values=values: override_settings(**values)
    yield 'flag missing', lambda: without('SYNTHETIC_ONLY', QUILLMD_DATA_MODE='synthetic')
    yield 'mode missing', lambda: without('QUILLMD_DATA_MODE', SYNTHETIC_ONLY=True)


class EitherSettingSaysReal(SimpleTestCase):
    def test_the_rule(self):
        with override_settings(**SYNTHETIC):
            self.assertFalse(real_data_mode())
        with override_settings(SYNTHETIC_ONLY=False, QUILLMD_DATA_MODE='real'):
            self.assertTrue(real_data_mode())
        for label, mode in partial_modes():
            with self.subTest(mode=label), mode():
                self.assertTrue(real_data_mode())

    def test_the_webhook_refuses_a_sandbox_event_on_either_signal(self):
        with override_settings(**SYNTHETIC):
            validate_event_environment(stripe_live.event(False))  # Control: synthetic keeps sandbox events.
        for label, mode in partial_modes():
            with self.subTest(mode=label), mode(), self.assertRaisesRegex(ValidationError, 'Real data mode'):
                validate_event_environment(stripe_live.event(False))

    def test_checkout_refuses_sandbox_payments_on_either_signal(self):
        with override_settings(**SYNTHETIC):
            self.assertFalse(sandbox_payments_refused())
        for label, mode in partial_modes():
            with self.subTest(mode=label), mode():
                self.assertTrue(sandbox_payments_refused())

    def test_deepgram_refuses_a_request_without_the_opt_out_on_either_signal(self):
        recorded = SimpleNamespace(config={'deepgram_parameters': {'model': 'nova-3-medical', 'smart_format': 'false'}})
        with override_settings(**SYNTHETIC):
            self.assertEqual(request_parameters(recorded), {'model': 'nova-3-medical', 'smart_format': 'false'})
        for label, mode in partial_modes():
            with self.subTest(mode=label), mode(), self.assertRaisesRegex(NoProviderRequest, 'opt-out'):
                request_parameters(recorded)


@override_settings(STRIPE_WEBHOOK_SECRET=stripe_live.SECRET, ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False,
                   STORAGES=stripe_live.STORAGES, QUILLMD_WELCOME_CREDIT=Decimal('0'), STRIPE_SECRET_KEY='sk_test_synthetic_adapter')
class EitherSettingSaysRealAtTheDoor(SyntheticFixture, TestCase):
    setUp = stripe_live.LiveCheckoutAndSettlement.setUp
    checkout = stripe_live.LiveCheckoutAndSettlement.checkout

    def test_the_checkout_view_makes_no_provider_call_on_either_signal(self):
        for label, values in PARTIAL.items():
            with self.subTest(mode=label), override_settings(**values):
                response, api = self.checkout(f'partial-{label.replace(" ", "-")}')
                self.assertEqual(response.status_code, 302)
                api.assert_not_called()
                self.assertFalse(Payment.objects.exists())

    def test_reserve_refuses_a_sandbox_funded_balance_on_either_signal(self):
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        Payment.objects.create(user=self.user, wallet=wallet, amount_cents=1000, stripe_session='cs_test_partial', livemode=False)
        Wallet.objects.filter(pk=wallet.pk).update(balance=Decimal('10'))
        encounter = self.user.membership_set.first().department.encounter_set.first()
        for label, values in PARTIAL.items():
            with self.subTest(mode=label), override_settings(**values):
                job = Job.objects.create(encounter=encounter, user=self.user, kind='generation', request_key=f'partial-{label}', config={})
                with self.assertRaisesRegex(ValidationError, 'sandbox'):
                    reserve(job, Decimal('2'))
                self.assertFalse(Reservation.objects.filter(job=job).exists())
