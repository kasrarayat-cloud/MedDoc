"""Offline controls for the D1b dependency stage, on a fake venv with a simulated pip.

The module's literal pins are replaced, for the duration of each test, by one fake package ``demo`` moving
1.0 -> 1.1, so every rule (exact population, modes, generated metadata, untouched neighbours, stray bytecode,
drained units, no downgrade, the live-venv refusal) is exercised without pip or the network.
"""
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from ops import rebuild_dependency_stage as stage
from ops import venv_footprint as footprint

SITE = footprint.SITE
#: The literal pins, captured before any test replaces them with the fake package.
REAL_TRANSITIONS, REAL_WHEELS = dict(stage.TRANSITIONS), dict(stage.WHEELS)


def record_line(name, data):
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
    return [name, 'sha256=' + digest, str(len(data))]


def record_text(rows):
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator='\n').writerows(rows)
    return buffer.getvalue().encode()


def build_wheel(path, files, *, requires=('extra-thing ; python_version < "3.11"',), bad_record=False):
    meta = 'Metadata-Version: 2.1\nName: demo\nVersion: 1.1\n' + ''.join('Requires-Dist: %s\n' % r for r in requires)
    payload = dict(files)
    payload['demo-1.1.dist-info/METADATA'] = meta.encode()
    payload['demo-1.1.dist-info/WHEEL'] = b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
    rows = [record_line(n, b'tampered' if bad_record and n.endswith('.py') else d) for n, d in payload.items()]
    rows.append(['demo-1.1.dist-info/RECORD', '', ''])
    payload['demo-1.1.dist-info/RECORD'] = record_text(rows)
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in payload.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = (0o100644) << 16
            archive.writestr(info, data)
    path.chmod(0o600)
    raw = path.read_bytes()
    return {'filename': path.name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


def fake_venv(root):
    """demo 1.0 (with a stray .pyc at a RECORDed module's cache path), other 2.0 (with its own stray), pip."""
    venv = root / 'venv'
    site = venv / SITE
    (venv / 'bin').mkdir(parents=True)
    write(venv / 'pyvenv.cfg', b'home = /usr/bin\n')
    packages = {'demo': ('1.0', {'demo/__init__.py': b'OLD = 1\n', 'demo/old_only.py': b'GONE = 1\n'}),
                'other': ('2.0', {'other/__init__.py': b'OTHER = 1\n'}),
                'pip': ('24.0', {'pip/__init__.py': b'__version__ = "24.0"\n'})}
    for name, (version, files) in packages.items():
        for relative, data in files.items():
            write(site / relative, data)
        dist = name + '-' + version + '.dist-info'
        write(site / dist / 'METADATA', ('Metadata-Version: 2.1\nName: %s\nVersion: %s\n' % (name, version)).encode())
        write(site / dist / 'INSTALLER', b'pip\n')
        rows = [record_line(n, (site / n).read_bytes()) for n in files]
        rows += [record_line(dist + '/METADATA', (site / dist / 'METADATA').read_bytes()),
                 record_line(dist + '/INSTALLER', b'pip\n'), [dist + '/RECORD', '', '']]
        write(site / dist / 'RECORD', record_text(rows))
    write(site / 'demo/__pycache__/__init__.cpython-312.pyc', b'stray demo bytecode')
    write(site / 'other/__pycache__/__init__.cpython-312.pyc', b'stray other bytecode')
    return venv


class FakePip:
    """pip 24.0's observable effect: RECORD-driven uninstall (cache paths included), then a wheel install."""

    def __init__(self, venv, wheel_path, *, tamper=None, returncode=0):
        self.venv, self.wheel_path, self.tamper, self.returncode = venv, wheel_path, tamper, returncode
        self.calls = []

    def __call__(self, argv, **options):
        self.calls.append(argv)
        assert options['umask'] == 0o022 and argv[1:3] == ['-I', '-B']
        if self.returncode:
            return subprocess.CompletedProcess(argv, self.returncode, b'', b'ERROR: simulated\n')
        site = self.venv / SITE
        old = site / 'demo-1.0.dist-info'
        for row in csv.reader(io.StringIO((old / 'RECORD').read_text())):
            target = site / row[0]
            if target.exists():
                target.unlink()
            if row[0].endswith('.py'):
                cache = target.parent / '__pycache__' / (target.stem + '.cpython-312.pyc')
                if cache.exists():
                    cache.unlink()
        for directory in (site / 'demo/__pycache__', site / 'demo', old):
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()
        rows = []
        with zipfile.ZipFile(self.wheel_path) as archive:
            for info in archive.infolist():
                if info.filename.endswith('/RECORD'):
                    continue
                data = archive.read(info)
                write(site / info.filename, data)
                rows.append(record_line(info.filename, data))
        generated = stage.generated_metadata('demo', self.wheel_path)
        for name, data in generated.items():
            write(self.venv / name, data)
            rows.append(record_line(name[len(SITE) + 1:], data))
        rows.append(['demo-1.1.dist-info/RECORD', '', ''])
        write(site / 'demo-1.1.dist-info/RECORD', record_text(rows))
        for directory in (site / 'demo', site / 'demo-1.1.dist-info'):
            directory.chmod(0o755)
        if self.tamper:
            self.tamper(site)
        return subprocess.CompletedProcess(argv, 0, b'Successfully installed demo-1.1\n', b'')


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.root.chmod(0o700)
        self.addCleanup(self.temporary.cleanup)
        self.venv = fake_venv(self.root)
        self.wheels = self.root / 'wheels'
        self.wheels.mkdir(mode=0o700)
        self.wheel = self.wheels / 'demo-1.1-py3-none-any.whl'
        pin = build_wheel(self.wheel, {'demo/__init__.py': b'NEW = 1\n', 'demo/new.py': b'ADDED = 1\n'})
        for name, value in {'TRANSITIONS': {'demo': ('1.0', '1.1')}, 'WHEELS': {'demo': pin},
                            'ROOTS': {'demo': ('demo',)}, 'NATIVE': {'demo': ()}, 'DISTRIBUTIONS': 3,
                            'VENV': self.root / 'live-venv-not-present'}.items():
            patcher = patch.object(stage, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        checks = patch.object(stage, 'checks', return_value={'stubbed': True})
        checks.start()
        self.addCleanup(checks.stop)
        umask = os.umask(0o077)
        self.addCleanup(os.umask, umask)

    def install(self, pip=None, *, drained=lambda: True, before=None, live=False, venv=None):
        venv = venv or self.venv
        pip = pip or FakePip(venv, self.wheel)
        records = []
        before = before or footprint.snapshot(venv)
        after, proof = stage.install_once(venv, self.wheels, before, drained=drained, recorder=records.append,
                                          live=live, runner=pip)
        return after, proof, records, pip

    def test_one_pip_process_moves_only_the_package_and_accounts_for_stray_bytecode(self):
        after, proof, records, pip = self.install()
        self.assertEqual(len(pip.calls), 1)
        self.assertEqual(pip.calls[0][3:], stage.pip_arguments({'demo': {'path': str(self.wheel)}}))
        self.assertEqual(records[0]['returncode'], 0)
        self.assertEqual(proof['changes'], [{'name': 'demo', 'old_version': '1.0', 'new_version': '1.1'}])
        self.assertEqual(proof['unrecorded_bytecode_removed_by_pip_uninstall'],
                         [SITE + '/demo/__pycache__/__init__.cpython-312.pyc'])
        self.assertEqual(proof['unrecorded_bytecode_retained'], [SITE + '/other/__pycache__/__init__.cpython-312.pyc'])
        self.assertEqual(after['census']['distributions']['demo'], '1.1')
        self.assertTrue(proof['no_downgrade'])

    def test_every_deviation_from_the_wheel_or_outside_the_package_refuses(self):
        tampers = {
            'bytecode_in_new_package': lambda site: write(site / 'demo/__pycache__/new.cpython-312.pyc', b'x'),
            'neighbour_changed': lambda site: write(site / 'other/__init__.py', b'OTHER = 2\n'),
            'neighbour_stray_removed': lambda site: (site / 'other/__pycache__/__init__.cpython-312.pyc').unlink(),
            'group_writable_file': lambda site: (site / 'demo/new.py').chmod(0o664),
            'payload_changed': lambda site: write(site / 'demo/new.py', b'ADDED = 2\n'),
            'extra_file': lambda site: write(site / 'demo/extra.py', b'x'),
            'old_dist_info_left': lambda site: write(site / 'demo-1.0.dist-info/METADATA',
                                                     b'Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n'),
        }
        for name, tamper in tampers.items():
            with self.subTest(tamper=name), tempfile.TemporaryDirectory() as other:
                venv = fake_venv(Path(other).resolve())
                with self.assertRaises((stage.Refusal, footprint.Refusal)):
                    self.install(FakePip(venv, self.wheel, tamper=tamper), venv=venv)

    def test_pip_failure_is_recorded_and_refused_without_retry(self):
        pip = FakePip(self.venv, self.wheel, returncode=1)
        records = []
        with self.assertRaises(stage.Refusal):
            stage.install_once(self.venv, self.wheels, footprint.snapshot(self.venv), drained=lambda: True,
                               recorder=records.append, runner=pip)
        self.assertEqual((len(pip.calls), records[0]['returncode']), (1, 1))

    def test_units_must_be_drained_before_and_after_the_one_process(self):
        with self.assertRaises(stage.Refusal):
            self.install(drained=lambda: False)
        states = iter([True, False])
        pip = FakePip(self.venv, self.wheel)
        with self.assertRaises(stage.Refusal):
            self.install(pip, drained=lambda: next(states))
        self.assertEqual(len(pip.calls), 1)

    def test_a_changed_venv_or_wheel_refuses_before_pip(self):
        before = footprint.snapshot(self.venv)
        write(self.venv / SITE / 'other/__init__.py', b'changed\n')
        pip = FakePip(self.venv, self.wheel)
        with self.assertRaises(footprint.Refusal):
            self.install(pip, before=before)
        self.assertEqual(pip.calls, [])
        with zipfile.ZipFile(self.wheel, 'a') as archive:
            archive.writestr('demo/late.py', b'x')
        with self.assertRaises(stage.Refusal):
            self.install(FakePip(self.venv, self.wheel))

    def test_the_live_venv_is_refused_unless_the_declared_act_says_live(self):
        with patch.object(stage, 'VENV', self.venv):
            pip = FakePip(self.venv, self.wheel)
            with self.assertRaises(stage.Refusal):
                self.install(pip, live=False)
            self.assertEqual(pip.calls, [])
        with self.assertRaises(stage.Refusal):
            self.install(live=True)

    def test_no_transition_may_downgrade_or_stand_still(self):
        self.assertTrue(stage.forward_only({'pypdf': ('6.21.1', '6.21.4'), 'filelock': ('4.0.0', '4.2.1')}))
        for transitions in ({'demo': ('1.1', '1.0')}, {'demo': ('1.0', '1.0')}, {'demo': ('1.0rc1', '1.0')}):
            with self.subTest(transitions=transitions), self.assertRaises(stage.Refusal):
                stage.forward_only(transitions)
        with patch.object(stage, 'TRANSITIONS', {'demo': ('1.1', '1.0')}), self.assertRaises(stage.Refusal):
            self.install()

    def test_the_real_pins_only_move_forward(self):
        self.assertTrue(stage.forward_only(REAL_TRANSITIONS))
        self.assertEqual(sorted(REAL_TRANSITIONS), sorted(REAL_WHEELS))
        self.assertEqual(REAL_TRANSITIONS, {'filelock': ('4.0.0', '4.2.1'), 'msgpack': ('1.2.2', '1.2.3'),
                                            'pypdf': ('6.21.1', '6.21.4')})

    def test_wheel_proof_refuses_tampered_or_unbounded_wheels(self):
        stage.wheel(self.wheel, 'demo')
        variants = {'bad_record': dict(bad_record=True), 'outside_roots': dict(extra={'evil/x.py': b'x'}),
                    'unconditional_requirement': dict(requires=('extra-thing',))}
        for name, options in variants.items():
            with self.subTest(variant=name):
                path = self.root / name / 'demo-1.1-py3-none-any.whl'
                path.parent.mkdir(mode=0o700)
                files = {'demo/__init__.py': b'NEW = 1\n', **options.pop('extra', {})}
                pin = build_wheel(path, files, **options)
                with patch.object(stage, 'WHEELS', {'demo': pin}), self.assertRaises(stage.Refusal):
                    stage.wheel(path, 'demo')
        self.wheel.chmod(0o664)
        with self.assertRaises(stage.Refusal):
            stage.wheel(self.wheel, 'demo')

    def test_calibration_runs_on_a_copy_and_proves_the_live_venv_untouched(self):
        live = fake_venv(self.root / 'live-root')
        copy = self.root / 'copy'
        shutil.copytree(live, copy, symlinks=True)
        with patch.object(stage, 'VENV', live):
            receipt = stage.calibrate(copy, self.wheels, self.root / 'calibration',
                                      runner=FakePip(copy, self.wheel))
            self.assertTrue(receipt['live_venv_unchanged'] and receipt['copy_before_matches_live'])
            self.assertEqual(receipt['transition']['unrecorded_bytecode_after'], 1)
            for name in ('venv-copy-before.json', 'venv-copy-after.json', 'pip-process.json',
                         'calibration-receipt.json'):
                self.assertEqual(oct((self.root / 'calibration' / name).stat().st_mode & 0o777), '0o600')
            with self.assertRaises(stage.Refusal):
                stage.calibrate(live, self.wheels, self.root / 'calibration-2', runner=FakePip(live, self.wheel))
            fresh = self.root / 'copy-3'
            shutil.copytree(live, fresh, symlinks=True)
            touch_live = FakePip(fresh, self.wheel, tamper=lambda site: write(live / 'pyvenv.cfg', b'touched\n'))
            with self.assertRaises(footprint.Refusal):
                stage.calibrate(fresh, self.wheels, self.root / 'calibration-3', runner=touch_live)


class ChecksTests(unittest.TestCase):
    def test_checks_compare_the_venv_s_own_report_with_the_snapshot(self):
        venv = Path('/nonexistent/venv')
        site = venv / SITE
        after = {'files': {SITE + '/certifi/cacert.pem': {'sha256': 'c' * 64}},
                 'census': {'distributions': {'pillow': '13.0.0'}}}
        good = {'pypdf': '6.21.4', 'pypdf_file': str(site / 'pypdf/__init__.py'), 'pdf_roundtrip': True,
                'filelock': '4.2.1', 'filelock_file': str(site / 'filelock/__init__.py'), 'filelock_api': True,
                'msgpack': [1, 2, 3], 'msgpack_extension': str(site / stage.NATIVE['msgpack'][0]),
                'msgpack_c_packer': True, 'msgpack_roundtrip': True,
                'cachecontrol_file_cache': str(site / 'cachecontrol/caches/file_cache.py'),
                'certifi_ca_sha256': 'c' * 64, 'pillow': '13.0.0', 'png_roundtrip': True}

        def runner(report, pip_check=b'No broken requirements found.\n'):
            def run(argv, **options):
                output = pip_check if argv[-1] == 'check' else json.dumps(report).encode()
                return subprocess.CompletedProcess(argv, 0, output, b'')
            return run
        umask = os.umask(0o077)
        try:
            self.assertEqual(stage.checks(venv, after, runner=runner(good)), good)
            for change in ({'msgpack_c_packer': False}, {'pypdf': '6.21.1'}, {'certifi_ca_sha256': 'd' * 64}):
                with self.subTest(change=change), self.assertRaises(stage.Refusal):
                    stage.checks(venv, after, runner=runner(dict(good, **change)))
            with self.assertRaises(stage.Refusal):
                stage.checks(venv, after, runner=runner(good, b'pypdf 6.21.4 requires x, which is not installed.\n'))
        finally:
            os.umask(umask)


class PublishedTests(unittest.TestCase):
    def documents(self, **changes):
        pin = stage.WHEELS['pypdf']
        api = {'urls': [{'filename': pin['filename'], 'digests': {'sha256': pin['sha256']}, 'size': pin['bytes'],
                         'yanked': False, 'url': 'https://files.pythonhosted.org/packages/x/' + pin['filename']}]}
        simple = {'files': [{'filename': pin['filename'], 'hashes': {'sha256': pin['sha256']}, 'yanked': False}]}
        api['urls'][0].update(changes.get('api', {}))
        simple['files'][0].update(changes.get('simple', {}))
        return json.dumps(api).encode(), json.dumps(simple).encode()

    def test_both_surfaces_must_publish_the_pinned_digest(self):
        self.assertTrue(stage.published('pypdf', *self.documents()).startswith('https://files.pythonhosted.org/'))
        for changes in ({'api': {'digests': {'sha256': '0' * 64}}}, {'simple': {'hashes': {'sha256': '0' * 64}}},
                        {'api': {'yanked': True}}, {'simple': {'yanked': 'withdrawn'}}, {'api': {'size': 1}},
                        {'api': {'url': 'https://example.invalid/pypdf.whl'}}):
            with self.subTest(changes=changes), self.assertRaises(stage.Refusal):
                stage.published('pypdf', *self.documents(**changes))

    def test_fetch_writes_only_verified_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            root.chmod(0o700)
            wheel = root / 'demo-1.1-py3-none-any.whl'
            pin = build_wheel(wheel, {'demo/__init__.py': b'NEW = 1\n'})
            api = json.dumps({'urls': [{'filename': pin['filename'], 'digests': {'sha256': pin['sha256']},
                                        'size': pin['bytes'], 'url': 'https://files.pythonhosted.org/d.whl'}]})
            simple = json.dumps({'files': [{'filename': pin['filename'], 'hashes': {'sha256': pin['sha256']}}]})

            def getter(url, accept=None):
                return {'json': api.encode(), 'simple': simple.encode()}.get(
                    'json' if url.endswith('/json') else 'simple' if '/simple/' in url else '', wheel.read_bytes())
            with patch.object(stage, 'TRANSITIONS', {'demo': ('1.0', '1.1')}), \
                    patch.object(stage, 'WHEELS', {'demo': pin}), patch.object(stage, 'ROOTS', {'demo': ('demo',)}), \
                    patch.object(stage, 'NATIVE', {'demo': ()}):
                evidence = stage.fetch(root / 'wheels', getter=getter)
                self.assertEqual(evidence['demo']['sha256'], pin['sha256'])
                self.assertEqual(oct((root / 'wheels' / pin['filename']).stat().st_mode & 0o777), '0o600')
                with self.assertRaises(stage.Refusal):
                    stage.fetch(root / 'wheels-2', getter=lambda url, accept=None: getter(url, accept)
                                if 'pythonhosted' not in url else b'not the wheel')


if __name__ == '__main__':
    unittest.main()
