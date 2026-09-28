"""Bounded complete literal observations under the full ordinary relation contract.

This reader never turns an entity or clinician into the patient. Full source
subjects, negation, passive agents and reported clauses stay in the answer.
Destination meaning still requires qualification of the exact model contract.
"""
import bisect
import re
import unicodedata
from . import v3_syntax as syntax

# Concrete clinical/context entities can be explicit local subjects without
# being people. Unknown nominal classes gain no allowance from this reader.
ENTITIES = frozenset(('accommodation residence housing home facility medication medicine drug dose '
    'treatment therapy prescription diagnosis condition illness disease symptom injury infection '
    'examination assessment result report investigation').split())
CLINICIANS = frozenset('clinician doctor physician nurse supervisor therapist pharmacist staff team'.split())
FOREIGN = re.compile(r"\b(?:mother|father|sister|brother|son|daughter|wife|husband|partner|relative|family|"
                     r"neighbou?r|someone|anyone|another|other|different)\b|['’]s\b", re.I)
NONFACT = re.compile(r'\b(?:if|unless|suppose|imagine|hypothetical|generally|typically|usually|perhaps|possibly|maybe)\b|[?"“”]', re.I)
SUBJECTS = ('nsubj', 'nsubjpass')
CONTACT_VERBS = tuple(frozenset(group.split()) for group in ('see saw seen sees', 'meet met meets', 'visit visited visits',
    'examine examined examines', 'assess assessed assesses', 'review reviewed reviews', 'contact contacted contacts'))


def _contact_question(verb, question):
    return any(verb.text.casefold() in group and any(re.search(r'\b' + word + r'\b', question, re.I) for word in group)
               for group in CONTACT_VERBS)


def _foreign_context(reading, unit, parser):
    """An unowned entity cannot silently become the patient's after another actor.

    Read grammatical source subjects, not a list of personal names. Only an
    explicit patient subject/object establishes a new patient anchor; an entity
    clause retains the current ownership and an unknown actor stays unresolved.
    """
    foreign = False
    roles = reading.setdefault('_ordinary_source_roles', {})
    for previous in reading['units']:
        if previous['id'] == unit['id']: break
        if previous['id'] not in roles:
            text = previous['quote']; role = 'foreign'
            if reading['parsed'].get(previous['id']):
                role = 'labelled'
            elif 0 < len(text) <= syntax.MAX_CHARACTERS:
                parsed = parser(text)
                if len(list(parsed.sents)) == 1:
                    root = next(iter(parsed.sents)).root
                    subjects = [t for t in root.children if t.dep_ in SUBJECTS]
                    if len(subjects) == 1:
                        subject = subjects[0]
                        if (_finite(root) and subject.text.casefold() == 'patient' and
                                all(c.dep_ == 'det' for c in subject.children)):
                            role = 'patient'
                        elif _word(subject) in ENTITIES and _nominal(subject) and not FOREIGN.search(text):
                            role = 'entity'
                        elif _finite(root) and _word(subject) in CLINICIANS and _patient_object(root) and not FOREIGN.search(text):
                            role = 'patient'
            roles[previous['id']] = role
        role = roles[previous['id']]
        if role == 'patient': foreign = False
        elif role == 'foreign': foreign = True
    return foreign

def _word(token):
    word = token.text.casefold()
    return word[:-1] if word.endswith('s') and word[:-1] in ENTITIES | CLINICIANS else word


def _finite(verb):
    return any('Fin' in token.morph.get('VerbForm') for token in (verb, *verb.children)
               if token is verb or token.dep_ in ('aux', 'auxpass'))


def _nominal(subject, *, determiners=('the', 'this', 'each', 'no')):
    words = list(subject.subtree)
    return (subject.pos_ == 'NOUN' and not any(t.dep_ == 'conj' for t in subject.children)
            and any(t.dep_ == 'det' and t.text.casefold() in determiners for t in subject.children)
            and all(t.i == subject.i or t.dep_ in ('det', 'amod', 'compound', 'advmod', 'neg')
                    or t.dep_ == 'acl' and t.pos_ == 'NOUN' for t in words))


def _patient_object(verb):
    return any(t.dep_ in ('dobj', 'obj') and t.text.casefold() == 'patient'
               and any(c.dep_ == 'det' and c.text.casefold() in ('the', 'this') for c in t.children)
               and not any(c.dep_ in ('poss', 'appos', 'compound', 'conj', 'acl', 'relcl') for c in t.children)
               for t in verb.children)


def _base(doc):
    words = [t for t in doc if not t.is_punct and not t.is_space]
    return (0 < len(doc) <= syntax.MAX_TOKENS and len(list(doc.sents)) == 1
            and bool(words) and words[-1].pos_ not in ('CCONJ', 'SCONJ', 'ADP', 'DET', 'AUX', 'PART')
            and not any(t.tag_ == 'MD' for t in doc))


def _patient_copular_complement(doc):
    """A finite patient copula with one complete adjectival/nominal complement.

    Only this syntax allowance is new. The caller still requires the signed
    complete-source relation and all destination, source and context guards.
    Negation stays in the exact free-text answer; it never selects an option.
    """
    from . import generation as g
    root = next(iter(doc.sents)).root
    if root.pos_ != 'AUX' or root.text.casefold() not in ('am', 'is', 'are', 'was', 'were', 'be', 'been') or not _finite(root):
        return False
    subjects = [t for t in root.children if t.dep_ == 'nsubj']
    if len(subjects) != 1 or sum(t.dep_ in SUBJECTS for t in doc) != 1:
        return False
    subject = subjects[0]
    if subject.text.casefold() != 'patient' or subject.i >= root.i or any(
            t.i != subject.i and not (t.dep_ == 'det' and t.text.casefold() in ('the', 'this'))
            for t in subject.subtree):
        return False
    complements = [t for t in root.children if t.dep_ == 'acomp' and t.pos_ == 'ADJ']
    if len(complements) != 1 or any(t.dep_ not in ('nsubj', 'acomp', 'neg', 'punct', 'aux') for t in root.children):
        return False
    adjective = complements[0]
    prepositions = [t for t in adjective.children if t.dep_ == 'prep' and t.pos_ == 'ADP']
    if len(prepositions) != 1 or any(t.dep_ != 'prep' for t in adjective.children):
        return False
    prep = prepositions[0]
    if prep.text.casefold() not in ('to', 'on', 'for', 'with', 'under', 'at', 'in', 'of', 'from'):
        return False
    objects = [t for t in prep.children if t.dep_ == 'pobj' and t.pos_ in ('NOUN', 'PROPN')]
    if len(objects) != 1 or list(prep.children) != objects:
        return False
    # An appositional noun/acronym remains inside its complete nominal object;
    # nested predicates, actors, coordination and a trailing preposition do not.
    if any(t.pos_ not in ('NOUN', 'PROPN', 'ADJ', 'DET', 'NUM', 'PUNCT') or
           t.dep_ not in ('pobj', 'compound', 'amod', 'det', 'nummod', 'appos', 'punct')
           for t in objects[0].subtree):
        return False
    if any(match.group().casefold() != 'to' for text in g.safety_readings(doc.text)
           for match in g.UNSETTLED.finditer(text)):
        return False
    # Bind the one otherwise-unsettled word to this actual nominal preposition,
    # never remove "to" generally or grant an infinitive/purpose clause.
    return all((match.start(), match.end()) == (prep.idx, prep.idx + len(prep.text))
               for match in g.UNSETTLED.finditer(doc.text))


