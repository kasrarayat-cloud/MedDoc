"""Who each ordinary-note sentence is about (2026-09-29; round 3: TIGHTENING ONLY).

ONE reading, computed once per note by `generation.v3_preceding_reading` and read by `generation.v3_added_causes`, the
hold-only additions that the page, save, finalization and (through `judged_context`) generation all apply on top of the
positional rules of debaefd9, which are unchanged. Syntax comes only from the pinned parser (`v3_syntax.docs`). This
module establishes no destination and no value and RELEASES NOTHING: it only says who a sentence may be about, so a
sentence can be HELD. Whatever it cannot read fails closed (RR4-1): in a note of more units than `MAX_UNITS` every
unit is held; a single line longer than the parser reads is held when a word in it may name a person.

(b'') A unit is ANOTHER PERSON'S when:
  - a subject anywhere in it names a person ('Her husband takes warfarin.', 'The patient reports her husband takes
    warfarin.', 'Somebody at home takes warfarin.', 'Her stepdad takes warfarin.', 'Another patient takes warfarin.');
  - a noun other than this patient possesses anything in it ('Her daughter's examination');
  - it names such a person anywhere and its subject is not the explicit patient ('Warfarin was prescribed for her
    husband.');
  - a clinician is the subject of a medication, allergy or history statement ('Dr Smith takes warfarin.', 'The nurse is
    allergic to latex.', RR8; a clinician ACTING on the patient, 'Dr Smith reviewed the scan.', is not);
  - a relative clause gives another person something ('... presents with his mother, who has chest pain.'), or an
    appositive names a relative ('A 70-year-old woman, the patient's mother, ...', RR9);
  - it has personal pronoun subjects of two genders, or any personal pronoun in it (subject, possessive or object)
    disagrees with the patient's gender (RR6, R1-5).

ONE RUN FOR THE WHOLE NOTE (round 3: RR5, X1, RR4-8). A blank line or a paragraph proves nothing about who the next
sentence is about ('His father had a heart attack at 55.' / blank line / 'He takes rosuvastatin.' was adopted), so the
run no longer resets there: only the explicit patient ends another person's run. A pronoun or an encounter topic whose
nearest person anywhere earlier in the note is not uniquely the patient is ambiguous, and so is one with no antecedent
at all when another person was named anywhere earlier in the note.

THE PATIENT'S GENDER IS THE NOTE'S (RR6, X2): read from every cue in the note BEFORE any unit is resolved - an age
presentation, a copular noun or adjective of the explicit patient ('The patient is a woman.', '... is female.'), a
title on a sentence's main subject ('Mrs Jones presents ...') or the explicit patient's own possessive. Cues of both
genders make every gendered pronoun disagree. Gender is used only to HOLD.

WITHDRAWN in round 3: the age and titled-name presentation release (F2-set2). A person described by age or by a titled
name is read like any other person unless the deterministic age grammar (`AGE_PATIENT_PRESENTATION`) opens the unit, as
on 0350b4ea: 'A 45-year-old man presents with cough.' and 'Mrs Jones presents with chest pain.' are HELD (an over-hold;
debaefd9 supported them only because it had no actor reader at all).

STATED RESIDUALS (none of them releases anything): a sentence whose subject is the EXPLICIT patient and that names
another person only as an object or beneficiary ('The patient takes warfarin for her husband.') is not held by this
reader; a person noun outside the lexicon and a given name without a title read as things when they stand alone ('The
sherpa takes warfarin.', 'Jane is subject to a CTO.').
"""
import re
import unicodedata

