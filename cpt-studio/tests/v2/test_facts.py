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
- DECISIONS D220 (repair r2d; 3d PMONO, 4b F5) for places: apart_by_place reads EVERY pair control between the two
  objects, whatever place it asks about - every control asked of either object, as the FactSet cannot tell which
  object a control on a list was generated for - and "apart" needs every such control rejected and every current
  member of the other covered by a rejected control. 4b's F5 case and 3d's single-target SC-B case stay held when the
  member is deleted (9.4's weakening, the controls left as they were), through coverage and pairing too; P-MONO of both
  predicates over generated scenes whose controls come from the full lists, its one release named (a deleted member
  that overlaps the other's place without being compatible with it, its control rejected: repair r2d's question Q2,
  ruled by D245); the place reading is never more apart than 4.2's before D220, and differs only through an unrejected
  control; on the pairing and coverage fixtures as they were at the base - every call their tests made there, frozen as
  data (repair r2d-2; refute-r2d-r1 RF2), so that a test a later step adds to either module never reaches it - the
  predicates answer as before; and on a settled FactSet whose controls come from the full lists the place arm holds a
  pair 4.2's reading set apart when a control another pair made, asked of one of the two objects, was not rejected:
  repair r2d's question Q1, ruled by D236 (as built, named in 6a's P-MONO) (refute-r2d-r1 RF1, RF3);
- DECISIONS D235 (this repair; refute-r2d-r2 RL1): apart_by_lesion reads only the lesion pair controls between the two
  objects as their target lesions name them, (a, lb) and (b, la) - 4.2's lesion reading, on every generated pair - so
  a control made for another pair never holds the pair: RL1's scene (its lesion_arm probe) sets the biopsy E4 apart
  from the snare E3 (coverage T) and 45380 carries no bundling hold, with the every-control scan as positive control;
- DECISIONS D244 question Q-N1 option (b) (this repair): a session fact K3 demoted (session_unreachable) is possibly
  every session whose reach holds a place the act may be at (catalogue.FAMILY_REACH as K3 reads it; a family it does
  not list and a place in no region judged by no reach) besides its claimed session and its own options, through the
  builder's options and so through possibly and every rule reading the fact; a session fact unresolved without a K3
  finding is read as before; 6c's N1 (ii) and (iii) hold 43235 base_included, with the widening switched off as
  positive control;
- effective(): L1 re-judged on the stored literals of every timing fact against the effective date - a member's date,
  none, a coarse literal - demoting only; the re-judge equals the claim-time rule (contract/consistency.rejudge,
  imported here only) over the grid relation x precision x literal x service date (D193);
- every unreadable row is refused (FactSetError), and the new modules keep 5.7 measure 4 (step 0b's scanner).
Every document here is written for this test: no real patient, no development or acceptance document.
"""
from __future__ import annotations

import dataclasses
import datetime
import enum
import hashlib
import importlib
import inspect
import json
import os
import random
import subprocess
import sys
import types
import typing
import unittest
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation import store
from studio.interpretation.contract import extract_read
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import anatomy
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import reading as RD
from studio.interpretation.engine import requirements_table as RT
from studio.interpretation.engine.types import Anchor, Cited, Fact, FactSet, Id, IdFamily, IsoDate, Span
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
    """A verification report with nothing counted, in settle's records (contract/types' Health, Coherence and Usage:
    the store is closed to them since DECISIONS D229, so an empty object is no longer a report)."""
    def zero(record) -> dict:
        return {field.name: 0 for field in dataclasses.fields(record)}

    return {'counts': {}, 'reasons': {}, 'doubts': [], 'health': {**zero(ct.Health), 'refused': []},
            'coherence': zero(ct.Coherence), 'unlisted': {'kept': unlisted, 'dropped': []},
            'usage': {'interpretation': zero(ct.Usage), 'appraisal': zero(ct.Usage)}}


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

    def test_a_supports_verdict_naming_approximate_alone_counters_nothing(self):
        # DECISIONS D224 (1.3): pass 2's approximate is recorded and never lowers a supported claim, so a supports
        # verdict naming approximate alone holds no counter evidence (r3a's R-B, applied by the integration), and the
        # fact resting on it stays established; beside another qualifier the verdict is still read as qualified (D186)
        events = colonoscopy()
        k = Ledger()
        k.claims = events['claims']
        e5 = events['events'][4]
        cited = [src(['S11'])]
        e5['kind'] = est(k, 'E5', 'kind', 'biopsy', cited)
        e5['kind']['appraisal']['qualifiers'] = ['approximate']
        k.claims[-1]['verdict']['qualifiers'] = ['approximate']  # the claim est() just stored, as settle stores it
        e5['session'] = unsettled(k, 'E5', 'session', 'X1', cited, verdict='supports',
                                  qualifiers=['approximate', 'conditional'],
                                  reasons=('appraisal_qualified:conditional',), evidence=['S10'])
        R = F.factset(view(events))
        self.assertEqual(F.fact(R, E5, A.KIND).counter, ())
        self.assertIs(F.fact(R, E5, A.KIND).result, ct.Result.SUPPORTED)
        self.assertEqual(F.fact(R, E5, A.SESSION).counter, (unit_span(10),))


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


# --- DECISIONS D220 and D235: the pair controls between the two objects (repair r2d; 3d PMONO, 4b F5; RL1) ------------
#
# 9.4's weakening acts on the FactSet ("a deleted member of a multi-valued list ..., the list's completeness claim and
# pair controls left as they were"), so these scenes are FactSets built directly; every value is synthetic.

LM = ct.Landmark
PERFORMED = ct.Status.PERFORMED
L3 = Id(IdFamily.LESION, 3)
E6 = Id(IdFamily.EVENT, 6)
PLACES, LESION = A.TARGET_PLACES, A.TARGET_LESION


def plain(result, value, state) -> Fact:
    return Fact(result=result, value=value, state=state, options=(), reasons=(), spans=())


def sup(value) -> Fact:
    return plain(ct.Result.SUPPORTED, value, ct.FactState.SUPPORTED)


def neg(value) -> Fact:
    return plain(ct.Result.NEGATED, value, ct.FactState.NEGATED)


def unresolved(value) -> Fact:
    return plain(ct.Result.UNRESOLVED, value, ct.FactState.SUPPORTED)


def doubted(value) -> Fact:
    return plain(ct.Result.UNKNOWN, value, ct.FactState.SUPPORTED)


def scene(events, *, lesions=None, controls=None, sessions=None) -> FactSet:
    """A FactSet of ``events`` ({Id: {Attribute: (Fact, ...)}}), with their lesions, pair controls and sessions."""
    return FactSet(encounter={}, people={}, sections={}, sessions=sessions or {}, anatomy={}, lesions=lesions or {},
                   events=events, unlisted=(), pair_controls=controls or {}, completeness={},
                   anchors={subject: Anchor(units=(Span(100 * subject.number, 100 * subject.number + 40),),
                                            kind_words=None, status_words=None) for subject in events})


def placed(*places, lesion=None) -> dict:
    """What apart_* reads of an event: its target places (each supported) and its target lesion (or a silent slot)."""
    return {PLACES: tuple(sup(place) for place in places), LESION: (sup(lesion) if lesion is not None else F.SILENT,)}


def replaced(R, subject, attribute, facts) -> FactSet:
    """``R`` with ``subject``'s ``attribute`` (an event's or a lesion's) replaced by ``facts``; everything else - the
    pair controls first - left as it was."""
    table = R.lesions if subject.family is IdFamily.LESION else R.events
    copy = {key: dict(value) for key, value in table.items()}
    copy[subject][attribute] = tuple(facts)
    if subject.family is IdFamily.LESION:
        return scene(R.events, lesions=copy, controls=R.pair_controls, sessions=R.sessions)
    return scene(copy, lesions=R.lesions, controls=R.pair_controls, sessions=R.sessions)


def deleted(R, subject, index, attribute=PLACES) -> FactSet:
    """9.4's weakening: member ``index`` of the list deleted, the pair controls left as they were."""
    members = list((R.lesions if subject.family is IdFamily.LESION else R.events)[subject][attribute])
    del members[index]
    return replaced(R, subject, attribute, members)


def before_place(R, a, b) -> bool:
    """4.2's apart_by_place as built before D220 (base ffb2d083's facts.py, by value): only the controls asking about
    the other object's CURRENT places are read."""
    first, second = F._supported(R, a, PLACES), F._supported(R, b, PLACES)
    if first is None or second is None:
        return False
    places_a = [place for place in first if isinstance(place, LM)]
    places_b = [place for place in second if isinstance(place, LM)]
    if len(places_a) != len(first) or len(places_b) != len(second):
        return False
    if not all(anatomy.disjoint(one, other) for one in places_a for other in places_b):
        return False
    return (all(R.pair_controls.get((a, PLACES, place)) is True for place in places_b)
            and all(R.pair_controls.get((b, PLACES, place)) is True for place in places_a))


def before_lesion(R, a, b) -> bool:
    """4.2's apart_by_lesion as built before D220 (base ffb2d083's facts.py, by value)."""
    first, second = F.fact(R, a, LESION), F.fact(R, b, LESION)
    if first.result is not ct.Result.SUPPORTED or second.result is not ct.Result.SUPPORTED:
        return False
    la, lb = first.value, second.value
    if not isinstance(la, Id) or not isinstance(lb, Id) or la == lb:
        return False
    distinct = any(F.holds(member, lb) for member in F.members(R, la, A.DISTINCT_FROM)) or any(
        F.holds(member, la) for member in F.members(R, lb, A.DISTINCT_FROM))
    return (distinct and R.pair_controls.get((a, LESION, lb)) is True
            and R.pair_controls.get((b, LESION, la)) is True)


def unrejected_between(R, a, b, attribute) -> bool:
    """Whether a pair control asked of ``a`` or ``b`` about ``attribute`` was not rejected (D220's added reading)."""
    return any(not rejected for (subject, about, _value), rejected in R.pair_controls.items()
               if about is attribute and subject in (a, b))


def performed(kind, *places, lesion=None) -> dict:
    """An act of ``kind`` as coverage and pairing read it: established performed in X1, on the date of service, by the
    documenting team, entered by the documenting clinician, with its target places and lesion (``placed``)."""
    facts = {A.KIND: (sup(kind),), A.STATUS: (sup(PERFORMED),), A.SESSION: (sup(X1),),
             A.DATE_RELATION: (sup(ct.DateRelation.ON_DATE_OF_SERVICE),),
             A.PERFORMER: (sup(ct.Performer.DOCUMENTING_TEAM),), A.ENTRY: (sup(ct.Owner.DOCUMENTING_CLINICIAN),)}
    facts.update(placed(*places, lesion=lesion))
    return facts


def full_list_controls(events, pairs, unclear=()) -> dict:
    """The place pair controls contract/claims.pair() makes from the FULL lists of ``pairs`` (claims.py's ``pair``: each
    object asked about every place of the other that none of its own places is compatible with, in both directions; one
    claim, so one control, per question), each rejected but those in ``unclear``."""
    controls = {}
    for first, second in pairs:
        for asked, other in ((first, second), (second, first)):
            own = [member.value for member in events[asked][PLACES]]
            for member in events[other][PLACES]:
                if own and not any(anatomy.compatible(member.value, place) for place in own):
                    controls[(asked, PLACES, member.value)] = (asked, PLACES, member.value) not in unclear
    return controls


def lesion_pair_controls(events, pairs, unclear=()) -> dict:
    """The lesion pair controls contract/claims.pair() makes for ``pairs`` (claims.py's ``pair``: each object asked
    about the other's target lesion when the two differ, in both directions; one claim, so one control, per question),
    each rejected but those in ``unclear``."""
    controls = {}
    for first, second in pairs:
        for asked, other in ((first, second), (second, first)):
            mine, theirs = events[asked][LESION][0].value, events[other][LESION][0].value
            if mine is not None and theirs is not None and mine != theirs:
                controls[(asked, LESION, theirs)] = (asked, LESION, theirs) not in unclear
    return controls


