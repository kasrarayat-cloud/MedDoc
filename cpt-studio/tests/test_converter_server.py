"""studio.converter_server and the worker's side of it, studio.fable.document.convert_docx (release 1, E3): the Word
converter as a single-threaded service on a Unix socket, with no Django in it. Server and client run over a socket in a
temporary folder with stand-in runners (no LibreOffice): ok, refused, failed and busy; an unreachable socket and a
timeout; an oversize request and an oversize answer; a client that disconnects halfway; CONVERTER_REQUIRED with no
socket, which is BUSY and never converts in the worker; byte identity - the service's PDF equals the in-process PDF for
the same input and runner; and a BUSY document error settling as a failed round a member may retry, through the
existing coding path (the spec's [TO CONFIRM]). Release 2, R2-31: a refusal for what E2 would leave out of the PDF
names its code and counts in the refused answer, additively, and the worker believes them in that one form only -
release 1's worker and converter meet release 2's across the switch. Synthetic bytes only; nothing leaves the
machine."""
import hashlib
import io
import json
import os
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import types
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from studio import bounded, converter_server, decisions, jobs, models
from studio.fable import BUSY, CONVERT, client as fable_client, document, docx_package
from tests.support import coding as f
from tests.test_fable_document import (CONVERTED, DANGEROUS, DOCX, PLAIN_PACKAGE, TEXT, _echo_package, _follower,
                                       complex_field, failing_runner, fake_runner, full_package, no_pdf_runner,
                                       paragraph, private_tempdir, simple_field, word_package)

CPT_STUDIO = Path(__file__).resolve().parent.parent
MIB = 1024 * 1024


