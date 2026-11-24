"""Health, sign-in/out, the account page and the single-page shell.

The shell's Content-Security-Policy is the site's own (access.SecurityHeadersMiddleware) with frame-src 'self' named, so
the review page's viewer frames the in-page view of the original (GET /api/encounters/<id>/original?view=1, which only
CPT Studio's own pages may frame) and nothing else.

Release 1 (RELEASE-1-SPEC 4, B1 to B7):
- Both doors ask studio.throttle before any password is checked and record every attempt that reaches the check (B1):
  the doctors' door, login_view on cpt.quillmd.com, signs in an account with an active membership and nothing else -
  an account without one gets the wrong-password sentence and the outcome no_access (B3: no operator branch); the
  operator door, admin_login_view on admin.quillmd.com, calls no login() at all: a human operator's right password
  waits for the security key (studio.second_factor.begin, B2), every other account gets the same sentence as a wrong
  password. A staff-set password not replaced within STAFF_PASSWORD_UNUSED_SECONDS is refused at both doors exactly
  like a wrong password (B4). Every sign-in writes the session keys of studio.sessions (its user_logged_in receiver).
- /account/ (both hosts): a member changes their own password - the current one, the new one twice, the validators;
  this session stays, every other one ends (B4). An operator changes theirs at the admin host only, after the step-up.
  POST /logout/everywhere ends every session of the account, this one included.
- POST /session/activity: the page's activity ping (B5). The session policy has already counted it; it answers how
  long the session has before it idles out.
- /health/ answers a request that came through nginx (it carries X-Forwarded-For) with release_digest instead of the
  release, and the operator sign-in page shows no release (B7).
"""
import hashlib
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET

from . import audit, rate, request_meta, second_factor, security_events, sessions, throttle
from .access import SecurityHeadersMiddleware, active_membership
from .api import UNSTORABLE
from .models import LoginAttempt
from .operator import is_operator
# the client's address: moved to studio.request_meta (release 1, RELEASE-1-SPEC 3.3); the alias keeps every caller
from .request_meta import client_address as _client  # noqa: F401 (kept: tests pin views._client)


INDEX_CSP = SecurityHeadersMiddleware.CSP.replace("frame-ancestors 'none'", "frame-src 'self'; frame-ancestors 'none'")


def release_digest(release=None) -> str:
    """B7: what /health/ says of the build to a request that came through nginx - the first 16 hex characters of
    sha256(HEALTH_DIGEST_PREFIX + RELEASE_SHA) - so the installer can match its own revision and a visitor learns
    nothing it could look up."""
    text = settings.HEALTH_DIGEST_PREFIX + (settings.RELEASE_SHA if release is None else release)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            database = 'ok' if cursor.fetchone() == (1,) else 'error'
    except Exception:  # noqa: BLE001 — health reports, never raises
        database = 'error'
    status = 200 if database == 'ok' else 503
    body = {'status': 'ok' if status == 200 else 'degraded', 'service': 'cpt-studio', 'data_mode': 'synthetic-only'}
    if 'HTTP_X_FORWARDED_FOR' in request.META:  # nginx sets it on every request it proxies (B7)
        body['release_digest'] = release_digest()
    else:  # a probe of the web's own port: the installer's waits, the container's health check
        body['release'] = settings.RELEASE_SHA
    body['database'] = database
    return JsonResponse(body, status=status)


SIGN_IN_REFUSED = 'The username or password is not correct.'


