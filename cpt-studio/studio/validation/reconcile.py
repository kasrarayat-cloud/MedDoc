"""Reconcile provider proposals with the documented-service inventory (ARCHITECTURE 5.9-5.10). Pure.

Three questions, kept apart on purpose:
- Is a proposal ready for review? A provider-selected code is matched to the documented service of its family and to
  the documented act it accounts for (the coverage catalogue's internal code-to-act table). Its status follows that
  service and act - never a fragment of a provider passage read on its own - and its evidence is verified: each
  provider passage either shows the act (and so its anatomy, technique and date, which the inventory reads in context),
  or it does not, and CPT Studio then shows the source passages that do.
- What does the document say was done that no proposal accounts for? Every performed act the catalogue reconciles,
  not bundled by a profile rule, is covered by a selected proposal or listed as unresolved. Nothing is coded for it:
  an unresolved service is shown, never filled in, and no alternative is promoted.
- Is the encounter's coding complete? Only when no documented service is unresolved, no conflict is open and every
  question is answered - and even then code-set membership and NCCI edits stay not verified (no licensed source).
"""
from __future__ import annotations

import functools
import re
from dataclasses import dataclass, replace
from typing import Optional, Sequence

from studio.gi import catalogue
from studio.gi import sections as gi_sections
from studio.gi.context import is_member_conflict
from studio.gi.services import (ACTS, FAMILY_REGIONS, INSTRUMENT_FAMILY, INSTRUMENTS, LUMEN, POSITIVE,
                                 HYPOTHETICAL_CUE, ROUTING_CONTRARY_CUE, ROUTING_DOUBT_CUE, SERVICES, Act, Conflict,
                                 DocumentedService,
                                 ServiceInventory, _sentences, act_regions, examined_regions, reflow)
from studio.types import Check, ClarificationSpec, EvidenceSpan, PageSpan, Span
from studio.validation import checks

SOURCE = f'cpt-studio:{catalogue.CATALOGUE_VERSION}'
INVENTORY_SOURCE = 'cpt-studio:gi-services@4'  # the inventory's label (services.INVENTORY_VERSION)
REMOVAL_KINDS = ('snare', 'emr', 'hot_biopsy', 'esd')
OWN_ROLES = ('physician', 'unknown')  # whose documentation of the procedure the reconciliation counts
# A denial that states a failed attempt, never a mere denial ("was not attempted"): refutation round 2, esc-7 and the
# cost lens's control ("We were unable to ...", "could not be achieved", "was not successful")
FAILED_ATTEMPT = re.compile(r"\b(?:unable|could\s+not|couldn['\u2019]t|cannot|can\s+not|fail(?:s|ed|ure|ing)?"
                            r"|unsuccessful(?:ly)?|without\s+success|not\s+(?:be\s+|been\s+)?(?:successful|achieved"
                            r"|completed))\b", re.I)
# Physiology studies whose coded act is the study itself (the act a code of the family accounts for is the service).
STUDY_ACTS = {'gi.capsule': 'capsule_study', 'gi.motility': 'manometry', 'gi.reflux': 'ph_monitoring',
              'gi.anorectal': 'manometry'}
ACT_LABELS = {
    'biopsy': 'forceps biopsy', 'hot_biopsy': 'hot forceps removal', 'snare': 'snare removal', 'emr': 'endoscopic '
    'mucosal resection', 'esd': 'endoscopic submucosal dissection', 'ablation': 'ablation', 'bleeding_control':
    'bleeding control', 'clip': 'clip placement', 'tattoo': 'submucosal tattoo', 'injection': 'submucosal injection',
    'band_ligation': 'band ligation', 'dilation': 'dilation', 'stent': 'stent placement', 'foreign_body':
    'foreign-body removal', 'sphincterotomy': 'sphincterotomy', 'stone_extraction': 'stone removal', 'lithotripsy':
    'lithotripsy', 'cholangioscopy': 'cholangioscopy', 'cannulation': 'cannulation', 'peg': 'gastrostomy (PEG) '
    'placement', 'tube_replacement': 'feeding-tube replacement', 'tube_placement': 'tube placement', 'specimen': 'specimen collection',
    'myotomy': 'myotomy', 'decompression': 'decompression', 'fundoplication': 'transoral fundoplication',
    'capsule_study': 'capsule study', 'manometry': 'manometry', 'ph_monitoring': 'pH / impedance monitoring',
    'rectal_sensation': 'rectal sensation and compliance testing', 'moderate_sedation': 'moderate sedation',
    'fna': 'fine-needle aspiration or biopsy', 'eus_exam': 'endosonographic examination', 'em_visit': 'office visit',
    'drainage': 'drainage', 'stent_removal': 'stent removal', 'stent_exchange': 'stent exchange',
    'pressure_measurement': 'pressure measurement', 'balloon_expulsion': 'balloon expulsion test',
}
SERVICE_LABELS = {'egd': 'upper endoscopy', 'esophagoscopy': 'esophagoscopy', 'poem': 'peroral endoscopic myotomy',
                  'colonoscopy': 'colonoscopy', 'flex_sig': 'flexible sigmoidoscopy', 'eus': 'endoscopic ultrasound',
                  'ercp': 'ERCP', 'enteroscopy': 'enteroscopy', 'capsule': 'capsule endoscopy',
                  'manometry': 'manometry', 'ph_study': 'pH / impedance study', 'anorectal_testing':
                  'anorectal testing', 'feeding_tube': 'feeding-tube procedure', 'office_em': 'office / outpatient '
                  'visit'}


def act_label(kind: str) -> str:
    return ACT_LABELS.get(kind, kind.replace('_', ' '))


def kind_label(kind: str) -> str:
    """A service kind's label, as service_label words a documented service's own kind."""
    return SERVICE_LABELS.get(kind, kind.replace('_', ' '))


def mention_label(kind: str) -> str:
    """A service mention's kind as a sentence names it: its service label, else - a kind named as an act, such as a PEG
    placement, which services files under the upper endoscopy - its act label (refutation round 9, wording-2: "the peg
    as cancelled"). service_label is never changed by it: services.inventory names a service that way on every path."""
    return SERVICE_LABELS.get(kind) or ACT_LABELS.get(kind) or kind.replace('_', ' ')


def service_label(service: DocumentedService) -> str:
    return kind_label(service.kind)


def quote(span: Span, limit: int = 160) -> str:
    text = ' '.join(span.text.split())
    return f'“{text[:limit - 1]}…”' if len(text) > limit else f'“{text}”'


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def lesion_words(service: DocumentedService, lesion_id: str) -> str:
    lesion = next((l for l in service.lesions if l.id == lesion_id), None)
    if lesion is None:
        return ''
    parts = [p for p in (lesion.size, lesion.morphology, lesion.noun) if p]
    where = f' in the {lesion.anatomy}' if lesion.anatomy else ''
    spec = f' (specimen {lesion.specimen})' if lesion.specimen else ''
    return f'{" ".join(parts)}{where}{spec}'


def describe_act(service: DocumentedService, act: Act) -> str:
    target = lesion_words(service, act.lesion) if act.lesion else ', '.join(act.anatomy)
    technique = f' ({act.technique})' if act.technique and act.technique not in act_label(act.kind) else ''
    return f'{act_label(act.kind)}{technique}' + (f' of the {target}' if act.lesion and target else
                                                  f' at the {target}' if target else '')


