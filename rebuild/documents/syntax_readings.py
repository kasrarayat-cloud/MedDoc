"""The pinned parser's reading of the texts the isolated Word parser asks about (trusted parent side only).

The isolated parser cannot load the pinned syntax model (its sandbox sees no native libraries), so it names what it
must classify and this parent reads it, and the SAME request runs again with the readings (service._run). Two kinds of
key are read (word_v3.reading_key):

  's:<clause>'     a clause holding a word whose signing sense depends on its grammatical role (word_v3.CANDIDATE:
                   'initial', 'sign'): which of those words carry the signing sense ({"s": [ordinals]});
  't:<statement>'  a printed statement holding a first-person pronoun or the consent act (word_v3.statement_key: the
                   printed text with its answer places left out): which sentences are a first-person declaration, which
                   of those attest (a clausal complement, the consent act, a predicate over the declarant's own
                   words), which embed the consent act under a governing verb, and which have a first-person subject
                   of their statement at all ({"x" every sentence, "d", "a", "c", "g": [[start, end]]}, in the
                   statement's own character offsets).

This module establishes no clinical or destination fact. Anything it cannot read is left out, and the isolated parser
then reads it in the HOLDING direction. No source text is cached, logged or sent anywhere; the parser is
core.v3_syntax's pinned local model.
"""
from __future__ import annotations

import re

if __package__:
    from .word_v3 import (CANDIDATE, CONSENT, MAX_CLAUSE_CHARS, MAX_READING_CLAUSES, MAX_STATEMENT_CHARS, clause_key,
                          statement_key)
else:  # pragma: no cover - never imported by the isolated worker
    from word_v3 import (CANDIDATE, CONSENT, MAX_CLAUSE_CHARS, MAX_READING_CLAUSES, MAX_STATEMENT_CHARS, clause_key,
                         statement_key)


def _parser():
    try:
        from core.v3_syntax import _parser as pinned
        return pinned()
    except Exception:
        return None


def _verbs():
    """The pinned model's own verb lexicon (core.v3_syntax._verbs), never a list of this module's."""
    try:
        from core.v3_syntax import _verbs as pinned
        return pinned()
    except Exception:
        return frozenset()


def _lock():
    """core.v3_syntax's lock: the one pinned parser is used by one caller at a time."""
    try:
        from core.v3_syntax import _lock as lock
        return lock
    except Exception:
        import threading
        return threading.Lock()


def _verb_form(word) -> bool:
    """The word is an inflection of a verb of the pinned lexicon ('print', 'dated', 'signing')."""
    lexicon = _verbs()
    w = (word or "").lower()
    forms = {w}
    for ending, base in (("ies", "y"), ("ied", "y"), ("es", ""), ("s", ""), ("ed", ""), ("ed", "e"), ("d", ""),
                         ("ing", ""), ("ing", "e")):
        if w.endswith(ending):
            forms.add(w[:-len(ending)] + base)
    return bool(forms & lexicon)


# ─── 's:' - the signing sense of 'initial' and 'sign' by the word's role in its clause ──────────────────────────────

def _sense(doc, token, word):
    """The signing sense of `token` ('initial', 'sign') in its clause, by its grammatical role."""
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
    # 'sign': the signing act unless the clause uses it as a clinical NOUN, read from its role and never from its
    # part-of-speech tag alone (the pinned model tags 'Sign present' a verb and 'Sign & date' a proper noun):
    #   the complement of 'of' ('Sign of infection'), a possessor ("Murphy's sign"), the subject of a predicate
    #   ('Sign elicited'), an adjective predicated of it ('Sign present', 'Sign positive'), or the modifier of a
    #   following noun ('Sign language interpreter', 'Sign and symptom review') - unless it is coordinated there with
    #   another act the lexicon knows as a verb ('Sign & print name').
    # Everything else - the whole caption ('Sign:'), an instruction ('Sign below', 'Please sign', 'Patient to sign',
    # 'Sign on the line'), a role's caption ('Nurse sign', 'Doctor sign/date') or a list of acts ('Sign & date',
    # 'Sign, date and time') - is the signing act.
    children = list(token.children)
    if any(c.dep_ == "prep" and c.lower_ == "of" for c in children) or any(c.dep_ == "poss" for c in children):
        return False
    if token.dep_ in ("nsubj", "nsubjpass"):
        return False
    following = doc[token.i + 1] if token.i + 1 < len(doc) else None
    if (following is not None and following.pos_ == "ADJ") or any(
            c.pos_ == "ADJ" and c.dep_ in ("advmod", "acomp", "amod", "oprd") for c in children):
        return False
    if token.dep_ in ("compound", "nmod", "amod") and token.head.i > token.i and token.head.pos_ in ("NOUN", "PROPN"):
        partners = [c for c in children if c.dep_ == "conj"]
        if not any(_verb_form(p.text) for p in partners):
            return False
    return True


