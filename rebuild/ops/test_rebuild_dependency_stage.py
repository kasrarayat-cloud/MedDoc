"""Offline controls for the D1b dependency stage, on a fake venv with a simulated pip.

The module's literal pins are replaced, for the duration of each test, by one fake package ``demo`` moving
1.0 -> 1.1, so every rule (exact population, modes, generated metadata, untouched neighbours, stray bytecode,
drained units, no downgrade, the live-venv refusal) is exercised without pip or the network.
"""
import base64
from contextlib import redirect_stdout
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from ops import rebuild_dependency_stage as stage
from ops import venv_footprint as footprint

SITE = footprint.SITE
#: The literal pins, captured before any test replaces them with the fake package.
REAL_TRANSITIONS, REAL_WHEELS = dict(stage.TRANSITIONS), dict(stage.WHEELS)
ROUTED_SIGNALS = ('SIGTERM', 'SIGINT', 'SIGHUP')


def settle():
    for _ in range(40):
        time.sleep(0.005)


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
    write(venv / 'bin/python', b'#!/bin/sh\nexit 1\n', 0o755)
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
    """pip 24.0's observable effect: hash checking of the requirements file's wheels (--require-hashes), then a
    RECORD-driven uninstall (cache paths included), then a wheel install from the path the requirements file names."""

    def __init__(self, venv, wheel_path, *, tamper=None, returncode=0, during=None):
        self.venv, self.wheel_path, self.tamper, self.returncode = venv, wheel_path, tamper, returncode
        self.during = during
        self.calls = []
        self.installed_from = None

    def __call__(self, argv, **options):
        self.calls.append(argv)
        assert options['umask'] == 0o022 and argv[1:3] == ['-I', '-B']
        if self.during:
            self.during()
        if self.returncode:
            return subprocess.CompletedProcess(argv, self.returncode, b'', b'ERROR: simulated\n')
        assert '--require-hashes' in argv
        requirements = Path(argv[argv.index('-r') + 1])
        path, option = requirements.read_text().split()
        if option != '--hash=sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest():
            return subprocess.CompletedProcess(argv, 1, b'', b'ERROR: THESE PACKAGES DO NOT MATCH THE HASHES\n')
        self.installed_from = wheel_path = Path(path)
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
        with zipfile.ZipFile(wheel_path) as archive:
            for info in archive.infolist():
                if info.filename.endswith('/RECORD'):
                    continue
                data = archive.read(info)
                write(site / info.filename, data)
                rows.append(record_line(info.filename, data))
        generated = stage.generated_metadata('demo', wheel_path)
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
        self.check_calls = []

        def checks(venv, snapshot, *, phase='after', runner=None, recorder=None, proven=None):
            self.check_calls.append(phase)
            if phase == 'before':       # the new dependency graph is judged from the proven wheels
                self.assertEqual(sorted(proven), ['demo'])
                self.assertEqual(proven['demo']['sha256'], stage.WHEELS['demo']['sha256'])
            return {'stubbed': True}
        patcher = patch.object(stage, 'checks', checks)
        patcher.start()
        self.addCleanup(patcher.stop)
        umask = os.umask(0o077)
        self.addCleanup(os.umask, umask)
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, [])
        self.addCleanup(lambda: self.assertEqual((signal.pthread_sigmask(signal.SIG_BLOCK, []), signal.sigpending()),
                                                 (mask, set())))

    def install(self, pip=None, *, drained=lambda: True, before=None, live=False, venv=None, records=None):
        venv = venv or self.venv
        pip = pip or FakePip(venv, self.wheel)
        records = [] if records is None else records
        before = before or footprint.snapshot(venv)
        after, proof = stage.install_once(venv, self.wheels, before, drained=drained, recorder=records.append,
                                          live=live, runner=pip, work=self.root)
        return after, proof, records, pip

    def refused_before_pip(self, label, *, venv=None, drained=lambda: True, before=None):
        venv = venv or self.venv
        pip, records = FakePip(venv, self.wheel), []
        with self.assertRaises(stage.Refusal) as caught:
            self.install(pip, venv=venv, drained=drained, before=before, records=records)
        self.assertEqual(str(caught.exception), label)
        self.assertEqual(pip.calls, [])
        self.assertEqual([r['record'] for r in records], ['outcome'])
        self.assertEqual((records[0]['outcome'], records[0]['pip_started'], records[0]['venv_changed']),
                         ('refused', False, False))
        return records[0]

    def test_one_pip_process_moves_only_the_package_and_accounts_for_stray_bytecode(self):
        after, proof, records, pip = self.install()
        self.assertEqual(len(pip.calls), 1)
        argv = pip.calls[0][3:]
        self.assertEqual(argv, stage.pip_arguments(argv[-1]))
        self.assertIn('--require-hashes', argv)
        self.assertEqual([r['record'] for r in records], ['pip_process', 'outcome'])
        self.assertEqual((records[0]['returncode'], records[1]['outcome']), (0, 'installed'))
        # pip read the private, hash-pinned copy, not the operator's wheel directory; the copy is gone afterwards.
        self.assertNotEqual(pip.installed_from.parent, self.wheels)
        self.assertEqual(pip.installed_from.parent.parent, self.root)
        self.assertFalse(pip.installed_from.parent.exists())
        self.assertEqual(proof['uninstall_proof']['demo']['cache_files_removed'], 1)
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

    def test_pip_failure_is_recorded_with_the_measured_venv_and_refused_without_retry(self):
        """DEP-3(c): a failure after pip starts records the venv as measured then, not pip's narration."""
        def half_done():
            os.rename(self.venv / SITE / 'demo', self.venv / SITE / '~emo')
        pip = FakePip(self.venv, self.wheel, returncode=1, during=half_done)
        records = []
        with self.assertRaises(stage.Refusal) as caught:
            self.install(pip, records=records)
        self.assertEqual(str(caught.exception), 'venv_child_failed')
        self.assertEqual((len(pip.calls), records[0]['record'], records[0]['returncode']), (1, 'pip_process', 1))
        outcome = records[1]
        self.assertEqual((outcome['record'], outcome['outcome'], outcome['pip_started'], outcome['stage']),
                         ('outcome', 'refused', True, 'pip'))
        measured = outcome['measured_after_failure']
        self.assertEqual(measured['pip_residue'], [SITE + '/~emo'])
        self.assertEqual(measured['versions'], {'demo': '1.0'})
        self.assertIn(SITE + '/demo/__init__.py', measured['difference']['removed'])

    def test_a_timeout_is_recorded_and_refused_as_this_module_s_refusal(self):
        """DEP-3(a): the bound's TimeoutExpired leaves a pip record, a measured state and one refusal class."""
        def runner(argv, **options):
            raise subprocess.TimeoutExpired(argv, options['timeout'], output=b'Processing demo\n', stderr=b'')
        records = []
        with self.assertRaises(stage.Refusal) as caught:
            self.install(runner, records=records)
        self.assertEqual(str(caught.exception), 'venv_child_timeout')
        self.assertEqual((records[0]['timed_out'], records[0]['returncode'], records[0]['stdout']),
                         (True, None, 'Processing demo\n'))
        self.assertEqual(records[1]['measured_after_failure']['versions'], {'demo': '1.0'})

    def test_footprint_refusals_leave_as_this_module_s_refusal(self):
        """DEP-3(b): one refusal class for install_once and calibrate (the act and __main__ catch stage.Refusal)."""
        before = footprint.snapshot(self.venv)
        write(self.venv / SITE / 'other/__init__.py', b'changed\n')
        record = self.refused_before_pip('venv_unchanged_since_its_snapshot', before=before)
        self.assertEqual(record['label'], 'venv_unchanged_since_its_snapshot')

    def test_units_must_be_drained_before_immediately_before_and_after_the_one_process(self):
        """DEP-4: a unit that starts after the first check is seen by the one immediately before the child."""
        self.refused_before_pip('owned_units_drained_before_pip', drained=lambda: False)
        states = iter([True, False])
        self.refused_before_pip('owned_units_drained_immediately_before_pip', drained=lambda: next(states))
        order = []

        def drained():
            order.append('drained')
            return True
        pip = FakePip(self.venv, self.wheel, during=lambda: order.append('pip'))
        self.install(pip, drained=drained)
        self.assertEqual(order, ['drained', 'drained', 'pip', 'drained'])
        states = iter([True, True, False])
        pip = FakePip(fake_venv(self.root / 'third'), self.wheel)
        with self.assertRaises(stage.Refusal) as caught:
            self.install(pip, venv=pip.venv, drained=lambda: next(states))
        self.assertEqual((str(caught.exception), len(pip.calls)), ('owned_units_drained_after_pip', 1))

    def test_a_changed_venv_or_wheel_refuses_before_pip(self):
        before = footprint.snapshot(self.venv)
        write(self.venv / SITE / 'other/__init__.py', b'changed\n')
        self.refused_before_pip('venv_unchanged_since_its_snapshot', before=before)
        write(self.venv / SITE / 'other/__init__.py', b'OTHER = 1\n')
        with zipfile.ZipFile(self.wheel, 'a') as archive:
            archive.writestr('demo/late.py', b'x')
        self.refused_before_pip('exact_official_wheel_bytes')

    def test_pip_residue_or_an_incomplete_population_refuses_before_pip(self):
        """DEP-1: a killed pip's stash, or a RECORD naming files that are gone, refuses before any pip run."""
        venv = fake_venv(self.root / 'killed')
        site = venv / SITE
        os.rename(site / 'demo', site / '~emo')
        os.rename(site / 'demo-1.0.dist-info', site / '~emo-1.0.dist-info')
        self.refused_before_pip('interrupted_pip_residue_in_the_venv', venv=venv)
        venv = fake_venv(self.root / 'partial')
        (venv / SITE / 'demo/old_only.py').unlink()
        self.refused_before_pip('complete_installed_record_population', venv=venv)

    def test_pip_uninstall_must_provably_empty_the_package_before_pip_runs(self):
        """DEP-2: anything pip's RECORD-driven uninstall would leave under the package refuses BEFORE pip."""
        strays = {'opt1_bytecode': 'demo/__pycache__/__init__.cpython-312.opt-1.pyc',
                  'other_interpreter_bytecode': 'demo/__pycache__/old_only.cpython-311.pyc',
                  'unrecorded_file': 'demo/notes.txt', 'unrecorded_dist_info_file': 'demo-1.0.dist-info/extra'}
        for name, relative in strays.items():
            with self.subTest(stray=name):
                venv = fake_venv(self.root / name)
                write(venv / SITE / relative, b'stray')
                self.refused_before_pip('pip_uninstall_would_leave_package_objects', venv=venv)
        venv = fake_venv(self.root / 'new_dist_info_file')
        write(venv / SITE / 'demo-1.1.dist-info', b'')     # a FILE named like the new dist-info (exp7's trigger)
        self.refused_before_pip('pip_uninstall_would_leave_package_objects', venv=venv)
        # The cpython-312 cache file of a RECORDed module is pip's to remove: admitted (fake_venv carries one).
        self.install()

    def test_wheels_must_sit_in_a_private_directory_and_pip_reads_only_proven_copies(self):
        """DEP-6: an open wheel directory refuses; a swap in the operator's directory during pip changes nothing."""
        self.wheels.chmod(0o777)
        self.refused_before_pip('private_wheel_directory')
        self.wheels.chmod(0o700)
        official = self.wheel.read_bytes()

        def swap():                     # a second writer replaces the operator's wheel while pip runs
            self.wheel.write_bytes(official.replace(b'NEW = 1', b'BAD = 1'))
        pip = FakePip(self.venv, self.wheel, during=swap)
        with self.assertRaises(stage.Refusal) as caught:
            self.install(pip)
        # pip installed the proven copy; the swapped original is then refused by the re-proof, nothing else moved.
        self.assertEqual((self.venv / SITE / 'demo/__init__.py').read_bytes(), b'NEW = 1\n')
        self.assertEqual(str(caught.exception), 'exact_official_wheel_bytes')
        self.wheel.write_bytes(official)
        # A copy whose bytes do not match its pin is refused by pip's own hash check, before any uninstall.
        venv = fake_venv(self.root / 'tampered-copy')
        copies = stage.private_copies(stage.wheels(self.wheels), self.root)
        target, _, requirements = copies
        (target / self.wheel.name).write_bytes(b'not the wheel')
        result = FakePip(venv, self.wheel)(['python', '-I', '-B', *stage.pip_arguments(requirements)], umask=0o022)
        self.assertEqual(result.returncode, 1)
        self.assertTrue((venv / SITE / 'demo-1.0.dist-info').is_dir())

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
            for name in ('venv-live-before.json', 'venv-copy-before.json', 'venv-copy-after.json', 'pip-process.json',
                         'outcome.json', 'calibration-receipt.json'):
                self.assertEqual(oct((self.root / 'calibration' / name).stat().st_mode & 0o777), '0o600')
            with self.assertRaises(stage.Refusal):
                stage.calibrate(live, self.wheels, self.root / 'calibration-2', runner=FakePip(live, self.wheel))
            fresh = self.root / 'copy-3'
            shutil.copytree(live, fresh, symlinks=True)
            touch_live = FakePip(fresh, self.wheel, tamper=lambda site: write(live / 'pyvenv.cfg', b'touched\n'))
            with self.assertRaises(stage.Refusal) as caught:     # DEP-3(b): one refusal class
                stage.calibrate(fresh, self.wheels, self.root / 'calibration-3', runner=touch_live)
            self.assertEqual(str(caught.exception), 'live_venv_touched_during_calibration')

    def test_calibration_refuses_a_copy_that_is_not_the_live_venv_path_by_path(self):
        """DEP-5: equality is the full footprint (bytes, modes, owners, links), required, printed and kept."""
        live = fake_venv(self.root / 'live-root')
        with patch.object(stage, 'VENV', live):
            for name, change in (('same_size_other_bytes', lambda copy: write(copy / SITE / 'other/__init__.py',
                                                                              b'OTHER = 2\n')),
                                 ('mode', lambda copy: (copy / SITE / 'other/__init__.py').chmod(0o600)),
                                 ('missing_stray', lambda copy: (copy / SITE / 'other/__pycache__/'
                                                                 '__init__.cpython-312.pyc').unlink())):
                with self.subTest(change=name):
                    copy = self.root / ('copy-' + name)
                    shutil.copytree(live, copy, symlinks=True)
                    change(copy)
                    pip = FakePip(copy, self.wheel)
                    with self.assertRaises(stage.Refusal) as caught:
                        stage.calibrate(copy, self.wheels, self.root / ('calibration-' + name), runner=pip)
                    self.assertEqual(str(caught.exception), 'calibration_copy_equals_the_live_venv')
                    self.assertEqual(pip.calls, [])
                    self.assertTrue((self.root / ('calibration-' + name) / 'venv-live-before.json').exists())
                    self.assertTrue((self.root / ('calibration-' + name) / 'venv-copy-difference.json').exists())
            copy = self.root / 'copy-printed'
            shutil.copytree(live, copy, symlinks=True)
            argv = ['calibrate', '--venv-copy', str(copy), '--wheels', str(self.wheels), '--output',
                    str(self.root / 'calibration-printed')]
            real = stage.calibrate
            with patch.object(stage, 'calibrate', lambda c, w, o: real(c, w, o, runner=FakePip(copy, self.wheel))), \
                    redirect_stdout(io.StringIO()) as output:
                self.assertEqual(stage.main(argv), 0)
            self.assertTrue(json.loads(output.getvalue())['copy_before_matches_live'])

    def test_calibration_refuses_an_ancestor_of_the_live_venv_before_reading_anything(self):
        """DEP-7: the copy guard is two-way and requires a venv root; nothing is snapshotted before it passes."""
        tree = self.root / 'fake-rebuild'
        tree.mkdir()
        write(tree / '.env', b'DUMMY=not-a-secret\n', 0o600)
        live = fake_venv(tree)            # tree/venv plays the live venv
        with patch.object(stage, 'VENV', live):
            for copy, label in ((tree, 'calibration_runs_on_a_copy'), (live / SITE, 'calibration_runs_on_a_copy'),
                                (self.root, 'calibration_runs_on_a_copy')):
                with self.subTest(copy=copy):
                    output = self.root / ('calibration-' + copy.name)
                    with self.assertRaises(stage.Refusal) as caught:
                        stage.calibrate(copy, self.wheels, output, runner=FakePip(copy, self.wheel))
                    self.assertEqual(str(caught.exception), label)
                    self.assertFalse(output.exists())
            not_a_venv = self.root / 'plain'
            (not_a_venv / 'lib').mkdir(parents=True)
            with self.assertRaises(stage.Refusal) as caught:
                stage.calibrate(not_a_venv, self.wheels, self.root / 'calibration-plain',
                                runner=FakePip(not_a_venv, self.wheel))
            self.assertEqual(str(caught.exception), 'calibration_copy_is_a_venv_root')
            self.assertFalse((self.root / 'calibration-plain').exists())


    def test_dep2_r1_a_population_the_stage_was_not_calibrated_on_refuses_before_pip(self):
        """DEP2-R1(A): one extra distribution (a later `pip install x`), or a pip other than the one the uninstall proof
        and the generated metadata model, is in the before-snapshot: refused before any pip process. transition()
        used to find it only AFTER pip had moved every package, and D2 then leaves no way forward."""
        venv = fake_venv(self.root / 'extra')
        meta = b'Metadata-Version: 2.1\nName: lens-extra\nVersion: 1.0\n'
        write(venv / SITE / 'lens_extra-1.0.dist-info/METADATA', meta)
        write(venv / SITE / 'lens_extra-1.0.dist-info/RECORD', record_text([
            record_line('lens_extra-1.0.dist-info/METADATA', meta), ['lens_extra-1.0.dist-info/RECORD', '', '']]))
        record = self.refused_before_pip('calibrated_population', venv=venv)
        self.assertEqual(record['stage'], 'preconditions')
        venv = fake_venv(self.root / 'other-pip')
        write(venv / SITE / 'pip-24.0.dist-info/METADATA', b'Metadata-Version: 2.1\nName: pip\nVersion: 23.3\n')
        self.refused_before_pip('calibrated_population', venv=venv)
        self.assertEqual(self.check_calls, [])          # refused before the venv's own checks even ran

    def test_dep2_r1_the_venv_s_own_checks_run_before_pip_and_refuse_with_nothing_changed(self):
        """DEP2-R1(B): what the venv's checks refuse (a broken import, a dependency graph pip check would refuse) is
        refused BEFORE pip: the checks run first, on the old versions and the new graph, with nothing moved."""
        order = []

        def checks(venv, snapshot, *, phase='after', runner=None, recorder=None, proven=None):
            order.append('checks_' + phase)
            if phase == 'before' and getattr(self, 'broken', False):
                raise stage.Refusal('new_dependency_graph_before_pip')
            return {'stubbed': True}
        with patch.object(stage, 'checks', checks):
            self.broken = True
            self.refused_before_pip('new_dependency_graph_before_pip')
            self.broken = False
            pip = FakePip(self.venv, self.wheel, during=lambda: order.append('pip'))
            self.install(pip)
        self.assertEqual(order, ['checks_before', 'checks_before', 'pip', 'checks_after'])

    def test_dep2_r2_a_signal_before_pip_refuses_with_nothing_changed(self):
        """DEP2-R2: SIGTERM, SIGINT and SIGHUP are blocked for the whole stage; one taken at a checkpoint before pip
        refuses (interrupted_by_<name>) with nothing changed, and it is in the outcome record."""
        for name in ROUTED_SIGNALS:
            with self.subTest(signal=name):
                venv = fake_venv(self.root / ('before-' + name))
                calls = {'n': 0}

                def drained(name=name, calls=calls):
                    calls['n'] += 1
                    if calls['n'] == 1:
                        os.kill(os.getpid(), getattr(signal, name))
                        settle()            # no handler, no KeyboardInterrupt: it waits for the checkpoint
                    return True
                record = self.refused_before_pip('interrupted_by_' + name, venv=venv, drained=drained)
                self.assertEqual((record['signals_received'], record['signal_records'][0]['stage']),
                                 ([name], 'checks_before_pip'))

    def test_dep2_r2_a_signal_during_pip_is_recorded_and_the_stage_runs_to_its_end(self):
        """DEP2-R2 (r2_signals): a SIGTERM to the stage alone killed it with no record and left pip running on; a
        SIGINT left no pip_process record. Blocked, they change nothing: pip ends, every check runs, both records
        are written, and the outcome and the proof carry the signals for judgement."""
        def signals():
            os.kill(os.getpid(), signal.SIGTERM)
            os.kill(os.getpid(), signal.SIGINT)
            settle()
        after, proof, records, pip = self.install(FakePip(self.venv, self.wheel, during=signals))
        self.assertEqual([r['record'] for r in records], ['pip_process', 'outcome'])
        self.assertEqual((records[0]['returncode'], records[1]['outcome']), (0, 'installed'))
        self.assertEqual(sorted(records[1]['signals_received']), ['SIGINT', 'SIGTERM'])
        self.assertEqual({row['stage'] for row in records[1]['signal_records']}, {'after_pip'})
        self.assertEqual(sorted(proof['signals_received']), ['SIGINT', 'SIGTERM'])
        self.assertEqual(self.check_calls, ['before', 'after'])
        self.assertEqual(after['census']['distributions']['demo'], '1.1')

    def test_dep2_r2_a_child_that_cannot_start_still_leaves_its_record(self):
        def runner(argv, **options):
            raise FileNotFoundError(2, 'No such file or directory')
        records = []
        with self.assertRaises(FileNotFoundError):
            self.install(runner, records=records)
        self.assertEqual([r['record'] for r in records], ['pip_process', 'outcome'])
        self.assertEqual((records[0]['start_failure'], records[0]['returncode']), ('FileNotFoundError', None))
        self.assertEqual((records[1]['stage'], records[1]['label'], records[1]['pip_started']),
                         ('pip', 'FileNotFoundError', True))

    def test_dep2_r2_every_venv_child_starts_blocked_and_dies_with_the_stage(self):
        """DEP2-R2: a venv child inherits the stage's blocked mask (only SIGKILL stops it) and is SIGKILLed by the
        kernel when the stage process dies (PR_SET_PDEATHSIG): pip never runs on after the stage is gone."""
        venv = self.root / 'real-venv'
        (venv / 'bin').mkdir(parents=True)
        (venv / 'bin/python').symlink_to(os.path.realpath(sys.executable))
        pid_file = self.root / 'child.pid'
        stage_code = ('import os, sys; sys.path.insert(0, sys.argv[1]); from ops import rebuild_dependency_stage as s;'
                      ' os.umask(0o077); s.block_signals();'
                      ' s.interpreter(sys.argv[2], ["-c", "import os,sys,time; open(sys.argv[1], \'w\').write('
                      'str(os.getpid())); time.sleep(60)", sys.argv[3]], timeout=90)')
        parent = subprocess.Popen([sys.executable, '-I', '-B', '-c', stage_code, str(Path(stage.__file__).parents[1]),
                                   str(venv), str(pid_file)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            for _ in range(400):
                if pid_file.exists() and pid_file.read_text():
                    break
                time.sleep(0.025)
            child = int(pid_file.read_text())
            self.addCleanup(lambda: alive(child) and os.kill(child, signal.SIGKILL))    # never left sleeping
            status = (Path('/proc') / str(child) / 'status').read_text()
            blocked = int(next(line for line in status.splitlines() if line.startswith('SigBlk:')).split()[1], 16)
            self.assertTrue(all(blocked >> (getattr(signal, name) - 1) & 1 for name in ROUTED_SIGNALS))
            os.kill(child, signal.SIGTERM)
            time.sleep(0.2)
            self.assertTrue(alive(child))                  # blocked: SIGTERM does not stop it
            parent.kill()                                  # the stage dies, as only SIGKILL can make it
            parent.wait(timeout=30)
            for _ in range(200):
                if not alive(child):
                    break
                time.sleep(0.025)
            self.assertFalse(alive(child))                 # ... and its child with it
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait()
            parent.stderr.close()

    def test_dep2_r2_calibrate_exits_2_when_a_signal_arrived_during_the_stage(self):
        live = fake_venv(self.root / 'live-root')
        copy = self.root / 'copy-signalled'
        shutil.copytree(live, copy, symlinks=True)
        argv = ['calibrate', '--venv-copy', str(copy), '--wheels', str(self.wheels), '--output',
                str(self.root / 'calibration-signalled')]
        real = stage.calibrate
        pip = FakePip(copy, self.wheel, during=lambda: (os.kill(os.getpid(), signal.SIGHUP), settle()))
        with patch.object(stage, 'VENV', live), \
                patch.object(stage, 'calibrate', lambda c, w, o: real(c, w, o, runner=pip)), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(stage.main(argv), 2)
        self.assertEqual(json.loads(output.getvalue())['signals_received'], ['SIGHUP'])


def alive(pid):
    try:
        state = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()[0]
    except OSError:
        return False
    return state != 'Z'


class ChecksTests(unittest.TestCase):
    def test_dep2_r3_every_check_child_is_recorded_under_its_own_name_and_label(self):
        """DEP2-R3 (r3): the check children ran without the recorder and a failure read 'venv_child_failed', the label
        of a failed pip install, while pip check's exit 1 made its own 'pip_check' label unreachable. Each child now
        leaves its record (argv, return code, output) under its own name and refuses under its own label."""
        venv = Path('/nonexistent/venv')
        snapshot = {'files': {SITE + '/certifi/cacert.pem': {'sha256': 'c' * 64}},
                    'census': {'distributions': {'pillow': '13.0.0'}}}

        def report(index):
            site = venv / SITE
            version = {package: pair[index] for package, pair in stage.TRANSITIONS.items()}
            return {'pypdf': version['pypdf'], 'pypdf_file': str(site / 'pypdf/__init__.py'), 'pdf_roundtrip': True,
                    'filelock': version['filelock'], 'filelock_file': str(site / 'filelock/__init__.py'),
                    'filelock_api': True, 'msgpack': [int(x) for x in version['msgpack'].split('.')],
                    'msgpack_extension': str(site / stage.NATIVE['msgpack'][0]), 'msgpack_c_packer': True,
                    'msgpack_roundtrip': True,
                    'cachecontrol_file_cache': str(site / 'cachecontrol/caches/file_cache.py'),
                    'certifi_ca_sha256': 'c' * 64, 'pillow': '13.0.0', 'png_roundtrip': True}
        broken = b'tqdm 4.70.1 requires lens-missing-dependency, which is not installed.\n'
        proven = {package: {'requires': []} for package in stage.TRANSITIONS}
        clean_graph = json.dumps({'distributions': stage.DISTRIBUTIONS, 'parsing_problems': False, 'missing': {},
                                  'conflicting': {}, 'installed': {p: pair[0] for p, pair
                                                                   in stage.TRANSITIONS.items()}}).encode()

        def dependency_child(argv):
            return argv[-1] == 'check' or argv[3:5] == ['-c', stage.GRAPH_PROGRAM]

        def runner(program, check):
            def run(argv, **options):
                if dependency_child(argv):
                    return subprocess.CompletedProcess(argv, *check)
                return subprocess.CompletedProcess(argv, *program)
            return run
        umask = os.umask(0o077)
        try:
            for phase, index, names, labels, passing in (
                    ('after', 1, ('check_program', 'pip_check'),
                     ('installed_versions_locations_and_round_trips', 'pip_check'),
                     b'No broken requirements found.\n'),
                    ('before', 0, ('check_program_before_pip', 'new_dependency_graph_before_pip'),
                     ('versions_locations_and_round_trips_before_pip', 'new_dependency_graph_before_pip'),
                     clean_graph)):
                good = (0, json.dumps(report(index)).encode(), b'')
                with self.subTest(phase=phase, child='dependency_check_exit_1'):
                    records = []
                    with self.assertRaises(stage.Refusal) as caught:
                        stage.checks(venv, snapshot, phase=phase, runner=runner(good, (1, broken, b'')),
                                     recorder=records.append, proven=proven)
                    self.assertEqual(str(caught.exception), labels[1])
                    self.assertEqual([(r['record'], r['returncode']) for r in records], [(names[0], 0), (names[1], 1)])
                    self.assertIn('lens-missing-dependency', records[1]['stdout'])
                    # After pip, `pip check` itself; before pip, the new graph through pip's own check code.
                    self.assertTrue(records[1]['argv'][-1] == 'check' if phase == 'after'
                                    else records[1]['argv'][4] == stage.GRAPH_PROGRAM)
                with self.subTest(phase=phase, child='import_error'):
                    records = []
                    failing = (1, b'', b'ModuleNotFoundError: No module named PIL\n')
                    with self.assertRaises(stage.Refusal) as caught:
                        stage.checks(venv, snapshot, phase=phase, runner=runner(failing, (0, b'', b'')),
                                     recorder=records.append, proven=proven)
                    self.assertEqual(str(caught.exception), labels[0])
                    self.assertEqual([(r['record'], r['returncode']) for r in records], [(names[0], 1)])
                    self.assertIn('No module named PIL', records[0]['stderr'])
                with self.subTest(phase=phase, child='both_pass'):
                    records = []
                    stage.checks(venv, snapshot, phase=phase, runner=runner(good, (0, passing, b'')),
                                 recorder=records.append, proven=proven)
                    self.assertEqual([r['record'] for r in records], list(names))
            # The new versions are not the old ones: an 'after' report fails the 'before' comparison and vice versa.
            with self.assertRaises(stage.Refusal):
                stage.checks(venv, snapshot, phase='before', proven=proven,
                             runner=runner((0, json.dumps(report(1)).encode(), b''), (0, clean_graph, b'')))
            # Before pip the wheels are required: the new graph is judged from their metadata.
            with self.assertRaises(stage.Refusal) as caught:
                stage.checks(venv, snapshot, phase='before', runner=runner(good, (0, clean_graph, b'')))
            self.assertEqual(str(caught.exception), 'checks_phase')
        finally:
            os.umask(umask)

    def test_r3_dep_1_the_new_graph_report_must_describe_this_venv_and_find_nothing_broken(self):
        """R3-DEP-1: dependency_graph hands the child the NEW versions and the proven wheels' Requires-Dist, and
        refuses unless the report names the calibrated population with the OLD versions installed and finds nothing
        missing, conflicting or unparsable."""
        venv = Path('/nonexistent/venv')
        proven = {package: {'requires': ['typing_extensions>=4.0; python_version < "3.11"'] if package == 'pypdf'
                            else []} for package in stage.TRANSITIONS}
        clean = {'distributions': stage.DISTRIBUTIONS, 'parsing_problems': False, 'missing': {}, 'conflicting': {},
                 'installed': {p: pair[0] for p, pair in stage.TRANSITIONS.items()}}
        seen = []

        def runner(report):
            def run(argv, **options):
                seen.append(argv)
                return subprocess.CompletedProcess(argv, 0, report if isinstance(report, bytes)
                                                   else json.dumps(report).encode(), b'')
            return run
        umask = os.umask(0o077)
        try:
            records = []
            self.assertEqual(stage.dependency_graph(venv, proven, runner=runner(clean), recorder=records.append),
                             clean)
            self.assertEqual([r['record'] for r in records], ['new_dependency_graph_before_pip'])
            self.assertEqual(seen[-1][1:5], ['-I', '-B', '-c', stage.GRAPH_PROGRAM])
            self.assertEqual(json.loads(seen[-1][5]), {p: {'version': pair[1], 'requires': proven[p]['requires']}
                                                       for p, pair in stage.TRANSITIONS.items()})
            for change in ({'conflicting': {'tqdm': ['pypdf<6.21.4 (new graph has 6.21.4)']}},
                           {'missing': {'pypdf': ['typing-extensions>=4.0']}}, {'parsing_problems': True},
                           {'installed': dict(clean['installed'], pypdf='6.21.4')},
                           {'distributions': stage.DISTRIBUTIONS + 1}):
                with self.subTest(change=change), self.assertRaises(stage.Refusal) as caught:
                    stage.dependency_graph(venv, proven, runner=runner(dict(clean, **change)))
                self.assertEqual(str(caught.exception), 'new_dependency_graph_before_pip')
            with self.assertRaises(stage.Refusal):
                stage.dependency_graph(venv, proven, runner=runner(b'not json'))
        finally:
            os.umask(umask)

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


def pip_package():
    """The test interpreter's own pip package (GRAPH_PROGRAM runs pip's check code inside the venv)."""
    spec = importlib.util.find_spec('pip')
    return Path(spec.origin).parent if spec is not None and spec.origin else None


def graph_venv(root, distributions):
    """A venv the real interpreter runs (pyvenv.cfg, bin/python -> the interpreter) holding exactly the given
    distributions {name: (version, [Requires-Dist, ...])}, with the test interpreter's pip linked in."""
    venv = root / 'graph-venv'
    site = venv / SITE
    site.mkdir(parents=True)
    (venv / 'bin').mkdir()
    interpreter = Path(os.path.realpath(sys.executable))
    (venv / 'bin/python').symlink_to(interpreter)
    write(venv / 'pyvenv.cfg', ('home = %s\ninclude-system-site-packages = false\n' % interpreter.parent).encode())
    (site / 'pip').symlink_to(pip_package(), target_is_directory=True)
    for name, (version, requires) in distributions.items():
        dist = site / (name + '-' + version + '.dist-info')
        meta = 'Metadata-Version: 2.1\nName: %s\nVersion: %s\n' % (name, version)
        write(dist / 'METADATA', (meta + ''.join('Requires-Dist: %s\n' % r for r in requires)).encode())
        write(dist / 'RECORD', b'')
    return venv


@unittest.skipIf(pip_package() is None, 'pip is not importable by the test interpreter')
class NewDependencyGraphTests(unittest.TestCase):
    """R3-DEP-1 with pip's REAL check code (pip._internal.operations.check, what `pip check` runs) over fabricated
    distributions: the pre-pip `pip check` judged the OLD graph, so a bound only the NEW versions violate passed it
    and was refused only by the post-pip `pip check`, with all three packages moved (D2: no way back)."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        for name, value in {'TRANSITIONS': {'demo': ('1.0', '1.1')}, 'DISTRIBUTIONS': 2}.items():
            patcher = patch.object(stage, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        umask = os.umask(0o077)
        self.addCleanup(os.umask, umask)

    def judge(self, name, distributions, requires=()):
        venv = graph_venv(self.root / name, distributions)
        records = []
        try:
            report = stage.dependency_graph(venv, {'demo': {'requires': list(requires)}}, recorder=records.append)
        except stage.Refusal as refusal:
            return str(refusal), records, venv
        return report, records, venv

    def old_graph_pip_check(self, venv):
        """The check the stage ran before pip until round 4: `pip check` on the venv as it is (the OLD graph)."""
        return subprocess.run([str(venv / 'bin/python'), '-I', '-B', *stage.PIP_CHECK], capture_output=True,
                              env=stage.child_environment(), cwd=str(venv), timeout=120).returncode

    def test_r3_dep_1_a_bound_only_the_new_version_violates_refuses_before_pip(self):
        verdict, records, venv = self.judge('upper-bound', {'demo': ('1.0', []), 'other': ('2.0', ['demo<1.1'])})
        self.assertEqual(verdict, 'new_dependency_graph_before_pip')
        self.assertEqual(json.loads(records[0]['stdout'])['conflicting'], {'other': ['demo<1.1 (new graph has 1.1)']})
        self.assertEqual(self.old_graph_pip_check(venv), 0)      # the old check passed this venv: the finding

    def test_r3_dep_1_a_requirement_the_transition_fixes_no_longer_refuses(self):
        verdict, records, venv = self.judge('fixed', {'demo': ('1.0', []), 'other': ('2.0', ['demo>=1.1'])})
        self.assertEqual((verdict['conflicting'], verdict['missing'], verdict['installed']), ({}, {}, {'demo': '1.0'}))
        self.assertEqual(self.old_graph_pip_check(venv), 1)      # the old check refused it although pip fixes it

    def test_r3_dep_1_the_new_wheels_requirements_are_judged_with_pip_s_marker_rules(self):
        base = {'demo': ('1.0', []), 'other': ('2.0', [])}
        cases = {'applicable_missing': (['missing-thing>=1; python_version >= "3"'], 'new_dependency_graph_before_pip'),
                 'applicable_conflict': (['other>=3; python_version >= "3"'], 'new_dependency_graph_before_pip'),
                 'applicable_satisfied': (['other>=2.0; python_version >= "3"'], None),
                 'extra_only_or_other_python': (['missing-thing; extra == "full"', 'other>=3; python_version < "3"'],
                                                None)}
        for name, (requires, label) in cases.items():
            with self.subTest(case=name):
                verdict, records, _ = self.judge(name, base, requires)
                if label is None:
                    self.assertEqual((verdict['missing'], verdict['conflicting']), ({}, {}))
                else:
                    self.assertEqual(verdict, label)
                    report = json.loads(records[0]['stdout'])
                    self.assertTrue(report['missing'] or report['conflicting'])

    def test_r3_dep_1_a_venv_that_is_not_the_calibrated_population_refuses(self):
        verdict, _, _ = self.judge('not-the-old-version', {'demo': ('0.9', []), 'other': ('2.0', [])})
        self.assertEqual(verdict, 'new_dependency_graph_before_pip')
        verdict, _, _ = self.judge('extra-distribution', {'demo': ('1.0', []), 'other': ('2.0', []),
                                                          'third': ('1.0', [])})
        self.assertEqual(verdict, 'new_dependency_graph_before_pip')


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
