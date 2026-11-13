"""The strict reader of pass 1's answer (contract/extract_read.py; docs/gemini-migration/FINAL-V2.md 3.1 S1, S2, I1, I3's
per-source bound and I4, and 1.8; step 1b of 8.1), TEXT-ONLY and SYNTHETIC.

The base fixture is the design's own worked example (FINAL-V2 1.9: a synthetic colonoscopy report of nine units with a
fictional endoscopist), written as pass 1's answer; no document is read (the reader takes the unit count) and no
provider is called.

What is proved here:
- the worked example is read with no finding, every fact keyed where it sits and exactly as written;
- every refusal stage of S1 with a planted case each (json, schema, bounds, ids, and the ISO shapes at schema), in
  order, and each bound of 1.8 at its limit (read) and one past it (refused, named by count) - every slot, every list,
  every words value and the cited units included; a section's closing signatures take no count of their own, only the
  cited units bound them (triage 1b#1);
- the ids stage is DECISIONS D185's one grammar - a family's letter and its number in canonical decimal digits - for
  every object id, every id-valued reference and option, every member of an id list, every object a doubt names and
  every cited unit id, each named by its path; a well-formed id that leads nowhere stays item-level (I4, I1); the
  grammar equals store._v2_id's, and engine/types.Id.parse reads back every id it admits;
- a source or an anchor over 12 units is an ITEM-level finding, source_too_long, and the answer is read [R:CO-5];
- S2's fact shapes (value empty exactly for contradicted; sources and options counts; a source of no unit) and the date
  of service's; S2's doubt shape, a malformed doubt naming every claimed fact of its objects (fail-closed) [R:HO-1]
  [R:CO-1], a date of service's reading a day (DECISIONS D200, triage 1b#2); I1 against the unit count; I4's
  resolution, self references and cycles;
- nothing in the reader sets, changes or removes a value (a property test over random facts as well);
- Refusal, refuse, iso_date and partial_date equal v1's (read.py, read only), and the pin is v1's pattern;
- 5.7 measure 4 holds for the module, and mypy --strict passes on both of the step's modules.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest import mock

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio import interpretation
from studio.interpretation import read as v1_read  # v1, read only: the parity proofs, computed here
from studio.interpretation.contract import extract_read as xr
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract import jsonschema
from studio.interpretation.contract import types as ct
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
CONTRACT = APP / 'studio' / 'interpretation' / 'contract'
REFUSED = xr.REFUSED
A, F, R = ct.Attribute, xs.Family, ct.Reason
UNITS = 9  # the worked example's units, S1 .. S9 (FINAL-V2 1.9)
SHAPE, UNIT, LONG, REF = R.SHAPE_INCONSISTENT, R.UNIT_UNKNOWN, R.SOURCE_TOO_LONG, R.REFERENCE_INVALID
MODEL_TEXT = 'Polyp_removed_at_twelve'  # a model-written string no refusal may repeat
# DECISIONS D185's grammar as the ids stage states it: a family's letter, then 0 or 1-9 digits not opening with 0
DIGITS = 'and then a number of at most 9 decimal digits with no leading zero'
ANY_OBJECT = f'the letter P, N, X, Y, L or E {DIGITS}'  # a reference, an option of one, a member, a doubt's object
A_UNIT = f'the letter S {DIGITS}'
GRAMMAR = re.compile(r'(?:0|[1-9][0-9]{0,8})')  # the number, computed here independently of the reader


# --- the answer builders ------------------------------------------------------------------------------------------------

def src(*units: str, words: str = '', link: str = 'statement') -> dict:
    return {'units': list(units), 'words': words, 'link': link}


def fact(value: str, *units: str, state: str = 'supported', words: str = '', link: str = 'statement',
         qualifiers=()) -> dict:
    return {'state': state, 'value': value, 'qualifiers': list(qualifiers),
            'sources': [src(*units, words=words, link=link)] if units else [], 'options': []}


def contradicted(*sides) -> dict:
    """A contradicted fact: each side (value, units...), its sources the union of the sides'."""
    return {'state': 'contradicted', 'value': '', 'qualifiers': [],
            'sources': [src(*units) for _, *units in sides],
            'options': [{'value': value, 'sources': [src(*units)]} for value, *units in sides]}


def put(item: dict, path: str, value) -> dict:
    """``item`` with ``value`` at the dotted ``path`` (target.places), in place."""
    *parents, last = path.split('.')
    node = item
    for key in parents:
        node = node[key]
    node[last] = value
    return item


def section(id: str, start: dict, owner: dict, **slots) -> dict:
    item = {'id': id, 'start': start, 'end': [], 'owner': owner, 'role': [], 'occasion': [], 'performer': [],
            'performer_person': []}
    item.update(slots)
    return item


def session(id: str, kind: dict, **fields) -> dict:
    item = {'id': id, 'examination': [], 'kind': kind, 'encounter': [], 'tract': [], 'approach': [], 'through': [],
            'reached': [], 'device_reached': [], 'reached_anatomy': [], 'completion': [], 'stations': [],
            'part_of_session': []}
    item.update(fields)
    return item


def anatomy(id: str, type_: dict, **fields) -> dict:
    item = {'id': id, 'type': type_, 'organ': [], 'subtype': [], 'joins': []}
    item.update(fields)
    return item


def lesion(id: str, description: dict, **fields) -> dict:
    item = {'id': id, 'description': description, 'multiplicity': [], 'places': [], 'distinct_from': [],
            'same_as': []}
    item.update(fields)
    return item


def event(id: str, anchor, kind: dict, status: dict, **fields) -> dict:
    item = {'id': id, 'anchor': {'units': list(anchor), 'kind_words': 'act', 'status_words': 'done'},
            'restatements': [], 'kind': kind, 'other_class': [], 'status': status, 'session': [], 'date_relation': [],
            'date': [], 'performer': [], 'performer_person': [],
            'target': {'lesion': [], 'structure': [], 'places': [], 'anatomy': [], 'duct': []},
            'technique': {'device': [], 'route': []}, 'purpose': [], 'cause': [], 'cause_event': [], 'part_of': [],
            'part_relation': [], 'yield': [], 'access_outcome': [],
            'scope': {'breadth': [], 'targets': [], 'segment': [], 'covers': [], 'excepts': []},
            'visit': {'basis': [], 'separately_identifiable': []}}
    for path, value in fields.items():
        put(item, path.replace('__', '.'), value)
    return item


def doubt(about: str, objects=(), units=('S6',), basis: str = 'unclear', readings=()) -> dict:
    return {'about': about, 'objects': list(objects), 'units': list(units), 'basis': basis,
            'readings': list(readings)}


def answer() -> dict:
    """FINAL-V2 1.9's worked example as pass 1 would file it (abridged there, whole here)."""
    frame = {'link': 'document_frame'}
    return {
        'encounter': {
            'date_of_service': {'state': 'stated', 'value': '2026-11-09',
                                'sources': [src('S2', words='11/09/2026', **frame)], 'options': []},
            'other_dates': [{'value': '2023', 'role': fact('other_occurrence', 'S4', words='2023')}],
            'documenting_clinician': [fact('P1', 'S3', words='Anselm Wrenfield, MD', **frame)],
        },
        'people': [
            {'id': 'P1', 'name': src('S3', words='Anselm Wrenfield'),
             'role': fact('documenting_clinician', 'S3', words='Endoscopist')},
            {'id': 'P2', 'name': src('S8', words='Jo Rowe'), 'role': fact('nurse', 'S8', words='RN')},
        ],
        'sections': [
            section('N0', src(link='section'), fact('documenting_clinician', 'S3', **frame),
                    role=[fact('header', 'S1', link='section')],
                    occasion=[fact('on_date_of_service', 'S2', words='11/09/2026', **frame)],
                    performer=[fact('documenting_team', 'S3', **frame)]),
            section('N1', src('S4', words='History:', link='section'), fact('documenting_clinician', 'S3', **frame),
                    role=[fact('history', 'S4', words='History:', link='section')],
                    occasion=[fact('earlier_date', 'S4', words='Prior colonoscopy in 2023', link='section')]),
            section('N2', src('S5', words='Findings:', link='section'), fact('documenting_clinician', 'S3', **frame),
                    role=[fact('findings', 'S5', words='Findings:', link='section')],
                    occasion=[fact('on_date_of_service', 'S2', **frame)],
                    performer=[fact('documenting_team', 'S3', **frame)]),
            section('N3', src('S8', words='Documented by Jo Rowe, RN:', link='section'),
                    fact('nursing', 'S8', words='Documented by Jo Rowe, RN:', link='section'),
                    role=[fact('nursing_note', 'S8', link='section')],
                    occasion=[fact('on_date_of_service', 'S2', **frame)]),
        ],
        'sessions': [
            session('X1', fact('colonoscopy', 'S1', words='COLONOSCOPY', **frame), examination=[fact('E1', 'S5')],
                    encounter=[fact('this_encounter', 'S2', **frame)],
                    reached=[fact('cecum', 'S5', words='advanced to the cecum')]),
        ],
        'anatomy': [],
        'lesions': [
            lesion('L1', src('S6', words='A 6 mm sessile polyp'), multiplicity=[fact('single', 'S6')],
                   places=[fact('sigmoid_colon', 'S6', words='sigmoid colon')]),
            lesion('L2', src('S8', words='A 4 mm polyp'), places=[fact('rectum', 'S8', words='rectum')]),
        ],
        'events': [
            event('E1', ['S5'], fact('examination', 'S5', words='colonoscope'), fact('performed', 'S5'),
                  session=[fact('X1', 'S5')]),
            event('E2', ['S6'], fact('snare', 'S6', words='cold snare'), fact('performed', 'S6', words='was removed'),
                  session=[fact('X1', 'S6')], target__lesion=[fact('L1', 'S6')],
                  target__places=[fact('sigmoid_colon', 'S6')], technique__device=[fact('cold_snare', 'S6')]),
            event('E3', ['S7'], fact('biopsy', 'S7', words='biopsy'),
                  fact('performed', 'S7', state='negated', words='Neither biopsy nor tattoo was performed'),
                  session=[fact('X1', 'S7')], scope__breadth=[fact('all_of_kind', 'S7')]),
            event('E4', ['S7'], fact('tattoo', 'S7', words='tattoo'),
                  fact('performed', 'S7', state='negated', words='Neither biopsy nor tattoo was performed'),
                  session=[fact('X1', 'S7')], scope__breadth=[fact('all_of_kind', 'S7')]),
            event('E5', ['S8', 'S9'], fact('biopsy', 'S9', words='biopsied'),
                  fact('performed', 'S9', words='was biopsied'), target__lesion=[fact('L2', 'S8')],
                  target__places=[fact('rectum', 'S8')], technique__device=[fact('cold_forceps', 'S9')]),
            event('E6', ['S4'], fact('removal', 'S4', words='removal'), fact('performed', 'S4', words='with removal'),
                  date=[fact('2023', 'S4', words='2023')]),
        ],
        'doubts': [],
    }


def text(value) -> str:
    return json.dumps(value)


def changed(edit) -> dict:
    value = answer()
    edit(value)
    return value


def typed_source(node: dict) -> ct.Source:
    return ct.Source(tuple(node['units']), node['words'], ct.Link(node['link']))


def typed(node: dict) -> ct.Fact:
    """A fact node typed independently of the reader: what 'as written' means."""
    return ct.Fact(ct.FactState(node['state']), node['value'], tuple(ct.Qualifier(q) for q in node['qualifiers']),
                   tuple(typed_source(s) for s in node['sources']),
                   tuple(ct.Option(o['value'], tuple(typed_source(s) for s in o['sources'])) for o in node['options']))