def _simple_fact(doc, question):
    if not _base(doc) or FOREIGN.search(doc.text): return False
    if any(t.dep_ in ('ccomp', 'xcomp', 'advcl', 'relcl', 'parataxis', 'csubj', 'csubjpass')
           or t.dep_ == 'acl' and t.pos_ == 'VERB' for t in doc): return False
    root = next(iter(doc.sents)).root
    if root.pos_ not in ('VERB', 'AUX'): return False
    if _patient_copular_complement(doc): return 'patient'
    clauses = [root] + [t for t in doc if t.dep_ == 'conj' and t.pos_ in ('VERB', 'AUX')
                         and t.head.pos_ in ('VERB', 'AUX')]
    clinical_actor = False
    for verb in clauses:
        subjects = [t for t in verb.children if t.dep_ in SUBJECTS]
        if not subjects and verb is not root:
            # Shared-subject coordination must remain finite.
            subjects = [t for t in root.children if t.dep_ in SUBJECTS]
        if len(subjects) != 1 or not _finite(verb): return False
        subject = subjects[0]
        if subject.i >= verb.i or not _nominal(subject): return False
        noun = _word(subject)
        if noun in ENTITIES: continue
        if noun in CLINICIANS and _contact_question(verb, question) and _patient_object(verb):
            clinical_actor = True
            continue
        return False
    return 'clinical_actor' if clinical_actor else 'entity'


class _Unbounded(Exception):
    """A predicate with more syntactic readings than this bounded reader keeps."""


class OpposedClaim(ValueError):
    """A selected statement is directly opposed; the relation read refuses it."""


# A predicate head's dependants that restate or rename it (each conjunct or
# appositive is a complete reading of its own), qualify it adverbially, or
# carry no topic word at all. Everything else is part of the complete topic.
_ALTERNATES = ('conj', 'appos')
_ADVERBIAL = ('advmod', 'npadvmod')
# Negation is polarity, not topic. A determiner only refers or quantifies (a
# quantifier is read separately and only withholds), and a possessive case
# marker only refers. An answer ("Subject to MAPPA: no") is cut off by _limit.
_NO_TOPIC = ('neg', 'preconj', 'cc', 'punct', 'det', 'predet', 'case')
# Copular complements by dependency role, never by part of speech: the pinned
# tagger reads "well" as an adverb in "is well" and an adjective in "is not well".
_PREDICATES = ('acomp', 'oprd', 'attr')
_INDIRECT = ('xcomp', 'ccomp', 'advcl')
# A word modifying a noun: before it, attributive ("suicidal ideation"); after
# it, a reduced relative that predicates the noun ("Patient subject to MAPPA").
_MODIFIERS = ('amod', 'compound', 'nmod', 'poss')
# A nominal complement's noun also occurs as an ordinary argument ("The nurse
# reviewed it"); there, and only for a noun, an occurrence states no predicate
# unless it carries the predicate's own complement. An adjective or verb in an
# unrecognised role still withholds.
_NOMINAL = ('NOUN', 'PROPN', 'PRON', 'NUM')
_ARGUMENTS = ('nsubj', 'nsubjpass', 'dobj', 'iobj', 'dative', 'pobj', 'agent')
# Dependants that may place a clause at another time than its tense alone (the
# pinned parser's labels: it has no "tmod" or "obl").
_TIMED = ('advmod', 'npadvmod', 'advcl')
_FUNCTION = ('ADP', 'DET', 'PRON', 'CCONJ', 'SCONJ', 'PART', 'AUX', 'PUNCT', 'SPACE', 'INTJ')
_READINGS = 64
_ANSWERS = 'quillmd.v3_literal_facts.answers'
_CLAIMS = 'quillmd.v3_literal_facts.claims'
_PREFIX = 4    # letters of a prefix that may reverse a word ("un", "non", "dis", "semi")
_ACRONYM = 10  # most words one acronym is read as standing for
# Roles of a written prefix the parser splits off as its own word ("non smoker",
# "semi conscious"); a determiner, negation or case marker is none.
_PREFIX_ROLES = ('compound', 'amod', 'advmod', 'nmod', 'npadvmod', 'dep')


_HYPHENS = frozenset('\u002d\u2010\u2011')
# Every dash that may join a written word: Unicode's Pd category and the minus sign.
_DASHES = ('\u002d\u058a\u05be\u1400\u1806\u2010\u2011\u2012\u2013\u2014\u2015\u2e17\u2e1a\u2e3a\u2e3b\u2e40'
           '\u2e5d\u301c\u3030\u30a0\ufe31\ufe32\ufe58\ufe63\uff0d\U00010ead\u2212')


def _dash(text):
    return bool(text) and all(unicodedata.category(c) == 'Pd' or c == '\u2212' for c in text)


def _separator(token):
    """A label separator: any colon form, a dash that never joins a word ("Subject
    to MAPPA\u2014no"), or a hyphen spaced off from its words ("Subject to MAPPA -
    no"). A hyphen inside a word ("non-allergic") is not one."""
    from .generation import COLONS
    if any(c in COLONS for c in token.text): return True
    return _dash(token.text) and (not set(token.text) <= _HYPHENS or bool(
        token.whitespace_ or token.i > 0 and token.doc[token.i - 1].whitespace_))


def _answered(token):
    """A separator or an interjection answer after it ("Subject to MAPPA; no")."""
    return _separator(token) or token.pos_ == 'INTJ'


