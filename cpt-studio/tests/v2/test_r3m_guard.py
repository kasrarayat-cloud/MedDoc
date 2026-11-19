"""Round r3's round 7 (DECISIONS D342 (1); build-v2/a2b/r3b/r3m/int9/NOTES.md): THE GUARD'S RELEASE READS ONE PREDICATE
OVER SETTLE'S OUTCOME. TEXT-ONLY and SYNTHETIC: every note is written for these tests or is the fifth adversarial pass's
or the final check's constructed input word for word (r3i/attack: test_l4p8_refute.py, test_l5r3i_attack.py,
test_l9_refute.py, the L6 oracle's e2e scripts and the verifiers' scripts; r3i/final-check/probes: e2e_q1.py,
fc_probe.py; fictional clinicians), every pass-1 answer is built by hand with test_settle's builders and every pass-2
answer by test_settle's faithful oracle (or that oracle with the claims a finding names answered as named), every other
FactSet in code; nothing is sent.

The rule (D342 (1)):
- (a) ONE PREDICATE over settle's outcome (evaluate.settled_narrows) for every claim a release decides on - a subtype, an
  absence's organ, a controlled type, any claim a harmless row reads - and for every reader built on it (_may_be,
  _possibly_settled: release_reading, harmless_row, harmless, path_guard, R5R-9's clauses, the per-anus clause): a claim
  narrows the reading only when ESTABLISHED through its control (3.3 row 8) or UNAPPRAISED (row 6: pass 2 never asked and
  pass 1 had no doubt - D340 Q1); every other state reads at its WIDEST, whatever its reason;
- (b) A FILED FIELD NAMES ITS SHAPE: a filed joins list names an anastomosis whatever the entry's uncontrolled type, its
  unnamed ends every landmark or the subtype's own; an absence's organ claim decides nothing about its joins (the absent
  rows admit none); only a controlled type established as a shape of its own reads its list otherwise;
- (c) THE ROUTE'S OWN ENTRY is read in the hold direction like every other entry: its organ, subtype and joins, read by
  (a) and (b), within its type's own anatomy (catalogue.ROUTE_OWN), or the route is not certain;
- (d) the censuses below.

- FindingTests: every confirmed finding of the fifth pass (L4P8-1, L5R8-1, L6R-1, L6R-3, L9-1, L9-2), its two lows on
  verification that the rule closes (L4P8-2, with L9-3 - the same class; L6R-2 is D340 Q1's own carve-out and stays READY,
  ControlTests), L4P8-3, and the final check's findings 1 and 2, each on its own input: RED on int8 (57b48228's
  evaluate.py 110562044a2e; r3m/int9/red/), GREEN on int9 - held with the table's own hold, 0 questions asked for it.
- SettledStateCensusTests: settle's WHOLE outcome table (settle.appraise x settle.decide: every claim verdict x every
  control verdict, attached or not, every qualifier; a failed check, pass 1's qualifier, a pass-1 doubt or
  contradiction, indistinct cards, a silent slot, unappraised; each for a supported and a negated claim) x every
  controlled claim (every controlled subtype, every absence organ, every controlled type) and the claims a harmless row
  reads beside them (a gastric pouch's organ, an anastomosis's type and joins members) x every route family; the
  completeness test derives the table from settle itself.
- JoinsCensusTests: every anatomy type (established, claimed, at its widest) x a joins list of 0, 1 and 2 members over
  every landmark x the subtype silent or every subtype x every route family, against the declared reading of (b).
- RouteOwnEntryCensusTests: every through family's own entry x its organ, subtype and joins in every state x the through's
  states, against the declared own anatomy of (c).
- UnnamedEndTests: mutant FC.b2 (a one-member list's unnamed end dropped) killed in this module.
- ControlTests: the development filings and D340 Q1's unappraised claims stay as int8 decides them.
"""
from __future__ import annotations

import itertools
from dataclasses import replace

from django.test import SimpleTestCase

from studio.interpretation.contract import claims as CL
from studio.interpretation.contract import settle
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import catalogue, evaluate
from studio.interpretation.engine.types import Id
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_r2cl_lesion as R2CL
from tests.v2 import test_r3f_rules as R3F
from tests.v2 import test_r3g_rules as G
from tests.v2 import test_r3i_guard as T
from tests.v2.test_settle import answer, event, fact, faithful, frame, labelled, opening, session, src, verdict

A, LM, EX, AT, AP, SUB, SK, Kind, RS = (ct.Attribute, ct.Landmark, ct.Extent, ct.AnatomyType, ct.Approach,
                                        ct.AnastomosisSubtype, ct.SessionKind, ct.Kind, ct.Reason)
V, ATT, Q2, FS, Res = ct.VerdictValue, ct.Attached, ct.Qualifier2, ct.FactState, ct.Result
sup, unres, neg = EF.sup, EF.unres, EF.neg
UN = RS.UNAPPRAISED
X1, E2 = Id.parse('X1'), Id.parse('E2')
Y1, Y2, Y7 = Id.parse('Y1'), Id.parse('Y2'), Id.parse('Y7')
HELD, READY, ROUTE = G.HELD, G.READY, G.ROUTE
entry_of = R3F.entry_of
held_by_route = T.held_by_route
FAMILIES = G.FAMILIES


def assessed(R, code, number=2) -> tuple:
    return G.assessed(R, str(code), number)


# === settle's outcome table, DERIVED FROM SETTLE ITSELF (settle.appraise, settle.decide) ===============================

OTHER_CHECK = RS.GEOMETRY_STATEMENT          # a check of S2, I1-I4, G1-G6, K1-K8 or L1 that failed (3.3 row 4)
PASS1_QUALIFIER = RS.QUALIFIED_HEDGED        # Q1: pass 1's own qualifier (row 5)


def claim_verdicts():
    """Every verdict pass 2 may give a claim, as settle.appraise reads it: none (missing); each verdict value x each
    attached value x the qualifiers it may name (none; each one) - a qualifier is read only beside supports and
    qualified."""
    yield None
    for value in V:
        for attached in ATT:
            qualifiers = [()] + ([(q,) for q in Q2] if value in (V.SUPPORTS, V.QUALIFIED) else [])
            for named in qualifiers:
                yield ct.Verdict('c1', value, attached, named, ())


CONTROL_VERDICTS = (None, *V)


def pair_outcomes():
    """settle.appraise over every claim verdict x every control verdict x attached evidence or not: each distinct
    (outcome, reasons) pair outcome with the control verdict that gave it (whether the control was rejected decides
    whether its value stays an option: facts._Context.control_value)."""
    seen = {}
    for claim_v, control_v, attached_evidence in itertools.product(claim_verdicts(), CONTROL_VERDICTS, (True, False)):
        outcome, reasons = settle.appraise(claim_v, attached_evidence, True, control_v)
        rejected = control_v is V.CONTRADICTS
        seen.setdefault((outcome, reasons, rejected), (claim_v, control_v, attached_evidence))
    return seen


def _case(state, *, sides=False, doubts=frozenset(), joined=False, findings=(), claimed=True, indistinct=False,
          pair=settle.PairOutcome.ESTABLISHED, pair_reasons=()):
    return settle.Case(state=state, sides=sides, doubts=frozenset(doubts), joined=joined, findings=tuple(findings),
                       claimed=claimed, indistinct=indistinct, pair=pair, pair_reasons=tuple(pair_reasons))


def settled_cases():
    """(label, settle.Case, the control's value stays an option, a pass-1 side or doubt reading is an option) for every
    row of 3.3's table: rows 6-9 over every pair outcome settle.appraise gives (pair_outcomes) for a supported and for a
    negated claim; rows 1-5 and 7 by their own inputs."""
    for state in (FS.SUPPORTED, FS.NEGATED):
        for (outcome, reasons, rejected), _inputs in pair_outcomes().items():
            yield (f'{state.value} {outcome.value} {",".join(r.value for r in reasons)} control '
                   f'{"rejected" if rejected else "not rejected"}',
                   _case(state, pair=outcome, pair_reasons=reasons), not rejected, False)
        yield f'{state.value} unappraised', _case(state, claimed=False, pair=None), False, False
        yield f'{state.value} cards indistinct', _case(state, indistinct=True), False, False
        yield (f'{state.value} cards indistinct, control not rejected',
               _case(state, indistinct=True, pair=settle.PairOutcome.INCOHERENT,
                     pair_reasons=(RS.CONTROL_INCOHERENT,)), True, False)
        yield f'{state.value} a failed check', _case(state, findings=(OTHER_CHECK,)), False, False
        yield f'{state.value} pass 1 qualified', _case(state, findings=(PASS1_QUALIFIER,)), False, False
        for basis in (ct.DoubtBasis.STATED, ct.DoubtBasis.UNCLEAR):
            yield f'{state.value} a pass-1 doubt ({basis.value})', _case(state, doubts={basis}), False, True
        yield f'{state.value} a pass-1 conflict doubt', _case(state, doubts={ct.DoubtBasis.CONFLICT}), False, True
        yield f'{state.value} joined (K8)', _case(state, joined=True), False, False
    yield 'pass 1 contradicted, its sides passing', _case(FS.CONTRADICTED, sides=True), False, True
    yield 'pass 1 contradicted, a side failing integrity', _case(FS.CONTRADICTED, sides=False), False, True
    yield 'a silent slot', _case(None, claimed=False, pair=None), False, False


