"""Health, sign-in/out and the single-page shell."""
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

from .access import active_membership
from .models import LoginAttempt


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
        username = request.POST.get('username', '').strip()[:150]
        password = request.POST.get('password', '')
        client = _client(request)
        if _throttled(username, client):
            error = 'Too many failed attempts. Wait 15 minutes and try again.'
        else:
            user = authenticate(request, username=username, password=password)
            LoginAttempt.objects.create(username=username, client=client, succeeded=user is not None)
            if user is not None and user.memberships.filter(active=True).exists():
                login(request, user)
                return redirect(next_url)
            error = 'The username or password is not correct.'
    context = {'error': error, 'next': next_url, 'username': request.POST.get('username', '')[:150] if error else ''}
    return render(request, 'studio/login.html', context, status=200 if not error else 400)


def logout_view(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    logout(request)
    return redirect('/login/')


@ensure_csrf_cookie
@login_required
def index(request):
    active_membership(request.user)  # 404 for accounts without an active workspace
    return render(request, 'studio/index.html', {'release': settings.RELEASE_SHA})