def _clause(nlp, clause):
    doc = nlp(_cased(clause))
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
    return {"s": senses}


# ─── 't:' - first-person declarations and embedded consent, sentence by sentence ────────────────────────────────────

#: The dependency edges along which a clause still belongs to the statement the sentence makes: its main clause, a
#: coordinated or complement clause, a relative clause on one of its arguments, and those arguments. An adverbial
#: clause ('If we need to contact you, telephone:'), a parenthetical aside or an appended clause ('Allergies (so we can
#: keep you safe)', 'Follow-up booked (we will write to the GP)') and a prepositional attachment are not the statement.
GOVERNING = frozenset(("conj", "ccomp", "xcomp", "relcl", "dobj", "nsubj", "nsubjpass", "attr", "acomp", "oprd"))
#: Words that cannot end a complete statement: a preposition, determiner, conjunction or particle waiting for what the
#: blank supplies ('We recommend review in: ____', 'I reviewed this patient in clinic on ____.').
OPEN_ENDING = frozenset(("ADP", "DET", "CCONJ", "SCONJ", "PART"))
ASIDE = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")


def _dangling(doc) -> bool:
    words = [t for t in doc if not t.is_punct and not t.is_space]
    if words and words[-1].pos_ in OPEN_ENDING:
        return True
    return any(t.dep_ == "prep" and not any(c.dep_ in ("pobj", "pcomp") for c in t.children) for t in doc)


def _declaration(doc, nlp=None):
    """(declaration, attesting, governing) of one parsed sentence: a first-person pronoun is the subject of the statement it
    makes, and that statement either attests (a clausal complement - 'I confirm that ...', 'I agree to proceed' - the
    consent act, or a predicate over the declarant's own words - 'The information I have provided is accurate') or is
    complete before its answer place (it is answered, not completed: 'I understand the risks: ☐').

    A sentence opening with a prepositional or participial frame ('To the best of my knowledge I confirm the above is
    correct', 'Having read the leaflet I agree ...') is also read from its first-person subject on, when the frame ends
    in a noun or a comma before it (the pinned model attaches such a main clause to the frame's noun): that reading
    counts only when it ATTESTS, so a relative clause after a prepositional phrase ('For patients we see in clinic') is
    not made a declaration by it."""
    found = _governing_declaration(doc)
    if found[0] or nlp is None or not len(doc):
        return found
    opening = doc[0]
    if opening.pos_ == "ADP" or opening.tag_ in ("VBG", "VBN"):
        for token in doc:
            if token.i > 1 and token.pos_ == "PRON" and token.morph.get("Person") == ["1"] and \
                    token.lower_ in ("i", "we") and (doc[token.i - 1].pos_ in ("NOUN", "PROPN") or doc[token.i - 1].text == ","):
                declared, attesting, governs = _governing_declaration(nlp(doc[token.i:].text))
                if declared and attesting:
                    return True, True, True
    return found


def _governing_declaration(doc):
    """(declared, attesting, governing): `governing` is a first-person subject of the statement the sentence makes, whether
    or not that statement is complete; `declared` adds that it attests or is complete before its answer place."""
    governs = False
    for token in doc:
        if not (token.pos_ == "PRON" and token.morph.get("Person") == ["1"] and token.dep_ in ("nsubj", "nsubjpass")):
            continue
        head = token.head
        # A first-person subject agrees with its verb: 'Type I diabetes' (tagged a pronoun before a 3rd-person '-s'
        # form) is a numeral.
        if head.pos_ not in ("VERB", "AUX") or head.tag_ == "VBZ":
            continue
        path, node, governing = [head], head, True
        while node.dep_ != "ROOT":
            if node.dep_ not in GOVERNING or node.head is node:
                governing = False
                break
            node = node.head
            path.append(node)
        if not governing:
            continue
        governs = True
        root = path[-1]
        attesting = (any(c.dep_ in ("ccomp", "xcomp") for verb in path for c in verb.children if verb.pos_ in ("VERB", "AUX"))
                     or bool(CONSENT.search(head.text))
                     or (head is not root and any(c.dep_ in ("acomp", "attr") for c in root.children)))
        if attesting or not _dangling(doc):
            return True, attesting, True
    return False, False, governs


