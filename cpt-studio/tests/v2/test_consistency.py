"""contract/consistency.py: whether pass 1's own values hold together (docs/gemini-migration/FINAL-V2.md 3.1 rows K1-K8,
L1 and Q1, as REFUTATIONS-V2 revised them; step 2b of 8.1). TEXT-ONLY and SYNTHETIC: no network, no provider, no
document of the acceptance set.

The base fixture is FINAL-V2 1.9's worked example (a synthetic colonoscopy report of nine units with a fictional
endoscopist), as revision text and as pass 1's answer; DATES is a synthetic dated note written for L1. Every answer is
read by contract/extract_read.py under the computed LOCAL_SCHEMA_2 pin, and L1 reads each source's words as
contract/geometry.py locates them in the revision (the seam settle will use). The tables the checks read are the ones
settle wires (the hand-off 2b:R2 to step 3a): engine/anatomy.py and engine/catalogue.py (step 1e, FAMILY_REACH by
DECISIONS D192), engine/requirements_table.FAMILY_KINDS (step 1f, DECISIONS D191) and engine/requirements.py's
EXTRACTION_KINDS; VocabularyTests pins the Vocabulary's interface and proves the tables equal to v1's own (read only)
where the checks read them.

What is proved here, against the done-when of 8.1 step 2b and 9.3's consistency row:
- every rule with a violating and a satisfying fixture: K1's fourteen (K1Tests), K2's four arms (K2Tests), K3-K7
  (K3Tests ... K7Tests), K8 (K8Tests), L1 (L1Tests, RejudgeTests) and Q1 (Q1Tests); each finding lands on exactly the
  facts the rule names, and nowhere else;
- K2 with a second performer in one session has no effect, and an act's own other date demotes its session fact only,
  never the examination's facts [R:HO-7];
- K8 joins a reach given both polarities (and a reach inside a denied place) into one group of pass 1's own facts and
  creates nothing; a reach that only holds a denied point joins nothing [R:HO-9];
- L1 at day, month and year precision, at claim time against the document's own date of service (never a member value;
  a literal that meets no document date stops nothing), and re-judged with a member date, only ever demoting [R:MO-5];
- a finding never sets, changes or removes a value and never creates a fact, an exclusion, a support or a contradiction:
  the answer is left as read, the findings carry keys, reasons and literals only, and a property test over random
  answers checks it (NeverChangesTests);
- 5.7 measure 4 (WordsNeverDecide's import, string-method and membership rules, NoWordLists) holds over the module, each
  rule refusing a planted control, and mypy --strict passes on it (ModuleTests).

And the arbiter triage's repairs of waves 1 and 2 under the rulings: K1's reasons are types.Reason members (D186;
ModuleTests, NeverChangesTests); K2's kind arm reads the family-kinds table (D191; K2Tests) and K3 a reach typed over
Region (D192; K3Tests, VocabularyTests); K8 joins act places only (2b#3; K8Tests); L1 judges a month or a year against
on_date_of_service, an event's own date against the relation it inherits, and only a supported date (D193, 2b#5;
L1Tests, InheritedDateTests, RejudgeTests); and no citation names a report the harness refused (D207; ModuleTests).
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import inspect
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio import interpretation
from studio.gi import services as v1_services  # v1, read only: K3's reach is its FAMILY_REGIONS (DECISIONS D192)
from studio.interpretation import lexicon as v1_lexicon  # v1, read only
from studio.interpretation import mapping as v1_mapping  # v1, read only
from studio.interpretation.contract import consistency as cs
from studio.interpretation.contract import extract_read as xr
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract import geometry, jsonschema
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import anatomy as engine_anatomy
from studio.interpretation.engine import catalogue, requirements, requirements_table
from tests.v2.test_types import STR_METHODS, measure_4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'contract' / 'consistency.py'
F, A, R, S = xs.Family, ct.Attribute, ct.Reason, cs.Structure
# K1's fourteen reasons: types.Reason's structure_<rule> members, in 3.1 K1's order (DECISIONS D186).
K1_REASONS = (R.STRUCTURE_SCOPE, R.STRUCTURE_YIELD, R.STRUCTURE_ACCESS_OUTCOME, R.STRUCTURE_CAUSE, R.STRUCTURE_PART_OF,
              R.STRUCTURE_ENDOSCOPIC, R.STRUCTURE_VISIT, R.STRUCTURE_OTHER_CLASS, R.STRUCTURE_STATUS_TIME,
              R.STRUCTURE_EXCEPTIVE, R.STRUCTURE_LISTED_TARGETS, R.STRUCTURE_SINGLE_TARGET, R.STRUCTURE_SEGMENT,
              R.STRUCTURE_UMBRELLA)

# FINAL-V2 1.9's worked example as revision text: it segments into exactly the nine units 1.9 shows (WorkedExampleTests).
TEXT = ('COLONOSCOPY REPORT\n'
        'Date of service: 11/09/2026\n'
        'Endoscopist: Anselm Wrenfield, MD (fictional)\n'
        'History: Prior colonoscopy in 2023 with removal of two adenomas.\n'
        'Findings: The colonoscope was advanced to the cecum.\n'
        'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.\n'
        'Neither biopsy nor tattoo was performed.\n'
        'Documented by Jo Rowe, RN: A 4 mm polyp in the rectum at approx.\n'
        '5 cm was biopsied with cold forceps.\n')

# A synthetic dated note for L1: one date literal of a known precision per unit (S3-S11), none in S1 and S12.
DATES = ('EGD REPORT\n'  # S1
         'Date of service: 11/09/2026\n'  # S2: the document's date, day precision
         'Prior EGD in 2023.\n'  # S3: a year before
         'Repeat EGD planned in 2027.\n'  # S4: a year after
         'Seen in clinic in March 2026.\n'  # S5: a month before
         'Seen again in November 2026.\n'  # S6: the month of the date of service
         'A biopsy was taken on 11/08/2026.\n'  # S7: the day before
         'A biopsy was taken on 11/09/2026.\n'  # S8: the date of service
         'A biopsy is planned on 11/10/2026.\n'  # S9: the day after
         'In 2026 the stricture was dilated.\n'  # S10: the year of the date of service
         'Labs from 10/2026 were reviewed.\n'  # S11: the month before, written numerically
         'The polyp was removed with a cold snare.\n')  # S12: no date literal


# --- the answer builders ---------------------------------------------------------------------------------------------

def src(*units: str, words: str = '', link: str = 'statement') -> dict:
    return {'units': list(units), 'words': words, 'link': link}


def fact(value: str, *units: str, state: str = 'supported', words: str = '', link: str = 'statement',
         qualifiers=()) -> dict:
    return {'state': state, 'value': value, 'qualifiers': list(qualifiers),
            'sources': [src(*units, words=words, link=link)] if units else [], 'options': []}


def contradicted(*sides, qualifiers=()) -> dict:
    """A contradicted fact: each side (value, unit), its sources the union of the sides'."""
    return {'state': 'contradicted', 'value': '', 'qualifiers': list(qualifiers),
            'sources': [src(unit) for _, unit in sides],
            'options': [{'value': value, 'sources': [src(unit)]} for value, unit in sides]}


def put(item: dict, path: str, value) -> dict:
    *parents, last = path.split('.')
    node = item
    for name in parents:
        node = node[name]
    node[last] = value
    return item


def person(id: str, role: str, unit: str = 'S3') -> dict:
    return {'id': id, 'name': src(unit), 'role': fact(role, unit)}


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


def event(id: str, anchor, kind: dict, status: dict, kind_words: str = '', status_words: str = '', **fields) -> dict:
    item = {'id': id, 'anchor': {'units': list(anchor), 'kind_words': kind_words, 'status_words': status_words},
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


def doubt(about: str, objects, units=('S6',), basis: str = 'stated', readings=()) -> dict:
    return {'about': about, 'objects': list(objects), 'units': list(units), 'basis': basis, 'readings': list(readings)}


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
                  kind_words='colonoscope', status_words='advanced', session=[fact('X1', 'S5')]),
            event('E2', ['S6'], fact('snare', 'S6', words='cold snare'), fact('performed', 'S6', words='was removed'),
                  kind_words='cold snare', status_words='was removed', session=[fact('X1', 'S6')],
                  target__lesion=[fact('L1', 'S6')], target__places=[fact('sigmoid_colon', 'S6')],
                  technique__device=[fact('cold_snare', 'S6')]),
            event('E3', ['S7'], fact('biopsy', 'S7', words='biopsy'),
                  fact('performed', 'S7', state='negated', words='Neither biopsy nor tattoo was performed'),
                  kind_words='biopsy', status_words='was performed', session=[fact('X1', 'S7')],
                  scope__breadth=[fact('all_of_kind', 'S7')]),
            event('E4', ['S7'], fact('tattoo', 'S7', words='tattoo'),
                  fact('performed', 'S7', state='negated', words='Neither biopsy nor tattoo was performed'),
                  kind_words='tattoo', status_words='was performed', session=[fact('X1', 'S7')],
                  scope__breadth=[fact('all_of_kind', 'S7')]),
            event('E5', ['S8', 'S9'], fact('biopsy', 'S9', words='biopsied'),
                  fact('performed', 'S9', words='was biopsied'), kind_words='biopsied', status_words='was biopsied',
                  target__lesion=[fact('L2', 'S8')], target__places=[fact('rectum', 'S8')],
                  technique__device=[fact('cold_forceps', 'S9')]),
            event('E6', ['S4'], fact('removal', 'S4', words='removal'), fact('performed', 'S4', words='with removal'),
                  kind_words='removal', status_words='removal', date=[fact('2023', 'S4', words='2023')]),
        ],
        'doubts': [],
    }


def dated(*events: dict, dos: str = '2026-11-09', dos_words: str = '11/09/2026', dos_state: str = 'stated',
          occasion=None, other_dates=()) -> dict:
    """An answer over DATES: the date of service from S2, one opening section N0 (its occasion ``occasion``), one EGD
    session X1 whose examination E1 is told in S1, and ``events``."""
    frame = {'link': 'document_frame'}
    when = ({'state': dos_state, 'value': dos, 'sources': [src('S2', words=dos_words, **frame)], 'options': []}
            if dos_state == 'stated' else {'state': 'not_stated', 'value': '', 'sources': [], 'options': []})
    return {
        'encounter': {'date_of_service': when,
                      'other_dates': [{'value': value, 'role': fact('other_occurrence', unit, words=words)}
                                      for value, unit, words in other_dates],
                      'documenting_clinician': []},
        'people': [],
        'sections': [section('N0', src(link='section'), fact('documenting_clinician', 'S1', **frame),
                             occasion=[occasion] if occasion else [])],
        'sessions': [session('X1', fact('egd', 'S1', words='EGD', **frame), examination=[fact('E1', 'S1')])],
        'anatomy': [], 'lesions': [],
        'events': [event('E1', ['S1'], fact('examination', 'S1', words='EGD'), fact('performed', 'S1'),
                         kind_words='EGD', status_words='EGD', session=[fact('X1', 'S1')]), *events],
        'doubts': [],
    }


def key(family, object_id, attribute, index=0) -> xr.FactKey:
    return xr.FactKey(family, object_id, attribute, index)


def changed(edit, base=answer) -> dict:
    value = base()
    edit(value)
    return value


def at(value: dict, event_id: str) -> dict:
    return next(item for item in value['events'] if item['id'] == event_id)


def section_at(value: dict, section_id: str) -> dict:
    return next(item for item in value['sections'] if item['id'] == section_id)


# --- the seam: geometry locates the words L1 reads, and the sections K2's date arm reads -----------------------------

def located(layout: geometry.Layout):
    """What settle hands L1 (consistency.Words): the revision's own slice of a source's located words, or of its whole
    units for words ''; None when the source does not locate."""
    def words(source: ct.Source):
        found = geometry.locate(layout, source)
        if found.reasons or found.place is None:
            return None
        return layout.text[found.place.start:found.place.end]
    return words


def typed_source(node: dict) -> ct.Source:
    return ct.Source(tuple(node['units']), node['words'], ct.Link(node['link']))


def sections_of(layout: geometry.Layout, value: dict) -> dict:
    """Each event's containing section when G4's edge holds (geometry.Sections.attached on its anchor's place)."""
    sections = geometry.Sections(layout, [
        geometry.Section(item['id'], typed_source(item['start']), tuple(typed_source(end) for end in item['end']))
        for item in value['sections']])
    out = {}
    for item in value['events']:
        anchor = geometry.Anchor(tuple(item['anchor']['units']), item['anchor']['kind_words'],
                                 item['anchor']['status_words'])
        place = geometry.locate_anchor(layout, anchor).place
        found = sections.attached(place) if place is not None else None
        if found is not None:
            out[item['id']] = found.id
    return out


# --- the vocabulary: the tables settle wires (hand-off 2b:R2; DECISIONS D191, D192) -----------------------------------

