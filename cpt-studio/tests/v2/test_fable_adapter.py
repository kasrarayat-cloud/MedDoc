"""studio/interpretation/fable_adapter.py, the interpreter's connector for Claude Fable 5.2 (docs/gemini-migration/
AMENDMENT-2.md section 1 as its refutation revised it, AMEND2-REFUTATIONS.md CONN-1 to CONN-7; DECISIONS D275, D278;
step F1 of section 10). TEXT-ONLY and SYNTHETIC: tests/v2/test_claims.py's synthetic note and its hand-built pass-1
answer (checked there against the acceptance set's DEV-EXCLUSION hashes), appraisal answers built here for its claims,
and answer streams, error bodies, refusals and cut streams constructed in this module. Every send goes to a fake
session behind the network guard of tests/test_participants_support, or to a loopback server this module starts on
127.0.0.1 behind a loopback guard that fails a test reaching any other address; every key is fake, and nothing is sent
anywhere.

What is proved, against section 10's F1 row and 11.1:
- the names of 1.1 (NamesTests): the provider, model, adapter version, endpoint, effort, output maximum (D278: the
  guard 128,000 / 100 + 40 <= the 1,320 s deadline), the body keys, VENDOR with its describe and complete hooks, and the
  anthropic-version pinned to interpretation.API_VERSION_V3, never to the Fable participant's [R:replay-R8];
- both bodies exactly (BodyTests: keys, model, effort, max_tokens, stream, the cache marker on pass 1 only, the format on
  pass 2 only, no forbidden field), body_kind refusing every altered body, the headers set at send time (SendTests);
- the stream reader of 1.4 on constructed streams, rule by rule (AssembleTests); ``complete`` true only at message_stop
  or an error event (CompleteTests); ``describe`` on streams and error bodies, with no usage from a stream without
  message_delta, an error-ended one included [R:connector-CONN-3] (DescribeTests);
- every row of 1.5's table with a constructed body, type-before-status precedence, 1.5's precedence for 200 streams (an
  error event first FAILED, never HOLD model; another model then an error HOLD model; a stream opening with
  content_block_start HOLD model) [R:connector-CONN-4], and the refusal category kept as one word, never the
  explanation (ClassifyTests); the model and fallback holds (1.6; FallbackTests, by reference to the Fable participant's
  rule and test vectors);
- the envelope of 1.4 (EnvelopeTests) and the two readers (ReadTests);
- the send of 1.3: one exchange, no retry, a member's Stop, a continuation refused (SendTests); an incomplete stream
  recorded UNKNOWN with its bytes, live and replay, and a cut stream, a deadline cut and a cap overflow each UNKNOWN with
  the bytes read before the stop and no usage (CutStreamTests over fake sessions, LoopbackTests over a real socket: a
  chunked body cut mid-chunk raises ChunkedEncodingError inside iter_content) [R:connector-CONN-6][R:connector-CONN-2];
- the configured interpreter of 1.11 and 1.12 (ConfiguredTests);
- no jobs.py call reaches the Gemini interpreter, and the module imports nothing the sentinel denies (GuardTests), and
  mypy --strict passes on the module (GuardTests).
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest import mock

import requests
from django.conf import settings
from django.test import SimpleTestCase, override_settings

from studio import interpretation
from studio.interpretation import adapter, fable_adapter
from studio.interpretation.contract import appraise_prompt, appraise_read, appraise_schema, extract_prompt, extract_read
from studio.participants import anthropic_fable
from studio.participants import http as participants_http
from studio.participants import loop as participants_loop
from studio.providers.base import ProviderUnavailable, canonical_body, request_sha256
from studio.types import ProviderRequest
from tests.test_participants_support import (ANTHROPIC_KEY, ANTHROPIC_WORKSPACE, SECRETS, FakeClock, FakeResponse,
                                             FakeSession, NetworkBlocked, OfflineTestCase, anthropic_env, write_file)
from tests.v2 import test_claims as fixtures
from tests.v2.test_adapter import KIND, PAGES, TEXT

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'fable_adapter.py'
JOBS = APP / 'studio' / 'jobs.py'
MODEL = 'claude-fable-5-2'
MESSAGE_ID = 'msg_synthetic_0001'
REQUEST_ID = 'req_synthetic_0001'
# no refusal or sentence of this module names a provider or a model (D22)
NAMES = ('anthropic', 'claude', 'fable', 'gemini', 'google', 'opus', 'sonnet')
START_USAGE = {'input_tokens': 4210, 'cache_creation_input_tokens': 44466, 'cache_read_input_tokens': 0,
               'cache_creation': {'ephemeral_5m_input_tokens': 44466, 'ephemeral_1h_input_tokens': 0},
               'output_tokens': 1, 'service_tier': 'standard'}
DELTA_USAGE = {'output_tokens': 15210, 'output_tokens_details': {'thinking_tokens': 9120}}
FINAL_USAGE = {**START_USAGE, **DELTA_USAGE}
CATEGORY_EXPLANATION = 'SYNTHETIC-EXPLANATION-TEXT that a model might write and is never repeated'


# --- answer streams, built here ------------------------------------------------------------------------------------------

def sse(*events, names=True, crlf=False) -> bytes:
    """The SSE bytes of ``events`` (dicts, or raw strings already rendered), one event: and one data: line each."""
    out = []
    for event in events:
        if isinstance(event, str):
            out.append(event)
            continue
        lines = ([f'event: {event["type"]}'] if names else []) + [f'data: {json.dumps(event, ensure_ascii=False)}']
        out.append('\n'.join(lines) + '\n\n')
    text = ''.join(out)
    return (text.replace('\n', '\r\n') if crlf else text).encode()


def start(model=MODEL, *, usage=None, message_id=MESSAGE_ID, **message) -> dict:
    return {'type': 'message_start', 'message': {'id': message_id, 'type': 'message', 'role': 'assistant',
                                                 'content': [], 'model': model, 'stop_reason': None,
                                                 'stop_sequence': None,
                                                 'usage': copy.deepcopy(START_USAGE if usage is None else usage),
                                                 **message}}


def block_start(index, kind='text', **fields) -> dict:
    block = {'type': kind, **({'text': ''} if kind == 'text' else {}),
             **({'thinking': '', 'signature': ''} if kind == 'thinking' else {}), **fields}
    return {'type': 'content_block_start', 'index': index, 'content_block': block}


def text_delta(index, text) -> dict:
    return {'type': 'content_block_delta', 'index': index, 'delta': {'type': 'text_delta', 'text': text}}


def thinking_delta(index, text='') -> dict:
    return {'type': 'content_block_delta', 'index': index, 'delta': {'type': 'thinking_delta', 'thinking': text}}


def signature_delta(index, signature='c3ludGhldGljLXNpZ25hdHVyZQ==') -> dict:
    return {'type': 'content_block_delta', 'index': index, 'delta': {'type': 'signature_delta', 'signature': signature}}


def block_stop(index) -> dict:
    return {'type': 'content_block_stop', 'index': index}


def message_delta(stop_reason='end_turn', *, usage=None, stop_details=None, **delta) -> dict:
    return {'type': 'message_delta', 'delta': {'stop_reason': stop_reason, 'stop_sequence': None,
                                               **({'stop_details': stop_details} if stop_details is not None else {}),
                                               **delta},
            'usage': copy.deepcopy(DELTA_USAGE if usage is None else usage)}


def stop() -> dict:
    return {'type': 'message_stop'}


def ping() -> dict:
    return {'type': 'ping'}


def error_event(kind='overloaded_error', message='Synthetic: the service is overloaded.') -> dict:
    return {'type': 'error', 'error': {'type': kind, 'message': message}}


def answer_events(text='{"synthetic": true}', *, model=MODEL, stop_reason='end_turn', thinking=True, pieces=3,
                  stop_details=None, tail=True) -> list:
    """A whole answer: message_start, a ping, a thinking block (omitted text, its signature), one text block fed in
    ``pieces`` deltas, message_delta and message_stop (``tail`` False: neither)."""
    events = [start(model), ping()]
    index = 0
    if thinking:
        events += [block_start(0, 'thinking'), thinking_delta(0), signature_delta(0), block_stop(0)]
        index = 1
    if text is not None:
        size = max(1, -(-len(text) // pieces))
        events.append(block_start(index, 'text'))
        events += [text_delta(index, text[at:at + size]) for at in range(0, len(text), size)]
        events.append(block_stop(index))
    if tail:
        events += [message_delta(stop_reason, stop_details=stop_details), stop()]
    return events


def answer_stream(text='{"synthetic": true}', **options) -> bytes:
    return sse(*answer_events(text, **options))


def error_body(kind, message='Synthetic: an error message that is never kept.') -> bytes:
    return json.dumps({'type': 'error', 'error': {'type': kind, 'message': message},
                       'request_id': REQUEST_ID}).encode()


def pass_1_answer() -> str:
    return json.dumps(fixtures.note_answer())


def verdicts_for(built, verdict='supports') -> str:
    """A synthetic pass-2 answer text for ``built`` (appraise_prompt.Request): one verdict per claim."""
    return json.dumps({'verdicts': [{'claim': claim.id, 'verdict': verdict, 'attached': 'yes', 'qualifiers': [],
                                     'evidence': list(claim.units[:1])} for claim in built.claim_set.claims],
                       'unlisted': []})


def no_findings(text, pages, answer):
    return {}


def imports(source: str) -> set:
    """Every module a source imports, and every name it imports from one (as module.name), by its syntax tree."""
    import ast

    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found |= {f'{node.module}.{alias.name}' for alias in node.names}
    return found


def stored(request: ProviderRequest, **changes) -> ProviderRequest:
    fields = dict(provider=request.provider, adapter_version=request.adapter_version, body=request.body,
                  canonical_sha256=request.canonical_sha256, contexts=request.contexts)
    fields.update(changes)
    return ProviderRequest(**fields)


class FablePinned:
    """The Fable bodies are built under their pins (A2 8.2), which the integration owner writes after the build's last
    repair (D202): the adapter's tests do not depend on when they are written, so the two pin checks of the Fable path
    (contract/extract_prompt.check_pins_fable and contract/appraise_prompt.check_pins_fable, step F2's) are passed here;
    F2's pin tests judge the written values."""

    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.object(extract_prompt, 'check_pins_fable', lambda: None))
        self.enterContext(mock.patch.object(appraise_prompt, 'check_pins_fable', lambda: None))

    def extraction(self):
        return fable_adapter.build_extraction_request(TEXT, PAGES, KIND)

    def appraisal(self, extraction=None, raw=None):
        extraction = extraction or self.extraction()
        raw = answer_stream(pass_1_answer()) if raw is None else raw
        return fable_adapter.build_appraisal_request(TEXT, PAGES, KIND, extraction, raw, check=no_findings)


# --- 1.1 ---------------------------------------------------------------------------------------------------------------

