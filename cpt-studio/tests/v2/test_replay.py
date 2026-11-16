"""studio/interpretation/replay.py, design v2's replay (docs/gemini-migration/FINAL-V2.md 7.4 and 9.3; step 3b of 8.1):
both purposes, by request sha256. TEXT-ONLY and SYNTHETIC: tests/v2/test_claims.py's note and hand-built pass-1
answer, a synthetic appraisal answer built for its claims (tests/v2/test_adapter.py's helpers); every recording is
written here, under a temporary directory; nothing is sent, and no credential or network is involved.

What is proved:
- pass 1 and pass 2 each replay the recording keyed by their own request's canonical sha256, from the one folder
  GEMINI_REPLAY_DIR/gemini/, as a replayed exchange (sent False, no usage, the replay usage basis, no endpoint), and
  each is read exactly as a live answer of its kind is (BothPurposesTests);
- every refusal design v2's interpreter makes of a request is made before any recording is read - v1's request
  included - and a missing or unsafe recording is not sent (RefusalTests);
- v1's ReplayInterpreter is unchanged: it never replays a design v2 request, and v2's never replays v1's
  (RefusalTests); its own tests (tests/test_interpretation_adapter.py, tests/test_interpretation_replay.py) stay green.

AMENDMENT-2 (docs/gemini-migration/AMENDMENT-2.md 1.8; step F1): ReplayInterpreterF replays fable_adapter's two request
kinds from GEMINI_REPLAY_DIR/anthropic/<request sha256>.sse, the raw stream of a complete 200 answer, with the answer
streams of tests/v2/test_fable_adapter.py. What is proved: an .sse recording is read exactly as the same bytes read
live (FableReplayTests); an incomplete recording replays as an unknown outcome with its bytes, the path a live one takes
(FableRecordingTests, FableReplayTests); a changed instruction byte finds no recording ("No recorded response for this
request.") (FableReplayTests); Gemini's folder and Fable's never answer each other's requests (FableReplayTests).
"""
from __future__ import annotations

import copy
import hashlib
from unittest import mock

from studio import interpretation
from studio.interpretation import adapter, holds
from studio.interpretation.contract import appraise_read, extract_read
from studio.interpretation import fable_adapter
from studio.interpretation.contract import extract_prompt
from studio.interpretation.replay import (INCOMPLETE_RECORDING, USAGE_BASIS, ReplayInterpreter, ReplayInterpreterF,
                                          ReplayInterpreterV2)
from studio.participants import http as participants_http
from studio.participants import loop as participants_loop
from studio.types import ProviderRequest
from tests.test_interpretation_adapter import encoded, envelope, with_parts
from tests.test_participants_support import FakeResponse, FakeSession, OfflineTestCase, anthropic_env, write_file
from tests.v2 import test_fable_adapter as streams
from tests.v2.test_adapter import KIND, PAGES, TEXT, Pinned, appraisal_answer, request_with, stored_answer