def family_admits(family: ct.SessionKind, kind: ct.Kind) -> bool:
    """K2's kind arm as settle wires it (DECISIONS D191): whether ``kind`` is one of the session family's kinds,
    engine/requirements_table.FAMILY_KINDS; a family the table does not list admits no kind (fail-closed: the act's
    session fact is demoted, never set)."""
    return kind in requirements_table.FAMILY_KINDS.get(family, frozenset())


# Positionally, in Vocabulary's field order, which VocabularyTests pins by name and type: contains, region, reach,
# family_admits, covers, endoscopic, extraction.
VOCABULARY = cs.Vocabulary(engine_anatomy.contains, engine_anatomy.region, catalogue.FAMILY_REACH, family_admits,
                           catalogue.covers, catalogue.ENDOSCOPIC_FAMILIES, requirements.EXTRACTION_KINDS)
# v1's own tables (read only), which steps 1e and 1f port by value: VocabularyTests compares them where the checks
# read them.
V1_REACH = {name[3:]: frozenset(regions) for name, regions in v1_services.FAMILY_REGIONS.items()}
V1_EXTRACTION = frozenset({ct.Kind.STONE_EXTRACTION, ct.Kind.FOREIGN_BODY, ct.Kind.REMOVAL, ct.Kind.STENT_REMOVAL})


class Case(SimpleTestCase):
    """Every answer is read under the computed LOCAL_SCHEMA_2 pin, which the integration owner writes (2.5)."""
    vocabulary = VOCABULARY

    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.object(interpretation, 'LOCAL_SCHEMA_SHA256_V2',
                                            jsonschema.sha256_of(xs.LOCAL_SCHEMA_2)))

    def read(self, value: dict, text: str = TEXT) -> xr.ReadAnswer:
        layout = geometry.Layout.of(text)
        found = xr.read(json.dumps(value), len(layout.units))
        self.assertIsInstance(found, xr.ReadAnswer, getattr(found, 'reason', ''))
        return found

    def check(self, value: dict, text: str = TEXT, containing=None) -> cs.Findings:
        layout = geometry.Layout.of(text)
        read = self.read(value, text)
        return cs.check(read, self.vocabulary, located(layout),
                        sections_of(layout, value) if containing is None else containing)

    def found(self, value: dict, text: str = TEXT, containing=None) -> dict:
        """Every fact with a finding, and its reasons by value (K1's, K2-K7's, L1's and Q1's)."""
        findings = self.check(value, text, containing)
        keys = [*findings.structure, *findings.consistency, *findings.literal, *findings.qualified]
        return {item: {reason.value for reason in findings.reasons(item)} for item in dict.fromkeys(keys)}

    def assertFound(self, value: dict, expected: dict, text: str = TEXT, containing=None):
        self.assertEqual(self.found(value, text, containing), {item: set(reasons) for item, reasons in
                                                                 expected.items()})


# --- the worked example --------------------------------------------------------------------------------------------------


class WorkedExampleTests(Case):
    def test_the_text_segments_into_the_nine_units_of_the_design(self):
        layout = geometry.Layout.of(TEXT)
        self.assertEqual([unit.id for unit in layout.units], [f'S{k}' for k in range(1, 10)])
        self.assertEqual(TEXT[layout.units[6].start:layout.units[6].end], 'Neither biopsy nor tattoo was performed.')

    def test_the_worked_example_holds_together(self):
        findings = self.check(answer())
        self.assertEqual((dict(findings.structure), dict(findings.consistency), dict(findings.literal),
                          dict(findings.qualified), findings.joined), ({}, {}, {}, {}, ()))
        self.assertEqual(findings.document_date, date(2026, 11, 9))
        lit = ct.StoredLiteral
        self.assertEqual(dict(findings.literals), {
            key(F.ENCOUNTER, '', A.DATE_OF_SERVICE): (lit('2026-11-09', ct.Precision.DAY),),
            key(F.ENCOUNTER, '', A.OTHER_DATES_ROLE): (lit('2023', ct.Precision.YEAR),),
            key(F.SECTION, 'N0', A.OCCASION): (lit('2026-11-09', ct.Precision.DAY),),
            key(F.SECTION, 'N1', A.OCCASION): (lit('2023', ct.Precision.YEAR),),
            key(F.SECTION, 'N2', A.OCCASION): (lit('2026-11-09', ct.Precision.DAY),),
            key(F.SECTION, 'N3', A.OCCASION): (lit('2026-11-09', ct.Precision.DAY),),
            key(F.EVENT, 'E6', A.DATE): (lit('2023', ct.Precision.YEAR),),
            # E6, the history's prior removal, states no date relation of its own: it inherits N1's earlier_date, read
            # with N1's words and its own date's, under its own key; its 2023 agrees with it (DECISIONS D193)
            key(F.EVENT, 'E6', A.DATE_RELATION): (lit('2023', ct.Precision.YEAR), lit('2023', ct.Precision.YEAR))})

    def test_the_dated_note_holds_together(self):
        self.assertEqual([unit.id for unit in geometry.Layout.of(DATES).units], [f'S{k}' for k in range(1, 13)])
        self.assertFound(dated(), {}, DATES)


# --- K1: values allowed together -----------------------------------------------------------------------------------------


class K1Tests(Case):
    def test_scope_only_on_negated_or_stated_doubt_statements(self):
        def scoped(value):
            put(at(value, 'E2'), 'scope.breadth', [fact('all_of_kind', 'S6')])
            put(at(value, 'E2'), 'scope.covers', ['E5'])
        self.assertFound(changed(scoped), {key(F.EVENT, 'E2', A.SCOPE_BREADTH): {'structure_scope'},
                                           key(F.EVENT, 'E2', A.SCOPE_COVERS): {'structure_scope'}})
        # a stated doubt on the status makes it a statement; an unclear one does not (1.3)
        stated = changed(lambda value: (scoped(value), value['doubts'].append(doubt('status', ['E2']))))
        self.assertFound(stated, {})
        whole = changed(lambda value: (scoped(value), value['doubts'].append(doubt('whole', ['E2']))))
        self.assertFound(whole, {})
        unclear = changed(lambda value: (scoped(value), value['doubts'].append(doubt('status', ['E2'],
                                                                                     basis='unclear'))))
        self.assertIn(key(F.EVENT, 'E2', A.SCOPE_BREADTH), self.found(unclear))
        # the base: two negated statements with their scopes
        self.assertFound(answer(), {})

    def test_yield_only_on_extraction_kinds(self):
        self.assertFound(changed(lambda value: put(at(value, 'E2'), 'yield', [fact('stones', 'S6')])),
                         {key(F.EVENT, 'E2', A.YIELD): {'structure_yield'}})
        for kind in ('stone_extraction', 'foreign_body', 'removal', 'stent_removal'):
            with self.subTest(kind=kind):
                def edit(value, kind=kind):
                    put(at(value, 'E2'), 'yield', [fact('anything', 'S6', state='negated')])
                    at(value, 'E2')['kind'] = fact(kind, 'S6')
                self.assertNotIn(key(F.EVENT, 'E2', A.YIELD), self.found(changed(edit)))

    def test_access_outcome_only_on_cannulation(self):
        self.assertFound(changed(lambda value: put(at(value, 'E2'), 'access_outcome', [fact('achieved', 'S6')])),
                         {key(F.EVENT, 'E2', A.ACCESS_OUTCOME): {'structure_access_outcome'}})

        def cannulation(value):
            put(at(value, 'E5'), 'access_outcome', [fact('failed', 'S9')])
            at(value, 'E5')['kind'] = fact('cannulation', 'S9')
        self.assertFound(changed(cannulation), {})

    def test_cause_and_cause_event_only_with_purpose_hemostasis(self):
        def caused(purpose):
            def edit(value):
                put(at(value, 'E5'), 'cause', [fact('act_of_this_session', 'S9')])
                put(at(value, 'E5'), 'cause_event', [fact('E2', 'S9')])
                if purpose:
                    put(at(value, 'E5'), 'purpose', [fact(purpose, 'S9')])
            return edit
        demoted = {key(F.EVENT, 'E5', A.CAUSE): {'structure_cause'},
                   key(F.EVENT, 'E5', A.CAUSE_EVENT): {'structure_cause'}}
        self.assertFound(changed(caused('prophylaxis')), demoted)
        self.assertFound(changed(caused('')), demoted)
        self.assertFound(changed(caused('hemostasis')), {})

    def test_part_of_and_part_relation_together(self):
        part = key(F.EVENT, 'E5', A.PART_OF)
        relation = key(F.EVENT, 'E5', A.PART_RELATION)
        self.assertFound(changed(lambda value: put(at(value, 'E5'), 'part_of', [fact('E2', 'S9')])),
                         {part: {'structure_part_of'}})
        self.assertFound(changed(lambda value: put(at(value, 'E5'), 'part_relation', [fact('step_of', 'S9')])),
                         {relation: {'structure_part_of'}})

        def both(value):
            put(at(value, 'E5'), 'part_of', [fact('E2', 'S9')])
            put(at(value, 'E5'), 'part_relation', [fact('adjunct_of', 'S9')])
        self.assertFound(changed(both), {})
        # a separate act is part_of negated (1.6), and needs no relation
        self.assertFound(changed(lambda value: put(at(value, 'E5'), 'part_of', [fact('E2', 'S9', state='negated')])),
                         {})

    def test_reached_stations_and_completion_only_on_endoscopic_sessions(self):
        def office(value):
            value['sessions'].append(session('X2', fact('office_em', 'S1'), stations=[fact('stomach', 'S5')],
                                             completion=[fact('complete', 'S5')], reached=[fact('cecum', 'S5')]))
        self.assertFound(changed(office), {key(F.SESSION, 'X2', A.REACHED): {'structure_endoscopic'},
                                           key(F.SESSION, 'X2', A.COMPLETION): {'structure_endoscopic'},
                                           key(F.SESSION, 'X2', A.STATIONS): {'structure_endoscopic'}})

        def capsule(value):  # a capsule's points go in device_reached (P19), which this rule never names
            value['sessions'].append(session('X2', fact('capsule', 'S1'), device_reached=[fact('cecum', 'S5')]))
        self.assertFound(changed(capsule), {})

        def colon(value):
            value['sessions'][0]['stations'] = [fact('colon', 'S5')]
            value['sessions'][0]['completion'] = [fact('complete', 'S5')]
        self.assertFound(changed(colon), {})

    def test_visit_facts_only_on_em_visit(self):
        def visit(kind):
            def edit(value):
                put(at(value, 'E5'), 'visit.basis', [fact('total_time', 'S9')])
                put(at(value, 'E5'), 'visit.separately_identifiable', [fact('stated', 'S9', state='negated')])
                at(value, 'E5')['kind'] = fact(kind, 'S9')
            return edit
        self.assertFound(changed(visit('biopsy')), {key(F.EVENT, 'E5', A.VISIT_BASIS): {'structure_visit'},
                                                    key(F.EVENT, 'E5', A.VISIT_SEPARATELY_IDENTIFIABLE):
                                                        {'structure_visit'}})
        self.assertFound(changed(visit('em_visit')), {})

    def test_other_class_only_on_kind_other(self):
        self.assertFound(changed(lambda value: put(at(value, 'E5'), 'other_class', [fact('procedure', 'S9')])),
                         {key(F.EVENT, 'E5', A.OTHER_CLASS): {'structure_other_class'}})

        def other(value):
            put(at(value, 'E5'), 'other_class', [fact('order', 'S9')])
            at(value, 'E5')['kind'] = fact('other', 'S9')
        self.assertFound(changed(other), {})

    def test_status_against_timing(self):
        def timed(status, relation):
            def edit(value):
                at(value, 'E5')['status'] = fact(status, 'S9')
                put(at(value, 'E5'), 'date_relation', [fact(relation, 'S9')])
            return edit
        both = {key(F.EVENT, 'E5', A.STATUS): {'structure_status_time'},
                key(F.EVENT, 'E5', A.DATE_RELATION): {'structure_status_time'}}
        self.assertFound(changed(timed('performed', 'later_date')), both)
        self.assertFound(changed(timed('attempted_not_completed', 'later_date')), both)
        self.assertFound(changed(timed('planned', 'earlier_date')), both)
        self.assertFound(changed(timed('planned', 'later_date')), {})
        self.assertFound(changed(timed('performed', 'earlier_date')), {})
        self.assertFound(changed(timed('performed', 'on_date_of_service')), {})

    def test_exceptive_needs_existing_positive_excepts_of_a_covered_kind(self):
        breadth = key(F.EVENT, 'E3', A.SCOPE_BREADTH)

        def exceptive(kind, *excepts):
            def edit(value):
                at(value, 'E3')['kind'] = fact(kind, 'S7')
                put(at(value, 'E3'), 'scope.breadth', [fact('exceptive', 'S7')])
                put(at(value, 'E3'), 'scope.excepts', list(excepts))
            return edit
        self.assertFound(changed(exceptive('removal', 'E2')), {})  # removal covers the performed snare
        self.assertFound(changed(exceptive('snare', 'E2')), {})
        self.assertFound(changed(exceptive('removal')), {breadth: {'structure_exceptive'}})  # 3.8 probe (c)
        self.assertFound(changed(exceptive('biopsy', 'E2')), {breadth: {'structure_exceptive'}})  # not covered
        self.assertFound(changed(exceptive('tattoo', 'E4')), {breadth: {'structure_exceptive'}})  # not positive
        self.assertIn('structure_exceptive', self.found(changed(exceptive('removal', 'E9')))[breadth])  # no event

    def test_listed_targets_needs_two_or_more_targets(self):
        def listed(*targets):
            def edit(value):
                put(at(value, 'E3'), 'scope.breadth', [fact('listed_targets', 'S7')])
                put(at(value, 'E3'), 'scope.targets', list(targets))
            return edit
        self.assertFound(changed(listed('L1', 'L2')), {})
        self.assertFound(changed(listed('L1')), {key(F.EVENT, 'E3', A.SCOPE_BREADTH): {'structure_listed_targets'}})
        self.assertFound(changed(listed('L1', 'L1')),
                         {key(F.EVENT, 'E3', A.SCOPE_BREADTH): {'structure_listed_targets'}})

    def test_single_target_needs_a_lesion_or_a_place(self):
        def single(**target):
            def edit(value):
                put(at(value, 'E3'), 'scope.breadth', [fact('single_target', 'S7')])
                for path, item in target.items():
                    put(at(value, 'E3'), path.replace('__', '.'), item)
            return edit
        self.assertFound(changed(single()), {key(F.EVENT, 'E3', A.SCOPE_BREADTH): {'structure_single_target'}})
        self.assertFound(changed(single(target__lesion=[fact('L1', 'S7')])), {})
        self.assertFound(changed(single(target__lesion=[fact('L9', 'S7')])),  # names no lesion (I4's, and K1's too)
                         {key(F.EVENT, 'E3', A.SCOPE_BREADTH): {'structure_single_target'}})
        self.assertFound(changed(single(target__places=[fact('rectum', 'S7')])), {})
        self.assertFound(changed(single(scope__targets=['L2'])), {})

    def test_segment_needs_two_landmarks(self):
        def segment(*places):
            def edit(value):
                put(at(value, 'E3'), 'scope.breadth', [fact('segment', 'S7')])
                put(at(value, 'E3'), 'scope.segment', list(places))
            return edit
        self.assertFound(changed(segment('sigmoid_colon', 'rectum')), {})
        for places in (('rectum',), ('rectum', 'rectum'), ('cecum', 'sigmoid_colon', 'rectum')):
            with self.subTest(places=places):
                self.assertFound(changed(segment(*places)),
                                 {key(F.EVENT, 'E3', A.SCOPE_BREADTH): {'structure_segment'}})

    def test_the_umbrella_intervention_only_on_statements(self):
        self.assertFound(changed(lambda value: at(value, 'E5').update(kind=fact('intervention', 'S9'))),
                         {key(F.EVENT, 'E5', A.KIND): {'structure_umbrella'}})
        self.assertFound(changed(lambda value: at(value, 'E3').update(kind=fact('intervention', 'S7'))), {})

    def test_a_k1_finding_never_demotes_the_value_it_is_checked_against(self):
        """The kind, status, purpose and session kind stay as read: only the dependent value is named."""
        def everything(value):
            item = at(value, 'E2')
            put(item, 'yield', [fact('stones', 'S6')])
            put(item, 'access_outcome', [fact('achieved', 'S6')])
            put(item, 'cause', [fact('pre_existing_lesion', 'S6')])
            put(item, 'other_class', [fact('procedure', 'S6')])
            put(item, 'visit.basis', [fact('total_time', 'S6')])
        found = self.found(changed(everything))
        self.assertEqual(set(found), {key(F.EVENT, 'E2', attribute) for attribute in (
            A.YIELD, A.ACCESS_OUTCOME, A.CAUSE, A.OTHER_CLASS, A.VISIT_BASIS)})

    def test_k1s_findings_are_types_reason_members(self):
        """DECISIONS D186: K1's findings are types.Reason's structure_<rule> members, which settle stores in
        SettledFact.reasons as they are; the gate's merged tree failed while they were consistency.Structure's."""
        own = key(F.EVENT, 'E2', A.YIELD)
        findings = self.check(changed(lambda value: put(at(value, 'E2'), 'yield', [fact('stones', 'S6')])))
        self.assertEqual(dict(findings.structure), {own: (R.STRUCTURE_YIELD,)})
        self.assertEqual(findings.reasons(own), (R.STRUCTURE_YIELD,))
        statement = self.check(changed(lambda value: (
            put(at(value, 'E3'), 'scope.breadth', [fact('segment', 'S7')]),
            put(at(value, 'E2'), 'scope.breadth', [fact('all_of_kind', 'S6')]))))
        self.assertEqual(dict(statement.structure), {key(F.EVENT, 'E2', A.SCOPE_BREADTH): (R.STRUCTURE_SCOPE,),
                                                     key(F.EVENT, 'E3', A.SCOPE_BREADTH): (R.STRUCTURE_SEGMENT,)})


