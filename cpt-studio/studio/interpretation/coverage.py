"""Coverage and completeness over the event inventory (design/FINAL.md 7.7 and 7.8, as design/ADJUDICATION.md C-2, C-4 and
C-5 amend them): bundling, sessions, reportable events, what the counted codes cover, the unresolved items with their
second-review marks, and coding completeness - a port of reconcile.py:662-1023 onto structured fields. Pure set logic
over stored attributes: no text is read for meaning and no pattern is matched.

BUNDLING (7.7; COMMON_BUNDLED, catalogue.py:163-175):
- lift_injection: an injection or tattoo whose verified part_of names a current performed EMR or ESD, or whose verified
  purpose is lift_for_resection and whose verified lesion is that resection's; and (C-5) an injection - never a tattoo,
  never one whose hemostasis purpose is verified (that is bleeding control) - beside a current performed EMR or ESD of its
  session at compatible places, neither naming an unresolved lesion and the two not verified on two lesions. Where its
  lesion or place is unresolved the relations step recorded a bundling_identity: asked, never READY (bundling_doubt).
- resection_technique: a snare or hot biopsy part_of an EMR or ESD, or on the same verified lesion as one.
- biopsy_of_removed_lesion: a biopsy of the same verified lesion as a current performed removal (snare, EMR, hot biopsy,
  ESD) where that lesion is single, or - whatever the multiplicity (C-2) - where the two acts cite a passage in common;
  a group lesion whose two acts sit in separate passages has a bundling_identity relation instead.
- clip and cannulation: never separately reported (NOT_REPORTED); a clip whose hemostasis purpose is verified is
  bleeding control (its catalogue kind). Each family entry's own bundled kinds as the catalogue states them (the ERCP's
  contrast injection).

SESSIONS (7.8): a family's session is its current examination event (an endoscopic family's: an examination whose device
is not verified as another than the endoscope - FINAL 5.6, E13); two current examinations of one family leave it
unresolved for every rule that reads it. A session's examination ``part_of`` an examination of another family is that
session's included portion (C3), and - structurally (C-4) - a current performed EGD examination in an encounter with a
current performed upper-tract EUS examination is the EUS's endoscopic portion.

REPORTABLE (7.8): performed, current and by the documenting team (all usable); a kind of the family's catalogue acts,
not the examination, not NOT_REPORTED, not bundled. COVERED: an event a counted code's decision read (its supporting
events, or the candidates its question is about), or a session included through catalogue.includes_examination. The
unresolved items: no_proposal, not_covered, coverage_unknown and unsupported as reconcile.reconcile gives them, and
in_doubt - a reportable kind whose candidate a relation or an unusable attribute blocks and that no code depends on: it
gets a service-scope question and keeps coding completeness open. The second-review mark is True on a no_proposal or
not_covered item (its events are done: status, time and performer usable) with an index below SECOND_REVIEW_CHECKED.

Imports nothing from studio.gi but the reference tables (FINAL 3.1).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Optional

from studio.gi import catalogue
from studio.interpretation import ENGINE_VERSION, events, identity, lexicon, mapping, relations, verify, wording
from studio.types import ClarificationSpec

SECOND_REVIEW_CHECKED = 64  # engine.SECOND_REVIEW_CHECKED (copied, pinned equal)
COMMON = dict(catalogue.COMMON_BUNDLED)
RESECTIONS = frozenset({'emr', 'esd'})
# The regions of the lower tract: an EUS event placed there is a lower EUS, of which no EGD is the endoscopic portion.
LOWER_REGIONS = frozenset({'colon', 'rectum', 'anus'})
NOT_ACT_KINDS = mapping.EXAMINATION_KINDS | frozenset(mapping.UMBRELLAS)
CODING_VERSION = ENGINE_VERSION  # event_coding's version: its reader (overlay.py) refuses any other


# --- bundling (7.7) -------------------------------------------------------------------------------------------------------

def current_performed(event: Mapping) -> bool:
    """A whole a part can be bundled into: performed, current (usable) - never a statement, an earlier act or a doubt."""
    return (events.usable(event, 'status') and events.value(event, 'status') == 'performed'
            and events.usable(event, 'time') and events.value(event, 'time') == 'current_encounter')


def _same_session(reading, whole: Mapping, part: Mapping) -> bool:
    return relations.procedure_row(reading.context, whole, part).result != relations.DIFFERENT


def _part_of(event: Mapping) -> str:
    part = event.get('part_of')
    if isinstance(part, Mapping) and part.get('state') == 'verified' and not part.get('open'):
        return part.get('value') or ''
    return ''


def _purpose(event: Mapping) -> str:
    return events.value(event, 'purpose') if events.usable(event, 'purpose') else ''


def _wholes(reading, part: Mapping, kinds) -> list:
    return [whole for whole in reading.events.values() if whole is not part and whole.get('catalogue_kind') in kinds
            and current_performed(whole) and _same_session(reading, whole, part)]


def _compatible(first, second) -> bool:
    return bool(first) and bool(second) and all(lexicon.compatible(one, two) for one in first for two in second)


def bundled_reason(reading, event: Mapping) -> str:
    """Why ``event`` is part of another documented act and never separately reported (module docstring), or ''."""
    kind = event.get('catalogue_kind') or ''
    raw = events.value(event, 'kind') or ''
    if kind in catalogue.NOT_REPORTED:
        return COMMON.get(kind, '')
    entry = catalogue.entry(event.get('family', ''))
    own = dict(entry.bundled) if entry is not None else {}
    if kind in own and kind not in COMMON and kind != 'biopsy':  # a family's own bundled kind (ERCP's contrast)
        return own[kind]
    whole_of = _part_of(event)
    lesion = identity.verified_lesion(event)
    if kind in mapping.ONE_ACT:
        for whole in _wholes(reading, event, RESECTIONS):
            if whole_of == whole['id']:
                return COMMON['lift_injection']
            other = identity.verified_lesion(whole)
            if lesion and other:
                if lesion == other and (raw == 'injection' or _purpose(event) == 'lift_for_resection'):
                    return COMMON['lift_injection']
                continue
            if raw != 'injection' or reading.relations_of(event['id'], (relations.BUNDLING,)):
                continue
            identities = (whole['target'].get('identity'), event['target'].get('identity'))
            places, own_places = reading.context.places(whole), reading.context.places(event)
            if identity.UNRESOLVED not in identities and _compatible(places, own_places):  # C-5
                return COMMON['lift_injection']
        return ''
    if kind in relations.RESECTION_TECHNIQUES:
        for whole in _wholes(reading, event, RESECTIONS):
            other = identity.verified_lesion(whole)
            if whole_of == whole['id'] or (lesion and lesion == other):
                return COMMON['resection_technique']
        return ''
    if kind == 'biopsy' and lesion:
        for whole in _wholes(reading, event, mapping.REMOVAL_MEMBERS):
            if identity.verified_lesion(whole) != lesion:
                continue
            single = (reading.lesions.get(lesion) or {}).get('multiplicity') == 'single'
            common = set(events.own_passages(event)) & set(events.own_passages(whole))
            if single or common:  # C-2: one passage in common bundles whatever the multiplicity
                return COMMON['biopsy_of_removed_lesion']
    return ''


def bundling_doubt(reading, event: Mapping) -> Optional[dict]:
    """The bundling_identity relation that makes ``event``'s bundling depend on an identity not established, whose
    whole is a current performed act (FINAL 7.7: asked, never READY), or None."""
    for relation in reading.relations_of(event['id'], (relations.BUNDLING,)):
        whole = reading.events.get(relation['statement'])
        if whole is not None and current_performed(whole):
            return relation
    return None


# --- sessions (7.8) -------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Session:
    """One family's documented service at this encounter: ``event`` its one current examination ('' for none, or when
    two leave it ``unresolved``), ``part_of`` the session it is the endoscopic portion of, ``done`` whether the family
    has a done event, ``incomplete`` whether its examination was begun and not completed."""
    id: str
    family: str
    kind: str
    label: str
    event: str = ''
    examinations: tuple = ()
    part_of: str = ''
    unresolved: bool = False
    done: bool = False
    incomplete: bool = False
    events: tuple = ()


def _lower_eus(reading) -> bool:
    for event in reading.events.values():
        if event.get('family') != 'gi.eus':
            continue
        places = [mapping.target_landmark(event)]
        extent = event.get('extent')
        if verify.usable(extent):
            places.append(extent.get('value', ''))
        if any(mapping.region(place) in LOWER_REGIONS for place in places if place):
            return True
    return False


def sessions(reading) -> dict:
    """{session id (the family slug): Session} of every family with an event, in the families' order."""
    by_family: dict = {}
    for event in reading.events.values():
        family = event.get('family') or ''
        if family:
            by_family.setdefault(family, []).append(event)
    found = {}
    for family in sorted(by_family, key=lambda value: (lexicon.FAMILY_ORDER.index(value)
                                                       if value in lexicon.FAMILY_ORDER else 99, value)):
        members = by_family[family]
        done = [event for event in members if events.done(event) and events.usable(event, 'kind')]
        exams = [event for event in done if event.get('catalogue_kind') in mapping.EXAMINATION_KINDS
                 and events.endoscopic_examination(event)]  # FINAL 5.6 E13: a manual examination is no session
        service = mapping.service_kind(family)
        session = Session(id=family, family=family, kind=service,
                          label=wording.kind_label(service) if service else wording.family_label(family),
                          event=exams[0]['id'] if len(exams) == 1 else '',
                          examinations=tuple(event['id'] for event in exams), unresolved=len(exams) >= 2,
                          done=bool(done), incomplete=bool(exams) and all(
                              events.value(event, 'status') == 'attempted_not_completed' for event in exams),
                          events=tuple(event['id'] for event in members))
        found[family] = session
    upper_eus = found.get('gi.eus') is not None and found['gi.eus'].examinations and not _lower_eus(reading)
    for family, session in list(found.items()):
        if not session.event:
            continue
        exam = reading.events[session.event]
        whole = reading.events.get(_part_of(exam))
        part_of = ''
        if whole is not None and whole.get('family') in found and whole.get('family') != family \
                and whole.get('catalogue_kind') in mapping.EXAMINATION_KINDS:
            part_of = whole['family']  # C3: the endoscopic portion of another examination
        elif family == 'gi.egd' and upper_eus:
            part_of = 'gi.eus'  # C-4: structurally, an EGD within an upper EUS
        if part_of:
            found[family] = replace(session, part_of=part_of)
    return found