# --- one proposal --------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Match:
    """What the inventory says about one provider-selected code."""
    state: str  # performed | incomplete | not_performed | uncertain
    service: DocumentedService
    acts: tuple[Act, ...]  # the performed acts the code accounts for
    reason: str  # service | act_denied | act_missing | conflict | service_uncertain | service_negative | profile_unknown
    detail: str
    conflict: Optional[Conflict] = None
    question: str = ''


def service_for(inventory: ServiceInventory, family: str) -> Optional[DocumentedService]:
    """The service of ``family`` the inventory documents: the one performed today when there is one."""
    found = inventory.for_family(family)
    if not found:
        return None
    rank = {'performed': 0, 'incomplete': 0, 'uncertain': 1, 'cancelled': 2, 'negated': 2, 'planned': 3, 'historical': 4}
    return sorted(found, key=lambda s: rank.get(s.status, 5))[0]


def gi_services_name_only(act) -> bool:
    """R1a-r5: whether ``act`` carries services.NAME_ONLY_CUE."""
    from studio.gi.services import NAME_ONLY_CUE
    return NAME_ONLY_CUE in act.cues


def match(code: str, inventory: ServiceInventory, family: str) -> Optional[Match]:
    """The inventory's reading of ``code`` (None when the inventory documents no service of its family: the code is
    then judged as before, by its own passages and routing)."""
    service = service_for(inventory, family)
    if service is None:
        return None
    profile = catalogue.code_profile(code)
    name = service_label(service)
    if service.status in ('planned', 'historical', 'cancelled', 'negated'):
        ev = service.evidence[0] if service.evidence else None
        return Match('not_performed', service, (), 'service_negative',
                     f'The document gives the {name} as {service.status}, not as performed on the date of service'
                     + (f': {quote(ev)}.' if ev else '.'))
    if service.status == 'uncertain':
        # The cue that made it uncertain: routing's reading of the family when that decided it (services._finish adds it
        # after the statement of performance it overrides), else the service's own first doubt.
        cue = next((c for c in service.cues if c.startswith((ROUTING_CONTRARY_CUE, ROUTING_DOUBT_CUE))),
                   service.cues[0] if service.cues else 'its documentation does not establish it')
        return Match('uncertain', service, (), 'service_uncertain',
                     f'The document does not establish the {name} as performed on the date of service ({cue}).',
                     question=f'Confirm whether the {name} was performed on the date of service.')
    positive = 'incomplete' if service.status == 'incomplete' else 'performed'
    if profile is None or profile.family != family:
        return Match('uncertain' if profile is not None else positive, service, (), 'profile_unknown',
                     f'The {name} is documented as {service.status}; which documented act {code} accounts for is not '
                     'established by the coverage catalogue (internal profile), so its evidence is checked against the '
                     'service only.')
    if profile.base or 'em_visit' in profile.covers:
        detail = f'The {name} is documented as {service.status}' + (
            f' ({service.completion} examination)' if service.completion != 'unknown' else '') + '.'
        others = sorted({a.kind for a in service.acts if a.status == 'performed'
                         and a.kind in (catalogue.entry(family).acts if catalogue.entry(family) else ())})
        if profile.base and others:
            detail += (' The service also documents ' + ', '.join(act_label(k) for k in others)
                       + ', which another code accounts for.')
        return Match(positive, service, (), 'service', detail)
    kinds = profile.covers
    done = tuple(a for a in service.acts if a.kind in kinds and a.status == 'performed')
    denied = tuple(a for a in service.acts if a.kind in kinds and a.status in ('negated', 'cancelled'))
    conflict = next((c for c in inventory.conflicts if c.service == service.id
                     and (c.subject in kinds or any(k in ('tattoo', 'injection') for k in kinds)
                          and c.subject in ('tattoo', 'injection'))), None)
    what = ' or '.join(act_label(k) for k in kinds)
    if conflict is not None:
        sides = '; '.join(f'{side.role} entry: {side.status} ({quote(side.evidence[0], 120)})' for side in conflict.sides
                          if side.evidence)
        return Match('uncertain', service, done, 'conflict',
                     f'The document conflicts on the {what} this code accounts for: {sides}. Both are kept; neither is '
                     'chosen.', conflict=conflict,
                     question=f'The record states the {what} both as performed and as not performed. Which is correct '
                              'for this encounter?')
    if done and all(gi_services_name_only(a) for a in done):
        # R1a-r5 (hold-only): every act this code could rest on is tied to its service only by a lesion's name in a
        # document of several procedures (services.NAME_ONLY_CUE): it stays documented, and the code is held for the
        # reviewer - a reason no release or exclusion path reads
        return Match('uncertain', service, done, 'named_only',
                     f'The {name} is documented as {service.status}, but the {what} this code accounts for is tied to '
                     f'it only by a lesion\'s name ({quote(done[0].evidence[0])}) in a document of several procedures.',
                     question=f'The {what} ({quote(done[0].evidence[0], 120)}) is tied to the {name} only by a '
                              f'lesion\'s name. Was a {what} performed in the {name} on the date of service?')
    if done:
        # Harness repair 2026-11-05 (stage 6): an act the reconciliation reads as part of another documented act
        # (_bundled: the lift injection of a lesion the service resects by EMR or ESD, the biopsy of a lesion it then
        # removes, a prophylactic clip, ...) is never what a code accounts for while the service documents an act of the
        # code's kinds that is not; where every such act is part of another, the code is held with that reading, never
        # ready - no separate act is documented for it, and an EMR's components are never charged apart from it.
        own = tuple(a for a in done if _bundled(service, a) is None)
        if not own:
            listed = '; '.join(describe_act(service, a) for a in done[:4])
            why = _bundled(service, done[0])
            return Match('uncertain', service, done, 'act_included',
                         f'The {name} is documented as {service.status} with {listed}, which is part of another '
                         f'documented act: {why} No separate {what} is documented for this code.',
                         question=f'The {what} documented ({quote(done[0].evidence[0], 120)}) is part of another '
                                  f'procedure documented with it. Was a separate {what} performed on the date of '
                                  'service?')
        done = own
        listed = '; '.join(describe_act(service, a) for a in done[:4])
        return Match(positive, service, done, 'service',
                     f'The {name} is documented as {service.status} with {listed}.')
    if denied:
        return Match('not_performed', service, (), 'act_denied',
                     f'The {name} is documented as {service.status}, but the document states the {what} was not '
                     f'performed: {quote(denied[0].evidence[0])}.')
    doubted = next((a for a in service.acts if a.kind in kinds and a.status == 'uncertain' and a.evidence), None)
    if doubted is not None:
        # The document names the act and leaves it in doubt ("It is unclear whether biopsies were taken."): held with
        # that passage, never reported as an act the document does not mention. Still 'act_missing' - no such act is
        # documented as done - so every rule that reads that reason (engine._select, engine._second_opinion) is unchanged.
        return Match('uncertain', service, (), 'act_missing',
                     f'The {name} is documented as {service.status}, but the document does not establish the {what} '
                     f'as done: {quote(doubted.evidence[0])}.',
                     question=f'The documented {name} leaves the {what} in doubt ({quote(doubted.evidence[0], 120)}). '
                              f'Was a {what} performed on the date of service?')
    return Match('uncertain', service, (), 'act_missing',
                 f'The {name} is documented as {service.status}, but no {what} is documented as done in it.',
                 question=f'The documented {name} shows no {what}. Was a {what} performed on the date of service?')


