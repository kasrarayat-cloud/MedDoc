"""Independent private-preview access; account login and MFA are unchanged."""
from contextlib import contextmanager
import ipaddress
import re
import secrets
import time
import unicodedata
from urllib.parse import unquote, urlsplit

from django import forms
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.csrf import csrf_failure as default_csrf_failure
from django.views.decorators.http import require_http_methods, require_POST

from .security import audit, rate_limit

COOKIE = '__Host-quillmd_preview'
SIGN_IN = '/preview/sign-in/'
SIGN_OUT = '/preview/sign-out/'
KIND = 'quillmd-preview-v1'
IDLE_SECONDS = 1800
ABSOLUTE_SECONDS = 7200
FLOW_SECONDS = 900
MAX_FLOWS = 8
FLOW_PATTERN = re.compile(r'[a-f0-9]{32}')
CSS_PATTERN = re.compile(r'/static/app(?:\.[a-f0-9]{12})?\.css')


def safe_destination(value):
    """Accept a local GET location, including existing capability paths only."""
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        return False
    decoded = value
    for decoding_pass in range(4):
        if (not decoded.startswith('/') or decoded.startswith('//') or '\\' in decoded
                or any((c.isspace() and c != ' ') or unicodedata.category(c).startswith('C') for c in decoded)
                or re.search(r'%(?![a-fA-F0-9]{2})', decoded)
                or re.search(r'[A-Za-z][A-Za-z0-9+.-]*:', decoded)):
            return False
        try:
            parsed = urlsplit(decoded)
        except ValueError:
            return False
        if parsed.scheme or parsed.netloc or parsed.fragment or any(part in {'.', '..'} for part in parsed.path.split('/')):
            return False
        if ' ' in decoded and (decoding_pass == 0 or ' ' in parsed.path):
            # A normal encoded search-query space is safe; raw spaces and path
            # whitespace remain refused. Return the original encoded location.
            return False
        next_value = unquote(decoded)
        if next_value == decoded:
            return True
        decoded = next_value
    return False


def fingerprint():
    username = settings.QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME
    password = settings.QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD
    if (settings.QUILLMD_APP_BASE_URL != settings.QUILLMD_PREVIEW_ORIGIN or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', username)
            or not re.fullmatch(r'[!-~]{20,128}', password)):
        return None
    return salted_hmac(KIND, username + '\0' + password).hexdigest()


def valid_grant(store, now):
    grant = store.get('grant', {})
    try:
        return (isinstance(grant, dict) and bool(fingerprint())
                and constant_time_compare(grant.get('fingerprint', ''), fingerprint())
                and 0 <= now - grant['issued'] < ABSOLUTE_SECONDS
                and 0 <= now - grant['seen'] < IDLE_SECONDS)
    except (KeyError, TypeError, ValueError):
        return False


@contextmanager
def preview_store(request):
    """Serialize per-browser updates; never modify another kind of session."""
    with transaction.atomic():
        key = request.COOKIES.get(COOKIE)
        if not isinstance(key, str) or not re.fullmatch(r'[a-z0-9]{32}', key):
            key = None
        if key:
            Session.objects.select_for_update().filter(session_key=key).exists()
        store = SessionStore(session_key=key)
        if store.get('kind') != KIND:
            # A copied account-session cookie must not be changed or deleted.
            store = SessionStore()
            store['kind'] = KIND
        yield store
        if getattr(request, '_preview_delete_cookie', False):
            return
        if store.modified or not store.session_key:
            remaining = IDLE_SECONDS
            if valid_grant(store, time.time()):
                remaining = max(1, min(IDLE_SECONDS, int(store['grant']['issued'] + ABSOLUTE_SECONDS - time.time())))
            store.set_expiry(remaining)
            store.save()
            request._preview_set_cookie = (store.session_key, remaining)


def flows(store, now):
    return {key: value for key, value in store.get('flows', {}).items()
            if FLOW_PATTERN.fullmatch(key) and isinstance(value, dict)
            and isinstance(value.get('created'), (int, float))
            and 0 <= now - value['created'] < FLOW_SECONDS
            and safe_destination(value.get('destination'))}


