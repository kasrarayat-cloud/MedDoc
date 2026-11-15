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
  step cites a report the harness never kept (D207);
- the integration owner's rulings on waves 1-2, built by step 2c3: sibling labels are contraries - the act of each
  manometry code and of 43263, and the anorectal and motility sessions, each with a true claim and a false control,
  and every pair of KIND_SIBLINGS and SESSION_SIBLINGS audited (SiblingContraryTests, D209); an all_of_kind breadth's
  control listing only the reported acts that may lie in its own session (ReportedActsTests, D210); pair controls only
  for the kind pairs a rule of identity by place reads together, and the claim count of one session with many snares
  and biopsies (PairBoundTests, D211); a lesion's places with their template and contrast control (LesionPlaceTests,
  D212); an act's and a statement's device, a targeted breadth and moderate sedation's kind controlled, and the segment
  control's candidate order pinned (RemainingGapTests, D213);
- the integration owner's rulings on waves 3-4, built by repair r2c: the control audit extended from genus to overlap -
  every pair of KIND_SIBLINGS, SESSION_SIBLINGS and the device contraries audited with its reason, each overlapping
  pair given a contrary its kind never is (a bleed treated with clips, a drainage told with its needle step, an argon
  plasma coagulation, moderate sedation's control true of every procedure, the four further overlaps the audit found),
  and the parts of an exchange and a replacement reading plainly true (OverlapTests, D222); each fact one sentence tells
  - an exceptive breadth and each act it excepts, a segment's two places, part_of and part_relation - its own claim of
  that sentence with its own control, and a segment's pair controls asking its whole range (OneSentenceTests, D223);
  the rulings' stated outcomes end to end through settle, the store and the engine's pairing (RulingOutcomeTests); and
  D210's fail-closed arm for an act whose unestablished session names another session (ReportedActsTests, 2c3's P1);
- refute-r2c-r1's findings, repaired by r2c-2: a pair control is never one claim with a contrary control - a contrary
  prefers a place or a lesion no pair control asks the same object about, and a pair control's content key carries its
  role - so a segment's place next to its range, a single target beside the place next to it, and two lesions each the
  other's contrary are set apart end to end (PairRoleTests, RulingOutcomeTests; RF1, RF2); two place facts of one
  object never share a control (ContrastTests, the repair's own finding of RF1's class); an ablation's control a clip
  placement, never "a treatment of bleeding", true of an ablation of a lesion that bleeds (RF3; superseded by D233,
  below); a whole-tract segment's two places unclaimed, never one control read by both (OneSentenceTests; RF6);
- the integration owner's rulings on waves 5-6, built by repair r2c of round w7r: an ablation's control is the bleeding
  control again, its label narrowed to the hemostasis purpose's own wording ("a treatment of bleeding present at this
  encounter"), so an oozing lesion treated with argon plasma coagulation and filed as an ablation keeps its kind
  unresolved and holds the ablation and the bleeding-control code with one question, and an ablation with no bleeding
  stated at this encounter is established and its code READY, in every family with an ablation code (OverlapTests,
  RulingOutcomeTests; D233, refute-r2c-r2 G1); each listed target of a denial appraised by a control of its own, a
  lesion no other lesion fact of the statement takes, and unclaimed (control) when none is left, so the second listed
  target is established and the removal of another polyp met (ListedTargetTests; D234, G2), and its claim count
  before and after against the bound (PairBoundTests); and a supported value '' read as not supported, never raising,
  settling unresolved end to end (EmptyValueTests; D251's O3).
The readings this step's builder made are recorded in DECISIONS D207, step 2c3's in its NOTES, and repair r2c's,
r2c-2's and w7r r2c's in their NOTES.
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
# DECISIONS D209: one note per manometry code and one for 43263's sphincter of Oddi manometry, each telling the study
# its code reports (the code's covered act, catalogue.CODES)
STUDY_NOTE = ('SYNTHETIC MOTILITY NOTE\n'
              'Date of service: 06/02/2031\n'
              'Endoscopist: Q. R. Vance, MD (fictional)\n'
              '\n'
              'Procedure: {study} was performed.\n')
SOD = ('SYNTHETIC ERCP NOTE\n'
       'Date of service: 06/02/2031\n'
       'Endoscopist: Q. R. Vance, MD (fictional)\n'
       '\n'
       'Findings: The duodenoscope was advanced to the papilla.\n'
       'Sphincter of Oddi manometry was performed through the papilla.\n')
# DECISIONS D210 (refute-2c-r2 B, its probe p11's shape): an upper endoscopy's gastric biopsy beside a colonoscopy's
# denial of every biopsy of the colonoscopy, and that colonoscopy's own biopsy
BIDI = ('SYNTHETIC BIDIRECTIONAL ENDOSCOPY NOTE\n'
        'Date of service: 06/02/2031\n'
        'Endoscopist: Q. R. Vance, MD (fictional)\n'
        '\n'
        'Procedure 1: Upper endoscopy.\n'
        'The gastroscope was advanced to the second portion of the duodenum.\n'
        'Biopsies of the gastric antrum were taken with cold forceps.\n'
        '\n'
        'Procedure 2: Colonoscopy.\n'
        'The colonoscope was advanced to the cecum.\n'
        'No biopsies were taken during the colonoscopy.\n'
        'A polyp in the ascending colon was sampled with cold forceps.\n'
        'Biopsies of the rectum were taken with cold forceps.\n')
SEDATION = ('SYNTHETIC COLONOSCOPY NOTE\n'
            'Date of service: 06/02/2031\n'
            'Endoscopist: Q. R. Vance, MD (fictional)\n'
            '\n'
            'Findings: The colonoscope was advanced to the cecum.\n'
            'Moderate sedation was given by the endoscopist.\n')


def many_note(count):
    """DECISIONS D211's shape (refute-2c-r2's probe p12): one colonoscopy and ``count`` polyps, one sentence each."""
    lines = ['SYNTHETIC COLONOSCOPY NOTE R2N', 'Date of service: 06/02/2031',
             'Endoscopist: Q. R. Vance, MD (fictional)', '', 'Findings: The colonoscope was advanced to the cecum.']
    return '\n'.join(lines + [f'Polyp {number} was handled as listed.' for number in range(1, count + 1)]) + '\n'


# The study each manometry code and 43263 reports, as its note tells it, and the words of it the act's kind label must
# name for the kind claim to be true of that act (DECISIONS D209)
STUDIES = {91010: ('Esophageal manometry', 'esophageal'),
           91013: ('Esophageal manometry with stimulation and perfusion', 'esophageal'),
           91020: ('Gastric manometry', 'gastric'), 91022: ('Duodenal manometry', 'duodenal'),
           91040: ('An esophageal balloon distension study', 'esophageal balloon distension study'),
           91117: ('Colonic manometry', 'colonic'), 91122: ('Anorectal manometry', 'anorectal'),
           43263: ('Sphincter of Oddi manometry', 'sphincter of Oddi')}
NOTES = {'NOTE': NOTE, 'RICH': RICH, 'EUS': EUS, 'SHARED': SHARED, 'SEGMENT': SEGMENT, 'PAIRS': PAIRS,
         'DUODENAL': DUODENAL, 'WIDE': WIDE, 'MANOMETRY': MANOMETRY, 'LISTED': LISTED, 'SOD': SOD, 'BIDI': BIDI,
         'SEDATION': SEDATION,
         **{f'STUDY {code}': STUDY_NOTE.format(study=study) for code, (study, _words) in STUDIES.items()
            if code != 43263},
         **{f'MANY {count}': many_note(count) for count in range(0, 31)}}

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
            # a lesion's places (CLAIMED, D195), with DECISIONS D212's template "Lesion {lesion} is in the {place}."
            ('L1', 'multiplicity', 'single', None), ('L1', 'places', 'transverse_colon', None)]))
        self.assertEqual([(item.key.object, item.key.attribute, item.why) for item in claim_set.unclaimed], [])

    def test_a_denial_is_claimed_with_statement_phrased_sentences(self):
        claim_set = build(NOTE, note_answer())
        by_attribute = {item.key.attribute: sentence_of(claim_set, item.claim)
                        for item in claim_set.appraised if item.key.object == 'E3'}
        self.assertEqual(by_attribute, {
            A.KIND: 'This statement is about tissue samplings with forceps (not hot forceps).',
            A.STATUS: 'This statement says that tissue sampling with forceps (not hot forceps) was not done.',
            A.SESSION: 'This statement is about session X1.',
            A.DATE_RELATION: 'This statement is about tissue samplings with forceps (not hot forceps) on the date of '
                             'service.',
            A.SCOPE_BREADTH: 'This statement denies tissue sampling with forceps (not hot forceps) of the rectum.',
            A.TARGET_PLACES: 'This statement is about tissue samplings with forceps (not hot forceps) in the rectum.'})
        for item in appraised(claim_set, A.KIND, 'E2'):
            self.assertEqual(sentence_of(claim_set, item.claim),
                             'This act is a removal with a snare that is not an endoscopic mucosal resection.')

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
                         'This statement is about tissue samplings with forceps (not hot forceps).')
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
                         'This statement is about tissue samplings with forceps (not hot forceps) by the person named '
                         'at S4.')
        self.assertEqual(sentence_of(claim_set, person.control),
                         'This statement is about tissue samplings with forceps (not hot forceps) by the person named '
                         'at S3.')
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
# lesion's places (CLAIMED, DECISIONS D195: SITE's lesion arm) take DECISIONS D212's "Lesion {lesion} is in the
# {place}." with the contrast control, so they are no dash any more.
NO_SUPPORTED_FORM = {(OC.STATEMENT, A.STATUS)}
# The controls the rulings give a form of its own, which no real claim takes: 3.2.3's three - the restatement's summary,
# the statement's "was done" and the completeness claim's limitation (DECISIONS D196 keeps them as prescribed) - and
# DECISIONS D213's exceptive breadth over a targeted breadth's own targets ("... other than {targets}"). D196 moved a
# performed act's control to the statement form, a real claim's; 3.2.2's act form of a negated status
# (ACT_STATUS_NEGATED) no claim takes, as an event whose status is negated is a statement (3.2.1).
OWN_FORMS = {claims.TemplateId.ACT_RESTATES_SUMMARY, claims.TemplateId.STMT_DONE,
             claims.TemplateId.SESSION_SOME_STATIONS, claims.TemplateId.STMT_BREADTH_EXCEPT_TARGETS}
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

    def test_every_control_takes_a_form_a_real_claim_takes_but_the_own_forms(self):
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
                         'This statement says that removal with a snare (not an endoscopic mucosal resection) was not '
                         'done.')
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
# control is needed only for values on such a path (D196). DECISIONS D213 decided the two rows that rested on 3.2.3's
# own rows (the pairing's technique row reads every device, an act's and a statement's; exclusion condition 3 reads a
# targeted breadth): every device and every targeted breadth now has its control, and those rows are gone. Each row
# left cites the design's or a ruling's own sentence that no READY or exclusion path turns on its values.
READY_FAMILIES = frozenset(row.family for row in CODES.values() if row.template not in rq.NEVER_READY)
VALUES_DECIDING_NOTHING = {
    (OC.ACT, A.KIND): (frozenset({Kind.EXAMINATION, Kind.EM_VISIT}),
                       '3.2.3: decided through session.kind and the visit facts, which are controlled'),
    (OC.STATEMENT, A.KIND): (frozenset({Kind.EXAMINATION, Kind.EM_VISIT}),
                             '3.2.3: decided through session.kind and the visit facts, which are controlled'),
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
    (OC.LESION, A.PLACES): (anatomy.ALTERED | anatomy.UNPLACED, 'engine/anatomy: never disjoint, in no region (D212)'),
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


# DECISIONS D213: the same-day rule's READY path and base_included read every act's kind, moderate sedation's included,
# so that read is a READY read. Step 1f's read-sets still mark it a hold read (engine/requirements._NO_SIBLING_KINDS);
# moving it is the integration owner's change (NOTES, a request), and until then P-CONTROLLED takes it from the ruling.
D213_READS = {(OC.ACT, A.KIND, Kind.MODERATE_SEDATION)}


class ControlTests(SimpleTestCase):
    def test_p_controlled_per_class_attribute_kind_and_value(self):
        reads = deciding_reads() | D213_READS
        self.assertGreater(len(reads), 400)
        # DECISIONS D213: every device of an act and of a statement, a targeted breadth and moderate sedation's kind
        # are read on a READY or exclusion path, and each is controlled (no row of VALUES_DECIDING_NOTHING names them)
        self.assertLessEqual({(OC.ACT, A.TECHNIQUE_DEVICE, Kind.SNARE), (OC.STATEMENT, A.TECHNIQUE_DEVICE, Kind.SNARE),
                              (OC.STATEMENT, A.SCOPE_BREADTH, Kind.BIOPSY), (OC.LESION, A.PLACES, None)}, reads)
        self.assertFalse({(OC.ACT, A.TECHNIQUE_DEVICE), (OC.STATEMENT, A.TECHNIQUE_DEVICE),
                          (OC.STATEMENT, A.SCOPE_BREADTH)} & set(VALUES_DECIDING_NOTHING))
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
        # the five session siblings: with them, every family a code of which can be READY has one (reflux's motility
        # was true in part of a pH study told with its manometric location of the sphincter: DECISIONS D222 gives it
        # anorectal testing)
        self.assertEqual({key.value: value.value for key, value in claims.SESSION_SIBLINGS.items()
                          if key.value in ('office_em', 'motility', 'reflux', 'anorectal', 'feeding_tube')},
                         {'office_em': 'em_other', 'motility': 'reflux', 'reflux': 'anorectal', 'anorectal': 'motility',
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
        # 3.2.3's list, DECISIONS D194's three and D213's moderate sedation, each chosen outside the kind
        self.assertEqual(len(claims.KIND_SIBLINGS), 39)
        self.assertEqual(claims.KIND_SIBLINGS[Kind.SPHINCTEROTOMY], Kind.DILATION)  # SC-C's case
        self.assertEqual({kind.value: claims.KIND_SIBLINGS[kind].value for kind in (
            Kind.REMOVAL, Kind.INTERVENTION, Kind.EM_PROLONGED, Kind.MODERATE_SEDATION)},
            {'removal': 'biopsy', 'intervention': 'examination', 'em_prolonged': 'em_visit',
             'moderate_sedation': 'intervention'})
        # the examination and the visit are decided through session.kind and the visit facts (3.2.3); other gets none
        # (D194: no catalogue kind, read on the hold path only). Moderate sedation has one since D213: the same-day
        # rule's READY path and base_included read every act's kind (1f's read-sets mark it: a request, NOTES)
        self.assertEqual(rq.CODABLE_KINDS - set(claims.KIND_SIBLINGS), {Kind.EXAMINATION, Kind.EM_VISIT, Kind.OTHER})
        kinds_on_a_path = {kind for object_class, attribute, kind in deciding_reads() if attribute is A.KIND
                           and object_class in (OC.ACT, OC.STATEMENT)}
        self.assertFalse(kinds_on_a_path & {Kind.OTHER})
        self.assertLessEqual((kinds_on_a_path | {Kind.MODERATE_SEDATION}) - {Kind.EXAMINATION, Kind.EM_VISIT},
                             set(claims.KIND_SIBLINGS))
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
            ('E1', A.STATUS): 'This statement says that examination as a whole (not a capsule study) was not done.',
            ('E1', A.DATE_RELATION): 'This act was done on a date before the date of service.',
            ('E1', A.PERFORMER): 'This act was done by a clinician other than the documenting clinician and their '
                                 'team.',
            ('E1', A.ENTRY): 'This act is told in the part of the document that begins at S5, written by nursing '
                             'staff.',
            ('E2', A.KIND): 'This act is an endoscopic mucosal resection.',
            ('E2', A.STATUS): 'This statement says that removal with a snare (not an endoscopic mucosal resection) was '
                              'not done.',
            ('E2', A.DATE_RELATION): 'This act was done on a date before the date of service.',
            ('E2', A.PERFORMER): 'This act was done by a clinician other than the documenting clinician and their '
                                 'team.',
            ('E2', A.ENTRY): 'This act is told in the part of the document that begins at S5, written by nursing '
                             'staff.',
            # the places of every kind a READY path reads (D196), the first candidate compatible with no place of E2
            ('E2', A.TARGET_PLACES): 'This act was done in the splenic flexure.',
            # an act's device, its sibling in its family (DECISIONS D213)
            ('E2', A.TECHNIQUE_DEVICE): 'This act used a hot snare.',
            # the history's removal, codable since D194: its sibling is outside the umbrella
            ('E4', A.KIND): 'This act is a tissue sampling with forceps other than hot forceps.',
            ('E4', A.STATUS): 'This statement says that removal by any method was not done.',
            ('E4', A.DATE_RELATION): 'This act was done on the date of service.',
            ('E4', A.ENTRY): 'This act is told in the part of the document that begins at S4, written by nursing '
                             'staff.',
            ('E3', A.KIND): 'This statement is about removals or samplings with hot forceps.',
            ('E3', A.STATUS): 'This statement says that tissue sampling with forceps (not hot forceps) was '
                              'done.',
            ('E3', A.DATE_RELATION): 'This statement is about tissue samplings with forceps (not hot forceps) on a '
                                     'date before the date of service.',
            ('E3', A.TARGET_PLACES): 'This statement is about tissue samplings with forceps (not hot forceps) in the '
                                     'sigmoid colon.',
            # a targeted breadth: the exceptive breadth over the same targets (DECISIONS D213)
            ('E3', A.SCOPE_BREADTH): 'This statement denies only tissue samplings with forceps (not hot forceps) other '
                                     'than those of the rectum.',
            ('X1', A.KIND): 'Session X1 is a flexible sigmoidoscopy.',
            ('X1', A.REACHED): 'In session X1 the endoscope did not reach the cecum.',
            ('L1', A.MULTIPLICITY): 'Lesion L1 is a group of lesions described only together.',
            # a lesion's places: the contrast rule (DECISIONS D212)
            ('L1', A.PLACES): 'Lesion L1 is in the splenic flexure.'})
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
                         'This statement denies only tissue samplings with forceps (not hot forceps) other than acts '
                         'A6.')
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
        # a device outside the technique classes: controlled since DECISIONS D213 (4.5's technique row reads any
        # established device), by its sibling in its family; a place of an act that is no dilation or stent:
        # controlled since DECISIONS D196, as every kind's places a READY path reads are
        claim_set = build(NOTE, note_answer())
        (device,) = appraised(claim_set, A.TECHNIQUE_DEVICE, 'E2')
        self.assertEqual(sentence_of(claim_set, device.control), 'This act used a hot snare.')
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
        # place LANDMARKS2's order puts between them (a container of some of them is compatible, so never chosen). Each
        # place of the segment has its own claim and control since DECISIONS D223: the first place's control the first
        # such candidate, the last place's the second
        expected = {('descending_colon', 'rectum'): ('splenic flexure', 'transverse colon'),
                    ('sigmoid_colon', 'rectum'): ('descending colon', 'splenic flexure'),
                    ('ascending_colon', 'sigmoid_colon'): ('cecum', 'terminal ileum'),
                    ('cecum', 'rectum'): ('terminal ileum', 'anal canal'),
                    ('rectum', 'descending_colon'): ('anal canal', 'transverse colon')}
        for segment, places in expected.items():
            with self.subTest(segment=segment):
                claim_set = build(SEGMENT, segment_answer(segment))
                members = sorted(appraised(claim_set, A.SCOPE_SEGMENT, 'E2'), key=lambda item: item.key.index)
                self.assertEqual([item.value for item in members], list(segment))
                self.assertEqual([sentence_of(claim_set, item.control) for item in members],
                                 ['This statement is about tissue samplings with forceps (not hot forceps) in the '
                                  f'{place}.' for place in places])
                ends = [Landmark(value) for value in segment]
                inside = claims.segment_range(*ends)
                for item in members:
                    control = claim_set.claim(item.control)
                    self.assertFalse([value for value in inside
                                      if anatomy.compatible(Landmark(control.value), value)])
        self.assertEqual([place.value for place in claims.segment_range(Landmark.DESCENDING_COLON, Landmark.RECTUM)],
                         ['descending_colon', 'sigmoid_colon', 'rectosigmoid', 'rectum'])
        self.assertEqual(claims.segment_range(Landmark.RECTUM, Landmark.DESCENDING_COLON),
                         claims.segment_range(Landmark.DESCENDING_COLON, Landmark.RECTUM))

    def test_a_duodenal_segment_keeps_the_second_portion_inside(self):
        # refute-2c-r1 problem 3: the second portion of the duodenum holds the ampulla, which LANDMARKS2 lists after the
        # fourth portion; a range keeping only the places that hold nothing left the second portion out, and its
        # control "in the duodenum (its second portion)" was inside the segment, true by construction
        expected = {('duodenal_bulb', 'third_portion_duodenum'): ('antrum of the stomach', 'body of the stomach'),
                    ('duodenal_bulb', 'fourth_portion_duodenum'): ('antrum of the stomach', 'body of the stomach'),
                    ('third_portion_duodenum', 'duodenal_bulb'): ('duodenum (its fourth portion)', 'jejunum'),
                    ('third_portion_duodenum', 'esophagus'): ('duodenum (its fourth portion)', 'jejunum')}
        for segment, places in expected.items():
            with self.subTest(segment=segment):
                claim_set = build(DUODENAL, duodenal_answer(segment))
                members = sorted(appraised(claim_set, A.SCOPE_SEGMENT, 'E2'), key=lambda item: item.key.index)
                self.assertEqual([sentence_of(claim_set, item.control) for item in members],
                                 ['This statement is about tissue samplings with forceps (not hot forceps) in the '
                                  f'{place}.' for place in places])
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
        checked, one_only = 0, set()
        for first, last in itertools.product(position, repeat=2):
            one, other = sorted((position[first], position[last]))
            between = [place for group in tract[one:other + 1] for place in group]
            found = claims.contrasts(claims.contrast_candidates([first, last]), claims.segment_range(first, last))
            with self.subTest(segment=(first.value, last.value)):
                self.assertTrue(found)
                self.assertIs(found[0], claims.contrast(claims.contrast_candidates([first, last]),
                                                        claims.segment_range(first, last)))
                # the first place's control and the last place's (DECISIONS D223: each its own), neither between
                for place_found in found[:2]:
                    self.assertFalse([place for place in between if anatomy.compatible(place_found, place)],
                                     place_found)
            if len(found) < 2:
                one_only.add((first.value, last.value))
            checked += 1
        self.assertEqual(checked, 28 * 28)
        # only a segment of the whole tract leaves its last place no contrast of its own: that place, and so the
        # segment, is not claimed (Unclaimable.CONTROL, fail-closed)
        self.assertEqual(one_only, {('proximal_esophagus', 'anal_canal'), ('anal_canal', 'proximal_esophagus')})

    def test_a_contrast_is_never_one_of_the_objects_own_places(self):
        # 2c#3: a dilation filed in the esophagus and the stomach; a denial of biopsies from the sigmoid colon and the
        # rectum. Each place's control is a place compatible with neither, never the other place's own claim - and,
        # since repair r2c-2, never the other place's control either: the duodenum was both places' first contrast, one
        # control read by two facts, which the store reads for the first alone (the stomach settled unappraised)
        data = rich_answer()
        data['events'][1]['target']['places'] = [fact('esophagus', src(['S7'], 'distal esophagus')),
                                                  fact('stomach', src(['S7'], 'distal esophagus'))]
        data['events'][7]['target']['places'] = [fact('sigmoid_colon', src(['S14'], 'No biopsies')),
                                                  fact('rectum', src(['S14'], 'No biopsies'))]
        claim_set = build(RICH, data)
        self.assertEqual({sentence_of(claim_set, claim.id) for claim in controls_of(claim_set, 'E2', A.TARGET_PLACES)},
                         {'This act was done in the duodenum.', 'This act was done in the jejunum.'})
        no_claim_or_control_read_twice(self, claim_set)
        self.assertEqual({sentence_of(claim_set, claim.id) for claim in controls_of(claim_set, 'E8', A.TARGET_PLACES)},
                         {'This statement is about tissue samplings with forceps (not hot forceps) in the descending '
                          'colon.',
                          'This statement is about tissue samplings with forceps (not hot forceps) in the anal canal.'})
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

    def test_two_places_of_one_object_never_share_a_control(self):
        # repair r2c-2 (refute-r2c-r1 RF1's class, found by the repair): an act's or a lesion's two places whose first
        # contrasts are one place - the esophagus and the stomach (the duodenum), the rectum and the anal canal (the
        # sigmoid colon): 30 of the 967 pairs of places that are not compatible - took one control for both facts, which
        # the store reads for one fact only, so the second place settled unappraised. A candidate another place fact of
        # the same object takes as its control now comes last among its candidates: in every such pair, for an act and
        # for a lesion, each place fact has a control of its own
        placed = list(claims.CONTRAST_PLACES)
        checked = 0
        for one, other in itertools.combinations(placed, 2):
            if anatomy.compatible(one, other):
                continue
            places = [fact(place.value, src(['S5'], 'two named places')) for place in (one, other)]
            data = frame_answer('colonoscopy', [
                examination(words='colonoscope'),
                event('E2', ['S5'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S5']))],
                      target__lesion=[fact('L1', src(['S5'], 'A polyp'))], target__places=places)],
                fact('E1', src(['S4'])), lesions=[lesion('L1', ['S5'], 'A polyp', places=copy.deepcopy(places))])
            claim_set = build(TWO_PLACES, data)
            for subject, attribute in (('E2', A.TARGET_PLACES), ('L1', A.PLACES)):
                items = appraised(claim_set, attribute, subject)
                with self.subTest(places=(one.value, other.value), subject=subject):
                    self.assertEqual(len(items), 2)
                    self.assertEqual(len({item.control for item in items} - {None}), 2)
            checked += 1
        self.assertEqual(checked, 967)

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
        # without the covered act, the exceptive breadth is claimed and so is its excepted act, each its own claim of
        # the one exceptive sentence (DECISIONS D223), the act's controlled by the covers form naming it
        data['events'][7]['scope']['covers'] = []
        claim_set = build(RICH, data)
        (breadth,) = appraised(claim_set, A.SCOPE_BREADTH, 'E8')
        (excepted,) = appraised(claim_set, A.SCOPE_EXCEPTS, 'E8')
        self.assertNotEqual(breadth.claim, excepted.claim)
        for item in (breadth, excepted):
            self.assertEqual(sentence_of(claim_set, item.claim),
                             'This statement denies only tissue samplings with forceps (not hot forceps) other than '
                             'acts A6.')
        self.assertEqual((claim_set.claim(excepted.claim).value, sentence_of(claim_set, excepted.control)),
                         ('E6', 'This statement applies to act A6.'))
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
                         'This statement is about tissue samplings with forceps (not hot forceps) in the transverse '
                         'colon.')
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
        self.assertIn(['injection', 'fna'], kinds)  # an act whose sibling is the statement's kind (DECISIONS D222)
        self.assertIn(['removal', 'snare'], kinds)  # an umbrella and its member
        self.assertNotIn(['biopsy', 'snare'], kinds)
        # a clip or an injection beside a bleeding control statement: the catalogue reads such an act as one when its
        # purpose is hemostasis, and the pairing pairs them (the clip was the bleeding control's sibling until D222)
        self.assertIn(['bleeding_control', 'clip'], kinds)
        self.assertIn(['bleeding_control', 'injection'], kinds)
        self.assertNotIn(['clip', 'bleeding_control'], kinds)


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