@dataclass(frozen=True)
class Support:
    """How the passages relate to the act a proposal accounts for."""
    status: str  # pass | warn | fail | not_applicable
    supporting: tuple[int, ...]  # indices of provider passages that show it
    unrelated: tuple[int, ...]  # indices of provider passages that do not
    source: tuple[Span, ...]  # passages CPT Studio selected from the source that show it
    detail: str


def _targets(m: Match) -> tuple[Span, ...]:
    if m.acts:
        return tuple(ev for a in m.acts for ev in a.evidence)
    s = m.service
    return tuple(s.evidence) + tuple(s.completion_evidence) + tuple(
        ev for a in s.acts if a.status == 'performed' for ev in a.evidence)


def _study_named(m: Match, span: EvidenceSpan, today, report_family=None) -> bool:
    """A physiology study whose coded act is the study itself (STUDY_ACTS): a passage that names this service, or
    that lies in the study's own report (``report_family``: the family whose report part holds it - its results and its
    interpretation are the study's; refutation gi2 RC4, ho-08: 91010's results rows and interpretation read as citing
    other text), and states something of this encounter (``today``: not in a plan, history or indication section, not
    about another time, planned, denied or cancelled - "Esophageal manometry showed normal peristalsis.") shows the
    study, as a statement of this visit shows an office visit."""
    study = STUDY_ACTS.get(m.service.family)
    if today is None or study is None or not m.acts or any(a.kind != study for a in m.acts):
        return False
    named = any(family == m.service.family and pattern.search(span.text) for family, _, pattern in SERVICES) or (
        report_family is not None and report_family(span) == m.service.family)
    return named and today(span)


def support(m: Match, evidence: Sequence[EvidenceSpan], current=None, today=None, report_family=None) -> Support:
    """How ``evidence`` (the provider's exact passages) relates to the documented act. For an office visit the act is
    the visit itself: a passage supports it when it is a statement of this visit - not one ``current`` reads as about
    another time ("Last seen by Dr. Ramos on 2026-03-02", a planned procedure). So for a study that is its own act: a
    statement of this encounter naming the study supports it (_study_named)."""
    targets = _targets(m)
    supporting, unrelated = [], []
    for index, span in enumerate(evidence):
        if m.service.family == 'gi.office_em' and current is not None:
            (supporting if current(span) else unrelated).append(index)
        elif any(_overlaps(span.start, span.end, t.start, t.end) for t in targets) \
                or _study_named(m, span, today, report_family):
            supporting.append(index)
        else:
            unrelated.append(index)
    what = (' and '.join(sorted({act_label(a.kind) for a in m.acts})) if m.acts
            else f'the {service_label(m.service)}')
    source = tuple(_first_unique(targets))[:4]
    if m.state not in ('performed', 'incomplete'):
        return Support('not_applicable', tuple(supporting), tuple(unrelated), source,
                       'Not checked: the documented service or act is not established as performed.')
    if supporting and not unrelated:
        return Support('pass', tuple(supporting), (), (), f'Every provider passage shows {what}.')
    if supporting:
        return Support('pass', tuple(supporting), tuple(unrelated), (),
                       f'{len(supporting)} of {len(evidence)} provider passages show {what}; '
                       f'{len(unrelated)} cite text that does not.')
    if source:
        return Support('warn', (), tuple(unrelated), source,
                       f'None of the provider passages shows {what}; they match the text exactly but cite other text. '
                       f'CPT Studio selected the source passages that do: '
                       + '; '.join(quote(s, 120) for s in source[:2]) + '.')
    return Support('fail', (), tuple(unrelated), (), f'No passage shows {what}.')


def _first_unique(spans: Sequence[Span]) -> list[Span]:
    seen, out = set(), []
    for s in spans:
        if (s.start, s.end) not in seen:
            seen.add((s.start, s.end))
            out.append(s)
    return out


def match_check(m: Match) -> Check:
    status = {'performed': 'pass', 'incomplete': 'warn', 'not_performed': 'fail', 'uncertain': 'warn'}[m.state]
    if m.reason == 'profile_unknown' and m.state != 'uncertain':
        status = 'not_verified'
    return Check('service.documented', 'Documented service and act', status, m.detail, INVENTORY_SOURCE)


def support_check(s: Support) -> Check:
    return Check('evidence.support', 'Passages show the coded act', s.status, s.detail, INVENTORY_SOURCE)


# --- a status, as the readers read the passage a reviewer confirms it on (HARNESS.md 11.3, 12.5) -------------------
# Refutation round 2, EV2-1: a status candidate, and every status confirmation the engine reads, is checked on the act
# the question asks about. One function decides it (status_stated), which studio.candidates and engine._Confirmations
# both call, on the documented-service inventory the engine decided the hold from.

# A status a confirmation carries, as the inventory reads a mention's status (services.ACT_STATUSES): 'not performed' is
# a denial.
STATUS_READS = {'performed': 'performed', 'not_performed': 'negated', 'negated': 'negated', 'cancelled': 'cancelled',
                'canceled': 'cancelled', 'planned': 'planned', 'historical': 'historical'}
# How the readers' reading of a mention is said: the status words a confirmation carries, and a doubt.
STATUS_SAID = {'performed': 'performed', 'incomplete': 'performed', 'negated': 'not performed',
               'cancelled': 'cancelled', 'planned': 'planned', 'historical': 'historical', 'uncertain': 'in doubt'}
HELD_SECTIONS = ('history', 'plan', 'indication')  # never documents a service at this encounter (HARNESS.md 11.3)
NO_SUBJECT = "CPT Studio's readers cannot tell which act this passage documents"
NOT_A_STATUS = ('the value is neither performed nor a status of a service not performed at this encounter (not '
                'performed, cancelled, planned, historical)')


def held_why(kind: str) -> str:
    """Why a passage in a ``kind`` section (HELD_SECTIONS) documents nothing at this encounter, in CPT Studio's
    words."""
    article = 'an' if kind[:1] in 'aeiou' else 'a'
    return f'the passage is in {article} {kind} section, which never documents a service at this encounter'


def held_section(text: str, start: int, end: int) -> str:
    """The first history, plan or indication section (gi.sections, the routing sections reader) the passage [start, end)
    lies in, or '' - a passage there never documents a service at this encounter."""
    lay = gi_sections.layout(text)
    kinds = [section.kind for section in lay.sections if section.start < end and start < section.end]
    return next((kind for kind in kinds or [lay.section_at(start).kind] if kind in HELD_SECTIONS), '')


def page_spans(pages) -> tuple[PageSpan, ...]:
    """``pages`` (PageSpan, or {page, start, end} as a revision stores them) as PageSpans, each well-formed one once."""
    out = []
    for page in pages or ():
        values = ([page.get(name) for name in ('page', 'start', 'end')] if isinstance(page, dict)
                  else [getattr(page, name, None) for name in ('page', 'start', 'end')])
        if all(type(value) is int for value in values) and 0 <= values[1] <= values[2]:
            out.append(PageSpan(*values))
    return tuple(sorted(set(out), key=lambda p: (p.start, p.end, p.page)))


