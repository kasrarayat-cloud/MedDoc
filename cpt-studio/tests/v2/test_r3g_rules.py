"""Round r3's round-5 repair, lane rules6 (DECISIONS D330 (1); build-v2/a2b/r3b/r3h/rules6/NOTES.md): THE LOWER-GI PATH
GUARD, fail-closed by construction. TEXT-ONLY and SYNTHETIC: every note is written for these tests or is round 4a's
refuter's constructed input word for word (r3f/refute-rules5: tests/v2/test_refute_rules5.py, scripts/e2e1.py, probe1-8;
fictional clinicians), every pass-1 answer is built by hand with test_settle's builders and every pass-2 answer by
test_r2cl_lesion's faithful oracle, every other FactSet in code; nothing is sent.

The rule (engine/evaluate ``path_guard`` over engine/catalogue ``HARMLESS``): after every existing arm of a lower-GI
code's route row (every row of the route table), the code is held with the table's own hold unless EVERY anatomy entry
of the document is, for that code's route, (i) the entry the route itself uses (the stoma or the pouch the session
established it entered through) or (ii) a match for a row of ONE finite typed RULED HARMLESS SET for that route family -
every possible value of every field it files (type, subtype, organ, every joins member; read by ``_may_be``: a silent or
unreadable field may be every value) within the row. A per-anus code's own approach and through belong to the guard too.
The guard only holds; no answer lifts it (D324 (4)).
- FindingTests: R5R-1, R5R-2, R5R-3, R5R-4 (D330 (1) (c)), R5R-6, R5R-7, R5R-8, R5R-9 and the D328 addendum's silent-
  anastomosis residual, each on its finding's own input (RED on int6 + rules4 + rules5).
- HarmlessSetTests: the table is the DECLARED release set below, row by row (a mutant adding a harmful shape fails here).
- CensusTests: every entry shape over the contract's finite vocabularies (type x subtype x joins of up to two members x
  organ, silent included) x every route family, the field states, the route states and the colon's cover: the guard
  holds exactly the shapes outside the declared set.
- CompletenessTests: the guard reads every row of the route table (every lower-GI code of the catalogue).
- CommonInputTests: every harmless row keeps the common controls as int6 decides them (int6's decisions DECLARED from
  its run, r3h/rules6/out/rows_probe-i6.jsonl), and D328 (1) (c)'s common inputs end to end.
- VariantTests: at least six constructed variants per route family beyond the findings.
- MonotonicityTests (P-MONO) and RequirementsTests (D330 (1) (a): the route table's row in requirements_of).

Round r3's round 6 (DECISIONS D336 (1); r3i/int8): the construction rule completed in the release direction - every
attribute is read by its widest possible value unless the contract CONTROLS it, so each row releases on ONE controlled
claim (a controlled type, the organ claim of an absence, a controlled subtype), joins and every uncontrolled type are
read only to hold, a claim pass 2 rejected with no control is fully open, an anastomosis's unnamed ends are every
landmark or its subtype's own, a contradictory filing is read at its widest, and the per-anus approach (no control) is
never established. The DECLARED set, the oracle and every pin it owns below moved with it (each marked D336);
tests/v2/test_r3i_guard.py holds the findings, the state census, the P-MONO and P-CONTROLLED censuses.
"""
from __future__ import annotations

import copy
import itertools
import json
from dataclasses import replace
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, catalogue, evaluate
from studio.interpretation.engine import requirements as RQ
from studio.interpretation.engine.types import Id
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_r2cl_lesion as R2CL
from tests.v2 import test_r3c_rules as RR
from tests.v2 import test_r3d_rules as RD
from tests.v2 import test_r3f_rules as R3F
from tests.v2.test_settle import answer, event, fact, frame, labelled, opening, session, src

A, LM, EX = ct.Attribute, ct.Landmark, ct.Extent
AT, AP, SUB, SK, Kind = ct.AnatomyType, ct.Approach, ct.AnastomosisSubtype, ct.SessionKind, ct.Kind
E2, X1 = Id.parse('E2'), Id.parse('X1')
Y1, Y2, Y3, Y5, Y7 = (Id.parse(f'Y{n}') for n in (1, 2, 3, 5, 7))
sup, unres, neg, doubted, contra = EF.sup, EF.unres, EF.neg, EF.doubted, EF.contra
UNAPPRAISED = ct.Reason.UNAPPRAISED
ROUTE = RR.ROUTE                                     # 'coding_rule:stoma_route': the route table's own hold
HELD, READY = 'needs_clarification', 'ready'
held_of, serving = RR.held_of, RR.serving
entry_of, route_row, witnesses, scope = R3F.entry_of, R3F.route_row, R3F.witnesses, R3F.scope
open_denial = R3F.open_denial


def lm(*names: str) -> frozenset:
    return frozenset(LM(name) for name in names)


# === THE DECLARED RELEASE SET (DECISIONS D330 (1); NOTES section 2, row by row with its reason) =======================
# Written out member by member from the ruling - never computed from engine/catalogue - so the census below compares the
# guard with an independent statement of the set, and a mutant that adds a harmful shape to the table fails it.
OUTSIDE = lm('esophagus', 'proximal_esophagus', 'mid_esophagus', 'distal_esophagus', 'gastroesophageal_junction',
             'stomach', 'gastric_cardia', 'gastric_fundus', 'gastric_body', 'gastric_antrum', 'pylorus', 'duodenum',
             'duodenal_bulb', 'second_portion_duodenum', 'third_portion_duodenum', 'fourth_portion_duodenum', 'ampulla',
             'jejunum', 'common_bile_duct', 'bile_duct', 'pancreatic_duct', 'pancreas', 'gallbladder', 'liver',
             'lymph_node')
COLON_PARTS = lm('right_colon', 'left_colon', 'proximal_colon', 'distal_colon', 'cecum', 'appendiceal_orifice',
                 'ileocecal_valve', 'ascending_colon', 'hepatic_flexure', 'transverse_colon', 'splenic_flexure',
                 'descending_colon', 'sigmoid_colon', 'rectosigmoid')
COLON_ALL = COLON_PARTS | lm('colon')
SMALL_BOWEL = lm('jejunum', 'ileum', 'terminal_ileum', 'neo_terminal_ileum', 'small_bowel')
ILEAL_PARTS = lm('terminal_ileum', 'neo_terminal_ileum')
NO_ORGAN = lm('other', 'anastomosis', 'stoma', 'pouch')
ALL_TYPES, ALL_SUBTYPES, ALL_PLACES = frozenset(AT), frozenset(SUB), frozenset(LM)
COLON_KEEPING = frozenset({SUB.ILEOCOLIC, SUB.COLOCOLIC, SUB.COLORECTAL, SUB.COLOANAL})
UPPER_SUBTYPES = frozenset({SUB.GASTROJEJUNAL, SUB.GASTRODUODENAL, SUB.ESOPHAGOJEJUNAL, SUB.ESOPHAGOGASTRIC,
                            SUB.HEPATICOJEJUNAL, SUB.CHOLEDOCHODUODENAL, SUB.PANCREATICOJEJUNAL})
ILEUM_BELOW = frozenset({SUB.ILEORECTAL, SUB.ILEOANAL})
FAMILIES = ('COLON', 'RECTUM_AND_SIGMOID', 'COLONIC_STOMA', 'ILEAL_STOMA', 'POUCH')
ABSENT = {
    'COLON': OUTSIDE | lm('other') | COLON_PARTS | lm('rectum') | SMALL_BOWEL,
    'RECTUM_AND_SIGMOID': OUTSIDE | lm('other') | COLON_PARTS | lm('rectum') | SMALL_BOWEL,
    'COLONIC_STOMA': OUTSIDE | lm('other') | COLON_PARTS | lm('rectum') | SMALL_BOWEL | lm('anal_canal'),
    'ILEAL_STOMA': OUTSIDE | lm('other') | COLON_ALL | lm('rectum', 'anal_canal') | ILEAL_PARTS,
    'POUCH': OUTSIDE | lm('other') | COLON_ALL | lm('rectum') | ILEAL_PARTS,
}
# DECISIONS D336 (1) (b): what the contract CONTROLS, DECLARED from 3.2.3's tables (never read from engine/catalogue or
# contract/claims - tests/v2/test_r3i_guard.py's P-CONTROLLED census ties both to these): the anatomy types with a
# sibling control, the subtypes with one (OTHER and pancreaticojejunal have none), the approaches with a contrary (per
# anus has none)
CONTROLLED_TYPES = frozenset({AT.ILEAL_POUCH, AT.GASTRIC_POUCH, AT.STOMA})
CONTROLLED_SUBTYPES = ALL_SUBTYPES - {SUB.OTHER, SUB.PANCREATICOJEJUNAL}
CONTROLLED_APPROACHES = frozenset({AP.ORAL, AP.THROUGH_STOMA, AP.THROUGH_POUCH})
# family -> [(shape, decided_by, values, organs, joins)] (DECISIONS D336 (1)): each row RELEASES ON ONE CONTROLLED CLAIM
# - decided_by 'type' (a controlled type), 'organ' (the organ claim of an entry filed surgically absent: the absence form)
# or 'subtype' (a controlled subtype, which names an anastomosis) - every value of which lies within ``values``; a filed
# organ within ``organs`` and every place of each joins member within ``joins`` are read only to HOLD. No row releases on
# joins (D330 (1)'s rows 7 and 9 are gone) or on an uncontrolled type (row 4, OUTSIDE, and the Roux limb are gone)
COLON_JOINS = SMALL_BOWEL | COLON_ALL | lm('rectum', 'anal_canal', 'pouch')
POUCH_JOINS = SMALL_BOWEL | lm('rectum', 'anal_canal', 'pouch')
UPPER_JOINS = OUTSIDE | lm('pouch')


def declared_rows(family: str) -> list:
    rows = [('absent', 'organ', ABSENT[family], ABSENT[family], ABSENT[family]),
            ('anastomosis_upper', 'subtype', UPPER_SUBTYPES & CONTROLLED_SUBTYPES, ALL_PLACES, UPPER_JOINS),
            # a gastric pouch's filed organ outside the lower GI tract (D336 (1) (e): an upper type at a lower organ)
            ('upper_alteration', 'type', frozenset({AT.GASTRIC_POUCH}), OUTSIDE, UPPER_JOINS),
            ('stoma', 'type', frozenset({AT.STOMA}), ALL_PLACES, ALL_PLACES)]   # D310 (1); its organ never read
    if family == 'POUCH':
        rows.append(('anastomosis_pouch', 'subtype', ILEUM_BELOW, ALL_PLACES, POUCH_JOINS))
    else:
        rows.append(('anastomosis_colon', 'subtype', COLON_KEEPING, ALL_PLACES, COLON_JOINS))
    return rows


WHOLE_COLON_HARMLESS = {'ILEAL_STOMA', 'POUCH'}
ILEUM_BELOW_HARMLESS = {'POUCH'}


# The two ends each subtype names (every subtype but OTHER), DECLARED by its name over the anatomy table's regions: a
# joins member naming no placed organ is read as one of its subtype's own ends (R5R-6's class rule, by principle)
ILEAL = lm('ileum', 'terminal_ileum', 'neo_terminal_ileum', 'small_bowel')
STOMACH_PLACES = lm('stomach', 'gastric_cardia', 'gastric_fundus', 'gastric_body', 'gastric_antrum', 'pylorus')
ESOPHAGUS_PLACES = lm('esophagus', 'proximal_esophagus', 'mid_esophagus', 'distal_esophagus',
                      'gastroesophageal_junction')
DUODENUM_PLACES = lm('duodenum', 'duodenal_bulb', 'second_portion_duodenum', 'third_portion_duodenum',
                     'fourth_portion_duodenum')
BILIARY_PLACES = lm('ampulla', 'common_bile_duct', 'bile_duct', 'gallbladder')
SUBTYPE_ENDS = {
    SUB.ILEOCOLIC: ILEAL | COLON_ALL, SUB.COLOCOLIC: COLON_ALL, SUB.COLORECTAL: COLON_ALL | lm('rectum'),
    SUB.COLOANAL: COLON_ALL | lm('anal_canal'), SUB.ILEORECTAL: ILEAL | lm('rectum'),
    SUB.ILEOANAL: ILEAL | lm('anal_canal'), SUB.GASTROJEJUNAL: STOMACH_PLACES | lm('jejunum'),
    SUB.GASTRODUODENAL: STOMACH_PLACES | DUODENUM_PLACES, SUB.ESOPHAGOJEJUNAL: ESOPHAGUS_PLACES | lm('jejunum'),
    SUB.ESOPHAGOGASTRIC: ESOPHAGUS_PLACES | STOMACH_PLACES,
    SUB.HEPATICOJEJUNAL: BILIARY_PLACES | lm('liver', 'jejunum'),
    SUB.CHOLEDOCHODUODENAL: BILIARY_PLACES | DUODENUM_PLACES,
    SUB.PANCREATICOJEJUNAL: lm('pancreas', 'pancreatic_duct', 'jejunum'),
}


