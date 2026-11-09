"""Lesion distinctness and act-to-lesion identity (design/contract.md 6.1-6.3; design/ADJUDICATION.md C-11, C-15 and EB1):
two of normalize's linked steps (normalize.LINKED_STEPS), ``distinguish`` then ``link``, each taking the Draft.

Every rule reads only the cited words of the records it compares - a lesion's description, site and size words, a
target's words, an act's kind and status words - and the literal values inside them (EB1): a size, a distance, a
landmark, a specimen label. No rule reads a passage, a heading or the document for meaning, and no rule produces a
value: a link is VERIFIED only when every rule establishes it, and otherwise it is ``unresolved`` with its reasons, which
gives a question only where a code depends on it (contract 5.5, 6.5). An identifier that cannot be established never
makes a match or a non-match (P3).

Distinctness (6.3; C-11; C-15) - a non-match must be ESTABLISHED, never manufactured. Two lesions are distinct only when
a literal shows it, in this order:
- ``landmarks``: both sites verified and disjoint (lexicon.disjoint: neither contains the other, nothing lies in both,
  never an unplaced or surgically altered place; the right, left, proximal and distal colon carry their containment);
- ``distances``: both state distances (cm) and none is shared;
- ``specimens``: both carry specimen labels ("specimen A", "jar 2") and none is shared;
- ``sizes``: the sizes differ beyond the tolerance - more than 2 mm AND more than 20% of the larger - and no shared
  literal says "same": no shared distance, and no site literal of one compatible with a site literal of the other (one
  place, or one holding the other: the sigmoid colon and the left colon), each lesion's site literals read where its
  distances are - its verified site, and the landmarks its site's and its description's own words name (C-11: a lesion
  registered twice with a 9 mm and a 1 cm measurement at one place must not hide a contradiction behind two ids);
- ``passage``: both are single lesions whose descriptions sit, apart, in one passage (the registry split one passage
  into two entries), neither description being only reference words.
Otherwise they are ``possibly_same_as`` each other. ``landmarks``, ``distances`` and ``specimens`` are HARD literals: only
they let a model's contradicts[] claim be dismissed (C-11; relations.py).

A link (6.2): an event whose target names lesion L is VERIFIED only when all of these hold, else ``unresolved`` with the
reasons of verify.IDENTITY_REASONS in ``identity_by``:
1. statement tie (identity_not_in_statement): the target words lie in a passage that also holds the event's kind or
   status words; with no target words, a passage holding the act's kind or status words holds L's description (one
   sentence describes L and states the act). Target words given that did not bind tie to nothing.
2. lexical tie (identity_no_tie): the target words share a content word with L's description - lower-cased tokens of 3
   or more letters, hyphens split, a closed function-word list and the reference pronouns removed, a final plural "s"
   removed - or consist only of reference words (it, them, the lesion, the polyp, the mass, the area ...) and literals
   (sizes, distances, landmarks). No words: nothing to tie.
3. literal consistency (identity_literal_conflict): no size, distance or landmark in the target words conflicts with L's:
   a size whose range meets none of L's, a distance L does not state, a landmark that neither contains nor is contained
   by any of L's.
4. discrimination (identity_ambiguous): every other verified lesion L2 that passes 2 and 3 as well (with no target words:
   whose description a passage of the act also holds) is told apart by a literal of the target words that matches L and
   not L2, by a content word L has and L2 has not, or by adjacency - L's description is the nearest one before the target
   words (or one they overlap) among the tied lesions, every place involved in a located (unambiguous) passage.
5. L is verified (lesion_unverified).
An open question about the event's identity leaves it ``unresolved`` whatever the rules found (``open`` in identity_by).

Pure and Django-free; imports nothing from studio.gi (FINAL 3.1).
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

from studio.interpretation import lexicon, literals, verify

# --- the closed lists --------------------------------------------------------------------------------------------------

NOT_IN_STATEMENT, NO_TIE, LITERAL_CONFLICT, AMBIGUOUS, LESION_UNVERIFIED = verify.IDENTITY_REASONS
VERIFIED, UNRESOLVED, NONE = 'verified', 'unresolved', 'none'

LANDMARKS, DISTANCES, SPECIMENS, SIZES, PASSAGE = 'landmarks', 'distances', 'specimens', 'sizes', 'passage'
DISTINCT_BY = (LANDMARKS, DISTANCES, SPECIMENS, SIZES, PASSAGE)
# The literals a model's contradicts[] claim can be dismissed by (C-11): a difference of place, distance or specimen.
HARD = frozenset({LANDMARKS, DISTANCES, SPECIMENS})
SIZE_TOLERANCE_MM = 2
SIZE_TOLERANCE_SHARE = 0.2

# --- reading words (EB1: a record's own cited words, and the literals in them) ------------------------------------------

# Runs of letters. Written [^\W_\d], not [^\W\d_]: the latter is studio.validation.engine._WORD's source, and re's
# cache can return one object for one source, which would make every read of this pattern a denied pattern's
# (sentinel.twins; tests/test_interpretation_sentinel.py). The two sets of characters are the same.
_LETTERS = re.compile(r'[^\W_\d]+')


def _singular(token: str) -> str:
    return token[:-1] if len(token) > 3 and token.endswith('s') and not token.endswith('ss') else token


# The words that refer back to a lesion or finding (contract 6.2), read from the closed list lexicon.REFERENCE_WORDS: the
# nouns it names after "the" (lesion, polyp, mass, area) and the pronouns (it, its, this, these, that, those, them).
_REFERENCE_NOUNS = frozenset(_singular(token) for phrase in lexicon.REFERENCE_WORDS if lexicon.fold(phrase).startswith('the ')
                             for token in _LETTERS.findall(lexicon.fold(phrase))[1:])
_REFERENCE_PRONOUNS = frozenset(token for phrase in lexicon.REFERENCE_WORDS for token in _LETTERS.findall(
    lexicon.fold(phrase)) if _singular(token) not in _REFERENCE_NOUNS and token != 'the')
_UNIT_WORDS = frozenset({'millimeter', 'millimetre', 'centimeter', 'centimetre'})
_LANDMARK_FORMS = re.compile(r'(?<!\w)(?:' + '|'.join(
    re.escape(form) for form in sorted({lexicon.fold(item) for forms in lexicon.LANDMARK_FORMS.values()
                                        for item in forms}, key=lambda value: (-len(value), value))) + r')(?!\w)')
_SPECIMEN = re.compile(r'(?<!\w)(?:specimens?|jars?|bottles?|containers?|cassettes?)[ \t]*(?:#|no\.?|number)?[ \t]*'
                       r'([a-z]|\d{1,3})(?!\w)')


def content_tokens(text: str) -> frozenset:
    """The content words of ``text`` (6.2, lexical tie): folded tokens of 3 or more letters (hyphens split), the closed
    function-word list (lexicon.TIE_FUNCTION_WORDS) and the reference pronouns removed, a final plural "s" removed."""
    found = set()
    for token in _LETTERS.findall(lexicon.fold(text)):
        if len(token) < 3 or token in lexicon.TIE_FUNCTION_WORDS or token in _REFERENCE_PRONOUNS:
            continue
        found.add(_singular(token))
    return frozenset(found)


def reference_only(text: str) -> bool:
    """Whether ``text`` consists only of reference words (it, its, this, these, that, those, them, the lesion(s), the
    polyp(s), the mass, the area) and literals - sizes, distances, landmarks - besides function words (6.2)."""
    stripped = _LANDMARK_FORMS.sub(' ', lexicon.fold(text))
    return content_tokens(stripped) <= _REFERENCE_NOUNS | _UNIT_WORDS


def specimen_labels(text: str) -> tuple:
    """The specimen labels ``text`` states ("specimen A", "jar 2", "bottle #3"), folded, in order, each once."""
    labels = []
    for match in _SPECIMEN.finditer(lexicon.fold(text)):
        if match.group(1) not in labels:
            labels.append(match.group(1))
    return tuple(labels)


def _text(span: Optional[Mapping]) -> str:
    return span['text'] if span else ''


@dataclass(frozen=True)
class LesionFacts:
    """What the identity and distinctness rules read of one lesion: whether it is verified, its verified and placed site
    landmark, the landmarks its literal check compares (that site's and those its description names), the site literals
    C-11's "says same" reads (``sites``: those and the landmarks its site's own located words name, read where its
    distances are), its sizes (mm) and distances (cm) from its own located words, its specimen labels, its description
    span and those of its OWN passages that hold it, and its description's content tokens."""
    id: str
    verified: bool
    single: bool
    landmark: str
    landmarks: tuple
    sites: tuple
    sizes: tuple
    distances: tuple
    specimens: tuple
    words: Optional[dict]
    passages: tuple
    tokens: frozenset
    reference_only: bool


