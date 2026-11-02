"""The participants' tool loop (HARNESS.md 11.2; I6, I8, I9), for Astra and Fable alike: two- and three-exchange loops
with the answer passed back exactly (reasoning items, thinking blocks) and append-only; tool results and every error
result; the limits (exchanges, the loop deadline, the per-exchange read timeout, an oversized result); unknown, failed
and unsent exchanges mid-loop; the PDF placeholder re-verified and expanded on every exchange; another model's tool
request never acted on; usage summed and the run's record; and replayed loops keyed by each exchange's request sha256.
Offline and synthetic (test_participants_support): every exchange goes to a fake session."""
from __future__ import annotations

import base64
import copy
import dataclasses
import hashlib
import json
from unittest import mock

import requests
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, ReadTimeoutError

from studio.participants import anthropic_fable, loop, openai_astra
from studio.participants import http as participants_http
from studio.participants.anthropic_fable import FableParticipant
from studio.participants.openai_astra import AstraParticipant
from studio.participants.replay import ReplayParticipant
from studio.providers.base import canonical_body, request_sha256

from tests.test_participants_support import (ASTRA_TOOL_USAGE, CLIENT_REQUEST_ID, FABLE_TOOL_USAGE, FACTS_ARGUMENTS,
                                             NOTE, ORIGINAL, PAGES, PASSAGES_ARGUMENTS, PDF, SECRETS, FakeClock,
                                             FakeExecutor, FakeResponse, FakeSession, OfflineTestCase, anthropic_env,
                                             astra_tool_call, canonical, fable_tool_use, fixture_bytes, openai_env,
                                             write_file)

UNKNOWN = 'The outcome is unknown; reconcile it before any new attempt.'


