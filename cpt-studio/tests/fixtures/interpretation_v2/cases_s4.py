"""S4's 52 failure classes and 21 borderline filings as fixtures (FINAL-V2 9.5, Appendix C; design-v2/survey/failures.json,
read for each class's attested input, attribute and contract). Each case: a synthetic document written for it, pass 1's
right filing and the class's misfiling, the proposal provider's codes, and the expected outcome of (i) and (ii) with the
design's reason. (iii) is recorded, never expected (build.py's docstring)."""
from __future__ import annotations

from tests.fixtures.interpretation_v2.build import Case
from tests.fixtures.interpretation_v2.dsl import Note

R, H, X = 'R', 'H', 'X'
OTHER = 'other_statement'
Q, EXP = 'question', 'explanation'
HEAD_OFFICE = ('SYNTHETIC OFFICE VISIT NOTE\n'
               'Date of service: 03/14/2031\n'
               'Clinician: Corvin Ashdale, MD (fictional)\n'
               '\n')
VISIT = 'The patient was seen in the office today for follow-up of rectal bleeding.\n'
TIME = 'Total time spent on the date of the encounter was 30 minutes.\n'


def office(n: Note, *events: dict, sessions: tuple = (), visit_fields: dict | None = None, sections: tuple = (),
           lesions: tuple = (), anatomy: tuple = (), doubts: tuple = ()) -> dict:
    """An office note's answer: N0 (today, the team, the documenting clinician), the office visit session X1 (this
    encounter) and its visit E1 (total time), then ``sessions`` and ``events``."""
    visit = dict(basis=('total_time', '30 minutes'))
    visit.update(visit_fields or {})
    return n.answer(
        sections=[n.opening(), *sections],
        sessions=[n.session('X1', 'office_em', 'seen in the office', exam='E1',
                            encounter=('this_encounter', 'seen in the office today')), *sessions],
        events=[n.event('E1', 'em_visit', 'seen in the office', 'was seen', session='X1', **visit), *events],
        lesions=lesions, anatomy=anatomy, doubts=doubts, role_words='Clinician')


def head(title: str) -> str:
    return f'SYNTHETIC {title}\nDate of service: 03/14/2031\nEndoscopist: Corvin Ashdale, MD (fictional)\n\n'


def scope(n: Note, kind: str, kind_words: str, exam_words: str, *events: dict, label: str = 'Findings:',
          reached: tuple = (), sections: tuple = (), lesions: tuple = (), anatomy: tuple = (), doubts: tuple = (),
          people: list | None = None, sessions: tuple = (), status_words: str = 'was advanced', exam: dict | None = None,
          **session_fields: object) -> dict:
    """An endoscopy note's answer: N0, the part opened by ``label`` (today, the team, the documenting clinician), the
    session X1 of ``kind`` cited at ``kind_words`` with its examination E1 anchored at ``exam_words``, then
    ``sections``, ``sessions`` and ``events``."""
    first = n.event('E1', 'examination', exam_words, status_words, session='X1') if exam is None else exam
    return n.answer(sections=[n.opening(), n.part('N1', label, 'findings'), *sections],
                    sessions=[n.session('X1', kind, kind_words, exam='E1', reached=list(reached), **session_fields),
                              *sessions],
                    events=[first, *events], lesions=lesions, anatomy=anatomy, doubts=doubts, people=people)


def colo(n: Note, *events: dict, reached: tuple = (('cecum', 'advanced to the cecum'),), **kw: object) -> dict:
    return scope(n, 'colonoscopy', 'colonoscope', 'colonoscope', *events, reached=reached, **kw)


def ercp(n: Note, *events: dict, **kw: object) -> dict:
    return scope(n, 'ercp', 'duodenoscope', 'duodenoscope', *events, reached=(('ampulla', 'major papilla'),), **kw)


def cannulation(n: Note, eid: str = 'E2', words: str = 'Deep biliary cannulation') -> dict:
    """A deep biliary cannulation with a sphincterotome, achieved (R6:cannulation's act)."""
    return n.event(eid, 'cannulation', words, 'was achieved', session='X1', access_outcome='achieved',
                   duct=('biliary', 'biliary'), device=('sphincterotome', 'sphincterotome'))


# --- T: timing -----------------------------------------------------------------------------------------------------------

T1_TEXT = HEAD_OFFICE + VISIT + ('Earlier this AM, I performed a flexible sigmoidoscopy, which showed internal '
                                 'hemorrhoids.\n') + TIME


def t1(n: Note, mis: bool) -> dict:
    return office(n, n.event('E2', 'examination', 'flexible sigmoidoscopy', 'I performed', session='X2',
                             date_relation=('earlier_date' if mis else 'on_date_of_service', 'Earlier this AM'),
                             performer=('documenting_team', 'I performed')),
                  sessions=(n.session('X2', 'flex_sig', 'flexible sigmoidoscopy', exam='E2',
                                      encounter=('separate_encounter', 'Earlier this AM')),))


T2_TEXT = HEAD_OFFICE + VISIT + ('Earlier today, I performed a flexible sigmoidoscopy to 40 cm, which showed internal '
                                 'hemorrhoids.\n') + TIME


def t2(n: Note, mis: bool) -> dict:
    return office(n, n.event('E2', 'examination', 'flexible sigmoidoscopy', 'I performed', session='X2',
                             date_relation=('earlier_date' if mis else 'on_date_of_service', 'Earlier today'),
                             performer=('documenting_team', 'I performed')),
                  sessions=(n.session('X2', 'flex_sig', 'flexible sigmoidoscopy', exam='E2',
                                      encounter=('separate_encounter', 'Earlier today'),
                                      reached=[('stated_depth', 'to 40 cm')]),))


T3_TEXT = HEAD_OFFICE + VISIT + ('At her last visit two weeks ago, I performed a flexible sigmoidoscopy later in the '
                                 'morning, which showed internal hemorrhoids.\n') + TIME


def t3(n: Note, mis: bool) -> dict:
    relation = ('on_date_of_service', 'later in the morning') if mis else \
        ('earlier_date', 'At her last visit two weeks ago')
    return office(n, n.event('E2', 'examination', 'flexible sigmoidoscopy', 'I performed', session='X2',
                             date_relation=relation, performer=('documenting_team', 'I performed')),
                  sessions=(n.session('X2', 'flex_sig', 'flexible sigmoidoscopy', exam='E2',
                                      encounter=('separate_encounter', 'At her last visit')),))


CASES = [
    Case('T1', 'class', ('T1', 'BF1'), 'A same-day act read as another date', T1_TEXT, t1,
         codes=(('99213', 'seen in the office'),), caught=('date_relation@E2/0',),
         expect={'i': {'99213': (H, 'separate_em', Q, '4.7 C-3: the flexible sigmoidoscopy (examination, supported '
                                                     'on the date of service) makes a done procedure day; no '
                                                     'separately identifiable statement')},
                 'ii': {'99213': (H, 'event_time', Q, '4.7 C-3: the act\'s date relation not established makes it '
                                                      'undatable and no act establishes the day (RANK 6)')}}),
    Case('T2', 'class', ('T2', 'BF1'), 'A same-day act\'s own code read as at an earlier encounter', T2_TEXT, t2,
         codes=(('45330', 'flexible sigmoidoscopy'),), caught=('date_relation@E2/0',),
         expect={'i': {'45330': (R, None, None, '4.3 row 3 accepts any act on the date of service (T2, D180); '
                                                'R6:extent met by the stated depth')},
                 'ii': {'45330': (H, 'event_time', Q, '4.3 row 3 unresolved: event_time (RANK 6)')}}),
    Case('T3', 'class', ('T3', 'BF1'), 'Another day\'s act read on the date of service by a same-day frame', T3_TEXT,
         t3, codes=(('99213', 'seen in the office'),), caught=('date_relation@E2/0',),
         expect={'i': {'99213': (R, None, None, '4.7 C-3: the only act is established on an earlier date, so no '
                                                'procedure day and no undatable act')},
                 'ii': {'99213': (H, 'event_time', Q, '4.7 C-3: the act\'s date relation not established: '
                                                      'undatable (RANK 6)')}}),
]


T4_TEXT = HEAD_OFFICE + VISIT + 'Excision of a 1 cm sebaceous cyst on the upper back was performed in the office.\n' + TIME


def t4(n: Note, mis: bool) -> dict:
    return office(n, n.event('E2', 'other', 'Excision', 'was performed', session='X2',
                             other_class=('evaluation' if mis else 'procedure', 'Excision')),
                  sessions=(n.session('X2', 'not_gi', 'sebaceous cyst'),))


T6_TEXT = head('ERCP REPORT') + (
    'Findings: The duodenoscope was advanced to the major papilla.\n'
    'At her index ERCP, a 10 Fr plastic biliary stent was placed in the common bile duct.\n'
    'Deep biliary cannulation was achieved with a sphincterotome.\n'
    'A biliary sphincterotomy was performed.\n'
    'The bile duct was swept with an extraction balloon and two stones were removed.\n')


def t6(n: Note, mis: bool) -> dict:
    stent = n.event('E5', 'stent', 'plastic biliary stent', 'was placed', session='X1', duct=('biliary', 'biliary'),
                    places=[('common_bile_duct', 'common bile duct')],
                    date_relation=None if mis else ('earlier_date', 'At her index ERCP'))
    return ercp(n, cannulation(n),
                n.event('E3', 'sphincterotomy', 'biliary sphincterotomy', 'was performed', session='X1',
                        duct=('biliary', 'biliary')),
                n.event('E4', 'stone_extraction', 'swept with an extraction balloon', 'were removed', session='X1',
                        duct=('biliary', 'bile duct'), device=('extraction_balloon', 'extraction balloon'),
                        **{'yield': ('stones', 'two stones were removed')}),
                stent)


T7_TEXT = head('ERCP REPORT') + (
    'Findings: The duodenoscope was advanced to the major papilla.\n'
    'Deep biliary cannulation was achieved with a sphincterotome.\n'
    'Two stones were removed from the bile duct with an extraction balloon two weeks ago.\n'
    'The bile duct was swept with an extraction balloon and no stones were retrieved.\n')


def t7(n: Note, mis: bool) -> dict:
    earlier = n.event('E3', 'stone_extraction', 'Two stones were removed', 'were removed', session='X1',
                      duct=('biliary', 'from the bile duct'), date_relation=('earlier_date', 'two weeks ago'),
                      **{'yield': ('stones', 'Two stones')})
    sweep_yield = ('stones', 'Two stones were removed') if mis else ('anything', 'no stones were retrieved',
                                                                    'statement', 'negated')
    sweep = n.event('E4', 'stone_extraction', 'swept with an extraction balloon', 'was swept', session='X1',
                    duct=('biliary', 'The bile duct'), device=('extraction_balloon', 'extraction balloon'),
                    **{'yield': sweep_yield})
    return ercp(n, cannulation(n), *(() if mis else (earlier,)), sweep)


T8_TEXT = head('ERCP REPORT') + (
    'Findings: The duodenoscope was advanced to the major papilla.\n'
    'Deep biliary cannulation was achieved with a sphincterotome.\n'
    'A 15 mm stone in the common bile duct was fragmented with mechanical lithotripsy.\n'
    'At that time, the stone fragments were extracted from the bile duct with an extraction balloon.\n')


def t8(n: Note, mis: bool) -> dict:
    relation = ('earlier_date', 'At that time') if mis else \
        n.fact('on_date_of_service', n.src('was fragmented', 'antecedent'))
    return ercp(n, cannulation(n),
                n.event('E3', 'lithotripsy', 'mechanical lithotripsy', 'was fragmented', session='X1',
                        duct=('biliary', 'common bile duct'), device=('lithotripter', 'mechanical lithotripsy')),
                n.event('E4', 'stone_extraction', 'were extracted', 'were extracted', session='X1',
                        duct=('biliary', 'from the bile duct'), date_relation=relation,
                        device=('extraction_balloon', 'extraction balloon'),
                        **{'yield': ('stone_fragments', 'the stone fragments')}))


SNARE_LINE = 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.\n'
COLO_FINDINGS = 'Findings: The colonoscope was advanced to the cecum.\n'


def snare(n: Note, eid: str = 'E2', **over: object) -> dict:
    """The cold snare removal of SNARE_LINE (its lesion L1 at the sigmoid colon)."""
    fields = dict(session='X1', lesion=('L1', 'A 6 mm sessile polyp'), places=[('sigmoid_colon', 'sigmoid colon')],
                  device=('cold_snare', 'cold snare'))
    fields.update(over)
    return n.event(eid, 'snare', 'cold snare', 'was removed', **fields)


