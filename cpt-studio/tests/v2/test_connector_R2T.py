"""The interpreter's connector under DECISIONS D294's connector rulings (repair round r2; the connector lens's refutation
CONN-RF-3 and CONN-RF-5). TEXT-ONLY and SYNTHETIC: the answer streams are tests/v2/test_fable_adapter's constructed ones
over its synthetic note, and tests/v2/test_jobs' synthetic NOTE; every send goes to a fake session behind the network
guard of tests/test_participants_support, or to a loopback server on 127.0.0.1 behind tests/v2/test_fable_adapter's
loopback guard; every key is fake and nothing is sent anywhere. Each rule is tested on inputs it must change and on a
boundary it must leave alone:

- CONN-RF-3 (studio/participants/http.py): kept bytes that already end with the stream's end event are classified as
  the whole stream they are - whatever stopped the read (a connection reset after message_stop, a deadline that passed
  once it was read, a chunked body whose terminating chunk comes late) - and only bytes short of it are UNKNOWN; so the
  stage reads such an answer and the reconcile path (P-6) settles from the connector's record of it, never paying for it
  again (R2TKeptBytesTests, R2TKeptBytesLoopbackTests, R2TConnectorJobsTests);
- CONN-RF-5 (studio/interpretation/fable_adapter.py): a stream whose message_delta carries no usage has no final usage -
  describe records none, so the run is unpriced in the report (and the harness counts it at its bound) and is never
  priced at its message_start count (R2TFinalUsageTests, R2TConnectorJobsTests).
"""
from __future__ import annotations

import json
import time
from unittest import mock

import requests
from django.test import SimpleTestCase
from django.utils import timezone

from studio import interpretation, jobs, models, review
from studio.interpretation import fable_adapter
from studio.interpretation import report as release_report
from studio.participants import http as participants_http
from tests.test_participants_support import FakeResponse, FakeSession, OfflineMixin, OfflineTestCase, anthropic_env, \
    write_file
from tests.v2 import test_fable_adapter as fa
from tests.v2 import test_jobs as tj

Run, Job = models.ProviderRun, models.Job
RESET = 'synthetic: the connection was reset'


def without_delta_usage(delta_usage, text=None) -> bytes:
    """A whole answer stream whose message_delta's usage is ``delta_usage`` (``...``: no usage key at all)."""
    events = fa.answer_events(fa.pass_1_answer() if text is None else text)
    for event in events:
        if event.get('type') == 'message_delta':
            if delta_usage is ...:
                event.pop('usage')
            else:
                event['usage'] = delta_usage
    return fa.sse(*events)


