"""The currently supported payment environment is one own-account sandbox.

A valid signature authenticates the endpoint; it does not make Connect or
organization-scoped events part of this application's payment namespace.
"""
from django.core.exceptions import ValidationError


def validate_event_environment(event):
    """Refuse unsupported payment namespaces before event or ledger writes."""
    if not isinstance(event, dict) or event.get('livemode') is not False:
        raise ValidationError('Only explicit test-mode payment events are accepted.')
    # Ordinary own-account events omit account/context (or carry null). Stripe's
    # account field identifies a connected account, not the endpoint owner's ID.
    for field in ('account', 'context'):
        if event.get(field) not in (None, ''):
            raise ValidationError('Connected-account and organization-context payment events are not supported.')
