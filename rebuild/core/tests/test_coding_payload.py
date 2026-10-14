"""Real CSRF/form parsing with synthetic services and no database access.

The test URLs expose the unchanged endpoint bodies without their database
transaction decorators. Tenant lookup and coding mutations are mocked; the
client, CSRF middleware, request parsing and payload validation are real.
"""
import inspect
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import path

from core import coding_views as views


class SyntheticUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user = SimpleNamespace(pk='synthetic-user')
        return self.get_response(request)


urlpatterns = [
    path('context/', inspect.unwrap(views.context), {'pk': 'synthetic'}),
    path('request/', inspect.unwrap(views.request_run), {'pk': 'synthetic'}),
    path('selections/', inspect.unwrap(views.selections), {'pk': 'synthetic', 'run_pk': 'synthetic-run'}),
    path('approval/', inspect.unwrap(views.approval), {'pk': 'synthetic', 'run_pk': 'synthetic-run'}),
]


@override_settings(
    ROOT_URLCONF=__name__,
    MIDDLEWARE=[
        'django.middleware.csrf.CsrfViewMiddleware',
        __name__ + '.SyntheticUserMiddleware',
    ],
    ALLOWED_HOSTS=['testserver'],
    FILE_UPLOAD_HANDLERS=['django.core.files.uploadhandler.MemoryFileUploadHandler'],
    FILE_UPLOAD_MAX_MEMORY_SIZE=1024 * 1024,
)
class CodingPayload(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        token_request = self.factory.get('/')
        self.token = get_token(token_request)
        self.secret = token_request.META['CSRF_COOKIE']
        self.client = Client(enforce_csrf_checks=True)
        self.client.cookies[settings.CSRF_COOKIE_NAME] = self.secret
        self.run = SimpleNamespace(result={'suggestions': [{'id': 'finding'}]})
        self.service = SimpleNamespace(
            CONTEXT_DEFAULTS=views.service.CONTEXT_DEFAULTS,
            displayed_run=Mock(return_value=self.run), verify_display=Mock(),
            ensure_run=Mock(return_value=self.run), update_context=Mock(),
            update_selection=Mock(), approve=Mock(),
        )
        for target, value in [
            ('service', self.service),
            ('encounter_for', Mock(return_value=SimpleNamespace(pk='synthetic'))),
            ('run_for', Mock(return_value=self.run)),
            ('response', lambda request, encounter, error='', status=200: HttpResponse(error, status=status)),
        ]:
            patcher = patch.object(views, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def form(self, **extra):
        return {
            'csrfmiddlewaretoken': self.token, 'display_token': 'synthetic-display',
            'setting': 'outpatient_office', 'time_same_day': 'true',
            'selection_revision': '0', 'select_finding': 'include',
            'input_digest': 'a' * 64, 'selection_digest': 'b' * 64, **extra,
        }

    def mutations(self):
        return [self.service.update_context, self.service.ensure_run,
                self.service.update_selection, self.service.approve]

    def assert_no_mutations(self):
        for method in self.mutations():
            method.assert_not_called()

    def parse_after_csrf(self, data=None, content_type=None):
        options = {'HTTP_X_CSRFTOKEN': self.token}
        if content_type:
            options['content_type'] = content_type
        request = self.factory.post('/context/', self.form() if data is None else data, **options)
        request.COOKIES[settings.CSRF_COOKIE_NAME] = self.secret
        middleware = CsrfViewMiddleware(lambda request: HttpResponse())
        middleware.process_request(request)
        self.assertIsNone(middleware.process_view(request, views.context, (), {}))
        return request

    def test_all_four_multipart_endpoints_pass_enforced_csrf_once(self):
        for url, mutation in zip(['context', 'request', 'selections', 'approval'], self.mutations()):
            with self.subTest(endpoint=url):
                for method in self.mutations():
                    method.reset_mock()
                response = self.client.post('/' + url + '/', self.form())
                self.assertEqual(response.status_code, 200)
                mutation.assert_called_once()
                self.assertEqual(sum(method.call_count for method in self.mutations()), 1)
                self.service.verify_display.assert_called_with(
                    views.encounter_for.return_value,
                    response.wsgi_request.user, 'synthetic-display', self.run)

    def test_multipart_csrf_consumes_stream_without_raw_body_cache(self):
        request = self.parse_after_csrf()
        self.assertTrue(request._read_started)
        self.assertFalse(hasattr(request, '_body'))
        self.assertEqual(views.payload(request), self.form())
        self.assertFalse(hasattr(request, '_body'))

    def test_context_values_and_selection_remain_exact(self):
        self.assertEqual(self.client.post('/context/', self.form()).status_code, 200)
        values = self.service.update_context.call_args.args[2]
        self.assertEqual(values['setting'], 'outpatient_office')
        self.assertIs(values['time_same_day'], True)
        self.assertIs(values['time_qualified_clinician'], False)
        self.assertEqual(self.client.post('/selections/', self.form()).status_code, 200)
        self.assertEqual(self.service.update_selection.call_args.args[2:],
                         ({'selected_ids': ['finding'], 'overrides': {}}, 0))

    def test_invalid_csrf_refuses_all_four_before_mutation(self):
        for url in ['context', 'request', 'selections', 'approval']:
            with self.subTest(endpoint=url):
                response = self.client.post('/' + url + '/', self.form(csrfmiddlewaretoken='invalid'))
                self.assertEqual(response.status_code, 403)
        self.assert_no_mutations()

    def test_urlencoded_form_remains_accepted(self):
        response = self.client.post('/context/', urlencode(self.form()),
                                    content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 200)
        self.service.update_context.assert_called_once()

    def test_json_with_csrf_header_remains_accepted(self):
        data = {'display_token': 'synthetic-display', 'context': {'setting': 'outpatient_office'}}
        response = self.client.post('/context/', data, content_type='application/json',
                                    HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.update_context.call_args.args[2], data['context'])

    def test_duplicate_multipart_field_refuses_all_endpoints(self):
        for url in ['context', 'request', 'selections', 'approval']:
            with self.subTest(endpoint=url):
                response = self.client.post('/' + url + '/', self.form(display_token=['first', 'second']))
                self.assertEqual(response.status_code, 409)
        self.assert_no_mutations()

    def test_multipart_file_refuses_all_endpoints(self):
        for url in ['context', 'request', 'selections', 'approval']:
            with self.subTest(endpoint=url):
                upload = SimpleUploadedFile('synthetic.txt', b'synthetic')
                response = self.client.post('/' + url + '/', self.form(attachment=upload))
                self.assertEqual(response.status_code, 409)
        self.assert_no_mutations()

    def test_wire_size_limit_refuses_multipart_and_json(self):
        response = self.client.post('/context/', self.form(identity_review_reason='x' * 64000))
        self.assertEqual(response.status_code, 409)
        response = self.client.post('/context/', {'value': 'x' * 64000},
                                    content_type='application/json', HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code, 409)
        self.assert_no_mutations()

    def test_missing_content_length_refuses_parsed_multipart(self):
        request = self.parse_after_csrf()
        del request.META['CONTENT_LENGTH']
        with self.assertRaisesMessage(ValidationError, 'Invalid coding form size.'):
            views.payload(request)

    def test_invalid_content_lengths_refuse_parsed_multipart(self):
        for value in ['', '-1', '+1', ' 1', '1.0', '1e3', '１２', '1' * 11, 10, True, None]:
            with self.subTest(value=value):
                request = self.parse_after_csrf()
                request.META['CONTENT_LENGTH'] = value
                with self.assertRaisesMessage(ValidationError, 'Invalid coding form size.'):
                    views.payload(request)

    def test_false_small_content_length_cannot_admit_oversized_parsed_form(self):
        request = self.parse_after_csrf(self.form(identity_review_reason='é' * 32001))
        request.META['CONTENT_LENGTH'] = '1'
        with self.assertRaisesMessage(ValidationError, 'The coding form is too large.'):
            views.payload(request)

    def test_parsed_form_limit_includes_field_names_and_utf8_bytes(self):
        fields = {str(index) + 'é' * 200: '' for index in range(160)}
        request = self.parse_after_csrf({**fields, 'csrfmiddlewaretoken': self.token})
        request.META['CONTENT_LENGTH'] = '1'
        with self.assertRaisesMessage(ValidationError, 'The coding form is too large.'):
            views.payload(request)

    def test_json_actual_body_size_checked_even_if_header_changed(self):
        request = self.parse_after_csrf(json.dumps({'value': 'x' * 64000}), 'application/json')
        request.META['CONTENT_LENGTH'] = '1'
        with self.assertRaisesMessage(ValidationError, 'The coding form is too large.'):
            views.payload(request)

    def test_json_duplicate_and_nonfinite_values_still_refused(self):
        for data in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '[]', 'null', '{']:
            with self.subTest(data=data):
                response = self.client.post('/context/', data, content_type='application/json',
                                            HTTP_X_CSRFTOKEN=self.token)
                self.assertEqual(response.status_code, 409)
        self.assert_no_mutations()

    def test_unsupported_content_type_refuses(self):
        response = self.client.post('/context/', 'setting=outpatient_office',
                                    content_type='text/plain', HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code, 409)
        self.assert_no_mutations()
