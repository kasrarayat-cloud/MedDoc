"""The ERCP rules of the events engine (DECISIONS D105, D106 and D107; the round-4 refutation, findings 22, 25 and 26;
completed by D127, the review of those rules and the family parity audit): holds and signals the per-code rule and the
session's reading give an ERCP's codes, each only ADDING a hold, a question or a warning to what the engine decided
before - never READY, never an exclusion, never another code's question - but for the releases of D106's hold named
below: D127's clearance and D140's structural reading (an act whose own words state its yield: the basket of D127's
two-act sentence). D147's third release, the following sentence of a performed act, is withdrawn (D155).

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

- D147, as the review of D140 asked (problems 0-3 and 5):
  - "fragments" is a yield subject only directly after a stone word ("stone fragments", "calculus fragments"): "the
    remaining stent fragments were retrieved", "plastic fragments were removed" and "the tissue fragments were
    retrieved" retrieved no stones;
  - a yield is the act's own only in the act's own SIMPLE clause - a clause cut before each word that opens a new one
    (CLAUSE_OPENERS: "after", "when", "and", "then" ...). The clause reading takes a yield only from a simple clause that
    holds one of the act's own words, the guard words still read over the whole clause ("The bile duct was swept with
    an extraction balloon after stones were removed at an outside hospital" states no yield of the sweep's). The
    structural reading takes the act's attribute words as its yield only where no clause of a located passage that
    holds those words carries a guard word ("It is unclear whether any stones were removed when ..." with the kind words
    "stones were removed");
  - (withdrawn by D155) the sentence that follows the act's own is dropped as another act's when it holds the own words
    of another event whose status is 'performed', and read when the only other events whose words it holds are not
    performed - so D140's hold is released where a performed act's sentence also names a plan ("Two stones were
    extracted with a basket; ... and a repeat ERCP is planned.").

- D155, round 5e (narrowing only; the review of D147, review:ercp4 problems 0 and 6, and its builder's disagreements 2
  and 5):
  - D147's third rule is withdrawn: D140's following-sentence condition is restored - the sentence after the act's own
    is read when it holds no other event's own words OR holds the words of an event that is not performed (a denial, an
    uncertain statement, a plan, an act begun and not completed), whatever performed events' words it also holds;
  - the sentence after the act's own that is dropped as another act's is still read for its DENIAL CLAUSE: a clause of
    it (cut at CLAUSE_BREAKS) that holds no other event's own words and, read with the act's own sentence, denies the
    retrieval or the stones' presence (_denial) is the act's statement, whatever the sentence's other clauses hold -
    "The bile duct was swept with an extraction balloon. No stones were retrieved, and a plastic biliary stent was
    placed." (the stent filed) holds 43264. It only adds a hold.

- DECISIONS D168, round 5g (narrowing only; round 5f's ercp6, D159, not integrated, rebuilt without review:ercp6
  problem 1; that review's problems 3 and 4; review:colon5 problem 0). D155's reading is unchanged and runs first; only
  where it states nothing do D159's two WIDENED reads give the act's statement (D168 (1)):
  - D159's rule (1): a clause of the sentence D155 drops as another act's is the act's statement WHATEVER other events'
    words it holds - "No stones were retrieved and a plastic biliary stent was placed." holds 43264 as "No stones were
    retrieved; a plastic biliary stent was placed." does;
  - D159's rule (3): a LATER sentence of the act's own passage, past the one right after the act's own, is read for a
    denial clause that holds no other event's own words - "... A plastic biliary stent was placed. No stones were
    retrieved." holds 43264;
  - one structural condition decides WHOSE such a denial is. Where the sentence it sits in - or, for rule (3), a
    sentence between the act's own and it - holds the own words of ANOTHER performed stone extraction that supports
    the same code (a second sweep or extraction), the denial is that act's, never this act's, when this act's own
    sentence states its own yield (_clause_yield): "The bile duct was swept with an extraction balloon and two stones
    were removed. The pancreatic duct was then swept with a balloon and no stones were seen." stays READY on both
    sweeps, never on the pancreatic one alone. When it states none, the denial stays this act's statement. That
    own-yield reading is read nowhere else, so it never stops a denial D155 reads;
  - D168 (2): after an own sentence that states the act's yield, a later sentence's RETRIEVAL denial is still read, as
    D127 reads one in the act's own sentence - "... and two stones were removed. A plastic biliary stent was placed. No
    stones were retrieved." holds 43264; a presence denial there is still a clearance;
  - a widened statement only ever HOLDS the code. Where another act still supports it, every act stays in E* as D155
    leaves it (retrieval_hold), so no READY code's acts change;
  - D168 (3): the another_role hold (events.another_role_hold, D124 and D158) of a code these rules would hold as a
    possible exchange (D105) or as nothing retrieved (D106) keeps its question, and the ERCP question is its SECOND
    clarification (role_second; events.Evaluation.second, D161's mechanism), so neither question is dropped.

- DECISIONS D173, round 5h (narrowing only; refute6 families findings 7 and 8, judges findings 8 and 9, review:ercp7
  problems 0-2). Each rule only HOLDS a code, or keeps in E* an act whose own sentence states its yield and that D155's
  reading took out of it for another act's denial:
  - (1) whose denial, for E*: D168's condition now covers D155's own arm too, but only where the acts of a code still
    READY are chosen (retrieval_hold; nothing_retrieved with ``whose``). A clause of the sentence D155 drops as another
    act's, where that sentence holds the own words of a RIVAL (another performed stone extraction supporting the same
    code) and this act's own sentence states its own yield (_own_sentence_yield), is the rival's denial: "The bile duct
    was swept with an extraction balloon and two stones were removed. The pancreatic duct was then swept with a balloon;
    no stones were seen." is READY on both sweeps, as at e5628be56, never on the pancreatic one alone. The hold is still
    decided by D155's reading as it was: there the condition would release "... and two stones were removed. The
    pancreatic duct was then swept with an extraction balloon, and no stones were retrieved." (both sweeps deny);
  - (2) D168's rule (3) reads past a rival's sentence: only a later sentence that itself holds a rival's own words is
    the rival's, so "... and two stones were removed. The pancreatic duct was then swept with a balloon. No stones were
    retrieved from the bile duct." holds 43264;
  - (3), (4) and (6) 43264 never stands on acts that state no yield: when no act of its E* states a stone yield of its
    own (_states_own_yield: its attribute words, its own sentences or the sentence that continues one) or is done to a
    finding the inventory lists (its target names a lesion: _done_to_a_finding) with no statement of its own that
    nothing was retrieved, the code is held - D106's question on the statement of an act E* keeps ("The bile duct was
    swept with an extraction balloon. The pancreatic duct was then swept with a balloon and no stones were seen.": the
    denial stays the bile-duct sweep's), else NO_YIELD's ("The bile duct was swept several times with an extraction
    balloon." after a cholangiogram without filling defects; a basket sweep left alone beside the extraction "Three
    stones, the largest 9 mm, were extracted ..." / "No stones remained." that D155's reading takes out of E*);
  - (4) the yield across an appositive (_appositive_yield: "Three stones, the largest 9 mm, were extracted") is read
    only by (1)'s whose-denial and by (3)'s test of an act E* keeps - never as a clearance of D106's hold;
  - (5) a READY 43276 whose every exchange is named only apart from the sentence that states it done - no sentence of
    its kind passages (a 'Procedure:' title) holds its status words outside its kind words (_named_only_apart) - with
    no stent removal or placement D105 pairs beside it, is held [performed_status] (EXCHANGE_TITLE): "Procedure: ERCP
    with biliary stent exchange." over a body that states only a placement;
  - (7) the own-yield readings never count a yield whose clause holds the time words of another event that the time
    reader places off this date (_other_times: facts.day_of, the event's time earlier_encounter or future in any
    verification state).

Where they run: D105 and D106 sit inside the per-code rule itself - ``ruled`` is events.evaluate's one call site, its
first statement - so every reader of the per-code rule (the assessment, its participants and second review, and the
review overlay's counted codes, overlay.counted_codes: "the evaluation the engine made, made again") reads one
evaluation, and events.evaluate stays the function its module defines. D107 is read by assess._incomplete_session.
DECISIONS D168 (3): events.evaluate hands its another_role hold to ``role_second`` (the one other place this module is
called from there), so the ERCP question about the acts that hold names is that same one evaluation's second.

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
EXCHANGE_TITLE = 'exchange_named_apart'  # DECISIONS D173 (5): the reason of the hold of an exchange named only apart
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


def _named_only_apart(reading, event: Mapping) -> bool:
    """DECISIONS D173 (5) (refute6 judges finding 8): whether the act is named only apart from the sentence that states
    it done - no sentence of its kind passages (the passages Gemini cites for its kind) holds its status words outside
    its kind words. "Procedure: ERCP with biliary stent exchange." as the exchange's kind words, with the status words
    "was placed" in "A 10 Fr x 9 cm plastic biliary stent was placed into the common bile duct." (a sentence that names
    no exchange) or with the title's own words as its status words ("stent exchange", inside the kind words): named only
    apart. "The existing biliary stent was exchanged ..." with the kind words "exchanged" and the status words "was
    exchanged": stated. An act with no kind or no status words is named only apart. Read in the event's own words and
    its own cited passages only (EB1), never a scan of the document."""
    from studio.interpretation import events

    kind, status = events.words_of(event, 'kind'), events.words_of(event, 'status')
    if kind is None or status is None:
        return True
    if kind['start'] <= status['start'] and status['end'] <= kind['end']:
        return True  # the status words lie inside the kind words: they state nothing the name does not
    for place in reading.places(events.own_passages(event, ('kind',))):
        for sentence in _sentences(place):
            if _holds(sentence, [status]):
                return False
    return True


def _exchange_named_apart_hold(evaluation, reading):
    """DECISIONS D173 (5): the hold of a READY 43276 whose every exchange is named only apart (_named_only_apart) and
    beside which no stent removal or placement pairs (exchange_pairs: no removal stated at this ERCP that the exchange
    could include) - the performed_status question quoting the words that name the exchange and the sentence that states
    the act. Never READY, never excluded: 43276 is a stent removed and replaced in the same duct at one session, as the
    installed release holds it (act_missing)."""
    from studio.interpretation import events

    link = evaluation.link
    event = reading.events[evaluation.supporting[0]]
    named = events.words_of(event, 'kind')
    named_in = (next((_trimmed(sentence) for place in reading.places(events.own_passages(event, ('kind',)))
                      for sentence in _sentences(place) if named is not None and _holds(sentence, [named])), None)
                or (dict(named) if named is not None else None))
    stated = statement_sentence(reading, event)
    stated = _trimmed(stated) if stated is not None else None
    if stated is not None and named_in is not None and _holds(stated, [named_in]):
        stated = None
    title = named_in['text'] if named_in is not None else events.statement_text(reading, event)
    question = (f'Was a stent removed and replaced in the same duct at this ERCP, one stent exchange (43276), where '
                f'the document names the exchange only in {wording.quote(title, 120)}'
                + (f' and states the act in {wording.quote(stated["text"], 120)}' if stated is not None else '') + '?')
    reason = (f'The document names a stent exchange only in {wording.quote(title, 140)}'
              + (f', apart from the sentence that states the act ({wording.quote(stated["text"], 140)})'
                 if stated is not None else '')
              + ', and states no stent removal at this ERCP that the exchange could include. A stent exchange (43276) '
                'is a stent removed and replaced in the same duct at one session. Held for the reviewer, not excluded.')
    places = [place for place in (named_in, stated) if isinstance(place, Mapping)]
    return events.Evaluation(evaluation.code, link.family, link, 'uncertain', EXCHANGE_TITLE, reason,
                             read=tuple(dict.fromkeys(tuple(evaluation.read) + tuple(evaluation.supporting))),
                             question=events.Question(EXCHANGE_FACT, question, reason, tuple(evaluation.supporting),
                                                      _spans(places)))


def exchange_hold(evaluation, reading):
    """D105 over one code's evaluation: a READY 43275 or 43274 whose own removal or placement is a side of a possible
    exchange (exchange_pairs), and a READY or not-documented 43276 in a session with one, held with the exchange question
    (the first such pair). Any other evaluation is returned unchanged: a code held for another reason keeps its own
    question (D89: a question is never displaced), and an exclusion stands. DECISIONS D173 (5) (refute6 judges finding
    8): a READY 43276 in a session with no such pair, whose every supporting act is a stent exchange named only apart
    from the sentence that states it done (_named_only_apart: "Procedure: ERCP with biliary stent exchange." over a body
    that states only a placement, the old stent left in place, not removed, migrated, removed at an earlier ERCP or from
    the other duct), is held [performed_status] (_exchange_named_apart_hold), as the installed release holds it."""
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
        if (ready and EXCHANGE in sides and evaluation.supporting
                and all((reading.events[eid].get('catalogue_kind') or '') == EXCHANGE
                        and _named_only_apart(reading, reading.events[eid]) for eid in evaluation.supporting)):
            return _exchange_named_apart_hold(evaluation, reading)  # DECISIONS D173 (5)
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
NO_YIELD = 'no_yield'  # DECISIONS D173 (3), (4), (6): the reason of the hold of 43264 on acts that state no yield
# DECISIONS D173 (7): the time values of another occasion (events.verified_other_time's, read in any verification state)
OTHER_TIMES = ('earlier_encounter', 'future')
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
YIELD_SUBJECTS = ('stone', 'stones', 'sludge', 'debris', 'calculus', 'calculi')
# DECISIONS D147 (the review of D140, problem 0): "fragments" is a yield subject only directly after one of
# YIELD_SUBJECTS ("stone fragments", "calculus fragments") - "the remaining stent fragments were retrieved", "plastic
# fragments were removed" and "the tissue fragments were retrieved" retrieved no stones
FRAGMENT_WORDS = ('fragments',)
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
# event with any other value (a denial, an uncertain statement, a plan, an act begun and not completed) is never dropped.
# DECISIONS D147 (the review of D140, problem 3) dropped it when it also held a performed event's own words; DECISIONS
# D155 withdraws that and restores D140's condition
PERFORMED = 'performed'
# The words between a negator and the stone word that make the negation exceptive (C-7: "no further stones" is about
# stones beyond those the document reports removed) or partial ("not all stones"): such a negation states nothing about
# whether anything was retrieved. D127: "nothing else" is exceptive too.
NOT_NOTHING = ('further', 'other', 'additional', 'more', 'residual', 'remaining', 'retained', 'all', 'every', 'each',
               'both', 'only', 'else')
NEGATOR_REACH = 3  # at most this many words between the negator and the stone word it governs
CLAUSE_BREAKS = frozenset(',;:()[]')
SENTENCE_ENDS = frozenset('.!?')
# DECISIONS D147 (the review of D140, problems 1 and 2): the words that open a new SIMPLE clause inside a clause
# (CLAUSE_BREAKS) - a clause is cut before each, and a yield is the act's own only in the act's own simple clause
CLAUSE_OPENERS = ('after', 'before', 'since', 'when', 'whenever', 'while', 'once', 'until', 'till', 'as', 'because',
                  'although', 'though', 'whereas', 'where', 'and', 'but', 'then')
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


def _words(place: Mapping) -> list:
    """DECISIONS D147: the folded words of one place ({start, end, text}) - the words _tokens reads, in order, with no
    clause-break marks - each (token, start, end) in document offsets."""
    out, word, where = [], [], []

    def close() -> None:
        token = ''.join(word)
        if token and not token.endswith("n't"):
            token = token.strip("'")
        if token:
            out.append((token, place['start'] + where[0], place['start'] + where[-1] + 1))
        word.clear()
        where.clear()

    for index, char in enumerate(place['text']):
        for piece in lexicon.fold_char(char):
            if piece.isalnum() or piece == "'":
                word.append(piece)
                where.append(index)
            elif word:
                close()
    if word:
        close()
    return out


def _simple_clause(words: Sequence, index: int) -> tuple:
    """DECISIONS D147: (first, last), the positions in ``words`` (_words of one clause) of the simple clause that holds
    the word at ``index`` - the clause is cut before each word that opens a new one (CLAUSE_OPENERS): "The bile duct was
    swept with an extraction balloon | after stones were removed at an outside hospital"."""
    first = index
    while first > 0 and words[first][0] not in CLAUSE_OPENERS:
        first -= 1
    last = index
    while last + 1 < len(words) and words[last + 1][0] not in CLAUSE_OPENERS:
        last += 1
    return first, last


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


