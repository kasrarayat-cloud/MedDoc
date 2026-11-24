"""Release 1's installer items (RELEASE-1-SPEC A3's database half, A5, A6, A8, B7's installer side, Section 1.3's
sentences): offline, every Docker, root-helper and in-image call replaced by a fake, under test_install's host guard.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r1 -v
"""
import ast
import hashlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import TemporaryDirectoryTest, guard_host, release_host  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[1]
REVISION = 'a' * 40
OTHER = 'b' * 40
RULING = 'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md'
BASE = ['--revision', REVISION, '--receipts', '/tmp/cpt-receipts']


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


def settings_literal(name):
    """A module-level string literal of cptstudio/settings.py (read with ast; nothing is imported)."""
    for node in ast.parse((APP_ROOT / 'cptstudio' / 'settings.py').read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(getattr(target, 'id', None) == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise LookupError(name)


def healthy(**fields):
    return {'status': 'ok', 'service': 'cpt-studio', 'data_mode': 'synthetic-only', 'database': 'ok', **fields}


def parse(*extra):
    with mock.patch('sys.stderr', io.StringIO()):
        return install.parse_args([*BASE, *extra])


def refused(*extra) -> str:
    stderr = io.StringIO()
    with mock.patch('sys.stderr', stderr):
        try:
            install.parse_args([*BASE, *extra])
        except SystemExit as exc:
            assert exc.code == 2, exc.code
            return stderr.getvalue()
    raise AssertionError(f'{extra} was accepted')


class HealthDigestTests(unittest.TestCase):
    """B7, the installer side: either shape of /health/ is read, and a wrong digest is refused."""

    def test_the_digest_is_the_settings_prefix_and_the_release_cut_to_16_hex(self):
        self.assertEqual(install.HEALTH_DIGEST_PREFIX, settings_literal('HEALTH_DIGEST_PREFIX'))
        expected = hashlib.sha256(('cpt-studio-release:' + REVISION).encode()).hexdigest()[:16]
        self.assertEqual(install.release_digest(REVISION), expected)
        self.assertRegex(install.release_digest(REVISION), r'^[0-9a-f]{16}$')
        self.assertNotEqual(install.release_digest(REVISION), install.release_digest(OTHER))

    def test_health_ok_accepts_either_shape_and_refuses_a_wrong_or_missing_build(self):
        digest = install.release_digest(REVISION)
        self.assertTrue(install.health_ok(healthy(release=REVISION), REVISION))  # the loopback port, an older web
        self.assertTrue(install.health_ok(healthy(release_digest=digest), REVISION))  # through nginx, release 1
        self.assertTrue(install.health_ok(healthy(release=REVISION, release_digest=digest), REVISION))
        for label, body in (('another release', healthy(release=OTHER)),
                            ('another digest', healthy(release_digest=install.release_digest(OTHER))),
                            ('a release given as a digest', healthy(release_digest=REVISION)),
                            ('a digest given as a release', healthy(release=digest)),
                            ('no build at all', healthy()),
                            ('the two disagree', healthy(release=REVISION, release_digest=install.release_digest(OTHER))),
                            ('a sick database', {**healthy(release_digest=digest), 'database': 'unavailable'}),
                            ('not an object', [healthy(release=REVISION)])):
            with self.subTest(label):
                self.assertFalse(install.health_ok(body, REVISION))

    def test_the_public_path_and_the_availability_record_read_the_digest(self):
        digest = install.release_digest(REVISION)
        with mock.patch.object(install, 'probe', return_value={'status': 200, 'json': healthy(release_digest=digest)}):
            passed, observations = install.public_health(REVISION)
        self.assertTrue(passed)
        recorder = install.AvailabilityRecorder(check=lambda: {'status': 200, 'json': healthy(release_digest=digest)})
        recorder.sample()
        recorder.check = lambda: {'status': 200, 'json': healthy(release=OTHER)}
        recorder.sample()
        self.assertEqual(recorder.record['releases_seen'], [digest, OTHER])  # whichever each answer carried
        self.assertEqual(install.health_release(healthy()), None)


class LegacyVendorTests(unittest.TestCase):
    """A8: no way back to a vendor that has no BAA, in app or in switch-back; the disabled starts still work."""

    def test_each_live_legacy_mode_is_refused_in_a_switch_back_whatever_authority_is_given(self):
        for flag in ('--provider-mode', '--astra-mode', '--fable-mode', '--interpreter-mode'):
            modes = {'--provider-mode': 'disabled', flag: 'live'}
            argv = ['--phase', 'switch-back', *[part for item in modes.items() for part in item]]
            for authority in ((), ('--authorization-ref', RULING)):
                with self.subTest(flag=flag, authority=authority):
                    said = refused(*argv, *authority)
                    self.assertIn(f'{flag} live is refused', said)
                    self.assertIn('business associate agreement', said)
        # an app phase names none of them at all (its pair runs them disabled)
        for flag in ('--provider-mode', '--astra-mode', '--fable-mode', '--interpreter-mode'):
            with self.subTest(app=flag):
                self.assertIn(f'{flag} is not used by --phase app',
                              refused('--phase', 'app', '--coding-mode', 'disabled', flag, 'live'))

    def test_the_disabled_starts_and_a_replayed_interpreter_still_parse(self):
        args = parse('--phase', 'switch-back', '--provider-mode', 'disabled', '--astra-mode', 'disabled',
                     '--fable-mode', 'disabled', '--interpreter-mode', 'replay')
        self.assertEqual((args.provider_mode, args.astra_mode, args.fable_mode, args.interpreter_mode),
                         ('disabled', 'disabled', 'disabled', 'replay'))
        args = parse('--phase', 'switch-back', '--provider-mode', 'disabled', '--coding-mode', 'live',
                     '--authorization-ref', RULING)
        self.assertEqual((args.provider_mode, args.coding_mode), ('disabled', 'live'))  # the Fable coder is not legacy

    def test_the_credentials_check_refuses_them_too_before_reading_anything(self):
        with mock.patch.object(install, 'helper_stat', side_effect=AssertionError('read a credentials path')):
            for mode, live, interpreter in (('live', [], 'disabled'), ('disabled', ['astra'], 'disabled'),
                                            ('disabled', ['fable'], 'disabled'), ('disabled', [], 'live')):
                with self.subTest(mode=mode, live=live, interpreter=interpreter):
                    with self.assertRaisesRegex(install.InstallError, 'live is refused'):
                        install.check_credential_files(mode, live, interpreter)
            install.check_credential_files('disabled', [], 'disabled')  # nothing live: nothing to read
            install.check_credential_files('disabled', [], 'replay')


if __name__ == '__main__':
    unittest.main()
