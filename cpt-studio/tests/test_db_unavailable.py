"""Integrated refutation round 1, avail-0 (I1-15): a database that cannot be reached answers 503 wherever the request
is, never Django's HTML 500 (studio.db_unavailable).

The connection is lost at ONE chosen statement of a signed-in request - an execute wrapper raises the error Django
raises for a connection the database ended (OperationalError) or one already closed (InterfaceError) - so each place a
loss can land is named exactly: in a middleware (the session's load, before any view), in a view before its read is
recorded, and after. (A loss in Django's own write of the session's row, at its save after a view, is Django's own
400, a recorded limit the documents name, I1-20: see its tests.) Each answers 503 with Retry-After, under /api/ the
API's fail-closed JSON, elsewhere the plain error page; no byte of the request is served. Any other error stays Django's
own 500. The real web, its connections ended while requests run and refused for a while, is tests/test_web_process.py's
test_a_database_lost_while_requests_run_or_restarted_answers_503_never_500. Integrated refutation round 2 (I2-4): only a
lost or unusable connection is the 503 - by the driver's SQLSTATE under Django's error, and against PostgreSQL itself
(a real deadlock and a cancelled statement stay Django's 500 with their traceback; a terminated connection is the
503) - a change's 503 says neither that it was kept nor that it was not, and a read's own record lost as it is
written is the 503 with Retry-After. Synthetic data only.
"""
from __future__ import annotations

import ast
import json
import logging
import threading
import time
from pathlib import Path
from unittest import mock

import psycopg
import psycopg.errors

from django.conf import settings
from django.core.signals import got_request_exception
from django.db import IntegrityError, InterfaceError, OperationalError, connection
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import get_resolver

from studio import db_unavailable, decisions, jobs, models, read_audit, session_store, state
from tests.support import coding as f
from tests.support import rounds as r
from tests.test_frontend import PLAIN_STATIC

PASSWORD = 'synthetic-pass-123!'  # tests.support.coding.user's
UNAVAILABLE_JSON = {'error': read_audit.NOT_RECORDED, 'details': {}}
LOST = 'terminating connection due to administrator command'  # the text the database's own error carries


def reported(sqlstate_error, text=LOST):
    """Django's OperationalError for ``sqlstate_error`` (a psycopg error class, or None for the driver's own error with
    no SQLSTATE) as Django raises it: the driver's error as its __cause__ (django.db.utils.DatabaseErrorWrapper)."""
    error = OperationalError(text)
    error.__cause__ = (psycopg.OperationalError if sqlstate_error is None else sqlstate_error)(text)
    return error