class _LoopContract:
    """Every arm of the tool loop for one vendor; the concrete classes below name the vendor."""
    module = None
    adapter_class = None
    fixture = ''
    vendor = ''
    request_id_header = ''
    tool_usage = None

    def env(self):
        raise NotImplementedError

    def tool_answer(self, *calls, **options) -> bytes:
        raise NotImplementedError

    def appended(self, body: dict, answer: bytes, outputs) -> dict:
        """The body the next exchange must carry: ``body``, extended exactly as the vendor documents."""
        raise NotImplementedError

    def passed_back(self, body: dict) -> list:
        """The items of the answer the next request passed back (what follows the previous request's own items)."""
        raise NotImplementedError

    def setUp(self):
        super().setUp()
        self.clock = FakeClock()
        for target in (participants_http, self.module, loop):
            self.enterContext(mock.patch.object(target, 'monotonic', self.clock))
        self.credentials = write_file(self.tmp / 'vendor.env', self.env())
        self.final_raw = fixture_bytes(self.fixture)

    # --- helpers -------------------------------------------------------------------

    def make(self, session, **options):
        made = []

        def factory():
            made.append(session)
            return session
        return self.adapter_class(self.credentials, session_factory=factory, **options), made

    def ok(self, raw, number=1):
        return FakeResponse(200, raw, headers={self.request_id_header: f'req_synthetic_{number:04d}'})

    def run_loop(self, *steps, kind='paste', original_bytes=None, request=None, deadline_s=540, executor=None,
                 client_request_id=CLIENT_REQUEST_ID, **options):
        session = FakeSession(*steps)
        adapter, made = self.make(session, **options)
        if request is None:
            request = adapter.build_request(NOTE, PAGES, kind, ORIGINAL if kind == 'pdf' else None)
        executor = FakeExecutor() if executor is None else executor
        outcome = adapter.send_loop(request, deadline_s=deadline_s, client_request_id=client_request_id,
                                    original_bytes=original_bytes, execute_tool=executor)
        self.assertNoSecrets(outcome)
        self.assertTrue(all(response.closed for response in session.responses))
        self.assertGreaterEqual(len(made), len(session.calls))  # a session per exchange that reached http.post
        self.assertTrue(session.closed or not made)
        return outcome, session, adapter, request, executor

    def assertNoSecrets(self, outcome):
        text = repr(outcome)
        for secret in SECRETS:
            self.assertNotIn(secret, text)

    def facts_call(self, call_id='call_synthetic_facts_01'):
        return (call_id, 'cms_code_facts', FACTS_ARGUMENTS)

    # --- the loop -------------------------------------------------------------------

    def test_a_two_exchange_loop_passes_the_answer_back_exactly_and_records_every_exchange(self):
        answer = self.tool_answer(self.facts_call())
        executor = FakeExecutor()
        outcome, session, adapter, request, _ = self.run_loop(self.ok(answer, 1), self.ok(self.final_raw, 2),
                                                              executor=executor)
        self.assertEqual(len(session.calls), 2)
        result, refs = FakeExecutor()('cms_code_facts', FACTS_ARGUMENTS)
        output = canonical(result)
        expected = self.appended(request.body, answer, [('call_synthetic_facts_01', output)])
        self.assertEqual(session.calls[0]['data'], canonical_body(request.body))
        self.assertEqual(json.loads(session.calls[1]['data']), expected)
        self.assertEqual(session.calls[1]['data'], canonical_body(expected))  # exactly the stored body (no PDF)
        first, second = outcome.exchanges
        self.assertEqual((first.turn, first.request_body, first.request_sha256), (1, request.body,
                                                                                 request.canonical_sha256))
        self.assertEqual((second.turn, second.request_body, second.request_sha256),
                         (2, expected, hashlib.sha256(canonical_body(expected)).hexdigest()))
        for record, raw, number in ((first, answer, 1), (second, self.final_raw, 2)):
            with self.subTest(turn=number):
                self.assertEqual((record.outcome, record.http_status, record.response_bytes, record.response_sha256,
                                  record.usage, record.provider_request_id, record.response_id, record.error),
                                 ('succeeded', 200, raw, hashlib.sha256(raw).hexdigest(), json.loads(raw)['usage'],
                                  f'req_synthetic_{number:04d}', json.loads(raw)['id'], ''))
                self.assertIsNotNone(record.started_at)
                self.assertIsNotNone(record.finished_at)
        (call,) = first.tool_calls
        self.assertEqual((call.call_id, call.tool, call.arguments, call.result, call.refs),
                         ('call_synthetic_facts_01', 'cms_code_facts', FACTS_ARGUMENTS, result, tuple(refs)))
        self.assertEqual(call.result_sha256, hashlib.sha256(output.encode()).hexdigest())
        self.assertIsNotNone(call.executed_at)
        self.assertEqual(second.tool_calls, ())
        self.assertEqual(executor.calls, [('cms_code_facts', FACTS_ARGUMENTS)])
        final = outcome.final
        self.assertEqual((final.outcome, final.sent, final.http_status, final.response_bytes, final.error),
                         ('succeeded', True, 200, self.final_raw, ''))
        self.assertEqual((final.endpoint, final.requested_model, final.returned_model, final.response_id,
                          final.provider_request_id),
                         (self.module.ENDPOINT, self.module.MODEL, self.module.MODEL, json.loads(self.final_raw)['id'],
                          'req_synthetic_0002'))
        self.assertEqual((final.usage, final.usage_basis),
                         (loop.summed_usage([json.loads(answer)['usage'], json.loads(self.final_raw)['usage']]),
                          'provider_reported_tokens_summed_over_exchanges'))
        self.assertEqual(final.latency_ms, 0.0)
        self.assertEqual((outcome.outcome, outcome.refs_retrieved), ('succeeded', frozenset(refs)))
        reading = adapter.read(request, final.response_bytes, outcome.refs_retrieved)
        self.assertEqual((reading.refused, reading.adapter_version), (False, self.module.ADAPTER_VERSION))

    def test_a_three_exchange_loop_appends_and_never_edits(self):
        first_answer = self.tool_answer(self.facts_call('call_synthetic_a'), number=1)
        second_answer = self.tool_answer(('call_synthetic_b', 'cms_policy_passages', PASSAGES_ARGUMENTS),
                                         ('call_synthetic_c', 'cms_code_facts', {'codes': ['45380'],
                                                                                 'date_of_service': ''}), number=2)
        outcome, session, _, request, executor = self.run_loop(
            self.ok(first_answer, 1), self.ok(second_answer, 2), self.ok(self.final_raw, 3))
        self.assertEqual(len(session.calls), 3)
        self.assertEqual([name for name, _ in executor.calls], ['cms_code_facts', 'cms_policy_passages',
                                                                'cms_code_facts'])
        bodies = [record.request_body for record in outcome.exchanges]
        self.assertEqual(bodies[0], request.body)
        outputs = [[(call.call_id, canonical(call.result)) for call in record.tool_calls]
                   for record in outcome.exchanges]
        self.assertEqual([len(item) for item in outputs], [1, 2, 0])
        self.assertEqual(bodies[1], self.appended(bodies[0], first_answer, outputs[0]))
        self.assertEqual(bodies[2], self.appended(bodies[1], second_answer, outputs[1]))
        self.assertEqual([json.loads(call['data']) for call in session.calls], bodies)
        for earlier, later in zip(bodies, bodies[1:]):  # append-only: every earlier turn is unchanged
            key = 'input' if self.module is openai_astra else 'messages'
            self.assertEqual(later[key][:len(earlier[key])], earlier[key])
            self.assertEqual({k: v for k, v in later.items() if k != key}, {k: v for k, v in earlier.items() if k != key})
        self.assertEqual([record.request_sha256 for record in outcome.exchanges],
                         [request_sha256(body) for body in bodies])
        self.assertEqual(outcome.final.outcome, 'succeeded')

    def test_the_answer_is_passed_back_exactly_as_returned(self):
        """Reasoning items with their encrypted content, thinking blocks with their signatures, and any field CPT Studio
        does not know, nested values and numbers included, travel back unchanged."""
        answer = self.vendor_specific_answer()
        outcome, session, _, request, _ = self.run_loop(self.ok(answer), self.ok(self.final_raw, 2))
        returned = json.loads(answer)
        returned_items = returned['output'] if self.module is openai_astra else returned['content']
        self.assertEqual(self.passed_back(outcome.exchanges[1].request_body), returned_items)
        self.assertEqual(self.passed_back(json.loads(session.calls[1]['data'])), returned_items)

    # --- tool results ---------------------------------------------------------------

    def test_tool_errors_are_cpt_studios_own_sentences_and_carry_no_refs(self):
        def raises(name, arguments):
            raise RuntimeError('synthetic internal detail that must never reach the vendor')
        cases = {
            'call_unknown': ('web_search', {'query': 'x'}, loop.UNKNOWN_TOOL),
            'call_extra': ('cms_code_facts', dict(FACTS_ARGUMENTS, extra='x'), None),
            'call_type': ('cms_code_facts', {'codes': '45385', 'date_of_service': ''}, None),
            'call_enum': ('cms_policy_passages', {'topic': 'payer_policy', 'codes': []}, None),
            'call_raises': ('cms_policy_passages', PASSAGES_ARGUMENTS, loop.TOOL_FAILED),
        }
        answers = {'cms_policy_passages': raises}
        answer = self.tool_answer(*((call_id, name, arguments) for call_id, (name, arguments, _) in cases.items()))
        executor = FakeExecutor(answers)
        outcome, session, _, _, _ = self.run_loop(self.ok(answer), self.ok(self.final_raw, 2), executor=executor)
        records = {call.call_id: call for call in outcome.exchanges[0].tool_calls}
        self.assertEqual(list(records), list(cases))
        facts = ('The arguments do not fit cms_code_facts, which takes exactly these fields: codes, '
                 'date_of_service.')
        passages = ('The arguments do not fit cms_policy_passages, which takes exactly these fields: topic, codes '
                    '(topic is one of pfs_indicator_definitions, ncci_endoscopy_rules, multiple_endoscopy_payment).')
        expected = {'call_unknown': loop.UNKNOWN_TOOL, 'call_extra': facts, 'call_type': facts,
                    'call_enum': passages, 'call_raises': loop.TOOL_FAILED}
        for call_id, sentence in expected.items():
            with self.subTest(call_id=call_id):
                self.assertEqual((records[call_id].result, records[call_id].refs), ({'error': sentence}, ()))
        self.assertEqual(records['call_unknown'].tool, 'web_search')
        self.assertEqual(executor.calls, [('cms_policy_passages', PASSAGES_ARGUMENTS)])  # only a call that fits ran
        sent = session.calls[1]['data'].decode()
        self.assertNotIn('synthetic internal detail', sent)
        self.assertNotIn('synthetic internal detail', repr(outcome))
        self.assertEqual(outcome.refs_retrieved, frozenset())
        self.assertEqual(outcome.final.outcome, 'succeeded')

    def test_an_executor_answer_that_is_not_a_result_becomes_the_error_result(self):
        bad = {'not a pair': {'result': 1}, 'a list result': ([1], []), 'refs as a string': ({'a': 1}, 'fact:x'),
               'a ref that is not text': ({'a': 1}, [1]), 'a NaN': ({'a': float('nan')}, []),
               'a NUL': ({'a': 'x\x00y'}, []), 'a lone surrogate': ({'a': '\ud800'}, []),
               'a key that is not text': ({1: 'a', 'b': 2}, []), 'an object': ({'a': object()}, []),
               'a NUL in a ref': ({'a': 1}, ['fact:\x00'])}
        for label, returned in bad.items():
            with self.subTest(label):
                answer = self.tool_answer(self.facts_call())
                outcome, _, _, _, _ = self.run_loop(self.ok(answer), self.ok(self.final_raw, 2),
                                                    executor=FakeExecutor({'cms_code_facts': returned}))
                (call,) = outcome.exchanges[0].tool_calls
                self.assertEqual((call.result, call.refs), ({'error': loop.TOOL_FAILED}, ()))

    def test_an_oversized_result_is_replaced_never_truncated(self):
        limit = 2048
        for size, kept in ((limit, True), (limit + 1, False)):
            with self.subTest(size=size):
                padding = 'x' * (size - len(canonical({'pad': ''})))
                result = {'pad': padding}
                self.assertEqual(len(canonical(result).encode()), size)
                answer = self.tool_answer(self.facts_call())
                outcome, session, _, _, _ = self.run_loop(
                    self.ok(answer), self.ok(self.final_raw, 2), max_tool_result_bytes=limit,
                    executor=FakeExecutor({'cms_code_facts': (result, ['fact:cms-pfs-rvu26d:45385:status'])}))
                (call,) = outcome.exchanges[0].tool_calls
                if kept:
                    self.assertEqual((call.result, call.refs), (result, ('fact:cms-pfs-rvu26d:45385:status',)))
                else:
                    self.assertEqual((call.result, call.refs), ({'error': loop.TOO_LARGE}, ()))
                    self.assertNotIn(padding[:100], session.calls[1]['data'].decode())
                    self.assertEqual(outcome.refs_retrieved, frozenset())

    # --- limits ---------------------------------------------------------------------

    def test_the_exchange_limit_ends_the_loop_failed_and_sends_nothing_more(self):
        for limit in (4, 2):
            with self.subTest(limit=limit):
                steps = [self.ok(self.tool_answer(self.facts_call(f'call_synthetic_{n}'), number=n), n)
                         for n in range(1, limit + 1)]
                executor = FakeExecutor()
                outcome, session, _, _, _ = self.run_loop(*steps, executor=executor, max_exchanges=limit)
                self.assertEqual(len(session.calls), limit)
                self.assertEqual((outcome.final.outcome, outcome.final.sent), ('failed', True))
                self.assertIn('the tool-call limit was reached', outcome.final.error)
                self.assertIn(f'after {limit} exchanges', outcome.final.error)
                self.assertEqual(len(executor.calls), limit - 1)  # the last request's tools are never run
                self.assertEqual(outcome.exchanges[-1].tool_calls, ())
                self.assertEqual(outcome.final.response_bytes, outcome.exchanges[-1].response_bytes)

    def test_each_exchange_reads_within_its_timeout_clamped_to_the_time_left(self):
        def slow_answer():
            self.clock.advance(500)
            return self.ok(self.tool_answer(self.facts_call()))
        _, session, _, _, _ = self.run_loop(slow_answer, self.ok(self.final_raw, 2))
        self.assertEqual([call['timeout'] for call in session.calls], [(10, 240), (10, 40)])

    def test_the_loop_deadline_is_never_more_than_the_configured_one(self):
        def slow_answer():
            self.clock.advance(530)
            return self.ok(self.tool_answer(self.facts_call()))
        outcome, session, _, _, _ = self.run_loop(slow_answer, self.ok(self.final_raw, 2), deadline_s=10_000)
        self.assertEqual([call['timeout'] for call in session.calls], [(10, 240), (10, 10)])
        self.assertEqual(outcome.final.outcome, 'succeeded')
        _, session, _, _, _ = self.run_loop(self.ok(self.final_raw), deadline_s=30)  # a shorter one is kept
        self.assertEqual(session.calls[0]['timeout'], (10, 30))

    def test_the_deadline_passing_before_the_tools_are_answered_fails_the_loop(self):
        answer = self.tool_answer(self.facts_call())
        late = FakeResponse(200, chunks=[answer[:20], lambda: self.clock.advance(540) or answer[20:]])
        outcome, session, _, _, executor = self.run_loop(late)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(executor.calls, [])
        self.assertEqual((outcome.final.outcome, outcome.final.sent), ('failed', True))
        self.assertIn("The loop's deadline passed before the participant's tool calls were answered",
                      outcome.final.error)
        self.assertEqual(outcome.exchanges[0].outcome, 'succeeded')

    def test_the_deadline_passing_while_the_tools_are_answered_fails_the_loop(self):
        def slow(name, arguments):
            self.clock.advance(600)
            return {'ok': True}, ['fact:slow']
        answer = self.tool_answer(self.facts_call('call_synthetic_1'), self.facts_call('call_synthetic_2'))
        outcome, session, _, _, executor = self.run_loop(self.ok(answer),
                                                         executor=FakeExecutor({'cms_code_facts': slow}))
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual([call.call_id for call in outcome.exchanges[0].tool_calls], ['call_synthetic_1'])
        self.assertEqual(outcome.final.outcome, 'failed')
        self.assertIn('passed while CPT Studio was answering', outcome.final.error)

    def test_the_deadline_passing_before_the_next_exchange_is_sent_fails_the_loop(self):
        def slow(name, arguments):
            self.clock.advance(600)
            return {'ok': True}, []
        answer = self.tool_answer(self.facts_call())
        outcome, session, _, _, _ = self.run_loop(self.ok(answer), executor=FakeExecutor({'cms_code_facts': slow}))
        self.assertEqual(len(session.calls), 1)
        first, second = outcome.exchanges
        self.assertEqual((second.outcome, second.error),
                         ('not_sent', 'The deadline passed before the request was sent; nothing was sent.'))
        self.assertEqual((outcome.final.outcome, outcome.final.sent), ('failed', True))
        self.assertIn('The tool loop stopped at exchange 2, which was not sent', outcome.final.error)

    # --- unknown, failed and unsent exchanges --------------------------------------------

    def test_an_unknown_outcome_mid_loop_stops_the_loop_and_is_never_retried(self):
        path = '/v1/' + self.module.ENDPOINT.rsplit('/', 1)[1]
        timeout = requests.exceptions.ReadTimeout(ReadTimeoutError(None, path, 'Read timed out.'))
        answer = self.tool_answer(self.facts_call())
        outcome, session, _, _, _ = self.run_loop(self.ok(answer), timeout)
        self.assertEqual(len(session.calls), 2)
        first, second = outcome.exchanges
        self.assertEqual((second.outcome, second.response_bytes, second.http_status), ('unknown', None, None))
        final = outcome.final
        self.assertEqual((final.outcome, final.sent, final.response_bytes), ('unknown', True, None))
        self.assertTrue(final.error.startswith(f'The tool loop stopped at exchange 2: The request may have reached '
                                               f'{self.vendor}'))
        self.assertIn(UNKNOWN, final.error)
        self.assertEqual((final.usage, final.usage_basis),
                         (json.loads(answer)['usage'], 'provider_reported_tokens_summed_over_exchanges'))

    def test_a_failed_exchange_mid_loop_keeps_its_body(self):
        body = b'{"error":{"message":"synthetic upstream failure"}}'
        answer = self.tool_answer(self.facts_call())
        outcome, session, _, _, _ = self.run_loop(self.ok(answer), FakeResponse(500, body))
        self.assertEqual(len(session.calls), 2)
        final = outcome.final
        self.assertEqual((final.outcome, final.http_status, final.response_bytes, final.response_sha256),
                         ('failed', 500, body, hashlib.sha256(body).hexdigest()))
        self.assertEqual(final.error, f'The tool loop stopped at exchange 2: {self.vendor} answered HTTP 500; the '
                                      'response body is retained.')
        self.assertEqual((outcome.exchanges[1].outcome, outcome.exchanges[1].response_bytes), ('failed', body))

    def test_a_later_exchange_that_never_left_fails_the_run_and_is_not_unsent(self):
        path = '/v1/' + self.module.ENDPOINT.rsplit('/', 1)[1]
        never = requests.exceptions.ConnectTimeout(MaxRetryError(None, path, ConnectTimeoutError('synthetic')))
        outcome, session, _, _, _ = self.run_loop(self.ok(self.tool_answer(self.facts_call())), never)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(outcome.exchanges[1].outcome, 'not_sent')
        self.assertEqual((outcome.final.outcome, outcome.final.sent), ('failed', True))
        self.assertIn('The tool loop stopped at exchange 2, which was not sent', outcome.final.error)
        self.assertIn('The earlier exchanges were sent, so this run failed.', outcome.final.error)

    def test_a_first_exchange_that_never_left_is_not_sent(self):
        path = '/v1/' + self.module.ENDPOINT.rsplit('/', 1)[1]
        never = requests.exceptions.ConnectTimeout(MaxRetryError(None, path, ConnectTimeoutError('synthetic')))
        outcome, session, _, _, executor = self.run_loop(never)
        self.assertEqual((outcome.final.outcome, outcome.final.sent, len(outcome.exchanges)), ('not_sent', False, 1))
        self.assertEqual(outcome.final.error, f'{self.vendor} could not be reached (ConnectTimeout); nothing was sent.')
        self.assertEqual(executor.calls, [])

    def test_refusals_before_the_loop_starts_record_no_exchange(self):
        adapter, made = self.make(FakeSession())
        good = adapter.build_request(NOTE, PAGES, 'paste', None)
        altered = copy.deepcopy(good)
        key = 'input' if self.module is openai_astra else 'messages'
        altered.body[key][0]['content'][-1]['text'] += ' altered'
        cases = ((good, 0, FakeExecutor(), 'deadline'), (good, float('nan'), FakeExecutor(), 'deadline'),
                 (good, 540, None, 'No tool executor was given'), (altered, 540, FakeExecutor(), 'recorded hash'))
        for request, deadline, executor, expect in cases:
            with self.subTest(expect=expect, deadline=deadline):
                outcome = adapter.send_loop(request, deadline_s=deadline, client_request_id=CLIENT_REQUEST_ID,
                                            original_bytes=None, execute_tool=executor)
                self.assertEqual((outcome.final.outcome, outcome.final.sent, outcome.exchanges),
                                 ('not_sent', False, ()))
                self.assertIn(expect, outcome.final.error)
        self.assertEqual(made, [])

    # --- the original, the model, the requests CPT Studio cannot answer ----------------------

    def test_the_pdf_placeholder_is_reverified_and_expanded_on_every_exchange(self):
        first = self.tool_answer(self.facts_call('call_synthetic_1'), number=1)
        second = self.tool_answer(self.facts_call('call_synthetic_2'), number=2)
        verify = mock.patch.object(participants_http, 'verify_original', wraps=participants_http.verify_original)
        with verify as spy:
            outcome, session, _, request, _ = self.run_loop(self.ok(first), self.ok(second, 2),
                                                            self.ok(self.final_raw, 3), kind='pdf', original_bytes=PDF)
        self.assertEqual(spy.call_count, 3)  # once per exchange, each against the bytes given
        self.assertEqual(outcome.final.outcome, 'succeeded')
        rendered = self.prefix + base64.b64encode(PDF).decode('ascii')
        for record, call in zip(outcome.exchanges, session.calls):
            with self.subTest(turn=record.turn):
                stored = record.request_body
                self.assertEqual(self.at(stored, self.module.ORIGINAL_PATH),
                                 {'$original_sha256': ORIGINAL['sha256'], '$original_bytes': ORIGINAL['bytes']})
                self.assertEqual(record.request_sha256, request_sha256(stored))  # the stored, unexpanded form
                sent = json.loads(call['data'])
                self.assertEqual(self.at(sent, self.module.ORIGINAL_PATH), rendered)
                expected = copy.deepcopy(stored)
                self.at(expected, self.module.ORIGINAL_PATH[:-1])[self.module.ORIGINAL_PATH[-1]] = rendered
                self.assertEqual(sent, expected)
                self.assertNotIn(b'$original_sha256', call['data'])

    def test_an_original_that_changes_mid_loop_is_never_sent(self):
        original = bytearray(PDF)

        def tamper(name, arguments):
            original[10] ^= 1
            return {'ok': True}, []
        outcome, session, _, _, _ = self.run_loop(self.ok(self.tool_answer(self.facts_call())), kind='pdf',
                                                  original_bytes=original,
                                                  executor=FakeExecutor({'cms_code_facts': tamper}))
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(outcome.exchanges[1].outcome, 'not_sent')
        self.assertIn('does not match the sha256 and size', outcome.exchanges[1].error)
        self.assertEqual(outcome.final.outcome, 'failed')

    def test_another_models_tool_request_is_never_acted_on(self):
        answer = self.tool_answer(self.facts_call(), model=self.other_model)
        outcome, session, adapter, request, executor = self.run_loop(self.ok(answer))
        self.assertEqual((len(session.calls), executor.calls, outcome.final.outcome), (1, [], 'succeeded'))
        reading = adapter.read(request, outcome.final.response_bytes, outcome.refs_retrieved)
        self.assertTrue(reading.refused)
        self.assertIn(f'as the model that answered, not {self.module.MODEL}', reading.problems[0])

    def test_tool_requests_cpt_studio_cannot_answer_fail_the_loop(self):
        cases = {'two calls share one call id': [self.facts_call('call_same'), self.facts_call('call_same')],
                 'a call has no usable call id': [self.facts_call(None)],
                 'a call has no usable call id ': [self.facts_call('c' * 121)],
                 'a call has no usable call id  ': [self.facts_call('call with space')],
                 '65 calls at once, more than the 64': [self.facts_call(f'call_{n}') for n in range(65)]}
        for expect, calls in cases.items():
            with self.subTest(expect=expect):
                outcome, session, _, _, executor = self.run_loop(self.ok(self.tool_answer(*calls)))
                self.assertEqual((len(session.calls), executor.calls), (1, []))
                self.assertEqual(outcome.final.outcome, 'failed')
                self.assertIn(f'cannot answer ({expect.strip()}', outcome.final.error)
        outcome, _, _, _, executor = self.run_loop(
            self.ok(self.tool_answer(*[self.facts_call(f'call_{n}') for n in range(64)])), self.ok(self.final_raw, 2))
        self.assertEqual((outcome.final.outcome, len(executor.calls)), ('succeeded', 64))
        long_id = 'c' * 120
        outcome, _, _, _, _ = self.run_loop(self.ok(self.tool_answer(self.facts_call(long_id))),
                                            self.ok(self.final_raw, 2))
        self.assertEqual(outcome.exchanges[0].tool_calls[0].call_id, long_id)

    def test_credentials_are_read_for_every_exchange(self):
        def remove(name, arguments):
            self.credentials.unlink()
            return {'ok': True}, []
        outcome, session, _, _, _ = self.run_loop(self.ok(self.tool_answer(self.facts_call())),
                                                  executor=FakeExecutor({'cms_code_facts': remove}))
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(outcome.exchanges[1].outcome, 'not_sent')
        self.assertIn('credentials file does not exist', outcome.exchanges[1].error)
        self.assertNotIn(str(self.credentials), outcome.final.error)
        self.assertEqual(outcome.final.outcome, 'failed')

    def test_a_crash_building_the_next_exchange_fails_the_loop_and_keeps_its_records(self):
        with mock.patch.object(self.module, 'follow_up', side_effect=RuntimeError('synthetic')):
            outcome, session, _, _, executor = self.run_loop(self.ok(self.tool_answer(self.facts_call())))
        self.assertEqual((len(session.calls), len(executor.calls), len(outcome.exchanges)), (1, 1, 1))
        self.assertEqual(outcome.final.outcome, 'failed')
        self.assertEqual(outcome.final.error, 'CPT Studio could not build exchange 2 (RuntimeError); nothing more was '
                                              'sent.')
        self.assertEqual(len(outcome.exchanges[0].tool_calls), 1)

    def test_a_single_exchange_loop_records_what_a_single_send_would(self):
        loop_outcome, _, adapter, request, executor = self.run_loop(self.ok(self.final_raw))
        session = FakeSession(self.ok(self.final_raw))
        sender, _ = self.make(session)
        single = sender.send(request, deadline_s=540, client_request_id=CLIENT_REQUEST_ID, original_bytes=None)
        self.assertEqual(dataclasses.replace(loop_outcome.final, latency_ms=None),
                         dataclasses.replace(single, latency_ms=None))
        self.assertEqual((loop_outcome.final.usage_basis, len(loop_outcome.exchanges), executor.calls),
                         ('provider_reported_tokens', 1, []))


