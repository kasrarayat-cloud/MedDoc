"""The ERCP rules of the events engine (DECISIONS D105, D106 and D107; the round-4 refutation, findings 22, 25 and 26):
holds and signals the per-code rule and the session's reading give an ERCP's codes, each only ADDING a hold, a question
or a warning to what the engine decided before - never READY, never an exclusion, never another code's question.

- D105, a possible stent exchange. An ERCP session with a positive stent REMOVAL and a positive stent PLACEMENT whose
  ducts nothing sets apart is a possible stent exchange (43276: "removal and exchange of stent(s)"), so 43275 (the
  removal) and 43274 (the placement) are never READY on it: each is held with ONE question naming the exchange - whether
  the removal and the placement were one exchange (43276) - and 43276, when proposed, is held with that question,
  never "not documented". Finding 22: "The existing biliary stent was removed with a snare." and "A 10 Fr x 9 cm plastic
  biliary stent was placed into the common bile duct." read as stent_removal and stent made 43275 and 43274 both READY
  and 43276 held not documented. A removal and a placement verified in different ducts (the bile duct and the
  pancreatic duct) stay separate acts; a duct verified on neither act, or the ampulla (it opens on both), never sets
  them apart (coverage.duct_side, D45's reading). "Positive" is verify.POSITIVE and current is D62's possibly current,
  each read as a value in any verification state (D74's reading, D87: a doubt is a question, never a fact); an act
  verified as another performer's is no side of this team's exchange.
- D106, a stone removal that retrieved nothing. A stone_extraction (43264's act) whose own sentence states that nothing
  was retrieved - a negator over stones, calculi, debris or sludge, and a retrieval or extraction word, in the act's
  own sentence: "The bile duct was swept several times with an extraction balloon; no stones or sludge were
  retrieved." - does not support 43264. With no other act supporting it, 43264 is held with the performed_status
  question naming that statement, never READY (finding 25). The installed release EXCLUDES 43264 on that text; the
  hold is the fail-closed answer, recorded as such. An exceptive negation ("no further stones", ADJUDICATION C-7's
  "no further / no other / no additional") states nothing about the acts the document reports as done, so it is not
  read as one; neither is a partial one ("not all stones").
- D107, an ERCP whose access act was begun and not completed. Its cannulation (the session's access act) done at this
  encounter with a usable attempted_not_completed status (verified by its failure marker, as D71 reads an
  examination's) gives every code of the session D61's service.incomplete warn, in the cannulation's own failure-marker
  words (ADJUDICATION R-4), and the 52/53 consideration - a warn and a consideration, never a status (finding 26:
  "Multiple attempts at biliary cannulation were unsuccessful." left a READY 43260 with neither, where the installed
  release gives both). The access act is the session's DEFINING one: a pancreatic duct's cannulation begun and not
  completed beside the bile duct's achieved is no failed ERCP (the installed release's pancreatic avoidance), and
  gives nothing. The examination stated terminated - its status begun and not completed, or its reach's completion
  'incomplete' - is D61's and D71's arm, read before this one (assess._incomplete_session).

Where they run: D105 and D106 sit inside the per-code rule itself - ``ruled`` is events.evaluate's one call site, its
first statement - so every reader of the per-code rule (the assessment, its participants and second review, and the
review overlay's counted codes, overlay.counted_codes: "the evaluation the engine made, made again") reads one
evaluation, and events.evaluate stays the function its module defines. D107 is read by assess._incomplete_session.

Pure apart from one context variable (``_RULING``, set only while ``ruled`` has the per-code rule evaluate one code):
it reads the stored attributes' values and states and the literal words of an act's own located passages, never the
revision text; it imports nothing from studio.gi.
"""
from __future__ import annotations

import contextvars
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Optional

from studio.interpretation import lexicon, mapping, verify, wording

ERCP = 'gi.ercp'

# --- D105: a possible stent exchange ---------------------------------------------------------------------------------

REMOVAL, PLACEMENT, EXCHANGE = 'stent_removal', 'stent', 'stent_exchange'
POSSIBLE_EXCHANGE = 'possible_exchange'  # the reason (events.Evaluation.reason) of D105's hold
EXCHANGE_FACT = 'performed_status'


def _stent_side(event: Mapping, kind: str) -> bool:
    """D105: ``event`` is a side of a possible exchange of the ERCP family - of ``kind``, stated positive
    (verify.POSITIVE) and possibly current (coverage.possibly_current, D62), each read as a value in any verification
    state, and not verified as another performer's act."""
    from studio.interpretation import coverage, events

    return (event.get('family') == ERCP and (event.get('catalogue_kind') or '') == kind
            and events.value(event, 'status') in verify.POSITIVE and coverage.possibly_current(event)
            and not events.verified_other_performer(event))