def _signed_out_notice(request, idle_seconds):
    """The sentence a sign-in page shows when the session policy ended the session (B5, item 5), or ''."""
    reason = request.GET.get('reason') or getattr(request, 'cpt_signed_out', None)
    if reason == sessions.IDLE:
        minutes = max(1, idle_seconds // 60)
        return f'You were signed out after {minutes} minutes without activity.'
    if reason == sessions.EXPIRED:
        return 'Your session has ended. Sign in again.'
    if reason == 'key':
        return 'The security key could not be verified. Sign in again.'
    return ''


def _member_door(user):
    return user.memberships.filter(active=True).exists()


@ensure_csrf_cookie
def login_view(request):
    if request.method not in ('GET', 'POST'):
        return HttpResponseNotAllowed(['GET', 'POST'])
    next_url = request.POST.get('next') or request.GET.get('next') or '/'
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        next_url = '/'
    error = ''
    if request.method == 'POST':
        submitted = request.POST.get('username', '').strip()[:150]
        # A name the database cannot store (NUL, lone surrogate) matches no account; it is
        # still counted, under a storable form, so the throttle sees every attempt.
        username = UNSTORABLE.sub('�', submitted)
        password = request.POST.get('password', '')
        door = throttle.Door(request, request_meta.CPT, username)
        error = door.refusal()  # B1: before any password is checked
        if not error:
            user = door.check(authenticate(request, username=username, password=password) if username == submitted
                              else None, allowed=_member_door)
            sessions.prepare_sign_in(request, door=request_meta.CPT, sign_in_ref=door.sign_in_ref)
            if user is not None and user.memberships.filter(active=True).exists():
                login(request, user)
                return redirect(next_url)
            # B3: an account with no active membership - a platform operator's included - is refused as a wrong
            # password (recorded no_access); the console is the admin host's alone
            error = SIGN_IN_REFUSED
    context = {'error': error, 'next': next_url,
               'notice': '' if error else _signed_out_notice(request, settings.SESSION_IDLE_MEMBER_SECONDS),
               'username': UNSTORABLE.sub('�', request.POST.get('username', ''))[:150] if error else ''}
    return render(request, 'studio/login.html', context, status=200 if not error else 400)


def logout_view(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    logout(request)
    return redirect('/login/')


@ensure_csrf_cookie
@login_required
def index(request):
    # B3: no redirect to the console - an account without an active workspace gets the 404 active_membership gives
    membership = active_membership(request.user)
    # the workspace's specialty, a label the page shows (owner direction 2026-11-22, D390); nothing codes from it
    response = render(request, 'studio/index.html', {'release': settings.RELEASE_SHA,
                                                     'specialty': membership.workspace.category.name})
    response.headers['Content-Security-Policy'] = INDEX_CSP
    return response


# The admin host (admin.quillmd.com; owner direction 2026-11-23, DECISIONS D396; cptstudio.urls_admin).
ADMIN_SIGN_IN_REFUSED = 'The username or password is not correct, or the account is not a platform operator.'


@csrf_exempt  # it reads no body and writes nothing: every method gets the redirect (refutation h1, gate-1)
def admin_home(request):
    """admin.quillmd.com/: an operator signed in with the second factor goes to the console, anyone else to the operator
    sign-in - every method alike, so a monitor's HEAD gets the same 302 as a browser's GET (an unsafe request from
    another origin is refused first by studio.hosts.foreign_origin)."""
    return redirect('/ops/' if second_factor.satisfied(request) and is_operator(request.user) else '/login/')


@csrf_exempt  # a redirect only, as admin_home
def admin_ops_slash(request):
    """admin.quillmd.com/ops goes to /ops/ (the full urlconf keeps /ops answering what /opsx answers)."""
    return redirect('/ops/')


@ensure_csrf_cookie
def admin_login_view(request):
    """The operator door on the admin host: login_view's form, CSRF, next rule and throttle, but only a human platform
    operator gets past it, and not into the console yet - the right password waits for the security key
    (studio.second_factor.begin; B2), recorded second_factor_pending. Any other account - a doctor with the right
    password included - gets the same sentence as a wrong password and no session, recorded no_access, which counts
    toward no delay (B1). An operator who is also a member is the operator here: this host has no doctor app. next may
    only name a console page on this host, or the account page."""
    if request.method not in ('GET', 'POST'):
        return HttpResponseNotAllowed(['GET', 'POST'])
    next_url = request.POST.get('next') or request.GET.get('next') or '/ops/'
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        next_url = '/ops/'
    next_url = second_factor.safe_next(next_url, request.get_host())
    error = ''
    if request.method == 'POST':
        submitted = request.POST.get('username', '').strip()[:150]
        username = UNSTORABLE.sub('�', submitted)
        password = request.POST.get('password', '')
        door = throttle.Door(request, request_meta.ADMIN, username)
        error = door.refusal()  # B1: before any password is checked
        if not error:
            user = door.check(authenticate(request, username=username, password=password) if username == submitted
                              else None, allowed=second_factor.is_human_operator,
                              success=LoginAttempt.SECOND_FACTOR_PENDING)
            if user is not None:
                second_factor.begin(request, user, door.sign_in_ref, next_url)  # no login() yet (B2, item 2)
                return redirect(second_factor.STEP_UP_PATH)
            error = ADMIN_SIGN_IN_REFUSED
    context = {'error': error, 'next': next_url,
               'notice': '' if error else _signed_out_notice(request, settings.SESSION_IDLE_OPERATOR_SECONDS),
               'username': UNSTORABLE.sub('�', request.POST.get('username', ''))[:150] if error else ''}
    return render(request, 'studio/ops_login.html', context, status=200 if not error else 400)


# --- the account page (B4) --------------------------------------------------------------------------------------------

ACCOUNT_SCOPE = 'account.wrong_password'  # wrong current passwords on /account/, per account and minute
WRONG_CURRENT = 'The current password is not correct.'
TOO_MANY_WRONG = 'Too many wrong passwords. Wait {wait} and try again.'
NOT_THE_SAME = 'The two new passwords are not the same.'
SAME_AS_BEFORE = 'Choose a new password that is not the one you have now.'
OPERATOR_ON_CONSOLE = ('A platform operator changes this password on the console\'s own account page, with the security '
                       'key.')
CHANGED = 'Your password was changed. Every other session of this account was signed out.'


def _wrong_passwords(user):
    """Wrong current passwords of ``user`` in the sign-in window: counted like a sign-in's failures, at most
    SIGNIN_USER_DELAY_AFTER per SIGNIN_WINDOW_SECONDS (B4: 5 per 15 minutes per account)."""
    since = rate.window_start(throttle.MINUTE, timezone.now() - timedelta(seconds=settings.SIGNIN_WINDOW_SECONDS))
    return rate.count(ACCOUNT_SCOPE, user.pk, since=since)


def _change_password(request, user):
    """Change ``user``'s password from the account page's form; the refusal sentence, or '' once changed."""
    if _wrong_passwords(user) >= settings.SIGNIN_USER_DELAY_AFTER:  # refused for the window, before any hashing
        return TOO_MANY_WRONG.format(wait=throttle.wait_words(settings.SIGNIN_WINDOW_SECONDS))
    current = request.POST.get('current_password', '')
    new = request.POST.get('new_password', '')
    again = request.POST.get('new_password_again', '')
    if not user.check_password(current):
        rate.hit(ACCOUNT_SCOPE, user.pk, window_seconds=throttle.MINUTE)
        return WRONG_CURRENT
    if new != again:
        return NOT_THE_SAME
    if new == current:
        return SAME_AS_BEFORE
    try:
        validate_password(new, user)
    except ValidationError as exc:
        return ' '.join(exc.messages)
    user.set_password(new)
    user.password_changed_at = timezone.now()
    user.password_change_required_at = None
    user.save(update_fields=['password', 'password_changed_at', 'password_change_required_at'])
    update_session_auth_hash(request, user)  # this session stays signed in (it gets a new key)
    ended = sessions.end_sessions(user, keep_session_key=request.session.session_key)
    security_events.record('password.changed', actor=user, subject=user, request=request,
                           door=request_meta.host_kind(request), sessions_ended=ended)
    for membership in user.memberships.select_related('workspace').order_by('created_at', 'pk'):
        audit.record(membership.workspace, 'member.password_changed', actor=user, user=str(user.pk))
    return ''


@ensure_csrf_cookie
@login_required
def account_security(request):
    if request.method not in ('GET', 'POST'):
        return HttpResponseNotAllowed(['GET', 'POST'])
    user = request.user
    on_console = request_meta.host_kind(request) == request_meta.ADMIN
    operator = is_operator(user)
    error = ''
    if request.method == 'POST':
        if operator and not on_console:
            error = OPERATOR_ON_CONSOLE
        elif on_console and not second_factor.recent(request):
            response = HttpResponseRedirect(second_factor.step_up_location(sessions.ACCOUNT_PATH))
            response.status_code = 303  # the change is not made; the operator submits it again after the key
            return response
        else:
            try:
                error = _change_password(request, user)
            except sessions.Refused as refused:
                error = str(refused)
            if not error:
                return redirect(f'{sessions.ACCOUNT_PATH}?done=changed')
    context = {
        'error': error, 'done': CHANGED if request.GET.get('done') == 'changed' and not error else '',
        'required': user.password_change_required_at is not None, 'on_console': on_console,
        'can_change': not (operator and not on_console), 'operator_on_console': OPERATOR_ON_CONSOLE,
        'min_length': settings.PASSWORD_MIN_LENGTH, 'home': '/ops/' if on_console else '/',
        'idle_minutes': sessions.limits(request_meta.ADMIN if on_console else request_meta.CPT)[0] // 60,
    }
    return render(request, 'studio/account_security.html', context, status=200 if not error else 400)


def logout_everywhere(request):
    """POST: end every session of the signed-in account, this one included (B4, item 2)."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    user = request.user
    if user.is_authenticated:
        try:
            ended = sessions.end_sessions(user)
        except sessions.Refused as refused:
            return HttpResponse(str(refused), status=refused.status, content_type='text/plain; charset=utf-8')
        security_events.record('sessions.ended_everywhere', actor=user, subject=user, request=request,
                               door=request_meta.host_kind(request), sessions_ended=ended)
        logout(request)
    return redirect('/login/')


def activity_ping(request):
    """POST: the person is active on the page (B5): the session policy has already moved the session's last activity;
    the answer says how long the session has before it idles out and before its cap, and the warning's lead."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not request.user.is_authenticated:
        return JsonResponse({**sessions.SIGNED_OUT, 'reason': getattr(request, 'cpt_signed_out', None)
                             or sessions.EXPIRED}, status=401)
    idle, cap = sessions.remaining(request)
    return JsonResponse({'idle_seconds': idle, 'cap_seconds': cap,
                         'warning_seconds': settings.SESSION_IDLE_WARNING_SECONDS})