def key(family, object_id, attribute, index=0) -> xr.FactKey:
    return xr.FactKey(family, object_id, attribute, index)


class ReadTestCase(SimpleTestCase):
    """Every test reads under the computed LOCAL_SCHEMA_2 pin, which the integration owner writes (2.5)."""

    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.object(interpretation, 'LOCAL_SCHEMA_SHA256_V2',
                                            jsonschema.sha256_of(xs.LOCAL_SCHEMA_2)))

    def read(self, value, units: int = UNITS):
        return xr.read(value if isinstance(value, str) else text(value), units)

    def accepted(self, value, units: int = UNITS) -> xr.ReadAnswer:
        result = self.read(value, units)
        self.assertIsInstance(result, xr.ReadAnswer, getattr(result, 'reason', ''))
        return result

    def refused(self, value, stage: str, reason: str):
        result = self.read(value)
        self.assertIsInstance(result, xr.Refusal)
        self.assertEqual((result.stage, result.reason), (stage, f'{REFUSED}{reason}.'))

    def reasons(self, value, at: xr.FactKey, units: int = UNITS) -> tuple:
        found = self.accepted(value, units).fact(at)
        self.assertIsNotNone(found, at)
        return found.reasons

    def findings(self, result: xr.ReadAnswer) -> list:
        """Every (place, reasons) with a finding, over facts, citations, members and doubts."""
        out = [(item.key, item.reasons) for item in result.facts if item.reasons]
        out += [((item.family, item.object, item.cited, item.index), item.reasons) for item in result.citations
                if item.reasons]
        out += [(item.key, item.reasons) for item in result.members if item.reasons]
        out += [(('doubt', item.index), item.reasons) for item in result.doubts if item.reasons]
        return out


# --- a good answer -------------------------------------------------------------------------------------------------------


class GoodAnswerTests(ReadTestCase):
    def test_the_worked_example_is_read_with_no_finding(self):
        result = self.accepted(answer())
        self.assertEqual(self.findings(result), [])
        self.assertEqual(result.answer, answer())  # exactly as parsed
        self.assertEqual(result.unit_count, UNITS)
        self.assertEqual((len(result.facts), len(result.citations), len(result.members), len(result.doubts)),
                         (51, 14, 0, 0))

    def test_every_fact_is_keyed_where_it_sits_and_read_as_written(self):
        result = self.accepted(answer())
        source = answer()
        events = {item['id']: item for item in source['events']}
        expected = {
            key(F.ENCOUNTER, '', A.OTHER_DATES_ROLE): source['encounter']['other_dates'][0]['role'],
            key(F.ENCOUNTER, '', A.DOCUMENTING_CLINICIAN): source['encounter']['documenting_clinician'][0],
            key(F.PERSON, 'P2', A.ROLE): source['people'][1]['role'],
            key(F.SECTION, 'N3', A.OWNER): source['sections'][3]['owner'],
            key(F.SECTION, 'N1', A.OCCASION): source['sections'][1]['occasion'][0],
            key(F.SESSION, 'X1', A.REACHED): source['sessions'][0]['reached'][0],
            key(F.LESION, 'L2', A.PLACES): source['lesions'][1]['places'][0],
            key(F.EVENT, 'E2', A.TECHNIQUE_DEVICE): events['E2']['technique']['device'][0],
            key(F.EVENT, 'E3', A.STATUS): events['E3']['status'],
            key(F.EVENT, 'E3', A.SCOPE_BREADTH): events['E3']['scope']['breadth'][0],
            key(F.EVENT, 'E6', A.DATE): events['E6']['date'][0],
        }
        for at, node in expected.items():
            with self.subTest(key=at):
                self.assertEqual(result.fact(at).fact, typed(node))
        when = result.fact(key(F.ENCOUNTER, '', A.DATE_OF_SERVICE))
        self.assertEqual(when.fact, xr.DateOfService(ct.DateState.STATED, '2026-11-09',
                                                     (ct.Source(('S2',), '11/09/2026', ct.Link.DOCUMENT_FRAME),), ()))
        self.assertIsNone(result.fact(key(F.EVENT, 'E1', A.PURPOSE)))  # a silent slot has no fact
        self.assertEqual(result.facts[0].key, key(F.ENCOUNTER, '', A.DATE_OF_SERVICE))  # the answer's order
        self.assertEqual(result.facts[-1].key, key(F.EVENT, 'E6', A.DATE))
        orders = [xs.attributes(item.key.family).index(item.key.attribute) for item in result.facts
                  if item.key.family is F.EVENT and item.key.object == 'E2']
        self.assertEqual(orders, sorted(orders))

    def test_citations_are_listed_with_their_sources(self):
        result = self.accepted(answer())
        found = {(c.family, c.object, c.cited, c.index): c for c in result.citations}
        self.assertEqual(found[(F.PERSON, 'P1', xr.Cited.NAME, 0)].source,
                         ct.Source(('S3',), 'Anselm Wrenfield', ct.Link.STATEMENT))
        self.assertEqual(found[(F.SECTION, 'N0', xr.Cited.START, 0)].units, ())
        self.assertEqual(found[(F.EVENT, 'E5', xr.Cited.ANCHOR, 0)].units, ('S8', 'S9'))
        self.assertIsNone(found[(F.EVENT, 'E5', xr.Cited.ANCHOR, 0)].source)

    def test_the_read_is_deterministic_and_frozen(self):
        self.assertEqual(self.accepted(answer()), self.accepted(answer()))
        result = self.accepted(answer())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.facts[0].reasons = (SHAPE,)

    def test_a_value_reaches_the_reader_untouched(self):
        odd = changed(lambda v: v['encounter']['documenting_clinician'][0]['sources'][0].update(
            words='  Anselm   Wrenfield,\nMD '))
        odd['events'][1]['kind']['qualifiers'] = ['approximate', 'approximate', 'hedged']
        before = jsonschema.canonical(odd)
        result = self.accepted(odd)
        self.assertEqual(jsonschema.canonical(result.answer), before)
        self.assertEqual(result.fact(key(F.ENCOUNTER, '', A.DOCUMENTING_CLINICIAN)).fact.sources[0].words,
                         '  Anselm   Wrenfield,\nMD ')
        self.assertEqual(result.fact(key(F.EVENT, 'E2', A.KIND)).fact.qualifiers,
                         (ct.Qualifier.APPROXIMATE, ct.Qualifier.APPROXIMATE, ct.Qualifier.HEDGED))


# --- S1: json, schema, bounds, ids, ISO shapes ---------------------------------------------------------------------------


class JsonStageTests(ReadTestCase):
    def test_strict_json(self):
        good = text(answer())
        rows = {
            'no text': (None, 'there is no answer text'),
            'bytes': (good.encode(), 'there is no answer text'),
            'empty': ('', 'the answer is not valid JSON (Expecting value at character 0)'),
            'trailing text': (good + ' x', f'the answer is not valid JSON (Extra data at character {len(good) + 1})'),
            'a code fence': ('```json\n' + good + '\n```',
                             'the answer is not valid JSON (Expecting value at character 0)'),
            'a repeated key': ('{"doubts": [], "doubts": []}',
                               'the answer repeats a JSON object key, so its meaning is ambiguous'),
            'NaN': ('{"a": NaN}', 'the answer contains a non-finite number'),
            'Infinity': ('{"a": -Infinity}', 'the answer contains a non-finite number'),
            'a number too large': ('{"a": 1e400}', 'the answer contains a number too large to represent'),
            'NUL': ('{"a": "\\u0000"}', 'the answer contains NUL or unpaired surrogate characters'),
            'a lone surrogate': ('{"a": "\\ud800"}', 'the answer contains NUL or unpaired surrogate characters'),
        }
        for name, (value, reason) in rows.items():
            with self.subTest(json=name):
                result = xr.read(value, UNITS)
                self.assertIsInstance(result, xr.Refusal)
                self.assertEqual((result.stage, result.reason), ('json', f'{REFUSED}{reason}.'))


class SchemaStageTests(ReadTestCase):
    def test_the_schema(self):
        breach = 'the answer breaks the interpretation schema: '
        e1 = 'events[1]'
        rows = {
            'not an object': ([], 'the interpretation is not an object'),
            'no doubts list [R:CO-1]': (changed(lambda v: v.pop('doubts')),
                                        "the interpretation lacks the required field 'doubts'"),
            "v1's open questions": (changed(lambda v: v.update(open_questions=[])),  # a long key named by length
                                    'the interpretation has a field the schema does not allow (a value of 14 '
                                    'characters)'),
            'a verified flag (3.6)': (changed(lambda v: v['events'][1]['kind'].update(verified='yes')),
                                      f"{e1}.kind has a field the schema does not allow ('verified')"),
            'no device_reached [R:CO-8]': (changed(lambda v: v['sessions'][0].pop('device_reached')),
                                           "sessions[0] lacks the required field 'device_reached'"),
            "v1's uncertain status": (changed(lambda v: v['events'][1]['status'].update(value='uncertain')),
                                      f'{e1}.status.value is not one of the values the schema allows'),
            "v1's not_stated device": (changed(lambda v: v['events'][1]['technique']['device'][0].update(
                value='not_stated')), f'{e1}.technique.device[0].value is not one of the values the schema allows'),
            'a place written as words': (changed(lambda v: v['lesions'][0]['places'][0].update(value='sigmoid colon')),
                                         'lesions[0].places[0].value is not one of the values the schema allows'),
            "an option's empty value": (changed(lambda v: v['events'][1].update(kind=contradicted(
                ('snare', 'S6'), ('', 'S7')))), f'{e1}.kind.options[1].value is not one of the values the schema '
                                                'allows'),
            'a state outside FACT_STATES': (changed(lambda v: v['events'][1]['kind'].update(state='ambiguous')),
                                            f'{e1}.kind.state is not one of the values the schema allows'),
            'a link outside LINKS': (changed(lambda v: v['events'][1]['kind']['sources'][0].update(link='default')),
                                     f'{e1}.kind.sources[0].link is not one of the values the schema allows'),
            'a doubt about something unlisted': (changed(lambda v: v['doubts'].append(doubt('time', ['E2']))),
                                                 'doubts[0].about is not one of the values the schema allows'),
            'a slot given as a fact': (changed(lambda v: v['events'][1].update(session=fact('X1', 'S6'))),
                                       f'{e1}.session is not a list'),
            'a fact given as a slot': (changed(lambda v: v['events'][1].update(kind=[fact('snare', 'S6')])),
                                       f'{e1}.kind is not an object'),
            'null for a string': (changed(lambda v: v['events'][1]['anchor'].update(kind_words=None)),
                                  f'{e1}.anchor.kind_words is not a string'),
            'an integer for a string': (changed(lambda v: v['encounter']['other_dates'][0].update(value=2023)),
                                        'encounter.other_dates[0].value is not a string'),
            'a unit id as a number': (changed(lambda v: v['events'][1]['anchor'].update(units=[6])),
                                      f'{e1}.anchor.units[0] is not a string'),
        }
        for name, (value, reason) in rows.items():
            with self.subTest(schema=name):
                self.refused(value, 'schema', breach + reason)


def full_ids(count: int, letter: str) -> list:
    return [f'{letter}{index}' for index in range(1, count + 1)]


