"""Repair round r2e, builder e-tools-records (DECISIONS D303: records3's RDRX-1). TEXT-ONLY and SYNTHETIC: every note
here was written for these tests (fictional clinicians, no patient) and every pass-1 answer is built by hand with
tests/v2/test_settle's builders (identical in this tree and the recorded one); nothing is sent.

RDRX-1 - whenever a check's rule changed after a label's first recording - by AMENDMENT-2 4.3.3 or by any later ruling -
findings made for that label read it as recorded (D202: a label's rule never changes after its first recording). The
checks a ruling changed after gemini-inventory@2 was first recorded (the tree every gemini-inventory@2 batch was
recorded with, 195e06e90, against int2) are G5's attributes (D292's U3 added reached_anatomy), G1's document_frame (the
frame part: D295, D300) and G1's section (the procedure part: D299); contract/checks.py now consults the label for each,
as consistency._reading does for the K rules and L1 (D294 F2, D297 R2RX-1, D301 RBRX-1): under gemini-inventory@2 G5
reads reached, completion, stations, approach and through, document_frame reads N0's span alone and section reads the
containing section's own start or closing source; gemini-inventory@3 (the current path, the default) reads every rule
as amended. So a recording made under gemini-inventory@2 re-settles, and its pass-2 request rebuilds, as the recorded
tree made them.

- R2ETRecordedG5Tests: the refutation's input (NOTE, X1.reached_anatomy cited at the snare's sentence): no
  extent_inferred for @2 (as recorded), extent_inferred for @3 and with no label; boundaries: reached_anatomy in the
  examination's statement passes under both labels, and the reach cited at the snare's sentence - an attribute
  gemini-inventory@2 was recorded with - is extent_inferred under both.
- R2ETRecordedFramePartTests: a header in labelled parts, under a title line (R2ET_HEADER) and with none (R2ET_LABEL_FIRST,
  D199's empty N0): every frame fact geometry_document_frame for @2 (as recorded), none for @3; boundary: a date line
  after the acts fails under both labels.
- R2ETRecordedProcedurePartTests: a note in procedure parts (R2ET_PARTS), each act's session cited at its part's heading:
  geometry_section for @2 (as recorded), none for @3; boundaries: an act citing its own section's start passes, and one
  citing another part's heading fails, under both labels.
- R2ETRecordedTreeTests: for each input, the whole Checked made for gemini-inventory@2 - and the dormant (Gemini)
  adapter's pass-2 request built with it - equals the RECORDED tree's (RECORDED_FIXTURE, written in the recorded tree by
  ``write_recorded``, its owning function, which refuses a tree whose checks take a label); for @3 both differ on each
  change input and equal it on each control.
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation.contract import checks, geometry, jsonschema
from studio.interpretation.contract import extract_read as xr
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract.types import Attribute, Reason
from tests.v2.test_settle import (NOTE, answer, event, fact, frame, labelled, lesion, note_answer, opening, section,
                                  session, src)

INV2 = interpretation.INVENTORY_VERSION_V2
INV3 = getattr(interpretation, 'INVENTORY_VERSION_V3', 'gemini-inventory@3')  # the recorded tree names no @3
A, F, R = Attribute, xs.Family, Reason
RECORDED_FIXTURE = (Path(__file__).resolve().parents[1] / 'fixtures' / 'interpretation_v2' / 'r2et_records'
                    / 'recorded_checks.json')

# --- the synthetic notes (each line one unit) ---------------------------------------------------------------------------

# D295: a header in labelled parts under a title line - the date line in N1, the author line in N2 (S1-S10)
R2ET_HEADER = ('SYNTHETIC COLONOSCOPY NOTE\n'                                       # S1: N0, the title
               'PATIENT INFORMATION\n'                                              # S2: N1's label
               'Patient: synthetic patient Q-31\n'                                  # S3
               'Date of service: 03/14/2031\n'                                      # S4: the date line, in N1
               'PROCEDURE DETAILS\n'                                                # S5: N2's label
               'Endoscopist: Corvin Ashdale, MD (fictional)\n'                      # S6: the author line, in N2
               'Instrument: adult colonoscope\n'                                    # S7
               '\n'
               'Findings: The colonoscope was advanced to the cecum.\n'             # S8: N3, the first act
               'A 5 mm polyp in the sigmoid colon was removed with a cold snare.\n'  # S9
               '\n'
               'Addendum: Date of service 03/14/2031 confirmed.\n')                 # S10: N4, after the acts

# D300 RBFX-FRAME-1: the same header with no title line - the note opens with its first heading (N0 empty, D199)
R2ET_LABEL_FIRST = ('PATIENT INFORMATION\n'                                        # S1: N1 at offset 0
                    'Patient: synthetic patient Q-32\n'                             # S2
                    'Date of service: 05/21/2032\n'                                 # S3: the date line, in N1
                    'PROCEDURE DETAILS\n'                                           # S4: N2
                    'Endoscopist: Corvin Ashdale, MD (fictional)\n'                 # S5: the author line, in N2
                    'Instrument: adult colonoscope\n'                               # S6
                    '\n'
                    'Findings: The colonoscope was advanced to the cecum.\n'        # S7: N3, the first act
                    'A 5 mm polyp in the sigmoid colon was removed with a cold snare.\n')  # S8

# D299: a note in procedure parts with findings subsections (S1-S11)
R2ET_PARTS = ('SYNTHETIC ENDOSCOPY NOTE\n'                                         # S1: N0, the title
              'Date of service: 03/14/2031\n'                                      # S2: the date line
              'Endoscopist: Corvin Ashdale, MD (fictional)\n'                      # S3: the author line
              '\n'
              'PART 1: UPPER ENDOSCOPY\n'                                          # S4: N1, role procedure
              'The gastroscope was advanced to the second part of the duodenum.\n'  # S5: E1, X1's examination
              'FINDINGS:\n'                                                        # S6: N2, role findings
              'Biopsies of the gastric antrum were taken with cold forceps.\n'     # S7: E2, a biopsy in X1
              '\n'
              'PART 2: COLONOSCOPY\n'                                              # S8: N3, role procedure
              'The colonoscope was advanced to the cecum.\n'                       # S9: E3, X2's examination
              'FINDINGS:\n'                                                        # S10: N4, role findings
              'A 5 mm polyp in the sigmoid colon was removed with a cold snare.\n')  # S11: E4, a removal in X2


# --- the pass-1 answers ------------------------------------------------------------------------------------------------

def g5_answer(units: list, words: str, link: str = 'statement', attribute: str = 'reached_anatomy') -> dict:
    """NOTE's answer with X1's ``attribute`` cited at ``units``/``words`` (reached_anatomy: Y1, the ileocolic
    anastomosis entry; reached: the sigmoid colon)."""
    data = note_answer()
    value = 'Y1' if attribute == 'reached_anatomy' else 'sigmoid_colon'
    data['sessions'][0][attribute] = [fact(value, src(units, words, link))]
    return data


def header_answer(date_unit: str = 'S4', date_words: str = '03/14/2031') -> dict:
    """R2ET_HEADER's answer: N0 the title; N1 and N2 the labelled header parts (role header); N3 the findings part with
    the colonoscopy X1 (E1) to the cecum and a cold-snare removal of L1 (E2); N4 an addendum. The date of service, each
    part's occasion and the session's encounter cite ``date_unit``, the documenting clinician, each part's owner and
    performer the author line S6 - all through the document frame."""
    owner = fact('documenting_clinician', frame(['S6']))
    occasion = fact('on_date_of_service', frame([date_unit]))
    team = fact('documenting_team', frame(['S6']))

    def part(sid, unit, label, role):
        return section(sid, src([unit], label, 'section'), owner, role=[fact(role, src([unit], label, 'section'))],
                       occasion=[occasion], performer=[team])

    return answer(
        sections=[section('N0', src([], '', 'section'), owner, role=[fact('header', src(['S1'], '', 'frame'))],
                          occasion=[occasion], performer=[team]),
                  part('N1', 'S2', 'PATIENT INFORMATION', 'header'), part('N2', 'S5', 'PROCEDURE DETAILS', 'header'),
                  part('N3', 'S8', 'Findings:', 'findings'), part('N4', 'S10', 'Addendum:', 'addendum')],
        when={'state': 'stated', 'value': '2031-03-14', 'sources': [frame([date_unit], date_words)], 'options': []},
        clinician=[fact('P1', frame(['S6'], 'Corvin Ashdale'))],
        people=[{'id': 'P1', 'name': src(['S6'], 'Corvin Ashdale'),
                 'role': fact('documenting_clinician', src(['S6'], 'Endoscopist'))}],
        sessions=[session('X1', fact('colonoscopy', src(['S8'], 'colonoscope')), examination=[fact('E1', src(['S8']))],
                          encounter=[fact('this_encounter', frame([date_unit]))],
                          reached=[fact('cecum', src(['S8'], 'advanced to the cecum'))])],
        lesions=[lesion('L1', src(['S9'], 'A 5 mm polyp'), multiplicity=[fact('single', src(['S9'], 'A 5 mm polyp'))],
                        places=[fact('sigmoid_colon', src(['S9'], 'sigmoid colon'))])],
        events=[event('E1', ['S8'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S8']))]),
                event('E2', ['S9'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S9']))],
                      target__lesion=[fact('L1', src(['S9'], 'A 5 mm polyp'))],
                      target__places=[fact('sigmoid_colon', src(['S9'], 'sigmoid colon'))],
                      technique__device=[fact('cold_snare', src(['S9'], 'cold snare'))])])


def label_first_answer() -> dict:
    """R2ET_LABEL_FIRST's answer: N0 the opening part (its start cites no unit; length zero, D199); N1 and N2 the
    labelled header parts (role header); N3 the findings part with X1 (E1) and a cold-snare removal of L1 (E2). The
    frame facts cite the date line S3 and the author line S5 through the document frame."""
    owner = fact('documenting_clinician', frame(['S5']))
    occasion = fact('on_date_of_service', frame(['S3']))
    team = fact('documenting_team', frame(['S5']))

    def part(sid, unit, label, role):
        start = src([unit], label, 'section')
        return section(sid, start, owner, role=[fact(role, start)], occasion=[occasion], performer=[team])

    return answer(
        sections=[section('N0', src([], '', 'section'), owner, role=[], occasion=[occasion], performer=[team]),
                  part('N1', 'S1', 'PATIENT INFORMATION', 'header'), part('N2', 'S4', 'PROCEDURE DETAILS', 'header'),
                  part('N3', 'S7', 'Findings:', 'findings')],
        when={'state': 'stated', 'value': '2032-05-21', 'sources': [frame(['S3'], '05/21/2032')], 'options': []},
        clinician=[fact('P1', frame(['S5'], 'Corvin Ashdale'))],
        people=[{'id': 'P1', 'name': src(['S5'], 'Corvin Ashdale'),
                 'role': fact('documenting_clinician', src(['S5'], 'Endoscopist'))}],
        sessions=[session('X1', fact('colonoscopy', src(['S7'], 'colonoscope')), examination=[fact('E1', src(['S7']))],
                          encounter=[fact('this_encounter', frame(['S3']))],
                          reached=[fact('cecum', src(['S7'], 'advanced to the cecum'))])],
        lesions=[lesion('L1', src(['S8'], 'A 5 mm polyp'), multiplicity=[fact('single', src(['S8'], 'A 5 mm polyp'))],
                        places=[fact('sigmoid_colon', src(['S8'], 'sigmoid colon'))])],
        events=[event('E1', ['S7'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S7']))]),
                event('E2', ['S8'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S8']))],
                      target__lesion=[fact('L1', src(['S8'], 'A 5 mm polyp'))],
                      target__places=[fact('sigmoid_colon', src(['S8'], 'sigmoid colon'))],
                      technique__device=[fact('cold_snare', src(['S8'], 'cold snare'))])])


def parts_answer(e2_session: tuple = ('S4', 'PART 1: UPPER ENDOSCOPY'),
                 e4_session: tuple = ('S8', 'PART 2: COLONOSCOPY')) -> dict:
    """R2ET_PARTS' answer: N0 the title; N1 'PART 1: UPPER ENDOSCOPY' (role procedure) and its findings part N2; N3
    'PART 2: COLONOSCOPY' (role procedure) and its findings part N4. X1 (E1 in N1) and an antral biopsy E2 in N2; X2 (E3
    in N3) and a cold-snare removal of L1 E4 in N4; each act's session cited at ``e2_session`` / ``e4_session`` (unit,
    words) through the link section - by default its part's heading."""
    return answer(
        sections=[opening(), labelled('N1', 'S4', 'PART 1: UPPER ENDOSCOPY', 'procedure'),
                  labelled('N2', 'S6', 'FINDINGS:', 'findings'), labelled('N3', 'S8', 'PART 2: COLONOSCOPY', 'procedure'),
                  labelled('N4', 'S10', 'FINDINGS:', 'findings')],
        sessions=[session('X1', fact('egd', src(['S5'], 'gastroscope')), examination=[fact('E1', src(['S5']))],
                          encounter=[fact('this_encounter', frame(['S2']))],
                          reached=[fact('duodenum', src(['S5'], 'advanced to the second part of the duodenum'))]),
                  session('X2', fact('colonoscopy', src(['S9'], 'colonoscope')), examination=[fact('E3', src(['S9']))],
                          encounter=[fact('this_encounter', frame(['S2']))],
                          reached=[fact('cecum', src(['S9'], 'advanced to the cecum'))])],
        lesions=[lesion('L1', src(['S11'], 'A 5 mm polyp'), multiplicity=[fact('single', src(['S11'], 'A 5 mm polyp'))],
                        places=[fact('sigmoid_colon', src(['S11'], 'sigmoid colon'))])],
        events=[event('E1', ['S5'], 'gastroscope', 'was advanced', 'examination', session=[fact('X1', src(['S5']))]),
                event('E2', ['S7'], 'Biopsies', 'were taken', 'biopsy',
                      session=[fact('X1', src([e2_session[0]], e2_session[1], 'section'))],
                      target__places=[fact('gastric_antrum', src(['S7'], 'gastric antrum'))],
                      technique__device=[fact('cold_forceps', src(['S7'], 'cold forceps'))]),
                event('E3', ['S9'], 'colonoscope', 'was advanced', 'examination', session=[fact('X2', src(['S9']))]),
                event('E4', ['S11'], 'cold snare', 'was removed', 'snare',
                      session=[fact('X2', src([e4_session[0]], e4_session[1], 'section'))],
                      target__lesion=[fact('L1', src(['S11'], 'A 5 mm polyp'))],
                      target__places=[fact('sigmoid_colon', src(['S11'], 'sigmoid colon'))],
                      technique__device=[fact('cold_snare', src(['S11'], 'cold snare'))])])


