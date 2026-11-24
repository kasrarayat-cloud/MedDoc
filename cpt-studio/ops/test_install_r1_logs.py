"""Release 1: deploys stop deleting the application's logs (RELEASE-1-SPEC A13). Before retire_parked removes a parked
container its output is copied, ids only, into a root-only file; one-shots and helpers each leave one journal line;
copies and journals older than the retention are deleted and counted. The root helper's bodies run here in-process on
temporary folders (test_install.run_body); Docker is a fake, under test_install's host guard.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r1_logs -v
"""
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import test_install  # noqa: E402
from test_install import FakeOwnership, TemporaryDirectoryTest, guard_host, release_host, run_body  # noqa: E402
from test_install_bluegreen import (IMAGE, OLD, OLD_IMAGE, REVISION, WEB, WORKER, BlueGreenWorld, run_app,  # noqa: E402
                                    switch_back_args)

APP_ROOT = Path(__file__).resolve().parents[1]
UUID = '0f8fad5b-d9cb-469f-a165-70867728950e'
MARKER = 'ZZ-TEXT-MARKER'
REQUEST_ID = '0123456789abcdef0123456789abcdef'
ACCESS = (f'[24/Nov/2026:10:00:01 +0000] 203.0.113.9 "GET /api/encounters/{UUID} HTTP/1.1" 200 812 41ms {REQUEST_ID} '
          f'{UUID}')
ACCESS_POST = f'[24/Nov/2026:10:00:02 +0000] 203.0.113.9 "POST /api/encounters/{UUID}/reports HTTP/1.1" 201 66 210ms - -'
BOOT = '[2026-11-24 10:00:00 +0000] [7] [INFO] Booting worker with pid: 7'


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


def stamped(seconds, line, fraction='123456789'):
    return f'2026-11-24T10:00:{seconds:02d}.{fraction}Z {line}'


class KeptFormatTests(unittest.TestCase):
    """Only lines in a format whose variable parts hold ids, numbers, times, addresses and fixed words are copied."""

    def test_access_and_life_cycle_lines_are_kept_and_a_traceback_and_text_are_dropped_and_counted(self):
        stdout = '\n'.join([stamped(1, ACCESS), stamped(2, ACCESS_POST),
                            stamped(3, f'[24/Nov/2026:10:00:03 +0000] 203.0.113.9 "GET /api/encounters/{MARKER} '
                                       'HTTP/1.1" 404 9 1ms - -')]).encode()
        stderr = '\n'.join([stamped(0, BOOT), stamped(4, 'Internal Server Error: /api/encounters'),
                            stamped(4, 'Traceback (most recent call last):'),
                            stamped(4, f'psycopg.errors.UniqueViolation: DETAIL:  Key (title)=({MARKER}) exists.'),
                            'a line with no timestamp']).encode()
        kept, dropped = install.ids_only_lines('web', stdout, stderr)
        self.assertEqual(kept, [stamped(0, BOOT), stamped(1, ACCESS), stamped(2, ACCESS_POST),
                                stamped(4, 'Internal Server Error: /api/encounters')])
        self.assertEqual(dropped, 4)
        self.assertNotIn(MARKER, '\n'.join(kept))

    def test_worker_messages_are_kept_with_their_ids_and_fixed_words_alone(self):
        lines = [f'round {UUID}: the document was not sent (unreadable)',
                 f'round {UUID}: the document was not sent ({MARKER} page 2)',
                 f'stage code failed for job {UUID}', 'Traceback (most recent call last):',
                 f'  File "/app/studio/jobs.py", line 1, in x: {MARKER}', 'CPT Studio worker started.']
        kept, dropped = install.ids_only_lines('worker', '\n'.join(stamped(i, line) for i, line in enumerate(lines)).encode())
        self.assertEqual([line.split(' ', 1)[1] for line in kept], [lines[0], lines[2], lines[5]])
        self.assertEqual(dropped, 3)
        # a role with no format listed (the converter's messages are Lane 5's) keeps nothing: fail closed
        self.assertEqual(install.ids_only_lines('converter', stamped(1, 'converted 1 file').encode()), ([], 1))

    def test_a_path_is_kept_only_when_every_segment_is_a_route_word_an_id_or_a_hashed_static_name(self):
        def kept(path):
            line = f'[24/Nov/2026:10:00:01 +0000] 127.0.0.1 "GET {path} HTTP/1.1" 200 1 1ms - -'
            return any(pattern.fullmatch(line) for pattern in install.KEPT_LOG_FORMATS['web'])
        for path in ('/', '/health/', f'/ops/encounters/{UUID}/original', '/ops/activity/sign-ins',
                     '/static/studio/app.0123456789ab.js', '/static/studio/fonts/inter.0123456789ab.woff2'):
            self.assertTrue(kept(path), path)
        for path in ('/api/encounters/jane-doe', '/static/studio/app.js', '/wp-login.php', '/api/encounters/1 2',
                     f'/api/encounters/{UUID}?view=1', '/.env', '/API/session'):
            self.assertFalse(kept(path), path)

    def test_the_route_words_are_every_literal_segment_of_both_urlconfs(self):
        words = set()
        for name in ('urls.py', 'urls_admin.py'):
            text = (APP_ROOT / 'cptstudio' / name).read_text(encoding='utf-8')
            for route in re.findall(r"path\('([^']*)'", text):
                words |= {segment for segment in route.split('/') if segment and not segment.startswith('<')}
        self.assertLessEqual(words, set(install.ROUTE_WORDS) | {'ops'})
        self.assertIn('static', install.ROUTE_WORDS)