class ReplayCase(Pinned, OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.folder = self.tmp / 'gemini'
        self.folder.mkdir(mode=0o700)
        self.replay = ReplayInterpreterV2(self.tmp)
        self.extracted = self.replay.build_extraction_request(TEXT, PAGES, KIND)
        self.data = stored_answer()
        self.appraised = self.replay.build_appraisal_request(TEXT, PAGES, KIND, self.extracted, self.data,
                                                             check=lambda text, pages, answer: {})
        self.answer = appraisal_answer(self.appraised.built)

    def record(self, request: ProviderRequest, raw: bytes, mode=0o600):
        return write_file(self.folder / f'{request.canonical_sha256}.json', raw, mode)


class BothPurposesTests(ReplayCase):
    def test_each_purpose_replays_the_recording_keyed_by_its_own_request(self):
        self.assertNotEqual(self.extracted.canonical_sha256, self.appraised.request.canonical_sha256)
        self.record(self.extracted, self.data)
        self.record(self.appraised.request, self.answer)
        for request, raw, purpose in ((self.extracted, self.data, adapter.EXTRACTION),
                                      (self.appraised.request, self.answer, adapter.APPRAISAL)):
            with self.subTest(purpose=purpose):
                self.assertEqual(self.replay.purpose(request), purpose)
                exchange = self.replay.send(request, deadline_s=5)
                self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.response_bytes,
                                  exchange.response_sha256, exchange.usage, exchange.usage_basis, exchange.endpoint,
                                  exchange.requested_model, exchange.returned_model, exchange.response_id),
                                 ('succeeded', False, None, raw, hashlib.sha256(raw).hexdigest(), {}, USAGE_BASIS, '',
                                  'gemini-4-carbon', 'gemini-4-carbon', 'synthetic-response-0001'))
                recorded = []
                with participants_loop.recording(recorded.append):
                    outcome = self.replay.send_loop(request, deadline_s=540, client_request_id='run',
                                                    original_bytes=None)
                self.assertEqual((outcome.outcome, outcome.final.sent, outcome.final.endpoint, len(outcome.exchanges)),
                                 ('succeeded', False, '', 1))
                self.assertEqual((recorded[0].turn, recorded[0].request_sha256), (1, request.canonical_sha256))
        self.assertEqual((self.replay.name, self.replay.adapter_version, self.replay.mode, self.replay.endpoint),
                         ('gemini', 'gemini-generate@cptstudio-2', 'replay', ''))
        self.assertEqual(sorted(path.name for path in self.folder.iterdir()),
                         sorted(f'{sha}.json' for sha in (self.extracted.canonical_sha256,
                                                          self.appraised.request.canonical_sha256)))
        self.assertEqual(self.network_attempts, [])

    def test_a_replayed_answer_of_each_kind_is_read_as_a_live_one(self):
        self.record(self.extracted, self.data)
        self.record(self.appraised.request, self.answer)
        first = self.replay.send(self.extracted, deadline_s=5)
        second = self.replay.send(self.appraised.request, deadline_s=5)
        for exchange in (first, second):
            self.assertEqual(adapter.classify(exchange.outcome, exchange.http_status, exchange.response_bytes).kind,
                             adapter.ANSWERED)
            self.assertEqual(holds.classify(exchange.outcome, exchange.http_status, exchange.response_bytes).effect,
                             holds.ANSWERED)
        read = self.replay.read_extraction(self.extracted, first.response_bytes, self.appraised.unit_count)
        self.assertIsInstance(read, extract_read.ReadAnswer)
        self.assertEqual(read, self.appraised.answer)
        appraised = self.replay.read_appraisal(self.appraised, self.appraised.request, second.response_bytes)
        self.assertIsInstance(appraised, appraise_read.ReadAppraisal)
        self.assertEqual([verdict.content for verdict in appraised.verdicts],
                         [claim.content for claim in self.appraised.built.claim_set.claims])
        # the appraisal is rebuilt from the replayed pass-1 bytes exactly as from the stored ones: replay and reuse
        # work for pass 2 as for pass 1 (7.4 [R:MO-5])
        again = self.replay.build_appraisal_request(TEXT, PAGES, KIND, self.extracted, first.response_bytes,
                                                    check=lambda text, pages, answer: {})
        self.assertEqual(again.request, self.appraised.request)

    def test_a_replayed_cut_off_or_substituted_answer_is_classified_as_a_live_one(self):
        for raw, kind, hold in ((encoded(with_parts({'text': '{'}, finish='MAX_TOKENS')), adapter.TOO_LONG, ''),
                                (encoded(envelope(modelVersion=f'{interpretation.MODEL}-preview')), adapter.HOLD,
                                 adapter.MODEL_HOLD),
                                # gemini-4-argon, the model until DECISIONS D230: another model for a v2 request
                                (encoded(envelope(modelVersion='gemini-4-argon')), adapter.HOLD, adapter.MODEL_HOLD)):
            for request in (self.extracted, self.appraised.request):
                with self.subTest(kind=kind, purpose=self.replay.purpose(request)):
                    path = self.record(request, raw)
                    exchange = self.replay.send(request, deadline_s=5)
                    path.unlink()  # the next case records this request's answer afresh
                    verdict = adapter.classify(exchange.outcome, exchange.http_status, exchange.response_bytes)
                    self.assertEqual((verdict.kind, verdict.hold), (kind, hold))

    def test_the_configured_replay_interpreter(self):
        replay = ReplayInterpreterV2(self.tmp, send_deadline=500, appraisal_send_deadline=490,
                                     max_response_bytes=2048)
        self.assertEqual((replay.send_deadlines, replay.max_response_bytes, replay.replay_dir),
                         ({'interpretation': 500, 'appraisal': 490}, 2048, self.tmp))
        with self.assertRaises(ValueError):
            ReplayInterpreterV2('')