def inputs() -> dict:
    """{name: (text, answer, kind)}: each input a later ruling reaches ('change') and the controls none reaches."""
    return {
        'g5: reached_anatomy at the snare': (NOTE, g5_answer(['S7'], 'sigmoid colon', 'other_statement'), 'change'),
        'g5: reached_anatomy in the examination': (NOTE, g5_answer(['S6'], 'advanced to the cecum'), 'control'),
        'frame: labelled header under a title': (R2ET_HEADER, header_answer(), 'change'),
        'frame: labelled header, no title line': (R2ET_LABEL_FIRST, label_first_answer(), 'change'),
        'parts: each act at its part heading': (R2ET_PARTS, parts_answer(), 'change'),
        'parts: each act at its own section start': (R2ET_PARTS, parts_answer(('S6', 'FINDINGS:'), ('S10', 'FINDINGS:')),
                                                     'control'),
    }


def inputs_sha256() -> str:
    return hashlib.sha256(json.dumps({name: [text, value] for name, (text, value, _) in inputs().items()},
                                     sort_keys=True).encode('utf-8')).hexdigest()


# --- reading and checking as the recorded label reads -------------------------------------------------------------

def read(value: dict, text: str) -> xr.ReadAnswer:
    """``value`` read as the recorded pass-1 label reads it (extract_read's default, gemini-events@2), under the
    computed LOCAL_SCHEMA_2 pin."""
    with mock.patch.object(interpretation, 'LOCAL_SCHEMA_SHA256_V2', jsonschema.sha256_of(xs.LOCAL_SCHEMA_2)):
        found = xr.read(json.dumps(value), len(geometry.Layout.of(text).units))
    if not isinstance(found, xr.ReadAnswer):
        raise AssertionError(f'refused: {getattr(found, "reason", found)}')
    return found