@override_settings(STORAGES=PLAIN_STATIC)
class TheDatabaseLostAtOneStatementTests(TestCase):
    def setUp(self):
        ws = f.workspace('Synthetic database-loss practice')
        self.user = f.member(ws, role=models.Membership.OWNER)
        self.enc = f.encounter(ws, self.user, title='Synthetic database-loss note')
        f.upload(self.enc, self.user)  # a stored PDF original: its view would serve f.PDF_BYTES
        r.write_round(self.enc)
        # the handler500 door is reached through Django's own exception handling, which a test client otherwise
        # raises again in the test
        self.client = Client(raise_request_exception=False)
        signed = self.client.post('/login/', {'username': self.user.get_username(), 'password': PASSWORD})
        self.assertEqual(signed.status_code, 302)
        self.detail = f'/api/encounters/{self.enc.pk}'

    def lost_at(self, needle, path, *, method='get', error=OperationalError, **extra):
        """The answer to ``path`` when the first statement holding ``needle`` raises ``error``, the served rows the
        request wrote, and whether the statement was reached at all."""
        hit = []

        def wrapper(execute, sql, params, many, context):
            if needle in sql and not hit:
                hit.append(sql[:80])
                raise error(LOST) if isinstance(error, type) else error
            return execute(sql, params, many, context)
        before = models.AccessRecord.objects.filter(outcome=read_audit.SERVED).count()
        with connection.execute_wrapper(wrapper):
            response = getattr(self.client, method)(path, **extra)
        served = models.AccessRecord.objects.filter(outcome=read_audit.SERVED).count() - before
        self.assertTrue(hit, f'{needle} was never reached by {path}')
        return response, served

    def assertUnavailable(self, response, *, api, what, sentence=read_audit.NOT_RECORDED):
        self.assertEqual(response.status_code, 503, what)
        self.assertEqual(response['Retry-After'], str(db_unavailable.DATABASE_RETRY_AFTER_SECONDS), what)
        self.assertEqual(response['Cache-Control'], 'no-store', what)
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'], what)
        self.assertNotIn(LOST.encode(), response.content, what)
        self.assertNotIn(b'Traceback', response.content, what)
        self.assertNotIn(b'%PDF', response.content, what)
        if api:
            self.assertEqual(response['Content-Type'], 'application/json', what)
            self.assertEqual(json.loads(response.content), {'error': sentence, 'details': {}}, what)
        else:
            self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8', what)
            self.assertEqual(response.content.decode(), db_unavailable.DATABASE_UNAVAILABLE_PAGE, what)
            self.assertIn('<title>Service Unavailable (503)</title>', response.content.decode(), what)

    def test_a_connection_lost_in_a_middleware_before_the_view_answers_503(self):
        # the session's load (studio.sessions.SessionPolicyMiddleware, before any view): no middleware hook sees it, so
        # it is the urlconf's handler500 that answers - the API's JSON, a page's plain page; nothing read or recorded
        for path, api in (('/api/encounters', True), (self.detail, True), (f'{self.detail}/original?view=1', True),
                          ('/api/session', True), ('/', False), ('/account/', False)):
            for error in (OperationalError, InterfaceError):
                with self.subTest(path=path, error=error.__name__):
                    response, served = self.lost_at('"django_session"', path, error=error)
                    self.assertUnavailable(response, api=api, what=f'{path} {error.__name__}')
                    self.assertEqual(served, 0)

    def test_a_connection_lost_in_a_view_before_its_read_is_recorded_answers_503_with_nothing_read(self):
        for needle, path in (('"studio_membership"', '/api/encounters'), ('"studio_encounter"', self.detail),
                             ('"studio_encounter"', f'{self.detail}/original?view=1'),
                             ('"studio_encounter"', f'{self.detail}/original')):
            with self.subTest(needle=needle, path=path):
                response, served = self.lost_at(needle, path)
                self.assertUnavailable(response, api=True, what=f'{path} at {needle}')
                self.assertEqual(served, 0)

    def test_a_connection_lost_after_a_read_is_recorded_answers_503_and_serves_nothing(self):
        # the detail's record is written before its payload is built: lost at the payload's queries, the answer is the
        # 503 all the same - its record then says more than was shown, never less
        for needle in ('"studio_sourcefile"', '"studio_exportartifact"', '"studio_codinground"'):
            with self.subTest(needle=needle):
                response, served = self.lost_at(needle, self.detail)
                self.assertUnavailable(response, api=True, what=needle)
                self.assertEqual(served, 1)

    def test_a_connection_lost_in_a_change_answers_503(self):
        # a change's sentence says neither that it was kept nor that it was not (integrated refutation round 2, I2-4:
        # the loss can come after the database committed it), in words the page already says (its 409's)
        response, _ = self.lost_at('"studio_encounter"', f'{self.detail}/stop', method='post',
                                   content_type='application/json', data='{}')
        self.assertUnavailable(response, api=True, what='a change', sentence=db_unavailable.CHANGE_UNKNOWN)
        self.assertNotIn(b'nothing was shown', response.content)
        page = (Path(settings.BASE_DIR) / 'studio' / 'static' / 'studio' / 'app.js').read_text(encoding='utf-8')
        self.assertIn(f"if (status === 409) return '{db_unavailable.CHANGE_UNKNOWN}';", page)

    def test_a_search_lost_keeps_the_reads_sentence(self):
        # the search is a read, a POST only so its words stay out of addresses (R2-20): nothing of it was shown
        response, served = self.lost_at('"studio_membership"', '/api/encounters/search', method='post',
                                        content_type='application/json', data='{"text": "synthetic", "before": null}')
        self.assertUnavailable(response, api=True, what='the search')
        self.assertEqual(served, 0)

    def test_a_connection_lost_in_a_reads_own_record_answers_503_with_retry_after(self):
        # integrated refutation round 2, I2-4 (I1-20's measurement): a loss inside the read's own record - its INSERT -
        # was the record's own 503 with no Retry-After; it is a database that cannot be reached like any other
        for path, method, extra in (('/api/encounters', 'get', {}), (self.detail, 'get', {}),
                                    (f'{self.detail}/original?view=1', 'get', {}), (f'{self.detail}/original', 'get', {}),
                                    (f'{self.detail}/bundle', 'get', {}),
                                    ('/api/encounters/search', 'post', {'content_type': 'application/json',
                                                                        'data': '{"text": "synthetic", "before": null}'})):
            with self.subTest(path=path):
                response, served = self.lost_at('INSERT INTO "studio_accessrecord"', path, method=method, **extra)
                self.assertUnavailable(response, api=True, what=path)
                self.assertEqual(served, 0)
        # a record refused for any other reason keeps its own 503, without Retry-After, as before
        with mock.patch.object(models.AccessRecord.objects, 'create', side_effect=IntegrityError(LOST)):
            response = self.client.get(self.detail)
        self.assertEqual((response.status_code, response.has_header('Retry-After'), response.json()),
                         (503, False, UNAVAILABLE_JSON))

    def test_a_connection_lost_at_the_sessions_save_stays_djangos_own_400(self):
        # a recorded limit: Django's database SessionStore.save turns any database error of an update into UpdateError,
        # which SessionMiddleware answers 400 (SessionInterrupted, as for a session deleted while the request ran)
        # before either door sees an OperationalError - left as Django answers it, since catching it would catch more
        # than a lost database. The write comes at most once a SESSION_ACTIVITY_WRITE_SECONDS: here at every request.
        # An API read's answer is not sent either, and its record, written before it, says it was served (I1-20: the
        # batch B check's probe, a signed-in GET of a document)
        with override_settings(SESSION_ACTIVITY_WRITE_SECONDS=0):
            for path, method, recorded in (('/session/activity', 'post', 0), (self.detail, 'get', 1)):
                with self.subTest(path=path):
                    response, served = self.lost_at('UPDATE "django_session"', path, method=method)
                    self.assertEqual((response.status_code, response.has_header('Retry-After'),
                                      response['Content-Type']), (400, False, 'text/html; charset=utf-8'))
                    self.assertNotIn(LOST.encode(), response.content)
                    self.assertNotIn(b'Synthetic database-loss note', response.content)
                    self.assertEqual(served, recorded)

    def test_a_connection_lost_in_the_session_stores_own_links_at_the_save_answers_503(self):
        # the store keeps the session's links around Django's write of its row, in the save's own transaction
        # (studio.session_store.sync_links): a loss there leaves SessionMiddleware as an OperationalError, which the
        # urlconf's handler500 answers 503 - the read's record already written, nothing of its answer sent (I1-20)
        with override_settings(SESSION_ACTIVITY_WRITE_SECONDS=0), \
                mock.patch.object(session_store, 'sync_links', side_effect=OperationalError(LOST)) as links, \
                self.assertLogs('django.request', 'ERROR'):
            before = models.AccessRecord.objects.filter(outcome=read_audit.SERVED).count()
            response = self.client.get(self.detail)
            self.assertUnavailable(response, api=True, what="the store's links at the session's save")
        self.assertEqual(links.call_count, 1)
        self.assertNotIn(b'Synthetic database-loss note', response.content)
        self.assertEqual(models.AccessRecord.objects.filter(outcome=read_audit.SERVED).count() - before, 1)

    def test_a_loss_in_a_view_is_answered_by_the_middleware_before_djangos_own_handling(self):
        # the middleware answers what a view raises: Django's handling of an uncaught exception never runs for it (no
        # got_request_exception), so the request logs one fixed line - 'Service Unavailable: <path>', which the
        # installer's kept web log keeps - and no traceback. A loss in a middleware reaches the handler through
        # Django's own handling, which logs its traceback, as for any server error before (a recorded limit)
        from django.core.signals import got_request_exception
        for needle, path, door in (('"studio_membership"', '/api/encounters', 'middleware'),
                                   ('"django_session"', '/api/encounters', 'handler')):
            with self.subTest(door=door):
                signalled = []

                def heard(sender, **kwargs):
                    signalled.append(kwargs.get('request').path)
                got_request_exception.connect(heard)
                try:
                    with self.assertLogs('django.request', 'WARNING') as logged:
                        response, _ = self.lost_at(needle, path)
                finally:
                    got_request_exception.disconnect(heard)
                self.assertUnavailable(response, api=True, what=door)
                self.assertEqual([record.getMessage() for record in logged.records], [f'Service Unavailable: {path}'])
                self.assertEqual((signalled, logged.records[0].exc_info is None),
                                 ([], True) if door == 'middleware' else ([path], False), door)

    def test_any_other_error_stays_djangos_own_500(self):
        for error, needle in ((IntegrityError(LOST), '"studio_membership"'), (RuntimeError(LOST), '"studio_encounter"'),
                              (IntegrityError(LOST), '"django_session"')):
            with self.subTest(error=type(error).__name__, needle=needle):
                response, _ = self.lost_at(needle, '/api/encounters' if 'membership' in needle else self.detail,
                                           error=error)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn('Retry-After', response)
                self.assertIn(b'Server Error (500)', response.content)
                self.assertNotIn(LOST.encode(), response.content)

    def test_an_error_the_database_reports_that_is_no_loss_stays_djangos_500_with_its_traceback(self):
        # integrated refutation round 2, I2-4 (failclosed-2): PostgreSQL reports a deadlock, a cancelled statement, a lock
        # not granted, a full disk as OperationalError too - each the request's own error, answered as before: Django's
        # 500, got_request_exception sent and the traceback logged (the operator's evidence), never the 503
        for cause in (psycopg.errors.DeadlockDetected, psycopg.errors.QueryCanceled, psycopg.errors.LockNotAvailable,
                      psycopg.errors.SerializationFailure, psycopg.errors.DiskFull):
            for needle, path, method, extra in (('"studio_membership"', '/api/encounters', 'get', {}),
                                                ('"studio_encounter"', f'{self.detail}/stop', 'post',
                                                 {'content_type': 'application/json', 'data': '{}'})):
                with self.subTest(cause=cause.__name__, path=path):
                    signalled = []

                    def heard(sender, **kwargs):
                        signalled.append(kwargs.get('request').path)
                    got_request_exception.connect(heard)
                    try:
                        with self.assertLogs('django.request', 'ERROR') as logged:
                            response, _ = self.lost_at(needle, path, method=method, error=reported(cause), **extra)
                    finally:
                        got_request_exception.disconnect(heard)
                    self.assertEqual(response.status_code, 500)
                    self.assertNotIn('Retry-After', response)
                    self.assertIn(b'Server Error (500)', response.content)
                    self.assertNotIn(LOST.encode(), response.content)
                    self.assertEqual(signalled, [path])
                    self.assertEqual([(record.getMessage(), record.exc_info is not None) for record in logged.records],
                                     [(f'Internal Server Error: {path}', True)])

    def test_the_admin_host_answers_the_same(self):
        # a request of the admin host whose session's load is lost (the cookie of this browser's session): the same 503
        response, _ = self.lost_at('"django_session"', '/account/', HTTP_HOST='admin.quillmd.com')
        self.assertUnavailable(response, api=False, what='the admin host')


