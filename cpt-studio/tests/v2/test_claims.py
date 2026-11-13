"""contract/claims.py: the claims pass 2 judges (docs/gemini-migration/FINAL-V2.md 2.4, 3.2.1-3.2.6, 3.6 and 1.8; step 2c
of 8.1). TEXT-ONLY and SYNTHETIC: every note here is written for this test (no development or acceptance document; each
is checked against the acceptance set's DEV-EXCLUSION hashes), every pass-1 answer is constructed by hand, nothing is
sent anywhere.

What is proved, item by item against the done-when of 8.1 step 2c, with the arbiter triage's repairs and DECISIONS
D194-D196, D202, D206 and D207:
- the selection from CLAIMED (SelectionTests): a fact is claimed only when CLAIMED lists it, its condition holds and it
  passed its checks; a doubted, contradicted, silent, qualified or failed fact never is, a scope list's member included;
  inherited facts are claimed per act and cite the governing source; the umbrellas are codable (D194); a statement's
  own named person is claimed in the statement form (D195);
- a template for every (attribute, state), statement-phrased for every attribute a denial is claimed on, and the label
  tables complete and unambiguous (TemplateTests);
- a control for every READY- or exclusion-path (class, attribute, kind, value) not on UNCONTROLLED - P-CONTROLLED,
  computed from step 1f's read-sets per kind (D196) - each control a form a real claim takes, but 3.2.3's three own
  forms (ControlTests); an anorectal session's sibling control false of anorectal testing (the second refutation's
  problem 2); a contrast place never one of the object's own places nor inside its segment - the duodenum's second
  portion included, judged against a tract order written apart from the implementation - and every place an object
  names controlled or not claimed, never claimed alone (ContrastTests: the arbiter's 2c#2 and 2c#3, refute-2c-r1's
  problems 1 and 3); no control ever a real claim of the same object; the all_of_kind control naming only claimable
  acts, a contradicted reported act included (2c#7, problem 6); a breadth not claimed for its control taking its
  excepted acts with it (problem 7);
- pair controls in both directions, the selection's kinds pinned (PairControlTests, 2c#8), a failed listed target
  leaving the others claimed and the set built (problem 4); the completeness claim only for an empty upper-EUS station
  list whose session kind and tract are claimable (CompletenessTests, 2c#6);
- cards naming only a type and units, no label of pass 1's values, same-anchor cards carrying each event's words
  (CardTests);
- the content keys, the seeded order, byte-identical output in any process, the per-request bound (OrderTests);
- the pins handed to the integration owner, and 5.7 measure 4 over the module (PinTests, GuardTests); no file of the
  step cites a report the harness never kept (D207).
The readings this step's builder made are recorded in DECISIONS D207.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation.contract import appraise_prompt, claims, extract_read, extract_schema, jsonschema
from studio.interpretation.contract.extract_read import FactKey
from studio.interpretation.contract.types import (AnastomosisSubtype, AnatomyType, Approach, Attribute, Breadth,
                                                  CardType, Cause, Device, FactState, Kind, Landmark, Reason,
                                                  RestatementRole, Route, SessionKind, Span, Structure, Tract)
from studio.interpretation.engine import anatomy, catalogue
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.requirements_table import CODES
from tests.v2.test_requirements import kinds_read  # step 1f's resolution of a read to the kinds it is made for
from tests.v2.test_types import measure_4  # step 0b's statement of 5.7 measure 4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'contract' / 'claims.py'
DEV_EXCLUSION = APP / 'docs' / 'gemini-migration' / 'acceptance-a1' / 'DEV-EXCLUSION.sha256'
# Every file step 2c's patch creates (DECISIONS D207's citation check).
CONTRACT = APP / 'studio' / 'interpretation' / 'contract'
STEP_NAMES = ('claims', 'appraise_schema', 'appraise_prompt', 'appraise_read')
STEP_FILES = (tuple(CONTRACT / f'{name}.py' for name in STEP_NAMES)
              + tuple(APP / 'tests' / 'v2' / f'test_{name}.py' for name in STEP_NAMES))
A = Attribute
F = extract_schema.Family
OC = rq.ObjectClass

# --- the synthetic notes, written for these tests -------------------------------------------------------------------

NOTE = ('SYNTHETIC COLONOSCOPY NOTE\n'
        'Date of service: 06/02/2031\n'
        'Endoscopist: Q. R. Vance, MD (fictional)\n'
        '\n'
        'History: Prior colonoscopy in 2027 with removal of one polyp.\n'
        'Findings: The colonoscope was advanced to the cecum.\n'
        'A 5 mm polyp in the transverse colon was removed with a cold snare.\n'
        'No biopsies were taken from the rectum.\n')
RICH = ('SYNTHETIC ENDOSCOPY NOTE\n'
        'Date of service: 06/02/2031\n'
        'Endoscopist: Q. R. Vance, MD (fictional)\n'
        'Assistant: T. Ward, RN (fictional)\n'
        '\n'
        'Procedure 1: Upper endoscopy.\n'
        'The gastroscope was advanced to the second portion of the duodenum.\n'
        'A stricture in the distal esophagus was dilated with a balloon.\n'
        'A second stricture in the stomach was dilated with a balloon.\n'
        '\n'
        'Procedure 2: Colonoscopy.\n'
        'The colonoscope was advanced to the cecum.\n'
        'A 4 mm polyp in the sigmoid colon was removed with a hot snare.\n'
        'Biopsies of a 6 mm polyp in the transverse colon were taken with cold forceps.\n'
        'Bleeding from the polypectomy site was treated with a clip.\n'
        'No biopsies were taken from the rectum.\n'
        '\n'
        'Nursing note: A clip was placed by the nurse at the request of the endoscopist.\n')
EUS = ('SYNTHETIC ULTRASOUND NOTE\n'
       'Date of service: 06/02/2031\n'
       'Endoscopist: Q. R. Vance, MD (fictional)\n'
       '\n'
       'Findings: An upper endoscopic ultrasound examination was performed.\n'
       'A fine-needle aspiration of a pancreatic mass was performed.\n')
SHARED = ('SYNTHETIC COLONOSCOPY NOTE\n'
          'Date of service: 06/02/2031\n'
          '\n'
          'Findings: The colonoscope was advanced to the cecum.\n'
          'Neither a biopsy nor a tattoo was performed.\n')
SEGMENT = ('SYNTHETIC COLONOSCOPY NOTE\n'
           'Date of service: 06/02/2031\n'
           'Endoscopist: Q. R. Vance, MD (fictional)\n'
           '\n'
           'Findings: The colonoscope was advanced to the cecum.\n'
           'No biopsies were taken from the descending colon to the rectum.\n')
PAIRS = ('SYNTHETIC COLONOSCOPY NOTE\n'
         'Date of service: 06/02/2031\n'
         'Endoscopist: Q. R. Vance, MD (fictional)\n'
         '\n'
         'Findings: The colonoscope was advanced to the cecum.\n'
         'Cold forceps biopsies were taken in the ascending colon.\n'
         'A polyp in the transverse colon was removed with hot forceps.\n'
         'A polyp in the sigmoid colon was removed with a cold snare.\n'
         'No biopsies were taken from the rectum.\n')
DUODENAL = ('SYNTHETIC UPPER ENDOSCOPY NOTE\n'
            'Date of service: 06/02/2031\n'
            'Endoscopist: Q. R. Vance, MD (fictional)\n'
            '\n'
            'Findings: The gastroscope was advanced to the fourth portion of the duodenum.\n'
            'No biopsies were taken from the duodenal bulb to the third portion of the duodenum.\n')
WIDE = ('SYNTHETIC COLONOSCOPY NOTE\n'
        'Date of service: 06/02/2031\n'
        'Endoscopist: Q. R. Vance, MD (fictional)\n'
        '\n'
        'Findings: The colonoscope was advanced to the cecum.\n'
        'Random biopsies were taken from the right colon, the transverse colon, the left colon and the rectum.\n'
        'The narrowed colon, rectum and anal canal were dilated with a balloon.\n')
MANOMETRY = ('SYNTHETIC MANOMETRY NOTE\n'
             'Date of service: 06/02/2031\n'
             'Endoscopist: Q. R. Vance, MD (fictional)\n'
             '\n'
             'Procedure: Anorectal manometry was performed.\n')
LISTED = ('SYNTHETIC COLONOSCOPY NOTE\n'
          'Date of service: 06/02/2031\n'
          'Endoscopist: Q. R. Vance, MD (fictional)\n'
          '\n'
          'Findings: The colonoscope was advanced to the cecum.\n'
          'A 5 mm polyp in the transverse colon was removed with a cold snare.\n'
          'A 3 mm polyp in the sigmoid colon was seen.\n'
          'The two polyps were not both removed with a snare.\n')
NOTES = {'NOTE': NOTE, 'RICH': RICH, 'EUS': EUS, 'SHARED': SHARED, 'SEGMENT': SEGMENT, 'PAIRS': PAIRS,
         'DUODENAL': DUODENAL, 'WIDE': WIDE, 'MANOMETRY': MANOMETRY, 'LISTED': LISTED}

# --- building pass 1's answer by hand (FINAL-V2 1.4's shape) ----------------------------------------------------------


def src(units, words='', link='statement'):
    return {'units': list(units), 'words': words, 'link': link}


def fact(value, *sources, state='supported', qualifiers=(), options=()):
    return {'state': state, 'value': value, 'qualifiers': list(qualifiers), 'sources': list(sources),
            'options': list(options)}


def neg(value, *sources):
    return fact(value, *sources, state='negated')


def event(eid, units, kind_words, status_words, kind, status='performed', **over):
    """An event: kind and status are a value (cited at the anchor's own words) or a whole fact; ``over`` sets any
    field, a nested one written ``a__b`` (target__places)."""
    anchor = src(units)
    the_kind = kind if isinstance(kind, dict) else fact(kind, dict(anchor, words=kind_words))
    the_status = status if isinstance(status, dict) else fact(status, dict(anchor, words=status_words))
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


def section(sid, start, owner='documenting_clinician', owner_source=None, role=(), occasion=(), performer=(),
            performer_person=(), end=()):
    return {'id': sid, 'start': start, 'end': list(end),
            'owner': owner if isinstance(owner, dict) else fact(owner, owner_source or src(['S3'], '',
                                                                                         'document_frame')),
            'role': list(role), 'occasion': list(occasion), 'performer': list(performer),
            'performer_person': list(performer_person)}


def session(xid, kind, kind_source, examination=None, **over):
    item = {'id': xid, 'examination': [] if examination is None else [examination], 'kind': fact(kind, kind_source),
            'encounter': [], 'tract': [], 'approach': [], 'through': [], 'reached': [], 'device_reached': [],
            'reached_anatomy': [], 'completion': [], 'stations': [], 'part_of_session': []}
    item.update(over)
    return item


def lesion(lid, units, words, **over):
    item = {'id': lid, 'description': src(units, words), 'multiplicity': [], 'places': [], 'distinct_from': [],
            'same_as': []}
    item.update(over)
    return item


def answer(sections=(), sessions=(), events=(), lesions=(), anatomy=(), people=None, doubts=(), when=None,
           clinician=None):
    return {
        'encounter': {
            'date_of_service': when or {'state': 'stated', 'value': '2031-06-02',
                                        'sources': [src(['S2'], '06/02/2031', 'document_frame')], 'options': []},
            'other_dates': [],
            'documenting_clinician': [fact('P1', src(['S3'], 'Q. R. Vance', 'document_frame'))]
            if clinician is None else clinician},
        'people': [{'id': 'P1', 'name': src(['S3'], 'Q. R. Vance'),
                    'role': fact('documenting_clinician', src(['S3'], 'Endoscopist'))}] if people is None else people,
        'sections': list(sections), 'sessions': list(sessions), 'anatomy': list(anatomy), 'lesions': list(lesions),
        'events': list(events), 'doubts': list(doubts)}


def note_answer():
    """NOTE's answer: the opening part, a History part (earlier_date), a Findings part (today, the team), one
    colonoscopy session (E1), a cold-snare removal of L1 (E2), a rectal biopsy denial (E3), a history removal (E4)."""
    return answer(
        sections=[
            section('N0', src([], '', 'section'), role=[fact('header', src(['S1'], '', 'document_frame'))],
                    occasion=[fact('on_date_of_service', src(['S2'], '', 'document_frame'))],
                    performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))]),
            section('N1', src(['S4'], 'History:', 'section'), role=[fact('history', src(['S4'], 'History:', 'section'))],
                    occasion=[fact('earlier_date', src(['S4'], 'Prior colonoscopy in 2027', 'section'))]),
            section('N2', src(['S5'], 'Findings:', 'section'),
                    role=[fact('findings', src(['S5'], 'Findings:', 'section'))],
                    occasion=[fact('on_date_of_service', src(['S2'], '', 'document_frame'))],
                    performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))])],
        sessions=[session('X1', 'colonoscopy', src(['S1'], 'COLONOSCOPY', 'document_frame'), fact('E1', src(['S5'])),
                          reached=[fact('cecum', src(['S5'], 'advanced to the cecum'))])],
        lesions=[lesion('L1', ['S6'], 'A 5 mm polyp in the transverse colon',
                        multiplicity=[fact('single', src(['S6'], 'A 5 mm polyp'))],
                        places=[fact('transverse_colon', src(['S6'], 'transverse colon'))])],
        events=[
            event('E1', ['S5'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S5']))]),
            event('E2', ['S6'], 'removed with a cold snare', 'was removed', 'snare',
                  session=[fact('X1', src(['S6']))], target__lesion=[fact('L1', src(['S6'], 'A 5 mm polyp'))],
                  target__places=[fact('transverse_colon', src(['S6'], 'transverse colon'))],
                  technique__device=[fact('cold_snare', src(['S6'], 'cold snare'))]),
            event('E3', ['S7'], 'biopsies', 'No biopsies were taken', 'biopsy',
                  neg('performed', src(['S7'], 'No biopsies were taken')), session=[fact('X1', src(['S7']))],
                  scope__breadth=[fact('single_target', src(['S7'], 'from the rectum'))],
                  target__places=[fact('rectum', src(['S7'], 'rectum'))]),
            event('E4', ['S4'], 'removal of one polyp', 'removal', 'removal')])


def read(text, data):
    """Pass 1's answer as contract/extract_read reads it (under its schema's pin, as the integration owner sets it)."""
    with mock.patch.object(interpretation, 'LOCAL_SCHEMA_SHA256_V2',
                           jsonschema.sha256_of(extract_schema.LOCAL_SCHEMA_2)):
        found = extract_read.read(json.dumps(data), len(appraise_prompt.segment.units(text)))
    assert not isinstance(found, extract_read.Refusal), found
    return found


def build(text, data, findings=None, seed=None):
    """The claim set of ``data`` about ``text``: its geometry computed by appraise_prompt.basis (no check finding unless
    ``findings`` gives some, passed as the required keyword), ordered by the seed build_request would use."""
    found = read(text, data)
    return claims.build(appraise_prompt.basis(text, (), found, findings=findings or {}),
                        seed if seed is not None else appraise_prompt.seed(text, found))


def appraised(claim_set, attribute, subject):
    """The appraised facts of ``attribute`` on ``subject``."""
    return [item for item in claim_set.appraised if item.key.attribute is attribute and item.key.object == subject]


def sentence_of(claim_set, claim_id):
    return claim_set.sentences[claim_id]


def sentences(claim_set):
    return set(claim_set.sentences.values())


# --- the selection (3.2.1) ---------------------------------------------------------------------------------------------


class SelectionTests(SimpleTestCase):
    def test_the_notes_are_synthetic_and_no_acceptance_document(self):
        with open(DEV_EXCLUSION, encoding='ascii') as handle:
            excluded = {line.strip() for line in handle if line.strip()}
        self.assertEqual(len(excluded), 288)
        for name, text in NOTES.items():
            with self.subTest(note=name):
                for data in (text.encode('utf-8'), text.strip().encode('utf-8')):
                    self.assertNotIn(hashlib.sha256(data).hexdigest(), excluded)

    def test_every_claimable_fact_of_the_note_is_claimed_once(self):
        claim_set = build(NOTE, note_answer())
        got = sorted((item.key.object, item.key.attribute.value, item.value, item.inherited_from)
                     for item in claim_set.appraised)
        self.assertEqual(got, sorted([
            ('', 'date_of_service', '2031-06-02', None),
            ('E1', 'kind', 'examination', None), ('E1', 'status', 'performed', None), ('E1', 'session', 'X1', None),
            ('E1', 'date_relation', 'on_date_of_service', 'N2'), ('E1', 'performer', 'documenting_team', 'N2'),
            ('E1', 'entry', 'documenting_clinician', 'N2'),
            ('E2', 'kind', 'snare', None), ('E2', 'status', 'performed', None), ('E2', 'session', 'X1', None),
            ('E2', 'date_relation', 'on_date_of_service', 'N2'), ('E2', 'performer', 'documenting_team', 'N2'),
            ('E2', 'entry', 'documenting_clinician', 'N2'), ('E2', 'technique.device', 'cold_snare', None),
            ('E2', 'target.places', 'transverse_colon', None), ('E2', 'target.lesion', 'L1', None),
            ('E3', 'kind', 'biopsy', None), ('E3', 'status', 'performed', None), ('E3', 'session', 'X1', None),
            ('E3', 'date_relation', 'on_date_of_service', 'N2'), ('E3', 'scope.breadth', 'single_target', None),
            ('E3', 'target.places', 'rectum', None),
            # E4, the history's removal: an umbrella, codable since DECISIONS D194, so its facts are claimed like any
            # other act's - its occasion and entry from its part (History, N1); it names no session and no performer
            ('E4', 'kind', 'removal', None), ('E4', 'status', 'performed', None),
            ('E4', 'date_relation', 'earlier_date', 'N1'), ('E4', 'entry', 'documenting_clinician', 'N1'),
            ('X1', 'kind', 'colonoscopy', None), ('X1', 'reached', 'cecum', None),
            ('L1', 'multiplicity', 'single', None)]))
        # a lesion's places are in CLAIMED (D195), but 3.2.2 gives them no template and no ruling has yet: never
        # claimed, they settle unappraised (fail-closed) - 1f's finding F1, open for the integration owner (NOTES)
        self.assertEqual([(item.key.object, item.key.attribute, item.why) for item in claim_set.unclaimed],
                         [('L1', A.PLACES, claims.Unclaimable.NO_TEMPLATE)])

    def test_a_denial_is_claimed_with_statement_phrased_sentences(self):
        claim_set = build(NOTE, note_answer())
        by_attribute = {item.key.attribute: sentence_of(claim_set, item.claim)
                        for item in claim_set.appraised if item.key.object == 'E3'}
        self.assertEqual(by_attribute, {
            A.KIND: 'This statement is about tissue samplings with forceps.',
            A.STATUS: 'This statement says that tissue sampling with forceps was not done.',
            A.SESSION: 'This statement is about session X1.',
            A.DATE_RELATION: 'This statement is about tissue samplings with forceps on the date of service.',
            A.SCOPE_BREADTH: 'This statement denies tissue sampling with forceps of the rectum.',
            A.TARGET_PLACES: 'This statement is about tissue samplings with forceps in the rectum.'})
        for item in appraised(claim_set, A.KIND, 'E2'):
            self.assertEqual(sentence_of(claim_set, item.claim), 'This act is a removal with a snare.')

    def test_an_inherited_fact_is_claimed_about_the_act_citing_the_section(self):
        claim_set = build(NOTE, note_answer())
        (date,) = appraised(claim_set, A.DATE_RELATION, 'E2')
        claim = claim_set.claim(date.claim)
        self.assertEqual((date.inherited_from, claim.subject, claim.units), ('N2', 'E2', ('S1', 'S2', 'S3')))
        self.assertEqual(claim_set.about[date.claim], 'A3')  # A1 is the history's removal (S4), A2 the examination
        (entry,) = appraised(claim_set, A.ENTRY, 'E2')
        self.assertEqual(sentence_of(claim_set, entry.claim),
                         'This act is told in the part of the document that begins at S5, written by the documenting '
                         'clinician.')
        # an act's own date relation is claimed instead, citing its anchor's sentence, and nothing is inherited
        data = note_answer()
        data['events'][1]['date_relation'] = [fact('on_date_of_service', src(['S6'], 'was removed'))]
        (own,) = appraised(build(NOTE, data), A.DATE_RELATION, 'E2')
        self.assertIsNone(own.inherited_from)

    def test_an_act_attached_to_no_section_inherits_nothing(self):
        found = read(NOTE, note_answer())
        basis = appraise_prompt.basis(NOTE, (), found, findings={})
        unattached = claims.Basis(basis.answer, basis.units, basis.findings, basis.closures,
                                  {key: value for key, value in basis.sections.items() if key != 'E2'},
                                  basis.restatement_sections, basis.anchor_words)
        claim_set = claims.build(unattached, 'seed')
        self.assertEqual([item.key.attribute for item in claim_set.appraised if item.inherited_from is not None
                          and item.key.object == 'E2'], [])
        self.assertTrue(appraised(claim_set, A.KIND, 'E2'))

    def test_a_doubted_contradicted_qualified_or_failed_fact_is_never_claimed(self):
        cases = {
            'a stated doubt on the status': ({'doubts': [{'about': 'status', 'objects': ['E2'], 'units': ['S6'],
                                                          'basis': 'stated', 'readings': ['performed']}]},
                                             (A.STATUS, 'E2')),
            'a conflict doubt': ({'doubts': [{'about': 'status', 'objects': ['E2'], 'units': ['S6', 'S7'],
                                              'basis': 'conflict', 'readings': []}]}, (A.STATUS, 'E2')),
            'a doubt on the section occasion': ({'doubts': [{'about': 'date_relation', 'objects': ['N2'],
                                                             'units': ['S5'], 'basis': 'unclear',
                                                             'readings': ['on_date_of_service', 'earlier_date']}]},
                                                (A.DATE_RELATION, 'E2')),
            'a doubt on the act names its effective fact': ({'doubts': [{'about': 'date_relation', 'objects': ['E2'],
                                                                         'units': ['S6'], 'basis': 'unclear',
                                                                         'readings': []}]}, (A.DATE_RELATION, 'E2')),
            'a malformed doubt names every fact': ({'doubts': [{'about': 'stations', 'objects': ['E2'],
                                                                'units': ['S6'], 'basis': 'stated', 'readings': []}]},
                                                   (A.TARGET_PLACES, 'E2')),
        }
        for name, (extra, (attribute, subject)) in cases.items():
            with self.subTest(case=name):
                data = note_answer()
                data.update(extra)
                self.assertEqual(appraised(build(NOTE, data), attribute, subject), [])
        data = note_answer()  # contradicted: both sides as options
        data['events'][1]['target']['places'] = [fact('', src(['S6'], 'transverse colon'), src(['S7'], 'rectum'),
                                                      state='contradicted', options=[
                                                          {'value': 'transverse_colon', 'sources': [src(['S6'])]},
                                                          {'value': 'rectum', 'sources': [src(['S7'])]}])]
        self.assertEqual(appraised(build(NOTE, data), A.TARGET_PLACES, 'E2'), [])
        data = note_answer()  # qualified: any qualifier but approximate
        data['events'][1]['technique']['device'] = [fact('cold_snare', src(['S6'], 'cold snare'),
                                                         qualifiers=['hedged'])]
        self.assertEqual(appraised(build(NOTE, data), A.TECHNIQUE_DEVICE, 'E2'), [])
        data['events'][1]['technique']['device'][0]['qualifiers'] = ['approximate']
        self.assertEqual(len(appraised(build(NOTE, data), A.TECHNIQUE_DEVICE, 'E2')), 1)
        data = note_answer()  # a failed check: the reader's own finding, and the caller's
        data['events'][1]['technique']['device'] = [fact('cold_snare', src(['S99'], 'cold snare'))]
        self.assertEqual(appraised(build(NOTE, data), A.TECHNIQUE_DEVICE, 'E2'), [])
        findings = {FactKey(F.EVENT, 'E2', A.TECHNIQUE_DEVICE, 0): (Reason.WORDS_NOT_IN_UNITS,)}
        self.assertEqual(appraised(build(NOTE, note_answer(), findings), A.TECHNIQUE_DEVICE, 'E2'), [])
        findings = {FactKey(F.SECTION, 'N2', A.OCCASION, 0): (Reason.FRAME_ROLE,)}
        self.assertEqual(appraised(build(NOTE, note_answer(), findings), A.DATE_RELATION, 'E2'), [])

    def test_a_doubted_statement_kind_is_never_shown(self):
        # a statement-phrased sentence names the statement's kind: with that kind doubted, no sentence may name it
        data = note_answer()
        data['doubts'] = [{'about': 'kind', 'objects': ['E3'], 'units': ['S7'], 'basis': 'unclear',
                           'readings': ['biopsy', 'hot_biopsy']}]
        claim_set = build(NOTE, data)
        about_e3 = {item.key.attribute: item for item in claim_set.appraised if item.key.object == 'E3'}
        self.assertEqual(set(about_e3), {A.SESSION})  # the one sentence that names no kind
        self.assertEqual(sentence_of(claim_set, about_e3[A.SESSION].claim), 'This statement is about session X1.')
        self.assertEqual({(item.key.attribute, item.why) for item in claim_set.unclaimed if item.key.object == 'E3'},
                         {(A.STATUS, claims.Unclaimable.KIND), (A.DATE_RELATION, claims.Unclaimable.KIND),
                          (A.SCOPE_BREADTH, claims.Unclaimable.KIND), (A.TARGET_PLACES, claims.Unclaimable.KIND)})
        about_the_denial = {claim_set.sentences[claim.id] for claim in claim_set.claims
                            if claim_set.objects.get(claim_set.about[claim.id]) == (F.EVENT, 'E3')}
        self.assertTrue(about_the_denial)
        for sentence in about_the_denial:  # (the history's removal is controlled by a forceps biopsy: D194)
            self.assertNotIn('tissue sampling', sentence)
        self.assertFalse([pair for pair in claim_set.pair_controls if pair.subject[1] == 'E3'])

    def test_an_invalid_anchor_or_a_kind_not_established_claims_nothing(self):
        data = note_answer()
        data['events'][1]['anchor']['units'] = ['S6', 'S8']  # unknown unit
        claim_set = build(NOTE, data)
        self.assertFalse([item for item in claim_set.appraised if item.key.object == 'E2'])
        # every Kind is codable (D194: the umbrellas too); an event whose kind pass 1 contradicts has none
        data = note_answer()
        data['events'][1]['kind'] = fact('', src(['S6'], 'removed with a cold snare'), state='contradicted', options=[
            {'value': 'snare', 'sources': [src(['S6'])]}, {'value': 'emr', 'sources': [src(['S6'])]}])
        self.assertFalse([item for item in build(NOTE, data).appraised if item.key.object == 'E2'])
        self.assertEqual(rq.CODABLE_KINDS, frozenset(Kind))

    def test_the_umbrellas_are_codable(self):
        # DECISIONS D194: 4.10's broad denial "No polyp was removed today." (kind removal, all_of_kind) is claimed, its
        # breadth's control naming the reported snare; a positive umbrella act is claimed too (rank 9's act_method)
        data = note_answer()
        data['events'][2] = event('E3', ['S7'], 'biopsies', 'No biopsies were taken', 'removal',
                                  neg('performed', src(['S7'], 'No biopsies were taken')),
                                  session=[fact('X1', src(['S7']))],
                                  scope__breadth=[fact('all_of_kind', src(['S7'], 'No biopsies'))])
        claim_set = build(NOTE, data)
        by = {item.key.attribute: item for item in claim_set.appraised if item.key.object == 'E3'}
        self.assertEqual(sentence_of(claim_set, by[A.KIND].claim), 'This statement is about removals by any method.')
        self.assertEqual(sentence_of(claim_set, by[A.KIND].control),
                         'This statement is about tissue samplings with forceps.')
        # the reported acts of the kind, over the document (D207's reading of 2c): the history's removal and the snare
        self.assertEqual(sentence_of(claim_set, by[A.SCOPE_BREADTH].control),
                         'This statement denies only removals by any method other than acts A1 and A3.')
        self.assertEqual((claim_set.objects['A1'], claim_set.objects['A3']), ((F.EVENT, 'E4'), (F.EVENT, 'E2')))
        (removal,) = appraised(claim_set, A.KIND, 'E4')
        self.assertEqual(sentence_of(claim_set, removal.claim), 'This act is a removal by a method the document does '
                                                                'not give.')

    def test_conditions_of_claimed(self):
        # performer_person only when the effective performer is other_clinician
        data = note_answer()
        data['people'].append({'id': 'P2', 'name': src(['S4'], 'Prior'), 'role': fact('other', src(['S4']))})
        data['events'][1]['performer_person'] = [fact('P2', src(['S6'], 'was removed'))]
        self.assertEqual(appraised(build(NOTE, data), A.PERFORMER_PERSON, 'E2'), [])
        data['events'][1]['performer'] = [fact('other_clinician', src(['S6'], 'was removed'))]
        (person,) = appraised(build(NOTE, data), A.PERFORMER_PERSON, 'E2')
        claim_set = build(NOTE, data)
        self.assertEqual(sentence_of(claim_set, person.claim), 'This act was done by the person named at S4.')
        # an injection's structure only in an EUS session; a drainage's always
        found = build(EUS, eus_answer(structure=True))
        self.assertEqual([item.value for item in appraised(found, A.TARGET_STRUCTURE, 'E2')],
                         ['pancreatic_fluid_collection'])
        # a session's encounter only when it holds a visit
        self.assertEqual(appraised(build(NOTE, note_answer_with(encounter=True)), A.ENCOUNTER, 'X1'), [])

    def test_a_statement_names_its_own_person_in_the_statement_form(self):
        # DECISIONS D195: a statement's own named person is claimed with the statement-phrased template, and its control
        # names another person's units when another person is named (4.5's performer row)
        data = note_answer()
        data['people'].append({'id': 'P2', 'name': src(['S4'], 'Prior'), 'role': fact('other', src(['S4']))})
        data['events'][2]['performer_person'] = [fact('P2', src(['S7'], 'No biopsies were taken'))]
        claim_set = build(NOTE, data)
        (person,) = appraised(claim_set, A.PERFORMER_PERSON, 'E3')
        self.assertEqual(sentence_of(claim_set, person.claim),
                         'This statement is about tissue samplings with forceps by the person named at S4.')
        self.assertEqual(sentence_of(claim_set, person.control),
                         'This statement is about tissue samplings with forceps by the person named at S3.')
        self.assertEqual(claims.template(claims.TemplateId.STMT_PERFORMER_PERSON),
                         'This statement is about {kinds} by the person named at {person}.')

    def test_a_doubt_naming_a_scope_list_leaves_its_members_unclaimed(self):
        # a doubt about whole, or a malformed one, names every attribute of its objects, a statement's scope lists
        # included (3.1 S2, 3.3): a covered act is never claimed under it (the covers form names no kind, so nothing
        # else stopped it)
        data = rich_answer()
        data['events'][7]['scope']['covers'] = ['E6']
        self.assertEqual(len(appraised(build(RICH, data), A.SCOPE_COVERS, 'E8')), 1)
        data['doubts'] = [{'about': 'whole', 'objects': ['E8'], 'units': ['S14'], 'basis': 'stated', 'readings': []}]
        claim_set = build(RICH, data)
        self.assertEqual([item for item in claim_set.appraised if item.key.object == 'E8'], [])
        self.assertNotIn('This statement applies to act A6.', sentences(claim_set))

    def test_a_restates_restatement_is_claimed_only_in_the_documenting_clinicians_part(self):
        data = note_answer()
        data['sections'].append(section('N3', src(['S7'], 'No', 'section'), owner='nursing',
                                         owner_source=src(['S7'], 'No', 'section')))
        data['events'] = data['events'][:2]
        data['events'][1]['anchor'] = {'units': ['S7'], 'kind_words': 'biopsies', 'status_words': 'were taken'}
        data['events'][1]['kind'] = fact('snare', src(['S7'], 'biopsies'))
        data['events'][1]['status'] = fact('performed', src(['S7'], 'were taken'))
        data['events'][1]['target']['lesion'] = []
        data['events'][1]['target']['places'] = []
        data['events'][1]['technique']['device'] = []
        data['events'][1]['session'] = [fact('X1', src(['S7']))]
        data['events'][1]['restatements'] = [{'units': ['S6'], 'role': 'restates'}]
        claim_set = build(NOTE, data)
        (role,) = appraised(claim_set, A.RESTATEMENTS_ROLE, 'E2')
        self.assertEqual(sentence_of(claim_set, role.claim),
                         'The part of the document beginning at S6 tells this act in full, in its own words, not only '
                         'as a summary, a title or a reference to another part.')
        self.assertEqual(sentence_of(claim_set, role.control),
                         'The part of the document beginning at S6 only summarizes this act, names it, or refers to '
                         'where it is told.')
        (entry,) = appraised(claim_set, A.ENTRY, 'E2')
        self.assertEqual((entry.value, entry.inherited_from), ('nursing', 'N3'))
        data['events'][1]['restatements'] = [{'units': ['S6'], 'role': 'summarizes'}]
        self.assertEqual(appraised(build(NOTE, data), A.RESTATEMENTS_ROLE, 'E2'), [])

    def test_the_lesions_of_claimed_acts_only(self):
        data = note_answer()
        data['lesions'].append(lesion('L2', ['S4'], 'one polyp', multiplicity=[fact('single', src(['S4'], 'one'))]))
        claim_set = build(NOTE, data)
        self.assertEqual(appraised(claim_set, A.MULTIPLICITY, 'L2'), [])  # no claimed act is done to it
        self.assertEqual(len(appraised(claim_set, A.MULTIPLICITY, 'L1')), 1)


def eus_answer(structure=False, stations=(), tract='upper'):
    """EUS's answer: an upper EUS session (E1 its examination) and an FNA (E2), or a drainage with a structure."""
    kind = 'drainage' if structure else 'fna'
    target = {'target__structure': [fact('pancreatic_fluid_collection', src(['S5'], 'pancreatic mass'))]} \
        if structure else {}
    return answer(
        sections=[section('N0', src([], '', 'section')),
                  section('N1', src(['S4'], 'Findings:', 'section'),
                          occasion=[fact('on_date_of_service', src(['S2'], '', 'document_frame'))],
                          performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))])],
        sessions=[session('X1', 'eus', src(['S4'], 'endoscopic ultrasound'), fact('E1', src(['S4'])),
                          tract=[fact(tract, src(['S4'], 'upper'))], stations=list(stations))],
        events=[event('E1', ['S4'], 'endoscopic ultrasound examination', 'was performed', 'examination',
                      session=[fact('X1', src(['S4']))]),
                event('E2', ['S5'], 'fine-needle aspiration', 'was performed', kind,
                      session=[fact('X1', src(['S5']))], **target)])