def session_of(sessions_: Mapping, family: str) -> str:
    """The session id a code of ``family`` is matched to ('' when the family has none at this encounter)."""
    return family if family in sessions_ and sessions_[family].done else ''


# --- reportable and doubted events ---------------------------------------------------------------------------------------

def reportable_kind(event: Mapping) -> bool:
    entry = catalogue.entry(event.get('family', ''))
    kind = event.get('catalogue_kind') or ''
    return (entry is not None and kind in entry.acts and kind not in NOT_ACT_KINDS
            and kind not in catalogue.NOT_REPORTED)


def reportable(reading, event: Mapping) -> bool:
    """7.8: performed, current and by the documenting team, of a reportable kind, not bundled."""
    return (events.done(event) and events.value(event, 'status') == 'performed' and events.usable(event, 'kind')
            and events.usable(event, 'procedure') and reportable_kind(event) and not bundled_reason(reading, event))


def doubted(reading, event: Mapping) -> bool:
    """A reportable-kind event in doubt (FINAL 7.9 base rule (c), the event form of listed_in_doubt and
    listed_contradicted; fail-closed): stated positive or uncertain, not verified at another time or by another performer,
    and its status uncertain, a CONTRADICTION, DOUBT or UNRESOLVED relation on it, or an attribute of its own statement
    (kind, status, time, performer) unusable."""
    if not reportable_kind(event) or events.value(event, 'status') not in verify.POSITIVE + ('uncertain',):
        return False
    if events.verified_other_time(event) or events.verified_other_performer(event):
        return False
    if events.value(event, 'status') == 'uncertain' or reading.relations_of(event['id']):
        return True
    return not all(events.usable(event, name) for name in ('kind', 'status', 'time', 'performer'))