def oracle_ileum_below(subtypes, subtype_silent: bool, joins, may_be_anastomosis: bool = False) -> bool:
    """The ileum joined below the colon, DECLARED (D327 (1), the D328 addendum, D330 (1) (c), R5R-6, D336 (1) (b)): a
    filed subtype that may be ileorectal or ileoanal; or joins - one member that may lie below the colon (the rectum, the
    anal canal or no placed organ); two or more where one may lie in the small bowel beside another that may lie below - a
    member naming no placed organ read as either, unless the subtype is filed and every subtype it may be names its ends:
    then as one of those ends. D336 (1) (b): an entry that may be an anastomosis has two ends, and each its joins list does
    not name may be every landmark - or, its subtype filed and naming its ends, one of those."""
    if not subtype_silent and subtypes & ILEUM_BELOW:
        return True
    ends = None
    if not subtype_silent and subtypes and all(value in SUBTYPE_ENDS for value in subtypes):
        ends = frozenset().union(*(SUBTYPE_ENDS[value] for value in subtypes))
    members = [((member - NO_ORGAN) | ends) if ends is not None and member & NO_ORGAN else member for member in joins]
    below = lm('rectum', 'anal_canal') | NO_ORGAN
    small = SMALL_BOWEL | NO_ORGAN
    if len(members) == 1 and members[0] & below:
        return True
    if len(members) < 2 and may_be_anastomosis:
        members += [ends if ends is not None else ALL_PLACES] * (2 - len(members))
    return any(members[i] & small and members[j] & below for i in range(len(members)) for j in range(len(members))
               if i != j)


def oracle_decided(types, subtypes, subtype_silent: bool, organs, organ_silent: bool):
    """D336 (1) (b) and (e), DECLARED: the controlled claim that decides an entry's shape - ('subtype', its values) for a
    filed subtype that may only be controlled ones beside a type that may only be an anastomosis; ('organ', its values)
    for an entry that may only be surgically absent, its organ filed (the absence form); ('type', its values) for a type
    that may only be controlled ones, the subtype silent - else None (the widest reading, which no row holds)."""
    if not subtype_silent:
        if subtypes and subtypes <= CONTROLLED_SUBTYPES and types == {AT.ANASTOMOSIS}:
            return 'subtype', subtypes
        return None
    if types == {AT.SURGICALLY_ABSENT}:
        return ('organ', organs) if not organ_silent else None
    if types and types <= CONTROLLED_TYPES:
        return 'type', types
    return None


def oracle_ends_contradicted(subtypes, organs, organ_silent: bool, joins) -> bool:
    """D336 (1) (e), DECLARED: for some subtype the entry may be, a filed organ or a joins member that may name a placed
    organ outside that subtype's own ends (a landmark naming no placed organ names an end)."""
    fields = list(joins) + ([] if organ_silent else [organs])
    return any(place not in SUBTYPE_ENDS[subtype] and place not in NO_ORGAN
               for subtype in subtypes for found in fields for place in found)


def oracle_harmless(family: str, types, subtypes, subtype_silent: bool, organs, organ_silent: bool, joins) -> bool:
    """The declared release set's verdict (D330 (1), D336 (1)) on one entry whose fields may be these values - the
    caller's widest reading of each: a silent field, an open denial, an established negation or a claim pass 2 rejected
    with no control left, every value."""
    if family not in ILEUM_BELOW_HARMLESS and oracle_ileum_below(subtypes, subtype_silent, joins,
                                                                AT.ANASTOMOSIS in types):
        return False
    decided = oracle_decided(types, subtypes, subtype_silent, organs, organ_silent)
    if decided is None:
        return False
    by, values = decided
    if by == 'subtype' and oracle_ends_contradicted(values, organs, organ_silent, joins):
        return False
    for _shape, r_by, r_values, r_organs, r_joins in declared_rows(family):
        if r_by != by or not values <= r_values:
            continue
        if not organ_silent and not organs <= r_organs:
            continue
        if all(member <= r_joins for member in joins):
            return True
    return False


# Each field state the census files: (label, the fact or None for silent, the values it may be).
def field_states(values, enum, others):
    """Every state of one field over ``values``: silent; supported; claimed (unappraised); rejected (D336 (1) (b): a claim
    pass 2 contradicted with no control left, fully open); a contradiction's sides with each of ``others``; an established
    negation; an open denial."""
    yield 'silent', None, frozenset(enum)
    for value in values:
        yield f'{value.value} supported', sup(value), frozenset({value})
        yield f'{value.value} claimed', unres(value, UNAPPRAISED), frozenset({value})
        yield f'{value.value} rejected', unres(value, ct.Reason.APPRAISAL_CONTRADICTS), frozenset(enum)
    for value in values[:3]:
        for other in others:
            if other is not value:
                yield f'{value.value} or {other.value}', contra(value, other), frozenset({value, other})
    yield 'established negation', neg(values[0]), frozenset(enum)
    yield 'open denial', open_denial(values[0]), frozenset(enum)


def bare():
    """A FactSet holding one colonoscopy session and nothing else (the census swaps its anatomy)."""
    doc = EF.Doc()
    doc.session(1, SK.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
    return doc.build()


def with_entry(R, facts):
    return replace(R, anatomy={Y1: facts})


def needs(name: str):
    return catalogue.RouteAnatomy[name]


# === the findings: round 4a's refuter's inputs word for word (r3f/refute-rules5) =====================================

HEAD = ('SYNTHETIC LOWER ENDOSCOPY REPORT\n'                   # S1
        'Date of service: 03/14/2031\n'                         # S2
        'Endoscopist: Corvin Ashdale, MD (fictional)\n'         # S3
        '\n')


def note(history, findings, act, *, kind, kind_words, approach, reached, anatomy, place=None, place_words='',
         exam_status='was inserted', through=None, tract=None):
    """test_refute_rules5.note (and e2e1.note's tract), word for word: a lower endoscopy X1 (``kind``), its examination
    E1 and, with ``act``, a cold-forceps biopsy E2 at ``place``. anatomy: [(id, type, words, [organ...], [subtype...],
    [joins...])]; approach and through: (value, words) or None."""
    text = HEAD + f'History: {history}\n' + f'Findings: {findings}\n' + (f'{act}\n' if act else '')
    entries = [{'id': yid, 'type': fact(typ, src(['S4'], words)),
                'organ': [fact(organ, src(['S4'], words)) for organ in organs],
                'subtype': [fact(value, src(['S4'], words)) for value in subtypes],
                'joins': [fact(value, src(['S4'], words)) for value in joins]}
               for yid, typ, words, organs, subtypes, joins in anatomy]
    fields = dict(examination=[fact('E1', src(['S5']))], encounter=[fact('this_encounter', frame(['S2']))],
                  approach=[fact(approach[0], src(['S5'], approach[1]))] if approach else [],
                  through=[fact(through[0], src(['S5'], through[1]))] if through else [],
                  reached=[fact(value, src(['S5'], words)) for value, words in reached])
    if tract:
        fields['tract'] = [fact(tract, src(['S5'], kind_words))]
    sess = session('X1', fact(kind, src(['S5'], kind_words)), **fields)
    events = [event('E1', ['S5'], kind_words, exam_status, 'examination', session=[fact('X1', src(['S5']))])]
    if act:
        events.append(event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                            target__places=[fact(place, src(['S6'], place_words))],
                            technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))]))
    data = answer(
        sections=[opening(), labelled('N1', 'S4', 'History:', 'history'), labelled('N2', 'S5', 'Findings:', 'findings')],
        sessions=[sess], anatomy=entries, events=events)
    return text, data


def status(case, code, quote) -> tuple:
    text, data = case
    return R2CL.outcomes(text, data, R2CL.FAITHFUL, (code, quote))[code][:2]


FLEX, COLO = ('flex_sig', 'flexible sigmoidoscope'), ('colonoscopy', 'colonoscope')
PER_ANUS = ('transanal', 'inserted per anus')
BX_ANAST = 'Two biopsies of the anastomosis were taken with cold forceps.'
BX_POUCH = 'Two biopsies of the pouch body were taken with cold forceps.'
BX_CECUM = 'Two biopsies of the cecum were taken with cold forceps.'
BX_SIG = 'Two biopsies of the sigmoid colon were taken with cold forceps.'
BX_DESC = 'Two biopsies of the descending colon were taken with cold forceps.'
NTI = [('neo_terminal_ileum', 'into the neo-terminal ileum')]
CECUM = [('cecum', 'advanced to the cecum')]
IAA = 'Total proctocolectomy with an ileoanal anastomosis in 2025.'
IAA_ANAT = [('Y1', 'surgically_absent', 'Total proctocolectomy', ['colon'], [], []),
            ('Y2', 'anastomosis', 'ileoanal anastomosis', [], ['ileoanal'], ['ileum', 'anal_canal'])]
FS_IAA = ('The flexible sigmoidoscope was inserted per anus, passed across the ileoanal anastomosis and advanced 15 cm '
          'into the neo-terminal ileum.')
SPOUCH = 'Restorative proctocolectomy with an S-pouch anal anastomosis in 2024.'
SPOUCH_ANAT = [('Y1', 'surgically_absent', 'Restorative proctocolectomy', ['colon'], [], []),
               ('Y2', 'other_alteration', 'S-pouch anal anastomosis', ['pouch'], [], ['ileum', 'anal_canal'])]
FS_SP = 'The flexible sigmoidoscope was inserted per anus into the S-pouch and advanced 10 cm into the afferent limb.'
JPOUCH = 'Total proctocolectomy with an ileal J-pouch anal anastomosis in 2025.'
JPOUCH_ANAT = [('Y2', 'anastomosis', 'ileal J-pouch anal anastomosis', [], [], ['pouch', 'anal_canal'])]
FS_JP = 'The flexible sigmoidoscope was inserted per anus into the J-pouch and advanced 15 cm into the afferent limb.'
IPAA_J_ANAT = [('Y1', 'surgically_absent', 'Total proctocolectomy', ['colon'], [], []),
               ('Y2', 'anastomosis', 'ileal J-pouch anal anastomosis', [], ['ileoanal'], ['pouch', 'anal_canal'])]
FS2 = ('The flexible sigmoidoscope was inserted per anus into the J-pouch and advanced 15 cm into the neo-terminal '
       'ileum.')
EUS_F = ('The echoendoscope was inserted per anus, passed across the ileoanal anastomosis into the neo-terminal ileum, '
         'and the anastomosis and the presacral space were examined.')
APR = 'Abdominoperineal resection of the rectum and anal canal for rectal cancer in 2027.'
APR_ANAT = [('Y1', 'surgically_absent', 'Abdominoperineal resection of the rectum', ['rectum'], [], []),
            ('Y2', 'surgically_absent', 'and anal canal', ['anal_canal'], [], [])]
FC_APR = 'The colonoscope was advanced to the cecum and the appendiceal orifice was identified.'
FS_APR = 'The flexible sigmoidoscope was advanced to the descending colon.'
FC = 'The colonoscope was inserted per anus and advanced to the cecum.'
SBR = 'Small bowel resection with an ileo-ileal anastomosis for a Crohn stricture in 2028.'
REV = ('Low anterior resection with a colorectal anastomosis in 2028; the diverting loop ileostomy was closed with an '
       'ileo-ileal anastomosis in 2029.')
RYGB = 'Roux-en-Y gastric bypass with a jejuno-jejunal anastomosis in 2020.'
CJP = 'Low anterior resection with a colonic J-pouch anal anastomosis in 2027.'
CJP_ANAT = [('Y1', 'anastomosis', 'colonic J-pouch anal anastomosis', [], ['coloanal'], ['pouch', 'anal_canal'])]
KOCK = 'Proctocolectomy with a continent ileostomy (Kock pouch) in 1998.'
KOCK_ANAT = [('Y1', 'surgically_absent', 'Proctocolectomy', ['colon'], [], []),
             ('Y2', 'ileal_pouch', 'Kock pouch', [], [], []),
             ('Y3', 'stoma', 'continent ileostomy', ['ileum'], [], [])]
FK = ('The endoscope was introduced through the stoma and the nipple valve into the Kock pouch and advanced 15 cm into '
      'the afferent ileum.')
BX_K = 'Two biopsies of the pouch were taken with cold forceps.'