# --- the integration owner's rulings on waves 1-2 (DECISIONS D209-D213) ------------------------------------------------


def study_answer(code):
    """The answer of the act ``code`` reports (DECISIONS D209): a session of the code's family and an act of the one
    kind the code covers (catalogue.CODES). 43263's sphincter of Oddi manometry is an ERCP's (SOD: E1 the session's
    examination, E2 the measurement); each manometry code's study is its session's one act, E1 (STUDY_NOTE)."""
    profile = catalogue.CODES[code]
    (kind,) = profile.covers
    today = fact('on_date_of_service', src(['S2'], '', 'document_frame'))
    team = fact('documenting_team', src(['S3'], '', 'document_frame'))
    sections = [section('N0', src([], '', 'section'), occasion=[today]),
                section('N1', src(['S4'], 'Findings:' if code == 43263 else 'Procedure:', 'section'), occasion=[today],
                        performer=[team])]
    if code == 43263:
        return answer(sections=sections,
                      sessions=[session('X1', 'ercp', src(['S1'], 'ERCP', 'document_frame'), fact('E1', src(['S4'])))],
                      events=[event('E1', ['S4'], 'duodenoscope', 'was advanced', 'examination',
                                    session=[fact('X1', src(['S4']))]),
                              event('E2', ['S5'], 'Sphincter of Oddi manometry', 'was performed', kind.value,
                                    session=[fact('X1', src(['S5']))])])
    study = STUDIES[code][0]
    return answer(sections=sections, sessions=[session('X1', profile.family.value, src(['S4'], study))],
                  events=[event('E1', ['S4'], study, 'was performed', kind.value, session=[fact('X1', src(['S4']))])])


# DECISIONS D209's audit, extended by D222 from genus to overlap: every pair of KIND_SIBLINGS and SESSION_SIBLINGS, with
# the reason its control is false of every act the claim's kind admits under pass 1's definition (the step's NOTES give
# the same table). Each reason opens with its class:
# - "narrowed": the sibling's label named a genus of the claim's kind (a faithful reading supported the control), so its
#   label now sets the claim's kind apart (NARROWED);
# - "replaced": D222's overlap - an act of the claim's kind done by the sibling's method, holding the sibling as a step
#   its own code includes, or using a device whose physics includes the sibling's, made the control true of a correct
#   filing; the pair takes a contrary the claim's kind never is (REPLACED gives the sibling it had);
# - "a misfiling": the overlap is an act whose correct filing is the sibling, or the sibling and the claim's kind as
#   parts (the sibling reported by a code of its own), so the control is meant to be true of it, and holds it;
# - any other: no act of the claim's kind is the sibling, does it, or holds it.
KIND_AUDIT = {
    (Kind.SNARE, Kind.EMR): ('a misfiling: an endoscopic mucosal resection is its own technique (a lift, then the '
                             'resection); a snare removal told with a lift is one, and the control holds it'),
    (Kind.EMR, Kind.SNARE): 'narrowed: most resections are done with a snare, so "a removal with a snare" was a genus',
    (Kind.ESD, Kind.EMR): ('a submucosal dissection is not a mucosal resection, and one finished with a snare is still '
                           'a dissection, which the label of a mucosal resection does not name'),
    (Kind.HOT_BIOPSY, Kind.BIOPSY): ('narrowed: hot forceps are forceps, so "a tissue sampling with forceps" was a '
                                     'genus'),
    (Kind.BIOPSY, Kind.HOT_BIOPSY): ('a misfiling: a forceps biopsy filed as such was not done with hot forceps; one '
                                     'that was is a hot biopsy, which the control holds'),
    (Kind.CLIP, Kind.INJECTION): ('a clip placement injects nothing; an injection beside it is its own act and code, '
                                  'never a step of placing a clip'),
    (Kind.INJECTION, Kind.CLIP): 'an injection places no clip',
    (Kind.TATTOO, Kind.INJECTION): ('the sibling label says it does not mark a site, which a tattoo, a saline lift '
                                    'before the ink included, does'),
    (Kind.BLEEDING_CONTROL, Kind.DILATION): ('replaced (D222, P4): a bleed is treated with clips, injections, heat or '
                                             'bands, so "a clip placement" was true of a bleed treated with clips; no '
                                             'treatment of bleeding, by any method, dilates a narrowing'),
    (Kind.ABLATION, Kind.BLEEDING_CONTROL): ('narrowed (D233, refute-r2c-r2 G1): an ablation of a lesion that bleeds '
                                             'chronically (an antral vascular ectasia, radiation proctitis) with no '
                                             'bleeding stated at this encounter is, in plain words, a treatment of '
                                             'bleeding (refute-r2c-r1 RF3), so the label now names the hemostasis '
                                             "purpose's own wording, bleeding present at this encounter; an ablation "
                                             'of tissue bleeding at this encounter is a misfiling - a treatment of '
                                             'bleeding present at this encounter is coded as the control of bleeding '
                                             "(D222's own example) - which the control holds"),
    (Kind.DILATION, Kind.STENT): 'a dilation leaves no stent in place; a stent placed after it is its own act and code',
    (Kind.STENT, Kind.STENT_REMOVAL): ('replaced (D222, this audit): a stent placement includes its pre- and '
                                       'post-dilation (its code says so), so "a dilation of a narrowing" was true of a '
                                       'stent placed after dilating; a placement removes no stent, and the removal '
                                       'label names the removal alone'),
    (Kind.BAND_LIGATION, Kind.INJECTION): 'a band ligation injects nothing; an injection beside it is its own act',
    (Kind.STONE_EXTRACTION, Kind.LITHOTRIPSY): ('a misfiling: an extraction removes stones; destroying them is '
                                                "lithotripsy's own code, and an extraction told with it is a "
                                                'lithotripsy, which the control holds'),
    (Kind.LITHOTRIPSY, Kind.SPHINCTEROTOMY): ('replaced (D222, this audit): the destruction of calculi includes '
                                              'removing the fragments (its code covers the extraction), so "an '
                                              'extraction of stones" was true of stones fragmented and swept out; a '
                                              'lithotripsy cuts no sphincter'),
    (Kind.STENT_REMOVAL, Kind.STENT): ('a misfiling: a stent removal, the removal alone, places no stent; a removal '
                                       'told with its replacement as one act is an exchange, which the control holds'),
    (Kind.STENT_EXCHANGE, Kind.STENT_REMOVAL): ('narrowed: every exchange removes a stent, so "a stent removal" was a '
                                                'genus of it; the label names the removal alone, never the whole '
                                                'exchange (reworded by D222, P3, so the parts read plainly true)'),
    (Kind.SPHINCTEROTOMY, Kind.DILATION): ('a misfiling: a sphincterotomy cuts; a balloon sphincteroplasty filed as '
                                           "one is the control's catch (SC-C)"),
    (Kind.CANNULATION, Kind.SPHINCTEROTOMY): ('a misfiling: a cannulation cuts nothing; a precut that gains it is a '
                                              'sphincterotomy of its own code, which the control holds'),
    (Kind.CHOLANGIOSCOPY, Kind.CANNULATION): ('narrowed: a cholangioscope enters the duct, so "a cannulation of a '
                                              'duct" was true of it in part; the label sets the examination inside '
                                              'it apart'),
    (Kind.FOREIGN_BODY, Kind.STONE_EXTRACTION): 'a foreign body or a food bolus is no stone',
    (Kind.PEG, Kind.TUBE_PLACEMENT): 'the sibling label says other than a gastrostomy, which a PEG is',
    (Kind.TUBE_PLACEMENT, Kind.PEG): 'a tube placement filed as such is not a gastrostomy',
    (Kind.TUBE_REPLACEMENT, Kind.TUBE_PLACEMENT): ('narrowed: every replacement places a tube, so "a tube placement" '
                                                   'was a genus of it; the label names the placement alone, never '
                                                   'the whole replacement (reworded by D222, P3)'),
    (Kind.DECOMPRESSION, Kind.STENT): 'a decompression leaves a tube, never a stent (a stent placed for it is a stent)',
    (Kind.MYOTOMY, Kind.DILATION): 'a myotomy cuts muscle; it stretches no narrowing',
    (Kind.FUNDOPLICATION, Kind.MYOTOMY): 'a fundoplication folds the stomach; it cuts no muscle',
    (Kind.FNA, Kind.INJECTION): ('replaced (D222, this audit): a fine-needle biopsy may be taken with forceps passed '
                                 'through the needle, so "a tissue sampling with forceps" was true of it; a '
                                 'fine-needle aspiration or biopsy injects nothing into tissue'),
    (Kind.DRAINAGE, Kind.BAND_LIGATION): ('replaced (D222, P2): a drainage holds its needle puncture and aspiration, '
                                          'so "a fine-needle aspiration or biopsy" was true of it in part; no step of '
                                          'a drainage (needle, wire, dilated tract, stent) ligates with a band'),
    (Kind.CAPSULE_STUDY, Kind.EXAMINATION): ("narrowed: a capsule study is its session's examination, so \"the "
                                             'examination itself" was true of it; the label sets capsule studies '
                                             'apart'),
    (Kind.MANOMETRY, Kind.PRESSURE_MEASUREMENT): 'narrowed (D209): a manometry is a pressure measurement',
    (Kind.PRESSURE_MEASUREMENT, Kind.MANOMETRY): 'narrowed (D209): a sphincter of Oddi manometry is a manometry study',
    (Kind.PH_MONITORING, Kind.PRESSURE_MEASUREMENT): ('replaced (D222, this audit): a pH study may hold the manometric '
                                                      'location of the sphincter its probe is placed by, so "a '
                                                      'manometry study" was true of it in part; no pH study measures '
                                                      'the pressure of the sphincter of Oddi'),
    (Kind.RECTAL_SENSATION, Kind.BALLOON_EXPULSION): ('a sensation, tone or compliance test expels no balloon; an '
                                                      'expulsion test is its own act'),
    (Kind.BALLOON_EXPULSION, Kind.RECTAL_SENSATION): ('an expulsion test is no sensation, tone or compliance test; '
                                                      'graded distension testing is a code of its own'),
    (Kind.REMOVAL, Kind.BIOPSY): 'D194: a removal of a lesion is not a sampling with forceps',
    (Kind.INTERVENTION, Kind.EXAMINATION): 'D194: an intervention is never the examination itself',
    (Kind.EM_PROLONGED, Kind.EM_VISIT): 'D194: prolonged time is time added to a visit, not a visit',
    (Kind.MODERATE_SEDATION, Kind.INTERVENTION): ('narrowed (D213; D222, P6): in the form its control takes, the '
                                                  'intervention label names the examination itself or an intervention '
                                                  'of any kind other than sedation: true of every procedure on the '
                                                  'patient, false of sedation'),
}
SESSION_AUDIT = {
    (SessionKind.COLONOSCOPY, SessionKind.FLEX_SIG): ('a colonoscopy, complete or not, is no flexible sigmoidoscopy '
                                                      '(52/53 for a short one)'),
    (SessionKind.FLEX_SIG, SessionKind.COLONOSCOPY): 'a flexible sigmoidoscopy is no colonoscopy',
    (SessionKind.EGD, SessionKind.EUS): ('a misfiling: an upper endoscopy with no ultrasound is no ultrasound '
                                         'examination; an EGD session holding one is an EUS, which the control holds'),
    (SessionKind.EUS, SessionKind.EGD): 'narrowed: an upper EUS is an upper endoscopy with ultrasound, so a genus',
    (SessionKind.ERCP, SessionKind.EGD): 'narrowed: an ERCP passes a scope into the upper tract, so a genus',
    (SessionKind.ENTEROSCOPY, SessionKind.EGD): 'narrowed: a push enteroscopy is an upper endoscopy that goes on',
    (SessionKind.CAPSULE, SessionKind.EGD): ('a misfiling: a capsule endoscopy passes no scope; an endoscopic '
                                             'delivery of the capsule is an upper endoscopy of its own, which the '
                                             'control holds when filed inside the capsule session'),
    (SessionKind.OFFICE_EM, SessionKind.EM_OTHER): 'the sibling label says in another setting',
    (SessionKind.MOTILITY, SessionKind.REFLUX): ('a manometry study measures pressure; impedance channels in it are '
                                                 "the manometry's own, never a monitoring study"),
    (SessionKind.REFLUX, SessionKind.ANORECTAL): ('replaced (D222, this audit): a pH or impedance study may hold the '
                                                  'manometric location of the sphincter its probe is placed by, so '
                                                  "motility's label was true of it in part; no reflux study is an "
                                                  'anorectal test'),
    (SessionKind.ANORECTAL, SessionKind.MOTILITY): ('narrowed (refute-2c-r1 problem 2): the sibling label says not an '
                                                    'anorectal test'),
    (SessionKind.FEEDING_TUBE, SessionKind.EGD): ("a misfiling: the family's codes are tube procedures done without "
                                                  "an endoscope; an endoscopic tube placement is an upper endoscopy's "
                                                  'code, which the control holds'),
}
# The pairs D222's overlap replaced, and the sibling each had: P4, P2 and this step's audit (a stent placed after
# dilating, stones fragmented and swept out, a fine-needle biopsy taken with forceps, a pH study placed by a manometric
# location of its sphincter, and that study's session). refute-r2c-r1's RF3 replaced the ablation's sibling with the
# clip placement; DECISIONS D233 returned it to the bleeding control with that label narrowed (NARROWED).
REPLACED = {(Kind.BLEEDING_CONTROL, Kind.DILATION): Kind.CLIP, (Kind.DRAINAGE, Kind.BAND_LIGATION): Kind.FNA,
            (Kind.STENT, Kind.STENT_REMOVAL): Kind.DILATION,
            (Kind.LITHOTRIPSY, Kind.SPHINCTEROTOMY): Kind.STONE_EXTRACTION,
            (Kind.FNA, Kind.INJECTION): Kind.BIOPSY, (Kind.PH_MONITORING, Kind.PRESSURE_MEASUREMENT): Kind.MANOMETRY}
