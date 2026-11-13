"""Where pass 1's citations sit (docs/gemini-migration/FINAL-V2.md 1.2 rules 6-7, 1.5, 3.1 I2, I3 and G1-G6; step 1c of
8.1; DECISIONS D198, D199 and D207): words located over consecutive units, runs of units and their sentence closures,
section spans and containment, and the link geometry of every source. Every check here proves WHERE a source is, never
what it means (P4).

**I2, words over consecutive units** [R:CO-4]. ``bind_words`` locates a source's ``words`` in the revision slice from its
first unit's start to its last unit's end: the exact tier first, any whitespace run (line breaks included) matching any
whitespace run; then the fold tier (contract/fold.py, v1's fold copied: NFKC, case folding, dashes and quotes folded,
whitespace collapsed). The first and last characters must stand on word boundaries, as v1's ``_bounded_positions``
decides them (``bounded_positions``, v1's rule exactly); at the edge of the slice the boundary is judged against the
revision's own neighbouring character, so a unit boundary that cuts a word (a forced 600-character split) is no word
boundary. Words '' cite the whole of the units. Failures: ``words_not_in_units`` (no occurrence in either tier),
``words_not_bounded`` (occurrences, none on word boundaries).

**I3, runs** [R:CO-5]. A source's units, and an anchor's, are one or more consecutive units of one paragraph, at most
SOURCE_UNITS (12): ``units_not_consecutive``, ``source_too_long``; an unknown id is ``unit_unknown`` (I1, also step 1b's).
An anchor's ``kind_words`` and ``status_words`` lie inside its units by I2's rule, else ``anchor_words``. The sentence
closure of a run is contract/segment.py's (1.2 rule 6), reached here through ``Layout.closure``.

**G2, sections** (``Sections``). The answer lists sections in document order (2.1 P3); the first is the opening part N0,
which begins at the text start: its start cites no unit, or cites units with no unit of the text before them. An N0
whose start cites no unit (1.4: units [], words "") starts with a part of length zero at offset 0 (D199): it orders
before every other section, one that starts at the text's first character included, and when one does, N0 contains no
unit (its span runs to that start, as every span runs to the next). Every other start is located by I1-I3 at the
offset of its start words, so a label in the middle of a line or of a unit opens its section where its words begin
[J][B]. Starts strictly increase in the answer's order. A section reaches from its start to the
next listed start, or, when it gives closing sources, to the end of the last of them, and no other section starts
inside that reach, whatever its place in the list. ``section_start_unlocated``: a start (or a closing source) that does
not locate, or a start citing no unit on any section but the first. ``section_order`` (D186 keeps G2's two reasons):
two sections listed out of offset order, and a section whose reach holds another section's start (an overlap), each on
both sections involved; a closing source before its start; an opening part that is not at the text start (G2 names no
reason of its own for that). A section with any of these has no span; so has a section whose next listed start is
unknown, since its end, and whether it overlaps, cannot be known. Every other span is computed over the sections sorted
by start offset: from its start to the end of its closing sources when it gives any, else to the next start in the
text, the last to the end of the text.

**Containment** (1.5): the containing section of a place is the last section whose start is at or before the place's
start and whose closing source, when given, ends at or after the place's end. An act's place is its anchor's own words -
from the first of its kind and status words to the last - so that an act told after a mid-unit label is told in that
label's section. **G4**: an inherited fact is attached only when the containing section has a span and the place lies
inside it (``inherit_unattached``); whether the section's own fact passed its checks is settle's (3.3 steps 1-5).

**G1, link geometry** (``link_reasons``), per source, measured against a ``Subject`` - the object a fact is about:
``statement`` units are among the units of the object's own statement: an event's anchor units and their sentence
closure, a session's examination anchor units and their closure (D207: the examination is an event, and its card shows
the closure, 2.4), a lesion's description units, a person's name units (no closure: 3.1 G1 names the description unit);
an encounter or anatomy fact's units need only exist (D207). ``section``: the source's words (its units, for words '')
lie inside the place of the containing section's start source or of one of its closing sources, by offsets, so neither
the next section's mid-unit label nor a framing sentence after the label is the start; ``frame`` lies inside the
containing section's span; ``placing`` is any unit that is not the object's own anchor (its meaning is pass 2's)
[R:CO-2]; ``document_frame`` lies inside N0's span and every unit is a source of an encounter fact (the frame units);
``antecedent``: the source's units end before the first unit of the object's own statement starts (3.1 G1: it precedes
the anchor), so the anaphoric frame inside the anchor is not its own antecedent; ``other_statement`` units exist.
Failure: ``geometry_<link>``.

**G3** (``target_reasons``, ``lesion_reasons``): a target fact with link ``statement`` has its words inside the anchor
units; target.lesion's description units are among the act's anchor units or among a valid restatement's units (G6) -
never their sentence closure (3.1 G3: the description unit IS the anchor or a restatement) - or the description ends
before the act's own words (an antecedent, D207): ``target_detached``. **G5** (``extent_units``, ``extent_reasons``;
D36 restated [R:CO-6], D198): a session's reached, completion, stations, approach and through sources lie - where their
words are - in a unit of its examination's anchor or of one of the examination's valid restatements, or in a unit no act
is told in. The acts are the events whose claimed status is not negated, other than the session's own examination, each
told in its anchor's units and its valid restatements' units; a denial's anchor is no act's. A source lying only in
acts' units, of this session or another, is ``extent_inferred``; there is no section test, so an examination told
across several parts passes. **G6** (``restatement_valid``): a restatement's units are a valid run and no event's anchor
units (``anchored_units``: any event's, D198 keeps the broad reading), and a ``title`` restatement lies in N0 or in a
section start; any other restatement is ignored.

**Every failure is a closed-list reason** (types.Reason) that leaves the fact UNRESOLVED when settle applies it (3.3 row
4). Nothing here sets, changes or removes a value, creates a fact, or makes anything READY; a malformed citation is
reported, never repaired, and never raises. Only a caller's breach of the contract raises: a layout that is not a text's
units, a text or words that are not a str, or repeated section ids (which 3.1 S1 refuses before geometry runs).

**Why this is not a reader** (5.6, 5.7 measure 4, SingleCharacterGeometry and NoWordLists): words are found by comparing
characters one at a time; nothing here names a word, holds a word, phrase, marker or frame list, imports ``re`` or a text
module, compares with a string literal longer than one character, or calls a str method but ``isspace`` and ``isalnum``.
Geometry reads offsets, unit ids, link types, restatement roles and the state of an event's claimed status (G5, D198) -
enumeration members - and never what a word means.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from studio.interpretation.contract import segment
from studio.interpretation.contract.fold import fold, fold_char
from studio.interpretation.contract.types import (Attribute, FactState, Link, LocatedWords, Reason, RestatementRole,
                                                  Source, Span, Unit)

SOURCE_UNITS = 12  # 1.8 and 3.1 I3: a source, or an anchor, cites at most this many units (an item-level bound) [R:CO-5]

# G5's attributes: the session facts whose sources must lie in the examination's statement or in no act's anchor
EXTENT_ATTRIBUTES = (Attribute.REACHED, Attribute.COMPLETION, Attribute.STATIONS, Attribute.APPROACH, Attribute.THROUGH)

_GEOMETRY = {Link.STATEMENT: Reason.GEOMETRY_STATEMENT, Link.SECTION: Reason.GEOMETRY_SECTION,
             Link.FRAME: Reason.GEOMETRY_FRAME, Link.PLACING: Reason.GEOMETRY_PLACING,
             Link.DOCUMENT_FRAME: Reason.GEOMETRY_DOCUMENT_FRAME, Link.ANTECEDENT: Reason.GEOMETRY_ANTECEDENT,
             Link.OTHER_STATEMENT: Reason.GEOMETRY_OTHER_STATEMENT}
_RANK = {reason: rank for rank, reason in enumerate(Reason)}


# --- what geometry is given -------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Anchor:
    """An event's anchor as pass 1 wrote it (FINAL-V2 1.4 EVENT.anchor): the act's own statement. units: its unit ids;
    kind_words, status_words: words inside them ('' for the whole of the units)."""
    units: tuple[str, ...]
    kind_words: str
    status_words: str


@dataclass(frozen=True, slots=True)
class Restatement:
    """One of an event's restatements as pass 1 wrote it (FINAL-V2 1.4 EVENT.restatements): its unit ids and its role."""
    units: tuple[str, ...]
    role: RestatementRole


