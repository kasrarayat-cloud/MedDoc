"""Rationale sentences built only from data the assessment holds.

No clinical reasoning is invented: the sentences restate who proposed the
code, how much exact evidence links it, where routing placed it, the status
the documentation supports and the documented facts with their values.
"""
from __future__ import annotations

from typing import Optional, Sequence

from studio.gi.profiles import ServiceProfile
from studio.validation.checks import StatusOutcome, excerpt, plural, fact_label

STATE_PHRASES = {
    'performed': 'performed',
    'incomplete': 'incomplete (performed in part)',
    'uncertain': 'not established as performed',
}


def _family_sentence(profile: ServiceProfile, detected: bool) -> str:
    if not profile.supported:
        return f'Routed to {profile.label}, which has no GI profile in this release.'
    found = 'routing also detected' if detected else 'routing did not detect'
    return f'Routed to {profile.label}; {found} this service in the document.'


def _state_phrase(outcome: StatusOutcome) -> str:
    if outcome.state == 'not_performed':
        return outcome.decisive.status
    return STATE_PHRASES[outcome.state]


def selected_rationale(*, provider: str, units: int, evidence_count: int, profile: ServiceProfile, detected: bool,
                       outcome: Optional[StatusOutcome], facts: Sequence[tuple[str, str]]) -> str:
    times = f' {units} times' if units > 1 else ''
    parts = [f'Selected by {provider}{times}.', f'{plural(evidence_count, "exact evidence passage")}.']
    if outcome is not None:
        parts.append(_family_sentence(profile, detected))
        parts.append(f'Service status: {_state_phrase(outcome)}.')
    if facts:
        listed = '; '.join(f'{fact_label(name)} = {excerpt(str(value))}' for name, value in facts)
        parts.append(f'Documented facts: {listed}.')
    return ' '.join(parts)


def _listing(role: str, parent_code: Optional[str], unlisted_parent: bool = False) -> str:
    if role == 'alternative':
        if parent_code:
            return f'alternative to {parent_code}'
        return 'alternative to a provider code that is not listed' if unlisted_parent else 'alternative'
    if role == 'candidate':
        return 'candidate'
    return f'code listed with role “{role}”'


def alternative_rationale(*, provider: str, role: str, parent_code: Optional[str], evidence_count: int,
                          unlisted_parent: bool = False, not_added: str = '') -> str:
    """``not_added``: why a code the bounded second review SELECTED is not added as a proposal - it is said to be
    selected, never listed as a code the provider did not select (refutation r1, report lens)."""
    if role == 'selected' and not_added:
        text = f'Selected by {provider}; not added as a proposal: {not_added}. Informational only.'
    else:
        text = (f'Listed by {provider} as {_listing(role, parent_code, unlisted_parent)}; the provider did not select '
                'it. Informational only.')
    if evidence_count:
        text += f' {plural(evidence_count, "exact evidence passage")}.'
    return text


def alternative_note(role: str, parent_code: Optional[str], *, unlisted_parent: bool = False,
                     not_added: str = '') -> str:
    if role == 'selected' and not_added:
        return (f'Selected by the provider in the bounded second review, but not added as a proposal: {not_added}. '
                'Candidates and alternatives cannot be approved.')
    return (f'Provider {_listing(role, parent_code, unlisted_parent)}; not selected. Candidates and alternatives '
            'cannot be approved.')