SESSION_REPLACED = {(SessionKind.REFLUX, SessionKind.ANORECTAL): SessionKind.MOTILITY}
# The words each narrowed sibling's label holds that set the claim's kind apart, and each narrowed label's head: the
# label it had before, which the kind's own claim keeps, so that claim stays true of every act of its own kind.
NARROWED = {
    (Kind.EMR, Kind.SNARE): 'not an endoscopic mucosal resection',
    (Kind.HOT_BIOPSY, Kind.BIOPSY): 'other than hot forceps',
    (Kind.STENT_EXCHANGE, Kind.STENT_REMOVAL): 'the removal alone',
    (Kind.TUBE_REPLACEMENT, Kind.TUBE_PLACEMENT): 'the placement alone',
    (Kind.CAPSULE_STUDY, Kind.EXAMINATION): 'not a capsule study',
    (Kind.CHOLANGIOSCOPY, Kind.CANNULATION): 'not an examination inside the duct with a cholangioscope',
    (Kind.MANOMETRY, Kind.PRESSURE_MEASUREMENT): 'of the sphincter of Oddi',
    (Kind.PRESSURE_MEASUREMENT, Kind.MANOMETRY): 'other than one of the sphincter of Oddi',
    (Kind.MODERATE_SEDATION, Kind.INTERVENTION): 'other than sedation',
    (Kind.ABLATION, Kind.BLEEDING_CONTROL): 'present at this encounter'}  # DECISIONS D233
SESSION_NARROWED = {
    (SessionKind.EUS, SessionKind.EGD): 'not an endoscopic ultrasound examination',
    (SessionKind.ERCP, SessionKind.EGD): 'an endoscopic retrograde cholangiopancreatography',
    (SessionKind.ENTEROSCOPY, SessionKind.EGD): 'or a small-bowel enteroscopy',
    (SessionKind.ANORECTAL, SessionKind.MOTILITY): 'not an anorectal test'}
HEADS = {Kind.SNARE: 'a removal with a snare', Kind.BIOPSY: 'a tissue sampling with forceps',
         Kind.STENT_REMOVAL: 'a stent removal', Kind.TUBE_PLACEMENT: 'a tube placement other than a gastrostomy',
         Kind.EXAMINATION: 'the examination itself, not an act done during it',
         Kind.CANNULATION: 'a cannulation of a duct',
         Kind.PRESSURE_MEASUREMENT: 'a pressure measurement', Kind.MANOMETRY: 'a manometry study',
         # the form moderate sedation's control takes (D222, P6): its head names the examination too
         Kind.INTERVENTION: 'the examination itself or an intervention of any kind',
         Kind.BLEEDING_CONTROL: 'a treatment of bleeding'}  # D233: the label it had before


class SiblingContraryTests(SimpleTestCase):
    """DECISIONS D209: sibling labels are contraries - each kind claim true of every act of its kind, each control
    false of it."""

    def test_the_act_of_each_manometry_code_and_of_43263_has_a_true_claim_and_a_false_control(self):
        # refute-2c-r2 A: the manometry act's control "This act is a pressure measurement." was true of every manometry,
        # and the reverse true of 43263's: every manometry code (91010-91122) and 43263 held on a correct reading
        self.assertEqual(sorted(code for code, profile in catalogue.CODES.items()
                                if set(profile.covers) & {Kind.MANOMETRY, Kind.PRESSURE_MEASUREMENT}), sorted(STUDIES))
        for code, (study, named) in STUDIES.items():
            with self.subTest(code=code):
                (kind,) = catalogue.CODES[code].covers  # the code's act: the one kind it covers
                text = SOD if code == 43263 else STUDY_NOTE.format(study=study)
                claim_set = build(text, study_answer(code))
                (item,) = appraised(claim_set, A.KIND, 'E2' if code == 43263 else 'E1')
                claim, control = sentence_of(claim_set, item.claim), sentence_of(claim_set, item.control)
                sibling = claims.KIND_SIBLINGS[kind]
                self.assertEqual((claim, control), (f'This act is {claims.KIND_LABELS[kind][1]}.',
                                                    f'This act is {claims.KIND_LABELS[sibling][1]}.'))
                self.assertIn(named, claim)  # true of the act: the claim names the study the code reports
                if code == 43263:  # false of it: the control sets the sphincter of Oddi's apart
                    self.assertIn('other than one of the sphincter of Oddi', control)
                else:  # false of it: the control names the sphincter of Oddi's, which the claim sets apart
                    self.assertEqual(control, 'This act is a pressure measurement of the sphincter of Oddi.')
                    self.assertNotIn(named, control)
                    self.assertIn('other than one of the sphincter of Oddi', claim)
        # both passes say it (D209): pass 1's definition of each kind names what pass 2's label names
        line = extract_schema.DEFINITIONS[Kind]
        self.assertIn('pressure_measurement (a pressure measurement of the sphincter of Oddi)', line)
        self.assertIn('manometry (any manometry study other than one of the sphincter of Oddi', line)

    def test_the_anorectal_and_motility_sessions_have_a_true_claim_and_a_false_control(self):
        # 91122's session (anorectal) and 91010's (motility): each family's claim names its own studies, and its control
        # (SESSION_SIBLINGS) is a family that sets them apart
        for code, family in ((91122, SessionKind.ANORECTAL), (91010, SessionKind.MOTILITY)):
            with self.subTest(family=family.value):
                self.assertIs(catalogue.CODES[code].family, family)
                claim_set = build(STUDY_NOTE.format(study=STUDIES[code][0]), study_answer(code))
                (item,) = appraised(claim_set, A.KIND, 'X1')
                sibling = claims.SESSION_SIBLINGS[family]
                self.assertEqual((sentence_of(claim_set, item.claim), sentence_of(claim_set, item.control)),
                                 (f'Session X1 is {claims.LABELS[family]}.',
                                  f'Session X1 is {claims.LABELS[sibling]}.'))
        anorectal, motility, reflux = (claims.LABELS[family] for family in (
            SessionKind.ANORECTAL, SessionKind.MOTILITY, SessionKind.REFLUX))
        self.assertTrue(motility.endswith('not ' + anorectal))  # anorectal's control sets anorectal testing apart
        self.assertIn('the esophagus', motility)  # motility's claim names 91010's study
        self.assertFalse({'manometry', 'motility'} & set(reflux.split()))  # and its control, reflux, names neither

    def test_every_sibling_pair_is_audited_and_none_names_a_genus_of_its_kind(self):
        # D209's audit, extended from genus to overlap by DECISIONS D222: each pair's reason opens with its class
        self.assertEqual(set(KIND_AUDIT), set(claims.KIND_SIBLINGS.items()))
        self.assertEqual(set(SESSION_AUDIT), set(claims.SESSION_SIBLINGS.items()))
        for pair, reason in {**KIND_AUDIT, **SESSION_AUDIT}.items():
            self.assertTrue(reason, pair)
            self.assertEqual(reason.startswith('narrowed'), pair in NARROWED or pair in SESSION_NARROWED, pair)
            self.assertEqual(reason.startswith('replaced (D222'), pair in REPLACED or pair in SESSION_REPLACED, pair)
        # each replaced pair takes a contrary the claim's kind never is, never the sibling it had, and never one the
        # claim's umbrella covers or that covers it
        for (kind, sibling), had in {**REPLACED, **SESSION_REPLACED}.items():
            with self.subTest(replaced=(kind.value, sibling.value)):
                self.assertIsNot(sibling, had)
                if isinstance(kind, Kind):
                    self.assertIs(claims.KIND_SIBLINGS[kind], sibling)
                    self.assertFalse(catalogue.covers(kind, sibling) or catalogue.covers(sibling, kind))
                else:
                    self.assertIs(claims.SESSION_SIBLINGS[kind], sibling)
        self.assertEqual(len(REPLACED) + len(SESSION_REPLACED), 7)  # D233 took the ablation back to NARROWED
        for (kind, sibling), words in NARROWED.items():
            with self.subTest(pair=(kind.value, sibling.value)):
                self.assertIn(words, claims.KIND_LABELS[sibling][1])
                self.assertTrue(claims.KIND_LABELS[sibling][1].startswith(HEADS[sibling]))
        for (family, sibling), words in SESSION_NARROWED.items():
            with self.subTest(pair=(family.value, sibling.value)):
                self.assertIn(words, claims.LABELS[sibling])
                self.assertIn(claims.LABELS[family].partition(' ')[2], claims.LABELS[sibling])  # the family, set apart
        self.assertTrue(claims.LABELS[SessionKind.EGD].startswith('an upper endoscopy that is not '))
        # a narrowed label's bare and plural forms carry the same exclusion, in parentheses (a template writes more
        # after them: "... of lesion L1", "... in the rectum"), so it can never be read into what follows
        for kind in HEADS:
            bare, _article, plural = claims.KIND_LABELS[kind]
            with self.subTest(kind=kind.value):
                if kind in (Kind.EXAMINATION, Kind.PRESSURE_MEASUREMENT):
                    # the examination's bare and plural forms end with their exclusion; 43263's names its organ
                    continue
                self.assertTrue(bare.endswith(')') and plural.endswith(')'), (bare, plural))


def bidi_answer(doubts=(), gastric=None, colon=None, rectal=None):
    """BIDI's answer (refute-2c-r2's probe p11): X1 an upper endoscopy (E1) with a gastric biopsy (E2); X2 a colonoscopy
    (E3) with the denial of every biopsy of X2 (E4, all_of_kind). ``colon`` adds X2's own biopsy E5 and ``rectal`` its
    rectal biopsies E6, each with its fields set by the dict given; ``gastric`` sets E2's fields."""
    team = fact('documenting_team', src(['S3'], '', 'document_frame'))
    today = fact('on_date_of_service', src(['S2'], '', 'document_frame'))
    gastric_biopsy = event('E2', ['S6'], 'Biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                           target__places=[fact('gastric_antrum', src(['S6'], 'gastric antrum'))])
    gastric_biopsy.update(gastric or {})
    events = [event('E1', ['S5'], 'gastroscope', 'was advanced', 'examination', session=[fact('X1', src(['S5']))]),
              gastric_biopsy,
              event('E3', ['S8'], 'colonoscope', 'was advanced', 'examination', session=[fact('X2', src(['S8']))]),
              event('E4', ['S9'], 'biopsies', 'No biopsies were taken', 'biopsy',
                    neg('performed', src(['S9'], 'No biopsies were taken')), session=[fact('X2', src(['S9']))],
                    scope__breadth=[fact('all_of_kind', src(['S9'], 'No biopsies'))])]
    if colon is not None:
        own = event('E5', ['S10'], 'sampled with cold forceps', 'was sampled', 'biopsy',
                    session=[fact('X2', src(['S10']))],
                    target__places=[fact('ascending_colon', src(['S10'], 'ascending colon'))])
        own.update(colon)
        events.append(own)
    if rectal is not None:
        rectum = event('E6', ['S11'], 'Biopsies', 'were taken', 'biopsy', session=[fact('X2', src(['S11']))],
                       target__places=[fact('rectum', src(['S11'], 'rectum'))])
        rectum.update(rectal)
        events.append(rectum)
    return answer(sections=[section('N0', src([], '', 'section'), occasion=[today], performer=[team]),
                            section('N1', src(['S4'], 'Procedure 1:', 'section'), occasion=[today], performer=[team]),
                            section('N2', src(['S7'], 'Procedure 2:', 'section'), occasion=[today], performer=[team])],
                  sessions=[session('X1', 'egd', src(['S4'], 'Upper endoscopy'), fact('E1', src(['S5']))),
                            session('X2', 'colonoscopy', src(['S7'], 'Colonoscopy'), fact('E3', src(['S8'])))],
                  events=events, doubts=list(doubts))


def contradicted(value, other, unit, words):
    """A contradicted fact of ``value`` and ``other`` (both sides as options), cited at ``unit``."""
    return fact('', src([unit], words), state='contradicted', options=[{'value': value, 'sources': [src([unit])]},
                                                                       {'value': other, 'sources': [src([unit])]}])


class ReportedActsTests(SimpleTestCase):
    """DECISIONS D210: an all_of_kind breadth's control lists only the reported acts that may lie in the statement's own
    session; in it, an act that cannot be listed makes the breadth Unclaimable.CONTROL; across sessions, nothing."""

    def breadth(self, data):
        claim_set = build(BIDI, data)
        why = {item.why for item in claim_set.unclaimed
               if (item.key.object, item.key.attribute) == ('E4', A.SCOPE_BREADTH)}
        return claim_set, appraised(claim_set, A.SCOPE_BREADTH, 'E4'), why

    def test_an_act_established_in_another_session_is_never_listed(self):
        # refute-2c-r2 B: the colonoscopy's "No biopsies were taken during the colonoscopy." got the control "...
        # other than acts A2" - A2 the upper endoscopy's gastric biopsy - which is literally true, so a wrong 45380 was
        # held, not excluded. No reported biopsy may lie in X2 now: no contrary, and the claim alone decides (3.2.3)
        claim_set, (breadth,), _why = self.breadth(bidi_answer())
        self.assertEqual(sentence_of(claim_set, breadth.claim),
                         'This statement says no tissue sampling with forceps (not hot forceps) at all was done in '
                         'session X2.')
        self.assertIsNone(breadth.control)
        self.assertEqual(claim_set.objects['A2'], (F.EVENT, 'E2'))
        self.assertFalse([text for text in sentences(claim_set) if 'other than acts' in text])
        # and across sessions an act that cannot be listed has no effect either (refute-2c-r2 F's widening of B): its
        # anchor invalid, its status contradicted, or doubted
        for name, gastric, doubts in (
                ('anchor invalid', {'anchor': {'units': ['S6', 'S99'], 'kind_words': 'Biopsies',
                                               'status_words': 'were taken'}}, ()),
                ('status contradicted', {'status': contradicted('performed', 'planned', 'S6', 'were taken')}, ()),
                ('status doubted', None, ({'about': 'status', 'objects': ['E2'], 'units': ['S6'], 'basis': 'unclear',
                                           'readings': ['performed', 'planned']},))):
            with self.subTest(gastric=name):
                claim_set, found, why = self.breadth(bidi_answer(doubts=doubts, gastric=gastric))
                self.assertEqual((len(found), found[0].control, why), (1, None, set()))

    def test_the_acts_of_its_own_session_are_listed(self):
        claim_set, (breadth,), _why = self.breadth(bidi_answer(colon={}))
        self.assertEqual(sentence_of(claim_set, breadth.control),
                         'This statement denies only tissue samplings with forceps (not hot forceps) other than acts '
                         'A5.')
        self.assertEqual(claim_set.objects['A5'], (F.EVENT, 'E5'))
        # an act whose session is not established may lie in the statement's: listed (fail-closed), whether its
        # session fact is silent or doubted
        for name, colon, doubts in (('silent', {'session': []}, ()),
                                    ('doubted', {}, ({'about': 'session', 'objects': ['E5'], 'units': ['S10'],
                                                      'basis': 'unclear', 'readings': ['X1', 'X2']},))):
            with self.subTest(session=name):
                claim_set, (breadth,), _why = self.breadth(bidi_answer(doubts=doubts, colon=colon))
                self.assertEqual(sentence_of(claim_set, breadth.control),
                                 'This statement denies only tissue samplings with forceps (not hot forceps) other '
                                 'than acts A5.')

    def test_an_act_whose_unestablished_session_names_another_session_is_listed(self):
        # refute-2c3-r1 P1: D210's fail-closed arm read with an act of ANOTHER session. E2, the upper endoscopy's
        # gastric biopsy, with its session doubted (X1 or X2), contradicted (X1 against X2) or failing a check on X1:
        # its session is not established, so it may lie in X2, the statement's own, and the control lists it (A2) - a
        # reading that trusted the doubted, contradicted or failed value naming X1 would drop it and leave the breadth
        # claim with no control
        doubted = {'about': 'session', 'objects': ['E2'], 'units': ['S6'], 'basis': 'unclear', 'readings': ['X1', 'X2']}
        both = {'session': [fact('', src(['S6'], 'Biopsies'), state='contradicted', options=[
            {'value': 'X1', 'sources': [src(['S6'])]}, {'value': 'X2', 'sources': [src(['S9'])]}])]}
        failed = {FactKey(F.EVENT, 'E2', A.SESSION, 0): (Reason.GEOMETRY_STATEMENT,)}
        for name, data, findings in (('doubted', bidi_answer(doubts=(doubted,)), None),
                                     ('contradicted', bidi_answer(gastric=both), None),
                                     ('failing a check', bidi_answer(), failed)):
            with self.subTest(session=name):
                claim_set = build(BIDI, data, findings)
                (breadth,) = appraised(claim_set, A.SCOPE_BREADTH, 'E4')
                self.assertIsNotNone(breadth.control)  # never the breadth claimed with no control
                self.assertEqual(sentence_of(claim_set, breadth.control),
                                 'This statement denies only tissue samplings with forceps (not hot forceps) other '
                                 'than acts A2.')
                self.assertEqual(claim_set.objects['A2'], (F.EVENT, 'E2'))
        # established in X1 (the control of the same input with no doubt, conflict or finding), it is never listed
        (breadth,) = appraised(build(BIDI, bidi_answer()), A.SCOPE_BREADTH, 'E4')
        self.assertIsNone(breadth.control)

    def test_an_act_of_its_own_session_that_cannot_be_listed_leaves_the_breadth_unclaimed(self):
        # refute-2c-r2 F: in the statement's own session, an act whose anchor is invalid, or whose status or kind is
        # contradicted, makes the breadth Unclaimable.CONTROL (2c#7's fail-closed reading), D210 pinned
        for name, colon in (
                ('anchor invalid', {'anchor': {'units': ['S10', 'S99'], 'kind_words': 'sampled with cold forceps',
                                               'status_words': 'was sampled'}}),
                ('status contradicted', {'status': contradicted('performed', 'planned', 'S10', 'was sampled')}),
                ('kind contradicted', {'kind': contradicted('biopsy', 'hot_biopsy', 'S10', 'cold forceps')})):
            with self.subTest(colon=name):
                claim_set, found, why = self.breadth(bidi_answer(colon=colon))
                self.assertEqual((found, why), ([], {claims.Unclaimable.CONTROL}))
                self.assertFalse([text for text in sentences(claim_set) if 'no tissue sampling' in text])
        # and beside a listable act of the session (E6): a list naming only the listable one would make the control
        # rejectable for an exceptive statement misfiled as all_of_kind, so the breadth is still not claimed
        claim_set, (breadth,), _why = self.breadth(bidi_answer(colon={}, rectal={}))
        self.assertEqual(sentence_of(claim_set, breadth.control),
                         'This statement denies only tissue samplings with forceps (not hot forceps) other than acts '
                         'A5 and A6.')
        for name, colon in (
                ('anchor invalid', {'anchor': {'units': ['S10', 'S99'], 'kind_words': 'sampled with cold forceps',
                                               'status_words': 'was sampled'}}),
                ('status contradicted', {'status': contradicted('performed', 'planned', 'S10', 'was sampled')})):
            with self.subTest(beside_a_listable_act=name):
                claim_set, found, why = self.breadth(bidi_answer(colon=colon, rectal={}))
                self.assertEqual((found, why), ([], {claims.Unclaimable.CONTROL}))
                self.assertFalse([text for text in sentences(claim_set) if 'other than acts' in text])


def many_answer(snares, biopsies, rich=False):
    """many_note's answer (refute-2c-r2's probe p12): one colonoscopy session X1 (E1 its examination) with ``snares``
    snare removals and then ``biopsies`` biopsies, each its own lesion and place. ``rich`` adds what a note telling "A 5
    mm polyp in the sigmoid colon was removed with a cold snare." gives too: each lesion's multiplicity and place, and
    each act's device."""
    places = ('cecum', 'ascending_colon', 'hepatic_flexure', 'transverse_colon', 'splenic_flexure', 'descending_colon',
              'sigmoid_colon', 'rectum')
    lesions, events = [], [event('E1', ['S4'], '', '', 'examination', session=[fact('X1', src(['S4']))])]
    for number in range(1, snares + biopsies + 1):
        unit, place, snare = f'S{4 + number}', places[number % len(places)], number <= snares
        extra = {'multiplicity': [fact('single', src([unit]))], 'places': [fact(place, src([unit]))]} if rich else {}
        lesions.append(lesion(f'L{number}', [unit], '', **extra))
        device = {'technique__device': [fact('cold_snare' if snare else 'cold_forceps', src([unit]))]} if rich else {}
        events.append(event(f'E{number + 1}', [unit], '', '', 'snare' if snare else 'biopsy',
                            session=[fact('X1', src([unit]))], target__lesion=[fact(f'L{number}', src([unit]))],
                            target__places=[fact(place, src([unit]))], **device))
    today = fact('on_date_of_service', src(['S2'], '', 'document_frame'))
    return answer(sections=[section('N0', src([], '', 'section'), occasion=[today]),
                            section('N1', src(['S4'], 'Findings:', 'section'), occasion=[today],
                                    performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))])],
                  sessions=[session('X1', 'colonoscopy', src(['S1'], '', 'document_frame'), fact('E1', src(['S4'])))],
                  lesions=lesions, events=events)