class NamesTests(SimpleTestCase):
    def test_the_names_of_1_1(self):
        self.assertEqual((fable_adapter.NAME, fable_adapter.MODEL, fable_adapter.ADAPTER_VERSION_V3),
                         ('anthropic', MODEL, 'anthropic-messages@cptstudio-interp-1'))
        self.assertEqual((fable_adapter.NAME, fable_adapter.MODEL),
                         (interpretation.PROVIDER_V3, interpretation.MODEL_V3))
        self.assertEqual(fable_adapter.ENDPOINT, 'https://api.anthropic.com/v1/messages')
        self.assertEqual((fable_adapter.EFFORT, fable_adapter.MAX_TOKENS), ('high', 128000))
        self.assertEqual(fable_adapter.BODY_KEYS,
                         {'model', 'max_tokens', 'stream', 'output_config', 'system', 'messages'})
        self.assertEqual(dict(fable_adapter.READ_MODELS), {interpretation.ADAPTER_VERSION_V3: (MODEL,)})
        self.assertEqual(fable_adapter.PURPOSES, (interpretation.PURPOSE, interpretation.APPRAISAL_PURPOSE))
        vendor = fable_adapter.VENDOR
        self.assertEqual((vendor.label, vendor.request_id_header, vendor.describe, vendor.complete),
                         ('Anthropic', 'request-id', fable_adapter.describe, fable_adapter.complete))
        # the dormant Gemini adapter keeps its names and its vendor without the hook (adapter.py is not edited)
        self.assertEqual((adapter.NAME, adapter.MODEL, adapter.VENDOR.complete), ('gemini', 'gemini-4-carbon', None))
        self.assertEqual(len(interpretation.ADAPTER_VERSION_V3), 37)  # ProviderRun.adapter_version holds 40

    def test_the_api_version_is_pinned_to_the_adapter_versions_value_never_the_participants(self):
        self.assertEqual(fable_adapter.API_VERSION, interpretation.API_VERSION_V3)
        source = MODULE.read_text(encoding='utf-8')
        self.assertIn("API_VERSION = '2026-10-21'", source)  # its own constant (8.4 [R:replay-R8])
        self.assertFalse({name for name in imports(source) if 'anthropic_fable' in name})  # nothing of the participant
        self.assertEqual(fable_adapter.InterpreterF.api_version, fable_adapter.API_VERSION)
        # 1.11: the existing Anthropic credential, by the participants' own loader (ops/install.py's INTERPRETER row
        # names this module and 'load_anthropic_credentials')
        from studio.participants import credentials

        self.assertIs(fable_adapter.load_anthropic_credentials, credentials.load_anthropic_credentials)

    def test_the_output_maximum_fits_the_deadlines_and_the_hold_reasons_fit_the_table(self):
        # D278 and 1.12: 128,000 output tokens at 100 tokens per second plus 40 s, at most each send deadline
        for deadline in (settings.INTERPRETER_SEND_DEADLINE_SECONDS, settings.APPRAISER_SEND_DEADLINE_SECONDS,
                         fable_adapter.SEND_DEADLINE_SECONDS, fable_adapter.APPRAISAL_SEND_DEADLINE_SECONDS):
            self.assertLessEqual(fable_adapter.MAX_TOKENS / 100 + 40, deadline)
        self.assertEqual(fable_adapter.DEFAULT_MAX_RESPONSE_BYTES, settings.INTERPRETER_MAX_RESPONSE_BYTES)
        from studio.models import InterpreterHold

        self.assertEqual(fable_adapter.HOLD_REASONS,
                         (InterpreterHold.AUTH, InterpreterHold.PERMISSION, InterpreterHold.QUOTA,
                          InterpreterHold.MODEL, InterpreterHold.REFUSED, InterpreterHold.DECLINED))
        reason = InterpreterHold._meta.get_field('reason').max_length
        self.assertTrue(all(len(hold) <= reason for hold in fable_adapter.HOLD_REASONS))
        self.assertEqual(InterpreterHold._meta.get_field('vendor_status').max_length, 40)  # _TYPE keeps at most 40
        self.assertEqual((fable_adapter._TYPE.fullmatch('a' * 40) is not None,
                          fable_adapter._TYPE.fullmatch('a' * 41) is None), (True, True))


# --- 1.2 ---------------------------------------------------------------------------------------------------------------

FORBIDDEN = ('thinking', 'temperature', 'top_p', 'top_k', 'tools', 'tool_choice', 'stop_sequences', 'metadata',
             'fallbacks')


class BodyTests(FablePinned, OfflineTestCase):
    def test_pass_1s_body_exactly(self):
        request = self.extraction()
        body = request.body
        framed = extract_prompt.framed(TEXT, PAGES, KIND)
        self.assertEqual(body, {'model': MODEL, 'max_tokens': 128000, 'stream': True,
                                'output_config': {'effort': 'high'},
                                'system': [{'type': 'text', 'text': extract_prompt.INSTRUCTIONS_3,
                                            'cache_control': {'type': 'ephemeral'}}],
                                'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': framed}]}]})
        self.assertEqual((request.provider, request.adapter_version, request.contexts),
                         ('anthropic', interpretation.ADAPTER_VERSION_V3, (TEXT,)))
        self.assertEqual(request.canonical_sha256, request_sha256(body))
        self.assertEqual(fable_adapter.body_kind(body), (fable_adapter.EXTRACTION, ''))
        for name in FORBIDDEN:
            self.assertNotIn(name, body)
        self.assertEqual(fable_adapter.build_extraction_request(TEXT, PAGES, KIND), request)  # pure

    def test_pass_2s_body_exactly(self):
        appraisal = self.appraisal()
        body = appraisal.request.body
        self.assertEqual(body, {'model': MODEL, 'max_tokens': 128000, 'stream': True,
                                'output_config': {'effort': 'high',
                                                  'format': {'type': 'json_schema',
                                                             'schema': appraise_schema.LOCAL_SCHEMA}},
                                'system': [{'type': 'text', 'text': appraise_prompt.INSTRUCTIONS}],
                                'messages': [{'role': 'user', 'content': [{'type': 'text',
                                                                           'text': appraisal.built.turn}]}]})
        self.assertNotIn('cache_control', json.dumps(body['system']))  # 7.2: no breakpoint on pass 2
        self.assertIsNot(body['output_config']['format']['schema'], appraise_schema.LOCAL_SCHEMA)  # a deep copy
        self.assertEqual(fable_adapter.body_kind(body), (fable_adapter.APPRAISAL, ''))
        self.assertEqual(appraisal.request.adapter_version, interpretation.ADAPTER_VERSION_V3)
        for name in FORBIDDEN:
            self.assertNotIn(name, body)
        again = self.appraisal()
        self.assertEqual(again.request, appraisal.request)  # a pure function of the revision and the stored bytes
        # 2.2 [R:replay-R7]: the canonical body is sent, its keys sorted at every depth - the schema's verdict
        # properties go out as attached, claim, evidence, qualifiers, verdict, whatever order LOCAL_SCHEMA declares
        sent = canonical_body(body).decode()
        schema = sent[sent.index('"schema":'):]
        places = [schema.index(f'"{name}":') for name in ('attached', 'claim', 'evidence', 'qualifiers', 'verdict')]
        self.assertEqual(places, sorted(places))

    def test_body_kind_refuses_every_altered_body(self):
        for request in (self.extraction(), self.appraisal().request):
            for name, change in (
                    ('temperature', lambda body: body.update(temperature=0)),
                    ('thinking', lambda body: body.update(thinking={'type': 'adaptive'})),
                    ('tools', lambda body: body.update(tools=[])),
                    ('fallbacks', lambda body: body.update(fallbacks='default')),
                    ('a second message', lambda body: body['messages'].append(
                        {'role': 'user', 'content': [{'type': 'text', 'text': 'Synthetic second turn.'}]})),
                    ('a changed instruction byte', lambda body: body['system'][0].update(
                        text=body['system'][0]['text'] + ' ')),
                    ('another model', lambda body: body.update(model='claude-opus-5-5')),
                    ('another effort', lambda body: body['output_config'].update(effort='max')),
                    ('another maximum', lambda body: body.update(max_tokens=64000)),
                    ('no stream', lambda body: body.update(stream=False)),
                    ('an assistant prefill', lambda body: body['messages'].append(
                        {'role': 'assistant', 'content': [{'type': 'text', 'text': '{'}]})),
                    ('a changed user turn', lambda body: body['messages'][0]['content'][0].update(
                        text=body['messages'][0]['content'][0]['text'] + '\nSynthetic extra line.'))):
                with self.subTest(name, kind=fable_adapter.body_kind(request.body)[0]):
                    body = copy.deepcopy(request.body)
                    change(body)
                    self.assertEqual(fable_adapter.body_kind(body), ('', fable_adapter.NOT_BUILT))
        # the cache marker belongs to pass 1 alone, the format to pass 2 alone
        first = copy.deepcopy(self.extraction().body)
        first['output_config']['format'] = {'type': 'json_schema', 'schema': appraise_schema.LOCAL_SCHEMA}
        self.assertEqual(fable_adapter.body_kind(first), ('', fable_adapter.NOT_BUILT))
        second = copy.deepcopy(self.appraisal().request.body)
        second['system'][0]['cache_control'] = {'type': 'ephemeral'}
        self.assertEqual(fable_adapter.body_kind(second), ('', fable_adapter.NOT_BUILT))
        # a pin that no longer matches refuses the bodies it pins (no request of this version can be checked)
        first, second = self.extraction().body, self.appraisal().request.body
        with mock.patch.object(extract_prompt, 'check_pins_fable', side_effect=RuntimeError('pin')):
            self.assertEqual(fable_adapter.body_kind(first), ('', fable_adapter.UNPINNED_V3))
        with mock.patch.object(appraise_prompt, 'check_pins_fable', side_effect=RuntimeError('pin')):
            self.assertEqual(fable_adapter.body_kind(second), ('', fable_adapter.UNPINNED_V3))

    def test_the_gemini_bodies_are_never_fable_bodies(self):
        gemini = adapter.build_extraction_request(TEXT, PAGES, KIND)
        self.assertEqual(fable_adapter.body_kind(gemini.body), ('', fable_adapter.NOT_BUILT))
        self.assertEqual(fable_adapter.body_kind(None), ('', fable_adapter.NOT_BUILT))

    def test_a_text_that_cannot_be_framed_is_not_built_with_its_reason(self):
        for text, reason in (('[S1] synthetic label of its own.', extract_prompt.Unframed.LABEL.value),
                             ('   \n', extract_prompt.Unframed.EMPTY.value)):
            with self.subTest(reason):
                with self.assertRaises(fable_adapter.NotBuilt) as caught:
                    fable_adapter.build_extraction_request(text, (), 'paste')
                self.assertEqual((caught.exception.reason, caught.exception.effect),
                                 (reason, fable_adapter.UNBUILT))
        with self.assertRaises(fable_adapter.NotBuilt) as caught:
            fable_adapter.build_extraction_request('synthetic\x00text', (), 'paste')
        self.assertEqual(caught.exception.reason, adapter.NUL)
        with self.assertRaises(fable_adapter.NotBuilt) as caught:
            fable_adapter.build_extraction_request(TEXT, PAGES, KIND, max_bytes=1024)
        self.assertEqual(caught.exception.reason, adapter.SIZE)


