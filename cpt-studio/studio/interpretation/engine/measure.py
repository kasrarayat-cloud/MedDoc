"""What the engine exposes so the blind acceptance set can be measured (docs/gemini-migration/FINAL-V2.md 9.1; step 5a
of 8.1; schema cpt-studio-measure@1): ``export`` writes one run of one document as 9.1's JSON - a superset of everything
an expected outcome can name, keyed by revision offsets (anchors are run-independent; Gemini's event and unit ids are
not), so the acceptance owner's comparator scores it without reading the engine. Operator data, kept out of customer
screens.

**The shape is 9.1's, key for key** (tests/v2/test_measure.py parses 9.1's own JSON block out of FINAL-V2.md and
compares every key and value type):
- ``case``: the document's and the revision text's sha256 and the run's index; ``runs``: the label and both passes'
  runs (run id, request and response sha256, the model that answered, usage {prompt, candidates, thoughts}, cost and
  seconds), as the caller recorded them; ``versions``: the assessment's D22 fields;
- ``encounter``: the date of service (the effective value and the document fact's result), the service questions (each
  as an item), the unlisted statements kept (each statement's units as one span) and dropped (each unit's span, and the
  event that absorbed it, from the verification report), and the doubts pass 1 reported (about, objects, basis, units);
  a unit id the row does not have is left out of these spans, as engine/facts.py reads it (an item-level finding the
  store keeps), never a reason to export nothing;
- ``codes``: every proposal (selected and excluded; alternatives are not codes): its code, origin (the proposal
  provider's name for a code it proposed, else participant or second_review), proposers, status, its acts (E*: event,
  kind, session, anchor), its one item (fact key, question or explanation, subject, the spans it quotes, cause), every
  held fact (fact, subject, result, reason, cause, rank), its trace (requirement, truth, the first witness's subject,
  attribute, result and reason), its exclusion (event, deciding fact, cover, anchor) and its considerations;
- ``facts``: every stored fact (a FACT record of the row, each member of a list its own entry): its subject (None for
  the encounter), attribute, the section it was inherited from, its claim's state and value, its result, reasons, pass
  2's verdict on its claim and on its control;
- ``relations``: every statement paired with an act (engine/pairing.py): the two events, the relation's name and its
  row (the deciding row's name; for a contradiction or a doubt, which no single row decides, the statement's breadth
  when established, else None);
- ``health``: the share of the appraisal's claims established, and of its controlled claims whose control pass 2
  rejected (settle's 3.2.6 measures, from the verification report); None where nothing was measured;
- ``guard``: the sentinel's legacy and retired calls (the D22 record's).
Offsets are [start, end] lists; ids are pass 1's form; enumeration members their values.

**The text-free boundary** (P1, FINAL-V2 5.7 measures 4 and 5): this module imports the standard library,
contract/types.py and engine's assess, facts, pairing and types only, reads the stored row through
store.textfree_v2's view (no text, no words: D188) and the verification report's counts, holds no word list, and
``mypy --strict`` passes over it.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, unique

from studio.interpretation.contract.types import Attribute, Breadth, Result
from studio.interpretation.engine import assess as assess_
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import pairing
from studio.interpretation.engine.types import FactSet, HeldFact, Id, Span

SCHEMA = 'cpt-studio-measure@1'


@unique
class Label(Enum):
    """What a run is (9.1 runs.label; 9.6's labels)."""
    FRESH_ACCEPTANCE = 'fresh-acceptance'
    FRESH_DEV = 'fresh-dev'
    REPLAY = 'replay'
    TEXT_ONLY = 'text-only'
    SYNTHETIC = 'synthetic'


@dataclass(frozen=True, slots=True)
class Usage:
    """A run's token counts as the provider reported them."""
    prompt: int
    candidates: int
    thoughts: int


@dataclass(frozen=True, slots=True)
class Run:
    """One pass's run as recorded (ProviderRun): its id, request and response sha256, the model that answered, its
    usage, its estimated cost in dollars and its seconds."""
    run: str
    request_sha256: str
    response_sha256: str
    model: str
    usage: Usage
    usd: float
    seconds: float


@dataclass(frozen=True, slots=True)
class Case:
    """Which document and which run: the document's sha256, the revision text's sha256, the run's index (from 1)."""
    document_sha256: str
    revision_text_sha256: str
    run_index: int


@dataclass(frozen=True, slots=True)
class Guard:
    """The sentinel's D22 counts for the run (5.7 measures 1 and 9): legacy and retired executions on the new path."""
    legacy_calls: int
    retired_calls: int


def _spans(spans: Sequence[Span]) -> list[list[int]]:
    return [[span.start, span.end] for span in spans]


def _id(value: Id | None) -> str | None:
    return None if value is None else str(value)


def _enum(value: Enum | None) -> object:
    return None if value is None else value.value


# --- the stored row (store.textfree_v2's view; D188) ------------------------------------------------------------------


def _mapping(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f'The stored inventory is not readable: {where} is no record.')
    return value


def _sequence(value: object, where: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f'The stored inventory is not readable: {where} is no list.')
    return value


def _unit_spans(view: Mapping[str, object]) -> dict[str, Span]:
    """The row's units table, id -> span."""
    out: dict[str, Span] = {}
    for index, unit in enumerate(_sequence(view.get('units'), 'units')):
        record = _mapping(unit, f'units[{index}]')
        label, start, end = record.get('id'), record.get('start'), record.get('end')
        if not isinstance(label, str) or type(start) is not int or type(end) is not int:
            raise ValueError(f'The stored inventory is not readable: units[{index}] has no id and offsets.')
        out[label] = Span(start, end)
    return out


def _cited(units: Mapping[str, Span], cited: object, where: str) -> list[Span]:
    """The spans of the units a doubt or an unlisted statement cites, in its order: a unit id the row does not have is
    left out, as engine/facts.py reads it (3.1 I1's unit_unknown is an item-level finding, and the store keeps pass 1's
    doubts as given: the refutation's P5), so a storable row always exports; a cited id that is no string is no row's
    (ValueError)."""
    found = []
    for label in _sequence(cited, where):
        if not isinstance(label, str):
            raise ValueError(f'The stored inventory is not readable: {where} cites a unit by no id.')
        if label in units:
            found.append(units[label])
    return found


def _joined(spans: Sequence[Span]) -> list[list[int]]:
    """A statement's units as ONE span, from its first unit's start to its last unit's end (9.1 unlisted.kept)."""
    if not spans:
        return []
    return [[min(span.start for span in spans), max(span.end for span in spans)]]


def _is_fact(value: object) -> bool:
    """A FACT record of the row (1.7): a claim and a result."""
    return isinstance(value, Mapping) and isinstance(value.get('claim'), Mapping) and isinstance(value.get('result'),
                                                                                                   str)


def _facts_in(record: Mapping[str, object], prefix: str) -> Iterator[tuple[str, Mapping[str, object]]]:
    """Every FACT inside one object record with its attribute path (``<field>.<field>`` for a nested field; each member
    of a list its own entry), found by shape alone: a source, an anchor or a completeness record holds no claim."""
    for name, value in record.items():
        path = f'{prefix}{name}'
        if _is_fact(value) and isinstance(value, Mapping):
            yield path, value
        elif isinstance(value, Mapping):
            yield from _facts_in(value, f'{path}.')
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                if _is_fact(item) and isinstance(item, Mapping):
                    yield path, item
                elif isinstance(item, Mapping):
                    yield from _facts_in(item, f'{path}.')


def _verdicts(found: Mapping[str, object]) -> tuple[object, object]:
    """Pass 2's verdict on a fact's claim and on its control (None where there is none)."""
    appraisal = found.get('appraisal')
    if not isinstance(appraisal, Mapping):
        return None, None
    control = appraisal.get('control')
    return appraisal.get('verdict'), control.get('verdict') if isinstance(control, Mapping) else None


def _fact_entry(subject: str | None, attribute: str, found: Mapping[str, object]) -> dict[str, object]:
    claim = _mapping(found.get('claim'), f'{attribute} claim')
    verdict, control = _verdicts(found)
    reasons = found.get('reasons')
    return {'subject': subject, 'attribute': attribute, 'inherited_from': claim.get('inherited_from'),
            'claim': {'state': claim.get('state'), 'value': claim.get('value')}, 'result': found.get('result'),
            'reasons': list(reasons) if isinstance(reasons, Sequence) and not isinstance(reasons, str) else [],
            'verdict': verdict, 'control': control}


def stored_facts(view: Mapping[str, object]) -> list[dict[str, object]]:
    """9.1's ``facts``: every FACT of the row - the encounter's (subject None), then each object's in 1.7's order of the
    families and pass 1's order of the objects. ValueError for a path that is no Attribute of contract/types.py."""
    out: list[dict[str, object]] = []
    known = {attribute.value for attribute in Attribute}
    objects: list[tuple[str | None, Mapping[str, object]]] = [(None, _mapping(view.get('encounter'), 'encounter'))]
    for family in ('people', 'sections', 'sessions', 'anatomy', 'lesions', 'events'):
        for index, item in enumerate(_sequence(view.get(family), family)):
            objects.append((family, _mapping(item, f'{family}[{index}]')))
    for owner, record in objects:
        label = record.get('id') if owner is not None else None
        subject = label if isinstance(label, str) else None
        for path, found in _facts_in(record, ''):
            if path not in known:
                raise ValueError(f'The stored inventory is not readable: {path} is no attribute.')
            out.append(_fact_entry(subject, path, found))
    return out


def _doubts(view: Mapping[str, object], units: Mapping[str, Span]) -> list[dict[str, object]]:
    out = []
    for index, item in enumerate(_sequence(view.get('doubts'), 'doubts')):
        doubt = _mapping(item, f'doubts[{index}]')
        objects = doubt.get('objects')
        out.append({'about': doubt.get('about'),
                    'objects': [str(value) for value in _sequence(objects, f'doubts[{index}].objects')],
                    'basis': doubt.get('basis'),
                    'units': _spans(_cited(units, doubt.get('units'), f'doubts[{index}].units'))})
    return out


def _unlisted(view: Mapping[str, object], report: Mapping[str, object],
              units: Mapping[str, Span]) -> dict[str, object]:
    kept = []
    for index, item in enumerate(_sequence(view.get('unlisted'), 'unlisted')):
        entry = _mapping(item, f'unlisted[{index}]')
        kept += _joined(_cited(units, entry.get('units'), f'unlisted[{index}].units'))
    dropped = []
    record = report.get('unlisted')
    for index, item in enumerate(_sequence(record.get('dropped'), 'dropped') if isinstance(record, Mapping) else ()):
        entry = _mapping(item, f'verification.unlisted.dropped[{index}]')
        dropped.append({'units': _spans(_cited(units, entry.get('units'), f'dropped[{index}].units')),
                        'absorbed_by': entry.get('event')})
    return {'kept': kept, 'dropped': dropped}


def _share(part: object, whole: object) -> float | None:
    if type(part) is not int or type(whole) is not int or whole <= 0:
        return None
    return part / whole


def health(report: Mapping[str, object]) -> dict[str, object]:
    """9.1's ``health`` from the verification report's 3.2.6 measures (contract/settle.Health): the share of the claims
    established, and of the controlled claims whose control was rejected (pairs less not_rejected); None where nothing
    was measured."""
    measured = report.get('health')
    found = measured if isinstance(measured, Mapping) else {}
    pairs, not_rejected = found.get('pairs'), found.get('not_rejected')
    rejected = pairs - not_rejected if type(pairs) is int and type(not_rejected) is int else None
    return {'appraisal': _share(found.get('established'), found.get('claims')),
            'controls_coherent': _share(rejected, pairs)}


# --- the codes --------------------------------------------------------------------------------------------------------


def _held(held: HeldFact) -> dict[str, object]:
    return {'fact': held.fact, 'subject': _id(held.subject), 'result': _enum(held.result), 'reason': _enum(held.reason),
            'cause': held.cause, 'rank': held.rank}


def _item(held: HeldFact) -> dict[str, object]:
    return {'fact': held.fact, 'kind': held.kind.value, 'subject': _id(held.subject), 'anchor': _spans(held.spans),
            'cause': held.cause}


def _acts(found: assess_.Assessed, R: FactSet) -> list[dict[str, object]]:
    supporting = found.evaluation.supporting if found.evaluation is not None else ()
    out = []
    for event in supporting:
        kind = facts_.fact(R, event, Attribute.KIND)
        session = facts_.fact(R, event, Attribute.SESSION)
        anchor = R.anchors.get(event)
        out.append({'event': str(event), 'kind': _enum(kind.value) if isinstance(kind.value, Enum) else None,
                    'session': str(session.value) if isinstance(session.value, Id) else None,
                    'anchor': _spans(anchor.units) if anchor is not None else []})
    return out


def _origin(found: assess_.Assessed) -> str:
    """The proposal provider's name for a code it proposed (9.1: "corti | participant | second_review")."""
    if found.origin is assess_.Origin.PRIMARY and found.proposed_by:
        return found.proposed_by[0]
    return found.origin.value


def _code(found: assess_.Assessed, R: FactSet) -> dict[str, object]:
    exclusion = found.evaluation.exclusion if found.evaluation is not None else None
    return {
        'code': found.code, 'origin': _origin(found), 'proposed_by': list(found.proposed_by),
        'status': found.status.value, 'acts': _acts(found, R),
        'item': _item(found.item.held) if found.item is not None else None,
        'held_facts': [_held(held) for held in found.held_facts],
        'trace': [{'requirement': row.requirement, 'truth': row.truth.value,
                   'witness': None if row.witness is None else {
                       'subject': _id(row.witness.subject), 'attribute': _enum(row.witness.attribute),
                       'result': _enum(row.witness.result), 'reason': _enum(row.witness.reason)}}
                  for row in found.trace],
        'exclusion': None if exclusion is None else {'event': str(exclusion.event), 'fact': exclusion.fact.value,
                                                     'cover': exclusion.cover.value,
                                                     'anchor': _spans(exclusion.anchor)},
        'considerations': [found_.value for found_ in found.considerations],
    }


def _row(pair: pairing.Pair, R: FactSet) -> str | None:
    if pair.row is not None:
        return str(pair.row.value)
    breadth = facts_.fact(R, pair.statement, Attribute.SCOPE_BREADTH)
    if breadth.result is Result.SUPPORTED and isinstance(breadth.value, Breadth):
        return f'{pairing.Row.BREADTH.value} {breadth.value.value}'
    return None


def relations(R: FactSet) -> list[dict[str, object]]:
    """9.1's ``relations``: every pair of engine/pairing.py, in its order."""
    return [{'statement': str(pair.statement), 'act': str(pair.act), 'type': pair.relation.name,
             'row': _row(pair, R)} for pair in pairing.pairs(R)]


def _run(run: Run) -> dict[str, object]:
    return {'run': run.run, 'request_sha256': run.request_sha256, 'response_sha256': run.response_sha256,
            'model': run.model, 'usage': {'prompt': run.usage.prompt, 'candidates': run.usage.candidates,
                                          'thoughts': run.usage.thoughts},
            'usd': float(run.usd), 'seconds': float(run.seconds)}


# --- the export -------------------------------------------------------------------------------------------------------


def export(assessment: assess_.Assessment, *, view: Mapping[str, object], report: Mapping[str, object], case: Case,
           label: Label, pass1: Run, pass2: Run, guard: Guard, R: FactSet | None = None) -> dict[str, object]:
    """9.1's JSON for one run of one document (module docstring). ``view``: store.textfree_v2's view of the row the
    assessment read; ``report``: the row's verification report; ``R``: the FactSet the assessment was made over (by
    default facts.effective of ``view`` at the assessment's date of service, as assess reads it). Pure; reads no
    text."""
    R = R if R is not None else facts_.effective(view, assessment.date_of_service)
    units = _unit_spans(view)
    date = assessment.date_of_service
    return {
        'schema': SCHEMA,
        'case': {'document_sha256': case.document_sha256, 'revision_text_sha256': case.revision_text_sha256,
                 'run_index': case.run_index},
        'runs': {'label': label.value, 'pass1': _run(pass1), 'pass2': _run(pass2)},
        'versions': dict(assessment.versions),
        'encounter': {
            'date_of_service': {'value': date.isoformat() if date is not None else None,
                                'result': assessment.date_fact.result.value},
            'service_questions': [_item(found.item.item) for found in assessment.service_questions],
            'unlisted': _unlisted(view, report, units),
            'doubts': _doubts(view, units)},
        'codes': [_code(found, R) for found in assessment.codes],
        'facts': stored_facts(view),
        'relations': relations(R),
        'health': health(report),
        'guard': {'legacy_calls': guard.legacy_calls, 'retired_calls': guard.retired_calls},
    }
