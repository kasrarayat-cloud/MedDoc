"""The release-2 bench's own tests (RELEASE-2-SPEC R2-2): no database, no browser, in CI's ops suite.

They cover every refusal arm (the pure check, the bench's settings, the module-level refusal before a test database
could be made, the protocol driver), the lock and the never-overwritten output, benchdata's equal bytes twice, the
barcode (encode, decode, the page's decoder against Python's, and the barcode read back out of a scan's pixels), that
bench.cjs and proxy.cjs parse, the judge's arithmetic, its C5 floors and its INVALID cases, the office model's
arithmetic against the tree's own vhost, and that ops/bench never ships in the image and is never discovered as tests.
"""
import contextlib
import copy
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

OPS = Path(__file__).resolve().parent
APP = OPS.parent
BENCH = OPS / 'bench'


def bench_module(name):
    if str(BENCH) not in sys.path:
        sys.path.insert(0, str(BENCH))
    spec = importlib.util.spec_from_file_location(f'cpt_bench_{name}', BENCH / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BD = bench_module('benchdata')
RUN = bench_module('bench_run')
JUDGE = bench_module('judge')
NODE = shutil.which('node')
GOOD_DB = {'HOST': '127.0.0.1', 'PORT': '55461', 'NAME': 'cptstudio_ci', 'TEST': {'NAME': 'test_cptstudio_x'}}


class BenchRefusesAnythingButTheThrowawayServerTests(unittest.TestCase):
    def test_the_throwaway_server_with_a_test_database_is_accepted(self):
        self.assertEqual(RUN.refusals(GOOD_DB, 'disabled', ['http://127.0.0.1:9301']), [])

    def test_each_refusal_arm(self):
        for change, expected in (
                ({'HOST': 'localhost'}, 'host'), ({'HOST': '10.0.0.5'}, 'host'),
                ({'PORT': '55451'}, "55451, live's"), ({'PORT': '5432'}, 'port is not 55461'),
                ({'TEST': {'NAME': 'cptstudio'}}, 'test_cptstudio_'),
                ({'TEST': {'NAME': 'test_other'}}, 'test_cptstudio_')):
            db = {**GOOD_DB, **change}
            with self.subTest(change=change):
                why = RUN.refusals(db, 'disabled')
                self.assertTrue(why and any(expected in w for w in why), why)
        self.assertIn('CODING_MODE is not disabled', RUN.refusals(GOOD_DB, 'live'))
        self.assertIn('CODING_MODE is not disabled', RUN.refusals(GOOD_DB, 'replay'))
        for url in ('http://0.0.0.0:9300', 'http://10.1.2.3:9300', 'https://127.0.0.1:9300', 'http://cpt.quillmd.com'):
            with self.subTest(url=url):
                self.assertTrue(any('not loopback' in w for w in RUN.refusals(GOOD_DB, 'disabled', [url])))

    def test_live_s_port_is_named_and_never_accepted_as_a_test_database(self):
        why = RUN.refusals({**GOOD_DB, 'PORT': 55451}, 'disabled')
        self.assertEqual(len([w for w in why if '55451' in w]), 1)

    def _environ(self, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('BENCH_', 'DJANGO_SETTINGS'))}
        env.update({'CPT_STUDIO_SECRET_KEY': 'synthetic-test-only', 'CPT_STUDIO_DB_HOST': '127.0.0.1',
                    'CPT_STUDIO_DB_PORT': '55461', 'CPT_STUDIO_CODING_MODE': 'disabled',
                    'CPT_STUDIO_STATE_DIR': tempfile.gettempdir(), 'PYTHONDONTWRITEBYTECODE': '1',
                    'PYTHONPATH': f'{APP}:{BENCH}'})
        env.update(extra)
        return env

    def _run(self, code, **extra):
        return subprocess.run([sys.executable, '-B', '-c', code], cwd=APP, env=self._environ(**extra),
                              capture_output=True, text=True, timeout=120)

    def test_the_bench_settings_refuse_another_database(self):
        load = 'import bench_settings'
        ok = self._run(load, BENCH_DB='test_cptstudio_x', BENCH_STATIC='/nonexistent', BENCH_ORIGINALS='/nonexistent')
        self.assertEqual(ok.returncode, 0, ok.stderr[-800:])
        for extra, words in (({'BENCH_DB': 'cptstudio'}, 'test_cptstudio_'),
                             ({'BENCH_DB': 'test_cptstudio_x', 'CPT_STUDIO_DB_PORT': '55451'}, '127.0.0.1:55461'),
                             ({'BENCH_DB': 'test_cptstudio_x', 'CPT_STUDIO_DB_HOST': 'db.example'}, '127.0.0.1:55461'),
                             ({'BENCH_DB': 'test_cptstudio_x', 'CPT_STUDIO_CODING_MODE': 'live'}, 'CODING_MODE')):
            with self.subTest(extra=extra):
                done = self._run(load, BENCH_STATIC='/nonexistent', BENCH_ORIGINALS='/nonexistent', **extra)
                self.assertNotEqual(done.returncode, 0)
                self.assertIn('bench_settings refused', done.stderr)
                self.assertIn(words, done.stderr)

    def test_the_round_refuses_at_import_before_any_test_database_is_made(self):
        code = 'import django; django.setup(); import bench_run'
        for parts in ({'BENCH_PARTS': 'server'}, {'BENCH_PARTS': ''}, {}):  # bench[7]: a missing BENCH_PARTS too
            ok = self._run(code, DJANGO_SETTINGS_MODULE='cptstudio.settings', CPT_STUDIO_TEST_DB_SUFFIX='x', **parts)
            self.assertEqual(ok.returncode, 0, ok.stderr[-800:])
            for extra in ({'CPT_STUDIO_DB_PORT': '55451'}, {'CPT_STUDIO_DB_HOST': 'db.example'},
                          {'CPT_STUDIO_CODING_MODE': 'live'}):
                with self.subTest(parts=parts, extra=extra):
                    done = self._run(code, DJANGO_SETTINGS_MODULE='cptstudio.settings', CPT_STUDIO_TEST_DB_SUFFIX='x',
                                     **parts, **extra)
                    self.assertNotEqual(done.returncode, 0)
                    self.assertIn('bench refused', done.stderr)

    def test_the_protocol_driver_refuses_the_same_settings(self):
        # The tree named does not exist: were the refusal missing, the driver would try to run a round there and fail
        # differently (and write its log first) - and nothing could reach any database.
        with tempfile.TemporaryDirectory() as out:
            for extra in ({'CPT_STUDIO_DB_PORT': '55451'}, {'CPT_STUDIO_TEST_DB_SUFFIX': ''},
                          {'CPT_STUDIO_CODING_MODE': 'live'}):
                with self.subTest(extra=extra):
                    env = self._environ(**{'CPT_STUDIO_TEST_DB_SUFFIX': 'x', **extra})
                    done = subprocess.run([sys.executable, '-B', str(BENCH / 'bench_run.py'), '--tree',
                                           'A=/nonexistent/bench-tree', '--order', 'A:1', '--group', 'server',
                                           '--out', out, '--ports', '9300-9349', '--max-load', '999',
                                           '--wait-minutes', '0'],
                                          env=env, capture_output=True, text=True, timeout=120)
                    self.assertEqual(done.returncode, 2, done.stderr[-600:])
                    self.assertIn('refused', done.stderr)
                    self.assertFalse((Path(out) / 'protocol.log').exists())


