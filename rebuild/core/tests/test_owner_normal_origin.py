"""Transport, CSRF and account protections; no database or shared gate."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, _get_new_csrf_string
from django.test import RequestFactory, SimpleTestCase, override_settings

from core import preview_access as preview
from core.middleware import AccessMiddleware
from core import security, views

CONFIG = {
    'ADMIN_SITE': False, 'QUILLMD_TRUST_PROXY': True,
    'QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED': True,
    'QUILLMD_PREVIEW_AUTH_ENABLED': False, 'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED': True,
    'QUILLMD_PREVIEW_ORIGIN': 'https://obsolete.invalid:9443',
    'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com',
    'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME': '', 'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD': '',
    'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'), 'CSRF_TRUSTED_ORIGINS': [],
    'STORAGES': {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
}


@override_settings(**CONFIG)
class OwnerNormalOriginTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.app = MagicMock(return_value=HttpResponse('fictional app'))

    def request(self, path='/', **extra):
        request = self.factory.get(path, secure=True, HTTP_HOST='app.quillmd.com',
                                   HTTP_X_QUILLMD_ACCOUNT='1')
        request.META.update(extra)
        return request

    def respond(self, request):
        return preview.AccountOriginMiddleware(self.app)(request)

    def test_transport_works_without_any_obsolete_shared_configuration(self):
        for path in ('/', '/login/', '/health/', '/api/patients/', '/console/services/',
                     '/templates/example/original/', '/static/app.css'):
            request = self.request(path)
            self.assertEqual(self.respond(request).status_code, 200)
            self.app.assert_called_once_with(request)
            self.app.reset_mock()

    def test_old_cookies_are_ignored_without_any_session_read_or_write(self):
        for cookie in (None, '', 'malformed', 'a' * 32, 'A' * 32, 'a' * 33):
            request = self.request('/login/')
            request.COOKIES = {} if cookie is None else {preview.COOKIE: cookie}
            with self.subTest(cookie=cookie), patch('django.contrib.sessions.backends.db.SessionStore') as store:
                response = self.respond(request)
                self.assertEqual(response.status_code, 200)
                store.assert_not_called()
                if cookie is not None:
                    self.assertEqual(response.cookies[preview.COOKIE]['max-age'], 0)

    def test_exact_host_tls_new_marker_and_trusted_proxy_are_required(self):
        for changes in ({'HTTP_X_QUILLMD_ACCOUNT': ''}, {'HTTP_X_QUILLMD_ACCOUNT': '1, 1'},
                        {'HTTP_X_QUILLMD_ACCOUNT': 'true'}, {'wsgi.url_scheme': 'http'},
                        {'HTTP_HOST': 'admin.quillmd.com'}, {'HTTP_HOST': 'admin.quillmd.com:443'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.respond(self.request(**changes)).status_code, 403)
                self.app.assert_not_called()
        for config in ({'QUILLMD_TRUST_PROXY': False}, {'ADMIN_SITE': True},
                       {'QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED': False},
                       {'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED': False}):
            with override_settings(**config):
                self.assertEqual(self.respond(self.request()).status_code, 403)
                self.app.assert_not_called()
        for source in ('OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED', 'DIRECT_ACCOUNT_ORIGIN_PROTOCOL_QUALIFIED'):
            with patch.object(preview, source, False):
                self.assertEqual(self.respond(self.request()).status_code, 403)
                self.app.assert_not_called()
        request = self.request()
        del request.META['HTTP_X_QUILLMD_ACCOUNT']
        request.META['HTTP_X_QUILLMD_PREVIEW'] = '1'
        self.assertEqual(self.respond(request).status_code, 403)
        self.app.assert_not_called()

    def test_unmarked_public_host_variants_cannot_enter_loopback_development_path(self):
        # Concrete refutation: ALLOWED_HOSTS accepts a known hostname at any
        # port, so the transport must reject rather than treating it as local.
        for host in ('app.quillmd.com:9444', 'admin.quillmd.com:9444',
                     'APP.QUILLMD.COM', 'APP.QUILLMD.COM:443', 'localhost:0', 'localhost:70000'):
            request = self.request(HTTP_HOST=host)
            request.META.pop('HTTP_X_QUILLMD_ACCOUNT')
            with self.subTest(host=host):
                self.assertEqual(self.respond(request).status_code, 403)
                self.app.assert_not_called()
        for host in ('localhost:19430', '127.0.0.1:9170'):
            request = self.request(HTTP_HOST=host)
            request.META.pop('HTTP_X_QUILLMD_ACCOUNT')
            self.assertEqual(self.respond(request).status_code, 200)
            self.app.reset_mock()

    def test_legacy_port_redirects_only_to_normal_account_login_without_capability(self):
        for host in ('app.quillmd.com:9443', 'app.quillmd.com:443'):
            for method in ('GET', 'HEAD', 'POST'):
                request = self.request('/preview/sign-in/?flow=' + 'f' * 32, HTTP_HOST=host)
                request.method = method
                response = self.respond(request)
                self.assertEqual(response.status_code, 303)
                self.assertEqual(response['Location'], 'https://app.quillmd.com/login/')
                self.app.assert_not_called()

    def test_unmarked_loopback_stays_usable_but_marker_cannot_extend_trust_to_other_host(self):
        for host in ('127.0.0.1:9130', 'localhost:9130', 'testserver'):
            request = self.request(HTTP_HOST=host)
            request.META.pop('HTTP_X_QUILLMD_ACCOUNT')
            self.assertEqual(self.respond(request).status_code, 200)
            self.app.reset_mock()
        self.assertEqual(self.respond(self.request(HTTP_HOST='localhost:9130')).status_code, 403)
        self.app.assert_not_called()
        with self.assertRaises(DisallowedHost):
            self.respond(self.request(HTTP_HOST='outside.invalid'))
        self.app.assert_not_called()

    def test_transport_does_not_bypass_account_verification_staff_or_mfa(self):
        cases = [
            (SimpleNamespace(is_authenticated=False), '/', 302, '/login/'),
            (SimpleNamespace(is_authenticated=True, verified_at=None), '/', 403, None),
            (SimpleNamespace(is_authenticated=True, verified_at=True, is_staff=False), '/console/', 404, None),
            (SimpleNamespace(is_authenticated=True, verified_at=True, is_staff=True, is_verified=lambda:False), '/', 302, '/mfa/'),
            (SimpleNamespace(is_authenticated=True, verified_at=True, is_staff=True, is_verified=lambda:True), '/console/', 200, None),
        ]
        for user, path, status, destination in cases:
            request = self.request(path); request.user = user; request.resolver_match = None
            with self.subTest(path=path, status=status):
                response = preview.AccountOriginMiddleware(AccessMiddleware(lambda _:HttpResponse('protected')))(request)
                self.assertEqual(response.status_code, status)
                if destination:
                    self.assertIn(destination, response['Location'])

    def test_real_csrf_accepts_only_normal_https_origin(self):
        token = _get_new_csrf_string()
        middleware = CsrfViewMiddleware(lambda _:HttpResponse('allowed'))
        for origin, expected in [('https://app.quillmd.com', None),
                                 ('https://app.quillmd.com:9443', 403), ('https://outside.invalid', 403)]:
            request = self.factory.post('/login/', {'csrfmiddlewaretoken': token}, secure=True,
                HTTP_HOST='app.quillmd.com', HTTP_ORIGIN=origin)
            request.COOKIES[settings.CSRF_COOKIE_NAME] = token
            middleware.process_request(request)
            with patch.object(middleware, '_reject', side_effect=lambda req, reason:HttpResponse(status=403)):
                result = middleware.process_view(request, lambda _:HttpResponse(), (), {})
            self.assertEqual(None if result is None else result.status_code, expected)
        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, [])

    def test_patient_api_keeps_actual_active_department_query_boundary(self):
        user = SimpleNamespace(is_authenticated=True, verified_at=True, is_staff=False, is_active=True)
        departments = MagicMock(name='actual_active_department_queryset')
        patients = MagicMock()
        patients.filter.return_value.values.return_value.__getitem__.return_value = [
            {'id': '11111111-1111-4111-8111-111111111111', 'display_name': 'Synthetic',
             'reference': 'synthetic', 'department_id': '22222222-2222-4222-8222-222222222222'}]
        request = self.request('/api/patients/?q=Synthetic'); request.user = user; request.resolver_match = None
        with patch.object(security.Department, 'objects') as department_manager, \
             patch.object(views.Patient, 'objects') as patient_manager:
            department_manager.filter.return_value = departments
            patient_manager.filter.return_value = patients
            response = preview.AccountOriginMiddleware(AccessMiddleware(views.api_patients))(request)
        self.assertEqual(response.status_code, 200)
        department_manager.filter.assert_called_once_with(membership__user=user, membership__active=True)
        patient_manager.filter.assert_called_once_with(department__in=departments)
        patients.filter.assert_called_once_with(display_name__icontains='Synthetic')