def _entry(reading, event: Mapping) -> dict:
    lesion = identity.verified_lesion(event)
    return {'event': event['id'], 'kind': event.get('catalogue_kind') or '',
            'label': wording.act_label(event.get('catalogue_kind') or ''), 'lesion': lesion,
            'describe': events.event_label(reading, event)}


# --- coverage and the unresolved items (reconcile.py:793-923, ported onto events) ---------------------------------------

@dataclass(frozen=True)
class Counted:
    """A counted, decidable code as coverage reads it: its key, code, family and the events its decision read (its
    supporting events first)."""
    key: str
    code: str
    family: str
    supporting: tuple = ()
    read: tuple = ()


@dataclass
class Coverage:
    unresolved: list = field(default_factory=list)  # item dicts (completeness['unresolved_items'] without the mark)
    bundled: list = field(default_factory=list)
    covered: dict = field(default_factory=dict)  # session id -> codes
    not_listed: list = field(default_factory=list)  # sessions done with no proposal and not listed
    unestablished: int = 0
    in_doubt: list = field(default_factory=list)  # (item, event id)


def inclusion_asks_no_code(sessions_: Mapping, session: Session, counted: Sequence[Counted]) -> bool:
    """reconcile.inclusion_asks_no_code over sessions: a session read as included in another asks for no code of its
    own while that other session has no counted code, or when one of its counted codes includes the examination."""
    including = sessions_.get(session.part_of) if session.part_of else None
    if including is None:
        return False
    codes = [item.code for item in counted if item.family == including.family]
    return not codes or any(catalogue.includes_examination(code, session.kind) for code in codes)


