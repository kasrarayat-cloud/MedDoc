"""Repair round r2b, builder records2 (DECISIONS D297 R2RX-1 and R2RX-2). TEXT-ONLY and SYNTHETIC: the note below is
written here (no real patient), and nothing is sent.

R2RX-1 - whenever findings are made for gemini-inventory@2 (the label recorded before AMENDMENT-2), EVERY K rule
AMENDMENT-2 4.3.3 widened reads a slot as that label was recorded, not only K2's date arm (D294 F2): K1's status against
timing, K2's examination-link, kind and date arms, K3, K4's type and organ, and K5's performer, person, role and
documenting clinician read a fact's value only when it is supported (pass 1's own contradiction states no value), and
K2's examination link is named by a supported session of that value or a contradiction offering it as a side. Under
gemini-inventory@3 (the current path, the default) every rule reads every value a fact states or offers, as before.
consistency.check takes the label (``inventory_version``) and every K rule reads through that label's
consistency._Reading.

R2RX-2 - whenever a label's recorded rule is kept beside a newer one, a test pins the kept arm against the RECORDED
tree's outputs over every state pair: GRIDS puts each slot every kept arm reads in every state it can take (supported -
two values where two can differ -, negated, contradicted, and silent where the slot can be silent), each against each
on the slots the arm compares (two denials included: a value denied on both sides, and two different values denied),
and RECORDED_FIXTURE holds the K findings (K1's structure_<rule> reasons and K2-K7's) the recorded tree (0a5f3283b, the
tree gemini-inventory@2 produced, with no label) made for every case: ``write_recorded``, the fixture's owning
function, is run in that tree and refuses to run in a tree whose checks take a label. The pin compares K findings;
L1, which DECISIONS D301 RBRX-1 makes read as recorded under gemini-inventory@2 too, is pinned against the recorded
tree by tests/v2/test_r2dr_records3.py.

Each case's answer is read under gemini-events@2 (extract_read's default, the recorded pass-1 label: an overfilled slot
is refused whole there) and checked by contract/checks.check, the orchestration settle and claims read."""
from __future__ import annotations

import hashlib
import inspect
import itertools
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation.contract import checks, geometry, jsonschema
from studio.interpretation.contract import extract_read as xr
from studio.interpretation.contract import extract_schema as xs

INV2 = interpretation.INVENTORY_VERSION_V2
RECORDED_FIXTURE = (Path(__file__).resolve().parents[1] / 'fixtures' / 'interpretation_v2' / 'r2br_records2'
                    / 'recorded_k_rules.json')
# the reasons of the K rules: K1's are types.Reason's structure_<rule> members, K2-K7's these (consistency.Findings)
K_REASONS = frozenset({'session_inconsistent', 'session_conflict', 'session_unreachable', 'anatomy_conflict',
                       'person_conflict', 'instrument_conflict', 'frame_role'})

# --- the synthetic note and its answer -------------------------------------------------------------------------------

R2BR_EGD = ('SYNTHETIC EGD REPORT\n'                                                # S1
            'Date of service: 05/20/2031\n'                                           # S2
            'Findings: The gastroscope was advanced to the duodenum.\n'               # S3
            'A 5 mm polyp in the gastric antrum was removed with a cold snare.\n'     # S4
            'A clip was placed at the polypectomy site.\n')                           # S5


def src(*units: str, words: str = '', link: str = 'statement') -> dict:
    return {'units': list(units), 'words': words, 'link': link}


def fact(value: str, unit: str, state: str = 'supported', link: str = 'statement') -> dict:
    return {'state': state, 'value': value, 'qualifiers': [], 'sources': [src(unit, link=link)], 'options': []}


def contradicted(sides: list, unit: str) -> dict:
    return {'state': 'contradicted', 'value': '', 'qualifiers': [], 'sources': [src(unit) for _ in sides],
            'options': [{'value': value, 'sources': [src(unit)]} for value in sides]}


def stated(spec: str, unit: str, link: str = 'statement') -> dict:
    """One fact from a spec: 'v' supported, '-v' negated, 'a|b' pass 1's own contradiction of a and b."""
    if '|' in spec:
        return contradicted(spec.split('|'), unit)
    if spec.startswith('-'):
        return fact(spec[1:], unit, 'negated', link)
    return fact(spec, unit, link=link)


