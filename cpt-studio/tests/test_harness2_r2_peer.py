"""Refutation round 2, R2-PEER: what a peer request shows, and how a participant's exchanges are recorded (HARNESS.md
12.4 and 12.7, as amended for the round's design decisions D4 and D5; I5, I8, I9, I10).

- FG2-3: a peer request shows Corti's units as the number of its entries, and CPT Studio's excluded codes with their
  reasons - pinned on a pipeline run whose Corti answer selects one code twice and whose assess #1 excludes one.
- sends-r2-1: a tool call whose arguments are missing or null is recorded with JSON null arguments, and the run is
  recorded whole (succeeded, every exchange and tool call kept), never unknown with nothing of it kept.
- sends-r2-2: a connection whose TCP connect or TLS handshake never completed wrote no byte of the request, so it is
  not_sent - a handshake stalled past the deadline or the connect timeout, a certificate the check refuses - while a
  request that was written and got no answer stays unknown; demonstrated against loopback servers (127.0.0.1, ephemeral
  ports) through the real default session, with a throwaway certificate made in memory.
- sends-r2-4: each exchange of a participant's tool loop and its tool calls are recorded as that exchange ends, so a
  worker that dies mid-loop leaves the exchanges before it recorded, and the stale sweep marks such a run sent.

Synthetic data only; nothing is sent. Corti is the harness@1 suite's in-process fake. Astra and Fable are the real
replay adapters on the real tool loop with scripted answers (tests.test_harness2_pipeline), their tool calls answered by
CPT Studio's real CMS tool executor over a synthetic reference store.
"""
import datetime
import ipaddress
import json
import os
import socket
import ssl
import tempfile
import threading
import time
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase
from django.utils import timezone

from studio import jobs, models
from studio.participants import http as participants_http
from studio.participants import openai_astra
from studio.participants.openai_astra import AstraParticipant
from tests.test_harness2_pipeline import (ASTRA_READING, CPT_STUDIO, FABLE_READING, HEAD, LAND, SNARE, ColonCase,
                                          Harness2Case, answered, asks, document_sections, facts_call, peer_document)
from tests.test_harness_pipeline import _WorkerDied
from tests.test_participants_support import NOTE, PAGES, openai_env, write_file
from tests.test_pipeline_api import drain

# --- FG2-3: Corti's units and CPT Studio's excluded codes, as a peer request shows them -------------------------------

SECOND_SNARE = 'A 7 mm sessile polyp in the descending colon was removed with a hot snare'
SURVEILLANCE = 'Plan: Surveillance colonoscopy in three years.'
TWO_SNARES = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
              'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
              'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
              + SECOND_SNARE + '.\n' + LAND + '\n' + SURVEILLANCE + '\n')


class PeerMaterialTests(ColonCase):
    """HARNESS.md 11.1, 12.4 and 12.7: Corti's selected codes 'with units as the number of its entries', and CPT
    Studio's held and excluded codes with their reasons. The earlier pins saw only one-entry Corti codes and an empty
    excluded list, so a peer shown units 1 and no excluded code at all stayed green (FG2-3)."""
    corti_codes = (('45385', SNARE), ('45385', SECOND_SNARE), ('45378', SURVEILLANCE), ('G0121', SURVEILLANCE))

    def test_corti_s_units_and_the_excluded_codes_are_shown_as_assess_one_recorded_them(self):
        encounter_id = self.create(TWO_SNARES)
        drain()
        first = self.assessments(encounter_id)[0]
        self.assertEqual((first.proposals.get(key='sel:0').code, first.proposals.get(key='sel:0').units), ('45385', 2))
        excluded = first.proposals.get(key='exc:0')
        self.assertEqual((excluded.code, excluded.status), ('G0121', 'excluded'))
        for name in ('astra', 'fable'):
            with self.subTest(name):
                run = self.runs_of(encounter_id, name, 'peer_review')[0]
                sections = document_sections(peer_document(name, run.request_body))
                corti = {item['code']: item for item in sections['corti (another coding system):']['codes']}
                self.assertEqual(corti['45385'], {'code': '45385', 'modifiers': [], 'units': 2,
                                                  'evidence': [SNARE, SECOND_SNARE]})
                self.assertEqual([corti[c]['units'] for c in ('45378', 'G0121')], [1, 1])
                self.assertEqual(sections[CPT_STUDIO]['excluded'],
                                 [{'code': 'G0121', 'key': 'exc:0', 'status': 'excluded',
                                   'reasons': ['HCPCS Level II code — CPT-only results.']}])
                self.assertEqual(sections[CPT_STUDIO]['excluded'][0]['reasons'],
                                 [c['detail'] for c in excluded.checks if c['status'] != 'pass'])


