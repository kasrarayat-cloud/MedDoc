"""Reading results (docs/gemini-migration/FINAL-V2.md 4.1, 4.2, 1.7 and 6.5; step 2d of its 8.1), TEXT-ONLY and SYNTHETIC:
engine/facts.py builds the typed, text-free FactSet from store.textfree_v2's view of a stored v2 row (DECISIONS D188) -
every row here is written by store.row_v2, read back by store.load_v2 and viewed by store.textfree_v2, so it is a row
the store accepts - and its predicates read it.

What is proved here:
- the FactSet holds enumeration members, ids, dates, results, reasons and integer spans only: no string anywhere, no
  stored words or text copied (a fact's spans are its cited units; an anchor's words are offsets), and no public
  accessor of facts.py returns a string; ``mypy --strict`` passes over engine/types.py, facts.py and reading.py (5.7
  measure 5), with its positive control; the builder reads the text-free view only (D188: the row and its events as
  stored are refused);
- each fact's ``cited`` sources (link, units span, located words' offsets), its ``inherited_from`` and its ``counter``
  evidence (D188; triage 2d#2): C-10's statement-linked words are read off ``cited``, so the kept span 'cold snare'
  lying inside E2's target unit but outside its target words is told apart (the arbiter's input);
- options: a contradicted fact's sides, a doubt's readings (also through the section an inherited fact came from), and
  the value of a control pass 2 did not reject; none for an established fact;
- holds, denied, established and possibly at every result; a status that is not established leaves every status
  possible (HO-1's doubted act, HO-3's caught misfiling); the kind arm of a statement widened to its session's family
  (HO-5) over THE family table K2 reads too (requirements_table.FAMILY_KINDS, D191; triage 2d#1): P-UNKNOWN-KIND over
  every (family, kind) of it, read off that table so a narrowed copy turns red; apart_by_lesion and apart_by_place
  only on established targets and rejected pair controls in both directions, SC-B's short list held;
- effective(): L1 re-judged on the stored literals of every timing fact against the effective date - a member's date,
  none, a coarse literal - demoting only; the re-judge equals the claim-time rule (contract/consistency.rejudge,
  imported here only) over the grid relation x precision x literal x service date (D193);
- every unreadable row is refused (FactSetError), and the new modules keep 5.7 measure 4 (step 0b's scanner).
Every document here is written for this test: no real patient, no development or acceptance document.
"""
from __future__ import annotations

import datetime
import enum
import hashlib
import inspect
import json
import os
import subprocess
import sys
import typing
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation import store
from studio.interpretation.contract import extract_read
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import reading as RD
from studio.interpretation.engine import requirements_table as RT
from studio.interpretation.engine.types import Cited, Fact, FactSet, Id, IdFamily, IsoDate, Span
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
ENGINE = APP / 'studio' / 'interpretation' / 'engine'
A = ct.Attribute
E1, E2, E3, E4, E5 = (Id(IdFamily.EVENT, n) for n in range(1, 6))
X1, X2 = Id(IdFamily.SESSION, 1), Id(IdFamily.SESSION, 2)
N0, N1, N2 = (Id(IdFamily.SECTION, n) for n in range(3))
L1, L2 = Id(IdFamily.LESION, 1), Id(IdFamily.LESION, 2)
P1, Y1 = Id(IdFamily.PERSON, 1), Id(IdFamily.ANATOMY, 1)

ENCOUNTER = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e2001'
REVISION = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e2002'
RUN = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e2003'
APPRAISAL_RUN = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e2004'

# The synthetic revision (no real patient; written for this test), one unit per line.
LINES = (
    'SYNTHETIC COLONOSCOPY REPORT - FICTIONAL PATIENT - NOT FOR CLINICAL USE',  # S1
    'Date of service: 11/09/2026',  # S2
    'Endoscopist: Synthetic Endoscopist, MD (fictional)',  # S3
    'History: Prior colonoscopy in 2023.',  # S4
    'Findings: The colonoscope was advanced to the cecum.',  # S5
    'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.',  # S6
    'No biopsies were taken from the rectum.',  # S7
    'It is unclear whether a tattoo was placed.',  # S8
    'DOB: 01/02/1960',  # S9
    'Next procedure: 11/04/2026',  # S10
    'Biopsies were taken from the transverse colon and the rectum.',  # S11
)
TEXT = '\n'.join(LINES) + '\n'
TEXT_SHA256 = hashlib.sha256(TEXT.encode('utf-8')).hexdigest()
DAY = [{'value': '2026-11-09', 'precision': 'day'}]


def unit_span(index: int) -> Span:
    """S<index>'s span in TEXT."""
    start = sum(len(line) + 1 for line in LINES[:index - 1])
    return Span(start, start + len(LINES[index - 1]))


def units() -> list:
    return [{'id': f'S{n}', 'start': unit_span(n).start, 'end': unit_span(n).end, 'line': n, 'paragraph': n,
             'page': 1, 'forced': False} for n in range(1, len(LINES) + 1)]


def at(words: str, after: str = '') -> dict:
    """Words located in TEXT where they first occur at or after ``after``: the revision's own slice."""
    start = TEXT.index(words, TEXT.index(after) if after else 0)
    return {'start': start, 'end': start + len(words), 'text': words}


def src(cited, link='statement', words=None) -> dict:
    return {'units': list(cited), 'link': link, 'words': words, 'geometry': 'ok'}


def checks(literals=()) -> dict:
    return {'integrity': 'ok', 'geometry': 'ok', 'literal': 'ok', 'literals': list(literals), 'consistency': 'ok',
            'qualified': False}


def claim(state, value, *, options=(), inherited_from=None) -> dict:
    return {'state': state, 'value': value, 'qualifiers': [], 'options': list(options),
            'inherited_from': inherited_from}


def silent() -> dict:
    return {'claim': claim(None, ''), 'sources': [], 'checks': checks(), 'appraisal': None, 'result': 'unknown',
            'reasons': ['silent']}


def fact(value, sources, *, state='supported', result='unresolved', reasons=('unappraised',), appraisal=None,
         inherited_from=None, options=(), literals=()) -> dict:
    """A fact that is not established (unappraised by default)."""
    return {'claim': claim(state, value, options=options, inherited_from=inherited_from), 'sources': list(sources),
            'checks': checks(literals), 'appraisal': appraisal, 'result': result, 'reasons': list(reasons)}


class Ledger:
    """The stored claim list, as settle builds it: K<n> in seeded order, each verdict stored with its content key."""

    def __init__(self):
        self.claims = []

    def add(self, role, subject, attribute, value, cited, verdict='supports', *, evidence=None, qualifiers=()):
        """``evidence``: the units the verdict relies on (the cited units by default); ``qualifiers``: those it names."""
        content = hashlib.sha256(json.dumps([role, subject, attribute, value, list(cited)]).encode()).hexdigest()
        entry = {'id': f'K{len(self.claims) + 1}', 'role': role, 'template': f'synthetic.{role}.{attribute}',
                 'subject': subject, 'attribute': attribute, 'value': value, 'units': list(cited), 'content': content,
                 'verdict': None if verdict is None else {
                     'verdict': verdict, 'attached': 'yes', 'qualifiers': list(qualifiers),
                     'evidence': list(cited if evidence is None else evidence)}}
        self.claims.append(entry)
        return entry

    def appraised(self, subject, attribute, value, cited, *, verdict='supports', control=None,
                  control_verdict='contradicts', role='claim', evidence=None, qualifiers=()) -> dict:
        entry = self.add(role, subject, attribute, value, cited, verdict, evidence=evidence, qualifiers=qualifiers)
        appraisal = {'claim': entry['id'], 'content': entry['content'], 'verdict': verdict,
                     'attached': None if verdict is None else 'yes',
                     'qualifiers': [] if verdict is None else list(qualifiers),
                     'evidence': [] if verdict is None else list(cited if evidence is None else evidence),
                     'control': None}
        if control is not None:
            other = self.add('control' if role == 'claim' else 'completeness_control', subject, attribute, control,
                             cited, control_verdict)
            appraisal['control'] = {'claim': other['id'], 'verdict': control_verdict}
        return appraisal

    def pair(self, subject, attribute, asked, cited, verdict):
        self.add('pair_control', subject, attribute, asked, cited, verdict)


