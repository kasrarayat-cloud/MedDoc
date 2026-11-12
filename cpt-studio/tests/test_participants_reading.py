"""Participant readings (HARNESS.md 4, 12.8; I6, I7): each vendor's answer shapes (good, refusal, truncated, wrong
model, fallback), the strict JSON and CPT Studio's own schema validation, the bounds, the item-level rules, and quote
location (every span an exact slice of the revision text; anything else unverified and never evidence); Fable's
harness-3 answer, which nothing at Anthropic constrained, read only when it is exactly one JSON object (alone or alone
in one json code fence), and Fable's earlier versions' stored runs read exactly as before. Offline and synthetic
(test_participants_support)."""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import time

from studio.participants import anthropic_fable, loop, openai_astra, prompt, reading
from studio.participants.anthropic_fable import FableParticipant
from studio.participants.openai_astra import AstraParticipant
from studio.providers.base import request_sha256
from studio.types import EvidenceSpan, ExtractionIssue, ParticipantLesion, ProviderRequest, sha256_json

from tests.test_participants_support import (FIXTURE_SHA256, FIXTURES, NOTE, ORIGINAL, PAGE_BREAK, PAGES,
                                             OfflineTestCase, astra_envelope, astra_tool_call, astra_with, changed,
                                             code, empty_reading, fable_envelope, fable_harness_2, fable_harness_3,
                                             fable_with, fixture_bytes, fixture_reading, service)

# Model-written text shaped like a descriptor (synthetic placeholder wording, refutation round 1, IND-2): never repeated
REFUSAL_WORDING = ('I will not code this. 45385 is SYNTHETIC-DESCRIPTOR-WORDING with removal of lesion(s) by snare '
                   'technique, single or multiple, PLACEHOLDER-FOR-LICENSED-TEXT.')
PROSE_MARK = 'SYNTHETIC-MODEL-PROSE-0001'  # model-written words around an answer: never repeated in a problem
NOT_ONE = f'The reading was not used: {reading.NOT_ONE_OBJECT}.'
# The harness@2 head's own readings of stored Fable runs (9d773838c; sha256_json of the whole ParticipantReading).
HARNESS_2_READINGS = {
    'fixture': '55d0186ae7283cba8f5ed7db54572e283cc300c803d679fc40d210e66ad0d179',
    'fenced': 'f953fb596922a47aff32369734e3d177be40badb091013b32667d18abc2af5a8',
    'fixture as harness@1': 'f1733b797ef8723496c2604702db9b13cd90e3e0fcd893a15c4df8c183857d34',
}


def located(text: str, quote: str) -> list[tuple[int, int, str]]:
    return [(span.start, span.end, span.text) for span in reading.Locator(text).locate(quote).spans]


class FixtureTests(OfflineTestCase):
    def test_the_fixture_bytes_are_unchanged_and_documented(self):
        readme = (FIXTURES / 'README.md').read_text()
        for name, sha in FIXTURE_SHA256.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256(fixture_bytes(name)).hexdigest(), sha)
                self.assertIn(f'`{name}`', readme)
                self.assertIn(sha, readme)
        self.assertEqual(NOTE[PAGE_BREAK:].split('\n', 1)[0][:9], 'Findings:')


class _GoodAnswerContract:
    adapter_class = None
    module = None

    def setUp(self):
        super().setUp()
        self.adapter = self.adapter_class(self.tmp / 'never-read.env')
        self.request = self.adapter.build_request(NOTE, PAGES, 'pdf', {'sha256': '0' * 64, 'bytes': 1})

    def read(self, raw, request=None):
        return self.adapter.read(request or self.request, raw)

    def test_the_good_answer_is_read_in_full_and_every_quote_is_an_exact_slice(self):
        result = self.read(fixture_bytes(self.fixture))
        self.assertEqual((result.refused, result.problems, result.unverified_quotes), (False, (), 0))
        self.assertEqual((result.provider, result.adapter_version, result.reading_version, result.requested_model,
                          result.returned_model),
                         (self.module.NAME, self.module.ADAPTER_VERSION, 'harness-reading@2', self.module.MODEL,
                          self.module.MODEL))
        self.assertEqual(result.date_of_service, '2026-10-21')
        (procedure,) = result.services
        self.assertEqual((procedure.id, procedure.family, procedure.status, procedure.extent),
                         ('s1', 'colonoscopy', 'performed', 'cecum'))
        self.assertEqual(procedure.lesions[0], ParticipantLesion(site='ascending colon', size='6 mm',
                                                                 morphology='sessile', action='removed by cold snare',
                                                                 specimen='retrieved for pathology'))
        self.assertEqual([(c.code, c.modifiers, c.units, c.service_ids, c.confidence) for c in result.codes],
                         [('45385', (), 1, ('s1',), 'high'), ('45380', ('59',), 1, ('s1',), 'medium')])
        quotes = (result.date_evidence + procedure.evidence
                  + tuple(item for c in result.codes for item in c.evidence))
        self.assertEqual(len(quotes), 5)
        for item in quotes:
            with self.subTest(quote=item.quote):
                self.assertEqual(item.reason, '')
                for span in item.spans:
                    self.assertEqual((span.context_index, span.exact, span.page), (0, True, None))
                    self.assertEqual(NOTE[span.start:span.end], span.text)
                    self.assertEqual(' '.join(span.text.split()), ' '.join(item.quote.split()))
        # The quote that crosses a line break in the note is still found: whitespace runs are collapsed.
        crossing = procedure.evidence[1]
        self.assertIn('\n', crossing.spans[0].text)
        self.assertNotIn('\n', crossing.quote)

    def test_a_response_is_read_only_as_the_participant_and_version_that_recorded_it(self):
        raw = fixture_bytes(self.fixture)
        for provider, version in ((self.module.NAME, self.module.ADAPTER_VERSION[:-1] + '0'),
                                  ('replay', self.module.ADAPTER_VERSION), ('corti', 'corti-coding-v2@cptstudio-1'),
                                  (self.other.NAME, self.other.ADAPTER_VERSION)):
            request = ProviderRequest(provider=provider, adapter_version=version, body=self.request.body,
                                      canonical_sha256=self.request.canonical_sha256, contexts=self.request.contexts)
            with self.subTest(provider=provider, version=version):
                result = self.read(raw, request)
                self.assertTrue(result.refused)
                self.assertEqual(result.codes, ())
                self.assertEqual(result.problems, (f"The reading was not used: it was recorded for {provider!r} with "
                                                   f"adapter {version!r}, not {self.module.NAME!r} with "
                                                   f"{self.module.ADAPTER_VERSION!r}.",))

    def test_an_unusable_response_is_refused_whole(self):
        cases = {b'': 'the response is not valid JSON', b'\xff\xfe{}': 'the response is not valid UTF-8',
                 b'[]': 'the response is not a JSON object',
                 b'{"model":"x","model":"y"}': 'the response repeats a JSON object key',
                 b'{"usage":{"input_tokens":NaN}}': 'the response contains a non-finite number',
                 b'{"id":"\\u0000"}': 'the response contains NUL or unpaired surrogate characters',
                 b'{"id":"\\ud800"}': 'the response contains NUL or unpaired surrogate characters',
                 b'[' * 100_000 + b']' * 100_000: 'the response is not valid JSON'}
        for raw, expect in cases.items():
            with self.subTest(raw=raw[:30]):
                result = self.read(raw)
                self.assertTrue(result.refused)
                self.assertEqual((result.codes, result.services, len(result.problems)), ((), (), 1))
                self.assertTrue(result.problems[0].startswith(f'The reading was not used: {expect}'), result.problems)
        self.assertEqual(self.read(None).problems, ('The reading was not used: there are no response bytes.',))

    def test_a_request_without_its_revision_text_is_refused(self):
        request = ProviderRequest(provider=self.request.provider, adapter_version=self.request.adapter_version,
                                  body=self.request.body, canonical_sha256=self.request.canonical_sha256, contexts=())
        result = self.read(fixture_bytes(self.fixture), request)
        self.assertEqual(result.problems, ('The reading was not used: the request carries no revision text to locate '
                                           'quotes in.',))

    def test_a_stored_run_reads_the_same_after_a_json_round_trip(self):
        stored = json.loads(json.dumps({'body': self.request.body, 'contexts': list(self.request.contexts)}))
        rebuilt = ProviderRequest(provider=self.module.NAME, adapter_version=self.module.ADAPTER_VERSION,
                                  body=stored['body'], canonical_sha256=self.request.canonical_sha256,
                                  contexts=tuple(stored['contexts']))
        raw = fixture_bytes(self.fixture)
        self.assertEqual(self.module.read_response(rebuilt, raw), self.read(raw))


