"""Production lock checks only; no package installation or network access."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ops.dependency_lock import verify


class DependencyLockTests(unittest.TestCase):
    root = Path(__file__).resolve().parent.parent

    def test_checked_in_pins_match_the_full_wheel_lock(self):
        self.assertEqual(verify(self.root)['packages'], 64)

    def test_changes_to_a_pin_hash_missing_package_or_provenance_refuse(self):
        for kind in ('pin', 'hash', 'missing', 'index', 'artifact', 'duplicate', 'source_option'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in ('requirements.txt', 'requirements-production.lock', 'requirements-production.manifest.json'):
                    (root / name).write_bytes((self.root / name).read_bytes())
                manifest = json.loads((root / 'requirements-production.manifest.json').read_bytes())
                lock = root / 'requirements-production.lock'
                if kind == 'pin':
                    lock.write_text(lock.read_text().replace('anthropic==0.125.0', 'anthropic==0.124.0'))
                elif kind == 'hash':
                    lock.write_text(lock.read_text().replace(manifest['artifacts'][0]['sha256'], 'f' * 64))
                elif kind == 'missing':
                    lock.write_text('\n'.join(lock.read_text().splitlines()[:-1]) + '\n')
                elif kind == 'index':
                    manifest['index'] = 'https://untrusted.invalid/simple'
                elif kind == 'artifact':
                    manifest['artifacts'][0]['filename'] = '../escape.whl'
                elif kind == 'duplicate':
                    manifest['artifacts'].append(manifest['artifacts'][0])
                else:
                    lock.write_text(lock.read_text() + '--extra-index-url https://untrusted.invalid\n')
                # Even a recomputed digest must not excuse inconsistent version/artifact content.
                manifest['lock_sha256'] = hashlib.sha256(lock.read_bytes()).hexdigest()
                (root / 'requirements-production.manifest.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    verify(root)