def polyp(n: Note, lid: str = 'L1', words: str = 'A 6 mm sessile polyp', place: tuple = ('sigmoid_colon', 'sigmoid colon'),
          **over: object) -> dict:
    fields = dict(multiplicity=('single', words), places=[place])
    fields.update(over)
    return n.lesion(lid, words, **fields)


T9_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + SNARE_LINE + 'As previously noted, no polypectomy was performed.\n'


def t9(n: Note, mis: bool) -> dict:
    denial = n.event('E3', 'removal', 'polypectomy', 'no polypectomy was performed', session='X1',
                     status_state='negated', breadth=('all_of_kind', 'no polypectomy'),
                     date_relation=('earlier_date', 'As previously noted') if mis else None)
    return colo(n, snare(n), denial, lesions=(polyp(n),))


E1_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + (
    'CRNA note: Cold snare polypectomy of the 6 mm sigmoid polyp was performed under monitored anesthesia care.\n')


def e1(n: Note, mis: bool) -> dict:
    act = n.event('E2', 'snare', 'Cold snare polypectomy', 'was performed', session='X1',
                  places=[('sigmoid_colon', 'sigmoid polyp')], device=('cold_snare', 'Cold snare'))
    sections = () if mis else (n.part('N2', 'CRNA note:', 'anesthesia_record', owner='anesthesia',
                                      owner_words='CRNA note:', performer=None),)
    return colo(n, act, sections=sections)


E2_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + (
    'Documented by Jo Rowe, RN: Sigmoid colon, 6 mm sessile polyp at approx.\n'
    '30 cm, removed en bloc with a cold snare.\n')


def e2(n: Note, mis: bool) -> dict:
    act = n.event('E2', 'snare', 'cold snare', 'removed en bloc', session='X1',
                  anchor_units=[n.u('Documented by Jo Rowe'), n.u('cold snare')],
                  places=[('sigmoid_colon', 'Sigmoid colon', 'other_statement')], device=('cold_snare', 'cold snare'))
    owner = 'documenting_clinician' if mis else 'nursing'
    return colo(n, act, sections=(n.part('N2', 'Documented by Jo Rowe, RN:', 'nursing_note', owner=owner,
                                         owner_words='Documented by Jo Rowe, RN', performer=None),))


E3_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + (
    'Per nursing note: 6 mm sessile polyp in the sigmoid colon removed with cold snare, retrieved.\n'
    'Endoscopist: Polypectomy as above, no bleeding.\n')


def e3(n: Note, mis: bool) -> dict:
    sections = (n.part('N2', 'Per nursing note:', 'nursing_note', owner='nursing', owner_words='Per nursing note',
                       performer=None),
                n.part('N3', 'Endoscopist: Polypectomy', 'findings'))
    if mis:
        act = n.event('E2', 'snare', 'Polypectomy', 'as above', session='X1',
                      places=[('sigmoid_colon', 'sigmoid colon')], device=('cold_snare', 'cold snare'))
    else:
        act = n.event('E2', 'snare', 'cold snare', 'removed with cold snare', session='X1',
                      places=[('sigmoid_colon', 'sigmoid colon')], device=('cold_snare', 'cold snare'),
                      restatements=[('Polypectomy as above', 'refers_back')])
    return colo(n, act, sections=sections)


E4_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + (
    'Endoscopist: see below. Nurse: A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.\n')


def e4(n: Note, mis: bool) -> dict:
    sections = [n.part('N2', 'Endoscopist: see below', 'findings')]
    if not mis:
        sections.append(n.part('N3', 'Nurse:', 'nursing_note', owner='nursing', owner_words='Nurse:', performer=None))
    return colo(n, snare(n), sections=tuple(sections), lesions=(polyp(n),))


E5_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + (
    'Pathology report\n'
    'Final diagnosis\n'
    'Sigmoid colon, biopsy: tubular adenoma.\n')


def e5(n: Note, mis: bool) -> dict:
    sections = [n.part('N2', 'Pathology report', 'pathology_result', owner='pathology', owner_words='Pathology report',
                       performer=None)]
    if mis:
        sections.append(n.part('N3', 'Final diagnosis', 'findings'))
    act = n.event('E2', 'biopsy', 'biopsy', 'biopsy', anchor_words='Sigmoid colon, biopsy', session='X1',
                  places=[('sigmoid_colon', 'Sigmoid colon')])
    return colo(n, act, sections=tuple(sections))


ENTRY_EXP = 'SUPPORT row 5: the act is told only in another role\'s entry: event_entry, an explanation (4.8, RANK 5)'
ENTRY_Q = 'SUPPORT row 5 unresolved (pass 2 contradicts the entry claim): event_entry, a question (RANK 5)'

CASES += [
    Case('T4', 'class', ('T4', 'BF2'), 'An act of unknown class beside the visit', T4_TEXT, t4,
         codes=(('99213', 'seen in the office'),), caught=('other_class@E2/0',),
         expect={'i': {'99213': (H, 'separate_em', Q, '4.7 C-3: an act of kind other whose class is procedure is a '
                                                     'possible procedure (by its class alone, never done): no '
                                                     'separate statement')},
                 'ii': {'99213': (H, 'separate_em', Q, 'the class not established leaves it possibly a procedure: '
                                                       'the same possible procedure day')}}),
    Case('T6', 'class', ('T6', 'BF2'), 'A whole placed at another encounter absorbs today\'s act', T6_TEXT, t6,
         codes=(('43262', 'biliary sphincterotomy'), ('43264', 'swept with an extraction balloon')),
         caught=('date_relation@E5/0',),
         expect={'i': {'43262': (R, None, None, 'the stent is established on an earlier date: no whole today (4.7 '
                                                'stent_included reads the whole by possibly)'),
                       '43264': (R, None, None, 'YIELD stones, R6:cannulation met')},
                 'ii': {'43262': (H, 'act_part', Q, '4.7: the stent possibly today (date not established) makes '
                                                    'stent_included U: act_part (RANK 17)'),
                        '43264': (R, None, None, 'no rule reads the stent for the stone extraction')}}),
    Case('T7', 'class', ('T7', 'BF11', 'BF21'), 'Another time\'s yield counted as this sweep\'s', T7_TEXT, t7,
         codes=(('43264', 'no stones were retrieved'),), caught=('yield@E4/0',),
         expect={'i': {'43264': (H, 'act_yield', EXP, '4.3 YIELD negated: documented as retrieving nothing (an '
                                                      'explanation); the earlier removal is another date')},
                 'ii': {'43264': (H, 'act_yield', Q, '4.3 YIELD unresolved: act_yield (RANK 15)')}}),
    Case('T8', 'class', ('T8', 'BF3'), 'An anaphoric "At that time" filed as an earlier encounter', T8_TEXT, t8,
         codes=(('43264', 'were extracted'), ('43265', 'mechanical lithotripsy')), caught=('date_relation@E4/0',),
         expect={'i': {'43264': (H, 'competing_codes', Q, '4.7 competition: 43265 claims the extraction (D55/D74)'),
                       '43265': (H, 'competing_codes', Q, '4.7 competition over the same extraction')},
                 'ii': {'43264': (H, 'event_time', Q, 'SUPPORT row 3 unresolved on the extraction (RANK 6)'),
                        '43265': (H, 'competing_codes', Q, 'claims read by possibly (D163, D167): the extraction '
                                                           'stays claimed')}}),
    Case('T9', 'class', ('T9', 'BF18'), 'A discourse back-reference sets a denial apart', T9_TEXT, t9,
         codes=(('45385', 'cold snare'),), caught=('date_relation@E3/0',),
         expect={'i': {'45385': (H, 'conflict:snare', Q, '4.5: the denial pairs with the snare on every row: '
                                                         'CONTRADICTION (RANK 1)')},
                 'ii': {'45385': (H, 'event_time', Q, '4.5 timing row UNRESOLVED: event_time')}}),
    Case('E1', 'class', ('E1', 'BF13'), 'An act told only in an anesthesia entry', E1_TEXT, e1,
         codes=(('45385', 'Cold snare polypectomy'),), caught=('entry@E2/0',),
         expect={'i': {'45385': (H, 'event_entry', EXP, ENTRY_EXP)}, 'ii': {'45385': (H, 'event_entry', Q, ENTRY_Q)}}),
    Case('E2', 'class', ('E2', 'BF12'), 'A hard-wrapped act after a nursing signature', E2_TEXT, e2,
         codes=(('45385', 'cold snare'),), caught=('entry@E2/0',),
         expect={'i': {'45385': (H, 'event_entry', EXP, ENTRY_EXP)}, 'ii': {'45385': (H, 'event_entry', Q, ENTRY_Q)}}),
    Case('E3', 'class', ('E3', 'BF11'), 'An "as above" line read as the physician\'s statement', E3_TEXT, e3,
         codes=(('45385', 'removed with cold snare'),), caught=('entry@E2/0',),
         expect={'i': {'45385': (H, 'event_entry', EXP, ENTRY_EXP + '; a refers_back restatement moves no entry '
                                                                    '(1.5, SC-D)')},
                 'ii': {'45385': (H, 'event_entry', Q, ENTRY_Q)}}),
    Case('E4', 'class', ('E4', 'BF12'), 'A role label opening a later sentence of a physician line', E4_TEXT, e4,
         codes=(('45385', 'cold snare'),), caught=('entry@E2/0',),
         expect={'i': {'45385': (H, 'event_entry', EXP, ENTRY_EXP + '; two labels on one line are two parts')},
                 'ii': {'45385': (H, 'event_entry', Q, ENTRY_Q)}}),
    Case('E5', 'class', ('E5',), 'A pathology sub-heading ends the pathology entry', E5_TEXT, e5,
         codes=(('45380', 'Sigmoid colon, biopsy'),), caught=('entry@E2/0',),
         expect={'i': {'45380': (H, 'event_entry', EXP, ENTRY_EXP + ' (the pathologist\'s)')},
                 'ii': {'45380': (H, 'event_entry', Q, ENTRY_Q)}}),
]


T5_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + (
    'Once, a 22 mm polyp was found in the ascending colon.\n'
    'It was removed piecemeal with a cold snare in four pieces.\n'
    'During this procedure, cold forceps biopsies of the polyp were taken.\n')


def t5(n: Note, mis: bool) -> dict:
    removal = n.event('E2', 'snare', 'cold snare', 'was removed', session='X1', lesion=('L1', 'It was removed'),
                      places=[('ascending_colon', 'ascending colon')], device=('cold_snare', 'cold snare'),
                      date_relation=('earlier_date', 'Once') if mis else None)
    biopsy = n.event('E3', 'biopsy', 'cold forceps biopsies', 'were taken', session='X1', lesion=('L1', 'of the polyp'),
                     device=('cold_forceps', 'cold forceps'), date_relation=('on_date_of_service', 'During this procedure'))
    doubts = () if mis else (n.doubt('date_relation', ('E2',), 'Once, a 22 mm polyp', 'unclear',
                                     ('on_date_of_service', 'earlier_date')),)
    return colo(n, removal, biopsy, lesions=(polyp(n, words='a 22 mm polyp', place=('ascending_colon', 'ascending colon')),),
                doubts=doubts)


EUS_HEAD = head('EUS REPORT') + 'Findings: A linear echoendoscope was advanced to the second portion of the duodenum.\n'
EUS_STATIONS = 'EUS imaging was performed from the esophagus, stomach and duodenum.\n'


def stations3(n: Note) -> list:
    return [n.fact('esophagus', n.src('from the esophagus', OTHER)), n.fact('stomach', n.src('stomach and duodenum', OTHER)),
            n.fact('duodenum', n.src('stomach and duodenum', OTHER))]


def eus(n: Note, *events: dict, stations: object = None, tract: object = ('upper', 'linear echoendoscope'),
        exam_places: tuple = (), **kw: object) -> dict:
    exam = n.event('E1', 'examination', 'linear echoendoscope', 'was advanced', session='X1', places=list(exam_places))
    return scope(n, 'eus', 'linear echoendoscope', 'linear echoendoscope', *events,
                 reached=(('second_portion_duodenum', 'second portion of the duodenum'),), exam=exam,
                 stations=stations3(n) if stations is None else stations, tract=tract, **kw)


G1_TEXT = EUS_HEAD + EUS_STATIONS + (
    'A 12 mm subepithelial lesion was seen in the duodenal bulb.\n'
    'A carbon-particle tattoo was placed 2 cm distal to the ampulla for surgical localization.\n')