class AstraAnswerTests(_GoodAnswerContract, OfflineTestCase):
    adapter_class = AstraParticipant
    module = openai_astra
    other = anthropic_fable
    fixture = 'astra-colonoscopy.response.json'

    def refused(self, raw):
        result = self.read(raw)
        self.assertTrue(result.refused)
        self.assertEqual((result.codes, result.services, result.date_of_service), ((), (), ''))
        self.assertEqual(len(result.problems), 1)
        return result.problems[0]

    def envelope(self, **changes):
        envelope = astra_envelope()
        envelope.update(changes)
        return json.dumps(envelope).encode()

    def test_a_refusal_item_refuses_the_reading_and_never_repeats_what_the_model_wrote(self):
        # Refutation round 1, IND-2 (I9): the model writes its refusal, and it can write descriptor-like wording there;
        # the problem - shown on the page, in the reports and in the trace - names the refusal by its length only
        for text in ("I can't help with\nthat request.", REFUSAL_WORDING):
            envelope = astra_envelope()
            envelope['output'][1]['content'] = [{'type': 'refusal', 'refusal': text}]
            with self.subTest(text=text[:20]):
                problem = self.refused(json.dumps(envelope).encode())
                self.assertEqual(problem, f'The reading was not used: the model refused (its message, {len(text):,} '
                                          'characters, is not repeated).')
                for words in ("can't help", 'SYNTHETIC-DESCRIPTOR', 'removal of lesion', 'I will not code'):
                    self.assertNotIn(words, problem)
        envelope = astra_envelope()  # beside output text, a refusal still refuses everything
        envelope['output'][1]['content'].append({'type': 'refusal', 'refusal': ''})
        self.assertEqual(self.refused(json.dumps(envelope).encode()),
                         'The reading was not used: the model refused (no reason was given).')

    def test_an_incomplete_response_is_refused_as_truncated(self):
        self.assertEqual(self.refused(self.envelope(status='incomplete',
                                                    incomplete_details={'reason': 'max_output_tokens'})),
                         'The reading was not used: the response was cut off at the output limit.')
        self.assertEqual(self.refused(self.envelope(status='incomplete',
                                                    incomplete_details={'reason': 'content_filter'})),
                         'The reading was not used: the response is incomplete (content_filter).')
        self.assertEqual(self.refused(self.envelope(status='incomplete', incomplete_details=None)),
                         'The reading was not used: the response is incomplete.')
        # a stated reason that is not one word is named by its length, never repeated (IND-2, I9)
        long_reason = {'reason': REFUSAL_WORDING}
        self.assertEqual(self.refused(self.envelope(status='incomplete', incomplete_details=long_reason)),
                         'The reading was not used: the response is incomplete (a value of '
                         f'{len(REFUSAL_WORDING):,} characters, not repeated).')
        self.assertIn(f'its status is a value of {len(REFUSAL_WORDING):,} characters, not repeated, not completed',
                      self.refused(self.envelope(status=REFUSAL_WORDING)))
        envelope = astra_envelope()
        envelope['output'][1]['status'] = 'incomplete'
        self.assertEqual(self.refused(json.dumps(envelope).encode()),
                         'The reading was not used: the response was cut off at the output limit.')

    def test_any_status_but_completed_is_refused(self):
        for status in ('failed', 'in_progress', 'queued', 'cancelled', None, 7):
            with self.subTest(status=status):
                self.assertIn('not completed', self.refused(self.envelope(status=status)))

    def test_another_model_is_refused_and_never_read(self):
        """I6: only the exact model requested, gpt-6-astra. The vendor lists no other snapshot or alias of it, so a
        dated name - a real calendar date or not - is another model as far as CPT Studio can tell, and its answer,
        tool calls included, is never read (refutation round 1, EV-6)."""
        for model in ('gpt-6-astra-mini', 'gpt-6-astra-pro-2026-10-01', 'gpt-6', 'gpt-6-astra-2026-10', 'GPT-6-ASTRA',
                      'gpt-6-astra ', 'gpt-5.5', '', 'gpt-6-astra-2026-09-15', 'gpt-6-astra-2026-10-15',
                      'gpt-6-astra-0000-00-00', 'gpt-6-astra-9999-99-99', 'gpt-6-astra-2026-13-45'):
            with self.subTest(model=model):
                problem = self.refused(self.envelope(model=model))
                self.assertIn('as the model that answered, not gpt-6-astra', problem)
        self.assertIn('names no model', self.refused(self.envelope(model=None)))
        self.assertIn('names no model', self.refused(self.envelope(model=['gpt-6-astra'])))
        self.assertIn("names model 'gpt-6-astra ' as the model", self.refused(self.envelope(model='gpt-6-astra ')))
        refused = self.read(self.envelope(model='gpt-6-astra-2026-09-15'))
        self.assertEqual(refused.returned_model, 'gpt-6-astra-2026-09-15')  # what answered is kept, never read
        dated = json.loads(astra_tool_call(('call_dated_1', 'cms_code_facts', {'codes': ['45385'],
                                                                               'date_of_service': ''})))
        dated['model'] = 'gpt-6-astra-2026-10-15'
        self.assertEqual(openai_astra.parse_turn(json.dumps(dated).encode()), loop.FINAL)  # nor its tool calls run
        refused = self.read(self.envelope(model='gpt-6-astra-mini'))
        self.assertEqual(refused.returned_model, 'gpt-6-astra-mini')  # what answered is kept, the answer is not read

    def test_the_model_is_checked_before_anything_else_the_response_says(self):
        problem = self.refused(self.envelope(model='gpt-6-astra-mini', status='incomplete'))
        self.assertIn("names model 'gpt-6-astra-mini' as the model that answered", problem)

    def test_output_without_a_message_text_is_refused(self):
        for output, expect in (([], 'carries no output text'),
                               ([{'type': 'reasoning', 'id': 'rs_x', 'summary': []}], 'carries no output text'),
                               ({'type': 'message'}, 'has no output list'),
                               ([{'type': 'message', 'content': 'text'}], 'has no content list'),
                               ([{'type': 'message', 'content': [{'type': 'output_text', 'text': None}]}],
                                'output text part of the response has no text')):
            with self.subTest(expect=expect):
                self.assertIn(expect, self.refused(self.envelope(output=output)))

    def test_output_text_parts_are_joined_in_order_and_other_items_ignored(self):
        answer = json.dumps(fixture_reading())
        envelope = astra_envelope()
        envelope['output'] = [{'type': 'reasoning', 'summary': [{'type': 'summary_text', 'text': '{"x":1}'}]},
                              {'type': 'message', 'content': [{'type': 'output_text', 'text': answer[:40]}]},
                              {'type': 'web_search_call', 'text': 'ignored'},
                              {'type': 'message', 'content': [{'type': 'output_text', 'text': answer[40:]}]}]
        result = self.read(json.dumps(envelope).encode())
        self.assertEqual((result.refused, [c.code for c in result.codes]), (False, ['45385', '45380']))


