"""The Word converter as a service of its own (release 1, E3; the installer's container is A7): a single-threaded
Unix-socket server with no Django in it - no settings, no secret, no database - that converts one Word file at a time by
exactly the code the worker ran in-process (studio.fable.docx_package.convert_in_child, which is
run_bounded(_convert_package, soffice_convert, ...)), so the same limits apply inside its container; and ``request``,
the worker's side (studio.fable.document.convert_docx calls it when settings.CONVERTER_SOCKET names the socket).

One request per connection. Both directions are framed alike: a 4-byte big-endian length, a JSON header of that many
bytes, then a body of the header's ``size`` bytes.
- The request: {"op": "convert", "size": n, "sha256": hex} and the Word bytes (at most MAX_REQUEST_BYTES, the upload
  limit), or {"op": "ping"}.
- The answer: {"status": "ok", "size": n, "sha256": hex} and the PDF (at most docx_package.MAX_PDF_BYTES), or
  {"status": "error", "kind": "refused" | "failed" | "busy", "size": 0}. The worker reads refused and failed as a failed
  conversion (CONVERT) and busy - the converter stopping, the package checks out of time, or no answer at all: an
  unreachable socket, a timeout, a closed connection - as BUSY, which a member may retry.
- Conversions run one at a time; up to BACKLOG more connections wait in the listen backlog. On SIGTERM the server
  finishes the conversion it is running, answers busy to the connections waiting, and stops once none is left.
- Its log holds sizes, durations and fixed words: never a document's text, title or file name.

    python -m studio.converter_server              serve at SOCKET_PATH (mode 0660, group SOCKET_GROUP)
    python -m studio.converter_server --ping       exit 0 when the server takes connections (the health check)
    python -m studio.converter_server --self-test  convert a Word file built in memory here; exit 0 on a %PDF- answer
    (--socket PATH serves or pings another socket, as tests and local runs do; it keeps the socket's group as made.)
"""
import argparse
import hashlib
import io
import json
import logging
import os
import re
import signal
import socket
import socketserver
import stat
import struct
import sys
import time
import zipfile

from .fable import docx_package

log = logging.getLogger(__name__)

SOCKET_PATH = '/run/cpt-convert/convert.sock'
SOCKET_MODE = 0o660
SOCKET_GROUP = 10150  # the worker's group, which the converter's own user shares (A7)
BACKLOG = 8  # connections that may wait while one conversion runs
MAX_REQUEST_BYTES = 15 * 1024 * 1024  # settings.MAX_UPLOAD_BYTES (a test holds them equal): nothing larger is uploaded
MAX_HEADER_BYTES = 4096
REQUEST_SECONDS = 30  # how long a connection may take to send its whole request
ANSWER_SECONDS = 30  # and to take its answer
CONNECT_SECONDS = 2
PING_SECONDS = 2
IDLE_SECONDS = 0.5  # how often the server looks whether it was asked to stop, while no connection waits
CONVERT, PING = 'convert', 'ping'
OK, ERROR = 'ok', 'error'
REFUSED, FAILED, BUSY = 'refused', 'failed', 'busy'
_LENGTH = struct.Struct('>I')
_SHA256 = re.compile(r'[0-9a-f]{64}\Z')
# The self-test's Word file: the three parts a .docx needs, one synthetic paragraph, a fixed timestamp.
SELF_TEST_TEXT = 'SYNTHETIC CONVERTER SELF TEST - FICTIONAL - NO PATIENT DATA'
_SELF_TEST_PARTS = (
    ('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
     '<Default Extension="xml" ContentType="application/xml"/>'
     '<Override PartName="/word/document.xml" '
     'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'),
    ('_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" '
     'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
     'Target="word/document.xml"/></Relationships>'),
    ('word/document.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
     '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
     f'<w:p><w:r><w:t>{SELF_TEST_TEXT}</w:t></w:r></w:p></w:body></w:document>'),
)


class ConverterBusy(Exception):
    """The converter cannot convert now: it cannot be reached, did not answer in time, closed the connection, or said
    busy. The worker fails the document BUSY, which a member may retry."""