def lesion_facts(draft) -> dict:
    """{lesion id: LesionFacts} for every lesion of the draft, in the answer's order."""
    facts = {}
    for lid, lesion in draft.lesions.items():
        site, words = lesion['site'], lesion['words']
        text, site_text = _text(words), _text(site['words'])
        landmark = site['value'] if verify.usable(site) and site['value'] not in lexicon.UNPLACED_LANDMARKS else ''
        named = tuple(name for name in lexicon.landmarks_named(text) if name != landmark)
        landmarks = ((landmark,) if landmark else ()) + named
        facts[lid] = LesionFacts(
            id=lid, verified=lesion['state'] == VERIFIED, single=lesion['multiplicity'] == 'single',
            landmark=landmark, landmarks=landmarks,
            sites=tuple(dict.fromkeys(landmarks + lexicon.landmarks_named(site_text))),
            sizes=tuple(lesion['size']['mm']) + literals.sizes_mm(text),
            distances=tuple((site['literals'] or {}).get('distances_cm', ())) + literals.distances_cm(text),
            specimens=tuple(dict.fromkeys(specimen_labels(text) + specimen_labels(site_text))),
            words=words, passages=tuple(pid for pid in draft.passages_of(words) if pid in lesion['passages'])
            if words else (),
            tokens=content_tokens(text), reference_only=reference_only(text) if words else True)
    return facts


