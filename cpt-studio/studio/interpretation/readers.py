"""The one dispatch of read time (design/FINAL.md 8.2 and 10.3, as design/ADJUDICATION.md R-2 and R-6 amend them; P7):
every consumer that reads an assessment's stored rows reads them through the reader of the engine that made them.

- ``for_assessment(a)`` gives EventReader for an assessment the events engine made (interpretation.is_new_assessment:
  engine_version 'cpt-studio-events@...'), else LegacyReader.
- LegacyReader's methods are today's calls, moved verbatim: review_view.stored_from and review_view.review_view,
  engine.reviewed_completeness, the stored services record. EventReader's read the new path's own stored records:
  overlay.py's port of the review overlay over completeness['event_coding'], the frozen event inventory for a reviewed
  coverage, and the event coding's sessions for the documented services.
- Each refuses the other's rows (WrongReader, a ValueError): a mis-dispatch fails loudly, never quietly reads a record
  with the wrong rules.
- Each method sets the sentinel's row label for its duration (FINAL 10.3): LegacyReader's executions count as
  legacy_record - the archived reader serving the records it made, which D22 reports as residual legacy execution - and
  EventReader's as new_path, where any execution of the legacy reader is a finding (the write gates refuse on it).

SCOPES (FINAL 10.3; R-6). ``web_scope`` wraps every URL pattern (cptstudio/urls.py): a request whose URL names an
encounter - directly, or through a report it names - opens a base scope labelled by that encounter (``label_of``: its
current assessment's engine, else its current context's, else the new path this image runs), so a consumer that
bypasses the readers on a new-path encounter still runs under new_path and is counted; a request naming no encounter (the
session and the lists) runs under 'other', and the list loops label each encounter's row (``labelled``). Reads never
refuse: a request naming an encounter records what a write in its place would be refused for (sentinel.observe).

WRITE GATES (FINAL 10.3): a decision on a new-path assessment, a member answer on a new-path revision and a report made
from a new-path assessment each run in a new_path scope of their own (``write_scope``), asked again before their
transaction commits (``check``: GateClosed rolls the write back whole), then refused outside it by the sentinel's gate
(``refuse``: the AuditEvent 'sentinel.tripped' and sentinel.Tripped, which the API answers 409 with CPT Studio's own
sentence). A caller that held a transaction of its own records the trip again once it has left it (``record_trip``).
A report or member-answer write whose scope was opened from the row its request read is decided again from its LOCKED
row (``moved``), and refused (MOVED, a 409) when a reading finished in between moved the row to the other path.

Nothing here reads the revision text, and nothing here imports the legacy reader at load: LegacyReader imports it where
it calls it.
"""
from __future__ import annotations

import contextlib
import functools
import hashlib
import logging
from typing import Optional

from studio import interpretation
from studio.interpretation import overlay, sentinel

log = logging.getLogger(__name__)

LEGACY, EVENTS = 'legacy', 'events'
SELECTED, EXCLUDED = 'selected', 'excluded'


class WrongReader(ValueError):
    """A reader handed a row of the other engine (FINAL 8.2; P7): never read with the wrong rules."""


class GateClosed(Exception):
    """A new-path write the sentinel would refuse, raised inside the write's transaction so nothing of it is written
    (``scope``: the write's scope, which ``refuse`` asks the gate about once the transaction has rolled back)."""

    def __init__(self, scope_):
        super().__init__('the sentinel refuses this write')
        self.scope = scope_


# --- the readers (FINAL 8.2) ------------------------------------------------------------------------------------------

class _Reader:
    kind = ''
    label = ''

    def owns(self, assessment) -> bool:
        raise NotImplementedError

    def _own(self, assessment):
        if not self.owns(assessment):
            other = 'the events engine' if self.kind == LEGACY else 'the legacy engine'
            raise WrongReader(f'This assessment was made by {other}; the {self.kind} reader does not read it.')

    @contextlib.contextmanager
    def row(self, assessment):
        """This reader's label for the duration of reading ``assessment``'s rows, after refusing the other's."""
        self._own(assessment)
        with sentinel.relabel(self.label):
            yield