class ConverterFailed(Exception):
    """The converter refused the Word file, failed to convert it, or answered in a form it does not use. The worker
    fails the document CONVERT."""


class _Malformed(Exception):
    """A frame that is not one this protocol uses."""


def _frame(header: dict, body: bytes = b'') -> bytes:
    data = json.dumps(header, separators=(',', ':'), sort_keys=True).encode('ascii')
    return _LENGTH.pack(len(data)) + data + body


def _receive(sock, size, deadline) -> bytes:
    """Exactly ``size`` bytes of ``sock`` by ``deadline``: EOFError when it closes first, TimeoutError past the
    deadline."""
    chunks, left = [], size
    while left:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        sock.settimeout(remaining)
        chunk = sock.recv(min(left, 1 << 20))
        if not chunk:
            raise EOFError
        chunks.append(chunk)
        left -= len(chunk)
    return b''.join(chunks)


def _read_header(sock, deadline) -> dict:
    (length,) = _LENGTH.unpack(_receive(sock, _LENGTH.size, deadline))
    if not 2 <= length <= MAX_HEADER_BYTES:
        raise _Malformed
    try:
        header = json.loads(_receive(sock, length, deadline).decode('ascii'))
    except (UnicodeDecodeError, ValueError):
        raise _Malformed from None
    if not isinstance(header, dict):
        raise _Malformed
    return header