# --- distinctness (6.3; C-11) ------------------------------------------------------------------------------------------

def _range(values) -> tuple:
    return min(values), max(values)


def sizes_apart(first, second) -> bool:
    """Whether two size lists (mm) differ beyond the tolerance (C-11): the gap between their ranges is more than 2 mm
    AND more than 20% of the nearer end of the larger. Overlapping ranges never differ."""
    if not first or not second:
        return False
    (low1, high1), (low2, high2) = _range(first), _range(second)
    if high1 < low2:
        gap, larger = low2 - high1, low2
    elif high2 < low1:
        gap, larger = low1 - high2, low1
    else:
        return False
    return gap > SIZE_TOLERANCE_MM and gap > SIZE_TOLERANCE_SHARE * larger


def sizes_meet(first, second) -> bool:
    """Whether two size lists' ranges meet (a size literal that does not conflict)."""
    if not first or not second:
        return False
    (low1, high1), (low2, high2) = _range(first), _range(second)
    return low1 <= high2 and low2 <= high1


def _apart(first: Optional[Mapping], second: Optional[Mapping]) -> bool:
    return first['end'] <= second['start'] or second['end'] <= first['start']


def same_place(first: LesionFacts, second: LesionFacts) -> bool:
    """Whether a site literal says the two lesions may be at one place (C-11): a site literal of one is one place with,
    or holds or lies in, a site literal of the other (lexicon.compatible), read over every site literal of each."""
    return any(lexicon.compatible(one, two) for one in first.sites for two in second.sites)


def distinct_reason(first: LesionFacts, second: LesionFacts) -> str:
    """Why two lesions are distinct (DISTINCT_BY, in its order), or '' when no literal establishes it."""
    if first.landmark and second.landmark and lexicon.disjoint(first.landmark, second.landmark):
        return LANDMARKS
    shared_distance = set(first.distances) & set(second.distances)
    if first.distances and second.distances and not shared_distance:
        return DISTANCES
    if first.specimens and second.specimens and not set(first.specimens) & set(second.specimens):
        return SPECIMENS
    if sizes_apart(first.sizes, second.sizes) and not shared_distance and not same_place(first, second):
        return SIZES
    if (first.single and second.single and first.words and second.words and not first.reference_only
            and not second.reference_only and set(first.passages) & set(second.passages)
            and _apart(first.words, second.words)):
        return PASSAGE
    return ''


