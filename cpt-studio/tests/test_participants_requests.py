"""Participant requests (HARNESS.md 3, 8, 11.2, 12.8; I5, I9): the exact bodies both adapters build from a revision
alone - since harness@2 with CPT Studio's two reference tools; Fable's since harness-3 with no output format and the
schema in its system prompt - the fields they must never carry, the original-file placeholder and its size accounting,
what refuses a request before anything is built, and Astra's requests byte for byte as they were before Fable's change.
Offline and synthetic (test_participants_support)."""
from __future__ import annotations

import base64
import copy
import dataclasses
import hashlib
import json
from unittest import mock

from studio.management.commands import participant_access_check
from studio.participants import Participant, anthropic_fable, openai_astra, prompt
from studio.participants import http as participants_http
from studio.participants.anthropic_fable import FableParticipant
from studio.participants.openai_astra import AstraParticipant
from studio.providers.base import ProviderUnavailable, canonical_body, request_sha256
from studio.types import PageSpan, sha256_json

from tests.test_participants_peer import CORTI, CORTI_SHA256, CPT_STUDIO
from tests.test_participants_support import (FACTS_ARGUMENTS, NOTE, ORIGINAL, PAGE_BREAK, PAGES, PASSAGES_ARGUMENTS,
                                             PDF, FakeExecutor, OfflineTestCase, astra_tool_call, canonical,
                                             fable_harness_2, fixture_bytes, fixture_reading)

FORBIDDEN_FABLE_FIELDS = ('thinking', 'temperature', 'top_p', 'top_k', 'fallbacks', 'betas', 'anthropic_beta',
                          'stop_sequences', 'metadata', 'mcp_servers', 'container')
ASTRA_TOOLS = [{'type': 'function', 'name': tool['name'], 'description': tool['description'],
                'parameters': tool['parameters'], 'strict': True} for tool in prompt.TOOLS]
FABLE_TOOLS = [{'name': tool['name'], 'description': tool['description'], 'input_schema': tool['parameters'],
                'strict': True} for tool in prompt.TOOLS]
FABLE_SYSTEM_3 = prompt.INSTRUCTIONS + prompt.schema_instruction(prompt.SCHEMA)
FABLE_PEER_SYSTEM_3 = prompt.PEER_INSTRUCTIONS + prompt.schema_instruction(prompt.PEER_SCHEMA)
FABLE_SYSTEM = FABLE_SYSTEM_3 + prompt.fields_instruction()  # harness-4 (HARNESS.md, "Harness repair 3", F-CONTRACT)
FABLE_PEER_SYSTEM = FABLE_PEER_SYSTEM_3 + prompt.fields_instruction()
# Fable's harness-3 system prompts, pinned: a change to either is a change to the request, so it comes with a new
# adapter version (HARNESS.md 12.8). harness-3's stay pinned, so its stored runs' bodies are rebuilt exactly.
FABLE_SYSTEM_SHA256 = {'first': 'b07c140b936d2183cfe71f2be024b89ac2670fb75269658a7a79aa16032e2174',
                       'peer': '2518d218c437e4991a58fe53375a006a50f89550a4dde1c081e5dc2bbfc623ba'}
# Astra's requests on the test fixtures as the harness@2 head built them (9d773838c, before Fable's harness-3 change),
# by astra_request_sha256s below: Astra does not change (HARNESS.md 12.8), so not one of these may move.
ASTRA_REQUEST_SHA256 = {
    'first:access-check': '1b4425d36b43ebc32f206592b97249ad108704d61c26c64eea0f1e00346e8f25',
    'first:addendum': '6126aa75e485d0c91a9f7bae4957985fefaa3f9c8fe707d8a5b4e9f840b7b1af',
    'first:docx': '9e90eea34b0de600c7f67929f9db13d993e58b48bf8e4a5870239e60f35162de',
    'first:paste': '6dd3fd761a59431b04c2a3faefcc976ec1a2be555a2cf9706b578cb967ad2292',
    'first:paste-without-pages': 'e464eea7dfb9b91152007807a7d57fa9a43a20ebef5bcd1fd596572e004cddce',
    'first:pdf': '33c9ffa78cc347ed44a334e5f32f949448a2205f67c21b2c31eba7e24d2f2dcc',
    'first:txt': 'bb1124e2befa62d1d73467c907f1a6c0959b3055ee72ff8e306804c516b30200',
    'loop:exchange-2': '65cefb65b81e3711f47574c00ec2de3ed8766adf6881a6d8bc4d4d7f24a8d5c7',
    'loop:exchange-3': '521be8c618efe5a7a223a9849a956e982f6c19d2198387931849d66654be2aec',
    'peer:alone': '7b5ad0eb4c89821445212d0abbc306b6e2bc3e0c1cf689b999de6c17a4ddce60',
    'peer:loop-exchange-2': 'aff0c5f03d203989466a68e65fa2c0722e7e567dcbc6926c07a94b23c87f8b7a',
    'peer:with-peers': 'a9e1207fdddb57a10a4cbff74db08e43ca28de8def48733783bd4472a3772581',
    'reading:astra-fixture': 'af4060d536d5fa08e4748d173675abab9ee14d8a7a4ca5844fb5df7fec2d3b92',
}
# The harness@2 Fable adapter's own bodies (9d773838c) for the same fixtures: fable_harness_2 must rebuild them exactly,
# so the stored-run tests read what that adapter stored.
FABLE_HARNESS_2_SHA256 = {
    'first:addendum': '41262a43f9e03a04d5834ca1e36a0fe13e0bc4bd9ba10f4ae1614bba04963fc9',
    'first:docx': '3be047efdec8e6a1ae05fb4e0d9b467899a3aafa2cd897a2312658759d086465',
    'first:paste': 'c231de3ea5177bec2626d2c6cc708c484107f3646c76f7685635a563dcb75328',
    'first:pdf': '866d2445650b0c4495920bdc9650aeab6cfb9ca7f8f132610d418403c5ca8066',
    'first:txt': '886c1db5d1bc0f92e851547d316fcbe4c0c1d321faac201bacb1216b74e6be37',
    'peer:with-peers': 'c5c4278b192df32a27238f5362ceb01a5b9ed03112515f89549f8d023789e92f',
}