def g1(n: Note, mis: bool) -> dict:
    route = ('eus_transmural', 'linear echoendoscope', 'other_statement') if mis else ('submucosal', 'carbon-particle tattoo')
    return eus(n, n.event('E2', 'tattoo', 'carbon-particle tattoo', 'was placed', session='X1', route=route,
                          purpose=('marking', 'for surgical localization'),
                          places=[('second_portion_duodenum', '2 cm distal to the ampulla')]),
               exam_places=(('duodenal_bulb', 'duodenal bulb'),))


G2_TEXT = head('EUS REPORT') + (
    'Findings: A radial echoendoscope was advanced through the rectum to the sigmoid colon.\n'
    'A 3 cm mass was seen in the rectum.\n'
    'Three gold fiducial markers were then placed into the rectal mass under EUS guidance for radiation planning.\n')


def g2(n: Note, mis: bool) -> dict:
    exam = n.event('E1', 'examination', 'radial echoendoscope', 'was advanced', session='X1',
                   places=[('rectum', 'A 3 cm mass was seen in the rectum')])
    act = n.event('E2', 'injection', 'fiducial markers', 'were then placed', session='X1',
                  route=('eus_transmural', 'under EUS guidance'), places=[('rectum', 'rectal mass')],
                  purpose=('marking', 'for radiation planning'), structure=('mass', 'rectal mass'))
    tract = ('upper', 'radial echoendoscope') if mis else ('lower', 'through the rectum')
    return scope(n, 'eus', 'radial echoendoscope', 'radial echoendoscope', act, exam=exam,
                 reached=(('sigmoid_colon', 'to the sigmoid colon'),), tract=tract)


G3_TEXT = EUS_HEAD + EUS_STATIONS + (
    'A 9 cm pancreatic pseudocyst was seen adjacent to the gastric body.\n'
    'Under EUS guidance, the pseudocyst was punctured from the gastric body with a 19-gauge needle and 20 mL of fluid '
    'was aspirated.\n'
    'EUS-guided transmural drainage of the pseudocyst was then performed across the posterior gastric wall.\n')


def g3(n: Note, mis: bool) -> dict:
    fna = n.event('E2', 'fna', 'was punctured', 'was punctured', session='X1', lesion=('L1', 'the pseudocyst'),
                  device=('needle', '19-gauge needle'), places=[('pancreas', 'pancreatic pseudocyst')],
                  part_of=None if mis else ('E3', 'transmural drainage'),
                  part_relation=None if mis else ('access_for', 'was punctured'))
    if mis:
        drainage = n.event('E3', 'drainage', 'transmural drainage', 'was then performed', session='X1',
                           structure=('wall', 'posterior gastric wall'), places=[('gastric_body', 'posterior gastric wall')],
                           route=('eus_transmural', 'transmural'))
    else:
        drainage = n.event('E3', 'drainage', 'transmural drainage', 'was then performed', session='X1',
                           lesion=('L1', 'of the pseudocyst'), structure=('pancreatic_fluid_collection', 'pseudocyst'),
                           places=[('pancreas', 'pancreatic pseudocyst')], route=('eus_transmural', 'transmural'))
    return eus(n, fna, drainage, lesions=(n.lesion('L1', 'A 9 cm pancreatic pseudocyst',
                                                   multiplicity=('single', 'A 9 cm pancreatic pseudocyst')),),
               exam_places=(('pancreas', 'pancreatic pseudocyst'),))


G4_TEXT = EUS_HEAD + EUS_STATIONS + (
    'A 2 cm hypoechoic mass was seen in the pancreatic head.\n'
    'Later, a 20 mm lumen-apposing metal stent was deployed from the gastric body into a distended jejunal loop.\n')


def g4(n: Note, mis: bool) -> dict:
    stent = n.event('E2', 'stent', 'lumen-apposing metal stent', 'was deployed', session='X1',
                    places=[('gastric_body', 'from the gastric body')], date_relation=('on_date_of_service', 'Later'))
    return eus(n, *(() if mis else (stent,)), exam_places=(('pancreas', 'pancreatic head'),))


G5_TEXT = HEAD_OFFICE + VISIT + 'Labs were drawn in the office today.\n' + TIME


def g5(n: Note, mis: bool) -> dict:
    return office(n, n.event('E2', 'other', 'Labs were drawn', 'were drawn', session='X1',
                             other_class=('procedure' if mis else 'laboratory', 'Labs')))


S1_TEXT = EUS_HEAD + 'EUS imaging was performed from the duodenum only.\nA 2 cm hypoechoic mass was seen in the pancreatic head.\n'


def s1(n: Note, mis: bool) -> dict:
    if mis:
        stations: list = []
    else:
        stations = [n.fact('duodenum', n.src('from the duodenum only', OTHER)),
                    n.fact('esophagus', n.src('from the duodenum only', OTHER), state='negated'),
                    n.fact('stomach', n.src('from the duodenum only', OTHER), state='negated')]
    return eus(n, stations=stations, exam_places=(('pancreas', 'pancreatic head'),))


S2_TEXT = EUS_HEAD + ('EUS imaging was performed from the duodenum.\n'
                      'The pancreatic head was examined; a 2 cm hypoechoic mass was seen.\n'
                      'The esophagus and the stomach were not examined.\n')


def s2(n: Note, mis: bool) -> dict:
    if mis:
        stations: list = []
        denials = (n.event('E3', 'examination', 'esophagus', 'were not examined', session='X1', status_state='negated',
                           breadth=('single_target', 'The esophagus'), places=[('esophagus', 'The esophagus')]),
                   n.event('E4', 'examination', 'the stomach', 'were not examined', session='X1',
                           status_state='negated', breadth=('single_target', 'the stomach'),
                           places=[('stomach', 'the stomach')]))
    else:
        stations = [n.fact('duodenum', n.src('performed from the duodenum', OTHER)),
                    n.fact('esophagus', n.src('The esophagus and the stomach were not examined', OTHER), state='negated'),
                    n.fact('stomach', n.src('The esophagus and the stomach were not examined', OTHER), state='negated')]
        denials = ()
    return eus(n, *denials, stations=stations, exam_places=(('pancreas', 'The pancreatic head'),))


S3_TEXT = head('ENDOSCOPY REPORT') + (
    'EGD: The gastroscope was advanced to the second portion of the duodenum.\n'
    'Push enteroscopy: Two angioectasias in the proximal jejunum were treated with argon plasma coagulation.\n')


def s3(n: Note, mis: bool) -> dict:
    sessions = () if mis else (n.session('X2', 'enteroscopy', 'Push enteroscopy'),)
    act = n.event('E3', 'ablation', 'argon plasma coagulation', 'were treated', session='X1' if mis else 'X2',
                  device=('argon_plasma', 'argon plasma coagulation'),
                  places=[('jejunum', 'in the proximal jejunum')])
    sections = (n.part('N2', 'Push enteroscopy:', 'procedure'),)
    return scope(n, 'egd', 'gastroscope', 'gastroscope', act, label='EGD:', sessions=sessions, sections=sections,
                 reached=(('second_portion_duodenum', 'advanced to the second portion of the duodenum'),))


S4_TEXT = head('ERCP REPORT') + (
    'Findings: The duodenoscope was advanced to the major papilla.\n'
    'Deep biliary cannulation was achieved with a sphincterotome.\n'
    'The procedure was terminated; no sphincterotomy and no stent placement were performed.\n')


def s4(n: Note, mis: bool) -> dict:
    completion = ('complete', 'The procedure was terminated') if mis else ('terminated', 'The procedure was terminated')
    denials = (n.event('E3', 'sphincterotomy', 'no sphincterotomy', 'were performed', session='X1',
                       status_state='negated', breadth=('all_of_kind', 'no sphincterotomy')),
               n.event('E4', 'stent', 'no stent placement', 'were performed', session='X1', status_state='negated',
                       breadth=('all_of_kind', 'no stent placement')))
    return ercp(n, cannulation(n), *denials, completion=completion)


ENT_HEAD = head('ENDOSCOPY REPORT') + (
    'EGD: The gastroscope was advanced to the second portion of the duodenum.\n'
    'Push enteroscopy: The enteroscope was then advanced to the proximal jejunum.\n')


def egd_and_push(n: Note, *events: dict, doubts: tuple = ()) -> dict:
    return scope(n, 'egd', 'gastroscope', 'gastroscope',
                 n.event('E2', 'examination', 'enteroscope', 'was then advanced', session='X2'), *events,
                 label='EGD:', reached=(('second_portion_duodenum', 'advanced to the second portion of the duodenum'),),
                 sessions=(n.session('X2', 'enteroscopy', 'enteroscope', exam='E2',
                                     reached=[('jejunum', 'proximal jejunum')]),),
                 sections=(n.part('N2', 'Push enteroscopy:', 'procedure'),), doubts=doubts)


N1_TEXT = ENT_HEAD + 'On withdrawal, a polypectomy of a 7 mm gastric body polyp was performed.\n'


def n1(n: Note, mis: bool) -> dict:
    act = n.event('E3', 'removal', 'polypectomy', 'was performed', session='X2' if mis else None,
                  places=[('gastric_body', 'gastric body polyp')])
    doubts = () if mis else (n.doubt('session', ('E3',), 'On withdrawal', 'unclear', ('X1', 'X2')),)
    return egd_and_push(n, act, doubts=doubts)


N2_TEXT = ENT_HEAD + ('Biopsies of the distal duodenum may have been taken with cold forceps.\n'
                      'Argon plasma coagulation of a jejunal angioectasia may have been performed.\n')


def n2(n: Note, mis: bool) -> dict:
    biopsy = n.event('E3', 'biopsy', 'Biopsies', 'may have been taken', session='X1',
                     places=[('duodenum', 'distal duodenum')], device=('cold_forceps', 'cold forceps'))
    ablation = n.event('E4', 'ablation', 'Argon plasma coagulation', 'may have been performed',
                       session='X1' if mis else 'X2', places=[('jejunum', 'jejunal angioectasia')],
                       device=('argon_plasma', 'Argon plasma coagulation'))
    doubts = (n.doubt('status', ('E3',), 'may have been taken', 'stated', ('performed',)),
              n.doubt('status', ('E4',), 'may have been performed', 'stated', ('performed',)))
    return egd_and_push(n, biopsy, ablation, doubts=doubts)


N3_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + (
    'A flexible sigmoidoscopy to the sigmoid colon was performed as part of the colonoscopy.\n')


def n3(n: Note, mis: bool) -> dict:
    flex = n.event('E2', 'examination', 'flexible sigmoidoscopy', 'was performed', session='X2',
                   part_of=('E1', 'as part of the colonoscopy') if mis else None)
    part = None if mis else ('X1', 'as part of the colonoscopy')
    return colo(n, flex, sessions=(n.session('X2', 'flex_sig', 'flexible sigmoidoscopy', exam='E2',
                                             reached=[('sigmoid_colon', 'to the sigmoid colon')],
                                             part_of_session=part),))


