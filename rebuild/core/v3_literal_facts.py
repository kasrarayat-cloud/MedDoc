"""Bounded complete literal observations under the full ordinary relation contract.

This reader never turns an entity or clinician into the patient. Full source
subjects, negation, passive agents and reported clauses stay in the answer.
Destination meaning still requires qualification of the exact model contract.
"""
import re
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
_NO_TOPIC = ('neg', 'preconj', 'cc', 'punct')
# Copular complements by dependency role, never by part of speech: the pinned
# tagger reads "well" as an adverb in "is well" and an adjective in "is not well".
_PREDICATES = ('acomp', 'oprd', 'attr')
_INDIRECT = ('xcomp', 'ccomp', 'advcl')
# A nominal complement's noun also occurs as an ordinary argument ("The nurse
# reviewed it"); only there, and only for a noun, is an occurrence no claim. An
# adjective or verb in an unrecognised role still withholds.
_NOMINAL = ('NOUN', 'PROPN', 'PRON', 'NUM')
_ARGUMENTS = ('nsubj', 'nsubjpass', 'dobj', 'iobj', 'dative', 'pobj', 'agent')
_READINGS = 64


def _topic_word(token):
    # Articles, punctuation and negation are never topic identity; negation is
    # read as polarity from the dependency parse, not from a list of words.
    return not (token.is_punct or token.is_space or token.dep_ in _NO_TOPIC
                or 'Art' in token.morph.get('PronType'))


def _combine(left, right):
    result = {tuple(sorted(a + b)) for a in left for b in right}
    if len(result) > _READINGS: raise _Unbounded()
    return result


def _topic_readings(token, top=False):
    """Every complete reading of one predicate subtree, as source token indices.

    The whole literal subtree is always a reading. A coordinated or appositive
    nominal also states the predicate of each conjunct/renaming, and an adverbial
    qualifier may be absent; at the predicate head, material before the head may
    be absent too (tagger variance). This only widens what is the SAME topic, so
    it can withhold an answer and never grants one.
    """
    own = {(token.i,)} if _topic_word(token) else {()}
    alternates = []
    for child in sorted(token.children, key=lambda t: t.i):
        if top and child.dep_ in ('conj', 'cc'):
            continue  # a coordinated predicate head is its own occurrence
        if child.dep_ in _NO_TOPIC or child.is_punct or child.is_space:
            continue
        if child.dep_ in _ALTERNATES:
            alternates.append(_topic_readings(child))
        elif child.dep_ in _ADVERBIAL or (top and child.i < token.i):
            own = own | _combine(own, _topic_readings(child))
        else:
            own = _combine(own, _topic_readings(child))
    whole = own
    for readings in alternates:
        whole = _combine(whole, readings)
    result = own | whole
    for readings in alternates:
        result |= readings
    if len(result) > _READINGS: raise _Unbounded()
    return result


def _main_clause(verb):
    while verb.dep_ == 'conj' and verb.head is not verb:
        verb = verb.head
    return verb.dep_ == 'ROOT'


def _clause_subject(verb):
    while True:
        found = [t for t in verb.children if t.dep_ in SUBJECTS]
        if found: return found[0]
        if verb.dep_ != 'conj' or verb.head is verb: return None
        verb = verb.head


def _possible_patient(actor):
    """Whether the claim's actor may be the patient. Only a possessed nominal
    other than the patient ("her mother", "the patient's father") is another
    actor; a pronoun, name, abbreviation, unpossessed noun or omitted subject
    remains unresolved and may be the patient. Nothing here admits an answer.
    """
    if actor is None: return True
    heads = [actor, *actor.conjuncts]
    return any(t.text.casefold() == 'patient' or not any(c.dep_ == 'poss' for c in t.children)
               for t in heads)


def _conjunct_chain(token):
    """A coordinated complement shares its first conjunct's role and clause."""
    chain = [token]
    while chain[-1].dep_ == 'conj' and chain[-1].head is not chain[-1]:
        chain.append(chain[-1].head)
    return chain