class AppraisalRequestTests(FablePinned, OfflineTestCase):
    def test_the_stored_first_reading_must_be_this_revisions_and_readable(self):
        extraction = self.extraction()
        with self.assertRaises(fable_adapter.NotBuilt) as caught:
            self.appraisal(stored(extraction, canonical_sha256='0' * 64))
        self.assertEqual((caught.exception.reason, caught.exception.effect), (adapter.STORED, adapter.UNBUILT))
        for raw, stage in ((answer_stream('{"x": '), 'envelope'), (answer_stream('{}'), 'schema'),
                           (answer_stream(pass_1_answer(), stop_reason='max_tokens'), 'envelope'),
                           (answer_stream(pass_1_answer(), model='claude-opus-5-5'), 'envelope')):
            with self.subTest(stage=stage):
                with self.assertRaises(fable_adapter.NotBuilt) as caught:
                    self.appraisal(extraction, raw)
                refused = caught.exception
                self.assertEqual((refused.reason, refused.effect, refused.refusal.stage),
                                 (adapter.STORED, adapter.REFUSED, stage))

    def test_the_claim_bound_is_the_fable_paths_and_refuses_before_a_body(self):
        from studio.interpretation.contract import claims

        appraisal = self.appraisal()
        count = len(appraisal.built.claim_set.claims)
        self.assertGreater(claims.CLAIM_BOUND_V3, claims.CLAIM_BOUND)  # 8.2: 1,000 on this path, 640 kept for Gemini
        with mock.patch.object(claims, 'CLAIM_BOUND_V3', count - 1):
            with self.assertRaises(fable_adapter.NotBuilt) as caught:
                self.appraisal()
        refused = caught.exception
        self.assertEqual((refused.reason, refused.effect, refused.claims), (adapter.CLAIMS, adapter.TOO_LONG, count))
        self.assertIn(f'more than the {count - 1:,} one request may carry', str(refused))


# --- 1.4: the stream ---------------------------------------------------------------------------------------------------

class AssembleTests(SimpleTestCase):
    def assembled(self, raw):
        stream, code, why = fable_adapter.assemble(raw)
        self.assertEqual((code, why), ('', ''))
        return stream

    def refused(self, raw, code):
        stream, found, why = fable_adapter.assemble(raw)
        self.assertEqual((stream, found), (None, code), why)
        for name in NAMES:
            self.assertNotIn(name, why.lower())
        return why

    def test_a_whole_answer_assembles_into_one(self):
        stream = self.assembled(answer_stream('{"a": 1, "b": "two"}', pieces=4))
        self.assertEqual((stream.text, stream.model, stream.message_id, stream.stop_reason, stream.blocks,
                          stream.final_usage, dict(stream.usage), stream.unknown_events, stream.errored),
                         ('{"a": 1, "b": "two"}', MODEL, MESSAGE_ID, 'end_turn', ('thinking', 'text'), True,
                          FINAL_USAGE, 0, False))
        # two text blocks are joined in order; a redacted thinking block and a thinking block's deltas are never read
        raw = sse(start(), block_start(0, 'text'), text_delta(0, 'one '), block_stop(0),
                  block_start(1, 'redacted_thinking', data='c3ludGhldGlj'), block_stop(1),
                  block_start(2, 'thinking'), thinking_delta(2, 'synthetic thought'), signature_delta(2), block_stop(2),
                  block_start(3, 'text'), text_delta(3, 'two'), block_stop(3), message_delta(), stop())
        stream = self.assembled(raw)
        self.assertEqual((stream.texts, stream.text), (('one ', 'two'), 'one two'))

    def test_rule_1_lines_comments_and_event_names(self):
        events = answer_events('{"a": 1}')
        self.assertEqual(self.assembled(sse(*events, crlf=True)).text, '{"a": 1}')  # \r\n is read as \n
        self.assertEqual(self.assembled(sse(*events, names=False)).text, '{"a": 1}')  # the event: line is optional
        commented = sse(events[0]) + b': a synthetic comment\n' + sse(*events[1:])
        self.assertEqual(self.assembled(commented).text, '{"a": 1}')
        commented = sse(events[0], ': a synthetic comment line inside nothing\n\n', *events[1:])
        self.assertEqual(self.assembled(commented).text, '{"a": 1}')
        self.assertIn('not valid UTF-8', self.refused(sse(*events)[:-30] + b'\xff\xfe' + sse(*events)[-30:],
                                                       fable_adapter.UTF8))
        for raw, expect in (
                (sse(start()) + b'id: 7\n' + sse(*events[1:]), 'not an event or data line'),
                (sse(start()) + b'retry: 100\n\n', 'not an event or data line'),
                (sse(start()) + b'data\n\n', 'not an event or data line'),
                (b'event: message_start\n' + b'data: {"type": "message_start"}\n' + b'data: {}\n\n', 'repeats'),
                (b'event: ping\nevent: ping\ndata: {"type": "ping"}\n\n', 'repeats'),
                (sse(start()) + b'event: ping\n\n', 'has no data line'),
                (sse(start()) + b'data: {"type": "ping"\n\n', 'is not valid JSON'),
                (sse(start()) + b'data: {"type": "ping", "type": "ping"}\n\n', 'repeats a JSON object key'),
                (sse(start()) + b'data: ["ping"]\n\n', 'not an object naming its type'),
                (sse(start()) + b'event: ping\ndata: {"type": "message_stop"}\n\n', 'names another type')):
            with self.subTest(expect):
                self.assertIn(expect, self.refused(raw, fable_adapter.JSON))
        self.assertEqual(fable_adapter.assemble('not bytes')[1], fable_adapter.BYTES)

    def test_rule_2_pings_anywhere_and_unknown_events_skipped_and_counted(self):
        events = answer_events('{"a": 1}')
        pinged = [ping()] + [item for event in events for item in (event, ping())]
        stream = self.assembled(sse(*pinged))
        self.assertEqual((stream.text, stream.unknown_events), ('{"a": 1}', 0))
        unknown = {'type': 'synthetic_new_event', 'detail': 1}
        mixed = [unknown] + events[:3] + [unknown, unknown] + events[3:] + [unknown]
        stream = self.assembled(sse(*mixed))
        self.assertEqual((stream.text, stream.unknown_events), ('{"a": 1}', 4))

    def test_rule_3_message_start_first_and_once(self):
        events = answer_events('{"a": 1}')
        self.assertIn('starts its message twice', self.refused(sse(events[0], *events), fable_adapter.CONTENT))
        for message, expect in (({'type': 'other'}, 'empty assistant message'),
                                ({'role': 'user'}, 'empty assistant message'),
                                ({'content': [{'type': 'text', 'text': 'x'}]}, 'empty assistant message')):
            with self.subTest(message):
                self.assertIn(expect, self.refused(sse(start(**message), *events[1:]), fable_adapter.CONTENT))
        # a message id kept only when it fits the record
        self.assertEqual(self.assembled(sse(start(message_id='x' * 141), *events[1:])).message_id, '')
        self.assertEqual(self.assembled(sse(start(message_id='msg with space'), *events[1:])).message_id, '')

    def test_rule_4_blocks(self):
        head = [start()]
        tail = [message_delta(), stop()]
        for name, middle, expect in (
                ('a delta to an unopened block', [text_delta(0, 'x')], 'not open'),
                ('a delta to another index', [block_start(0), text_delta(1, 'x'), block_stop(0)], 'not open'),
                ('a block at the wrong index', [block_start(1), block_stop(1)], 'out of order'),
                ('a block opened inside another', [block_start(0), block_start(1), block_stop(1), block_stop(0)],
                 'out of order'),
                ('a stop of no open block', [block_stop(0)], 'not the open one'),
                ('a tool_use block', [block_start(0, 'tool_use', id='toolu_synthetic', name='x', input={}),
                                      block_stop(0)], 'of type tool_use'),
                ('a server_tool_use block', [block_start(0, 'server_tool_use'), block_stop(0)],
                 'of type server_tool_use'),
                ('a citations-bearing text block', [block_start(0, citations=[{'type': 'char_location'}]),
                                                    block_stop(0)], 'not plain text'),
                ('a citations_delta', [block_start(0), {'type': 'content_block_delta', 'index': 0,
                                                        'delta': {'type': 'citations_delta', 'citation': {}}},
                                       block_stop(0)], 'of type citations_delta'),
                ('a text_delta in a thinking block', [block_start(0, 'thinking'), text_delta(0, 'x'), block_stop(0)],
                 'of type text_delta to a thinking block'),
                ('a thinking_delta in a text block', [block_start(0), thinking_delta(0, 'x'), block_stop(0)],
                 'of type thinking_delta to a text block'),
                ('a delta in a redacted block', [block_start(0, 'redacted_thinking'), text_delta(0, 'x'),
                                                 block_stop(0)], 'to a redacted_thinking block'),
                ('a delta that carries no string', [block_start(0), {'type': 'content_block_delta', 'index': 0,
                                                                     'delta': {'type': 'text_delta', 'text': 7}},
                                                    block_stop(0)], 'carries no string'),
                ('a malformed thinking block', [block_start(0, 'thinking', signature=7), block_stop(0)],
                 'malformed thinking block'),
                ('a block left open', [block_start(0)], 'with a block open')):
            with self.subTest(name):
                self.assertIn(expect, self.refused(sse(*head, *middle, *tail), fable_adapter.CONTENT))
        # a thinking block that leaves out its strings at start is still one (they are never read)
        self.assertEqual(self.assembled(sse(start(), {'type': 'content_block_start', 'index': 0,
                                                      'content_block': {'type': 'thinking'}},
                                            signature_delta(0), block_stop(0), block_start(1), text_delta(1, '{}'),
                                            block_stop(1), message_delta(), stop())).text, '{}')

    def test_rules_5_and_6_message_delta_and_message_stop(self):
        events = answer_events('{"a": 1}')
        self.assertIn('message_delta twice', self.refused(sse(*events[:-1], message_delta(), stop()),
                                                          fable_adapter.CONTENT))
        self.assertIn('no message_delta', self.refused(sse(*events[:-2], stop()), fable_adapter.CONTENT))
        self.assertIn('goes on after its end', self.refused(sse(*events, block_start(2)), fable_adapter.CONTENT))
        self.assertIn('opens a block after message_delta',
                      self.refused(sse(*events[:-1], block_start(2), block_stop(2), stop()), fable_adapter.CONTENT))
        # skipped events after the end are harmless (an unknown one is still counted: rule 2)
        self.assertEqual(self.assembled(sse(*events, ping(), {'type': 'synthetic_new_event'})).unknown_events, 1)
        # message_delta's usage is merged over message_start's, field by field
        raw = sse(*events[:-2], message_delta(usage={'output_tokens': 7, 'input_tokens': 9}), stop())
        self.assertEqual(dict(self.assembled(raw).usage), {**START_USAGE, 'output_tokens': 7, 'input_tokens': 9})

    def test_rule_7_an_error_event_ends_the_stream_wherever_it_comes(self):
        for name, events, after_start in (
                ('first', [error_event()], False),
                ('after message_start', [start(), error_event()], True),
                ('inside a block', [start(), block_start(0), text_delta(0, '{'), error_event()], True)):
            with self.subTest(name):
                stream = self.assembled(sse(*events))
                self.assertEqual((stream.errored, stream.error_type, stream.error_after_start, stream.final_usage),
                                 (True, 'overloaded_error', after_start, False))
                self.assertNotIn('overloaded.', repr(stream))  # the message is never kept
        self.assertIn('goes on after its end', fable_adapter._scan(sse(error_event(), start())).failure[1])

    def test_an_end_that_never_comes_is_incomplete(self):
        events = answer_events('{"a": 1}')
        for cut in (sse(*events[:-1]), sse(*events)[:-1], sse(*events)[:-2], sse(*events)[:57], b''):
            with self.subTest(size=len(cut)):
                self.assertEqual(fable_adapter.assemble(cut)[1], fable_adapter.INCOMPLETE)
        whole = answer_stream('{"a": "café"}')  # the stream carries its text as UTF-8 (JSON need not escape it)
        cut = whole[:whole.index('é'.encode()) + 1]  # the bytes stop inside a two-byte UTF-8 sequence
        self.assertEqual(fable_adapter.assemble(cut)[1], fable_adapter.INCOMPLETE)  # a cut, never a refusal of UTF-8
        self.assertEqual(fable_adapter.describe(cut), ({}, MODEL, MESSAGE_ID))  # what came before the cut is read
        self.assertFalse(fable_adapter.complete(cut))
        self.assertEqual(self.assembled(whole).text, '{"a": "café"}')
        # a bad byte on a terminated line refuses the stream there, and never hides the model named before it
        bad = sse(start('claude-opus-5-5')) + b'event: ping\ndata: {"type": "ping", "x": "\xff"}\n\n' + sse(*events[1:])
        self.assertEqual(fable_adapter.assemble(bad)[1], fable_adapter.MODEL_CODE)
        self.assertEqual(fable_adapter.classify('succeeded', 200, bad).hold, 'model')
        bad_first = b'event: ping\ndata: {"type": "ping", "x": "\xff"}\n\n' + sse(*events)
        self.assertEqual(fable_adapter.assemble(bad_first)[1], fable_adapter.UTF8)  # nothing before it: refused