def kock():
    return note(KOCK, FK, BX_K, kind='enteroscopy', kind_words='endoscope', approach=('through_stoma',
                'through the stoma'), through=('Y3', 'through the stoma'), reached=[('ileum', 'into the afferent ileum')],
                anatomy=KOCK_ANAT, place='pouch', place_words='pouch', exam_status='was introduced')


R5R_1 = {  # R5R-1's input and its variants (FindingF1Tests; e2e1 F1a-F1c, F1e): each HELD by the table's own hold
    '45331, an ileoanal anastomosis (subtype and joins)': (
        note(IAA, FS_IAA, BX_ANAST, kind=FLEX[0], kind_words=FLEX[1], approach=PER_ANUS, reached=NTI,
             anatomy=IAA_ANAT, place='anastomosis', place_words='anastomosis'), '45331', BX_ANAST),
    '45330, an ileoanal anastomosis, diagnostic': (
        note(IAA, FS_IAA, '', kind=FLEX[0], kind_words=FLEX[1], approach=PER_ANUS, reached=NTI, anatomy=IAA_ANAT),
        '45330', FS_IAA),
    '45331, an S-pouch filed as other_alteration joining the ileum and the anal canal': (
        note(SPOUCH, FS_SP, BX_POUCH, kind=FLEX[0], kind_words=FLEX[1], approach=PER_ANUS,
             reached=[('neo_terminal_ileum', 'into the afferent limb')], anatomy=SPOUCH_ANAT, place='pouch',
             place_words='pouch body'), '45331', BX_POUCH),
    '45331, a J-pouch anastomosis, subtype silent, joins pouch and anal canal': (
        note(JPOUCH, FS_JP, BX_POUCH, kind=FLEX[0], kind_words=FLEX[1], approach=PER_ANUS,
             reached=[('neo_terminal_ileum', 'into the afferent limb')], anatomy=JPOUCH_ANAT, place='pouch',
             place_words='pouch body'), '45331', BX_POUCH),
    '45331, an ileal J-pouch anal anastomosis filed as the anastomosis (e2e1 F1c)': (
        note(JPOUCH, FS2, BX_POUCH, kind=FLEX[0], kind_words=FLEX[1], approach=PER_ANUS, reached=NTI,
             anatomy=IPAA_J_ANAT, place='pouch', place_words='pouch body'), '45331', BX_POUCH),
    '45341, an ileoanal anastomosis, a sigmoidoscopic EUS per anus (e2e1 F1e)': (
        note(IAA, EUS_F, '', kind='eus', kind_words='echoendoscope', approach=PER_ANUS, reached=NTI, anatomy=IAA_ANAT,
             tract='lower'), '45341', 'the anastomosis and the presacral space were examined'),
}
R5R_2 = {  # R5R-2's input (FindingF2Tests; e2e1 F2a, F2b): the anal canal filed surgically absent, HELD
    '45380, colonoscopy to the cecum, approach silent': (
        note(APR, FC_APR, BX_CECUM, kind='colonoscopy', kind_words=COLO[1], approach=None, reached=CECUM,
             anatomy=APR_ANAT, place='cecum', place_words='cecum', exam_status='was advanced'), '45380', BX_CECUM),
    '45331, sigmoidoscopy to the descending colon, approach silent': (
        note(APR, FS_APR, BX_DESC, kind=FLEX[0], kind_words=FLEX[1], approach=None,
             reached=[('descending_colon', 'to the descending colon')], anatomy=APR_ANAT, place='descending_colon',
             place_words='descending colon', exam_status='was advanced'), '45331', BX_DESC),
    '45380, colonoscopy to the cecum, per anus filed (probe1)': (
        note(APR, FC, BX_CECUM, kind='colonoscopy', kind_words=COLO[1], approach=PER_ANUS, reached=CECUM,
             anatomy=APR_ANAT, place='cecum', place_words='cecum'), '45380', BX_CECUM),
}
R5R_4 = {  # R5R-4's input (FindingF3Tests; e2e1 F3a-F3c) and R5R-6's (e2e1 F3d): READY, as on int6
    'a Crohn ileo-ileal anastomosis, joins [ileum]': (
        SBR, [('Y1', 'anastomosis', 'ileo-ileal anastomosis', [], ['other'], ['ileum'])]),
    'a closed loop ileostomy after LAR, joins [ileum]': (
        REV, [('Y1', 'anastomosis', 'colorectal anastomosis', [], ['colorectal'], ['colon', 'rectum']),
              ('Y2', 'anastomosis', 'ileo-ileal anastomosis', [], ['other'], ['ileum'])]),
    'a Roux-en-Y jejuno-jejunal anastomosis, joins [jejunum]': (
        RYGB, [('Y1', 'anastomosis', 'jejuno-jejunal anastomosis', [], ['other'], ['jejunum'])]),
    'R5R-6: a colonic J-pouch anal anastomosis (coloanal; joins the pouch and the anal canal)': (CJP, CJP_ANAT),
}


def per_anus_scope(code: int, *, approach=sup(AP.TRANSANAL), through=None, entries=None, reached=None):
    """R3F.scope: ``code``'s per-anus session, its approach (supported per anus by default)."""
    return scope(code, approach=approach, through=through, entries=entries, reached=reached)


def ileoscopy(organ, *, reached=(sup(EX.ILEUM),), entries=None, through=sup(Y1)):
    """An enteroscopy X1 through a stoma Y1 (``organ``: its organ fact, None silent), reaching ``reached``, its
    examination E1 and a cold-forceps biopsy E2 of the ileum (probe6, probe8)."""
    doc = EF.Doc()
    doc.session(1, SK.ENTEROSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER), reached=list(reached),
                approach=sup(AP.THROUGH_STOMA), through=through)
    doc.exam(1)
    doc.act(2, Kind.BIOPSY, places=[sup(LM.ILEUM)], device=sup(ct.Device.COLD_FORCEPS))
    doc.anatomy[Y1] = entry_of(type=sup(AT.STOMA), organ=organ)
    doc.anatomy.update(entries or {})
    return doc.build()


def assessed(R, code, number=2) -> tuple:
    (found,) = [item for item in TA.run(R, (code, number)).codes if item.code == code]
    return found.status.value, tuple(sorted({held.cause for held in found.held_facts}))


class FindingTests(SimpleTestCase):
    def test_r5r_1_an_ileoanal_join_however_filed_holds_the_sigmoidoscopy_family(self):
        # RED: READY on int6 and on int6 + rules4 + rules5 (r3f/verify-rules5-R5R-1: 9 of 9, 0 questions)
        for name, (case, code, quote) in R5R_1.items():
            with self.subTest(case=name):
                found = status(case, code, quote)
                self.assertEqual(found[0], HELD)
                self.assertIn(ROUTE, found[1])

    def test_r5r_2_an_absent_anal_canal_holds_every_per_anus_code(self):
        # RED: READY on int6 and rules5 (verify-rules5-R5R-2); a colostomy is the only route after an APR
        for name, (case, code, quote) in R5R_2.items():
            with self.subTest(case=name):
                found = status(case, code, quote)
                self.assertEqual(found[0], HELD)
                self.assertIn(ROUTE, found[1])

    def test_r5r_3_a_kock_pouch_holds_the_ileoscopy_and_44386_stays_a_recorded_limit(self):
        # RED: 44382 READY with 0 questions on int6 and rules5 (verify-rules5-R5R-3); now the pouch beside the stoma's
        # route is no harmless shape for an ileal stoma. 44386 stays held (D330 (1): its hold is a recorded limit - the
        # POUCH class's route needs the through to name the pouch)
        found = status(kock(), '44382', BX_K)
        self.assertEqual(found[0], HELD)
        self.assertIn(ROUTE, found[1])
        self.assertEqual(status(kock(), '44386', BX_K)[0], HELD)
        diagnostic = note(KOCK, FK, '', kind='enteroscopy', kind_words='endoscope',
                          approach=('through_stoma', 'through the stoma'), through=('Y3', 'through the stoma'),
                          reached=[('ileum', 'into the afferent ileum')], anatomy=KOCK_ANAT,
                          exam_status='was introduced')
        self.assertEqual(status(diagnostic, '44380', FK)[0], HELD)

    def test_r5r_4_and_r5r_6_a_colon_that_remains_beside_the_join_stays_ready(self):
        # RED: held on rules5 by the table's own hold (R5R-4: verify-rules5-R5R-4; R5R-6: e2e1 F3d), READY on int6.
        # Round r3's round 6 (DECISIONS D336 (1) (b), final check 3, superseding D330 (1) (c)'s release): a joins list of
        # ONE member is that member plus every landmark - an IRA or an IPAA whose other end pass 1 did not file - and the
        # subtype OTHER has no control, so R5R-4's three one-member filings hold now (moved by evaluate.path_guard);
        # R5R-6's colonic J-pouch, a controlled coloanal subtype that decides its ends, stays READY
        moved = {'a Crohn ileo-ileal anastomosis, joins [ileum]', 'a closed loop ileostomy after LAR, joins [ileum]',
                 'a Roux-en-Y jejuno-jejunal anastomosis, joins [jejunum]'}
        for name, (history, anatomy) in R5R_4.items():
            with self.subTest(case=name):
                case = note(history, FC, BX_CECUM, kind='colonoscopy', kind_words='colonoscope', approach=PER_ANUS,
                            reached=CECUM, anatomy=anatomy, place='cecum', place_words='cecum')
                self.assertEqual(status(case, '45380', BX_CECUM), (HELD, (ROUTE,)) if name in moved else (READY, ()))
        # 44389 through a Hartmann colostomy to the cecum beside an ileo-ileal anastomosis (R5R-4's FactSet): held now
        S = RR.stoma_scope(reached=(sup(EX.CECUM),), organ=sup(LM.SIGMOID_COLON),
                           entries={Y2: entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.OTHER),
                                                 joins=(sup(LM.ILEUM),))})
        self.assertIn(ROUTE, [held[1] for held in held_of(S, '44389')])

    def test_r5r_7_another_established_approach_holds_the_per_anus_codes(self):
        # RED (probe6): READY on int6 and rules5 for each approach SUPPORTED oral, transnasal, through a gastrostomy or
        # percutaneous - the record establishes no per-anus route
        for approach in (AP.ORAL, AP.TRANSNASAL, AP.THROUGH_GASTROSTOMY, AP.PERCUTANEOUS):
            for code in (45380, 45331, 45391, 45341):
                with self.subTest(approach=approach.value, code=code):
                    found = assessed(per_anus_scope(code, approach=sup(approach)), str(code))
                    self.assertEqual(found[0], HELD)
                    self.assertIn(ROUTE, found[1])

    def test_r5r_8_a_through_that_may_name_a_stoma_holds_the_per_anus_codes(self):
        # RED (probe6): READY on int6 and rules5 - the approach per anus, the through SUPPORTED naming a stoma whose organ
        # pass 1 claimed in the sigmoid colon
        colostomy = {Y5: entry_of(type=sup(AT.STOMA), organ=unres(LM.SIGMOID_COLON, UNAPPRAISED))}
        for code in (45380, 45331, 45391, 45341):
            with self.subTest(code=code):
                found = assessed(per_anus_scope(code, through=sup(Y5), entries=colostomy), str(code))
                self.assertEqual(found[0], HELD)
                self.assertIn(ROUTE, found[1])

    def test_r5r_9_an_ileoscopy_needs_its_stoma_ileal_and_no_colon_traversed(self):
        # RED (probe6, probe8): READY on int6 and rules5. (a) the stoma's organ filed outside the ileum; (b) the organ
        # silent and the reach supported through the colon to the cecum (a colonoscopy through a stoma)
        held = {
            'a jejunostomy (organ claimed the jejunum)': ileoscopy(unres(LM.JEJUNUM, UNAPPRAISED)),
            'a gastrostomy (organ claimed the stomach)': ileoscopy(unres(LM.STOMACH, UNAPPRAISED)),
            'the organ silent, the reach the transverse colon, the cecum and the terminal ileum': ileoscopy(
                None, reached=(sup(EX.TRANSVERSE_COLON), sup(EX.CECUM), sup(EX.TERMINAL_ILEUM))),
            'the organ claimed the ileum, the reach the cecum': ileoscopy(unres(LM.ILEUM, UNAPPRAISED),
                                                                         reached=(sup(EX.CECUM), sup(EX.ILEUM))),
        }
        for name, R in held.items():
            for code, number in (('44380', 1), ('44382', 2)):
                with self.subTest(case=name, code=code):
                    found = assessed(R, code, number)
                    self.assertEqual(found[0], HELD)
                    self.assertIn(ROUTE, found[1])
        for name, R in {'an end ileostomy, the organ the ileum': ileoscopy(unres(LM.ILEUM, UNAPPRAISED)),
                        'the organ silent, an ileal reach': ileoscopy(None),
                        'the organ the small bowel, the reach the valve': ileoscopy(
                            sup(LM.SMALL_BOWEL), reached=(sup(EX.ILEOCECAL_VALVE), sup(EX.ILEUM)))}.items():
            with self.subTest(control=name):
                self.assertEqual(assessed(R, '44382'), (READY, ()))

    def test_the_silent_anastomosis_residual_holds(self):
        # the D328 addendum's recorded residual, closed by the guard (D330 (1)): an anastomosis whose subtype AND joins
        # pass 1 left silent matches no row - rules4's g7b (the subtype not filed) moves to held; the subtype filed, or the
        # development set's filing (subtype ileocolic, joins the ileum and the colon), stays READY
        E = R3F.r3e()
        text, data, (code, quote) = E.AS_BEFORE['g7b a right hemicolectomy to the neo-terminal ileum, the subtype not '
                                                'filed (the verifier c2)']
        found = R3F.statuses(text, data, (code, quote))[code]
        self.assertEqual(found[0], HELD)
        self.assertIn(ROUTE, found[1])
        text, data, (code, quote) = E.AS_BEFORE['g7 a right hemicolectomy to the neo-terminal ileum, the subtype filed']
        self.assertEqual(R3F.statuses(text, data, (code, quote))[code], (READY, ()))
        data = copy.deepcopy(data)  # rules4's shared case: never mutated in place
        y2 = next(item for item in data['anatomy'] if item['id'] == 'Y2')
        y2['joins'] = [fact('ileum', src(['S4'], 'ileocolic anastomosis')),
                       fact('colon', src(['S4'], 'ileocolic anastomosis'))]
        self.assertEqual(R3F.statuses(text, data, (code, quote))[code], (READY, ()))
        for code in (45380, 45331, 44389):
            with self.subTest(code=code):
                entries = {Y2: entry_of(type=sup(AT.ANASTOMOSIS))}
                R = (RR.stoma_scope(reached=(sup(EX.CECUM),), organ=sup(LM.SIGMOID_COLON), entries=entries)
                     if code == 44389 else per_anus_scope(code, entries=entries))
                self.assertEqual(witnesses(route_row(R, code))[-1], (ROUTE, A.TYPE, X1, None))

    def test_no_question_is_served_to_a_code_the_guard_holds(self):
        # the table's own hold is ABSENT to the planner (asking's census): nothing is asked of Fable for a held code
        cases = [(case, code) for case, code, _quote in R5R_1.values()] + [
            (case, code) for case, code, _quote in R5R_2.values()] + [(kock(), '44382')]
        for (text, data), code in cases:
            with self.subTest(code=code, note=text.split('\n')[4][:50]):
                _claims, _out, R, view = R2CL.run(text, data, R2CL.FAITHFUL)
                self.assertEqual(serving(asking.plan(R, (), view), code), [])