class FableAnswerTests(_GoodAnswerContract, OfflineTestCase):
    adapter_class = FableParticipant
    module = anthropic_fable
    other = openai_astra
    fixture = 'fable-colonoscopy.response.json'

    def refused(self, raw):
        result = self.read(raw)
        self.assertTrue(result.refused)
        self.assertEqual((result.codes, result.services, result.date_of_service), ((), (), ''))
        self.assertEqual(len(result.problems), 1)
        return result.problems[0]

    def envelope(self, **changes):
        envelope = fable_envelope()
        envelope.update(changes)
        return json.dumps(envelope).encode()

    def test_the_same_answer_reads_the_same_from_either_vendor(self):
        astra = AstraParticipant(self.tmp / 'x.env')
        astra_reading = astra.read(astra.build_request(NOTE, PAGES, 'paste', None),
                                   fixture_bytes('astra-colonoscopy.response.json'))
        fable_reading = self.read(fixture_bytes(self.fixture))
        for field in ('date_of_service', 'date_evidence', 'services', 'codes', 'not_coded', 'questions',
                      'extraction_issues', 'problems', 'refused', 'unverified_quotes'):
            self.assertEqual(getattr(fable_reading, field), getattr(astra_reading, field), field)

    def test_a_max_tokens_stop_is_refused_as_truncated(self):
        self.assertEqual(self.refused(self.envelope(stop_reason='max_tokens')),
                         'The reading was not used: the response was cut off at the output limit.')

    def test_a_refusal_stop_is_refused_with_its_category(self):
        self.assertEqual(self.refused(self.envelope(stop_reason='refusal', stop_details={
            'type': 'refusal', 'category': 'reasoning_extraction', 'explanation': 'synthetic'})),
            'The reading was not used: the model refused (category reasoning_extraction).')
        for details in (None, {'type': 'refusal', 'category': None}, 'refusal'):
            with self.subTest(details=details):
                self.assertEqual(self.refused(self.envelope(stop_reason='refusal', stop_details=details)),
                                 'The reading was not used: the model refused (no category was given).')
        # a category that is not one word is named by its length, never repeated (IND-2, I9); nor is the explanation
        problem = self.refused(self.envelope(stop_reason='refusal', stop_details={
            'type': 'refusal', 'category': REFUSAL_WORDING[:60], 'explanation': REFUSAL_WORDING}))
        self.assertEqual(problem, 'The reading was not used: the model refused (a category of 60 characters, not '
                                  'repeated).')
        self.assertIn(f'it stopped for a value of {len(REFUSAL_WORDING):,} characters, not repeated, not at the end',
                      self.refused(self.envelope(stop_reason=REFUSAL_WORDING)))

    def test_any_other_stop_is_refused(self):
        for stop in ('stop_sequence', 'tool_use', 'pause_turn', 'model_context_window_exceeded', None):
            with self.subTest(stop=stop):
                self.assertIn('not at the end of its turn', self.refused(self.envelope(stop_reason=stop)))

    def test_another_model_is_refused_and_never_read(self):
        """I6: claude-fable-5-1 is a snapshot, not an alias, so only that exact name is accepted."""
        for model in ('claude-opus-5-5', 'claude-fable-5', 'claude-fable-5-1-20261001', 'Claude-Fable-5-1', ''):
            with self.subTest(model=model):
                self.assertIn('as the model that answered, not claude-fable-5-1',
                              self.refused(self.envelope(model=model)))
        self.assertIn('names no model', self.refused(self.envelope(model=None)))

    def test_a_server_side_fallback_is_refused(self):
        envelope = fable_envelope()
        envelope['content'].insert(0, {'type': 'fallback', 'from': {'model': 'claude-fable-5-1'},
                                       'to': {'model': 'claude-fable-5-1'}})
        self.assertIn('a server-side fallback took part', self.refused(json.dumps(envelope).encode()))
        envelope = fable_envelope()
        envelope['usage']['iterations'] = [{'type': 'message', 'input_tokens': 10, 'output_tokens': 0},
                                           {'type': 'fallback_message', 'model': 'claude-fable-5-1'}]
        self.assertIn('a server-side fallback took part', self.refused(json.dumps(envelope).encode()))
        envelope = fable_envelope()  # a plain iteration list is no fallback
        envelope['usage']['iterations'] = [{'type': 'message', 'input_tokens': 10, 'output_tokens': 5}]
        self.assertFalse(self.read(json.dumps(envelope).encode()).refused)

    def test_the_model_is_checked_before_anything_else_the_response_says(self):
        self.assertIn("names model 'claude-opus-5-5' as the model that answered",
                      self.refused(self.envelope(model='claude-opus-5-5', stop_reason='max_tokens')))

    def test_a_response_that_is_not_a_message_or_carries_no_text_is_refused(self):
        self.assertIn('is not a message', self.refused(self.envelope(type='error')))
        self.assertIn('has no content list', self.refused(self.envelope(content={'type': 'text'})))
        self.assertIn('carries no text block', self.refused(self.envelope(content=[
            {'type': 'thinking', 'thinking': '{"date_of_service":{}}', 'signature': 'synthetic'}])))
        self.assertIn('text block of the response has no text', self.refused(self.envelope(content=[
            {'type': 'text', 'text': 7}])))

    def test_text_blocks_are_joined_in_order_and_thinking_is_never_read(self):
        answer = json.dumps(fixture_reading())
        poisoned = json.dumps(empty_reading(codes=[code('99999')]))
        result = self.read(self.envelope(content=[
            {'type': 'thinking', 'thinking': poisoned, 'signature': 'synthetic'}, {'type': 'text', 'text': answer[:25]},
            {'type': 'redacted_thinking', 'data': 'synthetic'}, {'type': 'text', 'text': answer[25:]}]))
        self.assertEqual((result.refused, [c.code for c in result.codes]), (False, ['45385', '45380']))


class SoleObjectTests(OfflineTestCase):
    """reading.sole_object (HARNESS.md 12.8), the one implementation both of Fable's harness-3 readers use: exactly one
    JSON object, alone or alone in a single json code fence, its text returned unchanged; anything else refused in CPT
    Studio's own words; what still is not one object is left to the strict reader."""
    OBJECT = '{"a": [1, "```"], "b": {"c": "x"}}'  # backticks inside a string are the object's own

    def test_a_bare_object_or_one_alone_in_a_single_fence_is_returned_unchanged(self):
        o = self.OBJECT
        cases = {o: o, f' \n\t{o}\r\n ': o, f'```json\n{o}\n```': o, f'```\n{o}\n```': o,
                 f'```json\r\n{o}\r\n```': o, f'\n\n```json  \n\n  {o}\n\n  ```\n': o, '{}': '{}',
                 '```json\n{\n  "a": 1\n}\n```': '{\n  "a": 1\n}'}
        for text, expected in cases.items():
            with self.subTest(text=text[:16]):
                self.assertEqual(reading.sole_object(text), (expected, ''))

    def test_anything_else_is_refused_in_cpt_studios_own_words(self):
        o = self.OBJECT
        cases = {
            'prose before': f'{PROSE_MARK}: {o}', 'prose after': f'{o}\n{PROSE_MARK}.',
            'prose before a fence': f'{PROSE_MARK}\n```json\n{o}\n```',
            'prose after a fence': f'```json\n{o}\n```\n{PROSE_MARK}',
            'a fence naming another language': f'```javascript\n{o}\n```',
            'a fence naming JSON in capitals': f'```JSON\n{o}\n```', 'a fence on one line': f'```json {o} ```',
            "a fence closed on the object's line": f'```json\n{o}```', 'an unclosed fence': f'```json\n{o}',
            'a fence closed twice': f'```json\n{o}\n```\n```', 'an empty fence': '```json\n\n```',
            'tildes for a fence': f'~~~json\n{o}\n~~~', 'an array': f'[{o}]', 'a string': '"{}"', 'a number': '7',
            'a truncated object': o[:-3], 'nothing': '', 'only whitespace': ' \n\t\r',
            'a no-break space before': ' ' + o, 'a form feed after': o + '\x0c', 'a byte order mark': '﻿' + o,
            'a zero-width space after': o + '​',
        }
        for label, text in cases.items():
            with self.subTest(label):
                self.assertEqual(reading.sole_object(text), ('', reading.NOT_ONE_OBJECT))
        for value in (None, b'{}', 7):
            self.assertEqual(reading.sole_object(value), ('', 'there is no answer text'))

    def test_what_still_is_not_one_object_is_handed_on_unchanged_and_the_strict_reader_refuses_it(self):
        o = self.OBJECT
        cases = ((f'{o}\n{o}', f'{o}\n{o}'),  # two objects
                 (f'```json\n{o}\n```\n```json\n{o}\n```', f'{o}\n```\n```json\n{o}'),  # two fences
                 (f'```json\n{o}\n{o}\n```', f'{o}\n{o}'),  # two objects in one fence
                 (o[:-1], o[:-1]),  # a truncated object that happens to close a brace
                 (f'{o} and {{x}}', f'{o} and {{x}}'))  # prose that happens to close a brace
        for text, handed in cases:
            with self.subTest(text=text[:20]):
                self.assertEqual(reading.sole_object(text), (handed, ''))
                with self.assertRaises(reading.JSONRefused):
                    reading.strict_json_text(handed)


