"""Corti's reads bounded by the time its send has left (HTTP-TRICKLE). Refutation round 1's repair R2 bounded every read
of the participants' sends (studio/participants/http.py); Corti's adapter (studio/providers/corti.py) had the same
defect: _read_capped checked the deadline only between 64 KiB chunks, and a read timeout bounds each wait for a byte,
never the whole read, so a response trickling in a byte at a time - its status line, a header or its body - held the
token or the coding exchange far past the send's deadline, and past the stale-stage sweep.

Demonstrated against loopback servers this test starts (127.0.0.1, ephemeral ports), through Corti's real default
session: its token and coding URLs are pointed at them, and nothing else is reached. The credentials file is synthetic.
A read the deadline cuts is unknown and its partial body is never taken for the answer; a coding request that never
left is not_sent; an answer that arrives in time is kept exactly as before (I1)."""
from __future__ import annotations

import hashlib
import json
import re
import socket
import tempfile
import threading
import time
from contextlib import nullcontext, suppress
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio.participants import http as participants_http
from studio.providers import CortiProvider
from studio.providers import corti as corti_module
from tests.test_providers import NOTE, SECRETS, SERVICE_DATE, TOKEN, dotenv, write_file

UNKNOWN = 'The outcome is unknown; reconcile it before any new attempt.'
DEADLINE = 'the deadline passed while the response was being read'
TOKEN_BODY = json.dumps({'access_token': TOKEN, 'token_type': 'Bearer', 'expires_in': 300}).encode()
# a Corti-shaped answer (no code, so nothing to normalize) with the usage Corti reports, padded so that trickled a byte
# every 0.25 s it takes about 20 s: twenty times the 1 s deadline the tests give the send
BODY = json.dumps({'codes': [], 'candidates': [], 'usageInfo': {'creditsConsumed': 0.0123},
                   'padding': 'x' * 21}).encode()


def head(body=None, *extra):
    """A 200 status line and headers; with ``body``, its Content-Length."""
    lines = [b'HTTP/1.1 200 OK', b'Content-Type: application/json', *extra]
    if body is not None:
        lines.append(b'Content-Length: %d' % len(body))
    return b'\r\n'.join(lines) + b'\r\n\r\n'


class Server:
    """A one-connection loopback server: it reads one request, sends ``head`` at once, then ``trickled`` one byte every
    ``every`` seconds - until it is done, the client goes away or the test ends - and then closes. ``received`` keeps
    every byte it was sent."""

    def __init__(self, case, head_bytes, trickled=b'', every=0.25):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(1)
        self.listener.settimeout(15)
        self.port = self.listener.getsockname()[1]
        self.received = bytearray()
        self.stop = threading.Event()
        self.head, self.trickled, self.every = head_bytes, trickled, every
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        case.addCleanup(self.close)

    def run(self):
        try:
            conn, _ = self.listener.accept()
        except OSError:
            return  # never contacted: the test ended
        with conn:
            conn.settimeout(15)
            try:
                data = b''
                while b'\r\n\r\n' not in data:
                    more = conn.recv(65536)
                    self.received.extend(more)
                    if not more:
                        return  # the client went away before its request was complete
                    data += more
                head_part, _, rest = data.partition(b'\r\n\r\n')
                length = int(re.search(rb'(?i)content-length: *([0-9]+)', head_part).group(1))
                while len(rest) < length:
                    more = conn.recv(65536)
                    self.received.extend(more)
                    if not more:
                        return
                    rest += more
                conn.sendall(self.head)
                for byte in self.trickled:
                    if self.stop.wait(self.every):
                        return
                    conn.sendall(bytes([byte]))
            except OSError:
                return  # the client went away

    def close(self):
        self.stop.set()
        with suppress(OSError):
            self.listener.shutdown(socket.SHUT_RDWR)  # wakes an accept() still waiting for a client
        self.listener.close()
        self.thread.join(15)