def settled_fact(case, value, control_value, other, control_option, side_option):
    """The engine Fact settle's outcome for ``case`` stores for a claim at ``value`` (facts._fact's reading of it): the
    result and reasons settle.decide gives; the options - the control's value where the control was not rejected (and
    the fact is not established), a pass-1 side or doubt's reading (``other``) where it names one; a contradicted claim's
    value is its first side."""
    result, reasons = settle.decide(case)
    options = []
    if result not in (Res.SUPPORTED, Res.NEGATED):
        if side_option and other is not None:
            options.append(other)
        if control_option and control_value is not None and control_value != value:
            options.append(control_value)
    state = case.state
    if state is None:
        return EF.fact(result, None, None, reasons=reasons)
    if state is FS.CONTRADICTED:
        return EF.fact(result, None, state, options=(value, *options), reasons=reasons)
    return EF.fact(result, value, state, options=tuple(options), reasons=reasons)


def settled_states(value, control_value, other):
    """(label, row, engine Fact, decides) for every outcome of settle's table for a claim at ``value``: ``decides``
    (DECLARED from D342 (1) (a)) - the claim narrows the reading to ``value`` exactly when it is established supported
    (row 8, a supported claim) or unappraised (row 6) supported; an established or unappraised NEGATED claim names no
    value, and every other row reads at its widest."""
    for label, case, control_option, side_option in settled_cases():
        row = settle.row(case)
        found = settled_fact(case, value, control_value, other, control_option, side_option)
        decides = case.state is FS.SUPPORTED and row in (6, 8)
        yield label, row, found, decides


# The controlled claims (D342 (1) (a)): every controlled subtype (its control its sibling, 3.2.3), every absence organ
# (controlled by its own negation: no other value), every controlled type (its sibling type)
def controlled_claims():
    for value in sorted(catalogue.CONTROLLED_SUBTYPES, key=lambda s: s.value):
        yield (f'subtype {value.value}', CL.SUBTYPE_SIBLINGS[value], SUB.ILEORECTAL if value is not SUB.ILEORECTAL
               else SUB.OTHER, lambda f: entry_of(type=sup(AT.ANASTOMOSIS), subtype=f), value)
    for organ in sorted(LM, key=lambda place: place.value):
        yield (f'absence organ {organ.value}', organ, LM.COLON if organ is not LM.COLON else LM.RECTUM,
               lambda f: entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=f), organ)
    for typ in sorted(catalogue.CONTROLLED_TYPES, key=lambda t: t.value):
        yield (f'type {typ.value}', CL.TYPE_SIBLINGS[typ], AT.SURGICALLY_ABSENT,
               lambda f, typ=typ: entry_of(type=f, organ=sup(LM.STOMACH) if typ is AT.GASTRIC_POUCH else None), typ)


# Claims a harmless row reads beside a controlled one (read only to hold). Round r3's round 7 fixes (DECISIONS D345 (3),
# 2026-11-19; the final check's finding 4: int9 listed three by hand - a gastric pouch's organ, an anastomosis's type,
# an ileocolic anastomosis's joins member): EVERY claim a harmless row reads, DERIVED from catalogue.HARMLESS - for
# every family's every row, its controlled claim at each value it releases on, its filed organ at each place it admits
# (the absence row's organ is its claim), a joins member at each place it admits, and the type it is filed with - each
# beside the row's own entry at its first value (one claim per distinct shape, field and value).
def _row_entry(row, value):
    if row.decided_by is A.TYPE:
        return {A.TYPE: (sup(value),)}
    if row.decided_by is A.ORGAN:
        return {A.TYPE: (sup(catalogue.ABSENCE_TYPE),), A.ORGAN: (sup(value),)}
    return {A.TYPE: (sup(catalogue.SUBTYPE_TYPE),), A.SUBTYPE: (sup(value),)}


def _claim_entry(base, field, found):
    out = dict(base)
    if field is A.JOINS:
        out.pop(A.JOINS, None)
        if found is not None:
            out[A.JOINS] = (found,)
    elif found is None:
        out.pop(field, None)
    else:
        out[field] = (found,)
    return out


def read_claims():
    seen = {}
    for _needs, rows in catalogue.HARMLESS.items():
        for row in rows:
            first = sorted(row.values, key=lambda v: v.value)[0]
            claims = [(row.decided_by, value) for value in row.values]
            if row.decided_by is not A.ORGAN:
                claims += [(A.ORGAN, place) for place in row.organs]
            claims += [(A.JOINS, place) for place in row.joins]
            claims += [(A.TYPE, row_type) for row_type in ((catalogue.ABSENCE_TYPE,) if row.decided_by is A.ORGAN
                                                         else (catalogue.SUBTYPE_TYPE,) if row.decided_by is A.SUBTYPE
                                                         else ())]
            for field, value in claims:
                base_value = value if field is row.decided_by else first
                key = (row.shape, field, value, base_value)
                if key in seen:
                    continue
                base = _row_entry(row, base_value)
                if field is A.TYPE:
                    control, other = CL.TYPE_SIBLINGS.get(value), (AT.STOMA if value is not AT.STOMA
                                                                    else AT.SURGICALLY_ABSENT)
                elif field is A.SUBTYPE:
                    control, other = CL.SUBTYPE_SIBLINGS.get(value), (SUB.ILEORECTAL if value is not SUB.ILEORECTAL
                                                                      else SUB.OTHER)
                elif field is A.ORGAN and row.decided_by is A.ORGAN:
                    control, other = value, (LM.COLON if value is not LM.COLON else LM.RECTUM)
                else:
                    control, other = None, (LM.COLON if value is not LM.COLON else LM.RECTUM)
                name = 'joins member' if field is A.JOINS else field.value
                seen[key] = (f'{row.shape.value}: {name} {value.value}', control, other,
                             lambda f, base=base, field=field: _claim_entry(base, field, f), value)
    yield from seen.values()