class LegacyReader(_Reader):
    """The legacy reader's records, read by the legacy code, unchanged (P7): today's calls, moved verbatim."""
    kind, label = LEGACY, sentinel.LEGACY_RECORD

    def owns(self, assessment) -> bool:
        return not interpretation.is_new_assessment(assessment)

    def overlay_inputs(self, assessment, proposals, clarifications, current, service_date):
        """(stored rows, decided, keyword arguments) review_view.review_view reads ``assessment`` with (review.py's
        _overlay_inputs, moved): ``clarifications``: {proposal pk: its Clarification rows}."""
        from studio.validation import review_view  # the legacy overlay, for the legacy rows only

        with self.row(assessment):
            stored = [review_view.stored_from(proposal, clarifications.get(proposal.pk, [])) for proposal in proposals]
            decided = {proposal.key: review_view.Decided(current[proposal.pk].action,
                                                         tuple(current[proposal.pk].modifiers or ()))
                       for proposal in proposals if proposal.pk in current}
            completeness = assessment.completeness or {}
            # an inconsistent documented-service reading decided nothing (engine: usable is None), and nothing re-reads it
            services = None if completeness.get('inventory_problems') else assessment.services
            return stored, decided, {'services': services, 'retrieval': assessment.retrieval,
                                     'reference_sources': assessment.reference_sources, 'service_date': service_date}

    def views(self, assessment, stored, decided, kwargs, answers=()):
        """review_view.review_view(stored, decided, **kwargs, answers=answers)."""
        from studio.validation import review_view

        with self.row(assessment):
            return review_view.review_view(stored, decided, **kwargs, answers=answers)

    def reviewed_completeness(self, assessment, completeness, proposals, reinstated, current=None):
        """engine.reviewed_completeness over the stored services record, as review.reviewed_completeness called it."""
        from studio.validation import engine

        with self.row(assessment):
            return engine.reviewed_completeness(
                assessment.services, completeness, [(p.code, p.family) for p in proposals if p.bucket == SELECTED],
                reinstated, [(p.support or {}).get('service') for p in proposals if (p.support or {}).get('service')])

    def services_list(self, assessment) -> list:
        """The documented services the customer API reads (customer_api.encounter_json, moved)."""
        with self.row(assessment):
            return [service for service in (assessment.services or {}).get('services') or []
                    if isinstance(service, dict)]

    def unreadable(self, assessment, reinstated=()) -> bool:
        """The legacy reader keeps its own fail-closed reading of an unreadable record (review_view._inventory)."""
        self._own(assessment)
        return False

    def interpretation_section(self, assessment) -> dict:
        """The operator's interpretation section: a legacy assessment is said to be one (report.interpretation_section)."""
        from studio.interpretation import report

        with self.row(assessment):
            return report.interpretation_section(assessment)


