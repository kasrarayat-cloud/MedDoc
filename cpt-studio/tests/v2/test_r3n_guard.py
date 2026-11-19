"""Round r3's round 7 fixes, the last round's repair (DECISIONS D344, D345 (1)-(3); build-v2/a2b/r3b/r3n/int10/NOTES.md):
A FILED FIELD NAMES ITS SHAPE IN EVERY FIELD AND EVERY READER, and THE ROUTE'S OWN ENTRY IS THE ENTRY THE THROUGH NAMES.
TEXT-ONLY and SYNTHETIC: every note is written for these tests or is the sixth adversarial pass's or the final check's
constructed input word for word (r3m/attack: the L6 oracle lens's e2e_a.py, test_l9r_refute.py, test_l4p9_refute.py and
the verifiers' scripts; r3m/final-check/probes: through_peg.py, through_other_type.py; fictional clinicians), every
pass-1 answer is built by hand with test_settle's builders and every pass-2 answer by test_r2cl_lesion's faithful oracle,
every other FactSet in code; nothing is sent.

The rule (D345):
- (1) an entry whose ORGAN or a JOINS member may be Landmark.STOMA (the D342 (1) (a) predicate) may be a stoma; at
  Landmark.POUCH it may be an ileal pouch - for every reader of an entry's possible shape (evaluate.made_shapes, one rule
  over the entry's fields: the per-anus stoma and pouch arms, lower_stoma_possible, the colonic and ileal stoma readers,
  the harmless rows, R5R-8). The one exception: a subtype established that itself defines that place - a colonic
  J-pouch's (colorectal, coloanal) or an ileal pouch's own join's (ileorectal, ileoanal) pouch, an upper join's own
  gastric pouch or anastomotic stoma;
- (2) the route's own entry is the entry the session's through names, its established type giving the route: when the
  through may name an entry that cannot be of the route's type, or an id with no entry, the route is not certain and
  reads at its widest - every entry that may be of the route's type is a candidate own entry (the own entry's fields,
  the colonic stoma's organ clause) and, with none established as the route's type, the route holds; the arms never take
  another entry than the SUPPORTED through's as the route's own;
- (3) the censuses are derived, never hand-listed.

- FindingTests: L6M-1 (confirmed), L9R-1 (low on verification), L4P9-1 and the final check's finding 1 (its class), each
  on its own input: RED on int9 (8adce6fb; r3n/int10/red/), GREEN on int10 - held, with an existing reason.
- ReadClaimsCensusTests: every claim a harmless row reads, DERIVED from catalogue.HARMLESS, x settle's whole outcome
  table x every route family, against the declared release set (test_r3g_rules.oracle_harmless, declared from the
  rulings); its completeness test.
- RouteThroughCensusTests: the session's through over every entry type, every settled state and none (an id with no
  entry), beside an entry of the route's type outside its anatomy, for every through family and LOWER's stoma class:
  the readers of (2) against the ruling declared here; and end to end on the deciding states.
- RouteOwnFieldCensusTests: each through family's own entry's organ, subtype and joins over settle's whole outcome table
  and its two-member joins over EVERY landmark pair, against the declared own anatomy.
- FieldCensusTests: every field (organ, each joins member, subtype) x every Landmark, the stoma and the pouch included,
  x every settled state x every route family (per anus, its EUS classes, through a stoma, its EUS class, through a
  pouch), against the ruling declared here (never the code's output); completeness.
- CombinationCensusTests: the combinations the one-field censuses left out, found by the mutation proof (NOTES section
  6): every reader over an entry's organ and a joins member TOGETHER (one landmark of every class the readers
  distinguish, derived), and the route's own entry's TYPE in every settled state beside the through naming it, an entry
  of every type, an id with no entry or nothing (the hold with no candidate established; the entry asked).
"""
from __future__ import annotations

import itertools
from dataclasses import replace

from django.test import SimpleTestCase

from studio.interpretation.contract import claims as CL
from studio.interpretation.contract import settle
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import catalogue, evaluate
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine.types import Id
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_r2cl_lesion as R2CL
from tests.v2 import test_r3f_rules as R3F
from tests.v2 import test_r3g_rules as G
from tests.v2 import test_r3m_guard as M
from tests.v2.test_settle import answer, event, fact, frame, labelled, opening, session, src

A, LM, EX, AT, AP, SUB, Res, FS, RS = (ct.Attribute, ct.Landmark, ct.Extent, ct.AnatomyType, ct.Approach,
                                       ct.AnastomosisSubtype, ct.Result, ct.FactState, ct.Reason)
sup, unres, neg, contra = EF.sup, EF.unres, EF.neg, EF.contra
UN = RS.UNAPPRAISED
X1 = Id.parse('X1')
Y1, Y2, Y5, Y7, Y9 = (Id.parse(f'Y{n}') for n in (1, 2, 5, 7, 9))
HELD, READY, ROUTE = G.HELD, G.READY, G.ROUTE
entry_of = R3F.entry_of
ALL_PLACES, ALL_SUBTYPES, ALL_TYPES = frozenset(LM), frozenset(SUB), frozenset(AT)


def assessed(R, code, number=2) -> tuple:
    return G.assessed(R, str(code), number)


def held(test, found, label=''):
    test.assertEqual(found[0], HELD, label)


# === DECLARED from the rulings (never read from engine/evaluate or engine/catalogue) ===================================

# D345 (1): the made places a filed field names as a shape, and the one exception (test_r3g_rules' declaration)
MADE, DEFINED = G.MADE_SHAPES, G.DEFINED_PLACES
LOWER_STOMA = G.COLON_ALL | G.lm('ileum', 'terminal_ileum', 'neo_terminal_ileum', 'small_bowel')
ILEAL = G.lm('ileum', 'terminal_ileum', 'neo_terminal_ileum', 'small_bowel')
# D342 (1) (c): each through family's own anatomy (type, organs, subtypes, joins)
OWN = {'COLONIC_STOMA': (AT.STOMA, LOWER_STOMA, frozenset(), LOWER_STOMA),
       'ILEAL_STOMA': (AT.STOMA, ILEAL, frozenset(), ILEAL),
       'POUCH': (AT.ILEAL_POUCH, ILEAL | G.lm('pouch'), G.ILEUM_BELOW, G.POUCH_JOINS)}
THROUGH_CODES = {'COLONIC_STOMA': ('44389', '44407'), 'ILEAL_STOMA': ('44382',), 'POUCH': ('44386',)}
# every route family's codes the field census reads end to end: per anus (the colonoscopy, its colonoscopic EUS; the
# sigmoidoscopy, its sigmoidoscopic EUS), through a stoma (the colonoscopy, LOWER's stoma class 44407; the ileoscopy),
# through a pouch
FAMILY_CODES = {'COLON': ('45380', '45392'), 'RECTUM_AND_SIGMOID': ('45331', '45342'),
                'COLONIC_STOMA': ('44389', '44407'), 'ILEAL_STOMA': ('44382',), 'POUCH': ('44386',)}


def declared_values(found, enum, decides):
    """D342 (1) (a), DECLARED: what a filed field in a settled state may be - the claimed value where it decides (an
    established or unappraised SUPPORTED claim), every value of its enumeration otherwise (the anatomy entry's
    hold-only rule: an established negation names no value, so it may be any)."""
    return frozenset({found.value}) if decides else frozenset(enum)


def possibly_values(found, enum):
    """facts.possibly's reading of a settled field, DECLARED from FINAL-V2 4.2: its supported value; none for an
    established negation; every value for a negated claim not established (RD-3); else its claimed value and options."""
    if found.result is Res.SUPPORTED:
        return frozenset({found.value})
    if found.result is Res.NEGATED:
        return frozenset()
    if found.state is FS.NEGATED:
        return frozenset(enum)
    return frozenset(v for v in (found.value, *found.options) if v is not None)


def declared_made(field_values, subtypes, subtype_silent) -> frozenset:
    """D345 (1), DECLARED: the shapes the filed fields' values name, but a place every subtype value defines."""
    named = {place for place in MADE for values in field_values if place in values}
    defined = (frozenset.intersection(*(DEFINED.get(value, frozenset()) for value in subtypes))
               if not subtype_silent and subtypes else frozenset())
    return frozenset(MADE[place] for place in named - defined)