def _singular(word):
    """One topic word for its singular and plural forms; only ever widens sameness."""
    if len(word) > 4 and word.endswith('ies'): return word[:-3] + 'y'
    if len(word) > 3 and word.endswith('s') and not word.endswith(('ss', 'us', 'is')): return word[:-1]
    return word


def _surface(token):
    """The whole written word the token belongs to, without its dashes: the
    tokenizer splits "non-allergic" or "non\u2013smoker" into tokens that are one
    word, and keeps "non\u2212compliant" as one token. A short word the parser links
    directly to it just before it ("non smoker", "semi conscious", "Non allergic")
    is read as a prefix written apart; that only relates it as a prefixed form,
    which withholds whatever the prefix means."""
    doc = token.doc; start = end = token.i
    joined = lambda t: t.text.isalpha() or _dash(t.text)
    while start > 0 and not doc[start - 1].whitespace_ and joined(doc[start - 1]): start -= 1
    while end + 1 < len(doc) and not doc[end].whitespace_ and joined(doc[end + 1]): end += 1
    word = ''.join(c for t in doc[start:end + 1] for c in t.text if not _dash(c))
    before = start - 1
    while before >= 0 and _dash(doc[before].text): before -= 1
    if before >= 0 and before != token.i:
        prefix = doc[before]
        if (prefix.text.isalpha() and len(prefix.text) <= _PREFIX
                and (prefix.head.i == token.i and prefix.dep_ in _PREFIX_ROLES
                     or token.head.i == prefix.i and prefix.pos_ in _NOMINAL + ('ADJ', 'ADV', 'X'))):
            word = prefix.text + word
    return _singular(word.casefold())


def _wordlike(token):
    """A written word, whether or not a dash is written inside it ("non\u2212compliant")."""
    return token.is_alpha or (any(c.isalpha() for c in token.text)
                              and all(c.isalpha() or _dash(c) for c in token.text))


def _related(a, b):
    """'same', 'prefixed' when one word is the other after a short alphabetic
    prefix (stable/unstable, allergic/nonallergic, smoker/non-smoker), or None.
    Whether a prefix reverses the word is never decided here: a prefixed form
    only ever withholds, so nothing is adopted from it."""
    if a == b: return 'same'
    short, long = sorted((a, b), key=len)
    prefix = long[:len(long) - len(short)]
    if len(short) >= 4 and long.endswith(short) and 0 < len(prefix) <= _PREFIX and prefix.isalpha():
        return 'prefixed'
    return None


def _quantifier(token):
    """A determiner that quantifies rather than refers ("no", "any", "all"), or an
    indefinite or negative pronoun ("anything", "nothing"). Its scope, and so the
    polarity of the claim it is in, is not read here: it only ever withholds."""
    kinds = set(token.morph.get('PronType'))
    if token.dep_ in ('det', 'predet'):
        return not kinds & {'Art', 'Dem', 'Prs'}
    return token.pos_ == 'PRON' and bool(kinds & {'Ind', 'Neg', 'Tot'})


def _topic_word(token):
    # Articles, punctuation and negation are never topic identity; negation is
    # read as polarity from the dependency parse, not from a list of words. A
    # possessive pronoun refers to an actor, never names a different topic.
    return not (token.is_punct or token.is_space or token.dep_ in _NO_TOPIC
                or 'Art' in token.morph.get('PronType')
                or token.dep_ == 'poss' and 'Prs' in token.morph.get('PronType'))


def _combine(left, right):
    result = {tuple(sorted(a + b)) for a in left for b in right}
    if len(result) > _READINGS: raise _Unbounded()
    return result


def _topic_readings(token, limit, top=False, nested=False):
    """Every complete reading of one predicate subtree, as source token indices.

    The whole literal subtree is always a reading. A coordinated or appositive
    nominal also states the predicate of each conjunct/renaming, and an adverbial
    qualifier may be absent; at the predicate head, material before the head may
    be absent too (tagger variance), and each prepositional complement is read as
    its own part; inside a complement (``nested``), a further prepositional
    phrase may be absent ("MAPPA as of this week"). Nothing at or after a label
    separator (``limit``) is topic: it is the answer. This only widens what is the
    SAME topic, so it can withhold an answer and never grants one.
    """
    own = {(token.i,)} if _topic_word(token) and token.i < limit else {()}
    alternates = []
    for child in sorted(token.children, key=lambda t: t.i):
        if top and child.dep_ in ('conj', 'cc', 'prep'):
            continue  # a coordinated head is its own occurrence; a complement is a part
        if child.dep_ in _NO_TOPIC or child.is_punct or child.is_space or child.left_edge.i >= limit:
            continue
        if child.dep_ in _ALTERNATES:
            alternates.append(_topic_readings(child, limit, nested=nested))
        elif child.dep_ in _ADVERBIAL or (top and child.i < token.i) or (nested and child.dep_ == 'prep'):
            own = own | _combine(own, _topic_readings(child, limit, nested=nested))
        else:
            own = _combine(own, _topic_readings(child, limit, nested=nested))
    whole = own
    for readings in alternates:
        whole = _combine(whole, readings)
    result = own | whole
    for readings in alternates:
        result |= readings
    if len(result) > _READINGS: raise _Unbounded()
    return result


def _words(doc, indices):
    """Casefolded words in source order, each marked when written as an acronym."""
    return tuple((_singular(doc[i].text.casefold()), len(doc[i].text) > 1 and doc[i].text.isalpha()
                  and doc[i].text.isupper()) for i in sorted(indices))


def _initials(words):
    return {''.join(w[0] for w, _ in words[i:j]) for i in range(len(words))
            for j in range(i + 2, min(len(words), i + _ACRONYM) + 1)}


def _cover(small, large):
    """Whether every word of ``small`` is a word of ``large``. An acronym stands for
    the run of words whose initials it spells, in either reading ("MAPPA" and
    "Multi-Agency Public Protection Arrangements"), whether or not the note
    states the apposition itself. A word right after an acronym that begins with
    the acronym's final letter may restate the word it ends with ("MAPPA
    arrangements", "HIV virus"), so it is the acronym's own word too."""
    words = {w for w, _ in large}
    missing = [i for i, (w, _) in enumerate(small) if w not in words]
    if not missing: return True
    acronyms = {w for w, acronym in large if acronym}
    covered = set()
    if acronyms:
        for i in range(len(small)):
            for j in range(i + 2, min(len(small), i + _ACRONYM) + 1):
                if ''.join(w[0] for w, _ in small[i:j]) in acronyms: covered.update(range(i, j))
    missing = [i for i in missing if i not in covered]
    if not missing: return True
    missing = [i for i in missing if not (i > 0 and small[i - 1][1] and small[i - 1][0][-1] == small[i][0][0])]
    if not missing: return True
    if not all(small[i][1] for i in missing): return False
    runs = _initials(large)
    return all(small[i][0] in runs for i in missing)