class D220Tests(SimpleTestCase):
    """DECISIONS D220: "apart" needs every pair control between the two objects rejected, whatever place it asks about,
    and every current member of the other covered by a rejected control; DECISIONS D235: the lesion arm reads only the
    lesion controls between the two objects, (a, lb) and (b, la)."""

    def test_4b_f5_a_deleted_members_unrejected_control_keeps_the_pair_together(self):
        # refute-4b-r2 F5 (its q4_case, seed 11, trial 36): a snare E3 at the liver on L2 and a biopsy E4 at a lymph
        # node and the duodenum; "This act was done in the duodenum." asked of the snare was NOT rejected, the other two
        # were
        controls = {(E3, PLACES, LM.LYMPH_NODE): True, (E3, PLACES, LM.DUODENUM): False, (E4, PLACES, LM.LIVER): True}
        R = scene({E3: placed(LM.LIVER, lesion=L2), E4: placed(LM.LYMPH_NODE, LM.DUODENUM)}, controls=controls)
        weak = deleted(R, E4, 1)  # the duodenum deleted, the controls left as they were
        self.assertEqual([member.value for member in F.members(weak, E4, PLACES)], [LM.LYMPH_NODE])
        for x, y in ((E3, E4), (E4, E3)):
            with self.subTest(pair=(x, y)):
                self.assertFalse(F.apart_by_place(R, x, y))
                self.assertTrue(before_place(weak, x, y))  # the defect: 4.2's reading before D220 sets it apart
                self.assertFalse(F.apart_by_place(weak, x, y))  # D220: the duodenum's control still holds the pair
        # with every control rejected the pair is apart, its member deleted or not: the controls decide
        rejected = scene(R.events, controls={key: True for key in controls})
        self.assertTrue(F.apart_by_place(rejected, E3, E4))
        self.assertTrue(F.apart_by_place(deleted(rejected, E4, 1), E3, E4))

    def test_4b_f5_through_coverage_the_biopsy_stays_held(self):
        # the same scene as coverage reads it (refute-4b-r2's fixture shape): an EGD X1 with its done examination, the
        # snare E3 and the biopsy E4; before the deletion E4 is U (biopsy_of_removed_lesion asked), and it stays U
        from studio.interpretation.engine import coverage as C

        def act(kind, *places, lesion=None):
            facts = {A.KIND: (sup(kind),), A.STATUS: (sup(PERFORMED),), A.SESSION: (sup(X1),),
                     A.DATE_RELATION: (sup(ct.DateRelation.ON_DATE_OF_SERVICE),),
                     A.PERFORMER: (sup(ct.Performer.DOCUMENTING_TEAM),),
                     A.ENTRY: (sup(ct.Owner.DOCUMENTING_CLINICIAN),)}
            facts.update(placed(*places, lesion=lesion))
            return facts

        lesions = {L2: {A.PLACES: (sup(LM.LIVER),), A.DISTINCT_FROM: (), A.SAME_AS: (),
                        A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),)}}
        sessions = {X1: {A.KIND: (sup(ct.SessionKind.EGD),), A.REACHED: (), A.DEVICE_REACHED: (), A.STATIONS: ()}}
        controls = {(E3, PLACES, LM.LYMPH_NODE): True, (E3, PLACES, LM.DUODENUM): False, (E4, PLACES, LM.LIVER): True}
        R = scene({E1: act(ct.Kind.EXAMINATION), E3: act(ct.Kind.SNARE, LM.LIVER, lesion=L2),
                   E4: act(ct.Kind.BIOPSY, LM.LYMPH_NODE, LM.DUODENUM)}, lesions=lesions, controls=controls,
                  sessions=sessions)
        weak = deleted(R, E4, 1)
        for name, given in (('settled', R), ('the duodenum deleted', weak)):
            with self.subTest(name):
                self.assertIs(C.verdict(given, E4).truth, C.Truth.U)
                self.assertTrue(C.doubted(given, E4))
        with mock.patch.object(F, 'apart_by_place', before_place):  # the reading before D220: the release F5 found
            self.assertIs(C.verdict(weak, E4).truth, C.Truth.T)

    def test_3d_sc_b_single_target_case_holds(self):
        # refute-3d-r2 PMONO, its single-target SC-B case (through pairing.py's facts.apart_by_place): D "No polyps
        # were removed from the hepatic flexure." filed [hepatic flexure]; A a cold snare filed [ascending colon,
        # cecum]; "This statement is about snares in the cecum." was NOT rejected; then A's cecum deleted, the controls
        # left as they were
        from studio.interpretation.engine import pairing as P
        from studio.interpretation.engine import requirements as rq

        common = {A.KIND: (sup(ct.Kind.SNARE),), A.SESSION: (sup(X1),),
                  A.DATE_RELATION: (sup(ct.DateRelation.ON_DATE_OF_SERVICE),)}
        statement = {**common, A.STATUS: (neg(PERFORMED),), A.SCOPE_BREADTH: (sup(ct.Breadth.SINGLE_TARGET),),
                     PLACES: (sup(LM.HEPATIC_FLEXURE),)}
        snare = {**common, A.STATUS: (sup(PERFORMED),), A.PERFORMER: (sup(ct.Performer.DOCUMENTING_TEAM),),
                 A.TECHNIQUE_DEVICE: (sup(ct.Device.COLD_SNARE),), PLACES: (sup(LM.ASCENDING_COLON), sup(LM.CECUM))}
        controls = {(E1, PLACES, LM.ASCENDING_COLON): True, (E1, PLACES, LM.CECUM): False,
                    (E2, PLACES, LM.HEPATIC_FLEXURE): True}
        R = scene({E1: statement, E2: snare}, controls=controls,
                  sessions={X1: {A.KIND: (sup(ct.SessionKind.COLONOSCOPY),)}})
        weak = deleted(R, E2, 1)
        self.assertTrue(before_place(weak, E1, E2))  # the release 3d found
        for name, given in (('settled', R), ('the cecum deleted', weak)):
            with self.subTest(name):
                self.assertFalse(F.apart_by_place(given, E1, E2))
                pair = P.relation(given, E1, E2)
                self.assertIs(pair.relation, P.Relation.UNRESOLVED)
                self.assertIs(pair.row, P.Row.TARGET)
                self.assertEqual(P.item(pair).fact, rq.FactKey.STATEMENT_SCOPE)

    def test_every_place_control_asked_of_either_object_is_read_whatever_place_it_asks(self):
        # the stored row: the snare E2 (sigmoid colon) and the rectal biopsy denial E3 are apart; then "This act was
        # done in the transverse colon." - asked of the snare for the biopsy E5's place - is left unclear by pass 2
        self.assertTrue(F.apart_by_place(F.factset(view(colonoscopy())), E2, E3))
        events = colonoscopy()
        k = Ledger()
        k.claims = events['claims']
        k.pair('E2', 'target.places', 'transverse_colon', ['S6'], 'unclear')
        R = F.factset(view(events))
        self.assertIs(R.pair_controls[(E2, PLACES, LM.TRANSVERSE_COLON)], False)
        for x, y in ((E2, E3), (E3, E2)):
            with self.subTest(pair=(x, y)):
                self.assertTrue(before_place(R, x, y))  # 4.2's reading before D220 (repair r2d's question Q1)
                self.assertFalse(F.apart_by_place(R, x, y))
        # rejected, the pair is apart again; and the biopsy E5's own unrejected rectum control (SC-B) never reaches
        # the pair E2/E3: a control asked of a third object is not between them
        events = colonoscopy()
        k.claims = events['claims']
        k.pair('E2', 'target.places', 'transverse_colon', ['S6'], 'contradicts')
        R = F.factset(view(events))
        self.assertIs(R.pair_controls[(E5, PLACES, LM.RECTUM)], False)
        self.assertTrue(F.apart_by_place(R, E2, E3))
        self.assertTrue(F.apart_by_place(R, E3, E2))

    def test_d235_the_lesion_arm_reads_only_the_controls_between_the_two_objects(self):
        # DECISIONS D235 (refute-r2d-r2 RL1): target.lesion is single-valued and no 9.4 weakening deletes or changes it,
        # so the lesion pair controls between E2 (L1) and E3 (L2) are exactly (E2, L2) and (E3, L1) - their target
        # lesions name them. A lesion control asked of either about L3, a lesion only E4 names (made for another pair),
        # is not read, rejected or not: 4.2's lesion reading
        lesions = {L1: {A.DISTINCT_FROM: (sup(L2),)}, L2: {}, L3: {}}
        controls = {(E2, LESION, L2): True, (E3, LESION, L1): True}
        events = {E2: placed(lesion=L1), E3: placed(lesion=L2), E4: placed(lesion=L3)}
        R = scene(events, lesions=lesions, controls=controls)
        self.assertTrue(F.apart_by_lesion(R, E2, E3))
        for asked in (E2, E3):
            for rejected in (False, True):
                given = scene(events, lesions=lesions, controls={**controls, (asked, LESION, L3): rejected})
                with self.subTest(asked=asked, rejected=rejected):
                    self.assertTrue(before_lesion(given, E2, E3))
                    self.assertTrue(F.apart_by_lesion(given, E2, E3))
                    self.assertTrue(F.apart_by_lesion(given, E3, E2))
                    # the every-control scan, which stays for multi-valued sets (D235), reads that control
                    self.assertIs(F.apart_by_controls(given, E2, E3, LESION, (L1,), (L2,)), rejected)
        # asked of a third object: not between E2 and E3
        given = scene(events, lesions=lesions, controls={**controls, (E4, LESION, L1): False})
        self.assertTrue(F.apart_by_lesion(given, E2, E3))
        # a between control not rejected keeps the pair together, in both directions
        for between in controls:
            given = scene(events, lesions=lesions, controls={**controls, between: False})
            with self.subTest(unrejected=between):
                self.assertFalse(F.apart_by_lesion(given, E2, E3))
                self.assertFalse(F.apart_by_lesion(given, E3, E2))
        # each current lesion still needs its own rejected control (a control not generated is not rejected)
        for missing in controls:
            given = scene(events, lesions=lesions, controls={key: True for key in controls if key != missing})
            with self.subTest(missing=missing):
                self.assertFalse(F.apart_by_lesion(given, E2, E3))

    def test_d235_rl1_a_biopsy_of_another_polyp_is_apart_and_45380_carries_no_bundling_hold(self):
        # refute-r2d-r2 RL1 (its lesion_arm probe; DECISIONS D235): one colonoscopy, three polyps, distinct_from
        # supported between every two; a cold snare E3 of L1 in the sigmoid colon, a forceps biopsy E4 of L2 also in the
        # sigmoid colon, a cold snare E5 of L3 in the transverse colon. The pair controls are exactly claims.pair()'s
        # place and lesion rule over D211's pairs (the biopsy with each snare), every one rejected but "This act was
        # done to lesion L3.", asked of the biopsy for the pair (E4, E5) and left unclear
        from studio.interpretation.engine import coverage as C

        sessions = {X1: {A.KIND: (sup(ct.SessionKind.COLONOSCOPY),), A.REACHED: (), A.DEVICE_REACHED: (),
                         A.STATIONS: ()}}

        def polyp(place, *others):
            return {A.PLACES: (sup(place),), A.DISTINCT_FROM: tuple(sup(other) for other in others), A.SAME_AS: (),
                    A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),)}

        def snare(place, lesion):
            return {**performed(ct.Kind.SNARE, place, lesion=lesion), A.TECHNIQUE_DEVICE: (sup(ct.Device.COLD_SNARE),)}

        lesions = {L1: polyp(LM.SIGMOID_COLON, L2, L3), L2: polyp(LM.SIGMOID_COLON, L1, L3),
                   L3: polyp(LM.TRANSVERSE_COLON, L1, L2)}
        events = {E1: performed(ct.Kind.EXAMINATION), E3: snare(LM.SIGMOID_COLON, L1),
                  E4: performed(ct.Kind.BIOPSY, LM.SIGMOID_COLON, lesion=L2), E5: snare(LM.TRANSVERSE_COLON, L3)}
        pairs, unclear = ((E4, E3), (E4, E5)), {(E4, LESION, L3)}
        R = scene(events, lesions=lesions, sessions=sessions,
                  controls={**full_list_controls(events, pairs, unclear), **lesion_pair_controls(events, pairs,
                                                                                                unclear)})
        self.assertEqual(dict(R.pair_controls), {
            (E4, LESION, L1): True, (E3, LESION, L2): True, (E4, PLACES, LM.TRANSVERSE_COLON): True,
            (E4, LESION, L3): False, (E5, PLACES, LM.SIGMOID_COLON): True, (E5, LESION, L2): True})
        for x, y in ((E4, E3), (E3, E4)):
            with self.subTest(pair=(x, y)):
                self.assertTrue(F.apart_by_lesion(R, x, y))  # L1 and L2: the controls between them rejected
                self.assertFalse(F.apart_by_place(R, x, y))  # both in the sigmoid colon: only the lesions differ
        self.assertTrue(F.apart_by_place(R, E4, E5))  # the pair the unclear control was made for, apart either way
        self.assertIs(C.verdict(R, E4).truth, C.Truth.T)  # the biopsy is its own act, never the snared polyp's
        self.assertFalse(C.doubted(R, E4))
        self.assertEqual(C.bundling('45380', (E4,), R), ())  # 45380 carries no bundling hold

        # the positive control: the every-control scan as repair r2d-2 built it (D220's reading of the lesion arm)
        # holds the biopsy against the snare through the control made for (E4, E5) - the defect RL1 found
        def scanned(R_, a, b):
            first, second = F.fact(R_, a, LESION), F.fact(R_, b, LESION)
            if not (F.holds(first, first.value) and F.holds(second, second.value)) or first.value == second.value:
                return False
            distinct = any(F.holds(member, second.value) for member in F.members(R_, first.value, A.DISTINCT_FROM))
            distinct = distinct or any(F.holds(member, first.value)
                                       for member in F.members(R_, second.value, A.DISTINCT_FROM))
            return distinct and F.apart_by_controls(R_, a, b, LESION, (first.value,), (second.value,))

        with mock.patch.object(F, 'apart_by_lesion', scanned):
            self.assertIs(C.verdict(R, E4).truth, C.Truth.U)
            self.assertEqual([(held.fact, held.subject) for held in C.bundling('45380', (E4,), R)],
                             [('act_target', E4)])

    def test_apart_by_controls(self):
        controls = {(E2, PLACES, LM.RECTUM): True, (E3, PLACES, LM.SIGMOID_COLON): True,
                    (E2, LESION, L2): False, (E4, PLACES, LM.CECUM): False}
        R = scene({E2: placed(LM.SIGMOID_COLON), E3: placed(LM.RECTUM)}, controls=controls)
        self.assertTrue(F.apart_by_controls(R, E2, E3, PLACES, (LM.SIGMOID_COLON,), (LM.RECTUM,)))
        self.assertTrue(F.apart_by_controls(R, E3, E2, PLACES, (LM.RECTUM,), (LM.SIGMOID_COLON,)))
        # a current member no rejected control covers
        self.assertFalse(F.apart_by_controls(R, E2, E3, PLACES, (LM.SIGMOID_COLON,), (LM.RECTUM, LM.CECUM)))
        # the attribute's own controls only: E2's unrejected lesion control does not touch its places, and does
        # touch its lesions
        self.assertFalse(F.apart_by_controls(R, E2, E3, LESION, (), ()))
        self.assertTrue(F.apart_by_controls(R, E3, E5, LESION, (), ()))
        with self.assertRaises(ValueError):
            F.apart_by_controls(R, E2, E3, A.KIND, (), ())

    def test_never_more_apart_than_before_and_different_only_through_an_unrejected_control(self):
        # over generated settled scenes (controls from the full lists, as contract/claims.pair() makes them): D220's
        # place reading sets nothing apart that 4.2's reading before D220 did not, and every pair it no longer sets
        # apart has an unrejected control asked of one of the two objects (repair r2d's question Q1, D236); the lesion
        # arm IS 4.2's reading on every pair (D235), also where the every-control scan would read a lesion control
        # made for another pair (refute-r2d-r2 RL1)
        rnd = random.Random(220)
        changed = scanned = 0
        for _ in range(150):
            R = generated(rnd)
            for x in R.events:
                for y in R.events:
                    if x == y:
                        continue
                    now, was = F.apart_by_place(R, x, y), before_place(R, x, y)
                    self.assertLessEqual(now, was)
                    if now != was:
                        changed += 1
                        self.assertTrue(unrejected_between(R, x, y, PLACES))
                    lesion_now, lesion_was = F.apart_by_lesion(R, x, y), before_lesion(R, x, y)
                    self.assertIs(lesion_now, lesion_was)
                    if lesion_was and unrejected_between(R, x, y, LESION):
                        scanned += 1  # D220's every-control scan would have held this pair (RL1's class)
        self.assertGreater(changed, 0)  # the generator reaches the place class
        self.assertGreater(scanned, 0)  # and RL1's lesion class, where the lesion arm stays 4.2's reading

    def test_p_mono_under_9_4s_weakenings(self):
        # P-MONO of both predicates (9.4) over generated settled scenes and every weakening of each: a deleted list
        # member (the pair controls left as they were), a member unresolved or doubted, a target lesion unresolved, a
        # distinct_from member deleted or unresolved, a rejected control not rejected. No pair is set apart that was
        # not before - but for the one named release (repair r2d's question Q2): a deleted member that overlaps a place
        # of the other object without being compatible with it (engine/anatomy: neither compatible nor disjoint), its
        # control on the other object REJECTED, so the controls do set the two apart and the deletion removed only the
        # overlap
        rnd = random.Random(9_4)
        releases = defects = 0
        for _ in range(120):
            R = generated(rnd)
            before = {(name, x, y): predicate(R, x, y)
                      for name, predicate in (('place', F.apart_by_place), ('lesion', F.apart_by_lesion))
                      for x in R.events for y in R.events if x != y}
            old = {(x, y): before_place(R, x, y) for x in R.events for y in R.events if x != y}
            for weakening, weak in weakenings(R):
                for (name, x, y), was in before.items():
                    now = (F.apart_by_place if name == 'place' else F.apart_by_lesion)(weak, x, y)
                    if (name == 'place' and not old[(x, y)] and before_place(weak, x, y)
                            and not overlap_release(R, weakening, x, y)):
                        defects += 1  # 4.2's reading before D220 released it: D220's class
                    if now and not was:
                        releases += 1
                        with self.subTest(weakening=weakening, pair=(name, x, y)):
                            self.assertEqual(name, 'place')
                            self.assertTrue(overlap_release(R, weakening, x, y))
        self.assertGreater(defects, 0)  # the generator reaches D220's class: every one stays held
        self.assertGreater(releases, 0)  # and reaches the named release

    def test_on_the_pairing_and_coverage_fixtures_the_predicates_answer_as_before(self):
        # the done-when: on the pairing and coverage fixtures as they were at the base - every call the base's
        # tests.v2.test_pairing and tests.v2.test_coverage made to the two predicates, frozen as data (FIXTURE_CALLS;
        # refute-r2d-r1 RF2) - both predicates answer as recorded there, and so does 4.2's reading before D220. Those
        # fixtures hold no settled FactSet of question Q1's class (a control another pair made, not rejected, asked of
        # one of the two objects: refute-r2d-r1 RF3); test_q1_... pins that class
        self.assertEqual(len(set(FIXTURE_CALLS)), len(FIXTURE_CALLS))
        tally = {}
        for line in FIXTURE_CALLS:
            tally[tuple(line.split()[:2])] = tally.get(tuple(line.split()[:2]), 0) + 1
        self.assertEqual(tally, {('lesion', '0'): 103, ('lesion', '1'): 3, ('place', '0'): 92, ('place', '1'): 5})
        self.assertEqual(fixture_replay(), (203, []))

    def test_a_later_steps_d220_tests_in_pairing_or_coverage_never_reach_the_fixture_replay(self):
        # refute-r2d-r1 RF2: the first patch ran the tests test_pairing and test_coverage hold at run time, so a D220
        # test a step built on r2d adds to either - r4b's for 4b F5 (the biopsy held when its duodenum is deleted),
        # r3d's for 3d's single-target case (held when the cecum is deleted) - turned this file red. Both modules here
        # hold such tests, served to every import route (sys.modules, the package's attributes, import_module); no
        # test of any module runs while the replay runs, and the replay, data recorded at the base, answers as recorded
        f5 = deleted(scene({E3: placed(LM.LIVER, lesion=L2), E4: placed(LM.LYMPH_NODE, LM.DUODENUM)},
                           controls={(E3, PLACES, LM.LYMPH_NODE): True, (E3, PLACES, LM.DUODENUM): False,
                                     (E4, PLACES, LM.LIVER): True}), E4, 1)
        sc_b = deleted(scene({E1: placed(LM.HEPATIC_FLEXURE), E2: placed(LM.ASCENDING_COLON, LM.CECUM)},
                             controls={(E1, PLACES, LM.ASCENDING_COLON): True, (E1, PLACES, LM.CECUM): False,
                                       (E2, PLACES, LM.HEPATIC_FLEXURE): True}), E2, 1)

        class LaterD220Tests(unittest.TestCase):
            def test_4b_f5_held(self_):
                self_.assertFalse(F.apart_by_place(f5, E4, E3))

            def test_3d_sc_b_held(self_):
                self_.assertFalse(F.apart_by_place(sc_b, E1, E2))

        later = types.ModuleType('later_d220_tests')
        later.LaterD220Tests = LaterD220Tests
        result = unittest.TestResult()
        unittest.TestLoader().loadTestsFromTestCase(LaterD220Tests).run(result)
        self.assertEqual((result.testsRun, result.wasSuccessful()), (2, True))  # D220 holds both pairs
        self.assertTrue(before_place(f5, E4, E3) and before_place(sc_b, E1, E2))  # 4.2's reading before D220 does not
        names = ('tests.v2.test_pairing', 'tests.v2.test_coverage')
        package, real = importlib.import_module('tests.v2'), importlib.import_module
        ran = []
        run, debug = unittest.TestCase.run, unittest.TestCase.debug

        def import_module(name, package=None):
            return later if name in names else real(name, package)

        def recorded(method):
            def call(test, *args, **kwargs):
                ran.append(test.id())
                return method(test, *args, **kwargs)
            return call

        saved = {name: sys.modules.get(name) for name in names}
        try:
            sys.modules.update(dict.fromkeys(names, later))
            with mock.patch.object(package, 'test_pairing', later, create=True), \
                    mock.patch.object(package, 'test_coverage', later, create=True), \
                    mock.patch.object(importlib, 'import_module', import_module), \
                    mock.patch.object(unittest.TestCase, 'run', recorded(run)), \
                    mock.patch.object(unittest.TestCase, 'debug', recorded(debug)):
                served = (sys.modules['tests.v2.test_pairing'], importlib.import_module('tests.v2.test_coverage'),
                          unittest.TestLoader().loadTestsFromName('tests.v2.test_pairing').countTestCases())
                replayed = fixture_replay()
        finally:
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module
        self.assertEqual(served, (later, later, 2))  # every route serves the later step's two tests
        self.assertEqual(ran, [])  # no test of any module ran inside the replay
        self.assertEqual(replayed, (203, []))

    def test_q1_on_a_settled_factset_another_pairs_unrejected_control_holds_the_pair(self):
        # repair r2d's question Q1, open for the owner (refute-r2d-r1 RF1, RF3). D220 expects 4.2's reading unchanged on
        # the FactSets settle produces, whose pair controls come from the full lists. A stored pair control names the
        # object it asks and the value it asks about, never the pair it was made for, so a control another pair made,
        # asked of one of the two objects and not rejected, holds a pair 4.2's reading set apart - on a settled FactSet
        # whose controls are exactly the ones contract/claims.pair() makes. Pinned to the fail-closed reading as built
        # (Q1's option (a)); under option (b) - each pair control's other objects carried through settle, store and the
        # FactSet (request R3), and exactly the controls between the two read - both scenes answer as 4.2's reading did,
        # and this test changes with the ruling
        from studio.interpretation.engine import coverage as C
        from studio.interpretation.engine import pairing as P
        from studio.interpretation.engine import requirements as rq

        # scene A (coverage): one colonoscopy; a cold snare E3 of L1 at the rectosigmoid, a biopsy E4 in the rectum
        # and a biopsy E5 in the ascending colon; claims.pair() pairs the snare with each biopsy (D211: never two
        # biopsies); every control rejected but "This act was done in the rectum.", asked of the snare for E4, left
        # unclear
        sessions = {X1: {A.KIND: (sup(ct.SessionKind.COLONOSCOPY),), A.REACHED: (), A.DEVICE_REACHED: (),
                         A.STATIONS: ()}}
        lesions = {L1: {A.PLACES: (sup(LM.RECTOSIGMOID),), A.DISTINCT_FROM: (), A.SAME_AS: (),
                        A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),)}}

        def colonoscopy_scene(*places_of_e5):
            events = {E1: performed(ct.Kind.EXAMINATION), E3: performed(ct.Kind.SNARE, LM.RECTOSIGMOID, lesion=L1),
                      E4: performed(ct.Kind.BIOPSY, LM.RECTUM), E5: performed(ct.Kind.BIOPSY, *places_of_e5)}
            return scene(events, lesions=lesions, sessions=sessions, controls=full_list_controls(
                events, ((E3, E4), (E3, E5)), {(E3, PLACES, LM.RECTUM)}))

        R = colonoscopy_scene(LM.ASCENDING_COLON)
        self.assertEqual(dict(R.pair_controls), {
            (E3, PLACES, LM.RECTUM): False, (E4, PLACES, LM.RECTOSIGMOID): True,
            (E3, PLACES, LM.ASCENDING_COLON): True, (E5, PLACES, LM.RECTOSIGMOID): True})
        for x, y in ((E5, E3), (E3, E5)):
            with self.subTest(pair=(x, y)):
                self.assertTrue(before_place(R, x, y))  # 4.2's reading: the ascending colon biopsy is apart
                self.assertFalse(F.apart_by_place(R, x, y))  # as built: the snare's unclear rectum control holds it
        self.assertIs(C.verdict(R, E5).truth, C.Truth.U)  # biopsy_of_removed_lesion asked: 45380's bundling is held
        self.assertTrue(C.doubted(R, E5))
        with mock.patch.object(F, 'apart_by_place', before_place):
            self.assertIs(C.verdict(R, E5).truth, C.Truth.T)
        # why no reading of the FactSet alone does both: S2, scene A with E5 also in the rectum, is settled too, with
        # the same controls (the snare's rectum control is one claim for both biopsies); deleting E5's rectum (9.4,
        # the controls left as they were) gives scene A exactly, and P-MONO keeps E5 held there, as it is on S2
        S2 = colonoscopy_scene(LM.ASCENDING_COLON, LM.RECTUM)
        self.assertEqual(dict(S2.pair_controls), dict(R.pair_controls))
        W = deleted(S2, E5, 1)
        self.assertEqual((W.events, dict(W.pair_controls)), (R.events, dict(R.pair_controls)))
        for reading in (F.apart_by_place, before_place):
            with mock.patch.object(F, 'apart_by_place', reading):
                self.assertIs(C.verdict(S2, E5).truth, C.Truth.U)

        # scene B (pairing): "No biopsies were taken from the rectum." (single target), a biopsy E4 at the rectosigmoid
        # and a biopsy E5 in the transverse colon; claims.pair() pairs the statement with each biopsy; every control
        # rejected but "This statement is about biopsies in the rectosigmoid.", asked of the statement for E4, left
        # unclear
        statement = {A.KIND: (sup(ct.Kind.BIOPSY),), A.STATUS: (neg(PERFORMED),), A.SESSION: (sup(X1),),
                     A.DATE_RELATION: (sup(ct.DateRelation.ON_DATE_OF_SERVICE),),
                     A.SCOPE_BREADTH: (sup(ct.Breadth.SINGLE_TARGET),), PLACES: (sup(LM.RECTUM),)}
        events = {E1: performed(ct.Kind.EXAMINATION), E2: statement, E4: performed(ct.Kind.BIOPSY, LM.RECTOSIGMOID),
                  E5: performed(ct.Kind.BIOPSY, LM.TRANSVERSE_COLON)}
        R = scene(events, sessions=sessions, controls=full_list_controls(
            events, ((E2, E4), (E2, E5)), {(E2, PLACES, LM.RECTOSIGMOID)}))
        self.assertEqual(dict(R.pair_controls), {
            (E2, PLACES, LM.RECTOSIGMOID): False, (E4, PLACES, LM.RECTUM): True,
            (E2, PLACES, LM.TRANSVERSE_COLON): True, (E5, PLACES, LM.RECTUM): True})
        self.assertTrue(before_place(R, E2, E5))
        pair = P.relation(R, E2, E5)  # as built: the statement's unclear rectosigmoid control holds the pair
        self.assertEqual((pair.relation, pair.row, P.item(pair).fact),
                         (P.Relation.UNRESOLVED, P.Row.TARGET, rq.FactKey.STATEMENT_SCOPE))
        with mock.patch.object(F, 'apart_by_place', before_place):  # 4.2's reading: independent, 45380 not held
            self.assertIs(P.relation(R, E2, E5).relation, P.Relation.INDEPENDENT)


