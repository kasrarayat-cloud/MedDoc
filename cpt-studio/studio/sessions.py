"""Sign-in state (release 1; RELEASE-1-SPEC 3.3, B3, B4, B5, B6, A2): ending an account's sessions, the keys every sign-in
writes into its session, and the session policy every signed-in request meets.

end_sessions(user, keep_session_key=None)
    every live session of ``user`` ended at once - studio.console's own function, moved here (with the refusal it
    answers, Refused, and the session stores it can end, SESSION_STORES) so every lane can end sessions without
    importing the console: the console's acts (access off, a password reset), a revocation (C3), a password change (B4,
    keeping the session that made it), sign out everywhere (B4) and a practice's disposal (D1). The console imports all
    four back, so studio.console.end_sessions and console.Refused are these. Besides the sessions signed in as the
    account it ends the anonymous ones waiting on it - a pending sign-in at the admin door, a setup under way - so a
    password change or a sign-out everywhere drops a sign-in made with the old password (refutation r2, finding 11).

Every sign-in writes the session keys of studio.request_meta (the contract between the lanes, RELEASE-1-SPEC section 5):
SESSION_DOOR (the door it was made at), SESSION_AUTH_AT and SESSION_LAST_ACTIVE (now) and SESSION_SIGN_IN_REF (the sign-in's
reference, its LoginAttempt's). They are written by the receiver of django.contrib.auth's user_logged_in, so no login()
anywhere can open a session without them: a door names its own door and the attempt's reference first
(prepare_sign_in); any other login() - a test client's own sign-in included - gets the door of its request's host (the
cpt door when it has none, which opens no console) and a new reference. A new sign-in carries no earlier second factor:
SESSION_SECOND_FACTOR_AT is written only by the second-factor views (studio.second_factor_views), after a verified key or
recovery code. The receiver also marks the request, so the response sets the known-device cookie (studio.throttle, B1).

SessionPolicyMiddleware, directly after AuthenticationMiddleware (cptstudio/settings.py MIDDLEWARE), binds every request
while it runs (studio.request_meta.bound: C1's records read its client, sign-in reference and request id). A request
that carries no session cookie is signed in as nobody and passes untouched - its session is never read. For a
signed-in request, before the view runs:
  - the session ends (logout(), which deletes its row) when it is not one this release opened - no door, or keys that
    are not whole seconds of the past (a session from before release 1 is one) - when it was opened at the other door
    than the request's host (B3), when it is older than its cap (SESSION_MAX_*_SECONDS) since SESSION_AUTH_AT, or when it
    has been idle longer than its limit (SESSION_IDLE_*_SECONDS) since SESSION_LAST_ACTIVE (B5). A session opened at the
    admin door is an operator's: it has the operators' limit and cap. The API (and the activity ping) then answers 401
    {"error": "signed_out", "reason": "idle" | "expired"}; a page goes on signed out, and the redirect to a sign-in page
    it is answered with (the console's signed_out_to_sign_in, login_required) carries the reason, which the sign-in page
    says in a sentence;
  - while the account must choose a new password (User.password_change_required_at; B4, item 3) every request but
    those FORCED_CHANGE_ALLOWED lets through is refused: the API answers 403 {"error": "password_change_required"},
    a page is sent to /account/?required=1;
  - the request is marked to count as the person's activity when it is not marked a poll (X-CPT-Poll: 1,
    request_meta.is_poll) and not a frame's load (Sec-Fetch-Dest iframe, frame, embed or object: the review page's
    viewer of the original, which the page loads by itself). It counts once its answer is known, and only an answer
    under 400 does (refutation r2, finding 17): a request the server refused - a CSRF failure, a method not allowed, a
    page not found - moves nothing. Counting moves SESSION_LAST_ACTIVE, written at most once every
    SESSION_ACTIVITY_WRITE_SECONDS; the activity ping records its own before it answers.
  - Recorded, not repaired (refutation r2, finding 19): anything that sends a signed-in request - the ping included - at
    least once within the idle limit keeps the session alive until its cap. The server cannot tell a person from a
    script acting with the person's session; the cap (SESSION_MAX_*_SECONDS) bounds it, and the page's own timer is
    for the person at the screen.
And on the way out: a signed-in response carries X-CPT-Actor: <the sign-in reference> (A2: nginx logs it and strips
it); a response to a sign-in sets the known-device cookie; and a browser that still sends the cookies of their names
before release 1 (cptstudio_session, cptstudio_csrf - other names than this site's under HTTPS, B6) is told to delete
them (Max-Age=0). The page's own sign-out (POST /logout/?reason=idle after inactivity, ?reason=expired at the cap) gets
its reason on the redirect too.

A signed-in request also carries request.cpt_page (page_config): the seconds the session has before it idles out and
before its cap, the warning's lead and the session's tag (session_tag), which index.html and ops_base.html give the
page, so its timer is armed from the moment it loads, whatever becomes of its first ping (refutation r2, findings 13,
14 and 16).
"""
from __future__ import annotations

