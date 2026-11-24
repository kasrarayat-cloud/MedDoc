"""Release 1's integrated refutation, round 2: the installer's repairs (repair builder i2). Offline, under test_install's
host guard; every Docker, root-helper and in-image call stood in. Synthetic data only.

  I2-1  installer-0: one ledger limit (LEDGER_LIMIT), read by the replay step and by the ledger step, which keeps no
        ledger the replay would refuse; sized for a practice-year at the owner's figure.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r1_repair_i2 -v
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import test_install_r1 as r1  # noqa: E402
from test_install import TemporaryDirectoryTest, guard_host, release_host  # noqa: E402


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- I2-1: a ledger's one limit -----------------------------------------------------------------------------------------

def ledger_of(size: int, lines: int = 4) -> bytes:
    """A ledger-shaped file of exactly ``size`` bytes in ``lines`` JSON lines of ids (the real ledger's MACs are the
    command's to check, and every command is stood in here)."""
    rows = [json.dumps({'entry': {'id': f'0f8fad5b-d9cb-469f-a165-7086772895{n:02d}', 'pad': ''}, 'mac': '0' * 64},
                       sort_keys=True).encode() + b'\n' for n in range(lines)]
    short = size - sum(len(row) for row in rows)
    assert short >= 0, size
    rows[-1] = rows[-1].replace(b'"pad": ""', b'"pad": "' + b'a' * short + b'"')
    data = b''.join(rows)
    assert len(data) == size, (len(data), size)
    return data


# The finding's two inputs (refutation round 2, installer-0): the genuine ledger of one whole-practice disposal of 5,000
# one-PDF documents (1,050,108 bytes in 4 lines), and the 'committed' line alone of an 8,100-document one (1,062,712
# bytes) - both over the 1 MiB the replay read before.
FIVE_THOUSAND_DOCUMENTS = 1_050_108
ONE_LINE_OF_8100_DOCUMENTS = 1_062_712


class LedgerLimitTests(TemporaryDirectoryTest):
    def world(self, name, **kwargs):
        folder = self.tmp / name
        folder.mkdir(mode=0o700)
        return r1.ManageWorld(folder, **kwargs)

    def replay(self, name, ledger_path, *extra):
        world = self.world(name, output=b'Ledger rows missing: 4\n')
        details = world.run('--command', 'dispose', '--dispose-step', 'replay-ledger', '--ledger-file', str(ledger_path),
                            '--by', 'Ada Lovelace', *extra)
        return world, details

    def test_the_ledger_the_ledger_step_keeps_whole_is_one_the_replay_step_reads(self):
        ledger = r1_ledger = ledger_of(FIVE_THOUSAND_DOCUMENTS)
        printer = self.world('print', output=ledger)
        printed = printer.run('--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace')
        kept = Path(printed['ledger_printed']['log'])
        self.assertEqual(kept.read_bytes(), ledger)
        self.assertEqual((printed['ledger_printed']['sha256'], printed['ledger_printed']['bytes'],
                          printed['ledger_printed']['lines']), (sha(ledger), len(ledger), 4))
        self.assertTrue(printed['stdout_cut'])  # the receipt keeps STDOUT_KEPT characters; the log keeps it whole
        for name, extra in (('dry-run', ()), ('execute', ('--execute', '--approved-by', 'Grace Hopper'))):
            with self.subTest(name):
                world, details = self.replay(name, kept, *extra)
                (act,) = world.acts()
                self.assertEqual(act[:4], ['manage', 'dispose', '--replay-ledger', '/run/cpt-manage/ledger'])
                # the RAM-only copy the one-shot read is the ledger, byte for byte, and the receipt names it by digest
                self.assertEqual(world.mounted['ledger'][0].encode(), r1_ledger)
                self.assertEqual(details['ledger'], {'sha256': sha(ledger), 'bytes': len(ledger)})

    def test_one_committed_line_of_an_8100_document_disposal_replays(self):
        line = ledger_of(ONE_LINE_OF_8100_DOCUMENTS, lines=1)
        path = self.tmp / 'committed-line.log'
        path.write_bytes(line)
        world, details = self.replay('one-line', path)
        self.assertEqual(world.mounted['ledger'][0].encode(), line)
        self.assertEqual(details['mode'], 'dry run')

    def test_the_ledger_step_keeps_no_ledger_the_replay_step_would_refuse_and_says_what_to_do(self):
        for name, output, why in (('over', ledger_of(install.LEDGER_LIMIT + 1), 'more than'),
                                  ('not-utf8', b'{"entry": "\xff"}\n', 'not UTF-8')):
            with self.subTest(name):
                world = self.world(name, output=output)
                with self.assertRaises(install.InstallError) as caught:
                    world.run('--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace')
                message, record = str(caught.exception), caught.exception.details
                self.assertIn('the ledger it printed is not kept', message)
                self.assertIn('Nothing was changed', message)
                self.assertIn('never restore the database from a backup older than its newest disposal', message)
                printed = record['ledger_printed']
                self.assertIsNone(printed['log'])
                self.assertIn(why, printed['not_kept'])
                self.assertEqual((printed['sha256'], printed['bytes']), (sha(output), len(output)))
                self.assertFalse([path for path in world.tmp.glob('*.log') if path.read_bytes() == output])
                self.assertFalse(list(world.tmp.glob('*-dispose-ledger.log')))
        # exactly at the limit it is kept - and the replay reads that very file
        exact = ledger_of(install.LEDGER_LIMIT)
        world = self.world('exact', output=exact)
        kept = Path(world.run('--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace')
                    ['ledger_printed']['log'])
        self.assertEqual(kept.read_bytes(), exact)
        replayed, _ = self.replay('exact-replay', kept)
        self.assertEqual(len(replayed.mounted['ledger'][0].encode()), install.LEDGER_LIMIT)

    def test_one_limit_is_read_by_both_steps(self):
        with mock.patch.object(install, 'LEDGER_LIMIT', 4096):
            refused = self.world('refused', output=ledger_of(4097, lines=2))
            with self.assertRaisesRegex(install.InstallError, 'not kept, since it is 4097 bytes, more than the 4096'):
                refused.run('--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace')
            path = self.tmp / 'ledger-4097.log'
            path.write_bytes(ledger_of(4097, lines=2))
            with self.assertRaisesRegex(install.InstallError, 'at most 4096 bytes'):
                self.replay('refused-replay', path)
            kept = Path(self.world('kept', output=ledger_of(4096, lines=2)).run(
                '--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace')['ledger_printed']['log'])
            world, _ = self.replay('kept-replay', kept)
            self.assertEqual(len(world.mounted['ledger'][0]), 4096)
        self.assertEqual(install.ledger_problem(b'x' * 10), '')
        self.assertIn('not UTF-8', install.ledger_problem(b'\xff'))

    def test_the_limit_holds_a_practice_year_at_the_owners_figure_within_the_replays_memory(self):
        documents = 50 * 365  # 1,000 practices at 50 uploads a day: one practice's year
        per_document, per_further_file, per_disposal = 209, 92, 5_120  # round 2's measurement of the ledger's growth
        for files in (1, 4):
            with self.subTest(files=files):
                self.assertLess(documents * (per_document + per_further_file * (files - 1)) + per_disposal,
                                install.LEDGER_LIMIT)
        # the replay's one-shot (the act's container) reads the ledger whole: repair round 2 measured its reading at about
        # five bytes per ledger byte, so the limit keeps six well inside that container's memory
        calls = []
        with mock.patch.object(install, 'run', lambda argv, **kwargs: calls.append(argv) or mock.Mock(returncode=0)), \
                mock.patch.object(install, 'inspect', return_value=None):
            install.oneshot('sha256:' + 'c' * 64, ['manage', 'dispose'], b'')
        memory = calls[0][calls[0].index('--memory') + 1]
        self.assertEqual(memory, '768m')
        self.assertLess(6 * install.LEDGER_LIMIT, 768 * 2 ** 20)


if __name__ == '__main__':
    unittest.main()