@functools.lru_cache(maxsize=4)
def _reader_sentences(text: str, pages: tuple[PageSpan, ...]) -> tuple[tuple[int, int], ...]:
    return tuple(_sentences(reflow(text, pages)))


def whole_sentence(text: str, start: int, end: int, pages=()) -> tuple[int, int]:
    """The whole sentence (or run of whole sentences) the passage [start, end) lies in, as the documented-service reader
    cuts the text into sentences - on the same reflowed view, a soft line break inside a sentence read as a space
    (services.build) - so a slice is never read apart from the words around it ("biopsies of the ascending colon lesion
    were taken" inside "It is unclear whether biopsies of the ascending colon lesion were taken.")."""
    met = [(s, e) for s, e in _reader_sentences(text, page_spans(pages)) if s < end and start < e]
    if not met:
        return start, end
    return min(start, met[0][0]), max(end, met[-1][1])


def status_subject(inventory: Optional[ServiceInventory], service_id: str, code: str,
                   family: str) -> Optional[tuple[DocumentedService, tuple[str, ...]]]:
    """What a status question of proposal ``code`` (family ``family``) asks about, read where the readers decided its
    hold: the documented service it was matched to (``service_id``: match's Match.service, recorded as
    support['service']) and the act kinds its code accounts for there (the code profile's ``covers``) - or () for the
    service itself: a base code, an E/M, or a code whose profile is of another family (profile_unknown). A code that
    accounts for an act asks about that act whichever hold raised its question (no act documented as done, one left in
    doubt, or the service itself in doubt): a confirmation decides the code's status, and the code accounts for the act.
    None when the readers have nothing to check it against: no consistent inventory, no service of that id and family
    (a hold no documented service decided: checks.performed_clarification)."""
    if not isinstance(inventory, ServiceInventory) or not isinstance(service_id, str) or not service_id:
        return None
    service = inventory.service(service_id)
    if service is None or service.family != family:
        return None
    profile = catalogue.code_profile(code) if isinstance(code, str) else None
    if profile is None or profile.family != family or profile.base or 'em_visit' in profile.covers \
            or not profile.covers:
        return service, ()
    return service, tuple(profile.covers)


def _status_mentions(service: DocumentedService, kinds: tuple[str, ...]) -> list[tuple[int, int, str]]:
    """(start, end, status) of every mention of the subject the inventory records, in text order: each act of those
    kinds in the service with its own reading; for the service itself, each passage that establishes it - read with
    its status for an office visit (services._em_service keeps the mentions of its own status), as performed for a
    procedure (services._finish keeps its report title and its performed statements) - and each act it documents as
    performed (an act done in a service documents the service)."""
    if kinds:
        found = [(ev.start, ev.end, act.status) for act in service.acts if act.kind in kinds for ev in act.evidence]
    else:
        said = service.status if service.family == 'gi.office_em' and service.status not in POSITIVE else 'performed'
        found = [(ev.start, ev.end, said) for ev in service.evidence]
        found += [(ev.start, ev.end, 'performed') for act in service.acts if act.status == 'performed'
                  for ev in act.evidence]
    return sorted(found)


def status_stated(inventory: Optional[ServiceInventory], service_id: str, code: str, family: str, value: str,
                  start: int, end: int, text: str, pages=()) -> str:
    """'' when CPT Studio's readers - the documented-service inventory the engine decided the hold from - read the
    passage [start, end) of ``text`` as stating exactly ``value`` for the question's subject (status_subject); otherwise
    why, a clause in CPT Studio's words. In this order: ``value`` is a status a confirmation carries; the passage lies
    in no history, plan or indication section; the readers can tell the subject; and every mention of the subject in
    the passage's WHOLE sentence (whole_sentence, never a slice of it) - at least one - is read with exactly that
    status: 'performed' never beside a mention read as negated, cancelled, in doubt, planned or historical, and a
    not-performed status (a denial for 'not performed', cancelled, planned, historical) only where every mention is read
    so."""
    wanted = STATUS_READS.get(re.sub(r'[\s-]+', '_', value.strip().lower())) if isinstance(value, str) else None
    if wanted is None:
        return NOT_A_STATUS
    held = held_section(text, start, end)
    if held:
        return held_why(held)
    subject = status_subject(inventory, service_id, code, family)
    if subject is None:
        return NO_SUBJECT
    service, kinds = subject
    name = ' or '.join(act_label(kind) for kind in kinds) if kinds else service_label(service)
    lo, hi = whole_sentence(text, start, end, pages)
    read = [STATUS_SAID.get(status, status) for s, e, status in _status_mentions(service, kinds) if s < hi and lo < e]
    if not read:
        return (f'the passage does not name the {name}' if kinds
                else f"CPT Studio's readers read no statement of the {name} in the passage")
    if 'in doubt' in read:
        return f'the passage leaves the {name} in doubt'
    said = STATUS_SAID[wanted]
    other = next((status for status in read if status != said), None)
    if other is None:
        return ''
    if said in read:
        return f'the passage states the {name} both as {said} and as {other}'
    return f'the passage states the {name} as {other}, not as {said}'


def elsewhere(code: str, inventory: ServiceInventory) -> Optional[Match]:
    """For a code whose family the inventory documents no service of (match is None): the acts the code accounts for
    (catalogue.code_acts) that the inventory documents as done in another family's service at the code's own site
    (_code_regions), as a Match its passages are verified against (support) - never the code's status, which its own
    passages still decide (engine._select), and never the service it is matched to. None when no such act is
    established or documented done there (refutation gi2 RC5, ho-09: 46221 was ready on "Sedation: None." and the
    sigmoidoscope's advance, unchecked, beside "band ligation of two columns through the flexible sigmoidoscope")."""
    kinds = catalogue.code_acts(code)
    regions = _code_regions(code)
    # only at the code's own site: where the act's own passage or lesion names one, else its service's tract - never an
    # esophageal variceal ligation for a hemorrhoid banding code, or a gastric polypectomy for a colonoscopy code
    # (refutation gi2 attr-F5); a code with no site established is checked against no act of another family
    acts = tuple(a for s in inventory.services for a in s.acts if a.kind in kinds and a.status == 'performed'
                 and (act_regions(s, a) or FAMILY_REGIONS.get(s.family, frozenset())) & regions)
    if not acts:
        return None
    return Match('performed', inventory.service(acts[0].service), acts, 'elsewhere', '')


def _code_regions(code: str) -> frozenset:
    """Where the act ``code`` accounts for is done (studio.gi.services.ANATOMY regions): its profile's family's tract
    (FAMILY_REGIONS), or catalogue.UNRECONCILED_REGIONS for a code of a family never reconciled. Empty when not
    established."""
    profile = catalogue.code_profile(code)
    if profile is not None:
        return FAMILY_REGIONS.get(profile.family, frozenset())
    return frozenset(catalogue.UNRECONCILED_REGIONS.get(code, ()))