class PairBoundTests(SimpleTestCase):
    """DECISIONS D211: pair controls only for the (kind, kind) pairs a bundling identity-by-place rule reads together,
    both directions, a same-kind pair only where a rule reads a same-kind identity; the claim bound stays 640."""

    def test_pair_controls_only_for_the_kind_pairs_a_rule_of_identity_reads_together(self):
        # refute-2c-r2 C: every pair of acts whose kinds any place-identity rule reads, the same kind included, got
        # them - 17 separately filed snares gave 625 claims. No rule reads a snare against a snare: none now
        self.assertEqual(build(many_note(6), many_answer(6, 0)).pair_controls, ())
        claim_set = build(many_note(3), many_answer(2, 1))  # a biopsy (E4) beside two snare removals (E2, E3)
        pairs = {(pair.subject[1], pair.other[1]) for pair in claim_set.pair_controls}
        self.assertEqual(pairs, {('E2', 'E4'), ('E4', 'E2'), ('E3', 'E4'), ('E4', 'E3')})  # biopsy_of_removed_lesion
        kinds = claims.controls_document()['pair_controls']['place_identity_kind_pairs']
        self.assertEqual({one for one, other in kinds if one == other}, {'dilation'})  # D118's one stricture
        self.assertLessEqual([['biopsy', 'snare'], ['snare', 'biopsy'], ['injection', 'emr'], ['fna', 'drainage']],
                             [pair for pair in kinds if pair in (['biopsy', 'snare'], ['snare', 'biopsy'],
                                                                 ['injection', 'emr'], ['fna', 'drainage'])])
        self.assertNotIn(['snare', 'snare'], kinds)
        self.assertFalse(claims._place_identity_pair(Kind.HOT_BIOPSY, Kind.HOT_BIOPSY))
        self.assertTrue(claims._place_identity_pair(Kind.DILATION, Kind.DILATION))
        rich = build(RICH, rich_answer())  # the two dilations of one session keep theirs (D118)
        self.assertTrue([pair for pair in rich.pair_controls if {pair.subject[1], pair.other[1]} == {'E2', 'E3'}])

    def test_the_claim_count_of_one_session_with_many_snares_and_biopsies(self):
        # D211's measure (the whole grid, N + M up to 30, is in the step's NOTES). The p12 shape: under the bound up to
        # 19 acts, the first total over it 20 (8+12 = 645 to 10+10 = 653). Its realistic variant (each lesion's size and
        # place, each act's device): 18 acts already pass it (6+12 = 641 to 9+9 = 679) - reported to the integration
        # owner with the counts (NOTES, a request), never raised here: past the bound the request is never built
        # (TOO_LONG, 7.4 door 0), and D3 counts it. Repair r2c-2 restored the pair controls a contrary control had
        # absorbed (refute-r2c-r1 RF1, RF2): 12+6 513 -> 533, 10+10 623 -> 653 (p12's first total over moved from 21
        # to 20), 9+9 652 -> 679 (rich)
        for (snares, biopsies, rich), count in {(17, 0, False): 268, (16, 0, False): 253, (12, 6, False): 533,
                                                (10, 10, False): 653, (11, 10, False): 695, (9, 9, True): 679,
                                                (10, 10, True): 773}.items():
            with self.subTest(snares=snares, biopsies=biopsies, rich=rich):
                claim_set = build(many_note(snares + biopsies), many_answer(snares, biopsies, rich))
                self.assertEqual(len(claim_set.claims), count)
                self.assertEqual(claims.over_bound(claim_set), count > 640)
        self.assertEqual(claims.CLAIM_BOUND, 640)
        found = read(many_note(18), many_answer(9, 9, rich=True))
        with mock.patch.multiple(interpretation, **{name: value for name, value in appraise_prompt.pins().items()
                                                    if name != 'APPRAISAL_LOCAL_SCHEMA_SHA256'}):
            with self.assertRaises(appraise_prompt.OverBound) as caught:
                appraise_prompt.build_request(many_note(18), (), 'txt', found, findings={})
        self.assertEqual(caught.exception.count, 679)

    def test_the_claim_count_with_a_listed_denial_before_and_after_d234(self):
        # DECISIONS D234's cost, measured against the rule before it (no lesion taken, so every listed target read one
        # control): the stress shape of rich snares and biopsies with two further polyps a denial lists. A listed
        # target that shared the first one's control gets its own (one claim more); with one other lesion only, the
        # second listed target is not claimed (one claim less); with none, nothing changes. The whole grid is in the
        # step's NOTES (493 shapes +1, 2 shapes -1, 1 unchanged; none crosses CLAIM_BOUND, the first total over it 17
        # acts before and after); the other stress shapes have no listed denial and do not move (the counts above)
        for (snares, biopsies), (before, after) in {(9, 9): (718, 719), (15, 15): (1360, 1361), (12, 6): (689, 690),
                                                    (8, 8): (625, 626), (1, 0): (48, 47), (0, 0): (24, 24)}.items():
            with self.subTest(snares=snares, biopsies=biopsies):
                text, data = many_listed(snares, biopsies)
                claim_set = build(text, data)
                with mock.patch.object(claims._Builder, 'lesions_taken', lambda self, subject: set()):
                    earlier = build(text, data)
                self.assertEqual((len(earlier.claims), len(claim_set.claims)), (before, after))
                self.assertEqual((claims.over_bound(earlier), claims.over_bound(claim_set)),
                                 (before > 640, after > 640))


def many_listed(snares, biopsies):
    """The 'listed' stress shape (the step's NOTES, D234): many_answer's rich shape, then two further polyps seen and
    not removed, each its own lesion, and the denial of removing them (listed_targets)."""
    count = snares + biopsies
    text = many_note(count) + ('A further polyp was seen.\nAnother further polyp was seen.\n'
                               'The two further polyps were not removed.\n')
    data = many_answer(snares, biopsies, rich=True)
    data['lesions'] += [lesion(f'L{count + 1}', [f'S{5 + count}'], 'A further polyp'),
                        lesion(f'L{count + 2}', [f'S{6 + count}'], 'Another further polyp')]
    unit = f'S{7 + count}'
    data['events'].append(event(f'E{count + 4}', [unit], 'removed', 'were not removed', 'snare',
                                neg('performed', src([unit], 'were not removed')), session=[fact('X1', src([unit]))],
                                scope__breadth=[fact('listed_targets', src([unit], 'The two further polyps'))],
                                scope__targets=[f'L{count + 1}', f'L{count + 2}']))
    return text, data


NOTES.update({f'MANY LISTED {snares}+{biopsies}': many_listed(snares, biopsies)[0]
              for snares, biopsies in ((9, 9), (15, 15), (12, 6), (8, 8), (1, 0), (0, 0))})


class LesionPlaceTests(SimpleTestCase):
    """DECISIONS D212: a lesion's places, claimed wherever a READY or exclusion path reads them (SITE's lesion arm),
    with "Lesion {lesion} is in the {place}." and CONTRAST_PLACES' control."""

    def test_a_lesions_places_are_claimed_with_the_contrast_control(self):
        # refute-2c-r2 D (2c:F5): lesion L1 of a claimed snare, its places [transverse colon]: never claimed (no
        # template)
        claim_set = build(NOTE, note_answer())
        (place,) = appraised(claim_set, A.PLACES, 'L1')
        self.assertEqual((sentence_of(claim_set, place.claim), sentence_of(claim_set, place.control)),
                         ('Lesion L1 is in the transverse colon.', 'Lesion L1 is in the splenic flexure.'))
        self.assertEqual(claim_set.claim(place.control).units, claim_set.claim(place.claim).units)
        self.assertEqual(claims.template(claims.TemplateId.LESION_PLACES), 'Lesion {lesion} is in the {place}.')
        # two places: each control is compatible with neither (the first candidate disjoint from every place of it)
        data = note_answer()
        data['lesions'][0]['places'].append(fact('splenic_flexure', src(['S6'], 'transverse colon')))
        claim_set = build(NOTE, data)
        items = appraised(claim_set, A.PLACES, 'L1')
        self.assertEqual(len(items), 2)
        for item in items:
            contrast = Landmark(claim_set.claim(item.control).value)
            self.assertFalse([own for own in (Landmark.TRANSVERSE_COLON, Landmark.SPLENIC_FLEXURE)
                              if anatomy.compatible(contrast, own)], contrast)
        # a doubted or contradicted place of the lesion is never claimed
        doubted = note_answer()
        doubted['doubts'] = [{'about': 'target', 'objects': ['L1'], 'units': ['S6'], 'basis': 'unclear',
                              'readings': []}]
        both = note_answer()
        both['lesions'][0]['places'] = [contradicted('transverse_colon', 'sigmoid_colon', 'S6', 'transverse colon')]
        for name, data in (('doubted', doubted), ('contradicted', both)):
            with self.subTest(place=name):
                self.assertEqual(appraised(build(NOTE, data), A.PLACES, 'L1'), [])


def sedation_answer():
    """SEDATION's answer: a colonoscopy X1 (E1 its examination) and moderate sedation (E2)."""
    today = fact('on_date_of_service', src(['S2'], '', 'document_frame'))
    return answer(sections=[section('N0', src([], '', 'section'), occasion=[today]),
                            section('N1', src(['S4'], 'Findings:', 'section'), occasion=[today],
                                    performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))])],
                  sessions=[session('X1', 'colonoscopy', src(['S1'], '', 'document_frame'), fact('E1', src(['S4'])))],
                  events=[event('E1', ['S4'], 'colonoscope', 'was advanced', 'examination',
                                session=[fact('X1', src(['S4']))]),
                          event('E2', ['S5'], 'Moderate sedation', 'was given', 'moderate_sedation',
                                session=[fact('X1', src(['S5']))])])


class RemainingGapTests(SimpleTestCase):
    """DECISIONS D213: the remaining P-CONTROLLED gaps on READY paths get controls."""

    def test_every_device_has_its_sibling_in_its_family_or_another_device(self):
        self.assertEqual(set(claims.DEVICE_CONTRARY), set(Device))
        self.assertFalse([device for device, other in claims.DEVICE_CONTRARY.items() if device is other])
        self.assertFalse(set(claims.DEVICE_SIBLINGS) & set(claims.ANOTHER_DEVICE))
        self.assertEqual({key.value: value.value for key, value in claims.DEVICE_SIBLINGS.items()}, {
            'cold_snare': 'hot_snare', 'hot_snare': 'cold_snare', 'cold_forceps': 'hot_forceps',
            'hot_forceps': 'cold_forceps', 'balloon': 'wire_bougie', 'wire_bougie': 'balloon',  # 3.2.3's three pairs
            'snare': 'hot_snare', 'forceps': 'hot_forceps'})  # D213's "forceps and hot forceps"
        # an act's device outside the technique classes takes it (F-2: a cold snare misfiled where the note says hot is
        # no longer established by one "supports"); a technique class keeps 3.2.3's negated form
        claim_set = build(NOTE, note_answer())
        (device,) = appraised(claim_set, A.TECHNIQUE_DEVICE, 'E2')
        self.assertEqual(sentence_of(claim_set, device.control), 'This act used a hot snare.')
        # argon plasma coagulation delivers high-frequency current, so radiofrequency energy was true of it in part:
        # its contrary is cryotherapy (DECISIONS D222, P5)
        for value, expected in (('snare', 'This act used a hot snare.'), ('clip', 'This act used a band.'),
                                ('argon_plasma', 'This act used cryotherapy.')):
            with self.subTest(device=value):
                data = note_answer()
                data['events'][1]['technique']['device'] = [fact(value, src(['S6'], 'cold snare'))]
                claim_set = build(NOTE, data)
                (device,) = appraised(claim_set, A.TECHNIQUE_DEVICE, 'E2')
                self.assertEqual(sentence_of(claim_set, device.control), expected)
        rich = build(RICH, rich_answer())
        (balloon,) = appraised(rich, A.TECHNIQUE_DEVICE, 'E2')
        self.assertEqual(sentence_of(rich, balloon.control),
                         'The document states that a dilating balloon was not used for this act.')
        # a statement's device: its sibling in its family, else another device (4.5's technique row reads D's too)
        for value, expected in (('hot_forceps', 'cold forceps'), ('argon_plasma', 'cryotherapy')):
            with self.subTest(statement_device=value):
                data = note_answer()
                data['events'][2]['technique']['device'] = [fact(value, src(['S7'], 'biopsies'))]
                claim_set = build(NOTE, data)
                (device,) = appraised(claim_set, A.TECHNIQUE_DEVICE, 'E3')
                self.assertEqual(sentence_of(claim_set, device.control),
                                 f'This statement is about tissue samplings with forceps (not hot forceps) with '
                                 f'{expected}.')

    def test_a_targeted_breadth_is_controlled_by_the_exceptive_form_over_its_targets(self):
        # F-3: "No other polyps were removed." (exceptive) filed single_target: "This statement denies ... of lesion
        # L1." had no control, so one "supports" met 4.6 condition 3. Its control is the exceptive form over its targets
        claim_set = build(NOTE, note_answer())
        (breadth,) = appraised(claim_set, A.SCOPE_BREADTH, 'E3')
        self.assertEqual(sentence_of(claim_set, breadth.control),
                         'This statement denies only tissue samplings with forceps (not hot forceps) other than those '
                         'of the rectum.')
        claim_set = build(SEGMENT, segment_answer(('descending_colon', 'rectum')))
        (breadth,) = appraised(claim_set, A.SCOPE_BREADTH, 'E2')
        self.assertEqual(sentence_of(claim_set, breadth.control),
                         'This statement denies only tissue samplings with forceps (not hot forceps) other than those '
                         'of the descending colon to the rectum.')
        claim_set = build(LISTED, listed_answer(['L1', 'L2']))
        (breadth,) = appraised(claim_set, A.SCOPE_BREADTH, 'E3')
        self.assertEqual(sentence_of(claim_set, breadth.control),
                         'This statement denies only removals with a snare (not endoscopic mucosal resections) other '
                         'than those of lesions L1 and L2.')
        self.assertIn(claims.TemplateId.STMT_BREADTH_EXCEPT_TARGETS, OWN_FORMS)
        # an exceptive or an all_of_kind breadth keeps 3.2.3's own controls
        exceptive = claims.control_rule(OC.STATEMENT, A.SCOPE_BREADTH, FactState.SUPPORTED, Breadth.EXCEPTIVE)
        self.assertIs(exceptive.contrary, claims.Contrary.FIXED)

    def test_moderate_sedations_kind_has_a_sibling_false_of_sedation_and_true_of_a_procedure(self):
        # 1f's F2: a banding misfiled as moderate_sedation and one biased "supports" left no procedure that day, and
        # 99213 went READY without separate_em. The sibling, intervention, is false of sedation and, in the form its
        # control takes, true of every procedure on the patient, the examination included (DECISIONS D222, P6)
        claim_set = build(SEDATION, sedation_answer())
        (kind,) = appraised(claim_set, A.KIND, 'E2')
        self.assertEqual((sentence_of(claim_set, kind.claim), sentence_of(claim_set, kind.control)),
                         ('This act is moderate sedation.', 'This act is the examination itself or an intervention of '
                                                           'any kind, other than sedation.'))
        self.assertNotIn(Kind.MODERATE_SEDATION, catalogue.INTERVENTION_MEMBERS)  # false of sedation, by definition
        procedures = {kind for profile in catalogue.CODES.values() for kind in profile.covers
                      if profile.family in catalogue.PROCEDURAL_FAMILIES} - {Kind.EXAMINATION, Kind.MODERATE_SEDATION}
        self.assertTrue(procedures)
        self.assertLessEqual(procedures, {kind for kind in Kind if catalogue.covers(Kind.INTERVENTION, kind)})

    def test_the_segment_controls_candidate_order_is_pinned(self):
        # refute-2c-r2 E: the nearest disjoint landmark from the first place, then from the last, then the far ones. The
        # mutant MY1 (the first place's whole list, then the last's) changed 53 of 1,521 segments' controls and no test
        # failed, and CONTROLS_SHA256 did not move
        for (first, last), expected in {('anal_canal', 'cecum'): 'terminal_ileum',
                                        ('proximal_esophagus', 'duodenal_bulb'): 'second_portion_duodenum',
                                        ('proximal_esophagus', 'cecum'): 'ascending_colon',
                                        ('anal_canal', 'gastric_body'): 'gastric_fundus'}.items():
            with self.subTest(segment=(first, last)):
                ends = [Landmark(first), Landmark(last)]
                found = claims.contrast(claims.contrast_candidates(ends), claims.segment_range(*ends))
                self.assertIs(found, Landmark(expected))
        nearest = list(claims._NEAREST[Landmark.ANAL_CANAL])
        nearest += [place for place in claims._NEAREST[Landmark.CECUM] if place not in nearest]
        candidates = claims.contrast_candidates([Landmark.ANAL_CANAL, Landmark.CECUM])
        self.assertEqual(list(candidates)[:len(nearest)], nearest)

        def my1(places):
            found = []
            for place in places:
                found += [candidate for candidate in claims.CONTRAST_PLACES.get(place, ()) if candidate not in found]
            return tuple(found)

        before = jsonschema.sha256_of(claims.controls_document())
        with mock.patch.object(claims, 'contrast_candidates', my1):
            self.assertNotEqual(jsonschema.sha256_of(claims.controls_document()), before)


# --- the integration owner's rulings on waves 3-4 (DECISIONS D222, D223; repair r2c) ----------------------------------

# One act told in one sentence after the examination (S4: the part's label and the examination; S5: the act), for the
# overlaps D222 names and this step's audit found. Each note is synthetic (written here) and is in NOTES, so the
# exclusion test checks it.
OVERLAP_NOTE = ('SYNTHETIC {kind} NOTE\n'
                'Date of service: 06/02/2031\n'
                'Endoscopist: Q. R. Vance, MD (fictional)\n'
                '\n'
                'Findings: {exam}\n'
                '{act}\n')
OVERLAPS = {
    # name: (the note's kind and examination, the act's sentence, its kind, kind words, status words, session family,
    # the act's other fields)
    'P4 clips': (('COLONOSCOPY', 'The colonoscope was advanced to the cecum.'),
                 'Bleeding at the polypectomy site was treated with two clips.', 'bleeding_control',
                 'treated with two clips', 'was treated', 'colonoscopy',
                 {'technique__device': [fact('clip', src(['S5'], 'clips'))],
                  'purpose': [fact('hemostasis', src(['S5'], 'Bleeding'))]}),
    'P2 needle': (('ULTRASOUND', 'An upper endoscopic ultrasound examination was performed.'),
                  'The pancreatic fluid collection was punctured with a 19-gauge needle, fluid was aspirated, and it '
                  'was drained across the gastric wall with a stent.', 'drainage',
                  'drained across the gastric wall with a stent', 'was drained', 'eus',
                  {'target__structure': [fact('pancreatic_fluid_collection',
                                              src(['S5'], 'pancreatic fluid collection'))],
                   'technique__route': [fact('eus_transmural', src(['S5'], 'across the gastric wall'))]}),
    'P5 argon plasma': (('UPPER ENDOSCOPY', 'The gastroscope was advanced to the duodenum.'),
                        'The antral vascular ectasia was ablated with argon plasma coagulation.', 'ablation', 'ablated',
                        'was ablated', 'egd',
                        {'technique__device': [fact('argon_plasma', src(['S5'], 'argon plasma coagulation'))]}),
    'P6 sedation': (('COLONOSCOPY', 'The colonoscope was advanced to the cecum.'),
                    'Moderate sedation was given by the endoscopist.', 'moderate_sedation', 'Moderate sedation',
                    'was given', 'colonoscopy', {}),
    'audit stent': (('UPPER ENDOSCOPY', 'The gastroscope was advanced to the duodenum.'),
                    'The esophageal stricture was dilated with a balloon and a covered metal stent was placed across '
                    'it.', 'stent', 'a covered metal stent was placed', 'was placed', 'egd', {}),
    'audit lithotripsy': (('ERCP', 'The duodenoscope was advanced to the papilla.'),
                          'The stones were fragmented with electrohydraulic lithotripsy and the fragments were swept '
                          'out with a balloon.', 'lithotripsy', 'fragmented with electrohydraulic lithotripsy',
                          'were fragmented', 'ercp', {}),
    'audit microforceps': (('ULTRASOUND', 'An upper endoscopic ultrasound examination was performed.'),
                           'The cyst wall was sampled with microforceps passed through a 19-gauge needle.', 'fna',
                           'sampled with microforceps passed through a 19-gauge needle', 'was sampled', 'eus', {}),
    'audit pH': (('REFLUX', 'The lower esophageal sphincter was located by manometry.'),
                 'A pH catheter was placed above it for 24 hours of monitoring.', 'ph_monitoring', 'pH catheter',
                 'was placed', 'reflux', {}),
}
EXCHANGE = OVERLAP_NOTE.format(kind='ERCP', exam='The duodenoscope was advanced to the papilla.',
                               act='The existing biliary stent was removed and replaced with a new plastic stent.')
TUBE = OVERLAP_NOTE.format(kind='UPPER ENDOSCOPY', exam='The gastroscope was advanced to the duodenum.',
                           act='The nasojejunal feeding tube was removed and a new one was placed in the jejunum.')
APC = OVERLAP_NOTE.format(kind='UPPER ENDOSCOPY', exam='The gastroscope was advanced to the duodenum.',
                          act='The antral vascular ectasia was ablated with argon plasma coagulation.\n'
                              'No radiofrequency ablation was performed.')