# --- K2: session consistency [R:HO-7] ----------------------------------------------------------------------------------


class K2Tests(Case):
    def test_an_events_session_exists(self):
        def lost(value):
            value['sessions'].append(session('X2', fact('egd', 'S1')))
            put(at(value, 'E5'), 'session', [fact('X9', 'S9')])
        self.assertFound(changed(lost), {key(F.EVENT, 'E5', A.SESSION): {'session_inconsistent'}})
        self.assertFound(changed(lambda value: put(at(value, 'E5'), 'session',
                                                   [contradicted(('X1', 'S8'), ('X9', 'S9'))])),
                         {key(F.EVENT, 'E5', A.SESSION): {'session_inconsistent'}})
        self.assertFound(changed(lambda value: put(at(value, 'E5'), 'session', [fact('X1', 'S9')])), {})

    def test_a_sessions_examination_names_it(self):
        link = key(F.SESSION, 'X1', A.EXAMINATION)

        def elsewhere(value):
            value['sessions'].append(session('X2', fact('egd', 'S1')))
            at(value, 'E1')['session'] = [fact('X2', 'S5')]
        self.assertFound(changed(elsewhere), {link: {'session_inconsistent'}})  # never the examination's own facts
        self.assertFound(changed(lambda value: at(value, 'E1').update(session=[fact('X1', 'S5', state='negated')])),
                         {link: {'session_inconsistent'}})
        self.assertFound(changed(lambda value: at(value, 'E1').update(session=[])), {})  # silent: nothing differs
        self.assertFound(answer(), {})

    def test_an_acts_session_kind_admits_its_kind(self):
        def in_ercp(kind, state='supported'):
            def edit(value):
                value['sessions'].append(session('X2', fact('ercp', 'S1')))
                item = at(value, 'E5')
                item['kind'], item['status'] = fact(kind, 'S9'), fact('performed', 'S9', state=state)
                put(item, 'session', [fact('X2', 'S9')])
            return edit
        self.assertFound(changed(in_ercp('snare')), {key(F.EVENT, 'E5', A.SESSION): {'session_inconsistent'}})
        self.assertFound(changed(in_ercp('sphincterotomy')), {})
        self.assertFound(changed(in_ercp('snare', state='negated')), {})  # a statement is not an act (3.2.1)

        def examination(value):  # ADJUDICATION C-1: the examination is the session, never an act
            value['sessions'].append(session('X2', fact('ercp', 'S1'), examination=[fact('E5', 'S9')]))
            item = at(value, 'E5')
            item['kind'] = fact('examination', 'S9')
            put(item, 'session', [fact('X2', 'S9')])
        self.assertFound(changed(examination), {})

    def test_the_kind_arm_reads_the_family_kinds_table(self):
        """DECISIONS D191: "an act's session kind admits its kind" asks whether a session of the family can hold the
        kind (FAMILY_KINDS), not whether a CODE of the family accounts for it (catalogue.family_codes_act), under which
        every ERCP cannulation and every hemostatic clip lost its session. An ERCP's cannulation, a colonoscopy's and an
        EGD's clip and an EGD's ESD keep it; a PEG in a colonoscopy session is still demoted."""
        def act(kind, family):
            def edit(value):
                value['sessions'].append(session('X2', fact(family, 'S1')))
                at(value, 'E5')['kind'] = fact(kind, 'S9')
                put(at(value, 'E5'), 'session', [fact('X2', 'S9')])
                put(at(value, 'E5'), 'target.places', [])  # no place, so K3 has nothing to judge
            return edit
        for kind, family in (('cannulation', 'ercp'), ('clip', 'colonoscopy'), ('clip', 'egd'), ('esd', 'egd')):
            with self.subTest(kind=kind, family=family):
                self.assertFalse(catalogue.family_codes_act(ct.SessionKind(family), ct.Kind(kind)))  # no code of it
                self.assertFound(changed(act(kind, family)), {})
        self.assertFound(changed(act('peg', 'colonoscopy')), {key(F.EVENT, 'E5', A.SESSION): {'session_inconsistent'}})
        # the arm reads the injected table, whatever it holds: a table without the snare demotes the colonoscopy's snare
        self.vocabulary = dataclasses.replace(VOCABULARY, family_admits=lambda family, kind: kind is not ct.Kind.SNARE)
        self.assertFound(answer(), {key(F.EVENT, 'E2', A.SESSION): {'session_inconsistent'}})

    def test_an_acts_own_other_date_demotes_its_session_fact_only(self):
        """E2 says earlier_date of its own; its session's examination E1 inherits on_date_of_service from N2, the
        Findings part its anchor lies in. Only E2's session fact is demoted: the examination's facts, and E2's own
        date relation, are never touched (K2: "makes the ACT'S session fact unresolved")."""
        other = changed(lambda value: put(at(value, 'E2'), 'date_relation', [fact('earlier_date', 'S6')]))
        layout = geometry.Layout.of(TEXT)
        self.assertEqual(sections_of(layout, other)['E1'], 'N2')
        self.assertFound(other, {key(F.EVENT, 'E2', A.SESSION): {'session_conflict'}})
        same = changed(lambda value: put(at(value, 'E2'), 'date_relation', [fact('on_date_of_service', 'S6')]))
        self.assertFound(same, {})
        # with no section known for the examination, it has no inherited date to differ from
        self.assertFound(other, {}, containing={})

    def test_the_date_arm_reads_the_examinations_own_date_relation_first(self):
        def edit(value):
            at(value, 'E1')['date_relation'] = [fact('earlier_date', 'S5')]
            put(at(value, 'E2'), 'date_relation', [fact('on_date_of_service', 'S6')])
        self.assertFound(changed(edit), {key(F.EVENT, 'E2', A.SESSION): {'session_conflict'}})

    def test_the_date_arm_compares_stated_and_denied_values(self):
        def relation(own, state):
            return changed(lambda value: put(at(value, 'E2'), 'date_relation', [fact(own, 'S6', state=state)]))
        self.assertFound(relation('on_date_of_service', 'negated'),
                         {key(F.EVENT, 'E2', A.SESSION): {'session_conflict'}})
        self.assertFound(relation('later_date', 'negated'), {})  # "not later" agrees with today

    def test_a_second_performer_in_one_session_has_no_effect(self):
        """[R:HO-7] a surgeon called in to place clips: another performer than the examination's, in one session.
        There is no performer arm: nothing anywhere is demoted, the examination's facts above all."""
        def surgeon(value):
            value['people'].append(person('P3', 'other', 'S6'))
            item = at(value, 'E2')
            put(item, 'performer', [fact('other_clinician', 'S6')])
            put(item, 'performer_person', [fact('P3', 'S6')])
            at(value, 'E1')['performer'] = [fact('documenting_team', 'S5')]
            at(value, 'E1')['performer_person'] = [fact('P1', 'S5')]
        self.assertFound(changed(surgeon), {})
        findings = self.check(changed(surgeon))
        self.assertFalse([item for item in findings.consistency if item.object in ('E1', 'X1')])


# --- K3: place against session; K4: anatomy against places --------------------------------------------------------------