class AstraLoopTests(_LoopContract, OfflineTestCase):
    module = openai_astra
    adapter_class = AstraParticipant
    fixture = 'astra-colonoscopy.response.json'
    vendor = 'OpenAI'
    request_id_header = 'x-request-id'
    other_model = 'gpt-6-astra-mini'
    prefix = 'data:application/pdf;base64,'

    def env(self):
        return openai_env()

    def tool_answer(self, *calls, **options):
        return astra_tool_call(*calls, **options)

    def appended(self, body, answer, outputs):
        expected = copy.deepcopy(body)
        expected['input'] = (copy.deepcopy(body['input']) + json.loads(answer)['output']
                             + [{'type': 'function_call_output', 'call_id': call_id, 'output': output}
                                for call_id, output in outputs])
        return expected

    def passed_back(self, body):
        items = body['input'][1:]
        return [item for item in items if item.get('type') != 'function_call_output']

    @staticmethod
    def at(body, path):
        for key in path:
            body = body[key]
        return body

    def vendor_specific_answer(self):
        reasoning = {'type': 'reasoning', 'id': 'rs_synthetic_exact', 'encrypted_content': 'gAAAAB-exact-0001==',
                     'summary': [{'type': 'summary_text', 'text': 'Synthetic summary é with a "quote".'}],
                     'x_future_field': {'nested': [1, 2.5, None, True, {'deep': 'value'}]}}
        preamble = {'type': 'message', 'id': 'msg_synthetic_preamble', 'status': 'completed', 'role': 'assistant',
                    'content': [{'type': 'output_text', 'text': 'Looking up the facts.', 'annotations': []}]}
        body = json.loads(astra_tool_call(self.facts_call(), reasoning=reasoning))
        body['output'].insert(1, preamble)
        return json.dumps(body).encode()

    def test_each_exchange_sends_its_own_client_request_id(self):
        steps = [self.ok(self.tool_answer(self.facts_call(f'call_{n}'), number=n), n) for n in (1, 2)]
        outcome, session, _, _, _ = self.run_loop(*steps, self.ok(self.final_raw, 3))
        self.assertEqual([call['headers']['X-Client-Request-Id'] for call in session.calls],
                         [CLIENT_REQUEST_ID, f'{CLIENT_REQUEST_ID}-2', f'{CLIENT_REQUEST_ID}-3'])
        self.assertEqual([openai_astra.turn_client_request_id(CLIENT_REQUEST_ID, n) for n in (1, 2, 3)],
                         [call['headers']['X-Client-Request-Id'] for call in session.calls])

    def test_the_client_request_id_leaves_room_for_a_turn_number(self):
        for value, limit, accepted in (('x' * 510, 4, True), ('x' * 511, 4, False), ('x' * 509, 10, True),
                                       ('x' * 510, 10, False), ('', 4, False), ('has space', 4, False), (None, 4, False)):
            with self.subTest(length=len(value or ''), limit=limit):
                steps = (self.ok(self.final_raw),) if accepted else ()
                outcome, session, _, _, _ = self.run_loop(*steps, client_request_id=value, max_exchanges=limit)
                if accepted:
                    self.assertEqual(outcome.final.outcome, 'succeeded')
                else:
                    self.assertEqual((outcome.final.outcome, outcome.exchanges, session.calls), ('not_sent', (), []))
                    longest = 512 - len(f'-{limit}')
                    self.assertIn(f'The client request id must be 1 to {longest} visible ASCII characters',
                                  outcome.final.error)
                    self.assertEqual(outcome.final.requested_model, 'gpt-6-astra')

    def test_arguments_that_are_not_a_json_object_are_answered_with_an_error(self):
        answer = self.tool_answer(('call_text', 'cms_code_facts', 'not json'),
                                  ('call_list', 'cms_code_facts', '["45385"]'),
                                  ('call_nan', 'cms_code_facts', '{"codes": NaN}'))
        outcome, _, _, _, executor = self.run_loop(self.ok(answer), self.ok(self.final_raw, 2))
        records = {call.call_id: call for call in outcome.exchanges[0].tool_calls}
        self.assertEqual({call_id: call.result for call_id, call in records.items()},
                         {'call_text': {'error': loop.NOT_JSON}, 'call_list': {'error': loop.NOT_AN_OBJECT},
                          'call_nan': {'error': loop.NOT_JSON}})
        self.assertEqual((records['call_text'].arguments, records['call_list'].arguments), ('not json', ['45385']))
        self.assertEqual(executor.calls, [])

    def test_a_refused_or_cut_off_message_beside_tool_calls_is_final(self):
        for change in ({'content': [{'type': 'refusal', 'refusal': 'synthetic refusal'}]}, {'status': 'incomplete'}):
            with self.subTest(change=change):
                body = json.loads(self.tool_answer(self.facts_call()))
                body['output'].append(dict({'type': 'message', 'id': 'msg_x', 'status': 'completed',
                                            'role': 'assistant', 'content': []}, **change))
                outcome, session, adapter, request, executor = self.run_loop(self.ok(json.dumps(body).encode()))
                self.assertEqual((len(session.calls), executor.calls, outcome.final.outcome), (1, [], 'succeeded'))
                self.assertTrue(adapter.read(request, outcome.final.response_bytes).refused)


