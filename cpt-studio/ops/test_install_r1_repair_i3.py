"""Release 1's integrated refutation, round 3: the installer's repairs (repair builder i3). Offline, under test_install's
host guard; every Docker, root-helper and in-image call stood in. Synthetic data only.

  I3-1  installer-0: `replay-ledger --execute` alone also runs when there is no pair at all (neither cpt-studio-web nor
        cpt-studio-worker, read as docker's answer that there is no such container - an answer it cannot read still
        refuses), since nothing serves; close and execute still need a pair with disposal. The restore's one sequence,
        end to end through the installer's real phases: on the serving host the pair stopped, the replay, `app` again;
        on a fresh host the replay with no pair, then `app`.
  I3-2  installer-2: a reason in words is never refused - a heading, a label, a line of one word, two words, a language
        written without spaces - and a whole reason, or a line of 12 characters or more, of ids, links and numbers
        alone still is; what the rule lets through never alters an id, a count or a digest the act prints.
  I3-3  installer-3: after docker's own failure (125: its --rm removal failed) or a CLI killed by a signal, the one-shot
        is looked for, stopped and removed; nothing in that check takes the act's answer, or its record, away.
  I3-4  regression-9: the journal's flush test (test_install_r1_logs) reads install's clock at one pinned moment, so
        it passes when UTC midnight falls inside it - run here under the finding's midnight-crossing clock, with the
        unpinned body as the control that fails there.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r1_repair_i3 -v
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import test_install_r1 as r1  # noqa: E402
from test_install import TemporaryDirectoryTest, guard_host, release_host  # noqa: E402


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


# --- I3-1: a replay with no pair at all ----------------------------------------------------------------------------------

LEDGER = b'{"entry":{"id":"5717f66b-dae4-49b2-865b-102998117109"},"mac":"00"}\n'
REPLAY = ('--dispose-step', 'replay-ledger', '--ledger-file', 'LEDGER', '--execute', '--approved-by', 'Grace Hopper')
DRY_RUN = ('--dispose-step', 'replay-ledger', '--ledger-file', 'LEDGER')
CLOSE = ('--dispose-step', 'close', '--workspace-id', r1.WORKSPACE, '--reason-file', 'REASON')
EXECUTE = ('--dispose-step', 'execute', '--plan-id', r1.PLAN, '--approved-by', 'Grace Hopper')
NO_PAIR = {'web': None, 'worker': None}
PAIR = (install.SERVICES['web'], install.SERVICES['worker'])
REAL_INSPECT = install.inspect


def dispose(world, extra):
    """(details, None) when the step ran, (None, the InstallError) when it was refused."""
    try:
        return world.run('--command', 'dispose', *extra, '--by', 'Ada Lovelace', ledger=LEDGER), None
    except install.InstallError as error:
        return None, error


class AnsweringWorld(r1.ManageWorld):
    """ManageWorld whose canonical pair is read by the REAL install.inspect over a stood-in `docker container inspect`
    answering ``answer`` (exit code, stdout, stderr) for both names."""

    def __init__(self, tmp, answer, **kwargs):
        super().__init__(tmp, serving=NO_PAIR, **kwargs)
        self.answer, self.asked = answer, []

    def inspect(self, kind, name):
        if kind == 'container' and name in PAIR:
            def docker(*args, **kwargs):
                self.asked.append(args)
                code, out, err = self.answer
                return SimpleNamespace(returncode=code, stdout=out, stderr=err)
            with mock.patch.object(install, 'docker', docker):
                return REAL_INSPECT(kind, name)
        return super().inspect(kind, name)


class NoPairReplayTests(TemporaryDirectoryTest):
    def folder(self, name):
        folder = self.tmp / name.replace(' ', '-').replace("'", '')
        folder.mkdir(mode=0o700)
        return folder

    def test_with_no_pair_at_all_the_replay_runs_and_close_and_execute_still_refuse(self):
        # the finding's input: a fresh server after a database restore, before `app` - no cpt-studio-web, no worker
        world = r1.ManageWorld(self.folder('replay'), serving=NO_PAIR)
        details, error = dispose(world, REPLAY)
        self.assertIsNone(error, error and str(error))
        self.assertEqual((details['summary'], details['mode']), ('dispose replay-ledger: executed', 'executed'))
        self.assertEqual(len(world.acts()), 1)
        act = world.acts()[0]
        self.assertEqual(act[:4], ['manage', 'dispose', '--replay-ledger', f'{install.MANAGE_MOUNT}/ledger'])
        self.assertEqual(act[act.index('--execute'):act.index('--execute') + 3], ['--execute', '--approved-by',
                                                                                  'Grace Hopper'])
        # the installer still tells the command no switch is in progress, as for every disposal step
        self.assertIn('CPT_STUDIO_SWITCH_STATE=idle', world.oneshots[-1][1]['environment'])
        self.assertEqual(world.mounted['ledger'][0], LEDGER.decode())
        # the dry run and the ledger were open before, and stay so
        for label, extra in (('dry run', DRY_RUN), ('ledger', ('--dispose-step', 'ledger'))):
            with self.subTest(open=label):
                world = r1.ManageWorld(self.folder(label), serving=NO_PAIR)
                details, error = dispose(world, extra)
                self.assertIsNone(error, error and str(error))
                self.assertEqual(world.acts()[0][:2], ['manage', 'dispose'])
        # close and execute change rows a revision without disposal would serve: they still need a pair with disposal
        for label, extra in (('close', CLOSE), ('execute', EXECUTE)):
            with self.subTest(refused=label):
                world = r1.ManageWorld(self.folder(label), serving=NO_PAIR)
                details, error = dispose(world, extra)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn('there is no cpt-studio-web, so the revision that serves next is not known',
                              str(error))
                self.assertIn('install one (--phase app), then run this step again', str(error))
                self.assertIn('a replay with --execute runs too when there is no pair at all', str(error))
                self.assertEqual(world.acts(), [])

    def test_no_pair_is_read_from_dockers_own_answer_and_anything_else_refuses(self):
        # docker's own answer that neither exists - the stderr of `docker container inspect` for a missing name
        world = AnsweringWorld(self.folder('no such container'), (1, b'', b'Error: No such container: x\n'))
        details, error = dispose(world, REPLAY)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(details['summary'], 'dispose replay-ledger: executed')
        self.assertEqual(sorted(args[-1] for args in world.asked), sorted(PAIR))
        # an answer that cannot be read is never read as no pair: a daemon error, and an answer that is no container
        for label, answer, said in (
                ('a daemon error', (1, b'', b'Error response from daemon: i/o timeout\n'),
                 'docker container inspect cpt-studio-web failed (exit 1).'),
                ('an empty list', (0, b'[]', b''), 'answered something that is not one container'),
                ('a null', (0, b'[null]', b''), 'answered something that is not one container'),
                ('not json', (0, b'<html>', b''), 'answered something that is not one container')):
            with self.subTest(refused=label):
                world = AnsweringWorld(self.folder(label), answer)
                details, error = dispose(world, REPLAY)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn(said, str(error))
                self.assertIn('Nothing was disposed of.', str(error))
                self.assertEqual(world.acts(), [])
        # a pair that is not all there is not "no pair": a worker with no web, an older pair, one not this installer's
        import test_install
        old = 'b' * 40
        refused = {
            'a worker, no web': ({'web': None, 'worker': r1.REVISION}, 'there is no cpt-studio-web'),
            'an older web, no worker': ({'web': old, 'worker': None},
                                        f'cpt-studio-web is revision {old[:12]}, which has no disposal'),
            'an older worker, no web': ({'web': None, 'worker': old}, 'there is no cpt-studio-web'),
        }
        with mock.patch.object(test_install, 'PRE_DISPOSAL_REVISIONS', {old}):
            for label, (serving, said) in refused.items():
                with self.subTest(refused=label):
                    world = r1.ManageWorld(self.folder(label), serving=serving)
                    details, error = dispose(world, REPLAY)
                    self.assertIsInstance(error, install.InstallError)
                    self.assertIn(said, str(error))
                    self.assertEqual(world.acts(), [])
        # an install or switch-back in progress refuses with no pair too (its -next or -previous containers)
        for leftover in (install.INCOMING_WEB, 'cpt-studio-web-previous', 'cpt-studio-worker-previous'):
            with self.subTest(in_progress=leftover):
                world = r1.ManageWorld(self.folder(leftover), serving=NO_PAIR, containers=[leftover])
                details, error = dispose(world, REPLAY)
                self.assertIn('in progress', str(error))
                self.assertEqual(world.acts(), [])

    def test_a_docker_answer_that_is_not_one_object_raises_wherever_it_is_read(self):
        # install.inspect's own contract, which the reading above rests on: None only for docker's no such answer
        for stdout in (b'[]', b'[null]', b'{"Id": "x"}', b'"x"', b'[1]', b'not json'):
            with self.subTest(stdout=stdout), \
                    mock.patch.object(install, 'docker', return_value=SimpleNamespace(returncode=0, stdout=stdout,
                                                                                       stderr=b'')), \
                    self.assertRaises(install.InstallError) as caught:
                REAL_INSPECT('container', 'cpt-studio-web')
            self.assertIn('answered something that is not one container', str(caught.exception))
        with mock.patch.object(install, 'docker', return_value=SimpleNamespace(
                returncode=0, stdout=b'[{"Id": "x", "State": {}}]', stderr=b'')):
            self.assertEqual(REAL_INSPECT('container', 'cpt-studio-web'), {'Id': 'x', 'State': {}})
        with mock.patch.object(install, 'docker', return_value=SimpleNamespace(
                returncode=1, stdout=b'', stderr=b'Error: No such container: cpt-studio-web\n')):
            self.assertIsNone(REAL_INSPECT('container', 'cpt-studio-web'))


class ManageOnHost(r1.ManageWorld):
    """ManageWorld whose containers are a BlueGreenWorld host's, labelled as docker inspect shows them."""

    def __init__(self, tmp, host, **kwargs):
        super().__init__(tmp, **kwargs)
        self.host = host

    def inspect(self, kind, name):
        return self.host.inspect(kind, name)


