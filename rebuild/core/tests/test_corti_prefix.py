"""Focused HTTPS mount checks, without a database or provider connection."""
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse, HttpResponseRedirect
from django.middleware.csrf import CsrfViewMiddleware, _get_new_csrf_string
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import get_script_prefix, reverse, set_script_prefix

from core.corti_prefix import (CortiPrefixMiddleware, PREFIX, csrf_failure,
                               local_destination, next_destination)
from core.middleware import AccessMiddleware
from core.preview_access import AccountOriginMiddleware


CONFIG = {
    'FORCE_SCRIPT_NAME': PREFIX, 'SYNTHETIC_ONLY': True,
    'ALLOWED_HOSTS': ['app.quillmd.com', 'localhost'],
    'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),
    'QUILLMD_TRUST_PROXY': True, 'ADMIN_SITE': False,
    'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED': True,
    'QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED': True,
    'SESSION_COOKIE_NAME': 'quillmd_corti_session',
    'CSRF_COOKIE_NAME': 'quillmd_corti_csrf',
    'SESSION_COOKIE_PATH': PREFIX + '/', 'CSRF_COOKIE_PATH': PREFIX + '/',
    'SESSION_COOKIE_SECURE': True, 'CSRF_COOKIE_SECURE': True,
    'SESSION_COOKIE_SAMESITE': 'Strict', 'CSRF_COOKIE_SAMESITE': 'Strict',
    'CSRF_FAILURE_VIEW': 'core.corti_prefix.csrf_failure',
    'STORAGES': {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
    'STATIC_URL': PREFIX + '/static/',
}


@override_settings(**CONFIG)
class CortiPrefixTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.original_prefix = get_script_prefix()
        set_script_prefix(PREFIX + '/')
        self.addCleanup(set_script_prefix, self.original_prefix)

    def request(self, path='/', method='get', **extra):
        values = {'HTTP_HOST': 'app.quillmd.com', 'HTTP_X_FORWARDED_PROTO': 'https',
                  'HTTP_X_QUILLMD_ACCOUNT': '1', 'HTTP_X_QUILLMD_CORTI_PREFIX': PREFIX,
                  'SCRIPT_NAME': PREFIX}
        if method == 'post':
            values.update(HTTP_ORIGIN='https://app.quillmd.com',
                          HTTP_REFERER='https://app.quillmd.com' + PREFIX + '/login/')
        values.update(extra)
        request = getattr(self.factory, method)(path, **values)
        request.user = AnonymousUser()
        return request

    def test_native_auth_stays_required_and_login_next_stays_in_candidate(self):
        view = Mock(return_value=HttpResponse('private document'))
        application = CortiPrefixMiddleware(AccountOriginMiddleware(AccessMiddleware(view)))
        request = self.request('/encounters/example/?tab=coding')
        response = application(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response['Location']).path, PREFIX + '/login/')
        self.assertEqual(parse_qs(urlsplit(response['Location']).query)['next'],
                         [PREFIX + '/encounters/example/'])
        view.assert_not_called()
        login = self.request('/login/?next=' + PREFIX + '/encounters/example/')
        self.assertEqual(application(login).status_code, 200)
        self.assertEqual(login.GET['next'], PREFIX + '/encounters/example/')
        view.assert_called_once_with(login)

    def test_authenticated_clinician_routes_reverse_and_hardcoded_redirects_are_confined(self):
        request = self.request('/encounters/example/coding/')
        request.user = SimpleNamespace(is_authenticated=True, verified_at=True, is_staff=False)
        observed = {}

        def view(req):
            observed.update(path=req.path, external=req.corti_external_path,
                            dashboard=reverse('dashboard'), login=reverse('login'))
            return HttpResponseRedirect('/encounters/example/?tab=coding')

        response = CortiPrefixMiddleware(AccountOriginMiddleware(AccessMiddleware(view)))(request)
        self.assertEqual(response['Location'], PREFIX + '/encounters/example/?tab=coding')
        self.assertEqual(observed, {'path': '/encounters/example/coding/',
            'external': PREFIX + '/encounters/example/coding/',
            'dashboard': PREFIX + '/', 'login': PREFIX + '/login/'})
        self.assertEqual(response['Referrer-Policy'], 'same-origin')

    def test_exact_edge_transport_and_scope_are_required(self):
        for changed in ({'HTTP_X_QUILLMD_ACCOUNT': ''},
                        {'HTTP_X_QUILLMD_CORTI_PREFIX': ''},
                        {'HTTP_X_QUILLMD_CORTI_PREFIX': PREFIX + '/'},
                        {'HTTP_X_FORWARDED_PROTO': 'http'}, {'HTTP_HOST': 'localhost'}):
            target = Mock(return_value=HttpResponse())
            with self.subTest(changed=changed):
                self.assertEqual(CortiPrefixMiddleware(target)(self.request(**changed)).status_code, 403)
                target.assert_not_called()
        for path in (PREFIX + '/login/', '//example.invalid/', '/%2e%2e/login/'):
            with self.subTest(path=path):
                target = Mock(return_value=HttpResponse())
                request = self.request()
                # RequestFactory parses a URL's //authority separately; inject
                # the actual WSGI PATH_INFO that this refusal arm inspects.
                request.path_info = path
                self.assertEqual(CortiPrefixMiddleware(target)(request).status_code, 403)
                target.assert_not_called()
        with override_settings(SYNTHETIC_ONLY=False):
            self.assertEqual(CortiPrefixMiddleware(Mock())(self.request()).status_code, 403)

    def test_next_refuses_external_encoded_unscoped_duplicate_and_auth_loops(self):
        for value in ('https://outside.invalid/', '//outside.invalid/', '/encounters/native/',
                      PREFIX + '/login/', PREFIX + '/logout/', PREFIX + '/%2foutside.invalid/',
                      PREFIX + '/%252e%252e/login/', PREFIX + PREFIX + '/login/'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                next_destination(value)
        target = Mock(return_value=HttpResponse())
        response = CortiPrefixMiddleware(target)(
            self.request('/login/?next=' + PREFIX + '/&next=' + PREFIX + '/'))
        self.assertEqual(response.status_code, 403)
        target.assert_not_called()
        for method in ('get', 'post'):
            request = self.request('/login/', method)
            if method == 'post':
                request.POST = self.factory.post('/', {'next': '/encounters/native/'}).POST
            else:
                request.GET = self.factory.get('/?next=/encounters/native/').GET
            self.assertEqual(CortiPrefixMiddleware(target)(request).status_code, 403)
        target.assert_not_called()

    def test_no_cross_dashboard_post_even_with_same_origin(self):
        for referer in ('', 'https://app.quillmd.com/', 'https://app.quillmd.com/encounters/native/',
                        'https://app.quillmd.com' + PREFIX + '-other/',
                        'https://outside.invalid' + PREFIX + '/'):
            with self.subTest(referer=referer):
                target = Mock(return_value=HttpResponse())
                response = CortiPrefixMiddleware(target)(self.request('/login/', 'post', HTTP_REFERER=referer))
                self.assertEqual(response.status_code, 403)
                target.assert_not_called()
        target = Mock(return_value=HttpResponse())
        self.assertEqual(CortiPrefixMiddleware(target)(self.request('/login/', 'post')).status_code, 200)
        target.assert_called_once()

    def test_candidate_cookie_names_are_only_input_and_output_cookie_scope(self):
        observed = {}

        def view(request):
            observed.update(request.COOKIES)
            response = HttpResponse()
            response.set_cookie(settings.SESSION_COOKIE_NAME, 'candidate-session',
                path=settings.SESSION_COOKIE_PATH, secure=True, httponly=True, samesite='Strict')
            return response

        request = self.request('/login/')
        request.COOKIES = {'quillmd_doctor_session': 'native-session',
                          'quillmd_doctor_csrf': 'native-csrf', '__Host-quillmd_preview': 'obsolete',
                          'quillmd_corti_session': 'candidate-session'}
        response = CortiPrefixMiddleware(AccountOriginMiddleware(view))(request)
        self.assertEqual(observed, {'quillmd_corti_session': 'candidate-session'})
        self.assertEqual(set(response.cookies), {'quillmd_corti_session'})
        cookie = response.cookies['quillmd_corti_session']
        self.assertEqual(cookie['path'], PREFIX + '/')
        self.assertTrue(cookie['secure'] and cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Strict')
        wrong = HttpResponse()
        wrong.set_cookie('quillmd_corti_session', 'value', path='/')
        self.assertEqual(CortiPrefixMiddleware(lambda _: wrong)(self.request()).status_code, 403)

    def test_real_csrf_check_rejects_native_cookie_and_accepts_matching_candidate_token(self):
        token = _get_new_csrf_string()
        for candidate_cookie, expected in ((False, 403), (True, 200)):
            request = self.request('/login/', 'post', HTTP_X_CSRFTOKEN=token)
            request.COOKIES = {('quillmd_corti_csrf' if candidate_cookie else 'quillmd_doctor_csrf'): token}

            def validate(req):
                csrf = CsrfViewMiddleware(lambda _: HttpResponse())
                csrf.process_request(req)
                rejected = csrf.process_view(req, lambda _: HttpResponse(), (), {})
                return rejected or HttpResponse()

            response = CortiPrefixMiddleware(validate)(request)
            self.assertEqual(response.status_code, expected)

    def test_outgoing_redirects_never_leave_mount_or_reprefix_existing_urls(self):
        for location in ('/patients/', PREFIX + '/patients/',
                         'https://app.quillmd.com/patients/'):
            response = CortiPrefixMiddleware(lambda _: HttpResponseRedirect(location))(self.request())
            self.assertEqual(response['Location'], PREFIX + '/patients/')
        for location in ('https://outside.invalid/', '//outside.invalid/',
                         '/%2e%2e/', '/login/?next=/login/'):
            response = CortiPrefixMiddleware(lambda _: HttpResponseRedirect(location))(self.request())
            self.assertEqual(response.status_code, 403)
            self.assertNotIn('Location', response)
        with self.assertRaisesRegex(ValueError, 'application failure'):
            CortiPrefixMiddleware(Mock(side_effect=ValueError('application failure')))(self.request())

    def test_static_and_export_paths_preserve_unchanged_response_bytes(self):
        for path in ('/static/app.css', '/encounters/example/status/',
                     '/encounters/example/export/', '/encounters/example/export-with-codes/'):
            request = self.request(path)
            request.user = SimpleNamespace(is_authenticated=True, verified_at=True, is_staff=False)
            response = CortiPrefixMiddleware(AccountOriginMiddleware(AccessMiddleware(
                lambda _: HttpResponse(b'original-response-bytes'))))(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b'original-response-bytes')

    def test_csrf_error_navigation_stays_in_candidate(self):
        request = self.request('/login/', HTTP_ACCEPT='application/json')
        response = csrf_failure(request)
        self.assertEqual(response.status_code, 403)
        self.assertIn((PREFIX + '/login/').encode(), response.content)
        self.assertEqual(local_destination(PREFIX + '/'), PREFIX + '/')

    def test_real_login_page_has_prefixed_links_scoped_csrf_and_protected_download(self):
        middleware = ['core.corti_prefix.CortiPrefixMiddleware', *[
            item for item in settings.MIDDLEWARE if item != 'core.corti_prefix.CortiPrefixMiddleware']]
        edge = {'HTTP_HOST': 'app.quillmd.com', 'HTTP_X_FORWARDED_PROTO': 'https',
                'HTTP_X_QUILLMD_ACCOUNT': '1', 'HTTP_X_QUILLMD_CORTI_PREFIX': PREFIX,
                'SCRIPT_NAME': PREFIX}
        with override_settings(MIDDLEWARE=middleware):
            client = Client(enforce_csrf_checks=True)
            login = client.get('/login/', **edge)
            self.assertEqual(login.status_code, 200)
            self.assertContains(login, 'href="' + PREFIX + '/login/"')
            self.assertContains(login, 'href="' + PREFIX + '/recovery/"')
            self.assertContains(login, 'href="' + PREFIX + '/static/app.css"')
            self.assertNotContains(login, 'href="/login/"')
            self.assertEqual(set(login.cookies), {'quillmd_corti_csrf'})
            self.assertEqual(login.cookies['quillmd_corti_csrf']['path'], PREFIX + '/')
            self.assertTrue(login.cookies['quillmd_corti_csrf']['secure'])
            export = client.get('/encounters/a724dfab-59fe-45ac-87de-88cbc9d92d17/export-with-codes/', **edge)
            self.assertEqual(export.status_code, 302)
            self.assertTrue(export['Location'].startswith(PREFIX + '/login/?next='))
            self.assertEqual(client.post('/login/', {}, **edge,
                HTTP_REFERER='https://app.quillmd.com' + PREFIX + '/login/').status_code, 403)