import math
import uuid
from importlib import import_module
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.signals import user_logged_in
from django.contrib.sessions.models import Session
from django.http import HttpResponseRedirect, JsonResponse
from django.utils import timezone
from django.utils.crypto import salted_hmac

from . import request_meta, throttle

# the session stores whose sessions this console can list and end (refutation r2, secure-4)
SESSION_STORES = ('django.contrib.sessions.backends.db',)  # cached_db can hold a session the table no longer has (r3-3)
NO_SESSION_STORE = ('This site keeps sessions where the console cannot end them, so access cannot be changed or a '
                    'password reset here.')

IDLE, EXPIRED = 'idle', 'expired'  # why the policy ended a session: the 401's reason, the sign-in page's sentence
REASONS = (IDLE, EXPIRED)
SIGNED_OUT = {'error': 'signed_out'}  # the 401 the API answers a session the policy ended, with its reason
PASSWORD_CHANGE_REQUIRED = {'error': 'password_change_required'}  # the 403 the API answers during a forced change
ACCOUNT_PATH = '/account/'
FORCED_CHANGE_PAGE = ACCOUNT_PATH + '?required=1'
ACTIVITY_PATH = '/session/activity'
LOGIN_PATH = '/login/'
LOGOUT_PATH = '/logout/'
# what a session that must choose a new password still reaches (B4, item 3): the account page, signing out (here and
# everywhere), the activity ping and the health check (static files never reach this middleware: WhiteNoise serves them
# first). At the admin door, also the second-factor step-up the account page asks an operator for before a change
# (B2, item 5), with its options and the recovery code that can stand in for a key.
FORCED_CHANGE_ALLOWED = frozenset({ACCOUNT_PATH, LOGOUT_PATH, '/logout/everywhere', ACTIVITY_PATH, '/health/'})
FORCED_CHANGE_ALLOWED_ADMIN = frozenset({'/login/second-factor', '/login/second-factor/options', '/login/recovery'})
OLD_COOKIE_NAMES = ('cptstudio_session', 'cptstudio_csrf')  # the names before release 1 (B6)
ACTOR_HEADER = 'X-CPT-Actor'
SESSION_TAG_SALT = 'studio.sessions.session_tag'
FRAME_DESTINATIONS = frozenset({'iframe', 'frame', 'embed', 'object'})  # Sec-Fetch-Dest of a load the page itself makes
# the session keys of an anonymous session that waits on an account (studio.second_factor reads them by these names):
# a checked password waiting for its key, and a setup under way; end_sessions ends them with the account's sessions
PENDING_SIGN_IN_KEY, SETUP_KEY = 'cpt_2fa_pending', 'cpt_enrol'
WAITING_KEYS = (PENDING_SIGN_IN_KEY, SETUP_KEY)
REDIRECTS = frozenset({301, 302, 303, 307, 308})


