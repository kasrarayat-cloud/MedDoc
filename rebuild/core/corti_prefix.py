"""Confine the isolated replay application to its authenticated HTTPS mount.

Only ops.corti_https_settings installs this adapter. Existing native views keep
their root-relative internal paths; URL reversing retains Django's script prefix.
No authentication, permission or clinical/coding decision is supplied here.
"""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse

from .preview_access import safe_destination


PREFIX = '/synthetic/corti'
ORIGIN = 'https://app.quillmd.com'
COOKIE_NAMES = frozenset({'quillmd_corti_session', 'quillmd_corti_csrf'})
AUTH_PATHS = frozenset({'/login/', '/logout/', '/register/',
                        '/preview/sign-in/', '/preview/sign-out/'})


class PrefixRefusal(ValueError):
    """Fixed adapter rejection; unrelated application errors remain visible."""


def local_destination(value, *, require_prefix=False):
    """Reject encoded path tricks and keep every navigation in this mount."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise PrefixRefusal('Invalid synthetic destination.')
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise PrefixRefusal('Invalid synthetic destination.') from None
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != 'https' or parsed.netloc != 'app.quillmd.com':
            raise PrefixRefusal('External synthetic destination refused.')
        value = urlunsplit(('', '', parsed.path, parsed.query, parsed.fragment))
        parsed = urlsplit(value)
    # All application route paths are literal ASCII. Queries may legitimately
    # contain escaped search text; the existing safe-destination check covers it.
    if (not safe_destination(value) or '%' in parsed.path
            or parsed.path.startswith(PREFIX + PREFIX)
            or parsed.path == PREFIX):
        raise PrefixRefusal('Ambiguous synthetic destination refused.')
    mounted = parsed.path.startswith(PREFIX + '/')
    if require_prefix and not mounted:
        raise PrefixRefusal('Destination outside synthetic application.')
    path = parsed.path if mounted else PREFIX + parsed.path
    return urlunsplit(('', '', path, parsed.query, ''))


def next_destination(value):
    mounted = local_destination(value, require_prefix=True)
    internal = mounted[len(PREFIX):]
    if urlsplit(internal).path in AUTH_PATHS:
        raise PrefixRefusal('Authentication loop refused.')
    return mounted


def redirect_destination(value):
    mounted = local_destination(value)
    parts = urlsplit(mounted)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    if sum(key == 'next' for key, _ in pairs) > 1:
        raise PrefixRefusal('Ambiguous next destination.')
    # Existing AccessMiddleware emits /login/?next=/encounters/.... Scope both
    # layers, so a subsequent sign-in cannot navigate into the native dashboard.
    if any(key == 'next' for key, _ in pairs):
        rewritten = []
        for key, item in pairs:
            if key == 'next' and item:
                item = local_destination(item)
                next_destination(item)
            rewritten.append((key, item))
        mounted = urlunsplit(('', '', parts.path, urlencode(rewritten), ''))
    return mounted


def refusal():
    response = HttpResponseForbidden('The synthetic application request could not be verified.',
                                     content_type='text/plain')
    return protected_headers(response)


def protected_headers(response):
    response['Cache-Control'] = 'no-store, private'
    response['Referrer-Policy'] = 'same-origin'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


class CortiPrefixMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if (settings.FORCE_SCRIPT_NAME != PREFIX
                    or request.get_host() != 'app.quillmd.com'
                    or not request.is_secure()
                    or request.headers.get('X-QuillMD-Account') != '1'
                    or request.headers.get('X-QuillMD-Corti-Prefix') != PREFIX
                    or request.META.get('SCRIPT_NAME') != PREFIX
                    or not settings.SYNTHETIC_ONLY):
                return refusal()
            # nginx strips exactly the mount prefix. The external request path
            # is retained separately for audit/debug; native middleware receives
            # its expected root-relative path. Django reversing remains prefixed.
            local_destination(request.path_info)
            if request.path_info.startswith(PREFIX + '/'):
                return refusal()
            request.corti_external_path = PREFIX + request.path_info
            request.path = request.path_info
            request.COOKIES = {name: value for name, value in request.COOKIES.items()
                               if name in COOKIE_NAMES}
            if request.method not in {'GET', 'HEAD', 'OPTIONS', 'TRACE'}:
                origin = request.headers.get('Origin')
                if origin is not None and origin != ORIGIN:
                    return refusal()
                # Same-origin CSRF alone cannot distinguish the native dashboard
                # from this mount. Candidate pages publish same-origin referrers.
                referring = request.headers.get('Referer', '')
                if not referring.startswith(ORIGIN + PREFIX + '/'):
                    return refusal()
                local_destination(referring, require_prefix=True)
            for name in ('GET', 'POST'):
                values = getattr(request, name)
                if 'next' not in values:
                    continue
                if len(values.getlist('next')) != 1:
                    return refusal()
                if values['next']:
                    changed = values.copy()
                    changed['next'] = next_destination(values['next'])
                    setattr(request, name, changed)
            response = self.get_response(request)
            if response.has_header('Location'):
                response['Location'] = redirect_destination(response['Location'])
            if any(name not in COOKIE_NAMES or cookie['path'] != PREFIX + '/'
                   for name, cookie in response.cookies.items()):
                return refusal()
            return protected_headers(response)
        except PrefixRefusal:
            return refusal()


def csrf_failure(request, reason=''):
    """Retain the real CSRF refusal with a confined sign-in link."""
    if 'application/json' in request.headers.get('Accept', ''):
        return protected_headers(JsonResponse({'error': 'csrf_failed',
            'message': 'Reload the synthetic form and try again.',
            'sign_in_url': PREFIX + '/login/'}, status=403))
    from .preview_access import error
    return protected_headers(error(request, 'Reload the synthetic form and try again.',
        status=403, heading='Reload the form to continue',
        continue_url=PREFIX + '/login/'))