class BoundStageTests(ReadTestCase):
    """Each bound at its limit is read, and one past it is refused, named by count and never truncated."""

    def at_and_past(self, build, limit: int, reason: str):
        self.accepted(build(limit))
        self.refused(build(limit + 1), 'bounds', reason.format(n=f'{limit + 1:,}', limit=f'{limit:,}'))

    def test_the_top_level_lists(self):
        def events(n):
            value = answer()
            value['events'] += [event(f'E{i}', ['S1'], fact('other', 'S1'), fact('performed', 'S1'))
                                for i in range(7, 7 + n - len(value['events']))]
            return value

        def objects(name, make, letter):
            def build(n):
                value = answer()
                value[name] = [make(item) for item in full_ids(n, letter)]
                return value
            return build

        self.at_and_past(events, 200, 'it lists {n} events, more than the {limit} this contract accepts')
        rows = (  # each family's own letter (D185)
            ('sections', 48, lambda i: section(i, src('S1', link='section'), fact('documenting_clinician', 'S1')), 'N'),
            ('sessions', 16, lambda i: session(i, fact('egd', 'S1')), 'X'),
            ('people', 16, lambda i: {'id': i, 'name': src('S1'), 'role': fact('other', 'S1')}, 'P'),
            ('anatomy', 16, lambda i: anatomy(i, fact('stoma', 'S1')), 'Y'),
            ('lesions', 64, lambda i: lesion(i, src('S1')), 'L'),
        )
        for name, limit, make, letter in rows:
            with self.subTest(top=name):
                label = 'anatomy entries' if name == 'anatomy' else name
                # the ids the worked example's references name are replaced: item-level findings, never a refusal
                self.at_and_past(objects(name, make, letter), limit,
                                 'it lists {n} ' + label + ', more than the {limit} this contract accepts')

    def test_the_other_dates_and_the_doubts(self):
        def other_dates(n):
            return changed(lambda v: v['encounter'].update(other_dates=[
                {'value': '2023', 'role': fact('other_occurrence', 'S4')}] * n))

        def doubts(n):
            return changed(lambda v: v.update(doubts=[doubt('status', ['E2'])] * n))

        self.at_and_past(other_dates, 16, 'encounter.other_dates lists {n} other dates, more than the {limit} this '
                                          'contract accepts')
        self.at_and_past(doubts, 64, 'doubts lists {n} doubts, more than the {limit} this contract accepts')

    def test_every_slot_holds_one_fact(self):
        for family, fields in xs.ATTRIBUTES.items():
            for field in fields:
                if field.arity is not xs.Arity.SLOT:
                    continue
                with self.subTest(slot=f'{family.value}.{field.attribute.value}'):
                    if field.values is not None:
                        value = list(field.values)[0].value
                    elif field.refers_to is not None:
                        value = {F.PERSON: 'P1', F.EVENT: 'E1', F.SESSION: 'X1', F.LESION: 'L1',
                                 F.ANATOMY: 'Y1'}[field.refers_to]
                    else:
                        value = '2023'
                    one = fact(value, 'S1')

                    def build(n, family=family, field=field, one=one):
                        result = answer()
                        result['anatomy'] = [anatomy('Y1', fact('stoma', 'S1'))]
                        holder = result['encounter'] if family is F.ENCOUNTER else result[family.value][0]
                        return put(holder, '.'.join(field.path), [copy.deepcopy(one) for _ in range(n)]) and result

                    where = 'encounter' if family is F.ENCOUNTER else f'{family.value}[0]'
                    self.at_and_past(build, 1, f'{where}.{field.attribute.value} lists {{n}} facts, more than the '
                                               '{limit} one slot may have')

    def test_every_list_of_facts_takes_its_bound(self):
        rows = (
            ('lesions', 0, 'places', 8, 'rectum', 'list of places'),
            ('events', 1, 'target.places', 8, 'rectum', 'list of target.places'),
            ('sessions', 0, 'reached', 8, 'cecum', 'list of reached'),
            ('sessions', 0, 'device_reached', 8, 'cecum', 'list of device_reached'),
            ('anatomy', 0, 'joins', 8, 'ileum', 'list of joins'),
            ('sessions', 0, 'stations', 7, 'colon', 'list of stations'),
            ('lesions', 0, 'distinct_from', 16, 'L2', 'list of distinct_from'),
            ('lesions', 0, 'same_as', 16, 'L2', 'list of same_as'),
        )
        for family, index, path, limit, value, owner in rows:
            with self.subTest(list=f'{family}.{path}'):
                def build(n, family=family, index=index, path=path, value=value):
                    result = answer()
                    result['anatomy'] = [anatomy('Y1', fact('anastomosis', 'S1'))]
                    return put(result[family][index], path, [fact(value, 'S1') for _ in range(n)]) and result

                self.at_and_past(build, limit, f'{family}[{index}].{path} lists {{n}} facts, more than the {{limit}} '
                                               f'one {owner} may have')

    def test_sources_options_restatements_and_scope_lists(self):
        base = 'events[1]'

        def kind_sources(n):
            return changed(lambda v: v['events'][1]['kind'].update(sources=[src('S6')] * n))

        def kind_options(n):
            return changed(lambda v: v['events'][1].update(kind=contradicted(
                *[(value, 'S6') for value in ('snare', 'emr', 'esd', 'removal', 'biopsy')[:n]])))

        def option_sources(n):
            value = changed(lambda v: v['events'][1].update(kind=contradicted(('snare', 'S6'), ('emr', 'S7'))))
            value['events'][1]['kind']['options'][0]['sources'] = [src('S6')] * n
            return value

        def dos_sources(n):
            return changed(lambda v: v['encounter']['date_of_service'].update(sources=[src('S2')] * n))

        def dos_options(n):
            dates = ('2026-11-09', '2026-11-08', '2026-11-07', '2026-11-06', '2026-11-05')
            return changed(lambda v: v['encounter'].update(date_of_service={
                'state': 'several', 'value': '', 'sources': [src('S2')],
                'options': [{'value': day, 'sources': [src('S2')]} for day in dates[:n]]}))

        def restatements(n):
            return changed(lambda v: v['events'][1].update(restatements=[{'units': ['S7'], 'role': 'summarizes'}] * n))

        self.at_and_past(kind_sources, 8, f'{base}.kind.sources lists {{n}} sources, more than the {{limit}} one fact '
                                          'may have')
        self.at_and_past(kind_options, 4, f'{base}.kind.options lists {{n}} options, more than the {{limit}} one fact '
                                          'may have')
        self.at_and_past(option_sources, 8, f'{base}.kind.options[0].sources lists {{n}} sources, more than the '
                                            '{limit} one option may have')
        self.at_and_past(dos_sources, 8, 'encounter.date_of_service.sources lists {n} sources, more than the {limit} '
                                         'one fact may have')
        self.at_and_past(dos_options, 4, 'encounter.date_of_service.options lists {n} options, more than the {limit} '
                                         'one fact may have')
        self.at_and_past(restatements, 16, f'{base}.restatements lists {{n}} restatements, more than the {{limit}} one '
                                           'event may have')
        for name, value in (('targets', 'L1'), ('segment', 'rectum'), ('covers', 'E1'), ('excepts', 'E1')):
            with self.subTest(scope=name):
                def build(n, name=name, value=value):
                    return changed(lambda v: v['events'][2]['scope'].update({name: [value] * n}))

                self.at_and_past(build, 32, f'events[2].scope.{name} lists {{n}} values, more than the {{limit}} one '
                                            'scope list may have')

    def test_the_doubts_objects_and_readings(self):
        self.at_and_past(lambda n: changed(lambda v: v['doubts'].append(doubt('status', ['E2'] * n))), 16,
                         'doubts[0].objects lists {n} ids, more than the {limit} one doubt may have')
        self.at_and_past(lambda n: changed(lambda v: v['doubts'].append(doubt('status', ['E2'],
                                                                              readings=['performed'] * n))), 4,
                         'doubts[0].readings lists {n} readings, more than the {limit} one doubt may have')

    def test_a_sections_closing_signatures_take_no_count_of_their_own(self):
        # triage 1b#1: 1.8 numbers no closing signatures (1.4 SECTION.end), so 1.9's worked example with nine on N3,
        # each citing S9, is read with no finding; the 8-source bound stays on every fact, option and date of service
        nine = self.accepted(changed(lambda v: v['sections'][3].update(end=[src('S9')] * 9)))
        self.assertEqual(self.findings(nine), [])
        self.assertEqual([citation.index for citation in nine.citations if citation.cited is xr.Cited.END],
                         list(range(9)))
        # the list stays bounded by the cited units of the whole answer, named by count
        cited = xr._cited(answer())

        def ends(n):
            return changed(lambda v: v['sections'][3].update(end=[src('S9')] * (n - cited)))

        self.at_and_past(ends, 4000, 'it cites {n} unit ids in all, more than the {limit} this contract accepts')
        # and each signature's words take the words bound
        self.refused(changed(lambda v: v['sections'][3].update(end=[src('S9')] * 8 + [src('S9', words='w' * 601)])),
                     'bounds', 'sections[3].end[8].words has 601 characters, more than the 600 one words value may '
                               'have')

    def test_every_words_value(self):
        def words(path, edit):
            def build(n):
                value = answer()
                edit(value, 'w' * n)
                return value
            self.at_and_past(build, 600, path + ' has {n} characters, more than the {limit} one words value may have')

        rows = {
            'events[1].kind.sources[0].words': lambda v, w: v['events'][1]['kind']['sources'][0].update(words=w),
            'events[1].anchor.kind_words': lambda v, w: v['events'][1]['anchor'].update(kind_words=w),
            'events[1].anchor.status_words': lambda v, w: v['events'][1]['anchor'].update(status_words=w),
            'people[0].name.words': lambda v, w: v['people'][0]['name'].update(words=w),
            'sections[1].start.words': lambda v, w: v['sections'][1]['start'].update(words=w),
            'lesions[0].description.words': lambda v, w: v['lesions'][0]['description'].update(words=w),
            'encounter.date_of_service.sources[0].words':
                lambda v, w: v['encounter']['date_of_service']['sources'][0].update(words=w),
        }
        for path, edit in rows.items():
            with self.subTest(words=path):
                words(path, edit)

    def test_the_unit_ids_cited_in_the_whole_answer(self):
        cited = xr._cited(answer())
        self.assertEqual(cited, 65)  # the worked example's own citations, every list of unit ids counted

        def build(n):
            return changed(lambda v: v['doubts'].append(doubt('status', ['E2'], units=['S6'] * (n - cited))))

        self.at_and_past(build, 4000, 'it cites {n} unit ids in all, more than the {limit} this contract accepts')

    def test_a_top_level_bound_is_named_before_an_item_bound(self):
        value = answer()
        value['events'][1]['kind']['sources'] = [src('S6')] * 9
        value['people'] = [{'id': f'V{i}', 'name': src('S1'), 'role': fact('other', 'S1')} for i in range(17)]
        value['encounter']['documenting_clinician'] = []
        self.assertEqual(self.read(value).reason, f'{REFUSED}it lists 17 people, more than the 16 this contract '
                                                  'accepts.')