class RestoreSequenceTests(TemporaryDirectoryTest):
    """INSTALL.md's restore, one sequence on both hosts, through the installer's REAL phase_manage and phase_app on the
    blue/green host model (the application's half - the replay refused while the worker beat less than two minutes
    ago - is the command's own, and unchanged)."""

    def replay(self, host, name):
        folder = self.tmp / name
        folder.mkdir(mode=0o700)
        world = ManageOnHost(folder, host)
        details, error = dispose(world, REPLAY)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(details['summary'], 'dispose replay-ledger: executed')
        self.assertEqual([act[:3] for act in world.acts()], [['manage', 'dispose', '--replay-ledger']])

    def test_on_the_serving_host_the_pair_is_stopped_the_ledger_replayed_and_app_starts_it_again(self):
        from test_install_bluegreen import IMAGE, REVISION, WEB, WORKER, BlueGreenWorld, run_app
        host = BlueGreenWorld(self.tmp, serving=(REVISION, IMAGE))  # this revision serves on 9150
        host.checking = False  # from the stop on the site serves nothing: no blue/green invariant to hold
        stopped = {}
        for name, seconds in ((WORKER, install.STOP_SECONDS['worker']), (WEB, install.STOP_SECONDS['web'])):
            host.docker('stop', '--time', str(seconds), name)  # step 1, as INSTALL.md gives it: the worker first
            stopped[name] = host.containers[name]['Id']
        self.assertEqual((install.STOP_SECONDS['worker'], install.STOP_SECONDS['web']), (3600, 30))  # INSTALL.md's
        self.replay(host, 'replay')  # step 4: the stopped pair is read, its revision has disposal
        self.assertEqual({name: host.containers[name]['running'] for name in (WEB, WORKER)},
                         {WEB: False, WORKER: False})  # the replay starts nothing
        details, error = run_app(host)  # step 5: `app` again, its web stopped - a swap on the vhost's port
        self.assertIsNone(error, error and str(error))
        self.assertEqual(details['replacement']['mode'], 'fresh')
        self.assertEqual(host.names(), {WEB: (IMAGE, 9150, True), WORKER: (IMAGE, None, True)})
        self.assertNotIn(host.containers[WEB]['Id'], stopped.values())  # the stopped pair was replaced, then removed
        self.assertEqual(install.proxied_port(host.vhost_text), 9150)

    def test_on_a_fresh_host_the_ledger_is_replayed_with_no_pair_then_app_installs_one(self):
        from test_install_bluegreen import IMAGE, WEB, WORKER, BlueGreenWorld, run_app
        host = BlueGreenWorld(self.tmp)
        host.containers.clear()  # a fresh server: no pair; the database restored (the application's half)
        host.checking = False
        self.replay(host, 'replay')
        self.assertEqual(host.names(), {})  # the replay starts nothing
        with mock.patch.object(install, 'vhost_state', return_value={
                'file_exists': False, 'file_sha256': None, 'link_exists': False, 'link_target': None}):
            details, error = run_app(host)  # then `app`, before https-vhost opens the site
        self.assertIsNone(error, error and str(error))
        self.assertEqual(details['replacement']['mode'], 'fresh')
        self.assertEqual(host.names(), {WEB: (IMAGE, install.WEB_PORT, True), WORKER: (IMAGE, None, True)})


