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
- IR2-1, IR2-2, IR2-3 (D4): a peer request carries no person, no member-entered value and no other model's free text.
  No peer request body - as stored, and as handed to the adapter's send - holds any workspace member's label() or
  username after a reviewer's confirmation, any encounter.user_values value after a member's save, or a code string that
  is not a short token or free text of the other model; a save that changes only a member's value reuses both peer
  runs. Each test first shows that the record itself (the page's and the reports' wording) still carries what the peer
  request leaves out, so none of them passes on an input that never had it.

Synthetic data only; nothing is sent. Corti is the harness@1 suite's in-process fake. Astra and Fable are the real
replay adapters on the real tool loop with scripted answers (tests.test_harness2_pipeline), their tool calls answered by
CPT Studio's real CMS tool executor over a synthetic reference store.
"""
import datetime
import ipaddress
import json
import os
import re
import socket
import ssl
import tempfile
import threading
import time
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from studio import jobs, models
from studio.participants import http as participants_http
from studio.participants import loop, openai_astra, peer, prompt
from studio.participants.openai_astra import AstraParticipant
from studio.types import (EvidenceSpan, ExtractionIssue, LocatedQuote, ParticipantCode, ParticipantLesion,
                          ParticipantNotCoded, ParticipantQuestion, ParticipantReading, ParticipantService,
                          ReferenceUse, sha256_json)
from studio.validation import checks as validation_checks
from tests.legacy_chain import applied
from tests.test_harness2_pipeline import (ASTRA_READING, BIOPSY, CPT_STUDIO, EMPTY_PEER, FABLE_READING, HEAD, LAND,
                                          SNARE, TWO_EXTENTS, TWO_EXTENTS_INTERPRETATIONS, ColonCase, Harness2Case,
                                          answered, asks, document_sections, facts_call, peer_document, reading)
from tests.test_harness_pipeline import _WorkerDied
from tests.test_participants_support import (CLIENT_REQUEST_ID, FACTS_ARGUMENTS, NOTE, PAGES, PASSAGES_ARGUMENTS,
                                             FakeExecutor, FakeResponse, FakeSession, OfflineTestCase,
                                             astra_tool_call, code, empty_reading, fixture_bytes, openai_env, service,
                                             write_file)
from tests.test_pipeline_api import OFFICE_NOTE_STATE, RecordedInterpretation, drain

# --- FG2-3: Corti's units and CPT Studio's excluded codes, as a peer request shows them -------------------------------

SECOND_SNARE = 'A 7 mm sessile polyp in the descending colon was removed with a hot snare'
SURVEILLANCE = 'Plan: Surveillance colonoscopy in three years.'
TWO_SNARES = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
              'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
              'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
              + SECOND_SNARE + '.\n' + LAND + '\n' + SURVEILLANCE + '\n')


@applied
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


class NullArgumentsTests(RecordedInterpretation, Harness2Case):
    """HARNESS.md 11.2 and 12.1: every exchange is a recorded ProviderExchange and every tool call a ToolCall row; the
    loop answers arguments that are not a usable object with CPT Studio's own sentence and goes on (loop.NOT_AN_OBJECT).
    ToolCall.arguments is NOT NULL, and a Python None there was SQL NULL: the record failed, and the whole run - its
    final answer, its usage and every exchange - was recorded unknown with nothing kept, blocking the other participant
    (I8, I10), and a reconciliation sent the identical, already answered request again (sends-r2-1)."""
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads OFFICE_NOTE from its recorded synthetic
    # interpretation.

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
        self.assertEqual(self.encounter(encounter_id).state, OFFICE_NOTE_STATE)
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

@applied
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

    # Refutation round 3, falsegreen-5: the sweep's rule - a recorded exchange in any state but not_sent may have
    # reached the vendor - was pinned only for 'succeeded', so a sweep counting 'succeeded' alone stayed green while it
    # recorded a run the vendor answered with HTTP 529, or may have received, as never sent.

    def swept_after_its_only_exchange(self, step):
        """Astra's only exchange is ``step``, recorded as it ended; the worker dies once the loop has ended, before the
        run's outcome is recorded (_finish_loop); the stale sweep then settles the run. (state, sent, exchanges) before
        the sweep, and the run after it."""
        def dies(run, outcome):  # stands in for a SIGKILL between the exchange's record and the run's outcome
            raise _WorkerDied()
        self.adapters['astra'].first = [step]
        encounter_id = self.create()
        job = self.run_until('astra')
        with mock.patch('studio.jobs._finish_loop', side_effect=dies), self.assertRaises(_WorkerDied):
            jobs.run_job(job)
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        before = (run.state, run.sent, [(e.turn, e.state, e.http_status) for e in run.exchanges.all()])
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))
        jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual((run.error, models.Job.objects.get(pk=job.pk).state),
                         ('The worker stopped while the request was in flight.', 'unknown'))
        return before, run

    def test_a_recorded_http_529_answer_marks_the_swept_run_sent(self):
        from tests.test_harness2_pipeline import failed
        before, run = self.swept_after_its_only_exchange(failed())
        self.assertEqual(before, ('sending', False, [(1, 'failed', 529)]))
        self.assertEqual((run.state, run.sent), ('unknown', True))

    def test_a_recorded_unknown_exchange_marks_the_swept_run_sent(self):
        from tests.test_harness2_pipeline import unknown
        before, run = self.swept_after_its_only_exchange(unknown())
        self.assertEqual(before, ('sending', False, [(1, 'unknown', None)]))
        self.assertEqual((run.state, run.sent), ('unknown', True))

    def test_control_a_recorded_not_sent_exchange_leaves_the_swept_run_unsent(self):
        from studio.types import RawExchange
        refused = RawExchange(outcome='not_sent', sent=False,
                              error='Astra could not be reached (synthetic); nothing was sent.')
        before, run = self.swept_after_its_only_exchange(refused)
        self.assertEqual(before, ('sending', False, [(1, 'not_sent', None)]))
        self.assertEqual((run.state, run.sent), ('unknown', False))


class LoopRecordingTests(OfflineTestCase):
    """loop.recording, the hook the pipeline records each exchange through: every loop run hands the callback each
    exchange as it ends - its answer read and its tool calls answered - before the next exchange is sent, and a callback
    that raises changes nothing in the loop (offline: the real Astra adapter and loop over a fake session)."""

    def setUp(self):
        super().setUp()
        self.credentials = write_file(self.tmp / 'openai.env', openai_env())

    def run_loop(self):
        session = FakeSession(
            FakeResponse(200, astra_tool_call(('call_r1', 'cms_code_facts', FACTS_ARGUMENTS), number=1)),
            FakeResponse(200, astra_tool_call(('call_r2', 'cms_policy_passages', PASSAGES_ARGUMENTS), number=2)),
            FakeResponse(200, fixture_bytes('astra-colonoscopy.response.json')))
        self.session = session  # what was posted so far, as a callback sees it
        adapter = AstraParticipant(self.credentials, session_factory=lambda: session)
        request = adapter.build_request(NOTE, PAGES, 'paste', None)
        outcome = adapter.send_loop(request, deadline_s=540, client_request_id=CLIENT_REQUEST_ID, original_bytes=None,
                                    execute_tool=FakeExecutor())
        return outcome, session

    def test_each_exchange_is_handed_over_as_it_ends_before_the_next_is_sent(self):
        handed = []

        def on_exchange(record):
            handed.append((record.turn, record.outcome, [call.call_id for call in record.tool_calls],
                           len(self.session.calls)))
        with loop.recording(on_exchange):
            outcome, _ = self.run_loop()
        self.assertEqual(outcome.final.outcome, 'succeeded')
        # exchange N is handed over once its tool calls are answered, while only N requests have been posted
        self.assertEqual(handed, [(1, 'succeeded', ['call_r1'], 1), (2, 'succeeded', ['call_r2'], 2),
                                  (3, 'succeeded', [], 3)])
        handed.clear()
        self.run_loop()  # outside the block, nothing is handed over
        self.assertEqual(handed, [])

    def test_a_callback_that_raises_changes_nothing_in_the_loop(self):
        def shape(outcome):
            return (outcome.final.outcome, outcome.final.error,
                    [(record.turn, record.outcome, record.response_bytes,
                      [(call.call_id, call.result) for call in record.tool_calls]) for record in outcome.exchanges])
        plain, _ = self.run_loop()

        def broken(record):
            raise RuntimeError('synthetic')
        with loop.recording(broken):
            raised, session = self.run_loop()
        self.assertEqual(shape(raised), shape(plain))
        self.assertEqual(len(session.calls), 3)


# --- D4: what a peer request carries (IR2-1, IR2-2, IR2-3) ------------------------------------------------------------

def stored_bodies(case, encounter_id, runs=None):
    """Every peer run's stored request body as canonical text, with the bodies each adapter's loop handed to post()."""
    runs = case.runs_of(encounter_id, purpose='peer_review') if runs is None else runs
    return [json.dumps(run.request_body, ensure_ascii=False) for run in runs]


def posted_bodies(case, name):
    """Every body ``name``'s peer-review loops handed to post(), which a live adapter POSTs as canonical bytes."""
    return [json.dumps(body, ensure_ascii=False) for record in case.adapters[name].loops_of('peer')
            for body in record['bodies']]