class EventReader(_Reader):
    """A new-path assessment's records, read from what the events engine stored (FINAL 7.11, 8.1): the overlay over
    completeness['event_coding'], the frozen event inventory, and nothing of the legacy reader."""
    kind, label = EVENTS, sentinel.NEW_PATH

    def owns(self, assessment) -> bool:
        return interpretation.is_new_assessment(assessment)

    def overlay_inputs(self, assessment, proposals, clarifications, current, service_date):
        """(stored rows, decided, keyword arguments) overlay.review_view reads ``assessment`` with."""
        with self.row(assessment):
            stored = [overlay.stored_from(proposal, clarifications.get(proposal.pk, [])) for proposal in proposals]
            decided = {proposal.key: overlay.Decided(current[proposal.pk].action,
                                                     tuple(current[proposal.pk].modifiers or ()))
                       for proposal in proposals if proposal.pk in current}
            return stored, decided, {'completeness': assessment.completeness, 'retrieval': assessment.retrieval,
                                     'reference_sources': assessment.reference_sources, 'service_date': service_date}

    def views(self, assessment, stored, decided, kwargs, answers=()):
        with self.row(assessment):
            return overlay.review_view(stored, decided, **kwargs, answers=answers)

    def reviewed_completeness(self, assessment, completeness, proposals, reinstated, current=None):
        """The coverage as the review leaves it (overlay.reviewed_completeness): coverage re-run over the FROZEN event
        inventory the assessment was made from, with the reinstated codes counted. The inventory is read through
        interpretation.store's versioned reader against its revision's text sha256 and its run's stored bytes (P6:
        the stored row, never the text). One this release cannot read leaves the recorded coverage as it is and says
        so: the coding is incomplete, its reasons end with overlay.UNREADABLE_COVERAGE_REASON and its statement is
        worded from them as the engine words one (coverage.completeness) - and readiness blocks (``unreadable``), so
        nothing is approved or exported on a coverage that does not count the reinstated codes (fail-closed)."""
        with self.row(assessment):
            if not self._recounted(completeness):
                return completeness
            reading = self.reading(assessment)
            if reading is None:
                reasons = [*(completeness.get('reasons') or ()), overlay.UNREADABLE_COVERAGE_REASON]
                return {**completeness, 'state': 'incomplete', 'reasons': reasons,
                        'statement': 'Coding for this encounter is incomplete: ' + '; '.join(reasons) + '.'}
            keys = {p.key for p in proposals if p.bucket == EXCLUDED and (p.code, p.family) in set(reinstated)}
            counted = overlay.counted_codes(proposals, keys, reading)
            return overlay.reviewed_completeness(completeness, reading, counted, reinstated)

    @staticmethod
    def _recounted(completeness) -> bool:
        """Whether a reviewed coverage is re-run for a reinstated code: the assessment recorded a coverage (its covered
        map) to re-run."""
        return bool(completeness) and isinstance(completeness.get('covered'), dict)

    def reading(self, assessment):
        """events.Reading of the assessment's EventInventory as interpretation.store reads and checks it, or None when
        there is none or it cannot be read (logged)."""
        from studio.interpretation import events, store
        from studio.models import EventInventory

        self._own(assessment)
        inventory = (EventInventory.objects.select_related('provider_run', 'revision')
                     .filter(pk=assessment.event_inventory_id).first() if assessment.event_inventory_id else None)
        if inventory is None:
            return None
        data = bytes(inventory.provider_run.response_bytes or b'')
        try:
            stored = store.load(store.fields_of(inventory), text_sha256=inventory.revision.text_sha256,
                                response_sha256=hashlib.sha256(data).hexdigest())
            return events.Reading.of(stored)
        except (store.StoreError, KeyError, TypeError, ValueError) as exc:
            log.error('the event inventory %s of assessment %s could not be read: %s', inventory.pk, assessment.pk, exc)
            return None

    def services_list(self, assessment) -> list:
        """The documented services the customer API reads, one per session of the event coding: its id, family and
        whether it was done ('performed', 'incomplete' or '' - an 'uncertain' service is the legacy reading's own
        status; a session in doubt is an unresolved item here). [] when the coding cannot be read."""
        with self.row(assessment):
            coding = overlay.coding_of(assessment.completeness)
            if coding is None:
                return []
            return [{'id': sid, 'family': session['family'],
                     'status': ('incomplete' if session.get('incomplete') else 'performed') if session['done'] else ''}
                    for sid, session in coding['sessions'].items()]

    def services_section(self, assessment, completeness, rejected=frozenset()):
        """The documented services the operator's report lists (reports._services' rows), one per session of the event
        coding: its family, whether it was done, the labels of its reportable acts, the codes that cover it (a rejected
        one printed as rejected), and the session it is read as part of with the codes there that include it. None when
        the coding cannot be read."""
        with self.row(assessment):
            coding = overlay.coding_of(assessment.completeness)
            if coding is None:
                return None
            included_by = completeness.get('included_by') if isinstance(completeness.get('included_by'), dict) else {}
            out = []
            for sid, session in coding['sessions'].items():
                codes = list((completeness.get('covered') or {}).get(sid, []))
                including = included_by.get(sid)
                including = [code for code in including if code not in rejected] if isinstance(including, list) else None
                out.append({'id': sid, 'family': session['family'],
                            'status': ('incomplete' if session.get('incomplete') else 'performed') if session['done']
                            else 'not established', 'completion': 'incomplete' if session.get('incomplete') else '',
                            'extent': '', 'intent': '',
                            'acts': sorted({entry['label'] for entry in session['reportable']}),
                            'covered_by': [code for code in codes if code not in rejected],
                            'rejected_by_reviewer': [code for code in codes if code in rejected],
                            'included_in': session['part_of'], 'included_by': including})
            return out

    def unreadable(self, assessment, reinstated=()) -> bool:
        """Whether a record the review of ``assessment`` reads cannot be read (FINAL 8.1: readiness then adds
        overlay.UNREADABLE_BLOCKER): its event coding, or - while a reviewer has reinstated a code (``reinstated``:
        review.reinstated_codes) - the frozen event inventory its reviewed coverage is re-run over (reviewed_completeness
        then shows the recorded coverage, without the reinstated codes, and says so)."""
        with self.row(assessment):
            if overlay.coding_of(assessment.completeness) is None:
                return True
            return (bool(reinstated) and self._recounted(assessment.completeness or {})
                    and self.reading(assessment) is None)

    def interpretation_section(self, assessment) -> dict:
        """The operator's interpretation section (report.interpretation_section): its D22 record, the event inventory,
        the Gemini run with its usage and estimated cost, and the hold that run set."""
        from studio.interpretation import report

        with self.row(assessment):
            return report.interpretation_section(assessment)