class K3Tests(Case):
    def test_an_act_place_the_sessions_family_cannot_reach(self):
        session_key = key(F.EVENT, 'E2', A.SESSION)
        self.assertFound(changed(lambda value: put(at(value, 'E2'), 'target.places', [fact('gastric_antrum', 'S6')])),
                         {session_key: {'session_unreachable'}})
        # nothing is moved: the place and the session stay as read
        found = self.check(changed(lambda value: put(at(value, 'E2'), 'target.places', [fact('stomach', 'S6')])))
        self.assertEqual(list(found.consistency), [session_key])
        for place in ('sigmoid_colon', 'terminal_ileum', 'rectum'):
            with self.subTest(place=place):
                self.assertFound(changed(lambda value, p=place: put(at(value, 'E2'), 'target.places',
                                                                    [fact(p, 'S6')])), {})

    def test_k3_judges_only_what_it_can(self):
        """A place with no region, a denied place, a statement, and a family with no reach established."""
        for place, state in (('anastomosis', 'supported'), ('stomach', 'negated')):
            with self.subTest(place=place, state=state):
                self.assertFound(changed(lambda value, p=place, s=state: put(at(value, 'E2'), 'target.places',
                                                                             [fact(p, 'S6', state=s)])), {})
        self.assertFound(changed(lambda value: put(at(value, 'E3'), 'target.places', [fact('stomach', 'S7')])), {})

        def eus(value):
            value['sessions'][0]['kind'] = fact('eus', 'S1')
            at(value, 'E2')['kind'] = fact('fna', 'S6')
            put(at(value, 'E2'), 'target.places', [fact('pancreas', 'S6')])
        self.assertFound(changed(eus), {})

    def test_k3_fires_with_the_ruled_reach(self):
        """DECISIONS D192: K3's reach is engine/catalogue.FAMILY_REACH, v1's FAMILY_REGIONS by value, over Region. An
        EGD act at the sigmoid colon loses its session (3a pins the same with settle's own Vocabulary); an EGD act in
        the duodenum and an enteroscopy's in the jejunum keep theirs; the two over-holds D192 records as fail-closed
        residuals demote (an EGD biopsy at the ampulla, a push enteroscopy's gastric act); an ERCP, which the table
        does not list, is not judged."""
        def placed(family, place):
            def edit(value):
                value['sessions'][0]['kind'] = fact(family, 'S1')
                at(value, 'E2')['kind'] = fact('biopsy', 'S6')
                put(at(value, 'E2'), 'target.places', [fact(place, 'S6')])
            return changed(edit)
        unreachable = {key(F.EVENT, 'E2', A.SESSION): {'session_unreachable'}}
        for family, place, expected in (('egd', 'sigmoid_colon', unreachable), ('egd', 'second_portion_duodenum', {}),
                                        ('enteroscopy', 'jejunum', {}), ('egd', 'ampulla', unreachable),
                                        ('enteroscopy', 'stomach', unreachable), ('ercp', 'sigmoid_colon', {})):
            with self.subTest(family=family, place=place):
                self.assertFound(placed(family, place), expected)


class K4Tests(Case):
    def test_an_absent_organ_against_a_reach_a_place_and_a_station_inside_it(self):
        def colectomy(value):
            value['anatomy'].append(anatomy('Y1', fact('surgically_absent', 'S4'), organ=[fact('colon', 'S4')]))
        conflict = {'anatomy_conflict'}
        self.assertFound(changed(colectomy), {key(F.ANATOMY, 'Y1', A.TYPE): conflict,
                                              key(F.ANATOMY, 'Y1', A.ORGAN): conflict,
                                              key(F.SESSION, 'X1', A.REACHED): conflict,
                                              key(F.EVENT, 'E2', A.TARGET_PLACES): conflict})

        def gastrectomy(value):
            value['anatomy'].append(anatomy('Y1', fact('surgically_absent', 'S4'), organ=[fact('stomach', 'S4')]))
            value['sessions'][0]['stations'] = [fact('stomach', 'S5'), fact('colon', 'S5')]
        self.assertFound(changed(gastrectomy), {key(F.ANATOMY, 'Y1', A.TYPE): conflict,
                                                key(F.ANATOMY, 'Y1', A.ORGAN): conflict,
                                                key(F.SESSION, 'X1', A.STATIONS, 0): conflict})

    def test_no_conflict_outside_the_absent_organ_or_without_an_absence(self):
        def absent(organ, type_='surgically_absent'):
            return changed(lambda value: value['anatomy'].append(
                anatomy('Y1', fact(type_, 'S4'), organ=[fact(organ, 'S4')])))
        self.assertFound(absent('ileocecal_valve'), {})  # 3.8 probe (d): the cecum holds the valve, not inside it
        self.assertFound(absent('stomach'), {})
        self.assertFound(absent('colon', 'anastomosis'), {})
        # a statement's place is no act place, and a denied reach is no reach
        denied = changed(lambda value: (value['anatomy'].append(anatomy('Y1', fact('surgically_absent', 'S4'),
                                                                        organ=[fact('descending_colon', 'S4')])),
                                        put(at(value, 'E3'), 'target.places', [fact('descending_colon', 'S7')]),
                                        value['sessions'][0]['reached'].append(
                                            fact('descending_colon', 'S5', state='negated'))))
        self.assertFound(denied, {})


# --- K5: person against performer; K6: instrument; K7: frame by role --------------------------------------------------


class K5Tests(Case):
    def people(self, role):
        def edit(value):
            value['people'].append(person('P3', role, 'S6'))
        return edit

    def performed(self, performer, person_id, role='referring', object_id='E2'):
        def edit(value):
            self.people(role)(value)
            item = at(value, object_id) if object_id.startswith('E') else section_at(value, object_id)
            item['performer'] = [fact(performer, 'S6')]
            item['performer_person'] = [fact(person_id, 'S6')]
        return changed(edit)

    def test_a_documenting_team_performer_named_as_a_person_of_another_role(self):
        conflict = {key(F.EVENT, 'E2', A.PERFORMER): {'person_conflict'},
                    key(F.EVENT, 'E2', A.PERFORMER_PERSON): {'person_conflict'}}
        self.assertFound(self.performed('documenting_team', 'P3', 'referring'), conflict)
        self.assertFound(self.performed('documenting_team', 'P3', 'pathologist'), conflict)
        for role in ('trainee', 'assistant', 'nurse', 'anesthesia', 'documenting_clinician'):
            with self.subTest(role=role):
                self.assertFound(self.performed('documenting_team', 'P3', role), {})

    def test_another_performer_named_as_the_documenting_clinician(self):
        conflict = {key(F.EVENT, 'E2', A.PERFORMER): {'person_conflict'},
                    key(F.EVENT, 'E2', A.PERFORMER_PERSON): {'person_conflict'}}
        self.assertFound(self.performed('other_clinician', 'P1'), conflict)  # P1's role: documenting_clinician
        self.assertFound(self.performed('other_facility', 'P1'), conflict)
        self.assertFound(self.performed('other_clinician', 'P3', 'referring'), {})

        def documenting_only_by_the_encounter(value):  # the encounter names P3 as the documenting clinician
            value['encounter']['documenting_clinician'] = [fact('P3', 'S3')]
        self.assertFound(changed(lambda value: (documenting_only_by_the_encounter(value), self.people('other')(value),
                                                at(value, 'E2').update(performer=[fact('other_clinician', 'S6')],
                                                                       performer_person=[fact('P3', 'S6')]))),
                         conflict)

    def test_a_sections_performer(self):
        self.assertFound(self.performed('documenting_team', 'P3', 'radiologist', object_id='N2'),
                         {key(F.SECTION, 'N2', A.PERFORMER): {'person_conflict'},
                          key(F.SECTION, 'N2', A.PERFORMER_PERSON): {'person_conflict'}})
        self.assertFound(self.performed('documenting_team', 'P2', object_id='N2'), {})  # P2 is the nurse


class K6Tests(Case):
    def test_a_point_the_endoscope_and_a_device_both_reached(self):
        def device(point, state='supported'):
            return changed(lambda value: value['sessions'][0].update(device_reached=[fact(point, 'S5', state=state)]))
        self.assertFound(device('cecum'), {key(F.SESSION, 'X1', A.REACHED): {'instrument_conflict'}})
        self.assertFound(device('terminal_ileum'), {})  # a guidewire beyond the endoscope (BF25)
        self.assertFound(device('cecum', 'negated'), {})


class K7Tests(Case):
    def test_a_history_part_framed_by_the_document(self):
        frame = changed(lambda value: section_at(value, 'N1').update(
            occasion=[fact('on_date_of_service', 'S2', link='document_frame')]))
        # and E6, N1's prior removal dated 2023, inherits that on_date_of_service: L1 demotes E6's relation (D193)
        self.assertFound(frame, {key(F.SECTION, 'N1', A.OCCASION): {'frame_role'},
                                 key(F.EVENT, 'E6', A.DATE_RELATION): {'literal_mismatch'}})
        placed = changed(lambda value: section_at(value, 'N1').update(
            occasion=[fact('on_date_of_service', 'S7', link='placing')],
            performer=[fact('documenting_team', 'S7', link='placing')]))
        self.assertFound(placed, {key(F.SECTION, 'N1', A.OCCASION): {'frame_role'},
                                  key(F.SECTION, 'N1', A.PERFORMER): {'frame_role'},
                                  key(F.EVENT, 'E6', A.DATE_RELATION): {'literal_mismatch'}})  # E6's 2023 again
        elsewhere = changed(lambda value: section_at(value, 'N1').update(
            occasion=[fact('earlier_date', 'S7', link='placing')], performer=[fact('other_facility', 'S7',
                                                                                   link='placing')]))
        self.assertFound(elsewhere, {})  # a placing sentence may place a history part elsewhere

    def test_each_framed_role_and_an_outside_record(self):
        for role in ('indication', 'medications', 'plan', 'history'):
            with self.subTest(role=role):
                self.assertFound(changed(lambda value, r=role: section_at(value, 'N2').update(
                    role=[fact(r, 'S5', link='section')])), {key(F.SECTION, 'N2', A.OCCASION): {'frame_role'},
                                                            key(F.SECTION, 'N2', A.PERFORMER): {'frame_role'}})
        outside = changed(lambda value: section_at(value, 'N2').update(owner=fact('outside_record', 'S5')))
        self.assertFound(outside, {key(F.SECTION, 'N2', A.OCCASION): {'frame_role'},
                                   key(F.SECTION, 'N2', A.PERFORMER): {'frame_role'}})
        offered = changed(lambda value: section_at(value, 'N2').update(
            role=[contradicted(('findings', 'S5'), ('history', 'S4'))]))
        self.assertIn(key(F.SECTION, 'N2', A.OCCASION), self.found(offered))
        self.assertFound(answer(), {})  # the findings part's occasion from the document frame


# --- K8: both polarities [R:HO-9] ----------------------------------------------------------------------------------------


class K8Tests(Case):
    def reach(self, *points):
        return changed(lambda value: value['sessions'][0].update(
            reached=[fact(point, 'S5', state=state) for point, state in points]))

    def test_a_reach_given_both_polarities_joins_into_one_fact_of_pass_1(self):
        findings = self.check(self.reach(('cecum', 'supported'), ('cecum', 'negated')))
        self.assertEqual(findings.joined, (cs.Joined(F.SESSION, 'X1', A.REACHED,
                                                     supported=(key(F.SESSION, 'X1', A.REACHED, 0),),
                                                     negated=(key(F.SESSION, 'X1', A.REACHED, 1),)),))
        # nothing is created and nothing demoted: both sides are pass 1's own facts, with no reason
        self.assertEqual((dict(findings.structure), dict(findings.consistency), dict(findings.literal),
                          dict(findings.qualified)), ({}, {}, {}, {}))

    def test_a_reach_inside_a_denied_place_joins_and_a_reach_holding_it_does_not(self):
        inside = self.check(self.reach(('cecum', 'supported'), ('colon', 'negated'))).joined
        self.assertEqual([(item.supported, item.negated) for item in inside],
                         [((key(F.SESSION, 'X1', A.REACHED, 0),), (key(F.SESSION, 'X1', A.REACHED, 1),))])
        # reached the colon and not the cecum: an incomplete colonoscopy, no contradiction
        self.assertEqual(self.check(self.reach(('colon', 'supported'), ('cecum', 'negated'))).joined, ())
        self.assertEqual(self.check(self.reach(('cecum', 'supported'), ('terminal_ileum', 'negated'))).joined, ())

    def test_stations_and_act_places(self):
        stations = changed(lambda value: value['sessions'][0].update(
            stations=[fact('rectum', 'S5'), fact('colon', 'S5'), fact('rectum', 'S5', state='negated')]))
        self.assertEqual(self.check(stations).joined, (cs.Joined(F.SESSION, 'X1', A.STATIONS,
                                                                 (key(F.SESSION, 'X1', A.STATIONS, 0),),
                                                                 (key(F.SESSION, 'X1', A.STATIONS, 2),)),))
        places = changed(lambda value: put(at(value, 'E2'), 'target.places', [
            fact('sigmoid_colon', 'S6'), fact('left_colon', 'S6', state='negated')]))
        self.assertEqual(self.check(places).joined, (cs.Joined(F.EVENT, 'E2', A.TARGET_PLACES,
                                                               (key(F.EVENT, 'E2', A.TARGET_PLACES, 0),),
                                                               (key(F.EVENT, 'E2', A.TARGET_PLACES, 1),)),))

    def test_only_act_places_join_and_a_statements_places_never_do(self):
        """3.1 K8 joins "act places" (the arbiter triage's repair 2b#3): the places of CLAIMED's act class, every event
        whose status pass 1 did not state negated, the examination included. The negated E3 ("Neither biopsy nor tattoo
        was performed.") given the sigmoid colon and, denied, the colon joins nothing: its two places stay two facts
        (a statement's negated place has no statement-phrased template, so it stays unestablished; fail-closed). The
        same two places on the act E2, and on the examination E1, join."""
        def places(event_id, unit):
            return changed(lambda value: put(at(value, event_id), 'target.places', [
                fact('sigmoid_colon', unit), fact('colon', unit, state='negated')]))
        self.assertEqual(self.check(places('E3', 'S7')).joined, ())
        for event_id, unit in (('E2', 'S6'), ('E1', 'S5')):
            with self.subTest(event=event_id):
                self.assertEqual(self.check(places(event_id, unit)).joined, (
                    cs.Joined(F.EVENT, event_id, A.TARGET_PLACES, (key(F.EVENT, event_id, A.TARGET_PLACES, 0),),
                              (key(F.EVENT, event_id, A.TARGET_PLACES, 1),)),))
        # an event whose status pass 1 gave as contradicted is no statement either (3.2.1 names the negated ones)
        offered = changed(lambda value: (
            put(at(value, 'E2'), 'target.places', [fact('sigmoid_colon', 'S6'), fact('colon', 'S6', state='negated')]),
            at(value, 'E2').update(status=contradicted(('performed', 'S6'), ('planned', 'S6')))))
        self.assertEqual([item.object for item in self.check(offered).joined], ['E2'])

    def test_a_chain_of_sides_is_one_group(self):
        joined = self.check(self.reach(('cecum', 'supported'), ('colon', 'negated'), ('ascending_colon', 'supported'),
                                       ('terminal_ileum', 'negated'))).joined
        self.assertEqual(joined, (cs.Joined(F.SESSION, 'X1', A.REACHED,
                                            (key(F.SESSION, 'X1', A.REACHED, 0), key(F.SESSION, 'X1', A.REACHED, 2)),
                                            (key(F.SESSION, 'X1', A.REACHED, 1),)),))