CASES += [
    Case('T5', 'class', ('T5', 'BF2', 'D3', 'CO-1'), 'An unanchored earlier time on a removal releases its biopsy', T5_TEXT, t5,
         codes=(('45385', 'cold snare'), ('45380', 'cold forceps biopsies')), caught=('date_relation@E2/0',),
         expect={'i': {'45385': (H, 'event_time', Q, 'BF2: the vague "Once" is a doubt (3.3 row 2): the date '
                                                     'relation unknown (RANK 6) [R:CO-1]'),
                       '45380': (H, 'act_part', Q, '4.7 biopsy_of_removed_lesion: the whole possibly today '
                                                   '(read by possibly): asked, never silent (act_part, RANK 17)')},
                 'ii': {'45385': (H, 'event_time', Q, 'SUPPORT row 3 unresolved (RANK 6)'),
                        '45380': (H, 'act_part', Q, 'the whole possibly today: asked (RANK 17)')}}),
    Case('G1', 'class', ('G1', 'BF8'), '43253 on a submucosal tattoo', G1_TEXT, g1,
         codes=(('43253', 'carbon-particle tattoo'),), caught=('technique.route@E2/0',),
         expect={'i': {'43253': (H, 'technique', EXP, '4.3 ROUTE: submucosal, held, never READY on a wall '
                                                      'injection (an explanation, RANK 10)')},
                 'ii': {'43253': (H, 'technique', Q, '4.3 ROUTE unresolved (RANK 10)')}}),
    Case('G2', 'class', ('G2', 'BF6'), 'An upper EUS code on a lower EUS', G2_TEXT, g2,
         codes=(('43253', 'fiducial markers'), ('45341', 'radial echoendoscope')), caught=('tract@X1/0',),
         expect={'i': {'43253': (H, 'procedure', None, '4.3 TRACT: the other tract, held (RANK 8)'),
                       '45341': (H, 'base_included', EXP, '4.7 base_included: the session\'s reportable act; '
                                                          'D177(1): no same-tract code, the hold names the act')},
                 'ii': {'43253': (H, 'procedure', Q, '4.3 TRACT unresolved (RANK 8)'),
                        '45341': (H, 'procedure', Q, '4.3 TRACT unresolved (RANK 8)')}}),
    Case('G3', 'class', ('G3', 'BF9', 'BF15'), 'An FNA that is the access step of a drainage', G3_TEXT, g3,
         codes=(('43240', 'transmural drainage'), ('43242', 'was punctured')),
         caught=('target.structure@E3/0', 'target.places@E3/0'),
         expect={'i': {'43240': (R, None, None, '4.3 STRUCT:pfc, DEF, TRACT, R6:target met'),
                       '43242': (H, 'performed_status', EXP, '4.7 drainage_step: the FNA is the drainage\'s access '
                                                             'step (bundled, an explanation naming the whole, RANK 18)')},
                 'ii': {'43240': (H, 'target', Q, '4.3 STRUCT:pfc unresolved (RANK 12)'),
                        '43242': (H, 'act_target', Q, '4.7 drainage_step on an unknown lesion identity: asked '
                                                      '(RANK 17)')}}),
    Case('G4', 'class', ('G4', 'O1'), 'An unlisted EUS-guided act beside the EUS examination', G4_TEXT, g4,
         codes=(('43259', 'linear echoendoscope'),),
         unlisted_ii=({'units': ['S7'], 'what': 'act', 'kind': 'stent', 'session': 'X1'},),
         expect={'i': {'43259': (H, 'base_included', None, 'Appendix C G4: base_included on the session\'s other act '
                                                           '(its kind the EUS entry does not list, D137)')},
                 'ii': {'43259': (H, 'base_included', Q, '3.2.6 rule 3: the unlisted act is a synthetic doubted '
                                                         'act of the session: base_included, a question')}}),
    Case('G5', 'class', ('G5',), 'A lab draw counted as a possible same-day procedure', G5_TEXT, g5,
         codes=(('99213', 'seen in the office'),), caught=('other_class@E2/0',),
         expect={'i': {'99213': (R, None, None, '4.7 C-3: a laboratory act is no procedure')},
                 'ii': {'99213': (H, 'separate_em', Q, 'the class not established: a possible procedure day')}}),
    Case('S1', 'class', ('S1', 'BF6'), 'A full-class EUS code beside stations that exclude the upper tract', S1_TEXT,
         s1, codes=(('43259', 'linear echoendoscope'),), caught=('completeness@X1',),
         expect={'i': {'43259': (H, 'exam_stations', EXP, '4.3 STATIONS: a station negated, the class explanation')},
                 'ii': {'43259': (H, 'exam_stations', Q, '4.3 STATIONS: an empty list whose completeness claim is '
                                                         'not established (BF6 filed with an empty list is held) '
                                                         '[R:SC-B]')}}),
    Case('S2', 'class', ('S2', 'BF7'), 'Stations stated as not examined', S2_TEXT, s2,
         codes=(('43259', 'linear echoendoscope'),), caught=('completeness@X1',),
         expect={'i': {'43259': (H, 'exam_stations', EXP, '4.3 STATIONS: stations negated, the class explanation')},
                 'ii': {'43259': (H, 'performed_status', Q, '4.3 row 7: the misfiled denials are examination events '
                                                            'of the session established not done, so the session is '
                                                            'not done (RANK 4, before the stations\' RANK 13)')}}),
    Case('S3', 'class', ('S3', 'BF20'), 'A session told only by its acts keeps its extent question', S3_TEXT, s3,
         codes=(('43235', 'gastroscope'),), caught=('session@E3/0',), checked=('session@E3/0',),
         services={'i': (('extent', 'X2'),)},
         expect={'i': {'43235': (R, None, None, 'the ablation is the push enteroscopy\'s act; the EGD has none')},
                 'ii': {'43235': (H, 'base_included', Q, '4.7 base_included (c): an act whose session is not '
                                                         'established may be the EGD\'s (doubted)')}}),
    Case('S4', 'class', ('S4', 'BF7'), 'A terminated examination keeps its 52/53 consideration', S4_TEXT, s4,
         codes=(('43260', 'duodenoscope'),), caught=('completion@X1/0',),
         considerations={'i': {'43260': ('52|53',)}, 'ii': {'43260': ('52|53',)}},
         known={'ii': {'43260': (R, None, 'Q-S4', ('52|53',))}},
         note='(ii): completion is read by no requirement of 43260, so the caught misfiling cannot hold it (4.3, 4.4); '
              'the design names no form for a completion pass 2 did not establish beside the 52/53 consideration '
              '(4.7 reads "completion incomplete or terminated"). Dropping it is S4\'s own failure ("dropped '
              'consideration (52/53)"; c2e53f8e warns and considers 52/53), so the fail-closed reading built here keeps '
              'it: (ii) expects READY with 52|53, the installed reading DECISIONS D244 rules (Q-S4 option (a)). The '
              'engine gives no consideration: pinned as known; KnownDefectTests.test_Q_S4 asserts the ruling until '
              'assess.py is repaired.',
         expect={'i': {'43260': (R, None, None, 'READY with the 52/53 consideration (completion terminated)')},
                 'ii': {'43260': (R, None, None, 'completion read by no requirement of 43260: no hold; the 52/53 '
                                                 'consideration kept while the terminated completion may hold (D244 '
                                                 'Q-S4 option (a), the installed reading)')}}),
    Case('N1', 'class', ('N1', 'BF16', 'BF20'), 'An act assigned to the wrong coding session', N1_TEXT, n1,
         codes=(('43235', 'gastroscope'),), caught=('session@E3/0',), checked=('session@E3/0',),
         known={'ii': {'43235': (H, 'base_included', 'Q-N1')}},
         note='(ii): K3 (D192) demotes the session claim X2 (a gastric place outside the push enteroscopy\'s reach), so '
              'no claim and no control is made; possibly keeps X2 alone and D227 F8 reads only X2\'s family: 43235 '
              'READY against the documented hold. Pinned as known: DECISIONS D244 rules Q-N1 option (b) (a session '
              'fact K3 demotes is possibly any session whose reach holds the act\'s place), so the design\'s hold '
              'stands and KnownDefectTests.test_Q_N1 asserts it until facts.possibly is repaired.',
         expect={'i': {'43235': (H, 'base_included', Q, '"either scope" (a doubt on the session): the removal may '
                                                        'be the EGD\'s, a doubted act (4.7)')},
                 'ii': {'43235': (H, 'base_included', Q, 'the session not established: a doubted act of the EGD')}}),
    Case('N2', 'class', ('N2',), 'An act of unverified place is never moved into the EGD', N2_TEXT, n2,
         codes=(('44369', 'Argon plasma coagulation'), ('43239', 'Biopsies')), caught=('session@E4/0',),
         checked=('session@E4/0',),
         expect={'i': {'44369': (H, 'performed_status', Q, 'a doubt pass 1 reported on status: RANK 2'),
                       '43239': (H, 'performed_status', Q, 'a doubt on status: RANK 2')},
                 'ii': {'44369': (H, 'performed_status', Q, 'the doubt on status still ranks first (RANK 2); the '
                                                            'session unresolved is a held fact'),
                        '43239': (H, 'performed_status', Q, 'unchanged')}}),
    Case('N3', 'class', ('N3', 'BF15'), 'A part session\'s base code beside its whole', N3_TEXT, n3,
         codes=(('45330', 'flexible sigmoidoscopy'), ('45378', 'colonoscope')), variants=('i', 'iii'),
         known={'i': {'45330': (H, 'base_included', 'R-N3')}},
         note='(ii) has no claim to contradict: the misfiling omits part_of_session (an empty slot relates nothing, '
              '4.7), and pass 2 can list only acts, denials and doubts (3.2.6). Built with (i) and (iii); the '
              'omission is a residual (the step\'s NOTES, question Q-N3).',
         expect={'i': {'45330': (H, 'base_included', EXP, '4.7 base_within C3: part_of_session supported, an '
                                                          'established whole holds it (an explanation)'),
                       '45378': (R, None, None, 'the colonoscopy has no reportable act')}}),
]


# --- A: anatomy type -------------------------------------------------------------------------------------------------

def history_and_findings(n: Note, history: str = 'History:') -> list:
    return [n.opening(), n.part('N1', history, 'history', occasion=None), n.part('N2', 'Findings:', 'findings')]


A1_TEXT = head('POUCHOSCOPY REPORT') + (
    'History: The patient has an ileal pouch-anal anastomosis after a total proctocolectomy.\n'
    'Findings: The endoscope was advanced through the anus into the pouch and into the pre-pouch ileum for 15 cm.\n'
    'Biopsies of the pouch were taken with cold forceps.\n')


def a1(n: Note, mis: bool) -> dict:
    pouch = n.anatomy('Y1', ('anastomosis' if mis else 'ileal_pouch', 'ileal pouch-anal anastomosis'),
                      subtype=('ileoanal', 'ileal pouch-anal anastomosis'))
    return n.answer(sections=history_and_findings(n),
                    sessions=[n.session('X1', 'enteroscopy', 'The endoscope', exam='E1',
                                        approach=('transanal', 'through the anus'), through=('Y1', 'into the pouch'),
                                        reached=[('pouch', 'into the pouch'), ('ileum', 'pre-pouch ileum')])],
                    events=[n.event('E1', 'examination', 'The endoscope', 'was advanced', session='X1'),
                            n.event('E2', 'biopsy', 'Biopsies', 'were taken', session='X1',
                                    places=[('pouch', 'of the pouch')], device=('cold_forceps', 'cold forceps'))],
                    anatomy=[pouch])


A2_TEXT = head('ENTEROSCOPY REPORT') + (
    'History: The patient has an ileal J-pouch and a small gastric pouch after a Roux-en-Y gastric bypass.\n'
    'Findings: The enteroscope was advanced through the gastric pouch and the Roux limb into the proximal ileum.\n'
    'Biopsies of the proximal ileum were taken with cold forceps.\n')


def a2(n: Note, mis: bool) -> dict:
    approach = ('through_pouch' if mis else 'oral', 'advanced through the gastric pouch')
    through = ('Y1' if mis else 'Y2', 'through the gastric pouch')
    return n.answer(sections=history_and_findings(n),
                    sessions=[n.session('X1', 'enteroscopy', 'The enteroscope', exam='E1', approach=approach,
                                        through=through, reached=[('ileum', 'into the proximal ileum')])],
                    events=[n.event('E1', 'examination', 'The enteroscope', 'was advanced', session='X1'),
                            n.event('E2', 'biopsy', 'Biopsies', 'were taken', session='X1',
                                    places=[('ileum', 'of the proximal ileum')], device=('cold_forceps', 'cold forceps'))],
                    anatomy=[n.anatomy('Y1', ('ileal_pouch', 'ileal J-pouch')),
                             n.anatomy('Y2', ('gastric_pouch', 'small gastric pouch')),
                             n.anatomy('Y3', ('roux_limb', 'the Roux limb'))])


A3_TEXT = head('ENTEROSCOPY REPORT') + (
    'History: The colon was converted into an end ileostomy in 2019.\n'
    'Findings: Double-balloon enteroscopy was performed orally to the mid jejunum.\n'
    'Biopsies of the jejunum were taken with cold forceps.\n')


def a3(n: Note, mis: bool) -> dict:
    fields = dict(approach=('through_stoma', 'end ileostomy'), through=('Y1', 'end ileostomy')) if mis else \
        dict(approach=('oral', 'performed orally'))
    return n.answer(sections=history_and_findings(n),
                    sessions=[n.session('X1', 'enteroscopy', 'Double-balloon enteroscopy', exam='E1',
                                        reached=[('jejunum', 'to the mid jejunum')], **fields)],
                    events=[n.event('E1', 'examination', 'Double-balloon enteroscopy', 'was performed', session='X1'),
                            n.event('E2', 'biopsy', 'Biopsies', 'were taken', session='X1',
                                    places=[('jejunum', 'of the jejunum')], device=('cold_forceps', 'cold forceps'))],
                    anatomy=[n.anatomy('Y1', ('stoma', 'end ileostomy'))])


# --- C: causality ----------------------------------------------------------------------------------------------------

EGD_FINDINGS = 'Findings: The gastroscope was advanced to the second portion of the duodenum.\n'