class FableLoopTests(_LoopContract, OfflineTestCase):
    module = anthropic_fable
    adapter_class = FableParticipant
    fixture = 'fable-colonoscopy.response.json'
    vendor = 'Anthropic'
    request_id_header = 'request-id'
    other_model = 'claude-fable-5-1-preview'
    prefix = ''

    def env(self):
        return anthropic_env()

    def tool_answer(self, *calls, **options):
        return fable_tool_use(*calls, **options)

    def appended(self, body, answer, outputs):
        expected = copy.deepcopy(body)
        expected['messages'] = copy.deepcopy(body['messages']) + [
            {'role': 'assistant', 'content': json.loads(answer)['content']},
            {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': call_id, 'content': output}
                                         for call_id, output in outputs]}]
        return expected

    def passed_back(self, body):
        (assistant,) = [message for message in body['messages'] if message['role'] == 'assistant']
        return assistant['content']

    @staticmethod
    def at(body, path):
        for key in path:
            body = body[key]
        return body

    def vendor_specific_answer(self):
        body = json.loads(fable_tool_use(self.facts_call(), thinking={
            'type': 'thinking', 'thinking': 'Synthetic thinking é with "quotes" and\nlines.',
            'signature': 'EqQBCkYIBxgCKkDsynthetic+signature/0001=='}))
        body['content'].insert(1, {'type': 'redacted_thinking', 'data': 'EmwKAhgBEgy3va3pzix/LafPsn4aDFIT'})
        body['content'].insert(2, {'type': 'text', 'text': 'I will look up the facts.',
                                   'x_future_field': {'nested': [1, 2.5, None, True]}})
        return json.dumps(body).encode()

    def test_the_client_request_id_is_never_sent(self):
        steps = [self.ok(self.tool_answer(self.facts_call())), self.ok(self.final_raw, 2)]
        _, session, _, _, _ = self.run_loop(*steps, client_request_id='cptstudio-never-sent-0002')
        for call in session.calls:
            self.assertNotIn('cptstudio-never-sent-0002', json.dumps(call['headers']))
            self.assertEqual({name.lower() for name in call['headers']}, {'x-api-key', 'anthropic-version',
                                                                          'content-type'})

    def test_tool_input_that_is_not_an_object_is_answered_with_an_error(self):
        answer = self.tool_answer(('toolu_list', 'cms_code_facts', ['45385']), ('toolu_text', 'cms_code_facts', 'x'))
        outcome, _, _, _, executor = self.run_loop(self.ok(answer), self.ok(self.final_raw, 2))
        self.assertEqual([call.result for call in outcome.exchanges[0].tool_calls],
                         [{'error': loop.NOT_AN_OBJECT}, {'error': loop.NOT_AN_OBJECT}])
        self.assertEqual(executor.calls, [])

    def test_a_fallback_or_another_stop_beside_tool_use_is_final(self):
        for change in ({'stop_reason': 'end_turn'}, {'stop_reason': 'max_tokens'},
                       {'usage': dict(FABLE_TOOL_USAGE, iterations=[{'type': 'fallback_message'}])}):
            with self.subTest(change=change):
                answer = self.tool_answer(self.facts_call(), envelope=change)
                outcome, session, _, _, executor = self.run_loop(self.ok(answer))
                self.assertEqual((len(session.calls), executor.calls, outcome.final.outcome), (1, [], 'succeeded'))
        body = json.loads(self.tool_answer(self.facts_call()))
        body['content'].append({'type': 'fallback', 'model': 'claude-other'})
        outcome, session, _, _, executor = self.run_loop(self.ok(json.dumps(body).encode()))
        self.assertEqual((len(session.calls), executor.calls), (1, []))


