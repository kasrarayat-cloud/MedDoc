"""Round r3's proof location (DECISIONS D306 addendum 1 (b), D307, D308, D318 (1); build-v2/a2b/r3/design/DESIGN-v2.md
c.3): whether the quotes Fable gives for a question claim are the document's own words, inside the passages the claim's
named objects own.

``locate(text, required, optional, quotes, alternatives=())`` - THE PROOF CLASS (DECISIONS D318 (1)). A proof is void
only when a quote lies outside the claim's own passages, overlaps another located quote, or is too short - never
because of extra quotes inside them:
- every quote, whitespace runs collapsed to one space on both sides (no case or punctuation folding, no other change),
  holds at least MIN_CHARS non-space characters and MIN_TOKENS space-separated tokens (else proof_short);
- every quote occurs inside ONE maximal character range of one of the claim's passages - a REQUIRED passage set, the
  OPTIONAL one, or, for a session reach, one of its ALTERNATIVES - and no two located quotes overlap (else
  proof_unlocated: a quote outside every passage, a paraphrase, a unit label or a [Page N] line - neither is in the
  revision text - or an overlap);
- every REQUIRED passage set receives a quote of its own (one quote per required set, the sets never sharing one: a
  relation claim needs words from BOTH subjects, DESIGN-v2 b.0, R3D-06) - every FURTHER quote lies inside a required
  set or the optional set, any number of them; for a session reach (``alternatives``: the session's passage or the
  value passage) every quote lies inside an alternative, at least one in one of them;
- at most QUOTES_MAX quotes (else quotes_bound: the flood cap, below).
Every assignment is searched (a complete, deterministic search, the quotes' occurrences tried in the revision's order
and the required sets' quotes in lexicographic order, so a proof that located under the probe's one-to-one rule
locates at the same spans), and a quote that occurs several times is located at an occurrence that fits. Anything else
fails the whole proof (fail-closed), with its reason. The spans are the revision's own offsets: the required sets'
quotes first, in the sets' order, then every further quote in the answer's order.

**QUOTES_MAX = 8, THE flood cap - ONE constant, contract/appraise_schema's (beside LOCAL_SCHEMA_Q, whose quotes it
bounds), read by this module and by contract/appraise_read (quotes_bound) and rendered into the question instruction
(contract/question_claims.PROOF)**; why 8, there. QUOTE_MAX_CHARS (300 characters a quote) stays appraise_read's.

It reads characters, never meaning: no word list, no regular-expression module. Settle never touches text: it reads
the ProofLocation this hands it."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, unique
from itertools import permutations

from studio.interpretation.contract.appraise_schema import QUOTES_MAX

MIN_CHARS = 12
MIN_TOKENS = 2
# the search's own bound (fail-closed): far above any real proof - at most QUOTES_MAX quotes, each located only inside
# the claim's few passages - so it can stop only a degenerate input, never a proof a reader gives
SEARCH_STEPS_MAX = 200_000


@unique
class ProofReason(Enum):
    """Why a proof is not located (settle d.2 row 3)."""
    MISSING = 'proof_missing'  # no quote
    SHORT = 'proof_short'  # a quote under MIN_CHARS non-space characters or MIN_TOKENS tokens
    UNLOCATED = 'proof_unlocated'  # a quote outside the claim's passages, an overlap, or a required set left empty
    BOUND = 'quotes_bound'  # more than QUOTES_MAX quotes (appraise_read reads the same cap: QuestionVerdict.quotes_bound)


PROOF_MISSING = ProofReason.MISSING.value
PROOF_SHORT = ProofReason.SHORT.value
PROOF_UNLOCATED = ProofReason.UNLOCATED.value
PROOF_BOUND = ProofReason.BOUND.value


@dataclass(frozen=True)
class ProofLocation:
    """The outcome of one claim's proof: ``located``, the located spans (the revision's offsets, one per quote: the
    required sets' quotes in the sets' order, then the further quotes in the answer's order), and the reason it is not
    located ('' when it is)."""
    located: bool
    spans: tuple[tuple[int, int], ...]
    reason: str


def _collapsed(text: str) -> tuple[str, list[int]]:
    """``text`` with every whitespace run written as one space, and each kept character's offset in ``text``."""
    out: list[str] = []
    offsets: list[int] = []
    previous_space = False
    for index, char in enumerate(text):
        if char.isspace():
            if previous_space:
                continue
            out.append(' ')
            offsets.append(index)
            previous_space = True
        else:
            out.append(char)
            offsets.append(index)
            previous_space = False
    return ''.join(out), offsets


def _occurrences(collapsed: str, offsets: list[int], needle: str) -> list[tuple[int, int]]:
    """Every occurrence of ``needle`` (already collapsed) in the collapsed revision, as revision offsets [start, end)."""
    out: list[tuple[int, int]] = []
    if not needle:
        return out
    at = collapsed.find(needle)
    while at != -1:
        start = offsets[at]
        end = offsets[at + len(needle) - 1] + 1
        out.append((start, end))
        at = collapsed.find(needle, at + 1)
    return out