def slot(spec: str, unit: str, link: str = 'statement') -> list:
    """A slot from a spec: '' silent, else one fact (``stated``)."""
    return [] if spec == '' else [stated(spec, unit, link)]


def places(spec: str, unit: str) -> list:
    """An act's target places from a spec: '' none, else each comma-separated place a fact (``stated``)."""
    return [] if spec == '' else [stated(part, unit) for part in spec.split(',')]


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


def event(id: str, unit: str, kind: dict, status: dict, kind_words: str, status_words: str, **fields) -> dict:
    item = {'id': id, 'anchor': {'units': [unit], 'kind_words': kind_words, 'status_words': status_words},
            'restatements': [], 'kind': kind, 'other_class': [], 'status': status, 'session': [], 'date_relation': [],
            'date': [], 'performer': [], 'performer_person': [],
            'target': {'lesion': [], 'structure': [], 'places': [], 'anatomy': [], 'duct': []},
            'technique': {'device': [], 'route': []}, 'purpose': [], 'cause': [], 'cause_event': [], 'part_of': [],
            'part_relation': [], 'yield': [], 'access_outcome': [],
            'scope': {'breadth': [], 'targets': [], 'segment': [], 'covers': [], 'excepts': []},
            'visit': {'basis': [], 'separately_identifiable': []}}
    for name, value in fields.items():
        if '__' in name:
            outer, inner = name.split('__')
            item[outer][inner] = value
        else:
            item[name] = value
    return item


# Every slot the grids set, and its value when a case does not set it: one EGD session X1 (a second, X2, beside it)
# whose examination E1 is told in the Findings part N1 and inherits N1's occasion; the snare E2 and the clip E3 in X1.
DEFAULTS = {
    'e2_status': 'performed', 'e2_kind': 'snare', 'e2_session': 'X1', 'e2_rel': '', 'e2_places': '',
    'e2_performer': '', 'e2_person': '', 'e1_rel': '', 'e1_session': 'X1', 'e3_session': 'X1', 'n1_occ':
    'on_date_of_service', 'x1_exam': 'E1', 'x1_kind': 'egd', 'y1_type': '', 'y1_organ': '', 'p1_role':
    'documenting_clinician', 'documenting': '',
}


def answer(**spec: str) -> dict:
    """R2BR_EGD's pass-1 answer, each slot ``spec`` names set from its spec (DEFAULTS for the rest). A person P1 and a
    person P2 (role referring) are named in the title unit; an anatomy entry Y1 exists only when y1_type is given."""
    s = {**DEFAULTS, **spec}
    unknown = set(spec) - set(DEFAULTS)
    if unknown:
        raise KeyError(sorted(unknown))
    frame = 'document_frame'
    anatomy = ([{'id': 'Y1', 'type': stated(s['y1_type'], 'S4'), 'organ': slot(s['y1_organ'], 'S4'), 'subtype': [],
                 'joins': []}] if s['y1_type'] else [])
    return {
        'encounter': {'date_of_service': {'state': 'stated', 'value': '2031-05-20',
                                          'sources': [src('S2', words='05/20/2031', link=frame)], 'options': []},
                      'other_dates': [], 'documenting_clinician': slot(s['documenting'], 'S1', frame)},
        'people': [{'id': 'P1', 'name': src('S1'), 'role': stated(s['p1_role'], 'S1')},
                   {'id': 'P2', 'name': src('S1'), 'role': fact('referring', 'S1')}],
        'sections': [
            section('N0', src(link='section'), fact('documenting_clinician', 'S1', link=frame),
                    role=[fact('header', 'S1', link='section')],
                    occasion=[{**fact('on_date_of_service', 'S2', link=frame),
                               'sources': [src('S2', words='05/20/2031', link=frame)]}]),
            section('N1', src('S3', words='Findings:', link='section'), fact('documenting_clinician', 'S1', link=frame),
                    role=[{**fact('findings', 'S3', link='section'),
                           'sources': [src('S3', words='Findings:', link='section')]}],
                    occasion=slot(s['n1_occ'], 'S2'))],
        'sessions': [session('X1', stated(s['x1_kind'], 'S1', frame), examination=slot(s['x1_exam'], 'S3')),
                     session('X2', fact('egd', 'S1', link=frame))],
        'anatomy': anatomy, 'lesions': [],
        'events': [event('E1', 'S3', fact('examination', 'S3'), fact('performed', 'S3'), 'gastroscope', 'was advanced',
                         session=slot(s['e1_session'], 'S3'), date_relation=slot(s['e1_rel'], 'S3')),
                   event('E2', 'S4', stated(s['e2_kind'], 'S4'), stated(s['e2_status'], 'S4'), 'cold snare',
                         'was removed', session=slot(s['e2_session'], 'S4'), date_relation=slot(s['e2_rel'], 'S4'),
                         performer=slot(s['e2_performer'], 'S4'), performer_person=slot(s['e2_person'], 'S4'),
                         target__places=places(s['e2_places'], 'S4')),
                   event('E3', 'S5', fact('clip', 'S5'), fact('performed', 'S5'), 'clip', 'was placed',
                         session=slot(s['e3_session'], 'S5'))],
        'doubts': [],
    }