#: Nouns that name a person (casefolded, accents removed). HOLD-ONLY: a match can make an answer held, never supported.
PERSON_NOUNS = frozenset((
    # family and household (RR7: mum, dad, nan, grandad, hubby, fiance(e) and the step-/god- compounds by name)
    'mother mum mom mommy mummy mama mamma father dad daddy papa parent stepmother stepfather stepparent stepmum stepmom '
    'stepdad sister brother sibling son daughter child kid stepson stepdaughter stepchild wife husband hubby spouse '
    'partner fiance fiancee boyfriend girlfriend grandmother grandfather grandparent grandma grandpa granny gran grandad '
    'granddad grandmum grandmom nan nana nanna nanny grandson granddaughter grandchild godmother godfather godparent '
    'godson goddaughter godchild aunt auntie aunty uncle cousin niece nephew twin baby infant toddler family relative '
    'relation household missus '
    # friends, carers and other roles a note can name
    'friend mate bestie neighbour neighbor flatmate roommate housemate lodger tenant landlord landlady colleague coworker '
    'employer boss manager teacher carer caregiver guardian advocate volunteer visitor donor recipient client guest '
    'sponsor interpreter translator witness companion escort driver caller informant historian proxy surrogate '
    'representative kin student pupil classmate coach trainer lawyer solicitor police policeman policewoman '
    # generic persons
    'person people man men woman women boy girl gentleman lady someone somebody anyone anybody everyone everybody '
    'nobody individual adult'
).split())
#: The family words among them: an APPOSITIVE naming one says who the person is (RR9).
FAMILY_NOUNS = frozenset((
    'mother mum mom mommy mummy mama mamma father dad daddy papa parent stepmother stepfather stepparent stepmum stepmom '
    'stepdad sister brother sibling son daughter child kid stepson stepdaughter stepchild wife husband hubby spouse '
    'partner fiance fiancee boyfriend girlfriend grandmother grandfather grandparent grandma grandpa granny gran grandad '
    'granddad grandmum grandmom nan nana nanna grandson granddaughter grandchild godmother godfather godparent godson '
    'goddaughter godchild aunt auntie aunty uncle cousin niece nephew twin family relative relation missus'
).split())
#: Indefinite persons the pinned tagger reads as pronouns ('Someone at home takes warfarin.': PRON/NN/nsubj). R1-7.
PERSON_PRONOUNS = frozenset('someone somebody anyone anybody everyone everybody nobody'.split())
#: Kinship compounds: a head a compound may END with ('stepbrother', 'godmother', 'boyfriend'; not 'son', 'uncle',
#: 'mum' or 'dad': 'reason', 'carbuncle', 'minimum' end with them) ...
KINSHIP_HEADS = ('mother', 'father', 'brother', 'sister', 'daughter', 'parent', 'child', 'husband', 'wife',
                 'partner', 'friend', 'cousin', 'nephew', 'niece', 'aunt')
#: ... or a kinship PREFIX before any family word ('stepdad', 'granddad', 'godson', 'great-grandson', RR7).
KINSHIP_PREFIXES = ('great', 'grand', 'step', 'god', 'half', 'foster', 'ex')
#: 'Another patient', 'the other patient', 'the previous patient': a patient who is not this one (X3).
OTHER_PATIENT_WORDS = frozenset('another other different next previous prior last second new former'.split())
#: Clinicians and staff ACT ON the patient ('Dr Smith reviewed the scan.', 'Plan: see physiotherapist twice weekly.'),
#: so naming one does not by itself make a unit another person's; naming one still makes a later pronoun or encounter
#: topic not uniquely the patient's, and one as the subject of a BEARER verb is another person (RR8).
CARE_NOUNS = frozenset((
    'doctor physician gp surgeon anaesthetist anesthetist consultant clinician nurse midwife therapist physiotherapist '
    'physio psychiatrist psychologist pharmacist dentist optometrist paramedic practitioner registrar resident '
    'specialist cardiologist neurologist oncologist radiologist dermatologist worker keyworker coordinator officer '
    'staff team'
).split())
#: Verbs whose subject BEARS what a note records (RR8: 'The GP is on warfarin.', 'The consultant has asthma.'). HOLD-ONLY.
BEARER_VERBS = frozenset('be have take use smoke drink vape suffer develop experience feel complain inject inhale'.split())
TITLES = frozenset(('mr', 'mrs', 'ms', 'miss', 'mx', 'sir', 'dame'))
TITLE_GENDER = {'mr': 'Masc', 'sir': 'Masc', 'mrs': 'Fem', 'ms': 'Fem', 'miss': 'Fem', 'dame': 'Fem'}
CARE_TITLES = frozenset(('dr', 'prof'))
#: The patient's grammatical gender (used only to REFUSE a pronoun that disagrees).
MASCULINE = frozenset(('man', 'male', 'boy', 'gentleman', 'gent'))
FEMININE = frozenset(('woman', 'female', 'girl', 'lady'))
PERSONAL = frozenset(('he', 'she', 'they', 'him', 'her', 'them', 'his', 'hers', 'their', 'theirs', 'himself', 'herself'))
#: Words that stand for something said before ('It was postponed.', 'However, this was before the fall.').
NEUTER = frozenset(('it', 'its', 'this', 'that', 'these', 'those'))
CONTENT = frozenset(('NOUN', 'PROPN', 'ADJ'))
#: Dependencies whose head word is a CORE argument of the clause (repeating it is talking about the same thing).
CORE_DEPS = frozenset(('nsubj', 'nsubjpass', 'dobj', 'attr', 'acomp', 'oprd', 'appos'))
#: Subordinating words by which a clause BOUNDS or CONDITIONS the statement it is attached to ('... when the bleeding
#: stops.', '... until the order expired.', '... unless the order lapses.'): such a statement is not proven current
#: (PRE-3, RR2). HOLD-ONLY: a clause missing here leaves debaefd9's reading.
BOUNDING_MARKERS = frozenset('when whenever once until till unless if before after'.split())
#: Longest note this reader parses (units). A longer note is UNREAD: every unit in it is held (fail closed, RR4-1).
MAX_UNITS = 400
#: Word endings removed to compare two words by their stem ('smoker'/'smoking'/'smokes', 'allergic'/'allergies',
#: 'suicidal'/'suicide'). Used only to HOLD (a shared word may add a hold, never release one).
STEM_SUFFIXES = tuple(sorted(('ations', 'ation', 'itions', 'ition', 'ions', 'ion', 'ings', 'ing', 'ities', 'ity',
                              'ically', 'ical', 'ics', 'ic', 'ies', 'ied', 'ers', 'er', 'ors', 'or', 'ally', 'al', 'ly',
                              'ed', 'es', 's', 'y', 'e', 'ive', 'ous', 'ness', 'ment', 'ments'), key=len, reverse=True))


