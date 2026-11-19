"""A question's identity, its passages and the fact it names (completion repair, 2026-11-06: U10, U11; contract C5).

One implementation, read by every reader of a member's answer: the details rows a member answers (studio/answers.py),
the engine that applies the answers as an input (engine._MemberAnswers), and the read-time overlay's binding
(review.answer_states). Pure: no database, no clock, no provider.

**A question** is one clarification CPT Studio asks: its scope, family, fact, the code it is asked of ('' for a
documented service's question), CPT Studio's own question and reason, and the passages it concerns (``passages``). A
member's answer binds to the question it answered (``fingerprint`` of every instance of that (code, family, fact) the
assessment asked, in the form ``FORM`` presents them). A later assessment applies the answer only where it asks the
same question; an answer to a question no longer asked, or asked differently, is kept and shown as an earlier answer,
never applied.

**The form** is how a question is shown to the member who answers it. ``FORM`` shows each question's passages beside the
fact it names. An answer recorded before answers carried a fingerprint (``MemberAnswer.question`` '') was given to the
installed release's fixed prompt for its (code, family, fact): no question, reason or passage reached the member there,
and that release applied the answer wherever an assessment of its revision asked a question with that key. Refutation
cycle 2 (2026-11-06, answers W2 and W4): such an answer binds by its key, as the installed release bound it - also
after a re-assessment by this release (an install's reassess phase, the recompute after the member's next answer) and to
a question only the review overlay asks - and never by CPT Studio's question or reason text, which its member never saw
and which this release words anew. A fingerprinted answer binds by its fingerprint alone (the rule for stored answers;
API.md "Completion repair (2026-11-06): questions, answers and their recompute").
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
# DECISIONS D143 (the Gemini migration, round 5c): the statement a passage of CPT Studio's own (``support['source']``)
# is part of - set only by the new path's question about several statements (interpretation.events._h3_shown), never
# by the installed release - and the one fact whose row reads it (that question's: whether a statement applies to the
# act). Every other source, and every other fact's row, is read exactly as before.
STATEMENT = 'statement'
LEAD = 'lead'  # True on the one place a statement is quoted by (its status place), and on the act's status place
STATEMENT_FACT = 'statement_scope'
# The member answers a question takes (MemberAnswer.VALUES): each says the detail is unavailable from the document,
# so the code it is asked of is excluded until the answer is withdrawn. No value confirms a clinical fact (decision D7).
NOT_DOCUMENTED, CANNOT_CONFIRM = 'not_documented', 'cannot_confirm'
UNAVAILABLE = (NOT_DOCUMENTED, CANNOT_CONFIRM)
# Why an answer given to this revision is not applied to an assessment (kept, and shown as an earlier answer).
NO_LONGER_ASKED, ASKED_DIFFERENTLY = 'no_longer_asked', 'asked_differently'

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
    for an answer recorded before answers carried one, which binds by its code, family and fact: bind) - its value
    (UNAVAILABLE) and its id. It is what a member said, never clinical documentation: it excludes the code whose
    question it answers and approves nothing."""
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


def passages(evidence, support, text: Optional[str] = None, acts: Optional[Mapping] = None, named: bool = False
             ) -> tuple[tuple[int, int, str], ...]:
    """The passages a code's question concerns, as its row shows them and its fingerprint reads them, from three
    sources in this order, at most PER_SOURCE from each: the passages of each act the code was matched to
    (``support['acts']``, read in ``acts``: acts_of), whatever the act's status; the code's own cited passages
    (``evidence``: its exact spans of the document, context 0) - for a code whose act is in doubt, the passage that
    raised the doubt; then CPT Studio's own located passages (``support['source']``) - for a code whose service is in
    doubt, the passages that document the service. Each passage is shown once (_kept); one with fewer than
    MIN_PASSAGE_CHARACTERS non-space characters, or a single word, shows nothing a member could read it by; at most
    MAX_PASSAGES. With ``text`` (the revision's), each is re-checked as an exact slice of it. (start, end, text) each.

    DECISIONS D143: with ``named`` (question_passages: the STATEMENT_FACT question's row), a source whose passages name
    their statements (STATEMENT, which only the new path's question about several statements sets) is read by
    _statements_kept - one passage of each statement before a second of any; every other source, and every other
    question's row, exactly as before."""
    support = support if isinstance(support, Mapping) else {}
    matched = []
    for act in support.get('acts') or ():
        stored = (acts or {}).get(act.get('id')) if isinstance(act, Mapping) else None
        if isinstance(stored, Mapping):
            matched += _spans(stored.get('evidence'))
    cited, source = _spans(list(evidence or ()), cited=True), support.get('source')
    if named and _names_statements(source):
        return _statements_kept(matched, cited, source, text)
    return _kept((matched, cited, _spans(source)), text)