_LEGACY, _EVENTS = LegacyReader(), EventReader()


def for_assessment(assessment):
    """EventReader for an assessment the events engine made, LegacyReader for every other (FINAL 8.2)."""
    return _EVENTS if interpretation.is_new_assessment(assessment) else _LEGACY


# --- labels (FINAL 10.3; R-6) -----------------------------------------------------------------------------------------

def _label(engine_version, context_version) -> str:
    """The label of an encounter whose current assessment has ``engine_version`` and current context ``context_version``
    (None for none): the assessment's engine, else the context's, else new_path - the only path this image runs for a
    document it has not read yet."""
    if engine_version is not None:
        new = interpretation.is_new_assessment(_Versioned(engine_version=engine_version))
        return sentinel.NEW_PATH if new else sentinel.LEGACY_RECORD
    if context_version is not None:
        new = interpretation.is_new_context(_Versioned(version=context_version))
        return sentinel.NEW_PATH if new else sentinel.LEGACY_RECORD
    return sentinel.NEW_PATH


class _Versioned:
    def __init__(self, **values):
        self.__dict__.update(values)


def label_of(encounter) -> str:
    """The sentinel label of ``encounter``'s rows (FINAL 10.3): its current assessment's engine (new_path for the events
    engine, legacy_record for the legacy one), else its current context's (new_path for a context derived from an event
    inventory), else new_path."""
    assessment = encounter.current_assessment if encounter.current_assessment_id else None
    context = encounter.current_context if encounter.current_context_id else None
    return _label(assessment.engine_version if assessment is not None else None,
                  context.version if context is not None else None)


def labelled(fn, encounter, *args, **kwargs):
    """``fn(encounter, ...)`` under ``encounter``'s label (R-6: the list, session and operator-list loops label each
    encounter's row, so a consumer that bypasses the readers on a new-path row counts as new_path there too)."""
    with sentinel.relabel(label_of(encounter)):
        return fn(encounter, *args, **kwargs)


def _named(kwargs):
    """(label, encounter) of the encounter a request's URL names - its encounter_id, or the encounter of the report its
    report_id names - the encounter with its workspace; ('other', None) when it names none or no such row exists."""
    from django.core.exceptions import ValidationError

    from studio.models import Encounter, ReportArtifact

    fields = ('pk', 'current_assessment__engine_version', 'current_context__version')
    try:
        if kwargs.get('encounter_id') is not None:
            found = Encounter.objects.filter(pk=kwargs['encounter_id']).values_list(*fields).first()
        elif kwargs.get('report_id') is not None:
            found = (ReportArtifact.objects.filter(pk=kwargs['report_id'])
                     .values_list(*(f'encounter__{name}' for name in fields)).first())
        else:
            found = None
    except (ValueError, ValidationError):
        found = None
    if found is None or found[0] is None:
        return sentinel.OTHER, None
    encounter = Encounter.objects.select_related('workspace').filter(pk=found[0]).first()
    return (_label(found[1], found[2]), encounter) if encounter is not None else (sentinel.OTHER, None)


