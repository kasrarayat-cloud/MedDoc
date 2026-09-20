"""Operator form-client safety checks; all network responses are synthetic."""
import unittest
import httpx
from ops import preview_http as preview


class PreviewClientTests(unittest.TestCase):
    def test_only_local_opaque_signin_redirect_is_followed(self):
        for target in ('https://attacker.invalid/', '//attacker.invalid/', '/preview/sign-in/?next=/invite/secret/',
                       '/preview/sign-in/?flow=' + 'a' * 32 + '&next=secret', '/preview/sign-in/?flow=bad',
                       '/preview/sign-in/?flow=' + 'a' * 32 + '#other'):
            with self.subTest(target=target), self.assertRaises(preview.PreviewAccessError):
                preview.sign_in_path(httpx.Response(302, headers={'location': target}))

    def exercise(self, destination='/health/', cookie_flags='Secure; HttpOnly; SameSite=Lax'):
        flow = 'b' * 64
        csrf = 'C' * 64
        calls = []
        def handler(request):
            self.assertNotIn('authorization', request.headers)
            self.assertNotIn('synthetic-password', str(request.url))
            calls.append((request.method, request.url.path))
            if request.method == 'GET' and request.url.path == '/health/':
                return httpx.Response(302, headers={'location': '/preview/sign-in/?flow=' + flow})
            if request.method == 'GET':
                return httpx.Response(200, text=f'<form><input name="csrfmiddlewaretoken" value="{csrf}"><input name="flow" value="{flow}"></form>')
            self.assertEqual(request.headers['origin'], preview.ORIGIN)
            self.assertIn(b'csrfmiddlewaretoken=', request.content)
            return httpx.Response(302, headers={'location': destination,
                'set-cookie': preview.COOKIE + '=synthetic-session; Path=/; ' + cookie_flags})
        with httpx.Client(base_url=preview.ORIGIN, transport=httpx.MockTransport(handler), follow_redirects=False) as client:
            preview.authenticate(client, {'username': 'synthetic', 'password': 'synthetic-password'})
        return calls

    def test_real_form_sequence_uses_post_and_never_basic_or_url_credentials(self):
        self.assertEqual(self.exercise(), [('GET', '/health/'), ('GET', '/preview/sign-in/'), ('POST', '/preview/sign-in/')])

    def test_bad_return_and_missing_cookie_protection_refused(self):
        for destination, flags in (('https://attacker.invalid', 'Secure; HttpOnly; SameSite=Lax'),
                                   ('/health/', 'HttpOnly; SameSite=Lax'),
                                   ('/health/', 'Secure; SameSite=Lax'),
                                   ('/health/', 'Secure; HttpOnly; SameSite=None'),
                                   ('/health/', 'Secure; HttpOnly; SameSite=Lax; Domain=app.quillmd.com')):
            with self.subTest(destination=destination, flags=flags), self.assertRaises(preview.PreviewAccessError):
                self.exercise(destination, flags)

    def test_logout_requires_correct_destination_and_actual_access_revocation(self):
        for destination, health in (('/unexpected/', 302), ('/preview/sign-in/', 200), ('/preview/sign-in/', 302)):
            with self.subTest(destination=destination, health=health):
                def handler(request):
                    if request.method == 'POST':
                        return httpx.Response(302, headers={'location': destination})
                    return httpx.Response(health, headers={'location': '/preview/sign-in/?flow=' + 'a' * 32})
                with httpx.Client(base_url=preview.ORIGIN, transport=httpx.MockTransport(handler)) as client:
                    client.cookies.set('quillmd_doctor_csrf', 'C' * 32)
                    if destination == '/preview/sign-in/' and health == 302:
                        preview.sign_out(client)
                    else:
                        with self.assertRaises(preview.PreviewAccessError):
                            preview.sign_out(client)


if __name__ == '__main__':
    unittest.main()