UMBRELLA = OVERLAP_NOTE.format(kind='COLONOSCOPY', exam='The colonoscope was advanced to the cecum.',
                               act='Interventions were performed as listed.')
# D223's inputs: refute-3a-r2's p01 (BF17, "No other injection was given."), D223's own "No other polyps were
# removed." beside two snares, refute-3d-r2's R4 ("No biopsies were taken from the cecum to the hepatic flexure." beside
# a biopsy) and refute-3a-r2's p02 (a clip an adjunct done with a snare removal)
INJECTION_BF17 = ('SYNTHETIC COLONOSCOPY NOTE\n'
                  'Date of service: 06/02/2031\n'
                  'Endoscopist: Q. R. Vance, MD (fictional)\n'
                  '\n'
                  'Findings: The colonoscope was advanced to the cecum.\n'
                  'The sigmoid colon was tattooed with an injection of ink.\n'
                  'No other injection was given.\n')
POLYPS = ('SYNTHETIC COLONOSCOPY NOTE\n'
          'Date of service: 06/02/2031\n'
          'Endoscopist: Q. R. Vance, MD (fictional)\n'
          '\n'
          'Findings: The colonoscope was advanced to the cecum.\n'
          'A 4 mm polyp in the rectum was removed with a cold snare.\n'
          'A 3 mm polyp in the sigmoid colon was removed with a cold snare.\n'
          'No other polyps were removed.\n')
SEGMENT_RANGE = ('SYNTHETIC COLONOSCOPY NOTE\n'
                 'Date of service: 06/02/2031\n'
                 'Endoscopist: Q. R. Vance, MD (fictional)\n'
                 '\n'
                 'Findings: The colonoscope was advanced to the cecum.\n'
                 'Biopsies were taken with cold forceps.\n'
                 'No biopsies were taken from the cecum to the hepatic flexure.\n')
ADJUNCT = ('SYNTHETIC COLONOSCOPY NOTE\n'
           'Date of service: 06/02/2031\n'
           'Endoscopist: Q. R. Vance, MD (fictional)\n'
           '\n'
           'Findings: The colonoscope was advanced to the cecum.\n'
           'A 5 mm polyp in the cecum was removed with a cold snare.\n'
           'A clip was placed on the polypectomy site.\n')
NOTES.update({f'OVERLAP {name}': OVERLAP_NOTE.format(kind=kind, exam=exam, act=act)
              for name, ((kind, exam), act, *_rest) in OVERLAPS.items()})
NOTES.update({'EXCHANGE': EXCHANGE, 'TUBE': TUBE, 'APC': APC, 'UMBRELLA': UMBRELLA, 'INJECTION_BF17': INJECTION_BF17,
              'POLYPS': POLYPS, 'SEGMENT_RANGE': SEGMENT_RANGE, 'ADJUNCT': ADJUNCT})
# refute-r2c-r1's inputs (repair r2c-2): RF2's single target (a biopsy beside the denial of the place next to it) and
# RF2's lesions (a polyp left in place beside another removed), the two places of one object (the repair's own
# finding) and RF6's whole-tract segment
SINGLE_PLACE = ('SYNTHETIC COLONOSCOPY NOTE\n'
                'Date of service: 06/02/2031\n'
                'Endoscopist: Q. R. Vance, MD (fictional)\n'
                '\n'
                'Findings: The colonoscope was advanced to the cecum.\n'
                'Biopsies were taken from the sigmoid colon with cold forceps.\n'
                'No biopsies were taken from the rectum.\n')
POLYP_LEFT = ('SYNTHETIC COLONOSCOPY NOTE\n'
              'Date of service: 06/02/2031\n'
              'Endoscopist: Q. R. Vance, MD (fictional)\n'
              '\n'
              'Findings: The colonoscope was advanced to the cecum.\n'
              'A 6 mm polyp was seen in the cecum.\n'
              'A second polyp, 3 mm, in the sigmoid colon was removed with a cold snare.\n'
              'The 6 mm cecal polyp was not removed.\n')
POLYP_THIRD = POLYP_LEFT + 'A third polyp, in the rectum, was marked with a tattoo.\n'
TWO_PLACES = ('SYNTHETIC COLONOSCOPY NOTE\n'
              'Date of service: 06/02/2031\n'
              'Endoscopist: Q. R. Vance, MD (fictional)\n'
              '\n'
              'Findings: The colonoscope was advanced to the cecum.\n'
              'A polyp was found and biopsies were taken from the two named places.\n')
WHOLE_TRACT = ('SYNTHETIC ENDOSCOPY NOTE\n'
               'Date of service: 06/02/2031\n'
               'Endoscopist: Q. R. Vance, MD (fictional)\n'
               '\n'
               'Findings: The colonoscope was advanced to the cecum.\n'
               'No biopsies were taken from the proximal esophagus to the anal canal.\n')
PART_OF_COLON = ('SYNTHETIC COLONOSCOPY NOTE\n'
                 'Date of service: 06/02/2031\n'
                 'Endoscopist: Q. R. Vance, MD (fictional)\n'
                 '\n'
                 'Findings: The colonoscope was advanced to the cecum.\n'
                 'Biopsies were taken with cold forceps.\n'
                 'No biopsies were taken from the named part of the colon.\n')
NOTES.update({'SINGLE_PLACE': SINGLE_PLACE, 'POLYP_LEFT': POLYP_LEFT, 'POLYP_THIRD': POLYP_THIRD,
              'TWO_PLACES': TWO_PLACES, 'WHOLE_TRACT': WHOLE_TRACT, 'PART_OF_COLON': PART_OF_COLON})
RANGE_WORDS = 'from the cecum to the hepatic flexure'  # SEGMENT_RANGE's own words of its segment
COLON = tuple(Landmark(value) for value in (
    'cecum', 'appendiceal_orifice', 'ileocecal_valve', 'ascending_colon', 'hepatic_flexure', 'transverse_colon',
    'splenic_flexure', 'descending_colon', 'sigmoid_colon', 'rectosigmoid', 'rectum', 'anal_canal'))


def denial_answer(denied, biopsied, biopsy_words='Biopsies', denial_words='named part'):
    """A biopsy E2 (S5) in the places ``biopsied`` beside the denial E3 (S6) of biopsies in ``denied``: a segment from
    its first place to its last when it names two, else a single target (refute-r2c-r1's probes r02, r03, r04). The
    words cite the note's own (the checks locate them, so a run through settle needs them true)."""
    if len(denied) == 2:
        target = dict(scope__breadth=[fact('segment', src(['S6'], denial_words))], scope__segment=list(denied))
    else:
        target = dict(scope__breadth=[fact('single_target', src(['S6'], denial_words))],
                      target__places=[fact(denied[0], src(['S6'], denial_words))])
    return frame_answer('colonoscopy', [
        examination(words='colonoscope'),
        event('E2', ['S5'], 'Biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S5']))],
              target__places=[fact(place, src(['S5'], biopsy_words)) for place in biopsied]),
        event('E3', ['S6'], 'biopsies', 'No biopsies were taken', 'biopsy',
              neg('performed', src(['S6'], 'No biopsies were taken')), session=[fact('X1', src(['S6']))], **target)],
        fact('E1', src(['S4'])))


def polyp_left_answer():
    """POLYP_LEFT's answer: the cecal polyp L1 and the sigmoid polyp L2 (distinct from L1), the cold-snare removal E2
    of L2 and the denial E3 of removing L1 (single target): each lesion is the other's only contrary."""
    return frame_answer('colonoscopy', [
        examination(words='colonoscope'),
        event('E2', ['S6'], 'removed with a cold snare', 'was removed', 'snare', session=[fact('X1', src(['S6']))],
              target__lesion=[fact('L2', src(['S6'], 'A second polyp'))],
              target__places=[fact('sigmoid_colon', src(['S6'], 'sigmoid colon'))],
              technique__device=[fact('cold_snare', src(['S6'], 'cold snare'))]),
        event('E3', ['S7'], 'removed', 'was not removed', 'snare', neg('performed', src(['S7'], 'was not removed')),
              session=[fact('X1', src(['S7']))],
              scope__breadth=[fact('single_target', src(['S7'], 'The 6 mm cecal polyp'))],
              target__lesion=[fact('L1', src(['S7'], 'The 6 mm cecal polyp'))])],
        fact('E1', src(['S4'])),
        lesions=[lesion('L1', ['S5'], 'A 6 mm polyp', places=[fact('cecum', src(['S5'], 'cecum'))]),
                 lesion('L2', ['S6'], 'A second polyp', places=[fact('sigmoid_colon', src(['S6'], 'sigmoid colon'))],
                        distinct_from=[fact('L1', src(['S6'], 'A second polyp'))])])


def merged(claim_set):
    """The pair controls numbered into a contrary control (refute-r2c-r1 RF1, RF2): settle stores such a claim with role
    control, and the engine's FactSet reads no pair control from it."""
    controls = {item.control for item in claim_set.appraised if item.control is not None}
    return [pair for pair in claim_set.pair_controls if pair.claim in controls]


def frame_answer(family, events, examination=None, lesions=()):
    """A one-part note's answer (the opening part N0 and a Findings part N1 at S4, today, the team) with one session X1
    of ``family``, its kind told by the document frame."""
    today = fact('on_date_of_service', src(['S2'], '', 'document_frame'))
    return answer(sections=[section('N0', src([], '', 'section'), occasion=[today]),
                            section('N1', src(['S4'], 'Findings:', 'section'), occasion=[today],
                                    performer=[fact('documenting_team', src(['S3'], '', 'document_frame'))])],
                  sessions=[session('X1', family, src(['S1'], '', 'document_frame'), examination)],
                  events=list(events), lesions=list(lesions))


def overlap(name):
    """The note and the answer of one OVERLAPS case: its act E2 at S5, of its session X1."""
    (kind_word, exam), act, kind, kind_words, status_words, family, over = OVERLAPS[name]
    text = OVERLAP_NOTE.format(kind=kind_word, exam=exam, act=act)
    return text, frame_answer(family, [event('E2', ['S5'], kind_words, status_words, kind,
                                             session=[fact('X1', src(['S5']))], **over)])


def examination(eid='E1', unit='S4', words='scope'):
    return event(eid, [unit], words, 'was advanced', 'examination', session=[fact('X1', src([unit]))])


def exchange_answer():
    """EXCHANGE's answer: the ERCP's examination E1 and the exchange told as its parts, the removal E2 and the
    placement E3, sharing the anchor S5 (2a's composite-act rule)."""
    return frame_answer('ercp', [
        examination(words='duodenoscope'),
        event('E2', ['S5'], 'stent was removed', 'was removed', 'stent_removal', session=[fact('X1', src(['S5']))],
              target__duct=[fact('biliary', src(['S5'], 'biliary'))]),
        event('E3', ['S5'], 'replaced with a new plastic stent', 'replaced', 'stent',
              session=[fact('X1', src(['S5']))], target__duct=[fact('biliary', src(['S5'], 'biliary'))])],
        fact('E1', src(['S4'])))


# Each device's contrary (DEVICE_CONTRARY, D213) with the reason its control is false of every act done with the
# device (DECISIONS D222: never a device whose physics an act done with the device includes). "carried": the document
# says neither way, so a faithful reading answers unclear and the device stays unresolved (2c3's question Q3, carried by
# this step's NOTES: fail-closed, it can only hold).
DEVICE_AUDIT = {
    Device.COLD_SNARE: 'a cold snare cuts with no current', Device.HOT_SNARE: 'a hot snare cuts with current',
    Device.SNARE: 'carried: the document calls the snare neither cold nor hot',
    Device.COLD_FORCEPS: 'cold forceps take tissue with no current', Device.HOT_FORCEPS: 'hot forceps use current',
    Device.FORCEPS: 'carried: the document calls the forceps neither cold nor hot',
    Device.BALLOON: "3.2.3's pair, a statement's: a balloon is no bougie passed over a wire",
    Device.WIRE_BOUGIE: "3.2.3's pair: bougies passed over a wire are no balloon",
    Device.ENDOSCOPE: "an act done with the endoscope uses no capsule (a capsule's delivery is its own act)",
    Device.CAPSULE: 'a capsule study passes no endoscope (an endoscopic delivery is its own session)',
    Device.NEEDLE: 'a needle ligates nothing', Device.INJECTION: 'an injection ligates nothing',
    Device.CLIP: 'a clip is no band', Device.BAND: 'a band is no clip', Device.BOUGIE: 'a bougie is no balloon',
    Device.ARGON_PLASMA: ('replaced (D222, P5): argon plasma coagulation delivers high-frequency current, so '
                          'radiofrequency energy was true of it; it never freezes'),
    Device.RADIOFREQUENCY: 'radiofrequency energy is delivered by electrodes, never through ionised argon',
    Device.CRYOTHERAPY: 'cryotherapy freezes; it delivers no argon plasma',
    Device.THERMAL_PROBE: 'a thermal probe heats; it never freezes', Device.ELECTROCAUTERY: 'current heats; it never '
                                                                                          'freezes',
    Device.STENT: 'a stent ligates nothing', Device.BASKET: 'a basket cuts nothing',
    Device.EXTRACTION_BALLOON: 'an extraction balloon cuts nothing', Device.SPHINCTEROTOME: 'a sphincterotome is no '
                                                                                            'basket',
    Device.LITHOTRIPTER: 'a lithotripter cuts nothing', Device.CHOLANGIOSCOPE: 'a cholangioscope cuts nothing',
    Device.CATHETER: 'a catheter is no basket', Device.MANUAL: 'manual pressure places no clip',
    Device.OTHER: 'a device of another kind is no band (a band is named)',
}


def roles_of(claim_set):
    """What each claim of a request is (pass 2 never sees it): a real claim (claim or completeness), else a control."""
    real = {item.claim for item in claim_set.appraised} | {complete.claim for complete in claim_set.completeness}
    return {claim.id: claim.id in real for claim in claim_set.claims}


def faithful_oracle(true_of=frozenset(), places=None):
    """A faithful second reading of a well-filed answer: every real claim supported, every control contradicted, each
    attached with its first unit as evidence - except a sentence in ``true_of`` (a sentence true of its act, which a
    faithful reader supports, whatever it is), and a pair control, which ``places`` answers by the asked object's true
    places (supported exactly when the place is one of them), where it is given."""
    def oracle(claim, real, claim_set):
        supports = real or claim_set.sentences[claim.id] in true_of
        if places is not None:
            for pair in claim_set.pair_controls:
                if pair.claim == claim.id:
                    supports = pair.value in places[pair.subject[1]]
        return {'claim': claim.id, 'verdict': 'supports' if supports else 'contradicts', 'attached': 'yes',
                'qualifiers': [], 'evidence': list(claim.units[:1])}
    return oracle


def settled(text, data, oracle=None):
    """The rulings' outcomes end to end: pass 1's answer read, checked (contract/checks.check), claimed into the request
    (appraise_prompt.build_request, under the pins this tree measures), appraised by ``oracle`` (faithful_oracle()),
    read (appraise_read), settled (contract/settle, under its own health pin), stored and loaded (store.row_v2,
    load_v2) and read into the engine's FactSet (engine/facts over store.textfree_v2). Returns the claim set, the
    settled inventory and the FactSet."""
    from studio.interpretation import store
    from studio.interpretation.contract import appraise_read, checks, settle
    from studio.interpretation.engine import facts as engine_facts
    found = read(text, data)
    checked = checks.check(text, (), found)
    pins = {name: value for name, value in appraise_prompt.pins().items() if name != 'APPRAISAL_LOCAL_SCHEMA_SHA256'}
    with mock.patch.multiple(interpretation, **pins):
        request = appraise_prompt.build_request(text, (), 'txt', found, findings=checked.findings)
    claim_set = request.claim_set
    roles, answer_of = roles_of(claim_set), oracle or faithful_oracle()
    verdicts = [answer_of(claim, roles[claim.id], claim_set) for claim in claim_set.claims]
    appraisal = appraise_read.read(json.dumps({'verdicts': verdicts, 'unlisted': []}), claim_set,
                                   len(appraise_prompt.segment.units(text)))
    assert not isinstance(appraisal, extract_read.Refusal), appraisal
    usage = settle.Usages(settle.usage_of({'promptTokenCount': 1800, 'candidatesTokenCount': 900}),
                          settle.usage_of({'promptTokenCount': 2600, 'candidatesTokenCount': 480}))
    with mock.patch.object(interpretation, 'HEALTH_THRESHOLDS_SHA256',
                           jsonschema.sha256_of(settle.health_document())):
        out = settle.settle(found, checked, claim_set, request.indistinct, appraisal, usage)
    assert isinstance(out, settle.Settled), out
    sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
    ids = ('4' * 32, '5' * 32, '6' * 32, '7' * 32)
    fields = store.row_v2(encounter_id=ids[0], revision_id=ids[1], provider_run_id=ids[2], appraisal_run_id=ids[3],
                          revision_text=text, text_sha256=sha, request_sha256='2' * 64, response_sha256='3' * 64,
                          appraisal_request_sha256='8' * 64, appraisal_response_sha256='9' * 64, events=out.events,
                          verification=out.verification)
    loaded = store.load_v2(fields, text_sha256=sha, response_sha256='3' * 64, appraisal_response_sha256='9' * 64)
    return claim_set, out.events, engine_facts.factset(store.textfree_v2(loaded))


def at(events, name, attribute, *index):
    """The settled fact of event ``name``'s ``attribute`` (a scope list's member at ``index``)."""
    node = next(record for record in events['events'] if record['id'] == name)
    for part in attribute.value.split('.'):
        node = node[part]
    return node[index[0]] if index else node


def relation(factset, statement, act):
    """engine/pairing's relation of a statement and an act (E<n> ids)."""
    from studio.interpretation.engine import pairing
    from studio.interpretation.engine.types import Id, IdFamily
    return pairing.relation(factset, Id(IdFamily.EVENT, int(statement[1:])), Id(IdFamily.EVENT, int(act[1:])))