# === the table: the declared release set, row by row ==================================================================


def table_rows(family: str) -> set:
    return {(row.shape.value, row.decided_by.value, row.values, row.organs, row.joins)
            for row in catalogue.HARMLESS[needs(family)]}


class HarmlessSetTests(SimpleTestCase):
    def test_the_table_is_the_declared_release_set(self):
        self.assertEqual({member.name for member in catalogue.RouteAnatomy}, set(FAMILIES))
        self.assertEqual(set(catalogue.HARMLESS), set(catalogue.RouteAnatomy))
        for family in FAMILIES:
            with self.subTest(family=family):
                self.assertEqual(table_rows(family), set(declared_rows(family)))
                self.assertTrue(all(row.needs is needs(family) for row in catalogue.HARMLESS[needs(family)]))
        self.assertEqual({needs.name for needs in catalogue.HARMLESS_WHOLE_COLON}, WHOLE_COLON_HARMLESS)
        self.assertEqual({needs.name for needs in catalogue.HARMLESS_ILEUM_BELOW}, ILEUM_BELOW_HARMLESS)
        self.assertEqual({row.needs for row in catalogue.LOWER_ROUTES.values()}, set(catalogue.RouteAnatomy))

    def test_the_places_are_the_declared_members_and_split_by_the_anatomy_table(self):
        from studio.interpretation.engine import anatomy
        self.assertEqual(catalogue.OUTSIDE_LOWER_GI, OUTSIDE)
        self.assertEqual(catalogue.COLON_PARTS, COLON_PARTS)
        self.assertEqual(catalogue.COLON_LANDMARKS, COLON_ALL)
        self.assertEqual(catalogue.SMALL_BOWEL_LANDMARKS, SMALL_BOWEL)
        self.assertEqual(catalogue.ILEAL_PARTS, ILEAL_PARTS)
        self.assertEqual(catalogue.NO_PLACED_ORGAN, NO_ORGAN)
        self.assertEqual(catalogue.RECTUM_LANDMARKS | catalogue.ANUS_LANDMARKS, lm('rectum', 'anal_canal'))
        # every landmark is outside the lower GI tract, or one of its places, or names no placed organ - never two
        lower = COLON_ALL | SMALL_BOWEL - lm('jejunum') | lm('rectum', 'anal_canal')
        self.assertEqual(OUTSIDE | lower | NO_ORGAN, ALL_PLACES)
        self.assertEqual(OUTSIDE & (lower | NO_ORGAN), frozenset())
        for place in OUTSIDE:
            for anchor in (LM.ANAL_CANAL, LM.RECTUM, LM.COLON, LM.ILEUM):
                self.assertFalse(anatomy.compatible(place, anchor), (place, anchor))
        # the subtype classes split the enumeration with OTHER (a subtype the enumeration gains is in no row)
        self.assertEqual(catalogue.COLON_KEEPING_SUBTYPES, COLON_KEEPING)
        self.assertEqual(catalogue.UPPER_SUBTYPES, UPPER_SUBTYPES)
        self.assertEqual(catalogue.ILEUM_BELOW_SUBTYPES, ILEUM_BELOW)
        self.assertEqual(COLON_KEEPING | UPPER_SUBTYPES | ILEUM_BELOW | {SUB.OTHER}, ALL_SUBTYPES)
        self.assertEqual(len(COLON_KEEPING) + len(UPPER_SUBTYPES) + len(ILEUM_BELOW) + 1, len(ALL_SUBTYPES))
        self.assertEqual(ILEUM_BELOW, evaluate.ILEUM_BELOW_COLON)
        # each subtype's own ends (R5R-6's principle): every subtype but OTHER names two
        self.assertEqual(dict(evaluate.SUBTYPE_ENDS), SUBTYPE_ENDS)
        self.assertEqual(set(SUBTYPE_ENDS), ALL_SUBTYPES - {SUB.OTHER})

    def test_no_row_holds_an_ileal_pouch_a_whole_colon_beside_a_colon_or_an_anal_canal_per_anus(self):
        # the release set's boundaries the findings rest on, read off the table itself; D336 (1) (b): each row releases
        # on ONE controlled claim - a controlled type, the organ claim of an absence, a controlled subtype - never on
        # joins or on an uncontrolled type
        for family in FAMILIES:
            for row in catalogue.HARMLESS[needs(family)]:
                with self.subTest(family=family, shape=row.shape.value):
                    self.assertIn(row.decided_by, (A.TYPE, A.ORGAN, A.SUBTYPE))
                    self.assertNotIn(AT.ILEAL_POUCH, row.values)
                    if row.decided_by is A.TYPE:
                        self.assertLessEqual(row.values, CONTROLLED_TYPES)
                    if row.decided_by is A.SUBTYPE:
                        self.assertLessEqual(row.values, CONTROLLED_SUBTYPES)
                    if row.shape.value == 'stoma':  # a stoma's organ is never read in the release direction (D330 (d))
                        self.assertEqual((row.values, row.organs), (frozenset({AT.STOMA}), ALL_PLACES))
                    if family in ('COLON', 'RECTUM_AND_SIGMOID', 'COLONIC_STOMA') and row.decided_by is A.ORGAN:
                        self.assertNotIn(LM.COLON, row.values)
                    if family in ('COLON', 'RECTUM_AND_SIGMOID', 'POUCH') and row.decided_by is A.ORGAN:
                        self.assertNotIn(LM.ANAL_CANAL, row.values)


# === the census: every entry shape over the contract's finite vocabularies ============================================

def shape_facts(type_fact, subtype_fact, organ_fact, joins_facts) -> dict:
    out = {}
    if type_fact is not None:
        out[A.TYPE] = (type_fact,)
    if subtype_fact is not None:
        out[A.SUBTYPE] = (subtype_fact,)
    if organ_fact is not None:
        out[A.ORGAN] = (organ_fact,)
    if joins_facts:
        out[A.JOINS] = tuple(joins_facts)
    return out


TYPE_STATES = [('silent', None, ALL_TYPES)] + [(f'{t.value}', sup(t), frozenset({t})) for t in AT]
SUBTYPE_STATES = [('silent', None, ALL_SUBTYPES)] + [(f'{s.value}', sup(s), frozenset({s})) for s in SUB]
ORGAN_STATES = [('silent', None, ALL_PLACES)] + [(f'{place.value}', sup(place), frozenset({place})) for place in LM]
JOIN_REPS = [(), (LM.ILEUM,), (LM.RECTUM,), (LM.POUCH,), (LM.STOMACH,), (LM.ILEUM, LM.COLON), (LM.ILEUM, LM.RECTUM),
             (LM.POUCH, LM.ANAL_CANAL)]


