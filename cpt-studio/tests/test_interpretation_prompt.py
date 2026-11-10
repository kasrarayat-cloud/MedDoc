"""The interpretation contract, part I (Gemini migration slice S01; design/contract.md 1-2, design/FINAL.md 5.1-5.3, as
design/ADJUDICATION.md EB4, C-7, C-8 and C-15 amend them), TEXT-ONLY: the labels; the sha256 pins of INSTRUCTIONS,
LOCAL_SCHEMA and RESPONSE_SCHEMA beside INTERPRETATION_VERSION, and their check whenever a request is built; the
instructions' lineage (FINAL 5.3 plus the three adjudicated edits, and the contract's 2.1 under FINAL's four); the
enumerations and the generated schema with its measured size; the framing per kind and the PDF first-line guard; a
request body of exactly three keys that carries no member value, filename, title or reading; and an AST scan, plus a
fresh-interpreter import, showing that no module of the slice imports studio.gi. Offline: nothing is sent."""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation import prompt, schema
from studio.models import Assessment, EncounterContext, Job, ProviderRun, RoutingRun
from studio.participants import http
from studio.participants import prompt as participant_prompt
from studio.participants import reading
from studio.providers.base import ProviderUnavailable, canonical_body, request_sha256
from studio.types import PageSpan

APP = Path(__file__).resolve().parent.parent
PACKAGE = APP / 'studio' / 'interpretation'
SLICE_MODULES = ('__init__', 'prompt', 'schema', 'read', 'store')

# The pins, keyed by the version they belong to: a changed byte without a new version fails here, and a new version
# without its own pins fails too (KeyError). BOUNDS is pinned as well: it is part of what gemini-events@1 reads (never
# sent: DECISIONS D32 raised attribute_passages 8 -> 32 and question_ids 16 -> 64 before any product recording, and every
# FRESH request's sha256 still matches its record).
PINS = {
    'gemini-events@1': {
        'INSTRUCTIONS': '00da58c5a8f0f5deca4ee0dd8259bb7065ee6dd551e408e3257bd33b4eee14b1',
        'LOCAL_SCHEMA': '93574cacb4dc3d9fb0c3ed7789a8c2f7c708bf94176b53f1dd850fcd0214ccc3',
        'RESPONSE_SCHEMA': '7bb3057d724012910b4210272c31480eacb6fc6fe6dbacbce4415c61592d2537',
        'BOUNDS': '1465ca8d83ec9337e7c13245571fc01112c820cf2f2f98438e9a52039654dc4b',
    },
}
# The generated schema, measured (canonical bytes: keys sorted, no spaces). The contract's own enumerations, run through
# the same generator, give the contract's own measurement (contract 3.2: 10,993 local, 10,239 Gemini form, propertyOrdering
# 1,557 more), so the generator is the contract's.
SIZES = {'local': 11_241, 'gemini': 12_044, 'gemini_without_property_ordering': 10_487, 'depth': 6, 'enum_sites': 20}
CONTRACT_SIZES = {'local': 10_993, 'gemini': 11_796, 'gemini_without_property_ordering': 10_239}
CONTRACT_SCOPES = ['not_applicable', 'single_target', 'all_of_kind', 'listed_targets', 'unknown']
COLON_REGIONS = ('right_colon', 'left_colon', 'proximal_colon', 'distal_colon')