def _names_statements(source) -> bool:
    """DECISIONS D143: whether a source's passages name their statements (STATEMENT, a non-empty string on any)."""
    return isinstance(source, (list, tuple)) and any(
        isinstance(item, Mapping) and isinstance(item.get(STATEMENT), str) and bool(item.get(STATEMENT))
        for item in source)


def _statements_kept(matched, cited, source, text: Optional[str]) -> tuple[tuple[int, int, str], ...]:
    """DECISIONS D143 (1): the passages of a question about several statements, as its member's row shows them and its
    fingerprint reads them - the code's matched acts' and its own cited passages as passages reads them (at most
    PER_SOURCE each), then CPT Studio's own located ones (``source``, each naming its statement; the act's own name
    none): first ONE passage of each statement - its LEAD (the place the question quotes it by), else its first - in
    the source's order, then the act's (its LEAD, else its first), then every other in the source's order, to
    MAX_PASSAGES - shown in the source's order, so a statement's passages stay together. Every statement the question
    quotes is then in the row while MAX_PASSAGES leaves room for one passage of it: finding 3's framed, device and
    prior-segment denials beside the snare 45385 cites show all three, and a hard-wrapped denial beside the
    prior-segment one shows both its lines and the other sentence, where PER_SOURCE (2) had shown the first two
    passages only. The act's own passage, which a code citing the act shows already, comes after the statements: a
    code citing another passage beside three statements shows that passage and the three statements, not the act's.

    DECISIONS D150 (2): whatever number of passages the code cites. The code's own passages are still chosen as
    passages chooses them (its matched acts', then its cited ones, at most PER_SOURCE from each), but only the FIRST
    of them is kept before the statements: the others come after one passage of each statement, so each statement
    keeps its first passage beside the code's first while MAX_PASSAGES leaves room. D143 kept the code's two cited
    passages first, which left room for two statements: finding 3's framed and device denials beside the
    prior-segment denial, 45385 citing the snare's line and the colonoscope's, showed [the snare, the colonoscope, the
    first two statements] and never the prior-segment denial; it now shows [the snare, the three statements]. Shown as
    before: first the code's chosen passages (a passage that holds one shown in its place), in the code's order, then
    the others in the source's order. MAX_PASSAGES still bounds the row, so beside the code's first passage at most
    three statements are shown."""
    spans, first, lead, order = [], {}, {}, {}  # first/lead: statement name ('' the act's) -> index into spans
    for item in source:
        found = _span(item)
        if found is None:
            continue
        span = found[1:4]
        order.setdefault(span[:2], len(order))
        name = item.get(STATEMENT) if isinstance(item, Mapping) else None
        name = name if isinstance(name, str) else ''
        first.setdefault(name, len(spans))
        if isinstance(item, Mapping) and item.get(LEAD) is True:
            lead.setdefault(name, len(spans))
        spans.append(span)
    picked = [lead.get(name, index) for name, index in first.items() if name]
    own = [lead.get('', first[''])] if '' in first else []
    firsts, act = [spans[index] for index in picked], [spans[index] for index in own]
    rest = [span for index, span in enumerate(spans) if index not in picked and index not in own]
    code = [item[:3] for item in _chosen((matched, cited), text, PER_SOURCE)]  # D150 (2): the code's, as before
    out = _chosen((code[:1], firsts, code[1:], act, rest), text, PER_SOURCE,
                  (1, MAX_PASSAGES, MAX_PASSAGES, MAX_PASSAGES, MAX_PASSAGES))
    rank = {}  # a chosen passage that is, or holds, one of the code's: the first such code passage's place
    for index, (start, end, _, _) in enumerate(out):
        covered = [number for number, (a, b, _) in enumerate(code) if start <= a and b <= end]
        if covered:
            rank[index] = covered[0]
    head = [out[index] for index in sorted(rank, key=lambda index: rank[index])]
    tail = sorted((item for index, item in enumerate(out) if index not in rank),
                  key=lambda item: order.get((item[0], item[1]), len(order)))
    return tuple((start, end, quoted) for start, end, quoted, _ in head + tail)