class CensusTests(SimpleTestCase):
    def census(self, shapes):
        """Every shape (label, facts, oracle args) x every route family: the guard's harmless reading equals the declared
        set's. Returns the shapes checked and those the set holds harmless."""
        R0 = bare()
        wrong, checked, harmless = [], 0, 0
        for label, facts, args in shapes:
            R = with_entry(R0, facts)
            for family in FAMILIES:
                expected = oracle_harmless(family, *args)
                if evaluate.harmless(R, Y1, needs(family)) != expected:
                    wrong.append((family, label, expected))
                checked += 1
                harmless += expected
        return wrong, checked, harmless

    def test_every_type_subtype_and_organ_with_the_representative_joins(self):
        shapes = []
        for (tl, tf, tv), (sl, sf, sv), (ol, of, ov), joins in itertools.product(TYPE_STATES, SUBTYPE_STATES, ORGAN_STATES,
                                                                                  JOIN_REPS):
            shapes.append(((tl, sl, ol, tuple(j.value for j in joins)),
                           shape_facts(tf, sf, of, [sup(j) for j in joins]),
                           (tv, sv, sf is None, ov, of is None, tuple(frozenset({j}) for j in joins))))
        wrong, checked, harmless = self.census(shapes)
        self.assertEqual(wrong[:20], [])
        self.assertEqual(checked, 9 * 15 * 51 * len(JOIN_REPS) * 5)
        self.assertTrue(0 < harmless < checked)

    def test_every_joins_list_of_up_to_two_members_over_every_landmark(self):
        lists = [()] + [(place,) for place in LM] + list(itertools.combinations_with_replacement(LM, 2))
        shapes = []
        for (sl, sf, sv), joins in itertools.product(SUBTYPE_STATES, lists):
            shapes.append((('anastomosis', sl, 'silent', tuple(j.value for j in joins)),
                           shape_facts(sup(AT.ANASTOMOSIS), sf, None, [sup(j) for j in joins]),
                           (frozenset({AT.ANASTOMOSIS}), sv, sf is None, ALL_PLACES, True,
                            tuple(frozenset({j}) for j in joins))))
        for tl, tv in (('gastric_pouch', AT.GASTRIC_POUCH), ('surgically_absent', AT.SURGICALLY_ABSENT)):
            for joins in lists[:51]:  # an alteration of another type, its joins of one member
                shapes.append(((tl, 'silent', 'stomach', tuple(j.value for j in joins)),
                               shape_facts(sup(tv), None, sup(LM.STOMACH), [sup(j) for j in joins]),
                               (frozenset({tv}), ALL_SUBTYPES, True, frozenset({LM.STOMACH}), False,
                                tuple(frozenset({j}) for j in joins))))
        wrong, checked, harmless = self.census(shapes)
        self.assertEqual(wrong[:20], [])
        self.assertEqual(checked, (15 * (1 + 50 + 1275) + 2 * 51) * 5)
        self.assertTrue(0 < harmless < checked)

    def test_every_field_state_of_each_rows_representative(self):
        # each field of a representative entry of every row, and of shapes outside every row, in every state the fact
        # pass files (supported, claimed, a contradiction's sides, an established negation, an open denial, silent)
        bases = {  # (type, subtype, organ, joins)
            'absent gallbladder': (AT.SURGICALLY_ABSENT, None, LM.GALLBLADDER, ()),
            'absent cecum': (AT.SURGICALLY_ABSENT, None, LM.CECUM, ()),
            'absent colon': (AT.SURGICALLY_ABSENT, None, LM.COLON, ()),
            'ileocolic [ileum, colon]': (AT.ANASTOMOSIS, SUB.ILEOCOLIC, None, (LM.ILEUM, LM.COLON)),
            'coloanal [pouch, anal canal]': (AT.ANASTOMOSIS, SUB.COLOANAL, None, (LM.POUCH, LM.ANAL_CANAL)),
            'other [ileum]': (AT.ANASTOMOSIS, SUB.OTHER, None, (LM.ILEUM,)),
            'gastrojejunal [stomach, jejunum]': (AT.ANASTOMOSIS, SUB.GASTROJEJUNAL, None, (LM.STOMACH, LM.JEJUNUM)),
            'ileoanal [pouch, anal canal]': (AT.ANASTOMOSIS, SUB.ILEOANAL, None, (LM.POUCH, LM.ANAL_CANAL)),
            'gastric pouch': (AT.GASTRIC_POUCH, None, None, ()),
            'stoma, stomach': (AT.STOMA, None, LM.STOMACH, ()),
            'other alteration, stomach': (AT.OTHER_ALTERATION, None, LM.STOMACH, ()),
        }
        others = {A.TYPE: (AT.STOMA, AT.ILEAL_POUCH, AT.SURGICALLY_ABSENT, AT.GASTRIC_POUCH),
                  A.SUBTYPE: (SUB.ILEOANAL, SUB.COLORECTAL, SUB.GASTROJEJUNAL, SUB.OTHER),
                  A.ORGAN: (LM.COLON, LM.ANAL_CANAL, LM.STOMACH, LM.POUCH, LM.OTHER),
                  A.JOINS: (LM.RECTUM, LM.COLON, LM.ILEUM, LM.STOMACH, LM.OTHER)}
        enums = {A.TYPE: AT, A.SUBTYPE: SUB, A.ORGAN: LM, A.JOINS: LM}
        shapes = []
        for name, (typ, subtype, organ, joins) in bases.items():
            plain = {A.TYPE: (sup(typ), frozenset({typ})),
                     A.SUBTYPE: (sup(subtype), frozenset({subtype})) if subtype else (None, ALL_SUBTYPES),
                     A.ORGAN: (sup(organ), frozenset({organ})) if organ else (None, ALL_PLACES)}
            for attribute in (A.TYPE, A.SUBTYPE, A.ORGAN):
                base_value = typ if attribute is A.TYPE else (subtype if attribute is A.SUBTYPE else organ)
                values = [base_value] if base_value is not None else [others[attribute][0]]
                for label, state, possible in field_states(values, enums[attribute], others[attribute]):
                    fields = dict(plain)
                    fields[attribute] = (state, possible)
                    organ_fact = fields[A.ORGAN][0]
                    shapes.append(((name, attribute.value, label),
                                   shape_facts(fields[A.TYPE][0], fields[A.SUBTYPE][0], organ_fact,
                                               [sup(j) for j in joins]),
                                   (fields[A.TYPE][1], fields[A.SUBTYPE][1], fields[A.SUBTYPE][0] is None,
                                    fields[A.ORGAN][1], organ_fact is None, tuple(frozenset({j}) for j in joins))))
            for position, member in enumerate(joins):
                for label, state, possible in field_states([member], LM, others[A.JOINS]):
                    if state is None:
                        continue  # a member is never silent: an empty list has no member
                    members = [sup(j) for j in joins]
                    members[position] = state
                    sets = [frozenset({j}) for j in joins]
                    sets[position] = possible
                    shapes.append(((name, f'joins[{position}]', label),
                                   shape_facts(plain[A.TYPE][0], plain[A.SUBTYPE][0], plain[A.ORGAN][0], members),
                                   (plain[A.TYPE][1], plain[A.SUBTYPE][1], plain[A.SUBTYPE][0] is None,
                                    plain[A.ORGAN][1], plain[A.ORGAN][0] is None, tuple(sets))))
        wrong, checked, harmless = self.census(shapes)
        self.assertEqual(wrong[:20], [])
        self.assertTrue(0 < harmless < checked)

    def test_every_approach_and_through_state_of_a_per_anus_route(self):
        # the route's own entry is the guard's too (R5R-7, R5R-8): held when the approach is filed or supported as
        # anything but per anus, when its through may name an entry that may be a stoma or a pouch, and - the approach
        # silent - when an entry may be a stoma or a pouch (int6's reading: stoma_possible, pouch_possible). D336 (1) (b)
        # (final check 4): per anus has no control, so an approach supported per anus is read as a silent one is - every
        # approach not established through a control (CONTROLLED_APPROACHES) holds beside an entry that may be a stoma of
        # the lower tract or an ileal pouch
        approaches = {'silent': (None, None)}
        for value in AP:
            approaches[f'{value.value} supported'] = (sup(value), frozenset({value}))
        approaches.update({
            'per anus claimed': (unres(AP.TRANSANAL, UNAPPRAISED), frozenset({AP.TRANSANAL})),
            'oral claimed': (unres(AP.ORAL, UNAPPRAISED), frozenset({AP.ORAL})),
            'per anus or through a stoma': (contra(AP.TRANSANAL, AP.THROUGH_STOMA),
                                            frozenset({AP.TRANSANAL, AP.THROUGH_STOMA})),
            "per anus, a doubt's reading through a pouch": (doubted(AP.TRANSANAL, AP.THROUGH_POUCH),
                                                            frozenset({AP.TRANSANAL, AP.THROUGH_POUCH})),
            'per anus established denied': (neg(AP.TRANSANAL), frozenset(AP)),
            'through a stoma established denied': (neg(AP.THROUGH_STOMA), frozenset(AP)),
            'per anus, an open denial': (open_denial(AP.TRANSANAL), frozenset(AP)),
        })
        entries = {
            'no entry': {},
            'a cholecystectomy (harmless)': {Y2: entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.GALLBLADDER))},
            'an ileocolic anastomosis (harmless)': {Y2: entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.ILEOCOLIC))},
            'a stoma, its organ claimed the ileum': {Y2: entry_of(type=sup(AT.STOMA),
                                                                  organ=unres(LM.ILEUM, UNAPPRAISED))},
            'a stoma, its organ SUPPORTED the stomach': {Y2: entry_of(type=sup(AT.STOMA), organ=sup(LM.STOMACH))},
            'an ileal pouch': {Y2: entry_of(type=sup(AT.ILEAL_POUCH))},
            'an S-pouch filed another alteration of the pouch': {Y2: entry_of(type=sup(AT.OTHER_ALTERATION),
                                                                             organ=sup(LM.POUCH))},
        }
        throughs = {'silent': None, 'Y2 supported': sup(Y2), 'Y2 claimed': unres(Y2, UNAPPRAISED),
                    'Y9 supported (no such entry)': sup(Id.parse('Y9')), 'Y2 or Y3': contra(Y2, Y3),
                    'Y2 established denied': neg(Y2), 'Y2, an open denial': open_denial(Y2)}

        def lower_route_entry(facts) -> bool:
            # an entry whose type may be a stoma, its organ not SUPPORTED at a placed organ outside the colon and the
            # ileum (int6's lower_stoma_possible), or may be an ileal pouch - DECLARED over these entries' states
            value = facts[A.TYPE][0].value
            organ = facts.get(A.ORGAN)
            outside = (organ is not None and organ[0].result is ct.Result.SUPPORTED and organ[0].value not in NO_ORGAN
                       and organ[0].value not in COLON_ALL | lm('ileum', 'terminal_ileum', 'neo_terminal_ileum',
                                                                'small_bowel'))
            return (value is AT.STOMA and not outside) or value is AT.ILEAL_POUCH

        def may_be_stoma_or_pouch(facts) -> bool:
            if facts is None:  # no such entry: a silent type may be anything
                return True
            types = facts.get(A.TYPE)
            organs = facts.get(A.ORGAN)
            type_values = ALL_TYPES if not types else (ALL_TYPES if types[0].result is ct.Result.NEGATED
                                                       else {types[0].value})
            organ_values = set() if not organs else {organs[0].value}
            return bool(type_values & {AT.STOMA, AT.ILEAL_POUCH, AT.GASTRIC_POUCH}) or bool(
                organ_values & {LM.STOMA, LM.POUCH})

        wrong, checked, held = [], 0, 0
        for (a_name, (approach, a_values)), (e_name, anatomy), (t_name, through) in itertools.product(
                approaches.items(), entries.items(), throughs.items()):
            R = per_anus_scope(45331, approach=approach, through=through, entries=anatomy)
            expected = approach is not None and not a_values <= {AP.TRANSANAL}
            controlled = (approach is not None and approach.result is ct.Result.SUPPORTED
                          and approach.value in CONTROLLED_APPROACHES)
            if not controlled:
                expected = expected or any(lower_route_entry(facts) for facts in anatomy.values())
            if through is not None:  # the entries it may name (an entry the FactSet does not hold: anything)
                names = {'Y2 supported': {Y2}, 'Y2 claimed': {Y2}, 'Y9 supported (no such entry)': {Id.parse('Y9')},
                         'Y2 or Y3': {Y2, Y3}}.get(t_name, set(anatomy) | {Y2})
                expected = expected or any(may_be_stoma_or_pouch(anatomy.get(name)) for name in names)
            found = evaluate._anus_route_contradicted(R, X1)
            if found != expected:
                wrong.append((a_name, e_name, t_name, expected))
            checked += 1
            held += expected
        self.assertEqual(wrong, [])
        self.assertEqual(checked, len(approaches) * len(entries) * len(throughs))
        self.assertTrue(0 < held < checked)

    def test_the_route_entry_the_route_itself_uses(self):
        # (i): the stoma or the pouch the session established it entered through - the through's supported entry, or the
        # one entry that may be of the route's type and that a through not established may name; none when that is not
        # one entry; every such entry while the act's session is not established
        stoma = entry_of(type=sup(AT.STOMA), organ=unres(LM.ILEUM, UNAPPRAISED))
        claimed = entry_of(type=unres(AT.STOMA, UNAPPRAISED))
        absent = entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.COLON))
        row = catalogue.lower_route('44382')
        cases = {
            'the through supported naming the stoma': (sup(Y1), {Y1: stoma, Y2: absent}, {Y1}),
            'the through silent, one stoma': (None, {Y1: stoma, Y2: absent}, {Y1}),
            'the through silent, two stomas': (None, {Y1: stoma, Y3: stoma}, set()),
            'the through claimed naming one of two stomas': (unres(Y1, UNAPPRAISED), {Y1: stoma, Y3: stoma}, {Y1}),
            "the through a contradiction's sides, two stomas": (contra(Y1, Y3), {Y1: stoma, Y3: stoma}, set()),
            'the through supported naming an entry of another type': (sup(Y2), {Y1: stoma, Y2: absent}, set()),
            'the through silent, the one stoma only claimed a stoma': (None, {Y1: claimed}, set()),
            'the through established denied, one stoma': (neg(Y1), {Y1: stoma}, set()),
        }
        for name, (through, anatomy, expected) in cases.items():
            with self.subTest(case=name):
                doc = EF.Doc()
                doc.session(1, SK.ENTEROSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                            reached=[sup(EX.ILEUM)], approach=sup(AP.THROUGH_STOMA), through=through)
                doc.anatomy.update(anatomy)
                R = doc.build()
                self.assertEqual(evaluate.route_entries(row, R, X1), frozenset(expected))
                self.assertEqual(evaluate.route_entries(row, R, None),
                                 frozenset(entry for entry, facts in anatomy.items()
                                           if facts.get(A.TYPE)[0].value is AT.STOMA))
        self.assertEqual(evaluate.route_entries(catalogue.lower_route('45380'), bare(), X1), frozenset())

    def test_the_colons_cover_for_every_set_of_absent_parts(self):
        # beside a family needing a colon or a rectum and sigmoid (or a colonic stoma) the colon filed absent by its
        # parts is the colon's shape: held exactly when one reading covers both sides (D327 (1), the D328 addendum's Q2:
        # a side counts as its segments); beside an ileal stoma or a pouch never by the cover
        parts = (LM.CECUM, LM.ASCENDING_COLON, LM.TRANSVERSE_COLON, LM.DESCENDING_COLON, LM.SIGMOID_COLON,
                 LM.RIGHT_COLON, LM.LEFT_COLON, LM.PROXIMAL_COLON, LM.DISTAL_COLON)
        segments = {LM.CECUM: {'c'}, LM.ASCENDING_COLON: {'a'}, LM.TRANSVERSE_COLON: {'t'},
                    LM.DESCENDING_COLON: {'d'}, LM.SIGMOID_COLON: {'s'}, LM.RIGHT_COLON: {'c', 'a'},
                    LM.LEFT_COLON: {'d', 's'}, LM.PROXIMAL_COLON: {'c', 'a', 't'}, LM.DISTAL_COLON: {'d', 's'}}
        both_sides = {'c', 'a', 'd', 's'}
        checked = held = 0
        for size in range(1, 4):
            for chosen in itertools.combinations(parts, size):
                entries = R3F.RD_absences(*chosen)
                R = per_anus_scope(45331, entries=entries)
                covered = set().union(*(segments[place] for place in chosen)) >= both_sides
                for family in FAMILIES:
                    found = evaluate.path_guard(catalogue.LowerRoute(ROUTE_OF[family], needs(family)), R, None)
                    with self.subTest(parts=[place.value for place in chosen], family=family):
                        self.assertEqual(found, covered and family not in WHOLE_COLON_HARMLESS)
                checked += 1
                held += covered
        self.assertTrue(0 < held < checked)