# --- the grids: every state of every slot a kept @2 arm reads, each against each on the slots it compares -----------

ON, EARLIER, LATER = 'on_date_of_service', 'earlier_date', 'later_date'
# a date relation slot in every state: silent, supported (three values), negated (two values), contradicted (two pairs)
RELATIONS = ('', ON, EARLIER, LATER, f'-{ON}', f'-{EARLIER}', f'{ON}|{EARLIER}', f'{EARLIER}|{LATER}')
GRIDS: dict[str, dict[str, tuple[str, ...]]] = {
    # K1 status against timing: the act's status (a FACT: never silent) x its own date relation
    'k1_status_time': {
        'e2_status': ('performed', 'planned', 'attempted_not_completed', '-performed', '-planned',
                      'performed|planned', 'planned|attempted_not_completed', 'performed|attempted_not_completed'),
        'e2_rel': ('', ON, EARLIER, LATER, f'-{ON}', f'-{EARLIER}', f'-{LATER}', f'{LATER}|{EARLIER}',
                   f'{ON}|{LATER}', f'{ON}|{EARLIER}'),
    },
    # K2's date arm: the act's own relation x its examination's own relation (the examination's session link stated)
    'k2_date_own': {'e2_rel': RELATIONS, 'e1_rel': RELATIONS},
    # K2's date arm: the act's own relation x the occasion the examination inherits (its own relation silent)
    'k2_date_inherited': {'e2_rel': RELATIONS, 'n1_occ': RELATIONS},
    # K2's date arm: the ids it reads - the act's session x that session's examination link - for a conflicting and a
    # contradicted own relation
    'k2_date_ids': {'e2_session': ('', 'X1', 'X2', '-X1', 'X1|X2'),
                    'x1_exam': ('', 'E1', 'E3', 'E2', '-E1', 'E1|E3'),
                    'e2_rel': (EARLIER, f'{ON}|{EARLIER}')},
    # K2's examination-link arm: the session's link x the linked examination's session (E1 or E3)
    'k2_link': {'x1_exam': ('', 'E1', 'E3', '-E1', 'E1|E3', 'E9'),
                'e1_session': ('', 'X1', 'X2', '-X1', '-X2', 'X1|X2', 'X2|X1'),
                'e3_session': ('', 'X1', '-X1', 'X1|X2')},
    # K2's kind arm: the act's kind (a FACT) x its session x that session's kind (a FACT)
    'k2_kind': {'e2_kind': ('snare', 'sphincterotomy', '-snare', 'snare|sphincterotomy'),
                'e2_session': ('', 'X1', 'X2', '-X1', 'X1|X2'),
                'x1_kind': ('egd', 'ercp', '-egd', 'egd|ercp')},
    # K3: the act's session x that session's kind x the act's places (supported or not)
    'k3_reach': {'e2_session': ('', 'X1', 'X2', '-X1', 'X1|X2'),
                 'x1_kind': ('egd', 'colonoscopy', '-egd', 'egd|colonoscopy'),
                 'e2_places': ('', 'stomach', 'cecum', '-cecum', 'stomach,cecum')},
    # K4: the entry's type (a FACT) x its organ x the act's places
    'k4_absent': {'y1_type': ('surgically_absent', 'anastomosis', '-surgically_absent',
                              'surgically_absent|anastomosis'),
                  'y1_organ': ('', 'stomach', 'colon', '-stomach', 'stomach|esophagus'),
                  'e2_places': ('', 'stomach', 'gastric_antrum', '-stomach')},
    # K5: the act's performer x its person x the person's role (a FACT) x the documenting clinician
    'k5_person': {'e2_performer': ('', 'documenting_team', 'other_clinician', '-documenting_team',
                                   'documenting_team|other_clinician'),
                  'e2_person': ('', 'P1', 'P2', '-P1', 'P1|P2'),
                  'p1_role': ('documenting_clinician', 'nurse', 'referring', '-documenting_clinician',
                              'documenting_clinician|referring'),
                  'documenting': ('', 'P1', 'P2', '-P1', 'P1|P2')},
}