def exchange_pairs(reading) -> list:
    """D105: (removal, placement) of every positive stent removal and positive stent placement of the ERCP family whose
    ducts nothing sets apart - not both verified (coverage.duct_side) and different - in the reading's order."""
    from studio.interpretation import coverage

    removals = [event for event in reading.events.values() if _stent_side(event, REMOVAL)]
    placements = [event for event in reading.events.values() if _stent_side(event, PLACEMENT)]
    pairs = []
    for removal in removals:
        for placement in placements:
            one, two = coverage.duct_side(removal), coverage.duct_side(placement)
            if not one or not two or one == two:
                pairs.append((removal, placement))
    return pairs


def _spans(places) -> tuple:
    out, seen = [], set()
    for place in places:
        key = (place['start'], place['end'])
        if key not in seen:
            seen.add(key)
            out.append({'start': place['start'], 'end': place['end'], 'text': place['text']})
    return tuple(out)


def exchange_question(reading, removal: Mapping, placement: Mapping) -> tuple[str, str]:
    """D105: (question, reason) of a code held because its stent removal and placement may be one exchange."""
    from studio.interpretation import events

    removed, placed = events.event_label(reading, removal), events.event_label(reading, placement)
    question = (f'Were the {removed} ({wording.quote(events.statement_text(reading, removal), 120)}) and the {placed} '
                f'({wording.quote(events.statement_text(reading, placement), 120)}) one stent exchange (43276), or '
                'separate services (a stent removal, 43275, and a stent placement, 43274)?')
    reason = ('The document states a stent removal and a stent placement at this ERCP, in ducts nothing in the '
              'document sets apart. A stent removed and replaced in the same duct at one session is one stent exchange '
              '(43276), not a removal (43275) and a placement (43274); CPT Studio does not choose between them. Held '
              'for the reviewer, not excluded.')
    return question, reason


def exchange_hold(evaluation, reading):
    """D105 over one code's evaluation: a READY 43275 or 43274 whose own removal or placement is a side of a possible
    exchange (exchange_pairs), and a READY or not-documented 43276 in a session with one, held with the exchange question
    (the first such pair). Any other evaluation is returned unchanged: a code held for another reason keeps its own
    question (D89: a question is never displaced), and an exclusion stands."""
    from studio.interpretation import events

    link = evaluation.link
    if link.family != ERCP or link.route != mapping.CATALOGUE_ROUTE:
        return evaluation
    sides = {kind for kind in link.kinds if kind in (REMOVAL, PLACEMENT, EXCHANGE)}
    ready = evaluation.state == 'performed' and evaluation.reason == events.SUPPORTED
    not_documented = EXCHANGE in sides and evaluation.reason == events.NOT_DOCUMENTED
    if not sides or not (ready or not_documented):
        return evaluation
    own = set(evaluation.supporting)
    pairs = [(removal, placement) for removal, placement in exchange_pairs(reading)
             if EXCHANGE in sides or (REMOVAL in sides and removal['id'] in own)
             or (PLACEMENT in sides and placement['id'] in own)]
    if not pairs:
        return evaluation
    removal, placement = pairs[0]
    question, reason = exchange_question(reading, removal, placement)
    read = tuple(dict.fromkeys(tuple(evaluation.read) + tuple(evaluation.supporting) + (removal['id'], placement['id'])))
    places = events.anchors(reading, removal) + events.anchors(reading, placement)
    return events.Evaluation(evaluation.code, link.family, link, 'uncertain', POSSIBLE_EXCHANGE, reason, read=read,
                             question=events.Question(EXCHANGE_FACT, question, reason, (removal['id'], placement['id']),
                                                      _spans(places)))


# --- D106: a stone removal that retrieved nothing --------------------------------------------------------------------

STONE_EXTRACTION = 'stone_extraction'
NOTHING_RETRIEVED = 'nothing_retrieved'  # the reason (events.Evaluation.reason) of D106's hold
STONE_WORDS = ('stone', 'stones', 'calculus', 'calculi', 'debris', 'sludge')
RETRIEVAL_WORDS = ('retrieve', 'retrieved', 'retrieves', 'retrieving', 'retrieval', 'extract', 'extracted', 'extracts',
                   'extracting', 'extraction', 'remove', 'removed', 'removes', 'removing', 'removal', 'deliver',
                   'delivered', 'recover', 'recovered', 'yield', 'yielded')