class CompleteTests(SimpleTestCase):
    def test_complete_only_at_message_stop_or_an_error_event(self):
        events = answer_events('{"a": 1}')
        self.assertTrue(fable_adapter.complete(sse(*events)))
        self.assertTrue(fable_adapter.complete(sse(*events, ping())))  # skipped events after the end
        self.assertTrue(fable_adapter.complete(sse(error_event())))
        self.assertTrue(fable_adapter.complete(sse(start(), block_start(0), error_event())))
        self.assertTrue(fable_adapter.complete(sse(*events[:-2], stop())))  # malformed, but ended: classify refuses it
        for cut in (sse(*events[:-1]), sse(*events)[:-1], sse(*events)[:-2], sse(start()), b'', sse(ping()),
                    sse(*events) + b'event: ping\ndata: {"type": "ping"}',  # an unterminated event after the end
                    sse(*events) + b'garbage\n\n', 'text', None):
            with self.subTest(cut=str(cut)[-40:]):
                self.assertFalse(fable_adapter.complete(cut))
        with mock.patch.object(fable_adapter, '_scan', side_effect=RuntimeError('synthetic')):
            self.assertFalse(fable_adapter.complete(sse(*events)))  # it never raises


class DescribeTests(SimpleTestCase):
    def test_a_stream_states_its_usage_model_and_id_only_when_message_delta_arrived(self):
        self.assertEqual(fable_adapter.describe(answer_stream()), (FINAL_USAGE, MODEL, MESSAGE_ID))
        events = answer_events()
        for name, raw in (('cut before message_delta', sse(*events[:-2])),
                          ('cut before message_stop', sse(*events[:-1])),
                          ('ended by an error event before message_delta', sse(*events[:-2], error_event())),
                          ('ended by an error event after message_delta', sse(*events[:-1], error_event())),
                          ('an unterminated last event', sse(*events)[:-1])):
            with self.subTest(name):
                self.assertEqual(fable_adapter.describe(raw), ({}, MODEL, MESSAGE_ID))  # [R:connector-CONN-3]
        self.assertEqual(fable_adapter.describe(sse(error_event())), ({}, '', ''))
        self.assertEqual(fable_adapter.describe(answer_stream(model='claude-opus-5-5')),
                         (FINAL_USAGE, 'claude-opus-5-5', MESSAGE_ID))  # as stated: the operator reads what answered

    def test_an_error_body_states_none_and_describe_never_raises(self):
        for raw in (error_body('overloaded_error'), b'', b'<html>synthetic</html>', b'\xff', 'text', None):
            with self.subTest(raw=str(raw)[:30]):
                self.assertEqual(fable_adapter.describe(raw), ({}, '', ''))
        with mock.patch.object(fable_adapter, '_scan', side_effect=RuntimeError('synthetic')):
            self.assertEqual(fable_adapter.describe(answer_stream()), ({}, '', ''))
        # http.post's reading of it: a usage only for a final stream, recorded as the hook returns it
        self.assertEqual(participants_http.described(fable_adapter.VENDOR, sse(*answer_events()[:-1])),
                         ({}, MODEL, MESSAGE_ID))


# --- 1.5 ---------------------------------------------------------------------------------------------------------------

def table():
    """1.5's table, one row per (label, outcome, status, body, kind, hold, word), with constructed bodies."""
    ok = answer_stream()
    other = answer_stream(model='claude-opus-5-5')
    return (
        ('a complete stream of claude-fable-5-2 at end_turn with text', 'succeeded', 200, ok, 'answered', '',
         'answered'),
        ('max_tokens', 'succeeded', 200, answer_stream('{"a": ', stop_reason='max_tokens'), 'too_long', '',
         'too long'),
        ('a refusal, any category', 'succeeded', 200,
         answer_stream(None, stop_reason='refusal', stop_details={'type': 'refusal', 'category': 'cyber',
                                                                  'explanation': CATEGORY_EXPLANATION}),
         'hold', 'declined', 'hold'),
        ('a refusal with no category', 'succeeded', 200,
         answer_stream('{"partial', stop_reason='refusal', stop_details={'type': 'refusal', 'category': None}),
         'hold', 'declined', 'hold'),
        ('another model', 'succeeded', 200, other, 'hold', 'model', 'hold'),
        ('no model named', 'succeeded', 200, sse(start(model=None), *answer_events()[1:]), 'hold', 'model', 'hold'),
        ('a fallback block', 'succeeded', 200,
         sse(start(), block_start(0, 'fallback', **{'from': {'model': MODEL}, 'to': {'model': 'claude-opus-4-8'}}),
             block_stop(0), *answer_events()[2:]), 'hold', 'model', 'hold'),
        ('a fallback usage iteration', 'succeeded', 200,
         sse(*answer_events()[:-2], message_delta(usage={'output_tokens': 9, 'iterations': [
             {'type': 'message'}, {'type': 'fallback_message', 'model': 'claude-opus-4-8'}]}), stop()),
         'hold', 'model', 'hold'),
        *[(f'stop_reason {reason}', 'succeeded', 200, answer_stream(stop_reason=reason), 'failed', '', 'refused')
          for reason in ('tool_use', 'pause_turn', 'stop_sequence', None, 'model_context_window_exceeded')],
        ('end_turn with no text block', 'succeeded', 200, answer_stream(None), 'failed', '', 'refused'),
        ('a stream that does not assemble', 'succeeded', 200,
         sse(start(), block_start(0, 'tool_use'), block_stop(0), message_delta(), stop()), 'failed', '', 'refused'),
        ('authentication_error (an error body)', 'failed', 401, error_body('authentication_error'), 'hold', 'auth',
         'hold'),
        ('HTTP 401 with no body', 'failed', 401, b'', 'hold', 'auth', 'hold'),
        ('authentication_error (a stream error event)', 'succeeded', 200, sse(start(), error_event(
            'authentication_error')), 'hold', 'auth', 'hold'),
        ('billing_error', 'failed', 402, error_body('billing_error'), 'hold', 'quota', 'hold'),
        ('HTTP 402 with no body', 'failed', 402, b'', 'hold', 'quota', 'hold'),
        ('permission_error', 'failed', 403, error_body('permission_error'), 'hold', 'permission', 'hold'),
        ('not_found_error', 'failed', 404, error_body('not_found_error'), 'hold', 'permission', 'hold'),
        ('HTTP 403 with a body that is not JSON', 'failed', 403, b'<html>forbidden</html>', 'hold', 'permission',
         'hold'),
        ('HTTP 404 with no body', 'failed', 404, b'', 'hold', 'permission', 'hold'),
        ('invalid_request_error', 'failed', 400, error_body('invalid_request_error'), 'hold', 'refused', 'hold'),
        ('HTTP 400 with no body', 'failed', 400, b'', 'hold', 'refused', 'hold'),
        ('HTTP 409, another 4xx', 'failed', 409, b'', 'hold', 'refused', 'hold'),
        ('HTTP 422, another 4xx', 'failed', 422, error_body('synthetic_unknown_error'), 'hold', 'refused', 'hold'),
        ('rate_limit_error (an error body with HTTP 429)', 'failed', 429, error_body('rate_limit_error'), 'failed', '',
         'retry later'),
        ('rate_limit_error (a stream error event)', 'succeeded', 200, sse(start(), error_event('rate_limit_error')),
         'failed', '', 'retry later'),
        ('HTTP 429 with no body', 'failed', 429, b'', 'hold', 'quota', 'hold'),
        ('HTTP 429 whose body is not JSON', 'failed', 429, b'<html>Too Many Requests</html>', 'hold', 'quota', 'hold'),
        ('HTTP 429 naming another failure', 'failed', 429, error_body('overloaded_error'), 'hold', 'quota', 'hold'),
        ('request_too_large', 'failed', 413, error_body('request_too_large'), 'failed', '', 'refused'),
        ('HTTP 413 with no body', 'failed', 413, b'', 'failed', '', 'refused'),
        ('overloaded_error (HTTP 529)', 'failed', 529, error_body('overloaded_error'), 'failed', '', 'retry later'),
        ('api_error', 'failed', 500, error_body('api_error'), 'failed', '', 'retry later'),
        ('timeout_error', 'failed', 504, error_body('timeout_error'), 'failed', '', 'retry later'),
        ('any other type', 'failed', 500, error_body('synthetic_new_error'), 'failed', '', 'retry later'),
        ('a 5xx with no body', 'failed', 503, b'', 'failed', '', 'retry later'),
        ('an unread redirect', 'failed', 307, b'', 'failed', '', 'retry later'),
        ('overloaded_error as the stream opens', 'succeeded', 200, sse(error_event('overloaded_error')), 'failed', '',
         'retry later'),
        ('api_error inside a block', 'succeeded', 200, sse(start(), block_start(0), text_delta(0, '{'),
                                                           error_event('api_error')), 'failed', '', 'retry later'),
    )