# --- L1: date literals [R:MO-5] ------------------------------------------------------------------------------------------


def relation(event_id: str, value: str, unit: str, state: str = 'supported', status: str = 'performed',
             **fields) -> dict:
    """An act of DATES told in ``unit``, its own date relation ``value`` citing that unit's whole words."""
    return event(event_id, [unit], fact('biopsy', unit), fact(status, unit), session=[fact('X1', unit)],
                 date_relation=[fact(value, unit, state=state)], **fields)


class L1Tests(Case):
    def literal(self, value: dict, at_key: xr.FactKey):
        return self.found(value, DATES).get(at_key, set())

    def test_the_date_of_service_equals_its_literal_and_is_the_claim_time_reference(self):
        dos = key(F.ENCOUNTER, '', A.DATE_OF_SERVICE)
        self.assertEqual(self.check(dated(), DATES).document_date, date(2026, 11, 9))
        wrong = dated(dos='2026-11-10')
        self.assertEqual(self.literal(wrong, dos), {'literal_mismatch'})
        self.assertIsNone(self.check(wrong, DATES).document_date)  # a failed literal sets no reference
        unworded = dated(dos_words='Date of service')
        self.assertEqual(self.literal(unworded, dos), {'literal_mismatch'})  # no literal to equal
        self.assertIsNone(self.check(dated(dos_state='not_stated'), DATES).document_date)

    def test_other_dates_at_year_month_and_day_precision(self):
        role = key(F.ENCOUNTER, '', A.OTHER_DATES_ROLE)
        cases = (('2023', 'S3', '2023', set()), ('2024', 'S3', '2023', {'literal_mismatch'}),
                 ('2026-03', 'S5', 'March 2026', set()), ('2026-04', 'S5', 'March 2026', {'literal_mismatch'}),
                 ('2026-10', 'S11', '10/2026', set()),
                 ('2026-11-08', 'S7', '11/08/2026', set()), ('2026-11-07', 'S7', '11/08/2026', {'literal_mismatch'}),
                 ('2026-11', 'S7', '11/08/2026', {'literal_mismatch'}),  # a month whose words state a day
                 ('2026', 'S6', 'November 2026', {'literal_mismatch'}))  # a year whose words state a month
        for value, unit, words, expected in cases:
            with self.subTest(value=value, words=words):
                self.assertEqual(self.literal(dated(other_dates=[(value, unit, words)]), role), expected)

    def test_an_acts_date_at_year_month_and_day_precision(self):
        date_key = key(F.EVENT, 'E2', A.DATE)
        for value, unit, expected in (('2023', 'S3', set()), ('2022', 'S3', {'literal_mismatch'}),
                                      ('2026-03', 'S5', set()), ('2026-03-01', 'S5', {'literal_mismatch'}),
                                      ('2026-11-08', 'S7', set()), ('2026-11-09', 'S7', {'literal_mismatch'})):
            with self.subTest(value=value):
                act = event('E2', [unit], fact('biopsy', unit), fact('performed', unit), date=[fact(value, unit)])
                self.assertEqual(self.literal(dated(act), date_key), expected)
        both = contradicted(('2026-11-08', 'S7'), ('2026-11-10', 'S9'))
        act = event('E2', ['S7'], fact('biopsy', 'S7'), fact('performed', 'S7'), date=[both])
        self.assertEqual(self.literal(dated(act), date_key), set())  # each side against its own words

    def test_on_date_of_service_needs_every_literal_to_hold_the_document_date_at_its_precision(self):
        """DECISIONS D193 (with 3.8 probe (b) and v1's D54): a day equal to the date of service, or a month or a year
        containing it; any other literal is literal_mismatch, a month or a year included."""
        mismatch, own = {'literal_mismatch'}, key(F.EVENT, 'E2', A.DATE_RELATION)
        for unit, expected in (('S8', set()), ('S7', mismatch), ('S9', mismatch), ('S12', set()),
                               ('S6', set()), ('S10', set()),  # November 2026 and 2026 hold 11/09/2026
                               ('S3', mismatch), ('S4', mismatch), ('S5', mismatch), ('S11', mismatch)):  # other ones
            with self.subTest(unit=unit):
                self.assertEqual(self.literal(dated(relation('E2', 'on_date_of_service', unit)), own), expected)

    def test_probe_b_a_2023_fails_on_date_of_service(self):
        """3.8 probe (b), the arbiter triage's 2b#1: the date of service is 11/09/2026 and E2's own on_date_of_service
        cites "Prior EGD in 2023." (S3); then, as 3.8 writes it, E2's relation has no time words (S12) and its date 2023
        cites "2023". Both are literal_mismatch on E2's relation; its date, which equals its words, is not."""
        cited = dated(relation('E2', 'on_date_of_service', 'S3'))
        self.assertEqual(self.found(cited, DATES), {key(F.EVENT, 'E2', A.DATE_RELATION): {'literal_mismatch'}})
        dated_2023 = dated(relation('E2', 'on_date_of_service', 'S12', date=[fact('2023', 'S3', words='2023')]))
        self.assertEqual(self.found(dated_2023, DATES), {key(F.EVENT, 'E2', A.DATE_RELATION): {'literal_mismatch'}})

    def test_only_a_supported_date_is_read_into_a_relation(self):
        """DECISIONS D193 and the arbiter triage's repair 2b#5: a NEGATED date is no evidence of when the act was done.
        E2's own on_date_of_service cites S12 (no literal) and its date is denied, 2026-11-08 citing "11/08/2026": no
        reason, and the relation stores no literal; the same date supported is literal_mismatch."""
        own = key(F.EVENT, 'E2', A.DATE_RELATION)
        denied = dated(relation('E2', 'on_date_of_service', 'S12',
                                date=[fact('2026-11-08', 'S7', state='negated', words='11/08/2026')]))
        self.assertEqual(self.found(denied, DATES), {})
        self.assertEqual(self.check(denied, DATES).literals[own], ())
        stated = dated(relation('E2', 'on_date_of_service', 'S12', date=[fact('2026-11-08', 'S7', words='11/08/2026')]))
        self.assertEqual(self.found(stated, DATES), {own: {'literal_mismatch'}})
        contradicted_date = dated(relation('E2', 'on_date_of_service', 'S12',
                                           date=[contradicted(('2026-11-08', 'S7'), ('2026-11-10', 'S9'))]))
        self.assertEqual(self.check(contradicted_date, DATES).literals[own], ())  # a contradicted date states none

    def test_earlier_date_needs_every_literal_to_end_before_it(self):
        mismatch, own = {'literal_mismatch'}, key(F.EVENT, 'E2', A.DATE_RELATION)
        for unit, expected in (('S3', set()), ('S5', set()), ('S11', set()), ('S7', set()),  # year, months, a day
                               ('S10', mismatch), ('S6', mismatch), ('S8', mismatch), ('S9', mismatch), ('S4', mismatch),
                               ('S12', set())):
            with self.subTest(unit=unit):
                self.assertEqual(self.literal(dated(relation('E2', 'earlier_date', unit)), own), expected)

    def test_later_date_needs_every_literal_to_start_after_it(self):
        mismatch, own = {'literal_mismatch'}, key(F.EVENT, 'E2', A.DATE_RELATION)
        for unit, expected in (('S4', set()), ('S9', set()), ('S10', mismatch), ('S6', mismatch), ('S8', mismatch),
                               ('S3', mismatch)):
            with self.subTest(unit=unit):
                act = relation('E2', 'later_date', unit, status='planned')
                self.assertEqual(self.literal(dated(act), own), expected)

    def test_an_acts_own_date_relation_reads_the_words_of_its_own_date(self):
        """The date relation's own words hold no literal (S12); its date's words (S3, "2023") are read with them."""
        act = relation('E2', 'on_date_of_service', 'S12', date=[fact('2026-11-08', 'S7', words='11/08/2026')])
        self.assertEqual(self.literal(dated(act), key(F.EVENT, 'E2', A.DATE_RELATION)), {'literal_mismatch'})
        earlier = relation('E2', 'earlier_date', 'S12', date=[fact('2023', 'S3', words='2023')])
        self.assertFound(dated(earlier), {}, DATES)
        stored = self.check(dated(earlier), DATES).literals[key(F.EVENT, 'E2', A.DATE_RELATION)]
        self.assertEqual(stored, (ct.StoredLiteral('2023', ct.Precision.YEAR),))

    def test_a_sections_occasion(self):
        occasion = key(F.SECTION, 'N0', A.OCCASION)
        self.assertEqual(self.literal(dated(occasion=fact('on_date_of_service', 'S2')), occasion), set())
        self.assertEqual(self.literal(dated(occasion=fact('on_date_of_service', 'S7')), occasion),
                         {'literal_mismatch'})
        self.assertEqual(self.literal(dated(occasion=fact('earlier_date', 'S3')), occasion), set())

    def test_at_claim_time_a_literal_that_meets_no_document_date_stops_nothing(self):
        """No document date: L1 still stores the literals, gives no reason at claim time, and never literal_unchecked
        (that is assess and read time's). The claim set depends on the revision and pass 1's bytes alone."""
        for no_date in (dated(relation('E2', 'on_date_of_service', 'S7'), dos_state='not_stated'),
                        dated(relation('E2', 'on_date_of_service', 'S7'), dos='2026-11-10')):
            findings = self.check(no_date, DATES)
            own = key(F.EVENT, 'E2', A.DATE_RELATION)
            self.assertNotIn(own, findings.literal)
            self.assertEqual(findings.literals[own], (ct.StoredLiteral('2026-11-08', ct.Precision.DAY),))
            self.assertNotIn('literal_unchecked', {reason.value for item in findings.literal.values()
                                                   for reason in item})

    def test_claim_time_takes_no_member_value(self):
        """[R:MO-5] the claim set depends on the revision and pass 1's bytes alone: check() is given the answer, the
        tables, the located words and the sections, and no date of any member; its reference is pass 1's own."""
        self.assertEqual(list(inspect.signature(cs.check).parameters), ['answer', 'vocabulary', 'words', 'containing'])
        findings = self.check(dated(relation('E2', 'on_date_of_service', 'S9')), DATES)
        self.assertEqual((findings.document_date, findings.literal[key(F.EVENT, 'E2', A.DATE_RELATION)]),
                         (date(2026, 11, 9), (R.LITERAL_MISMATCH,)))

    def test_only_a_stated_relation_is_judged(self):
        own = key(F.EVENT, 'E2', A.DATE_RELATION)
        denied = self.check(dated(relation('E2', 'on_date_of_service', 'S7', state='negated')), DATES)
        self.assertNotIn(own, denied.literal)
        self.assertEqual(denied.literals[own], (ct.StoredLiteral('2026-11-08', ct.Precision.DAY),))

    def test_l1_reads_only_the_located_words_never_the_unit_around_them(self):
        """N0's occasion cites S8 with the words "A biopsy was taken": the unit's date is not in its words."""
        worded = dated(occasion=fact('earlier_date', 'S8', words='A biopsy was taken'))
        self.assertEqual(self.check(worded, DATES).literals[key(F.SECTION, 'N0', A.OCCASION)], ())
        self.assertFound(worded, {}, DATES)
        unlocated = dated(occasion=fact('earlier_date', 'S8', words='no such words'))
        self.assertEqual(self.check(unlocated, DATES).literals[key(F.SECTION, 'N0', A.OCCASION)], ())