def note_answer_with(encounter=False):
    data = note_answer()
    if encounter:
        data['sessions'][0]['encounter'] = [fact('this_encounter', src(['S5']))]
    return data


# --- the templates (3.2.2) ---------------------------------------------------------------------------------------------

# 3.2.2's dashes: the (object class, attribute) pairs whose negated state has no form. Every CLAIMED attribute's
# negated state is either in FORMS or here.
NO_NEGATED_FORM = {
    (OC.ACT, A.KIND), (OC.ACT, A.OTHER_CLASS), (OC.ACT, A.DATE_RELATION), (OC.ACT, A.DATE),
    (OC.ACT, A.PERFORMER_PERSON), (OC.ACT, A.ENTRY), (OC.ACT, A.SESSION), (OC.ACT, A.TARGET_LESION),
    (OC.ACT, A.TARGET_STRUCTURE), (OC.ACT, A.TARGET_DUCT), (OC.ACT, A.TECHNIQUE_ROUTE), (OC.ACT, A.PURPOSE),
    (OC.ACT, A.PART_RELATION), (OC.ACT, A.ACCESS_OUTCOME), (OC.ACT, A.VISIT_BASIS), (OC.ACT, A.RESTATEMENTS_ROLE),
    (OC.STATEMENT, A.KIND), (OC.STATEMENT, A.SESSION), (OC.STATEMENT, A.DATE_RELATION), (OC.STATEMENT, A.PERFORMER),
    (OC.STATEMENT, A.PERFORMER_PERSON),
    (OC.STATEMENT, A.SCOPE_BREADTH), (OC.STATEMENT, A.SCOPE_COVERS), (OC.STATEMENT, A.SCOPE_EXCEPTS),
    (OC.STATEMENT, A.TARGET_LESION), (OC.STATEMENT, A.TARGET_PLACES), (OC.STATEMENT, A.TARGET_ANATOMY),
    (OC.STATEMENT, A.TARGET_DUCT), (OC.STATEMENT, A.SCOPE_TARGETS), (OC.STATEMENT, A.SCOPE_SEGMENT),
    (OC.STATEMENT, A.TECHNIQUE_DEVICE),
    (OC.SESSION, A.KIND), (OC.SESSION, A.ENCOUNTER), (OC.SESSION, A.TRACT), (OC.SESSION, A.APPROACH),
    (OC.SESSION, A.THROUGH), (OC.SESSION, A.REACHED_ANATOMY), (OC.SESSION, A.COMPLETION),
    (OC.SESSION, A.PART_OF_SESSION),
    (OC.ANATOMY, A.TYPE), (OC.ANATOMY, A.SUBTYPE), (OC.ANATOMY, A.JOINS),
    (OC.LESION, A.MULTIPLICITY), (OC.LESION, A.PLACES), (OC.LESION, A.DISTINCT_FROM), (OC.LESION, A.SAME_AS),
    (OC.ENCOUNTER, A.DATE_OF_SERVICE)}