class FableUnconstrainedAnswerTests(OfflineTestCase):
    """HARNESS.md 12.8: a harness-4 Fable answer (as a harness-3 one), which nothing at Anthropic constrained, is read
    only when it is exactly one JSON object, alone or alone in a single json code fence; anything else is refused whole
    in CPT Studio's own words. Then everything that already happened happens: strict JSON, CPT Studio's own schema
    validation, the bounds and the located quotes (I7) - and before all of it the wrong-model, fallback and stop-reason
    refusals (I6)."""

    def setUp(self):
        super().setUp()
        self.adapter = FableParticipant(self.tmp / 'never-read.env')
        self.request = self.adapter.build_request(NOTE, PAGES, 'paste', None)
        self.answer = json.dumps(fixture_reading())
        self.good = self.adapter.read(self.request, fixture_bytes('fable-colonoscopy.response.json'))
        self.assertEqual((self.good.refused, self.good.problems, self.good.unverified_quotes,
                          self.good.adapter_version), (False, (), 0, 'anthropic-messages@cptstudio-harness-4'))

    def read(self, text, **fields):
        return self.adapter.read(self.request, fable_with(text, **fields))

    def content(self, *blocks):
        return self.adapter.read(self.request, json.dumps(dict(fable_envelope(), content=list(blocks))).encode())

    def refused(self, text, **fields):
        result = self.read(text, **fields)
        self.assertTrue(result.refused)
        self.assertEqual((result.codes, result.services, result.date_of_service, result.questions), ((), (), '', ()))
        (problem,) = result.problems
        return problem

    def test_a_bare_object_and_one_alone_in_a_single_fence_are_read_alike(self):
        pretty = json.dumps(fixture_reading(), indent=2)
        for text in (self.answer, f'\n  {self.answer}\n\n', f'```json\n{self.answer}\n```', f'```\n{self.answer}\n```',
                     f'\n```json\r\n{pretty}\r\n```\n', f'```json\n\n{pretty}\n\n```'):
            with self.subTest(text=text[:12]):
                self.assertEqual(self.read(text), self.good)

    def test_text_blocks_are_joined_before_the_object_is_found_and_thinking_is_never_read(self):
        fenced = f'```json\n{self.answer}\n```'
        thinking = {'type': 'thinking', 'thinking': '', 'signature': 'synthetic'}
        self.assertEqual(self.content(thinking, {'type': 'text', 'text': fenced[:9]},
                                      {'type': 'text', 'text': fenced[9:]}), self.good)
        held = {'type': 'thinking', 'thinking': fenced, 'signature': 'synthetic'}  # an object there answers nothing
        self.assertEqual(self.content(held, {'type': 'text', 'text': PROSE_MARK}).problems, (NOT_ONE,))
        self.assertEqual(self.content(thinking, {'type': 'text', 'text': 'Here is the reading.'},
                                      {'type': 'text', 'text': self.answer}).problems, (NOT_ONE,))

    def test_anything_but_one_object_is_refused_whole_in_cpt_studios_own_words(self):
        answer = self.answer
        not_one = {'prose before': f'{PROSE_MARK} {answer}', 'prose after': f'{answer}\n\n{PROSE_MARK}',
                   'prose before a fence': f'{PROSE_MARK}\n```json\n{answer}\n```',
                   'prose after a fence': f'```json\n{answer}\n```\n{PROSE_MARK}',
                   'a fence naming another language': f'```js\n{answer}\n```',
                   'an unclosed fence': f'```json\n{answer}',
                   'a truncated object': answer[:-40], 'an array': f'[{answer}]',
                   'model wording alone': REFUSAL_WORDING, 'nothing': ''}
        for label, text in not_one.items():
            with self.subTest(label):
                problem = self.refused(text)
                self.assertEqual(problem, NOT_ONE)
        closes = answer[:answer.index('}, "services"') + 1]  # a truncated object that happens to close a brace
        self.assertTrue(closes.endswith('}'))
        strict = {'two objects': f'{answer}\n{answer}', 'two objects in one fence': f'```json\n{answer}\n{answer}\n```',
                  'two fences': f'```json\n{answer}\n```\n\n```json\n{answer}\n```',
                  'a truncated object that closes a brace': closes,
                  'prose closing a brace after the object': f'{answer} {PROSE_MARK} {{1}}'}
        for label, text in strict.items():
            with self.subTest(label):
                problem = self.refused(text)
                self.assertTrue(problem.startswith('The reading was not used: the answer is not valid JSON ('), problem)
                self.assertNotIn(PROSE_MARK, problem)
        for words in (PROSE_MARK, 'SYNTHETIC-DESCRIPTOR', 'I will not code', 'colonoscope'):
            self.assertNotIn(words, NOT_ONE)

    def test_strict_json_the_schema_and_the_bounds_refuse_as_before_inside_a_fence(self):
        def fenced(value):
            return f'```json\n{value if isinstance(value, str) else json.dumps(value)}\n```'
        good = fixture_reading()
        lacking = dict(good)
        del lacking['not_coded']
        cases = {
            # harness-4 sets a field outside the schema aside (FableContractTests); a field the schema requires is
            # still required, and a wrong type still refuses the answer whole
            fenced(lacking): "the answer breaks the reading schema: the reading lacks the required field 'not_coded'",
            fenced(changed(good, codes=[dict(good['codes'][0], units='1')])):
                'the answer breaks the reading schema: codes[0].units is not an integer',
            fenced('{"date_of_service":{"value":"","evidence":[]},"date_of_service":{"value":"","evidence":[]}}'):
                'the answer repeats a JSON object key',
            fenced(json.dumps(empty_reading())[:-1] + ',"x":NaN}'): 'the answer contains a non-finite number',
            fenced(json.dumps(empty_reading(), ensure_ascii=True).replace('[]', '["\\ud800"]', 1)):
                'the answer contains NUL or unpaired surrogate characters',
            fenced(empty_reading(codes=[code() for _ in range(65)])):
                'it lists 65 codes, more than the 64 this adapter accepts',
        }
        for text, expect in cases.items():
            with self.subTest(expect=expect):
                problem = self.refused(text)
                self.assertTrue(problem.startswith(f'The reading was not used: {expect}'), problem)
        result = self.read(fenced(empty_reading(services=[service(evidence=[
            'The colonoscope was advanced to the cecum.', 'not in the note at all, verbatim'])])))
        quotes = result.services[0].evidence  # located exactly as a bare object's are (I7)
        self.assertEqual([(bool(item.spans), item.reason) for item in quotes], [(True, ''), (False, 'not found')])
        self.assertEqual([NOTE[span.start:span.end] == span.text for span in quotes[0].spans], [True])

    def test_the_vendors_refusals_come_first_and_never_meet_the_object_rule(self):
        prose = f'{PROSE_MARK} and no object'
        wrong = self.read(prose, model='claude-opus-5-5')
        self.assertEqual((wrong.refused, wrong.returned_model), (True, 'claude-opus-5-5'))
        self.assertIn("it names model 'claude-opus-5-5' as the model that answered, not claude-fable-5-1",
                      wrong.problems[0])
        self.assertEqual(self.refused(self.answer[:-40], stop_reason='max_tokens'),
                         'The reading was not used: the response was cut off at the output limit.')
        self.assertEqual(self.refused(prose, stop_reason='refusal', stop_details={'category': 'cyber'}),
                         'The reading was not used: the model refused (category cyber).')
        self.assertIn('it stopped for tool_use, not at the end of its turn',
                      self.refused(f'```json\n{self.answer}\n```', stop_reason='tool_use'))
        envelope = json.loads(fable_with(f'```json\n{self.answer}\n```'))
        envelope['usage']['iterations'] = [{'type': 'fallback_message', 'model': 'claude-fable-5-1'}]
        self.assertIn('a server-side fallback took part',
                      self.adapter.read(self.request, json.dumps(envelope).encode()).problems[0])


class FableEarlierVersionTests(OfflineTestCase):
    """HARNESS.md 12.8: a stored harness@2 or harness@1 Fable run is read exactly as before. Its answer's text is read
    as JSON as it stands, so a fence or prose is refused there as it always was, and the readings are the harness@2
    head's own (sha256 pinned at 9d773838c). The requests are the harness@2 adapter's own bodies (fable_harness_2)."""

    def setUp(self):
        super().setUp()
        self.adapter = FableParticipant(self.tmp / 'never-read.env')
        self.current = self.adapter.build_request(NOTE, PAGES, 'pdf', ORIGINAL)
        body = fable_harness_2(self.current.body)
        self.requests = {version: ProviderRequest(provider='fable', adapter_version=version, body=body,
                                                  canonical_sha256=request_sha256(body), contexts=(NOTE,))
                         for version in (anthropic_fable.ADAPTER_VERSION_2, anthropic_fable.ADAPTER_VERSION_1)}

    def test_each_version_is_still_read_and_reads_as_the_harness_2_head_read_it(self):
        self.assertEqual(anthropic_fable.READ_VERSIONS, ('anthropic-messages@cptstudio-harness-4',
                                                         'anthropic-messages@cptstudio-harness-3',
                                                         'anthropic-messages@cptstudio-harness-2',
                                                         'anthropic-messages@cptstudio-harness-1'))
        raw = fixture_bytes('fable-colonoscopy.response.json')
        older, oldest = (anthropic_fable.read_response(self.requests[version], raw) for version in
                         (anthropic_fable.ADAPTER_VERSION_2, anthropic_fable.ADAPTER_VERSION_1))
        self.assertEqual((older.refused, older.adapter_version), (False, anthropic_fable.ADAPTER_VERSION_2))
        self.assertEqual(sha256_json(older), HARNESS_2_READINGS['fixture'])
        self.assertEqual(sha256_json(oldest), HARNESS_2_READINGS['fixture as harness@1'])
        current = self.adapter.read(self.current, raw)  # a bare object reads alike in every version but its name
        self.assertEqual(dataclasses.replace(older, adapter_version=current.adapter_version), current)

    def test_a_fence_or_prose_is_refused_there_as_it_always_was(self):
        answer = json.dumps(fixture_reading())
        cases = ((f'```json\n{answer}\n```', 'the answer is not valid JSON (Expecting value at character 0)'),
                 (f'```\n{answer}\n```', 'the answer is not valid JSON (Expecting value at character 0)'),
                 (f'Here is the reading: {answer}', 'the answer is not valid JSON (Expecting value at character 0)'),
                 (f'{answer}\nDone.', f'the answer is not valid JSON (Extra data at character {len(answer) + 1})'))
        for version, request in self.requests.items():
            for text, expect in cases:
                with self.subTest(version=version, text=text[:12]):
                    result = anthropic_fable.read_response(request, fable_with(text))
                    self.assertEqual((result.refused, result.adapter_version, result.problems),
                                     (True, version, (f'The reading was not used: {expect}.',)))
        fenced = anthropic_fable.read_response(self.requests[anthropic_fable.ADAPTER_VERSION_2],
                                               fable_with(f'```json\n{answer}\n```'))
        self.assertEqual(sha256_json(fenced), HARNESS_2_READINGS['fenced'])

    def test_a_harness_3_answer_is_never_read_as_an_earlier_version_nor_an_earlier_one_as_harness_3(self):
        fenced = fable_with(f'```json\n{json.dumps(fixture_reading())}\n```')
        self.assertFalse(self.adapter.read(self.current, fenced).refused)  # harness-4 reads its fence, as harness-3 did
        self.assertTrue(anthropic_fable.read_response(self.requests[anthropic_fable.ADAPTER_VERSION_2], fenced).refused)
        for version in ('anthropic-messages@cptstudio-harness-5', 'anthropic-messages@cptstudio-harness-0'):
            request = dataclasses.replace(self.current, adapter_version=version)
            with self.subTest(version=version):
                self.assertEqual(self.adapter.read(request, fenced).problems, (
                    f"The reading was not used: it was recorded for 'fable' with adapter {version!r}, not 'fable' with "
                    "'anthropic-messages@cptstudio-harness-4'.",))