class InheritedDateTests(Case):
    """DECISIONS D193 (the arbiter triage's 2b#2): an event's own supported date is judged against its EFFECTIVE date
    relation. When pass 1 gave it none of its own, that is the occasion of the section its anchor lies in (1.5,
    ``containing``), read with the occasion's words and the event's own date's; the finding is keyed on the event's own
    date_relation slot, where settle keeps the relation the event inherits, and never on the section's fact."""
    ON = fact('on_date_of_service', 'S2', words='11/09/2026', link='document_frame')
    INHERITED = key(F.EVENT, 'E2', A.DATE_RELATION)

    def act(self, value='2023', unit='S3', words='2023', state='supported', **fields) -> dict:
        """E2, a biopsy told in S12 (no date literal) with no date relation of its own, its date ``value`` citing
        ``words`` in ``unit``."""
        return event('E2', ['S12'], fact('biopsy', 'S12'), fact('performed', 'S12'), session=[fact('X1', 'S12')],
                     date=[fact(value, unit, state=state, words=words)], **fields)

    def test_a_2023_date_under_an_inherited_on_date_of_service(self):
        value = dated(self.act(), occasion=self.ON)
        self.assertEqual(sections_of(geometry.Layout.of(DATES), value)['E2'], 'N0')
        self.assertNotIn(self.INHERITED, {item.key for item in self.read(value, DATES).facts})  # a silent slot
        self.assertFound(value, {self.INHERITED: {'literal_mismatch'}}, DATES)  # never N0's occasion
        lit, day, year = ct.StoredLiteral, ct.Precision.DAY, ct.Precision.YEAR
        literals = self.check(value, DATES).literals
        self.assertEqual(literals[self.INHERITED], (lit('2026-11-09', day), lit('2023', year)))  # N0's, then E2's own
        self.assertEqual(literals[key(F.SECTION, 'N0', A.OCCASION)], (lit('2026-11-09', day),))

    def test_probe_b_in_the_worked_example(self):
        """3.8 probe (b) in a Findings part: the snare E2 has no time words and inherits N2's on_date_of_service; its
        date 2023, citing the history's "2023", is literal_mismatch on E2's relation only."""
        value = changed(lambda item: put(at(item, 'E2'), 'date', [fact('2023', 'S4', words='2023')]))
        self.assertEqual(sections_of(geometry.Layout.of(TEXT), value)['E2'], 'N2')
        self.assertFound(value, {self.INHERITED: {'literal_mismatch'}})

    def test_a_date_that_holds_the_inherited_relation(self):
        later = fact('later_date', 'S4', words='Repeat EGD planned in 2027')
        for occasion, act in ((self.ON, self.act('2026-11-09', 'S8', '11/09/2026')),
                              (self.ON, self.act('2026-11', 'S6', 'November 2026')),
                              (fact('earlier_date', 'S3', words='Prior EGD in 2023'), self.act()),
                              (later, self.act('2027', 'S4', '2027'))):
            with self.subTest(occasion=occasion['value'], date=act['date'][0]['value']):
                self.assertFound(dated(act, occasion=occasion), {}, DATES)
        self.assertFound(dated(self.act('2026-11-09', 'S8', '11/09/2026'), occasion=later),
                         {self.INHERITED: {'literal_mismatch'}}, DATES)

    def test_an_own_relation_is_judged_and_nothing_is_inherited(self):
        own = self.act(date_relation=[fact('earlier_date', 'S12')])
        # E2's section only: K2's date arm would also find E2's own earlier date unlike its examination's inherited one
        self.assertFound(dated(own, occasion=self.ON), {}, DATES, containing={'E2': 'N0'})  # 2023 is earlier: it holds
        self.assertEqual(self.check(dated(own, occasion=self.ON), DATES, {'E2': 'N0'}).literals[self.INHERITED],
                         (ct.StoredLiteral('2023', ct.Precision.YEAR),))  # its own words and its date's only

    def test_nothing_is_inherited_without_a_supported_date_a_section_or_an_occasion(self):
        for value, containing in ((dated(self.act(state='negated'), occasion=self.ON), None),
                                  (dated(event('E2', ['S12'], fact('biopsy', 'S12'), fact('performed', 'S12')),
                                         occasion=self.ON), None),
                                  (dated(self.act(), occasion=self.ON), {}),  # no section holds its anchor
                                  (dated(self.act()), None)):  # its section states no occasion
            with self.subTest(value=value['events'][-1]['date'], containing=containing):
                findings = self.check(value, DATES, containing)
                self.assertNotIn(self.INHERITED, findings.literals)
                self.assertNotIn(self.INHERITED, findings.literal)

    def test_an_occasion_not_stated_or_no_document_date_stores_and_stops_nothing(self):
        """A denied occasion is stored and never judged (only a supported relation is); with no document date, the
        literals are stored for the re-judge, which a member's date then demotes [R:MO-5]."""
        denied = dated(self.act(), occasion=fact('on_date_of_service', 'S2', state='negated', words='11/09/2026',
                                                 link='document_frame'))
        self.assertFound(denied, {}, DATES)
        self.assertIn(self.INHERITED, self.check(denied, DATES).literals)
        undated = dated(self.act(), occasion=self.ON, dos_state='not_stated')
        findings = self.check(undated, DATES)
        self.assertEqual((findings.document_date, dict(findings.literal)), (None, {}))
        stored = findings.literals[self.INHERITED]
        self.assertEqual(cs.rejudge(ct.DateRelation.ON_DATE_OF_SERVICE, stored, date(2026, 11, 9)),
                         (R.LITERAL_MISMATCH,))  # the member's 11/09/2026 meets the act's 2023


class RejudgeTests(SimpleTestCase):
    """L1 re-judged at assess and read time against the effective date (a member's date takes precedence, dates.py),
    from the stored literals alone: it can only add reasons [R:MO-5]."""
    DAY, MONTH, YEAR = (ct.Precision.DAY, ct.Precision.MONTH, ct.Precision.YEAR)

    def test_on_date_of_service_re_judged_with_a_member_date(self):
        literals = (ct.StoredLiteral('2026-11-09', self.DAY),)
        on = ct.DateRelation.ON_DATE_OF_SERVICE
        self.assertEqual(cs.rejudge(on, literals, date(2026, 11, 9)), ())
        self.assertEqual(cs.rejudge(on, literals, date(2026, 11, 10)), (R.LITERAL_MISMATCH,))  # the member's date
        # a month or a year is judged at its own precision too (DECISIONS D193; 3.8 probe (b); v1's D54)
        self.assertEqual(cs.rejudge(on, (ct.StoredLiteral('2026-11', self.MONTH),), date(2027, 1, 2)),
                         (R.LITERAL_MISMATCH,))
        self.assertEqual(cs.rejudge(on, (ct.StoredLiteral('2023', self.YEAR),), date(2026, 11, 10)),
                         (R.LITERAL_MISMATCH,))
        self.assertEqual(cs.rejudge(on, (ct.StoredLiteral('2026-11', self.MONTH),), date(2026, 11, 10)), ())
        self.assertEqual(cs.rejudge(on, (ct.StoredLiteral('2026', self.YEAR),), date(2026, 11, 10)), ())
        # D67's shape: an EMR "In March 2024" filed on_date_of_service in a note with no date; the member enters one
        self.assertEqual(cs.rejudge(on, (ct.StoredLiteral('2024-03', self.MONTH),) * 2, date(2026, 11, 9)),
                         (R.LITERAL_MISMATCH,))

    def test_earlier_and_later_re_judged_at_day_month_and_year_precision(self):
        earlier, later = ct.DateRelation.EARLIER_DATE, ct.DateRelation.LATER_DATE
        member = date(2026, 11, 10)
        for relation_, value, precision, expected in (
                (earlier, '2026-11-09', self.DAY, ()), (earlier, '2026-11-10', self.DAY, (R.LITERAL_MISMATCH,)),
                (earlier, '2026-10', self.MONTH, ()), (earlier, '2026-11', self.MONTH, (R.LITERAL_MISMATCH,)),
                (earlier, '2025', self.YEAR, ()), (earlier, '2026', self.YEAR, (R.LITERAL_MISMATCH,)),
                (later, '2026-11-11', self.DAY, ()), (later, '2026-11-10', self.DAY, (R.LITERAL_MISMATCH,)),
                (later, '2026-12', self.MONTH, ()), (later, '2026-11', self.MONTH, (R.LITERAL_MISMATCH,)),
                (later, '2027', self.YEAR, ()), (later, '2026', self.YEAR, (R.LITERAL_MISMATCH,))):
            with self.subTest(relation=relation_, value=value):
                self.assertEqual(cs.rejudge(relation_, (ct.StoredLiteral(value, precision),), member), expected)

    def test_a_day_literal_that_meets_no_effective_date_is_unchecked(self):
        on = ct.DateRelation.ON_DATE_OF_SERVICE
        self.assertEqual(cs.rejudge(on, (ct.StoredLiteral('2026-11-09', self.DAY),), None), (R.LITERAL_UNCHECKED,))
        self.assertEqual(cs.rejudge(ct.DateRelation.EARLIER_DATE, (ct.StoredLiteral('2023', self.YEAR),), None), ())
        self.assertEqual(cs.rejudge(on, (), None), ())
        # D193 keeps literal_unchecked day-only: a month or a year with no effective date stays unjudged
        self.assertEqual(cs.rejudge(on, (ct.StoredLiteral('2026-11', self.MONTH), ct.StoredLiteral('2023', self.YEAR)),
                                    None), ())

    def test_re_judging_only_demotes(self):
        on = ct.DateRelation.ON_DATE_OF_SERVICE
        literals = (ct.StoredLiteral('2026-11-09', self.DAY),)
        # a claim-time mismatch against the document's date stays, whatever the member's date agrees with
        self.assertEqual(cs.rejudge(on, literals, date(2026, 11, 9), stored=(R.LITERAL_MISMATCH,)),
                         (R.LITERAL_MISMATCH,))
        self.assertEqual(cs.rejudge(on, literals, date(2026, 11, 10), stored=(R.QUALIFIED_HEDGED,)),
                         (R.LITERAL_MISMATCH, R.QUALIFIED_HEDGED))
        self.assertEqual(cs.rejudge(on, (ct.StoredLiteral('2026-13-01', self.DAY),), date(2026, 11, 9)),
                         (R.LITERAL_MISMATCH,))  # a stored literal that cannot be read back

    def test_the_claim_time_literals_round_trip_through_the_re_judge(self):
        with mock.patch.object(interpretation, 'LOCAL_SCHEMA_SHA256_V2', jsonschema.sha256_of(xs.LOCAL_SCHEMA_2)):
            layout = geometry.Layout.of(DATES)
            read = xr.read(json.dumps(dated(relation('E2', 'on_date_of_service', 'S8'))), len(layout.units))
            findings = cs.check(read, VOCABULARY, located(layout), {})
        own = key(F.EVENT, 'E2', A.DATE_RELATION)
        self.assertNotIn(own, findings.literal)  # at claim time, against the document's 11/09/2026
        stored = findings.literals[own]
        self.assertEqual(cs.rejudge(ct.DateRelation.ON_DATE_OF_SERVICE, stored, findings.document_date), ())
        self.assertEqual(cs.rejudge(ct.DateRelation.ON_DATE_OF_SERVICE, stored, date(2026, 11, 12)),
                         (R.LITERAL_MISMATCH,))  # a member's other date demotes it at assess time


# --- Q1: qualifiers -------------------------------------------------------------------------------------------------------