def _inside(span: tuple[int, int], ranges: Sequence[tuple[int, int]]) -> bool:
    return any(low <= span[0] and span[1] <= high for low, high in ranges)


def _apart(span: tuple[int, int], chosen: Sequence[tuple[int, int]]) -> bool:
    return all(span[1] <= other[0] or other[1] <= span[0] for other in chosen)


def normalized(quote: str) -> str:
    """A quote as it is compared: whitespace runs collapsed to one space, leading and trailing whitespace dropped."""
    return ' '.join(quote.split())


def long_enough(quote: str) -> bool:
    words = normalized(quote)
    return sum(1 for char in words if not char.isspace()) >= MIN_CHARS and len(words.split(' ')) >= MIN_TOKENS


def _ranges(found: object) -> tuple[tuple[int, int], ...]:
    return tuple(getattr(found, 'ranges', ()) or ())


class _Search:
    """One proof's assignment search (module docstring): one occurrence per quote, none overlapping another, each inside
    the passages its role allows - a required set's own quote inside that set, a further quote inside any of the
    claim's passages - tried in a fixed order, the first fit kept. Bounded by SEARCH_STEPS_MAX steps (fail-closed)."""

    def __init__(self, found_at: Sequence[Sequence[tuple[int, int]]]) -> None:
        self.found_at = found_at
        self.steps = 0

    def fit(self, order: Sequence[int], allowed: Sequence[Sequence[Sequence[tuple[int, int]]]]
            ) -> list[tuple[int, int]] | None:
        """The first assignment of the quotes ``order`` names, the quote at position k inside one of ``allowed[k]``'s
        range sets, none overlapping; None when there is none (or the bound is spent)."""
        chosen: list[tuple[int, int]] = []

        def walk(position: int) -> bool:
            if position == len(order):
                return True
            for span in self.found_at[order[position]]:
                self.steps += 1
                if self.steps > SEARCH_STEPS_MAX:
                    return False
                if _apart(span, chosen) and any(_inside(span, ranges) for ranges in allowed[position]):
                    chosen.append(span)
                    if walk(position + 1):
                        return True
                    chosen.pop()
            return False

        return list(chosen) if walk(0) else None


def locate(text: str, required: Sequence[object], optional: object | None, quotes: Sequence[str],
           alternatives: Sequence[object] = ()) -> ProofLocation:
    """One claim's proof (module docstring). ``required``, ``optional`` and ``alternatives`` are passage sets: objects
    with ``ranges`` (contract/question_claims.PassageSet), each a sequence of (start, end)."""
    if not quotes:
        return ProofLocation(False, (), PROOF_MISSING)
    if len(quotes) > QUOTES_MAX:
        return ProofLocation(False, (), PROOF_BOUND)
    if not all(long_enough(quote) for quote in quotes):
        return ProofLocation(False, (), PROOF_SHORT)
    sets = [_ranges(found) for found in required]
    if any(not ranges for ranges in sets):  # a required passage with no words can never receive its quote
        return ProofLocation(False, (), PROOF_UNLOCATED)
    choices = [_ranges(found) for found in alternatives if _ranges(found)]
    if (sets and choices) or (not sets and not choices):  # no form names both; a claim names at least one passage
        return ProofLocation(False, (), PROOF_UNLOCATED)
    extra = _ranges(optional) if optional is not None else ()
    places = (sets + ([extra] if extra else [])) if sets else choices
    collapsed, offsets = _collapsed(text)
    # each quote's occurrences inside one range of one of the claim's passages: a quote with none lies outside them all
    found_at = [[span for span in _occurrences(collapsed, offsets, normalized(quote))
                 if any(_inside(span, ranges) for ranges in places)] for quote in quotes]
    if any(not spans for spans in found_at):
        return ProofLocation(False, (), PROOF_UNLOCATED)
    search = _Search(found_at)
    if not sets:  # a session reach: every quote inside an alternative (at least one quote, so at least one in one)
        spans = search.fit(range(len(quotes)), [places] * len(quotes))
        return ProofLocation(True, tuple(spans), '') if spans is not None else ProofLocation(False, (), PROOF_UNLOCATED)
    if len(quotes) < len(sets):
        return ProofLocation(False, (), PROOF_UNLOCATED)
    # which quote each required set receives, in lexicographic order (the probe's permutations, their first k places),
    # each remaining quote a further one inside any of the claim's passages
    for owners in permutations(range(len(quotes)), len(sets)):
        rest = [index for index in range(len(quotes)) if index not in owners]
        order = list(owners) + rest
        allowed = [[ranges] for ranges in sets] + [places] * len(rest)
        spans = search.fit(order, allowed)
        if spans is not None:
            return ProofLocation(True, tuple(spans), '')
        if search.steps > SEARCH_STEPS_MAX:
            break
    return ProofLocation(False, (), PROOF_UNLOCATED)
