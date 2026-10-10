"""Account-only HTTPS transport and safe redirects for retired preview links.

The shared preview gate is retired. Historical preview cookies and session rows
have no authority and are never loaded, renewed or deleted by this module.
"""
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.csrf import csrf_failure as default_csrf_failure
from django.views.decorators.http import require_http_methods


# Kept as inert identifiers for retained evidence and historical fixtures.
COOKIE = '__Host-quillmd_preview'
KIND = 'quillmd-preview-v1'
IDLE_SECONDS = 1800
ABSOLUTE_SECONDS = 7200
FLOW_SECONDS = 900
SIGN_IN = '/preview/sign-in/'
SIGN_OUT = '/preview/sign-out/'
OWNER_NORMAL_HOST = 'app.quillmd.com'
OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED = True
DIRECT_ACCOUNT_ORIGIN_PROTOCOL_QUALIFIED = True
ACCOUNT_LOGIN = '/login/'


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
            return False
        next_value = unquote(decoded)
        if next_value == decoded:
            return True
        decoded = next_value
    return False


def account_destination(value):
    """Reject authentication loops while preserving safe protected GET pages."""
    if not safe_destination(value):
        return ''
    path = urlsplit(value).path
    for _ in range(4):
        path = unquote(path)
    if path in {ACCOUNT_LOGIN, '/logout/', '/register/', SIGN_IN, SIGN_OUT}:
        return ''
    return value


def api_request(request):
    return (request.path.startswith('/api/') or request.path == '/billing/webhook/'
            or 'application/json' in request.headers.get('Accept', ''))


def local_transport_host(host):
    """Only explicit isolated hosts may omit the trusted public selector."""
    try:
        parsed = urlsplit('//' + host)
        port = parsed.port
    except ValueError:
        return False
    return (parsed.hostname in {'localhost', '127.0.0.1', '::1', 'testserver'}
            and not parsed.username and not parsed.password
            and (port is None or 1 <= port <= 65535))


def account_redirect(*, canonical=False):
    """Retired links cannot carry tokens, restore submissions or alter sessions."""
    response = HttpResponse(status=303)
    response['Location'] = ('https://' + OWNER_NORMAL_HOST if canonical else '') + ACCOUNT_LOGIN
    return response


def error(request, message, *, status=403, heading='Account access unavailable', continue_url=None):
    request.user = getattr(request, 'user', AnonymousUser())
    if api_request(request):
        return JsonResponse({'error': 'account_access_unavailable', 'message': message,
                             'sign_in_url': ACCOUNT_LOGIN}, status=status)
    return render(request, 'preview_error.html', {
        'heading': heading, 'message': message, 'continue_url': continue_url,
        'continue_label': 'Account sign-in'}, status=status)


class AccountOriginMiddleware:
    """Validate the trusted public transport; account auth owns authorization.

    The edge overwrites X-QuillMD-Account and X-Forwarded-Proto before forwarding
    to the loopback service. No shared secret, preview flag or cookie is read.
    Local development/QA retain their separately isolated HTTP transport.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        marker = request.headers.get('X-QuillMD-Account')
        if host in {OWNER_NORMAL_HOST + ':9443', OWNER_NORMAL_HOST + ':443'}:
            response = account_redirect(canonical=True)
        elif host in {'admin.quillmd.com', 'admin.quillmd.com:443'}:
            response = error(request, 'Use the normal QuillMD account address.')
        elif host == OWNER_NORMAL_HOST:
            if (settings.ADMIN_SITE or not OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED
                    or not DIRECT_ACCOUNT_ORIGIN_PROTOCOL_QUALIFIED
                    or not getattr(settings, 'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED', False)
                    or not getattr(settings, 'QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED', False)
                    or not getattr(settings, 'QUILLMD_TRUST_PROXY', False)
                    or marker != '1' or not request.is_secure()):
                response = error(request, 'The HTTPS account transport could not be verified.')
            else:
                request.quillmd_account_origin = True
                response = (account_redirect() if request.path in {SIGN_IN, SIGN_OUT}
                            else self.get_response(request))
        elif marker is not None or not local_transport_host(host):
            response = error(request, 'The account request has an unexpected application origin.')
        else:
            response = self.get_response(request)

        # Retire only the browser cookie; an account cookie copied into its old
        # name must not load, flush or change the underlying account session.
        if COOKIE in request.COOKIES:
            response.delete_cookie(COOKIE, path='/', samesite='Lax')
        if not request.path.startswith('/static/'):
            response['Cache-Control'] = 'no-store, private'
        response.setdefault('Referrer-Policy', 'strict-origin')
        response['X-Robots-Tag'] = 'noindex, nofollow'
        response.setdefault('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        return response


# Compatibility for retained deployment readers; the implementation is account
# transport only, and contains no preview-grant verifier or credentials.
PreviewAccessMiddleware = AccountOriginMiddleware


@require_http_methods(['GET', 'HEAD', 'POST'])
def sign_in(request):
    return account_redirect()


@require_http_methods(['GET', 'HEAD', 'POST'])
def sign_out(request):
    return account_redirect()


def csrf_failure(request, reason=''):
    if getattr(request, 'quillmd_account_origin', False):
        return error(request,
                     'This form expired or could not be verified. Reload the page and try again. Your submission was not processed.',
                     heading='Reload the form to continue', continue_url=ACCOUNT_LOGIN)
    return default_csrf_failure(request, reason=reason)