@dataclass(frozen=True, slots=True)
class Section:
    """A section as pass 1 wrote it (FINAL-V2 1.4 SECTION), for G2: id; start, the source of its heading, label,
    signature or opening words (no unit for N0); end, its closing sources (a closing signature), else ()."""
    id: str
    start: Source
    end: tuple[Source, ...]


@dataclass(frozen=True, slots=True)
class Event:
    """An event as pass 1 wrote it (FINAL-V2 1.4 EVENT), as G5 reads it (D198): its anchor, its restatements, and the
    state of its claimed status (types.FactState; None when pass 1 gave none). An event whose status is negated is a
    denial: its anchor is no act's."""
    anchor: Anchor
    restatements: tuple[Restatement, ...]
    status: FactState | None


# --- what geometry gives ----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Citation:
    """A citation located (I1-I3): units, as cited; span, the units' slice of the revision, None when the run fails
    I1 or I3; words, the words located (the revision's own slice), None when '' or not located; place, where the citation
    stands - its words, or its units' span for words '' - None when it cannot be placed; reasons, () when it passed."""
    units: tuple[str, ...]
    span: Span | None
    words: LocatedWords | None
    place: Span | None
    reasons: tuple[Reason, ...]


@dataclass(frozen=True, slots=True)
class AnchorCitation:
    """An anchor located (I3): units; span, the units' slice; kind_words, status_words, each located (None when '' or
    not located); place, the act's own words, from the first of them to the last (the units' span for words ''), None
    when the anchor fails; reasons: unit_unknown, units_not_consecutive, source_too_long or anchor_words."""
    units: tuple[str, ...]
    span: Span | None
    kind_words: LocatedWords | None
    status_words: LocatedWords | None
    place: Span | None
    reasons: tuple[Reason, ...]