def distinguish(draft) -> None:
    """normalize's first linked step: every lesion's ``distinct_from`` and ``possibly_same_as`` (6.3), each list in the
    answer's lesion order. Changes the draft's lesions in place; reads no text for meaning."""
    facts = lesion_facts(draft)
    ids = list(draft.lesions)
    for index, first in enumerate(ids):
        for second in ids[index + 1:]:
            field = 'distinct_from' if distinct_reason(facts[first], facts[second]) else 'possibly_same_as'
            draft.lesions[first][field].append(second)
            draft.lesions[second][field].append(first)


# --- act-to-lesion identity (6.2) --------------------------------------------------------------------------------------

_GIVEN_UNBOUND = frozenset({'words_unlocated', 'passage_unknown', 'passage_unlocated'})


@dataclass(frozen=True)
class _Target:
    """What the rules read of an event's target words: the span (None when there are none, or when they did not bind),
    whether words were given that did not bind, their content tokens and their literals."""
    words: Optional[dict]
    unbound: bool
    tokens: frozenset
    sizes: tuple
    distances: tuple
    landmarks: tuple


def _target(event: Mapping) -> _Target:
    target = event['target']
    words = target['words']
    text = _text(words)
    found = target['literals'] or {}
    return _Target(words=words, unbound=words is None and bool(_GIVEN_UNBOUND & set(target['reasons'])),
                   tokens=content_tokens(text), sizes=tuple(found.get('sizes_mm', ())),
                   distances=tuple(found.get('distances_cm', ())), landmarks=lexicon.landmarks_named(text))


def act_passages(draft, event: Mapping) -> frozenset:
    """The passages holding the event's kind or status words (its own statement), located or ambiguous."""
    held = set()
    for name in ('kind', 'status'):
        span = event[name]['words']
        if span:
            held.update(draft.passages_of(span))
    return frozenset(held)


def _statement_tie(draft, event: Mapping, target: _Target, lesion: LesionFacts, acts: frozenset) -> str:
    """How rule 1 is met ('target_words', 'lesion_passage'), or ''."""
    if target.words is not None:
        return 'target_words' if set(draft.passages_of(target.words)) & acts else ''
    if target.unbound:
        return ''
    return 'lesion_passage' if acts & set(lesion.passages) else ''


def _lexical_tie(target: _Target, lesion: LesionFacts) -> str:
    """How rule 2 is met ('content_word', 'reference_words', 'no_words'), or ''."""
    if target.words is None:
        return '' if target.unbound else 'no_words'
    if target.tokens & lesion.tokens:
        return 'content_word'
    if reference_only(target.words['text']):
        return 'reference_words'
    return ''


def _conflicts(target: _Target, lesion: LesionFacts) -> bool:
    """Rule 3: a size, distance or landmark of the target words that conflicts with the lesion's."""
    if target.sizes and lesion.sizes and not sizes_meet(target.sizes, lesion.sizes):
        return True
    if target.distances and lesion.distances and not set(target.distances) & set(lesion.distances):
        return True
    if target.landmarks and lesion.landmarks:
        return any(not any(lexicon.compatible(named, own) for own in lesion.landmarks) for named in target.landmarks)
    return False


def _literal_single(target: _Target, lesion: LesionFacts, other: LesionFacts) -> bool:
    """A literal of the target words that matches ``lesion`` and not ``other`` (rule 4)."""
    if target.sizes and sizes_meet(target.sizes, lesion.sizes) and not sizes_meet(target.sizes, other.sizes):
        return True
    if set(target.distances) & set(lesion.distances) and not set(target.distances) & set(other.distances):
        return True
    return any(named in lesion.landmarks and named not in other.landmarks for named in target.landmarks)


def _located(draft, span: Optional[Mapping]) -> bool:
    """Whether a span lies in at least one passage and every passage holding it is located at one place."""
    if not span:
        return False
    held = draft.passages_of(span)
    return bool(held) and all(draft.passages[pid]['state'] == 'located' for pid in held)


def _distance(words: Mapping, target_words: Mapping) -> Optional[int]:
    """How far a description lies before the target words: 0 when they overlap, the characters between them when it
    ends before them, None when it lies after them."""
    if not _apart(words, target_words):
        return 0
    if words['end'] <= target_words['start']:
        return target_words['start'] - words['end']
    return None