class Running:
    """A ConverterServer on a socket in a temporary folder, served one connection at a time by a thread of this
    process; leaving the block stops it (draining) and removes the folder."""

    def __init__(self, runner=None, *, idle_seconds=0.05, draining=False):
        self.folder = Path(tempfile.mkdtemp())
        self.path = str(self.folder / 'convert.sock')
        self.server = converter_server.ConverterServer(self.path, runner=runner, idle_seconds=idle_seconds)
        self.server.draining = draining
        self.thread = threading.Thread(target=self.server.serve_until_stopped, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.draining = True
        self.thread.join(30)
        self.server.server_close()
        shutil.rmtree(self.folder, ignore_errors=True)


def frame(header, body=b''):
    data = json.dumps(header).encode('ascii')
    return struct.pack('>I', len(data)) + data + body


def answer_of(sock, seconds=30):
    """The header a raw connection was answered with, or None when it was closed unanswered."""
    sock.settimeout(seconds)
    head = b''
    while len(head) < 4:
        try:
            chunk = sock.recv(4 - len(head))
        except ConnectionResetError:  # closed with our bytes unread: the kernel resets the connection
            return None
        if not chunk:
            return None
        head += chunk
    (length,) = struct.unpack('>I', head)
    body = b''
    while len(body) < length:
        body += sock.recv(length - len(body))
    return json.loads(body)


def raw(path):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(path)
    return sock


def big_pdf(data, work):  # a runner whose PDF is one byte over what a request may carry back
    return b'%PDF-' + b'x' * (docx_package.MAX_PDF_BYTES - 4)


def slow_runner(data, work):
    time.sleep(3)
    return CONVERTED


@override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=False)
class ServiceTests(SimpleTestCase):
    def setUp(self):
        private_tempdir(self)  # the in-thread server's conversions make their work folders here

    def test_the_service_pdf_equals_the_in_process_pdf_for_the_same_input_and_runner(self):
        packages = [PLAIN_PACKAGE, full_package(paragraph(complex_field(' PAGE ', '1')) + TEXT),
                    full_package(paragraph(complex_field(DANGEROUS['INCLUDETEXT'])) + paragraph(simple_field(
                        DANGEROUS['LINK'])), header=paragraph(complex_field(DANGEROUS['DDEAUTO']))),
                    word_package(TEXT * 400)]
        with Running(_echo_package) as running:
            for data in packages:
                with self.subTest(size=len(data)):
                    here = document.convert_docx(data, runner=_echo_package)
                    self.assertTrue(here.startswith(CONVERTED))  # the runner saw the safe package and echoed it
                    self.assertEqual(converter_server.request(running.path, data, total_seconds=60), here)
                    with override_settings(CONVERTER_SOCKET=running.path):
                        self.assertEqual(document.convert_docx(data), here)

    def test_refused_and_failed_are_a_failed_conversion(self):
        cases = [(fake_runner, b'PK\x03\x04 synthetic, not a zip', 'refused'),
                 (failing_runner, PLAIN_PACKAGE, 'failed'), (no_pdf_runner, PLAIN_PACKAGE, 'failed'),
                 (big_pdf, PLAIN_PACKAGE, 'failed')]
        for runner, data, said in cases:
            with self.subTest(runner=runner.__name__), Running(runner) as running:
                with self.assertRaises(converter_server.ConverterFailed) as caught, \
                        self.assertLogs('studio', 'INFO'):
                    converter_server.request(running.path, data, total_seconds=60)
                self.assertIn(said, str(caught.exception))
                with override_settings(CONVERTER_SOCKET=running.path), self.assertLogs('studio', 'INFO'), \
                        self.assertRaises(document.DocumentError) as wrapped:
                    document.convert_docx(data)
                self.assertEqual((wrapped.exception.failure_kind, wrapped.exception.text),
                                 (CONVERT, document.CONVERT_TEXT))

    def test_busy_an_unreachable_socket_and_a_timeout_are_busy(self):
        def busy(path, **kwargs):
            with override_settings(CONVERTER_SOCKET=path), self.assertRaises(document.DocumentError) as caught:
                document.convert_docx(PLAIN_PACKAGE)
            self.assertEqual((caught.exception.failure_kind, caught.exception.text), (BUSY, document.BUSY_TEXT))
            return caught.exception.detail

        with Running(fake_runner, idle_seconds=5, draining=True) as running, self.assertLogs('studio', 'INFO'):
            self.assertEqual(busy(running.path), 'the converter was busy')  # it answers busy while it stops
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.assertIn('could not be reached', busy(str(folder / 'missing.sock')))
        stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stale.bind(str(folder / 'stale.sock'))  # a socket file no server listens on any more
        stale.close()
        self.assertIn('could not be reached', busy(str(folder / 'stale.sock')))
        silent = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # takes the connection, never answers
        silent.bind(str(folder / 'silent.sock'))
        silent.listen(1)
        self.addCleanup(silent.close)
        with mock.patch.object(document, 'CONVERT_SECONDS', 0), mock.patch.object(document,
                                                                                  'CONVERTER_MARGIN_SECONDS', 1):
            started = time.monotonic()
            self.assertIn('did not answer in time', busy(str(folder / 'silent.sock')))
        self.assertLess(time.monotonic() - started, 10)

    def test_package_checks_out_of_time_in_the_service_are_busy_not_a_failed_conversion(self):
        # the L-CODING lens's finding 3, through the service: the converter answers busy, the worker fails BUSY
        with Running(fake_runner) as running, mock.patch.object(docx_package, 'PACKAGE_SECONDS', -1), \
                self.assertLogs('studio.converter_server', 'WARNING') as logged:
            with self.assertRaises(converter_server.ConverterBusy) as caught:
                converter_server.request(running.path, PLAIN_PACKAGE, total_seconds=60)
            self.assertEqual(str(caught.exception), 'the converter was busy')
            with override_settings(CONVERTER_SOCKET=running.path), self.assertRaises(document.DocumentError) as wrapped:
                document.convert_docx(PLAIN_PACKAGE)
        self.assertEqual((wrapped.exception.failure_kind, wrapped.exception.text), (BUSY, document.BUSY_TEXT))
        self.assertIn('converter: busy (checking it took longer than', '\n'.join(logged.output))

    def test_the_worker_allows_two_seconds_to_connect_and_its_threads_turns_in_all(self):
        with override_settings(CONVERTER_SOCKET='/run/cpt-convert/convert.sock', CONCURRENT_DOCUMENTS=4), \
                mock.patch.object(converter_server, 'request', return_value=CONVERTED) as request:
            self.assertEqual(document.convert_docx(PLAIN_PACKAGE), CONVERTED)
        request.assert_called_once_with('/run/cpt-convert/convert.sock', PLAIN_PACKAGE, connect_seconds=2,
                                        total_seconds=300)
        # the bounds hold together: four Word files in a row, each up to the parent's limit, the connect and a margin
        with override_settings(CONCURRENT_DOCUMENTS=4):
            self.assertEqual(document.converter_wait_seconds(),
                             4 * docx_package.CONVERT_SECONDS + document.CONVERTER_CONNECT_SECONDS
                             + document.CONVERTER_MARGIN_SECONDS)
        self.assertGreater(document.CONVERTER_MARGIN_SECONDS, 0)

    def test_each_conversion_has_the_parents_limit_and_a_stop_allows_one_to_finish(self):
        seen = {}

        def converting(data, *, runner=None, seconds=None, memory_bytes=None, watch=None):
            seen['seconds'] = seconds
            seen['watch'] = watch  # repair round 1, C2: the client's connection, so a client that leaves stops it
            return CONVERTED
        with mock.patch.object(docx_package, 'convert_in_child', converting), Running(fake_runner) as running, \
                self.assertLogs('studio.converter_server', 'INFO'):
            self.assertEqual(converter_server.request(running.path, PLAIN_PACKAGE, total_seconds=60), CONVERTED)
        self.assertEqual(seen['seconds'], docx_package.CONVERT_SECONDS)
        self.assertIsInstance(seen['watch'], socket.socket)
        # what docker stop must allow the converter (A7): the conversion running, killing what it started, a margin
        self.assertEqual(converter_server.MIN_STOP_SECONDS, docx_package.CONVERT_SECONDS + bounded.GROUP_GONE_SECONDS
                         + converter_server.STOP_MARGIN_SECONDS)
        self.assertGreater(converter_server.STOP_MARGIN_SECONDS, 0)
        self.assertEqual(converter_server.MIN_STOP_SECONDS, 80)

    def test_required_with_no_socket_is_busy_and_nothing_is_converted_in_the_worker(self):
        with override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=True), \
                self.assertRaises(document.DocumentError) as caught:
            document.convert_docx(PLAIN_PACKAGE, runner=fake_runner)
        self.assertEqual((caught.exception.failure_kind, caught.exception.text), (BUSY, document.BUSY_TEXT))
        self.assertIn('no converter socket', caught.exception.detail)
        # the control: with no requirement, the same call converts in-process (tests and local runs)
        self.assertEqual(document.convert_docx(PLAIN_PACKAGE, runner=fake_runner), CONVERTED + b'PK\x03\x04')

    def test_an_oversize_request_and_an_oversize_answer(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        with self.assertRaises(converter_server.ConverterFailed):  # refused before any connection (none listens)
            converter_server.request(str(folder / 'none.sock'), b'x' * (converter_server.MAX_REQUEST_BYTES + 1),
                                     total_seconds=60)
        with Running(fake_runner) as running, self.assertLogs('studio.converter_server', 'WARNING'):
            sock = raw(running.path)
            sock.sendall(frame({'op': 'convert', 'size': converter_server.MAX_REQUEST_BYTES + 1,
                                'sha256': '0' * 64}))  # no body follows: it is answered before one is read
            self.assertEqual(answer_of(sock), {'status': 'error', 'kind': 'refused', 'size': 0})
            sock.close()
        # an answer that says more than a PDF may be is refused without waiting for it
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(folder / 'liar.sock'))
        listener.listen(1)
        self.addCleanup(listener.close)

        def lie():
            connection, _ = listener.accept()
            connection.recv(1 << 20)
            connection.sendall(frame({'status': 'ok', 'size': docx_package.MAX_PDF_BYTES + 1, 'sha256': '0' * 64}))
            time.sleep(5)
            connection.close()
        threading.Thread(target=lie, daemon=True).start()
        started = time.monotonic()
        with self.assertRaises(converter_server.ConverterFailed) as caught:
            converter_server.request(str(folder / 'liar.sock'), PLAIN_PACKAGE, total_seconds=60)
        self.assertLess(time.monotonic() - started, 4)
        self.assertIn('a PDF it may not send', str(caught.exception))

    def test_a_client_that_disconnects_halfway_leaves_the_server_serving(self):
        with Running(fake_runner) as running:
            with self.assertLogs('studio.converter_server', 'INFO') as logged:  # repair round 1, C2: see below
                sock = raw(running.path)
                sock.sendall(frame({'op': 'convert', 'size': 1000, 'sha256': hashlib.sha256(b'x' * 1000).hexdigest()},
                                   b'x' * 500))
                sock.close()
                garbage = raw(running.path)
                garbage.sendall(b'\xff\xff\xff\xffnot a frame')
                self.assertIsNone(answer_of(garbage))
                garbage.close()
                wrong = raw(running.path)
                wrong.sendall(frame({'op': 'convert', 'size': 3, 'sha256': '0' * 64}, b'abc'))
                self.assertEqual(answer_of(wrong)['kind'], 'refused')  # the bytes do not match their digest
                wrong.close()
            # repair round 1, C2: a request is queued on its header and its Word bytes read at its turn, so a client
            # gone halfway is met there - as one that left before its turn, or one whose bytes ended, as the race goes
            said = '\n'.join(logged.output)
            self.assertTrue('ended before its Word file arrived' in said or 'client left before its turn' in said,
                            said)
            self.assertEqual(converter_server.request(running.path, PLAIN_PACKAGE, total_seconds=60),
                             CONVERTED + b'PK\x03\x04')

    def test_conversions_take_turns_and_a_ping_meanwhile_is_answered_at_once(self):
        # repair round 1, C2 (coding-1): a ping during a conversion was 'busy' (it waited behind the conversion); it is
        # answered at once now, while the conversions still take turns (tests/test_r1_repair_c.py)
        with Running(slow_runner) as running:
            self.assertEqual(converter_server.ping(running.path), 'ok')
            answers = []
            first = threading.Thread(target=lambda: answers.append(converter_server.request(
                running.path, PLAIN_PACKAGE, total_seconds=60)))
            second = threading.Thread(target=lambda: answers.append(converter_server.request(
                running.path, PLAIN_PACKAGE, total_seconds=60)))
            started = time.monotonic()
            first.start()
            time.sleep(0.5)
            second.start()
            pinged = time.monotonic()
            self.assertEqual(converter_server.ping(running.path, seconds=1), 'ok')  # while one converts, one waits
            self.assertLess(time.monotonic() - pinged, 0.5)
            first.join(30)
            second.join(30)
            self.assertEqual(answers, [CONVERTED, CONVERTED])
            self.assertGreaterEqual(time.monotonic() - started, 6)  # one after the other, 3 s each
        with self.assertRaises(converter_server.ConverterBusy):
            converter_server.ping(running.path)

    def test_the_log_holds_sizes_and_counts_never_the_document(self):
        data = full_package(paragraph(complex_field(DANGEROUS['INCLUDETEXT'], 'SYNTHETIC VISIBLE WORDS')))
        with Running(_echo_package) as running, self.assertLogs('studio', 'INFO') as logged:
            converter_server.request(running.path, data, total_seconds=60)
        text = '\n'.join(logged.output)
        self.assertIn('1 field instructions', text)
        self.assertIn(f'converted {len(data)} bytes', text)
        for content in ('SYNTHETIC', 'secret', 'word/', 'INCLUDETEXT', '.xml'):
            self.assertNotIn(content, text)


