"""Design v2's persisted inventory (docs/gemini-migration/FINAL-V2.md 1.7, 3.1 B1, 3.2.4, 6.2 and 6.3; step 1d of its
8.1), TEXT-ONLY and SYNTHETIC: interpretation/store.py's v2 writer and reader, beside v1's, which stays as it was.

What is proved here:
- a read row: its fields (BINDINGS_V2 with the appraisal run, so its sha256 binds both runs; the claim list's sha256 in
  the report), a round trip through JSON, the model's columns and PostgreSQL, contract/types records stored as their
  JSON, and the report completed with the bindings or refused when it names others;
- load_v2 refuses every unknown version (v1's pair included: v2 never reads a v1 row), every unknown shape, every closed
  value it does not know, every hash mismatch, and a verdict read against another claim than the one made for its fact
  (3.2.4 [R:MO-5]); it reads every shipped v2 version pair as stored, its shapes pinned (6.2 [R:MO-5]);
- an established fact rests on the row itself - a supports verdict with no qualifier and at least one evidence unit,
  every unit it cites in the row's units table, an id naming an object of the row - and is read against its own
  control, about its attribute or the partner 3.2.3 writes it in; a pair control asks a place or a lesion id (arbiter
  triage 1d#3, 1d#4, 2d#7; DECISIONS D186);
- textfree_v2 gives the engine the events with every words record as its offsets and no text (DECISIONS D188);
- pass 1's refusal stages and sentence and the ISO date shapes are contract/extract_read's own (triage 1d#6, 5.7);
- row_v2 refuses any stored words that are not the revision text's own slice, and any unit beyond the text (P9, B1);
- there is no refused pass-2 row: refused_row_v2 takes no appraisal run, a refused row that names one is refused, a read
  row must name one, and a refused row's stage is one of pass 1's (6.3);
- the v2 reader executes contract/ and the standard library only - no line of schema, read, studio.types or v1's reader
  (a trace, with positive controls) - and v1's reader is kept as store._v1_reader.
Every document here is written for this test: no real patient, no development or acceptance document.
"""
from __future__ import annotations

import ast
import copy
import datetime
import hashlib
import inspect
import json
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from studio import types as studio_types
from studio.interpretation import (INTERPRETATION_PAIR, INTERPRETATION_VERSION, INVENTORY_VERSION,
                                   INVENTORY_VERSION_V2, read, store)
from studio.interpretation.contract import claims as contract_claims
from studio.interpretation.contract import extract_read
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import types as et
from studio.models import EventInventory, ProviderRun, SourceRevision
from tests.support import factories as f

store._v2()  # the v2 shapes are built on first use (contract/ is imported then); the tests below read them
APP = Path(__file__).resolve().parents[2]
STORE = APP / 'studio' / 'interpretation' / 'store.py'
CONTRACT = APP / 'studio' / 'interpretation' / 'contract'

ENCOUNTER = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e1001'
REVISION = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e1002'
RUN = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e1003'
APPRAISAL_RUN = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e1004'
REQUEST_SHA256, RESPONSE_SHA256 = '2' * 64, '3' * 64
APPRAISAL_REQUEST_SHA256, APPRAISAL_RESPONSE_SHA256 = '4' * 64, '5' * 64

# The synthetic revision (no real patient; written for this test), one unit per line.
LINES = (
    'SYNTHETIC COLONOSCOPY REPORT - FICTIONAL PATIENT - NOT FOR CLINICAL USE',
    'Date of service: 11/09/2026',
    'Endoscopist: Synthetic Endoscopist, MD (fictional)',
    'History: Prior colonoscopy in 2023.',
    'Findings: The colonoscope was advanced to the cecum.',
    'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.',
    'Neither biopsy nor tattoo was performed.',
    'The ileocolic anastomosis was patent.',
    'Impression: Polyp removed.',
)
TEXT = '\n'.join(LINES) + '\n'
TEXT_SHA256 = hashlib.sha256(TEXT.encode('utf-8')).hexdigest()
DOCUMENT_WORDS = ('sessile polyp', 'Synthetic Endoscopist', 'colonoscope', 'anastomosis')  # never in an error

# The pinned shapes of every v2 version pair store.READ_VERSIONS holds (store.shape_signature_v2): a change here is a
# change in how a STORED inventory reads. Until gemini-inventory@2 first stores a row on a served site, a deliberate
# change of its shapes (an enumeration of contract/types included) updates this pin in the same commit; once it has, a
# change needs a new INVENTORY_VERSION beside the shipped pair, never an edit of its shapes (FINAL-V2 6.1, 6.2;
# DECISIONS D202). Recomputed with the claim rules of triage 1d#4 and 2d#7 (CONTROL_ATTRIBUTES and what a pair control
# asks), from int0's 17ad573f... (D186's Reason), which the same signature without those two entries still gives.
SHAPE_PINS = {(INTERPRETATION_PAIR, INVENTORY_VERSION_V2):
              'ab62877bfd29ae97e6d8d4e48b58bf106b96f0bc6c66d7395f8bcc093eea711a'}


# --- the synthetic settled inventory ----------------------------------------------------------------------------------

def at(words: str, after: str = '') -> dict:
    """Words located in TEXT where they first occur at or after ``after``: the revision's own slice, found by search."""
    start = TEXT.index(words, TEXT.index(after) if after else 0)
    return {'start': start, 'end': start + len(words), 'text': words}


def units() -> list:
    found, start = [], 0
    for index, line in enumerate(LINES):
        found.append({'id': f'S{index + 1}', 'start': start, 'end': start + len(line), 'line': index + 1,
                      'paragraph': 1, 'page': 1, 'forced': False})
        start += len(line) + 1
    return found


def src(cited, link='statement', words=None, geometry='ok') -> dict:
    return {'units': list(cited), 'link': link, 'words': words, 'geometry': geometry}


def checks(**changes) -> dict:
    value = {'integrity': 'ok', 'geometry': 'ok', 'literal': 'ok', 'literals': [], 'consistency': 'ok',
             'qualified': False}
    value.update(changes)
    return value


def claim(state, value, *, qualifiers=(), options=(), inherited_from=None) -> dict:
    return {'state': state, 'value': value, 'qualifiers': list(qualifiers), 'options': list(options),
            'inherited_from': inherited_from}


def silent() -> dict:
    return {'claim': claim(None, ''), 'sources': [], 'checks': checks(), 'appraisal': None, 'result': 'unknown',
            'reasons': ['silent']}


def fact(value, sources, *, state='supported', result='unresolved', reasons=('unappraised',), appraisal=None,
         inherited_from=None, options=(), literals=()) -> dict:
    return {'claim': claim(state, value, options=options, inherited_from=inherited_from), 'sources': list(sources),
            'checks': checks(literals=list(literals)), 'appraisal': appraisal, 'result': result,
            'reasons': list(reasons)}


class Ledger:
    """The stored claim list, built as settle would build it: each claim K<n> in its seeded order, with pass 2's
    verdict stored beside its content key (3.2.4)."""

    def __init__(self):
        self.claims = []

    def add(self, role, subject, attribute, value, cited, verdict='supports'):
        content = hashlib.sha256(json.dumps([role, subject, attribute, value, list(cited)]).encode()).hexdigest()
        entry = {'id': f'K{len(self.claims) + 1}', 'role': role, 'template': f'synthetic.{role}.{attribute}',
                 'subject': subject, 'attribute': attribute, 'value': value, 'units': list(cited), 'content': content,
                 'verdict': None if verdict is None else {'verdict': verdict, 'attached': 'yes', 'qualifiers': [],
                                                          'evidence': list(cited)}}
        self.claims.append(entry)
        return entry

    def appraised(self, subject, attribute, value, cited, *, verdict='supports', control=None,
                  control_verdict='contradicts', role='claim') -> dict:
        entry = self.add(role, subject, attribute, value, cited, verdict)
        appraisal = {'claim': entry['id'], 'content': entry['content'], 'verdict': verdict,
                     'attached': None if verdict is None else 'yes', 'qualifiers': [],
                     'evidence': [] if verdict is None else list(cited), 'control': None}
        if control is not None:
            other = self.add('control' if role == 'claim' else 'completeness_control', subject, attribute, control,
                             cited, control_verdict)
            appraisal['control'] = {'claim': other['id'], 'verdict': control_verdict}
        return appraisal


def est(ledger, subject, attribute, value, sources, *, state='supported', control=None, inherited_from=None,
        literals=()) -> dict:
    """An established fact: its claim supported (or negated), attached, its control (if any) contradicted."""
    cited = [unit for source in sources for unit in source['units']] or ['S1']
    return {'claim': claim(state, value, inherited_from=inherited_from), 'sources': list(sources),
            'checks': checks(literals=list(literals)),
            'appraisal': ledger.appraised(subject, attribute, value, cited, control=control), 'result': state,
            'reasons': []}


def event(id, anchor, **facts) -> dict:
    item = {'id': id, 'anchor': anchor, 'restatements': [], 'kind': silent(), 'other_class': silent(),
            'status': silent(), 'session': silent(), 'date_relation': silent(), 'date': silent(),
            'performer': silent(), 'performer_person': silent(), 'entry': silent(),
            'target': {'lesion': silent(), 'structure': silent(), 'places': [], 'anatomy': silent(), 'duct': silent()},
            'technique': {'device': silent(), 'route': silent()}, 'purpose': silent(), 'cause': silent(),
            'cause_event': silent(), 'part_of': silent(), 'part_relation': silent(), 'yield': silent(),
            'access_outcome': silent(),
            'scope': {'breadth': silent(), 'targets': [], 'segment': [], 'covers': [], 'excepts': []},
            'visit': {'basis': silent(), 'separately_identifiable': silent()}}
    for key, value in facts.items():
        if key in ('target', 'technique', 'scope', 'visit'):
            item[key].update(value)
        else:
            item[key] = value
    return item


def session(id, **facts) -> dict:
    item = {'id': id, 'examination': silent(), 'kind': silent(), 'encounter': silent(), 'tract': silent(),
            'approach': silent(), 'through': silent(), 'reached': [], 'device_reached': [], 'reached_anatomy': silent(),
            'completion': silent(), 'stations': [], 'part_of_session': silent(), 'completeness': None}
    item.update(facts)
    return item


def inherited(ledger, subject, attribute, value, sources, control, **extra):
    return est(ledger, subject, attribute, value, sources, control=control, inherited_from='N2', **extra)