class OverlapTests(SimpleTestCase):
    """DECISIONS D222: the control audit extends from genus to overlap - a sibling control is false of every act the
    claim's kind admits, the acts done by the sibling's method, holding it as a step and using a device whose physics
    includes the sibling's included."""

    def kind_of(self, name, subject='E2', attribute=A.KIND):
        text, data = overlap(name)
        claim_set = build(text, data)
        (item,) = appraised(claim_set, attribute, subject)
        return claim_set, sentence_of(claim_set, item.claim), sentence_of(claim_set, item.control)

    def test_an_ablations_control_is_a_treatment_of_bleeding_present_at_this_encounter(self):
        # DECISIONS D233 (refute-r2c-r2 G1): the clip placement refute-r2c-r1's RF3 gave an ablation is false of every
        # ablation, so it let an oozing lesion's treatment filed as an ablation settle its kind supported (a false
        # READY). The control is the bleeding control again, its label narrowed to the hemostasis purpose's own wording:
        # false of RF3's vascular ectasia ablated (no bleeding stated at this encounter), true of a treatment of
        # bleeding present at this encounter, which the control holds
        claim_set, claim, control = self.kind_of('P5 argon plasma')
        self.assertEqual((claim, control), ('This act is an ablation of tissue.',
                                            'This act is a treatment of bleeding present at this encounter.'))
        self.assertIs(claims.KIND_SIBLINGS[Kind.ABLATION], Kind.BLEEDING_CONTROL)
        self.assertNotIn('This act is a clip placement.', sentences_of_controls(claim_set))
        self.assertNotIn('This act is a treatment of bleeding.', sentences(claim_set))  # the unnarrowed label: gone
        # the hemostasis purpose's own wording, the article's form; the bare and plural forms carry it in parentheses
        self.assertEqual(claims.KIND_LABELS[Kind.BLEEDING_CONTROL],
                         ('treatment of bleeding (present at this encounter)',
                          'a ' + claims.LABELS[claims.Purpose.HEMOSTASIS],
                          'treatments of bleeding (present at this encounter)'))
        # the bleeding control's own claim reads the same label (the cost D233 accepts), and its control stays the
        # dilation (D222, P4)
        claim_set, claim, control = self.kind_of('P4 clips')
        self.assertEqual((claim, control), ('This act is a treatment of bleeding present at this encounter.',
                                            'This act is a dilation of a narrowing.'))
        # the pair kinds follow the sibling (_compatible): an ablation and a bleeding control pair both ways, an
        # ablation and a clip no longer
        kinds = claims.controls_document()['pair_controls']['pair_kinds']
        self.assertLessEqual([['ablation', 'bleeding_control'], ['bleeding_control', 'ablation']],
                             [pair for pair in kinds if 'ablation' in pair and 'bleeding_control' in pair])
        self.assertNotIn(['ablation', 'clip'], kinds)
        self.assertNotIn(['clip', 'ablation'], kinds)

    def test_each_overlap_the_refutation_named_takes_a_contrary_its_kind_never_is(self):
        # P4: "a clip placement" was true of a bleed treated with clips (pass 1's "treatment of bleeding by any
        # method"); P2: "a fine-needle aspiration or biopsy" true of a drainage's needle puncture and aspiration; P5:
        # radiofrequency energy true of argon plasma coagulation's high-frequency current; P6: the sedation control was
        # false of the examination, a procedure on the patient
        expected = {
            ('P4 clips', A.KIND): ('This act is a treatment of bleeding present at this encounter.',  # D233's label
                                   'This act is a dilation of a narrowing.'),
            ('P2 needle', A.KIND): ('This act is a drainage.', 'This act is a band ligation.'),
            ('P5 argon plasma', A.TECHNIQUE_DEVICE): ('This act used argon plasma coagulation.',
                                                      'This act used cryotherapy.'),
            ('P6 sedation', A.KIND): ('This act is moderate sedation.', 'This act is the examination itself or an '
                                                                        'intervention of any kind, other than '
                                                                        'sedation.')}
        gone = {'P4 clips': 'This act is a clip placement.', 'P2 needle': 'This act is a fine-needle aspiration or '
                                                                           'biopsy.',
                'P5 argon plasma': 'This act used radiofrequency energy.',
                'P6 sedation': 'This act is an intervention of any kind other than sedation.'}
        for (name, attribute), sentences in expected.items():
            with self.subTest(overlap=name):
                claim_set, claim, control = self.kind_of(name, attribute=attribute)
                self.assertEqual((claim, control), sentences)
                self.assertNotIn(gone[name], sentences_of_controls(claim_set))

    def test_the_further_overlaps_the_audit_found(self):
        # a stent placement includes its pre- and post-dilation; the destruction of calculi includes removing the
        # fragments; a fine-needle biopsy may be taken with forceps through the needle; a pH study may hold the
        # manometric location of its sphincter - each made the old control true of a correct filing
        expected = {'audit stent': ('This act is a stent placement.', 'This act is a stent removal (the removal alone, '
                                                                       'even where a new stent is then placed).'),
                    'audit lithotripsy': ('This act is a lithotripsy.', 'This act is a sphincterotomy.'),
                    'audit microforceps': ('This act is a fine-needle aspiration or biopsy.',
                                           'This act is an injection that does not mark a site.'),
                    'audit pH': ('This act is a pH monitoring study.',
                                 'This act is a pressure measurement of the sphincter of Oddi.')}
        for name, sentences in expected.items():
            with self.subTest(overlap=name):
                self.assertEqual(self.kind_of(name)[1:], sentences)
        # and the pH study's session: anorectal testing, never motility, part of whose label it was
        claim_set, claim, control = self.kind_of('audit pH', 'X1')
        self.assertEqual((claim, control), ('Session X1 is a pH or impedance monitoring study.',
                                            'Session X1 is an anorectal test.'))

    def test_the_parts_of_an_exchange_and_a_replacement_read_plainly_true(self):
        # P3 (option (a)): the removal part and the placement part, each told as its own act, read plainly true; the
        # whole exchange and the whole replacement are false of their siblings' labels ("alone")
        claim_set = build(EXCHANGE, exchange_answer())
        by = {item.key.object: item for item in claim_set.appraised if item.key.attribute is A.KIND}
        self.assertEqual(sentence_of(claim_set, by['E2'].claim),
                         'This act is a stent removal (the removal alone, even where a new stent is then placed).')
        self.assertEqual(sentence_of(claim_set, by['E3'].claim), 'This act is a stent placement.')
        self.assertEqual(sentence_of(claim_set, by['E2'].control), 'This act is a stent placement.')
        tube = frame_answer('egd', [examination(words='gastroscope'),
                                    event('E2', ['S5'], 'a new one was placed in the jejunum', 'was placed',
                                          'tube_placement', session=[fact('X1', src(['S5']))])],
                            fact('E1', src(['S4'])))
        claim_set = build(TUBE, tube)
        (kind,) = appraised(claim_set, A.KIND, 'E2')
        self.assertEqual(sentence_of(claim_set, kind.claim), 'This act is a tube placement other than a gastrostomy '
                                                             '(the placement alone, even where it replaces an earlier '
                                                             'tube).')
        for whole, part in ((Kind.STENT_EXCHANGE, Kind.STENT_REMOVAL), (Kind.TUBE_REPLACEMENT, Kind.TUBE_PLACEMENT)):
            self.assertIs(claims.KIND_SIBLINGS[whole], part)
            self.assertIn('alone', claims.KIND_LABELS[part][1])

    def test_moderate_sedations_control_names_every_procedure_and_is_never_a_real_claim(self):
        # P6: true of every procedure on the patient, the examination included, and false of sedation; the form is
        # moderate sedation's control alone, since K1 demotes the kind of an act filed as the intervention umbrella
        article = claims.KIND_LABELS[Kind.INTERVENTION][1]
        self.assertTrue(article.startswith('the examination itself'))  # the examination, as its own label begins
        self.assertTrue(claims.KIND_LABELS[Kind.EXAMINATION][1].startswith('the examination itself'))
        self.assertIn('an intervention of any kind', article)  # every member of the umbrella (catalogue)
        self.assertTrue(article.endswith('other than sedation'))
        self.assertEqual(claims.KIND_SIBLINGS[Kind.MODERATE_SEDATION], Kind.INTERVENTION)
        # the statement forms keep the interventions a statement about interventions concerns
        self.assertEqual(claims.KIND_LABELS[Kind.INTERVENTION][2], 'interventions of any kind (not sedation)')
        from studio.interpretation.contract import checks
        data = frame_answer('colonoscopy', [examination(words='colonoscope'),
                                            event('E2', ['S5'], 'Interventions', 'were performed', 'intervention',
                                                  session=[fact('X1', src(['S5']))])], fact('E1', src(['S4'])))
        found = read(UMBRELLA, data)
        findings = checks.check(UMBRELLA, (), found).findings
        self.assertIn(Reason.STRUCTURE_UMBRELLA, findings[FactKey(F.EVENT, 'E2', A.KIND, 0)])
        claim_set = build(UMBRELLA, data, findings)
        self.assertEqual(appraised(claim_set, A.KIND, 'E2'), [])
        self.assertNotIn(f'This act is {article}.', sentences(claim_set))

    def test_every_device_contrary_is_audited(self):
        self.assertEqual(set(DEVICE_AUDIT), set(claims.DEVICE_CONTRARY))
        self.assertIs(claims.DEVICE_CONTRARY[Device.ARGON_PLASMA], Device.CRYOTHERAPY)
        for device, reason in DEVICE_AUDIT.items():
            with self.subTest(device=device.value):
                self.assertTrue(reason)
                self.assertEqual(reason.startswith('carried'), device in (Device.SNARE, Device.FORCEPS))
                self.assertEqual(reason.startswith('replaced (D222'), device is Device.ARGON_PLASMA)


def sentences_of_controls(claim_set):
    return {claim_set.sentences[claim_id] for claim_id in claim_set.controls}


class OneSentenceTests(SimpleTestCase):
    """DECISIONS D223: each fact a shared sentence tells has its own claim of it, with its own control (so each fact has
    one appraisal and the store reads every claim for one fact), and a segment's pair controls ask its whole range."""

    def test_each_excepted_act_has_its_own_claim_and_covers_control(self):
        # 3a's Q-A: the breadth and each excepted act of "No other polyps were removed." their own claims of the one
        # exceptive sentence, each act's control the covers form naming it; the breadth keeps its all_of_kind control
        data = frame_answer('colonoscopy', [
            examination(words='colonoscope'),
            event('E2', ['S5'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S5']))],
                  target__places=[fact('rectum', src(['S5'], 'rectum'))]),
            event('E3', ['S6'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S6']))],
                  target__places=[fact('sigmoid_colon', src(['S6'], 'sigmoid colon'))]),
            event('E4', ['S7'], 'removed', 'No other polyps were removed', 'removal',
                  neg('performed', src(['S7'], 'No other polyps were removed')), session=[fact('X1', src(['S7']))],
                  scope__breadth=[fact('exceptive', src(['S7'], 'No other polyps'))], scope__excepts=['E2', 'E3'])],
            fact('E1', src(['S4'])))
        claim_set = build(POLYPS, data)
        (breadth,) = appraised(claim_set, A.SCOPE_BREADTH, 'E4')
        excepted = sorted(appraised(claim_set, A.SCOPE_EXCEPTS, 'E4'), key=lambda item: item.key.index)
        self.assertEqual([item.value for item in excepted], ['E2', 'E3'])
        exceptive = 'This statement denies only removals by any method other than acts A2 and A3.'
        self.assertEqual({sentence_of(claim_set, item.claim) for item in [breadth, *excepted]}, {exceptive})
        self.assertEqual(len({item.claim for item in [breadth, *excepted]}), 3)
        self.assertEqual([claim_set.claim(item.claim).value for item in [breadth, *excepted]],
                         ['exceptive', 'E2', 'E3'])
        self.assertEqual([sentence_of(claim_set, item.control) for item in excepted],
                         ['This statement applies to act A2.', 'This statement applies to act A3.'])
        self.assertEqual(sentence_of(claim_set, breadth.control),
                         'This statement says no removal by any method at all was done in session X1.')
        no_claim_or_control_read_twice(self, claim_set)

    def test_each_place_of_a_segment_has_its_own_claim_and_control(self):
        claim_set = build(SEGMENT, segment_answer(('descending_colon', 'rectum')))
        members = sorted(appraised(claim_set, A.SCOPE_SEGMENT, 'E2'), key=lambda item: item.key.index)
        self.assertEqual([claim_set.claim(item.claim).value for item in members], ['descending_colon', 'rectum'])
        self.assertEqual({sentence_of(claim_set, item.claim) for item in members},
                         {'This statement is about tissue samplings with forceps (not hot forceps) from the descending '
                          'colon to the rectum.'})
        self.assertEqual(len({item.claim for item in members}), 2)
        self.assertEqual(len({item.control for item in members}), 2)
        no_claim_or_control_read_twice(self, claim_set)

    def test_a_whole_tract_segment_leaves_both_places_unclaimed(self):
        # refute-r2c-r1 RF6: from the proximal esophagus to the anal canal one candidate only lies outside the whole
        # range (the liver), so the segment's last place has no control of its own: it is not claimed (CONTROL), and its
        # first place goes with it (PARTNER), their claims telling one sentence - never the last place with the first
        # place's control, which two facts would then read
        (only,) = claims.contrasts(claims.contrast_candidates([Landmark.PROXIMAL_ESOPHAGUS, Landmark.ANAL_CANAL]),
                                   claims.segment_range(Landmark.PROXIMAL_ESOPHAGUS, Landmark.ANAL_CANAL))
        self.assertIs(only, Landmark.LIVER)
        claim_set = build(WHOLE_TRACT, segment_answer(('proximal_esophagus', 'anal_canal')))
        self.assertEqual(appraised(claim_set, A.SCOPE_SEGMENT, 'E2'), [])
        self.assertEqual(sorted((item.key.index, item.why) for item in claim_set.unclaimed
                                if (item.key.object, item.key.attribute) == ('E2', A.SCOPE_SEGMENT)),
                         [(0, claims.Unclaimable.PARTNER), (1, claims.Unclaimable.CONTROL)])
        self.assertNotIn('This statement is about tissue samplings with forceps (not hot forceps) in the liver.',
                         sentences(claim_set))
        no_claim_or_control_read_twice(self, claim_set)

    def test_a_segments_pair_controls_ask_its_whole_range(self):
        # 3d's R4 (w34 O14): the biopsy is asked about every place of the range from the cecum to the hepatic flexure
        # (its two ends and the three places between them), and the denial about the biopsy's place - not only about
        # the range's two ends
        data = frame_answer('colonoscopy', [
            examination(words='colonoscope'),
            event('E2', ['S5'], 'Biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S5']))],
                  target__places=[fact('sigmoid_colon', src(['S5'], 'Biopsies'))]),
            event('E3', ['S6'], 'biopsies', 'No biopsies were taken', 'biopsy',
                  neg('performed', src(['S6'], 'No biopsies were taken')), session=[fact('X1', src(['S6']))],
                  scope__breadth=[fact('segment', src(['S6'], 'from the cecum to the hepatic flexure'))],
                  scope__segment=['cecum', 'hepatic_flexure'])], fact('E1', src(['S4'])))
        claim_set = build(SEGMENT_RANGE, data)
        asked = {(pair.subject[1], pair.value) for pair in claim_set.pair_controls}
        whole = claims.segment_range(Landmark.CECUM, Landmark.HEPATIC_FLEXURE)
        self.assertEqual(len(whole), 5)
        self.assertEqual(asked, {('E2', place.value) for place in whole} | {('E3', 'sigmoid_colon')})
        # a place the biopsy names inside the range is never asked of it (its own place)
        data['events'][1]['target']['places'] = [fact('ascending_colon', src(['S5'], 'Biopsies'))]
        asked = {(pair.subject[1], pair.value) for pair in build(SEGMENT_RANGE, data).pair_controls}
        self.assertEqual(asked, {('E2', place.value) for place in whole if place is not Landmark.ASCENDING_COLON})

    def test_no_claim_or_control_is_read_by_two_facts_in_any_note(self):
        cases = {'NOTE': (NOTE, note_answer()), 'RICH': (RICH, rich_answer()), 'EUS': (EUS, eus_answer()),
                 'PAIRS': (PAIRS, pairs_answer()), 'EXCHANGE': (EXCHANGE, exchange_answer()),
                 'SEGMENT': (SEGMENT, segment_answer(('cecum', 'rectum'))),
                 'LISTED': (LISTED, listed_answer(['L1'])),
                 # D234: two listed targets, with a fourth polyp and without
                 'LISTED_FOURTH': (LISTED_FOURTH, listed_polyps_answer(fourth=True)),
                 'LISTED_TWO': (LISTED_TWO, listed_polyps_answer()),
                 **{f'OVERLAP {name}': overlap(name) for name in OVERLAPS}}
        # one collision stays, of another shape than D223's (the step's NOTES, a question): a statement that names one
        # lesion both as its target lesion and as a listed target renders one sentence with one value for both facts,
        # so one content key and one claim; the store reads it for one of them, and the other settles unappraised
        # (fail-closed)
        twice = build(LISTED, listed_answer(['L1', 'L2']))
        groups = {}
        for item in twice.appraised:
            groups.setdefault(item.claim, []).append((item.key.attribute, item.key.index))
        self.assertEqual([found for found in groups.values() if len(found) > 1],
                         [[(A.TARGET_LESION, 0), (A.SCOPE_TARGETS, 1)]])
        exceptive = rich_answer()
        exceptive['events'][7]['scope']['breadth'] = [fact('exceptive', src(['S14'], 'No biopsies'))]
        exceptive['events'][7]['scope']['excepts'] = ['E6']
        cases['RICH exceptive'] = (RICH, exceptive)
        adjunct = note_answer()
        adjunct['events'][1]['part_of'] = [fact('E1', src(['S6'], 'was removed'))]
        adjunct['events'][1]['part_relation'] = [fact('step_of', src(['S6'], 'was removed'))]
        cases['NOTE part_of'] = (NOTE, adjunct)
        for name, (text, data) in cases.items():
            with self.subTest(note=name):
                no_claim_or_control_read_twice(self, build(text, data))


def no_claim_or_control_read_twice(case, claim_set):
    """The store's rule (store._v2_verdicts_bound): no claim, and no control, is read by two facts."""
    claim_ids = [item.claim for item in claim_set.appraised]
    control_ids = [item.control for item in claim_set.appraised if item.control is not None]
    case.assertEqual(len(claim_ids), len(set(claim_ids)))
    case.assertEqual(len(control_ids), len(set(control_ids)))
    case.assertFalse(set(claim_ids) & set(control_ids))