def states_of(value, control, other):
    """settle's whole outcome table for a claim at ``value`` (test_r3m_guard.settled_states, derived from settle itself),
    one engine Fact per distinct outcome: (label, row, fact, decides)."""
    seen = {}
    for label, row, found, decides in M.settled_states(value, control, other):
        if found in seen:
            assert seen[found][2] == decides, (label, seen[found])
            continue
        seen[found] = (label, row, decides)
    return [(label, row, found, decides) for found, (label, row, decides) in seen.items()]


# === the findings ======================================================================================================

HEAD = G.HEAD
ACT_CECUM = 'Two biopsies of the cecum were taken with cold forceps.'
ACT_SIG = 'Two biopsies of the sigmoid colon were taken with cold forceps.'


def l6_note(history, findings, act, *, kind, kind_words, anatomy, approach=None, through=None, reached=(), place,
            place_words, reached_anatomy=None):
    """The L6 oracle lens's e2e.note, word for word: anatomy [(id, type, type words, [(organ, words)], [(subtype, words)],
    [(join, words)])], each fact cited in S4; approach, through and reached_anatomy (value, words) cited in S5."""
    text = HEAD + f'History: {history}\n' + f'Findings: {findings}\n' + f'{act}\n'
    entries = [{'id': yid, 'type': fact(typ, src(['S4'], tw)),
                'organ': [fact(v, src(['S4'], w)) for v, w in organs],
                'subtype': [fact(v, src(['S4'], w)) for v, w in subtypes],
                'joins': [fact(v, src(['S4'], w)) for v, w in joins]}
               for yid, typ, tw, organs, subtypes, joins in anatomy]
    fields = dict(examination=[fact('E1', src(['S5']))], encounter=[fact('this_encounter', frame(['S2']))],
                  approach=[fact(approach[0], src(['S5'], approach[1]))] if approach else [],
                  through=[fact(through[0], src(['S5'], through[1]))] if through else [],
                  reached=[fact(v, src(['S5'], w)) for v, w in reached])
    if reached_anatomy:
        fields['reached_anatomy'] = [fact(reached_anatomy[0], src(['S5'], reached_anatomy[1]))]
    sess = session('X1', fact(kind, src(['S5'], kind_words)), **fields)
    status_words = 'was inserted' if 'was inserted' in findings else 'was advanced'
    events = [event('E1', ['S5'], kind_words, status_words, 'examination', session=[fact('X1', src(['S5']))]),
              event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                    target__places=[fact(place, src(['S6'], place_words))],
                    technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])]
    data = answer(sections=[opening(), labelled('N1', 'S4', 'History:', 'history'),
                            labelled('N2', 'S5', 'Findings:', 'findings')],
                  sessions=[sess], anatomy=entries, events=events)
    return text, data


def colo(organ, sub, sub_words, hist, approach=True, extra=()):
    """e2e_a.colo, word for word: a colonoscopy to the cecum whose reached_anatomy names the anastomosis Y1."""
    findings = ('The colonoscope was inserted per anus, advanced to the anastomosis and to the cecum.' if approach else
                'The colonoscope was advanced to the anastomosis and to the cecum.')
    return l6_note(hist, findings, ACT_CECUM, kind='colonoscopy', kind_words='colonoscope',
                   anatomy=[('Y1', 'anastomosis', sub_words, [(organ, 'stoma' if organ in ('stoma',) else organ)]
                             if organ else [], [(sub, sub_words)], [])] + list(extra),
                   approach=('transanal', 'inserted per anus') if approach else None,
                   reached=[('cecum', 'to the cecum')], reached_anatomy=('Y1', 'to the anastomosis'),
                   place='cecum', place_words='cecum')


def flex(organ, hist, approach=True, extra=()):
    """e2e_a.flex, word for word: a flexible sigmoidoscopy to the anastomosis in the sigmoid colon (reached_anatomy Y1)."""
    findings = ('The flexible sigmoidoscope was inserted per anus and advanced to the anastomosis in the sigmoid colon.'
                if approach else 'The flexible sigmoidoscope was advanced to the anastomosis in the sigmoid colon.')
    return l6_note(hist, findings, ACT_SIG, kind='flex_sig', kind_words='flexible sigmoidoscope',
                   anatomy=[('Y1', 'anastomosis', 'colorectal anastomosis', [(organ, 'stoma')] if organ else [],
                             [('colorectal', 'colorectal anastomosis')], [])] + list(extra),
                   approach=('transanal', 'inserted per anus') if approach else None,
                   reached=[('sigmoid_colon', 'in the sigmoid colon')], reached_anatomy=('Y1', 'to the anastomosis'),
                   place='sigmoid_colon', place_words='sigmoid colon')


def outcome(case, code, quote):
    text, data = case
    return R2CL.outcomes(text, data, R2CL.FAITHFUL, (code, quote))[code][:2]


H1 = 'Right hemicolectomy with an ileocolic anastomosis and an end ileostomy stoma in 2029.'
H2 = 'Low anterior resection with a colorectal anastomosis and a diverting loop stoma in 2029.'
H3 = 'Ileocolic resection with an ileocolic anastomosis into a pouch in 2029.'


def per_anus_codes():
    return [code for code in G.guarded_codes() if catalogue.lower_route(str(code)).route is AP.TRANSANAL]


# The L6M-1 shapes (FactSet level; the organ has no claim form, so as pass 1 files it, unappraised; the subtype as the
# faithful pass 2 establishes it): an anastomosis whose ORGAN or a JOINS member names the stoma or the pouch
L6M_SHAPES = {
    'LAR: colorectal, organ the stoma': entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.COLORECTAL),
                                                 organ=unres(LM.STOMA, UN)),
    'RHC: ileocolic, organ the stoma': entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.ILEOCOLIC),
                                                organ=unres(LM.STOMA, UN)),
    'ileocolic, organ the pouch': entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.ILEOCOLIC),
                                           organ=unres(LM.POUCH, UN)),
    'ileocolic, joins [ileum, pouch]': entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.ILEOCOLIC),
                                                joins=(sup(LM.ILEUM), sup(LM.POUCH))),
    'colocolic, organ the pouch': entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.COLOCOLIC),
                                           organ=sup(LM.POUCH)),
}
# the one exception: an established subtype that itself defines the place (READY on int9 and int10 alike)
DEFINED_SHAPES = {
    'a colonic J-pouch: coloanal [pouch, anal canal]': entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.COLOANAL),
                                                                joins=(sup(LM.POUCH), sup(LM.ANAL_CANAL))),
    'a colonic J-pouch: colorectal, organ the pouch': entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.COLORECTAL),
                                                               organ=unres(LM.POUCH, UN)),
    "a gastric bypass's join: gastrojejunal [pouch, jejunum]": entry_of(type=sup(AT.ANASTOMOSIS),
                                                                        subtype=sup(SUB.GASTROJEJUNAL),
                                                                        joins=(sup(LM.POUCH), sup(LM.JEJUNUM))),
    'its anastomotic stoma: gastrojejunal, organ the stoma': entry_of(type=sup(AT.ANASTOMOSIS),
                                                                      subtype=sup(SUB.GASTROJEJUNAL),
                                                                      organ=unres(LM.STOMA, UN)),
}

# L9R-1 / L4P9-1 / the final check's finding 1: a gastrostomy (the only stoma) beside an entry of another type the
# session's established through names, or an id with no entry
PEG, PEG_EST = entry_of(type=sup(AT.STOMA), organ=unres(LM.STOMACH, UN)), entry_of(type=sup(AT.STOMA), organ=sup(LM.STOMACH))
NON_STOMAS = {
    'a colocolic anastomosis [transverse, descending]': entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.COLOCOLIC),
                                                                 joins=(sup(LM.TRANSVERSE_COLON),
                                                                        sup(LM.DESCENDING_COLON))),
    'an ileocolic anastomosis [ileum, colon]': entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.ILEOCOLIC),
                                                        joins=(sup(LM.ILEUM), sup(LM.COLON))),
    'a colorectal anastomosis [colon, rectum]': entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.COLORECTAL),
                                                         joins=(sup(LM.COLON), sup(LM.RECTUM))),
    'an absent appendix (other)': entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.OTHER)),
    'the sigmoid surgically absent': entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=unres(LM.SIGMOID_COLON, UN)),
    'an absent gallbladder': entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.GALLBLADDER)),
    'a gastric pouch': entry_of(type=sup(AT.GASTRIC_POUCH), organ=unres(LM.STOMACH, UN)),
}


