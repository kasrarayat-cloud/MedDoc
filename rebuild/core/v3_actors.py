"""Who each ordinary-note sentence is about (2026-09-29; repaired the same day after the refutation round).

ONE reading, computed once per note by `generation.v3_preceding_reading`, used by the ONE neighbour rule
(`generation.v3_neighbour_causes`) that generation, the page, save and finalization all call. Syntax comes only from the
pinned parser (`v3_syntax.docs`, the same verified bytes as every other syntax allowance).
This module establishes no destination and no value, and it RELEASES NOTHING: it only says who a sentence is about, so
the neighbour rule can HOLD a sentence that is another person's, or whose actor is not uniquely the patient. Every
result it cannot establish fails closed.

(b'') A unit is ANOTHER PERSON'S when a subject anywhere in it names a person who can bear what a note records ('Her
husband takes warfarin.', 'The patient reports her husband takes warfarin.', 'Somebody at home takes warfarin.', 'Her
stepbrother takes warfarin.'), when a noun other than 'patient' possesses anything in it ('Her daughter's examination'), when
it names such a person anywhere and its subject is not the explicit patient ('Warfarin was prescribed for her
husband.'), when it has personal pronoun subjects of two genders, or when a personal pronoun in it disagrees with the
patient's gender ('45-year-old woman ... The patient says he is allergic to penicillin.'). Clinicians and staff act ON
the patient and do not make a unit another person's; naming one still makes a later pronoun not uniquely the
patient's. A person described by AGE ('A 45-year-old man presents with cough.', 'This is a 60-year-old woman here for
...') and a named person PRESENTING as the note's first person ('Mrs Jones presents with chest pain.') is the patient
being presented, not another person.

STATED RESIDUALS (none of them releases anything the positional neighbour rule holds):
  - a sentence whose subject is the EXPLICIT patient and that names another person only as an object or beneficiary
    ('The patient takes warfarin for her husband.') is not held by this reader;
  - a person noun outside the lexicon and not a kinship compound of it ('stepbrother'), and a GIVEN NAME without a
    title, read as a thing when they stand alone ('The sherpa takes warfarin.', 'Her mate takes warfarin.', 'Jane is
    subject to a CTO.'): the pinned entity recognizer was measured and cannot tell names from drugs (`v3_syntax._reader`).
    In a paragraph, the positional rule holds the sentence after such a name ('The patient lives with Jane. She is
    subject to a CTO.') and the sentence itself when another sentence stands before it;
  - a named person who does not present ('Mr Smith takes aspirin 75 mg daily.') is held as another person (an
    over-hold: the name cannot be shown to be the patient's).
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
    'nobody individual adult'
).split())
#: Indefinite persons the pinned tagger reads as pronouns ('Someone at home takes warfarin.': PRON/NN/nsubj). R1-7.
PERSON_PRONOUNS = frozenset('someone somebody anyone anybody everyone everybody nobody'.split())
#: Kinship heads a compound noun may end with ('stepbrother', 'godmother', 'boyfriend'). HOLD-ONLY (R1-8). 'son' and
#: 'uncle' are not here: 'reason', 'person', 'carbuncle' would end with them.
KINSHIP_HEADS = ('mother', 'father', 'brother', 'sister', 'daughter', 'parent', 'child', 'husband', 'wife',
                 'partner', 'friend', 'cousin', 'nephew', 'niece', 'aunt')
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
#: Nouns an AGE may describe as the patient being presented ('A 45-year-old man', 'a 30-year-old female').
AGE_NOUNS = MASCULINE | FEMININE | frozenset(('patient', 'child', 'adult', 'person', 'individual'))
PERSONAL = frozenset(('he', 'she', 'they', 'him', 'her', 'them', 'his', 'hers', 'their', 'theirs'))
NEUTER = frozenset(('it', 'its', 'this', 'that', 'these', 'those'))
CONTENT = frozenset(('NOUN', 'PROPN', 'ADJ'))
#: Dependencies whose head word is a CORE argument of the clause (repeating it is talking about the same thing).
CORE_DEPS = frozenset(('nsubj', 'nsubjpass', 'dobj', 'attr', 'acomp', 'oprd', 'appos'))
#: Longest note this reader parses (units); a longer note is unreadable here and every rule falls back (fail closed).
MAX_UNITS = 400


def _lemma(token):
    return (token.lemma_ or token.text).casefold()


def names_carer(token):
    """A clinician or member of staff (lexicon, or 'Dr'/'Prof' inside it)."""
    if token.pos_ not in ('NOUN', 'PROPN'):
        return False
    if _lemma(token) in CARE_NOUNS or token.text.casefold() in CARE_NOUNS:
        return True
    return any(child.text.casefold().rstrip('.') in CARE_TITLES for child in token.children)


def names_person(token):
    """A word that names a person who can bear what a note records: an indefinite person pronoun ('Someone'), a lexicon
    noun, a kinship compound ('stepbrother') or a noun with a title inside it ('Mrs Jones'). A clinician or member of
    staff is not one (`names_carer`)."""
    if token.pos_ == 'PRON':
        return _lemma(token) in PERSON_PRONOUNS or token.text.casefold() in PERSON_PRONOUNS
    if token.pos_ not in ('NOUN', 'PROPN') or names_carer(token):
        return False
    lemma = _lemma(token)
    if lemma in PERSON_NOUNS or token.text.casefold() in PERSON_NOUNS:
        return True
    if any(child.text.casefold().rstrip('.') in TITLES for child in token.children):
        return True
    return token.pos_ == 'NOUN' and any(lemma.endswith(head) and len(lemma) > len(head) for head in KINSHIP_HEADS)


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


def _core_lemmas(root):
    """The clause's core content words: the clause head(s), their core arguments and prepositional objects, with
    their conjuncts (lemmas, casefolded; 'patient' excluded). Used only to HOLD: a later PLAIN labelled value that
    repeats one of them may change an unlabelled answer ('The patient is suicidal.' / 'Suicidal ideation: none.')."""
    heads = [root] + [child for child in root.children if child.dep_ == 'conj' and child.pos_ in ('VERB', 'AUX')]
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


def _content(doc):
    return {_lemma(token) for token in doc if token.pos_ in ('NOUN', 'PROPN', 'ADJ', 'VERB') and not token.is_stop
            and _lemma(token) != 'patient' and token.is_alpha}


def _described_by_age(token):
    """A person noun an AGE describes ('45-year-old man': the pinned parser reads 'old' as its amod, with 'year' under
    it and a number under that)."""
    if token is None or token.pos_ not in ('NOUN', 'PROPN') or _lemma(token) not in AGE_NOUNS:
        return False
    for old in token.children:
        if old.dep_ == 'amod' and _lemma(old) == 'old':
            for year in old.children:
                if _lemma(year) in ('year', 'yr') and any(number.pos_ == 'NUM' for number in year.children):
                    return True
    return False


def _age_person(doc, root, main):
    """The person noun a unit presents by age, as the main subject of a presentation predicate ('A 45-year-old man
    presents with ...', `_presents`), the copular attribute of its root ('This is a 60-year-old woman ...', 'She is a
    60-year-old woman who ...') or the fragment root ('Pleasant 70-year-old gentleman seen for ...'); None otherwise
    ('A 45-year-old man takes warfarin.' is not a presentation). Never a possessed or appositive noun."""
    candidates = [main] if main is not None and _presents(root) else []
    candidates += [child for child in root.children if child.dep_ == 'attr']
    if main is None:
        candidates.append(root)
    for token in candidates:
        if _described_by_age(token) and not any(child.dep_ == 'poss' for child in token.children) \
                and token.dep_ != 'appos':
            return token
    return None


def _presents(root):
    """The note's presentation predicate, read structurally: 'presents/presented with|for ...', or '(was) seen for
    ...' (the same wording `AGE_PATIENT_PRESENTATION`/`EXPLICIT_PATIENT_SUBJECT` presentations use)."""
    preps = {child.text.casefold() for child in root.children if child.dep_ == 'prep'}
    if _lemma(root) == 'present' and preps & {'with', 'for'}:
        return True
    return _lemma(root) == 'see' and 'for' in preps and any(child.dep_ == 'auxpass' for child in root.children)


def read(units, groups, *, colon, parsed, subjects, explicit, ages):
    """Per unit and per paragraph actor reading. `explicit`: unit ids whose text opens with an explicit patient subject
    by the deterministic source grammar (`EXPLICIT_PATIENT_SUBJECT`, the age presentation). Returns
    {'units': {id: info}, 'resolved': {id: state}, 'docs': {id: Doc}} (`docs` only for readable units: the pinned
    parser's reading, reused by the bare-repair reader so no unit is parsed twice)."""
    from . import v3_syntax
    texts = [unit['quote'] for unit in units]
    parsed_docs = v3_syntax.docs(texts) if len(units) <= MAX_UNITS else None
    info, docs = {}, {}
    relatives = re.compile(r'(?<![^\W_])(?:' + '|'.join(sorted(PERSON_NOUNS, key=len, reverse=True))
                           + r")(?:'s|s)?(?![^\W_])", re.I)
    patient_seen = False            # a person, a personal pronoun or 'patient' was already written in the note
    for index, unit in enumerate(units):
        uid = unit['id']
        doc = parsed_docs[index] if parsed_docs is not None else None
        if doc is None or len(list(doc.sents)) == 0:
            # Unreadable: nothing is established. Another person is presumed wherever a person word appears.
            info[uid] = {'readable': False, 'kind': 'unreadable', 'other': bool(relatives.search(unit['quote'])),
                         'mentions_other': True, 'content': set(), 'core': set(), 'nominal': set(),
                         'gender': None, 'patient_gender': None,
                         'embedded': set(), 'present': False, 'subject_span': None, 'age': False}
            patient_seen = True
            continue
        docs[uid] = doc
        root = next(iter(doc.sents)).root
        # A labelled line's LABEL is its question's name ('Urine dipstick: nitrites -', 'Mother: ...'), not who it is
        # about: only the value's words are read for persons.
        value_start = parsed[uid][2] if colon.get(uid) and parsed.get(uid) else 0
        words = [token for token in doc if token.idx >= value_start]
        subjects_tok = [token for token in words if token.dep_ in ('nsubj', 'nsubjpass')]
        for token in list(subjects_tok):
            subjects_tok.extend(conj for conj in token.children if conj.dep_ == 'conj')
        main = next((token for token in root.children if token.dep_ in ('nsubj', 'nsubjpass')),
                    subjects_tok[0] if subjects_tok else None)
        possessors = [token for token in words if token.dep_ == 'poss']
        # The patient being PRESENTED is not another person: by the deterministic age grammar (`ages`), by an age
        # the parser reads on the main subject, the copular attribute or the fragment root (F2-set2), or a named
        # person presenting as the note's FIRST person ('Mrs Jones presents with chest pain.').
        presented = set()
        age_token = _age_person(doc, root, main)
        if age_token is not None:
            presented.add(age_token.i)
        if uid in ages and main is not None:
            presented.add(main.i)
        named_presentation = bool(main is not None and main.pos_ == 'PROPN' and names_person(main) and _presents(root)
                                  and not patient_seen and not colon.get(uid))
        if named_presentation:
            presented.update(token.i for token in main.subtree)
        age = uid in ages or age_token is not None
        # (b'') ANOTHER PERSON as a subject, as a possessor, or as the heading word before a colon ('Father: MI.').
        other_subject = any(names_person(token) and token.i not in presented and not (token.i == 0 and uid in ages)
                            for token in subjects_tok)
        other_possessor = any(token.pos_ in ('NOUN', 'PROPN') and _lemma(token) != 'patient' for token in possessors)
        heading = unit['quote'].split(':', 1)[0] if ':' in unit['quote'] and not colon.get(uid) else ''
        other_heading = bool(heading) and any(names_person(token) for token in doc if token.idx < len(heading))
        fragment_person = main is None and not colon.get(uid) and names_person(root) and root.i not in presented
        # Naming a person anywhere, a label included ('Mother: alive and well.'), makes a later pronoun not uniquely
        # the patient's; only the value's words can make the line itself another person's.
        mentions_other = any((names_person(token) or names_carer(token)) and token.i not in presented
                             and _lemma(token) != 'patient' for token in doc)
        bearer_named = any(names_person(token) and token.i not in presented and _lemma(token) != 'patient'
                           for token in words)
        # Personal pronoun subjects of two genders in one sentence ('She takes ibuprofen and he takes aspirin.').
        genders = {_gender(token) for token in subjects_tok if _personal(token)} - {None}
        # R1-5: personal pronouns that are not the unit's main subject ('The patient says HE is allergic ...').
        embedded = {_gender(token) for token in words if _personal(token) and token.dep_ in ('nsubj', 'nsubjpass', 'poss')
                    and (main is None or token.i != main.i)} - {None}
        own_gender = None
        if age_token is not None:
            own_gender = ('Masc' if _lemma(age_token) in MASCULINE else 'Fem' if _lemma(age_token) in FEMININE
                          else None)
        pronoun_genders = genders | embedded | ({_gender(main)} - {None} if main is not None and _personal(main) else set())
        disagrees = bool(own_gender and pronoun_genders - {own_gender})
        other = (other_subject or other_possessor or other_heading or fragment_person
                 or (bearer_named and uid not in explicit and not age) or len(genders) > 1 or disagrees)
        explicit_patient = ((uid in explicit and (main is None or age or _lemma(main) == 'patient'
                                                 and not any(child.dep_ in ('compound', 'amod', 'poss', 'appos')
                                                             for child in main.children)))
                            or age_token is not None or named_presentation)
        possessed_by = None
        if main is not None:
            owner = next((child for child in main.children if child.dep_ == 'poss'), None)
            if owner is not None:
                possessed_by = ('patient' if owner.pos_ in ('NOUN', 'PROPN') and _lemma(owner) == 'patient'
                                else 'pronoun' if _personal(owner) else 'other')
        gender = None
        if colon.get(uid):
            kind = 'labelled'
        elif explicit_patient and not other:
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
            if own_gender:
                patient_gender = own_gender
            elif age:
                lemmas = {_lemma(token) for token in doc}
                patient_gender = ('Masc' if lemmas & MASCULINE else 'Fem' if lemmas & FEMININE else None)
            else:
                found = {_gender(token) for token in possessors if _personal(token)} - {None}
                patient_gender = found.pop() if len(found) == 1 else None
        span = None
        if kind == 'pronoun' and main is not None and _personal(main):
            span = (main.idx, main.idx + len(main.text))
        info[uid] = {'readable': True, 'kind': kind, 'other': other, 'mentions_other': mentions_other,
                     'content': _content(doc), 'core': _core_lemmas(root),
                     'nominal': {_lemma(token) for token in doc if token.pos_ in CONTENT and _lemma(token) != 'patient'},
                     'gender': gender, 'patient_gender': patient_gender,
                     'embedded': embedded if kind == 'patient' else set(), 'subject_span': span, 'age': age,
                     'present': 'Pres' in root.morph.get('Tense')}
        if mentions_other or bearer_named or kind in ('patient', 'pronoun', 'other') or any(
                _personal(token) or _lemma(token) == 'patient' for token in doc):
            patient_seen = True
    resolved = {}
    # The patient's gender is the note's, not a paragraph's: once an age presentation (or the explicit patient's own
    # possessive) gives it, a pronoun or an embedded pronoun anywhere in the note that disagrees is another person's.
    note_gender, gender_cause = None, None
    for group in groups:
        current, cause, other_since, other_cause = None, None, False, None
        for unit in group:
            uid = unit['id']
            this = info[uid]
            state = {'current': current, 'cause': cause, 'other_since': other_since, 'patient_gender': note_gender}
            kind = this['kind']
            topic = (parsed.get(uid) or (None,))[0] or subjects.get(uid)
            self_other = False
            blame = None              # the unit an actor hold shows when it is not the paragraph's run cause
            if kind == 'unreadable':
                # Nothing is established: another person where a person word appears, unresolved otherwise.
                actor = 'other' if this['other'] else 'unresolved'
                current, cause, other_since, other_cause = actor, unit, True, unit
            elif kind == 'labelled':
                # A labelled line names its question; it neither continues nor CLOSES another person's run (R1-6: a
                # labelled line held as possibly that person's cannot also end the run for the lines after it). A
                # labelled VALUE naming another person as its subject opens one ('Allergies: her sister is allergic
                # to penicillin.', R3-2).
                actor = 'labelled'
                if this['other']:
                    current, cause, other_since, other_cause = 'other', unit, True, unit
                elif this['mentions_other']:
                    other_since, other_cause = True, unit
            elif kind == 'other':
                actor = 'other'
                current, cause, other_since, other_cause = 'other', unit, True, unit
            elif kind == 'patient' and this['age'] and current in ('other', 'ambiguous'):
                # An age presentation DESCRIBES a person ('45-year-old man presents ...'); after another person's run
                # it may describe that person ('Her brother was seen yesterday. 45-year-old man presents ...').
                actor = 'ambiguous'
                current = 'ambiguous'
            elif kind == 'patient':
                if this['patient_gender'] and note_gender is None:
                    note_gender, gender_cause = this['patient_gender'], unit
                if note_gender and this['embedded'] - {note_gender}:
                    # R1-5: an embedded personal pronoun that disagrees with the patient's gender is another person's
                    # ('45-year-old woman ... The patient says he is allergic to penicillin.'): the unit holds itself.
                    actor, self_other = 'other', True
                    current, cause, other_since, other_cause = 'other', unit, True, unit
                elif this['embedded'] and (current in ('other', 'ambiguous') or other_since):
                    # With the gender unknown, an embedded pronoun written after another person was named in the
                    # paragraph is not uniquely the patient's ('His father has diabetes. The patient reports that he
                    # takes metformin.').
                    actor = 'ambiguous'
                    cause = other_cause if other_cause is not None else cause
                    current = 'ambiguous'
                else:
                    actor = 'patient'
                    current, cause = 'patient', unit
                    other_since = this['mentions_other']
                    other_cause = unit if other_since else None
            elif kind == 'pronoun':
                mismatch = bool(this['gender'] and note_gender and this['gender'] != note_gender)
                if current == 'patient' and not other_since and not mismatch:
                    actor = 'patient'
                    if this['gender'] and note_gender is None:
                        note_gender, gender_cause = this['gender'], unit
                elif current == 'other':
                    actor = 'other'
                elif current in ('patient', 'ambiguous') or mismatch:
                    # Not UNIQUELY the patient: another person was named since the patient anchor, or the pronoun's
                    # gender disagrees with the patient's ('45-year-old man ... She takes warfarin.', in any paragraph).
                    actor = 'ambiguous'
                    if mismatch and current != 'ambiguous':
                        cause = gender_cause or unit
                    elif current == 'patient':
                        cause = other_cause if other_since and other_cause is not None else cause
                    current = 'ambiguous'
                    blame = cause
                else:
                    actor = 'unresolved'
                    current, cause = 'unresolved', unit
                if this['mentions_other']:
                    other_since, other_cause = True, unit
            else:
                actor = current or 'unresolved'
                if this['mentions_other']:
                    other_since, other_cause = True, unit
            resolved[uid] = {**state, 'actor': actor, 'topic': topic, 'self_other': self_other,
                             'hold_cause': blame or state['cause']}
    return {'units': info, 'resolved': resolved, 'docs': docs}
