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

from dataclasses import dataclass
from typing import Optional, Sequence

from studio.gi import catalogue
from studio.gi.context import is_member_conflict
from studio.gi.services import (ROUTING_CONTRARY_CUE, ROUTING_DOUBT_CUE, SERVICES, Act, Conflict, DocumentedService,
                                 ServiceInventory)
from studio.types import Check, ClarificationSpec, EvidenceSpan, Span

SOURCE = f'cpt-studio:{catalogue.CATALOGUE_VERSION}'
INVENTORY_SOURCE = 'cpt-studio:gi-services@1'
REMOVAL_KINDS = ('snare', 'emr', 'hot_biopsy', 'esd')
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


def service_label(service: DocumentedService) -> str:
    return SERVICE_LABELS.get(service.kind, service.kind.replace('_', ' '))


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
    if done:
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


def _study_named(m: Match, span: EvidenceSpan, today) -> bool:
    """A physiology study whose coded act is the study itself (STUDY_ACTS): a passage that names this service and
    states something of this encounter (``today``: not in a plan, history or indication section, not about another
    time, planned, denied or cancelled - "Esophageal manometry showed normal peristalsis.") shows the study, as a
    statement of this visit shows an office visit."""
    study = STUDY_ACTS.get(m.service.family)
    if today is None or study is None or not m.acts or any(a.kind != study for a in m.acts):
        return False
    named = any(family == m.service.family and pattern.search(span.text) for family, _, pattern in SERVICES)
    return named and today(span)


def support(m: Match, evidence: Sequence[EvidenceSpan], current=None, today=None) -> Support:
    """How ``evidence`` (the provider's exact passages) relates to the documented act. For an office visit the act is
    the visit itself: a passage supports it when it is a statement of this visit - not one ``current`` reads as about
    another time ("Last seen by Dr. Ramos on 2026-03-02", a planned procedure). So for a study that is its own act: a
    statement of this encounter naming the study supports it (_study_named)."""
    targets = _targets(m)
    supporting, unrelated = [], []
    for index, span in enumerate(evidence):
        if m.service.family == 'gi.office_em' and current is not None:
            (supporting if current(span) else unrelated).append(index)
        elif any(_overlaps(span.start, span.end, t.start, t.end) for t in targets) or _study_named(m, span, today):
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
                                       and (not act.lesion or a.lesion == act.lesion) for a in service.acts):
        return dict(catalogue.COMMON_BUNDLED)['lift_injection']
    if family is not None:
        for kind, why in family.bundled:
            if kind == act.kind:
                return why
    return None


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
        if not codes and service.included_in:
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
            if act.status != 'performed' or act.role not in ('physician', 'unknown'):
                continue
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
            if why:
                bundled.append(Bundled(service.id, act.kind, describe_act(service, act), why))
                continue
            if act.kind not in entry.acts:
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
    (context.is_member_conflict), never as undocumented."""
    entry = catalogue.entry(service.family)
    if entry is None or service.status not in ('performed', 'incomplete', 'uncertain'):
        return []
    questions = dict(entry.questions)
    out: list[ClarificationSpec] = []
    if service.family == 'gi.office_em':
        for fact in service.uncertainty:
            if fact in questions:
                held = (context or {}).get(fact)
                reason = (f'The {fact.replace("_", " ")} is in conflict. {held.note}' if is_member_conflict(held)
                          else f'The documented office / outpatient visit does not state its {fact.replace("_", " ")}.')
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


def completeness(inventory: ServiceInventory, unresolved: Sequence[Unresolved], open_questions: int,
                 provider_ok: bool) -> dict:
    """The encounter's coding completeness at assessment time (review decisions are added by review.readiness)."""
    reasons = []
    if not provider_ok:
        reasons.append('the provider response was not available')
    if unresolved:
        reasons.append(f'{len(unresolved)} documented service{"s" if len(unresolved) != 1 else ""} or act'
                       f'{"s" if len(unresolved) != 1 else ""} without a supported proposal')
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


def unresolved_check(unresolved: Sequence[Unresolved]) -> Check:
    if not unresolved:
        return Check('services.unresolved', 'Documented services without a supported proposal', 'pass',
                     'Every documented act that the coverage catalogue reconciles has a selected proposal, or is not '
                     'separately reported under a profile rule. Wording the reader does not recognise is not '
                     'covered by this check.', SOURCE)
    items = '; '.join(f'{u.label}' + (f' ({quote(u.evidence[0], 100)})' if u.evidence else '') for u in unresolved[:6])
    more = f' and {len(unresolved) - 6} more' if len(unresolved) > 6 else ''
    return Check('services.unresolved', 'Documented services without a supported proposal', 'warn',
                 f'Unresolved: {items}{more}. No code is added for them and no alternative is promoted.', SOURCE)


def conflicts_check(inventory: ServiceInventory) -> Check:
    if not inventory.conflicts:
        return Check('services.conflicts', 'Conflicting statements', 'pass',
                     'No act is stated both as done and as not done for the same service and site.', INVENTORY_SOURCE)
    items = []
    for c in inventory.conflicts[:4]:
        service = inventory.service(c.service)
        sides = ' vs '.join(f'{side.role} {side.status}' for side in c.sides)
        items.append(f'{act_label(c.subject)} in the {service_label(service) if service else c.service}: {sides}')
    return Check('services.conflicts', 'Conflicting statements', 'warn',
                 'Kept with both sides, never resolved silently: ' + '; '.join(items) + '.', INVENTORY_SOURCE)


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