WALK = FIXTURES / 'fable-walk'  # Fable's three refused walk answers of 2026-11-05 and their runs' context 0
# (answer sha256 prefix, what the harness-3 schema check said, the set-aside field names, the codes its reading
# proposes)
WALK_ANSWERS = {
    'h2a': ('ef60812dcaa8e6d3', 'a value of 9 characters', ('code_note',),
            ('43249', '43251', '43239', '45385', '45380', '45381')),
    'h2b': ('bc621389dcc7c821', 'a value of 16 characters', ('service_ids_note',), ('45390', '45380')),
    'h2c': ('5918482ac44558f1', 'a value of 13 characters', ('evidence_note', 'reason_detail'), ('43239', '43248')),
}


class FableContractTests(OfflineTestCase):
    """HARNESS.md, "Harness repair 3", F-CONTRACT: a harness-4 Fable answer's fields outside its schema are set aside
    before it is validated - named in the problems (where, empty or not, size; never the text), never read - and what
    remains is validated exactly as strictly as before. A stored harness-3 answer is read exactly as it was on the walk:
    refused whole for the same field."""

    def setUp(self):
        super().setUp()
        self.adapter = FableParticipant(self.tmp / 'never-read.env')
        self.request = self.adapter.build_request(NOTE, PAGES, 'paste', None)
        self.harness_3 = self.harness_3_request(self.request)

    @staticmethod
    def harness_3_request(request, context=None):
        body = fable_harness_3(request.body)
        return ProviderRequest(provider='fable', adapter_version=anthropic_fable.ADAPTER_VERSION_3, body=body,
                               canonical_sha256=request_sha256(body), contexts=(context or request.contexts[0],))

    def read(self, value, request=None):
        return self.adapter.read(request or self.request, fable_with(f'```json\n{json.dumps(value)}\n```'))

    def test_the_three_refused_walk_answers_are_read_and_their_extra_fields_named(self):
        for name, (prefix, field, extras, codes) in WALK_ANSWERS.items():
            raw = (WALK / f'{name}.response.json').read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest()[:16], prefix)  # the stored bytes, unchanged
            context = (WALK / f'{name}.context.txt').read_text(encoding='utf-8')
            request = dataclasses.replace(self.request, contexts=(context,))
            with self.subTest(walk=name):
                then = anthropic_fable.read_response(self.harness_3_request(request, context), raw)
                self.assertEqual((then.refused, then.problems), (True, (
                    'The reading was not used: the answer breaks the reading schema: not_coded[0] has a field the '
                    f'schema does not allow ({field}).',)))
                now = anthropic_fable.read_response(request, raw)
                self.assertFalse(now.refused, now.problems)
                self.assertEqual(tuple(item.code for item in now.codes), codes)
                set_aside = [line for line in now.problems if 'outside the schema' in line]
                self.assertEqual(len(set_aside), len(extras))
                for line, extra in zip(set_aside, extras):
                    self.assertTrue(line.startswith(f'not_coded[0] field a value of {len(extra)} characters is '
                                                    'outside the schema; it was empty, and it was set aside'), line)
                    self.assertNotIn(extra, line)  # the model-written name is never repeated (I9)
                # the set-aside fields are the only difference: the same answer without them reads identically
                envelope = json.loads(raw)
                text = envelope['content'][-1]['text']
                answer = json.loads(reading.sole_object(text)[0])
                for extra in extras:
                    del answer['not_coded'][0][extra]
                envelope['content'][-1]['text'] = json.dumps(answer)
                clean = anthropic_fable.read_response(request, json.dumps(envelope).encode())
                self.assertEqual(dataclasses.replace(now, problems=tuple(line for line in now.problems
                                                                         if line not in set_aside)), clean)

    def test_a_field_outside_the_schema_with_content_is_set_aside_named_by_its_size_and_never_read(self):
        good = fixture_reading()
        noted = changed(good, codes=[dict(good['codes'][0], note=f'{PROSE_MARK} see 45390 instead')]
                        + good['codes'][1:], summary={'codes': ['45390'], 'why': PROSE_MARK})
        result = self.read(noted)
        base = self.read(good)
        self.assertFalse(result.refused)
        self.assertEqual(dataclasses.replace(result, problems=()), dataclasses.replace(base, problems=()))
        sizes = [len(json.dumps(value, sort_keys=True, separators=(',', ':')))
                 for value in (noted['codes'][0]['note'], noted['summary'])]
        self.assertEqual(sizes, [len(noted['codes'][0]['note']) + 2, 54])  # as canonical JSON, quotes included
        self.assertEqual(result.problems[:2], (
            f"codes[0] field 'note' is outside the schema; it held {sizes[0]} characters, kept in the raw response, "
            'and it was set aside and not read (an answer nothing constrained, HARNESS.md F-CONTRACT).',
            f"top-level field 'summary' is outside the schema; it held {sizes[1]} characters, kept in the raw "
            'response, and it was set aside and not read (an answer nothing constrained, HARNESS.md F-CONTRACT).'))
        for line in result.problems:
            self.assertNotIn(PROSE_MARK, line)
            self.assertNotIn('45390', line)
        self.assertNotIn('45390', [item.code for item in result.codes])  # a code named only there is never read
        # the same answer as harness-3 recorded it is refused whole, as it always was
        self.assertTrue(self.read(noted, self.harness_3).refused)

    def test_validation_is_not_relaxed_by_the_set_aside(self):
        good = fixture_reading()
        lacking = copy.deepcopy(good)
        del lacking['codes'][0]['units']
        cases = {
            'a required field missing': (lacking, "codes[0] lacks the required field 'units'"),
            'a wrong type': (changed(good, codes=[dict(good['codes'][0], units='1')]),
                             'codes[0].units is not an integer'),
            'a value no enum allows': (changed(good, codes=[dict(good['codes'][0], confidence='certain')]),
                                       'codes[0].confidence is not one of the values the schema allows'),
            'an object where a string belongs': (changed(good, codes=[dict(good['codes'][0], code={'value': '45385'})]),
                                                 'codes[0].code is not a string'),
            'a declared field inside an unknown one':
                (changed(good, extra={'codes': good['codes']}, codes='45385'), 'codes is not a list'),
        }
        for label, (value, expect) in cases.items():
            with self.subTest(label):
                result = self.read(value)
                self.assertTrue(result.refused)
                self.assertTrue(result.problems[0].startswith(
                    f'The reading was not used: the answer breaks the reading schema: {expect}'), result.problems)

    def test_nested_fields_are_set_aside_where_the_schema_declares_objects_only(self):
        good = fixture_reading()
        lesion = {'site': 'sigmoid colon', 'size': '6 mm', 'morphology': 'sessile', 'action': 'removed',
                  'specimen': 'jar 1', 'margin_note': ''}
        value = changed(good, services=[dict(good['services'][0], lesions=[lesion], extent_detail=None)],
                        date_of_service=dict(good['date_of_service'], value_note=[]))
        result = self.read(value)
        self.assertFalse(result.refused, result.problems)
        self.assertEqual([line.split(' is outside')[0] for line in result.problems[:3]],
                         ['date_of_service field a value of 10 characters',
                          'services[0].lesions[0] field a value of 11 characters',
                          'services[0] field a value of 13 characters'])  # in the answer's own order
        self.assertEqual(result.services[0].lesions, (ParticipantLesion(site='sigmoid colon', size='6 mm',
                                                                        morphology='sessile', action='removed',
                                                                        specimen='jar 1'),))

    def test_more_than_the_limit_refuses_the_answer_whole_and_set_aside_never_mutates(self):
        good = fixture_reading()
        many = dict(good, **{f'extra_{index}': '' for index in range(reading.MAX_SET_ASIDE + 1)})
        result = self.read(many)
        self.assertEqual((result.refused, result.problems), (True, (
            f'The reading was not used: the answer carries {reading.MAX_SET_ASIDE + 1} fields outside its schema, more '
            f'than the {reading.MAX_SET_ASIDE} this adapter sets aside.',)))
        at_limit = dict(good, **{f'extra_{index}': '' for index in range(reading.MAX_SET_ASIDE)})
        self.assertFalse(self.read(at_limit).refused)
        before = json.dumps(many, sort_keys=True)
        kept, removed = reading.set_aside(many, prompt.SCHEMA)
        self.assertEqual(json.dumps(many, sort_keys=True), before)
        self.assertEqual((len(removed), reading.schema_error(kept)), (reading.MAX_SET_ASIDE + 1, ''))

    def test_astra_and_the_earlier_versions_still_refuse_any_field_outside_the_schema(self):
        good = fixture_reading()
        noted = changed(good, not_coded=[dict(item, code_note='') for item in good['not_coded']] or
                        [{'service_ids': [], 'code': '', 'reason': 'other', 'evidence': [], 'code_note': ''}])
        astra = AstraParticipant(self.tmp / 'never-read.env')
        astra_request = astra.build_request(NOTE, PAGES, 'paste', None)
        self.assertTrue(astra.read(astra_request, astra_with(noted)).refused)  # a constrained answer that breaks it
        self.assertTrue(self.read(noted, self.harness_3).refused)
        self.assertFalse(self.read(noted).refused)

    def test_the_request_asks_for_exactly_the_schemas_fields(self):
        system = self.request.body['system']
        self.assertTrue(system.endswith(prompt.schema_instruction(prompt.SCHEMA) + prompt.fields_instruction()))
        self.assertEqual(prompt.fields_instruction(), prompt.FIELDS_INSTRUCTION + '\n')
        self.assertEqual(self.harness_3.body['system'], prompt.INSTRUCTIONS + prompt.schema_instruction(prompt.SCHEMA))
        self.assertEqual(fable_harness_3(self.request.body)['tools'], self.request.body['tools'])