# The instructions' lineage. FINAL 5.3's text block and the contract's 2.1 block, each with its line ends and a final
# one, have these sha256 (design files of 2026-11-09: FINAL.md c3d7bd86..., contract.md 8288dea7...).
FINAL_5_3_SHA256 = '0a0abadef5a2849743f4db1e3ae68dc2398e1dae72c8ef1584366d4666a5f1d0'
CONTRACT_2_1_SHA256 = '478cbdeeafb8c5460ec99787e3f40f0ed3dd28d6f478908e9afa3321ed5d96b4'
# (the text before, the text after) of each adjudicated edit, in the order they apply to FINAL 5.3's text: EB4's time
# words; C-7's exceptive scope; and C-8's all_of_kind, which covers the acts of its kind in the statement's own
# examination or session, never the whole encounter (on the scope line as C-7 left it, so it is undone first).
ADJUDICATED_EDITS = (
    ('''- time: current_encounter for acts of this encounter; earlier_encounter; future; unknown. words: the words that place the
  act in time, or "" when the act is told as part of this encounter without time words of its own. A purpose is not a
  time: an act done in this encounter for a later purpose is current_encounter. A statement that extends another statement
  to another time takes the time it establishes. For another time stated without a date, the words include the word that
  places it there, such as "previously" or "next".
''', '''- time: current_encounter for acts of this encounter; earlier_encounter; future; unknown. words: the words that place the
  act in time. Give them whenever the document gives any sign of when the act was done, whatever time you give: a date
  stated for it; a word such as "prior", "previous", "previously", "at that time" or "next"; or the heading or line that
  introduces the part of the document the act is told in, such as "History:", with that line among the time's passages.
  Give "" only when the act is told as part of this encounter with no such sign of its own. A purpose is not a time: an
  act done in this encounter for a later purpose is current_encounter. A statement that extends another statement to
  another time takes the time it establishes. For another time stated without a date, the words include the word that
  places it there, such as "previously" or "next".
'''),
    ('''- scope, for not_performed and uncertain only (not_applicable otherwise): single_target (the statement is about one lesion
  or site, given as target); all_of_kind (the statement covers every act of this kind in its encounter and names no
  particular target); listed_targets (give the lesion ids in targets); unknown. words: the words that set the scope.
''', '''- scope, for not_performed and uncertain only (not_applicable otherwise): single_target (the statement is about one lesion
  or site, given as target); all_of_kind (the statement covers every act of this kind in its encounter and names no
  particular target); listed_targets (give the lesion ids in targets); exceptive (the statement covers only acts of this
  kind beyond those the document reports as done, such as "no further", "no other" or "no additional"); unknown. words:
  the words that set the scope, including for exceptive the word that makes the exception, such as "further", "other" or
  "additional".
'''),
    ('''- scope, for not_performed and uncertain only (not_applicable otherwise): single_target (the statement is about one lesion
  or site, given as target); all_of_kind (the statement covers every act of this kind in its encounter and names no
  particular target); listed_targets (give the lesion ids in targets); exceptive (the statement covers only acts of this
  kind beyond those the document reports as done, such as "no further", "no other" or "no additional"); unknown. words:
  the words that set the scope, including for exceptive the word that makes the exception, such as "further", "other" or
  "additional".
''', '''- scope, for not_performed and uncertain only (not_applicable otherwise): single_target (the statement is about one lesion
  or site, given as target); all_of_kind (the statement covers every act of this kind in its own examination or session
  and names no particular target); listed_targets (give the lesion ids in targets); exceptive (the statement covers only
  acts of this kind beyond those the document reports as done, such as "no further", "no other" or "no additional");
  unknown. words: the words that set the scope, including for exceptive the word that makes the exception, such as
  "further", "other" or "additional".
'''),
    # S16, after the FRESH recording (DECISIONS D33): a sentence that frames a part of the document - before or after
    # it - places every act told in that part in time and says who did them (EB4: asking for the words, never a word
    # list). Applied after C-8, so undone first.
    ('''  introduces the part of the document the act is told in, such as "History:", with that line among the time's passages.
  Give "" only when the act is told as part of this encounter with no such sign of its own. A purpose is not a time: an
''', '''  introduces the part of the document the act is told in, such as "History:", with that line among the time's passages.
  A sentence that says which occasion a part of the document belongs to - before that part, such as "The reports below
  are copied from her earlier hospital stay.", or after it, such as "That was the examination of last spring." - places
  every act told in that part: give each of those acts the time it states, with that sentence as the act's time words
  and its passage among the time's passages.
  Give "" only when the act is told as part of this encounter with no such sign of its own. A purpose is not a time: an
'''),
    ('''  the name or description as written, or "" when the document names none. For another facility, the words include the
  word that names the place, such as "outside hospital".
''', '''  the name or description as written, or "" when the document names none. For another facility, the words include the
  word that names the place, such as "outside hospital". A sentence that says who did the acts told in a part of the
  document, before or after that part, such as "All of the above was done by her previous surgeon.", gives each act told
  in that part that performer, with that sentence as the act's performer words.
'''),
)
# (the contract's 2.1 text, FINAL 5.3's): C1's three sentences and C3's part_of line (FINAL 5.3, "Changed against").
FINAL_EDITS = (
    ('  to another time takes the time it establishes.\n',
     '  to another time takes the time it establishes. For another time stated without a date, the words include the word '
     'that\n  places it there, such as "previously" or "next".\n'),
    ('  the name or description as written, or "" when the document names none.\n',
     '  the name or description as written, or "" when the document names none. For another facility, the words include '
     'the\n  word that names the place, such as "outside hospital".\n'),
    ('  uncertain (the document leaves it in doubt). words: the words that state it.\n',
     '  uncertain (the document leaves it in doubt). words: the words that state it, including the word that says the act '
     'was\n  not done, is planned, or was not completed.\n'),
    ('- part_of: the id of another event when the document makes this act a step of that act on the same target; '
     'otherwise "".\n',
     '- part_of: the id of another event when the document makes this act a step of that act on the same target, or when '
     'this\n  examination is the endoscopic portion of that examination (for example an upper endoscopy done as part of an '
     'endoscopic\n  ultrasound); otherwise "".\n'),
)

# A short synthetic document on two pages (no real patient; written for this test).
NOTE = ('Synthetic procedure note. Date of service: 03/14/2026.\n'
        'A 7 mm sessile polyp in the transverse colon was removed with a cold snare.\n'
        'Page two of the synthetic note.\nNo other polyp was removed.\n')
BREAK = NOTE.index('Page two')
PAGES = (PageSpan(page=1, start=0, end=BREAK), PageSpan(page=2, start=BREAK, end=len(NOTE)))
# The request sha256 of NOTE framed as a PDF: the replay key a recording of it would carry. It moves with any byte of
# the instructions, the schema, the framing or the body's shape.
NOTE_PDF_REQUEST_SHA256 = '556582e7bf355b27755ec471e83df6989d3a5c03fc10dd4f5adb015f92195c0e'


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def replaced(text: str, old: str, new: str) -> str:
    """``text`` with its one occurrence of ``old`` replaced: AssertionError unless there is exactly one."""
    count = text.count(old)
    assert count == 1, f'expected 1 occurrence, measured {count}'
    return text.replace(old, new)


def nodes(node: dict, path: str = ''):
    """Every schema node of ``node`` with its path, depth first."""
    yield path, node
    for key, child in node.get('properties', {}).items():
        yield from nodes(child, f'{path}.{key}')
    if 'items' in node:
        yield from nodes(node['items'], f'{path}[]')


def depth(node: dict) -> int:
    kind = node['type'].lower()
    if kind == 'object':
        return 1 + max(depth(child) for child in node['properties'].values())
    if kind == 'array':
        return 1 + depth(node['items'])
    return 0


