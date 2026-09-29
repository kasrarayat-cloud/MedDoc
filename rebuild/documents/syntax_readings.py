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
    # 'sign': the signing act only where the clause reads it as that ACT - never a clinical NOUN. ⚠️ A noun 'sign' with
    # a modifier ('Babinski sign', 'Romberg sign', 'Warning sign', 'Meningeal sign') has the same parse as a role's
    # caption, and holding it made every eponymous sign on an examination form a signature place that nothing could
    # answer (and the legacy fill refuse the whole export). So:
    #   a clinical noun, whatever else the clause holds: the complement of 'of' ('Sign of infection'), a possessor
    #   ("Murphy's sign"), the subject of a predicate ('Sign elicited'), an adjective predicated of it ('Sign present',
    #   'Sign positive', 'Positive Romberg sign'), or the modifier of a following noun ('Sign language interpreter',
    #   'Sign and symptom review') unless listed there with another act ('Sign & print name');
    #   the act: the parser's VERB ('Sign', 'Sign below', 'Please sign', 'Patient to sign', 'Parent sign'), a list of
    #   acts ('Sign & date', 'Sign, date and time', 'Doctor sign/date', 'Sign/date'), the bare word ('Sign:'), or the
    #   noun captioned by a person who signs ('Nurse sign', 'Patient sign', 'Witness sign' - SIGNER);
    #   anything else - a noun with its own modifiers - is the clinical sign.
    children = list(token.children)
    if any(c.dep_ == "prep" and c.lower_ == "of" for c in children) or any(c.dep_ == "poss" for c in children):
        return False
    if token.dep_ in ("nsubj", "nsubjpass"):
        return False
    listed = _listed_act(doc, token)
    if token.dep_ in ("compound", "nmod", "amod") and token.head.i > token.i and token.head.pos_ in ("NOUN", "PROPN") \
            and not listed:
        return False
    if any(c.dep_ in ("compound", "amod", "nmod", "nsubj") and c.i < token.i and SIGNER.fullmatch(c.lower_)
           for c in children):
        return True
    if any(c.dep_ in ("aux", "auxpass") for c in children):
        return True                           # a modal or 'to' makes it a verb: 'Patient must sign', 'Nurse to sign'
    # The pinned model also reads '<noun> sign' as a subject and its verb ('Chvostek sign', 'Homans sign', 'Kehr sign'):
    # a subject that is not a pronoun or a person who signs is the sign's own modifier.
    if any(c.dep_ in ("nsubj", "nsubjpass") and c.i < token.i and c.pos_ != "PRON" for c in children):
        return False
    following = doc[token.i + 1] if token.i + 1 < len(doc) else None
    if (following is not None and following.pos_ == "ADJ") or any(
            c.pos_ == "ADJ" and c.dep_ in ("advmod", "acomp", "amod", "oprd") for c in children):
        return False
    words = [t for t in doc if not (t.is_punct or t.is_space)]
    return token.pos_ in ("VERB", "AUX") or listed or words == [token]


#: The persons a form names as the one who signs, read only as the modifier of a noun 'sign' ('Nurse sign', 'Patient
#: sign'): the signer roles the application already names (core.tab_review's clinical roles and NOT_THE_CLINICIAN,
#: documents.source_policy's printed roles) and the staff who sign an administration record. An eponym or a
#: description ('Babinski sign', 'Warning sign') is never one of them, so it stays the clinical sign.
SIGNER = re.compile(r"(?:patient|witness|guardian|parent|interpreter|relative|carer|caregiver|family|representative|"
                    r"nurse|midwife|doctor|physician|clinician|consultant|surgeon|anaesthetist|anesthetist|registrar|"
                    r"resident|practitioner|pharmacist|prescriber|checker|staff|supervisor|manager|employer|assessor|"
                    r"examiner|student|therapist|dentist|radiographer|sonographer|operator|gp|hca|rn|md|np|pa)")


