"""Platform-operator helpers for tests (CORE-UX-DESIGN.md 5). Synthetic data only.

The full encounter serializer, the trace, the operator report, every stored artifact and the reconciliation of an
unknown outcome are served under /ops/ to platform operators only (studio.operator). A test that reads them grants the
user it signs in an operator grant - the same user keeps its membership, so the payload is exactly what
serializers.encounter_detail gave that member - and reads OPS instead of '/api'.
"""
from django.test import Client

from studio import operator

OPS = '/ops/api'


def grant(user, reason='Synthetic test grant: this account reads the operator diagnostics in a test.'):
    """Grant ``user`` platform-operator access (as the grant_operator command records it); idempotent."""
    record, _ = operator.grant(user, reason, 'tests')
    return record


def client(user, **kwargs):
    """A client signed in as ``user``, which is granted operator access first."""
    grant(user)
    signed_in = Client(**kwargs)
    signed_in.force_login(user)
    return signed_in


class OperatorReads:
    """For a TestCase whose tests read the operator serializer - the full encounter payload, the trace, the operator
    report, a stored artifact's bytes, the reconciliation - which since CORE-UX-DESIGN.md 5 is served only under /ops/:
    every user such a test signs in (Client.force_login, Client.login) is granted platform-operator access first, by a
    real OperatorGrant, so the real gate is exercised and the user keeps its membership (the /ops/ payload is then
    exactly what serializers.encounter_detail gave that member). Customer actions stay at /api/ under the member's own
    role. The sign-in hook is installed for the whole class (setUpClass), so a setUp that signs in before - or without -
    calling its parents' setUp is covered too; the grants themselves are rows of each test, rolled back with it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from unittest import mock

        original_force_login, original_login = Client.force_login, Client.login

        def force_login(signed, user, backend=None):
            grant(user)
            return original_force_login(signed, user, backend)

        def login(signed, **credentials):
            from studio import models

            user = models.User.objects.filter(username=credentials.get('username')).first()
            if user is not None:
                grant(user)
            return original_login(signed, **credentials)

        for name, replacement in (('force_login', force_login), ('login', login)):
            patcher = mock.patch.object(Client, name, replacement)
            patcher.start()
            cls.addClassCleanup(patcher.stop)