class ClassifyTests(SimpleTestCase):
    def test_every_row_of_the_table(self):
        for label, outcome, status, body, kind, hold, word in table():
            with self.subTest(label):
                verdict = fable_adapter.classify(outcome, status, body)
                self.assertEqual((verdict.kind, verdict.hold, verdict.http_status), (kind, hold, status))
                self.assertEqual(fable_adapter.word(verdict.kind, verdict), word)
                self.assertEqual((verdict.error_reasons, verdict.violations, verdict.retry_delay), ((), (), ''))
                for name in NAMES:
                    self.assertNotIn(name, verdict.why.lower())
                self.assertNotIn('Synthetic: ', verdict.why)  # an error message is never repeated
                self.assertNotIn(CATEGORY_EXPLANATION, verdict.why + verdict.vendor_status)
                if kind == 'too_long':
                    self.assertIn('reached its output limit', verdict.why)
                    self.assertNotIn('too long', verdict.why)  # [R:truth-T7]: never "the document is too long"

    def test_type_before_status(self):
        for status, body, kind, hold in ((529, error_body('overloaded_error'), 'failed', ''),
                                         (400, error_body('billing_error'), 'hold', 'quota'),
                                         (429, b'', 'hold', 'quota'),
                                         (429, error_body('rate_limit_error'), 'failed', ''),
                                         (413, b'', 'failed', ''),
                                         (404, error_body('not_found_error'), 'hold', 'permission'),
                                         (500, error_body('authentication_error'), 'hold', 'auth'),
                                         (413, error_body('invalid_request_error'), 'hold', 'refused'),
                                         (401, error_body('overloaded_error'), 'hold', 'auth'),
                                         (400, error_body('rate_limit_error'), 'hold', 'refused')):
            with self.subTest(status=status, body=body[:40]):
                verdict = fable_adapter.classify('failed', status, body)
                self.assertEqual((verdict.kind, verdict.hold), (kind, hold))

    def test_the_precedence_for_200_streams(self):
        # (1) a model signal holds whatever follows; (2) an error event decides by its type, so an error first is FAILED
        # and never a model hold [R:connector-CONN-4]; (3) a stream that does not assemble FAILED; (4) the stop reason
        rows = (('an error event first', sse(error_event('overloaded_error')), 'failed', ''),
                ('an error event first, then a message_start of another model',
                 sse(error_event('overloaded_error'), start('claude-opus-5-5')), 'failed', ''),
                ('another model, then an error event', sse(start('claude-opus-5-5'), error_event('overloaded_error')),
                 'hold', 'model'),
                ('a stream opening with content_block_start', sse(block_start(0), text_delta(0, '{}'), block_stop(0),
                                                                  message_delta(), stop()), 'hold', 'model'),
                ('a stream opening with message_delta', sse(message_delta(), stop()), 'hold', 'model'),
                ('a fallback block after a malformed one', sse(start(), block_start(0, 'tool_use'), block_stop(0),
                                                                block_start(1, 'fallback'), block_stop(1),
                                                                message_delta(), stop()), 'hold', 'model'),
                ('a malformed block, then an error event naming a hold',
                 sse(start(), text_delta(0, 'x'), error_event('invalid_request_error')), 'hold', 'refused'),
                ('another model, then a stream that does not assemble', sse(start('claude-opus-5-5'), 'garbage\n\n'),
                 'hold', 'model'),
                ('a stream that does not assemble before any message', b'garbage\n\n', 'failed', ''),
                ('refusal after a malformed block', sse(start(), text_delta(0, 'x'), message_delta(
                    'refusal', stop_details={'category': 'cyber'}), stop()), 'failed', ''))
        for label, raw, kind, hold in rows:
            with self.subTest(label):
                verdict = fable_adapter.classify('succeeded', 200, raw)
                self.assertEqual((verdict.kind, verdict.hold), (kind, hold))

    def test_the_refusal_category_is_one_word_never_the_explanation(self):
        for category, vendor_status, named in (('cyber', 'cyber', 'category cyber'),
                                               ('reasoning_extraction', 'reasoning_extraction',
                                                'category reasoning_extraction'),
                                               ('Bio-Safety', '', 'category Bio-Safety'),
                                               ('two words', '', 'a value of 9 characters, not repeated'),
                                               ('x' * 41, '', 'a value of 41 characters, not repeated'),
                                               (None, '', 'no category was given'), ('', '', 'no category was given')):
            with self.subTest(category=category):
                raw = answer_stream(None, stop_reason='refusal',
                                    stop_details={'type': 'refusal', 'category': category,
                                                  'explanation': CATEGORY_EXPLANATION})
                verdict = fable_adapter.classify('succeeded', 200, raw)
                self.assertEqual((verdict.kind, verdict.hold, verdict.vendor_status), ('hold', 'declined',
                                                                                       vendor_status))
                self.assertIn(named, verdict.why)
                self.assertNotIn(CATEGORY_EXPLANATION, verdict.why)
                self.assertIn('nothing was asked of another model', verdict.why)
        # no stop_details at all
        verdict = fable_adapter.classify('succeeded', 200, answer_stream(None, stop_reason='refusal'))
        self.assertEqual((verdict.hold, verdict.vendor_status), ('declined', ''))

    def test_the_vendor_status_is_the_error_type_when_it_fits(self):
        self.assertEqual(fable_adapter.classify('failed', 401, error_body('authentication_error')).vendor_status,
                         'authentication_error')
        for kind in ('Authentication_Error', 'x' * 41, 'type with spaces', ''):
            with self.subTest(kind=kind):
                self.assertEqual(fable_adapter.classify('failed', 401, error_body(kind)).vendor_status, '')
        self.assertEqual(fable_adapter.classify('failed', 401, json.dumps(
            {'type': 'error', 'error': {'type': 7}}).encode()).vendor_status, '')

    def test_an_outcome_that_is_not_definite_is_not_classified(self):
        for outcome in ('unknown', 'not_sent', 'reserved', '', None):
            with self.subTest(outcome=outcome):
                self.assertIsNone(fable_adapter.classify(outcome, 200, answer_stream()))
        self.assertEqual(fable_adapter.word('unknown'), 'unknown')
        self.assertEqual(fable_adapter.word('none'), '-')

    def test_request_bound_answers(self):
        # 1.5 [R:connector-CONN-1]: a decline, or an error event after message_start that sets a hold
        declined = answer_stream(None, stop_reason='refusal', stop_details={'category': 'cyber'})
        self.assertTrue(fable_adapter.request_bound(200, declined))
        self.assertTrue(fable_adapter.request_bound(None, declined))  # a replayed recording of one
        self.assertTrue(fable_adapter.request_bound(200, sse(start(), error_event('invalid_request_error'))))
        self.assertTrue(fable_adapter.request_bound(200, sse(start(), block_start(0), error_event('billing_error'))))
        for label, status, raw in (
                ('an error before message_start', 200, sse(error_event('authentication_error'))),
                ('an error event that sets no hold', 200, sse(start(), error_event('rate_limit_error'))),
                ('another model', 200, answer_stream(model='claude-opus-5-5')),
                ('a decline of another model', 200, answer_stream(None, model='claude-opus-5-5',
                                                                  stop_reason='refusal')),
                ('an answer', 200, answer_stream()), ('a cut-off answer', 200, answer_stream(stop_reason='max_tokens')),
                ('an error body', 400, error_body('invalid_request_error')),
                ('a 401', 401, b''), ('a status that is a bool', True, declined)):
            with self.subTest(label):
                self.assertFalse(fable_adapter.request_bound(status, raw))


class FallbackTests(SimpleTestCase):
    """1.4 and 1.6: no fallback block and no usage.iterations entry whose type starts with 'fallback' - the Fable
    participant's rule (anthropic_fable._fell_back), copied, here checked against it on its own test vectors
    (tests/test_participants_reading.py, test_participants_loop.py)."""

    VECTORS = (
        ([{'type': 'fallback', 'from': {'model': 'claude-fable-5-1'}, 'to': {'model': 'claude-fable-5-1'}}], None),
        ([], {'iterations': [{'type': 'message', 'input_tokens': 10, 'output_tokens': 0},
                             {'type': 'fallback_message', 'model': 'claude-fable-5-1'}]}),
        ([], {'iterations': [{'type': 'message', 'input_tokens': 10, 'output_tokens': 5}]}),
        ([], {'iterations': [{'type': 'fallback_message'}]}),
        ([{'type': 'fallback', 'model': 'claude-other'}], {}),
        ([], {'iterations': 'not a list'}), ([], {'iterations': [{'type': 7}, 'x']}), ([], None))

    def test_the_rule_is_the_participants_on_its_vectors(self):
        for content, usage in self.VECTORS:
            with self.subTest(content=content, usage=usage):
                expected = anthropic_fable._fell_back(content, usage)
                events = [start(usage={**START_USAGE, **(usage or {})})] if usage else [start()]
                for index, block in enumerate(content):
                    events += [{'type': 'content_block_start', 'index': index, 'content_block': block},
                               block_stop(index)]
                events += [block_start(len(content)), text_delta(len(content), '{}'), block_stop(len(content)),
                           message_delta(), stop()]
                verdict = fable_adapter.classify('succeeded', 200, sse(*events))
                self.assertEqual(verdict.kind == 'hold' and verdict.hold == 'model', expected)
                # in message_delta's usage too
                if usage:
                    late = sse(*answer_events()[:-2], message_delta(usage={'output_tokens': 3, **usage}), stop())
                    held = fable_adapter.classify('succeeded', 200, late)
                    self.assertEqual(held.kind == 'hold' and held.hold == 'model', expected)


# --- 1.4: the envelope and the readers ---------------------------------------------------------------------------------

def v3_request(body=None) -> ProviderRequest:
    body = {'model': MODEL} if body is None else body
    return ProviderRequest(provider='anthropic', adapter_version=interpretation.ADAPTER_VERSION_V3, body=body,
                           canonical_sha256=request_sha256(body), contexts=(TEXT,))