class TheSessionSaveLimitDocumentTests(SimpleTestCase):
    """I1-20 (integrated refutation round 1, batch B's check): the documents name the recorded limit the tests above
    measure - a loss in Django's own write of the session's row is Django's 400, not the 503 - and the module's account
    of its two doors no longer counts that save among the losses they answer."""

    def test_the_documents_say_a_loss_in_the_sessions_own_write_is_djangos_400(self):
        root = Path(settings.BASE_DIR)
        api = (root / 'API.md').read_text(encoding='utf-8')
        start = api.index('- **A database that cannot be reached**')
        bullet = ' '.join(api[start:api.index('\n- **', start)].split())
        for words in ("a connection lost at the session's own save after the view, in Django's write of the session's "
                      "row, is Django's own `400` (`SessionInterrupted`: an HTML page, no `Retry-After`), "
                      "not this `503`", 'written at most once a minute (`SESSION_ACTIVITY_WRITE_SECONDS`)'):
            self.assertIn(words, bullet)
        self.assertEqual(settings.SESSION_ACTIVITY_WRITE_SECONDS, 60)  # "at most once a minute"
        source = (root / 'cptstudio' / 'settings.py').read_text(encoding='utf-8')
        start = source.index("# The web keeps each process's one connection")
        comment = ' '.join(source[start:source.index("'CONN_MAX_AGE'", start)].replace('#', ' ').split())
        self.assertIn("answers 503 (studio.db_unavailable) - except a loss in Django's own write of the session's row "
                      "after the view, which is Django's 400 (SessionInterrupted)", comment)
        module = ' '.join(ast.get_docstring(ast.parse((root / 'studio' / 'db_unavailable.py').read_text(
            encoding='utf-8'))).split())
        self.assertNotIn('its save in SessionMiddleware', module)
        self.assertIn("a loss in Django's own write of the session's row at that save reaches neither", module)
        self.assertIn("SessionMiddleware raises as SessionInterrupted: Django's own 400", module)