def web_scope(view):
    """A URL pattern's view in its sentinel scope (FINAL 10.3): labelled by the encounter its URL names (label_of), or
    'other' for a request naming none; once the view has answered, a request naming an encounter records what a write in
    its place would be refused for (sentinel.observe: reads never refuse, for availability)."""
    entry = f'web:{view.__module__}.{view.__name__}'

    @functools.wraps(view)
    def scoped(request, *args, **kwargs):
        label, encounter = _named(kwargs)
        with sentinel.scope(label, entry=entry):
            response = view(request, *args, **kwargs)
            if encounter is not None and getattr(response, 'status_code', 500) < 400:
                # only a request that was answered: one refused (another workspace's encounter answers 404, a write a
                # gate refused 409 with its own trip on record) records nothing more on the encounter
                user = getattr(request, 'user', None)
                sentinel.observe(entry, encounter=encounter,
                                 actor=user if getattr(user, 'is_authenticated', False) else None)
            return response
    return scoped


# --- the write gates (FINAL 10.3) -------------------------------------------------------------------------------------

@contextlib.contextmanager
def write_scope(entry: str, new_path: bool):
    """A write's own sentinel scope: new_path for a write on a new-path row (nested in the request's scope when one is
    open, whose counts the gate reads too), none for any other write, which keeps running as before."""
    if not new_path:
        yield None
        return
    with sentinel.scope(sentinel.NEW_PATH, entry=entry) as opened:
        yield opened


def check(scope_) -> None:
    """Asked inside the write's transaction, as the last thing before it commits: GateClosed when the gate would refuse
    (a new_path execution counted, an instrument that failed, or a process that cannot count), so the whole write rolls
    back. Nothing for a write with no scope (not a new-path write)."""
    if scope_ is not None and sentinel.refusal(scope_) is not None:
        raise GateClosed(scope_)


# The gate is decided again from the LOCKED row (the Gemini migration's review, finding 3). A write opens its scope from
# the encounter its request read, before the row lock; a reading that finished in between (a legacy encounter's first
# interpretation, FINAL 9) leaves the locked row on the other path, and the write would then be made from a new-path
# assessment with no gate - or from a row its scope does not describe. Asked first under the lock, before anything is
# computed or written, the write is refused instead (a 409 in these words), and the member's retry is decided from the
# row as it then stands.
MOVED = 'Nothing was saved: the reading of this document changed during this step. Reload the page and try again.'


class PathMoved(ValueError):
    """A gated write whose locked row reads on another path than the one its scope was opened for (``moved``)."""

    def __init__(self):
        super().__init__(MOVED)


def moved(scope_, new_path: bool) -> bool:
    """Whether the write's scope (``scope_``: write_scope's, None for a write opened as not new-path) is not the one its
    LOCKED row calls for (``new_path``: that row read on the new path)."""
    return (scope_ is not None) != bool(new_path)


def refuse(entry: str, closed: GateClosed, *, encounter, actor=None):
    """After the write's rollback: the sentinel's gate records the trip (AuditEvent 'sentinel.tripped') and raises
    sentinel.Tripped, CPT Studio's sentence naming no module, provider or model. The write's scope and the scopes around
    it are marked reported, so the request that made the write records no second trip for the same executions when it
    answers (sentinel.observe records once per scope)."""
    for item in closed.scope.chain():
        item.reported = True
    sentinel.gate(entry, encounter=encounter, actor=actor, scope_=closed.scope)
    raise sentinel.Tripped('unavailable', {'entry': entry})  # never reached: a closed gate refuses


def record_trip(encounter, actor, data: Optional[dict]):
    """Record a trip again once the caller has left a transaction of its own that rolled the gate's row back with its
    work (api.decisions, answers.save_details around a context save's refusal: jobs.Refused.trip)."""
    if not data:
        return
    from studio import audit

    audit.record(encounter.workspace, sentinel.TRIPPED, encounter=encounter, actor=actor, **data)