def takes_label() -> bool:
    """Whether this tree's checks take a label (the recorded tree's have one rule and take none)."""
    return 'inventory_version' in inspect.signature(checks.check).parameters


def check_for(value: dict, text: str, inventory_version: str | None):
    """checks.check over ``value`` read under gemini-events@2, made for ``inventory_version`` (None: no label named)."""
    named = {} if inventory_version is None or not takes_label() else {'inventory_version': inventory_version}
    return checks.check(text, (), read(value, text), **named)


def _key(key) -> list:
    return [str(key.family.value), key.object, str(key.attribute.value), key.index]


def whole_sha256(checked) -> str:
    """The sha256 of what the checks found: every finding, failed link, stored literal, K8 group and the reference date
    (canonical JSON; as tests/v2/test_r2dr_records3.whole_sha256 reads a Checked)."""
    def source(item) -> list:
        return [list(item.units), item.words, str(item.link.value)]
    whole = {'findings': sorted([*_key(key), sorted(str(reason.value) for reason in reasons)]
                                for key, reasons in checked.findings.items()),
             'failed_links': sorted([*_key(key), [source(item) for item in found]]
                                    for key, found in checked.failed_links.items()),
             'joined': [[[_key(key) for key in supported], [_key(key) for key in negated]]
                        for supported, negated in checked.joined],
             'literals': sorted([*_key(key), [[item.value, str(item.precision.value)] for item in found]]
                                for key, found in checked.literals.items()),
             'document_date': str(checked.document_date)}
    return hashlib.sha256(json.dumps(whole, sort_keys=True).encode('utf-8')).hexdigest()


