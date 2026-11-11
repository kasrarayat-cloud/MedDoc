"""The ERCP rules of the events engine (DECISIONS D105, D106 and D107; the round-4 refutation, findings 22, 25 and 26;
completed by D127, the review of those rules and the family parity audit): holds and signals the per-code rule and the
session's reading give an ERCP's codes, each only ADDING a hold, a question or a warning to what the engine decided
before - never READY, never an exclusion, never another code's question - but for D127's one release (a clearance, below).

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

- D127, as the review asked (each arm's docstring names its problem):
  - D105 reads an exchange Gemini files as stent_exchange beside the stent_removal or the stent placement it includes as
    a possible exchange too (exchange_pairs), so 43275 or 43274 is never READY beside it;
  - D106 reads the act's own sentence AND the sentence that immediately follows it when that one continues the act
    (names no other act), the sentences of the code's own exact evidence that hold the act's words (Gemini's passage
    may be the sentence's first clause), "nothing was retrieved" and "no stones were found" - and never another act's
    sentence of the act's passage. A sentence that states a yield ("Multiple stones were extracted ... until no stones
    remained.") is a clearance: its denial of the stones' PRESENCE ("no stones remained", "no stones were seen") supports
    43264 again, as the installed release reads it - the one release, never of a denied RETRIEVAL ("no stones were
    retrieved"), which still holds;
  - D107 quotes the sentence that states the failure, as the installed release does;
  - the cannulation stated both achieved and not achieved is the installed release's conflict (cannulation_conflict):
    every ERCP code asks it.

- D140, as the review of D127 asked (problems 0-2):
  - the yield that clears D106's hold is the act's OWN statement (_states_yield): read in the act's own attribute words
    (its kind, status, target and technique words; the structural reading, _own_yield), or in a clause of the act's own
    whose subject is a stone word with a past yield verb and that holds no purpose, condition or doubt, or other-time
    word (the clause reading, _yields, which keeps D127's pinned clearances) - never a purpose clause ("to ensure all
    stones had been removed"), a device as the subject ("the balloon was removed"), a doubt ("It is unclear whether any
    stones were removed"), an earlier yield ("after stones were removed at the prior ERCP") or the past perfect ("had
    been removed"). A false yield no longer stops the next sentence's read either;
  - the sentence that follows the act's own is never dropped as another act's when it holds the words of an event that
    is not performed - a denial or an uncertain statement Gemini files as its own event ("No stones or sludge were
    retrieved.", not_performed), or a plan or an act begun and not completed: that is the act's statement, not another
    act's.

Where they run: D105 and D106 sit inside the per-code rule itself - ``ruled`` is events.evaluate's one call site, its
first statement - so every reader of the per-code rule (the assessment, its participants and second review, and the
review overlay's counted codes, overlay.counted_codes: "the evaluation the engine made, made again") reads one
evaluation, and events.evaluate stays the function its module defines. D107 is read by assess._incomplete_session.

Pure apart from one context variable (``_RULING``, set only while ``ruled`` has the per-code rule evaluate one code):
it reads the stored attributes' values and states, the literal words of the inventory's located passages and of the
code's own exact evidence (the proposer's spans, verified against the revision text before the rule runs), never the
revision text itself; it imports nothing from studio.gi.
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
    ducts nothing sets apart - not both verified (coverage.duct_side) and different - in the reading's order. DECISIONS
    D127 (the review of D105, problem 1): then (removal, exchange) of every such removal beside a positive stent
    EXCHANGE, and (exchange, placement) of every such exchange beside a placement, read alike - an exchange Gemini files
    as stent_exchange plus the stent_removal it includes, or as stent_exchange beside the placement it includes, is a
    possible exchange too, so the removal (43275) or the placement (43274) is never READY beside it. The D105 pairs come
    first, so a session with all three keeps D105's question."""
    from studio.interpretation import coverage

    removals = [event for event in reading.events.values() if _stent_side(event, REMOVAL)]
    placements = [event for event in reading.events.values() if _stent_side(event, PLACEMENT)]
    exchanges = [event for event in reading.events.values() if _stent_side(event, EXCHANGE)]
    pairs = []
    for first, second in ([(removal, placement) for removal in removals for placement in placements]
                          + [(removal, exchange) for removal in removals for exchange in exchanges]
                          + [(exchange, placement) for exchange in exchanges for placement in placements]):
        one, two = coverage.duct_side(first), coverage.duct_side(second)
        if not one or not two or one == two:
            pairs.append((first, second))
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
    """D105: (question, reason) of a code held because its stent removal and placement may be one exchange. D127: a
    pair one of whose sides is a stent exchange asks whether the other side - the removal or the placement - was part of
    that exchange (43276) or a separate service (43275 or 43274)."""
    from studio.interpretation import events

    def said(event: Mapping) -> str:
        return wording.quote(events.statement_text(reading, event), 120)

    if EXCHANGE in ((removal.get('catalogue_kind') or ''), (placement.get('catalogue_kind') or '')):
        whole, part = (removal, placement) if (removal.get('catalogue_kind') or '') == EXCHANGE else (placement, removal)
        separate = ('a separate stent removal (43275)' if (part.get('catalogue_kind') or '') == REMOVAL
                    else 'a separate stent placement (43274)')
        question = (f'Was the {events.event_label(reading, part)} ({said(part)}) part of the '
                    f'{events.event_label(reading, whole)} ({said(whole)}), one stent exchange (43276), or {separate}?')
        reason = ('The document states a stent exchange and a stent removal or placement at this ERCP, in ducts nothing '
                  'in the document sets apart. A removal or a placement that is part of a stent exchange is reported '
                  'with the exchange (43276), not separately (43275, 43274); CPT Studio does not choose between them. '
                  'Held for the reviewer, not excluded.')
        return question, reason
    first, second = events.event_label(reading, removal), events.event_label(reading, placement)
    question = (f'Were the {first} ({said(removal)}) and the {second} ({said(placement)}) one stent exchange (43276), '
                'or separate services (a stent removal, 43275, and a stent placement, 43274)?')
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
    # D127: a pair's first event is its removal or its exchange, its second its exchange or its placement - and a code's
    # own supporting act is never an exchange but for 43276's, which EXCHANGE holds whatever its pair
    pairs = [(first, second) for first, second in exchange_pairs(reading)
             if EXCHANGE in sides or (REMOVAL in sides and first['id'] in own)
             or (PLACEMENT in sides and second['id'] in own)]
    if not pairs:
        return evaluation
    removal, placement = pairs[0]
    question, reason = exchange_question(reading, removal, placement)
    read = tuple(dict.fromkeys(tuple(evaluation.read) + tuple(evaluation.supporting) + (removal['id'], placement['id'])))
    places = events.anchors(reading, removal) + events.anchors(reading, placement)
    return events.Evaluation(evaluation.code, link.family, link, 'uncertain', POSSIBLE_EXCHANGE, reason, read=read,
                             question=events.Question(EXCHANGE_FACT, question, reason, (removal['id'], placement['id']),
                                                      _spans(places)))


