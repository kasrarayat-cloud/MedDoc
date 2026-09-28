"""Production lock checks only; no package installation or network access."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ops.dependency_lock import MODEL_NAME, MODEL_REQUIREMENT, MODEL_SHA256, MODEL_URL, verify


class DependencyLockTests(unittest.TestCase):
    root = Path(__file__).resolve().parent.parent

    def copy_contract(self, root):
        for name in ('requirements.txt', 'requirements-production.lock', 'requirements-production.manifest.json'):
            (root / name).write_bytes((self.root / name).read_bytes())
        return json.loads((root / 'requirements-production.manifest.json').read_bytes())

    def save_manifest(self, root, manifest):
        # Re-sign the envelope to test the inner constraints, not only stale digests.
        manifest['requirements_sha256'] = hashlib.sha256((root / 'requirements.txt').read_bytes()).hexdigest()
        manifest['lock_sha256'] = hashlib.sha256((root / 'requirements-production.lock').read_bytes()).hexdigest()
        (root / 'requirements-production.manifest.json').write_text(json.dumps(manifest))

    def test_checked_in_pins_match_the_full_wheel_lock(self):
        self.assertEqual(verify(self.root)['packages'], 89)
        manifest = json.loads((self.root / 'requirements-production.manifest.json').read_bytes())
        self.assertEqual(len(manifest['artifacts']), 89)
        model = next(a for a in manifest['artifacts'] if a['name'] == MODEL_NAME)
        self.assertEqual((model['source'], model['sha256']), (MODEL_URL, MODEL_SHA256))
        self.assertEqual(sum(a['source'] == 'https://pypi.org/simple' for a in manifest['artifacts']), 88)

    def test_changes_to_a_pin_hash_missing_package_or_provenance_refuse(self):
        for kind in ('pin', 'hash', 'missing', 'index', 'artifact', 'duplicate', 'source_option',
                     'requirements_option', 'duplicate_pin', 'bytes_bool', 'bytes_zero', 'filename_version',
                     'filename_package', 'source', 'extra_source_key', 'model_source', 'model_filename'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = self.copy_contract(root)
                lock = root / 'requirements-production.lock'
                req = root / 'requirements.txt'
                artifact = manifest['artifacts'][0]
                model = next(a for a in manifest['artifacts'] if a['name'] == MODEL_NAME)
                if kind == 'pin':
                    lock.write_text(lock.read_text().replace('anthropic==0.125.0', 'anthropic==0.124.0'))
                elif kind == 'hash':
                    lock.write_text(lock.read_text().replace(artifact['sha256'], 'f' * 64))
                elif kind == 'missing':
                    lock.write_text('\n'.join(lock.read_text().splitlines()[:-1]) + '\n')
                elif kind == 'index':
                    manifest['index'] = 'https://untrusted.invalid/simple'
                elif kind == 'artifact':
                    artifact['filename'] = '../escape.whl'
                elif kind == 'duplicate':
                    manifest['artifacts'].append(artifact)
                elif kind == 'source_option':
                    lock.write_text(lock.read_text() + '--extra-index-url https://untrusted.invalid\n')
                elif kind == 'requirements_option':
                    req.write_text(req.read_text() + '--find-links https://untrusted.invalid\n')
                elif kind == 'duplicate_pin':
                    req.write_text(req.read_text() + MODEL_REQUIREMENT + '\n')
                elif kind == 'bytes_bool':
                    artifact['bytes'] = True
                elif kind == 'bytes_zero':
                    artifact['bytes'] = 0
                elif kind == 'filename_version':
                    artifact['filename'] = artifact['filename'].replace('-' + artifact['version'] + '-', '-0.0.0-')
                elif kind == 'filename_package':
                    artifact['filename'] = 'wrong' + artifact['filename']
                elif kind == 'source':
                    artifact['source'] = MODEL_URL
                elif kind == 'extra_source_key':
                    artifact['url'] = 'https://untrusted.invalid/alternate.whl'
                elif kind == 'model_source':
                    model['source'] = 'https://pypi.org/simple'
                elif kind == 'model_filename':
                    model['filename'] = model['filename'].replace('py3-none-any', 'cp312-none-any')
                self.save_manifest(root, manifest)
                with self.assertRaises(ValueError):
                    verify(root)

    def test_only_exact_reviewed_official_model_url_is_accepted(self):
        replacements = (
            MODEL_REQUIREMENT.replace('https://github.com/', 'https://untrusted.invalid/'),
            MODEL_REQUIREMENT.replace('https://github.com/', 'https://github.com.evil.invalid/'),
            MODEL_REQUIREMENT.replace('https://github.com/', 'https://github.com@evil.invalid/'),
            MODEL_REQUIREMENT.replace('/explosion/', '/another-owner/'),
            MODEL_REQUIREMENT.replace('/spacy-models/', '/another-repo/'),
            MODEL_REQUIREMENT.replace('3.8.0', '3.8.1'),
            MODEL_REQUIREMENT.replace(MODEL_SHA256, 'f' * 64),
            MODEL_REQUIREMENT.replace('#sha256=', '#md5='),
            MODEL_REQUIREMENT.replace('#sha256=' + MODEL_SHA256, ''),
            MODEL_REQUIREMENT.replace('#sha256=', '?download=1#sha256='),
            MODEL_REQUIREMENT.replace('https:', 'http:'),
            MODEL_REQUIREMENT.replace('https://github.com/', 'file:///tmp/'),
            MODEL_REQUIREMENT.replace('en-core-web-sm @ ', 'another-package @ '),
            MODEL_NAME + '==3.8.0',
            MODEL_REQUIREMENT + ' ; python_version >= "3.12"',
        )
        for replacement in replacements:
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = self.copy_contract(root)
                # Both pin and lock agree on the bad URL; neither mutual agreement nor
                # a recomputed manifest authorizes a different host/model/version/hash.
                for name in ('requirements.txt', 'requirements-production.lock'):
                    path = root / name
                    path.write_text(path.read_text().replace(MODEL_REQUIREMENT, replacement))
                self.save_manifest(root, manifest)
                with self.assertRaises(ValueError):
                    verify(root)

    def test_model_lock_requires_matching_second_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.copy_contract(root)
            path = root / 'requirements-production.lock'
            path.write_text(path.read_text().replace('--hash=sha256:' + MODEL_SHA256, '--hash=sha256:' + 'f' * 64))
            self.save_manifest(root, manifest)
            with self.assertRaises(ValueError):
                verify(root)

    def test_local_wheel_inventory_bytes_and_missing_extra_symlink_refuse(self):
        # Small isolated stand-in exercises bytes, not a download or installation.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheels = root / 'wheels'
            wheels.mkdir()
            payload = b'bounded wheel bytes'
            sha = hashlib.sha256(payload).hexdigest()
            req = root / 'requirements.txt'
            lock = root / 'requirements-production.lock'
            req.write_text('example==1.0\n')
            lock.write_text('example==1.0 --hash=sha256:' + sha + '\n')
            manifest = json.loads((self.root / 'requirements-production.manifest.json').read_bytes())
            manifest['artifacts'] = [dict(name='example', version='1.0', filename='example-1.0-py3-none-any.whl',
                                          sha256=sha, bytes=len(payload), source='https://pypi.org/simple')]
            self.save_manifest(root, manifest)
            wheel = wheels / manifest['artifacts'][0]['filename']
            wheel.write_bytes(payload)
            self.assertEqual(verify(root, wheels)['packages'], 1)
            wheel.write_bytes(b'x' * len(payload))
            with self.assertRaises(ValueError):
                verify(root, wheels)
            wheel.unlink()
            with self.assertRaises(ValueError):
                verify(root, wheels)
            target = root / 'elsewhere.whl'
            target.write_bytes(payload)
            wheel.symlink_to(target)
            with self.assertRaises(ValueError):
                verify(root, wheels)
            wheel.unlink()
            wheel.write_bytes(payload)
            (wheels / 'unexpected.whl').write_bytes(payload)
            with self.assertRaises(ValueError):
                verify(root, wheels)

    def test_production_installer_uses_verified_hash_lock(self):
        installer = (self.root / 'deploy/production/bootstrap-host.sh').read_text()
        verify_at = installer.index('"$app/ops/dependency_lock.py" --root "$app"')
        install_at = installer.index('"$app/.venv/bin/python" -m pip --isolated install')
        self.assertLess(verify_at, install_at)
        command = installer[install_at:installer.index('\n', installer.index('-r "$app/requirements-production.lock"', install_at))]
        for flag in ('--index-url https://pypi.org/simple', '--require-hashes', '--only-binary=:all:',
                     '-r "$app/requirements-production.lock"'):
            self.assertIn(flag, command)
        self.assertNotIn('--extra-index-url', command)
        self.assertNotIn('requirements.txt', command)