class KeepContainerLogTests(TemporaryDirectoryTest):
    """keep_container_log: docker logs, the ids-only filter, a root-only copy through the root helper - its body run
    here on a temporary /var/log - and a record of counts and a sha256, never a line."""

    def setUp(self):
        super().setUp()
        self.host_log = self.tmp / 'var-log'
        self.host_log.mkdir()
        self.owner = FakeOwnership()

    def helper(self, body, params, *, mounts, **kwargs):
        """run_helper with the body run here: /host-log is the temporary /var/log, /in/kept the RAM-only file."""
        paths = {'/host-log': str(self.host_log)}
        kept = [mount.split(',')[1][4:] for mount in mounts if mount.endswith('dst=/in/kept,readonly')]
        if kept:
            paths['/in/kept'] = kept[0]
            self.handed = Path(kept[0])
            self.handed_mode = stat.S_IMODE(os.stat(kept[0]).st_mode)
        self.assertIn(install.LOG_MOUNT, mounts)
        answer = run_body(body, params, paths, fake_os=self.owner)
        if answer.get('error'):
            raise install.InstallError(f'Root helper refused: {answer["error"]}')
        return answer

    def keep(self, stdout, stderr=b'', returncode=0):
        logs = SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
        with mock.patch.object(install, 'docker', return_value=logs) as docker, \
                mock.patch.object(install, 'run_helper', self.helper):
            record = install.keep_container_log({'Id': 'c' * 64}, 'web', REVISION)
        self.assertEqual(docker.call_args[0], ('logs', '--timestamps', 'c' * 64))
        return record

    def test_the_copy_holds_the_kept_lines_alone_root_only_and_the_record_holds_no_line(self):
        stdout = '\n'.join([stamped(1, ACCESS), stamped(2, f'{MARKER} plain text')]).encode()
        stderr = '\n'.join([stamped(0, BOOT), stamped(3, 'Traceback (most recent call last):'),
                            stamped(3, f'ValueError: {MARKER}')]).encode()
        record = self.keep(stdout, stderr)
        copies = sorted((self.host_log / 'cpt-studio' / 'containers').iterdir())
        self.assertEqual(len(copies), 1)
        self.assertRegex(copies[0].name, rf'^web-{REVISION[:12]}-\d{{8}}T\d{{6}}Z\.log$')
        data = copies[0].read_bytes()
        self.assertEqual(data.decode(), stamped(0, BOOT) + '\n' + stamped(1, ACCESS) + '\n')
        self.assertNotIn(MARKER.encode(), data)
        self.assertEqual(record, {'file': f'{install.LOG_DIR}/containers/{copies[0].name}',
                                  'sha256': hashlib.sha256(data).hexdigest(), 'kept': 2, 'dropped': 3,
                                  'bytes': len(data)})
        self.assertNotIn(MARKER, json.dumps(record))
        self.assertNotIn(REQUEST_ID, json.dumps(record))
        # root-only: the file 0600 and both folders 0700, root-owned (the helper's chown, recorded)
        self.assertEqual(stat.S_IMODE(os.stat(copies[0]).st_mode), 0o600)
        self.assertEqual(self.owner.owners[str(copies[0])], (0, 0))
        for folder in (self.host_log / 'cpt-studio', self.host_log / 'cpt-studio' / 'containers'):
            self.assertEqual(stat.S_IMODE(os.stat(folder).st_mode), 0o700)
            self.assertEqual(self.owner.owners[str(folder)], (0, 0))
        # the copy travelled as a RAM-only file under /dev/shm, private, and is gone
        self.assertTrue(str(self.handed).startswith('/dev/shm/'))
        self.assertEqual(self.handed_mode, 0o600)
        self.assertFalse(self.handed.exists())

    def test_a_log_that_cannot_be_read_or_a_folder_that_is_not_root_only_is_refused(self):
        with self.assertRaisesRegex(install.InstallError, 'left in place'):
            self.keep(b'', returncode=1)
        (self.host_log / 'cpt-studio').mkdir(mode=0o755)  # not root 0700: never written into
        with self.assertRaisesRegex(install.InstallError, 'not a root-owned 0700 directory'):
            self.keep(stamped(1, ACCESS).encode())


