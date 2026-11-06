"""Purpose phrases: why an act was done, never when (completion repair 2026-11-06, U5; HARNESS.md "Completion repair
(2026-11-06)"). One reading, read by routing (studio.gi.detect) and by the documented-service reader
(studio.gi.services) alike.

A purpose phrase - "for future localization", "for subsequent surveillance", "to facilitate later identification" -
says what an act is for. Its time word ("future", "subsequent", "later", "eventual") is the purpose's own time:
- it never dates the act the clause's main predicate states done ("A separate 25 mm flat lesion ... was marked with
  submucosal tattoo for future localization": a tattoo done today);
- an act or a service named INSIDE the phrase is the purpose's, and keeps that future ("India ink was injected ... for
  future localization at the time of EMR", "tattooed for future resection (EMR)", "biopsied for future treatment with
  APC", "obtained for future comparison at colonoscopy").

What the phrase is, structurally:
- its opener: "for" or "to facilitate/allow/aid/permit/enable/guide/help (with)", at most two determiners or hedges,
  then the time word (OPENER);
- its end: the end of the span its reader passes - its sentence, as that reader segments it, so a decimal size
  ("1.5 cm"), a parenthesis ("(APC)"), a colon ("treatment: EMR"), "Dr." or "e.g." never ends it early (the refutation
  of F-TIME R, cycle 2: C2-1-1 to C2-1-3) - unless an independent predicate begins first (STOP): a semicolon, a
  coordinated predicate ("and not resected today", "and was then removed"), or a comma before a new subject and its
  verb.

What the clause states done (main_predicate_done) is the LAST finite predicate before the opener, and only when that
predicate itself is a done act predicate ("was marked", "were obtained", "has been injected", "we tattooed", or a
fragment's participle right after its noun phrase: "Tattoo ink injected into ...") - never the last act participle
anywhere ("India ink tattoo was requested for future localization" states nothing done, whatever another clause
says: the refutation of F-TIME R keyed on any act's participle). Which mention a done predicate is said of is each
reader's own question (its subject, its participle, its instrument), answered by that reader.

Pure functions of the text; bounded (PHRASE_REACH characters per phrase, one pattern search per predicate)."""
from __future__ import annotations

import re
from typing import Optional

FLAGS = re.A | re.I
TIME_WORDS = r'(?:future|subsequent|later|eventual)'
OPENER = re.compile(r'\b(?:for|to[ \t\n]+(?:facilitate|allow|aid|assist(?:[ \t\n]+with)?|permit|enable|guide|ease|'
                    r'help(?:[ \t\n]+with)?))[ \t\n]+(?:(?:the|a|an|its|their|any|possible|potential)[ \t\n]+){0,2}'
                    r'(?P<time>' + TIME_WORDS + r')\b', FLAGS)
OPENER_REACH = 60  # characters before a time word read for its opener
PHRASE_REACH = 400  # characters after the opener a phrase is read in, at most
STOP = re.compile(r';'
                  r'|[ \t\n]*,?[ \t\n]+and[ \t\n]+(?:then[ \t\n]+)?(?:not[ \t\n]+|never[ \t\n]+)?'
                  r'(?:(?:was|were|is|are|has|have|had)[ \t\n]+)?(?:[a-z]+ly[ \t\n]+)?[a-z]+(?:ed|en)\b'
                  r'|,[ \t\n]+(?:and[ \t\n]+)?(?:the|this|that|it|she|he|they|we|I)[ \t\n]+[^.;,\n]{0,40}?'
                  r'\b(?:was|were|is|are|will)\b', FLAGS)
# the act participles that state an act done (a closed class: an unknown participle states nothing done, so the
# purpose's future keeps dating the clause - the safe side)
DONE = (r'(?:performed|done|obtained|taken|removed|resected|retrieved|excised|placed|deployed|inserted|applied|'
        r'injected|tattooed|marked|inked|ablated|treated|dilated|banded|ligated|clipped|biopsied|sampled|snared|'
        r'cannulated|completed|extracted|administered|given|made|used)')
# the finite predicates of a clause: an auxiliary and its participle (any participle: the last one decides), or an
# active past with a personal subject
PREDICATE = re.compile(r"\b(?P<aux>(?:has|have|had)[ \t\n]+been|was|were|is|are|be|been|being|get|gets|got)[ \t\n]+"
                       r"(?:(?:then|also|not|never|successfully|subsequently|carefully|completely|[a-z]+ly)[ \t\n]+)?"
                       r"(?P<participle>[a-z]+(?:ed|en|ne|wn|ken)|done|made|taken|given)\b"
                       r"|\b(?:we|I)[ \t\n]+(?:then[ \t\n]+)?(?P<active>[a-z]+ed)\b", FLAGS)
RELATIVE_BEFORE = re.compile(r'\b(?:that|which|who|whom|where)[ \t\n]+$', FLAGS)
# what between the done predicate and the purpose opener opens another clause or a coordination: then the purpose is
# not (provably) the done predicate's, and nothing is released
OTHER_CLAUSE_BETWEEN = re.compile(r'[,;:()]|\b(?:and|or|but|nor|which|that|who|while|whereas|because|since|when|after|'
                                  r'before|although|if|unless|then|so)\b', FLAGS)