# --- D106: a stone removal that retrieved nothing (as DECISIONS D127 completes it) ---------------------------------

STONE_EXTRACTION = 'stone_extraction'
NOTHING_RETRIEVED = 'nothing_retrieved'  # the reason (events.Evaluation.reason) of D106's hold
STONE_WORDS = ('stone', 'stones', 'calculus', 'calculi', 'debris', 'sludge')
RETRIEVAL_WORDS = ('retrieve', 'retrieved', 'retrieves', 'retrieving', 'retrieval', 'extract', 'extracted', 'extracts',
                   'extracting', 'extraction', 'remove', 'removed', 'removes', 'removing', 'removal', 'deliver',
                   'delivered', 'recover', 'recovered', 'yield', 'yielded')
# D127 (disagreement 1(b) of D106's builder): "no stones were found" after a sweep denies its yield as "were retrieved"
# does - the words that make a negation over stones about the act's yield are the retrieval words and these
FIND_WORDS = ('find', 'finds', 'found')
# D127: the negators that are themselves what was retrieved - "nothing was retrieved", "none were extracted" - read
# only beside a retrieval word in their own clause (disagreement 1(a))
OBJECT_NEGATORS = ('nothing', 'none')
# D127 (the review of D106, problem 3): the verbs that state a yield - a stone, calculus, debris or sludge retrieved,
# extracted or removed ("Multiple stones were extracted ... until no stones remained.") - past forms only, never after
# "to" or "be" (an intent: "to extract", "could not be extracted") or a negator. DECISIONS D140 (the review of D127,
# problems 0 and 2): the verb states a yield only with a stone word as its subject (_states_yield) - D127 read any
# stone word of the clause, so "the balloon was removed" beside "swept for stones" was a yield, and "been" before the
# verb ("to ensure all stones had been removed") was no guard.
YIELD_VERBS = ('retrieved', 'extracted', 'removed', 'delivered', 'recovered', 'yielded')
# D140: the subject of a yield - the stone word the past yield verb's clause names before it, at most AUXILIARY_REACH
# auxiliaries between ("several small stones were removed", "all stones have been removed", "two stones extracted").
# The past perfect is not the act's own yield ("had" is no auxiliary here): "to ensure all stones had been removed",
# and "Several stones had been removed ...; no stones remained" is held, as the installed release holds it (act_missing)
YIELD_SUBJECTS = ('stone', 'stones', 'sludge', 'debris', 'calculus', 'calculi', 'fragments')
YIELD_AUXILIARIES = ('was', 'were', 'has', 'have', 'been')
AUXILIARY_REACH = 2
# D140: the words that make a clause's yield no yield of the act's - a purpose ("to ensure", "in order to", "so
# that"), a condition or doubt ("It is unclear whether any stones were removed"), or another time ("after stones were
# removed at the prior ERCP")
PURPOSE_WORDS = ('to',)
PURPOSE_PAIRS = (('so', 'that'),)
DOUBT_WORDS = ('whether', 'if', 'unclear', 'possible', 'possibly', 'may', 'might', 'suspected', 'any')
OTHER_TIME_WORDS = ('prior', 'previous', 'previously', 'earlier', 'index', 'last')
# D140: the attributes whose words are the act's own statement of its yield (the structural reading, EB1)
YIELD_ATTRIBUTES = ('kind', 'status', 'target', 'technique')
# D140 (problem 1): the one status value of an act done; the sentence after the act's own that holds the words of an
# event with any other value (a denial, an uncertain statement, a plan, an act begun and not completed) is never dropped
PERFORMED = 'performed'
# The words between a negator and the stone word that make the negation exceptive (C-7: "no further stones" is about
# stones beyond those the document reports removed) or partial ("not all stones"): such a negation states nothing about
# whether anything was retrieved. D127: "nothing else" is exceptive too.
NOT_NOTHING = ('further', 'other', 'additional', 'more', 'residual', 'remaining', 'retained', 'all', 'every', 'each',
               'both', 'only', 'else')