def _listed_act(doc, token) -> bool:
    """`token` is printed in a LIST of acts with another word the pinned lexicon knows as a verb: coordinated with it
    ('Sign & date', 'Sign, date and time', 'Sign & print name'), set beside it ('Doctor sign/date'), or joined to the
    noun it modifies by list punctuation alone ('Sign/date'). 'Sign and symptom review' lists no act."""
    if any(c.dep_ in ("conj", "appos") and _verb_form(c.text) for c in token.children):
        return True
    head = token.head
    if head is not token and head.i > token.i and _verb_form(head.text) and token.dep_ in ("nmod", "compound", "conj", "appos"):
        between = doc[token.i + 1:head.i]
        return bool(len(between)) and all(t.is_punct or t.lower_ in ("and", "or", "&", "+", "/") for t in between)
    return False


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
    # A preposition closing a reduced relative clause ('the operation described above', 'the risks listed below')
    # points at the form itself; it waits for nothing.
    pointing = [t for t in doc if t.dep_ == "prep" and t.pos_ == "ADP" and t.head.dep_ == "acl" and t.head.tag_ == "VBN"
                and not list(t.children)]
    if words and words[-1].pos_ in OPEN_ENDING and words[-1] not in pointing:
        return True
    return any(t.dep_ == "prep" and t not in pointing and not any(c.dep_ in ("pobj", "pcomp") for c in t.children)
               for t in doc)


def _declaration(doc, nlp=None):
    """(declaration, attesting, governing) of one parsed sentence: a first-person pronoun is the subject of a finite verb
    of the statement it makes, and that statement either attests (a clausal complement - 'I confirm that ...', 'I agree
    to proceed', 'I am happy to go ahead' - an agreement to what it names - 'I agree to the operation described above' -
    the consent act, or a predicate over the declarant's own words - 'The information I have provided is accurate'), is
    COMPLETED BY ITS BLANK at its verb's own complement ('I hereby certify that ____', 'I declare that:', 'I agree to
    ____', 'I have been informed that ____': the blank is what is attested, never a note's answer), or is complete
    before its answer place (it is answered, not completed: 'I understand the risks: ☐').

    A sentence whose first-person subject does not open its clause is also read from that subject on: after a
    prepositional or participial frame ('To the best of my knowledge I confirm the above is correct', 'Having read the
    leaflet I agree ...'), when the frame ends in a noun or a comma before it (the pinned model attaches such a main
    clause to the frame's noun), and after a noun a capital 'I' may number ('Today I confirm ...', but 'Grade I reflux'):
    that reading counts only when it ATTESTS, so a relative clause after a prepositional phrase ('For patients we see in
    clinic') is not made a declaration by it, and a numeral never is ('Grade I tear', 'Type I fracture': 'I tear'
    attests nothing)."""
    found = _governing_declaration(doc)
    if found[0] or nlp is None or not len(doc):
        return found
    opening = doc[0]
    framed = opening.pos_ == "ADP" or opening.tag_ in ("VBG", "VBN")
    for token in doc:
        if not (token.i > 0 and token.pos_ == "PRON" and token.morph.get("Person") == ["1"] and token.lower_ in ("i", "we")):
            continue
        before = doc[token.i - 1]
        if (framed and token.i > 1 and (before.pos_ in ("NOUN", "PROPN") or before.text == ",")) or _numbered(doc, token):
            declared, attesting, governs = _governing_declaration(nlp(doc[token.i:].text))
            if declared and attesting:
                return True, True, True
    return found


def _numbered(doc, token) -> bool:
    """A capital 'I' printed straight after a word it may number ('Grade I reflux', 'Stage I disease', 'Type I fracture',
    'Mallampati class I airway', 'Dose I given'): it does not open its clause, so it is not read as the declarant."""
    if token.text != "I" or token.i == 0:
        return False
    before = doc[token.i - 1]
    return not (before.is_punct or before.is_space) and before.pos_ in ("NOUN", "PROPN", "NUM", "ADJ", "X", "SYM")


