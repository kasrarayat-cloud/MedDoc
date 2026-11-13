"""The strict reader of pass 2's answer (gemini-appraisal@1; docs/gemini-migration/FINAL-V2.md 3.2.4, 3.2.5, 2.4 and
1.8; step 2c of 8.1): read(answer_text, claim_set, unit_count) gives the answer's verdicts and unlisted statements,
each bound to its claim's content key, with their item-level findings (ReadAppraisal), or a Refusal of the WHOLE answer.

**The whole answer, in this order; the first failure refuses it and nothing of it is read** (3.2.4: "Strict JSON, the
schema and the bounds refuse the whole answer, as for pass 1"):
1. JSON, strictly (participants.reading.strict_json_text: a repeated key, NaN or Infinity, a number too large, NUL or a
   lone surrogate), stage ``json``;
2. appraise_schema.LOCAL_SCHEMA, by CPT Studio's own validator (participants.reading.schema_error), stage ``schema``;
3. the bounds of 1.8, each named by count, never truncated, stage ``bounds``: at most one verdict per claim of the
   request (the request's own claim count), at most 8 evidence units per verdict, at most 32 unlisted entries.

**Item-level findings demote only the claim they affect** (3.2.4), and never refuse the answer:
- a verdict naming no claim of the request is ignored (``unknown``);
- a claim answered more than once has no verdict (``repeated``): neither answer is read for it;
- a claim no verdict answers has none (``missing``); settle gives it appraisal_missing, and health counts it (3.2.6);
- an evidence unit that is no unit of the revision makes the verdict's evidence ignored (``evidence_unknown``) -
  fail-closed, so a ``supports`` resting on it cannot count as attached;
- an unlisted entry is always kept (3.2.6: fail-closed uses only): a unit that is no unit of the revision is dropped
  from it (``unit_unknown``), and a session that names no session card of the request is read as no session
  (``session_unknown``), so it pairs with every session (3.2.6 rule 4).

**The evidence attachment check** (3.2.5, deterministic): a ``supports`` verdict counts only when at least one of its
evidence units is among the claim's cited units - which, for an inherited or placed fact, are the governing source's
(claims.py) - or the units of the card the claim is about (its anchor's sentence closure, or a lesion's or anatomy
entry's description). ReadVerdict.attached_evidence says whether it holds; for ``contradicts`` and ``qualified`` the
evidence units are kept as they are, as counter sources (settle stores and quotes them; the verdict demotes whether or
not they locate).

**Bound to the claim** [R:MO-5]: each ReadVerdict carries its claim's content key, so a verdict is never read against a
different claim, whatever the claim ids.

Nothing here judges a verdict or reads a word of the document: it reads ids, enumeration values and counts. A refusal's
reason is CPT Studio's own sentence (extract_read's Refusal, the shared type): it names places by path and position and
values by count, never the model's text. An answer is read only under LOCAL_SCHEMA's pin (check_pin), which stays empty
until the integration owner writes it (2.5): until then no answer is read.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, cast

from studio import interpretation
from studio.interpretation.contract import appraise_schema, claims, jsonschema
from studio.interpretation.contract.extract_read import Refusal, refuse, unit_known
from studio.interpretation.contract.types import (Attached, CardType, Kind, Qualifier2, Unlisted, UnlistedWhat, Verdict,
                                                  VerdictValue)
from studio.participants import reading

Bound = appraise_schema.Bound


@unique
class VerdictFinding(Enum):
    """An item-level finding on a claim's verdict (3.2.4)."""
    MISSING = 'missing'  # no verdict answers the claim
    REPEATED = 'repeated'  # more than one verdict answers it: none is read
    EVIDENCE_UNKNOWN = 'evidence_unknown'  # an evidence unit is no unit of the revision: the evidence is ignored


@unique
class UnlistedFinding(Enum):
    """An item-level finding on an unlisted entry; the entry is kept either way (3.2.6)."""
    UNIT_UNKNOWN = 'unit_unknown'  # a unit that is no unit of the revision, dropped from the entry
    SESSION_UNKNOWN = 'session_unknown'  # a session that names no session card of the request: read as none