class SettledStateCensusTests(SimpleTestCase):
    """D342 (1) (d): settle's whole outcome table x every controlled claim (and the claims a harmless row reads beside
    them) x every route family - an entry is harmless exactly when the claim decides (established or unappraised) and the
    same entry with the claim established is harmless; every other settled state holds."""

    def test_every_controlled_claim_every_settled_state_every_family(self):
        # a silent slot (row 3) reads as the field not filed - for a field read only to hold (a gastric pouch's organ)
        # that files nothing; a joins member is never silent (an empty list has no member). Round r3's round 7 fixes
        # (DECISIONS D345 (3), 2026-11-19): every claim a harmless row reads, derived (read_claims); the states one
        # engine Fact per distinct outcome of settle's table for each claim (equal Facts read alike)
        R0 = G.bare()
        wrong, checked, released, widened = [], 0, 0, 0
        for label, control, other, make, value in (*controlled_claims(), *read_claims()):
            seen_facts = set()
            established = G.with_entry(R0, make(sup(value)))
            baseline = {family: evaluate.harmless(established, Y1, G.needs(family)) for family in FAMILIES}
            unfiled = G.with_entry(R0, make(None))
            silent = {family: evaluate.harmless(unfiled, Y1, G.needs(family)) for family in FAMILIES}
            for state, row, found, decides in settled_states(value, control, other):
                if row == 3 and 'joins member' in label:
                    continue
                if found in seen_facts:
                    continue
                seen_facts.add(found)
                R = G.with_entry(R0, make(found))
                for family in FAMILIES:
                    expected = silent[family] if row == 3 else decides and baseline[family]
                    if evaluate.harmless(R, Y1, G.needs(family)) != expected:
                        wrong.append((family, label, state, expected))
                    checked += 1
                    released += expected
                    widened += baseline[family] and not decides
        self.assertEqual(wrong[:20], [])
        self.assertGreater(checked, 35000)
        self.assertTrue(0 < released < checked)
        self.assertGreater(widened, 10000)   # int8: most of these were harmless (L4P8-1: 336 subtype x outcome x family)
        self.assertGreater(len(list(read_claims())), 300)   # int9: 3 claims listed by hand (D345 (3))

    def test_the_predicate_is_rows_6_and_8_of_settles_table(self):
        # one predicate over the settled result: it narrows exactly on settle's rows 6 (unappraised) and 8 (established),
        # whatever the reasons of any other row (never a list of the reasons it widens)
        rows = set()
        for _label, row, found, _decides in settled_states(SUB.ILEOCOLIC, SUB.COLOCOLIC, SUB.ILEORECTAL):
            rows.add(row)
            with self.subTest(row=row, reasons=[r.value for r in found.reasons], result=found.result.value):
                self.assertEqual(evaluate.settled_narrows(found), row in (6, 8))
        self.assertEqual(rows, set(range(1, 10)))

    def test_the_census_is_settles_whole_outcome_table(self):
        # completeness, derived from settle itself: every row of 3.3's table, every pair outcome of 3.2.3's coherence
        # table and every reason settle.appraise and settle.decide give are among the census's states
        cases = list(settled_cases())
        self.assertEqual({settle.row(case) for _l, case, _c, _s in cases}, set(range(1, 10)))
        outcomes = {outcome for outcome, _reasons, _rejected in pair_outcomes()}
        self.assertEqual(outcomes, set(settle.PairOutcome))
        reasons = {reason for _o, found, _r in pair_outcomes() for reason in found}
        expected = ({RS.APPRAISAL_MISSING, RS.APPRAISAL_UNCLEAR, RS.APPRAISAL_CONTRADICTS, RS.APPRAISAL_DETACHED,
                     RS.CONTROL_INCOHERENT, RS.APPRAISAL_QUALIFIED} | set(settle.APPRAISAL_QUALIFIED.values()))
        self.assertEqual(reasons, expected)
        decided = {settle.decide(case) for _l, case, _c, _s in cases}
        results = {result for result, _reasons in decided}
        self.assertEqual(results, {Res.SUPPORTED, Res.NEGATED, Res.UNRESOLVED, Res.UNKNOWN, Res.CONTRADICTED})
        self.assertLessEqual({RS.CONTRADICTED_BY_PASS1, RS.DOUBT_STATED, RS.DOUBT_UNCLEAR, RS.SILENT, OTHER_CHECK,
                              PASS1_QUALIFIER, RS.UNAPPRAISED, RS.CARDS_INDISTINCT} | reasons,
                             {reason for _result, found in decided for reason in found})
        # every row a pass-1 claim can reach appears for a supported and for a negated claim; the silent slot is row 3
        for state in (FS.SUPPORTED, FS.NEGATED):
            rows = {settle.row(case) for _l, case, _c, _s in cases if case.state is state}
            self.assertEqual(rows, {1, 2, 4, 5, 6, 7, 8, 9})
        self.assertEqual({settle.row(case) for _l, case, _c, _s in cases if case.state is None}, {3})
        self.assertEqual({settle.row(case) for _l, case, _c, _s in cases if case.state is FS.CONTRADICTED}, {1, 4})

    def test_every_family_end_to_end_on_a_state_of_each_row(self):
        # the assembled engine, beside each family's own control: one value of each controlled claim kind in every
        # settled state - READY only where the claim decides and the established entry is READY; else the table's hold
        claims = {'subtype': (SUB.ILEOCOLIC, SUB.COLOCOLIC, SUB.ILEORECTAL,
                              lambda f: entry_of(type=sup(AT.ANASTOMOSIS), subtype=f)),
                  'pouch subtype': (SUB.ILEOANAL, SUB.ILEORECTAL, SUB.OTHER,
                                    lambda f: entry_of(type=sup(AT.ANASTOMOSIS), subtype=f)),
                  'absence organ': (LM.SIGMOID_COLON, LM.SIGMOID_COLON, LM.COLON,
                                    lambda f: entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=f)),
                  'absence organ gallbladder': (LM.GALLBLADDER, LM.GALLBLADDER, LM.COLON,
                                                lambda f: entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=f)),
                  'type gastric pouch': (AT.GASTRIC_POUCH, AT.ILEAL_POUCH, AT.SURGICALLY_ABSENT,
                                         lambda f: entry_of(type=f, organ=sup(LM.STOMACH)))}
        wrong, checked = [], 0
        for family in FAMILIES:
            for name, (value, control, other, make) in claims.items():
                R, code, number = G.family_control(family, {Y7: make(sup(value))})
                base = assessed(R, code, number)
                seen = set()
                for state, row, found, decides in settled_states(value, control, other):
                    key = (row, found.result, found.reasons, bool(found.options), found.state)
                    if key in seen:
                        continue
                    seen.add(key)
                    R, code, number = G.family_control(family, {Y7: make(found)})
                    got = assessed(R, code, number)
                    expected_ready = decides and base == (READY, ())
                    if (got == (READY, ())) != expected_ready or (not expected_ready and base == (READY, ())
                                                                  and ROUTE not in got[1]):
                        wrong.append((family, name, state, got))
                    checked += 1
        self.assertEqual(wrong[:20], [])
        self.assertGreater(checked, 300)


# === the findings =====================================================================================================

HEAD = T.HEAD
FD_ANAST = 'The colonoscope was inserted per anus, advanced to the anastomosis and into the neo-terminal ileum.'
FD_THROUGH = 'The colonoscope was inserted per anus, advanced through the anastomosis and into the neo-terminal ileum.'
BX_NTI = 'Two biopsies of the neo-terminal ileum were taken with cold forceps.'


def subtype_oracle(claim_v, control_v):
    """test_settle.faithful, but the anastomosis's subtype claim and its sibling control answered as given (None: no
    verdict); each verdict a string, or a (value, qualifiers) pair."""
    def given(claim, found):
        if found is None:
            return None
        if isinstance(found, tuple):
            return verdict(claim, found[0], qualifiers=found[1])
        return verdict(claim, found)

    def answer_(claim, role, claim_set):
        if claim.template == 'anatomy.subtype':
            if role == 'claim':
                return given(claim, claim_v)
            if role == 'control':
                return given(claim, control_v)
        return faithful(claim, role, claim_set)
    return answer_


def colectomy_note(history, words, findings=FD_ANAST, *, joins=(), named_words='to the anastomosis'):
    """L4P8-1's note (test_l4p8_refute.colectomy_note): a per-anus colonoscopy whose reached_anatomy names the
    anastomosis Y1 (pass 2 is asked its type and subtype); pass 1 files the subtype ileocolic."""
    return T.reached_note(history, findings, BX_NTI, subtypes=['ileocolic'], joins=list(joins), words=words,
                          reached=[('neo_terminal_ileum', 'into the neo-terminal ileum')],
                          reached_anatomy_words=named_words, place='neo_terminal_ileum',
                          place_words='neo-terminal ileum')


def colonoscopy_note(history, words, typ, *, organs=(), subtypes=(), joins=(), named=True):
    """L9's note (test_l9_refute.colonoscopy_note), word for word: a per-anus colonoscopy to the neo-terminal ileum, its
    reached_anatomy naming Y1 when ``named``, a cold-forceps biopsy E2; one anatomy entry Y1 of ``typ``."""
    text = HEAD + f'History: {history}\n' + f'Findings: {FD_THROUGH}\n' + f'{BX_NTI}\n'
    assert words in text
    entries = [{'id': 'Y1', 'type': fact(typ, src(['S4'], words)),
                'organ': [fact(value, src(['S4'], words)) for value in organs],
                'subtype': [fact(value, src(['S4'], words)) for value in subtypes],
                'joins': [fact(value, src(['S4'], words)) for value in joins]}]
    fields = dict(examination=[fact('E1', src(['S5']))], encounter=[fact('this_encounter', frame(['S2']))],
                  approach=[fact('transanal', src(['S5'], 'inserted per anus'))],
                  reached=[fact('neo_terminal_ileum', src(['S5'], 'into the neo-terminal ileum'))])
    if named:
        fields['reached_anatomy'] = [fact('Y1', src(['S5'], 'through the anastomosis'))]
    sess = session('X1', fact('colonoscopy', src(['S5'], 'colonoscope')), **fields)
    events = [event('E1', ['S5'], 'colonoscope', 'was inserted', 'examination', session=[fact('X1', src(['S5']))]),
              event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                    target__places=[fact('neo_terminal_ileum', src(['S6'], 'neo-terminal ileum'))],
                    technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])]
    data = answer(sections=[opening(), labelled('N1', 'S4', 'History:', 'history'),
                            labelled('N2', 'S5', 'Findings:', 'findings')],
                  sessions=[sess], anatomy=entries, events=events)
    return text, data