def _main_clause(verb):
    while verb.dep_ == 'conj' and verb.head.i != verb.i:
        verb = verb.head
    return verb.dep_ == 'ROOT'


def _clause_subject(verb):
    while True:
        found = [t for t in verb.children if t.dep_ in SUBJECTS]
        if found: return found[0]
        if verb.dep_ != 'conj' or verb.head.i == verb.i: return None
        verb = verb.head


def _possible_patient(actor):
    """Whether the claim's actor may be the patient. Only a nominal possessed by
    another person ("her mother", "the patient's father") is another actor; a
    first- or second-person possessor ("our service user", "my client") is the
    clinician's own patient, and a pronoun, name, abbreviation, unpossessed noun
    or omitted subject remains unresolved and may be the patient. Nothing here
    admits an answer.
    """
    if actor is None: return True

    def another(t):
        return t.text.casefold() != 'patient' and any(
            c.dep_ == 'poss' and not (c.pos_ == 'PRON' and set(c.morph.get('Person')) & {'1', '2'})
            for c in t.children)
    return any(not another(t) for t in [actor, *actor.conjuncts])


def _conjunct_chain(token):
    """A coordinated complement shares its first conjunct's role and clause."""
    chain = [token]
    while chain[-1].dep_ == 'conj' and chain[-1].head.i != chain[-1].i:
        chain.append(chain[-1].head)
    return chain


def _negations(tokens):
    # Each token once: the same token may reach the spine by two roles.
    return sum(c.dep_ == 'neg' for t in {t.i: t for t in tokens}.values() for c in t.children)


def _elided(verb):
    """Coordinated clauses whose predicate is elided ("... but is not now")."""
    top = _conjunct_chain(verb)[-1]
    group = [top] + [t for t in top.subtree if t.dep_ == 'conj' and t.pos_ in ('AUX', 'VERB')
                     and _conjunct_chain(t)[-1].i == top.i]
    # spaCy builds a new Token object on every access: compare positions, never identity.
    return [t for t in group if t.i != verb.i and t.pos_ == 'AUX' and not any(
        c.dep_ in _PREDICATES + _INDIRECT + ('dobj',) for c in t.children)]


def _predicate_prep(token):
    """The preposition that is the predicate of a copula ("is on MAPPA", "is not at
    risk of falls") or of a telegraphic subject ("Patient not on methadone"), when
    the token names its object: the object head, a conjunct or renaming of it, or a
    noun naming it with the head ("on methadone treatment"); or with the subject
    and copula omitted ("Not on methadone.", "No longer on methadone."). Beside
    another complement of the copula it is that complement's part, as _parts reads
    it ("is tender over the knee"), not a predicate. Returns the preposition, the
    coordinated preposition heading it ("on MAPPA or on ...") and the object head,
    or three Nones."""
    t = token
    while t.dep_ in ('compound', 'nmod', 'appos', 'conj') and t.head.i != t.i:
        t = t.head
    if t.dep_ != 'pobj' or t.head.i == t.i:
        return None, None, None
    prep = top = t.head
    while top.dep_ == 'conj' and top.head.i != top.i and top.head.pos_ == 'ADP':
        top = top.head
    if top.dep_ == 'ROOT':
        return prep, top, t
    owner = top.head
    if top.dep_ != 'prep' or owner.i == top.i:
        return None, None, None
    if (owner.pos_ == 'AUX' and owner.dep_ not in ('aux', 'auxpass')
            and not any(c.dep_ in _PREDICATES for c in owner.children)
            or owner.pos_ in _NOMINAL + ('ADV',) and _conjunct_chain(owner)[-1].dep_ == 'ROOT'):
        return prep, top, t
    return None, None, None