def _fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text)) if not unicodedata.combining(c)).casefold()


def _lemma(token):
    return _fold(token.lemma_ or token.text)


def stem(word):
    """A word's comparison stem (see `STEM_SUFFIXES`); 'non' is removed first ('nonsmoker' / 'smoker')."""
    word = _fold(word).replace('-', '')
    if word.startswith('non') and len(word) >= 7:
        word = word[3:]
    for suffix in STEM_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            word = word[:-len(suffix)]
            break
    return word


#: Words of time and frequency name no topic ('for three weeks' / 'review in six weeks' / 'twice weekly'): they are not
#: comparison keys, so they add no hold. A missing word here only adds a hold.
GENERIC_WORDS = frozenset((
    'day days daily week weeks weekly month months monthly year years yearly annual annually hour hours hourly minute '
    'minutes time times night nights nightly morning mornings evening evenings afternoon today tonight tomorrow '
    'yesterday now twice once ago period duration recent recently'
).split())

def keys(lemmas):
    """Comparison keys of a set of lemmas: each alphabetic lemma of three letters or more, and its stem, except words
    of time and frequency (`GENERIC_WORDS`)."""
    words = {lemma for lemma in lemmas if len(lemma) >= 3 and lemma.replace('-', '').isalpha()
             and lemma not in GENERIC_WORDS}
    found = frozenset(words) | frozenset(stem(lemma) for lemma in words)
    return frozenset(key for key in found if key not in GENERIC_WORDS and key not in _GENERIC_STEMS)


_GENERIC_STEMS = frozenset(stem(word) for word in GENERIC_WORDS)


def other_patient(token):
    """'Another patient', 'the other patient', 'the previous patient' (X3): a patient who is not this note's."""
    return (token.pos_ in ('NOUN', 'PROPN') and _lemma(token) == 'patient'
            and any(child.dep_ in ('det', 'amod', 'compound', 'nummod') and _fold(child.text) in OTHER_PATIENT_WORDS
                    for child in token.children))


def this_patient(token):
    return _lemma(token) == 'patient' and not other_patient(token)


def _kin_compound(word):
    word = word.replace('-', '')
    if any(word.endswith(head) and len(word) > len(head) for head in KINSHIP_HEADS):
        return True
    rest = word
    while True:
        prefix = next((p for p in KINSHIP_PREFIXES if rest.startswith(p) and len(rest) > len(p)), None)
        if prefix is None:
            return False
        rest = rest[len(prefix):]
        if rest in FAMILY_NOUNS:
            return True