def cases() -> dict[str, dict[str, str]]:
    """Every case of GRIDS, by id ('<grid>/<slot>=<spec>/...'), in a fixed order."""
    out = {}
    for name, grid in GRIDS.items():
        slots = list(grid)
        for values in itertools.product(*(grid[item] for item in slots)):
            spec = dict(zip(slots, values))
            out[name + '/' + '/'.join(f'{item}={value}' for item, value in spec.items())] = spec
    return out


def read(value: dict) -> xr.ReadAnswer:
    """``value`` read as the recorded pass-1 label reads it (extract_read's default, gemini-events@2), under the
    computed LOCAL_SCHEMA_2 pin."""
    with mock.patch.object(interpretation, 'LOCAL_SCHEMA_SHA256_V2', jsonschema.sha256_of(xs.LOCAL_SCHEMA_2)):
        found = xr.read(json.dumps(value), len(geometry.Layout.of(R2BR_EGD).units))
    if not isinstance(found, xr.ReadAnswer):
        raise AssertionError(f'refused: {getattr(found, "reason", found)}')
    return found


def k_findings(checked) -> list:
    """The K findings of a Checked: [family, object, attribute, index, [reasons]] for each fact with a K1 structure
    reason or a K2-K7 reason, those reasons only, sorted."""
    rows = []
    for key, reasons in checked.findings.items():
        kept = sorted(str(reason.value) for reason in reasons
                      if str(reason.value).startswith('structure_') or str(reason.value) in K_REASONS)
        if kept:
            rows.append([str(key.family.value), key.object, str(key.attribute.value), key.index, kept])
    return sorted(rows)


def grid_sha256() -> str:
    """The sha256 of the grid (every case id, in order) and of every answer the generator builds."""
    digest = hashlib.sha256()
    for case_id, spec in cases().items():
        digest.update(case_id.encode('utf-8') + b'\0' + json.dumps(answer(**spec), sort_keys=True).encode('utf-8'))
    return digest.hexdigest()


def write_recorded(path: Path = RECORDED_FIXTURE) -> None:
    """RECORDED_FIXTURE's owning function: the K findings the RECORDED tree makes for every case of GRIDS. Run it in the
    tree gemini-inventory@2 produced (0a5f3283b), whose checks have one rule and take no label: it refuses a tree whose
    checks.check takes ``inventory_version``."""
    if 'inventory_version' in inspect.signature(checks.check).parameters:
        raise RuntimeError('The recorded outputs are written in the recorded tree, whose checks take no label.')
    consistency = Path(inspect.getfile(checks)).with_name('consistency.py')
    out = {'grid_sha256': grid_sha256(),
           'recorded_consistency_sha256': hashlib.sha256(consistency.read_bytes()).hexdigest(),
           'cases': {case_id: k_findings(checks.check(R2BR_EGD, (), read(answer(**spec))))
                     for case_id, spec in cases().items()}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=0, sort_keys=True) + '\n', encoding='utf-8')


def check_for(value: dict, inventory_version: str | None):
    """checks.check over ``value`` read under gemini-events@2, made for ``inventory_version`` (None: no label named,
    the default every unnamed caller gets)."""
    named = {} if inventory_version is None else {'inventory_version': inventory_version}
    return checks.check(R2BR_EGD, (), read(value), **named)