@dataclass(frozen=True, slots=True)
class ReadVerdict:
    """A claim of the request and pass 2's answer to it. claim: its id; content: its content key (claims.py), which
    binds the verdict [R:MO-5]; verdict: the verdict as read (types.Verdict, its evidence emptied when it named an
    unknown unit), None when missing or repeated; findings: the item-level findings on it; attached_evidence: 3.2.5's
    check, True when an evidence unit is among the claim's cited units or its card's units."""
    claim: str
    content: str
    verdict: Verdict | None
    findings: tuple[VerdictFinding, ...]
    attached_evidence: bool


@dataclass(frozen=True, slots=True)
class ReadUnlisted:
    """An unlisted statement pass 2 reports (2.4 A6; 3.2.6), kept whatever its findings: unlisted, as read (its known
    units; its kind; its session card's id, or None); session, the id of that session in pass 1's answer, None when it
    names none or no known one; findings."""
    unlisted: Unlisted
    session: str | None
    findings: tuple[UnlistedFinding, ...]


@dataclass(frozen=True, slots=True)
class ReadAppraisal:
    """An appraisal read: answer, the parsed JSON exactly as parsed; verdicts, one per claim of the request, in the
    claim set's order; unknown, the positions of the verdicts that named no claim (ignored); unlisted, every entry, in
    the answer's order."""
    answer: dict[str, Any]
    verdicts: tuple[ReadVerdict, ...]
    unknown: tuple[int, ...]
    unlisted: tuple[ReadUnlisted, ...]

    def verdict(self, claim_id: str) -> ReadVerdict | None:
        """The read verdict of that claim, None when the request had no such claim."""
        return next((item for item in self.verdicts if item.claim == claim_id), None)


def check_pin() -> None:
    """RuntimeError unless LOCAL_SCHEMA is byte for byte what APPRAISAL_VERSION pins (2.5; v1's read.check_pin
    pattern). An empty pin (step 0b's placeholder) is refused too: no answer is read under a schema nobody pinned. Until
    the first recording under the label a changed schema needs only its pin recomputed; after it, a new
    APPRAISAL_VERSION (DECISIONS D202)."""
    pinned = interpretation.APPRAISAL_LOCAL_SCHEMA_SHA256
    version = interpretation.APPRAISAL_VERSION
    if not pinned:
        raise RuntimeError(f'The local schema of {version} has no pin yet; an answer is read only under its pin.')
    if jsonschema.sha256_of(appraise_schema.LOCAL_SCHEMA) != pinned:
        raise RuntimeError(f'The local schema no longer matches the {version} pin; a changed schema needs its pin '
                           'recomputed before the first recording under the label, and a new APPRAISAL_VERSION after '
                           'it (DECISIONS D202).')


def read(answer: object, claim_set: claims.ClaimSet, unit_count: int) -> Refusal | ReadAppraisal:
    """Pass 2's answer to the request ``claim_set`` was built into, parsed and checked whole as 3.2.4 says, then item by
    item; or the Refusal of all of it. ``unit_count``: the number of units contract/segment.py cut the revision into.
    Nothing is repaired, coerced or truncated. RuntimeError when LOCAL_SCHEMA is not pinned or no longer matches its
    pin; ValueError for a unit count that is not a whole number of at least 0."""
    check_pin()
    if type(unit_count) is not int or unit_count < 0:
        raise ValueError('The unit count is a whole number of at least 0.')
    if not isinstance(answer, str):
        return refuse('json', 'there is no appraisal text')
    try:
        parsed = reading.strict_json_text(answer)
    except reading.JSONRefused as exc:
        return refuse('json', f'the appraisal {exc}')
    error = reading.schema_error(parsed, appraise_schema.LOCAL_SCHEMA, 'the appraisal')
    if error:
        return refuse('schema', f'the appraisal breaks its schema: {error}')
    parsed = cast(dict[str, Any], parsed)  # the schema's root is an object
    error = bound_error(parsed, len(claim_set.claims))
    if error:
        return refuse('bounds', error)
    return _read(parsed, claim_set, unit_count)