def _occurrence(token, limit, nested=False):
    """Polarity, time and actor of one predicate occurrence, by syntax only.

    Returns None only when the occurrence is provably no claim about the
    predicate's subject: a restrictor of a plural class. A modifier of another
    noun states that noun's property at a polarity only the governing verb's
    meaning fixes, so it never agrees. A noun as an ordinary argument is marked,
    and opposes only while it carries the selected predicate's own complement. A
    label, a question or an inverted clause asserts no polarity, whatever the
    word's role.
    """
    chain = _conjunct_chain(token)
    head = chain[-1]
    governor = head.head if head.head.i != head.i else None
    verb = actor = passive = modifier = None
    uncertain = argument = extras = False
    unasserted = _label(token) or _question(token)
    spine = list(chain)
    prep, top, anchor = _predicate_prep(token)
    if prep is not None:
        # A prepositional predicate: the copula's (or telegraphic subject's)
        # polarity, read on the preposition too ("Patient not on methadone").
        spine += [prep, top]
        owner = top.head if top.head.i != top.i else None
        if owner is None:
            pass  # "Not on methadone.": subject and copula omitted
        elif owner.pos_ == 'AUX':
            verb = owner
        elif owner.pos_ == 'ADV':
            spine.append(owner)  # "No longer on methadone."
        else:
            actor = owner
    elif head.dep_ in _PREDICATES + _INDIRECT and governor is not None and governor.pos_ in ('AUX', 'VERB'):
        verb = governor
    elif head.dep_ == 'ROOT':
        actor = next((c for c in head.children if c.dep_ in SUBJECTS), None)
        if head.pos_ in ('AUX', 'VERB'):
            auxiliaries = [c for c in head.children if c.dep_ in ('aux', 'auxpass')]
            spine += auxiliaries
            # A simple passive participle predicate ("is oriented") has its copula's tense.
            if (len(auxiliaries) == 1 and auxiliaries[0].dep_ == 'auxpass'
                    and 'Fin' in auxiliaries[0].morph.get('VerbForm') and len(auxiliaries[0].morph.get('Tense')) == 1):
                passive = auxiliaries[0].morph.get('Tense')[0]
    elif head.dep_ in _MODIFIERS and governor is not None:
        noun = governor
        if head.i > noun.i:
            if _conjunct_chain(noun)[-1].dep_ == 'ROOT':
                actor = noun  # telegraphic: "Patient subject to the arrangements."
            elif noun.pos_ == 'NOUN' and 'Plur' in noun.morph.get('Number') and not unasserted:
                return None  # a restrictor of a plural class: "Patients subject to MAPPA are reviewed"
            else:
                actor, uncertain = noun, True  # it may predicate the patient, but not assert it
        elif noun.text.casefold() == 'patient':
            actor = noun  # "the suicidal patient"
        elif noun.dep_ in _PREDICATES and noun.head.i != noun.i:
            actor, uncertain = _clause_subject(noun.head), True  # "she is a suicidal risk"
        else:
            # A modifier of another noun ("suicidal ideation") states that noun's
            # property, at a polarity only the governing verb's meaning fixes
            # ("reports" or "denies"): never agreement. Its actor is the noun's
            # possessor ("her mother's suicidal ideation" is another person's).
            actor = next((c for c in noun.children if c.dep_ == 'poss'), None)
            uncertain, modifier = True, 'adjectival' if head.dep_ == 'amod' else 'nominal'
    elif head.dep_ in _ADVERBIAL and governor is not None and not nested:
        # An adverb of another predicate ("well controlled", "eating well") has that
        # predicate's polarity, at a time never proven different.
        base = _occurrence(governor, limit, nested=True)
        if base is None:
            uncertain = True
        else:
            base.update(extras=True, tense=None, argument=False, verb=None, anchor=token, skip=frozenset(),
                        prep=None, modifier=None, adverbial=True)
            base['uncertain'] = base['uncertain'] or unasserted
            return base
    elif token.pos_ in _NOMINAL and head.dep_ in _ARGUMENTS:
        argument = True
    else:
        uncertain = True
    if verb is not None:
        spine += [verb] + [c for c in verb.children if c.dep_ in ('aux', 'auxpass') + _ADVERBIAL]
    spine += [c for t in chain for c in t.children if c.dep_ in _ADVERBIAL]
    negative = _negations(spine) % 2 == 1
    # Reported, conditional-complement, infinitival or otherwise embedded
    # predicates, and either/neither coordination, are not the note's own
    # plain assertion: their polarity is never taken to agree with an answer.
    uncertain = uncertain or any(t.dep_ == 'preconj' for t in token.subtree)
    # A heading before a label separator ("Subject to MAPPA: No.") or a question
    # has its answer elsewhere, so its own syntax asserts no polarity.
    clause = verb if verb is not None else (head if head.pos_ in ('AUX', 'VERB') else governor)
    inverted = clause is not None and clause.pos_ in ('AUX', 'VERB') and any(
        c.dep_ in SUBJECTS and c.i > clause.i for c in clause.children)  # "Nor is the patient ..."
    if unasserted or inverted:
        uncertain, argument = True, False
    tense = passive
    if verb is not None:
        embedded = (head.dep_ not in _PREDICATES and prep is None) or not _main_clause(verb)
        uncertain = uncertain or embedded
        actor = _clause_subject(verb)
        auxiliaries = [c for c in verb.children if c.dep_ in ('aux', 'auxpass')]
        for elided in _elided(verb):
            extras = True
            own = [elided] + [c for c in elided.children if c.dep_ in _ADVERBIAL]
            uncertain = uncertain or (_negations(own) % 2 == 1) != negative
        value = verb.morph.get('Tense')
        # Only two simple finite main-clause verbs with explicitly different
        # tense can be two different times. Every auxiliary, aspect or modal may
        # overlap, and reported speech shifts tense ("she said she was not").
        if not embedded and not auxiliaries and 'Fin' in verb.morph.get('VerbForm') and len(value) == 1:
            tense = value[0]
    return {'negative': negative, 'uncertain': uncertain, 'tense': tense, 'extras': extras,
            'patient': _possible_patient(actor), 'argument': argument, 'verb': verb,
            'anchor': anchor if anchor is not None else token,
            'skip': frozenset(t.i for t in (prep, top) if t is not None),
            'prep': prep.text.casefold() if prep is not None else None, 'modifier': modifier, 'adverbial': False}


def _answers(doc):
    """Per parse, read once: positions of label separators and interjection answers,
    and for each token whether its sentence is a question."""
    if _ANSWERS not in doc.user_data:
        questions = set()
        for sentence in doc.sents:
            if any('?' in t.text for t in sentence): questions.update(range(sentence.start, sentence.end))
        doc.user_data[_ANSWERS] = (tuple(t.i for t in doc if _answered(t)), frozenset(questions))
    return doc.user_data[_ANSWERS]


def _label(token):
    answers = _answers(token.doc)[0]
    return bool(answers) and answers[-1] > token.i


def _limit(token):
    """The first answer position after the token: nothing from there on is topic."""
    answers = _answers(token.doc)[0]
    n = bisect.bisect_right(answers, token.i)
    return answers[n] if n < len(answers) else len(token.doc)


def _question(token):
    return token.i in _answers(token.doc)[1]


def _parts(token, verb, limit, skip=frozenset()):
    """Each prepositional complement, keyed by its preposition, whether the parser
    attaches it to the predicate or to the copula ("tender over the knee"). The
    predicate's own preposition (``skip``: "is on MAPPA") is the predicate, not a part."""
    doc = token.doc; parts = {}
    for owner in [token] + ([verb] if verb is not None else []):
        for prep in owner.children:
            if prep.dep_ != 'prep' or prep.i >= limit or prep.i in skip: continue
            part = parts.setdefault(prep.text.casefold(), {'readings': set(), 'indices': set(), 'wild': False,
                                                           'heads': set()})
            readings = {tuple(i for i in r if i != prep.i) for r in _topic_readings(prep, limit, nested=True)}
            inner = [t for t in prep.subtree if t.dep_ == 'prep' and t.i != prep.i and t.i < limit]
            # Each reading records the prepositions of the qualifiers it leaves out: one
            # the other statement also states is compared, never dropped ("of the hip").
            part['readings'] |= {(_words(doc, r), frozenset(t.text.casefold() for t in inner
                                  if t.i not in r and (t.head.i in r or t.head.i == prep.i))) for r in readings}
            part['indices'] |= set().union(*readings)
            # The object it names (an acronym renaming it is read by its spelling).
            part['heads'] |= {_singular(o.text.casefold()) for o in prep.children if o.dep_ == 'pobj' and o.i < limit}
            if len(part['readings']) > _READINGS: raise _Unbounded()
            # "allergic to any medication", "subject to no arrangements"
            part['wild'] |= any(_quantifier(t) for t in prep.subtree if t.i < limit)
    for part in parts.values():
        indices = part.pop('indices')
        part['full'] = _words(doc, indices)
        part['content'] = _words(doc, {i for i in indices if doc[i].pos_ not in _FUNCTION})
    return parts