def cpt_section(run):
    return document_sections(peer_document(run.provider, run.request_body))[CPT_STUDIO]


def phase_one(case, encounter_id):
    """The newest assess #1 of the encounter: the assessment the newest peer requests were built from."""
    return [a for a in case.assessments(encounter_id) if jobs.assessment_phase(a) == 1][-1]


class PeerMaterialCase(Harness2Case):
    """Every workspace member's identity, for the assertions that no peer request carries it."""

    def setUp(self):
        super().setUp()
        self.reviewer.display_name = 'Rowan Synthetic-Reviewer Zq'
        self.reviewer.username = 'rowan.r2peer.synthetic@example.invalid'
        self.reviewer.save()

    def identities(self):
        users = models.User.objects.filter(memberships__workspace=self.ws)
        return [value for user in users for value in (user.label(), user.get_username())]

    def confirm_row(self, encounter_id, question, value, passage):
        """A reviewer's confirmation as the confirmation endpoint records it (review.confirm_finding), of ``passage``
        located by Astra - made directly, so the test reads what any confirmation the engine reads makes of a peer
        request, whatever the candidates offer."""
        revision = self.encounter(encounter_id).current_revision
        start = revision.text.index(passage)
        return models.FindingConfirmation.objects.create(
            encounter_id=encounter_id, revision=revision, clarification=question, scope=question.scope,
            fact=question.fact, family=question.family,
            proposal_key=question.proposal.key if question.proposal_id else '', value=value,
            spans=[{'start': start, 'end': start + len(passage), 'text': passage, 'page': None}],
            located_by=['astra'], runs=[], confirmed_by=self.reviewer,
            attestation=f'I read this passage in the source document; it documents {value} for this encounter.')

    def assertCarriesNone(self, bodies, values):
        self.assertTrue(bodies)
        for value in values:
            self.assertEqual([value in body for body in bodies], [False] * len(bodies), value)


