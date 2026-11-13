"""Settled FactSets for the per-code rule's tests (tests/v2/test_evaluate.py, tests/v2/test_questions.py), TEXT-ONLY and
SYNTHETIC: every fixture is hand-built from engine/types' records (enumeration members, ids, results and integer spans:
the engine's whole input, FINAL-V2 4.1). No document is read and no provider is called. The sentences quoted in the tests'
comments are the design's own or v1's test lines; the engine never reads them.

``Doc`` builds one FactSet: sessions, events, lesions and anatomy entries by short attribute names, each event anchored on
its own unit (100 * n .. 100 * n + 60) unless told otherwise. ``exam`` and ``act`` add a complete, established act -
done today by the documenting team, told in the documenting clinician's own entry - so a test changes exactly the fact it
is about."""
from __future__ import annotations

from typing import Any

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import Anchor, Cited, Fact, FactSet, Id, IdFamily, Span, UnlistedStatement

A, Res, State = ct.Attribute, ct.Result, ct.FactState
Kind, Status, SessionKind = ct.Kind, ct.Status, ct.SessionKind
DateRelation, Performer, Owner, Landmark = ct.DateRelation, ct.Performer, ct.Owner, ct.Landmark
ON, EARLIER = DateRelation.ON_DATE_OF_SERVICE, DateRelation.EARLIER_DATE
TEAM, DC = Performer.DOCUMENTING_TEAM, Owner.DOCUMENTING_CLINICIAN


def E(n: int) -> Id:
    return Id(IdFamily.EVENT, n)


def X(n: int) -> Id:
    return Id(IdFamily.SESSION, n)


def L(n: int) -> Id:
    return Id(IdFamily.LESION, n)


def Y(n: int) -> Id:
    return Id(IdFamily.ANATOMY, n)


def fact(result: ct.Result, value: Any, state: ct.FactState | None, *, options: tuple = (), reasons: tuple = (),
         spans: tuple = (), cited: tuple = (), inherited_from: Id | None = None) -> Fact:
    return Fact(result=result, value=value, state=state, options=tuple(options), reasons=tuple(reasons),
                spans=tuple(spans), cited=tuple(cited), inherited_from=inherited_from)


def sup(value: Any, **kw: Any) -> Fact:
    """Supported: established, the claim's value."""
    return fact(Res.SUPPORTED, value, State.SUPPORTED, **kw)


def neg(value: Any, **kw: Any) -> Fact:
    """Negated: established, the claim negated."""
    return fact(Res.NEGATED, value, State.NEGATED, **kw)


def unres(value: Any, reason: ct.Reason = ct.Reason.APPRAISAL_UNCLEAR, **kw: Any) -> Fact:
    """Unresolved: a failed check or an appraisal that did not establish it; the claimed value kept."""
    return fact(Res.UNRESOLVED, value, State.SUPPORTED, reasons=(reason,), **kw)


def doubted(value: Any, *readings: Any, **kw: Any) -> Fact:
    """A doubt pass 1 reported (3.3 row 2): unknown, the value and the readings kept."""
    return fact(Res.UNKNOWN, value, State.SUPPORTED, options=readings, reasons=(ct.Reason.DOUBT_STATED,), **kw)


def contra(*sides: Any, **kw: Any) -> Fact:
    """Pass 1's contradicted fact (3.3 row 1): its sides are its options, its value None."""
    return fact(Res.CONTRADICTED, None, State.CONTRADICTED, options=sides,
                reasons=(ct.Reason.CONTRADICTED_BY_PASS1,), **kw)


SILENT = F.SILENT

NAMES = {
    'kind': A.KIND, 'status': A.STATUS, 'session': A.SESSION, 'date': A.DATE_RELATION, 'performer': A.PERFORMER,
    'person': A.PERFORMER_PERSON, 'entry': A.ENTRY, 'lesion': A.TARGET_LESION, 'structure': A.TARGET_STRUCTURE,
    'places': A.TARGET_PLACES, 'duct': A.TARGET_DUCT, 'device': A.TECHNIQUE_DEVICE, 'route': A.TECHNIQUE_ROUTE,
    'purpose': A.PURPOSE, 'cause': A.CAUSE, 'cause_event': A.CAUSE_EVENT, 'part_of': A.PART_OF,
    'part_relation': A.PART_RELATION, 'yield_': A.YIELD, 'access': A.ACCESS_OUTCOME, 'breadth': A.SCOPE_BREADTH,
    'targets': A.SCOPE_TARGETS, 'segment': A.SCOPE_SEGMENT, 'covers': A.SCOPE_COVERS, 'excepts': A.SCOPE_EXCEPTS,
    'basis': A.VISIT_BASIS, 'separate': A.VISIT_SEPARATELY_IDENTIFIABLE, 'other_class': A.OTHER_CLASS,
    # a session's
    'encounter': A.ENCOUNTER, 'tract': A.TRACT, 'approach': A.APPROACH, 'through': A.THROUGH, 'reached': A.REACHED,
    'completion': A.COMPLETION, 'stations': A.STATIONS, 'part_of_session': A.PART_OF_SESSION,
    # a lesion's, an anatomy entry's
    'lesion_places': A.PLACES, 'distinct_from': A.DISTINCT_FROM, 'same_as': A.SAME_AS, 'multiplicity': A.MULTIPLICITY,
    'type': A.TYPE, 'subtype': A.SUBTYPE,
}
MANY = {'places', 'targets', 'segment', 'covers', 'excepts', 'reached', 'stations', 'lesion_places', 'distinct_from',
        'same_as'}