class TheTwoDoorsTests(SimpleTestCase):
    """Both urlconfs name the handler; the middleware answers the two errors alone, last in the chain."""

    def test_both_urlconfs_answer_a_lost_database_through_the_handler(self):
        for urlconf in ('cptstudio.urls', 'cptstudio.urls_admin'):
            with self.subTest(urlconf):
                self.assertIs(get_resolver(urlconf).resolve_error_handler(500), db_unavailable.server_error)

    def test_the_middleware_answers_only_a_database_that_cannot_be_reached(self):
        from django.conf import settings
        self.assertEqual(settings.MIDDLEWARE[-1], 'studio.db_unavailable.DatabaseUnavailableMiddleware')
        middleware = db_unavailable.DatabaseUnavailableMiddleware(lambda request: None)
        request = RequestFactory().get('/api/encounters')
        for error in (OperationalError(LOST), InterfaceError(LOST)):
            self.assertEqual(middleware.process_exception(request, error).status_code, 503)
        for error in (IntegrityError(LOST), ValueError(LOST), RecursionError(), KeyError('x')):
            self.assertIsNone(middleware.process_exception(request, error), type(error).__name__)

    # integrated refutation round 2, I2-4 (failclosed-2): only a lost or unusable connection is the 503 - by the driver
    # error under Django's: none at all (an OperationalError raised as such), the driver's own with no SQLSTATE (a
    # refusal at connect, a connection broken under a statement), class 08, or 57P01-57P03; every other error the
    # database reports as an OperationalError is the request's own, Django's 500
    LOSSES = (None, psycopg.errors.AdminShutdown, psycopg.errors.CrashShutdown, psycopg.errors.CannotConnectNow,
              psycopg.errors.ConnectionFailure, psycopg.errors.ConnectionDoesNotExist,
              psycopg.errors.SqlclientUnableToEstablishSqlconnection, psycopg.errors.ProtocolViolation)
    NOT_LOSSES = (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure, psycopg.errors.QueryCanceled,
                  psycopg.errors.LockNotAvailable, psycopg.errors.DiskFull, psycopg.errors.OutOfMemory,
                  psycopg.errors.ProgramLimitExceeded, psycopg.errors.ObjectInUse, psycopg.errors.InFailedSqlTransaction)

    def test_only_a_lost_or_unusable_connection_is_a_database_that_cannot_be_reached(self):
        middleware = db_unavailable.DatabaseUnavailableMiddleware(lambda request: None)
        request = RequestFactory().get('/api/encounters')
        for cause in self.LOSSES:
            with self.subTest(cause=getattr(cause, '__name__', 'none'), sqlstate=getattr(cause, 'sqlstate', None)):
                self.assertTrue(db_unavailable.is_database_unavailable(reported(cause)))
                self.assertEqual(middleware.process_exception(request, reported(cause)).status_code, 503)
                try:
                    raise reported(cause)
                except OperationalError:
                    self.assertEqual(db_unavailable.server_error(request).status_code, 503)
        bare = OperationalError(LOST)  # raised with no driver error under it: lost, as the tests above raise it
        self.assertEqual((bare.__cause__, db_unavailable.is_database_unavailable(bare)), (None, True))
        for cause in self.NOT_LOSSES:
            with self.subTest(cause=cause.__name__, sqlstate=cause.sqlstate):
                self.assertFalse(db_unavailable.is_database_unavailable(reported(cause)))
                self.assertIsNone(middleware.process_exception(request, reported(cause)))
                try:
                    raise reported(cause)
                except OperationalError:
                    answer = db_unavailable.server_error(request)
                self.assertEqual((answer.status_code, answer.has_header('Retry-After')), (500, False))
        self.assertTrue(db_unavailable.is_database_unavailable(InterfaceError(LOST)))
        for error in (IntegrityError(LOST), ValueError(LOST), psycopg.errors.DeadlockDetected(LOST), None):
            self.assertFalse(db_unavailable.is_database_unavailable(error), repr(error))

    def test_the_handler_gives_any_other_error_djangos_own_page(self):
        request = RequestFactory().get('/api/encounters')
        try:
            raise ValueError(LOST)
        except ValueError:
            response = db_unavailable.server_error(request)
        self.assertEqual((response.status_code, response.has_header('Retry-After')), (500, False))
        try:
            raise OperationalError(LOST)
        except OperationalError:
            response = db_unavailable.server_error(request)
        self.assertEqual((response.status_code, response['Retry-After']), (503, '5'))