# --- I3-2: a reason in words is never refused; a line, or a whole reason, of ids, links and numbers alone still is -------

# the finding's reasons (refutation round 3, installer-2 - the lens's and the verifier's), each refused before the act
REASONS_IN_WORDS_R3 = {
    'a heading line': 'Justification\nThe practice ended its contract with us on 2026-11-20 and asked in writing for its '
                      'data to be destroyed.\n',
    'the specialty on its own line': 'Gastroenterology\nThe owner of this practice asked us to close it at the end of '
                                     'its contract.\n',
    'a label line': 'Confidential\nThe practice owner asked us in writing to close the practice.\n',
    'a German subject line': 'Vertragsbeendigung\nDie Praxis hat die Löschung ihrer Daten schriftlich verlangt.\n',
    'Japanese, no spaces': '契約終了に伴い、診療所のデータ削除を書面で依頼されました。\n',
    'two words': 'Contract terminated.\n',
    'two words, no stop': 'Practice closure\n',
    'a last line of one word': 'The owner asked us in writing to close it.\nAcknowledgement\n',
    'an indented word': 'Closing the practice per the owner.\n  Gastroenterology\n',
    'a paragraph wrapped at 80 columns': '\n'.join(__import__('textwrap').wrap(
        'The practice ended its contract with us on 2026-11-20 and asked us in writing to destroy all of its data; '
        "the signed request is on file with the owner's written acknowledgement.", width=80)) + '\n',
    'a sign-off': 'The practice asked us in writing on 2026-11-20 for its data to be destroyed.\nRespectfully,\n',
}
# and more of the class, words in other forms: a heading with its colon, separator lines, a date in a Japanese sentence,
# a German word written decomposed (o and its combining diaeresis), a word alone
WORDS_IN_OTHER_FORMS_R3 = {
    'a heading with its colon': 'Justification:\nThe practice asked us to close it.\n',
    'separator lines': 'Reason\n------------\n============\n____________\nThe practice asked us to close it.\n',
    'a date in a Japanese sentence': '2026年11月20日、診療所から書面でデータ削除の依頼を受けました。\n',
    'a decomposed German word': 'Löschung der Praxisdaten verlangt\n',
    'one long word': 'Vertragsbeendigung\n',
}
# round 2's own refusals (installer-5's class), which still refuse: too short, or ids, links and numbers alone
REASONS_TOO_PLAIN_R2 = ('4521\n', '40de\n', '7c9e6679\n', 'Ticket 4521\n', 'Grace Hopper\n', 'per ticket\n', 'a b\n',
                        '4521 4522 4523\n', '4521\n4522\n4523\n')