class RefusalTests(ReplayCase):
    def test_a_missing_or_unsafe_recording_is_not_sent(self):
        for request in (self.extracted, self.appraised.request):
            with self.subTest(purpose=self.replay.purpose(request)):
                exchange = self.replay.send(request, deadline_s=5)
                self.assertEqual((exchange.outcome, exchange.sent, exchange.error, exchange.requested_model),
                                 ('not_sent', False, 'No recorded response for this request.', 'gemini-4-carbon'))
                target = write_file(self.tmp / f'elsewhere-{request.canonical_sha256[:8]}.json', self.answer)
                (self.folder / f'{request.canonical_sha256}.json').symlink_to(target)
                self.assertEqual(self.replay.send(request, deadline_s=5).error,
                                 'The recorded response is a symbolic link; it was refused.')
                (self.folder / f'{request.canonical_sha256}.json').unlink()
                self.record(request, b'x' * 4096)
                small = ReplayInterpreterV2(self.tmp, max_response_bytes=1024)
                self.assertEqual(small.send(request, deadline_s=5).error,
                                 'The recorded response is larger than 1,024 bytes.')
                self.assertEqual(ReplayInterpreterV2(self.tmp / 'absent').send(request, deadline_s=5).error,
                                 'The replay directory is not available.')

    def test_every_refusal_of_the_interpreter_is_made_before_a_recording_is_read(self):
        for request in (self.extracted, self.appraised.request):
            self.record(request, self.answer)  # a recording exists for each: still never read for a refused request
            tools = request_with(request, body=dict(copy.deepcopy(request.body), tools=[]))
            self.record(tools, self.answer)
            altered = copy.deepcopy(request.body)
            altered['contents'][0]['parts'][0]['text'] += ' Synthetic addition.'
            cases = ((tools, {}, adapter.NOT_BUILT),
                     (request_with(request, body=altered, canonical_sha256=request.canonical_sha256), {},
                      'does not match its recorded hash'),
                     (request_with(request, provider='fable'), {}, 'different provider'),
                     (request_with(request, adapter_version=adapter.ADAPTER_VERSION), {}, 'different provider'),
                     (request, {'deadline_s': 0}, adapter.INVALID_DEADLINE))
            for refused, options, expect in cases:
                with self.subTest(expect, purpose=self.replay.purpose(request)), \
                        mock.patch.object(ReplayInterpreterV2, 'recorded', side_effect=AssertionError('read')):
                    exchange = self.replay.send(refused, deadline_s=options.get('deadline_s', 5))
                    self.assertEqual((exchange.outcome, exchange.response_bytes), ('not_sent', None))
                    self.assertIn(expect, exchange.error)
                    outcome = self.replay.send_loop(refused, deadline_s=options.get('deadline_s', 5))
                    self.assertEqual((outcome.outcome, outcome.exchanges), ('not_sent', ()))
                    self.assertIn(expect, outcome.final.error)
            with mock.patch.object(ReplayInterpreterV2, 'recorded', side_effect=AssertionError('read')):
                stopped = self.replay.send_loop(request, deadline_s=540, should_stop=lambda: True)
            self.assertEqual((stopped.outcome, stopped.stopped, stopped.exchanges), ('not_sent', True, ()))

    def test_v1s_replay_and_design_v2s_never_replay_each_others_requests(self):
        v1_replay = ReplayInterpreter(self.tmp)
        v1_request = v1_replay.build_request(TEXT, PAGES, KIND)
        self.record(v1_request, encoded(envelope()))
        self.record(self.extracted, self.data)
        self.assertEqual(v1_replay.send(v1_request, deadline_s=5).outcome, 'succeeded')  # v1's own still replays
        for replay, request in ((v1_replay, self.extracted), (v1_replay, self.appraised.request),
                                (self.replay, v1_request)):
            with self.subTest(replay=type(replay).__name__, version=request.adapter_version):
                exchange = replay.send(request, deadline_s=5)
                self.assertEqual((exchange.outcome, exchange.response_bytes), ('not_sent', None))
                self.assertIn('different provider or adapter version', exchange.error)


# --- AMENDMENT-2 (1.8): the Fable recordings ------------------------------------------------------------------------------