class SocketTests(SimpleTestCase):
    def test_the_socket_is_0660_and_a_stale_one_is_replaced_but_never_another_file(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = str(folder / 'convert.sock')
        first = converter_server.ConverterServer(path, group=os.getgid())
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o660)
        self.assertTrue(stat.S_ISSOCK(os.stat(path).st_mode))
        first.socket.close()  # a converter that died: its socket file stays
        second = converter_server.ConverterServer(path)
        self.assertEqual(converter_server.ping(path), BUSY)  # taken (no loop serves it here), so it listens
        second.server_close()
        self.assertFalse(os.path.exists(path))  # a clean stop removes its own socket
        Path(path).write_text('not a socket')
        with self.assertRaises(RuntimeError):
            converter_server.ConverterServer(path)
        self.assertEqual(Path(path).read_text(), 'not a socket')

    def test_constants_the_service_shares_with_the_settings_and_the_worker(self):
        self.assertEqual(converter_server.MAX_REQUEST_BYTES, settings.MAX_UPLOAD_BYTES)
        self.assertEqual(document.BUSY_TEXT, jobs.FAILURE_TEXT[BUSY])
        self.assertEqual((converter_server.SOCKET_PATH, converter_server.SOCKET_MODE, converter_server.SOCKET_GROUP,
                          converter_server.BACKLOG), ('/run/cpt-convert/convert.sock', 0o660, 10150, 8))
        self.assertEqual(converter_server.ConverterServer.request_queue_size, 8)


