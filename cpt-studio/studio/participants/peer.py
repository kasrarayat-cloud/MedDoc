"""Phase 2 of a model participant: its peer review (HARNESS.md 11.1), made after every first assessment was frozen.

The request (build_request) is the participant's own: PEER_INSTRUCTIONS, the same framed revision text with no original
file attached (prompt.peer_framed_document), and one text block (prompt.peer_document) holding its own frozen first
reading, the frozen peer conclusions and CPT Studio's rule-based reading, each labelled for what it is, then the open
questions' ids and the sha256 of every frozen input shown. The own reading must be one that was read (a participant whose
first assessment failed never gets a first look that has already seen its peers). The frozen inputs listed are exactly
what the request shows (refutation round 1, IND-5; check_frozen): the participant's own reading under its own name,
each peer shown under the peer's name ('corti', or the other model's), 'revision' (the text) and 'cpt_studio' (CPT
Studio's reading), every sha256 CPT Studio can compute from what is shown being that one - the own reading's
studio.types.sha256_json, the text's UTF-8 sha256 and CPT Studio's reading's sha256_json - so the record never lists an
input that was not shown, never shows one it does not list, and never files the own reading under another name. The
answer is the peer-review schema (prompt.PEER_SCHEMA), and the tools are the same as in phase 1, through the same loop.

What a peer is shown of another model's frozen reading (shown_reading; HARNESS.md 12.4 as amended after refutation round
2, IR2-3, and round 3, peer-1) carries none of that model's own wording to the other vendor: its codes, modifiers and
ids only in their strict shapes (shown_code, shown_modifier, ShownIds: a CPT or HCPCS code's five characters, two
capital letters or digits, letters and digits up to 8), the quotes CPT Studio located in the revision text, a
reference's ref as given when that model's own tool results returned it (any other ref only as such an id), and its
enumerated values, units, pages and date; every other value and text it wrote only by its length, an id so withheld
under a name of CPT Studio's own that is the same wherever the request mentions it.

The answer (read) is checked as a reading is (reading.py): strict JSON, CPT Studio's own schema validation, bounds that
refuse it whole (more than 64 question answers, 128 code positions, 64 additional codes or 64 references used, more than
16 quotes on one item, a quote over 600 characters or any other text over 2,000), and every quote located in the revision
text (I7) - an unlocated quote is kept, unverified, and is never evidence. The vendor modules refuse a refused,
truncated, other-model or fallback answer whole before it reaches this module. Item-level findings are problems and never
refuse the review:
- an answer to a question id the request did not list is dropped;
- an answer that says the document settles its question but gives no value is read as not settled, and the value of an
  answer that says the document does not settle it is not kept (so a non-answer can never become a candidate);
- a repeated question id is named; a code that is not five characters is kept as given; an additional code whose units
  fall outside 1 to 99 is dropped.
The frozen inputs are copied from the request, and each reference used is checked against the refs the peer-review run's
own tool calls returned (``retrieved``), exactly as in phase 1. The review is recorded apart from the frozen reading and
never replaces it; a code it adds is proposed after peer review, never independently.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Callable, Optional, Sequence

from studio.participants import http, prompt, reading
from studio.providers.base import ProviderUnavailable, request_sha256
from studio.types import (CodePosition, PageSpan, ParticipantCode, ParticipantReading, PeerReview, ProviderRequest,
                          QuestionAnswer, ReferenceUse, sha256_json)

REFUSED = 'The peer review was not used: '  # every refusal problem starts so; the reason follows
REVISION, CPT_STUDIO = 'revision', 'cpt_studio'  # the frozen inputs every peer request shows besides the readings
MAX_ANSWERS = 64
MAX_POSITIONS = 128
MAX_ADDITIONAL_CODES = 64
_TOP_LISTS = (('question_answers', MAX_ANSWERS, 'question answers'),
              ('code_positions', MAX_POSITIONS, 'code positions'),
              ('additional_codes', MAX_ADDITIONAL_CODES, 'additional codes'),
              ('references_used', reading.MAX_REFERENCES, 'references used'))


def build_request(name: str, adapter_version: str, text: str, pages: Sequence[PageSpan], kind: str,
                  own: ParticipantReading, peers: dict, cpt_studio: dict, frozen: Sequence, *, max_bytes: int,
                  make_body: Callable[[str, str], dict]) -> ProviderRequest:
    """A participant's peer-review request (pure; no credentials). Content that cannot be sent (unframeable or
    unencodable text, over ``max_bytes``) raises ProviderUnavailable; inputs that are not the documented shapes - an own
    reading that is another participant's, refused or not among the frozen inputs, peers or CPT Studio's reading in
    another shape (prompt.peer_document) - are programming errors (TypeError, ValueError)."""
    framed = http.framed_text(text, pages, kind, prompt.peer_framed_document)
    if not isinstance(own, ParticipantReading):
        raise TypeError('The own reading must be a studio.types.ParticipantReading.')
    if own.provider != name:
        raise ValueError(f"The own reading is {own.provider!r}'s, not {name!r}'s.")
    if own.refused:
        raise ValueError('A refused first reading has no peer review: only a participant whose first reading was read '
                         'takes part in phase 2.')
    document = prompt.peer_document(own, peers, cpt_studio, frozen)
    listed = prompt.peer_document_inputs(document)
    if listed is None:  # peer_document writes what peer_document_inputs reads; anything else is a defect here
        raise RuntimeError('The peer document does not read back as one.')
    check_frozen(text, own, peers, cpt_studio, listed[1])
    return http.finished_request(name, adapter_version, make_body(framed, document), text, max_bytes=max_bytes)


NOT_SHOWN = ' (not shown)'  # what follows a value named only by its length (as the owner's trace shows one too)
LESION_FIELDS = ('site', 'size', 'morphology', 'action', 'specimen')
# The strict shapes in which a value another model - or Corti - wrote is shown to the other vendor as given (HARNESS.md
# 12.4 as amended after refutation round 3, peer-1). Each is ASCII and whole: fullmatch, no case folding.
HCPCS = re.compile(r'[A-Z][0-9]{4}')  # an HCPCS Level II code (checks.SCOPE_FORMATS 'hcpcs'); a CPT code: reading.CODE
MODIFIER = re.compile(r'[A-Z0-9]{2}')  # a modifier as the engine states a participant's (engine.MODIFIER_SHAPE)
SHORT_ID = re.compile(r'[A-Za-z0-9]{1,8}')  # an id: letters and digits only, at most 8 characters
# A tool call's own shapes (prompt.TOOLS; the owner's trace, shown_tool and shown_arguments): the tools CPT Studio has,
# the fields they take, a date as they take one (studio.reference.tools: YYYY-MM-DD, or '' for every release held).
TOOL_NAMES = frozenset(tool['name'] for tool in prompt.TOOLS)
TOOL_FIELDS = frozenset(name for tool in prompt.TOOLS for name in tool['parameters']['properties'])
TOOL_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')


def code_shaped(value) -> bool:
    """Whether ``value`` is in a code's shape: the five characters CPT Studio lists a CPT code in (reading.CODE,
    serializers.CODE_SHAPE: four digits and a digit or capital letter) or an HCPCS Level II code's (HCPCS: a capital
    letter and four digits). The one rule (refutation round 4, the session's D9) by which a code a model participant -
    or Corti - wrote is shown as given (shown_code: a peer request, the owner's trace) and by which the engine reads a
    participant's code at all (engine.participant_listable): no other value is listed or shown as a code."""
    return isinstance(value, str) and bool(reading.CODE.fullmatch(value) or HCPCS.fullmatch(value))


def shown_code(value):
    """A code another model - or Corti - wrote, as a peer request shows it to the other vendor: as given only in a
    code's shape - the five characters CPT Studio lists a CPT code in (reading.CODE, serializers.CODE_SHAPE: four digits
    and a digit or capital letter) or an HCPCS Level II code's (HCPCS: a capital letter and four digits) - and otherwise
    only by its length (withheld). The 20-character token rule this replaces (refutation round 3, peer-1) passed
    'SYNTH;WITH-LESION(S)' - a Corti code the engine refuses to list and tells the member is not shown - verbatim to
    both vendors, and any piece of a descriptor cut to 20 characters; text in a code field may carry a CPT descriptor,
    which CPT Studio never sends (I9). '' (no code named) stays ''; a value that is not a string is returned as it
    is."""
    if not isinstance(value, str) or code_shaped(value):
        return value
    return withheld(value)


def shown_modifier(value):
    """A modifier another model wrote, as a peer request shows it: as given only when it is exactly two capital letters
    or digits (MODIFIER, the shape the engine states a participant's modifiers in), otherwise only by its length - a
    descriptor cut into pieces of 20 characters or fewer reached the other vendor as one code's modifiers (peer-1). A
    value that is not a string is returned as it is."""
    if not isinstance(value, str) or MODIFIER.fullmatch(value):
        return value
    return withheld(value)


class ShownIds:
    """The ids one peer request shows of another model's reading - its services' ids and every list of service ids that
    refers to them: an id of letters and digits only, at most 8 characters (SHORT_ID), as given; any other id (peer-1:
    'SNARE;WITH-SYNTH(S)' reached the other vendor as a service id) under a name of CPT Studio's own, "id N: a value of
    L characters (not shown)", numbered in the order the request first mentions each. One instance serves one request,
    so a withheld id has the same name wherever that request mentions it - what refers to a service still finds it - and
    two withheld ids never share one, so two services are never made one; a name holds a space, which no id shown as
    given does, so it never meets one. '' stays ''; a value that is not a string is returned as it is."""

    def __init__(self):
        self.names: dict[str, str] = {}

    def __call__(self, value):
        if not isinstance(value, str) or not value or SHORT_ID.fullmatch(value):
            return value
        if value not in self.names:
            self.names[value] = f'id {len(self.names) + 1}: {withheld(value)}'
        return self.names[value]


def shown_reference(ref, retrieved):
    """A reference a model says it used, as CPT Studio shows it anywhere - a peer request, the owner's trace, the API
    and both reports (refutation round 4, the session's D9, shapes-3): its ref as given when that model's own tool
    results returned it (``retrieved`` True: CPT Studio's own identifier), any other ref only when it is a short id
    (SHORT_ID), and otherwise only by its length - a ref no tool returned is the model's own text:
    'colonoscopy-flexible-with-biopsy-single-or-multiple' was served and printed as written. A ref that is not a string
    is returned as it is."""
    if retrieved is True or not isinstance(ref, str) or SHORT_ID.fullmatch(ref):
        return ref
    return withheld(ref)


def shown_ref(item: ReferenceUse):
    """A reference another model says it used, as a peer request shows it (shown_reference)."""
    return shown_reference(item.ref, item.retrieved)


def shown_tool(name):
    """The tool a model's call names, as the owner's trace shows it (refutation round 4, shapes-4): as given only when
    it is one of CPT Studio's tools (TOOL_NAMES) - a model can name any other, which the loop answers as unknown and
    records by a name of up to 40 characters - and otherwise only by its length. '' (none recorded) stays ''; a value
    that is not a string is returned as it is."""
    if not isinstance(name, str) or not name or name in TOOL_NAMES:
        return name
    return withheld(name)


def shown_arguments(arguments):
    """A tool call's arguments as a model wrote them, as the owner's trace shows them (refutation round 4, shapes-4;
    I9): an object of the tools' own fields (TOOL_FIELDS), each value only in its shape - each of ``codes`` as
    shown_code shows a code, ``date_of_service`` as a YYYY-MM-DD date or '', ``topic`` as one of the policy topics - and
    any other value only by its length; arguments that are not such an object (a field no tool has, a list, or text the
    loop could not read as JSON, which it records as given) only by their length, as a whole. None (no arguments
    recorded) stays None. 'Colonoscopy, flexible, diagnostic' had been served as written in a call's codes."""
    if arguments is None:
        return None
    if isinstance(arguments, dict) and all(isinstance(name, str) and name in TOOL_FIELDS for name in arguments):
        return {name: _shown_argument(name, value) for name, value in arguments.items()}
    return _by_length(arguments)


def _shown_argument(name: str, value):
    if name == 'codes':
        return ([shown_code(item) if isinstance(item, str) else _by_length(item) for item in value]
                if isinstance(value, list) else _by_length(value))
    if name == 'date_of_service':
        return value if isinstance(value, str) and (not value or TOOL_DATE.fullmatch(value)) else _by_length(value)
    return value if isinstance(value, str) and value in prompt.POLICY_TOPICS else _by_length(value)  # 'topic'


def _by_length(value):
    """A value a model wrote, only by its length: text as withheld names it; any other JSON value by the length of its
    compact JSON."""
    if isinstance(value, str):
        return withheld(value)
    return withheld(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def withheld(text):
    """Text another model wrote in its own words, as a peer request shows it: only by its length, never as written; ''
    stays ''. A value that is not a string is returned as it is."""
    if not isinstance(text, str) or not text:
        return text
    return f'a value of {len(text):,} character{"" if len(text) == 1 else "s"}{NOT_SHOWN}'


def shown_reading(other: ParticipantReading) -> dict:
    """Another model's frozen first reading as a peer request shows it (HARNESS.md 12.4, amended after refutation round
    2, IR2-3, and round 3, peer-1; the session lead's D4: a peer request carries no other model's free text). The
    reading schema's shape, as prompt.reading_answer gives it, with only what is not that model's own wording as
    written: its codes, modifiers and ids only in their strict shapes (shown_code, shown_modifier, ShownIds - one for
    the whole reading, so an id it withholds has one name wherever the reading mentions it); every quote CPT Studio
    located in the revision text, as the model quoted it (the document's own text); a reference by its ref when that
    model's own tool results returned it (CPT Studio's own identifier; any other ref only as a short id, shown_ref);
    and its enumerated values (family, status, reason, confidence), units, pages and date of service as CPT Studio
    recorded them. Everything else it wrote - a basis, a description, the anatomy, extent and technique, a lesion's
    fields, the provider role, a question and why it is asked, an extraction issue, a reference's use, a quote that was
    not located - is shown only by its length (withheld). The request's frozen list still names the reading itself (its
    reading_sha256), from which this is made. Pure."""
    def quotes(items) -> list:
        return [item.quote if item.spans else withheld(item.quote) for item in items]

    ids = ShownIds()  # services first, then the lists that refer to them: the names follow the reading's own order
    services = [{'id': ids(item.id), 'family': item.family, 'status': item.status,
                 'description': withheld(item.description), 'anatomy': withheld(item.anatomy),
                 'extent': withheld(item.extent), 'technique': withheld(item.technique),
                 'lesions': [{field: withheld(getattr(lesion, field)) for field in LESION_FIELDS}
                             for lesion in item.lesions],
                 'provider_role': withheld(item.provider_role), 'evidence': quotes(item.evidence)}
                for item in other.services]
    codes = [{'code': shown_code(item.code), 'modifiers': [shown_modifier(value) for value in item.modifiers],
              'units': item.units, 'service_ids': [ids(value) for value in item.service_ids],
              'basis': withheld(item.basis), 'evidence': quotes(item.evidence), 'confidence': item.confidence}
             for item in other.codes]
    not_coded = [{'service_ids': [ids(value) for value in item.service_ids], 'code': shown_code(item.code),
                  'reason': item.reason, 'evidence': quotes(item.evidence)} for item in other.not_coded]
    clarifications = [{'question': withheld(item.question), 'why': withheld(item.why),
                       'service_ids': [ids(value) for value in item.service_ids], 'evidence': quotes(item.evidence)}
                      for item in other.questions]
    return {
        'date_of_service': {'value': other.date_of_service, 'evidence': quotes(other.date_evidence)},
        'services': services, 'codes': codes, 'not_coded': not_coded, 'clarifications': clarifications,
        'extraction_issues': [{'page': item.page, 'issue': withheld(item.issue)} for item in other.extraction_issues],
        'references_used': [{'ref': shown_ref(item), 'use': withheld(item.use)} for item in other.references_used],
    }


def check_frozen(text: str, own: ParticipantReading, peers: dict, cpt_studio: dict, frozen: Sequence) -> None:
    """Refuse (ValueError) a frozen list that is not exactly what a peer request shows (refutation round 1, IND-5): the
    own reading under ``own.provider``, each peer in ``peers`` under its name, REVISION and CPT_STUDIO - no other name,
    none missing - and the sha256 of each input CPT Studio can compute from what it shows equal to that one. A peer's
    sha256 (Corti's response bytes, the other model's frozen reading) is the caller's, from the first assessment's
    record. ``frozen``: (name, sha256) pairs, as prompt.peer_document validates them."""
    listed = {name: sha256 for name, sha256 in frozen}
    shown = {own.provider, *peers, REVISION, CPT_STUDIO}
    if set(listed) != shown or len(listed) != len(frozen):
        missing, extra = sorted(shown - set(listed)), sorted(set(listed) - shown)
        raise ValueError('The frozen inputs must name exactly what the request shows'
                         + (f'; not listed: {", ".join(missing)}' if missing else '')
                         + (f'; listed but not shown: {", ".join(extra)}' if extra else '') + '.')
    try:
        revision = hashlib.sha256(text.encode('utf-8')).hexdigest()
    except UnicodeEncodeError:
        raise ProviderUnavailable('The document text cannot be encoded as UTF-8; nothing was sent.') from None
    computed = {own.provider: sha256_json(own), REVISION: revision, CPT_STUDIO: sha256_json(cpt_studio)}
    wrong = sorted(name for name, sha256 in computed.items() if listed[name] != sha256)
    if wrong:
        raise ValueError(f'The frozen inputs do not carry the sha256 of what the request shows for {", ".join(wrong)}.')


def request_inputs(request: ProviderRequest, document_of: Callable[[dict], Optional[str]]):
    """(question ids, frozen inputs) of a stored peer-review request, read from its own body; or why it is not one
    (a str): its body no longer matches its recorded sha256, or ``document_of`` (the vendor's) finds no peer document in
    it."""
    try:
        if request_sha256(request.body) != request.canonical_sha256:
            return 'the request does not match its recorded hash'
    except (TypeError, ValueError):
        return 'the request body is not JSON data'
    try:
        document = document_of(request.body)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        document = None
    listed = prompt.peer_document_inputs(document)
    if listed is None:
        return 'the request is not a peer review this adapter builds'
    return listed


def refusal(provider: str, adapter_version: str, requested_model: str, returned_model: str, reason: str,
            frozen_inputs=()) -> PeerReview:
    """A peer review refused whole: none of it is read, and its one problem says why."""
    ending = '' if reason.endswith(('.', '!', '?')) else '.'
    return PeerReview(provider=provider, adapter_version=adapter_version, review_version=prompt.PEER_VERSION,
                      requested_model=requested_model, returned_model=returned_model,
                      frozen_inputs=tuple(frozen_inputs), refused=True, problems=(f'{REFUSED}{reason}{ending}',))


def read(answer: str, source: str, *, provider: str, adapter_version: str, requested_model: str, returned_model: str,
         question_ids: Sequence[str], frozen_inputs: Sequence, refs_retrieved=frozenset(),
         set_aside_unknown: bool = False) -> PeerReview:
    """The peer review in ``answer`` (the vendor's output text), its quotes located in ``source`` (the revision text the
    request carried as its context 0). ``set_aside_unknown``: as reading.read's (Fable's harness-4; HARNESS.md, "Harness
    repair 3", F-CONTRACT): the fields the peer schema does not declare are set aside, named and not read."""
    refs = reading.retrieved_refs(refs_retrieved)
    frozen = tuple((name, sha256) for name, sha256 in frozen_inputs)

    def refused(reason: str) -> PeerReview:
        return refusal(provider, adapter_version, requested_model, returned_model, reason, frozen)

    if not isinstance(answer, str):
        return refused('there is no answer text')
    if not isinstance(source, str):
        return refused('the request carries no revision text to locate quotes in')
    try:
        parsed = reading.strict_json_text(answer)
    except reading.JSONRefused as exc:
        return refused(f'the answer {exc}')
    notes: tuple[str, ...] = ()
    if set_aside_unknown:
        parsed, removed = reading.set_aside(parsed, prompt.PEER_SCHEMA)
        if len(removed) > reading.MAX_SET_ASIDE:
            return refused(reading.too_many_set_aside(len(removed)))
        notes = tuple(reading.set_aside_note(item) for item in removed)
    error = reading.schema_error(parsed, prompt.PEER_SCHEMA, 'the peer review')
    if error:
        return refused(f'the answer breaks the peer-review schema: {error}')
    error = reading.bound_error(parsed, _TOP_LISTS)
    if error:
        return refused(error)
    return _Reader(source, notes).read(parsed, tuple(question_ids), refs, provider=provider,
                                       adapter_version=adapter_version, requested_model=requested_model,
                                       returned_model=returned_model, frozen_inputs=frozen)


class _Reader:
    """Builds a PeerReview from a schema-valid, bounded answer, recording item-level problems in order."""

    def __init__(self, source: str, notes: tuple[str, ...] = ()):
        self.locator = reading.Locator(source)
        self.problems: list[str] = list(notes)  # the fields reading.set_aside removed, first (F-CONTRACT)
        self.unverified = 0

    def quotes(self, items) -> tuple:
        located = tuple(self.locator.locate(item) for item in items)
        self.unverified += sum(1 for item in located if not item.spans)
        return located

    def read(self, parsed: dict, question_ids: tuple, refs: frozenset, **identity) -> PeerReview:
        listed, answered, answers = set(question_ids), set(), []
        for index, item in enumerate(parsed['question_answers']):
            where, question = f'question_answers[{index}]', item['question_id']
            if question not in listed:
                self.problems.append(f'{where} answers a question id the request did not list '
                                     f'({reading._token(question)}); it was dropped.')
                continue
            if question in answered:
                self.problems.append(f'{where} answers {reading._token(question)} again.')
            answered.add(question)
            settled, value = item['settled'], item['value']
            if settled and not value.strip():
                self.problems.append(f'{where} says the document settles {reading._token(question)} but gives no '
                                     'value; it is read as not settled.')
                settled = False
            if not settled:
                if value.strip():
                    self.problems.append(f'{where} says the document does not settle {reading._token(question)} but '
                                         'gives a value; the value was not kept.')
                value = ''
            answers.append(QuestionAnswer(question_id=question, settled=settled, value=value,
                                          evidence=self.quotes(item['evidence'])))
        positions = []
        for index, item in enumerate(parsed['code_positions']):
            if not reading.CODE.fullmatch(item['code']):
                self.problems.append(f'code_positions[{index}] ({reading._token(item["code"])}) is not a five-character '
                                     'CPT code; it is kept as given.')
            positions.append(CodePosition(code=item['code'], position=item['position'], reason=item['reason'],
                                          evidence=self.quotes(item['evidence'])))
        codes = []
        for index, item in enumerate(parsed['additional_codes']):
            where = f'additional_codes[{index}] ({reading._token(item["code"])})'
            if item['units'] not in reading.UNITS:
                self.problems.append(f'{where} gives {reading._units(item["units"])} units, outside 1 to 99; it was '
                                     'dropped.')
                continue
            if not reading.CODE.fullmatch(item['code']):
                self.problems.append(f'{where} is not a five-character CPT code; it is kept as given.')
            codes.append(ParticipantCode(code=item['code'], modifiers=tuple(item['modifiers']), units=item['units'],
                                         service_ids=tuple(item['service_ids']), basis=item['basis'],
                                         evidence=self.quotes(item['evidence']), confidence=item['confidence']))
        references = tuple(ReferenceUse(ref=item['ref'], use=item['use'], retrieved=item['ref'] in refs)
                           for item in parsed['references_used'])
        return PeerReview(review_version=prompt.PEER_VERSION, answers=tuple(answers), positions=tuple(positions),
                          additional_codes=tuple(codes), references_used=references, problems=tuple(self.problems),
                          refused=False, unverified_quotes=self.unverified, **identity)