class SourceUnitsTests(ReadTestCase):
    """[R:CO-5]: a source or an anchor over 12 units fails its own check; the answer is never refused for it."""

    def test_a_source_of_13_units_is_read_with_source_too_long(self):
        long, twelve = [f'S{i}' for i in range(1, 14)], [f'S{i}' for i in range(1, 13)]
        at = key(F.EVENT, 'E2', A.KIND)
        self.assertEqual(self.reasons(changed(lambda v: v['events'][1]['kind'].update(sources=[src(*twelve)])), at, 20),
                         ())
        result = self.accepted(changed(lambda v: v['events'][1]['kind'].update(sources=[src(*long)])), 20)
        self.assertEqual(result.fact(at).reasons, (LONG,))
        self.assertEqual([place for place, _ in self.findings(result)], [at])  # nothing else is touched

    def test_every_source_and_the_anchor_take_the_bound_but_a_restatement_does_not(self):
        long = [f'S{i}' for i in range(1, 14)]
        rows = {
            'an option': (lambda v: v['events'][1].update(kind=contradicted(('snare', *long), ('emr', 'S7'))),
                          key(F.EVENT, 'E2', A.KIND)),
            'the date of service': (lambda v: v['encounter']['date_of_service'].update(sources=[src(*long)]),
                                    key(F.ENCOUNTER, '', A.DATE_OF_SERVICE)),
            'an anchor': (lambda v: v['events'][1]['anchor'].update(units=long),
                          (F.EVENT, 'E2', xr.Cited.ANCHOR, 0)),
            'a start': (lambda v: v['sections'][1]['start'].update(units=long),
                        (F.SECTION, 'N1', xr.Cited.START, 0)),
            'an end': (lambda v: v['sections'][1].update(end=[src(*long)]), (F.SECTION, 'N1', xr.Cited.END, 0)),
            'a name': (lambda v: v['people'][0]['name'].update(units=long), (F.PERSON, 'P1', xr.Cited.NAME, 0)),
            'a description': (lambda v: v['lesions'][0]['description'].update(units=long),
                              (F.LESION, 'L1', xr.Cited.DESCRIPTION, 0)),
        }
        for name, (edit, place) in rows.items():
            with self.subTest(source=name):
                self.assertEqual(self.findings(self.accepted(changed(edit), 20)), [(place, (LONG,))])
        restated = changed(lambda v: v['events'][1].update(restatements=[{'units': long, 'role': 'restates'}]))
        self.assertEqual(self.findings(self.accepted(restated, 20)), [])


class IdStageTests(ReadTestCase):
    """DECISIONS D185: one grammar - a family's letter, then its number in canonical decimal digits - for every object
    id, every id-valued reference and option, every member of an id list, every object a doubt names and every cited
    unit id. A breach refuses the whole answer at stage ids, named by its path; where a well-formed id leads is
    item-level (I4, I1)."""

    NOT_IDS = ('', 'E', 'E01', 'E00', 'e2', 'E 2', ' E2', 'E2 ', 'E2\n', 'E+2', 'E-2', 'E2.0', 'E²', 'E٢', 'Ｅ2', 'E１',
               'EE2', '2', 'E1234567890', 'K1', MODEL_TEXT)

    def test_an_object_id_is_its_familys_letter_and_number(self):
        for bad in self.NOT_IDS + ('X2', 'S2', 'L2'):
            with self.subTest(id=bad):
                self.refused(changed(lambda v: v['events'][1].update(id=bad)), 'ids',
                             f'events[1].id is not an id of events: the letter E {DIGITS}')
        for good in ('E0', 'E7', 'E10', 'E999999999'):
            with self.subTest(id=good):
                self.assertEqual(self.findings(self.accepted(changed(lambda v: v['events'][1].update(id=good)))), [])
        rows = (  # another family's well-formed id, as an object's own id: each family takes its own letter only
            ('people', 1, 'N2', 'people', 'P'), ('sections', 2, 'P2', 'sections', 'N'),
            ('sessions', 0, 'E1', 'sessions', 'X'), ('lesions', 0, 'Y1', 'lesions', 'L'),
            ('events', 4, 'L5', 'events', 'E'),
        )
        for family, index, value, what, letter in rows:
            with self.subTest(family=family):
                self.refused(changed(lambda v: v[family][index].update(id=value)), 'ids',
                             f'{family}[{index}].id is not an id of {what}: the letter {letter} {DIGITS}')
        self.refused(changed(lambda v: v['anatomy'].append(anatomy('L1', fact('stoma', 'S1')))), 'ids',
                     f'anatomy[0].id is not an id of anatomy entries: the letter Y {DIGITS}')

    def test_an_id_is_unique_in_its_family_and_no_two_families_share_one(self):
        self.refused(changed(lambda v: v['events'][2].update(id='E2')), 'ids',
                     'two events share one id (events[1] and events[2])')
        self.refused(changed(lambda v: v['anatomy'].extend([anatomy('Y1', fact('stoma', 'S1'))] * 2)), 'ids',
                     'two anatomy entries share one id (anatomy[0] and anatomy[1])')
        # a lesion filed under an event's id is no lesion id: two families can no longer share an id (triage 1b dev 6)
        self.refused(changed(lambda v: v['lesions'][1].update(id='E6')), 'ids',
                     f'lesions[1].id is not an id of lesions: the letter L {DIGITS}')

    def test_every_id_valued_reference_has_the_shape(self):
        def option(path, *sides):  # a contradicted reference, the second side malformed
            return lambda v: put(v['events'][1], path, [contradicted(*sides)])

        rows = {
            'encounter.documenting_clinician[0].value':
                lambda v: v['encounter']['documenting_clinician'][0].update(value='P01'),
            'sections[2].performer_person[0].value': lambda v: v['sections'][2].update(performer_person=[fact('p1',
                                                                                                             'S5')]),
            'sessions[0].examination[0].value': lambda v: v['sessions'][0]['examination'][0].update(value='E 1'),
            'sessions[0].through[0].value': lambda v: v['sessions'][0].update(through=[fact('Y+1', 'S5')]),
            'sessions[0].reached_anatomy[0].value': lambda v: v['sessions'][0].update(reached_anatomy=[fact('Y1.0',
                                                                                                           'S5')]),
            'sessions[0].part_of_session[0].value': lambda v: v['sessions'][0].update(part_of_session=[fact('X-1',
                                                                                                           'S5')]),
            'lesions[0].distinct_from[0].value': lambda v: v['lesions'][0].update(distinct_from=[fact('L٢', 'S6')]),
            'lesions[0].same_as[0].value': lambda v: v['lesions'][0].update(same_as=[fact('Ｌ2', 'S6')]),
            'events[1].session[0].value': lambda v: v['events'][1]['session'][0].update(value='session 1'),
            'events[1].performer_person[0].value': lambda v: v['events'][1].update(performer_person=[fact('P',
                                                                                                         'S6')]),
            'events[1].target.lesion[0].value': lambda v: v['events'][1]['target']['lesion'][0].update(value='L1 '),
            'events[1].target.anatomy[0].value': lambda v: v['events'][1]['target'].update(anatomy=[fact('Y0001',
                                                                                                        'S6')]),
            'events[1].cause_event[0].value': lambda v: v['events'][1].update(cause_event=[fact('S6', 'S6')]),
            'events[1].part_of[0].value': lambda v: v['events'][1].update(part_of=[fact('K1', 'S6')]),
            'events[1].session[0].options[1].value': option('session', ('X1', 'S6'), ('X02', 'S6')),
            'events[1].part_of[0].options[0].value': option('part_of', ('', 'S6'), ('E1', 'S6')),  # never ''
            'events[2].scope.targets[1]': lambda v: v['events'][2]['scope'].update(targets=['L1', 'L 2']),
            'events[2].scope.covers[0]': lambda v: v['events'][2]['scope'].update(covers=['E1234567890']),
            'events[2].scope.excepts[0]': lambda v: v['events'][2]['scope'].update(excepts=['']),
            'doubts[0].objects[1]': lambda v: v['doubts'].append(doubt('status', ['E2', 'e2'])),
        }
        for path, edit in rows.items():
            with self.subTest(reference=path):
                self.refused(changed(edit), 'ids', f'{path} is not an id: {ANY_OBJECT}')

    def test_a_well_formed_id_leads_where_it_leads_item_by_item(self):
        # an id of no object, or of an object of another family, is I4's; a unit the revision lacks is I1's; the empty
        # value of a fact is S2's, and a contradicted reference's empty value is its own (1.3)
        at = key(F.EVENT, 'E2', A.SESSION)
        for value in ('X9', 'L1', 'E2', 'N0', 'P1', 'Y0'):
            with self.subTest(reference=value):
                self.assertEqual(self.reasons(changed(lambda v: v['events'][1]['session'][0].update(value=value)), at),
                                 (REF,))
        self.assertEqual(self.reasons(changed(lambda v: v['events'][1]['session'][0].update(value='')), at), (SHAPE,))
        sides = self.accepted(changed(lambda v: v['events'][1].update(session=[contradicted(('X1', 'S6'),
                                                                                            ('L1', 'S7'))])))
        self.assertEqual((sides.fact(at).reasons, sides.fact(at).sides), ((REF,), ((), (REF,))))
        for unit in ('S0', 'S10', 'S999999999'):
            with self.subTest(unit=unit):
                self.assertEqual(self.reasons(changed(lambda v: v['events'][1]['kind']['sources'][0].update(
                    units=[unit])), key(F.EVENT, 'E2', A.KIND)), (UNIT,))
        named = self.accepted(changed(lambda v: v['doubts'].append(doubt('status', ['E77'])))).doubts[0]
        self.assertEqual((named.malformed, named.reasons), (True, (REF,)))

    def test_every_cited_unit_id_has_the_shape(self):
        def several(v):
            v['encounter']['date_of_service'] = {
                'state': 'several', 'value': '', 'sources': [src('S2')],
                'options': [{'value': '2026-11-09', 'sources': [src('S2')]},
                            {'value': '2026-11-08', 'sources': [src('S02')]}]}

        def side(v):
            v['events'][1]['kind'] = contradicted(('snare', 'S6'), ('emr', 'S7'))
            v['events'][1]['kind']['options'][1]['sources'][0]['units'] = ['s7']

        rows = {
            'encounter.date_of_service.sources[0].units[0]':
                lambda v: v['encounter']['date_of_service']['sources'][0].update(units=['S02']),
            'encounter.date_of_service.options[1].sources[0].units[0]': several,
            'encounter.other_dates[0].role.sources[0].units[0]':
                lambda v: v['encounter']['other_dates'][0]['role']['sources'][0].update(units=['P1']),
            'encounter.documenting_clinician[0].sources[0].units[0]':
                lambda v: v['encounter']['documenting_clinician'][0]['sources'][0].update(units=['S3 ']),
            'people[1].name.units[0]': lambda v: v['people'][1]['name'].update(units=['']),
            'sections[2].start.units[1]': lambda v: v['sections'][2]['start'].update(units=['S5', 'S5a']),
            'sections[2].end[0].units[0]': lambda v: v['sections'][2].update(end=[src('[S9]')]),
            'lesions[1].description.units[0]': lambda v: v['lesions'][1]['description'].update(units=['S٨']),
            'events[0].anchor.units[1]': lambda v: v['events'][0]['anchor'].update(units=['S5', 'Ｓ5']),
            'events[0].restatements[0].units[0]': lambda v: v['events'][0].update(restatements=[
                {'units': ['S+5'], 'role': 'title'}]),
            'events[1].kind.sources[0].units[0]': lambda v: v['events'][1]['kind']['sources'][0].update(units=['S06']),
            'events[1].kind.options[1].sources[0].units[0]': side,
            'events[5].date[0].sources[0].units[0]': lambda v: v['events'][5]['date'][0]['sources'][0].update(
                units=['S1234567890']),
            'doubts[0].units[0]': lambda v: v['doubts'].append(doubt('status', ['E2'], units=['S'])),
        }
        for path, edit in rows.items():
            with self.subTest(unit=path):
                self.refused(changed(edit), 'ids', f'{path} is not a unit id: {A_UNIT}')

    def test_the_first_breach_is_named_object_ids_first_then_in_the_answers_order(self):
        both = changed(lambda v: [v['events'][0]['anchor'].update(units=['s5']), v['events'][1].update(id='E02')])
        self.assertEqual(self.read(both).reason, f'{REFUSED}events[1].id is not an id of events: the letter E '
                                                 f'{DIGITS}.')
        order = changed(lambda v: [v['doubts'].append(doubt('status', ['e2'])),
                                   v['events'][1]['session'][0].update(value='x1'),
                                   v['people'][0]['name'].update(units=['s3'])])
        self.assertEqual(self.read(order).reason, f'{REFUSED}people[0].name.units[0] is not a unit id: {A_UNIT}.')
        order['people'][0]['name']['units'] = ['S3']
        self.assertEqual(self.read(order).reason, f'{REFUSED}events[1].session[0].value is not an id: {ANY_OBJECT}.')
        order['events'][1]['session'][0]['value'] = 'X1'
        self.assertEqual(self.read(order).reason, f'{REFUSED}doubts[0].objects[0] is not an id: {ANY_OBJECT}.')

    @hypothesis.settings(max_examples=600, deadline=None)
    @hypothesis.given(st.one_of(st.text(alphabet=st.sampled_from('EXNLYPSeK0123456789 +-.²٢１'), max_size=12),
                                st.builds(lambda letter, zeros, number: f'{letter}{"0" * zeros}{number}',
                                          st.sampled_from('EXNLYPSK'), st.integers(min_value=0, max_value=2),
                                          st.integers(min_value=0, max_value=10 ** 10))),
                      st.sampled_from(['E', 'X', 'S', 'PNXYLE', '']))
    @hypothesis.example('E01', 'E')  # the defect 0b#4 names: it passed v1's shape and failed at the FactSet
    @hypothesis.example('E00', 'PNXYLE')
    @hypothesis.example('S999999999', 'S')  # nine digits, the longest number admitted
    @hypothesis.example('S1000000000', 'S')  # ten
    @hypothesis.example('N0', 'PNXYLE')
    def test_the_grammar_is_d185s_the_stores_and_the_engines(self, value, letters):
        from studio.interpretation import store  # 1d's reader, read only: the parity this ruling restores
        from studio.interpretation.engine import types as et
        admitted = xr.is_id(value, letters)
        self.assertEqual(admitted, len(value) > 1 and value[0] in letters and bool(GRAMMAR.fullmatch(value[1:])))
        self.assertEqual(admitted, store._v2_id(value, tuple(letters)))
        if admitted:  # the defect D185 closes: an id the reader admits always reaches the engine as itself
            parsed = et.Id.parse(value)
            self.assertEqual((parsed.family.value, str(parsed)), (value[0], value))
        self.assertEqual(xr.OBJECT_LETTERS, 'PNXYLE')
        self.assertEqual(xr.UNIT_LETTER, 'S')