def _bare(token, verb, anchor, skip, extras):
    """Whether a clause states nothing beyond its predicate: no elided clause, no
    adverbial anywhere in it ("today", "no longer", "when discharged"), and no
    prepositional phrase other than the predicate's own complements, so none
    nested inside them ("MAPPA as of this week") or coordinated with them ("or to
    a curfew at today's review"). Only such a past proves another time."""
    chain = _conjunct_chain(token)
    direct = {t.i for t in chain} | {anchor.i} | ({verb.i} if verb is not None else set())
    clause = list((verb if verb is not None else chain[-1]).subtree)
    return (not extras and not any(t.dep_ in _TIMED for t in clause)
            and all(t.head.i in direct or t.i in skip for t in clause if t.dep_ == 'prep' or t.pos_ == 'ADP'))


def _claim(token):
    doc = token.doc
    limit = _limit(token)
    occurrence = _occurrence(token, limit)
    if occurrence is None: return None
    verb = occurrence.pop('verb')
    anchor = occurrence.pop('anchor')  # the token, or the object head of a prepositional predicate
    skip = occurrence.pop('skip')      # the predicate's own preposition, never a part
    occurrence['bare'] = occurrence['tense'] is not None and _bare(token, verb, anchor, skip, occurrence['extras'])
    # The claim's own clause: its subtree without its coordinated heads (each is
    # its own occurrence), and the copula's other dependants, subject included.
    chain = {t.i for t in _conjunct_chain(token)}
    coordinated = {t.i for c in anchor.children if c.dep_ == 'conj' for t in c.subtree}
    scope = [t for t in anchor.subtree if t.i not in coordinated]
    if verb is not None:
        scope += [t for c in verb.children if c.dep_ != 'conj' and c.i not in chain for t in c.subtree]
    if any(_quantifier(t) or t.dep_ == 'preconj' for t in scope if t.i < limit):
        # A quantified claim's polarity is not read ("subject to no arrangements"), nor
        # a claim over a neither/either coordination ("Neither the patient nor ...").
        occurrence['uncertain'] = True
    try:
        core = {tuple(i for i in r if i != token.i) for r in _topic_readings(anchor, limit, top=True)}
        parts = _parts(anchor, verb, limit, skip)
    except _Unbounded:
        core = parts = None  # compared by its head word alone, which only withholds
    # A nominal predicate by its role, never its tag (the tagger calls "tender" a noun):
    # a noun complement ("is a smoker") or a prepositional predicate's object.
    nominal = bool(skip) or _conjunct_chain(token)[-1].dep_ == 'attr'
    claim = {'word': _surface(token), 'nominal': nominal, **occurrence}
    claim['heads'] = frozenset({claim['word'], _singular(anchor.text.casefold())}
                               | set().union(*(part['heads'] for part in (parts or {}).values())))
    if core is None:
        claim.update(core=None, core_full=(), parts={}, vocabulary=(), content=())
        return claim
    indices = set().union(*core)
    claim.update(core=[_words(doc, r) for r in core], core_full=_words(doc, indices), parts=parts)
    vocabulary = [(claim['word'], False), *claim['core_full']]
    content = [(claim['word'], False), *_words(doc, {i for i in indices if doc[i].pos_ not in _FUNCTION})]
    for key, part in parts.items():
        vocabulary += [(key, False), *part['full']]
        content += part['content']
    claim.update(vocabulary=tuple(vocabulary), content=tuple(content))
    return claim


def _covered(small, large):
    """Whether small's complete predicate is within large's: the same predicate or
    a more general one. A prepositional complement only one of them states is a
    qualifier ("at present", "per the probation officer"), never a different
    topic; the same preposition with an object that neither states is one
    ("tender over the lateral / medial epicondyle"). A quantified object ("any
    medication") is never a different topic."""
    if small['core'] is None or large['core'] is None: return True
    # The parser may attach a complement's words to the head or to its preposition
    # ("responsive enough to physiotherapy"): the core is read against it all.
    if not any(_cover(r, large['vocabulary']) for r in small['core']): return False
    for key, part in small['parts'].items():
        other = large['parts'].get(key)
        if other is None or part['wild'] or other['wild']: continue
        stated = {w for w, _ in other['full']}
        if not any(_cover(r, other['full']) and not dropped & stated for r, dropped in part['readings']):
            return False
    return True


def _different_time(a, b):
    """Two simple tenses are two times only when the past one is bare (see _bare):
    a time adverbial anywhere in it ("today ... was not", "on the ward today"), a
    nested or coordinated qualifier ("MAPPA as of this week"), a qualifier the
    present one lacks ("at today's review") or an elided clause ("but is not now")
    may place it now."""
    if a['tense'] is None or b['tense'] is None or a['tense'] == b['tense']: return False
    past, present = (a, b) if a['tense'] == 'Past' else (b, a)
    return past['tense'] == 'Past' and past['bare'] and set(past['parts']) <= set(present['parts'])


def _opposes(selected, other):
    relation = _related(selected['word'], other['word'])
    if relation is None or not (selected['patient'] and other['patient']):
        return False
    if relation == 'prefixed' and other['adverbial']:
        return False  # an adverb of another predicate ("less severe") is no form of this word
    if relation == 'same' and other['modifier'] == 'nominal' and selected['nominal']:
        return False  # a noun classifying another noun ("Smoker status") predicates nothing
    uncertain = selected['uncertain'] or other['uncertain'] or relation == 'prefixed'
    if selected['prep'] and other['prep'] and selected['prep'] != other['prep']:
        return False  # another preposition is another predicate ("off methadone")
    if other['argument']:
        # A noun used as an ordinary argument states no predicate, unless it carries
        # the selected predicate's own complement (an inverted predicate misread).
        if selected['prep'] or not set(selected['parts']) & set(other['parts']): return False
        uncertain = True
    if not uncertain and selected['negative'] == other['negative']:
        return False
    if _different_time(selected, other):
        return False
    if uncertain:
        return _covered(selected, other) or _covered(other, selected)
    negative, positive = (selected, other) if selected['negative'] else (other, selected)
    return _covered(negative, positive)