@dataclass(frozen=True, slots=True)
class SectionPlace:
    """One section's geometry (G2). id, index: the section and its place in the answer (index 0 is the opening part).
    start: the offset where it begins (0 for the opening part), None when unlocated. opening: its start source's place
    (Span(0, 0) for an opening part that cites none). start_units: its start's unit ids. end_units: each closing
    source's unit ids. closers: each closing source's place, None when it does not locate. closed: whether it gives
    closing sources. closing: the end of the last of them, None when not located. span: [start, end) when known.
    reasons: section_order, section_start_unlocated; () when G2 passed."""
    id: str
    index: int
    start: int | None
    opening: Span | None
    start_units: tuple[str, ...]
    end_units: tuple[tuple[str, ...], ...]
    closers: tuple[Span | None, ...]
    closed: bool
    closing: int | None
    span: Span | None
    reasons: tuple[Reason, ...]


@dataclass(frozen=True, slots=True)
class Extent:
    """G5's two sets of units for one session (D198, ``extent_units``). own: the units that always place its reach - its
    examination's anchor units (when that anchor passes I3) and the units of the examination's valid restatements.
    acts: the units the acts are told in - the anchor units and valid restatement units of every event whose claimed
    status is not negated, the session's own examination excluded."""
    own: frozenset[str]
    acts: frozenset[str]


@dataclass(frozen=True, slots=True)
class Subject:
    """The object a fact is about, as G1 measures its sources (see the subject builders). statement: the units a
    ``statement`` source may cite (an event's or examination's anchor units and their sentence closure; a lesion's
    description units; a person's name units). anywhere: True for an object with no statement of its own to measure
    against (the encounter, an anatomy entry), whose ``statement`` sources need only exist. own: the units of its own
    statement as cited (an event's or examination's anchor, the description, the name, a section's start): a
    ``placing`` source may not cite them, and an ``antecedent`` source's units end before the first of them starts.
    place: where its own statement stands, None when it cannot be placed (then nothing is its antecedent). section: the
    section it is told in when G4's edge holds - for a section, itself - else None."""
    statement: tuple[str, ...]
    anywhere: bool
    own: tuple[str, ...]
    place: Span | None
    section: SectionPlace | None


# --- the layout: units, runs and closures -----------------------------------------------------------------------------


class Layout:
    """The revision text and its units (segment.units of that text), indexed by id: ``line``, ``paragraph``, ``run``
    (I1 and I3), ``span`` and ``closure`` (1.2 rule 6). ValueError when the units are not a text's units in document
    order (an offset outside the text, out of order, empty, or a repeated id); TypeError for a text that is not a str or
    a unit that is not a contract Unit."""

    def __init__(self, text: str, units: Sequence[Unit]) -> None:
        if not isinstance(text, str):
            raise TypeError('The revision text must be a str.')
        ordered = tuple(units)
        at: dict[str, int] = {}
        reached = 0
        for position, unit in enumerate(ordered):
            if not isinstance(unit, Unit):
                raise TypeError('A layout holds contract Units.')
            if unit.id in at:
                raise ValueError(f'The unit id {unit.id!r} is repeated.')
            if not reached <= unit.start < unit.end <= len(text):
                raise ValueError('The units are not this text\'s units in document order.')
            at[unit.id] = position
            reached = unit.end
        self.text = text
        self.units = ordered
        self._at = at

    @classmethod
    def of(cls, text: str, pages: Sequence[segment.Page] = ()) -> Layout:
        """The layout of ``text`` cut by contract/segment.py (1.2 rules 1-5)."""
        return cls(text, segment.units(text, pages))

    def unit(self, unit_id: str) -> Unit | None:
        """The unit of that id, None when the text has none."""
        position = self._at.get(unit_id)
        return None if position is None else self.units[position]

    def line(self, unit_id: str) -> int | None:
        """line(u): the 1-based line holding the unit's start, None for an unknown id."""
        unit = self.unit(unit_id)
        return None if unit is None else unit.line

    def paragraph(self, unit_id: str) -> int | None:
        """paragraph(u): the unit's paragraph, None for an unknown id."""
        unit = self.unit(unit_id)
        return None if unit is None else unit.paragraph

    def consecutive(self, unit_ids: Sequence[str]) -> bool:
        """consecutive(us): one or more known units, consecutive in document order, each once, all of one paragraph."""
        positions = self._positions(unit_ids)
        return positions is not None and _consecutive(self.units, positions)

    def run(self, unit_ids: Sequence[str]) -> tuple[Reason, ...]:
        """I1 and I3 on a citation's units, in Reason order: unit_unknown for an id the text has none of;
        units_not_consecutive unless they are one or more consecutive units of one paragraph; source_too_long over
        SOURCE_UNITS. () when the run passes."""
        reasons: list[Reason] = []
        if len(unit_ids) > SOURCE_UNITS:
            reasons.append(Reason.SOURCE_TOO_LONG)
        positions = self._positions(unit_ids)
        if positions is None:
            reasons.append(Reason.UNIT_UNKNOWN)
        elif not _consecutive(self.units, positions):
            reasons.append(Reason.UNITS_NOT_CONSECUTIVE)
        return _ordered(reasons)

    def span(self, unit_ids: Sequence[str]) -> Span | None:
        """The slice of the revision from the run's first unit's start to its last unit's end, None unless the run
        passes I1 and I3 (``run``)."""
        if self.run(unit_ids):
            return None
        return Span(self.units[self._at[unit_ids[0]]].start, self.units[self._at[unit_ids[-1]]].end)

    def closure(self, unit_ids: Sequence[str]) -> tuple[str, ...] | None:
        """closure(us): the unit ids of the run's sentence closure (1.2 rule 6, contract/segment.py), None unless the run
        passes I1 and I3."""
        if self.run(unit_ids):
            return None
        return segment.closure(self.text, self.units, tuple(unit_ids))

    def _positions(self, unit_ids: Sequence[str]) -> list[int] | None:
        """Each id's position among the units; None when an id is unknown."""
        positions = []
        for unit_id in unit_ids:
            position = self._at.get(unit_id)
            if position is None:
                return None
            positions.append(position)
        return positions