class R2TKeptBytesTests(fa.SendCase):
    """D294 (CONN-RF-3) over fake sessions, live through the interpreter: bytes kept from a read that stopped early are
    the whole stream when they already end with its end event; only bytes short of it are UNKNOWN."""

    def send(self, response, **options):
        session = FakeSession(response)
        return self.interpreter(session, **options).send_loop(self.extraction(), deadline_s=60), session

    def assertWhole(self, outcome, raw, usage=fa.FINAL_USAGE):
        final = outcome.final
        self.assertEqual((final.outcome, final.sent, final.http_status, final.response_bytes, final.usage,
                          final.usage_basis, final.error, final.returned_model, final.response_id,
                          final.provider_request_id),
                         ('succeeded', True, 200, raw, usage, 'provider_reported_tokens' if usage else '', '',
                          fa.MODEL, fa.MESSAGE_ID, fa.REQUEST_ID))
        [record] = outcome.exchanges
        self.assertEqual((record.outcome, record.response_bytes, record.usage), ('succeeded', raw, usage))
        self.assertNoSecrets(final)

    def test_a_reset_after_the_end_event_keeps_the_whole_stream(self):
        raw = fa.answer_stream(fa.pass_1_answer())
        for error in (requests.exceptions.ChunkedEncodingError(RESET), requests.exceptions.ConnectionError(RESET)):
            with self.subTest(error=type(error).__name__):
                response = FakeResponse(200, chunks=[raw[:300], raw[300:], error, b'never read'],
                                        headers={'request-id': fa.REQUEST_ID})
                outcome, _ = self.send(response)
                self.assertWhole(outcome, raw)
                verdict = fable_adapter.classify(outcome.final.outcome, outcome.final.http_status,
                                                 outcome.final.response_bytes)
                self.assertEqual(verdict.kind, fable_adapter.ANSWERED)
                self.assertTrue(response.closed)

    def test_a_stream_ended_by_an_error_event_then_reset_is_that_whole_stream(self):
        """An error event is the stream's end too: the kept bytes are classified by it (an overload: FAILED, retry
        later), with no usage - never an UNKNOWN outcome left for a reconcile."""
        raw = fa.sse(fa.start(), fa.error_event('overloaded_error'))
        outcome, _ = self.send(FakeResponse(200, chunks=[raw, requests.exceptions.ChunkedEncodingError(RESET)],
                                            headers={'request-id': fa.REQUEST_ID}))
        self.assertWhole(outcome, raw, usage={})
        verdict = fable_adapter.classify(outcome.final.outcome, outcome.final.http_status, outcome.final.response_bytes)
        self.assertEqual((verdict.kind, fable_adapter.word(verdict.kind, verdict)), ('failed', 'retry later'))

    def test_a_deadline_that_passes_once_the_end_event_is_read_keeps_the_whole_stream(self):
        events = fa.answer_events(fa.pass_1_answer())
        first, rest = fa.sse(*events[:6]), fa.sse(*events[6:])

        def late():
            self.clock.advance(120)  # the deadline (60 s) passes as the chunk that ends with message_stop arrives
            return rest
        outcome, _ = self.send(FakeResponse(200, chunks=[first, late, b'never read'],
                                            headers={'request-id': fa.REQUEST_ID}))
        self.assertWhole(outcome, first + rest)

    def test_bytes_short_of_the_end_event_stay_unknown(self):
        """The boundary: a reset, a deadline or a body that ends before message_stop leaves the outcome unknown, the
        bytes read kept and no usage."""
        events = fa.answer_events(fa.pass_1_answer())
        short = fa.sse(*events[:-1])  # message_delta read, message_stop not

        def late():
            self.clock.advance(120)
            return short[200:]
        for name, response, expect in (
                ('a reset before message_stop',
                 FakeResponse(200, chunks=[short, requests.exceptions.ChunkedEncodingError(RESET)],
                              headers={'request-id': fa.REQUEST_ID}), 'ChunkedEncodingError'),
                ('the deadline before message_stop',
                 FakeResponse(200, chunks=[short[:200], late, fa.sse(fa.stop())], headers={'request-id': fa.REQUEST_ID}),
                 participants_http.DEADLINE_READING),
                ('a body read whole without message_stop',
                 FakeResponse(200, short, headers={'request-id': fa.REQUEST_ID}), 'ended before its end event'),
                ('the last event left unterminated',
                 FakeResponse(200, chunks=[fa.sse(*events)[:-1], requests.exceptions.ChunkedEncodingError(RESET)],
                              headers={'request-id': fa.REQUEST_ID}), 'ChunkedEncodingError')):
            with self.subTest(name):
                outcome, _ = self.send(response)
                final = outcome.final
                kept = final.response_bytes
                self.assertEqual((final.outcome, final.sent, final.http_status, final.usage, final.usage_basis),
                                 ('unknown', True, 200, {}, ''))
                self.assertFalse(fable_adapter.complete(kept))
                self.assertIn('The outcome is unknown; reconcile it before any new attempt.', final.error)
                self.assertIn(expect, final.error)
                self.assertIsNone(fable_adapter.classify(final.outcome, final.http_status, kept))


class R2TKeptBytesLoopbackTests(fa.LoopbackGuard, SimpleTestCase):
    """D294 (CONN-RF-3) over a REAL socket - the tree's default session (the watched adapter, the deadline's timer) and
    participants.http.post with the Fable VENDOR against a loopback server on 127.0.0.1 (the refutation's input: a whole
    stream written at once, the chunked body's terminating chunk after the deadline)."""

    def post(self, url, deadline_s=5.0):
        return participants_http.post(fable_adapter.VENDOR, participants_http.default_session, url, b'{}',
                                      {'content-type': 'application/json'}, deadline=time.monotonic() + deadline_s,
                                      connect_timeout=2, read_timeout=3, max_response_bytes=1 << 20,
                                      requested_model=fa.MODEL)

    def test_a_whole_stream_whose_body_ends_after_the_deadline_succeeds(self):
        raw = fa.answer_stream(fa.pass_1_answer())
        started = time.monotonic()
        server = fa.LoopbackServer(self, [(fa.HEAD + b'Transfer-Encoding: chunked\r\n\r\n', 0), (fa.chunk(raw), 0),
                                          (b'0\r\n\r\n', 4.0)])
        exchange = self.post(server.url, deadline_s=1.0)
        self.assertLess(time.monotonic() - started, 3)  # read until the 1 s deadline, never until the late end
        self.assertEqual((exchange.outcome, exchange.http_status, exchange.response_bytes, exchange.usage,
                          exchange.error, exchange.returned_model),
                         ('succeeded', 200, raw, fa.FINAL_USAGE, '', fa.MODEL))

    def test_a_connection_closed_after_the_end_event_succeeds(self):
        raw = fa.answer_stream(fa.pass_1_answer())
        server = fa.LoopbackServer(self, [(fa.HEAD + b'Transfer-Encoding: chunked\r\n\r\n', 0),
                                          (fa.chunk(raw[:500]), 0), (fa.chunk(raw[500:]), 0.05)])
        exchange = self.post(server.url)  # the chunked body is left without its terminating chunk
        self.assertEqual((exchange.outcome, exchange.response_bytes, exchange.usage), ('succeeded', raw, fa.FINAL_USAGE))

    def test_a_stream_cut_before_its_end_event_stays_unknown(self):
        """The boundary, over the same socket: the bytes stop inside message_stop."""
        raw = fa.answer_stream(fa.pass_1_answer())
        server = fa.LoopbackServer(self, [(fa.HEAD + b'Transfer-Encoding: chunked\r\n\r\n', 0),
                                          (fa.chunk(raw[:-20]), 0)])
        exchange = self.post(server.url)
        self.assertEqual((exchange.outcome, exchange.http_status, exchange.response_bytes, exchange.usage),
                         ('unknown', 200, raw[:-20], {}))
        self.assertIn('The outcome is unknown; reconcile it before any new attempt.', exchange.error)


