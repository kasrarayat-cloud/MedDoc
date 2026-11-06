"""A question's identity, its passages and the fact it names (completion repair, 2026-11-06: U10, U11; contract C5).

One implementation, read by every reader of a member's answer: the details rows a member answers (studio/answers.py),
the engine that applies the answers as an input (engine._MemberAnswers), and the read-time overlay's binding
(review.bound_answers). Pure: no database, no clock, no provider.

**A question** is one clarification CPT Studio asks: its scope, family, fact, the code it is asked of ('' for a
documented service's question), CPT Studio's own question and reason, and the passages it concerns (``passages``). A
member's answer binds to the question it answered (``fingerprint`` of every instance of that (code, family, fact) the
assessment asked, in the form ``FORM`` presents them). A later assessment applies the answer only where it asks the
same question; an answer to a question no longer asked, or asked differently, is kept and shown as an earlier answer,
never applied.

**The form** is how a question is shown to the member who answers it. ``FORM`` shows each question's passages beside the
fact it names. An answer recorded before answers carried a fingerprint (``MemberAnswer.question`` '') was given to the
earlier form: a fixed prompt with no passage. No question of this form is that question, so such an answer is never
applied, and is shown as an earlier answer (the rule for stored answers; API.md "Completion repair (2026-11-06):
questions, answers and their recompute").
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional

from studio.types import sha256_json

FORM = 'cpt-studio-question@1'
MAX_PASSAGES = 4  # a question shows a short list: its act's own passages, the code's own, then CPT Studio's located
PER_SOURCE = 2  # at most this many from each, so the code's own passage and CPT Studio's located one are both shown
MIN_PASSAGE_CHARACTERS = 8  # non-space characters: a shorter cited fragment shows nothing a member can read it by
MIN_PASSAGE_WORDS = 2  # and a single word ("Multiple") is a fragment of a passage, never one
# The member answers a question takes (MemberAnswer.VALUES): each says the detail is unavailable from the document,
# so the code it is asked of is excluded until the answer is withdrawn. No value confirms a clinical fact (decision D7).
NOT_DOCUMENTED, CANNOT_CONFIRM = 'not_documented', 'cannot_confirm'
UNAVAILABLE = (NOT_DOCUMENTED, CANNOT_CONFIRM)
# Why an answer given to this revision is not applied to an assessment (kept, and shown as an earlier answer).
NO_LONGER_ASKED, ASKED_DIFFERENTLY, EARLIER_FORM = 'no_longer_asked', 'asked_differently', 'earlier_form'

# The fact a question names, in plain words: what CPT Studio could not confirm from the document. A fact this table
# does not name is worded from its own name, never left unnamed.
MISSING = {
    'performed_status': 'that this procedure was performed on the date of service',
    'extent': 'how far the instrument was advanced',
    'completion': 'whether the examination was completed as intended',
    'target': 'what was examined, and what was sampled',
    'cannulation': 'whether the intended duct was cannulated',
    'interpretation': 'who interpreted the study',
    'method': 'which testing method was used, and for how long',
    'route': 'how the tube was placed or replaced',
    'base_included': ('whether this diagnostic examination is reported separately from the other procedures on this '
                      'date'),
    'separate_em': 'a significant, separately identifiable visit beside the procedure',
    'em_basis': 'what supports the visit level (total time on the date of service, or medical decision making)',
    'units': 'how many units were performed',
    'documentation': 'the documentation this reinstated code needs before it can be approved',
    'setting': 'where this service was provided',
    'patient_status': 'whether the patient is new or established to this clinician and group',
    'billing_context': 'whether this is billed as a professional claim or a facility claim',
    'service_date': 'the date of service',
    'competing_codes': 'which of the codes proposed for the same documented act the documentation supports',
}


def missing(fact: str, act: str = '') -> str:
    """The fact ``fact`` names, in plain words; a conflict about an act (``conflict:<act>``) names which statement about
    that act is right (``act``: its label)."""
    if fact.startswith('conflict:'):
        return f'which statement about the {act or fact.split(":", 1)[1].replace("_", " ")} is right for this date'
    return MISSING.get(fact, f'the {fact.replace("_", " ")}')


@dataclass(frozen=True)
class MemberAnswerInput:
    """A member's standing answer as the engine reads it (engine.assess ``member_answers``): the question it answered -
    its scope, code ('' for a documented service's question), family, fact and that question's fingerprint (''
    for an answer recorded before answers carried one) - its value (UNAVAILABLE) and its id. It is what a member said,
    never clinical documentation: it excludes the code whose question it answers and approves nothing."""
    code: str
    family: str
    fact: str
    value: str
    question: str
    answer_id: str


ANSWERED_SUPPORT = 'answered'  # support[...] of a code the engine excluded by a member's answer: {fact, value, answers}


def answered_away(proposal) -> bool:
    """Whether ``proposal`` - an engine ProposalAssessment, a stored Proposal or the review overlay's Stored row - is a
    code the engine excluded because a member's answer left a detail it needs unavailable (engine._MemberAnswers): its
    support records the answer. Such a code still holds every code its presence held (session decision (e) of
    2026-11-03: a member's answer never releases a code); only a reviewer's recorded decision does
    (studio.validation.review_view), and it needs no decision of its own."""
    support = getattr(proposal, 'support', None)
    marker = support.get(ANSWERED_SUPPORT) if isinstance(support, Mapping) else None
    return (isinstance(marker, Mapping) and marker.get('value') in UNAVAILABLE
            and isinstance(marker.get('fact'), str) and bool(marker.get('fact')))


def _field(item, name):
    return item.get(name) if isinstance(item, Mapping) else getattr(item, name, None)


def _span(item) -> Optional[tuple]:
    """(context_index, start, end, text, exact) of an evidence span - an engine EvidenceSpan, or its stored form - or
    None when it is not one."""
    start, end, text = _field(item, 'start'), _field(item, 'end'), _field(item, 'text')
    if type(start) is not int or type(end) is not int or not isinstance(text, str) or not 0 <= start < end:
        return None
    index = _field(item, 'context_index')
    return (index if type(index) is int else 0, start, end, text, _field(item, 'exact'))


def _readable(text: str) -> bool:
    return (sum(1 for ch in text if not ch.isspace()) >= MIN_PASSAGE_CHARACTERS
            and len(text.split()) >= MIN_PASSAGE_WORDS)


def acts_of(services) -> dict:
    """{act id: act} of a documented-service reading's JSON form (Assessment.services; review.act_index's reading):
    the acts a code's support names, with the passages each was read from."""
    out = {}
    listed = services.get('services') if isinstance(services, Mapping) else None
    for service in listed if isinstance(listed, list) else []:
        if isinstance(service, Mapping):
            for act in service.get('acts') or []:
                if isinstance(act, Mapping) and isinstance(act.get('id'), str):
                    out[act['id']] = act
    return out


def _spans(items, cited=False) -> list:
    out = []
    for item in items if isinstance(items, (list, tuple)) else ():
        found = _span(item)
        if found is not None and (not cited or (found[0] == 0 and found[4] is True)):
            out.append(found[1:4])
    return out


def passages(evidence, support, text: Optional[str] = None, acts: Optional[Mapping] = None
             ) -> tuple[tuple[int, int, str], ...]:
    """The passages a code's question concerns, as its row shows them and its fingerprint reads them, from three
    sources in this order, at most PER_SOURCE from each: the passages of each act the code was matched to
    (``support['acts']``, read in ``acts``: acts_of), whatever the act's status; the code's own cited passages
    (``evidence``: its exact spans of the document, context 0) - for a code whose act is in doubt, the passage that
    raised the doubt; then CPT Studio's own located passages (``support['source']``) - for a code whose service is in
    doubt, the passages that document the service. Each passage is shown once (_kept); one with fewer than
    MIN_PASSAGE_CHARACTERS non-space characters, or a single word, shows nothing a member could read it by; at most
    MAX_PASSAGES. With ``text`` (the revision's), each is re-checked as an exact slice of it. (start, end, text) each."""
    support = support if isinstance(support, Mapping) else {}
    matched = []
    for act in support.get('acts') or ():
        stored = (acts or {}).get(act.get('id')) if isinstance(act, Mapping) else None
        if isinstance(stored, Mapping):
            matched += _spans(stored.get('evidence'))
    return _kept((matched, _spans(list(evidence or ()), cited=True), _spans(support.get('source'))), text)


def _kept(groups, text: Optional[str], per_source: int = PER_SOURCE) -> tuple[tuple[int, int, str], ...]:
    """The passages of ``groups`` (lists of (start, end, text), in order), each re-checked, readable and shown once: a
    passage inside one already listed adds nothing; one that holds listed ones takes the first one's place and the
    others' (it shows all they show); one that only partly overlaps one listed adds nothing either. At most
    ``per_source`` from each group and MAX_PASSAGES in all."""
    out: list = []  # [start, end, text, group]
    for number, group in enumerate(groups):
        for start, end, quoted in group:
            if len(out) >= MAX_PASSAGES or sum(1 for item in out if item[3] == number) >= per_source:
                break
            if text is not None and not (end <= len(text) and text[start:end] == quoted):
                continue
            if not _readable(quoted) or any(a <= start and end <= b for a, b, _, _ in out):
                continue
            held = [i for i, (a, b, _, _) in enumerate(out) if start <= a and b <= end]
            if any(start < b and a < end for i, (a, b, _, _) in enumerate(out) if i not in held):
                continue
            if held:
                out[held[0]] = [start, end, quoted, out[held[0]][3]]
                out = [item for i, item in enumerate(out) if i not in held[1:]]
                continue
            out.append([start, end, quoted, number])
    return tuple((start, end, quoted) for start, end, quoted, _ in out)


REACH_FACTS = ('extent', 'completion')  # a documented service's reading of these rests on its completion passages


def service_passages(services, family: str, fact: str, text: Optional[str] = None) -> tuple[tuple[int, int, str], ...]:
    """The passages a documented service's question concerns (no code; ``services``: the documented-service reading's
    JSON form, Assessment.services): for a conflict about an act (``conflict:<subject>``), each side's own passage; for
    how far the examination reached or whether it was completed, the passages its reading of that rests on, then those
    establishing the service; otherwise those establishing the service - of every service of ``family`` the reading
    documents, kept as ``passages`` keeps them."""
    listed = services.get('services') if isinstance(services, Mapping) else None
    of_family = [item for item in (listed if isinstance(listed, list) else ()) if isinstance(item, Mapping)
                 and item.get('family') == family]
    candidates = []
    if fact.startswith('conflict:'):
        ids = {item.get('id') for item in of_family}
        subject = fact.split(':', 1)[1]
        conflicts = services.get('conflicts') if isinstance(services, Mapping) else None
        for conflict in conflicts if isinstance(conflicts, list) else ():
            if isinstance(conflict, Mapping) and conflict.get('service') in ids and conflict.get('subject') == subject:
                for side in conflict.get('sides') or ():
                    if isinstance(side, Mapping):
                        candidates += _spans(side.get('evidence'))
        return _kept((candidates,), text, MAX_PASSAGES)
    for item in of_family:
        if fact in REACH_FACTS:
            candidates += _spans(item.get('completion_evidence'))
        candidates += _spans(item.get('evidence'))
    return _kept((candidates,), text, MAX_PASSAGES)


def instance(scope: str, family: str, fact: str, code: str, question: str, reason: str, shown=()) -> dict:
    """One question as its fingerprint reads it: every part a member is shown or CPT Studio reasons from."""
    return {'scope': str(scope or ''), 'family': str(family or ''), 'fact': str(fact or ''), 'code': str(code or ''),
            'question': str(question or ''), 'reason': str(reason or ''),
            'passages': [[start, end, quoted] for start, end, quoted in shown]}


def fingerprint(instances: Iterable[dict]) -> str:
    """The fingerprint of the question a (code, family, fact) asks in one assessment: every instance of it (two
    proposals of one code can each ask it), in canonical order, in FORM. '' for none: no question is asked."""
    items = sorted((dict(item) for item in instances), key=sha256_json)
    return sha256_json({'form': FORM, 'questions': items}) if items else ''


def member_key(code, family, fact) -> tuple[str, str, str]:
    return (str(code or ''), str(family or ''), str(fact or ''))


def group(pairs: Iterable[tuple[tuple[str, str, str], dict]]) -> dict:
    """{member key: fingerprint} of (member key, instance) pairs."""
    by: dict = {}
    for key, item in pairs:
        by.setdefault(key, []).append(item)
    return {key: fingerprint(items) for key, items in by.items()}


def bind(answers, asked: Mapping[tuple[str, str, str], str]) -> tuple[list, list]:
    """(bound, earlier): each standing answer (mappings or objects with code, family, fact, value and question) bound to
    the question it answered - a question ``asked`` asks ({member key: fingerprint}) with its own fingerprint - else
    earlier, as (answer, why): EARLIER_FORM for an answer recorded with no fingerprint (the earlier form, which showed
    no passage), ASKED_DIFFERENTLY where its (code, family, fact) is asked with another fingerprint, NO_LONGER_ASKED where
    it is not asked at all. An answer whose value is not one a question takes binds to nothing and is left out."""
    bound, earlier = [], []
    for answer in answers or ():
        if _field(answer, 'value') not in UNAVAILABLE:
            continue
        key = member_key(_field(answer, 'code'), _field(answer, 'family'), _field(answer, 'fact'))
        given, now = str(_field(answer, 'question') or ''), asked.get(key, '')
        if given and now and given == now:
            bound.append(answer)
        else:
            earlier.append((answer, EARLIER_FORM if not given else ASKED_DIFFERENTLY if now else NO_LONGER_ASKED))
    return bound, earlier