class FableRecordingTests(OfflineTestCase):
    """_Recordings for ReplayInterpreterF, read directly: the folder and the suffix are its interpreter's, and the
    stream's end test decides whether a recording is a whole answer."""

    def setUp(self):
        super().setUp()
        self.folder = self.tmp / 'anthropic'
        self.folder.mkdir(mode=0o700)
        self.replay = ReplayInterpreterF(self.tmp)

    def test_a_complete_recording_replays_as_an_answer(self):
        raw = streams.answer_stream()
        write_file(self.folder / f'{"a" * 64}.sse', raw)
        exchange = self.replay.recorded('a' * 64)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.response_bytes,
                          exchange.response_sha256, exchange.usage, exchange.usage_basis, exchange.endpoint,
                          exchange.requested_model, exchange.returned_model, exchange.response_id, exchange.error),
                         ('succeeded', False, None, raw, hashlib.sha256(raw).hexdigest(), {}, USAGE_BASIS, '',
                          'claude-fable-5-2', 'claude-fable-5-2', streams.MESSAGE_ID, ''))
        self.assertEqual((self.replay.recording_folder, self.replay.recording_suffix, self.replay.mode,
                          self.replay.endpoint, self.replay.name, self.replay.adapter_version),
                         ('anthropic', '.sse', 'replay', '', 'anthropic', interpretation.ADAPTER_VERSION_V3))
        # Gemini's replay interpreters keep their folder and suffix
        self.assertEqual((ReplayInterpreterV2.recording_folder, ReplayInterpreterV2.recording_suffix,
                          ReplayInterpreter.recording_folder, ReplayInterpreter.recording_suffix),
                         ('gemini', '.json', 'gemini', '.json'))

    def test_an_incomplete_recording_replays_unknown_with_its_bytes(self):
        events = streams.answer_events()
        for number, raw in enumerate((streams.sse(*events[:-1]), streams.sse(*events)[:-1],
                                      streams.sse(*events[:3]), b'')):
            with self.subTest(size=len(raw)):
                sha = f'{number:064x}'
                write_file(self.folder / f'{sha}.sse', raw)
                exchange = self.replay.recorded(sha)
                self.assertEqual((exchange.outcome, exchange.sent, exchange.response_bytes, exchange.usage,
                                  exchange.usage_basis, exchange.error),
                                 ('unknown', False, raw, {}, USAGE_BASIS, INCOMPLETE_RECORDING))
                self.assertIsNone(fable_adapter.classify(exchange.outcome, exchange.http_status,
                                                         exchange.response_bytes))
                self.assertEqual(holds.classify(exchange.outcome, exchange.http_status, exchange.response_bytes,
                                                adapter_version=interpretation.ADAPTER_VERSION_V3).effect,
                                 holds.UNKNOWN)

    def test_a_missing_or_unsafe_recording_is_not_sent(self):
        self.assertEqual(self.replay.recorded('b' * 64).error, 'No recorded response for this request.')
        write_file(self.tmp / 'gemini.json', streams.answer_stream())
        (self.tmp / 'gemini').mkdir()
        write_file(self.tmp / 'gemini' / f'{"c" * 64}.json', streams.answer_stream())
        self.assertEqual(self.replay.recorded('c' * 64).error, 'No recorded response for this request.')
        self.assertEqual(ReplayInterpreterF(self.tmp / 'absent').recorded('c' * 64).error,
                         'The replay directory is not available.')
        small = ReplayInterpreterF(self.tmp, max_response_bytes=64)
        write_file(self.folder / f'{"d" * 64}.sse', streams.answer_stream())
        self.assertEqual(small.recorded('d' * 64).error, 'The recorded response is larger than 64 bytes.')
        with self.assertRaises(ValueError):
            ReplayInterpreterF('')


