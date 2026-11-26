"""A database that cannot be reached answers 503, never Django's HTML 500 (integrated refutation round 1, avail-0).

A connection the database ended while a request ran, or a database that refuses connections for a while (a restart),
raised django.db's OperationalError or InterfaceError wherever the request was - the session's load, the membership,
the document's scope, a query after the read's record was written - and Django answered its HTML 500 (an error page
the page reads as "Something went wrong"), with a traceback logged for each. R2-7 keeps the web's connections and
checks them at a request's first query, which replaces one the database ended between requests; this is the rest:

- DatabaseUnavailableMiddleware (cptstudio/settings.py MIDDLEWARE) answers such an error a view raises;
- server_error, both urlconfs' handler500 (cptstudio/urls.py, cptstudio/urls_admin.py), answers one another middleware
  raises - the session's load in studio.sessions.SessionPolicyMiddleware, its save in SessionMiddleware - which Django
  converts at that middleware's own layer through handler500, calling no middleware's process_exception.

Both answer database_unavailable: 503 with Retry-After; under /api/ the API's fail-closed answer (studio.read_audit's
NOT_RECORDED sentence: no exception text), elsewhere Django's own plain error page, titled "Service Unavailable (503)".
Nothing of the request is served: the answer is made in place of the view's, and a read whose record was already
written is answered with it all the same (its record then says more than was shown, never less). Every other exception
is Django's own 500 exactly as before (django.views.defaults.server_error): nothing else is caught. Cache-Control
no-store and the site's policy come from studio.access.SecurityHeadersMiddleware, which wraps every answer.
"""
from __future__ import annotations

import sys

from django.db import InterfaceError, OperationalError
from django.http import HttpResponse, JsonResponse
from django.views import defaults

from . import read_audit

# The errors of a database that cannot be reached: a connection it ended or refused (OperationalError), one that is
# already closed (InterfaceError). Not IntegrityError, DataError, ProgrammingError or any other: those stay 500.
DATABASE_UNAVAILABLE_ERRORS = (OperationalError, InterfaceError)
# How soon to ask again: R2-7's health check replaces a lost connection at the next request's first query
DATABASE_RETRY_AFTER_SECONDS = 5
DATABASE_UNAVAILABLE_PAGE = defaults.ERROR_PAGE_TEMPLATE % {'title': 'Service Unavailable (503)', 'details': ''}


def database_unavailable(request) -> HttpResponse:
    """The 503 a request meets when the database cannot be reached: JSON under /api/, the plain error page elsewhere."""
    if request.path.startswith('/api/'):
        response = JsonResponse({'error': read_audit.NOT_RECORDED, 'details': {}}, status=503)
    else:
        response = HttpResponse(DATABASE_UNAVAILABLE_PAGE, status=503, content_type='text/html; charset=utf-8')
    response['Retry-After'] = str(DATABASE_RETRY_AFTER_SECONDS)
    return response


class DatabaseUnavailableMiddleware:
    """An OperationalError or InterfaceError a view raises answers database_unavailable; anything else goes on to
    Django's own handling, unchanged."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, DATABASE_UNAVAILABLE_ERRORS):
            return database_unavailable(request)
        return None


def server_error(request, template_name=defaults.ERROR_500_TEMPLATE_NAME):
    """handler500: called inside Django's own except block, so the exception being handled is sys.exc_info()'s. A
    database that cannot be reached answers database_unavailable; anything else Django's own 500."""
    if isinstance(sys.exc_info()[1], DATABASE_UNAVAILABLE_ERRORS):
        return database_unavailable(request)
    return defaults.server_error(request, template_name=template_name)