def names_carer(token):
    """A clinician or member of staff (lexicon, or 'Dr'/'Prof' inside it)."""
    if token.pos_ not in ('NOUN', 'PROPN'):
        return False
    if _lemma(token) in CARE_NOUNS or _fold(token.text) in CARE_NOUNS:
        return True
    return any(_fold(child.text).rstrip('.') in CARE_TITLES for child in token.children)


def names_person(token):
    """A word that names a person who can bear what a note records: an indefinite person pronoun ('Someone'), a lexicon
    noun, a kinship compound ('stepbrother', 'stepdad'), another patient, or a noun with a title inside it ('Mrs
    Jones'). A clinician or member of staff is not one here (`names_carer`, `_carer_bears`)."""
    if token.pos_ == 'PRON':
        return _lemma(token) in PERSON_PRONOUNS or _fold(token.text) in PERSON_PRONOUNS
    if token.pos_ not in ('NOUN', 'PROPN'):
        return False
    if other_patient(token):
        return True
    if names_carer(token):
        return False
    lemma, text = _lemma(token), _fold(token.text)
    if lemma in PERSON_NOUNS or text in PERSON_NOUNS:
        return True
    if any(_fold(child.text).rstrip('.') in TITLES for child in token.children):
        return True
    return _kin_compound(lemma) or _kin_compound(text)


def _family(token):
    lemma, text = _lemma(token), _fold(token.text)
    return lemma in FAMILY_NOUNS or text in FAMILY_NOUNS or _kin_compound(lemma) or _kin_compound(text)


def _carer_bears(token):
    """A clinician as the subject of a bearer verb ('The nurse is allergic to latex.', RR8)."""
    if not names_carer(token) or token.dep_ not in ('nsubj', 'nsubjpass', 'conj'):
        return False
    head = token.head
    while head.pos_ in ('NOUN', 'PROPN', 'PRON') and head.i != head.head.i:   # 'The GP and the nurse are ...'
        head = head.head
    return _lemma(head) in BEARER_VERBS


def _personal(token):
    return token.pos_ == 'PRON' and _fold(token.text) in PERSONAL


def _gender(token):
    found = token.morph.get('Gender')
    return found[0] if found and found[0] in ('Masc', 'Fem') else None


def _noun_gender(token):
    lemma = _lemma(token)
    return 'Masc' if lemma in MASCULINE else 'Fem' if lemma in FEMININE else None


def _described_by_age(token):
    """A person noun an AGE describes ('45-year-old man': the pinned parser reads 'old' as its amod, with 'year' under
    it and a number under that). Read here ONLY as a gender cue."""
    if token is None or token.pos_ not in ('NOUN', 'PROPN'):
        return False
    for old in token.children:
        if old.dep_ == 'amod' and _lemma(old) == 'old':
            for year in old.children:
                if _lemma(year) in ('year', 'yr') and any(number.pos_ == 'NUM' for number in year.children):
                    return True
    return False


def _core_lemmas(root):
    """The clause's core content words: the clause head(s), their core arguments and prepositional objects, with
    their conjuncts (lemmas; 'patient' excluded). Used only to HOLD."""
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


def _past(root):
    """A clause head in a past or perfect form by the parser's morphology ('was seen', 'had', 'attended')."""
    tokens = [root] + [child for child in root.children if child.dep_ in ('aux', 'auxpass')]
    return any(token.pos_ in ('VERB', 'AUX') and 'Past' in token.morph.get('Tense') for token in tokens)


#: Any word that may name who a line is about, read WITHOUT the parser (an unread line in a readable note, RR4-1).
_PERSON_WORDS = re.compile(r'(?<![^\W_])(?:' + '|'.join(sorted(PERSON_NOUNS | CARE_NOUNS | PERSONAL | TITLES | CARE_TITLES,
                                                              key=len, reverse=True))
                           + r"|(?:great|grand|step|god|half|foster)[^\W\d_]+)(?:'s|s)?(?![^\W_])", re.I)