def without_property_ordering(node: dict) -> dict:
    node = {key: value for key, value in node.items() if key != 'propertyOrdering'}
    if 'properties' in node:
        node['properties'] = {key: without_property_ordering(child) for key, child in node['properties'].items()}
    if 'items' in node:
        node['items'] = without_property_ordering(node['items'])
    return node


def with_enums(node: dict, swaps: dict) -> dict:
    """A copy of a local schema with each enumeration that equals a key of ``swaps`` replaced by its value."""
    node = copy.deepcopy(node)
    for _, child in nodes(node):
        if 'enum' in child and tuple(child['enum']) in swaps:
            child['enum'] = list(swaps[tuple(child['enum'])])
    return node


def line_of(text: str, start: str) -> str:
    """The instruction item that starts with ``start`` (its continuation lines included)."""
    at = text.index(start)
    end = text.find('\n- ', at + 1)
    return text[at:end if end != -1 else len(text)]


class LabelTests(SimpleTestCase):
    def test_the_labels_are_the_designs(self):
        self.assertEqual(
            {name: getattr(interpretation, name) for name in (
                'INTERPRETATION_VERSION', 'INVENTORY_VERSION', 'LABEL', 'ADAPTER_VERSION', 'MODEL', 'PROVIDER',
                'PURPOSE', 'JOB_KIND', 'ENGINE_VERSION', 'CONTEXT_VERSION', 'ROUTING_VERSION')},
            {'INTERPRETATION_VERSION': 'gemini-events@1', 'INVENTORY_VERSION': 'gemini-inventory@1',
             'LABEL': 'gemini-events@1+inventory@1', 'ADAPTER_VERSION': 'gemini-generate@cptstudio-1',
             'MODEL': 'gemini-4-argon', 'PROVIDER': 'gemini', 'PURPOSE': 'interpretation', 'JOB_KIND': 'interpret',
             'ENGINE_VERSION': 'cpt-studio-events@1', 'CONTEXT_VERSION': 'gemini-context@1',
             'ROUTING_VERSION': 'gemini-routing@1'})
        self.assertEqual((len(interpretation.LABEL), len(interpretation.ADAPTER_VERSION)), (27, 27))

    def test_each_label_fits_its_column(self):
        columns = (
            (interpretation.ADAPTER_VERSION, ProviderRun, 'adapter_version'),
            (interpretation.PROVIDER, ProviderRun, 'provider'),
            (interpretation.PURPOSE, ProviderRun, 'purpose'),
            (interpretation.MODEL, ProviderRun, 'requested_model'),
            (interpretation.MODEL, ProviderRun, 'returned_model'),
            (interpretation.JOB_KIND, Job, 'kind'),
            (interpretation.ENGINE_VERSION, Assessment, 'engine_version'),
            (interpretation.CONTEXT_VERSION, EncounterContext, 'version'),
            (interpretation.ROUTING_VERSION, RoutingRun, 'version'),
        )
        for value, model, name in columns:
            with self.subTest(column=f'{model.__name__}.{name}'):
                self.assertLessEqual(len(value), model._meta.get_field(name).max_length)
        self.assertEqual((len(interpretation.PURPOSE), len(interpretation.JOB_KIND)), (14, 9))  # of 16 and of 10
        for value in (interpretation.INTERPRETATION_VERSION, interpretation.INVENTORY_VERSION):
            self.assertLessEqual(len(value), 40)  # EventInventory's two version columns (FINAL 4.1, Char 40)

    def test_new_path_rows_are_told_by_their_version_family(self):
        for version, new in (('cpt-studio-events@1', True), ('cpt-studio-events@2', True),
                             ('cpt-studio-validation@10', False), ('cpt-studio-events', False),
                             ('cpt-studio-eventsX@1', False), ('', False), (None, False), (7, False)):
            with self.subTest(engine_version=version):
                self.assertIs(interpretation.is_new_assessment(SimpleNamespace(engine_version=version)), new)
        for version, new in (('gemini-context@1', True), ('gemini-context@3', True), ('gi-context@5', False),
                             ('gemini-context', False), (None, False)):
            with self.subTest(context_version=version):
                self.assertIs(interpretation.is_new_context(SimpleNamespace(version=version)), new)
        self.assertFalse(interpretation.is_new_assessment(None))
        self.assertFalse(interpretation.is_new_assessment(SimpleNamespace()))
        self.assertFalse(interpretation.is_new_context(object()))