# --- I2: words located over consecutive units -------------------------------------------------------------------------


def bounded_positions(hay: Sequence[str], needle: Sequence[str]) -> list[int]:
    """Every place ``needle`` occurs in ``hay`` without splitting a word at either end: v1's
    normalize._bounded_positions, compared character by character (a word character is a letter, a digit or ``_``). An
    occurrence's first character may stand at the start of ``hay`` or after a character that is not a word character,
    or be no word character itself; likewise its last. Overlapping occurrences are all listed, in order. An empty needle
    has no place (v1 is never called with one)."""
    if not needle:
        return []
    return [at for at in range(len(hay) - len(needle) + 1)
            if _matches(hay, needle, at) and _bounded(hay, needle, at, False, False)]


def bind_words(layout: Layout, unit_ids: Sequence[str], words: str) -> Citation:
    """I1-I3 on a citation (FINAL-V2 1.2 rule 7, 3.1 I2 [R:CO-4]): its run (``Layout.run``), then its ``words`` in the
    slice from the first unit's start to the last unit's end - the exact tier (any whitespace run matching any
    whitespace run), else the fold tier - at the first occurrence whose first and last characters stand on word
    boundaries. words '' cite the whole of the units. A failure is a reason, never an exception: unit_unknown,
    units_not_consecutive or source_too_long for the run; words_not_in_units or words_not_bounded for the words."""
    if not isinstance(words, str):
        raise TypeError('A citation\'s words are a str.')
    units = tuple(unit_ids)
    reasons = layout.run(units)
    span = None if reasons else layout.span(units)
    if span is None:
        return Citation(units, None, None, None, reasons)
    if not words:
        return Citation(units, span, None, span, ())
    located, occurred = _locate(layout.text, span, words)
    if located is None:
        return Citation(units, span, None, None,
                        (Reason.WORDS_NOT_BOUNDED if occurred else Reason.WORDS_NOT_IN_UNITS,))
    return Citation(units, span, located, Span(located.start, located.end), ())


def locate(layout: Layout, source: Source) -> Citation:
    """I1-I3 on a pass-1 source: ``bind_words`` over its units and words."""
    return bind_words(layout, source.units, source.words)


def locate_anchor(layout: Layout, anchor: Anchor) -> AnchorCitation:
    """I3 on an anchor: its run, then its kind_words and status_words inside its units by I2's rule (anchor_words when
    either does not locate). Its place is the act's own words, from the first to the last of them."""
    units = tuple(anchor.units)
    reasons = layout.run(units)
    span = None if reasons else layout.span(units)
    if span is None:
        return AnchorCitation(units, None, None, None, None, reasons)
    kind = bind_words(layout, units, anchor.kind_words)
    status = bind_words(layout, units, anchor.status_words)
    if kind.place is None or status.place is None:
        return AnchorCitation(units, span, kind.words, status.words, None, (Reason.ANCHOR_WORDS,))
    place = Span(min(kind.place.start, status.place.start), max(kind.place.end, status.place.end))
    return AnchorCitation(units, span, kind.words, status.words, place, ())


# --- G2 and containment: sections ---------------------------------------------------------------------------------------