class DateStageTests(ReadTestCase):
    def test_the_date_of_service_is_empty_or_a_day(self):
        def dos(value, state='stated'):
            return changed(lambda v: v['encounter']['date_of_service'].update(value=value, state=state))

        for bad in ('2026-02-30', '2026-11', '2026', '11/09/2026', '2026-11-9', '０２６-11-09'):
            with self.subTest(value=bad):
                self.refused(dos(bad), 'schema', 'a date is not YYYY-MM-DD (encounter.date_of_service.value)')
        self.accepted(dos('2024-02-29'))
        self.accepted(changed(lambda v: v['encounter'].update(date_of_service={
            'state': 'not_stated', 'value': '', 'sources': [], 'options': []})))
        several = {'state': 'several', 'value': '', 'sources': [src('S2')],
                   'options': [{'value': '2026-11-09', 'sources': [src('S2')]},
                               {'value': '', 'sources': [src('S2')]}]}
        self.refused(changed(lambda v: v['encounter'].update(date_of_service=several)), 'schema',
                     'a date is not YYYY-MM-DD (encounter.date_of_service.options[1].value)')

    def test_other_dates_and_act_dates_at_their_precision(self):
        for good in ('2023', '2023-04', '2023-04-05', ''):
            with self.subTest(other=good):
                self.accepted(changed(lambda v: v['encounter']['other_dates'][0].update(value=good)))
                self.accepted(changed(lambda v: v['events'][5]['date'][0].update(value=good)))
        for bad in ('23', '2023-4', '2023-13', '0000', '2023-04-31', 'in 2023'):
            with self.subTest(other=bad):
                self.refused(changed(lambda v: v['encounter']['other_dates'][0].update(value=bad)), 'schema',
                             'a date is not YYYY-MM-DD, YYYY-MM or YYYY (encounter.other_dates[0].value)')
                self.refused(changed(lambda v: v['events'][5]['date'][0].update(value=bad)), 'schema',
                             'a date is not YYYY-MM-DD, YYYY-MM or YYYY (events[5].date[0].value)')
        self.refused(changed(lambda v: v['events'][5].update(date=[contradicted(('2023', 'S4'), ('', 'S4'))])),
                     'schema', 'a date is not YYYY-MM-DD, YYYY-MM or YYYY (events[5].date[0].options[1].value)')

    @hypothesis.settings(max_examples=500, deadline=None)
    @hypothesis.given(st.one_of(st.text(alphabet=st.sampled_from('0123456789-٣２'), max_size=11),
                                st.dates().map(lambda day: day.isoformat()),
                                st.dates().map(lambda day: day.isoformat()[:7]),
                                st.dates().map(lambda day: day.isoformat()[:4])))
    def test_the_date_shapes_are_v1s(self, value):
        self.assertEqual(xr.iso_date(value), v1_read.iso_date(value))
        self.assertEqual(xr.partial_date(value), v1_read.partial_date(value))


class OrderTests(ReadTestCase):
    def test_the_first_failing_step_refuses_the_whole_answer(self):
        both = answer()
        both['events'][1]['kind']['sources'] = [src('S6')] * 9  # a bound
        both['events'][2]['id'] = 'E2'  # and a repeated id
        self.assertEqual(self.read(both).stage, 'bounds')
        ids = answer()
        ids['events'][2]['id'] = 'E2'
        ids['encounter']['date_of_service']['value'] = '2026-02-30'
        self.assertEqual(self.read(ids).stage, 'ids')
        schema_first = answer()
        schema_first['events'][1]['kind']['state'] = 'ambiguous'
        schema_first['events'][1]['kind']['sources'] = [src('S6')] * 9
        self.assertEqual(self.read(schema_first).stage, 'schema')
        self.assertEqual(self.read(text(answer())[:-1]).stage, 'json')
        dates = answer()
        dates['encounter']['date_of_service']['value'] = '2026-02-30'
        dates['events'][1]['kind']['sources'] = [src('S99', 'S100')]  # item-level: never reached
        self.assertEqual(self.read(dates).reason, f'{REFUSED}a date is not YYYY-MM-DD '
                                                  '(encounter.date_of_service.value).')


class WordingTests(ReadTestCase):
    def test_no_refusal_repeats_the_models_text(self):
        planted = {
            'a words value too long': changed(lambda v: v['events'][1]['kind']['sources'][0].update(
                words=MODEL_TEXT * 30)),
            'an id that is not one': changed(lambda v: v['events'][1].update(id=MODEL_TEXT + ' NOT AN ID')),
            'an id that is not one, repeated': changed(lambda v: [item.update(id=MODEL_TEXT) for item in
                                                                  v['events'][:2]]),
            'a reference that is not an id': changed(lambda v: v['events'][1]['session'][0].update(value=MODEL_TEXT)),
            'a unit id that is not one': changed(lambda v: v['events'][1]['kind']['sources'][0].update(
                units=[MODEL_TEXT])),
            "a doubt's object that is not an id": changed(lambda v: v['doubts'].append(doubt('status', [MODEL_TEXT]))),
            'a date that is not one': changed(lambda v: v['encounter']['date_of_service'].update(value=MODEL_TEXT)),
            'an enumeration value': changed(lambda v: v['events'][1]['kind'].update(value=MODEL_TEXT)),
            'a field the schema lacks': changed(lambda v: v['events'][1].update({MODEL_TEXT: ''})),
        }
        for name, value in planted.items():
            with self.subTest(planted=name):
                result = self.read(value)
                self.assertIsInstance(result, xr.Refusal)
                for piece in (MODEL_TEXT, MODEL_TEXT[:12]):
                    self.assertNotIn(piece, result.reason)
        broken = text(answer()).replace('"S7"', f'"{MODEL_TEXT}" "S7"', 1)
        self.assertNotIn(MODEL_TEXT, self.read(broken).reason)  # a JSON error names a position only


# --- the Refusal, the pin and the unit count --------------------------------------------------------------------------


class RefusalTests(SimpleTestCase):
    def test_the_refusal_is_v1s(self):
        self.assertEqual(xr.STAGES, v1_read.STAGES)
        self.assertEqual(xr.REFUSED, v1_read.REFUSED)
        self.assertEqual([f.name for f in dataclasses.fields(xr.Refusal)],
                         [f.name for f in dataclasses.fields(v1_read.Refusal)])
        made = xr.refuse('envelope', 'the answer ended at the output limit (MAX_TOKENS)')
        self.assertEqual(dataclasses.asdict(made), dataclasses.asdict(
            v1_read.refuse('envelope', 'the answer ended at the output limit (MAX_TOKENS)')))
        self.assertEqual(xr.refuse('json', 'it stops.').reason, f'{REFUSED}it stops.')
        cases = (('other', f'{REFUSED}why.', True), ('json', 'why.', True),
                 ('json', 'The reading was not used: the answer is not valid JSON.', True), ('json', f'{REFUSED}why', True),
                 ('json', f'{REFUSED}.', True), ('json', None, True), ('json', f'{REFUSED}why.', False),
                 ('bounds', f'{REFUSED}why.', True))
        for stage, reason, refused in cases:
            with self.subTest(stage=stage, reason=reason, refused=refused):
                outcomes = []
                for module in (v1_read, xr):
                    try:
                        module.Refusal(stage=stage, reason=reason, refused=refused)
                        outcomes.append('made')
                    except ValueError as exc:
                        outcomes.append(str(exc))
                self.assertEqual(outcomes[0], outcomes[1])
        with self.assertRaises(ValueError):
            xr.refuse('json', '')
        with self.assertRaises(dataclasses.FrozenInstanceError):
            made.stage = 'json'


class PinTests(SimpleTestCase):
    def test_no_answer_is_read_before_the_pin_is_written(self):
        with mock.patch.object(interpretation, 'LOCAL_SCHEMA_SHA256_V2', ''):  # step 0b's placeholder
            with self.assertRaisesRegex(RuntimeError, 'has no pin yet'):
                xr.read(text(answer()), UNITS)
        # the placeholder holds nothing or exactly this schema's sha: the integration owner writes it (2.5)
        self.assertIn(interpretation.LOCAL_SCHEMA_SHA256_V2, ('', jsonschema.sha256_of(xs.LOCAL_SCHEMA_2)))

    def test_an_answer_is_read_only_under_the_local_schemas_pin(self):
        pin = jsonschema.sha256_of(xs.LOCAL_SCHEMA_2)
        with mock.patch.object(interpretation, 'LOCAL_SCHEMA_SHA256_V2', pin):
            self.assertIsInstance(xr.read(text(answer()), UNITS), xr.ReadAnswer)  # the positive control
            changed_schema = copy.deepcopy(xs.LOCAL_SCHEMA_2)
            changed_schema['properties']['doubts']['items']['properties']['about']['enum'].append('time')
            with mock.patch.object(xs, 'LOCAL_SCHEMA_2', changed_schema):
                with self.assertRaisesRegex(RuntimeError, 'needs a new INTERPRETATION_VERSION'):
                    xr.read(text(answer()), UNITS)
            self.assertIsInstance(xr.read(text(answer()), UNITS), xr.ReadAnswer)  # nothing was left changed