def _yield_pairs(tokens: Sequence[str]) -> list:
    """DECISIONS D140 (the review of D127, problems 0 and 2): (subject, verb), the positions in one clause's folded words
    of each yield they state, guard words aside - a past yield verb (YIELD_VERBS) no negator precedes whose subject is a
    stone word (YIELD_SUBJECTS: the word before the verb, past at most AUXILIARY_REACH auxiliaries - "several small
    stones were removed", "all stones have been removed"). "The sphincterotome was removed and the bile duct was swept
    for stones" states none (the verb's subject is the device). D127's intent guard ("to extract", "could not be
    extracted") is the subject rule's now: neither "to" nor "be" is a stone word or an auxiliary. DECISIONS D147 (the
    review of D140, problem 0): "fragments" (FRAGMENT_WORDS) is a subject only directly after a stone word - "stone
    fragments were removed" states a yield, "the remaining stent fragments were retrieved" none."""
    out = []
    for index, token in enumerate(tokens):
        if token not in YIELD_VERBS or any(_negator(word) for word in tokens[:index]):
            continue
        subject = index - 1
        while subject >= 0 and index - subject <= AUXILIARY_REACH and tokens[subject] in YIELD_AUXILIARIES:
            subject -= 1
        if subject >= 0 and (tokens[subject] in YIELD_SUBJECTS or (tokens[subject] in FRAGMENT_WORDS and subject > 0
                                                                  and tokens[subject - 1] in YIELD_SUBJECTS)):
            out.append((subject, index))
    return out