def on(spec: dict, inventory_version: str | None, family: str, object_id: str, attribute: str) -> set:
    """The K reasons on one fact of ``answer(**spec)``, for ``inventory_version``."""
    return {reason for row in k_findings(check_for(answer(**spec), inventory_version))
            if row[:3] == [family, object_id, attribute] for reason in row[4]}


# --- R2RX-1: every widened K rule reads gemini-inventory@2 as recorded -------------------------------------------------

class R2BRRecordedReadingTests(SimpleTestCase):
    """DECISIONS D297 R2RX-1: one input each rule must change (pass 1's own contradiction, which the recorded label
    read as stating no value) and one boundary each must leave alone (a supported value fires the rule under both
    labels; gemini-inventory@3 and the unnamed default read every value a fact states or offers, as before)."""
    INV3 = getattr(interpretation, 'INVENTORY_VERSION_V3', 'gemini-inventory@3')

    def assertReads(self, spec: dict, where: tuple, reason: str, *, recorded: bool, current: bool) -> None:
        self.assertEqual(reason in on(spec, INV2, *where), recorded, f'gemini-inventory@2 on {where}')
        self.assertEqual(reason in on(spec, self.INV3, *where), current, f'gemini-inventory@3 on {where}')
        self.assertEqual(reason in on(spec, None, *where), current, f'no label on {where}')

    def test_k1_status_against_timing_reads_a_contradiction_as_no_value_under_the_recorded_label(self):
        where = ('events', 'E2', 'date_relation')
        for spec in ({'e2_status': 'performed|planned', 'e2_rel': LATER},
                     {'e2_status': 'performed', 'e2_rel': f'{ON}|{LATER}'},
                     {'e2_status': 'planned|attempted_not_completed', 'e2_rel': f'{LATER}|{EARLIER}'}):
            with self.subTest(**spec):
                self.assertReads(spec, where, 'structure_status_time', recorded=False, current=True)
        for spec in ({'e2_status': 'performed', 'e2_rel': LATER}, {'e2_status': 'planned', 'e2_rel': EARLIER}):
            with self.subTest(boundary=spec):  # a supported status and a supported relation: both labels fire
                self.assertReads(spec, where, 'structure_status_time', recorded=True, current=True)
        with self.subTest(boundary='negated relation'):  # a denial is no value under either label
            self.assertReads({'e2_status': 'performed', 'e2_rel': f'-{LATER}'}, where, 'structure_status_time',
                             recorded=False, current=False)

    def test_k2_examination_link_reads_as_recorded(self):
        where = ('sessions', 'X1', 'examination')
        # a contradicted link: the recorded label named no examination; a link to an examination whose session is
        # pass 1's own contradiction offering the session: the recorded label read it as naming the session
        for spec in ({'x1_exam': 'E1|E3', 'e3_session': 'X1|X2'}, {'x1_exam': 'E1', 'e1_session': 'X1|X2'}):
            with self.subTest(**spec):
                self.assertReads(spec, where, 'session_inconsistent', recorded=False, current=True)
        for spec in ({'x1_exam': 'E1', 'e1_session': 'X2'}, {'x1_exam': 'E1', 'e1_session': '-X1'}):
            with self.subTest(boundary=spec):  # another session stated, or this one denied: both labels fire
                self.assertReads(spec, where, 'session_inconsistent', recorded=True, current=True)
        with self.subTest(boundary='the session stated'):
            self.assertReads({'x1_exam': 'E1', 'e1_session': 'X1'}, where, 'session_inconsistent', recorded=False,
                             current=False)

    def test_k2_kind_arm_reads_as_recorded(self):
        where = ('events', 'E2', 'session')
        for spec in ({'e2_kind': 'snare|sphincterotomy'}, {'x1_kind': 'egd|ercp'},
                     {'e2_kind': 'sphincterotomy', 'e2_session': 'X1|X2'}):
            with self.subTest(**spec):
                self.assertReads(spec, where, 'session_inconsistent', recorded=False, current=True)
        with self.subTest(boundary='a supported kind no family admits'):
            self.assertReads({'e2_kind': 'sphincterotomy'}, where, 'session_inconsistent', recorded=True, current=True)

    def test_k2_date_arm_reads_as_recorded(self):
        where = ('events', 'E2', 'session')
        for spec in ({'e2_rel': f'{ON}|{EARLIER}'}, {'e2_rel': EARLIER, 'n1_occ': f'{ON}|{EARLIER}'},
                     {'e2_rel': EARLIER, 'e2_session': 'X1|X2'}, {'e2_rel': EARLIER, 'x1_exam': 'E1|E3'}):
            with self.subTest(**spec):
                self.assertReads(spec, where, 'session_conflict', recorded=False, current=True)
        with self.subTest(boundary='two stated relations that differ'):
            self.assertReads({'e2_rel': EARLIER}, where, 'session_conflict', recorded=True, current=True)
        with self.subTest(boundary='two denials never conflict'):
            self.assertReads({'e2_rel': f'-{ON}', 'n1_occ': f'-{ON}'}, where, 'session_conflict', recorded=False,
                             current=False)

    def test_k3_reads_as_recorded(self):
        where = ('events', 'E2', 'session')
        for spec in ({'e2_places': 'cecum', 'e2_session': 'X1|X2'}, {'e2_places': 'stomach',
                                                                    'x1_kind': 'egd|colonoscopy'}):
            with self.subTest(**spec):
                self.assertReads(spec, where, 'session_unreachable', recorded=False, current=True)
        with self.subTest(boundary='a supported session and kind'):
            self.assertReads({'e2_places': 'cecum'}, where, 'session_unreachable', recorded=True, current=True)

    def test_k4_reads_as_recorded(self):
        where = ('events', 'E2', 'target.places')
        for spec in ({'y1_type': 'surgically_absent', 'y1_organ': 'stomach|esophagus', 'e2_places': 'stomach'},
                     {'y1_type': 'surgically_absent|anastomosis', 'y1_organ': 'stomach', 'e2_places': 'gastric_antrum'}):
            with self.subTest(**spec):
                self.assertReads(spec, where, 'anatomy_conflict', recorded=False, current=True)
        with self.subTest(boundary='a supported absence of the organ'):
            self.assertReads({'y1_type': 'surgically_absent', 'y1_organ': 'stomach', 'e2_places': 'gastric_antrum'},
                             where, 'anatomy_conflict', recorded=True, current=True)

    def test_k5_reads_as_recorded(self):
        where = ('events', 'E2', 'performer')
        for spec in ({'e2_performer': 'documenting_team|other_clinician', 'e2_person': 'P2'},
                     {'e2_performer': 'other_clinician', 'e2_person': 'P1|P2'},
                     {'e2_performer': 'documenting_team', 'e2_person': 'P1', 'p1_role': 'documenting_clinician|referring'},
                     {'e2_performer': 'other_clinician', 'e2_person': 'P1', 'p1_role': 'nurse', 'documenting': 'P1|P2'}):
            with self.subTest(**spec):
                self.assertReads(spec, where, 'person_conflict', recorded=False, current=True)
        for spec in ({'e2_performer': 'documenting_team', 'e2_person': 'P2'},
                     {'e2_performer': 'other_clinician', 'e2_person': 'P1', 'p1_role': 'nurse', 'documenting': 'P1'}):
            with self.subTest(boundary=spec):
                self.assertReads(spec, where, 'person_conflict', recorded=True, current=True)

    def test_the_label_chooses_one_reading_for_every_k_rule(self):
        from studio.interpretation.contract import consistency as cs
        self.assertIs(cs._reading(INV2), cs._RECORDED)
        for label in (self.INV3, 'gemini-inventory@1', 'gemini-inventory@4', ''):  # every other label: the newer
            with self.subTest(label=label):
                self.assertIs(cs._reading(label), cs._OFFERED)
        self.assertEqual(inspect.signature(cs.check).parameters['inventory_version'].default, self.INV3)

    def test_no_answer_read_under_the_recorded_pass_1_label_holds_a_merged_view(self):
        """The premise of the recorded reading: gemini-events@2 refuses an overfilled slot whole (AMENDMENT-2 4.3.1), so
        the reading never meets a merged view; gemini-events@3 reads one."""
        value = answer()
        value['events'][1]['session'] = [fact('X1', 'S4'), fact('X2', 'S4')]
        with mock.patch.object(interpretation, 'LOCAL_SCHEMA_SHA256_V2', jsonschema.sha256_of(xs.LOCAL_SCHEMA_2)):
            units = len(geometry.Layout.of(R2BR_EGD).units)
            self.assertIsInstance(xr.read(json.dumps(value), units), xr.Refusal)
            self.assertIsInstance(xr.read(json.dumps(value), units, version=interpretation.INTERPRETATION_VERSION_V3),
                                  xr.ReadAnswer)