class PinTests(SimpleTestCase):
    def test_the_pins_sit_beside_the_version(self):
        pins = PINS[interpretation.INTERPRETATION_VERSION]
        self.assertEqual(schema.sha256_of(prompt.INSTRUCTIONS), pins['INSTRUCTIONS'])
        self.assertEqual(schema.sha256_of(schema.LOCAL_SCHEMA), pins['LOCAL_SCHEMA'])
        self.assertEqual(schema.sha256_of(schema.RESPONSE_SCHEMA), pins['RESPONSE_SCHEMA'])
        self.assertEqual(schema.sha256_of(dict(schema.BOUNDS)), pins['BOUNDS'])
        # the code's own pins, beside INTERPRETATION_VERSION, are these
        self.assertEqual((interpretation.INSTRUCTIONS_SHA256, interpretation.LOCAL_SCHEMA_SHA256,
                          interpretation.RESPONSE_SCHEMA_SHA256),
                         (pins['INSTRUCTIONS'], pins['LOCAL_SCHEMA'], pins['RESPONSE_SCHEMA']))
        # canonical bytes are the body's: the schema's sha256 is the sha256 of its canonical_body bytes
        self.assertEqual(hashlib.sha256(canonical_body(schema.RESPONSE_SCHEMA)).hexdigest(), pins['RESPONSE_SCHEMA'])

    def test_a_request_is_built_only_under_its_pins(self):
        document = prompt.framed(NOTE, PAGES, 'pdf')
        prompt.request_parts(document)  # the positive control: unchanged, it builds
        with mock.patch.object(prompt, 'INSTRUCTIONS', prompt.INSTRUCTIONS.replace('synthetic', 'Synthetic', 1)):
            with self.assertRaisesRegex(RuntimeError, 'needs a new INTERPRETATION_VERSION'):
                prompt.request_parts(document)
        changed = copy.deepcopy(schema.RESPONSE_SCHEMA)
        changed['properties']['events']['items']['properties']['kind']['properties']['value']['enum'].append('x')
        with mock.patch.object(schema, 'RESPONSE_SCHEMA', changed):
            with self.assertRaisesRegex(RuntimeError, 'needs a new INTERPRETATION_VERSION'):
                prompt.request_parts(document)
        prompt.request_parts(document)  # and nothing was left changed

    def test_the_generated_schema_size(self):
        measured = {'local': len(schema.canonical(schema.LOCAL_SCHEMA)),
                    'gemini': len(schema.canonical(schema.RESPONSE_SCHEMA)),
                    'gemini_without_property_ordering': len(schema.canonical(
                        without_property_ordering(schema.RESPONSE_SCHEMA))),
                    'depth': depth(schema.LOCAL_SCHEMA),
                    'enum_sites': sum(1 for _, node in nodes(schema.LOCAL_SCHEMA) if 'enum' in node)}
        self.assertEqual(measured, SIZES)
        self.assertEqual(depth(schema.RESPONSE_SCHEMA), 6)

    def test_the_contracts_enumerations_give_the_contracts_measurement(self):
        contract_landmarks = tuple(item for item in schema.LANDMARKS if item not in COLON_REGIONS)
        local = with_enums(schema.LOCAL_SCHEMA, {schema.SCOPES: CONTRACT_SCOPES,
                                                 schema.LANDMARKS: contract_landmarks})
        swapped = sum(1 for _, node in nodes(local) if node.get('enum') in (CONTRACT_SCOPES, list(contract_landmarks)))
        self.assertEqual(swapped, 5)  # one scope site and four landmark sites
        gemini = schema.gemini_schema(local)
        self.assertEqual({'local': len(schema.canonical(local)), 'gemini': len(schema.canonical(gemini)),
                          'gemini_without_property_ordering': len(schema.canonical(without_property_ordering(gemini)))},
                         CONTRACT_SIZES)
        self.assertEqual(CONTRACT_SIZES['gemini'] - CONTRACT_SIZES['gemini_without_property_ordering'], 1_557)


class EnumerationTests(SimpleTestCase):
    def test_the_enumerations_and_their_order(self):
        self.assertEqual(len(schema.ENUMERATIONS), 17)
        self.assertEqual({name: len(values) for name, values in schema.ENUMERATIONS.items()}, {
            'PROCEDURES': 17, 'KINDS': 42, 'DEVICES': 30, 'TIMES': 4, 'PERFORMERS': 4, 'STATUSES': 5, 'SCOPES': 6,
            'PURPOSES': 10, 'COMPLETIONS': 3, 'EM_BASES': 3, 'SEPARATE': 3, 'DATE_STATES': 3, 'DATE_ROLES': 6,
            'ANATOMY_STATES': 2, 'MULTIPLICITY': 3, 'LANDMARKS': 49, 'QUESTION_ABOUT': 15})
        for name, values in schema.ENUMERATIONS.items():
            with self.subTest(enumeration=name):
                self.assertIsInstance(values, tuple)
                self.assertEqual(len(set(values)), len(values))
                self.assertTrue(all(re.fullmatch(r'[a-z][a-z0-9_]*', value) for value in values))

    def test_the_adjudicated_additions(self):
        # C-7: exceptive, before the catch-all unknown
        self.assertEqual(schema.SCOPES, ('not_applicable', 'single_target', 'all_of_kind', 'listed_targets',
                                         'exceptive', 'unknown'))
        # C-15: the four colon regions, right after colon and before the segments they contain
        at = schema.LANDMARKS.index('colon')
        self.assertEqual(schema.LANDMARKS[at:at + 6], ('colon',) + COLON_REGIONS + ('cecum',))
        self.assertNotIn('specimen', schema.KINDS)  # the legacy artifact: the act that took tissue is the event
        self.assertTrue({'examination', 'removal', 'intervention', 'other'} <= set(schema.KINDS))

    def test_every_enumeration_is_asked_somewhere(self):
        sites = [tuple(node['enum']) for _, node in nodes(schema.LOCAL_SCHEMA) if 'enum' in node]
        for name, values in schema.ENUMERATIONS.items():
            with self.subTest(enumeration=name):
                self.assertIn(values, sites)
        landmark_sites = [path for path, node in nodes(schema.LOCAL_SCHEMA) if node.get('enum') == list(schema.LANDMARKS)]
        self.assertEqual(landmark_sites, ['.encounter.anatomy[].landmark', '.encounter.reach[].landmark',
                                          '.lesions[].landmark', '.events[].target.landmark'])