def fixture_test(test) -> bool:
    """Whether a loaded test of another module is one repair r2d's fixture harvest ran: not a hypothesis test (it
    carries hypothesis's ``is_hypothesis_test`` mark) and not a BoundaryTests test. The harvest ran once, at the base,
    to record FIXTURE_CALLS (repair r2d-2); nothing here runs another module's tests any more (refute-r2d-r1 RF2)."""
    method = getattr(type(test), test._testMethodName, None)
    return type(test).__name__ != 'BoundaryTests' and not getattr(method, 'is_hypothesis_test', False)


# --- the pairing and coverage fixtures' calls, frozen as data (D220's done-when; refute-r2d-r1 RF2) -------------------
#
# Every call the base's (ffb2d083) tests.v2.test_pairing and tests.v2.test_coverage made to apart_by_place and
# apart_by_lesion - their 174 tests that ``fixture_test`` admits, 9,865 calls - recorded once by repair r2d-2 with the
# base's facts.py: one line per distinct call, holding what the called predicate reads and nothing else. A place call:
# the two objects' target places and the place pair controls asked of either; a lesion call: their target lesions, those
# lesions' distinct_from and the lesion pair controls asked of either. Each member is its result and value (the state
# it had follows from them: ``fixture_case``); the two objects are renamed E1 and E2 and the lesions L1.. in order of
# appearance. The recorder decoded every line again and found the predicate answering on it exactly as on the call's
# whole FactSet, with the base's facts.py and with D220's, and the lines identical under both. A line:
#     <place | lesion> <1 apart, 0 not> | <E1's members> | <E2's members> [| <distinct_from>] | <pair controls>
# members: <result>:<value>, the result sup, neg, unr, con or unk and the value ~ for none, '-' for no member;
# distinct_from: L<n>=<member>,<member>...; pair controls: E<1 or 2, the object asked>:<value>:<1 rejected, 0 not>.
# As data it is frozen: a test a later step adds to either module never reaches it.
FIXTURE_CALLS = (
    'lesion 0 | - | - | - | -',
    'lesion 0 | - | sup:L1 | - | -',
    'lesion 0 | - | unk:L1 | - | -',
    'lesion 0 | - | unk:~ | - | -',
    'lesion 0 | - | unk:~ | - | E1:L2:1 E2:L1:1',
    'lesion 0 | - | unr:L1 | - | -',
    'lesion 0 | con:~ | - | - | -',
    'lesion 0 | con:~ | neg:L1 | L1=sup:L2 | E1:L1:0',
    'lesion 0 | con:~ | neg:L1 | L1=sup:L2,sup:L3 | E2:L3:1',
    'lesion 0 | con:~ | sup:L1 | - | -',
    'lesion 0 | con:~ | sup:L1 | - | E1:L1:1 E2:L2:1',
    'lesion 0 | con:~ | unr:L1 | L1=sup:L2 | -',
    'lesion 0 | neg:L1 | con:~ | L1=sup:L2,sup:L3 | E1:L3:1',
    'lesion 0 | neg:L1 | neg:L1 | - | E1:L2:1 E2:L2:1',
    'lesion 0 | neg:L1 | neg:L2 | L1=sup:L2 L2=sup:L3 | -',
    'lesion 0 | neg:L1 | sup:L2 | - | E2:L1:0',
    'lesion 0 | neg:L1 | sup:L2 | L1=sup:L3 L2=sup:L1 | -',
    'lesion 0 | neg:L1 | unk:L2 | - | E1:L1:0 E1:L2:0 E2:L1:1 E2:L3:1',
    'lesion 0 | neg:L1 | unk:L2 | - | E1:L2:0 E2:L3:0',
    'lesion 0 | neg:L1 | unk:L2 | - | E1:L2:1 E2:L3:1',
    'lesion 0 | neg:L1 | unk:L2 | - | E2:L1:0',
    'lesion 0 | neg:L1 | unk:L2 | L1=sup:L3 L2=sup:L1 | E2:L3:0',
    'lesion 0 | neg:L1 | unk:~ | L1=sup:L2 | E1:L1:1',
    'lesion 0 | neg:L1 | unk:~ | L1=sup:L2,sup:L3 | E1:L1:1',
    'lesion 0 | neg:L1 | unr:L1 | - | E2:L2:0',
    'lesion 0 | neg:L1 | unr:L1 | L1=sup:L2 | E1:L1:1 E2:L3:0',
    'lesion 0 | neg:L1 | unr:L1 | L1=sup:L2,sup:L3 | E1:L1:1 E2:L2:0',
    'lesion 0 | neg:L1 | unr:L2 | - | E1:L2:0 E2:L3:0',
    'lesion 0 | sup:L1 | - | - | -',
    'lesion 0 | sup:L1 | - | - | E1:L2:0',
    'lesion 0 | sup:L1 | - | - | E1:L2:1',
    'lesion 0 | sup:L1 | - | L1=sup:L2 | -',
    'lesion 0 | sup:L1 | - | L1=sup:L2 | E1:L2:0',
    'lesion 0 | sup:L1 | - | L1=sup:L2 | E1:L2:1',
    'lesion 0 | sup:L1 | - | L1=unk:L2 | E1:L2:1',
    'lesion 0 | sup:L1 | - | L1=unr:L2 | E1:L2:1',
    'lesion 0 | sup:L1 | con:~ | - | -',
    'lesion 0 | sup:L1 | con:~ | L1=sup:L2 | E1:L2:1 E2:L1:1',
    'lesion 0 | sup:L1 | con:~ | L1=sup:L2 | E1:L3:1 E2:L1:0 E2:L2:1',
    'lesion 0 | sup:L1 | con:~ | L1=sup:L2,sup:L3 | E1:L2:0 E1:L3:0 E2:L1:0 E2:L3:0',
    'lesion 0 | sup:L1 | sup:L1 | - | -',
    'lesion 0 | sup:L1 | sup:L2 | - | -',
    'lesion 0 | sup:L1 | sup:L2 | - | E1:L2:1 E2:L1:1',
    'lesion 0 | sup:L1 | sup:L2 | L1=sup:L2 | -',
    'lesion 0 | sup:L1 | sup:L2 | L1=sup:L2 | E1:L2:0 E2:L1:0',
    'lesion 0 | sup:L1 | sup:L2 | L1=sup:L2 | E1:L2:0 E2:L1:1',
    'lesion 0 | sup:L1 | sup:L2 | L1=sup:L2 | E1:L2:1',
    'lesion 0 | sup:L1 | sup:L2 | L1=sup:L2 | E1:L2:1 E2:L1:0',
    'lesion 0 | sup:L1 | sup:L2 | L1=unk:L2 | E1:L2:1 E2:L1:1',
    'lesion 0 | sup:L1 | sup:L2 | L1=unr:L2 | E1:L2:1 E2:L1:1',
    'lesion 0 | sup:L1 | sup:L2 | L2=sup:L1 | E1:L2:0 E2:L1:1',
    'lesion 0 | sup:L1 | sup:L2 | L2=sup:L1 | E1:L2:1',
    'lesion 0 | sup:L1 | sup:L2 | L2=sup:L1 | E1:L2:1 E2:L1:0',
    'lesion 0 | sup:L1 | sup:L2 | L2=sup:L1 | E2:L1:1',
    'lesion 0 | sup:L1 | sup:L2 | L2=unk:L1 | E1:L2:1 E2:L1:1',
    'lesion 0 | sup:L1 | sup:L2 | L2=unr:L1 | E1:L2:1 E2:L1:1',
    'lesion 0 | sup:L1 | unk:L1 | - | -',
    'lesion 0 | sup:L1 | unk:L1 | L1=sup:L2 | E2:L3:0',
    'lesion 0 | sup:L1 | unk:L1 | L1=sup:L2,sup:L3 | -',
    'lesion 0 | sup:L1 | unk:L2 | L1=sup:L2 | E1:L2:1 E2:L1:1',
    'lesion 0 | sup:L1 | unk:L2 | L1=sup:L3 L2=sup:L1 | E1:L2:0 E2:L1:0 E2:L3:0',
    'lesion 0 | sup:L1 | unk:L2 | L2=sup:L1 | E1:L2:1 E2:L1:1',
    'lesion 0 | sup:L1 | unk:~ | - | -',
    'lesion 0 | sup:L1 | unk:~ | L1=sup:L2 | E1:L2:1 E2:L1:1',
    'lesion 0 | sup:L1 | unk:~ | L1=sup:L2 | E1:L3:1',
    'lesion 0 | sup:L1 | unr:L1 | - | -',
    'lesion 0 | sup:L1 | unr:L2 | - | E1:L2:0 E2:L1:0',
    'lesion 0 | sup:L1 | unr:L2 | L1=sup:L2 | E1:L2:1 E2:L1:1',
    'lesion 0 | sup:L1 | unr:L2 | L2=sup:L1 | E1:L2:1 E2:L1:1',
    'lesion 0 | unk:L1 | - | - | -',
    'lesion 0 | unk:L1 | - | - | E1:L2:1',
    'lesion 0 | unk:L1 | - | L1=sup:L2 | E1:L2:1',
    'lesion 0 | unk:L1 | con:~ | L1=sup:L2 | -',
    'lesion 0 | unk:L1 | neg:L2 | - | E1:L2:1 E1:L3:1 E2:L1:0 E2:L2:0',
    'lesion 0 | unk:L1 | neg:L2 | - | E1:L3:0 E2:L1:0',
    'lesion 0 | unk:L1 | neg:L2 | - | E1:L3:1 E2:L1:1',
    'lesion 0 | unk:L1 | neg:L2 | L1=sup:L2 L2=sup:L1,sup:L3 | E2:L3:1',
    'lesion 0 | unk:L1 | neg:L2 | L1=sup:L3 L2=sup:L3 | E1:L2:0',
    'lesion 0 | unk:L1 | neg:L2 | L1=sup:L3 L2=sup:L3 | E1:L2:0 E1:L3:0',
    'lesion 0 | unk:L1 | sup:L1 | - | -',
    'lesion 0 | unk:L1 | sup:L1 | L1=sup:L2 | E1:L3:0',
    'lesion 0 | unk:L1 | sup:L2 | L1=sup:L2 L2=sup:L3 | E1:L2:0 E1:L3:0 E2:L1:0',
    'lesion 0 | unk:L1 | sup:L2 | L1=sup:L2 | E1:L2:1 E2:L1:1',
    'lesion 0 | unk:L1 | sup:L2 | L2=sup:L1 | E1:L2:1 E2:L1:1',
    'lesion 0 | unk:L1 | unk:L1 | - | E1:L2:1 E2:L2:1',
    'lesion 0 | unk:L1 | unk:L1 | L1=sup:L2,sup:L3 | -',
    'lesion 0 | unk:L1 | unr:L1 | - | E1:L2:0 E2:L2:0',
    'lesion 0 | unk:L1 | unr:L2 | L1=sup:L3 L2=sup:L3 | E1:L2:1 E2:L3:0',
    'lesion 0 | unk:~ | - | - | -',
    'lesion 0 | unk:~ | sup:L1 | - | -',
    'lesion 0 | unk:~ | sup:L1 | - | E1:L1:1 E2:L2:1',
    'lesion 0 | unk:~ | sup:L1 | L1=sup:L2 | E2:L3:1',
    'lesion 0 | unk:~ | unk:~ | - | -',
    'lesion 0 | unk:~ | unr:L1 | L1=sup:L2 | E2:L3:0',
    'lesion 0 | unk:~ | unr:L1 | L1=sup:L2,sup:L3 | E2:L2:0',
    'lesion 0 | unr:L1 | - | - | -',
    'lesion 0 | unr:L1 | - | - | E1:L2:1',
    'lesion 0 | unr:L1 | - | L1=sup:L2 | E1:L2:1',
    'lesion 0 | unr:L1 | sup:L1 | - | -',
    'lesion 0 | unr:L1 | sup:L2 | - | E1:L2:0 E2:L1:0',
    'lesion 0 | unr:L1 | sup:L2 | L1=sup:L2 | E1:L2:1 E2:L1:1',
    'lesion 0 | unr:L1 | sup:L2 | L2=sup:L1 | E1:L2:1 E2:L1:1',
    'lesion 0 | unr:L1 | unk:L2 | L1=sup:L3 L2=sup:L3 | E1:L3:0 E2:L1:1',
    'lesion 1 | sup:L1 | sup:L2 | L1=sup:L2 | E1:L2:1 E2:L1:1',
    'lesion 1 | sup:L1 | sup:L2 | L1=sup:L2 | E1:L2:1 E2:L1:1 E2:L3:1',
    'lesion 1 | sup:L1 | sup:L2 | L2=sup:L1 | E1:L2:1 E2:L1:1',
    'place 0 | - | - | -',
    'place 0 | - | - | E1:anastomosis:0',
    'place 0 | - | - | E1:cecum:1',
    'place 0 | - | - | E1:transverse_colon:1',
    'place 0 | - | con:~ sup:sigmoid_colon | E2:ascending_colon:0 E2:cecum:0',
    'place 0 | - | con:~ | -',
    'place 0 | - | sup:cecum | -',
    'place 0 | - | sup:cecum | E1:cecum:1 E2:rectum:1',
    'place 0 | - | sup:rectum | -',
    'place 0 | - | sup:sigmoid_colon | -',
    'place 0 | - | sup:sigmoid_colon | E1:sigmoid_colon:1 E2:rectum:1',
    'place 0 | - | sup:stomach | -',
    'place 0 | - | sup:transverse_colon | E1:transverse_colon:1 E2:sigmoid_colon:1',
    'place 0 | - | unk:cecum unk:hepatic_flexure | -',
    'place 0 | - | unk:~ | -',
    'place 0 | - | unr:anastomosis unk:~ | E1:anastomosis:0 E2:rectum:0',
    'place 0 | - | unr:anastomosis unk:~ | E2:ascending_colon:0 E2:rectum:0',
    'place 0 | - | unr:anastomosis unk:~ | E2:rectum:0',
    'place 0 | - | unr:hepatic_flexure | -',
    'place 0 | - | unr:hepatic_flexure | E2:ascending_colon:0',
    'place 0 | con:~ sup:colon | - | -',
    'place 0 | con:~ sup:colon | con:~ sup:colon | -',
    'place 0 | con:~ sup:colon | unk:~ | -',
    'place 0 | con:~ sup:colon | unk:~ | E1:rectum:1',
    'place 0 | con:~ sup:sigmoid_colon | - | E1:ascending_colon:0 E1:cecum:0',
    'place 0 | con:~ unk:sigmoid_colon | unk:~ sup:sigmoid_colon | E1:ascending_colon:0 E1:rectum:0 '
    'E2:ascending_colon:1 E2:cecum:1 E2:rectum:0',
    'place 0 | con:~ unr:sigmoid_colon | - | E1:hepatic_flexure:0',
    'place 0 | con:~ unr:sigmoid_colon | con:~ sup:sigmoid_colon | E1:hepatic_flexure:0 E2:ascending_colon:0 '
    'E2:cecum:0',
    'place 0 | con:~ | - | -',
    'place 0 | con:~ | neg:ascending_colon unk:anastomosis | -',
    'place 0 | con:~ | sup:sigmoid_colon | E1:sigmoid_colon:1 E2:rectum:1',
    'place 0 | con:~ | unk:anastomosis | E1:anastomosis:0 E2:ascending_colon:0',
    'place 0 | con:~ | unk:colon | -',
    'place 0 | neg:colon | sup:sigmoid_colon sup:sigmoid_colon | E1:sigmoid_colon:1 E2:hepatic_flexure:0',
    'place 0 | sup:cecum | - | -',
    'place 0 | sup:cecum | sup:cecum | -',
    'place 0 | sup:colon | sup:cecum | E1:cecum:1 E2:colon:1',
    'place 0 | sup:other | sup:rectum | E1:rectum:1 E2:other:1',
    'place 0 | sup:rectum | - | -',
    'place 0 | sup:rectum | - | E1:cecum:0',
    'place 0 | sup:rectum | - | E1:cecum:1',
    'place 0 | sup:rectum | - | E1:cecum:1 E2:rectum:1',
    'place 0 | sup:rectum | con:~ | -',
    'place 0 | sup:rectum | con:~ | E1:sigmoid_colon:1 E2:rectum:1',
    'place 0 | sup:rectum | sup:anastomosis | E1:anastomosis:1 E2:rectum:1',
    'place 0 | sup:rectum | sup:cecum | -',
    'place 0 | sup:rectum | sup:cecum | E1:cecum:0 E2:rectum:1',
    'place 0 | sup:rectum | sup:cecum | E1:cecum:1 E2:rectum:0',
    'place 0 | sup:rectum | sup:sigmoid_colon sup:rectum | E1:rectum:1 E1:sigmoid_colon:1 E2:rectum:1',
    'place 0 | sup:rectum | sup:sigmoid_colon | -',
    'place 0 | sup:rectum | sup:sigmoid_colon | E1:sigmoid_colon:0 E2:rectum:1',
    'place 0 | sup:rectum | sup:sigmoid_colon | E1:sigmoid_colon:1',
    'place 0 | sup:rectum | sup:sigmoid_colon | E1:sigmoid_colon:1 E2:rectum:0',
    'place 0 | sup:rectum | sup:sigmoid_colon | E2:rectum:1',
    'place 0 | sup:rectum | sup:transverse_colon | E1:transverse_colon:1 E2:rectum:0',
    'place 0 | sup:rectum | unk:cecum | E1:cecum:1 E2:rectum:1',
    'place 0 | sup:rectum | unk:sigmoid_colon | -',
    'place 0 | sup:rectum | unk:sigmoid_colon | E1:sigmoid_colon:1 E2:rectum:1',
    'place 0 | sup:rectum | unk:~ | E1:sigmoid_colon:1 E2:rectum:1',
    'place 0 | sup:rectum | unr:cecum | E1:cecum:1 E2:rectum:1',
    'place 0 | sup:rectum | unr:sigmoid_colon | -',
    'place 0 | sup:rectum | unr:sigmoid_colon | E1:sigmoid_colon:1 E2:rectum:1',
    'place 0 | sup:sigmoid_colon | - | E1:transverse_colon:1',
    'place 0 | sup:sigmoid_colon | sup:colon | E1:colon:1 E2:sigmoid_colon:1',
    'place 0 | sup:sigmoid_colon | sup:sigmoid_colon | -',
    'place 0 | sup:stomach | - | -',
    'place 0 | sup:transverse_colon | - | E1:sigmoid_colon:1',
    'place 0 | sup:transverse_colon | - | E1:sigmoid_colon:1 E2:transverse_colon:1',
    'place 0 | unk:cecum | - | -',
    'place 0 | unk:rectum | - | E1:cecum:1',
    'place 0 | unk:rectum | sup:cecum | E1:cecum:1 E2:rectum:1',
    'place 0 | unk:rectum | sup:sigmoid_colon | E1:sigmoid_colon:1 E2:rectum:1',
    'place 0 | unk:~ unk:colon | unk:~ sup:sigmoid_colon | E2:ascending_colon:1 E2:cecum:1 E2:rectum:0',
    'place 0 | unk:~ | - | -',
    'place 0 | unk:~ | con:~ sup:colon | -',
    'place 0 | unk:~ | con:~ sup:colon | E2:rectum:1',
    'place 0 | unk:~ | sup:sigmoid_colon | E1:sigmoid_colon:1 E2:rectum:1',
    'place 0 | unk:~ | unk:~ | -',
    'place 0 | unr:anastomosis unk:~ | - | E1:ascending_colon:0 E1:rectum:0',
    'place 0 | unr:anastomosis unk:~ | - | E1:rectum:0',
    'place 0 | unr:cecum unr:hepatic_flexure | unk:~ | E1:rectum:1 E1:sigmoid_colon:0 E2:cecum:0 E2:hepatic_flexure:1',
    'place 0 | unr:cecum unr:hepatic_flexure | unr:colon | E1:rectum:1 E1:sigmoid_colon:0 E2:rectum:0',
    'place 0 | unr:cecum | - | -',
    'place 0 | unr:colon | unr:cecum unr:hepatic_flexure | E1:rectum:0 E2:rectum:1 E2:sigmoid_colon:0',
    'place 0 | unr:hepatic_flexure | - | -',
    'place 0 | unr:hepatic_flexure | - | E1:ascending_colon:0',
    'place 0 | unr:rectum | - | E1:cecum:1',
    'place 0 | unr:rectum | sup:cecum | E1:cecum:1 E2:rectum:1',
    'place 0 | unr:rectum | sup:sigmoid_colon | -',
    'place 0 | unr:rectum | sup:sigmoid_colon | E1:sigmoid_colon:1 E2:rectum:1',
    'place 0 | unr:sigmoid_colon | sup:sigmoid_colon sup:sigmoid_colon | E1:ascending_colon:1 E1:hepatic_flexure:0 '
    'E2:hepatic_flexure:0',
    'place 0 | unr:sigmoid_colon | sup:sigmoid_colon | -',
    'place 1 | sup:rectum | sup:cecum | E1:cecum:1 E2:rectum:1',
    'place 1 | sup:rectum | sup:sigmoid_colon | E1:sigmoid_colon:1 E2:rectum:1',
    'place 1 | sup:rectum | sup:transverse_colon | E1:transverse_colon:1 E2:rectum:1',
    'place 1 | sup:sigmoid_colon | sup:transverse_colon | E1:transverse_colon:1 E2:sigmoid_colon:1',
    'place 1 | sup:transverse_colon | sup:sigmoid_colon | E1:sigmoid_colon:1 E2:transverse_colon:1',
)