# --- R2RX-2: the kept arm against the recorded tree's outputs over every state pair ---------------------------------

class R2BRKeptArmPinTests(SimpleTestCase):
    """DECISIONS D297 R2RX-2: for every case of GRIDS, the K findings made for gemini-inventory@2 equal the K findings
    the recorded tree made (RECORDED_FIXTURE, written there by ``write_recorded``)."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.recorded = json.loads(RECORDED_FIXTURE.read_text(encoding='utf-8'))
        cls.reads = {case_id: read(answer(**spec)) for case_id, spec in cases().items()}  # each case read once

    def k_for(self, case_id: str, inventory_version: str) -> list:
        return k_findings(checks.check(R2BR_EGD, (), self.reads[case_id], inventory_version=inventory_version))

    def test_the_fixture_is_the_recorded_trees_answer_to_this_grid(self):
        self.assertEqual(self.recorded['grid_sha256'], grid_sha256())
        self.assertEqual(sorted(self.recorded['cases']), sorted(cases()))

    def test_every_state_pair_of_every_kept_arm_is_in_the_grid(self):
        """Each grid puts each slot in every state it can take - supported (two values where two can differ),
        negated, contradicted, and silent unless the slot is a FACT - each against each (two denials included)."""
        facts = {'e2_status', 'e2_kind', 'x1_kind', 'y1_type', 'p1_role'}  # FACTs: never silent

        def state(spec: str) -> str:
            return ('silent' if spec == '' else 'contradicted' if '|' in spec else 'negated' if spec.startswith('-')
                    else 'supported')
        for name, grid in GRIDS.items():
            for item, specs in grid.items():
                with self.subTest(grid=name, slot=item):
                    states = {state(spec) for spec in specs}
                    want = {'supported', 'negated', 'contradicted'} | (set() if item in facts else {'silent'})
                    if name == 'k2_date_ids' and item == 'e2_rel':
                        want = {'supported', 'contradicted'}  # the own relation that makes the ids' arm decide
                    if item == 'e2_places':
                        want = {'silent', 'supported', 'negated'}  # places are a list: a contradiction is not one
                    self.assertLessEqual(want, states)
        for name, (left, right) in {'k2_date_own': ('e2_rel', 'e1_rel'),
                                    'k2_date_inherited': ('e2_rel', 'n1_occ')}.items():
            pairs = {(a, b) for a in GRIDS[name][left] for b in GRIDS[name][right]}
            with self.subTest(two_denials=name):
                self.assertIn((f'-{ON}', f'-{ON}'), pairs)  # one value denied on both sides
                self.assertIn((f'-{ON}', f'-{EARLIER}'), pairs)  # two values, each denied

    def test_the_kept_arm_makes_the_recorded_trees_findings_on_every_case(self):
        differ = []
        for case_id in cases():
            found = self.k_for(case_id, INV2)
            if found != self.recorded['cases'][case_id]:
                differ.append((case_id, found, self.recorded['cases'][case_id]))
        self.assertEqual(len(differ), 0, f'{len(differ)} of {len(cases())} cases differ; first: {differ[:5]}')

    def test_the_current_reading_only_adds_findings_to_the_recorded_ones(self):
        """The boundary: gemini-inventory@3 is left as it was - on the same grid it finds every K finding the recorded
        label finds (it only demotes more) and more on pass 1's own contradictions."""
        inv3 = getattr(interpretation, 'INVENTORY_VERSION_V3', 'gemini-inventory@3')
        more = 0
        for case_id in cases():
            recorded = {(*row[:4], reason) for row in self.recorded['cases'][case_id] for reason in row[4]}
            current = {(*row[:4], reason) for row in self.k_for(case_id, inv3) for reason in row[4]}
            with self.subTest(case=case_id):
                self.assertLessEqual(recorded, current)
            more += current > recorded
        self.assertGreater(more, 100)