def findings(checked, family, name: str, attribute) -> tuple:
    return checked.findings.get(xr.FactKey(family, name, attribute, 0), ())


def recorded_request(text: str, value: dict, inventory_version: str | None) -> dict:
    """The dormant (Gemini) adapter's pass-2 request for ``text`` and ``value``: built from pass 1's request and a
    synthetic stored answer (``value`` in a Gemini envelope) with the checks made for ``inventory_version``, as a
    recorded Gemini case-run's pass2 request sha256 names it (the replay tools' paste: one page per span)."""
    from studio import jobs
    from studio.ingest.extract import extract_paste
    from studio.interpretation import adapter
    from studio.types import PageSpan
    result = extract_paste(text, limits=jobs._limits())
    assert result.text == text, 'the paste changed the text; its unit ids would not be the answer\'s'
    spans = sorted(result.pages, key=lambda span: span.start)
    tiled: list = []
    for index, span in enumerate(spans):
        end = spans[index + 1].start if index + 1 < len(spans) else len(result.text)
        tiled.append(PageSpan(page=span.page, start=tiled[-1].end if tiled else 0, end=end))
    pages = tuple(tiled)
    first = adapter.build_extraction_request(text, pages, 'paste')
    body = json.dumps({'candidates': [{'content': {'parts': [{'text': json.dumps(value)}], 'role': 'model'},
                                       'finishReason': 'STOP', 'index': 0}],
                       'usageMetadata': {'promptTokenCount': 31000, 'candidatesTokenCount': 2100,
                                         'totalTokenCount': 33100},
                       'modelVersion': adapter.MODEL, 'responseId': 'synthetic-r2et-0001'}).encode()
    named = {} if inventory_version is None or not takes_label() else {'inventory_version': inventory_version}
    with mock.patch.object(interpretation, 'LOCAL_SCHEMA_SHA256_V2', jsonschema.sha256_of(xs.LOCAL_SCHEMA_2)):
        second = adapter.build_appraisal_request(text, pages, 'paste', first, body,
                                                 check=lambda t, p, a: checks.check(t, p, a, **named).findings)
    return {'pass2_sha256': second.request.canonical_sha256, 'claims': len(second.built.claim_set.claims)}


