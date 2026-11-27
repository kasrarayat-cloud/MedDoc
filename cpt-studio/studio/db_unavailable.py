"""A database that cannot be reached answers 503, never Django's HTML 500 (integrated refutation round 1, avail-0).

A connection the database ended while a request ran, or a database that refuses connections for a while (a restart),
raised django.db's OperationalError or InterfaceError wherever the request was - the session's load, the membership,
the document's scope, a query after the read's record was written - and Django answered its HTML 500 (an error page
the page reads as "Something went wrong"), with a traceback logged for each. R2-7 keeps the web's connections and
checks them at a request's first query, which replaces one the database ended between requests; this is the rest.
Only a lost or unusable connection is answered so (is_database_unavailable; integrated refutation round 2, I2-4):
PostgreSQL reports other errors as OperationalError too - a deadlock, a cancelled statement, a lock not granted, a full
disk - and each of those stays Django's own 500, its traceback logged, as before.

- DatabaseUnavailableMiddleware (cptstudio/settings.py MIDDLEWARE) answers such an error a view raises;
- server_error, both urlconfs' handler500 (cptstudio/urls.py, cptstudio/urls_admin.py), answers one another middleware
  raises - the session's load in studio.sessions.SessionPolicyMiddleware, the session store's own bookkeeping of its
  links around the save in SessionMiddleware (studio.session_store) - which Django converts at that middleware's own
  layer through handler500, calling no middleware's process_exception.

A recorded limit (integrated refutation round 1, I1-20): a loss in Django's own write of the session's row at that save
reaches neither. Django's SessionStore.save turns a database error of an update into UpdateError, which
SessionMiddleware raises as SessionInterrupted: Django's own 400 (an HTML page, no Retry-After), left as Django answers
it, since catching it would catch more than a lost database. The view's answer is not sent then either, and a read's
record, already written, says it was served. A request writes its session only when it changed it: under /api/ only its
activity time, at most once a minute (SESSION_ACTIVITY_WRITE_SECONDS).

Both answer database_unavailable: 503 with Retry-After; under /api/ the API's fail-closed JSON with no exception text -
for a read (a GET or HEAD, and the search, a POST only so its words stay out of addresses) studio.read_audit's
NOT_RECORDED sentence, for a change CHANGE_UNKNOWN, which says neither that it was kept nor that it was not: a loss can
come after the database committed it (a decision's refresh after its transaction; an upload whose COMMIT's answer was
lost) - elsewhere Django's own plain error page, titled "Service Unavailable (503)". A read's own record, lost as it is
written (studio.read_audit.NotRecorded from a lost connection), is answered the same (raise_if_lost: Retry-After
included). Nothing of the request is served: the answer is made in place of the view's, and a read whose record was
already written is answered with it all the same (its record then says more than was shown, never less). Every other
exception is Django's own 500 exactly as before (django.views.defaults.server_error): nothing else is caught.
Cache-Control no-store and the site's policy come from studio.access.SecurityHeadersMiddleware, which wraps every
answer.
"""
from __future__ import annotations

import sys

from django.db import InterfaceError, OperationalError
from django.http import HttpResponse, JsonResponse
from django.views import defaults

from . import read_audit

# The errors of a database that cannot be reached (is_database_unavailable): a connection already closed
# (InterfaceError), or an OperationalError of a connection the database ended, refused or never gave - the driver's
# own, with no SQLSTATE (a refusal at connect: a restart, a database not accepting connections; a connection broken
# under a statement), or the server's with class 08 (a connection exception) or 57P01-57P03 (shut down by an operator,
# by a crash, or not yet accepting). Any other OperationalError - a deadlock (40P01), a serialization failure (40001),
# a cancelled statement (57014), a lock not granted (55P03), a full disk (53100), memory (53200), a program limit
# (54000) - is the request's own error, as is any IntegrityError, DataError or ProgrammingError: Django's 500 with its
# traceback.
LOST_CONNECTION_SQLSTATES = frozenset({'57P01', '57P02', '57P03'})
# How soon to ask again: R2-7's health check replaces a lost connection at the next request's first query
DATABASE_RETRY_AFTER_SECONDS = 5
DATABASE_UNAVAILABLE_PAGE = defaults.ERROR_PAGE_TEMPLATE % {'title': 'Service Unavailable (503)', 'details': ''}
# The sentence of a change the database could not be reached for: it may have been kept or not, so this says neither and
# sends the member to the latest state - a sentence the page already says (app.js errorText's 409), so no new words
CHANGE_UNKNOWN = 'This action is not available right now. Reload the page to see the latest state.'
# The API's one read that is a POST (R2-20: so its words stay out of addresses)
READ_BY_POST = '/api/encounters/search'


def is_database_unavailable(exception) -> bool:
    """Whether ``exception`` is a lost or unusable database connection (LOST_CONNECTION_SQLSTATES' comment): an
    InterfaceError, or an OperationalError whose driver error (its __cause__) carries no SQLSTATE, class 08 or one of
    LOST_CONNECTION_SQLSTATES. An OperationalError raised with no driver error under it counts as lost too."""
    if isinstance(exception, InterfaceError):
        return True
    if not isinstance(exception, OperationalError):
        return False
    sqlstate = getattr(exception.__cause__, 'sqlstate', None)
    return sqlstate is None or str(sqlstate)[:2] == '08' or sqlstate in LOST_CONNECTION_SQLSTATES


def raise_if_lost(refused) -> None:
    """A read whose own record could not be written (``refused``, a read_audit.NotRecorded) because the connection was
    lost is answered as a database that cannot be reached: its error is raised again for the doors above (503 with
    Retry-After). Any other refusal is left to the caller's own 503."""
    if is_database_unavailable(refused.__cause__):
        raise refused.__cause__


def database_unavailable(request) -> HttpResponse:
    """The 503 a request meets when the database cannot be reached: JSON under /api/ (a read's sentence or a change's),
    the plain error page elsewhere."""
    if request.path.startswith('/api/'):
        read = request.method in ('GET', 'HEAD') or request.path == READ_BY_POST
        sentence = read_audit.NOT_RECORDED if read else CHANGE_UNKNOWN
        response = JsonResponse({'error': sentence, 'details': {}}, status=503)
    else:
        response = HttpResponse(DATABASE_UNAVAILABLE_PAGE, status=503, content_type='text/html; charset=utf-8')
    response['Retry-After'] = str(DATABASE_RETRY_AFTER_SECONDS)
    return response


class DatabaseUnavailableMiddleware:
    """A lost or unusable connection a view raises (is_database_unavailable) answers database_unavailable; anything
    else goes on to Django's own handling, unchanged."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if is_database_unavailable(exception):
            return database_unavailable(request)
        return None


def server_error(request, template_name=defaults.ERROR_500_TEMPLATE_NAME):
    """handler500: called inside Django's own except block, so the exception being handled is sys.exc_info()'s. A
    database that cannot be reached answers database_unavailable; anything else Django's own 500."""
    if is_database_unavailable(sys.exc_info()[1]):
        return database_unavailable(request)
    return defaults.server_error(request, template_name=template_name)
