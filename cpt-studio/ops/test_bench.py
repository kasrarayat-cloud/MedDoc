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
    'load_before': [1.0, 1.0, 1.0], 'load_after': [1.0, 1.0, 1.0], 'load_max': load, 'metrics': {}, 'checks': {},
    'controls': {}, 'errors': [], 'unexpected_statuses': {}, 'console_errors': [], 'blocked_requests': []}))
with open(env['STUB_CALLS'], 'a') as calls:
    calls.write(name + chr(10))
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

    def test_the_driver_fails_when_a_round_is_still_invalid_with_no_retries_left(self):
        done = self.drive({'*': 12.0}, retries=1)
        self.assertEqual(done.returncode, 3, done.stderr)  # protocol[0]: it exited 0 after 'no retries left'
        log = (self.out / 'protocol.log').read_text()
        self.assertIn('A:101 server INVALID (exit 0, load 12.0; load average 12.0 > 8.0); no retries left', log)


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
        self.assertEqual(set(BD.SIZES), {'n50', 'n100', 'n101', 'n1500', 'n5000', 'n18000'})

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
        def run(order):
            rounds = []
            for n in (1, 2, 3):
                rounds.append(_round('A', n, {'open.later.first_page.P0': [300, 298, 296], 'open.text.frame.P0': [100]},
                                     checks={'correct.barcode_every_open': {'ok': True}}))
                for profile in order:
                    ok = not (n == 1 and profile == 'P0')
                    rounds.append(_round('B', n, {'open.later.first_page.P0': [120, 121, 119],
                                                  'open.text.frame.P0': [100]}, app_js='bbb',
                                         parts=(f'open@{profile}',),
                                         checks={'correct.barcode_every_open': {'ok': ok, 'opens': 9}}))
            return self.answer(self.folder(rounds))
        for order in (('P0', 'P3'), ('P3', 'P0')):  # the failing file sorting first, then last
            with self.subTest(order=order):
                got = run(order)
                self.assertEqual(got['verdict'], 'FAIL', got)
                self.assertEqual(next(r for r in got['rows'] if r['id'] == 'barcode')['verdict'], 'FAIL')
        merged = {}
        JUDGE._and_merge(merged, {'left.no_store': {'ok': False, 'missing': ['GET /original 304']}})
        JUDGE._and_merge(merged, {'left.no_store': {'ok': True}})
        self.assertFalse(merged['left.no_store']['ok'])
        self.assertEqual(len(merged['left.no_store']['by_file']), 2)

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

    def test_every_no_worse_than_a_gate_carries_the_floor_of_its_recorded_spread(self):
        """C5: every "no worse than A" limit is at least A x (1 + 2 x its metric's A/A spread), written here from lane
        M's recorded A/A before any B was measured and never moved: each floor is exactly its recorded spread's."""
        spread = self.table.get('spread') or {}
        recorded = spread.get('metrics') or {}
        self.assertTrue(recorded and spread.get('source'), 'acceptance.json carries no recorded A/A spread')
        floored = 0
        for row in self.table['rows']:
            for gate in row.get('gate', []):
                if JUDGE.needs_floor(gate):
                    self.assertIn(row['metric'], recorded, row['id'])
                    self.assertEqual(gate.get('spread'), recorded[row['metric']], row['id'])
                    self.assertEqual(gate.get('floor_factor'), JUDGE.floor_factor(recorded[row['metric']]), row['id'])
                    floored += 1
            if row.get('gain'):
                self.assertIsNotNone(row.get('spread'), row['id'])
                self.assertEqual(row['spread'], recorded.get(row['metric']), row['id'])
        self.assertGreaterEqual(floored, 15)  # section 8's no-worse-than-A gates: none may lose its floor unseen


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