def _states_yield(tokens: Sequence[str]) -> bool:
    """DECISIONS D140: whether one clause's folded words state a yield (_yield_pairs) in a clause that holds no purpose,
    condition or doubt, or other-time word (_guarded): "to ensure all stones had been removed", "It is unclear whether
    any stones were removed" and "after stones were removed at the prior ERCP" state none ("to" is a purpose word)."""
    return not _guarded(tokens) and bool(_yield_pairs(tokens))


def _simple_yield(place: Mapping, mine: Optional[Sequence[Mapping]] = None) -> bool:
    """DECISIONS D147 (the review of D140, problems 1 and 2): whether one clause ``place`` ({start, end, text}) states a
    yield (_yield_pairs) whose verb and subject stand in one SIMPLE clause (_simple_clause: the clause cut before each
    word that opens a new one) that holds one of ``mine`` (the act's own words; None: every simple clause is the act's).
    The caller reads the guard words over the whole clause."""
    words = _words(place)
    for subject, verb in _yield_pairs([word[0] for word in words]):
        first, last = _simple_clause(words, verb)
        if first <= subject and (mine is None or _holds({'start': words[first][1], 'end': words[last][2]}, mine)):
            return True
    return False


def _attribute_words(event: Mapping) -> list:
    """D140: the located words of the act's own attributes that state its yield (YIELD_ATTRIBUTES: kind, status, target
    and technique), each {start, end, text}."""
    return [event[name]['words'] for name in YIELD_ATTRIBUTES
            if isinstance(event.get(name), Mapping) and isinstance(event[name].get('words'), Mapping)]


def _own_yield(event: Mapping, others: Sequence[Mapping] = (), located: Sequence[Mapping] = (),
               times: Sequence[Mapping] = ()) -> bool:
    """DECISIONS D140, the structural reading (EB1): whether the act's own attribute words (_attribute_words: kind,
    status, target and technique) state its yield (_states_yield), each clause of those words read in those words alone
    ("Multiple stones were extracted" as the act's kind words) - and none of them another event's words (``others``:
    that event's yield, never this act's). DECISIONS D147 (the review of D140, problem 2): only where no clause of a
    located passage (``located``) that holds those words carries a guard word (_guarded) - "It is unclear whether any
    stones were removed when ..." with the kind words "stones were removed" states no yield of the act's - and words no
    located passage holds state none; the yield's verb and subject stand in one simple clause of those words
    (_simple_yield). DECISIONS D173 (7): ``times`` (another occasion's time words, _other_times; D155's reading passes
    none) - a clause of the words, or of a located passage around them, that holds them states no yield."""
    for item in _attribute_words(event):
        around = [clause for place in located for clause in _clauses(place) if _holds(clause, [item])]
        if not around or any(_guarded(clause['tokens']) or _holds(clause, times) for clause in around):
            continue
        for piece in _clauses(item):
            if not _holds(piece, others) and not _guarded(piece['tokens']) and _simple_yield(piece):
                return True
    return False