NEGATOR_REACH = 3  # at most this many words between the negator and the stone word it governs
CLAUSE_BREAKS = frozenset(',;:()[]')
SENTENCE_ENDS = frozenset('.!?')
# D127 (the review of D106, problem 0): the sentence that continues an act begins at most this many characters after
# the act's own sentence ends - in the same passage, or in the located passage or the code's own exact evidence that
# starts on the next line ("...extraction balloon." then "No stones or sludge were retrieved.")
CONTINUES_WITHIN = 2


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


def _clauses(sentence: Mapping) -> list:
    """D127: the clauses of one sentence {start, end, text}, each {start, end, text, tokens}: split at a clause break or
    a sentence end, each clause's folded words (_tokens)."""
    text, start = sentence['text'], sentence['start']
    out, begin = [], 0
    for index, char in enumerate(text + '.'):
        if char in CLAUSE_BREAKS or char in SENTENCE_ENDS or index == len(text):
            piece = text[begin:index]
            tokens = [token for token in _tokens(piece) if token != '|']
            if tokens:
                out.append({'start': start + begin, 'end': start + index, 'text': piece, 'tokens': tokens})
            begin = index + 1
    return out


def _negator(token: str) -> bool:
    return token in lexicon.NEGATORS or token.endswith("n't")