class EndToEndCensusTests(SimpleTestCase):
    def test_a_shape_outside_the_set_holds_every_family_end_to_end(self):
        # the census over the assembled engine (test_assess.run): beside each family's common control, a shape the
        # declared set holds harmless keeps the control's READY and any other holds the code
        organs = (None, LM.GALLBLADDER, LM.OTHER, LM.CECUM, LM.COLON, LM.RECTUM, LM.ANAL_CANAL, LM.ILEUM,
                  LM.TERMINAL_ILEUM, LM.JEJUNUM, LM.STOMACH, LM.POUCH, LM.STOMA)
        subtypes = (None, SUB.ILEOCOLIC, SUB.ILEOANAL, SUB.GASTROJEJUNAL, SUB.OTHER)
        joins = ((), (LM.ILEUM, LM.COLON), (LM.STOMACH, LM.JEJUNUM))
        wrong, checked, ready = [], 0, 0
        for family in FAMILIES:
            for typ, organ, subtype, members in itertools.product(AT, organs, subtypes, joins):
                facts = shape_facts(sup(typ), sup(subtype) if subtype else None, sup(organ) if organ else None,
                                    [sup(j) for j in members])
                R, code, number = family_control(family, {Y7: facts})
                expected = oracle_harmless(family, frozenset({typ}), frozenset({subtype}) if subtype else ALL_SUBTYPES,
                                           subtype is None, frozenset({organ}) if organ else ALL_PLACES, organ is None,
                                           tuple(frozenset({j}) for j in members))
                lower = COLON_ALL | lm('ileum', 'terminal_ileum', 'neo_terminal_ileum', 'small_bowel')
                if (ROUTE_OF[family] is AP.TRANSANAL and typ is AT.STOMA
                        and (organ is None or organ in NO_ORGAN or organ in lower)):
                    expected = False  # D336 (1) (b): per anus has no control - a stoma of the lower tract may be the route
                found = assessed(R, code, number)[0]
                if (found == READY) != expected:
                    wrong.append((family, typ.value, organ and organ.value, subtype and subtype.value,
                                  [j.value for j in members], found))
                checked += 1
                ready += found == READY
        self.assertEqual(wrong[:20], [])
        self.assertTrue(0 < ready < checked)


ROUTE_OF = {'COLON': AP.TRANSANAL, 'RECTUM_AND_SIGMOID': AP.TRANSANAL, 'COLONIC_STOMA': AP.THROUGH_STOMA,
            'ILEAL_STOMA': AP.THROUGH_STOMA, 'POUCH': AP.THROUGH_POUCH}


def family_control(family: str, extra=None, *, approach_silent=False):
    """Each route family's common control (rows_probe.py's, the one int6 was run on): (R, code, act number)."""
    doc = EF.Doc()
    enc = sup(ct.EncounterRelation.THIS_ENCOUNTER)
    stoma = entry_of(type=sup(AT.STOMA), organ=unres(LM.SIGMOID_COLON, UNAPPRAISED))
    if family == 'COLON':
        doc.session(1, SK.COLONOSCOPY, encounter=enc, reached=[sup(EX.CECUM)],
                    approach=None if approach_silent else sup(AP.TRANSANAL))
        code, place = '45380', LM.CECUM
    elif family == 'RECTUM_AND_SIGMOID':
        doc.session(1, SK.FLEX_SIG, encounter=enc, reached=[sup(EX.SIGMOID_COLON)],
                    approach=None if approach_silent else sup(AP.TRANSANAL))
        code, place = '45331', LM.SIGMOID_COLON
    elif family == 'COLONIC_STOMA':
        doc.session(1, SK.COLONOSCOPY, encounter=enc, reached=[sup(EX.CECUM)], approach=sup(AP.THROUGH_STOMA),
                    through=sup(Y1))
        doc.anatomy[Y1] = stoma
        code, place = '44389', LM.TRANSVERSE_COLON
    elif family == 'ILEAL_STOMA':
        doc.session(1, SK.ENTEROSCOPY, encounter=enc, reached=[sup(EX.ILEUM)], approach=sup(AP.THROUGH_STOMA),
                    through=sup(Y1))
        doc.anatomy[Y1] = entry_of(type=sup(AT.STOMA), organ=unres(LM.ILEUM, UNAPPRAISED))
        code, place = '44382', LM.ILEUM
    else:
        doc.session(1, SK.ENTEROSCOPY, encounter=enc, reached=[sup(EX.POUCH)], approach=sup(AP.THROUGH_POUCH),
                    through=sup(Y1))
        doc.anatomy[Y1] = entry_of(type=sup(AT.ILEAL_POUCH))
        code, place = '44386', LM.POUCH
    doc.exam(1)
    doc.act(2, Kind.BIOPSY, places=[sup(place)], device=sup(ct.Device.COLD_FORCEPS))
    doc.anatomy.update(extra or {})
    return doc.build(), code, 2


# === completeness: the guard reads every row of the route table ======================================================

ANASTOMOSIS_SILENT = entry_of(type=sup(AT.ANASTOMOSIS))         # no family's row holds it (the D328 residual)
# D336 (1) (b): an entry only the guard reads - a Roux limb (its type has no control, so no row releases on it; no arm
# reads a Roux limb), so a hold beside it is the guard's own (a silent anastomosis now meets D327 (1)'s arms too, whose
# own hold - LOWER's for 44406 and 44407 - answers before the guard does)
GUARD_ONLY = entry_of(type=sup(AT.ROUX_LIMB))
CHOLECYSTECTOMY = entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.GALLBLADDER))


def met_scope(code: int, extra=None):
    """``code``'s session with its route met (R3F.scope): per anus, the approach supported per anus; through a stoma,
    the through supported naming Y1, a stoma whose organ is SUPPORTED in the colon (a colonic stoma) or the ileum (an
    ileal one); through a pouch, the through naming Y1, an ileal pouch."""
    row = catalogue.lower_route(str(code))
    if row.route is AP.TRANSANAL:
        return scope(code, approach=sup(AP.TRANSANAL), entries=extra)
    if row.route is AP.THROUGH_POUCH:
        return scope(code, approach=sup(AP.THROUGH_POUCH), through=sup(Y1),
                     entries={Y1: entry_of(type=sup(AT.ILEAL_POUCH)), **(extra or {})})
    organ = LM.SIGMOID_COLON if row.needs is catalogue.RouteAnatomy.COLONIC_STOMA else LM.ILEUM
    return scope(code, approach=sup(AP.THROUGH_STOMA), through=sup(Y1),
                 entries={Y1: entry_of(type=sup(AT.STOMA), organ=sup(organ)), **(extra or {})})


def guarded_codes() -> list:
    return sorted(code for code in catalogue.CODES if catalogue.lower_gi(str(code)))


class CompletenessTests(SimpleTestCase):
    def test_the_guard_reads_every_row_of_the_route_table(self):
        # every lower-GI code of the catalogue (every row the route table declares a code of it): its route met, the
        # route row is T; beside an entry no row of its family holds, the table's own hold
        codes = guarded_codes()
        self.assertEqual(len(codes), 50)
        for code in codes:
            with self.subTest(code=code):
                self.assertIsNotNone(catalogue.lower_route(str(code)))
                self.assertEqual(witnesses(route_row(met_scope(code), code)), [])
                found = witnesses(route_row(met_scope(code, {Y7: GUARD_ONLY}), code))
                self.assertIn((ROUTE, A.TYPE, X1, None), found)

    def test_with_no_harmless_row_every_lower_gi_code_holds_beside_any_entry(self):
        # the guard reads the table: emptied, even a cholecystectomy beside any lower-GI code holds it
        from types import MappingProxyType
        empty = MappingProxyType({needs: () for needs in catalogue.RouteAnatomy})
        for code in guarded_codes():
            R = met_scope(code, {Y7: CHOLECYSTECTOMY})
            with self.subTest(code=code):
                self.assertEqual(witnesses(route_row(R, code)), [])
                with mock.patch.object(catalogue, 'HARMLESS', empty):
                    self.assertIn((ROUTE, A.TYPE, X1, None), witnesses(route_row(R, code)))

    def test_the_acts_open_session_holds_only_what_holds_whatever_the_session(self):
        # D312 checker S3's principle: with the act's session not established, an entry no row holds holds the code
        # about the act; an entry that may be the route's own (a stoma, a pouch) is left to the session's answer
        open_session = unres(X1, ct.Reason.GEOMETRY_SECTION)
        for code in guarded_codes():
            row = catalogue.lower_route(str(code))
            with self.subTest(code=code):
                R = scope(code, act_session=open_session, entries={Y7: ANASTOMOSIS_SILENT})
                self.assertIn((ROUTE, A.TYPE, E2, None), witnesses(route_row(R, code)))
                own = AT.STOMA if row.route is AP.THROUGH_STOMA else AT.ILEAL_POUCH
                R = scope(code, act_session=open_session, entries={Y7: entry_of(type=sup(own))})
                if row.route is not AP.TRANSANAL:
                    self.assertNotIn((ROUTE, A.TYPE, E2, None), witnesses(route_row(R, code)))


# === the common inputs: every harmless row keeps them as int6 decides them ===========================================

def claimed_entry(t, organ=None, subtype=None, joins=(), organ_sup=False) -> dict:
    """rows_probe.py's entry: its type supported, its organ, subtype and joins claimed (unappraised), as pass 1 files
    an entry no rule reads."""
    facts = {A.TYPE: (sup(t),)}
    if organ is not None:
        facts[A.ORGAN] = (sup(organ) if organ_sup else unres(organ, UNAPPRAISED),)
    if subtype is not None:
        facts[A.SUBTYPE] = (unres(subtype, UNAPPRAISED),)
    if joins:
        facts[A.JOINS] = tuple(unres(j, UNAPPRAISED) for j in joins)
    return facts


def claimed_args(t, organ=None, subtype=None, joins=(), organ_sup=False) -> tuple:
    """The oracle's reading of a ``claimed_entry``."""
    return (frozenset({t}), frozenset({subtype}) if subtype else ALL_SUBTYPES, subtype is None,
            frozenset({organ}) if organ else ALL_PLACES, organ is None, tuple(frozenset({j}) for j in joins))


