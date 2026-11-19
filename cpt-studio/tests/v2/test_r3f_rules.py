"""Round r3's fourth repair, lane rules5 (DECISIONS D328 (1) and its addendum; build-v2/a2b/r3b/r3f/rules5/NOTES.md):
the lower-GI route table by principle. TEXT-ONLY and SYNTHETIC: every note is written for these tests or is the third
adversarial pass's constructed input word for word (fictional clinicians), every pass-1 answer is built by hand with
test_settle's builders and every pass-2 answer by test_r2cl_lesion's faithful oracle, every other FactSet in code;
nothing is sent.

The rule (catalogue.LOWER_ROUTES, read by engine/evaluate's route rows): every lower-GI endoscopy code of the catalogue
(catalogue.lower_gi) declares, in one typed table, its route (per anus, through a stoma, through a pouch) and the
anatomy it needs (a colon to traverse, a rectum and sigmoid, a colonic stoma, an ileal stoma, a pouch); a code is READY
only when the record establishes its route and nothing filed contradicts the anatomy it needs, read fail-closed. For a
per-anus code: an approach established through a stoma is the class's explanation; a stoma that may exist asks the
approach; an entry that may be an ileal pouch, or an approach established or possible through a pouch, is the table's
own hold; for the colonoscopy family, no colon possible is the table's own hold; there is no rectum-absent arm.
- FindingTests: L6C-1 (the colonoscopy's and the sigmoidoscopy's EUS codes per anus) and L6C-3 (the sigmoidoscopy
  family), each the attacker's input word for word (r3d/attack/L6-generality/l6: t03, t08, t09, t10) - READY on int6 and
  int6 + rules4, held here; the attacker's controls (t03 e5, e6, the through-stoma EUS of e7 and e9, t11) as before.
- CompletenessTests: every lower-GI code of the catalogue has a row; the rows are the ruling's families; a code with no
  row holds at run time.
- AnusCensusTests: every per-anus catalogue code x every anatomy entry state x every approach state (and the act's
  session open): the route row exactly as the ruling declares it (states DECLARED in test_r3d_rules).
- IlealStomaTests, PouchTests: the ileoscopy through a stoma needs an ileal stoma; the pouch codes as before.
- AddendumTests: the D328 addendum on rules4's questions - LOWER's subtype read (Q1), both sides of the colon cover the
  transverse (Q2), an anastomosis's joins (Q3; only a subtype AND joins both silent stays as int6).
- VariantTests: constructed variants per family (at least six each), holding or left as before exactly as the rule says.
- CommonInputTests: the common inputs D328 (1) lists, end to end, exactly as int6 decides them.
- MonotonicityTests (P-MONO: no 9.4 weakening releases a held scene) and ClosureTests (P-INDEP's closure: the route
  table's reads are every lower-GI code's).
"""
from __future__ import annotations

import itertools
from dataclasses import replace
from types import MappingProxyType
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, catalogue, evaluate, questions
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import requirements as RQ
from studio.interpretation.engine.requirements_table import Tag
from studio.interpretation.engine.types import Id
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_r2cl_lesion as R2CL
from tests.v2 import test_r3c_rules as RR
from tests.v2 import test_r3d_rules as RD
from tests.v2.test_settle import answer, event, fact, frame, labelled, opening, session, src

A, LM, EX = ct.Attribute, ct.Landmark, ct.Extent
AT, AP, SUB, SK, Kind = ct.AnatomyType, ct.Approach, ct.AnastomosisSubtype, ct.SessionKind, ct.Kind
EC, EUS = catalogue.EnteroscopyClass, catalogue.EusClass
E1, E2, X1 = Id.parse('E1'), Id.parse('E2'), Id.parse('X1')
Y1, Y2, Y3 = Id.parse('Y1'), Id.parse('Y2'), Id.parse('Y3')
sup, unres, neg, doubted, contra = EF.sup, EF.unres, EF.neg, EF.doubted, EF.contra
UNAPPRAISED = ct.Reason.UNAPPRAISED
OPEN = ct.Reason.APPRAISAL_UNCLEAR
ROUTE = RR.ROUTE                                     # 'coding_rule:stoma_route': the route table's own hold
LOWER_RULE = questions.coding_rule(questions.Rule.LOWER)
T, U, Fa = evaluate.Truth.T, evaluate.Truth.U, evaluate.Truth.F
HELD, READY = 'needs_clarification', 'ready'
TABLE_HOLD = [('procedure', ROUTE, A.TYPE, 'X1', 'question')]
held_of, serving = RR.held_of, RR.serving


def guarded(R, code, session=X1) -> bool:
    """Round r3's round 5 (DECISIONS D330 (1), lane rules6): whether the lower-GI path guard holds ``code``'s route row
    in ``R`` where every arm leaves the route met (evaluate.path_guard, the owning function the pins below move by): an
    anatomy entry matching no row of the ruled harmless set, the colon's cover beside a family that needs a colon or a
    rectum and sigmoid, or a per-anus route's own approach or through."""
    return evaluate.path_guard(catalogue.lower_route(str(code)), R, session)


def properties():
    from tests.v2 import test_properties
    return test_properties


def open_denial(value):
    """A claim pass 1 wrote negated that pass 2 did not establish (D294 RD-3: every value of its domain stays possible)."""
    return EF.fact(ct.Result.UNRESOLVED, value, ct.FactState.NEGATED, reasons=(OPEN,))


def witnesses(row) -> list:
    return [(held.cause, held.attribute, held.subject, held.result) for held in row.witnesses]


def label_of(code) -> object:
    """The row a code's route is read in: a lower EUS code's LOWER row, a colonoscopy code's COLFULL row, any other
    lower-GI code's the route table's own (Requirement.ROUTE_TABLE)."""
    c = evaluate._code(str(code))
    if c.has(Tag.LOWER):
        return Tag.LOWER
    return Tag.COLFULL if c.has(Tag.COLFULL) else RQ.Requirement.ROUTE_TABLE


def route_row(R, code, event=E2):
    """``code``'s route row over act ``event`` (evaluate.code_rows; its group the code's first)."""
    c = evaluate._code(str(code))
    group = catalogue.requirements(c.link)[0]
    rows = [row for row in evaluate.code_rows(str(code), group, R, event) if row.requirement is label_of(code)]
    assert len(rows) == 1, (code, rows)
    return rows[0]


# The session each lower-GI code's scope is in, and a reached point its class reaches (so a LOWER row's reach part is T)
def session_of(code: int):
    exam = catalogue.LOWER_EUS_CLASS.get(code)
    if exam is EUS.SIGMOIDOSCOPIC:
        return SK.EUS, EX.SIGMOID_COLON
    if exam is not None:
        return SK.EUS, EX.CECUM
    family = catalogue.CODES[code].family
    return family, {SK.COLONOSCOPY: EX.TERMINAL_ILEUM, SK.FLEX_SIG: EX.SIGMOID_COLON, SK.ENTEROSCOPY: EX.ILEUM}[family]


def scope(code, *, approach=None, through=None, entries=None, act_session=None, reached=None, exam_places=False):
    """A settled lower-GI endoscopy X1 of ``code``'s family (a lower EUS for an EUS code) reaching ``reached`` (by
    default a point of the code's class), its approach ``approach`` and through ``through`` (None: silent), its
    examination E1 (its places the rectum when ``exam_places``: an EUS's R6 target) and E2 - an FNA of a lymph node for
    an EUS sampling code, else a cold-forceps biopsy of the rectum - (its session ``act_session``, a Fact, or X1
    supported), with the anatomy entries ``entries`` {id: facts}."""
    kind, point = session_of(int(code))
    doc = EF.Doc()
    facts = dict(encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER), reached=[reached or sup(point)], approach=approach,
                 through=through)
    if kind is SK.EUS:
        facts['tract'] = sup(ct.Tract.LOWER)
    doc.session(1, kind, **facts)
    doc.exam(1, **({'places': [sup(LM.RECTUM)]} if exam_places else {}))
    if Kind.FNA in catalogue.requirements(evaluate._code(str(code)).link)[0]:  # an EUS sampling code's act
        doc.act(2, Kind.FNA, places=[sup(LM.LYMPH_NODE)],
                **({'session': act_session} if act_session is not None else {}))
    else:
        doc.act(2, Kind.BIOPSY, places=[sup(LM.RECTUM)], device=sup(ct.Device.COLD_FORCEPS),
                **({'session': act_session} if act_session is not None else {}))
    doc.anatomy.update({entry: dict(facts) for entry, facts in (entries or {}).items()})
    return doc.build()


def entry_of(**facts):
    """An anatomy entry's facts by attribute name (type, organ, subtype, joins - a sequence of member facts; None or
    absent: not filed)."""
    names = {'type': A.TYPE, 'organ': A.ORGAN, 'subtype': A.SUBTYPE, 'joins': A.JOINS}
    return {names[name]: (tuple(value) if name == 'joins' else (value,)) for name, value in facts.items()
            if value is not None}


STOMA_ENTRY = entry_of(type=sup(AT.STOMA))
POUCH_ENTRY = entry_of(type=sup(AT.ILEAL_POUCH))
ABSENT_COLON = entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.COLON))


def statuses(text, data, *codes) -> dict:
    found = R2CL.outcomes(text, data, R2CL.FAITHFUL, *codes)
    return {code: found[code][:2] for code, _quote in codes}


# === the findings: the attacker's inputs word for word (r3d/attack/L6-generality/l6) =================================

EUS_HEAD = ('SYNTHETIC LOWER ENDOSCOPIC ULTRASOUND REPORT\n'       # S1
            'Date of service: 03/14/2031\n'                         # S2
            'Endoscopist: Corvin Ashdale, MD (fictional)\n'         # S3
            '\n')


def eus_case(history, findings, act, *, anatomy, approach, reached, exam_places, act_place=None, act_kind=None,
             act_words='', act_status='was performed', through=None):
    """t03_eus_anus.build, word for word: anatomy [(id, type, type words, [organ...], [subtype...], [joins...])]."""
    text = EUS_HEAD + f'History: {history}\n' + f'Findings: {findings}\n' + (f'{act}\n' if act else '')
    entries = [{'id': yid, 'type': fact(typ, src(['S4'], words)),
                'organ': [fact(organ, src(['S4'], words)) for organ in organs],
                'subtype': [fact(value, src(['S4'], words)) for value in subtypes],
                'joins': [fact(value, src(['S4'], words)) for value in joins]}
               for yid, typ, words, organs, subtypes, joins in anatomy]
    sess = session('X1', fact('eus', src(['S5'], 'echoendoscope')), examination=[fact('E1', src(['S5']))],
                   encounter=[fact('this_encounter', frame(['S2']))],
                   tract=[fact('lower', src(['S5'], 'echoendoscope'))],
                   approach=[fact(approach[0], src(['S5'], approach[1]))],
                   through=[fact(through, src(['S5'], approach[1]))] if through else [],
                   reached=[fact(value, src(['S5'], words)) for value, words in reached])
    exam_status = next(w for w in ('was introduced', 'was inserted', 'was advanced') if w in findings)
    events = [event('E1', ['S5'], 'echoendoscope', exam_status, 'examination', session=[fact('X1', src(['S5']))],
                    target__places=[fact(value, src(['S5'], words)) for value, words in exam_places])]
    if act_kind:
        events.append(event('E2', ['S6'], act_words, act_status, act_kind, session=[fact('X1', src(['S6']))],
                            target__places=[fact(act_place[0], src(['S6'], act_place[1]))]))
    data = answer(
        sections=[opening(), labelled('N1', 'S4', 'History:', 'history'), labelled('N2', 'S5', 'Findings:', 'findings')],
        sessions=[sess], anatomy=entries, events=events)
    return text, data