def _governed(tokens: Sequence[str], index: int) -> list:
    """The positions of the stone words the negator at ``index`` governs in its clause: within NEGATOR_REACH words after
    it, before any exceptive or partial word (NOT_NOTHING)."""
    out = []
    for later in range(index + 1, min(len(tokens), index + 2 + NEGATOR_REACH)):
        if tokens[later] in NOT_NOTHING:
            break
        if tokens[later] in STONE_WORDS:
            out.append(later)
    return out


def _denial(clauses: Sequence[Mapping]) -> tuple:
    """D106 over a statement's clauses (D127: the act's own sentence and the sentence that continues it), with a
    retrieval or find word anywhere in the statement: 'retrieval' when a negation denies a retrieval - a negator over a
    stone word (_governed) with a retrieval word in its clause after the negator, or in the two words before it ("no
    stones or sludge were retrieved", "retrieved no stones", "without retrieval of any stones"), or a negator that is
    itself what was retrieved ("nothing was retrieved": OBJECT_NEGATORS, not exceptive, beside a retrieval word in its
    own clause); 'presence' when it denies only that stones were there ("no stones were found", "no stones remained",
    "no stones were seen"); '' when neither - with the clauses of the presence denials."""
    context = any(token in RETRIEVAL_WORDS or token in FIND_WORDS for clause in clauses for token in clause['tokens'])
    presence = []
    for clause in clauses:
        tokens = clause['tokens']
        for index, token in enumerate(tokens):
            if (token in OBJECT_NEGATORS and (index + 1 == len(tokens) or tokens[index + 1] not in NOT_NOTHING)
                    and any(word in RETRIEVAL_WORDS for word in tokens)):
                return 'retrieval', []
            if not context or not _negator(token) or not _governed(tokens, index):
                continue
            if any(word in RETRIEVAL_WORDS for word in tokens[max(0, index - 2):index] + tokens[index + 1:]):
                return 'retrieval', []
            if clause not in presence:
                presence.append(clause)
    return ('presence' if presence else ''), presence


def _guarded(tokens: Sequence[str]) -> bool:
    """D140: whether one clause's folded words hold a purpose word (PURPOSE_WORDS, PURPOSE_PAIRS), a condition or doubt
    word (DOUBT_WORDS) or an other-time word (OTHER_TIME_WORDS): such a clause states no yield of the act's."""
    if any(token in PURPOSE_WORDS or token in DOUBT_WORDS or token in OTHER_TIME_WORDS for token in tokens):
        return True
    return any(pair in PURPOSE_PAIRS for pair in zip(tokens, tokens[1:]))


def _states_yield(tokens: Sequence[str]) -> bool:
    """DECISIONS D140 (the review of D127, problems 0 and 2): whether one clause's folded words state a yield - a past
    yield verb (YIELD_VERBS) no negator precedes whose subject is a stone word (YIELD_SUBJECTS: the word before the
    verb, past at most AUXILIARY_REACH auxiliaries - "several small stones were removed", "all stones have been
    removed"), in a clause that holds no purpose, condition or doubt, or other-time word (_guarded). "The sphincterotome
    was removed and the bile duct was swept for stones" states none (the verb's subject is the device); neither does
    "to ensure all stones had been removed", "It is unclear whether any stones were removed" or "after stones were
    removed at the prior ERCP". D127's intent guard ("to extract", "could not be extracted") is the subject rule's now:
    neither "to" nor "be" is a stone word or an auxiliary, and "to" is a purpose word."""
    if _guarded(tokens):
        return False
    for index, token in enumerate(tokens):
        if token not in YIELD_VERBS or any(_negator(word) for word in tokens[:index]):
            continue
        subject = index - 1
        while subject >= 0 and index - subject <= AUXILIARY_REACH and tokens[subject] in YIELD_AUXILIARIES:
            subject -= 1
        if subject >= 0 and tokens[subject] in YIELD_SUBJECTS:
            return True
    return False


