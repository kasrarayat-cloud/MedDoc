"""Accuracy evaluation against independently adjudicated, withheld reference cases.

The harness refuses any case that is not marked as independently adjudicated
AND withheld from development: author expectations, development fixtures and
model agreement are not accuracy evidence. Metrics are reported per internal
service family and never pooled into a single headline number.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .gi.profiles import FAMILY_ORDER, PROFILES, family_for_code

REQUIRED_ADJUDICATION = ('adjudicators', 'method', 'adjudicated_on')


class ManifestRefused(ValueError):
    pass


@dataclass(frozen=True)
class ReferenceCode:
    code: str
    modifiers: tuple[str, ...] = ()
    units: int = 1

    @property
    def family(self) -> str:
        return family_for_code(self.code)


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    document: str  # path relative to the manifest
    delivery: str  # pdf | docx | txt | paste
    references: tuple[ReferenceCode, ...]
    adjudication: dict = field(default_factory=dict)


def load_manifest(path) -> list[EvaluationCase]:
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('adjudicated') is not True or data.get('withheld_from_development') is not True:
        raise ManifestRefused('Only independently adjudicated cases withheld from development can measure accuracy.')
    cases = []
    for raw in data.get('cases', []):
        adjudication = raw.get('adjudication') or data.get('adjudication') or {}
        missing = [key for key in REQUIRED_ADJUDICATION if not adjudication.get(key)]
        if missing:
            raise ManifestRefused(f'Case {raw.get("case_id")} lacks adjudication fields: {", ".join(missing)}.')
        if raw.get('delivery') not in {'pdf', 'docx', 'txt', 'paste'}:
            raise ManifestRefused(f'Case {raw.get("case_id")} has no supported delivery format.')
        references = tuple(ReferenceCode(code=str(r['code']), modifiers=tuple(r.get('modifiers', ())),
                                         units=int(r.get('units', 1))) for r in raw.get('reference_codes', []))
        cases.append(EvaluationCase(case_id=str(raw['case_id']), document=str(raw['document']),
                                    delivery=raw['delivery'], references=references, adjudication=adjudication))
    if not cases:
        raise ManifestRefused('The manifest contains no cases.')
    return cases


def score_case(case: EvaluationCase, proposals: list[dict]) -> dict:
    """Compare one case's reference codes with the system's selected proposals, per family.

    ``proposals`` are API-shaped proposal dicts. Only bucket 'selected' counts as
    proposed; 'ready' vs 'needs_clarification' is reported as review burden. The
    system never assigns modifiers, so a reference modifier is always counted as
    not produced (never as agreement).
    """
    selected = [p for p in proposals if p.get('bucket') == 'selected']
    families = {ref.family for ref in case.references} | {p.get('family') for p in selected}
    result = {}
    for family in sorted(f for f in families if f):
        expected = [r for r in case.references if r.family == family]
        proposed = [p for p in selected if p.get('family') == family]
        expected_codes = {r.code: r for r in expected}
        proposed_codes = {p['code']: p for p in proposed}
        missed = sorted(set(expected_codes) - set(proposed_codes))
        extra = sorted(set(proposed_codes) - set(expected_codes))
        unit_mismatches = sorted(code for code in set(expected_codes) & set(proposed_codes)
                                 if int(proposed_codes[code].get('units') or 1) != expected_codes[code].units)
        modifiers_expected = sum(len(r.modifiers) for r in expected)
        result[family] = {
            'expected': sorted(expected_codes), 'proposed': sorted(proposed_codes),
            'missed': missed, 'extra': extra, 'unit_mismatches': unit_mismatches,
            'modifiers_expected': modifiers_expected, 'modifiers_produced': 0,
            'complete_correct': not missed and not extra and not unit_mismatches and modifiers_expected == 0,
            'needs_review': any(p.get('status') != 'ready' for p in proposed) or bool(missed),
        }
    return result


def aggregate(scored_cases: list[dict]) -> dict:
    """Per-family totals across cases. No pooled cross-family figure is produced."""
    totals = {}
    for case in scored_cases:
        for family, row in case['families'].items():
            entry = totals.setdefault(family, {
                'label': PROFILES[family].label if family in PROFILES else family,
                'cases': 0, 'complete_correct': 0, 'missed_codes': 0, 'extra_codes': 0, 'unit_mismatches': 0,
                'modifiers_expected': 0, 'modifiers_produced': 0, 'cases_needing_review': 0})
            entry['cases'] += 1
            entry['complete_correct'] += int(row['complete_correct'])
            entry['missed_codes'] += len(row['missed'])
            entry['extra_codes'] += len(row['extra'])
            entry['unit_mismatches'] += len(row['unit_mismatches'])
            entry['modifiers_expected'] += row['modifiers_expected']
            entry['modifiers_produced'] += row['modifiers_produced']
            entry['cases_needing_review'] += int(row['needs_review'])
    ordered = {}
    for family in list(FAMILY_ORDER) + sorted(set(totals) - set(FAMILY_ORDER)):
        if family in totals:
            entry = totals[family]
            entry['complete_case_rate'] = round(entry['complete_correct'] / entry['cases'], 4)
            entry['review_rate'] = round(entry['cases_needing_review'] / entry['cases'], 4)
            ordered[family] = entry
    return ordered
