"""Installed reference sources and the date-applicable lookup over them (ARCHITECTURE 5.5).

A source applies to a service date only when effective_start <= date <=
effective_end. At most one installed source of a kind may apply: when two
cover the same date the applicable release is ambiguous and neither is used.
Lookups return code-keyed facts only; descriptors are never imported.

``CodeReference.pfs`` is the unmodified row of the applicable PFS source plus
``source_key`` and ``modifier_rows`` (the modifiers that have rows of their
own). ``CodeReference.mue`` is the MUE row plus ``source_key``. Every note
about one code begins with that code.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Iterable, Mapping, Optional

from studio.models import ReferenceCodeFact, ReferenceSource
from studio.types import CodeReference, ReferenceSourceInfo

PFS = 'cms-pfs'
MUE = 'cms-mue-practitioner'
LOOKUP_KINDS = (PFS, MUE)
KIND_LABELS = {PFS: 'CMS Physician Fee Schedule', MUE: 'CMS practitioner MUE'}
UNKNOWN_DATE_NOTE = 'Service date unknown; dated references cannot be applied.'

# (source key, code) -> {modifier: facts}
RowReader = Callable[[str, str], Mapping[str, dict]]


def source_applies(source: ReferenceSourceInfo, service_date: Optional[date]) -> bool:
    if service_date is None:
        return False
    return date.fromisoformat(source.effective_start) <= service_date <= date.fromisoformat(source.effective_end)


def applied_sources(sources: Iterable[ReferenceSourceInfo],
                    service_date: Optional[date]) -> dict[str, ReferenceSourceInfo]:
    """kind -> the single source of that kind covering the date; ambiguous kinds are left out."""
    covering: dict[str, list[ReferenceSourceInfo]] = {}
    for source in sources:
        if source_applies(source, service_date):
            covering.setdefault(source.kind, []).append(source)
    return {kind: found[0] for kind, found in covering.items() if len(found) == 1}


def modifier_only_prefix(code: str, release: str) -> str:
    return f'{code} is listed in {release} only with modifier'


def build_reference(code: str, service_date: Optional[date], sources: tuple[ReferenceSourceInfo, ...],
                    read_rows: RowReader) -> CodeReference:
    if service_date is None:
        return CodeReference(code=code, notes=(UNKNOWN_DATE_NOTE,))
    applied = applied_sources(sources, service_date)
    found: dict[str, dict] = {}
    keys, notes = [], []
    for kind in LOOKUP_KINDS:
        source = applied.get(kind)
        if source is None:
            notes.append(_unavailable_note(code, kind, sources, service_date))
            continue
        keys.append(source.key)
        rows = read_rows(source.key, code)
        if '' in rows:
            facts = dict(rows[''], source_key=source.key)
            if kind == PFS:
                facts['modifier_rows'] = sorted(modifier for modifier in rows if modifier)
            found[kind] = facts
        elif rows:
            modifiers = ', '.join(sorted(rows))
            notes.append(f'{modifier_only_prefix(code, source.release)}(s) {modifiers}; it has no unmodified row.')
        else:
            notes.append(f'{code} is not listed in {source.release}.')
    return CodeReference(code=code, pfs=found.get(PFS), mue=found.get(MUE), applicable_sources=tuple(keys),
                         notes=tuple(notes))


def _unavailable_note(code, kind, sources, service_date):
    label = KIND_LABELS[kind]
    covering = [s.key for s in sources if s.kind == kind and source_applies(s, service_date)]
    if covering:
        return (f'{code}: {len(covering)} installed {label} sources cover {service_date.isoformat()} '
                f'({", ".join(covering)}); none was applied because the applicable release is ambiguous.')
    return f'{code}: no installed {label} source covers {service_date.isoformat()}.'


def _ordered(sources: Iterable[ReferenceSourceInfo]) -> tuple[ReferenceSourceInfo, ...]:
    return tuple(sorted(sources, key=lambda s: (s.kind, s.effective_start, s.key)))


def source_info(row: ReferenceSource) -> ReferenceSourceInfo:
    return ReferenceSourceInfo(
        key=row.key, kind=row.kind, publisher=row.publisher, title=row.title, release=row.release, url=row.url,
        sha256=row.sha256, effective_start=row.effective_start.isoformat(), effective_end=row.effective_end.isoformat(),
        license_note=row.license_note, scope_note=row.scope_note)


class DbReferenceLookup:
    """ReferenceLookup over the installed rows. Sources are read once, so one assessment sees one snapshot."""

    def __init__(self):
        self._sources = _ordered(source_info(row) for row in ReferenceSource.objects.all())
        self._cache: dict[tuple[str, Optional[date]], CodeReference] = {}

    def sources(self) -> tuple[ReferenceSourceInfo, ...]:
        return self._sources

    def lookup(self, code: str, service_date: Optional[date]) -> CodeReference:
        key = (code, service_date)
        if key not in self._cache:
            self._cache[key] = build_reference(code, service_date, self._sources, self._read_rows)
        return self._cache[key]

    @staticmethod
    def _read_rows(source_key: str, code: str) -> dict[str, dict]:
        rows = ReferenceCodeFact.objects.filter(source__key=source_key, code=code).values_list('modifier', 'facts')
        return dict(rows)


class InMemoryReferenceLookup:
    """ReferenceLookup over in-memory rows: ``facts`` maps source key -> {(code, modifier): facts}."""

    def __init__(self, sources: Iterable[ReferenceSourceInfo], facts: Mapping[str, Mapping[tuple[str, str], dict]]):
        self._sources = _ordered(sources)
        unknown = set(facts) - {s.key for s in self._sources}
        if unknown:
            raise ValueError(f'Facts given for sources that are not listed: {sorted(unknown)}')
        self._facts = {key: {(code, modifier): dict(value) for (code, modifier), value in rows.items()}
                       for key, rows in facts.items()}

    def sources(self) -> tuple[ReferenceSourceInfo, ...]:
        return self._sources

    def lookup(self, code: str, service_date: Optional[date]) -> CodeReference:
        return build_reference(code, service_date, self._sources, self._read_rows)

    def _read_rows(self, source_key: str, code: str) -> dict[str, dict]:
        return {modifier: dict(value) for (row_code, modifier), value in self._facts.get(source_key, {}).items()
                if row_code == code}
