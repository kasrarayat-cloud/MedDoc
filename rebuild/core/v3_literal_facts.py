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
