"""The admin host (owner direction 2026-11-23, DECISIONS D396): admin.quillmd.com serves the operator console and its
sign-in alone, from its own urlconf (cptstudio.urls_admin); every other allowed host keeps the full urlconf
(cptstudio.urls). Host routing is a convenience, never the security boundary: operator_view guards every console view on
both hosts, and a request straight to the loopback port that names the admin host meets the same gate.

The host is the request's Host header as Django reads it (USE_X_FORWARDED_HOST stays off, so a client's X-Forwarded-Host
chooses nothing), already checked against ALLOWED_HOSTS by get_host(); its port, if any, is set aside."""
import functools
from urllib.parse import urlencode

from django.conf import settings
from django.http.request import split_domain_port
from django.shortcuts import redirect

ADMIN_URLCONF = 'cptstudio.urls_admin'


def is_admin_host(request) -> bool:
    return split_domain_port(request.get_host())[0] == settings.ADMIN_HOST


class HostUrlconfMiddleware:
    """Placed before CommonMiddleware, so its slash rule and every resolve read the host's own urlconf."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_admin_host(request):
            request.urlconf = ADMIN_URLCONF
        return self.get_response(request)


def signed_out_to_sign_in(view):
    """A console view as the admin host serves it: a signed-out GET or HEAD goes to the operator sign-in, which brings the
    operator back to the page asked for (D396 (b): no unexplained 404 for a visitor on the admin host). Every other request
    - any other method, any signed-in account - reaches the view, whose operator_view answers anyone who is not an
    operator with Django's 404, exactly as on cpt.quillmd.com."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.method in ('GET', 'HEAD') and not request.user.is_authenticated:
            return redirect('/login/?' + urlencode({'next': request.get_full_path()}))
        return view(request, *args, **kwargs)
    return wrapper