def keys_anywhere(value) -> set:
    """Every object key at any depth of a JSON value."""
    found, pending = set(), [value]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            found.update(node)
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return found


def _follow_astra(body: dict, number: int, calls) -> dict:
    turn = openai_astra.parse_turn(astra_tool_call(*calls, number=number))
    executor = FakeExecutor()
    return openai_astra.follow_up(body, turn, tuple((call.call_id, canonical(executor(call.name, call.arguments)[0]))
                                                    for call in turn.calls))


def astra_request_sha256s() -> dict:
    """Astra's request sha256s on the test fixtures: its first reading for every kind of document (and the access
    check's), the later exchanges of a three-exchange loop, its peer review with and without peer conclusions and a
    peer-review loop's second exchange - and its fixture reading's own sha256 - every input fixed, none of them made by
    Fable's adapter."""
    adapter = AstraParticipant('/nonexistent/never-read.env')
    out = {}
    for kind in ('pdf', 'docx', 'paste', 'txt', 'addendum'):
        out[f'first:{kind}'] = adapter.build_request(NOTE, PAGES, kind, ORIGINAL if kind == 'pdf' else None
                                                     ).canonical_sha256
    out['first:paste-without-pages'] = adapter.build_request(NOTE, (), 'paste', None).canonical_sha256
    out['first:access-check'] = adapter.build_request(participant_access_check.NOTE, (), 'paste', None
                                                      ).canonical_sha256
    body = _follow_astra(adapter.build_request(NOTE, PAGES, 'pdf', ORIGINAL).body, 1,
                         [('call_pin_1', 'cms_code_facts', FACTS_ARGUMENTS)])
    out['loop:exchange-2'] = request_sha256(body)
    body = _follow_astra(body, 2, [('call_pin_2', 'cms_policy_passages', PASSAGES_ARGUMENTS),
                                   ('call_pin_3', 'cms_code_facts', {'codes': ['45380'], 'date_of_service': ''})])
    out['loop:exchange-3'] = request_sha256(body)
    own = adapter.read(adapter.build_request(NOTE, PAGES, 'pdf', ORIGINAL),
                       fixture_bytes('astra-colonoscopy.response.json'))
    out['reading:astra-fixture'] = sha256_json(own)
    revision = hashlib.sha256(NOTE.encode()).hexdigest()
    frozen = [('astra', sha256_json(own)), ('revision', revision), ('corti', CORTI_SHA256),
              ('fable', hashlib.sha256(b'synthetic frozen fable reading').hexdigest()),
              ('cpt_studio', sha256_json(CPT_STUDIO))]
    peer = adapter.build_peer_request(NOTE, PAGES, 'pdf', own, {'corti': CORTI, 'fable': fixture_reading()},
                                      CPT_STUDIO, frozen)
    out['peer:with-peers'] = peer.canonical_sha256
    out['peer:loop-exchange-2'] = request_sha256(_follow_astra(peer.body, 1, [('call_pin_4', 'cms_code_facts',
                                                                                FACTS_ARGUMENTS)]))
    out['peer:alone'] = adapter.build_peer_request(
        NOTE, PAGES, 'paste', own, {}, CPT_STUDIO,
        [('astra', sha256_json(own)), ('revision', revision), ('cpt_studio', sha256_json(CPT_STUDIO))]
    ).canonical_sha256
    return out


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
            'system': prompt.INSTRUCTIONS + prompt.schema_instruction(prompt.SCHEMA) + prompt.fields_instruction(),
            'messages': [{'role': 'user', 'content': [
                {'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf',
                                                'data': {'$original_sha256': ORIGINAL['sha256'],
                                                         '$original_bytes': ORIGINAL['bytes']}}},
                {'type': 'text', 'text': framed()}]}],
            'output_config': {'effort': 'medium'},  # no format: Anthropic's grammar limit (HARNESS.md 12.8)
            'tools': FABLE_TOOLS,
            'tool_choice': {'type': 'auto'},
        })
        self.assertEqual((request.provider, request.adapter_version),
                         ('fable', 'anthropic-messages@cptstudio-harness-4'))
        self.assertEqual(request.contexts, (NOTE,))

    def test_no_forbidden_field_is_ever_built_and_no_output_format(self):
        for kind, original in (('pdf', ORIGINAL), ('paste', None), ('docx', None)):
            request = self.fable.build_request(NOTE, PAGES, kind, original)
            encoded = canonical_body(request.body).decode()
            for field in FORBIDDEN_FABLE_FIELDS:
                with self.subTest(kind=kind, field=field):
                    self.assertNotIn(f'"{field}"', encoded)
            self.assertEqual(set(request.body), {'model', 'max_tokens', 'system', 'messages', 'output_config', 'tools',
                                                 'tool_choice'})
            self.assertEqual(request.body['output_config'], {'effort': 'medium'})
            # no format and no json_schema anywhere in the body: the schema travels only as text (HARNESS.md 12.8)
            self.assertFalse({'format', 'json_schema', 'schema'} & keys_anywhere(request.body))
            self.assertNotIn('"json_schema"', encoded)
            self.assertEqual(request.body['tool_choice'], {'type': 'auto'})  # a forced tool_choice is a 400 here
            self.assertEqual([tool['strict'] for tool in request.body['tools']], [True, True])  # the tools stay strict

    def test_the_system_prompt_is_the_instructions_unchanged_then_the_schema_and_one_instruction(self):
        """HARNESS.md 12.8: nothing at Anthropic constrains the answer, so the system prompt gives its shape - the
        reading schema, serialized deterministically - with one instruction; the instructions before it are Astra's
        exactly. harness-4 (F-CONTRACT) adds one line after the schema; harness-3's prompt is unchanged."""
        system = self.fable.build_request(NOTE, PAGES, 'paste', None).body['system']
        self.assertTrue(system.startswith(prompt.INSTRUCTIONS))
        blank, instruction, encoded, fields, end = system[len(prompt.INSTRUCTIONS):].split('\n')
        self.assertEqual((blank, instruction, fields, end), (
            '', 'Answer with exactly one JSON object that matches this JSON Schema, and nothing else:',
            'Give every object exactly the fields this schema lists for it. Add no other field, not even an empty one '
            'or a note: an explanation belongs only in a field the schema has for it.', ''))
        self.assertEqual(json.loads(encoded), prompt.SCHEMA)
        self.assertEqual(encoded, json.dumps(prompt.SCHEMA, sort_keys=True, separators=(',', ':')))
        self.assertEqual(system, FABLE_SYSTEM)
        self.assertEqual(hashlib.sha256(FABLE_SYSTEM_3.encode()).hexdigest(), FABLE_SYSTEM_SHA256['first'])
        self.assertEqual(hashlib.sha256(FABLE_PEER_SYSTEM_3.encode()).hexdigest(), FABLE_SYSTEM_SHA256['peer'])
        self.assertEqual(anthropic_fable.system_prompt(prompt.PEER_INSTRUCTIONS, prompt.PEER_SCHEMA), FABLE_PEER_SYSTEM)
        self.assertEqual(anthropic_fable.system_prompt(prompt.INSTRUCTIONS, prompt.SCHEMA,
                                                       anthropic_fable.ADAPTER_VERSION_3), FABLE_SYSTEM_3)
        with self.assertRaises(ValueError):
            anthropic_fable.system_prompt(prompt.INSTRUCTIONS, prompt.SCHEMA, anthropic_fable.ADAPTER_VERSION_2)

    def test_the_schema_text_is_deterministic_and_the_function_pure(self):
        def reordered(value):
            if isinstance(value, dict):
                return {key: reordered(value[key]) for key in reversed(list(value))}
            return [reordered(item) for item in value] if isinstance(value, list) else value
        schema = reordered(json.loads(json.dumps(prompt.SCHEMA)))
        self.assertNotEqual(list(schema), list(prompt.SCHEMA))  # built in another order
        self.assertEqual(prompt.schema_instruction(schema), prompt.schema_instruction(prompt.SCHEMA))
        before = json.dumps(prompt.SCHEMA)
        self.assertEqual(prompt.schema_instruction(prompt.SCHEMA), prompt.schema_instruction(prompt.SCHEMA))
        self.assertEqual(json.dumps(prompt.SCHEMA), before)  # the constant is read, never changed
        self.assertEqual(self.fable.build_request(NOTE, PAGES, 'paste', None).canonical_sha256,
                         self.fable.build_request(NOTE, PAGES, 'paste', None).canonical_sha256)
        for bad, error in (([], TypeError), ('{}', TypeError), ({'type': float('nan')}, ValueError),
                           ({'type': object()}, TypeError)):
            with self.subTest(bad=repr(bad)[:20]), self.assertRaises(error):
                prompt.schema_instruction(bad)

    def test_an_earlier_versions_body_is_rebuilt_exactly_for_the_stored_run_tests(self):
        """fable_harness_2 (test support) rebuilds the harness@2 adapter's own bodies, byte for byte (9d773838c)."""
        for kind in ('pdf', 'docx', 'paste', 'txt', 'addendum'):
            with self.subTest(kind=kind):
                body = self.fable.build_request(NOTE, PAGES, kind, ORIGINAL if kind == 'pdf' else None).body
                self.assertEqual(request_sha256(fable_harness_2(body)), FABLE_HARNESS_2_SHA256[f'first:{kind}'])
        own = self.fable.read(self.fable.build_request(NOTE, PAGES, 'pdf', ORIGINAL),
                              fixture_bytes('fable-colonoscopy.response.json'))
        own = dataclasses.replace(own, adapter_version=anthropic_fable.ADAPTER_VERSION_2)  # as harness@2 read it
        frozen = [('fable', sha256_json(own)), ('revision', hashlib.sha256(NOTE.encode()).hexdigest()),
                  ('corti', CORTI_SHA256), ('astra', hashlib.sha256(b'synthetic frozen astra reading').hexdigest()),
                  ('cpt_studio', sha256_json(CPT_STUDIO))]
        peer = self.fable.build_peer_request(NOTE, PAGES, 'pdf', own, {'corti': CORTI, 'astra': fixture_reading()},
                                             CPT_STUDIO, frozen)
        self.assertEqual(request_sha256(fable_harness_2(peer.body)), FABLE_HARNESS_2_SHA256['peer:with-peers'])

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
                if adapter.name == 'astra':
                    self.assertEqual(body['text']['format'].pop('schema'), prompt.SCHEMA)
                    instructions = prompt.INSTRUCTIONS
                else:  # no format to hold a schema: Fable's is fixed text in its system prompt (HARNESS.md 12.8)
                    self.assertEqual(body['output_config'], {'effort': 'medium'})
                    instructions = FABLE_SYSTEM  # harness-4: the fields line too (F-CONTRACT)
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
                self.assertEqual(set(strings) - labels, {instructions, framed(), ORIGINAL['sha256']})

    def test_the_schema_and_tool_constants_are_copied_never_shared(self):
        for adapter in self.adapters:
            with self.subTest(adapter=adapter.name):
                request = adapter.build_request(NOTE, PAGES, 'paste', None)
                if adapter.name == 'astra':
                    schema = request.body['text']['format']['schema']
                    schema['properties']['injected'] = {'type': 'string'}
                else:  # Fable's schema is text (HARNESS.md 12.8): there is no object to share
                    self.assertIsInstance(request.body['system'], str)
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


class AstraUnchangedTests(OfflineTestCase):
    """HARNESS.md 12.8: Fable's request changed and Astra's did not - each Astra request on the test fixtures (and its
    fixture reading) is byte for byte what the harness@2 head built (9d773838c)."""

    def test_astras_requests_are_byte_identical_to_the_harness_2_heads(self):
        self.assertEqual(astra_request_sha256s(), ASTRA_REQUEST_SHA256)
        self.assertEqual(openai_astra.ADAPTER_VERSION, 'openai-responses@cptstudio-harness-2')

    def test_astra_keeps_its_strict_structured_output_and_never_carries_the_schema_text(self):
        adapter = AstraParticipant(self.tmp / 'never-read.env')
        for kind in ('pdf', 'paste'):
            with self.subTest(kind=kind):
                body = adapter.build_request(NOTE, PAGES, kind, ORIGINAL if kind == 'pdf' else None).body
                self.assertEqual(body['instructions'], prompt.INSTRUCTIONS)
                self.assertEqual(body['text']['format']['strict'], True)
                self.assertNotIn(prompt.SCHEMA_INSTRUCTION, canonical_body(body).decode())