# The supported state of a statement's status has no form either: a statement's status is claimed negated (3.2.2). A
# lesion's places are in CLAIMED (DECISIONS D195: SITE's lesion arm), but neither 3.2.2 nor a ruling gives them a
# template (or 3.2.3 a control): never claimed, they settle unappraised and hold (fail-closed). Step 1f's finding F1,
# open for the integration owner: a template and its control are a decision, not this step's to invent.
NO_SUPPORTED_FORM = {(OC.STATEMENT, A.STATUS), (OC.LESION, A.PLACES)}
# The three controls 3.2.3 gives a form of its own, which no real claim takes: the restatement's summary, the
# statement's "was done" and the completeness claim's limitation (DECISIONS D196 keeps them as prescribed). D196 moved
# a performed act's control to the statement form, a real claim's; 3.2.2's act form of a negated status
# (ACT_STATUS_NEGATED) no claim takes, as an event whose status is negated is a statement (3.2.1).
OWN_FORMS = {claims.TemplateId.ACT_RESTATES_SUMMARY, claims.TemplateId.STMT_DONE, claims.TemplateId.SESSION_SOME_STATIONS}
# The (class, attribute, state) rows of FORMS no real claim reaches.
UNREACHED_FORMS = {(OC.ACT, A.STATUS, FactState.NEGATED)}


def placeholders(sentence):
    return set(re.findall(r'\{([a-z_]+)\}', sentence))


class TemplateTests(SimpleTestCase):
    def test_every_template_is_in_one_table_and_fills_only_its_slots(self):
        self.assertEqual(set(claims.TEMPLATES) | set(claims.STATEMENT_TEMPLATES), set(claims.TemplateId))
        self.assertFalse(set(claims.TEMPLATES) & set(claims.STATEMENT_TEMPLATES))
        slots = {slot.value for slot in claims.Slot}
        for template_id in claims.TemplateId:
            with self.subTest(template=template_id.value):
                sentence = claims.template(template_id)
                self.assertTrue(placeholders(sentence) <= slots, placeholders(sentence) - slots)
                self.assertTrue(sentence.endswith('.') and sentence[0].isupper())
        # every statement-phrased template begins with "This statement", and so do breadth and covers
        for template_id in claims.TemplateId:
            statement = template_id.value.startswith('statement.')
            self.assertEqual(claims.template(template_id).startswith('This statement'), statement, template_id)

    def test_every_template_is_filled_by_one_arm(self):
        import inspect
        source = inspect.getsource(claims._Builder.fill)
        for template_id in claims.TemplateId:
            arms = (template_id in claims._LABEL_SLOT) + (template_id in claims._REF_SLOT) + (
                f'T.{template_id.name}' in source)
            with self.subTest(template=template_id.value):
                self.assertGreaterEqual(arms, 1)
                self.assertFalse(template_id in claims._LABEL_SLOT and template_id in claims._REF_SLOT)

    def test_a_template_for_every_attribute_and_state(self):
        for object_class, entries in rq.CLAIMED.items():
            for entry in entries:
                if entry.condition is rq.Condition.COMPLETENESS:
                    continue
                for state in (FactState.SUPPORTED, FactState.NEGATED):
                    key = (object_class, entry.attribute, state)
                    with self.subTest(claimed=key):
                        dash = (object_class, entry.attribute) in (
                            NO_NEGATED_FORM if state is FactState.NEGATED else NO_SUPPORTED_FORM)
                        self.assertNotEqual(key in claims.FORMS, dash)
        # the dashes name only attributes CLAIMED lists, so none is stale
        claimed = {(object_class, entry.attribute) for object_class, entries in rq.CLAIMED.items()
                   for entry in entries}
        self.assertTrue(NO_NEGATED_FORM <= claimed and NO_SUPPORTED_FORM <= claimed)

    def test_statement_phrased_for_every_attribute_a_denial_is_claimed_on(self):
        for entry in rq.CLAIMED[OC.STATEMENT]:
            state = FactState.NEGATED if entry.attribute is A.STATUS else FactState.SUPPORTED
            form = claims.FORMS[(OC.STATEMENT, entry.attribute, state)]
            with self.subTest(attribute=entry.attribute.value):
                self.assertTrue(claims.template(form).startswith('This statement'))
        for value, form in ((claims.Breadth.ALL_OF_KIND, claims.TemplateId.STMT_BREADTH_ALL),
                            (claims.Breadth.EXCEPTIVE, claims.TemplateId.STMT_BREADTH_EXCEPTIVE)):
            self.assertIs(claims.FORMS_BY_VALUE[(OC.STATEMENT, A.SCOPE_BREADTH, FactState.SUPPORTED, value)], form)

    def test_the_label_tables_are_complete_and_tell_every_value_apart(self):
        enumerations = {type(member) for member in claims.LABELS}
        for enumeration in enumerations:
            with self.subTest(enumeration=enumeration.__name__):
                labels = [claims.LABELS[member] for member in enumeration]  # KeyError: a value without a label
                self.assertEqual(len(set(labels)), len(labels))
        self.assertEqual(set(claims.KIND_LABELS), set(Kind))
        for position in range(3):
            forms = [claims.KIND_LABELS[kind][position] for kind in Kind if kind is not Kind.MODERATE_SEDATION]
            self.assertEqual(len(set(forms)), len(forms))
        self.assertEqual(set(claims.PLACE_LABELS), set(Landmark))
        self.assertEqual(len(set(claims.PLACE_LABELS.values())), len(Landmark))
        self.assertNotIn(claims.PLACE_LABEL_DEPTH, claims.PLACE_LABELS.values())
        self.assertEqual(set(claims.CARD_PHRASES), set(CardType))
        # no label holds a brace (it would be read as a slot) or a value of an enumeration written as a value
        for text in [*claims.LABELS.values(), *claims.PLACE_LABELS.values(),
                     *(form for forms in claims.KIND_LABELS.values() for form in forms)]:
            self.assertFalse(set(text) & set('{}_'), text)

    def test_every_control_takes_a_form_a_real_claim_takes_but_the_three_own_forms(self):
        # 3.2.3: "written with the same templates ... so nothing about its wording marks it". DECISIONS D196 (the
        # arbiter's 2c#4): a performed act's control is the statement-phrased "This statement says that {kind} was not
        # done.", which every denial's status claim takes; the act form of a negated status is a form no claim takes
        reached = {form for key, form in claims.FORMS.items() if key not in UNREACHED_FORMS}
        reached |= set(claims.FORMS_BY_VALUE.values())
        for rule in claims.CONTROLS:
            with self.subTest(rule=(rule.object_class.value, rule.attribute.value, rule.state.value)):
                form = rule.form or claims.FORMS[(rule.object_class, rule.as_attribute or rule.attribute,
                                                  rule.as_state or rule.state)]
                self.assertTrue(form in reached or form in OWN_FORMS, form)
                self.assertNotIn(form, {claims.FORMS[key] for key in UNREACHED_FORMS})
        performed = claims.control_rule(OC.ACT, A.STATUS, FactState.SUPPORTED, claims.Status.PERFORMED)
        self.assertIs(performed.form, claims.TemplateId.STMT_NOT_DONE)
        self.assertIs(claims.FORMS[(OC.STATEMENT, A.STATUS, FactState.NEGATED)], claims.TemplateId.STMT_NOT_DONE)
        self.assertEqual({rule.form for rule in claims.CONTROLS if rule.form in OWN_FORMS} | {
            claims.TemplateId.SESSION_SOME_STATIONS}, OWN_FORMS)
        # and the three own forms are taken by no real claim
        self.assertFalse(OWN_FORMS & reached)
        # an event whose claimed status is negated is a statement, so the act form of a negated status is reached by
        # no claim: an act's negated status, as pass 1 can write it, is claimed in the statement form
        found = build(NOTE, note_answer())
        self.assertNotIn(claims.TemplateId.ACT_STATUS_NEGATED.value, {claim.template for claim in found.claims})
        (denial,) = appraised(found, A.STATUS, 'E3')
        self.assertEqual(found.claim(denial.claim).template, claims.TemplateId.STMT_NOT_DONE.value)

    def test_a_performed_acts_control_is_the_statement_form_and_needs_its_kind(self):
        claim_set = build(NOTE, note_answer())
        (status,) = appraised(claim_set, A.STATUS, 'E2')
        self.assertEqual(sentence_of(claim_set, status.control),
                         'This statement says that removal with a snare was not done.')
        # the form names the act's kind: with that kind doubted the control cannot be written, and the status is not
        # claimed (fail-closed: never a status claim standing uncontrolled)
        data = note_answer()
        data['doubts'] = [{'about': 'kind', 'objects': ['E2'], 'units': ['S6'], 'basis': 'unclear',
                           'readings': ['snare', 'emr']}]
        claim_set = build(NOTE, data)
        self.assertEqual(appraised(claim_set, A.STATUS, 'E2'), [])
        self.assertIn(claims.Unclaimable.CONTROL, {item.why for item in claim_set.unclaimed
                                                   if (item.key.object, item.key.attribute) == ('E2', A.STATUS)})
        self.assertTrue(appraised(claim_set, A.TARGET_PLACES, 'E2'))  # its other facts' forms name no kind


# --- the controls (3.2.3) ----------------------------------------------------------------------------------------------