class UsageTests(OfflineTestCase):
    def test_usage_is_summed_key_by_key(self):
        usages = [dict(ASTRA_TOOL_USAGE), {'input_tokens': 10, 'input_tokens_details': {'cached_tokens': 4},
                                           'output_tokens': 5, 'output_tokens_details': {'reasoning_tokens': 2},
                                           'total_tokens': 15, 'later_only': 7}]
        self.assertEqual(loop.summed_usage(usages), {
            'input_tokens': 2510, 'input_tokens_details': {'cached_tokens': 4}, 'output_tokens': 125,
            'output_tokens_details': {'reasoning_tokens': 66}, 'total_tokens': 2635, 'later_only': 7})
        self.assertEqual(list(loop.summed_usage(usages)), ['input_tokens', 'input_tokens_details', 'output_tokens',
                                                           'output_tokens_details', 'total_tokens', 'later_only'])

    def test_values_that_are_not_counts_are_kept_only_when_every_exchange_agrees(self):
        same = [dict(FABLE_TOOL_USAGE), dict(FABLE_TOOL_USAGE)]
        self.assertEqual(loop.summed_usage(same)['service_tier'], 'standard')
        differing = [dict(FABLE_TOOL_USAGE), dict(FABLE_TOOL_USAGE, service_tier='priority')]
        self.assertNotIn('service_tier', loop.summed_usage(differing))
        mixed = [{'flag': True, 'rate': 0.5, 'none': None, 'count': 1, 'iterations': [{'type': 'message'}]},
                 {'flag': True, 'rate': 0.25, 'none': None, 'count': True, 'iterations': [{'type': 'message'}]}]
        self.assertEqual(loop.summed_usage(mixed), {'flag': True, 'none': None,
                                                    'iterations': [{'type': 'message'}]})

    def test_the_refs_retrieved_are_every_tool_calls_refs(self):
        def call(refs):
            return loop.ToolCallRecord(call_id='c', tool='cms_code_facts', arguments={}, result={},
                                       result_sha256='0' * 64, refs=tuple(refs))
        outcome = loop.LoopOutcome(final=participants_http.not_sent('x'), exchanges=(
            loop.ExchangeRecord(turn=1, request_body={}, request_sha256='', outcome='succeeded',
                                tool_calls=(call(['a', 'b']), call([]))),
            loop.ExchangeRecord(turn=2, request_body={}, request_sha256='', outcome='succeeded',
                                tool_calls=(call(['b', 'c']),))))
        self.assertEqual(outcome.refs_retrieved, frozenset({'a', 'b', 'c'}))
        self.assertEqual(loop.LoopOutcome(final=participants_http.not_sent('x')).refs_retrieved, frozenset())