# --- R2RX-1 at the row: the row the recorded labels' writer makes equals the recorded tree's ---------------------------

# The row sha256 the RECORDED tree (0a5f3283b) writes for each case through tests/v2/test_failure_classes.pipeline - the
# path that writes the recorded labels (pass 1 read at gemini-events@2, the @1 request, a faithful pass 2, settle,
# store.row_v2 at the @2 pair) - measured in that tree (records2/probes/r2br_rows.py): one input per widened rule, and
# the control. Pinned because the recorded tree is the only owner of these values.
RECORDED_ROWS = {
    'control': ({}, 'b80b585c2fb3865bba2abd45e35d07080132e93e84b399782f5fc509394b43b6'),
    'k1_contradicted_relation': ({'e2_rel': f'{ON}|{LATER}'},
                                 'dbbb81bf4aa9a46f34f3983e9aa59e47b67fc148ba6bc5551c807426827c3a6f'),
    'k1_contradicted_status': ({'e2_status': 'performed|planned', 'e2_rel': LATER},
                               'a4a33849fa6b9338b1f9280f60e7d436de161b6bac7ba2503e733250d826bc32'),
    'k2_link_contradicted_session': ({'x1_exam': 'E1', 'e1_session': 'X1|X2'},
                                     '0c2cbfe49c633e96bcaf56b8dd8ef7431d65c5560ea2dab4464ec4b8a415a236'),
    'k2_kind_contradicted_kind': ({'e2_kind': 'snare|sphincterotomy'},
                                  'edb2aba2d0d3a909b1801a6a0a96ae6ad9e44947fbadbdcec97245cb851dbe7a'),
    'k2_date_contradicted_relation': ({'e2_rel': f'{ON}|{EARLIER}'},
                                      '1da6dcde6ceb3f0385a43efe3dd3dc0205019dc68b3c17057995a6b3f6b522ee'),
    'k3_contradicted_session_kind': ({'e2_places': 'stomach', 'x1_kind': 'egd|colonoscopy'},
                                     'c83264803f57917626b2c34204794a5e4fcdcda79580711d64845612da66733d'),
    'k4_contradicted_organ': ({'y1_type': 'surgically_absent', 'y1_organ': 'stomach|esophagus', 'e2_places': 'stomach'},
                              '7d7e49907ace3c57e001a739b43c6fc1f65ed1ab1e0324f50e9ed85e9b3c763d'),
    'k5_contradicted_person': ({'e2_performer': 'other_clinician', 'e2_person': 'P1|P2'},
                               '885e0e613f79a2798b076fc2104ce35b87a90c74252452a0355192f193194398'),
}


