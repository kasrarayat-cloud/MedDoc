"""Deterministic worker identity refusals; no real service, process or provider is changed.

The two retained live-host tests intentionally skip on CI without QuillMD's systemd
unit. These fixtures exercise their refusal paths there, and also cover the helper
used by the latest completed private activation. They do not replace host evidence.
"""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from . import source_module
except ImportError:
    import source_module


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ('activate-audio-submission.py', 'activate-recording-repair.py', 'activate-word-export.py')
UNIT = 'quillmd-fresh-worker.service'
PID = 12345


class WorkerIdentityFixtures(unittest.TestCase):
    def identify(self, script, *, pid=PID, cgroup=None, command=None, missing_proc=False):
        helper = source_module.load('worker_identity_fixture', ROOT / 'scripts' / script)
        if cgroup is None:
            cgroup = '0::/system.slice/' + UNIT + '\n'
        if command is None:
            command = b'/opt/meddoc-pro/rebuild/.venv/bin/python\0/opt/meddoc-pro/rebuild/manage.py\0worker\0'
        process_stat = str(PID) + ' (python) ' + ' '.join(['0'] * 19 + ['500'])
        content = {
            f'/proc/{PID}/cgroup': cgroup,
            f'/proc/{PID}/cmdline': command,
            f'/proc/{PID}/stat': process_stat,
            '/proc/stat': 'cpu 1 2 3\nbtime 1700000000\n',
        }

        def output(argv):
            self.assertEqual(argv[:3], ['systemctl', 'show', UNIT])
            self.assertEqual(argv[-1], '--value')
            return {'--property=MainPID': str(pid),
                    '--property=ExecMainStartTimestamp': 'Tue 2023-11-14 22:13:25 UTC'}[argv[3]]

        def fake_path(value):
            self.assertIn(str(value), content, 'unexpected file read')
            if missing_proc and str(value).startswith(f'/proc/{PID}/'):
                raise FileNotFoundError('synthetic process exited before inspection')
            return SimpleNamespace(read_text=lambda: content[str(value)],
                                   read_bytes=lambda: content[str(value)])

        with patch.object(helper, 'output', side_effect=output), \
                patch.object(helper, 'Path', side_effect=fake_path), \
                patch.object(helper.os, 'sysconf', return_value=100), \
                patch.object(helper.subprocess, 'run', side_effect=AssertionError('no external operation')), \
                patch.object(helper.subprocess, 'check_output', side_effect=AssertionError('no external operation')):
            return helper.worker_process()

    def test_valid_fixture_records_identity_and_both_start_sources(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                row = self.identify(script)
                self.assertEqual(row['pid'], PID)
                self.assertEqual(row['unit'], UNIT)
                self.assertEqual(row['kernel_start_utc'], '2023-11-14T22:13:25+00:00')
                self.assertEqual(row['systemd_start'], 'Tue 2023-11-14 22:13:25 UTC')
                self.assertIn('/system.slice/' + UNIT, row['cgroup'])

    def test_inactive_worker_refuses_before_reading_process(self):
        for script in SCRIPTS:
            with self.subTest(script=script), self.assertRaisesRegex(RuntimeError, 'no main process'):
                self.identify(script, pid=0)

    def test_same_pid_in_an_unrelated_service_refuses(self):
        for script in SCRIPTS:
            with self.subTest(script=script), self.assertRaisesRegex(RuntimeError, 'service cgroup'):
                self.identify(script, cgroup='0::/system.slice/unrelated-project.service\n')

    def test_wrong_interpreter_or_nonworker_command_refuses(self):
        for script in SCRIPTS:
            for command in (
                b'/usr/bin/python\0/opt/meddoc-pro/rebuild/manage.py\0worker\0',
                b'/opt/meddoc-pro/rebuild/.venv/bin/python\0/opt/meddoc-pro/rebuild/manage.py\0shell\0',
                b'/opt/meddoc-pro/rebuild/.venv/bin/python\0unrelated.py\0worker\0',
            ):
                with self.subTest(script=script, command=command), self.assertRaisesRegex(RuntimeError, 'reviewed worker command'):
                    self.identify(script, command=command)

    def test_process_exit_during_inspection_is_not_accepted_as_identity(self):
        for script in SCRIPTS:
            with self.subTest(script=script), self.assertRaises(FileNotFoundError):
                self.identify(script, missing_proc=True)


if __name__ == '__main__':
    unittest.main()
