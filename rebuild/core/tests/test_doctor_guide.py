from types import SimpleNamespace
import re
from unittest.mock import patch
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.http import Http404
from django.template.loader import get_template
from core.doctor_guide import doctor_guide
from core.middleware import AccessMiddleware


@override_settings(STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class DoctorGuideTests(SimpleTestCase):
    def setUp(self):
        # This is a rendering/authentication control, with no database access.
        membership = patch('core.context.Membership.objects.filter')
        membership.start().return_value.select_related.return_value = []
        self.addCleanup(membership.stop)

    def request(self, authenticated=True):
        request = RequestFactory().get('/doctor-guide/')
        request.user = SimpleNamespace(is_authenticated=authenticated, verified_at=True,
                                       is_staff=False, is_verified=lambda: False,
                                       username='synthetic-guide-doctor', email='synthetic-guide@example.invalid',
                                       get_full_name=lambda: 'Synthetic Guide Doctor')
        return request

    def test_anonymous_guide_redirects_to_authentication(self):
        response = doctor_guide(self.request(False))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        self.assertEqual(AccessMiddleware(doctor_guide)(self.request(False)).status_code, 302)

    @override_settings(ADMIN_SITE=False, SYNTHETIC_ONLY=True)
    def test_authenticated_guide_has_private_cache_and_honest_human_checks(self):
        response = AccessMiddleware(doctor_guide)(self.request())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertIn(b'HTML previews are approximate', response.content)
        self.assertIn(b'actual browser microphone', response.content)
        self.assertIn(b'native Microsoft Word', response.content)
        self.assertIn(b'Jordan Example', response.content)

    @override_settings(ADMIN_SITE=False, SYNTHETIC_ONLY=True)
    def test_soap_walkthrough_matches_accepted_four_section_form_and_dashboard(self):
        # Accepted blank SOAP fixture SHA-256 4af367765a10367aca0f09872360445eedb1c69bc79ed7c4c4bfadd1387efdf6.
        # The private runtime fixture is independently qualified; CI checks the
        # same four-label contract without requiring private runtime files.
        expected = ['Subjective', 'Objective', 'Assessment', 'Plan']
        response = doctor_guide(self.request())
        self.assertEqual(response.status_code, 200)
        case = re.search(r'<h2>Fictional typed SOAP case</h2>(.*?)</section>',
                         response.content.decode(), re.S)
        self.assertIsNotNone(case)
        example = re.search(r'<pre[^>]*>(.*?)</pre>', case.group(1), re.S)
        self.assertIsNotNone(example)
        lines = [line.strip() for line in example.group(1).splitlines() if line.strip()]
        self.assertEqual([line.partition(':')[0] for line in lines], expected)
        self.assertTrue(all(line.partition(':')[2].strip() for line in lines))
        dashboard = get_template('dashboard.html').template.source
        self.assertIn('Approved custom forms accept ordinary narrative or labelled notes.', dashboard)
        self.assertIn('WM IOV requires exact question labels and labelled prewritten statements.', dashboard)
        self.assertIn('approved custom forms also accept ordinary narrative', case.group(1))
        self.assertNotIn('use its exact labels', case.group(1))
        self.assertNotIn('eight-field', case.group(1))
        self.assertIn('own authorized department', case.group(1))

    def test_admin_site_or_non_synthetic_activation_cannot_expose_guide(self):
        for admin, synthetic in [(True, True), (False, False)]:
            with self.subTest(admin=admin), override_settings(ADMIN_SITE=admin, SYNTHETIC_ONLY=synthetic), self.assertRaises(Http404):
                doctor_guide(self.request())

    def test_post_cannot_create_work(self):
        request = self.request()
        request.method = 'POST'
        self.assertEqual(doctor_guide(request).status_code, 405)