class UnitCountTests(ReadTestCase):
    def test_the_unit_ids_that_exist(self):
        for value in ('S1', 'S9'):
            self.assertTrue(xr.unit_known(value, 9), value)
        for value in ('S0', 'S10', 'S01', 's1', 'S', '', 'S-1', 'S1 ', ' S1', 'S１', 'S٣', 'P1', 'S+1', 'S1.0',
                      'S' + '9' * 5000):
            self.assertFalse(xr.unit_known(value, 9), value)
        self.assertFalse(xr.unit_known('S1', 0))
        self.assertTrue(xr.unit_known('S181', 181))  # GI Note #8's count under 1.2's rule (FINAL-V2 1.2)

    def test_the_count_must_be_a_whole_number(self):
        for bad in (-1, 1.0, True, '9', None):
            with self.subTest(count=bad):
                with self.assertRaises(ValueError):
                    xr.read(text(answer()), bad)

    def test_a_unit_past_the_count_is_unknown(self):
        self.assertEqual(self.findings(self.accepted(answer(), units=9)), [])
        found = self.findings(self.accepted(answer(), units=8))  # S9 no longer exists
        self.assertEqual(found, [(key(F.EVENT, 'E5', A.KIND), (UNIT,)), (key(F.EVENT, 'E5', A.STATUS), (UNIT,)),
                                 (key(F.EVENT, 'E5', A.TECHNIQUE_DEVICE), (UNIT,)),
                                 ((F.EVENT, 'E5', xr.Cited.ANCHOR, 0), (UNIT,))])


# --- S2: the fact's and the date of service's shapes ------------------------------------------------------------------


class FactShapeTests(ReadTestCase):
    def test_each_fact_shape_breach_is_shape_inconsistent_and_the_value_stays(self):
        at = key(F.EVENT, 'E2', A.KIND)
        rows = {
            'supported with no value': lambda v: v['events'][1]['kind'].update(value=''),
            'negated with no value': lambda v: v['events'][1]['kind'].update(value='', state='negated'),
            'supported with no source': lambda v: v['events'][1]['kind'].update(sources=[]),
            'supported with an option': lambda v: v['events'][1]['kind'].update(
                options=[{'value': 'emr', 'sources': [src('S6')]}]),
            'contradicted with a value': lambda v: v['events'][1].update(kind={
                **contradicted(('snare', 'S6'), ('emr', 'S7')), 'value': 'snare'}),
            'contradicted with one option': lambda v: v['events'][1].update(kind=contradicted(('snare', 'S6'))),
            'contradicted with one value twice': lambda v: v['events'][1].update(kind=contradicted(
                ('snare', 'S6'), ('snare', 'S7'))),
            'contradicted with no source of its own': lambda v: v['events'][1].update(kind={
                **contradicted(('snare', 'S6'), ('emr', 'S7')), 'sources': []}),
            'a source citing no unit': lambda v: v['events'][1]['kind'].update(sources=[src()]),
        }
        for name, edit in rows.items():
            with self.subTest(shape=name):
                value = changed(edit)
                result = self.accepted(value)
                self.assertEqual(self.findings(result), [(at, (SHAPE,))])
                self.assertEqual(result.fact(at).fact, typed(value['events'][1]['kind']))  # as written

    def test_a_side_carries_its_own_findings(self):
        value = changed(lambda v: v['events'][1].update(kind=contradicted(('snare', 'S6'), ('emr', 'S7'))))
        good = self.accepted(value).fact(key(F.EVENT, 'E2', A.KIND))
        self.assertEqual((good.reasons, good.sides), ((), ((), ())))
        value['events'][1]['kind']['options'][1]['sources'] = []
        value['events'][1]['kind']['options'][0]['sources'][0]['units'] = ['S77']
        read = self.accepted(value).fact(key(F.EVENT, 'E2', A.KIND))
        self.assertEqual(read.sides, ((UNIT,), (SHAPE,)))
        self.assertEqual(read.reasons, (SHAPE, UNIT))

    def test_the_date_of_service_by_its_own_states(self):
        at = key(F.ENCOUNTER, '', A.DATE_OF_SERVICE)

        def dos(**node):
            whole = {'state': 'stated', 'value': '2026-11-09', 'sources': [src('S2')], 'options': []}
            whole.update(node)
            return changed(lambda v: v['encounter'].update(date_of_service=whole))

        two = [{'value': '2026-11-09', 'sources': [src('S2')]}, {'value': '2026-11-08', 'sources': [src('S2')]}]
        self.assertEqual(self.reasons(dos(state='several', value='', options=two), at), ())
        self.assertEqual(self.reasons(dos(state='not_stated', value='', sources=[]), at), ())
        bad = {
            'stated with no value': dos(value=''),
            'stated with no source': dos(sources=[]),
            'stated with options': dos(options=two),
            'several with a value': dos(state='several', options=two),
            'several with one date': dos(state='several', value='', options=two[:1]),
            'several with one date twice': dos(state='several', value='', options=[two[0], two[0]]),
            'several with no source': dos(state='several', value='', sources=[], options=two),
            'not stated with a source': dos(state='not_stated', value=''),
            'not stated with options': dos(state='not_stated', value='', sources=[], options=two),
        }
        for name, value in bad.items():
            with self.subTest(dos=name):
                self.assertEqual(self.reasons(value, at), (SHAPE,))
        sideless = dos(state='several', value='', options=[two[0], {'value': '2026-11-08', 'sources': []}])
        self.assertEqual(self.accepted(sideless).fact(at).sides, ((), (SHAPE,)))


# --- I1: unit ids ------------------------------------------------------------------------------------------------------


class UnitIdTests(ReadTestCase):
    def test_an_unknown_unit_anywhere_is_unit_unknown_where_it_is(self):
        # every unit id here is well formed (D185): only where it leads is in doubt, and that is I1's, item by item
        rows = {
            'a fact': (lambda v: v['events'][1]['kind']['sources'][0].update(units=['S10']),
                       key(F.EVENT, 'E2', A.KIND)),
            'an option': (lambda v: v['events'][1].update(kind=contradicted(('snare', 'S6'), ('emr', 'S70'))),
                          key(F.EVENT, 'E2', A.KIND)),
            'the date of service': (lambda v: v['encounter']['date_of_service']['sources'][0].update(units=['S0']),
                                    key(F.ENCOUNTER, '', A.DATE_OF_SERVICE)),
            'an other date': (lambda v: v['encounter']['other_dates'][0]['role']['sources'][0].update(units=['S99']),
                              key(F.ENCOUNTER, '', A.OTHER_DATES_ROLE)),
            'a name': (lambda v: v['people'][1]['name'].update(units=['S0']), (F.PERSON, 'P2', xr.Cited.NAME, 0)),
            'a start': (lambda v: v['sections'][2]['start'].update(units=['S5', 'S55']),
                        (F.SECTION, 'N2', xr.Cited.START, 0)),
            'an end': (lambda v: v['sections'][2].update(end=[src('S19')]), (F.SECTION, 'N2', xr.Cited.END, 0)),
            'a description': (lambda v: v['lesions'][1]['description'].update(units=['S10']),
                              (F.LESION, 'L2', xr.Cited.DESCRIPTION, 0)),
            'an anchor': (lambda v: v['events'][0]['anchor'].update(units=['S5', 'S50']),
                          (F.EVENT, 'E1', xr.Cited.ANCHOR, 0)),
            'a restatement': (lambda v: v['events'][0].update(restatements=[{'units': ['S11'], 'role': 'title'}]),
                              (F.EVENT, 'E1', xr.Cited.RESTATEMENT, 0)),
        }
        for name, (edit, place) in rows.items():
            with self.subTest(unit=name):
                self.assertEqual(self.findings(self.accepted(changed(edit))), [(place, (UNIT,))])
        unknown = changed(lambda v: v['doubts'].append(doubt('status', ['E2'], units=['S12'])))
        self.assertEqual(self.findings(self.accepted(unknown)), [(('doubt', 0), (UNIT,))])

    def test_a_citation_of_no_unit(self):
        rows = {
            'an anchor': (lambda v: v['events'][0]['anchor'].update(units=[]), (F.EVENT, 'E1', xr.Cited.ANCHOR, 0)),
            'a name': (lambda v: v['people'][0]['name'].update(units=[]), (F.PERSON, 'P1', xr.Cited.NAME, 0)),
            'an end': (lambda v: v['sections'][2].update(end=[src()]), (F.SECTION, 'N2', xr.Cited.END, 0)),
            'a restatement': (lambda v: v['events'][0].update(restatements=[{'units': [], 'role': 'title'}]),
                              (F.EVENT, 'E1', xr.Cited.RESTATEMENT, 0)),
        }
        for name, (edit, place) in rows.items():
            with self.subTest(citation=name):
                self.assertEqual(self.findings(self.accepted(changed(edit))), [(place, (SHAPE,))])
        # the opening part's start cites no unit (1.4); where a start sits is geometry's (G2, step 1c)
        self.assertEqual(self.findings(self.accepted(changed(lambda v: v['sections'][1]['start'].update(units=[])))),
                         [])


# --- I4: references, self references, cycles ----------------------------------------------------------------------------