# rows_probe.py's representatives (r3h/rules6/scripts/rows_probe.py, its ENTRIES): name -> claimed_entry's arguments
REPRESENTATIVES = {
    'absent gallbladder': (AT.SURGICALLY_ABSENT, LM.GALLBLADDER),
    'absent other (appendix)': (AT.SURGICALLY_ABSENT, LM.OTHER),
    'absent appendiceal orifice': (AT.SURGICALLY_ABSENT, LM.APPENDICEAL_ORIFICE),
    'absent cecum': (AT.SURGICALLY_ABSENT, LM.CECUM),
    'absent sigmoid': (AT.SURGICALLY_ABSENT, LM.SIGMOID_COLON),
    'absent right colon': (AT.SURGICALLY_ABSENT, LM.RIGHT_COLON),
    'absent rectum': (AT.SURGICALLY_ABSENT, LM.RECTUM),
    'absent ileum': (AT.SURGICALLY_ABSENT, LM.ILEUM),
    'absent terminal ileum': (AT.SURGICALLY_ABSENT, LM.TERMINAL_ILEUM),
    'absent jejunum': (AT.SURGICALLY_ABSENT, LM.JEJUNUM),
    'absent anal canal': (AT.SURGICALLY_ABSENT, LM.ANAL_CANAL),
    'absent colon': (AT.SURGICALLY_ABSENT, LM.COLON),
    'absent organ silent': (AT.SURGICALLY_ABSENT,),
    'ileocolic [ileum, colon]': (AT.ANASTOMOSIS, None, SUB.ILEOCOLIC, (LM.ILEUM, LM.COLON)),
    'ileocolic joins silent': (AT.ANASTOMOSIS, None, SUB.ILEOCOLIC),
    'colorectal [colon, rectum]': (AT.ANASTOMOSIS, None, SUB.COLORECTAL, (LM.COLON, LM.RECTUM)),
    'coloanal [pouch, anal canal]': (AT.ANASTOMOSIS, None, SUB.COLOANAL, (LM.POUCH, LM.ANAL_CANAL)),
    'colocolic joins silent': (AT.ANASTOMOSIS, None, SUB.COLOCOLIC),
    'gastrojejunal [stomach, jejunum]': (AT.ANASTOMOSIS, None, SUB.GASTROJEJUNAL, (LM.STOMACH, LM.JEJUNUM)),
    'hepaticojejunal joins silent': (AT.ANASTOMOSIS, None, SUB.HEPATICOJEJUNAL),
    'subtype silent [ileum, colon]': (AT.ANASTOMOSIS, None, None, (LM.ILEUM, LM.COLON)),
    'other [ileum]': (AT.ANASTOMOSIS, None, SUB.OTHER, (LM.ILEUM,)),
    'other [jejunum]': (AT.ANASTOMOSIS, None, SUB.OTHER, (LM.JEJUNUM,)),
    'subtype silent [stomach, duodenum]': (AT.ANASTOMOSIS, None, None, (LM.STOMACH, LM.DUODENUM)),
    'ileoanal [pouch, anal canal]': (AT.ANASTOMOSIS, None, SUB.ILEOANAL, (LM.POUCH, LM.ANAL_CANAL)),
    'ileorectal [ileum, rectum]': (AT.ANASTOMOSIS, None, SUB.ILEORECTAL, (LM.ILEUM, LM.RECTUM)),
    'anastomosis both silent': (AT.ANASTOMOSIS,),
    'other joins silent': (AT.ANASTOMOSIS, None, SUB.OTHER),
    'gastric pouch organ silent': (AT.GASTRIC_POUCH,),
    'roux limb jejunum [stomach, jejunum]': (AT.ROUX_LIMB, LM.JEJUNUM, None, (LM.STOMACH, LM.JEJUNUM)),
    'other alteration stomach': (AT.OTHER_ALTERATION, LM.STOMACH),
    'bypass stomach': (AT.BYPASS, LM.STOMACH),
    'other alteration rectum': (AT.OTHER_ALTERATION, LM.RECTUM),
    'other alteration pouch [ileum, anal canal]': (AT.OTHER_ALTERATION, LM.POUCH, None, (LM.ILEUM, LM.ANAL_CANAL)),
    'stoma organ supported stomach': (AT.STOMA, LM.STOMACH, None, (), True),
    'stoma organ claimed stomach': (AT.STOMA, LM.STOMACH),
    'stoma organ claimed ileum': (AT.STOMA, LM.ILEUM),
    'ileal pouch': (AT.ILEAL_POUCH,),
}
# int6's decision on each harmless representative beside each family's common control (r3h/rules6/out/
# rows_probe-i6.jsonl, run read-only on int6, its manifest equal before and after): READY in every case the declared set
# holds harmless - DECLARED here as the count of such cases per family (the approach filed per anus and, per anus, also
# silent), so a representative the set gains or loses moves this pin
# Round r3's round 6 (DECISIONS D336 (1) (b), r3i/int8): the declared set no longer holds harmless the seven
# representatives whose release rested on an uncontrolled attribute - an anastomosis of silent or OTHER subtype by its
# joins (subtype silent [ileum, colon], [stomach, duodenum]; other [ileum], [jejunum]), a Roux limb, another
# alteration and a bypass by their types - so each family's count falls by seven (moved by the declared set, the
# owner; each of the seven now holds: test_r3i_guard.FindingTests); was COLON 28, R&S 28, COLONIC_STOMA 29,
# ILEAL_STOMA 29, POUCH 25
INT6_READY_HARMLESS = {'COLON': 21, 'RECTUM_AND_SIGMOID': 21, 'COLONIC_STOMA': 22, 'ILEAL_STOMA': 22, 'POUCH': 18}


class CommonInputTests(SimpleTestCase):
    def test_every_harmless_row_keeps_the_common_controls_as_int6_decides_them(self):
        # READY, as int6 decides each - but, the per-anus approach silent, a stoma whose organ is not established holds
        # the code with the approach's question (int6 for the colonoscopy family; D330 (d)'s recorded limit, R5R-5, for
        # the sigmoidoscopy family, which rules5's arm holds and int6 READYs)
        counts = {}
        for family in FAMILIES:
            for silent in ((False, True) if family in ('COLON', 'RECTUM_AND_SIGMOID') else (False,)):
                for name, args in REPRESENTATIVES.items():
                    if not oracle_harmless(family, *claimed_args(*args)):
                        continue
                    R, code, number = family_control(family, {Y7: claimed_entry(*args)}, approach_silent=silent)
                    limit = silent and args[0] is AT.STOMA and not (args[4:] and args[4])
                    # D336 (1) (b) (final check 4): per anus has no control, so a stoma whose organ is not SUPPORTED
                    # outside the lower tract may be the route - the guard's own hold beside a supported per-anus approach
                    per_anus_stoma = (not silent and family in ('COLON', 'RECTUM_AND_SIGMOID') and args[0] is AT.STOMA
                                      and not (args[4:] and args[4]))
                    with self.subTest(family=family, approach='silent' if silent else 'per anus', entry=name):
                        self.assertEqual(assessed(R, code, number), (HELD, ('reading_unknown',)) if limit
                                         else (HELD, (ROUTE,)) if per_anus_stoma else (READY, ()))
                    if not silent:
                        counts[family] = counts.get(family, 0) + 1
        self.assertEqual(counts, INT6_READY_HARMLESS)

    def test_the_common_inputs_end_to_end(self):
        # D328 (1) (c)'s common inputs, the development set's right hemicolectomy filing, entries outside the lower GI
        # tract (a cholecystectomy beside a lower EUS per anus) and a surgically absent appendix: READY, as int6
        E = R3F.r3e()
        for name in ('g8 an ordinary colonoscopy to the cecum', 'g8b an ordinary colonoscopy to the terminal ileum',
                     'g8c a sigmoid colectomy with a colorectal anastomosis, to the cecum',
                     'g8d a transverse colectomy with a colocolic anastomosis, to the terminal ileum',
                     'g9 a through-stoma colonoscopy, the colostomy to the cecum (the attacker control b)',
                     'g9b a through-stoma colonoscopy after a Hartmann procedure, to the cecum',
                     'g7 a right hemicolectomy to the neo-terminal ileum, the subtype filed'):
            text, data, (code, quote) = E.AS_BEFORE[name]
            with self.subTest(case=name):
                self.assertEqual(R3F.statuses(text, data, (code, quote))[code], (READY, ()))
        for name in ('e5-control-lower-eus-cecum', 'l1-rectal-eus-chole', 'l2-colonic-eus-chole',
                     'e7-colostomy-eus-as-45391', 'e9-colostomy-eus-cecum-fna'):
            (text, data), codes = R3F.EUS_CASES[name]
            code = {'e7-colostomy-eus-as-45391': '44406', 'e9-colostomy-eus-cecum-fna': '44407'}.get(name, codes[0][0])
            with self.subTest(case=name):
                self.assertEqual(R3F.statuses(text, data, (code, dict(codes)[code]))[code], (READY, ()))
        sig = R3F.sig_note('Screening; no prior surgery.', R3F.F_SIG, R3F.SIGMOID_BX, anatomy=[],
                           reached=[('sigmoid_colon', 'advanced to the sigmoid colon')], place='sigmoid_colon',
                           place_words='sigmoid colon')
        lar = R3F.sig_note(R3F.LAR, R3F.F_LAR, R3F.SIG_BX,
                           anatomy=[('Y1', 'surgically_absent', 'Low anterior resection', 'sigmoid_colon', None, []),
                                    ('Y2', 'anastomosis', 'colorectal anastomosis', None, 'colorectal',
                                     ['colon', 'rectum'])],
                           reached=[('stated_depth', 'to 30 cm')], place='anastomosis', place_words='anastomosis')
        for name, (text, data), quote in (('a sigmoidoscopy per anus', sig, R3F.SIGMOID_BX),
                                          ('a sigmoidoscopy per anus after a low anterior resection', lar, R3F.SIG_BX)):
            with self.subTest(case=name):
                self.assertEqual(R3F.statuses(text, data, ('45331', quote))['45331'], (READY, ()))
        for organ in ('other', 'appendiceal_orifice'):  # an appendectomy, filed with no appendix landmark
            case = note('Appendectomy in 2010.', FC, BX_CECUM, kind='colonoscopy', kind_words='colonoscope',
                        approach=PER_ANUS, reached=CECUM, anatomy=[('Y1', 'surgically_absent', 'Appendectomy', [organ],
                                                                    [], [])], place='cecum', place_words='cecum')
            with self.subTest(appendix=organ):
                self.assertEqual(status(case, '45380', BX_CECUM), (READY, ()))


# === constructed variants per route family (beyond the findings) =====================================================

def absent(organ):
    return entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(organ))


def anastomosis(*joins, subtype=None):
    return entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(subtype) if subtype else None,
                    joins=tuple(sup(j) for j in joins))


STOMA_CLAIMED = entry_of(type=sup(AT.STOMA), organ=unres(LM.STOMACH, UNAPPRAISED))
LOOP_ILEOSTOMY = entry_of(type=sup(AT.STOMA), organ=unres(LM.ILEUM, UNAPPRAISED))
POUCH = entry_of(type=sup(AT.ILEAL_POUCH))
WHIPPLE = {Y3: anastomosis(LM.PANCREAS, LM.JEJUNUM, subtype=SUB.PANCREATICOJEJUNAL),
           Y5: anastomosis(LM.BILE_DUCT, LM.JEJUNUM, subtype=SUB.HEPATICOJEJUNAL),
           Y7: anastomosis(LM.STOMACH, LM.JEJUNUM, subtype=SUB.GASTROJEJUNAL)}
GASTRIC_BYPASS = {Y3: entry_of(type=sup(AT.GASTRIC_POUCH), organ=sup(LM.STOMACH)),
                  Y5: anastomosis(LM.POUCH, LM.JEJUNUM, subtype=SUB.GASTROJEJUNAL)}