LINES_NOT_WORDS_R2 = ('1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9', 'https://support.example/tickets/4521', '123456789012',
                      'deadbeefcafe', 'deadbeefcafe,', 'abcdefab-cdef-abcd-efab-cdefabcdefab',
                      '7c9e6679-4521-40de-944b-e07fc1f90ae7, 1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9',
                      'https://support.example/tickets', 'support.example.com', 'owner@practice.example',
                      'studio_encounter', '/run/cpt-manage/reason', 'docs/foundation/mutations/x.md',
                      '2026-11-25T01:00:00Z', 'sha256:9f86d081884c7d65')
# the act's output in dispose.py's own formats (the close line, the plan, its rows, files and manifest line, a ledger
# JSON line), and what its record needs whole: every id, count and digest
PRINTED_WORKSPACE, PRINTED_PLAN = '7a1c2e9b-4d3f-4b8a-9c6d-0e1f2a3b4c5d', '7c9e6679-4521-40de-944b-e07fc1f90ae7'
PRINTED_DIGEST = '3b8f0a1c9d2e4f5a6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c'
PRINTED_FILE = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
PRINTED_BY_DISPOSE = (
    f'Closed practice {PRINTED_WORKSPACE} at 2026-11-25T00:41:07Z: no new upload or coding; reading stays on. '
    f'DisposalEvent {PRINTED_PLAN} (closed).\n'
    f'Plan {PRINTED_PLAN} for practice {PRINTED_WORKSPACE} (3 document(s)); nothing was changed. Carry it out within 24 '
    'hours with --execute --plan <id>, run and approved by two different people.\n'
    'Rows in scope: studio_encounter 3, studio_sourcefile 3, studio_sourcerevision 4521\n'
    f'Files in scope: 1 (4521 bytes; 0 missing); manifest sha256 {PRINTED_DIGEST}\n'
    f'  {PRINTED_FILE}  4521  {"c0ffee" * 8}.pdf\n'
    + __import__('json').dumps({'event': PRINTED_PLAN, 'workspace': PRINTED_WORKSPACE, 'manifest_digest': PRINTED_DIGEST,
                                'files': 1, 'bytes': 4521}) + '\n').encode()