def _item(session: Session, event_ids, act: str, label: str, reason: str, evidence) -> dict:
    return {'service': session.id, 'family': session.family, 'act': act, 'label': label, 'reason': reason,
            'evidence': [dict(span) for span in list(evidence)[:2]], 'events': list(event_ids)}


def reconcile(reading, counted: Sequence[Counted], *, procedure_day: bool = False, sessions_=None) -> Coverage:
    """The unresolved items, bundled acts and covered sessions for the counted codes (module docstring), as
    reconcile.reconcile gives them over a documented-service reading."""
    sessions_ = sessions_ if sessions_ is not None else sessions(reading)
    out = Coverage()
    read_by = {}
    for item in counted:
        for eid in tuple(item.supporting) + tuple(item.read):
            read_by.setdefault(eid, []).append(item)
    any_other_done = {family for family, session in sessions_.items() if session.done}
    for session in sessions_.values():
        entry = catalogue.entry(session.family)
        if not session.done or entry is None or entry.support != catalogue.SUPPORTED:
            continue
        codes = [item for item in counted if item.family == session.family]
        out.covered[session.id] = [item.code for item in codes]
        members = [reading.events[eid] for eid in session.events]
        anchor = reading.events.get(session.event) or next((event for event in members if events.done(event)), None)
        evidence = events.anchors(reading, anchor) if anchor is not None else []
        if not codes and inclusion_asks_no_code(sessions_, session, counted):
            pass  # the including session's code covers the examination; its own acts still count
        elif not codes:
            if session.family == 'gi.office_em' and (procedure_day or any_other_done - {session.family}):
                continue  # never push an office visit beside a same-day procedure (listed as not_listed below)
            done_ids = [event['id'] for event in members if events.done(event)]
            out.unresolved.append(_item(session, done_ids, '', f'{session.label} (documented as '
                                        f'{"incomplete" if session.incomplete else "performed"}) has no supported '
                                        'proposal', 'no_proposal', evidence))
            for event in members:
                if reportable_kind(event) and events.done(event) and event.get('catalogue_kind') in \
                        catalogue.UNSUPPORTED_ACTS:
                    out.unresolved.append(_item(session, [event['id']], event['catalogue_kind'],
                                                f'{events.event_label(reading, event)}: no supported code profile',
                                                'unsupported', events.anchors(reading, event)))
            continue
        unknown = any(mapping.code_link(item.code).route != mapping.CATALOGUE_ROUTE for item in codes)
        for event in members:  # reconcile.reconcile's order: a bundled act is read before its kind is
            kind = event.get('catalogue_kind') or ''
            if kind in NOT_ACT_KINDS or not kind:
                continue
            why = bundled_reason(reading, event)
            if not events.done(event) or events.value(event, 'status') != 'performed':
                # an act no code of the family accounts for is listed whatever its outcome (reconcile, compl-1)
                if (events.value(event, 'status') in ('attempted_not_completed', 'uncertain') and not why
                        and kind in entry.acts and kind not in catalogue.UNSUPPORTED_ACTS
                        and not events.verified_other_time(event) and not events.verified_other_performer(event)
                        and not catalogue.family_codes_act(session.family, kind)):
                    out.unresolved.append(_item(session, [event['id']], kind,
                                                f'{events.event_label(reading, event)} in the {session.label}, attempted '
                                                'or in doubt: no code profile of this service accounts for it',
                                                'unsupported', events.anchors(reading, event)))
                continue
            if kind in catalogue.UNSUPPORTED_ACTS:
                out.unresolved.append(_item(session, [event['id']], kind,
                                            f'{events.event_label(reading, event)}: no supported code profile',
                                            'unsupported', events.anchors(reading, event)))
                continue
            under = _read_under(reading, sessions_, session, event)
            if under is not None:
                if under:
                    out.unresolved.append(_item(session, [event['id']], kind,
                                                f'{events.event_label(reading, event)} in the {session.label}: {under}, '
                                                'and no code profile of this service accounts for it', 'unsupported',
                                                events.anchors(reading, event)))
                else:
                    out.bundled.append({'service': session.id, 'act': kind, 'label': events.event_label(reading, event),
                                        'why': dict(entry.bundled).get(kind, ''), 'event': event['id']})
                continue
            if why:
                out.bundled.append({'service': session.id, 'act': kind, 'label': events.event_label(reading, event),
                                    'why': why, 'event': event['id']})
                continue
            if kind not in entry.acts:
                continue
            if bundling_doubt(reading, event) is not None and event['id'] in read_by:
                continue  # a code depends on its identity and asks it (act_target)
            if not catalogue.family_codes_act(session.family, kind):
                out.unresolved.append(_item(session, [event['id']], kind,
                                            f'{events.event_label(reading, event)} in the {session.label}: no code '
                                            'profile of this service accounts for it', 'unsupported',
                                            events.anchors(reading, event)))
                continue
            if any(item.family == session.family for item in read_by.get(event['id'], ())):
                continue
            out.unresolved.append(_item(session, [event['id']], kind,
                                        f'{events.event_label(reading, event)} in the {session.label}',
                                        'coverage_unknown' if unknown else 'not_covered', events.anchors(reading, event)))
    for session in sessions_.values():  # in doubt: a reportable kind blocked, that no code depends on (7.8)
        entry = catalogue.entry(session.family)
        if entry is None or entry.support != catalogue.SUPPORTED:
            continue
        for eid in session.events:
            event = reading.events[eid]
            if not doubted(reading, event) or eid in read_by or bundled_reason(reading, event):
                continue
            item = _item(session, [eid], event['catalogue_kind'],
                         f'{events.event_label(reading, event)} in the {session.label}: CPT Studio could not confirm '
                         'from the document that it was done at this encounter', 'in_doubt',
                         events.anchors(reading, event))
            out.unresolved.append(item)
            out.in_doubt.append((item, eid))
    merged: dict = {}
    for item in out.unresolved:  # one item per (session, act kind): a second site of one service is the same code
        key = (item['service'], item['act'])
        if key not in merged:
            merged[key] = item
        else:
            merged[key]['events'] = list(dict.fromkeys(merged[key]['events'] + item['events']))
    out.unresolved = list(merged.values())
    out.in_doubt = [(item, eid) for item, eid in out.in_doubt if any(item is kept for kept in out.unresolved)]
    listed = {item['service'] for item in out.unresolved}
    for session in sessions_.values():  # reconcile.uncounted: a session done with no proposal, not listed or included
        if session.id in out.covered and not out.covered[session.id] and not session.part_of \
                and session.id not in listed:
            out.not_listed.append(session)
    for family, session in sessions_.items():  # unestablished: a family stated, none of it done, read by no code
        if session.done or catalogue.entry(family) is None or any(item.family == family for item in counted):
            continue
        members = [reading.events[eid] for eid in session.events]
        if any(events.value(event, 'status') in verify.POSITIVE + ('uncertain',) and not events.verified_other_time(event)
               and not events.verified_other_performer(event) for event in members):
            out.unestablished += 1
    return out