def _attribute_words(event: Mapping) -> list:
    """D140: the located words of the act's own attributes that state its yield (YIELD_ATTRIBUTES: kind, status, target
    and technique), each {start, end, text}."""
    return [event[name]['words'] for name in YIELD_ATTRIBUTES
            if isinstance(event.get(name), Mapping) and isinstance(event[name].get('words'), Mapping)]


def _own_yield(event: Mapping, others: Sequence[Mapping] = ()) -> bool:
    """DECISIONS D140, the structural reading (EB1): whether the act's own attribute words (_attribute_words: kind,
    status, target and technique) state its yield (_states_yield), each clause of those words read in those words alone
    ("Multiple stones were extracted" as the act's kind words) - and none of them another event's words (``others``:
    that event's yield, never this act's)."""
    for item in _attribute_words(event):
        for piece in _clauses(item):
            if not _holds(piece, others) and _states_yield(piece['tokens']):
                return True
    return False


def _yields(clauses: Sequence[Mapping], others: Sequence[Mapping] = (),
            mine: Optional[Sequence[Mapping]] = None) -> bool:
    """D127 (problem 3): whether the act's own sentence (its ``clauses``) states the act's yield; such a sentence's
    denial of the stones' presence is a clearance ("until no stones remained", "no stones remained on the final
    cholangiogram"). DECISIONS D140 (the review of D127, problems 0 and 2): this is the CLAUSE reading, which keeps
    D127's pinned clearances whose yield lies in no attribute's words (_own_yield is the structural one): a clause of
    the sentence that holds one of the act's own words (``mine``: kind, status or target; None: every clause is the
    act's, a sentence read alone) and no other event's (``others``: that event's yield, never this act's) states a
    yield (_states_yield: a stone word the subject of a past yield verb, and no purpose, doubt or other-time word) -
    "Multiple stones were extracted ... until no stones remained." with the kind words "extracted". Never another word
    of the passage: a purpose clause, a device as the subject, a doubt or another time is no yield."""
    for clause in clauses:
        if any(clause['start'] < item['end'] and item['start'] < clause['end'] for item in others):
            continue
        if mine is not None and not any(clause['start'] < item['end'] and item['start'] < clause['end']
                                        for item in mine):
            continue
        if _states_yield(clause['tokens']):
            return True
    return False


def states_nothing_retrieved(text: str) -> bool:
    """D106 over one sentence read alone as the act's own (every clause the act's), as D127 completes it: a negator
    over stones, calculi, debris or sludge (at most NEGATOR_REACH words between, no clause break and no exceptive or
    partial word) beside a retrieval or find word, or "nothing" or "none" retrieved (_denial) - a denial of a retrieval
    always, a denial of the stones' presence only where the sentence states no yield (_yields: "until no stones
    remained" after "Multiple stones were extracted" is a clearance). nothing_retrieved reads an act's own sentence with
    the act's own words: only a clause that holds them states the act's yield."""
    clauses = _clauses({'start': 0, 'end': len(text), 'text': text})
    denial, _ = _denial(clauses)
    return denial == 'retrieval' or (denial == 'presence' and not _yields(clauses))


def _trimmed(place: Mapping) -> dict:
    """``place`` ({start, end, text}) without its surrounding whitespace, its offsets moved with it."""
    text = place['text']
    lead = len(text) - len(text.lstrip())
    body = text.strip()
    return {'start': place['start'] + lead, 'end': place['start'] + lead + len(body), 'text': body}


def _own_words(event: Mapping) -> list:
    return [event[name]['words'] for name in ('kind', 'status', 'target')
            if isinstance(event.get(name), Mapping) and isinstance(event[name].get('words'), Mapping)]