PRINTED_WHOLE = (PRINTED_WORKSPACE, PRINTED_PLAN, PRINTED_DIGEST, PRINTED_FILE, '4521', '3 document(s)', 'c0ffee' * 8,
                 '2026-11-25T00:41:07Z')


class ReasonInWordsTests(TemporaryDirectoryTest):
    def close(self, reason, name):
        folder = self.tmp / name
        folder.mkdir(mode=0o700)
        world = r1.ManageWorld(folder)
        try:
            return world.run('--command', 'dispose', *CLOSE, '--by', 'Ada Lovelace', reason=reason), None, world
        except install.InstallError as error:
            return None, error, world

    def test_every_reason_in_words_runs_through_the_manage_phase(self):
        # the finding's input: --dispose-step close --workspace-id ... --reason-file R, with each reason it refused
        for index, (label, text) in enumerate({**REASONS_IN_WORDS_R3, **WORDS_IN_OTHER_FORMS_R3}.items()):
            with self.subTest(reason=label):
                details, error, world = self.close(text.encode(), f'r{index}')
                self.assertIsNone(error, error and str(error))
                self.assertEqual(details['summary'], 'dispose close: executed')
                self.assertEqual(world.acts()[0][:3], ['manage', 'dispose', '--close'])
                self.assertEqual(world.mounted['reason'][0], text)  # the reason reached the act as written

    def test_round_twos_refusals_still_refuse_before_the_act(self):
        for index, text in enumerate(REASONS_TOO_PLAIN_R2):
            with self.subTest(reason=text):
                details, error, world = self.close(text.encode(), f'p{index}')
                self.assertIn('--reason-file must give the reason in words', str(error))
                self.assertIn('nothing was run', str(error))
                self.assertNotIn(text.strip(), str(error))  # the refusal never repeats the reason
                self.assertEqual(world.acts(), [])
        for index, line in enumerate(LINES_NOT_WORDS_R2):
            with self.subTest(line=line):
                details, error, world = self.close(f'The practice asked to end access.\n{line}\n'.encode(), f'l{index}')
                self.assertIn('is an id, a link or a number alone', str(error))
                self.assertNotIn(line, str(error))
                self.assertEqual(world.acts(), [])

    def test_what_the_rule_lets_through_never_alters_an_id_a_count_or_a_digest_the_act_prints(self):
        # the rule's purpose: each value redact_output replaces (reason_values) of a reason it lets through leaves
        # every id, count and digest whole - as printed, and with the reason echoed in the output too
        for label, text in {**REASONS_IN_WORDS_R3, **WORDS_IN_OTHER_FORMS_R3}.items():
            data = text.encode()
            self.assertEqual(install.reason_words_problem(data), '', label)
            echoed = PRINTED_BY_DISPOSE + data + b'\n' + PRINTED_BY_DISPOSE
            for output in (PRINTED_BY_DISPOSE, echoed):
                with self.subTest(reason=label, echoed=output is echoed):
                    redacted, counts = install.redact_output(output, reasons=install.reason_values(data))
                    for value in PRINTED_WHOLE:
                        self.assertEqual(redacted.count(value.encode()), output.count(value.encode()), value)
        # the positive control: a line that is an id alone, if it were let through, alters the plan id it names
        values = install.reason_values(f'The practice asked to end access.\n{PRINTED_PLAN}\n'.encode())
        redacted, counts = install.redact_output(PRINTED_BY_DISPOSE, reasons=values)
        self.assertEqual(redacted.count(PRINTED_PLAN.encode()), 0)
        self.assertGreater(counts['reason'], 0)

    def test_ids_links_and_numbers_are_told_from_words(self):
        for part in ('Gastroenterology', 'Justification:', 'acknowledgement.', 'Respectfully,', '(Confidential)',
                     'end-of-contract', "practice's", 'Löschung', '診療所のデータ削除を書面で依頼されました。',
                     '2026年11月20日、', '------------', '____________', 'faced', 'decade'):
            with self.subTest(word=part):
                self.assertFalse(install.reason_part_is_an_id(part))
        for part in ('4521', '40de-944b', 'ADM-4521', 'https://support.example', 'owner@practice', 'x.md',
                     'studio_encounter', 'key=value', '/run', 'deadbeefcafe', '(deadbeefcafe)', 'DEADBEEFCAFE'):
            with self.subTest(not_a_word=part):
                self.assertTrue(install.reason_part_is_an_id(part))
        self.assertTrue(install.reason_holds_a_word('Ticket 4521'))
        self.assertFalse(install.reason_holds_a_word('4521 4522'))
        self.assertFalse(install.reason_holds_a_word(''))  # nothing in it: no word