def bound_error(answer: Mapping[str, Any], claim_count: int) -> str:
    """The first bound of 1.8 a schema-valid answer breaks, named by count, or '': the verdicts (one per claim of the
    request), the unlisted entries, then each verdict's evidence."""
    verdicts, unlisted = answer['verdicts'], answer['unlisted']
    if len(verdicts) > claim_count:
        return (f'it gives {len(verdicts):,} verdicts, more than the {claim_count:,} claims of the request, one verdict '
                'each')
    limit = appraise_schema.BOUNDS[Bound.UNLISTED]
    if len(unlisted) > limit:
        return f'unlisted lists {len(unlisted):,} statements, more than the {limit:,} this contract accepts'
    limit = appraise_schema.BOUNDS[Bound.EVIDENCE]
    for index, verdict in enumerate(verdicts):
        if len(verdict['evidence']) > limit:
            return (f'verdicts[{index}].evidence lists {len(verdict["evidence"]):,} units, more than the {limit:,} one '
                    'verdict may cite')
    return ''


def _read(answer: dict[str, Any], claim_set: claims.ClaimSet, unit_count: int) -> ReadAppraisal:
    """The item-level reading of a whole answer that passed 3.2.4's checks."""
    by_claim: dict[str, list[int]] = {}
    unknown: list[int] = []
    known = {claim.id for claim in claim_set.claims}
    for index, node in enumerate(answer['verdicts']):
        if node['claim'] in known:
            by_claim.setdefault(node['claim'], []).append(index)
        else:
            unknown.append(index)
    verdicts = []
    for claim in claim_set.claims:
        positions = by_claim.get(claim.id, [])
        if len(positions) != 1:
            finding = VerdictFinding.MISSING if not positions else VerdictFinding.REPEATED
            verdicts.append(ReadVerdict(claim.id, claim.content, None, (finding,), False))
            continue
        node = answer['verdicts'][positions[0]]
        evidence = tuple(node['evidence'])
        findings: tuple[VerdictFinding, ...] = ()
        if any(not unit_known(unit, unit_count) for unit in evidence):
            evidence, findings = (), (VerdictFinding.EVIDENCE_UNKNOWN,)
        verdict = Verdict(claim=claim.id, verdict=VerdictValue(node['verdict']), attached=Attached(node['attached']),
                          qualifiers=tuple(Qualifier2(value) for value in node['qualifiers']), evidence=evidence)
        verdicts.append(ReadVerdict(claim.id, claim.content, verdict, findings,
                                    attached_evidence(claim_set, claim.id, evidence)))
    sessions = {card.id: claim_set.objects[card.id][1] for card in claim_set.cards if card.type is CardType.SESSION}
    unlisted = []
    for node in answer['unlisted']:
        notes: list[UnlistedFinding] = []
        units = tuple(unit for unit in node['units'] if unit_known(unit, unit_count))
        if len(units) != len(node['units']):
            notes.append(UnlistedFinding.UNIT_UNKNOWN)
        session: str | None = node['session'] or None
        if session is not None and session not in sessions:
            notes.append(UnlistedFinding.SESSION_UNKNOWN)
            session = None
        entry = Unlisted(units=units, what=UnlistedWhat(node['what']), kind=Kind(node['kind']) if node['kind'] else None,
                         session=session)
        unlisted.append(ReadUnlisted(entry, sessions.get(session) if session is not None else None, tuple(notes)))
    return ReadAppraisal(answer, tuple(verdicts), tuple(unknown), tuple(unlisted))


def attached_evidence(claim_set: claims.ClaimSet, claim_id: str, evidence: tuple[str, ...]) -> bool:
    """3.2.5: whether at least one evidence unit is among the claim's cited units or the units of the card it is about.
    A claim about the document itself (the encounter's) has no card: its cited units alone count."""
    claim = claim_set.claim(claim_id)
    if claim is None:
        return False
    allowed = set(claim.units)
    card = claim_set.card(claim_set.about.get(claim_id, ''))
    if card is not None:
        allowed |= set(card.units)
    return any(unit in allowed for unit in evidence)
