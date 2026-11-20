"""Platform-operator helpers for tests (studio.operator; CORE-UX-DESIGN.md 5). Synthetic data only.

The operator console under /ops/ answers anyone without an operator grant exactly as an unknown URL. A test that reads it
grants the user it signs in a real OperatorGrant, as the grant_operator command records one, so the real gate is
exercised.
"""
from django.test import Client

from studio import operator


def grant(user, reason='Synthetic test grant: this account reads the operator console in a test.'):
    """Grant ``user`` platform-operator access (as the grant_operator command records it); idempotent."""
    record, _ = operator.grant(user, reason, 'tests')
    return record


def client(user, **kwargs):
    """A client signed in as ``user``, which is granted operator access first."""
    grant(user)
    signed_in = Client(**kwargs)
    signed_in.force_login(user)
    return signed_in
