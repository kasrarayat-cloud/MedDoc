"""The console's second-factor gate (release 1, B2; RELEASE-1-SPEC 3.3), finished here so the console's gate (Lane 3)
can rely on it. Lane 2 adds the WebAuthn ceremony around it (studio.second_factor_views): its second-factor view is the
only writer of the session's SESSION_SECOND_FACTOR_AT, after a verified key or recovery code.

    satisfied(request)
        True only when the request is signed in, its session was opened at the admin door (SESSION_DOOR is 'admin') and
        it carries a valid second-factor time (SESSION_SECOND_FACTOR_AT: whole seconds since the epoch, not in the
        future). A password alone, a session opened at cpt.quillmd.com, a session from before release 1 or a malformed
        marker is never satisfied.
    requires_recent_second_factor(max_age=SECOND_FACTOR_STEP_UP_SECONDS)
        a decorator for the acts that change who can see what (B2, item 5): a satisfied session whose second factor is
        older than ``max_age`` seconds is sent to /login/second-factor?next=<the console page the act's form is on>
        and the act is not done - the form is never replayed; the operator submits it again. A session that is not
        satisfied at all is answered Django's 404, as the console's gate answers it. ``max_age`` left out is
        settings.SECOND_FACTOR_STEP_UP_SECONDS, read at each request.

Neither is applied to any view in Lane 1: Lane 3's operator_view and acts apply them.
"""
from __future__ import annotations

import functools
import math
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.http import Http404, HttpResponseRedirect

from . import hosts, request_meta

STEP_UP_PATH = '/login/second-factor'  # Lane 2's second-factor page on the admin host (RELEASE-1-SPEC 3.4)
CONSOLE_FRONT = '/ops/'


def _age(request):
    """Seconds since the session's second factor, or None: no session, no marker, a marker that is not a positive
    finite number, or one in the future."""
    session = getattr(request, 'session', None)
    if session is None:
        return None
    at = session.get(request_meta.SESSION_SECOND_FACTOR_AT)
    if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or at <= 0:
        return None
    age = request_meta.epoch_seconds() - at
    return age if age >= 0 else None


def satisfied(request) -> bool:
    """Whether the request's session passed the second factor at the admin door (see the module)."""
    if getattr(request, 'session', None) is None:
        return False
    if not getattr(getattr(request, 'user', None), 'is_authenticated', False):
        return False
    if request.session.get(request_meta.SESSION_DOOR) != request_meta.ADMIN:
        return False
    return _age(request) is not None


def _form_page(request) -> str:
    """Where the operator comes back to after the step-up: a GET's own page; for any other method the page its form was
    on (the Referer, when it is this host's and names a console page); else the console's front page."""
    if request.method in ('GET', 'HEAD'):
        candidate = request.get_full_path()
    else:
        try:
            parts = urlsplit(request.META.get('HTTP_REFERER', ''))
        except ValueError:
            return CONSOLE_FRONT
        if not parts.netloc or parts.netloc != request.get_host():
            return CONSOLE_FRONT
        candidate = parts.path + (f'?{parts.query}' if parts.query else '')
    return candidate if hosts.is_console_page(candidate) else CONSOLE_FRONT


def requires_recent_second_factor(view=None, *, max_age=None):
    """The step-up decorator (see the module): ``@requires_recent_second_factor()``,
    ``@requires_recent_second_factor(max_age=...)`` or bare."""
    if view is None:
        return functools.partial(requires_recent_second_factor, max_age=max_age)
    if max_age is not None and (isinstance(max_age, bool) or not isinstance(max_age, int) or max_age < 0):
        raise ValueError('max_age is a whole number of seconds.')

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not satisfied(request):
            raise Http404()
        limit = settings.SECOND_FACTOR_STEP_UP_SECONDS if max_age is None else max_age
        if _age(request) > limit:
            response = HttpResponseRedirect(f'{STEP_UP_PATH}?{urlencode({"next": _form_page(request)})}')
            if request.method not in ('GET', 'HEAD'):
                response.status_code = 303  # the browser fetches the step-up page; the act's form is not sent again
            return response
        return view(request, *args, **kwargs)
    return wrapper