IPAA = 'Total proctocolectomy with an ileal pouch-anal anastomosis in 2025.'
IPAA_ENTRIES = [('Y1', 'surgically_absent', 'Total proctocolectomy', ['colon'], [], []),
                ('Y2', 'ileal_pouch', 'ileal pouch-anal anastomosis', [], [], [])]
F1 = ('The echoendoscope was advanced through the ileal pouch into the neo-terminal ileum, and the pouch wall and the '
      'presacral space were examined.')
F2 = ('The echoendoscope was inserted per anus and advanced through the ileal pouch into the neo-terminal ileum, and '
      'the pouch wall was examined.')
F3 = ('The echoendoscope was inserted per anus and advanced through the ileal pouch into the neo-terminal ileum, and '
      'a 14 mm presacral lymph node was seen.')
A3 = 'Fine needle aspiration of the presacral lymph node was performed with a 22-gauge needle.'
IRA_EUS = 'Total abdominal colectomy with an ileorectal anastomosis in 2026.'
F4 = ('The echoendoscope was inserted per anus, the rectal wall was examined, and the scope was advanced across the '
      'ileorectal anastomosis 10 cm into the ileum.')
F5 = 'The echoendoscope was inserted per anus and advanced to the cecum, and the rectal wall was examined.'
F6 = ('The echoendoscope was introduced through the ileostomy and advanced 20 cm into the ileum, and the ileal wall '
      'was examined.')
F7 = ('The echoendoscope was introduced through the colostomy and advanced to the cecum, and the colonic wall was '
      'examined.')
NTI = [('neo_terminal_ileum', 'into the neo-terminal ileum')]
EUS_CASES = {
    'e1-ipaa-eus-through-pouch': (eus_case(IPAA, F1, '', anatomy=IPAA_ENTRIES,
                                           approach=('through_pouch', 'through the ileal pouch'), reached=NTI,
                                           exam_places=[('pouch', 'the pouch wall')]),
                                  [('45391', 'the pouch wall and the presacral space were examined')]),
    'e2-ipaa-eus-transanal': (eus_case(IPAA, F2, '', anatomy=IPAA_ENTRIES, approach=('transanal', 'inserted per anus'),
                                       reached=NTI, exam_places=[('pouch', 'the pouch wall')]),
                              [('45391', 'the pouch wall was examined')]),
    'e3-ipaa-eus-fna': (eus_case(IPAA, F3, A3, anatomy=IPAA_ENTRIES, approach=('transanal', 'inserted per anus'),
                                 reached=NTI, exam_places=[('pouch', 'ileal pouch')],
                                 act_place=('lymph_node', 'presacral lymph node'), act_kind='fna',
                                 act_words='Fine needle aspiration'),
                        [('45392', A3)]),
    'e4-ira-eus': (eus_case(IRA_EUS, F4, '',
                            anatomy=[('Y1', 'surgically_absent', 'Total abdominal colectomy', ['colon'], [], []),
                                     ('Y2', 'anastomosis', 'ileorectal anastomosis', [], ['ileorectal'],
                                      ['ileum', 'rectum'])],
                            approach=('transanal', 'inserted per anus'), reached=[('ileum', '10 cm into the ileum')],
                            exam_places=[('rectum', 'the rectal wall')]),
                   [('45391', 'the rectal wall was examined')]),
    'e5-control-lower-eus-cecum': (eus_case('Rectal wall thickening on imaging.', F5, '', anatomy=[],
                                            approach=('transanal', 'inserted per anus'),
                                            reached=[('cecum', 'advanced to the cecum')],
                                            exam_places=[('rectum', 'the rectal wall')]),
                                   [('45391', 'the rectal wall was examined')]),
    'e6-stoma-twin-44406': (eus_case('Total proctocolectomy with an end ileostomy in 2024.', F6, '',
                                     anatomy=[('Y1', 'surgically_absent', 'Total proctocolectomy', ['colon'], [], []),
                                              ('Y2', 'stoma', 'end ileostomy', [], [], [])],
                                     approach=('through_stoma', 'through the ileostomy'), through='Y2',
                                     reached=[('ileum', '20 cm into the ileum')],
                                     exam_places=[('ileum', 'the ileal wall')]),
                            [('44406', 'the ileal wall was examined')]),
    'e7-colostomy-eus-as-45391': (eus_case('Hartmann procedure with an end colostomy in 2027.', F7, '',
                                           anatomy=[('Y1', 'stoma', 'end colostomy', [], [], []),
                                                    ('Y2', 'surgically_absent', 'Hartmann procedure',
                                                     ['sigmoid_colon'], [], [])],
                                           approach=('through_stoma', 'through the colostomy'), through='Y1',
                                           reached=[('cecum', 'advanced to the cecum')],
                                           exam_places=[('colon', 'the colonic wall')]),
                                  [('45391', 'the colonic wall was examined'),
                                   ('44406', 'the colonic wall was examined')]),
}
FNA8 = 'Fine needle aspiration of the mesenteric lymph node was performed with a 22-gauge needle.'
FNA9 = 'Fine needle aspiration of the pericolic lymph node was performed with a 22-gauge needle.'
EUS_CASES.update({  # t08_eus_stoma, word for word
    'e8-loop-ileo-eus-icv-fna': (eus_case(
        'Low anterior resection with a diverting loop ileostomy in 2030.',
        'The echoendoscope was introduced through the loop ileostomy into the efferent limb and advanced to the '
        'ileocecal valve, and a 12 mm mesenteric lymph node was seen.', FNA8,
        anatomy=[('Y1', 'stoma', 'loop ileostomy', [], [], [])], approach=('through_stoma', 'through the loop ileostomy'),
        through='Y1', reached=[('ileocecal_valve', 'advanced to the ileocecal valve')],
        exam_places=[('ileum', 'efferent limb')], act_place=('lymph_node', 'mesenteric lymph node'), act_kind='fna',
        act_words='Fine needle aspiration'), [('44407', FNA8), ('45392', FNA8)]),
    'e9-colostomy-eus-cecum-fna': (eus_case(
        'Hartmann procedure with an end colostomy in 2027.',
        'The echoendoscope was introduced through the colostomy and advanced to the cecum, and a 12 mm pericolic lymph '
        'node was seen.', FNA9,
        anatomy=[('Y1', 'stoma', 'end colostomy', [], [], []),
                 ('Y2', 'surgically_absent', 'Hartmann procedure', ['sigmoid_colon'], [], [])],
        approach=('through_stoma', 'through the colostomy'), through='Y1', reached=[('cecum', 'advanced to the cecum')],
        exam_places=[('colon', 'pericolic')], act_place=('lymph_node', 'pericolic lymph node'), act_kind='fna',
        act_words='Fine needle aspiration'), [('44407', FNA9), ('45392', FNA9)]),
})
RECTAL_WALL = 'the rectal wall was examined'
EUS_CASES.update({  # t11_lower_eus_reads, word for word (LOWER's organ read beside an ordinary history entry)
    name: (eus_case('Laparoscopic cholecystectomy in 2019.',
                    f'The echoendoscope was inserted per anus and {reach[1]}, and the rectal wall was examined.', '',
                    anatomy=[('Y1', 'surgically_absent', 'Laparoscopic cholecystectomy', ['gallbladder'], [], [])],
                    approach=('transanal', 'inserted per anus'), reached=[reach],
                    exam_places=[('rectum', 'the rectal wall')]), [(code, RECTAL_WALL)])
    for name, reach, code in (('l1-rectal-eus-chole', ('sigmoid_colon', 'advanced to the sigmoid colon'), '45341'),
                              ('l2-colonic-eus-chole', ('cecum', 'advanced to the cecum'), '45391'))})

POUCH_HEAD = ('SYNTHETIC POUCHOSCOPY REPORT\n'                       # S1
              'Date of service: 03/14/2031\n'                         # S2
              'Endoscopist: Corvin Ashdale, MD (fictional)\n'         # S3
              '\n')
POUCH_BX = 'Two biopsies of the pouch body were taken with cold forceps.'


def pouch_flexsig(findings, approach, reached):
    """t09_pouch_flexsig.build, word for word: a pouchoscopy documented with a flexible sigmoidoscope after a total
    proctocolectomy with an ileal pouch."""
    text = POUCH_HEAD + f'History: {IPAA}\n' + f'Findings: {findings}\n' + POUCH_BX + '\n'
    entries = [{'id': yid, 'type': fact(typ, src(['S4'], words)), 'organ': [fact(o, src(['S4'], words)) for o in organs],
                'subtype': [], 'joins': []}
               for yid, typ, words, organs in (('Y1', 'surgically_absent', 'Total proctocolectomy', ['colon']),
                                               ('Y2', 'ileal_pouch', 'ileal pouch-anal anastomosis', []))]
    exam_status = next(w for w in ('was introduced', 'was inserted', 'was advanced') if w in findings)
    sess = session('X1', fact('flex_sig', src(['S5'], 'flexible sigmoidoscope')), examination=[fact('E1', src(['S5']))],
                   encounter=[fact('this_encounter', frame(['S2']))],
                   approach=[fact(approach[0], src(['S5'], approach[1]))] if approach else [],
                   reached=[fact(value, src(['S5'], words)) for value, words in reached])
    data = answer(
        sections=[opening(), labelled('N1', 'S4', 'History:', 'history'), labelled('N2', 'S5', 'Findings:', 'findings')],
        sessions=[sess], anatomy=entries,
        events=[event('E1', ['S5'], 'flexible sigmoidoscope', exam_status, 'examination',
                      session=[fact('X1', src(['S5']))]),
                event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                      target__places=[fact('pouch', src(['S6'], 'pouch body'))],
                      technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])])
    return text, data


SIG_HEAD = ('SYNTHETIC LOWER ENDOSCOPY REPORT\n'                   # S1
            'Date of service: 03/14/2031\n'                         # S2
            'Endoscopist: Corvin Ashdale, MD (fictional)\n'         # S3
            '\n')
