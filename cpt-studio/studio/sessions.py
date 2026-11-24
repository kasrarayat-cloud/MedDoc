"""Sign-in state (release 1; RELEASE-1-SPEC 3.3): ending an account's sessions, and the session policy.

end_sessions(user, keep_session_key=None)
    every live session of ``user`` ended at once - studio.console's own function, moved here unchanged (with the
    refusal it answers, Refused, and the session stores it can end, SESSION_STORES) so every lane can end sessions
    without importing the console: the console's acts (access off, a password reset), a revocation (C3), a password
    change (B4, keeping the session that made it), sign out everywhere (B4) and a practice's disposal (D1). The console
    imports all four back, so studio.console.end_sessions and console.Refused are these.

SessionPolicyMiddleware
    after AuthenticationMiddleware (cptstudio/settings.py MIDDLEWARE). In Lane 1 it passes every request and its response
    through unchanged, binding the request while it runs (studio.request_meta.bound) so records written without the
    request in hand can carry its client, sign-in reference and request id (C1, item 7). Lane 2 fills it in: the idle
    limit and the cap (B5), the door binding (B3), the forced password change (B4), old-named cookies (B6) and the
    X-CPT-Actor response header (A2).
"""
from __future__ import annotations

from importlib import import_module

from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone

from . import request_meta

# the session stores whose sessions this console can list and end (refutation r2, secure-4)
SESSION_STORES = ('django.contrib.sessions.backends.db',)  # cached_db can hold a session the table no longer has (r3-3)
NO_SESSION_STORE = ('This site keeps sessions where the console cannot end them, so access cannot be changed or a '
                    'password reset here.')


class Refused(Exception):
    """An act the console declines, with the sentence the operator reads and the status it answers."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def end_sessions(user, keep_session_key=None) -> int:
    """End every live session signed in as ``user``: an open session ends at once and can never come back, whatever
    happens to the account later (refutation r1, gate-1). The sessions are read from the database table (the db store
    only, SESSION_STORES; any other store is refused - r2, secure-4; r3, r3-3), live ones only (an expired session signs
    nobody in - r2, secure-5), and each is deleted through its store. Sessions are sign-in state, not records. The
    number ended. ``keep_session_key``, when given, names the one session left signed in (B4: a password changed on
    /account/ keeps the session that changed it and ends the others)."""
    if settings.SESSION_ENGINE not in SESSION_STORES:
        raise Refused(NO_SESSION_STORE, 409)
    store = import_module(settings.SESSION_ENGINE).SessionStore
    ended = 0
    live = Session.objects.filter(expire_date__gt=timezone.now())
    if keep_session_key is not None:
        live = live.exclude(session_key=keep_session_key)
    for session in live.iterator(chunk_size=200):
        try:
            data = session.get_decoded()
        except Exception:  # noqa: BLE001 - a session that cannot be read signs nobody in
            continue
        if isinstance(data, dict) and str(data.get('_auth_user_id', '')) == str(user.pk):
            store(session_key=session.session_key).delete()
            ended += 1
    return ended


class SessionPolicyMiddleware:
    """The session policy (B3, B4, B5, B6, A2), directly after AuthenticationMiddleware. Lane 1: a pass-through that binds
    the request while it runs (studio.request_meta.bound); Lane 2 fills in the policy."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with request_meta.bound(request):
            return self.get_response(request)