_RESULTS = {'sup': ct.Result.SUPPORTED, 'neg': ct.Result.NEGATED, 'unr': ct.Result.UNRESOLVED,
            'con': ct.Result.CONTRADICTED, 'unk': ct.Result.UNKNOWN}
_STATES = {ct.Result.SUPPORTED: ct.FactState.SUPPORTED, ct.Result.NEGATED: ct.FactState.NEGATED,
           ct.Result.CONTRADICTED: ct.FactState.CONTRADICTED}


def fixture_case(line) -> tuple:
    """One line of FIXTURE_CALLS: (the predicate, 'place' or 'lesion'; the answer recorded at the base; the FactSet, the
    two objects E1 and E2). Each member gets the state every recorded member of its result and value had: supported,
    negated or contradicted for those results; supported for an unresolved or unknown member with a value; none (a
    silent slot) for an unknown member without one."""
    head, *fields = line.split(' | ')
    name, answer = head.split()
    attribute = PLACES if name == 'place' else LESION

    def value(token):
        return None if token == '~' else LM(token) if attribute is PLACES else Id.parse(token)

    def facts(field, separator=' '):
        found = []
        for token in [] if field == '-' else field.split(separator):
            result, raw = token.split(':')
            member = value(raw)
            state = _STATES.get(_RESULTS[result], ct.FactState.SUPPORTED if member is not None else None)
            found.append(plain(_RESULTS[result], member, state))
        return tuple(found)

    events = {E1: {attribute: facts(fields[0])}, E2: {attribute: facts(fields[1])}}
    lesions = {}
    if attribute is LESION and fields[2] != '-':
        for entry in fields[2].split():
            named, listed = entry.split('=')
            lesions[Id.parse(named)] = {A.DISTINCT_FROM: facts(listed, ',')}
    controls = {}
    for token in [] if fields[-1] == '-' else fields[-1].split():
        asked, raw, rejected = token.split(':')
        controls[(Id.parse(asked), attribute, value(raw))] = rejected == '1'
    return name, answer == '1', scene(events, lesions=lesions, controls=controls)