def _finite(head) -> bool:
    """The first-person subject's head is a finite verb: an auxiliary, a verb with its own auxiliary, a past form, or a
    present form the pinned lexicon knows as a verb - never a noun the tagger read as a present-tense verb after a
    numeral ('Stage I disease', 'Class I obesity', 'Grade I tumour'). Without the lexicon it is read as a verb (holding)."""
    if head.pos_ == "AUX" or any(c.dep_ in ("aux", "auxpass") for c in head.children):
        return True
    if head.tag_ in ("VBP", "VB"):
        return not _verbs() or _verb_form(head.text)
    return True


def _between_ok(doc, start, end) -> bool:
    """Only adverbs, particles, punctuation and a predicate adjective stand between two tokens ('I hereby certify that',
    'I am aware that')."""
    return all(t.pos_ in ("ADV", "PART", "PUNCT") or (t.pos_ == "ADJ" and t.dep_ == "acomp") for t in doc[start + 1:end])


def _completed_by_blank(doc, path) -> bool:
    """The statement ends on its verb's OWN complement marker, so the blank after it is the attested complement: a
    complementizer ('I hereby certify that', 'I declare that:', 'I understand that', 'I have been informed that', 'I am
    aware that') or 'to' straight after the verb ('I agree to', 'I consent to'). A preposition after the verb's object or
    adjunct ('I reviewed this patient in clinic on', 'We recommend review in:') waits for an ordinary answer."""
    words = [t for t in doc if not (t.is_punct or t.is_space)]
    if not words:
        return False
    last = words[-1]
    complementizer = last.pos_ == "SCONJ" and last.lower_ in ("that", "whether", "if")
    to = last.lower_ == "to" and last.pos_ in ("ADP", "PART")
    if not (complementizer or to):
        return False
    anchor = last.head
    # 'to' only straight after the verb itself ('I am allergic to' waits for an ordinary answer); a complementizer also
    # after the predicate adjective ('I am aware that').
    if anchor not in path and not (complementizer and anchor.dep_ == "acomp" and anchor.head in path):
        return False
    return anchor.i < last.i and _between_ok(doc, anchor.i, last.i)


def _agrees(doc, path) -> bool:
    """The statement agrees to what it names: a verb of the statement takes 'to' and its printed object straight after
    it ('I agree to the operation described above'), or a predicate adjective takes a clausal complement ('I am happy
    to go ahead with the operation', 'I am willing to proceed')."""
    for verb in path:
        for c in verb.children:
            if c.dep_ == "prep" and c.lower_ == "to" and c.i > verb.i and _between_ok(doc, verb.i, c.i) and \
                    any(g.dep_ in ("pobj", "pcomp") for g in c.children):
                return True
            if c.dep_ == "acomp" and any(g.dep_ in ("xcomp", "ccomp") for g in c.children):
                return True
    return False


def _governing_declaration(doc):
    """(declared, attesting, governing): `governing` is a first-person subject of a finite verb of the statement the
    sentence makes, whether or not that statement is complete; `declared` adds that it attests, is completed by its
    blank, or is complete before its answer place."""
    governs = False
    for token in doc:
        if not (token.pos_ == "PRON" and token.morph.get("Person") == ["1"] and token.dep_ in ("nsubj", "nsubjpass")):
            continue
        head = token.head
        # A first-person subject agrees with its verb: 'Type I diabetes' (tagged a pronoun before a 3rd-person '-s'
        # form) is a numeral, and so is an 'I' after the word it numbers or before a noun read as a verb.
        if head.pos_ not in ("VERB", "AUX") or head.tag_ == "VBZ" or _numbered(doc, token) or not _finite(head):
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
        # An agreement to what the statement names makes a complete statement attest; it never completes one that
        # still waits for its blank ('I was admitted to hospital on: ____' stays an ordinary answer).
        if attesting or not _dangling(doc):
            return True, attesting or _agrees(doc, path), True
        if _completed_by_blank(doc, path):
            return True, True, True
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