def facts_of(**attributes: Any) -> dict:
    """An object's facts by attribute; a multi-valued attribute is a sequence of member facts; None is left out."""
    out: dict = {}
    for name, value in attributes.items():
        if value is None:
            continue
        out[NAMES[name]] = tuple(value) if name in MANY else (value,)
    return out


def unit(n: int) -> Span:
    """The unit an event numbered ``n`` is anchored on by default."""
    return Span(100 * n, 100 * n + 60)


class Doc:
    """One synthetic settled inventory, built object by object (module docstring)."""

    def __init__(self) -> None:
        self.events: dict = {}
        self.sessions: dict = {}
        self.lesions: dict = {}
        self.anatomy: dict = {}
        self.anchors: dict = {}
        self.unlisted: list = []
        self.controls: dict = {}
        self.completeness: dict = {}

    def session(self, number: int, kind: Any, **attributes: Any) -> Id:
        """A session; ``kind`` a SessionKind (supported) or a Fact."""
        sid = X(number)
        self.sessions[sid] = facts_of(kind=kind if isinstance(kind, Fact) else sup(kind), **attributes)
        return sid

    def event(self, number: int, *, anchor: Any = None, kind_words: Span | None = None,
              status_words: Span | None = None, **attributes: Any) -> Id:
        eid = E(number)
        self.events[eid] = facts_of(**attributes)
        units = anchor if anchor is not None else (unit(number),)
        self.anchors[eid] = Anchor(units=tuple(units), kind_words=kind_words, status_words=status_words)
        return eid

    def act(self, number: int, kind: Any, *, session: Any = X(1), **over: Any) -> Id:
        """A complete established act of ``kind`` (a Kind or a Fact) in ``session`` (an Id, supported, or a Fact):
        performed, today, by the documenting team, in the documenting clinician's own entry; ``over`` replaces or adds
        facts (None leaves one out)."""
        base: dict = dict(kind=kind if isinstance(kind, Fact) else sup(kind), status=sup(Status.PERFORMED),
                          session=session if isinstance(session, Fact) else sup(session), date=sup(ON),
                          performer=sup(TEAM), entry=sup(DC))
        anchor = over.pop('anchor', None)
        kind_words = over.pop('kind_words', None)
        status_words = over.pop('status_words', None)
        base.update(over)
        return self.event(number, anchor=anchor, kind_words=kind_words, status_words=status_words, **base)

    def exam(self, number: int = 1, *, session: Id = X(1), **over: Any) -> Id:
        """The session's examination, done today by the documenting team."""
        return self.act(number, Kind.EXAMINATION, session=session, **over)

    def lesion(self, number: int, **attributes: Any) -> Id:
        lid = L(number)
        self.lesions[lid] = facts_of(**attributes)
        return lid

    def entry(self, number: int, **attributes: Any) -> Id:
        yid = Y(number)
        self.anatomy[yid] = facts_of(**attributes)
        return yid

    def build(self) -> FactSet:
        return FactSet(encounter={}, people={}, sections={}, sessions=self.sessions, anatomy=self.anatomy,
                       lesions=self.lesions, events=self.events, anchors=self.anchors, unlisted=tuple(self.unlisted),
                       pair_controls=self.controls, completeness=self.completeness)


def colonoscopy(*, snare: bool = True, **snare_over: Any) -> Doc:
    """A colonoscopy X1 to the cecum (its examination E1) with, by default, the cold snare removal E2 of L1 in the
    sigmoid colon ("A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.")."""
    doc = Doc()
    doc.session(1, SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(ct.Extent.CECUM)])
    doc.exam(1)
    if snare:
        doc.lesion(1, lesion_places=[sup(Landmark.SIGMOID_COLON)])
        base: dict = dict(places=[sup(Landmark.SIGMOID_COLON)], lesion=sup(L(1)), device=sup(ct.Device.COLD_SNARE))
        base.update(snare_over)
        kind = base.pop('kind', Kind.SNARE)
        doc.act(2, kind, **base)
    return doc


def egd(**over: Any) -> Doc:
    """An EGD X1 to the second portion of the duodenum (E1)."""
    doc = Doc()
    doc.session(1, SessionKind.EGD, reached=[sup(ct.Extent.SECOND_PORTION_DUODENUM)], **over)
    doc.exam(1)
    return doc


def cited(link: ct.Link, units: Span, at: Span | None) -> Cited:
    return Cited(link=link, units=units, at=at)


def statement_source(units: Span, at: Span | None) -> tuple:
    """One ``statement`` source of a fact: its units' span and its located words (None: its whole units)."""
    return (cited(ct.Link.STATEMENT, units, at),)


def unlisted(what: ct.UnlistedWhat, kind: Kind | None, session: Id | None, span: Span) -> UnlistedStatement:
    return UnlistedStatement(units=(span,), what=what, kind=kind, session=session)