# The words between a negator and the stone word that make the negation exceptive (C-7: "no further stones" is about
# stones beyond those the document reports removed) or partial ("not all stones"): such a negation states nothing about
# whether anything was retrieved.
NOT_NOTHING = ('further', 'other', 'additional', 'more', 'residual', 'remaining', 'retained', 'all', 'every', 'each',
               'both', 'only')
NEGATOR_REACH = 3  # at most this many words between the negator and the stone word it governs
CLAUSE_BREAKS = frozenset(',;:()[]')
SENTENCE_ENDS = frozenset('.!?')


def _sentences(place: Mapping) -> list:
    """The sentences of one located place, each {start, end, text} in document offsets: a sentence ends at '.', '!' or
    '?' followed by whitespace or the place's end."""
    text, start = place['text'], place['start']
    out, begin = [], 0
    for index, char in enumerate(text):
        if char in SENTENCE_ENDS and (index + 1 == len(text) or text[index + 1].isspace()):
            if text[begin:index + 1].strip():
                out.append({'start': start + begin, 'end': start + index + 1, 'text': text[begin:index + 1]})
            begin = index + 1
    if text[begin:].strip():
        out.append({'start': start + begin, 'end': start + len(text), 'text': text[begin:]})
    return out


def _tokens(text: str) -> list:
    """The folded words of ``text`` (lexicon.fold) in order, with '|' for a clause break."""
    out, word = [], []
    for char in lexicon.fold(text) + ' ':
        if char.isalnum() or char == "'":
            word.append(char)
            continue
        token = ''.join(word)
        if token and not token.endswith("n't"):
            token = token.strip("'")
        if token:
            out.append(token)
        word = []
        if char in CLAUSE_BREAKS or char in SENTENCE_ENDS:
            out.append('|')
    return out


def _negator(token: str) -> bool:
    return token in lexicon.NEGATORS or token.endswith("n't")


def states_nothing_retrieved(text: str) -> bool:
    """D106: whether ``text`` (one sentence) holds a negator over a stone word - the negator, then at most NEGATOR_REACH
    words with no clause break and no exceptive or partial word (NOT_NOTHING), then STONE_WORDS - and a retrieval or
    extraction word (RETRIEVAL_WORDS)."""
    tokens = _tokens(text)
    if not any(token in RETRIEVAL_WORDS for token in tokens):
        return False
    for index, token in enumerate(tokens):
        if not _negator(token):
            continue
        for later in tokens[index + 1:index + 2 + NEGATOR_REACH]:
            if later == '|' or later in NOT_NOTHING:
                break
            if later in STONE_WORDS:
                return True
    return False


def nothing_retrieved(reading, event: Mapping) -> Optional[dict]:
    """D106: the act's own sentence (a place {start, end, text}) that states nothing was retrieved, else None. The
    act's own sentences are those of its own located passages (events.own_passages: kind, status, target) that hold one
    of its own words (kind, status or target words); a passage of the act none of whose sentences holds them is read
    whole."""
    from studio.interpretation import events

    words = [event[name]['words'] for name in ('kind', 'status', 'target')
             if isinstance(event.get(name), Mapping) and isinstance(event[name].get('words'), Mapping)]
    for place in reading.places(events.own_passages(event)):
        sentences = _sentences(place)
        own = [sentence for sentence in sentences
               if any(sentence['start'] < item['end'] and item['start'] < sentence['end'] for item in words)]
        for sentence in own or sentences:
            if states_nothing_retrieved(sentence['text']):
                return sentence
    return None