DESC_BX = 'Two biopsies of the descending colon were taken with cold forceps.'


def stoma_flexsig():
    """t10_stoma_flexsig, word for word: a flexible sigmoidoscope passed through a colostomy after an abdominoperineal
    resection."""
    text = (SIG_HEAD + 'History: Abdominoperineal resection with an end colostomy in 2026.\n'
            'Findings: The flexible sigmoidoscope was introduced through the colostomy and advanced 40 cm into the '
            'descending colon.\n' + DESC_BX + '\n')
    data = answer(
        sections=[opening(), labelled('N1', 'S4', 'History:', 'history'), labelled('N2', 'S5', 'Findings:', 'findings')],
        sessions=[session('X1', fact('flex_sig', src(['S5'], 'flexible sigmoidoscope')),
                          examination=[fact('E1', src(['S5']))], encounter=[fact('this_encounter', frame(['S2']))],
                          approach=[fact('through_stoma', src(['S5'], 'through the colostomy'))],
                          through=[fact('Y1', src(['S5'], 'through the colostomy'))],
                          reached=[fact('descending_colon', src(['S5'], 'into the descending colon'))])],
        anatomy=[{'id': 'Y1', 'type': fact('stoma', src(['S4'], 'end colostomy')), 'organ': [], 'subtype': [],
                  'joins': []},
                 {'id': 'Y2', 'type': fact('surgically_absent', src(['S4'], 'Abdominoperineal resection')),
                  'organ': [fact('rectum', src(['S4'], 'Abdominoperineal resection'))], 'subtype': [], 'joins': []}],
        events=[event('E1', ['S5'], 'flexible sigmoidoscope', 'was introduced', 'examination',
                      session=[fact('X1', src(['S5']))]),
                event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                      target__places=[fact('descending_colon', src(['S6'], 'descending colon'))],
                      technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])])
    return text, data


SIG_CASES = {
    'f1-flexsig-scope-pouch-transanal': (pouch_flexsig(
        'The flexible sigmoidoscope was inserted per anus into the ileal pouch and advanced into the afferent limb.',
        ('transanal', 'inserted per anus'), [('neo_terminal_ileum', 'into the afferent limb')]),
        [('45331', POUCH_BX), ('45330', POUCH_BX)]),
    'f2-flexsig-scope-through-pouch': (pouch_flexsig(
        'The flexible sigmoidoscope was advanced through the ileal pouch into the afferent limb.',
        ('through_pouch', 'through the ileal pouch'), [('neo_terminal_ileum', 'into the afferent limb')]),
        [('45331', POUCH_BX), ('45330', POUCH_BX)]),
    's1-apr-colostomy-flexsig-through-stoma': (stoma_flexsig(), [('45331', DESC_BX)]),
}
# (case, code) -> the causes the code must be held by: L6C-1's and L6C-3's false READYs (int6 and int6 + rules4)
MUST_HOLD = {
    ('e1-ipaa-eus-through-pouch', '45391'): ROUTE, ('e2-ipaa-eus-transanal', '45391'): ROUTE,
    ('e3-ipaa-eus-fna', '45392'): ROUTE, ('e4-ira-eus', '45391'): ROUTE,
    ('e7-colostomy-eus-as-45391', '45391'): LOWER_RULE, ('e8-loop-ileo-eus-icv-fna', '45392'): LOWER_RULE,
    ('e9-colostomy-eus-cecum-fna', '45392'): LOWER_RULE,
    ('f1-flexsig-scope-pouch-transanal', '45331'): ROUTE, ('f1-flexsig-scope-pouch-transanal', '45330'): ROUTE,
    ('f2-flexsig-scope-through-pouch', '45331'): ROUTE, ('f2-flexsig-scope-through-pouch', '45330'): ROUTE,
    ('s1-apr-colostomy-flexsig-through-stoma', '45331'): ROUTE,
}
# (case, code) -> the status int6 gives, which must stand: the attacker's controls
AS_BEFORE = {
    ('e5-control-lower-eus-cecum', '45391'): (READY, ()),
    ('e6-stoma-twin-44406', '44406'): (HELD, (LOWER_RULE,)),
    ('e7-colostomy-eus-as-45391', '44406'): (READY, ()),
    ('e8-loop-ileo-eus-icv-fna', '44407'): (HELD, (LOWER_RULE,)),
    ('e9-colostomy-eus-cecum-fna', '44407'): (READY, ()),
    ('l1-rectal-eus-chole', '45341'): (READY, ()),
    ('l2-colonic-eus-chole', '45391'): (READY, ()),
}


class FindingTests(SimpleTestCase):
    def test_l6c_1_and_l6c_3_hold_every_lower_gi_code_their_inputs_proposed(self):
        # the must-change pins: READY on int6 (attack/L6-generality/out/t03-int6.out, t08, t09, t10) and on int6 +
        # rules4; held now - each by the route table's own hold (a pouch, a colon gone) or the class's explanation
        # (an approach established through a stoma: LOWER's own for an EUS code)
        for (name, code), cause in MUST_HOLD.items():
            (text, data), codes = {**EUS_CASES, **SIG_CASES}[name]
            quote = dict(codes)[code]
            with self.subTest(case=name, code=code):
                status, causes = statuses(text, data, (code, quote))[code]
                self.assertEqual(status, HELD)
                self.assertIn(cause, causes)

    def test_the_attackers_controls_stay_as_int6_decides_them(self):
        for (name, code), expected in AS_BEFORE.items():
            (text, data), codes = EUS_CASES[name]
            with self.subTest(case=name, code=code):
                self.assertEqual(statuses(text, data, (code, dict(codes)[code]))[code], expected)

    def test_no_question_is_served_to_a_code_the_table_holds(self):
        # the table's own hold is ABSENT to the planner (asking's census), the explanation B5 or BILLING: nothing is
        # asked of Fable for a held finding's code
        for (name, code), cause in MUST_HOLD.items():
            (text, data), _codes = {**EUS_CASES, **SIG_CASES}[name]
            with self.subTest(case=name, code=code):
                _claims, _out, R, view = R2CL.run(text, data, R2CL.FAITHFUL)
                self.assertEqual(serving(asking.plan(R, (), view), code), [])


# === completeness: every lower-GI code of the catalogue has a row =====================================================

# DECISIONS D328 (1)'s families as the ruling names them: (first, last) -> (route, the name of the anatomy it needs) -
# DECLARED. The needs are read as catalogue.RouteAnatomy's members only when a test runs (``families``), so this module
# imports on a tree without the table: on the RED run each test that reads the table fails by itself
FAMILIES = {
    (45378, 45398): (AP.TRANSANAL, 'COLON'),                  # colonoscopy, its EUS 45391 and 45392 included
    (45330, 45350): (AP.TRANSANAL, 'RECTUM_AND_SIGMOID'),     # sigmoidoscopy, its EUS 45341 and 45342 included
    (45300, 45327): (AP.TRANSANAL, 'RECTUM_AND_SIGMOID'),     # proctosigmoidoscopy
    (44388, 44408): (AP.THROUGH_STOMA, 'COLONIC_STOMA'),      # colonoscopy through a stoma, 44406 and 44407 included
    (44380, 44384): (AP.THROUGH_STOMA, 'ILEAL_STOMA'),        # ileoscopy through a stoma
    (44385, 44386): (AP.THROUGH_POUCH, 'POUCH'),              # the endoscopy of a pouch
}


def families() -> dict:
    return {span: (route, catalogue.RouteAnatomy[name]) for span, (route, name) in FAMILIES.items()}
# The catalogue's lower-GI endoscopy codes, DECLARED (the 2 + 13 + 12 + 13 + 2 + 4 + 2 + 2 of the families' profiles)
LOWER_GI = frozenset({
    45378, 45379, 45380, 45381, 45382, 45384, 45385, 45386, 45388, 45389, 45390, 45393, 45398, 45391, 45392,
    45330, 45331, 45332, 45333, 45334, 45335, 45337, 45338, 45340, 45346, 45347, 45349, 45350, 45341, 45342,
    44388, 44389, 44390, 44391, 44392, 44394, 44401, 44402, 44403, 44404, 44405, 44408, 44406, 44407,
    44380, 44381, 44382, 44384, 44385, 44386})


def by_principle() -> frozenset:
    """The lower-GI codes computed here from the catalogue's own tables, independently of catalogue.lower_gi: every
    profile of the colonoscopy or the sigmoidoscopy family, every lower-tract EUS code (eus_tract LOWER) and every
    enteroscopy code whose class passes through a stoma or a pouch."""
    return frozenset(code for code, profile in catalogue.CODES.items()
                     if profile.family in (SK.COLONOSCOPY, SK.FLEX_SIG)
                     or catalogue.eus_tract(str(code)) is ct.Tract.LOWER
                     or catalogue.code_class(str(code)) in (EC.STOMA, EC.POUCH))


