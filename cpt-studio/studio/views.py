"""Health, sign-in/out and the single-page shell.

The shell's Content-Security-Policy is the site's own (access.SecurityHeadersMiddleware) with frame-src 'self' named, so
the review page's viewer frames the in-page view of the original (GET /api/encounters/<id>/original?view=1, which only
CPT Studio's own pages may frame) and nothing else.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from .access import SecurityHeadersMiddleware, active_membership
from .api import UNSTORABLE
from .models import LoginAttempt
from .operator import is_operator


INDEX_CSP = SecurityHeadersMiddleware.CSP.replace("frame-ancestors 'none'", "frame-src 'self'; frame-ancestors 'none'")


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            database = 'ok' if cursor.fetchone() == (1,) else 'error'
    except Exception:  # noqa: BLE001 — health reports, never raises
        database = 'error'
    status = 200 if database == 'ok' else 503
    return JsonResponse({'status': 'ok' if status == 200 else 'degraded', 'service': 'cpt-studio',
                         'data_mode': 'synthetic-only', 'release': settings.RELEASE_SHA, 'database': database},
                        status=status)


def _client(request):
    # Behind the loopback proxy the real client is in X-Forwarded-For, which
    # nginx REPLACES with $remote_addr; never trust it otherwise.
    if settings.SECURE_PROXY_SSL_HEADER:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        if forwarded:
            return forwarded[:64]
    return request.META.get('REMOTE_ADDR', '')[:64]


def _throttled(username, client):
    since = timezone.now() - timedelta(seconds=settings.LOGIN_THROTTLE_WINDOW_SECONDS)
    failures = LoginAttempt.objects.filter(created_at__gte=since, succeeded=False)
    return (failures.filter(username=username).count() >= settings.LOGIN_THROTTLE_ATTEMPTS
            or failures.filter(client=client).count() >= settings.LOGIN_THROTTLE_ATTEMPTS * 3)


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
        username = UNSTORABLE.sub('\ufffd', submitted)
        password = request.POST.get('password', '')
        client = UNSTORABLE.sub('\ufffd', _client(request))
        if _throttled(username, client):
            error = 'Too many failed attempts. Wait 15 minutes and try again.'
        else:
            user = authenticate(request, username=username, password=password) if username == submitted else None
            LoginAttempt.objects.create(username=username, client=client, succeeded=user is not None)
            if user is not None and user.memberships.filter(active=True).exists():
                login(request, user)
                return redirect(next_url)
            if user is not None and is_operator(user):
                # A platform operator may hold no membership (CORE-UX-DESIGN.md 5): they sign in on this same page and
                # land on the operator diagnostics, or where they asked to go (an operator who is also a member signs in
                # as the member, above)
                login(request, user)
                return redirect(next_url if next_url != '/' else '/ops/')
            error = 'The username or password is not correct.'
    context = {'error': error, 'next': next_url,
               'username': UNSTORABLE.sub('\ufffd', request.POST.get('username', ''))[:150] if error else ''}
    return render(request, 'studio/login.html', context, status=200 if not error else 400)


def logout_view(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    logout(request)
    return redirect('/login/')


@ensure_csrf_cookie
@login_required
def index(request):
    if is_operator(request.user) and not request.user.memberships.filter(active=True).exists():
        return redirect('/ops/')  # an operator with no membership has no workspace here: the diagnostics are theirs
    membership = active_membership(request.user)  # 404 for accounts without an active workspace
    # the workspace's specialty, a label the page shows (owner direction 2026-11-22, D390); nothing codes from it
    response = render(request, 'studio/index.html', {'release': settings.RELEASE_SHA,
                                                     'specialty': membership.workspace.category.name})
    response.headers['Content-Security-Policy'] = INDEX_CSP
    return response


# The admin host (admin.quillmd.com; owner direction 2026-11-23, DECISIONS D396; cptstudio.urls_admin).
ADMIN_SIGN_IN_REFUSED = 'The username or password is not correct, or the account is not a platform operator.'


def admin_home(request):
    """admin.quillmd.com/: an operator goes to the console, anyone else to the operator sign-in - every method alike, so
    a monitor's HEAD gets the same 302 as a browser's GET."""
    return redirect('/ops/' if is_operator(request.user) else '/login/')


def admin_ops_slash(request):
    """admin.quillmd.com/ops goes to /ops/ (the full urlconf keeps /ops answering what /opsx answers)."""
    return redirect('/ops/')


@ensure_csrf_cookie
def admin_login_view(request):
    """The operator door on the admin host: login_view's form, CSRF, next rule and throttle, but only a platform operator
    signs in here. Any other account - a doctor with the right password included - gets the same sentence as a wrong
    password and no session, so this door never tells a doctor's password apart; its attempt is recorded as not
    succeeded (LoginAttempt has no door column), which the shared throttle counts. An operator who is also a member signs
    in as the operator: this host has no doctor app. next may only name a console page on this host."""
    if request.method not in ('GET', 'POST'):
        return HttpResponseNotAllowed(['GET', 'POST'])
    next_url = request.POST.get('next') or request.GET.get('next') or '/ops/'
    if not (next_url.startswith('/ops/') and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure())):
        next_url = '/ops/'
    error = ''
    if request.method == 'POST':
        submitted = request.POST.get('username', '').strip()[:150]
        username = UNSTORABLE.sub('�', submitted)
        password = request.POST.get('password', '')
        client = UNSTORABLE.sub('�', _client(request))
        if _throttled(username, client):
            error = 'Too many failed attempts. Wait 15 minutes and try again.'
        else:
            user = authenticate(request, username=username, password=password) if username == submitted else None
            operator = is_operator(user)
            LoginAttempt.objects.create(username=username, client=client, succeeded=operator)
            if operator:
                login(request, user)
                return redirect(next_url)
            error = ADMIN_SIGN_IN_REFUSED
    context = {'error': error, 'next': next_url, 'release': settings.RELEASE_SHA,
               'username': UNSTORABLE.sub('�', request.POST.get('username', ''))[:150] if error else ''}
    return render(request, 'studio/ops_login.html', context, status=200 if not error else 400)