class FableReplayTests(streams.FablePinned, OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.folder = self.tmp / 'anthropic'
        self.folder.mkdir(mode=0o700)
        self.replay = ReplayInterpreterF(self.tmp)
        self.extracted = self.replay.build_extraction_request(TEXT, PAGES, KIND)
        self.data = streams.answer_stream(streams.pass_1_answer())
        self.appraised = self.replay.build_appraisal_request(TEXT, PAGES, KIND, self.extracted, self.data,
                                                             check=streams.no_findings)
        self.answer = streams.answer_stream(streams.verdicts_for(self.appraised.built))

    def record(self, request: ProviderRequest, raw: bytes):
        return write_file(self.folder / f'{request.canonical_sha256}.sse', raw)

    def live(self, request, raw):
        """The same bytes as a live exchange (a fake session behind the network guard)."""
        credentials = write_file(self.tmp / f'anthropic-{request.canonical_sha256[:8]}.env', anthropic_env())
        session = FakeSession(FakeResponse(200, raw, headers={'request-id': streams.REQUEST_ID}))
        return fable_adapter.FableInterpreter(credentials, session_factory=lambda: session).send(request,
                                                                                                deadline_s=60)

    def test_an_sse_recording_is_read_exactly_as_live(self):
        self.record(self.extracted, self.data)
        self.record(self.appraised.request, self.answer)
        for request, raw, purpose in ((self.extracted, self.data, fable_adapter.EXTRACTION),
                                      (self.appraised.request, self.answer, fable_adapter.APPRAISAL)):
            with self.subTest(purpose=purpose):
                self.assertEqual(self.replay.purpose(request), purpose)
                replayed, live = self.replay.send(request, deadline_s=5), self.live(request, raw)
                self.assertEqual((replayed.outcome, replayed.sent, replayed.usage, replayed.usage_basis,
                                  replayed.endpoint), ('succeeded', False, {}, USAGE_BASIS, ''))
                self.assertEqual((live.outcome, live.sent), ('succeeded', True))
                for field in ('response_bytes', 'response_sha256', 'returned_model', 'response_id', 'requested_model'):
                    self.assertEqual(getattr(replayed, field), getattr(live, field), field)
                self.assertEqual(fable_adapter.classify(replayed.outcome, replayed.http_status,
                                                        replayed.response_bytes),
                                 fable_adapter.classify(live.outcome, None, live.response_bytes))
                recorded = []
                with participants_loop.recording(recorded.append):
                    outcome = self.replay.send_loop(request, deadline_s=540)
                self.assertEqual((outcome.outcome, outcome.final.sent, len(outcome.exchanges)), ('succeeded', False, 1))
                self.assertEqual((recorded[0].turn, recorded[0].request_sha256), (1, request.canonical_sha256))
        read = self.replay.read_extraction(self.extracted, self.replay.send(self.extracted, deadline_s=5).response_bytes,
                                           self.appraised.unit_count)
        self.assertEqual(read, self.appraised.answer)
        appraised = self.replay.read_appraisal(self.appraised, self.appraised.request,
                                               self.replay.send(self.appraised.request, deadline_s=5).response_bytes)
        self.assertEqual([verdict.content for verdict in appraised.verdicts],
                         [claim.content for claim in self.appraised.built.claim_set.claims])
        self.assertEqual(sorted(path.name for path in self.folder.iterdir()),
                         sorted(f'{sha}.sse' for sha in (self.extracted.canonical_sha256,
                                                         self.appraised.request.canonical_sha256)))

    def test_an_incomplete_recording_replays_unknown_as_a_live_one_does(self):
        raw = streams.sse(*streams.answer_events(streams.pass_1_answer())[:-1])
        self.record(self.extracted, raw)
        outcome = self.replay.send_loop(self.extracted, deadline_s=540)
        self.assertEqual((outcome.outcome, outcome.final.response_bytes, outcome.final.usage, outcome.final.error),
                         ('unknown', raw, {}, INCOMPLETE_RECORDING))
        live = self.live(self.extracted, raw)
        self.assertEqual((live.outcome, live.response_bytes, live.usage), ('unknown', raw, {}))
        self.assertIn('ended before its end event', live.error)

    def test_a_changed_instruction_byte_finds_no_recording(self):
        self.record(self.extracted, self.data)
        self.assertEqual(self.replay.send(self.extracted, deadline_s=5).outcome, 'succeeded')
        with mock.patch.object(extract_prompt, 'INSTRUCTIONS_3', extract_prompt.INSTRUCTIONS_3 + ' '):
            changed = self.replay.build_extraction_request(TEXT, PAGES, KIND)
            self.assertNotEqual(changed.canonical_sha256, self.extracted.canonical_sha256)
            exchange = self.replay.send(changed, deadline_s=5)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.error),
                         ('not_sent', False, 'No recorded response for this request.'))

    def test_gemini_and_fable_never_replay_each_others_requests(self):
        gemini = ReplayInterpreterV2(self.tmp)
        (self.tmp / 'gemini').mkdir()
        self.record(self.extracted, self.data)
        for replay, request in ((gemini, self.extracted), (self.replay, gemini.build_extraction_request(TEXT, PAGES,
                                                                                                      KIND))):
            with self.subTest(replay=type(replay).__name__):
                exchange = replay.send(request, deadline_s=5)
                self.assertEqual((exchange.outcome, exchange.response_bytes), ('not_sent', None))
                self.assertIn('different provider or adapter version', exchange.error)
        with mock.patch.object(ReplayInterpreterF, 'recorded', side_effect=AssertionError('read')):
            stopped = self.replay.send_loop(self.extracted, deadline_s=540, should_stop=lambda: True)
        self.assertEqual((stopped.outcome, stopped.stopped, stopped.exchanges), ('not_sent', True, ()))