def proctectomy_note(history, organ, joins, stations):
    """L6R-3's note (attack/L6-oracle/e2e/e2e_absent_join.run), word for word: pass 1 files a proctectomy with an ileal
    anastomosis as ONE entry - surgically absent, organ ``organ``, joins ``joins`` - beside a per-anus colonoscopy into
    the neo-terminal ileum (the stations name the rectum, so the absence is claimed, or not)."""
    fd = 'The colonoscope was inserted per anus and advanced into the neo-terminal ileum.'
    text = HEAD + f'History: {history}\n' + f'Findings: {fd}\n' + f'{BX_NTI}\n'
    words = 'Proctectomy with an ileal anastomosis'
    entries = [{'id': 'Y1', 'type': fact('surgically_absent', src(['S4'], words)),
                'organ': [fact(organ, src(['S4'], words))], 'subtype': [],
                'joins': [fact(v, src(['S4'], words)) for v in joins]}]
    sess = session('X1', fact('colonoscopy', src(['S5'], 'colonoscope')), examination=[fact('E1', src(['S5']))],
                   encounter=[fact('this_encounter', frame(['S2']))],
                   approach=[fact('transanal', src(['S5'], 'inserted per anus'))],
                   reached=[fact('neo_terminal_ileum', src(['S5'], 'into the neo-terminal ileum'))],
                   stations=[fact(s, src(['S5'], 'inserted per anus')) for s in stations])
    events = [event('E1', ['S5'], 'colonoscope', 'was inserted', 'examination', session=[fact('X1', src(['S5']))]),
              event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                    target__places=[fact('neo_terminal_ileum', src(['S6'], 'neo-terminal ileum'))],
                    technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])]
    data = answer(sections=[opening(), labelled('N1', 'S4', 'History:', 'history'),
                            labelled('N2', 'S5', 'Findings:', 'findings')], sessions=[sess], anatomy=entries,
                  events=events)
    return text, data


def rhc_note():
    """The final check's e2e_q1.note, word for word: a right hemicolectomy's ileocolic anastomosis Y1 [ileum, colon] that
    the colonoscope's reach names; 45380 and 45378 proposed."""
    text = (HEAD + 'History: Right hemicolectomy with an ileocolic anastomosis in 2025.\n'
            + 'Findings: The colonoscope was inserted per anus, advanced to what appeared to be the ileocolic anastomosis '
              'and into the neo-terminal ileum.\n' + f'{BX_NTI}\n')
    words = 'ileocolic anastomosis'
    entries = [{'id': 'Y1', 'type': fact('anastomosis', src(['S4'], words)), 'organ': [],
                'subtype': [fact('ileocolic', src(['S4'], words))],
                'joins': [fact(value, src(['S4'], words)) for value in ('ileum', 'colon')]}]
    sess = session('X1', fact('colonoscopy', src(['S5'], 'colonoscope')),
                   examination=[fact('E1', src(['S5']))], encounter=[fact('this_encounter', frame(['S2']))],
                   approach=[fact('transanal', src(['S5'], 'inserted per anus'))],
                   reached=[fact('neo_terminal_ileum', src(['S5'], 'into the neo-terminal ileum'))],
                   reached_anatomy=[fact('Y1', src(['S5'], 'the ileocolic anastomosis'))])
    events = [event('E1', ['S5'], 'colonoscope', 'was inserted', 'examination', session=[fact('X1', src(['S5']))]),
              event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                    target__places=[fact('neo_terminal_ileum', src(['S6'], 'neo-terminal ileum'))],
                    technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])]
    data = answer(sections=[opening(), labelled('N1', 'S4', 'History:', 'history'),
                            labelled('N2', 'S5', 'Findings:', 'findings')],
                  sessions=[sess], anatomy=entries, events=events)
    return text, data


def row9(value, control):
    """test_l9_refute.row9: each 3.3 row-9 outcome of a controlled claim at ``value`` whose control names ``control``."""
    return {
        'claim unclear, control rejected': unres(value, RS.APPRAISAL_UNCLEAR),
        'claim unclear, control unclear': unres(value, RS.APPRAISAL_UNCLEAR, options=(control,)),
        'claim qualified (hedged), control rejected': unres(value, RS('appraisal_qualified:hedged')),
        'claim contradicted, control unclear or supported': unres(value, RS.APPRAISAL_CONTRADICTS, options=(control,)),
        'claim and control both supported (incoherent)': unres(value, RS.CONTROL_INCOHERENT, options=(control,)),
        'claim verdict missing, control rejected': unres(value, RS.APPRAISAL_MISSING),
        'claim detached (no evidence attached), control rejected': unres(value, RS.APPRAISAL_DETACHED),
    }