def egd(n: Note, *events: dict, **kw: object) -> dict:
    return scope(n, 'egd', 'gastroscope', 'gastroscope', *events,
                 reached=(('second_portion_duodenum', 'second portion of the duodenum'),), **kw)


C1_TEXT = head('UPPER ENDOSCOPY REPORT') + EGD_FINDINGS + (
    'Cold forceps biopsies of the gastric antrum were taken.\n'
    'Oozing at the biopsy site was controlled with a clip.\n')


def c1(n: Note, mis: bool) -> dict:
    cause = dict(cause=('spontaneous', 'Oozing')) if mis else \
        dict(cause=('act_of_this_session', 'at the biopsy site'), cause_event=('E2', 'at the biopsy site'))
    return egd(n, n.event('E2', 'biopsy', 'Cold forceps biopsies', 'were taken', session='X1',
                          places=[('gastric_antrum', 'gastric antrum')], device=('cold_forceps', 'Cold forceps')),
               n.event('E3', 'clip', 'clip', 'was controlled', session='X1', purpose=('hemostasis', 'Oozing'),
                       device=('clip', 'clip'), **cause))


C2_TEXT = head('UPPER ENDOSCOPY REPORT') + EGD_FINDINGS + (
    'A 12 mm sessile polyp in the gastric cardia was removed with a hot snare.\n'
    'Immediate oozing from the polypectomy site in the gastric antrum was controlled with two hemoclips for '
    'hemostasis.\n')


def c2(n: Note, mis: bool) -> dict:
    cause = dict(cause=('pre_existing_lesion', 'Immediate oozing')) if mis else \
        dict(cause=('act_of_this_session', 'from the polypectomy site'),
             cause_event=('E2', 'from the polypectomy site'))
    return egd(n, n.event('E2', 'snare', 'hot snare', 'was removed', session='X1',
                          lesion=('L1', 'A 12 mm sessile polyp'), places=[('gastric_cardia', 'gastric cardia')],
                          device=('hot_snare', 'hot snare')),
               n.event('E3', 'clip', 'hemoclips', 'was controlled', session='X1',
                       purpose=('hemostasis', 'for hemostasis'), places=[('gastric_antrum', 'in the gastric antrum')],
                       device=('clip', 'hemoclips'), **cause),
               lesions=(polyp(n, words='A 12 mm sessile polyp', place=('gastric_cardia', 'gastric cardia')),))


C3_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + (
    'A 4 mm angioectasia was seen in the cecum.\n'
    'Cautery was applied at this site.\n')


def c3(n: Note, mis: bool) -> dict:
    kind, purpose = ('bleeding_control', ('hemostasis', 'Cautery')) if mis else ('ablation', ('treatment', 'Cautery'))
    return colo(n, n.event('E2', kind, 'Cautery', 'was applied', session='X1', purpose=purpose,
                           device=('electrocautery', 'Cautery'), lesion=('L1', 'at this site'),
                           places=[('cecum', 'in the cecum')]),
                lesions=(n.lesion('L1', 'A 4 mm angioectasia', multiplicity=('single', 'A 4 mm angioectasia'),
                                  places=[('cecum', 'in the cecum')]),))


C4_TEXT = head('UPPER ENDOSCOPY REPORT') + EGD_FINDINGS + (
    'A 9 mm sessile polyp in the gastric body was removed with a hot snare.\n'
    'Cautery was applied to the polypectomy site.\n')


def c4(n: Note, mis: bool) -> dict:
    return egd(n, n.event('E2', 'snare', 'hot snare', 'was removed', session='X1',
                          lesion=('L1', 'A 9 mm sessile polyp'), places=[('gastric_body', 'gastric body')],
                          device=('hot_snare', 'hot snare')),
               n.event('E3', 'bleeding_control' if mis else 'ablation', 'Cautery', 'was applied', session='X1',
                       device=('electrocautery', 'Cautery'), part_of=('E2', 'to the polypectomy site'),
                       part_relation=('adjunct_of', 'to the polypectomy site')),
               lesions=(polyp(n, words='A 9 mm sessile polyp', place=('gastric_body', 'gastric body')),))


# --- Y: yield ----------------------------------------------------------------------------------------------------------

ERCP_HEAD = head('ERCP REPORT') + ('Findings: The duodenoscope was advanced to the major papilla.\n'
                                   'Deep biliary cannulation was achieved with a sphincterotome.\n')
NEG = 'negated'


def sweep(n: Note, eid: str, kind_words: str, status_words: str, yield_: object = None, duct: object = None,
          device: object = ('extraction_balloon', 'extraction balloon'), **over: object) -> dict:
    fields = dict(session='X1', device=device, duct=duct if duct is not None else ('biliary', 'bile duct'))
    fields.update(over)
    if yield_ is not None:
        fields['yield'] = yield_
    return n.event(eid, 'stone_extraction', kind_words, status_words, **fields)


Y1_TEXT = ERCP_HEAD + ('The bile duct was swept with an extraction balloon and two stones were removed.\n'
                       'The pancreatic duct was then swept with a balloon; no stones were seen.\n')


def y1(n: Note, mis: bool) -> dict:
    first = ('anything', 'no stones were seen', OTHER, NEG) if mis else ('stones', 'two stones were removed')
    second = ('stones', 'two stones were removed', OTHER) if mis else ('anything', 'no stones were seen', 'statement', NEG)
    return ercp(n, cannulation(n),
                sweep(n, 'E3', 'swept with an extraction balloon', 'was swept', first),
                sweep(n, 'E4', 'then swept with a balloon', 'was then swept', second,
                      duct=('pancreatic', 'pancreatic duct'), device=('balloon', 'with a balloon')))


Y2_TEXT = ERCP_HEAD + ('The stones were first swept with a basket.\n'
                       'Three stones, the largest 9 mm, were extracted from the bile duct with an extraction balloon.\n'
                       'No stones remained.\n')


def y2(n: Note, mis: bool) -> dict:
    return ercp(n, cannulation(n),
                sweep(n, 'E3', 'swept with a basket', 'were first swept', ('stones', 'The stones') if mis else None,
                      duct=('biliary', 'bile duct', OTHER), device=('basket', 'basket')),
                sweep(n, 'E4', 'were extracted', 'were extracted', None if mis else ('stones', 'Three stones')))


Y3_TEXT = ERCP_HEAD + ('Cholangiogram showed a mildly dilated bile duct without filling defects.\n'
                       'A biliary sphincterotomy was performed.\n'
                       'The bile duct was swept several times with an extraction balloon.\n')


def y3(n: Note, mis: bool) -> dict:
    return ercp(n, cannulation(n),
                n.event('E3', 'sphincterotomy', 'biliary sphincterotomy', 'was performed', session='X1',
                        duct=('biliary', 'biliary')),
                sweep(n, 'E4', 'swept several times', 'was swept', ('debris', 'swept several times') if mis else None,
                      duct=('biliary', 'The bile duct')))


Y4_TEXT = ERCP_HEAD + ('The bile duct was swept with an extraction balloon to ensure all stones had been removed; no '
                       'stones remained.\n')


def y4(n: Note, mis: bool) -> dict:
    found = ('stones', 'all stones had been removed') if mis else ('anything', 'no stones remained', 'statement', NEG)
    return ercp(n, cannulation(n), sweep(n, 'E3', 'swept with an extraction balloon', 'was swept', found))


Y5_TEXT = ERCP_HEAD + 'The bile duct was swept with an extraction balloon and two stones were removed. No stones were retrieved.\n'


def y5(n: Note, mis: bool) -> dict:
    denial = n.event('E4', 'stone_extraction', 'No stones were retrieved', 'No stones were retrieved', session='X1',
                     status_state=NEG, breadth=('all_of_kind', 'No stones were retrieved'))
    return ercp(n, cannulation(n), sweep(n, 'E3', 'swept with an extraction balloon', 'was swept',
                                         ('stones', 'two stones were removed')), *(() if mis else (denial,)))


Y6_TEXT = ERCP_HEAD + ('The bile duct was swept with an extraction balloon.\n'
                       'No stones were retrieved and a plastic biliary stent was placed.\n')


def y6(n: Note, mis: bool) -> dict:
    found = ('stones', 'No stones were retrieved', OTHER) if mis else ('anything', 'No stones were retrieved', OTHER, NEG)
    return ercp(n, cannulation(n), sweep(n, 'E3', 'swept with an extraction balloon', 'was swept', found),
                n.event('E4', 'stent', 'plastic biliary stent', 'was placed', session='X1', duct=('biliary', 'biliary')))


Y7_TEXT = ERCP_HEAD + ('The bile duct was swept with an extraction balloon.\n'
                       'No stones were retrieved.\n')


def y7(n: Note, mis: bool) -> dict:
    found = None if mis else ('anything', 'No stones were retrieved', OTHER, NEG)
    return ercp(n, cannulation(n), sweep(n, 'E3', 'swept with an extraction balloon', 'was swept', found))


# --- X1: a title-named exchange --------------------------------------------------------------------------------------

X1_TEXT = head('ERCP REPORT') + (
    'Procedure: ERCP with biliary stent exchange.\n'
    'Findings: The duodenoscope was advanced to the major papilla.\n'
    'Deep biliary cannulation was achieved with a sphincterotome.\n'
    'The existing biliary stent was left in place.\n'
    'A 10 Fr x 9 cm plastic biliary stent was placed into the common bile duct.\n')


def x1(n: Note, mis: bool) -> dict:
    if mis:
        events: tuple = (n.event('E3', 'stent_exchange', 'biliary stent exchange', 'was placed', session='X1',
                                 anchor_units=[n.u('biliary stent exchange'), n.u('was placed into')],
                                 duct=('biliary', 'plastic biliary stent', OTHER)),)
    else:
        events = (n.event('E3', 'stent_removal', 'existing biliary stent', 'was left in place', session='X1',
                          status_state=NEG, breadth=('single_target', 'existing biliary stent'),
                          duct=('biliary', 'existing biliary stent')),
                  n.event('E4', 'stent', 'plastic biliary stent', 'was placed', session='X1',
                          duct=('biliary', 'plastic biliary stent'), places=[('common_bile_duct', 'common bile duct')]))
    return ercp(n, cannulation(n), *events)


# --- D: denial scope -------------------------------------------------------------------------------------------------

D1_TEXT = head('UPPER ENDOSCOPY REPORT') + EGD_FINDINGS + (
    'A 15 mm ulcer was seen in the duodenal bulb.\n'
    'A hemostatic injection of dilute epinephrine was given into the ulcer base.\n'
    'No other injection was given.\n')


def d1(n: Note, mis: bool) -> dict:
    scope_fields = dict(breadth=('all_of_kind', 'No other injection')) if mis else \
        dict(breadth=('exceptive', 'No other'), excepts=['E2'])
    return egd(n, n.event('E2', 'injection', 'hemostatic injection', 'was given', session='X1',
                          purpose=('hemostasis', 'hemostatic'), cause=('pre_existing_lesion', 'into the ulcer base'),
                          structure=('ulcer', 'ulcer base'), places=[('duodenal_bulb', 'duodenal bulb')],
                          device=('injection', 'injection')),
               n.event('E3', 'injection', 'injection', 'No other injection was given', anchor_words='No other injection',
                       session='X1', status_state=NEG, **scope_fields))


D2_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + SNARE_LINE + (
    'No polypectomy was performed in the prior segment.\n'
    'It is unclear whether the 4 mm rectal polyp was removed.\n')


def d2(n: Note, mis: bool) -> dict:
    scope_fields = dict(breadth=('single_target', 'No polypectomy'), places=[('rectum', 'in the prior segment')]) \
        if mis else dict(breadth=('segment', 'in the prior segment'))
    denial = n.event('E3', 'removal', 'No polypectomy', 'No polypectomy was performed', session='X1',
                     status_state=NEG, **scope_fields)
    doubted = n.event('E4', 'removal', 'was removed', 'was removed', anchor_words='rectal polyp was removed',
                      session='X1', places=[('rectum', 'rectal polyp')])
    return colo(n, snare(n), denial, doubted, lesions=(polyp(n),),
                doubts=(n.doubt('status', ('E4',), 'It is unclear whether', 'unclear', ('performed',)),))


D3_TEXT = T5_TEXT + 'No biopsies were taken.\n'


def d3(n: Note, mis: bool) -> dict:
    data = t5(n, mis)
    data['events'].append(n.event('E4', 'biopsy', 'No biopsies', 'No biopsies were taken', session='X1',
                                  status_state=NEG, breadth=('all_of_kind', 'No biopsies')))
    return data


