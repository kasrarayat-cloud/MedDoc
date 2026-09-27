"""The supported payment environment is one own-account Stripe mode: sandbox by default.

QUILLMD_STRIPE_MODE decides which: 'test' (the default) accepts only events that say
livemode=false, exactly as before; 'live' accepts only livemode=true. Neither accepts the other,
so a sandbox event can never credit a live wallet and a live event can never land in a sandbox
database.

A valid signature authenticates the endpoint; it does not make Connect or
organization-scoped events part of this application's payment namespace.
"""
from django.conf import settings
from django.core.exceptions import ValidationError


def live_payments():
    return getattr(settings, 'QUILLMD_STRIPE_MODE', 'test') == 'live'


def validate_event_environment(event):
    """Refuse unsupported payment namespaces before event or ledger writes."""
    live = live_payments()
    if not isinstance(event, dict) or event.get('livemode') is not live:
        raise ValidationError('Only explicit live-mode payment events are accepted.' if live
                              else 'Only explicit test-mode payment events are accepted.')
    # Ordinary own-account events omit account/context (or carry null). Stripe's
    # account field identifies a connected account, not the endpoint owner's ID.
    for field in ('account', 'context'):
        if event.get(field) not in (None, ''):
            raise ValidationError('Connected-account and organization-context payment events are not supported.')
