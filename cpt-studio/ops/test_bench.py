"""The release-2 bench's own tests (RELEASE-2-SPEC R2-2): no database, no browser, in CI's ops suite.

They cover every refusal arm (the pure check, the bench's settings, the module-level refusal before a test database
could be made, the protocol driver), the lock and the never-overwritten output, benchdata's equal bytes twice, the
barcode (encode, decode, the page's decoder against Python's, and the barcode read back out of a scan's pixels), that
bench.cjs and proxy.cjs parse, the judge's arithmetic, its C5 floors and its INVALID cases, the office model's
arithmetic against the tree's own vhost, and that ops/bench never ships in the image and is never discovered as tests.
"""
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
        ok = self._run(code, DJANGO_SETTINGS_MODULE='cptstudio.settings', BENCH_PARTS='server',
                       CPT_STUDIO_TEST_DB_SUFFIX='x')
        self.assertEqual(ok.returncode, 0, ok.stderr[-800:])
        for extra in ({'CPT_STUDIO_DB_PORT': '55451'}, {'CPT_STUDIO_DB_HOST': 'db.example'},
                      {'CPT_STUDIO_CODING_MODE': 'live'}):
            with self.subTest(extra=extra):
                done = self._run(code, DJANGO_SETTINGS_MODULE='cptstudio.settings', BENCH_PARTS='server',
                                 CPT_STUDIO_TEST_DB_SUFFIX='x', **extra)
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

    def test_the_lock_stops_a_second_bench(self):
        with tempfile.TemporaryDirectory() as out:
            first = RUN.take_lock(Path(out) / 'bench.lock')
            self.assertIsNotNone(first)
            self.assertIsNone(RUN.take_lock(Path(out) / 'bench.lock'))
            first.close()
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
        row = {'id': 'c', 'kind': 'same_as_a'}
        same = [['text', 'reader', 'aa', 'bb', 2]]
        self.assertEqual(JUDGE.judge_row(row, {1: {'requests': same}}, {1: {'requests': same}})['verdict'], 'PASS')
        other = [['text', 'reader', 'ab', 'bb', 2]]
        self.assertEqual(JUDGE.judge_row(row, {1: {'requests': same}}, {1: {'requests': other}})['verdict'], 'FAIL')
        self.assertEqual(JUDGE.judge_row(row, {1: {'requests': None}}, {1: {'requests': same}})['verdict'], 'INVALID')

    def test_the_spread_and_its_floor(self):
        first = {'metrics': {'m': [100, 102, 98], 'n': [10, 10, 10], 'z': [0]}}
        second = {'metrics': {'m': [104, 106, 102], 'n': [10, 10, 10], 'z': [0]}}
        got = JUDGE.spread(first, second)
        self.assertAlmostEqual(got['m'], 4 / 102, places=4)
        self.assertEqual(got['n'], 0.0)
        self.assertEqual(got['z'], 0.0)
        self.assertEqual(JUDGE.floor_factor(0.05), 1.1)
        table = {'rows': [{'id': 'x', 'metric': 'm', 'gate': [{'rel_max': 1.02}]},
                          {'id': 'y', 'metric': 'm', 'gate': [{'abs_max': 5}]},
                          {'id': 'g', 'metric': 'm', 'gate': [{'rel_max': 0.6}], 'gain': True}]}
        floored = JUDGE.apply_floors(table, got)
        self.assertAlmostEqual(floored['rows'][0]['gate'][0]['floor_factor'], 1 + 2 * round(4 / 102, 4), places=4)
        self.assertNotIn('floor_factor', floored['rows'][1]['gate'][0])
        self.assertNotIn('floor_factor', floored['rows'][2]['gate'][0])
        self.assertAlmostEqual(floored['rows'][2]['spread'], round(4 / 102, 4))

    def test_section_eight_s_a_column_tolerance(self):
        self.assertTrue(JUDGE.a_column_close(310, 298))
        self.assertFalse(JUDGE.a_column_close(400, 298))
        self.assertTrue(JUDGE.a_column_close(200, [194, 199]))
        self.assertTrue(JUDGE.a_column_close(196, [194, 199]))
        self.assertFalse(JUDGE.a_column_close(120, [194, 199]))
        self.assertTrue(JUDGE.a_column_close(5, None))


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
        busy = JUDGE.office_429s(zones, JUDGE.office_requests(model, {**measured, 'typing': typing}))
        self.assertGreater(busy['cpt_write'], 0, busy)  # in the write zone, 5 typists at 2.9 a second each pass it