# --- sends-r2-1: a tool call with missing or null arguments is recorded whole -----------------------------------------

def without_key(data, key):
    """An answer asking for tool calls, each call's ``key`` ('arguments', 'input') removed."""
    envelope = json.loads(data)
    for item in envelope.get('output', envelope.get('content', [])):
        if item.get('type') in ('function_call', 'tool_use'):
            item.pop(key, None)
    return json.dumps(envelope).encode()


class NullArgumentsTests(Harness2Case):
    """HARNESS.md 11.2 and 12.1: every exchange is a recorded ProviderExchange and every tool call a ToolCall row; the
    loop answers arguments that are not a usable object with CPT Studio's own sentence and goes on (loop.NOT_AN_OBJECT).
    ToolCall.arguments is NOT NULL, and a Python None there was SQL NULL: the record failed, and the whole run - its
    final answer, its usage and every exchange - was recorded unknown with nothing kept, blocking the other participant
    (I8, I10), and a reconciliation sent the identical, already answered request again (sends-r2-1)."""

    def assertRecordedWhole(self, encounter_id, name, call_id, reading):
        run = self.runs_of(encounter_id, name, 'independent')[0]
        self.assertEqual((run.state, run.sent, run.error), ('succeeded', True, ''))
        self.assertEqual([(e.turn, e.state) for e in run.exchanges.order_by('turn')], [(1, 'succeeded'),
                                                                                       (2, 'succeeded')])
        call = models.ToolCall.objects.get(exchange__run=run)
        self.assertEqual((call.call_id, call.tool, call.arguments, call.result),
                         (call_id, 'cms_code_facts', None, {'error': 'The arguments are not a JSON object.'}))
        self.assertEqual(models.ToolCall.objects.filter(exchange__run=run, arguments=None).count(), 1)  # JSON null
        self.assertEqual(bytes(run.response_bytes), answered(name, reading))
        self.assertTrue(run.usage)
        for other in ('astra', 'fable'):
            self.assertEqual([r.state for r in self.runs_of(encounter_id, other, 'independent')], ['succeeded'])
            self.assertEqual([r.state for r in self.runs_of(encounter_id, other, 'peer_review')], ['succeeded'])
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')
        record = self.records(self.encounter(encounter_id).current_assessment)[name]
        self.assertEqual((record['state'], record['exchanges'], record['tool_calls']), ('read', 2, 1))

    def run_first(self, name, data, reading):
        self.adapters[name].first = [data, answered(name, reading)]
        encounter_id = self.create()
        drain()
        self.assertEqual([len(record['bodies']) for record in self.adapters[name].loops_of('first')], [2])
        return encounter_id

    def test_astra_arguments_null_are_recorded_as_json_null(self):
        encounter_id = self.run_first('astra', asks('astra', ('call_astra_null', 'cms_code_facts', 'null')),
                                      ASTRA_READING)
        self.assertRecordedWhole(encounter_id, 'astra', 'call_astra_null', ASTRA_READING)

    def test_astra_arguments_missing_are_recorded_as_json_null(self):
        data = without_key(asks('astra', ('call_astra_none', 'cms_code_facts', '{}')), 'arguments')
        encounter_id = self.run_first('astra', data, ASTRA_READING)
        self.assertRecordedWhole(encounter_id, 'astra', 'call_astra_none', ASTRA_READING)

    def test_fable_input_null_is_recorded_as_json_null(self):
        encounter_id = self.run_first('fable', asks('fable', ('toolu_fable_null', 'cms_code_facts', None)),
                                      FABLE_READING)
        self.assertRecordedWhole(encounter_id, 'fable', 'toolu_fable_null', FABLE_READING)

    def test_fable_input_missing_is_recorded_as_json_null(self):
        data = without_key(asks('fable', ('toolu_fable_none', 'cms_code_facts', {})), 'input')
        encounter_id = self.run_first('fable', data, FABLE_READING)
        self.assertRecordedWhole(encounter_id, 'fable', 'toolu_fable_none', FABLE_READING)

    def test_control_arguments_that_are_a_list_are_recorded_as_given(self):
        self.adapters['astra'].first = [asks('astra', ('call_astra_list', 'cms_code_facts', '["99213"]')),
                                        answered('astra', ASTRA_READING)]
        encounter_id = self.create()
        drain()
        run = self.runs_of(encounter_id, 'astra', 'independent')[0]
        self.assertEqual((run.state, run.exchanges.count()), ('succeeded', 2))
        call = models.ToolCall.objects.get(exchange__run=run)
        self.assertEqual((call.arguments, call.result), (['99213'], {'error': 'The arguments are not a JSON object.'}))