class CompletenessTests(SimpleTestCase):
    def test_every_lower_gi_code_of_the_catalogue_has_a_declared_row(self):
        # THE COMPLETENESS TEST (D328 (1)): a lower-GI code the catalogue gains with no row fails here
        found = frozenset(code for code in catalogue.CODES if catalogue.lower_gi(str(code)))
        self.assertEqual(found, by_principle())
        self.assertEqual(found, LOWER_GI)
        self.assertEqual(sorted(code for code in found if catalogue.lower_route(str(code)) is None), [])
        for code in sorted(found):
            with self.subTest(code=code):
                row = catalogue.lower_route(str(code))
                self.assertEqual((row.route, row.needs),
                                 next(value for (first, last), value in families().items() if first <= code <= last))

    def test_the_table_is_the_rulings_families_exactly(self):
        self.assertEqual({(first, last): (row.route, row.needs) for first, last, row in catalogue.LOWER_ROUTE_RANGES},
                         families())
        expanded = {code: value for (first, last), value in families().items() for code in range(first, last + 1)}
        self.assertEqual({code: (row.route, row.needs) for code, row in catalogue.LOWER_ROUTES.items()}, expanded)
        spans = sorted(FAMILIES)
        self.assertTrue(all(one[1] < other[0] for one, other in zip(spans, spans[1:])))  # no two overlap
        self.assertEqual(set(catalogue.RouteAnatomy), {needs for _route, needs in families().values()})  # every need
        with self.assertRaises(TypeError):
            catalogue.LOWER_ROUTES[45380] = None  # type: ignore[index]

    def test_every_number_the_catalogue_routes_to_a_lower_gi_family_has_a_row(self):
        # the routing ranges of the colonoscopy and the sigmoidoscopy families (gi.profiles', carve-outs included), and
        # the proctosigmoidoscopy the ruling names (an OTHER_GI routing range, no profile: route (d) holds it first)
        numbers = {code for family in (SK.COLONOSCOPY, SK.FLEX_SIG)
                   for first, last in catalogue.CODE_RANGES[family] for code in range(first, last + 1)}
        self.assertIn((45300, 45327), catalogue.CODE_RANGES[SK.OTHER_GI])
        numbers |= set(range(45300, 45328))
        self.assertEqual(sorted(code for code in numbers if code not in catalogue.LOWER_ROUTES), [45399])
        # 45399 (the unlisted colon procedure, gi.profiles' _NOT_COLONOSCOPY) is no endoscopy: no row, never a profile
        self.assertNotIn(45399, catalogue.CODES)
        for code in range(45300, 45328):
            self.assertIsNone(catalogue.code_profile(str(code)))
            self.assertFalse(catalogue.lower_gi(str(code)))

    def test_no_row_names_a_code_outside_the_lower_gi(self):
        for code in catalogue.LOWER_ROUTES:
            with self.subTest(code=code):
                self.assertTrue(code not in catalogue.CODES or catalogue.lower_gi(str(code)))
        for code in catalogue.CODES:
            if not catalogue.lower_gi(str(code)):
                self.assertNotIn(code, catalogue.LOWER_ROUTES)

    def test_each_class_table_agrees_with_its_row(self):
        # D43's lower EUS classes and D108's enteroscopy classes, each its family's route and need
        for code, exam in catalogue.LOWER_EUS_CLASS.items():
            row = catalogue.lower_route(str(code))
            with self.subTest(code=code):
                self.assertEqual((row.route, row.needs.name), {
                    EUS.SIGMOIDOSCOPIC: (AP.TRANSANAL, 'RECTUM_AND_SIGMOID'), EUS.COLONOSCOPIC: (AP.TRANSANAL, 'COLON'),
                    EUS.STOMA: (AP.THROUGH_STOMA, 'COLONIC_STOMA')}[exam])
        for code in catalogue.CODES:
            found = catalogue.code_class(str(code))
            if found in (EC.STOMA, EC.POUCH):
                row = catalogue.lower_route(str(code))
                self.assertEqual(row.route, catalogue.ENTEROSCOPY_CLASS_APPROACH[found], code)
                self.assertEqual(row.needs.name, 'ILEAL_STOMA' if found is EC.STOMA else 'POUCH', code)
        self.assertEqual(evaluate.STOMA_ROUTE_CODES, {code for code in LOWER_GI if 44388 <= code <= 44408} - {44406, 44407})
        self.assertEqual(evaluate.ANUS_ROUTE_CODES, {code for code in LOWER_GI if 45378 <= code <= 45398} - {45391, 45392})

    def test_a_lower_gi_code_with_no_row_holds_at_run_time(self):
        # "a code with no row fails the test, and at run time it holds": each family's code, its row removed from the
        # table, in a scene its row leaves T, holds by the table's own hold (and lower_gi, never read from the table,
        # still names it)
        for code in (45380, 45391, 45392, 45331, 45330, 45341, 45342, 44389, 44382, 44380, 44386):
            # round r3's round 5 (D330 (1), lane rules6): the per-anus scene's entry another alteration OF THE STOMACH -
            # of no stated organ it matches no row of the ruled harmless set and the path guard would hold the code
            # before its row is removed
            R = scope(code, approach=sup(AP.TRANSANAL) if catalogue.lower_route(str(code)).route is AP.TRANSANAL
                      else sup(catalogue.lower_route(str(code)).route), through=sup(Y1),
                      entries={Y1: STOMA_ENTRY if code in (44389, 44382, 44380) else
                               POUCH_ENTRY if code == 44386 else entry_of(type=sup(AT.OTHER_ALTERATION),
                                                                          organ=sup(LM.STOMACH))},
                      reached=sup(EX.CECUM) if code == 44389 else None)
            with self.subTest(code=code):
                self.assertNotIn(ROUTE, [w[0] for w in witnesses(route_row(R, code))])
                table = MappingProxyType({key: row for key, row in catalogue.LOWER_ROUTES.items() if key != code})
                with mock.patch.object(catalogue, 'LOWER_ROUTES', table):
                    self.assertIsNone(catalogue.lower_route(str(code)))
                    self.assertTrue(catalogue.lower_gi(str(code)))
                    row = route_row(R, code)
                    self.assertIn((ROUTE, A.TYPE, X1, None), witnesses(row))
                    self.assertIsNot(row.truth, T)
                    self.assertIn(('procedure', ROUTE, A.TYPE, 'X1', 'question'), held_of(R, str(code)))
                    # the act's session open: the hold about the act, whatever the session
                    S = replace(R, events={**R.events, E2: {**R.events[E2], A.SESSION: (unres(X1, RR.GEOMETRY),)}})
                    self.assertIn((ROUTE, A.TYPE, E2, None), witnesses(route_row(S, code)))


# === per anus: every per-anus code x every entry state x every approach state =========================================

ENTRY_STATES, APPROACH_STATES = RD.ENTRY_STATES, RD.APPROACH_STATES
PER_ANUS = sorted(code for code in LOWER_GI if FAMILIES[next(span for span in FAMILIES
                                                             if span[0] <= code <= span[1])][0] is AP.TRANSANAL)


def needs_of(code) -> str:
    return next(needs for (first, last), (_route, needs) in FAMILIES.items() if first <= code <= last)


def explanation_rule(code) -> str:
    """The class's explanation of a per-anus code beside an approach established through a stoma: LOWER's own for a
    lower EUS code (its class), the route table's for the colonoscopy and the sigmoidoscopy families."""
    return LOWER_RULE if code in catalogue.LOWER_EUS_CLASS else ROUTE


class AnusCensusTests(SimpleTestCase):
    def test_the_per_anus_codes_are_the_four_families(self):
        self.assertEqual(len(PER_ANUS), 30)
        self.assertEqual({needs_of(code) for code in PER_ANUS}, {'COLON', 'RECTUM_AND_SIGMOID'})
        self.assertEqual({code for code in PER_ANUS if code in catalogue.LOWER_EUS_CLASS}, {45341, 45342, 45391, 45392})

    def test_the_census_every_per_anus_code_every_entry_state_every_approach(self):
        # the route row: F (the class's explanation) when the approach is supported through the stoma; else the
        # table's own hold exactly when an entry may be an ileal pouch or the approach may be through a pouch - or, for
        # the colonoscopy family (a colon to traverse), the entry may file the colon absent; else the approach's
        # question exactly when a stoma route is possible; else T (states DECLARED in test_r3d_rules)
        checked = 0
        for (e_name, (facts, absent, pouch, stoma)), (a_name, (approach, by_pouch, stoma_reading, closed)) in (
                itertools.product(ENTRY_STATES.items(), APPROACH_STATES.items())):
            for code in PER_ANUS:
                R = scope(code, approach=approach, entries={Y2: facts} if facts is not None else None)
                colon = needs_of(code) == 'COLON'
                with self.subTest(entry=e_name, approach=a_name, code=code):
                    row = route_row(R, code)
                    if a_name == 'through the stoma, supported':
                        self.assertIs(row.truth, Fa)
                        self.assertEqual([(h.attribute, h.kind.value, h.cause) for h in row.witnesses],
                                         [(A.APPROACH, 'explanation', explanation_rule(code))])
                    elif pouch or by_pouch or (colon and absent):
                        self.assertIs(row.truth, U)
                        self.assertEqual(witnesses(row), [(ROUTE, A.TYPE, X1, None)])
                    elif not closed and (stoma_reading or stoma):
                        self.assertIs(row.truth, U)
                        self.assertEqual([(h.attribute, h.kind.value) for h in row.witnesses],
                                         [(A.APPROACH, 'question')])
                    elif guarded(R, code):
                        # round r3's round 5 (D330 (1), lane rules6): after the arms, the path guard's table hold - an
                        # entry no row of the ruled harmless set holds (beside a rectum and sigmoid the colon filed
                        # absent as a whole too), or an approach filed as anything but per anus (moved by path_guard)
                        self.assertIs(row.truth, U)
                        self.assertEqual(witnesses(row), [(ROUTE, A.TYPE, X1, None)])
                    else:
                        self.assertIs(row.truth, T)
                checked += 1
        self.assertEqual(checked, len(ENTRY_STATES) * len(APPROACH_STATES) * len(PER_ANUS))

    def test_an_acts_open_session_reads_the_anatomy_alone(self):
        # D312 checker S3's principle: beside an entry that may be an ileal pouch - or, for the colonoscopy family, may
        # file the colon absent - no session the act may be in gives the route, so the table's hold about the act
        # stands whatever the session (a lower EUS code's row asks the session beside it); else the route is read once
        # the session is known
        for (e_name, (facts, absent, pouch, _stoma)), code in itertools.product(ENTRY_STATES.items(), PER_ANUS):
            R = scope(code, entries={Y2: facts} if facts is not None else None,
                      act_session=unres(X1, ct.Reason.GEOMETRY_SECTION))
            # round r3's round 5 (D330 (1), lane rules6): the path guard holds about the act too where an entry matches
            # no row of the ruled harmless set whatever the session (moved by evaluate.path_guard)
            held = pouch or (needs_of(code) == 'COLON' and absent) or guarded(R, code, None)
            with self.subTest(entry=e_name, code=code):
                found = witnesses(route_row(R, code))
                self.assertEqual((ROUTE, A.TYPE, E2, None) in found, held)
                if code in catalogue.LOWER_EUS_CLASS:  # LOWER asks the session as it did
                    self.assertIn(A.SESSION, [w[1] for w in found])
                elif not held:
                    self.assertEqual(found, [])

    def test_the_colonoscopy_family_is_read_exactly_as_before(self):
        # the colonoscopy codes' route rows are the rows the rounds before built (D310 (1), D312 (5), D325 (2)): the
        # same census test_r3d_rules runs, through the old name; the table only adds families beside them
        self.assertIs(evaluate._row_colon_route, evaluate._row_lower_route)
        for code in sorted(evaluate.ANUS_ROUTE_CODES):
            self.assertIs(label_of(code), Tag.COLFULL)
        for code in (45330, 45331, 44380, 44386):
            self.assertIs(label_of(code), RQ.Requirement.ROUTE_TABLE)
        for code in (45341, 45391, 44406):
            self.assertIs(label_of(code), Tag.LOWER)


# === the ileoscopy through a stoma needs an ileal stoma; the pouch codes =============================================