class RetireParkedTests(TemporaryDirectoryTest):
    """Each parked container's log is copied before its removal, on the app path and on the switch-back path; a copy
    that fails removes nothing."""

    def test_every_copy_is_made_before_any_removal_and_a_failed_copy_removes_nothing(self):
        events = []
        parked = {'worker': {'id': 'worker-1', 'revision': OLD}, 'web': {'id': 'web-1', 'revision': OLD}}

        def keep(container, role, revision=None):
            events.append(('keep', container['Id'], role, revision))
            return {'kept': 1}

        def docker(*args, **kwargs):
            events.append(tuple(args[:1]) + (args[-1],))
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        with mock.patch.multiple(install, keep_container_log=keep, docker=docker):
            self.assertEqual(install.retire_parked(parked), {'worker': {'kept': 1}, 'web': {'kept': 1}})
        self.assertEqual(events, [('keep', 'worker-1', 'worker', OLD), ('keep', 'web-1', 'web', OLD),
                                  ('rm', 'worker-1'), ('rm', 'web-1')])
        events.clear()

        def failing(container, role, revision=None):
            events.append(('keep', container['Id']))
            if role == 'web':
                raise install.InstallError('the disk is full')
            return {'kept': 1}
        with mock.patch.multiple(install, keep_container_log=failing, docker=docker), \
                self.assertRaisesRegex(install.InstallError, 'left in place'):
            install.retire_parked(parked)
        self.assertEqual([event for event in events if event[0] == 'rm'], [])

    def test_the_app_and_switch_back_paths_keep_each_parked_log_before_removing_it(self):
        world = BlueGreenWorld(self.tmp)
        details, error = run_app(world)
        self.assertIsNone(error, error and str(error))
        kept = [event for event in world.events if event[0] in ('keep-log', 'rm')]
        self.assertEqual([event[0] for event in kept], ['keep-log', 'keep-log', 'rm', 'rm'])
        self.assertEqual(sorted(event[2] for event in kept if event[0] == 'keep-log'), ['web', 'worker'])
        self.assertEqual(sorted(details['logs_kept']), ['web', 'worker'])
        # switch-back: this revision's parked pair, kept then removed (B9)
        world = BlueGreenWorld(self.tmp, live=9151, serving=(REVISION, IMAGE))
        install.write_receipt(self.tmp, 'app', {'phase': 'app', 'ok': True, 'revision': REVISION, 'details': {
            'replaced': {'web': {'id': 'web-old', 'image': OLD_IMAGE, 'revision': OLD},
                         'worker': {'id': 'worker-old', 'image': OLD_IMAGE, 'revision': OLD}}}})
        patches = world.patches()
        for patcher in patches:
            patcher.start()
        try:
            details = install.phase_switch_back(install.Context(switch_back_args(self.tmp), self.tmp))
        finally:
            for patcher in reversed(patches):
                patcher.stop()
        kept = [event for event in world.events if event[0] in ('keep-log', 'rm')]
        self.assertEqual([event[0] for event in kept], ['keep-log', 'keep-log', 'rm', 'rm'])
        self.assertEqual(sorted(details['logs_kept']), ['web', 'worker'])