# --- Q: the hold and question policy (not Gemini attributes: S4's contract column; each built with a misfiling of the
# deciding fact, so its three variants exist) ---------------------------------------------------------------------------

Q1_TEXT = head('UPPER ENDOSCOPY REPORT') + EGD_FINDINGS + (
    'At that time, biopsies of the gastric antrum were taken with cold forceps.\n'
    'At that time, the gastric polyps were removed with a cold snare.\n')


def q1(n: Note, mis: bool) -> dict:
    relation = ('earlier_date', 'At that time') if mis else None
    first = n.event('E2', 'biopsy', 'biopsies', 'were taken', session='X1', places=[('gastric_antrum', 'gastric antrum')],
                    device=('cold_forceps', 'cold forceps'),
                    date_relation=None if relation is None else n.fact('earlier_date', n.src('At that time, biopsies')))
    second = n.event('E3', 'snare', 'cold snare', 'were removed', session='X1', places=[('stomach', 'gastric polyps')],
                     device=('cold_snare', 'cold snare'),
                     date_relation=None if relation is None else n.fact('earlier_date', n.src('At that time, the gastric')))
    doubts = () if mis else (n.doubt('date_relation', ('E2',), 'biopsies of the gastric antrum', 'unclear',
                                     ('on_date_of_service', 'earlier_date')),
                             n.doubt('date_relation', ('E3',), 'the gastric polyps were removed', 'unclear',
                                     ('on_date_of_service', 'earlier_date')))
    return egd(n, first, second, doubts=doubts)


Q2_TEXT = ERCP_HEAD + ('The existing stent was removed with a snare.\n'
                       'Documented by Jo Rowe, RN: A new 10 Fr x 9 cm plastic\n'
                       'biliary stent was placed into the common bile duct.\n')


def q2(n: Note, mis: bool) -> dict:
    owner = 'documenting_clinician' if mis else 'nursing'
    return ercp(n, cannulation(n),
                n.event('E3', 'stent_removal', 'existing stent', 'was removed', session='X1', device=('snare', 'snare')),
                n.event('E4', 'stent', 'biliary stent', 'was placed', session='X1', duct=('biliary', 'biliary stent'),
                        places=[('common_bile_duct', 'common bile duct')]),
                sections=(n.part('N2', 'Documented by Jo Rowe, RN:', 'nursing_note', owner=owner,
                                 owner_words='Documented by Jo Rowe, RN', performer=None),))


Q3_TEXT = ERCP_HEAD + ('A 15 mm stone in the common bile duct was fragmented with mechanical lithotripsy.\n'
                       'Documented by Jo Rowe, RN: The stone fragments were extracted from the bile duct with an '
                       'extraction balloon.\n')


def q3(n: Note, mis: bool) -> dict:
    owner = 'documenting_clinician' if mis else 'nursing'
    return ercp(n, cannulation(n),
                n.event('E3', 'lithotripsy', 'mechanical lithotripsy', 'was fragmented', session='X1',
                        duct=('biliary', 'common bile duct'), device=('lithotripter', 'mechanical lithotripsy')),
                sweep(n, 'E4', 'were extracted', 'were extracted', ('stone_fragments', 'The stone fragments')),
                sections=(n.part('N2', 'Documented by Jo Rowe, RN:', 'nursing_note', owner=owner,
                                 owner_words='Documented by Jo Rowe, RN', performer=None),))


Q4_TEXT = EUS_HEAD + EUS_STATIONS + ('A 2 cm hypoechoic mass was seen in the pancreatic head.\n'
                                     'EUS-guided drainage of the gallbladder was performed.\n')


def q4(n: Note, mis: bool) -> dict:
    target = dict(structure=('pancreatic_fluid_collection', 'of the gallbladder')) if mis else \
        dict(structure=('gallbladder', 'of the gallbladder'), places=[('gallbladder', 'of the gallbladder')])
    return eus(n, n.event('E2', 'drainage', 'EUS-guided drainage', 'was performed', session='X1',
                          route=('eus_transmural', 'EUS-guided'), **target),
               exam_places=(('pancreas', 'pancreatic head'),))


Q5_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + 'Later, a 6 mm polyp in the sigmoid colon was removed with a cold snare.\n'


def q5(n: Note, mis: bool) -> dict:
    relation = ('earlier_date', 'Later') if mis else None
    doubts = () if mis else (n.doubt('date_relation', ('E2',), 'Later, a 6 mm polyp', 'unclear',
                                     ('on_date_of_service', 'earlier_date')),)
    return colo(n, snare(n, lesion=None, date_relation=relation), doubts=doubts)


Q6_TEXT = head('UPPER ENDOSCOPY REPORT') + EGD_FINDINGS + (
    'Cold forceps biopsies of the gastric antrum were taken.\n'
    'A submucosal injection of saline was given in the gastric body.\n')


def q6(n: Note, mis: bool) -> dict:
    return egd(n, n.event('E2', 'biopsy', 'Cold forceps biopsies', 'were taken', session='X1',
                          places=[('gastric_antrum', 'gastric antrum')], device=('cold_forceps', 'Cold forceps'),
                          date_relation=('earlier_date', 'Cold forceps biopsies') if mis else None),
               n.event('E3', 'injection', 'submucosal injection', 'was given', session='X1',
                       purpose=('lift_for_resection', 'submucosal injection'), route=('submucosal', 'submucosal'),
                       places=[('gastric_body', 'gastric body')]))


Q7_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + SNARE_LINE + ''.join(
    f'No polypectomy was performed in the {word} segment.\n' for word in ('first', 'second', 'third', 'fourth', 'fifth'))


def q7(n: Note, mis: bool) -> dict:
    denials = []
    for number, word in enumerate(('first', 'second', 'third', 'fourth', 'fifth'), start=3):
        breadth = ('all_of_kind', f'in the {word} segment') if (mis and number == 3) else ('segment', f'in the {word} segment')
        denials.append(n.event(f'E{number}', 'removal', 'No polypectomy', 'No polypectomy was performed',
                               anchor_words=f'in the {word} segment', session='X1', status_state=NEG, breadth=breadth))
    return colo(n, snare(n), *denials, lesions=(polyp(n),))


O1_TEXT = HEAD_OFFICE + VISIT + 'Rubber band ligation of one internal hemorrhoid was performed in the office today.\n' + TIME


def o1(n: Note, mis: bool) -> dict:
    if mis:
        return office(n)
    return office(n, n.event('E2', 'band_ligation', 'Rubber band ligation', 'was performed', session='X2',
                             places=[('rectum', 'internal hemorrhoid')],
                             date_relation=('on_date_of_service', 'in the office today')),
                  sessions=(n.session('X2', 'other_gi', 'Rubber band ligation'),))


BUNDLED = 'bundled as a procedural adjunct (4.3 CAUSE established otherwise; 4.7): an explanation naming the whole (RANK 18)'