# --- sends-r2-2: a connection that was never established sent nothing -------------------------------------------------

def throwaway_tls_context():
    """A server-side TLS context with a throwaway self-signed certificate for 127.0.0.1 (synthetic, valid for one hour),
    which the default session's certificate check refuses. Its key is made here and handed to ssl through an anonymous
    memory file where the platform has one (never written to a disk), otherwise through a temporary directory removed at
    once."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'synthetic-throwaway.invalid')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), False)
            .sign(key, hashes.SHA256()))
    pem = (key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()) + cert.public_bytes(serialization.Encoding.PEM))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    if hasattr(os, 'memfd_create'):
        fd = os.memfd_create('synthetic-throwaway-tls')
        try:
            os.write(fd, pem)
            context.load_cert_chain(f'/proc/self/fd/{fd}')
        finally:
            os.close(fd)
    else:  # pragma: no cover - a platform without memfd_create
        with tempfile.TemporaryDirectory() as folder:
            path = write_file(Path(folder) / 'throwaway.pem', pem)
            context.load_cert_chain(str(path))
    return context


class LoopbackServer:
    """A one-connection server on 127.0.0.1 that keeps what it received. ``mode``: 'stall' reads the client's TLS hello
    and answers only a handshake record header whose body never comes; 'tls' completes the server side of a real TLS
    handshake with a throwaway certificate (``context``), keeping what it decrypts; 'http-stall' reads a plain HTTP
    request and never answers."""

    def __init__(self, case, mode, context=None):
        self.mode, self.context = mode, context
        self.received, self.decrypted = bytearray(), bytearray()
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(1)
        self.listener.settimeout(10)
        self.port = self.listener.getsockname()[1]
        self.stop = threading.Event()
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        case.addCleanup(thread.join, 10)
        case.addCleanup(self.stop.set)
        case.addCleanup(self.listener.close)

    def url(self, scheme='https'):
        return f'{scheme}://127.0.0.1:{self.port}/v1/responses'

    def run(self):
        try:
            conn, _ = self.listener.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(0.2)
            if self.mode == 'tls':
                conn.settimeout(10)
                try:
                    tls = self.context.wrap_socket(conn, server_side=True)
                    while data := tls.recv(65536):
                        self.decrypted.extend(data)
                except (OSError, ssl.SSLError):
                    return  # the client refused the certificate and aborted the handshake
                return
            answered = False
            while not self.stop.is_set():
                try:
                    data = conn.recv(65536)
                except socket.timeout:
                    continue
                except OSError:
                    return
                if not data:
                    return
                self.received.extend(data)
                if self.mode == 'stall' and not answered:
                    conn.sendall(b'\x16\x03\x03\x00\x7a')  # a handshake record header whose body never comes
                    answered = True

    @property
    def request_line_received(self):
        return b'POST ' in bytes(self.received) or bool(self.decrypted)


def closed_port():
    probe = socket.socket()
    probe.bind(('127.0.0.1', 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class NeverConnectedTests(SimpleTestCase):
    """HARNESS.md 8 and http.py's own rule: not_sent only while the request provably has not left - "a connection that
    was never established". A watched connection hands its socket to the exchange's watch once its TCP connect and TLS
    handshake completed, before any byte of the request is written, so one that never did sent nothing; urllib3 surfaces
    a handshake cut by the (clamped) connect timeout as a read timeout and a refused certificate as an SSL error, which
    were taken for failures after the request may have left (unknown): a member had to reconcile an attempt that never
    left, and while it stood unknown every other participant was held (I8, I10) (sends-r2-2)."""

    def post(self, url, *, deadline_s, connect_timeout, read_timeout=240):
        started = time.monotonic()
        exchange = participants_http.post(
            openai_astra.VENDOR, participants_http.default_session, url, b'{"model":"gpt-6-astra"}',
            {'Content-Type': 'application/json'}, deadline=started + deadline_s, connect_timeout=connect_timeout,
            read_timeout=read_timeout, max_response_bytes=1 << 20, requested_model=openai_astra.MODEL)
        return exchange, time.monotonic() - started

    def assertNotSent(self, exchange, error):
        self.assertEqual((exchange.outcome, exchange.sent, exchange.error, exchange.endpoint, exchange.http_status),
                         ('not_sent', False, error, '', None))
        self.assertEqual(exchange.requested_model, openai_astra.MODEL)

    def test_a_tls_handshake_the_deadline_cuts_sent_nothing(self):
        server = LoopbackServer(self, 'stall')
        exchange, elapsed = self.post(server.url(), deadline_s=1.0, connect_timeout=10)
        self.assertNotSent(exchange, 'The deadline passed before the request was sent; nothing was sent.')
        self.assertLess(elapsed, 3)
        self.assertEqual(bytes(server.received[:1]), b'\x16')  # the client's TLS hello reached it ...
        self.assertFalse(server.request_line_received)  # ... and not a byte of the request

    def test_a_tls_handshake_the_connect_timeout_cuts_sent_nothing(self):
        server = LoopbackServer(self, 'stall')
        exchange, elapsed = self.post(server.url(), deadline_s=30, connect_timeout=1.0)
        self.assertNotSent(exchange, 'OpenAI could not be reached (ReadTimeout); nothing was sent.')
        self.assertLess(elapsed, 5)
        self.assertEqual(bytes(server.received[:1]), b'\x16')
        self.assertFalse(server.request_line_received)

    def test_a_certificate_the_check_refuses_sent_nothing(self):
        server = LoopbackServer(self, 'tls', throwaway_tls_context())
        exchange, _ = self.post(server.url(), deadline_s=30, connect_timeout=10)
        self.assertNotSent(exchange, 'OpenAI could not be reached (SSLError); nothing was sent.')
        self.assertEqual(bytes(server.decrypted), b'')

    def test_control_a_refused_tcp_connection_stays_not_sent(self):
        exchange, _ = self.post(f'https://127.0.0.1:{closed_port()}/v1/responses', deadline_s=30, connect_timeout=10)
        self.assertNotSent(exchange, 'OpenAI could not be reached (ConnectionError); nothing was sent.')

    def test_control_a_request_written_and_never_answered_stays_unknown(self):
        server = LoopbackServer(self, 'http-stall')
        exchange, elapsed = self.post(server.url('http'), deadline_s=30, connect_timeout=10, read_timeout=1.0)
        self.assertEqual((exchange.outcome, exchange.sent), ('unknown', True))
        self.assertIn('The request may have reached OpenAI, but no complete response was read (ReadTimeout)',
                      exchange.error)
        self.assertLess(elapsed, 5)
        time.sleep(0.3)
        self.assertTrue(server.request_line_received)  # the request was written: it may have left

    def test_the_real_tool_loop_records_its_first_exchange_not_sent(self):
        server = LoopbackServer(self, 'stall')
        with tempfile.TemporaryDirectory() as folder:
            credentials = write_file(Path(folder) / 'openai.env', openai_env())
            adapter = AstraParticipant(credentials, connect_timeout=10)
            request = adapter.build_request(NOTE, PAGES, 'paste', None)
            with mock.patch.object(openai_astra, 'ENDPOINT', server.url()):
                outcome = adapter.send_loop(request, deadline_s=1.0, client_request_id='synthetic-run-0001',
                                            original_bytes=None, execute_tool=lambda name, arguments: ({}, []))
        self.assertEqual((outcome.final.outcome, outcome.final.sent), ('not_sent', False))
        self.assertEqual([(e.turn, e.outcome) for e in outcome.exchanges], [(1, 'not_sent')])
        self.assertFalse(server.request_line_received)


# --- sends-r2-4: every exchange is recorded as it ends ----------------------------------------------------------------

class RecordedAsItEndsTests(Harness2Case):
    """HARNESS.md 11.2 and 12.1: each exchange of the loop is a recorded ProviderExchange with its response bytes, usage
    and tool calls, and the run records whether it was sent. They were all written only once the whole loop had ended
    (_finish_loop), so a worker that died mid-loop - up to 540 s and 4 exchanges - left nothing of the exchanges that
    had been answered and paid for, and the stale sweep settled the run unknown with sent false (sends-r2-4)."""

    def dies_at_exchange_two(self):
        def dies(body):  # stands in for a SIGKILL or an OOM kill while exchange 2 is in flight
            raise _WorkerDied()
        self.adapters['astra'].first = [asks('astra', facts_call('call_astra_1', ['99213'])), dies]
        encounter_id = self.create()
        job = self.run_until('astra')
        with self.assertRaises(_WorkerDied):
            jobs.run_job(job)
        self.assertEqual(len(self.adapters['astra'].loops_of('first')[0]['bodies']), 2)  # exchange 2 was in flight
        return encounter_id, job

    def test_a_worker_that_dies_mid_loop_leaves_the_exchanges_before_it_recorded(self):
        encounter_id, job = self.dies_at_exchange_two()
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual(run.state, 'sending')
        self.assertEqual([(e.turn, e.state) for e in run.exchanges.all()], [(1, 'succeeded')])  # kept as it ended
        (exchange,) = run.exchanges.all()
        answer = asks('astra', facts_call('call_astra_1', ['99213']))
        self.assertEqual((exchange.turn, exchange.state, exchange.http_status, bytes(exchange.response_bytes)),
                         (1, 'succeeded', 200, answer))
        self.assertEqual(exchange.request_sha256, run.request_sha256)  # the run's own first request
        self.assertTrue(exchange.usage)
        (call,) = exchange.tool_calls.all()
        self.assertEqual((call.call_id, call.tool, call.arguments['codes']), ('call_astra_1', 'cms_code_facts',
                                                                              ['99213']))
        self.assertTrue(call.refs)
        # the stale sweep settles the run unknown - and sent, since an exchange of it reached the vendor
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))
        jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual((run.state, run.sent, run.error),
                         ('unknown', True, 'The worker stopped while the request was in flight.'))
        self.assertEqual([(e.turn, e.state) for e in run.exchanges.all()], [(1, 'succeeded')])
        self.assertEqual(models.ToolCall.objects.filter(exchange__run=run).count(), 1)
        self.assertEqual(models.Job.objects.get(pk=job.pk).state, 'unknown')
        # I8 as before: the unknown outcome blocks every further send until a member reconciles it
        drain()
        self.assertEqual(self.sent('fable', 'first'), 0)

    def test_control_a_run_swept_before_any_exchange_was_recorded_stays_not_sent(self):
        def dies(body):
            raise _WorkerDied()
        self.adapters['astra'].first = [dies]
        encounter_id = self.create()
        job = self.run_until('astra')
        with self.assertRaises(_WorkerDied):
            jobs.run_job(job)
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))
        jobs.mark_stale()
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((run.state, run.sent, run.exchanges.count()), ('unknown', False, 0))

    def test_a_finished_loop_records_each_exchange_once(self):
        self.adapters['astra'].first = [asks('astra', facts_call('call_astra_1', ['99213'])),
                                        asks('astra', facts_call('call_astra_2', ['99214']), number=2),
                                        answered('astra', ASTRA_READING)]
        recorded = []
        real = jobs._record_exchanges

        def spy(run, exchanges):
            recorded.append([record.turn for record in exchanges])
            return real(run, exchanges)
        with mock.patch('studio.jobs._record_exchanges', side_effect=spy):
            encounter_id = self.create()
            drain()
        run = self.runs_of(encounter_id, 'astra', 'independent')[0]
        self.assertEqual((run.state, [e.turn for e in run.exchanges.all()]), ('succeeded', [1, 2, 3]))
        self.assertEqual(models.ToolCall.objects.filter(exchange__run=run).count(), 2)
        # each as it ended, in its own transaction; the run's outcome then finds nothing more to record
        self.assertEqual(recorded[:4], [[1], [2], [3], []])

    def test_an_exchange_that_cannot_be_recorded_as_it_ends_is_recorded_with_the_outcome(self):
        real, calls = jobs._record_exchanges, []

        def fails_once(run, exchanges):
            calls.append([record.turn for record in exchanges])
            if len(calls) == 1:
                raise RuntimeError('synthetic')
            return real(run, exchanges)
        with mock.patch('studio.jobs._record_exchanges', side_effect=fails_once), \
                self.assertLogs('studio.jobs', level='ERROR') as logged:
            encounter_id = self.create()
            jobs.run_job(self.run_until('astra'))
        self.assertIn('exchange 1 of participant run', logged.output[0])
        run = self.runs_of(encounter_id, 'astra', 'independent')[0]
        self.assertEqual((run.state, run.sent, [e.turn for e in run.exchanges.all()]), ('succeeded', True, [1, 2]))
        self.assertEqual(calls, [[1], [2], [1]])