class FindingTests(SimpleTestCase):
    """Each finding on its own input: RED on int8 (every assertion marked 'int8:' gave READY there), GREEN on int9 - held
    with the table's own hold."""

    def test_l4p8_1_every_not_established_pair_outcome_of_a_controlled_subtype_holds(self):
        released = []
        for value in sorted(CL.SUBTYPE_SIBLINGS, key=lambda s: s.value):
            for (outcome, reasons, rejected), _inputs in pair_outcomes().items():
                if outcome is settle.PairOutcome.ESTABLISHED:
                    continue
                options = () if rejected else (CL.SUBTYPE_SIBLINGS[value],)
                found = EF.fact(Res.UNRESOLVED, value, FS.SUPPORTED, options=options, reasons=reasons)
                entry = entry_of(type=sup(AT.ANASTOMOSIS), subtype=found)
                for family in FAMILIES:
                    R, code, number = G.family_control(family, {Y7: entry})
                    if evaluate.harmless(R, Y7, G.needs(family)):
                        released.append((value.value, outcome.value, family))
        self.assertEqual(sorted(set(released))[:12], [])    # int8: 336 (subtype, outcome, family) released

    def test_l4p8_1_end_to_end_a_colectomy_anastomosis_pass_2_did_not_establish_holds_45380(self):
        for history, words in (('Subtotal colectomy with a primary anastomosis in 2025.', 'primary anastomosis'),
                               ('Subtotal colectomy with an ileorectal anastomosis in 2025.', 'ileorectal anastomosis')):
            text, data = colectomy_note(history, words)
            for name, (claim_v, control_v) in {
                    'claim unclear, control unclear (an honest reader of an unnamed subtype)': ('unclear', 'unclear'),
                    'claim contradicts, control unclear': ('contradicts', 'unclear'),
                    'claim contradicts, control supports': ('contradicts', 'supports'),
                    'claim unclear, control contradicts': ('unclear', 'contradicts'),
                    'claim supports, control supports (control_incoherent: a yes-bias)': ('supports', 'supports')}.items():
                with self.subTest(history=history, pass2=name):
                    held_by_route(self, R2CL.outcomes(text, data, subtype_oracle(claim_v, control_v),
                                                      ('45380', BX_NTI))['45380'][:2])    # int8: ('ready', ())

    def test_l5r8_1_an_appraised_subtype_or_absence_organ_not_established_decides_no_release(self):
        shapes = {'anastomosis, subtype ileocolic': lambda f: entry_of(type=sup(AT.ANASTOMOSIS), subtype=f(SUB.ILEOCOLIC)),
                  'absence, organ cecum': lambda f: entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=f(LM.CECUM))}
        states = {'unclear': RS.APPRAISAL_UNCLEAR, 'qualified': RS.APPRAISAL_QUALIFIED, 'detached': RS.APPRAISAL_DETACHED,
                  'missing': RS.APPRAISAL_MISSING, 'control incoherent': RS.CONTROL_INCOHERENT}
        for shape, make in shapes.items():
            for state, reason in states.items():
                R = R3F.scope(45380, approach=sup(AP.TRANSANAL), entries={Y1: make(lambda v: unres(v, reason))})
                with self.subTest(shape=shape, state=state):
                    held_by_route(self, assessed(R, '45380'))    # int8: ('ready', ())
        # end to end: a subtotal colectomy's join misfiled ileocolic, pass 2 asked and answering unclear
        text, data = colectomy_note('Subtotal colectomy with an anastomosis in 2025.', 'an anastomosis')
        held_by_route(self, R2CL.outcomes(text, data, subtype_oracle('unclear', 'contradicts'),
                                          ('45380', BX_NTI))['45380'][:2])    # int8 (and int7): ('ready', ())

    def test_l6r_1_an_honest_unclear_or_incoherent_pass_2_holds_45380(self):
        oracles = {'subtype UNCLEAR, control colocolic rejected': subtype_oracle('unclear', 'contradicts'),
                   'subtype UNCLEAR, control colocolic unclear': subtype_oracle('unclear', 'unclear'),
                   'subtype claim AND control supported (incoherent)': subtype_oracle('supports', 'supports')}
        for history in ('Subtotal colectomy with an ileal anastomosis in 2025.',
                        'Colectomy with an ileal anastomosis in 2025.'):
            for joins in ((), ('ileum',)):
                text, data = colectomy_note(history, 'ileal anastomosis', FD_THROUGH, joins=joins,
                                            named_words='through the anastomosis')
                for name, oracle in oracles.items():
                    with self.subTest(history=history, joins=joins, pass2=name):
                        held_by_route(self, R2CL.outcomes(text, data, oracle, ('45380', BX_NTI))['45380'][:2])
                # the faithful pass 2 establishes the ileocolic subtype: READY
                self.assertEqual(R2CL.outcomes(text, data, R2CL.FAITHFUL, ('45380', BX_NTI))['45380'][:2], (READY, ()))

    def test_l9_1_a_controlled_claim_pass_2_did_not_establish_decides_no_release(self):
        for family in ('COLON', 'RECTUM_AND_SIGMOID', 'COLONIC_STOMA', 'ILEAL_STOMA'):
            for value, control in ((SUB.ILEOCOLIC, SUB.COLOCOLIC), (SUB.COLORECTAL, SUB.COLOANAL)):
                for name, state in row9(value, control).items():
                    R, code, number = G.family_control(family, {Y7: entry_of(type=sup(AT.ANASTOMOSIS), subtype=state)})
                    with self.subTest(family=family, subtype=value.value, pass2=name):
                        held_by_route(self, assessed(R, code, number))    # int8: READY
        for name, state in row9(SUB.ILEOANAL, SUB.ILEORECTAL).items():
            R, code, number = G.family_control('POUCH', {Y7: entry_of(type=sup(AT.ANASTOMOSIS), subtype=state)})
            with self.subTest(family='POUCH', pass2=name):
                held_by_route(self, assessed(R, code, number))    # int8: READY
        for code in (45391, 45341, 44406):
            for name, state in row9(SUB.ILEOCOLIC, SUB.COLOCOLIC).items():
                entry = entry_of(type=sup(AT.ANASTOMOSIS), subtype=state)
                R = (G.met_scope(code, {Y7: entry}) if code == 44406 else
                     R3F.scope(code, approach=sup(AP.TRANSANAL), entries={Y1: entry}))
                with self.subTest(code=code, pass2=name):
                    self.assertTrue(evaluate.decide(str(code), (), R).held_facts)    # int8: none
        entries = {f'the sigmoid colon absent, organ: {name}': entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=state)
                   for name, state in row9(LM.SIGMOID_COLON, LM.SIGMOID_COLON).items()}
        entries.update({f'a gastric pouch, type: {name}': entry_of(type=state)
                        for name, state in row9(AT.GASTRIC_POUCH, AT.ILEAL_POUCH).items()})
        for name, entry in entries.items():
            for family in ('COLON', 'RECTUM_AND_SIGMOID'):
                R, code, number = G.family_control(family, {Y7: entry})
                with self.subTest(family=family, entry=name):
                    held_by_route(self, assessed(R, code, number))    # int8: READY (but the unrejected ileal pouch)
        # end to end: "Colectomy for ulcerative colitis with an ileal anastomosis" - an IRA, an IPAA or an ileocolic
        # join; pass 1 claims ileocolic; pass 2 cannot confirm it
        text, data = colonoscopy_note('Colectomy for ulcerative colitis with an ileal anastomosis in 2027.',
                                      'ileal anastomosis', 'anastomosis', subtypes=['ileocolic'])
        for name, oracle in (('claim unclear', subtype_oracle('unclear', 'contradicts')),
                             ('claim contradicted, control unclear', subtype_oracle('contradicts', 'unclear')),
                             ('claim and control supported', subtype_oracle('supports', 'supports'))):
            with self.subTest(pass2=name):
                held_by_route(self, R2CL.outcomes(text, data, oracle, ('45380', BX_NTI))['45380'][:2])    # int8: READY

    def test_l6r_3_and_l9_2_an_absence_filing_a_join_holds(self):
        # L6R-3: an absence filing one end of an ileal join, every organ of the colon and rectum, supported or claimed,
        # beside the colonoscopy, the sigmoidoscopy (EUS included) and the colonoscopy through a stoma
        for organ in (LM.RECTUM, LM.SIGMOID_COLON, LM.LEFT_COLON):
            for member in (LM.ILEUM, LM.SMALL_BOWEL, LM.TERMINAL_ILEUM, LM.NEO_TERMINAL_ILEUM):
                for state in (sup, lambda v: unres(v, UN)):
                    entry = entry_of(type=state(AT.SURGICALLY_ABSENT), organ=state(organ), joins=(sup(member),))
                    for code in (45380, 45331, 45342, 45392):
                        R = R3F.scope(code, approach=sup(AP.TRANSANAL), entries={Y1: entry})
                        with self.subTest(organ=organ.value, member=member.value, code=code):
                            held_by_route(self, assessed(R, code))    # int8: READY
                    R, code, number = G.family_control('COLONIC_STOMA', {Y7: entry})
                    with self.subTest(organ=organ.value, member=member.value, code='44389'):
                        held_by_route(self, assessed(R, code, number))    # int8: READY
        # end to end: "Proctectomy with an ileal anastomosis" filed as ONE entry (absent rectum, joins [ileum])
        for stations in ((), ('rectum',)):
            text, data = proctectomy_note('Proctectomy with an ileal anastomosis in 2025.', 'rectum', ['ileum'],
                                          stations)
            with self.subTest(stations=stations):
                held_by_route(self, R2CL.outcomes(text, data, R2CL.FAITHFUL, ('45380', BX_NTI))['45380'][:2])
        # L9-2: an absence filing one end of an anastomosis, beside 45380, 45331 and the ileal stoma; an upper organ
        # joined below the colon on an absence (L6O-3's class through the absence type)
        for organ in (sup(LM.OTHER), unres(LM.TRANSVERSE_COLON, UN), sup(LM.SMALL_BOWEL), unres(LM.CECUM, UN)):
            for member in (LM.ILEUM, LM.SMALL_BOWEL, LM.TERMINAL_ILEUM):
                entry = entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=organ, joins=(sup(member),))
                for code in (45380, 45331):
                    R = R3F.scope(code, approach=sup(AP.TRANSANAL), entries={Y1: entry})
                    with self.subTest(organ=organ.value.value, member=member.value, code=code):
                        held_by_route(self, assessed(R, code))    # int8: READY
        for member in (LM.TERMINAL_ILEUM, LM.NEO_TERMINAL_ILEUM):
            entry = entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.COLON), joins=(sup(member),))
            R, code, number = G.family_control('ILEAL_STOMA', {Y7: entry})
            with self.subTest(family='ILEAL_STOMA', member=member.value):
                held_by_route(self, assessed(R, code, number))    # int8: READY
        for joins in ((LM.DUODENUM, LM.RECTUM), (LM.STOMACH, LM.RECTUM), (LM.COMMON_BILE_DUCT, LM.RECTUM)):
            entry = entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.SMALL_BOWEL), joins=tuple(sup(j) for j in joins))
            for code in (45380, 45331):
                R = R3F.scope(code, approach=sup(AP.TRANSANAL), entries={Y1: entry})
                with self.subTest(joins=[j.value for j in joins], code=code):
                    held_by_route(self, assessed(R, code))    # int8: READY
        for organ in ('other', 'transverse_colon'):
            for named in (True, False):
                text, data = colonoscopy_note('Colectomy with an ileal anastomosis in 2027.',
                                              'Colectomy with an ileal anastomosis', 'surgically_absent',
                                              organs=[organ], joins=['ileum'], named=named)
                with self.subTest(organ=organ, named=named):
                    held_by_route(self, R2CL.outcomes(text, data, R2CL.FAITHFUL, ('45380', BX_NTI))['45380'][:2])

    def test_l4p8_2_l9_3_and_final_check_2_the_routes_own_entry_filed_against_its_type_holds(self):
        own_pouch = {
            'organ claimed the stomach': entry_of(type=sup(AT.ILEAL_POUCH), organ=unres(LM.STOMACH, UN)),
            'organ claimed the esophagus': entry_of(type=sup(AT.ILEAL_POUCH), organ=unres(LM.ESOPHAGUS, UN)),
            'organ claimed the jejunum': entry_of(type=sup(AT.ILEAL_POUCH), organ=unres(LM.JEJUNUM, UN)),
            'organ supported the duodenum': entry_of(type=sup(AT.ILEAL_POUCH), organ=sup(LM.DUODENUM)),
            'organ claimed the colon': entry_of(type=sup(AT.ILEAL_POUCH), organ=unres(LM.COLON, UN)),
            'organ supported the rectum': entry_of(type=sup(AT.ILEAL_POUCH), organ=sup(LM.RECTUM)),
            'organ supported the anal canal': entry_of(type=sup(AT.ILEAL_POUCH), organ=sup(LM.ANAL_CANAL)),
            'subtype claimed gastrojejunal': entry_of(type=sup(AT.ILEAL_POUCH), subtype=unres(SUB.GASTROJEJUNAL, UN)),
            'subtype claimed coloanal (a colonic J-pouch)': entry_of(type=sup(AT.ILEAL_POUCH),
                                                                     subtype=unres(SUB.COLOANAL, UN)),
            'subtype claimed ileocolic': entry_of(type=sup(AT.ILEAL_POUCH), subtype=unres(SUB.ILEOCOLIC, UN)),
            'subtype claimed colorectal': entry_of(type=sup(AT.ILEAL_POUCH), subtype=unres(SUB.COLORECTAL, UN)),
            'joins [stomach, jejunum]': entry_of(type=sup(AT.ILEAL_POUCH), joins=(sup(LM.STOMACH), sup(LM.JEJUNUM))),
            'joins [colon, rectum]': entry_of(type=sup(AT.ILEAL_POUCH), joins=(sup(LM.COLON), sup(LM.RECTUM))),
            'subtype coloanal, joins [pouch, anal canal]': entry_of(type=sup(AT.ILEAL_POUCH), subtype=sup(SUB.COLOANAL),
                                                                     joins=(sup(LM.POUCH), sup(LM.ANAL_CANAL))),
        }
        for name, own in own_pouch.items():
            R, code, number = G.family_control('POUCH', {Y1: own})
            with self.subTest(family='POUCH', own=name):
                held_by_route(self, assessed(R, code, number))    # int8: READY
            for approach in (AP.THROUGH_POUCH, AP.TRANSANAL):
                with self.subTest(family='POUCH', own=name, approach=approach.value):
                    held_by_route(self, assessed(pouch_scene(own, approach), '44386'))    # int8: READY
        for family, organ in (('COLONIC_STOMA', unres(LM.SIGMOID_COLON, UN)), ('ILEAL_STOMA', unres(LM.ILEUM, UN))):
            for name, over in (('subtype claimed gastrojejunal', {'subtype': unres(SUB.GASTROJEJUNAL, UN)}),
                               ('subtype claimed ileocolic', {'subtype': unres(SUB.ILEOCOLIC, UN)}),
                               ('subtype supported ileoanal', {'subtype': sup(SUB.ILEOANAL)}),
                               ('joins [stomach, jejunum]', {'joins': (sup(LM.STOMACH), sup(LM.JEJUNUM))}),
                               ('joins [colon, rectum]', {'joins': (sup(LM.COLON), sup(LM.RECTUM))}),
                               ('joins [pouch, anal canal]', {'joins': (sup(LM.POUCH), sup(LM.ANAL_CANAL))})):
                own = entry_of(type=sup(AT.STOMA), organ=organ, **over)
                R, code, number = G.family_control(family, {Y1: own})
                with self.subTest(family=family, own=name):
                    held_by_route(self, assessed(R, code, number))    # int8: READY
        # the controls: each through family's own entry filed within its type's anatomy stays READY
        for family, own in (('POUCH', entry_of(type=sup(AT.ILEAL_POUCH))),
                            ('POUCH', entry_of(type=sup(AT.ILEAL_POUCH), organ=sup(LM.ILEUM),
                                               subtype=unres(SUB.ILEOANAL, UN), joins=(sup(LM.POUCH), sup(LM.ANAL_CANAL)))),
                            ('ILEAL_STOMA', entry_of(type=sup(AT.STOMA), organ=unres(LM.ILEUM, UN),
                                                     joins=(sup(LM.TERMINAL_ILEUM),))),
                            ('COLONIC_STOMA', entry_of(type=sup(AT.STOMA), organ=unres(LM.SIGMOID_COLON, UN),
                                                       joins=(sup(LM.SIGMOID_COLON),)))):
            R, code, number = G.family_control(family, {Y1: own})
            with self.subTest(control=family):
                self.assertEqual(assessed(R, code, number), (READY, ()))

    def test_l4p8_3_a_reach_member_pass_2_rejected_may_be_the_cecum(self):
        for member in (EX.TERMINAL_ILEUM, EX.ILEOCECAL_VALVE, EX.NEO_TERMINAL_ILEUM):
            for name, found in (('rejected', T.rejected(member)), ('unclear', unres(member, RS.APPRAISAL_UNCLEAR)),
                                ('a pass-1 doubt', EF.doubted(member, EX.ILEUM))):
                R = G.ileoscopy(None, reached=(sup(EX.ILEUM), found))
                with self.subTest(member=member.value, state=name):
                    self.assertTrue(evaluate.ileal_stoma_contradicted(R, X1))    # int8: False
                    self.assertEqual(assessed(R, '44382')[0], HELD)            # int8: ('ready', ())
        # an established reach (or an established denial: no point reached) stays as before
        for found in (sup(EX.TERMINAL_ILEUM), neg(EX.CECUM), unres(EX.TERMINAL_ILEUM, UN)):
            R = G.ileoscopy(None, reached=(sup(EX.ILEUM), found))
            with self.subTest(control=found.result.value):
                self.assertFalse(evaluate.ileal_stoma_contradicted(R, X1))

    def test_final_check_1_a_right_hemicolectomys_subtype_pass_2_did_not_establish_holds(self):
        text, data = rhc_note()
        variants = {
            'subtype claim unclear, control contradicted': subtype_oracle('unclear', 'contradicts'),
            'subtype claim supported but hedged, control contradicted': subtype_oracle(('supports', ('hedged',)),
                                                                                       'contradicts'),
            'subtype claim contradicted, sibling control colocolic supported': subtype_oracle('contradicts', 'supports'),
            'subtype claim and control both contradicted': subtype_oracle('contradicts', 'contradicts'),
        }
        for name, oracle in variants.items():
            found = R2CL.outcomes(text, data, oracle, ('45380', BX_NTI))
            with self.subTest(pass2=name):
                held_by_route(self, found['45380'][:2])    # int8: READY (but both contradicted)
        self.assertEqual(R2CL.outcomes(text, data, R2CL.FAITHFUL, ('45380', BX_NTI))['45380'][:2], (READY, ()))
        # the probe's FactSet half (fc_probe S4): beside 45380 and 45331
        subtype_states = {
            'ileocolic unclear (control rejected)': unres(SUB.ILEOCOLIC, RS.APPRAISAL_UNCLEAR),
            'ileocolic qualified, colocolic control unrejected': unres(SUB.ILEOCOLIC, RS.APPRAISAL_QUALIFIED,
                                                                       options=(SUB.COLOCOLIC,)),
            'ileocolic CONTRADICTED, colocolic control supported': unres(SUB.ILEOCOLIC, RS.APPRAISAL_CONTRADICTS,
                                                                         options=(SUB.COLOCOLIC,)),
            'ileocolic incoherent (claim and control supported)': unres(SUB.ILEOCOLIC, RS.CONTROL_INCOHERENT,
                                                                        options=(SUB.COLOCOLIC,)),
        }
        for family in ('COLON', 'RECTUM_AND_SIGMOID'):
            for label, subtype in subtype_states.items():
                R, code, number = G.family_control(family, {Y7: entry_of(type=sup(AT.ANASTOMOSIS), subtype=subtype)})
                with self.subTest(family=family, subtype=label):
                    held_by_route(self, assessed(R, code, number))    # int8: READY
            R, code, number = G.family_control(family, {Y7: entry_of(type=unres(AT.SURGICALLY_ABSENT, UN),
                                                                     organ=unres(LM.SIGMOID_COLON,
                                                                                 RS.APPRAISAL_UNCLEAR))})
            with self.subTest(family=family, absence='the sigmoid unclear'):
                held_by_route(self, assessed(R, code, number))    # int8: READY