# A passage states its act done through or with a service where, after the act's own mention, an instrumental
# preposition (a closed class) governs the service's or its instrument's name, with at most two words of the name's
# own between them ("band ligation ... through the flexible sigmoidoscope", "banded today with the colonoscope in
# retroflexion", "performed via flexible sigmoidoscopy") - none of them a conjunction, a negation or another
# preposition, which would make the name another phrase's ("with an anoscope after withdrawal of the colonoscope") - and
# no negation or replacement governs the preposition ("with the anoscope, not through the flexible sigmoidoscope", "via
# anoscopy instead of through the colonoscope"). A name before the act's mention heads another phrase ("With the
# colonoscope withdrawn, two internal hemorrhoids were banded using an anoscope").
DONE_THROUGH = re.compile(r'\b(?:through|with|via|using)\s+(?:(?!(?:and|or|but|nor|not|no|never|after|before|of|than|'
                          r'then|instead|rather|without|following|once|until|while|when|from|to|into|at|in|on|by|for|'
                          r'during)\b)[a-z-]+\s+){0,2}$', re.I | re.A)
NOT_DONE_THROUGH = re.compile(r'\b(?:not|never|no|rather\s+than|instead\s+of|in\s+lieu\s+of|as\s+opposed\s+to)\s+$',
                              re.I | re.A)


ACT_PATTERNS = dict(ACTS)  # the reader's own act mentions, by kind


def _done_through(service: DocumentedService, passage: str, kind: str) -> bool:
    """Whether a passage states its act (of ``kind``) done through or with ``service``: after the act's own mention,
    its family's name or an instrument of its family, governed by an instrumental preposition no negation or replacement
    governs (DONE_THROUGH: "band ligation of two columns through the flexible sigmoidoscope"). A passage that only names
    the service - to say the act was not done through it, or was done after it - places nothing in it (refutation gi2
    attr-F4)."""
    act = ACT_PATTERNS[kind].search(passage) if kind in ACT_PATTERNS else None
    if act is None:
        return False
    names = [m.start() for family, _, pattern in SERVICES if family == service.family
             for m in pattern.finditer(passage, act.end())]
    names += [m.start() for m in INSTRUMENTS.finditer(passage, act.end())
              if next((family for name, family in INSTRUMENT_FAMILY if name in m.group(0).lower()), '') == service.family]
    for start in names:
        lead = passage[max(act.end(), start - 120):start]
        prep = DONE_THROUGH.search(lead)
        if prep is not None and not NOT_DONE_THROUGH.search(lead, 0, prep.start()):
            return True
    return False


def placed_check(m: Match, inventory: ServiceInventory, family_label: str) -> Optional[Check]:
    """Where the document places the act a code accounts for when no service of the code's family is documented
    (elsewhere): in another documented service, said only where the act's own passage states it done through or with
    that service or its instrument ("band ligation of two columns through the flexible sigmoidoscope": _done_through) -
    an act the reader merely gave to the one service a document names, or whose passage names the service only to say
    it was not used ("not through the flexible sigmoidoscope", "after withdrawal of the colonoscope"), is not said to be
    in it. A warning for the reviewer, who decides which code accounts for the act: nothing is added and no alternative
    is promoted. None when no passage states the act done through or with the service."""
    places, seen = [], set()
    for act in m.acts:
        service = inventory.service(act.service)
        span = next((ev for ev in act.evidence if _done_through(service, ev.text, act.kind)), None) if service else None
        if span is not None and service.id not in seen:
            seen.add(service.id)
            places.append(f'the {act_label(act.kind)} in the documented {service_label(service)} ({service.status}): '
                          f'{quote(span, 140)}')
    if not places:
        return None
    return Check('service.act_elsewhere', 'Coded act documented in another service', 'warn',
                 f'No service of this code\'s family ({family_label}) is documented, and the document places the act it '
                 f'accounts for in another service: {"; ".join(places[:2])}. Which code accounts for that act is the '
                 'reviewer\'s decision; no code is added and no alternative is promoted.', INVENTORY_SOURCE)


# --- the encounter -------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Unresolved:
    service: str
    family: str
    act: str  # '' when the whole service has no proposal
    label: str
    evidence: tuple[Span, ...]
    reason: str  # no_proposal | not_covered | unsupported | coverage_unknown


@dataclass(frozen=True)
class Bundled:
    service: str
    act: str
    label: str
    why: str


def _bundled(service: DocumentedService, act: Act) -> Optional[str]:
    family = catalogue.entry(service.family)
    if act.kind == 'clip':
        return dict(catalogue.COMMON_BUNDLED)['clip']
    if act.kind == 'cannulation':
        return dict(catalogue.COMMON_BUNDLED)['cannulation']
    if act.kind == 'biopsy' and act.lesion and any(
            a.lesion == act.lesion and a.kind in REMOVAL_KINDS and a.status == 'performed' for a in service.acts):
        return dict(catalogue.COMMON_BUNDLED)['biopsy_of_removed_lesion']
    if act.kind == 'injection' and any(a.kind in ('emr', 'esd') and a.status == 'performed'
                                       and (not act.lesion or a.lesion == act.lesion) and _sites_agree(act, a)
                                       for a in service.acts):
        return dict(catalogue.COMMON_BUNDLED)['lift_injection']
    if act.kind in ('snare', 'hot_biopsy') and any(
            a.kind in ('emr', 'esd') and a.status == 'performed' and _one_resection(act, a) for a in service.acts):
        # Harness repair 2026-11-05, refutation multi-1: "resected by EMR with a hot snare" reads an EMR and a snare at
        # one lesion; the snare is the resection's own technique, never a second removal charged beside it. A snare at
        # another lesion keeps its own code (and its distinct-lesion consideration).
        return dict(catalogue.COMMON_BUNDLED)['resection_technique']
    if family is not None:
        for kind, why in family.bundled:
            if kind == act.kind:
                return why
    return None


def _sites_agree(one: Act, other: Act) -> bool:
    """Whether two acts' own sites can be one place: either names none, or they share one (refutation round 2, cost-4:
    a steroid injection into a rectal stricture is never a cecal EMR's lift)."""
    return not one.anatomy or not other.anatomy or bool(set(one.anatomy) & set(other.anatomy))


def _one_resection(removal: Act, resection: Act) -> bool:
    """Whether ``removal`` (a snare or hot-forceps act) is the technique of ``resection`` (an EMR or ESD act): both at
    one recorded lesion, the removal's own sites agreeing with the resection's; or, neither at a lesion, both read in
    one clause naming one site at most. Refutation round 2, over-4: a snare of another lesion is never the EMR's - "The
    sigmoid polyp was removed with a cold snare." after a lesion's EMR, "EMR ... in the ascending colon, and cold snare
    polypectomy ... in the sigmoid colon"."""
    if removal.lesion or resection.lesion:
        return removal.lesion == resection.lesion and _sites_agree(removal, resection)
    shared = any(_overlaps(e.start, e.end, f.start, f.end) for e in removal.evidence for f in resection.evidence)
    return shared and len(set(removal.anatomy) | set(resection.anatomy)) <= 1


def _needle_sampling(service: DocumentedService, act: Act) -> Optional[Act]:
    """A biopsy at an endoscopic ultrasound taken with the needle - or, with no technique stated, of the lesion the
    service's own fine-needle sampling samples - is that sampling: returned as the fna act it is reconciled as, never
    a forceps biopsy (refutation r1, report-0: it had been bundled as "read under the upper GI family"). None otherwise."""
    if service.family != 'gi.eus' or act.kind != 'biopsy':
        return None
    sampled = bool(act.lesion) and not act.technique and any(
        a.kind == 'fna' and a.status == 'performed' and a.lesion == act.lesion for a in service.acts)
    return replace(act, kind='fna') if 'needle' in act.technique or sampled else None


