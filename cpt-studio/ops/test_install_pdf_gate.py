"""Unit tests for the image phase's PDF reading gate in ops/install.py (pdf_reading_gate; pypdf-r6 FC-4): the image
reads one synthetic guard PDF through its own extraction child, as its own user on its read-only root, and the install
is refused unless the reading is installed pypdf 6.21.2's. No Docker, sudo or network: docker is replaced, and the
gate's own script is also run here, on this tree, as the image runs it.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import guard_host, release_host  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:' + 'c' * 64
SMOKE = ['run', '--rm', '--pull=never', '--network', 'none', '--read-only', '--tmpfs', '/tmp', '--cap-drop', 'ALL',
         '--security-opt', 'no-new-privileges', '--no-healthcheck']
UNAVAILABLE = ('The PDF could not be read on this server: its PDF library is not the one the PDF reader was checked '
               'with.')
# The extraction child made to refuse the layer, as a pypdf of another version would make it: run in place of the
# real child (studio.ingest.extract.CHILD_ARGV) by the gate's own script below.
REFUSING_CHILD = ("import studio.ingest.pypdf_compat as layer; layer.PYPDF_VERSION = '0.0.0'; import runpy; "
                  "runpy.run_module('studio.ingest._child', run_name='__main__', alter_sys=True)")


def setUpModule():
    guard_host()


def tearDownModule():
    release_host()


def reading(**changes) -> bytes:
    found = {'pdf_sha256': install.PDF_GATE_PDF_SHA256, **install.PDF_GATE_READING, 'messages': [],
             'engine': {'ingest': 'cpt-studio-ingest@3', 'pypdf': '6.21.4'}} | changes
    return json.dumps(found).encode() + b'\n'


class PdfReadingGateTests(unittest.TestCase):
    def gate(self, stdout: bytes, returncode: int = 0):
        calls = []

        def docker(*args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=b'')
        original = install.docker
        install.docker = docker
        try:
            return install.pdf_reading_gate(SMOKE, IMAGE), calls
        finally:
            install.docker = original

    def test_it_runs_as_the_other_image_gates_and_passes_installed_6_21_2s_reading(self):
        found, calls = self.gate(reading())
        self.assertEqual(found['status'], 'ok')
        (args, kwargs), = calls
        # the image's own user (no --user), its read-only root, no network, no capabilities: the smoke options
        self.assertEqual(list(args), SMOKE + ['--entrypoint', 'python', IMAGE, '-c', install.PDF_GATE_SCRIPT])
        self.assertNotIn('--user', args)
        self.assertEqual((kwargs['check'], kwargs['timeout']), (False, 120))

    def test_any_other_reading_refuses_the_install(self):
        refused = reading(status='failed', text_sha256=hashlib.sha256(b'').hexdigest(), messages=[UNAVAILABLE],
                          engine={'ingest': 'cpt-studio-ingest@3', 'pypdf_compat': "pypdf's source files are not the "
                                                                                   "proven set."})
        cases = {
            'the layer refused': (refused, 0, "pypdf's source files are not the proven set."),
            'read without the layer': (reading(text_sha256='585ff58831411674f666f2dc5223fcc0562fed3c5cc6f405fb7dd9f915878c3b'),
                                       0, "'status': 'ok'"),
            'another guard': (reading(pdf_sha256='0' * 64), 0, "'pdf_sha256': '" + '0' * 64),
            'the script failed': (b'Traceback (most recent call last):\n  ...\nImportError: synthetic\n', 1,
                                  'could not read the guard PDF'),
            'no output': (b'', 0, 'could not read the guard PDF'),
            'a failing exit with the reading': (reading(), 1, 'does not read the guard PDF'),
        }
        for label, (stdout, code, said) in cases.items():
            with self.subTest(label), self.assertRaises(install.InstallError) as raised:
                self.gate(stdout, code)
            self.assertIn(said, str(raised.exception))

    def run_gate_script(self, child: str = '') -> subprocess.CompletedProcess:
        """The gate's own script, run on this tree as the image runs it (python -c in the service directory)."""
        prelude = (f'import sys, studio.ingest.extract as extract; extract.CHILD_ARGV = (sys.executable, "-c", '
                   f'{child!r})\n' if child else '')
        return subprocess.run([sys.executable, '-B', '-c', prelude + install.PDF_GATE_SCRIPT], cwd=APP_ROOT,
                              capture_output=True, timeout=120, check=False)

    def test_the_gate_script_on_this_tree_passes_and_a_refusing_layer_fails_it(self):
        done = self.run_gate_script()
        found, _ = self.gate(done.stdout, done.returncode)
        self.assertEqual((found['pdf_sha256'], found['status'], found['text_sha256']),
                         (install.PDF_GATE_PDF_SHA256, *install.PDF_GATE_READING.values()))
        done = self.run_gate_script(REFUSING_CHILD)
        with self.assertRaises(install.InstallError) as raised:
            self.gate(done.stdout, done.returncode)
        self.assertIn("'status': 'failed'", str(raised.exception))
        self.assertIn('pypdf 6.21.4 is installed; this layer is proven for 0.0.0.', str(raised.exception))
        self.assertEqual(raised.exception.details['pdf_reading']['messages'], [UNAVAILABLE])


if __name__ == '__main__':
    unittest.main()