class RulingOutcomeTests(SimpleTestCase):
    """The outcomes D222 and D223 state, end to end: read, checks, claims, a pass 2 that reads the document, settle,
    the store and the engine's FactSet (settled)."""

    def test_an_excepted_act_is_set_apart_by_its_own_claim(self):
        # D223 (3a Q-A, FINAL-V2 4.5's BF17): with the excepted act's own claim and covers control established it
        # settles supported, and the pairing sets the denial apart from it (row breadth), for one excepted act and two
        bf17 = frame_answer('colonoscopy', [
            examination(words='colonoscope'),
            event('E2', ['S5'], 'injection', 'was tattooed', 'injection', session=[fact('X1', src(['S5']))],
                  target__places=[fact('sigmoid_colon', src(['S5'], 'sigmoid colon'))]),
            event('E3', ['S6'], 'injection', 'No other injection was given', 'injection',
                  neg('performed', src(['S6'], 'No other injection was given')), session=[fact('X1', src(['S6']))],
                  scope__breadth=[fact('exceptive', src(['S6'], 'No other injection'))], scope__excepts=['E2'])],
            fact('E1', src(['S4'])))
        polyps = frame_answer('colonoscopy', [
            examination(words='colonoscope'),
            event('E2', ['S5'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S5']))],
                  target__places=[fact('rectum', src(['S5'], 'rectum'))]),
            event('E3', ['S6'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S6']))],
                  target__places=[fact('sigmoid_colon', src(['S6'], 'sigmoid colon'))]),
            event('E4', ['S7'], 'removed', 'No other polyps were removed', 'removal',
                  neg('performed', src(['S7'], 'No other polyps were removed')), session=[fact('X1', src(['S7']))],
                  scope__breadth=[fact('exceptive', src(['S7'], 'No other polyps'))], scope__excepts=['E2', 'E3'])],
            fact('E1', src(['S4'])))
        for name, text, data, denial, acts in (('BF17', INJECTION_BF17, bf17, 'E3', ('E2',)),
                                               ('two snares', POLYPS, polyps, 'E4', ('E2', 'E3'))):
            with self.subTest(note=name):
                _claim_set, events, factset = settled(text, data)
                self.assertEqual(at(events, denial, A.SCOPE_BREADTH).result.value, 'supported')
                for index, act in enumerate(acts):
                    member = at(events, denial, A.SCOPE_EXCEPTS, index)
                    self.assertEqual((member.result.value, member.claim.value), ('supported', act))
                    pair = relation(factset, denial, act)
                    self.assertEqual((pair.relation.value, pair.row.value), ('independent', 'breadth'))

    def test_a_segment_pairs_independent_once_its_whole_range_is_rejected(self):
        # D223 (3d's R4): "No biopsies were taken from the cecum to the hepatic flexure." beside a biopsy truly and only
        # in the sigmoid colon pairs INDEPENDENT once its controls are rejected; truly inside the range, the two
        # conflict; and the short list (truly in the sigmoid and the ascending colon, filed with the sigmoid alone) is
        # never set apart, since the biopsy's pair control about the ascending colon is supported
        whole = {place.value for place in claims.segment_range(Landmark.CECUM, Landmark.HEPATIC_FLEXURE)}

        def note(filed):
            return frame_answer('colonoscopy', [
                examination(words='colonoscope'),
                event('E2', ['S5'], 'Biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S5']))],
                      target__places=[fact(place, src(['S5'], 'Biopsies')) for place in filed]),
                event('E3', ['S6'], 'biopsies', 'No biopsies were taken', 'biopsy',
                      neg('performed', src(['S6'], 'No biopsies were taken')), session=[fact('X1', src(['S6']))],
                      scope__breadth=[fact('segment', src(['S6'], 'from the cecum to the hepatic flexure'))],
                      scope__segment=['cecum', 'hepatic_flexure'])], fact('E1', src(['S4'])))

        for name, filed, truth, expected in (
                ('outside the range', ['sigmoid_colon'], {'sigmoid_colon'}, ('independent', 'target')),
                ('inside the range', ['ascending_colon'], {'ascending_colon'}, ('contradiction', None)),
                ('a short list', ['sigmoid_colon'], {'sigmoid_colon', 'ascending_colon'}, ('unresolved', 'target'))):
            with self.subTest(biopsy=name):
                _claim_set, events, factset = settled(SEGMENT_RANGE, note(filed),
                                                      faithful_oracle(places={'E2': truth, 'E3': whole}))
                for index in (0, 1):
                    self.assertEqual(at(events, 'E3', A.SCOPE_SEGMENT, index).result.value, 'supported')
                pair = relation(factset, 'E3', 'E2')
                self.assertEqual((pair.relation.value, pair.row.value if pair.row else None), expected)

    def test_part_relation_is_established_by_its_own_claim(self):
        # D223 (O6's third item): "A clip was placed on the polypectomy site." filed as an adjunct of the snare removal:
        # part_relation is established, so a bundling explanation can read it
        data = frame_answer('colonoscopy', [
            examination(words='colonoscope'),
            event('E2', ['S5'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S5']))],
                  target__places=[fact('cecum', src(['S5'], 'cecum'))]),
            event('E3', ['S6'], 'clip', 'was placed', 'clip', session=[fact('X1', src(['S6']))],
                  part_of=[fact('E2', src(['S6'], 'polypectomy site'))],
                  part_relation=[fact('adjunct_of', src(['S6'], 'placed on the polypectomy site'))])],
            fact('E1', src(['S4'])))
        _claim_set, events, _factset = settled(ADJUNCT, data)
        self.assertEqual((at(events, 'E3', A.PART_OF).result.value, at(events, 'E3', A.PART_RELATION).result.value),
                         ('supported', 'supported'))

    def test_an_overlapping_act_is_established_by_a_reader_who_sees_the_overlap(self):
        # D222: a pass 2 that supports what is true of each act - "a clip placement" of the bleed treated with clips,
        # "a fine-needle aspiration or biopsy" of the drainage's needle step, "radiofrequency energy" of argon plasma
        # coagulation - no longer meets it as a control, so each fact settles supported (it was control_incoherent)
        for name, attribute, true_of in (
                ('P4 clips', A.KIND, {'This act is a clip placement.'}),
                ('P2 needle', A.KIND, {'This act is a fine-needle aspiration or biopsy.'}),
                ('P5 argon plasma', A.TECHNIQUE_DEVICE, {'This act used radiofrequency energy.'})):
            with self.subTest(overlap=name):
                text, data = overlap(name)
                _claim_set, events, _factset = settled(text, data, faithful_oracle(frozenset(true_of)))
                self.assertEqual(at(events, 'E2', attribute).result.value, 'supported')
        # and P5 in the pairing: the argon plasma ablation beside "No radiofrequency ablation was performed." is set
        # apart by its technique
        data = frame_answer('egd', [
            examination(words='gastroscope'),
            event('E2', ['S5'], 'ablated', 'was ablated', 'ablation', session=[fact('X1', src(['S5']))],
                  target__places=[fact('gastric_antrum', src(['S5'], 'antral'))],
                  technique__device=[fact('argon_plasma', src(['S5'], 'argon plasma coagulation'))]),
            event('E3', ['S6'], 'radiofrequency ablation', 'No radiofrequency ablation was performed', 'ablation',
                  neg('performed', src(['S6'], 'No radiofrequency ablation was performed')),
                  session=[fact('X1', src(['S6']))],
                  scope__breadth=[fact('all_of_kind', src(['S6'], 'No radiofrequency ablation'))],
                  technique__device=[fact('radiofrequency', src(['S6'], 'radiofrequency'))])],
            fact('E1', src(['S4'])))
        _claim_set, events, factset = settled(APC, data, faithful_oracle(frozenset({'This act used radiofrequency '
                                                                                    'energy.'})))
        pair = relation(factset, 'E3', 'E2')
        self.assertEqual((pair.relation.value, pair.row.value), ('independent', 'technique'))

    def test_an_ablation_with_no_bleeding_stated_is_established_and_its_code_ready(self):
        # DECISIONS D233 (refute-r2c-r1 RF3): "The antral vascular ectasia was ablated with argon plasma coagulation." -
        # a reader who calls the ablation of a lesion that bleeds chronically, in plain words, "a treatment of
        # bleeding" (RF3's reader, whose sentence no claim asks any more) rejects "a treatment of bleeding present at
        # this encounter", since the document states no bleeding at this encounter: the kind settles supported and
        # 43270 is READY; and so is each family's ablation code for an angioectasia ablated with no bleeding stated
        rf3 = faithful_oracle(frozenset({'This act is a treatment of bleeding.'}))
        cases = [('egd, RF3', *overlap('P5 argon plasma'), '43270')]
        cases += [(name, *angioectasia(name, oozing=False), row[6]) for name, row in ANGIOECTASIA.items()]
        self.assertEqual(sorted(code for *_rest, code in cases), ['43229', '43270', '43270', '44369', '45346', '45388'])
        for name, text, data, code in cases:
            with self.subTest(case=name):
                claim_set, events, factset = settled(text, data, rf3)
                status, evaluation = decided(code, factset)  # the outcome first, then how it was reached
                self.assertEqual((at(events, 'E2', A.KIND).result.value, status,
                                  [str(act) for act in evaluation.supporting]), ('supported', 'READY', ['E2']))
                (kind,) = appraised(claim_set, A.KIND, 'E2')
                self.assertEqual(sentence_of(claim_set, kind.control), BLEEDING_HERE)

    def test_an_oozing_lesion_filed_as_an_ablation_is_held_with_one_question(self):
        # DECISIONS D233 (refute-r2c-r2 G1, its probe p02): "An oozing angioectasia in the gastric antrum was treated
        # with argon plasma coagulation." filed as an ablation, its purpose hemostasis (pass 1's ablation and its
        # bleeding control both admit it). Its kind's control is the narrowed bleeding control, which a faithful reader
        # supports of a treatment of bleeding present at this encounter: the kind stays unresolved (control_incoherent)
        # and 43270 and 43255 are held by one question, the act's kind - where the clip placement's control let the
        # kind settle supported and 43270 go READY. The same for 43229, 45388, 44369 and 45346 with their families'
        # bleeding-control codes
        from studio.interpretation.engine.types import Id, IdFamily, ItemKind
        for name, row in ANGIOECTASIA.items():
            ablation, bleeding = row[6], row[7]
            with self.subTest(family=name):
                text, data = angioectasia(name, oozing=True)
                claim_set, events, factset = settled(text, data, faithful_oracle(frozenset({BLEEDING_HERE})))
                # the outcome first: both codes held, and the act's kind unresolved
                outcomes = {code: decided(code, factset) for code in (ablation, bleeding)}
                found = at(events, 'E2', A.KIND)
                statuses = {code: (status, evaluation.supporting) for code, (status, evaluation) in outcomes.items()}
                self.assertEqual((statuses, found.result.value, [reason.value for reason in found.reasons]),
                                 ({ablation: ('NEEDS_CLARIFICATION', ()), bleeding: ('NEEDS_CLARIFICATION', ())},
                                  'unresolved', ['control_incoherent']))
                # one question: both codes held by the one fact, the act's kind its control left in doubt
                held = [evaluation.held_facts for _status, evaluation in outcomes.values()]
                self.assertEqual(held[0], held[1])
                (one,) = held[0]
                self.assertEqual((one.fact, one.subject, one.kind, one.cause),
                                 ('performed_status', Id(IdFamily.EVENT, 2), ItemKind.QUESTION,
                                  'appraisal:control_incoherent'))
                # how it was reached: the narrowed control, and the purpose supported
                (kind,) = appraised(claim_set, A.KIND, 'E2')
                self.assertEqual(sentence_of(claim_set, kind.control), BLEEDING_HERE)
                self.assertEqual(at(events, 'E2', A.PURPOSE).result.value, 'supported')

    def test_a_pair_is_set_apart_when_the_nearest_contrast_is_the_other_objects_place(self):
        # refute-r2c-r1 RF1 and RF2, end to end under a faithful pass 2: a segment denial beside a biopsy next to its
        # range (the transverse colon; the terminal ileum), a single target beside the place next to it, and a polyp
        # left in place beside another removed. Each pair control was numbered into a contrary control of the same
        # sentence, stored with role control, so the FactSet held it as no pair control and the pair was never set
        # apart (UNRESOLVED, the code not met). Every pair control the claim set lists now reaches the FactSet
        from studio.interpretation.engine import evaluate
        from studio.interpretation.engine.types import Id, IdFamily
        whole = {place.value for place in claims.segment_range(Landmark.CECUM, Landmark.HEPATIC_FLEXURE)}
        for name, text, data, oracle, code, kind in (
                ('segment, transverse colon', SEGMENT_RANGE,
                 denial_answer(('cecum', 'hepatic_flexure'), ('transverse_colon',), denial_words=RANGE_WORDS),
                 faithful_oracle(places={'E2': {'transverse_colon'}, 'E3': whole}), '45380', Kind.BIOPSY),
                ('segment, terminal ileum', SEGMENT_RANGE,
                 denial_answer(('cecum', 'hepatic_flexure'), ('terminal_ileum',), denial_words=RANGE_WORDS),
                 faithful_oracle(places={'E2': {'terminal_ileum'}, 'E3': whole}), '45380', Kind.BIOPSY),
                ('single target', SINGLE_PLACE,
                 denial_answer(('rectum',), ('sigmoid_colon',), 'sigmoid colon', 'rectum'),
                 faithful_oracle(places={'E2': {'sigmoid_colon'}, 'E3': {'rectum'}}), '45380', Kind.BIOPSY),
                ('two lesions', POLYP_LEFT, polyp_left_answer(), faithful_oracle(), '45385', Kind.SNARE)):
            with self.subTest(case=name):
                claim_set, events, factset = settled(text, data, oracle)
                self.assertEqual(merged(claim_set), [])
                asked = {(pair.subject[1], pair.attribute, pair.value) for pair in claim_set.pair_controls}
                self.assertTrue(asked)
                self.assertEqual(len(factset.pair_controls), len(asked))
                roles = {claim.id: claim.role.value for claim in events['claims']}
                self.assertEqual({roles[pair.claim] for pair in claim_set.pair_controls}, {'pair_control'})
                pair = relation(factset, 'E3', 'E2')
                self.assertEqual((pair.relation.value, pair.row.value), ('independent', 'target'))
                self.assertTrue(evaluate.support(code, (kind,), factset, Id(IdFamily.EVENT, 2)).met)


class PairRoleTests(SimpleTestCase):
    """refute-r2c-r1 RF1 and RF2 (repair r2c-2): a pair control is never one claim with a contrary control. settle
    stores one role per claim and the engine reads a pair control by its role, so a pair control numbered into a
    contrary control of the same sentence about the same object was lost, and the pair never set apart. A contrary now
    prefers a place or a lesion no pair control asks the same object about, and a pair control's content key carries its
    role, so where every candidate is one (two lesions, each the other's only contrary) the two are two claims."""

    def test_no_pair_control_is_one_claim_with_a_contrary_control(self):
        # RF1's and RF2's inputs at the claims level: every colon segment denial and every single-target colon denial
        # beside a biopsy in each place outside it (626 inputs, 196 of which had a pair control merged), and the two
        # lesions each the other's only contrary
        checked = 0
        for denied in [*itertools.combinations(COLON, 2), *((place,) for place in COLON)]:
            whole = claims.segment_range(*denied) if len(denied) == 2 else denied
            for place in (Landmark.TERMINAL_ILEUM, *COLON):
                if any(anatomy.compatible(place, own) for own in whole):
                    continue
                claim_set = build(PART_OF_COLON, denial_answer([item.value for item in denied], (place.value,)))
                with self.subTest(denied=[item.value for item in denied], biopsy=place.value):
                    self.assertTrue(claim_set.pair_controls)
                    self.assertEqual(merged(claim_set), [])
                checked += 1
        self.assertEqual(checked, 486 + 140)
        self.assertEqual(merged(build(POLYP_LEFT, polyp_left_answer())), [])

    def test_a_contrary_prefers_a_value_no_pair_control_asks(self):
        # RF1: "No biopsies were taken from the cecum to the hepatic flexure." beside a biopsy in the transverse colon -
        # the segment's last place took the transverse colon, its second contrast and the very place the pair control
        # asks the denial about; it now takes the rectum. Beside a biopsy in the terminal ileum, the segment's first
        # place took the terminal ileum, and the biopsy's control the cecum, a place of the range a pair control asks it
        # about: the segment's places now take the transverse colon and the rectum, and the biopsy's the jejunum
        def controls(claim_set, subject, attribute):
            return sorted((item.key.index, sentence_of(claim_set, item.control))
                          for item in appraised(claim_set, attribute, subject))

        claim_set = build(SEGMENT_RANGE, denial_answer(('cecum', 'hepatic_flexure'), ('transverse_colon',),
                                                       denial_words=RANGE_WORDS))
        stem = 'This statement is about tissue samplings with forceps (not hot forceps) in the '
        self.assertEqual(controls(claim_set, 'E3', A.SCOPE_SEGMENT),
                         [(0, stem + 'terminal ileum.'), (1, stem + 'rectum.')])
        self.assertEqual(controls(claim_set, 'E2', A.TARGET_PLACES), [(0, 'This act was done in the splenic flexure.')])
        self.assertIn(('E3', 'transverse_colon'), {(pair.subject[1], pair.value) for pair in claim_set.pair_controls})
        claim_set = build(SEGMENT_RANGE, denial_answer(('cecum', 'hepatic_flexure'), ('terminal_ileum',),
                                                       denial_words=RANGE_WORDS))
        self.assertEqual(controls(claim_set, 'E3', A.SCOPE_SEGMENT),
                         [(0, stem + 'transverse colon.'), (1, stem + 'rectum.')])
        self.assertEqual(controls(claim_set, 'E2', A.TARGET_PLACES), [(0, 'This act was done in the jejunum.')])
        self.assertLessEqual({('E3', 'terminal_ileum'), ('E2', 'cecum')},
                             {(pair.subject[1], pair.value) for pair in claim_set.pair_controls})
        # RF2: "No biopsies were taken from the rectum." beside a biopsy in the sigmoid colon: each object's nearest
        # contrast was the other's place, which the pair control asks it about
        claim_set = build(SINGLE_PLACE, denial_answer(('rectum',), ('sigmoid_colon',), 'sigmoid colon', 'rectum'))
        self.assertEqual(controls(claim_set, 'E3', A.TARGET_PLACES), [(0, stem + 'anal canal.')])
        self.assertEqual(controls(claim_set, 'E2', A.TARGET_PLACES),
                         [(0, 'This act was done in the descending colon.')])
        self.assertEqual({(pair.subject[1], pair.value) for pair in claim_set.pair_controls},
                         {('E3', 'sigmoid_colon'), ('E2', 'rectum')})
        # with no pair control the contrast is D196's first candidate, as before
        claim_set = build(SINGLE_PLACE, denial_answer(('rectum',), ('transverse_colon',), 'sigmoid colon', 'rectum'))
        self.assertEqual(controls(claim_set, 'E3', A.TARGET_PLACES), [(0, stem + 'sigmoid colon.')])

    def test_two_lesions_each_the_others_only_contrary_ask_one_sentence_twice(self):
        # RF2's lesions: the polyp left in place (L1) beside the polyp removed (L2). The only other lesion of each
        # object is the one the pair control asks it about, so the contrary stays 3.2.3's ("another lesion of the
        # session" / "another lesion"), and the pair control asking the same sentence is a claim of its own: another
        # content key, another id, stored with its own role
        claim_set = build(POLYP_LEFT, polyp_left_answer())
        for subject, other in (('E2', 'L1'), ('E3', 'L2')):
            with self.subTest(subject=subject):
                (lesion_fact,) = appraised(claim_set, A.TARGET_LESION, subject)
                (pair,) = [pair for pair in claim_set.pair_controls
                           if pair.subject[1] == subject and pair.attribute is A.TARGET_LESION]
                self.assertEqual(pair.value, other)
                self.assertEqual(claim_set.claim(lesion_fact.control).value, other)
                self.assertEqual(sentence_of(claim_set, lesion_fact.control), sentence_of(claim_set, pair.claim))
                self.assertNotEqual(lesion_fact.control, pair.claim)
                self.assertNotEqual(claim_set.claim(lesion_fact.control).content, claim_set.claim(pair.claim).content)
        # one line pass 2 reads twice (the card, the units and the sentence), each of the two lesion facts' control
        # beside its pair control: only here, where no other candidate is left
        lines = [(claim_set.about[claim.id], claim.units, claim_set.sentences[claim.id]) for claim in claim_set.claims]
        self.assertEqual(len(lines) - len(set(lines)), 2)
        # with a third lesion, done to by an act of the session that pairs with neither (a tattoo), each object's
        # lesion contrary is that lesion, a question no pair control asks: no line is asked twice
        data = polyp_left_answer()
        data['lesions'].append(lesion('L3', ['S8'], 'A third polyp', places=[fact('rectum', src(['S8'], 'rectum'))]))
        data['events'].append(event('E4', ['S8'], 'marked with a tattoo', 'was marked', 'tattoo',
                                    session=[fact('X1', src(['S8']))],
                                    target__lesion=[fact('L3', src(['S8'], 'A third polyp'))]))
        claim_set = build(POLYP_THIRD, data)
        for subject in ('E2', 'E3'):
            with self.subTest(third=subject):
                (lesion_fact,) = appraised(claim_set, A.TARGET_LESION, subject)
                self.assertEqual(claim_set.claim(lesion_fact.control).value, 'L3')
        self.assertEqual(merged(claim_set), [])
        lines = [(claim_set.about[claim.id], claim.units, claim_set.sentences[claim.id]) for claim in claim_set.claims]
        self.assertEqual(len(lines), len(set(lines)))
        # and two pair controls asking one object one question stay one claim (the role is the same)
        spec = claims._Spec(claims.TemplateId.ACT_TARGET_LESION, claims.Ref(F.EVENT, 'E2'), 'L1', ('S6',), (), (),
                            claims._PAIR_ROLE)
        self.assertEqual(spec.content(), claims._Spec(*(getattr(spec, name) for name in (
            'template', 'subject', 'value', 'units', 'params', 'slots', 'role'))).content())
        self.assertNotEqual(spec.content(), claims._Spec(spec.template, spec.subject, spec.value, spec.units,
                                                         spec.params, spec.slots).content())


# --- the integration owner's rulings on waves 5-6 (DECISIONS D233, D234, D251's O3; repair r2c of round w7r) ----------

# D233 (refute-r2c-r2 G1): an angioectasia treated with argon plasma coagulation in each family with an ablation code -
# oozing at this encounter (filed as an ablation, its purpose hemostasis: the refutation's probe p02, in the upper
# endoscopy) or with no bleeding stated (refute-r2c-r1 RF3's shape). Each note is synthetic and is in NOTES.
ANGIOECTASIA = {
    # name: (the note's kind, its examination sentence, the scope's words, the session family, the act's place and its
    # words, the family's ablation code, its bleeding-control code)
    'egd, antrum': ('UPPER ENDOSCOPY', 'The gastroscope was advanced to the duodenum.', 'gastroscope', 'egd',
                    'gastric_antrum', 'gastric antrum', '43270', '43255'),
    'egd, esophagus': ('UPPER ENDOSCOPY', 'The gastroscope was advanced to the duodenum.', 'gastroscope', 'egd',
                       'distal_esophagus', 'distal esophagus', '43229', '43227'),
    'colonoscopy': ('COLONOSCOPY', 'The colonoscope was advanced to the cecum.', 'colonoscope', 'colonoscopy',
                    'ascending_colon', 'ascending colon', '45388', '45382'),
    'enteroscopy': ('ENTEROSCOPY', 'The enteroscope was advanced to the jejunum.', 'enteroscope', 'enteroscopy',
                    'jejunum', 'jejunum', '44369', '44366'),
    'flexible sigmoidoscopy': ('FLEXIBLE SIGMOIDOSCOPY', 'The sigmoidoscope was advanced to the descending colon.',
                               'sigmoidoscope', 'flex_sig', 'sigmoid_colon', 'sigmoid colon', '45346', '45334'),
}
# what a faithful reader supports of a treatment of bleeding present at this encounter: D233's narrowed label
BLEEDING_HERE = 'This act is a treatment of bleeding present at this encounter.'


def angioectasia(name, oozing):
    """The note and the answer of one ANGIOECTASIA case: the examination E1 (S4) and the act E2 (S5), filed as an
    ablation with argon plasma in its place; an oozing one with its purpose hemostasis too (refute-r2c-r2's p02)."""
    kind_word, exam, scope, family, place, words, _ablation, _bleeding = ANGIOECTASIA[name]
    if oozing:
        act = f'An oozing angioectasia in the {words} was treated with argon plasma coagulation.'
        kind_words, status_words = 'treated with argon plasma coagulation', 'was treated'
        over = {'purpose': [fact('hemostasis', src(['S5'], 'An oozing angioectasia'))]}
    else:
        act = f'The angioectasia in the {words} was ablated with argon plasma coagulation.'
        kind_words, status_words, over = 'ablated', 'was ablated', {}
    text = OVERLAP_NOTE.format(kind=kind_word, exam=exam, act=act)
    return text, frame_answer(family, [
        examination(words=scope),
        event('E2', ['S5'], kind_words, status_words, 'ablation', session=[fact('X1', src(['S5']))],
              technique__device=[fact('argon_plasma', src(['S5'], 'argon plasma coagulation'))],
              target__places=[fact(place, src(['S5'], words))], **over)], fact('E1', src(['S4'])))


def decided(code, factset, act='E2'):
    """evaluate.decide for ``code`` with the act's anchor as its kept evidence (refute-r2c-r2's probes): READY when an
    act supports it and nothing is held, EXCLUDED with an exclusion, else NEEDS_CLARIFICATION; and the evaluation."""
    from studio.interpretation.engine import evaluate
    from studio.interpretation.engine.types import Id, IdFamily
    found = evaluate.decide(code, tuple(factset.anchors[Id(IdFamily.EVENT, int(act[1:]))].units), factset)
    status = ('EXCLUDED' if found.exclusion is not None else
              'READY' if found.supporting and not found.held_facts else 'NEEDS_CLARIFICATION')
    return status, found


# D234 (refute-r2c-r2 G2, its probes p01 and p04): a cold-snare removal of one polyp (L1) beside the denial of removing
# two others it lists (L2 and L3, each a different polyp); the second note tells a fourth polyp (L4) too
LISTED_TWO = ('SYNTHETIC COLONOSCOPY NOTE\n'
              'Date of service: 06/02/2031\n'
              'Endoscopist: Q. R. Vance, MD (fictional)\n'
              '\n'
              'Findings: The colonoscope was advanced to the cecum.\n'
              'A 5 mm polyp in the transverse colon was removed with a cold snare.\n'
              'A different 4 mm polyp was seen in the cecum.\n'
              'A different 6 mm polyp was seen in the ascending colon.\n'
              'The cecal polyp and the ascending colon polyp were not removed.\n')
LISTED_FOURTH = LISTED_TWO.replace('The cecal polyp', 'A different 2 mm polyp was seen in the rectum.\nThe cecal polyp')
# each object's true lesions and places, as a faithful pass 2 answers the pair controls
LISTED_TRUTH = {'E2': {'L1', 'transverse_colon'}, 'E3': {'L2', 'L3', 'cecum', 'ascending_colon'}}


def listed_polyps_answer(fourth=False):
    """LISTED_TWO's answer (LISTED_FOURTH's with ``fourth``), as refute-r2c-r2's p01 builds it: the removal E2 of L1
    (S5) and the denial E3 of removing L2 and L3 (listed_targets), each listed polyp distinct from L1."""
    last = 'S9' if fourth else 'S8'
    lesions = [lesion('L1', ['S5'], 'A 5 mm polyp', places=[fact('transverse_colon', src(['S5'], 'transverse colon'))]),
               lesion('L2', ['S6'], 'A different 4 mm polyp', places=[fact('cecum', src(['S6'], 'cecum'))],
                      distinct_from=[fact('L1', src(['S6'], 'A different 4 mm polyp'))]),
               lesion('L3', ['S7'], 'A different 6 mm polyp',
                      places=[fact('ascending_colon', src(['S7'], 'ascending colon'))],
                      distinct_from=[fact('L1', src(['S7'], 'A different 6 mm polyp'))])]
    if fourth:
        lesions.append(lesion('L4', ['S8'], 'A different 2 mm polyp', places=[fact('rectum', src(['S8'], 'rectum'))],
                              distinct_from=[fact('L1', src(['S8'], 'A different 2 mm polyp'))]))
    return frame_answer('colonoscopy', [
        examination(words='colonoscope'),
        event('E2', ['S5'], 'removed with a cold snare', 'was removed', 'snare', session=[fact('X1', src(['S5']))],
              target__lesion=[fact('L1', src(['S5'], 'A 5 mm polyp'))],
              target__places=[fact('transverse_colon', src(['S5'], 'transverse colon'))],
              technique__device=[fact('cold_snare', src(['S5'], 'cold snare'))]),
        event('E3', [last], 'removed', 'were not removed', 'snare', neg('performed', src([last], 'were not removed')),
              session=[fact('X1', src([last]))],
              scope__breadth=[fact('listed_targets', src([last], 'The cecal polyp and the ascending colon polyp'))],
              scope__targets=['L2', 'L3'])],
        fact('E1', src(['S4'])), lesions=lesions)


def listed_note(count):
    """A colonoscopy telling ``count`` polyps, one sentence each (S5..), then a denial of removing some (D234's
    sweep)."""
    lines = ['SYNTHETIC COLONOSCOPY NOTE', 'Date of service: 06/02/2031', 'Endoscopist: Q. R. Vance, MD (fictional)',
             '', 'Findings: The colonoscope was advanced to the cecum.']
    return '\n'.join(lines + [f'Polyp {number} was seen.' for number in range(1, count + 1)]
                     + ['The listed polyps were not removed.']) + '\n'


def listed_answer_of(members, others, target=None):
    """listed_note(members + others)'s answer: the polyps L1.. (S5..) and the denial E2 of removing the first
    ``members`` of them (listed_targets), with ``target`` as its target lesion too when given; no act, so no pair
    control asks the denial anything."""
    count = members + others
    last = f'S{5 + count}'
    over = {} if target is None else {'target__lesion': [fact(target, src([last], 'polyps'))]}
    return frame_answer('colonoscopy', [
        examination(words='colonoscope'),
        event('E2', [last], 'removed', 'were not removed', 'snare', neg('performed', src([last], 'were not removed')),
              session=[fact('X1', src([last]))],
              scope__breadth=[fact('listed_targets', src([last], 'The listed polyps'))],
              scope__targets=[f'L{number}' for number in range(1, members + 1)], **over)],
        fact('E1', src(['S4'])),
        lesions=[lesion(f'L{number}', [f'S{4 + number}'], f'Polyp {number}') for number in range(1, count + 1)])


NOTES.update({f'ANGIOECTASIA {name} {case}': angioectasia(name, case == 'oozing')[0] for name in ANGIOECTASIA
              for case in ('oozing', 'no bleeding stated')})
NOTES.update({'LISTED_TWO': LISTED_TWO, 'LISTED_FOURTH': LISTED_FOURTH,
              **{f'LISTED SWEEP {count}': listed_note(count) for count in range(2, 9)}})


class ListedTargetTests(SimpleTestCase):
    """DECISIONS D234 (refute-r2c-r2 G2): every member of a listed-targets denial read the same lesion control (its
    own lesions and the lesions the pair controls ask it about depend on the statement alone), so the store bound the
    control to the first member and the second settled unappraised: no listed-targets denial ever set apart an act on
    another lesion. The place preference ("taken") extends to lesions: each lesion fact of a statement takes a lesion no
    other lesion fact of it takes, and is not claimed (control) when none is left."""

    def test_each_listed_target_has_a_control_of_its_own(self):
        # p01's variant (b): the first listed polyp takes L4 (no pair control asks the denial about it), the second
        # L1 - the one lesion left, the very question the pair control asks, a claim of its own beside it
        claim_set = build(LISTED_FOURTH, listed_polyps_answer(fourth=True))
        members = sorted(appraised(claim_set, A.SCOPE_TARGETS, 'E3'), key=lambda item: item.key.index)
        self.assertEqual([(item.value, claim_set.claim(item.control).value) for item in members],
                         [('L2', 'L4'), ('L3', 'L1')])
        stem = 'This statement is about removals with a snare (not endoscopic mucosal resections) of lesion '
        self.assertEqual([sentence_of(claim_set, item.control) for item in members], [stem + 'L4.', stem + 'L1.'])
        (asked,) = [pair for pair in claim_set.pair_controls if pair.subject[1] == 'E3'
                    and pair.attribute is A.TARGET_LESION]
        self.assertEqual(asked.value, 'L1')
        self.assertNotEqual(members[1].control, asked.claim)
        no_claim_or_control_read_twice(self, claim_set)
        # p01's variant (a): no fourth polyp - the first listed polyp takes L1, and none is left for the second, which
        # is not claimed (control): it settles unappraised, never read through the first one's control
        claim_set = build(LISTED_TWO, listed_polyps_answer())
        (member,) = appraised(claim_set, A.SCOPE_TARGETS, 'E3')
        self.assertEqual((member.key.index, claim_set.claim(member.control).value), (0, 'L1'))
        self.assertEqual([(item.key.index, item.why) for item in claim_set.unclaimed
                          if (item.key.object, item.key.attribute) == ('E3', A.SCOPE_TARGETS)],
                         [(1, claims.Unclaimable.CONTROL)])
        no_claim_or_control_read_twice(self, claim_set)

    def test_the_second_listed_target_is_appraised_by_its_own_control_and_45385_met(self):
        # p01 (b) and p04, end to end under a faithful pass 2: the second listed polyp's own claim is supported and its
        # own control rejected, so it settles supported; L2 and L3 are distinct from L1 and every pair control is
        # rejected, so the denial is set apart from the removal (target) and 45385 is met. In (a) the second listed
        # polyp has no control of its own (D234: none left), so the pair stays unresolved and 45385 is not met
        from studio.interpretation.engine import evaluate
        from studio.interpretation.engine.types import Id, IdFamily
        for name, text, data, expected in (
                ('a fourth polyp', LISTED_FOURTH, listed_polyps_answer(fourth=True),
                 (['supported', 'supported'], ('independent', 'target'), True)),
                ('no fourth polyp', LISTED_TWO, listed_polyps_answer(),
                 (['supported', 'unresolved'], ('unresolved', 'target'), False))):
            with self.subTest(note=name):
                claim_set, events, factset = settled(text, data, faithful_oracle(places=LISTED_TRUTH))
                results = [at(events, 'E3', A.SCOPE_TARGETS, index).result.value for index in (0, 1)]
                pair = relation(factset, 'E3', 'E2')
                met = evaluate.support('45385', (Kind.SNARE,), factset, Id(IdFamily.EVENT, 2)).met
                self.assertEqual((results, (pair.relation.value, pair.row.value if pair.row else None), met), expected)
                if name == 'no fourth polyp':
                    self.assertEqual([reason.value for reason in at(events, 'E3', A.SCOPE_TARGETS, 1).reasons],
                                     ['unappraised'])
                no_claim_or_control_read_twice(self, claim_set)

    def test_a_statements_lesion_facts_never_share_a_control_and_the_real_scope(self):
        # NOTES Q6's real scope, swept: a denial listing m polyps (and, in the second form, its target lesion besides)
        # in a note telling n other polyps. Each lesion fact takes the next other polyp in document order, so with
        # n >= 1 the first n facts have controls of their own and the rest are not claimed (control); with n = 0 no
        # other lesion exists, and none has a control (3.2.3: "of lesion {another lesion}", when one exists). Never a
        # control read by two facts
        for members, others, target in ((2, 0, None), (2, 1, None), (2, 2, None), (2, 3, None), (3, 1, None),
                                        (3, 2, None), (3, 3, None), (3, 5, None), (2, 3, 'L3'), (2, 2, 'L4')):
            with self.subTest(members=members, others=others, target=target):
                claim_set = build(listed_note(members + others), listed_answer_of(members, others, target))
                no_claim_or_control_read_twice(self, claim_set)
                facts = [item for item in claim_set.appraised if item.key.object == 'E2'
                         and item.key.attribute in (A.SCOPE_TARGETS, A.TARGET_LESION)]
                left = [item for item in claim_set.unclaimed if item.key.object == 'E2'
                        and item.key.attribute in (A.SCOPE_TARGETS, A.TARGET_LESION)]
                own = {f'L{number}' for number in range(1, members + 1)} | ({target} if target else set())
                candidates = [f'L{number}' for number in range(1, members + others + 1)
                              if f'L{number}' not in own]
                lesion_facts = members + (1 if target else 0)
                if not candidates:
                    self.assertEqual(([item.control for item in facts], left), ([None] * lesion_facts, []))
                    continue
                controls = [claim_set.claim(item.control).value for item in facts]
                self.assertEqual(sorted(controls), sorted(candidates[:lesion_facts]))
                self.assertEqual(len(facts), min(lesion_facts, len(candidates)))
                self.assertEqual([item.why for item in left],
                                 [claims.Unclaimable.CONTROL] * max(0, lesion_facts - len(candidates)))


# DECISIONS D251, O3 (refute-3a-r2's p10 and p11; r3a's request R-C): a supported fact whose value is '' is S2's
# item-level breach (shape_inconsistent), with which 1.8 keeps the answer. claims.py raised on it (Kind(''),
# Extent(''), Station(''), AnatomyType('')), so the interpret stage failed at claim time and settle's fail-closed
# reading was never reached. Each answer below is walked for its supported facts, and each is emptied in turn.
EMPTY_CASES = {
    'NOTE': (NOTE, note_answer),
    'RICH': (RICH, rich_answer),
    'EUS': (EUS, lambda: eus_answer(stations=[fact('stomach', src(['S4'], 'upper'))])),
}


def anatomy_answer():
    """NOTE's answer with two anatomy entries a rule reads: a stoma the session passed through (Y1) and a surgically
    absent organ whose organ holds the reached cecum (Y2), so the entries' type and organ are claimed."""
    data = note_answer()
    data['anatomy'] = [{'id': 'Y1', 'type': fact('stoma', src(['S5'], 'colonoscope')), 'organ': [], 'subtype': [],
                        'joins': []},
                       {'id': 'Y2', 'type': fact('surgically_absent', src(['S4'], 'Prior colonoscopy')),
                        'organ': [fact('colon', src(['S4'], 'colonoscopy'))], 'subtype': [], 'joins': []}]
    data['sessions'][0]['through'] = [fact('Y1', src(['S5'], 'colonoscope'))]
    return data


EMPTY_CASES['NOTE anatomy'] = (NOTE, anatomy_answer)


def supported_paths(data):
    """The path of every supported fact of pass 1's answer (refute-3a-r2's p11 walk)."""
    found = []

    def walk(node, path):
        if isinstance(node, dict):
            if {'state', 'value', 'sources', 'options', 'qualifiers'} <= set(node) and node['state'] == 'supported':
                found.append(path)
            for key, value in node.items():
                walk(value, path + (key,))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + (index,))

    walk(data, ())
    return found