CASES += [
    Case('A1', 'class', ('A1', 'BF5'), 'An ileal pouch-anal anastomosis filed as an anastomosis', A1_TEXT, a1,
         codes=(('44386', 'Biopsies of the pouch'),), caught=('type@Y1/0',),
         note='One code per case: two codes proposed for one biopsy compete (4.7), which would hold both.',
         expect={'i': {'44386': (R, None, None, '4.3 ENT pouch class: transanal through an established ileal pouch '
                                                '(D219)')},
                 'ii': {'44386': (H, 'procedure', Q, '4.3 ENT: the entry passed through has no established type '
                                                     '(RANK 8)')}}),
    Case('A1b', 'class', ('A1', 'BF5'), 'The ileal class on a pouchoscopy', A1_TEXT, a1,
         codes=(('44377', 'Biopsies of the pouch'),), caught=('type@Y1/0',),
         expect={'i': {'44377': (H, 'procedure', None, '4.3 ENT ileal class needs the oral approach (RANK 8)')},
                 'ii': {'44377': (H, 'procedure', None, 'the approach is still not oral')}}),
    Case('A2', 'class', ('A2', 'BF5'), 'An ileal J-pouch beside a gastric pouch and a Roux limb', A2_TEXT, a2,
         codes=(('44386', 'Biopsies of the proximal ileum'),), caught=('approach@X1/0', 'through@X1/0'),
         expect={'i': {'44386': (H, 'procedure', None, '4.3 ENT pouch class: never through a gastric pouch or a '
                                                       'Roux limb')},
                 'ii': {'44386': (H, 'procedure', Q, '4.3 ENT: the approach not established (RANK 8)')}}),
    Case('A2b', 'class', ('A2', 'BF5'), 'The ileal class through a gastric pouch and a Roux limb', A2_TEXT, a2,
         codes=(('44377', 'Biopsies of the proximal ileum'),), caught=('approach@X1/0', 'through@X1/0'),
         expect={'i': {'44377': (R, None, None, '4.3 ENT ileal class: oral, reached the ileum, completion silent '
                                                '(D217)')},
                 'ii': {'44377': (H, 'procedure', Q, '4.3 ENT: the approach not established (RANK 8)')}}),
    Case('A3', 'class', ('A3', 'BF19'), 'An anatomy history clause read as the scope\'s route', A3_TEXT, a3,
         codes=(('44382', 'Biopsies of the jejunum'),), caught=('approach@X1/0',),
         expect={'i': {'44382': (H, 'procedure', None, '4.3 ENT stoma class needs through_stoma')},
                 'ii': {'44382': (H, 'procedure', Q, '4.3 ENT: the approach not established (RANK 8)')}}),
    Case('A3b', 'class', ('A3', 'BF19'), 'The jejunal class beside a stoma history', A3_TEXT, a3,
         codes=(('44361', 'Biopsies of the jejunum'),), caught=('approach@X1/0',),
         expect={'i': {'44361': (R, None, None, '4.3 ENT jejunal class: oral, reached the jejunum')},
                 'ii': {'44361': (H, 'procedure', Q, '4.3 ENT: the approach not established (RANK 8)')}}),
    Case('C1', 'class', ('C1', 'BF4', 'BF14'), 'A bleeding control for bleeding this session\'s biopsy caused', C1_TEXT,
         c1, codes=(('43239', 'Cold forceps biopsies'), ('43255', 'controlled with a clip')), caught=('cause@E3/0',),
         expect={'i': {'43239': (R, None, None, 'SUPPORT met'),
                       '43255': (H, 'performed_status', EXP, BUNDLED)},
                 'ii': {'43239': (R, None, None, 'unchanged'),
                        # restated at round r3's integration: the silent-link rule (DESIGN-v2 b.8, DECISIONS D308 Q-B)
                        # reads the clip's silent part_of beside the biopsy as a doubt, asked first (act_part, RANK 17)
                        '43255': (H, 'act_part', Q, '4.3 CAUSE unresolved: act_cause (RANK 17); since round r3 the '
                                                    'silent part_of is a doubt too, asked first: act_part (RANK 17)')}}),
    Case('C2', 'class', ('C2',), 'A control naming the polypectomy site at a conflicting place', C2_TEXT, c2,
         codes=(('43251', 'hot snare'), ('43255', 'hemoclips')), caught=('cause@E3/0',),
         expect={'i': {'43251': (R, None, None, 'SUPPORT met'),
                       '43255': (H, 'performed_status', EXP, BUNDLED + '; a place conflict sets nothing apart (4.7, '
                                                                     '4.13: D77 dropped)')},
                 'ii': {'43251': (R, None, None, 'unchanged'),
                        # restated at round r3's integration (DESIGN-v2 b.8, DECISIONS D308 Q-B), as C1's
                        '43255': (H, 'act_part', Q, '4.3 CAUSE unresolved (RANK 17); since round r3 the silent part_of '
                                                    'is a doubt too, asked first: act_part (RANK 17)')}}),
    Case('C3', 'class', ('C3', 'BF14'), 'Cautery to an angioectasia read as a bleeding control', C3_TEXT, c3,
         codes=(('45382', 'Cautery was applied'), ('45388', 'Cautery was applied')),
         caught=('kind@E2/0', 'purpose@E2/0'),
         expect={'i': {'45388': (R, None, None, 'an ablation of the angioectasia (purpose treatment)'),
                       '45382': (H, 'performed_status', None, '4.4: no candidate of the bleeding-control group: not '
                                                              'documented (RANK 4)')},
                 'ii': {'45382': (H, 'performed_status', Q, 'SUPPORT row 1 unresolved: performed_status (RANK 4)'),
                        '45388': (H, 'performed_status', None, 'the act is possibly no ablation: no candidate')}}),
    Case('C4', 'class', ('C4', 'BF15'), 'A device-named procedural adjunct keeps its record', C4_TEXT, c4,
         codes=(('43251', 'hot snare'), ('43270', 'Cautery was applied')), caught=('kind@E3/0',),
         expect={'i': {'43251': (R, None, None, 'SUPPORT met'),
                       '43270': (H, 'performed_status', EXP, '4.7 procedural adjunct: part_of the removal, bundled '
                                                             '(an explanation naming the whole, RANK 18)')},
                 'ii': {'43251': (R, None, None, 'unchanged'),
                        '43270': (H, 'performed_status', None, 'the kind not established and possibly no ablation')}}),
    Case('Y1', 'class', ('Y1',), 'Another extraction\'s denial clause read as this sweep\'s', Y1_TEXT, y1,
         codes=(('43264', 'two stones were removed'),), caught=('yield@E3/0', 'yield@E4/0'),
         acts={'i': {'43264': ('E3',)}},
         expect={'i': {'43264': (R, None, None, '4.3 YIELD on the act that removed two stones')},
                 'ii': {'43264': (H, 'act_yield', Q, '4.3 YIELD unresolved on both sweeps (RANK 15)')}}),
    Case('Y2', 'class', ('Y2', 'BF11', 'BF21'), 'A sweep that states nothing carries 43264', Y2_TEXT, y2,
         codes=(('43264', 'were extracted'),), caught=('yield@E3/0',), acts={'i': {'43264': ('E4',)}},
         expect={'i': {'43264': (R, None, None, '4.3 YIELD on the balloon extraction')},
                 'ii': {'43264': (H, 'act_yield', Q, '4.3 YIELD: neither sweep\'s yield established')}}),
    Case('Y3', 'class', ('Y3',), 'A sweep that states no yield after a clean cholangiogram', Y3_TEXT, y3,
         codes=(('43264', 'swept several times'),), caught=('yield@E4/0',),
         expect={'i': {'43264': (H, 'act_yield', Q, '4.3 YIELD: a yield the document does not state is unknown: one '
                                                    'question (RANK 15)')},
                 'ii': {'43264': (H, 'act_yield', Q, '4.3 YIELD unresolved')}}),
    Case('Y4', 'class', ('Y4',), 'A purpose clause and an end state read as a yield', Y4_TEXT, y4,
         codes=(('43264', 'swept with an extraction balloon'),), caught=('yield@E3/0',),
         expect={'i': {'43264': (H, 'act_yield', EXP, '4.3 YIELD negated: documented as retrieving nothing')},
                 'ii': {'43264': (H, 'act_yield', Q, '4.3 YIELD unresolved')}}),
    Case('Y5', 'class', ('Y5',), 'A retrieval denial right after an own yield', Y5_TEXT, y5,
         codes=(('43264', 'two stones were removed'),),
         unlisted_ii=({'units': ['S6'], 'what': 'denial', 'kind': 'stone_extraction', 'session': 'X1'},),
         expect={'i': {'43264': (H, 'conflict:stone_extraction', Q, '4.5: the denial pairs on every row: '
                                                                    'CONTRADICTION (RANK 1)')},
                 'ii': {'43264': (H, 'performed_status', Q, '3.2.6 rule 4: the unlisted denial pairs UNRESOLVED; '
                                                            'RANK 2 (D228)')}}),
    Case('Y6', 'class', ('Y6',), 'A denial clause holding another event\'s words', Y6_TEXT, y6,
         codes=(('43264', 'swept with an extraction balloon'), ('43274', 'plastic biliary stent')),
         caught=('yield@E3/0',),
         expect={'i': {'43264': (H, 'act_yield', EXP, '4.3 YIELD negated'),
                       '43274': (R, None, None, '4.3 XCHG: no possibly performed counterpart')},
                 'ii': {'43264': (H, 'act_yield', Q, '4.3 YIELD unresolved'),
                        '43274': (R, None, None, 'unchanged')}}),
    Case('Y7', 'class', ('Y7', 'O1'), 'A denial pass 1 does not report', Y7_TEXT, y7,
         codes=(('43264', 'swept with an extraction balloon'),),
         unlisted_ii=({'units': ['S7'], 'what': 'denial', 'kind': 'stone_extraction', 'session': 'X1'},),
         expect={'i': {'43264': (H, 'act_yield', EXP, '4.3 YIELD negated')},
                 'ii': {'43264': (H, 'performed_status', Q, '3.2.6 rule 4: the unlisted denial (RANK 2, D228)')}}),
    Case('X1', 'class', ('X1', 'BF10', 'BF11'), 'A stent exchange named in the title', X1_TEXT, x1,
         codes=(('43276', 'biliary stent exchange'), ('43274', 'plastic biliary stent')), caught=('kind@E3/0',),
         checked=('kind@E3/0',),
         expect={'i': {'43276': (H, 'performed_status', None, '4.3 XCHG: the removal negated, 43276 not supported '
                                                              '(not documented, RANK 4)'),
                       '43274': (R, None, None, '4.3 XCHG: no possibly performed counterpart (X1)')},
                 'ii': {'43276': (H, 'performed_status', None, 'a title is never a statement (G6, I3) and pass 2 '
                                                              'contradicts the kind: SUPPORT row 1 not met'),
                        '43274': (H, 'performed_status', Q, '4.4: the only stent act filed is the title-named '
                                                            'exchange, its kind not established (a title is never a '
                                                            'statement, G6/I3), and no placement is filed: no candidate '
                                                            'of the group, not documented (RANK 4); never READY')}}),
    Case('D1', 'class', ('D1', 'BF17', 'HO-2'), 'An exceptive denial cited alone', D1_TEXT, d1,
         codes=(('43236', 'No other injection was given', True), ('43255', 'hemostatic injection')),
         caught=('scope.breadth@E3/0',),
         expect={'i': {'43236': (H, 'performed_status', None, '4.6 condition 3: an exceptive denial never excludes '
                                                              '(C-7): not documented'),
                       '43255': (R, None, None, '4.5 breadth row: the denial excepts the injection (INDEPENDENT)')},
                 'ii': {'43236': (H, 'performed_status', None, '4.6 condition 3: the breadth not established is no '
                                                              'exclusion (C-7), and no candidate is positive: not '
                                                              'documented (RANK 4), as in (i)'),
                        '43255': (H, 'statement_scope', Q, '4.5 breadth row UNRESOLVED (RANK 3)')}}),
    Case('D2', 'class', ('D2',), 'A partial-scope denial keeps the conflict question', D2_TEXT, d2,
         codes=(('45385', 'cold snare'),), caught=('scope.breadth@E3/0', 'target.places@E3/0'),
         subjects={'i': {'45385': 'E2'}, 'ii': {'45385': 'E2'}},
         expect={'i': {'45385': (H, 'statement_scope', Q, '4.5: a segment of unknown places never sets apart '
                                                          '(4.11): UNRESOLVED (RANK 3), bound to the cited snare')},
                 'ii': {'45385': (H, 'statement_scope', Q, '4.5 breadth and target rows UNRESOLVED')}}),
    Case('D3', 'class', ('D3', 'BF2'), 'A contradicted act is never bundled out of its question', D3_TEXT, d3,
         codes=(('45380', 'cold forceps biopsies'), ('45385', 'cold snare')), caught=('date_relation@E2/0',),
         expect={'i': {'45380': (H, 'conflict:biopsy', Q, '4.8 RANK 1: the biopsy is contradicted and never bundled '
                                                          '(D3)'),
                       '45385': (H, 'event_time', Q, 'the doubt on "Once" (RANK 6)')},
                 'ii': {'45380': (H, 'conflict:biopsy', Q, 'unchanged: RANK 1'),
                        '45385': (H, 'event_time', Q, 'SUPPORT row 3 unresolved')}}),
    Case('Q1', 'class', ('Q1', 'BF3'), 'Each held code names the act its decision depends on', Q1_TEXT, q1,
         codes=(('43239', 'biopsies of the gastric antrum'), ('43251', 'cold snare')),
         caught=('date_relation@E2/0', 'date_relation@E3/0'),
         subjects={'i': {'43239': 'E2', '43251': 'E3'}, 'ii': {'43239': 'E2', '43251': 'E3'}},
         expect={'i': {'43239': (H, 'event_time', Q, '4.8: one item per code on its own deciding act'),
                       '43251': (H, 'event_time', Q, '4.8: the snare\'s own item, never the biopsy\'s')},
                 'ii': {'43239': (H, 'event_time', Q, 'SUPPORT row 3 unresolved'),
                        '43251': (H, 'event_time', Q, 'SUPPORT row 3 unresolved')}}),
    Case('Q2', 'class', ('Q2', 'BF12'), 'A first hold never pre-empts the code\'s other facts', Q2_TEXT, q2,
         codes=(('43274', 'biliary stent was placed'),), caught=('entry@E4/0',),
         held={'i': {'43274': ('event_entry', 'event_performer')}, 'ii': {'43274': ('event_entry', 'event_performer')}},
         note='4.4 evaluates the code-specific rows over E* only (4.3: "over its E* acts"), so XCHG\'s duct fact is '
              'not recorded for a candidate that fails SUPPORT; S4\'s Q2 contract asks every unresolved required fact '
              'known. Built as the design; the step\'s NOTES, question Q-Q2.',
         expect={'i': {'43274': (H, 'event_entry', EXP, ENTRY_EXP + '; every SUPPORT witness stays a held fact '
                                                                    '(4.4: no early return, Q2)')},
                 'ii': {'43274': (H, 'event_entry', Q, ENTRY_Q)}}),
    Case('Q3', 'class', ('Q3',), 'A held code keeps its claims and its rival held', Q3_TEXT, q3,
         codes=(('43264', 'were extracted'), ('43265', 'mechanical lithotripsy')), caught=('entry@E4/0',),
         expect={'i': {'43264': (H, 'event_entry', EXP, ENTRY_EXP),
                       '43265': (H, 'competing_codes', Q, '4.7: a held code keeps its claims (D163, D167)')},
                 'ii': {'43264': (H, 'event_entry', Q, ENTRY_Q),
                        '43265': (H, 'competing_codes', Q, 'unchanged')}}),
    Case('Q4', 'class', ('Q4',), 'One item keyed to the fact it resolves', Q4_TEXT, q4,
         codes=(('43240', 'EUS-guided drainage'), ('43259', 'linear echoendoscope')),
         caught=('target.structure@E2/0',),
         expect={'i': {'43240': (H, 'target', EXP, '4.3 STRUCT:pfc: another structure, held (an explanation, '
                                                   'RANK 12)'),
                       '43259': (H, 'base_included', EXP, '4.7 base_included: the drainage is a reportable act')},
                 'ii': {'43240': (H, 'target', Q, '4.3 STRUCT:pfc unresolved (RANK 12)'),
                        '43259': (H, 'base_included', None, 'the drainage still an act of the session')}}),
    Case('Q5', 'class', ('Q5',), 'A standing pre-v2 answer is asked differently, never applied', Q5_TEXT, q5,
         codes=(('45385', 'cold snare'),), caught=('date_relation@E2/0',),
         answers=({'code': '45385', 'family': 'colonoscopy', 'fact': 'event_time', 'value': 'not_documented',
                   'question': 'cpt-studio-question@1:' + '0' * 64, 'answer_id': 'answer-1'},),
         note='Appendix C: Q5 is out of scope (answer binding unchanged); built so that a pre-v2 answer is shown '
              'asked differently and the code stays held (4.8: v2 items have new fingerprints).',
         expect={'i': {'45385': (H, 'event_time', Q, 'the doubt on "Later" (RANK 6); the pre-v2 answer binds to no '
                                                     'v2 item')},
                 'ii': {'45385': (H, 'event_time', Q, 'SUPPORT row 3 unresolved')}}),
    Case('Q6', 'class', ('Q6',), 'An act no code is proposed for stays listed', Q6_TEXT, q6,
         codes=(('43239', 'Cold forceps biopsies'),), caught=('date_relation@E2/0',),
         listed={'i': (('not_covered', ('E3',), True),), 'ii': (('not_covered', ('E3',), True),)},
         note='Appendix C: Q6 is out of scope (listing policy unchanged); built so that the injection no code reads '
              'is listed (not_covered, beside the session\'s proposed code), marked for the second review, whether '
              'that code is READY or held.',
         expect={'i': {'43239': (R, None, None, 'SUPPORT met')},
                 'ii': {'43239': (H, 'event_time', Q, 'SUPPORT row 3 unresolved')}}),
    Case('Q7', 'class', ('Q7',), 'Every statement a hold reads stays a held fact', Q7_TEXT, q7,
         codes=(('45385', 'cold snare'),), caught=('scope.breadth@E3/0',),
         held={'i': {'45385': ('statement_scope@E2x5',)}, 'ii': {'45385': ('statement_scope@E2x5',)}},
         note='Appendix C: Q7 is out of scope (display policy); built so that each of five statements keeps its own '
              'witness in held_facts (4.4 [R:HO-8]), which the reviewer sees as fixed sentences.',
         expect={'i': {'45385': (H, 'statement_scope', Q, '4.5: five segments of unknown places: each UNRESOLVED')},
                 'ii': {'45385': (H, 'statement_scope', Q, 'unchanged: the misfiled breadth not established')}}),
    Case('O1', 'class', ('O1',), 'An act pass 1 omits beside an office visit', O1_TEXT, o1,
         codes=(('99213', 'seen in the office'),),
         unlisted_ii=({'units': ['S5'], 'what': 'act', 'kind': 'band_ligation', 'session': ''},),
         expect={'i': {'99213': (H, 'separate_em', Q, '4.7 C-3: the banding makes a done procedure day')},
                 'ii': {'99213': (H, 'event_time', Q, '3.2.6 rule 5: the unlisted act is an undatable possible '
                                                      'procedure; no act establishes the day (RANK 6)')}}),
]