class BenchProtocolTests(unittest.TestCase):
    def test_ports_come_from_a_declared_range_and_are_checked_free(self):
        self.assertEqual(RUN.parse_ports('9300-9349'), range(9300, 9350))
        for bad in ('', '9300', '80-90', '9349-9300', '1000-2000', '9300-9600'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                RUN.parse_ports(bad)
        import socket
        with socket.socket() as busy:
            busy.bind(('127.0.0.1', 0))
            port = busy.getsockname()[1]
            busy.listen()
            pool = RUN.PortPool(range(port, port + 1))
            with self.assertRaises(RuntimeError):
                pool.take()

    def test_a_round_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as out:
            target = RUN.claim_output(Path(out), 'A', 1, ['open', 'lists'])
            self.assertEqual(target.name, 'A-r1-open+lists.json')
            target.write_text('{}')
            with self.assertRaises(FileExistsError):
                RUN.claim_output(Path(out), 'A', 1, ['open', 'lists'])
            self.assertEqual(RUN.claim_output(Path(out), 'A', 2, ['open', 'lists']).name, 'A-r2-open+lists.json')
        for bad in ('', '1A', 'A-1', 'A/B', 'x' * 17):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                RUN.out_name(bad, 1, ['open'])
        self.assertEqual(RUN.out_name('A', 101, ['open'], ['P0']), 'A-r101-open@P0.json')
        self.assertEqual(RUN.out_name('A', 1, ['lists'], ['P1', 'P2']), 'A-r1-lists@P1+P2.json')
        with self.assertRaises(ValueError):
            RUN.out_name('A', 1, ['open'], ['P9'])
        for name in ('A-r101-open@P0.json', 'A-r1-lists@P1+P2.json', 'B-r3-cold+server.json'):
            self.assertIsNotNone(JUDGE.ROUND_RE.match(name), name)

    def test_the_lock_stops_a_second_bench(self):
        with tempfile.TemporaryDirectory() as out:
            first = RUN.take_lock(Path(out) / 'bench.lock')
            self.assertIsNotNone(first)
            self.assertIsNone(RUN.take_lock(Path(out) / 'bench.lock'))
            self.assertFalse(RUN.lock_free(Path(out) / 'bench.lock'))  # the driver waits while another bench runs
            first.close()
            self.assertTrue(RUN.lock_free(Path(out) / 'bench.lock'))
            again = RUN.take_lock(Path(out) / 'bench.lock')
            self.assertIsNotNone(again)
            again.close()

    def test_unexpected_statuses_are_counted(self):
        self.assertEqual(RUN.statuses_unexpected([200, 304, 302, 500, 404, 500]), {'500': 2, '404': 1})
        self.assertEqual(RUN.statuses_unexpected([200, 204, 303]), {})

    def test_every_part_names_the_data_it_needs(self):
        self.assertEqual(set(RUN.PARTS), set(RUN.NEEDS))
        for part in RUN.PARTS:
            self.assertTrue(hasattr(RUN.Bench, 'part_' + part.replace('-', '_')), part)

    def test_statements_are_classified_by_what_they_serve(self):
        got = RUN.classify(['SELECT "studio_encounter"."id" FROM "studio_encounter"', 'SAVEPOINT "s1"',
                            'INSERT INTO "studio_accessrecord" ("id") VALUES (1)', 'RELEASE SAVEPOINT "s1"',
                            'UPDATE "studio_ratewindow" SET count = 2', 'SELECT 1 FROM "django_session"'])
        self.assertEqual(got, {'total': 6, 'builder': 1, 'record': 3, 'rate': 1, 'other': 1})


class BenchDriverStartTests(unittest.TestCase):
    def test_the_driver_starts_a_run_only_when_both_loads_are_within_their_bounds(self):
        quiet = RUN.bench_host_quiet
        self.assertTrue(quiet(3.0, 7.9, 6.0, 8.0))
        self.assertFalse(quiet(3.0, 8.1, 6.0, 8.0))  # the default 5-minute bound
        self.assertFalse(quiet(6.1, 2.0, 6.0, 8.0))
        self.assertTrue(quiet(5.0, 12.0, 5.0, 99.0))  # --max-load-5 99: start as soon as the 1-minute load settles
        self.assertFalse(quiet(5.5, 12.0, 5.0, 99.0))


STUB_MANAGE = """import json, os, sys
from pathlib import Path
env = os.environ
loads = json.loads(env.get('STUB_LOADS', '{}'))
number, parts = int(env['BENCH_ROUND']), env['BENCH_PARTS'].split(',')
own = '@' + '+'.join(env['BENCH_PROFILES'].split(',')) if env.get('BENCH_GROUP_PROFILES') == '1' else ''
name = env['BENCH_TAG'] + '-r' + str(number) + '-' + '+'.join(parts) + own + '.json'
load = float(loads.get(str(number), loads.get('*', 1.0)))
Path(env['BENCH_OUT'], name).write_text(json.dumps({'tag': env['BENCH_TAG'], 'round': number, 'parts': parts,
    'revision': (Path.cwd().parent / 'REVISION').read_text().strip(),
    'load_before': [1.0, 1.0, 1.0], 'load_after': [1.0, 1.0, 1.0], 'load_max': load, 'metrics': {}, 'checks': {},
    'controls': {}, 'errors': [], 'unexpected_statuses': {}, 'console_errors': [], 'blocked_requests': []}))
with open(env['STUB_CALLS'], 'a') as calls:
    calls.write(name + chr(10))
"""


STUB_MANAGE_CLAIM = """import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
import bench_run as br  # judge[6]: the real lock and output claim (a round is never overwritten)
env = os.environ
out, tag, number = Path(env['BENCH_OUT']), env['BENCH_TAG'], int(env['BENCH_ROUND'])
if br.take_lock(out / 'bench.lock') is None:
    print('AssertionError: another bench holds the lock'); sys.exit(1)
try:
    target = br.claim_output(out, tag, number, env['BENCH_PARTS'].split(','))
except FileExistsError as exc:
    print(f'AssertionError: {exc}'); sys.exit(1)
target.write_text(json.dumps({'parts': env['BENCH_PARTS'].split(','), 'load_before': [1.0], 'load_after': [1.0],
                              'load_max': 1.0, 'errors': [], 'revision': 'stub-rev'}))
with open(env['STUB_CALLS'], 'a') as f:
    f.write(target.name + chr(10))
"""


class BenchDriverResumeTests(unittest.TestCase):
    """judge[2], records[1], protocol[0]: the real driver over a stub round (a tree whose manage.py writes the round's
    file with a chosen load): a valid round is never measured again, an INVALID one is run as round + 100, and a
    round still INVALID with every retry spent fails the driver."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        (self.dir / 'tree' / 'cpt-studio').mkdir(parents=True)
        (self.dir / 'tree' / 'cpt-studio' / 'manage.py').write_text(STUB_MANAGE)
        (self.dir / 'tree' / 'REVISION').write_text('stub-rev\n')
        self.out, self.calls = self.dir / 'out', self.dir / 'calls.log'
        self.out.mkdir()

    def drive(self, loads, retries=2):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('BENCH_', 'DJANGO_SETTINGS'))}
        env.update({'CPT_STUDIO_DB_HOST': '127.0.0.1', 'CPT_STUDIO_DB_PORT': '55461', 'CPT_STUDIO_TEST_DB_SUFFIX': 'x',
                    'CPT_STUDIO_CODING_MODE': 'disabled', 'PYTHONDONTWRITEBYTECODE': '1',
                    'STUB_LOADS': json.dumps(loads), 'STUB_CALLS': str(self.calls)})
        return subprocess.run([sys.executable, '-B', str(BENCH / 'bench_run.py'), '--tree', f'A={self.dir / "tree"}',
                               '--order', 'A:1', '--group', 'server', '--out', str(self.out), '--ports', '9300-9349',
                               '--max-load', '999', '--max-load-5', '999', '--wait-minutes', '0',
                               '--retries', str(retries)], env=env, capture_output=True, text=True, timeout=120)

    def calls_made(self):
        return self.calls.read_text().split() if self.calls.exists() else []

    def test_a_valid_round_is_kept_and_never_measured_again(self):
        self.assertEqual(self.drive({'*': 1.0}).returncode, 0)
        self.assertEqual(self.calls_made(), ['A-r1-server.json'])
        run_log = (self.out / 'run-A-r1-server.log').read_bytes()
        again = self.drive({'*': 1.0})
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.calls_made(), ['A-r1-server.json'])  # nothing measured the second time
        self.assertFalse((self.out / 'A-r101-server.json').exists())
        self.assertEqual((self.out / 'run-A-r1-server.log').read_bytes(), run_log)  # its log never overwritten
        self.assertIn('measured before, valid; kept, not run again', (self.out / 'protocol.log').read_text())

    def test_a_resumed_invalid_round_is_run_again_as_its_next_attempt(self):
        self.assertEqual(self.drive({'1': 12.0, '101': 1.0}, retries=0).returncode, 3)  # INVALID, no retry allowed
        self.assertEqual(self.calls_made(), ['A-r1-server.json'])
        done = self.drive({'1': 12.0, '101': 1.0})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.calls_made(), ['A-r1-server.json', 'A-r101-server.json'])  # round 1 itself never again
        self.assertIn('measured before, INVALID: load average 12.0', (self.out / 'protocol.log').read_text())

    def test_a_round_measured_during_the_lock_wait_is_kept_and_its_log_too(self):
        """judge[6]: a second driver on one folder re-measured a valid round as round + 101, logged it INVALID by its
        own exit code and wrote over the round's run log. The bench's own refusal now sends it back to the loop's
        top, which judges the file found by judge.attempt_reasons alone; a run log is never written over."""
        (self.dir / 'tree' / 'cpt-studio' / 'manage.py').write_text(STUB_MANAGE_CLAIM)
        valid = {'parts': ['server'], 'load_before': [1.0], 'load_after': [1.0], 'load_max': 1.0, 'errors': [],
                 'revision': 'stub-rev'}
        real, seen = RUN.lock_free, []

        def lock_free(path):  # while this driver waited, the other driver's bench measured A:1 and wrote its log
            if not seen:
                seen.append(1)
                (self.out / 'A-r1-server.json').write_text(json.dumps(valid))
                (self.out / 'run-A-r1-server.log').write_text("the other driver's valid round\n")
            return real(path)
        env = {'CPT_STUDIO_DB_HOST': '127.0.0.1', 'CPT_STUDIO_DB_PORT': '55461', 'CPT_STUDIO_TEST_DB_SUFFIX': 'x',
               'CPT_STUDIO_CODING_MODE': 'disabled', 'STUB_CALLS': str(self.calls)}
        with unittest.mock.patch.object(RUN, 'lock_free', lock_free), unittest.mock.patch.dict(os.environ, env), \
                unittest.mock.patch('sys.stdout', io.StringIO()):
            rc = RUN.driver(['--tree', f'A={self.dir / "tree"}', '--order', 'A:1', '--group', 'server', '--out',
                             str(self.out), '--ports', '9300-9349', '--max-load', '999', '--max-load-5', '999',
                             '--wait-minutes', '0', '--retries', '1'])
        log = (self.out / 'protocol.log').read_text()
        self.assertEqual(rc, 0, log)
        self.assertEqual(self.calls_made(), [])  # nothing measured here
        self.assertFalse((self.out / 'A-r101-server.json').exists(), 'the valid round was measured again as 101')
        self.assertNotIn('INVALID', log)
        self.assertIn('another bench held the lock or measured this round', log)
        self.assertEqual((self.out / 'run-A-r1-server.log').read_text(), "the other driver's valid round\n")
        self.assertIn('exists; a round is never overwritten', (self.out / 'run-A-r1-server.2.log').read_text())

    def test_a_round_of_another_tree_is_run_again(self):
        """judge-9: a resumed driver kept a round measured on another tree as valid, so the tag stayed INVALID."""
        self.assertEqual(self.drive({'*': 1.0}).returncode, 0)
        (self.dir / 'tree' / 'REVISION').write_text('stub-rev-2\n')
        self.assertEqual(self.drive({'*': 1.0}).returncode, 0)
        self.assertEqual(self.calls_made(), ['A-r1-server.json', 'A-r101-server.json'])
        self.assertIn('measured before, INVALID: measured on revision stub-rev, not stub-rev-2',
                      (self.out / 'protocol.log').read_text())

    def test_a_round_with_a_failed_part_is_run_again(self):
        """The driver's retry rule is the judge's own: a part error, not only a load above 8, is INVALID."""
        (self.dir / 'tree' / 'cpt-studio' / 'manage.py').write_text(STUB_MANAGE.replace(
            "'errors': []", "'errors': [{'part': 'server', 'error': 'x'}] if number == 1 else []"))
        done = self.drive({'*': 1.0})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.calls_made(), ['A-r1-server.json', 'A-r101-server.json'])
        self.assertIn("A:1 server INVALID (exit 0, load 1.0; a part failed", (self.out / 'protocol.log').read_text())

    def test_the_driver_fails_when_a_round_is_still_invalid_with_no_retries_left(self):
        done = self.drive({'*': 12.0}, retries=1)
        self.assertEqual(done.returncode, 3, done.stderr)  # protocol[0]: it exited 0 after 'no retries left'
        log = (self.out / 'protocol.log').read_text()
        self.assertIn('A:101 server INVALID (exit 0, load 12.0; load average 12.0 > 8.0); no retries left', log)


REMEASURE_ROW = {'id': 'later', 'metric': 'open.later.first_page.P0', 'min_samples': 1, 'needs_a': False,
                 'spread': 0.03, 'gate': [{'abs_max': 180}]}


def _remeasure_file(folder, tag, number, group, metrics=None, **extra):
    """judge[0] (round 2): one round file named by its group as the driver names it."""
    parts = group.split('@')[0].split('+')
    data = {'tag': tag, 'round': number, 'parts': parts, 'metrics': metrics or {}, 'checks': {},
            'controls': {}, 'errors': [], 'unexpected_statuses': {}, 'console_errors': [], 'blocked_requests': [],
            'load_before': [1.0, 1.0, 1.0], 'load_after': [1.0, 1.0, 1.0], 'load_max': 1.0, 'revision': tag,
            'files': {'studio/static/studio/app.js': tag * 3}, **extra}
    Path(folder, f'{tag}-r{number}-{group}.json').write_text(json.dumps(data))


class BenchRemeasureTests(unittest.TestCase):
    """judge[0] (round 2, D-R2-48): a round's identity is the (part, profile) pairs its files cover, not how its group
    is spelled: a part measured twice in one round is INVALID, A and B carry the same base rounds, requests, an office
    size and the front door come from one file of a round, and the driver resumes by coverage."""

    def folder(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        return d

    def answer(self, d, table):
        return JUDGE.verdict(JUDGE.load_rounds(Path(d)), table, 'A', 'B')

    def test_a_part_measured_again_under_another_group_name_is_never_pooled(self):
        table = {'controls': [], 'rows': [REMEASURE_ROW]}
        d = self.folder()
        for n in (1, 2, 3):
            _remeasure_file(d, 'A', n, 'open@P0', {REMEASURE_ROW['metric']: [300] * 6})
            _remeasure_file(d, 'B', n, 'open@P0', {REMEASURE_ROW['metric']: [190] * 6})
        self.assertEqual(self.answer(d, table)['verdict'], 'FAIL')
        for n in (1, 2, 3):
            _remeasure_file(d, 'B', n, 'open', {REMEASURE_ROW['metric']: [165] * 6})  # every profile, P0 again
        got = self.answer(d, table)
        self.assertEqual(got['verdict'], 'INVALID', got)
        self.assertTrue(any('measured twice' in w and 'B-r1-open.json' in w for w in got['invalid']), got['invalid'])

    def test_a_second_requests_or_office_file_in_a_round_is_never_the_one_judged(self):
        d = self.folder()
        good = [{'case': 'c', 'role': 'reader', 'params_sha256': f'{k:016x}', 'effort': 'max', 'attempts': 1}
                for k in range(8)]
        for n in (1, 2, 3):
            _remeasure_file(d, 'A', n, 'cold+server+queries+load+requests', requests=good, requests_effort='max')
            high = [dict(x, effort='high') for x in good]
            if n == 1:
                high[2] = dict(high[2], params_sha256='f' * 16)
            _remeasure_file(d, 'B', n, 'cold+server+queries+load+requests', requests=high, requests_effort='high')
        table = {'controls': [], 'rows': [{'id': 'coder', 'kind': 'same_as_a', 'min_rows': 8,
                                           'effort': {'a': 'max', 'b': 'high'}}]}
        self.assertEqual(self.answer(d, table)['verdict'], 'FAIL')
        _remeasure_file(d, 'B', 1, 'requests', requests=[dict(x, effort='high') for x in good], requests_effort='high')
        got = self.answer(d, table)
        self.assertEqual(got['verdict'], 'INVALID', got)
        self.assertTrue(any('requests' in w and 'measured twice' in w for w in got['invalid']), got['invalid'])
        d2 = self.folder()
        _remeasure_file(d2, 'B', 1, 'office')
        _remeasure_file(d2, 'B', 1, 'office@P0')  # the office part runs at P0 whatever it is told: one measurement
        self.assertTrue(JUDGE.load_rounds(Path(d2))['B'][1].get('remeasured'))

    def test_a_value_one_file_carries_is_never_the_last_of_two_whatever_the_parts_say(self):
        """judge[0], the lead's 'judged for every file': requests, an office size and the front door are taken from
        one file of a round; a second file carrying one (whatever its parts list says) is a remeasure, never a
        last-file-wins value."""
        good = [{'case': 'c', 'role': 'reader', 'params_sha256': f'{k:016x}', 'effort': 'max', 'attempts': 1}
                for k in range(8)]
        for extra in ({'requests': good, 'requests_effort': 'max'}, {'office': {'101': {'typing': []}}},
                      {'front_door': {'later': [['GET', '/x']], 'back': [['GET', '/y']]}}):
            with self.subTest(carried=list(extra)[0]):
                d = self.folder()
                _remeasure_file(d, 'B', 1, 'server', **extra)
                _remeasure_file(d, 'B', 1, 'cold', **extra)  # two parts that never write it: no coverage overlap
                merged = JUDGE.load_rounds(Path(d))['B'][1]
                self.assertTrue(any(w.startswith(list(extra)[0].split('_effort')[0]) for w in merged['remeasured']),
                                merged['remeasured'])
                why = JUDGE.invalid_reasons({'B': {1: merged}}, ['B'], control=True, controls=[])
                self.assertTrue(any('measured twice' in w for w in why), why)
        d = self.folder()
        _remeasure_file(d, 'B', 1, 'server', requests=good, requests_effort='max')
        self.assertEqual(JUDGE.load_rounds(Path(d))['B'][1]['remeasured'], [])  # one carrier: nothing twice

    def test_rounds_of_one_tag_only_never_enter_the_verdict(self):
        table = {'controls': [], 'rows': [REMEASURE_ROW]}
        d = self.folder()
        for n in (1, 2, 3):
            _remeasure_file(d, 'A', n, 'open@P0', {REMEASURE_ROW['metric']: [300] * 6})
            _remeasure_file(d, 'B', n, 'open@P0', {REMEASURE_ROW['metric']: [190] * 6})
        for n in (4, 5, 6):
            _remeasure_file(d, 'B', n, 'open@P0', {REMEASURE_ROW['metric']: [165] * 6})
        got = self.answer(d, table)
        self.assertEqual(got['verdict'], 'INVALID', got)
        self.assertTrue(any('carry different rounds' in w for w in got['invalid']), got['invalid'])

    def test_the_driver_never_measures_a_round_again_under_another_group_name(self):
        d = Path(self.folder())
        tree, out, calls = d / 'tree' / 'cpt-studio', d / 'out', d / 'calls.log'
        tree.mkdir(parents=True)
        out.mkdir()
        tree.joinpath('manage.py').write_text(
            "import json, os\nfrom pathlib import Path\ne = os.environ\nparts = e['BENCH_PARTS'].split(',')\n"
            "own = '@' + '+'.join(e['BENCH_PROFILES'].split(',')) if e.get('BENCH_GROUP_PROFILES') == '1' else ''\n"
            "name = e['BENCH_TAG'] + '-r' + e['BENCH_ROUND'] + '-' + '+'.join(parts) + own + '.json'\n"
            "Path(e['BENCH_OUT'], name).write_text(json.dumps({'parts': parts, 'load_max': 1.0, 'metrics': {},\n"
            "    'load_before': [1.0, 1.0, 1.0], 'load_after': [1.0, 1.0, 1.0], 'errors': []}))\n"
            "open(e['STUB_CALLS'], 'a').write(name + chr(10))\n")
        env = {k: v for k, v in os.environ.items() if not k.startswith(('BENCH_', 'DJANGO_SETTINGS'))}
        env.update({'CPT_STUDIO_DB_HOST': '127.0.0.1', 'CPT_STUDIO_DB_PORT': '55461', 'CPT_STUDIO_TEST_DB_SUFFIX': 'x',
                    'CPT_STUDIO_CODING_MODE': 'disabled', 'PYTHONDONTWRITEBYTECODE': '1', 'STUB_CALLS': str(calls)})

        def drive(group):
            return subprocess.run([sys.executable, '-B', str(BENCH / 'bench_run.py'), '--tree', f'B={d / "tree"}',
                                   '--order', 'B:1', '--group', group, '--out', str(out), '--ports', '9300-9349',
                                   '--max-load', '999', '--max-load-5', '999', '--wait-minutes', '0'],
                                  env=env, capture_output=True, text=True, timeout=120).returncode
        self.assertEqual(drive('server'), 0)
        self.assertEqual(drive('server@P0'), 3)  # the same part, spelled otherwise: refused, nothing run
        self.assertEqual(calls.read_text().split(), ['B-r1-server.json'])
        self.assertIn('refused: B-r1-server.json measured part of it before', (out / 'protocol.log').read_text())


class BenchRoundRecordTests(unittest.TestCase):
    def test_a_round_that_aborts_outside_its_parts_is_invalid_in_its_own_file(self):
        """records[1]: the round's file is written whatever happens, and an abort outside the parts is its error."""
        with tempfile.TemporaryDirectory() as d:
            target = Path(d, 'A-r1-server.json')
            result = {'parts': ['server'], 'errors': [], 'load_before': [1.0, 1.0, 1.0], 'load_max': 1.0}
            closed = []
            with self.assertRaises(RuntimeError):
                with RUN.recorded_round(result, target, lambda: closed.append(True)):
                    raise RuntimeError('collectstatic failed')
            data = json.loads(target.read_text())
            self.assertEqual(closed, [True])
            self.assertEqual(data['errors'][0]['part'], 'round')
            self.assertTrue(JUDGE.attempt_reasons(target.name, data))
            clean = Path(d, 'A-r2-server.json')
            with RUN.recorded_round(dict(result, errors=[]), clean, lambda: None):
                pass
            self.assertEqual(JUDGE.attempt_reasons(clean.name, json.loads(clean.read_text())), [])
        self.assertIn('with recorded_round(result, target, close):', (BENCH / 'bench_run.py').read_text())

    def test_a_round_records_the_host_it_ran_on(self):
        """protocol[4]: a reboot separated release 1's rounds more than load did; each round names its boot."""
        self.assertIn("'host': host_state(),", (BENCH / 'bench_run.py').read_text())
        host = RUN.host_state()
        self.assertRegex(host['boot_id'] or '', r'^[0-9a-f-]{36}$')
        self.assertGreater(host['uptime_s'], 0)
        self.assertIsInstance(host['swap_used_mb'], int)
        self.assertTrue(host['kernel'])


class BenchDataTests(unittest.TestCase):
    def test_benchdata_gives_equal_bytes_twice(self):
        self.assertEqual(BD.all_bytes(), BD.all_bytes())

    def test_the_scans_have_the_sizes_the_specification_names(self):
        sizes = {spec['label']: len(BD.rich_files(spec)['data']) for spec in BD.RICH if spec['kind'] == 'scan'}
        self.assertAlmostEqual(sizes['scan-3p'] / 1e6, 1.67, delta=0.05)
        self.assertGreater(sizes['scan-3p'], 1024 * 1024)  # over 1 MiB: no click-time download, as C5 requires
        self.assertAlmostEqual(sizes['scan-20p'] / 1e6, 11.1, delta=0.3)

    def test_every_number_round_trips_through_the_barcode(self):
        for number in range(1, 2 ** BD.BITS):
            self.assertEqual(BD.decode_bits(BD.barcode_bits(number)), number)

    def test_a_blank_an_all_dark_or_a_damaged_barcode_never_decodes(self):
        self.assertIsNone(BD.decode_bits([0] * BD.SQUARES))
        self.assertIsNone(BD.decode_bits([1] * BD.SQUARES))
        bits = BD.barcode_bits(1234)
        for i in range(BD.SQUARES):
            flipped = list(bits)
            flipped[i] ^= 1
            self.assertIsNone(BD.decode_bits(flipped), i)
        for bad in (0, 4096, -1, '7', 1.0):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                BD.barcode_bits(bad)

    def test_the_geometry_places_every_square_and_the_marker_on_the_page(self):
        g = BD.geometry()
        self.assertEqual(len(g['squares']), BD.SQUARES)
        for x, y in [g['marker'], *g['squares']]:
            self.assertTrue(0 < x < 1 and 0 < y < 1)
        xs = [x for x, _ in g['squares']]
        self.assertEqual(xs, sorted(xs))

    def test_the_barcode_is_read_back_from_a_scan_s_pixels_at_the_geometry(self):
        from PIL import Image
        from pypdf import PdfReader
        data = BD.scan_pdf(1, 2741, 77, dpi=60, quality=62)
        page = PdfReader(io.BytesIO(data)).pages[0]
        image = next(iter(page.images)).image.convert('L')
        w, h = image.size
        g = BD.geometry()
        bits = [1 if image.getpixel((round(w * x), round(h * y))) < 128 else 0 for x, y in g['squares']]
        self.assertEqual(BD.decode_bits(bits), 2741)
        mx, my = g['marker']
        self.assertLess(image.getpixel((round(w * mx), round(h * my))), 100)

    def test_the_walk_s_scan_has_ink_under_every_word_of_its_text_layer(self):
        """walk.cjs counts a mark as drawn only over ink (5% of its pixels): every word of the walk's invisible text
        layer lies on ink in the page image, at the place the layer gives it, and the layer reads back."""
        from pypdf import PdfReader
        from reportlab.pdfbase.pdfmetrics import stringWidth
        reader = PdfReader(io.BytesIO(BD.walk_scan()))
        self.assertEqual(len(reader.pages), 2)
        sx, sy = lambda v, w: round(w * v / BD.PAGE_W), lambda v, h: round(h * (BD.PAGE_H - v) / BD.PAGE_H)
        for number, page in enumerate(reader.pages, start=1):
            self.assertIn(f'Quoted passage {number}:', page.extract_text())
            image = next(iter(page.images)).image.convert('L')
            w, h = image.size
            words = 0
            for i, line in enumerate(BD.WALK_SCAN_OCR):
                y, x = 700 - 12 * i, 56.0
                for word in line.replace('{page}', str(number)).split(' '):
                    end = x + stringWidth(word, 'Helvetica', 10)
                    box = image.crop((sx(x, w), sy(y + 6, h), sx(end, w), sy(y - 1, h)))
                    dark = sum(box.histogram()[:120]) / max(1, box.width * box.height)
                    self.assertGreater(dark, 0.5, (number, word))
                    x += stringWidth(word + ' ', 'Helvetica', 10)
                    words += 1
            self.assertGreater(words, 20)

    def test_docs_json_names_what_bench_cjs_reads(self):
        seeded = {'n100': {'username': 'bench-n100', 'rows': 100, 'docs': [{'id': 'x', 'label': 'text-2p'}]},
                  'n1500': {'username': 'bench-n1500', 'rows': 1500, 'docs': []}}
        got = BD.docs_json(seeded, ('X-CPT-Studio-Client', 'v'), 'zqx')
        self.assertEqual(set(got), {'geometry', 'docs', 'client', 'marker', 'users', 'rows'})
        self.assertEqual(got['docs'], [{'id': 'x', 'label': 'text-2p'}])
        self.assertEqual(got['users'], {'n100': 'bench-n100', 'n1500': 'bench-n1500'})
        self.assertEqual(got['geometry'], BD.geometry())
        self.assertEqual(set(BD.SIZES), {'n51', 'n100', 'n101', 'n1500', 'n5000', 'n18000'})

    def test_the_control_document_carries_no_marker_and_no_barcode(self):
        spec = next(s for s in BD.RICH if s['label'] == 'control-nomarker')
        marked = next(s for s in BD.RICH if s['label'] == 'text-2p')
        rect = re.compile(rb'(?:^|\s)-?[\d.]+ -?[\d.]+ -?[\d.]+ -?[\d.]+ re\b')
        self.assertEqual(rect.findall(_page_one_stream(BD.rich_files(spec)['data'])), [])
        ones = bin(101).count('1')
        self.assertEqual(len(rect.findall(_page_one_stream(BD.rich_files(marked)['data']))), 1 + 2 + ones + ones % 2)


def _page_one_stream(data):
    from pypdf import PdfReader
    return PdfReader(io.BytesIO(data)).pages[0].get_contents().get_data()


@unittest.skipUnless(NODE, 'node is not installed')
class BenchBrowserFilesTests(unittest.TestCase):
    def test_bench_cjs_and_proxy_cjs_parse(self):
        for name in ('bench.cjs', 'proxy.cjs'):
            done = subprocess.run([NODE, '--check', str(BENCH / name)], capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_the_page_s_probe_parses_and_its_decoder_agrees_with_python(self):
        script = (f'const b = require({json.dumps(str(BENCH / "bench.cjs"))});'
                  f'new Function(b.INIT_FOR({json.dumps(BD.geometry())}));'
                  'const out = [];'
                  'for (let n = 0; n < 4096; n += 1) out.push(b.decodeSquares(b.encodeForTest(n), 12));'
                  'out.push(b.decodeSquares(Array(15).fill(0), 12), b.decodeSquares(Array(15).fill(1), 12));'
                  'console.log(JSON.stringify(out));')
        done = subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(out[1:4096], list(range(1, 4096)))
        self.assertEqual(out[0], None)
        self.assertEqual(out[4096:], [None, None])
        for number in (1, 101, 4095):
            self.assertEqual(BD.barcode_bits(number), _node_bits(number))


    def test_the_base_is_loopback_or_in_a_rehearsal_a_private_address_over_tls(self):
        cases = [('http://127.0.0.1:9301', False, True), ('https://172.17.0.2:8443', False, False),
                 ('https://172.17.0.2:8443', True, True), ('https://10.1.2.3', True, True),
                 ('https://192.168.4.5:443', True, True), ('https://cpt.quillmd.com', True, False),
                 ('https://admin.quillmd.com', True, False), ('https://147.189.172.8', True, False),
                 ('http://172.17.0.2', True, False), ('https://172.32.0.1', True, False),
                 ('http://localhost:9301', False, False)]
        script = (f'const b = require({json.dumps(str(BENCH / "bench.cjs"))});'
                  f'console.log(JSON.stringify({json.dumps(cases)}.map(([u, r]) => b.baseAllowed(u, r))));')
        done = subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), [expected for _, _, expected in cases])
        refused = subprocess.run([NODE, str(BENCH / 'bench.cjs'), '--flow', 'open', '--base', 'https://cpt.quillmd.com',
                                  '--rehearsal', '--out', os.devnull], capture_output=True, text=True, timeout=60)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('the base must be loopback', refused.stderr)
        unpinned = subprocess.run([NODE, str(BENCH / 'bench.cjs'), '--flow', 'open', '--base',
                                   'https://172.17.0.2:8443',
                                   '--rehearsal', '--out', os.devnull], capture_output=True, text=True, timeout=60)
        self.assertNotEqual(unpinned.returncode, 0)  # bench[1] (round 2): a rehearsal trusts its certificate by SPKI
        self.assertIn("names the test certificate's SPKI sha256 (--spki)", unpinned.stderr)
        source = (BENCH / 'bench.cjs').read_text()
        self.assertNotIn('ignoreHTTPSErrors: REHEARSAL', source)
        self.assertIn("...(REHEARSAL ? [`--ignore-certificate-errors-spki-list=${SPKI}`] : [])", source)


PLAYWRIGHT = Path('/opt/meddoc-pro/node_modules/playwright')


def _free_ports(n):
    pool = RUN.PortPool(range(9300, 9350))
    return [pool.take() for _ in range(n)]