ILEAL_STOMA_CODES = sorted(code for code in LOWER_GI if 44380 <= code <= 44384)
# Each organ state of the stoma passed through: (its fact, whether it may be a colonic stoma by what is filed) - DECLARED
ORGAN_STATES = {
    'silent (pass 1 filed none)': (None, False),
    'the ileum, supported': (sup(LM.ILEUM), False),
    'the terminal ileum, claimed': (unres(LM.TERMINAL_ILEUM, UNAPPRAISED), False),
    'the small bowel, supported': (sup(LM.SMALL_BOWEL), False),
    'the jejunum, supported': (sup(LM.JEJUNUM), False),
    "the ileum claimed, a doubt's reading of the jejunum": (doubted(LM.ILEUM, LM.JEJUNUM), False),
    'the descending colon, supported (a colostomy)': (sup(LM.DESCENDING_COLON), True),
    'the sigmoid colon, claimed': (unres(LM.SIGMOID_COLON, UNAPPRAISED), True),
    'the colon, supported': (sup(LM.COLON), True),
    'the cecum, supported': (sup(LM.CECUM), True),
    "the ileum claimed, a doubt's reading of the transverse colon": (doubted(LM.ILEUM, LM.TRANSVERSE_COLON), True),
    "a contradiction's sides the ileum and the colon": (contra(LM.ILEUM, LM.COLON), True),
    'other, supported (no placeable organ)': (sup(LM.OTHER), True),
    'a stoma, supported (no placeable organ)': (sup(LM.STOMA), True),
    'established not the colon (hold-only)': (neg(LM.COLON), True),
    'an open denial of the colon': (open_denial(LM.COLON), True),
}
COLOSTOMY = entry_of(type=sup(AT.STOMA), organ=sup(LM.SIGMOID_COLON))
ILEOSTOMY = entry_of(type=sup(AT.STOMA), organ=sup(LM.ILEUM))


def ileoscopy(organ, *, through=sup(Y1), entries=None, approach=sup(AP.THROUGH_STOMA), act_session=None):
    """An ileoscopy through a stoma X1 (44380-44384's class) passing through Y1, a stoma whose organ is ``organ``."""
    return scope(44382, approach=approach, through=through, act_session=act_session,
                 entries={Y1: entry_of(type=sup(AT.STOMA), organ=organ), **(entries or {})})


class IlealStomaTests(SimpleTestCase):
    def test_the_census_every_code_every_organ_state(self):
        for (name, (organ, colonic)), code in itertools.product(ORGAN_STATES.items(), ILEAL_STOMA_CODES):
            with self.subTest(organ=name, code=code):
                R = ileoscopy(organ)
                self.assertEqual(evaluate.colonic_stoma_possible(R, X1), colonic)
                # round r3's round 5 (D330 (1), lane rules6, R5R-9): an organ FILED that may lie nowhere in the ileum
                # (the jejunum) is no ileal stoma either (moved by evaluate.ileal_stoma_contradicted)
                held = colonic or name == 'the jejunum, supported'
                self.assertEqual(evaluate.ileal_stoma_contradicted(R, X1), held)
                self.assertEqual(witnesses(route_row(R, code)), [(ROUTE, A.TYPE, X1, None)] if held else [])

    def test_only_the_stoma_passed_through_is_read_when_the_through_is_established(self):
        # an ileostomy passed through beside a colostomy (its mucous fistula, say) leaves the code as before; the
        # through not established reads every entry that may be a stoma - the colostomy may be the one passed
        R = ileoscopy(sup(LM.ILEUM), entries={Y2: COLOSTOMY})
        self.assertEqual(witnesses(route_row(R, 44382)), [])
        for name, through in {'silent': None, 'claimed': unres(Y1, UNAPPRAISED), 'naming the colostomy': sup(Y2),
                              "a contradiction's sides": contra(Y1, Y2)}.items():
            with self.subTest(through=name):
                R = ileoscopy(sup(LM.ILEUM), through=through, entries={Y2: COLOSTOMY})
                self.assertEqual(witnesses(route_row(R, 44382)), [(ROUTE, A.TYPE, X1, None)])
        # an entry that cannot be a stoma is never read (a surgically absent colon beside an ileostomy: an end
        # ileostomy after a proctocolectomy) - nor is one the through names (the enteroscopy class's route part holds
        # a code whose through names no stoma: engine/classes)
        R = ileoscopy(None, through=None, entries={Y2: ABSENT_COLON})
        self.assertEqual(witnesses(route_row(R, 44382)), [])
        R = ileoscopy(sup(LM.ILEUM), through=sup(Y2), entries={Y2: ABSENT_COLON})
        self.assertEqual(witnesses(route_row(R, 44382)), [])
        self.assertEqual(evaluate._stomas_passed(R, X1), ())

    def test_the_acts_open_session_reads_every_stoma(self):
        R = ileoscopy(sup(LM.ILEUM), entries={Y2: COLOSTOMY}, act_session=unres(X1, ct.Reason.GEOMETRY_SECTION))
        self.assertEqual(witnesses(route_row(R, 44382)), [(ROUTE, A.TYPE, E2, None)])
        R = ileoscopy(sup(LM.ILEUM), act_session=unres(X1, ct.Reason.GEOMETRY_SECTION))
        self.assertEqual(witnesses(route_row(R, 44382)), [])

    def test_the_hold_reaches_the_coder_and_the_ordinary_ileoscopy_stays_ready(self):
        # end to end over the assembled engine (test_assess.run): an ileoscopy through an end ileostomy, its organ
        # silent or the ileum, READY as int6 decides it; through a colostomy, held by the table's own hold, nothing asked
        for name, organ in (('silent', None), ('the ileum', sup(LM.ILEUM))):
            with self.subTest(organ=name):
                (found,) = TA.run(ileoscopy(organ), ('44382', 2)).codes
                self.assertEqual(found.status.value, READY)
        R = ileoscopy(sup(LM.DESCENDING_COLON))
        (found,) = TA.run(R, ('44382', 2)).codes
        self.assertEqual(found.status.value, HELD)
        self.assertIn(ROUTE, [held.cause for held in found.held_facts])
        self.assertEqual(serving(asking.plan(R, ()), '44382'), [])


class PouchTests(SimpleTestCase):
    def test_the_pouch_codes_route_is_the_enteroscopy_classs_own(self):
        # 44385 and 44386 through a pouch: the class's route establishes the pouch (an entry passed through established
        # an ileal pouch: engine/classes), so the table's row adds nothing whatever the anatomy - as int6 decides them
        for (e_name, (facts, *_flags)), code in itertools.product(ENTRY_STATES.items(), (44385, 44386)):
            R = scope(code, approach=sup(AP.THROUGH_POUCH), through=sup(Y1),
                      entries={Y1: POUCH_ENTRY, **({Y2: facts} if facts is not None else {})})
            with self.subTest(entry=e_name, code=code):
                # round r3's round 5 (D330 (1), lane rules6): beside the pouch the route uses, an entry that matches no
                # row of the pouch family's ruled harmless set holds (a second pouch, an anastomosis that keeps a colon,
                # an entry of no readable type or organ: moved by evaluate.path_guard)
                self.assertIs(route_row(R, code).truth, U if guarded(R, code) else T)
        for approach in (sup(AP.THROUGH_POUCH), sup(AP.TRANSANAL)):  # D219: a pouchoscopy per anus
            R = scope(44386, approach=approach, through=sup(Y1), entries={Y1: POUCH_ENTRY})
            (found,) = TA.run(R, ('44386', 2)).codes
            self.assertEqual(found.status.value, READY, approach)


# === the D328 addendum: rules4's questions ===========================================================================

# Each place a member of an anastomosis's joins may name -> (in the small bowel, below the colon) - DECLARED from the
# ruling's words ("may join the ileum to the rectum or the anus"); a landmark naming no placeable organ may be either
JOIN_PLACES = {
    LM.ILEUM: (True, False), LM.TERMINAL_ILEUM: (True, False), LM.NEO_TERMINAL_ILEUM: (True, False),
    LM.SMALL_BOWEL: (True, False), LM.JEJUNUM: (True, False),
    LM.RECTUM: (False, True), LM.ANAL_CANAL: (False, True),
    LM.COLON: (False, False), LM.SIGMOID_COLON: (False, False), LM.TRANSVERSE_COLON: (False, False),
    LM.RECTOSIGMOID: (False, False), LM.RIGHT_COLON: (False, False), LM.CECUM: (False, False),
    LM.STOMACH: (False, False), LM.DUODENUM: (False, False),
    LM.POUCH: (True, True), LM.OTHER: (True, True), LM.ANASTOMOSIS: (True, True),
}


def member_states():
    """Each state of one joins member: (label, its fact, (may be in the small bowel, may be below the colon))."""
    for place, (small, below) in JOIN_PLACES.items():
        yield f'{place.value} supported', sup(place), (small, below)
        yield f'{place.value} claimed', unres(place, UNAPPRAISED), (small, below)
        side_small, side_below = JOIN_PLACES[LM.COLON]
        yield f'{place.value} or the colon', contra(place, LM.COLON), (small or side_small, below or side_below)
    yield 'the colon established denied (hold-only)', neg(LM.COLON), (True, True)
    yield 'an open denial of the ileum', open_denial(LM.ILEUM), (True, True)


def anastomosis(*joins, subtype=None):
    return entry_of(type=sup(AT.ANASTOMOSIS), subtype=subtype, joins=joins)