class SchemaTests(SimpleTestCase):
    def test_the_local_schema_is_one_cpt_studio_validates_itself(self):
        self.assertEqual(reading.schema_error({}, schema.LOCAL_SCHEMA, 'the interpretation'),
                         "the interpretation lacks the required field 'passages'")
        for path, node in nodes(schema.LOCAL_SCHEMA):
            with self.subTest(path=path or 'root'):
                self.assertIn(node['type'], ('object', 'array', 'string', 'integer'))
                if node['type'] == 'object':
                    self.assertIs(node['additionalProperties'], False)
                    self.assertEqual(node['required'], list(node['properties']))
        self.assertEqual(list(schema.LOCAL_SCHEMA['properties']),
                         ['passages', 'encounter', 'lesions', 'events', 'open_questions'])
        event = schema.LOCAL_SCHEMA['properties']['events']['items']['properties']
        self.assertEqual(list(event), ['id', 'procedure', 'kind', 'technique', 'target', 'time', 'performer', 'status',
                                       'scope', 'purpose', 'part_of', 'sequence', 'contradicts'])
        self.assertEqual(event['sequence'], {'type': 'integer'})

    def test_the_response_schema_is_derived_mechanically(self):
        local, gemini = dict(nodes(schema.LOCAL_SCHEMA)), dict(nodes(schema.RESPONSE_SCHEMA))
        self.assertEqual(set(local), set(gemini))
        for path, node in local.items():
            with self.subTest(path=path or 'root'):
                derived = gemini[path]
                self.assertEqual(derived['type'], node['type'].upper())
                self.assertNotIn('additionalProperties', derived)
                self.assertEqual(derived.get('enum'), node.get('enum'))
                if node['type'] == 'object':
                    self.assertEqual(set(derived), {'type', 'properties', 'required', 'propertyOrdering'})
                    self.assertEqual(derived['propertyOrdering'], list(node['properties']))
                    self.assertEqual(derived['required'], derived['propertyOrdering'])
                else:
                    self.assertEqual(set(derived) - {'items', 'enum'}, {'type'})
        self.assertEqual(schema.gemini_schema(schema.LOCAL_SCHEMA), schema.RESPONSE_SCHEMA)

    def test_the_generator_refuses_what_it_does_not_implement(self):
        base = {'type': 'object', 'additionalProperties': False, 'required': ['a'], 'properties': {'a': {'type': 'string'}}}
        refused = {
            'a keyword': {**base, 'description': 'x'},
            'a nested keyword': {**base, 'properties': {'a': {'type': 'string', 'format': 'date'}}},
            'a number': {**base, 'properties': {'a': {'type': 'number'}}},
            'a boolean': {**base, 'properties': {'a': {'type': 'boolean'}}},
            'a nullable union': {**base, 'properties': {'a': {'type': ['string', 'null']}}},
            'open properties': {**base, 'additionalProperties': True},
            'no additionalProperties': {key: value for key, value in base.items() if key != 'additionalProperties'},
            'a field not required': {**base, 'properties': {'a': {'type': 'string'}, 'b': {'type': 'string'}}},
            'required out of order': {**base, 'required': ['b', 'a'],
                                      'properties': {'a': {'type': 'string'}, 'b': {'type': 'string'}}},
            'an empty enum': {**base, 'properties': {'a': {'type': 'string', 'enum': []}}},
            'a repeated enum value': {**base, 'properties': {'a': {'type': 'string', 'enum': ['x', 'x']}}},
            'an integer enum': {**base, 'properties': {'a': {'type': 'integer', 'enum': [1]}}},
            'not a dict': 'string',
        }
        for name, node in refused.items():
            with self.subTest(refused=name):
                with self.assertRaises(ValueError):
                    schema.gemini_schema(node)
        self.assertEqual(schema.gemini_schema(base), {'type': 'OBJECT', 'properties': {'a': {'type': 'STRING'}},
                                                      'required': ['a'], 'propertyOrdering': ['a']})

    def test_the_derived_schema_shares_nothing_with_its_source(self):
        before = schema.canonical(schema.LOCAL_SCHEMA)
        derived = schema.gemini_schema(schema.LOCAL_SCHEMA)
        derived['properties']['events']['items']['properties']['kind']['properties']['value']['enum'].append('x')
        derived['properties']['passages']['items']['required'].append('x')
        self.assertEqual(schema.canonical(schema.LOCAL_SCHEMA), before)

    def test_the_bounds_are_the_contracts(self):
        self.assertEqual(dict(schema.BOUNDS), {
            'passages': 400, 'passage_chars': (1, 600), 'lesions': 64, 'events': 200, 'open_questions': 32,
            'anatomy': 16, 'reach': 16, 'visit_facts': 8, 'team': 8, 'other_dates': 16, 'attribute_passages': 32,
            'contradicts': 8, 'scope_targets': 16, 'question_ids': 64, 'words_chars': 300, 'sequence': (0, 999),
            'cited_passages': 4000})
        self.assertEqual(schema.BOUNDS['passage_chars'][1], reading.MAX_QUOTE_CHARS)  # reading.py:58, as the contract says
        with self.assertRaises(TypeError):
            schema.BOUNDS['events'] = 1  # read-only


