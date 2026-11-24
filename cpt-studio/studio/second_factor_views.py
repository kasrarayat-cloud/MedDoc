"""The operator's second factor at the admin door (release 1, B2; RELEASE-1-SPEC 3.4): the sign-in's second step, setup
with a code issued on the server, recovery codes, and the keys page. Lane 1 routes them, and every view is a stub that
answers Django's 404 - so a half-merged main exposes nothing - until Lane 2 replaces it with the WebAuthn ceremony
(py_webauthn) around studio.second_factor's gate.

    GET, POST /login/second-factor            the key, after a checked password (admin host only)
    POST      /login/second-factor/options    the signed challenge's options (admin host only)
    GET, POST /login/enrol                    setup: code, new password, first key (admin host only)
    POST      /login/enrol/options            the new key's options (admin host only)
    GET, POST /login/recovery                 a recovery code in place of a key (admin host only)
    GET, POST /ops/security                   the operator's keys (the console, behind operator_view)
"""
from django.http import Http404
from django.views.decorators.common import no_append_slash
from django.views.decorators.csrf import csrf_exempt


# R1 stub: Lane 2 replaces this (B2)
@csrf_exempt
@no_append_slash
def second_factor(request, *args, **kwargs):
    raise Http404()


# R1 stub: Lane 2 replaces this (B2)
@csrf_exempt
@no_append_slash
def second_factor_options(request, *args, **kwargs):
    raise Http404()


# R1 stub: Lane 2 replaces this (B2)
@csrf_exempt
@no_append_slash
def enrol(request, *args, **kwargs):
    raise Http404()


# R1 stub: Lane 2 replaces this (B2)
@csrf_exempt
@no_append_slash
def enrol_options(request, *args, **kwargs):
    raise Http404()


# R1 stub: Lane 2 replaces this (B2)
@csrf_exempt
@no_append_slash
def recovery(request, *args, **kwargs):
    raise Http404()


# R1 stub: Lane 2 replaces this (B2)
@csrf_exempt
@no_append_slash
def keys(request, *args, **kwargs):
    raise Http404()