def pouch_scene(own, approach=AP.THROUGH_POUCH):
    """test_l9_refute.pouch_scene: a pouchoscopy X1 through Y1 (``own``), approach ``approach``, a cold-forceps biopsy of
    the pouch."""
    doc = EF.Doc()
    doc.session(1, SK.ENTEROSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER), reached=[sup(EX.POUCH)],
                approach=sup(approach), through=sup(Y1))
    doc.anatomy[Y1] = own
    doc.exam(1)
    doc.act(2, Kind.BIOPSY, places=[sup(LM.POUCH)], device=sup(ct.Device.COLD_FORCEPS))
    return doc.build()


# === (b) A FILED FIELD NAMES ITS SHAPE: the joins census =============================================================

SMALL = G.SMALL_BOWEL | G.NO_ORGAN
BELOW = G.lm('rectum', 'anal_canal') | G.NO_ORGAN


def declared_ileum_below(types, type_narrow, subtypes, subtype_silent, joins) -> bool:
    """D342 (1) (b), DECLARED from the ruling (with D327 (1), the D328 addendum, D330 (1) (c), R5R-6 and D336 (1) (b)):
    the ileum may be joined below the colon - a filed subtype that may be ileorectal or ileoanal; one member that may lie
    below the colon; or two ends, one of which may lie in the small bowel beside another that may lie below. A filed list
    names an anastomosis whatever the entry's uncontrolled type: a list of one member has an unnamed end unless the type
    is a controlled type established as a shape of its own (``type_narrow`` and every value controlled); an empty list
    names two only for an entry that may be an anastomosis. An unnamed end is every landmark, or - the subtype filed,
    every value naming its ends - one of them; a member naming no placed organ is one of those ends too."""
    if not subtype_silent and subtypes & G.ILEUM_BELOW:
        return True
    ends = None
    if not subtype_silent and subtypes and all(value in G.SUBTYPE_ENDS for value in subtypes):
        ends = frozenset().union(*(G.SUBTYPE_ENDS[value] for value in subtypes))
    members = [((m - G.NO_ORGAN) | ends) if ends is not None and m & G.NO_ORGAN else m for m in joins]
    if len(members) == 1 and members[0] & BELOW:
        return True
    own_shape = type_narrow and bool(types) and types <= G.CONTROLLED_TYPES
    if (not members and AT.ANASTOMOSIS in types) or (len(members) == 1 and not own_shape):
        members += [ends if ends is not None else G.ALL_PLACES] * (2 - len(members))
    return any(members[i] & SMALL and members[j] & BELOW for i in range(len(members)) for j in range(len(members))
               if i != j)