class InstructionTests(SimpleTestCase):
    def test_the_lineage_final_5_3_then_the_adjudication(self):
        text = prompt.INSTRUCTIONS
        for old, new in reversed(ADJUDICATED_EDITS):  # the last edit applied is undone first
            text = replaced(text, new, old)
        self.assertEqual(sha256_text(text), FINAL_5_3_SHA256)  # FINAL 5.3, byte for byte
        for old, new in reversed(FINAL_EDITS):
            text = replaced(text, new, old)
        self.assertEqual(sha256_text(text), CONTRACT_2_1_SHA256)  # and under it the contract's 2.1

    def test_the_text_is_plain_and_names_no_code(self):
        text = prompt.INSTRUCTIONS
        self.assertTrue(text.isascii())
        self.assertTrue(text.startswith('You read one gastrointestinal (GI) clinical document'))
        self.assertTrue(text.endswith('Answer with the JSON object only.\n'))
        self.assertIsNone(re.search(r'\b[0-9]{4}[0-9A-Z]\b', text))  # no CPT or HCPCS-shaped code
        self.assertIsNone(re.search(r'(?i)\b(setting|billing context|patient status|cpt studio)\b', text))  # D3; no reading
        self.assertLessEqual(max(len(line) for line in text.split('\n')), 125)

    def test_the_adjudicated_asks(self):
        time = line_of(prompt.INSTRUCTIONS, '- time:')
        for asked in ('whenever the document gives any sign of when the act was done', 'whatever time you give',
                      'a date\n  stated for it', '"prior"', '"previous"', '"previously"', '"at that time"', '"next"',
                      '"History:"', 'with that line among the time\'s passages',
                      'Give "" only\n  when the act is told as part of this encounter with no such sign of its own'):
            with self.subTest(time=asked):
                self.assertIn(asked.replace('\n  ', ' '), ' '.join(time.split()))
        scope = line_of(prompt.INSTRUCTIONS, '- scope,')
        for asked in ('exceptive (the statement covers only acts of this kind beyond those the document reports as done',
                      '"no further", "no other" or "no additional"',
                      'including for exceptive the word that makes the exception',
                      # C-8: all_of_kind means every act of that kind in the statement's own examination or session
                      'all_of_kind (the statement covers every act of this kind in its own examination or session and '
                      'names no particular target)'):
            with self.subTest(scope=asked):
                self.assertIn(asked, ' '.join(scope.split()))
        # C-8: the encounter-wide meaning FINAL 5.3 gave all_of_kind is asked nowhere
        self.assertNotIn('in its encounter', ' '.join(prompt.INSTRUCTIONS.split()))

    def test_the_instructions_name_the_values_each_attribute_takes(self):
        text = ' '.join(prompt.INSTRUCTIONS.split())
        kinds = text[text.index('KINDS examination:'):text.index('OPEN QUESTIONS')]
        lines = {
            'KINDS': kinds,
            'TIMES': line_of(prompt.INSTRUCTIONS, '- time:'),
            'PERFORMERS': line_of(prompt.INSTRUCTIONS, '- performer:'),
            'STATUSES': line_of(prompt.INSTRUCTIONS, '- status:'),
            'SCOPES': line_of(prompt.INSTRUCTIONS, '- scope,'),
            'DATE_STATES': line_of(prompt.INSTRUCTIONS, '- date_of_service:'),
            'DATE_ROLES': line_of(prompt.INSTRUCTIONS, '- date_of_service:'),
            'ANATOMY_STATES': line_of(prompt.INSTRUCTIONS, '- anatomy:'),
            'MULTIPLICITY': line_of(prompt.INSTRUCTIONS, '- lesions lists'),
            'EM_BASES': line_of(prompt.INSTRUCTIONS, '- visit_facts:'),
            'SEPARATE': line_of(prompt.INSTRUCTIONS, '- visit_facts:'),
        }
        for name, where in lines.items():
            words = set(re.findall(r'[a-z][a-z0-9_]*', where))
            for value in schema.ENUMERATIONS[name]:
                if value == 'not_stated':
                    continue  # rule 4 names the not-stated values once for every attribute
                with self.subTest(enumeration=name, value=value):
                    self.assertIn(value, words)