def _segments(doc, answered=False):
    """Label text before a separator or an interjection answer, with the answer
    after it; a question before its mark, with what follows it; and a whole unit
    answered by the next one ("MAPPA." then "No."), whose answer is not read here."""
    for sentence in doc.sents:
        start = sentence.start
        marks = [t.i for t in sentence if _answered(t) or '?' in t.text]
        for n, i in enumerate(marks):
            yield doc[start:i], doc[i + 1:marks[n + 1] if n + 1 < len(marks) else sentence.end]
            start = i + 1
    if answered:
        yield doc[:], None


def _value(answer):
    """A plain nonzero number ("MAPPA level: 2"): the only answer read after a label."""
    words = [t for t in answer if not (t.is_punct or t.is_space)] if answer is not None else []
    return bool(words) and all(t.text.isascii() and t.text.isdigit() for t in words) and any(
        int(t.text) for t in words)


def _names_topic(segment, answer, claim):
    """A label or question about the selected predicate: its content words, outside
    its subject, are all the predicate's own ("MAPPA: No.", "Is the patient on
    MAPPA? No."), or it names the predicate or its object with a word of its own
    ("MAPPA status: none."), whose answer only that word's meaning reads, unless
    the answer is a plain nonzero number ("MAPPA level: 2")."""
    # The subject names who is asked about; a phrase the parser hangs on it is
    # still asked ("Is the patient on MAPPA?").
    subject = {i for s in segment if s.dep_ in SUBJECTS
               for i in [s.i, *(t.i for c in s.children if c.dep_ != 'prep' for t in c.subtree)]}
    words = tuple((_singular(t.text.casefold()), len(t.text) > 1 and t.text.isalpha() and t.text.isupper())
                  for t in segment if (t.is_alpha or t.like_num) and t.pos_ not in _FUNCTION and t.i not in subject)
    if not words: return False
    if _cover(words, claim['vocabulary']): return True
    named = any(w in claim['heads'] or acronym and _cover(((w, True),), claim['vocabulary']) for w, acronym in words)
    return named and not _value(answer)


def _selected_claims(doc):
    """Every copular complement of the selected statement, read by its role."""
    claims = []
    for token in doc:
        if not _wordlike(token): continue
        head = _conjunct_chain(token)[-1]
        governor = head.head
        if ((head.dep_ in _PREDICATES and governor.i != head.i and governor.pos_ in ('AUX', 'VERB'))
                # a prepositional predicate's object, or a conjunct or renaming of it
                or (token.dep_ not in ('compound', 'nmod') and _predicate_prep(token)[0] is not None)
                or (head.dep_ == 'ROOT' and token.pos_ == 'ADJ')
                # the tagger reads "is oriented" as a passive participle, "is orientated" as acomp
                or (head.dep_ == 'ROOT' and token.pos_ == 'VERB' and any(c.dep_ == 'auxpass' for c in head.children))
                or (head.dep_ == 'amod' and head.i > governor.i and _conjunct_chain(governor)[-1].dep_ == 'ROOT')):
            claims.append(_claim(token))
    return claims


def _occurrences(doc, words):
    """Claims of the tokens naming a selected word or a prefixed form of it. Each
    token's claim depends only on its own parse, so it is read once per parse and
    shared by every field that revalidates against this source."""
    cache = doc.user_data.setdefault(_CLAIMS, {})
    if None not in cache:
        cache[None] = tuple(_surface(t) if _wordlike(t) else '' for t in doc)
    surfaces = cache[None]
    for token in doc:
        if surfaces[token.i] and any(_related(w, surfaces[token.i]) for w in words):
            if token.i not in cache:
                cache[token.i] = _claim(token)
            yield cache[token.i]


_WORD = re.compile(r'[^\W\d_]+(?:[\u002d\u2010\u2011][^\W\d_]+)*')
_SPACED_DASH = re.compile(r'[\u2012-\u2015]|(?:^|\s)[\u002d\u2010\u2011\u2212]|[\u002d\u2010\u2011\u2212](?:\s|$)')



def _fragment(doc):
    """A unit with a word or number but no clause of its own: no subject and no
    finite verb ("None.", "Not applicable.", "Denied.", "N/A.", "0."), whatever the
    tagger calls its words. After a unit, it may be that unit's answer."""
    return (any(not (t.is_punct or t.is_space) for t in doc)
            and not any(t.dep_ in SUBJECTS + ('expl', 'csubj', 'csubjpass') for t in doc)
            and not any('Fin' in t.morph.get('VerbForm') for t in doc))


def _stems(words):
    """Each word and what remains of it after a short alphabetic prefix, so that the
    'prefixed' relation of _related is a set lookup."""
    return set(words) | {w[k:] for w in words for k in range(1, _PREFIX + 1)
                         if len(w) - k >= 4 and w[:k].isalpha()}


def _summary(text):
    """The words of one unit reading, read once per reading of the source."""
    from .generation import COLONS
    found = {_singular(''.join(c for c in w if c not in _HYPHENS).casefold()) for w in _WORD.findall(text)}
    found |= {_singular(w.casefold()) for w in re.findall(r'[^\W\d_]+', text)}
    label = any(c in COLONS or c == '?' for c in text) or bool(_SPACED_DASH.search(text))
    return frozenset(found), frozenset(_stems(found)), label


def _mentions(summary, words, vocabulary):
    """A cheap pre-read: 'word' when the unit names a selected predicate word or a
    prefixed form of it, 'label' for a label or question with one of its content
    words, 'topic' for another unit with one of them, else None."""
    found, stems, label = summary
    if words & stems or _stems(words) & found: return 'word'
    if not found & vocabulary: return None
    return 'label' if label else 'topic'