def type_states():
    """Every anatomy type established (supported), claimed (unappraised) and at its widest (pass 2 unclear), and a
    silent type: (label, fact or None, the values it may be, whether it narrows)."""
    yield 'silent', None, G.ALL_TYPES, False
    for typ in AT:
        yield f'{typ.value} supported', sup(typ), frozenset({typ}), True
        yield f'{typ.value} claimed', unres(typ, UN), frozenset({typ}), True
        yield f'{typ.value} unclear', unres(typ, RS.APPRAISAL_UNCLEAR), G.ALL_TYPES, False


class JoinsCensusTests(SimpleTestCase):
    """D342 (1) (d): the joins census - every type state x a joins list of 0, 1 and 2 members over every landmark x
    every route family: the guard's ileum-below reading and its harmless reading equal the declared ones."""

    def test_every_type_every_joins_list_of_up_to_two_members(self):
        R0 = G.bare()
        lists = [()] + [(place,) for place in LM] + list(itertools.combinations_with_replacement(sorted(
            LM, key=lambda p: p.value), 2))
        wrong, checked, held = [], 0, 0
        for (t_label, t_fact, types, narrow), joins in itertools.product(list(type_states()), lists):
            facts = G.shape_facts(t_fact, None, None, [sup(j) for j in joins])
            R = G.with_entry(R0, facts)
            sets = tuple(frozenset({j}) for j in joins)
            expected = declared_ileum_below(types, narrow, G.ALL_SUBTYPES, True, sets)
            if evaluate.ileum_below_colon_possible(R, Y1) != expected:
                wrong.append(('ileum_below', t_label, [j.value for j in joins], expected))
            for family in FAMILIES:
                harmless = G.oracle_harmless(family, types, G.ALL_SUBTYPES, True, G.ALL_PLACES, True, sets)
                if evaluate.harmless(R, Y1, G.needs(family)) != harmless:
                    wrong.append((family, t_label, [j.value for j in joins], harmless))
                checked += 1
            held += expected
        self.assertEqual(wrong[:20], [])
        self.assertEqual(checked, len(list(type_states())) * len(lists) * len(FAMILIES))
        self.assertTrue(0 < held < checked)

    def test_every_subtype_every_joins_list_of_up_to_two_members(self):
        # an anastomosis (its type established) with each subtype - silent, every value - and a one- or two-member list
        R0 = G.bare()
        members = sorted(LM, key=lambda p: p.value)
        lists = [()] + [(place,) for place in members] + [
            pair for pair in itertools.combinations_with_replacement(members, 2)
            if pair[0] in (LM.ILEUM, LM.POUCH, LM.COLON, LM.RECTUM, LM.JEJUNUM, LM.STOMACH)]
        wrong, checked = [], 0
        for subtype, joins in itertools.product((None, *SUB), lists):
            facts = G.shape_facts(sup(AT.ANASTOMOSIS), sup(subtype) if subtype else None, None, [sup(j) for j in joins])
            R = G.with_entry(R0, facts)
            subtypes = frozenset({subtype}) if subtype else G.ALL_SUBTYPES
            sets = tuple(frozenset({j}) for j in joins)
            expected = declared_ileum_below(frozenset({AT.ANASTOMOSIS}), True, subtypes, subtype is None, sets)
            if evaluate.ileum_below_colon_possible(R, Y1) != expected:
                wrong.append((subtype and subtype.value, [j.value for j in joins], expected))
            for family in FAMILIES:
                harmless = G.oracle_harmless(family, frozenset({AT.ANASTOMOSIS}), subtypes, subtype is None,
                                             G.ALL_PLACES, True, sets)
                if evaluate.harmless(R, Y1, G.needs(family)) != harmless:
                    wrong.append((family, subtype and subtype.value, [j.value for j in joins], harmless))
                checked += 1
        self.assertEqual(wrong[:20], [])
        self.assertGreater(checked, 10000)

    def test_an_absences_organ_decides_nothing_about_its_joins(self):
        # D342 (1) (b): every absence organ the ABSENT row releases, with any joins member, matches no row
        R0 = G.bare()
        for family in FAMILIES:
            organs = G.ABSENT[family]
            for organ, member in itertools.product(sorted(organs, key=lambda p: p.value), (LM.GALLBLADDER, LM.OTHER,
                                                                                            LM.SIGMOID_COLON)):
                R = G.with_entry(R0, G.shape_facts(sup(AT.SURGICALLY_ABSENT), None, sup(organ), [sup(member)]))
                with self.subTest(family=family, organ=organ.value, member=member.value):
                    self.assertFalse(evaluate.harmless(R, Y1, G.needs(family)))
                R = G.with_entry(R0, G.shape_facts(sup(AT.SURGICALLY_ABSENT), None, sup(organ), []))
                self.assertTrue(evaluate.harmless(R, Y1, G.needs(family)), (family, organ))


# === (c) THE ROUTE'S OWN ENTRY: the route census =====================================================================

ILEAL = G.lm('ileum', 'terminal_ileum', 'neo_terminal_ileum', 'small_bowel')
LOWER_STOMA = G.COLON_ALL | ILEAL
OWN = {  # DECLARED from the ruling: family -> (type, organs, subtypes, joins)
    'COLONIC_STOMA': (AT.STOMA, LOWER_STOMA, frozenset(), LOWER_STOMA),
    'ILEAL_STOMA': (AT.STOMA, ILEAL, frozenset(), ILEAL),
    'POUCH': (AT.ILEAL_POUCH, ILEAL | G.lm('pouch'), G.ILEUM_BELOW, G.POUCH_JOINS),
}
OWN_ORGAN = {'COLONIC_STOMA': unres(LM.SIGMOID_COLON, UN), 'ILEAL_STOMA': unres(LM.ILEUM, UN), 'POUCH': None}


def own_variants():
    """The own entry's other fields, each varied alone: (label, field overrides, the values it may be or None)."""
    yield 'as filed', {}, ()
    for place in LM:
        for name, found, values in (('supported', sup(place), frozenset({place})),
                                    ('claimed', unres(place, UN), frozenset({place})),
                                    ('unclear', unres(place, RS.APPRAISAL_UNCLEAR), G.ALL_PLACES)):
            yield f'organ {place.value} {name}', {'organ': found}, (('organ', values),)
    for subtype in SUB:
        for name, found, values in (('supported', sup(subtype), frozenset({subtype})),
                                    ('claimed', unres(subtype, UN), frozenset({subtype})),
                                    ('a pass-1 doubt', EF.doubted(subtype, SUB.ILEOANAL), G.ALL_SUBTYPES)):
            yield f'subtype {subtype.value} {name}', {'subtype': found}, (('subtype', values),)
    for place in LM:
        yield f'joins [{place.value}]', {'joins': (sup(place),)}, (('joins', (frozenset({place}),)),)
    # round r3's round 7 fixes (DECISIONS D345 (3), 2026-11-19): EVERY landmark pair (was: 36 pairs over 9 chosen
    # landmarks)
    for one, other in itertools.combinations(sorted(LM, key=lambda p: p.value), 2):
        yield (f'joins [{one.value}, {other.value}]', {'joins': (sup(one), sup(other))},
               (('joins', (frozenset({one}), frozenset({other}))),))
    yield 'a joins member pass 2 rejected', {'joins': (T.rejected(LM.ILEUM),)}, (('joins', (G.ALL_PLACES,)),)


def declared_own_outside(family, fields) -> bool:
    _type, organs, subtypes, joins = OWN[family]
    for name, values in fields:
        if name == 'organ' and not values <= organs:
            return True
        if name == 'subtype' and not values <= subtypes:
            return True
        if name == 'joins' and any(not member <= joins for member in values):
            return True
    return False