def est(ledger, subject, attribute, value, sources, *, state='supported', control=None, inherited_from=None,
        literals=()) -> dict:
    """An established fact: its claim supported (or negated), attached, its control (if any) contradicted."""
    cited = [unit for source in sources for unit in source['units']] or ['S1']
    return {'claim': claim(state, value, inherited_from=inherited_from), 'sources': list(sources),
            'checks': checks(literals), 'appraisal': ledger.appraised(subject, attribute, value, cited,
                                                                       control=control),
            'result': state, 'reasons': []}


def unsettled(ledger, subject, attribute, value, sources, *, verdict='unclear', control=None,
              control_verdict='supports', reasons=('appraisal_unclear',), literals=(), inherited_from=None,
              evidence=None, qualifiers=()) -> dict:
    """An appraised fact pass 2 did not establish (``evidence`` and ``qualifiers``: its verdict's)."""
    cited = [unit for source in sources for unit in source['units']] or ['S1']
    return fact(value, sources, reasons=reasons, literals=literals, inherited_from=inherited_from,
                appraisal=ledger.appraised(subject, attribute, value, cited, verdict=verdict, control=control,
                                           control_verdict=control_verdict, evidence=evidence,
                                           qualifiers=qualifiers))


def event(id, anchor, kind_words=None, status_words=None, **facts) -> dict:
    item = {'id': id, 'anchor': {'units': list(anchor), 'kind_words': kind_words, 'status_words': status_words},
            'restatements': [], 'kind': silent(), 'other_class': silent(), 'status': silent(), 'session': silent(),
            'date_relation': silent(), 'date': silent(), 'performer': silent(), 'performer_person': silent(),
            'entry': silent(),
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


def section(id, start, **facts) -> dict:
    item = {'id': id, 'start': start, 'end': [], 'owner': silent(), 'role': silent(), 'occasion': silent(),
            'performer': silent(), 'performer_person': silent()}
    item.update(facts)
    return item


def lesion(id, description, **facts) -> dict:
    item = {'id': id, 'description': description, 'multiplicity': silent(), 'places': [], 'distinct_from': [],
            'same_as': []}
    item.update(facts)
    return item


def encounter(date_of_service=None, other_dates=(), documenting_clinician=None) -> dict:
    return {'date_of_service': date_of_service or silent(), 'other_dates': list(other_dates),
            'documenting_clinician': documenting_clinician or silent()}


def content(ledger, *, encounter_=None, people=(), sections=(), sessions=(), anatomy=(), lesions=(), events=(),
            doubts=(), unlisted=()) -> dict:
    return {'units': units(), 'encounter': encounter_ or encounter(), 'people': list(people),
            'sections': list(sections), 'sessions': list(sessions), 'anatomy': list(anatomy),
            'lesions': list(lesions), 'events': list(events), 'doubts': list(doubts), 'claims': ledger.claims,
            'unlisted': list(unlisted)}


def report(unlisted=0) -> dict:
    return {'counts': {}, 'reasons': {}, 'doubts': [], 'health': {}, 'coherence': {},
            'unlisted': {'kept': unlisted, 'dropped': []}, 'usage': {'interpretation': {}, 'appraisal': {}}}


def stored(events: dict) -> store.StoredInventoryV2:
    """``events`` written by store.row_v2 (so the store accepts it) and read back by store.load_v2."""
    fields = store.row_v2(encounter_id=ENCOUNTER, revision_id=REVISION, provider_run_id=RUN,
                          appraisal_run_id=APPRAISAL_RUN, revision_text=TEXT, text_sha256=TEXT_SHA256,
                          request_sha256='2' * 64, response_sha256='3' * 64, appraisal_request_sha256='4' * 64,
                          appraisal_response_sha256='5' * 64, events=events,
                          verification=report(len(events['unlisted'])))
    fields = json.loads(json.dumps(fields))
    return store.load_v2(fields, text_sha256=TEXT_SHA256, response_sha256='3' * 64,
                         appraisal_response_sha256='5' * 64)


def view(events: dict) -> typing.Mapping:
    """``events`` as the engine reads them (DECISIONS D188): written and read back by the store (``stored``), then
    given as store.textfree_v2's view - every source's located words as their offsets (``at``), and no text."""
    return store.textfree_v2(stored(events))


def colonoscopy() -> dict:
    """The settled inventory of TEXT in every shape the FactSet presents (module docstring): the encounter with a date
    of service and two other dates; a person; three sections; a colonoscopy session X1 and an upper EUS session X2
    whose kind pass 2 left unclear (its control's egd not rejected) and whose empty stations list has an established
    completeness claim; an anatomy entry; two lesions; an examination E1, a cold snare E2 on the sigmoid polyp, a rectal
    biopsy denial E3 whose performer a doubt names, a doubted tattoo E4 whose kind pass 2 left unclear, and a biopsy E5
    filed with the transverse colon only (SC-B); pair controls; a kept unlisted doubt."""
    k = Ledger()
    dos = lambda: src(['S2'], 'document_frame', at('11/09/2026'))  # noqa: E731
    clinician = lambda: src(['S3'], 'document_frame')  # noqa: E731
    findings = lambda: src(['S5'], 'section', at('Findings:'))  # noqa: E731
    inherited = dict(inherited_from='N2')
    sections = [
        section('N0', src([], 'section'), owner=fact('documenting_clinician', [clinician()]),
                role=fact('header', [src(['S1'], 'section')]), occasion=fact('on_date_of_service', [dos()]),
                performer=fact('documenting_team', [clinician()])),
        section('N1', src(['S4'], 'section', at('History:')), owner=fact('documenting_clinician', [clinician()]),
                role=fact('history', [src(['S4'], 'section')]),
                occasion=est(k, 'N1', 'occasion', 'earlier_date',
                             [src(['S4'], 'section', at('Prior colonoscopy in 2023'))], control='on_date_of_service',
                             literals=[{'value': '2023', 'precision': 'year'}])),
        section('N2', src(['S5'], 'section', at('Findings:')), owner=fact('documenting_clinician', [clinician()]),
                role=fact('findings', [src(['S5'], 'section')]),
                occasion=est(k, 'N2', 'occasion', 'on_date_of_service', [dos()], control='earlier_date',
                             literals=DAY),
                performer=fact('documenting_team', [clinician()])),
    ]
    sessions = [
        session('X1', examination=fact('E1', [src(['S5'])]),
                kind=est(k, 'X1', 'kind', 'colonoscopy', [src(['S1'], 'document_frame')], control='flex_sig'),
                reached=[est(k, 'X1', 'reached', 'cecum', [src(['S5'], words=at('advanced to the cecum'))],
                             control='cecum')]),
        session('X2', kind=unsettled(k, 'X2', 'kind', 'eus', [src(['S1'], 'document_frame')], control='egd'),
                completeness={'appraisal': k.appraised('X2', 'stations', '', ['S1'], role='completeness',
                                                       control=''), 'result': 'supported', 'reasons': []}),
    ]
    lesions = [
        lesion('L1', src(['S6'], words=at('6 mm sessile polyp')),
               multiplicity=fact('', [src(['S6']), src(['S11'])], state='contradicted', result='contradicted',
                                 reasons=['contradicted_by_pass1'],
                                 options=[{'value': 'single', 'sources': [src(['S6'])]},
                                          {'value': 'group', 'sources': [src(['S11'])]}]),
               places=[est(k, 'L1', 'places', 'sigmoid_colon', [src(['S6'], words=at('sigmoid colon'))])],
               distinct_from=[est(k, 'L1', 'distinct_from', 'L2', [src(['S6'])])]),
        lesion('L2', src(['S7'], words=at('rectum', 'No biopsies')),
               places=[est(k, 'L2', 'places', 'rectum', [src(['S7'])])]),
    ]
    snare = dict(kind_words=at('cold snare'), status_words=at('was removed'))
    events = [
        event('E1', ['S5'], at('colonoscope'), at('was advanced'),
              kind=est(k, 'E1', 'kind', 'examination', [src(['S5'], words=at('colonoscope'))]),
              status=est(k, 'E1', 'status', 'performed', [src(['S5'])], control='performed'),
              session=est(k, 'E1', 'session', 'X1', [src(['S5'])], control='X2'),
              date_relation=est(k, 'E1', 'date_relation', 'on_date_of_service', [dos()], control='earlier_date',
                                literals=DAY, **inherited),
              performer=est(k, 'E1', 'performer', 'documenting_team', [clinician()], control='other_clinician',
                            **inherited),
              entry=est(k, 'E1', 'entry', 'documenting_clinician', [findings()], control='nursing', **inherited)),
        event('E2', ['S6'], **snare,
              kind=est(k, 'E2', 'kind', 'snare', [src(['S6'], words=at('cold snare'))], control='emr'),
              status=est(k, 'E2', 'status', 'performed', [src(['S6'], words=at('was removed'))], control='performed'),
              session=est(k, 'E2', 'session', 'X1', [src(['S6'])], control='X2'),
              date_relation=est(k, 'E2', 'date_relation', 'on_date_of_service', [dos()], control='earlier_date',
                                literals=DAY, **inherited),
              performer=est(k, 'E2', 'performer', 'documenting_team', [clinician()], control='other_clinician',
                            **inherited),
              entry=est(k, 'E2', 'entry', 'documenting_clinician', [findings()], control='nursing', **inherited),
              target={'lesion': est(k, 'E2', 'target.lesion', 'L1', [src(['S6'])]),
                      'places': [est(k, 'E2', 'target.places', 'sigmoid_colon',
                                     [src(['S6'], words=at('sigmoid colon'))], control='rectum')]},
              technique={'device': est(k, 'E2', 'technique.device', 'cold_snare',
                                       [src(['S6'], words=at('cold snare'))])}),
        event('E3', ['S7'], at('biopsies', 'No biopsies'), at('No biopsies were taken'),
              kind=est(k, 'E3', 'kind', 'biopsy', [src(['S7'])], control='hot_biopsy'),
              status=est(k, 'E3', 'status', 'performed', [src(['S7'], words=at('No biopsies were taken'))],
                         state='negated', control='performed'),
              session=est(k, 'E3', 'session', 'X1', [src(['S7'])], control='X2'),
              date_relation=est(k, 'E3', 'date_relation', 'on_date_of_service', [dos()], control='earlier_date',
                                literals=DAY, **inherited),
              performer=fact('documenting_team', [clinician()], result='unknown', reasons=['doubt_unclear'],
                             **inherited),
              target={'lesion': est(k, 'E3', 'target.lesion', 'L2', [src(['S7'])]),
                      'places': [est(k, 'E3', 'target.places', 'rectum', [src(['S7'], words=at('rectum', 'No'))],
                                     control='sigmoid_colon')]},
              scope={'breadth': est(k, 'E3', 'scope.breadth', 'single_target', [src(['S7'])], control='all_of_kind')}),
        event('E4', ['S8'], at('tattoo'), at('was placed'),
              kind=unsettled(k, 'E4', 'kind', 'tattoo', [src(['S8'])], control='injection'),
              status=fact('performed', [src(['S8'])], result='unknown', reasons=['doubt_stated']),
              session=est(k, 'E4', 'session', 'X1', [src(['S8'])], control='X2')),
        event('E5', ['S11'], at('Biopsies'), at('were taken', 'Biopsies'),
              kind=est(k, 'E5', 'kind', 'biopsy', [src(['S11'])], control='hot_biopsy'),
              status=est(k, 'E5', 'status', 'performed', [src(['S11'])], control='performed'),
              session=est(k, 'E5', 'session', 'X1', [src(['S11'])], control='X2'),
              target={'places': [est(k, 'E5', 'target.places', 'transverse_colon',
                                     [src(['S11'], words=at('transverse colon'))], control='rectum')]}),
    ]
    k.pair('E2', 'target.places', 'rectum', ['S6'], 'contradicts')
    k.pair('E3', 'target.places', 'sigmoid_colon', ['S7'], 'contradicts')
    k.pair('E2', 'target.lesion', 'L2', ['S6'], 'contradicts')
    k.pair('E3', 'target.lesion', 'L1', ['S7'], 'contradicts')
    k.pair('E5', 'target.places', 'rectum', ['S11'], 'supports')  # SC-B: the omitted rectum
    k.pair('E3', 'target.places', 'transverse_colon', ['S7'], 'contradicts')
    people = [{'id': 'P1', 'name': src(['S3'], words=at('Synthetic Endoscopist')),
               'role': fact('documenting_clinician', [src(['S3'])])}]
    anatomy = [{'id': 'Y1', 'type': fact('anastomosis', [src(['S1'])]), 'organ': silent(), 'subtype': silent(),
                'joins': []}]
    encounter_ = encounter(
        est(k, '', 'date_of_service', '2026-11-09', [dos()], literals=DAY),
        [{'value': '1960-01-02', 'role': fact('birth', [src(['S9'], words=at('01/02/1960'))])},
         {'value': '2026-11-04', 'role': fact('other_occurrence', [src(['S10'], words=at('11/04/2026'))])}],
        fact('P1', [clinician()]))
    doubts = [{'about': 'performer', 'objects': ['E3'], 'units': ['S7'], 'basis': 'unclear',
               'readings': ['documenting_team', 'other_facility']},
              {'about': 'status', 'objects': ['E4'], 'units': ['S8'], 'basis': 'stated',
               'readings': ['performed', 'planned']}]
    return content(k, encounter_=encounter_, people=people, sections=sections, sessions=sessions, anatomy=anatomy,
                   lesions=lesions, events=events, doubts=doubts,
                   unlisted=[{'units': ['S8'], 'what': 'doubt', 'kind': 'tattoo', 'session': 'X1'}])


def strings(value, path='R') -> list:
    """Every str inside ``value`` (dataclasses, mappings, sequences and frozensets walked), by path."""
    found = []
    if isinstance(value, str):
        return [path]
    if hasattr(value, '__dataclass_fields__'):
        for name in value.__dataclass_fields__:
            found += strings(getattr(value, name), f'{path}.{name}')
    elif isinstance(value, typing.Mapping):
        for key, item in value.items():
            found += strings(key, f'{path}<key>') + strings(item, f'{path}[{key!r}]')
    elif isinstance(value, (tuple, list, frozenset, set)):
        for index, item in enumerate(value):
            found += strings(item, f'{path}[{index}]')
    return found


# --- the FactSet -------------------------------------------------------------------------------------------------------


class FactSetTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.row = view(colonoscopy())
        cls.R = F.factset(cls.row)

    def test_the_factset_is_typed_and_text_free(self):
        R = self.R
        self.assertIsInstance(R, FactSet)
        self.assertEqual(strings(R), [])  # no str anywhere: values, keys, reasons are members, ids, dates, spans
        values = [fact.value for table in (R.people, R.sections, R.sessions, R.anatomy, R.lesions, R.events)
                  for facts in table.values() for members in facts.values() for fact in members]
        values += [fact.value for members in R.encounter.values() for fact in members]
        options = [option for table in (R.sessions, R.lesions, R.events) for facts in table.values()
                   for members in facts.values() for fact in members for option in fact.options]
        for value in values + options:
            self.assertTrue(value is None or isinstance(value, (Id, IsoDate))
                            or (isinstance(value, enum.Enum) and type(value).__module__ == ct.__name__), value)
        # no stored words reach it: the snare's located words are not its kind fact's span, its unit is
        self.assertEqual(R.events[E2][A.KIND][0].spans, (unit_span(6),))
        self.assertEqual(R.anchors[E2].kind_words, Span(TEXT.index('cold snare'), TEXT.index('cold snare') + 10))
        self.assertEqual(R.anchors[E2].units, (unit_span(6),))

    def test_objects_and_attributes_in_pass_1s_order(self):
        R = self.R
        self.assertEqual(list(R.events), [E1, E2, E3, E4, E5])
        self.assertEqual(list(R.sections), [N0, N1, N2])
        self.assertEqual((list(R.sessions), list(R.lesions), list(R.people), list(R.anatomy)), ([X1, X2], [L1, L2],
                                                                                                [P1], [Y1]))
        # every attribute of the family: a single slot as one Fact, a list as its members (none when empty)
        for (family, attribute), domain in F.DOMAINS.items():
            table = {None: {None: R.encounter}, IdFamily.EVENT: R.events, IdFamily.SESSION: R.sessions,
                     IdFamily.SECTION: R.sections, IdFamily.LESION: R.lesions, IdFamily.ANATOMY: R.anatomy,
                     IdFamily.PERSON: R.people}[family]
            for subject, facts in table.items():
                with self.subTest(family=family, attribute=attribute, subject=subject):
                    self.assertIn(attribute, facts)
                    if not domain.many:
                        self.assertEqual(len(facts[attribute]), 1)
        self.assertEqual(R.events[E1][A.TARGET_PLACES], ())
        self.assertEqual(R.events[E1][A.RESTATEMENTS_ROLE], ())
        self.assertEqual(R.events[E1][A.PURPOSE], (F.SILENT,))
        self.assertEqual([m.value for m in R.encounter[A.OTHER_DATES_ROLE]], [ct.DateRole.BIRTH,
                                                                              ct.DateRole.OTHER_OCCURRENCE])

    def test_values_are_parsed_into_their_domains(self):
        R = self.R
        self.assertIs(F.fact(R, E2, A.KIND).value, ct.Kind.SNARE)
        self.assertEqual(F.fact(R, E2, A.SESSION).value, X1)
        self.assertEqual(F.fact(R, None, A.DATE_OF_SERVICE).value, IsoDate(datetime.date(2026, 11, 9), ct.Precision.DAY))
        self.assertIs(F.fact(R, X1, A.KIND).value, ct.SessionKind.COLONOSCOPY)
        self.assertEqual([m.value for m in F.members(R, X1, A.REACHED)], [ct.Extent.CECUM])
        self.assertIs(F.fact(R, P1, A.ROLE).value, ct.PersonRole.DOCUMENTING_CLINICIAN)
        self.assertIs(F.fact(R, N1, A.ROLE).value, ct.SectionRole.HISTORY)
        self.assertIs(F.fact(R, E3, A.STATUS).state, ct.FactState.NEGATED)
        self.assertEqual(F.fact(R, E3, A.STATUS).result, ct.Result.NEGATED)
        self.assertEqual(R.completeness, {X2: ct.Result.SUPPORTED})
        self.assertEqual(R.unlisted[0].kind, ct.Kind.TATTOO)
        self.assertEqual((R.unlisted[0].session, R.unlisted[0].units), (X1, (unit_span(8),)))

    def test_options(self):
        R = self.R
        # a contradicted fact: no value, its sides as options
        multiplicity = F.fact(R, L1, A.MULTIPLICITY)
        self.assertEqual((multiplicity.value, multiplicity.options), (None, (ct.Multiplicity.SINGLE,
                                                                             ct.Multiplicity.GROUP)))
        # a doubt's readings, the claimed value kept (3.3 row 2)
        performer = F.fact(R, E3, A.PERFORMER)
        self.assertEqual((performer.result, performer.value, performer.options),
                         (ct.Result.UNKNOWN, ct.Performer.DOCUMENTING_TEAM, (ct.Performer.OTHER_FACILITY,)))
        # the value of a control pass 2 did not reject (3.2.3 [R:HO-3])
        self.assertEqual(F.fact(R, X2, A.KIND).options, (ct.SessionKind.EGD,))
        self.assertEqual(F.fact(R, E4, A.KIND).options, (ct.Kind.INJECTION,))
        # an established fact has none, its rejected control's value included
        self.assertEqual(F.fact(R, E2, A.KIND).options, ())
        self.assertEqual(F.fact(R, X1, A.KIND).options, ())

    def test_a_section_doubt_reaches_the_facts_its_acts_inherit(self):
        events = colonoscopy()
        events['doubts'].append({'about': 'performer', 'objects': ['N2'], 'units': ['S5'], 'basis': 'unclear',
                                 'readings': ['other_clinician']})
        R = F.factset(view(events))
        self.assertIn(ct.Performer.OTHER_CLINICIAN, F.fact(R, E3, A.PERFORMER).options)  # inherited from N2

    def test_the_encounters_dates(self):
        found = F.encounter_dates(self.row)
        self.assertEqual(found.date_of_service, F.fact(self.R, None, A.DATE_OF_SERVICE))
        self.assertEqual((found.sides, found.literals), ((), (IsoDate(datetime.date(2026, 11, 9), ct.Precision.DAY),)))
        self.assertEqual([(other.value, other.role.value) for other in found.others],
                         [(IsoDate(datetime.date(1960, 1, 2), ct.Precision.DAY), ct.DateRole.BIRTH),
                          (IsoDate(datetime.date(2026, 11, 4), ct.Precision.DAY), ct.DateRole.OTHER_OCCURRENCE)])
        # checks_passed: the date of service's stored integrity and L1 checks, both ok (what engine/derive.py's
        # candidates need: every side of a contradicted date verified, triage 2d#3); either one failed is False, and a
        # check outside CheckStatus is refused
        self.assertIs(found.checks_passed, True)
        for name in ('integrity', 'literal'):
            for value, expected in (('failed', False), ('ok', True)):
                events = json.loads(json.dumps(self.row))
                events['encounter']['date_of_service']['checks'][name] = value
                with self.subTest(check=name, value=value):
                    self.assertIs(F.encounter_dates(events).checks_passed, expected)
            for broken in ('unchecked', None):
                events = json.loads(json.dumps(self.row))
                events['encounter']['date_of_service']['checks'][name] = broken
                with self.subTest(check=name, value=broken), self.assertRaises(F.FactSetError):
                    F.encounter_dates(events)
            events = json.loads(json.dumps(self.row))
            events['encounter']['date_of_service']['checks'].pop(name)
            with self.subTest(check=name, value='absent'), self.assertRaises(F.FactSetError):
                F.encounter_dates(events)

    def test_pair_controls(self):
        self.assertEqual(dict(self.R.pair_controls), {
            (E2, A.TARGET_PLACES, ct.Landmark.RECTUM): True, (E3, A.TARGET_PLACES, ct.Landmark.SIGMOID_COLON): True,
            (E2, A.TARGET_LESION, L2): True, (E3, A.TARGET_LESION, L1): True,
            (E5, A.TARGET_PLACES, ct.Landmark.RECTUM): False,
            (E3, A.TARGET_PLACES, ct.Landmark.TRANSVERSE_COLON): True})

    def test_a_pair_control_asked_twice_is_rejected_only_when_every_asking_was(self):
        events = colonoscopy()
        ledger = Ledger()
        ledger.claims = events['claims']
        ledger.pair('E2', 'target.places', 'rectum', ['S6'], 'unclear')
        R = F.factset(view(events))
        self.assertIs(R.pair_controls[(E2, A.TARGET_PLACES, ct.Landmark.RECTUM)], False)

    def test_the_builder_reads_the_text_free_view_only(self):
        # DECISIONS D188: engine/facts.py builds only from store.textfree_v2's view. The row itself and its events as
        # stored (whose words records hold the text) are refused by every entry point; the view reads as before.
        row = stored(colonoscopy())
        self.assertEqual(F.factset(store.textfree_v2(row)), self.R)
        empty = stored(content(Ledger()))  # no source and no anchor at all: the row is refused for what it is
        self.assertEqual(F.factset(store.textfree_v2(empty)).events, {})
        for given in (row, row.events, json.loads(json.dumps(row.events)), empty):
            for read in (F.factset, F.encounter_dates, lambda value: F.effective(value, '2026-11-09')):
                with self.subTest(given=type(given).__name__, read=read), self.assertRaises(F.FactSetError):
                    read(given)

    def test_accessors(self):
        R = self.R
        self.assertIs(F.fact(R, Id(IdFamily.EVENT, 99), A.STATUS), F.SILENT)  # a dangling id: unknown, never established
        self.assertEqual(F.members(R, Id(IdFamily.SESSION, 99), A.STATIONS), ())
        with self.assertRaises(ValueError):
            F.fact(R, E2, A.TARGET_PLACES)
        with self.assertRaises(ValueError):
            F.members(R, E2, A.KIND)


# --- what each fact cites: DECISIONS D188 (triage 2d#2, 2d:D1, 2d:R1, 2d:R2) ---------------------------------------------


def located(words: str, after: str = '') -> Span:
    """The offsets of ``words`` in TEXT where they first occur at or after ``after`` (what ``at`` stores)."""
    found = at(words, after)
    return Span(found['start'], found['end'])


class CitedTests(SimpleTestCase):
    """Each fact carries, text-free, one Cited per stored source - its link, its units' span and its located words'
    offsets -, the section it was inherited from, and the evidence units of a contradicts or qualified verdict."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.R = F.factset(view(colonoscopy()))

    def test_each_source_is_cited_with_its_link_its_units_and_its_located_words(self):
        R = self.R
        self.assertEqual(F.members(R, E2, A.TARGET_PLACES)[0].cited,
                         (Cited(ct.Link.STATEMENT, unit_span(6), located('sigmoid colon')),))
        # E3's place: 'rectum' inside 'No biopsies were taken from the rectum.' (the arbiter's (345, 351) in (313, 352))
        e3 = F.members(R, E3, A.TARGET_PLACES)[0]
        self.assertEqual(e3.cited, (Cited(ct.Link.STATEMENT, unit_span(7), located('rectum', 'No biopsies')),))
        self.assertEqual((e3.cited[0].at, e3.cited[0].units), (Span(345, 351), Span(313, 352)))
        self.assertEqual(e3.spans, (unit_span(7),))  # spans stay the whole units, for wording
        # the links as stored; a source that cites its whole units (words '') has no located words
        self.assertEqual(F.fact(R, E1, A.DATE_RELATION).cited,
                         (Cited(ct.Link.DOCUMENT_FRAME, unit_span(2), located('11/09/2026')),))
        self.assertEqual(F.fact(R, E1, A.ENTRY).cited, (Cited(ct.Link.SECTION, unit_span(5), located('Findings:')),))
        self.assertEqual(F.fact(R, None, A.DOCUMENTING_CLINICIAN).cited,
                         (Cited(ct.Link.DOCUMENT_FRAME, unit_span(3), None),))
        self.assertEqual(F.fact(R, X1, A.KIND).cited, (Cited(ct.Link.DOCUMENT_FRAME, unit_span(1), None),))
        # one per source, in pass 1's order; the spans the distinct units; a silent slot cites nothing
        multiplicity = F.fact(R, L1, A.MULTIPLICITY)
        self.assertEqual(multiplicity.cited, (Cited(ct.Link.STATEMENT, unit_span(6), None),
                                              Cited(ct.Link.STATEMENT, unit_span(11), None)))
        self.assertEqual(multiplicity.spans, (unit_span(6), unit_span(11)))
        self.assertEqual((F.fact(R, E1, A.PURPOSE).cited, F.SILENT.cited), ((), ()))

    def test_c_10_can_tell_the_statement_linked_words_from_their_unit(self):
        # the arbiter's input (triage 2d#2): the kept span 'cold snare' lies inside E2's target fact's unit span but
        # outside its statement-linked target words ('sigmoid colon'), so C-10 (4.6 condition 4) can read a partial
        # cover as statement_scope; read off Fact.spans alone it would be a full cover
        kept = located('cold snare')
        target = F.members(self.R, E2, A.TARGET_PLACES)[0]
        words = [item.at if item.at is not None else item.units for item in target.cited
                 if item.link is ct.Link.STATEMENT]
        self.assertEqual(words, [located('sigmoid colon')])

        def within(outer: Span) -> bool:
            return outer.start <= kept.start and kept.end <= outer.end

        self.assertEqual((any(within(span) for span in target.spans), any(within(span) for span in words)),
                         (True, False))
        self.assertEqual(self.R.anchors[E2].kind_words, kept)

    def test_inherited_from_names_the_section_an_acts_fact_came_from(self):
        R = self.R
        for event in (E1, E2):
            for attribute in (A.DATE_RELATION, A.PERFORMER, A.ENTRY):
                with self.subTest(event=event, attribute=attribute):
                    self.assertEqual(F.fact(R, event, attribute).inherited_from, N2)
        self.assertEqual(F.fact(R, E3, A.PERFORMER).inherited_from, N2)  # doubted, and still inherited
        self.assertIsNone(F.fact(R, E2, A.KIND).inherited_from)  # the act's own slot
        self.assertIsNone(F.fact(R, E5, A.PERFORMER).inherited_from)  # silent: D names no performer
        self.assertIsNone(F.fact(R, N2, A.OCCASION).inherited_from)

    def test_counter_holds_the_evidence_of_a_contradicts_or_qualified_verdict(self):
        events = colonoscopy()
        k = Ledger()
        k.claims = events['claims']
        e5 = events['events'][4]
        cited = [src(['S11'])]
        e5['kind'] = unsettled(k, 'E5', 'kind', 'biopsy', cited, verdict='contradicts',
                               reasons=('appraisal_contradicts',), evidence=['S7', 'S12', 'S7', 'S2'])
        e5['status'] = unsettled(k, 'E5', 'status', 'performed', cited, verdict='qualified', qualifiers=['hedged'],
                                 reasons=('appraisal_qualified:hedged',), evidence=['S8'])
        e5['session'] = unsettled(k, 'E5', 'session', 'X1', cited, verdict='supports', qualifiers=['conditional'],
                                  reasons=('appraisal_qualified:conditional',), evidence=['S10'])
        e5['purpose'] = unsettled(k, 'E5', 'purpose', 'diagnostic', cited, verdict='unclear', evidence=['S9'])
        R = F.factset(view(events))
        self.assertEqual(F.fact(R, E5, A.KIND).counter, (unit_span(7), unit_span(2)))  # S12 locates nothing
        self.assertEqual(F.fact(R, E5, A.STATUS).counter, (unit_span(8),))
        self.assertEqual(F.fact(R, E5, A.SESSION).counter, (unit_span(10),))  # supports naming a qualifier (D186)
        self.assertEqual(F.fact(R, E5, A.PURPOSE).counter, ())  # unclear: no counter
        self.assertEqual(F.fact(R, E2, A.KIND).counter, ())  # supported
        self.assertEqual(F.fact(R, E3, A.PERFORMER).counter, ())  # never appraised


# --- the predicates (4.2) ------------------------------------------------------------------------------------------------


def make(result, value, *, state=ct.FactState.SUPPORTED, options=()) -> Fact:
    return Fact(result=result, value=value, state=state, options=tuple(options), reasons=(), spans=())


class PredicateTests(SimpleTestCase):
    def test_holds_denied_established(self):
        S = ct.Status.PERFORMED
        supported, negated = make(ct.Result.SUPPORTED, S), make(ct.Result.NEGATED, S, state=ct.FactState.NEGATED)
        self.assertEqual((F.holds(supported, S), F.denied(supported, S), F.established(supported)), (True, False, True))
        self.assertEqual((F.holds(negated, S), F.denied(negated, S), F.established(negated)), (False, True, True))
        for result in (ct.Result.UNRESOLVED, ct.Result.UNKNOWN, ct.Result.CONTRADICTED):
            found = make(result, S)
            with self.subTest(result=result):
                self.assertEqual((F.holds(found, S), F.denied(found, S), F.established(found)), (False, False, False))

    def test_possibly_at_every_result(self):
        P, R_ = ct.Performer, ct.Result
        self.assertTrue(F.possibly(make(R_.SUPPORTED, P.DOCUMENTING_TEAM), P.DOCUMENTING_TEAM))
        self.assertFalse(F.possibly(make(R_.SUPPORTED, P.DOCUMENTING_TEAM), P.OTHER_CLINICIAN))
        self.assertFalse(F.possibly(make(R_.NEGATED, P.OTHER_CLINICIAN, state=ct.FactState.NEGATED),
                                    P.OTHER_CLINICIAN))
        for result in (R_.UNRESOLVED, R_.UNKNOWN, R_.CONTRADICTED):
            found = make(result, P.DOCUMENTING_TEAM, options=(P.OTHER_FACILITY,))
            with self.subTest(result=result):
                self.assertTrue(F.possibly(found, P.DOCUMENTING_TEAM))  # the claimed value
                self.assertTrue(F.possibly(found, P.OTHER_FACILITY))  # an option: a reading, a side, a control
                self.assertFalse(F.possibly(found, P.OTHER_CLINICIAN))
        self.assertTrue(all(F.possibly(F.SILENT, value) for value in P))  # silent: every value

    def test_a_status_not_established_leaves_every_status_possible(self):
        # HO-1: "It is unclear whether the polyp was removed with the cold snare." - the act is a positive candidate and
        # a possible statement at once; HO-3: a denial misfiled as performed and caught by pass 2 (unresolved)
        for result in (ct.Result.UNKNOWN, ct.Result.UNRESOLVED, ct.Result.CONTRADICTED):
            for claimed in ct.Status:
                found = make(result, claimed)
                with self.subTest(result=result, claimed=claimed):
                    self.assertTrue(all(F.possibly(found, status) for status in ct.Status))
        # an established status leaves exactly itself (none when denied)
        self.assertEqual([F.possibly(make(ct.Result.SUPPORTED, ct.Status.PLANNED), s) for s in ct.Status],
                         [False, False, True])
        self.assertFalse(any(F.possibly(make(ct.Result.NEGATED, ct.Status.PERFORMED, state=ct.FactState.NEGATED), s)
                             for s in ct.Status))
        # and on the stored row: E4's doubted tattoo is possibly performed and possibly not done
        R = F.factset(view(colonoscopy()))
        self.assertTrue(F.possibly(F.fact(R, E4, A.STATUS), ct.Status.PERFORMED))
        self.assertTrue(F.possibly(F.fact(R, E4, A.STATUS), ct.Status.ATTEMPTED_NOT_COMPLETED))
        self.assertFalse(F.possibly(F.fact(R, E3, A.STATUS), ct.Status.PERFORMED))  # an established denial

    def test_a_kind_not_established_on_a_statement_is_any_kind_of_its_sessions_family(self):
        R = F.factset(view(colonoscopy()))
        colonoscopy_kinds = F.family_kinds(ct.SessionKind.COLONOSCOPY)
        self.assertIn(ct.Kind.SNARE, colonoscopy_kinds)
        # E4: kind tattoo, unresolved; its session X1 is an established colonoscopy
        self.assertEqual(F.possible_kinds(R, E4, of_family=True), colonoscopy_kinds | {ct.Kind.TATTOO,
                                                                                         ct.Kind.INJECTION})
        # as a candidate (4.4) only its claimed value, readings and control sibling
        self.assertEqual(F.possible_kinds(R, E4, of_family=False), {ct.Kind.TATTOO, ct.Kind.INJECTION})
        self.assertFalse(F.possibly(F.fact(R, E4, A.KIND), ct.Kind.SNARE))
        self.assertTrue(F.possibly_of_family(R, E4, ct.Kind.SNARE))
        self.assertFalse(F.possibly_of_family(R, E4, ct.Kind.SPHINCTEROTOMY))  # an ERCP kind, not the family's
        # an established kind never widens
        self.assertEqual(F.possible_kinds(R, E3, of_family=True), {ct.Kind.BIOPSY})

    def test_with_its_session_or_that_sessions_kind_not_established_every_kind(self):
        events = colonoscopy()
        e4 = events['events'][3]
        e4['session'] = fact('X1', [src(['S8'])])  # its session not established
        R = F.factset(view(events))
        self.assertEqual(F.possible_kinds(R, E4, of_family=True), frozenset(ct.Kind))
        events = colonoscopy()
        k = Ledger()
        k.claims = events['claims']
        # its session X2 is established, and X2's kind is not (pass 2 left it unclear, its control egd not rejected)
        events['events'][3]['session'] = est(k, 'E4', 'session', 'X2', [src(['S8'])], control='X1')
        R = F.factset(view(events))
        self.assertIsNone(F.session_family(R, E4))
        self.assertEqual(F.possible_kinds(R, E4, of_family=True), frozenset(ct.Kind))

    def test_the_kind_arm_reads_the_one_family_table_k2_reads(self):
        # DECISIONS D191: requirements_table.FAMILY_KINDS is THE answer to "the kinds of a session family"; facts.py
        # computes none of its own. A family the table has no row for has no kinds (D191's union is empty for it).
        self.assertIs(F.FAMILY_KINDS, RT.FAMILY_KINDS)
        for family in ct.SessionKind:
            with self.subTest(family=family):
                self.assertEqual(F.family_kinds(family), RT.FAMILY_KINDS.get(family, frozenset()))
        # the kinds 2d's own table had left out (triage 2d#1) are its families' now
        for family, kind in ((ct.SessionKind.ERCP, ct.Kind.CANNULATION), (ct.SessionKind.COLONOSCOPY, ct.Kind.CLIP),
                             (ct.SessionKind.COLONOSCOPY, ct.Kind.EXAMINATION), (ct.SessionKind.EGD, ct.Kind.ESD),
                             (ct.SessionKind.ANORECTAL, ct.Kind.BALLOON_EXPULSION),
                             (ct.SessionKind.COLONOSCOPY, ct.Kind.REMOVAL)):
            with self.subTest(family=family, kind=kind):
                self.assertIn(kind, F.family_kinds(family))

    def test_p_unknown_kind_over_every_family_and_kind_of_the_table(self):
        # 9.4 P-UNKNOWN-KIND [R:HO-5] (triage 2d#1): a statement whose kind is not established pairs with at least
        # every act of its session's family that the same statement with an established kind would pair with. Per
        # family F of the table, a denial E1 in an established F session, its kind unresolved (claimed outside F, no
        # reading, no control), is possibly-of-family every kind of F - each one an established-kind twin (E2) can
        # be - read off requirements_table.FAMILY_KINDS, never off facts' own copy, so a narrowed copy is red.
        checked = 0
        for family, kinds in RT.FAMILY_KINDS.items():
            if not kinds:
                continue
            claimed = next(kind for kind in ct.Kind if kind not in kinds)
            for kind in sorted(kinds, key=lambda member: member.value):
                k = Ledger()
                denial = dict(status=est(k, 'E1', 'status', 'performed', [src(['S7'])], state='negated'),
                              session=est(k, 'E1', 'session', 'X1', [src(['S7'])]))
                events = content(k, sessions=[session('X1', kind=est(k, 'X1', 'kind', family.value,
                                                                       [src(['S1'], 'document_frame')]))],
                                 events=[event('E1', ['S7'], kind=fact(claimed.value, [src(['S7'])]), **denial),
                                         event('E2', ['S7'], kind=est(k, 'E2', 'kind', kind.value, [src(['S7'])]),
                                               status=est(k, 'E2', 'status', 'performed', [src(['S7'])],
                                                          state='negated'),
                                               session=est(k, 'E2', 'session', 'X1', [src(['S7'])]))])
                R = F.factset(view(events))
                with self.subTest(family=family, kind=kind):
                    self.assertFalse(F.possibly(F.fact(R, E1, A.KIND), kind))  # only the family arm reaches it
                    self.assertTrue(F.possibly_of_family(R, E2, kind))  # the established-kind twin
                    self.assertTrue(F.possibly_of_family(R, E1, kind))  # P-UNKNOWN-KIND
                    self.assertEqual(F.possible_kinds(R, E2, of_family=True), {kind})  # established never widens
                checked += 1
        self.assertEqual(checked, sum(len(kinds) for kinds in RT.FAMILY_KINDS.values()))


class ApartTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.R = F.factset(view(colonoscopy()))

    def test_apart_by_place_needs_disjoint_established_places_and_rejected_pair_controls_both_ways(self):
        self.assertTrue(F.apart_by_place(self.R, E2, E3))  # sigmoid colon against rectum, both controls rejected
        self.assertTrue(F.apart_by_place(self.R, E3, E2))

    def test_sc_bs_short_list_is_never_apart(self):
        # biopsies "from the transverse colon and the rectum" filed with the transverse colon only, beside "No biopsies
        # were taken from the rectum.": the pair control "This act was done in the rectum." was supported
        self.assertFalse(F.apart_by_place(self.R, E5, E3))
        self.assertFalse(F.apart_by_place(self.R, E3, E5))

    def test_a_missing_pair_control_is_not_rejected(self):
        R = self.R
        trimmed = FactSet(encounter=R.encounter, people=R.people, sections=R.sections, sessions=R.sessions,
                          anatomy=R.anatomy, lesions=R.lesions, events=R.events, anchors=R.anchors,
                          unlisted=R.unlisted, completeness=R.completeness,
                          pair_controls={key: value for key, value in R.pair_controls.items()
                                         if key != (E3, A.TARGET_PLACES, ct.Landmark.SIGMOID_COLON)})
        self.assertFalse(F.apart_by_place(trimmed, E2, E3))

    def test_an_unestablished_or_absent_place_never_sets_apart(self):
        R = self.R
        self.assertFalse(F.apart_by_place(R, E1, E3))  # E1 states no place: unknown, never a difference
        events = colonoscopy()
        events['events'][2]['target']['places'] = [fact('rectum', [src(['S7'])])]  # E3's place not established
        self.assertFalse(F.apart_by_place(F.factset(view(events)), E2, E3))

    def test_contained_places_are_never_disjoint(self):
        events = colonoscopy()
        k = Ledger()
        k.claims = events['claims']
        events['events'][2]['target']['places'] = [est(k, 'E3', 'target.places', 'colon', [src(['S7'])])]
        k.pair('E3', 'target.places', 'sigmoid_colon', ['S7'], 'contradicts')
        k.pair('E2', 'target.places', 'colon', ['S6'], 'contradicts')
        self.assertFalse(F.apart_by_place(F.factset(view(events)), E2, E3))

    def test_apart_by_lesion(self):
        self.assertTrue(F.apart_by_lesion(self.R, E2, E3))  # L1 and L2, distinct_from established, controls rejected
        self.assertTrue(F.apart_by_lesion(self.R, E3, E2))
        self.assertFalse(F.apart_by_lesion(self.R, E2, E2))
        self.assertFalse(F.apart_by_lesion(self.R, E2, E5))  # E5 names no lesion
        events = colonoscopy()
        events['lesions'][0]['distinct_from'] = []  # no established difference between the lesions
        self.assertFalse(F.apart_by_lesion(F.factset(view(events)), E2, E3))
        R = self.R
        for missing in ((E2, A.TARGET_LESION, L2), (E3, A.TARGET_LESION, L1)):
            trimmed = FactSet(encounter=R.encounter, people=R.people, sections=R.sections, sessions=R.sessions,
                              anatomy=R.anatomy, lesions=R.lesions, events=R.events, anchors=R.anchors,
                              unlisted=R.unlisted, completeness=R.completeness,
                              pair_controls={key: value for key, value in R.pair_controls.items() if key != missing})
            with self.subTest(missing=missing):
                self.assertFalse(F.apart_by_lesion(trimmed, E2, E3))


# --- effective(): L1 re-judged (4.2, 6.5) ---------------------------------------------------------------------------------


class EffectiveTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.row = view(colonoscopy())

    def relation(self, R, subject=E2, attribute=A.DATE_RELATION):
        found = F.fact(R, subject, attribute)
        return found.result, found.reasons

    def test_the_document_date_changes_nothing(self):
        self.assertEqual(F.effective(self.row, '2026-11-09'), F.factset(self.row))
        self.assertEqual(F.effective(self.row, datetime.date(2026, 11, 9)), F.factset(self.row))

    def test_a_members_other_date_demotes_every_day_literal_that_misses_it(self):
        R = F.effective(self.row, '2026-11-08')
        for event in (E1, E2, E3):
            with self.subTest(event=event):
                self.assertEqual(self.relation(R, event), (ct.Result.UNRESOLVED, (ct.Reason.LITERAL_MISMATCH,)))
        # the section's occasion too (N2), while the history's year literal 2023 still ends before the date (N1)
        self.assertEqual(self.relation(R, N2, A.OCCASION), (ct.Result.UNRESOLVED, (ct.Reason.LITERAL_MISMATCH,)))
        self.assertEqual(self.relation(R, N1, A.OCCASION), (ct.Result.SUPPORTED, ()))
        # an act whose relation is not established is never touched (E4 states none; E5's is silent)
        self.assertEqual(F.fact(R, E5, A.DATE_RELATION), F.SILENT)
        # every other fact is read as stored
        self.assertEqual(F.fact(R, E2, A.KIND), F.fact(F.factset(self.row), E2, A.KIND))

    def test_no_effective_date_leaves_a_day_literal_unchecked(self):
        R = F.effective(self.row, None)
        self.assertEqual(self.relation(R), (ct.Result.UNRESOLVED, (ct.Reason.LITERAL_UNCHECKED,)))

    def test_earlier_and_later_dates_at_each_precision(self):
        rejudged = F.rejudged
        day = lambda value: F.iso_value(value)  # noqa: E731
        service = datetime.date(2026, 11, 9)
        ON, EARLIER, LATER = (ct.DateRelation.ON_DATE_OF_SERVICE, ct.DateRelation.EARLIER_DATE,
                              ct.DateRelation.LATER_DATE)
        cases = [
            (ON, '2026-11-09', None), (ON, '2026-11-08', ct.Reason.LITERAL_MISMATCH),
            (ON, '2026-11', None), (ON, '2026-10', ct.Reason.LITERAL_MISMATCH),
            (ON, '2026', None), (ON, '2023', ct.Reason.LITERAL_MISMATCH),
            (EARLIER, '2023', None), (EARLIER, '2026', ct.Reason.LITERAL_MISMATCH),
            (EARLIER, '2026-10', None), (EARLIER, '2026-11', ct.Reason.LITERAL_MISMATCH),
            (EARLIER, '2026-11-08', None), (EARLIER, '2026-11-09', ct.Reason.LITERAL_MISMATCH),
            (LATER, '2027', None), (LATER, '2026-12', None), (LATER, '2026-11-10', None),
            (LATER, '2026-11', ct.Reason.LITERAL_MISMATCH), (LATER, '2026-11-09', ct.Reason.LITERAL_MISMATCH),
        ]
        for value, literal, expected in cases:
            with self.subTest(value=value, literal=literal):
                self.assertEqual(rejudged(value, (day(literal),), service), expected)
        # with no effective date: a day literal is unchecked, a coarse one is not (3.1 L1)
        self.assertEqual(rejudged(EARLIER, (day('2023'),), None), None)
        self.assertEqual(rejudged(EARLIER, (day('2023-03-14'),), None), ct.Reason.LITERAL_UNCHECKED)
        # an unreadable literal never meets the date; no literal, nothing to judge; a silent value is not judged
        self.assertEqual(rejudged(ON, (None,), service), ct.Reason.LITERAL_MISMATCH)
        self.assertEqual(rejudged(ON, (), service), None)
        self.assertEqual(rejudged(None, (day('2023'),), service), None)

    def test_it_only_demotes(self):
        # a timing fact L1 failed at claim time stays unresolved whatever date now meets its literal
        events = colonoscopy()
        e2 = events['events'][1]
        e2['date_relation'] = fact('on_date_of_service', [src(['S2'], 'document_frame', at('11/09/2026'))],
                                   reasons=['literal_mismatch'], literals=[{'value': '2026-11-08', 'precision': 'day'}],
                                   inherited_from='N2')
        row = view(events)
        for date in ('2026-11-08', '2026-11-09', None):
            with self.subTest(date=date):
                self.assertEqual(self.relation(F.effective(row, date)), (ct.Result.UNRESOLVED,
                                                                          (ct.Reason.LITERAL_MISMATCH,)))

    def test_an_inherited_relation_with_no_literals_of_its_own_is_judged_on_its_sections(self):
        events = colonoscopy()
        k = Ledger()
        k.claims = events['claims']
        dos = src(['S2'], 'document_frame', at('11/09/2026'))
        events['events'][1]['date_relation'] = est(k, 'E2', 'date_relation', 'on_date_of_service', [dos],
                                                   control='earlier_date', inherited_from='N2')  # no literals stored
        events['events'][4]['date_relation'] = est(k, 'E5', 'date_relation', 'on_date_of_service', [dos],
                                                   control='earlier_date')  # its own, with none: nothing to judge
        row = view(events)
        R = F.effective(row, '2026-11-08')
        self.assertEqual(self.relation(R), (ct.Result.UNRESOLVED, (ct.Reason.LITERAL_MISMATCH,)))
        self.assertEqual(self.relation(R, E5), (ct.Result.SUPPORTED, ()))
        self.assertEqual(self.relation(F.effective(row, '2026-11-09')), (ct.Result.SUPPORTED, ()))

    def test_the_re_judge_is_the_claim_time_rule_over_the_grid(self):
        # DECISIONS D193: L1's claim-time rule (contract/consistency.rejudge, imported test-only) and this re-judge are
        # two implementations, because engine/ cannot import date_literals; they are pinned equal over the grid
        # relation x precision x literal x service date (none included), one literal at a time and two together
        from studio.interpretation.contract import consistency  # test-only

        services = (datetime.date(2026, 11, 9), datetime.date(2026, 1, 1), datetime.date(2026, 12, 31),
                    datetime.date(2024, 2, 29), None)
        values = ('2025', '2026', '2027', '2024', '2025-12', '2026-01', '2026-10', '2026-11', '2026-12', '2027-01',
                  '2024-02', '2025-12-31', '2026-01-01', '2026-11-08', '2026-11-09', '2026-11-10', '2026-12-31',
                  '2027-01-01', '2024-02-29')
        literals = [F.iso_value(value) for value in values]
        grid = [(one,) for one in literals] + [(one, two) for one in literals[::3] for two in literals[1::4]]
        self.assertEqual({literal.precision for literal in literals}, set(ct.Precision))
        compared = 0
        for relation in ct.DateRelation:
            for service in services:
                for found in grid:
                    stored_literals = tuple(ct.StoredLiteral(literal.iso, literal.precision) for literal in found)
                    mine = F.rejudged(relation, found, service)
                    theirs = set(consistency.rejudge(relation, stored_literals, service))
                    with self.subTest(relation=relation, service=service, literals=[item.iso for item in found]):
                        self.assertEqual(theirs, set() if mine is None else {mine})
                    compared += 1
        self.assertEqual(compared, len(ct.DateRelation) * len(services) * len(grid))

    def test_the_effective_date_is_a_date(self):
        for bad in ('11/09/2026', '2026-11', '2026-02-30', 20261109, datetime.datetime(2026, 11, 9, 8)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                F.effective(self.row, bad)


# --- refusals ----------------------------------------------------------------------------------------------------------


class RefusalTests(SimpleTestCase):
    def test_a_row_it_cannot_read_whole_is_refused(self):
        def broken(change):
            events = json.loads(json.dumps(view(colonoscopy())))
            change(events)
            return events

        cases = {
            'a missing slot': lambda e: e['events'][0].pop('purpose'),
            'an attribute its object does not have': lambda e: e['events'][0].update(owner=silent()),
            'a value outside its domain': lambda e: e['events'][1]['kind']['claim'].update(value='polypectomy'),
            'a result it does not know': lambda e: e['events'][1]['kind'].update(result='probable'),
            'a list where one fact stands': lambda e: e['events'][1].update(kind=[silent()]),
            'an id of another family': lambda e: e['events'][1].update(id='X9'),
            'a repeated id': lambda e: e['events'][1].update(id='E1'),
            'a control naming no claim': lambda e: e['sessions'][1]['kind']['appraisal']['control'].update(claim='K999'),
            'no units': lambda e: e.pop('units'),
            # the view's own shapes (DECISIONS D188)
            'a source with no located offsets': lambda e: e['events'][1]['kind']['sources'][0].pop('at'),
            'a source as stored, its words in place of at': lambda e: e['events'][1]['kind']['sources'][0].update(
                words=e['events'][1]['kind']['sources'][0].pop('at')),
            'a located record holding more than its offsets': lambda e: e['events'][1]['anchor']['kind_words'].update(
                text='cold snare'),
            'a source at holding more than its offsets': lambda e: e['events'][1]['kind']['sources'][0]['at'].update(
                text='cold snare'),
            'a link outside its enumeration': lambda e: e['events'][1]['kind']['sources'][0].update(link='nearby'),
            'an inheritance from no section': lambda e: e['events'][0]['date_relation']['claim'].update(
                inherited_from='X1'),
            'a verdict outside its enumeration': lambda e: e['events'][1]['kind']['appraisal'].update(
                verdict='probably'),
            'a qualifier outside its enumeration': lambda e: e['events'][1]['kind']['appraisal'].update(
                qualifiers=['somewhat']),
        }
        for name, change in cases.items():
            with self.subTest(name), self.assertRaises(F.FactSetError):
                F.factset(broken(change))

    def test_a_refused_row_has_no_events(self):
        # the refusal sentence is contract/extract_read's (store.py keeps no copy: triage 1d#6)
        refusal = type('Refusal', (), {'stage': 'bounds', 'reason': extract_read.REFUSED + 'too many events.'})()
        fields = store.refused_row_v2(refusal, encounter_id=ENCOUNTER, revision_id=REVISION, provider_run_id=RUN,
                                      text_sha256=TEXT_SHA256, request_sha256='2' * 64, response_sha256='3' * 64)
        row = store.load_v2(fields, text_sha256=TEXT_SHA256, response_sha256='3' * 64, appraisal_response_sha256=None)
        with self.assertRaises(store.StoreError):
            store.textfree_v2(row)  # a refused row has no events, so no view
        with self.assertRaises(F.FactSetError):
            F.factset(row)  # and the row itself is never read (D188)


# --- the boundary (5.7 measures 4 and 5) ----------------------------------------------------------------------------------

PUBLIC_FACTS = ('factset', 'effective', 'encounter_dates', 'fact', 'members', 'holds', 'denied', 'established',
                'silent', 'possibly', 'family_kinds', 'session_family', 'possibly_of_family', 'possible_kinds',
                'apart_by_lesion', 'apart_by_place', 'iso_value', 'as_date', 'compare', 'rejudged')


class BoundaryTests(SimpleTestCase):
    def test_no_accessor_returns_a_string(self):
        for module, names in ((F, PUBLIC_FACTS), (RD, [name for name, value in vars(RD).items()
                                                        if inspect.isfunction(value) and not name.startswith('_')
                                                        and value.__module__ == RD.__name__])):
            for name in names:
                function = getattr(module, name)
                with self.subTest(module=module.__name__, name=name):
                    hint = typing.get_type_hints(function).get('return')
                    self.assertNotIn(str, _leaves(hint), hint)
        # and at run time, over the stored row: every result of every accessor on every object and attribute
        R = F.factset(view(colonoscopy()))
        reading = RD.Reading(R)
        found = []
        for (family, attribute), domain in F.DOMAINS.items():
            subjects = [None] if family is None else [subject for subject in
                                                      {IdFamily.EVENT: R.events, IdFamily.SESSION: R.sessions,
                                                       IdFamily.SECTION: R.sections, IdFamily.LESION: R.lesions,
                                                       IdFamily.ANATOMY: R.anatomy, IdFamily.PERSON: R.people}[family]]
            for subject in subjects:
                found.append(F.members(R, subject, attribute) if domain.many else F.fact(R, subject, attribute))
                found.append(RD.usable(reading, subject, attribute))
                if not domain.many:
                    found.append(RD.value(reading, subject, attribute))
        for event in R.events:
            found += [RD.done(reading, event), RD.own_spans(reading, event), RD.all_spans(reading, event),
                      RD.anchors(reading, event), RD.event_label(reading, event), F.possible_kinds(R, event,
                                                                                                   of_family=True),
                      RD.verified_other_time(reading, event), RD.verified_other_performer(reading, event)]
        found += [F.encounter_dates(view(colonoscopy())), F.effective(view(colonoscopy()), '2026-11-08')]
        self.assertEqual(strings(found), [])

    def test_mypy_strict_passes_on_types_facts_and_reading(self):
        def mypy(*arguments):
            return subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--cache-dir', os.devnull, *arguments],
                                  capture_output=True, text=True, timeout=600, cwd=APP)

        result = mypy('studio/interpretation/engine/types.py', 'studio/interpretation/engine/facts.py',
                      'studio/interpretation/engine/reading.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 3 source files', result.stdout)
        # the positive control: a string operation on a value an accessor returns is a type error
        probe = mypy('-c', 'from studio.interpretation.engine import facts\n'
                           'from studio.interpretation.engine.types import FactSet, Id\n'
                           'from studio.interpretation.contract.types import Attribute\n'
                           'def probe(R: FactSet, e: Id) -> bool:\n'
                           '    value = facts.fact(R, e, Attribute.KIND).value\n'
                           '    return value.startswith("no") if value is not None else False\n')
        self.assertEqual(probe.returncode, 1, probe.stdout + probe.stderr)
        self.assertIn('has no attribute "startswith"', probe.stdout)

    def test_the_new_modules_keep_measure_4(self):
        for name in ('facts', 'reading', 'derive'):
            with self.subTest(module=name):
                self.assertEqual(measure_4((ENGINE / f'{name}.py').read_text(encoding='utf-8'), engine=True), [])

    def test_they_import_no_retired_module_no_text_module_and_not_store(self):
        code = ('import sys\n'
                'import studio.interpretation.engine.facts, studio.interpretation.engine.reading\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=60, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().split(','), [
            'studio', 'studio.interpretation', 'studio.interpretation.contract',
            'studio.interpretation.contract.types', 'studio.interpretation.engine',
            'studio.interpretation.engine.anatomy', 'studio.interpretation.engine.catalogue',
            'studio.interpretation.engine.facts', 'studio.interpretation.engine.reading',
            'studio.interpretation.engine.requirements_table', 'studio.interpretation.engine.types'])


def _leaves(hint) -> set:
    """Every type a hint is built from (unions, generics and aliases unfolded)."""
    args = typing.get_args(hint)
    if not args:
        return {hint}
    return set().union(*(_leaves(arg) for arg in args)) | {typing.get_origin(hint)}