class AddendumTests(SimpleTestCase):
    # --- Q1: LOWER declares the anatomy subtype read (P-INDEP) ---
    def test_q1_lower_reads_every_entrys_subtype_and_joins_to_hold_only(self):
        reads = {(read.role, read.attribute): read.paths for read in RQ.RULES[Tag.LOWER].reads}
        self.assertEqual(reads[(RQ.Role.ANATOMY, A.SUBTYPE)], {RQ.Path.HOLD})
        self.assertEqual(reads[(RQ.Role.ANATOMY, A.JOINS)], {RQ.Path.HOLD})
        colfull = {(read.role, read.attribute): read.paths for read in RQ.RULES[Tag.COLFULL].reads}
        self.assertEqual(colfull[(RQ.Role.ANATOMY, A.JOINS)], {RQ.Path.HOLD})
        self.assertEqual(colfull[(RQ.Role.ANATOMY, A.SUBTYPE)], {RQ.Path.READY})  # COLFULL's ileocolic anastomosis
        for code in ('45341', '45342', '45391', '45392', '44406', '44407'):
            self.assertEqual(RQ.dependencies(code).reads[RQ.Role.ANATOMY], {A.ORGAN, A.SUBTYPE, A.TYPE, A.JOINS}, code)

    def test_q1_an_eus_subtype_or_joins_outside_the_closure_never_moves_it(self):
        # the residual the read closes: 44406 beside an anastomosis whose subtype or joins may join the ileum below the
        # colon is held (LOWER's class route hold) - so a perturbation of the subtype moves the code, and the closure
        # must hold it
        base = RD.eus_stoma(sup(EX.CECUM), organ=sup(LM.ILEUM))
        self.assertEqual(held_of(base, '44406'), [])
        for name, entry in {'the subtype ileorectal': anastomosis(subtype=sup(SUB.ILEORECTAL)),
                            'the joins the ileum and the rectum': anastomosis(sup(LM.ILEUM), sup(LM.RECTUM))}.items():
            with self.subTest(case=name):
                self.assertEqual(held_of(RD.eus_stoma(sup(EX.CECUM), organ=sup(LM.ILEUM), entries={Y2: entry}),
                                         '44406'), RD.LOWER_HOLD)

    # --- Q2: both sides of the colon possibly absent cover the transverse too ---
    def test_q2_both_sides_cover_the_colon(self):
        held = {
            'the right and the left colon': RD_absences(LM.RIGHT_COLON, LM.LEFT_COLON),
            'four segments, the transverse colon kept': RD_absences(LM.CECUM, LM.ASCENDING_COLON, LM.DESCENDING_COLON,
                                                                   LM.SIGMOID_COLON),
            'the right colon, the descending and the sigmoid colon': RD_absences(LM.RIGHT_COLON, LM.DESCENDING_COLON,
                                                                                 LM.SIGMOID_COLON),
            'the cecum, the ascending and the left colon': RD_absences(LM.CECUM, LM.ASCENDING_COLON, LM.LEFT_COLON),
            'the right colon and the distal colon': RD_absences(LM.RIGHT_COLON, LM.DISTAL_COLON),
            'the right colon and the left colon claimed': RD_absences(unres(LM.RIGHT_COLON, UNAPPRAISED),
                                                                      unres(LM.LEFT_COLON, UNAPPRAISED)),
            "the right colon, and the left colon a contradiction's side": RD_absences(
                LM.RIGHT_COLON, contra(LM.HEPATIC_FLEXURE, LM.LEFT_COLON)),
        }
        kept = {
            'the right colon alone': RD_absences(LM.RIGHT_COLON),
            'the left colon alone': RD_absences(LM.LEFT_COLON),
            'the right colon and the sigmoid colon (the descending kept)': RD_absences(LM.RIGHT_COLON,
                                                                                      LM.SIGMOID_COLON),
            'the proximal colon and the sigmoid colon': RD_absences(LM.PROXIMAL_COLON, LM.SIGMOID_COLON),
            'four segments, the sigmoid colon kept': RD_absences(LM.CECUM, LM.ASCENDING_COLON, LM.TRANSVERSE_COLON,
                                                                LM.DESCENDING_COLON),
            'four segments, the cecum kept': RD_absences(LM.ASCENDING_COLON, LM.TRANSVERSE_COLON, LM.DESCENDING_COLON,
                                                        LM.SIGMOID_COLON),
            "either side (one entry's two sides) beside the transverse": RD_absences(
                contra(LM.RIGHT_COLON, LM.LEFT_COLON), LM.TRANSVERSE_COLON),
        }
        for name, entries in {**held, **kept}.items():
            with self.subTest(case=name):
                R = RD.anus_scope(approach=sup(AP.TRANSANAL), entries=entries)
                expected = name in held
                self.assertEqual(evaluate.segments_absent_possible(R), expected)
                self.assertEqual(held_of(R, '45380'), RD.TABLE_HOLD if expected else [])
                S = RR.stoma_scope(reached=(sup(EX.CECUM),), organ=sup(LM.ILEUM), entries=entries)
                self.assertEqual(evaluate.colonic_route(S, X1), not expected)
                self.assertEqual(held_of(RD.eus_stoma(sup(EX.CECUM), organ=sup(LM.ILEUM), entries=entries), '44406'),
                                 RD.LOWER_HOLD if expected else [])

    # --- Q3: an anastomosis's joins are read as well as its subtype ---
    def test_q3_the_census_one_member_and_every_pair_of_members(self):
        states = list(member_states())
        checked = held = 0
        for label, member, (small, below) in states:  # one member: its other end not filed - it may be either
            R = RD.anus_scope(approach=sup(AP.TRANSANAL), entries={Y2: anastomosis(member)})
            # round r3's round 5 (DECISIONS D330 (1) (c), lane rules6, R5R-4): a list of one member names one organ (the
            # anastomosis of that organ to itself), so it holds only where the member may lie below the colon (the
            # rectum, the anal canal, no placed organ); and the path guard holds a member no row of the ruled harmless
            # set names (a landmark naming no placed organ, an established or open denial: moved by path_guard)
            expected = below
            with self.subTest(joins=[label]):
                self.assertEqual(evaluate.joins_ileum_below_colon_possible(R, Y2), expected)
                self.assertEqual(evaluate.whole_colon_absent_possible(R), expected)
                self.assertIs(route_row(R, 45380).truth, U if expected or guarded(R, 45380) else T)
            checked += 1
            held += expected
        for (l1, m1, (s1, b1)), (l2, m2, (s2, b2)) in itertools.product(states, repeat=2):
            R = RD.anus_scope(approach=sup(AP.TRANSANAL), entries={Y2: anastomosis(m1, m2)})
            expected = (s1 and b2) or (s2 and b1)
            with self.subTest(joins=[l1, l2]):
                self.assertEqual(evaluate.joins_ileum_below_colon_possible(R, Y2), expected)
                # round r3's round 5 (D330 (1), lane rules6): the path guard's table hold beside (moved by path_guard)
                self.assertEqual(witnesses(route_row(R, 45380)), [(ROUTE, A.TYPE, X1, None)]
                                 if expected or guarded(R, 45380) else [])
            checked += 1
            held += expected
        self.assertEqual(checked, len(states) + len(states) ** 2)
        self.assertTrue(0 < held < checked)

    def test_q3_the_subtype_or_the_joins_holds_and_only_both_silent_stays_as_int6(self):
        holds = {
            'the joins the ileum and the rectum, the subtype silent': anastomosis(sup(LM.ILEUM), sup(LM.RECTUM)),
            'the joins the pouch and the anal canal (an IPAA)': anastomosis(sup(LM.POUCH), sup(LM.ANAL_CANAL)),
            'the joins the rectum alone, the subtype silent': anastomosis(sup(LM.RECTUM)),
            'the subtype colorectal, the joins the ileum and the rectum (OR)': anastomosis(
                sup(LM.ILEUM), sup(LM.RECTUM), subtype=sup(SUB.COLORECTAL)),
            'the subtype ileorectal, the joins the ileum and the colon (OR)': anastomosis(
                sup(LM.ILEUM), sup(LM.COLON), subtype=sup(SUB.ILEORECTAL)),
            'the joins the jejunum and the rectum': anastomosis(sup(LM.JEJUNUM), sup(LM.RECTUM)),
        }
        as_before = {
            'the subtype and the joins both silent (the recorded residual)': anastomosis(),
            'the joins the ileum and the colon (the development set filing)': anastomosis(
                sup(LM.ILEUM), sup(LM.COLON), subtype=sup(SUB.ILEOCOLIC)),
            'the joins the ileum and the colon, the subtype silent': anastomosis(sup(LM.ILEUM), sup(LM.COLON)),
            'the joins the sigmoid colon and the rectum (a colorectal anastomosis)': anastomosis(
                sup(LM.SIGMOID_COLON), sup(LM.RECTUM), subtype=sup(SUB.COLORECTAL)),
            'the joins the colon and the anal canal (a coloanal anastomosis)': anastomosis(sup(LM.COLON),
                                                                                           sup(LM.ANAL_CANAL)),
            'the joins the transverse colon alone': anastomosis(sup(LM.TRANSVERSE_COLON)),
            'the joins the stomach and the jejunum (an upper anastomosis)': anastomosis(sup(LM.STOMACH),
                                                                                       sup(LM.JEJUNUM)),
            'the joins the pouch and the colon (one end each way: never the same member twice)': anastomosis(
                sup(LM.POUCH), sup(LM.COLON)),
            # round r3's round 5 (DECISIONS D330 (1) (c), lane rules6, R5R-4): moved here from ``holds`` - one member
            # names one organ, and the ileum alone is no ileum joined below the colon
            'the joins the ileum alone': anastomosis(sup(LM.ILEUM)),
        }
        # round r3's round 5 (D330 (1), lane rules6): after the arms, the path guard holds an anastomosis no row of the
        # ruled harmless set holds - its subtype and joins both silent (the D328 addendum's residual, closed), or a joins
        # member naming no placed organ beside a silent subtype (moved by evaluate.path_guard)
        for name, entry in {**holds, **as_before}.items():
            expected = name in holds
            for code, R in (('45380', RD.anus_scope(approach=sup(AP.TRANSANAL), entries={Y2: entry})),
                            ('44389', RR.stoma_scope(reached=(sup(EX.CECUM),), organ=sup(LM.ILEUM),
                                                     entries={Y2: entry})),
                            ('44406', RD.eus_stoma(sup(EX.CECUM), organ=sup(LM.ILEUM), entries={Y2: entry})),
                            ('45391', scope(45391, approach=sup(AP.TRANSANAL), entries={Y2: entry}))):
                with self.subTest(case=name, code=code):
                    self.assertEqual(evaluate.whole_colon_absent_possible(R), expected)
                    guard = guarded(R, code)
                    self.assertEqual(guard, name in ('the subtype and the joins both silent (the recorded residual)',
                                                     'the joins the pouch and the colon (one end each way: never the '
                                                     'same member twice)') or expected)
                    if code == '44406':
                        self.assertEqual(held_of(R, code), RD.LOWER_HOLD if expected else TABLE_HOLD if guard else [])
                    else:
                        self.assertEqual((ROUTE, A.TYPE, X1, None) in witnesses(route_row(R, int(code))),
                                         expected or guard)

    def test_q3_the_sigmoidoscopy_family_reads_no_colon_arm(self):
        # a rectum and sigmoid needs no colon (D328 (1): the colon arm is the colonoscopy family's): beside an IRA or an
        # IPAA filed as an anastomosis (no pouch entry), no arm of the sigmoidoscopy and its EUS codes holds - but round
        # r3's round 5 (DECISIONS D330 (1), lane rules6): the path guard's ruled harmless set holds neither the colon
        # filed absent as a whole nor an ileum joined below the colon beside a rectum and sigmoid (what closes rules5's
        # Q5, the proctocolectomy), so each is held with the table's own hold (moved by evaluate.path_guard)
        for code in (45330, 45331, 45341, 45342):
            for name, entry in {'an IRA': anastomosis(sup(LM.ILEUM), sup(LM.RECTUM), subtype=sup(SUB.ILEORECTAL)),
                                'the colon absent': ABSENT_COLON}.items():
                with self.subTest(code=code, case=name):
                    R = scope(code, approach=sup(AP.TRANSANAL), entries={Y2: entry})
                    self.assertFalse(evaluate._anatomy_contradicts(catalogue.RouteAnatomy.RECTUM_AND_SIGMOID, R, X1))
                    self.assertTrue(guarded(R, code))
                    self.assertEqual(witnesses(route_row(R, code)), [(ROUTE, A.TYPE, X1, None)])