class RouteOwnEntryCensusTests(SimpleTestCase):
    """D342 (1) (d): the route census - every through family's own entry x its organ, subtype and joins in every state x
    the through's states: the guard holds exactly when a field may lie outside the own type's declared anatomy."""

    def test_every_through_family_every_own_field_state(self):
        wrong, checked, held = [], 0, 0
        for family, (typ, _o, _s, _j) in OWN.items():
            code = {'COLONIC_STOMA': '44389', 'ILEAL_STOMA': '44382', 'POUCH': '44386'}[family]
            found = catalogue.lower_route(code)
            for label, over, fields in own_variants():
                facts = {'type': sup(typ), 'organ': OWN_ORGAN[family], **over}
                R, _code, number = G.family_control(family, {Y1: entry_of(**facts)})
                expected = declared_own_outside(family, fields)
                if evaluate.path_guard(found, R, X1) != expected:
                    wrong.append((family, label, expected))
                if evaluate.route_own_entry_contradicted(found, R, X1) != expected:
                    wrong.append(('own', family, label, expected))
                checked += 1
                held += expected
        self.assertEqual(wrong[:20], [])
        self.assertTrue(0 < held < checked)

    def test_every_through_state_reads_every_entry_that_may_be_the_routes_own(self):
        # beside the own entry Y1 (as filed), a second entry Y7 of the route's type filed outside its anatomy: held
        # whenever the through may name Y7 (silent, claimed Y7, a contradiction's sides, denied, rejected), never when
        # it is SUPPORTED naming Y1; with the act's session not established, held only when every candidate is
        for family, (typ, _o, _s, _j) in OWN.items():
            code = {'COLONIC_STOMA': '44389', 'ILEAL_STOMA': '44382', 'POUCH': '44386'}[family]
            found = catalogue.lower_route(code)
            outside = entry_of(type=sup(typ), joins=(sup(LM.STOMACH), sup(LM.JEJUNUM)))
            for name, through, expected in (('Y1 supported', sup(Y1), False), ('silent', None, True),
                                            ('Y7 claimed', unres(Y7, UN), True),
                                            ('Y1 or Y7', EF.contra(Y1, Y7), True), ('Y1 denied', neg(Y1), True),
                                            ('Y1 rejected', T.rejected(Y1), True), ('Y1 claimed', unres(Y1, UN), False)):
                R, _code, _number = G.family_control(family, {Y7: outside})
                session = dict(R.sessions[X1])
                session.pop(A.THROUGH, None)
                if through is not None:
                    session[A.THROUGH] = (through,)
                R = replace(R, sessions={**R.sessions, X1: session})
                with self.subTest(family=family, through=name):
                    self.assertEqual(evaluate.route_own_entry_contradicted(found, R, X1), expected)
                    self.assertEqual(evaluate.route_own_entry_contradicted(found, R, None), False)
            R, _code, _number = G.family_control(family, {Y1: entry_of(type=sup(typ), joins=(sup(LM.STOMACH),))})
            self.assertTrue(evaluate.route_own_entry_contradicted(found, R, None), family)

    def test_the_declared_own_anatomy_is_the_catalogues(self):
        for family, (typ, organs, subtypes, joins) in OWN.items():
            own = catalogue.ROUTE_OWN[G.needs(family)]
            self.assertEqual((own.type, own.organs, own.subtypes, own.joins), (typ, organs, subtypes, joins), family)
        self.assertEqual(catalogue.LOWER_STOMA_PLACES, evaluate.LOWER_STOMA_ORGANS)
        self.assertEqual(catalogue.ILEAL_PLACES, evaluate.ILEAL_PLACES)
        # every lower-GI code whose route passes an entry has its family's own anatomy
        for code in G.guarded_codes():
            row = catalogue.lower_route(str(code))
            self.assertEqual(row.needs in catalogue.ROUTE_OWN, row.route is not AP.TRANSANAL, code)


# === mutant FC.b2: a one-member list's unnamed end ====================================================================

class UnnamedEndTests(SimpleTestCase):
    """The final check's info finding: mutant FC.b2 (a one-member joins list names no other end) survived the guard's
    module on int8. Its rule is pinned here: a one-member list whose member may lie in the small bowel has an unnamed
    end that may lie below the colon - beside every uncontrolled type, a silent type and a controlled type pass 2 did
    not establish - and none beside a controlled type established as its own shape."""

    def test_a_one_member_small_bowel_list_has_an_unnamed_end(self):
        R0 = G.bare()
        for typ in (*(t for t in AT if t not in catalogue.CONTROLLED_TYPES), None):
            for member in (LM.ILEUM, LM.TERMINAL_ILEUM, LM.JEJUNUM, LM.SMALL_BOWEL):
                facts = G.shape_facts(sup(typ) if typ else None, None, None, [sup(member)])
                R = G.with_entry(R0, facts)
                with self.subTest(type=typ and typ.value, member=member.value):
                    self.assertTrue(evaluate.joins_ileum_below_colon_possible(R, Y1))
                    self.assertTrue(evaluate.ileum_below_colon_possible(R, Y1))
        for typ in catalogue.CONTROLLED_TYPES:
            for name, found, expected in (('established', sup(typ), False), ('claimed', unres(typ, UN), False),
                                          ('unclear', unres(typ, RS.APPRAISAL_UNCLEAR), True)):
                R = G.with_entry(R0, G.shape_facts(found, None, None, [sup(LM.ILEUM)]))
                with self.subTest(type=typ.value, state=name):
                    self.assertEqual(evaluate.joins_ileum_below_colon_possible(R, Y1), expected)

    def test_an_absence_filing_one_ileal_end_beside_every_family_but_the_pouchs(self):
        entry = entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.RECTUM), joins=(sup(LM.ILEUM),))
        for family in FAMILIES:
            if G.needs(family) in catalogue.HARMLESS_ILEUM_BELOW:
                continue
            R, code, number = G.family_control(family, {Y7: entry})
            with self.subTest(family=family):
                self.assertTrue(evaluate.ileum_below_colon_possible(R, Y7))
                held_by_route(self, assessed(R, code, number))


# === controls: the development filings and D340 Q1 ===================================================================

class ControlTests(SimpleTestCase):
    """The development filings stay as int8 decides them; an unappraised controlled claim decides as Fable read it
    (D340 Q1; L6R-2's input is its carve-out, READY as ruled)."""

    def test_l6r_2_an_unappraised_subtype_decides_as_filed(self):
        fd = 'The colonoscope was inserted per anus and advanced into the neo-terminal ileum.'
        for history in ('Subtotal colectomy with an ileal anastomosis in 2025.',
                        'Colectomy with an ileal anastomosis in 2025.'):
            for joins in ((), ('ileum',), ('ileum', 'colon')):
                text = HEAD + f'History: {history}\n' + f'Findings: {fd}\n' + f'{BX_NTI}\n'
                entries = [{'id': 'Y1', 'type': fact('anastomosis', src(['S4'], 'ileal anastomosis')), 'organ': [],
                            'subtype': [fact('ileocolic', src(['S4'], 'ileal anastomosis'))],
                            'joins': [fact(v, src(['S4'], 'ileal anastomosis')) for v in joins]}]
                sess = session('X1', fact('colonoscopy', src(['S5'], 'colonoscope')),
                               examination=[fact('E1', src(['S5']))], encounter=[fact('this_encounter', frame(['S2']))],
                               approach=[fact('transanal', src(['S5'], 'inserted per anus'))],
                               reached=[fact('neo_terminal_ileum', src(['S5'], 'into the neo-terminal ileum'))])
                events = [event('E1', ['S5'], 'colonoscope', 'was inserted', 'examination',
                                session=[fact('X1', src(['S5']))]),
                          event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                                target__places=[fact('neo_terminal_ileum', src(['S6'], 'neo-terminal ileum'))],
                                technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])]
                data = answer(sections=[opening(), labelled('N1', 'S4', 'History:', 'history'),
                                        labelled('N2', 'S5', 'Findings:', 'findings')],
                              sessions=[sess], anatomy=entries, events=events)
                with self.subTest(history=history, joins=joins):
                    self.assertEqual(R2CL.outcomes(text, data, R2CL.FAITHFUL, ('45380', BX_NTI))['45380'][:2],
                                     (READY, ()))

    def test_the_development_filings_stay_ready(self):
        T.DevelopmentFilingTests('test_the_development_sets_own_filings').test_the_development_sets_own_filings()
        T.DevelopmentFilingTests('test_the_oracle_lenss_controls_stay_ready_or_held_as_on_int7'
                                 ).test_the_oracle_lenss_controls_stay_ready_or_held_as_on_int7()


# === round r3's round 7 fixes (DECISIONS D345 (3), 2026-11-19): the census lists are derived =========================

class ReadClaimsDerivedTests(SimpleTestCase):
    """The final check's finding 4: read_claims and the route census's two-member joins were listed by hand. Each is
    derived now, and its completeness is pinned here from the catalogue and the landmark enumeration themselves."""

    def test_every_claim_every_harmless_row_reads_is_a_census_claim(self):
        found = {label for label, _control, _other, _make, _value in read_claims()}
        names = {A.TYPE: 'type', A.ORGAN: 'organ', A.SUBTYPE: 'subtype', A.JOINS: 'joins member'}
        expected = set()
        for rows in catalogue.HARMLESS.values():
            for row in rows:
                expected |= {f'{row.shape.value}: {names[row.decided_by]} {value.value}' for value in row.values}
                if row.decided_by is not A.ORGAN:
                    expected |= {f'{row.shape.value}: organ {place.value}' for place in row.organs}
                expected |= {f'{row.shape.value}: joins member {place.value}' for place in row.joins}
        self.assertEqual(sorted(expected - found)[:10], [])

    def test_the_route_census_two_member_joins_are_every_landmark_pair(self):
        pairs = [label for label, _over, fields in own_variants()
                 if fields and fields[0][0] == 'joins' and len(fields[0][1]) == 2]
        self.assertEqual(len(pairs), len(LM) * (len(LM) - 1) // 2)