# IR2-1: a reviewer's confirmation is read by every later assessment of the revision, assess #1 included (12.7), and
# its wording names the reviewer: "confirmed from Astra's located passage by <reviewer>".

NEGATED = 'No ascending colon biopsy was submitted to pathology.'
DOUBTED = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
           'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
           'The colonoscope was advanced to the cecum and the examination was completed.\n'
           'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
           'It is unclear whether biopsies of the ascending colon lesion were taken.\n' + NEGATED + '\n')
TAKEN = 'Cold forceps biopsies of the ascending colon lesion were taken.'
PERFORMED = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
             'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
             'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
             'It is unclear whether biopsies of the ascending colon lesion were taken.\n' + TAKEN + '\n' + LAND + '\n')


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@applied
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class ReviewerIdentityTests(PeerMaterialCase):
    """HARNESS.md 3 and 11.1 list what a peer request holds, and no workspace member's identity is among it; 11.3: a
    reviewer's confirmation is never presented as a reading of CPT Studio's own. A later chain's assess #1 reads the
    revision's confirmations, and the proposal it decides words them "confirmed from Astra's located passage by
    <reviewer>" in its checks, which the peer request copied as CPT Studio's reasons: the reviewer's name, and the
    reviewer's attested conclusion filed under CPT Studio's rule-based reading, reached OpenAI and Anthropic (IR2-1)."""
    corti_codes = (('45385', SNARE), ('45380', 'biopsies of the ascending colon lesion were taken'))

    def setUp(self):
        super().setUp()
        self.adapters['astra'].first = [answered('astra', reading(
            codes=[('45385', SNARE)], services=[('c1', 'colonoscopy', 'performed', SNARE),
                                                ('c2', 'colonoscopy', 'not_performed', NEGATED)]))]
        self.adapters['fable'].first = [answered('fable', reading(codes=[('45385', SNARE)]))]
        for name in ('astra', 'fable'):
            self.adapters[name].peer = [answered(name, EMPTY_PEER, number=2)]

    def confirmed_chain(self, document, value, passage, save):
        """Chain 1 runs; a reviewer confirms 45380's performed_status as ``value`` from ``passage``; a member's save
        starts chain 2. (encounter id, the confirmation, chain 2's assess #1, chain 2's peer runs)."""
        encounter_id = self.create(document)
        drain()
        final = self.encounter(encounter_id).current_assessment
        question = final.clarifications.get(fact='performed_status', proposal__code='45380',
                                            state=models.Clarification.OPEN)
        confirmation = self.confirm_row(encounter_id, question, value, passage)
        before = len(self.runs_of(encounter_id, purpose='peer_review'))
        self.assertCarriesNone(stored_bodies(self, encounter_id), self.identities())  # chain 1 came before it
        response = self.post(f'/api/encounters/{encounter_id}/context', save)
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        chain2 = self.runs_of(encounter_id, purpose='peer_review')[before:]
        self.assertEqual([(run.provider, run.state, run.sent) for run in chain2],
                         [('astra', 'succeeded', True), ('fable', 'succeeded', True)])
        first = phase_one(self, encounter_id)
        item = first.proposals.get(code='45380')
        # the record itself words the confirmation with the reviewer's name, as the page and the reports do ...
        self.assertEqual(item.support.get('confirmed'), [str(confirmation.pk)])
        self.assertTrue(any(self.reviewer.label() in str(check.get('detail')) for check in item.checks))
        return encounter_id, confirmation, first, chain2

    def assertNoIdentity(self, encounter_id, chain2, code, bucket):
        # ... and no peer request carries any member's identity, nor the confirmation's wording as CPT Studio's own
        self.assertCarriesNone(stored_bodies(self, encounter_id, chain2), self.identities())
        for name in ('astra', 'fable'):
            self.assertCarriesNone(posted_bodies(self, name), self.identities())
        for run in chain2:
            shown = {item['code']: item for item in cpt_section(run)[bucket]}
            self.assertEqual(shown[code]['reasons'], [jobs.PEER_CONFIRMED_REASON])
            self.assertNotIn('located passage by', json.dumps(run.request_body, ensure_ascii=False))

    def test_a_not_performed_confirmation_names_no_one_in_a_later_peer_request(self):
        encounter_id, _, first, chain2 = self.confirmed_chain(DOUBTED, 'not performed', NEGATED,
                                                               {'billing_context': 'professional'})
        self.assertEqual(first.proposals.get(code='45380').status, 'excluded')
        self.assertNoIdentity(encounter_id, chain2, '45380', 'excluded')

    def test_a_performed_confirmation_of_a_code_still_held_names_no_one(self):
        encounter_id, _, first, chain2 = self.confirmed_chain(PERFORMED, 'performed', TAKEN, {'setting': 'asc'})
        self.assertEqual(first.proposals.get(code='45380').status, 'needs_clarification')  # held on its extent
        self.assertNoIdentity(encounter_id, chain2, '45380', 'held')

    def test_the_username_a_label_falls_back_to_is_never_carried_either(self):
        self.reviewer.display_name = ''
        self.reviewer.save()
        self.assertEqual(self.reviewer.label(), 'rowan.r2peer.synthetic@example.invalid')
        encounter_id, _, _, chain2 = self.confirmed_chain(DOUBTED, 'not performed', NEGATED,
                                                          {'billing_context': 'facility'})
        self.assertNoIdentity(encounter_id, chain2, '45380', 'excluded')

    def test_a_proposal_that_words_a_confirmation_in_any_check_is_held_fail_closed(self):
        # whichever check carries it: support['confirmed'], a check of the confirmation source, or its heading
        held = [{'id': 'service.status', 'status': 'pass', 'detail': 'Performed.',
                 'source': validation_checks.CONFIRMATION_SOURCE},
                {'id': 'facts.required', 'status': 'warn', 'source': 'cpt-studio:x@1',
                 'detail': f'Not documented: extent. {validation_checks.CONFIRMED_HEADING}: extent = cecum, '
                           'confirmed from Astra\'s located passage by Rowan Synthetic-Reviewer Zq ("x").'}]
        other = [{'id': 'a', 'status': 'warn', 'detail': 'Any.', 'source': ''}]
        for checks, support in ((held, {}), (held[1:], {}), (other, {'confirmed': ['c']})):
            with self.subTest(support=support, ids=[c['id'] for c in checks]):
                proposal = models.Proposal(key='sel:0', code='45380', status='needs_clarification', checks=checks,
                                           support=support)
                self.assertEqual(jobs._peer_reasons(proposal, ''), [jobs.PEER_CONFIRMED_REASON])
        control = models.Proposal(key='sel:0', code='45380', status='needs_clarification', support={},
                                  checks=[{'id': 'a', 'status': 'warn', 'detail': 'Any.', 'source': ''},
                                          {'id': 'b', 'status': 'pass', 'detail': 'Passed.', 'source': ''}])
        self.assertEqual(jobs._peer_reasons(control, ''), ['Any.'])