class Sections:
    """The sections' geometry (G2) and containment (1.5, G4) over one layout. ``places``: one SectionPlace per section,
    in the answer's order. ValueError for a repeated section id (3.1 S1 refuses such an answer first)."""

    def __init__(self, layout: Layout, sections: Sequence[Section]) -> None:
        given = tuple(sections)
        by_id: dict[str, int] = {}
        for index, section in enumerate(given):
            if section.id in by_id:
                raise ValueError(f'The section id {section.id!r} is repeated.')
            by_id[section.id] = index
        count = len(given)
        reasons: list[set[Reason]] = [set() for _ in given]
        starts: list[int | None] = []
        openings: list[Span | None] = []
        for index, section in enumerate(given):
            start, opening, why = _section_start(layout, section.start, index == 0)
            starts.append(start)
            openings.append(opening)
            reasons[index].update(why)
        # D199: an opening part whose start cites no unit is of length zero at offset 0 and orders before everything
        empty = bool(given) and not given[0].start.units and not given[0].start.words
        closers: list[tuple[Span | None, ...]] = []
        closings: list[int | None] = []
        for index, section in enumerate(given):
            found, closing, why = _section_closing(layout, section.end, starts[index])
            closers.append(found)
            closings.append(closing)
            reasons[index].update(why)
        for first in range(count):
            for later in range(first + 1, count):
                before, after = starts[first], starts[later]
                if (before is not None and after is not None and after <= before
                        and not (first == 0 and empty)):
                    reasons[first].add(Reason.SECTION_ORDER)
                    reasons[later].add(Reason.SECTION_ORDER)
        for index in range(count):
            start, reach = starts[index], _section_reach(layout, given, index, starts, closings)
            if start is None or reach is None:
                continue
            for other in range(count):
                inside = starts[other]
                if (other != index and inside is not None and inside < reach
                        and (start < inside or (start == inside and index == 0 and empty))):
                    reasons[index].add(Reason.SECTION_ORDER)
                    reasons[other].add(Reason.SECTION_ORDER)
        places = []
        for index, section in enumerate(given):
            span = _section_span(layout, given, index, starts, closings, empty) if not reasons[index] else None
            places.append(SectionPlace(
                id=section.id, index=index, start=starts[index], opening=openings[index],
                start_units=tuple(section.start.units), end_units=tuple(tuple(end.units) for end in section.end),
                closers=closers[index], closed=bool(section.end), closing=closings[index], span=span,
                reasons=_ordered(reasons[index])))
        self.layout = layout
        self.places = tuple(places)
        self._by_id = by_id

    def place(self, section_id: str) -> SectionPlace | None:
        """The geometry of the section of that id, None when the answer has none."""
        index = self._by_id.get(section_id)
        return None if index is None else self.places[index]

    @property
    def opening(self) -> SectionPlace | None:
        """N0, the document's opening part: the first section of the answer, None when it lists none."""
        return self.places[0] if self.places else None

    def containing(self, place: Span) -> SectionPlace | None:
        """The containing section of ``place`` (1.5): the last section whose start is at or before the place's start and
        whose closing source, when given, ends at or after the place's end. A section whose closing source did not
        locate may contain anything after its start (fail-closed); one whose start did not locate contains nothing.
        None when no section qualifies."""
        best: SectionPlace | None = None
        for candidate in self.places:
            start = candidate.start
            if start is None or start > place.start:
                continue
            if candidate.closed and candidate.closing is not None and candidate.closing < place.end:
                continue
            if best is None or best.start is None or start >= best.start:
                best = candidate
        return best

    def attached(self, place: Span) -> SectionPlace | None:
        """G4: the containing section of ``place`` when it has a span (G2 passed, its end known) and the place lies
        inside it; None otherwise, and an inherited fact is then inherit_unattached."""
        section = self.containing(place)
        if section is None or not _within(place, section.span):
            return None
        return section


# --- the subjects G1 measures sources against -------------------------------------------------------------------------


def event_subject(layout: Layout, sections: Sections, anchor: Anchor) -> Subject:
    """An event: its statement is its anchor's units and their sentence closure; its place, its own words; its section,
    the containing section when G4's edge holds."""
    found = locate_anchor(layout, anchor)
    closure = layout.closure(found.units)
    return Subject(statement=found.units if closure is None else closure, anywhere=False, own=found.units,
                   place=found.place, section=None if found.place is None else sections.attached(found.place))


def session_subject(layout: Layout, sections: Sections, examination: Anchor | None) -> Subject:
    """A session: measured against its examination event's anchor (its statement - the anchor units and their closure,
    accepted by D207 - its place and its section). A session with no examination (told only by its acts, or whose
    examination id does not resolve) has no statement of its own, so its ``statement``, ``section``, ``frame`` and
    ``antecedent`` sources fail."""
    if examination is None:
        return Subject(statement=(), anywhere=False, own=(), place=None, section=None)
    return event_subject(layout, sections, examination)


def described_subject(layout: Layout, sections: Sections, description: Source) -> Subject:
    """A lesion (its description) or a person (its name): that source's own units are its statement - not their
    sentence closure (3.1 G1: "its description unit") - its place is where the source stands, and its section the
    containing section when G4's edge holds."""
    found = locate(layout, description)
    return Subject(statement=found.units, anywhere=False, own=found.units, place=found.place,
                   section=None if found.place is None else sections.attached(found.place))


def section_subject(sections: Sections, section_id: str) -> Subject:
    """A section's own facts (owner, role, occasion, performer): ``section`` sources lie in its own start or closing
    sources, ``frame`` sources lie in its own span, a ``placing`` source is not its start, an ``antecedent`` source's
    units end before its start's first unit. A section has no ``statement`` of its own (its start is cited as
    ``section``). An unknown id places nothing."""
    place = sections.place(section_id)
    if place is None:
        return Subject(statement=(), anywhere=False, own=(), place=None, section=None)
    return Subject(statement=(), anywhere=False, own=place.start_units, place=place.opening, section=place)


def unplaced_subject() -> Subject:
    """The encounter, or an anatomy entry: an object pass 1 gives no statement of its own, so a ``statement`` or
    ``placing`` source need only exist, and nothing can be its ``section``, ``frame`` or ``antecedent``."""
    return Subject(statement=(), anywhere=True, own=(), place=None, section=None)