def retrieval_hold(evaluation, reading):
    """D106 over one code's evaluation: a READY code of the stone removal (its one requirement group is
    stone_extraction: 43264) whose supporting acts each state that nothing was retrieved is held with the
    performed_status question naming that statement; when another act supports it, the code keeps READY on that act and
    the act that retrieved nothing leaves E* (the decision still read it). Any other evaluation is returned unchanged."""
    from studio.interpretation import events

    link = evaluation.link
    if (link.family != ERCP or link.route != mapping.CATALOGUE_ROUTE
            or tuple(events.requirements(link)) != ((STONE_EXTRACTION,),)):
        return evaluation
    if evaluation.state != 'performed' or evaluation.reason != events.SUPPORTED:
        return evaluation
    stated = []
    for eid in evaluation.supporting:
        sentence = nothing_retrieved(reading, reading.events[eid])
        if sentence is not None:
            stated.append((eid, sentence))
    if not stated:
        return evaluation
    apart = {eid for eid, _ in stated}
    left = tuple(eid for eid in evaluation.supporting if eid not in apart)
    if left:
        labels = [events.event_label(reading, reading.events[eid]) for eid in left[:4]]
        return replace(evaluation, supporting=left, detail=f'The {events.service_label(link.family)} is documented as '
                                                           f'performed with {"; ".join(labels)}.')
    eid, sentence = stated[0]
    act = events.event_label(reading, reading.events[eid])
    question = (f'Was any stone, calculus, debris or sludge removed with the {act} '
                f'({wording.quote(sentence["text"], 120)})?')
    reason = (f'The document states that nothing was retrieved with the {act} ({wording.quote(sentence["text"], 140)}). '
              'CPT Studio does not read a sweep or an extraction that retrieved nothing as a removal of stones or '
              'debris. Held for the reviewer, not excluded.')
    return events.Evaluation(evaluation.code, link.family, link, 'uncertain', NOTHING_RETRIEVED, reason,
                             read=evaluation.read,
                             question=events.Question('performed_status', question, reason, (eid,), _spans([sentence])))


def _read_by_a_rule(link) -> bool:
    """Whether D105 or D106 reads a code of ``link``: of the ERCP family on the catalogue route, a stent removal,
    placement or exchange code (43275, 43274, 43276), or the stone removal's (43264: its one requirement group is
    stone_extraction)."""
    from studio.interpretation import events

    if not link.linked or link.family != ERCP or link.route != mapping.CATALOGUE_ROUTE:
        return False
    return (bool({kind for kind in link.kinds if kind in (REMOVAL, PLACEMENT, EXCHANGE)})
            or tuple(events.requirements(link)) == ((STONE_EXTRACTION,),))


# Set while ``ruled`` has the per-code rule evaluate a code: that evaluation is the rule's own, with this hook stood down.
_RULING = contextvars.ContextVar('studio.interpretation.ercp.ruling', default=False)


def ruled(code: str, kept: Sequence, reading, link: Optional[mapping.CodeLink] = None):
    """DECISIONS D105 and D106, at events.evaluate's one call site (its first statement): None for a code neither rule
    reads, and the per-code rule then goes on as it is; else the per-code rule's evaluation of ``code`` - made once, by
    events.evaluate itself, re-entered with this hook stood down (_RULING) - with the ERCP rules applied. Each only
    turns a READY or a not-documented evaluation into a hold; every other evaluation is returned as it was. The rules
    sit inside the per-code rule, so every reader of it - the assessment, its participants and second review, and the
    review overlay's counted codes (overlay.counted_codes) - reads one evaluation."""
    from studio.interpretation import events

    if _RULING.get():
        return None
    link = link if link is not None else mapping.code_link(code)
    if not _read_by_a_rule(link):
        return None
    token = _RULING.set(True)
    try:
        evaluation = events.evaluate(code, kept, reading, link)
    finally:
        _RULING.reset(token)
    return retrieval_hold(exchange_hold(evaluation, reading), reading)


# --- D107: an ERCP whose access act was begun and not completed ------------------------------------------------------

ACCESS_KINDS = ('cannulation',)  # the ERCP's access act: the duct's cannulation


def access_not_completed(reading, family: str) -> Optional[str]:
    """D107: the failure-marker words (its status words) of the first access act of the ERCP session (ACCESS_KINDS) done
    at this encounter (events.done: a usable status, current time and documenting-team performer) whose status is
    attempted_not_completed - "Multiple attempts at biliary cannulation were unsuccessful." - else None; None for any
    family but the ERCP's. The session's DEFINING access act: a cannulation of the pancreatic duct begun and not
    completed beside a cannulation of the bile duct achieved (both ducts verified, coverage.duct_side) is not the
    session's access failing - the installed release's pancreatic avoidance (detect._pancreatic_avoidance: "a deliberate
    choice, not a failed ERCP") - so it gives nothing; any other begun and not completed, an earlier attempt before the
    access was achieved included, gives the signals as the installed release does."""
    from studio.interpretation import coverage, events

    if family != ERCP:
        return None
    done = [event for event in reading.events.values() if event.get('family') == ERCP
            and (event.get('catalogue_kind') or '') in ACCESS_KINDS and events.done(event)]
    achieved = {coverage.duct_side(event) for event in done if events.value(event, 'status') == 'performed'}
    for event in done:
        if events.value(event, 'status') != 'attempted_not_completed':
            continue
        if coverage.duct_side(event) == 'pancreas' and 'biliary' in achieved:
            continue
        words = events.words_of(event, 'status')
        return words['text'] if words else ''
    return None