class Refused(Exception):
    """An act the console declines, with the sentence the operator reads and the status it answers."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def waits_on(data, user_id) -> bool:
    """Whether a session's ``data`` is signed in as the account ``user_id``, or waits on it: a checked password waiting
    for its key (PENDING_SIGN_IN_KEY) or a setup under way (SETUP_KEY), each naming the account in 'user'."""
    if str(data.get('_auth_user_id', '')) == user_id:
        return True
    return any(isinstance(data.get(name), dict) and str(data[name].get('user', '')) == user_id for name in WAITING_KEYS)


def end_sessions(user, keep_session_key=None) -> int:
    """End every live session signed in as ``user``, and every one waiting on it (waits_on: a pending sign-in at the
    admin door, a setup under way - refutation r2, finding 11): an open session ends at once and can never come back,
    whatever happens to the account later (refutation r1, gate-1). The sessions are read from the database table (the
    db store only, SESSION_STORES; any other store is refused - r2, secure-4; r3, r3-3), live ones only (an expired
    session signs nobody in - r2, secure-5), and each is deleted through its store. Sessions are sign-in state, not
    records. The number ended. ``keep_session_key``, when given, names the one session left signed in (B4: a password
    changed on /account/ keeps the session that changed it and ends the others)."""
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
        if isinstance(data, dict) and waits_on(data, str(user.pk)):
            store(session_key=session.session_key).delete()
            ended += 1
    return ended


# --- the keys a sign-in writes ------------------------------------------------------------------------------------------

def prepare_sign_in(request, *, door, sign_in_ref):
    """Name the door and the attempt's reference the next login() of ``request`` writes (a door calls this first)."""
    request.cpt_sign_in = {'door': door, 'ref': str(sign_in_ref)}


def _host_door(request):
    try:
        return request_meta.host_kind(request)
    except Exception:  # noqa: BLE001 - a request with no host (a test client's own sign-in): the cpt door, no console
        return request_meta.CPT


def stamp_sign_in(sender, request=None, user=None, **kwargs):
    """django.contrib.auth's user_logged_in: write the session keys of a sign-in (see the module)."""
    session = getattr(request, 'session', None)
    if session is None or user is None:
        return
    prepared = getattr(request, 'cpt_sign_in', None) or {}
    door = prepared.get('door') if prepared.get('door') in (request_meta.CPT, request_meta.ADMIN) else _host_door(request)
    ref = prepared.get('ref') or str(uuid.uuid4())
    now = request_meta.epoch_seconds()
    session.pop(request_meta.SESSION_SECOND_FACTOR_AT, None)
    session.update({request_meta.SESSION_DOOR: door, request_meta.SESSION_AUTH_AT: now,
                    request_meta.SESSION_LAST_ACTIVE: now, request_meta.SESSION_SIGN_IN_REF: ref})
    request.cpt_new_sign_in = {'user': str(user.pk), 'ref': ref}


user_logged_in.connect(stamp_sign_in, dispatch_uid='studio.sessions.stamp_sign_in')


# --- the policy -----------------------------------------------------------------------------------------------------------

def _stamp(value, now):
    """A session timestamp as this release writes it - whole seconds of the past, after the epoch - or None."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > now:
        return None
    return value


def limits(door):
    """(the idle limit, the cap) in seconds of a session opened at ``door``: an operator's at the admin door."""
    if door == request_meta.ADMIN:
        return settings.SESSION_IDLE_OPERATOR_SECONDS, settings.SESSION_MAX_OPERATOR_SECONDS
    return settings.SESSION_IDLE_MEMBER_SECONDS, settings.SESSION_MAX_MEMBER_SECONDS