def fixture_replay() -> tuple:
    """Replays FIXTURE_CALLS: (how many lines; every line on which apart_by_place or apart_by_lesion, or 4.2's reading
    before D220 - before_place, before_lesion - does not answer as recorded at the base, with the two answers)."""
    changed = []
    for line in FIXTURE_CALLS:
        name, answer, R = fixture_case(line)
        now = (F.apart_by_place if name == 'place' else F.apart_by_lesion)(R, E1, E2)
        was = (before_place if name == 'place' else before_lesion)(R, E1, E2)
        if now is not answer or was is not answer:
            changed.append((line, now, was))
    return len(FIXTURE_CALLS), changed


# The places the generated scenes draw from: colonic and upper, one place containing another (left colon, sigmoid
# colon; stomach, gastric body), two that overlap without either containing the other (esophagus, stomach) and an
# altered place (anastomosis), which engine/anatomy calls neither compatible nor disjoint with anything placed.
POOL = (LM.CECUM, LM.ASCENDING_COLON, LM.TRANSVERSE_COLON, LM.SIGMOID_COLON, LM.RECTUM, LM.LEFT_COLON, LM.ESOPHAGUS,
        LM.STOMACH, LM.GASTRIC_BODY, LM.DUODENUM, LM.ANASTOMOSIS)


def generated(rnd) -> FactSet:
    """A settled scene: 2-4 events with 1-3 supported target places and a target lesion or none; lesions with
    distinct_from; the pair controls contract/claims.pair() makes from the FULL lists - each event asked about every
    place of every other event that none of its own places is compatible with, and about the other's lesion when they
    differ - each rejected or not at random (one claim per question: asked for two events, it is one control)."""
    ids = [Id(IdFamily.EVENT, number) for number in range(1, rnd.randint(3, 5))]
    events = {event: placed(*rnd.sample(POOL, rnd.randint(1, 3)), lesion=rnd.choice((None, L1, L2, L3)))
              for event in ids}
    lesions = {lesion: {A.DISTINCT_FROM: tuple(sup(other) for other in (L1, L2, L3)
                                               if other != lesion and rnd.random() < 0.6)}
               for lesion in (L1, L2, L3)}
    controls = {}
    for asked in ids:
        own = [member.value for member in events[asked][PLACES]]
        mine = events[asked][LESION][0].value
        for other in ids:
            if other == asked:
                continue
            for member in events[other][PLACES]:
                if not any(anatomy.compatible(member.value, place) for place in own):
                    controls.setdefault((asked, PLACES, member.value), rnd.random() < 0.75)
            theirs = events[other][LESION][0].value
            if mine is not None and theirs is not None and mine != theirs:
                controls.setdefault((asked, LESION, theirs), rnd.random() < 0.75)
    return scene(events, lesions=lesions, controls=controls)


def weakenings(R):
    """9.4's weakenings of ``R``, one at a time: (a description, the weakened FactSet)."""
    for subject, facts in R.events.items():
        members = facts[PLACES]
        for index, member in enumerate(members):
            if len(members) >= 2:  # a deleted member: the list stays a list
                yield ('delete', subject, index), deleted(R, subject, index)
            for name, weaker in (('unresolved', unresolved(member.value)), ('doubted', doubted(member.value))):
                yield (name, subject, index), replaced(R, subject, PLACES,
                                                       members[:index] + (weaker,) + members[index + 1:])
        lesion = facts[LESION][0]
        if lesion.result is ct.Result.SUPPORTED:
            yield ('unresolved lesion', subject, 0), replaced(R, subject, LESION, (unresolved(lesion.value),))
    for subject, facts in R.lesions.items():
        members = facts[A.DISTINCT_FROM]
        for index, member in enumerate(members):
            yield ('delete distinct_from', subject, index), deleted(R, subject, index, A.DISTINCT_FROM)
            yield ('unresolved distinct_from', subject, index), replaced(
                R, subject, A.DISTINCT_FROM, members[:index] + (unresolved(member.value),) + members[index + 1:])
    for key, rejected in R.pair_controls.items():
        if rejected:
            yield ('not rejected', key, 0), scene(R.events, lesions=R.lesions, controls={**R.pair_controls, key: False})


def overlap_release(R, weakening, x, y) -> bool:
    """The one release P-MONO names (repair r2d's question Q2): ``weakening`` deletes a place X of x or y that overlaps
    a place p of the other without being compatible with it (neither compatible nor disjoint: the only bar to apartness
    X raised), and the control asking the other object about X was REJECTED."""
    kind, subject, index = weakening
    if kind != 'delete' or subject not in (x, y) or not isinstance(subject, Id) or subject.family is not IdFamily.EVENT:
        return False
    other = y if subject == x else x
    place = R.events[subject][PLACES][index].value
    overlaps = any(not anatomy.compatible(place, member.value) and not anatomy.disjoint(place, member.value)
                   for member in R.events[other][PLACES])
    return overlaps and R.pair_controls.get((other, PLACES, place)) is True


# --- DECISIONS D244 Q-N1 option (b): a session fact K3 demoted (repair r2d) -------------------------------------------

X3, X4, X5 = (Id(IdFamily.SESSION, n) for n in range(3, 6))


def unreachable(value, sources) -> dict:
    """A session fact K3 demoted, as settle stores it (6c's N1 (ii)): its claim kept, no claim made for it and no
    appraisal, the consistency check failed, unresolved with session_unreachable."""
    record = fact(value, sources, reasons=('session_unreachable',))
    record['checks'] = {**checks(), 'consistency': 'failed'}
    return record


def k3_row(*, places=('gastric_body',), readings=()) -> dict:
    """A synthetic settled row on TEXT's units (cited for their offsets only: the builder reads no text) in the shapes
    question Q-N1 reads: an EGD X1, a push enteroscopy X2, a colonoscopy X3, an upper EUS X4 (a family K3's reach
    table does not list, DECISIONS D192) and X5, whose kind pass 2 left between a colonoscopy and a sigmoidoscopy (its
    control flex_sig not rejected); E3, a polypectomy at ``places`` (each supported) whose session claim X2 K3 demoted
    (session_unreachable: the stomach lies outside an enteroscopy's reach), with a session doubt of ``readings`` when
    given; E4, a biopsy at the gastric body whose session claim X2 pass 2 left unclear (no K3 finding)."""
    k = Ledger()
    frame = lambda: src(['S1'], 'document_frame')  # noqa: E731
    sessions = [session('X1', kind=est(k, 'X1', 'kind', 'egd', [frame()])),
                session('X2', kind=est(k, 'X2', 'kind', 'enteroscopy', [frame()])),
                session('X3', kind=est(k, 'X3', 'kind', 'colonoscopy', [frame()])),
                session('X4', kind=est(k, 'X4', 'kind', 'eus', [frame()])),
                session('X5', kind=unsettled(k, 'X5', 'kind', 'colonoscopy', [frame()], control='flex_sig'))]
    events = [
        event('E3', ['S6'], kind=est(k, 'E3', 'kind', 'removal', [src(['S6'])]),
              status=est(k, 'E3', 'status', 'performed', [src(['S6'])]), session=unreachable('X2', [src(['S6'])]),
              target={'places': [est(k, 'E3', 'target.places', place, [src(['S6'])]) for place in places]}),
        event('E4', ['S11'], kind=est(k, 'E4', 'kind', 'biopsy', [src(['S11'])]),
              status=est(k, 'E4', 'status', 'performed', [src(['S11'])]),
              session=unsettled(k, 'E4', 'session', 'X2', [src(['S11'])]),
              target={'places': [est(k, 'E4', 'target.places', 'gastric_body', [src(['S11'])])]}),
    ]
    doubts = [{'about': 'session', 'objects': ['E3'], 'units': ['S6'], 'basis': 'unclear',
               'readings': list(readings)}] if readings else []
    return content(k, sessions=sessions, events=events, doubts=doubts)