# The reader's anatomy vocabulary (canonical name -> region) and the regions of the GI lumen, where an endoscope's
# forceps act: what a READ_UNDER rule reads an act's site and its examination's sites with - one reading with the
# inventory's, which reads an endoscopic ultrasound's tract with it (studio.gi.services: REGION_OF, LUMEN).
_act_sites, _exam_sites = act_regions, examined_regions


def _read_under(inventory: ServiceInventory, service: DocumentedService, act: Act) -> Optional[str]:
    """For an act a profile rule reads under ANOTHER family (catalogue.READ_UNDER): '' when the rule holds, else why
    nothing of this encounter reads it. None for any other act. The other family reads the act only where the document
    places it at one of that family's sites (its anatomy and its lesion's; none named is not a place elsewhere) during
    an examination of that family's tract - every GI-lumen site the service documents is one of them, and it documents
    one (the ec5 skeptic: a rectal EUS's forceps biopsy of the rectal mass was "read under the upper GI family" beside an
    upper endoscopy's own gastric biopsy) - and only when a service of that family done at this encounter documents
    such an act (refutation r1, report-0)."""
    under = catalogue.READ_UNDER.get((service.family, act.kind))
    if under is None:
        return None
    family, label, tract, regions = under
    examined = _exam_sites(service) & LUMEN
    if not (_act_sites(service, act) <= set(regions) and examined and examined <= set(regions)):
        return (f'the document does not place it at an {tract} site of an {tract} examination, so no {label} of this '
                'encounter reads it')
    reads = any(other.id != service.id and other.family == family and other.status in ('performed', 'incomplete')
                and any(a.kind == act.kind and a.status == 'performed' for a in other.acts)
                for other in inventory.services)
    return '' if reads else f'no {label} documented at this encounter reads it'


def includes_through(inventory: ServiceInventory, service: DocumentedService, code: str, family: str) -> bool:
    """Whether ``code``, of ``family``, includes ``service``'s examination through the service it is read as part of
    (``included_in``: an EGD as the endoscopic portion of an EUS): that service is of ``family`` and the code includes
    the examination (catalogue.includes_examination: an EGD-with-EUS code). The one test of the inclusion rule - read by
    this reconciliation (inclusion_asks_no_code), by services.unproposed and the documented services the assessment
    records (engine._included_by), and by the bounded second review's merge (engine._second_review)."""
    including = inventory.service(service.included_in) if service.included_in else None
    return (including is not None and including.family == family
            and catalogue.includes_examination(code, service.kind))


def inclusion_asks_no_code(inventory: ServiceInventory, service: DocumentedService,
                           selected: Sequence[tuple[str, str]]) -> bool:
    """Whether ``service``, read as included in another service of this encounter (``included_in``: an EGD as the
    endoscopic portion of an EUS), asks for no code of its own beside ``selected`` = (code, family) of the selected,
    non-excluded proposals: while that other service has no selected code (it is listed itself, and the code it asks
    for includes the examination), or when one of its selected codes includes the examination (includes_through). A
    selected code of it that includes no such examination - a sigmoidoscopy, colonoscopy or esophagoscopy EUS code
    never includes an upper endoscopy - accounts for nothing of this service, which is then a service without a proposal
    like any other (refutation p2, reports2:0)."""
    including = inventory.service(service.included_in) if service.included_in else None
    if including is None:
        return False
    codes = [code for code, family in selected if family == including.family]
    return not codes or any(includes_through(inventory, service, code, including.family) for code in codes)


def reconcile(inventory: ServiceInventory, selected: Sequence[tuple[str, str]], procedure_day: bool = False
              ) -> tuple[list[Unresolved], list[Bundled], dict[str, list[str]]]:
    """(unresolved items, bundled acts, covered: service id -> codes) for ``selected`` = (code, family) of the selected,
    non-excluded proposals. ``procedure_day``: the engine's same-day E/M reading (a procedure the inventory does not
    read - another GI service, a possibly performed one, a selected procedural code - is one too)."""
    unresolved: list[Unresolved] = []
    bundled: list[Bundled] = []
    covered: dict[str, list[str]] = {}
    for service in inventory.services:
        if service.status not in ('performed', 'incomplete'):
            continue
        entry = catalogue.entry(service.family)
        if entry is None or entry.support != catalogue.SUPPORTED:
            continue
        codes = [code for code, family in selected if family == service.family]
        covered[service.id] = codes
        if not codes and inclusion_asks_no_code(inventory, service, selected):
            pass  # the including service's code covers the examination (an EGD inside an EUS); its own acts still count
        elif not codes:
            if service.family == 'gi.office_em' and (procedure_day or any(
                    s.status in ('performed', 'incomplete') and s.family != service.family for s in inventory.services)):
                continue  # never push an office visit beside a same-day procedure
            unresolved.append(Unresolved(service.id, service.family, '', f'{service_label(service)} '
                                         f'(documented as {service.status}) has no supported proposal',
                                         tuple(service.evidence[:2]), 'no_proposal'))
            for act in service.acts:  # an act no code profile covers is named whatever the service's proposals
                if act.status == 'performed' and act.role in ('physician', 'unknown') \
                        and act.kind in catalogue.UNSUPPORTED_ACTS:
                    unresolved.append(Unresolved(service.id, service.family, act.kind,
                                                 f'{describe_act(service, act)}: no supported code profile',
                                                 act.evidence[:1], 'unsupported'))
            continue
        profiles = [catalogue.code_profile(code) for code in codes]
        unknown = any(p is None or p.family != service.family for p in profiles)
        covers = {kind for p in profiles if p is not None and p.family == service.family for kind in p.covers}
        seen_acts: set[tuple] = set()
        for act in service.acts:
            if ((act.status == 'uncertain' and not any(c.startswith(HYPOTHETICAL_CUE) for c in act.cues))
                    or (act.status == 'negated' and any(FAILED_ATTEMPT.search(ev.text) for ev in act.evidence))) \
                    and act.role in OWN_ROLES \
                    and act.kind in entry.acts \
                    and act.kind not in catalogue.UNSUPPORTED_ACTS and _bundled(service, act) is None \
                    and not catalogue.family_codes_act(service.family, act.kind):
                # Harness repair 2026-11-05, refutation compl-1: "Decompression of the stomach was attempted but
                # failed." - an act no code of the family accounts for is listed whatever its outcome (the directive:
                # never hide a therapeutic or failed decompression to clear completeness)
                unresolved.append(Unresolved(service.id, service.family, act.kind,
                                             f'{describe_act(service, act)} in the {service_label(service)}, '
                                             'attempted or in doubt: no code profile of this service accounts for it',
                                             act.evidence[:2], 'unsupported'))
                continue
            if act.status != 'performed' or act.role not in OWN_ROLES:
                continue
            act = _needle_sampling(service, act) or act
            key = (act.kind, act.lesion or ','.join(act.anatomy))
            if key in seen_acts:
                continue
            seen_acts.add(key)
            if act.kind in catalogue.UNSUPPORTED_ACTS:
                unresolved.append(Unresolved(service.id, service.family, act.kind,
                                             f'{describe_act(service, act)}: no supported code profile',
                                             act.evidence[:1], 'unsupported'))
                continue
            why = _bundled(service, act)
            missing = _read_under(inventory, service, act) if why and why == dict(entry.bundled).get(act.kind) else None
            if missing:
                # refutation r1, report-0 (and the ec5 skeptic): a rule that reads the act under another family holds
                # only for an act that family could read (its site, its examination's tract) when a service of that
                # family documents such an act; otherwise no code of this encounter can account for it - listed for
                # the reviewer (never bundled, never sent for a second review: these codes cannot account for it)
                unresolved.append(Unresolved(service.id, service.family, act.kind,
                                             f'{describe_act(service, act)} in the {service_label(service)}: '
                                             f'{missing}, and no code profile of this service accounts for it',
                                             act.evidence[:2], 'unsupported'))
                continue
            if why:
                bundled.append(Bundled(service.id, act.kind, describe_act(service, act), why))
                continue
            if act.kind not in entry.acts:
                continue
            if not catalogue.family_codes_act(service.family, act.kind):
                # Harness repair 2026-11-05 (stage 6): an act the family lists that no code of the family accounts for
                # (catalogue.family_codes_act: a stomach decompression in an upper endoscopy) is listed for the
                # reviewer as one no code of this service accounts for - routine, therapeutic or failed alike, for
                # nothing here reads which it was - never bundled, never sent for a second review (SECOND_REVIEW_REASONS:
                # no code it could select accounts for it), and never dropped: it keeps coding completeness open
                unresolved.append(Unresolved(service.id, service.family, act.kind,
                                             f'{describe_act(service, act)} in the {service_label(service)}: no code '
                                             'profile of this service accounts for it', act.evidence[:2],
                                             'unsupported'))
                continue
            if act.kind in covers or (act.kind in ('tattoo', 'injection') and covers & {'tattoo', 'injection'}):
                continue
            if any(other.kind in covers for other in service.acts if other.status == 'performed'
                   and other.kind == act.kind):
                continue
            unresolved.append(Unresolved(service.id, service.family, act.kind,
                                         f'{describe_act(service, act)} in the {service_label(service)}',
                                         act.evidence[:2], 'coverage_unknown' if unknown else 'not_covered'))
    # One unresolved entry per (service, act kind): a second biopsy site of the same service is the same code.
    merged: dict[tuple, Unresolved] = {}
    for item in unresolved:
        key = (item.service, item.act)
        if key not in merged:
            merged[key] = item
    return list(merged.values()), bundled, covered