def ended_reason(request, now=None):
    """Why the signed-in ``request``'s session must end now (IDLE or EXPIRED), or None (see the module)."""
    now = request_meta.epoch_seconds() if now is None else now
    session = request.session
    door = session.get(request_meta.SESSION_DOOR)
    auth_at = _stamp(session.get(request_meta.SESSION_AUTH_AT), now)
    last_active = _stamp(session.get(request_meta.SESSION_LAST_ACTIVE), now)
    if door not in (request_meta.CPT, request_meta.ADMIN) or auth_at is None or last_active is None \
            or request_meta.sign_in_ref(request) is None:
        return EXPIRED  # no keys of this release: a session from before release 1, or one written by nothing here
    if door != request_meta.host_kind(request):
        return EXPIRED  # B3: a session is bound to the door it was opened at
    idle, cap = limits(door)
    if now - auth_at > cap:
        return EXPIRED
    if now - last_active > idle:
        return IDLE
    return None


def remaining(request, now=None):
    """(seconds until the signed-in ``request``'s session idles out, seconds until its cap), never below 0."""
    now = request_meta.epoch_seconds() if now is None else now
    session = request.session
    idle, cap = limits(session.get(request_meta.SESSION_DOOR))
    last_active = session.get(request_meta.SESSION_LAST_ACTIVE) or now
    auth_at = session.get(request_meta.SESSION_AUTH_AT) or now
    return max(0, idle - (now - last_active)), max(0, cap - (now - auth_at))


def note_activity(request, now=None):
    """The person did something: SESSION_LAST_ACTIVE moves to now, written at most once every
    SESSION_ACTIVITY_WRITE_SECONDS."""
    now = request_meta.epoch_seconds() if now is None else now
    last_active = request.session.get(request_meta.SESSION_LAST_ACTIVE) or 0
    if now - last_active >= settings.SESSION_ACTIVITY_WRITE_SECONDS:
        request.session[request_meta.SESSION_LAST_ACTIVE] = now


def automatic(request) -> bool:
    """Whether the request is one the page makes by itself, never the person's activity: a poll (X-CPT-Poll: 1), or a
    frame's load (Sec-Fetch-Dest; a browser that sends none counts it, as before)."""
    return request_meta.is_poll(request) or request.META.get('HTTP_SEC_FETCH_DEST', '') in FRAME_DESTINATIONS


def _is_api(request):
    return request.path.startswith('/api/') or request.path == ACTIVITY_PATH


def _allowed_during_change(request):
    if request.path in FORCED_CHANGE_ALLOWED:
        return True
    return request.path in FORCED_CHANGE_ALLOWED_ADMIN and request_meta.host_kind(request) == request_meta.ADMIN


def _see_other(url):
    response = HttpResponseRedirect(url)
    response.status_code = 303
    return response


def _with_reason(response, reason):
    """Add ``reason`` to a redirect to this site's sign-in page (a path, no host), unless it already names one."""
    location = response.get('Location', '')
    try:
        parts = urlsplit(location)
    except ValueError:
        return
    if parts.scheme or parts.netloc or parts.path != LOGIN_PATH:
        return
    query = parse_qsl(parts.query, keep_blank_values=True)
    if any(name == 'reason' for name, _ in query):
        return
    response['Location'] = urlunsplit(('', '', parts.path, urlencode(query + [('reason', reason)]), parts.fragment))


def _page_sign_out_reason(request):
    """The page's own sign-out (app.js and ops_session.js submit the sign-out form to /logout/?reason=idle after
    inactivity, and to /logout/?reason=expired at the session's cap): its redirect to the sign-in page says why."""
    if request.method == 'POST' and request.path == LOGOUT_PATH and request.GET.get('reason') in REASONS:
        return request.GET['reason']
    return None


def session_tag(request) -> str:
    """The value a signed-in page is given to know its own session by (data-session, and the ping's answer): a keyed
    hash of the session's sign-in reference, so the tabs of one browser can tell their session's news from another
    session's (refutation r2, finding 14) while the reference itself never reaches the page. '' when there is none."""
    ref = request_meta.sign_in_ref(request)
    return salted_hmac(SESSION_TAG_SALT, str(ref), algorithm='sha256').hexdigest()[:32] if ref else ''