# P-CONTROLLED (9.4), as DECISIONS D196 completes it: checked per object class, attribute, kind and value. Every
# (class, attribute, kind) a READY or an exclusion path reads - step 1f's read-sets, each read resolved under each code
# to the act kinds it is made for (tests/v2/test_requirements.kinds_read, 1f's own resolution) - that CLAIMED claims, in
# every state and value a claim of it can take (FORMS, NEGATED_VALUES), has a control rule whose contrary exists, or an
# UNCONTROLLED entry, or is a value that decides no code (VALUES_DECIDING_NOTHING, each row naming its source). D196
# decided every gap the attribute-level check had pinned (act.target.duct, session.through, session.part_of_session),
# and the ones it could not see (the places of thirteen kinds, nine session kinds, the visit, a transanal approach):
# none is left, and READ_NOT_CLAIMED is gone with them (D195: every attribute a rule reads is claimed).
DESIGN_GAPS: set = set()
# The values 3.2.3's rows and the rulings leave without a control, because no READY or exclusion path turns on them. A
# control is needed only for values on such a path (D196). Two rows rest on 3.2.3's own row and are open findings for
# the integration owner (NOTES: the pairing's technique row reads every device; exclusion condition 3 reads a targeted
# breadth): built as the design specifies, pinned here so that deciding them moves this table.
READY_FAMILIES = frozenset(row.family for row in CODES.values() if row.template not in rq.NEVER_READY)
VALUES_DECIDING_NOTHING = {
    (OC.ACT, A.KIND): (frozenset({Kind.EXAMINATION, Kind.EM_VISIT}),
                       '3.2.3: decided through session.kind and the visit facts, which are controlled'),
    (OC.STATEMENT, A.KIND): (frozenset({Kind.EXAMINATION, Kind.EM_VISIT}),
                             '3.2.3: decided through session.kind and the visit facts, which are controlled'),
    (OC.ACT, A.TECHNIQUE_DEVICE): (frozenset(Device) - frozenset(catalogue.TECHNIQUE_CLASS),
                                   "3.2.3's row: a technique class (TECH); open finding D-1"),
    (OC.STATEMENT, A.TECHNIQUE_DEVICE): (frozenset(Device) - frozenset(claims.DEVICE_SIBLINGS),
                                         "3.2.3's row: the sibling devices; open finding D-1"),
    (OC.STATEMENT, A.SCOPE_BREADTH): (frozenset({Breadth.SINGLE_TARGET, Breadth.LISTED_TARGETS, Breadth.SEGMENT}),
                                      "3.2.3's row: the target row decides; open finding D-2"),
    (OC.ACT, A.TECHNIQUE_ROUTE): (frozenset(Route) - {Route.EUS_TRANSMURAL}, "3.2.3's row: ROUTE reads 43253's"),
    (OC.ACT, A.TARGET_STRUCTURE): (frozenset(Structure) - {Structure.PANCREATIC_FLUID_COLLECTION},
                                   "3.2.3's row: STRUCT:pfc"),
    (OC.ACT, A.CAUSE): (frozenset({Cause.ACT_OF_THIS_SESSION}), "3.2.3's row: it can only bundle"),
    (OC.ACT, A.RESTATEMENTS_ROLE): (frozenset(RestatementRole) - {RestatementRole.RESTATES},
                                    'CLAIMED: only a restates restatement is claimed (3.2.1)'),
    (OC.ANATOMY, A.SUBTYPE): (frozenset(AnastomosisSubtype) - frozenset(claims.SUBTYPE_SIBLINGS),
                              "3.2.3's row: COLFULL reads an ileocolic subtype"),
    (OC.ANATOMY, A.TYPE): (frozenset(AnatomyType) - {AnatomyType.ILEAL_POUCH, AnatomyType.GASTRIC_POUCH,
                                                     AnatomyType.STOMA},
                           "D196: anatomy types outside 3.2.3's row (a surgically absent organ is its organ fact's)"),
    (OC.SESSION, A.APPROACH): (frozenset(Approach) - {Approach.ORAL, Approach.THROUGH_STOMA, Approach.THROUGH_POUCH},
                               'D196'),
    (OC.SESSION, A.TRACT): (frozenset({Tract.PANCREATOBILIARY}), 'D196'),
    (OC.SESSION, A.KIND): (frozenset(SessionKind) - READY_FAMILIES,
                           'D196: no code of these families can be READY (sedation is recognised only, D80)'),
    # engine/anatomy sets these apart from nothing and puts them in no region: no class, region or difference
    (OC.ACT, A.TARGET_PLACES): (anatomy.ALTERED | anatomy.UNPLACED, 'engine/anatomy: never disjoint, in no region'),
    (OC.STATEMENT, A.TARGET_PLACES): (anatomy.ALTERED | anatomy.UNPLACED,
                                      'engine/anatomy: never disjoint, in no region'),
    (OC.STATEMENT, A.SCOPE_SEGMENT): (anatomy.ALTERED | anatomy.UNPLACED,
                                      'engine/anatomy: never disjoint, in no region'),
}
# The negated forms 3.2.3's rows leave without a control: they control an act's performer, places and technique-class
# device in the supported state only, as every rule reads the supported value (4.3 rows 4 and 6, SITE, TECH; 4.5's rows
# set a pair apart on supported values), so the denial "this act was not done by / in / with ..." can only hold.
NEGATED_FORMS_DECIDING_NOTHING = {(OC.ACT, A.PERFORMER), (OC.ACT, A.TARGET_PLACES), (OC.ACT, A.TECHNIQUE_DEVICE)}


def deciding_reads():
    """(class, attribute, kind) of every claimed read made on a READY or an exclusion path, per code (kind None for an
    object that is no event): step 1f's read-sets, resolved as its own P-READSET resolves them."""
    found = set()
    for code in [str(code) for code in CODES] + ['46221']:
        template = rq.spec(code).template
        for requirement in rq.requirements_of(code):
            for read_ in rq.RULES[requirement].reads_for(template):
                object_class = rq.ROLE_CLASS[read_.role]
                if object_class is None or read_.attribute is None or not read_.paths & {rq.Path.READY,
                                                                                          rq.Path.EXCLUSION}:
                    continue
                if object_class in (OC.ACT, OC.STATEMENT):
                    found |= {(object_class, read_.attribute, kind) for kind in kinds_read(code, read_)
                              if rq.claimed(object_class, read_.attribute, kind)}
                elif rq.claimed(object_class, read_.attribute):
                    found.add((object_class, read_.attribute, None))
    return found


def claim_values(object_class, attribute, kind):
    """The values a claim of the attribute can take: its enumeration's (an event's kind: its own), or None for an id."""
    if attribute is A.KIND and object_class in (OC.ACT, OC.STATEMENT):
        return (kind,)
    enum = claims._ENUM_OF.get((claims._FAMILY_OF[object_class], attribute))
    return tuple(enum) if enum is not None else (None,)


def contrary_exists(rule, value):
    """Whether ``rule`` has a contrary for ``value`` wherever its object is (the document-conditional rules - another
    object, the reported acts, an anatomy point - count: 3.2.3 controls them where one exists)."""
    if rule.contrary is claims.Contrary.TABLE:
        return value is not None and claims.table(rule.table).get(value) is not None
    if rule.contrary in (claims.Contrary.CONTRAST, claims.Contrary.FIRST_CONTRAST):
        return bool(claims.CONTRAST_PLACES.get(value))
    if rule.contrary is claims.Contrary.FIXED:
        return rule.fixed is not None
    return True


def uncontrolled_values(reads=None):
    """Every (class, attribute, kind, state, value) a READY or exclusion read claims with neither a control nor an
    UNCONTROLLED entry, nor a row of VALUES_DECIDING_NOTHING."""
    found = set()
    for object_class, attribute, kind in reads if reads is not None else deciding_reads():
        for state in (FactState.SUPPORTED, FactState.NEGATED):
            if (object_class, attribute, state) not in claims.FORMS or \
                    (object_class, attribute, state) in UNREACHED_FORMS:
                continue
            if state is FactState.NEGATED and (object_class, attribute) in NEGATED_FORMS_DECIDING_NOTHING:
                continue
            allowed = claims.NEGATED_VALUES.get((object_class, attribute)) if state is FactState.NEGATED else None
            for value in claim_values(object_class, attribute, kind):
                if allowed is not None and value not in allowed:
                    continue
                rule = claims.control_rule(object_class, attribute, state, value, kind)
                if (rule is not None and contrary_exists(rule, value)) or claims.uncontrolled(
                        object_class, attribute, value) is not None:
                    continue
                if value in VALUES_DECIDING_NOTHING.get((object_class, attribute), (frozenset(),))[0]:
                    continue
                found.add((object_class, attribute, kind, state, value))
    return found


class ControlTests(SimpleTestCase):
    def test_p_controlled_per_class_attribute_kind_and_value(self):
        reads = deciding_reads()
        self.assertGreater(len(reads), 400)
        # the kinds a check per attribute missed are read and claimed: thirteen kinds' places, the examination's
        self.assertLessEqual({(OC.ACT, A.TARGET_PLACES, kind) for kind in (
            Kind.ABLATION, Kind.BAND_LIGATION, Kind.BIOPSY, Kind.BLEEDING_CONTROL, Kind.CLIP, Kind.DRAINAGE, Kind.EMR,
            Kind.ESD, Kind.FNA, Kind.HOT_BIOPSY, Kind.INJECTION, Kind.SNARE, Kind.TATTOO, Kind.EXAMINATION)}, reads)
        self.assertEqual(uncontrolled_values(reads), DESIGN_GAPS)
        # every row of VALUES_DECIDING_NOTHING is read on such a path and none of its values has a control: no stale row
        read_attributes = {(object_class, attribute) for object_class, attribute, _kind in reads}
        for (object_class, attribute), (values, _source) in VALUES_DECIDING_NOTHING.items():
            with self.subTest(row=(object_class.value, attribute.value)):
                self.assertIn((object_class, attribute), read_attributes)
                for value in values:
                    state = FactState.SUPPORTED
                    rule = claims.control_rule(object_class, attribute, state, value, value if isinstance(
                        value, Kind) else None)
                    self.assertFalse(rule is not None and contrary_exists(rule, value), value)
        # the controls: a kind-level gap (the review's mutant R2, act.kind narrowed to snare) and a value-level one (a
        # session sibling dropped) are both found
        narrowed = tuple(claims.ControlRule(rule.object_class, rule.attribute, rule.state, rule.contrary, rule.values,
                                            frozenset({Kind.SNARE}), rule.as_attribute, rule.as_state, rule.table,
                                            rule.fixed, rule.form)
                         if (rule.object_class, rule.attribute) == (OC.ACT, A.KIND) else rule
                         for rule in claims.CONTROLS)
        with mock.patch.object(claims, 'CONTROLS', narrowed):
            self.assertIn((OC.ACT, A.KIND, Kind.BIOPSY, FactState.SUPPORTED, Kind.BIOPSY), uncontrolled_values(reads))
        fewer = {key: value for key, value in claims.SESSION_SIBLINGS.items() if key is not SessionKind.OFFICE_EM}
        with mock.patch.object(claims, 'SESSION_SIBLINGS', fewer):
            self.assertIn((OC.SESSION, A.KIND, None, FactState.SUPPORTED, SessionKind.OFFICE_EM),
                          uncontrolled_values(reads))

    def test_the_gaps_d196_decided(self):
        # act.target.duct: biliary against pancreatic, pancreatic against biliary, cystic against pancreatic
        self.assertEqual({key.value: value.value for key, value in claims.table(claims.Table.DUCT_CONTRARY).items()},
                         {'biliary': 'pancreatic', 'pancreatic': 'biliary', 'cystic': 'pancreatic'})
        self.assertIsNotNone(claims.control_rule(OC.ACT, A.TARGET_DUCT, FactState.SUPPORTED, claims.Duct.CYSTIC))
        # session.through: another anatomy entry when one exists, else UNCONTROLLED; part_of_session UNCONTROLLED
        through = claims.control_rule(OC.SESSION, A.THROUGH, FactState.SUPPORTED, None)
        self.assertIs(through.contrary, claims.Contrary.ANOTHER_ANATOMY)
        self.assertIs(claims.uncontrolled(OC.SESSION, A.THROUGH).why, claims.Why.ONE_ANATOMY_ENTRY)
        self.assertIs(claims.uncontrolled(OC.SESSION, A.PART_OF_SESSION).why, claims.Why.ONLY_HOLDS)
        # achieved_after_failed_attempts takes the failed form
        self.assertIs(claims.table(claims.Table.ACCESS_CONTRARY)[claims.AccessOutcome.ACHIEVED_AFTER_FAILED_ATTEMPTS],
                      claims.AccessOutcome.FAILED)
        # the places of every kind are controlled, not only a dilation's and a stent's
        self.assertIsNone(claims.control_rule(OC.ACT, A.TARGET_PLACES, FactState.SUPPORTED, Landmark.RECTUM,
                                              Kind.BIOPSY).kinds)
        # the five session siblings: with them, every family a code of which can be READY has one
        self.assertEqual({key.value: value.value for key, value in claims.SESSION_SIBLINGS.items()
                          if key.value in ('office_em', 'motility', 'reflux', 'anorectal', 'feeding_tube')},
                         {'office_em': 'em_other', 'motility': 'reflux', 'reflux': 'motility', 'anorectal': 'motility',
                          'feeding_tube': 'egd'})
        self.assertEqual(set(claims.SESSION_SIBLINGS), READY_FAMILIES)

    def test_an_anorectal_sessions_control_is_false_of_anorectal_testing(self):
        # refute-2c-r1 problem 2: DECISIONS D196 gives anorectal the sibling motility, whose label "a motility or
        # manometry study" an anorectal manometry (91122) is too - a faithful pass 2 supported the control and the
        # session kind stayed unresolved. The motility label names its family's studies and sets anorectal testing
        # apart
        data = manometry_answer('anorectal')
        claim_set = build(MANOMETRY, data)
        (kind,) = appraised(claim_set, A.KIND, 'X1')
        self.assertEqual(sentence_of(claim_set, kind.claim), 'Session X1 is an anorectal test.')
        self.assertEqual(sentence_of(claim_set, kind.control),
                         'Session X1 is a motility or manometry study of the esophagus, the stomach, the small '
                         'bowel or the colon, not an anorectal test.')
        self.assertIs(claims.SESSION_SIBLINGS[SessionKind.ANORECTAL], SessionKind.MOTILITY)
        self.assertTrue(claims.LABELS[SessionKind.MOTILITY].endswith('not ' + claims.LABELS[SessionKind.ANORECTAL]))
        # the same sentence is a motility session's real claim: nothing about the control's wording marks it
        motility = build(MANOMETRY, manometry_answer('motility'))
        (kind,) = appraised(motility, A.KIND, 'X1')
        self.assertEqual(sentence_of(motility, kind.claim),
                         'Session X1 is a motility or manometry study of the esophagus, the stomach, the small '
                         'bowel or the colon, not an anorectal test.')

    def test_session_through_names_another_anatomy_entry_when_one_exists(self):
        data = note_answer()
        data['anatomy'] = [{'id': 'Y1', 'type': fact('stoma', src(['S5'], 'colonoscope')), 'organ': [], 'subtype': [],
                            'joins': []}]
        data['sessions'][0]['through'] = [fact('Y1', src(['S5'], 'colonoscope'))]
        claim_set = build(NOTE, data)
        (through,) = appraised(claim_set, A.THROUGH, 'X1')
        self.assertEqual(sentence_of(claim_set, through.claim), 'In session X1 the scope passed through anatomy Y1.')
        self.assertIsNone(through.control)  # one anatomy entry: UNCONTROLLED (D196)
        data['anatomy'].append({'id': 'Y2', 'type': fact('ileal_pouch', src(['S6'], 'polyp')), 'organ': [],
                                'subtype': [], 'joins': []})
        claim_set = build(NOTE, data)
        (through,) = appraised(claim_set, A.THROUGH, 'X1')
        self.assertEqual(sentence_of(claim_set, through.control), 'In session X1 the scope passed through anatomy Y2.')

    def test_uncontrolled_is_closed_and_gives_each_reason(self):
        self.assertEqual({(entry.object_class.value, entry.attribute.value, entry.why.value) for entry in
                          claims.UNCONTROLLED}, {
            ('act', 'date', 'literal_checked'), ('encounter', 'date_of_service', 'no_single_contrary'),
            ('act', 'part_of', 'only_holds'), ('act', 'part_relation', 'only_holds'), ('act', 'purpose', 'only_holds'),
            ('statement', 'scope.covers', 'only_unresolves'), ('lesion', 'same_as', 'only_joins'),
            # DECISIONS D196
            ('session', 'through', 'one_anatomy_entry'), ('session', 'part_of_session', 'only_holds')})
        purpose = claims.uncontrolled(OC.ACT, A.PURPOSE, claims.Purpose.PROPHYLAXIS)
        self.assertIsNotNone(purpose)
        self.assertIsNone(claims.uncontrolled(OC.ACT, A.PURPOSE, claims.Purpose.HEMOSTASIS))
        # an uncontrolled attribute and a controlled value are never both: purpose's hemostasis is controlled. The one
        # entry conditioned on the document instead (D196: session.through with one anatomy entry) has its rule for
        # the documents with another entry
        self.assertIsNotNone(claims.control_rule(OC.ACT, A.PURPOSE, FactState.SUPPORTED, claims.Purpose.HEMOSTASIS))
        for entry in claims.UNCONTROLLED:
            for rule in claims.CONTROLS:
                if (rule.object_class, rule.attribute) == (entry.object_class, entry.attribute):
                    if entry.why is claims.Why.ONE_ANATOMY_ENTRY:
                        self.assertIs(rule.contrary, claims.Contrary.ANOTHER_ANATOMY)
                        continue
                    self.assertTrue(entry.values is not None and rule.values is not None
                                    and not entry.values & rule.values)

    def test_kind_siblings_cover_every_codable_kind_a_ready_path_reads(self):
        # 3.2.3's list and DECISIONS D194's three, each chosen outside the kind
        self.assertEqual(len(claims.KIND_SIBLINGS), 38)
        self.assertEqual(claims.KIND_SIBLINGS[Kind.SPHINCTEROTOMY], Kind.DILATION)  # SC-C's case
        self.assertEqual({kind.value: claims.KIND_SIBLINGS[kind].value for kind in (
            Kind.REMOVAL, Kind.INTERVENTION, Kind.EM_PROLONGED)},
            {'removal': 'biopsy', 'intervention': 'examination', 'em_prolonged': 'em_visit'})
        # the examination and the visit are decided through session.kind and the visit facts (3.2.3); moderate sedation
        # and other get none (D194): engine/requirements reads their kind on the hold path only
        self.assertEqual(rq.CODABLE_KINDS - set(claims.KIND_SIBLINGS), {Kind.EXAMINATION, Kind.EM_VISIT,
                                                                        Kind.MODERATE_SEDATION, Kind.OTHER})
        kinds_on_a_path = {kind for object_class, attribute, kind in deciding_reads() if attribute is A.KIND
                           and object_class in (OC.ACT, OC.STATEMENT)}
        self.assertFalse(kinds_on_a_path & {Kind.MODERATE_SEDATION, Kind.OTHER})
        self.assertLessEqual(kinds_on_a_path - {Kind.EXAMINATION, Kind.EM_VISIT}, set(claims.KIND_SIBLINGS))
        for kind, sibling in claims.KIND_SIBLINGS.items():
            self.assertIsNot(kind, sibling)
        for kind in (Kind.REMOVAL, Kind.INTERVENTION, Kind.EM_PROLONGED):  # outside the umbrella: a faithful reading
            sibling = claims.KIND_SIBLINGS[kind]  # rejects it
            self.assertFalse(catalogue.covers(kind, sibling) or catalogue.covers(sibling, kind), kind)

    def test_contrast_places_are_ordered_candidates_none_compatible_with_its_place(self):
        # DECISIONS D196: an ordered list per place; 3.2.3's three named pairs first
        for place, candidates in claims.CONTRAST_PLACES.items():
            with self.subTest(place=place.value):
                self.assertTrue(candidates)
                self.assertEqual(len(set(candidates)), len(candidates))
                self.assertFalse([candidate for candidate in candidates if anatomy.compatible(place, candidate)
                                  or candidate in anatomy.ALTERED | anatomy.UNPLACED])
                # each list ends with the fallback's places the key is compatible with none of (refute-2c-r1 problem 1)
                far = [candidate for candidate in claims.CONTRAST_FALLBACK if not anatomy.compatible(place, candidate)]
                self.assertLessEqual(set(far), set(candidates))
        self.assertEqual(claims.CONTRAST_PLACES[Landmark.ESOPHAGUS][0], Landmark.STOMACH)
        self.assertEqual(claims.CONTRAST_PLACES[Landmark.STOMACH][0], Landmark.DUODENUM)
        self.assertEqual(claims.CONTRAST_PLACES[Landmark.SIGMOID_COLON][0], Landmark.RECTUM)
        self.assertEqual(set(Landmark) - set(claims.CONTRAST_PLACES), anatomy.ALTERED | anatomy.UNPLACED)

    def test_each_control_of_the_note(self):
        claim_set = build(NOTE, note_answer())
        controls = {(item.key.object, item.key.attribute): sentence_of(claim_set, item.control)
                    for item in claim_set.appraised if item.control is not None}
        self.assertEqual(controls, {
            # a performed act's control is the statement-phrased form (DECISIONS D196)
            ('E1', A.STATUS): 'This statement says that examination as a whole was not done.',
            ('E1', A.DATE_RELATION): 'This act was done on a date before the date of service.',
            ('E1', A.PERFORMER): 'This act was done by a clinician other than the documenting clinician and their '
                                 'team.',
            ('E1', A.ENTRY): 'This act is told in the part of the document that begins at S5, written by nursing '
                             'staff.',
            ('E2', A.KIND): 'This act is an endoscopic mucosal resection.',
            ('E2', A.STATUS): 'This statement says that removal with a snare was not done.',
            ('E2', A.DATE_RELATION): 'This act was done on a date before the date of service.',
            ('E2', A.PERFORMER): 'This act was done by a clinician other than the documenting clinician and their '
                                 'team.',
            ('E2', A.ENTRY): 'This act is told in the part of the document that begins at S5, written by nursing '
                             'staff.',
            # the places of every kind a READY path reads (D196), the first candidate compatible with no place of E2
            ('E2', A.TARGET_PLACES): 'This act was done in the splenic flexure.',
            # the history's removal, codable since D194: its sibling is outside the umbrella
            ('E4', A.KIND): 'This act is a tissue sampling with forceps.',
            ('E4', A.STATUS): 'This statement says that removal by any method was not done.',
            ('E4', A.DATE_RELATION): 'This act was done on the date of service.',
            ('E4', A.ENTRY): 'This act is told in the part of the document that begins at S4, written by nursing '
                             'staff.',
            ('E3', A.KIND): 'This statement is about removals or samplings with hot forceps.',
            ('E3', A.STATUS): 'This statement says that tissue sampling with forceps was done.',
            ('E3', A.DATE_RELATION): 'This statement is about tissue samplings with forceps on a date before the date '
                                     'of service.',
            ('E3', A.TARGET_PLACES): 'This statement is about tissue samplings with forceps in the sigmoid colon.',
            ('X1', A.KIND): 'Session X1 is a flexible sigmoidoscopy.',
            ('X1', A.REACHED): 'In session X1 the endoscope did not reach the cecum.',
            ('L1', A.MULTIPLICITY): 'Lesion L1 is a group of lesions described only together.'})
        # each control cites exactly its claim's units, and is about its claim's card
        for item in claim_set.appraised:
            if item.control is not None:
                self.assertEqual(claim_set.claim(item.control).units, claim_set.claim(item.claim).units)
                self.assertEqual(claim_set.about[item.control], claim_set.about[item.claim])
        # one session, one lesion: no other session or lesion to assert, so those facts have no control here
        for attribute, subject in ((A.SESSION, 'E2'), (A.TARGET_LESION, 'E2')):
            (item,) = appraised(claim_set, attribute, subject)
            self.assertIsNone(item.control)
        self.assertEqual(claim_set.controls, {item.control for item in claim_set.appraised if item.control})

    def test_controls_naming_another_object(self):
        claim_set = build(RICH, rich_answer())
        by = {(item.key.object, item.key.attribute): item for item in claim_set.appraised}
        # another session; another lesion of the session; another positive act of the session; another person
        self.assertEqual(sentence_of(claim_set, by[('E5', A.SESSION)].control), 'This act was done during session X1.')
        self.assertEqual(sentence_of(claim_set, by[('E5', A.TARGET_LESION)].control), 'This act was done to lesion L2.')
        self.assertEqual(sentence_of(claim_set, by[('E7', A.PURPOSE)].control),
                         'This act was done for prevention of bleeding.')
        self.assertEqual(sentence_of(claim_set, by[('E9', A.PERFORMER_PERSON)].control),
                         'This act was done by the person named at S3.')
        # the dilations' places and devices (technique classes); the statement's breadth all_of_kind -> exceptive
        self.assertEqual(sentence_of(claim_set, by[('E2', A.TARGET_PLACES)].control),
                         'This act was done in the middle esophagus.')
        self.assertEqual(sentence_of(claim_set, by[('E2', A.TECHNIQUE_DEVICE)].control),
                         'The document states that a dilating balloon was not used for this act.')
        self.assertEqual(sentence_of(claim_set, by[('E8', A.SCOPE_BREADTH)].control),
                         'This statement denies only tissue samplings with forceps other than acts A6.')
        # a cause act_of_this_session can only bundle (3.2.3 controls any cause other than it), and cause_event only
        # holds: neither has a control
        self.assertIsNone(by[('E7', A.CAUSE)].control)
        self.assertIsNone(by[('E7', A.CAUSE_EVENT)].control)
        # any other cause: another positive act of the session, when one exists
        data = rich_answer()
        data['events'][6]['cause'] = [fact('pre_existing_lesion', src(['S13'], 'Bleeding'))]
        data['events'][6]['cause_event'] = []
        other = build(RICH, data)
        (cause,) = appraised(other, A.CAUSE, 'E7')
        # the first act of X2 in document order claimed performed: its examination, E4 (card A4)
        self.assertEqual(sentence_of(other, cause.control), 'The bleeding this act treated was caused by act A4.')
        self.assertEqual(other.objects['A4'], (F.EVENT, 'E4'))

    def test_conditional_controls_and_values_without_a_rule(self):
        # a device outside the technique classes: no control (3.2.3's row); a place of an act that is no dilation or
        # stent: controlled since DECISIONS D196, as every kind's places a READY path reads are
        claim_set = build(NOTE, note_answer())
        (device,) = appraised(claim_set, A.TECHNIQUE_DEVICE, 'E2')
        self.assertIsNone(device.control)
        (place,) = appraised(claim_set, A.TARGET_PLACES, 'E2')
        self.assertIsNotNone(place.control)
        # attempted and planned: the control asserts it was carried out
        data = note_answer()
        data['events'][1]['status'] = fact('planned', src(['S6'], 'was removed'))
        found = build(NOTE, data)
        (status,) = appraised(found, A.STATUS, 'E2')
        self.assertEqual(sentence_of(found, status.claim), 'This act is planned or recommended, not done.')
        self.assertEqual(sentence_of(found, status.control),
                         'This act was carried out (not only planned, attempted or denied).')