class K3SessionTests(SimpleTestCase):
    """DECISIONS D244, question Q-N1 option (b): a session fact K3 demoted (session_unreachable) is possibly any session
    whose reach holds the act's place, not its claimed session alone - in facts.possibly, through the fact's options,
    which every rule reading the session fact reads too."""

    def test_a_k3_demoted_session_is_possibly_every_session_whose_reach_holds_the_place(self):
        from studio.interpretation.engine import combination as CB
        from studio.interpretation.engine import coverage as C

        row = view(k3_row())
        for name, R in (('factset', F.factset(row)), ('effective', F.effective(row, '2026-11-09'))):
            found = F.fact(R, E3, A.SESSION)
            with self.subTest(name):
                self.assertEqual((found.result, found.value, found.reasons),
                                 (ct.Result.UNRESOLVED, X2, (ct.Reason.SESSION_UNREACHABLE,)))
                # the EGD's reach holds the stomach; the EUS is a family K3 does not judge (it never demotes there)
                self.assertEqual(found.options, (X1, X4))
                self.assertEqual({session: F.possibly(found, session) for session in (X1, X2, X3, X4, X5)},
                                 {X1: True, X2: True, X3: False, X4: True, X5: False})
                # every rule reading the session fact's options reads the same sessions
                self.assertEqual(CB.possible_sessions(R, E3), (X2, X1, X4))
                self.assertEqual(C.sessions_of(R, E3), frozenset({X1, X2, X4}))
                # a session fact pass 2 left unresolved without a K3 finding is read as before: its claim alone
                other = F.fact(R, E4, A.SESSION)
                self.assertEqual((other.result, other.options), (ct.Result.UNRESOLVED, ()))
                self.assertFalse(F.possibly(other, X1))

    def test_its_own_options_come_first_and_the_claimed_session_stays_possible(self):
        # a session doubt naming E3 (reading the colonoscopy X3) is kept as the fact's own option, first; the K3
        # widening adds the sessions it does not already name, in pass 1's order: it never narrows what was possible
        found = F.fact(F.factset(view(k3_row(readings=('X3',)))), E3, A.SESSION)
        self.assertEqual(found.options, (X3, X1, X4))
        self.assertTrue(F.possibly(found, X2))

    def test_each_place_the_act_may_be_at_is_read(self):
        # any place of the act: a jejunal place is held by a colonoscopy's reach too (D192: the small bowel beyond the
        # valve), so the colonoscopy X3 and X5 (possibly a colonoscopy) join; a place in no region (an anastomosis) is
        # judged by no reach, so every session's reach may hold it
        for places in (('gastric_body', 'jejunum'), ('gastric_body', 'anastomosis')):
            with self.subTest(places=places):
                found = F.fact(F.factset(view(k3_row(places=places))), E3, A.SESSION)
                self.assertEqual(found.options, (X1, X3, X4, X5))
        # no place known (an empty list is unknown, never an absence, P3): every session's reach may hold it
        self.assertEqual(F.fact(F.factset(view(k3_row(places=()))), E3, A.SESSION).options, (X1, X3, X4, X5))

    def test_the_places_an_act_may_be_at_and_the_families_a_session_may_be_of(self):
        S = ct.SessionKind
        doubted_place = Fact(result=ct.Result.UNKNOWN, value=LM.STOMACH, state=ct.FactState.SUPPORTED,
                             options=(LM.DUODENUM,), reasons=(ct.Reason.DOUBT_UNCLEAR,), spans=())
        # a supported member's value, an open member's value and options; a negated member names none
        self.assertEqual(F._places((sup(LM.GASTRIC_BODY), neg(LM.CECUM), unresolved(LM.JEJUNUM), doubted_place)),
                         (LM.GASTRIC_BODY, LM.JEJUNUM, LM.STOMACH, LM.DUODENUM))
        # no place known: no member, negated members only, or a member that is not negated and names none
        for members in ((), (neg(LM.STOMACH),), (sup(LM.STOMACH), plain(ct.Result.UNKNOWN, None, None))):
            with self.subTest(members=members):
                self.assertIsNone(F._places(members))
        # a session's families: its supported kind; every other when negated; possibly's otherwise
        self.assertEqual(F._families(sup(S.EGD)), frozenset({S.EGD}))
        self.assertEqual(F._families(neg(S.EGD)), frozenset(S) - {S.EGD})
        self.assertEqual(F._families(unresolved(S.COLONOSCOPY)), frozenset({S.COLONOSCOPY}))
        self.assertEqual(F._families(F.SILENT), frozenset(S))

    def test_the_reach_is_k3s(self):
        # K3's reach (DECISIONS D192): catalogue.FAMILY_REACH against engine/anatomy.region; a family it does not list
        # and a place in no region are judged by no reach
        S, LM_ = ct.SessionKind, ct.Landmark
        rows = {(S.EGD, LM_.GASTRIC_BODY): True, (S.ENTEROSCOPY, LM_.GASTRIC_BODY): False,
                (S.COLONOSCOPY, LM_.GASTRIC_BODY): False, (S.FLEX_SIG, LM_.JEJUNUM): False,
                (S.COLONOSCOPY, LM_.JEJUNUM): True, (S.ENTEROSCOPY, LM_.JEJUNUM): True, (S.EGD, LM_.AMPULLA): False,
                (S.EUS, LM_.GASTRIC_BODY): True, (S.ERCP, LM_.CECUM): True, (S.EGD, LM_.ANASTOMOSIS): True}
        self.assertEqual({key: F._reach_holds(*key) for key in rows}, rows)
        from studio.interpretation.engine import catalogue
        for family in S:
            for place in LM_:
                region, reach = anatomy.region(place), catalogue.FAMILY_REACH.get(family)
                with self.subTest(family=family, place=place):
                    self.assertIs(F._reach_holds(family, place), region is None or reach is None or region in reach)

    def test_n1_ii_and_iii_hold_43235_base_included(self):
        # 6c's N1 (S4's class; the step's NOTES question Q-N1): "EGD ...; push enteroscopy ...; on withdrawal, a
        # polypectomy of a 7 mm gastric body polyp was performed." filed in the enteroscopy X2 (misfiled), caught by K3
        # in (ii) and (iii) alike (a deterministic check): the polypectomy may be the EGD's, so the EGD's base code
        # 43235 is held base_included with a question, as (i) documents - never READY
        from tests.v2 import test_failure_classes as FC

        wanted = ('needs_clarification', 'base_included', 'question')
        for variant in ('i', 'ii', 'iii'):
            run = FC.run('N1', variant)
            found = FC.outcomes(run.assessment)['43235']
            with self.subTest(variant=variant):
                self.assertEqual((found['status'], found['item'], found['item_kind']), wanted)
                self.assertTrue(F.possibly(F.fact(run.R, E3, A.SESSION), X1))  # the EGD's session
        # the positive control: without the widening, (ii) and (iii) read the claimed session alone: 43235 READY
        with mock.patch.object(F, '_k3_widened', lambda sessions, held, overfilled=False: held):
            for variant in ('ii', 'iii'):
                run = FC.run.__wrapped__('N1', variant)
                with self.subTest(variant=variant, widening='off'):
                    self.assertEqual(FC.outcomes(run.assessment)['43235']['status'], 'ready')
                    self.assertFalse(F.possibly(F.fact(run.R, E3, A.SESSION), X1))


# --- AMENDMENT-2 4.3.3: an overfilled slot read as one merged view; DECISIONS D287's established_kind ---------------


def written_fact(state: str, value: str, units=('S5',), *, options=(), reasons=('slot_overfull',)) -> dict:
    """One written fact of an overfilled slot as store.textfree_v2 gives it (AMENDMENT-2 4.3.1, 4.3.6): its claim as
    pass 1 wrote it, never claimed (no appraisal), unresolved for slot_overfull."""
    return {'claim': claim(state, value, options=options), 'sources': [{'units': list(units), 'link': 'statement',
                                                                         'at': None, 'geometry': 'ok'}],
            'checks': checks(), 'appraisal': None, 'result': 'unresolved', 'reasons': list(reasons)}


def planted(view_: typing.Mapping, family, subject: str, attribute, facts: list) -> dict:
    """``view_`` (a text-free view) with ``subject``'s single-valued ``attribute`` an overfilled slot holding ``facts``:
    a list at the slot's key, as store.py stores one for a gemini-inventory@3 row (4.3.6)."""
    events = json.loads(json.dumps(view_))
    record = events['encounter'] if family is None else next(
        item for item in events[TABLE_OF[family]] if item['id'] == subject)
    *path, key = attribute.value.split('.')
    for name in path:
        record = record[name]
    record[key] = facts
    return events


TABLE_OF = {IdFamily.PERSON: 'people', IdFamily.SECTION: 'sections', IdFamily.SESSION: 'sessions',
            IdFamily.ANATOMY: 'anatomy', IdFamily.LESION: 'lesions', IdFamily.EVENT: 'events'}
SUBJECTS = {None: '', IdFamily.PERSON: 'P1', IdFamily.SECTION: 'N1', IdFamily.SESSION: 'X1', IdFamily.ANATOMY: 'Y1',
            IdFamily.LESION: 'L1', IdFamily.EVENT: 'E2'}


def three_values(family, attribute) -> list:
    """Three distinct values of the attribute's domain, as pass 1 writes them (facts.DOMAINS)."""
    domain = F.DOMAINS[(family, attribute)]
    if domain.enum is not None:
        found = [member.value for member in list(domain.enum)[:3]]
        return found + found[-1:] * (3 - len(found))  # a two-member domain writes its second value twice
    if domain.family is not None:
        return [f'{domain.family.value}{number}' for number in (1, 2, 3)]
    return ['2026-11-09', '2026-11-08', '2026-11-07']


def parsed(family, attribute, raw: str):
    return F._value(raw, F.DOMAINS[(family, attribute)], 'a test value')


class OverfilledSlotTests(SimpleTestCase):
    """AMENDMENT-2 4.3.3 and 4.4 [R:truth-T1][R:truth-T2][R:truth-T5][R:truth-T9], the FactSet's half of the plant test:
    on EACH of the 38 slot attributes, an overfilled slot - supported values only (A-v6's shape), one supported value
    beside negated others (A-v2's), negated values only - is read as ONE Fact: unresolved, value None, state contradicted,
    reason slot_overfull alone, the written values its options in written order (never a value pass 1 did not write,
    never the domain), the denied ones its negated_values; never silent and never established, so nothing derived from
    the slot is. The store's acceptance of such a row (4.3.6) is step f3s's; these rows are the text-free view as it gives
    one."""

    def test_the_slots_are_the_answers_38_slot_attributes(self):
        from studio.interpretation.contract import extract_schema as XS

        families = {XS.Family.ENCOUNTER: None, XS.Family.PERSON: IdFamily.PERSON, XS.Family.SECTION: IdFamily.SECTION,
                    XS.Family.SESSION: IdFamily.SESSION, XS.Family.ANATOMY: IdFamily.ANATOMY,
                    XS.Family.LESION: IdFamily.LESION, XS.Family.EVENT: IdFamily.EVENT}
        slots = {(families[family], field_.attribute) for family, fields_ in XS.ATTRIBUTES.items() for field_ in fields_
                 if field_.arity is XS.Arity.SLOT}
        self.assertEqual(len(slots), 38)
        self.assertEqual(F.SLOTS, slots)
        self.assertEqual(F.REQUIRED_FACTS & F.SLOTS, frozenset())

    def test_every_slot_attribute_in_every_shape_is_one_merged_view(self):
        base = view(colonoscopy())
        checked = 0
        for family, attribute in sorted(F.SLOTS, key=lambda key: (str(key[0]), key[1].value)):
            v1, v2, v3 = three_values(family, attribute)
            subject = SUBJECTS[family]
            for shape, written in (('supported only (A-v6)', [('supported', v1), ('supported', v2)]),
                                   ('one supported, others negated (A-v2)',
                                    [('supported', v1), ('negated', v2), ('negated', v3)]),
                                   ('negated only', [('negated', v1), ('negated', v2)])):
                with self.subTest(attribute=attribute.value, family=family, shape=shape):
                    facts = [written_fact(state, value, units=(f'S{index + 5}',))
                             for index, (state, value) in enumerate(written)]
                    R = F.factset(planted(base, family, subject, attribute, facts))
                    found = F.fact(R, None if family is None else Id.parse(subject), attribute)
                    values = tuple(dict.fromkeys(parsed(family, attribute, value) for _state, value in written))
                    stated = {parsed(family, attribute, value) for state, value in written if state != 'negated'}
                    denied = tuple(dict.fromkeys(parsed(family, attribute, value) for state, value in written
                                                 if state == 'negated' and parsed(family, attribute, value)
                                                 not in stated))
                    self.assertEqual((found.result, found.value, found.state, found.reasons),
                                     (ct.Result.UNRESOLVED, None, ct.FactState.CONTRADICTED,
                                      (ct.Reason.SLOT_OVERFULL,)))
                    self.assertEqual((found.options, found.negated_values), (values, denied))
                    self.assertEqual(found.spans, tuple(unit_span(index + 5) for index in range(len(written))))
                    self.assertEqual(len(found.cited), len(written))
                    self.assertTrue(F.overfilled(found))
                    self.assertTrue(F.open_denial(found))  # 4.3.3 a, read fail-closed (the step's NOTES, Q1R)
                    self.assertFalse(F.silent(found) or F.established(found))
                    self.assertFalse(any(F.holds(found, value) or F.denied(found, value) for value in values))
                    self.assertTrue(all(F.possibly(found, value) for value in values))  # 4.3.3 a: every written value
                    self.assertEqual(F.claimed_values(found), tuple(value for value in values if value not in denied))
                    checked += 1
        self.assertEqual(checked, 38 * 3)

    def test_the_view_carries_only_written_values_and_reads_like_test_combination_builds_it(self):
        """The options are the written values - a written contradiction's sides among them - then what each written
        fact read alone leaves possible besides (a doubt naming the object); a value written both supported and negated
        is stated, never in negated_values (the fail-closed reading for the claimed-value readers, this step's NOTES
        question Q1), and so is a denied value a doubt offers (question Q1R: the written fact the doubt names, read
        alone, leaves it possible); and the builder's view equals the form tests/v2/test_combination.overfilled builds."""
        from tests.v2 import test_combination as TC

        base = view(colonoscopy())
        both = F.factset(planted(base, IdFamily.EVENT, 'E2', A.TECHNIQUE_DEVICE, [
            written_fact('supported', 'manual'), written_fact('negated', 'manual'),
            written_fact('negated', 'hot_snare')]))
        device = F.fact(both, E2, A.TECHNIQUE_DEVICE)
        self.assertEqual((device.options, device.negated_values),
                         ((ct.Device.MANUAL, ct.Device.HOT_SNARE), (ct.Device.HOT_SNARE,)))
        self.assertEqual(device, dataclasses.replace(
            TC.overfilled((ct.FactState.SUPPORTED, ct.Device.MANUAL), (ct.FactState.NEGATED, ct.Device.MANUAL),
                          (ct.FactState.NEGATED, ct.Device.HOT_SNARE)), spans=device.spans, cited=device.cited))
        sides = F.factset(planted(base, IdFamily.EVENT, 'E2', A.TECHNIQUE_DEVICE, [
            written_fact('contradicted', '', options=[{'value': 'cold_snare', 'sources': []},
                                                      {'value': 'hot_snare', 'sources': []}]),
            written_fact('supported', 'endoscope')]))
        self.assertEqual(F.fact(sides, E2, A.TECHNIQUE_DEVICE).options,
                         (ct.Device.COLD_SNARE, ct.Device.HOT_SNARE, ct.Device.ENDOSCOPE))
        doubted_ = F.factset(planted(base, IdFamily.EVENT, 'E3', A.PERFORMER, [
            written_fact('supported', 'documenting_team'), written_fact('supported', 'other_clinician')]))
        performer = F.fact(doubted_, E3, A.PERFORMER)  # the colonoscopy's doubt names E3's performer
        self.assertEqual(performer.options, (ct.Performer.DOCUMENTING_TEAM, ct.Performer.OTHER_CLINICIAN,
                                             ct.Performer.OTHER_FACILITY))  # the written values, then the reading
        plain_device = F.fact(F.factset(planted(base, IdFamily.EVENT, 'E2', A.TECHNIQUE_DEVICE, [
            written_fact('supported', 'endoscope'), written_fact('supported', 'endoscope')])), E2, A.TECHNIQUE_DEVICE)
        self.assertEqual(plain_device.options, (ct.Device.ENDOSCOPE,))  # never a value nobody wrote, never the domain
        offered = F.fact(F.factset(planted(base, IdFamily.EVENT, 'E3', A.PERFORMER, [
            written_fact('supported', 'other_clinician'), written_fact('negated', 'other_facility')])), E3, A.PERFORMER)
        # the colonoscopy's doubt names E3's performer and reads documenting_team and other_facility: other_facility,
        # denied by a written fact, is offered by the doubt, so it is not only denied (as built, it was negated_values')
        self.assertEqual((offered.options, offered.negated_values),
                         ((ct.Performer.OTHER_CLINICIAN, ct.Performer.OTHER_FACILITY, ct.Performer.DOCUMENTING_TEAM), ()))
        self.assertEqual(F.claimed_values(offered), offered.options)
        self.assertEqual(offered, dataclasses.replace(
            TC.overfilled((ct.FactState.SUPPORTED, ct.Performer.OTHER_CLINICIAN),
                          (ct.FactState.NEGATED, ct.Performer.OTHER_FACILITY),
                          readings=(ct.Performer.DOCUMENTING_TEAM, ct.Performer.OTHER_FACILITY)),
            spans=offered.spans, cited=offered.cited))

    def test_a_list_the_slot_rule_does_not_make_is_refused(self):
        base = view(colonoscopy())
        for name, family, subject, attribute, facts in (
                ('one fact in a list', IdFamily.EVENT, 'E2', A.TECHNIQUE_DEVICE, [written_fact('supported', 'manual')]),
                ('a fact without slot_overfull', IdFamily.EVENT, 'E2', A.TECHNIQUE_DEVICE,
                 [written_fact('supported', 'manual'), written_fact('supported', 'endoscope', reasons=('unappraised',))]),
                ('a required fact (kind)', IdFamily.EVENT, 'E2', A.KIND,
                 [written_fact('supported', 'snare'), written_fact('supported', 'biopsy')]),
                ('a required fact (status)', IdFamily.EVENT, 'E2', A.STATUS,
                 [written_fact('supported', 'performed'), written_fact('supported', 'planned')]),
                ('a value outside the domain', IdFamily.EVENT, 'E2', A.TECHNIQUE_DEVICE,
                 [written_fact('supported', 'manual'), written_fact('supported', 'lasso')])):
            with self.subTest(name), self.assertRaises(F.FactSetError):
                F.factset(planted(base, family, subject, attribute, facts))

    def test_a_written_fact_k3_demoted_keeps_the_merged_session_widened(self):
        """4.4's property for the K3 reader: an overfilled session slot one of whose written facts carries
        session_unreachable is widened as that fact alone would be (DECISIONS D244 Q-N1), never narrower; without the
        finding it reads its written sessions only."""
        def row(reasons):
            base = json.loads(json.dumps(view(k3_row())))
            event_ = next(item for item in base['events'] if item['id'] == 'E3')
            event_['session'] = [written_fact('supported', 'X2', units=('S6',), reasons=reasons),
                                 written_fact('supported', 'X5', units=('S6',))]
            return F.factset(base)

        widened = F.fact(row(('slot_overfull', 'session_unreachable')), E3, A.SESSION)
        plain = F.fact(row(('slot_overfull',)), E3, A.SESSION)
        self.assertEqual(plain.options, (Id(IdFamily.SESSION, 2), Id(IdFamily.SESSION, 5)))
        self.assertIn(X1, widened.options)  # the EGD, whose reach holds the gastric body
        self.assertEqual(widened.options[:2], plain.options)
        self.assertEqual(widened.reasons, (ct.Reason.SLOT_OVERFULL,))

    def test_an_overfilled_occasion_re_judges_its_acts_on_every_written_literal(self):
        """L1 only demotes: an act's inherited date relation stored with no literal of its own is re-judged on the
        literals of EVERY written fact of its section's overfilled occasion."""
        events = json.loads(json.dumps(view(colonoscopy())))
        section_ = next(item for item in events['sections'] if item['id'] == 'N2')
        day, year = {'value': '2026-11-09', 'precision': 'day'}, {'value': '2023', 'precision': 'year'}
        section_['occasion'] = [dict(written_fact('supported', 'on_date_of_service'), checks=checks([day])),
                                dict(written_fact('supported', 'earlier_date'), checks=checks([year]))]
        for item in events['events']:
            if item['id'] == 'E1':
                item['date_relation']['checks']['literals'] = []
        R = F.effective(events, datetime.date(2026, 11, 9))
        self.assertIn(ct.Reason.LITERAL_MISMATCH, F.fact(R, E1, A.DATE_RELATION).reasons)  # 2023 fails the day