# --- G1: link geometry ------------------------------------------------------------------------------------------------


def frame_units(sources: Iterable[Source]) -> frozenset[str]:
    """The frame units for ``document_frame`` (G1): every unit cited by the given sources, which are the sources of the
    encounter's facts (the date of service, the documenting clinician) and of each session's kind."""
    return frozenset(unit_id for source in sources for unit_id in source.units)


def link_reasons(layout: Layout, sections: Sections, subject: Subject, source: Source,
                 frame: frozenset[str] = frozenset()) -> tuple[Reason, ...]:
    """G1 on one source of a fact about ``subject``: () when its link's geometry holds, else (geometry_<link>,). The
    geometry of each link is the module's docstring; ``frame`` is ``frame_units``. Only offsets and unit ids are read."""
    units = tuple(source.units)
    known = bool(units) and all(layout.unit(unit_id) is not None for unit_id in units)
    link = source.link
    if link is Link.STATEMENT:
        holds = known and (subject.anywhere or all(unit_id in subject.statement for unit_id in units))
    elif link is Link.SECTION:
        holds = known and subject.section is not None and _cites_section(layout, subject.section, source)
    elif link is Link.FRAME:
        holds = subject.section is not None and _within(locate(layout, source).place, subject.section.span)
    elif link is Link.PLACING:
        holds = known and not any(unit_id in subject.own for unit_id in units)
    elif link is Link.DOCUMENT_FRAME:
        opening = sections.opening
        holds = (known and opening is not None and _within(locate(layout, source).place, opening.span)
                 and all(unit_id in frame for unit_id in units))
    elif link is Link.ANTECEDENT:
        found = locate(layout, source)
        first = layout.unit(subject.own[0]) if subject.own and subject.place is not None else None
        holds = (found.place is not None and found.span is not None and first is not None
                 and found.span.end <= first.start)
    else:
        holds = known
    return () if holds else (_GEOMETRY[link],)


# --- G3, G4, G5, G6 ---------------------------------------------------------------------------------------------------


def target_reasons(layout: Layout, anchor: Anchor, source: Source) -> tuple[Reason, ...]:
    """G3's statement tie for a target fact's source: with link ``statement``, its words (its units, for words '') lie
    inside the anchor's units, not merely in their closure: (target_detached,) otherwise. A source with another link is
    not G3's (() )."""
    if source.link is not Link.STATEMENT:
        return ()
    return () if _within(locate(layout, source).place, layout.span(anchor.units)) else (Reason.TARGET_DETACHED,)


def lesion_reasons(layout: Layout, sections: Sections, anchor: Anchor, restatements: Sequence[Restatement],
                   description: Source, anchored: frozenset[str]) -> tuple[Reason, ...]:
    """G3 for target.lesion (3.1 G3: the description unit IS the anchor, a restatement or an antecedent): the lesion's
    description units are among the act's anchor units (a run passing I3), or among the units of one of its valid
    restatements (G6) - never their sentence closure - or the description ends before the act's own words (an
    antecedent: identity rule 1, generalised; D207); (target_detached,) otherwise."""
    units = tuple(description.units)
    if units and not layout.run(tuple(anchor.units)) and _among(units, anchor.units):
        return ()
    for restatement in restatements:
        if (units and restatement_valid(layout, sections, restatement, anchored)
                and _among(units, restatement.units)):
            return ()
    own = locate_anchor(layout, anchor).place
    place = locate(layout, description).place
    if own is not None and place is not None and place.end <= own.start:
        return ()
    return (Reason.TARGET_DETACHED,)


def inherit_reasons(sections: Sections, anchor: Anchor) -> tuple[Reason, ...]:
    """G4: () when the act's anchor lies inside its containing section's span (``Sections.attached``), else
    (inherit_unattached,). An anchor that fails I3 places nothing, so nothing attaches."""
    place = locate_anchor(sections.layout, anchor).place
    return () if place is not None and sections.attached(place) is not None else (Reason.INHERIT_UNATTACHED,)


def anchored_units(anchors: Iterable[Anchor]) -> frozenset[str]:
    """G6's set (and so G3's, through G6): every unit some event of the answer is anchored in - acts and statements
    about acts alike, denials included, valid or not: an invalid anchor still names where pass 1 placed an event, so
    counting it can only demote. D198 keeps G6's broad reading (restatement units are never an anchor unit of any
    event); G5 reads ``extent_units`` instead."""
    return frozenset(unit_id for anchor in anchors for unit_id in anchor.units)


