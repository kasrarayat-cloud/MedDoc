"""The check orchestration (docs/gemini-migration/FINAL-V2.md 3.1; DECISIONS D206; step 3a of 8.1): ``check(text, pages,
read)`` runs, over pass 1's answer as contract/extract_read.py read it, every deterministic check of 3.1 that is not the
reader's own - the segmentation (1.2), the reader's item-level findings (1b), geometry (I2, I3, G1-G6, the sentence
closures and the section places: contract/geometry.py, 1c) and consistency (K1-K8, L1 and Q1: contract/consistency.py,
2b) - and returns ONE typed record, contract/types.Checked. 5b's interpret stage calls it at claim time and the re-settle
path calls it before settle (D206), so the claim set (contract/claims.py, through the findings) and the settled
inventory (contract/settle.py) rest on one implementation and stay a pure function of the revision text and pass 1's
bytes (7.4 [R:MO-5]). settle and claims read the Checked as data: they never segment, locate or measure anything
themselves (5.7 WordsNeverDecide, which binds them, is unchanged; this module is outside it, as D206 rules).

**What each finding is, and on which fact** (3.1's table, row by row; every reason is a member of contract/types.Reason):
- S2, I1, I3's per-source bound and I4: the reader's own (extract_read.ReadFact.reasons, ReadMember.reasons, and a
  restatement's ReadCitation.reasons on its role), carried as they are.
- I2 and I3 on every source of a fact and of its options (geometry.locate): words_not_in_units, words_not_bounded,
  units_not_consecutive, source_too_long, unit_unknown.
- G1 on every source of a fact and of its options, against the fact's subject (geometry.link_reasons): an event's
  anchor; a session's examination's anchor (its supported examination link); a lesion's description; a person's name;
  a section itself; the encounter and an anatomy entry anywhere. ``document_frame`` reads the frame units - every unit a
  source of the date of service, of the documenting clinician or of a session's kind cites (geometry.frame_units). A
  source whose geometry fails is listed in ``failed_links`` under its fact (settle stores its geometry from there).
- G2 (geometry.Sections): section_order and section_start_unlocated on a section's owner, occasion and performer, the
  three facts 3.1 G2 names (DECISIONS D186).
- G3 (geometry.target_reasons, lesion_reasons): target_detached on an event's target facts whose ``statement`` source
  leaves the anchor's units, and on a target.lesion whose lesion's description is neither the anchor, a valid
  restatement nor an antecedent.
- G4 (geometry.inherit_reasons): inherit_unattached on an act's INHERITED keys - its effective date relation, performer
  and performer_person when its own slot is empty (a statement's date relation only: a statement's performer is its own
  or none, 3.2.1), and every event's entry - whenever its anchor is not attached to a section with a span.
- G5 (geometry.extent_units, extent_reasons; DECISIONS D198): extent_inferred on a session's reached, completion,
  stations, approach and through sources that lie only in the units acts are told in.
- G6 (geometry.restatement_valid): no reason; a restatement it ignores is absent from ``restatements``.
- K1-K8, L1 and Q1 (consistency.check with VOCABULARY, the located words and the G4 edges): structure_<rule>, K2-K7's,
  literal_mismatch and qualified:<q>; the date literals read (``literals``); K8's groups (``joined``); the claim-time
  reference date (``document_date``).
- 3.1's cross-object rule that reads the checks alone (the w3int build's reading, its Q2): anchor_invalid on every fact
  of an event whose anchor has a reason - its own facts, its scope members, its restatements' roles and its inherited
  keys - so claims never claims one of them. The other cross-object rules read settled results and are settle's.

**The keys** are contract/extract_read.FactKey: a fact's or a member's own key; an act's inherited fact by the act's key
of that attribute (as claims.py and settle key it); a restatement's role by (its event, restatements.role, its
position). An answer's ids are read as written (S1 checked their shape); an id that names nothing finds nothing here.

**VOCABULARY** is the one wiring of consistency's tables (hand-off 2b:R2): engine/anatomy's containment and regions,
engine/catalogue's FAMILY_REACH (DECISIONS D192), covers and ENDOSCOPIC_FAMILIES, engine/requirements' EXTRACTION_KINDS,
and ``family_admits`` - a kind's membership in engine/requirements_table.FAMILY_KINDS.get(family, frozenset())
(DECISIONS D191; the integration's O9 and O14: a family the table does not list admits no kind, fail-closed).

**What this module never does** (5.6, 5.7 measure 4, P1-P9): it decides nothing about what a word means. It hands the
text to contract/segment.py and contract/geometry.py, and gives consistency's L1 the revision's own slice of a source's
located words (or of its whole cited units for words ''), which only contract/date_literals.py's copied parsers read.
It imports no regular-expression or text-folding module, holds no word, phrase, marker or frame list (NoWordLists: every
module-level collection holds enumeration members), calls no string method and runs no v1 code. A finding only ever
demotes: nothing here sets, changes or creates a value, a fact, a support, an exclusion or a contradiction (3.1).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from studio.interpretation.contract import consistency, geometry, segment
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract.extract_read import Cited, DateOfService, FactKey, ReadAnswer, ReadFact
from studio.interpretation.contract.types import (AnchorCitation, Attribute, Checked, Citation, Fact, FactState, Kind,
                                                  Link, Reason, RestatementRole, SectionPlace, SessionKind, Source)
from studio.interpretation.engine import anatomy, catalogue, requirements, requirements_table

Family = xs.Family
A = Attribute

# The facts of an act that inherit from its containing section when its own slot is empty (FINAL-V2 1.5; 3.2.1:
# a statement's performer and performer_person are its own, when named, so only its date relation inherits).
ACT_INHERITED: tuple[Attribute, ...] = (A.DATE_RELATION, A.PERFORMER, A.PERFORMER_PERSON)
STATEMENT_INHERITED: tuple[Attribute, ...] = (A.DATE_RELATION,)
# G2's demotions (3.1 G2; DECISIONS D186): a section's owner, occasion and performer.
SECTION_GEOMETRY: frozenset[Attribute] = frozenset({A.OWNER, A.OCCASION, A.PERFORMER})
# G3's target facts (3.1 G3): an event's five target fields.
TARGETS: frozenset[Attribute] = frozenset({A.TARGET_LESION, A.TARGET_STRUCTURE, A.TARGET_PLACES, A.TARGET_ANATOMY,
                                           A.TARGET_DUCT})


def family_admits(family: SessionKind, kind: Kind) -> bool:
    """K2's kind arm (DECISIONS D191; the integration's O9): whether a session of ``family`` can hold an act of ``kind`` -
    its membership in engine/requirements_table.FAMILY_KINDS.get(family, frozenset()), so a family the table does not
    list admits no kind (O14: fail-closed, the act's session fact is demoted, never set)."""
    return kind in requirements_table.FAMILY_KINDS.get(family, frozenset())


# consistency's tables, wired once (hand-off 2b:R2; DECISIONS D191, D192): what check() and every test of K1-K8 read.
VOCABULARY = consistency.Vocabulary(contains=anatomy.contains, region=anatomy.region, reach=catalogue.FAMILY_REACH,
                                    family_admits=family_admits, covers=catalogue.covers,
                                    endoscopic=catalogue.ENDOSCOPIC_FAMILIES,
                                    extraction=requirements.EXTRACTION_KINDS)


def check(text: str, pages: Sequence[segment.Page], read: ReadAnswer) -> Checked[FactKey]:
    """Every check of 3.1 the reader does not run, over pass 1's answer ``read`` to the revision ``text`` and its
    ``pages`` (the module's docstring), as one Checked record. Pure: equal arguments give an equal Checked in every
    process. ValueError when ``read`` was read against another segmentation than this text's (its unit count is not the
    number of units contract/segment.py cuts ``text`` into); TypeError and ValueError as geometry.Layout.of for a text
    or pages that are not a revision's."""
    layout = geometry.Layout.of(text, pages)
    if len(layout.units) != read.unit_count:
        raise ValueError(f'The answer was read against {read.unit_count:,} units, and this text has '
                         f'{len(layout.units):,}: it is not this revision\'s answer.')
    return _Check(layout, read).run()


# --- the orchestration ------------------------------------------------------------------------------------------------


def _source(node: Mapping[str, Any]) -> Source:
    return Source(units=tuple(node['units']), words=node['words'], link=Link(node['link']))


def _sources_of(fact: Fact | DateOfService) -> list[Source]:
    """A fact's sources, then each option's, each once, in order."""
    found: list[Source] = []
    for source in (*fact.sources, *(source for option in fact.options for source in option.sources)):
        if source not in found:
            found.append(source)
    return found


def _ordered(reasons: Iterable[Reason]) -> tuple[Reason, ...]:
    """``reasons`` once each, in the closed list's order (hand-off 1c:R6: a fact's reasons are a set)."""
    found = set(reasons)
    return tuple(reason for reason in Reason if reason in found)


def _runs(value: object) -> list[tuple[str, ...]]:
    """Every list of unit ids the answer cites (a ``units`` field anywhere in it), in the answer's order."""
    found: list[tuple[str, ...]] = []
    pending: list[object] = [value]
    while pending:
        node = pending.pop(0)
        if isinstance(node, dict):
            for key, item in node.items():
                if key == 'units' and isinstance(item, list):
                    found.append(tuple(item))
                else:
                    pending.append(item)
        elif isinstance(node, list):
            pending.extend(node)
    return found


class _Check:
    """One check: the layout and the answer, indexed, and the findings as they are gathered."""

    def __init__(self, layout: geometry.Layout, read: ReadAnswer) -> None:
        self.layout = layout
        self.read = read
        raw = read.answer
        self.raw = raw
        self.sections = geometry.Sections(layout, [
            geometry.Section(item['id'], _source(item['start']), tuple(_source(end) for end in item['end']))
            for item in raw['sections']])
        self.facts: dict[tuple[xs.Family, str, Attribute], list[ReadFact]] = {}
        for item in read.facts:
            self.facts.setdefault((item.key.family, item.key.object, item.key.attribute), []).append(item)
        self.event_ids: tuple[str, ...] = tuple(item['id'] for item in raw['events'])
        self.position: dict[str, int] = {name: index for index, name in enumerate(self.event_ids)}
        self.anchors: dict[str, geometry.Anchor] = {
            item['id']: geometry.Anchor(tuple(item['anchor']['units']), item['anchor']['kind_words'],
                                        item['anchor']['status_words']) for item in raw['events']}
        self.located: dict[str, geometry.AnchorCitation] = {
            name: geometry.locate_anchor(layout, anchor) for name, anchor in self.anchors.items()}
        self.restated: dict[str, tuple[geometry.Restatement, ...]] = {
            item['id']: tuple(geometry.Restatement(tuple(node['units']), RestatementRole(node['role']))
                              for node in item['restatements']) for item in raw['events']}
        self.anchored = geometry.anchored_units(self.anchors.values())
        self.described: dict[tuple[xs.Family, str], Source] = {
            (citation.family, citation.object): citation.source for citation in read.citations
            if citation.cited in (Cited.NAME, Cited.DESCRIPTION) and citation.source is not None}
        self.cache: dict[Source, geometry.Citation] = {}
        self.subjects: dict[tuple[xs.Family, str], geometry.Subject] = {}
        self.extents: dict[str, geometry.Extent] = {}
        self.findings: dict[FactKey, set[Reason]] = {}
        self.failed: dict[FactKey, list[Source]] = {}
        self.containing: dict[str, str] = {}
        for name, found in self.located.items():
            section = self.sections.attached(found.place) if found.place is not None else None
            if section is not None:
                self.containing[name] = section.id
        self.frame = geometry.frame_units(self.frame_sources())

    # -- reading the answer --

    def one(self, family: xs.Family, name: str, attribute: Attribute) -> ReadFact | None:
        found = self.facts.get((family, name, attribute), [])
        return found[0] if found else None

    def supported(self, family: xs.Family, name: str, attribute: Attribute) -> str | None:
        """The value of a slot's fact when it is supported, else None."""
        found = self.one(family, name, attribute)
        if found is None or not isinstance(found.fact, Fact) or found.fact.state is not FactState.SUPPORTED:
            return None
        return found.fact.value

    def statement(self, name: str) -> bool:
        """An event whose claimed status pass 1 stated negated (3.2.1)."""
        found = self.one(Family.EVENT, name, A.STATUS)
        return found is not None and isinstance(found.fact, Fact) and found.fact.state is FactState.NEGATED

    def cite(self, source: Source) -> geometry.Citation:
        found = self.cache.get(source)
        if found is None:
            found = self.cache[source] = geometry.locate(self.layout, source)
        return found

    def words(self, source: Source) -> str | None:
        """consistency.Words: the revision's own slice of a source's located words, or of its whole cited units for
        words ''; None when the source does not locate (I1-I3 failed)."""
        found = self.cite(source)
        if found.reasons or found.place is None:
            return None
        return self.layout.text[found.place.start:found.place.end]

    def frame_sources(self) -> list[Source]:
        """The sources of the encounter's facts (the date of service, the documenting clinician) and of each session's
        kind: what makes a unit a frame unit (3.1 G1 ``document_frame``)."""
        found: list[Source] = []
        for family, name, attribute in ((Family.ENCOUNTER, '', A.DATE_OF_SERVICE),
                                        (Family.ENCOUNTER, '', A.DOCUMENTING_CLINICIAN)):
            for item in self.facts.get((family, name, attribute), []):
                found += _sources_of(item.fact)
        for item in self.raw['sessions']:
            for fact in self.facts.get((Family.SESSION, item['id'], A.KIND), []):
                found += _sources_of(fact.fact)
        return found

    def subject(self, family: xs.Family, name: str) -> geometry.Subject:
        """The object a fact is about, as G1 measures its sources (geometry's subject builders)."""
        found = self.subjects.get((family, name))
        if found is not None:
            return found
        if family is Family.EVENT and name in self.anchors:
            found = geometry.event_subject(self.layout, self.sections, self.anchors[name])
        elif family is Family.SESSION:
            examination = self.supported(Family.SESSION, name, A.EXAMINATION)
            anchor = self.anchors.get(examination) if examination is not None else None
            found = geometry.session_subject(self.layout, self.sections, anchor)
        elif family in (Family.LESION, Family.PERSON) and (family, name) in self.described:
            found = geometry.described_subject(self.layout, self.sections, self.described[(family, name)])
        elif family is Family.SECTION:
            found = geometry.section_subject(self.sections, name)
        else:
            found = geometry.unplaced_subject()
        self.subjects[(family, name)] = found
        return found

    def extent(self, session: str) -> geometry.Extent:
        """G5's units for one session (DECISIONS D198): its examination's, and those the acts are told in."""
        found = self.extents.get(session)
        if found is None:
            examination = self.supported(Family.SESSION, session, A.EXAMINATION)
            events = [geometry.Event(self.anchors[name], self.restated[name], self.status_state(name))
                      for name in self.event_ids]
            position = self.position.get(examination) if examination is not None else None
            found = self.extents[session] = geometry.extent_units(self.layout, self.sections, events, position)
        return found

    def status_state(self, name: str) -> FactState | None:
        found = self.one(Family.EVENT, name, A.STATUS)
        return found.fact.state if found is not None and isinstance(found.fact, Fact) else None

    # -- gathering --

    def add(self, key: FactKey, reasons: Iterable[Reason]) -> None:
        self.findings.setdefault(key, set()).update(reasons)

    def run(self) -> Checked[FactKey]:
        for item in self.read.facts:
            self.fact(item)
        for member in self.read.members:
            self.add(member.key, member.reasons)
        restatements = self.restatements()
        for citation in self.read.citations:
            if citation.cited is Cited.RESTATEMENT:
                self.add(FactKey(Family.EVENT, citation.object, A.RESTATEMENTS_ROLE, citation.index), citation.reasons)
        inherited = self.inherited()
        found = consistency.check(self.read, VOCABULARY, self.words, self.containing)
        for mapping in (found.structure, found.consistency, found.literal, found.qualified):
            for key, reasons in mapping.items():
                self.add(key, reasons)
        self.anchor_rule(inherited)
        citations = {source: _citation(self.cite(source)) for source in self.sources()}
        return Checked(
            units=self.layout.units, closures=self.closures(), citations=citations,
            anchors={name: _anchor_citation(found_anchor) for name, found_anchor in self.located.items()},
            sections=tuple(_section_place(place) for place in self.sections.places), containing=self.containing,
            restatements=restatements,
            findings={key: _ordered(reasons) for key, reasons in self.findings.items()},
            failed_links={key: tuple(sources) for key, sources in self.failed.items()},
            literals=dict(found.literals),
            joined=tuple((group.supported, group.negated) for group in found.joined),
            document_date=found.document_date, objectless_doubts=self.objectless())

    def fact(self, item: ReadFact) -> None:
        """One fact's I2, I3, G1, G2, G3 and G5 findings, with the reader's own."""
        key, fact = item.key, item.fact
        self.add(key, item.reasons)
        sources = _sources_of(fact)
        for source in sources:
            self.add(key, self.cite(source).reasons)
        subject = self.subject(key.family, key.object)
        for source in sources:
            failed = geometry.link_reasons(self.layout, self.sections, subject, source, self.frame)
            if failed:
                self.add(key, failed)
                if source not in self.failed.setdefault(key, []):
                    self.failed[key].append(source)
        if key.family is Family.SECTION and key.attribute in SECTION_GEOMETRY:
            place = self.sections.place(key.object)
            if place is not None:
                self.add(key, place.reasons)
        if key.family is Family.EVENT and key.attribute in TARGETS and key.object in self.anchors:
            anchor = self.anchors[key.object]
            for source in sources:
                self.add(key, geometry.target_reasons(self.layout, anchor, source))
            if (key.attribute is A.TARGET_LESION and isinstance(fact, Fact)
                    and fact.state in (FactState.SUPPORTED, FactState.NEGATED)
                    and (Family.LESION, fact.value) in self.described):
                self.add(key, geometry.lesion_reasons(self.layout, self.sections, anchor, self.restated[key.object],
                                                      self.described[(Family.LESION, fact.value)], self.anchored))
        if key.family is Family.SESSION and key.attribute in geometry.EXTENT_ATTRIBUTES:
            extent = self.extent(key.object)
            for source in sources:
                self.add(key, geometry.extent_reasons(self.layout, source, extent))

    def inherited(self) -> list[FactKey]:
        """G4 on every inherited key (the module's docstring): inherit_unattached when the act's anchor is not attached
        to a section with a span. Returns the inherited keys, in the events' order."""
        keys: list[FactKey] = []
        for name in self.event_ids:
            attributes = STATEMENT_INHERITED if self.statement(name) else ACT_INHERITED
            owned = [attribute for attribute in attributes if self.one(Family.EVENT, name, attribute) is None]
            for attribute in (*owned, A.ENTRY):
                key = FactKey(Family.EVENT, name, attribute, 0)
                keys.append(key)
                self.add(key, geometry.inherit_reasons(self.sections, self.anchors[name]))
        return keys

    def restatements(self) -> dict[tuple[str, int], str | None]:
        """G6: each restatement it counts, by (event, position), and the section its units lie attached in (None when
        none); a restatement it ignores is absent."""
        found: dict[tuple[str, int], str | None] = {}
        for name in self.event_ids:
            for index, restatement in enumerate(self.restated[name]):
                if not geometry.restatement_valid(self.layout, self.sections, restatement, self.anchored):
                    continue
                span = self.layout.span(restatement.units)
                section = self.sections.attached(span) if span is not None else None
                found[(name, index)] = section.id if section is not None else None
        return found

    def anchor_rule(self, inherited: Sequence[FactKey]) -> None:
        """3.1's cross-object rule that reads the checks alone: an event whose anchor fails I3 has every fact
        unresolved (anchor_invalid) - its own facts, its members, its restatements' roles and its inherited keys."""
        invalid = {name for name, found in self.located.items() if found.reasons}
        if not invalid:
            return
        keys = [item.key for item in self.read.facts] + [member.key for member in self.read.members]
        keys += [FactKey(Family.EVENT, citation.object, A.RESTATEMENTS_ROLE, citation.index)
                 for citation in self.read.citations if citation.cited is Cited.RESTATEMENT]
        keys += list(inherited)
        for key in keys:
            if key.family is Family.EVENT and key.object in invalid:
                self.add(key, (Reason.ANCHOR_INVALID,))

    def objectless(self) -> dict[int, tuple[str, ...]]:
        """DECISIONS D200: each malformed doubt that names no object it resolves, by its position: the events whose
        anchor units include one of its units, in the answer's order (() when none does). Unit ids only."""
        found: dict[int, tuple[str, ...]] = {}
        for doubt in self.read.doubts:
            if doubt.objects:
                continue
            units = set(doubt.doubt.units)
            found[doubt.index] = tuple(name for name in self.event_ids if units & set(self.anchors[name].units))
        return found

    def sources(self) -> list[Source]:
        """Every source of the answer: each fact's and each option's, the date of service's, each person's name, each
        section's start and closing sources, each lesion's description - each once, in the answer's order."""
        found: list[Source] = []
        for item in self.read.facts:
            found += _sources_of(item.fact)
        found += [citation.source for citation in self.read.citations if citation.source is not None]
        return list(dict.fromkeys(found))

    def closures(self) -> dict[tuple[str, ...], tuple[str, ...]]:
        """The sentence closure (1.2 rule 6) of each run the answer cites; a run failing I1 or I3 has none."""
        found: dict[tuple[str, ...], tuple[str, ...]] = {}
        for run in _runs(self.raw):
            if run and run not in found:
                closure = self.layout.closure(run)
                if closure is not None:
                    found[run] = closure
        return found


# --- geometry's records, copied into contract/types' (field for field; the w3int build's R1 makes them one) -----------


def _citation(found: geometry.Citation) -> Citation:
    return Citation(units=found.units, span=found.span, words=found.words, place=found.place, reasons=found.reasons)


def _anchor_citation(found: geometry.AnchorCitation) -> AnchorCitation:
    return AnchorCitation(units=found.units, span=found.span, kind_words=found.kind_words,
                          status_words=found.status_words, place=found.place, reasons=found.reasons)


def _section_place(found: geometry.SectionPlace) -> SectionPlace:
    return SectionPlace(id=found.id, index=found.index, start=found.start, opening=found.opening,
                        start_units=found.start_units, end_units=found.end_units, closers=found.closers,
                        closed=found.closed, closing=found.closing, span=found.span, reasons=found.reasons)

