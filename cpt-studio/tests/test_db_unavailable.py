"""Integrated refutation round 1, avail-0 (I1-15): a database that cannot be reached answers 503 wherever the request
is, never Django's HTML 500 (studio.db_unavailable).

The connection is lost at ONE chosen statement of a signed-in request - an execute wrapper raises the error Django
raises for a connection the database ended (OperationalError) or one already closed (InterfaceError) - so each place a
loss can land is named exactly: in a middleware (the session's load, before any view), in a view before its read is
recorded, and after. (The session's save after a view is Django's own 400, a recorded limit: see its test.) Each answers 503 with Retry-After, under /api/ the API's fail-closed JSON,
elsewhere the plain error page; no byte of the request is served. Any other error stays Django's own 500. The real web,
its connections ended while requests run and refused for a while, is tests/test_web_process.py's
test_a_database_lost_while_requests_run_or_restarted_answers_503_never_500. Synthetic data only.
"""
from __future__ import annotations

import json

from django.db import IntegrityError, InterfaceError, OperationalError, connection
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import get_resolver

from studio import db_unavailable, models, read_audit
from tests.support import coding as f
from tests.support import rounds as r
from tests.test_frontend import PLAIN_STATIC

PASSWORD = 'synthetic-pass-123!'  # tests.support.coding.user's
UNAVAILABLE_JSON = {'error': read_audit.NOT_RECORDED, 'details': {}}
LOST = 'terminating connection due to administrator command'  # the text the database's own error carries


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

    def assertUnavailable(self, response, *, api, what):
        self.assertEqual(response.status_code, 503, what)
        self.assertEqual(response['Retry-After'], str(db_unavailable.DATABASE_RETRY_AFTER_SECONDS), what)
        self.assertEqual(response['Cache-Control'], 'no-store', what)
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'], what)
        self.assertNotIn(LOST.encode(), response.content, what)
        self.assertNotIn(b'Traceback', response.content, what)
        self.assertNotIn(b'%PDF', response.content, what)
        if api:
            self.assertEqual(response['Content-Type'], 'application/json', what)
            self.assertEqual(json.loads(response.content), UNAVAILABLE_JSON, what)
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
        response, _ = self.lost_at('"studio_encounter"', f'{self.detail}/stop', method='post',
                                   content_type='application/json', data='{}')
        self.assertUnavailable(response, api=True, what='a change')

    def test_a_connection_lost_at_the_sessions_save_stays_djangos_own_400(self):
        # a recorded limit: Django's database SessionStore.save turns any database error of an update into UpdateError,
        # which SessionMiddleware answers 400 (SessionInterrupted, as for a session deleted while the request ran)
        # before either door sees an OperationalError - left as Django answers it, since catching it would catch more
        # than a lost database. The write comes at most once a SESSION_ACTIVITY_WRITE_SECONDS: here at every ping
        with override_settings(SESSION_ACTIVITY_WRITE_SECONDS=0):
            response, _ = self.lost_at('UPDATE "django_session"', '/session/activity', method='post')
        self.assertEqual((response.status_code, response.has_header('Retry-After')), (400, False))
        self.assertNotIn(LOST.encode(), response.content)

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

    def test_the_admin_host_answers_the_same(self):
        # a request of the admin host whose session's load is lost (the cookie of this browser's session): the same 503
        response, _ = self.lost_at('"django_session"', '/account/', HTTP_HOST='admin.quillmd.com')
        self.assertUnavailable(response, api=False, what='the admin host')


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