def extent_units(layout: Layout, sections: Sections, events: Sequence[Event], examination: int | None) -> Extent:
    """G5's units for one session (D198). ``events``: every event of the answer, in its order; ``examination``: the
    position among them of the session's examination event, None when it has none. ``own``: the examination's anchor
    units (when the anchor passes I3: one that fails places nothing, as for G4) and the units of its valid restatements
    (G6). ``acts``: the anchor units and the valid restatement units of every other event whose claimed status is not
    negated - an act of this session or another, another session's examination included; a denial's anchor is no
    act's. A missing status counts as an act's (fail-closed)."""
    told = tuple(events)
    anchored = anchored_units(event.anchor for event in told)
    own: set[str] = set()
    acts: set[str] = set()
    for position, event in enumerate(told):
        restated = [restatement.units for restatement in event.restatements
                    if restatement_valid(layout, sections, restatement, anchored)]
        if position == examination:
            if not locate_anchor(layout, event.anchor).reasons:
                own.update(event.anchor.units)
            for units in restated:
                own.update(units)
        elif event.status is not FactState.NEGATED:
            acts.update(event.anchor.units)
            for units in restated:
                acts.update(units)
    return Extent(own=frozenset(own), acts=frozenset(acts))


def extent_reasons(layout: Layout, source: Source, extent: Extent) -> tuple[Reason, ...]:
    """G5 (D36 restated [R:CO-6], D198) on one source of a session's reached, completion, stations, approach or through
    fact: () when some unit its words lie in (every cited unit, for words '') is one of the examination's own units or a
    unit no act is told in (``extent_units``); (extent_inferred,) when it lies only in acts' units, of this session or
    another, or cannot be placed. There is no section test."""
    place = locate(layout, source).place
    if place is None:
        return (Reason.EXTENT_INFERRED,)
    for unit_id in source.units:
        unit = layout.unit(unit_id)
        if (unit is not None and unit.start < place.end and place.start < unit.end
                and (unit_id in extent.own or unit_id not in extent.acts)):
            return ()
    return (Reason.EXTENT_INFERRED,)


def restatement_valid(layout: Layout, sections: Sections, restatement: Restatement, anchored: frozenset[str]) -> bool:
    """G6: a restatement counts only when its units pass I1 and I3, none of them is any event's anchor unit
    (``anchored_units``, D198), and, for a ``title`` restatement, it lies in N0's span or in a section's start.
    Otherwise it is ignored (no reason: 3.1 G6)."""
    units = tuple(restatement.units)
    if layout.run(units) or any(unit_id in anchored for unit_id in units):
        return False
    if restatement.role is not RestatementRole.TITLE:
        return True
    opening = sections.opening
    if opening is not None and _within(layout.span(units), opening.span):
        return True
    return any(place.start_units and _among(units, place.start_units) for place in sections.places)


# --- helpers ----------------------------------------------------------------------------------------------------------


def _ordered(reasons: Iterable[Reason]) -> tuple[Reason, ...]:
    """Distinct reasons in Reason's order."""
    return tuple(sorted(set(reasons), key=lambda reason: _RANK[reason]))


def _consecutive(units: tuple[Unit, ...], positions: list[int]) -> bool:
    """One or more positions, each the one before plus one, all units of the first one's paragraph."""
    if not positions:
        return False
    first = positions[0]
    return all(position == first + offset and units[position].paragraph == units[first].paragraph
               for offset, position in enumerate(positions))


def _among(units: tuple[str, ...], allowed: Sequence[str] | None) -> bool:
    """Every unit id of ``units`` is one of ``allowed`` (False when ``allowed`` is None)."""
    return allowed is not None and all(unit_id in allowed for unit_id in units)


def _within(place: Span | None, span: Span | None) -> bool:
    """``place`` lies inside ``span`` (False when either is unknown)."""
    return place is not None and span is not None and span.start <= place.start and place.end <= span.end


def _cites_section(layout: Layout, section: SectionPlace, source: Source) -> bool:
    """G1 ``section``: the source's place - its located words, or its units' span for words '' - lies inside the place
    of the containing section's start source (an opening part's empty start holds nothing) or inside the place of one of
    its closing sources, by offsets. So the words before a mid-unit label, the next section's mid-unit label, and a
    framing sentence after the label in the label's own unit are none of them this section's start."""
    place = locate(layout, source).place
    if place is None:
        return False
    if section.start_units and _within(place, section.opening):
        return True
    return any(_within(place, closer) for closer in section.closers)


def _word_char(char: str) -> bool:
    """A word character, as v1's normalize._word_char: alphanumeric, or an underscore."""
    return char.isalnum() or char == '_'


def _matches(hay: Sequence[str], needle: Sequence[str], at: int) -> bool:
    """Whether ``needle`` occurs in ``hay`` at ``at``, compared one character at a time."""
    for offset in range(len(needle)):
        if hay[at + offset] != needle[offset]:
            return False
    return True


def _bounded(hay: Sequence[str], needle: Sequence[str], at: int, word_before: bool, word_after: bool) -> bool:
    """v1's boundary rule for an occurrence at ``at``: no word character of the needle's edge touches a word character
    of the hay. ``word_before`` and ``word_after`` say whether the character just outside the hay, in the revision, is a
    word character (False: the hay is the whole text, as v1 reads a passage)."""
    end = at + len(needle)
    before = hay[at - 1] if at > 0 else None
    after = hay[end] if end < len(hay) else None
    touches_before = word_before if before is None else _word_char(before)
    touches_after = word_after if after is None else _word_char(after)
    return not (_word_char(needle[0]) and touches_before) and not (_word_char(needle[-1]) and touches_after)