def RD_absences(*organs):
    """Anatomy entries Y3.. each filed surgically absent (supported) at one of ``organs`` (a Landmark or a Fact)."""
    return {Id.parse(f'Y{index}'): entry_of(type=sup(AT.SURGICALLY_ABSENT),
                                            organ=organ if isinstance(organ, EF.Fact) else sup(organ))
            for index, organ in enumerate(organs, start=3)}


# === constructed variants per family (FactSets), each as the rule says ================================================

def decided(R, code) -> list:
    return held_of(R, str(code))


COLONIC_EUS = {  # 45391 and 45392 per anus: a colon to traverse
    'a1 the colon filed absent as a whole, the approach per anus': (dict(approach=sup(AP.TRANSANAL),
                                                                         entries={Y2: ABSENT_COLON}), 'hold'),
    'a2 an ileal pouch claimed (unresolved), per anus': (dict(approach=sup(AP.TRANSANAL), entries={
        Y2: entry_of(type=unres(AT.ILEAL_POUCH, UNAPPRAISED))}), 'hold'),
    'a3 the approach claimed through a pouch, no entry': (dict(approach=unres(AP.THROUGH_POUCH, UNAPPRAISED)), 'hold'),
    'a4 the approach supported through a stoma (a colostomy)': (dict(approach=sup(AP.THROUGH_STOMA),
                                                                     entries={Y1: COLOSTOMY}), 'explained'),
    'a5 the approach silent beside an end colostomy': (dict(entries={Y1: COLOSTOMY}), 'asked'),
    'a6 the joins of an anastomosis the ileum and the rectum': (dict(approach=sup(AP.TRANSANAL), entries={
        Y2: anastomosis(sup(LM.ILEUM), sup(LM.RECTUM))}), 'hold'),
    'a7 the right and the left colon filed absent': (dict(approach=sup(AP.TRANSANAL),
                                                          entries=RD_absences(LM.RIGHT_COLON, LM.LEFT_COLON)), 'hold'),
    'a8 an ordinary EUS per anus to the cecum (no anatomy)': (dict(approach=sup(AP.TRANSANAL)), 'ready'),
    'a9 a right hemicolectomy (the right colon, an ileocolic anastomosis joining the ileum to the colon)': (dict(
        approach=sup(AP.TRANSANAL), entries={**RD_absences(LM.RIGHT_COLON), Y2: anastomosis(
            sup(LM.ILEUM), sup(LM.COLON), subtype=sup(SUB.ILEOCOLIC))}), 'ready'),
    'a10 per anus beside a Hartmann colostomy (the approach established)': (dict(
        approach=sup(AP.TRANSANAL), entries={Y1: COLOSTOMY, **RD_absences(LM.SIGMOID_COLON)}), 'ready'),
}
RECTAL_EUS = {  # 45341 and 45342 per anus: a rectum and sigmoid
    'b1 an ileal pouch (an IPAA), per anus': (dict(approach=sup(AP.TRANSANAL), entries={Y2: POUCH_ENTRY}), 'hold'),
    'b2 the approach supported through a pouch': (dict(approach=sup(AP.THROUGH_POUCH)), 'hold'),
    'b3 the approach supported through a stoma': (dict(approach=sup(AP.THROUGH_STOMA), entries={Y1: COLOSTOMY}),
                                                  'explained'),
    'b4 the approach silent beside a diverting loop ileostomy': (dict(entries={Y1: ILEOSTOMY}), 'asked'),
    'b5 after a low anterior resection (the sigmoid absent, a colorectal anastomosis)': (dict(
        approach=sup(AP.TRANSANAL), entries={**RD_absences(LM.SIGMOID_COLON), Y2: anastomosis(
            sup(LM.DESCENDING_COLON), sup(LM.RECTUM), subtype=sup(SUB.COLORECTAL))}), 'ready'),
    # round r3's round 5 (D330 (1), lane rules6): was 'ready' - the path guard holds the colon gone beside a rectum and
    # sigmoid (moved by evaluate.path_guard)
    'b6 after a total abdominal colectomy with an IRA (the rectal stump)': (dict(
        approach=sup(AP.TRANSANAL), entries={Y1: ABSENT_COLON, Y2: anastomosis(
            sup(LM.ILEUM), sup(LM.RECTUM), subtype=sup(SUB.ILEORECTAL))}), 'hold'),
    'b7 per anus beside an end colostomy (the approach established)': (dict(approach=sup(AP.TRANSANAL),
                                                                          entries={Y1: COLOSTOMY}), 'ready'),
    'b8 an ordinary rectal EUS (no anatomy, the approach silent)': (dict(), 'ready'),
}
SIGMOIDOSCOPY = {  # 45330-45350 per anus: a rectum and sigmoid
    'c1 an ileal pouch claimed, per anus': (dict(approach=sup(AP.TRANSANAL), entries={
        Y2: entry_of(type=unres(AT.ILEAL_POUCH, UNAPPRAISED))}), 'hold'),
    "c2 a contradiction's side a pouch approach": (dict(approach=contra(AP.TRANSANAL, AP.THROUGH_POUCH)), 'hold'),
    'c3 through an end colostomy after an APR (the approach supported)': (dict(
        approach=sup(AP.THROUGH_STOMA), through=sup(Y1), entries={Y1: COLOSTOMY, **RD_absences(LM.RECTUM)}),
        'explained'),
    'c4 the approach silent beside a diverting loop ileostomy after an LAR': (dict(
        entries={Y1: ILEOSTOMY, **RD_absences(LM.SIGMOID_COLON)}), 'asked'),
    'c5 the approach claimed per anus (unresolved) beside a colostomy': (dict(
        approach=unres(AP.TRANSANAL, UNAPPRAISED), entries={Y1: COLOSTOMY}), 'asked'),
    'c6 per anus after an LAR with a loop ileostomy (the approach established)': (dict(
        approach=sup(AP.TRANSANAL), entries={Y1: ILEOSTOMY, **RD_absences(LM.SIGMOID_COLON)}), 'ready'),
    # round r3's round 5 (D330 (1), lane rules6): was 'ready' - the path guard (moved by evaluate.path_guard)
    'c7 per anus after a total abdominal colectomy with an IRA': (dict(
        approach=sup(AP.TRANSANAL), entries={Y1: ABSENT_COLON, Y2: anastomosis(
            sup(LM.ILEUM), sup(LM.RECTUM), subtype=sup(SUB.ILEORECTAL))}), 'hold'),
    'c8 per anus after an LAR (the rectum filed partly absent: no rectum-absent arm)': (dict(
        approach=sup(AP.TRANSANAL), entries=RD_absences(LM.SIGMOID_COLON, LM.RECTUM)), 'ready'),
    'c9 an ordinary sigmoidoscopy (no anatomy, the approach silent)': (dict(), 'ready'),
    'c10 a gastrostomy beside it (no lower-tract stoma)': (dict(entries={Y1: entry_of(
        type=sup(AT.STOMA), organ=sup(LM.STOMACH))}), 'ready'),
}
ILEOSCOPY = {  # 44380-44384 through a stoma: an ileal stoma
    'd1 through an end ileostomy, its organ silent': (dict(organ=None), 'ready'),
    'd2 through an end ileostomy, its organ the ileum': (dict(organ=sup(LM.ILEUM)), 'ready'),
    'd3 through a stoma filed in the descending colon (a colostomy)': (dict(organ=sup(LM.DESCENDING_COLON)), 'hold'),
    'd4 through a stoma whose organ is claimed in the transverse colon': (dict(
        organ=unres(LM.TRANSVERSE_COLON, UNAPPRAISED)), 'hold'),
    'd5 the through silent beside an ileostomy and a mucous fistula': (dict(organ=sup(LM.ILEUM), through=None,
                                                                         entries={Y2: COLOSTOMY}), 'hold'),
    'd6 through the ileostomy (established) beside a mucous fistula': (dict(organ=sup(LM.ILEUM),
                                                                         entries={Y2: COLOSTOMY}), 'ready'),
    "d7 a contradiction's sides the ileum and the colon": (dict(organ=contra(LM.ILEUM, LM.COLON)), 'hold'),
    'd8 through an end ileostomy after a proctocolectomy (the colon absent)': (dict(organ=None,
                                                                                  entries={Y2: ABSENT_COLON}), 'ready'),
}
STATES = {'hold': [('procedure', ROUTE, A.TYPE, 'X1', 'question')]}


def explained(code) -> list:
    return [('procedure', explanation_rule(code), A.APPROACH, 'X1', 'explanation')]


class VariantTests(SimpleTestCase):
    def check(self, family, codes, build):
        for (name, (kwargs, expected)), code in itertools.product(family.items(), codes):
            R = build(code, **kwargs)
            with self.subTest(case=name, code=code):
                held = decided(R, code)
                if expected == 'ready':
                    self.assertEqual(held, [])
                elif expected == 'hold':
                    self.assertEqual(held, STATES['hold'])
                elif expected == 'explained':
                    self.assertEqual(held, explained(code))
                else:  # the approach's question (its reading's cause)
                    self.assertEqual([(h[0], h[2], h[4]) for h in held], [('procedure', A.APPROACH, 'question')])
        self.assertGreaterEqual(len(family), 6)
        for status in ('ready',):
            self.assertIn(status, {expected for _kwargs, expected in family.values()})

    def test_the_colonic_eus_codes_per_anus(self):
        self.check(COLONIC_EUS, (45391, 45392), lambda code, **kw: scope(code, exam_places=True, **kw))

    def test_the_rectal_eus_codes_per_anus(self):
        self.check(RECTAL_EUS, (45341, 45342), lambda code, **kw: scope(code, exam_places=True, **kw))

    def test_the_sigmoidoscopy_family(self):
        self.check(SIGMOIDOSCOPY, (45330, 45331), scope)

    def test_the_ileoscopy_through_a_stoma(self):
        def build(code, organ=None, through=sup(Y1), entries=None):
            return scope(code, approach=sup(AP.THROUGH_STOMA), through=through,
                         entries={Y1: entry_of(type=sup(AT.STOMA), organ=organ), **(entries or {})})
        self.check(ILEOSCOPY, (44380, 44382), build)

    def test_the_variants_end_to_end_over_the_assembled_engine(self):
        # one code of each family through test_assess.run: READY where the rule leaves it, held otherwise
        scenes = [('45392', 2, COLONIC_EUS, lambda **kw: scope(45392, exam_places=True, **kw)),
                  ('45342', 2, RECTAL_EUS, lambda **kw: scope(45342, exam_places=True, **kw)),
                  ('45331', 2, SIGMOIDOSCOPY, lambda **kw: scope(45331, **kw))]
        for code, number, family, build in scenes:
            for name, (kwargs, expected) in family.items():
                with self.subTest(case=name, code=code):
                    (found,) = TA.run(build(**kwargs), (code, number)).codes
                    self.assertEqual(found.status.value, READY if expected == 'ready' else HELD)