def conflict_clarification(conflict: Conflict, service: DocumentedService) -> ClarificationSpec:
    sides = '; '.join(f'{side.role} entry: {side.status} ({quote(side.evidence[0], 140)})' for side in conflict.sides
                      if side.evidence)
    what = act_label(conflict.subject)
    return ClarificationSpec(
        scope='service', fact=f'conflict:{conflict.subject}', family=service.family,
        question=f'The record conflicts on the {what} in the {service_label(service)}: which statement is correct for '
                 'this encounter?',
        reason=f'{sides}. Both statements are kept and neither is chosen; a code for the {what} is not reconciled '
               'until this is answered.')


def documentation_clarifications(service: DocumentedService, context=None) -> list[ClarificationSpec]:
    """Every materially necessary question for one documented service, asked together. A fact the visit lacks because
    a member's encounter metadata conflicts with the document is asked as that conflict, both sides named
    (context.is_member_conflict), never as undocumented; so is a fact the document itself states twice."""
    entry = catalogue.entry(service.family)
    if entry is None or service.status not in ('performed', 'incomplete', 'uncertain'):
        return []
    questions = dict(entry.questions)
    out: list[ClarificationSpec] = []
    if service.family == 'gi.office_em':
        for fact in service.uncertainty:
            if fact in questions:
                held = (context or {}).get(fact)
                if is_member_conflict(held):
                    reason = f'The {fact.replace("_", " ")} is in conflict. {held.note}'
                elif getattr(held, 'origin', None) == 'conflict':
                    # refutation r1, context-6: values that conflict within the document are a conflict, quoted as the
                    # E/M proposal's own question quotes them (checks.fact_clarifications), never "does not state"
                    reason = (f'The document gives conflicting values for the {checks.fact_label(fact)}: '
                              f'{checks.conflict_values(held)}.')
                else:
                    reason = f'The documented office / outpatient visit does not state its {fact.replace("_", " ")}.'
                out.append(ClarificationSpec(scope='service', fact=fact, family=service.family,
                                             question=questions[fact], reason=reason))
        return out
    if entry.support == catalogue.SUPPORTED and 'extent' in questions and not service.extent \
            and service.completion == 'unknown' and service.family in ('gi.egd', 'gi.colonoscopy', 'gi.flex_sig',
                                                                       'gi.enteroscopy'):
        out.append(ClarificationSpec(scope='service', fact='extent', family=service.family,
                                     question=questions['extent'],
                                     reason=f'The documented {service_label(service)} does not state how far the '
                                            'instrument was advanced or whether the examination was completed.'))
    return out


def uncounted(inventory: ServiceInventory, unresolved: Sequence[Unresolved], covered: dict[str, list[str]]
              ) -> list[DocumentedService]:
    """The documented services performed today that no selected proposal accounts for and that the reconciliation
    neither lists as unresolved nor reads as included in another: an office visit beside a same-day procedure, which is
    never pushed as unresolved (nor sent for a second review), is still a documented service without a proposal, so
    coding completeness names it and never says every documented service has one (refutation 7c8, reports-1)."""
    listed = {u.service for u in unresolved}
    return [s for s in inventory.services if s.status in ('performed', 'incomplete') and s.id in covered
            and not covered[s.id] and not s.included_in and s.id not in listed]


def uncounted_label(service: DocumentedService) -> str:
    """An office visit is not listed on a procedure day the engine sees: a procedure done today, or one whose
    performance today is not established - so the label never says the procedure was done."""
    return service_label(service) + (' beside a procedure done or possibly done the same day'
                                     if service.family == 'gi.office_em' else '')


def completeness(inventory: ServiceInventory, unresolved: Sequence[Unresolved], open_questions: int,
                 provider_ok: bool, unestablished: int = 0, not_listed: Sequence[DocumentedService] = ()) -> dict:
    """The encounter's coding completeness at assessment time (review decisions are added by review.readiness).
    ``unestablished``: documented services not established as performed that no proposal reads (refutation r1, report
    lens: "EUS: Normal pancreas" beside a coded colonoscopy had let it say every documented service has a proposal).
    ``not_listed``: documented services performed with no proposal that are not listed as unresolved (uncounted)."""
    reasons = []
    if not provider_ok:
        reasons.append('the provider response was not available')
    if unresolved:
        reasons.append(f'{len(unresolved)} documented service{"s" if len(unresolved) != 1 else ""} or act'
                       f'{"s" if len(unresolved) != 1 else ""} without a supported proposal')
    if unestablished:
        reasons.append(f'{unestablished} documented service{"s" if unestablished != 1 else ""} not established as '
                       'performed and read by no proposal')
    if not_listed:
        reasons.append(f'{len(not_listed)} documented service{"s" if len(not_listed) != 1 else ""} without a supported '
                       'proposal and not listed as unresolved: ' + ', '.join(uncounted_label(s) for s in not_listed))
    if inventory.conflicts:
        reasons.append(f'{len(inventory.conflicts)} conflict{"s" if len(inventory.conflicts) != 1 else ""} in the record')
    if open_questions:
        reasons.append(f'{open_questions} open question{"s" if open_questions != 1 else ""}')
    if inventory.problems:
        reasons.append('the documented-service reading reported a problem')
    performed = [s for s in inventory.services if s.status in ('performed', 'incomplete')]
    return {
        'state': 'incomplete' if reasons else 'complete_pending_review',
        'reasons': reasons,
        'services': len(performed),
        'unresolved': len(unresolved),
        'conflicts': len(inventory.conflicts),
        'statement': ('Coding for this encounter is incomplete: ' + '; '.join(reasons) + '.') if reasons else (
            'Every documented service has a proposal to review. This is not verified coding: code-set membership '
            'and NCCI edits are not verified, and each proposal still needs a reviewer.'),
    }