def through_scope(code, through, entries):
    """test_l9r_refute.through_scope: ``code``'s colonoscopy through a stoma, the approach supported through_stoma,
    ``through``, a reach SUPPORTED at the cecum, the anatomy ``entries``."""
    return R3F.scope(int(code), approach=sup(AP.THROUGH_STOMA), through=through, entries=entries,
                     reached=sup(EX.CECUM))


L9R_HISTORY = ('Percutaneous endoscopic gastrostomy for dysphagia in 2029; segmental colectomy with a colocolic '
               'anastomosis in 2027.')
L9R_FINDINGS = ('The colonoscope was inserted through the stoma, passed through the colocolic anastomosis and advanced '
                'to the cecum.')
L9R_ACT = 'Two biopsies of the transverse colon were taken with cold forceps.'
L9R_ANATOMY = [('Y1', 'stoma', 'Percutaneous endoscopic gastrostomy', ['stomach'], [], []),
               ('Y2', 'anastomosis', 'colocolic anastomosis', [], ['colocolic'], ['transverse_colon', 'descending_colon'])]


def l9r_e2e(through):
    """test_l9r_refute.e2e, word for word: 44389 through the stoma, the through ``through`` (or silent)."""
    text, data = G.note(L9R_HISTORY, L9R_FINDINGS, L9R_ACT, kind='colonoscopy', kind_words='colonoscope',
                        approach=('through_stoma', 'inserted through the stoma'), through=through,
                        reached=[('cecum', 'advanced to the cecum')], anatomy=L9R_ANATOMY, place='transverse_colon',
                        place_words='transverse colon')
    return R2CL.outcomes(text, data, R2CL.FAITHFUL, ('44389', L9R_ACT))['44389'][:2]


L4P9_HISTORY = ('History: Percutaneous endoscopic gastrostomy for dysphagia and a sigmoid colectomy with a colorectal '
                'anastomosis in 2022.\n')
L4P9_FINDINGS = ('Findings: The colonoscope was inserted through the stoma, advanced across the colorectal anastomosis '
                 'and to the cecum.\n')


def peg_note(through_entry):
    """test_l4p9_refute.peg_note, word for word: the only stoma entry a gastrostomy Y2; the through ``through_entry`` (Y1,
    the colorectal anastomosis the scope crossed; or Y2)."""
    text = HEAD + L4P9_HISTORY + L4P9_FINDINGS + L9R_ACT + '\n'
    entries = [{'id': 'Y1', 'type': fact('anastomosis', src(['S4'], 'colorectal anastomosis')), 'organ': [],
                'subtype': [fact('colorectal', src(['S4'], 'colorectal anastomosis'))],
                'joins': [fact(v, src(['S4'], 'colorectal anastomosis')) for v in ('colon', 'rectum')]},
               {'id': 'Y2', 'type': fact('stoma', src(['S4'], 'Percutaneous endoscopic gastrostomy')),
                'organ': [fact('stomach', src(['S4'], 'Percutaneous endoscopic gastrostomy'))], 'subtype': [],
                'joins': []}]
    words = {'Y1': 'across the colorectal anastomosis', 'Y2': 'inserted through the stoma'}[through_entry]
    sess = session('X1', fact('colonoscopy', src(['S5'], 'colonoscope')), examination=[fact('E1', src(['S5']))],
                   encounter=[fact('this_encounter', frame(['S2']))],
                   approach=[fact('through_stoma', src(['S5'], 'inserted through the stoma'))],
                   through=[fact(through_entry, src(['S5'], words))],
                   reached=[fact('cecum', src(['S5'], 'to the cecum'))])
    events = [event('E1', ['S5'], 'colonoscope', 'was inserted', 'examination', session=[fact('X1', src(['S5']))]),
              event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                    target__places=[fact('transverse_colon', src(['S6'], 'transverse colon'))],
                    technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])]
    data = answer(sections=[opening(), labelled('N1', 'S4', 'History:', 'history'),
                            labelled('N2', 'S5', 'Findings:', 'findings')],
                  sessions=[sess], anatomy=entries, events=events)
    return R2CL.outcomes(text, data, R2CL.FAITHFUL, ('44389', L9R_ACT))['44389'][:2]


def with_through(R, through):
    session_ = dict(R.sessions[X1])
    session_.pop(A.THROUGH, None)
    if through is not None:
        session_[A.THROUGH] = (through,)
    return replace(R, sessions={**R.sessions, X1: session_})