def _send(sock, data, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    sock.settimeout(remaining)
    sock.sendall(data)


def _error(kind) -> dict:
    return {'status': ERROR, 'kind': kind, 'size': 0}


# --- the worker's side ------------------------------------------------------------------------------------------------

def request(path, data: bytes, *, connect_seconds=CONNECT_SECONDS, total_seconds) -> bytes:
    """The PDF the converter on the socket ``path`` makes of ``data`` (a Word file): ``connect_seconds`` to connect and
    ``total_seconds`` in all. ConverterBusy or ConverterFailed (each with a detail in fixed words) otherwise."""
    if len(data) > MAX_REQUEST_BYTES:
        raise ConverterFailed('the Word file is larger than the converter takes')
    deadline = time.monotonic() + total_seconds
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(connect_seconds)
        try:
            sock.connect(path)
        except OSError as exc:
            raise ConverterBusy(f'the converter could not be reached ({type(exc).__name__})') from None
        try:
            _send(sock, _frame({'op': CONVERT, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}, data),
                  deadline)
            answer = _read_header(sock, deadline)
            status = answer.get('status')
            if status == OK:
                size, digest = answer.get('size'), answer.get('sha256')
                if type(size) is not int or not 0 < size <= docx_package.MAX_PDF_BYTES or not isinstance(digest, str) \
                        or not _SHA256.match(digest):
                    raise ConverterFailed('the converter answered with a PDF it may not send')
                pdf = _receive(sock, size, deadline)
                if hashlib.sha256(pdf).hexdigest() != digest:
                    raise ConverterFailed('the converter sent a PDF that does not match its digest')
                return pdf
            kind = answer.get('kind') if status == ERROR else None
            if kind == BUSY:
                raise ConverterBusy('the converter was busy')
            if kind == REFUSED:
                raise ConverterFailed('the converter refused the Word package')
            if kind == FAILED:
                raise ConverterFailed('the conversion failed in the converter')
            raise ConverterFailed('the converter answered in a form it does not use')
        except TimeoutError:
            raise ConverterBusy('the converter did not answer in time') from None
        except EOFError:
            raise ConverterBusy('the converter closed the connection before it answered') from None
        except _Malformed:
            raise ConverterFailed('the converter answered in a form it does not use') from None
        except OSError as exc:
            raise ConverterBusy(f'the connection to the converter failed ({type(exc).__name__})') from None
    finally:
        sock.close()


def ping(path=SOCKET_PATH, *, seconds=PING_SECONDS) -> str:
    """'ok' when the converter on ``path`` answered a ping, 'busy' when it took the connection but is converting (it
    answers one connection at a time); ConverterBusy when nothing takes connections there."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(seconds)
        try:
            sock.connect(path)
        except OSError as exc:
            raise ConverterBusy(f'the converter could not be reached ({type(exc).__name__})') from None
        deadline = time.monotonic() + seconds
        try:
            _send(sock, _frame({'op': PING}), deadline)
            answer = _read_header(sock, deadline)
        except TimeoutError:
            return BUSY
        except (EOFError, OSError, _Malformed) as exc:
            raise ConverterBusy(f'the converter did not answer a ping ({type(exc).__name__})') from None
        if answer.get('status') != OK:
            raise ConverterBusy('the converter did not answer a ping')
        return OK
    finally:
        sock.close()


# --- the server -----------------------------------------------------------------------------------------------------

class _Connection(socketserver.BaseRequestHandler):
    def handle(self):
        self.server.serve_connection(self.request)


class ConverterServer(socketserver.UnixStreamServer):
    """The converter's socket and its one-at-a-time loop (serve_until_stopped). ``runner``: the function the bounded
    child runs on the safe package (default LibreOffice's; tests give a stand-in); ``group``: the socket's group, or
    None to keep it as made. Setting ``draining`` stops it: the conversion running finishes, the connections waiting are
    answered busy, and the loop returns once none is left."""
    request_queue_size = BACKLOG

    def __init__(self, path, *, runner=None, group=None, idle_seconds=IDLE_SECONDS):
        self.path, self.runner, self.draining, self.timeout = path, runner, False, idle_seconds
        self._idle, self._inode = False, None
        _clear_stale_socket(path)
        umask = os.umask(0o117)  # the socket is made 0660, never wider, even for an instant
        try:
            super().__init__(path, _Connection)
        finally:
            os.umask(umask)
        try:
            os.chmod(path, SOCKET_MODE)
            if group is not None and os.stat(path).st_gid != group:
                os.chown(path, -1, group)
            self._inode = os.stat(path).st_ino
        except OSError:
            self.server_close()
            raise

    def serve_until_stopped(self):
        while True:
            self._idle = False
            self.handle_request()
            if self.draining and self._idle:
                return

    def handle_timeout(self):
        self._idle = True

    def handle_error(self, request, client_address):
        log.error('converter: a connection failed (%s)', sys.exc_info()[0].__name__)

    def server_close(self):
        super().server_close()
        try:
            if self._inode is not None and os.lstat(self.path).st_ino == self._inode:
                os.unlink(self.path)
        except OSError:
            pass

    def serve_connection(self, sock):
        """One connection: read its request (by REQUEST_SECONDS), answer it (by ANSWER_SECONDS)."""
        deadline = time.monotonic() + REQUEST_SECONDS
        try:
            header = _read_header(sock, deadline)
        except (EOFError, TimeoutError, OSError, _Malformed) as exc:
            log.warning('converter: a request could not be read (%s)', type(exc).__name__)
            return
        op = header.get('op')
        if op == PING:
            self._answer(sock, {'status': OK, 'size': 0})
            return
        size, digest = header.get('size'), header.get('sha256')
        if op != CONVERT or type(size) is not int or not 0 < size <= MAX_REQUEST_BYTES \
                or not isinstance(digest, str) or not _SHA256.match(digest):
            log.warning('converter: refused a request it does not take (its operation, size or digest)')
            self._answer(sock, _error(REFUSED))
            return
        try:
            data = _receive(sock, size, deadline)
        except (EOFError, TimeoutError, OSError) as exc:
            log.warning('converter: a request ended before its Word file arrived (%s)', type(exc).__name__)
            return
        if hashlib.sha256(data).hexdigest() != digest:
            log.warning('converter: refused a Word file that does not match its digest')
            self._answer(sock, _error(REFUSED))
            return
        if self.draining:
            log.info('converter: busy (stopping)')
            self._answer(sock, _error(BUSY))
            return
        started = time.monotonic()
        try:
            pdf = docx_package.convert_in_child(data, runner=self.runner)
        except docx_package.ConversionBusy as exc:  # its checks ran out of time: busy, for a retry
            log.warning('converter: busy (%s)', exc)
            self._answer(sock, _error(BUSY))
            return
        except docx_package.ConversionRefused as exc:
            log.info('converter: refused a Word file (%s)', exc)
            self._answer(sock, _error(REFUSED))
            return
        except docx_package.ConversionFailed as exc:
            log.warning('converter: a conversion failed (%s)', exc)
            self._answer(sock, _error(FAILED))
            return
        except Exception as exc:  # noqa: BLE001 - one failed conversion never stops the service
            log.error('converter: a conversion failed unexpectedly (%s)', type(exc).__name__)
            self._answer(sock, _error(FAILED))
            return
        if len(pdf) > docx_package.MAX_PDF_BYTES:
            log.warning('converter: a conversion made a PDF over the limit (%d bytes)', len(pdf))
            self._answer(sock, _error(FAILED))
            return
        log.info('converter: converted %d bytes to a PDF of %d in %.1f s', size, len(pdf), time.monotonic() - started)
        self._answer(sock, {'status': OK, 'size': len(pdf), 'sha256': hashlib.sha256(pdf).hexdigest()}, pdf)

    def _answer(self, sock, header, body=b''):
        try:
            _send(sock, _frame(header, body), time.monotonic() + ANSWER_SECONDS)
        except (TimeoutError, OSError) as exc:
            log.warning('converter: an answer could not be sent (%s)', type(exc).__name__)


def _clear_stale_socket(path):
    """A socket a stopped converter left at ``path`` is removed; anything else there is refused, never removed."""
    try:
        found = os.lstat(path)
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(found.st_mode):
        raise RuntimeError('the converter socket path holds something that is not a socket')
    os.unlink(path)


def serve(path=SOCKET_PATH, *, group=SOCKET_GROUP, runner=None) -> int:
    """Serves at ``path`` until SIGTERM or SIGINT (then it drains: see ConverterServer). Main thread only."""
    server = ConverterServer(path, runner=runner, group=group)

    def stop(signum, frame):
        server.draining = True
    previous = {number: signal.signal(number, stop) for number in (signal.SIGTERM, signal.SIGINT)}
    log.info('converter: listening (one conversion at a time, up to %d waiting)', BACKLOG)
    try:
        server.serve_until_stopped()
    finally:
        server.server_close()
        for number, handler in previous.items():
            signal.signal(number, handler)
    log.info('converter: stopped')
    return 0


def self_test_docx() -> bytes:
    """The self-test's Word file (synthetic, the same bytes every time)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, content in _SELF_TEST_PARTS:
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 24, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content.encode('utf-8'))
    return buffer.getvalue()


def self_test(*, runner=None) -> int:
    """Converts self_test_docx() as a request would be converted, here (no socket): the PDF's size, or
    docx_package.ConversionRefused / ConversionBusy / ConversionFailed."""
    pdf = docx_package.convert_in_child(self_test_docx(), runner=runner)
    if not pdf.startswith(b'%PDF-'):
        raise docx_package.ConversionFailed('the conversion produced no PDF')
    return len(pdf)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='python -m studio.converter_server',
                                     description='The CPT Studio Word converter (one conversion at a time).')
    parser.add_argument('--socket', default=SOCKET_PATH, help='the socket to serve or ping (default %(default)s)')
    checks = parser.add_mutually_exclusive_group()
    checks.add_argument('--ping', action='store_true', help='exit 0 when the converter takes connections')
    checks.add_argument('--self-test', action='store_true', help='convert a Word file built in memory, here')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    if args.ping:
        try:
            state = ping(args.socket)
        except ConverterBusy as exc:
            print(f'cpt-studio converter: not taking connections ({exc})')
            return 1
        print(f'cpt-studio converter: {state}')
        return 0
    if args.self_test:
        try:
            size = self_test()
        except (docx_package.ConversionRefused, docx_package.ConversionBusy, docx_package.ConversionFailed) as exc:
            print(f'cpt-studio converter self-test: failed ({exc})')
            return 1
        print(f'cpt-studio converter self-test: ok, a PDF of {size} bytes')
        return 0
    return serve(args.socket, group=SOCKET_GROUP if args.socket == SOCKET_PATH else None)


if __name__ == '__main__':
    sys.exit(main())