def _holds(place: Mapping, spans: Sequence[Mapping]) -> bool:
    return any(place['start'] < item['end'] and item['start'] < place['end'] for item in spans)


def _kept(kept: Sequence) -> list:
    return [{'start': span.start, 'end': span.end, 'text': span.text} for span in kept or ()
            if getattr(span, 'exact', True) and span.text]


def nothing_retrieved(reading, event: Mapping, kept: Sequence = ()) -> Optional[list]:
    """D106: the act's statement that nothing was retrieved (its places, [{start, end, text}], in document order), else
    None. The act's own sentences are those of its own located passages (events.own_passages: kind, status, target) that
    hold one of its own words (kind, status or target words); a passage of the act none of whose sentences holds them is
    read whole. DECISIONS D127, as the review of D106 asks it:
    - (problem 0) a statement is an own sentence AND the sentence that immediately follows it when that one continues
      the act - it begins within CONTINUES_WITHIN characters of the sentence's end, in the same passage or in a located
      passage or the code's exact evidence (``kept``) that starts there, and holds no other event's own words ("The
      bile duct was swept several times with an extraction balloon. No stones or sludge were retrieved.");
    - (disagreement 1(c)) a sentence of the code's own exact evidence that overlaps one of the act's own passages and
      holds one of its own words is an own sentence too: Gemini's passage may be only the sentence's first clause;
    - (problem 2) only those: another act's sentence in the act's own passage is never read;
    - (problem 3) a sentence that denies only the stones' presence ('presence', _denial) where a clause of it that
      holds the act's own words states a yield (_yields) is a clearance, and denies nothing - unless a presence denial
      sits in a clause that holds another act's words (a sentence of two acts, D106's own sentence read whole: held, as
      before); a denial of a retrieval ('retrieval') in the act's own sentence is read whatever the sentence states
      beside it, as before. An own sentence that states the act's yield is the act's own word on what it retrieved, so
      the sentence after it - read only because it may continue the act - is not read.
    DECISIONS D140, as the review of D127 asks it:
    - (problems 0 and 2) the yield is the act's own statement (_yields: its own attribute words, or a clause of its own
      whose subject is a stone word with a past yield verb, no purpose, doubt or other-time word): "...to ensure all
      stones had been removed; no stones remained." and "The sphincterotome was removed and the bile duct was swept for
      stones ...; no stones were found." state none, so the denial holds - and a false yield no longer stops the read
      of the sentence after ("The sphincterotome was removed and ... . No stones or sludge were retrieved.");
    - (problem 1) the following sentence is never dropped as another act's when it holds the words of an event that is
      not performed (its status value, in any verification state, anything but PERFORMED: a denial or an uncertain
      statement, and a planned act or one begun and not completed): "No stones or sludge were retrieved." filed as its
      own not_performed event is the act's statement, not another act's."""
    from studio.interpretation import events

    words = _own_words(event)
    others = [span for other in reading.events.values() if other.get('id') != event.get('id')
              for span in _own_words(other)]
    # D140 (problem 1): the words of the events that are not performed - a denial or an uncertain statement, and a
    # planned act or one begun and not completed: every status value but 'performed', in any verification state
    unperformed = [span for other in reading.events.values() if other.get('id') != event.get('id')
                   and events.value(other, 'status') != PERFORMED for span in _own_words(other)]
    stated = _own_yield(event, others)  # D140: the act's own words state its yield (the structural reading)
    places = reading.places(events.own_passages(event))
    evidence = [place for place in _kept(kept) if any(_holds(place, [mine]) for mine in places)]
    own, seen = [], set()
    for place in places:
        sentences = _sentences(place)
        for sentence in [item for item in sentences if _holds(item, words)] or sentences:
            if (sentence['start'], sentence['end']) not in seen:
                seen.add((sentence['start'], sentence['end']))
                own.append(sentence)
    for place in evidence:
        for sentence in _sentences(place):
            if _holds(sentence, words) and (sentence['start'], sentence['end']) not in seen:
                seen.add((sentence['start'], sentence['end']))
                own.append(sentence)
    located = [place for record in reading.passages.values() if record.get('state') != 'unlocated'
               for place in record['spans']]
    candidates = [sentence for place in located + _kept(kept) for sentence in _sentences(place)]
    for sentence in sorted(own, key=lambda item: (item['start'], item['end'])):
        clauses = _clauses(sentence)
        yields, (denial, where) = stated or _yields(clauses, others, words), _denial(clauses)
        shared = any(_holds(clause, others) for clause in where)  # a presence denial in a clause of another act's
        if denial == 'retrieval' or (denial == 'presence' and (not yields or shared)):
            return [_trimmed(sentence)]
        if yields:  # the act's own sentence states what it retrieved: a sentence after it never denies that
            continue
        after = [item for item in candidates
                 if sentence['end'] <= item['start'] <= sentence['end'] + CONTINUES_WITHIN]
        first = min((item['start'] for item in after), default=None)
        # D140 (problem 1): another act's sentence does not continue the act - but one that holds the words of an event
        # that is not performed (a denial, an uncertain statement, a plan, an act begun and not completed) is never
        # dropped
        following = list({(item['start'], item['end']): item for item in after if item['start'] == first
                          and (not _holds(item, others) or _holds(item, unperformed))}.values())
        if following and _denial(clauses + [clause for item in following for clause in _clauses(item)])[0]:
            return [_trimmed(item) for item in (sentence, *following)]
    return None