def _occurrence(token):
    """The polarity, time and actor of one predicate occurrence, by syntax only."""
    chain = _conjunct_chain(token)
    head = chain[-1]
    verb = head.head if (head.dep_ in _PREDICATES + _INDIRECT and head.head is not head
                         and head.head.pos_ in ('AUX', 'VERB')) else None
    spine = list(chain)
    if verb is not None:
        spine += [verb] + [c for c in verb.children if c.dep_ in ('aux', 'auxpass', 'advmod', 'npadvmod')]
    spine += [c for t in chain for c in t.children if c.dep_ in _ADVERBIAL]
    negative = sum(c.dep_ == 'neg' for t in spine for c in t.children) % 2 == 1
    # Reported, conditional-complement, infinitival or otherwise embedded
    # predicates, and either/neither coordination, are not the note's own
    # plain assertion: their polarity is never taken to agree with an answer.
    uncertain = any(t.dep_ == 'preconj' for t in token.subtree)
    # A predicate before a label colon is a heading ("Subject to MAPPA: No."):
    # its answer follows the colon, so its own syntax asserts no polarity.
    from .generation import COLONS
    uncertain = uncertain or any(c in COLONS for t in token.doc[token.i + 1:] for c in t.text)
    tense = None
    if verb is not None:
        embedded = head.dep_ not in _PREDICATES or not _main_clause(verb)
        uncertain = uncertain or embedded
        actor = _clause_subject(verb)
        auxiliaries = [c for c in verb.children if c.dep_ in ('aux', 'auxpass')]
        value = verb.morph.get('Tense')
        # Only two simple finite main-clause verbs with explicitly different
        # tense are two different times. Every auxiliary, aspect or modal may
        # overlap, and reported speech shifts tense ("she said she was not").
        if not embedded and not auxiliaries and 'Fin' in verb.morph.get('VerbForm') and len(value) == 1:
            tense = value[0]
    elif head.dep_ == 'ROOT':
        actor = next((c for c in head.children if c.dep_ in SUBJECTS), None)
    elif head.dep_ == 'amod':
        actor = head.head
    elif token.pos_ in _NOMINAL and head.dep_ in _ARGUMENTS:
        return None  # a noun as an ordinary subject/object is no predication
    else:
        actor, uncertain = None, True
    return {'negative': negative, 'uncertain': uncertain, 'tense': tense,
            'patient': _possible_patient(actor)}


def _claim(token):
    occurrence = _occurrence(token)
    if occurrence is None: return None
    try:
        readings = {tuple(token.doc[i].text.casefold() for i in r) for r in _topic_readings(token, top=True) if r}
    except _Unbounded:
        readings = None  # compared by its head word alone, which only withholds
    return {'word': token.text.casefold(), 'readings': readings, **occurrence}


def _opposes(selected, other):
    if selected['word'] != other['word'] or not (selected['patient'] and other['patient']):
        return False
    if (selected['readings'] is not None and other['readings'] is not None
            and not selected['readings'] & other['readings']):
        return False
    if selected['tense'] is not None and other['tense'] is not None and selected['tense'] != other['tense']:
        return False
    return selected['uncertain'] or other['uncertain'] or selected['negative'] != other['negative']


def _selected_claims(doc):
    """Every copular complement of the selected statement, read by its role."""
    claims = []
    for token in doc:
        head = _conjunct_chain(token)[-1]
        if ((head.dep_ in _PREDICATES and head.head is not head and head.head.pos_ in ('AUX', 'VERB'))
                or (head.dep_ == 'ROOT' and token.pos_ == 'ADJ')):
            claims.append(_claim(token))
    return claims


def opposed_ids(selected, reading):
    """Selected units whose patient copular claim is directly opposed elsewhere.

    A model's "independent" label cannot erase a direct opposite: the same
    complete predicate (same topic), for the patient or an unresolved actor,
    at a time not proven different, with the opposite or an unasserted polarity.
    This applies to every selected unit whichever reader admitted it, and it
    only ever withholds. The whole source is read, in every compatibility
    reading; an opposing unit beyond the parser's bounds withholds the claim.
    """
    from . import generation as g
    docs = reading.setdefault('_ordinary_opposite_docs', {})
    variants = reading.setdefault('_ordinary_opposite_readings', {})

    def readings_of(text):
        if text not in variants:
            variants[text] = list(g.safety_readings(text))
        return variants[text]
    try:
        with syntax._lock:
            parser = syntax._parser()
            if parser is None: return set()

            def parsed(texts):
                missing = [t for t in dict.fromkeys(texts) if t not in docs]
                for text, doc in zip(missing, parser.pipe(missing, batch_size=16)):
                    docs[text] = doc
                return [docs[t] for t in texts]

            held = set()
            for unit in selected:
                texts = readings_of(unit['quote'])
                if any(len(t) > syntax.MAX_CHARACTERS for t in texts): continue
                claims = [c for doc in parsed(texts) for c in _selected_claims(doc)]
                claims = [c for c in claims if c is not None and c['patient']]
                if not claims: continue
                words = {c['word'] for c in claims}
                others = [(u, readings_of(u['quote'])) for u in reading['units'] if u['id'] != unit['id']]
                others = [(u, texts) for u, texts in others
                          if any(word in text.casefold() for text in texts for word in words)]
                if (len(others) > syntax.MAX_UNITS
                        or any(len(t) > syntax.MAX_CHARACTERS for _, texts in others for t in texts)):
                    held.add(unit['id']); continue
                for doc in parsed([t for _, texts in others for t in texts]):
                    occurrences = [_claim(token) for token in doc if token.text.casefold() in words]
                    if any(_opposes(claim, other) for other in occurrences if other is not None
                           for claim in claims):
                        held.add(unit['id']); break
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
