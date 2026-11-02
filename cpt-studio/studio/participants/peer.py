"""Phase 2 of a model participant: its peer review (HARNESS.md 11.1), made after every first assessment was frozen.

The request (build_request) is the participant's own: PEER_INSTRUCTIONS, the same framed revision text with no original
file attached (prompt.peer_framed_document), and one text block (prompt.peer_document) holding its own frozen first
reading, the frozen peer conclusions and CPT Studio's rule-based reading, each labelled for what it is, then the open
questions' ids and the sha256 of every frozen input shown. The own reading must be one that was read (a participant whose
first assessment failed never gets a first look that has already seen its peers) and one of the frozen inputs: its
studio.types.sha256_json is among those listed. The answer is the peer-review schema (prompt.PEER_SCHEMA), and the tools
are the same as in phase 1, through the same loop.

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

from typing import Callable, Optional, Sequence

from studio.participants import http, prompt, reading
from studio.providers.base import request_sha256
from studio.types import (CodePosition, PageSpan, ParticipantCode, ParticipantReading, PeerReview, ProviderRequest,
                          QuestionAnswer, ReferenceUse, sha256_json)

REFUSED = 'The peer review was not used: '  # every refusal problem starts so; the reason follows
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
    if sha256_json(own) not in {sha256 for _, sha256 in listed[1]}:
        raise ValueError('The own reading is not among the frozen inputs: its studio.types.sha256_json must be listed.')
    return http.finished_request(name, adapter_version, make_body(framed, document), text, max_bytes=max_bytes)


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
         question_ids: Sequence[str], frozen_inputs: Sequence, refs_retrieved=frozenset()) -> PeerReview:
    """The peer review in ``answer`` (the vendor's output text), its quotes located in ``source`` (the revision text the
    request carried as its context 0)."""
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
    error = reading.schema_error(parsed, prompt.PEER_SCHEMA, 'the peer review')
    if error:
        return refused(f'the answer breaks the peer-review schema: {error}')
    error = reading.bound_error(parsed, _TOP_LISTS)
    if error:
        return refused(error)
    return _Reader(source).read(parsed, tuple(question_ids), refs, provider=provider, adapter_version=adapter_version,
                                requested_model=requested_model, returned_model=returned_model, frozen_inputs=frozen)


class _Reader:
    """Builds a PeerReview from a schema-valid, bounded answer, recording item-level problems in order."""

    def __init__(self, source: str):
        self.locator = reading.Locator(source)
        self.problems: list[str] = []
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