def r2a_doubted(row: typing.Mapping, objects, readings, about='technique') -> dict:
    """``row`` (a text-free view) with one more doubt (basis unclear, cited on S5) naming ``objects`` and reading
    ``readings`` (DECISIONS D294 RD-1's inputs)."""
    events = json.loads(json.dumps(row))
    events['doubts'] = list(events['doubts']) + [{'about': about, 'objects': list(objects), 'units': ['S5'],
                                                  'basis': 'unclear', 'readings': list(readings)}]
    return events


def r2a_inherited(state: str, value: str, section: str) -> dict:
    """One written fact of an overfilled slot (``written_fact``) that the act inherited from ``section`` (1.5)."""
    found = written_fact(state, value)
    found['claim'] = claim(state, value, inherited_from=section)
    return found


class R2AOverfilledDoubtTests(SimpleTestCase):
    """DECISIONS D294 RD-1 (repair r2, builder R2A): a value any doubt naming an overfilled slot's object - the subject,
    or a section a written fact inherits from - reads is offered and never in negated_values, compared with the written
    values directly: a reading of the value EVERY written fact writes and denies included (as built, _fact removed each
    fact's own value from its options, so the doubt's reading was lost and the value read as only denied - 45378 READY
    on [manual N, manual N] beside a doubt reading manual). D293 N2's T2 exception (no doubt) is unchanged."""

    def device_view(self, readings=None, objects=('E1',)):
        written = [written_fact('negated', 'manual', units=('S5',)), written_fact('negated', 'manual', units=('S5',))]
        row = planted(view(colonoscopy()), IdFamily.EVENT, 'E1', A.TECHNIQUE_DEVICE, written)
        if readings is not None:
            row = r2a_doubted(row, objects, readings)
        return F.fact(F.factset(row), E1, A.TECHNIQUE_DEVICE)

    def test_a_doubt_reading_the_value_every_written_fact_denies_offers_it(self):
        from tests.v2 import test_combination as TC

        M, N_ = ct.Device.MANUAL, ct.FactState.NEGATED
        device = self.device_view(['manual'])
        self.assertEqual((device.options, device.negated_values, F.claimed_values(device)), ((M,), (), (M,)))
        self.assertEqual(device, dataclasses.replace(TC.overfilled((N_, M), (N_, M), readings=(M,)), spans=device.spans,
                                                     cited=device.cited))
        # three written denials, and a doubt reading the denied value beside another: both read, neither only denied
        three = planted(view(colonoscopy()), IdFamily.EVENT, 'E1', A.TECHNIQUE_DEVICE,
                        [written_fact('negated', 'manual', units=(unit,)) for unit in ('S5', 'S6', 'S7')])
        both = F.fact(F.factset(r2a_doubted(three, ['E1'], ['manual', 'endoscope'])), E1, A.TECHNIQUE_DEVICE)
        self.assertEqual((both.options, both.negated_values), ((M, ct.Device.ENDOSCOPE), ()))
        # the session slot: [X2 N, X2 N] beside a doubt naming the act and reading X2 claims X2 (as the doubt-free view
        # claims nothing)
        sessions = planted(view(colonoscopy()), IdFamily.EVENT, 'E2', A.SESSION,
                           [written_fact('negated', 'X2', units=('S6',)), written_fact('negated', 'X2', units=('S6',))])
        found = F.fact(F.factset(r2a_doubted(sessions, ['E2'], ['X2'], about='session')), E2, A.SESSION)
        self.assertEqual((found.negated_values, F.claimed_values(found)), ((), (X2,)))
        # an inherited slot: the doubt names the SECTION the written facts inherit from (N2), not the act
        inherited = planted(view(colonoscopy()), IdFamily.EVENT, 'E1', A.PERFORMER,
                            [r2a_inherited('negated', 'other_clinician', 'N2'),
                             r2a_inherited('negated', 'other_clinician', 'N2')])
        performer = F.fact(F.factset(r2a_doubted(inherited, ['N2'], ['other_clinician'], about='performer')), E1,
                           A.PERFORMER)
        self.assertEqual((performer.negated_values, performer.inherited_from), ((), Id(IdFamily.SECTION, 2)))
        self.assertEqual(F.claimed_values(performer), (ct.Performer.OTHER_CLINICIAN,))

    def test_only_a_doubt_naming_the_object_and_reading_the_denied_value_offers_it(self):
        """The boundary, beside its twin the rule changes (a doubt naming the act and reading manual offers it): no doubt
        (D293 N2's T2 exception), a doubt naming another object, a doubt naming the act but reading another value, and a
        doubt whose reading is no value of the slot's domain leave manual only denied."""
        M = ct.Device.MANUAL
        self.assertEqual(self.device_view(['manual']).negated_values, ())  # the twin
        for name, device in (('no doubt', self.device_view()),
                             ('a doubt naming another act', self.device_view(['manual'], objects=('E2',))),
                             ('a doubt reading another value', self.device_view(['endoscope'])),
                             ('a reading of another attribute', self.device_view(['performed']))):
            with self.subTest(name):
                self.assertEqual(device.negated_values, (M,))
                self.assertEqual(F.claimed_values(device), tuple(value for value in device.options if value != M))
        self.assertEqual(self.device_view(['endoscope']).options, (M, ct.Device.ENDOSCOPE))

    def test_45378_is_held_beside_the_doubt_and_ready_without_it(self):
        """The engine on the builder's view (the refute-f3e-r2 q3 scene: a colonoscopy X1 reaching the cecum, its
        examination E1 done today, 45378 proposed on E1): [manual N, manual N] beside a doubt naming E1 that reads
        manual claims manual (a possibly digital examination) - 45378 held, as the written fact read alone holds it;
        with no doubt, READY (D293 N2's T2 exception)."""
        from studio.interpretation.engine.types import Outcome
        from tests.v2 import evaluate_fixtures as EF
        from tests.v2 import test_assess as TA

        def status(device):
            doc = EF.Doc()
            doc.session(1, ct.SessionKind.COLONOSCOPY, tract=EF.sup(ct.Tract.LOWER), reached=[EF.sup(ct.Extent.CECUM)])
            doc.exam(1, device=dataclasses.replace(device, spans=(EF.unit(1),), cited=()))
            return TA.by_code(TA.run(doc.build(), ('45378', 1)))['45378']

        held = status(self.device_view(['manual']))
        self.assertEqual(held.status, Outcome.NEEDS_CLARIFICATION)
        self.assertEqual((held.item.held.fact, held.item.held.cause), ('performed_status', 'coding_rule:not_documented'))
        self.assertEqual(status(self.device_view()).status, Outcome.READY)


class R2ANegatedClaimOpenTests(SimpleTestCase):
    """DECISIONS D294 RD-3 (repair r2, builder R2A): a claim pass 1 wrote negated that is not established leaves every
    value of its domain open for facts.possibly and every possibility reader built on it - the kind readers included
    (facts.possible_kinds and possibly_of_family; coverage.may_be reads possibly) - as facts.open_denial makes
    classes._open read it; an overfilled slot's merged view reads so too (AMENDMENT-2 4.4: never narrower than a
    written denial read alone). As built, possibly read such a claim's denied value alone, so a weakened "not an
    examination" narrowed the kinds the act may be from every other kind to the examination. An established fact, a
    stated claim that is not established (4.2's candidate arm: its claimed value, readings and control's sibling), and
    ``possibly_written`` - the claimed-value readers' and the list members' reading - are as before."""

    def kind_denial(self, result=ct.Result.UNRESOLVED, reasons=(ct.Reason.APPRAISAL_UNCLEAR,), state=ct.FactState.NEGATED,
                    value=ct.Kind.SNARE) -> Fact:
        return Fact(result=result, value=value, state=state, options=(), reasons=reasons, spans=())

    def factset(self, kind: Fact) -> FactSet:
        from tests.v2 import evaluate_fixtures as EF

        doc = EF.colonoscopy()
        doc.events[E2] = {**doc.events[E2], A.KIND: (kind,)}
        return doc.build()

    def test_a_denial_left_open_leaves_every_value_possible(self):
        from studio.interpretation.engine import coverage

        for how, found in (('unresolved', self.kind_denial()),
                           ('doubted', self.kind_denial(ct.Result.UNKNOWN, (ct.Reason.DOUBT_STATED,))),
                           ('a conflict doubt', self.kind_denial(ct.Result.CONTRADICTED, (ct.Reason.DOUBT_UNCLEAR,)))):
            with self.subTest(how):
                self.assertTrue(F.open_denial(found))
                self.assertTrue(all(F.possibly(found, kind) for kind in ct.Kind))
                self.assertFalse(F.possibly_written(found, ct.Kind.BIOPSY))  # the claimed value alone, as before
                R = self.factset(found)
                for of_family in (False, True):
                    self.assertEqual(F.possible_kinds(R, E2, of_family=of_family), frozenset(ct.Kind))
                self.assertIn(ct.Kind.SNARE, coverage.may_be(found))
                self.assertIn(ct.Kind.BIOPSY, coverage.may_be(found))
        session = Fact(ct.Result.UNRESOLVED, X1, ct.FactState.NEGATED, (), (ct.Reason.APPRAISAL_UNCLEAR,), ())
        self.assertTrue(F.possibly(session, X2))  # "not in X1", the denial may be wrong either way
        from tests.v2 import test_combination as TC

        view = TC.overfilled((ct.FactState.SUPPORTED, ct.Device.ENDOSCOPE), (ct.FactState.SUPPORTED, ct.Device.HOT_SNARE))
        self.assertTrue(F.possibly(view, ct.Device.MANUAL))  # every view, as open_denial reads it (Q1R)
        self.assertFalse(F.possibly_written(view, ct.Device.MANUAL))  # never a value pass 1 did not write

    def test_an_established_fact_and_a_stated_claim_read_as_before(self):
        """The boundary, beside its twin the rule changes (the same denial left open leaves another kind possible): the
        denial established, and the claim stated (not negated) and left open, read as before; possibly_written is
        possibly for each."""
        from studio.interpretation.engine import coverage

        self.assertTrue(F.possibly(self.kind_denial(), ct.Kind.BIOPSY))  # the twin
        established = self.kind_denial(ct.Result.NEGATED, ())
        self.assertFalse(any(F.possibly(established, kind) for kind in ct.Kind))
        from studio.interpretation.engine import catalogue

        others = frozenset(member for kind in ct.Kind if kind is not ct.Kind.SNARE
                           for member in catalogue.UMBRELLAS.get(kind, (kind,)))
        self.assertEqual(coverage.may_be(established), others)  # every OTHER kind, an umbrella read as its members
        R = self.factset(established)
        self.assertEqual(F.possible_kinds(R, E2, of_family=False), frozenset())
        stated = self.kind_denial(state=ct.FactState.SUPPORTED)  # "a snare", unresolved: 4.2's candidate arm
        self.assertFalse(F.open_denial(stated))
        self.assertEqual(F.possible_kinds(self.factset(stated), E2, of_family=False), frozenset({ct.Kind.SNARE}))
        self.assertEqual(coverage.may_be(stated), frozenset({ct.Kind.SNARE}))
        for f in (established, stated):
            for kind in ct.Kind:
                self.assertEqual(F.possibly(f, kind), F.possibly_written(f, kind))