class ReadingTests(OfflineTestCase):
    """The reading itself, through the Astra envelope (the Fable reader hands the same text to the same code)."""

    def setUp(self):
        super().setUp()
        self.adapter = AstraParticipant(self.tmp / 'never-read.env')
        self.request = self.adapter.build_request(NOTE, PAGES, 'paste', None)

    def read(self, answer):
        return self.adapter.read(self.request, astra_with(answer))

    def refused(self, answer):
        result = self.read(answer)
        self.assertTrue(result.refused, result.problems)
        self.assertEqual((result.codes, result.services, result.questions, result.not_coded), ((), (), (), ()))
        (problem,) = result.problems
        self.assertTrue(problem.startswith('The reading was not used: '))
        return problem

    def test_strict_json_inside_the_answer(self):
        cases = {'{"date_of_service":{"value":"","evidence":[]},"date_of_service":{"value":"","evidence":[]}}':
                 'the answer repeats a JSON object key',
                 json.dumps(empty_reading())[:-1] + ',"x":NaN}': 'the answer contains a non-finite number',
                 json.dumps(empty_reading())[:-1] + ',"x":Infinity}': 'the answer contains a non-finite number',
                 json.dumps(empty_reading())[:-1] + ',"x":1e999}': 'the answer contains a number too large',
                 json.dumps(empty_reading(), ensure_ascii=True).replace('[]', '["\\u0000"]', 1):
                     'the answer contains NUL or unpaired surrogate characters',
                 json.dumps(empty_reading(), ensure_ascii=True).replace('[]', '["\\udc00"]', 1):
                     'the answer contains NUL or unpaired surrogate characters',
                 '': 'the answer is not valid JSON', 'not json': 'the answer is not valid JSON',
                 '```json\n{}\n```': 'the answer is not valid JSON'}
        for answer, expect in cases.items():
            with self.subTest(answer=answer[:40]):
                self.assertIn(expect, self.refused(answer))

    def test_the_schema_is_enforced_here_whatever_the_vendor_did(self):
        good = fixture_reading()
        no_codes = dict(good)
        del no_codes['codes']
        with_extra = dict(good, summary='extra')
        cases = (
            ([], 'the reading is not an object'),
            (no_codes, "the reading lacks the required field 'codes'"),
            (with_extra, "the reading has a field the schema does not allow ('summary')"),
            (changed(good, codes=[dict(good['codes'][0], units=1.0)]), 'codes[0].units is not an integer'),
            (changed(good, codes=[dict(good['codes'][0], units=True)]), 'codes[0].units is not an integer'),
            (changed(good, codes=[dict(good['codes'][0], units='1')]), 'codes[0].units is not an integer'),
            (changed(good, codes=[dict(good['codes'][0], confidence='certain')]),
             'codes[0].confidence is not one of the values the schema allows'),
            (changed(good, services=[dict(good['services'][0], family='hepatology')]),
             'services[0].family is not one of the values the schema allows'),
            (changed(good, services=[dict(good['services'][0], status='done')]),
             'services[0].status is not one of the values the schema allows'),
            (changed(good, not_coded=[{'service_ids': [], 'code': '', 'reason': 'because', 'evidence': []}]),
             'not_coded[0].reason is not one of the values the schema allows'),
            (changed(good, services=[dict(good['services'][0], lesions=[dict(good['services'][0]['lesions'][0],
                                                                                 color='red')])]),
             "services[0].lesions[0] has a field the schema does not allow ('color')"),
            (changed(good, codes=[dict(good['codes'][0], modifiers='59')]), 'codes[0].modifiers is not a list'),
            (changed(good, codes=[dict(good['codes'][0], evidence=[{'text': 'x'}])]),
             'codes[0].evidence[0] is not a string'),
            (changed(good, date_of_service={'value': None, 'evidence': []}), 'date_of_service.value is not a string'),
            (changed(good, extraction_issues=[{'page': '2', 'issue': 'x'}]),
             'extraction_issues[0].page is not an integer'),
            (changed(good, clarifications=[{'question': 'q', 'why': 'w', 'service_ids': [], 'evidence': []},
                                           None]), 'clarifications[1] is not an object'),
        )
        for answer, expect in cases:
            with self.subTest(expect=expect):
                self.assertEqual(self.refused(answer),
                                 f'The reading was not used: the answer breaks the reading schema: {expect}.')

    def test_the_validator_follows_prompt_schema_and_refuses_keywords_it_does_not_implement(self):
        self.assertEqual(reading.schema_error(fixture_reading()), '')
        self.assertEqual(reading.schema_error(empty_reading()), '')
        with self.assertRaises(ValueError):
            reading.schema_error({}, {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False,
                                      'minProperties': 1})
        with self.assertRaises(ValueError):
            reading.schema_error(1, {'type': 'number'})
        with self.assertRaises(ValueError):
            reading.schema_error({}, {'type': 'object', 'properties': {}, 'required': []})

    def test_the_bounds_refuse_the_reading_whole_and_name_the_count(self):
        evidence = lambda n: [f'quote {index:02d} in the note' for index in range(n)]  # noqa: E731
        cases = (
            ({'services': [service(i) for i in range(64)]}, {'services': [service(i) for i in range(65)]},
             'it lists 65 services, more than the 64 this adapter accepts'),
            ({'codes': [code() for _ in range(64)]}, {'codes': [code() for _ in range(65)]},
             'it lists 65 codes, more than the 64 this adapter accepts'),
            ({'not_coded': [{'service_ids': [], 'code': '', 'reason': 'other', 'evidence': []}] * 64},
             {'not_coded': [{'service_ids': [], 'code': '', 'reason': 'other', 'evidence': []}] * 65},
             'it lists 65 not-coded items, more than the 64 this adapter accepts'),
            ({'clarifications': [{'question': 'q', 'why': 'w', 'service_ids': [], 'evidence': []}] * 32},
             {'clarifications': [{'question': 'q', 'why': 'w', 'service_ids': [], 'evidence': []}] * 33},
             'it lists 33 clarifications, more than the 32 this adapter accepts'),
            ({'extraction_issues': [{'page': 1, 'issue': 'x'}] * 64},
             {'extraction_issues': [{'page': 1, 'issue': 'x'}] * 65},
             'it lists 65 extraction issues, more than the 64 this adapter accepts'),
            ({'services': [service(evidence=evidence(16))]}, {'services': [service(evidence=evidence(17))]},
             'services[0].evidence lists 17 quotes, more than the 16 one item may have'),
            ({'codes': [code(evidence=evidence(16))]}, {'codes': [code(evidence=evidence(17))]},
             'codes[0].evidence lists 17 quotes, more than the 16 one item may have'),
            ({'date_of_service': {'value': '', 'evidence': evidence(16)}},
             {'date_of_service': {'value': '', 'evidence': evidence(17)}},
             'date_of_service.evidence lists 17 quotes, more than the 16 one item may have'),
            ({'codes': [code(evidence=['q' * 600])]}, {'codes': [code(evidence=['q' * 601])]},
             'codes[0].evidence[0] has 601 characters, more than the 600 one quote may have'),
            ({'codes': [code(basis='b' * 2000)]}, {'codes': [code(basis='b' * 2001)]},
             'codes[0].basis has 2,001 characters, more than the 2,000 one text field may have'),
            ({'services': [service(description='d' * 2000)]}, {'services': [service(description='d' * 2001)]},
             'services[0].description has 2,001 characters'),
            ({'services': [service(lesions=[{'site': 's', 'size': '', 'morphology': '', 'action': '',
                                             'specimen': ''}] * 64)]},
             {'services': [service(lesions=[{'site': 's', 'size': '', 'morphology': '', 'action': '',
                                             'specimen': ''}] * 65)]},
             'services[0].lesions lists 65 lesions, more than the 64 one item may have'),
            ({'codes': [code(modifiers=['59'] * 16)]}, {'codes': [code(modifiers=['59'] * 17)]},
             'codes[0].modifiers lists 17 modifiers'),
            ({'codes': [code(service_ids=['s1'] * 64)]}, {'codes': [code(service_ids=['s1'] * 65)]},
             'codes[0].service_ids lists 65 service ids'),
            ({'codes': [code(modifiers=['m' * 2000])]}, {'codes': [code(modifiers=['m' * 2001])]},
             'codes[0].modifiers[0] has 2,001 characters'),
        )
        for at_limit, over, expect in cases:
            with self.subTest(expect=expect):
                self.assertFalse(self.read(empty_reading(**at_limit)).refused)
                self.assertIn(expect, self.refused(empty_reading(**over)))

    def test_codes_are_kept_as_given_and_named_when_they_are_not_five_characters(self):
        values = ('45385', '0001F', 'G0121', '4538', '453850', '45385-59', ' 45385', '1234a', '')
        result = self.read(empty_reading(services=[service()], codes=[code(value) for value in values]))
        self.assertEqual([c.code for c in result.codes], list(values))  # nothing stripped, dropped or rewritten
        # each named as reading._token names it: quoted in a code, short-id or digits-and-punctuation shape, otherwise
        # by its length (refutation round 3; this pin moved from quoting every short token)
        named = ["'G0121'", "'4538'", "'453850'", "'45385-59'", 'a value of 6 characters', "'1234a'",
                 'a value of 0 characters']
        self.assertEqual(result.problems, tuple(
            f'codes[{index}] ({name}) is not a five-character CPT code; it is kept as given.'
            for index, name in enumerate(named, start=2)))

    def test_problems_name_a_long_value_by_its_length_and_never_repeat_it(self):
        """I9: a model could write descriptor-like text into a code, id or date field. The value is kept as given (the
        contract), but a problem names it by its length only."""
        long_code = 'Colonoscopy, flexible; with removal of polyp by snare technique'
        long_id = 'first service, the colonoscopy'
        result = self.read(empty_reading(
            date_of_service={'value': 'the twenty-first of October, 2026', 'evidence': []},
            services=[service(1, id=long_id), service(2, id=long_id)],
            codes=[code(long_code, service_ids=[]), code(long_code, units=0, service_ids=[])],
            not_coded=[{'service_ids': [], 'code': long_code, 'reason': 'other', 'evidence': []}]))
        self.assertEqual([c.code for c in result.codes], [long_code])
        self.assertEqual(result.problems, (
            'date_of_service a value of 33 characters is not a YYYY-MM-DD date; it was not used.',
            'services[1] repeats the service id a value of 30 characters.',
            'codes[0] (a value of 63 characters) is not a five-character CPT code; it is kept as given.',
            'codes[1] (a value of 63 characters) gives 0 units, outside 1 to 99; it was dropped.',
            'not_coded[0] (a value of 63 characters) is not a five-character CPT code; it is kept as '
            'given.'))
        for text in ('Colonoscopy', 'first service', 'twenty-first'):
            self.assertFalse(any(text in problem for problem in result.problems), text)

    def test_a_field_name_the_model_wrote_is_named_by_its_length_when_it_is_not_one_word(self):
        # IND-2 (I9): an extra field's name is model-written too; a refusal names it only when it is a short token
        problem = self.refused(dict(fixture_reading(), **{REFUSAL_WORDING: 'x'}))
        self.assertEqual(problem, 'The reading was not used: the answer breaks the reading schema: the reading has a '
                                  f'field the schema does not allow (a value of {len(REFUSAL_WORDING):,} characters).')

    def test_units_outside_1_to_99_drop_that_code(self):
        units = (1, 99, 0, 100, -1, 10 ** 40)
        result = self.read(empty_reading(services=[service()], codes=[code(f'4538{i}', units=u)
                                                                      for i, u in enumerate(units)]))
        self.assertEqual([(c.code, c.units) for c in result.codes], [('45380', 1), ('45381', 99)])
        self.assertEqual(result.problems, (
            "codes[2] ('45382') gives 0 units, outside 1 to 99; it was dropped.",
            "codes[3] ('45383') gives 100 units, outside 1 to 99; it was dropped.",
            "codes[4] ('45384') gives -1 units, outside 1 to 99; it was dropped.",
            "codes[5] ('45385') gives over a million units, outside 1 to 99; it was dropped."))

    def test_a_date_of_service_that_is_not_a_calendar_date_is_not_used(self):
        # a value written with digits and date punctuation only is quoted; a word is named by its length (refutation
        # round 3: a problem quotes a model-written value only in a shape that cannot carry descriptor text)
        named = {'2026-02-30': "'2026-02-30'", '10/21/2026': "'10/21/2026'", '2026-10-21T09:00': "'2026-10-21T09:00'",
                 '2026-1-21': "'2026-1-21'", 'yesterday': 'a value of 9 characters'}
        for value, name in named.items():
            with self.subTest(value=value):
                result = self.read(empty_reading(date_of_service={'value': value, 'evidence': []}))
                self.assertEqual((result.refused, result.date_of_service), (False, ''))
                self.assertEqual(result.problems, (f'date_of_service {name} is not a YYYY-MM-DD date; it was not '
                                                   'used.',))
        self.assertEqual(self.read(empty_reading(date_of_service={'value': '2028-02-29', 'evidence': []}))
                         .date_of_service, '2028-02-29')

    def test_service_ids_that_repeat_or_name_no_service_are_named(self):
        result = self.read(empty_reading(
            services=[service(1), service(1), service(2)],
            codes=[code(service_ids=['s1', 's9', 's8'])],
            not_coded=[{'service_ids': ['s7'], 'code': '45378', 'reason': 'not_performed_at_this_encounter',
                        'evidence': []}],
            clarifications=[{'question': 'Was it completed?', 'why': 'extent', 'service_ids': ['s2', 's6'],
                             'evidence': []}]))
        self.assertFalse(result.refused)
        self.assertEqual(result.problems, ("services[1] repeats the service id 's1'.",
                                           "codes[0] ('45385') names 2 service ids that no service has.",
                                           'not_coded[0] names 1 service id that no service has.',
                                           'clarifications[0] names 1 service id that no service has.'))
        self.assertEqual(len(result.services), 3)

    def test_not_coded_and_questions_and_extraction_issues(self):
        result = self.read(empty_reading(
            services=[service()],
            not_coded=[{'service_ids': ['s1'], 'code': '', 'reason': 'included_in_another_code',
                        'evidence': ['A 3 mm polyp in the rectum was biopsied']},
                       {'service_ids': ['s1'], 'code': 'G0105', 'reason': 'other', 'evidence': []}],
            clarifications=[{'question': 'Was the biopsy a separate lesion?', 'why': 'Decides modifier use.',
                             'service_ids': ['s1'], 'evidence': ['biopsied with cold forceps']}],
            extraction_issues=[{'page': 2, 'issue': 'A table is missing.'}, {'page': 0, 'issue': 'x'},
                               {'page': -4, 'issue': 'y'}]))
        self.assertEqual([(n.code, n.reason) for n in result.not_coded],
                         [('', 'included_in_another_code'), ('G0105', 'other')])
        self.assertTrue(result.not_coded[0].evidence[0].spans)
        self.assertEqual(result.questions[0].question, 'Was the biopsy a separate lesion?')
        self.assertEqual(result.extraction_issues, (ExtractionIssue(page=2, issue='A table is missing.'),))
        self.assertEqual(result.problems, (
            "not_coded[1] ('G0105') is not a five-character CPT code; it is kept as given.",
            'extraction_issues[1] names page 0, which no document has; it was not used.',
            'extraction_issues[2] names page -4, which no document has; it was not used.'))

    def test_unverified_quotes_are_kept_counted_and_never_evidence(self):
        answer = empty_reading(services=[service(evidence=[
            'The colonoscope was advanced to the cecum.',  # found
            'the colonoscope was advanced to the cecum.',  # case differs: not found
            'Colonoscope advanced to cecum',  # paraphrase: not found
            '6 mm',  # too short
            'Technique: The colonoscope [Page 2] Findings',  # across a page marker: not found
        ])], codes=[code(evidence=['removed with a cold snare', 'polyp was resected'])])
        result = self.read(answer)
        quotes = result.services[0].evidence + result.codes[0].evidence
        self.assertEqual([(q.reason, bool(q.spans)) for q in quotes],
                         [('', True), ('not found', False), ('not found', False), ('too short', False),
                          ('not found', False), ('', True), ('not found', False)])
        self.assertEqual(result.unverified_quotes, 5)
        self.assertEqual(quotes[3].quote, '6 mm')  # kept as the participant wrote it