DONE_PARTICIPLE = re.compile(DONE + r'$', FLAGS)
DONE_ACTIVE = re.compile(r'(?:performed|obtained|removed|resected|placed|deployed|inserted|applied|injected|tattooed|'
                         r'marked|ablated|treated|dilated|banded|ligated|clipped|biopsied|sampled|snared|cannulated|'
                         r'completed|extracted|administered)$', FLAGS)
# what makes a finite form no statement that the act is done: a modal, an infinitive marker or a negation before it
NOT_STATED = re.compile(r"\b(?:will|would|could|can|cannot|should|may|might|must|shall|to|not|never|\w+n['’]t)"
                        r"[ \t\n]+(?:(?:not|never|then|also|[a-z]+ly)[ \t\n]+)?$", FLAGS)
# a fragment: a noun phrase of content words, then the act's participle, with no auxiliary ("Tattoo ink injected into")
FRAGMENT = re.compile(r'[\W\d]*(?:(?!(?:was|were|is|are|be|been|has|have|had|will|would|could|can|should|may|might|'
                      r'must|to|not|never|no|and|or|but|if|when|after|before|because|which|that|who)\b)'
                      r'[A-Za-z][\w-]*[ \t\n]+){1,6}?(?P<participle>' + DONE + r')\b', FLAGS)


def phrase_at(text: str, word_start: int, limit: int) -> Optional[tuple[int, int, int]]:
    """The purpose phrase whose time word starts at ``word_start``: (opener start, time word end, phrase end), the phrase
    read no further than ``limit`` (its reader's sentence or clause end) and stopping at STOP; None when no opener
    governs the word ("in the future", "future colonoscopy" alone are no purpose phrase here)."""
    lo = max(0, word_start - OPENER_REACH)
    opener = None
    for m in OPENER.finditer(text, lo, min(len(text), word_start + 12)):
        if m.start('time') == word_start:
            opener = m
    if opener is None:
        return None
    end = min(limit, opener.end() + PHRASE_REACH)
    stop = STOP.search(text, opener.end(), end)
    return opener.start(), opener.end(), stop.start() if stop is not None else end


def purpose_spans(text: str, start: int, end: int) -> tuple[tuple[int, int, int], ...]:
    """Every purpose phrase in [start, end), as phrase_at gives each."""
    out = []
    for m in OPENER.finditer(text, start, end):
        phrase = phrase_at(text, m.start('time'), end)
        if phrase is not None and (not out or phrase[0] >= out[-1][2]):
            out.append(phrase)
    return tuple(out)


def main_predicate_done(text: str, clause_start: int, opener_start: int) -> Optional[tuple[int, int, int]]:
    """The clause's main predicate before a purpose opener, when it states an act done: (predicate start, participle
    start, participle end), else None. The predicate is the LAST finite one in [clause_start, opener_start): an
    auxiliary's participle (it states the act done only with "was"/"were" or a perfect "has/have been", no modal, no
    infinitive marker and no negation before it, and a DONE participle), or an active past with "we"/"I" (a DONE verb);
    with no finite predicate, a fragment's DONE participle right after its noun phrase."""
    last = None
    for last in PREDICATE.finditer(text, clause_start, opener_start):
        pass
    if last is not None:
        if RELATIVE_BEFORE.search(text, max(clause_start, last.start() - 12), last.start()):
            return None  # "The lesion that was biopsied needs tattooing ...": a relative clause's, not the main one
        end = last.end('active') if last.group('active') else last.end('participle')
        if OTHER_CLAUSE_BETWEEN.search(text, end, opener_start):
            return None
        if last.group('active'):
            word = last.group('active')
            if NOT_STATED.search(text, max(clause_start, last.start() - 30), last.start()) \
                    or not DONE_ACTIVE.match(word):
                return None
            return last.start(), last.start('active'), last.end('active')
        aux = ' '.join(last.group('aux').lower().split())
        participle = last.group('participle')
        if aux not in ('was', 'were', 'has been', 'have been'):
            return None  # "is injected", "get injected", "to be injected", "had been injected": not stated done today
        if NOT_STATED.search(text, max(clause_start, last.start() - 30), last.start()) \
                or not DONE_PARTICIPLE.match(participle):
            return None
        between = text[last.end('aux'):last.start('participle')]
        if re.search(r'\b(?:not|never)\b', between, FLAGS):
            return None
        return last.start(), last.start('participle'), last.end('participle')
    fragment = FRAGMENT.match(text, clause_start, opener_start)
    if fragment is not None and not OTHER_CLAUSE_BETWEEN.search(text, fragment.end('participle'), opener_start):
        return fragment.start('participle'), fragment.start('participle'), fragment.end('participle')
    return None


INSTRUMENT = re.compile(r'[ \t\n]+with[ \t\n]+(?:(?:a|an|the|some)[ \t\n]+)?(?:[A-Za-z][\w-]*[ \t\n]+){0,2}$', FLAGS)


def instrument_of(text: str, participle_end: int, mention_start: int) -> bool:
    """Whether the mention starting at ``mention_start`` is the done participle's instrument ("marked with submucosal
    tattoo", "injected with India ink"): "with", at most a determiner and two modifiers, between them."""
    return mention_start >= participle_end and INSTRUMENT.fullmatch(text, participle_end, mention_start) is not None