class R2TFinalUsageTests(OfflineTestCase):
    """D294 (CONN-RF-5): a stream whose message_delta carries no usage - no usage key, null, an empty object, or one that
    states no output count - has no final usage: describe records none (so the report counts the run unpriced and the
    harness counts it at its bound), never message_start's partial count; the answer itself is read as before."""

    NONE = (('no usage key', ...), ('usage null', None), ('an empty usage', {}),
            ('no output count', {'input_tokens': 9}), ('an output count that is text', {'output_tokens': '15210'}),
            ('a negative output count', {'output_tokens': -1}), ('a true/false output count', {'output_tokens': True}))

    def post(self, raw):
        session = FakeSession(FakeResponse(200, raw, headers={'request-id': fa.REQUEST_ID}))
        return participants_http.post(fable_adapter.VENDOR, lambda: session, fable_adapter.ENDPOINT, b'{}', {},
                                      deadline=time.monotonic() + 30, connect_timeout=5, read_timeout=5,
                                      max_response_bytes=fable_adapter.DEFAULT_MAX_RESPONSE_BYTES,
                                      requested_model=fa.MODEL)

    def test_a_message_delta_that_states_no_usage_leaves_no_final_usage(self):
        for name, delta_usage in self.NONE:
            with self.subTest(name):
                raw = without_delta_usage(delta_usage)
                self.assertEqual(fable_adapter.describe(raw), ({}, fa.MODEL, fa.MESSAGE_ID))
                stream, code, _ = fable_adapter.assemble(raw)
                self.assertEqual((code, stream.final_usage), ('', False))
                self.assertEqual(fable_adapter.classify('succeeded', 200, raw).kind, fable_adapter.ANSWERED)
                exchange = self.post(raw)
                self.assertEqual((exchange.outcome, exchange.usage, exchange.usage_basis), ('succeeded', {}, ''))

    def test_a_message_delta_that_states_its_output_count_is_final(self):
        """The boundary: message_delta's usage - its output count alone, or Anthropic's whole delta usage - is final,
        merged over message_start's."""
        for delta_usage, usage in (({'output_tokens': 7}, {**fa.START_USAGE, 'output_tokens': 7}),
                                   ({'output_tokens': 0}, {**fa.START_USAGE, 'output_tokens': 0}),
                                   (fa.DELTA_USAGE, fa.FINAL_USAGE)):
            with self.subTest(delta_usage=delta_usage):
                raw = without_delta_usage(delta_usage)
                self.assertEqual(fable_adapter.describe(raw), (usage, fa.MODEL, fa.MESSAGE_ID))
                self.assertTrue(fable_adapter.assemble(raw)[0].final_usage)
                exchange = self.post(raw)
                self.assertEqual((exchange.usage, exchange.usage_basis), (usage, 'provider_reported_tokens'))


class R2TFableOverSession(fable_adapter.FableInterpreter):
    """The live connector - FableInterpreter's body checks, the key read at send time and participants.http.post under
    the Fable VENDOR - over a fake session. Its mode is 'replay', as the scripted interpreter's is, so the live gate's
    attestation rule (a synthetic-attested revision) does not apply; everything the connector does is the live one's."""
    mode = 'replay'