def _yields(clauses: Sequence[Mapping], others: Sequence[Mapping] = (),
            mine: Optional[Sequence[Mapping]] = None) -> bool:
    """D127 (problem 3): whether the act's own sentence (its ``clauses``) states the act's yield; such a sentence's
    denial of the stones' presence is a clearance ("until no stones remained", "no stones remained on the final
    cholangiogram"). DECISIONS D140 (the review of D127, problems 0 and 2): this is the CLAUSE reading, which keeps
    D127's pinned clearances whose yield lies in no attribute's words (_own_yield is the structural one): a clause of
    the sentence that holds one of the act's own words (``mine``: kind, status or target; None: every clause is the
    act's, a sentence read alone) and no other event's (``others``: that event's yield, never this act's), and no
    purpose, condition or doubt, or other-time word (_guarded), states a yield - a stone word the subject of a past
    yield verb (_yield_pairs). DECISIONS D147 (the review of D140, problems 1 and 5): the yield's verb and subject must
    stand in the act's own SIMPLE clause - the clause cut before each word that opens a new one (CLAUSE_OPENERS), the
    simple clause holding one of the act's own words (_simple_yield) - while the guard words are read over the whole
    clause: "Multiple stones were extracted ... until no stones remained." with the kind words "extracted" states the
    act's yield; "The bile duct was swept with an extraction balloon after stones were removed at an outside hospital"
    with the sweep's words states none. Never another word of the passage: a purpose clause, a device as the subject,
    a doubt or another time is no yield."""
    for clause in clauses:
        if _holds(clause, others):
            continue
        if mine is not None and not _holds(clause, mine):
            continue
        if not _guarded(clause['tokens']) and _simple_yield(clause, mine):
            return True
    return False


def _clause_yield(clauses: Sequence[Mapping], others: Sequence[Mapping], times: Sequence[Mapping] = ()) -> bool:
    """DECISIONS D168 (1) (review:ercp6 problem 1): whether the act's OWN sentence (its ``clauses``) states a stone
    yield in a clause that holds no other event's own words (``others``) - a stone word the subject of a past yield
    verb, with D140's guards: no purpose, condition or doubt, or other-time word (_states_yield) - in ANY of its
    clauses: "The bile duct was swept with an extraction balloon and two stones were removed." states the sweep's yield
    here, where D147's simple-clause reading (_yields) does not. Read ONLY where a widened read meets a denial in
    another performed stone extraction's words (nothing_retrieved, _later_statement): it decides that such a denial is
    the other act's, and is read nowhere else, so it never stops a denial D155 reads. DECISIONS D173 (review:ercp7
    problem 2): (7) a clause that holds another occasion's time words (``times``: _other_times, the time reader's)
    states no yield of this act ("... and two stones were removed two weeks ago." with that earlier removal filed as its
    own event, its time words there); and the condition is also read for E* (D173 (1)) and by D173 (3)'s test of an act
    E* keeps (_own_sentence_yield) - each only ever holding a code or keeping an act in E*."""
    return any(not _holds(clause, others) and not _holds(clause, times) and _states_yield(clause['tokens'])
               for clause in clauses)


def _nominal(tokens: Sequence[str]) -> bool:
    """DECISIONS D173 (4): whether one clause's folded words can be a subject's noun phrase or its appositive - no past
    yield verb, auxiliary, clause opener or negator among them ("Three stones", "the largest 9 mm")."""
    return not any(token in YIELD_VERBS or token in YIELD_AUXILIARIES or token in CLAUSE_OPENERS or _negator(token)
                   for token in tokens)


def _appositive_yield(clauses: Sequence[Mapping], others: Sequence[Mapping] = (),
                      times: Sequence[Mapping] = ()) -> bool:
    """DECISIONS D173 (4) (refute6 families finding 8; FRESH-2 fb13's attested "Three stones, the largest 9 mm, were
    extracted from the bile duct with an extraction balloon."): whether one sentence (its ``clauses``, cut at
    CLAUSE_BREAKS) states a stone yield ACROSS an appositive, which D140's subject rule cannot read across the commas -
    a clause that opens with a past yield verb (YIELD_VERBS, after at most AUXILIARY_REACH auxiliaries) right after a
    run of nominal clauses (_nominal: the subject's noun phrase and its appositive), the run's FIRST clause ending in
    the subject, a stone word (YIELD_SUBJECTS, or "fragments" right after one); D140's guards read over the words from
    that clause through the verb's clause (_guarded); none of those clauses holding another event's own words
    (``others``) or another occasion's time words (``times``, D173 (7)). "The balloon, used for the stones, was removed"
    states none (its subject is the device). Read ONLY to decide whose a denial is (nothing_retrieved with ``whose``,
    for E*) and whether an act E* keeps states a yield (_own_sentence_yield) - never as a clearance of D106's hold, so
    it never releases one."""
    for index in range(1, len(clauses)):
        tokens = clauses[index]['tokens']
        lead = 0
        while lead < len(tokens) and lead < AUXILIARY_REACH and tokens[lead] in YIELD_AUXILIARIES:
            lead += 1
        if lead >= len(tokens) or tokens[lead] not in YIELD_VERBS:
            continue
        first = index
        while first > 0 and _nominal(clauses[first - 1]['tokens']):
            first -= 1
        if first == index:
            continue
        head = clauses[first]['tokens']
        if not (head[-1] in YIELD_SUBJECTS
                or (head[-1] in FRAGMENT_WORDS and len(head) > 1 and head[-2] in YIELD_SUBJECTS)):
            continue
        span = clauses[first:index + 1]
        if _guarded([token for clause in span for token in clause['tokens']]):
            continue
        if any(_holds(clause, others) or _holds(clause, times) for clause in span):
            continue
        return True
    return False


def _free_simple_yield(clauses: Sequence[Mapping], others: Sequence[Mapping] = (),
                       times: Sequence[Mapping] = ()) -> bool:
    """DECISIONS D173 (3): whether one sentence (its ``clauses``) states a stone yield in a SIMPLE clause
    (_simple_clause: cut before each of CLAUSE_OPENERS) that holds no other event's own words (``others``) and no other
    occasion's time words (``times``), its subject and verb in that simple clause (_yield_pairs), D140's guards read
    over the whole clause as D147 reads them: "The bile duct was swept with an extraction balloon and sludge was
    retrieved and a plastic stent was placed." (the stent filed) states the sweep's yield in "and sludge was
    retrieved"."""
    for clause in clauses:
        if _guarded(clause['tokens']):
            continue
        words = _words(clause)
        for subject, verb in _yield_pairs([word[0] for word in words]):
            first, last = _simple_clause(words, verb)
            span = {'start': words[first][1], 'end': words[last][2]}
            if first <= subject and not _holds(span, others) and not _holds(span, times):
                return True
    return False


def _own_sentence_yield(clauses: Sequence[Mapping], others: Sequence[Mapping] = (),
                        times: Sequence[Mapping] = ()) -> bool:
    """DECISIONS D173 (1), (3), (4): whether one of the act's own sentences (its ``clauses``) states the act's stone
    yield - in any clause that holds no other event's own words (_clause_yield, D168's reading), across an appositive
    (_appositive_yield) or in a simple clause free of other events' words (_free_simple_yield) - each without another
    occasion's time words (D173 (7)). Read only to decide whose a denial in a rival's sentence is, for E* (D173 (1)),
    and whether an act E* keeps states a yield (_states_own_yield) - so it only ever holds a code, or keeps an act in E*
    whose own sentence states that it removed stones; never a clearance of D106's hold."""
    return (_clause_yield(clauses, others, times) or _appositive_yield(clauses, others, times)
            or _free_simple_yield(clauses, others, times))


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


