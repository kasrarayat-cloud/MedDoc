"""contract/settle.py: settle (docs/gemini-migration/FINAL-V2.md 1.5, 1.7, 3.1's cross-object rules, 3.2.3-3.2.6, 3.3 and
3.4; step 3a of 8.1). TEXT-ONLY and SYNTHETIC: every note here is written for this test (fictional clinicians, no real
patient; each checked against the acceptance set's DEV-EXCLUSION hashes), every pass-1 and pass-2 answer is constructed
by hand or by a deterministic oracle over the claim set, nothing is sent anywhere.

What is proved, item by item against the done-when of 8.1 step 3a:
- the exhaustive truth table (TruthTableTests): every combination of state x doubt x check x qualifier x CLAIMED x
  verdict x control x attached x evidence (and row 7's indistinct cards), its result and reasons computed by an oracle
  written here from 3.3's and 3.2.3's tables, against settle.decide and settle.appraise; and the same table reached
  through the whole pipeline on a real claim set (WiringTests);
- S1's probes (a)-(e) each end unresolved (ProbeTests, 3.8);
- SC-A's three unlisted cases kept, every drop recorded with the event that absorbed it (UnlistedTests, 3.2.6);
- a yes-man, an all-contradicts and an all-detached appraisal each refused, and the completeness measure (HealthTests,
  3.2.6 [R:HO-4]), control acceptance over claim/control pairs only (hand-off 2c#12), and the pin;
- K3 fires with the real Vocabulary - an EGD act at the sigmoid colon (VocabularyTests, DECISIONS D192);
- the date of service settles by DECISIONS D187's map, its checks as the integration's O13 states (DateOfServiceTests);
- P-INDEP-SETTLE over DECISIONS D201's listed couplings (IndependenceTests, 9.4 [R:HO-7]), with P-DEMOTE and P-DET;
- inheritance, the doubt mapping (D200's object-less doubt included), K8, the cross-object rules, shared claims, the
  restatement role, cards_indistinct, and every settled inventory stored by store.row_v2 and read by engine/facts
  (InheritanceTests, DoubtTests, CrossObjectTests, ClaimTests, StoreTests);
- the module keeps 5.7 measure 4 (WordsNeverDecide, NoWordLists) and mypy --strict (ModuleTests);
- the repairs after the step's first refutation (refute-3a-r1): a restates role carries its entry move's conditions -
  rows 1-5 on the owner of R's section, the act's entry doubts - and is never established while no claim appraises
  that owner for the act (P2, ClaimTests); a planned or attempted event absorbs no unlisted act or denial (P3,
  UnlistedTests); a shared claim is read only by the entry whose value it states, and a claim no fact reads is stored
  under the attribute its value belongs to (ClaimTests); a shared claim counts as established only when every pair it
  is in is (P5, HealthTests); row 1 reads every option's own sources (P6, DateOfServiceTests); P-INDEP-SETTLE's G5 and
  anatomy couplings as narrow as the design states them (P7, IndependenceTests). The shared claims themselves (P1)
  stay a fail-closed limit, pinned as such, until the step's notes' REQUEST R4 is ruled.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import itertools
import json
import os
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from unittest import mock

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio import interpretation
from studio.interpretation import store
from studio.interpretation.contract import (appraise_prompt, appraise_read, checks, claims, extract_read, jsonschema,
                                            segment, settle)
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract.extract_read import FactKey
from studio.interpretation.contract.types import (Attached, Attribute, CheckStatus, DoubtBasis, FactState, Kind,
                                                  Qualifier2, Reason, Result, UnlistedWhat, Verdict, VerdictValue)
from studio.interpretation.engine import catalogue
from studio.interpretation.engine import facts as engine_facts
from tests.v2.test_types import STR_METHODS, measure_4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'contract' / 'settle.py'
DEV_EXCLUSION = APP / 'docs' / 'gemini-migration' / 'acceptance-a1' / 'DEV-EXCLUSION.sha256'
A, F, R = Attribute, xs.Family, Reason
HEALTH_PIN = jsonschema.sha256_of(settle.health_document())  # the pin this step hands the integration owner

# --- the synthetic notes, written for these tests --------------------------------------------------------------------

NOTE = ('SYNTHETIC ENDOSCOPY REPORT\n'                                                    # S1
        'Date of service: 03/14/2031\n'                                                   # S2
        'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                   # S3
        'Assistant: Ines Varro, RN (fictional)\n'                                         # S4
        '\n'
        'History: Prior colonoscopy in 2027 with removal of one polyp.\n'                 # S5
        '\n'
        'Findings: The colonoscope was advanced to the cecum.\n'                          # S6
        'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.\n'      # S7
        'Bleeding from the polypectomy site was treated with a clip.\n'                   # S8
        'Neither biopsy nor tattoo was performed.\n'                                      # S9
        'The ileocolic anastomosis was patent.\n'                                         # S10
        '\n'
        'Upper endoscopy: The gastroscope was advanced to the duodenum.\n'                # S11
        'Biopsies of the gastric antrum were taken with cold forceps.\n'                  # S12
        '\n'
        'Impression: Polyp removed.\n')                                                   # S13
PROBE_A = ('SYNTHETIC COLONOSCOPY REPORT\n'
           'Date of service: 03/14/2031\n'
           'Endoscopist: Corvin Ashdale, MD (fictional)\n'
           '\n'
           'Findings: The colonoscope was advanced to the cecum.\n'
           'Neither biopsy nor snare polypectomy was performed.\n')
PROBE_B = ('SYNTHETIC COLONOSCOPY REPORT\n'
           'Date of service: 03/14/2031\n'
           'Endoscopist: Corvin Ashdale, MD (fictional)\n'
           '\n'
           'History: polypectomy with a hot snare in the rectum in 2023.\n'
           '\n'
           'Findings: The colonoscope was advanced to the cecum.\n')
PROBE_C = ('SYNTHETIC COLONOSCOPY REPORT\n'
           'Date of service: 03/14/2031\n'
           'Endoscopist: Corvin Ashdale, MD (fictional)\n'
           '\n'
           'Findings: The colonoscope was advanced to the cecum.\n'
           'A 4 mm polyp in the rectum was removed with a cold snare.\n'
           'No polyps were removed.\n')
PROBE_D = ('SYNTHETIC COLONOSCOPY REPORT\n'
           'Date of service: 03/14/2031\n'
           'Endoscopist: Corvin Ashdale, MD (fictional)\n'
           '\n'
           'Findings: The colonoscope was advanced to the ileocecal valve.\n'
           'The ileocecal valve was seen.\n')
PROBE_E = ('SYNTHETIC COLONOSCOPY REPORT\n'
           'Date of service: 03/14/2031\n'
           'Endoscopist: Corvin Ashdale, MD (fictional)\n'
           '\n'
           'Findings: The colonoscope was advanced to the cecum.\n'
           'A 7 mm polyp was seen in the sigmoid colon.\n')
EXCHANGE = ('SYNTHETIC ERCP REPORT\n'
            'Date of service: 03/14/2031\n'
            'Endoscopist: Corvin Ashdale, MD (fictional)\n'
            '\n'
            'Findings: The duodenoscope was advanced to the major papilla.\n'
            'The existing biliary stent was removed and replaced with a new plastic stent.\n')
BOTH = ('SYNTHETIC COLONOSCOPY REPORT\n'
        'Date of service: 03/14/2031\n'
        'Endoscopist: Corvin Ashdale, MD (fictional)\n'
        '\n'
        'Findings: The colonoscope was advanced to the cecum.\n'
        'A polyp in the descending colon was biopsied with cold forceps and then removed with a hot snare.\n')
DATES = ('SYNTHETIC COLONOSCOPY REPORT\n'
         'Date of service: 03/14/2031\n'
         'Endoscopist: Corvin Ashdale, MD (fictional)\n'
         'Procedure date: 03/15/2031\n'
         '\n'
         'Findings: The colonoscope was advanced to the cecum.\n')
NURSING = ('SYNTHETIC COLONOSCOPY REPORT\n'                                                  # S1
           'Date of service: 03/14/2031\n'                                                     # S2
           'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                     # S3
           '\n'
           'Findings: The colonoscope was advanced to the cecum.\n'                            # S4
           '\n'
           'Nursing note: A 5 mm rectal polyp was removed with a cold snare.\n'                # S5
           '\n'
           'Impression: A 5 mm rectal polyp was removed with a cold snare by me.\n')           # S6
PLANNED = ('SYNTHETIC UPPER ENDOSCOPY REPORT\n'
           'Date of service: 03/14/2031\n'
           'Endoscopist: Corvin Ashdale, MD (fictional)\n'
           '\n'
           'Findings: The gastroscope was advanced to the duodenum.\n'                         # S4
           'The esophageal stricture was dilated with a balloon today and repeat dilation is planned in four weeks.\n')
ATTEMPTED = ('SYNTHETIC UPPER ENDOSCOPY REPORT\n'
             'Date of service: 03/14/2031\n'
             'Endoscopist: Corvin Ashdale, MD (fictional)\n'
             '\n'
             'Findings: The gastroscope was advanced to the duodenum.\n'                       # S4
             'Balloon dilation of the stricture was attempted but not completed, and a bougie dilation was then done.\n')
NOT_PLANNED = ('SYNTHETIC UPPER ENDOSCOPY REPORT\n'
               'Date of service: 03/14/2031\n'
               'Endoscopist: Corvin Ashdale, MD (fictional)\n'
               '\n'
               'Findings: The gastroscope was advanced to the duodenum.\n'                     # S4
               'No repeat dilation is planned, and no dilation was performed today.\n')        # S5
NOTES = {'NOTE': NOTE, 'PROBE_A': PROBE_A, 'PROBE_B': PROBE_B, 'PROBE_C': PROBE_C, 'PROBE_D': PROBE_D,
         'PROBE_E': PROBE_E, 'EXCHANGE': EXCHANGE, 'BOTH': BOTH, 'DATES': DATES, 'NURSING': NURSING,
         'PLANNED': PLANNED, 'ATTEMPTED': ATTEMPTED, 'NOT_PLANNED': NOT_PLANNED}

# --- building pass 1's answer by hand (FINAL-V2 1.4's shape) ----------------------------------------------------------


def src(units, words='', link='statement'):
    return {'units': list(units), 'words': words, 'link': link}


def fact(value, *sources, state='supported', qualifiers=(), options=()):
    return {'state': state, 'value': value, 'qualifiers': list(qualifiers), 'sources': list(sources),
            'options': list(options)}


def frame(units, words=''):
    return src(units, words, 'document_frame')


def section(sid, start, owner, **slots):
    item = {'id': sid, 'start': start, 'end': [], 'owner': owner, 'role': [], 'occasion': [], 'performer': [],
            'performer_person': []}
    item.update(slots)
    return item


def session(xid, kind, **fields):
    item = {'id': xid, 'examination': [], 'kind': kind, 'encounter': [], 'tract': [], 'approach': [], 'through': [],
            'reached': [], 'device_reached': [], 'reached_anatomy': [], 'completion': [], 'stations': [],
            'part_of_session': []}
    item.update(fields)
    return item


def lesion(lid, description, **fields):
    item = {'id': lid, 'description': description, 'multiplicity': [], 'places': [], 'distinct_from': [],
            'same_as': []}
    item.update(fields)
    return item


def event(eid, units, kind_words, status_words, kind, status='performed', state='supported', status_source=None,
          **over):
    """An event: its kind and status cited at its anchor's own words unless given whole; ``over`` sets any field, a
    nested one written ``a__b`` (target__places)."""
    the_kind = kind if isinstance(kind, dict) else fact(kind, src(units, kind_words))
    the_status = status if isinstance(status, dict) else fact(status, status_source or src(units, status_words),
                                                              state=state)
    item = {'id': eid, 'anchor': {'units': list(units), 'kind_words': kind_words, 'status_words': status_words},
            'restatements': [], 'kind': the_kind, 'other_class': [], 'status': the_status, 'session': [],
            'date_relation': [], 'date': [], 'performer': [], 'performer_person': [],
            'target': {'lesion': [], 'structure': [], 'places': [], 'anatomy': [], 'duct': []},
            'technique': {'device': [], 'route': []}, 'purpose': [], 'cause': [], 'cause_event': [], 'part_of': [],
            'part_relation': [], 'yield': [], 'access_outcome': [],
            'scope': {'breadth': [], 'targets': [], 'segment': [], 'covers': [], 'excepts': []},
            'visit': {'basis': [], 'separately_identifiable': []}}
    for key, value in over.items():
        if '__' in key:
            outer, inner = key.split('__')
            item[outer][inner] = value
        else:
            item[key] = value
    return item


def doubt(about, objects, units, basis='stated', readings=()):
    return {'about': about, 'objects': list(objects), 'units': list(units), 'basis': basis, 'readings': list(readings)}


def answer(sections, sessions=(), events=(), lesions=(), anatomy=(), people=None, doubts=(), when=None,
           others=(), clinician=None):
    return {
        'encounter': {
            'date_of_service': when or {'state': 'stated', 'value': '2031-03-14',
                                        'sources': [frame(['S2'], '03/14/2031')], 'options': []},
            'other_dates': list(others),
            'documenting_clinician': [fact('P1', frame(['S3'], 'Corvin Ashdale'))] if clinician is None else clinician},
        'people': [{'id': 'P1', 'name': src(['S3'], 'Corvin Ashdale'),
                    'role': fact('documenting_clinician', src(['S3'], 'Endoscopist'))}] if people is None else people,
        'sections': list(sections), 'sessions': list(sessions), 'anatomy': list(anatomy), 'lesions': list(lesions),
        'events': list(events), 'doubts': list(doubts)}


def opening(**slots):
    """N0, the document's opening part: its start cites no unit (1.4)."""
    defaults = {'role': [fact('header', src(['S1'], '', 'frame'))],
                'occasion': [fact('on_date_of_service', frame(['S2']))],
                'performer': [fact('documenting_team', frame(['S3']))]}
    defaults.update(slots)
    return section('N0', src([], '', 'section'), fact('documenting_clinician', frame(['S3'])), **defaults)


def labelled(sid, unit, label, role, occasion=None, performer=True, owner=None):
    """A part opened by a label: its role cited at the label, its occasion on the date of service and its performer
    the documenting team through the document frame (unless given)."""
    slots = {'role': [fact(role, src([unit], label, 'section'))],
             'occasion': [occasion if occasion is not None else fact('on_date_of_service', frame(['S2']))]}
    if performer:
        slots['performer'] = [fact('documenting_team', frame(['S3']))]
    return section(sid, src([unit], label, 'section'), owner or fact('documenting_clinician', frame(['S3'])), **slots)