def recorded_case(text: str, value: dict, inventory_version: str | None) -> dict:
    """What RECORDED_FIXTURE holds per input: the whole Checked's sha256 and the dormant adapter's pass-2 request."""
    return {'whole_sha256': whole_sha256(check_for(value, text, inventory_version)),
            **recorded_request(text, value, inventory_version)}


def write_recorded(path: Path = RECORDED_FIXTURE) -> None:
    """RECORDED_FIXTURE's owning function: what the RECORDED tree makes for each input of ``inputs`` - the whole
    Checked's sha256 and the dormant adapter's pass-2 request (its canonical sha256, its claim count). Run it in the
    tree every gemini-inventory@2 batch was recorded with (195e06e90), whose checks have one rule and take no label: it
    refuses a tree whose checks.check takes ``inventory_version``."""
    if takes_label():
        raise RuntimeError('The recorded outputs are written in the recorded tree, whose checks take no label.')
    contract = Path(inspect.getfile(checks)).parent
    out = {'inputs_sha256': inputs_sha256(),
           'recorded_checks_sha256': hashlib.sha256((contract / 'checks.py').read_bytes()).hexdigest(),
           'recorded_geometry_sha256': hashlib.sha256((contract / 'geometry.py').read_bytes()).hexdigest(),
           'cases': {name: recorded_case(text, value, None) for name, (text, value, _) in inputs().items()}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=0, sort_keys=True) + '\n', encoding='utf-8')


