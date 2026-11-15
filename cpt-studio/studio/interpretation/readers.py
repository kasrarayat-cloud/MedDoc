"""The one dispatch of read time (design/FINAL.md 8.2 and 10.3, as design/ADJUDICATION.md R-2 and R-6 amend them; P7):
every consumer that reads an assessment's stored rows reads them through the reader of the engine that made them.

- ``for_assessment(a)`` gives EventReader for an assessment the events engine made (interpretation.is_new_assessment:
  engine_version 'cpt-studio-events@...'), else LegacyReader.
- LegacyReader's methods are today's calls, moved verbatim: review_view.stored_from and review_view.review_view,
  engine.reviewed_completeness, the stored services record. EventReader's read the new path's own stored records:
  overlay.py's port of the review overlay over completeness['event_coding'], the frozen event inventory for a reviewed
  coverage, and the event coding's sessions for the documented services.
- DESIGN V2 (docs/gemini-migration/FINAL-V2.md 6.2, 6.5; step 5c of its 8.1): EventReader dispatches by the events
  version that made a row (``EventReader.branch``). A cpt-studio-events@2 row (READ_ENGINES) is read from event_coding@2
  and the FactSet of its frozen settled inventory - store.load_v2 at any version pair store.READ_VERSIONS lists, as
  stored [R:MO-5], then store.textfree_v2 and overlay.reading (engine/facts.effective with the date of service the
  assessment was made with); a cpt-studio-events@1 row (a test instance's, v1) goes to the V1 branch, labelled
  legacy_record, read AS STORED and UNREADABLE: revoke only, until it is assessed again; any other events version is
  UNREADABLE. ``label_of`` labels a v1 row legacy_record, so a v1 row is never read under new_path.
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
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from typing import Any, NoReturn, Optional, TypeVar, cast

from studio import interpretation
from studio.interpretation import overlay, sentinel, wording
from studio.interpretation.contract.types import SessionKind
from studio.interpretation.engine import assess as engine_assess
from studio.interpretation.engine.types import FactSet

log = logging.getLogger(__name__)

LEGACY, EVENTS = 'legacy', 'events'
SELECTED, EXCLUDED, ALTERNATIVE = 'selected', 'excluded', 'alternative'
# EventReader's branches (FINAL-V2 6.2): the events versions this release reads, the v1 rows it reads as stored, and any
# other events version (a later release's), which it does not read.
V2, V1, UNKNOWN = 'v2', 'v1', 'unknown'
# The engine versions whose rows EventReader reads (FINAL-V2 6.2 [R:MO-5], as the adapter and store keep READ_VERSIONS):
# a later engine version is added here beside the earlier one, never in its place.
READ_ENGINES = (interpretation.ENGINE_VERSION_V2,)
# The context version a v2 assessment is made through (engine/derive.py; FINAL-V2 1.1).
READ_CONTEXTS = (interpretation.CONTEXT_VERSION_V2,)
_MISSING = object()
_T = TypeVar('_T')


class WrongReader(ValueError):
    """A reader handed a row of the other engine (FINAL 8.2; P7): never read with the wrong rules."""


class GateClosed(Exception):
    """A new-path write the sentinel would refuse, raised inside the write's transaction so nothing of it is written
    (``scope``: the write's scope, which ``refuse`` asks the gate about once the transaction has rolled back)."""

    def __init__(self, scope_: Any) -> None:
        super().__init__('the sentinel refuses this write')
        self.scope = scope_


# --- the readers (FINAL 8.2) ------------------------------------------------------------------------------------------

class _Reader:
    kind = ''
    label = ''

    def owns(self, assessment: Any) -> bool:
        raise NotImplementedError

    def _own(self, assessment: Any) -> None:
        if not self.owns(assessment):
            other = 'the events engine' if self.kind == LEGACY else 'the legacy engine'
            raise WrongReader(f'This assessment was made by {other}; the {self.kind} reader does not read it.')

    @contextlib.contextmanager
    def row(self, assessment: Any) -> Iterator[None]:
        """This reader's label for the duration of reading ``assessment``'s rows, after refusing the other's."""
        self._own(assessment)
        with sentinel.relabel(self.label):
            yield


class LegacyReader(_Reader):
    """The legacy reader's records, read by the legacy code, unchanged (P7): today's calls, moved verbatim."""
    kind, label = LEGACY, sentinel.LEGACY_RECORD

    def owns(self, assessment: Any) -> bool:
        return not interpretation.is_new_assessment(assessment)

    def overlay_inputs(self, assessment: Any, proposals: Sequence[Any], clarifications: Mapping[Any, Any],
                       current: Mapping[Any, Any],
                       service_date: Any) -> tuple[list[Any], dict[str, Any], dict[str, Any]]:
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

    def views(self, assessment: Any, stored: Sequence[Any], decided: Mapping[str, Any], kwargs: Mapping[str, Any],
              answers: Any = ()) -> dict[str, Any]:
        """review_view.review_view(stored, decided, **kwargs, answers=answers)."""
        from studio.validation import review_view

        with self.row(assessment):
            return review_view.review_view(stored, decided, **kwargs, answers=answers)

    def reviewed_completeness(self, assessment: Any, completeness: Any, proposals: Sequence[Any],
                              reinstated: Any, current: Any = None) -> Any:
        """engine.reviewed_completeness over the stored services record, as review.reviewed_completeness called it."""
        from studio.validation import engine

        with self.row(assessment):
            return engine.reviewed_completeness(
                assessment.services, completeness, [(p.code, p.family) for p in proposals if p.bucket == SELECTED],
                reinstated, cast(list[str], [(p.support or {}).get('service') for p in proposals
                                             if (p.support or {}).get('service')]))

    def services_list(self, assessment: Any) -> list[Any]:
        """The documented services the customer API reads (customer_api.encounter_json, moved)."""
        with self.row(assessment):
            return [service for service in (assessment.services or {}).get('services') or []
                    if isinstance(service, dict)]

    def unreadable(self, assessment: Any, reinstated: Iterable[Any] = ()) -> bool:
        """The legacy reader keeps its own fail-closed reading of an unreadable record (review_view._inventory)."""
        self._own(assessment)
        return False

    def interpretation_section(self, assessment: Any) -> dict[str, Any]:
        """The operator's interpretation section: a legacy assessment is said to be one (report.interpretation_section)."""
        from studio.interpretation import report

        with self.row(assessment):
            return report.interpretation_section(assessment)


class EventReader(_Reader):
    """An events-engine assessment's records (FINAL-V2 6.2 and 6.5; step 5c), dispatched by the engine version that made
    them (``branch``):

    - V2 (``READ_ENGINES``: cpt-studio-events@2): read from what the engine stored and the frozen settled inventory -
      the overlay over completeness['event_coding'] (event_coding@2) and the FactSet of the EventInventory row, read
      through store.load_v2 (every shipped v2 inventory version, store.READ_VERSIONS, as stored [R:MO-5]: a newer
      version never makes an older v2 assessment unreadable) against its revision's text sha256 and both runs' stored
      response bytes, then store.textfree_v2 and overlay.reading (engine/facts.effective with the date of service the
      assessment was made with). Label new_path.
    - V1 (cpt-studio-events@1, a test instance's row; FINAL-V2 6.2): read AS STORED under the label legacy_record -
      the stored rows as they are, nothing re-read or recomputed (the overlay reads event_coding@2 only, so its every
      check and question stands) - and UNREADABLE: readiness adds overlay.UNREADABLE_BLOCKER, so only a revoke is
      allowed and approve, export and a reinstatement's reviewed completeness are refused until it is assessed again.
      A v1 EventInventory row is never read by v2 (store.load_v2 refuses its versions; store._v1_reader is v1's own).
    - any other events version (a later release's row): UNREADABLE, nothing read.

    Nothing of the legacy reader runs here, and nothing here reads document text."""
    kind, label = EVENTS, sentinel.NEW_PATH

    def owns(self, assessment: Any) -> bool:
        return interpretation.is_new_assessment(assessment)

    @staticmethod
    def branch(assessment: Any) -> str:
        """V2, V1 or UNKNOWN: the events version ``assessment`` was made at."""
        version = getattr(assessment, 'engine_version', None)
        if version in READ_ENGINES:
            return V2
        if version == interpretation.ENGINE_VERSION:
            return V1
        return UNKNOWN

    @contextlib.contextmanager
    def row(self, assessment: Any) -> Iterator[None]:
        """This reader's label for the duration of reading ``assessment``'s rows, after refusing the other's: new_path
        for a v2 row, legacy_record for a v1 row (FINAL-V2 6.2: a v1 row is never read under new_path)."""
        self._own(assessment)
        with sentinel.relabel(sentinel.LEGACY_RECORD if self.branch(assessment) == V1 else self.label):
            yield

    # --- the inputs read time reads ---------------------------------------------------------------------------------

    def reading(self, assessment: Any) -> Optional[FactSet]:
        """The FactSet of ``assessment``'s frozen settled inventory (overlay.reading), or None when it has none or it
        cannot be read (logged): a v2 row only (a v1 row's inventory is never read by v2). Cached on the assessment
        object, which is immutable. (The name v1's reader gave its loader, which tests/guard_support.py counts.)"""
        self._own(assessment)
        if self.branch(assessment) != V2:
            return None
        cached = getattr(assessment, '_v2_read_facts', _MISSING)
        if cached is not _MISSING:
            return cast(Optional[FactSet], cached)
        found = self._load_facts(assessment)
        try:
            assessment._v2_read_facts = found
        except AttributeError:  # an object that takes no attribute (a test's namespace): read again next time
            pass
        return found

    def _load_facts(self, assessment: Any) -> Optional[FactSet]:
        from studio.interpretation import store
        from studio.jobs import context_service_date  # local import: jobs imports this module's callers
        from studio.models import EventInventory

        service_date: Callable[[Any], Any] = context_service_date  # jobs.py is untyped: called through a typed name

        inventory = (EventInventory.objects.select_related('provider_run', 'appraisal_run', 'revision')
                     .filter(pk=assessment.event_inventory_id).first() if assessment.event_inventory_id else None)
        if inventory is None or inventory.appraisal_run_id is None:
            return None
        try:
            if (inventory.interpretation_version, inventory.inventory_version) not in store.READ_VERSIONS:
                raise store.UnknownVersion('The inventory was stored at a version this release does not read.')
            first = bytes(inventory.provider_run.response_bytes or b'')
            second = bytes(inventory.appraisal_run.response_bytes or b'')
            stored = store.load_v2(store.fields_of_v2(inventory), text_sha256=inventory.revision.text_sha256,
                                   response_sha256=hashlib.sha256(first).hexdigest(),
                                   appraisal_response_sha256=hashlib.sha256(second).hexdigest())
            context = assessment.context if assessment.context_id else None
            return overlay.reading(store.textfree_v2(stored), service_date(context) if context is not None else None)
        except (store.StoreError, KeyError, TypeError, ValueError) as exc:
            log.error('the event inventory %s of assessment %s could not be read: %s', inventory.pk, assessment.pk, exc)
            return None

    @staticmethod
    def member(assessment: Any) -> engine_assess.MemberContext:
        """The member context ``assessment`` was made with (overlay.member_context over its context's facts)."""
        context = assessment.context if getattr(assessment, 'context_id', None) else None
        return overlay.member_context(context.facts if context is not None else None)

    # --- the views ---------------------------------------------------------------------------------------------------

    def overlay_inputs(self, assessment: Any, proposals: Sequence[Any], clarifications: Mapping[Any, Any],
                       current: Mapping[Any, Any],
                       service_date: Any) -> tuple[list[overlay.Stored], dict[str, overlay.Decided], dict[str, Any]]:
        """(stored rows, decided, keyword arguments) overlay.review_view reads ``assessment`` with: for a v2 row the
        FactSet and the member context too; for a v1 row none (read as stored)."""
        with self.row(assessment):
            stored = [overlay.stored_from(proposal, clarifications.get(proposal.pk, [])) for proposal in proposals]
            decided = {proposal.key: overlay.Decided(current[proposal.pk].action,
                                                     tuple(current[proposal.pk].modifiers or ()))
                       for proposal in proposals if proposal.pk in current}
            kwargs: dict[str, Any] = {'completeness': assessment.completeness, 'retrieval': assessment.retrieval,
                                      'reference_sources': assessment.reference_sources, 'service_date': service_date}
            if self.branch(assessment) == V2:
                kwargs.update(facts=self.reading(assessment), member=self.member(assessment))
            return stored, decided, kwargs

    def views(self, assessment: Any, stored: Sequence[overlay.Stored], decided: Mapping[str, Any],
              kwargs: Mapping[str, Any], answers: Any = ()) -> dict[str, overlay.View]:
        with self.row(assessment):
            return overlay.review_view(stored, decided, **kwargs, answers=answers)

    def reviewed_completeness(self, assessment: Any, completeness: Any, proposals: Sequence[Any],
                              reinstated: Iterable[tuple[str, str]], current: Any = None) -> Any:
        """The coverage as the review leaves it (overlay.reviewed_coverage): the engine's coverage re-run over the
        FROZEN inventory the assessment was made from (FINAL-V2 6.5), with the reinstated codes counted and the
        assessment's own counts kept (overlay.assessment_counts: recorded, or derived from what step 5a's completeness
        records). A v1 row, a record this release cannot read (the coding, the inventory, a proposal's record, or a
        record the engine's own counted set does not reproduce - its held facts, or its completeness under any counts)
        leaves the recorded coverage as it is and says so: the coding is incomplete, its reasons end with
        overlay.UNREADABLE_COVERAGE_REASON and its statement is worded from them - and readiness blocks
        (``unreadable``), so nothing is approved or exported on a coverage that does not count the reinstated codes
        (fail-closed)."""
        with self.row(assessment):
            if not self._recounted(completeness):
                return completeness
            found = self._recounted_coverage(assessment, completeness, proposals, reinstated)
            if found is None:
                reasons = [*(completeness.get('reasons') or ()), overlay.UNREADABLE_COVERAGE_REASON]
                return {**completeness, 'state': 'incomplete', 'reasons': reasons,
                        'statement': 'Coding for this encounter is incomplete: ' + '; '.join(reasons) + '.'}
            return found

    def _recounted_coverage(self, assessment: Any, completeness: Any, proposals: Sequence[Any],
                            reinstated: Iterable[tuple[str, str]]) -> Optional[dict[str, Any]]:
        """overlay.reviewed_completeness over ``assessment``'s v2 records, or None when it cannot be run."""
        if self.branch(assessment) != V2:
            return None
        R = self.reading(assessment)
        coding = overlay.coding_of(assessment.completeness)
        if R is None or coding is None:
            return None
        rows = [overlay.stored_from(proposal, ()) for proposal in proposals]
        reinstated = list(reinstated)
        wanted = set(reinstated)
        keys = {p.key for p in rows if p.bucket == EXCLUDED and (p.code, p.family) in wanted}
        engine = [p.key for p in rows if p.bucket == SELECTED or overlay.answered_by_engine(p)[0]]
        try:
            counted = overlay.counted_codes(rows, keys, R)
            # DECISIONS D270 DQ-2: the engine's own competition reads without the codes assess took out of it by an
            # overlay-bound "Not documented" (overlay.assessed_out, from the stored record), so it reproduces the record
            found = overlay.recount(rows, [item.key for item in counted], engine, coding, R,
                                    retrieval=assessment.retrieval, member=self.member(assessment),
                                    assessed=overlay.assessed_out(assessment.completeness, rows))
            # the assessment's own counts: recorded, or derived from what step 5a's completeness records (overlay)
            own = overlay.assessment_counts(completeness, R, rows, retrieval=assessment.retrieval)
            return overlay.reviewed_coverage(completeness, R, counted, reinstated, own,
                                             members=tuple(found.members.values()))
        except (ValueError, LookupError, TypeError) as exc:  # UnreadableRecord, RecordMismatch, UnreadableCounts
            log.error('the reviewed coverage of assessment %s could not be re-run: %s', assessment.pk, exc)
            return None

    @staticmethod
    def _recounted(completeness: Any) -> bool:
        """Whether a reviewed coverage is re-run for a reinstated code: the assessment recorded a coverage (its covered
        map) to re-run."""
        return bool(completeness) and isinstance(completeness.get('covered'), dict)

    def unreadable(self, assessment: Any, reinstated: Iterable[tuple[str, str]] = ()) -> bool:
        """Whether a record the review of ``assessment`` reads cannot be read (FINAL 8.1; FINAL-V2 6.2: readiness then
        adds overlay.UNREADABLE_BLOCKER): every v1 row and every row of an events version this release does not read;
        for a v2 row, its event coding, or - while a reviewer has reinstated a code (``reinstated``:
        review.reinstated_codes) - anything its reviewed coverage and its read-time holds are re-run from (the
        frozen inventory, the proposals' records, a record the engine's own counted set does not reproduce: its held
        facts, or its completeness under any counts - overlay.assessment_counts): a reinstatement can add a hold, so it
        is never approved on what could not be re-read. With nothing reinstated a v2 row whose coding reads is not
        blocked, its inventory read or not: a rejection only releases or swaps combination holds, so the views it
        cannot recompute keep their stored holds, marked stale - and the one hold a rejection can add, the ADDON row of
        an add-on whose last primary it rejects (DECISIONS D268), the overlay adds from the codes alone, holding the
        add-on (overlay's UNREADABLE paragraph)."""
        with self.row(assessment):
            if self.branch(assessment) != V2 or overlay.coding_of(assessment.completeness) is None:
                return True
            reinstated = list(reinstated)
            if not reinstated:
                return False
            # asked once per proposal by the review's actions: the verdict is kept on the (immutable) assessment object
            # for the reinstated codes it was asked with
            key = tuple(sorted((str(code), str(family)) for code, family in reinstated))
            cache = getattr(assessment, '_v2_unreadable', None)
            if isinstance(cache, dict) and key in cache:
                return bool(cache[key])
            completeness = assessment.completeness or {}
            proposals = list(assessment.proposals.exclude(bucket=ALTERNATIVE))
            found = self._recounted_coverage(assessment, completeness, proposals, reinstated) is None
            try:
                assessment._v2_unreadable = {**(cache if isinstance(cache, dict) else {}), key: found}
            except AttributeError:  # an object that takes no attribute: asked again next time
                pass
            return found

    # --- the documented services --------------------------------------------------------------------------------------

    def services_list(self, assessment: Any) -> list[dict[str, Any]]:
        """The documented services the customer API reads, one per session of the event coding: its id, family slug and
        whether it was done ('performed', 'incomplete' or ''). A v1 row's stored sessions, as stored (``_v1_coding``).
        [] when the coding cannot be read."""
        with self.row(assessment):
            sessions = self._sessions(assessment)
            if sessions is None:
                return []
            return [{'id': sid, 'family': session['family'],
                     'status': ('incomplete' if session['incomplete'] else 'performed') if session['done'] else ''}
                    for sid, session in sessions.items()]

    def services_section(self, assessment: Any, completeness: Mapping[str, Any],
                         rejected: Collection[str] = frozenset()) -> Optional[list[dict[str, Any]]]:
        """The documented services the operator's report lists (reports._services' rows), one per session of the event
        coding: its family, whether it was done, the labels of its reportable acts, the codes that cover it (a rejected
        one printed as rejected), and the session it is read as part of with the codes there that include it. None
        when the coding cannot be read."""
        with self.row(assessment):
            sessions = self._sessions(assessment)
            if sessions is None:
                return None
            recorded = completeness.get('included_by')
            included_by = recorded if isinstance(recorded, dict) else {}
            out = []
            for sid, session in sessions.items():
                codes = list((completeness.get('covered') or {}).get(sid, []))
                including = included_by.get(sid)
                including = [code for code in including if code not in rejected] if isinstance(including, list) else None
                out.append({'id': sid, 'family': session['family'],
                            'status': ('incomplete' if session['incomplete'] else 'performed') if session['done']
                            else 'not established', 'completion': 'incomplete' if session['incomplete'] else '',
                            'extent': '', 'intent': '', 'acts': session['acts'],
                            'covered_by': [code for code in codes if code not in rejected],
                            'rejected_by_reviewer': [code for code in codes if code in rejected],
                            'included_in': session['part_of'], 'included_by': including})
            return out

    def _sessions(self, assessment: Any) -> Optional[dict[str, dict[str, Any]]]:
        """{session id: {family, done, incomplete, part_of, acts}} of ``assessment``'s event coding: event_coding@2's
        sessions, each family as its gi.profiles slug and its reportable acts by their kinds' labels; a v1 row's
        event_coding@1 sessions as stored (``_v1_coding``); None when the coding cannot be read."""
        if self.branch(assessment) == V1:
            return _v1_coding(assessment.completeness)
        coding = overlay.coding_of(assessment.completeness) if self.branch(assessment) == V2 else None
        if coding is None:
            return None
        out = {}
        for sid, session in coding['sessions'].items():
            kind = session.get('kind')
            out[sid] = {'family': _slug(kind), 'done': session['done'], 'incomplete': session['incomplete'],
                        'part_of': session.get('part_of') or '',
                        'acts': sorted({wording.event_kind_label(entry['kind']) for entry in session['reportable']
                                        if entry['kind']})}
        return out

    def interpretation_section(self, assessment: Any) -> dict[str, Any]:
        """The operator's interpretation section (report.interpretation_section): its D22 record, the event inventory,
        the Gemini runs (pass 1 and, for a v2 row, the appraisal) with their usage and estimated cost, and the hold
        each set."""
        from studio.interpretation import report

        with self.row(assessment):
            return report.interpretation_section(assessment)


def _slug(kind: object) -> str:
    """A session kind's gi.profiles slug (engine/assess.family_slug); '' for a kind not established."""
    if not isinstance(kind, str):
        return ''
    try:
        return engine_assess.family_slug(SessionKind(kind))
    except ValueError:
        return ''


def _v1_coding(completeness: object) -> Optional[dict[str, dict[str, Any]]]:
    """A v1 row's event_coding@1 sessions AS STORED (FINAL-V2 6.2: the V1 branch reads what v1 stored and re-reads
    nothing), for the services lists only: {session id: {family, done, incomplete, part_of, acts}} from its stored
    family slug, flags, part_of and the stored labels of its reportable acts; None for any record not in that shape."""
    coding = completeness.get('event_coding') if isinstance(completeness, Mapping) else None
    if not isinstance(coding, Mapping) or coding.get('version') != interpretation.ENGINE_VERSION:
        return None
    sessions = coding.get('sessions')
    if not isinstance(sessions, Mapping):
        return None
    out = {}
    for sid, session in sessions.items():
        entries = session.get('reportable') if isinstance(session, Mapping) else None
        if not (isinstance(sid, str) and isinstance(session.get('family'), str)
                and isinstance(session.get('done'), bool) and isinstance(entries, list)
                and all(isinstance(entry, Mapping) and isinstance(entry.get('label'), str) for entry in entries)):
            return None
        out[sid] = {'family': session['family'], 'done': session['done'],
                    'incomplete': bool(session.get('incomplete')), 'part_of': str(session.get('part_of') or ''),
                    'acts': sorted({entry['label'] for entry in entries})}
    return out


_LEGACY, _EVENTS = LegacyReader(), EventReader()


def for_assessment(assessment: Any) -> LegacyReader | EventReader:
    """EventReader for an assessment the events engine made, LegacyReader for every other (FINAL 8.2)."""
    return _EVENTS if interpretation.is_new_assessment(assessment) else _LEGACY


# --- labels (FINAL 10.3; R-6) -----------------------------------------------------------------------------------------

def _label(engine_version: Optional[str], context_version: Optional[str]) -> str:
    """The label of an encounter whose current assessment has ``engine_version`` and current context ``context_version``
    (None for none): the assessment's engine - new_path for a version EventReader reads (READ_ENGINES), legacy_record
    for the legacy engine's and for a v1 row (FINAL-V2 6.2: a v1 row is never read under new_path) - else the
    context's (new_path for a v2 context, READ_CONTEXTS; legacy_record for a legacy or a v1 one), else new_path - the
    only path this image runs for a document it has not read yet. A later events version than this release reads is
    labelled new_path: nothing of the legacy reader may read it."""
    if engine_version is not None:
        new = interpretation.is_new_assessment(_Versioned(engine_version=engine_version))
        return sentinel.NEW_PATH if new and engine_version != interpretation.ENGINE_VERSION else sentinel.LEGACY_RECORD
    if context_version is not None:
        new = interpretation.is_new_context(_Versioned(version=context_version))
        return sentinel.NEW_PATH if new and context_version != interpretation.CONTEXT_VERSION else \
            sentinel.LEGACY_RECORD
    return sentinel.NEW_PATH


class _Versioned:
    def __init__(self, **values: Any) -> None:
        self.__dict__.update(values)


def label_of(encounter: Any) -> str:
    """The sentinel label of ``encounter``'s rows (FINAL 10.3): its current assessment's engine (new_path for the events
    engine, legacy_record for the legacy one), else its current context's (new_path for a context derived from an event
    inventory), else new_path."""
    assessment = encounter.current_assessment if encounter.current_assessment_id else None
    context = encounter.current_context if encounter.current_context_id else None
    return _label(assessment.engine_version if assessment is not None else None,
                  context.version if context is not None else None)


def labelled(fn: Callable[..., _T], encounter: Any, *args: Any, **kwargs: Any) -> _T:
    """``fn(encounter, ...)`` under ``encounter``'s label (R-6: the list, session and operator-list loops label each
    encounter's row, so a consumer that bypasses the readers on a new-path row counts as new_path there too)."""
    with sentinel.relabel(label_of(encounter)):
        return fn(encounter, *args, **kwargs)


def _named(kwargs: Mapping[str, Any]) -> tuple[str, Any]:
    """(label, encounter) of the encounter a request's URL names - its encounter_id, or the encounter of the report its
    report_id names - the encounter with its workspace; ('other', None) when it names none or no such row exists."""
    from django.core.exceptions import ValidationError  # type: ignore[import-untyped]  # Django ships no type stubs

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


def web_scope(view: Callable[..., Any]) -> Callable[..., Any]:
    """A URL pattern's view in its sentinel scope (FINAL 10.3): labelled by the encounter its URL names (label_of), or
    'other' for a request naming none; once the view has answered, a request naming an encounter records what a write in
    its place would be refused for (sentinel.observe: reads never refuse, for availability)."""
    entry = f'web:{view.__module__}.{view.__name__}'

    @functools.wraps(view)
    def scoped(request: Any, *args: Any, **kwargs: Any) -> Any:
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
def write_scope(entry: str, new_path: bool) -> Iterator[Any]:
    """A write's own sentinel scope: new_path for a write on a new-path row (nested in the request's scope when one is
    open, whose counts the gate reads too), none for any other write, which keeps running as before."""
    if not new_path:
        yield None
        return
    with sentinel.scope(sentinel.NEW_PATH, entry=entry) as opened:
        yield opened


def check(scope_: Any) -> None:
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

    def __init__(self) -> None:
        super().__init__(MOVED)


def moved(scope_: Any, new_path: bool) -> bool:
    """Whether the write's scope (``scope_``: write_scope's, None for a write opened as not new-path) is not the one its
    LOCKED row calls for (``new_path``: that row read on the new path)."""
    return (scope_ is not None) != bool(new_path)


def refuse(entry: str, closed: GateClosed, *, encounter: Any, actor: Any = None) -> NoReturn:
    """After the write's rollback: the sentinel's gate records the trip (AuditEvent 'sentinel.tripped') and raises
    sentinel.Tripped, CPT Studio's sentence naming no module, provider or model. The write's scope and the scopes around
    it are marked reported, so the request that made the write records no second trip for the same executions when it
    answers (sentinel.observe records once per scope)."""
    for item in closed.scope.chain():
        item.reported = True
    sentinel.gate(entry, encounter=encounter, actor=actor, scope_=closed.scope)
    raise sentinel.Tripped('unavailable', {'entry': entry})  # never reached: a closed gate refuses


def record_trip(encounter: Any, actor: Any, data: Optional[dict[str, Any]]) -> None:
    """Record a trip again once the caller has left a transaction of its own that rolled the gate's row back with its
    work (api.decisions, answers.save_details around a context save's refusal: jobs.Refused.trip)."""
    if not data:
        return
    from studio import audit

    record: Callable[..., Any] = audit.record  # audit.py is untyped: called through a typed name
    record(encounter.workspace, sentinel.TRIPPED, encounter=encounter, actor=actor, **data)