def _read_under(reading, sessions_: Mapping, session: Session, event: Mapping) -> Optional[str]:
    """reconcile._read_under over events (catalogue.READ_UNDER: an EUS forceps biopsy read under the EGD): '' when the
    rule holds - its verified place is in the rule's regions and a done session of that family has a performed act of
    the kind - else why nothing reads it; None for any other act. A biopsy taken with the needle is the sampling."""
    rule = catalogue.READ_UNDER.get((session.family, event.get('catalogue_kind') or ''))
    if rule is None:
        return None
    family, label, tract, regions = rule
    if not mapping.in_regions(mapping.target_landmark(event), regions):
        return (f'the document does not place it at an {tract} site of an {tract} examination, so no {label} of this '
                'encounter reads it')
    other = sessions_.get(family)
    reads = other is not None and other.done and any(
        reading.events[eid].get('catalogue_kind') == event.get('catalogue_kind') and events.done(reading.events[eid])
        and events.value(reading.events[eid], 'status') == 'performed' for eid in other.events)
    return '' if reads else f'no {label} documented at this encounter reads it'


def unresolved_record(items: Sequence[dict]) -> list:
    """completeness['unresolved_items']: each item with its second-review mark (FINAL 7.8, D10): True on a no_proposal or
    not_covered item - whose events are done (status, time and performer usable) - with an index below
    SECOND_REVIEW_CHECKED."""
    return [{**item, 'second_review': index < SECOND_REVIEW_CHECKED and item['reason'] in ('no_proposal', 'not_covered')}
            for index, item in enumerate(items)]