class Q1Tests(Case):
    def test_every_qualifier_but_approximate(self):
        for qualifier in ct.Qualifier:
            with self.subTest(qualifier=qualifier):
                value = changed(lambda item, q=qualifier.value: at(item, 'E2').update(
                    kind=fact('snare', 'S6', qualifiers=[q])))
                expected = {} if qualifier is ct.Qualifier.APPROXIMATE else {
                    key(F.EVENT, 'E2', A.KIND): {f'qualified:{qualifier.value}'}}
                self.assertFound(value, expected)

    def test_qualifiers_on_any_fact_and_several_at_once(self):
        value = changed(lambda item: (
            section_at(item, 'N1').update(occasion=[fact('earlier_date', 'S4', words='Prior colonoscopy in 2023',
                                                         link='section', qualifiers=['reported', 'hedged'])]),
            item['sessions'][0].update(reached=[fact('cecum', 'S5', qualifiers=['approximate', 'partial'])])))
        self.assertFound(value, {key(F.SECTION, 'N1', A.OCCASION): {'qualified:hedged', 'qualified:reported'},
                                 key(F.SESSION, 'X1', A.REACHED): {'qualified:partial'}})


# --- what a finding never does ---------------------------------------------------------------------------------------------


def _shape(value):
    """A comparable copy of a read answer: the parsed JSON and every read record."""
    return copy.deepcopy((value.answer, value.facts, value.citations, value.members, value.doubts))


CHECK_REASONS = frozenset({R.SESSION_INCONSISTENT, R.SESSION_CONFLICT, R.SESSION_UNREACHABLE, R.ANATOMY_CONFLICT,
                           R.PERSON_CONFLICT, R.INSTRUMENT_CONFLICT, R.FRAME_ROLE, R.LITERAL_MISMATCH,
                           R.QUALIFIED_HEDGED, R.QUALIFIED_CONDITIONAL, R.QUALIFIED_REPORTED, R.QUALIFIED_PARTIAL,
                           R.QUALIFIED_NAMED_ONLY, R.QUALIFIED_RESTATEMENT_ONLY, R.QUALIFIED_REFERENCE_ONLY})


def _pick(enumeration, index: int) -> str:
    members = list(enumeration)
    return members[index % len(members)].value


def _event_at(value: dict, index: int) -> dict:
    return value['events'][index % len(value['events'])]


_UNITS = [f'S{k}' for k in range(1, 10)]
_STATES = ('supported', 'negated')
EDITS = (
    lambda v, i, j: _event_at(v, i).update(status=fact(_pick(ct.Status, j), 'S6', state=_STATES[j % 2])),
    lambda v, i, j: _event_at(v, i).update(kind=fact(_pick(ct.Kind, j), 'S6')),
    lambda v, i, j: put(_event_at(v, i), 'scope.breadth', [fact(_pick(ct.Breadth, j), 'S7')]),
    lambda v, i, j: put(_event_at(v, i), 'scope.excepts', [v['events'][j % len(v['events'])]['id']]),
    lambda v, i, j: put(_event_at(v, i), 'yield', [fact(_pick(ct.Material, j), 'S6', state=_STATES[i % 2])]),
    lambda v, i, j: v['sessions'][0].update(kind=fact(_pick(ct.SessionKind, j), 'S1')),
    lambda v, i, j: v['sessions'][0]['reached'].append(fact(_pick(ct.Extent, j), 'S5', state=_STATES[i % 2]))
    if len(v['sessions'][0]['reached']) < 8 else None,
    lambda v, i, j: v['sessions'][0]['stations'].append(fact(_pick(ct.Station, j), 'S5', state=_STATES[i % 2]))
    if len(v['sessions'][0]['stations']) < 7 else None,
    lambda v, i, j: v['anatomy'].append(anatomy(f'Y{len(v["anatomy"]) + 1}', fact(_pick(ct.AnatomyType, i), 'S4'),
                                                organ=[fact(_pick(ct.Landmark, j), 'S4')]))
    if len(v['anatomy']) < 4 else None,
    lambda v, i, j: _event_at(v, i).update(performer=[fact(_pick(ct.Performer, j), 'S6')],
                                           performer_person=[fact(('P1', 'P2')[j % 2], 'S6')]),
    lambda v, i, j: _event_at(v, i).update(date_relation=[fact(_pick(ct.DateRelation, j), _UNITS[i % 9],
                                                               state=_STATES[j % 2])]),
    lambda v, i, j: _event_at(v, i).update(date=[fact(('2023', '2026-11-09', '2026-11', '2027')[j % 4],
                                                      ('S4', 'S2')[i % 2])]),
    lambda v, i, j: _event_at(v, i).update(kind=fact(_pick(ct.Kind, i), 'S6', qualifiers=[_pick(ct.Qualifier, j)])),
    lambda v, i, j: v['doubts'].append(doubt(_pick(ct.DoubtAbout, i), [_event_at(v, j)['id']],
                                             basis=_pick(ct.DoubtBasis, j))) if len(v['doubts']) < 8 else None,
    lambda v, i, j: _event_at(v, i).update(part_of=[fact(_event_at(v, j)['id'], 'S6')] if j % 3 else [],
                                           part_relation=[fact(_pick(ct.PartRelation, j), 'S6')] if j % 2 else []),
    lambda v, i, j: v['sessions'][0].update(examination=[fact(_event_at(v, j)['id'], 'S5')]),
    lambda v, i, j: v['sections'][i % 4].update(role=[fact(_pick(ct.SectionRole, j), 'S4')],
                                                occasion=[fact(_pick(ct.DateRelation, i), _UNITS[j % 9],
                                                               link=_pick(ct.Link, j))]),
    lambda v, i, j: v['sessions'][0]['device_reached'].append(fact(_pick(ct.Extent, j), 'S5'))
    if len(v['sessions'][0]['device_reached']) < 8 else None,
    # a point the base reach (the cecum) is, or lies inside, denied: K8's join; or a point it is not inside
    lambda v, i, j: v['sessions'][0]['reached'].append(fact(('cecum', 'colon', 'right_colon', 'terminal_ileum')[j % 4],
                                                            'S5', state='negated'))
    if len(v['sessions'][0]['reached']) < 8 else None,
    # an event's place and, denied, the place holding it (or another): K8 joins them on an act, never on a statement
    lambda v, i, j: put(_event_at(v, i), 'target.places', [
        fact(('sigmoid_colon', 'cecum', 'rectum')[j % 3], 'S6'),
        fact(('colon', 'right_colon', 'stomach')[(i + j) % 3], 'S6', state='negated')]),
)


class NeverChangesTests(Case):
    def test_the_answer_is_left_exactly_as_read_and_findings_hold_no_value(self):
        value = changed(lambda item: (
            put(at(item, 'E2'), 'yield', [fact('stones', 'S6')]),
            item['sessions'][0].update(reached=[fact('cecum', 'S5'), fact('cecum', 'S5', state='negated')]),
            item['anatomy'].append(anatomy('Y1', fact('surgically_absent', 'S4'), organ=[fact('colon', 'S4')])),
            put(at(item, 'E2'), 'date_relation', [fact('earlier_date', 'S6', qualifiers=['hedged'])])))
        read = self.read(value)
        before = _shape(read)
        layout = geometry.Layout.of(TEXT)
        findings = cs.check(read, VOCABULARY, located(layout), sections_of(layout, value))
        self.assertEqual(_shape(read), before)
        self.assertTrue(findings.structure and findings.consistency and findings.joined and findings.qualified)
        hints = {field.name: field.type for field in dataclasses.fields(cs.Findings)}
        self.assertEqual(hints, {
            'structure': 'Mapping[FactKey, tuple[Reason, ...]]',  # K1's reasons are types.Reason members (D186)
            'consistency': 'Mapping[FactKey, tuple[Reason, ...]]', 'literal': 'Mapping[FactKey, tuple[Reason, ...]]',
            'literals': 'Mapping[FactKey, tuple[StoredLiteral, ...]]',
            'qualified': 'Mapping[FactKey, tuple[Reason, ...]]', 'joined': 'tuple[Joined, ...]',
            'document_date': 'date | None'})
        with self.assertRaises(TypeError):
            findings.consistency[key(F.EVENT, 'E2', A.SESSION)] = (R.SESSION_CONFLICT,)

    def test_k8_creates_nothing_it_joins_two_facts_pass_1_reported(self):
        read = self.read(changed(lambda item: item['sessions'][0].update(
            reached=[fact('cecum', 'S5'), fact('colon', 'S5', state='negated')])))
        findings = cs.check(read, VOCABULARY, lambda source: None)
        (joined,) = findings.joined
        states = {item.key: item.fact.state for item in read.facts}
        self.assertEqual([states[item] for item in joined.supported], [ct.FactState.SUPPORTED])
        self.assertEqual([states[item] for item in joined.negated], [ct.FactState.NEGATED])
        self.assertEqual(len(read.facts), len(_shape(read)[1]))  # no fact added to the answer

    @hypothesis.settings(max_examples=150, deadline=None, derandomize=True,
                         suppress_health_check=[hypothesis.HealthCheck.too_slow])
    @hypothesis.given(st.lists(st.tuples(st.integers(0, len(EDITS) - 1), st.integers(0, 63), st.integers(0, 63)),
                               max_size=8))
    def test_property_findings_name_existing_facts_with_closed_reasons_and_change_nothing(self, edits):
        value = answer()
        for which, first, second in edits:
            EDITS[which](value, first, second)
        found = xr.read(json.dumps(value), 9)
        hypothesis.assume(isinstance(found, xr.ReadAnswer))
        before = _shape(found)
        layout = geometry.Layout.of(TEXT)
        findings = cs.check(found, VOCABULARY, located(layout), sections_of(layout, value))
        self.assertEqual(_shape(found), before)
        keys = {item.key for item in found.facts} | {item.key for item in found.members}
        states = {item.key: item.fact.state for item in found.facts}
        # L1's per-event key (D193): the silent date_relation slot of an event whose own date is supported
        inherited = {key(F.EVENT, item['id'], A.DATE_RELATION) for item in value['events']
                     if key(F.EVENT, item['id'], A.DATE_RELATION) not in keys
                     and states.get(key(F.EVENT, item['id'], A.DATE)) is ct.FactState.SUPPORTED}
        named = [*findings.structure, *findings.consistency, *findings.literal, *findings.qualified,
                 *findings.literals]
        self.assertLessEqual(set(named), keys | inherited)
        self.assertTrue(all(isinstance(reason, ct.Reason) and reason in K1_REASONS
                            for item in findings.structure.values() for reason in item))
        for mapping in (findings.consistency, findings.literal, findings.qualified):
            self.assertTrue(all(isinstance(reason, ct.Reason) and reason in CHECK_REASONS for item in mapping.values()
                                for reason in item))
        for joined in findings.joined:
            if joined.family is F.EVENT:  # act places only (2b#3): never a statement's
                self.assertIsNot(states.get(key(F.EVENT, joined.object, A.STATUS)), ct.FactState.NEGATED)
            self.assertTrue(joined.supported and joined.negated)
            self.assertTrue(all(states[item] is ct.FactState.SUPPORTED for item in joined.supported))
            self.assertTrue(all(states[item] is ct.FactState.NEGATED for item in joined.negated))
            self.assertEqual({(item.family, item.object, item.attribute) for item in
                              (*joined.supported, *joined.negated)}, {(joined.family, joined.object,
                                                                       joined.attribute)})
        self.assertEqual(cs.check(found, VOCABULARY, located(layout), sections_of(layout, value)), findings)


# --- the module: 5.7 measure 4, a fresh import, mypy ---------------------------------------------------------------------


TEXT_MODULES = ('segment', 'geometry', 'fold', 'date_literals')  # contract's text modules (5.7 measure 4)


def words_never_decide(source: str) -> list:
    """WordsNeverDecide as it binds contract/consistency.py (5.7 measure 4): no import of re, regex, unicodedata,
    difflib, fnmatch, lexicon, literals, a retired v1 module (here: any module of studio.interpretation outside the new
    path's contract and engine packages) or contract's text modules but date_literals; no call of a string method of its
    list on a non-literal receiver; no in or not in with a string-constant operand; no reading.text or revision.text."""
    tree, out = ast.parse(source), []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ''] + [f'{node.module}.{alias.name}' for alias in node.names]
        for name in names:
            parts = name.split('.')
            if parts[0] in ('re', 'regex', 'unicodedata', 'difflib', 'fnmatch'):
                out.append(f'imports {name}')
            if parts[:3] == ['studio', 'interpretation', 'contract'] and len(parts) > 3 and \
                    parts[3] in TEXT_MODULES and parts[3] != 'date_literals':
                out.append(f'imports a text module {name}')
            if parts[:2] == ['studio', 'interpretation'] and len(parts) > 2 and parts[2] not in ('contract', 'engine'):
                out.append(f'imports {name}')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in STR_METHODS \
                and not isinstance(node.func.value, ast.Constant):
            out.append(f'calls .{node.func.attr}()')
        if isinstance(node, ast.Compare) and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            operands = [node.left, *node.comparators]
            if any(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in operands) or any(
                    isinstance(item, (ast.Tuple, ast.List, ast.Set)) and any(
                        isinstance(element, ast.Constant) and isinstance(element.value, str) for element in item.elts)
                    for item in operands):
                out.append(f'tests membership against a string at line {node.lineno}')
        if isinstance(node, ast.Attribute) and node.attr == 'text' and isinstance(node.value, ast.Name) and \
                node.value.id in ('reading', 'revision'):
            out.append(f'reads {node.value.id}.text')
    return out