def inventory_check(inventory: ServiceInventory, problems: Sequence[str]) -> Check:
    performed = [s for s in inventory.services if s.status in ('performed', 'incomplete')]
    others = [s for s in inventory.services if s.status not in ('performed', 'incomplete')]
    names = ', '.join(f'{service_label(s)} ({s.status}' + (f', included in {service_label(inventory.service(s.included_in))}'
                                                         if s.included_in and inventory.service(s.included_in) else '')
                      + ')' for s in performed) or 'none'
    detail = f'Documented as done on this encounter: {names}.'
    if others:
        detail += ' Documented but not as done today: ' + ', '.join(f'{service_label(s)} ({s.status})' for s in others) + '.'
    if inventory.attributions:
        detail += (' Attributed to another provider: ' + ', '.join(a.role for a in inventory.attributions)
                   + ' (never coded for the performing physician).')
    all_problems = list(inventory.problems) + list(problems)
    if all_problems:
        return Check('services.inventory', 'Documented services', 'warn',
                     detail + ' Problems: ' + ' '.join(all_problems), INVENTORY_SOURCE)
    return Check('services.inventory', 'Documented services', 'info',
                 detail + ' The reading is advisory: it reads declared wording and can miss wording it does not '
                          'recognise.', INVENTORY_SOURCE)


def unresolved_check(unresolved: Sequence[Unresolved], problems: Sequence[str] = (),
                     not_listed: Sequence[DocumentedService] = ()) -> Check:
    """``problems``: the reading problems the inventory recorded (a cap, a sentence read in part). Such a reading speaks
    only for what it read, which can be part of a service it read: the check then never claims every documented act
    (refutation r1, report-8: it passed with that claim beside an unread act of a service it had read).
    ``not_listed``: the documented services performed with no supported proposal that the reconciliation does not list
    as unresolved (uncounted: an office visit beside a procedure done or possibly done the same day). The check names
    them, as coding completeness and UNRESOLVED do, and never passes beside one nor says every act has a proposal
    (skeptic of refutation 7c8 reports-1: it passed with "Every documented act ... has a selected proposal" beside an
    office visit no proposal accounts for, and read in part it said so "among what was read" of a visit it had read)."""
    partial = (' The documented-service reading reported a problem (see services.inventory), so a service or act in '
               'the part it did not read is not covered by this check.') if problems else ''
    one = len(not_listed) == 1
    named = (f'{len(not_listed)} documented service{"" if one else "s"} {"has" if one else "have"} no supported '
             f'proposal and {"is" if one else "are"} not listed as unresolved: '
             + ', '.join(uncounted_label(s) for s in not_listed)
             + f'; no proposal accounts for {"it" if one else "them"}.') if not_listed else ''
    if not unresolved and named:
        return Check('services.unresolved', 'Documented services without a supported proposal', 'warn',
                     ('Among what was read, ' if partial else '') + named + ' Every other documented act that the '
                     'coverage catalogue reconciles has a selected proposal, or is not separately reported under a '
                     'profile rule.' + (partial or ' Wording the reader does not recognise is not covered by this '
                                                   'check.'), SOURCE)
    if not unresolved and partial:
        return Check('services.unresolved', 'Documented services without a supported proposal', 'warn',
                     'Among what was read, every documented act that the coverage catalogue reconciles has a selected '
                     'proposal, or is not separately reported under a profile rule.' + partial, SOURCE)
    if not unresolved:
        return Check('services.unresolved', 'Documented services without a supported proposal', 'pass',
                     'Every documented act that the coverage catalogue reconciles has a selected proposal, or is not '
                     'separately reported under a profile rule. Wording the reader does not recognise is not '
                     'covered by this check.', SOURCE)
    items = '; '.join(f'{u.label}' + (f' ({quote(u.evidence[0], 100)})' if u.evidence else '') for u in unresolved[:6])
    more = f' and {len(unresolved) - 6} more' if len(unresolved) > 6 else ''
    return Check('services.unresolved', 'Documented services without a supported proposal', 'warn',
                 f'Unresolved: {items}{more}. No code is added for them and no alternative is promoted.'
                 + (f' {named}' if named else '') + partial, SOURCE)


def conflicts_check(inventory: ServiceInventory) -> Check:
    """A reading that recorded a problem (the inventory's problems: a cap, a sentence read in part) speaks only for what
    it read: the check then never states that no act is stated both ways (the ec5 skeptic of report-8: it passed with
    that claim beside a denial in the unread tail of a sentence, as unresolved_check had before)."""
    partial = (' The documented-service reading reported a problem (see services.inventory), so an act in the part it '
               'did not read is not covered by this check.') if inventory.problems else ''
    if not inventory.conflicts and partial:
        return Check('services.conflicts', 'Conflicting statements', 'warn',
                     'Among what was read, no act is stated both as done and as not done for the same service and '
                     'site.' + partial, INVENTORY_SOURCE)
    if not inventory.conflicts:
        return Check('services.conflicts', 'Conflicting statements', 'pass',
                     'No act is stated both as done and as not done for the same service and site.', INVENTORY_SOURCE)
    items = []
    for c in inventory.conflicts[:4]:
        service = inventory.service(c.service)
        sides = ' vs '.join(f'{side.role} {side.status}' for side in c.sides)
        items.append(f'{act_label(c.subject)} in the {service_label(service) if service else c.service}: {sides}')
    return Check('services.conflicts', 'Conflicting statements', 'warn',
                 'Kept with both sides, never resolved silently: ' + '; '.join(items) + '.' + partial, INVENTORY_SOURCE)


def attribution_check(inventory: ServiceInventory, selected_codes: Sequence[str]) -> Optional[Check]:
    """A provider-selected code of a service the document attributes to another provider."""
    roles = {a.role for a in inventory.attributions}
    flagged = []
    for code in selected_codes:
        if not (len(code) == 5 and code.isdigit()):
            continue
        if 'anesthesia' in roles and '00100' <= code <= '01999':
            flagged.append(f'{code} (anesthesia)')
        elif 'pathology' in roles and '88000' <= code <= '88399':
            flagged.append(f'{code} (pathology)')
        elif 'radiology' in roles and code in ('74328', '74329', '74330', '76975'):
            flagged.append(f'{code} (radiology)')
    if not flagged:
        return None
    return Check('services.attribution', 'Another provider\'s service', 'warn',
                 'The document attributes these services to another provider, so they are not the performing '
                 'physician\'s: ' + ', '.join(flagged) + '.', INVENTORY_SOURCE)