class EnvelopeTests(SimpleTestCase):
    def test_a_usable_answer_and_the_form_of_each_pass(self):
        request = v3_request()
        self.assertEqual(fable_adapter.answer_text(request, answer_stream('{"a": 1}'), fable_adapter.EXTRACTION),
                         '{"a": 1}')
        fenced = '```json\n{"a": 1}\n```'
        self.assertEqual(fable_adapter.answer_text(request, answer_stream(fenced), fable_adapter.EXTRACTION),
                         '{"a": 1}')  # pass 1: JSON mode constrains nothing (sole_object)
        self.assertEqual(fable_adapter.answer_text(request, answer_stream(fenced), fable_adapter.APPRAISAL),
                         fenced)  # pass 2: structured outputs constrain it; read as it stands
        prose = 'Synthetic prose before {"a": 1}'
        refusal = fable_adapter.answer_text(request, answer_stream(prose), fable_adapter.EXTRACTION)
        self.assertEqual((refusal.stage, refusal.refused), ('envelope', True))
        self.assertEqual(fable_adapter.answer_text(request, answer_stream(prose), fable_adapter.APPRAISAL), prose)
        with self.assertRaises(ValueError):
            fable_adapter.answer_text(request, answer_stream(), 'primary')

    def test_each_refusal_in_order_and_in_cpt_studios_words(self):
        request = v3_request()
        rows = (('another model, checked first', answer_stream(model='claude-opus-5-5', stop_reason='max_tokens'),
                 'names a model other than the one requested'),
                ('no model', sse(start(model=''), *answer_events()[1:]), 'does not name the model'),
                ('a fallback', sse(*answer_events()[:-2], message_delta(usage={'iterations': [
                    {'type': 'fallback_message'}]}), stop()), 'a fallback took part'),
                ('an error event', sse(start(), error_event('overloaded_error')),
                 'ended with an error (overloaded_error)'),
                ('a stream that does not assemble', sse(start(), text_delta(0, 'x'), message_delta(), stop()),
                 'not open'),
                ('max_tokens', answer_stream('{"a": ', stop_reason='max_tokens'), 'reached its output limit'),
                ('a refusal', answer_stream(None, stop_reason='refusal', stop_details={
                    'category': 'cyber', 'explanation': CATEGORY_EXPLANATION}), 'declined to answer (category cyber)'),
                ('another stop', answer_stream(stop_reason='pause_turn'), 'stopped for pause_turn'),
                ('no text', answer_stream(None), 'carries no text block'),
                ('incomplete', sse(*answer_events()[:-1]), 'ended before its end event'),
                ('not UTF-8', b'\xff\xfe\n\n', 'not valid UTF-8'))
        for label, raw, expect in rows:
            for purpose in fable_adapter.PURPOSES:
                with self.subTest(label, purpose=purpose):
                    refusal = fable_adapter.answer_text(request, raw, purpose)
                    self.assertIsInstance(refusal, extract_read.Refusal)
                    self.assertEqual(refusal.stage, 'envelope')
                    self.assertIn(expect, refusal.reason)
                    self.assertNotIn(CATEGORY_EXPLANATION, refusal.reason)
                    for name in NAMES:
                        self.assertNotIn(name, refusal.reason.lower())

    def test_only_this_providers_and_versions_answers_are_read(self):
        raw = answer_stream('{"a": 1}')
        for request in (stored(v3_request(), provider='gemini'), stored(v3_request(), provider='fable'),
                        stored(v3_request(), adapter_version=interpretation.ADAPTER_VERSION_V2),
                        stored(v3_request(), adapter_version=anthropic_fable.ADAPTER_VERSION), object()):
            with self.subTest(request=getattr(request, 'adapter_version', None)):
                refusal = fable_adapter.answer_text(request, raw, fable_adapter.EXTRACTION)
                self.assertEqual(refusal.reason, extract_read.refuse('envelope', fable_adapter.STORED_VERSION).reason)


class ReadTests(FablePinned, OfflineTestCase):
    def test_pass_1s_answer_is_read_from_its_stream(self):
        extraction = self.extraction()
        appraisal = self.appraisal(extraction)
        read = fable_adapter.read_extraction(extraction, answer_stream(pass_1_answer()), appraisal.unit_count)
        self.assertIsInstance(read, extract_read.ReadAnswer)
        self.assertEqual(read, appraisal.answer)
        fenced = fable_adapter.read_extraction(extraction, answer_stream(f'```json\n{pass_1_answer()}\n```'),
                                               appraisal.unit_count)
        self.assertEqual(fenced, read)
        # a request of the other kind, or of another provider, is never read as pass 1's
        self.assertEqual(fable_adapter.read_extraction(appraisal.request, answer_stream(pass_1_answer()),
                                                       appraisal.unit_count).reason,
                         extract_read.refuse('envelope', fable_adapter.OTHER_KIND).reason)
        self.assertEqual(fable_adapter.read_extraction(stored(extraction, provider='gemini'),
                                                       answer_stream(pass_1_answer()), appraisal.unit_count).reason,
                         extract_read.refuse('envelope', fable_adapter.STORED_VERSION).reason)

    def test_pass_2s_answer_is_read_against_the_claims_it_answered(self):
        appraisal = self.appraisal()
        raw = answer_stream(verdicts_for(appraisal.built))
        read = fable_adapter.read_appraisal(appraisal, appraisal.request, raw)
        self.assertIsInstance(read, appraise_read.ReadAppraisal)
        self.assertEqual([verdict.content for verdict in read.verdicts],
                         [claim.content for claim in appraisal.built.claim_set.claims])
        other = stored(appraisal.request, canonical_sha256='0' * 64)
        self.assertEqual(fable_adapter.read_appraisal(appraisal, other, raw).reason,
                         extract_read.refuse('envelope', fable_adapter.OTHER_APPRAISAL).reason)
        refused = fable_adapter.read_appraisal(appraisal, appraisal.request, answer_stream(model='claude-opus-5-5'))
        self.assertEqual(refused.stage, 'envelope')


class ReadLabelTests(FablePinned, OfflineTestCase):
    """The a2b integration's I1 and I2 (AMENDMENT-2 4.3.1 and 8.1-8.2; DECISIONS D275's slot rule): the Fable path
    reads pass 1 under gemini-events@3 - an overfilled slot is read, each written fact carrying slot_overfull, never
    S1's refusal of the whole answer, which gemini-events@2 (the dormant path's label) keeps - and pass 2 under
    gemini-appraisal@2, the label its claims were built under."""

    def test_pass_1_reads_an_overfilled_slot_under_gemini_events_3(self):
        from studio.interpretation.contract import types as ct
        extraction = self.extraction()
        appraisal = self.appraisal(extraction)
        answer = fixtures.note_answer()
        device = answer['events'][1]['technique']['device']  # E2's one supported cold snare
        device.append({**json.loads(json.dumps(device[0])), 'state': 'negated', 'value': 'hot_snare'})
        read = fable_adapter.read_extraction(extraction, answer_stream(json.dumps(answer)), appraisal.unit_count)
        self.assertIsInstance(read, extract_read.ReadAnswer, getattr(read, 'reason', ''))
        written = [item for item in read.facts
                   if (item.key.object, item.key.attribute) == ('E2', ct.Attribute.TECHNIQUE_DEVICE)]
        self.assertEqual(len(written), 2)
        for item in written:
            self.assertIn(ct.Reason.SLOT_OVERFULL, item.reasons)
        # the control: the same answer under gemini-events@2 is refused whole (S1), as the dormant path reads it
        older = extract_read.read(json.dumps(answer), appraisal.unit_count,
                                  version=interpretation.INTERPRETATION_VERSION_V2)
        self.assertIsInstance(older, extract_read.Refusal)
        self.assertEqual(older.stage, 'bounds')

    def test_pass_2_is_read_under_gemini_appraisal_2(self):
        appraisal = self.appraisal()
        seen, real = [], appraise_read.check_pin

        def check_pin(version=None):
            seen.append(version)
            return real(version)
        with mock.patch.object(appraise_read, 'check_pin', check_pin):
            read = fable_adapter.read_appraisal(appraisal, appraisal.request,
                                                answer_stream(verdicts_for(appraisal.built)))
        self.assertIsInstance(read, appraise_read.ReadAppraisal)
        self.assertEqual(seen, [interpretation.APPRAISAL_VERSION_V3])


# --- 1.3: the send ------------------------------------------------------------------------------------------------------

class SendCase(FablePinned, OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.clock = FakeClock()
        self.enterContext(mock.patch.object(participants_http, 'monotonic', self.clock))
        self.enterContext(mock.patch.object(fable_adapter, 'monotonic', self.clock))
        self.enterContext(mock.patch.object(participants_loop, 'monotonic', self.clock))
        self.credentials = write_file(self.tmp / 'anthropic.env', anthropic_env())

    def interpreter(self, session, **options):
        made = []

        def factory():
            made.append(session)
            return session
        self.made = made
        return fable_adapter.FableInterpreter(self.credentials, session_factory=factory, **options)

    def ok(self, raw=None, **headers):
        return FakeResponse(200, answer_stream(pass_1_answer()) if raw is None else raw,
                            headers={'request-id': REQUEST_ID, **headers})

    def assertNoSecrets(self, exchange):
        for secret in SECRETS:
            self.assertNotIn(secret, repr(exchange) + exchange.error)


class SendTests(SendCase):
    def test_one_post_of_the_exact_body_with_the_headers_set_at_send_time(self):
        request = self.extraction()
        session = FakeSession(self.ok())
        exchange = self.interpreter(session).send(request, deadline_s=60)
        [call] = session.calls
        self.assertEqual(call['url'], 'https://api.anthropic.com/v1/messages')
        self.assertEqual(call['data'], canonical_body(request.body))
        self.assertEqual(call['headers'], {'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2026-10-21',
                                           'content-type': 'application/json'})
        self.assertEqual((call['allow_redirects'], call['stream']), (False, True))
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.usage, exchange.usage_basis,
                          exchange.returned_model, exchange.response_id, exchange.provider_request_id,
                          exchange.requested_model, exchange.endpoint),
                         ('succeeded', True, 200, FINAL_USAGE, 'provider_reported_tokens', MODEL, MESSAGE_ID,
                          REQUEST_ID, MODEL, fable_adapter.ENDPOINT))
        self.assertEqual(exchange.response_sha256, hashlib.sha256(exchange.response_bytes).hexdigest())
        self.assertNoSecrets(exchange)
        self.assertTrue(session.closed)
        # the workspace header only when the credential names one
        write_file(self.tmp / 'workspace.env', anthropic_env(ANTHROPIC_WORKSPACE_ID=ANTHROPIC_WORKSPACE))
        session = FakeSession(self.ok())
        interpreter = self.interpreter(session)
        interpreter.credentials_path = self.tmp / 'workspace.env'
        interpreter.send(request, deadline_s=60)
        self.assertEqual(session.calls[0]['headers']['anthropic-workspace-id'], ANTHROPIC_WORKSPACE)

    def test_the_key_is_read_at_send_time_and_a_bad_credential_sends_nothing(self):
        request = self.extraction()
        for content in ('', 'ANTHROPIC_API_KEY=\n', 'OTHER=1\n'):
            with self.subTest(content=content):
                path = self.tmp / f'bad-{len(content)}.env'
                write_file(path, content)
                session = FakeSession()
                interpreter = self.interpreter(session)
                interpreter.credentials_path = path
                exchange = interpreter.send(request, deadline_s=60)
                self.assertEqual((exchange.outcome, exchange.sent, session.calls), ('not_sent', False, []))
                self.assertIn('No request was sent.', exchange.error)

    def test_one_exchange_never_retried_and_a_rate_limits_retry_after_changes_nothing(self):
        request = self.extraction()
        for response in (FakeResponse(429, error_body('rate_limit_error'), headers={'retry-after': '17'}),
                         FakeResponse(529, error_body('overloaded_error'), headers={'retry-after': '3'}),
                         FakeResponse(200, sse(error_event('overloaded_error')))):
            with self.subTest(status=response.status_code):
                session = FakeSession(response)  # a second POST would raise 'unexpected extra POST'
                outcome = self.interpreter(session).send_loop(request, deadline_s=60)
                self.assertEqual((len(session.calls), len(outcome.exchanges)), (1, 1))
                verdict = fable_adapter.classify(outcome.final.outcome, outcome.final.http_status,
                                                 outcome.final.response_bytes)
                self.assertEqual((verdict.kind, fable_adapter.word(verdict.kind, verdict)), ('failed', 'retry later'))

    def test_a_members_stop_a_continuation_and_a_body_of_neither_kind_send_nothing(self):
        request = self.extraction()
        session = FakeSession()
        interpreter = self.interpreter(session)
        stopped = interpreter.send_loop(request, deadline_s=60, should_stop=lambda: True)
        self.assertEqual((stopped.outcome, stopped.stopped, stopped.exchanges), ('not_sent', True, ()))
        broken = interpreter.send_loop(request, deadline_s=60, should_stop=lambda: 1 / 0)
        self.assertIn('could not check for a Stop', broken.final.error)
        carried = interpreter.send_loop(request, deadline_s=60, carried=('synthetic',))
        self.assertEqual((carried.outcome, carried.final.error), ('not_sent', adapter.NOT_CONTINUED))
        tools = copy.deepcopy(request.body)
        tools['tools'] = []
        for refused, expect in ((stored(request, body=tools, canonical_sha256=request_sha256(tools)),
                                 fable_adapter.NOT_BUILT),
                                (stored(request, adapter_version=interpretation.ADAPTER_VERSION_V2),
                                 'different provider or adapter version'),
                                (stored(request, provider='fable'), 'different provider or adapter version')):
            with self.subTest(expect):
                self.assertIn(expect, interpreter.send(refused, deadline_s=60).error)
                outcome = interpreter.send_loop(refused, deadline_s=60)
                self.assertEqual((outcome.outcome, outcome.exchanges), ('not_sent', ()))
        self.assertEqual(session.calls, [])
        self.assertEqual(interpreter.send(request, deadline_s=0).error, adapter.INVALID_DEADLINE)

    def test_the_live_exchange_verifies_the_body_again(self):
        request = self.extraction()
        session = FakeSession()
        interpreter = self.interpreter(session)
        tools = dict(copy.deepcopy(request.body), tools=[])
        self.assertEqual(interpreter._exchange(tools, self.clock() + 60, fable_adapter.EXTRACTION).error,
                         fable_adapter.NOT_BUILT)
        appraisal = self.appraisal(request)
        self.assertEqual(interpreter._exchange(appraisal.request.body, self.clock() + 60,
                                               fable_adapter.EXTRACTION).error, fable_adapter.NOT_BUILT)
        self.assertEqual(session.calls, [])

    def test_each_purposes_deadline_and_read_timeout(self):
        request = self.extraction()
        appraisal = self.appraisal(request)
        session = FakeSession(self.ok(), self.ok(answer_stream(verdicts_for(appraisal.built))))
        interpreter = self.interpreter(session, read_timeout=900, appraisal_read_timeout=800, send_deadline=1000,
                                       appraisal_send_deadline=950)
        interpreter.send(request, deadline_s=5000)
        interpreter.send(appraisal.request, deadline_s=5000)
        self.assertEqual([call['timeout'] for call in session.calls], [(10, 900), (10, 800)])
        self.assertEqual(interpreter.purpose(appraisal.request), fable_adapter.APPRAISAL)