def _embedded(doc) -> bool:
    """The consent act (any inflection) sits inside a complement clause governed by another verb ('Record that the
    patient consents to proceed'), never merely beside one ('Consent obtained - state who explained the risks')."""
    for token in doc:
        if not CONSENT.fullmatch(token.text):
            continue
        node = token
        while node.dep_ != "ROOT" and node.head is not node:
            if node.dep_ in ("ccomp", "xcomp"):
                return True
            node = node.head
    return False


def _cased(text):
    """A statement printed in capitals ('I CONFIRM THAT THE INFORMATION IS CORRECT') read in ordinary case, the pronoun
    'I' kept: the same length, so every offset stays the printed one."""
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) < 4 or any(ch.islower() for ch in letters):
        return text
    return re.sub(r"\bi\b", "I", text.lower())


def _statement(nlp, statement):
    """{"x", "d", "a", "c", "g": [[start, end], ...]}: every sentence of `statement`, and those that are first-person
    declarations, that attest, that embed the consent act, and that have a first-person subject of their statement at
    all (governing - the isolated parser holds such a sentence when the place is answered by a SELECTION: 'I agree to:
    ☐ photographs ☐ teaching'). A bracketed aside is not the sentence's statement: the sentence is parsed without it; an
    aside counts as a declaration only when it attests on its own ('Patient statement (I confirm the above is true)'),
    and as governing when its own statement has a first-person subject ('Consent (I agree to the operation): ☐')."""
    sentences, declared, attested, embedded, governing = [], [], [], [], []
    for sentence in nlp(_cased(statement)).sents:
        span = [sentence.start_char, sentence.end_char]
        if not sentence.text.strip():
            continue
        sentences.append(span)
        text = sentence.text
        main = re.sub(r"\s+", " ", ASIDE.sub(" ", text)).strip()
        d = a = c = g = False
        if main:
            parsed = nlp(main)
            d, a, g = _declaration(parsed, nlp)
            c = _embedded(parsed)
        for aside in ASIDE.findall(text):
            inner = aside[1:-1].strip()
            if not inner:
                continue
            parsed = nlp(inner)
            _, aside_attests, aside_governs = _declaration(parsed)
            if aside_attests:
                d = a = True
            # An aside is the declarant's own statement only when it opens with its first-person subject ('Consent (I
            # agree to the operation)'); one opening with a subordinator explains the question ('Allergies (so we can
            # keep you safe)').
            opening = next((t for t in parsed if not t.is_punct and not t.is_space), None)
            g = g or (aside_governs and opening is not None and opening.pos_ == "PRON" and opening.morph.get("Person") == ["1"])
            c = c or _embedded(parsed)
        for flag, bucket in ((d, declared), (a, attested), (c, embedded), (g or d, governing)):
            if flag:
                bucket.append(span)
    return {"x": sentences, "d": declared, "a": attested, "c": embedded, "g": governing}


def read_clauses(keys) -> dict:
    """{key: reading} for each 's:' clause key and 't:' statement key (see the module docstring).

    A key the parser cannot read is left out (the isolated parser then reads it as holding). A candidate word the
    parser's tokens do not line up with is reported WITH the signing sense (holding)."""
    nlp = _parser()
    if nlp is None:
        return {}
    out = {}
    lock = _lock()
    for key in list(keys)[:MAX_READING_CLAUSES]:
        if not isinstance(key, str) or len(key) < 3 or key[1] != ":":
            continue
        kind, text = key[0], key[2:]
        try:
            if kind == "s" and text == clause_key(text) and 0 < len(text) <= MAX_CLAUSE_CHARS:
                with lock:
                    out[key] = _clause(nlp, text)
            elif kind == "t" and text == statement_key(text)[0] and 0 < len(text) <= MAX_STATEMENT_CHARS:
                with lock:
                    out[key] = _statement(nlp, text)
        except Exception:
            continue
    return out