class TheChangeKeptBeforeTheLossTests(TestCase):
    """Integrated refutation round 2, I2-4 (failclosed-3): a change the database committed before the connection was
    lost - an approval, whose refresh after its transaction (studio.decisions, D358-frozen) is its next statement - is
    answered with the change's sentence, which says neither that it was kept nor that it was not, and Retry-After; the
    approval stands, and the page's reload shows it."""

    def test_an_approval_committed_then_lost_is_answered_with_neither_outcome(self):
        from tests.test_decisions import DecisionCase

        case = type('Decided', (DecisionCase,), {'runTest': lambda self: None})()
        case.setUp()
        inserted, hit = [], []

        def wrapper(execute, sql, params, many, context):
            if sql.startswith('INSERT INTO "studio_codedecision"'):
                inserted.append(sql[:40])
            elif inserted and not hit and 'FROM "studio_codedecision"' in sql:
                hit.append(sql[:80])
                raise reported(None, 'server closed the connection unexpectedly')
            return execute(sql, params, many, context)
        with connection.execute_wrapper(wrapper):
            response = case.decide('45385', 'approve')
        self.assertEqual(len(hit), 1, 'the refresh after the approval was never reached')
        self.assertEqual((response.status_code, response['Retry-After'], response.json()),
                         (503, str(db_unavailable.DATABASE_RETRY_AFTER_SECONDS),
                          {'error': db_unavailable.CHANGE_UNKNOWN, 'details': {}}))
        self.assertNotIn(read_audit.NOT_RECORDED, response.json()['error'])
        _payload, codes = case.codes()
        self.assertEqual(codes['45385']['decision']['action'], 'approve')  # kept: the member's reload shows it
        self.assertEqual(models.CodeDecision.objects.filter(encounter=case.enc, code='45385', action='approve').count(), 1)