def note_answer():
    """NOTE's answer: N0; a History part (earlier_date); a Findings part and an Upper endoscopy part (today, the team);
    an Impression part; a colonoscopy session X1 (E1) reaching the cecum and an upper endoscopy session X2 (E6)
    reaching the duodenum; a cold-snare removal of L1 at the sigmoid colon (E2) with a summarizing restatement in the
    impression; a hemostasis clip caused by E2 (E3); a biopsy and a tattoo denial sharing one sentence (E4, E5); an
    antral biopsy (E7); an ileocolic anastomosis (Y1); the endoscopist P1 and the assistant P2."""
    return answer(
        sections=[
            opening(),
            section('N1', src(['S5'], 'History:', 'section'), fact('documenting_clinician', frame(['S3'])),
                    role=[fact('history', src(['S5'], 'History:', 'section'))],
                    occasion=[fact('earlier_date', src(['S5'], 'Prior colonoscopy in 2027', 'frame'))]),
            labelled('N2', 'S6', 'Findings:', 'findings'),
            labelled('N3', 'S11', 'Upper endoscopy:', 'procedure'),
            section('N4', src(['S13'], 'Impression:', 'section'), fact('documenting_clinician', frame(['S3'])),
                    role=[fact('impression', src(['S13'], 'Impression:', 'section'))])],
        people=[{'id': 'P1', 'name': src(['S3'], 'Corvin Ashdale'),
                 'role': fact('documenting_clinician', src(['S3'], 'Endoscopist'))},
                {'id': 'P2', 'name': src(['S4'], 'Ines Varro'), 'role': fact('assistant', src(['S4'], 'Assistant'))}],
        sessions=[
            session('X1', fact('colonoscopy', src(['S6'], 'colonoscope')), examination=[fact('E1', src(['S6']))],
                    encounter=[fact('this_encounter', frame(['S2']))],
                    reached=[fact('cecum', src(['S6'], 'advanced to the cecum'))]),
            session('X2', fact('egd', src(['S11'], 'gastroscope')), examination=[fact('E6', src(['S11']))],
                    reached=[fact('duodenum', src(['S11'], 'advanced to the duodenum'))])],
        anatomy=[{'id': 'Y1', 'type': fact('anastomosis', src(['S10'], 'ileocolic anastomosis')), 'organ': [],
                  'subtype': [fact('ileocolic', src(['S10'], 'ileocolic'))], 'joins': []}],
        lesions=[lesion('L1', src(['S7'], 'A 6 mm sessile polyp'),
                        multiplicity=[fact('single', src(['S7'], 'A 6 mm sessile polyp'))],
                        places=[fact('sigmoid_colon', src(['S7'], 'sigmoid colon'))])],
        events=[
            event('E1', ['S6'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S6']))]),
            event('E2', ['S7'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S7']))],
                  restatements=[{'units': ['S13'], 'role': 'summarizes'}],
                  target__lesion=[fact('L1', src(['S7'], 'A 6 mm sessile polyp'))],
                  target__places=[fact('sigmoid_colon', src(['S7'], 'sigmoid colon'))],
                  technique__device=[fact('cold_snare', src(['S7'], 'cold snare'))]),
            event('E3', ['S8'], 'clip', 'was treated', 'clip', session=[fact('X1', src(['S8']))],
                  purpose=[fact('hemostasis', src(['S8'], 'Bleeding'))],
                  cause=[fact('act_of_this_session', src(['S8'], 'from the polypectomy site'))],
                  cause_event=[fact('E2', src(['S8'], 'polypectomy site'))]),
            event('E4', ['S9'], 'biopsy', 'was performed', 'biopsy', state='negated',
                  status_source=src(['S9'], 'Neither biopsy nor tattoo was performed'),
                  session=[fact('X1', src(['S9']))], scope__breadth=[fact('all_of_kind', src(['S9']))]),
            event('E5', ['S9'], 'tattoo', 'was performed', 'tattoo', state='negated',
                  status_source=src(['S9'], 'Neither biopsy nor tattoo was performed'),
                  session=[fact('X1', src(['S9']))], scope__breadth=[fact('all_of_kind', src(['S9']))]),
            event('E6', ['S11'], 'gastroscope', 'was advanced', 'examination', session=[fact('X2', src(['S11']))]),
            event('E7', ['S12'], 'Biopsies', 'were taken', 'biopsy', session=[fact('X2', src(['S12']))],
                  target__places=[fact('gastric_antrum', src(['S12'], 'gastric antrum'))],
                  technique__device=[fact('cold_forceps', src(['S12'], 'cold forceps'))])])


def colonoscopy(text, *events, extra_sections=(), lesions=(), anatomy=(), doubts=(), reached='cecum',
                reached_words='advanced to the cecum', findings_unit='S4'):
    """A one-session colonoscopy note's answer: N0, a Findings part at ``findings_unit``, the examination E1 there."""
    return answer(
        sections=[opening(), labelled('N1', findings_unit, 'Findings:', 'findings'), *extra_sections],
        sessions=[session('X1', fact('colonoscopy', src([findings_unit], 'colonoscope')),
                          examination=[fact('E1', src([findings_unit]))],
                          reached=[fact(reached, src([findings_unit], reached_words))])],
        events=[event('E1', [findings_unit], 'colonoscope', 'was advanced', 'examination',
                      session=[fact('X1', src([findings_unit]))]), *events],
        lesions=lesions, anatomy=anatomy, doubts=doubts)


# --- the pipeline: read, check, claim, appraise (an oracle), settle --------------------------------------------------


def roles_of(claim_set):
    """What each claim of a request is, from the claim set (pass 2 never sees it): claim, control, pair control,
    completeness, completeness control."""
    roles = {}
    for item in claim_set.appraised:
        roles[item.claim] = 'claim'
    for complete in claim_set.completeness:
        roles.setdefault(complete.claim, 'completeness')
    for item in claim_set.appraised:
        if item.control is not None:
            roles.setdefault(item.control, 'control')
    for complete in claim_set.completeness:
        roles.setdefault(complete.control, 'completeness_control')
    for pair in claim_set.pair_controls:
        roles.setdefault(pair.claim, 'pair_control')
    for claim in claim_set.claims:
        roles.setdefault(claim.id, 'control')
    return roles


def verdict(claim, value='supports', attached='yes', qualifiers=(), evidence=None):
    return {'claim': claim.id, 'verdict': value, 'attached': attached, 'qualifiers': list(qualifiers),
            'evidence': list(claim.units[:1] if evidence is None else evidence)}


def faithful(claim, role, claim_set):
    """A faithful second reading of a well-filed answer: every real claim supported, attached, its first unit as
    evidence; every control, pair control and limitation contradicted."""
    return verdict(claim, 'supports' if role in ('claim', 'completeness') else 'contradicts')


class Prepared:
    """A revision and pass 1's answer, read, checked and built into a request: what pass 2 is asked."""

    def __init__(self, text, data):
        self.text, self.data = text, data
        self.units = segment.units(text)
        found = extract_read.read(json.dumps(data), len(self.units))
        assert not isinstance(found, extract_read.Refusal), found
        self.read = found
        self.checked = checks.check(text, (), found)
        self.request = appraise_prompt.build_request(text, (), 'txt', found, findings=self.checked.findings)
        self.claim_set = self.request.claim_set
        self.roles = roles_of(self.claim_set)

    def appraised(self, attribute, subject, index=0):
        """The Appraised entry of a fact (its claim and control ids), None when it is not claimed."""
        return next((item for item in self.claim_set.appraised if item.key.attribute is attribute
                     and item.key.object == subject and item.key.index == index), None)

    def answer2(self, oracle=faithful, unlisted=()):
        """Pass 2's answer: the oracle's verdict per claim (None leaves the claim without one), and unlisted."""
        verdicts = []
        for claim in self.claim_set.claims:
            found = oracle(claim, self.roles[claim.id], self.claim_set)
            if found is not None:
                verdicts.append(found)
        return {'verdicts': verdicts, 'unlisted': list(unlisted)}

    def appraisal(self, oracle=faithful, unlisted=()):
        found = appraise_read.read(json.dumps(self.answer2(oracle, unlisted)), self.claim_set, len(self.units))
        assert not isinstance(found, extract_read.Refusal), found
        return found

    def settle(self, oracle=faithful, unlisted=()):
        with mock.patch.object(interpretation, 'HEALTH_THRESHOLDS_SHA256', HEALTH_PIN):
            return settle.settle(self.read, self.checked, self.claim_set, self.request.indistinct,
                                 self.appraisal(oracle, unlisted), USAGE)


USAGE = settle.Usages(settle.usage_of({'promptTokenCount': 1800, 'candidatesTokenCount': 900,
                                       'thoughtsTokenCount': 2100, 'totalTokenCount': 4800}),
                      settle.usage_of({'promptTokenCount': 2600, 'candidatesTokenCount': 480}))


def run(text, data, oracle=faithful, unlisted=()):
    prepared = Prepared(text, data)
    return prepared, prepared.settle(oracle, unlisted)


def overriding(**answers):
    """An oracle that answers the claims named by (attribute value, subject, index) - and their controls, as
    ``'<attribute>@<subject>/control'`` - as given, every other claim faithfully. Each answer is a dict of
    verdict()'s keywords, or None to leave the claim without a verdict."""
    def oracle(claim, role, claim_set):
        for item in claim_set.appraised:
            name = f'{item.key.attribute.value}@{item.key.object}/{item.key.index}'
            if item.claim == claim.id and name in answers:
                return None if answers[name] is None else verdict(claim, **answers[name])
            if item.control == claim.id and f'{name}/control' in answers:
                given = answers[f'{name}/control']
                return None if given is None else verdict(claim, **given)
        return faithful(claim, role, claim_set)
    return oracle


def at(events, *path):
    """The settled fact at ``path`` in the settled inventory: ('events', 'E2', 'status'), ('events', 'E2',
    'target.places', 0), ('encounter', 'date_of_service'), ('sessions', 'X1', 'reached', 0)."""
    if path[0] == 'encounter':
        return events['encounter'][path[1]]
    family, name, attribute, *index = path
    item = next(record for record in events[family] if record['id'] == name)
    node = item
    for part in attribute.split('.'):
        node = node[part]
    return node[index[0]] if index else node


def stored(prepared, out):
    """The settled inventory as store.row_v2 writes it, store.load_v2 reads it back and engine/facts builds its FactSet
    from store.textfree_v2's view: proof that settle's output is the stored contract (FINAL-V2 1.7, 3.1 B1)."""
    text_sha256 = hashlib.sha256(prepared.text.encode('utf-8')).hexdigest()
    fields = store.row_v2(encounter_id=uuid.uuid4(), revision_id=uuid.uuid4(), provider_run_id=uuid.uuid4(),
                          appraisal_run_id=uuid.uuid4(), revision_text=prepared.text, text_sha256=text_sha256,
                          request_sha256='2' * 64, response_sha256='3' * 64, appraisal_request_sha256='4' * 64,
                          appraisal_response_sha256='5' * 64, events=out.events, verification=out.verification)
    loaded = store.load_v2(fields, text_sha256=text_sha256, response_sha256='3' * 64,
                           appraisal_response_sha256='5' * 64)
    return fields, engine_facts.factset(store.textfree_v2(loaded))


class Case(SimpleTestCase):
    def assertSettled(self, fact, result, *reasons):  # noqa: N802 - unittest's naming
        self.assertEqual((fact.result, fact.reasons), (result, tuple(reasons)))


# --- the truth table, by an oracle written from 3.3 and 3.2.3 --------------------------------------------------------

STATES = (FactState.SUPPORTED, FactState.NEGATED, FactState.CONTRADICTED, None)
DOUBTS = (frozenset(), frozenset({DoubtBasis.STATED}), frozenset({DoubtBasis.UNCLEAR}),
          frozenset({DoubtBasis.CONFLICT}), frozenset({DoubtBasis.STATED, DoubtBasis.UNCLEAR}))
CHECKS = ((), (R.WORDS_NOT_IN_UNITS,), (R.GEOMETRY_SECTION, R.LITERAL_MISMATCH))  # pass; integrity; geometry and L1
QUALIFIERS = ((), (R.QUALIFIED_HEDGED,))  # Q1: none (or approximate, which gives no finding); hedged
VERDICTS = (None, 'supports', 'supports+approximate', 'contradicts', 'qualified', 'qualified+none', 'unclear')
CONTROLS = ('uncontrolled', None, VerdictValue.CONTRADICTS, VerdictValue.SUPPORTS, VerdictValue.QUALIFIED,
            VerdictValue.UNCLEAR)


def table_verdict(name, attached):
    """A Verdict for the table's verdict dimension: supports, supports naming a qualifier (approximate: read as
    qualified, D186), contradicts, qualified naming one, qualified naming none, unclear; None for no verdict."""
    if name is None:
        return None
    value, _, extra = name.partition('+')
    qualifiers = () if extra == 'none' else ((Qualifier2.APPROXIMATE,) if extra else
                                             ((Qualifier2.HEDGED,) if value == 'qualified' else ()))
    return Verdict('K1', VerdictValue(value), attached, qualifiers, ('S1',))


def expected(state, sides, doubts, findings, claimed, indistinct, verdict_, attached_evidence, control):
    """3.3's table, row by row, and 3.2.3's coherence table, as the design writes them (computed here, apart from
    settle): the result and the reasons of one fact."""
    every = set(findings)
    if (state is FactState.CONTRADICTED and sides) or DoubtBasis.CONFLICT in doubts:  # row 1
        return Result.CONTRADICTED, {R.CONTRADICTED_BY_PASS1} | every
    if DoubtBasis.STATED in doubts or DoubtBasis.UNCLEAR in doubts:  # row 2
        return Result.UNKNOWN, ({R.DOUBT_STATED} if DoubtBasis.STATED in doubts else set()) | (
            {R.DOUBT_UNCLEAR} if DoubtBasis.UNCLEAR in doubts else set()) | every
    if state is None:  # row 3
        return Result.UNKNOWN, {R.SILENT} | every
    if every or state is FactState.CONTRADICTED:  # rows 4-5 (a contradicted claim with a failing side: row 4)
        return Result.UNRESOLVED, every or {R.SHAPE_INCONSISTENT}
    if not claimed:  # row 6
        return Result.UNRESOLVED, {R.UNAPPRAISED}
    if indistinct:  # row 7
        return Result.UNRESOLVED, {R.CARDS_INDISTINCT}
    # rows 8-9: the coherence table
    if verdict_ is None:
        return Result.UNRESOLVED, {R.APPRAISAL_MISSING}
    if verdict_.verdict is VerdictValue.QUALIFIED or (verdict_.verdict is VerdictValue.SUPPORTS and verdict_.qualifiers):
        named = {R(f'appraisal_qualified:{q.value}') for q in verdict_.qualifiers}
        return Result.UNRESOLVED, named or {R.APPRAISAL_QUALIFIED}
    if verdict_.verdict is VerdictValue.UNCLEAR:
        return Result.UNRESOLVED, {R.APPRAISAL_UNCLEAR}
    if verdict_.verdict is VerdictValue.CONTRADICTS:
        return Result.UNRESOLVED, {R.APPRAISAL_CONTRADICTS}
    if verdict_.attached is not Attached.YES or not attached_evidence:
        return Result.UNRESOLVED, {R.APPRAISAL_DETACHED}
    if control == 'uncontrolled' or control is VerdictValue.CONTRADICTS:
        return (Result.SUPPORTED if state is FactState.SUPPORTED else Result.NEGATED), set()
    if control is None:
        return Result.UNRESOLVED, {R.APPRAISAL_MISSING}
    return Result.UNRESOLVED, {R.CONTROL_INCOHERENT}


class TruthTableTests(SimpleTestCase):
    def test_the_exhaustive_truth_table(self):
        """state x doubt x check x qualifier x CLAIMED x verdict x control x attached x evidence (and row 7): every
        combination's result and reasons are 3.3's, through settle.appraise (the pair) and settle.decide (the fact)."""
        count = 0
        for (state, sides, doubts, check, qualifier, claimed, indistinct, name, control, attached,
             evidence) in itertools.product(STATES, (True, False), DOUBTS, CHECKS, QUALIFIERS, (True, False),
                                            (False, True), VERDICTS, CONTROLS, tuple(Attached), (True, False)):
            if state is not FactState.CONTRADICTED and not sides:
                continue  # the side condition is a contradicted claim's only
            findings = tuple(check) + tuple(qualifier)
            if state is FactState.CONTRADICTED and not sides and not check:
                findings += (R.UNIT_UNKNOWN,)  # a side that fails integrity is a check finding (the reader's)
            found = table_verdict(name, attached)
            pair, pair_reasons = settle.appraise(found, evidence, control != 'uncontrolled',
                                                 None if control == 'uncontrolled' else control)
            result, reasons = settle.decide(settle.Case(
                state=state, sides=sides, doubts=doubts, joined=False, findings=settle.ordered(findings),
                claimed=claimed, indistinct=indistinct, pair=pair if claimed else None,
                pair_reasons=pair_reasons if claimed else ()))
            want, want_reasons = expected(state, sides, doubts, findings, claimed, indistinct, found, evidence, control)
            self.assertEqual((result, set(reasons)), (want, want_reasons),
                             (state, sides, doubts, check, qualifier, claimed, indistinct, name, control, attached,
                              evidence))
            self.assertEqual(reasons, settle.ordered(reasons))  # a set, in the closed list's order (1c:R6)
            count += 1
        self.assertEqual(count, 3 * 5 * 3 * 2 * 2 * 2 * 7 * 6 * 3 * 2 + 1 * 2 * 5 * 3 * 2 * 2 * 2 * 7 * 6 * 3 * 2)

    def test_k8_joins_settle_as_row_one(self):
        result, reasons = settle.decide(settle.Case(
            state=FactState.SUPPORTED, sides=False, doubts=frozenset({DoubtBasis.STATED}), joined=True, findings=(),
            claimed=True, indistinct=False, pair=settle.PairOutcome.ESTABLISHED, pair_reasons=()))
        self.assertEqual((result, reasons), (Result.CONTRADICTED, (R.CONTRADICTED_BY_PASS1,)))

    def test_every_outcome_of_the_coherence_table(self):
        """3.2.3's table, row by row, with the outcome each pair is counted as (verification.coherence)."""
        supports = Verdict('K1', VerdictValue.SUPPORTS, Attached.YES, (), ('S1',))
        contradicts = dataclasses.replace(supports, verdict=VerdictValue.CONTRADICTS)
        rows = [
            (supports, True, True, VerdictValue.CONTRADICTS, settle.PairOutcome.ESTABLISHED, ()),
            (supports, True, False, None, settle.PairOutcome.ESTABLISHED, ()),
            (supports, True, True, VerdictValue.SUPPORTS, settle.PairOutcome.INCOHERENT, (R.CONTROL_INCOHERENT,)),
            (supports, True, True, VerdictValue.UNCLEAR, settle.PairOutcome.INCOHERENT, (R.CONTROL_INCOHERENT,)),
            (supports, True, True, None, settle.PairOutcome.CONTROL_MISSING, (R.APPRAISAL_MISSING,)),
            (contradicts, True, True, VerdictValue.CONTRADICTS, settle.PairOutcome.UNINFORMATIVE,
             (R.APPRAISAL_CONTRADICTS,)),
            (contradicts, True, True, VerdictValue.SUPPORTS, settle.PairOutcome.CONTRADICTED,
             (R.APPRAISAL_CONTRADICTS,)),
            (dataclasses.replace(supports, verdict=VerdictValue.QUALIFIED, qualifiers=(Qualifier2.OTHER_OCCASION,
                                                                                       Qualifier2.HEDGED)),
             True, True, VerdictValue.CONTRADICTS, settle.PairOutcome.QUALIFIED,
             (R.APPRAISAL_QUALIFIED_HEDGED, R.APPRAISAL_QUALIFIED_OTHER_OCCASION)),
            (dataclasses.replace(supports, qualifiers=(Qualifier2.PLANNED_ONLY,)), True, True,
             VerdictValue.CONTRADICTS, settle.PairOutcome.QUALIFIED, (R.APPRAISAL_QUALIFIED_PLANNED_ONLY,)),
            (dataclasses.replace(supports, verdict=VerdictValue.UNCLEAR), True, True, VerdictValue.CONTRADICTS,
             settle.PairOutcome.UNCLEAR, (R.APPRAISAL_UNCLEAR,)),
            (dataclasses.replace(supports, attached=Attached.NO), True, True, VerdictValue.CONTRADICTS,
             settle.PairOutcome.DETACHED, (R.APPRAISAL_DETACHED,)),
            (supports, False, True, VerdictValue.CONTRADICTS, settle.PairOutcome.DETACHED, (R.APPRAISAL_DETACHED,)),
            (None, False, True, VerdictValue.CONTRADICTS, settle.PairOutcome.MISSING, (R.APPRAISAL_MISSING,)),
        ]
        for found, evidence, controlled, control, outcome, reasons in rows:
            with self.subTest(verdict=found, controlled=controlled, control=control):
                self.assertEqual(settle.appraise(found, evidence, controlled, control), (outcome, reasons))

    def test_every_qualifier_of_pass_two_has_its_reason(self):
        self.assertEqual(set(settle.APPRAISAL_QUALIFIED), set(Qualifier2))
        for qualifier, reason in settle.APPRAISAL_QUALIFIED.items():
            self.assertEqual(reason.value, f'appraisal_qualified:{qualifier.value}')


class WiringTests(Case):
    """The truth table reached through the whole pipeline: a real claim set, pass 2's verdict on one fact's claim and
    control varied, the settled result the table's."""

    def test_a_controlled_fact_through_every_verdict_pattern(self):
        prepared = Prepared(NOTE, note_answer())
        item = prepared.appraised(A.KIND, 'E2')
        self.assertIsNotNone(item.control)  # KIND_SIBLINGS: snare's control is the emr form (3.2.3)
        patterns = {
            'faithful': ({}, Result.SUPPORTED, ()),
            'claim contradicted': ({'kind@E2/0': {'value': 'contradicts'}}, Result.UNRESOLVED,
                                   (R.APPRAISAL_CONTRADICTS,)),
            'control supported': ({'kind@E2/0/control': {'value': 'supports'}}, Result.UNRESOLVED,
                                  (R.CONTROL_INCOHERENT,)),
            'control without a verdict': ({'kind@E2/0/control': None}, Result.UNRESOLVED, (R.APPRAISAL_MISSING,)),
            'claim without a verdict': ({'kind@E2/0': None}, Result.UNRESOLVED, (R.APPRAISAL_MISSING,)),
            'claim detached': ({'kind@E2/0': {'attached': 'no'}}, Result.UNRESOLVED, (R.APPRAISAL_DETACHED,)),
            'evidence elsewhere': ({'kind@E2/0': {'evidence': ['S1']}}, Result.UNRESOLVED, (R.APPRAISAL_DETACHED,)),
            'no evidence': ({'kind@E2/0': {'evidence': []}}, Result.UNRESOLVED, (R.APPRAISAL_DETACHED,)),
            'supports naming a qualifier': ({'kind@E2/0': {'qualifiers': ['named_only']}}, Result.UNRESOLVED,
                                            (R.APPRAISAL_QUALIFIED_NAMED_ONLY,)),
            'qualified naming none': ({'kind@E2/0': {'value': 'qualified'}}, Result.UNRESOLVED,
                                      (R.APPRAISAL_QUALIFIED,)),
            'unclear': ({'kind@E2/0': {'value': 'unclear'}}, Result.UNRESOLVED, (R.APPRAISAL_UNCLEAR,)),
            'both contradicted': ({'kind@E2/0': {'value': 'contradicts'}, 'kind@E2/0/control': {'value': 'contradicts'}},
                                  Result.UNRESOLVED, (R.APPRAISAL_CONTRADICTS,)),
        }
        for name, (answers, result, reasons) in patterns.items():
            with self.subTest(pattern=name):
                out = prepared.settle(overriding(**answers))
                fact = at(out.events, 'events', 'E2', 'kind')
                self.assertSettled(fact, result, *reasons)
                self.assertEqual(fact.appraisal.claim, item.claim)
                self.assertEqual(fact.appraisal.control.claim, item.control)
                stored(prepared, out)

    def test_an_uncontrolled_fact_is_decided_by_its_claim_alone(self):
        prepared = Prepared(NOTE, note_answer())
        item = prepared.appraised(A.DATE_OF_SERVICE, '')
        self.assertIsNone(item.control)  # UNCONTROLLED (3.2.3)
        self.assertSettled(at(prepared.settle().events, 'encounter', 'date_of_service'), Result.SUPPORTED)
        out = prepared.settle(overriding(**{'date_of_service@/0': {'value': 'contradicts'}}))
        self.assertSettled(at(out.events, 'encounter', 'date_of_service'), Result.UNRESOLVED, R.APPRAISAL_CONTRADICTS)
        self.assertIsNone(at(out.events, 'encounter', 'date_of_service').appraisal.control)

    def test_a_negated_claim_establishes_negated(self):
        prepared, out = run(NOTE, note_answer())
        self.assertSettled(at(out.events, 'events', 'E4', 'status'), Result.NEGATED)
        self.assertEqual(at(out.events, 'events', 'E4', 'status').claim.value, 'performed')

    def test_a_fact_outside_claimed_is_unappraised_and_never_established(self):
        prepared, out = run(NOTE, note_answer())
        # sections and people are no CLAIMED object (3.2.1): their facts settle unappraised
        self.assertSettled(at(out.events, 'sections', 'N2', 'occasion'), Result.UNRESOLVED, R.UNAPPRAISED)
        self.assertSettled(at(out.events, 'people', 'P2', 'role'), Result.UNRESOLVED, R.UNAPPRAISED)
        # a statement's entry is not claimed (CLAIMED's statement class lists none)
        self.assertSettled(at(out.events, 'events', 'E4', 'entry'), Result.UNRESOLVED, R.UNAPPRAISED)


class ProbeTests(Case):
    """Survey 1's probes (FINAL-V2 3.8), each ending unresolved."""

    def test_probe_a_a_denial_filed_as_a_performed_snare(self):
        """'Neither biopsy nor snare polypectomy was performed.' filed as a performed snare, words 'polypectomy was
        performed': pass 2 contradicts 'This act was carried out' against the whole sentence and supports its control,
        so the status is unresolved."""
        data = colonoscopy(PROBE_A, event('E2', ['S5'], 'snare polypectomy', 'polypectomy was performed', 'snare',
                                          session=[fact('X1', src(['S5']))]))
        prepared = Prepared(PROBE_A, data)
        item = prepared.appraised(A.STATUS, 'E2')
        self.assertIn('S5', prepared.claim_set.claim(item.claim).units)  # the sentence closure, its negator in it
        out = prepared.settle(overriding(**{'status@E2/0': {'value': 'contradicts'},
                                            'status@E2/0/control': {'value': 'supports'}}))
        self.assertSettled(at(out.events, 'events', 'E2', 'status'), Result.UNRESOLVED, R.APPRAISAL_CONTRADICTS)
        stored(prepared, out)

    def test_probe_b_a_history_act_with_no_time_words(self):
        """'History: polypectomy with a hot snare in the rectum in 2023.': never current by default."""
        history = lambda occasion, role='history': section(  # noqa: E731
            'N2', src(['S4'], 'History:', 'section'), fact('documenting_clinician', frame(['S3'])),
            role=[fact(role, src(['S4'], 'History:', 'section'))], occasion=[occasion])
        act = lambda **over: event('E2', ['S4'], 'hot snare', 'polypectomy', 'snare',  # noqa: E731
                                   session=[fact('X1', src(['S4']))], **over)
        cases = {
            # the history part's occasion filed from the document frame: K7 makes it unresolved, and so the act's
            'the occasion framed by the document': (
                colonoscopy(PROBE_B, act(), extra_sections=[history(fact('on_date_of_service', frame(['S2'])))],
                            findings_unit='S5'), {}, (R.FRAME_ROLE,)),
            # the role filed wrongly too: pass 2 contradicts 'done on the date of service' against the sentence
            'the role filed wrongly too': (
                colonoscopy(PROBE_B, act(), extra_sections=[history(fact('on_date_of_service', frame(['S2'])),
                                                                    'findings')], findings_unit='S5'),
                {'date_relation@E2/0': {'value': 'contradicts'}}, (R.APPRAISAL_CONTRADICTS,)),
            # its own date 2023 against the inherited on_date_of_service: L1 (DECISIONS D193)
            'a date 2023': (
                colonoscopy(PROBE_B, act(date=[fact('2023', src(['S4'], '2023'))]),
                            extra_sections=[history(fact('on_date_of_service', frame(['S2'])), 'findings')],
                            findings_unit='S5'), {}, (R.LITERAL_MISMATCH,)),
        }
        for name, (data, answers, reasons) in cases.items():
            with self.subTest(case=name):
                data['sections'] = [data['sections'][0], data['sections'][2], data['sections'][1]]  # document order
                prepared = Prepared(PROBE_B, data)
                out = prepared.settle(overriding(**answers))
                fact_ = at(out.events, 'events', 'E2', 'date_relation')
                self.assertEqual(fact_.result, Result.UNRESOLVED)
                self.assertTrue(set(reasons) <= set(fact_.reasons), fact_.reasons)
                self.assertEqual(fact_.claim.inherited_from, 'N2')
                stored(prepared, out)

    def test_probe_c_a_broad_denial_filed_exceptive_with_no_excepts(self):
        """'No polyps were removed.' filed exceptive with words 'No': K1 makes the breadth unresolved."""
        data = colonoscopy(PROBE_C,
                           event('E2', ['S5'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S5']))],
                                 target__places=[fact('rectum', src(['S5'], 'rectum'))]),
                           event('E3', ['S6'], 'removed', 'No polyps were removed', 'removal', state='negated',
                                 session=[fact('X1', src(['S6']))], scope__breadth=[fact('exceptive', src(['S6'], 'No'))]))
        prepared, out = run(PROBE_C, data)
        self.assertSettled(at(out.events, 'events', 'E3', 'scope.breadth'), Result.UNRESOLVED, R.STRUCTURE_EXCEPTIVE)
        stored(prepared, out)

    def test_probe_d_a_seen_valve_filed_as_an_absent_organ(self):
        """'The ileocecal valve was seen.' filed as an absent organ: K4 makes it and the reach at the valve unresolved;
        with no reach, pass 2 contradicts 'The ileocecal valve is surgically absent.' or it is not even claimed."""
        absent = {'id': 'Y1', 'type': fact('surgically_absent', src(['S5'], 'The ileocecal valve was seen')),
                  'organ': [fact('ileocecal_valve', src(['S5'], 'ileocecal valve'))], 'subtype': [], 'joins': []}
        data = colonoscopy(PROBE_D, anatomy=[absent], reached='ileocecal_valve',
                           reached_words='advanced to the ileocecal valve')
        prepared, out = run(PROBE_D, data)
        for path in (('anatomy', 'Y1', 'type'), ('anatomy', 'Y1', 'organ'), ('sessions', 'X1', 'reached', 0)):
            with self.subTest(fact=path):
                self.assertSettled(at(out.events, *path), Result.UNRESOLVED, R.ANATOMY_CONFLICT)
        stored(prepared, out)
        data['sessions'][0]['reached'] = []
        prepared, out = run(PROBE_D, data)
        self.assertEqual(at(out.events, 'anatomy', 'Y1', 'type').result, Result.UNRESOLVED)

    def test_probe_e_an_injection_worded_was_seen_part_of_with_no_citation(self):
        """An injection worded 'was seen', part_of E1 with no citation: part_of fails S2 (no step); the kind claim is
        contradicted against 'A 7 mm polyp was seen in the sigmoid colon.'"""
        data = colonoscopy(PROBE_E, event('E2', ['S5'], 'polyp', 'was seen', 'injection',
                                          session=[fact('X1', src(['S5']))], part_of=[fact('E1')],
                                          part_relation=[fact('step_of', src(['S5']))]))
        prepared = Prepared(PROBE_E, data)
        out = prepared.settle(overriding(**{'kind@E2/0': {'value': 'contradicts'},
                                            'kind@E2/0/control': {'value': 'contradicts'}}))
        self.assertSettled(at(out.events, 'events', 'E2', 'part_of'), Result.UNRESOLVED, R.SHAPE_INCONSISTENT)
        self.assertSettled(at(out.events, 'events', 'E2', 'kind'), Result.UNRESOLVED, R.APPRAISAL_CONTRADICTS)
        stored(prepared, out)


def card_of(prepared, family, name):
    """The card id of an object in the request (pass 2 names a session by its card)."""
    return next(card for card, item in prepared.claim_set.objects.items() if item == (family, name))


def unlisted_entry(units, what, kind='', session=''):
    return {'units': list(units), 'what': what, 'kind': kind, 'session': session}


class UnlistedTests(Case):
    """3.2.6's unlisted statements [R:SC-A][R:HO-6]: dropped only by an event of the same nature, a compatible kind and
    the named session; every drop recorded with the event that absorbed it; every other entry kept."""

    def test_sc_a_an_exchange_whose_removal_only_pass_two_reports_is_kept(self):
        data = answer(
            sections=[opening(), labelled('N1', 'S4', 'Findings:', 'findings')],
            sessions=[session('X1', fact('ercp', src(['S4'], 'duodenoscope')), examination=[fact('E1', src(['S4']))])],
            events=[event('E1', ['S4'], 'duodenoscope', 'was advanced', 'examination',
                          session=[fact('X1', src(['S4']))]),
                    event('E2', ['S5'], 'new plastic stent', 'replaced', 'stent', session=[fact('X1', src(['S5']))])])
        prepared = Prepared(EXCHANGE, data)
        entry = unlisted_entry(['S5'], 'act', 'stent_removal', card_of(prepared, F.SESSION, 'X1'))
        out = prepared.settle(unlisted=[entry])
        self.assertEqual(list(out.events['unlisted']), [settle.Unlisted(('S5',), UnlistedWhat.ACT, Kind.STENT_REMOVAL,
                                                                        'X1')])
        self.assertEqual(out.verification.unlisted, settle.UnlistedReport(kept=1, dropped=()))
        stored(prepared, out)

    def test_sc_a_a_biopsy_and_a_snare_in_one_sentence_the_snare_only_pass_two_reports_is_kept(self):
        data = colonoscopy(BOTH, event('E2', ['S5'], 'biopsied', 'was biopsied', 'biopsy',
                                       session=[fact('X1', src(['S5']))]))
        prepared = Prepared(BOTH, data)
        out = prepared.settle(unlisted=[unlisted_entry(['S5'], 'act', 'snare', card_of(prepared, F.SESSION, 'X1'))])
        self.assertEqual([entry.kind for entry in out.events['unlisted']], [Kind.SNARE])
        self.assertEqual(out.verification.unlisted.dropped, ())

    def test_sc_a_a_shared_denial_anchor_the_tattoo_only_pass_two_reports_is_kept(self):
        data = note_answer()
        data['events'] = [item for item in data['events'] if item['id'] != 'E5']
        prepared = Prepared(NOTE, data)
        out = prepared.settle(unlisted=[unlisted_entry(['S9'], 'denial', 'tattoo', card_of(prepared, F.SESSION,
                                                                                           'X1'))])
        self.assertEqual(list(out.events['unlisted']), [settle.Unlisted(('S9',), UnlistedWhat.DENIAL, Kind.TATTOO,
                                                                        'X1')])
        stored(prepared, out)

    def test_an_entry_of_the_same_nature_and_kind_is_dropped_with_the_event_that_absorbed_it(self):
        prepared = Prepared(NOTE, note_answer())
        x1, x2 = card_of(prepared, F.SESSION, 'X1'), card_of(prepared, F.SESSION, 'X2')
        cases = {
            'the same kind and session': (unlisted_entry(['S12'], 'act', 'biopsy', x2), 'E7'),
            'no session named': (unlisted_entry(['S12'], 'act', 'biopsy'), 'E7'),
            'an umbrella of the kind': (unlisted_entry(['S7'], 'act', 'removal', x1), 'E2'),
            'a restatement unit': (unlisted_entry(['S13'], 'act', 'snare'), 'E2'),
            'the same denial': (unlisted_entry(['S9'], 'denial', 'tattoo', x1), 'E5'),
            'another session': (unlisted_entry(['S12'], 'act', 'biopsy', x1), None),
            'no kind': (unlisted_entry(['S12'], 'act', '', x2), None),
            'another nature': (unlisted_entry(['S12'], 'denial', 'biopsy', x2), None),
            'a doubt no doubt of pass 1 matches': (unlisted_entry(['S12'], 'doubt', 'biopsy', x2), None),
            'another kind': (unlisted_entry(['S12'], 'act', 'hot_biopsy', x2), None),
            'a unit no event tells': (unlisted_entry(['S10'], 'act', 'biopsy'), None),
            'an unknown session card': (unlisted_entry(['S12'], 'act', 'biopsy', 'X9'), None),
        }
        for name, (entry, absorbed) in cases.items():
            with self.subTest(case=name):
                out = prepared.settle(unlisted=[entry])
                report = out.verification.unlisted
                if absorbed is None:
                    self.assertEqual((report.kept, report.dropped), (1, ()))
                    self.assertEqual(len(out.events['unlisted']), 1)
                else:
                    self.assertEqual(report.kept, 0)
                    self.assertEqual([item.event for item in report.dropped], [absorbed])
                    self.assertEqual(report.dropped[0].units, tuple(entry['units']))
                    self.assertEqual(list(out.events['unlisted']), [])
                stored(prepared, out)

    def test_a_doubt_is_absorbed_only_by_an_event_a_doubt_of_pass_one_names(self):
        data = note_answer()
        data['doubts'] = [doubt('performer', ['E7'], ['S12'], 'unclear', ['documenting_team'])]
        prepared = Prepared(NOTE, data)
        out = prepared.settle(unlisted=[unlisted_entry(['S12'], 'doubt', 'biopsy')])
        self.assertEqual([item.event for item in out.verification.unlisted.dropped], ['E7'])

    def test_an_objectless_doubt_no_anchor_holds_is_kept_as_an_unlisted_doubt(self):
        """DECISIONS D200: a malformed doubt naming no object, whose units no event's anchor includes, is kept as an
        unlisted doubt with no kind and no session (3.2.6 rule 4)."""
        data = note_answer()
        data['doubts'] = [doubt('status', ['E99'], ['S10'], 'stated')]
        prepared, out = run(NOTE, data)
        self.assertEqual(list(out.events['unlisted']), [settle.Unlisted(('S10',), UnlistedWhat.DOUBT, None, None)])
        self.assertEqual(out.verification.doubts[0].unlisted, True)
        self.assertEqual(out.verification.doubts[0].applied, 0)
        self.assertEqual(out.verification.unlisted.kept, 1)
        stored(prepared, out)

    def test_a_planned_or_attempted_event_absorbs_no_unlisted_act_or_denial(self):
        """3.2.6 drops an entry only for an event of the same nature (act, denial or doubt); a plan or an attempt is not
        a done act (1.4: "not done" is negated performed), so a planned or attempted event of the same kind, told in the
        same unit and the named session, absorbs no unlisted act, and a negated plan absorbs no unlisted denial - each
        entry is kept (the fail-closed reading; the step's notes' question). The performed event is the control."""
        def egd(text, act):
            return answer(sections=[opening(), labelled('N1', 'S4', 'Findings:', 'findings')],
                          sessions=[session('X1', fact('egd', src(['S4'], 'gastroscope')),
                                            examination=[fact('E1', src(['S4']))],
                                            reached=[fact('duodenum', src(['S4'], 'advanced to the duodenum'))])],
                          events=[event('E1', ['S4'], 'gastroscope', 'was advanced', 'examination',
                                        session=[fact('X1', src(['S4']))]), act])

        cases = {
            'a planned dilation beside an unlisted performed one': (
                PLANNED, event('E2', ['S5'], 'repeat dilation', 'is planned', 'dilation', status='planned',
                               session=[fact('X1', src(['S5']))],
                               date_relation=[fact('later_date', src(['S5'], 'in four weeks'))]), 'act', None),
            'an attempted dilation beside an unlisted performed one': (
                ATTEMPTED, event('E2', ['S5'], 'Balloon dilation', 'was attempted but not completed', 'dilation',
                                 status='attempted_not_completed', session=[fact('X1', src(['S5']))]), 'act', None),
            'a negated plan beside an unlisted denial': (
                NOT_PLANNED, event('E2', ['S5'], 'repeat dilation', 'is planned', 'dilation', status='planned',
                                   state='negated', session=[fact('X1', src(['S5']))],
                                   scope__breadth=[fact('all_of_kind', src(['S5']))]), 'denial', None),
            'the control: a performed dilation absorbs the unlisted act': (
                PLANNED, event('E2', ['S5'], 'dilated', 'was dilated', 'dilation', session=[fact('X1', src(['S5']))]),
                'act', 'E2'),
        }
        for name, (text, act, what, absorbed) in cases.items():
            with self.subTest(case=name):
                prepared = Prepared(text, egd(text, act))
                entry = unlisted_entry(['S5'], what, 'dilation', card_of(prepared, F.SESSION, 'X1'))
                out = prepared.settle(unlisted=[entry])
                self.assertIsInstance(out, settle.Settled)
                report = out.verification.unlisted
                if absorbed is None:
                    self.assertEqual(list(out.events['unlisted']),
                                     [settle.Unlisted(('S5',), UnlistedWhat(what), Kind.DILATION, 'X1')])
                    self.assertEqual((report.kept, report.dropped), (1, ()))
                else:
                    self.assertEqual(list(out.events['unlisted']), [])
                    self.assertEqual([item.event for item in report.dropped], [absorbed])
                stored(prepared, out)


class HealthTests(Case):
    """3.2.6's health [R:HO-4]: every degenerate appraisal the refutation named is refused whole, never a row."""

    def test_a_faithful_appraisal_is_healthy(self):
        prepared, out = run(NOTE, note_answer())
        health = out.verification.health
        self.assertEqual(health.refused, ())
        self.assertEqual((health.not_rejected, health.established, health.missing), (0, health.claims, 0))
        self.assertGreaterEqual(health.pairs, settle.CONTROL_ACCEPTANCE_AT_LEAST)

    def test_a_yes_man_is_refused(self):
        prepared, out = run(NOTE, note_answer(), lambda claim, role, claim_set: verdict(claim))
        self.assertIsInstance(out, settle.Unhealthy)
        self.assertIn(settle.HealthRefusal.CONTROL_ACCEPTANCE, out.health.refused)
        self.assertEqual(out.health.not_rejected, out.health.pairs)  # control acceptance 1.0

    def test_an_all_contradicts_appraisal_is_refused(self):
        prepared, out = run(NOTE, note_answer(), lambda claim, role, claim_set: verdict(claim, 'contradicts'))
        self.assertIsInstance(out, settle.Unhealthy)
        self.assertEqual(out.health.refused, (settle.HealthRefusal.ESTABLISHMENT,))
        self.assertEqual(out.health.established, 0)

    def test_an_all_qualified_appraisal_is_refused(self):
        prepared, out = run(NOTE, note_answer(), lambda claim, role, claim_set: (
            verdict(claim, 'qualified', qualifiers=['hedged']) if role == 'claim' else verdict(claim, 'contradicts')))
        self.assertEqual(out.health.refused, (settle.HealthRefusal.ESTABLISHMENT,))

    def test_an_all_detached_appraisal_is_refused(self):
        prepared, out = run(NOTE, note_answer(), lambda claim, role, claim_set: (
            verdict(claim, attached='no') if role in ('claim', 'completeness') else verdict(claim, 'contradicts')))
        self.assertIsInstance(out, settle.Unhealthy)
        self.assertEqual(out.health.refused, (settle.HealthRefusal.ESTABLISHMENT,))

    def test_too_many_claims_without_a_verdict_are_refused(self):
        prepared = Prepared(NOTE, note_answer())
        dropped = {claim.id for claim in prepared.claim_set.claims[:len(prepared.claim_set.claims) // 5]}
        out = prepared.settle(lambda claim, role, claim_set: None if claim.id in dropped else
                              faithful(claim, role, claim_set))
        self.assertIsInstance(out, settle.Unhealthy)
        self.assertIn(settle.HealthRefusal.COMPLETENESS, out.health.refused)
        self.assertEqual(out.health.missing, len(dropped))

    def test_the_thresholds_are_exact_fractions(self):
        """Above one half of the controls not rejected refuses, one half does not; below one half of the claims
        established refuses, one half does not; above one tenth without a verdict refuses, one tenth does not; and the
        first two need their minimum counts."""
        rejected_controls: set = set()

        def health(pairs, claims_, missing=0, total=None):
            ids = [f'K{index}' for index in range(1, (total or 40) + 1)]
            claim_set = mock.Mock(claims=[mock.Mock(id=name) for name in ids])
            supports = Verdict('K', VerdictValue.SUPPORTS, Attached.YES, (), ('S1',))
            contradicts = dataclasses.replace(supports, verdict=VerdictValue.CONTRADICTS)
            verdicts = {name: (None if index < missing else
                               mock.Mock(verdict=contradicts if name in rejected_controls else supports))
                        for index, name in enumerate(ids)}
            return settle.measure_health(claim_set, verdicts, pairs + claims_)

        def controlled(rejected, kept):
            rejected_controls.clear()
            rejected_controls.update(f'K{index + 1}' for index in range(rejected))
            return ([settle.Pair(f'C{index}', f'K{index + 1}', settle.PairOutcome.ESTABLISHED, ())
                     for index in range(rejected)]
                    + [settle.Pair(f'D{index}', f'K{index + 1 + rejected}', settle.PairOutcome.INCOHERENT, ())
                       for index in range(kept)])

        self.assertEqual(health(controlled(2, 2), []).refused.count(settle.HealthRefusal.CONTROL_ACCEPTANCE), 0)
        self.assertIn(settle.HealthRefusal.CONTROL_ACCEPTANCE, health(controlled(2, 3), []).refused)
        self.assertNotIn(settle.HealthRefusal.CONTROL_ACCEPTANCE, health(controlled(0, 3), []).refused)  # 3 < 4
        established = [settle.Pair(f'E{index}', None, settle.PairOutcome.ESTABLISHED, ()) for index in range(2)]
        failed = [settle.Pair(f'F{index}', None, settle.PairOutcome.DETACHED, ()) for index in range(3)]
        self.assertNotIn(settle.HealthRefusal.ESTABLISHMENT, health([], established + failed[:2]).refused)
        self.assertIn(settle.HealthRefusal.ESTABLISHMENT, health([], established + failed).refused)
        self.assertNotIn(settle.HealthRefusal.ESTABLISHMENT, health([], failed).refused)  # 3 < 4
        self.assertNotIn(settle.HealthRefusal.COMPLETENESS, health([], [], missing=4, total=40).refused)
        self.assertIn(settle.HealthRefusal.COMPLETENESS, health([], [], missing=5, total=40).refused)

    def test_a_claim_two_facts_share_is_established_only_when_every_pair_it_is_in_is(self):
        """Establishment counts a non-control claim once, established only when EVERY pair it is in is (the step's notes,
        D13): EXCEPTIVE's breadth claim is shared by the breadth (its control the all_of_kind form) and the excepted act
        (its control the covers form). Pass 2 supporting the covers form leaves the breadth's pair established and the
        excepted act's incoherent: the shared claim is not established, so establishment drops by exactly one."""
        prepared = Prepared(EXCEPTIVE, exceptive_answer())
        breadth, excepted = prepared.appraised(A.SCOPE_BREADTH, 'E3'), prepared.appraised(A.SCOPE_EXCEPTS, 'E3')
        self.assertEqual(breadth.claim, excepted.claim)
        self.assertNotEqual(breadth.control, excepted.control)
        faithful_health = prepared.settle().verification.health
        out = prepared.settle(overriding(**{'scope.excepts@E3/0/control': {'value': 'supports'}}))
        self.assertIsInstance(out, settle.Settled)
        health = out.verification.health
        pairs = {(pair.claim, pair.control): pair.outcome for pair in settle.pairs_of(
            prepared.claim_set, settle.verdicts_of(prepared.claim_set, prepared.appraisal(
                overriding(**{'scope.excepts@E3/0/control': {'value': 'supports'}}))))}
        self.assertEqual(pairs[(breadth.claim, breadth.control)], settle.PairOutcome.ESTABLISHED)
        self.assertEqual(pairs[(excepted.claim, excepted.control)], settle.PairOutcome.INCOHERENT)
        self.assertEqual(health.claims, faithful_health.claims)
        self.assertEqual(faithful_health.established, faithful_health.claims)
        self.assertEqual(health.established, faithful_health.established - 1)
        self.assertEqual(health.not_rejected, faithful_health.not_rejected + 1)
        self.assertSettled(at(out.events, 'events', 'E3', 'scope.breadth'), Result.SUPPORTED)  # its own pair
        stored(prepared, out)

    def test_pair_controls_are_not_counted_as_controls(self):
        """Hand-off 2c#12: control acceptance is over claim/control pairs, never over ClaimSet.controls - a pair
        control that a faithful reading supports (the act really is at that place) refuses nothing."""
        text = ('SYNTHETIC COLONOSCOPY REPORT\n'
                'Date of service: 03/14/2031\n'
                'Endoscopist: Corvin Ashdale, MD (fictional)\n'
                '\n'
                'Findings: The colonoscope was advanced to the cecum.\n'
                'Biopsies of the ascending colon and the rectum were taken with cold forceps.\n'
                'No biopsies were taken from the transverse colon.\n')
        data = colonoscopy(text,
                           event('E2', ['S5'], 'Biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S5']))],
                                 target__places=[fact('ascending_colon', src(['S5'], 'ascending colon'))]),
                           event('E3', ['S6'], 'biopsies', 'No biopsies were taken', 'biopsy', state='negated',
                                 session=[fact('X1', src(['S6']))],
                                 scope__breadth=[fact('single_target', src(['S6'], 'from the transverse colon'))],
                                 target__places=[fact('transverse_colon', src(['S6'], 'transverse colon'))]))
        prepared = Prepared(text, data)
        self.assertTrue(prepared.claim_set.pair_controls)
        pairs = {pair.claim for pair in prepared.claim_set.pair_controls}
        out = prepared.settle(lambda claim, role, claim_set: verdict(claim) if claim.id in pairs else
                              faithful(claim, role, claim_set))
        self.assertIsInstance(out, settle.Settled)
        self.assertEqual(out.verification.health.not_rejected, 0)
        self.assertEqual(out.verification.health.pairs,
                         len({(item.claim, item.control) for item in prepared.claim_set.appraised if item.control}))
        roles = {claim.id: claim.role for claim in out.events['claims']}
        self.assertTrue(all(roles[claim] is settle.ClaimRole.PAIR_CONTROL for claim in pairs))
        stored(prepared, out)

    def test_no_appraisal_is_settled_under_unpinned_or_changed_thresholds(self):
        prepared = Prepared(NOTE, note_answer())
        appraisal = prepared.appraisal()
        for pin in ('', '0' * 64):
            with self.subTest(pin=pin), mock.patch.object(interpretation, 'HEALTH_THRESHOLDS_SHA256', pin):
                with self.assertRaises(RuntimeError):
                    settle.settle(prepared.read, prepared.checked, prepared.claim_set, prepared.request.indistinct,
                                  appraisal, USAGE)
        with mock.patch.object(settle, 'CONTROL_ACCEPTANCE_AT_LEAST', 5), \
                mock.patch.object(interpretation, 'HEALTH_THRESHOLDS_SHA256', HEALTH_PIN):
            with self.assertRaises(RuntimeError):  # a moved threshold changes the document, so the pin refuses
                settle.check_pin()
        self.assertEqual(HEALTH_PIN, '%s' % jsonschema.sha256_of(settle.health_document()))


class VocabularyTests(Case):
    def test_k3_fires_with_the_real_vocabulary_an_egd_act_at_the_sigmoid_colon(self):
        """DECISIONS D192: K3 reads v1's FAMILY_REGIONS by value through the real Vocabulary - an act at the sigmoid
        colon in an upper endoscopy session makes the act's session fact unresolved, and nothing is moved."""
        data = note_answer()
        e7 = next(item for item in data['events'] if item['id'] == 'E7')
        e7['target']['places'] = [fact('sigmoid_colon', src(['S12'], 'gastric antrum'))]
        prepared, out = run(NOTE, data)
        self.assertEqual(prepared.checked.findings[FactKey(F.EVENT, 'E7', A.SESSION, 0)], (R.SESSION_UNREACHABLE,))
        self.assertSettled(at(out.events, 'events', 'E7', 'session'), Result.UNRESOLVED, R.SESSION_UNREACHABLE)
        self.assertEqual(at(out.events, 'events', 'E7', 'session').claim.value, 'X2')  # never moved
        self.assertSettled(at(out.events, 'events', 'E7', 'target.places', 0), Result.SUPPORTED)
        stored(prepared, out)
        # the control: at the gastric antrum the act's session stands
        prepared, out = run(NOTE, note_answer())
        self.assertSettled(at(out.events, 'events', 'E7', 'session'), Result.SUPPORTED)

    def test_the_vocabulary_is_the_ruled_tables(self):
        vocabulary = checks.VOCABULARY
        self.assertIs(vocabulary.reach, catalogue.FAMILY_REACH)
        self.assertIs(vocabulary.covers, catalogue.covers)
        self.assertIs(vocabulary.endoscopic, catalogue.ENDOSCOPIC_FAMILIES)
        self.assertIs(vocabulary.family_admits, checks.family_admits)


class DateOfServiceTests(Case):
    """DECISIONS D187: the date of service is one settled fact; the integration's O13: its checks over every side."""

    def dates(self, when, doubts=()):
        data = answer(sections=[opening(), labelled('N1', 'S5', 'Findings:', 'findings')],
                      sessions=[session('X1', fact('colonoscopy', src(['S5'], 'colonoscope')),
                                        examination=[fact('E1', src(['S5']))])],
                      events=[event('E1', ['S5'], 'colonoscope', 'was advanced', 'examination',
                                    session=[fact('X1', src(['S5']))])], when=when, doubts=doubts)
        prepared, out = run(DATES, data)
        return prepared, out, at(out.events, 'encounter', 'date_of_service')

    def test_stated_is_supported(self):
        prepared, out, when = self.dates({'state': 'stated', 'value': '2031-03-14',
                                          'sources': [frame(['S2'], '03/14/2031')], 'options': []})
        self.assertSettled(when, Result.SUPPORTED)
        self.assertEqual((when.claim.state, when.claim.value, when.claim.options), (FactState.SUPPORTED, '2031-03-14',
                                                                                    ()))
        self.assertEqual([(item.value, item.precision.value) for item in when.checks.literals], [('2031-03-14', 'day')])
        self.assertIsNone(when.appraisal.control)  # UNCONTROLLED
        fields, factset = stored(prepared, out)
        dates = engine_facts.encounter_dates(store.textfree_v2(store.load_v2(
            fields, text_sha256=fields['text_sha256'], response_sha256='3' * 64, appraisal_response_sha256='5' * 64)))
        self.assertTrue(dates.checks_passed)

    def test_several_is_contradicted_each_date_an_option_with_its_sources(self):
        several = {'state': 'several', 'value': '', 'sources': [frame(['S2'], '03/14/2031'), frame(['S4'], '03/15/2031')],
                   'options': [{'value': '2031-03-14', 'sources': [frame(['S2'], '03/14/2031')]},
                               {'value': '2031-03-15', 'sources': [frame(['S4'], '03/15/2031')]}]}
        prepared, out, when = self.dates(several)
        self.assertSettled(when, Result.CONTRADICTED, R.CONTRADICTED_BY_PASS1)
        self.assertEqual((when.claim.state, when.claim.value), (FactState.CONTRADICTED, ''))
        self.assertEqual([(option.value, [source.units for source in option.sources]) for option in when.claim.options],
                         [('2031-03-14', [('S2',)]), ('2031-03-15', [('S4',)])])
        self.assertIsNone(when.appraisal)  # never appraised
        self.assertEqual((when.checks.integrity, when.checks.literal), (CheckStatus.OK, CheckStatus.OK))
        stored(prepared, out)

    def test_a_side_that_fails_integrity_fails_the_fact_and_is_not_contradicted(self):
        several = {'state': 'several', 'value': '', 'sources': [frame(['S2'], '03/14/2031'), frame(['S4', 'S99'])],
                   'options': [{'value': '2031-03-14', 'sources': [frame(['S2'], '03/14/2031')]},
                               {'value': '2031-03-15', 'sources': [frame(['S4', 'S99'])]}]}
        prepared, out, when = self.dates(several)
        self.assertEqual(when.result, Result.UNRESOLVED)
        self.assertIn(R.UNIT_UNKNOWN, when.reasons)
        self.assertEqual(when.checks.integrity, CheckStatus.FAILED)
        fields, _factset = stored(prepared, out)
        dates = engine_facts.encounter_dates(store.textfree_v2(store.load_v2(
            fields, text_sha256=fields['text_sha256'], response_sha256='3' * 64, appraisal_response_sha256='5' * 64)))
        self.assertFalse(dates.checks_passed)

    def test_a_side_whose_words_state_another_date_fails_the_literal_check(self):
        several = {'state': 'several', 'value': '', 'sources': [frame(['S2'], '03/14/2031'), frame(['S4'], '03/15/2031')],
                   'options': [{'value': '2031-03-14', 'sources': [frame(['S2'], '03/14/2031')]},
                               {'value': '2031-03-16', 'sources': [frame(['S4'], '03/15/2031')]}]}
        prepared, out, when = self.dates(several)
        self.assertEqual(when.result, Result.CONTRADICTED)  # row 1 reads the sides' integrity, not L1
        self.assertIn(R.LITERAL_MISMATCH, when.reasons)
        self.assertEqual(when.checks.literal, CheckStatus.FAILED)

    def test_a_side_whose_own_source_fails_i2_is_not_contradicted_though_the_facts_sources_pass(self):
        """3.3 row 1 reads EVERY side's sources: a side's own source that is not among the fact's sources (the reader
        does not require the union, 1.3) and whose words do not lie in its unit (I2) fails the side's integrity, so the
        fact is unresolved, never contradicted - although every source in the fact's own list locates."""
        several = {'state': 'several', 'value': '', 'sources': [frame(['S2'], '03/14/2031')],
                   'options': [{'value': '2031-03-14', 'sources': [frame(['S2'], '03/14/2031')]},
                               {'value': '2031-03-15', 'sources': [frame(['S4'], '04/15/2031')]}]}
        prepared, out, when = self.dates(several)
        self.assertEqual(prepared.read.fact(FactKey(F.ENCOUNTER, '', A.DATE_OF_SERVICE, 0)).reasons, ())
        self.assertTrue(all(not prepared.checked.citations[source].reasons
                            for source in prepared.read.fact(FactKey(F.ENCOUNTER, '', A.DATE_OF_SERVICE, 0)).fact.sources))
        self.assertEqual(when.result, Result.UNRESOLVED)
        self.assertIn(R.WORDS_NOT_IN_UNITS, when.reasons)
        self.assertNotIn(R.CONTRADICTED_BY_PASS1, when.reasons)
        self.assertEqual(when.checks.integrity, CheckStatus.FAILED)
        stored(prepared, out)

    def test_not_stated_is_silent(self):
        prepared, out, when = self.dates({'state': 'not_stated', 'value': '', 'sources': [], 'options': []})
        self.assertSettled(when, Result.UNKNOWN, R.SILENT)
        self.assertEqual((when.claim.state, when.sources, when.appraisal), (None, (), None))
        stored(prepared, out)

    def test_a_doubt_about_the_date_of_service_is_row_two(self):
        prepared, out, when = self.dates({'state': 'stated', 'value': '2031-03-14',
                                          'sources': [frame(['S2'], '03/14/2031')], 'options': []},
                                         doubts=[doubt('date_of_service', [], ['S4'], 'unclear', ['2031-03-15'])])
        self.assertSettled(when, Result.UNKNOWN, R.DOUBT_UNCLEAR)
        self.assertEqual(when.claim.value, '2031-03-14')  # the value kept for the doubt arm (4.2)
        self.assertEqual(out.events['doubts'][0].readings, ('2031-03-15',))
        stored(prepared, out)


def event_of(data, name):
    return next(item for item in data['events'] if item['id'] == name)


def section_of(data, name):
    return next(item for item in data['sections'] if item['id'] == name)


class InheritanceTests(Case):
    """1.5 and 3.3: an act's effective date relation, performer and performer_person, and its entry, settled per act
    from its containing section's fact."""

    def test_an_inherited_fact_is_the_sections_claim_stored_and_appraised_per_act(self):
        prepared, out = run(NOTE, note_answer())
        for name in ('E1', 'E2', 'E3'):
            for attribute, value in (('date_relation', 'on_date_of_service'), ('performer', 'documenting_team'),
                                     ('entry', 'documenting_clinician')):
                with self.subTest(event=name, attribute=attribute):
                    fact_ = at(out.events, 'events', name, attribute)
                    self.assertSettled(fact_, Result.SUPPORTED)
                    self.assertEqual((fact_.claim.value, fact_.claim.inherited_from), (value, 'N2'))
                    claim = next(item for item in out.events['claims'] if item.id == fact_.appraisal.claim)
                    self.assertEqual((claim.subject, claim.attribute.value), (name, attribute))
        when = at(out.events, 'events', 'E2', 'date_relation')
        self.assertEqual([source.units for source in when.sources], [('S2',)])  # N2's occasion's source
        self.assertEqual([(item.value, item.precision.value) for item in when.checks.literals], [('2031-03-14', 'day')])
        self.assertSettled(at(out.events, 'events', 'E7', 'date_relation'), Result.SUPPORTED)
        self.assertEqual(at(out.events, 'events', 'E7', 'date_relation').claim.inherited_from, 'N3')
        stored(prepared, out)

    def test_a_doubt_about_a_sections_fact_reaches_every_act_it_governs_and_none_other(self):
        data = note_answer()
        data['doubts'] = [doubt('date_relation', ['N2'], ['S6'], 'unclear', ['earlier_date'])]
        prepared, out = run(NOTE, data)
        self.assertSettled(at(out.events, 'sections', 'N2', 'occasion'), Result.UNKNOWN, R.DOUBT_UNCLEAR)
        for name in ('E1', 'E2', 'E3', 'E4', 'E5'):
            with self.subTest(event=name):
                fact_ = at(out.events, 'events', name, 'date_relation')
                self.assertSettled(fact_, Result.UNKNOWN, R.DOUBT_UNCLEAR)
                self.assertEqual(fact_.claim.value, 'on_date_of_service')  # kept for the doubt arm
                self.assertIsNone(fact_.appraisal)  # never claimed
        self.assertSettled(at(out.events, 'events', 'E7', 'date_relation'), Result.SUPPORTED)  # N3's act
        self.assertSettled(at(out.events, 'events', 'E2', 'performer'), Result.SUPPORTED)  # another attribute
        stored(prepared, out)

    def test_a_doubt_that_names_the_act_applies_to_the_acts_fact_alone(self):
        data = note_answer()
        data['doubts'] = [doubt('date_relation', ['E2'], ['S7'], 'stated')]
        prepared, out = run(NOTE, data)
        self.assertSettled(at(out.events, 'events', 'E2', 'date_relation'), Result.UNKNOWN, R.DOUBT_STATED)
        self.assertSettled(at(out.events, 'events', 'E3', 'date_relation'), Result.SUPPORTED)
        self.assertSettled(at(out.events, 'sections', 'N2', 'occasion'), Result.UNRESOLVED, R.UNAPPRAISED)

    def test_a_section_framed_from_outside_its_role_unresolves_what_its_acts_inherit(self):
        """K7 on the section's occasion and performer (a history part framed by the document) reaches every act inside
        it through inheritance (3.1's cross-object rule)."""
        data = note_answer()
        section_of(data, 'N2')['role'] = [fact('history', src(['S6'], 'Findings:', 'section'))]
        prepared, out = run(NOTE, data)
        for name in ('E1', 'E2', 'E3'):
            for attribute in ('date_relation', 'performer'):
                with self.subTest(event=name, attribute=attribute):
                    self.assertSettled(at(out.events, 'events', name, attribute), Result.UNRESOLVED, R.FRAME_ROLE)
        self.assertSettled(at(out.events, 'events', 'E2', 'entry'), Result.SUPPORTED)  # the owner is not framed
        stored(prepared, out)

    def test_an_act_attached_to_no_section_inherits_nothing(self):
        data = note_answer()
        section_of(data, 'N2')['start'] = src(['S6'], 'Results:', 'section')  # unlocated: N1 and N2 lose their spans
        prepared, out = run(NOTE, data)
        self.assertNotIn('E2', prepared.checked.containing)
        for attribute in ('date_relation', 'performer', 'performer_person', 'entry'):
            with self.subTest(attribute=attribute):
                fact_ = at(out.events, 'events', 'E2', attribute)
                self.assertSettled(fact_, Result.UNKNOWN, R.SILENT, R.INHERIT_UNATTACHED)
                self.assertEqual((fact_.claim.state, fact_.claim.inherited_from), (None, None))
        stored(prepared, out)

    def test_a_statements_performer_is_its_own_and_its_date_relation_inherits(self):
        prepared, out = run(NOTE, note_answer())
        self.assertSettled(at(out.events, 'events', 'E4', 'performer'), Result.UNKNOWN, R.SILENT)
        self.assertIsNone(at(out.events, 'events', 'E4', 'performer').claim.inherited_from)
        self.assertSettled(at(out.events, 'events', 'E4', 'date_relation'), Result.SUPPORTED)
        self.assertEqual(at(out.events, 'events', 'E4', 'date_relation').claim.inherited_from, 'N2')

    def test_an_acts_own_date_is_judged_against_its_inherited_relation_and_stored_with_it(self):
        """DECISIONS D193: an act with no date relation of its own and a supported date - its date's literal is
        judged against the relation it inherits, and the per-act fact stores both literals."""
        data = note_answer()
        event_of(data, 'E2')['date'] = [fact('2027', src(['S5'], '2027'))]
        prepared, out = run(NOTE, data)
        fact_ = at(out.events, 'events', 'E2', 'date_relation')
        self.assertSettled(fact_, Result.UNRESOLVED, R.LITERAL_MISMATCH)
        self.assertEqual([(item.value, item.precision.value) for item in fact_.checks.literals],
                         [('2031-03-14', 'day'), ('2027', 'year')])
        self.assertSettled(at(out.events, 'events', 'E3', 'date_relation'), Result.SUPPORTED)  # its own fact only
        self.assertSettled(at(out.events, 'sections', 'N2', 'occasion'), Result.UNRESOLVED, R.UNAPPRAISED)
        stored(prepared, out)

    def test_a_contradicted_section_fact_is_contradicted_for_its_acts(self):
        data = note_answer()
        section_of(data, 'N2')['occasion'] = [fact('', frame(['S2']), src(['S5'], '2027', 'placing'),
                                                   state='contradicted',
                                                   options=[{'value': 'on_date_of_service', 'sources': [frame(['S2'])]},
                                                            {'value': 'earlier_date',
                                                             'sources': [src(['S5'], '2027', 'placing')]}])]
        prepared, out = run(NOTE, data)
        fact_ = at(out.events, 'events', 'E2', 'date_relation')
        self.assertEqual((fact_.result, fact_.reasons[0]), (Result.CONTRADICTED, R.CONTRADICTED_BY_PASS1))
        self.assertEqual([option.value for option in fact_.claim.options], ['on_date_of_service', 'earlier_date'])
        self.assertEqual(fact_.claim.inherited_from, 'N2')
        stored(prepared, out)


class DoubtTests(Case):
    """The doubt mapping (1.3, 3.3 rows 1-2; DECISIONS D200): a doubt only demotes, its value kept."""

    def test_each_basis(self):
        for basis, result, reasons in (('stated', Result.UNKNOWN, (R.DOUBT_STATED,)),
                                       ('unclear', Result.UNKNOWN, (R.DOUBT_UNCLEAR,)),
                                       ('conflict', Result.CONTRADICTED, (R.CONTRADICTED_BY_PASS1,))):
            with self.subTest(basis=basis):
                data = note_answer()
                data['doubts'] = [doubt('status', ['E7'], ['S12'], basis)]
                prepared, out = run(NOTE, data)
                fact_ = at(out.events, 'events', 'E7', 'status')
                self.assertSettled(fact_, result, *reasons)
                self.assertEqual((fact_.claim.state, fact_.claim.value), (FactState.SUPPORTED, 'performed'))
                self.assertSettled(at(out.events, 'events', 'E7', 'kind'), Result.SUPPORTED)  # status only
                self.assertEqual(out.verification.doubts[0].applied, 1)
                stored(prepared, out)

    def test_a_stated_and_an_unclear_doubt_on_one_fact(self):
        data = note_answer()
        data['doubts'] = [doubt('status', ['E7'], ['S12'], 'unclear'), doubt('whole', ['E7'], ['S12'], 'stated')]
        prepared, out = run(NOTE, data)
        self.assertSettled(at(out.events, 'events', 'E7', 'status'), Result.UNKNOWN, R.DOUBT_STATED, R.DOUBT_UNCLEAR)
        # whole names every fact of its object, the inherited ones and the entry included
        for attribute in ('kind', 'session', 'date_relation', 'performer', 'entry', 'technique.device'):
            with self.subTest(attribute=attribute):
                self.assertSettled(at(out.events, 'events', 'E7', attribute), Result.UNKNOWN, R.DOUBT_STATED)
        self.assertSettled(at(out.events, 'events', 'E7', 'target.places', 0), Result.UNKNOWN, R.DOUBT_STATED)
        self.assertSettled(at(out.events, 'events', 'E2', 'status'), Result.SUPPORTED)

    def test_a_malformed_doubt_names_every_fact_of_its_objects_and_stores_no_free_text(self):
        data = note_answer()
        data['doubts'] = [doubt('yield', ['E7'], ['S12'], 'unclear', ['the biopsy may not have been taken'])]
        prepared, out = run(NOTE, data)
        self.assertTrue(prepared.read.doubts[0].malformed)
        for attribute in ('kind', 'status', 'date_relation'):
            with self.subTest(attribute=attribute):
                self.assertSettled(at(out.events, 'events', 'E7', attribute), Result.UNKNOWN, R.DOUBT_UNCLEAR)
        self.assertEqual(out.events['doubts'][0].readings, ())  # P9: a reading that is no value is not stored
        self.assertTrue(out.verification.doubts[0].malformed)
        stored(prepared, out)

    def test_an_objectless_doubt_reaches_every_fact_of_the_events_anchored_at_its_units(self):
        """DECISIONS D200, through Checked.objectless_doubts: a malformed doubt naming no object applies to every fact
        of every event whose anchor units include one of its units (the hand-off recorded after D215)."""
        data = note_answer()
        data['doubts'] = [doubt('status', ['E99'], ['S9'], 'stated')]
        prepared, out = run(NOTE, data)
        self.assertEqual(dict(prepared.checked.objectless_doubts), {0: ('E4', 'E5')})
        for name in ('E4', 'E5'):
            for attribute in ('kind', 'status', 'session', 'date_relation', 'scope.breadth'):
                with self.subTest(event=name, attribute=attribute):
                    self.assertSettled(at(out.events, 'events', name, attribute), Result.UNKNOWN, R.DOUBT_STATED)
        self.assertSettled(at(out.events, 'events', 'E2', 'status'), Result.SUPPORTED)
        self.assertEqual(out.events['unlisted'], [])
        self.assertGreater(out.verification.doubts[0].applied, 10)
        stored(prepared, out)


class CrossObjectTests(Case):
    """3.1's cross-object rules and K8, as settle receives them from Checked."""

    def test_an_invalid_anchor_unresolves_every_fact_of_its_event(self):
        data = note_answer()
        event_of(data, 'E7')['anchor']['kind_words'] = 'snare'  # not in S12: the anchor fails I3
        prepared, out = run(NOTE, data)
        for attribute in ('kind', 'status', 'session', 'technique.device'):
            with self.subTest(attribute=attribute):
                fact_ = at(out.events, 'events', 'E7', attribute)
                self.assertEqual(fact_.result, Result.UNRESOLVED)
                self.assertIn(R.ANCHOR_INVALID, fact_.reasons)
        self.assertIn(R.ANCHOR_INVALID, at(out.events, 'events', 'E7', 'target.places', 0).reasons)
        for attribute in ('date_relation', 'entry'):  # inherited: attached to no section, silent
            with self.subTest(attribute=attribute):
                self.assertSettled(at(out.events, 'events', 'E7', attribute), Result.UNKNOWN, R.SILENT,
                                   R.INHERIT_UNATTACHED, R.ANCHOR_INVALID)
        self.assertSettled(at(out.events, 'events', 'E7', 'target.duct'), Result.UNKNOWN, R.SILENT)
        self.assertSettled(at(out.events, 'events', 'E2', 'kind'), Result.SUPPORTED)
        stored(prepared, out)

    def test_k8_a_reach_given_both_polarities_settles_as_one_contradicted_fact(self):
        data = note_answer()
        data['sessions'][0]['reached'].append(fact('colon', src(['S6'], 'advanced to the cecum'), state='negated'))
        prepared, out = run(NOTE, data)
        self.assertEqual(prepared.checked.joined, (((FactKey(F.SESSION, 'X1', A.REACHED, 0),),
                                                    (FactKey(F.SESSION, 'X1', A.REACHED, 1),)),))
        for index in (0, 1):
            with self.subTest(member=index):
                fact_ = at(out.events, 'sessions', 'X1', 'reached', index)
                self.assertSettled(fact_, Result.CONTRADICTED, R.CONTRADICTED_BY_PASS1)
        # pass 2 supporting both members (claims.py does not read K8's groups yet) lifts neither: row 1 comes first
        self.assertEqual(at(out.events, 'sessions', 'X1', 'reached', 0).appraisal.verdict, VerdictValue.SUPPORTS)
        stored(prepared, out)

    def test_a_session_examination_that_another_session_claims(self):
        data = note_answer()
        event_of(data, 'E1')['session'] = [fact('X2', src(['S6']))]
        prepared, out = run(NOTE, data)
        self.assertSettled(at(out.events, 'sessions', 'X1', 'examination'), Result.UNRESOLVED, R.SESSION_INCONSISTENT)
        self.assertSettled(at(out.events, 'sessions', 'X2', 'examination'), Result.UNRESOLVED, R.UNAPPRAISED)


EXCEPTIVE = ('SYNTHETIC COLONOSCOPY REPORT\n'
             'Date of service: 03/14/2031\n'
             'Endoscopist: Corvin Ashdale, MD (fictional)\n'
             '\n'
             'Findings: The colonoscope was advanced to the cecum.\n'
             'A 4 mm polyp in the rectum was removed with a cold snare.\n'
             'No other polyps were removed.\n')
NOTES['EXCEPTIVE'] = EXCEPTIVE


def exceptive_answer():
    """EXCEPTIVE's answer: a cold-snare removal at the rectum (E2) and the exceptive denial that excepts it (E3), whose
    breadth's exceptive claim claims.py shares with the excepted act (E3's excepts[0], with its own covers-form
    control)."""
    return colonoscopy(EXCEPTIVE,
                       event('E2', ['S5'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S5']))],
                             target__places=[fact('rectum', src(['S5'], 'rectum'))]),
                       event('E3', ['S6'], 'removed', 'No other polyps were removed', 'removal', state='negated',
                             session=[fact('X1', src(['S6']))],
                             scope__breadth=[fact('exceptive', src(['S6'], 'No other polyps'))],
                             scope__excepts=['E2']))


class ClaimTests(Case):
    """The stored claims (1.7), the claims several facts share, the restatement role, cards_indistinct, and verdicts
    bound by content key [R:MO-5]."""

    def test_every_stored_claim_has_its_role_and_attribute(self):
        prepared, out = run(NOTE, note_answer())
        stored_claims = {claim.id: claim for claim in out.events['claims']}
        self.assertEqual([claim.id for claim in out.events['claims']],
                         [claim.id for claim in prepared.claim_set.claims])
        for item in prepared.claim_set.appraised:
            with self.subTest(fact=item.key):
                claim = stored_claims[item.claim]
                self.assertEqual((claim.role, claim.attribute, claim.subject), (settle.ClaimRole.CLAIM,
                                                                                item.key.attribute, item.key.object))
                if item.control is not None:
                    control = stored_claims[item.control]
                    self.assertEqual(control.role, settle.ClaimRole.CONTROL)
                    self.assertIn(control.attribute, (item.key.attribute,
                                                      settle.CONTROL_ATTRIBUTES.get(item.key.attribute)))
        # DECISIONS D210 (step 2c3): E7, the one reported biopsy, lies in X2, an established session other than E4's,
        # so it is never listed and E4's breadth is claimed with no reported-acts control. With E7's session left
        # silent (not established, so it may lie in X1) it is listed, and that control is stored under scope.breadth.
        # (Integration fix of waves 3-4: the line read the control D210 removed.)
        breadth = prepared.appraised(A.SCOPE_BREADTH, 'E4')
        self.assertIsNotNone(breadth)
        self.assertIsNone(breadth.control)
        silent = note_answer()
        event_of(silent, 'E7')['session'] = []
        listed, listed_out = run(NOTE, silent)
        control = listed.appraised(A.SCOPE_BREADTH, 'E4').control
        self.assertIsNotNone(control)
        listed_claims = {claim.id: claim for claim in listed_out.events['claims']}
        self.assertEqual(listed_claims[control].attribute, A.SCOPE_BREADTH)  # the reported-acts form
        self.assertEqual(listed_claims[control].role, settle.ClaimRole.CONTROL)
        verdicts = {claim.id: claim.verdict for claim in out.events['claims']}
        self.assertTrue(all(found is not None for found in verdicts.values()))
        fields, _factset = stored(prepared, out)
        self.assertEqual(fields['verification']['claims_sha256'],
                         store.claims_sha256_v2(fields['events']['claims']))

    def test_the_claim_roles_and_control_attributes_are_the_stores(self):
        self.assertEqual(tuple(role.value for role in settle.ClaimRole), store.CLAIM_ROLES)
        self.assertEqual({fact_.value: control.value for fact_, control in settle.CONTROL_ATTRIBUTES.items()},
                         dict(store.CONTROL_ATTRIBUTES))
        self.assertEqual(settle.ACT_INHERITED, checks.ACT_INHERITED)
        self.assertEqual(settle.STATEMENT_INHERITED, checks.STATEMENT_INHERITED)

    def test_part_of_and_part_relation_share_one_claim_read_by_part_of_alone(self):
        """A KNOWN LIMIT, fail-closed until the step's notes' REQUEST R4 is ruled (refutation P1): claims.py renders
        part_relation as part_of's claim, and the store reads a claim for one fact only (the one whose attribute and value
        it states), so part_relation settles unappraised although its own pair is established."""
        data = note_answer()
        event_of(data, 'E3')['part_of'] = [fact('E2', src(['S8'], 'polypectomy site'))]
        event_of(data, 'E3')['part_relation'] = [fact('adjunct_of', src(['S8'], 'was treated'))]
        prepared, out = run(NOTE, data)
        part_of, relation = prepared.appraised(A.PART_OF, 'E3'), prepared.appraised(A.PART_RELATION, 'E3')
        self.assertEqual(part_of.claim, relation.claim)  # one sentence, one claim (claims.py)
        self.assertSettled(at(out.events, 'events', 'E3', 'part_of'), Result.SUPPORTED)
        self.assertSettled(at(out.events, 'events', 'E3', 'part_relation'), Result.UNRESOLVED, R.UNAPPRAISED)
        self.assertIsNone(at(out.events, 'events', 'E3', 'part_relation').appraisal)
        claim = next(item for item in out.events['claims'] if item.id == part_of.claim)
        self.assertEqual(claim.attribute, A.PART_OF)
        stored(prepared, out)

    def test_an_exceptive_breadth_and_its_excepted_act_share_the_breadths_claim(self):
        """A KNOWN LIMIT, fail-closed until the step's notes' REQUEST R4 is ruled (refutation P1; FINAL-V2 4.5's BF17
        needs the excepted act established): the excepted act shares its breadth's exceptive claim, the store reads that
        claim for the breadth alone, so the excepted act settles unappraised although its own pair - the shared claim
        and its covers-form control - is established."""
        prepared, out = run(EXCEPTIVE, exceptive_answer())
        breadth, excepted = prepared.appraised(A.SCOPE_BREADTH, 'E3'), prepared.appraised(A.SCOPE_EXCEPTS, 'E3')
        self.assertEqual(breadth.claim, excepted.claim)
        self.assertSettled(at(out.events, 'events', 'E3', 'scope.breadth'), Result.SUPPORTED)
        member = at(out.events, 'events', 'E3', 'scope.excepts', 0)
        self.assertSettled(member, Result.UNRESOLVED, R.UNAPPRAISED)
        self.assertEqual((member.claim.value, [source.units for source in member.sources]), ('E2', [('S6',)]))
        pairs = {(pair.claim, pair.control): pair.outcome for pair in settle.pairs_of(
            prepared.claim_set, settle.verdicts_of(prepared.claim_set, prepared.appraisal()))}
        self.assertEqual(pairs[(excepted.claim, excepted.control)], settle.PairOutcome.ESTABLISHED)
        stored(prepared, out)

    def test_a_shared_claim_whose_value_is_no_entrys_own_is_read_by_none(self):
        """A claim several facts share is bound only to the entry whose value it states: when that fact is not itself
        claimed (here its Appraised entry is withdrawn, as claims.py withdraws a fact it cannot claim), the partner
        rendered as its claim is read by no fact - settle never binds it to a fact whose value it does not state, which
        the store refuses (store._v2_verdicts_bound) - and the row stores."""
        prepared = Prepared(EXCEPTIVE, exceptive_answer())
        breadth = prepared.appraised(A.SCOPE_BREADTH, 'E3')
        claim_set = dataclasses.replace(prepared.claim_set, appraised=tuple(
            item for item in prepared.claim_set.appraised if item is not breadth))
        with mock.patch.object(interpretation, 'HEALTH_THRESHOLDS_SHA256', HEALTH_PIN):
            out = settle.settle(prepared.read, prepared.checked, claim_set, prepared.request.indistinct,
                                prepared.appraisal(), USAGE)
        member = at(out.events, 'events', 'E3', 'scope.excepts', 0)
        self.assertSettled(member, Result.UNRESOLVED, R.UNAPPRAISED)
        self.assertIsNone(member.appraisal)
        self.assertSettled(at(out.events, 'events', 'E3', 'scope.breadth'), Result.UNRESOLVED, R.UNAPPRAISED)
        stored(prepared, out)

    def test_a_partner_given_its_own_claim_is_established_with_nothing_changed_here(self):
        """REQUEST R4's first option (claims.py gives each fact its own claim) needs no change in settle: the excepted
        act given a claim of its own (its own value and content key, its covers-form control kept) binds to it, its pair
        established settles it supported, and the store accepts the row."""
        prepared = Prepared(EXCEPTIVE, exceptive_answer())
        excepted = prepared.appraised(A.SCOPE_EXCEPTS, 'E3')
        shared = prepared.claim_set.claim(excepted.claim)
        own = dataclasses.replace(shared, id=f'K{len(prepared.claim_set.claims) + 1}', value='E2',
                                  content=hashlib.sha256(b'synthetic own claim of E3 excepts E2').hexdigest())
        claim_set = dataclasses.replace(
            prepared.claim_set, claims=(*prepared.claim_set.claims, own),
            appraised=tuple(dataclasses.replace(item, claim=own.id) if item is excepted else item
                            for item in prepared.claim_set.appraised))
        appraisal = prepared.appraisal()
        supports = Verdict(own.id, VerdictValue.SUPPORTS, Attached.YES, (), own.units[:1])
        appraisal = dataclasses.replace(appraisal, verdicts=(*appraisal.verdicts, appraise_read.ReadVerdict(
            own.id, own.content, supports, (), True)))
        with mock.patch.object(interpretation, 'HEALTH_THRESHOLDS_SHA256', HEALTH_PIN):
            out = settle.settle(prepared.read, prepared.checked, claim_set, prepared.request.indistinct, appraisal,
                                USAGE)
        member = at(out.events, 'events', 'E3', 'scope.excepts', 0)
        self.assertSettled(member, Result.SUPPORTED)
        self.assertEqual((member.appraisal.claim, member.appraisal.control.claim), (own.id, excepted.control))
        self.assertSettled(at(out.events, 'events', 'E3', 'scope.breadth'), Result.SUPPORTED)
        stored(prepared, out)

    def test_a_restates_restatement_in_the_documenting_clinicians_part_is_claimed_and_never_established(self):
        """1.5 [R:SC-D] moves the entry only when the role AND the owner of R's section are established; no claim of the
        request appraises that owner for the act (3.2.1 claims no section fact), so the role is never established: its
        own pair - established here - is kept with it, and it settles unappraised (the fail-closed reading of the step's
        notes' question; the engine's entry is then never moved, and the anchor's entry stands)."""
        data = note_answer()
        event_of(data, 'E2')['restatements'] = [{'units': ['S13'], 'role': 'restates'}]
        prepared, out = run(NOTE, data)
        self.assertEqual(dict(prepared.checked.restatements), {('E2', 0): 'N4'})
        item = prepared.appraised(A.RESTATEMENTS_ROLE, 'E2')
        role = out.events['events'][1]['restatements'][0]['role']
        self.assertSettled(role, Result.UNRESOLVED, R.UNAPPRAISED)
        self.assertEqual((role.claim.value, [source.units for source in role.sources]), ('restates', [('S13',)]))
        self.assertEqual((role.appraisal.claim, role.appraisal.control.claim), (item.claim, item.control))
        self.assertEqual((role.appraisal.verdict, role.appraisal.control.verdict),
                         (VerdictValue.SUPPORTS, VerdictValue.CONTRADICTS))  # the role's own pair is established
        self.assertSettled(at(out.events, 'events', 'E2', 'entry'), Result.SUPPORTED)  # N2's owner, never moved
        stored(prepared, out)

    def test_a_restates_role_reads_its_sections_owner_and_its_acts_entry_doubts(self):
        """Refutation P2: the role carries the move's conditions - rows 1-5 on the owner of R's section (its doubts and
        findings), every doubt naming the act's entry, and that owner given as the documenting clinician - so a doubted,
        qualified or nursing owner of the clinician's impression never lets a nursing-part act's restatement count."""
        def nursing(doubts=(), owner=None):
            return colonoscopy(
                NURSING,
                event('E2', ['S5'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S5']))],
                      restatements=[{'units': ['S6'], 'role': 'restates'}],
                      target__places=[fact('rectum', src(['S5'], 'rectal'))],
                      technique__device=[fact('cold_snare', src(['S5'], 'cold snare'))]),
                extra_sections=[
                    labelled('N2', 'S5', 'Nursing note:', 'nursing_note',
                             owner=fact('nursing', src(['S5'], 'Nursing note:', 'section'))),
                    section('N3', src(['S6'], 'Impression:', 'section'),
                            owner or fact('documenting_clinician', frame(['S3'])),
                            role=[fact('impression', src(['S6'], 'Impression:', 'section'))])],
                doubts=doubts)

        cases = {
            "R's section's owner doubted": (nursing([doubt('entry', ['N3'], ['S6'], 'unclear')]),
                                             Result.UNKNOWN, (R.DOUBT_UNCLEAR,), True),
            "the act's entry doubted": (nursing([doubt('entry', ['E2'], ['S5'], 'stated')]),
                                        Result.UNKNOWN, (R.DOUBT_STATED,), True),
            "R's section's owner qualified": (
                nursing(owner=fact('documenting_clinician', frame(['S3']), qualifiers=['hedged'])),
                Result.UNRESOLVED, (R.QUALIFIED_HEDGED,), True),
            "R's section's owner a nurse": (nursing(owner=fact('nursing', src(['S6'], 'Impression:', 'section'))),
                                            Result.UNRESOLVED, (R.UNAPPRAISED,), False),
            'the control: nothing doubted': (nursing(), Result.UNRESOLVED, (R.UNAPPRAISED,), True),
        }
        for name, (data, result, reasons, claimed) in cases.items():
            with self.subTest(case=name):
                prepared, out = run(NURSING, data)
                self.assertEqual(dict(prepared.checked.restatements), {('E2', 0): 'N3'})
                role = out.events['events'][1]['restatements'][0]['role']
                self.assertSettled(role, result, *reasons)
                self.assertEqual(prepared.appraised(A.RESTATEMENTS_ROLE, 'E2') is not None, claimed)
                self.assertEqual(at(out.events, 'events', 'E2', 'entry').claim.value, 'nursing')  # never moved
                stored(prepared, out)

    def test_a_restatement_g6_ignores_never_establishes_its_role(self):
        """G6: a restatement on an anchor unit is ignored, so its role is never claimed in Checked's world and never
        established, whatever claim the request carries for it (the w3int build's D4)."""
        data = note_answer()
        event_of(data, 'E2')['restatements'] = [{'units': ['S8'], 'role': 'restates'}]  # E3's anchor unit
        prepared, out = run(NOTE, data)
        self.assertEqual(dict(prepared.checked.restatements), {})
        role = out.events['events'][1]['restatements'][0]['role']
        self.assertSettled(role, Result.UNRESOLVED, R.UNAPPRAISED)
        self.assertEqual(role.sources[0].geometry, CheckStatus.FAILED)
        self.assertIsNone(role.appraisal)
        stored(prepared, out)

    def test_identical_cards_unresolve_the_facts_whose_values_differ(self):
        data = note_answer()
        for name in ('E4', 'E5'):
            event_of(data, name)['anchor']['kind_words'] = 'biopsy nor tattoo'
            event_of(data, name)['kind']['sources'] = [src(['S9'], 'biopsy nor tattoo')]
        prepared, out = run(NOTE, data)
        self.assertEqual(prepared.request.indistinct, (('E4', 'E5'),))
        for name in ('E4', 'E5'):
            with self.subTest(event=name):
                self.assertSettled(at(out.events, 'events', name, 'kind'), Result.UNRESOLVED, R.CARDS_INDISTINCT)
                self.assertSettled(at(out.events, 'events', name, 'status'), Result.NEGATED)  # the same value
                self.assertSettled(at(out.events, 'events', name, 'session'), Result.SUPPORTED)
        stored(prepared, out)

    def test_a_claim_about_another_value_or_section_is_not_the_facts(self):
        """A claim the request carries for a fact's key but about another value or another governing section (a seam
        between claims.py's geometry and Checked's) is not read for the fact: it settles unappraised, and the row
        stores."""
        prepared = Prepared(NOTE, note_answer())
        item = prepared.appraised(A.DATE_RELATION, 'E2')
        moved = dataclasses.replace(item, inherited_from='N3')
        claim_set = dataclasses.replace(prepared.claim_set, appraised=tuple(
            moved if found is item else found for found in prepared.claim_set.appraised))
        with mock.patch.object(interpretation, 'HEALTH_THRESHOLDS_SHA256', HEALTH_PIN):
            out = settle.settle(prepared.read, prepared.checked, claim_set, prepared.request.indistinct,
                                prepared.appraisal(), USAGE)
        self.assertSettled(at(out.events, 'events', 'E2', 'date_relation'), Result.UNRESOLVED, R.UNAPPRAISED)
        self.assertSettled(at(out.events, 'events', 'E3', 'date_relation'), Result.SUPPORTED)
        stored(prepared, out)

    def test_a_verdict_bound_to_another_content_key_is_no_verdict(self):
        prepared = Prepared(NOTE, note_answer())
        appraisal = prepared.appraisal()
        item = prepared.appraised(A.KIND, 'E2')
        verdicts = tuple(dataclasses.replace(found, content='f' * 64) if found.claim == item.claim else found
                         for found in appraisal.verdicts)
        changed = dataclasses.replace(appraisal, verdicts=verdicts)
        with mock.patch.object(interpretation, 'HEALTH_THRESHOLDS_SHA256', HEALTH_PIN):
            out = settle.settle(prepared.read, prepared.checked, prepared.claim_set, prepared.request.indistinct,
                                changed, USAGE)
            self.assertSettled(at(out.events, 'events', 'E2', 'kind'), Result.UNRESOLVED, R.APPRAISAL_MISSING)
            self.assertIsNone(next(claim for claim in out.events['claims'] if claim.id == item.claim).verdict)
            stored(prepared, out)
            other = Prepared(PROBE_A, colonoscopy(PROBE_A))
            with self.assertRaises(ValueError):  # an appraisal read against another request
                settle.settle(prepared.read, prepared.checked, other.claim_set, other.request.indistinct, appraisal,
                              USAGE)
            with self.assertRaises(ValueError):  # checks of another segmentation
                settle.settle(other.read, prepared.checked, prepared.claim_set, prepared.request.indistinct,
                              appraisal, USAGE)


def canonical(out):
    """A settled inventory as JSON data, with its sha256: what P-DET compares."""
    events = store._v2_jsonable(out.events, 'events')
    report = store._v2_jsonable(out.verification, 'verification')
    return jsonschema.sha256_of({'events': events, 'verification': report})


def fingerprint() -> str:
    """The sha256 of NOTE's settled inventory under a doubted, a malformed and an object-less doubt and an unlisted
    entry: P-DET's probe, run in processes with different hash seeds."""
    data = note_answer()
    data['doubts'] = [doubt('performer', ['E2'], ['S7'], 'unclear', ['other_clinician']),
                      doubt('yield', ['E7'], ['S12'], 'stated'), doubt('status', ['E99'], ['S9'], 'stated')]
    prepared = Prepared(NOTE, data)
    out = prepared.settle(unlisted=[unlisted_entry(['S12'], 'act', 'biopsy')])
    return canonical(out)


class StoreTests(Case):
    def test_p_det_identical_inputs_give_byte_identical_inventories_in_every_process(self):
        first, second = fingerprint(), fingerprint()
        self.assertEqual(first, second)
        environment = dict(os.environ, DJANGO_SETTINGS_MODULE='cptstudio.settings')
        code = ('import django\ndjango.setup()\nfrom tests.v2.test_settle import fingerprint\nprint(fingerprint())\n')
        for seed in ('0', '4242'):
            with self.subTest(seed=seed):
                result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, cwd=APP,
                                        env=dict(environment, PYTHONHASHSEED=seed), timeout=300)
                self.assertEqual(result.returncode, 0, result.stderr[-2000:])
                self.assertEqual(result.stdout.strip().splitlines()[-1], first)

    def test_the_report_counts_what_is_stored(self):
        prepared, out = run(NOTE, note_answer())
        report = out.verification
        facts = sum(sum(per.values()) for per in report.counts.values())
        self.assertEqual(facts, len(_every_fact(out.events)))
        self.assertEqual(report.counts[A.KIND][Result.SUPPORTED], 9)  # seven events and two sessions
        self.assertEqual(report.reasons[R.UNAPPRAISED], sum(R.UNAPPRAISED in fact_.reasons
                                                            for fact_ in _every_fact(out.events)))
        self.assertEqual(report.usage.interpretation, settle.Usage(1800, 900, 2100, 4800, 0, 0))
        self.assertEqual(report.coherence.established, len(prepared.claim_set.appraised)
                         - _shared(prepared.claim_set) + len(prepared.claim_set.completeness))
        fields, _factset = stored(prepared, out)
        self.assertEqual(fields['verification']['usage']['appraisal'],
                         {'prompt': 2600, 'candidates': 480, 'thoughts': 0, 'total': 0, 'cached': 0,
                          'tool_use_prompt': 0})

    def test_usage_stores_integers_only(self):
        self.assertEqual(settle.usage_of({'promptTokenCount': '12', 'candidatesTokenCount': -3,
                                          'thoughtsTokenCount': 7.5, 'totalTokenCount': True,
                                          'cachedContentTokenCount': 4, 'promptTokensDetails': [{'x': 'text'}]}),
                         settle.Usage(0, 0, 0, 0, 4, 0))


def _every_fact(events):
    """Every settled fact of a settled inventory, the restatements' roles and the scope members included."""
    found = [events['encounter']['date_of_service'], events['encounter']['documenting_clinician']]
    found += [other['role'] for other in events['encounter']['other_dates']]
    for family in (F.PERSON, F.SECTION, F.SESSION, F.ANATOMY, F.LESION, F.EVENT):
        for record in events[family.value]:
            for field in xs.ATTRIBUTES[family]:
                if field.attribute is A.RESTATEMENTS_ROLE:
                    found += [item['role'] for item in record['restatements']]
                    continue
                node = record
                for part in field.path:
                    node = node[part]
                found += list(node) if isinstance(node, list) else [node]
    return found


def _shared(claim_set):
    """How many appraised facts share their claim and control pair with an earlier one (one pair counted once)."""
    seen, shared = set(), 0
    for item in claim_set.appraised:
        if (item.claim, item.control) in seen:
            shared += 1
        seen.add((item.claim, item.control))
    return shared


# --- P-INDEP-SETTLE (9.4 [R:HO-7]; DECISIONS D201) and P-DEMOTE --------------------------------------------------------


def flat(out):
    """Every settled fact of a settled inventory by (family, object, attribute, position), as (result, reasons); a
    session's completeness record under (sessions, its id, stations, -1)."""
    events = out.events
    found = {(F.ENCOUNTER, '', A.DATE_OF_SERVICE, 0): events['encounter']['date_of_service'],
             (F.ENCOUNTER, '', A.DOCUMENTING_CLINICIAN, 0): events['encounter']['documenting_clinician']}
    for index, other in enumerate(events['encounter']['other_dates']):
        found[(F.ENCOUNTER, '', A.OTHER_DATES_ROLE, index)] = other['role']
    summary = {key: (fact_.result, fact_.reasons) for key, fact_ in found.items()}
    for family in (F.PERSON, F.SECTION, F.SESSION, F.ANATOMY, F.LESION, F.EVENT):
        for record in events[family.value]:
            name = record['id']
            for field in xs.ATTRIBUTES[family]:
                if field.attribute is A.RESTATEMENTS_ROLE:
                    for index, item in enumerate(record['restatements']):
                        summary[(family, name, field.attribute, index)] = (item['role'].result, item['role'].reasons)
                    continue
                node = record
                for part in field.path:
                    node = node[part]
                for index, fact_ in enumerate(node if isinstance(node, list) else [node]):
                    summary[(family, name, field.attribute, index)] = (fact_.result, fact_.reasons)
            if family is F.SESSION and record['completeness'] is not None:
                summary[(family, name, A.STATIONS, -1)] = (record['completeness'].result,
                                                           record['completeness'].reasons)
    return summary


def _value(slot):
    """The supported value of a FACT or a slot of the raw answer, None otherwise."""
    facts_ = slot if isinstance(slot, list) else [slot]
    return facts_[0]['value'] if len(facts_) == 1 and facts_[0]['state'] == 'supported' else None


def _cites(slot, units):
    """Whether any source of a raw slot's or list's facts (their options' included) cites one of ``units``."""
    for fact_ in slot if isinstance(slot, list) else [slot]:
        for source in (*fact_['sources'], *(item for option in fact_['options'] for item in option['sources'])):
            if set(source['units']) & units:
                return True
    return False


def couplings(prepared, family, name, attribute):
    """The facts of OTHER objects that perturbing ``family`` ``name``'s ``attribute`` may change: DECISIONS D201's
    listed couplings - 4.9's rules (a section's owner, occasion and performer through inheritance, 1.5, and the owner of
    the section a restates restatement lies in, through its role; an invalid anchor and K8 stay inside their object; a
    doubt naming several objects is never planted here), K1's exceptive rule, K2's arms 2-4, K3, K4, K5, K7 (inside its
    section, then through inheritance) and L1 - and the couplings the design specifies beside them, each named and each
    as narrow as the design states it: G5's reading of an act's status (D198: an event's claimed status decides whether
    its anchor and restatements are an act's units, so only the extent facts citing one of them), CLAIMED's conditions
    on another object (3.2.1: a lesion of a claimed act; the anatomy entry an act's target.anatomy or a session's through
    or reached_anatomy names, and a surgically absent organ a reach or a station names; a session holding a visit; a
    restatement in the documenting clinician's part) and the all_of_kind control's reported acts (3.2.3, D210). Computed
    from the raw answer and the checks' geometry, never from settle."""
    data, checked = prepared.data, prepared.checked
    out = set()
    sessions = {item['id']: item for item in data['sessions']}
    session_of = {item['id']: _value(item['session']) for item in data['events']}
    kind_of = {item['id']: _value(item['kind']) for item in data['events']}
    examination_of = {name_: _value(item['examination']) for name_, item in sessions.items()}
    inherited = (A.ENTRY, A.DATE_RELATION, A.PERFORMER, A.PERFORMER_PERSON)
    extent = (A.REACHED, A.COMPLETION, A.STATIONS, A.APPROACH, A.THROUGH)
    lesion_facts = (A.MULTIPLICITY, A.PLACES, A.DISTINCT_FROM, A.SAME_AS)
    anatomy_facts = (A.TYPE, A.ORGAN, A.SUBTYPE, A.JOINS)
    if family is F.SECTION:  # inheritance (1.5; 4.9), K7 through it, L1's per-event rule (D193)
        for event_, section_ in checked.containing.items():
            if section_ == name:
                out |= {(F.EVENT, event_, item) for item in inherited}
                for session_, examination in examination_of.items():  # K2 arm 4: the examination's effective relation
                    if examination == event_:
                        out |= {(F.EVENT, act, A.SESSION) for act, of in session_of.items() if of == session_}
        for (event_, _index), section_ in checked.restatements.items():  # 3.2.1: restates in the clinician's part
            if section_ == name:
                out.add((F.EVENT, event_, A.RESTATEMENTS_ROLE))
    if family is F.EVENT:
        for item in data['events']:  # K1's exceptive rule; the all_of_kind control's reported acts (3.2.3, D210)
            excepts = name in item['scope']['excepts']
            reported = (_value(item['scope']['breadth']) == 'all_of_kind' and kind_of[item['id']] is not None
                        and kind_of[name] is not None
                        and catalogue.covers(Kind(kind_of[item['id']]), Kind(kind_of[name])))
            if excepts or reported:
                out |= {(F.EVENT, item['id'], A.SCOPE_BREADTH), (F.EVENT, item['id'], A.SCOPE_EXCEPTS)}
        for session_, examination in examination_of.items():  # K2 arms 2 and 4
            if examination == name:
                out.add((F.SESSION, session_, A.EXAMINATION))
                out |= {(F.EVENT, act, A.SESSION) for act, of in session_of.items() if of == session_}
        event_item = next(item for item in data['events'] if item['id'] == name)
        if attribute is A.STATUS:  # G5 (D198): only an extent fact citing a unit this event is told in
            told = set(event_item['anchor']['units']) | {unit for item in event_item['restatements']
                                                          for unit in item['units']}
            out |= {(F.SESSION, session_, item) for session_, record in sessions.items() for item in extent
                    if _cites(record[xs.field(F.SESSION, item).path[0]], told)}
        if kind_of[name] == 'em_visit' and session_of[name] in sessions:  # 3.2.1: a session holding a visit
            out.add((F.SESSION, session_of[name], A.ENCOUNTER))
        named = {fact_['value'] for fact_ in event_item['target']['lesion']} | set(event_item['scope']['targets'])
        out |= {(F.LESION, lesion_, fact_) for lesion_ in named for fact_ in lesion_facts}  # 3.2.1: of a claimed act
        if attribute is A.TARGET_ANATOMY:  # 3.2.1: the anatomy entry an act names is read
            out |= {(F.ANATOMY, fact_['value'], item) for fact_ in event_item['target']['anatomy']
                    for item in anatomy_facts}
        if attribute is A.TARGET_PLACES:  # K4: an act place at or inside a surgically absent organ
            out |= {(F.ANATOMY, item['id'], fact_) for item in data['anatomy'] for fact_ in anatomy_facts}
    if family is F.SESSION:  # K2 arm 3, K3; K4 and 3.2.1's anatomy read by a reach, a station or a through
        out |= {(F.EVENT, act, A.SESSION) for act, of in session_of.items() if of == name}
        if attribute in (A.THROUGH, A.REACHED_ANATOMY):  # 3.2.1: the entry a through or a reached_anatomy names
            out |= {(F.ANATOMY, fact_['value'], item) for fact_ in sessions[name][xs.field(F.SESSION, attribute).path[0]]
                    for item in anatomy_facts}
        if attribute in (A.REACHED, A.STATIONS):  # K4; 3.2.1: a surgically absent organ a reach or a station names
            out |= {(F.ANATOMY, item['id'], fact_) for item in data['anatomy'] for fact_ in anatomy_facts}
    if family is F.ANATOMY:  # K4
        out |= {(F.SESSION, session_, item) for session_ in sessions for item in (A.REACHED, A.STATIONS)}
        out |= {(F.EVENT, item['id'], A.TARGET_PLACES) for item in data['events']}
    if family is F.PERSON or (family is F.ENCOUNTER and attribute is A.DOCUMENTING_CLINICIAN):  # K5
        out |= {(F.EVENT, item['id'], fact_) for item in data['events'] for fact_ in (A.PERFORMER, A.PERFORMER_PERSON)}
        out |= {(F.SECTION, item['id'], fact_) for item in data['sections']
                for fact_ in (A.PERFORMER, A.PERFORMER_PERSON)}
    if family is F.ENCOUNTER and attribute is A.DATE_OF_SERVICE:  # L1's reference date
        out |= {(F.EVENT, item['id'], fact_) for item in data['events'] for fact_ in (A.DATE_RELATION, A.DATE)}
        out |= {(F.SECTION, item['id'], A.OCCASION) for item in data['sections']}
    return out


def _node(data, key):
    """The raw fact of the answer at ``key`` (a dict), or None."""
    if key.family is F.ENCOUNTER:
        if key.attribute is A.DATE_OF_SERVICE:
            return data['encounter']['date_of_service']
        if key.attribute is A.OTHER_DATES_ROLE:
            return data['encounter']['other_dates'][key.index]['role']
        return data['encounter']['documenting_clinician'][key.index]
    item = next(record for record in data[key.family.value] if record['id'] == key.object)
    node = item
    for part in xs.field(key.family, key.attribute).path:
        node = node[part]
    return node if isinstance(node, dict) else node[key.index]


def perturbations(prepared):
    """Every one-fact perturbation of the answer (P-INDEP-SETTLE): for each fact of pass 1, its state flipped, its
    value changed within its domain, a hedging qualifier, an unknown unit cited, a stated doubt naming it, and pass 2
    contradicting its claim. Yields (label, key, the perturbed answer, the oracle)."""
    for item in prepared.read.facts:
        key = item.key
        field = xs.field(key.family, key.attribute)

        def edited(change, key=key):
            data = copy.deepcopy(prepared.data)
            change(_node(data, key))
            return data

        is_date_of_service = key.attribute is A.DATE_OF_SERVICE
        node = _node(prepared.data, key)
        if not is_date_of_service and node['state'] in ('supported', 'negated'):
            flipped = 'negated' if node['state'] == 'supported' else 'supported'
            yield 'state', key, edited(lambda found, flipped=flipped: found.update(state=flipped)), faithful
        values = []
        if field.values is not None:
            members = [member.value for member in field.values]
            values = [members[(members.index(node['value']) + 1) % len(members)]] if node['value'] in members else []
        elif field.refers_to is not None:
            values = [record['id'] for record in prepared.data[field.refers_to.value] if record['id'] != node['value']
                      and not (record['id'] == key.object and field.refers_to is key.family)][:1]
        elif node['value']:
            values = ['2031-03-13' if len(node['value']) == 10 else '2026']
        for value in values:
            yield 'value', key, edited(lambda found, value=value: found.update(value=value)), faithful
        if not is_date_of_service:
            yield 'qualifier', key, edited(lambda found: found['qualifiers'].append('hedged')), faithful
        if node['sources']:
            yield 'unit', key, edited(lambda found: found['sources'][0]['units'].append('S99')), faithful
        about = next((value for value, row in xs.DOUBT_ATTRIBUTES.items()
                      if value.value != 'whole' and key.attribute in row.get(key.family, ())), None)
        objects = [] if key.family is F.ENCOUNTER else [key.object]
        if about is not None and (key.family is not F.ENCOUNTER or is_date_of_service):
            data = copy.deepcopy(prepared.data)
            data['doubts'].append(doubt(about.value, objects, (node['sources'][0]['units'][:1] if node['sources']
                                                               else ['S1']), 'stated'))
            yield 'doubt', key, data, faithful
        found = prepared.appraised(key.attribute, key.object, key.index)
        if found is not None:
            yield 'verdict', key, prepared.data, overriding(**{
                f'{key.attribute.value}@{key.object}/{key.index}': {'value': 'contradicts'}})


class IndependenceTests(Case):
    def test_p_indep_settle_one_objects_fact_changes_anothers_only_through_the_listed_couplings(self):
        """9.4 P-INDEP-SETTLE [R:HO-7] over DECISIONS D201's couplings: every one-fact perturbation of NOTE's pass-1
        and pass-2 answers, settled; any fact of ANOTHER object that changed is one a listed coupling reaches. HO-7's
        defect - one act's performer unresolving its session's examination - is exactly what this catches."""
        base = Prepared(NOTE, note_answer())
        before = flat(base.settle())
        counted = {'state': 0, 'value': 0, 'qualifier': 0, 'unit': 0, 'doubt': 0, 'verdict': 0}
        unhealthy = 0
        for label, key, data, oracle in perturbations(base):
            with self.subTest(perturbation=label, fact=key):
                prepared = base if data is base.data else Prepared(NOTE, data)
                out = prepared.settle(oracle)
                if isinstance(out, settle.Unhealthy):
                    unhealthy += 1
                    continue
                after = flat(out)
                allowed = couplings(base, key.family, key.object, key.attribute) | couplings(
                    prepared, key.family, key.object, key.attribute)
                changed = {(family, name, attribute) for family, name, attribute, index in set(before) | set(after)
                           if before.get((family, name, attribute, index)) != after.get((family, name, attribute,
                                                                                        index))}
                outside = {item for item in changed if (item[0], item[1]) != (key.family, key.object)} - allowed
                self.assertEqual(outside, set(), (label, key))
                counted[label] += 1
        self.assertEqual(unhealthy, 0)
        self.assertTrue(all(count > 10 for count in counted.values()), counted)

    def test_the_coupling_table_is_not_vacuous(self):
        """The property sees a change through a listed coupling: a section's occasion reaches its acts' inherited
        date relations, and nothing of another section's acts."""
        base = Prepared(NOTE, note_answer())
        before = flat(base.settle())
        data = note_answer()
        section_of(data, 'N2')['occasion'][0]['qualifiers'] = ['hedged']
        after = flat(Prepared(NOTE, data).settle())
        changed = {(name, attribute) for family, name, attribute, index in before
                   if before[(family, name, attribute, index)] != after[(family, name, attribute, index)]}
        self.assertEqual(changed, {('N2', A.OCCASION)} | {(name, A.DATE_RELATION) for name in
                                                           ('E1', 'E2', 'E3', 'E4', 'E5')})

    def test_g5s_coupling_is_an_acts_status_and_only_the_extent_facts_citing_its_units(self):
        """G5's coupling, as narrow as D198 states it: X1's station cited at E2's anchor (a snare act's sentence) is
        extent_inferred; E2's status negated makes its anchor a denial's, no act's, so the station no longer is - a change
        the coupling admits for E2's status, and never for another act's status or for E2's kind."""
        data = note_answer()
        data['sessions'][0]['stations'] = [fact('colon', src(['S7'], 'sigmoid colon'))]
        base = Prepared(NOTE, data)
        before = flat(base.settle())
        self.assertIn(R.EXTENT_INFERRED, before[(F.SESSION, 'X1', A.STATIONS, 0)][1])
        flipped = copy.deepcopy(data)
        event_of(flipped, 'E2')['status']['state'] = 'negated'
        after = flat(Prepared(NOTE, flipped).settle())
        self.assertNotIn(R.EXTENT_INFERRED, after[(F.SESSION, 'X1', A.STATIONS, 0)][1])
        self.assertIn((F.SESSION, 'X1', A.STATIONS), couplings(base, F.EVENT, 'E2', A.STATUS))
        self.assertNotIn((F.SESSION, 'X1', A.STATIONS), couplings(base, F.EVENT, 'E3', A.STATUS))
        self.assertNotIn((F.SESSION, 'X1', A.STATIONS), couplings(base, F.EVENT, 'E2', A.KIND))
        self.assertNotIn((F.SESSION, 'X1', A.REACHED), couplings(base, F.EVENT, 'E2', A.STATUS))  # cited at S6


_PREPARED: dict[str, Prepared] = {}


def _note():
    if 'NOTE' not in _PREPARED:
        _PREPARED['NOTE'] = Prepared(NOTE, note_answer())
    return _PREPARED['NOTE']


VERDICT = st.fixed_dictionaries({
    'value': st.sampled_from([item.value for item in VerdictValue]),
    'attached': st.sampled_from([item.value for item in Attached]),
    'qualifiers': st.lists(st.sampled_from(['hedged', 'approximate', 'other_act']), max_size=2, unique=True),
    'evidence': st.sampled_from(['own', 'elsewhere', 'none'])})


class DemotionTests(Case):
    @hypothesis.settings(max_examples=60, deadline=None, derandomize=True, database=None,
                         suppress_health_check=list(hypothesis.HealthCheck))
    @hypothesis.given(st.lists(st.one_of(st.none(), VERDICT), min_size=200, max_size=200))
    def test_p_demote_pass_two_never_creates_changes_or_upgrades_a_fact(self, answers):
        """9.4 P-DEMOTE: for any appraisal answer, every settled result is at most pass 1's claim - an established
        result only where pass 1 claimed that very state and the faithful reading establishes it too, and nothing
        contradicted that pass 1 did not report."""
        prepared = _note()
        faithful_out = flat(prepared.settle())

        def oracle(claim, role, claim_set):
            given = answers[int(claim.id[1:]) % len(answers)]
            if given is None:
                return None
            evidence = {'own': claim.units[:1], 'elsewhere': ['S1'], 'none': []}[given['evidence']]
            return verdict(claim, given['value'], given['attached'], given['qualifiers'], evidence)

        out = prepared.settle(oracle)
        if isinstance(out, settle.Unhealthy):
            return
        for key, (result, _reasons) in flat(out).items():
            if result in (Result.SUPPORTED, Result.NEGATED):
                self.assertEqual(faithful_out[key][0], result, key)
            self.assertNotEqual(result, Result.CONTRADICTED, key)  # NOTE's pass 1 reports no contradiction
        for fact_ in _every_fact(out.events):
            if fact_.result in (Result.SUPPORTED, Result.NEGATED):
                self.assertEqual(fact_.claim.state.value, fact_.result.value)
                self.assertEqual((fact_.appraisal.verdict, fact_.appraisal.attached, fact_.appraisal.qualifiers),
                                 (VerdictValue.SUPPORTS, Attached.YES, ()))
                self.assertIn(fact_.appraisal.control.verdict if fact_.appraisal.control else None,
                              (None, VerdictValue.CONTRADICTS) if fact_.appraisal.control is None
                              else (VerdictValue.CONTRADICTS,))

    def test_a_doubt_never_upgrades_a_fact(self):
        base = flat(_note().settle())
        for basis in ('stated', 'unclear', 'conflict'):
            for target in ('E2', 'N2', 'X1', 'L1'):
                with self.subTest(basis=basis, target=target):
                    data = note_answer()
                    data['doubts'] = [doubt('whole', [target], ['S7'], basis)]
                    after = flat(Prepared(NOTE, data).settle())
                    for key, (result, _reasons) in after.items():
                        if result in (Result.SUPPORTED, Result.NEGATED):
                            self.assertEqual(base[key][0], result, key)


# --- the module ----------------------------------------------------------------------------------------------------------

TEXT_MODULES = ('segment', 'geometry', 'fold', 'date_literals')  # contract's text modules (5.7 measure 4)
RETIRED = ('prompt', 'schema', 'read', 'normalize', 'verify', 'literals', 'identity', 'lexicon', 'relations', 'mapping',
           'classes', 'ercp', 'facts', 'events', 'coverage', 'combination', 'assess')  # FINAL-V2 5.0


def words_never_decide(source: str) -> list:
    """WordsNeverDecide as it binds contract/settle.py (5.7 measure 4): no import of re, regex, unicodedata, difflib,
    fnmatch, a retired v1 module or ANY of contract's text modules (settle has no L1 exemption: D206 moved the checks
    into contract/checks.py); no call of a string method of its list on a non-literal receiver; no in or not in with a
    string-constant operand; no reading.text or revision.text."""
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
            if parts[:3] == ['studio', 'interpretation', 'contract'] and len(parts) > 3 and parts[3] in TEXT_MODULES:
                out.append(f'imports a text module {name}')
            if parts[:2] == ['studio', 'interpretation'] and len(parts) > 2 and parts[2] in RETIRED:
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

    def test_the_notes_are_synthetic_and_no_acceptance_document(self):
        with open(DEV_EXCLUSION, encoding='ascii') as handle:
            excluded = {line.strip() for line in handle if line.strip()}
        self.assertEqual(len(excluded), 288)
        for name, text in NOTES.items():
            with self.subTest(note=name):
                for data in (text.encode('utf-8'), text.strip().encode('utf-8')):
                    self.assertNotIn(hashlib.sha256(data).hexdigest(), excluded)

    def test_words_never_decide_holds_and_refuses_each_planted_control(self):
        self.assertEqual(words_never_decide(self.source), [])
        for plant in ('import re\n', 'from studio.interpretation.contract import geometry\n',
                      'from studio.interpretation.contract import date_literals\n',
                      'from studio.interpretation.contract.segment import units\n',
                      'from studio.interpretation import lexicon\n', 'X = lambda value: value.startswith("no")\n',
                      'Y = lambda value: "no" in value\n', 'Z = lambda reading: reading.text\n',
                      'W = lambda value: value.index("x")\n'):
            with self.subTest(plant=plant):
                self.assertTrue(words_never_decide(self.source + '\n' + plant))

    def test_no_word_lists(self):
        self.assertEqual(measure_4(self.source, engine=False), [])
        self.assertTrue(measure_4(self.source + "\nNEGATORS = ('no', 'neither')\n", engine=False))  # the control
        self.assertTrue(measure_4(self.source + "\nSTATES = {'denied': 1, 'without': 2}\n", engine=False))

    def test_importing_settle_loads_no_text_module_and_no_v1_module(self):
        """What importing settle adds to a process (after Django's own start-up, which loads v1's modules for its
        apps): the contract's reading and claim modules and the engine's tables - never a text module or a v1 module."""
        code = ('import sys\nimport django\ndjango.setup()\nbefore = set(sys.modules)\n'
                'from studio.interpretation.contract import settle\n'
                'print(",".join(sorted(m for m in set(sys.modules) - before if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, cwd=APP,
                                env=dict(os.environ, DJANGO_SETTINGS_MODULE='cptstudio.settings'), timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        loaded = result.stdout.strip().splitlines()[-1].split(',')
        self.assertIn('studio.interpretation.contract.settle', loaded)
        for name in TEXT_MODULES:
            self.assertNotIn(f'studio.interpretation.contract.{name}', loaded)
        for name in RETIRED:
            self.assertNotIn(f'studio.interpretation.{name}', loaded)
        self.assertTrue(all(name == 'studio.interpretation.engine' or name.startswith((
            'studio.interpretation.contract.', 'studio.interpretation.engine.', 'studio.participants'))
            for name in loaded), loaded)

    def test_mypy_strict_passes_on_the_steps_modules_and_refuses_a_string_operation_on_a_result(self):
        def mypy(*arguments):
            return subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--follow-imports=silent', '--cache-dir',
                                   os.devnull, *arguments], capture_output=True, text=True, timeout=900, cwd=APP)

        result = mypy('studio/interpretation/contract/settle.py', 'studio/interpretation/contract/checks.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 2 source files', result.stdout)
        probe = mypy('-c', 'from studio.interpretation.contract.settle import decide, Case\n'
                           'def probe(case: Case) -> bool:\n'
                           '    return decide(case)[0].startswith("s")\n')
        self.assertEqual(probe.returncode, 1, probe.stdout + probe.stderr)
        self.assertIn('has no attribute "startswith"', probe.stdout)