class ModuleTests(SimpleTestCase):
    source = MODULE.read_text(encoding='utf-8')

    def test_words_never_decide_holds_and_refuses_each_planted_control(self):
        self.assertEqual(words_never_decide(self.source), [])
        for plant in ('import re\n', 'from studio.interpretation.contract import geometry\n',
                      'from studio.interpretation import lexicon\n', 'X = lambda value: value.startswith("no")\n',
                      'Y = lambda value: "no" in value\n', 'Z = lambda reading: reading.text\n'):
            with self.subTest(plant=plant):
                self.assertTrue(words_never_decide(self.source + '\n' + plant))

    def test_no_word_lists(self):
        self.assertEqual(measure_4(self.source, engine=False), [])
        self.assertTrue(measure_4(self.source + "\nNEGATORS = ('no', 'neither')\n", engine=False))  # the control

    def test_the_one_text_module_is_date_literals_and_the_engine_is_read_by_the_type_checker_only(self):
        """The module's run-time imports are contract's (date_literals the one text module); its one import of the
        engine is engine/anatomy.py's Region, under TYPE_CHECKING, for the Vocabulary's types (DECISIONS D192), so the
        step keeps 1b and 1c as its only dependencies at run time (the seam DECISIONS D207 accepts)."""
        tree = ast.parse(self.source)
        guarded = [node for node in tree.body if isinstance(node, ast.If) and isinstance(node.test, ast.Name)
                   and node.test.id == 'TYPE_CHECKING']
        self.assertEqual(len(guarded), 1)
        typed = {(node.module, alias.name) for node in ast.walk(guarded[0]) if isinstance(node, ast.ImportFrom)
                 for alias in node.names}
        self.assertEqual(typed, {('studio.interpretation.engine.anatomy', 'Region')})
        inside = set(ast.walk(guarded[0]))
        runtime = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                   and node not in inside]
        imported = {node.module for node in runtime if isinstance(node, ast.ImportFrom)}
        imported |= {alias.name for node in runtime if isinstance(node, ast.Import) for alias in node.names}
        studio_modules = sorted(name for name in imported if name and name.startswith('studio'))
        self.assertEqual(studio_modules, ['studio.interpretation.contract', 'studio.interpretation.contract.extract_read',
                                          'studio.interpretation.contract.types'])
        named = {alias.name for node in runtime if isinstance(node, ast.ImportFrom)
                 and node.module == 'studio.interpretation.contract' for alias in node.names}
        self.assertEqual(named, {'date_literals', 'extract_schema'})

    def test_a_fresh_interpreter_loads_no_v1_module(self):
        code = ('import sys\n'
                'import studio.interpretation.contract.consistency\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=60, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().split(','), [
            'studio', 'studio.interpretation', 'studio.interpretation.contract',
            'studio.interpretation.contract.consistency', 'studio.interpretation.contract.date_literals',
            'studio.interpretation.contract.extract_read', 'studio.interpretation.contract.extract_schema',
            'studio.interpretation.contract.jsonschema', 'studio.interpretation.contract.types', 'studio.participants',
            'studio.participants.prompt', 'studio.participants.reading', 'studio.types'])

    def test_k1s_reasons_are_types_reason_members_and_every_other_reason_is_closed(self):
        """DECISIONS D186: types.Reason holds K1's fourteen reasons, of Structure's values and in its order (3.1 K1's),
        right after extent_inferred; each rule finds its own member (``_STRUCTURE_REASONS``), and K1Tests and
        NeverChangesTests show Findings.structure holding them. Every other reason the module names is closed."""
        self.assertEqual(len(cs.Structure), 14)
        self.assertTrue(all(rule.value == f'structure_{rule.name.lower()}' for rule in cs.Structure))
        self.assertEqual(tuple(ct.Reason(rule.value) for rule in cs.Structure), K1_REASONS)
        reasons = list(ct.Reason)
        after = reasons.index(R.EXTENT_INFERRED) + 1
        self.assertEqual(tuple(reasons[after:after + len(K1_REASONS)]), K1_REASONS)
        self.assertEqual(dict(cs._STRUCTURE_REASONS), dict(zip(cs.Structure, K1_REASONS)))
        produced = {node.attr for node in ast.walk(ast.parse(self.source)) if isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name) and node.value.id == 'Reason'}
        self.assertLessEqual({getattr(ct.Reason, name) for name in produced}, set(CHECK_REASONS) | {
            R.LITERAL_UNCHECKED})

    def test_no_citation_names_a_report_the_harness_refused(self):
        """DECISIONS D207: the harness refused every builder's report, so a citation of it pointed nowhere; the module
        and this file cite the DECISIONS entry that records each reading (the arbiter triage's repair 2b#8)."""
        refused = '.'.join(('REPORT', 'md'))
        for path in (MODULE, Path(__file__)):
            with self.subTest(path=path.name):
                self.assertNotIn(refused, path.read_text(encoding='utf-8'))

    def test_mypy_strict_passes_on_the_module(self):
        result = subprocess.run(
            [sys.executable, '-m', 'mypy', '--strict', '--follow-imports=silent', '--cache-dir', os.devnull,
             'studio/interpretation/contract/consistency.py'], capture_output=True, text=True, timeout=300, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 1 source file', result.stdout)


# --- the Vocabulary: its interface and the ruled tables (DECISIONS D191, D192) -------------------------------------------

# Settle's wiring of the real tables (the hand-off 2b:R2), and two tables of v1's region NAMES where Region members
# belong: what K3 would silently ignore, and what the Vocabulary's types (D192) make the type checker refuse.
WIRED = '''\
from studio.interpretation.contract import consistency as cs
from studio.interpretation.contract.types import Kind, SessionKind
from studio.interpretation.engine import anatomy, catalogue, requirements, requirements_table


def family_admits(family: SessionKind, kind: Kind) -> bool:
    return kind in requirements_table.FAMILY_KINDS.get(family, frozenset())


VOCABULARY = cs.Vocabulary(contains=anatomy.contains, region=anatomy.region, reach=catalogue.FAMILY_REACH,
                           family_admits=family_admits, covers=catalogue.covers,
                           endoscopic=catalogue.ENDOSCOPIC_FAMILIES, extraction=requirements.EXTRACTION_KINDS)
'''
NAMES = '''\
from studio.interpretation.contract import consistency as cs
from studio.interpretation.contract.types import Landmark, SessionKind
from wired import VOCABULARY


def region_name(landmark: Landmark) -> str:
    return landmark.value


BY_NAME = cs.Vocabulary(VOCABULARY.contains, region_name, VOCABULARY.reach, VOCABULARY.family_admits,
                        VOCABULARY.covers, VOCABULARY.endoscopic, VOCABULARY.extraction)
NAMED_REACH = cs.Vocabulary(VOCABULARY.contains, VOCABULARY.region, {SessionKind.EGD: frozenset({'stomach'})},
                            VOCABULARY.family_admits, VOCABULARY.covers, VOCABULARY.endoscopic, VOCABULARY.extraction)
'''


class VocabularyTests(Case):
    def test_the_vocabulary_is_typed_over_the_ruled_tables(self):
        """K2's kind arm reads ``family_admits``, the family-kinds table (DECISIONS D191), never
        catalogue.family_codes_act; K3's region and reach are typed over Landmark, SessionKind and engine/anatomy's
        Region, never Hashable (DECISIONS D192). region may answer None, as engine/anatomy.region does for the
        landmarks REGION_OF places in no region."""
        self.assertEqual([(field.name, field.type) for field in dataclasses.fields(cs.Vocabulary)], [
            ('contains', 'Callable[[Place, Place], bool]'), ('region', 'Callable[[Landmark], Region | None]'),
            ('reach', 'Mapping[SessionKind, frozenset[Region]]'),
            ('family_admits', 'Callable[[SessionKind, Kind], bool]'), ('covers', 'Callable[[Kind, Kind], bool]'),
            ('endoscopic', 'frozenset[SessionKind]'), ('extraction', 'frozenset[Kind]')])
        self.assertIsNone(engine_anatomy.region(ct.Landmark.ANASTOMOSIS))  # why region's result is optional

    def test_the_type_checker_takes_the_wiring_and_refuses_region_names(self):
        """mypy --strict accepts settle's wiring of the real tables and refuses both tables of region names, so a
        reach K3 could never meet (the review's I2: silently inert) fails before any document is read (D192)."""
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'wired.py').write_text(WIRED, encoding='utf-8')
            Path(folder, 'names.py').write_text(NAMES, encoding='utf-8')
            result = subprocess.run(
                [sys.executable, '-m', 'mypy', '--strict', '--follow-imports=silent', '--cache-dir', os.devnull,
                 str(Path(folder, 'wired.py')), str(Path(folder, 'names.py'))],
                capture_output=True, text=True, timeout=300, cwd=APP, env={**os.environ, 'MYPYPATH': str(APP)})
        errors = [line for line in result.stdout.splitlines() if ': error:' in line]
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse([line for line in errors if 'wired.py' in line], result.stdout)
        self.assertEqual(sorted({line.split(':')[1] for line in errors if 'names.py' in line}), ['10', '12'],
                         result.stdout)  # NAMES' line 10, the region of names; line 12, the reach of names

    def test_the_tables_equal_v1s_where_the_checks_read_them(self):
        """Steps 1e and 1f port v1's tables by value; here, where K1-K4 and K8 read them: containment, the regions,
        K3's reach (v1's FAMILY_REGIONS, D192), covers, the endoscopic families and the extraction kinds."""
        for outer in ct.Landmark:
            for inner in ct.Landmark:
                if outer.value in v1_lexicon.CONTAINS and inner.value in v1_lexicon.CONTAINS:
                    self.assertEqual(VOCABULARY.contains(outer, inner), v1_lexicon.contains(outer.value, inner.value))
        for landmark in ct.Landmark:
            if landmark.value in v1_mapping.REGION_OF:
                region = VOCABULARY.region(landmark)
                self.assertEqual(region.value if region is not None else '', v1_mapping.region(landmark.value))
        self.assertEqual({family.value: frozenset(region.value for region in regions)
                          for family, regions in VOCABULARY.reach.items()}, V1_REACH)
        kinds = [kind for kind in ct.Kind if kind is not ct.Kind.OTHER]  # other has no catalogue kind (1e's covers)
        for statement in kinds:
            for act in kinds:
                self.assertEqual(VOCABULARY.covers(statement, act), v1_mapping.covers(statement.value, act.value),
                                 (statement, act))
        self.assertFalse(VOCABULARY.covers(ct.Kind.OTHER, ct.Kind.OTHER))  # fail-closed: K1's exceptive rule demotes
        self.assertEqual(VOCABULARY.endoscopic,
                         frozenset(ct.SessionKind(name[3:]) for name in v1_mapping.ENDOSCOPIC_FAMILIES))
        self.assertEqual(VOCABULARY.extraction, V1_EXTRACTION)

    def test_k8_k4_k2_and_k1_with_the_engine_tables(self):
        """Values v1 lacks (the third portion of the duodenum, DECISIONS D204) and the family-kinds table (D191)."""
        reach = changed(lambda value: value['sessions'][0].update(
            reached=[fact('cecum', 'S5'), fact('colon', 'S5', state='negated'), fact('third_portion_duodenum', 'S5'),
                     fact('duodenum', 'S5', state='negated')]))
        self.assertEqual([(item.supported, item.negated) for item in self.check(reach).joined],
                         [((key(F.SESSION, 'X1', A.REACHED, 0),), (key(F.SESSION, 'X1', A.REACHED, 1),)),
                          ((key(F.SESSION, 'X1', A.REACHED, 2),), (key(F.SESSION, 'X1', A.REACHED, 3),))])
        colectomy = changed(lambda value: value['anatomy'].append(
            anatomy('Y1', fact('surgically_absent', 'S4'), organ=[fact('colon', 'S4')])))
        self.assertEqual(set(self.found(colectomy)), {key(F.ANATOMY, 'Y1', A.TYPE), key(F.ANATOMY, 'Y1', A.ORGAN),
                                                      key(F.SESSION, 'X1', A.REACHED),
                                                      key(F.EVENT, 'E2', A.TARGET_PLACES)})
        cannulation = changed(lambda value: (value['sessions'].append(session('X2', fact('ercp', 'S1'))),
                                             at(value, 'E5').update(kind=fact('cannulation', 'S9'),
                                                                    session=[fact('X2', 'S9')])))
        self.assertEqual(self.found(cannulation), {})  # an ERCP session holds its cannulation (D191)
        self.assertFound(changed(lambda value: put(at(value, 'E2'), 'yield', [fact('stones', 'S6')])),
                         {key(F.EVENT, 'E2', A.YIELD): {'structure_yield'}})