def _kept(groups, text: Optional[str], per_source: int = PER_SOURCE) -> tuple[tuple[int, int, str], ...]:
    """The passages of ``groups`` (lists of (start, end, text), in order), each re-checked, readable and shown once: a
    passage inside one already listed adds nothing; one that holds listed ones takes the first one's place and the
    others' (it shows all they show); one that only partly overlaps one listed adds nothing either. At most
    ``per_source`` from each group and MAX_PASSAGES in all."""
    return tuple((start, end, quoted) for start, end, quoted, _ in _chosen(groups, text, per_source))


def _chosen(groups, text: Optional[str], per_source: int, caps: Optional[tuple] = None) -> list:
    """_kept's choice, [start, end, text, group] each, in order - at most ``per_source`` from each group, or
    ``caps[group]`` (DECISIONS D143: _statements_kept's), and MAX_PASSAGES in all."""
    out: list = []  # [start, end, text, group]
    for number, group in enumerate(groups):
        cap = per_source if caps is None else caps[number]
        for start, end, quoted in group:
            if len(out) >= MAX_PASSAGES or sum(1 for item in out if item[3] == number) >= cap:
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
    return out


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


def question_passages(services, family: str, fact: str, evidence, support, text: Optional[str] = None,
                      acts: Optional[Mapping] = None) -> tuple[tuple[int, int, str], ...]:
    """The passages a code's question shows and its fingerprint reads (refutation cycle 1, answers F3 and F4): for how
    far the examination reached or whether it was completed, the passages the documented service's reading of that
    rests on - the extent sentence, never the code's polypectomy sentence ("How far was the instrument advanced?" beside
    "The colonoscope was advanced.") - and for a conflict about an act, each side's own passage, the denial that raised
    the doubt included (service_passages); for any other fact, or where the service reading gives none, the code's own
    (passages). One reading for every reader: the engine, the review overlay's binding, and the details rows.
    DECISIONS D143: the STATEMENT_FACT question's row reads the statements its source names (passages ``named``)."""
    if fact.startswith('conflict:') or fact in REACH_FACTS:
        found = service_passages(services, family, fact, text)
        if found:
            return found
    return passages(evidence, support, text, acts, named=fact == STATEMENT_FACT)


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


# The facts whose question the review overlay words anew with each review decision while the member's row stays the same
# (refutation cycle 5, answers 1): base_included's hidden reason names the codes that hold the base code ("Is 45378 reported
# separately from 45380, 45385 ...?" becomes "... from 45385 ..." when 45380 is rejected), and separate_em's reason names
# the reinstated procedures - the row the member answered shows the fixed prompt and the same passages either way. An
# answer to one is bound by its (code, family, fact) key, as the installed release bound every answer; a fingerprint bound
# it to wording the member never saw, and a rejection or a reinstatement withdrew it silently as "asked differently".
KEY_BOUND_FACTS = ('base_included', 'separate_em')


def bind(answers, asked: Mapping[tuple[str, str, str], str]) -> tuple[list, list]:
    """(bound, earlier): each standing answer (mappings or objects with code, family, fact, value and question) bound to
    the question it answered - a question ``asked`` asks ({member key: fingerprint}) with its own fingerprint, or, for
    an answer recorded in the earlier form (no fingerprint: given to the installed release's fixed prompt for its key),
    any question ``asked`` asks with its (code, family, fact), as the installed release bound it (refutation cycle 2,
    answers W2 and W4) - else earlier, as (answer, why): ASKED_DIFFERENTLY where a fingerprinted answer's key is asked
    with another fingerprint, NO_LONGER_ASKED where its key is not asked at all. An answer whose value is not one a
    question takes binds to nothing and is left out. An answer to a KEY_BOUND_FACTS question binds by its key whatever
    fingerprint it carries (refutation cycle 5)."""
    bound, earlier = [], []
    for answer in answers or ():
        if _field(answer, 'value') not in UNAVAILABLE:
            continue
        key = member_key(_field(answer, 'code'), _field(answer, 'family'), _field(answer, 'fact'))
        given, now = str(_field(answer, 'question') or ''), asked.get(key, '')
        if _field(answer, 'fact') in KEY_BOUND_FACTS:
            given = ''
        if not now:
            earlier.append((answer, NO_LONGER_ASKED))
        elif not given or given == now:
            bound.append(answer)
        else:
            earlier.append((answer, ASKED_DIFFERENTLY))
    return bound, earlier