@unittest.skipUnless(NODE, 'node is not installed')
class BenchProxyCookieTests(unittest.TestCase):
    def test_the_proxy_logs_every_cookie_but_the_server_s_own(self):
        """records[4]: the proxy logged the whole Cookie header as the session's digest, so a search word a page put in
        a cookie never reached the marker scan."""
        import http.server
        import socketserver
        import threading
        import urllib.request
        listen, upstream, control = _free_ports(3)

        class Answer(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Length', '2')
                self.end_headers()
                self.wfile.write(b'ok')

            def log_message(self, *args):
                pass
        server = socketserver.TCPServer(('127.0.0.1', upstream), Answer)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        proxy = subprocess.Popen([NODE, str(BENCH / 'proxy.cjs'), '--listen', str(listen), '--upstream', str(upstream),
                                  '--control', str(control)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(proxy.wait, 10)
        self.addCleanup(proxy.terminate)
        self.assertIn('proxy up', proxy.stdout.readline())
        cookie = 'cptstudio_session=sess123; cptstudio_csrf=csrf456; cptstudio_device=dev789; cpt-last-search=zqxword'
        asked = urllib.request.Request(f'http://127.0.0.1:{listen}/x', headers={'Cookie': cookie})
        self.assertEqual(urllib.request.urlopen(asked, timeout=10).read(), b'ok')
        log = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{control}/log?since=0', timeout=10).read())
        logged = log['entries'][0]['reqHeaders']['cookie']
        self.assertIn('cpt-last-search=zqxword', logged)
        self.assertRegex(logged, r'cptstudio_session=session:[0-9a-f]{12}')
        for secret in ('sess123', 'csrf456', 'dev789'):
            self.assertNotIn(secret, logged)

    def test_the_proxy_logs_the_server_s_own_set_cookie_redacted_and_answers_it_as_set(self):
        """records[8]: the answers' Set-Cookie carried the session key, the CSRF token and the device cookie in the
        clear. They are logged as the request Cookie is (the session as its member's digest, so joins still work),
        the attributes kept, every other cookie as set; the browser is still answered with the cookies as set."""
        import http.client
        import http.server
        import socketserver
        import threading
        import urllib.request
        listen, upstream, control = _free_ports(3)
        set_cookies = ['cptstudio_session=sess123; HttpOnly; Path=/', 'cptstudio_csrf=csrf456; Path=/',
                       'cptstudio_device=dev789; HttpOnly; Path=/', 'cpt-last-search=zqxword; Path=/']

        class Answer(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length') or 0))
                self.send_response(302)
                self.send_header('Location', '/')
                for line in set_cookies:
                    self.send_header('Set-Cookie', line)
                self.send_header('Content-Length', '0')
                self.end_headers()

            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Length', '2')
                self.end_headers()
                self.wfile.write(b'ok')

            def log_message(self, *args):
                pass
        server = socketserver.TCPServer(('127.0.0.1', upstream), Answer)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        proxy = subprocess.Popen([NODE, str(BENCH / 'proxy.cjs'), '--listen', str(listen), '--upstream', str(upstream),
                                  '--control', str(control)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(proxy.wait, 10)
        self.addCleanup(proxy.terminate)
        self.assertIn('proxy up', proxy.stdout.readline())
        client = http.client.HTTPConnection('127.0.0.1', listen, timeout=10)  # a 302 is not followed
        client.request('POST', '/login/', body=b'u=x', headers={'Content-Type': 'application/x-www-form-urlencoded'})
        answer = client.getresponse()
        answer.read()
        self.assertEqual(answer.status, 302)
        self.assertEqual(answer.headers.get_all('Set-Cookie'), set_cookies)  # the browser gets them as set
        client.close()
        asked = urllib.request.Request(f'http://127.0.0.1:{listen}/x', headers={'Cookie': 'cptstudio_session=sess123'})
        self.assertEqual(urllib.request.urlopen(asked, timeout=10).read(), b'ok')
        entries = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{control}/log?since=0', timeout=10).read())[
            'entries']
        for entry in entries:
            for secret in ('sess123', 'csrf456', 'dev789'):
                self.assertNotIn(secret, json.dumps(entry))
        posted = next(e for e in entries if e['method'] == 'POST')
        logged = posted['resHeaders']['set-cookie']
        self.assertIn('cpt-last-search=zqxword; Path=/', logged)
        followed = next(e for e in entries if e['method'] == 'GET')
        self.assertEqual(logged[0], f'cptstudio_session=session:{followed["member"]}; HttpOnly; Path=/')
        self.assertEqual(logged[1:3], ['cptstudio_csrf=<redacted>; Path=/',
                                       'cptstudio_device=<redacted>; HttpOnly; Path=/'])


NOTHING_DRAWN_DRIVER = r"""
const http = require('http');
const [bench, playwright, port, geometryJson] = process.argv.slice(2);
const B = require(bench); const G = JSON.parse(geometryJson); const BASE = `http://127.0.0.1:${port}`;
const ID = '0f0e0d0c-0b0a-5909-8807-060504030201'; const OTHER = 'a1a2a3a4-b1b2-5c1c-8d1d-e1e2e3e4e5e6';
const PAGE = `
const V = new URLSearchParams(location.search).get('v');
const ID = ${JSON.stringify(ID)}; const OTHER = ${JSON.stringify(OTHER)}; const G = ${JSON.stringify(G)};
const main = () => document.getElementById('main');
function list() {
  const ids = V.startsWith('norow') ? [OTHER] : [ID, OTHER];
  const rows = ids.map(i => '<a class="document-row" href="#doc/' + i + '">r</a>').join('');
  main().innerHTML = '<section><div id="documentsTable">' + rows + '</div></section>';
}
function draw() {
  main().innerHTML = '<section><div id="reviewColumn">r</div>'
    + '<div class="pdf-page" data-page="1"><canvas width="1224" height="1584"></canvas></div></section>';
  const cv = document.querySelector('canvas'); const g = cv.getContext('2d');
  g.fillStyle = 'white'; g.fillRect(0, 0, cv.width, cv.height);
  g.fillStyle = 'black'; g.fillRect(G.marker[0] * cv.width - 40, G.marker[1] * cv.height - 40, 80, 80);
}
function route() {
  if (location.hash !== '#doc/' + ID) return list();
  if (V === 'leave-clean') return location.assign('/login/');
  if (V === 'norow-clean') { main().innerHTML = '<section><p>Not available.</p></section>'; return; }
  if (V.startsWith('col-')) {  // records[3] (round 2): a review column and a text layer from page memory, no canvas
    main().innerHTML = '<section><div id="reviewColumn"><h2>Title</h2><p>99213</p><blockquote>quote</blockquote></div>'
      + (V === 'col-stays' ? '' : '<div class="pdf-text"><span>page text</span></div>') + '</section>';
    if (V === 'col-removed') setTimeout(() => { main().innerHTML = '<section><p>Not available.</p></section>'; }, 300);
    if (V === 'col-left') setTimeout(() => location.assign('/login/'), 300);
    return;
  }
  draw();
  if (V === 'leave') setTimeout(() => location.assign('/login/'), 300);
}
window.addEventListener('hashchange', route); route();`;
const APP = '<!doctype html><html><body><main id="main"></main><script>' + PAGE + '</script></body></html>';
const LOGIN = '<!doctype html><input name="password" type="password">';
const server = http.createServer((req, res) => {
  const path = new URL(req.url, BASE).pathname;
  const body = path === '/login/' ? LOGIN : path === '/' ? APP : null;
  res.writeHead(body === null ? 404 : 200, { 'content-type': 'text/html', 'cache-control': 'no-store' });
  res.end(body || '');
});
(async () => {
  await new Promise(resolve => server.listen(Number(port), '127.0.0.1', resolve));
  const { chromium } = require(playwright);
  const browser = await chromium.launch({ headless: true,
    args: ['--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'] });
  B.TESTING.set({ DOC: { 'text-2p': { label: 'text-2p', id: ID, number: 102, kind: 'pdf' } }, browser,
    INIT: B.INIT_FOR(G), result: { consoleErrors: [], pageErrors: [], blocked: [] }, FLOW: 'correct', PROFILE: 'P0',
    BASE });
  const out = {};
  try {
    for (const v of ['stay', 'leave', 'norow', 'leave-clean', 'norow-clean', 'col-removed', 'col-left', 'col-stays']) {
      const s = await B.TESTING.newContext();
      try {
        await s.page.goto(`${BASE}/?v=${v}`); await s.page.waitForSelector('#documentsTable .document-row');
        const o = await B.TESTING.openNoWait(s, 'text-2p');
        out[v] = [o.canvasDark, Boolean(o.columnDrawn), Boolean(o.textDrawn)];
      } finally { await s.context.close(); }
    }
  } finally { await browser.close(); server.close(); }
  console.log(JSON.stringify(out));
})().catch(e => { console.error(String(e && e.stack || e)); server.close(); process.exit(1); });
"""


@unittest.skipUnless(NODE and (PLAYWRIGHT / 'package.json').exists(), 'node or Playwright is not installed')
class BenchNothingDrawnTests(unittest.TestCase):
    def test_a_document_drawn_and_then_left_or_routed_with_no_row_is_seen(self):
        """records[3]: 'nothing drawn' read the probe of whatever document was current 4 s later, so a page that drew
        and then went to the sign-in page (as a 401 does), or drew from the hash with no row, passed as nothing."""
        with tempfile.TemporaryDirectory() as d:
            driver = Path(d, 'driver.cjs')
            driver.write_text(NOTHING_DRAWN_DRIVER)
            port = _free_ports(1)[0]
            done = subprocess.run([NODE, str(driver), str(BENCH / 'bench.cjs'), str(PLAYWRIGHT), str(port),
                                   json.dumps(BD.geometry())], capture_output=True, text=True, timeout=180,
                                  env={**os.environ, 'TMPDIR': d})
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        got = json.loads(done.stdout.strip().splitlines()[-1])
        self.assertEqual({v: got[v][0] for v in ('stay', 'leave', 'norow', 'leave-clean', 'norow-clean')},
                         {'stay': True, 'leave': True, 'norow': True, 'leave-clean': False, 'norow-clean': False})
        # records[3] (round 2): a column or text layer drawn from page memory is drawn, canvas or not, whether it is
        # then removed, left by a sign-in route, or stays; the clean twins draw nothing at all
        self.assertEqual({v: got[v] for v in ('col-removed', 'col-left', 'col-stays')},
                         {'col-removed': [False, True, True], 'col-left': [False, True, True],
                          'col-stays': [False, True, False]})
        self.assertEqual([got['leave-clean'], got['norow-clean']], [[False, False, False], [False, False, False]])


TAB_PAINT_DRIVER = r"""
const http = require('http'); const { spawn } = require('child_process');
const [bench, proxyPath, playwright, appPort, proxyPort, controlPort, geometryJson] = process.argv.slice(2);
const B = require(bench); const G = JSON.parse(geometryJson); const BASE = `http://127.0.0.1:${proxyPort}`;
const ID = '0f0e0d0c-0b0a-5909-8807-060504030201';
const PAGE = `
const V = new URLSearchParams(location.search).get('v') || 'clean';
const G = ${JSON.stringify(G)}; const main = document.getElementById('main');
const busy = ms => { const t = performance.now(); while (performance.now() - t < ms) {} };
let serial = 0, routes = 0;
function canvas() {
  const cv = document.querySelector('canvas'); const g = cv.getContext('2d');
  g.fillStyle = 'white'; g.fillRect(0, 0, cv.width, cv.height);
  g.fillStyle = 'black'; g.fillRect(G.marker[0] * cv.width - 40, G.marker[1] * cv.height - 40, 80, 80);
}
async function route() {
  const view = (location.hash || '#documents').slice(1); const my = ++serial; routes += 1;
  if (view.startsWith('doc/')) {
    main.innerHTML = '<section><a class="back-link" href="#documents">Back</a><div id="reviewColumn">review</div>'
      + '<div class="pdf-page" data-page="1"><canvas width="1224" height="1584"></canvas></div></section>';
    const col = document.getElementById('reviewColumn');
    if (V === 'fade-review') { col.style.opacity = '0'; void col.offsetWidth;
      col.style.transition = 'opacity .35s'; col.style.opacity = '1'; }
    canvas(); return;
  }
  main.innerHTML = '<section><div id="documentsTable"></div></section>';
  const sec = main.firstElementChild; const table = document.getElementById('documentsTable');
  const later = routes > 1;  // a page load's own entrance is allowed; a tab change shows none (R2-14)
  if (later && V === 'r1') sec.style.animation = 'enter .35s';  // release 1's fade, on the section
  if (later && V === 'fade-main') { main.style.transition = 'none'; main.style.opacity = '0'; void main.offsetWidth;
    main.style.transition = 'opacity .35s'; main.style.opacity = '1'; }
  const body = await (await fetch('/api/encounters?view=' + view, { cache: 'no-store' })).json();
  if (my !== serial) return;
  if (later && V === 'fade-list') table.style.opacity = '0';
  if (later && V === 'fade-anim') table.style.animation = 'appear .35s';
  table.innerHTML = body.ids.map(i => '<a class="document-row" href="#doc/' + i + '">r</a>').join('');
  if (later && V === 'fade-list') { void table.offsetWidth; table.style.transition = 'opacity .35s';
    table.style.opacity = '1'; }
  if (V === 'late-queue' && view === 'queue') setTimeout(() => busy(300), 0);  // painted 300 ms after the rows
}
window.addEventListener('hashchange', route); route();`;
const APP = '<!doctype html><html><head><style>@keyframes enter{from{opacity:0}to{opacity:1}}'
  + '@keyframes appear{from{opacity:0}to{opacity:1}}</style></head><body><nav><a data-nav="queue" href="#queue">Q</a>'
  + '<a data-nav="workspace" href="#workspace">W</a><a data-nav="documents" href="#documents">D</a></nav>'
  + '<main id="main"></main><script>' + PAGE + '</script></body></html>';
const ids = n => Array.from({ length: n },
  (_, i) => (i === 0 ? ID : `00000000-0000-4000-8000-${String(i).padStart(12, '0')}`));
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  if (url.pathname === '/') {
    res.writeHead(200, { 'content-type': 'text/html', 'cache-control': 'no-store' }); return res.end(APP); }
  if (url.pathname === '/api/encounters') { const v = url.searchParams.get('view');
    res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    return res.end(JSON.stringify({ ids: ids(v === 'queue' ? 16 : v === 'workspace' ? 5 : 100) })); }
  res.writeHead(404, { 'cache-control': 'no-store' }); res.end('');
});
let proxy = null;
(async () => {
  await new Promise(resolve => server.listen(Number(appPort), '127.0.0.1', resolve));
  proxy = spawn(process.execPath, [proxyPath, '--listen', proxyPort, '--upstream', appPort, '--control', controlPort],
    { stdio: ['ignore', 'pipe', 'ignore'] });
  await new Promise((ok, no) => { proxy.stdout.on('data', d => { if (String(d).includes('proxy up')) ok(); });
    proxy.on('exit', c => no(new Error('the proxy exited ' + c))); });
  const { chromium } = require(playwright);
  const browser = await chromium.launch({ headless: true,
    args: ['--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'] });
  B.TESTING.set({ DOC: { 'text-2p': { label: 'text-2p', id: ID, number: 102, kind: 'pdf' } }, browser,
    INIT: B.INIT_FOR(G),
    result: { consoleErrors: [], pageErrors: [], blocked: [], actions: [], unfinished: [], metrics: {}, errors: [] },
    FLOW: 'lists', PROFILE: 'P0', BASE, CONTROL: Number(controlPort) });
  const out = {};
  try {
    for (const v of ['clean', 'late-queue', 'fade-list', 'fade-main', 'fade-anim', 'r1', 'fade-review']) {
      const s = await B.TESTING.newContext();
      try {
        await s.page.goto(`${BASE}/?v=${v}#documents`); await s.page.waitForSelector('#documentsTable .document-row');
        const row = {};
        for (const nav of ['queue', 'workspace', 'documents']) {
          const t = await B.TESTING.tab(s, nav, 'pin'); row[nav] = t && t.opaque; }
        row.review = (await B.TESTING.openDoc(s, 'text-2p', 'pin')).opaque;
        out[v] = row;
      } finally { await s.context.close(); }
    }
  } finally { await browser.close(); server.close(); proxy.kill(); }
  console.log(JSON.stringify(out));
})().catch(e => {
  console.error(String(e && e.stack || e)); server.close(); if (proxy) proxy.kill(); process.exit(1); });
"""


@unittest.skipUnless(NODE and (PLAYWRIGHT / 'package.json').exists(), 'node or Playwright is not installed')
class BenchTabPaintTests(unittest.TestCase):
    def test_a_tab_is_opaque_when_its_own_content_is_shown_and_painted(self):
        """bench[0] (round 2): the per-tab rows stopped the timer when rows were inserted and read only the section's
        own opacity, so a Queue painted 300 ms late, or a list (or #main, or the review column) faded in over 350 ms,
        passed at about 16 ms. Through the bench's own tab() and openDoc() and the real proxy.cjs: each is now seen,
        release 1's fade on the section reads as before, and a clean page stays fast. (The clean bound is loose on
        purpose: this pin runs beside the whole suite; a late or faded tab reads 300-360 ms.)"""
        with tempfile.TemporaryDirectory() as d:
            driver = Path(d, 'driver.cjs')
            driver.write_text(TAB_PAINT_DRIVER)
            app, listen, control = _free_ports(3)
            done = subprocess.run([NODE, str(driver), str(BENCH / 'bench.cjs'), str(BENCH / 'proxy.cjs'),
                                   str(PLAYWRIGHT), str(app), str(listen), str(control), json.dumps(BD.geometry())],
                                  capture_output=True, text=True, timeout=300, env={**os.environ, 'TMPDIR': d})
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        got = json.loads(done.stdout.strip().splitlines()[-1])
        tabs = ('queue', 'workspace', 'documents')
        for nav in tabs:
            self.assertLess(got['clean'][nav], 150, got['clean'])
            self.assertLess(got['fade-review'][nav], 150, got['fade-review'])
            for v in ('fade-list', 'fade-main', 'fade-anim'):
                self.assertGreaterEqual(got[v][nav], 340, (v, got[v]))
            self.assertTrue(330 <= got['r1'][nav] <= 400, got['r1'])  # A is unchanged: release 1's 350 ms fade
        self.assertGreaterEqual(got['late-queue']['queue'], 300, got['late-queue'])
        self.assertLess(got['late-queue']['workspace'], 150, got['late-queue'])
        self.assertLess(got['clean']['review'], 150, got['clean'])
        self.assertGreaterEqual(got['fade-review']['review'], 340, got['fade-review'])


WORKER_LOG_DRIVER = r"""
const http = require('http');
const [bench, playwright, port] = process.argv.slice(2);
const B = require(bench); const BASE = `http://127.0.0.1:${port}`; const served = [];
const PAGE = '<!doctype html><title>load</title><script type="module">'
  + "const w = new URLSearchParams(location.search).get('w') || ''; await import('/static/pdf.min.mjs');"
  + "const worker = new Worker('/static/pdf.worker.min.mjs' + w, { type: 'module' });"
  + "worker.onmessage = () => fetch('/api/ping', { cache: 'no-store' }).then(r => r.text())"
  + ".then(() => { document.title = 'done'; });"  // the body read: an unread answer never ends its load
  + '</script>';
const server = http.createServer((req, res) => {
  const path = new URL(req.url, BASE).pathname; if (path !== '/favicon.ico') served.push(req.url);
  const immutable = { 'content-type': 'text/javascript', 'cache-control': 'public, max-age=31536000, immutable' };
  if (path === '/') {
    res.writeHead(200, { 'content-type': 'text/html', 'cache-control': 'no-store' }); return res.end(PAGE); }
  if (path === '/static/pdf.min.mjs') { res.writeHead(200, immutable); return res.end('export const ready = 1;'); }
  if (path === '/static/pdf.worker.min.mjs') { res.writeHead(200, immutable); return res.end("postMessage('ready');"); }
  if (path === '/api/ping') {
    res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' }); return res.end('{}'); }
  res.writeHead(404, { 'cache-control': 'no-store' }); res.end('');
});
(async () => {
  await new Promise(resolve => server.listen(Number(port), '127.0.0.1', resolve));
  const { chromium } = require(playwright);
  const browser = await chromium.launch({ headless: true,
    args: ['--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'] });
  B.TESTING.set({ DOC: {}, browser, INIT: '', result: { consoleErrors: [], pageErrors: [], blocked: [] }, FLOW: 'open',
    PROFILE: 'P0', BASE });
  const out = {};
  try {
    const s = await B.TESTING.newContext();
    try {
      await B.TESTING.logFromCdp(s.cdp);
      const step = async (name, go) => {
        const logged = B.TESTING.cdpState().log.length; const asked = served.length;
        await go(); await s.page.waitForFunction(() => document.title === 'done', null, { timeout: 30000 });
        await new Promise(resolve => setTimeout(resolve, 1000));
        out[name] = { log: B.TESTING.cdpState().log.slice(logged).filter(e => !e.url.startsWith('/favicon'))
          .map(e => `${e.method} ${e.url} ${e.status}`), served: served.slice(asked) };
      };
      await step('cold', () => s.page.goto(`${BASE}/`));
      await step('warm', () => s.page.reload());
      await step('fresh', () => s.page.goto(`${BASE}/?w=${encodeURIComponent('?nc=1')}`));
      out.inFlight = B.TESTING.cdpState().inFlight;
    } finally { await s.context.close(); }
  } finally { await browser.close(); server.close(); }
  console.log(JSON.stringify(out));
})().catch(e => { console.error(String(e && e.stack || e)); server.close(); process.exit(1); });
"""


@unittest.skipUnless(NODE and (PLAYWRIGHT / 'package.json').exists(), 'node or Playwright is not installed')
class BenchWorkerLogTests(unittest.TestCase):
    def test_the_rehearsal_log_sees_a_worker_s_own_script_and_never_waits_on_it(self):
        """bench[1], bench[2] (round 2): the page's CDP session reports a dedicated worker's own script asked for (and
        its responseReceivedExtraInfo) but never its answer or end, so the rehearsal's log missed pdf.worker.min.mjs
        and counted it in flight for ever. Real Chromium, the bench's own logFromCdp: the cold log is what the server
        served, worker file included; a warm reload asks for no library file; a fresh worker address for exactly one;
        nothing is left in flight."""
        with tempfile.TemporaryDirectory() as d:
            driver = Path(d, 'driver.cjs')
            driver.write_text(WORKER_LOG_DRIVER)
            done = subprocess.run([NODE, str(driver), str(BENCH / 'bench.cjs'), str(PLAYWRIGHT),
                                   str(_free_ports(1)[0])],
                                  capture_output=True, text=True, timeout=180, env={**os.environ, 'TMPDIR': d})
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        got = json.loads(done.stdout.strip().splitlines()[-1])
        self.assertEqual(sorted(got['cold']['log']), sorted(f'GET {u} 200' for u in got['cold']['served']))
        self.assertIn('GET /static/pdf.worker.min.mjs 200', got['cold']['log'])
        library = re.compile(r'pdf(\.worker)?\.min\.([0-9a-f]{12}\.)?mjs')
        self.assertEqual([x for x in got['warm']['log'] if library.search(x)], [], got['warm'])
        self.assertEqual([u for u in got['warm']['served'] if library.search(u)], [], got['warm'])
        self.assertEqual([x for x in got['fresh']['log'] if library.search(x)],
                         ['GET /static/pdf.worker.min.mjs?nc=1 200'], got['fresh'])
        self.assertEqual(got['inFlight'], 0)


DETAIL_RACE_DRIVER = r"""
const http = require('http'); const { spawn } = require('child_process');
const [bench, proxyPath, playwright, appPort, proxyPort, controlPort, geometryJson] = process.argv.slice(2);
const B = require(bench); const G = JSON.parse(geometryJson); const BASE = `http://127.0.0.1:${proxyPort}`;
const ID = '0f0e0d0c-0b0a-5909-8807-060504030201'; const OTHER = 'a1a2a3a4-b1b2-5c1c-8d1d-e1e2e3e4e5e6';
const PAGE = `
const V = new URLSearchParams(location.search).get('v');
const ID = ${JSON.stringify(ID)}; const OTHER = ${JSON.stringify(OTHER)};
const G = ${JSON.stringify(G)}; const main = () => document.getElementById('main'); let closed = false;
function list() {
  const rows = [ID, OTHER].map(i => '<a class="document-row" href="#doc/' + i + '">r</a>').join('');
  main().innerHTML = '<section><div id="documentsTable">' + rows + '</div></section>';
}
function draw() {
  if (closed) return;
  main().innerHTML = '<section><div class="pdf-page" data-page="1">'
    + '<canvas width="1224" height="1584"></canvas></div></section>';
  const cv = document.querySelector('canvas'); const g = cv.getContext('2d');
  g.fillStyle = 'white'; g.fillRect(0, 0, cv.width, cv.height);
  g.fillStyle = 'black'; g.fillRect(G.marker[0] * cv.width - 40, G.marker[1] * cv.height - 40, 80, 80);
}
function close() { closed = true; main().innerHTML = '<section><p>Not available.</p></section>'; }
function route() {
  if (location.hash !== '#doc/' + ID) return list();
  closed = false;
  const view = fetch('/api/encounters/' + ID + '/original?view=1', { cache: 'no-store' });
  const detail = fetch('/api/encounters/' + ID, { cache: 'no-store' });
  if (V === 'race') {  // the held copy drawn on the view's 304, the viewer closed on a refused detail
    view.then(r => { if (r.status === 304 || r.ok) setTimeout(draw, 60); });
    detail.then(r => { if (!r.ok) close(); });
  } else {  // a page that waits for the detail before it draws anything
    Promise.all([view, detail]).then(([, d]) => (d.ok ? draw() : close()));
  }
}
window.addEventListener('hashchange', route); route();`;
const APP = '<!doctype html><html><body><main id="main"></main><script>' + PAGE + '</script></body></html>';
const server = http.createServer((req, res) => {
  const path = new URL(req.url, 'http://127.0.0.1').pathname;
  if (path === '/') {
    res.writeHead(200, { 'content-type': 'text/html', 'cache-control': 'no-store' }); return res.end(APP); }
  if (path === `/api/encounters/${ID}/original`) {
    return setTimeout(() => { res.writeHead(304, { 'cache-control': 'no-store' }); res.end(); }, 5); }
  if (path === `/api/encounters/${ID}`) {
    return setTimeout(() => { res.writeHead(503, { 'cache-control': 'no-store' }); res.end(''); }, 8); }
  res.writeHead(404, { 'cache-control': 'no-store' }); res.end('');
});
const rule = r => new Promise((ok, no) => { const body = JSON.stringify(r);
  const q = http.request({ host: '127.0.0.1', port: Number(controlPort), path: '/rule', method: 'POST',
    headers: { 'content-type': 'application/json', 'content-length': Buffer.byteLength(body) } },
  a => { a.resume(); a.on('end', ok); });
  q.on('error', no); q.end(body); });
let proxy = null;
(async () => {
  await new Promise(resolve => server.listen(Number(appPort), '127.0.0.1', resolve));
  proxy = spawn(process.execPath, [proxyPath, '--listen', proxyPort, '--upstream', appPort, '--control', controlPort],
    { stdio: ['ignore', 'pipe', 'ignore'] });
  await new Promise((ok, no) => { proxy.stdout.on('data', d => { if (String(d).includes('proxy up')) ok(); });
    proxy.on('exit', c => no(new Error('the proxy exited ' + c))); });
  const { chromium } = require(playwright);
  const browser = await chromium.launch({ headless: true,
    args: ['--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'] });
  B.TESTING.set({ DOC: { 'control-held': { label: 'control-held', id: ID, number: 103, kind: 'pdf' } }, browser,
    INIT: B.INIT_FOR(G), result: { consoleErrors: [], pageErrors: [], blocked: [], actions: [], unfinished: [] },
    FLOW: 'fail-closed', PROFILE: 'P0', BASE, CONTROL: Number(controlPort) });
  const out = {};
  try {
    const cases = [['race', 'race', false], ['race-held', 'race', true], ['waits-held', 'waits', true]];
    for (const [name, v, held] of cases) {
      const s = await B.TESTING.newContext();
      try {
        await s.page.goto(`${BASE}/?v=${v}`); await s.page.waitForSelector('#documentsTable .document-row');
        // as flowFailClosed plants it
        if (held) await rule({ kind: 'hold', match: `^/api/encounters/${ID}$`, ms: 300, times: 1 });
        out[name] = (await B.TESTING.openNoWait(s, 'control-held')).canvasDark;
      } finally { await s.context.close(); }
    }
  } finally { await browser.close(); server.close(); proxy.kill(); }
  console.log(JSON.stringify(out));
})().catch(e => {
  console.error(String(e && e.stack || e)); server.close(); if (proxy) proxy.kill(); process.exit(1); });
"""


@unittest.skipUnless(NODE and (PLAYWRIGHT / 'package.json').exists(), 'node or Playwright is not installed')
class BenchDetailRaceTests(unittest.TestCase):
    def test_a_kept_copy_drawn_before_the_refused_detail_answers_is_seen_once_the_detail_is_held(self):
        """records[1] (round 2): on loopback the refused detail answered in about 8 ms, so a page that draws its held
        copy on the view's 304 and closes on the detail's 503 drew nothing in time and the detail_kept arm was green.
        With the detail held 300 ms, as flowFailClosed now plants it, that page is seen; a page that waits for the
        detail still draws nothing."""
        with tempfile.TemporaryDirectory() as d:
            driver = Path(d, 'driver.cjs')
            driver.write_text(DETAIL_RACE_DRIVER)
            app, listen, control = _free_ports(3)
            done = subprocess.run([NODE, str(driver), str(BENCH / 'bench.cjs'), str(BENCH / 'proxy.cjs'),
                                   str(PLAYWRIGHT), str(app), str(listen), str(control), json.dumps(BD.geometry())],
                                  capture_output=True, text=True, timeout=180, env={**os.environ, 'TMPDIR': d})
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        self.assertEqual(json.loads(done.stdout.strip().splitlines()[-1]),
                         {'race': False, 'race-held': True, 'waits-held': False})


MARKER_PAGES_DRIVER = r"""
const http = require('http');
const [bench, playwright, port, marker] = process.argv.slice(2);
const B = require(bench); const BASE = `http://127.0.0.1:${port}`;
const PAGE = `
const V = new URLSearchParams(location.search).get('v'); const box = document.getElementById('documentSearch');
box.addEventListener('input', async () => { const q = box.value; if (!q) return;
  if (V === 'idb') { const r = indexedDB.open('cpt-studio', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('recent');
    r.onsuccess = () => { r.result.transaction('recent', 'readwrite').objectStore('recent').put({ q }, 'last'); }; }
  if (V === 'cache') { const c = await caches.open('cpt-studio');
    await c.put('/api/encounters/search?text=' + encodeURIComponent(q), new Response('{}')); }
  if (V === 'hash-b64') history.replaceState(null, '', '#documents/' + btoa(JSON.stringify({ q })));
  if (V === 'storage-b64') sessionStorage.setItem('cpt-list-state', btoa(JSON.stringify({ q })));
  if (V === 'plain') sessionStorage.setItem('cpt-last-search', q);
});`;
const APP = '<!doctype html><html><body><input id="documentSearch"><script>' + PAGE + '</script></body></html>';
const server = http.createServer((req, res) => {
  const path = new URL(req.url, BASE).pathname;
  res.writeHead(path === '/' ? 200 : 404, { 'content-type': 'text/html', 'cache-control': 'no-store' });
  res.end(path === '/' ? APP : '');
});
(async () => {
  await new Promise(resolve => server.listen(Number(port), '127.0.0.1', resolve));
  const { chromium } = require(playwright);
  const browser = await chromium.launch({ headless: true,
    args: ['--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'] });
  B.TESTING.set({ DOC: {}, browser, INIT: '', result: { consoleErrors: [], pageErrors: [], blocked: [] },
    FLOW: 'records',
    PROFILE: 'P0', BASE });
  const out = {};
  try {
    for (const v of ['idb', 'cache', 'hash-b64', 'storage-b64', 'plain', 'clean']) {
      const s = await B.TESTING.newContext();
      try {
        await s.page.goto(`${BASE}/?v=${v}`); await s.page.locator('#documentSearch').click();
        for (const ch of marker) await s.page.keyboard.press(ch);
        await new Promise(resolve => setTimeout(resolve, 1000));
        out[v] = await B.TESTING.pageMarkerHits(s, [], marker);
      } finally { await s.context.close(); }
    }
  } finally { await browser.close(); server.close(); }
  console.log(JSON.stringify(out));
})().catch(e => { console.error(String(e && e.stack || e)); server.close(); process.exit(1); });
"""


@unittest.skipUnless(NODE and (PLAYWRIGHT / 'package.json').exists(), 'node or Playwright is not installed')
class BenchMarkerPagesTests(unittest.TestCase):
    def test_a_search_word_kept_in_a_record_a_cache_entry_or_base64_is_named(self):
        """records[2] (round 2): the page read saw only the names of Cache API caches and IndexedDB databases, and only
        raw or URI-encoded text. Pages keeping the typed word in an IndexedDB record, a Cache API entry, a base64 hash
        or base64 sessionStorage are each named now (the plain control as before); the clean page gives []."""
        with tempfile.TemporaryDirectory() as d:
            driver = Path(d, 'driver.cjs')
            driver.write_text(MARKER_PAGES_DRIVER)
            done = subprocess.run([NODE, str(driver), str(BENCH / 'bench.cjs'), str(PLAYWRIGHT), str(_free_ports(1)[0]),
                                   'zqxmarkerword'], capture_output=True, text=True, timeout=180,
                                  env={**os.environ, 'TMPDIR': d})
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        got = json.loads(done.stdout.strip().splitlines()[-1])
        for v, hit in (('idb', 'indexedDB:cpt-studio/recent'), ('cache', 'caches:cpt-studio:entry'),
                       ('hash-b64', 'location'), ('storage-b64', 'sessionStorage:cpt-list-state'),
                       ('plain', 'sessionStorage:cpt-last-search')):
            self.assertIn(hit, got[v], (v, got[v]))
        self.assertEqual(got['clean'], [])


CDP_LOG_DRIVER = r"""
const { EventEmitter } = require('events');
const B = require(process.argv[2]); const BASE = 'http://127.0.0.1:9';
B.TESTING.set({ DOC: {}, browser: null, INIT: '', result: {}, FLOW: 'open', PROFILE: 'P0', BASE });
(async () => {
  const cdp = new EventEmitter(); cdp.send = async () => ({});
  await B.TESTING.logFromCdp(cdp);
  const ask = (id, method, path, t, extra = {}) => cdp.emit('Network.requestWillBeSent',
    { requestId: id, wallTime: 1000 + t, timestamp: t, request: { url: BASE + path, method, headers: {} }, ...extra });
  ask('1', 'POST', '/login/', 1);
  ask('1', 'GET', '/', 1.1, { redirectResponse: { status: 302, headers: { location: '/' }, encodedDataLength: 120 } });
  cdp.emit('Network.responseReceived', { requestId: '1', response: { status: 200, headers: {} } });
  cdp.emit('Network.dataReceived', { requestId: '1', dataLength: 5244 });
  cdp.emit('Network.loadingFinished', { requestId: '1', timestamp: 1.2, encodedDataLength: 5490 });
  ask('2', 'GET', '/api/encounters/x/original?view=1', 2);
  cdp.emit('Network.responseReceived', { requestId: '2', response: { status: 304, headers: {} } });
  cdp.emit('Network.loadingFinished', { requestId: '2', timestamp: 2.1, encodedDataLength: 184 });
  const state = B.TESTING.cdpState();
  const log = state.log.map(e => `${e.method} ${e.url} ${e.status} ${e.bytes}`);
  console.log(JSON.stringify({ log, inFlight: state.inFlight }));
})().catch(e => { console.error(String(e && e.stack || e)); process.exit(1); });
"""


@unittest.skipUnless(NODE, 'node is not installed')
class BenchRehearsalLogTests(unittest.TestCase):
    def test_the_rehearsal_log_keeps_a_redirect_s_hop_and_counts_body_bytes_only(self):
        """bench[4]: a redirect's hop (POST /login/ 302) was dropped and the in-flight count never returned to 0;
        bench[5]: a 304's header bytes were counted as body bytes, failing the '0 view body bytes' gate."""
        with tempfile.TemporaryDirectory() as d:
            driver = Path(d, 'cdp.cjs')
            driver.write_text(CDP_LOG_DRIVER)
            done = subprocess.run([NODE, str(driver), str(BENCH / 'bench.cjs')], capture_output=True, text=True,
                                  timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        got = json.loads(done.stdout.strip().splitlines()[-1])
        self.assertEqual(got, {'log': ['POST /login/ 302 0', 'GET / 200 5244',
                                       'GET /api/encounters/x/original?view=1 304 0'], 'inFlight': 0})


HTTP_CACHE_DRIVER = r"""
const http = require('http');
const [bench, playwright, port] = process.argv.slice(2);
const B = require(bench); const BASE = `http://127.0.0.1:${port}`;
let served = 0;
const server = http.createServer((req, res) => {
  const path = new URL(req.url, BASE).pathname;
  if (path === '/') {
    res.writeHead(200, { 'content-type': 'text/html', 'cache-control': 'no-store' }); res.end('<p>x</p>'); return;
  }
  served += 1;
  res.writeHead(200, { 'content-type': 'application/pdf',
    'cache-control': path === '/cached' ? 'private, max-age=600' : 'no-store' }); res.end('%PDF-1.4 x');
});
(async () => {
  await new Promise(resolve => server.listen(Number(port), '127.0.0.1', resolve));
  const { chromium } = require(playwright);
  const browser = await chromium.launch({ headless: true,
    args: ['--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'] });
  B.TESTING.set({ DOC: {}, browser, INIT: '', result: { consoleErrors: [], pageErrors: [], blocked: [] },
    FLOW: 'left-behind', PROFILE: 'P0', BASE });
  const out = {};
  try {
    for (const path of ['/cached', '/fresh']) {
      const s = await B.TESTING.newContext(); const cached = []; const urls = new Map();
      try {
        await s.cdp.send('Network.enable'); B.TESTING.watchHttpCache(s.cdp, cached, urls);
        await s.page.goto(`${BASE}/`);
        for (let i = 0; i < 3; i += 1) await s.page.evaluate(p => fetch(p).then(r => r.arrayBuffer()), path);
        await new Promise(r => setTimeout(r, 300));
        out[path] = [...new Set(cached.map(id => new URL(urls.get(id)).pathname))];
      } finally { await s.context.close(); }
    }
  } finally { await browser.close(); server.close(); }
  console.log(JSON.stringify({ ...out, served }));
})().catch(e => { console.error(String(e && e.stack || e)); server.close(); process.exit(1); });
"""


@unittest.skipUnless(NODE and (PLAYWRIGHT / 'package.json').exists(), 'node or Playwright is not installed')
class BenchHttpCacheTests(unittest.TestCase):
    def test_an_answer_the_http_cache_served_is_seen(self):
        """bench[6]: left.not_from_http_cache listened only for requestServedFromCache, which a fetch's disk-cache hit
        never raises, so re-opens served from the HTTP cache passed."""
        with tempfile.TemporaryDirectory() as d:
            driver = Path(d, 'cache.cjs')
            driver.write_text(HTTP_CACHE_DRIVER)
            port = _free_ports(1)[0]
            done = subprocess.run([NODE, str(driver), str(BENCH / 'bench.cjs'), str(PLAYWRIGHT), str(port)],
                                  capture_output=True, text=True, timeout=180, env={**os.environ, 'TMPDIR': d})
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        got = json.loads(done.stdout.strip().splitlines()[-1])
        self.assertEqual(got['/cached'], ['/cached'])  # asked 3 times, served once: twice from the cache, seen
        self.assertEqual(got['/fresh'], [])
        self.assertEqual(got['served'], 4)  # 1 for /cached, 3 for /fresh


class BenchBrowserFlowPinsTests(unittest.TestCase):
    def test_each_nav_tab_is_recorded_and_a_tab_that_never_opens_is_an_error(self):
        """bench[0]: a tab that timed out was skipped silently, and the tabs were pooled with the list returns."""
        source = (BENCH / 'bench.cjs').read_text()
        self.assertIn('metric(`open.tab.opaque.${nav}.${PROFILE}`, t.opaque);', source)
        self.assertIn('if (!t) { result.errors.push(`open ${PROFILE} context ${k}: the ${nav} tab never became '
                      'opaque`);', source)
        self.assertIn('the queue tab never became opaque', source)
        self.assertIn('the overview tab never became opaque', source)

    def test_the_records_and_fail_closed_flows_plant_what_their_gates_need(self):
        """records[8]: the records flow downloads three files; records[10]: a kept re-open's view is held 300 ms in the
        records and fail-closed flows; records[9]: a document is held for the detail arm, and every painted list row
        counts; records[4]: the page is read for the marker. (Their red on a planted fault: laneM/PROOFS.md.)"""
        source = (BENCH / 'bench.cjs').read_text()
        flow = source[source.index('async function flowRecords('):source.index('async function flowFailClosed(')]
        self.assertIn("for (const [label, query] of [['text-2p', ''], ['word-3p', ''], "
                      "['word-3p', '?format=original']])", flow)
        # records[0] (round 2): the polls end with a document this sign-in never read, the poll release 1 records
        self.assertIn("for (const label of ['text-4p', 'text-4p', 'text-4p', 'text-10p']) {", flow)
        # records[5] (round 2): page 1 read again after it changed, so the repeat rule meets a changed list
        tabs = "await tab(s, 'workspace', 'records-changed'); await tab(s, 'documents', 'records-changed');"
        self.assertIn(f"await act('destroy', {{ doc: 'scan-20p' }});\n      {tabs}\n"
                      f"      await act('destroy', {{ doc: 'scan-20p', on: false }});\n      {tabs}", flow)
        self.assertIn("if (kept.has(label)) await proxyRule({ kind: 'delay',", flow)
        for step in ("await typeMarker(); await read();", "await box.fill(''); await sleep(800); await read();",
                     "await typeMarker(); await s.page.keyboard.press('Enter'); await sleep(800); await read();",
                     "await s.page.keyboard.press('Tab'); await sleep(800); await read();",
                     "await tab(s, 'queue', 'records-marker'); await read();",
                     "await s.page.reload(); await s.page.waitForSelector('#main > section', { timeout: 180000 }); "
                     "await sleep(1500); await read();"):
            self.assertIn(step, flow)  # records[4]: the page read typed, cleared, at Enter, a blur, a route, pagehide
        # records[7] (round 2): one reading, 3 s after the last hover, an in-flight read counted
        self.assertIn('await sleep(3000);  // records[7]', flow)
        self.assertIn('result.checks[\'records.hover\'] = { ok: hover.requests === 0 && hover.rows === 0 && '
                      'hover.inFlight === 0, ...hover };', flow)
        closed = source[source.index('async function flowFailClosed('):source.index('async function flowLeftBehind(')]
        self.assertIn("await openDoc(s, 'control-held', 'fail-warm'); await back(s);", closed)
        self.assertIn("seen.detail_kept = await openNoWait(s, 'control-held');", closed)
        # records[1] (round 2): the held document's detail is held 300 ms right before its kept re-open
        self.assertIn("await proxyRule({ kind: 'hold', match: `^/api/encounters/${DOC['control-held'].id}$`, ms: 300, "
                      "times: 1 });\n    seen.detail_kept = await openNoWait(s, 'control-held');", closed)
        # records[2] (round 2): every end of the left-behind flow follows a search typed and cleared
        left = source[source.index('async function flowLeftBehind('):]
        self.assertIn("await s.page.locator('#documentSearch').click();\n"
                      "      for (const ch of DATA.marker) { await s.page.keyboard.press(ch); await sleep(60); }", left)
        self.assertIn("await proxyRule({ kind: 'hold', match: `^/api/encounters/${DOC['text-2p'].id}", closed)
        self.assertIn("const drawn = ['inline_kept', 'inline_fresh', 'detail_kept', 'detail']", closed)
        self.assertIn('Math.max(window.__bench.cur.rowCount || 0,', closed)

    def test_a_warm_page_load_s_standby_requests_are_counted(self):
        """bench[8]: 'only on a cold browser cache' was never measured."""
        source = (BENCH / 'bench.cjs').read_text()
        self.assertIn("metric(`open.standby.requests_warm.${PROFILE}`, (await proxyLog(warm)).filter(e => "
                      "LIBRARY.test(e.url)).length);", source)


def _node_bits(number):
    script = f'console.log(JSON.stringify(require({json.dumps(str(BENCH / "bench.cjs"))}).encodeForTest({number})))'
    return json.loads(subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=60).stdout)


# --- the judge --------------------------------------------------------------------------------------------------------

def _round(tag, number, metrics, *, parts=('open',), app_js='aaa', controls=True, checks=None, **extra):
    data = {'tag': tag, 'round': number, 'parts': list(parts), 'metrics': metrics, 'checks': checks or {},
            'controls': {name: {'ok': True} for name in ('nomarker', 'planted_delay', 'planted_fetch', 'planted_detail',
                                                         'reduced_motion', 'heap_probe')} if controls else {},
            'errors': [], 'unexpected_statuses': {}, 'console_errors': [], 'blocked_requests': [],
            'load_before': [1.0, 1.0, 1.0], 'load_after': [1.0, 1.0, 1.0],
            'files': {'studio/static/studio/app.js': app_js}, 'revision': tag}
    data.update(extra)
    return data


def _requests(effort, hashes):
    """{1: a round's requests part}: one request row per hash, sent at ``effort`` with the tree's setting the same."""
    return {1: {'requests': [{'case': 'text', 'role': 'reader', 'params_sha256': h, 'effort': effort, 'attempts': 2}
                             for h in hashes], 'requests_effort': effort}}


TABLE = {'controls': ['nomarker', 'planted_delay', 'planted_fetch', 'planted_detail', 'reduced_motion', 'heap_probe'],
         'rows': [
             {'id': 'later', 'metric': 'open.later.first_page.P0', 'min_samples': 6, 'a_section8': 298,
              'gate': [{'abs_max': 180}, {'rel_max': 0.65}], 'gain': True, 'spread': 0.03},
             {'id': 'text', 'metric': 'open.text.frame.P0', 'min_samples': 3, 'a_section8': None,
              'gate': [{'rel_max': 1.0, 'rel_plus': 15, 'floor_factor': 1.06}]},
             {'id': 'barcode', 'kind': 'check', 'check': 'correct.barcode_every_open'}]}


class JudgeTests(unittest.TestCase):
    def folder(self, rounds):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        for data in rounds:
            Path(d, f'{data["tag"]}-r{data["round"]}-{"+".join(data["parts"])}.json').write_text(json.dumps(data))
        return Path(d)

    def pair(self, a_later, b_later, a_text=100, b_text=100, *, b_app='bbb', b_extra=None, checks_ok=True):
        rounds = []
        for n in (1, 2, 3):
            rounds.append(_round('A', n, {'open.later.first_page.P0': a_later, 'open.text.frame.P0': [a_text]},
                                 checks={'correct.barcode_every_open': {'ok': True}}))
            rounds.append(_round('B', n, {'open.later.first_page.P0': b_later, 'open.text.frame.P0': [b_text]},
                                 app_js=b_app, checks={'correct.barcode_every_open': {'ok': checks_ok}},
                                 **(b_extra or {})))
        return self.folder(rounds)

    def answer(self, out, *, control=False, table=TABLE):
        return JUDGE.verdict(JUDGE.load_rounds(out), table, 'A', 'B', control=control)

    def test_pass_when_every_gate_holds(self):
        got = self.answer(self.pair([300, 298, 296], [120, 121, 119]))
        self.assertEqual(got['verdict'], 'PASS', got)

    def test_a_against_a_is_invalid_unless_asked_as_the_control(self):
        out = self.pair([300, 298, 296], [300, 298, 296], b_app='aaa')
        got = self.answer(out)
        self.assertEqual(got['verdict'], 'INVALID')
        self.assertTrue(any('app.js hashes are equal' in w for w in got['invalid']))
        self.assertNotIn('app.js', ' '.join(self.answer(out, control=True)['invalid']))

    def test_a_round_with_one_500_is_invalid(self):
        got = self.answer(self.pair([300, 298, 296], [120, 121, 119], b_extra={'unexpected_statuses': {'open:500': 1}}))
        self.assertEqual(got['verdict'], 'INVALID')

    def test_a_round_with_a_missing_or_failed_control_is_invalid(self):
        rounds = [_round('A', 1, {'open.later.first_page.P0': [300] * 6}), _round('B', 1, {'open.later.first_page.P0':
                  [120] * 6}, app_js='bbb', controls=False)]
        got = self.answer(self.folder(rounds))
        self.assertEqual(got['verdict'], 'INVALID')
        self.assertTrue(any('control nomarker missing' in w for w in got['invalid']))
        failed = _round('B', 1, {'open.later.first_page.P0': [120] * 6}, app_js='bbb')
        failed['controls']['planted_delay'] = {'ok': False, 'shift': 30}
        got = self.answer(self.folder([_round('A', 1, {'open.later.first_page.P0': [300] * 6}), failed]))
        self.assertTrue(any('control planted_delay failed' in w for w in got['invalid']))

    def test_other_invalid_cases(self):
        loaded = self.pair([300, 298, 296], [120, 121, 119], b_extra={'load_after': [9.5, 5, 4]})
        self.assertEqual(self.answer(loaded)['verdict'], 'INVALID')
        noisy = self.pair([300, 298, 296], [120, 121, 119], b_extra={'console_errors': ['open/P0: boom']})
        self.assertEqual(self.answer(noisy)['verdict'], 'INVALID')
        failed = self.pair([300, 298, 296], [120, 121, 119], b_extra={'errors': [{'part': 'open', 'error': 'x'}]})
        self.assertEqual(self.answer(failed)['verdict'], 'INVALID')
        few = self.answer(self.pair([300, 298, 296], [120]))
        self.assertEqual(few['verdict'], 'INVALID')
        off = self.answer(self.pair([400, 398, 396], [120, 121, 119]))  # A 34% from section 8's 298
        self.assertEqual(off['verdict'], 'INVALID')
        self.assertTrue(any('20%' in ' '.join(r['why']) for r in off['rows']))
        nofloor = copy.deepcopy(TABLE)
        nofloor['rows'][1]['gate'][0].pop('floor_factor')
        self.assertEqual(self.answer(self.pair([300, 298, 296], [120, 121, 119]), table=nofloor)['verdict'], 'INVALID')

    def test_a_retried_round_supersedes_its_invalid_attempt(self):
        rounds = []
        for n in (1, 2, 3):
            rounds.append(_round('A', n, {'open.later.first_page.P0': [300, 298, 296], 'open.text.frame.P0': [100]},
                                 checks={'correct.barcode_every_open': {'ok': True}}))
            rounds.append(_round('B', n, {'open.later.first_page.P0': [120, 121, 119], 'open.text.frame.P0': [100]},
                                 app_js='bbb', checks={'correct.barcode_every_open': {'ok': True}}))
        rounds[1]['load_after'] = [12.0, 9.0, 7.0]  # B round 1 spoiled by another process
        out = self.folder(rounds)
        self.assertEqual(self.answer(out)['verdict'], 'INVALID')
        retry = _round('B', 101, {'open.later.first_page.P0': [122, 120, 118], 'open.text.frame.P0': [101]},
                       app_js='bbb', checks={'correct.barcode_every_open': {'ok': True}})
        Path(out, 'B-r101-open.json').write_text(json.dumps(retry))
        kept, superseded = JUDGE.chosen_attempts(out)
        self.assertEqual(superseded, ['B-r1-open.json'])
        self.assertIn('B-r101-open.json', [p.name for p in kept])
        self.assertEqual(sorted(JUDGE.load_rounds(out)['B']), [1, 2, 3])
        self.assertEqual(self.answer(out)['verdict'], 'PASS')

    def test_b_ten_percent_slower_fails(self):
        got = self.answer(self.pair([300, 298, 296], [328, 330, 326], a_text=100, b_text=110))
        self.assertEqual(got['verdict'], 'FAIL')
        text = next(r for r in got['rows'] if r['id'] == 'text')
        self.assertEqual(text['verdict'], 'PASS')  # 110 <= max(100 + 15, 1.06 x 100)
        slower = self.answer(self.pair([300, 298, 296], [120, 121, 119], a_text=1000, b_text=1100))
        self.assertEqual(next(r for r in slower['rows'] if r['id'] == 'text')['verdict'], 'FAIL')  # 1100 > 1060

    def test_a_barcode_mismatch_fails(self):
        got = self.answer(self.pair([300, 298, 296], [120, 121, 119], checks_ok=False))
        self.assertEqual(got['verdict'], 'FAIL')
        self.assertEqual(next(r for r in got['rows'] if r['id'] == 'barcode')['verdict'], 'FAIL')

    def test_the_floor_is_used_where_the_written_limit_is_tighter(self):
        row = {'id': 'scan', 'metric': 'm', 'min_samples': 1, 'a_section8': None,
               'gate': [{'rel_max': 1.02, 'floor_factor': 1.10}]}
        a = {1: {'metrics': {'m': [100]}}}
        self.assertEqual(JUDGE.judge_row(row, a, {1: {'metrics': {'m': [109]}}})['verdict'], 'PASS')
        self.assertEqual(JUDGE.judge_row(row, a, {1: {'metrics': {'m': [111]}}})['verdict'], 'FAIL')
        tight = {**row, 'gate': [{'rel_max': 1.36, 'no_worse': True, 'floor_factor': 1.10}]}
        self.assertEqual(JUDGE.judge_row(tight, a, {1: {'metrics': {'m': [135]}}})['verdict'], 'PASS')  # 1.36 wins

    def test_a_check_is_ok_only_when_every_file_of_its_round_says_so(self):
        """judge[0], records[0]: a round's files were merged last-file-wins, so open@P3's ok overwrote open@P0's failed
        barcode, and the left-behind file's ok overwrote open@P1's failed no-store. Each check is ANDed now."""
        def run(failing):
            rounds = []
            for n in (1, 2, 3):
                rounds.append(_round('A', n, {'open.later.first_page.P0': [300, 298, 296], 'open.text.frame.P0': [100]},
                                     checks={'correct.barcode_every_open': {'ok': True}}))
                for profile in ('P0', 'P3'):
                    ok = not (n == 1 and profile == failing)
                    rounds.append(_round('B', n, {'open.later.first_page.P0': [120, 121, 119],
                                                  'open.text.frame.P0': [100]}, app_js='bbb',
                                         parts=(f'open@{profile}',),
                                         checks={'correct.barcode_every_open': {'ok': ok, 'opens': 9}}))
            return self.answer(self.folder(rounds))
        for failing in ('P0', 'P3'):  # judge[3]: the failing file sorting first (open@P0), then last (open@P3)
            with self.subTest(failing=failing):
                got = run(failing)
                self.assertEqual(got['verdict'], 'FAIL', got)
                self.assertEqual(next(r for r in got['rows'] if r['id'] == 'barcode')['verdict'], 'FAIL')
        merged = {}
        JUDGE._and_merge(merged, {'left.no_store': {'ok': False, 'missing': ['GET /original 304']}})
        JUDGE._and_merge(merged, {'left.no_store': {'ok': True}})
        self.assertFalse(merged['left.no_store']['ok'])
        self.assertEqual(len(merged['left.no_store']['by_file']), 2)
        merged = {}
        JUDGE._and_merge(merged, {'left.no_store': {'ok': True}})
        JUDGE._and_merge(merged, {'left.no_store': {'ok': False, 'missing': ['GET /original 304']}})
        self.assertFalse(merged['left.no_store']['ok'])  # judge[3]: the failing file merged last

    def test_a_file_needs_the_controls_only_where_its_open_part_ran_at_p0(self):
        """Only the P0 open flow plants the controls; an open@P1 file without them is valid on its own, an open@P0 or
        an all-profile open file without them is not (the driver keeps and retries by this rule)."""
        bare = _round('B', 1, {'x': [1]}, controls=False)
        self.assertEqual(JUDGE.attempt_reasons('B-r1-open@P1.json', bare, TABLE['controls']), [])
        for name in ('B-r1-open@P0.json', 'B-r1-open.json'):
            self.assertTrue(JUDGE.attempt_reasons(name, bare, TABLE['controls']), name)
        self.assertEqual(JUDGE.attempt_reasons('B-r1-lists@P0.json', dict(bare, parts=['lists']), TABLE['controls']),
                         [])

    def test_an_operation_that_never_finished_is_invalid(self):
        """judge[1], bench[0]: a tab that never became opaque left no sample, and the row still met its count."""
        stuck = self.answer(self.pair([300, 298, 296], [120, 121, 119],
                                      b_extra={'unfinished': ['P0 tab-queue queue']}))
        self.assertEqual(stuck['verdict'], 'INVALID')
        self.assertTrue(any('never finished' in w and 'tab-queue' in w for w in stuck['invalid']), stuck)

    def test_a_valid_round_is_never_superseded(self):
        """judge[2], records[1]: an attempt after a valid round replaced it, so a FAIL disappeared. The first valid
        attempt is final; a later one is set aside, named and never judged."""
        rounds = []
        for n in (1, 2, 3):
            rounds.append(_round('A', n, {'open.later.first_page.P0': [300, 298, 296], 'open.text.frame.P0': [100]},
                                 checks={'correct.barcode_every_open': {'ok': True}}))
            rounds.append(_round('B', n, {'open.later.first_page.P0': [200, 201, 199], 'open.text.frame.P0': [100]},
                                 app_js='bbb', checks={'correct.barcode_every_open': {'ok': n != 1}}))
        out = self.folder(rounds)
        for n in (1, 2, 3):
            later = _round('B', 100 + n, {'open.later.first_page.P0': [90, 91, 89], 'open.text.frame.P0': [100]},
                           app_js='bbb', checks={'correct.barcode_every_open': {'ok': True}})
            Path(out, f'B-r{100 + n}-open.json').write_text(json.dumps(later))
        got = self.answer(out)
        self.assertEqual(got['verdict'], 'FAIL', got)
        self.assertEqual(sorted(got['superseded']), ['B-r101-open.json', 'B-r102-open.json', 'B-r103-open.json'])
        kept, unused = JUDGE.chosen_attempts(out)
        self.assertIn('B-r1-open.json', [p.name for p in kept])
        records = [_round('A', 1, {'x': [1]}, parts=('records',)),
                   _round('B', 1, {'x': [1]}, parts=('records',), app_js='bbb', load_after=[2.0, 1.0, 1.0],
                          checks={'records.equation': {'ok': False}}),
                   _round('B', 101, {'x': [1]}, parts=('records',), app_js='bbb',
                          checks={'records.equation': {'ok': True}})]
        table = {'controls': [], 'rows': [{'id': 'eq', 'kind': 'check', 'check': 'records.equation'}]}
        self.assertEqual(self.answer(self.folder(records), table=table)['verdict'], 'FAIL')

    def test_a_tag_is_one_tree(self):
        """judge[3]: a B file measured on A's tree (or on another B head) never enters B's verdict unseen."""
        rounds = []
        for n in (1, 2, 3):
            rounds.append(_round('A', n, {'open.later.first_page.P0': [300, 298, 296], 'open.text.frame.P0': [100]},
                                 checks={'correct.barcode_every_open': {'ok': True}}))
            rounds.append(_round('B', n, {'open.later.first_page.P0': [120, 121, 119], 'open.text.frame.P0': [100]},
                                 app_js='bbb', checks={'correct.barcode_every_open': {'ok': True}}))
        out = self.folder(rounds)
        self.assertEqual(self.answer(out)['verdict'], 'PASS')
        stray = _round('B', 2, {'x': [1]}, parts=('lists',), app_js='aaa', revision='A')  # not last in its round
        Path(out, 'B-r2-lists.json').write_text(json.dumps(stray))
        got = self.answer(out)
        self.assertEqual(got['verdict'], 'INVALID')
        self.assertTrue(any('2 trees' in w for w in got['invalid']), got['invalid'])
        self.assertTrue(any('app.js hashes are equal' in w for w in got['invalid']), got['invalid'])
        Path(out, 'B-r2-lists.json').unlink()
        other = _round('B', 101, {'open.later.first_page.P0': [120]}, app_js='ccc', revision='B-old',
                       load_after=[1.0, 1.0, 1.0])
        rounds[1]['load_after'] = [12.0, 1.0, 1.0]  # B round 1 INVALID, so its retry on another head is used
        Path(out, 'B-r1-open.json').write_text(json.dumps(rounds[1]))
        Path(out, 'B-r101-open.json').write_text(json.dumps(other))
        got = self.answer(out)
        self.assertEqual(got['verdict'], 'INVALID')
        self.assertEqual(got['trees'], {'A': ['A'], 'B': ['B', 'B-old']})

    def test_a_no_worse_than_a_floor_is_never_below_a_plus_one_instrument_step(self):
        """judge[5]: the A-column check allowed one Event Timing step (a_step), the floor did not, so a B one step from
        A FAILed and the same samples swapped PASSed. The floor is now max(floor_factor x A, A + a_step)."""
        row = {'id': 'r', 'metric': 'm', 'min_samples': 3, 'a_recorded': 17, 'a_spread': 0.1177, 'spread': 0.1177,
               'a_step': 8, 'gate': [{'rel_max': 1.0, 'spread': 0.1177, 'floor_factor': 1.2354}]}
        a = {n: {'metrics': {'m': [v]}} for n, v in ((1, 16), (2, 16), (3, 24))}
        b = lambda values: {n: {'metrics': {'m': [v]}} for n, v in zip((1, 2, 3), values)}
        self.assertEqual(JUDGE.judge_row(row, a, b((24, 24, 16)))['verdict'], 'PASS')  # one step: limit 24
        self.assertEqual(JUDGE.judge_row(row, a, b((32, 32, 24)))['verdict'], 'FAIL')  # two steps worse
        stepless = {k: v for k, v in row.items() if k != 'a_step'}
        self.assertEqual(JUDGE.judge_row(stepless, a, b((24, 24, 16)))['verdict'], 'FAIL')  # limit 19.77
        plus = {**row, 'gate': [{'rel_max': 1.0, 'spread': 0.1177, 'floor_factor': 1.2354, 'plus_metric': 'later'}]}
        b_plus = lambda values: {n: {'metrics': {'m': [v], 'later': [40]}} for n, v in zip((1, 2, 3), values)}
        self.assertEqual(JUDGE.judge_row(plus, a, b_plus((64, 64, 56)))['verdict'], 'PASS')  # 16 + 8 + 40
        self.assertEqual(JUDGE.judge_row(plus, a, b_plus((72, 72, 64)))['verdict'], 'FAIL')

    def test_a_s_own_control_checks_are_read(self):
        """judge[7]: the walk 'on A first and then on B' and the correctness checks 'checked on A as the control'
        passed with A failing: a row marked control_a is INVALID unless A passed it in every round."""
        rows = [{'id': 'walk.passes', 'table': 'walk', 'kind': 'check', 'check': 'walk.passes', 'control_a': True}]
        table = {'controls': [], 'rows': rows}

        def verdict(a_ok, a_has=True):
            d = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, d)
            for n in (1, 2, 3):
                if a_has:
                    Path(d, f'A-r{n}-walk.json').write_text(json.dumps(
                        _round('A', n, {}, parts=('walk',), controls=False, checks={'walk.passes': {'ok': a_ok}})))
                else:
                    Path(d, f'A-r{n}-plans.json').write_text(json.dumps(
                        _round('A', n, {}, parts=('plans',), controls=False)))
                Path(d, f'B-r{n}-walk.json').write_text(json.dumps(_round(
                    'B', n, {}, parts=('walk',), app_js='bbb', controls=False, checks={'walk.passes': {'ok': True}})))
            return JUDGE.verdict(JUDGE.load_rounds(d), table, 'A', 'B')
        self.assertEqual(verdict(True)['verdict'], 'PASS')
        self.assertEqual(verdict(False)['verdict'], 'INVALID')  # A, the control, failed
        self.assertEqual(verdict(True, a_has=False)['verdict'], 'INVALID')  # A never walked

    def test_a_round_of_another_tree_is_superseded_by_its_retry_on_the_named_tree(self):
        """judge-9: a round of another tree was valid on its own, so final; its retry on the right tree was set
        aside and the tag stayed INVALID. Named trees: B's by --b-revision, A's by the table's a_tree."""
        rounds = []
        for n in (1, 2, 3):
            rounds.append(_round('A', n, {'open.later.first_page.P0': [300, 298, 296], 'open.text.frame.P0': [100]},
                                 checks={'correct.barcode_every_open': {'ok': True}}))
            rounds.append(_round('B', n, {'open.later.first_page.P0': [120, 121, 119], 'open.text.frame.P0': [100]},
                                 app_js='bbb', checks={'correct.barcode_every_open': {'ok': True}},
                                 revision='B-stale' if n == 1 else 'B'))
        out = self.folder(rounds)
        retry = _round('B', 101, {'open.later.first_page.P0': [120, 121, 119], 'open.text.frame.P0': [100]},
                       app_js='bbb', checks={'correct.barcode_every_open': {'ok': True}}, revision='B')
        Path(out, 'B-r101-open.json').write_text(json.dumps(retry))
        self.assertEqual(self.answer(out)['verdict'], 'INVALID')  # no tree named: the tag's two trees
        got = JUDGE.verdict(JUDGE.load_rounds(out, (), {'B': 'B'}), TABLE, 'A', 'B', b_revision='B')
        self.assertEqual((got['verdict'], got['superseded']), ('PASS', ['B-r1-open.json']), got)
        stale = self.folder([r if r['tag'] == 'A' else {**r, 'revision': 'B-stale'} for r in rounds])
        got = JUDGE.verdict(JUDGE.load_rounds(stale, (), {'B': 'B'}), TABLE, 'A', 'B', b_revision='B')
        self.assertEqual(got['verdict'], 'INVALID')  # every B file of another tree: never judged as B
        self.assertTrue(any('B is not B' in w for w in got['invalid']), got['invalid'])
        failing = self.folder([r if r['tag'] == 'A' else {**r, 'revision': 'B', 'metrics': {
            'open.later.first_page.P0': [200, 201, 199], 'open.text.frame.P0': [100]}} for r in rounds])
        Path(failing, 'B-r101-open.json').write_text(json.dumps(retry))  # judge[2]: a valid round stays final
        got = JUDGE.verdict(JUDGE.load_rounds(failing, (), {'B': 'B'}), TABLE, 'A', 'B', b_revision='B')
        self.assertEqual((got['verdict'], got['superseded']), ('FAIL', ['B-r101-open.json']), got)
        r1 = '816045c7264481bc6956285e1ca89991b9fcec2f'
        table = {**copy.deepcopy(TABLE), 'a_tree': f'{r1} (release 1)'}
        a_rounds = self.folder([{**r, 'revision': ('0' * 40 if r['round'] == 1 else r1)} if r['tag'] == 'A' else
                                {**r, 'revision': 'B'} for r in rounds])
        Path(a_rounds, 'A-r101-open.json').write_text(json.dumps({**rounds[0], 'round': 101, 'revision': r1}))
        Path(table_path := a_rounds / 't.json').write_text(json.dumps(table))
        with unittest.mock.patch('sys.stdout', io.StringIO()) as printed:
            code = JUDGE.main(['verdict', '--out', str(a_rounds), '--a', 'A', '--b', 'B', '--acceptance',
                               str(table_path)])
        self.assertEqual(code, 0, printed.getvalue())
        self.assertEqual(json.loads(printed.getvalue())['superseded'], ['A-r1-open.json'])

    def test_a_is_release_one_s_tree_when_the_table_names_it(self):
        """protocol[1]: an A measured on another tree would loosen exactly the gates whose limit is A."""
        table = {**copy.deepcopy(TABLE), 'a_tree': '816045c7264481bc6956285e1ca89991b9fcec2f (release 1)'}
        rounds = []
        for n in (1, 2, 3):
            rounds.append(_round('A', n, {'open.later.first_page.P0': [300, 298, 296], 'open.text.frame.P0': [100]},
                                 checks={'correct.barcode_every_open': {'ok': True}},
                                 revision='816045c7264481bc6956285e1ca89991b9fcec2f'))
            rounds.append(_round('B', n, {'open.later.first_page.P0': [120, 121, 119], 'open.text.frame.P0': [100]},
                                 app_js='bbb', checks={'correct.barcode_every_open': {'ok': True}}))
        self.assertEqual(self.answer(self.folder(rounds), table=table)['verdict'], 'PASS')
        for r in rounds:
            if r['tag'] == 'A':
                r['revision'] = '0' * 40
        got = self.answer(self.folder(rounds), table=table)
        self.assertEqual(got['verdict'], 'INVALID')
        self.assertTrue(any('is not release 1' in w for w in got['invalid']), got['invalid'])

    def test_too_few_a_samples_is_invalid_wherever_the_row_reads_a(self):
        """judge[4]: only rows saying needs_a true counted A's samples, so a session with one A round judged B."""
        few_a = self.answer(self.pair([300], [120, 121, 119]))  # A 3 later-open samples, the row needs 6
        self.assertEqual(few_a['verdict'], 'INVALID', few_a)
        self.assertTrue(any('too few samples (A 3, B 9' in ' '.join(r['why']) for r in few_a['rows']), few_a)
        table = {'controls': TABLE['controls'], 'rows': [
            {'id': 'abs', 'metric': 'pause.detail.ms', 'min_samples': 3, 'a_recorded': 74.65,
             'gate': [{'abs_max': 50}]},
            {'id': 'new', 'metric': 'open.reopen.view_body_bytes.P0', 'min_samples': 3, 'needs_a': False,
             'gate': [{'eq': 0}]}]}
        rounds = [_round('A', n, {'open.later.first_page.P0': [300]}) for n in (1, 2, 3)]
        rounds += [_round('B', n, {'pause.detail.ms': [45], 'open.reopen.view_body_bytes.P0': [0]}, app_js='bbb')
                   for n in (1, 2, 3)]
        rows = {r['id']: r for r in self.answer(self.folder(rounds), table=table)['rows']}
        self.assertEqual(rows['abs']['verdict'], 'INVALID', rows['abs'])  # no A: the A-column check cannot run
        self.assertEqual(rows['new']['verdict'], 'PASS', rows['new'])

    def test_the_a_column_tolerance_is_at_least_one_event_timing_step(self):
        """judge[9]: Event Timing reports 8 ms steps, so at a recorded 32 ms one key 8 ms slower is still A."""
        row = {'id': 'k', 'metric': 'lists.search.key_event.100.P0', 'stat': 'max', 'min_samples': 4,
               'a_recorded': 32, 'a_spread': 0.0, 'a_step': 8, 'gate': [{'abs_max': 64}], 'spread': 0.0}
        b = {1: {'metrics': {row['metric']: [16, 24, 24, 16]}}}
        for keys, verdict in (([40, 24, 32, 16], 'PASS'), ([24, 16, 16, 24], 'PASS'), ([48, 24, 32, 16], 'INVALID')):
            with self.subTest(keys=keys):
                self.assertEqual(JUDGE.judge_row(row, {1: {'metrics': {row['metric']: keys}}}, b)['verdict'], verdict)
        bare = {k: v for k, v in row.items() if k != 'a_step'}
        self.assertEqual(JUDGE.judge_row(bare, {1: {'metrics': {row['metric']: [40, 24, 32, 16]}}}, b)['verdict'],
                         'INVALID')

    def test_a_limit_below_a_asks_for_a_gain_beyond_twice_the_spread(self):
        """judge[10]: scan20-P0's 400 ms sits 8% under a recorded 436 ms with a 4.6% spread, so a 398 ms B 'gained'
        inside release 1's own spread. Wherever a limit lies below A the gain rule applies, flag or not."""
        row = {'id': 's', 'metric': 'm', 'min_samples': 1, 'a_recorded': 436, 'gate': [{'abs_max': 400}],
               'spread': 0.0461}
        a = {1: {'metrics': {'m': [436]}}}
        self.assertEqual(JUDGE.judge_row(row, a, {1: {'metrics': {'m': [398]}}})['verdict'], 'FAIL')
        self.assertEqual(JUDGE.judge_row(row, a, {1: {'metrics': {'m': [390]}}})['verdict'], 'PASS')
        self.assertEqual(JUDGE.judge_row({k: v for k, v in row.items() if k != 'spread'}, a,
                                         {1: {'metrics': {'m': [390]}}})['verdict'], 'INVALID')
        above = {**row, 'gate': [{'abs_max': 500}]}  # a limit above A asks for no gain
        self.assertEqual(JUDGE.judge_row(above, a, {1: {'metrics': {'m': [440]}}})['verdict'], 'PASS')
        rate = {'id': 'r', 'metric': 'm', 'min_samples': 1, 'gate': [{'abs_min': 100}], 'spread': 0.05}
        slow = {1: {'metrics': {'m': [95]}}}
        self.assertEqual(JUDGE.judge_row(rate, slow, {1: {'metrics': {'m': [101]}}})['verdict'], 'FAIL')  # 6% <= 10%
        self.assertEqual(JUDGE.judge_row(rate, slow, {1: {'metrics': {'m': [110]}}})['verdict'], 'PASS')

    def test_the_spread_and_the_floors_refuse_an_invalid_or_partial_pair(self):
        """protocol[0], [3]: floors and a recorded A came out of an INVALID round (load 22) and passed every test."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        good = {'open.later.first_page.P0': [300, 298], 'open.text.frame.P0': [100]}
        Path(d, 'A-r1-open.json').write_text(json.dumps(_round('A', 1, good, load_max=9.5)))
        Path(d, 'A-r2-open.json').write_text(json.dumps(_round('A', 2, good)))
        table = Path(d, 'acceptance.json')
        table.write_text(json.dumps(TABLE))
        for command in ('spread', 'floors'):
            with self.subTest(command=command):
                extra = ['--source', 'test'] if command == 'floors' else []
                out, err = io.StringIO(), io.StringIO()
                with unittest.mock.patch('sys.stdout', out), unittest.mock.patch('sys.stderr', err):
                    code = JUDGE.main([command, '--out', str(d), '--a', 'A:1', '--a', 'A:2', '--acceptance',
                                       str(table), *extra])
                self.assertEqual(code, 3)
                self.assertEqual(out.getvalue(), '')
                self.assertIn('load average 9.5', err.getvalue())
        Path(d, 'A-r101-open.json').write_text(json.dumps(_round('A', 101, good)))  # its valid retry
        out = io.StringIO()
        with unittest.mock.patch('sys.stdout', out):
            self.assertEqual(JUDGE.main(['floors', '--out', str(d), '--a', 'A:1', '--a', 'A:2', '--acceptance',
                                         str(table), '--source', 'test']), 0)
        derived = json.loads(out.getvalue())
        self.assertEqual(derived['derived']['rows']['text'], [100, 100, 100])
        Path(d, 'B-only-a-list.json').write_text('{}')  # not a round file: ignored
        partial = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, partial)
        for n in (1, 2):  # one part group only: the rows that read open's A have no value
            Path(partial, f'A-r{n}-lists.json').write_text(json.dumps(_round('A', n, {'x': [1]}, parts=('lists',))))
        err = io.StringIO()
        with unittest.mock.patch('sys.stderr', err), unittest.mock.patch('sys.stdout', io.StringIO()):
            self.assertEqual(JUDGE.main(['floors', '--out', str(partial), '--a', 'A:1', '--a', 'A:2',
                                         '--acceptance', str(table), '--source', 'test']), 3)
        self.assertIn('no value for', err.getvalue())

    def test_the_spread_and_the_floors_refuse_a_pair_that_is_not_release_one(self):
        """The A/A is release 1's: a pair measured on another tree derives no floor, no spread and no recorded A, as
        the verdict calls such an A INVALID (judge[3], protocol[1])."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        table = Path(d, 'acceptance.json')
        table.write_text(json.dumps({**TABLE, 'a_tree': '816045c7264481bc6956285e1ca89991b9fcec2f (release 1)'}))
        for revision, want in (('816045c7264481bc6956285e1ca89991b9fcec2f', 0), ('0' * 40, 3)):
            for n, values in ((1, [300, 298]), (2, [306, 304])):
                Path(d, f'A-r{n}-open.json').write_text(json.dumps(_round(
                    'A', n, {'open.later.first_page.P0': values, 'open.text.frame.P0': [100 + n]}, revision=revision)))
            for command in ('spread', 'floors'):
                with self.subTest(revision=revision[:8], command=command):
                    extra = ['--source', 'test'] if command == 'floors' else []
                    out, err = io.StringIO(), io.StringIO()
                    with unittest.mock.patch('sys.stdout', out), unittest.mock.patch('sys.stderr', err):
                        code = JUDGE.main([command, '--out', str(d), '--a', 'A:1', '--a', 'A:2', '--acceptance',
                                           str(table), *extra])
                    self.assertEqual(code, want, err.getvalue())
                    if want:
                        self.assertEqual(out.getvalue(), '')
                        self.assertIn('is not release 1', err.getvalue())

    def test_the_spread_and_the_floors_refuse_a_pair_whose_rounds_ran_different_parts(self):
        """protocol[0]: an A/A pair is the same part groups twice. A group in one round only (here a check-only group,
        which no row's A reads, so derive alone accepts the pair) is refused, exit 3, nothing printed."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        good = {'open.later.first_page.P0': [300, 298], 'open.text.frame.P0': [100]}
        gates = ('records', 'left-behind', 'correct')
        for n in (1, 2):
            Path(d, f'A-r{n}-open.json').write_text(json.dumps(_round('A', n, good)))
        Path(d, 'A-r1-records+left-behind+correct.json').write_text(json.dumps(
            _round('A', 1, {}, parts=gates, controls=False, checks={'records.equation': {'ok': True}})))
        table = Path(d, 'acceptance.json')
        table.write_text(json.dumps(TABLE))
        for command in ('spread', 'floors'):
            with self.subTest(command=command):
                extra = ['--source', 'test'] if command == 'floors' else []
                out, err = io.StringIO(), io.StringIO()
                with unittest.mock.patch('sys.stdout', out), unittest.mock.patch('sys.stderr', err):
                    code = JUDGE.main([command, '--out', str(d), '--a', 'A:1', '--a', 'A:2', '--acceptance',
                                       str(table), *extra])
                self.assertEqual(code, 3)
                self.assertEqual(out.getvalue(), '')
                self.assertIn('ran different parts', err.getvalue())
        Path(d, 'A-r2-records+left-behind+correct.json').write_text(json.dumps(
            _round('A', 2, {}, parts=gates, controls=False, checks={'records.equation': {'ok': True}})))
        with unittest.mock.patch('sys.stdout', io.StringIO()):  # the same groups twice: the pair derives
            self.assertEqual(JUDGE.main(['floors', '--out', str(d), '--a', 'A:1', '--a', 'A:2', '--acceptance',
                                         str(table), '--source', 'test']), 0)

    def test_floors_check_holds_the_table_to_its_own_pair_byte_for_byte(self):
        """protocol[2]: the committed table must be exactly what judge.py floors writes from its A/A pair."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        for n, values in ((1, [300, 298]), (2, [306, 304])):
            Path(d, f'A-r{n}-open.json').write_text(json.dumps(_round('A', n, {'open.later.first_page.P0': values,
                                                                                'open.text.frame.P0': [100 + n]})))
        table = Path(d, 'acceptance.json')
        table.write_text(json.dumps(TABLE))
        args = ['floors', '--out', str(d), '--a', 'A:1', '--a', 'A:2', '--acceptance', str(table), '--source', 'x']
        out = io.StringIO()
        with unittest.mock.patch('sys.stdout', out):
            self.assertEqual(JUDGE.main(args), 0)
        table.write_text(out.getvalue())
        with unittest.mock.patch('sys.stderr', io.StringIO()):
            self.assertEqual(JUDGE.main(args + ['--check']), 0)
        moved = json.loads(out.getvalue())
        moved['rows'][1]['gate'][0]['floor_factor'] = 2.0
        table.write_text(json.dumps(moved, indent=1) + '\n')
        with unittest.mock.patch('sys.stderr', io.StringIO()):
            self.assertEqual(JUDGE.main(args + ['--check']), 1)

    def test_a_gain_must_exceed_twice_the_spread(self):
        row = {'id': 'g', 'metric': 'm', 'min_samples': 1, 'a_section8': None, 'gate': [{'rel_max': 0.98}],
               'gain': True, 'spread': 0.03}
        a = {1: {'metrics': {'m': [100]}}}
        self.assertEqual(JUDGE.judge_row(row, a, {1: {'metrics': {'m': [97]}}})['verdict'], 'FAIL')  # 3% <= 6%
        row['gate'] = [{'rel_max': 0.95}]
        self.assertEqual(JUDGE.judge_row(row, a, {1: {'metrics': {'m': [93]}}})['verdict'], 'PASS')
        up = {'id': 'u', 'metric': 'm', 'min_samples': 1, 'a_section8': None, 'gate': [{'rel_min': 1.8}], 'gain': True,
              'gain_direction': 'up', 'spread': 0.05}
        self.assertEqual(JUDGE.judge_row(up, a, {1: {'metrics': {'m': [190]}}})['verdict'], 'PASS')
        self.assertEqual(JUDGE.judge_row(up, a, {1: {'metrics': {'m': [170]}}})['verdict'], 'FAIL')

    def test_ratios_round_trips_and_equality(self):
        b = {1: {'metrics': {'p2': [400], 'p0': [150], 'x': [30], 'y': [20], 's50': [13], 's5000': [13], 'z': [21]}}}
        self.assertEqual(JUDGE.judge_row({'id': 'r', 'kind': 'round_trips', 'metric': 'p2', 'over': 'p0', 'per_ms': 200,
                                          'max': 1.3}, {}, b)['verdict'], 'PASS')  # 1.25
        self.assertEqual(JUDGE.judge_row({'id': 'r', 'kind': 'ratio', 'metric': 'x', 'over': 'y', 'max': 1.5}, {}, b)
                         ['verdict'], 'PASS')
        ratio = {'id': 'r', 'kind': 'max_ratio', 'metrics': ['x', 'y', 'z'], 'max': 1.25}
        self.assertEqual(JUDGE.judge_row(ratio, {}, b)['verdict'], 'FAIL')
        self.assertEqual(JUDGE.judge_row({'id': 'e', 'kind': 'equal', 'metrics': ['s50', 's5000']}, {}, b)['verdict'],
                         'PASS')
        b[1]['metrics']['s5000'] = [14]
        self.assertEqual(JUDGE.judge_row({'id': 'e', 'kind': 'equal', 'metrics': ['s50', 's5000']}, {}, b)['verdict'],
                         'FAIL')

    def test_what_the_coder_is_sent_must_be_equal_on_both_trees(self):
        row = {'id': 'c', 'kind': 'same_as_a', 'effort': {'a': 'max', 'b': 'high'}}
        a, b = _requests('max', ['aa']), _requests('high', ['aa'])
        self.assertEqual(JUDGE.judge_row(row, a, b)['verdict'], 'PASS')  # the effort aside, byte for byte the same
        self.assertEqual(JUDGE.judge_row(row, a, _requests('high', ['ab']))['verdict'], 'FAIL')  # one prompt byte
        self.assertEqual(JUDGE.judge_row(row, {1: {'requests': None}}, b)['verdict'], 'INVALID')

    def test_the_coder_row_compares_the_effort_as_release_one_and_r2_33_set_it(self):
        """bench[3]: B is asked at R2-33's 'high', release 1 at 'max'; the row compares every other byte and the effort
        as exactly those values, never a looser comparison."""
        row = {'id': 'c', 'kind': 'same_as_a', 'effort': {'a': 'max', 'b': 'high'}}
        self.assertEqual(JUDGE.judge_row(row, _requests('max', ['aa']), _requests('max', ['aa']))['verdict'], 'FAIL')
        self.assertEqual(JUDGE.judge_row(row, _requests('high', ['aa']), _requests('high', ['aa']))['verdict'], 'FAIL')
        named = _requests('high', ['aa'])
        named[1]['requests_effort'] = 'max'  # what the tree's settings say must be what it sent
        self.assertEqual(JUDGE.judge_row(row, _requests('max', ['aa']), named)['verdict'], 'FAIL')
        old = {1: {'requests': [['text', 'reader', 'aa', 'bb', 2]], 'requests_effort': None}}
        self.assertEqual(JUDGE.judge_row(row, old, _requests('high', ['aa']))['verdict'], 'INVALID')  # an old bench
        table = json.loads((BENCH / 'acceptance.json').read_text())
        coder = next(r for r in table['rows'] if r['id'] == 'coder-requests')
        self.assertEqual(coder.get('effort'), {'a': 'max', 'b': 'high'})

    def test_the_coder_row_never_passes_on_requests_nobody_recorded(self):
        """Two empty lists are equal, so a requests part that recorded nothing on both trees passed this row; it is
        INVALID now. Section 8 asks for 8 request hashes, and the committed row says so (min_rows 8)."""
        row = {'id': 'c', 'kind': 'same_as_a', 'effort': {'a': 'max', 'b': 'high'}}
        self.assertEqual(JUDGE.judge_row(row, _requests('max', []), _requests('high', []))['verdict'], 'INVALID')
        eight = [f'{n:02d}' for n in range(8)]
        row = {**row, 'min_rows': 8}
        self.assertEqual(JUDGE.judge_row(row, _requests('max', eight[:7]), _requests('high', eight[:7]))['verdict'],
                         'INVALID')
        self.assertEqual(JUDGE.judge_row(row, _requests('max', eight), _requests('high', []))['verdict'], 'INVALID')
        self.assertEqual(JUDGE.judge_row(row, _requests('max', eight), _requests('high', eight))['verdict'], 'PASS')
        table = json.loads((BENCH / 'acceptance.json').read_text())
        self.assertEqual(next(r for r in table['rows'] if r['id'] == 'coder-requests').get('min_rows'), 8)

    def test_the_spread_and_its_floor(self):
        first = {'metrics': {'m': [100, 102, 98], 'n': [10, 10, 10], 'z': [0]}}
        second = {'metrics': {'m': [104, 106, 102], 'n': [10, 10, 10], 'z': [0]}}
        got = JUDGE.spread(first, second)
        self.assertEqual(got['m'], 0.0393)  # 4 / 102 = 0.039216, rounded UP (protocol[5])
        self.assertEqual(got['n'], 0.0)
        self.assertEqual(got['z'], 0.0)
        self.assertEqual(JUDGE.floor_factor(0.05), 1.1)
        table = {'controls': [], 'rows': [{'id': 'x', 'metric': 'm', 'gate': [{'rel_max': 1.02}]},
                                          {'id': 'y', 'metric': 'm', 'gate': [{'abs_max': 5}]},
                                          {'id': 'g', 'metric': 'm', 'gate': [{'rel_max': 0.6}], 'gain': True}]}
        floored = JUDGE.derive(table, first, second, 'test')
        self.assertEqual(floored['rows'][0]['gate'][0]['floor_factor'], 1.0786)
        self.assertNotIn('floor_factor', floored['rows'][1]['gate'][0])
        self.assertNotIn('floor_factor', floored['rows'][2]['gate'][0])
        self.assertEqual(floored['rows'][2]['spread'], 0.0393)

    def test_the_spread_is_rounded_up_so_no_floor_is_below_c5_s_minimum(self):
        """protocol[5]: medians 18 and 16 are 2/17 = 0.117647 apart; rounded to nearest the floor 1.2352 x 17 = 20.998
        failed a B of 21 that C5's exact floor (21.0) passes."""
        self.assertGreaterEqual(JUDGE.up_spread(18, 16), 2 / 17)
        self.assertEqual(JUDGE.up_spread(18, 16), 0.1177)
        self.assertEqual(JUDGE.up_spread(100, 100), 0.0)
        self.assertEqual(JUDGE.up_spread(0.05, 0.05), 0.0)
        self.assertEqual(JUDGE.up_spread(105, 95), 0.1)  # exact at 4 decimals stays: float noise never lifts it
        row = JUDGE.derive_row({'id': 'r', 'metric': 'm', 'min_samples': 1, 'gate': [{'rel_max': 1.0}]}, 18, 16, 17)
        a = {1: {'metrics': {'m': [17]}}}
        self.assertEqual(JUDGE.judge_row(row, a, {1: {'metrics': {'m': [21]}}})['verdict'], 'PASS')
        self.assertEqual(JUDGE.judge_row(row, a, {1: {'metrics': {'m': [21.1]}}})['verdict'], 'FAIL')

    def test_derive_writes_every_row_that_reads_a_in_its_own_statistic(self):
        """protocol[1], [2]: every row whose A is read gets lane M's recorded A and its A/A spread in the row's own
        statistic (a max row whose medians agree but whose maxima differ gets the maxima's), never None; a row that says
        needs_a false gets none, and a pair that lacks a row's value is refused."""
        first = {'metrics': {'m': [10, 50, 10], 'k': [20], 'z': [5]}}
        second = {'metrics': {'m': [10, 40, 10], 'k': [21], 'z': [6]}}
        table = {'controls': [], 'rows': [
            {'id': 'max', 'metric': 'm', 'stat': 'max', 'gate': [{'abs_max': 64}]},
            {'id': 'rel', 'metric': 'k', 'gate': [{'rel_max': 1.0, 'rel_plus': 15}]},
            {'id': 'new', 'metric': 'z', 'needs_a': False, 'gate': [{'eq': 0}]},
            {'id': 'rep', 'kind': 'report', 'metric': 'k'}]}
        got = {r['id']: r for r in JUDGE.derive(table, first, second, 'test')['rows']}
        self.assertEqual(got['max']['a_recorded'], 50)  # the pooled max, not the median 10
        self.assertEqual(got['max']['a_spread'], JUDGE.up_spread(50, 40))  # the maxima's spread, the medians' is 0
        self.assertEqual(got['rel']['a_recorded'], 20.5)
        self.assertEqual(got['rel']['gate'][0]['floor_factor'], JUDGE.floor_factor(JUDGE.up_spread(20, 21)))
        for name in ('new', 'rep'):
            self.assertNotIn('a_recorded', got[name])
        with self.assertRaises(ValueError):
            JUDGE.derive(table, first, {'metrics': {'m': [10]}}, 'test')  # 'rel' reads A and the pair has no k

    def test_derive_refuses_a_round_with_too_few_samples(self):
        """Section 8 and D-R2-44: the floors apply the validity rule, too few samples included: a round that kept 1 of
        a row's 6 samples (min_samples 18 over a session's three rounds) never sets its recorded A, spread or floor."""
        table = {'controls': [], 'rows': [{'id': 'x', 'metric': 'm', 'min_samples': 18, 'gate': [{'rel_max': 1.02}]}]}
        six = [300, 298, 305, 301, 299, 303]
        derived = JUDGE.derive(table, {'metrics': {'m': six}}, {'metrics': {'m': six}}, 't')
        self.assertIn('x', derived['derived']['rows'])
        for short in ([304], six[:5], six[:5] + [None]):
            with self.subTest(short=short), self.assertRaisesRegex(ValueError, 'too few samples'):
                JUDGE.derive(table, {'metrics': {'m': six}}, {'metrics': {'m': short}}, 't')
        table['rows'][0]['needs_a'] = False  # a row that does not read A is not counted
        derived = JUDGE.derive(table, {'metrics': {'m': six}}, {'metrics': {'m': [1]}}, 't')
        self.assertNotIn('x', derived['derived']['rows'])

    def test_derive_is_reproducible_byte_for_byte(self):
        """protocol[2]: the same table and pair give the same bytes, whether the table was derived before or not, and
        every earlier value is replaced, never kept."""
        first = {'metrics': {'m': [100, 102], 'k': [7]}}
        second = {'metrics': {'m': [104, 106], 'k': [7]}}
        table = {'controls': [], 'rows': [{'id': 'x', 'metric': 'm', 'gate': [{'rel_max': 1.02}]},
                                          {'id': 'k', 'metric': 'k', 'gate': [{'abs_max': 9}]}]}
        once = JUDGE.derive(table, first, second, 'pair 1')
        again = JUDGE.derive(once, first, second, 'pair 1')
        self.assertEqual(json.dumps(once, indent=1), json.dumps(again, indent=1))
        moved = JUDGE.derive(once, {'metrics': {'m': [100, 102], 'k': [7]}}, {'metrics': {'m': [140, 140], 'k': [9]}},
                             'pair 2')
        self.assertNotEqual(moved['rows'][0]['gate'][0]['floor_factor'], once['rows'][0]['gate'][0]['floor_factor'])
        self.assertEqual(moved['derived']['rows']['k'], [7, 9, 8.0])
        self.assertEqual(moved['derived']['sha256'], JUDGE.derived_digest(moved['derived']['rows']))
        stopped = json.loads(json.dumps(once))
        stopped['rows'][1]['needs_a'] = False  # a row that stops reading A loses its old derived values
        again = JUDGE.derive(stopped, first, second, 'pair 1')
        self.assertFalse([k for k in ('a_recorded', 'a_spread', 'spread') if k in again['rows'][1]])
        self.assertNotIn('k', again['derived']['rows'])
        base = JUDGE.base_table(once)
        self.assertIsNone(base['derived'])
        self.assertFalse([r for r in base['rows'] for k in ('a_recorded', 'a_spread', 'spread') if k in r])

    def test_section_eight_s_a_column_tolerance(self):
        self.assertTrue(JUDGE.a_column_close(310, 298))
        self.assertFalse(JUDGE.a_column_close(400, 298))
        self.assertTrue(JUDGE.a_column_close(200, [194, 199]))
        self.assertTrue(JUDGE.a_column_close(196, [194, 199]))
        self.assertFalse(JUDGE.a_column_close(120, [194, 199]))
        self.assertTrue(JUDGE.a_column_close(5, None))

    def test_a_is_checked_against_lane_m_s_recorded_a_where_there_is_one(self):
        """Section 8's figure for the list at 100 documents is 39.2 ms; release 1 measured on this bench in the A/A
        protocol gives about 25. With the recorded A in the row, A at 25 is A, and A at 39 is not."""
        table = copy.deepcopy(TABLE)
        table['rows'][0].update({'a_section8': 39.2, 'a_recorded': 25.0, 'gate': [{'abs_max': 30}], 'gain': False})
        quiet = self.answer(self.pair([25.0, 24.6, 25.4], [20.0, 20.5, 19.5]), table=table)
        self.assertEqual(quiet['verdict'], 'PASS', quiet)
        loud = self.answer(self.pair([39.0, 39.4, 38.8], [20.0, 20.5, 19.5]), table=table)
        self.assertEqual(loud['verdict'], 'INVALID')
        self.assertTrue(any("lane M's recorded A 25.0" in ' '.join(r['why']) for r in loud['rows']), loud)
        table['rows'][0].pop('a_recorded')  # without a recorded A, section 8's figure is the A column, as before
        self.assertEqual(self.answer(self.pair([25.0, 24.6, 25.4], [20.0, 20.5, 19.5]), table=table)['verdict'],
                         'INVALID')

    def test_a_noisy_metric_s_a_column_tolerance_is_twice_its_own_spread(self):
        """The longest GC pause is one sample a round (A/A 135 and 205 ms, a 41% spread): A at 140 against a recorded
        205 is within twice that spread, and outside a plain 20%."""
        table = copy.deepcopy(TABLE)
        table['rows'][0].update({'a_section8': [194, 199], 'a_recorded': 205.3, 'a_spread': 0.41, 'stat': 'max',
                                 'min_samples': 1, 'gate': [{'abs_max': 5}], 'gain': False})
        self.assertAlmostEqual(JUDGE.a_tolerance(table['rows'][0]), 0.82)
        noisy = self.answer(self.pair([140.0], [3.0]), table=table)
        self.assertEqual(noisy['verdict'], 'PASS', noisy)
        table['rows'][0]['a_spread'] = 0.05
        self.assertEqual(JUDGE.a_tolerance(table['rows'][0]), 0.20)
        self.assertEqual(self.answer(self.pair([140.0], [3.0]), table=table)['verdict'], 'INVALID')


class OfficeModelTests(unittest.TestCase):
    def test_limit_req_is_nginx_s(self):
        self.assertEqual(JUDGE.limit_req([0] * 6, 5 / 1000, 5), 0)  # the first makes the node, five fit the burst
        self.assertEqual(JUDGE.limit_req([0] * 7, 5 / 1000, 5), 1)
        self.assertEqual(JUDGE.limit_req([0] * 6 + [200], 5 / 1000, 5), 0)  # 200 ms drained one
        self.assertEqual(JUDGE.limit_req([i * 100 for i in range(100)], 30 / 1000, 0), 0)  # under the rate
        # every 10 ms at 30 r/s with no burst: one is let through each time 1/30 s has drained, at 0, 40, 80 ... 960 ms
        self.assertEqual(JUDGE.limit_req([i * 10 for i in range(100)], 30 / 1000, 0), 75)

    def test_requests_fall_in_the_vhost_s_zones(self):
        zones = RUN.vhost_zones(APP)
        maps = zones['maps']
        self.assertIn('cpt_signin_key', JUDGE.zone_of(maps, 'POST', '/login/'))
        self.assertIn('cpt_upload_key', JUDGE.zone_of(maps, 'POST', '/api/encounters'))
        self.assertIn('cpt_export_key', JUDGE.zone_of(maps, 'POST', '/api/encounters/<id>/reports'))
        # every request counts in cpt_all; a view also in the bytes zone (a limit_conn zone); no POST zone takes a GET
        self.assertEqual(sorted(JUDGE.zone_of(maps, 'GET', '/api/encounters/<id>/original?view=1')),
                         ['cpt_all_key', 'cpt_bytes_key'])
        self.assertEqual(JUDGE.zone_of(maps, 'GET', '/api/encounters'), ['cpt_all_key'])
        self.assertEqual(set(zones['zones']), {'cpt_all', 'cpt_signin', 'cpt_write', 'cpt_upload', 'cpt_export'})
        self.assertEqual(zones['zones']['cpt_all']['burst'], 120)

    def test_the_office_model_counts_429s_from_measured_requests(self):
        zones = RUN.vhost_zones(APP)
        model = {'members': 20, 'typists': 5, 'signin_window_ms': 2000, 'cold_caches': 5, 'minutes': 1,
                 'open_every_ms': 15000, 'read_ms': 10000, 'typing_at_ms': 4000}
        measured = {'signin': [('POST', '/login/'), ('GET', '/'), ('GET', '/static/studio/app.js'),
                               ('POST', '/session/activity'), ('GET', '/api/encounters')],
                    'open': [('GET', '/api/encounters/<id>'), ('GET', '/api/encounters/<id>/original?view=1')],
                    'list': [('GET', '/api/encounters')], 'typing': []}
        calm = JUDGE.office_429s(zones, JUDGE.office_requests(model, measured))
        self.assertEqual(sum(calm.values()), 0, calm)
        typing = [(350 * i, 'POST', '/api/encounters/search') for i in range(30)]
        write = '"~^0:POST /(api|ops)/" $cpt_client;\n    default "";\n'
        release1 = {**zones, 'maps': {**zones['maps'], 'cpt_write_key': write}}
        busy = JUDGE.office_429s(release1, JUDGE.office_requests(model, {**measured, 'typing': typing}))
        self.assertGreater(busy['cpt_write'], 0, busy)  # in the write zone, 5 typists at 2.9 a second each pass it
        exact = '"0:POST /api/encounters/search" "";\n    ' + write
        r2_27 = {**zones, 'maps': {**zones['maps'], 'cpt_write_key': exact}}
        calm = JUDGE.office_429s(r2_27, JUDGE.office_requests(model, {**measured, 'typing': typing}))
        self.assertEqual(sum(calm.values()), 0, calm)  # R2-27: a search counts in the read zone only

    def test_an_exact_empty_entry_wins_over_every_expression(self):
        """judge[6]: nginx picks a map's exact string first, then its expressions in order, then the default, and an
        empty key counts in no zone; the search was counted in the write zone despite R2-27's exact empty entry."""
        write = '"~^0:POST /(api|ops)/" $cpt_client;\n    default "";\n'
        maps = {'cpt_all_key': '"~^0:" $cpt_client;\n    default "";\n',
                'cpt_write_key': '"0:POST /api/encounters/search" "";  # R2-27\n    ' + write}
        self.assertEqual(JUDGE.zone_of(maps, 'POST', '/api/encounters/search'), ['cpt_all_key'])
        self.assertEqual(JUDGE.zone_of(maps, 'GET', '/api/encounters'), ['cpt_all_key'])
        for path in ('/api/encounters/<id>/answers', '/api/encounters/search/', '/ops/encounters/<id>/note'):
            self.assertIn('cpt_write_key', JUDGE.zone_of(maps, 'POST', path), path)
        mutated = {**maps, 'cpt_write_key': maps['cpt_write_key'].replace('search" ""', 'search" $cpt_client')}
        self.assertIn('cpt_write_key', JUDGE.zone_of(mutated, 'POST', '/api/encounters/search'))


DOC_A, DOC_B = '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222'


def _entry(rid, method, url, status=200, poll=False, at=3000.0, t0=None):
    """One proxy entry; a proxy entry always carries t0 and tEnd (records[0] and records[5], round 2)."""
    headers = {'x-request-id': rid, **({'x-cpt-poll': '1'} if poll else {})}
    start = at if t0 is None else t0
    return {'method': method, 'url': url, 'status': status, 'reqHeaders': headers, 't0': start, 'tEnd': start + 20}


def _row(rid, view, ids=(), at=1000.0, sign_in='s1', outcome='served', filters=None):
    if filters is None:  # R2-21: a list row names its list and cursor
        filters = {'list': 'documents', 'before': None} if view == 'member.list' else {}
    return {'request_id': rid, 'view': view, 'encounter_ids': list(ids), 'count': len(ids), 'created_at': at,
            'sign_in_ref': sign_in, 'outcome': outcome, 'filters': filters}


DOCS = {'text-2p': {'id': DOC_A, 'number': 101}}


class RecordsJudgementTests(unittest.TestCase):
    """The records part's exact gates (R2-32 M4), over synthetic proxy logs and access rows."""

    def flow(self):
        entries = [_entry('l1', 'GET', '/api/encounters'), _entry('l2', 'GET', '/api/encounters'),
                   _entry('d1', 'GET', f'/api/encounters/{DOC_A}'),
                   _entry('v1', 'GET', f'/api/encounters/{DOC_A}/original?view=1'),
                   _entry('p1', 'GET', f'/api/encounters/{DOC_A}', poll=True),
                   _entry('s1', 'GET', '/static/studio/app.js'), _entry('x1', 'POST', '/session/activity')]
        rows = [_row('l1', 'member.list', [DOC_A, DOC_B]), _row('d1', 'member.detail', [DOC_A], at=2000),
                _row('v1', 'member.inline', [DOC_A], at=2100)]
        actions = [{'kind': 'records-open', 'label': 'text-2p', 'number': 101, 'mode': 'pdf', 'canvasEpoch': 2300,
                    'firstPage': 300, 'barcode': {'number': 101},
                    'rids': [['GET', '/api/encounters/<id>', 200, 'd1', 1],
                             ['GET', '/api/encounters/<id>/original?view=1', 200, 'v1', 5]]}]
        lists = [{'rid': 'l1', 'path': '/api/encounters', 'ids': [DOC_A, DOC_B]},
                 {'rid': 'l2', 'path': '/api/encounters', 'ids': [DOC_A, DOC_B]}]
        return entries, rows, actions, lists

    def test_every_served_read_is_one_row_or_a_counted_repeat(self):
        entries, rows, actions, lists = self.flow()
        got = RUN.judge_records(entries, rows, 1, actions, lists, docs=DOCS)
        for name in ('equation', 'polls', 'openings', 'inline_before_pixels', 'list_ids'):
            self.assertTrue(got[name]['ok'], (name, got[name]))

    def test_each_bad_shape_fails_its_gate(self):
        entries, rows, actions, lists = self.flow()
        self.assertFalse(RUN.judge_records(entries, rows, 0, actions, lists)['equation']['ok'])  # a repeat uncounted
        no_detail = [r for r in rows if r['request_id'] != 'd1']
        got = RUN.judge_records(entries, no_detail, 1, actions, lists)
        self.assertFalse(got['equation']['ok'])
        self.assertFalse(got['openings']['ok'])
        orphan = rows + [_row('zz', 'member.inline', [DOC_B])]
        self.assertFalse(RUN.judge_records(entries, orphan, 1, actions, lists)['equation']['ok'])
        twice = rows + [_row('v1', 'member.inline', [DOC_A], at=2150)]
        self.assertFalse(RUN.judge_records(entries, twice, 1, actions, lists)['openings']['ok'])
        late = [dict(r, created_at=2400) if r['request_id'] == 'v1' else r for r in rows]
        self.assertFalse(RUN.judge_records(entries, late, 1, actions, lists)['inline_before_pixels']['ok'])
        unnamed = [dict(r, encounter_ids=[], count=2) if r['view'] == 'member.list' else r for r in rows]
        self.assertFalse(RUN.judge_records(entries, unnamed, 1, actions, lists)['list_ids']['ok'])
        # one answer, its own row naming other ids, nothing counted as a repeat: only the row-to-answer comparison
        # sees it
        wrong = [dict(r, encounter_ids=[DOC_B, DOC_A]) if r['view'] == 'member.list' else r for r in rows]
        alone = [e for e in entries if e['reqHeaders']['x-request-id'] != 'l2']
        got = RUN.judge_records(alone, wrong, 0, actions, lists[:1])
        self.assertTrue(got['equation']['ok'], got['equation'])
        self.assertFalse(got['list_ids']['ok'])
        self.assertEqual(got['list_ids']['mismatches'], [{'path': '/api/encounters', 'served': 2, 'named': 2}])
        self.assertFalse(RUN.judge_records(entries, rows, 1, actions, [])['list_ids']['ok'])  # nothing seen: no pass
        crowded = entries + [_entry('p2', 'GET', f'/api/encounters/{DOC_A}', poll=True)]
        polled = rows + [_row('p1', 'member.detail', [DOC_A], at=5000), _row('p2', 'member.detail', [DOC_A], at=9000)]
        self.assertFalse(RUN.judge_records(crowded, polled, 1, actions, lists)['polls']['ok'])
        spaced = rows + [_row('p1', 'member.detail', [DOC_A], at=62000), _row('p2', 'member.detail', [DOC_A],
                                                                           at=125000)]
        self.assertTrue(RUN.judge_records(crowded, spaced, 1, actions, lists)['polls']['ok'])

    def test_a_poll_row_within_a_minute_of_the_open_s_own_row_fails(self):
        """records[7]: polls were grouped among themselves only, so a poll writing a row 3 s after the open passed."""
        entries, rows, actions, lists = self.flow()
        crowded = entries + [_entry('p2', 'GET', f'/api/encounters/{DOC_A}', poll=True)]
        after_open = rows + [_row('p1', 'member.detail', [DOC_A], at=5000)]
        got = RUN.judge_records(crowded, after_open, 1, actions, lists, docs=DOCS)
        self.assertFalse(got['polls']['ok'], got['polls'])
        day = 86400000
        midnight = [dict(r, created_at=r['created_at'] + day - 7000) for r in rows]  # the open at 23:59:55 (UTC)
        new_day = midnight + [_row('p1', 'member.detail', [DOC_A], at=day + 6210)]  # its poll at 00:00:06.21
        self.assertTrue(RUN.judge_records(crowded, new_day, 1, actions, lists, docs=DOCS)['polls']['ok'])  # by design
        refused = rows + [_row('p1', 'member.detail', [DOC_A], at=5000, outcome='refused')]
        self.assertTrue(RUN.judge_records(crowded, refused, 1, actions, lists, docs=DOCS)['polls']['ok'])

    def test_a_poll_release_1_records_needs_its_row(self):
        """records-0 (round 2): every poll was taken out of the equation, so a poll release 1 records passed with no
        row, and the flow's only polls fell inside the open's minute."""
        entries, rows, actions, lists = self.flow()
        late = entries + [_entry('p2', 'GET', f'/api/encounters/{DOC_A}', poll=True, at=62100)]
        self.assertFalse(RUN.judge_records(late, rows, 1, actions, lists, docs=DOCS)['equation']['ok'])
        written = rows + [_row('p2', 'member.detail', [DOC_A], at=62110)]
        self.assertTrue(RUN.judge_records(late, written, 1, actions, lists, docs=DOCS)['equation']['ok'])
        first = entries + [_entry('p3', 'GET', f'/api/encounters/{DOC_B}', poll=True, at=4000)]  # never read: one row
        self.assertFalse(RUN.judge_records(first, rows, 1, actions, lists, docs=DOCS)['equation']['ok'])
        edge = entries + [_entry('p4', 'GET', f'/api/encounters/{DOC_A}', poll=True, at=61990)]  # spans d1 + 60 s
        for extra in ([], [_row('p4', 'member.detail', [DOC_A], at=62001)]):
            self.assertTrue(RUN.judge_records(edge, rows + extra, 1, actions, lists, docs=DOCS)['equation']['ok'])
        wrong = rows + [_row('p2', 'member.detail', [DOC_B], at=62110)]
        self.assertFalse(RUN.judge_records(late, wrong, 1, actions, lists, docs=DOCS)['polls']['ok'])
        untimed = [dict(e, t0=None) if e['reqHeaders']['x-request-id'] == 'p1' else e for e in entries]
        self.assertFalse(RUN.judge_records(untimed, rows, 1, actions, lists, docs=DOCS)['equation']['ok'])

    def test_an_opening_names_and_draws_the_document_opened(self):
        """records[5]: openings counted rows by request id only, so rows naming another document passed."""
        entries, rows, actions, lists = self.flow()
        self.assertTrue(RUN.judge_records(entries, rows, 1, actions, lists, docs=DOCS)['openings']['ok'])
        for change in ([DOC_B], []):
            wrong = [dict(r, encounter_ids=change) if r['request_id'] == 'v1' else r for r in rows]
            got = RUN.judge_records(entries, wrong, 1, actions, lists, docs=DOCS)
            self.assertFalse(got['openings']['ok'], change)
            self.assertTrue(got['equation']['ok'], change)
        drawn = [dict(actions[0], barcode={'number': 102})]
        got = RUN.judge_records(entries, rows, 1, drawn, lists, docs=DOCS)
        self.assertFalse(got['openings']['ok'])
        self.assertFalse(got['openings']['opens'][0]['drawn'])
        self.assertFalse(RUN.judge_records(entries, rows, 1, actions, lists)['openings']['ok'])  # no documents named

    def test_a_list_row_names_its_list_and_cursor(self):
        """records[6]: list_ids compared ids and count only, so rows naming another list or cursor passed."""
        entries, rows, actions, lists = self.flow()
        alone = [e for e in entries if e['reqHeaders']['x-request-id'] != 'l2']
        good = RUN.judge_records(alone, rows, 0, actions, lists[:1], docs=DOCS)
        self.assertTrue(good['list_ids']['ok'], good['list_ids'])
        for filters in ({}, {'list': 'queue', 'before': None}, {'list': 'documents', 'before': 'x'}):
            wrong = [dict(r, filters=filters) if r['view'] == 'member.list' else r for r in rows]
            got = RUN.judge_records(alone, wrong, 0, actions, lists[:1], docs=DOCS)
            self.assertTrue(got['equation']['ok'], filters)
            self.assertFalse(got['list_ids']['ok'], filters)
        later = [_entry('l3', 'GET', '/api/encounters?list=documents&before=2026-11-02T10:00:00Z~x')]
        row = [_row('l3', 'member.list', [DOC_A], filters={'list': 'documents', 'before': '2026-11-02T10:00:00Z~x'})]
        answer = [{'rid': 'l3', 'path': '/api/encounters?list=documents&before=<cursor>', 'ids': [DOC_A]}]
        self.assertTrue(RUN.judge_records(later, row, 0, [], answer, docs=DOCS)['list_ids']['ok'])
        search = [_entry('s9', 'POST', '/api/encounters/search')]
        found = [_row('s9', 'member.list', [DOC_A], filters={'list': 'search', 'before': None})]
        asked = [{'rid': 's9', 'path': '/api/encounters/search', 'ids': [DOC_A], 'before': None}]
        self.assertTrue(RUN.judge_records(search, found, 0, [], asked, docs=DOCS)['list_ids']['ok'])

    def test_a_repeat_names_the_list_cursor_and_time_of_its_row(self):
        """R2-21: an answer with no row passed as a repeat of any list row with its ids, whatever its list or cursor."""
        entries, rows, actions, lists = self.flow()
        self.assertTrue(RUN.judge_records(entries, rows, 1, actions, lists, docs=DOCS)['list_ids']['ok'])
        for url, t0 in (('/api/encounters?list=queue', 1500.0), ('/api/encounters?list=documents&before=x', 1500.0),
                        ('/api/encounters?list=documents', 61500.0)):
            moved = [e if e['reqHeaders']['x-request-id'] != 'l2' else _entry('l2', 'GET', url, t0=t0)
                     for e in entries]
            got = RUN.judge_records(moved, rows, 1, actions, lists, docs=DOCS)
            self.assertTrue(got['equation']['ok'], url)
            self.assertFalse(got['list_ids']['ok'], (url, t0))
        changed = lists[:1] + [dict(lists[1], ids=[DOC_B, DOC_A])]
        self.assertEqual(RUN.judge_records(entries, rows, 1, actions, changed, docs=DOCS)['list_ids']['changed'], 1)
        got = RUN.records_n100_rule(RUN.judge_records(entries, rows, 1, actions, lists, docs=DOCS))
        self.assertFalse(got['list_ids']['ok'])  # no list read again after it changed: no pass at 100


    def test_the_download_kind_is_exercised_at_the_practice_of_100(self):
        """records[8]: no records flow downloaded, so a download served with no record passed the equation."""
        entries, rows, actions, lists = self.flow()
        opens = actions * 4
        judged = RUN.judge_records(entries, rows, 1, opens, lists, docs=DOCS)
        judged['openings'] = {'ok': True, 'opens': [{}] * 4}
        self.assertFalse(RUN.records_n100_rule(json.loads(json.dumps(judged)))['equation']['ok'])
        downloaded = entries + [_entry('w1', 'GET', f'/api/encounters/{DOC_A}/original')]
        with_rows = rows + [_row('w1', 'member.download', [DOC_A], at=2500)]
        judged = RUN.judge_records(downloaded, with_rows, 1, opens, lists, docs=DOCS)
        judged['openings'] = {'ok': True, 'opens': [{}] * 4}
        self.assertTrue(RUN.records_n100_rule(judged)['equation']['ok'])

    def test_a_failed_library_may_write_a_second_inline_row(self):
        entries, rows, actions, lists = self.flow()
        actions[0]['mode'] = 'frame'
        entries.append(_entry('v2', 'GET', f'/api/encounters/{DOC_A}/original?view=1'))
        actions[0]['rids'].append(['GET', '/api/encounters/<id>/original?view=1', 200, 'v2', 5])
        rows.append(_row('v2', 'member.inline', [DOC_A], at=2200))
        self.assertTrue(RUN.judge_records(entries, rows, 1, actions, lists, docs=DOCS)['openings']['ok'])

    def test_requests_map_to_the_views_they_record(self):
        self.assertEqual(RUN.read_kind('GET', '/api/encounters?list=documents&before=x'), 'member.list')
        self.assertEqual(RUN.read_kind('POST', '/api/encounters/search'), 'member.list')
        self.assertEqual(RUN.read_kind('GET', f'/api/encounters/{DOC_A}'), 'member.detail')
        self.assertEqual(RUN.read_kind('GET', f'/api/encounters/{DOC_A}/original?view=1'), 'member.inline')
        self.assertEqual(RUN.read_kind('GET', f'/api/encounters/{DOC_A}/original'), 'member.download')
        for method, url in (('POST', '/api/encounters'), ('GET', '/api/session'), ('GET', '/static/studio/app.js'),
                            ('GET', '/api/encounters/search'), ('POST', f'/api/encounters/{DOC_A}/decisions')):
            self.assertIsNone(RUN.read_kind(method, url), url)


NO_STORE = {'content-type': 'application/json', 'cache-control': 'no-store'}


class _FakeWeb:
    def __init__(self, env, label, *extra, **kw):
        self.port, self.label, self.base = 9301, label, 'http://127.0.0.1:9301'

    def stop(self):
        pass

    def lines(self):
        return []

    def pids(self):
        return [1]


class _FakeProxy:
    entries_for = {}  # label -> the proxy's log of that flow

    def __init__(self, env, upstream, label, host_header=''):
        self.base, self.control, self.label = 'http://127.0.0.1:9302', 9303, label

    def entries(self, since=0):
        return list(_FakeProxy.entries_for.get(self.label, []))

    def stop(self):
        pass


def _flows_bench(raw: Path, outputs: dict):
    """A Bench with no database and no browser: its servers and bench.cjs are fakes, so a part's own code runs on the
    proxy log and the flow outputs given (by label)."""
    bench = object.__new__(RUN.Bench)
    bench.raw, bench.env, bench.acts_port, bench.contexts = raw, None, 9304, 3
    bench.docs_file, bench.password_file = raw / 'docs.json', raw / 'password'
    bench.docs_by_label, bench.warm = {}, (lambda web, **kw: None)
    bench.result = {'metrics': {}, 'checks': {}, 'controls': {}, 'errors': [], 'unexpected_statuses': {},
                    'console_errors': [], 'blocked_requests': []}

    def run(cmd, **kw):
        out = Path(cmd[cmd.index('--out') + 1])
        label = out.name[len('browser-'):-len('.json')]
        out.write_text(json.dumps({'metrics': {}, 'checks': {}, 'controls': {}, 'actions': [], 'lists': [],
                                   'errors': [], 'blocked': [], 'consoleErrors': [], 'pageErrors': [],
                                   **outputs.get(label, {})}))
        return subprocess.CompletedProcess(cmd, 0, '', '')
    patches = [unittest.mock.patch.object(RUN, 'Web', _FakeWeb), unittest.mock.patch.object(RUN, 'Proxy', _FakeProxy),
               unittest.mock.patch.object(RUN.subprocess, 'run', run), unittest.mock.patch.object(RUN.bd, 'RICH', [])]
    return bench, patches


class BenchGateFlowStatusTests(unittest.TestCase):
    def statuses(self, status):
        _FakeProxy.entries_for = {label: [
            {'method': 'GET', 'url': '/api/encounters', 'status': 200, 'resHeaders': NO_STORE, 'reqHeaders': {}},
            {'method': 'GET', 'url': f'/api/encounters/{DOC_A}', 'status': status,
             'resHeaders': {'content-type': 'text/html'}, 'reqHeaders': {}}] for label in ('left-behind', 'correct')}
        with tempfile.TemporaryDirectory() as d:
            bench, patches = _flows_bench(Path(d), {})
            with contextlib.ExitStack() as stack:
                for patch in patches:
                    stack.enter_context(patch)
                bench.part_left_behind()
                bench.part_correct()
        return bench.result['unexpected_statuses']

    def test_a_500_in_the_left_behind_or_correctness_flows_reaches_the_judge(self):
        """judge[8]: both flows allowed every status from 100 to 599, so a 500 after an access end was never seen."""
        for status in (401, 404, 499):
            self.assertEqual(self.statuses(status), {}, status)  # the flows' own ends
        got = self.statuses(500)
        self.assertEqual(got, {'left-behind:500': 1, 'correct:500': 1})
        self.assertNotIn(403, RUN.GATE_STATUS_OK)  # release 1 answers another practice's document as missing (404)


class _NoRows(list):
    def count(self):
        return len(self)

    def order_by(self, *a):
        return self

    def values(self, *a):
        return self

    def values_list(self, *a, **kw):
        return _NoRows()

    def filter(self, **kw):
        return _NoRows()


class BenchRecordsPartTests(unittest.TestCase):
    def records_round(self, hover_fails_at=(), marker_page=None):
        flows = {}
        for size in ('n100', 'n1500'):
            flows[f'records-{size}'] = {'checks': {'records.hover': {'ok': size not in hover_fails_at}},
                                        'markerPage': [] if marker_page is None else marker_page}
        flows['fail-closed'] = {'checks': {'records.fail_closed': {'ok': True}}}
        _FakeProxy.entries_for = {}
        manager = type('Manager', (), {'objects': _NoRows()})
        models = type(sys)('studio.models')
        models.AccessRecord = models.AccessRecordRepeat = models.SecurityEvent = manager
        studio = type(sys)('studio')
        studio.models = models
        with tempfile.TemporaryDirectory() as d:
            bench, patches = _flows_bench(Path(d), flows)
            with contextlib.ExitStack() as stack:
                for patch in patches + [unittest.mock.patch.dict(sys.modules, {'studio': studio,
                                                                                'studio.models': models})]:
                    stack.enter_context(patch)
                bench.part_records()
        return bench.result['checks']

    def test_a_hover_read_in_either_practice_fails_the_round(self):
        """records[2]: browser() kept the n1500 flow's records.hover over the n100 one, so a hover read at 100
        passed."""
        self.assertTrue(self.records_round()['records.hover']['ok'])
        for size in ('n100', 'n1500'):
            self.assertFalse(self.records_round(hover_fails_at=(size,))['records.hover']['ok'], size)

    def test_the_marker_scan_reads_the_page(self):
        """records[4]: the marker scan read only the server's artifacts, so search words in the page's URL, storage or a
        cookie passed; a flow that never read its page fails too."""
        self.assertTrue(self.records_round()['records.marker']['ok'])
        got = self.records_round(marker_page=['location', 'sessionStorage:cpt-last-search'])['records.marker']
        self.assertFalse(got['ok'])
        self.assertEqual(got['found']['page-n100'], ['location', 'sessionStorage:cpt-last-search'])
        self.assertEqual(RUN.marker_in_pages({'n100': None, 'n1500': []}), {'page-n100': 'never read'})


class BenchServerPartTests(unittest.TestCase):
    def test_the_typical_search_fills_its_first_page(self):
        """bench[2]: '0042' matched 12 of 18,000 titles, so the 'typical' search walked the whole practice."""
        self.assertTrue(all(RUN.TYPICAL_WORD in BD.TITLE.format(i=i) for i in range(17999, 17948, -1)))
        self.assertTrue(all(RUN.TYPICAL_WORD in BD.TITLE.format(i=i) for i in range(0, 18000, 997)))
        self.assertFalse(RUN.MARKER_WORD in BD.TITLE.format(i=0))
        source = (BENCH / 'bench_run.py').read_text()
        self.assertNotIn("'0042'", source)  # the server part and the plans part search the typical word
        self.assertEqual(source.count("{'text': TYPICAL_WORD,"), 3)

    def test_a_request_row_is_every_byte_but_the_effort(self):
        """bench[3]: the row hashes the exact parameters with output_config.effort taken out, and carries the effort."""
        canonical = lambda v: json.dumps(v, sort_keys=True, separators=(',', ':')).encode()  # noqa: E731
        params = {'model': 'm', 'system': 's', 'messages': [{'role': 'user', 'content': 'x'}],
                  'output_config': {'effort': 'max'}}
        a = RUN.request_row('text', 'reader', params, 2, canonical)
        b = RUN.request_row('text', 'reader', {**params, 'output_config': {'effort': 'high'}}, 2, canonical)
        self.assertEqual((a['effort'], b['effort']), ('max', 'high'))
        self.assertEqual(a['params_sha256'], b['params_sha256'])
        c = RUN.request_row('text', 'reader', {**params, 'system': 't'}, 2, canonical)
        self.assertNotEqual(a['params_sha256'], c['params_sha256'])  # one prompt byte
        self.assertEqual(params['output_config'], {'effort': 'max'})  # the request itself is never changed
        self.assertIn("self.result['requests_effort'] = settings.CODING_EFFORT", (BENCH / 'bench_run.py').read_text())


class BenchTreeReadingTests(unittest.TestCase):
    def test_release_two_s_index_names_come_from_its_own_migrations(self):
        with tempfile.TemporaryDirectory() as d:
            migrations = Path(d, 'studio', 'migrations')
            migrations.mkdir(parents=True)
            Path(migrations, '0018_r1_availability.py').write_text("models.Index(name='studio_old_one')")
            Path(migrations, '0019_r2_document_lists.py').write_text(
                "AddIndex(index=models.Index(fields=['a'], name='studio_enc_ws_time'))\n"
                "AddIndex(index=models.Index(fields=['b'], name=\"studio_enc_ws_queue\"))")
            Path(migrations, '0020_r2_run_lookups.py').write_text("models.Index(F('x'), name='studio_run_round')")
            self.assertEqual(RUN.release2_index_names(Path(d)),
                             ['studio_enc_ws_queue', 'studio_enc_ws_time', 'studio_run_round'])
        self.assertEqual(RUN.release2_index_names(APP), sorted(RUN.release2_index_names(APP)))

    def test_the_other_tree_s_client_header_is_read_from_its_own_file(self):
        header, version = RUN.read_client(APP)
        self.assertEqual(header, 'X-CPT-Studio-Client')
        self.assertTrue(version.startswith('customer-'))

    def test_profile_p3_gets_two_distinct_cpus(self):
        cores = RUN.idlest_cores(2, seconds=0.2).split(',')
        self.assertEqual(len(set(cores)), 2)
        self.assertTrue(all(c.isdigit() for c in cores))


DERIVED_SHA256 = None  # the committed table's derived rows: set by the commit that derives a new A/A (D-R2-44)


def _derived_problems(table: dict, pin) -> list:
    """Why ``table`` is neither its base (no A-derived value anywhere, and no pin) nor exactly its own derivation (every
    value recomputed from the inputs judge.py floors recorded, the inputs hashing to their sha256, that sha256 the
    pinned one, every row that reads A among them)."""
    derived = table.get('derived')
    values = [(r['id'], k) for r in table['rows'] for k in JUDGE.DERIVED_ROW_KEYS if k in r]
    values += [(r['id'], k) for r in table['rows'] for g in r.get('gate', []) for k in JUDGE.DERIVED_GATE_KEYS
               if k in g]
    if derived is None:
        return ([f'a base table carries A-derived values: {values[:5]}'] if values else []) + \
            ([f'a base table with a pinned derivation {pin}'] if pin is not None else [])
    problems = []
    if derived.get('sha256') != JUDGE.derived_digest(derived.get('rows') or {}):
        problems.append('the recorded inputs do not hash to the sha256 the table names')
    if derived.get('sha256') != pin:
        problems.append(f'the derived inputs {str(derived.get("sha256"))[:16]} are not the pinned {str(pin)[:16]}')
    again = JUDGE.base_table(table)
    for row in again['rows']:
        if row['id'] in derived.get('rows', {}):
            JUDGE.derive_row(row, *derived['rows'][row['id']])
    again['derived'] = derived
    if again != table:
        problems.append('a derived value is not the one its recorded inputs give')
    if sorted(derived.get('rows', {})) != sorted(r['id'] for r in table['rows'] if JUDGE.reads_a(r)):
        problems.append('the recorded inputs are not exactly the rows that read A')
    return problems


class AcceptanceTableTests(unittest.TestCase):
    """acceptance.json is section 8's table: every row whole, named once, and judged on something the bench measures."""

    def setUp(self):
        self.table = json.loads((BENCH / 'acceptance.json').read_text())

    def test_every_row_is_whole_and_named_once(self):
        ids = [row['id'] for row in self.table['rows']]
        self.assertEqual(len(ids), len(set(ids)))
        for row in self.table['rows']:
            self.assertTrue(row.get('table') and row.get('section8'), row['id'])
            kind = row.get('kind', 'metric')
            self.assertIn(kind, {'metric', 'report', 'check', 'external', 'office', 'max_ratio', 'equal', 'ratio',
                                 'round_trips', 'same_as_a'}, row['id'])
            if kind == 'metric':
                self.assertTrue(row.get('metric') and row.get('gate'), row['id'])

    def test_every_check_and_metric_family_is_one_the_bench_produces(self):
        sources = ''.join((BENCH / name).read_text() for name in ('bench.cjs', 'bench_run.py'))
        for row in self.table['rows']:  # the whole name, quoted, as the bench records it: never a longer name
            if row.get('kind') == 'check':
                self.assertRegex(sources, '[\'"`]' + re.escape(row['check']) + '[\'"`]', row['id'])
        families = {row['metric'].split('.')[0] for row in self.table['rows'] if row.get('metric')}
        self.assertEqual(families - {'open', 'lists', 'server', 'queries', 'cold', 'pause', 'load', 'office', 'static'},
                         set())
        self.assertEqual(self.table['controls'], ['nomarker', 'planted_delay', 'planted_fetch', 'planted_detail',
                                                  'reduced_motion', 'heap_probe'])

    def test_every_check_the_bench_records_is_judged(self):
        """The reverse of the test above: a check the bench measures that no row reads is a gate nobody judges, as
        left.not_from_http_cache and requests.recorded were until lane M's review of its A/A."""
        sources = ''.join((BENCH / name).read_text() for name in ('bench.cjs', 'bench_run.py'))
        files = {'cjs', 'js', 'log', 'json', 'jsonl', 'py', 'txt'}  # walk.cjs and walk.log are file names, not checks
        named = re.findall(r'[\'"`]((?:records|correct|left|walk|bluegreen|plans|requests)\.[a-z0-9_]+)[\'"`]', sources)
        produced = {name for name in named if name.split('.')[1] not in files}
        judged = {row['check'] for row in self.table['rows'] if row.get('kind') == 'check'}
        self.assertGreaterEqual(len(produced), 30)  # a pattern that matched nothing would pass vacuously
        self.assertEqual(produced - judged, set())

    def test_the_table_is_its_base_or_exactly_its_derivation(self):
        """protocol[3]: a floor moved together with its spread copy, or a table built from an INVALID round, passed
        every test. The committed table is either the base (no A-derived value anywhere: D-R2-44, until the new A/A) or
        exactly its own derivation: each derived value recomputed from the per-row inputs judge.py floors recorded,
        those inputs hashing to the sha256 the table names, and that sha256 the one pinned here, which only the
        commit deriving a new A/A pair moves."""
        self.assertNotIn('spread', self.table)  # the old block of median spreads is gone
        self.assertEqual(_derived_problems(self.table, DERIVED_SHA256), [])

    def test_the_rows_that_do_not_read_a_are_judged_on_their_absolute_limit_alone(self):
        """judge[2]: the general gain rule made the six needs_a-false rows INVALID in every B session (floors write no
        spread on them). Derived from a pair that measured every metric row, each PASSes a B under its limit with A at
        release 1's aa4 values above it, and FAILs a B 5% over it, never INVALID."""
        metric_rows = [r for r in self.table['rows'] if r.get('kind', 'metric') == 'metric' and r.get('metric')]
        pair = [{'metrics': {r['metric']: [10 + n] * -(-r.get('min_samples', 1) // 3) for r in metric_rows}}
                for n in (0, 1)]
        rows = {r['id']: r for r in JUDGE.derive(self.table, pair[0], pair[1], 'guard pair')['rows']}
        a_values = {'documents-usable-18000-P1': 124901, 'documents-long-task-1500-P0': 454,
                    'documents-long-task-18000-P0': 6439, 'key-event-18000-P1': 7464, 'cold-closed-loop': 3213.1,
                    'worker-retained': 29.5}
        b_pass = {'documents-usable-18000-P1': 250, 'documents-long-task-1500-P0': 30,
                  'documents-long-task-18000-P0': 50, 'key-event-18000-P1': 104, 'cold-closed-loop': 110,
                  'worker-retained': 3}
        for rid, a in a_values.items():
            with self.subTest(row=rid):
                row = rows[rid]
                self.assertIs(row.get('needs_a'), False)
                need = row.get('min_samples', 1)
                a_rounds = {1: {'metrics': {row['metric']: [a] * need}}}
                ok = JUDGE.judge_row(row, a_rounds, {1: {'metrics': {row['metric']: [b_pass[rid]] * need}}})
                self.assertEqual(ok['verdict'], 'PASS', ok['why'])
                over = [g['abs_max'] for g in row['gate'] if 'abs_max' in g][0] * 1.05
                no = JUDGE.judge_row(row, a_rounds, {1: {'metrics': {row['metric']: [over] * need}}})
                self.assertEqual(no['verdict'], 'FAIL', no['why'])
        self.assertEqual([r['id'] for r in self.table['rows'] if r.get('needs_a') is False and r.get('gain')], [])

    def test_the_table_marks_every_row_whose_control_is_a(self):
        """judge[7]: walk.passes and every correct.* row are checked on A as the control (control_a); records.list_ids
        and plans.* are not (release 1 is expected to fail them)."""
        marked = {r['check'] for r in self.table['rows'] if r.get('control_a')}
        want = {r['check'] for r in self.table['rows'] if r.get('kind') == 'check' and
                (r['check'] == 'walk.passes' or r['check'].startswith('correct.'))}
        self.assertEqual(len(want), 8)
        self.assertEqual(marked, want)

    def test_a_derived_table_is_held_to_its_recorded_inputs(self):
        """protocol[3]: on a derived table the check recomputes every value from the recorded inputs and pins their
        sha256, so a floor moved with its spread copy, or inputs rewritten with their sha256, both fail."""
        reads = [r for r in self.table['rows'] if JUDGE.reads_a(r)]
        pair = [{'metrics': {r['metric']: [100 + 3 * n] * -(-r.get('min_samples', 1) // 3) for r in reads}}
                for n in (0, 1)]
        derived = JUDGE.derive(self.table, pair[0], pair[1], 'test pair')
        pin = derived['derived']['sha256']
        self.assertEqual(_derived_problems(derived, pin), [])
        moved = json.loads(json.dumps(derived))
        row = next(r for r in moved['rows'] if any(JUDGE.needs_floor(g) for g in r.get('gate', [])))
        gate = next(g for g in row['gate'] if JUDGE.needs_floor(g))
        gate['spread'], gate['floor_factor'] = 0.5, 2.0  # a floor moved together with its spread copy
        self.assertTrue(_derived_problems(moved, pin))
        rewritten = json.loads(json.dumps(derived))
        rewritten['derived']['rows'][row['id']] = [100, 150, 125]
        rewritten['derived']['sha256'] = JUDGE.derived_digest(rewritten['derived']['rows'])
        for r in rewritten['rows']:
            if r['id'] == row['id']:
                JUDGE.derive_row(r, 100, 150, 125)
        self.assertTrue(_derived_problems(rewritten, pin))  # consistent with itself, not with the pinned inputs

    def test_every_row_that_reads_a_gets_its_recorded_a_and_floors_when_derived(self):
        """protocol[1]: eight rows whose limit is A carried no recorded A; derive writes one on every row that reads
        A, its gain spread and every floor, from a pair that measured them, and no floor sits on a row that never reads
        A."""
        reads = [r for r in self.table['rows'] if JUDGE.reads_a(r)]
        self.assertGreater(len(reads), 90)
        pair = [{'metrics': {r['metric']: [10 + n] * -(-r.get('min_samples', 1) // 3) for r in reads}}
                for n in (0, 1)]
        derived = JUDGE.derive(self.table, pair[0], pair[1], 'test')
        for row in derived['rows']:
            floors = [g for g in row.get('gate', []) if JUDGE.needs_floor(g)]
            if floors:
                self.assertTrue(JUDGE.reads_a(row), row['id'])
            for gate in floors:
                self.assertEqual(gate.get('floor_factor'), JUDGE.floor_factor(JUDGE.up_spread(10, 11)), row['id'])
            if JUDGE.reads_a(row):
                self.assertEqual(row.get('a_recorded'), JUDGE.stat([10, 11], row.get('stat', 'median')), row['id'])
                self.assertEqual(row.get('spread'), JUDGE.up_spread(10, 11), row['id'])
                self.assertIsNotNone(JUDGE.a_reference(row)[0], row['id'])

    def test_the_memory_limits_are_in_the_metric_s_unit(self):
        """judge[5]: the heap limit was 40.2, in MB, against a metric in MiB; both memory rows are in MiB now."""
        source = (BENCH / 'bench.cjs').read_text()
        self.assertIn("metric('open.memory.heap_list_mb.P0', Math.round(used / 104857.6) / 10)", source)
        self.assertIn('privateMb: Math.round(priv / 102.4) / 10', source)  # the renderer's private kB / 1024: MiB
        rows = {r['id']: r for r in self.table['rows']}
        self.assertEqual(rows['memory-heap']['gate'], [{'abs_max': round((24 * 1048576 + 15_000_000) / 1048576, 1)}])
        kept = sum(len(BD.rich_files(spec)['view'] or BD.rich_files(spec)['data']) for spec in BD.RICH
                   if spec['label'] in ('text-2p', 'text-4p', 'text-10p', 'word-3p'))  # the memory flow's cycle
        self.assertEqual(kept, 43934)
        self.assertEqual(rows['memory-list']['gate'], [{'rel_max': 1.0,
                                                        'rel_plus': round((25_000_000 + kept) / 1048576, 2)}])

    def test_every_statement_row_names_a_practice_of_more_than_one_page(self):
        """judge[7], bench[1]: at 50 documents (the page size) there is no later page and no COUNT, so three rows could
        never pass; every statement row is at a practice the queries part seeds, above one page of 50."""
        seeded = {BD.SIZES[name] for name in RUN.NEEDS['queries']}
        found = 0
        for row in self.table['rows']:
            for metric in [row.get('metric')] + row.get('metrics', []):
                m = re.fullmatch(r'queries\.(list_first|list_later|search)\.(\d+)(\.builder)?', metric or '')
                if m:
                    found += 1
                    self.assertIn(int(m.group(2)), seeded, row['id'])
                    self.assertGreater(int(m.group(2)), 50, row['id'])
        self.assertGreaterEqual(found, 18)
        self.assertGreater(BD.SIZES['n51'], 50)  # R2-19: a page holds 50 rows; a later page and a COUNT only above
        self.assertIn("for name in ('n51', 'n5000'):", (BENCH / 'bench_run.py').read_text())

    def test_each_nav_tab_is_judged_on_its_own(self):
        """bench[0]: 89% of the pooled tab-change samples were returns to the list, so a Queue tab at 350 ms passed."""
        rows = {r['id']: r for r in self.table['rows']}
        for p, limit in zip(('P0', 'P1', 'P2'), (130, 280, 280)):
            for nav in ('queue', 'workspace', 'documents'):
                row = rows[f'tab-opaque-{nav}-{p}']
                self.assertEqual((row['metric'], row['min_samples'], row['gate']),
                                 (f'open.tab.opaque.{nav}.{p}', 9, [{'abs_max': limit}]))
        queue = JUDGE.derive_row(dict(rows['tab-opaque-queue-P0']), 345, 346, 345.5)
        a = {1: {'metrics': {queue['metric']: [345] * 9}}}
        self.assertEqual(JUDGE.judge_row(queue, a, {1: {'metrics': {queue['metric']: [351] * 9}}})['verdict'], 'FAIL')
        self.assertEqual(JUDGE.judge_row(queue, a, {1: {'metrics': {queue['metric']: [67] * 9}}})['verdict'], 'PASS')

    def test_the_two_standby_clauses_are_gated(self):
        """bench[8]: '2 once the standby worker is ready' and 'only on a cold browser cache' were never judged."""
        rows = {r['id']: r for r in self.table['rows']}

        def verdict_of(row, values):
            return JUDGE.judge_row(row, {}, {1: {'metrics': {row['metric']: values}}})['verdict']
        self.assertEqual(verdict_of(rows['requests-first-median'], [4] * 9), 'FAIL')
        self.assertEqual(verdict_of(rows['requests-first-median'], [2] * 9), 'PASS')
        self.assertEqual(verdict_of(rows['standby-warm'], [2] * 3), 'FAIL')
        self.assertEqual(verdict_of(rows['standby-warm'], [0] * 3), 'PASS')

    def test_section_eight_s_units_and_instrument_steps(self):
        """judge[11]: 16 KB is 16,000 B as section 8 writes it; judge[9]: an Event Timing row carries its 8 ms step."""
        rows = {r['id']: r for r in self.table['rows']}
        for size in (100, 1500, 18000):
            self.assertEqual(rows[f'server-list-body-{size}']['gate'], [{'abs_max': 16000}])
        stepped = [r for r in self.table['rows'] if JUDGE.reads_a(r) and
                   re.match(r'lists\.search\.(key_event|first_key|after_last_key)\.', r.get('metric') or '')]
        self.assertEqual(len(stepped), 9)
        self.assertTrue(all(r.get('a_step') == 8 for r in stepped), [r['id'] for r in stepped])


class BenchNeverShipsTests(unittest.TestCase):
    def test_the_image_build_leaves_ops_out(self):
        ignored = [line.strip() for line in (APP / 'deploy' / '.dockerignore').read_text().splitlines()
                   if line.strip() and not line.startswith('#')]
        self.assertIn('ops', ignored)
        install = (OPS / 'install.py').read_text()
        self.assertIn("shutil.copyfile(context / 'deploy' / '.dockerignore', context / '.dockerignore')", install)

    def test_ops_bench_is_never_discovered_as_tests(self):
        self.assertFalse((BENCH / '__init__.py').exists())
        self.assertEqual(sorted(p.name for p in BENCH.glob('test*.py')), [])
        found = unittest.defaultTestLoader.discover(str(OPS), pattern='bench_run.py', top_level_dir=str(OPS))
        self.assertEqual(found.countTestCases(), 0)


if __name__ == '__main__':
    unittest.main()