DOC_A, DOC_B = '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222'


def _entry(rid, method, url, status=200, poll=False):
    headers = {'x-request-id': rid, **({'x-cpt-poll': '1'} if poll else {})}
    return {'method': method, 'url': url, 'status': status, 'reqHeaders': headers}


def _row(rid, view, ids=(), at=1000.0, sign_in='s1', outcome='served'):
    return {'request_id': rid, 'view': view, 'encounter_ids': list(ids), 'count': len(ids), 'created_at': at,
            'sign_in_ref': sign_in, 'outcome': outcome, 'filters': {}}


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
        actions = [{'kind': 'records-open', 'label': 'text-2p', 'mode': 'pdf', 'canvasEpoch': 2300,
                    'rids': [['GET', '/api/encounters/<id>', 200, 'd1', 1],
                             ['GET', '/api/encounters/<id>/original?view=1', 200, 'v1', 5]]}]
        lists = [{'rid': 'l1', 'path': '/api/encounters', 'ids': [DOC_A, DOC_B]},
                 {'rid': 'l2', 'path': '/api/encounters', 'ids': [DOC_A, DOC_B]}]
        return entries, rows, actions, lists

    def test_every_served_read_is_one_row_or_a_counted_repeat(self):
        entries, rows, actions, lists = self.flow()
        got = RUN.judge_records(entries, rows, 1, actions, lists)
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
        # one answer, its own row naming other ids, nothing counted as a repeat: only the row-to-answer comparison sees it
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
        spaced = rows + [_row('p1', 'member.detail', [DOC_A], at=5000), _row('p2', 'member.detail', [DOC_A],
                                                                          at=70000)]
        self.assertTrue(RUN.judge_records(crowded, spaced, 1, actions, lists)['polls']['ok'])

    def test_a_failed_library_may_write_a_second_inline_row(self):
        entries, rows, actions, lists = self.flow()
        actions[0]['mode'] = 'frame'
        entries.append(_entry('v2', 'GET', f'/api/encounters/{DOC_A}/original?view=1'))
        actions[0]['rids'].append(['GET', '/api/encounters/<id>/original?view=1', 200, 'v2', 5])
        rows.append(_row('v2', 'member.inline', [DOC_A], at=2200))
        self.assertTrue(RUN.judge_records(entries, rows, 1, actions, lists)['openings']['ok'])

    def test_requests_map_to_the_views_they_record(self):
        self.assertEqual(RUN.read_kind('GET', '/api/encounters?list=documents&before=x'), 'member.list')
        self.assertEqual(RUN.read_kind('POST', '/api/encounters/search'), 'member.list')
        self.assertEqual(RUN.read_kind('GET', f'/api/encounters/{DOC_A}'), 'member.detail')
        self.assertEqual(RUN.read_kind('GET', f'/api/encounters/{DOC_A}/original?view=1'), 'member.inline')
        self.assertEqual(RUN.read_kind('GET', f'/api/encounters/{DOC_A}/original'), 'member.download')
        for method, url in (('POST', '/api/encounters'), ('GET', '/api/session'), ('GET', '/static/studio/app.js'),
                            ('GET', '/api/encounters/search'), ('POST', f'/api/encounters/{DOC_A}/decisions')):
            self.assertIsNone(RUN.read_kind(method, url), url)


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