def opposed_ids(selected, reading):
    """Selected units whose patient copular claim is directly opposed elsewhere.

    A model's "independent" label cannot erase a direct opposite: the same
    complete predicate (same topic, or a more general one), for the patient or an
    unresolved actor, at a time not proven different, with the opposite or an
    unasserted polarity. This applies to every selected unit whichever reader
    admitted it, and it only ever withholds. The whole source is read, in every
    compatibility reading; a unit beyond the parser's bounds, or no pinned parser
    at all, withholds the claim.
    """
    from . import generation as g
    docs = reading.setdefault('_ordinary_opposite_docs', {})
    variants = reading.setdefault('_ordinary_opposite_readings', {})
    summaries = reading.setdefault('_ordinary_opposite_words', {})

    def summary(text):
        if text not in summaries:
            summaries[text] = _summary(text)
        return summaries[text]

    def readings_of(text):
        if text not in variants:
            variants[text] = list(g.safety_readings(text))
        return variants[text]
    try:
        with syntax._lock:
            parser = syntax._parser()
            if parser is None:
                # Other readers may still admit the statement; nothing here can show
                # it unopposed, so it is withheld (as on a parser error below).
                return {unit['id'] for unit in selected}

            def parsed(texts):
                missing = [t for t in dict.fromkeys(texts) if t not in docs]
                for text, doc in zip(missing, parser.pipe(missing, batch_size=16)):
                    docs[text] = doc
                return [docs[t] for t in texts]

            held = set()
            for unit in selected:
                texts = readings_of(unit['quote'])
                if any(len(t) > syntax.MAX_CHARACTERS for t in texts):
                    held.add(unit['id']); continue  # unread, so never shown unopposed
                claims = [c for doc in parsed(texts) for c in _selected_claims(doc)]
                claims = [c for c in claims if c is not None and c['patient']]
                if not claims: continue
                words = {c['word'] for c in claims}
                vocabulary = {w for c in claims for w, _ in c['content']}
                # and each acronym the predicate's words spell ("MAPPA status: none." against
                # "subject to Multi-Agency Public Protection Arrangements")
                vocabulary |= {run for c in claims for run in _initials(c['vocabulary'])}
                units = reading['units']
                following = {u['id']: units[n + 1] for n, u in enumerate(units[:-1])}

                def answered(u):
                    # A unit followed by a fragment ("Subject to MAPPA." then "No.", "None.",
                    # "Not applicable." or "Denied.") is a prompt: its own syntax asserts no
                    # polarity. A following unit too long to read may be one as well.
                    after = following.get(u['id'])
                    if after is None or not after['quote']: return False
                    texts = readings_of(after['quote'])
                    return (any(len(t) > syntax.MAX_CHARACTERS for t in texts)
                            or any(_fragment(doc) for doc in parsed(texts)))
                others = []
                for u in units:
                    if u['id'] == unit['id']: continue
                    kinds = {_mentions(summary(text), words, vocabulary) for text in readings_of(u['quote'])}
                    if kinds & {'word', 'label'} or ('topic' in kinds and answered(u)):
                        others.append((u, readings_of(u['quote'])))
                if (len(others) > syntax.MAX_UNITS
                        or any(len(t) > syntax.MAX_CHARACTERS for _, texts in others for t in texts)):
                    held.add(unit['id']); continue
                for u, texts in others:
                    prompt = answered(u)
                    for doc in parsed(texts):
                        occurrences = [c for c in _occurrences(doc, words) if c is not None]
                        if prompt:
                            occurrences = [dict(c, uncertain=True, argument=False) for c in occurrences]
                        if (any(_opposes(claim, other) for other in occurrences for claim in claims)
                                or any(_names_topic(segment, answer, claim) for segment, answer in _segments(doc, prompt)
                                       for claim in claims)):
                            held.add(unit['id']); break
                    if unit['id'] in held: break
            return held
    except (ValueError, TypeError, RuntimeError, OSError, KeyError, AttributeError, IndexError):
        return {unit['id'] for unit in selected}


def _elicited_report(text, doc, destination, question):
    # A completed elicitation, not a future/conditional response. The entire
    # reported clause and corroborating actor are retained, never patientized.
    match = re.fullmatch(r'When (?:asked|questioned) (?P<topic>[^,;:.!?]+), (?:the )?patient '
        r'(?:said|reported|stated) [^;]+; (?P<actor>staff|the (?:clinical )?(?:supervisor|clinician|nurse|doctor)) '
        r'(?:also )?(?:confirm|confirmed|report|reported|observe|observed) [^;]+\.', text, re.I)
    if not match or not _base(doc): return False
    if not re.search(r'\b(?:response|reply|said|reported)\b', question, re.I): return False
    topic = re.search(r'\babout\s+(.+)$', match['topic'], re.I)
    if not topic: return False
    words = re.findall(r'[a-z]+', topic[1].casefold())
    if not words or not all(re.search(r'\b' + re.escape(word) + r'\b', destination, re.I) for word in words): return False
    subjects = [t for t in doc if t.dep_ in SUBJECTS]
    patient = next((t for t in subjects if t.text.casefold() == 'patient' and t.head.text.casefold() in ('said', 'reported', 'stated')), None)
    if patient is None or not _nominal(patient) or not _finite(patient.head): return False
    if any(t.pos_ not in ('NOUN', 'PROPN') or not _finite(t.head) for t in subjects): return False
    # Every additional subject is either inside that attributed report, or the
    # explicit final corroborating clause; no unbound pronoun/actor is invented.
    for subject in subjects:
        if subject is patient: continue
        if patient.head in subject.ancestors: continue
        if _word(subject) not in CLINICIANS or subject.head.text.casefold() not in ('confirm', 'confirmed', 'report', 'reported', 'observe', 'observed'): return False
    return len(subjects) >= 3


def complete_ids(field, units, reading):
    """Selected units this reader admits; raises OpposedClaim to refuse them all.

    The ordinary relation revalidation (generation, review, save, finalization)
    calls this once with every selected unit, for every field kind, before any
    admission route is consulted, and refuses the whole relation on ValueError.
    The direct-opposite hold therefore covers units admitted by every reader,
    while the separately priced and pinned relation module stays unchanged.
    """
    if opposed_ids(units, reading):
        raise OpposedClaim('A selected patient statement is directly opposed elsewhere in the source.')
    if field.get('kind') not in ('text', 'long_text'): return set()
    candidates = [u for u in units[:syntax.MAX_UNITS] if isinstance(u.get('quote'), str)
                  and 0 < len(u['quote']) <= syntax.MAX_CHARACTERS and u['quote'].endswith('.')
                  and not NONFACT.search(u['quote'])]
    if not candidates: return set()
    destination = str(field.get('context') or '') + ' ' + str(field.get('label') or '')
    try:
        with syntax._lock:
            parser = syntax._parser()
            if parser is None: return set()
            result = set()
            for u, doc in zip(candidates, parser.pipe((u['quote'] for u in candidates), batch_size=16)):
                kind = _simple_fact(doc, str(field.get('label') or ''))
                if kind and (kind != 'entity' or not _foreign_context(reading, u, parser)):
                    result.add(u['id'])
                elif _elicited_report(u['quote'], doc, destination, str(field.get('label') or '')):
                    result.add(u['id'])
            return result
    except (ValueError, TypeError, RuntimeError, OSError, KeyError):
        return set()
