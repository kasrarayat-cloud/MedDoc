"""Who each ordinary-note sentence is about, and which later sentence can change another (2026-09-29).

ONE reading, computed once per note by `generation.v3_preceding_reading`, used by the ONE neighbour rule
(`generation.v3_neighbour_causes`) that generation, the page, save and finalization all call. Syntax comes only from the
pinned parser (`v3_syntax.docs`, the same verified bytes as every other syntax allowance). This module establishes no
destination and no value: it only says WHO a sentence is about and HOW it is linked to another, and every result it
cannot establish fails closed (the caller then keeps the positional rule it had before).

(b'') A unit is ANOTHER PERSON'S when a subject anywhere in it names a person who can bear what a note records ('Her
husband takes warfarin.', 'The patient reports her husband takes warfarin.'), when a noun other than 'patient'
possesses anything in it ('Her daughter's examination'), when it names such a person anywhere and its subject is not
the explicit patient ('Warfarin was prescribed for her husband.', 'She will follow up for the donor.'), or when it
has personal pronoun subjects of two genders. Clinicians and staff act ON the patient and do not make a unit another
person's; naming one still makes a later pronoun not uniquely the patient's. STATED RESIDUAL: a sentence whose subject
is the EXPLICIT patient and that names another person only as an object or beneficiary ('The patient takes warfarin
for her husband.') is not held by this reader.

The person lexicon below is used ONLY to HOLD. A person noun it lacks is a stated leak mode ('The sherpa takes
warfarin.' reads as a thing); every POSSESSOR that is a noun other than 'patient' is another person by structure, with
no list.
"""
import re

#: Nouns that name a person (lemma, casefolded). HOLD-ONLY: a match can make an answer held, never supported.
PERSON_NOUNS = frozenset((
    # family and household
    'mother mum mom mommy mummy father dad daddy parent stepmother stepfather stepparent sister brother sibling son '
    'daughter child kid stepson stepdaughter stepchild wife husband spouse partner fiance fiancee boyfriend girlfriend '
    'grandmother grandfather grandparent grandma grandpa granny grandson granddaughter grandchild aunt uncle cousin '
    'niece nephew twin baby infant toddler family relative relation household sibling '
    # friends, carers and other roles a note can name
    'friend neighbour neighbor flatmate roommate housemate lodger tenant landlord landlady colleague coworker employer '
    'boss manager teacher carer caregiver guardian advocate volunteer visitor donor recipient client guest sponsor '
    'interpreter translator witness companion escort driver caller informant historian proxy surrogate '
    'representative kin student pupil classmate coach trainer lawyer solicitor police policeman policewoman '
    # generic persons
    'person people man men woman women boy girl gentleman lady someone somebody anyone anybody everyone everybody '
    'individual adult'
).split())
#: Clinicians and staff: they ACT ON the patient ('Dr Smith reviewed the scan.', 'Plan: see physiotherapist twice
#: weekly.') and bear no attribute the note records, so they do not hold a unit as another person (b''); naming one
#: still makes a later pronoun not uniquely the patient's.
CARE_NOUNS = frozenset((
    'doctor physician gp surgeon anaesthetist anesthetist consultant clinician nurse midwife therapist physiotherapist '
    'physio psychiatrist psychologist pharmacist dentist optometrist paramedic practitioner registrar resident '
    'specialist cardiologist neurologist oncologist radiologist dermatologist worker keyworker coordinator officer '
    'staff team'
).split())
TITLES = frozenset(('mr', 'mrs', 'ms', 'miss', 'mx', 'sir', 'dame'))
CARE_TITLES = frozenset(('dr', 'prof'))
#: The age-presentation noun gives the patient's grammatical gender (used only to REFUSE a pronoun that disagrees).
MASCULINE = frozenset(('man', 'male', 'boy', 'gentleman', 'gent'))
FEMININE = frozenset(('woman', 'female', 'girl', 'lady'))
PERSONAL = frozenset(('he', 'she', 'they', 'him', 'her', 'them', 'his', 'hers', 'their', 'theirs'))
NEUTER = frozenset(('it', 'its', 'this', 'that', 'these', 'those'))
#: Dependencies that sit at clause level under a clause head (the root, or a verb coordinated with it).
CLAUSE_DEPS = frozenset(('neg', 'aux', 'auxpass', 'advmod', 'prt', 'acomp', 'attr', 'oprd', 'xcomp', 'cc', 'det',
                         'npadvmod'))
#: Dependencies whose head word is a CORE argument of the clause (repeating it is talking about the same thing).
CORE_DEPS = frozenset(('nsubj', 'nsubjpass', 'dobj', 'attr', 'acomp', 'oprd', 'appos'))
CONTENT = frozenset(('NOUN', 'PROPN', 'ADJ'))
#: Longest note this reader parses (units); a longer note is unreadable here and every rule falls back (fail closed).
MAX_UNITS = 400