class R2BRRecordedRowsTests(SimpleTestCase):
    """The row tests/v2/test_failure_classes.pipeline writes at the recorded labels (its checks made for
    gemini-inventory@2) is byte for byte the recorded tree's, for an input of each widened K rule and the control."""

    def row(self, spec: dict) -> dict:
        import tests.v2.test_failure_classes as FC
        from studio.interpretation import store
        seen = {}
        real = store.row_v2

        def spy(**kwargs):
            seen['fields'] = real(**kwargs)
            return seen['fields']
        text = R2BR_EGD
        s3, s4 = text.index('Findings:'), text.index('A 5 mm polyp')
        data = {'proposals': [{'code': '43235', 'start': s3, 'end': text.index('\n', s3)},
                              {'code': '43251', 'start': s4, 'end': text.index('\n', s4)}],
                'member': None, 'date_of_service': '2031-05-20', 'answers': []}
        with mock.patch.object(store, 'row_v2', spy):
            FC.pipeline(text, answer(**spec), {'default': 'faithful', 'verdicts': [], 'unlisted': []}, data)
        return seen['fields']

    def test_each_row_is_the_recorded_trees(self):
        for name, (spec, sha256) in RECORDED_ROWS.items():
            with self.subTest(case=name):
                fields = self.row(spec)
                self.assertEqual((fields['interpretation_version'], fields['inventory_version']),
                                 (interpretation.INTERPRETATION_PAIR, INV2))
                self.assertEqual(fields['sha256'], sha256)
