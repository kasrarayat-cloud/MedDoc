"""Fictional requests and signed-store representations; no database or login."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, _get_new_csrf_string
from django.test import RequestFactory, SimpleTestCase, override_settings

from core import preview_access as preview
from core.middleware import AccessMiddleware
from core import security, views


CONFIG = {
    'ADMIN_SITE': False, 'QUILLMD_PREVIEW_AUTH_ENABLED': True,
    'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED': True,
    'QUILLMD_PREVIEW_ORIGIN': 'https://app.quillmd.com:9443',
    'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com:9443',
    'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME': 'fictional-owner',
    'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD': 'Fictional-private-grant-only-12345!',
    'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),
    'CSRF_TRUSTED_ORIGINS': [],
}


@override_settings(**CONFIG)
class OwnerNormalOriginTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.now = 2000000000
        self.grant = {'kind': preview.KIND, 'grant': {
            'fingerprint': preview.fingerprint(), 'issued': self.now - 100, 'seen': self.now - 10}}
        self.source = patch.object(preview, 'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED', True)
        self.source.start(); self.addCleanup(self.source.stop)
        self.clock = patch.object(preview.time, 'time', return_value=self.now)
        self.clock.start(); self.addCleanup(self.clock.stop)
        self.loaded = patch.object(preview, 'SessionStore')
        self.store = self.loaded.start(); self.addCleanup(self.loaded.stop)
        self.store.return_value.load.return_value = self.grant
        self.app = MagicMock(return_value=HttpResponse('fictional app'))

    def request(self, path='/', **extra):
        request = self.factory.get(path, secure=True, HTTP_HOST='app.quillmd.com',
                                   HTTP_X_QUILLMD_PREVIEW='1')
        request.META.update(extra)
        request.COOKIES[preview.COOKIE] = 'a' * 32
        return request

    def respond(self, request):
        return preview.PreviewAccessMiddleware(self.app)(request)

    def deny(self, request):
        response = self.respond(request)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Retry-After'], '3600')
        self.assertFalse(response.cookies)
        self.app.assert_not_called()
        self.store.return_value.save.assert_not_called()
        self.store.return_value.create.assert_not_called()
        self.store.return_value.delete.assert_not_called()
        self.store.return_value.cycle_key.assert_not_called()
        return response

    def test_both_source_qualification_and_explicit_setting_are_required(self):
        with patch.object(preview, 'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED', False):
            self.deny(self.request())
        with override_settings(QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED=False):
            self.deny(self.request())
        self.store.assert_not_called()

    def test_host_marker_tls_and_admin_surface_refuse_before_any_store_read(self):
        for changes in ({'HTTP_HOST': 'app.quillmd.com:443'},
                        {'HTTP_X_QUILLMD_PREVIEW': ''}, {'HTTP_X_QUILLMD_PREVIEW': '1, 1'},
                        {'wsgi.url_scheme': 'http'}, {'HTTP_HOST': 'admin.quillmd.com'},
                        {'HTTP_HOST': 'admin.quillmd.com:443'}):
            with self.subTest(changes=changes):
                self.deny(self.request(**changes))
        with override_settings(ADMIN_SITE=True):
            self.deny(self.request())
        with override_settings(QUILLMD_PREVIEW_AUTH_ENABLED=False):
            self.deny(self.request())
        self.store.assert_not_called()

    def test_missing_malformed_and_unknown_cookie_never_create_a_session(self):
        for cookie in (None, '', 'malformed', 'A' * 32, 'a' * 33):
            with self.subTest(cookie=cookie):
                request = self.request()
                request.COOKIES = {} if cookie is None else {preview.COOKIE: cookie}
                self.deny(request)
        self.store.assert_not_called()
        self.store.return_value.load.return_value = {}
        self.deny(self.request())
        self.store.assert_called_once_with(session_key='a' * 32)

    def test_expired_foreign_rotated_and_corrupted_grants_only_read(self):
        variants = [dict(self.grant, kind='account-session'), {},
            {'kind': preview.KIND, 'grant': {'fingerprint': 'wrong', 'issued': self.now, 'seen': self.now}},
            {'kind': preview.KIND, 'grant': {**self.grant['grant'], 'issued': self.now - preview.ABSOLUTE_SECONDS}},
            {'kind': preview.KIND, 'grant': {**self.grant['grant'], 'seen': self.now - preview.IDLE_SECONDS}},
            {'kind': preview.KIND, 'grant': {'fingerprint': preview.fingerprint(), 'issued': 'bad'}}]
        for value in variants:
            with self.subTest(value=value):
                self.store.return_value.load.return_value = value
                self.deny(self.request())

    def test_private_entry_and_signout_are_not_public_grant_issuers(self):
        for path in (preview.SIGN_IN, preview.SIGN_OUT):
            self.deny(self.request(path))
        self.store.assert_not_called()

    def test_valid_static_read_reaches_same_application_without_store_write(self):
        self.assertEqual(self.respond(self.request('/static/app.css')).status_code, 200)
        self.app.assert_called_once()
        self.store.return_value.save.assert_not_called()
        self.assertEqual(settings.QUILLMD_APP_BASE_URL, 'https://app.quillmd.com:9443')
        self.assertEqual(settings.QUILLMD_PREVIEW_ORIGIN, 'https://app.quillmd.com:9443')

    def test_only_four_frozen_renderer_assets_allow_cookie_free_read(self):
        self.assertEqual(len(preview.OPAQUE_WORD_ASSETS), 4)
        for method in ('GET', 'HEAD'):
            for path in preview.OPAQUE_WORD_ASSETS:
                with self.subTest(method=method, path=path):
                    request = self.request(path)
                    request.method = method
                    request.COOKIES = {}
                    self.assertEqual(self.respond(request).status_code, 200)
                    self.app.assert_called_once_with(request)
                    self.app.reset_mock()
        self.store.assert_not_called()

    def test_renderer_allowance_cannot_admit_other_assets_documents_or_writes(self):
        paths = ('/', '/login/', '/console/services/', '/templates/preview-frame/',
                 '/templates/example/original/', '/api/patients/', '/static/app.css',
                 '/static/docx-frame.js', '/static/docx-frame.000000000000.js',
                 '/static/vendor/docx-preview/docx-preview.min.js.map',
                 '/static/docx-frame.fa120285a29f.js/extra')
        for path in paths:
            request = self.request(path); request.COOKIES = {}
            self.deny(request)
        for method in ('POST', 'PUT', 'DELETE', 'OPTIONS'):
            request = self.request(next(iter(preview.OPAQUE_WORD_ASSETS)))
            request.COOKIES = {}; request.method = method
            self.deny(request)
        self.store.assert_not_called()

    def test_renderer_reads_still_require_exact_host_tls_marker_and_enablement(self):
        path = next(iter(preview.OPAQUE_WORD_ASSETS))
        for changes in ({'HTTP_HOST': 'app.quillmd.com:443'},
                        {'HTTP_X_QUILLMD_PREVIEW': ''}, {'wsgi.url_scheme': 'http'},
                        {'HTTP_HOST': 'admin.quillmd.com'}):
            request = self.request(path, **changes); request.COOKIES = {}
            self.deny(request)
        for setting in ('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED', 'QUILLMD_PREVIEW_AUTH_ENABLED'):
            with override_settings(**{setting: False}):
                request = self.request(path); request.COOKIES = {}; self.deny(request)
        with patch.object(preview, 'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED', False):
            request = self.request(path); request.COOKIES = {}; self.deny(request)
        self.store.assert_not_called()

    def test_renderer_allowlist_matches_reviewed_source_content_hashes(self):
        import hashlib
        from pathlib import Path, PurePosixPath
        root = Path(__file__).resolve().parents[2] / 'static'
        names = ('docx-frame.css', 'docx-frame.js', 'vendor/docx-preview/jszip.min.js',
                 'vendor/docx-preview/docx-preview.min.js')
        compiled = set()
        for name in names:
            raw = (root / name).read_bytes()
            if name.endswith('/docx-preview.min.js'):
                source_map = (root / 'vendor/docx-preview/docx-preview.min.js.map').read_bytes()
                mapped = 'docx-preview.min.js.' + hashlib.md5(source_map).hexdigest()[:12] + '.map'
                raw = raw.replace(b'sourceMappingURL=docx-preview.min.js.map',
                                  ('sourceMappingURL=' + mapped).encode())
            path = PurePosixPath(name)
            compiled.add('/static/' + str(path.with_suffix('')) + '.'
                         + hashlib.md5(raw).hexdigest()[:12] + path.suffix)
        self.assertEqual(compiled, preview.OPAQUE_WORD_ASSETS)

    def test_grant_expiry_race_refuses_in_existing_only_store(self):
        @contextmanager
        def expired(request, *, existing_only=False):
            self.assertTrue(existing_only)
            yield None
        with patch.object(preview, 'preview_store', expired):
            self.deny(self.request('/login/'))

    def test_existing_only_real_context_never_saves_or_replaces_expired_store(self):
        current = MagicMock(); current.get.side_effect = lambda key, default=None: {
            'kind': preview.KIND, 'grant': {**self.grant['grant'], 'seen': self.now - preview.IDLE_SECONDS}}.get(key, default)
        with patch.object(preview, 'SessionStore', return_value=current) as constructor, \
                patch.object(preview, 'Session') as model, patch.object(preview.transaction, 'atomic'):
            with preview.preview_store(self.request(), existing_only=True) as value:
                self.assertIsNone(value)
            constructor.assert_called_once_with(session_key='a' * 32)
            current.save.assert_not_called(); current.set_expiry.assert_not_called()
            current.delete.assert_not_called(); current.cycle_key.assert_not_called()

    def test_valid_normal_grant_preserves_account_login_mfa_and_staff_scope(self):
        @contextmanager
        def valid(request, *, existing_only=False):
            self.assertTrue(existing_only)
            yield {'kind': preview.KIND, 'grant': dict(self.grant['grant'])}
        cases = [
            (SimpleNamespace(is_authenticated=False), '/', 302, '/login/'),
            (SimpleNamespace(is_authenticated=True, verified_at=None), '/', 403, None),
            (SimpleNamespace(is_authenticated=True, verified_at=True, is_staff=False), '/console/', 404, None),
            (SimpleNamespace(is_authenticated=True, verified_at=True, is_staff=True, is_verified=lambda:False), '/', 302, '/mfa/'),
            (SimpleNamespace(is_authenticated=True, verified_at=True, is_staff=True, is_verified=lambda:True), '/console/', 200, None),
        ]
        for user, path, status, destination in cases:
            request = self.request(path); request.user = user
            with self.subTest(path=path, status=status), patch.object(preview, 'preview_store', valid):
                response = preview.PreviewAccessMiddleware(AccessMiddleware(lambda _:HttpResponse('protected')))(request)
                self.assertEqual(response.status_code, status)
                if destination:self.assertIn(destination, response['Location'])

    def test_real_csrf_accepts_canonical_443_only_and_never_whitelists_private_port(self):
        token = _get_new_csrf_string()
        middleware = CsrfViewMiddleware(lambda _:HttpResponse('allowed'))
        for origin, expected in [('https://app.quillmd.com', None),
                                 ('https://app.quillmd.com:9443', 403), ('https://outside.invalid', 403)]:
            request = self.factory.post('/login/', {'csrfmiddlewaretoken': token}, secure=True,
                HTTP_HOST='app.quillmd.com', HTTP_ORIGIN=origin)
            request.COOKIES[settings.CSRF_COOKIE_NAME] = token
            middleware.process_request(request)
            # Avoid invoking the application/error template; the real CSRF
            # predicate and token verifier still run against the true Host.
            with patch.object(middleware, '_reject', side_effect=lambda req, reason:HttpResponse(status=403)):
                result = middleware.process_view(request, lambda _:HttpResponse(), (), {})
            self.assertEqual(None if result is None else result.status_code, expected)
        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, [])

    def test_real_patient_api_keeps_the_active_department_query_boundary(self):
        # The request/store fixtures above isolate preview I/O. Only model
        # managers are replaced in the actual departments/scoped/view path.
        @contextmanager
        def valid(request, *, existing_only=False):
            self.assertTrue(existing_only)
            yield {'kind': preview.KIND, 'grant': dict(self.grant['grant'])}
        user = SimpleNamespace(is_authenticated=True, verified_at=True,
                               is_staff=False, is_active=True)
        departments = MagicMock(name='actual_active_department_queryset')
        patients = MagicMock()
        patients.filter.return_value.values.return_value.__getitem__.return_value = [
            {'id': '11111111-1111-4111-8111-111111111111', 'display_name': 'Synthetic',
             'reference': 'synthetic', 'department_id': '22222222-2222-4222-8222-222222222222'}]
        request = self.request('/api/patients/?q=Synthetic'); request.user = user
        with patch.object(preview, 'preview_store', valid), \
             patch.object(security.Department, 'objects') as department_manager, \
             patch.object(views.Patient, 'objects') as patient_manager:
            department_manager.filter.return_value = departments
            patient_manager.filter.return_value = patients
            response = preview.PreviewAccessMiddleware(AccessMiddleware(views.api_patients))(request)
        self.assertEqual(response.status_code, 200)
        department_manager.filter.assert_called_once_with(membership__user=user, membership__active=True)
        patient_manager.filter.assert_called_once_with(department__in=departments)
        patients.filter.assert_called_once_with(display_name__icontains='Synthetic')
        patients.filter.return_value.values.assert_called_once_with('id', 'display_name', 'reference', 'department_id')
