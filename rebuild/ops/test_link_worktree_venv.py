"""scripts/link-worktree-venv.sh: a worktree's venv link is made once, reused, and never written into the shared venv.

2026-09-23: a second `ln -s <venv> rebuild/.venv` wrote `.venv/.venv` INSIDE the shared production venv, and the
activation's source-readability gate refused an install 18 hours later. Each test builds a fake shared venv and a
fake worktree in a temporary directory; nothing outside it is touched.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'link-worktree-venv.sh'


class LinkWorktreeVenv(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.shared = root / 'shared' / 'rebuild' / '.venv'
        (self.shared / 'bin').mkdir(parents=True)
        (self.shared / 'lib').mkdir()
        (self.shared / 'bin' / 'python3').write_text('')
        os.symlink('python3', self.shared / 'bin' / 'python')
        os.symlink('lib', self.shared / 'lib64')
        self.worktree = root / 'worktree'
        (self.worktree / 'rebuild').mkdir(parents=True)
        self.link = self.worktree / 'rebuild' / '.venv'

    def run_script(self):
        return subprocess.run(['bash', str(SCRIPT), str(self.worktree)], capture_output=True, text=True,
                              env={**os.environ, 'QUILLMD_SHARED_VENV': str(self.shared)}, timeout=60)

    def shared_entries(self):
        return sorted(str(path.relative_to(self.shared)) for path in self.shared.rglob('*'))

    def test_the_hazard_itself_a_second_plain_ln_writes_inside_the_target(self):
        """Positive control for the mechanism the script guards against."""
        subprocess.run(['ln', '-s', str(self.shared), str(self.link)], check=True)
        subprocess.run(['ln', '-s', str(self.shared), str(self.link)], check=True)
        self.assertTrue((self.shared / '.venv').is_symlink())

    def test_it_links_once_and_a_second_run_reuses_the_link_and_writes_nothing(self):
        before = self.shared_entries()
        first = self.run_script()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(os.readlink(self.link), str(self.shared))
        second = self.run_script()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn('reused', second.stdout)
        self.assertEqual(self.shared_entries(), before)
        self.assertFalse((self.shared / '.venv').exists())

    def test_a_link_pointing_elsewhere_is_refused_and_left_alone(self):
        other = Path(self.directory.name) / 'other-venv'
        other.mkdir()
        os.symlink(other, self.link)
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(os.readlink(self.link), str(other))

    def test_a_real_directory_is_refused_and_left_alone(self):
        self.link.mkdir()
        (self.link / 'keep').write_text('x')
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertTrue((self.link / 'keep').exists())

    def test_a_stray_link_already_inside_the_shared_venv_is_reported(self):
        os.symlink(self.shared, self.shared / '.venv')
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn('.venv/.venv', result.stdout)
        self.assertTrue((self.shared / '.venv').is_symlink())          # reported, never removed by the script


if __name__ == '__main__':
    unittest.main()