class OneShotJournalTests(unittest.TestCase):
    """One journal line per one-shot and helper run, with no argument value and no output in it."""

    def setUp(self):
        install.journal_begin('provision', {'declaration': 'docs/foundation/mutations/x.md', 'declaration_commit': 'd' * 40})

    def test_each_one_shot_appends_exactly_one_line_without_values_or_output(self):
        answer = SimpleNamespace(returncode=3, stdout=f'printed {MARKER}'.encode(), stderr=MARKER.encode())
        with mock.patch.object(install, 'run', return_value=answer), mock.patch.object(install, 'inspect',
                                                                                       return_value=None):
            install.oneshot(IMAGE, ['manage', 'provision', '--owner-username', 'zz-argument-value'], b'ENV=1\n',
                            by='Ada Lovelace')
            install.oneshot(IMAGE, ['migrate'], b'')
            install.oneshot(IMAGE, ['manage', 'shell', '-c', f'print({MARKER!r})'], b'', what='Reading the queue')
        lines = [json.loads(line) for line in install.JOURNAL['lines']]
        self.assertEqual(len(lines), 3)
        self.assertEqual([(line['kind'], line['what'], line['exit']) for line in lines],
                         [('oneshot', 'manage provision', 3), ('oneshot', 'migrate', 3), ('oneshot', 'Reading the queue', 3)])
        self.assertEqual(lines[0]['by'], 'Ada Lovelace')
        for line in lines:
            self.assertEqual((line['phase'], line['declaration'], line['commit']),
                             ('provision', 'docs/foundation/mutations/x.md', 'd' * 40))
            self.assertRegex(line['at'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        text = '\n'.join(install.JOURNAL['lines'])
        for value in (MARKER, 'zz-argument-value', 'ENV=1', 'printed'):
            self.assertNotIn(value, text)

    def test_each_helper_run_appends_exactly_one_line_and_the_journal_write_none(self):
        answer = SimpleNamespace(returncode=0, stdout=b'{"paths": {}}\n', stderr=b'')
        with mock.patch.object(install.subprocess, 'run', return_value=answer), \
                mock.patch.object(install, 'remove_helper'):
            install.run_helper(install.H_STAT, {'paths': ['/etc/zz-param-value']}, mounts=[install.ROOT_MOUNT])
            install.run_helper(install.H_JOURNAL, {}, mounts=[], journal_run=False)
        lines = [json.loads(line) for line in install.JOURNAL['lines']]
        self.assertEqual([(line['kind'], line['what'], line['exit']) for line in lines], [('helper', 'stat', 0)])
        self.assertNotIn('zz-param-value', '\n'.join(install.JOURNAL['lines']))

    def test_a_run_that_timed_out_is_still_one_line(self):
        with mock.patch.object(install, 'run', side_effect=install.InstallError('did not finish')), \
                mock.patch.object(install, 'inspect', return_value=None), self.assertRaises(install.InstallError):
            install.oneshot(IMAGE, ['migrate'], b'')
        self.assertEqual([json.loads(line)['exit'] for line in install.JOURNAL['lines']], ['timeout'])

    def test_a_label_is_never_free_text(self):
        install.journal('oneshot', 'x\n{"forged": 1}', 0, by='a\nb')
        line = json.loads(install.JOURNAL['lines'][-1])
        self.assertNotIn('\n', line['what'] + line['by'])
        self.assertEqual(len(install.JOURNAL['lines'][-1].splitlines()), 1)


class JournalFlushAndRetentionTests(TemporaryDirectoryTest):
    """The journal's lines appended root-only to their date's file; copies and journals older than the retention
    deleted and counted - the helper's body run here."""

    def setUp(self):
        super().setUp()
        self.host_log = self.tmp / 'var-log'
        self.host_log.mkdir()
        self.owner = FakeOwnership()

    def helper(self, body, params, *, mounts, journal_run=True, **kwargs):
        self.assertIs(journal_run, False)  # the journal's own write is not a line of it
        self.assertEqual(mounts, [install.LOG_MOUNT])
        answer = run_body(body, params, {'/host-log': str(self.host_log)}, fake_os=self.owner)
        if answer.get('error'):
            raise install.InstallError(f'Root helper refused: {answer["error"]}')
        return answer

    def test_lines_are_appended_and_files_older_than_the_retention_are_deleted_and_counted(self):
        base, containers = self.host_log / 'cpt-studio', self.host_log / 'cpt-studio' / 'containers'
        # a first flush makes the folders root 0700
        install.journal_begin('db')
        install.journal('helper', 'stat', 0)
        with mock.patch.object(install, 'run_helper', self.helper):
            first = test_install.REAL_FLUSH_JOURNAL()
        self.assertTrue(first['written'], first)
        old = install.utc_now()  # dates in names: one well inside the retention, two outside it
        today = old[:10].replace('-', '')
        for name in ('oneshots-20200101.log', 'oneshots-20200102.log'):
            (base / name).write_text('{}\n')
        for name in ('web-aaaaaaaaaaaa-20200101T000000Z.log', f'worker-bbbbbbbbbbbb-{today}T000000Z.log', 'notes.txt'):
            (containers / name).write_text('x\n')
        install.journal_begin('app', {'declaration': 'docs/foundation/mutations/x.md', 'declaration_commit': 'd' * 40})
        install.journal('oneshot', 'migrate', 0)
        install.journal('helper', 'read-file', 0)
        with mock.patch.object(install, 'run_helper', self.helper):
            record = test_install.REAL_FLUSH_JOURNAL()
        self.assertEqual(record['pruned'], {'oneshots': 2, 'containers': 1})
        self.assertEqual(record['files'], {f'{install.LOG_DIR}/oneshots-{today}.log': 2})
        self.assertEqual((record['lines'], record['overflow'], record['kept_days']), (2, 0, install.LOG_KEEP_DAYS))
        self.assertEqual(sorted(path.name for path in base.iterdir() if path.is_file()), [f'oneshots-{today}.log'])
        self.assertEqual(sorted(path.name for path in containers.iterdir()),
                         ['notes.txt', f'worker-bbbbbbbbbbbb-{today}T000000Z.log'])
        journal = base / f'oneshots-{today}.log'
        lines = [json.loads(line) for line in journal.read_text().splitlines()]
        self.assertEqual([line['what'] for line in lines], ['stat', 'migrate', 'read-file'])
        self.assertEqual(stat.S_IMODE(os.stat(journal).st_mode), 0o600)
        self.assertEqual(install.JOURNAL['lines'], [])

    def test_nothing_ran_nothing_written_and_a_failed_or_odd_answer_is_said_never_raised(self):
        install.journal_begin('verify')
        self.assertIsNone(test_install.REAL_FLUSH_JOURNAL())
        install.journal('helper', 'stat', 0)
        with mock.patch.object(install, 'run_helper', side_effect=install.InstallError('Root helper refused: x')):
            record = test_install.REAL_FLUSH_JOURNAL()
        self.assertEqual((record['written'], record['lines']), (False, 1))
        install.journal('helper', 'stat', 0)
        with mock.patch.object(install, 'run_helper', return_value={'appended': {'20990101': 1}, 'pruned': {}}):
            record = test_install.REAL_FLUSH_JOURNAL()
        self.assertEqual(record['written'], False)
        self.assertIn('no answer it could be judged by', record['why'])

    def test_main_records_the_journal_in_the_receipt(self):
        receipts = self.tmp / 'receipts'
        with mock.patch.object(install, 'check_door', return_value={'declaration': 'd.md', 'declaration_commit': 'd' * 40}), \
                mock.patch.object(install, 'check_tree', return_value={'mode': 'exact'}), \
                mock.patch.dict(install.PHASES, {'verify': lambda ctx: (install.journal('helper', 'stat', 0),
                                                                        {'summary': 'ok'})[1]}), \
                mock.patch('sys.stdout'):
            code = install.main(['--phase', 'verify', '--revision', REVISION, '--receipts', str(receipts)])
        self.assertEqual(code, 0)
        record = json.loads(sorted(receipts.glob('verify-*.json'))[-1].read_text())
        self.assertEqual(record['oneshot_log'], {'written': False, 'why': 'the test host guard keeps the journal',
                                                 'lines': 1})
        self.assertEqual(json.loads(test_install.JOURNALS_FLUSHED[-1][0])['phase'], 'verify')



# A failing container's output as Docker gives it: a traceback, then a DETAIL line that holds document text.
SEEDED_MARKER = b'ZZ-TEXT-MARKER'
SEEDED_LOGS = (b'2026-11-24T10:00:00.000000000Z Traceback (most recent call last):\n',
               b'2026-11-24T10:00:00.100000000Z psycopg.errors.UniqueViolation: duplicate key\n'
               b'2026-11-24T10:00:00.200000000Z DETAIL:  Key (title)=(ZZ-TEXT-MARKER colonoscopy, Jane Doe) already '
               b'exists.\n')


def seeded(world):
    """``world`` whose docker logs answers SEEDED_LOGS for every container."""
    real = world.docker

    def docker(*args, **kwargs):
        if args[0] == 'logs':
            world.act('logs', args[-1])
            return SimpleNamespace(returncode=0, stdout=SEEDED_LOGS[0], stderr=SEEDED_LOGS[1])
        return real(*args, **kwargs)
    world.docker = docker
    return world


def removed_without_a_copy(events) -> list:
    kept, out = set(), []
    for event in events:
        if event[0] == 'keep-log':
            kept.add(event[1])
        elif event[0] == 'rm' and event[1] not in kept:
            out.append(event[1])
    return out


class UndoPathLogTests(TemporaryDirectoryTest):
    """Refutation, installer lens A-2: an undo kept the failed container's last 40 raw lines in the receipts folder -
    a seeded DETAIL line holding document text survived - and removed containers with no ids-only copy."""

    def world(self, cls, label):
        folder = self.tmp / label
        folder.mkdir()
        return seeded(cls(folder))

    def test_an_undo_keeps_no_raw_line_in_the_receipts_folder(self):
        import test_install_r2 as r2
        for label, world, role in (('s1', self.world(BlueGreenWorld, 's1'), 'web'),
                                   ('s4', self.world(r2.World, 's4'), 'worker')):
            with self.subTest(label):
                world.unhealthy.add(install.INCOMING_WEB if label == 's1' else WORKER)
                details, error = run_app(world)
                self.assertIsInstance(error, install.InstallError)
                logs = list(world.tmp.glob('*.log'))
                self.assertTrue(logs)
                self.assertEqual([path.name for path in logs if SEEDED_MARKER in path.read_bytes()], [])
                tails = [path for path in logs if path.name.endswith(('-incoming-web-failed.log', '-worker-failed.log'))]
                self.assertTrue(tails, [path.name for path in logs])
                for path in tails:
                    text = path.read_text()
                    self.assertTrue(text.startswith('# the last 200 lines of '), text[:80])
                    self.assertIn('0 kept, 3 dropped', text)

    def test_every_removal_on_every_undo_path_keeps_its_ids_only_copy_first(self):
        import test_install_r2 as r2
        cases = []
        world = self.world(BlueGreenWorld, 's1')
        world.unhealthy.add(install.INCOMING_WEB)
        cases.append(('S1', world, run_app))
        world = self.world(BlueGreenWorld, 's3')
        world.fail[('https', 9151)] = install.InstallError('https://cpt.quillmd.com/health/ did not serve it')
        cases.append(('S3 after the reload', world, run_app))
        world = self.world(r2.World, 's4')
        world.unhealthy.add(WORKER)
        cases.append(('S4', world, run_app))
        world = seeded(r2.switched_back_world(self.tmp / 'sb' if (self.tmp / 'sb').mkdir() is None else None))
        world.fail[('https', 9150)] = install.InstallError('https://cpt.quillmd.com/health/ did not serve it')
        cases.append(('switch-back', world, r2.run_switch_back))
        for label, world, run in cases:
            with self.subTest(label):
                details, error = run(world)
                self.assertIsInstance(error, install.InstallError)
                removals = [event for event in world.events if event[0] == 'rm']
                self.assertTrue(removals, f'{label}: nothing was removed')
                self.assertEqual(removed_without_a_copy(world.events), [])

    def test_the_in_place_swap_undo_keeps_ids_only_tails_and_copies_before_it_removes(self):
        names = {install.SERVICES['web']: 'web', install.SERVICES['worker']: 'worker'}
        live = {name: {'Id': f'old-{role}', 'Image': OLD_IMAGE, 'State': {'Running': True},
                       'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role, install.REVISION_LABEL: OLD}}}
                for name, role in names.items()}
        events = []

        def fake_docker(*args, **kwargs):
            events.append((args[0], args[-1]))
            if args[0] == 'rename':
                live[args[2]] = live.pop(args[1])
            elif args[0] == 'run':
                name = args[args.index('--name') + 1]
                live[name] = {'Id': f'new-{names[name]}', 'Image': IMAGE, 'State': {'Running': True},
                              'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: names[name],
                                                    install.REVISION_LABEL: REVISION}}}
            elif args[0] == 'rm':
                live.pop(next(name for name, c in live.items() if c['Id'] == args[-1]))
            elif args[0] == 'logs':
                return SimpleNamespace(returncode=0, stdout=SEEDED_LOGS[0], stderr=SEEDED_LOGS[1])
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

        def keep(container, role, revision=None):
            events.append(('keep-log', container['Id']))
            return {'kept': 0}

        def wait(role, revision, image_id, **kwargs):
            if role == 'worker':
                raise install.InstallError('cpt-studio-worker did not become ready')
            return {'id': 'new-web'}
        ctx = install.Context(SimpleNamespace(phase='app', revision=REVISION), self.tmp)
        with mock.patch.multiple(install, inspect=lambda kind, name: live.get(name), docker=fake_docker,
                                 wait_service=wait, keep_container_log=keep, stage_kinds_of=mock.Mock(return_value=[]),
                                 close_undone_stages=mock.Mock(return_value={'closed': 0, 'kinds': [], 'hazards': {},
                                                                             'relabel': []}),
                                 put_back_states=mock.Mock(return_value={'encounters': 0, 'changed': {}})), \
                self.assertRaises(install.InstallError):
            install.swap_services(ctx, IMAGE, b'', 'disabled', '')
        self.assertEqual([path.name for path in self.tmp.glob('*.log') if SEEDED_MARKER in path.read_bytes()], [])
        removed = [event[1] for event in events if event[0] == 'rm']
        self.assertEqual(sorted(removed), ['new-web', 'new-worker'])
        for container in removed:  # each copy made before its removal
            self.assertLess(events.index(('keep-log', container)), events.index(('rm', container)))
        self.assertEqual(sorted(c['Id'] for c in live.values()), ['old-web', 'old-worker'])  # the old pair is back

    def test_a_removal_whose_copy_fails_leaves_the_container_in_place(self):
        container = {'Id': 'w' * 64, 'Image': IMAGE, 'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'worker',
                                                                            install.REVISION_LABEL: REVISION}}}
        calls = []
        with mock.patch.object(install, 'inspect', return_value=container), \
                mock.patch.object(install, 'docker', side_effect=lambda *a, **k: calls.append(a) or SimpleNamespace(
                    returncode=0, stdout=b'', stderr=b'')), \
                mock.patch.object(install, 'keep_container_log',
                                  side_effect=install.InstallError('the copy could not be written')), \
                self.assertRaisesRegex(install.InstallError, 'could not be written'):
            install.remove_service_container(install.SERVICES['worker'], 'worker')
        self.assertEqual([call[0] for call in calls], ['stop'])  # stopped, never removed


if __name__ == '__main__':
    unittest.main()