def other_session(**kwargs):
    """A second session of this run's own test database, outside Django (plain psycopg)."""
    conf = connection.settings_dict
    return psycopg.connect(dbname=conf['NAME'], user=conf['USER'], password=conf['PASSWORD'], host=conf['HOST'],
                           port=conf['PORT'], **kwargs)


def wait_blocked(watcher, pid, blocker, timeout=15.0):
    """Until the request's backend ``pid`` waits for a lock ``blocker`` holds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = watcher.execute('SELECT %s::int = ANY(pg_blocking_pids(%s::int)) FROM pg_stat_activity WHERE pid = %s::int',
                              (blocker, pid, pid)).fetchone()
        if row and row[0]:
            return
        time.sleep(0.01)
    raise AssertionError(f'backend {pid} never waited for {blocker}')


@override_settings(STORAGES=PLAIN_STATIC)
class TheRealDatabaseTests(TransactionTestCase):
    """Integrated refutation round 2, I2-4 (failclosed-2): PostgreSQL itself, through second sessions. A real deadlock
    in a member's Stop and a statement an operator cancelled are the request's own errors - Django's 500, the traceback
    logged with the database's words - while a connection the operator ended is a database that cannot be reached: the
    503 with Retry-After. The Stop is undone each time."""

    def setUp(self):
        self.ws = f.workspace('Synthetic lock practice')
        self.user = f.member(self.ws)  # a reviewer: may Stop
        self.enc = f.encounter(self.ws, self.user, title='Synthetic lock note')
        f.upload(self.enc, self.user)
        self.enc.refresh_from_db()
        jobs.start_round(self.enc, self.enc.current_revision, models.CodingRound.UPLOAD, self.user)
        self.job = models.Job.objects.get(encounter=self.enc, state=models.Job.QUEUED)

    def deadlock(self, pid, ready, done):
        """Hold the job's row; once the Stop (holding the document's row) waits for it, ask for the document's row. Only
        the request's backend looks for the deadlock in time (this session's deadlock_timeout is long), so the database
        ends the request's statement."""
        with other_session() as holder, other_session(autocommit=True) as watcher:
            holder.execute("SET deadlock_timeout = '20s'")
            holder.execute('SELECT 1 FROM studio_job WHERE id = %s FOR UPDATE', (self.job.pk,))
            ready.set()
            wait_blocked(watcher, pid, holder.info.backend_pid)
            time.sleep(0.2)
            holder.execute('SELECT 1 FROM studio_encounter WHERE id = %s FOR UPDATE', (self.enc.pk,))
            holder.rollback()
        done.set()

    def blocked_then(self, action):
        """Hold the document's row; once the Stop's UPDATE waits for it, an operator's ``action`` on its backend."""
        def partner(pid, ready, done):
            with other_session() as holder, other_session(autocommit=True) as watcher:
                holder.execute('SELECT 1 FROM studio_encounter WHERE id = %s FOR UPDATE', (self.enc.pk,))
                ready.set()
                wait_blocked(watcher, pid, holder.info.backend_pid)
                watcher.execute(f'SELECT {action}(%s::int)', (pid,))
                time.sleep(0.2)
                holder.rollback()
            done.set()
        return partner

    def stop_with(self, partner):
        """The member's Stop while ``partner`` works on its backend: the answer, got_request_exception's paths and the
        django.request records (message, level, whether a traceback came with it, its text)."""
        client = Client(raise_request_exception=False)
        client.force_login(self.user)
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_backend_pid()')
            pid = cursor.fetchone()[0]
        signalled, records = [], []

        def heard(sender, **kwargs):
            signalled.append(kwargs.get('request').path)

        class Kept(logging.Handler):
            def emit(self, record):
                records.append((record.getMessage(), record.levelname, record.exc_info is not None,
                                logging.Formatter().format(record)))
        kept = Kept(logging.DEBUG)
        logger = logging.getLogger('django.request')
        logger.addHandler(kept)
        got_request_exception.connect(heard)
        ready, done = threading.Event(), threading.Event()
        thread = threading.Thread(target=partner, args=(pid, ready, done), daemon=True)
        thread.start()
        try:
            self.assertTrue(ready.wait(15), 'the second session never took its lock')
            response = client.post(f'/api/encounters/{self.enc.pk}/stop', data='{}', content_type='application/json')
            self.assertTrue(done.wait(30), 'the second session never finished')
        finally:
            got_request_exception.disconnect(heard)
            logger.removeHandler(kept)
            thread.join(30)
        self.enc.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual((self.enc.stopped_at, self.job.state), (None, models.Job.QUEUED), 'the Stop was undone')
        return response, signalled, records

    def assertDjangos500(self, response, signalled, records, words):
        path = f'/api/encounters/{self.enc.pk}/stop'
        self.assertEqual((response.status_code, response.has_header('Retry-After')), (500, False))
        self.assertIn(b'Server Error (500)', response.content)
        self.assertNotIn(words.encode(), response.content)
        self.assertEqual(signalled, [path])
        self.assertEqual([(message, level, traceback) for message, level, traceback, _ in records],
                         [(f'Internal Server Error: {path}', 'ERROR', True)])
        self.assertIn(words, records[0][3])  # the operator's evidence: the database's own words, in the traceback

    def test_a_real_deadlock_in_a_stop_is_djangos_500_with_its_traceback(self):
        self.assertDjangos500(*self.stop_with(self.deadlock), 'deadlock detected')

    def test_a_statement_an_operator_cancelled_is_djangos_500_with_its_traceback(self):
        self.assertDjangos500(*self.stop_with(self.blocked_then('pg_cancel_backend')),
                              'canceling statement due to user request')

    def test_a_connection_an_operator_ended_is_the_503(self):
        response, signalled, records = self.stop_with(self.blocked_then('pg_terminate_backend'))
        self.assertEqual((response.status_code, response['Retry-After'], response.json()),
                         (503, str(db_unavailable.DATABASE_RETRY_AFTER_SECONDS),
                          {'error': db_unavailable.CHANGE_UNKNOWN, 'details': {}}))
        self.assertEqual(signalled, [])
        self.assertEqual([(message, traceback) for message, _, traceback, _ in records],
                         [(f'Service Unavailable: /api/encounters/{self.enc.pk}/stop', False)])