# IR2-2: a member's encounter metadata - a setting, a service date - and a member conflict's value.

FOLLOW = 'Follow-up of chronic constipation.'
NO_SETTING = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n\n'
              'Riverbend Digestive Health (fictional)\nDate of service: 2026-10-20\n'
              'Patient status: Established patient, last seen 2026-03-02.\n\n'
              'Chief complaint\n' + FOLLOW + '\n\n'
              'Assessment and plan\nChronic idiopathic constipation, improved. Continue polyethylene glycol daily.\n')
OFFICE = NO_SETTING.replace('Date of service: 2026-10-20\n', 'Date of service: 2026-10-20\nPlace of service: Office\n')
NO_DATE = (HEAD + 'Colonoscopy report (fictional)\nPlace of service: Ambulatory surgery center\n'
           'Procedure: Colonoscopy\nA 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
           + LAND + '\n')
MEMBER_DATE = '2019-03-04'  # before every installed release, so the reference checks would print it


@applied
class MemberValueTests(PeerMaterialCase):
    """HARNESS.md 3: "No title, filename, member-entered date, setting or billing context" is sent, and 2: a context
    change reuses the participants' requests. A held proposal's facts.required detail lists what a member entered
    (checks.MEMBER_ENTERED: "place of service = telehealth"), a member conflict's question quotes the member's value,
    and a reference check prints a member's service date - and each reached both vendors in phase 2, every save of a
    value making two new, paid peer sends (IR2-2)."""
    corti_codes = (('99213', FOLLOW),)

    def setUp(self):
        super().setUp()
        for name in ('astra', 'fable'):
            self.adapters[name].first = [answered(name, reading(codes=[('99213', FOLLOW)]))]
            self.adapters[name].peer = [answered(name, EMPTY_PEER, number=2)]

    def saved(self, encounter_id, values):
        before = len(self.runs_of(encounter_id, purpose='peer_review'))
        response = self.post(f'/api/encounters/{encounter_id}/context', values)
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        return self.runs_of(encounter_id, purpose='peer_review')[before:]

    def member_values(self, encounter_id):
        values = list(self.encounter(encounter_id).user_values.values())
        self.assertTrue(values)
        return values

    def test_a_member_entered_setting_reaches_no_peer_request_and_a_value_only_change_reuses_them(self):
        encounter_id = self.create(NO_SETTING)
        drain()
        chain2 = self.saved(encounter_id, {'setting': 'telehealth'})
        self.assertEqual([(run.provider, run.sent) for run in chain2], [('astra', True), ('fable', True)])
        held = phase_one(self, encounter_id).proposals.get(code='99213')
        facts = next(check['detail'] for check in held.checks if check['id'] == 'facts.required')
        self.assertIn(f'{validation_checks.MEMBER_ENTERED}: place of service = telehealth.', facts)  # the record's
        self.assertCarriesNone(stored_bodies(self, encounter_id, chain2), self.member_values(encounter_id))
        for name in ('astra', 'fable'):
            self.assertCarriesNone(posted_bodies(self, name), [validation_checks.MEMBER_ENTERED, '= telehealth'])
        for run in chain2:
            (shown,) = cpt_section(run)['held']
            self.assertIn(facts[:facts.index(validation_checks.MEMBER_ENTERED)].rstrip(), shown['reasons'])
        # a save that changes only the member's value makes the identical peer requests: reused, nothing sent
        posted = [len(posted_bodies(self, name)) for name in ('astra', 'fable')]
        chain3 = self.saved(encounter_id, {'setting': 'office'})
        self.assertEqual([(run.provider, run.sent, run.reused_from_id) for run in chain3],
                         [('astra', False, chain2[0].pk), ('fable', False, chain2[1].pk)])
        self.assertEqual([run.request_sha256 for run in chain3], [run.request_sha256 for run in chain2])
        self.assertEqual([len(posted_bodies(self, name)) for name in ('astra', 'fable')], posted)

    def test_a_member_conflict_s_value_reaches_no_peer_request(self):
        encounter_id = self.create(OFFICE)
        drain()
        chain2 = self.saved(encounter_id, {'setting': 'telehealth'})
        asked = phase_one(self, encounter_id).clarifications.get(fact='setting', state=models.Clarification.OPEN)
        self.assertIn('gives telehealth', asked.reason)  # the record's own words keep both sides
        self.assertCarriesNone(stored_bodies(self, encounter_id, chain2), self.member_values(encounter_id))
        for name in ('astra', 'fable'):
            self.assertCarriesNone(posted_bodies(self, name), self.member_values(encounter_id))
        for run in chain2:
            (question,) = [q for q in cpt_section(run)['open_questions'] if q['fact'] == 'setting']
            self.assertEqual(question['reason'], 'The place of service is in conflict. ' + jobs.PEER_MEMBER_CONFLICT)
            self.assertEqual(question['question'], asked.question)

    def test_a_member_entered_service_date_reaches_no_peer_request(self):
        self.corti.selections = [('45385', SNARE)]
        for name in ('astra', 'fable'):
            self.adapters[name].first = [answered(name, reading(codes=[('45385', SNARE)]))]
        encounter_id = self.create(NO_DATE)
        drain()
        chain2 = self.saved(encounter_id, {'service_date': MEMBER_DATE})
        held = phase_one(self, encounter_id).proposals.get(code='45385')
        self.assertEqual(held.status, 'needs_clarification')  # held on its extent
        printed = [check['detail'] for check in held.checks if MEMBER_DATE in check['detail']]
        self.assertTrue(printed)  # the record's reference checks print the date
        self.assertCarriesNone(stored_bodies(self, encounter_id, chain2), self.member_values(encounter_id))
        for name in ('astra', 'fable'):
            self.assertCarriesNone(posted_bodies(self, name), self.member_values(encounter_id))
        for run in chain2:
            (shown,) = cpt_section(run)['held']
            for detail in printed:
                self.assertIn(detail.replace(MEMBER_DATE, jobs.PEER_MEMBER_DATE), shown['reasons'])


