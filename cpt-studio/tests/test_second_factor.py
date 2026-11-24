"""studio.second_factor, the console's gate (release 1, B2; RELEASE-1-SPEC 3.3): satisfied() and the step-up decorator,
built in Lane 1 and applied to no view yet. Lane 2 adds the WebAuthn ceremony and owns this file from then on: its
ceremony tests (a software authenticator on cryptography) join these. Synthetic data only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
from importlib import import_module
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import Http404, HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from studio import request_meta, second_factor
from tests.support import coding as f

ADMIN = 'admin.quillmd.com'
MOMENT = datetime(2026, 11, 24, 12, 0, tzinfo=dt_timezone.utc)
NOW = request_meta.epoch_seconds(MOMENT)


def at(moment):
    return mock.patch.object(timezone, 'now', return_value=moment)


class GateCase(TestCase):
    def setUp(self):
        self.user = f.user('synthetic-operator')

    def request(self, *, door=request_meta.ADMIN, second_factor_at=NOW, method='get', path='/ops/people', user=None,
                **extra):
        request = getattr(RequestFactory(), method)(path, HTTP_HOST=ADMIN, **extra)
        request.session = import_module(settings.SESSION_ENGINE).SessionStore()
        if door is not None:
            request.session[request_meta.SESSION_DOOR] = door
        if second_factor_at is not None:
            request.session[request_meta.SESSION_SECOND_FACTOR_AT] = second_factor_at
        request.user = user or self.user
        return request


class SatisfiedTests(GateCase):
    def test_a_second_factor_at_the_admin_door_satisfies(self):
        with at(MOMENT):
            self.assertTrue(second_factor.satisfied(self.request()))
            self.assertTrue(second_factor.satisfied(self.request(second_factor_at=NOW - 7 * 3600)))  # B5 bounds age

    def test_nothing_less_satisfies(self):
        cases = {
            'the cpt door': dict(door=request_meta.CPT),
            'a session from before release 1 (no door)': dict(door=None),
            'a password alone (no second factor)': dict(second_factor_at=None),
            'a marker that is text': dict(second_factor_at=str(NOW)),
            'a marker that is a flag': dict(second_factor_at=True),
            'a marker of nothing': dict(second_factor_at=0),
            'a negative marker': dict(second_factor_at=-5),
            'a marker that is not finite': dict(second_factor_at=float('inf')),
            'a marker in the future': dict(second_factor_at=NOW + 1),
            'a door that is no door': dict(door='Admin'),
        }
        with at(MOMENT):
            for label, arguments in cases.items():
                with self.subTest(label):
                    self.assertFalse(second_factor.satisfied(self.request(**arguments)))
            self.assertFalse(second_factor.satisfied(self.request(user=AnonymousUser())))
            no_session = RequestFactory().get('/ops/', HTTP_HOST=ADMIN)
            no_session.user = self.user
            self.assertFalse(second_factor.satisfied(no_session))


class StepUpTests(GateCase):
    def decorated(self, **options):
        calls = []

        @second_factor.requires_recent_second_factor(**options)
        def act(request, *args, **kwargs):
            calls.append((args, kwargs))
            return HttpResponse('done')
        return act, calls

    def test_a_recent_second_factor_does_the_act(self):
        act, calls = self.decorated()
        with at(MOMENT + timedelta(seconds=settings.SECOND_FACTOR_STEP_UP_SECONDS)):  # exactly the limit: still recent
            answer = act(self.request(method='post', path='/ops/people/x/role'), 'x', back='people')
        self.assertEqual((answer.status_code, answer.content, calls), (200, b'done', [(('x',), {'back': 'people'})]))

    def test_an_older_one_goes_to_the_step_up_and_back_to_the_form_page(self):
        act, calls = self.decorated()
        later = at(MOMENT + timedelta(seconds=settings.SECOND_FACTOR_STEP_UP_SECONDS + 1))
        with later:
            posted = act(self.request(method='post', path='/ops/people/x/role',
                                      HTTP_REFERER='http://admin.quillmd.com/ops/workspaces/00000000-0000-4000-8000-'
                                                   '000000000003?done=role'))
            read = act(self.request(path='/ops/activity?kind=people'))
        self.assertEqual(calls, [])  # the act was not done, and its form is never replayed
        self.assertEqual((posted.status_code, posted['Location']),
                         (303, '/login/second-factor?next=%2Fops%2Fworkspaces%2F00000000-0000-4000-8000-'
                               '000000000003%3Fdone%3Drole'))
        self.assertEqual((read.status_code, read['Location']),
                         (302, '/login/second-factor?next=%2Fops%2Factivity%3Fkind%3Dpeople'))

    def test_next_is_only_ever_a_console_page_of_this_host(self):
        act, _ = self.decorated()
        with at(MOMENT + timedelta(hours=1)):
            for referer in ('', 'http://evil.example/ops/people', 'http://admin.quillmd.com/login/',
                            'http://admin.quillmd.com/ops/../login/', 'http://[::1', 'http://admin.quillmd.com/api/session'):
                with self.subTest(referer=referer):
                    answer = act(self.request(method='post', path='/ops/people/x/role', HTTP_REFERER=referer))
                    self.assertEqual(answer['Location'], '/login/second-factor?next=%2Fops%2F')

    def test_a_session_that_is_not_satisfied_meets_the_gate_s_404(self):
        act, calls = self.decorated()
        with at(MOMENT):
            for request in (self.request(door=request_meta.CPT), self.request(second_factor_at=None),
                            self.request(user=AnonymousUser())):
                with self.assertRaises(Http404):
                    act(request)
        self.assertEqual(calls, [])

    def test_the_limit_is_the_setting_at_each_request_unless_given(self):
        act, _ = self.decorated()
        tight, _ = self.decorated(max_age=60)
        with at(MOMENT + timedelta(seconds=120)):
            self.assertEqual(act(self.request()).status_code, 200)
            self.assertEqual(tight(self.request()).status_code, 302)
            with override_settings(SECOND_FACTOR_STEP_UP_SECONDS=100):
                self.assertEqual(act(self.request()).status_code, 302)

        @second_factor.requires_recent_second_factor
        def bare(request):
            return HttpResponse('done')
        with at(MOMENT):
            self.assertEqual(bare(self.request()).status_code, 200)


class ContractTests(SimpleTestCase):
    def test_max_age_is_whole_seconds(self):
        for value in (-1, 1.5, True, '300'):
            with self.subTest(max_age=value), self.assertRaises(ValueError):
                second_factor.requires_recent_second_factor(max_age=value)(lambda request: None)