class ReplayLoopTests(OfflineTestCase):
    """A replayed loop is keyed exchange by exchange by each stored request's sha256, so with the same recordings and
    the same tool results it is deterministic; it sends nothing and reports no new usage."""

    def setUp(self):
        super().setUp()
        self.credentials = write_file(self.tmp / 'openai.env', openai_env())
        self.recordings = self.tmp / 'replay'

    def live_loop(self, kind='paste', original_bytes=None):
        steps = [FakeResponse(200, astra_tool_call(('call_r1', 'cms_code_facts', FACTS_ARGUMENTS), number=1)),
                 FakeResponse(200, astra_tool_call(('call_r2', 'cms_policy_passages', PASSAGES_ARGUMENTS),
                                                   number=2)),
                 FakeResponse(200, fixture_bytes('astra-colonoscopy.response.json'))]
        session = FakeSession(*steps)
        adapter = AstraParticipant(self.credentials, session_factory=lambda: session)
        request = adapter.build_request(NOTE, PAGES, kind, ORIGINAL if kind == 'pdf' else None)
        return adapter.send_loop(request, deadline_s=540, client_request_id=CLIENT_REQUEST_ID,
                                 original_bytes=original_bytes, execute_tool=FakeExecutor())

    def record(self, outcome, turns=None):
        folder = self.recordings / 'astra'
        folder.mkdir(parents=True, exist_ok=True)
        for record in outcome.exchanges:
            if turns is None or record.turn in turns:
                write_file(folder / f'{record.request_sha256}.json', record.response_bytes)

    def replay(self, kind='paste', original_bytes=None, executor=None):
        replay = ReplayParticipant('astra', self.recordings)
        request = replay.build_request(NOTE, PAGES, kind, ORIGINAL if kind == 'pdf' else None)
        return replay.send_loop(request, deadline_s=540, client_request_id=CLIENT_REQUEST_ID,
                                original_bytes=original_bytes, execute_tool=executor or FakeExecutor())

    @staticmethod
    def shape(outcome):
        return [(record.turn, record.request_body, record.request_sha256, record.outcome, record.response_bytes,
                 record.response_sha256, record.response_id,
                 [dataclasses.replace(call, executed_at=None) for call in record.tool_calls])
                for record in outcome.exchanges]

    def test_a_recorded_loop_replays_exchange_by_exchange(self):
        live = self.live_loop()
        self.assertEqual(len(live.exchanges), 3)
        self.record(live)
        replayed = self.replay()
        self.assertEqual(self.shape(replayed), self.shape(live))
        self.assertEqual(self.shape(self.replay()), self.shape(replayed))  # deterministic
        final = replayed.final
        self.assertEqual((final.outcome, final.sent, final.usage, final.usage_basis, final.endpoint, final.latency_ms,
                          final.provider_request_id),
                         ('succeeded', False, {}, 'historical_replay_not_new_usage', '', None, ''))
        self.assertEqual([record.usage for record in replayed.exchanges], [{}, {}, {}])
        self.assertEqual(replayed.refs_retrieved, live.refs_retrieved)
        self.assertEqual(final.response_bytes, live.final.response_bytes)

    def test_a_missing_recording_for_a_later_exchange_fails_the_replayed_loop(self):
        live = self.live_loop()
        self.record(live, turns={1})
        replayed = self.replay()
        self.assertEqual([record.outcome for record in replayed.exchanges], ['succeeded', 'not_sent'])
        self.assertEqual(replayed.exchanges[1].error, 'No recorded response for this request.')
        self.assertEqual((replayed.final.outcome, replayed.final.sent), ('failed', False))

    def test_different_tool_results_ask_for_a_different_recording(self):
        self.record(self.live_loop())
        replayed = self.replay(executor=FakeExecutor({'cms_code_facts': ({'other': True}, [])}))
        self.assertEqual([record.outcome for record in replayed.exchanges], ['succeeded', 'not_sent'])

    def test_a_replayed_pdf_loop_reverifies_the_original_on_every_exchange(self):
        live = self.live_loop(kind='pdf', original_bytes=PDF)
        self.record(live)
        self.assertEqual(self.replay(kind='pdf', original_bytes=PDF).final.outcome, 'succeeded')
        refused = self.replay(kind='pdf', original_bytes=PDF + b'x')
        self.assertEqual((refused.final.outcome, len(refused.exchanges)), ('not_sent', 1))
        self.assertIn('does not match', refused.final.error)
        with mock.patch.object(participants_http, 'verify_original',
                               wraps=participants_http.verify_original) as spy:
            self.replay(kind='pdf', original_bytes=PDF)
        self.assertEqual(spy.call_count, 3)