# --- I3-3: a one-shot docker may have left after it answered is looked for and removed; the answer always stands -------

REAL_ONESHOT = install.oneshot
CERTIFICATE = (b'Destruction certificate\nPlan 2f8fad5b-d9cb-469f-a165-70867728950e: completed\nRun by: Ada Lovelace; '
               b'approved by: Grace Hopper\nRows destroyed: 12\nFiles remaining: 0\n')
DOCKER_ERROR = b'Error response from daemon: unable to remove filesystem\n'
LEFTOVER = {'Id': 'oneshot-1', 'State': {'Running': True},
            'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'oneshot'}}}
STOP_LEFTOVER = ('stop', '--time', str(install.ONESHOT_STOP_SECONDS), 'oneshot-1')


def answering(code, stdout=CERTIFICATE):
    return SimpleNamespace(returncode=code, stdout=stdout, stderr=DOCKER_ERROR if code == 125 else b'')


class LeftAfterAnswerWorld(r1.ManageWorld):
    """ManageWorld whose one-shots are the REAL install.oneshot over a stood-in docker CLI (install.run, given to the
    test's patch): the act prints its certificate, the CLI answers ``code`` (125: its --rm removal failed; -9: it was
    killed, its container running on) and the container is left; ``interrupt`` names the docker call ('inspect' or
    'stop') a SIGTERM lands in, once."""

    def __init__(self, tmp, *, code, interrupt=None, **kwargs):
        super().__init__(tmp, **kwargs)
        self.code, self.interrupt, self.left, self.calls = code, interrupt, {}, []
        self.oneshot = REAL_ONESHOT

    def signal_at(self, call):
        if self.interrupt == call:
            self.interrupt = None
            raise install.Interrupted('SIGTERM')

    def docker_run(self, argv, *, input=None, timeout=60, check=True, quiet=False, env=None):
        args = [str(part) for part in argv[1:]]
        if args[:1] == ['run']:
            if 'migrate' in args:
                return answering(0, b'')
            name = args[args.index('--name') + 1]
            self.left[name] = {**LEFTOVER, 'Id': f'id-{name}', 'State': {'Running': self.code < 0}}
            return answering(self.code)
        self.calls.append(args)
        self.signal_at(args[0])
        if args[:2] == ['rm', '--force']:
            self.left = {name: c for name, c in self.left.items() if args[2] not in (name, c['Id'])}
        if args[:1] == ['stop']:
            for c in self.left.values():
                if c['Id'] == args[-1]:
                    c['State'] = {'Running': False}
        return answering(0, b'')

    def inspect(self, kind, name):
        if name.startswith('cpt-studio-oneshot-'):
            self.calls.append(['inspect', name])
            self.signal_at('inspect')
            return self.left.get(name)
        return super().inspect(kind, name)


class AnsweredLeftoverTests(TemporaryDirectoryTest):
    def oneshot(self, answer, *, inspect=None, docker=None):
        calls = []

        def stand_in(*args, **kwargs):
            calls.append((args, kwargs))
            if docker is not None:
                return docker(*args, **kwargs)
        with mock.patch.object(install, 'run', return_value=answer), \
                mock.patch.object(install, 'inspect', inspect or (lambda kind, name: LEFTOVER)), \
                mock.patch.object(install, 'docker', stand_in):
            return REAL_ONESHOT('sha256:' + 'c' * 64, ['manage', 'dispose', '--execute'], b'K=1\n'), calls

    def test_after_dockers_own_failure_or_a_killed_cli_the_one_shot_is_stopped_and_removed(self):
        # the finding's input: the real oneshot, the CLI answering 125 (its --rm removal failed) or -9 (killed while
        # the container ran on), the container left labelled oneshot
        for code in (125, -9, -15):
            with self.subTest(answer=code):
                answer = answering(code)
                result, calls = self.oneshot(answer)
                self.assertIs(result, answer)
                self.assertEqual([args for args, _ in calls], [STOP_LEFTOVER, ('rm', '--force', 'oneshot-1')])
                self.assertTrue(all(kwargs.get('check') is False for _, kwargs in calls))
        self.assertEqual(install.DOCKER_RUN_FAILED, 125)

    def test_an_act_that_answered_its_own_exit_is_still_never_looked_for(self):
        # round 2's installer-1 repair, kept: after the act's own exit `docker run --rm` has removed its container
        for code in (0, 1, 2, 3, 126, 127, 137, 143):
            with self.subTest(answer=code):
                looked = []
                result, calls = self.oneshot(answering(code), inspect=lambda kind, name: looked.append(name))
                self.assertEqual((result.returncode, looked, calls), (code, [], []))

    def test_nothing_in_that_check_takes_the_answer_away(self):
        def failing(kind, name):
            raise install.InstallError('docker container inspect x failed (exit 1).')

        def stop_times_out(*args, **kwargs):
            if args[0] == 'stop':
                raise install.InstallError('docker stop did not finish within 40 s.')

        def rm_fails(*args, **kwargs):
            if args[0] == 'rm':
                raise install.InstallError('docker rm did not finish within 60 s.')
        for label, kwargs, expected in (
                ('a daemon error', {'inspect': failing}, []),
                ('a stop that does not finish', {'docker': stop_times_out}, [STOP_LEFTOVER, ('rm', '--force', 'oneshot-1')]),
                ('a removal that does not finish', {'docker': rm_fails}, [STOP_LEFTOVER, ('rm', '--force', 'oneshot-1')])):
            with self.subTest(label):
                answer = answering(125)
                result, calls = self.oneshot(answer, **kwargs)
                self.assertIs(result, answer)
                self.assertEqual([args for args, _ in calls], expected)
        # a SIGTERM or a Ctrl-C in the check: the one-shot removed at once, then the signal raised carrying the answer
        for label, signal_at, removed_as in (('a SIGTERM in the inspect', 'inspect', 'by its name'),
                                             ('a SIGTERM in the stop', 'stop', 'by its id'),
                                             ('a Ctrl-C in the stop', 'ctrl-c', 'by its id')):
            with self.subTest(label):
                answer, calls = answering(-9), []

                def inspect(kind, name, signal_at=signal_at):
                    calls.append(('inspect', name))
                    if signal_at == 'inspect':
                        raise install.Interrupted('SIGTERM')
                    return LEFTOVER

                def docker(*args, signal_at=signal_at, **kwargs):
                    calls.append(args)
                    if args[0] == 'stop' and signal_at in ('stop', 'ctrl-c'):
                        raise KeyboardInterrupt() if signal_at == 'ctrl-c' else install.Interrupted('SIGTERM')
                with mock.patch.object(install, 'run', return_value=answer), \
                        mock.patch.object(install, 'inspect', inspect), mock.patch.object(install, 'docker', docker):
                    try:
                        REAL_ONESHOT('sha256:' + 'c' * 64, ['manage', 'dispose', '--execute'], b'K=1\n')
                    except (install.Interrupted, KeyboardInterrupt) as error:
                        caught = error
                    else:
                        self.fail('the signal was not raised')
                self.assertIs(install.oneshot_answer_of(caught), answer)
                name = calls[0][1]
                self.assertEqual(calls[-1], ('rm', '--force', name if removed_as == 'by its name' else 'oneshot-1'))
        # the answer is found where a later error was raised over the signal (the RAM folder's wipe failing)
        signal = install.Interrupted('SIGTERM')
        signal.oneshot_answer = answer = answering(125)
        try:
            try:
                raise signal
            except install.Interrupted:
                raise install.InstallError('Root helper refused: the wipe')
        except install.InstallError as later:
            self.assertIs(install.oneshot_answer_of(later), answer)
        self.assertIsNone(install.oneshot_answer_of(install.InstallError('no answer here')))

    def test_through_the_manage_phase_the_record_is_kept_and_the_leftover_removed(self):
        import json
        for code in (125, -9):
            for interrupt in (None, 'inspect', 'stop'):
                with self.subTest(answer=code, signal_in=interrupt):
                    folder = self.tmp / f'{code}-{interrupt}'
                    folder.mkdir(mode=0o700)
                    world = LeftAfterAnswerWorld(folder, code=code, interrupt=interrupt)
                    with mock.patch.object(install, 'run', world.docker_run), \
                            self.assertRaises((install.InstallError, install.Interrupted)) as caught:
                        world.run('--command', 'dispose', '--dispose-step', 'execute', '--plan-id', r1.PLAN, '--by',
                                  'Ada Lovelace', '--approved-by', 'Grace Hopper')
                    error = caught.exception
                    if interrupt is None:
                        self.assertIsInstance(error, install.InstallError)
                        self.assertIn(f'manage dispose failed (exit {code})', str(error))
                    else:
                        self.assertIsInstance(error, install.Interrupted)
                    record = error.details
                    self.assertEqual((record['exit'], record['stdout']), (code, CERTIFICATE.decode()))
                    self.assertEqual(Path(record['log']).read_bytes(), CERTIFICATE + answering(code).stderr)
                    self.assertEqual(world.left, {})  # stopped and removed before the receipts' lock is let go
                    self.assertEqual([call[0] for call in world.calls][-1], 'rm')
                    json.dumps(record)  # the receipt can hold it
        # issue-enrolment's act keeps its record too, its setup code never kept
        (self.tmp / 'enrol').mkdir(mode=0o700)
        world = LeftAfterAnswerWorld(self.tmp / 'enrol', code=125, interrupt='stop')
        with mock.patch.object(install, 'run', world.docker_run), self.assertRaises(install.Interrupted) as caught:
            world.run('--command', 'issue-enrolment', '--username', 'platform-operator', '--reason-file', 'REASON',
                      '--by', 'Ada Lovelace')
        self.assertEqual((caught.exception.details['exit'], caught.exception.details['setup_code_kept']), (125, False))
        self.assertEqual(world.left, {})


# --- I3-4: the journal's flush test reads one moment, wherever UTC midnight falls ------------------------------------

JOURNAL_TEST_NAME = 'test_lines_are_appended_and_files_older_than_the_retention_are_deleted_and_counted'


def install_clock_crossing_midnight(start='2026-11-25T23:59:59.999500+00:00', step_ms=1):
    """(a patch, the moments it gave): install.py's clock (its dt) answering its k-th read with ``start`` + k *
    ``step_ms`` ms, so UTC midnight falls between its first two reads - the finding's input (refutation round 3,
    regression-9: the verifier's scripted clock)."""
    import datetime as dt
    import types
    first, given = dt.datetime.fromisoformat(start), []

    class CrossingDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            value = first + dt.timedelta(milliseconds=step_ms * len(given))
            given.append(value)
            return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)
    crossing = types.ModuleType('datetime')
    for name in dir(dt):
        if not name.startswith('__'):
            setattr(crossing, name, getattr(dt, name))
    crossing.datetime = CrossingDatetime
    return mock.patch.object(install, 'dt', crossing), given


