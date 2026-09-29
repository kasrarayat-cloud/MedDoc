"""The pinned parser's reading of the clauses the isolated Word parser asks about (trusted parent side only).

The isolated parser cannot load the pinned syntax model (its sandbox sees no native libraries), so for each clause that
holds a word whose signing sense depends on its grammatical role (word_v3.CANDIDATE) or that names the consent act
(word_v3.CONSENT) it asks this parent for a reading, and applies it inside the sandbox. This module establishes no
clinical or destination fact: it reports, per clause, which candidate words carry the signing / first-person sense and
whether a consent is embedded under a governing verb. Anything it cannot read is reported in the HOLDING direction.

No source text is cached, logged or sent anywhere; the parser is core.v3_syntax's pinned local model.
"""
from __future__ import annotations

import re

if __package__:
    from .word_v3 import CANDIDATE, CONSENT, MAX_CLAUSE_CHARS, MAX_READING_CLAUSES, clause_key
else:  # pragma: no cover - never imported by the isolated worker
    from word_v3 import CANDIDATE, CONSENT, MAX_CLAUSE_CHARS, MAX_READING_CLAUSES, clause_key


def _parser():
    try:
        from core.v3_syntax import _parser as pinned
        return pinned()
    except Exception:
        return None


def _lock():
    """core.v3_syntax's lock: the one pinned parser is used by one caller at a time."""
    try:
        from core.v3_syntax import _lock as lock
        return lock
    except Exception:
        import threading
        return threading.Lock()


def _sense(doc, token, word):
    """The signing (initial, sign) or first-person (I, we) sense of `token` in its clause, by its grammatical role."""
    if any(child.dep_ == "neg" for child in token.children):
        return False                          # 'Do not sign this answer for another person' names no signing place
    if word == "initial":
        # An adjectival modifier of a following noun, with no determiner between them ('Initial assessment'), is the
        # ordinary adjective. Anything else - the clause's head ('Initial here'), a noun ('Staff initial'), a verb
        # ('Nurse to initial') or a mis-attached modifier with a determiner between ('Initial each box') - is initials.
        head = token.head
        adjective = (token.dep_ in ("amod", "compound") and head.i > token.i and head.pos_ in ("NOUN", "PROPN")
                     and not any(t.pos_ == "DET" for t in doc[token.i + 1:head.i]))
        return not adjective
    if word == "sign":
        # A verb ('Sign below', 'Please sign', 'Patient to sign') or the whole caption ('Sign:'); a noun with other
        # words ('Sign of infection', 'Babinski sign') is clinical.
        alone = all(t.is_punct or t.i == token.i for t in doc)
        return token.pos_ == "VERB" or alone
    # 'I' / 'we': a first-person pronoun subject ('I declare', 'We confirm', 'The patient and I agreed'). The pinned
    # model tags the numeral in 'Type I diabetes' a pronoun too, so 'I' also has to OPEN its clause: first, or after a
    # conjunction, a comma or an adverb ('... and I', ', I', 'then I') - never after the noun it numbers ('Type I').
    if token.pos_ != "PRON":
        return False
    if word == "we":
        return True
    return token.i == 0 or doc[token.i - 1].pos_ in ("CCONJ", "SCONJ", "PUNCT", "ADV", "INTJ")


def read_clauses(clauses) -> dict:
    """{clause: {"s": [ordinals of candidate words with the signing / first-person sense], "c": consent embedded}}.

    A clause the parser cannot read is left out (the isolated parser then reads it as holding). A candidate word the
    parser's tokens do not line up with is reported WITH the sense (holding)."""
    nlp = _parser()
    if nlp is None:
        return {}
    out = {}
    lock = _lock()
    for clause in list(clauses)[:MAX_READING_CLAUSES]:
        if not isinstance(clause, str) or clause != clause_key(clause) or not 0 < len(clause) <= MAX_CLAUSE_CHARS:
            continue
        try:
            with lock:
                doc = nlp(clause)
        except Exception:
            continue
        by_start = {t.idx: t for t in doc}
        senses = []
        for ordinal, match in enumerate(CANDIDATE.finditer(clause)):
            token = by_start.get(match.start())
            printed = match.group(0).lower()
            word = re.sub(r"^(?:counter-?|co-?|under|re-)", "", printed)
            if token is None or token.text.lower() != printed:
                senses.append(ordinal)            # the parser split it differently: holding
            elif _sense(doc, token, word):
                senses.append(ordinal)
        embedded = bool(CONSENT.search(clause)) and any(t.dep_ == "ccomp" for t in doc)
        out[clause] = {"s": senses, "c": embedded}
    return out
