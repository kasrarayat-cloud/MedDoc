"""The admin host (owner direction 2026-11-23, DECISIONS D396): admin.quillmd.com serves the operator console and its
sign-in alone, from its own urlconf (cptstudio.urls_admin); every other allowed host keeps the full urlconf
(cptstudio.urls). Host routing is a convenience, never the security boundary: operator_view guards every console view on
both hosts, and a request straight to the loopback port that names the admin host meets the same gate.

The host is the request's Host header as Django reads it (USE_X_FORWARDED_HOST stays off, so a client's X-Forwarded-Host
chooses nothing), already checked against ALLOWED_HOSTS by get_host(); its port, if any, is set aside."""
import functools
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.http.request import split_domain_port
from django.shortcuts import redirect
from django.urls import Resolver404, resolve
from django.views.csrf import csrf_failure

ADMIN_URLCONF = 'cptstudio.urls_admin'
SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS', 'TRACE')  # CsrfViewMiddleware's own


def is_admin_host(request) -> bool:
    return split_domain_port(request.get_host())[0] == settings.ADMIN_HOST


def foreign_origin(request) -> str:
    """Why an unsafe request to the admin host comes from another origin, or nothing. The admin host trusts only its own
    origin: CSRF_TRUSTED_ORIGINS (cpt.quillmd.com's) is global in Django and would let a page on cpt.quillmd.com post to
    the console, so it never applies here (refutation h1, door-1). The own origin is Django's: the scheme the request
    arrived on (TRUST_PROXY behind nginx) and get_host()."""
    own = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}"
    origin = request.META.get('HTTP_ORIGIN')
    if origin is not None:
        return '' if origin == own else 'Origin checking failed - the admin host accepts only its own origin.'
    referer = request.META.get('HTTP_REFERER')
    if referer:  # on a plain request too: the own origin carries the scheme (refutation h2, fresh-4)
        try:
            parts = urlsplit(referer)
        except ValueError:  # refused as Django's own Referer rule refuses it, never a 500 (refutation h2, fresh-1)
            return 'Referer checking failed - Referer is malformed.'
        if f'{parts.scheme}://{parts.netloc}' != own:
            return 'Referer checking failed - the admin host accepts only its own origin.'
    return ''  # neither header: CsrfViewMiddleware's own Referer rule refuses a secure request that names none


def is_console_page(target) -> bool:
    """Whether ``target`` (a sign-in's next) names a console page of the admin host: a path alone - no scheme, no host -
    that resolves in the admin urlconf to an ops/ route. A path that climbs out ('/ops/../login/', '/ops/%2e%2e/') or
    names anything else resolves to no console route (refutation h2, fresh-3)."""
    try:
        parts = urlsplit(target)
    except ValueError:
        return False
    if parts.scheme or parts.netloc or not parts.path.startswith('/ops/'):
        return False
    try:
        match = resolve(parts.path, urlconf=ADMIN_URLCONF)
    except Resolver404:
        return False
    return str(match.route).startswith('ops/')


class HostUrlconfMiddleware:
    """Placed before CommonMiddleware, so its slash rule and every resolve read the host's own urlconf, and before
    CsrfViewMiddleware, so the admin host's own-origin rule (foreign_origin) runs ahead of every view - csrf_exempt and
    csrf_protect ones alike."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_admin_host(request):
            request.urlconf = ADMIN_URLCONF
            if request.method not in SAFE_METHODS:
                reason = foreign_origin(request)
                if reason:
                    return csrf_failure(request, reason=reason)
        return self.get_response(request)


def signed_out_to_sign_in(view):
    """A console view as the admin host serves it: any signed-out request goes to the operator sign-in (D396 (b): no
    unexplained 404 for a visitor on the admin host) - a GET or HEAD with the page asked for as next, any other method (a
    form submitted after the session ended) with a 303 and the console's front page as next, its body never read
    (refutation h1, regression-2). Every signed-in request reaches the view, whose operator_view answers any account that
    is not an operator with Django's 404, exactly as on cpt.quillmd.com."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.method in ('GET', 'HEAD'):
                return redirect('/login/?' + urlencode({'next': request.get_full_path()}))
            response = redirect('/login/?' + urlencode({'next': '/ops/'}))
            response.status_code = 303
            return response
        return view(request, *args, **kwargs)
    # said here, not left to functools.wraps copying them from operator_view's wrapper (refutation h2, repairs-3): the
    # global CSRF check never runs ahead of this redirect, and operator_view's csrf_protect runs after its gate
    wrapper.csrf_exempt = True
    wrapper.should_append_slash = False
    return wrapper
