"""The supported payment environment is one own-account Stripe mode: sandbox by default.

QUILLMD_STRIPE_MODE decides which: 'test' (the default) accepts only events that say
livemode=false, exactly as before; 'live' accepts only livemode=true. Neither accepts the other,
so a sandbox event can never credit a live wallet and a live event can never land in a sandbox
database.

Real data mode accepts only livemode=true, whatever QUILLMD_STRIPE_MODE says. Startup already refuses
real mode with a sandbox mode and a server key; this is the second wall, so a sandbox payment can never
become paid balance that funds real provider calls. Real mode with test Stripe (payments off) therefore
refuses every event.

A valid signature authenticates the endpoint; it does not make Connect or
organization-scoped events part of this application's payment namespace.
"""
from django.conf import settings
from django.core.exceptions import ValidationError


def live_payments():
    return getattr(settings, 'QUILLMD_STRIPE_MODE', 'test') == 'live'


def real_data_mode():
    """Anything but the synthetic data mode. Either setting saying so counts, and a missing one reads as real."""
    return (not getattr(settings, 'SYNTHETIC_ONLY', False)
            or getattr(settings, 'QUILLMD_DATA_MODE', 'real') != 'synthetic')


def sandbox_payments_refused():
    """Real data mode takes only live payments: sandbox checkout and sandbox events are refused."""
    return real_data_mode() and not live_payments()


def validate_event_environment(event):
    """Refuse unsupported payment namespaces before event or ledger writes."""
    live = live_payments()
    if not isinstance(event, dict) or event.get('livemode') is not live:
        raise ValidationError('Only explicit live-mode payment events are accepted.' if live
                              else 'Only explicit test-mode payment events are accepted.')
    if real_data_mode() and event.get('livemode') is not True:
        raise ValidationError('Real data mode accepts only explicit live-mode payment events.')
    # Ordinary own-account events omit account/context (or carry null). Stripe's
    # account field identifies a connected account, not the endpoint owner's ID.
    for field in ('account', 'context'):
        if event.get(field) not in (None, ''):
            raise ValidationError('Connected-account and organization-context payment events are not supported.')