# IR2-3: the other model's reading and Corti's codes, as a peer request shows them.

LONG_CODE = '45385 SYNTHETIC-PLACEHOLDER; with removal of lesion(s) by PLACEHOLDER technique'
LONG_BASIS = 'SYNTHETIC-PLACEHOLDER colonoscopy; with biopsy, single or multiple (synthetic wording)'
CORTI_LONG = '45380 SYNTHETIC-CORTI-PLACEHOLDER; with biopsy, single or multiple'
PAGE_RULE = re.compile(r'\((?:s|es|ies)\)|;\s*(?:with|without|diagnostic|including|each|single|multiple|first|'
                       r'initial)\b|\bsingle or multiple\b|\bwhen performed\b', re.I)  # app.js DESCRIPTOR_LIKE
WORDS = {field: f'Free-text-{field} of the other model (synthetic)' for field in (
    'description', 'anatomy', 'extent', 'technique', 'provider_role', 'site', 'size', 'morphology', 'action',
    'specimen', 'basis', 'question', 'why', 'issue', 'use')}
UNLOCATED = 'A quote the other model wrote that the document does not hold (synthetic).'
CITED_REF = 'a reference the other model cited and never retrieved (synthetic)'
NOT_CODED_LONG = '45378 SYNTHETIC-PLACEHOLDER; diagnostic, including collection of specimen(s)'
LESION_FIELDS = ('site', 'size', 'morphology', 'action', 'specimen')  # the reading schema's (prompt.SCHEMA)