def manometry_answer(family):
    """MANOMETRY's answer: one session X1 of ``family`` (no examination) and the manometry act E1."""
    today = fact('on_date_of_service', src(['S2'], '', 'document_frame'))
    return answer(
        sections=[section('N0', src([], '', 'section'), occasion=[today]),
                  section('N1', src(['S4'], 'Procedure:', 'section'), occasion=[today],
                          performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))])],
        sessions=[session('X1', family, src(['S4'], 'Anorectal manometry'))],
        events=[event('E1', ['S4'], 'Anorectal manometry', 'was performed', 'manometry',
                      session=[fact('X1', src(['S4']))])])


def rich_answer():
    """RICH's answer: an upper endoscopy X1 (E1) with two balloon dilations (E2 distal esophagus, E3 stomach), a
    colonoscopy X2 (E4) with a hot-snare removal of L1 (E5), cold-forceps biopsies of L2 (E6), a clip treating the
    removal's bleeding (E7), a rectal biopsy denial with breadth all_of_kind (E8), and a nursing-note clip by the nurse
    (E9, performer other_clinician, person P2)."""
    docs = src(['S3'], '', 'document_frame')
    today = fact('on_date_of_service', src(['S2'], '', 'document_frame'))
    team = fact('documenting_team', docs)
    return answer(
        people=[{'id': 'P1', 'name': src(['S3'], 'Q. R. Vance'),
                 'role': fact('documenting_clinician', src(['S3'], 'Endoscopist'))},
                {'id': 'P2', 'name': src(['S4'], 'T. Ward'), 'role': fact('nurse', src(['S4'], 'RN'))}],
        sections=[section('N0', src([], '', 'section'), occasion=[today], performer=[team]),
                  section('N1', src(['S5'], 'Procedure 1:', 'section'), occasion=[today], performer=[team]),
                  section('N2', src(['S9'], 'Procedure 2:', 'section'), occasion=[today], performer=[team]),
                  section('N3', src(['S15'], 'Nursing note:', 'section'), owner='nursing',
                          owner_source=src(['S15'], 'Nursing note:', 'section'), occasion=[today])],
        sessions=[session('X1', 'egd', src(['S5'], 'Upper endoscopy'), fact('E1', src(['S6']))),
                  session('X2', 'colonoscopy', src(['S9'], 'Colonoscopy'), fact('E4', src(['S10'])))],
        lesions=[lesion('L1', ['S11'], 'A 4 mm polyp in the sigmoid colon'),
                 lesion('L2', ['S12'], 'a 6 mm polyp in the transverse colon')],
        events=[
            event('E1', ['S6'], 'gastroscope', 'was advanced', 'examination', session=[fact('X1', src(['S6']))]),
            event('E2', ['S7'], 'dilated', 'was dilated', 'dilation', session=[fact('X1', src(['S7']))],
                  target__places=[fact('distal_esophagus', src(['S7'], 'distal esophagus'))],
                  technique__device=[fact('balloon', src(['S7'], 'balloon'))]),
            event('E3', ['S8'], 'dilated', 'was dilated', 'dilation', session=[fact('X1', src(['S8']))],
                  target__places=[fact('stomach', src(['S8'], 'stomach'))],
                  technique__device=[fact('balloon', src(['S8'], 'balloon'))]),
            event('E4', ['S10'], 'colonoscope', 'was advanced', 'examination', session=[fact('X2', src(['S10']))]),
            event('E5', ['S11'], 'removed with a hot snare', 'was removed', 'snare', session=[fact('X2', src(['S11']))],
                  target__lesion=[fact('L1', src(['S11'], 'A 4 mm polyp'))],
                  target__places=[fact('sigmoid_colon', src(['S11'], 'sigmoid colon'))]),
            event('E6', ['S12'], 'Biopsies', 'were taken', 'biopsy', session=[fact('X2', src(['S12']))],
                  target__lesion=[fact('L2', src(['S12'], 'a 6 mm polyp'))],
                  target__places=[fact('transverse_colon', src(['S12'], 'transverse colon'))]),
            event('E7', ['S13'], 'clip', 'was treated', 'clip', session=[fact('X2', src(['S13']))],
                  purpose=[fact('hemostasis', src(['S13'], 'Bleeding'))],
                  cause=[fact('act_of_this_session', src(['S13'], 'from the polypectomy site'))],
                  cause_event=[fact('E5', src(['S13'], 'polypectomy site'))]),
            event('E8', ['S14'], 'biopsies', 'No biopsies were taken', 'biopsy',
                  neg('performed', src(['S14'], 'No biopsies were taken')), session=[fact('X2', src(['S14']))],
                  scope__breadth=[fact('all_of_kind', src(['S14'], 'No biopsies'))]),
            event('E9', ['S15'], 'clip', 'was placed', 'clip', session=[fact('X2', src(['S15']))],
                  performer=[fact('other_clinician', src(['S15'], 'by the nurse'))],
                  performer_person=[fact('P2', src(['S15'], 'the nurse'))])])


# --- contrasts, and no control a real claim (DECISIONS D196; the arbiter's 2c#2, 2c#3 and 2c#7) ----------------------


def segment_answer(segment):
    """SEGMENT's answer: a colonoscopy session X1 (E1 its examination) and a biopsy denial (E2) of breadth segment."""
    return answer(
        sections=[section('N0', src([], '', 'section'), occasion=[fact('on_date_of_service', src(['S2'], '',
                                                                                                  'document_frame'))]),
                  section('N1', src(['S4'], 'Findings:', 'section'),
                          occasion=[fact('on_date_of_service', src(['S2'], '', 'document_frame'))],
                          performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))])],
        sessions=[session('X1', 'colonoscopy', src(['S1'], 'COLONOSCOPY', 'document_frame'), fact('E1', src(['S4'])),
                          reached=[fact('cecum', src(['S4'], 'advanced to the cecum'))])],
        events=[event('E1', ['S4'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S4']))]),
                event('E2', ['S5'], 'biopsies', 'No biopsies were taken', 'biopsy',
                      neg('performed', src(['S5'], 'No biopsies were taken')), session=[fact('X1', src(['S5']))],
                      scope__breadth=[fact('segment', src(['S5'], 'from the descending colon to the rectum'))],
                      scope__segment=list(segment))])


def duodenal_answer(segment):
    """DUODENAL's answer: an upper endoscopy X1 (E1 its examination) and a biopsy denial (E2) of breadth segment."""
    today = fact('on_date_of_service', src(['S2'], '', 'document_frame'))
    return answer(
        sections=[section('N0', src([], '', 'section'), occasion=[today]),
                  section('N1', src(['S4'], 'Findings:', 'section'), occasion=[today],
                          performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))])],
        sessions=[session('X1', 'egd', src(['S1'], 'UPPER ENDOSCOPY', 'document_frame'), fact('E1', src(['S4'])),
                          reached=[fact('fourth_portion_duodenum', src(['S4'], 'fourth portion of the duodenum'))])],
        events=[event('E1', ['S4'], 'gastroscope', 'was advanced', 'examination', session=[fact('X1', src(['S4']))]),
                event('E2', ['S5'], 'biopsies', 'No biopsies were taken', 'biopsy',
                      neg('performed', src(['S5'], 'No biopsies were taken')), session=[fact('X1', src(['S5']))],
                      scope__breadth=[fact('segment', src(['S5'], 'from the duodenal bulb to the third portion'))],
                      scope__segment=list(segment))])