def in_doubt_questions(reading, coverage: Coverage, asked=()) -> list:
    """A service-scope question for each in_doubt item, with the fact of 7.4 for its event (FINAL 7.8), once per (family,
    fact), never one a proposal of the family already asks (``asked``: (family, fact) pairs)."""
    seen = set(asked)
    out = []
    for item, eid in coverage.in_doubt:
        question = events.focus_question(reading, reading.events[eid])
        if question is None or (item['family'], question.fact) in seen:
            continue
        seen.add((item['family'], question.fact))
        out.append(ClarificationSpec(scope='service', fact=question.fact, question=question.question,
                                     reason=question.reason, family=item['family']))
    return out


# --- completeness (reconcile.completeness; copied wording, pinned equal) -------------------------------------------------

UNVERIFIED_REASON = "CPT Studio's reading left {count} attribute{s} unverified that a decision read"


def completeness(coverage: Coverage, sessions_: Mapping, *, open_questions: int, provider_ok: bool, conflicts: int,
                 unverified: int = 0) -> dict:
    """The encounter's coding completeness at assessment time, worded as reconcile.completeness words it, plus FINAL
    7.8's reason for the attributes left unverified that a decision read."""
    reasons = []
    unresolved = coverage.unresolved
    not_listed = coverage.not_listed
    if not provider_ok:
        reasons.append('the provider response was not available')
    if unresolved:
        reasons.append(f'{len(unresolved)} documented service{"s" if len(unresolved) != 1 else ""} or act'
                       f'{"s" if len(unresolved) != 1 else ""} without a supported proposal')
    if coverage.unestablished:
        reasons.append(f'{coverage.unestablished} documented service{"s" if coverage.unestablished != 1 else ""} not '
                       'established as performed and read by no proposal')
    if not_listed:
        reasons.append(f'{len(not_listed)} documented service{"s" if len(not_listed) != 1 else ""} without a supported '
                       'proposal and not listed as unresolved: ' + ', '.join(uncounted_label(s) for s in not_listed))
    if conflicts:
        reasons.append(f'{conflicts} conflict{"s" if conflicts != 1 else ""} in the record')
    if open_questions:
        reasons.append(f'{open_questions} open question{"s" if open_questions != 1 else ""}')
    if unverified:
        reasons.append(UNVERIFIED_REASON.format(count=unverified, s='' if unverified == 1 else 's'))
    performed = [session for session in sessions_.values() if session.done]
    return {
        'state': 'incomplete' if reasons else 'complete_pending_review',
        'reasons': reasons,
        'services': len(performed),
        'unresolved': len(unresolved),
        'conflicts': conflicts,
        'statement': ('Coding for this encounter is incomplete: ' + '; '.join(reasons) + '.') if reasons else (
            'Every documented service has a proposal to review. This is not verified coding: code-set membership '
            'and NCCI edits are not verified, and each proposal still needs a reviewer.'),
    }