def worded_reading():
    """Astra's first reading with every text field it may write filled with its own words."""
    return empty_reading(
        date_of_service={'value': '2026-10-14', 'evidence': ['Date of service: 2026-10-14', UNLOCATED]},
        services=[service(1, id='c1', family='colonoscopy', status='performed', evidence=[SNARE, UNLOCATED],
                          **{key: WORDS[key] for key in ('description', 'anatomy', 'extent', 'technique',
                                                           'provider_role')},
                          lesions=[{key: WORDS[key] for key in LESION_FIELDS}])],
        codes=[code('45385', service_ids=['c1'], evidence=[SNARE], basis=WORDS['basis']),
               code(LONG_CODE, service_ids=[], evidence=[SNARE]),
               code('45380', service_ids=[], evidence=[BIOPSY], basis=LONG_BASIS)],
        not_coded=[{'service_ids': ['c1'], 'code': NOT_CODED_LONG, 'reason': 'other', 'evidence': [UNLOCATED]}],
        clarifications=[{'question': WORDS['question'], 'why': WORDS['why'], 'service_ids': ['c1'],
                         'evidence': [LAND]}],
        extraction_issues=[{'page': 1, 'issue': WORDS['issue']}],
        references_used=[{'ref': CITED_REF, 'use': WORDS['use']}])