class FindingTests(SimpleTestCase):
    """Each finding on its own input: RED on int9 (every assertion marked 'int9:' gave READY or a met route row there),
    GREEN on int10 - held with an existing reason."""

    def test_l6m_1_every_per_anus_code_beside_a_stoma_or_pouch_filed_in_an_anastomosis_field_holds(self):
        codes = per_anus_codes()
        self.assertEqual(len(codes), 30)
        met = []
        for (name, entry), code, approach in itertools.product(L6M_SHAPES.items(), codes, (None, sup(AP.TRANSANAL))):
            R = R3F.scope(code, approach=approach, entries={Y1: entry})
            if not R3F.witnesses(R3F.route_row(R, code)):
                met.append((name, code, approach is not None))
        self.assertEqual(met[:12], [])    # int9: every (shape, code, approach) met

    def test_l6m_1_a_pouch_or_stoma_named_by_a_field_holds_the_through_codes(self):
        through = [code for code in G.guarded_codes() if catalogue.lower_route(str(code)).route is not AP.TRANSANAL
                   and catalogue.lower_route(str(code)).needs is not catalogue.RouteAnatomy.POUCH]
        met = []
        for (name, entry), code in itertools.product(L6M_SHAPES.items(), through):
            R = G.met_scope(code, {Y7: entry})
            if not R3F.witnesses(R3F.route_row(R, code)):
                met.append((name, code))
        self.assertEqual(met[:12], [])    # int9: the pouch-named shapes beside 44388-44408 and 44380-44384 met

    def test_l6m_1_end_to_end_the_lens_notes_hold(self):
        # held exactly as the same stoma or pouch filed as an entry of its own (the lens's controls): the approach's
        # question beside a stoma with the approach silent, the table's own hold per anus or beside a pouch
        question, table = (HELD, ('reading_unknown',)), (HELD, (ROUTE,))
        cases = {'A1r ileocolic, organ the stoma, per anus': (colo('stoma', 'ileocolic', 'ileocolic anastomosis', H1),
                                                             '45380', ACT_CECUM, table),
                 'A1r-s the same, approach silent': (colo('stoma', 'ileocolic', 'ileocolic anastomosis', H1,
                                                          approach=False), '45380', ACT_CECUM, question),
                 'A2r colorectal, organ the stoma, flex sig, approach silent': (flex('stoma', H2, approach=False),
                                                                               '45331', ACT_SIG, question),
                 'A2r per anus': (flex('stoma', H2), '45331', ACT_SIG, table),
                 'A4r ileocolic, organ the pouch, approach silent': (colo('pouch', 'ileocolic', 'ileocolic anastomosis',
                                                                          H3, approach=False), '45380', ACT_CECUM,
                                                                     table)}
        for name, (case, code, quote, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(outcome(case, code, quote), expected)    # int9: ('ready', ())
        # the controls: the organ silent READY; the stoma filed as its own entry held, as before
        self.assertEqual(outcome(colo(None, 'ileocolic', 'ileocolic anastomosis', H1, approach=False), '45380',
                                 ACT_CECUM), (READY, ()))
        self.assertEqual(outcome(flex(None, H2, approach=False, extra=[('Y2', 'stoma', 'diverting loop stoma', [], [],
                                                                       [])]), '45331', ACT_SIG)[0], HELD)

    def test_l6m_1_the_one_exception_an_established_subtype_that_defines_the_place(self):
        for name, entry in DEFINED_SHAPES.items():
            for code in (45380, 45331):
                R = R3F.scope(code, approach=sup(AP.TRANSANAL), entries={Y1: entry})
                with self.subTest(shape=name, code=code):
                    self.assertEqual(assessed(R, code), (READY, ()))
            # the same subtype not established (pass 2 left it unclear) never exempts
            widened = dict(entry)
            widened[A.SUBTYPE] = (unres(entry[A.SUBTYPE][0].value, RS.APPRAISAL_UNCLEAR),)
            R = R3F.scope(45380, approach=sup(AP.TRANSANAL), entries={Y1: widened})
            with self.subTest(shape=name, subtype='unclear'):
                held(self, assessed(R, 45380))

    def test_l9r_1_l4p9_1_and_final_check_1_through_names_no_stoma_beside_a_gastrostomy(self):
        for code in ('44389', '44407', '44388'):
            for (name, other), peg in itertools.product(NON_STOMAS.items(), (PEG, PEG_EST)):
                R = through_scope(code, sup(Y2), {Y1: peg, Y2: other})
                with self.subTest(code=code, through=name, peg=peg[A.ORGAN][0].result.value):
                    held(self, assessed(R, code))    # int9: ('ready', ())
            R = through_scope(code, sup(Y9), {Y1: PEG_EST})
            with self.subTest(code=code, through='an id with no entry'):
                held(self, assessed(R, code))    # int9: ('ready', ())
        # the final check's probe (through_peg.py): the family's control with the PEG as its only stoma
        for name, through, extra in (('Y2 an ileocolic anastomosis', sup(Y2), {Y2: NON_STOMAS[
                'an ileocolic anastomosis [ileum, colon]']}), ('Y2 an absent gallbladder', sup(Y2), {
                    Y2: NON_STOMAS['an absent gallbladder']}), ('Y9, no entry', sup(Y9), {})):
            R, code, number = G.family_control('COLONIC_STOMA', {Y1: PEG_EST, **extra})
            R = with_through(R, through)
            with self.subTest(probe=name):
                self.assertTrue(evaluate.colonic_route_stoma_contradicted(R, X1))    # int9: False
                held(self, assessed(R, code, number))    # int9: ('ready', ())

    def test_l9r_1_and_l4p9_1_end_to_end(self):
        held(self, l9r_e2e(('Y2', 'passed through the colocolic anastomosis')))    # int9: ('ready', ())
        held(self, peg_note('Y1'))    # int9: ('ready', ())
        # the controls: the through on the gastrostomy, or silent, held as before
        for through in (('Y1', 'inserted through the stoma'), None):
            held(self, l9r_e2e(through))
        held(self, peg_note('Y2'))

    def test_the_route_reads_its_own_entry_never_another_stoma(self):
        # D345 (2): a colostomy beside the route's own entry is not the route's own - the supported through names Y2, a
        # stoma whose type pass 2 left unclear, or an id with no entry: held; the colostomy named by the through: READY
        colostomy = entry_of(type=sup(AT.STOMA), organ=unres(LM.SIGMOID_COLON, UN))
        for code in ('44389', '44407'):
            R = through_scope(code, sup(Y1), {Y1: colostomy})
            self.assertEqual(assessed(R, code), (READY, ()), code)
            for name, through, entries in (
                    ('a stoma pass 2 left unclear', sup(Y2), {Y1: colostomy, Y2: entry_of(type=unres(
                        AT.STOMA, RS.APPRAISAL_UNCLEAR), organ=unres(LM.SIGMOID_COLON, UN))}),
                    ('a stoma claimed, never asked', sup(Y2), {Y1: colostomy, Y2: entry_of(type=unres(AT.STOMA, UN))}),
                    ('the colocolic anastomosis passed', sup(Y2), {Y1: colostomy, Y2: NON_STOMAS[
                        'a colocolic anastomosis [transverse, descending]']}),
                    ('an id with no entry', sup(Y9), {Y1: colostomy})):
                with self.subTest(code=code, through=name):
                    held(self, assessed(through_scope(code, through, entries), code))


# === (3) the censuses ==================================================================================================

def _row_entry(row, value):
    """The entry a harmless row releases at ``value`` of its controlled claim, every other field as filed (silent)."""
    if row.decided_by is A.TYPE:
        return {A.TYPE: (sup(value),)}
    if row.decided_by is A.ORGAN:
        return {A.TYPE: (sup(catalogue.ABSENCE_TYPE),), A.ORGAN: (sup(value),)}
    return {A.TYPE: (sup(catalogue.SUBTYPE_TYPE),), A.SUBTYPE: (sup(value),)}


def _claim_control(field, value):
    """A claim's control value and a second reading (a pass-1 side or doubt's), from the contract's sibling tables."""
    if field is A.TYPE:
        return CL.TYPE_SIBLINGS.get(value), (AT.SURGICALLY_ABSENT if value is not AT.SURGICALLY_ABSENT else AT.STOMA)
    if field is A.SUBTYPE:
        return CL.SUBTYPE_SIBLINGS.get(value), (SUB.ILEORECTAL if value is not SUB.ILEORECTAL else SUB.OTHER)
    return None, (LM.COLON if value is not LM.COLON else LM.RECTUM)


def read_claims():
    """DECISIONS D345 (3) (the final check's finding 4: int9 listed three by hand): EVERY claim a harmless row reads,
    DERIVED from catalogue.HARMLESS - for every family's every row, its controlled claim at each value it releases on
    (``values``), its filed organ at each place it admits (``organs``; the absence row's organ is its claim) and a joins
    member at each place it admits (``joins``), each beside the row's own entry at its first value: (label, field, value,
    base facts) - each distinct (shape, field, value) once."""
    seen = {}
    for needs, rows in catalogue.HARMLESS.items():
        for row in rows:
            first = sorted(row.values, key=lambda v: v.value)[0]
            claims = [(row.decided_by, value) for value in row.values]
            if row.decided_by is not A.ORGAN:
                claims += [(A.ORGAN, place) for place in row.organs]
            claims += [(A.JOINS, place) for place in row.joins]
            for field, value in claims:
                base_value = value if field is row.decided_by else first
                key = (row.shape, field, value, base_value)
                seen.setdefault(key, (f'{row.shape.value}: {field.value} {value.value}', field, value,
                                      _row_entry(row, base_value)))
    return list(seen.values())


def entry_args(facts, field, found, decides):
    """The declared oracle's arguments (G.oracle_harmless) for ``facts`` with ``field`` settled as ``found`` (None:
    silent): each field's values by D342 (1) (a) - a filed established field its value, the varied one by its state."""
    def values(attribute, enum):
        if attribute is field:
            return None if found is None else declared_values(found, enum, decides)
        filed = facts.get(attribute, (None,))[0]
        return None if filed is None else frozenset({filed.value})
    types = values(A.TYPE, AT)
    subtypes = values(A.SUBTYPE, SUB)
    organs = values(A.ORGAN, LM)
    joins = tuple(frozenset({member.value}) for member in facts.get(A.JOINS, ()))
    if field is A.JOINS and found is not None:
        joins = joins + (declared_values(found, LM, decides),)
    return (types if types is not None else ALL_TYPES, subtypes if subtypes is not None else ALL_SUBTYPES,
            subtypes is None, organs if organs is not None else ALL_PLACES, organs is None, joins)


def with_field(facts, field, found):
    out = dict(facts)
    if field is A.JOINS:
        if found is not None:
            out[A.JOINS] = tuple(facts.get(A.JOINS, ())) + (found,)
    elif found is None:
        out.pop(field, None)
    else:
        out[field] = (found,)
    return out


class ReadClaimsCensusTests(SimpleTestCase):
    """D345 (3): settle's whole outcome table x every claim a harmless row reads (derived from the catalogue) x every route
    family: evaluate.harmless equals the declared release set (test_r3g_rules.oracle_harmless) over the values the
    claim may be by D342 (1) (a)."""

    def test_every_claim_a_harmless_row_reads_every_settled_state_every_family(self):
        R0 = G.bare()
        wrong, checked, released, widened = [], 0, 0, 0
        claims = read_claims()
        for label, field, value, base in claims:
            control, other = _claim_control(field, value)
            for state, row, found, decides in states_of(value, control, other):
                if row == 3 and field is A.JOINS:
                    continue  # a joins member is never silent: an empty list has no member
                settled = None if row == 3 else found
                R = G.with_entry(R0, with_field(base, field, settled))
                args = entry_args(base, field, settled, decides)
                for family in G.FAMILIES:
                    expected = G.oracle_harmless(family, *args)
                    if evaluate.harmless(R, Y1, G.needs(family)) != expected:
                        wrong.append((family, label, state, expected))
                    checked += 1
                    released += expected
                    widened += not decides and row != 3
        self.assertEqual(wrong[:20], [])
        self.assertGreater(len(claims), 300)
        self.assertTrue(0 < released < checked)
        self.assertGreater(widened, checked // 2)

    def test_the_claims_are_every_claim_every_row_reads(self):
        # completeness, derived from the catalogue itself: every row of every family, every value of its controlled
        # claim, every place its organs and joins admit
        claims = {(field, value) for _l, field, value, _b in read_claims()}
        for needs, rows in catalogue.HARMLESS.items():
            for row in rows:
                with self.subTest(needs=needs.value, row=row.shape.value):
                    self.assertLessEqual({(row.decided_by, value) for value in row.values}, claims)
                    self.assertLessEqual({(A.JOINS, place) for place in row.joins}, claims)
                    if row.decided_by is not A.ORGAN:
                        self.assertLessEqual({(A.ORGAN, place) for place in row.organs}, claims)
        # and settle's whole table: every row 1-9 for each claim kind
        rows = {row for _l, row, _f, _d in states_of(LM.STOMACH, None, LM.COLON)}
        self.assertEqual(rows, set(range(1, 10)))


# --- (2) the route's own entry: the through over every entry type, every settled state and none ------------------------

OUTSIDE_OWN = {  # an entry of the route's type outside its anatomy (DECLARED: its organ outside OWN's organs)
    'COLONIC_STOMA': entry_of(type=sup(AT.STOMA), organ=sup(LM.STOMACH)),
    'ILEAL_STOMA': entry_of(type=sup(AT.STOMA), organ=sup(LM.JEJUNUM)),
    'POUCH': entry_of(type=sup(AT.ILEAL_POUCH), organ=sup(LM.STOMACH)),
}


def through_entry(typ):
    """An entry of type ``typ`` (supported), every other field silent."""
    return entry_of(type=sup(typ))


def declared_route(family, anatomy, found, decides, silent, target):
    """D342 (1) (c) and D345 (2), DECLARED: (uncertain, candidates, stomas passed, own established for the arms) for the
    session's through settled as ``found`` naming ``target``."""
    wanted = OWN[family][0]

    def shapes(entry):
        facts = anatomy[entry]
        type_ = facts.get(A.TYPE, (None,))[0]
        types = frozenset({type_.value}) if type_ is not None and facts_.established(type_) or (
            type_ is not None and type_.result is Res.UNRESOLVED and type_.reasons == (UN,)) else ALL_TYPES
        if type_ is not None and type_.result is Res.NEGATED:
            types = ALL_TYPES
        organ = facts.get(A.ORGAN, (None,))[0]
        fields = [frozenset({organ.value})] if organ is not None else []
        fields += [frozenset({member.value}) for member in facts.get(A.JOINS, ())]
        return types | declared_made(fields, ALL_SUBTYPES, True)
    of_type = {entry for entry in anatomy if wanted in shapes(entry)}
    if silent:
        names, may_name = set(), set(anatomy)
    elif decides:
        names, may_name = {target}, {target}
    else:
        names = may_name = set(anatomy) | {target} | {v for v in found.options if isinstance(v, Id)}
    uncertain = any(name not in anatomy or wanted not in shapes(name) for name in names)
    supported = found is not None and found.result is Res.SUPPORTED
    if uncertain:
        candidates = of_type
    elif supported:
        candidates = {target} & of_type
    else:
        candidates = of_type & may_name
    stomas = {entry for entry in anatomy if AT.STOMA in shapes(entry)}
    if not uncertain and supported:
        stomas &= {target}
    own = {target} if supported else candidates
    established = any(entry in anatomy and anatomy[entry].get(A.TYPE, (None,))[0] == sup(wanted) for entry in own)
    return uncertain, candidates, stomas, established


def declared_outside(family, facts) -> bool:
    _t, organs, subtypes, joins = OWN[family]
    organ = facts.get(A.ORGAN, (None,))[0]
    subtype = facts.get(A.SUBTYPE, (None,))[0]
    return ((organ is not None and organ.value not in organs) or (subtype is not None and subtype.value not in subtypes)
            or any(member.value not in joins for member in facts.get(A.JOINS, ())))


class RouteThroughCensusTests(SimpleTestCase):
    """D345 (2) and (3): every through family and LOWER's stoma class x the session's through naming an entry of EVERY
    type (supported, every other field silent) or an id with no entry, in EVERY settled state of settle's table (silent
    included), beside the family's own entry and an entry of the route's type outside its anatomy: the route's own entry
    and its readers equal the ruling declared here."""

    def test_every_through_family_every_entry_type_every_settled_state_and_none(self):
        wrong, checked, held_n = [], 0, 0
        seen_targets = set()
        for family in OWN:
            found_row = catalogue.lower_route(THROUGH_CODES[family][0])
            wanted = OWN[family][0]
            for target_type in (*sorted(AT, key=lambda t: t.value), None):
                extra = {Y5: OUTSIDE_OWN[family]}
                target = Y9 if target_type is None else Y7
                seen_targets.add(target_type)
                if target_type is not None:
                    extra[Y7] = through_entry(target_type)
                R0, _code, _number = G.family_control(family, extra)
                for state, row, found, decides in states_of(target, Y1, Y5):
                    settled = None if row == 3 else found
                    R = with_through(R0, settled)
                    anatomy = dict(R.anatomy)
                    uncertain, candidates, stomas, established = declared_route(family, anatomy, settled, decides,
                                                                                row == 3, target)
                    expected_own = ((uncertain and not any(anatomy[c].get(A.TYPE, (None,))[0] == sup(wanted)
                                                           for c in candidates))
                                    or any(declared_outside(family, anatomy[c]) for c in candidates))
                    got = (evaluate._route_uncertain(R, X1, wanted), set(evaluate._route_may_use(found_row, R, X1)),
                           evaluate.route_own_entry_contradicted(found_row, R, X1),
                           evaluate._route_own_established(R, X1, wanted))
                    expected = (uncertain, candidates, expected_own, established)
                    if family == 'COLONIC_STOMA':
                        got += (set(evaluate._stomas_passed(R, X1)), evaluate.colonic_route_stoma_contradicted(R, X1))
                        expected += (stomas, any(anatomy[s].get(A.ORGAN, (None,))[0] is not None and anatomy[s][
                            A.ORGAN][0].value not in LOWER_STOMA for s in stomas))
                    if got != expected:
                        wrong.append((family, target_type and target_type.value, state, expected, got))
                    checked += 1
                    held_n += expected_own
        self.assertEqual(wrong[:10], [])
        self.assertTrue(0 < held_n < checked)
        # D345 (3): the census's own derivation - every type the through may name, and an id with no entry
        self.assertEqual(seen_targets, {*AT, None})

    def test_the_deciding_states_end_to_end(self):
        # the supported through naming an entry of each type beside the family's own entry and an entry of the route's
        # type outside its anatomy: READY only where the through names an entry established of the route's type (and
        # for the pouch never: a second pouch is no harmless shape)
        for family, codes in THROUGH_CODES.items():
            wanted = OWN[family][0]
            for code in codes:
                for target_type in (*sorted(AT, key=lambda t: t.value), None):
                    extra = {Y5: OUTSIDE_OWN[family]}
                    if target_type is not None:
                        extra[Y7] = through_entry(target_type)
                    R, _c, number = G.family_control(family, extra)
                    if code != _c:
                        R = replace(R, events={**R.events})
                    R = with_through(R, sup(Y7 if target_type is not None else Y9))
                    found = assessed(R, _c, number) if code == _c else None
                    with self.subTest(family=family, through=target_type and target_type.value):
                        if found is None:
                            continue
                        if target_type is wanted and family != 'POUCH':
                            self.assertEqual(found, (READY, ()))
                        else:
                            held(self, found)


class RouteOwnFieldCensusTests(SimpleTestCase):
    """D345 (3) (D342 (1) (d)'s route census, derived): each through family's own entry (its type established, the
    through supported naming it) x its organ, subtype and one joins member at every value in EVERY settled state of
    settle's table, and its two-member joins over EVERY landmark pair: the guard holds exactly when a field may lie
    outside the declared own anatomy."""

    def check(self, family, label, facts, expected, wrong):
        code = THROUGH_CODES[family][0]
        R, _code, _number = G.family_control(family, {Y1: facts})
        found = catalogue.lower_route(code)
        got = (evaluate.route_own_entry_contradicted(found, R, X1), evaluate.path_guard(found, R, X1))
        if got != (expected, expected):
            wrong.append((family, label, expected, got))

    def test_every_own_field_every_value_every_settled_state(self):
        wrong, checked, held_n = [], 0, 0
        for family, (typ, organs, subtypes, joins) in OWN.items():
            base = {A.TYPE: (sup(typ),)}
            for field, enum, inside in ((A.ORGAN, LM, organs), (A.SUBTYPE, SUB, subtypes), (A.JOINS, LM, joins)):
                for value in sorted(enum, key=lambda v: v.value):
                    control, other = _claim_control(field, value)
                    for state, row, found, decides in states_of(value, control, other):
                        if row == 3:
                            continue  # a silent field files nothing (the base: the own entry as filed)
                        values = declared_values(found, enum, decides)
                        expected = not values <= inside
                        self.check(family, (field.value, value.value, state), with_field(base, field, found), expected,
                                   wrong)
                        checked += 1
                        held_n += expected
            self.check(family, 'as filed', base, False, wrong)
        self.assertEqual(wrong[:20], [])
        self.assertTrue(0 < held_n < checked)

    def test_two_member_joins_over_every_landmark_pair(self):
        wrong, checked = [], 0
        places = sorted(LM, key=lambda p: p.value)
        for family, (typ, _organs, _subtypes, joins) in OWN.items():
            for one, other in itertools.combinations_with_replacement(places, 2):
                facts = {A.TYPE: (sup(typ),), A.JOINS: (sup(one), sup(other))}
                self.check(family, (one.value, other.value), facts, not {one, other} <= joins, wrong)
                checked += 1
        self.assertEqual(wrong[:20], [])
        self.assertEqual(checked, 3 * len(places) * (len(places) + 1) // 2)


# --- (1) the field census ----------------------------------------------------------------------------------------------

BASES = {  # the entry each field is filed beside: (type fact, subtype fact or None)
    'an anastomosis, its subtype silent': (sup(AT.ANASTOMOSIS), None),
    'an anastomosis, ileocolic': (sup(AT.ANASTOMOSIS), sup(SUB.ILEOCOLIC)),
    'an anastomosis, coloanal': (sup(AT.ANASTOMOSIS), sup(SUB.COLOANAL)),
    'an anastomosis, gastrojejunal': (sup(AT.ANASTOMOSIS), sup(SUB.GASTROJEJUNAL)),
    'an anastomosis, ileoanal': (sup(AT.ANASTOMOSIS), sup(SUB.ILEOANAL)),
    'an anastomosis, coloanal pass 2 left unclear': (sup(AT.ANASTOMOSIS), unres(SUB.COLOANAL, RS.APPRAISAL_UNCLEAR)),
    'surgically absent': (sup(AT.SURGICALLY_ABSENT), None),
    'a stoma': (sup(AT.STOMA), None),
    'a gastric pouch': (sup(AT.GASTRIC_POUCH), None),
    'its type silent': (None, None),
}
FIELDS = ('organ', 'joins[0]', 'joins[1]')
FIRST_MEMBER = LM.COLON   # joins[1] is filed beside this first member


def field_facts(base, field, found):
    type_, subtype = BASES[base]
    facts = {}
    if type_ is not None:
        facts[A.TYPE] = (type_,)
    if subtype is not None:
        facts[A.SUBTYPE] = (subtype,)
    if field == 'organ':
        facts[A.ORGAN] = (found,)
    elif field == 'joins[0]':
        facts[A.JOINS] = (found,)
    else:
        facts[A.JOINS] = (sup(FIRST_MEMBER), found)
    return facts


def base_subtypes(base):
    subtype = BASES[base][1]
    if subtype is None:
        return ALL_SUBTYPES, True
    if subtype.result is Res.SUPPORTED:
        return frozenset({subtype.value}), False
    return ALL_SUBTYPES, False


def base_types(base):
    type_ = BASES[base][0]
    return frozenset({type_.value}) if type_ is not None else ALL_TYPES


def field_values(field, values):
    """The field sets of the declared readers: the varied field's values, and joins[1]'s first member."""
    return [values] + ([frozenset({FIRST_MEMBER})] if field == 'joins[1]' else [])


class FieldCensusTests(SimpleTestCase):
    """D345 (1) and (3): every field (organ, each joins member, subtype) x every Landmark, the stoma and the pouch
    included, x every settled state x every route family, against the ruling declared here."""

    def test_the_one_rule_every_field_every_landmark_every_settled_state(self):
        # evaluate.made_shapes (by the one predicate, and by facts.possibly for the hold-or-question readers) over every
        # field x every Landmark x every distinct settled state x the subtype beside it (silent, defining nothing,
        # defining the pouch, defining both, defining the ileal pouch's own join, and one pass 2 left unclear)
        R0 = G.bare()
        wrong, checked, made = [], 0, 0
        seen = set()
        for field, place in itertools.product(FIELDS, sorted(LM, key=lambda p: p.value)):
            _control, other = _claim_control(A.ORGAN, place)
            seen.add((field, place))
            for state, row, found, decides in states_of(place, None, other):
                if row == 3:
                    continue  # a silent field files nothing
                for base in BASES:
                    R = G.with_entry(R0, field_facts(base, field, found))
                    subtypes, silent = base_subtypes(base)
                    values = declared_values(found, LM, decides)
                    expected = declared_made(field_values(field, values), subtypes, silent)
                    expected_p = declared_made(field_values(field, possibly_values(found, LM)), subtypes, silent)
                    got = (evaluate.made_shapes(R, Y1), evaluate.made_shapes(R, Y1, facts_.possibly))
                    if got != (expected, expected_p):
                        wrong.append((field, place.value, state, base, (expected, expected_p), got))
                    checked += 1
                    made += bool(expected)
        self.assertEqual(wrong[:20], [])
        self.assertTrue(0 < made < checked)
        # D345 (3): the census's own derivation - every field the rule reads at every Landmark
        self.assertEqual(seen, set(itertools.product(FIELDS, LM)))

    def test_the_subtype_every_value_every_settled_state(self):
        # the exception's own field: the subtype at every value in every settled state beside the stoma and the pouch
        # filed in each field - only an established (or unappraised) subtype every value of which defines the place
        # exempts it
        R0 = G.bare()
        wrong, checked = [], 0
        for value in sorted(SUB, key=lambda s: s.value):
            control, other = _claim_control(A.SUBTYPE, value)
            for state, row, found, decides in states_of(value, control, other):
                for field, place in itertools.product(FIELDS, (LM.STOMA, LM.POUCH)):
                    facts = field_facts('an anastomosis, its subtype silent', field, sup(place))
                    if row != 3:
                        facts[A.SUBTYPE] = (found,)
                    R = G.with_entry(R0, facts)
                    subtypes = declared_values(found, SUB, decides) if row != 3 else ALL_SUBTYPES
                    expected = declared_made(field_values(field, frozenset({place})), subtypes, row == 3)
                    if evaluate.made_shapes(R, Y1) != expected:
                        wrong.append((value.value, state, field, place.value, expected))
                    checked += 1
        self.assertEqual(wrong[:20], [])
        self.assertGreater(checked, 1000)

    def test_every_reader_every_route_family(self):
        # every reader of an entry's shape, over every field x every Landmark x a narrowing and two widening states x
        # each base: the harmless rows for every family (the declared release set), the per-anus arms' readers, and the
        # path guard of every route family's codes - EUS included - beside the family's control
        R0 = G.bare()
        wrong, checked = [], 0
        states = (('supported', lambda p: sup(p), True), ('claimed', lambda p: unres(p, UN), True),
                  ('pass 2 unclear', lambda p: unres(p, RS.APPRAISAL_UNCLEAR), False),
                  ('pass 1 contradicted', lambda p: contra(p, LM.COLON if p is not LM.COLON else LM.RECTUM), False))
        scenes = {code: (family, (R3F.scope(int(code), approach=sup(AP.TRANSANAL)) if G.ROUTE_OF[family]
                                  is AP.TRANSANAL else G.met_scope(int(code))))
                  for family, codes in FAMILY_CODES.items() for code in codes}
        for field, place, (s_name, make, narrow), base in itertools.product(
                FIELDS, sorted(LM, key=lambda p: p.value), states, BASES):
            facts = field_facts(base, field, make(place))
            R = G.with_entry(R0, facts)
            subtypes, silent = base_subtypes(base)
            values = frozenset({place}) if narrow else ALL_PLACES
            fields = field_values(field, values)
            shapes = base_types(base) | declared_made(fields, subtypes, silent)
            organs = values if field == 'organ' else ALL_PLACES
            joins = tuple(fields) if field != 'organ' else ()
            args = (base_types(base), subtypes, silent, organs, field != 'organ', joins)
            organ_outside = (field == 'organ' and narrow and make(place).result is Res.SUPPORTED
                             and place not in LOWER_STOMA and place not in G.NO_ORGAN)
            lower = AT.STOMA in declared_made(fields, subtypes, silent) or not organ_outside
            readers = (evaluate.may_be_shape(R, Y1, AT.STOMA), evaluate.ileal_pouch_possible(R, Y1),
                       evaluate.lower_stoma_possible(R, Y1))
            expected_readers = (AT.STOMA in shapes, AT.ILEAL_POUCH in shapes, lower)
            if readers != expected_readers:
                wrong.append(('readers', field, place.value, s_name, base, expected_readers, readers))
            harmless = {family: G.oracle_harmless(family, *args) for family in G.FAMILIES}
            for family in G.FAMILIES:
                if evaluate.harmless(R, Y1, G.needs(family)) != harmless[family]:
                    wrong.append(('harmless', family, field, place.value, s_name, base, harmless[family]))
            for code, (family, scene) in scenes.items():
                R2 = replace(scene, anatomy={**scene.anatomy, Y7: facts})
                expected = not harmless[family]
                if G.ROUTE_OF[family] is AP.TRANSANAL:
                    expected = expected or (AT.STOMA in shapes and lower) or AT.ILEAL_POUCH in shapes
                if evaluate.path_guard(catalogue.lower_route(code), R2, X1) != expected:
                    wrong.append(('guard', code, field, place.value, s_name, base, expected))
                checked += 1
        self.assertEqual(wrong[:20], [])
        self.assertEqual(checked, len(FIELDS) * len(LM) * len(states) * len(BASES) * len(scenes))

    def test_every_other_reader_of_the_shape(self):
        # the readers the guard's backstop hides (an entry a field makes a stoma or a pouch is never harmless, so the
        # code holds either way): the per-anus approach's question (stoma_possible, by facts.possibly), the colonic
        # route's organ arm (colonic_route), the stomas passed (_stomas_passed, colonic_stoma_possible: the one
        # predicate) and R5R-8 (_stoma_or_pouch_possible, every made place) - each reads a filed organ's stoma or pouch
        # exactly as one filed as the entry's type; DECLARED here over every landmark x a narrowing and a widening state
        colostomy = entry_of(type=sup(AT.STOMA), organ=sup(LM.SIGMOID_COLON))
        states = (('supported', lambda p: sup(p), True), ('claimed', lambda p: unres(p, UN), True),
                  ('pass 2 unclear', lambda p: unres(p, RS.APPRAISAL_UNCLEAR), False),
                  ('pass 1 contradicted', lambda p: contra(p, LM.COLON if p is not LM.COLON else LM.RECTUM), False))
        wrong, checked = [], 0
        ileocolic = frozenset({SUB.ILEOCOLIC})
        for place, (s_name, make, narrow) in itertools.product(sorted(LM, key=lambda p: p.value), states):
            organ = make(place)
            facts = entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.ILEOCOLIC), organ=organ)
            values = frozenset({place}) if narrow else ALL_PLACES
            made = declared_made([values], ileocolic, False)
            made_p = declared_made([possibly_values(organ, LM)], ileocolic, False)
            R = R3F.scope(45380, approach=None, entries={Y7: facts})
            R_cs, _c, _n = G.family_control('COLONIC_STOMA', {Y1: colostomy, Y7: facts})
            session_ = dict(R_cs.sessions[X1])
            session_[A.REACHED] = (sup(EX.STOMA),)
            R_cs = replace(R_cs, sessions={**R_cs.sessions, X1: session_})
            R_is, _c, _n = G.family_control('ILEAL_STOMA', {Y7: facts})
            R_is = with_through(R_is, None)
            got = (evaluate.stoma_possible(R, X1), evaluate.colonic_route(R_cs, X1),
                   set(evaluate._stomas_passed(R_is, X1)), evaluate.colonic_stoma_possible(R_is, X1),
                   evaluate._stoma_or_pouch_possible(R, Y7))
            expected = (AT.STOMA in made_p, AT.STOMA not in made_p, {Y1} | ({Y7} if AT.STOMA in made else set()),
                        AT.STOMA in made and bool(values & (G.COLON_ALL | G.NO_ORGAN)),
                        bool(values & {LM.STOMA, LM.POUCH}) or bool(made))
            if got != expected:
                wrong.append((place.value, s_name, expected, got))
            checked += 1
        self.assertEqual(wrong[:20], [])
        self.assertEqual(checked, len(LM) * len(states))

    def test_every_route_family_end_to_end_on_the_made_places(self):
        # the assembled engine: the stoma or the pouch filed in each field of an anastomosis beside each family's code
        # (EUS included) - held with an existing reason, but where the established subtype defines the place
        for code, family in ((c, f) for f, codes in FAMILY_CODES.items() for c in codes):
            scene = (R3F.scope(int(code), approach=sup(AP.TRANSANAL)) if G.ROUTE_OF[family] is AP.TRANSANAL
                     else G.met_scope(int(code)))
            self.assertEqual(assessed(scene, code), (READY, ()), code)
            for base, field, place in itertools.product(('an anastomosis, ileocolic', 'an anastomosis, coloanal',
                                                         'an anastomosis, gastrojejunal'), FIELDS, (LM.STOMA, LM.POUCH)):
                facts = field_facts(base, field, unres(place, UN))
                R = replace(scene, anatomy={**scene.anatomy, Y7: facts})
                subtypes, silent = base_subtypes(base)
                made = declared_made(field_values(field, frozenset({place})), subtypes, silent)
                found = assessed(R, code)
                with self.subTest(code=code, base=base, field=field, place=place.value):
                    if made:
                        held(self, found)   # each with an existing reason (no new Reason: engine/types)

    def test_the_census_is_complete(self):
        # every field the rule reads, every Landmark (the made places among them), every row of settle's table, every
        # route family and each EUS class's code, and every lower-GI code's family has a code here
        self.assertEqual({'organ', 'joins[0]', 'joins[1]'}, set(FIELDS))
        self.assertLessEqual(set(MADE), set(LM))
        self.assertEqual({row for _l, row, _f, _d in states_of(LM.STOMA, None, LM.COLON)}, set(range(1, 10)))
        self.assertEqual(set(FAMILY_CODES), set(G.FAMILIES))
        eus = {code for codes in FAMILY_CODES.values() for code in codes if int(code) in catalogue.LOWER_EUS_CLASS}
        self.assertEqual({catalogue.LOWER_EUS_CLASS[int(code)] for code in eus}, set(catalogue.LOWER_EUS_CLASS.values()))
        self.assertEqual({G.needs(family) for family in FAMILY_CODES},
                         {catalogue.lower_route(str(code)).needs for code in G.guarded_codes()})
        self.assertEqual({SUB(value) for value in DEFINED} | {s for s in SUB if s not in DEFINED}, set(SUB))

# === the combinations the one-field censuses left out (the mutation proof's survivors: NOTES section 6) ===============

def place_classes():
    """DERIVED: one landmark of every class the shape readers distinguish - the made place it is (MADE), whether it
    names no placeable organ (G.NO_ORGAN), whether a lower-tract stoma may lie there (LOWER_STOMA), whether it is the
    colon's (G.COLON_ALL) or the ileum's (ILEAL) - the first of each class by value."""
    seen = {}
    for place in sorted(LM, key=lambda p: p.value):
        key = (MADE.get(place), place in G.NO_ORGAN, place in LOWER_STOMA, place in G.COLON_ALL, place in ILEAL)
        seen.setdefault(key, place)
    return seen


READER_STATES = (('supported', lambda p: sup(p), True), ('claimed', lambda p: unres(p, UN), True),
                 ('pass 2 unclear', lambda p: unres(p, RS.APPRAISAL_UNCLEAR), False),
                 ('pass 1 contradicted', lambda p: contra(p, LM.COLON if p is not LM.COLON else LM.RECTUM), False))


def declared_types(found, decides):
    """D342 (1) (a), DECLARED: the types an entry's type field in a settled state may be (silent: every type)."""
    return ALL_TYPES if found is None else declared_values(found, AT, decides)


def declared_established(found, wanted) -> bool:
    """DECLARED: a type ESTABLISHED as ``wanted`` - pass 2 established it (SUPPORTED at that value)."""
    return found is not None and found.result is Res.SUPPORTED and found.value is wanted


class CombinationCensusTests(SimpleTestCase):
    """D345 (1) and (2), the combinations the one-field censuses left out - found by the mutation proof, whose reader
    mutants survived them (NOTES section 6): (1) every reader of an entry's shape over its ORGAN and a JOINS member
    TOGETHER, each a landmark of every class the readers distinguish (derived) in every reader state or not filed,
    beside every base; (2) the route's own entry's TYPE in every settled state of settle's table beside the session's
    through naming it, an entry of every type, an id with no entry, or nothing - against the rulings declared here."""

    def test_every_reader_over_the_organ_and_a_joins_member_together(self):
        # a filed organ decides lower_stoma_possible where a joins member makes a stoma (an upper organ beside a made
        # stoma), R5R-8 reads a joins member's shape, the per-anus stoma arm reads a made stoma beside a type that is
        # none, the question readers read each field by facts.possibly - each DECLARED here
        R0 = G.bare()
        classes = place_classes()
        options = [None] + [(place, state) for place in classes.values() for state in READER_STATES]
        scene = R3F.scope(45380, approach=sup(AP.TRANSANAL))
        wrong, checked, made_n = [], 0, 0
        for base, organ_opt, member_opt in itertools.product(BASES, options, options):
            type_, subtype = BASES[base]
            facts = {}
            if type_ is not None:
                facts[A.TYPE] = (type_,)
            if subtype is not None:
                facts[A.SUBTYPE] = (subtype,)
            fields, fields_p, organ_values, organ_outside = [], [], None, False
            if organ_opt is not None:
                place, (_s, make, narrow) = organ_opt
                found = make(place)
                facts[A.ORGAN] = (found,)
                organ_values = frozenset({place}) if narrow else ALL_PLACES
                fields.append(organ_values)
                fields_p.append(possibly_values(found, LM))
                organ_outside = (found.result is Res.SUPPORTED and place not in LOWER_STOMA
                                 and place not in G.NO_ORGAN)
            if member_opt is not None:
                place, (_s, make, narrow) = member_opt
                found = make(place)
                facts[A.JOINS] = (found,)
                fields.append(frozenset({place}) if narrow else ALL_PLACES)
                fields_p.append(possibly_values(found, LM))
            R = G.with_entry(R0, facts)
            subtypes, silent = base_subtypes(base)
            made = declared_made(fields, subtypes, silent)
            made_p = declared_made(fields_p, subtypes, silent)
            types = base_types(base)
            shapes, shapes_p = types | made, types | made_p
            lower = AT.STOMA in made or not organ_outside
            stoma_or_pouch = (bool(types & {AT.STOMA, AT.ILEAL_POUCH, AT.GASTRIC_POUCH})
                              or (organ_values is not None and bool(organ_values & {LM.STOMA, LM.POUCH}))
                              or bool(made))
            R2 = replace(scene, anatomy={**scene.anatomy, Y7: facts})
            got = (evaluate.may_be_shape(R, Y1, AT.STOMA), evaluate.may_be_shape(R, Y1, AT.ILEAL_POUCH),
                   evaluate.possibly_shape(R, Y1, AT.STOMA), evaluate.possibly_shape(R, Y1, AT.ILEAL_POUCH),
                   evaluate.lower_stoma_possible(R, Y1), evaluate._stoma_or_pouch_possible(R, Y1),
                   evaluate._anus_route_contradicted(R2, X1))
            expected = (AT.STOMA in shapes, AT.ILEAL_POUCH in shapes, AT.STOMA in shapes_p, AT.ILEAL_POUCH in shapes_p,
                        lower, stoma_or_pouch, (AT.STOMA in shapes and lower) or AT.ILEAL_POUCH in shapes)
            if got != expected:
                wrong.append((base, organ_opt and (organ_opt[0].value, organ_opt[1][0]),
                              member_opt and (member_opt[0].value, member_opt[1][0]), expected, got))
            checked += 1
            made_n += bool(made)
        self.assertEqual(wrong[:20], [])
        self.assertEqual(checked, len(BASES) * len(options) ** 2)
        self.assertTrue(0 < made_n < checked)
        # completeness: every class the readers distinguish has its landmark, the made places among them
        self.assertEqual(set(classes), {(MADE.get(p), p in G.NO_ORGAN, p in LOWER_STOMA, p in G.COLON_ALL,
                                         p in ILEAL) for p in LM})
        self.assertLessEqual(set(MADE), set(classes.values()))

    def test_the_own_entry_type_every_settled_state_beside_every_through(self):
        # (2) with no candidate established as the route's type, a route that is not certain holds; the arms take the
        # SUPPORTED through's entry and none other; only the route's own entry is asked (_stoma_entry) and passed
        # (_stomas_passed) - beside the route's own entry whose TYPE is in every settled state, the through naming it,
        # an entry of every type, an id with no entry, or nothing
        wrong, checked, held_n, asked_n, targets = [], 0, 0, 0, set()
        for family in OWN:
            found_row = catalogue.lower_route(THROUGH_CODES[family][0])
            wanted = OWN[family][0]
            control, other = _claim_control(A.TYPE, wanted)
            R0, code, number = G.family_control(family)
            group = catalogue.requirements(evaluate._code(code).link)[0]
            event = Id.parse(f'E{number}')
            own_facts = dict(R0.anatomy[Y1])
            for state, row, found, decides in states_of(wanted, control, other):
                facts = dict(own_facts)
                facts.pop(A.TYPE, None)
                if row != 3:
                    facts[A.TYPE] = (found,)
                y1_type = None if row == 3 else found
                for target_type in (*sorted(AT, key=lambda t: t.value), 'the own entry', 'no entry', 'silent'):
                    targets.add(target_type)
                    anatomy, types = {Y1: facts}, {Y1: declared_types(y1_type, decides)}
                    type_facts = {Y1: y1_type}
                    if target_type == 'the own entry':
                        through, target = sup(Y1), Y1
                    elif target_type == 'no entry':
                        through, target = sup(Y9), Y9
                    elif target_type == 'silent':
                        through, target = None, None
                    else:
                        anatomy[Y7] = through_entry(target_type)
                        types[Y7], type_facts[Y7] = frozenset({target_type}), sup(target_type)
                        through, target = sup(Y7), Y7
                    R = with_through(replace(R0, anatomy=anatomy), through)
                    names = set() if through is None else {target}
                    uncertain = any(name not in anatomy or wanted not in types[name] for name in names)
                    of_type = [entry for entry in anatomy if wanted in types[entry]]
                    if uncertain or through is None:
                        candidates = of_type
                    else:
                        candidates = [entry for entry in of_type if entry == target]
                    own = [target] if through is not None else candidates
                    established = [entry for entry in own if declared_established(type_facts.get(entry), wanted)]
                    contradicted = ((uncertain and not any(declared_established(type_facts[c], wanted)
                                                           for c in candidates))
                                    or any(declared_outside(family, anatomy[c]) for c in candidates))
                    got = (evaluate._route_uncertain(R, X1, wanted), list(evaluate._route_may_use(found_row, R, X1)),
                           evaluate.route_own_entry_contradicted(found_row, R, X1),
                           evaluate._route_own_established(R, X1, wanted))
                    expected = (uncertain, candidates, contradicted, bool(established))
                    if wanted is AT.STOMA:
                        asked = next((entry for entry in own if entry in anatomy and (
                            type_facts[entry] is None or AT.STOMA in possibly_values(type_facts[entry], AT))), None)
                        held_fact = evaluate._stoma_entry(R, X1, event, group)
                        got += (held_fact.subject if held_fact.subject in anatomy else None,)
                        expected += (asked,)
                        asked_n += asked is not None
                        # the stomas passed: every entry whose type may be a stoma as filed (facts.possibly) - only the
                        # supported through's when the route is certain, never its id where its entry may be none
                        stomas = [entry for entry in anatomy if type_facts[entry] is None
                                  or AT.STOMA in possibly_values(type_facts[entry], AT)]
                        if through is not None and not uncertain:
                            stomas = [entry for entry in stomas if entry == target]
                        got += (list(evaluate._stomas_passed(R, X1)),)
                        expected += (stomas,)
                    if got != expected:
                        wrong.append((family, state, str(target_type), expected, got))
                    checked += 1
                    held_n += contradicted
        self.assertEqual(wrong[:20], [])
        self.assertTrue(0 < held_n < checked)
        self.assertTrue(0 < asked_n)
        # completeness: every type the through may name, the own entry, an id with no entry and a silent through
        self.assertEqual(targets, {*AT, 'the own entry', 'no entry', 'silent'})