def inventory():
    """(events, verification) of a settled inventory of TEXT in every shape 1.7 gives: a unit table; the encounter with
    a date of service and an other date; a person; three sections (N0 with no start units); two sessions, one with its
    reach and one an upper EUS session whose empty stations list has an established completeness claim; an anatomy
    entry; a lesion with a contradicted multiplicity; an examination, a performed snare with a restatement, and a biopsy
    denial whose performer a doubt names (unknown, its value kept); established facts with and without controls and
    inherited from N2; an appraised fact pass 2 found unclear; a pair control; a kept unlisted denial; and settle's
    report before store completes it. Every words record is TEXT's own slice."""
    k = Ledger()
    dos = lambda: src(['S2'], 'document_frame', at('11/09/2026'))  # noqa: E731
    clinician = lambda: src(['S3'], 'document_frame')  # noqa: E731
    day = [{'value': '2026-11-09', 'precision': 'day'}]
    encounter = {
        'date_of_service': est(k, '', 'date_of_service', '2026-11-09', [dos()], literals=day),
        'other_dates': [{'value': '2023', 'role': fact('other_occurrence', [src(['S4'], words=at('2023'))])}],
        'documenting_clinician': fact('P1', [clinician()]),
    }
    people = [{'id': 'P1', 'name': src(['S3'], words=at('Synthetic Endoscopist')),
               'role': fact('documenting_clinician', [src(['S3'])])}]
    sections = [
        {'id': 'N0', 'start': src([], 'section'), 'end': [], 'owner': fact('documenting_clinician', [clinician()]),
         'role': fact('header', [src(['S1'], 'section')]), 'occasion': fact('on_date_of_service', [dos()]),
         'performer': fact('documenting_team', [clinician()]), 'performer_person': silent()},
        {'id': 'N1', 'start': src(['S4'], 'section', at('History:')), 'end': [],
         'owner': fact('documenting_clinician', [clinician()]), 'role': fact('history', [src(['S4'], 'section')]),
         'occasion': fact('earlier_date', [src(['S4'], 'section', at('Prior colonoscopy in 2023'))],
                          literals=[{'value': '2023', 'precision': 'year'}]),
         'performer': silent(), 'performer_person': silent()},
        {'id': 'N2', 'start': src(['S5'], 'section', at('Findings:')), 'end': [],
         'owner': fact('documenting_clinician', [clinician()]), 'role': fact('findings', [src(['S5'], 'section')]),
         'occasion': fact('on_date_of_service', [dos()]), 'performer': fact('documenting_team', [clinician()]),
         'performer_person': silent()},
    ]
    sessions = [
        session('X1', examination=fact('E1', [src(['S5'])]),
                kind=est(k, 'X1', 'kind', 'colonoscopy', [src(['S1'], 'document_frame')], control='flex_sig'),
                encounter=est(k, 'X1', 'encounter', 'this_encounter', [dos()], control='separate_encounter'),
                reached=[est(k, 'X1', 'reached', 'cecum', [src(['S5'], words=at('advanced to the cecum'))],
                             control='cecum')]),
        session('X2', kind=fact('eus', [src(['S1'], 'document_frame')], reasons=['appraisal_unclear'],
                                appraisal=k.appraised('X2', 'kind', 'eus', ['S1'], verdict='unclear', control='egd',
                                                      control_verdict='supports')),
                completeness={'appraisal': k.appraised('X2', 'stations', '', ['S1'], role='completeness',
                                                       control=''),
                              'result': 'supported', 'reasons': []}),
    ]
    anatomy = [{'id': 'Y1', 'type': fact('anastomosis', [src(['S8'], words=at('ileocolic anastomosis'))]),
                'organ': silent(), 'subtype': fact('ileocolic', [src(['S8'], words=at('ileocolic'))]), 'joins': []}]
    polyp = lambda: src(['S6'], words=at('6 mm sessile polyp'))  # noqa: E731
    lesions = [{'id': 'L1', 'description': polyp(),
                'multiplicity': fact('', [polyp(), src(['S9'], words=at('Polyp removed'))], state='contradicted',
                                     result='contradicted', reasons=['contradicted_by_pass1'],
                                     options=[{'value': 'single', 'sources': [polyp()]},
                                              {'value': 'group', 'sources': [src(['S9'], words=at('Polyp removed'))]}]),
                'places': [est(k, 'L1', 'places', 'sigmoid_colon', [src(['S6'], words=at('sigmoid colon'))])],
                'distinct_from': [], 'same_as': []}]
    findings = lambda: src(['S5'], 'section', at('Findings:'))  # noqa: E731
    events = [
        event('E1', {'units': ['S5'], 'kind_words': at('colonoscope'), 'status_words': at('was advanced')},
              kind=est(k, 'E1', 'kind', 'examination', [src(['S5'], words=at('colonoscope'))]),
              status=est(k, 'E1', 'status', 'performed', [src(['S5'], words=at('was advanced'))], control='performed'),
              session=est(k, 'E1', 'session', 'X1', [src(['S5'])], control='X2'),
              date_relation=inherited(k, 'E1', 'date_relation', 'on_date_of_service', [dos()], 'earlier_date',
                                      literals=day),
              performer=inherited(k, 'E1', 'performer', 'documenting_team', [clinician()], 'other_clinician'),
              entry=inherited(k, 'E1', 'entry', 'documenting_clinician', [findings()], 'nursing')),
        event('E2', {'units': ['S6'], 'kind_words': at('cold snare'), 'status_words': at('was removed')},
              restatements=[{'units': ['S9'], 'role': fact('summarizes', [src(['S9'], 'other_statement')])}],
              kind=est(k, 'E2', 'kind', 'snare', [src(['S6'], words=at('cold snare'))], control='emr'),
              status=est(k, 'E2', 'status', 'performed', [src(['S6'], words=at('was removed'))], control='performed'),
              session=est(k, 'E2', 'session', 'X1', [src(['S6'])], control='X2'),
              date_relation=inherited(k, 'E2', 'date_relation', 'on_date_of_service', [dos()], 'earlier_date',
                                      literals=day),
              performer=inherited(k, 'E2', 'performer', 'documenting_team', [clinician()], 'other_clinician'),
              entry=inherited(k, 'E2', 'entry', 'documenting_clinician', [findings()], 'nursing'),
              target={'lesion': est(k, 'E2', 'target.lesion', 'L1', [polyp()]),
                      'places': [est(k, 'E2', 'target.places', 'sigmoid_colon',
                                     [src(['S6'], words=at('sigmoid colon'))])]},
              technique={'device': est(k, 'E2', 'technique.device', 'cold_snare',
                                       [src(['S6'], words=at('cold snare'))])},
              purpose=fact('removal', [src(['S6'], words=at('was removed'))])),
        event('E3', {'units': ['S7'], 'kind_words': at('biopsy'), 'status_words': at('was performed', 'Neither')},
              kind=est(k, 'E3', 'kind', 'biopsy', [src(['S7'], words=at('biopsy'))], control='hot_biopsy'),
              status=est(k, 'E3', 'status', 'performed',
                         [src(['S7'], words=at('Neither biopsy nor tattoo was performed'))], state='negated',
                         control='performed'),
              session=est(k, 'E3', 'session', 'X1', [src(['S7'])], control='X2'),
              date_relation=inherited(k, 'E3', 'date_relation', 'on_date_of_service', [dos()], 'earlier_date',
                                      literals=day),
              performer=fact('documenting_team', [clinician()], result='unknown', reasons=['doubt_unclear'],
                             inherited_from='N2'),
              entry=inherited(k, 'E3', 'entry', 'documenting_clinician', [findings()], 'nursing'),
              scope={'breadth': est(k, 'E3', 'scope.breadth', 'all_of_kind', [src(['S7'], words=at('Neither biopsy'))],
                                    control='exceptive')}),
    ]
    k.add('pair_control', 'E2', 'target.places', 'rectum', ['S6'], verdict='contradicts')
    settled = {'units': units(), 'encounter': encounter, 'people': people, 'sections': sections, 'sessions': sessions,
               'anatomy': anatomy, 'lesions': lesions, 'events': events,
               'doubts': [{'about': 'performer', 'objects': ['E3'], 'units': ['S7'], 'basis': 'unclear',
                           'readings': ['documenting_team', 'other_facility']}],
               'claims': k.claims, 'unlisted': [{'units': ['S7'], 'what': 'denial', 'kind': 'tattoo', 'session': 'X1'}]}
    report = {
        'counts': {'kind': {'supported': 3, 'unresolved': 1}, 'status': {'supported': 2, 'negated': 1}},
        'reasons': {'unappraised': 14, 'silent': 70, 'doubt_unclear': 1, 'appraisal_unclear': 1,
                    'contradicted_by_pass1': 1},
        'doubts': [{'about': 'performer', 'objects': ['E3'], 'applied': 1}],
        'health': {'control_acceptance': 0.077, 'establishment': 0.95, 'completeness': 0.0, 'controls': 13,
                   'claims': 20},
        'coherence': {'established': 19, 'control_incoherent': 1, 'appraisal_contradicts': 0},
        'unlisted': {'kept': 1, 'dropped': [{'units': ['S6'], 'what': 'act', 'kind': 'snare', 'session': 'X1',
                                             'event': 'E2'}]},
        'usage': {'interpretation': {'prompt_tokens': 1800, 'output_tokens': 900, 'thinking_tokens': 2100},
                  'appraisal': {'prompt_tokens': 2600, 'output_tokens': 480, 'thinking_tokens': 3300}},
    }
    return settled, report


def read_arguments(**changes) -> dict:
    events, verification = inventory()
    arguments = {'encounter_id': ENCOUNTER, 'revision_id': REVISION, 'provider_run_id': RUN,
                 'appraisal_run_id': APPRAISAL_RUN, 'revision_text': TEXT, 'text_sha256': TEXT_SHA256,
                 'request_sha256': REQUEST_SHA256, 'response_sha256': RESPONSE_SHA256,
                 'appraisal_request_sha256': APPRAISAL_REQUEST_SHA256,
                 'appraisal_response_sha256': APPRAISAL_RESPONSE_SHA256, 'events': events, 'verification': verification}
    arguments.update(changes)
    return arguments


def read_row(**changes) -> dict:
    return store.row_v2(**read_arguments(**changes))


REFUSAL_REASON = read.REFUSED + 'it lists 201 events, more than the 200 this contract accepts.'


def refusal(stage='bounds'):
    """A refusal of pass 1 as v1's read.Refusal writes one (refused_row_v2 takes any object with its stage and
    reason)."""
    return SimpleNamespace(stage=stage, reason=REFUSAL_REASON, refused=True)


def refused_row(**changes) -> dict:
    arguments = {'encounter_id': ENCOUNTER, 'revision_id': REVISION, 'provider_run_id': RUN,
                 'text_sha256': TEXT_SHA256, 'request_sha256': REQUEST_SHA256, 'response_sha256': RESPONSE_SHA256}
    arguments.update(changes)
    return store.refused_row_v2(refusal(), **arguments)


def load(fields, **changes) -> store.StoredInventoryV2:
    arguments = {'text_sha256': TEXT_SHA256, 'response_sha256': RESPONSE_SHA256,
                 'appraisal_response_sha256': APPRAISAL_RESPONSE_SHA256 if fields.get('state') == 'read' else None}
    arguments.update(changes)
    return store.load_v2(fields, **arguments)


def rehashed(fields: dict) -> dict:
    """``fields`` with its claim list's sha256 and its row sha256 recomputed where they still can be, so that only
    the change made to it is wrong."""
    try:
        fields['verification']['claims_sha256'] = store.claims_sha256_v2(fields['events']['claims'])
    except (KeyError, TypeError, ValueError):
        pass
    try:
        fields['sha256'] = store.content_sha256_v2(fields)
    except (store.StoreError, KeyError, TypeError, ValueError):
        pass
    return fields


def variant(fields: dict, edit, rehash: bool = True) -> dict:
    changed = copy.deepcopy(fields)
    edit(changed)
    return rehashed(changed) if rehash else changed


def node(value, *path):
    for step in path:
        value = value[step]
    return value


def setter(*path, value):
    """An edit that sets ``value`` at ``path`` of a row's fields (KeyError as the value: delete the key)."""
    def edit(fields):
        parent = node(fields, *path[:-1])
        if value is KeyError:
            del parent[path[-1]]
        else:
            parent[path[-1]] = copy.deepcopy(value)
    return edit


