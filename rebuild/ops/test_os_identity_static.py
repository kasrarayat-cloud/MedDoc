"""Regressions for public-asset access after the application UID changes."""
import hashlib
import importlib.util
import io
import json
import os
from email.message import Message
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/activate-os-identity.py'
SPEC = importlib.util.spec_from_file_location('os_identity_static_under_test', SCRIPT)
activation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(activation)


class StaticIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.app = Path(self.temporary.name)
        self.addCleanup(patch.stopall)
        patch.object(activation, 'APP', self.app).start()
        source = self.app / 'static'
        target = self.app / 'staticfiles'
        source.mkdir(mode=0o700)
        target.mkdir(mode=0o700)
        mapping = {}
        for name in ('app.css', 'app.js'):
            data = ('synthetic public ' + name).encode()
            hashed = 'app.' + hashlib.md5(data, usedforsecurity=False).hexdigest()[:12] + '.' + name.rsplit('.', 1)[1]
            (source / name).write_bytes(data)
            for path in (target / name, target / hashed):
                path.write_bytes(data)
                path.chmod(0o600)
            mapping[name] = hashed
        manifest = target / 'staticfiles.json'
        manifest.write_text(json.dumps({'paths': mapping, 'version': '1.1'}))
        manifest.chmod(0o600)
        self.target = target
        self.mapping = mapping
        patch.object(activation, 'static_sources', return_value={
            name: source / name for name in ('app.css', 'app.js')}).start()

    def test_permissions_fix_preserves_all_static_bytes_and_identities(self):
        before = activation.static_inventory()
        proof = activation.make_static_readable()
        self.assertTrue(proof['all_content_identical'])
        self.assertEqual(proof['before'], before)
        for name, row in proof['after'].items():
            self.assertEqual(row['mode'], 0o755 if name == '.' else 0o644)
            self.assertEqual({key: value for key, value in row.items() if key != 'mode'},
                             {key: value for key, value in before[name].items() if key != 'mode'})
        self.assertEqual((self.app / 'static').stat().st_mode & 0o777, 0o700)

    def test_extra_file_symlink_or_hardlink_refuses_before_permission_change(self):
        for kind in ('extra', 'symlink', 'hardlink'):
            unwanted = self.target / '.env'
            if kind == 'extra':
                unwanted.write_bytes(b'synthetic-private-value')
            elif kind == 'symlink':
                unwanted.symlink_to(self.app / 'static/app.css')
            else:
                os.link(self.target / 'app.css', unwanted)
            try:
                with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                    activation.make_static_readable()
                self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
                self.assertEqual((self.target / 'app.css').stat().st_mode & 0o777, 0o600)
            finally:
                unwanted.unlink()

    def test_stale_collected_source_refuses_before_permissions_change(self):
        (self.app / 'static/app.css').write_bytes(b'new source not collected')
        with self.assertRaisesRegex(RuntimeError, 'differs from current'):
            activation.make_static_readable()
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)

    def responses(self, *, stylesheet_type='text/css', css_override=None, missing_form=False):
        hashed = self.mapping['app.css']
        html = (f'<link href="/static/{hashed}">' +
                ('' if missing_form else '<input name="csrfmiddlewaretoken">')).encode()
        css = (self.target / hashed).read_bytes() if css_override is None else css_override
        class Response(io.BytesIO):
            def __init__(self, body, content_type):
                super().__init__(body)
                self.status = 200
                self.headers = Message()
                self.headers['Content-Type'] = content_type
        def get(url, timeout):
            self.assertTrue(url.startswith(('http://127.0.0.1:9130/', 'http://127.0.0.1:9131/')))
            return Response(html, 'text/html') if url.endswith('/login/') else Response(css, stylesheet_type)
        opener = unittest.mock.Mock()
        opener.open.side_effect = get
        return opener

    def test_actual_login_and_manifest_stylesheet_are_required(self):
        opener = self.responses()
        with patch.object(activation, 'build_opener', return_value=opener):
            result = activation.verify_interfaces()
        self.assertEqual(set(result), {'doctor', 'admin'})
        self.assertEqual(opener.open.call_count, 4)
        self.assertTrue(all(row['stylesheet_hash_matched'] for row in result.values()))
        for changes in ({'stylesheet_type': 'text/html'}, {'css_override': b''},
                        {'css_override': b'wrong css'}, {'missing_form': True}):
            with self.subTest(changes=changes), patch.object(activation, 'build_opener', return_value=self.responses(**changes)):
                with self.assertRaises(RuntimeError):
                    activation.verify_interfaces()


if __name__ == '__main__':
    unittest.main()