def _lemma(token):
    return (token.lemma_ or token.text).casefold()


def names_person(token):
    """A noun that names a person who can bear what a note records (lexicon, or a title such as 'Mrs' inside it)."""
    if token.pos_ not in ('NOUN', 'PROPN'):
        return False
    if _lemma(token) in PERSON_NOUNS or token.text.casefold() in PERSON_NOUNS:
        return True
    return any(child.text.casefold().rstrip('.') in TITLES for child in token.children)


def names_carer(token):
    """A clinician or member of staff (lexicon, or 'Dr'/'Prof' inside it)."""
    if token.pos_ not in ('NOUN', 'PROPN'):
        return False
    if _lemma(token) in CARE_NOUNS or token.text.casefold() in CARE_NOUNS:
        return True
    return any(child.text.casefold().rstrip('.') in CARE_TITLES for child in token.children)


def _personal(token):
    return token.pos_ == 'PRON' and token.text.casefold() in PERSONAL


def _neuter(token):
    text = token.text.casefold()
    if text not in NEUTER:
        return False
    if text == 'that' and token.pos_ not in ('PRON', 'DET'):
        return False
    return token.pos_ in ('PRON', 'DET')


def _gender(token):
    found = token.morph.get('Gender')
    return found[0] if found and found[0] in ('Masc', 'Fem') else None


def _clause_heads(root):
    return [root] + [child for child in root.children if child.dep_ == 'conj' and child.pos_ in ('VERB', 'AUX')]


def _core_lemmas(root):
    heads = _clause_heads(root)
    core = []
    for head in heads:
        if head.pos_ in CONTENT:
            core.append(head)
        for child in head.children:
            if child.dep_ in CORE_DEPS:
                core.append(child)
            elif child.dep_ == 'prep':
                core.extend(grand for grand in child.children if grand.dep_ == 'pobj')
    for token in list(core):
        core.extend(conj for conj in token.children if conj.dep_ == 'conj')
    return {_lemma(token) for token in core if token.pos_ in CONTENT and _lemma(token) != 'patient'}


def _marks(doc, root, unsettled, denial):
    """UNSETTLED or DENIAL words at clause level (G-C, 2026-09-29): the clause head itself, or a word attached to it at
    clause level. Not inside a noun's modifiers ('possible stable angina'), a preposition's object ('subject to'), a
    word-internal prefix ('nonsmoker'), a person noun ('father': that is an ACTOR, read by `read`), or a measured time
    phrase ('two months ago', 'last month': the phrase's head has a number or noun of measure under it)."""
    heads = {token.i for token in _clause_heads(root)}
    found = []
    for token in doc:
        text = token.text
        if token.dep_ == 'neg' and token.head.i in heads:
            found.append(text)                  # 'not', "n't", 'never' as the clause's own negation
            continue
        if not (unsettled.fullmatch(text) or denial.fullmatch(text)):
            continue
        if token.text.casefold().startswith(('non', 'un')) and token.text.casefold() not in (
                'non', 'unless', 'until', 'unknown', 'unclear', 'unsure', 'uncertain', 'unconfirmed', 'unverified',
                'unable', 'unsigned'):
            continue
        if _lemma(token) in PERSON_NOUNS or token.text.casefold() in PERSON_NOUNS:
            continue
        if token.i in heads:
            found.append(text)
            continue
        if token.head.i in heads and token.dep_ in CLAUSE_DEPS:
            if token.dep_ == 'det' and token.head.pos_ not in ('NOUN', 'PROPN'):
                continue
            if token.dep_ == 'npadvmod' or any(child.dep_ in ('npadvmod', 'nummod', 'amod') for child in token.children):
                continue                        # a measured time phrase: 'yesterday', 'two months ago', 'last month'
            found.append(text)
    return found


def _content(doc):
    return {_lemma(token) for token in doc if token.pos_ in ('NOUN', 'PROPN', 'ADJ', 'VERB') and not token.is_stop
            and _lemma(token) != 'patient' and token.is_alpha}