def _rivals(reading, event: Mapping, beside: Sequence[str]) -> list:
    """DECISIONS D168 (1): the own words (kind, status, target) of the act's RIVALS - each of ``beside`` (the code's
    supporting acts) that is another performed stone extraction."""
    from studio.interpretation import events

    return [span for eid in dict.fromkeys(beside) if eid != event.get('id') and eid in reading.events
            and events.value(reading.events[eid], 'status') == PERFORMED
            and (reading.events[eid].get('catalogue_kind') or '') == STONE_EXTRACTION
            for span in _own_words(reading.events[eid])]


def _other_times(reading, event: Mapping) -> list:
    """DECISIONS D173 (7) (review:ercp7 problem 2): another occasion's time words - the located time words of every
    other event whose time is another encounter's, as the time reader places it: its time value earlier_encounter or
    future (events.verified_other_time's values, read in any verification state: D87, a doubted other time is a doubt,
    never this act's yield) and facts.day_of not placing it ON the date of service by its own words. A yield clause that
    holds them is no yield of this act ("... and two stones were removed two weeks ago." with that earlier removal filed
    as its own event, its time words "two weeks ago"). Words no event's time gives are never read as a time (no word
    list)."""
    from studio.interpretation import events, facts

    out = []
    for other in reading.events.values():
        if other.get('id') == event.get('id') or events.value(other, 'time') not in OTHER_TIMES:
            continue
        words = events.words_of(other, 'time')
        if words is not None and facts.day_of(other, None) != facts.ON:
            out.append(words)
    return out


def _later_statement(places: Sequence[Mapping], anchors: Mapping, others: Sequence[Mapping],
                     rivals: Sequence[Mapping], times: Sequence[Mapping] = ()) -> Optional[list]:
    """DECISIONS D168 (1), D159's rule (3) rebuilt (review:ercp5 problem 5): the act's statement in a LATER sentence of
    its own passage (each of ``places``, its own located passages), else None. Within a place, a sentence after an own
    sentence (``anchors``: (the sentence, its clauses, whether it states the act's yield) by its (start, end)) and past
    the one immediately after it (D127, D140 and D155 read that one) is read with the nearest own sentence before it,
    for a denial only, as D127 reads the following sentence: its first clause (_clauses, cut at CLAUSE_BREAKS) that
    holds no other event's own words and, read with that own sentence (_denial), denies the retrieval or the stones'
    presence is the act's statement, and that own sentence and the clause are returned ("The bile duct was swept with an
    extraction balloon. A plastic biliary stent was placed. No stones were retrieved." with the stent filed). Never
    another passage (EB1: the act's own words, not a scan of the document) and never a sentence before the act's own.
    - Whose denial (review:ercp6 problem 1, as DECISIONS D173 (2) narrows it, review:ercp7 problem 0): a later sentence
      that ITSELF holds the own words of another performed stone extraction that supports the same code (``rivals``)
      holds that act's denial, never this act's, when the own sentence states this act's yield (its D147 reading, or
      _clause_yield's). Where it states none, the denial stays this act's statement. A later sentence AFTER the rival's
      is read again, as for any act: "The bile duct was swept with an extraction balloon and two stones were removed.
      The pancreatic duct was then swept with a balloon. No stones were retrieved from the bile duct." is the bile-duct
      sweep's statement (D168 read every sentence past the rival's as the rival's). D173 (7): the own yield is read
      without another occasion's time words (``times``).
    - DECISIONS D168 (2) (review:ercp6 problem 3): after an own sentence that states the act's yield (D147's reading)
      only a RETRIEVAL denial is read, as D127 reads one in the own sentence - "... and two stones were removed. A
      plastic biliary stent was placed. No stones were retrieved." holds 43264, while "... No stones remained." there is
      a clearance, as before (D159 read nothing after such a sentence).
    It only turns a None into a statement, and retrieval_hold lets such a statement only hold the code."""
    for place in places:
        anchor, at = None, -1
        for index, item in enumerate(_sentences(place)):
            if (item['start'], item['end']) in anchors:
                anchor, at = anchors[(item['start'], item['end'])], index
                continue
            if anchor is None:
                continue
            rival = _holds(item, rivals)  # D173 (2): this later sentence itself holds a rival's own words
            if index == at + 1 or (rival and (anchor[2] or _clause_yield(anchor[1], others, times))):
                continue
            for clause in _clauses(item):
                found = '' if _holds(clause, others) else _denial(anchor[1] + [clause])[0]
                if found == 'retrieval' or (found and not anchor[2]):  # D168 (2): after a yield, a retrieval only
                    return [_trimmed(anchor[0]), _trimmed(clause)]
    return None