class ReferenceTests(ReadTestCase):
    def test_every_id_names_an_object_of_its_family(self):
        rows = {
            'the documenting clinician': (lambda v: v['encounter']['documenting_clinician'][0].update(value='P9'),
                                          key(F.ENCOUNTER, '', A.DOCUMENTING_CLINICIAN)),
            "a section's performer": (lambda v: v['sections'][2].update(performer_person=[fact('E1', 'S5')]),
                                      key(F.SECTION, 'N2', A.PERFORMER_PERSON)),
            "a session's examination": (lambda v: v['sessions'][0]['examination'][0].update(value='X1'),
                                        key(F.SESSION, 'X1', A.EXAMINATION)),
            "a session's way through": (lambda v: v['sessions'][0].update(through=[fact('Y9', 'S5')]),
                                        key(F.SESSION, 'X1', A.THROUGH)),
            "a session's anatomy reached": (lambda v: v['sessions'][0].update(reached_anatomy=[fact('L1', 'S5')]),
                                            key(F.SESSION, 'X1', A.REACHED_ANATOMY)),
            "a session's parent": (lambda v: v['sessions'][0].update(part_of_session=[fact('X2', 'S5')]),
                                   key(F.SESSION, 'X1', A.PART_OF_SESSION)),
            'a distinct lesion': (lambda v: v['lesions'][0].update(distinct_from=[fact('L3', 'S6')]),
                                  key(F.LESION, 'L1', A.DISTINCT_FROM)),
            'the same lesion': (lambda v: v['lesions'][0].update(same_as=[fact('E2', 'S6')]),
                                key(F.LESION, 'L1', A.SAME_AS)),
            "an act's session (another family's id)": (lambda v: v['events'][1]['session'][0].update(value='L1'),
                                                       key(F.EVENT, 'E2', A.SESSION)),
            "an act's performer": (lambda v: v['events'][1].update(performer_person=[fact('P3', 'S6')]),
                                   key(F.EVENT, 'E2', A.PERFORMER_PERSON)),
            "an act's lesion": (lambda v: v['events'][1]['target']['lesion'][0].update(value='X1'),
                                key(F.EVENT, 'E2', A.TARGET_LESION)),
            "an act's anatomy": (lambda v: v['events'][1]['target'].update(anatomy=[fact('Y1', 'S6')]),
                                 key(F.EVENT, 'E2', A.TARGET_ANATOMY)),
            "an act's cause": (lambda v: v['events'][1].update(cause_event=[fact('E9', 'S6')]),
                               key(F.EVENT, 'E2', A.CAUSE_EVENT)),
            "an act's whole": (lambda v: v['events'][1].update(part_of=[fact('N2', 'S6')]),
                               key(F.EVENT, 'E2', A.PART_OF)),
        }
        for name, (edit, at) in rows.items():
            with self.subTest(reference=name):
                self.assertEqual(self.findings(self.accepted(changed(edit))), [(at, (REF,))])

    def test_a_scope_lists_ids(self):
        rows = {
            'targets': (['L1', 'L9'], 1), 'covers': (['E1', 'X1'], 1), 'excepts': (['E1', 'E3'], 1),
        }
        for name, (ids, bad) in rows.items():
            with self.subTest(scope=name):
                result = self.accepted(changed(lambda v: v['events'][2]['scope'].update({name: ids})))
                attribute = ct.Attribute(f'scope.{name}')
                self.assertEqual(self.findings(result), [(key(F.EVENT, 'E3', attribute, bad), (REF,))])
                self.assertEqual([m.value for m in result.members], ids)
        segment = self.accepted(changed(lambda v: v['events'][2]['scope'].update(segment=['rectum', 'cecum'])))
        self.assertEqual(self.findings(segment), [])
        self.assertEqual([m.value for m in segment.members], ['rectum', 'cecum'])

    def test_no_object_refers_to_itself(self):
        rows = {
            'part_of': (lambda v: v['events'][1].update(part_of=[fact('E2', 'S6')]), key(F.EVENT, 'E2', A.PART_OF)),
            'cause_event': (lambda v: v['events'][1].update(cause_event=[fact('E2', 'S6', state='negated')]),
                            key(F.EVENT, 'E2', A.CAUSE_EVENT)),
            'part_of_session': (lambda v: v['sessions'][0].update(part_of_session=[fact('X1', 'S5')]),
                                key(F.SESSION, 'X1', A.PART_OF_SESSION)),
            'distinct_from': (lambda v: v['lesions'][0].update(distinct_from=[fact('L1', 'S6')]),
                              key(F.LESION, 'L1', A.DISTINCT_FROM)),
            'same_as': (lambda v: v['lesions'][1].update(same_as=[fact('L2', 'S8')]), key(F.LESION, 'L2', A.SAME_AS)),
        }
        for name, (edit, at) in rows.items():
            with self.subTest(self_reference=name):
                self.assertEqual(self.findings(self.accepted(changed(edit))), [(at, (REF,))])
        for name in ('covers', 'excepts'):
            with self.subTest(self_reference=name):
                result = self.accepted(changed(lambda v: v['events'][2]['scope'].update({name: ['E3']})))
                self.assertEqual(self.findings(result), [(key(F.EVENT, 'E3', ct.Attribute(f'scope.{name}')), (REF,))])
        # an act's session names a session: the act's own id is an event's (D185), so it names no session at all
        self.assertEqual(self.findings(self.accepted(changed(lambda v: v['events'][1]['session'][0].update(
            value='E2')))), [(key(F.EVENT, 'E2', A.SESSION), (REF,))])

    def test_a_contradicted_reference_finds_its_side(self):
        value = changed(lambda v: v['events'][1].update(session=[contradicted(('X1', 'S6'), ('X7', 'S6'))]))
        read = self.accepted(value).fact(key(F.EVENT, 'E2', A.SESSION))
        self.assertEqual((read.reasons, read.sides), ((REF,), ((), (REF,))))

    def test_part_of_cause_event_and_part_of_session_are_acyclic(self):
        two = changed(lambda v: [v['events'][1].update(part_of=[fact('E5', 'S6')]),
                                 v['events'][4].update(part_of=[fact('E2', 'S8')])])
        self.assertEqual(self.findings(self.accepted(two)), [(key(F.EVENT, 'E2', A.PART_OF), (REF,)),
                                                             (key(F.EVENT, 'E5', A.PART_OF), (REF,))])
        three = changed(lambda v: [v['events'][0].update(cause_event=[fact('E2', 'S5')]),
                                   v['events'][1].update(cause_event=[fact('E5', 'S6')]),
                                   v['events'][4].update(cause_event=[fact('E1', 'S8')]),
                                   v['events'][5].update(cause_event=[fact('E1', 'S4')])])  # into the cycle only
        self.assertEqual(self.findings(self.accepted(three)), [(key(F.EVENT, 'E1', A.CAUSE_EVENT), (REF,)),
                                                               (key(F.EVENT, 'E2', A.CAUSE_EVENT), (REF,)),
                                                               (key(F.EVENT, 'E5', A.CAUSE_EVENT), (REF,))])
        sessions = changed(lambda v: [v['sessions'][0].update(part_of_session=[fact('X2', 'S5')]),
                                      v['sessions'].append(session('X2', fact('egd', 'S5'),
                                                                   part_of_session=[fact('X1', 'S5')]))])
        self.assertEqual(self.findings(self.accepted(sessions)), [(key(F.SESSION, 'X1', A.PART_OF_SESSION), (REF,)),
                                                                  (key(F.SESSION, 'X2', A.PART_OF_SESSION), (REF,))])

    def test_a_cycle_needs_supported_or_possible_edges(self):
        denied = changed(lambda v: [v['events'][1].update(part_of=[fact('E5', 'S6')]),
                                    v['events'][4].update(part_of=[fact('E2', 'S8', state='negated')])])
        self.assertEqual(self.findings(self.accepted(denied)), [])  # "E5 is not part of E2" closes no cycle
        chain = changed(lambda v: [v['events'][1].update(part_of=[fact('E5', 'S6')]),
                                   v['events'][4].update(part_of=[fact('E1', 'S8')])])
        self.assertEqual(self.findings(self.accepted(chain)), [])
        possible = changed(lambda v: [v['events'][1].update(part_of=[fact('E5', 'S6')]),
                                      v['events'][4].update(part_of=[contradicted(('E1', 'S8'), ('E2', 'S9'))])])
        read = self.accepted(possible)
        self.assertEqual(read.fact(key(F.EVENT, 'E5', A.PART_OF)).sides, ((), (REF,)))
        self.assertEqual(read.fact(key(F.EVENT, 'E2', A.PART_OF)).reasons, (REF,))


# --- S2: the doubt's shape [R:HO-1][R:CO-1] ---------------------------------------------------------------------------


READINGS = {  # a valid reading for each attribute an about value names, on the worked example
    (F.EVENT, 'status'): 'planned', (F.EVENT, 'kind'): 'emr', (F.SESSION, 'kind'): 'egd',
    (F.EVENT, 'session'): 'X1', (F.EVENT, 'date_relation'): 'earlier_date', (F.SECTION, 'date_relation'): 'later_date',
    (F.SESSION, 'date_relation'): 'separate_encounter', (F.EVENT, 'performer'): 'other_clinician',
    (F.SECTION, 'performer'): 'P2', (F.EVENT, 'entry'): 'nursing', (F.SECTION, 'entry'): 'nursing',
    (F.EVENT, 'target'): 'L2', (F.LESION, 'target'): 'rectum', (F.EVENT, 'technique'): 'hot_snare',
    (F.SESSION, 'technique'): 'transanal', (F.EVENT, 'purpose'): 'removal', (F.EVENT, 'cause'): 'spontaneous',
    (F.EVENT, 'part_of'): 'step_of', (F.SESSION, 'part_of'): 'X1', (F.EVENT, 'yield'): 'tissue',
    (F.EVENT, 'access_outcome'): 'failed', (F.SESSION, 'extent'): 'terminal_ileum', (F.SESSION, 'stations'): 'rectum',
    (F.SESSION, 'completion'): 'incomplete', (F.SESSION, 'approach'): 'oral', (F.ANATOMY, 'anatomy'): 'ileocolic',
    (F.LESION, 'identity'): 'group', (F.EVENT, 'visit'): 'total_time',
}
OBJECTS = {F.EVENT: 'E2', F.SESSION: 'X1', F.SECTION: 'N2', F.LESION: 'L1', F.ANATOMY: 'Y1', F.PERSON: 'P1'}


def with_doubt(*doubts) -> dict:
    value = answer()
    value['anatomy'] = [anatomy('Y1', fact('anastomosis', 'S5'))]
    value['doubts'] = list(doubts)
    return value