# --- the borderline filings with a phrase of their own (the others are filed by the class cases that name them) --------

BF1_TEXT = HEAD_OFFICE + VISIT + ('Immediately prior to this visit, I performed a flexible sigmoidoscopy to 40 cm, which '
                                  'showed internal hemorrhoids.\n') + TIME


def bf1(n: Note, mis: bool) -> dict:
    return office(n, n.event('E2', 'examination', 'flexible sigmoidoscopy', 'I performed', session='X2',
                             date_relation=('earlier_date' if mis else 'on_date_of_service',
                                            'Immediately prior to this visit'),
                             performer=('documenting_team', 'I performed')),
                  sessions=(n.session('X2', 'flex_sig', 'flexible sigmoidoscopy', exam='E2',
                                      encounter=('separate_encounter', 'Immediately prior to this visit'),
                                      reached=[('stated_depth', 'to 40 cm')]),))


BF2_TEXT = HEAD_OFFICE + VISIT + 'Colonoscopy showed internal hemorrhoids.\n' + TIME


def bf2(n: Note, mis: bool) -> dict:
    doubts = () if mis else (n.doubt('date_relation', ('E2',), 'Colonoscopy showed', 'unclear',
                                     ('on_date_of_service', 'earlier_date')),
                             n.doubt('performer', ('E2',), 'Colonoscopy showed', 'unclear',
                                     ('documenting_team', 'other_clinician')))
    return office(n, n.event('E2', 'examination', 'Colonoscopy', 'showed', session='X2',
                             date_relation=('earlier_date', 'Colonoscopy showed') if mis else None),
                  sessions=(n.session('X2', 'colonoscopy', 'Colonoscopy', exam='E2'),), doubts=doubts)


BF4_TEXT = head('UPPER ENDOSCOPY REPORT') + (
    'History: On June 4, 2030 the esophageal stricture was dilated with a balloon.\n'
    'Findings: The gastroscope was advanced to the second portion of the duodenum.\n'
    'The esophageal stricture was dilated with a balloon to 15 mm.\n'
    'Oozing at the dilation site was treated with an epinephrine injection.\n')


def bf4(n: Note, mis: bool) -> dict:
    cause = dict(cause=('earlier_procedure', 'Oozing at the dilation site')) if mis else \
        dict(cause=('act_of_this_session', 'at the dilation site'), cause_event=('E3', 'at the dilation site'))
    history = n.event('E2', 'dilation', 'was dilated with a balloon', 'was dilated', session='X1',
                      date_relation=('earlier_date', 'On June 4, 2030'), date=('2030-06-04', 'On June 4, 2030'),
                      places=[('esophagus', 'esophageal stricture')], device=('balloon', 'balloon'))
    today = n.event('E3', 'dilation', 'dilated with a balloon to 15 mm', 'was dilated', session='X1',
                    places=[('esophagus', 'The esophageal stricture')], device=('balloon', 'balloon'),
                    structure=('stricture', 'stricture'))
    injection = n.event('E4', 'injection', 'epinephrine injection', 'was treated', session='X1',
                        purpose=('hemostasis', 'Oozing'), device=('injection', 'injection'), **cause)
    return n.answer(sections=history_and_findings(n),
                    sessions=[n.session('X1', 'egd', 'gastroscope', exam='E1',
                                        reached=[('second_portion_duodenum', 'second portion of the duodenum')])],
                    events=[n.event('E1', 'examination', 'gastroscope', 'was advanced', session='X1'), history, today,
                            injection])


BF6_TEXT = EUS_HEAD + EUS_STATIONS + 'A 2 cm hypoechoic mass was seen in the pancreatic head.\n'


def bf6(n: Note, mis: bool) -> dict:
    return eus(n, stations=[] if mis else None, exam_places=(('pancreas', 'pancreatic head'),))


BF8_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + (
    'A 15 mm polyp was seen at the splenic flexure.\n'
    'A tattoo was placed 3 cm distal to the splenic flexure lesion.\n'
    'No injection was given in the splenic flexure.\n')


def bf8(n: Note, mis: bool) -> dict:
    place = ('splenic_flexure', 'the splenic flexure lesion') if mis else ('descending_colon', '3 cm distal to the')
    return colo(n, n.event('E3', 'tattoo', 'A tattoo', 'was placed', session='X1', places=[place],
                           purpose=('marking', 'A tattoo')),
                n.event('E4', 'injection', 'No injection', 'No injection was given', session='X1', status_state=NEG,
                        breadth=('single_target', 'in the splenic flexure'),
                        places=[('splenic_flexure', 'in the splenic flexure')]))


BF11_TEXT = ERCP_HEAD + ('A biliary sphincterotomy was performed.\n'
                         'Three stones were extracted from the bile duct with an extraction balloon.\n'
                         'Impression: Choledocholithiasis; biliary sphincterotomy and complete balloon stone extraction.\n')


def bf11(n: Note, mis: bool) -> dict:
    extraction = sweep(n, 'E4', 'were extracted', 'were extracted', ('stones', 'Three stones'))
    if mis:
        extraction['kind']['sources'].append(n.src('complete balloon stone extraction'))
    else:
        extraction['restatements'] = [{'units': [n.u('complete balloon stone extraction')], 'role': 'summarizes'}]
    return ercp(n, cannulation(n), n.event('E3', 'sphincterotomy', 'A biliary sphincterotomy', 'was performed',
                                           session='X1', duct=('biliary', 'biliary')), extraction,
                sections=(n.part('N2', 'Impression:', 'impression'),))


BF16_TEXT = head('UPPER ENDOSCOPY REPORT') + EGD_FINDINGS + 'A polypectomy of the gastric body polyp was performed.\n'


def bf16(n: Note, mis: bool) -> dict:
    return egd(n, n.event('E2', 'snare' if mis else 'removal', 'polypectomy', 'was performed', session='X1',
                          places=[('gastric_body', 'gastric body polyp')]))


BF21_TEXT = ERCP_HEAD + 'Three stones, the largest 9 mm, were extracted from the bile duct with an extraction balloon.\n'


def bf21(n: Note, mis: bool) -> dict:
    found = ('stone_fragments', 'Three stones') if mis else ('stones', 'Three stones')
    return ercp(n, cannulation(n), sweep(n, 'E3', 'were extracted', 'were extracted', found))


CASES += [
    Case('BF1', 'borderline', ('BF1', 'T1', 'T2'), '"Immediately prior to this visit"', BF1_TEXT, bf1,
         codes=(('99213', 'seen in the office'), ('45330', 'flexible sigmoidoscopy')), caught=('date_relation@E2/0',),
         expect={'i': {'45330': (R, None, None, '4.3 row 3: a same-day act supports its code (T2, D180)'),
                       '99213': (H, 'separate_em', Q, '4.7 C-3: a done procedure day, no separate statement')},
                 'ii': {'45330': (H, 'event_time', Q, 'SUPPORT row 3 unresolved'),
                        '99213': (H, 'separate_em', Q, '4.7: 45330, a counted procedural code its rule does not '
                                                       'support, adds its family to the POSSIBLE list: a possible '
                                                       'procedure day, no separate statement')}}),
    Case('BF2', 'borderline', ('BF2', 'T4'), 'An undated finding beside a visit', BF2_TEXT, bf2,
         codes=(('99213', 'seen in the office'),), caught=('date_relation@E2/0',),
         expect={'i': {'99213': (H, 'event_time', Q, 'the undated examination is a doubt (unknown, never "not '
                                                     'today"): undatable beside the E/M (RANK 6)')},
                 'ii': {'99213': (H, 'event_time', Q, 'the date relation not established: undatable')}}),
    Case('BF4', 'borderline', ('BF4', 'C1'), 'A history act at the site of today\'s bleeding control', BF4_TEXT, bf4,
         codes=(('43249', 'dilated with a balloon to 15 mm'), ('43255', 'epinephrine injection')),
         caught=('cause@E4/0',),
         expect={'i': {'43249': (R, None, None, '4.3 TECH balloon, SITE esophageal; the history dilation is another '
                                                'date'),
                       '43255': (H, 'performed_status', EXP, BUNDLED)},
                 'ii': {'43249': (R, None, None, 'unchanged'),
                        # restated at round r3's integration (DESIGN-v2 b.8, DECISIONS D308 Q-B), as C1's
                        '43255': (H, 'act_part', Q, '4.3 CAUSE unresolved (RANK 17); since round r3 the silent part_of '
                                                    'is a doubt too, asked first: act_part (RANK 17)')}}),
    Case('BF6', 'borderline', ('BF6', 'S1', 'SC-B'), 'The EUS station line cited only as the examination', BF6_TEXT, bf6,
         codes=(('43259', 'linear echoendoscope'),), caught=('completeness@X1',),
         expect={'i': {'43259': (R, None, None, '4.3 STATIONS: the three upper stations supported examined')},
                 'ii': {'43259': (H, 'exam_stations', Q, '4.3 STATIONS: an empty list whose completeness claim is not '
                                                         'established [R:SC-B]')}}),
    Case('BF8', 'borderline', ('BF8', 'G1'), 'A tattoo\'s place taken from its reference point', BF8_TEXT, bf8,
         codes=(('45381', 'A tattoo'),), caught=('target.places@E3/0',),
         expect={'i': {'45381': (R, None, None, '4.5 target row: the tattoo distal to the lesion is apart from the '
                                                'splenic-flexure denial (pair controls rejected)')},
                 'ii': {'45381': (H, 'statement_scope', Q, '4.5 target row UNRESOLVED (RANK 3)')}}),
    Case('BF11', 'borderline', ('BF11', 'X1', 'Y2'), 'An impression restatement cited as the act\'s statement',
         BF11_TEXT, bf11, codes=(('43262', 'A biliary sphincterotomy'), ('43264', 'were extracted')),
         caught=('kind@E4/0',), checked=('kind@E4/0',),
         expect={'i': {'43262': (R, None, None, 'SUPPORT met'),
                       '43264': (R, None, None, 'the impression is a summarizing restatement (G6), never the statement')},
                 'ii': {'43262': (H, 'statement_scope', Q, '4.5 [R:HO-3][R:HO-5]: the extraction, its kind failing '
                                                           'G1, is a possible statement of any ERCP kind and pairs '
                                                           'with the sphincterotomy (RANK 3)'),
                        '43264': (H, 'performed_status', Q, 'a kind source in another unit than the statement fails G1: '
                                                            'SUPPORT row 1 not established (RANK 4)')}}),
    Case('BF16', 'borderline', ('BF16', 'N1'), 'A polypectomy whose technique is not stated', BF16_TEXT, bf16,
         codes=(('43251', 'polypectomy'),), caught=('kind@E2/0',),
         expect={'i': {'43251': (H, 'act_method', Q, '4.3 row 1: a positive umbrella never supports a method code '
                                                     '(RANK 9)')},
                 'ii': {'43251': (H, 'performed_status', Q, 'SUPPORT row 1 unresolved (RANK 4)')}}),
    Case('BF21', 'borderline', ('BF21', 'Y2', 'T7'), 'A yield stated as the act\'s attribute', BF21_TEXT, bf21,
         codes=(('43264', 'were extracted'),), caught=('yield@E3/0',),
         expect={'i': {'43264': (R, None, None, '4.3 YIELD stones')},
                 'ii': {'43264': (H, 'act_yield', Q, '4.3 YIELD unresolved')}}),
]