class LocatorTests(OfflineTestCase):
    def test_whitespace_runs_collapse_in_both_the_text_and_the_quote_and_nothing_else(self):
        text = 'Findings:\tA 6 mm  sessile\npolyp\r\n was removed.'
        self.assertEqual(located(text, 'A 6 mm sessile polyp was removed.'),
                         [(10, len(text), text[10:])])
        self.assertEqual(located(text, '  A 6\tmm\n\nsessile polyp  '), [(10, 31, 'A 6 mm  sessile\npolyp')])
        self.assertEqual(located(text, 'a 6 mm sessile polyp'), [])  # no case folding
        self.assertEqual(located(text, 'A 6 mm sessile polyp,'), [])  # no punctuation folding

    def test_every_occurrence_up_to_8_is_located_overlapping_included(self):
        text = ' '.join(['cold snare used.'] * 10)
        spans = located(text, 'cold snare used.')
        self.assertEqual(len(spans), 8)
        self.assertEqual([start for start, _, _ in spans], [17 * index for index in range(8)])
        self.assertEqual(located('aaaaaaaaaa', 'aaaaaaaa'), [(0, 8, 'aaaaaaaa'), (1, 9, 'aaaaaaaa'),
                                                             (2, 10, 'aaaaaaaa')])

    def test_too_short_means_fewer_than_8_non_space_characters(self):
        locator = reading.Locator('A 1 2 3 4 5 6 7 polyp; abcdefg h')
        self.assertEqual(locator.locate('1 2 3 4 5 6 7').reason, 'too short')  # 7 non-space characters
        self.assertEqual(locator.locate('1 2 3 4 5 6 7 polyp').reason, '')
        self.assertEqual(locator.locate('abcdefg h').reason, '')  # exactly 8
        for quote in ('', '   ', '\n\t', 'abcdefg'):
            self.assertEqual(locator.locate(quote).reason, 'too short')

    def test_offsets_are_exact_in_unicode_text_and_at_both_ends(self):
        text = 'Café visit — polyp noted.\n\n  Ends here'
        self.assertEqual(located(text, 'Café visit — polyp'), [(0, 18, 'Café visit — polyp')])
        self.assertEqual(located(text, 'noted. Ends here'), [(19, len(text), 'noted.\n\n  Ends here')])
        self.assertEqual(located('   leading space text', 'leading space'), [(3, 16, 'leading space')])

    def test_a_quote_across_a_page_boundary_is_found_only_as_the_text_runs(self):
        boundary = NOTE[PAGE_BREAK - 30:PAGE_BREAK + 30]
        spans = located(NOTE, boundary)
        self.assertEqual(spans, [(PAGE_BREAK - 30, PAGE_BREAK + 30, boundary)])  # verbatim revision text (I7)
        self.assertEqual(located(NOTE, boundary[:30] + '[Page 2]\n' + boundary[30:]), [])

    def test_every_span_is_an_exact_slice_that_collapses_to_its_quote(self):
        """I7, over every substring of the note between two non-space characters (sampled)."""
        locator = reading.Locator(NOTE)
        checked = 0
        for start in range(0, len(NOTE), 7):
            for length in (8, 15, 33, 80):
                quote = NOTE[start:start + length]
                result = locator.locate(quote)
                for span in result.spans:
                    self.assertEqual(NOTE[span.start:span.end], span.text)
                    self.assertTrue(span.exact)
                    self.assertEqual(' '.join(span.text.split()), ' '.join(quote.split()))
                    checked += 1
                if result.reason == '':
                    self.assertGreaterEqual(len(result.spans), 1)
        self.assertGreater(checked, 250)

    def test_locating_is_linear_enough_for_the_largest_answer(self):
        """64 services x 16 quotes + 64 codes x 16 + 64 not-coded x 16 + 32 x 16 + 16: 3,600 distinct quotes, none of
        them found, over a 400,000-character text. Each is a plain substring search; the whole reading stays well
        inside the assess stage's time."""
        text = ('Synthetic colon report line with ordinary words and numbers 0123456789. ' * 6000)[:400_000]
        locator = reading.Locator(text)
        started = time.monotonic()
        for index in range(3600):
            self.assertEqual(locator.locate(f'quote number {index:05d} absent from the text').reason, 'not found')
        self.assertLess(time.monotonic() - started, 30)