def api_request(request):
    return (request.path_info.startswith('/api/') or request.path_info == '/billing/webhook/'
            or 'application/json' in request.headers.get('Accept', ''))


def error(request, message, *, status=403, heading='Private preview access required', continue_url=None):
    request.user = getattr(request, 'user', AnonymousUser())
    if api_request(request):
        return JsonResponse({'error': 'private_preview_access_required', 'message': message,
                             'sign_in_url': SIGN_IN}, status=status)
    return render(request, 'preview_error.html', {'heading': heading, 'message': message, 'continue_url': continue_url}, status=status)


class PreviewAccessMiddleware:
    """Enforce the gate before static serving and the account-session middleware."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        marker = request.headers.get('X-QuillMD-Preview')
        public_origin = host == urlsplit(settings.QUILLMD_PREVIEW_ORIGIN).netloc
        enabled = settings.QUILLMD_PREVIEW_AUTH_ENABLED and not settings.ADMIN_SITE
        if not enabled:
            if marker is not None:
                return error(request, 'Private preview access is not available. Please contact your platform operator.', status=503)
            return self.get_response(request)
        if host in {'127.0.0.1:9130', 'localhost:9130', '[::1]:9130'} and marker is None:
            return self.get_response(request)
        if not public_origin or marker != '1' or not request.is_secure():
            return error(request, 'Open the original private HTTPS address to continue.')
        request.quillmd_preview = True
        if not fingerprint():
            response = error(request, 'Private access configuration needs repair. Please contact your platform operator.', status=503)
        # Every gate decision on PATH_INFO, the path Django resolves: the full path carries a client SCRIPT_NAME, and
        # SCRIPT_NAME '/preview/sign-in' with PATH_INFO '/' was the sign-in page to this gate while the dashboard was
        # served without a grant (refutation round 2, the R1 sibling).
        elif CSS_PATTERN.fullmatch(request.path_info):
            response = self.get_response(request)
        elif request.path_info in {SIGN_IN, SIGN_OUT}:
            response = self.get_response(request)
        else:
            with preview_store(request) as store:
                now = time.time()
                granted = valid_grant(store, now)
                if granted:
                    store['grant'] = {**store['grant'], 'seen': now}
                elif request.method == 'GET' and not api_request(request):
                    destination = request.get_full_path()
                    if not safe_destination(destination):
                        response = error(request, 'This address cannot be resumed. Open the original link again.', status=400)
                    else:
                        pending = flows(store, now)
                        if len(pending) >= MAX_FLOWS:
                            pending.pop(min(pending, key=lambda key: pending[key]['created']))
                        handle = secrets.token_hex(16)
                        pending[handle] = {'destination': destination, 'created': now}
                        store['flows'] = pending
                        response = redirect(SIGN_IN + '?flow=' + handle)
                else:
                    response = error(request, 'Your private preview access has expired or is missing. Sign in, then reopen the page. Your submission was not repeated.')
            if granted:
                response = self.get_response(request)
                if response.status_code == 404 and request.path_info.startswith('/invite/'):
                    response = render(request, 'preview_error.html', {
                        'heading': 'Invitation link unavailable',
                        'message': 'This invitation may have expired or already been accepted. If you accepted it, sign in to your QuillMD account. Otherwise contact your department owner.',
                        'continue_url': '/login/', 'continue_label': 'Account sign-in'}, status=404)
        if getattr(request, '_preview_delete_cookie', False):
            response.delete_cookie(COOKIE, path='/', samesite='Lax')
        elif hasattr(request, '_preview_set_cookie'):
            key, age = request._preview_set_cookie
            response.set_cookie(COOKIE, key, max_age=age, secure=True, httponly=True, samesite='Lax', path='/')
        response['Cache-Control'] = 'no-store, private'
        # Ordinary browser form POSTs need an origin for Django's CSRF check.
        # Send only that origin, never invitation/recovery paths or query tokens.
        response['Referrer-Policy'] = 'strict-origin'
        response['X-Robots-Tag'] = 'noindex, nofollow'
        response.setdefault('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        return response


class PreviewForm(forms.Form):
    username = forms.CharField(label='Private preview username', max_length=64,
                               widget=forms.TextInput(attrs={'autocomplete': 'username', 'autofocus': True}))
    password = forms.CharField(label='Private preview password', max_length=128, strip=False,
                               widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))
    flow = forms.RegexField(regex=r'^[a-f0-9]{32}$', required=False, widget=forms.HiddenInput)


@require_http_methods(['GET', 'POST'])
def sign_in(request):
    if not getattr(request, 'quillmd_preview', False):
        return HttpResponseForbidden('Private preview sign-in is available only at its approved HTTPS address.')
    handle = request.POST.get('flow', '') if request.method == 'POST' else request.GET.get('flow', '')
    if handle and not FLOW_PATTERN.fullmatch(handle):
        return error(request, 'This access request is invalid. Reopen your original email link.', status=400)
    form = PreviewForm(request.POST if request.method == 'POST' else None, initial={'flow': handle})
    status = 200
    with preview_store(request) as store:
        now = time.time()
        pending = flows(store, now)
        if handle and handle not in pending:
            return error(request, 'This access request expired or was already used. Reopen your original email link.', status=400, heading='Open your original link again')
        if request.method == 'POST' and form.is_valid():
            try:
                # Only this verified proxy context may trust the edge-overwritten
                # header. The loopback application never reaches this view.
                client_ip = str(ipaddress.ip_address(request.headers.get('X-Real-IP', request.META.get('REMOTE_ADDR', ''))))
            except ValueError:
                return error(request, 'The private access request could not be verified.', status=400)
            allowed = rate_limit('preview-ip:' + client_ip, limit=8, seconds=600)
            global_allowed = rate_limit('preview-shared-gate', limit=60, seconds=600)
            if not allowed or not global_allowed:
                form.add_error(None, 'Too many attempts. Wait ten minutes before trying again.')
                status = 429
                audit(None, 'preview.rate_limited')
            else:
                username_ok = constant_time_compare(form.cleaned_data['username'], settings.QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME)
                password_ok = constant_time_compare(form.cleaned_data['password'], settings.QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD)
                if username_ok & password_ok:
                    destination = pending.pop(handle)['destination'] if handle else '/login/'
                    store.cycle_key()
                    store['kind'] = KIND
                    store['grant'] = {'fingerprint': fingerprint(), 'issued': now, 'seen': now}
                    store['flows'] = pending
                    audit(None, 'preview.login')
                    return redirect(destination)
                form.add_error(None, 'The private preview username or password is incorrect. Use the access details provided for this preview.')
                audit(None, 'preview.login_failed')
        response = render(request, 'preview_signin.html', {'form': form, 'resuming': bool(handle)}, status=status)
        if status == 429:
            response['Retry-After'] = '600'
        return response


@require_POST
def sign_out(request):
    if not getattr(request, 'quillmd_preview', False):
        return HttpResponseForbidden('Use the approved private preview address.')
    with preview_store(request) as store:
        store.flush()
        request._preview_delete_cookie = True
        audit(None, 'preview.logout')
    return redirect(SIGN_IN)


def csrf_failure(request, reason=''):
    if getattr(request, 'quillmd_preview', False):
        continuation = None
        if request.path_info == SIGN_IN:
            handle = request.POST.get('flow', '')
            key = request.COOKIES.get(COOKIE, '')
            if FLOW_PATTERN.fullmatch(handle) and re.fullmatch(r'[a-z0-9]{32}', key):
                store = SessionStore(session_key=key)
                if store.get('kind') == KIND and handle in flows(store, time.time()):
                    # Only a live flow bound to this browser may enter the retry
                    # link. Its original capability remains solely server-side.
                    continuation = SIGN_IN + '?flow=' + handle
        return error(request, 'This form expired or could not be verified. Reload the page and try again. Your submission was not processed.', heading='Reload the form to continue', continue_url=continuation)
    return default_csrf_failure(request, reason=reason)
