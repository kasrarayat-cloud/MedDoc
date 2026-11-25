"""Release 1's integrated refutation, round 4: the lead's repair of the installer's low finding installer-1 (DECISIONS
D415). Offline, under test_install's host guard; every Docker, root-helper and in-image call stood in. Synthetic data
only.

  L4-3  installer-1: provision's act answered (its CLI killed, -9, while its container ran on) and a SIGTERM reached
        round 3's leftover check while it waited on that container's stop. The signal is raised carrying the answer
        (oneshot_answer_of), and provision now takes it back as the manage acts and the operators' grant do: the act's
        output is kept in the receipts folder, redacted, and the receipt names it beside the interrupt. Nothing is
        handed over: the staged credentials are discarded, as before.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r1_lead_round4 -v
"""
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import test_install  # noqa: E402
from test_install import TemporaryDirectoryTest, guard_host, release_host  # noqa: E402


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


REVISION, COMMIT = 'a' * 40, 'e' * 40
OUTPUT = b'created human account owner-gi (owner)\n'


class ProvisionRecordAfterASignalTests(TemporaryDirectoryTest):
    def provision(self, *, signal_in_stop):
        """The REAL install.main for --phase provision, with the REAL oneshot over a stood-in docker: provision's CLI
        answers -9 while its container runs on; with ``signal_in_stop`` a SIGTERM lands while the installer waits on
        that container's `docker stop`. (exit code, receipt, the receipts folder, root_file's ops, what is left)."""
        receipts = self.tmp / 'receipts'
        left, ops = {}, []

        def run(argv, *, input=None, timeout=60, check=True, quiet=False, env=None):
            args = [str(part) for part in argv[1:]]
            if args[:1] == ['run']:
                name = args[args.index('--name') + 1]
                if 'provision' in args:  # the act: its CLI killed, its container running on
                    left[name] = {'Id': f'id-{name}', 'State': {'Running': True},
                                  'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'oneshot'}}}
                    return SimpleNamespace(returncode=-9, stdout=OUTPUT, stderr=b'')
                return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
            if args[:1] == ['stop'] and signal_in_stop:
                raise install.Interrupted('SIGTERM')
            if args[:2] == ['rm', '--force']:
                for name in [n for n, c in left.items() if args[2] in (n, c['Id'])]:
                    del left[name]
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

        def inspect(kind, name):
            return left.get(name) if name.startswith('cpt-studio-oneshot-') else None

        def root_file(op, **params):
            ops.append(op)
            return {'final_exists': False, 'staged_exists': False} if op == 'state' else {}
        door = {'declaration': 'docs/foundation/mutations/r4-lead-synthetic.md', 'declaration_commit': COMMIT,
                'declaration_sha256': '0' * 64}
        argv = ['--phase', 'provision', '--revision', REVISION, '--receipts', str(receipts), '--owner-username',
                'owner-gi', '--by', 'Ada Lovelace']
        with mock.patch.multiple(install, installed_image=mock.Mock(return_value='sha256:' + 'c' * 64),
                                 require_db=mock.Mock(), read_protected_env=mock.Mock(return_value=b'K=v\n'),
                                 root_file=root_file, app_script=test_install.no_grants, run=run, inspect=inspect,
                                 docker=lambda *args, **kwargs: run([install.DOCKER, *args], **kwargs),
                                 check_door=mock.Mock(return_value=door),
                                 check_tree=mock.Mock(return_value={'mode': 'exact'})), \
                mock.patch('sys.stdout', io.StringIO()), mock.patch('sys.stderr', io.StringIO()):
            code = install.main(argv)
        receipt = json.loads(sorted(receipts.glob('provision-*.json'))[-1].read_text())
        return code, receipt, receipts, ops, left

    def test_a_signal_in_the_leftover_check_keeps_the_acts_record_and_hands_nothing_over(self):
        code, receipt, receipts, ops, left = self.provision(signal_in_stop=True)
        self.assertEqual((code, receipt['ok'], receipt['interrupted']), (143, False, 'SIGTERM'))
        details = receipt['details']
        self.assertIsNotNone(details, 'the receipt does not say what the act did')
        self.assertEqual((details['exit'], details['credentials_handed_over'], details['by']), (-9, False, 'Ada Lovelace'))
        self.assertEqual(Path(details['log']).parent, receipts)
        self.assertEqual(Path(details['log']).read_bytes(), OUTPUT)  # the act's output, kept
        self.assertIn('discard', ops)  # nothing handed over: the staged credentials discarded
        self.assertNotIn('commit', ops)
        self.assertEqual(left, {})  # the one-shot removed

    def test_control_without_a_signal_the_failure_names_its_log_as_before(self):
        code, receipt, receipts, ops, left = self.provision(signal_in_stop=False)
        self.assertEqual((code, receipt['ok'], receipt.get('interrupted')), (1, False, None))
        self.assertIn('provision failed (exit -9)', receipt['error'])
        self.assertEqual(Path(receipt['details']['log']).read_bytes(), OUTPUT)
        self.assertIn('discard', ops)
        self.assertNotIn('commit', ops)
        self.assertEqual(left, {})


if __name__ == '__main__':
    unittest.main()