class ParticipantInvariantTests(OfflineTestCase):
    def test_a_refused_reading_carries_no_reading_at_all(self):
        refused = reading.refusal('astra', openai_astra.ADAPTER_VERSION, 'gpt-6-astra', 'gpt-6-astra-mini', 'reason')
        self.assertEqual((refused.refused, refused.services, refused.codes, refused.not_coded, refused.questions,
                          refused.extraction_issues, refused.date_of_service, refused.date_evidence,
                          refused.unverified_quotes),
                         (True, (), (), (), (), (), '', (), 0))
        self.assertEqual(refused.problems, ('The reading was not used: reason.',))
        self.assertEqual(refused.reading_version, prompt.READING_VERSION)

    def test_evidence_spans_are_built_only_from_located_text(self):
        result = AstraParticipant(self.tmp / 'x.env').read(
            AstraParticipant(self.tmp / 'x.env').build_request(NOTE, PAGES, 'paste', None),
            fixture_bytes('astra-colonoscopy.response.json'))
        spans = [span for item in result.date_evidence + result.services[0].evidence for span in item.spans]
        self.assertTrue(spans)
        self.assertTrue(all(isinstance(span, EvidenceSpan) and NOTE[span.start:span.end] == span.text
                            for span in spans))


class ReferencesUsedTests(OfflineTestCase):
    """HARNESS.md 11.2: references_used is the participant's claim; ``retrieved`` is CPT Studio's check of it against
    the refs that participant's own run's tool results returned, never the claim itself."""
    REFS = [{'ref': 'ncci-2026-ch6-c-1', 'use': 'Surgical endoscopy includes diagnostic endoscopy.'},
            {'ref': 'fact:cms-pfs-rvu26d:45385:mult_proc', 'use': 'The endoscopic base.'},
            {'ref': 'cms-claims-100-04-ch12-40.6.c', 'use': 'Cited, never retrieved.'}]

    def setUp(self):
        super().setUp()
        self.cases = []
        for adapter_class, build in ((AstraParticipant, astra_with), (FableParticipant, fable_with)):
            adapter = adapter_class(self.tmp / 'never-read.env')
            request = adapter.build_request(NOTE, PAGES, 'paste', None)
            answer = changed(fixture_reading(), references_used=self.REFS)
            self.cases.append((adapter, request, build(answer)))

    def test_a_reference_is_retrieved_only_when_the_runs_own_tool_results_returned_it(self):
        refs = {'ncci-2026-ch6-c-1', 'fact:cms-pfs-rvu26d:45385:mult_proc', 'fact:cms-pfs-rvu26d:45380:status'}
        for adapter, request, raw in self.cases:
            for given in (refs, frozenset(refs), sorted(refs), tuple(refs)):
                with self.subTest(adapter=adapter.name, given=type(given).__name__):
                    result = adapter.read(request, raw, given)
                    self.assertEqual([(item.ref, item.use, item.retrieved) for item in result.references_used],
                                     [(item['ref'], item['use'], retrieved)
                                      for item, retrieved in zip(self.REFS, (True, True, False))])

    def test_without_the_runs_refs_nothing_is_retrieved_and_the_two_argument_call_still_works(self):
        from studio.participants import registry

        for adapter, request, raw in self.cases:
            with self.subTest(adapter=adapter.name):
                reader = registry.reader(request.provider, request.adapter_version)
                for result in (adapter.read(request, raw), reader(request, raw), reader(request, raw, frozenset())):
                    self.assertEqual([item.retrieved for item in result.references_used], [False, False, False])
                self.assertEqual([item.retrieved for item in reader(request, raw, {'ncci-2026-ch6-c-1'}).references_used],
                                 [True, False, False])

    def test_refs_must_be_a_set_of_ref_strings(self):
        adapter, request, raw = self.cases[0]
        for given in ('ncci-2026-ch6-c-1', b'x', None, [1], {'a': 1}, 7):
            with self.subTest(given=given), self.assertRaises(TypeError):
                adapter.read(request, raw, given)

    def test_a_harness_1_run_is_read_as_before(self):
        for adapter, request, raw in self.cases:
            module = openai_astra if adapter.name == 'astra' else anthropic_fable
            older = ProviderRequest(provider=request.provider, adapter_version=module.ADAPTER_VERSION_1,
                                    body=request.body, canonical_sha256=request.canonical_sha256,
                                    contexts=request.contexts)
            with self.subTest(adapter=adapter.name):
                current, previous = adapter.read(request, raw), adapter.read(older, raw)
                self.assertEqual(previous.adapter_version, module.ADAPTER_VERSION_1)
                self.assertEqual(dataclasses.replace(previous, adapter_version=current.adapter_version), current)
                refused = adapter.read(older, b'[]')
                self.assertEqual((refused.adapter_version, refused.problems),
                                 (module.ADAPTER_VERSION_1, ('The reading was not used: the response is not a JSON '
                                                             'object.',)))

    def test_an_astra_answer_that_still_asks_for_tools_is_final_only_for_harness_1(self):
        adapter, request, _ = self.cases[0]
        envelope = astra_envelope()
        envelope['output'].append({'type': 'function_call', 'id': 'fc_synthetic', 'call_id': 'call_synthetic',
                                   'name': 'cms_code_facts', 'arguments': '{}', 'status': 'completed'})
        raw = json.dumps(envelope).encode()
        result = adapter.read(request, raw)
        self.assertEqual(result.problems, ('The reading was not used: the response still asks for tool calls, so it '
                                           'is not a final answer.',))
        older = ProviderRequest(provider='astra', adapter_version=openai_astra.ADAPTER_VERSION_1, body=request.body,
                                canonical_sha256=request.canonical_sha256, contexts=request.contexts)
        self.assertFalse(adapter.read(older, raw).refused)  # harness@1 sent no tools, and read such an answer so