def recorded() -> dict:
    return json.loads(RECORDED_FIXTURE.read_text(encoding='utf-8'))


# --- RDRX-1, rule by rule ------------------------------------------------------------------------------------------

class R2ETRecordedG5Tests(SimpleTestCase):
    """DECISIONS D303 RDRX-1, G5: findings made for gemini-inventory@2 read G5's attributes as recorded (without
    reached_anatomy, which D292's U3 added after the label's first recording)."""

    def reasons(self, value: dict, label: str | None, attribute=A.REACHED_ANATOMY) -> tuple:
        return findings(check_for(value, NOTE, label), F.SESSION, 'X1', attribute)

    def test_reached_anatomy_at_an_acts_words_is_inferred_only_under_the_current_label(self):
        for link in ('other_statement', 'statement'):
            value = g5_answer(['S7'], 'sigmoid colon', link)
            with self.subTest(link=link):
                self.assertNotIn(R.EXTENT_INFERRED, self.reasons(value, INV2))  # as recorded
                self.assertIn(R.EXTENT_INFERRED, self.reasons(value, INV3))
                self.assertIn(R.EXTENT_INFERRED, self.reasons(value, None))  # the default is the current label
        # the attributes the recorded label reads: the recorded tree's (geometry.EXTENT_ATTRIBUTES before D292's U3)
        self.assertEqual(checks.RECORDED_EXTENT_ATTRIBUTES,
                         (A.REACHED, A.COMPLETION, A.STATIONS, A.APPROACH, A.THROUGH))
        self.assertEqual(set(geometry.EXTENT_ATTRIBUTES) - set(checks.RECORDED_EXTENT_ATTRIBUTES), {A.REACHED_ANATOMY})

    def test_the_examinations_words_and_a_recorded_attribute_read_alike_under_both_labels(self):
        """The boundaries: reached_anatomy in the examination's statement passes G5 under both labels, and the reach -
        an attribute gemini-inventory@2 was recorded with - cited at the snare's sentence is extent_inferred under both."""
        examination = g5_answer(['S6'], 'advanced to the cecum')
        reach = g5_answer(['S7'], 'sigmoid colon', attribute='reached')
        for label in (INV2, INV3):
            with self.subTest(label=label):
                self.assertEqual(self.reasons(examination, label), ())
                self.assertIn(R.EXTENT_INFERRED, self.reasons(reach, label, A.REACHED))


FRAMED = ((F.ENCOUNTER, '', A.DATE_OF_SERVICE), (F.ENCOUNTER, '', A.DOCUMENTING_CLINICIAN), (F.SECTION, 'N3', A.OWNER),
          (F.SECTION, 'N3', A.OCCASION), (F.SECTION, 'N3', A.PERFORMER), (F.SESSION, 'X1', A.ENCOUNTER))