class CommandTests(SimpleTestCase):
    def setUp(self):
        private_tempdir(self)

    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(converter_server.logging, 'basicConfig'):
            code = converter_server.main(list(argv))
        return code, out.getvalue()

    def test_the_self_test_converts_a_word_file_it_builds(self):
        docx = converter_server.self_test_docx()
        self.assertEqual(docx, converter_server.self_test_docx())  # the same bytes every time
        self.assertEqual(docx_package.safe_package(docx), docx)  # a package with nothing to remove
        self.assertEqual(converter_server.self_test(runner=fake_runner), len(CONVERTED) + 4)
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        with mock.patch.object(docx_package, 'SOFFICE', str(_follower(folder))):
            code, said = self.run_main('--self-test')
        self.assertEqual(code, 0)
        self.assertIn('self-test: ok', said)
        with mock.patch.object(docx_package, 'SOFFICE', str(folder / 'no-soffice-here')), \
                self.assertLogs('studio.bounded', 'ERROR'):
            code, said = self.run_main('--self-test')
        self.assertEqual(code, 1)
        self.assertIn('self-test: failed', said)

    def test_ping_answers_for_a_running_converter_only(self):
        with Running(fake_runner) as running:
            self.assertEqual(self.run_main('--ping', '--socket', running.path), (0, 'cpt-studio converter: ok\n'))
        code, said = self.run_main('--ping', '--socket', running.path)
        self.assertEqual(code, 1)
        self.assertIn('not taking connections', said)

    def test_the_service_runs_with_no_django_no_settings_and_no_secret_and_stops_on_sigterm(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(folder), 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(folder)}
        imported = subprocess.run(
            [sys.executable, '-c', 'import sys, studio.converter_server; '
                                   'print([m for m in sys.modules if m == "django" or m.startswith("django.")])'],
            cwd=CPT_STUDIO, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual((imported.returncode, imported.stdout.strip()), (0, '[]'), imported.stderr)
        path = str(folder / 'convert.sock')
        server = subprocess.Popen([sys.executable, '-m', 'studio.converter_server', '--socket', path], cwd=CPT_STUDIO,
                                  env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 30
            while not os.path.exists(path) and time.monotonic() < deadline and server.poll() is None:
                time.sleep(0.05)
            ping = subprocess.run([sys.executable, '-m', 'studio.converter_server', '--ping', '--socket', path],
                                  cwd=CPT_STUDIO, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(ping.returncode, 0, ping.stdout + ping.stderr)
            with self.assertRaises(converter_server.ConverterFailed) as caught:  # LibreOffice or not, it is refused
                converter_server.request(path, b'PK\x03\x04 synthetic, not a zip', total_seconds=60)
            self.assertIn('refused the Word package', str(caught.exception))
            server.send_signal(signal.SIGTERM)
            self.assertEqual(server.wait(timeout=30), 0)
            self.assertFalse(os.path.exists(path))
            log = server.stderr.read().decode('utf-8', 'replace')
            self.assertIn('converter: listening', log)
            self.assertIn('converter: stopped', log)
        finally:
            if server.poll() is None:
                server.kill()
                server.wait(timeout=30)
            server.stderr.close()


class BusyRoundTests(TestCase):
    """The spec's [TO CONFIRM] (E3): a BUSY DocumentError settles through the existing path as a failed round of kind
    busy, with the coding service's busy sentence, nothing sent, and a retry offered and taken by a member."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.originals = tempfile.TemporaryDirectory()
        cls.override = override_settings(ORIGINALS_DIR=Path(cls.originals.name))
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        cls.originals.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws)
        self.coder = f.FakeCoder()  # nothing may be sent: it fails the test if the reader is asked
        patcher = mock.patch.object(fable_client, 'coder', return_value=self.coder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def coded(self):
        enc = f.encounter(self.ws, self.user)
        rev = f.upload(enc, self.user, PLAIN_PACKAGE, 'synthetic-note.docx', DOCX)
        jobs.start_round(enc, rev, models.CodingRound.UPLOAD, self.user)
        job = jobs.claim_next()
        jobs.run_job(job)
        job.refresh_from_db()
        enc.refresh_from_db()
        return enc, rev, job, jobs.latest_round(enc)

    def assert_busy_and_retried(self):
        enc, rev, job, round_ = self.coded()
        self.assertEqual((job.state, round_.state, round_.failure_kind, round_.error),
                         (models.Job.FAILED, models.CodingRound.FAILED, BUSY, jobs.FAILURE_TEXT[BUSY]))
        self.assertEqual((self.coder.calls, self.coder.counts), ([], []))  # nothing was sent
        self.assertFalse(models.ProviderRun.objects.filter(encounter=enc).exists())
        self.assertTrue(decisions.retry_offered(enc, round_))
        again = decisions.retry(enc, self.user)
        self.assertEqual((again.state, again.trigger, again.revision_id, again.number),
                         (models.CodingRound.QUEUED, models.CodingRound.RETRY, rev.pk, round_.number + 1))

    @override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=True)
    def test_with_a_converter_required_and_none_named_the_round_fails_busy_and_a_member_may_retry(self):
        self.assert_busy_and_retried()

    def test_with_a_converter_that_cannot_be_reached_the_round_fails_busy_and_a_member_may_retry(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        with override_settings(CONVERTER_SOCKET=str(folder / 'missing.sock'), CONVERTER_REQUIRED=True):
            self.assert_busy_and_retried()


# --- release 2, R2-31: the refused answer names its code and counts, additively ------------------------------------

R2_IMPORTING = full_package(TEXT + '<w:altChunk r:id="rIdChunk"/>', document_rels=(
    '<Relationship Id="rIdChunk" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/aFChunk" '
    'Target="afchunk1.txt"/>',), parts=[('word/afchunk1.txt', 'SYNTHETIC IMPORTED TEXT')])
R2_BARE_OBJECT = full_package(paragraph('<w:r><w:object><o:OLEObject Type="Embed" ProgID="Package" r:id="rIdOle"/>'
                                        '</w:object></w:r>'), document_rels=(
    '<Relationship Id="rIdOle" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/package" '
    'Target="embeddings/object.bin"/>',), parts=[('word/embeddings/object.bin', b'\xd0\xcf synthetic object')])
R2_REFUSALS = ((R2_IMPORTING, 'inserted_document', {'documents': 1, 'objects': 0, 'controls': 0, 'fields': 0}),
               (R2_BARE_OBJECT, 'inserted_object', {'documents': 0, 'objects': 1, 'controls': 0, 'fields': 0}))
# release 1's studio/converter_server.py (9ee0c85be), as git stores it: the worker and converter of the other half of
# the blue/green switch
R2_RELEASE_1_CONVERTER_BLOB = '9a6195defa312b30c4d54d5ee7e6f15356d4b28f'


class R2Answering:
    """A socket that answers every convert request with ``header`` (a converter of another build, or one that
    misbehaves), after reading the whole request."""

    def __init__(self, header):
        self.folder = Path(tempfile.mkdtemp())
        self.path = str(self.folder / 'answering.sock')
        self.header, self.listener = header, socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(self.path)
        self.listener.listen(4)
        self.listener.settimeout(0.05)  # closing it would not wake an accept: the loop looks at stopped instead
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def serve(self):
        while not self.stopped.is_set():
            try:
                connection, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(10)
                (length,) = struct.unpack('>I', connection.recv(4, socket.MSG_WAITALL))
                size = json.loads(connection.recv(length, socket.MSG_WAITALL))['size']
                connection.recv(size, socket.MSG_WAITALL)
                connection.sendall(frame(self.header))

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stopped.set()
        self.thread.join(10)
        self.listener.close()
        shutil.rmtree(self.folder, ignore_errors=True)


def r2_release_1_converter_module():
    """Release 1's converter module, loaded from the repository by its blob id (its imports resolve in this tree), or
    None where there is no git checkout (the image has no .git)."""
    try:
        done = subprocess.run(['git', '-C', str(CPT_STUDIO), 'cat-file', 'blob', R2_RELEASE_1_CONVERTER_BLOB],
                              capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode or not done.stdout:
        return None
    module = types.ModuleType('laned_release_1_converter_server')
    module.__package__ = 'studio'
    exec(compile(done.stdout.decode('utf-8'), 'release-1 converter_server.py', 'exec'), module.__dict__)
    return module


@override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=False)
class RefusalReasonTests(SimpleTestCase):
    """R2-31 steps 2 and 3: a file refused for what E2 would leave out of its PDF is answered refused, size 0, with its
    code and counts added; the worker believes them only in exactly the form a release-2 converter writes them, and
    otherwise - an older converter, or anything else - reads the general refusal, as today."""

    def setUp(self):
        private_tempdir(self)

    def assert_general(self, error):
        self.assertEqual((error.failure_kind, error.text, error.code, error.counts, error.recorded()),
                         (CONVERT, document.CONVERT_TEXT, '', {}, {}))

    def test_the_raw_answer_for_each_code(self):
        with Running(fake_runner) as running, self.assertLogs('studio.converter_server', 'INFO') as logged:
            for data, code, counts in R2_REFUSALS:
                with self.subTest(code=code):
                    sock = raw(running.path)
                    sock.sendall(frame({'op': 'convert', 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()},
                                       data))
                    self.assertEqual(answer_of(sock), {'status': 'error', 'kind': 'refused', 'size': 0, 'reason': code,
                                                       'counts': counts})
                    sock.close()
            # any other refusal keeps release 1's answer exactly: no reason, no counts
            data = b'PK\x03\x04 synthetic, not a zip'
            sock = raw(running.path)
            sock.sendall(frame({'op': 'convert', 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}, data))
            self.assertEqual(answer_of(sock), {'status': 'error', 'kind': 'refused', 'size': 0})
            sock.close()
        said = '\n'.join(logged.output)
        self.assertIn('converter: refused a Word file (it holds inserted content that could not be shown in the PDF)',
                      said)
        self.assertNotIn('SYNTHETIC', said)
        self.assertNotIn('afchunk', said)

    def test_the_document_error_has_the_sentence_code_and_counts_through_the_socket_and_in_process(self):
        with Running(fake_runner) as running, self.assertLogs('studio', 'INFO'):
            for data, code, counts in R2_REFUSALS:
                for path in (running.path, ''):
                    with self.subTest(code=code, socket=bool(path)), override_settings(CONVERTER_SOCKET=path), \
                            self.assertRaises(document.DocumentError) as caught:
                        document.convert_docx(data, runner=failing_runner)
                    error = caught.exception
                    self.assertEqual((error.failure_kind, error.text, error.code, error.counts),
                                     (CONVERT, document.REFUSED_PACKAGE_TEXT[code], code, counts))
                    self.assertEqual(error.recorded(), {'refused': code, 'inserted': counts})
                    if path:
                        with self.assertRaises(converter_server.ConverterFailed) as failed:
                            converter_server.request(path, data, total_seconds=60)
                        self.assertEqual((str(failed.exception), failed.exception.code, failed.exception.counts),
                                         ('the converter refused the Word package', code, counts))

    def test_a_reason_in_any_other_form_gives_the_general_sentence_and_no_record(self):
        good = {'documents': 1, 'objects': 0, 'controls': 0, 'fields': 0}
        refused = {'status': 'error', 'kind': 'refused', 'size': 0}
        variants = {
            'an older converter: no reason': refused,
            'an unknown reason': {**refused, 'reason': 'inserted_picture', 'counts': good},
            'a reason that is a list': {**refused, 'reason': ['inserted_document'], 'counts': good},
            'counts that are a list': {**refused, 'reason': 'inserted_document', 'counts': [1, 0, 0, 0]},
            'no counts': {**refused, 'reason': 'inserted_document'},
            'a count missing': {**refused, 'reason': 'inserted_document',
                                'counts': {'documents': 1, 'objects': 0, 'controls': 0}},
            'an extra key': {**refused, 'reason': 'inserted_document', 'counts': {**good, 'pages': 0}},
            'True for a count': {**refused, 'reason': 'inserted_document', 'counts': {**good, 'documents': True}},
            '-1': {**refused, 'reason': 'inserted_object', 'counts': {**good, 'documents': 0, 'objects': -1}},
            'a string': {**refused, 'reason': 'inserted_document', 'counts': {**good, 'documents': '1'}},
            'a float': {**refused, 'reason': 'inserted_document', 'counts': {**good, 'documents': 1.0}},
            'past 1,000,000': {**refused, 'reason': 'inserted_document', 'counts': {**good, 'documents': 1_000_001}},
            'every count 0': {**refused, 'reason': 'inserted_object', 'counts': {**good, 'documents': 0}},
            'a document code with no document': {**refused, 'reason': 'inserted_document',
                                                 'counts': {**good, 'documents': 0, 'objects': 1}},
            'an object code with a document': {**refused, 'reason': 'inserted_object', 'counts': good},
            'a reason on a failure': {'status': 'error', 'kind': 'failed', 'size': 0, 'reason': 'inserted_document',
                                      'counts': good},
        }
        for label, header in variants.items():
            with self.subTest(label), R2Answering(header) as answering, \
                    override_settings(CONVERTER_SOCKET=answering.path), \
                    self.assertRaises(document.DocumentError) as caught:
                document.convert_docx(PLAIN_PACKAGE)
            self.assert_general(caught.exception)
        # the positive control: the same listener, in the one form believed
        with R2Answering({**refused, 'reason': 'inserted_document', 'counts': good}) as answering, \
                override_settings(CONVERTER_SOCKET=answering.path), \
                self.assertRaises(document.DocumentError) as caught:
            document.convert_docx(PLAIN_PACKAGE)
        self.assertEqual((caught.exception.code, caught.exception.counts), ('inserted_document', good))
        self.assertEqual(converter_server.MAX_COUNT, 1_000_000)

    def test_release_1s_worker_and_converter_meet_release_2s_across_the_switch(self):
        release_1 = r2_release_1_converter_module()
        if release_1 is None:
            self.skipTest('no git checkout here (the image has no .git): release 1\'s converter is read from git')
        # release 1's worker reads release 2's converter by the kind alone: a failed conversion, its general sentence
        with Running(fake_runner) as running, self.assertLogs('studio', 'INFO'):
            for data, code, _ in R2_REFUSALS:
                with self.subTest(worker='release 1', code=code), \
                        self.assertRaises(release_1.ConverterFailed) as caught:
                    release_1.request(running.path, data, total_seconds=60)
                self.assertEqual(str(caught.exception), 'the converter refused the Word package')
        # release 1's converter gives no reason: release 2's worker reads the general refusal
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        server = release_1.ConverterServer(str(folder / 'release-1.sock'), runner=fake_runner, idle_seconds=0.05)
        thread = threading.Thread(target=server.serve_until_stopped, daemon=True)
        thread.start()
        try:
            with self.assertLogs(release_1.log.name, 'INFO'):  # its own logger: the module loaded from git
                for data, code, _ in R2_REFUSALS:
                    with self.subTest(converter='release 1', code=code), \
                            override_settings(CONVERTER_SOCKET=server.path), \
                            self.assertRaises(document.DocumentError) as caught:
                        document.convert_docx(data)
                    self.assert_general(caught.exception)
        finally:
            server.draining = True
            thread.join(30)
            server.server_close()