class R2BADoubtOfferedOnAStatementTests(SimpleTestCase):
    """DECISIONS D297 ENGA-F1 (repair round r2b, builder R2BA), on RD-1's own input through the REAL builder: the device
    view [manual N, manual N] of test_facts' stored row beside a doubt naming the act that reads manual CLAIMS manual
    (D294 RD-1), and transplanted onto an examination STATEMENT that excludes a primary, that claim must never release
    the add-on beside it - RD-2's may_exclude reads E13's exception established (pairing.established_digital), never the
    claimed reading (as built in r2, adding the doubt - a weakening - turned 43273 READY where the tree before RD-1 held
    it; the r2 refuter's F1, probe x3)."""

    def device_view(self, readings=None):
        written = [written_fact('negated', 'manual', units=('S5',)), written_fact('negated', 'manual', units=('S5',))]
        row = planted(view(colonoscopy()), IdFamily.EVENT, 'E1', A.TECHNIQUE_DEVICE, written)
        if readings is not None:
            row = r2a_doubted(row, ['E1'], readings)
        return dataclasses.replace(F.fact(F.factset(row), E1, A.TECHNIQUE_DEVICE), spans=(), cited=(), counter=())

    def test_the_doubt_offering_manual_never_releases_the_add_on(self):
        """test_assess's two ERCPs (r2ba_two_ercps: X2's examination statement E1 a cited all_of_kind denial, 43260 on
        its words, 43273 on X1's cholangioscopy) with E1's device the builder's view: with no doubt (D293 N2's T2:
        manual only denied) 43260 is EXCLUDED and 43273 held by ADDON; beside the doubt reading manual the view claims
        manual - 43260 is no longer excluded (a digital examination's statement concerns no group: D265), and 43273
        stays held, 43260 being a primary that statement may exclude."""
        from studio.interpretation.engine import assess as AS
        from studio.interpretation.engine.types import Outcome
        from tests.v2 import test_assess as TA

        M = ct.Device.MANUAL
        alone, offered = self.device_view(), self.device_view(['manual'])
        self.assertEqual((alone.negated_values, offered.negated_values), ((M,), ()))  # RD-1, as built
        for name, device, excluded in (('no doubt', alone, True), ('a doubt reading manual', offered, False)):
            with self.subTest(name):
                R = TA.r2ba_two_ercps(device).build()
                found = TA.by_code(TA.run(R, *TA.R2BA_DIAGNOSTIC))
                self.assertIs(found['43260'].evaluation.exclusion is not None, excluded)
                self.assertTrue(AS.addon_uncounted('43260', found['43260'].evidence.kept, TA.dated(R),
                                                   found['43260'].evidence.runs))
                self.assertEqual(found['43273'].status, Outcome.NEEDS_CLARIFICATION)
                self.assertEqual([held.cause for held in found['43273'].held_facts], [AS.ADDON_CAUSE])


class EstablishedKindTests(SimpleTestCase):
    """DECISIONS D287 (G3-28; build list B9): facts.established_kind, the one label of an act - questions.act_kind's
    event branch moved here, which every conflict key reads."""

    def test_the_one_label_by_state(self):
        def R_with(kind, purpose=None):
            facts_ = {A.KIND: (kind,)}
            if purpose is not None:
                facts_[A.PURPOSE] = (purpose,)
            return FactSet(encounter={}, people={}, sections={}, sessions={}, anatomy={}, lesions={}, events={E1: facts_},
                           anchors={}, unlisted=(), pair_controls={}, completeness={})

        clip, snare = ct.Kind.CLIP, ct.Kind.SNARE
        for name, kind, purpose, label in (
                ('supported', sup(snare), None, snare), ('silent', F.SILENT, None, ct.Kind.OTHER),
                ('unresolved', unresolved(snare), None, ct.Kind.OTHER), ('doubted', doubted(snare), None, ct.Kind.OTHER),
                ('negated', neg(snare), None, ct.Kind.OTHER),
                ('contradicted', Fact(result=ct.Result.CONTRADICTED, value=None, state=ct.FactState.CONTRADICTED,
                                      options=(snare, clip), reasons=(), spans=()), None, ct.Kind.OTHER),
                ('overfilled', Fact(result=ct.Result.UNRESOLVED, value=None, state=ct.FactState.CONTRADICTED,
                                    options=(snare,), reasons=(ct.Reason.SLOT_OVERFULL,), spans=()), None, ct.Kind.OTHER),
                ('kind other', sup(ct.Kind.OTHER), None, ct.Kind.OTHER),
                ('a clip supported for hemostasis', sup(clip), sup(ct.Purpose.HEMOSTASIS), ct.Kind.BLEEDING_CONTROL),
                ('a clip whose purpose is unresolved', sup(clip), unresolved(ct.Purpose.HEMOSTASIS), clip)):
            with self.subTest(name):
                R = R_with(kind, purpose)
                self.assertEqual(F.established_kind(R, E1), label)
                from studio.interpretation.engine import questions as Q
                self.assertEqual(Q.act_kind(R, E1, ()), label)  # the label questions.act_kind gives: one derivation

    def test_open_denial_by_state(self):
        """facts.open_denial (AMENDMENT-2 4.3.3 a; refute-f3e-r1 F1, the step's NOTES question Q1R): what a possibility
        reader that takes an unestablished denial as leaving every value open reads so - a claim written negated, in any
        result but negated, and EVERY overfilled slot's merged view, whatever its written facts; never a supported,
        unresolved, doubted or contradicted claim that is not a view, nor a silent slot."""
        def view(options, negated=()):
            return Fact(result=ct.Result.UNRESOLVED, value=None, state=ct.FactState.CONTRADICTED, options=options,
                        reasons=(ct.Reason.SLOT_OVERFULL,), spans=(), negated_values=negated)

        X2_ = Id(IdFamily.SESSION, 2)
        for name, found, expected in (
                ('supported', sup(X1), False), ('unresolved', unresolved(X1), False), ('doubted', doubted(X1), False),
                ('silent', F.SILENT, False),
                ('contradicted', Fact(result=ct.Result.CONTRADICTED, value=None, state=ct.FactState.CONTRADICTED,
                                      options=(X1, X2_), reasons=(ct.Reason.CONTRADICTED_BY_PASS1,), spans=()), False),
                ('a negated claim left unresolved', dataclasses.replace(unresolved(X1), state=ct.FactState.NEGATED),
                 True),
                ('a view of X1 written stated and denied', view((X1,)), True),
                ('a view of X1 and X2 stated', view((X1, X2_)), True),
                ('a view denying X2', view((X1, X2_), (X2_,)), True)):
            with self.subTest(name):
                self.assertEqual(F.open_denial(found), expected)

    def test_claimed_values_by_state(self):
        X2_ = Id(IdFamily.SESSION, 2)
        for name, found, claimed in (
                ('supported', sup(X1), (X1,)), ('unresolved', unresolved(X1), (X1,)), ('doubted', doubted(X1), (X1,)),
                ('a doubt reading beside a claim', dataclasses.replace(doubted(X1), options=(X2_,)), (X1,)),
                ('negated', neg(X1), ()),
                ('silent', F.SILENT, ()),
                ('contradicted', Fact(result=ct.Result.CONTRADICTED, value=None, state=ct.FactState.CONTRADICTED,
                                      options=(X1, X2_), reasons=(), spans=()), (X1, X2_)),
                ('overfilled, X2 denied', Fact(result=ct.Result.UNRESOLVED, value=None,
                                               state=ct.FactState.CONTRADICTED, options=(X1, X2_),
                                               reasons=(ct.Reason.SLOT_OVERFULL,), spans=(),
                                               negated_values=(X2_,)), (X1,))):
            with self.subTest(name):
                self.assertEqual(F.claimed_values(found), claimed)


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
                'apart_by_lesion', 'apart_by_place', 'apart_by_controls', 'iso_value', 'as_date', 'compare', 'rejudged')


class R2BBFindingTests(SimpleTestCase):
    """DECISIONS D297 ENGB-1 (repair round r2b): the ONE reading every rule that reads an act's target lesion's places
    shares - facts.finding (every lesion entry a same_as member in ANY state may join to a lesion, directly or through
    other entries, either direction; the lesion first; a dangling id kept) and facts.finding_places (each entry's place
    members, and the first entry whose places are not established, or that the FactSet does not hold). Written for this
    round, outside every development set."""

    L3, L4, L9 = Id(IdFamily.LESION, 3), Id(IdFamily.LESION, 4), Id(IdFamily.LESION, 9)  # L9: never held
    GEJ, CARDIA = ct.Landmark.GASTROESOPHAGEAL_JUNCTION, ct.Landmark.GASTRIC_CARDIA

    @staticmethod
    def fact_(result, value, state, options=(), reasons=()) -> Fact:
        return Fact(result=result, value=value, state=state, options=tuple(options), reasons=tuple(reasons), spans=())

    def sup(self, value) -> Fact:
        return self.fact_(ct.Result.SUPPORTED, value, ct.FactState.SUPPORTED)

    def entry(self, places=(), same=()) -> dict:
        return {A.PLACES: tuple(place if isinstance(place, Fact) else self.sup(place) for place in places),
                A.SAME_AS: tuple(item if isinstance(item, Fact) else self.sup(item) for item in same)}

    @staticmethod
    def factset(lesions) -> FactSet:
        return FactSet(encounter={}, people={}, sections={}, sessions={}, anatomy={}, lesions=lesions, events={},
                       anchors={}, unlisted=(), pair_controls={}, completeness={})

    def test_the_finding_reads_every_member_state_either_way_and_through_other_entries(self):
        R = self.factset({
            L1: self.entry(same=(self.fact_(ct.Result.NEGATED, L2, ct.FactState.NEGATED),)),  # "not the same": joins
            L2: self.entry(),
            self.L3: self.entry(same=(self.fact_(ct.Result.CONTRADICTED, None, ct.FactState.CONTRADICTED,
                                                 options=(L2, self.L9)),)),
            self.L4: self.entry()})
        self.assertEqual(F.finding(R, L1), (L1, L2, self.L3, self.L9))
        self.assertEqual(F.finding(R, self.L9), (self.L9, L1, L2, self.L3))  # the other direction, a dangling start
        self.assertEqual(F.finding(R, self.L4), (self.L4,))  # an entry no member names stands alone
        doubt = self.fact_(ct.Result.UNKNOWN, L2, ct.FactState.SUPPORTED, options=(self.L4,),
                           reasons=(ct.Reason.DOUBT_UNCLEAR,))
        self.assertEqual(F.finding(self.factset({L1: self.entry(same=(doubt,)), L2: self.entry(),
                                                 self.L4: self.entry()}), L1), (L1, L2, self.L4))
        silent = self.factset({L1: {A.PLACES: (), A.SAME_AS: (F.SILENT,)}, L2: self.entry(), self.L3: self.entry()})
        self.assertEqual(F.finding(silent, L2), (L2, L1, self.L3))  # a silent member names every lesion
        self.assertEqual(F.any_state_ids(silent, F.SILENT), (L1, L2, self.L3))
        distinct = self.factset({L1: {A.PLACES: (), A.SAME_AS: (), A.DISTINCT_FROM: (self.sup(L2),)},
                                 L2: self.entry()})
        self.assertEqual(F.finding(distinct, L1), (L1,))

    def test_the_finding_places_and_the_first_entry_left_unknown(self):
        unresolved = self.fact_(ct.Result.UNRESOLVED, self.CARDIA, ct.FactState.SUPPORTED,
                                reasons=(ct.Reason.UNAPPRAISED,))
        negated = self.fact_(ct.Result.NEGATED, self.CARDIA, ct.FactState.NEGATED)
        cases = (('every entry established', {L1: self.entry((self.GEJ,), same=(L2,)), L2: self.entry((self.CARDIA,))},
                  (self.GEJ, self.CARDIA), None),
                 ('a place left unresolved', {L1: self.entry((self.GEJ,), same=(L2,)), L2: self.entry((unresolved,))},
                  (self.GEJ, self.CARDIA), L2),
                 ('a partner with no place', {L1: self.entry((self.GEJ,), same=(L2,)), L2: self.entry()},
                  (self.GEJ,), L2),
                 ('a partner with a negated place only', {L1: self.entry((self.GEJ,), same=(L2,)),
                                                          L2: self.entry((negated,))}, (self.GEJ, self.CARDIA), L2),
                 ('a dangling id', {L1: self.entry((self.GEJ,), same=(self.L9,))}, (self.GEJ,), self.L9),
                 ('the lesion itself with no place', {L1: self.entry()}, (), L1),
                 ('one entry', {L1: self.entry((self.GEJ, self.CARDIA))}, (self.GEJ, self.CARDIA), None))
        for name, lesions, places, unknown in cases:
            with self.subTest(name):
                found = F.finding_places(self.factset(lesions), L1)
                self.assertEqual(found.entries[0], L1)
                self.assertEqual((tuple(member.value for member in found.members), found.unknown), (places, unknown))

    def test_the_findings_are_computed_once_per_factset(self):
        """D248 G5's cost, for readers that hold no Reader (SITE and D240's site fit read a finding per code and act): a
        dense same_as graph - every lesion naming every other, a doubt's readings and an id the FactSet does not hold -
        has its components built ONCE however often its findings and their places are read, and a FactSet built equal
        but apart gets its own."""
        missing = Id(IdFamily.LESION, 99)  # never held
        lesions = {Id(IdFamily.LESION, n): self.entry(
            (self.GEJ,), same=tuple(self.fact_(ct.Result.UNRESOLVED, Id(IdFamily.LESION, (n + k) % 24 + 1),
                                               ct.FactState.SUPPORTED, options=(missing,),
                                               reasons=(ct.Reason.APPRAISAL_UNCLEAR,)) for k in range(1, 9)))
            for n in range(1, 25)}
        R = self.factset(lesions)
        built = []
        real = F._components

        def counting(R_):
            built.append(R_)
            return real(R_)

        with mock.patch.object(F, '_components', counting):
            for _round in range(3):
                for lesion in lesions:
                    self.assertEqual(F.finding_places(R, lesion).unknown, missing)
                    self.assertEqual(len(F.finding(R, lesion)), 25)
            self.assertEqual(len(built), 1)
            twin = self.factset(lesions)
            self.assertEqual(F.finding(twin, L1), F.finding(R, L1))
            self.assertEqual([found is R for found in built], [True, False])
            # the memo keeps the FactSets read last, at most _FINDINGS_KEPT: the one read longest ago goes first
            others = [self.factset({L1: self.entry((self.GEJ,))}) for _number in range(F._FINDINGS_KEPT + 2)]
            for other in others:
                F.finding(other, L1)
            self.assertLessEqual(len(F._FINDINGS), F._FINDINGS_KEPT)
            built.clear()
            F.finding(others[-1], L1)
            F.finding(others[1], L1)
            self.assertEqual([found is others[1] for found in built], [True])

    def test_no_reader_of_the_finding_returns_a_string(self):
        for function in (F.any_state_ids, F.finding, F.finding_places):
            with self.subTest(function=function.__name__):
                self.assertNotIn(str, _leaves(typing.get_type_hints(function).get('return')))
        self.assertNotIn(str, {leaf for hint in typing.get_type_hints(F.FindingPlaces).values()
                               for leaf in _leaves(hint)})


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
