"""Participant requests (HARNESS.md 3, 8, 11.2; I5, I9): the exact bodies both adapters build from a revision alone -
since harness@2 with CPT Studio's two reference tools - the fields they must never carry, the original-file placeholder
and its size accounting, and what refuses a request before anything is built. Offline and synthetic
(test_participants_support)."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from unittest import mock

from studio.participants import Participant, prompt
from studio.participants import http as participants_http
from studio.participants.anthropic_fable import FableParticipant
from studio.participants.openai_astra import AstraParticipant
from studio.providers.base import ProviderUnavailable, canonical_body, request_sha256
from studio.types import PageSpan

from tests.test_participants_support import NOTE, ORIGINAL, PAGE_BREAK, PAGES, PDF, OfflineTestCase

FORBIDDEN_FABLE_FIELDS = ('thinking', 'temperature', 'top_p', 'top_k', 'fallbacks', 'betas', 'anthropic_beta',
                          'stop_sequences', 'metadata', 'mcp_servers', 'container')
ASTRA_TOOLS = [{'type': 'function', 'name': tool['name'], 'description': tool['description'],
                'parameters': tool['parameters'], 'strict': True} for tool in prompt.TOOLS]
FABLE_TOOLS = [{'name': tool['name'], 'description': tool['description'], 'input_schema': tool['parameters'],
                'strict': True} for tool in prompt.TOOLS]


def framed() -> str:
    return '\n'.join([
        'Document: a PDF; the original file is attached so that the extracted text can be checked against it.',
        'Its extracted text follows between the two marker lines. The [Page N] lines mark where each page begins and '
        'are not part of the text.',
        f'<<<{prompt.marker(NOTE)} BEGIN>>>', '[Page 1]', NOTE[:PAGE_BREAK], '[Page 2]', NOTE[PAGE_BREAK:],
        f'<<<{prompt.marker(NOTE)} END>>>'])


class AstraRequestTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.astra = AstraParticipant(self.tmp / 'never-read.env')

    def test_the_body_is_exactly_the_contract(self):
        request = self.astra.build_request(NOTE, PAGES, 'pdf', ORIGINAL)
        self.assertEqual(request.body, {
            'model': 'gpt-6-astra',
            'instructions': prompt.INSTRUCTIONS,
            'input': [{'role': 'user', 'content': [
                {'type': 'input_file', 'filename': 'original.pdf',
                 'file_data': {'$original_sha256': ORIGINAL['sha256'], '$original_bytes': ORIGINAL['bytes']}},
                {'type': 'input_text', 'text': framed()}]}],
            'text': {'format': {'type': 'json_schema', 'name': 'gi_encounter_reading', 'schema': prompt.SCHEMA,
                                'strict': True}},
            'reasoning': {'effort': 'medium'},
            'max_output_tokens': 16000,
            'store': False,
            'tools': ASTRA_TOOLS,
            'tool_choice': 'auto',
            'include': ['reasoning.encrypted_content'],
        })
        self.assertEqual([tool['name'] for tool in request.body['tools']], ['cms_code_facts', 'cms_policy_passages'])
        self.assertEqual((request.provider, request.adapter_version), ('astra', 'openai-responses@cptstudio-harness-2'))
        self.assertEqual(request.contexts, (NOTE,))  # quotes are located in the revision text itself

    def test_only_a_pdf_attaches_its_original(self):
        for kind in ('docx', 'paste', 'txt', 'addendum'):
            with self.subTest(kind=kind):
                request = self.astra.build_request(NOTE, PAGES, kind, ORIGINAL)
                content = request.body['input'][0]['content']
                self.assertEqual([part['type'] for part in content], ['input_text'])
                self.assertTrue(content[0]['text'].startswith(f'Document: {prompt.KINDS[kind]}.\n'))
                self.assertNotIn('$original_sha256', json.dumps(request.body))

    def test_identity_and_endpoint_are_code_constants(self):
        self.assertIsInstance(self.astra, Participant)
        self.assertEqual((self.astra.name, self.astra.mode, self.astra.requested_model, self.astra.endpoint),
                         ('astra', 'live', 'gpt-6-astra', 'https://api.openai.com/v1/responses'))


class FableRequestTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.fable = FableParticipant(self.tmp / 'never-read.env')

    def test_the_body_is_exactly_the_contract(self):
        request = self.fable.build_request(NOTE, PAGES, 'pdf', ORIGINAL)
        self.assertEqual(request.body, {
            'model': 'claude-fable-5-1',
            'max_tokens': 16000,
            'system': prompt.INSTRUCTIONS,
            'messages': [{'role': 'user', 'content': [
                {'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf',
                                                'data': {'$original_sha256': ORIGINAL['sha256'],
                                                         '$original_bytes': ORIGINAL['bytes']}}},
                {'type': 'text', 'text': framed()}]}],
            'output_config': {'format': {'type': 'json_schema', 'schema': prompt.SCHEMA}, 'effort': 'medium'},
            'tools': FABLE_TOOLS,
            'tool_choice': {'type': 'auto'},
        })
        self.assertEqual((request.provider, request.adapter_version),
                         ('fable', 'anthropic-messages@cptstudio-harness-2'))
        self.assertEqual(request.contexts, (NOTE,))

    def test_no_forbidden_field_is_ever_built(self):
        for kind, original in (('pdf', ORIGINAL), ('paste', None), ('docx', None)):
            request = self.fable.build_request(NOTE, PAGES, kind, original)
            encoded = canonical_body(request.body).decode()
            for field in FORBIDDEN_FABLE_FIELDS:
                with self.subTest(kind=kind, field=field):
                    self.assertNotIn(f'"{field}"', encoded)
            self.assertEqual(set(request.body), {'model', 'max_tokens', 'system', 'messages', 'output_config', 'tools',
                                                 'tool_choice'})
            self.assertEqual(set(request.body['output_config']), {'format', 'effort'})
            self.assertEqual(request.body['tool_choice'], {'type': 'auto'})  # a forced tool_choice is a 400 here

    def test_only_a_pdf_attaches_its_original(self):
        request = self.fable.build_request(NOTE, PAGES, 'addendum', ORIGINAL)
        self.assertEqual([part['type'] for part in request.body['messages'][0]['content']], ['text'])

    def test_identity_and_endpoint_are_code_constants(self):
        self.assertIsInstance(self.fable, Participant)
        self.assertEqual((self.fable.name, self.fable.mode, self.fable.requested_model, self.fable.endpoint),
                         ('fable', 'live', 'claude-fable-5-1', 'https://api.anthropic.com/v1/messages'))


class SharedRequestTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.adapters = (AstraParticipant(self.tmp / 'never-read.env'), FableParticipant(self.tmp / 'never-read.env'))

    def test_the_hash_is_of_the_stored_unexpanded_body(self):
        for adapter in self.adapters:
            with self.subTest(adapter=adapter.name):
                request = adapter.build_request(NOTE, PAGES, 'pdf', ORIGINAL)
                encoded = json.dumps(request.body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
                self.assertEqual(request.canonical_sha256, hashlib.sha256(encoded).hexdigest())
                self.assertEqual(request_sha256(request.body), request.canonical_sha256)
                self.assertNotIn(base64.b64encode(PDF), encoded)
                self.assertNotIn(PDF, encoded)

    def test_the_hash_is_stable_and_moves_with_every_input(self):
        for adapter in self.adapters:
            with self.subTest(adapter=adapter.name):
                base = adapter.build_request(NOTE, PAGES, 'pdf', ORIGINAL).canonical_sha256
                self.assertEqual(adapter.build_request(NOTE, PAGES, 'pdf', ORIGINAL).canonical_sha256, base)
                other_pdf = {'sha256': hashlib.sha256(PDF + b'x').hexdigest(), 'bytes': len(PDF) + 1}
                variants = {adapter.build_request(NOTE + ' ', (PageSpan(1, 0, PAGE_BREAK),
                                                               PageSpan(2, PAGE_BREAK, len(NOTE) + 1)),
                                                  'pdf', ORIGINAL).canonical_sha256,
                            adapter.build_request(NOTE, PAGES, 'pdf', other_pdf).canonical_sha256,
                            adapter.build_request(NOTE, PAGES, 'docx', None).canonical_sha256,
                            adapter.build_request(NOTE, (PageSpan(1, 0, len(NOTE)),), 'pdf', ORIGINAL).canonical_sha256}
                self.assertEqual(len(variants), 4)
                self.assertNotIn(base, variants)

    def test_the_request_carries_nothing_but_the_revision(self):
        """I5: no title, filename, date, setting, billing context or CPT Studio reading. Outside the fixed schema and
        the fixed tool definitions (prompt.TOOLS), every string in the body is the fixed prompt, the framed revision
        text, the original's sha256 or a fixed label."""
        labels = {'gpt-6-astra', 'claude-fable-5-1', 'user', 'input_file', 'original.pdf', 'input_text', 'json_schema',
                  'gi_encounter_reading', 'medium', 'document', 'base64', 'application/pdf', 'text', 'auto',
                  'reasoning.encrypted_content'}
        for adapter in self.adapters:
            with self.subTest(adapter=adapter.name):
                body = copy.deepcopy(adapter.build_request(NOTE, PAGES, 'pdf', ORIGINAL).body)
                holder = body['text']['format'] if adapter.name == 'astra' else body['output_config']['format']
                self.assertEqual(holder.pop('schema'), prompt.SCHEMA)
                self.assertEqual(body.pop('tools'), ASTRA_TOOLS if adapter.name == 'astra' else FABLE_TOOLS)
                strings, pending = [], [body]
                while pending:
                    node = pending.pop()
                    if isinstance(node, dict):
                        pending.extend(node.values())
                    elif isinstance(node, list):
                        pending.extend(node)
                    elif isinstance(node, str):
                        strings.append(node)
                self.assertEqual(set(strings) - labels, {prompt.INSTRUCTIONS, framed(), ORIGINAL['sha256']})

    def test_the_schema_and_tool_constants_are_copied_never_shared(self):
        for adapter in self.adapters:
            with self.subTest(adapter=adapter.name):
                request = adapter.build_request(NOTE, PAGES, 'paste', None)
                schema = (request.body['text']['format']['schema'] if adapter.name == 'astra'
                          else request.body['output_config']['format']['schema'])
                schema['properties']['injected'] = {'type': 'string'}
                self.assertNotIn('injected', prompt.SCHEMA['properties'])
                tool = request.body['tools'][0]
                parameters = tool['parameters'] if adapter.name == 'astra' else tool['input_schema']
                parameters['properties']['injected'] = {'type': 'string'}
                self.assertNotIn('injected', prompt.TOOLS[0]['parameters']['properties'])

    def test_unframeable_text_is_refused_before_anything_is_built(self):
        cases = {'pages that leave a gap': (PageSpan(1, 0, 10), PageSpan(2, 11, len(NOTE))),
                 'pages that overrun': (PageSpan(1, 0, len(NOTE) + 1),),
                 'pages that start late': (PageSpan(1, 1, len(NOTE)),),
                 'pages that overlap': (PageSpan(1, 0, 20), PageSpan(2, 10, len(NOTE)))}
        for adapter in self.adapters:
            for label, pages in cases.items():
                with self.subTest(adapter=adapter.name, case=label), self.assertRaises(ProviderUnavailable) as caught:
                    adapter.build_request(NOTE, pages, 'paste', None)
                self.assertIn('pages do not cover it exactly; nothing was sent', str(caught.exception))

    def test_a_text_containing_its_own_marker_is_refused(self):
        # The marker is the text's own sha256 prefix, so no real text contains it: the marker is pinned for the test.
        with mock.patch.object(prompt, 'marker', return_value='DOCUMENT-0000000000000000'):
            for adapter in self.adapters:
                with self.subTest(adapter=adapter.name), self.assertRaises(ProviderUnavailable) as caught:
                    adapter.build_request(NOTE + ' DOCUMENT-0000000000000000', (), 'paste', None)
                self.assertIn('it contains its own framing marker; nothing was sent', str(caught.exception))

    def test_unsendable_text_is_refused(self):
        for adapter in self.adapters:
            for text in ('', '  \n\t', 'Synthetic\x00note', 'Synthetic \ud800 note'):
                with self.subTest(adapter=adapter.name, text=repr(text)), self.assertRaises(ProviderUnavailable):
                    adapter.build_request(text, (), 'paste', None)

    def test_wrong_argument_types_are_programming_errors(self):
        for adapter in self.adapters:
            with self.subTest(adapter=adapter.name):
                with self.assertRaises(TypeError):
                    adapter.build_request(b'bytes', (), 'paste', None)
                with self.assertRaises(TypeError):
                    adapter.build_request(NOTE, ({'page': 1, 'start': 0, 'end': len(NOTE)},), 'paste', None)
                with self.assertRaises(ValueError):
                    adapter.build_request(NOTE, PAGES, 'pdf-scan', None)
                with self.assertRaises(TypeError):  # a PDF must name its original
                    adapter.build_request(NOTE, PAGES, 'pdf', None)
                for original in ({'sha256': ORIGINAL['sha256']}, {'sha256': ORIGINAL['sha256'].upper(), 'bytes': 1},
                                 {'sha256': 'x' * 64, 'bytes': 1}, {'sha256': ORIGINAL['sha256'], 'bytes': 0},
                                 {'sha256': ORIGINAL['sha256'], 'bytes': True},
                                 {'sha256': ORIGINAL['sha256'], 'bytes': 1.0},
                                 {'sha256': ORIGINAL['sha256'], 'bytes': 1, 'name': 'report.pdf'}):
                    with self.subTest(original=original), self.assertRaises((TypeError, ValueError)):
                        adapter.build_request(NOTE, PAGES, 'pdf', original)

    def test_the_size_limit_counts_the_original_once_expanded(self):
        for adapter_class, prefix in ((AstraParticipant, 'data:application/pdf;base64,'), (FableParticipant, '')):
            probe = adapter_class(self.tmp / 'never-read.env')
            stored = len(canonical_body(probe.build_request(NOTE, PAGES, 'pdf', ORIGINAL).body))
            holder = {'$original_sha256': ORIGINAL['sha256'], '$original_bytes': ORIGINAL['bytes']}
            expanded = stored - len(canonical_body(holder)) + len(json.dumps(prefix + base64.b64encode(PDF).decode()))
            self.assertEqual(participants_http.expanded_length(stored, holder, prefix), expanded)
            with self.subTest(adapter=probe.name):
                at_limit = adapter_class(self.tmp / 'x.env', max_request_bytes=expanded)
                at_limit.build_request(NOTE, PAGES, 'pdf', ORIGINAL)
                over = adapter_class(self.tmp / 'x.env', max_request_bytes=expanded - 1)
                with self.assertRaises(ProviderUnavailable) as caught:
                    over.build_request(NOTE, PAGES, 'pdf', ORIGINAL)
                self.assertIn(f'with its original file would be {expanded:,} bytes, over the {expanded - 1:,}-byte '
                              'limit; nothing was truncated or sent', str(caught.exception))
                # The same text without an original fits in far less.
                over.build_request(NOTE, PAGES, 'docx', None)

    def test_constructors_refuse_nonsense_limits(self):
        for adapter_class in (AstraParticipant, FableParticipant):
            for options in ({'connect_timeout': 0}, {'read_timeout': float('nan')}, {'max_request_bytes': 0},
                            {'max_response_bytes': True}, {'max_request_bytes': 1.5}):
                with self.subTest(adapter=adapter_class.__name__, options=options), self.assertRaises(ValueError):
                    adapter_class(self.tmp / 'x.env', **options)