def retrieval_hold(evaluation, reading, kept: Sequence = ()):
    """D106 over one code's evaluation: a READY code of the stone removal (its one requirement group is
    stone_extraction: 43264) whose supporting acts each state that nothing was retrieved is held with the
    performed_status question naming that statement; when another act supports it, the code keeps READY on that act and
    the act that retrieved nothing leaves E* (the decision still read it). Any other evaluation is returned unchanged.
    D127: ``kept`` is the code's own exact evidence, which nothing_retrieved also reads."""
    from studio.interpretation import events

    link = evaluation.link
    if (link.family != ERCP or link.route != mapping.CATALOGUE_ROUTE
            or tuple(events.requirements(link)) != ((STONE_EXTRACTION,),)):
        return evaluation
    if evaluation.state != 'performed' or evaluation.reason != events.SUPPORTED:
        return evaluation
    stated = []
    for eid in evaluation.supporting:
        statement = nothing_retrieved(reading, reading.events[eid], kept)
        if statement is not None:
            stated.append((eid, statement))
    if not stated:
        return evaluation
    apart = {eid for eid, _ in stated}
    left = tuple(eid for eid in evaluation.supporting if eid not in apart)
    if left:
        labels = [events.event_label(reading, reading.events[eid]) for eid in left[:4]]
        return replace(evaluation, supporting=left, detail=f'The {events.service_label(link.family)} is documented as '
                                                           f'performed with {"; ".join(labels)}.')
    eid, statement = stated[0]
    said = ' '.join(' '.join(place['text'].split()) for place in statement)
    act = events.event_label(reading, reading.events[eid])
    question = f'Was any stone, calculus, debris or sludge removed with the {act} ({wording.quote(said, 120)})?'
    reason = (f'The document states that nothing was retrieved with the {act} ({wording.quote(said, 140)}). '
              'CPT Studio does not read a sweep or an extraction that retrieved nothing as a removal of stones or '
              'debris. Held for the reviewer, not excluded.')
    return events.Evaluation(evaluation.code, link.family, link, 'uncertain', NOTHING_RETRIEVED, reason,
                             read=evaluation.read,
                             question=events.Question('performed_status', question, reason, (eid,), _spans(statement)))


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
    return retrieval_hold(exchange_hold(evaluation, reading), reading, kept)  # D127: the code's own exact evidence


# --- D107: an ERCP whose access act was begun and not completed ------------------------------------------------------

ACCESS_KINDS = ('cannulation',)  # the ERCP's access act: the duct's cannulation