class FramingTests(SimpleTestCase):
    def test_a_pdf_says_only_its_text_is_given(self):
        original = participant_prompt.framed_document(NOTE, PAGES, 'pdf')
        framed = prompt.framed(NOTE, PAGES, 'pdf')
        self.assertEqual(framed.split('\n')[0], 'Document: a PDF; only its extracted text is given.')
        self.assertEqual(framed.split('\n')[1:], original.split('\n')[1:])
        self.assertTrue(original.startswith('Document: a PDF; the original file is attached'))
        self.assertNotIn('attached', framed)
        marker = participant_prompt.marker(NOTE)
        self.assertEqual(framed, '\n'.join([
            'Document: a PDF; only its extracted text is given.',
            'Its extracted text follows between the two marker lines. The [Page N] lines mark where each page begins and '
            'are not part of the text.',
            f'<<<{marker} BEGIN>>>', '[Page 1]', NOTE[:BREAK], '[Page 2]', NOTE[BREAK:], f'<<<{marker} END>>>']))

    def test_every_other_kind_is_framed_as_the_participants_frame_it(self):
        for kind in ('docx', 'paste', 'txt', 'addendum'):
            with self.subTest(kind=kind):
                self.assertEqual(prompt.framed(NOTE, PAGES, kind), participant_prompt.framed_document(NOTE, PAGES, kind))
        self.assertEqual(set(participant_prompt.KINDS), {'pdf', 'docx', 'paste', 'txt', 'addendum'})
        with self.assertRaises(ValueError):
            prompt.framed(NOTE, PAGES, 'html')

    def test_a_text_that_cannot_be_framed_is_not(self):
        # A text's marker is derived from the text, so one that contains it cannot be written by hand: the marker is
        # made a word the text holds instead.
        with mock.patch.object(participant_prompt, 'marker', return_value='Synthetic'):
            for kind in ('pdf', 'paste'):
                with self.subTest(kind=kind):
                    self.assertIsNone(prompt.framed(NOTE, PAGES, kind))
        gap = (PageSpan(page=1, start=0, end=BREAK - 1), PageSpan(page=2, start=BREAK, end=len(NOTE)))
        for kind in ('pdf', 'paste'):
            with self.subTest(kind=kind):
                self.assertIsNone(prompt.framed(NOTE, gap, kind))

    def test_the_pdf_line_is_guarded(self):
        original = participant_prompt.framed_document(NOTE, PAGES, 'pdf')
        other = 'Document: a scanned file.\n' + original.split('\n', 1)[1]
        with mock.patch.object(participant_prompt, 'framed_document', return_value=other):
            with self.assertRaisesRegex(RuntimeError, 'no longer opens with the PDF line'):
                prompt.framed(NOTE, PAGES, 'pdf')
            self.assertEqual(prompt.framed(NOTE, PAGES, 'docx'), other)  # only a PDF's first line is replaced
        self.assertTrue(prompt.framed(NOTE, PAGES, 'pdf').startswith(prompt.PDF_LINE + '\n'))  # positive control

    def test_the_adapter_frames_through_the_participants_checks(self):
        self.assertEqual(http.framed_text(NOTE, PAGES, 'pdf', prompt.framed), prompt.framed(NOTE, PAGES, 'pdf'))
        cannot = {'no text': ('   \n', ()), 'NUL': (NOTE + '\x00', ()),
                  'pages that do not tile it': (NOTE, (PageSpan(page=1, start=0, end=3),))}
        for name, (text, pages) in cannot.items():
            with self.subTest(cannot=name):
                with self.assertRaisesRegex(ProviderUnavailable, 'nothing was sent'):
                    http.framed_text(text, pages, 'pdf', prompt.framed)
        with mock.patch.object(participant_prompt, 'marker', return_value='Synthetic'):
            with self.assertRaisesRegex(ProviderUnavailable, 'its own framing marker'):
                http.framed_text(NOTE, PAGES, 'pdf', prompt.framed)


class BodyTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.framed = prompt.framed(NOTE, PAGES, 'pdf')
        self.body = prompt.request_parts(self.framed)

    def test_the_body_has_exactly_the_three_keys(self):
        self.assertEqual(list(self.body), ['systemInstruction', 'contents', 'generationConfig'])
        self.assertEqual(tuple(self.body), prompt.BODY_KEYS)
        self.assertEqual(self.body['systemInstruction'], {'parts': [{'text': prompt.INSTRUCTIONS}]})
        self.assertEqual(self.body['contents'], [{'role': 'user', 'parts': [{'text': self.framed}]}])
        self.assertEqual(self.body['generationConfig'], {'temperature': 0, 'maxOutputTokens': 32768,
                                                         'responseMimeType': 'application/json',
                                                         'responseSchema': schema.RESPONSE_SCHEMA})
        self.assertIs(type(self.body['generationConfig']['temperature']), int)
        self.assertEqual(request_sha256(self.body), NOTE_PDF_REQUEST_SHA256)

    def test_it_carries_the_instructions_the_document_and_the_schema_only(self):
        schema_strings = {value for value in _strings(schema.RESPONSE_SCHEMA)}
        allowed = {prompt.INSTRUCTIONS, self.framed, 'user', 'application/json'} | schema_strings
        self.assertLessEqual(set(_strings(self.body)), allowed)
        outer = dict(self.body)
        outer['generationConfig'] = {key: value for key, value in outer['generationConfig'].items()
                                     if key != 'responseSchema'}
        self.assertEqual(set(_keys(outer)), {'systemInstruction', 'contents', 'generationConfig', 'parts', 'text',
                                             'role', 'temperature', 'maxOutputTokens', 'responseMimeType'})

    def test_no_member_value_filename_title_or_reading_can_enter_it(self):
        self.assertEqual(list(inspect.signature(prompt.framed).parameters), ['text', 'pages', 'kind'])
        self.assertEqual(list(inspect.signature(prompt.request_parts).parameters), ['framed_text'])
        # an upload as the pipeline holds it: everything a request must never carry sits beside the text
        upload = SimpleNamespace(
            text=NOTE, pages=PAGES, kind='pdf', filename='SYNTHETIC-FILENAME-0001.pdf', title='SYNTHETIC-TITLE-0001',
            user_values={'service_date': '2031-02-03', 'setting': 'SYNTHETIC-SETTING-0001'},
            cpt_studio_reading={'held': [{'code': '45385', 'reason': 'SYNTHETIC-READING-0001'}]},
            participant_output={'codes': [{'code': '45380', 'basis': 'SYNTHETIC-PARTICIPANT-0001'}]})
        body = canonical_body(prompt.request_parts(prompt.framed(upload.text, upload.pages, upload.kind)))
        for planted in ('SYNTHETIC-FILENAME-0001', 'SYNTHETIC-TITLE-0001', '2031-02-03', 'SYNTHETIC-SETTING-0001',
                        '45385', 'SYNTHETIC-READING-0001', '45380', 'SYNTHETIC-PARTICIPANT-0001'):
            with self.subTest(planted=planted):
                self.assertNotIn(planted.encode(), body)
        self.assertIn('transverse colon'.encode(), body)  # positive control: the document itself is there

    def test_nothing_unframed_is_sent(self):
        with self.assertRaises(TypeError):
            prompt.request_parts(None)
        for text in (NOTE, '', 'Document: a PDF.', self.framed.rsplit('\n', 1)[0], self.framed + '\nmore',
                     self.framed.replace(' END>>>', ' FINISH>>>')):
            with self.subTest(text=text[:40]):
                with self.assertRaises(ValueError):
                    prompt.request_parts(text)
        for kind in ('pdf', 'docx', 'paste', 'txt', 'addendum'):
            with self.subTest(kind=kind):
                prompt.request_parts(prompt.framed(NOTE, PAGES, kind))
                prompt.request_parts(prompt.framed(NOTE, (), kind))
        # A PDF framed for a participant (whose first line says the original file is attached) or for a peer review is
        # framed in form, and still refused: this request attaches no original, and its first line must say so (D12).
        rest = self.framed.split('\n', 1)[1]
        for name, framed in (('participants.prompt.framed_document', participant_prompt.framed_document(NOTE, PAGES, 'pdf')),
                             ('participants.prompt.peer_framed_document',
                              participant_prompt.peer_framed_document(NOTE, PAGES, 'pdf')),
                             ('an unknown kind', f'Document: an image.\n{rest}'),
                             ('a first line with a space after it', f'{prompt.PDF_LINE} \n{rest}')):
            with self.subTest(framed_by=name):
                self.assertEqual(framed.split('\n')[1:], self.framed.split('\n')[1:])  # only the first line differs
                with self.assertRaises(ValueError):
                    prompt.request_parts(framed)

    def test_the_first_lines_are_the_ones_framed_gives(self):
        self.assertEqual(prompt.FIRST_LINES, frozenset({
            'Document: a PDF; only its extracted text is given.',
            'Document: a Word document; only its extracted text is given.',
            'Document: pasted text.',
            'Document: a plain-text file.',
            'Document: a document with an addendum appended to its text; only the text is given.'}))
        self.assertEqual({prompt.framed(NOTE, PAGES, kind).split('\n')[0] for kind in participant_prompt.KINDS},
                         prompt.FIRST_LINES)
        self.assertEqual([line for line in prompt.FIRST_LINES if 'attached' in line or 'review' in line], [])

    def test_the_body_shares_nothing_with_the_module(self):
        before = schema.canonical(schema.RESPONSE_SCHEMA)
        self.body['generationConfig']['responseSchema']['properties'].clear()
        self.body['systemInstruction']['parts'][0]['text'] = 'changed'
        self.assertEqual(schema.canonical(schema.RESPONSE_SCHEMA), before)
        again = prompt.request_parts(self.framed)
        self.assertEqual(again['systemInstruction']['parts'][0]['text'], prompt.INSTRUCTIONS)
        self.assertEqual(request_sha256(again), NOTE_PDF_REQUEST_SHA256)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