class R2ETRecordedFramePartTests(SimpleTestCase):
    """DECISIONS D303 RDRX-1, G1's document_frame: findings made for gemini-inventory@2 read it in N0's span alone (no
    frame part, which D295 and D300 added after the label's first recording)."""

    def test_a_labelled_header_frames_only_under_the_current_label(self):
        for name, text, value in (('titled', R2ET_HEADER, header_answer()),
                                  ('no title line', R2ET_LABEL_FIRST, label_first_answer())):
            recorded_reading, current = check_for(value, text, INV2), check_for(value, text, INV3)
            for family, object_id, attribute in FRAMED:
                with self.subTest(note=name, fact=(object_id, attribute.value)):
                    self.assertIn(R.GEOMETRY_DOCUMENT_FRAME, findings(recorded_reading, family, object_id, attribute))
                    self.assertNotIn(R.GEOMETRY_DOCUMENT_FRAME, findings(current, family, object_id, attribute))

    def test_a_date_line_after_the_acts_frames_nothing_under_either_label(self):
        """The boundary: the date line of the addendum (S10), told after the acts, lies in no frame part either way."""
        value = header_answer('S10', '03/14/2031')
        for label in (INV2, INV3):
            with self.subTest(label=label):
                self.assertIn(R.GEOMETRY_DOCUMENT_FRAME,
                              findings(check_for(value, R2ET_HEADER, label), F.ENCOUNTER, '', A.DATE_OF_SERVICE))


SESSION_OF = (('E2', A.SESSION), ('E4', A.SESSION))


class R2ETRecordedProcedurePartTests(SimpleTestCase):
    """DECISIONS D303 RDRX-1, G1's section: findings made for gemini-inventory@2 read it at the containing section's own
    start or closing source (no procedure part, which D299 added after the label's first recording)."""

    def sessions(self, value: dict, label: str) -> dict:
        found = check_for(value, R2ET_PARTS, label)
        return {name: findings(found, F.EVENT, name, attribute) for name, attribute in SESSION_OF}

    def test_an_act_citing_its_parts_heading_passes_only_under_the_current_label(self):
        self.assertEqual(self.sessions(parts_answer(), INV2), {'E2': (R.GEOMETRY_SECTION,), 'E4': (R.GEOMETRY_SECTION,)})
        self.assertEqual(self.sessions(parts_answer(), INV3), {'E2': (), 'E4': ()})

    def test_its_own_section_start_passes_and_another_parts_heading_fails_under_both_labels(self):
        own = parts_answer(('S6', 'FINDINGS:'), ('S10', 'FINDINGS:'))
        other = parts_answer(e4_session=('S4', 'PART 1: UPPER ENDOSCOPY'))
        for label in (INV2, INV3):
            with self.subTest(label=label):
                self.assertEqual(self.sessions(own, label), {'E2': (), 'E4': ()})
                self.assertEqual(self.sessions(other, label)['E4'], (R.GEOMETRY_SECTION,))


class R2ETRecordedTreeTests(SimpleTestCase):
    """DECISIONS D303 RDRX-1, against the recorded tree itself: the whole Checked made for gemini-inventory@2, and the
    dormant adapter's pass-2 request built with it, are the RECORDED tree's for every input (RECORDED_FIXTURE)."""

    def test_the_fixture_was_written_for_these_inputs_by_the_recorded_tree(self):
        found = recorded()
        self.assertEqual(found['inputs_sha256'], inputs_sha256())
        self.assertEqual(sorted(found['cases']), sorted(inputs()))
        contract = Path(inspect.getfile(checks)).parent
        self.assertNotEqual(found['recorded_checks_sha256'],
                            hashlib.sha256((contract / 'checks.py').read_bytes()).hexdigest())  # another tree's

    def test_the_recorded_label_reads_and_rebuilds_as_the_recorded_tree(self):
        cases = recorded()['cases']
        for name, (text, value, _) in inputs().items():
            with self.subTest(case=name):
                self.assertEqual(recorded_case(text, value, INV2), cases[name])

    def test_the_current_label_differs_where_a_later_ruling_reaches_and_nowhere_else(self):
        cases = recorded()['cases']
        for name, (text, value, kind) in inputs().items():
            with self.subTest(case=name, kind=kind):
                current = recorded_case(text, value, INV3)
                self.assertEqual(current['whole_sha256'] == cases[name]['whole_sha256'], kind == 'control')
                self.assertEqual(current['pass2_sha256'] == cases[name]['pass2_sha256'], kind == 'control')

    def test_the_inputs_are_not_moved_by_a_copy(self):
        """The fixture's inputs are built afresh each time (a test that mutated one would move the others)."""
        first = inputs()
        second = copy.deepcopy(first)
        for name in first:
            first[name][1]['sessions'] = []
        self.assertNotEqual(first, inputs())
        self.assertEqual(second, inputs())