class JournalMidnightTests(unittest.TestCase):
    def run_journal_test(self, test):
        """``test`` (a body of the journal's flush test) run as that test, with install's clock crossing midnight."""
        import test_install_r1_logs as logs

        class Case(logs.JournalFlushAndRetentionTests):
            pass
        setattr(Case, JOURNAL_TEST_NAME, test)
        result, (patch, given) = unittest.TestResult(), install_clock_crossing_midnight()
        with patch:
            Case(JOURNAL_TEST_NAME).run(result)
        return result, given

    def test_the_journal_flush_test_passes_when_utc_midnight_falls_inside_it(self):
        import test_install_r1_logs as logs
        test = getattr(logs.JournalFlushAndRetentionTests, JOURNAL_TEST_NAME)
        result, given = self.run_journal_test(test)
        self.assertEqual((result.testsRun, result.failures, result.errors), (1, [], []))
        self.assertEqual(given, [])  # its every read of install's clock was its own pinned moment
        # the control: the same body reading install's clock as it was fails on this clock, at its two dates
        result, given = self.run_journal_test(getattr(test, '__wrapped__', test))
        self.assertEqual((result.testsRun, len(result.failures), result.errors), (1, 1, []))
        self.assertIn("['oneshots-20261125.log', 'oneshots-20261126.log'] != ['oneshots-20261126.log']",
                      result.failures[0][1])
        self.assertEqual(sorted({moment.date().isoformat() for moment in given}), ['2026-11-25', '2026-11-26'])
        self.assertEqual(logs.JOURNAL_TEST_MOMENT.isoformat(), '2026-11-25T12:00:00+00:00')  # clear of midnight


class RestoreGuideTests(unittest.TestCase):
    """INSTALL.md's restore procedure is the sequence the tests above run, for both hosts."""

    def test_the_guide_gives_one_sequence_for_both_hosts(self):
        text = (Path(__file__).resolve().parent / 'INSTALL.md').read_text(encoding='utf-8')
        start = text.index('**Restoring the database.**')
        restore = ' '.join(text[start:text.index('\n## ', start)].split())
        for said in ('`docker stop --time 3600 cpt-studio-worker`, then `docker stop --time 30 cpt-studio-web`',
                     'Wait two minutes after the worker stopped', 'with no pair at all the replay runs too',
                     'rerun `app` with the `--coding-mode`', '`docker start cpt-studio-web cpt-studio-worker`',
                     'On a fresh server, `app`, and only then `https-vhost`', '`--coding-mode disabled`',
                     'must keep the same secret key'):
            self.assertIn(said, restore)
        self.assertNotIn('with no pair at all it is refused', restore)
        self.assertNotIn('install the revision with `app` before `https-vhost` opens the site, then replay', restore)


if __name__ == '__main__':
    unittest.main()
