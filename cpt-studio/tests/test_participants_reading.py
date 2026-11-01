"""Participant readings (HARNESS.md 4; I6, I7): each vendor's answer shapes (good, refusal, truncated, wrong model,
fallback), the strict JSON and CPT Studio's own schema validation, the bounds, the item-level rules, and quote location
(every span an exact slice of the revision text; anything else unverified and never evidence). Offline and synthetic
(test_participants_support)."""
from __future__ import annotations

import hashlib
import json
import time

from studio.participants import anthropic_fable, openai_astra, prompt, reading
from studio.participants.anthropic_fable import FableParticipant
from studio.participants.openai_astra import AstraParticipant
from studio.types import EvidenceSpan, ExtractionIssue, ParticipantLesion, ProviderRequest

from tests.test_participants_support import (FIXTURE_SHA256, FIXTURES, NOTE, PAGE_BREAK, PAGES, OfflineTestCase,
                                             astra_envelope, astra_with, changed, code, empty_reading, fable_envelope,
                                             fixture_bytes, fixture_reading, service)


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

    def test_a_refusal_item_refuses_the_reading_with_its_text(self):
        envelope = astra_envelope()
        envelope['output'][1]['content'] = [{'type': 'refusal', 'refusal': "I can't help with\nthat request."}]
        self.assertEqual(self.refused(json.dumps(envelope).encode()),
                         "The reading was not used: the model refused: I can't help with that request.")
        envelope = astra_envelope()  # beside output text, a refusal still refuses everything
        envelope['output'][1]['content'].append({'type': 'refusal', 'refusal': ''})
        self.assertEqual(self.refused(json.dumps(envelope).encode()),
                         'The reading was not used: the model refused: no reason was given.')

    def test_an_incomplete_response_is_refused_as_truncated(self):
        self.assertEqual(self.refused(self.envelope(status='incomplete',
                                                    incomplete_details={'reason': 'max_output_tokens'})),
                         'The reading was not used: the response was cut off at the output limit.')
        self.assertEqual(self.refused(self.envelope(status='incomplete',
                                                    incomplete_details={'reason': 'content_filter'})),
                         'The reading was not used: the response is incomplete (content_filter).')
        self.assertEqual(self.refused(self.envelope(status='incomplete', incomplete_details=None)),
                         'The reading was not used: the response is incomplete.')
        envelope = astra_envelope()
        envelope['output'][1]['status'] = 'incomplete'
        self.assertEqual(self.refused(json.dumps(envelope).encode()),
                         'The reading was not used: the response was cut off at the output limit.')

    def test_any_status_but_completed_is_refused(self):
        for status in ('failed', 'in_progress', 'queued', 'cancelled', None, 7):
            with self.subTest(status=status):
                self.assertIn('not completed', self.refused(self.envelope(status=status)))

    def test_another_model_is_refused_and_never_read(self):
        """I6. A dated snapshot of gpt-6-astra is the same model; a model whose name merely starts with it is not."""
        for model in ('gpt-6-astra-mini', 'gpt-6-astra-pro-2026-10-01', 'gpt-6', 'gpt-6-astra-2026-10', 'GPT-6-ASTRA',
                      'gpt-6-astra ', 'gpt-5.5', ''):
            with self.subTest(model=model):
                problem = self.refused(self.envelope(model=model))
                self.assertIn('as the model that answered, not gpt-6-astra', problem)
        self.assertIn('names no model', self.refused(self.envelope(model=None)))
        self.assertIn('names no model', self.refused(self.envelope(model=['gpt-6-astra'])))
        self.assertIn("names model 'gpt-6-astra ' as the model", self.refused(self.envelope(model='gpt-6-astra ')))
        result = self.read(self.envelope(model='gpt-6-astra-2026-09-15'))
        self.assertEqual((result.refused, result.returned_model), (False, 'gpt-6-astra-2026-09-15'))
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
        self.assertEqual(result.problems, tuple(
            f'codes[{index}] ({value!r}) is not a five-character CPT code; it is kept as given.'
            for index, value in enumerate(values) if index > 1))

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
        for value in ('2026-02-30', '10/21/2026', '2026-10-21T09:00', '2026-1-21', 'yesterday'):
            with self.subTest(value=value):
                result = self.read(empty_reading(date_of_service={'value': value, 'evidence': []}))
                self.assertEqual((result.refused, result.date_of_service), (False, ''))
                self.assertEqual(result.problems, (f'date_of_service {value!r} is not a YYYY-MM-DD date; it was not '
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