def nothing_retrieved(reading, event: Mapping, kept: Sequence = (), beside: Sequence[str] = (), *,
                      widened: bool = True, whose: bool = False) -> Optional[list]:
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
    - (problems 0 and 2) the yield is the act's own statement - its own attribute words (_own_yield, the structural
      reading), or a clause of its own whose subject is a stone word with a past yield verb, no purpose, doubt or
      other-time word (_yields, the clause reading): "...to ensure all stones had been removed; no stones remained." and
      "The sphincterotome was removed and the bile duct was swept for stones ...; no stones were found." state none, so
      the denial holds - and a false yield no longer stops the read of the sentence after ("The sphincterotome was
      removed and ... . No stones or sludge were retrieved.");
    - (problem 1) the following sentence is never dropped as another act's when it holds the words of an event that is
      not performed (its status value, in any verification state, anything but PERFORMED: a denial or an uncertain
      statement, and a planned act or one begun and not completed): "No stones or sludge were retrieved." filed as its
      own not_performed event is the act's statement, not another act's.
    DECISIONS D147, as the review of D140 asks it:
    - (problems 1 and 2) the yield stands in the act's own simple clause (_yields), and the act's attribute words are
      its yield only where no clause of a located passage that holds them carries a guard word (_own_yield);
    - (problem 3, WITHDRAWN by D155) the following sentence was dropped as another act's when it held the own words of
      another event whose status value was PERFORMED, whatever else it held.
    DECISIONS D155 (round 5e, narrowing only):
    - D140's following-sentence condition is restored: the sentence is read when it holds no other event's own words or
      holds the words of an event that is not performed, whatever performed events' words it also holds - "Two stones
      were extracted with a basket; ... and a repeat ERCP is planned." is read again, as at D140;
    - a following sentence dropped as another act's (it holds a performed event's own words and no event's that is not
      performed) is read for its denial clause: a clause of it (_clauses: cut at CLAUSE_BREAKS) that holds no other
      event's own words and, read with the act's own sentence, denies the retrieval or the stones' presence (_denial) is
      the act's statement, whatever the sentence's other clauses hold - the act's own sentence and that clause are
      returned: "The bile duct was swept with an extraction balloon. No stones were retrieved, and a plastic biliary
      stent was placed." with the stent filed. It only adds a hold.
    DECISIONS D168 (round 5g, narrowing only; D159's rules (1) and (3) rebuilt without review:ercp6 problem 1). D155's
    reading above runs first and is unchanged (``widened`` False: it alone). Only where it states nothing are two
    WIDENED reads made, and each only turns a None into a statement:
    - D159's rule (1): a clause of the sentence dropped as another act's that holds another event's own words and, read
      with the act's own sentence, denies the retrieval or the stones' presence is the act's statement, the own sentence
      and the clause returned: "No stones were retrieved and a plastic biliary stent was placed.", "A plastic biliary
      stent was placed because no stones were retrieved." and "The pancreatic duct was then swept with a balloon and no
      stones were retrieved." (the pancreatic sweep filed) hold as the ';' forms do;
    - D159's rule (3): a later sentence of the act's own passage, read for a denial (_later_statement: "... A plastic
      biliary stent was placed. No stones were retrieved."), with D168 (2)'s retrieval denial after an own yield;
    - WHOSE denial (review:ercp6 problem 1): ``beside`` is the code's other supporting acts (retrieval_hold's). A
      dropped sentence that holds the own words of one of them that is a performed stone extraction (a second sweep or
      extraction) is read for this act only when the act's own sentence states no yield of its own (_clause_yield,
      read here and in _later_statement only); where it states one, the denial is the other act's: "The bile duct was
      swept with an extraction balloon and two stones were removed. The pancreatic duct was then swept with a balloon
      and no stones were seen." states nothing of the bile-duct sweep's, as at f9013e12e and 05a881a75. Without
      ``beside`` (a direct read of one act) no other act supports the code, and the dropped sentence is read as D159
      read it.
    retrieval_hold lets a widened statement only hold the code, never take an act out of E* (D168).
    DECISIONS D173 (round 5h, narrowing only; refute6 families findings 7 and 8, review:ercp7 problems 0 and 2):
    - (1) with ``whose`` (retrieval_hold's reading of the acts of a code still READY, with ``widened`` False), D168's
      whose-denial condition covers D155's own arm too: a sentence dropped as another act's that holds the own words of
      a RIVAL (another performed stone extraction of ``beside``) holds the rival's denial, never this act's, when the
      act's own sentence states its own yield (_own_sentence_yield: D168's _clause_yield, across an appositive, or in a
      free simple clause) - "The bile duct was swept with an extraction balloon and two stones were removed. The
      pancreatic duct was then swept with a balloon; no stones were seen." no longer takes the bile-duct sweep out of
      E*. Without ``whose`` (the hold's reading) D155's arm reads as before: there the condition would RELEASE "... and
      two stones were removed. The pancreatic duct was then swept with an extraction balloon, and no stones were
      retrieved." (held on 1b4ca399: both sweeps state nothing retrieved);
    - (2) D159's rule (3) reads a later sentence after a rival's sentence (_later_statement);
    - (7) D168's own-yield reading never counts a yield in a clause that holds another occasion's time words
      (_other_times)."""
    from studio.interpretation import events

    words = _own_words(event)
    others = [span for other in reading.events.values() if other.get('id') != event.get('id')
              for span in _own_words(other)]
    # D140 (problem 1), restored by D155: the words of the events that are not performed - a denial or an uncertain
    # statement, and a planned act or one begun and not completed: every status value but 'performed', in any
    # verification state
    unperformed = [span for other in reading.events.values() if other.get('id') != event.get('id')
                   and events.value(other, 'status') != PERFORMED for span in _own_words(other)]
    located = [place for record in reading.passages.values() if record.get('state') != 'unlocated'
               for place in record['spans']]
    stated = _own_yield(event, others, located)  # D140: the act's own words state its yield (the structural reading)
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
    candidates = [sentence for place in located + _kept(kept) for sentence in _sentences(place)]
    anchors, pending = {}, []  # DECISIONS D168 (1): the own sentences and the dropped sentences the widened reads read
    times = _other_times(reading, event)  # DECISIONS D173 (7): another occasion's time words, the time reader's
    rivals = _rivals(reading, event, beside)  # D168 (1); DECISIONS D173 (1)
    for sentence in sorted(own, key=lambda item: (item['start'], item['end'])):
        clauses = _clauses(sentence)
        yields, (denial, where) = stated or _yields(clauses, others, words), _denial(clauses)
        shared = any(_holds(clause, others) for clause in where)  # a presence denial in a clause of another act's
        if denial == 'retrieval' or (denial == 'presence' and (not yields or shared)):
            return [_trimmed(sentence)]
        anchors[(sentence['start'], sentence['end'])] = (sentence, clauses, yields)
        if yields:  # the act's own sentence states what it retrieved: a sentence after it never denies that
            continue
        after = [item for item in candidates
                 if sentence['end'] <= item['start'] <= sentence['end'] + CONTINUES_WITHIN]
        first = min((item['start'] for item in after), default=None)
        # D140 (problem 1), restored by D155: another act's sentence does not continue the act - but one that holds the
        # words of an event that is not performed (a denial, an uncertain statement, a plan, an act begun and not
        # completed) is never dropped
        following = list({(item['start'], item['end']): item for item in after if item['start'] == first
                          and (not _holds(item, others) or _holds(item, unperformed))}.values())
        if following and _denial(clauses + [clause for item in following for clause in _clauses(item)])[0]:
            return [_trimmed(item) for item in (sentence, *following)]
        # D155 (review:ercp4 problem 6): a sentence dropped as another act's is read for its denial clause - a clause of
        # it that holds no other event's own words and, read with the act's own sentence, denies the retrieval or the
        # stones' presence is the act's statement, whatever the sentence's other clauses hold
        dropped = list({(item['start'], item['end']): item for item in after if item['start'] == first
                        and _holds(item, others) and not _holds(item, unperformed)}.values())
        for item in dropped:
            if whose and _holds(item, rivals) and _own_sentence_yield(clauses, others, times):
                continue  # DECISIONS D173 (1): for E*, a rival's denial, never this act's (refute6 families finding 7)
            for clause in _clauses(item):
                if not _holds(clause, others) and _denial(clauses + [clause])[0]:
                    return [_trimmed(sentence), _trimmed(clause)]
        pending.append((sentence, clauses, dropped))
    if not widened:  # D155's reading alone (retrieval_hold's E*)
        return None
    # DECISIONS D168 (1), D159's rule (1): a clause of a dropped sentence that holds another event's own words - but
    # not, where the act's own sentence states its yield, one of a sentence that holds another supporting stone
    # extraction's
    for sentence, clauses, dropped in pending:
        for item in dropped:
            if _holds(item, rivals) and _clause_yield(clauses, others, times):
                continue  # the denial is the other act's, never this act's (review:ercp6 problem 1)
            for clause in _clauses(item):
                if _holds(clause, others) and _denial(clauses + [clause])[0]:
                    return [_trimmed(sentence), _trimmed(clause)]
    return _later_statement(places, anchors, others, rivals, times)  # D159's rule (3), rebuilt


def retrieval_hold(evaluation, reading, kept: Sequence = ()):
    """D106 over one code's evaluation: a READY code of the stone removal (its one requirement group is
    stone_extraction: 43264) whose supporting acts each state that nothing was retrieved is held with the
    performed_status question naming that statement; when another act supports it, the code keeps READY on that act and
    the act that retrieved nothing leaves E* (the decision still read it). Any other evaluation is returned unchanged.
    D127: ``kept`` is the code's own exact evidence, which nothing_retrieved also reads.

    DECISIONS D168 (round 5g, narrowing only): each act is read beside the code's other supporting acts (``beside``:
    whose denial a sentence of another stone extraction's words is), and a statement only the WIDENED reads give
    (nothing_retrieved's D159 rules) only ever HOLDS the code - when every supporting act states nothing retrieved.
    Where an act would still support it, the acts leave E* only by D155's reading (widened=False), as before: "The bile
    duct was swept with an extraction balloon. Two stones were extracted with a basket and no stones were seen on the
    final cholangiogram." (the basket filed) stays READY on both acts, never on the basket alone - a READY whose acts
    changed would be a move this round's rule forbids (review:ercp6 problem 1's class).

    DECISIONS D173 (round 5h, narrowing only):
    - (1) (refute6 families finding 7) the acts of a code still READY leave E* only by D155's reading with D168's
      whose-denial condition on D155's own arm (nothing_retrieved with ``whose``): a rival's denial clause no longer
      takes out of E* an act whose own sentence states its yield - "... and two stones were removed. The pancreatic
      duct was then swept with a balloon; no stones were seen." is READY on both sweeps (e5628be56's acts), never on
      the pancreatic one alone. The hold itself is decided by the reading above, unchanged;
    - (3), (4), (6) (review:ercp7 problem 1; refute6 families finding 8; judges finding 9) 43264 never stands on acts
      that state no yield: when no act E* keeps carries the code (_carries: it states a stone yield of its own,
      _states_own_yield, or it is done to a finding the inventory lists, _done_to_a_finding, with no statement of its
      own that nothing was retrieved), the code is held, the final decision (_no_yield_hold) - with D106's question on
      the statement of an act E* keeps (review:ercp7's WV4 "The bile duct was swept with an extraction balloon. The
      pancreatic duct was then swept with a balloon and no stones were seen.": the denial stays the bile-duct sweep's),
      else with NO_YIELD's naming the acts E* keeps and those D155's reading set apart: a lone sweep that states no
      yield after "Cholangiogram showed a mildly dilated bile duct without filling defects." (judges finding 9), and a
      basket sweep left alone beside "Three stones, the largest 9 mm, were extracted ..." / "No stones remained."
      (families finding 8)."""
    from studio.interpretation import events

    link = evaluation.link
    if (link.family != ERCP or link.route != mapping.CATALOGUE_ROUTE
            or tuple(events.requirements(link)) != ((STONE_EXTRACTION,),)):
        return evaluation
    if evaluation.state != 'performed' or evaluation.reason != events.SUPPORTED:
        return evaluation
    supporting = tuple(evaluation.supporting)
    stated = {}
    for eid in supporting:
        statement = nothing_retrieved(reading, reading.events[eid], kept, supporting)
        if statement is not None:
            stated[eid] = statement
    if stated and not any(eid not in stated for eid in supporting):  # every act states nothing retrieved: D106's hold
        eid = next(iter(stated))
        return _nothing_retrieved_hold(evaluation, reading, eid, stated[eid])
    # DECISIONS D168: an act still supports the code, so only D155's reading takes acts out of E* - D173 (1): never by
    # a rival's denial clause read for an act whose own sentence states its yield
    apart = {}
    for eid in stated:
        found = nothing_retrieved(reading, reading.events[eid], kept, supporting, widened=False, whose=True)
        if found is not None:
            apart[eid] = found
    left = tuple(eid for eid in supporting if eid not in apart)
    if left and not any(_carries(reading, reading.events[eid], kept, stated.get(eid)) for eid in left):
        return _no_yield_hold(evaluation, reading, kept, left, apart, stated)  # DECISIONS D173 (3), (4), (6)
    if not apart:
        return evaluation
    labels = [events.event_label(reading, reading.events[eid]) for eid in left[:4]]
    return replace(evaluation, supporting=left, detail=f'The {events.service_label(link.family)} is documented as '
                                                       f'performed with {"; ".join(labels)}.')


def _nothing_retrieved_hold(evaluation, reading, eid: str, statement: Sequence[Mapping]):
    """D106's hold of ``evaluation`` (43264) on act ``eid``'s ``statement`` that nothing was retrieved: the
    performed_status question naming that statement (retrieval_hold's, as before)."""
    from studio.interpretation import events

    link = evaluation.link
    said = ' '.join(' '.join(place['text'].split()) for place in statement)
    act = events.event_label(reading, reading.events[eid])
    question = f'Was any stone, calculus, debris or sludge removed with the {act} ({wording.quote(said, 120)})?'
    reason = (f'The document states that nothing was retrieved with the {act} ({wording.quote(said, 140)}). '
              'CPT Studio does not read a sweep or an extraction that retrieved nothing as a removal of stones or '
              'debris. Held for the reviewer, not excluded.')
    return events.Evaluation(evaluation.code, link.family, link, 'uncertain', NOTHING_RETRIEVED, reason,
                             read=evaluation.read,
                             question=events.Question('performed_status', question, reason, (eid,), _spans(statement)))


def _own_sentences(reading, event: Mapping, kept: Sequence = ()) -> list:
    """D106's own sentences of the act, as nothing_retrieved reads them (D127): the sentences of its own located
    passages (events.own_passages: kind, status, target) that hold one of its own words - a passage none of whose
    sentences holds them read whole - and the sentences of the code's own exact evidence (``kept``) that overlap one of
    those passages and hold one of its own words; each once, in document order."""
    from studio.interpretation import events

    words = _own_words(event)
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
    return sorted(own, key=lambda item: (item['start'], item['end']))


def _states_own_yield(reading, event: Mapping, kept: Sequence = ()) -> bool:
    """DECISIONS D173 (3), (4), (6): whether the act states a stone yield of its own - in its own attribute words
    (D140's structural reading, _own_yield), in one of its own sentences (_own_sentences) by D168's reading, across an
    appositive or in a free simple clause (_own_sentence_yield), or so in the sentence right after an own sentence (it
    begins within CONTINUES_WITHIN characters of that sentence's end, in a located passage or the code's own exact
    evidence, as D127 reads the sentence that continues an act): "The bile duct was swept with an extraction balloon.
    Two stones were removed."; "... A plastic biliary stent was placed and sludge was retrieved." (the stent filed: its
    clause "and sludge was retrieved" holds no event's words, as D155 reads such a sentence's free clause for a denial).
    Never in a clause that holds another event's own words, nor in a sentence after the own one that holds another
    stone extraction's (that act's statement of what it retrieved), nor in another occasion's time words (D173 (7)).
    Read only to decide whether an act E* keeps carries 43264 (retrieval_hold), so it only ever decides whether to ADD
    D173's hold - never a clearance of D106's."""
    others = [span for other in reading.events.values() if other.get('id') != event.get('id')
              for span in _own_words(other)]
    stones = [span for other in reading.events.values() if other.get('id') != event.get('id')
              and (other.get('catalogue_kind') or '') == STONE_EXTRACTION for span in _own_words(other)]
    located = [place for record in reading.passages.values() if record.get('state') != 'unlocated'
               for place in record['spans']]
    times = _other_times(reading, event)
    if _own_yield(event, others, located, times):
        return True
    candidates = [sentence for place in located + _kept(kept) for sentence in _sentences(place)]
    for sentence in _own_sentences(reading, event, kept):
        if _own_sentence_yield(_clauses(sentence), others, times):
            return True
        after = [item for item in candidates if sentence['end'] <= item['start'] <= sentence['end'] + CONTINUES_WITHIN]
        first = min((item['start'] for item in after), default=None)
        for item in after:
            if item['start'] == first and not _holds(item, stones) and _own_sentence_yield(_clauses(item), others,
                                                                                            times):
                return True
    return False


def _done_to_a_finding(reading, event: Mapping) -> bool:
    """DECISIONS D173 (6): whether the act is done to a finding the examination states - its target names a lesion the
    inventory lists, in any verification state (FRESH-2 fb13's extraction is done to 'three filling defects (stones)',
    the cholangiogram's finding). A sweep of a duct after "Cholangiogram showed a mildly dilated bile duct without
    filling defects." names none. Read in the event's own target and the inventory's lesions (structure), never a word
    of the document."""
    target = event.get('target')
    lesion = target.get('lesion') if isinstance(target, Mapping) else ''
    return bool(lesion) and lesion in reading.lesions


def _carries(reading, event: Mapping, kept: Sequence, statement) -> bool:
    """DECISIONS D173 (3), (4), (6): whether an act E* keeps can carry 43264 - it states a stone yield of its own
    (_states_own_yield), or it is done to a finding the inventory lists (_done_to_a_finding) and the document gives no
    statement of its own that nothing was retrieved (``statement``: nothing_retrieved's, the hold's reading). An act
    that states nothing - a sweep with no yield, after a cholangiogram that found nothing - carries nothing."""
    return _states_own_yield(reading, event, kept) or (statement is None and _done_to_a_finding(reading, event))


def _no_yield_hold(evaluation, reading, kept: Sequence, left: Sequence[str], apart: Mapping, stated: Mapping):
    """DECISIONS D173 (3), (4), (6): the hold of a READY ``evaluation`` (43264) no act of whose E* (``left``) carries it
    (_carries): with D106's question on the statement of the first act of ``left`` that has one (``stated``: the hold's
    reading - review:ercp7 problem 1, "the denial stays this act's statement, so the code is held"), else with
    NO_YIELD's performed_status question naming the acts of ``left`` (their own sentences) and those D155's reading set
    apart (``apart``, their statements). Never READY, never excluded: CPT 43264 is a removal of calculi or debris, and
    the document states none removed with these acts. The question's events are the acts it names, and the decision's
    read events stay the READY evaluation's, so the competition (assess._claims, D163) keeps their claims."""
    from studio.interpretation import events

    for eid in left:
        if stated.get(eid) is not None:
            return _nothing_retrieved_hold(evaluation, reading, eid, stated[eid])
    link = evaluation.link
    named, places = [], []
    for eid in tuple(left)[:3]:
        event = reading.events[eid]
        own = list({(place['start'], place['end']): place for place in (
            _trimmed(sentence) for sentence in _own_sentences(reading, event, kept))}.values())
        said = ' '.join(' '.join(place['text'].split()) for place in own) or events.statement_text(reading, event)
        named.append((eid, events.event_label(reading, event), said))
        places += own
    for eid in [eid for eid in evaluation.supporting if eid in apart][:max(0, 3 - len(named))]:
        said = ' '.join(' '.join(place['text'].split()) for place in apart[eid])
        named.append((eid, events.event_label(reading, reading.events[eid]), said))
        places += list(apart[eid])
    acts = ' or '.join(f'the {label} ({wording.quote(said, 120)})' for _, label, said in named)
    silent = ' or '.join(f'the {label} ({wording.quote(said, 140)})' for eid, label, said in named if eid not in apart)
    denied = ' and '.join(f'the {label} ({wording.quote(said, 140)})' for eid, label, said in named if eid in apart)
    question = f'Was any stone, calculus, debris or sludge removed with {acts}?'
    reason = (f'The document states no stone, calculus, debris or sludge removed with {silent}'
              + (f', and CPT Studio reads {denied} as having retrieved nothing' if denied else '')
              + '. CPT Studio does not read a sweep or an extraction that states no yield, done to no finding the '
                'document lists, as a removal of stones or debris. Held for the reviewer, not excluded.')
    return events.Evaluation(evaluation.code, link.family, link, 'uncertain', NO_YIELD, reason, read=evaluation.read,
                             question=events.Question('performed_status', question, reason,
                                                      tuple(eid for eid, _, _ in named), _spans(places)))


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


def role_second(held, acts: Sequence[Mapping], kept: Sequence, reading):
    """DECISIONS D168 (3) (round 5g; review:colon5 problem 0): the another_role hold of a code these rules read - handed
    over by events.evaluate, where events.another_role_hold (D124, D158) holds a code whose every act is told only in
    another role's entry - keeps its question, and the question ``ruled`` would hold the code with were it READY on
    ``acts`` (its own acts: the per-code rule's E*, which the hold names) is the hold's SECOND clarification
    (events.Evaluation.second, D161's mechanism: assess asks it after the hold's own): D105's possible exchange
    (exchange_hold) or D106's nothing retrieved (retrieval_hold). So "Documented by Jo Rowe, RN: A new 10 Fr x 9 cm
    plastic" / "biliary stent was placed into the common bile duct." beside finding 22's snare removal asks the nursing
    entry's question AND the exchange question (43276), and finding 25's sweep signed by the nurse asks whether any
    stone was removed, where ``ruled`` applied both rules to a READY evaluation only, so the ERCP question was asked
    nowhere.
    Any other evaluation, a code neither rule reads, a hold with a second question already, acts none of which is
    performed (the per-code rule's evaluation would not be READY) and a READY evaluation the rules leave READY return
    ``held`` as it is. It never changes the hold: its reason, question, read events and E* (empty) stay the hold's,
    so the competition (assess._claims, D163) and coverage read what they read before."""
    from studio.interpretation import events

    if held.second is not None or held.reason != events.ANOTHER_ROLE or not _read_by_a_rule(held.link):
        return held
    if not any(events.value(event, 'status') == PERFORMED for event in acts):
        return held
    ready = replace(held, state='performed', reason=events.SUPPORTED, supporting=tuple(event['id'] for event in acts),
                    question=None)
    ruling = retrieval_hold(exchange_hold(ready, reading), reading, kept)
    if ruling.held and ruling.reason in (POSSIBLE_EXCHANGE, NOTHING_RETRIEVED) and ruling.question is not None:
        return replace(held, second=ruling.question)
    return held


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
