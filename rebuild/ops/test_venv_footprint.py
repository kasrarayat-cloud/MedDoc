"""Offline controls for the exact venv footprint (interpretation 67, D1)."""
import base64
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from ops import venv_footprint as footprint


def record_row(root, name):
    data = (root / name).read_bytes()
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
    return '%s,sha256=%s,%d' % (name, digest, len(data))


def fake_venv(root):
    """A small venv: two distributions, recorded bytecode, one unrecorded .pyc, a link and a script."""
    venv = root / 'venv'
    site = venv / footprint.SITE
    (site / 'demo/__pycache__').mkdir(parents=True)
    (site / 'other').mkdir()
    (venv / 'bin').mkdir()
    (venv / 'lib64').symlink_to('lib')
    (venv / 'bin/python').symlink_to('/usr/bin/python3')
    (venv / 'pyvenv.cfg').write_text('home = /usr/bin\n')
    (site / 'demo/__init__.py').write_text('VALUE = 1\n')
    (site / 'demo/__pycache__/__init__.cpython-312.pyc').write_bytes(b'recorded bytecode')
    (site / 'other/__init__.py').write_text('OTHER = 2\n')
    (site / 'other/stray.py').write_text('STRAY = 3\n')
    (site / 'other/__pycache__').mkdir()
    (site / 'other/__pycache__/stray.cpython-312.pyc').write_bytes(b'unrecorded bytecode')
    for name, version, files in (('demo', '1.0', ['demo/__init__.py', 'demo/__pycache__/__init__.cpython-312.pyc']),
                                 ('Other_Package', '2.5', ['other/__init__.py', 'other/stray.py'])):
        dist = site / (name + '-' + version + '.dist-info')
        dist.mkdir()
        (dist / 'METADATA').write_text('Metadata-Version: 2.1\nName: %s\nVersion: %s\n' % (name, version))
        rows = [record_row(site, f) for f in files]
        rows.append(dist.name + '/RECORD,,')
        (dist / 'RECORD').write_text('\n'.join(rows) + '\n')
    return venv


class FootprintTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()
        self.venv = fake_venv(self.root)

    def tearDown(self):
        self.directory.cleanup()

    def test_inventory_records_every_object_without_following_links(self):
        files = footprint.inventory(self.venv)
        self.assertEqual(files['lib64'], {**files['lib64'], 'kind': 'symlink', 'target': 'lib'})
        self.assertEqual(files['bin/python']['target'], '/usr/bin/python3')
        row = files[footprint.SITE + '/demo/__init__.py']
        self.assertEqual((row['kind'], row['bytes'], row['sha256']),
                         ('file', 10, hashlib.sha256(b'VALUE = 1\n').hexdigest()))
        self.assertNotIn('lib64/python3.12', files)  # the linked directory is not walked twice

    def test_census_names_distributions_and_only_unrecorded_bytecode(self):
        value = footprint.snapshot(self.venv)
        facts = value['census']
        self.assertEqual(facts['distributions'], {'demo': '1.0', 'other-package': '2.5'})
        self.assertEqual(facts['bytecode_files'], 2)
        self.assertEqual(facts['unrecorded_bytecode'], [footprint.SITE + '/other/__pycache__/stray.cpython-312.pyc'])
        self.assertEqual(footprint.summary(value)['unrecorded_bytecode'], 1)

    def test_every_kind_of_change_breaks_equality(self):
        before = footprint.snapshot(self.venv)
        footprint.require_exact(before, footprint.snapshot(self.venv))

        def replace_same_bytes(venv, site):
            # Same bytes, new inode: a replaced file is a changed file.
            (site / 'tmp').write_bytes((site / 'demo/__init__.py').read_bytes())
            os.replace(site / 'tmp', site / 'demo/__init__.py')

        def retarget(venv, site):
            (venv / 'lib64').unlink()
            (venv / 'lib64').symlink_to('lib/python3.12')
        changes = {
            'bytes': lambda venv, site: (site / 'other/__init__.py').write_text('OTHER = 3\n'),
            'new_bytecode': lambda venv, site: (site / 'demo/__pycache__/new.cpython-312.pyc').write_bytes(b'new'),
            # Toggle a bit rather than set a mode: the starting mode follows the process umask.
            'mode': lambda venv, site: os.chmod(site / 'other/stray.py',
                                                (site / 'other/stray.py').stat().st_mode & 0o777 ^ 0o100),
            'link_target': retarget,
            'same_bytes_new_inode': replace_same_bytes,
            'removed_stray': lambda venv, site: (site / 'other/__pycache__/stray.cpython-312.pyc').unlink()}
        for name, change in changes.items():
            with self.subTest(change=name), tempfile.TemporaryDirectory() as other:
                venv = fake_venv(Path(other).resolve())
                before = footprint.snapshot(venv)
                change(venv, venv / footprint.SITE)
                after = footprint.snapshot(venv)
                with self.assertRaises(footprint.Refusal):
                    footprint.require_exact(before, after)
                difference = footprint.difference(before['files'], after['files'])
                self.assertTrue(any(difference['counts'].values()))

    def test_a_tampered_snapshot_is_not_comparable(self):
        before = footprint.snapshot(self.venv)
        forged = dict(before, files=dict(before['files']))
        forged['files'].pop('pyvenv.cfg')
        with self.assertRaises(footprint.Refusal):
            footprint.require_exact(before, forged)

    def test_pip_stash_left_by_a_killed_pip_is_residue_never_a_distribution(self):
        """DEP-1: a killed pip leaves ~demo and ~emo-1.0.dist-info (its METADATA still says demo 1.0)."""
        site = self.venv / footprint.SITE
        os.rename(site / 'demo', site / '~emo')
        os.rename(site / 'demo-1.0.dist-info', site / '~emo-1.0.dist-info')
        facts = footprint.snapshot(self.venv)['census']
        self.assertEqual(facts['distributions'], {'other-package': '2.5'})
        self.assertEqual(facts['pip_residue'], [footprint.SITE + '/~emo', footprint.SITE + '/~emo-1.0.dist-info'])
        self.assertEqual(footprint.summary(footprint.snapshot(self.venv))['pip_residue'], 2)
        # With the new version installed beside the stash, the census no longer refuses unique_distribution.
        (site / 'demo-1.1.dist-info').mkdir()
        (site / 'demo-1.1.dist-info/METADATA').write_text('Metadata-Version: 2.1\nName: demo\nVersion: 1.1\n')
        (site / 'demo-1.1.dist-info/RECORD').write_text('demo-1.1.dist-info/RECORD,,\n')
        facts = footprint.snapshot(self.venv)['census']
        self.assertEqual(facts['distributions'], {'demo': '1.1', 'other-package': '2.5'})
        self.assertEqual(len(facts['pip_residue']), 2)

    def test_record_paths_are_venv_relative_and_include_the_record(self):
        files = footprint.inventory(self.venv)
        paths = footprint.record_paths(self.venv, files, footprint.SITE + '/demo-1.0.dist-info')
        self.assertEqual(paths, {footprint.SITE + '/demo/__init__.py',
                                 footprint.SITE + '/demo/__pycache__/__init__.cpython-312.pyc',
                                 footprint.SITE + '/demo-1.0.dist-info/RECORD'})

    def test_census_reads_only_what_the_footprint_measured(self):
        files = footprint.inventory(self.venv)
        metadata = self.venv / footprint.SITE / 'demo-1.0.dist-info/METADATA'
        metadata.write_text('Metadata-Version: 2.1\nName: demo\nVersion: 9.9\n')
        with self.assertRaises(footprint.Refusal):
            footprint.census(self.venv, files)

    def test_a_record_row_leaving_the_venv_refuses(self):
        record = self.venv / footprint.SITE / 'demo-1.0.dist-info/RECORD'
        record.write_text(record.read_text() + '../../../../escape.txt,,\n')
        with self.assertRaises(footprint.Refusal):
            footprint.snapshot(self.venv)

    def test_a_directory_the_operator_cannot_list_refuses_instead_of_vanishing(self):
        """The preflight-truth lens's latent: os.walk skipped unlistable directories without a word."""
        cache = self.venv / footprint.SITE / 'demo/__pycache__'
        os.chmod(cache, 0o000)
        try:
            with self.assertRaises(footprint.Refusal) as caught:
                footprint.snapshot(self.venv)
            self.assertEqual(str(caught.exception), 'unlistable_venv_directory')
        finally:
            os.chmod(cache, 0o755)

    def test_a_venv_path_through_a_link_refuses(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.venv)
        with self.assertRaises(footprint.Refusal):
            footprint.inventory(alias)


class RequirementTests(unittest.TestCase):
    def test_exact_pins_are_read_and_normalized(self):
        text = '# comment\n\nCacheControl==0.14.4\npypdf==6.21.4\nPython_Dotenv==1.2.3\n'
        self.assertEqual(footprint.requirement_pins(text),
                         {'cachecontrol': '0.14.4', 'pypdf': '6.21.4', 'python-dotenv': '1.2.3'})

    def test_anything_but_an_exact_pin_refuses(self):
        for line in ('pypdf>=6.21', 'pypdf==6.21.4; python_version>"3"', '-r other.txt', 'pypdf',
                     'pypdf==6.21.4 --hash=sha256:00', 'git+https://example.invalid/x'):
            with self.subTest(line=line), self.assertRaises(footprint.Refusal):
                footprint.requirement_pins(line + '\n')
        with self.assertRaises(footprint.Refusal):
            footprint.requirement_pins('pypdf==1\nPyPDF==2\n')

    def test_mismatch_lists_every_unsatisfied_pin_and_nothing_else(self):
        pins = {'pypdf': '6.21.4', 'filelock': '4.2.1', 'msgpack': '1.2.3', 'django': '5.2.17', 'absent': '1.0'}
        installed = {'pypdf': '6.21.1', 'filelock': '4.0.0', 'msgpack': '1.2.2', 'django': '5.2.17', 'pip': '24.0'}
        self.assertEqual(footprint.requirements_mismatch(pins, installed), {
            'absent': {'required': '1.0', 'installed': None},
            'filelock': {'required': '4.2.1', 'installed': '4.0.0'},
            'msgpack': {'required': '1.2.3', 'installed': '1.2.2'},
            'pypdf': {'required': '6.21.4', 'installed': '6.21.1'}})


if __name__ == '__main__':
    unittest.main()