def page_config(request) -> dict:
    """What a signed-in page needs to arm its own timer the moment it loads (refutation r2, findings 13 and 16): the
    seconds until the session idles out and until its cap, as they stand before this request's own activity - so the
    page's deadline is never later than the server's - the warning's lead, the session's tag, and when a page without
    script refreshes to the sign-in (ops_base.html's noscript)."""
    idle, cap = remaining(request)
    return {'idle_seconds': idle, 'cap_seconds': cap, 'warning_seconds': settings.SESSION_IDLE_WARNING_SECONDS,
            'session': session_tag(request), 'refresh_seconds': min(idle, cap) + 10}


class SessionPolicyMiddleware:
    """The session policy (see the module), directly after AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with request_meta.bound(request):
            response = self.policy(request)
            if response is None:
                response = self.get_response(request)
            return self.finish(request, response)

    def policy(self, request):
        """The answer that ends or refuses ``request`` before its view, or None to let it through."""
        cookies = getattr(request, 'COOKIES', None) or {}
        if not cookies.get(settings.SESSION_COOKIE_NAME) or getattr(request, 'session', None) is None:
            return None  # signed in as nobody: the session is never read
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return None
        now = request_meta.epoch_seconds()
        reason = ended_reason(request, now)
        if reason is not None:
            logout(request)  # deletes the session's row; the request goes on signed out
            request.cpt_signed_out = reason
            if _is_api(request):
                return JsonResponse({**SIGNED_OUT, 'reason': reason}, status=401)
            return None
        request.cpt_actor = str(request_meta.sign_in_ref(request))
        request.cpt_page = page_config(request)  # the signed-in page's own timer (index.html, ops_base.html)
        if getattr(user, 'password_change_required_at', None) is not None and not _allowed_during_change(request):
            if request.path.startswith('/api/'):
                return JsonResponse(PASSWORD_CHANGE_REQUIRED, status=403)
            if request.method in ('GET', 'HEAD'):
                return HttpResponseRedirect(FORCED_CHANGE_PAGE)
            return _see_other(FORCED_CHANGE_PAGE)
        request.cpt_counts = not automatic(request)  # the person's activity once the answer is known (finish)
        return None

    def finish(self, request, response):
        """The response's way out (see the module)."""
        if getattr(request, 'cpt_counts', False) and response.status_code < 400 \
                and getattr(getattr(request, 'user', None), 'is_authenticated', False):
            note_activity(request)  # still signed in after the view (a sign-out or a session ended counts nothing)
        if not hasattr(response, 'set_cookie'):
            return response
        reason = getattr(request, 'cpt_signed_out', None) or _page_sign_out_reason(request)
        if reason and response.status_code in REDIRECTS:
            _with_reason(response, reason)
        signed_in = getattr(request, 'cpt_new_sign_in', None)
        actor = signed_in['ref'] if signed_in else getattr(request, 'cpt_actor', '')
        if actor:
            response[ACTOR_HEADER] = actor
        if signed_in:
            response.set_cookie(throttle.device_cookie_name(), throttle.device_cookie_value(signed_in['user']),
                                max_age=settings.KNOWN_DEVICE_DAYS * 24 * 60 * 60, path='/', secure=settings.HTTPS,
                                httponly=True, samesite='Strict')
        cookies = getattr(request, 'COOKIES', None) or {}
        current = {settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME}
        for name in OLD_COOKIE_NAMES:
            if name not in current and name in cookies:
                response.set_cookie(name, '', max_age=0, expires='Thu, 01 Jan 1970 00:00:00 GMT', path='/',
                                    secure=settings.SESSION_COOKIE_SECURE, samesite='Strict')
        return response


def warning_minutes():
    """The idle warning's lead, in whole minutes (SESSION_IDLE_WARNING_SECONDS)."""
    return max(1, math.ceil(settings.SESSION_IDLE_WARNING_SECONDS / 60))