def _adjacent(draft, target: _Target, lesion: LesionFacts, tied: list) -> bool:
    """Rule 4's adjacency: ``lesion``'s description is the nearest before the target words (or one they overlap) among
    the tied lesions, every place involved in a located, unambiguous passage."""
    if not _located(draft, target.words):
        return False
    distances = {}
    for facts in [lesion] + tied:
        if not _located(draft, facts.words):
            return False
        distances[facts.id] = _distance(facts.words, target.words)
    own = distances[lesion.id]
    return own is not None and all(distances[facts.id] is None or distances[facts.id] > own for facts in tied)


def _single(target: _Target, lesion: LesionFacts, other: LesionFacts) -> str:
    """How ``lesion`` is told apart from ``other`` by the target words alone (rule 4): 'literal', 'content_word', or ''."""
    if _literal_single(target, lesion, other):
        return 'literal'
    if target.tokens & (lesion.tokens - other.tokens):
        return 'content_word'
    return ''


def judge(draft, event: Mapping, lesion: LesionFacts, facts: Mapping) -> tuple[list, dict]:
    """The identity rules (6.2) for ``event``'s link to ``lesion``: (reasons, how each rule that holds was met). Target
    words that were given and did not bind are read no further than the statement tie: nothing of them is known."""
    target = _target(event)
    acts = act_passages(draft, event)
    reasons, by = [], {}
    statement = _statement_tie(draft, event, target, lesion, acts)
    if statement:
        by['statement'] = statement
    else:
        reasons.append(NOT_IN_STATEMENT)
    if not target.unbound:
        tie = _lexical_tie(target, lesion)
        if tie:
            by['tie'] = tie
        else:
            reasons.append(NO_TIE)
        if _conflicts(target, lesion):
            reasons.append(LITERAL_CONFLICT)
        else:
            by['literals'] = 'consistent'
        if tie and LITERAL_CONFLICT not in reasons:
            tied = [other for other in facts.values() if other.id != lesion.id and other.verified
                    and _lexical_tie(target, other) and not _conflicts(target, other)
                    and (target.words is not None or acts & set(other.passages))]
            ways = {_single(target, lesion, other) for other in tied}
            if not tied:
                by['discrimination'] = 'only'
            elif '' not in ways:
                by['discrimination'] = ','.join(sorted(ways))
            elif _adjacent(draft, target, lesion, tied):
                by['discrimination'] = 'adjacency'
            else:
                reasons.append(AMBIGUOUS)
    if lesion.verified:
        by['lesion'] = VERIFIED
    else:
        reasons.append(LESION_UNVERIFIED)
    return reasons, by


def link(draft) -> None:
    """normalize's second linked step: the identity of every event target that names a lesion the answer defines (6.2).
    normalize set such a target ``unresolved``; it becomes ``verified`` only when every rule holds and no open question
    names its identity. An undefined lesion's ``none`` (lesion_unknown) and a target with no lesion are left as they
    are. ``identity_by`` records {'reasons': [...], 'by': {rule: how}} and ``open`` when an open question names it."""
    facts = lesion_facts(draft)
    for eid, event in draft.events.items():
        target = event['target']
        lid = target['lesion']
        if not lid or lid not in draft.lesions:
            continue
        reasons, by = judge(draft, event, facts[lid], facts)
        opened = eid in draft.identity_open
        target['identity'] = VERIFIED if not reasons and not opened else UNRESOLVED
        target['identity_by'] = {'reasons': verify.ordered(reasons), 'by': by, **({'open': True} if opened else {})}


# --- reading identity (for relations.py and the engine) ----------------------------------------------------------------

def verified_lesion(event: Mapping) -> str:
    """The lesion an event's target is verified to be, '' when none is."""
    target = event['target']
    return target['lesion'] if target.get('identity') == VERIFIED and target.get('lesion') else ''


def same_or_possibly_same(draft, first: str, second: str) -> bool:
    """Whether two lesion ids are one lesion or possibly the same (6.3)."""
    return first == second or second in draft.lesions.get(first, {}).get('possibly_same_as', ())