# family -> {variant: (extra entries, READY or HELD)}; each per family's common control (family_control)
VARIANTS = {
    'COLON': {
        'an ileal resection (the ileum absent)': ({Y7: absent(LM.ILEUM)}, READY),
        # D336 (1) (b): no row releases on joins (an uncontrolled attribute), so its silent subtype decides nothing
        'a jejunocolic anastomosis its joins name, its subtype silent': ({Y7: anastomosis(LM.JEJUNUM, LM.COLON)},
                                                                         HELD),
        # D336 (1) (b): the pancreaticojejunal subtype has no control, so it never decides a release
        'a Whipple procedure (three upper anastomoses)': (WHIPPLE, HELD),
        # D336 (1) (b): another alteration's type has no control, so it never decides a release (L8-4's recorded cost)
        'a gastric band (another alteration of the stomach)': (
            {Y7: entry_of(type=sup(AT.OTHER_ALTERATION), organ=sup(LM.STOMACH))}, HELD),
        'a repaired rectal fistula (another alteration of the rectum)': (
            {Y7: entry_of(type=sup(AT.OTHER_ALTERATION), organ=sup(LM.RECTUM))}, HELD),
        'a bypass of the colon': ({Y7: entry_of(type=sup(AT.BYPASS), organ=sup(LM.COLON))}, HELD),
        'an anastomosis of another pair, its joins silent': ({Y7: anastomosis(subtype=SUB.OTHER)}, HELD),
        # D336 (1) (b) (final check 4): per anus has no control, so beside a stoma whose organ pass 1 only claimed the
        # route is never established per anus (R5R-5's class with the approach supported)
        'a gastrostomy beside the route per anus (D310 (1)), its organ claimed': ({Y7: STOMA_CLAIMED}, HELD),
    },
    'RECTUM_AND_SIGMOID': {
        'a total colectomy (the colon absent)': ({Y7: absent(LM.COLON)}, HELD),
        'the right and the left colon absent (the cover)': ({Y5: absent(LM.RIGHT_COLON), Y7: absent(LM.LEFT_COLON)},
                                                            HELD),
        'an IRA (the colon absent, an ileorectal anastomosis)': (
            {Y5: absent(LM.COLON), Y7: anastomosis(LM.ILEUM, LM.RECTUM, subtype=SUB.ILEORECTAL)}, HELD),
        'an appendectomy (other absent)': ({Y7: absent(LM.OTHER)}, READY),
        'an ultralow anterior resection (the rectum absent, a coloanal anastomosis)': (
            {Y5: absent(LM.RECTUM), Y7: anastomosis(LM.COLON, LM.ANAL_CANAL, subtype=SUB.COLOANAL)}, READY),
        'a Whipple procedure (its pancreaticojejunal subtype uncontrolled, D336 (1) (b))': (WHIPPLE, HELD),
        'an S-pouch filed another alteration of the pouch': (
            {Y7: entry_of(type=sup(AT.OTHER_ALTERATION), organ=sup(LM.POUCH))}, HELD),
        'a cholecystectomy and a gastric bypass': ({Y1: CHOLECYSTECTOMY, **GASTRIC_BYPASS}, READY),
    },
    'COLONIC_STOMA': {
        'an abdominoperineal resection (the rectum and the anal canal absent)': (
            {Y5: absent(LM.RECTUM), Y7: absent(LM.ANAL_CANAL)}, READY),
        'an ileal pouch beside the colostomy': ({Y7: POUCH}, HELD),
        'a second stoma beside the stoma the route uses': ({Y7: STOMA_CLAIMED}, READY),
        'a cholecystectomy': ({Y7: CHOLECYSTECTOMY}, READY),
        'an anastomosis whose subtype and joins are silent': ({Y7: ANASTOMOSIS_SILENT}, HELD),
        'another alteration of the colon': ({Y7: entry_of(type=sup(AT.OTHER_ALTERATION), organ=sup(LM.COLON))},
                                            HELD),
        'a right hemicolectomy (an ileocolic anastomosis, the right colon absent)': (
            {Y5: absent(LM.RIGHT_COLON), Y7: anastomosis(LM.ILEUM, LM.COLON, subtype=SUB.ILEOCOLIC)}, READY),
    },
    'ILEAL_STOMA': {
        'a proctocolectomy (the colon and the rectum absent)': ({Y5: absent(LM.COLON), Y7: absent(LM.RECTUM)}, READY),
        'an ileal pouch beside the ileostomy': ({Y7: POUCH}, HELD),
        'an IRA beside the ileostomy': ({Y7: anastomosis(LM.ILEUM, LM.RECTUM, subtype=SUB.ILEORECTAL)}, HELD),
        'the ileum absent': ({Y7: absent(LM.ILEUM)}, HELD),
        'the terminal ileum absent': ({Y7: absent(LM.TERMINAL_ILEUM)}, READY),
        'a cholecystectomy': ({Y7: CHOLECYSTECTOMY}, READY),
        'the anal canal absent': ({Y7: absent(LM.ANAL_CANAL)}, READY),
        'an organ absent, its organ silent': ({Y7: entry_of(type=sup(AT.SURGICALLY_ABSENT))}, HELD),
    },
    'POUCH': {
        'an IPAA (the colon and the rectum absent, the pouch-anal join)': (
            {Y3: absent(LM.COLON), Y5: absent(LM.RECTUM),
             Y7: anastomosis(LM.POUCH, LM.ANAL_CANAL, subtype=SUB.ILEOANAL)}, READY),
        'a diverting loop ileostomy (its organ claimed)': ({Y7: LOOP_ILEOSTOMY}, READY),
        'a colorectal anastomosis beside the pouch': ({Y7: anastomosis(LM.COLON, LM.RECTUM, subtype=SUB.COLORECTAL)},
                                                      HELD),
        'the anal canal absent': ({Y7: absent(LM.ANAL_CANAL)}, HELD),
        'a gastric bypass': (GASTRIC_BYPASS, READY),
        'a second ileal pouch': ({Y7: POUCH}, HELD),
        'an anastomosis whose subtype and joins are silent': ({Y7: ANASTOMOSIS_SILENT}, HELD),
    },
}


class VariantTests(SimpleTestCase):
    def test_the_constructed_variants_per_route_family(self):
        for family, variants in VARIANTS.items():
            self.assertGreaterEqual(len(variants), 6, family)
            for name, (entries, expected) in variants.items():
                R, code, number = family_control(family, entries)
                with self.subTest(family=family, variant=name):
                    found = assessed(R, code, number)
                    self.assertEqual(found[0], expected)
                    if expected == HELD:
                        self.assertIn(ROUTE, found[1])
                        self.assertEqual(serving(asking.plan(R, ()), code), [])

    def test_the_lower_eus_codes_read_the_guard_as_their_family(self):
        # 45391 (a colon to traverse), 45341 (a rectum and sigmoid) per anus and 44406 (a colonic stoma) in LOWER's row
        cases = {
            45391: {'a cholecystectomy': ({Y7: CHOLECYSTECTOMY}, []),
                    'the anal canal absent': ({Y7: absent(LM.ANAL_CANAL)}, [(ROUTE, A.TYPE, X1, None)]),
                    'an anastomosis whose subtype and joins are silent': ({Y7: ANASTOMOSIS_SILENT},
                                                                         [(ROUTE, A.TYPE, X1, None)])},
            45341: {'an appendectomy': ({Y7: absent(LM.OTHER)}, []),
                    'the colon absent': ({Y7: absent(LM.COLON)}, [(ROUTE, A.TYPE, X1, None)]),
                    # D336 (1) (b) (final check 4): the per-anus approach has no control, so a stoma may be the route
                    'a stoma beside the route per anus, its organ claimed': ({Y7: STOMA_CLAIMED},
                                                                            [(ROUTE, A.TYPE, X1, None)]),
                    'an ileorectal anastomosis': ({Y7: anastomosis(LM.ILEUM, LM.RECTUM, subtype=SUB.ILEORECTAL)},
                                                  [(ROUTE, A.TYPE, X1, None)])},
            44406: {'a cholecystectomy': ({Y7: CHOLECYSTECTOMY}, []),
                    'an ileal pouch': ({Y7: POUCH}, [(ROUTE, A.TYPE, X1, None)])},
        }
        for code, variants in cases.items():
            for name, (entries, expected) in variants.items():
                with self.subTest(code=code, variant=name):
                    self.assertEqual(witnesses(route_row(met_scope(code, entries), code)), expected)

    def test_only_an_established_other_route_leaves_its_class_to_explain_it(self):
        # an ileoscopy whose session's approach is SUPPORTED as another route (oral) is held by the enteroscopy class's
        # explanation - the guard adds nothing, so the item stays that explanation; an approach only CLAIMED oral, or the
        # route's own, reads every entry: an ileal pouch beside holds with the table's own hold
        stoma = entry_of(type=sup(AT.STOMA), organ=sup(LM.ILEUM))
        for approach, guard in ((sup(AP.ORAL), False), (unres(AP.ORAL, UNAPPRAISED), True),
                                (sup(AP.THROUGH_STOMA), True), (sup(AP.TRANSANAL), False)):
            R = scope(44382, approach=approach, through=sup(Y1), entries={Y1: stoma, Y7: POUCH})
            with self.subTest(approach=(approach.value.value, approach.result.value)):
                self.assertEqual(evaluate.path_guard(catalogue.lower_route('44382'), R, X1), guard)
                self.assertEqual((ROUTE, A.TYPE, X1, None) in witnesses(route_row(R, 44382)), guard)
                found = assessed(R, '44382')
                self.assertEqual(found[0], HELD)


# === P-MONO: no 9.4 weakening releases a scene the guard holds ========================================================


class MonotonicityTests(SimpleTestCase):
    def test_no_weakening_releases_a_code_the_guard_holds(self):
        TP = R3F.properties()
        scenes = {
            '45331, the colon absent': family_control('RECTUM_AND_SIGMOID', {Y7: absent(LM.COLON)}),
            '45380, the anal canal absent': family_control('COLON', {Y7: absent(LM.ANAL_CANAL)}),
            '45380, an oral approach': (per_anus_scope(45380, approach=sup(AP.ORAL)), '45380', 2),
            '45331, a through naming a stoma': (per_anus_scope(45331, through=sup(Y5), entries={Y5: STOMA_CLAIMED}),
                                                '45331', 2),
            '44382, an ileal pouch beside': family_control('ILEAL_STOMA', {Y7: POUCH}),
            '44382, a jejunostomy': (ileoscopy(unres(LM.JEJUNUM, UNAPPRAISED)), '44382', 2),
            '44389, an anastomosis both silent': family_control('COLONIC_STOMA', {Y7: ANASTOMOSIS_SILENT}),
            '44386, a colorectal anastomosis beside': family_control(
                'POUCH', {Y7: anastomosis(LM.COLON, LM.RECTUM, subtype=SUB.COLORECTAL)}),
        }
        for name, (R, code, _number) in scenes.items():
            self.assertTrue(evaluate.decide(code, (), R).held_facts, name)
            count = 0
            for label, weak, _what in TP.weakenings(R):
                count += 1
                with self.subTest(case=name, weakening=label):
                    self.assertTrue(evaluate.decide(code, (), weak).held_facts)
                    if evaluate._session(weak, E2) is not None:
                        self.assertIsNot(route_row(weak, int(code)).truth, evaluate.Truth.T)
            self.assertGreater(count, 10, name)


# === D330 (1) (a): the route table's row in requirements_of, so gate 6 generates its cases ==========================

APART = (44380, 44381, 44382, 44384, 44385, 44386, 45330, 45331, 45332, 45333, 45334, 45335, 45337, 45338, 45340,
         45346, 45347, 45349, 45350)   # DECLARED: the lower-GI codes whose route row is neither COLFULL nor LOWER


class RequirementsTests(SimpleTestCase):
    def test_requirements_of_lists_the_route_table_where_it_stands_apart(self):
        from studio.interpretation.engine.requirements_table import Tag
        for code in sorted(catalogue.CODES):
            listed = RQ.requirements_of(str(code))
            with self.subTest(code=code):
                self.assertEqual(RQ.Requirement.ROUTE_TABLE in listed, code in APART)
                self.assertEqual(RQ.route_row_apart(str(code)), code in APART)
                if code in APART:
                    spec = RQ.spec(str(code))
                    self.assertEqual(listed, (*RQ.TEMPLATE_HEAD[spec.template], *spec.tags, RQ.Requirement.ROUTE_TABLE,
                                              *RQ.TEMPLATE_TAIL[spec.template]))
                    self.assertTrue({Tag.COLFULL, Tag.LOWER}.isdisjoint(spec.tags))
                # its reads once, in requirements_of's order where listed, else appended (a lower-GI code)
                plain = tuple(read for requirement in listed for read in RQ.RULES[requirement].reads_for(
                    RQ.spec(str(code)).template))
                extra = (RQ.RULES[RQ.Requirement.ROUTE_TABLE].reads_for(RQ.spec(str(code)).template)
                         if catalogue.lower_gi(str(code)) and code not in APART else ())
                self.assertEqual(RQ.reads_of(str(code)), plain + extra)

    def test_the_route_table_reads_the_reach_to_hold_only(self):
        reads = {(read.role, read.attribute): read.paths for read in RQ.RULES[RQ.Requirement.ROUTE_TABLE].reads}
        self.assertEqual(reads[(RQ.Role.SESSION, A.REACHED)], {RQ.Path.HOLD})
        for code in APART:
            self.assertIn(A.REACHED, RQ.dependencies(str(code)).reads[RQ.Role.SESSION])

    def test_gate_6_generates_the_route_tables_cases(self):
        from tests.v2 import test_gate6 as G
        cases = {(case['code'], case['requirement'], case['state']): case['expect'] for case in G.committed()['cases']}
        for code in APART:
            route = catalogue.lower_route(str(code)).route
            with self.subTest(code=code):
                self.assertEqual(cases[(str(code), 'route table', 'T')]['status'], READY)
                self.assertEqual((cases[(str(code), 'route table', 'U')]['status'],
                                  cases[(str(code), 'route table', 'U')]['item']), (HELD, 'procedure'))
                found = cases[(str(code), 'route table', 'F')]
                if route is AP.TRANSANAL:
                    self.assertEqual((found['status'], found['item'], found['item_kind']),
                                     (HELD, 'procedure', 'explanation'))
                else:
                    self.assertIsNone(found)