def statement_sentence(reading, event: Mapping, name: str = 'status') -> Optional[dict]:
    """DECISIONS D127: the sentence ({start, end, text}) of ``event``'s own located passages that holds its ``name``
    words - the statement that verifies them - else None."""
    from studio.interpretation import events

    record = event.get(name)
    words = record.get('words') if isinstance(record, Mapping) else None
    if not isinstance(words, Mapping):
        return None
    for place in reading.places(events.own_passages(event)):
        for sentence in _sentences(place):
            if sentence['start'] <= words['start'] and words['end'] <= sentence['end']:
                return sentence
    return None


def access_not_completed(reading, family: str) -> Optional[str]:
    """D107: the statement of the first access act of the ERCP session (ACCESS_KINDS) done at this encounter
    (events.done: a usable status, current time and documenting-team performer) whose status is attempted_not_completed
    - "Multiple attempts at biliary cannulation were unsuccessful." - else None; None for any family but the ERCP's.
    DECISIONS D127 (the review of D107, problem 4): the statement is the sentence that holds its verified failure-marker
    words (statement_sentence), as the installed release quotes the sentence that states the failure, no longer the
    bare words ("were unsuccessful"); the words themselves where no own sentence holds them. The session's DEFINING
    access act: a cannulation of the pancreatic duct begun and not completed beside a cannulation of the bile duct
    achieved (both ducts verified, coverage.duct_side) is not the session's access failing - the installed release's
    pancreatic avoidance (detect._pancreatic_avoidance: "a deliberate choice, not a failed ERCP") - so it gives nothing;
    any other begun and not completed, an earlier attempt before the access was achieved included, gives the signals as
    the installed release does."""
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
        sentence = statement_sentence(reading, event)
        if sentence is not None:
            return _trimmed(sentence)['text']
        words = events.words_of(event, 'status')
        return words['text'] if words else ''
    return None


# --- D127: the cannulation stated both achieved and not achieved -----------------------------------------------------

def cannulation_conflict(reading, family: str) -> Optional[tuple]:
    """DECISIONS D127 (the parity audit of D107, note 1): (note, places) of the ERCP session's cannulation outcome when
    the document states it both achieved and not achieved - a cannulation stated performed and one stated begun and not
    completed ("Initial attempts at biliary cannulation were unsuccessful." beside "Deep biliary cannulation was
    achieved with a sphincterotome."), of ducts nothing sets apart (not both verified, coverage.duct_side, and
    different: a pancreatic failure beside the biliary access is D107's avoidance, no conflict) - else None. Each is read
    as a value in any verification state, possibly current (coverage.possibly_current) and not verified as another
    performer's act (D87: a doubted outcome is a question, never a fact). assess._inventory_fact makes it the
    cannulation's conflict Fact, as the installed release's detect._cannulation does ("both documented is a conflict for
    a reviewer, never a pick"), so every ERCP code - the profile requires the cannulation - asks it. ``places``: each
    side's statement (statement_sentence, else its status words), in document order."""
    from studio.interpretation import coverage, events

    if family != ERCP:
        return None
    access = [event for event in reading.events.values() if event.get('family') == ERCP
              and (event.get('catalogue_kind') or '') in ACCESS_KINDS and coverage.possibly_current(event)
              and not events.verified_other_performer(event)]
    for achieved in [event for event in access if events.value(event, 'status') == 'performed']:
        for failed in [event for event in access if events.value(event, 'status') == 'attempted_not_completed']:
            one, two = coverage.duct_side(achieved), coverage.duct_side(failed)
            if one and two and one != two:
                continue
            values, places = [], []
            for event, outcome in ((achieved, 'cannulated'), (failed, 'not achieved')):
                where = wording.landmark_label(mapping.target_landmark(event))
                values.append(f'{where} {outcome}' if where else outcome)
                place = statement_sentence(reading, event) or events.words_of(event, 'status', 'kind', 'target')
                if isinstance(place, Mapping):
                    places.append(_trimmed(place))
            places.sort(key=lambda item: (item['start'], item['end']))
            return 'Conflicting documented values: ' + ', '.join(values) + '.', places
    return None