class CutStreamTests(SendCase):
    """1.3 [R:connector-CONN-6][R:connector-CONN-2][R:connector-CONN-3], over fake sessions: every 200 whose stream did
    not end is UNKNOWN with the bytes read before the stop kept and no usage, live through the interpreter."""

    def send(self, response, **options):
        session = FakeSession(response)
        outcome = self.interpreter(session, **options).send_loop(self.extraction(), deadline_s=60)
        return outcome, session

    def assertCut(self, outcome, kept, expect):
        final = outcome.final
        self.assertEqual((final.outcome, final.sent, final.http_status, final.response_bytes, final.response_sha256,
                          final.usage, final.usage_basis, final.provider_request_id, final.returned_model,
                          final.response_id),
                         ('unknown', True, 200, kept, hashlib.sha256(kept).hexdigest(), {}, '', REQUEST_ID, MODEL,
                          MESSAGE_ID))
        self.assertIn('The request reached Anthropic, but its answer stream', final.error)
        self.assertIn('The outcome is unknown; reconcile it before any new attempt.', final.error)
        self.assertIn(expect, final.error)
        [record] = outcome.exchanges
        self.assertEqual((record.outcome, record.response_bytes, record.usage), ('unknown', kept, {}))
        self.assertIsNone(fable_adapter.classify(final.outcome, final.http_status, final.response_bytes))
        self.assertNoSecrets(final)

    def test_an_incomplete_stream_is_unknown_with_its_bytes(self):
        events = answer_events(pass_1_answer())
        for name, raw in (('no message_stop', sse(*events[:-1])), ('no message_delta', sse(*events[:-2])),
                          ('an unterminated last event', sse(*events)[:-1])):
            with self.subTest(name):
                outcome, _ = self.send(self.ok(raw))
                self.assertCut(outcome, raw, 'ended before its end event')

    def test_a_broken_chunk_is_unknown_with_the_bytes_read_before_it(self):
        events = answer_events(pass_1_answer())
        first, second = sse(*events[:3]), sse(*events[3:6])
        for error in (requests.exceptions.ChunkedEncodingError('synthetic: connection broken mid-chunk'),
                      requests.exceptions.ConnectionError('synthetic: connection reset')):
            with self.subTest(error=type(error).__name__):
                response = FakeResponse(200, chunks=[first, second, error, b'never read'],
                                        headers={'request-id': REQUEST_ID})
                outcome, _ = self.send(response)
                self.assertCut(outcome, first + second, type(error).__name__)
                self.assertTrue(response.closed)

    def test_a_deadline_cut_is_unknown_with_the_bytes_read_before_it(self):
        events = answer_events(pass_1_answer())
        first, second = sse(*events[:3]), sse(*events[3:6])

        def late():
            self.clock.advance(120)  # the deadline (60 s) passes while this chunk arrives
            return second
        outcome, _ = self.send(FakeResponse(200, chunks=[first, late, sse(*events[6:])],
                                            headers={'request-id': REQUEST_ID}))
        self.assertCut(outcome, first + second, participants_http.DEADLINE_READING)

    def test_a_cap_overflow_is_unknown_with_the_bytes_read_before_it(self):
        events = answer_events(pass_1_answer())
        first, second = sse(*events[:3]), sse(*events[3:])
        outcome, _ = self.send(FakeResponse(200, chunks=[first, second], headers={'request-id': REQUEST_ID}),
                               max_response_bytes=len(first) + 10)
        self.assertCut(outcome, first, f'the response exceeded {len(first) + 10:,} bytes')

    def test_a_complete_stream_and_a_non_200_keep_their_old_paths(self):
        outcome, _ = self.send(self.ok())
        self.assertEqual((outcome.outcome, outcome.final.usage), ('succeeded', FINAL_USAGE))
        body = error_body('overloaded_error')
        outcome, _ = self.send(FakeResponse(529, body, headers={'request-id': REQUEST_ID}))
        self.assertEqual((outcome.outcome, outcome.final.http_status, outcome.final.response_bytes),
                         ('failed', 529, body))
        # a non-200 whose read breaks is unknown with nothing kept, as before (the hook is a 200's)
        outcome, _ = self.send(FakeResponse(529, chunks=[b'{"type"', requests.exceptions.ChunkedEncodingError('x')]))
        self.assertEqual((outcome.outcome, outcome.final.response_bytes), ('unknown', None))


# --- a real socket, behind a loopback guard ------------------------------------------------------------------------------

class LoopbackGuard:
    """While a test runs only 127.0.0.1 is reachable: a connect or a name lookup of any other address fails the test (a
    positive control proves the guard trips)."""

    def setUp(self):
        super().setUp()
        self.network_attempts = []
        real_connect, real_getaddrinfo = socket.socket.connect, socket.getaddrinfo

        def connect(sock, address):
            host = address[0] if isinstance(address, tuple) else address
            if host != '127.0.0.1':
                self.network_attempts.append(('connect', host))
                raise NetworkBlocked(f'{host} was reached; only 127.0.0.1 may be.')
            return real_connect(sock, address)

        def getaddrinfo(host, *args, **kwargs):
            if host != '127.0.0.1':
                self.network_attempts.append(('getaddrinfo', host))
                raise NetworkBlocked(f'{host} was looked up; only 127.0.0.1 may be.')
            return real_getaddrinfo(host, *args, **kwargs)
        self.enterContext(mock.patch.object(socket.socket, 'connect', connect))
        self.enterContext(mock.patch.object(socket, 'getaddrinfo', getaddrinfo))

    def tearDown(self):
        self.assertEqual(self.network_attempts, [], 'A test reached an address other than 127.0.0.1.')
        super().tearDown()


def chunk(data: bytes) -> bytes:
    return b'%x\r\n' % len(data) + data + b'\r\n'


class LoopbackServer:
    """A one-connection server on 127.0.0.1 that reads one request and then plays ``script``: (bytes, seconds to wait
    first) pairs - or (bytes, seconds, 'trickle'), sent one byte at a time with that wait before each - then closes the
    connection (a chunked body left without its terminating chunk is a socket-level cut)."""

    def __init__(self, case, script):
        self.script = script
        self.received = bytearray()
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(1)
        self.listener.settimeout(10)
        self.stop = threading.Event()
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        case.addCleanup(thread.join, 10)
        case.addCleanup(self.stop.set)
        case.addCleanup(self.listener.close)

    @property
    def url(self):
        return f'http://127.0.0.1:{self.listener.getsockname()[1]}/v1/messages'

    def run(self):
        try:
            conn, _ = self.listener.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(10)
            data = b''
            while b'\r\n\r\n' not in data:
                more = conn.recv(65536)
                if not more:
                    return
                data += more
            head, _, rest = data.partition(b'\r\n\r\n')
            length = int(re.search(rb'(?i)content-length: *([0-9]+)', head).group(1))
            while len(rest) < length:
                rest += conn.recv(65536)
            self.received.extend(head + b'\r\n\r\n' + rest)
            try:
                for piece, wait, *trickle in self.script:
                    if trickle:
                        for byte in piece:
                            if self.stop.wait(wait):
                                return
                            conn.sendall(bytes([byte]))
                        continue
                    if wait and self.stop.wait(wait):
                        return
                    conn.sendall(piece)
                self.stop.wait(0.05)
            except OSError:
                return  # the client went away


HEAD = b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nrequest-id: req_synthetic_0001\r\n'