# === the common inputs D328 (1) names: exactly as int6 decides them ==================================================

HEAD = RR.HEAD
LAR = 'Low anterior resection with a colorectal anastomosis in 2026.'
F_LAR = 'The flexible sigmoidoscope was inserted per anus and advanced across the colorectal anastomosis to 30 cm.'
SIG_BX = 'Two biopsies of the anastomosis were taken with cold forceps.'
F_SIG = 'The flexible sigmoidoscope was inserted per anus and advanced to the sigmoid colon.'
SIGMOID_BX = 'Two biopsies of the sigmoid colon were taken with cold forceps.'


def sig_note(history, findings, act, *, anatomy, reached, place, place_words):
    """A sigmoidoscopy per anus: X1 flex_sig (approach per anus), its examination E1 and a cold-forceps biopsy E2."""
    text = HEAD + f'History: {history}\n' + f'Findings: {findings}\n' + act + '\n'
    entries = [{'id': yid, 'type': fact(typ, src(['S4'], words)),
                'organ': [fact(organ, src(['S4'], words))] if organ else [],
                'subtype': [fact(subtype, src(['S4'], words))] if subtype else [],
                'joins': [fact(value, src(['S4'], words)) for value in joins]}
               for yid, typ, words, organ, subtype, joins in anatomy]
    sess = session('X1', fact('flex_sig', src(['S5'], 'flexible sigmoidoscope')), examination=[fact('E1', src(['S5']))],
                   encounter=[fact('this_encounter', frame(['S2']))],
                   approach=[fact('transanal', src(['S5'], 'inserted per anus'))],
                   reached=[fact(value, src(['S5'], words)) for value, words in reached])
    data = answer(
        sections=[opening(), labelled('N1', 'S4', 'History:', 'history'), labelled('N2', 'S5', 'Findings:', 'findings')],
        sessions=[sess], anatomy=entries,
        events=[event('E1', ['S5'], 'flexible sigmoidoscope', 'was inserted', 'examination',
                      session=[fact('X1', src(['S5']))]),
                event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                      target__places=[fact(place, src(['S6'], place_words))],
                      technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])])
    return text, data


R3E = None


def r3e():
    global R3E
    if R3E is None:
        from tests.v2 import test_r3e_rules
        R3E = test_r3e_rules
    return R3E


class CommonInputTests(SimpleTestCase):
    def test_the_common_inputs_stay_as_int6_decides_them(self):
        E = r3e()
        cases = {
            'an ordinary colonoscopy per anus to the cecum': E.AS_BEFORE['g8 an ordinary colonoscopy to the cecum'],
            'an ordinary colonoscopy per anus to the terminal ileum':
                E.AS_BEFORE['g8b an ordinary colonoscopy to the terminal ileum'],
            'a colonoscopy through an established colostomy reaching the colon':
                E.AS_BEFORE['g9 a through-stoma colonoscopy, the colostomy to the cecum (the attacker control b)'],
            'a colonoscopy through a Hartmann colostomy to the cecum':
                E.AS_BEFORE['g9b a through-stoma colonoscopy after a Hartmann procedure, to the cecum'],
            'a right hemicolectomy reaching the neo-terminal ileum, the subtype filed':
                E.AS_BEFORE['g7 a right hemicolectomy to the neo-terminal ileum, the subtype filed'],
            'a right hemicolectomy reaching the neo-terminal ileum, the subtype not filed':
                E.AS_BEFORE['g7b a right hemicolectomy to the neo-terminal ileum, the subtype not filed (the verifier '
                            'c2)'],
            'a sigmoidoscopy per anus': (*sig_note('Screening; no prior surgery.', F_SIG, SIGMOID_BX, anatomy=[],
                                                   reached=[('sigmoid_colon', 'advanced to the sigmoid colon')],
                                                   place='sigmoid_colon', place_words='sigmoid colon'),
                                         ('45331', SIGMOID_BX)),
            'a sigmoidoscopy per anus after a low anterior resection': (*sig_note(
                LAR, F_LAR, SIG_BX,
                anatomy=[('Y1', 'surgically_absent', 'Low anterior resection', 'sigmoid_colon', None, []),
                         ('Y2', 'anastomosis', 'colorectal anastomosis', None, 'colorectal', ['colon', 'rectum'])],
                reached=[('stated_depth', 'to 30 cm')], place='anastomosis', place_words='anastomosis'),
                ('45331', SIG_BX)),
        }
        for name, (text, data, (code, quote)) in cases.items():
            with self.subTest(case=name):
                # round r3's round 5 (D330 (1), lane rules6): the right hemicolectomy whose anastomosis files neither its
                # subtype nor its joins is the D328 addendum's residual, which the path guard holds (the table's hold);
                # filed as the development set files it (below) it stays READY
                held = name == 'a right hemicolectomy reaching the neo-terminal ileum, the subtype not filed'
                self.assertEqual(statuses(text, data, (code, quote))[code], (HELD, (ROUTE,)) if held else (READY, ()))

    def test_a_right_hemicolectomy_filed_as_the_development_set_files_it_stays_ready(self):
        # the development set's every anastomosis (anthropic-project batches: A-note8, C-C2MEM-023, A-v3, A-v6) is filed
        # subtype ileocolic, joins the ileum and the colon - the joins case (Q3) never reads it as an ileum below the colon
        E = r3e()
        text, data, (code, quote) = E.AS_BEFORE['g7 a right hemicolectomy to the neo-terminal ileum, the subtype filed']
        y2 = next(item for item in data['anatomy'] if item['id'] == 'Y2')
        y2['joins'] = [fact('ileum', src(['S4'], 'ileocolic anastomosis')),
                       fact('colon', src(['S4'], 'ileocolic anastomosis'))]
        self.assertEqual(statuses(text, data, (code, quote))[code], (READY, ()))
        _claims, _out, R, _view = R2CL.run(text, data, R2CL.FAITHFUL)
        self.assertEqual(len(F.members(R, Y2, A.JOINS)), 2)
        self.assertFalse(evaluate.whole_colon_absent_possible(R))


# === P-MONO: no 9.4 weakening releases a held scene ===================================================================


class MonotonicityTests(SimpleTestCase):
    def test_no_weakening_releases_a_code_a_new_arm_holds(self):
        TP = properties()
        scenes = {
            '45391, an ileal pouch per anus': (scope(45391, approach=sup(AP.TRANSANAL), entries={Y2: POUCH_ENTRY}),
                                               '45391'),
            '45391, the approach through a stoma': (scope(45391, approach=sup(AP.THROUGH_STOMA),
                                                          entries={Y1: COLOSTOMY}), '45391'),
            '45341, the approach silent beside a loop ileostomy': (scope(45341, entries={Y1: ILEOSTOMY}), '45341'),
            '45331, through a colostomy': (scope(45331, approach=sup(AP.THROUGH_STOMA), entries={Y1: COLOSTOMY}),
                                           '45331'),
            '45331, a pouch approach': (scope(45331, approach=sup(AP.THROUGH_POUCH)), '45331'),
            '44382, a colostomy passed through': (ileoscopy(sup(LM.SIGMOID_COLON)), '44382'),
            '45380, the joins the ileum and the rectum': (RD.anus_scope(approach=sup(AP.TRANSANAL), entries={
                Y2: anastomosis(sup(LM.ILEUM), sup(LM.RECTUM))}), '45380'),
            '45380, the joins the rectum alone': (RD.anus_scope(approach=sup(AP.TRANSANAL), entries={
                Y2: anastomosis(sup(LM.RECTUM))}), '45380'),
            '45380, the right and the left colon': (RD.anus_scope(approach=sup(AP.TRANSANAL), entries=RD_absences(
                LM.RIGHT_COLON, LM.LEFT_COLON)), '45380'),
        }
        for name, (R, code) in scenes.items():
            self.assertTrue(evaluate.decide(code, (), R).held_facts, name)
            count = 0
            for label, weak, _what in TP.weakenings(R):
                count += 1
                with self.subTest(case=name, weakening=label):
                    self.assertTrue(evaluate.decide(code, (), weak).held_facts)
                    if evaluate._session(weak, E2) is not None:
                        self.assertIsNot(route_row(weak, int(code)).truth, T)
            self.assertGreater(count, 15, name)


# === P-INDEP's closure: the route table's reads are every lower-GI code's ===========================================


class ClosureTests(SimpleTestCase):
    def test_every_lower_gi_codes_closure_holds_the_route_tables_reads(self):
        route = {(read.role, read.attribute) for read in RQ.RULES[RQ.Requirement.ROUTE_TABLE].reads}
        # round r3's round 5 (D330 (1), lane rules6): + the session's reach, read to hold only (R5R-9: an ileoscopy's
        # reach supported at or past the cecum) - moved by its owner, requirements.RULES
        self.assertEqual(route, {(RQ.Role.SESSION, A.APPROACH), (RQ.Role.SESSION, A.THROUGH),
                                 (RQ.Role.ANATOMY, A.TYPE), (RQ.Role.ANATOMY, A.ORGAN), (RQ.Role.ANATOMY, A.SUBTYPE),
                                 (RQ.Role.ANATOMY, A.JOINS), (RQ.Role.SESSION, A.REACHED)})
        for code in sorted(LOWER_GI):
            closure = RQ.dependencies(str(code))
            with self.subTest(code=code):
                self.assertTrue({A.APPROACH, A.THROUGH} <= closure.reads[RQ.Role.SESSION])
                self.assertTrue({A.TYPE, A.ORGAN, A.SUBTYPE, A.JOINS} <= closure.reads[RQ.Role.ANATOMY])
        for code in catalogue.CODES:  # no other code reads them through the table
            if not catalogue.lower_gi(str(code)):
                found = RQ.reads_of(str(code))
                plain = tuple(read for requirement in RQ.requirements_of(str(code))
                              for read in RQ.RULES[requirement].reads_for(RQ.spec(str(code)).template))
                self.assertEqual(found, plain, code)

    def test_the_route_tables_own_row_is_asked_and_explained_at_rank_8_and_never_listed(self):
        rule = RQ.RULES[RQ.Requirement.ROUTE_TABLE]
        items = {(item.rank, item.fact) for item in rule.asks + rule.explains}
        self.assertEqual(items, {(RQ.Rank.PROCEDURE, RQ.FactKey.PROCEDURE)})
        # round r3's round 5 (DECISIONS D330 (1) (a), lane rules6, rules5's Q2): listed where the row stands apart from
        # the code's tags, so gate 6 generates its cases - moved by its owner, requirements.requirements_of
        for code in [str(code) for code in catalogue.CODES] + ['46221', '12345']:
            self.assertEqual(RQ.Requirement.ROUTE_TABLE in RQ.requirements_of(code), RQ.route_row_apart(code))