def read(units, groups, *, colon, parsed, subjects, explicit, ages, encounter, unsettled, denial):
    """Per unit and per paragraph actor reading. `explicit`: unit ids whose text opens with an explicit patient subject
    by the deterministic source grammar (`EXPLICIT_PATIENT_SUBJECT`, the age presentation). `encounter`: labels owned
    by the encounter, not by a person (G-J). Returns {'units': {id: info}, 'resolved': {id: state}}."""
    from . import v3_syntax
    texts = [unit['quote'] for unit in units]
    parsed_docs = v3_syntax.docs(texts) if len(units) <= MAX_UNITS else None
    info = {}
    relatives = re.compile(r'(?<![^\W_])(?:' + '|'.join(sorted(PERSON_NOUNS, key=len, reverse=True))
                           + r")(?:'s|s)?(?![^\W_])", re.I)
    for index, unit in enumerate(units):
        uid = unit['id']
        doc = parsed_docs[index] if parsed_docs is not None else None
        if doc is None or len(list(doc.sents)) == 0:
            # Unreadable: nothing is established. Another person is presumed wherever a person word appears.
            info[uid] = {'readable': False, 'kind': 'unreadable', 'other': bool(relatives.search(unit['quote'])),
                         'regex_person': bool(relatives.search(unit['quote'])),
                         'mentions_other': True, 'neuter': True, 'denial': True, 'has_subject': False,
                         'connective': True, 'marks': ['unreadable'], 'core': set(), 'content': set(),
                         'anaphoric': True, 'nominal': set(),
                         'gender': None, 'patient_gender': None, 'present': False, 'subject_span': None}
            continue
        root = next(iter(doc.sents)).root
        subjects_tok = [token for token in doc if token.dep_ in ('nsubj', 'nsubjpass')]
        for token in list(subjects_tok):
            subjects_tok.extend(conj for conj in token.children if conj.dep_ == 'conj')
        main = next((token for token in root.children if token.dep_ in ('nsubj', 'nsubjpass')),
                    subjects_tok[0] if subjects_tok else None)
        possessors = [token for token in doc if token.dep_ == 'poss']
        age = uid in ages
        # (b'') ANOTHER PERSON as a subject, as a possessor, or as the heading word before a colon ('Father: MI.').
        other_subject = any(names_person(token) and not (age and main is not None and token.i == main.i)
                            and not (token.i == 0 and age) for token in subjects_tok)
        other_possessor = any(token.pos_ in ('NOUN', 'PROPN') and _lemma(token) != 'patient' for token in possessors)
        heading = unit['quote'].split(':', 1)[0] if ':' in unit['quote'] and not colon.get(uid) else ''
        other_heading = bool(heading) and any(names_person(token) for token in doc
                                              if token.idx < len(heading))
        fragment_person = main is None and not colon.get(uid) and names_person(root) and not age
        mentions_other = any(names_person(token) or names_carer(token) for token in doc
                             if not (age and main is not None and token.i == main.i) and _lemma(token) != 'patient')
        bearer_named = any(names_person(token) for token in doc
                           if not (age and main is not None and token.i == main.i) and _lemma(token) != 'patient')
        # Personal pronoun subjects of two genders in one sentence ('She takes ibuprofen and he takes aspirin.').
        genders = {_gender(token) for token in subjects_tok if _personal(token)} - {None}
        other = (other_subject or other_possessor or other_heading or fragment_person
                 or (bearer_named and uid not in explicit) or len(genders) > 1)
        explicit_patient = uid in explicit and (main is None or age or _lemma(main) == 'patient'
                                                 and not any(child.dep_ in ('compound', 'amod', 'poss', 'appos')
                                                             for child in main.children))
        possessed_by = None
        if main is not None:
            owner = next((child for child in main.children if child.dep_ == 'poss'), None)
            if owner is not None:
                possessed_by = ('patient' if owner.pos_ in ('NOUN', 'PROPN') and _lemma(owner) == 'patient'
                                else 'pronoun' if _personal(owner) else 'other')
        neuter = any(_neuter(token) for token in doc if not (age and token.i == 0))
        gender = None
        if colon.get(uid):
            kind = 'labelled'
        elif explicit_patient:
            kind = 'patient'
        elif other:
            kind = 'other'
        elif main is not None and _personal(main):
            kind, gender = 'pronoun', _gender(main)
        elif possessed_by == 'pronoun':
            kind = 'pronoun'
            gender = _gender(next(child for child in main.children if child.dep_ == 'poss'))
        elif possessed_by == 'patient':
            kind = 'patient'
        elif parsed.get(uid) or subjects.get(uid):
            kind = 'label_is'
        elif main is not None or any(token.dep_ == 'expl' for token in doc):
            kind = 'thing'
        else:
            kind = 'missing'
        patient_gender = None
        if kind == 'patient':
            if age:
                words = {_lemma(token) for token in doc}
                patient_gender = ('Masc' if words & MASCULINE else 'Fem' if words & FEMININE else None)
            else:
                genders = {_gender(token) for token in possessors if _personal(token)} - {None}
                patient_gender = genders.pop() if len(genders) == 1 else None
        first = next((token for token in doc if not token.is_punct and not token.is_space), None)
        connective = bool(first is not None and (first.pos_ in ('CCONJ', 'SCONJ') or (
            first.pos_ == 'ADV' and first.head.i == root.i and first.dep_ in ('advmod', 'cc', 'mark'))))
        # A definite or possessed THING as the subject ('The dose was reduced.', 'Her mood is low.') refers back to
        # something already said: as a LATER unit it is linked to what came before it (read by `v3_linked`).
        anaphoric = bool(main is not None and main.pos_ in ('NOUN', 'PROPN') and not names_person(main)
                         and not names_carer(main) and _lemma(main) != 'patient'
                         and any((child.dep_ == 'det' and child.text.casefold() == 'the') or child.dep_ == 'poss'
                                 for child in main.children))
        span = None
        if kind == 'pronoun' and main is not None and _personal(main):
            span = (main.idx, main.idx + len(main.text))
        info[uid] = {'readable': True, 'kind': kind, 'other': other, 'mentions_other': mentions_other,
                     'neuter': neuter, 'denial': any(denial.search(token.text) or token.dep_ == 'neg'
                                                     or 'Neg' in token.morph.get('Polarity') for token in doc),
                     'has_subject': bool(subjects_tok) or any(token.dep_ == 'expl' for token in doc),
                     'connective': connective, 'marks': _marks(doc, root, unsettled, denial),
                     'core': _core_lemmas(root), 'content': _content(doc), 'gender': gender,
                     'nominal': {_lemma(token) for token in doc if token.pos_ in CONTENT and _lemma(token) != 'patient'},
                     'patient_gender': patient_gender, 'subject_span': span, 'anaphoric': anaphoric,
                     'present': 'Pres' in root.morph.get('Tense')}
    resolved = {}
    for group in groups:
        current, cause, patient_gender, other_since, run_open = None, None, None, False, False
        other_cause, anchored = None, False
        for unit in group:
            uid = unit['id']
            this = info[uid]
            state = {'current': current, 'cause': cause, 'run_open': run_open, 'other_since': other_since,
                     'patient_gender': patient_gender, 'anchored': anchored}
            kind = this['kind']
            topic = (parsed.get(uid) or (None,))[0] or subjects.get(uid)
            if kind == 'unreadable':
                # Nothing is established: another person where a person word appears, unresolved otherwise.
                actor = 'other' if this['regex_person'] else 'unresolved'
                current, cause, run_open, other_since = actor, unit, actor == 'other', True
            elif kind == 'labelled':
                actor = 'labelled'
                run_open = False
            elif kind == 'other':
                actor = 'other'
                current, cause, run_open, other_since, other_cause = 'other', unit, True, True, unit
            elif kind == 'patient' and uid in ages and current in ('other', 'ambiguous'):
                # An age presentation DESCRIBES a person ('45-year-old man presents ...'); after another person's run
                # it may describe that person ('Her brother was seen yesterday. 45-year-old man presents ...').
                actor = 'ambiguous'
                current, run_open = 'ambiguous', True
            elif kind == 'patient':
                actor = 'patient'
                anchored = True
                current, cause, run_open = 'patient', unit, False
                other_since = this['mentions_other']
                other_cause = unit if other_since else None
                if this['patient_gender']:
                    patient_gender = this['patient_gender']
            elif kind == 'pronoun':
                mismatch = bool(this['gender'] and patient_gender and this['gender'] != patient_gender)
                if current == 'patient' and not other_since and not mismatch:
                    actor = 'patient'
                    patient_gender = patient_gender or this['gender']
                    run_open = False
                elif current == 'other':
                    actor = 'other'
                    run_open = True
                elif current in ('patient', 'ambiguous'):
                    # Not UNIQUELY the patient: another person was named since the patient anchor, or the pronoun's
                    # gender disagrees with the patient's ('45-year-old man ... She takes warfarin.').
                    actor = 'ambiguous'
                    if current == 'patient':
                        cause = other_cause if other_since and other_cause is not None else cause
                    current, run_open = 'ambiguous', True
                else:
                    actor = 'unresolved'
                    current, cause, run_open = 'unresolved', unit, True
                if this['mentions_other']:
                    other_since, other_cause = True, unit
            elif (kind == 'label_is' and topic in encounter and not run_open
                  and (current == 'patient' or (current == 'other' and anchored))):
                # G-J (engineering baseline 2026-09-29): an encounter topic after a CLOSED other-person run is the
                # encounter's, when the paragraph established the patient's encounter before that run. Directly
                # continuing the run (C4 'Her sister was seen ... Assessment is ...'), or in a paragraph that opens
                # with another person ('Her sister was seen ...\nAllergies: ...\nPlan is chemotherapy.'), it is not.
                actor = 'encounter'
                run_open = False
            else:
                actor = current or 'unresolved'
                run_open = actor == 'other'
                if this['mentions_other']:
                    other_since, other_cause = True, unit
            resolved[uid] = {**state, 'actor': actor, 'topic': topic}
    return {'units': info, 'resolved': resolved}