def emptied(data, path):
    """A copy of ``data`` with the fact at ``path`` given the value ''."""
    data = copy.deepcopy(data)
    node = data
    for part in path:
        node = node[part]
    node['value'] = ''
    return data


def settled_at(events, path):
    """The settled fact standing where ``path`` stands in pass 1's answer (a slot's one fact settles as the fact)."""
    node = events
    for part in path:
        if isinstance(part, int) and not isinstance(node, list):
            continue  # a slot: its one fact
        node = node[part]
    return node


class EmptyValueTests(SimpleTestCase):
    """DECISIONS D251, O3: claims.py never raises on a supported value ''; it reads it as not supported, so the fact
    is never claimed, no value is built from it, and settle reaches its fail-closed reading (unresolved,
    shape_inconsistent)."""

    def test_a_supported_empty_value_is_read_as_not_supported_and_never_raises(self):
        checked = 0
        for name, (text, answer_of) in EMPTY_CASES.items():
            data = answer_of()
            for path in supported_paths(data):
                with self.subTest(note=name, path=path):
                    claim_set = build(text, emptied(data, path))  # raised ValueError on ten of these
                    self.assertNotIn('', [item.value for item in claim_set.appraised])
                    no_claim_or_control_read_twice(self, claim_set)
                checked += 1
        self.assertGreater(checked, 100)
        # the facts each one leaves unclaimed: an event whose kind is '' is not claimable at all (its card shows no
        # claim), and a session's reach, a station, an anatomy entry's type or organ is never claimed or read
        data = note_answer()
        claim_set = build(NOTE, emptied(data, ('events', 1, 'kind')))
        self.assertEqual([item for item in claim_set.appraised if item.key.object == 'E2'], [])
        claim_set = build(NOTE, emptied(data, ('sessions', 0, 'reached', 0)))
        self.assertEqual(appraised(claim_set, A.REACHED, 'X1'), [])
        claim_set = build(EUS, emptied(eus_answer(stations=[fact('stomach', src(['S4'], 'upper'))]),
                                       ('sessions', 0, 'stations', 0)))
        self.assertEqual(appraised(claim_set, A.STATIONS, 'X1'), [])
        data = anatomy_answer()
        self.assertEqual({item.key.object for item in build(NOTE, data).appraised if item.key.family is F.ANATOMY},
                         {'Y1', 'Y2'})
        claim_set = build(NOTE, emptied(data, ('anatomy', 0, 'type')))
        self.assertEqual(appraised(claim_set, A.TYPE, 'Y1'), [])
        claim_set = build(NOTE, emptied(data, ('anatomy', 1, 'organ', 0)))
        self.assertEqual([item for item in claim_set.appraised if item.key.object == 'Y2'], [])  # no longer read

    def test_a_supported_empty_value_settles_not_supported_end_to_end(self):
        # read, checks, claims, a faithful pass 2, settle, the store and the FactSet: the emptied fact settles
        # unresolved (shape_inconsistent), never supported, and the document's row is written
        for name, path in (('NOTE', ('events', 1, 'kind')), ('NOTE', ('sessions', 0, 'reached', 0)),
                           ('NOTE', ('lesions', 0, 'places', 0)), ('NOTE', ('events', 1, 'technique', 'device', 0)),
                           ('NOTE', ('events', 2, 'scope', 'breadth', 0)), ('EUS', ('sessions', 0, 'stations', 0)),
                           ('NOTE anatomy', ('anatomy', 0, 'type')), ('NOTE anatomy', ('anatomy', 1, 'organ', 0))):
            with self.subTest(note=name, path=path):
                text, answer_of = EMPTY_CASES[name]
                _claim_set, events, _factset = settled(text, emptied(answer_of(), path))
                found = settled_at(events, path)
                self.assertEqual((found.claim.value, found.result.value), ('', 'unresolved'))
                self.assertIn(Reason.SHAPE_INCONSISTENT, found.reasons)


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

    def test_facts_one_sentence_tells_each_have_their_own_claim(self):
        # DECISIONS D223: part_of and part_relation are told by one sentence, and each has its own claim of it - its
        # value the fact's own, so its own content key - so each fact has one appraisal and the store reads every claim
        # for one fact; both are UNCONTROLLED (3.2.3)
        data = note_answer()
        data['events'][1]['part_of'] = [fact('E1', src(['S6'], 'was removed'))]
        data['events'][1]['part_relation'] = [fact('step_of', src(['S6'], 'was removed'))]
        claim_set = build(NOTE, data)
        (part_of,), (relation,) = appraised(claim_set, A.PART_OF, 'E2'), appraised(claim_set, A.PART_RELATION, 'E2')
        self.assertNotEqual(part_of.claim, relation.claim)
        self.assertNotEqual(claim_set.claim(part_of.claim).content, claim_set.claim(relation.claim).content)
        self.assertEqual((claim_set.claim(part_of.claim).value, claim_set.claim(relation.claim).value),
                         ('E1', 'step_of'))
        for item in (part_of, relation):
            self.assertEqual(sentence_of(claim_set, item.claim), 'This act was a step of act A2.')  # E1's card
            self.assertIsNone(item.control)  # UNCONTROLLED
        # no claim is read by two facts anywhere in the set
        ids = [item.claim for item in claim_set.appraised]
        self.assertEqual(len(ids), len(set(ids)))

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
# are superseded. Recomputed again by step 2c3 for DECISIONS D209-D213 (the narrowed labels, the lesion-places template
# and the targeted breadth's control form in TEMPLATES; D209's moderate-sedation sibling, D210's reported acts, D211's
# kind pairs, D212's lesion-places rule, D213's devices, targeted breadths and pinned segment order in CONTROLS):
# INT-5's TEMPLATES 9efd3e1d... and CONTROLS 19fbf962... are superseded; STATEMENT_TEMPLATES, CLAIM_BOUND and CLAIMED
# are measured unchanged. Until the first recording under gemini-appraisal@1 a changed object needs only its pin
# recomputed, no version bump (D202): the integration owner writes them in the waves 3-4 pin change. Recomputed again
# by repair r2c for DECISIONS D222 and D223 (the reworded stent removal and tube placement labels and the
# intervention's control form in TEMPLATES; the replaced siblings, argon plasma's contrary, the segment place's own
# contrast, the pair controls over a segment's whole range and the bleeding control's compatible acts in CONTROLS): the
# waves 3-4 TEMPLATES 54225978... and CONTROLS 95d1ee8b... are superseded; STATEMENT_TEMPLATES, CLAIM_BOUND and CLAIMED
# are measured unchanged. r2c writes the two moved pins in studio/interpretation/__init__.py itself (its task: D202,
# no version bump before the first recording). Recomputed again by repair r2c-2 for refute-r2c-r1's findings (the
# ablation's sibling, a contrary's preference for a value no pair control asks, the pair control's role in its content
# key, and their rule texts in CONTROLS): r2c's CONTROLS 14ecfe86... is superseded; TEMPLATES, STATEMENT_TEMPLATES,
# CLAIM_BOUND and CLAIMED are measured unchanged. r2c-2 writes the moved pin in __init__.py itself (D202). Recomputed
# again by repair r2c of round w7r for DECISIONS D233 and D234 (the bleeding control's narrowed label in TEMPLATES;
# ablation's sibling, the pair kinds that follow it and the lesion rule's text in CONTROLS): r2c-2's TEMPLATES
# 8bd8c0c9... and CONTROLS 07db0fd1... are superseded; STATEMENT_TEMPLATES, CLAIM_BOUND and CLAIMED are measured
# unchanged. The two moved pins are written in __init__.py by this repair (D202: no version bump before the first
# recording).
TEMPLATES_SHA256 = '8362112662c3172e6d375e713bb2ba5da7057e6f3c30085b68bc8359a50ef823'
STATEMENT_TEMPLATES_SHA256 = '3880e4af3eefbdbccf0c5bb8e4a099df1d50268b485e991f46db7b8f3a19e162'
CONTROLS_SHA256 = 'e4a8a79250ed14135b3d9f613fc4c4f57094bbe588b5484a1be98cc591a31c32'
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