def _collapsed(words: str) -> list[str]:
    """The exact tier's needle: ``words`` with each whitespace run made one space, stripped (v1's
    ``' '.join(words.split())``, one character at a time)."""
    out: list[str] = []
    pending = False
    for char in words:
        if char.isspace():
            pending = bool(out)
            continue
        if pending:
            out.append(' ')
            pending = False
        out.append(char)
    return out


def _mapped(text: str, start: int, end: int, folded: bool) -> tuple[list[str], list[int], list[int]]:
    """``text[start:end]`` as a tier reads it - each whitespace run one space, and, on the fold tier, each character
    folded - with the start and end offset in ``text`` of each character kept (v1's normalize._mapped)."""
    chars: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    for index in range(start, end):
        for piece in (fold_char(text[index]) if folded else text[index]):
            if piece.isspace():
                if chars and chars[-1] == ' ':
                    ends[-1] = index + 1
                    continue
                piece = ' '
            chars.append(piece)
            starts.append(index)
            ends.append(index + 1)
    return chars, starts, ends


def _locate(text: str, span: Span, words: str) -> tuple[LocatedWords | None, bool]:
    """The first bounded occurrence of ``words`` in ``text[span]`` - the exact tier, else the fold tier - as the
    revision's own slice, and whether the words occurred at all (bounded or not) in either tier."""
    word_before = span.start > 0 and _word_char(text[span.start - 1])
    word_after = span.end < len(text) and _word_char(text[span.end])
    occurred = False
    for folded in (False, True):
        needle: Sequence[str] = fold(words) if folded else _collapsed(words)
        if not needle:
            continue
        hay, starts, ends = _mapped(text, span.start, span.end, folded)
        for at in range(len(hay) - len(needle) + 1):
            if _matches(hay, needle, at):
                occurred = True
                if _bounded(hay, needle, at, word_before, word_after):
                    first, last = starts[at], ends[at + len(needle) - 1]
                    return LocatedWords(first, last, text[first:last]), True
    return None, occurred


def _section_start(layout: Layout, start: Source, opening_part: bool) -> tuple[int | None, Span | None,
                                                                                tuple[Reason, ...]]:
    """G2 on one section's start: its offset, its start source's place, and its reasons. The opening part (the first
    section) begins at the text start: its start cites no unit, or cites units with no unit of the text before them;
    otherwise section_order. Any other section's start must cite units and locate (I1-I3) at the offset of its words,
    else section_start_unlocated."""
    if not start.units:
        if opening_part and not start.words:
            return 0, Span(0, 0), ()
        return None, None, (Reason.SECTION_START_UNLOCATED,)
    found = locate(layout, start)
    if found.reasons or found.place is None:
        return None, None, (Reason.SECTION_START_UNLOCATED,)
    if not opening_part:
        return found.place.start, found.place, ()
    if layout.units[0].start < found.place.start:
        return found.place.start, found.place, (Reason.SECTION_ORDER,)
    return 0, found.place, ()


def _section_closing(layout: Layout, ends: tuple[Source, ...], start: int | None) -> tuple[
        tuple[Span | None, ...], int | None, tuple[Reason, ...]]:
    """G2 on one section's closing sources: each one's place (None when it does not locate), the end of the last of
    them (None unless every one locates), and reasons - section_start_unlocated when one does not locate (an unlocated
    boundary), section_order when one begins before the section's start."""
    if not ends:
        return (), None, ()
    found = tuple(locate(layout, end).place for end in ends)
    places = [place for place in found if place is not None]
    if len(places) < len(found):
        return found, None, (Reason.SECTION_START_UNLOCATED,)
    if start is not None and any(place.start < start for place in places):
        return found, max(place.end for place in places), (Reason.SECTION_ORDER,)
    return found, max(place.end for place in places), ()


def _section_reach(layout: Layout, given: tuple[Section, ...], index: int, starts: list[int | None],
                   closings: list[int | None]) -> int | None:
    """Where a section reaches as the answer lists it (G2's overlap test): the end of its closing sources when it gives
    any, else the next listed section's start, the last section the end of the text. None when that end is unknown
    (a closing source or the next start that does not locate: those are reported on their own)."""
    if given[index].end:
        return closings[index]
    if index + 1 < len(given):
        return starts[index + 1]
    return len(layout.text)


def _section_span(layout: Layout, given: tuple[Section, ...], index: int, starts: list[int | None],
                  closings: list[int | None], empty: bool) -> Span | None:
    """A section's span (G2) when it passed G2, computed over the sections sorted by start offset: from its start to the
    end of its closing sources when it gives any, else to the next start in the text (every start comes after an empty
    opening part's, D199), the last to the end of the text. None while the next listed section's start is unknown: the
    end, and whether the span overlaps the next section, cannot then be known; None too for a part of length zero (an
    empty opening part followed by a section at offset 0 contains no unit, D199)."""
    start = starts[index]
    if start is None:
        return None
    if index + 1 < len(given) and starts[index + 1] is None:
        return None
    if given[index].end:
        end = closings[index]
    else:
        later = [other for position, other in enumerate(starts) if other is not None and position != index
                 and (other > start or (other == start and index == 0 and empty))]
        end = min(later) if later else len(layout.text)
    if end is None or end <= start:
        return None
    return Span(start, end)