def uncounted_label(session: Session) -> str:
    """reconcile.uncounted_label over a session (copied)."""
    return session.label + (' beside a procedure done or possibly done the same day'
                            if session.family == 'gi.office_em' else '')


def included_by(sessions_: Mapping, covered: Mapping) -> dict:
    """engine._included_by over sessions: {session id: the counted codes of the session it is read as part of that
    include its examination} for every done session read as part of another."""
    out = {}
    for session in sessions_.values():
        if session.done and session.part_of:
            out[session.id] = [code for code in covered.get(session.part_of, ())
                               if catalogue.includes_examination(code, session.kind)]
    return out


# --- event_coding (FINAL 7.8): what the overlay, the reports and the customer API read -----------------------------------

def event_coding(reading, sessions_: Mapping, codes: Mapping) -> dict:
    """{version, sessions, codes, lesions} (module docstring; FINAL 7.8). ``codes``: {proposal key: (session id, E*
    event ids)} of the decidable proposals."""
    coded_sessions = {}
    for session in sessions_.values():
        members = [reading.events[eid] for eid in session.events]
        coded_sessions[session.id] = {
            'family': session.family, 'event': session.event, 'part_of': session.part_of, 'label': session.label,
            'kind': session.kind, 'unresolved': session.unresolved, 'done': session.done,
            'incomplete': session.incomplete, 'examinations': list(session.examinations),
            # the session's own service is never an act beside itself: an office visit's visit event (lexicon.EM_KINDS)
            'reportable': [_entry(reading, event) for event in members if reportable(reading, event)
                           and events.value(event, 'kind') not in lexicon.EM_KINDS],
            'doubted': [_entry(reading, event) for event in members if doubted(reading, event)
                        and events.value(event, 'kind') not in lexicon.EM_KINDS],
        }
    coded_codes = {}
    for key, (session, supporting) in codes.items():
        lesions = sorted({identity.verified_lesion(reading.events[eid]) for eid in supporting
                          if eid in reading.events and identity.verified_lesion(reading.events[eid])})
        coded_codes[key] = {'session': session, 'events': list(supporting), 'lesions': lesions}
    coded_lesions = {}
    for lid, lesion in reading.lesions.items():
        site = lesion.get('site') or {}
        coded_lesions[lid] = {'words': lesion.get('words'), 'landmark': site.get('value', 'not_stated')
                              if verify.usable(site) else 'not_stated', 'multiplicity': lesion.get('multiplicity'),
                              'distinct_from': list(lesion.get('distinct_from') or ()),
                              'label': events.lesion_words(reading, lid)}
    return {'version': CODING_VERSION, 'sessions': coded_sessions, 'codes': coded_codes, 'lesions': coded_lesions}