def _unread(note_unread=True, quote=''):
    """An unread unit. In an unread NOTE (more units than `MAX_UNITS`, or no verified parser) it holds whatever it
    says (fail closed, RR4-1). A single line the parser does not read (over `v3_syntax.MAX_CHARACTERS` or
    `MAX_TOKENS`) in a readable note holds when a word in it may name a person ('person_word'); otherwise the run reads
    it as a thing and debaefd9's rules judge it."""
    person = note_unread or bool(_PERSON_WORDS.search(_fold(quote)))
    return {'readable': False, 'kind': 'unreadable' if person else 'unread_thing', 'hold': person,
            'other': person, 'mentions_other': person, 'content': frozenset(),
            'core': frozenset(), 'nominal': frozenset(), 'keys': frozenset(), 'core_keys': frozenset(),
            'gender': None, 'pronoun_genders': frozenset(), 'embedded': frozenset(), 'cues': frozenset(),
            'past': True, 'bounded': (0,), 'age': False, 'standalone': False, 'patient_past': True}


def read(units, groups, *, colon, parsed, subjects, explicit, ages):
    """Per-unit and note-wide actor reading. `explicit`: unit ids whose text opens with an explicit patient subject by
    the deterministic source grammar (`EXPLICIT_PATIENT_SUBJECT`, the age presentation `ages`). `groups` (paragraphs)
    is accepted for the caller's signature and NOT used: the run is the note's. Returns {'units': {id: info},
    'resolved': {id: state}, 'gender': the note's patient gender (None, 'Masc', 'Fem' or 'conflict')}."""
    from . import v3_syntax
    texts = [unit['quote'] for unit in units]
    parsed_docs = v3_syntax.docs(texts) if len(units) <= MAX_UNITS else None
    info = {}
    for index, unit in enumerate(units):
        uid = unit['id']
        doc = parsed_docs[index] if parsed_docs is not None else None
        if doc is None or len(list(doc.sents)) == 0:
            info[uid] = _unread(parsed_docs is None, unit['quote'])
            continue
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
        # Only the deterministic age grammar presents the patient (F2-set2's parser-read release is withdrawn).
        age = uid in ages
        presented = {main.i} if age and main is not None else set()
        other_subject = any(names_person(token) and token.i not in presented and not (token.i == 0 and age)
                            for token in subjects_tok)
        other_possessor = any(token.pos_ in ('NOUN', 'PROPN') and not this_patient(token) for token in possessors)
        heading = unit['quote'].split(':', 1)[0] if ':' in unit['quote'] and not colon.get(uid) else ''
        other_heading = bool(heading) and any(names_person(token) for token in doc if token.idx < len(heading))
        fragment_person = main is None and not colon.get(uid) and names_person(root) and root.i not in presented
        mentions_other = any((names_person(token) or names_carer(token)) and token.i not in presented
                             and not this_patient(token) for token in doc)
        bearer_named = any(names_person(token) and token.i not in presented and not this_patient(token)
                           for token in words)
        carer_bearer = any(_carer_bears(token) for token in subjects_tok)                               # RR8
        relative_clause = any(names_person(token) and token.i not in presented and not this_patient(token)
                              and any(child.dep_ in ('relcl', 'acl') for child in token.children)
                              for token in words)                                                      # RR9
        appositive_relative = any(token.dep_ == 'appos' and names_person(token) and token.i not in presented
                                  and (_family(token) or any(child.dep_ == 'poss' for child in token.children)
                                       or any(child.dep_ == 'prep' and any(this_patient(grand) for grand in child.children)
                                              for child in token.children))
                                  for token in words)                                                  # RR9
        # Personal pronoun subjects of two genders in one sentence ('She takes ibuprofen and he takes aspirin.').
        genders = {_gender(token) for token in subjects_tok if _personal(token)} - {None}
        # Every personal pronoun in the value, subject, possessive or object (RR6: '... prescribed for her.').
        pronoun_genders = frozenset({_gender(token) for token in words if _personal(token)} - {None})
        embedded = frozenset({_gender(token) for token in words if _personal(token)
                              and (main is None or token.i != main.i)} - {None})
        other = (other_subject or other_possessor or other_heading or fragment_person
                 or (bearer_named and uid not in explicit) or len(genders) > 1
                 or carer_bearer or relative_clause or appositive_relative)
        explicit_patient = uid in explicit and (main is None or age or this_patient(main)
                                                and not any(child.dep_ in ('compound', 'amod', 'poss', 'appos')
                                                            for child in main.children))
        possessed_by = None
        if main is not None:
            owner = next((child for child in main.children if child.dep_ == 'poss'), None)
            if owner is not None:
                possessed_by = ('patient' if owner.pos_ in ('NOUN', 'PROPN') and this_patient(owner)
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
        # Gender CUES for the note's patient (RR6, X2). Each only ever makes a pronoun disagree.
        cues = set()
        if age and main is not None:
            cues.add(_noun_gender(main) or ('Masc' if {_lemma(t) for t in doc} & MASCULINE else
                                            'Fem' if {_lemma(t) for t in doc} & FEMININE else None))
        for token in [main, root] + [child for child in root.children if child.dep_ == 'attr']:
            if token is not None and _described_by_age(token):
                cues.add(_noun_gender(token))
        if main is not None:
            cues.update(TITLE_GENDER.get(_fold(child.text).rstrip('.')) for child in main.children)
        if kind == 'patient':
            for child in root.children:
                if child.dep_ in ('attr', 'acomp') and _lemma(root) == 'be':
                    cues.add(_noun_gender(child))
            found = {_gender(token) for token in possessors if _personal(token)} - {None}
            if len(found) == 1:
                cues.update(found)
        # A labelled line's core words are its VALUE's words (the parser makes its label the root): 'Plan: start
        # warfarin.' is about warfarin.
        core = (_core_lemmas(root) if not colon.get(uid) else
                {_lemma(token) for token in words if token.pos_ in ('NOUN', 'PROPN', 'ADJ', 'VERB') and not token.is_stop
                 and token.is_alpha and _lemma(token) != 'patient'})
        content = _content(doc)
        # SELF-STANDING (round 3): a line that names its own subject and points back at nothing - an explicit-patient
        # sentence, a labelled line, a 'Label is ...' sentence, a sentence with a thing or another person as its
        # subject - with no pronoun standing for something said before ('it', 'this', ...) and not opening with a
        # connective ('But', 'However', 'Also'). A pronoun-led line, a fragment ('Not anymore.') or an unread one in
        # another paragraph may depend on, or change, what was written before it (who a line is about is read by
        # the actor run, which does not stop at a blank line).
        first = next((token for token in doc if not token.is_punct and not token.is_space), None)
        # A connective joins the clause to what came before ('But ...', 'However, ...'); a fronted subordinate clause
        # ('When asked ..., the patient said ...') is attached to its own clause, not to the root.
        connective = bool(first is not None and first.head.i == root.i and (
            first.pos_ == 'CCONJ' or (first.pos_ in ('ADV', 'SCONJ') and first.dep_ in ('advmod', 'cc', 'mark'))))
        points_back = any(token.pos_ in ('PRON', 'DET') and _fold(token.text) in NEUTER
                          and (token.pos_ == 'PRON' or token.dep_ == 'nsubj') for token in words)
        nominal = {_lemma(token) for token in doc if token.pos_ in CONTENT and _lemma(token) != 'patient'}
        info[uid] = {'readable': True, 'kind': kind, 'other': other, 'mentions_other': mentions_other,
                     'content': frozenset(content), 'core': frozenset(core), 'nominal': frozenset(nominal),
                     'keys': keys(content | nominal), 'core_keys': keys(core),
                     'gender': gender, 'pronoun_genders': pronoun_genders,
                     'embedded': embedded if kind == 'patient' else frozenset(),
                     'cues': frozenset(cues - {None}), 'past': _past(root), 'age': age,
                     'standalone': (kind in ('patient', 'labelled', 'label_is', 'thing', 'other') and not connective
                                    and not points_back),
                     'patient_past': kind == 'patient' and _past(root),
                     'bounded': tuple(token.idx for token in words if token.dep_ in ('mark', 'advmod')
                                      and _fold(token.text) in BOUNDING_MARKERS and token.head.dep_ == 'advcl')}
    # The patient's gender is the NOTE's, read before any unit is resolved (X2: a cue after the pronoun counts too).
    cues, gender_cause = set(), None
    for unit in units:
        found = info[unit['id']]['cues']
        if found and gender_cause is None:
            gender_cause = unit
        cues |= found
    note_gender = cues.pop() if len(cues) == 1 else ('conflict' if cues else None)

    def disagrees(found):
        return bool(found and note_gender and (note_gender == 'conflict' or set(found) - {note_gender}))

    resolved = {}
    current, cause, other_since, other_cause = None, None, False, None
    other_ever, other_ever_cause = False, None
    for unit in units:
        uid = unit['id']
        this = info[uid]
        state = {'current': current, 'cause': cause, 'other_since': other_since, 'other_ever': other_ever,
                 'patient_gender': note_gender}
        kind = this['kind']
        self_other = False
        blame = None              # the unit an actor hold shows when it is not the run's cause
        named_other = this['mentions_other'] or this['other']
        if kind == 'unreadable':
            # Nothing is established: whoever it names, the run after it is not uniquely the patient's.
            actor = 'ambiguous'
            current, cause, other_since, other_cause = 'ambiguous', unit, True, unit
        elif kind == 'unread_thing':
            actor = current or 'unresolved'
        elif kind == 'labelled':
            # A labelled line names its question; it neither continues nor CLOSES another person's run (R1-6). A
            # labelled VALUE naming another person as its subject opens one (R3-2).
            actor = 'labelled'
            self_other = disagrees(this['pronoun_genders'])
            if this['other'] or self_other:
                current, cause, other_since, other_cause = 'other', unit, True, unit
            elif this['mentions_other']:
                other_since, other_cause = True, unit
        elif kind == 'other':
            actor = 'other'
            current, cause, other_since, other_cause = 'other', unit, True, unit
        elif kind == 'patient' and this['age'] and current in ('other', 'ambiguous'):
            # An age presentation DESCRIBES a person; after another person's run it may describe that person.
            actor = 'ambiguous'
            current = 'ambiguous'
        elif kind == 'patient':
            if disagrees(this['embedded']):
                # An embedded personal pronoun that disagrees with the patient's gender is another person's.
                actor, self_other = 'other', True
                current, cause, other_since, other_cause = 'other', unit, True, unit
            elif this['embedded'] and (current in ('other', 'ambiguous') or other_since or other_ever):
                # With the gender unknown, an embedded pronoun written after another person was named is not uniquely
                # the patient's ('His father has diabetes. The patient reports that he takes metformin.').
                actor = 'ambiguous'
                cause = other_cause or other_ever_cause or cause
                current = 'ambiguous'
                blame = cause
            else:
                actor = 'patient'
                current, cause = 'patient', unit
                other_since = this['mentions_other']
                other_cause = unit if other_since else None
        elif kind == 'pronoun':
            mismatch = disagrees({this['gender']} - {None}) or disagrees(this['pronoun_genders'])
            if current == 'patient' and not other_since and not mismatch:
                actor = 'patient'
            elif current == 'other':
                actor = 'other'
            elif current in ('patient', 'ambiguous') or mismatch:
                # Not UNIQUELY the patient: another person was named since the patient anchor, or the pronoun's
                # gender disagrees with the patient's ('45-year-old man ... She takes warfarin.').
                actor = 'ambiguous'
                if mismatch and current != 'ambiguous':
                    cause = gender_cause or unit
                elif current == 'patient':
                    cause = other_cause if other_since and other_cause is not None else cause
                current = 'ambiguous'
                blame = cause
            elif other_ever:
                # No antecedent in the run, and another person was named earlier in the note (RR5).
                actor = 'ambiguous'
                cause = other_ever_cause
                current = 'ambiguous'
                blame = cause
            else:
                actor = 'unresolved'
                current, cause = 'unresolved', unit
            if this['mentions_other']:
                other_since, other_cause = True, unit
        else:
            actor = current or 'unresolved'
            self_other = disagrees(this['pronoun_genders'])
            if actor == 'patient' and other_since:
                # An encounter topic or thing after a patient sentence that also named another person.
                actor, blame = 'ambiguous', other_cause
            elif actor == 'unresolved' and other_ever:
                actor, blame = 'ambiguous', other_ever_cause
            if this['mentions_other']:
                other_since, other_cause = True, unit
        if named_other and not other_ever:
            other_ever, other_ever_cause = True, unit
        resolved[uid] = {**state, 'actor': actor, 'self_other': self_other, 'hold_cause': blame or state['cause']}
    return {'units': info, 'resolved': resolved, 'gender': note_gender}