class OtherModelTests(RecordedInterpretation, PeerMaterialCase):
    """I9: no CPT descriptor text sent or displayed; 11.1 and 12.7: never Corti's display text. The engine refuses to
    list a code over 10 characters, the trace names one by its length and the page withholds descriptor-like text, yet a
    peer request relayed the other model's reading as written (prompt.reading_answer) - a long code, a basis, every free
    text and unlocated quote - and any code string Corti selected, to the other vendor (IR2-3)."""
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads every document the class uploads from its
    # recorded synthetic interpretation.
    interpretations = TWO_EXTENTS_INTERPRETATIONS
    corti_codes = (('45385', SNARE), ('45380', BIOPSY), (CORTI_LONG, BIOPSY))

    def setUp(self):
        super().setUp()
        self.adapters['astra'].first = [answered('astra', worded_reading())]
        self.adapters['fable'].first = [answered('fable', reading(codes=[('45385', SNARE)]))]
        for name in ('astra', 'fable'):
            self.adapters[name].peer = [answered(name, EMPTY_PEER, number=2)]

    def test_the_other_model_s_own_wording_and_long_codes_reach_no_other_vendor(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        astra = jobs.participant_reading(self.runs_of(encounter_id, 'astra', 'independent')[0])[0]
        self.assertIn(LONG_CODE, [item.code for item in astra.codes])  # the record keeps what Astra wrote
        fable_peer = self.runs_of(encounter_id, 'fable', 'peer_review')[0]
        astra_peer = self.runs_of(encounter_id, 'astra', 'peer_review')[0]
        withheld = [LONG_CODE, LONG_BASIS, CORTI_LONG, NOT_CODED_LONG, UNLOCATED, CITED_REF, *WORDS.values()]
        self.assertCarriesNone(stored_bodies(self, encounter_id, [fable_peer]) + posted_bodies(self, 'fable'),
                               withheld)
        for body in stored_bodies(self, encounter_id, [fable_peer]) + posted_bodies(self, 'fable'):
            shown = json.loads(body)
            text = json.dumps(shown.get('messages') or shown.get('input'), ensure_ascii=False)
            self.assertEqual(sorted({m.group(0) for m in PAGE_RULE.finditer(text)}), [])
        # Corti's code string reaches neither vendor; Astra's own reading is its own, and it is shown to itself
        self.assertCarriesNone(stored_bodies(self, encounter_id, [astra_peer]) + posted_bodies(self, 'astra'),
                               [CORTI_LONG])
        self.assertIn(json.dumps(LONG_CODE, ensure_ascii=False)[1:-1], stored_bodies(self, encounter_id,
                                                                                     [astra_peer])[0])
        sections = document_sections(peer_document('fable', fable_peer.request_body))
        shown = sections['astra (another model):']
        self.assertEqual(shown, peer.shown_reading(astra))
        self.assertEqual([item['code'] for item in shown['codes']],
                         ['45385', f'a value of {len(LONG_CODE)} characters (not shown)', '45380'])
        self.assertEqual(shown['codes'][0]['evidence'], [SNARE])  # a located quote is the document's own text
        self.assertEqual(shown['services'][0]['evidence'],
                         [SNARE, f'a value of {len(UNLOCATED)} characters (not shown)'])
        corti = [item['code'] for item in sections['corti (another coding system):']['codes']]
        self.assertEqual(corti, ['45385', '45380', f'a value of {len(CORTI_LONG)} characters (not shown)'])
        # the frozen list still names the reading itself, from which what is shown is made
        record = self.records(self.assessments(encounter_id)[0])['astra']
        listed = dict(prompt.peer_document_inputs(peer_document('fable', fable_peer.request_body))[1])
        self.assertEqual(listed['astra'], record['reading_sha256'])
        self.assertNotEqual(listed['astra'], sha256_json(shown))


class ShownReadingTests(SimpleTestCase):
    """peer.shown_reading, pure: the reading schema's shape, with only what is not the model's own wording, as
    written."""

    def test_only_tokens_located_quotes_retrieved_refs_and_recorded_values_are_shown_as_written(self):
        located = LocatedQuote(quote='was removed  with a hot snare',
                               spans=(EvidenceSpan(context_index=0, start=0, end=28, text=SNARE, exact=True),))
        lost = LocatedQuote(quote=UNLOCATED, reason='not found')
        reading_ = ParticipantReading(
            provider='astra', adapter_version='synthetic@1', reading_version=prompt.READING_VERSION,
            requested_model='gpt-6-astra', returned_model='gpt-6-astra', date_of_service='2026-10-14',
            date_evidence=(located, lost),
            services=(ParticipantService(id='c1', family='colonoscopy', status='performed', description='D',
                                         anatomy='Anatomy words', extent='', technique='Hot snare',
                                         lesions=(ParticipantLesion('Sigmoid', '9 mm', 'pedunculated', 'removed',
                                                                    'retrieved'),),
                                         provider_role='endoscopist', evidence=(located,)),
                      ParticipantService(id='a service id with spaces', family='other_gi', status='unclear',
                                         description='', anatomy='', extent='', technique='')),
            codes=(ParticipantCode(code='45385', modifiers=('XS', 'a modifier with words'), units=2,
                                   service_ids=('c1',), basis='Its basis.', evidence=(located, lost),
                                   confidence='high'),),
            not_coded=(ParticipantNotCoded(service_ids=('c1',), code='', reason='other', evidence=(lost,)),),
            questions=(ParticipantQuestion(question='Was it?', why='Because.', service_ids=('c1',), evidence=()),),
            extraction_issues=(ExtractionIssue(page=2, issue='Smudged.'),),
            references_used=(ReferenceUse(ref='fact:cms-pfs-rvu26d:45385:status', use='Payable.', retrieved=True),
                             ReferenceUse(ref='rule-01', use='Cited.', retrieved=False),
                             ReferenceUse(ref=CITED_REF, use='', retrieved=False)))

        def length(text):
            return f'a value of {len(text)} character{"" if len(text) == 1 else "s"} (not shown)'
        shown = peer.shown_reading(reading_)
        self.assertEqual(set(shown), set(prompt.reading_answer(reading_)))
        self.assertEqual(shown['date_of_service'], {'value': '2026-10-14',
                                                    'evidence': ['was removed  with a hot snare', length(UNLOCATED)]})
        self.assertEqual(shown['services'][0], {
            'id': 'c1', 'family': 'colonoscopy', 'status': 'performed', 'description': length('D'),
            'anatomy': length('Anatomy words'), 'extent': '', 'technique': length('Hot snare'),
            'lesions': [{'site': length('Sigmoid'), 'size': length('9 mm'), 'morphology': length('pedunculated'),
                         'action': length('removed'), 'specimen': length('retrieved')}],
            'provider_role': length('endoscopist'), 'evidence': ['was removed  with a hot snare']})
        # moved by refutation round 3 (peer-1): an id that is not letters and digits up to 8 is withheld under a name of
        # CPT Studio's own, the same wherever the request mentions it (peer.ShownIds); it was 'a value of 24 characters
        # (not shown)', which two withheld ids of one length shared
        self.assertEqual(shown['services'][1]['id'], 'id 1: a value of 24 characters (not shown)')  # 'a service id ...'
        self.assertEqual(len('a service id with spaces'), 24)
        self.assertEqual(shown['codes'], [{'code': '45385', 'modifiers': ['XS', 'a value of 21 characters (not shown)'],
                                           'units': 2, 'service_ids': ['c1'], 'basis': length('Its basis.'),
                                           'evidence': ['was removed  with a hot snare', length(UNLOCATED)],
                                           'confidence': 'high'}])
        self.assertEqual(shown['not_coded'], [{'service_ids': ['c1'], 'code': '', 'reason': 'other',
                                               'evidence': [length(UNLOCATED)]}])
        self.assertEqual(shown['clarifications'], [{'question': length('Was it?'), 'why': length('Because.'),
                                                    'service_ids': ['c1'], 'evidence': []}])
        self.assertEqual(shown['extraction_issues'], [{'page': 2, 'issue': length('Smudged.')}])
        self.assertEqual(shown['references_used'], [
            {'ref': 'fact:cms-pfs-rvu26d:45385:status', 'use': length('Payable.')},
            {'ref': 'a value of 7 characters (not shown)', 'use': length('Cited.')},  # moved by round 3 (peer-1):
            # a ref never retrieved is shown as given only when it is letters and digits up to 8 (peer.shown_ref);
            # 'rule-01' passed the 20-character token rule
            {'ref': f'a value of {len(CITED_REF)} characters (not shown)', 'use': ''}])