class CortiTrickleTests(SimpleTestCase):
    def setUp(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.credentials = write_file(tmp / 'corti.env', dotenv())

    def token_server(self, trickled=False):
        return Server(self, head(TOKEN_BODY), TOKEN_BODY) if trickled else Server(self, head(TOKEN_BODY) + TOKEN_BODY)

    def send(self, token, coding, deadline_s=1.0):
        """Corti's real send() through its default session, its token and coding URLs pointed at the two servers."""
        url = f'http://127.0.0.1:{coding.port}/v2/tools/coding/'
        provider = CortiProvider(self.credentials, connect_timeout=1, read_timeout=0.75)
        request = provider.build_request(NOTE, SERVICE_DATE)
        with mock.patch.object(corti_module, 'TOKEN_URL',
                               f'http://127.0.0.1:{token.port}/realms/{{tenant}}/protocol/openid-connect/token'), \
                mock.patch.object(corti_module, 'CODING_URL', url):
            started = time.monotonic()
            exchange = provider.send(request, deadline_s=deadline_s)
            elapsed = time.monotonic() - started
        text = repr(exchange)
        for secret in SECRETS:
            self.assertNotIn(secret, text)
        return exchange, elapsed, url

    def assertCutOffAtTheDeadline(self, exchange, elapsed, url, http_status):
        self.assertLess(elapsed, 2.5)  # the deadline is 1 s; the trickle alone takes about 20 s
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.response_bytes,
                          exchange.response_sha256, exchange.endpoint), ('unknown', True, http_status, None, '', url))
        self.assertIn(f'no complete response was read ({DEADLINE}). {UNKNOWN}', exchange.error)

    def test_a_coding_body_that_trickles_is_cut_off_at_the_deadline(self):
        self.assertCutOffAtTheDeadline(*self.send(self.token_server(), Server(self, head(BODY), BODY)), http_status=200)

    def test_a_coding_status_line_that_trickles_is_cut_off_at_the_deadline(self):
        coding = Server(self, b'', b'HTTP/1.1 200 OK\r\nX-Synthetic-Padding: ' + b'a' * 60
                        + b'\r\nContent-Length: 0\r\n\r\n')
        self.assertCutOffAtTheDeadline(*self.send(self.token_server(), coding), http_status=None)

    def test_coding_headers_that_trickle_are_cut_off_at_the_deadline(self):
        coding = Server(self, b'HTTP/1.1 200 OK\r\n',
                        b'X-Synthetic-Padding: ' + b'a' * 60 + b'\r\nContent-Length: 0\r\n\r\n')
        with self.assertLogs('urllib3.connection', level='WARNING') as logged:  # cut inside a header line
            # the status line arrived whole before the headers trickled, so the record states it, as for a body cut
            self.assertCutOffAtTheDeadline(*self.send(self.token_server(), coding), http_status=200)
        self.assertIn('Failed to parse headers', logged.output[0])

    def test_a_body_read_until_close_and_cut_off_is_never_taken_for_a_whole_answer(self):
        # no length: the body ends when the connection does, so the deadline's cut must never read as the end of it
        coding = Server(self, head(None, b'Connection: close'), BODY)
        self.assertCutOffAtTheDeadline(*self.send(self.token_server(), coding), http_status=200)

    def test_a_token_response_that_trickles_is_cut_off_and_no_coding_request_is_sent(self):
        padding = b'X-Synthetic-Padding: ' + b'a' * 60 + b'\r\n'
        unread = f'The Corti authentication response could not be read ({DEADLINE}); no coding request was sent.'
        cases = (('body', lambda: self.token_server(trickled=True), unread),
                 ('headers', lambda: Server(self, b'HTTP/1.1 200 OK\r\n', padding + b'\r\n'), unread),
                 ('status line', lambda: Server(self, b'', b'HTTP/1.1 200 OK\r\n' + padding + b'\r\n'),
                  f'Corti authentication failed ({DEADLINE}); no coding request was sent.'))
        for name, token, error in cases:
            with self.subTest(name):
                coding = Server(self, head(BODY) + BODY)
                # a cut inside a header line is also logged by urllib3
                with self.assertLogs('urllib3.connection', level='WARNING') if name == 'headers' else nullcontext():
                    exchange, elapsed, _ = self.send(token(), coding)
                self.assertLess(elapsed, 2.5)
                self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.response_bytes),
                                 ('not_sent', False, None, None))
                # the deadline's cut, never a token response read as one with no usable bearer token
                self.assertEqual(exchange.error, error)
                self.assertEqual(bytes(coding.received), b'')  # the coding service was never contacted

    def test_a_cut_read_is_never_taken_for_the_answer_even_where_the_chunk_check_does_not_see_the_deadline(self):
        # what keeps a partial body from being the answer is the watch's cut, not only the check after each chunk: with
        # Corti's own clock held at the send's start - the race where the deadline passes after a chunk's check - a
        # body read until close and cut at the deadline is still unknown, never a 200 answer of what had arrived
        start = time.monotonic()
        coding = Server(self, head(None, b'Connection: close'), BODY)
        with mock.patch.object(corti_module, 'monotonic', lambda: start):
            exchange, elapsed, url = self.send(self.token_server(), coding)
        self.assertCutOffAtTheDeadline(exchange, elapsed, url, http_status=200)

    def test_a_deadline_that_passes_while_connecting_to_the_coding_service_sends_nothing(self):
        # the watch is handed the socket once connected, before the request is written: past the deadline there, the
        # coding request never leaves, so the outcome is not_sent - never an unknown outcome a member must reconcile
        token, coding = self.token_server(), Server(self, head(BODY) + BODY)
        real = participants_http.HTTPConnection.connect

        def slow(connection):
            real(connection)
            if connection.port == coding.port:
                time.sleep(0.6)  # the connection (or its TLS handshake) took the time that was left
        with mock.patch.object(participants_http.HTTPConnection, 'connect', slow):
            exchange, elapsed, _ = self.send(token, coding, deadline_s=0.4)
        self.assertLess(elapsed, 2.5)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.endpoint, exchange.error),
                         ('not_sent', False, None, '',
                          'The deadline passed before the coding request was sent; nothing was sent.'))
        time.sleep(0.2)
        self.assertEqual(bytes(coding.received), b'')  # not a byte of the coding request reached the server
        self.assertTrue(bytes(token.received).startswith(b'POST /realms/'))  # control: the token request did

    def test_an_answer_that_arrives_in_time_is_kept_exactly(self):
        # control (I1): nothing is cut that arrives in time, and every recorded field is what it was
        coding = Server(self, head(BODY, b'X-Request-Id: req-synthetic-trickle') + BODY)
        exchange, elapsed, url = self.send(self.token_server(), coding, deadline_s=5.0)
        self.assertLess(elapsed, 2.5)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.response_bytes,
                          exchange.response_sha256, exchange.usage, exchange.usage_basis, exchange.provider_request_id,
                          exchange.error, exchange.endpoint, exchange.requested_model, exchange.returned_model,
                          exchange.response_id),
                         ('succeeded', True, 200, BODY, hashlib.sha256(BODY).hexdigest(), {'creditsConsumed': 0.0123},
                          'provider_reported_credits_not_usd', 'req-synthetic-trickle', '', url, '', '', ''))
        self.assertGreater(exchange.latency_ms, 0)
        request = CortiProvider(self.credentials).build_request(NOTE, SERVICE_DATE)
        self.assertTrue(bytes(coding.received).endswith(corti_module.canonical_body(request.body)))  # the bytes sent

    def test_the_default_session_watches_every_read_and_still_never_retries_or_redirects(self):
        session = corti_module.default_session()
        self.addCleanup(session.close)
        self.assertIs(session.trust_env, False)
        self.assertEqual(session.max_redirects, 0)
        for url in ('https://api.us.corti.app/v2/tools/coding/', 'https://auth.eu.corti.app/realms/x/token',
                    'http://127.0.0.1:9/'):
            adapter = session.get_adapter(url)
            self.assertIsInstance(adapter, participants_http._WatchedAdapter, url)
            self.assertEqual((adapter.max_retries.total, adapter.max_retries.read), (0, False), url)