class LoopbackTests(LoopbackGuard, SimpleTestCase):
    """1.3 [R:connector-CONN-6]: through the real default session and participants.http.post with the Fable VENDOR, a
    stream cut at the socket - a chunked body left without its terminating chunk (requests raises ChunkedEncodingError
    inside iter_content), a body that trickles past the deadline, a body that ends before message_stop - is UNKNOWN with
    the bytes read before the stop kept and no usage; a whole stream succeeds with its final usage."""

    def post(self, url, deadline_s=5.0, max_response_bytes=1 << 20):
        return participants_http.post(fable_adapter.VENDOR, participants_http.default_session, url, b'{}',
                                      {'content-type': 'application/json'}, deadline=time.monotonic() + deadline_s,
                                      connect_timeout=2, read_timeout=3, max_response_bytes=max_response_bytes,
                                      requested_model=MODEL)

    def assertUnknown(self, exchange, kept, expect):
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.response_bytes,
                          exchange.usage, exchange.provider_request_id),
                         ('unknown', True, 200, kept, {}, REQUEST_ID))
        self.assertIn(expect, exchange.error)

    def test_the_loopback_guard_trips(self):  # the positive control
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(probe.close)
        with self.assertRaises(NetworkBlocked):
            probe.connect(('192.0.2.1', 9))
        with self.assertRaises(NetworkBlocked):
            socket.getaddrinfo('synthetic.invalid', 80)
        exchange = participants_http.post(fable_adapter.VENDOR, participants_http.default_session,
                                          'http://192.0.2.1:9/v1/messages', b'{}', {}, deadline=time.monotonic() + 2,
                                          connect_timeout=1, read_timeout=1, max_response_bytes=1024,
                                          requested_model=MODEL)
        self.assertEqual((exchange.outcome, exchange.sent), ('not_sent', False))  # the guard refused the connect
        self.assertEqual([kind for kind, _ in self.network_attempts][:2], ['connect', 'getaddrinfo'])
        self.assertGreater(len(self.network_attempts), 2)
        self.network_attempts.clear()

    def test_a_whole_stream_succeeds(self):
        raw = answer_stream(pass_1_answer())
        server = LoopbackServer(self, [(HEAD + b'Transfer-Encoding: chunked\r\n\r\n', 0), (chunk(raw[:500]), 0),
                                       (chunk(raw[500:]), 0.05), (b'0\r\n\r\n', 0)])
        exchange = self.post(server.url)
        self.assertEqual((exchange.outcome, exchange.response_bytes, exchange.usage, exchange.returned_model),
                         ('succeeded', raw, FINAL_USAGE, MODEL))
        self.assertIn(b'POST /v1/messages', bytes(server.received))

    def test_a_chunked_body_cut_mid_chunk_is_unknown_with_the_bytes_read_before_the_cut(self):
        raw = answer_stream(pass_1_answer())
        first, second = raw[:400], raw[400:800]
        server = LoopbackServer(self, [(HEAD + b'Transfer-Encoding: chunked\r\n\r\n', 0), (chunk(first), 0),
                                       (chunk(second), 0.05), (b'%x\r\n' % 4096 + raw[800:900], 0.05)])
        exchange = self.post(server.url)
        self.assertUnknown(exchange, first + second, 'ChunkedEncodingError')
        # the same cut without the hook (every participant) keeps its old path: unknown, nothing kept
        server = LoopbackServer(self, [(HEAD + b'Transfer-Encoding: chunked\r\n\r\n', 0), (chunk(first), 0),
                                       (b'%x\r\n' % 4096 + raw[800:900], 0.05)])
        plain = participants_http.post(
            participants_http.Vendor(label='Anthropic', request_id_header='request-id'),
            participants_http.default_session, server.url, b'{}', {'content-type': 'application/json'},
            deadline=time.monotonic() + 5, connect_timeout=2, read_timeout=3, max_response_bytes=1 << 20,
            requested_model=MODEL)
        self.assertEqual((plain.outcome, plain.response_bytes), ('unknown', None))

    def test_a_stream_the_deadline_cuts_is_unknown_with_the_bytes_read_before_the_cut(self):
        raw = answer_stream(pass_1_answer())
        started = time.monotonic()
        # the rest trickles in one byte every 0.25 s, so no read waits past its timeout: only the deadline cuts it
        server = LoopbackServer(self, [(HEAD + b'Transfer-Encoding: chunked\r\n\r\n', 0), (chunk(raw[:300]), 0),
                                       (chunk(raw[300:600]), 0.05), (chunk(raw[600:]), 0.25, 'trickle')])
        exchange = self.post(server.url, deadline_s=1.0)
        self.assertLess(time.monotonic() - started, 4)  # cut at the 1 s deadline; the trickle alone takes minutes
        self.assertUnknown(exchange, raw[:600], participants_http.DEADLINE_READING)

    def test_a_body_that_ends_before_its_end_event_is_unknown_with_its_bytes(self):
        raw = sse(*answer_events(pass_1_answer())[:-1])
        server = LoopbackServer(self, [(HEAD + b'Content-Length: %d\r\n\r\n' % len(raw), 0), (raw, 0)])
        self.assertUnknown(self.post(server.url), raw, 'ended before its end event')

    def test_a_stream_over_the_cap_is_unknown_with_the_bytes_read_before_it(self):
        raw = answer_stream(pass_1_answer())
        server = LoopbackServer(self, [(HEAD + b'Transfer-Encoding: chunked\r\n\r\n', 0), (chunk(raw[:256]), 0),
                                       (chunk(raw[256:]), 0.05), (b'0\r\n\r\n', 0)])
        exchange = self.post(server.url, max_response_bytes=300)
        self.assertEqual((exchange.outcome, exchange.http_status, exchange.usage), ('unknown', 200, {}))
        self.assertLessEqual(len(exchange.response_bytes), 300)
        self.assertEqual(exchange.response_bytes, raw[:len(exchange.response_bytes)])  # what was read, in order
        self.assertIn('the response exceeded 300 bytes', exchange.error)


# --- 1.11, 1.12 ------------------------------------------------------------------------------------------------------------

class ConfiguredTests(OfflineTestCase):
    def test_the_configured_interpreter(self):
        with override_settings(GEMINI_MODE='disabled'):
            self.assertIsNone(fable_adapter.get_interpreter_v2())
        with override_settings(GEMINI_MODE='live', ANTHROPIC_CREDENTIALS_FILE=''):
            with self.assertRaises(ProviderUnavailable) as caught:
                fable_adapter.get_interpreter_v2()
            self.assertIn('CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE', str(caught.exception))
        path = str(self.tmp / 'anthropic.env')
        with override_settings(GEMINI_MODE='live', ANTHROPIC_CREDENTIALS_FILE=path, GEMINI_CREDENTIALS_FILE=''):
            live = fable_adapter.get_interpreter_v2()
        self.assertIsInstance(live, fable_adapter.FableInterpreter)
        self.assertEqual((live.mode, live.endpoint, live.credentials_path, live.name, live.adapter_version,
                          live.requested_model), ('live', fable_adapter.ENDPOINT, path, 'anthropic',
                                                  interpretation.ADAPTER_VERSION_V3, MODEL))
        self.assertEqual((live.send_deadlines, live.read_timeouts, live.connect_timeout, live.max_response_bytes),
                         ({'interpretation': settings.INTERPRETER_SEND_DEADLINE_SECONDS,
                           'appraisal': settings.APPRAISER_SEND_DEADLINE_SECONDS},
                          {'interpretation': settings.INTERPRETER_READ_TIMEOUT_SECONDS,
                           'appraisal': settings.APPRAISER_READ_TIMEOUT_SECONDS},
                          settings.PARTICIPANT_CONNECT_TIMEOUT_SECONDS, settings.INTERPRETER_MAX_RESPONSE_BYTES))
        self.assertEqual(live.send_deadlines['interpretation'], 1320)  # 1.12
        with override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR=''):
            with self.assertRaises(ProviderUnavailable):
                fable_adapter.get_interpreter_v2()
        with override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR=str(self.tmp)):
            from studio.interpretation.replay import ReplayInterpreterF

            replay = fable_adapter.get_interpreter_v2()
        self.assertIsInstance(replay, ReplayInterpreterF)
        self.assertEqual((replay.mode, replay.endpoint, replay.replay_dir), ('replay', '', self.tmp))
        with self.assertRaises(ValueError):
            fable_adapter.get_interpreter_v2('other')
        self.assertIsNone(fable_adapter.get_interpreter_v2('disabled'))

    def test_invalid_limits_are_refused(self):
        for options in ({'send_deadline': 0}, {'appraisal_send_deadline': -1}, {'max_request_bytes': 0},
                        {'max_response_bytes': True}, {'read_timeout': 0}, {'connect_timeout': float('nan')}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                fable_adapter.FableInterpreter(self.tmp / 'anthropic.env', **options)


# --- the guards --------------------------------------------------------------------------------------------------------------

class GuardTests(SimpleTestCase):
    def test_no_jobs_call_reaches_the_gemini_interpreter(self):
        # section 9: jobs.py's interpretation_adapter names the new module, and no call of jobs.py reaches
        # adapter.GeminiInterpreterV2 or adapter.get_interpreter_v2 (the v1 chain's adapter.get_interpreter stays)
        import ast

        from studio import jobs

        self.assertIs(jobs.interpretation_adapter, fable_adapter)
        tree = ast.parse(JOBS.read_text(encoding='utf-8'))
        gemini_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or '').endswith('interpretation'):
                gemini_names |= {alias.asname or alias.name for alias in node.names if alias.name == 'adapter'}
            elif isinstance(node, ast.ImportFrom) and (node.module or '').endswith('interpretation.adapter'):
                found = {alias.name for alias in node.names} & {'GeminiInterpreterV2', 'get_interpreter_v2',
                                                                'InterpreterV2'}
                self.assertEqual(found, set(), 'jobs.py imports the Gemini interpreter by name')
        reached = [f'{node.value.id}.{node.attr} (line {node.lineno})' for node in ast.walk(tree)
                   if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                   and node.value.id in gemini_names
                   and node.attr in ('GeminiInterpreterV2', 'get_interpreter_v2', 'InterpreterV2')]
        self.assertEqual(reached, [])

    def test_the_module_imports_nothing_the_sentinel_denies_and_adapter_py_is_unedited(self):
        from studio.interpretation import sentinel

        found = imports(MODULE.read_text(encoding='utf-8'))
        denied = set(sentinel.DENY_MODULES) | set(sentinel.RETIRED_MODULES)
        self.assertEqual(found & denied, set())
        self.assertFalse({name for name in found if name.startswith(('studio.gi', 'studio.validation',
                                                                     'studio.candidates'))})
        self.assertTrue({'studio.participants.http', 'studio.interpretation.adapter'} <= found)  # the reader reads
        # A2 1.1: adapter.py stays as it is - its sha at the round's base (0a5f3283b)
        adapter_bytes = (APP / 'studio' / 'interpretation' / 'adapter.py').read_bytes()
        self.assertEqual(hashlib.sha256(adapter_bytes).hexdigest(),
                         '2dcc6915db3e1e865df1faa212ea4286c2700b35d4ff6894e2fd06940a03b481')

    def test_mypy_strict_passes_on_the_module_and_on_holds(self):
        def mypy(*arguments):
            return subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--follow-imports=silent', '--cache-dir',
                                   os.devnull, *arguments], cwd=APP, capture_output=True, text=True, timeout=600)

        result = mypy('studio/interpretation/fable_adapter.py', 'studio/interpretation/holds.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # the positive control: mypy reads the module's types - assemble's stream may be None
        probe = mypy('-c', 'from studio.interpretation import fable_adapter\n'
                           'stream, code, why = fable_adapter.assemble(b"")\nprint(stream.text)\n')
        self.assertNotEqual(probe.returncode, 0)
        self.assertIn('union-attr', probe.stdout)

    def test_the_module_reads_no_settings_at_import(self):
        import ast

        tree = ast.parse(MODULE.read_text(encoding='utf-8'))
        top = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any('django' in ast.unparse(node) for node in top))
        self.assertEqual(inspect.getsource(fable_adapter.get_interpreter_v2).count('from django.conf import settings'),
                         1)