def words_records(value, path=()):
    """Every words record (a dict holding a start, an end and a text) in ``value``, with its path."""
    found = []
    if isinstance(value, dict):
        if {'start', 'end', 'text'} <= set(value):
            found.append((path, value))
        for key, item in value.items():
            found += words_records(item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += words_records(item, path + (index,))
    return found


def dotted(path) -> str:
    return ''.join(f'[{step}]' if isinstance(step, int) else f'.{step}' for step in path).lstrip('.')


# --- the read row -----------------------------------------------------------------------------------------------------

class RowTests(SimpleTestCase):
    def test_a_read_row(self):
        fields = read_row()
        self.assertEqual(tuple(fields), store.FIELDS_V2)
        self.assertEqual(store.FIELDS_V2, ('encounter_id', 'revision_id', 'provider_run_id', 'appraisal_run_id',
                                           'interpretation_version', 'inventory_version', 'text_sha256',
                                           'request_sha256', 'response_sha256', 'state', 'events', 'encounter_facts',
                                           'open_questions', 'verification', 'sha256'))
        self.assertEqual(store.BINDINGS_V2, ('encounter_id', 'revision_id', 'provider_run_id', 'appraisal_run_id'))
        self.assertEqual((fields['interpretation_version'], fields['inventory_version'], fields['state']),
                         ('gemini-events@2/appraisal@1', 'gemini-inventory@2', 'read'))
        self.assertEqual((fields['appraisal_run_id'], fields['encounter_facts'], fields['open_questions']),
                         (APPRAISAL_RUN, {}, []))
        events, report = inventory()
        self.assertEqual(fields['events'], events)
        self.assertEqual(fields['verification'], {
            **report, 'label': 'gemini-events@2/appraisal@1+inventory@2', 'request_sha256': REQUEST_SHA256,
            'response_sha256': RESPONSE_SHA256, 'appraisal_request_sha256': APPRAISAL_REQUEST_SHA256,
            'appraisal_response_sha256': APPRAISAL_RESPONSE_SHA256,
            'claims_sha256': store.claims_sha256_v2(events['claims']), 'refused': False})
        loaded = load(fields)
        self.assertIsInstance(loaded, store.StoredInventoryV2)
        self.assertEqual((loaded.encounter_id, loaded.revision_id, loaded.provider_run_id, loaded.appraisal_run_id),
                         (ENCOUNTER, REVISION, RUN, APPRAISAL_RUN))
        self.assertEqual((loaded.events, loaded.verification, loaded.sha256),
                         (events, fields['verification'], fields['sha256']))
        self.assertEqual((loaded.refused, loaded.refusal_stage, loaded.refusal_reason, loaded.label),
                         (False, None, None, 'gemini-events@2/appraisal@1+inventory@2'))
        self.assertEqual(loaded.claims_sha256, fields['verification']['claims_sha256'])
        self.assertEqual(len(events['claims']), 51)  # the fixture's claims, controls, completeness and pair control
        self.assertEqual(json.loads(json.dumps(fields)), fields)
        self.assertEqual(load(json.loads(json.dumps(fields))).sha256, fields['sha256'])

    def test_every_attribute_of_the_contract_is_a_stored_field(self):
        stored = {attribute for _, attribute in store._V2_DOMAINS}
        self.assertEqual(stored, {member.value for member in ct.Attribute})
        # kind, role, performer and performer_person are per object family: a session's kind is a SessionKind, an
        # act's a Kind; a person's role a PersonRole, a section's a SectionRole
        self.assertEqual(store._V2_DOMAINS[('X', 'kind')].values, {member.value for member in ct.SessionKind})
        self.assertEqual(store._V2_DOMAINS[('E', 'kind')].values, {member.value for member in ct.Kind})
        self.assertEqual(store._V2_DOMAINS[('P', 'role')].values, {member.value for member in ct.PersonRole})
        self.assertEqual(store._V2_DOMAINS[('N', 'role')].values, {member.value for member in ct.SectionRole})
        self.assertEqual(store._V2_DOMAINS[('X', 'reached')].values, {member.value for member in ct.Extent})
        self.assertEqual(store._V2_DOMAINS[('E', 'session')].letter, 'X')

    def test_the_report_is_completed_or_must_already_agree(self):
        fields = read_row()
        complete = fields['verification']
        self.assertEqual(read_row(verification=complete), fields)
        for key, value in (('label', 'gemini-events@2/appraisal@1+inventory@1'), ('request_sha256', '9' * 64),
                           ('response_sha256', '9' * 64), ('appraisal_request_sha256', '9' * 64),
                           ('appraisal_response_sha256', '9' * 64), ('claims_sha256', '9' * 64),
                           ('refused', True), ('refused', 0)):
            with self.subTest(report=key, value=value):
                with self.assertRaises(store.Mismatch):
                    read_row(verification=dict(inventory()[1], **{key: value}))
        with self.assertRaises(store.UnknownShape):
            read_row(verification=['not', 'a', 'report'])

    def test_contract_records_and_enum_members_are_stored_as_their_json(self):
        # settle (step 3a) may hand contract/types' records: they store as the same JSON data
        events, report = inventory()
        typed = copy.deepcopy(events)
        record = events['events'][1]['kind']
        appraisal = record['appraisal']
        typed['events'][1]['kind'] = ct.SettledFact(
            claim=ct.SettledClaim(state=ct.FactState.SUPPORTED, value='snare', qualifiers=(), options=(),
                                  inherited_from=None),
            sources=(ct.SettledSource(units=('S6',), link=ct.Link.STATEMENT,
                                      words=ct.LocatedWords(**record['sources'][0]['words']),
                                      geometry=ct.CheckStatus.OK),),
            checks=ct.Checks(integrity=ct.CheckStatus.OK, geometry=ct.CheckStatus.OK, literal=ct.CheckStatus.OK,
                             literals=(), consistency=ct.CheckStatus.OK, qualified=False),
            appraisal=ct.Appraisal(claim=appraisal['claim'], content=appraisal['content'],
                                   verdict=ct.VerdictValue.SUPPORTS, attached=ct.Attached.YES, qualifiers=(),
                                   evidence=tuple(appraisal['evidence']),
                                   control=ct.ControlVerdict(claim=appraisal['control']['claim'],
                                                             verdict=ct.VerdictValue.CONTRADICTS)),
            result=ct.Result.SUPPORTED, reasons=())
        typed['units'] = [ct.Unit(**unit) for unit in events['units']]
        typed['doubts'] = [ct.Doubt(about=ct.DoubtAbout.PERFORMER, objects=('E3',), units=('S7',),
                                    basis=ct.DoubtBasis.UNCLEAR, readings=('documenting_team', 'other_facility'))]
        typed['unlisted'] = [ct.Unlisted(units=('S7',), what=ct.UnlistedWhat.DENIAL, kind=ct.Kind.TATTOO,
                                         session='X1')]
        report = dict(report, counts={ct.Attribute.KIND: {ct.Result.SUPPORTED: 3, ct.Result.UNRESOLVED: 1},
                                      ct.Attribute.STATUS: {ct.Result.SUPPORTED: 2, ct.Result.NEGATED: 1}})
        self.assertEqual(read_row(events=typed, verification=report), read_row())
        with self.assertRaisesRegex(store.UnknownShape, 'not JSON data'):
            read_row(events=dict(events, doubts=[{'about': 'performer', 'objects': {'E3'}}]))
        with self.assertRaisesRegex(store.UnknownShape, 'not JSON data'):
            read_row(verification=dict(report, health={'establishment': float('nan')}))

    def test_the_bindings_are_uuids_however_they_are_given(self):
        fields = read_row(encounter_id=uuid.UUID(ENCOUNTER), revision_id=REVISION.upper(),
                          provider_run_id=f'{{{RUN}}}', appraisal_run_id=uuid.UUID(APPRAISAL_RUN))
        self.assertEqual(fields, read_row())
        for name in ('encounter_id', 'revision_id', 'provider_run_id', 'appraisal_run_id'):
            with self.subTest(binding=name):
                with self.assertRaisesRegex(store.UnknownShape, f'{name} is not a UUID'):
                    read_row(**{name: 'run-1'})

    def test_a_read_row_names_its_appraisal_run(self):
        # a read row is written only when both passes are settled (6.3): never one pass alone
        with self.assertRaisesRegex(store.UnknownShape, 'a read row names its appraisal run'):
            read_row(appraisal_run_id=None)
        fields = read_row()
        with self.assertRaisesRegex(store.UnknownShape, 'a read row names its appraisal run'):
            load(variant(fields, setter('appraisal_run_id', value=None)))

    def test_nothing_the_reader_would_refuse_is_written(self):
        events = inventory()[0]
        no_entry = copy.deepcopy(events)
        del no_entry['events'][0]['entry']
        rows = {
            'an event without its entry': dict(events=no_entry),
            'a sha256 that is no sha256': dict(text_sha256='abc'),
            'events that are no object': dict(events=['units']),
            'a unit out of order': dict(events=dict(events, units=list(reversed(events['units'])))),
        }
        for name, changes in rows.items():
            with self.subTest(row=name):
                with self.assertRaises(store.UnknownShape):
                    read_row(**changes)


class ModelTests(SimpleTestCase):
    def test_the_v2_fields_are_the_models_columns_and_v1s_stay_v1s(self):
        columns = {item.attname: item for item in EventInventory._meta.concrete_fields}
        self.assertEqual(set(store.FIELDS_V2), set(columns) - {'id', 'created_at'})
        # v1's FIELDS keep v1's names: migration 0015's column is v2's only, and a stored v1 row hashes without it
        self.assertEqual(set(store.FIELDS), set(columns) - {'id', 'created_at', 'appraisal_run_id'})
        self.assertEqual(store.BINDINGS_V2, store.BINDINGS + ('appraisal_run_id',))
        self.assertEqual((store.COLUMNS_V2, store.CONTENT_V2), (store.COLUMNS, store.CONTENT))
        fields = read_row()
        for name in ('interpretation_version', 'inventory_version', 'text_sha256', 'request_sha256', 'response_sha256',
                     'state', 'sha256'):
            with self.subTest(column=name):
                self.assertLessEqual(len(fields[name]), columns[name].max_length)
        for name in store.CONTENT_V2:
            self.assertFalse(columns[name].null, name)  # every row writes each of them, a refused one included
        self.assertTrue(columns['appraisal_run_id'].null)
        self.assertEqual((EventInventory.READ, EventInventory.REFUSED), (store.READ, store.REFUSED))


class HashTests(SimpleTestCase):
    def test_the_sha256_covers_every_field_and_both_runs(self):
        fields = read_row()
        self.assertEqual(fields['sha256'], store.content_sha256_v2(fields))
        self.assertEqual(read_row()['sha256'], fields['sha256'])  # stable
        changes = {'encounter_id': str(uuid.UUID(int=1)), 'revision_id': str(uuid.UUID(int=2)),
                   'provider_run_id': str(uuid.UUID(int=3)), 'appraisal_run_id': str(uuid.UUID(int=4)),
                   'interpretation_version': 'gemini-events@2/appraisal@2', 'inventory_version': 'gemini-inventory@3',
                   'text_sha256': '6' * 64, 'request_sha256': '7' * 64, 'response_sha256': '8' * 64,
                   'state': 'refused', 'events': {}, 'encounter_facts': {'x': 1}, 'open_questions': [1],
                   'verification': {}}
        self.assertEqual(set(changes), set(store.HASHED_V2))
        for name, value in changes.items():
            with self.subTest(field=name):
                self.assertNotEqual(store.content_sha256_v2(dict(fields, **{name: value})), fields['sha256'])
        # the appraisal run binds even by its absence, and the sha256 is over everything but itself
        self.assertNotEqual(store.content_sha256_v2(dict(fields, appraisal_run_id=None)), fields['sha256'])
        self.assertEqual(store.content_sha256_v2(dict(fields, sha256='0' * 64)), fields['sha256'])

    def test_the_hash_is_types_sha256_json_of_the_same_data(self):
        # EventInventory.sha256 says types.sha256_json; contract/jsonschema's sha256_of gives the same value for JSON
        # data
        for fields in (read_row(), refused_row()):
            hashed = {name: fields[name] for name in store.HASHED_V2}
            self.assertEqual(fields['sha256'], studio_types.sha256_json(hashed))

    def test_the_claim_list_sha256_is_over_the_claims_never_their_verdicts(self):
        claims = inventory()[0]['claims']
        pinned = store.claims_sha256_v2(claims)
        unchanged = copy.deepcopy(claims)
        unchanged[0]['verdict'] = {'verdict': 'unclear', 'attached': 'no', 'qualifiers': [], 'evidence': []}
        self.assertEqual(store.claims_sha256_v2(unchanged), pinned)
        self.assertEqual(store.CLAIM_IDENTITY, ('id', 'role', 'template', 'subject', 'attribute', 'value', 'units',
                                                'content'))
        for name, value in (('id', 'K99'), ('role', 'control'), ('template', 'synthetic.other'), ('subject', 'E9'),
                            ('attribute', 'status'), ('value', 'planned'), ('units', ['S9']), ('content', 'a' * 64)):
            with self.subTest(identity=name):
                changed = copy.deepcopy(claims)
                changed[0][name] = value
                self.assertNotEqual(store.claims_sha256_v2(changed), pinned)
        self.assertNotEqual(store.claims_sha256_v2(list(reversed(claims))), pinned)  # their seeded order counts


# --- versions ---------------------------------------------------------------------------------------------------------

class VersionTests(SimpleTestCase):
    def test_an_unknown_version_raises(self):
        for name, value in (('interpretation_version', INTERPRETATION_VERSION),
                            ('interpretation_version', 'gemini-events@2'),
                            ('interpretation_version', 'gemini-events@2/appraisal@2'),
                            ('inventory_version', INVENTORY_VERSION), ('inventory_version', 'gemini-inventory@3'),
                            ('inventory_version', ''), ('interpretation_version', None),
                            ('inventory_version', ['gemini-inventory@2'])):
            for state in ('read', 'refused'):
                with self.subTest(field=name, value=value, state=state):
                    fields = read_row() if state == 'read' else refused_row()
                    with self.assertRaises(store.UnknownVersion):
                        load(variant(fields, setter(name, value=value), rehash=False))

    def test_every_shipped_version_pair_is_read_as_stored_with_its_own_shapes_and_label(self):
        self.assertEqual(store.READ_VERSIONS, ((INTERPRETATION_PAIR, INVENTORY_VERSION_V2),))
        self.assertEqual(set(store._V2_SHAPES), set(store.READ_VERSIONS))
        self.assertEqual(set(store._V2_LABELS), set(store.READ_VERSIONS))
        self.assertEqual(store._V2_CURRENT, store.READ_VERSIONS[-1])  # rows are written at the last pair only
        for versions in store.READ_VERSIONS:
            with self.subTest(versions=versions):
                self.assertEqual(set(store._V2_SHAPES[versions]), {'read', 'refused'})
                for state, parts in store._V2_SHAPES[versions].items():
                    self.assertEqual(tuple(parts), store.CONTENT_V2, state)
        self.assertEqual(load(read_row()).inventory_version, INVENTORY_VERSION_V2)
        self.assertEqual(load(refused_row()).inventory_version, INVENTORY_VERSION_V2)

    def test_the_shapes_of_every_shipped_version_pair_are_pinned(self):
        # 6.2 [R:MO-5]: a new INVENTORY_VERSION never makes an earlier v2 inventory unreadable, so how a shipped pair
        # reads - every closed list, contract/types' enumerations included - never changes under it
        self.assertEqual(set(SHAPE_PINS), set(store.READ_VERSIONS))
        for versions, pin in SHAPE_PINS.items():
            with self.subTest(versions=versions):
                self.assertEqual(store.shape_signature_v2(versions), pin)

    def test_the_pin_sees_a_changed_enumeration_and_a_changed_shape(self):
        # the positive control of the pin: one value more in a closed list of contract/types, or one field more, moves
        # it
        pin = store.shape_signature_v2(store.READ_VERSIONS[0])
        wider = store._V2Domain(values=store._V2_DOMAINS[('E', 'yield')].values | {'gravel'})
        with mock.patch.dict(store._V2_DOMAINS, {('E', 'yield'): wider}):
            self.assertNotEqual(store.shape_signature_v2(store.READ_VERSIONS[0]), pin)
        with mock.patch.object(store._V2_UNLISTED, 'fields', dict(store._V2_UNLISTED.fields, note=store._V2_STR)):
            self.assertNotEqual(store.shape_signature_v2(store.READ_VERSIONS[0]), pin)
        self.assertEqual(store.shape_signature_v2(store.READ_VERSIONS[0]), pin)  # restored

    def test_v2_never_reads_a_v1_row_and_v1s_reader_never_reads_a_v2_row(self):
        from tests import test_interpretation_store as v1
        v1_row = v1.read_row()
        with self.assertRaisesRegex(store.UnknownShape, 'lacks appraisal_run_id'):
            load(v1_row, text_sha256=v1.TEXT_SHA256)
        with self.assertRaises(store.UnknownVersion):  # given the v2 field set, its version pair is still v1's
            load(dict(v1_row, appraisal_run_id=None), text_sha256=v1.TEXT_SHA256, appraisal_response_sha256=None)
        fields = read_row()
        for reader in (store.load, store._v1_reader.load):
            with self.subTest(reader=reader.__qualname__):
                with self.assertRaises(store.UnknownShape):  # it has a field v1 does not know
                    reader(fields, text_sha256=TEXT_SHA256, response_sha256=RESPONSE_SHA256)
                with self.assertRaises(store.UnknownVersion):
                    reader({name: fields[name] for name in store.FIELDS}, text_sha256=TEXT_SHA256,
                           response_sha256=RESPONSE_SHA256)


class V1ReaderKeptTests(SimpleTestCase):
    def test_v1s_reader_is_kept_whole_as_v1_reader(self):
        reader = store._v1_reader
        self.assertIs(reader.load, store.load)
        self.assertIs(reader.content_sha256, store.content_sha256)
        self.assertIs(reader.StoredInventory, store.StoredInventory)
        self.assertEqual((reader.FIELDS, reader.KNOWN_VERSIONS), (store.FIELDS, store.KNOWN_VERSIONS))
        self.assertEqual(store.KNOWN_VERSIONS, frozenset({(INTERPRETATION_VERSION, INVENTORY_VERSION)}))
        from tests import test_interpretation_store as v1
        fields = v1.read_row()
        as_model = SimpleNamespace(**fields, appraisal_run_id=None, id=uuid.uuid4(), created_at=None)
        loaded = reader.load(reader.fields_of(as_model), text_sha256=v1.TEXT_SHA256, response_sha256=v1.RESPONSE_SHA256)
        self.assertEqual((loaded.sha256, loaded.label), (fields['sha256'], 'gemini-events@1+inventory@1'))
        # a row that names an appraisal run is not a v1 row, whatever its versions say
        with self.assertRaisesRegex(store.UnknownShape, 'names an appraisal run'):
            reader.fields_of(SimpleNamespace(**fields, appraisal_run_id=uuid.UUID(APPRAISAL_RUN)))
        # v1's own names keep v1's values
        self.assertEqual(store.FIELDS, ('encounter_id', 'revision_id', 'provider_run_id', 'interpretation_version',
                                        'inventory_version', 'text_sha256', 'request_sha256', 'response_sha256',
                                        'state', 'events', 'encounter_facts', 'open_questions', 'verification',
                                        'sha256'))


# --- shapes and closed values -----------------------------------------------------------------------------------------

class ShapeTests(SimpleTestCase):
    """Every way the stored content can be a shape this release does not know raises UnknownShape, the claim list's
    and the row's sha256 recomputed, so that the shape alone is wrong; no problem repeats a stored text."""

    def assert_unknown(self, edit, fields=None) -> str:
        changed = variant(fields or read_row(), edit)
        with self.assertRaises(store.UnknownShape) as raised:
            load(changed)
        message = str(raised.exception)
        for words in DOCUMENT_WORDS:
            self.assertNotIn(words, message)
        return message

    def test_the_row(self):
        with self.assertRaises(store.UnknownShape):
            store.load_v2([('state', 'read')], text_sha256=TEXT_SHA256, response_sha256=RESPONSE_SHA256,
                          appraisal_response_sha256=None)
        rows = {
            'a field missing': setter('verification', value=KeyError),
            'an id': setter('id', value=str(uuid.uuid4())),
            'an unknown state': setter('state', value='pending'),
            'a binding that is no UUID': setter('encounter_id', value='encounter-1'),
            'an appraisal run that is no UUID': setter('appraisal_run_id', value=7),
            'a text sha256 that is no sha256': setter('text_sha256', value='ABC'),
            'an upper-case sha256': setter('request_sha256', value='A' * 64),
            'encounter facts': setter('encounter_facts', value={'date_of_service': None}),
            'open questions': setter('open_questions', value=[{'about': 'time'}]),
        }
        for name, edit in rows.items():
            with self.subTest(row=name):
                self.assert_unknown(edit)
        for stored in (None, '0' * 63, 'Z' * 64):
            with self.subTest(stored_sha256=stored):
                with self.assertRaises(store.UnknownShape):
                    load(variant(read_row(), setter('sha256', value=stored), rehash=False))

    def test_the_settled_inventory(self):
        e1, e2, e3 = ('events', 'events', 0), ('events', 'events', 1), ('events', 'events', 2)
        x1 = ('events', 'sessions', 0)
        rows = {
            'no unlisted list': setter('events', 'unlisted', value=KeyError),
            'an added container': setter('events', 'notes', value=[]),
            'units not a list': setter('events', 'units', value={}),
            'a unit numbered out of order': setter('events', 'units', 1, 'id', value='S3'),
            'a unit id that is not canonical': setter('events', 'units', 0, 'id', value='S01'),
            'an empty unit': setter('events', 'units', 0, 'end', value=0),
            'a unit over the one before': setter('events', 'units', 1, 'start', value=10),
            'a unit a line back': setter('events', 'units', 2, 'line', value=1),
            'a unit with text': setter('events', 'units', 0, 'text', value='SYNTHETIC'),
            'a negative offset': setter('events', 'units', 0, 'start', value=-1),
            'forced as text': setter('events', 'units', 0, 'forced', value='false'),
            'an event without its entry': setter(*e1, 'entry', value=KeyError),
            'an event with an added field': setter(*e2, 'excluded', value=True),
            'a person id of another family': setter('events', 'people', 0, 'id', value='E1'),
            'a section id that is not canonical': setter('events', 'sections', 1, 'id', value='N01'),
            'a repeated event id': setter(*e3, 'id', value='E2'),
            'a repeated section id': setter('events', 'sections', 2, 'id', value='N1'),
            'a kind outside the contract': setter(*e2, 'kind', 'claim', 'value', value='polypectomy'),
            'a session kind that is an act kind': setter(*x1, 'kind', 'claim', 'value', value='snare'),
            'a place outside LANDMARKS2': setter(*e2, 'target', 'places', 0, 'claim', 'value', value='not_stated'),
            'an extent outside EXTENTS': setter(*x1, 'reached', 0, 'claim', 'value', value='beyond'),
            'an option outside the domain': setter('events', 'lesions', 0, 'multiplicity', 'claim', 'options', 1,
                                                   'value', value='several'),
            'an id value that is free text': setter(*e1, 'session', 'claim', 'value', value='session one'),
            'a date that is no ISO date': setter('events', 'encounter', 'date_of_service', 'claim', 'value',
                                                 value='11/09/2026'),
            'an other date that is no ISO date': setter('events', 'encounter', 'other_dates', 0, 'value',
                                                        value='2023-13'),
            'a fact state': setter(*e2, 'status', 'claim', 'state', value='performed'),
            'a qualifier': setter(*e2, 'status', 'claim', 'qualifiers', value=['probable']),
            'a link': setter(*e2, 'kind', 'sources', 0, 'link', value='heading'),
            'a geometry': setter(*e2, 'kind', 'sources', 0, 'geometry', value='passed'),
            'a source unit that is free text': setter(*e2, 'kind', 'sources', 0, 'units', value=['the sixth line']),
            'a check status': setter(*e2, 'kind', 'checks', 'integrity', value='fine'),
            'a precision': setter('events', 'encounter', 'date_of_service', 'checks', 'literals', 0, 'precision',
                                  value='week'),
            'a result': setter(*e2, 'kind', 'result', value='established'),
            'a reason outside settle.REASONS': setter(*e3, 'performer', 'reasons', value=['doubt_probable']),
            'a verdict': setter(*e2, 'kind', 'appraisal', 'verdict', value='agrees'),
            'an attachment': setter(*e2, 'kind', 'appraisal', 'attached', value='maybe'),
            'an appraisal qualifier': setter('events', 'sessions', 1, 'kind', 'appraisal', 'qualifiers',
                                             value=['probable']),
            'an inherited section that is not a section': setter(*e1, 'date_relation', 'claim', 'inherited_from',
                                                                 value='X1'),
            'a doubt about something unknown': setter('events', 'doubts', 0, 'about', value='billing'),
            'a doubt basis': setter('events', 'doubts', 0, 'basis', value='guess'),
            'a doubt reading that is free text': setter('events', 'doubts', 0, 'readings', value=['maybe at home']),
            'an unlisted what': setter('events', 'unlisted', 0, 'what', value='plan'),
            'an unlisted kind': setter('events', 'unlisted', 0, 'kind', value='tattooing'),
            'an unlisted session that is a card of another type': setter('events', 'unlisted', 0, 'session',
                                                                         value='A1'),
            'a claim role': setter('events', 'claims', 0, 'role', value='hint'),
            'a claim template that is text': setter('events', 'claims', 0, 'template', value='This act is a snare.'),
            'a claim attribute': setter('events', 'claims', 0, 'attribute', value='billing'),
            'a claim value that is free text': setter('events', 'claims', 0, 'value', value='the 9th of November'),
            'claims out of their seeded order': lambda f: f['events']['claims'].reverse(),
            'a claim of an attribute its subject lacks': setter('events', 'claims', 0, 'attribute', value='kind'),
            'a claim value outside its attribute': setter('events', 'claims', 0, 'value', value='colonoscopy'),
            'a pair control on a session': setter('events', 'claims', -1, 'subject', value='X1'),
            'a pair control about a kind': setter('events', 'claims', -1, 'attribute', value='kind'),
            'a completeness claim on an act': lambda f: [c.update(subject='E1') for c in f['events']['claims']
                                                         if c['role'] == 'completeness'],
            'a completeness result that is negated': setter('events', 'sessions', 1, 'completeness', 'result',
                                                            value='negated'),
            'words with no text': setter(*e2, 'anchor', 'kind_words', 'text', value=''),
        }
        for name, edit in rows.items():
            with self.subTest(row=name):
                self.assert_unknown(edit)

    def test_each_closed_entry_takes_every_value_of_its_enumeration(self):
        # the closed lists are the contract's own: every value of each is read, so none of them refuses a value
        fields = read_row()
        entries = (('doubts', 0, 'about', ct.DoubtAbout), ('doubts', 0, 'basis', ct.DoubtBasis),
                   ('unlisted', 0, 'what', ct.UnlistedWhat), ('unlisted', 0, 'kind', ct.Kind))
        for *path, enumeration in entries:
            for member in enumeration:
                with self.subTest(path=path, value=member.value):
                    load(variant(fields, setter('events', *path, value=member.value)))
        for member in ct.Reason:
            with self.subTest(reason=member.value):
                load(variant(fields, setter('events', 'events', 2, 'performer', 'reasons', value=[member.value])))
        for member in ct.Link:
            with self.subTest(link=member.value):
                load(variant(fields, setter('events', 'events', 1, 'kind', 'sources', 0, 'link', value=member.value)))
        everything = variant(fields, setter('verification', 'counts', value={
            attribute.value: {result.value: 1 for result in ct.Result} for attribute in ct.Attribute}))
        self.assertEqual(set(load(everything).verification['counts']), {member.value for member in ct.Attribute})

    def test_the_report(self):
        rows = {
            'a count by an unknown attribute': setter('verification', 'counts', value={'billing': {'supported': 1}}),
            'a count by an unknown result': setter('verification', 'counts', value={'kind': {'verified': 1}}),
            'a negative count': setter('verification', 'counts', value={'kind': {'supported': -1}}),
            'a reason count by an unknown reason': setter('verification', 'reasons', value={'default': 3}),
            'health that is no object': setter('verification', 'health', value=[0.5]),
            'usage of a third run': setter('verification', 'usage', 'review', value={}),
            'a dropped unlisted entry without its event': setter('verification', 'unlisted', 'dropped', 0, 'event',
                                                                 value=KeyError),
            'a report field of v1': setter('verification', 'discarded', value=[]),
            'refused as text': setter('verification', 'refused', value='false'),
            'a stage on a read row': setter('verification', 'stage', value='json'),
        }
        for name, edit in rows.items():
            with self.subTest(row=name):
                self.assert_unknown(edit)

    def test_an_error_names_the_place_never_the_stored_text(self):
        message = self.assert_unknown(setter('events', 'events', 1, 'kind', 'claim', 'value',
                                             value='sessile polyp removed'))
        self.assertIn('events.events[1].kind.claim.value', message)
        message = self.assert_unknown(setter('events', 'events', 1, 'Synthetic Endoscopist, MD', value=1))
        self.assertIn('a key of 25 characters', message)


class FactRuleTests(SimpleTestCase):
    """The fact rules load_v2 holds a stored fact to (FINAL-V2 3.3, read as integrity): each turns a well-shaped fact
    into one this release refuses (UnknownShape)."""

    def assert_refused(self, *path, edit):
        def apply(fields):
            edit(node(fields, 'events', *path))
        changed = variant(read_row(), apply)
        with self.assertRaises(store.UnknownShape) as raised:
            load(changed)
        return str(raised.exception)

    def test_an_established_fact_needs_everything_establishing_it_needs(self):
        snare = ('events', 1, 'kind')  # supported, attached, its control contradicted
        breaks = {
            'no appraisal': lambda f: f.update(appraisal=None),
            'a verdict that does not support': lambda f: f['appraisal'].update(verdict='qualified'),
            'detached': lambda f: f['appraisal'].update(attached='no'),
            'its control supported': lambda f: f['appraisal']['control'].update(verdict='supports'),
            'its control unanswered': lambda f: f['appraisal']['control'].update(verdict=None),
            'a failed check': lambda f: f['checks'].update(consistency='failed'),
            'a failed source geometry': lambda f: f['sources'][0].update(geometry='failed'),
            'a qualifier': lambda f: (f['claim'].update(qualifiers=['hedged']), f['checks'].update(qualified=True)),
            'a reason': lambda f: f['reasons'].append('unappraised'),
            'another state': lambda f: f['claim'].update(state='negated'),
            'no value': lambda f: f['claim'].update(value=''),
            'no source': lambda f: f.update(sources=[]),
            'options': lambda f: f['claim'].update(options=[{'value': 'emr', 'sources': []}]),
        }
        for name, edit in breaks.items():
            with self.subTest(fact=name):
                message = self.assert_refused(*snare, edit=edit)
                if name not in ('a verdict that does not support', 'detached', 'its control unanswered'):
                    self.assertIn('events.events[1].kind', message)

    def test_an_established_id_names_an_object_of_its_family(self):
        # before establishment any object's id is kept (an id naming no object is an item-level finding, 1.8)
        message = self.assert_refused('events', 0, 'session', edit=lambda f: f['claim'].update(value='L1'))
        self.assertIn('without what establishing it needs', message)
        unresolved = variant(read_row(), lambda fields: node(fields, 'events', 'sessions', 0, 'examination',
                                                             'claim').update(value='L9'))
        self.assertEqual(load(unresolved).events['sessions'][0]['examination']['claim']['value'], 'L9')

    def test_silence_holds_nothing_and_settles_unknown_or_contradicted(self):
        tract = ('sessions', 0, 'tract')
        for name, edit in {'a value': lambda f: f['claim'].update(value='lower'),
                           'a source': lambda f: f['sources'].append({'units': ['S1'], 'link': 'statement',
                                                                      'words': None, 'geometry': 'ok'}),
                           'a qualifier': lambda f: f['claim'].update(qualifiers=['approximate']),
                           'settled supported': lambda f: f.update(result='supported', reasons=[]),
                           'settled unresolved': lambda f: f.update(result='unresolved')}.items():
            with self.subTest(silent=name):
                self.assert_refused(*tract, edit=edit)
        # a conflict doubt naming a silent attribute settles it contradicted (3.3 row 1): that is kept
        contradicted = variant(read_row(), lambda fields: node(fields, 'events', *tract).update(
            result='contradicted', reasons=['contradicted_by_pass1']))
        self.assertEqual(load(contradicted).events['sessions'][0]['tract']['result'], 'contradicted')

    def test_every_other_rule(self):
        cases = {
            'an unestablished result with no reason': (('events', 2, 'performer'), lambda f: f.update(reasons=[])),
            'an appraisal on a contradicted claim': (('lesions', 0, 'multiplicity'), lambda f: f.update(
                appraisal=copy.deepcopy(read_row()['events']['events'][1]['kind']['appraisal']))),
            'qualified not saying what the qualifiers say': (('events', 1, 'purpose'), lambda f: f['checks'].update(
                qualified=True)),
            'a literal not at its precision': (('encounter', 'date_of_service'), lambda f: f['checks']['literals'][0]
                                               .update(precision='month')),
            'a verdict without its attachment': (('sessions', 1, 'kind'), lambda f: f['appraisal'].update(
                attached=None)),
            'evidence without a verdict': (('sessions', 1, 'kind'), lambda f: f['appraisal'].update(
                verdict=None, attached=None)),
            'a completeness supported without its control': (('sessions', 1, 'completeness'), lambda f: f[
                'appraisal'].update(control=None)),
            'a completeness supported with a reason': (('sessions', 1, 'completeness'), lambda f: f.update(
                reasons=['appraisal_unclear'])),
            'a completeness unresolved with no reason': (('sessions', 1, 'completeness'), lambda f: f.update(
                result='unresolved')),
        }
        for name, (path, edit) in cases.items():
            with self.subTest(rule=name):
                self.assert_refused(*path, edit=edit)
        # qualified agrees with the qualifiers: approximate alone is recorded and never lowers (3.1 Q1)
        approximate = variant(read_row(), lambda fields: node(fields, 'events', 'events', 1, 'kind', 'claim').update(
            qualifiers=['approximate']))
        self.assertEqual(load(approximate).events['events'][1]['kind']['result'], 'supported')


class BindingTests(SimpleTestCase):
    """A verdict is never read against a different claim (FINAL-V2 3.2.4 [R:MO-5]); the report agrees with its row:
    each is a Mismatch."""

    def assert_mismatch(self, edit, pattern=''):
        changed = variant(read_row(), edit)
        with self.assertRaisesRegex(store.Mismatch, pattern) as raised:
            load(changed)
        return str(raised.exception)

    def claims(self, fields):
        return {claim['id']: claim for claim in fields['events']['claims']}

    def test_each_appraisal_names_the_claim_made_for_its_fact(self):
        fields = read_row()
        snare = fields['events']['events'][1]['kind']['appraisal']
        number = int(snare['claim'][1:]) - 1
        control = int(snare['control']['claim'][1:]) - 1
        other_fact = int(fields['events']['events'][0]['kind']['appraisal']['claim'][1:]) - 1
        cases = {
            'a claim that does not exist': lambda f: f['events']['events'][1]['kind']['appraisal'].update(claim='K99'),
            'the claim of another fact': lambda f: f['events']['events'][1]['kind']['appraisal'].update(
                claim=f'K{other_fact + 1}', content=f['events']['claims'][other_fact]['content']),
            'another content key': lambda f: f['events']['claims'][number].update(content='a' * 64),
            'another subject': lambda f: f['events']['claims'][number].update(subject='E1'),
            'another attribute': lambda f: f['events']['claims'][number].update(attribute='other_class', value=''),
            'another value': lambda f: f['events']['claims'][number].update(value='emr'),
            'a control in the claim role': lambda f: f['events']['claims'][number].update(role='control'),
            'another verdict stored': lambda f: f['events']['claims'][number]['verdict'].update(verdict='unclear'),
            'other evidence stored': lambda f: f['events']['claims'][number]['verdict'].update(evidence=['S1']),
            'no verdict stored': lambda f: f['events']['claims'][number].update(verdict=None),
            'its control a claim': lambda f: f['events']['claims'][control].update(role='claim'),
            'its control of another subject': lambda f: f['events']['claims'][control].update(subject='E1'),
            'its control answered otherwise': lambda f: f['events']['claims'][control]['verdict'].update(
                verdict='qualified'),
            'its control naming no claim': lambda f: f['events']['events'][1]['kind']['appraisal']['control'].update(
                claim='K99'),
        }
        for name, edit in cases.items():
            with self.subTest(binding=name):
                message = self.assert_mismatch(edit, 'against another claim')
                self.assertIn('events.events[1].kind.appraisal', message)

    def test_no_claim_is_read_by_two_facts(self):
        def twice(fields):
            first = fields['events']['events'][1]['kind']['appraisal']
            fields['events']['events'][2]['kind']['appraisal'] = copy.deepcopy(first)
            fields['events']['events'][2]['kind']['claim']['value'] = 'snare'
        # E3's kind now names E2's claim: its subject differs too, but a claim read twice is refused whatever else
        self.assert_mismatch(twice, 'against another claim')
        claims = self.claims(read_row())
        self.assertEqual(len(claims), 51)

    def test_the_completeness_record_names_its_own_claims(self):
        for name, edit in {
            'a claim in the claim role': lambda f: [c.update(role='claim') for c in f['events']['claims']
                                                    if c['role'] == 'completeness'],
            'its control in the control role': lambda f: [c.update(role='control') for c in f['events']['claims']
                                                          if c['role'] == 'completeness_control'],
        }.items():
            with self.subTest(completeness=name):
                self.assert_mismatch(edit, 'sessions\\[1\\]\\.completeness')

    def test_the_report_agrees_with_its_row(self):
        cases = {
            'another label': (setter('verification', 'label', value='gemini-events@1+inventory@1'), 'label'),
            'another request': (setter('verification', 'request_sha256', value='9' * 64), 'request or response'),
            'another response': (setter('verification', 'response_sha256', value='9' * 64), 'request or response'),
            'more kept unlisted statements': (setter('verification', 'unlisted', 'kept', value=2), 'unlisted'),
        }
        for name, (edit, pattern) in cases.items():
            with self.subTest(report=name):
                self.assert_mismatch(edit, pattern)
        # the claim list's sha256 is not recomputed here: a row whose claims changed under it is refused
        changed = variant(read_row(), setter('events', 'claims', -1, 'value', value='sigmoid_colon'), rehash=False)
        changed['sha256'] = store.content_sha256_v2(changed)
        with self.assertRaisesRegex(store.Mismatch, 'another claim list'):
            load(changed)

    def test_a_row_that_disagrees_with_its_hash_or_its_bindings(self):
        fields = read_row()
        for name, edit in {'a fact': setter('events', 'events', 1, 'kind', 'result', value='unresolved'),
                           'a verdict': setter('events', 'claims', 0, 'verdict', 'evidence', value=['S1']),
                           'the appraisal run': setter('appraisal_run_id', value=str(uuid.UUID(int=9)))}.items():
            with self.subTest(changed=name):
                with self.assertRaisesRegex(store.StoreError, 'sha256|against another claim|no reason'):
                    load(variant(fields, edit, rehash=False))
        with self.assertRaisesRegex(store.Mismatch, 'another revision text'):
            load(fields, text_sha256='7' * 64)
        with self.assertRaisesRegex(store.Mismatch, 'another response'):
            load(fields, response_sha256='7' * 64)
        with self.assertRaisesRegex(store.Mismatch, 'another appraisal response'):
            load(fields, appraisal_response_sha256='7' * 64)
        with self.assertRaisesRegex(store.Mismatch, 'another appraisal response'):
            load(fields, appraisal_response_sha256=None)

    def test_every_store_error_is_a_value_error_and_none_is_returned(self):
        for kind in (store.UnknownVersion, store.UnknownShape, store.Mismatch):
            self.assertTrue(issubclass(kind, store.StoreError) and issubclass(kind, ValueError))


# --- what an established fact rests on, and what its control and a pair control are about ----------------------------

def claim_of(events, appraisal) -> dict:
    """The stored claim an appraisal (or a control) names."""
    return next(item for item in events['claims'] if item['id'] == appraisal['claim'])


def refused_both_ways(case: SimpleTestCase, edit, pattern=''):
    """``edit`` (of a settled inventory's events) is refused at row_v2, and at load_v2 on an otherwise sound row
    (the claim list's and the row's sha256 recomputed), each with UnknownShape; the message is returned."""
    events = inventory()[0]
    edit(events)
    with case.assertRaisesRegex(store.UnknownShape, pattern):
        read_row(events=events)
    with case.assertRaisesRegex(store.UnknownShape, pattern) as raised:
        load(variant(read_row(), lambda fields: edit(fields['events'])))
    message = str(raised.exception)
    for words in DOCUMENT_WORDS:
        case.assertNotIn(words, message)
    return message


def read_both_ways(edit) -> store.StoredInventoryV2:
    """``edit`` is written by row_v2 and read by load_v2 (the positive control of refused_both_ways)."""
    events = inventory()[0]
    edit(events)
    return load(read_row(events=events))


def evidence(path, units):
    """An edit giving the appraisal at ``path`` (of the events) ``units`` as its evidence, in the fact and in its
    claim's stored verdict alike, so that only the evidence differs."""
    def edit(events):
        appraisal = node(events, *path, 'appraisal')
        appraisal['evidence'] = list(units)
        claim_of(events, appraisal)['verdict']['evidence'] = list(units)
    return edit


class EstablishedIntegrityTests(SimpleTestCase):
    """Triage 1d#3: an ESTABLISHED fact rests on the row itself - pass 2's supports with at least one evidence unit,
    each unit its sources and its evidence cite in the row's units table, an id value naming an object of its family in
    the row (FINAL-V2 3.2.3's coherence table, 3.2.5, 3.3 row 8, 3.1 I1 and I4). Each input below was written and read
    'supported' before the repair."""

    def test_the_reviewers_three_inputs_are_refused_at_row_v2_and_load_v2(self):
        def session_x9(events):
            fact = events['events'][1]['session']
            fact['claim']['value'] = 'X9'
            claim_of(events, fact['appraisal'])['value'] = 'X9'  # the claim made for it names X9 too

        cases = {
            'E2.kind with evidence []': (evidence(('events', 1, 'kind'), []), 'without what establishing it needs'),
            "E2.kind's source citing S99": (setter('events', 1, 'kind', 'sources', 0, 'units', value=['S99']),
                                           r'events\.events\[1\]\.kind\.sources\[0\], which cites a unit'),
            "E2.session 'X9'": (session_x9, 'an id that names no object of its family'),
        }
        for name, (edit, pattern) in cases.items():
            with self.subTest(case=name):
                message = refused_both_ways(self, edit, pattern)
                self.assertIn('events.events[1]', message)

    def test_evidence_names_the_rows_units_and_a_supported_completeness_needs_some(self):
        x2 = ('sessions', 1, 'completeness')
        for name, (edit, pattern) in {
            "E2.kind's evidence naming S99": (evidence(('events', 1, 'kind'), ['S99']), 'evidence that names a unit'),
            "E2.kind's evidence naming S6 and S99": (evidence(('events', 1, 'kind'), ['S6', 'S99']),
                                                    'evidence that names a unit'),
            "X2's completeness with evidence []": (evidence(x2, []), 'supported without what establishing it needs'),
            "X2's completeness on evidence S99": (evidence(x2, ['S99']), 'supported on evidence that names a unit'),
        }.items():
            with self.subTest(case=name):
                refused_both_ways(self, edit, pattern)

    def test_a_supports_verdict_naming_a_qualifier_establishes_nothing(self):
        # DECISIONS D186: a supports verdict that names qualifiers is read as qualified (A3: supports is "with no
        # qualification"), which settles unresolved, so a stored ESTABLISHED fact never rests on one; approximate too
        for qualifiers in (['hedged'], ['approximate'], ['other_target', 'partial']):
            def edit(events, qualifiers=qualifiers):
                appraisal = events['events'][1]['kind']['appraisal']
                appraisal['qualifiers'] = list(qualifiers)
                claim_of(events, appraisal)['verdict']['qualifiers'] = list(qualifiers)
            with self.subTest(qualifiers=qualifiers):
                refused_both_ways(self, edit, 'without what establishing it needs')

    def test_what_is_not_established_keeps_an_unknown_unit_or_a_dangling_id(self):
        # an unknown unit or an id naming nothing is an item-level finding (1.8): the fact settled unresolved or
        # unknown with its value kept, and it is stored as it is - the positive control of the three refusals above
        def edit(events):
            events['events'][2]['performer']['sources'][0]['units'] = ['S99']  # unknown (a doubt), its value kept
            events['encounter']['documenting_clinician']['claim']['value'] = 'P9'  # unresolved, names no person
            events['sessions'][0]['examination']['claim']['value'] = 'E9'  # unresolved, names no event
        loaded = read_both_ways(edit)
        self.assertEqual(loaded.events['events'][2]['performer']['sources'][0]['units'], ['S99'])
        self.assertEqual(loaded.events['encounter']['documenting_clinician']['claim']['value'], 'P9')
        # and the established facts of the fixture name their own objects: E2's lesion L1, every act's session X1
        acts = read_row()['events']['events']
        established = [acts[1]['target']['lesion'], *(item['session'] for item in acts)]
        self.assertEqual({fact['result'] for fact in established}, {'supported'})
        self.assertEqual({fact['claim']['value'] for fact in established}, {'L1', 'X1'})

    def test_k1s_reasons_and_a_bare_appraisal_qualified_are_read(self):
        # DECISIONS D186 (triage 1d dev 8): Reason holds K1's structure_<rule> reasons and appraisal_qualified, so a
        # fact K1 demoted, or a qualified verdict naming no qualifier, is stored and read
        for reason in ('structure_scope', 'structure_umbrella', 'appraisal_qualified'):
            with self.subTest(reason=reason):
                loaded = read_both_ways(setter('events', 2, 'performer', 'reasons', value=[reason]))
                self.assertEqual(loaded.events['events'][2]['performer']['reasons'], [reason])


def controlled(events, path, subject, attribute, value, control_attribute, control_value):
    """Put an ESTABLISHED fact of ``attribute`` at ``path`` (of the events; appended when the field is a list), its
    claim and its contrary control added to the stored claims - the control a claim of ``control_attribute``."""
    ledger = Ledger()
    ledger.claims = events['claims']
    cited = ['S7']
    made = ledger.add('claim', subject, attribute, value, cited)
    control = ledger.add('control', subject, control_attribute, control_value, cited, 'contradicts')
    record = {'claim': claim('supported', value), 'sources': [src(cited)], 'checks': checks(),
              'appraisal': {'claim': made['id'], 'content': made['content'], 'verdict': 'supports',
                            'attached': 'yes', 'qualifiers': [], 'evidence': list(cited),
                            'control': {'claim': control['id'], 'verdict': 'contradicts'}},
              'result': 'supported', 'reasons': []}
    parent = node(events, *path[:-1])
    if isinstance(parent[path[-1]], list):
        parent[path[-1]].append(record)
    else:
        parent[path[-1]] = record


# Where each fact with a partner sits in the fixture, its subject, a value of its domain naming an object the row holds,
# and a value for a control in its partner's form.
PARTNERED = {
    'cause': (('events', 1, 'cause'), 'E2', 'pre_existing_lesion', 'E1'),
    'scope.excepts': (('events', 2, 'scope', 'excepts'), 'E3', 'E2', 'E1'),
    'scope.segment': (('events', 2, 'scope', 'segment'), 'E3', 'sigmoid_colon', 'rectum'),
    'scope.targets': (('events', 2, 'scope', 'targets'), 'E3', 'L1', 'L1'),
    'reached_anatomy': (('sessions', 0, 'reached_anatomy'), 'X1', 'Y1', 'cecum'),
    'distinct_from': (('lesions', 0, 'distinct_from'), 'L1', 'L1', 'L1'),
}


class ControlBindingTests(SimpleTestCase):
    """Triage 1d#4: a fact's control is a claim about the fact's own attribute, or about the partner 3.2.3 writes its
    control in (store.CONTROL_ATTRIBUTES), so no fact is read against the control of another of its subject's facts."""

    def test_a_fact_is_never_read_against_the_control_of_another_attribute(self):
        def swap(events):
            kind, status = events['events'][1]['kind']['appraisal'], events['events'][1]['status']['appraisal']
            kind['control'], status['control'] = status['control'], kind['control']
        # both controls are E2's and both were rejected (contradicts): before the repair, both facts read established
        message = refused_both_ways(self, swap, 'about another attribute than its fact')
        self.assertIn('events.events[1].kind.appraisal.control', message)

    def test_control_attributes_are_the_partners_3_2_3_writes_a_control_in(self):
        # derived from 3.2.3's rows as contract/claims.CONTROLS generates them (as_attribute): every rule whose
        # control is another attribute's form, and nothing else
        partners = {rule.attribute.value: rule.as_attribute.value for rule in contract_claims.CONTROLS
                    if rule.as_attribute is not None and rule.as_attribute is not rule.attribute}
        self.assertEqual(dict(store.CONTROL_ATTRIBUTES), partners)
        self.assertEqual(set(PARTNERED), set(partners))
        attributes = {member.value for member in ct.Attribute}
        self.assertLessEqual(set(store.CONTROL_ATTRIBUTES) | set(store.CONTROL_ATTRIBUTES.values()), attributes)
        with self.assertRaises(TypeError):
            store.CONTROL_ATTRIBUTES['kind'] = 'status'  # a closed table

    def test_a_control_in_its_partners_form_or_its_own_is_read_and_one_in_a_third_is_refused(self):
        for attribute, (path, subject, value, partner_value) in PARTNERED.items():
            partner = store.CONTROL_ATTRIBUTES[attribute]
            with self.subTest(attribute=attribute, control=partner):
                loaded = read_both_ways(lambda e: controlled(e, path, subject, attribute, value, partner,
                                                             partner_value))
                stored = node(loaded.events, *path)
                self.assertEqual((stored[-1] if isinstance(stored, list) else stored)['result'], 'supported')
            with self.subTest(attribute=attribute, control=attribute):
                read_both_ways(lambda e: controlled(e, path, subject, attribute, value, attribute, value))
            with self.subTest(attribute=attribute, control='kind'):
                refused_both_ways(self, lambda e: controlled(e, path, subject, attribute, value, 'kind', 'snare'),
                                  'about another attribute than its fact')

    def test_the_pin_sees_a_changed_partner(self):
        pin = store.shape_signature_v2(store.READ_VERSIONS[0])
        with mock.patch.object(store, 'CONTROL_ATTRIBUTES', dict(store.CONTROL_ATTRIBUTES, kind='status')):
            self.assertNotEqual(store.shape_signature_v2(store.READ_VERSIONS[0]), pin)
        self.assertEqual(store.shape_signature_v2(store.READ_VERSIONS[0]), pin)


class PairControlTests(SimpleTestCase):
    """Triage 2d#7: a pair control asks a value of its attribute's domain - a place (a Landmark) for target.places, a
    lesion id for target.lesion - or the row is refused at row_v2, as the FactSet builder refuses it (3.1 B1)."""

    def test_a_pair_control_asks_a_value_of_its_attribute(self):
        refused = (('target.places', 'stated_depth'), ('target.places', 'L9'), ('target.places', ''),
                   ('target.places', '2026-11-09'), ('target.lesion', 'sigmoid_colon'), ('target.lesion', ''),
                   ('target.lesion', 'X1'), ('target.lesion', 'E2'))
        for attribute, value in refused:
            def edit(events, attribute=attribute, value=value):
                events['claims'][-1].update(attribute=attribute, value=value)
            with self.subTest(attribute=attribute, value=value):
                message = refused_both_ways(self, edit, r'events\.claims\[50\]\.value is not a')
                self.assertIn('lesion id' if attribute == 'target.lesion' else 'place', message)
        for attribute, value in (('target.places', 'rectum'), ('target.places', 'cecum'), ('target.lesion', 'L1'),
                                 ('target.lesion', 'L9')):
            with self.subTest(attribute=attribute, value=value):
                loaded = read_both_ways(lambda e: e['claims'][-1].update(attribute=attribute, value=value))
                self.assertEqual(loaded.events['claims'][-1]['role'], 'pair_control')


# --- the engine's text-free view (DECISIONS D188) ---------------------------------------------------------------------

def keys_of(value) -> set:
    """Every object key anywhere in ``value``."""
    found = set()
    if isinstance(value, dict):
        found |= set(value)
        for item in value.values():
            found |= keys_of(item)
    elif isinstance(value, list):
        for item in value:
            found |= keys_of(item)
    return found


def with_text(value):
    """A text-free view with the revision's text put back where it was: each ``at`` as a ``words`` record holding
    TEXT's slice, and an anchor's kind_words and status_words likewise - so equality with the stored events shows that
    the view dropped the text and nothing else."""
    if isinstance(value, dict):
        restored = {}
        for key, item in value.items():
            if key == 'at':
                restored['words'] = None if item is None else dict(item, text=TEXT[item['start']:item['end']])
            elif key in ('kind_words', 'status_words') and item is not None:
                restored[key] = dict(item, text=TEXT[item['start']:item['end']])
            else:
                restored[key] = with_text(item)
        return restored
    if isinstance(value, list):
        return [with_text(item) for item in value]
    return value


class TextFreeViewTests(SimpleTestCase):
    """store.textfree_v2 (DECISIONS D188): the read row's events with every source's words record as ``at`` {start,
    end} (None for none) and no text, which engine/facts.py builds the FactSet from."""

    def test_the_view_drops_the_text_and_nothing_else(self):
        stored = load(read_row())
        view = store.textfree_v2(stored)
        self.assertIsInstance(view, dict)
        self.assertEqual(keys_of(view) & {'text', 'words'}, set())
        self.assertEqual(with_text(view), stored.events)
        self.assertEqual(set(view), set(stored.events))
        # every source's words became its offsets: 41 words records, 35 of them a source's and 6 an anchor's kind or
        # status words
        found = words_records(stored.events)
        sources = [(path, record) for path, record in found if path[-1] == 'words']
        self.assertEqual((len(found), len(sources)), (41, 35))
        for path, record in sources:
            self.assertEqual(node(view, *path[:-1], 'at'), {'start': record['start'], 'end': record['end']},
                             dotted(path))
        for path, record in found:
            if path[-1] != 'words':
                self.assertEqual(node(view, *path), {'start': record['start'], 'end': record['end']}, dotted(path))
        # a source citing its whole units (words null) has at null; an anchor with no words keeps null
        self.assertIsNone(view['encounter']['documenting_clinician']['sources'][0]['at'])
        self.assertEqual(view['sections'][0]['start'], {'units': [], 'link': 'section', 'at': None,
                                                        'geometry': 'ok'})
        blob = json.dumps(view)
        for words in ('sessile polyp', 'Synthetic Endoscopist', 'colonoscope', 'cold snare', 'Findings:', '11/09/2026',
                      'ileocolic anastomosis', 'Prior colonoscopy in 2023', 'was advanced', 'Neither biopsy'):
            self.assertIn(words, TEXT)
            self.assertNotIn(words, blob)  # document words; the stored values ('anastomosis', 'ileocolic') are no text

    def test_the_view_keeps_the_offsets_links_and_inheritance_the_engine_reads(self):
        # what D188 names: C-10's statement-linked target words, the performer row's inherited_from, the units
        view = store.textfree_v2(load(read_row()))
        e2 = view['events'][1]
        self.assertEqual([(source['link'], source['at']) for source in e2['target']['places'][0]['sources']],
                         [('statement', {'start': TEXT.index('sigmoid colon'),
                                         'end': TEXT.index('sigmoid colon') + len('sigmoid colon')})])
        self.assertEqual(e2['anchor']['kind_words'], {'start': TEXT.index('cold snare'),
                                                     'end': TEXT.index('cold snare') + len('cold snare')})
        self.assertEqual(view['events'][0]['date_relation']['claim']['inherited_from'], 'N2')
        self.assertIsNone(view['events'][1]['kind']['claim']['inherited_from'])
        self.assertEqual(view['units'], units())

    def test_the_view_is_a_copy(self):
        stored = load(read_row())
        before = json.dumps(stored.events, sort_keys=True)
        view = store.textfree_v2(stored)
        view['events'][1]['kind']['sources'][0]['at']['start'] = 0
        view['units'].clear()
        self.assertEqual(json.dumps(stored.events, sort_keys=True), before)
        self.assertEqual(store.textfree_v2(stored), store.textfree_v2(load(read_row())))
        self.assertIsNot(store.textfree_v2(stored)['events'], store.textfree_v2(stored)['events'])

    def test_only_a_read_row_as_load_v2_gives_it_has_a_view(self):
        with self.assertRaisesRegex(store.StoreError, 'was refused'):
            store.textfree_v2(load(refused_row()))
        for value in (read_row(), read_row()['events'], inventory()[0], None):
            with self.subTest(given=type(value).__name__):
                with self.assertRaises(TypeError):
                    store.textfree_v2(value)


# --- the revision binding of the words (P9, 3.1 B1) -------------------------------------------------------------------

class WordsTests(SimpleTestCase):
    def test_the_fixture_quotes_only_the_document(self):
        events = inventory()[0]
        found = words_records(events)
        self.assertEqual(len(found), 41)
        for path, record in found:
            self.assertEqual(TEXT[record['start']:record['end']], record['text'], dotted(path))
        kinds = {path[-1] if isinstance(path[-1], str) else path[-2] for path, _ in found}
        self.assertEqual(kinds, {'words', 'kind_words', 'status_words'})

    def test_words_that_are_not_the_revisions_own_slice_are_never_written(self):
        events = inventory()[0]
        found = words_records(events)
        self.assertTrue(found)
        for path, record in found:
            for change, edit in (('another text', lambda r: r.update(text='x' * len(r['text']))),
                                 ('other offsets', lambda r: r.update(start=r['start'] + 1, end=r['end'] + 1)),
                                 ('beyond the text', lambda r: r.update(start=len(TEXT), end=len(TEXT) + len(
                                     r['text']))),
                                 ('the model\'s spelling', lambda r: r.update(text=r['text'].swapcase()))):
                with self.subTest(at=dotted(path), change=change):
                    changed = copy.deepcopy(events)
                    edit(node(changed, *path))
                    if node(changed, *path)['text'] == record['text'] and change == 'the model\'s spelling':
                        continue  # a text with no letters has no other spelling
                    with self.assertRaisesRegex(store.Mismatch, 'quotes at events') as raised:
                        read_row(events=changed)
                    self.assertIn(dotted(('events',) + path), str(raised.exception))
                    self.assertNotIn(record['text'], str(raised.exception))

    def test_a_unit_beyond_the_text_is_never_written(self):
        events = inventory()[0]
        events['units'][-1]['end'] = len(TEXT) + 5
        with self.assertRaisesRegex(store.Mismatch, r'events\.units\[8\] beyond the revision text'):
            read_row(events=events)

    def test_the_text_given_must_be_the_text_the_row_names(self):
        with self.assertRaisesRegex(store.Mismatch, 'text_sha256'):
            read_row(revision_text=TEXT + ' ')
        with self.assertRaisesRegex(store.Mismatch, 'text_sha256'):
            read_row(revision_text='\ud800' + TEXT)  # a text UTF-8 cannot encode names no revision
        with self.assertRaises(TypeError):
            read_row(revision_text=TEXT.encode())

    def test_load_keeps_what_needs_no_text(self):
        fields = read_row()
        for name, edit in {'words longer than their offsets': setter('events', 'events', 1, 'anchor', 'kind_words',
                                                                    'end', value=fields['events']['events'][1]
                                                                    ['anchor']['kind_words']['end'] + 1),
                           'a negative start': setter('events', 'people', 0, 'name', 'words', 'start', value=-1)
                           }.items():
            with self.subTest(words=name):
                with self.assertRaises(store.UnknownShape):
                    load(variant(fields, edit))


# --- the refused row: a refused PASS-1 answer only (6.3) --------------------------------------------------------------

class RefusedRowTests(SimpleTestCase):
    def test_a_refused_row(self):
        fields = refused_row()
        self.assertEqual(tuple(fields), store.FIELDS_V2)
        self.assertEqual((fields['state'], fields['appraisal_run_id'], fields['events'], fields['encounter_facts'],
                          fields['open_questions']), ('refused', None, {}, {}, []))
        self.assertEqual(fields['verification'], {
            'label': 'gemini-events@2/appraisal@1+inventory@2', 'request_sha256': REQUEST_SHA256,
            'response_sha256': RESPONSE_SHA256, 'refused': True, 'stage': 'bounds', 'problems': [refusal().reason]})
        loaded = load(fields)
        self.assertEqual((loaded.refused, loaded.refusal_stage, loaded.refusal_reason, loaded.appraisal_run_id),
                         (True, 'bounds', refusal().reason, None))
        for name in ('events', 'claims_sha256'):
            with self.subTest(read=name):
                with self.assertRaisesRegex(store.StoreError, 'was refused'):
                    getattr(loaded, name)

    def test_there_is_no_refused_pass_2_row(self):
        # the writer has no way to name an appraisal run on a refused row
        parameters = inspect.signature(store.refused_row_v2).parameters
        self.assertFalse([name for name in parameters if 'appraisal' in name])
        with self.assertRaises(TypeError):
            refused_row(appraisal_run_id=APPRAISAL_RUN)
        # and no function of the store writes or reads a refused row with one
        for name, function in inspect.getmembers(store, inspect.isfunction):
            if 'refused' in name and function.__module__ == store.__name__:
                with self.subTest(function=name):
                    self.assertFalse([p for p in inspect.signature(function).parameters if 'appraisal' in p])
        fields = refused_row()
        # a refused row that names an appraisal run is refused, and so is a refused report carrying pass 2's
        with self.assertRaisesRegex(store.UnknownShape, 'names none'):
            load(variant(fields, setter('appraisal_run_id', value=APPRAISAL_RUN)),
                 appraisal_response_sha256=APPRAISAL_RESPONSE_SHA256)
        for key, value in (('appraisal_response_sha256', APPRAISAL_RESPONSE_SHA256), ('claims_sha256', '1' * 64),
                           ('health', {'establishment': 0.1})):
            with self.subTest(report=key):
                with self.assertRaises(store.UnknownShape):
                    load(variant(fields, setter('verification', key, value=value)))
        with self.assertRaisesRegex(store.Mismatch, 'no appraisal response'):
            load(fields, appraisal_response_sha256=APPRAISAL_RESPONSE_SHA256)
        # a refused row's events are empty, and its stage one of pass 1's: there is no appraisal stage
        with self.assertRaises(store.UnknownShape):
            load(variant(fields, setter('events', value=inventory()[0])))
        for stage in ('appraisal', 'appraise', 'verdicts', 'health', 'claims'):
            with self.subTest(stage=stage):
                with self.assertRaises(store.UnknownShape):
                    load(variant(fields, setter('verification', 'stage', value=stage)))
                with self.assertRaises(store.UnknownShape):
                    store.refused_row_v2(SimpleNamespace(stage=stage, reason=refusal().reason), encounter_id=ENCOUNTER,
                                         revision_id=REVISION, provider_run_id=RUN, text_sha256=TEXT_SHA256,
                                         request_sha256=REQUEST_SHA256, response_sha256=RESPONSE_SHA256)

    def test_pass_1s_stages_and_sentence_are_contracts_own_never_a_copy(self):
        # triage 1d#6 (FINAL-V2 5.7): the store reads contract/extract_read's STAGES and REFUSED - the very objects,
        # read when used - and keeps no copy of its own; contract's are v1's (3.1 S1, "as v1"; test_extract_read)
        self.assertIs(store.xr, extract_read)
        for name in ('REFUSAL_STAGES_V2', 'REFUSAL_PREFIX_V2', '_v2_precision', '_V2_PRECISIONS'):
            self.assertFalse(hasattr(store, name), name)
        self.assertEqual(store._V2_REPORT_REFUSED.fields['stage'].values, {stage.value for stage in extract_read.Stage})
        self.assertEqual((extract_read.STAGES, extract_read.REFUSED), (read.STAGES, read.REFUSED))
        pin = store.shape_signature_v2(store.READ_VERSIONS[0])
        with mock.patch.object(extract_read, 'STAGES', extract_read.STAGES + ('appraisal',)):
            self.assertNotEqual(store.shape_signature_v2(store.READ_VERSIONS[0]), pin)  # the signature reads them
        with mock.patch.object(extract_read, 'REFUSED', 'Not used: '):
            with self.assertRaisesRegex(store.UnknownShape, 'exactly one problem'):
                load(refused_row())  # a sentence opening with another prefix than contract's is no refusal
        self.assertEqual(store.shape_signature_v2(store.READ_VERSIONS[0]), pin)
        # and the v2 section writes out neither the prefix nor a collection of stage names (a collection naming two or
        # more stages; the one stage-like word it holds is 'json', the tag of _V2Json's describe(), alone in its list)
        first = _v2_first_line()
        tree = ast.parse(STORE.read_text(encoding='utf-8'))
        written = {node.value for node in ast.walk(tree)
                   if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.lineno > first}
        self.assertNotIn(extract_read.REFUSED, written)
        collections = [ast.unparse(node) for node in ast.walk(tree) if isinstance(node, (ast.Tuple, ast.List, ast.Set))
                       and node.lineno > first and sum(isinstance(item, ast.Constant) and item.value in
                                                       extract_read.STAGES for item in node.elts) >= 2]
        self.assertEqual(collections, [])
        for stage in extract_read.STAGES:
            with self.subTest(stage=stage):
                fields = store.refused_row_v2(refusal(stage), encounter_id=ENCOUNTER, revision_id=REVISION,
                                              provider_run_id=RUN, text_sha256=TEXT_SHA256,
                                              request_sha256=REQUEST_SHA256, response_sha256=RESPONSE_SHA256)
                self.assertEqual(load(fields).refusal_stage, stage)
        # contract's own Refusal, and v1's read.Refusal, are stored as they stand
        for refused in (extract_read.refuse('schema', 'the answer breaks the interpretation schema: synthetic'),
                        read.refuse('schema', 'the answer breaks the interpretation schema: synthetic')):
            with self.subTest(refusal=type(refused).__module__):
                loaded = load(store.refused_row_v2(refused, encounter_id=ENCOUNTER, revision_id=REVISION,
                                                   provider_run_id=RUN, text_sha256=TEXT_SHA256,
                                                   request_sha256=REQUEST_SHA256, response_sha256=RESPONSE_SHA256))
                self.assertEqual((loaded.refusal_stage, loaded.refusal_reason), (refused.stage, refused.reason))

    def test_a_refused_row_records_exactly_one_refusal_sentence(self):
        fields = refused_row()
        for name, problems in (('none', []), ('two', [refusal().reason, refusal().reason]),
                               ('not a refusal sentence', ['It was refused.']),
                               ('no full stop', [refusal().reason[:-1]])):
            with self.subTest(problems=name):
                with self.assertRaisesRegex(store.UnknownShape, 'exactly one problem'):
                    load(variant(fields, setter('verification', 'problems', value=problems)))
        for refused in ({'stage': 'json', 'reason': refusal().reason}, 'json', SimpleNamespace(stage='json'),
                        SimpleNamespace(stage='json', reason=refusal().reason, refused=False)):
            with self.subTest(refusal=refused):
                with self.assertRaises(TypeError):
                    store.refused_row_v2(refused, encounter_id=ENCOUNTER, revision_id=REVISION, provider_run_id=RUN,
                                         text_sha256=TEXT_SHA256, request_sha256=REQUEST_SHA256,
                                         response_sha256=RESPONSE_SHA256)


class CopyTests(SimpleTestCase):
    def test_what_load_gives_shares_nothing_with_the_row(self):
        fields = read_row()
        before = json.dumps(fields, sort_keys=True)
        loaded = load(fields)
        loaded.events['events'].clear()
        loaded.verification['usage'].clear()
        self.assertEqual(json.dumps(fields, sort_keys=True), before)
        self.assertEqual(len(load(fields).events['events']), 3)


# --- the v2 reader executes contract/ only (5.7; the design's "a v2 reader importing only contract/") -----------------

def _v2_first_line() -> int:
    lines = STORE.read_text(encoding='utf-8').split('\n')
    marks = [number for number, line in enumerate(lines, 1) if line.startswith('# === design v2 (FINAL-V2')]
    assert len(marks) == 1, marks
    return marks[0]


def traced(work) -> list:
    """(file, first line, qualified name) of every Python function ``work`` executes."""
    calls = []

    def profile(frame, event, _):
        if event == 'call':
            code = frame.f_code
            calls.append((code.co_filename, code.co_firstlineno, code.co_qualname))

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        work()
    finally:
        sys.setprofile(previous)
    return calls


class ImportTests(SimpleTestCase):
    def test_the_v2_reader_executes_only_contract_and_the_standard_library(self):
        first = _v2_first_line()

        def work():
            fields = read_row()
            stored = load(fields)
            stored.events, stored.claims_sha256, stored.label
            refused = load(refused_row())
            refused.refusal_stage, refused.refusal_reason
            store.load_v2(store.fields_of_v2(SimpleNamespace(**fields, id=None, created_at=None)),
                          text_sha256=TEXT_SHA256, response_sha256=RESPONSE_SHA256,
                          appraisal_response_sha256=APPRAISAL_RESPONSE_SHA256)
            store.shape_signature_v2(store.READ_VERSIONS[0])
            store.textfree_v2(stored)
            for bad in (setter('state', value='pending'), setter('events', 'units', 0, 'id', value='S9')):
                try:
                    load(variant(fields, bad))
                except store.StoreError:
                    pass

        calls = traced(work)
        studio = str(APP / 'studio')
        mine = [call for call in calls if call[0] == str(STORE)]
        contract = [call for call in calls if call[0].startswith(str(CONTRACT))]
        others = [call for call in calls if call[0].startswith(studio) and call[0] != str(STORE)
                  and not call[0].startswith(str(CONTRACT))]
        self.assertEqual(others, [])  # no schema, read, studio.types or other studio module
        before = sorted({(line, name) for _, line, name in mine if line < first})
        self.assertEqual(before, [])  # no line of v1's reader
        # positive controls: the trace sees the store's v2 code and contract/ code run
        self.assertTrue(any(name == 'load_v2' for _, _, name in mine))
        self.assertTrue(any(name == 'textfree_v2' for _, _, name in mine))
        self.assertTrue(any(path.endswith('jsonschema.py') for path, _, _ in contract))
        # the dates are read by contract/extract_read's own iso_date and partial_date (triage 1d#6)
        self.assertEqual({name for path, _, name in contract if path.endswith('extract_read.py')} & {'iso_date',
                                                                                                    'partial_date'},
                         {'iso_date', 'partial_date'})

    def test_the_trace_sees_v1s_modules_when_v1s_writer_runs(self):
        # the negative control: the same trace over v1's row sees read, studio.types and v1's own reader
        from tests import test_interpretation_store as v1
        calls = traced(v1.read_row)
        files = {Path(path).name for path, _, _ in calls if path.startswith(str(APP / 'studio'))}
        self.assertTrue({'read.py', 'types.py', 'store.py'} <= files, files)
        first = _v2_first_line()
        self.assertTrue([line for path, line, _ in calls if path == str(STORE) and line < first])

    def test_the_v2_section_names_nothing_of_v1(self):
        tree = ast.parse(STORE.read_text(encoding='utf-8'))
        first = _v2_first_line()
        v1_defined = set()
        for statement in tree.body:
            if statement.lineno >= first:
                break
            if isinstance(statement, (ast.FunctionDef, ast.ClassDef)):
                v1_defined.add(statement.name)
            elif isinstance(statement, ast.Assign):  # the assigned names, never a comprehension's variables
                v1_defined.update(name.id for target in statement.targets for name in ast.walk(target)
                                  if isinstance(name, ast.Name))
        v1_imported = {'schema', 'STAGES', 'Refusal', 'iso_date', 'sha256_json', 'to_jsonable', 'LABEL',
                       'INTERPRETATION_VERSION', 'INVENTORY_VERSION', 're'}
        shared = {'READ', 'REFUSED', 'StoreError', 'UnknownVersion', 'UnknownShape', 'Mismatch'}
        self.assertTrue(shared <= v1_defined)
        used = {node.id for statement in tree.body if statement.lineno > first for node in ast.walk(statement)
                if isinstance(node, ast.Name)}
        self.assertEqual(used & (v1_defined - shared), set())
        self.assertEqual(used & v1_imported, set())
        # the v2 section's imports are contract/'s, made inside _v2_build (on first use), and nothing else; at the
        # module's top it adds the package's labels only
        inside = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                  and node.lineno > first]
        self.assertEqual(sorted((node.module, tuple(alias.name for alias in node.names)) for node in inside),
                         [('studio.interpretation.contract', ('extract_read',)),
                          ('studio.interpretation.contract', ('types',)),
                          ('studio.interpretation.contract.jsonschema', ('sha256_of',))])
        build = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_v2_build')
        self.assertTrue(all(build.lineno < node.lineno <= build.end_lineno for node in inside))
        labels = [statement for statement in tree.body if isinstance(statement, ast.ImportFrom)
                  and statement.module == 'studio.interpretation'
                  and 'INTERPRETATION_PAIR' in [alias.name for alias in statement.names]]
        self.assertEqual([[alias.name for alias in statement.names] for statement in labels],
                         [['INTERPRETATION_PAIR', 'INVENTORY_VERSION_V2']])

    def test_importing_the_store_loads_no_contract_module_until_v2_is_used(self):
        # importing store loads what v1's store did (tests/test_interpretation_prompt.py pins that set); the first v2
        # use imports contract/types, contract/jsonschema and contract/extract_read (with the extract_schema it reads),
        # and nothing else
        code = ('import sys\n'
                'import studio.interpretation.store as store\n'
                'before = sorted(m for m in sys.modules if m.startswith("studio"))\n'
                'store._v2()\n'
                'after = sorted(m for m in sys.modules if m.startswith("studio"))\n'
                'print(",".join(before)); print(",".join(sorted(set(after) - set(before))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=60, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        before, added = result.stdout.strip().split('\n')
        self.assertFalse([name for name in before.split(',') if 'contract' in name or 'engine' in name], before)
        self.assertEqual(before.split(','), ['studio', 'studio.interpretation', 'studio.interpretation.read',
                                             'studio.interpretation.schema', 'studio.interpretation.store',
                                             'studio.participants', 'studio.participants.prompt',
                                             'studio.participants.reading', 'studio.types'])
        self.assertEqual(added.split(','), ['studio.interpretation.contract',
                                            'studio.interpretation.contract.extract_read',
                                            'studio.interpretation.contract.extract_schema',
                                            'studio.interpretation.contract.jsonschema',
                                            'studio.interpretation.contract.types'])

    def test_ids_are_read_as_the_engine_reads_them(self):
        # store's id letters and canonical form are engine/types.IdFamily and Id.parse, computed here
        self.assertEqual(set(store.ID_LETTERS_V2), {family.value for family in et.IdFamily})
        for label in ('E3', 'N0', 'X12', 'S400', 'P1', 'Y9', 'L64', 'E03', 'E+3', 'E 3', 'E', 'e3', 'Q1', 'E٣', '',
                      'S1000000000', 'N00'):
            with self.subTest(label=label):
                try:
                    et.Id.parse(label)
                    engine = True
                except ValueError:
                    engine = False
                self.assertEqual(store._v2_id(label, store.ID_LETTERS_V2), engine and len(label) <= 10)

    def test_iso_dates_at_their_precision(self):
        # triage 1d#6: the precision is read by contract/extract_read's iso_date (a day) and partial_date (a month or a
        # year), pass 1's own date shapes, so the store and S1 never disagree about what a date is
        for value, precision in (('2026', 'year'), ('2026-11', 'month'), ('2026-11-09', 'day'), ('2024-02-29', 'day'),
                                 ('2026-02-29', ''), ('2026-13', ''), ('0000', ''), ('2026-1-09', ''),
                                 ('2026/11/09', ''), ('20261109', ''), ('２０２６', ''), ('2026-11-09T00', ''), (2026, ''),
                                 ('0001', 'year'), ('2026-00', ''), ('2026-11-31', ''), ('', ''), (None, '')):
            with self.subTest(value=value):
                self.assertEqual(store._v2_date_precision(value), precision)
                if isinstance(value, str):
                    self.assertEqual(precision == 'day', extract_read.iso_date(value))
                    self.assertEqual(precision in ('month', 'year'), extract_read.partial_date(value))
                if precision:
                    et.IsoDate(value=datetime.date(int(value[:4]), int(value[5:7] or 1), int(value[8:10] or 1)),
                               precision=ct.Precision(precision))
        with mock.patch.object(extract_read, 'iso_date', lambda value: False):
            self.assertEqual(store._v2_date_precision('2026-11-09'), '')  # it is contract's function that reads it
        with mock.patch.object(extract_read, 'partial_date', lambda value: False):
            self.assertEqual(store._v2_date_precision('2026-11'), '')


# --- PostgreSQL -------------------------------------------------------------------------------------------------------

class DatabaseRoundTripTests(TestCase):
    """Rows written to PostgreSQL (jsonb) and read back keep their sha256 and their content, bound to their revision
    text and to both runs' stored response bytes; v1's rows on the same table still read through v1's reader."""

    def setUp(self):
        self.workspace = f.workspace()
        self.member = f.member(self.workspace)
        self.encounter = f.encounter(self.workspace, self.member)
        self.revision = SourceRevision.objects.get(pk=f.pasted_revision(self.encounter, self.member, TEXT).pk)
        self.assertEqual(self.revision.text_sha256, TEXT_SHA256)

    def run_of(self, purpose, number):
        response = f'{{"synthetic": "{purpose} response bytes {number}"}}'.encode()
        return ProviderRun.objects.create(
            encounter=self.encounter, revision=self.revision, provider='gemini',
            adapter_version='gemini-generate@cptstudio-2', request_sha256=REQUEST_SHA256, request_body={},
            contexts=[], state=ProviderRun.SUCCEEDED, purpose=purpose, response_bytes=response,
            response_sha256=hashlib.sha256(response).hexdigest())

    def written(self, fields):
        return EventInventory.objects.create(**{name: fields[name] for name in store.FIELDS_V2})

    def test_rows_written_and_read_back_keep_their_hash(self):
        first, retry, appraisal = (self.run_of('interpretation', 1), self.run_of('interpretation', 2),
                                   self.run_of('appraisal', 3))
        bound = {'encounter_id': self.encounter.pk, 'revision_id': self.revision.pk,
                 'text_sha256': self.revision.text_sha256, 'request_sha256': REQUEST_SHA256}
        rows = [store.refused_row_v2(refusal(), provider_run_id=first.pk, response_sha256=first.response_sha256,
                                     **bound),
                read_row(provider_run_id=retry.pk, response_sha256=retry.response_sha256, appraisal_run_id=appraisal.pk,
                         appraisal_response_sha256=appraisal.response_sha256, revision_text=self.revision.text,
                         **bound)]
        for fields in rows:
            self.written(fields)
        for fields in rows:
            with self.subTest(state=fields['state']):
                stored = EventInventory.objects.select_related('provider_run', 'appraisal_run').get(
                    sha256=fields['sha256'])
                response = bytes(stored.provider_run.response_bytes)
                second = None if stored.appraisal_run is None else bytes(stored.appraisal_run.response_bytes)
                loaded = store.load_v2(store.fields_of_v2(stored), text_sha256=self.revision.text_sha256,
                                       response_sha256=hashlib.sha256(response).hexdigest(),
                                       appraisal_response_sha256=None if second is None
                                       else hashlib.sha256(second).hexdigest())
                self.assertEqual((loaded.sha256, loaded.state, loaded.revision_id),
                                 (fields['sha256'], fields['state'], str(self.revision.pk)))
                if loaded.refused:
                    self.assertEqual((loaded.refusal_stage, loaded.appraisal_run_id), ('bounds', None))
                    self.assertIsNone(stored.appraisal_run_id)
                    continue
                self.assertEqual(loaded.appraisal_run_id, str(appraisal.pk))
                self.assertEqual(loaded.events, inventory()[0])
                found = words_records(loaded.events)
                self.assertEqual(len(found), 41)
                for path, record in found:  # through jsonb, each words record is still the stored text's own slice
                    self.assertEqual(stored.revision.text[record['start']:record['end']], record['text'], dotted(path))
                with self.assertRaisesRegex(store.Mismatch, 'another appraisal response'):
                    store.load_v2(store.fields_of_v2(stored), text_sha256=self.revision.text_sha256,
                                  response_sha256=hashlib.sha256(response).hexdigest(),
                                  appraisal_response_sha256=hashlib.sha256(second + b' ').hexdigest())
                # v1's reader, kept, refuses the v2 row: it names an appraisal run
                with self.assertRaisesRegex(store.UnknownShape, 'names an appraisal run'):
                    store._v1_reader.fields_of(stored)

    def test_the_unique_key_holds_one_read_row_per_pass_1_run_and_version_pair(self):
        # 6.3: the key is unchanged and sufficient - a second read row for one pass-1 run and version pair is refused
        # whatever its appraisal run, and a retry is a new pass-1 run, so its row is a new key
        run, appraisal, other = self.run_of('interpretation', 1), self.run_of('appraisal', 2), self.run_of('appraisal',
                                                                                                           3)
        bound = {'encounter_id': self.encounter.pk, 'revision_id': self.revision.pk,
                 'text_sha256': self.revision.text_sha256, 'request_sha256': REQUEST_SHA256,
                 'provider_run_id': run.pk, 'response_sha256': run.response_sha256}
        self.written(read_row(appraisal_run_id=appraisal.pk, appraisal_response_sha256=appraisal.response_sha256,
                              **bound))
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.written(read_row(appraisal_run_id=other.pk, appraisal_response_sha256=other.response_sha256,
                                  **bound))
        bound.pop('provider_run_id')
        bound.pop('response_sha256')
        retried = self.run_of('interpretation', 4)
        self.written(read_row(appraisal_run_id=other.pk, appraisal_response_sha256=other.response_sha256,
                              provider_run_id=retried.pk, response_sha256=retried.response_sha256, **bound))
        self.assertEqual(EventInventory.objects.filter(revision=self.revision).count(), 2)

    def test_v1_rows_on_the_same_table_read_as_they_always_have(self):
        from tests import test_interpretation_store as v1
        v1_revision = SourceRevision.objects.get(pk=f.pasted_revision(self.encounter, self.member, v1.TEXT).pk)
        run = self.run_of('interpretation', 7)
        fields = store.row(encounter_id=self.encounter.pk, revision_id=v1_revision.pk, provider_run_id=run.pk,
                           revision_text=v1_revision.text, text_sha256=v1_revision.text_sha256,
                           request_sha256=REQUEST_SHA256, response_sha256=run.response_sha256, **v1.content())
        EventInventory.objects.create(**{name: fields[name] for name in store.FIELDS})  # as jobs.py writes it
        stored = EventInventory.objects.get(sha256=fields['sha256'])
        self.assertIsNone(stored.appraisal_run_id)
        for reader in (store, store._v1_reader):
            with self.subTest(reader=reader.__name__):
                loaded = reader.load(reader.fields_of(stored), text_sha256=v1_revision.text_sha256,
                                     response_sha256=run.response_sha256)
                self.assertEqual(loaded.sha256, fields['sha256'])
        with self.assertRaises(store.UnknownVersion):  # and v2 never reads it
            store.load_v2(store.fields_of_v2(stored), text_sha256=v1_revision.text_sha256,
                          response_sha256=run.response_sha256, appraisal_response_sha256=None)