def wide_answer(biopsy_places, dilation_places):
    """WIDE's answer: a colonoscopy X1 (E1 its examination), random biopsies (E2) and a balloon dilation (E3), each in
    the places given."""
    today = fact('on_date_of_service', src(['S2'], '', 'document_frame'))
    return answer(
        sections=[section('N0', src([], '', 'section'), occasion=[today]),
                  section('N1', src(['S4'], 'Findings:', 'section'), occasion=[today],
                          performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))])],
        sessions=[session('X1', 'colonoscopy', src(['S1'], 'COLONOSCOPY', 'document_frame'), fact('E1', src(['S4'])))],
        events=[event('E1', ['S4'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S4']))]),
                event('E2', ['S5'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S5']))],
                      target__places=[fact(place, src(['S5'], 'Random biopsies')) for place in biopsy_places]),
                event('E3', ['S6'], 'dilated', 'were dilated', 'dilation', session=[fact('X1', src(['S6']))],
                      target__places=[fact(place, src(['S6'], 'The narrowed colon')) for place in dilation_places],
                      technique__device=[fact('balloon', src(['S6'], 'balloon'))])])


def controls_of(claim_set, subject, attribute):
    """The control claims of ``subject``'s ``attribute`` facts."""
    return {claim_set.claim(item.control) for item in appraised(claim_set, attribute, subject) if item.control}


class ContrastTests(SimpleTestCase):
    def test_a_segment_control_is_never_inside_its_range(self):
        # 2c#2: the first candidate compatible with nothing of the segment's whole range - its two places and every
        # place LANDMARKS2's order puts between them (a container of some of them is compatible, so never chosen)
        expected = {('descending_colon', 'rectum'): 'splenic flexure', ('sigmoid_colon', 'rectum'): 'descending colon',
                    ('ascending_colon', 'sigmoid_colon'): 'cecum', ('cecum', 'rectum'): 'terminal ileum',
                    ('rectum', 'descending_colon'): 'anal canal'}
        for segment, place in expected.items():
            with self.subTest(segment=segment):
                claim_set = build(SEGMENT, segment_answer(segment))
                (control,) = controls_of(claim_set, 'E2', A.SCOPE_SEGMENT)
                self.assertEqual(sentence_of(claim_set, control.id),
                                 f'This statement is about tissue samplings with forceps in the {place}.')
                ends = [Landmark(value) for value in segment]
                inside = claims.segment_range(*ends)
                self.assertFalse([value for value in inside if anatomy.compatible(Landmark(control.value), value)])
        self.assertEqual([place.value for place in claims.segment_range(Landmark.DESCENDING_COLON, Landmark.RECTUM)],
                         ['descending_colon', 'sigmoid_colon', 'rectosigmoid', 'rectum'])
        self.assertEqual(claims.segment_range(Landmark.RECTUM, Landmark.DESCENDING_COLON),
                         claims.segment_range(Landmark.DESCENDING_COLON, Landmark.RECTUM))

    def test_a_duodenal_segment_keeps_the_second_portion_inside(self):
        # refute-2c-r1 problem 3: the second portion of the duodenum holds the ampulla, which LANDMARKS2 lists after the
        # fourth portion; a range keeping only the places that hold nothing left the second portion out, and its
        # control "in the duodenum (its second portion)" was inside the segment, true by construction
        expected = {('duodenal_bulb', 'third_portion_duodenum'): 'antrum of the stomach',
                    ('duodenal_bulb', 'fourth_portion_duodenum'): 'antrum of the stomach',
                    ('third_portion_duodenum', 'duodenal_bulb'): 'duodenum (its fourth portion)',
                    ('third_portion_duodenum', 'esophagus'): 'duodenum (its fourth portion)'}
        for segment, place in expected.items():
            with self.subTest(segment=segment):
                claim_set = build(DUODENAL, duodenal_answer(segment))
                (control,) = controls_of(claim_set, 'E2', A.SCOPE_SEGMENT)
                self.assertEqual(sentence_of(claim_set, control.id),
                                 f'This statement is about tissue samplings with forceps in the {place}.')
        self.assertIn(Landmark.SECOND_PORTION_DUODENUM,
                      claims.segment_range(Landmark.DUODENAL_BULB, Landmark.THIRD_PORTION_DUODENUM))

    def test_no_segment_control_lies_between_its_ends_in_the_tract(self):
        # an oracle written apart from the implementation: the luminal tract's places in the order the tract runs, a
        # place inside another at that place's position (the ampulla in the second portion of the duodenum; the
        # opening of the appendix and the ileocecal valve side by side in the cecum, so a segment reaching one of them
        # reaches the cecum and both). For every segment between two of them, the control's place is compatible with
        # none of the places between its ends
        tract = [tuple(Landmark(value) for value in group) for group in (
            ('proximal_esophagus',), ('mid_esophagus',), ('distal_esophagus',), ('gastroesophageal_junction',),
            ('gastric_cardia',), ('gastric_fundus',), ('gastric_body',), ('gastric_antrum',), ('pylorus',),
            ('duodenal_bulb',), ('second_portion_duodenum', 'ampulla'), ('third_portion_duodenum',),
            ('fourth_portion_duodenum',), ('jejunum',), ('terminal_ileum',),
            ('cecum', 'appendiceal_orifice', 'ileocecal_valve'), ('ascending_colon',), ('hepatic_flexure',),
            ('transverse_colon',), ('splenic_flexure',), ('descending_colon',), ('sigmoid_colon',), ('rectosigmoid',),
            ('rectum',), ('anal_canal',))]
        position = {place: index for index, group in enumerate(tract) for place in group}
        checked = 0
        for first, last in itertools.product(position, repeat=2):
            one, other = sorted((position[first], position[last]))
            between = [place for group in tract[one:other + 1] for place in group]
            found = claims.contrast(claims.contrast_candidates([first, last]), claims.segment_range(first, last))
            with self.subTest(segment=(first.value, last.value)):
                self.assertIsNotNone(found)
                self.assertFalse([place for place in between if anatomy.compatible(found, place)], found)
            checked += 1
        self.assertEqual(checked, 28 * 28)

    def test_a_contrast_is_never_one_of_the_objects_own_places(self):
        # 2c#3: a dilation filed in the esophagus and the stomach; a denial of biopsies from the sigmoid colon and the
        # rectum. Each place's control is a place compatible with neither, never the other place's own claim
        data = rich_answer()
        data['events'][1]['target']['places'] = [fact('esophagus', src(['S7'], 'distal esophagus')),
                                                  fact('stomach', src(['S7'], 'distal esophagus'))]
        data['events'][7]['target']['places'] = [fact('sigmoid_colon', src(['S14'], 'No biopsies')),
                                                  fact('rectum', src(['S14'], 'No biopsies'))]
        claim_set = build(RICH, data)
        self.assertEqual({sentence_of(claim_set, claim.id) for claim in controls_of(claim_set, 'E2', A.TARGET_PLACES)},
                         {'This act was done in the duodenum.'})
        self.assertEqual({sentence_of(claim_set, claim.id) for claim in controls_of(claim_set, 'E8', A.TARGET_PLACES)},
                         {'This statement is about tissue samplings with forceps in the descending colon.',
                          'This statement is about tissue samplings with forceps in the anal canal.'})
        real = {item.claim for item in claim_set.appraised}
        self.assertEqual(real & claim_set.controls, set())
        self.assertEqual(real & {pair.claim for pair in claim_set.pair_controls}, set())

    def test_every_place_an_object_names_is_controlled_or_not_claimed(self):
        # refute-2c-r1 problem 1: a place whose nearest candidates the object's other places use up - random biopsies of
        # the right, transverse and left colon and the rectum; a dilation of the colon, the rectum and the anal canal -
        # had no control, so one "supports" established it. Every list now ends with far places of six regions
        claim_set = build(WIDE, wide_answer(('right_colon', 'transverse_colon', 'left_colon', 'rectum'),
                                            ('colon', 'rectum', 'anal_canal')))
        for subject, count in (('E2', 4), ('E3', 3)):
            items = appraised(claim_set, A.TARGET_PLACES, subject)
            self.assertEqual(len(items), count)
            own = [Landmark(item.value) for item in items]
            for item in items:
                with self.subTest(subject=subject, place=item.value):
                    self.assertIsNotNone(item.control)
                    contrast = Landmark(claim_set.claim(item.control).value)
                    self.assertFalse([place for place in own if anatomy.compatible(contrast, place)], contrast)
        (transverse,) = [item for item in appraised(claim_set, A.TARGET_PLACES, 'E2')
                         if item.value == 'transverse_colon']
        self.assertEqual(sentence_of(claim_set, transverse.control), 'This act was done in the stomach.')
        # an act whose places reach all six regions uses its lists up: such a place is not claimed (fail-closed), and
        # none is ever claimed with no control
        everywhere = ('colon', 'rectum', 'anal_canal', 'stomach', 'esophagus', 'small_bowel', 'liver')
        claim_set = build(WIDE, wide_answer(('transverse_colon',), everywhere))
        claimed = appraised(claim_set, A.TARGET_PLACES, 'E3')
        self.assertFalse([item for item in claimed if item.control is None])
        not_claimed = [item.why for item in claim_set.unclaimed
                       if (item.key.object, item.key.attribute) == ('E3', A.TARGET_PLACES)]
        self.assertEqual(set(not_claimed), {claims.Unclaimable.CONTROL})
        self.assertEqual(len(claimed) + len(not_claimed), len(everywhere))
        self.assertEqual([item.value for item in claimed], ['liver'])  # the gallbladder is compatible with none

    def test_no_set_of_up_to_three_places_uses_up_a_list(self):
        # the fallback's six regions: a place's list runs out only when the object's places reach each of them, which
        # takes six places at least (no place is compatible with two of them)
        placed = list(claims.CONTRAST_PLACES)
        checked = 0
        for size in (1, 2, 3):
            for chosen in itertools.combinations(placed, size):
                for place in chosen:
                    found = claims.contrast(claims.CONTRAST_PLACES[place], chosen)
                    if found is None or any(anatomy.compatible(found, own) for own in chosen):
                        self.fail(f'{[item.value for item in chosen]}: {place.value} -> {found}')
                    checked += 1
        self.assertEqual(checked, 46 + 2 * 1035 + 3 * 15180)
        for far in claims.CONTRAST_FALLBACK:
            self.assertEqual([other for other in claims.CONTRAST_FALLBACK if other is not far
                              and anatomy.compatible(far, other)], [])
            self.assertEqual([place for place in Landmark if anatomy.compatible(place, far)
                              and [other for other in claims.CONTRAST_FALLBACK if other is not far
                                   and anatomy.compatible(place, other)]], [])

    def test_no_control_asserts_what_a_claim_about_the_same_object_asserts(self):
        # 2c#3, as the build asserts it: where pass 1 gives a value and its contrary - here lesion L1 both distinct from
        # L2 and the same as L2 - the one fact's control would be the other's claim, so neither is claimed
        data = note_answer()
        data['lesions'].append(lesion('L2', ['S4'], 'one polyp'))
        data['lesions'][0]['distinct_from'] = [fact('L2', src(['S6'], 'A 5 mm polyp'))]
        data['lesions'][0]['same_as'] = [fact('L2', src(['S6'], 'A 5 mm polyp'))]
        claim_set = build(NOTE, data)
        self.assertEqual(appraised(claim_set, A.DISTINCT_FROM, 'L1') + appraised(claim_set, A.SAME_AS, 'L1'), [])
        self.assertEqual({(item.key.attribute, item.why) for item in claim_set.unclaimed if item.key.object == 'L1'
                          and item.key.attribute is not A.PLACES},
                         {(A.DISTINCT_FROM, claims.Unclaimable.CONTRARY), (A.SAME_AS, claims.Unclaimable.CONTRARY)})
        # alone, each is claimed (same_as UNCONTROLLED; distinct_from with the same-lesion form)
        data['lesions'][0]['same_as'] = []
        (distinct,) = appraised(build(NOTE, data), A.DISTINCT_FROM, 'L1')
        self.assertIsNotNone(distinct.control)
        # and the build refuses a set where one would remain: the check is the build's own
        data['lesions'][0]['same_as'] = [fact('L2', src(['S6'], 'A 5 mm polyp'))]
        with mock.patch.object(claims._Builder, 'no_control_is_a_claim', lambda self: None):
            with self.assertRaisesMessage(RuntimeError, 'A control asserts what a real claim'):
                build(NOTE, data)

    def test_a_shared_claim_goes_with_a_fact_that_is_not_claimed(self):
        # an exceptive denial whose excepted act it also covers (pass 1 gives both): the excepted act's control is the
        # covers claim, so neither is claimed - and the breadth, whose exceptive sentence names the excepted act, goes
        # with them (a sentence never names a fact that is not claimed)
        data = rich_answer()
        data['events'][7]['scope']['breadth'] = [fact('exceptive', src(['S14'], 'No biopsies'))]
        data['events'][7]['scope']['excepts'] = ['E6']
        data['events'][7]['scope']['covers'] = ['E6']
        claim_set = build(RICH, data)
        self.assertEqual({(item.key.attribute, item.why) for item in claim_set.unclaimed if item.key.object == 'E8'},
                         {(A.SCOPE_EXCEPTS, claims.Unclaimable.CONTRARY), (A.SCOPE_COVERS, claims.Unclaimable.CONTRARY),
                          (A.SCOPE_BREADTH, claims.Unclaimable.PARTNER)})
        self.assertFalse([text for text in sentences(claim_set) if 'other than acts' in text or 'applies to' in text])
        self.assertEqual({item.claim for item in claim_set.appraised} & claim_set.controls, set())
        # without the covered act, the exceptive breadth is claimed, its excepted act sharing its sentence
        data['events'][7]['scope']['covers'] = []
        claim_set = build(RICH, data)
        (breadth,) = appraised(claim_set, A.SCOPE_BREADTH, 'E8')
        (excepted,) = appraised(claim_set, A.SCOPE_EXCEPTS, 'E8')
        self.assertEqual(breadth.claim, excepted.claim)
        self.assertEqual(sentence_of(claim_set, breadth.claim),
                         'This statement denies only tissue samplings with forceps other than acts A6.')
        # refute-2c-r1 problem 7: with no session the exceptive breadth's control (the all_of_kind form names it) cannot
        # be written, so the breadth is not claimed - and its excepted act, whose claim is the breadth's sentence, goes
        # with it: the exceptive sentence is never claimed while the breadth is not
        data['events'][7]['session'] = []
        claim_set = build(RICH, data)
        self.assertEqual({(item.key.attribute, item.why) for item in claim_set.unclaimed if item.key.object == 'E8'},
                         {(A.SCOPE_BREADTH, claims.Unclaimable.CONTROL), (A.SCOPE_EXCEPTS, claims.Unclaimable.PARTNER)})
        self.assertFalse([text for text in sentences(claim_set) if 'other than acts' in text])
        self.assertTrue(appraised(claim_set, A.KIND, 'E8'))  # its other facts stand

    def test_another_object_is_never_one_of_the_objects_own(self):
        # a statement listing lesions L1 and L2: neither target's control names the other, its own
        data = rich_answer()
        data['events'][7]['scope']['breadth'] = [fact('listed_targets', src(['S14'], 'No biopsies'))]
        data['events'][7]['scope']['targets'] = ['L1', 'L2']
        claim_set = build(RICH, data)
        targets = [item for item in claim_set.appraised if item.key.object == 'E8'
                   and item.key.attribute is A.SCOPE_TARGETS]
        self.assertEqual(len(targets), 2)
        self.assertTrue(all(item.control is None for item in targets))  # no third lesion in the document
        self.assertEqual({item.claim for item in claim_set.appraised} & claim_set.controls, set())

    def test_the_all_of_kind_control_lists_only_claimable_acts(self):
        # 2c#7: E8 denies every biopsy of X2; E6 is a reported biopsy. With E6's status or kind doubted the control
        # cannot name it, and no other reported biopsy is claimable: E8's breadth is not claimed (fail-closed)
        for doubt in ({'about': 'status', 'objects': ['E6'], 'units': ['S12'], 'basis': 'stated',
                       'readings': ['performed', 'planned']},
                      {'about': 'kind', 'objects': ['E6'], 'units': ['S12'], 'basis': 'unclear',
                       'readings': ['biopsy', 'hot_biopsy']}):
            with self.subTest(doubt=doubt['about']):
                data = rich_answer()
                data['doubts'] = [doubt]
                claim_set = build(RICH, data)
                self.assertFalse([text for text in sentences(claim_set) if 'acts A6' in text])
                self.assertEqual(appraised(claim_set, A.SCOPE_BREADTH, 'E8'), [])
                self.assertIn((A.SCOPE_BREADTH, claims.Unclaimable.CONTROL),
                              {(item.key.attribute, item.why) for item in claim_set.unclaimed
                               if item.key.object == 'E8'})
        # refute-2c-r1 problem 6: E6's status or kind contradicted rather than doubted - pass 1 still reports a biopsy
        # it may have performed, so the control exists and cannot name it: the breadth is not claimed either, never
        # claimed uncontrolled
        for attribute, options in (('status', ('performed', 'planned')), ('kind', ('biopsy', 'hot_biopsy'))):
            with self.subTest(contradicted=attribute):
                data = rich_answer()
                data['events'][5][attribute] = fact('', src(['S12'], 'Biopsies'), src(['S12'], 'were taken'),
                                                    state='contradicted', options=[
                                                        {'value': value, 'sources': [src(['S12'])]}
                                                        for value in options])
                claim_set = build(RICH, data)
                self.assertFalse([text for text in sentences(claim_set) if 'acts A6' in text])
                self.assertEqual(appraised(claim_set, A.SCOPE_BREADTH, 'E8'), [])
                self.assertIn((A.SCOPE_BREADTH, claims.Unclaimable.CONTROL),
                              {(item.key.attribute, item.why) for item in claim_set.unclaimed
                               if item.key.object == 'E8'})
        # a status pass 1 negates is no reported act: E6 is then a denial, and the breadth has no contrary
        data = rich_answer()
        data['events'][5]['status'] = neg('performed', src(['S12'], 'were taken'))
        (breadth,) = appraised(build(RICH, data), A.SCOPE_BREADTH, 'E8')
        self.assertIsNone(breadth.control)
        # with no reported act of the kind there is no contrary at all: the claim alone decides (3.2.3)
        data = rich_answer()
        data['events'] = [item for item in data['events'] if item['id'] != 'E6']
        (breadth,) = appraised(build(RICH, data), A.SCOPE_BREADTH, 'E8')
        self.assertIsNone(breadth.control)


# --- pair controls (3.2.3 [R:SC-B]) ------------------------------------------------------------------------------------


class PairControlTests(SimpleTestCase):
    def short_list(self):
        """SC-B's case: biopsies "from the transverse colon and the rectum" filed with the transverse colon only,
        beside "No biopsies were taken from the rectum." (single target)."""
        data = rich_answer()
        data['events'][7]['scope']['breadth'] = [fact('single_target', src(['S14'], 'from the rectum'))]
        data['events'][7]['target']['places'] = [fact('rectum', src(['S14'], 'rectum'))]
        return data

    def test_both_directions_and_the_short_list_is_asked(self):
        claim_set = build(RICH, self.short_list())
        pairs = {(pair.subject[1], pair.other[1], pair.attribute, pair.value): sentence_of(claim_set, pair.claim)
                 for pair in claim_set.pair_controls}
        # the act is asked about the statement's place, the statement about the act's place: the omitted rectum is
        # exactly what the pair control asks the act
        self.assertEqual(pairs[('E6', 'E8', A.TARGET_PLACES, 'rectum')], 'This act was done in the rectum.')
        self.assertEqual(pairs[('E8', 'E6', A.TARGET_PLACES, 'transverse_colon')],
                         'This statement is about tissue samplings with forceps in the transverse colon.')
        self.assertTrue(all(pair.claim in claim_set.controls for pair in claim_set.pair_controls))
        # a removal with a snare is no biopsy, sibling or cover: no pair of the statement with E5 (E5 and E6 are
        # paired by bundling identity, D196); none with the clips
        self.assertFalse([pair for pair in claim_set.pair_controls if 'E8' in (pair.subject[1], pair.other[1])
                          and 'E5' in (pair.subject[1], pair.other[1])])
        self.assertFalse([pair for pair in claim_set.pair_controls if {'E7', 'E9'} & {pair.subject[1],
                                                                                   pair.other[1]}])

    def test_lesions_differing_are_asked_both_ways(self):
        data = self.short_list()
        data['events'][7]['target']['lesion'] = [fact('L1', src(['S14'], 'biopsies'))]
        claim_set = build(RICH, data)
        pairs = {(pair.subject[1], pair.attribute, pair.value) for pair in claim_set.pair_controls}
        self.assertLessEqual({('E6', A.TARGET_LESION, 'L1'), ('E8', A.TARGET_LESION, 'L2')}, pairs)

    def test_every_pair_of_acts_a_place_identity_rule_reads_in_one_session(self):
        # D118's one stricture (two dilations) and bundling identity by place (DECISIONS D196: a biopsy beside a snare
        # removal, the kinds read from the requirement table), both directions, places and lesions
        claim_set = build(RICH, rich_answer())
        pairs = {(pair.subject[1], pair.other[1], pair.value): sentence_of(claim_set, pair.claim)
                 for pair in claim_set.pair_controls}
        self.assertEqual(pairs, {('E2', 'E3', 'stomach'): 'This act was done in the stomach.',
                                 ('E3', 'E2', 'distal_esophagus'): 'This act was done in the distal esophagus.',
                                 ('E5', 'E6', 'transverse_colon'): 'This act was done in the transverse colon.',
                                 ('E6', 'E5', 'sigmoid_colon'): 'This act was done in the sigmoid colon.',
                                 ('E5', 'E6', 'L2'): 'This act was done to lesion L2.',
                                 ('E6', 'E5', 'L1'): 'This act was done to lesion L1.'})
        self.assertEqual(claims.STRICTURE_PAIR_KINDS, {Kind.DILATION})
        self.assertEqual(claims.BUNDLING_PAIR_KINDS, (
            {Kind.INJECTION, Kind.SNARE, Kind.HOT_BIOPSY, Kind.BIOPSY, Kind.FNA},
            {Kind.SNARE, Kind.EMR, Kind.HOT_BIOPSY, Kind.ESD, Kind.DRAINAGE}))
        data = rich_answer()  # dilations in sessions established apart: no pair between them
        data['events'][2]['session'] = [fact('X2', src(['S8']))]
        self.assertFalse([pair for pair in build(RICH, data).pair_controls if {pair.subject[1], pair.other[1]}
                          == {'E2', 'E3'}])

    def test_no_pair_for_a_broad_statement_or_a_place_both_share(self):
        self.assertFalse([pair for pair in build(RICH, rich_answer()).pair_controls if 'E8' in (pair.subject[1],
                                                                                              pair.other[1])])
        data = self.short_list()
        data['events'][5]['target']['places'].append(fact('rectum', src(['S12'], 'transverse colon')))
        claim_set = build(RICH, data)
        self.assertFalse([pair for pair in claim_set.pair_controls if pair.attribute is A.TARGET_PLACES
                          and pair.subject[1] == 'E6' and pair.other[1] == 'E8'])

    def test_a_listed_target_that_fails_leaves_the_others_claimed_and_the_set_built(self):
        # refute-2c-r1 problem 4: a denial listing L1 and a second member that fails (an event's id, a lesion no entry
        # declares, a member the caller's checks failed), beside a snare done to L1. Its member L1 is claimed on its
        # own, but its lesions were read all or nothing, so the pair control asked the denial about L1 - that very
        # claim - and the build raised: no claim set at all for one failed member
        failed = {FactKey(F.EVENT, 'E3', A.SCOPE_TARGETS, 1): (Reason.REFERENCE_INVALID,)}
        for name, targets, findings in (('an event id', ['L1', 'E2'], None), ('undeclared', ['L1', 'L9'], None),
                                        ('a failed member', ['L1', 'L2'], failed)):
            with self.subTest(member=name):
                claim_set = build(LISTED, listed_answer(targets), findings)
                (member,) = appraised(claim_set, A.SCOPE_TARGETS, 'E3')
                self.assertEqual((member.key.index, member.value), (0, 'L1'))
                pairs = {(pair.subject[1], pair.other[1], pair.attribute, pair.value)
                         for pair in claim_set.pair_controls}
                self.assertNotIn(('E3', 'E2', A.TARGET_LESION, 'L1'), pairs)
                self.assertIn(('E2', 'E3', A.TARGET_LESION, 'L2'), pairs)  # the act asked about the denial's other
                self.assertEqual({item.claim for item in claim_set.appraised} & claim_set.controls, set())

    def test_the_selection_admits_a_compatible_and_a_sibling_kind_never_an_unrelated_one(self):
        # the arbiter's 2c#8: a denial of rectal biopsies beside a forceps biopsy (the same kind), a hot-forceps
        # removal (KIND_SIBLINGS' sibling of a biopsy) and a cold-snare removal (neither) of its session
        claim_set = build(PAIRS, pairs_answer())
        with_statement = {(pair.subject[1], pair.other[1], pair.value) for pair in claim_set.pair_controls
                          if 'E5' in (pair.subject[1], pair.other[1])}
        self.assertEqual(with_statement, {('E5', 'E2', 'ascending_colon'), ('E2', 'E5', 'rectum'),
                                          ('E5', 'E3', 'transverse_colon'), ('E3', 'E5', 'rectum')})
        # the acts among themselves: bundling identity by place (a biopsy or a hot-forceps act beside a removal)
        among = {frozenset({pair.subject[1], pair.other[1]}) for pair in claim_set.pair_controls
                 if 'E5' not in (pair.subject[1], pair.other[1])}
        self.assertEqual(among, {frozenset({'E2', 'E3'}), frozenset({'E2', 'E4'}), frozenset({'E3', 'E4'})})
        # the selection is in CONTROLS_SHA256's document, kind pair by kind pair, so a changed rule moves the pin
        kinds = claims.controls_document()['pair_controls']['pair_kinds']
        self.assertIn(['biopsy', 'biopsy'], kinds)
        self.assertIn(['biopsy', 'hot_biopsy'], kinds)
        self.assertIn(['biopsy', 'fna'], kinds)  # an act whose sibling is the statement's kind
        self.assertIn(['removal', 'snare'], kinds)  # an umbrella and its member
        self.assertNotIn(['biopsy', 'snare'], kinds)


def listed_answer(targets):
    """LISTED's answer: a colonoscopy X1 (E1 its examination), a cold-snare removal of L1 (E2), and a denial of snare
    removals (E3) of breadth listed_targets, listing ``targets``, its own target lesion L2."""
    today = fact('on_date_of_service', src(['S2'], '', 'document_frame'))
    return answer(
        sections=[section('N0', src([], '', 'section'), occasion=[today]),
                  section('N1', src(['S4'], 'Findings:', 'section'), occasion=[today],
                          performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))])],
        sessions=[session('X1', 'colonoscopy', src(['S1'], 'COLONOSCOPY', 'document_frame'), fact('E1', src(['S4'])))],
        lesions=[lesion('L1', ['S5'], 'A 5 mm polyp'), lesion('L2', ['S6'], 'A 3 mm polyp')],
        events=[event('E1', ['S4'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S4']))]),
                event('E2', ['S5'], 'removed with a cold snare', 'was removed', 'snare',
                      session=[fact('X1', src(['S5']))], target__lesion=[fact('L1', src(['S5'], 'A 5 mm polyp'))],
                      target__places=[fact('transverse_colon', src(['S5'], 'transverse colon'))]),
                event('E3', ['S7'], 'removed with a snare', 'were not both removed', 'snare',
                      neg('performed', src(['S7'], 'were not both removed')), session=[fact('X1', src(['S7']))],
                      scope__breadth=[fact('listed_targets', src(['S7'], 'The two polyps'))],
                      scope__targets=list(targets), target__lesion=[fact('L2', src(['S7'], 'polyps'))])])


def pairs_answer():
    """PAIRS' answer: a colonoscopy X1 (E1 its examination), a forceps biopsy in the ascending colon (E2), a
    hot-forceps removal in the transverse colon (E3), a cold-snare removal in the sigmoid colon (E4), and a denial of
    rectal biopsies (E5, single target)."""
    today = fact('on_date_of_service', src(['S2'], '', 'document_frame'))
    return answer(
        sections=[section('N0', src([], '', 'section'), occasion=[today]),
                  section('N1', src(['S4'], 'Findings:', 'section'), occasion=[today],
                          performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))])],
        sessions=[session('X1', 'colonoscopy', src(['S1'], 'COLONOSCOPY', 'document_frame'), fact('E1', src(['S4'])))],
        events=[event('E1', ['S4'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S4']))]),
                event('E2', ['S5'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S5']))],
                      target__places=[fact('ascending_colon', src(['S5'], 'ascending colon'))]),
                event('E3', ['S6'], 'removed with hot forceps', 'was removed', 'hot_biopsy',
                      session=[fact('X1', src(['S6']))],
                      target__places=[fact('transverse_colon', src(['S6'], 'transverse colon'))]),
                event('E4', ['S7'], 'removed with a cold snare', 'was removed', 'snare',
                      session=[fact('X1', src(['S7']))],
                      target__places=[fact('sigmoid_colon', src(['S7'], 'sigmoid colon'))]),
                event('E5', ['S8'], 'biopsies', 'No biopsies were taken', 'biopsy',
                      neg('performed', src(['S8'], 'No biopsies were taken')), session=[fact('X1', src(['S8']))],
                      scope__breadth=[fact('single_target', src(['S8'], 'from the rectum'))],
                      target__places=[fact('rectum', src(['S8'], 'rectum'))])])


class CompletenessTests(SimpleTestCase):
    def test_only_for_an_upper_eus_session_whose_station_list_is_empty(self):
        claim_set = build(EUS, eus_answer())
        (complete,) = claim_set.completeness
        self.assertEqual(sentence_of(claim_set, complete.claim),
                         'The document does not say that the ultrasound examination of session X1 covered only some '
                         'of the esophagus, the stomach and the duodenum.')
        self.assertEqual(sentence_of(claim_set, complete.control),
                         'The document says that the ultrasound examination of session X1 covered only some of the '
                         'esophagus, the stomach and the duodenum.')
        self.assertEqual(claim_set.claim(complete.claim).units, ('S4',))
        self.assertIn(complete.control, claim_set.controls)
        self.assertNotIn(complete.claim, claim_set.controls)
        for stations, tract in ((([fact('duodenum', src(['S4']))]), 'upper'), ((), 'lower')):
            self.assertEqual(build(EUS, eus_answer(stations=stations, tract=tract)).completeness, ())

    def test_none_when_the_sessions_kind_tract_or_list_is_not_claimable(self):
        # the arbiter's 2c#6: the claim renders the session's kind and tract and its empty list, so a doubt about the
        # kind, a whole doubt, a doubt about the stations or a failed tract leaves no completeness claim (STATIONS then
        # stays unmet: fail-closed), as every claim's facts must be claimable
        for doubt in ({'about': 'kind', 'objects': ['X1'], 'units': ['S4'], 'basis': 'unclear',
                       'readings': ['eus', 'egd']},
                      {'about': 'whole', 'objects': ['X1'], 'units': ['S4'], 'basis': 'stated', 'readings': []},
                      {'about': 'stations', 'objects': ['X1'], 'units': ['S4'], 'basis': 'unclear', 'readings': []}):
            with self.subTest(doubt=doubt['about']):
                data = eus_answer()
                data['doubts'] = [doubt]
                claim_set = build(EUS, data)
                self.assertEqual(claim_set.completeness, ())
                self.assertFalse([text for text in sentences(claim_set) if 'covered only some' in text])
        findings = {FactKey(F.SESSION, 'X1', A.TRACT, 0): (Reason.FRAME_ROLE,)}
        self.assertEqual(build(EUS, eus_answer(), findings).completeness, ())
        self.assertEqual(len(build(EUS, eus_answer()).completeness), 1)  # the control: claimable, it is made


# --- cards (2.4 [R:SC-C][R:CO-7]) --------------------------------------------------------------------------------------


def shared_answer():
    """SHARED's answer: one sentence denying two acts, filed as two denials sharing the anchor S4."""
    return answer(
        clinician=[], people=[],
        sections=[section('N0', src([], '', 'section'), owner_source=src(['S1'], '', 'document_frame')),
                  section('N1', src(['S3'], 'Findings:', 'section'), owner_source=src(['S1'], '', 'document_frame'),
                          occasion=[fact('on_date_of_service', src(['S2'], '', 'document_frame'))])],
        sessions=[session('X1', 'colonoscopy', src(['S1'], 'COLONOSCOPY', 'document_frame'), fact('E1', src(['S3'])))],
        events=[event('E1', ['S3'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S3']))]),
                event('E2', ['S4'], 'biopsy', 'Neither', 'biopsy', neg('performed', src(['S4'], 'Neither'))),
                event('E3', ['S4'], 'tattoo', 'was performed', 'tattoo', neg('performed', src(['S4'], 'nor')))])


class CardTests(SimpleTestCase):
    def test_a_card_names_only_its_type_and_units(self):
        claim_set = build(NOTE, note_answer())
        self.assertEqual([(card.id, card.type, card.units, card.kind_words, card.status_words)
                          for card in claim_set.cards], [
            ('A1', CardType.ACT, ('S4',), None, None), ('A2', CardType.ACT, ('S5',), None, None),
            ('A3', CardType.ACT, ('S6',), None, None), ('A4', CardType.ACT, ('S7',), None, None),
            ('X1', CardType.SESSION, ('S5',), None, None), ('L1', CardType.LESION, ('S6',), None, None)])
        self.assertEqual(dict(claim_set.objects), {'A1': (F.EVENT, 'E4'), 'A2': (F.EVENT, 'E1'),
                                                   'A3': (F.EVENT, 'E2'), 'A4': (F.EVENT, 'E3'),
                                                   'X1': (F.SESSION, 'X1'), 'L1': (F.LESION, 'L1')})

    def test_a_cards_letter_is_its_types(self):
        # the arbiter's 0b#9: contract/types' CardType.letter numbers the cards, and no label table of this step holds
        # one of its own
        self.assertFalse([member for member in claims.LABELS if isinstance(member, CardType)])
        for card in build(RICH, rich_answer()).cards:
            self.assertEqual(card.id[0], card.type.letter)

    def test_numbering_follows_the_document_never_pass_1s_order(self):
        data = note_answer()
        data['events'] = list(reversed(data['events']))
        data['lesions'] = list(reversed(data['lesions']))
        self.assertEqual([(card.id, card.units) for card in build(NOTE, data).cards],
                         [(card.id, card.units) for card in build(NOTE, note_answer()).cards])

    def test_same_anchor_cards_carry_each_events_own_words(self):
        claim_set = build(SHARED, shared_answer())
        by = {claim_set.objects[card.id][1]: card for card in claim_set.cards if card.type is CardType.ACT}
        self.assertIsNone(by['E1'].kind_words)
        biopsy, tattoo = by['E2'], by['E3']
        self.assertEqual((SHARED[biopsy.kind_words.start:biopsy.kind_words.end],
                          SHARED[biopsy.status_words.start:biopsy.status_words.end]), ('biopsy', 'Neither'))
        self.assertEqual((SHARED[tattoo.kind_words.start:tattoo.kind_words.end],
                          SHARED[tattoo.status_words.start:tattoo.status_words.end]), ('tattoo', 'was performed'))
        self.assertEqual((biopsy.id, tattoo.id), ('A2', 'A3'))  # numbered by where their own words stand


# --- content keys, the order and the bound -----------------------------------------------------------------------------


class OrderTests(SimpleTestCase):
    def test_identical_inputs_give_an_equal_claim_set(self):
        first, second = build(RICH, rich_answer()), build(RICH, copy.deepcopy(rich_answer()))
        self.assertEqual(first, second)
        self.assertEqual(first.sha256(), second.sha256())

    def test_byte_identical_in_any_process(self):
        code = ('import sys, json; sys.path.insert(0, %r)\n'
                'import django, os; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cptstudio.settings")\n'
                'django.setup()\n'
                'from tests.v2 import test_claims as t\n'
                'claim_set = t.build(t.RICH, t.rich_answer())\n'
                'print(claim_set.sha256(), json.dumps([claim_set.sentences[c.id] for c in claim_set.claims]))\n'
                % str(APP))
        outputs = set()
        for seed in ('0', '1', '4242'):
            result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, timeout=120,
                                    cwd=APP, env={'PYTHONHASHSEED': seed, 'PATH': '/usr/bin:/bin',
                                                  **{key: value for key, value in __import__('os').environ.items()
                                                     if key.startswith('CPT_STUDIO_')}})
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.add(result.stdout)
        self.assertEqual(len(outputs), 1)
        self.assertIn(build(RICH, rich_answer()).sha256(), outputs.pop())

    def test_the_seeded_order(self):
        claim_set = build(RICH, rich_answer())
        keys = [jsonschema.sha256_of([claim_set.seed, claim.content]) for claim in claim_set.claims]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual([claim.id for claim in claim_set.claims], [f'K{n}' for n in
                                                                    range(1, len(claim_set.claims) + 1)])
        other = build(RICH, rich_answer(), seed='another seed')
        self.assertEqual({claim.content for claim in other.claims}, {claim.content for claim in claim_set.claims})
        self.assertNotEqual([claim.content for claim in other.claims], [claim.content for claim in claim_set.claims])
        # controls are interleaved: not every control follows its claim
        follows = [int(item.control[1:]) == int(item.claim[1:]) + 1 for item in claim_set.appraised if item.control]
        self.assertFalse(all(follows))

    def test_the_content_key_binds_template_subject_value_units_and_params(self):
        claim_set = build(NOTE, note_answer())
        for claim in claim_set.claims:
            self.assertEqual(len(claim.content), 64)
        self.assertEqual(len({claim.content for claim in claim_set.claims}), len(claim_set.claims))
        spec = claims._Spec(claims.TemplateId.ACT_KIND, claims.Ref(F.EVENT, 'E2'), 'snare', ('S6',), (), ())
        for changed in (claims._Spec(claims.TemplateId.ACT_STATUS, spec.subject, 'snare', ('S6',), (), ()),
                        claims._Spec(spec.template, claims.Ref(F.EVENT, 'E3'), 'snare', ('S6',), (), ()),
                        claims._Spec(spec.template, spec.subject, 'emr', ('S6',), (), ()),
                        claims._Spec(spec.template, spec.subject, 'snare', ('S7',), (), ()),
                        claims._Spec(spec.template, spec.subject, 'snare', ('S6',), ('N2',), ())):
            self.assertNotEqual(changed.content(), spec.content())

    def test_shared_sentences_are_one_claim(self):
        data = note_answer()
        data['events'][1]['part_of'] = [fact('E1', src(['S6'], 'was removed'))]
        data['events'][1]['part_relation'] = [fact('step_of', src(['S6'], 'was removed'))]
        claim_set = build(NOTE, data)
        (part_of,), (relation,) = appraised(claim_set, A.PART_OF, 'E2'), appraised(claim_set, A.PART_RELATION, 'E2')
        self.assertEqual(part_of.claim, relation.claim)
        self.assertEqual(sentence_of(claim_set, part_of.claim), 'This act was a step of act A2.')  # E1's card
        self.assertIsNone(part_of.control)  # UNCONTROLLED

    def test_the_per_request_bound(self):
        self.assertEqual(claims.CLAIM_BOUND, 640)
        claim_set = build(NOTE, note_answer())
        self.assertFalse(claims.over_bound(claim_set))
        many = claims.ClaimSet(claim_set.cards, claim_set.claims * 641, claim_set.sentences, claim_set.about,
                               (), (), (), (), claim_set.objects, frozenset(), claim_set.seed)
        self.assertTrue(claims.over_bound(many))


# --- the pins (2.5) and 5.7 measure 4 ------------------------------------------------------------------------------------

# The shas this step hands the integration owner (FINAL-V2 2.5, 8.0; the arbiter's INT-5), each computed here.
# Recomputed after the repairs under DECISIONS D194-D196 and the arbiter's 2c#2-2c#8: TEMPLATES 7e61dec2...,
# STATEMENT_TEMPLATES 8de21ba3... and CONTROLS 52b9c337... are superseded; CLAIMED is step 1f's after its own repairs
# (789b8fcc... and b6ade5f5... superseded). Recomputed again after refute-2c-r1's repairs (the motility label; the
# tract order, the contrast fallback and the reported acts in CONTROLS): TEMPLATES 6787eec1... and CONTROLS 6158b68b...
# are superseded. Until the first recording under gemini-appraisal@1 a changed object needs only its pin recomputed, no
# version bump (D202).
TEMPLATES_SHA256 = '9efd3e1d2d1fd8124f3bb4c54169e5ede90dc5a4d7bdd7a7f0496927264a7ce0'
STATEMENT_TEMPLATES_SHA256 = '3880e4af3eefbdbccf0c5bb8e4a099df1d50268b485e991f46db7b8f3a19e162'
CONTROLS_SHA256 = '19fbf9621e4f3569170e0ed27a460fd4b172b7596b8d689c1a9c0d0c021db144'
CLAIM_BOUND_SHA256 = '58f544bee79e592b0a40c01e24884995f2e9dd4dd9ff4c16aeec104dcf691f02'
CLAIMED_SHA256 = '8c95246d6ff8a260b344bb5a52e25f51ac744343ed8ebe5887764ad7e5cd7b81'  # step 1f's, handed on


class PinTests(SimpleTestCase):
    def test_the_shas_handed_to_the_integration_owner(self):
        self.assertEqual(jsonschema.sha256_of(claims.templates_document()), TEMPLATES_SHA256)
        self.assertEqual(jsonschema.sha256_of(claims.statement_templates_document()), STATEMENT_TEMPLATES_SHA256)
        self.assertEqual(jsonschema.sha256_of(claims.controls_document()), CONTROLS_SHA256)
        self.assertEqual(jsonschema.sha256_of(claims.claim_bound_document()), CLAIM_BOUND_SHA256)
        self.assertEqual(rq.claimed_sha256(), CLAIMED_SHA256)
        # D202: the integration owner writes them in one commit after the wave's repairs; until then '' (refused)
        for name, measured in (('TEMPLATES_SHA256', TEMPLATES_SHA256), ('CONTROLS_SHA256', CONTROLS_SHA256),
                               ('STATEMENT_TEMPLATES_SHA256', STATEMENT_TEMPLATES_SHA256),
                               ('CLAIMED_SHA256', CLAIMED_SHA256), ('CLAIM_BOUND_SHA256', CLAIM_BOUND_SHA256)):
            self.assertIn(getattr(interpretation, name), ('', measured), name)

    def test_a_changed_table_changes_its_pin(self):
        for name, document, table in (
                ('templates', claims.templates_document, 'TEMPLATES'),
                ('statement templates', claims.statement_templates_document, 'STATEMENT_TEMPLATES'),
                ('labels', claims.templates_document, 'LABELS'),
                ('controls', claims.controls_document, 'KIND_SIBLINGS'),
                ('session siblings', claims.controls_document, 'SESSION_SIBLINGS'),
                ('contrast', claims.controls_document, 'CONTRAST_PLACES'),
                ('uncontrolled', claims.controls_document, 'UNCONTROLLED'),
                ('rules', claims.controls_document, 'CONTROLS')):
            with self.subTest(table=name):
                before = jsonschema.sha256_of(document())
                original = getattr(claims, table)
                if isinstance(original, tuple):
                    changed = original[:-1]
                else:
                    changed = dict(original)
                    changed.pop(next(iter(changed)))
                with mock.patch.object(claims, table, changed):
                    self.assertNotEqual(jsonschema.sha256_of(document()), before)
        # 2c#8: the pair-control selection itself is in CONTROLS_SHA256's document - the review's mutant R4 (the sibling
        # arms dropped) moves it, as a reordered candidate list does
        before = jsonschema.sha256_of(claims.controls_document())
        with mock.patch.object(claims, '_compatible', lambda statement, act: catalogue.covers(statement, act)):
            self.assertNotEqual(jsonschema.sha256_of(claims.controls_document()), before)
        reordered = dict(claims.CONTRAST_PLACES)
        reordered[Landmark.RECTUM] = tuple(reversed(reordered[Landmark.RECTUM]))
        with mock.patch.object(claims, 'CONTRAST_PLACES', reordered):
            self.assertNotEqual(jsonschema.sha256_of(claims.controls_document()), before)
        acts, wholes = claims.BUNDLING_PAIR_KINDS
        with mock.patch.object(claims, 'BUNDLING_PAIR_KINDS', (acts, wholes - {Kind.SNARE})):
            self.assertNotEqual(jsonschema.sha256_of(claims.controls_document()), before)


# The module's pinned OUTPUT tables (FINAL-V2 5.7 NoWordLists: claims.TEMPLATES and the label tables), the only
# module-level collections of string literals it may hold.
OUTPUT_TABLES = ('TEMPLATES', 'STATEMENT_TEMPLATES', 'KIND_LABELS', 'LABELS', 'PLACE_LABELS', 'STATEMENT_DATE_PHRASES',
                 'CARD_PHRASES')
ALLOWED_IMPORTS = {
    '__future__.annotations', 'collections.abc.Callable', 'collections.abc.Iterable', 'collections.abc.Mapping',
    'collections.abc.Sequence', 'dataclasses.dataclass', 'dataclasses.field', 'enum.Enum', 'enum.unique',
    'types.MappingProxyType', 'typing.cast', 'studio.interpretation.contract.extract_schema',
    'studio.interpretation.contract.jsonschema', 'studio.interpretation.engine.anatomy',
    'studio.interpretation.engine.catalogue', 'studio.interpretation.engine.requirements'}


class GuardTests(SimpleTestCase):
    def test_measure_4_holds_with_its_pinned_output_tables(self):
        source = MODULE.read_text(encoding='utf-8')
        tree = ast.parse(source)
        lines = set()
        for node in tree.body:
            target = getattr(node, 'target', None)
            if isinstance(node, ast.AnnAssign) and getattr(target, 'id', '') in OUTPUT_TABLES:
                lines |= {item.lineno for item in ast.walk(node.value)
                          if isinstance(item, (ast.Dict, ast.Tuple, ast.List, ast.Set))
                          and any(isinstance(child, ast.Constant) and isinstance(child.value, str)
                                  for child in [*getattr(item, 'keys', ()), *getattr(item, 'values', ()),
                                                *getattr(item, 'elts', ())])}
        # WordsNeverDecide binds claims.py (5.7 measure 4): engine=True applies its text rules here too
        findings = measure_4(source, engine=True)
        self.assertEqual(sorted(findings), sorted(f'a module-level word list at line {line}' for line in lines))
        self.assertEqual(len({line for line in lines}), len(lines))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                found |= {f'{node.module}.{alias.name}' for alias in node.names
                          if not node.module.startswith('studio.interpretation.contract.types')
                          and not node.module.startswith('studio.interpretation.contract.extract_read')}
        self.assertEqual(found, ALLOWED_IMPORTS)
        for plant, expected in (('import re\n', 'imports re'), ('import unicodedata\n', 'imports unicodedata'),
                                ('from studio.interpretation.contract import segment\n', 'imports a text module'),
                                ('from studio.interpretation import lexicon\n', 'imports studio.interpretation.lexicon'),
                                ("NEGATORS = ('no', 'not')\n", 'a module-level word list'),
                                ('def f(value):\n    return value.startswith("no")\n', 'calls .startswith()'),
                                ('def f(value):\n    return "no" in value\n', 'tests membership against a string')):
            with self.subTest(plant=plant.strip()):
                self.assertTrue(any(expected in finding for finding in measure_4(source + '\n' + plant, engine=True)))

    def test_no_file_of_the_step_cites_the_report_decisions_records(self):
        # DECISIONS D207: every builder's report was refused by the harness; the readings are D207's, the rulings each
        # their own entry, and no file of this step points at the report
        name = 'REPORT' + '.md'
        for path in STEP_FILES:
            with self.subTest(file=path.name):
                self.assertNotIn(name, path.read_text(encoding='utf-8'))
        self.assertIn('D207', Path(__file__).read_text(encoding='utf-8'))

    def test_a_fresh_interpreter_loads_no_retired_or_text_module_through_claims(self):
        code = ('import sys\n'
                f'sys.path.insert(0, {str(APP)!r})\n'
                'import studio.interpretation.contract.claims\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True, timeout=60,
                                cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        loaded = result.stdout.strip().split(',')
        retired = {f'studio.interpretation.{name}' for name in (
            'prompt', 'schema', 'read', 'normalize', 'verify', 'literals', 'identity', 'lexicon', 'relations',
            'mapping', 'classes', 'ercp', 'facts', 'events', 'coverage', 'combination', 'assess')}
        text_modules = {f'studio.interpretation.contract.{name}' for name in ('segment', 'geometry', 'fold',
                                                                              'date_literals')}
        self.assertFalse((retired | text_modules) & set(loaded), loaded)
        self.assertIn('studio.interpretation.contract.claims', loaded)
