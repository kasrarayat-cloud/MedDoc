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
2, IR2-3) carries none of that model's own wording to the other vendor: its codes, modifiers and ids only as short
tokens (shown_token), the quotes CPT Studio located in the revision text, a reference's ref as given when that model's
own tool results returned it (any other ref as a token), and its enumerated values, units, pages and date; every other
text it wrote only by its length.

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


NOT_SHOWN = ' (not shown)'  # what follows a value a peer request names only by its length (serializers._token's words)
LESION_FIELDS = ('site', 'size', 'morphology', 'action', 'specimen')


def shown_token(value):
    """A code, modifier or id a participant - or Corti - wrote, as a peer request shows it to the other vendor: as given
    when it is a short token (reading._token: at most 20 characters, no whitespace), otherwise only by its length, in
    the words the owner's trace uses (serializers._token). Longer text in such a field may carry a CPT descriptor, which
    CPT Studio never lists, displays or sends (I9; refutation round 2, IR2-3: the engine refused to list it, the trace
    named it by its length, and a peer request relayed it verbatim). A value that is not a string is returned as it
    is."""
    if not isinstance(value, str):
        return value
    named = reading._token(value)
    return value if named == repr(value) else f'{named}{NOT_SHOWN}'


def withheld(text):
    """Text another model wrote in its own words, as a peer request shows it: only by its length, never as written; ''
    stays ''. A value that is not a string is returned as it is."""
    if not isinstance(text, str) or not text:
        return text
    return f'a value of {len(text):,} character{"" if len(text) == 1 else "s"}{NOT_SHOWN}'


def shown_reading(other: ParticipantReading) -> dict:
    """Another model's frozen first reading as a peer request shows it (HARNESS.md 12.4, amended after refutation round
    2, IR2-3; the session lead's D4: a peer request carries no other model's free text). The reading schema's shape, as
    prompt.reading_answer gives it, with only what is not that model's own wording as written: its codes, modifiers and
    ids as given when each is a short token (shown_token); every quote CPT Studio located in the revision text, as the
    model quoted it (the document's own text); a reference by its ref only when that model's own tool results returned
    it (CPT Studio's own identifier; any other ref as a token); and its enumerated values (family, status, reason,
    confidence), units, pages and date of service as CPT Studio recorded them. Everything else it wrote - a basis, a
    description, the anatomy, extent and technique, a lesion's fields, the provider role, a question and why it is
    asked, an extraction issue, a reference's use, a quote that was not located - is shown only by its length
    (withheld). The request's frozen list still names the reading itself (its reading_sha256), from which this is
    made. Pure."""
    def quotes(items) -> list:
        return [item.quote if item.spans else withheld(item.quote) for item in items]

    def tokens(values) -> list:
        return [shown_token(value) for value in values]

    return {
        'date_of_service': {'value': other.date_of_service, 'evidence': quotes(other.date_evidence)},
        'services': [{'id': shown_token(item.id), 'family': item.family, 'status': item.status,
                      'description': withheld(item.description), 'anatomy': withheld(item.anatomy),
                      'extent': withheld(item.extent), 'technique': withheld(item.technique),
                      'lesions': [{field: withheld(getattr(lesion, field)) for field in LESION_FIELDS}
                                  for lesion in item.lesions],
                      'provider_role': withheld(item.provider_role), 'evidence': quotes(item.evidence)}
                     for item in other.services],
        'codes': [{'code': shown_token(item.code), 'modifiers': tokens(item.modifiers), 'units': item.units,
                   'service_ids': tokens(item.service_ids), 'basis': withheld(item.basis),
                   'evidence': quotes(item.evidence), 'confidence': item.confidence} for item in other.codes],
        'not_coded': [{'service_ids': tokens(item.service_ids), 'code': shown_token(item.code), 'reason': item.reason,
                       'evidence': quotes(item.evidence)} for item in other.not_coded],
        'clarifications': [{'question': withheld(item.question), 'why': withheld(item.why),
                            'service_ids': tokens(item.service_ids), 'evidence': quotes(item.evidence)}
                           for item in other.questions],
        'extraction_issues': [{'page': item.page, 'issue': withheld(item.issue)} for item in other.extraction_issues],
        'references_used': [{'ref': item.ref if item.retrieved else shown_token(item.ref), 'use': withheld(item.use)}
                            for item in other.references_used],
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
