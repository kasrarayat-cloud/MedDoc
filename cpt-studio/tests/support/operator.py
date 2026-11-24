"""Platform-operator helpers for tests (studio.operator; CORE-UX-DESIGN.md 5). Synthetic data only.

The operator console under /ops/ answers anyone without an operator grant exactly as an unknown URL. A test that reads it
grants the user it signs in a real OperatorGrant, as the grant_operator command records one, so the real gate is
exercised.

Release 1 (RELEASE-1-SPEC B2, B3 and B5; the session keys of studio.request_meta): a sign-in writes its door, its time,
the last activity and its sign-in reference into the session, and the admin door also the second factor's time, which
the console's gate reads (studio.second_factor.satisfied). client() signs a test operator in as the door of the client's
own host would: a client for admin.quillmd.com carries the admin door and the second factor - or not, with
second_factor=False, the password-only session of the gate's negative tests; a client for any other host carries the cpt
door, which has no second factor. So the operator tests keep working once the console's gate asks for the second factor
on the admin host (Lane 3), and once the session policy ends a session from before release 1 or from another door
(Lane 2).
"""
import uuid

from django.conf import settings
from django.http.request import split_domain_port
from django.test import Client

from studio import operator, request_meta


def grant(user, reason='Synthetic test grant: this account reads the operator console in a test.'):
    """Grant ``user`` platform-operator access (as the grant_operator command records it); idempotent."""
    record, _ = operator.grant(user, reason, 'tests')
    return record


def door_of(host):
    """The door a sign-in on ``host`` is made at: the admin door on the admin host, the cpt door anywhere else."""
    return request_meta.ADMIN if split_domain_port(host)[0] == settings.ADMIN_HOST else request_meta.CPT


def sign_in_markers(door, *, second_factor=True, moment=None):
    """The session keys a sign-in at ``door`` writes (now, or at ``moment``): the second factor's time only at the admin
    door, and there only when ``second_factor``."""
    now = request_meta.epoch_seconds(moment)
    markers = {request_meta.SESSION_DOOR: door, request_meta.SESSION_AUTH_AT: now,
               request_meta.SESSION_LAST_ACTIVE: now, request_meta.SESSION_SIGN_IN_REF: str(uuid.uuid4())}
    if second_factor and door == request_meta.ADMIN:
        markers[request_meta.SESSION_SECOND_FACTOR_AT] = now
    return markers


def mark_signed_in(signed_in, *, door, second_factor=True):
    """Write the markers of a sign-in at ``door`` into the session of the test client ``signed_in`` (already signed in)."""
    session = signed_in.session
    session.update(sign_in_markers(door, second_factor=second_factor))
    session.save()
    return signed_in


def client(user, *, second_factor=True, **kwargs):
    """A client signed in as ``user``, which is granted operator access first, carrying the markers of its host's door
    (the second factor's on the admin host, unless ``second_factor`` is False)."""
    grant(user)
    signed_in = Client(**kwargs)
    signed_in.force_login(user)
    return mark_signed_in(signed_in, door=door_of(kwargs.get('HTTP_HOST', 'testserver')), second_factor=second_factor)


def admin_client(user, *, second_factor=True, **kwargs):
    """client() on the admin host, admin.quillmd.com: with the second factor, or a password-only session."""
    return client(user, second_factor=second_factor, HTTP_HOST=settings.ADMIN_HOST, **kwargs)