class DoubtTests(ReadTestCase):
    def test_a_well_formed_doubt_names_its_rows_attributes_and_changes_nothing(self):
        value = with_doubt(doubt('status', ['E2'], units=['S6', 'S7'], basis='stated', readings=['performed',
                                                                                                 'planned']))
        result = self.accepted(value)
        read = result.doubts[0]
        self.assertEqual((read.malformed, read.reasons, read.objects), (False, (), ((F.EVENT, 'E2'),)))
        self.assertEqual(read.doubt, ct.Doubt(ct.DoubtAbout.STATUS, ('E2',), ('S6', 'S7'), ct.DoubtBasis.STATED,
                                              ('performed', 'planned')))
        self.assertEqual(read.named(F.EVENT), (A.STATUS,))
        self.assertEqual(read.named(F.LESION), ())
        status = result.fact(key(F.EVENT, 'E2', A.STATUS))
        self.assertEqual((status.fact, status.reasons), (typed(value['events'][1]['status']), ()))  # value kept
        self.assertEqual(self.accepted(with_doubt()).facts, result.facts)  # the doubt touched no fact

    def test_every_about_value_on_every_family_that_carries_it(self):
        for about, row in xs.DOUBT_ATTRIBUTES.items():
            for family in row:
                if about in (ct.DoubtAbout.WHOLE, ct.DoubtAbout.DATE_OF_SERVICE):
                    continue
                with self.subTest(about=about.value, family=family.value):
                    reading = READINGS[(family, about.value)]
                    read = self.accepted(with_doubt(doubt(about.value, [OBJECTS[family]], readings=[reading])))
                    self.assertEqual(read.doubts[0].reasons, ())
                    self.assertEqual(read.doubts[0].named(family), row[family])

    def test_a_malformed_doubt_names_every_attribute_of_its_objects(self):
        every_event, every_lesion = xs.attributes(F.EVENT), xs.attributes(F.LESION)
        rows = {
            'an object that does not carry the attribute': (doubt('status', ['L1']), (SHAPE,), F.LESION,
                                                            every_lesion),
            'a reading that is no value of it': (doubt('status', ['E2'], readings=['not_done']), (SHAPE,), F.EVENT,
                                                 every_event),
            "a reading of another attribute's values": (doubt('kind', ['E2'], readings=['colonoscopy']), (SHAPE,),
                                                        F.EVENT, every_event),
            'an id reading naming no session': (doubt('session', ['E2'], readings=['X9']), (SHAPE,), F.EVENT,
                                                every_event),
            "an id reading of another family's": (doubt('session', ['E2'], readings=['L1']), (SHAPE,), F.EVENT,
                                                  every_event),
            'a date reading that is no date': (doubt('date_relation', ['E6'], readings=['2023-13']), (SHAPE,),
                                               F.EVENT, every_event),
            'no unit': (doubt('status', ['E2'], units=[]), (SHAPE,), F.EVENT, every_event),
            'an unknown unit': (doubt('status', ['E2'], units=['S99']), (UNIT,), F.EVENT, every_event),
            'an object that names nothing, beside one that resolves': (doubt('status', ['E2', 'E77']), (REF,),
                                                                       F.EVENT, every_event),
        }
        for name, (node, reasons, family, named) in rows.items():
            with self.subTest(doubt=name):
                read = self.accepted(with_doubt(node)).doubts[0]
                self.assertEqual((read.malformed, read.reasons), (True, reasons))
                self.assertEqual(read.named(family), named)
                self.assertEqual(len(named), len(xs.ATTRIBUTES[family]))

    def test_a_doubt_that_names_no_object(self):
        nothing = self.accepted(with_doubt(doubt('status', []))).doubts[0]
        self.assertEqual((nothing.malformed, nothing.reasons, nothing.objects), (True, (SHAPE,), ()))
        unknown = self.accepted(with_doubt(doubt('status', ['E77']))).doubts[0]
        self.assertEqual((unknown.malformed, unknown.reasons, unknown.objects), (True, (REF,), ()))

    def test_a_named_id_resolves_to_the_one_family_its_letter_names(self):
        # D185: every object id opens with its family's letter, so no id is borne by two families and a doubt's object
        # resolves to one family at most (triage 1b dev 6); an id outside the grammar never reaches I4
        read = self.accepted(with_doubt(doubt('whole', ['L2', 'E5', 'X1', 'N3', 'P2', 'Y1', 'L2']))).doubts[0]
        self.assertEqual((read.malformed, read.reasons), (False, ()))
        self.assertEqual(read.objects, ((F.LESION, 'L2'), (F.EVENT, 'E5'), (F.SESSION, 'X1'), (F.SECTION, 'N3'),
                                        (F.PERSON, 'P2'), (F.ANATOMY, 'Y1')))  # each once, in the order named
        self.assertEqual([family.letter for family, name in read.objects], [name[0] for _, name in read.objects])
        self.refused(with_doubt(doubt('whole', ['K1'])), 'ids', f'doubts[0].objects[0] is not an id: {ANY_OBJECT}')

    def test_the_date_of_service_is_the_encounters(self):
        alone = self.accepted(with_doubt(doubt('date_of_service', [], units=['S2'], readings=['2026-11-09',
                                                                                              '2026-11-08'])))
        read = alone.doubts[0]
        self.assertEqual((read.malformed, read.objects), (False, ((F.ENCOUNTER, ''),)))
        self.assertEqual(read.named(F.ENCOUNTER), (A.DATE_OF_SERVICE,))
        named = self.accepted(with_doubt(doubt('date_of_service', ['E2'], units=['S2']))).doubts[0]
        self.assertEqual((named.malformed, named.reasons, named.objects),
                         (True, (SHAPE,), ((F.EVENT, 'E2'), (F.ENCOUNTER, ''))))
        self.assertEqual(named.named(F.ENCOUNTER), xs.attributes(F.ENCOUNTER))
        self.assertEqual(named.named(F.EVENT), xs.attributes(F.EVENT))
        bad = self.accepted(with_doubt(doubt('date_of_service', [], units=['S2'], readings=['today']))).doubts[0]
        self.assertTrue(bad.malformed)

    def test_a_date_of_service_reading_is_a_day(self):
        # triage 1b#2, DECISIONS D200: the date of service admits only a day (1.4; S1), so a month or a year is no
        # reading of it, and the doubt is malformed: it names every fact of the encounter (fail-closed)
        for readings in (['2026-11', '2026-11-09'], ['2026'], ['2026-11-09', '2026-11']):
            with self.subTest(readings=readings):
                read = self.accepted(with_doubt(doubt('date_of_service', [], units=['S2'], basis='unclear',
                                                      readings=readings))).doubts[0]
                self.assertEqual((read.malformed, read.reasons), (True, (SHAPE,)))
                self.assertEqual(read.named(F.ENCOUNTER), xs.attributes(F.ENCOUNTER))
        days = self.accepted(with_doubt(doubt('date_of_service', [], units=['S2'], readings=['2026-11-09',
                                                                                             '2024-02-29'])))
        self.assertEqual((days.doubts[0].malformed, days.doubts[0].named(F.ENCOUNTER)), (False, (A.DATE_OF_SERVICE,)))
        # an act's date keeps its own precision (1.4: ISO at its precision): a month or a year is a reading of it
        act = self.accepted(with_doubt(doubt('date_relation', ['E6'], units=['S4'], readings=['2023-04', '2023'])))
        self.assertFalse(act.doubts[0].malformed)

    def test_whole_and_conflict(self):
        whole = self.accepted(with_doubt(doubt('whole', ['E2', 'X1']))).doubts[0]
        self.assertFalse(whole.malformed)
        self.assertEqual((whole.named(F.EVENT), whole.named(F.SESSION)),
                         (xs.attributes(F.EVENT), xs.attributes(F.SESSION)))
        # a reading must be a value of the attribute on EVERY object named: emr is no value of a session's
        mixed = self.accepted(with_doubt(doubt('whole', ['E2', 'X1'], readings=['emr', 'egd']))).doubts[0]
        self.assertEqual((mixed.malformed, mixed.reasons), (True, (SHAPE,)))
        self.assertEqual(mixed.named(F.SESSION), xs.attributes(F.SESSION))  # whole either way
        kinds = self.accepted(with_doubt(doubt('kind', ['E2', 'X1'], readings=['emr']))).doubts[0]
        self.assertTrue(kinds.malformed)  # emr is a kind of an act, not of a session
        conflict = self.accepted(with_doubt(doubt('status', ['E2'], units=['S6', 'S7'], basis='conflict'))).doubts[0]
        self.assertEqual((conflict.malformed, conflict.doubt.basis), (False, ct.DoubtBasis.CONFLICT))

    def test_an_entry_reading_is_an_owner(self):
        good = self.accepted(with_doubt(doubt('entry', ['E5'], readings=['nursing', 'documenting_clinician'])))
        self.assertFalse(good.doubts[0].malformed)
        bad = self.accepted(with_doubt(doubt('entry', ['E5'], readings=['nurse'])))  # a person's role, not an owner
        self.assertTrue(bad.doubts[0].malformed)


# --- nothing is changed, as a property ----------------------------------------------------------------------------------

STATES = [state.value for state in ct.FactState]
# words of any character JSON may carry: NUL and lone surrogates are the json stage's refusals, never an item's
WORDS = st.text(alphabet=st.characters(blacklist_categories=('Cs',), blacklist_characters='\x00'), max_size=8)
# every id well formed (D185: a malformed one is the ids stage's refusal, IdStageTests): S0, S10 and S99 name no unit
UNIT_IDS = st.sampled_from(['S1', 'S6', 'S9', 'S10', 'S0', 'S99'])
SOURCES = st.lists(st.builds(lambda units, words, link: {'units': units, 'words': words, 'link': link},
                             st.lists(UNIT_IDS, max_size=14), WORDS,
                             st.sampled_from([link.value for link in ct.Link])), max_size=3)
OPTIONS = st.lists(st.builds(lambda value, sources: {'value': value, 'sources': sources},
                             st.sampled_from(['X1', 'X2', 'E2', 'L1']), SOURCES), max_size=3)  # an option is a value
FACTS = st.builds(lambda state, value, qualifiers, sources, options: {
    'state': state, 'value': value, 'qualifiers': qualifiers, 'sources': sources, 'options': options},
    st.sampled_from(STATES), st.sampled_from(['X1', 'X2', 'E2', 'L1', '']),
    st.lists(st.sampled_from([q.value for q in ct.Qualifier]), max_size=3), SOURCES, OPTIONS)


class PropertyTests(ReadTestCase):
    @hypothesis.settings(max_examples=300, deadline=None,
                         suppress_health_check=[hypothesis.HealthCheck.function_scoped_fixture])
    @hypothesis.given(FACTS)
    def test_any_fact_is_read_exactly_as_written_and_only_ever_gains_reasons(self, node):
        value = answer()
        value['events'][1]['session'] = [node]
        before = jsonschema.canonical(value)
        result = self.read(value)
        self.assertIsInstance(result, xr.ReadAnswer)  # an item can never refuse the answer
        self.assertEqual(jsonschema.canonical(result.answer), before)
        read = result.fact(key(F.EVENT, 'E2', A.SESSION))
        self.assertEqual(read.fact, typed(node))
        self.assertTrue(set(read.reasons) <= {SHAPE, UNIT, LONG, REF})
        self.assertEqual(len(read.sides), len(node['options']))
        clean = (node['state'] != 'contradicted' and node['value'] in ('X1',) and not node['options']
                 and node['sources'] and all(0 < len(s['units']) <= 12 and set(s['units']) <= {'S1', 'S6', 'S9'}
                                              for s in node['sources']))
        self.assertEqual(read.reasons == (), bool(clean))
        others = [item for item in result.facts if item.key != key(F.EVENT, 'E2', A.SESSION)]
        self.assertEqual([item.reasons for item in others], [()] * len(others))  # the finding stays on its fact


# --- the module: 5.7 measure 4, a fresh import, mypy ---------------------------------------------------------------------


class ModuleTests(SimpleTestCase):
    def test_the_reader_keeps_measure_4(self):
        self.assertEqual(measure_4((CONTRACT / 'extract_read.py').read_text(encoding='utf-8'), engine=False), [])
        planted = (CONTRACT / 'extract_read.py').read_text(encoding='utf-8') + "\nNEGATORS = ('no', 'neither')\n"
        self.assertTrue(measure_4(planted, engine=False))  # the control

    def test_a_fresh_interpreter_loads_no_v1_module(self):
        code = ('import sys\n'
                'import studio.interpretation.contract.extract_read\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=60, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().split(','), [
            'studio', 'studio.interpretation', 'studio.interpretation.contract',
            'studio.interpretation.contract.extract_read', 'studio.interpretation.contract.extract_schema',
            'studio.interpretation.contract.jsonschema', 'studio.interpretation.contract.types', 'studio.participants',
            'studio.participants.prompt', 'studio.participants.reading', 'studio.types'])

    def test_no_text_or_regular_expression_module_is_imported(self):
        for name in ('extract_read.py', 'extract_schema.py'):
            tree = ast.parse((CONTRACT / name).read_text(encoding='utf-8'))
            imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
            imported |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
            with self.subTest(module=name):
                self.assertFalse(imported & {'re', 'regex', 'unicodedata', 'difflib', 'fnmatch'}, imported)
                self.assertFalse({m for m in imported if m and m.startswith('studio.interpretation.')
                                  and m.split('.')[2] != 'contract'}, imported)

    def test_mypy_strict_passes_on_the_steps_modules(self):
        result = subprocess.run(
            [sys.executable, '-m', 'mypy', '--strict', '--follow-imports=silent', '--cache-dir', os.devnull,
             'studio/interpretation/contract/extract_schema.py', 'studio/interpretation/contract/extract_read.py'],
            capture_output=True, text=True, timeout=300, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 2 source files', result.stdout)