class NoLegacyImportTests(SimpleTestCase):
    """D17: nothing under studio/interpretation/ imports studio.gi except gi.profiles and gi.catalogue, and this slice's
    modules import none of it at all."""

    def imported(self, path: Path) -> list[str]:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        package = 'studio.interpretation'
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found += [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ''
                if node.level:
                    parts = package.split('.')[:len(package.split('.')) - node.level + 1]
                    base = '.'.join(parts + ([node.module] if node.module else []))
                found.append(base)
                found += [f'{base}.{alias.name}' for alias in node.names]
            elif isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                if name in ('importlib.import_module', '__import__', 'import_module') and node.args:
                    found.append(ast.unparse(node.args[0]))
        return found

    def test_an_ast_scan_finds_no_studio_gi_import(self):
        for module in SLICE_MODULES:
            path = PACKAGE / f'{module}.py'
            with self.subTest(module=module):
                imports = self.imported(path)
                self.assertTrue(imports)  # the scan sees this module's imports (positive control below)
                legacy = [name for name in imports if re.match(r"""['"]?studio\.(gi|validation|candidates)\b""", name)]
                self.assertEqual(legacy, [])
                self.assertFalse(any('gi' == name.split('.')[-1] for name in imports))

    def test_the_scan_sees_each_form_of_import(self):
        planted = ('import studio.gi.services\nfrom studio.gi import context\nfrom studio import gi\n'
                   'from ..gi import detect\nimportlib.import_module("studio.gi.catalogue")\n')
        path = Path(self.enterContext(_scratch_file(planted)))
        found = self.imported(path)
        for expected in ('studio.gi.services', 'studio.gi', 'studio.gi.context', 'studio.gi', 'studio.gi.detect',
                         "'studio.gi.catalogue'"):
            with self.subTest(form=expected):
                self.assertIn(expected, found)

    def test_a_fresh_interpreter_loads_no_legacy_module(self):
        code = ('import sys\n'
                'import studio.interpretation, studio.interpretation.prompt, studio.interpretation.schema\n'
                'import studio.interpretation.read, studio.interpretation.store\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=60, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        loaded = result.stdout.strip().split(',')
        self.assertIn('studio.interpretation.store', loaded)
        self.assertEqual([name for name in loaded if re.match(r'studio\.(gi|validation|candidates)\b', name)], [])
        self.assertEqual(sorted(loaded), ['studio', 'studio.interpretation', 'studio.interpretation.prompt',
                                          'studio.interpretation.read', 'studio.interpretation.schema',
                                          'studio.interpretation.store', 'studio.participants',
                                          'studio.participants.prompt', 'studio.participants.reading', 'studio.types'])


class _scratch_file:
    """A temporary .py file holding ``text`` (a context manager giving its path)."""

    def __init__(self, text: str):
        self.text = text

    def __enter__(self):
        import tempfile
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / 'planted.py'
        path.write_text(self.text, encoding='utf-8')
        return path

    def __exit__(self, *exc):
        self.directory.cleanup()
        return False