class R2TConnectorJobsTests(OfflineMixin, tj.FableCase):
    """The stages and the reconcile path (P-6) over the live connector's own record of a send: D294 (CONN-RF-3) - a whole
    stream whose read stopped after its end event is read by the interpret stage and settled from by P-6, never left
    UNKNOWN for a reconcile that pays for it again - and (CONN-RF-5) a run whose stream states no final usage is counted
    unpriced in the release report, its reading unchanged."""

    def setUp(self):
        super().setUp()
        self.credentials = write_file(self.tmp / 'anthropic.env', anthropic_env())

    def connector(self, *responses):
        session = FakeSession(*responses)
        return R2TFableOverSession(self.credentials, session_factory=lambda: session), session

    def over(self, *responses):
        interpreter, session = self.connector(*responses)
        self.enterContext(mock.patch.object(fable_adapter, 'get_interpreter_v2', return_value=interpreter))
        return session

    def test_the_interpret_stage_reads_a_whole_stream_whose_read_stopped_after_its_end_event(self):
        raw = fa.answer_stream(json.dumps(tj.note_answer()))
        session = self.over(FakeResponse(200, chunks=[raw, requests.exceptions.ChunkedEncodingError(RESET)],
                                         headers={'request-id': fa.REQUEST_ID}))
        encounter, job, run = self.run_to(tj.EXTRACTION)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual((job.state, run.state, bytes(run.response_bytes), run.usage, run.error),
                         (Job.SUCCEEDED, Run.SUCCEEDED, raw, fa.FINAL_USAGE, ''), job.error)
        self.assertFalse(jobs._unreconciled_unknown(encounter))  # no outcome left for a reconcile to pay for again
        self.assertTrue(Job.objects.filter(encounter=encounter, kind=jobs.APPRAISE).exists())  # pass 2 is what is owed

    def test_p6_settles_from_the_connectors_record_of_such_a_read_and_never_from_bytes_short_of_the_end(self):
        encounter, revision = self.fresh_encounter()
        self.run_next('extract')
        self.cancel_queued()
        revision.refresh_from_db()
        request = fable_adapter.build_extraction_request(*jobs._document_of(revision))
        raw = fa.answer_stream(json.dumps(tj.note_answer()))
        for kept, settles in ((raw, True), (raw[:-20], False)):  # the second: the bytes stop inside message_stop
            with self.subTest(settles=settles):
                interpreter, _ = self.connector(FakeResponse(200, chunks=[kept, requests.exceptions.ChunkedEncodingError(
                    RESET)], headers={'request-id': fa.REQUEST_ID}))
                outcome = interpreter.send_loop(request, deadline_s=60)
                run = Run.objects.create(encounter=encounter, revision=revision, provider=interpretation.PROVIDER_V3,
                                         adapter_version=interpretation.ADAPTER_VERSION_V3,
                                         request_sha256=request.canonical_sha256, request_body={}, contexts=[],
                                         state=Run.SENDING, sent=True, endpoint=fable_adapter.ENDPOINT,
                                         purpose=tj.EXTRACTION, scope={'mode': 'replay'}, started_at=timezone.now())
                jobs._record_exchanges(run, outcome.exchanges)  # what the stage records as the exchange ends
                self.assertEqual(jobs._settle_from_exchange(run), settles)  # a dead worker's run, settled by P-6
                run.refresh_from_db()
                if settles:
                    self.assertEqual((run.state, bytes(run.response_bytes), run.usage),
                                     (Run.SUCCEEDED, raw, fa.FINAL_USAGE))
                else:
                    self.assertEqual(run.state, Run.SENDING)

    def test_a_run_whose_stream_states_no_final_usage_is_counted_unpriced(self):
        for delta_usage, priced in ((..., False), ({}, False), (fa.DELTA_USAGE, True)):  # the last: the boundary
            with self.subTest(priced=priced, delta_usage=str(delta_usage)):
                self.cancel_queued()  # each scene starts from no queued job, whatever the one before left
                raw = without_delta_usage(delta_usage, json.dumps(tj.note_answer()))
                self.over(FakeResponse(200, raw, headers={'request-id': fa.REQUEST_ID}))
                encounter, job, run = self.run_to(tj.EXTRACTION)
                self.assertEqual((job.state, run.state), (Job.SUCCEEDED, Run.SUCCEEDED), job.error)  # read as before
                self.assertEqual(run.usage, fa.FINAL_USAGE if priced else {})
                self.assertEqual(review.estimated_cost(run) is not None, priced)
                sums = release_report.usage_sums([release_report.run_json(run)])
                self.assertEqual((sums['priced_runs'], sums['unpriced_runs']), (1, 0) if priced else (0, 1))
