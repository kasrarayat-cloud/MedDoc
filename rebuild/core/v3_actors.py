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



# ─── 2026-09-30: THE ORDINARY FIELD-RELATIONS FLOORS' READING (`generation.v3_relation_causes`) ──────────────────────
# Read for every parsed unit, and used ONLY by the relation floors, which apply only to a unit the field-relations
# contract (the Sonnet 5 ordinary-notes contract) proves: they HOLD it whatever the model called the other units. None of
# it makes anything an answer, it adds no evidence that a statement is the patient's, and the default path reads none of
# it. Every word list below lists what HOLDS: a word missing from one leaves the unit exactly as on 43fcf214 (the model's
# relation decides it), never released.
#: Words that date a statement to the past ('... last year.', '... two years ago.', 'in childhood').
PAST_TIME_WORDS = frozenset(('ago', 'yesterday', 'last', 'previous', 'previously', 'prior', 'earlier', 'formerly',
                             'former', 'childhood'))
#: Words that end a habit ('formerly', 'an ex-smoker'); 'used to' is read from the parse.
FORMER_WORDS = frozenset(('formerly', 'previously', 'former', 'ex'))
#: Dependents of a clause head that complete it (an object, complement, prepositional phrase or further clause).
COMPLEMENT_DEPS = frozenset(('dobj', 'obj', 'iobj', 'dative', 'attr', 'acomp', 'oprd', 'xcomp', 'ccomp', 'prep',
                             'agent', 'conj', 'advcl', 'pcomp', 'prt'))
#: Verbs too general to name a topic ('takes', 'has', 'reports'): never a comparison key of a claim.
LIGHT_VERBS = frozenset(('be', 'have', 'take', 'get', 'do', 'make', 'use', 'go', 'come', 'see', 'say', 'report',
                         'state', 'tell', 'feel', 'give', 'keep', 'need', 'want'))
_YEAR = re.compile(r'(?:19|20)[0-9]{2}')
#: Determiners and words by which a statement denies a whole CLASS ('no medicines', 'any blood thinners', 'never').
QUANTIFIED_DENIALS = frozenset(('no', 'any', 'neither'))
QUANTIFIED_DENIAL_WORDS = frozenset(('never', 'none', 'nothing', 'nobody', 'nil', 'nowhere', 'nor'))
#: Words that set a quantified thing apart from what was already said ('no other medication', 'nothing else').
SET_APART_WORDS = frozenset(('other', 'else', 'further', 'additional', 'more', 'new'))
#: Verbs by which a statement ENDS what it names ('Methadone was stopped.', 'The pain resolved yesterday.', 'She quit.'),
#: and the phrasal ones by their particle ('came off warfarin', 'gave up smoking').
CESSATION_VERBS = frozenset(('stop', 'discontinue', 'cease', 'withdraw', 'quit', 'halt', 'suspend', 'resolve', 'subside',
                             'abate', 'disappear', 'wean'))
CESSATION_PARTICLES = {'come': 'off', 'give': 'up'}
#: Their participles as the tagger may leave them unlemmatized ('is resolved', 'was discontinued').
CESSATION_FORMS = frozenset(('stopped', 'discontinued', 'ceased', 'withdrawn', 'quit', 'halted', 'suspended', 'resolved',
                             'subsided', 'abated', 'disappeared', 'weaned'))
#: What makes a statement an intention, plan, need, request or refusal rather than what is so now (the PLAN/intention
#: floor, for a question that is not a Plan): a future modal, 'going to', one of these words ('needs', 'declines', 'is
#: due', 'is a candidate for', 'is planned', 'is booked'), or a phrase of pending status ('on hold', 'on the waiting list',
#: 'in preparation'). A word missing here only leaves 43fcf214's reading.
FUTURE_MODALS = frozenset(('will', 'shall', "'ll", 'wo'))
INTENTION_WORDS = frozenset((
    'plan intend want wish hope expect need require request decline refuse consider await schedule propose recommend '
    'advise prefer arrange book offer aim seek defer postpone due candidate eligible keen willing agreeable interested '
    'awaiting pending ready suitable intended planned proposed scheduled booked provisional tentative prospective future'
).split())
DOSING_WORDS = frozenset(('needed', 'required', 'directed', 'prescribed'))
PENDING_PHRASES = frozenset(('hold', 'list', 'agenda', 'horizon', 'card', 'cards', 'pipeline', 'preparation', 'draft',
                             'discussion', 'consideration', 'review', 'waiting'))


def _claim_lemmas(root):
    """What a clause claims, for comparing it with another statement's claim or negation: its head (a verb included,
    unless a light verb), its core arguments, open complements and prepositional objects, and theirs one step down
    ('The patient is subject to MAPPA.' claims subject, MAPPA; 'He smoked heavily.' claims smoke). Used only to HOLD."""
    heads = [root] + [child for child in root.children if child.dep_ == 'conj' and child.pos_ in ('VERB', 'AUX')]
    core = []
    for head in heads:
        core.append(head)
        for child in head.children:
            if child.dep_ in CORE_DEPS or child.dep_ == 'xcomp':
                core.append(child)
            elif child.dep_ == 'prep':
                core.extend(grand for grand in child.children if grand.dep_ == 'pobj')
    for token in list(core):
        if token.dep_ in ('acomp', 'attr', 'xcomp', 'dobj', 'oprd'):
            for child in token.children:
                if child.dep_ == 'prep':
                    core.extend(grand for grand in child.children if grand.dep_ == 'pobj')
                elif child.dep_ in ('dobj', 'xcomp'):
                    core.append(child)
    for token in list(core):
        core.extend(conj for conj in token.children if conj.dep_ == 'conj')
    return {_lemma(token) for token in core
            if (token.pos_ in CONTENT or (token.pos_ == 'VERB' and _lemma(token) not in LIGHT_VERBS))
            and _lemma(token) != 'patient'}


def _tense(clause):
    """'past' or 'present' by the clause's finite verb or auxiliary (parser morphology), None when it has none (a
    verbless or noun-read statement: 'The patient smokes.' may parse as a noun phrase)."""
    for token in [clause] + [child for child in clause.children if child.dep_ in ('aux', 'auxpass')]:
        if 'Fin' in token.morph.get('VerbForm'):
            tense = token.morph.get('Tense')
            if tense:
                return 'past' if 'Past' in tense else 'present'
    return None


def _complement(token):
    """The content words completing a predicate: its object's and its prepositional objects' whole phrases ('tender
    over the lateral epicondyle' -> lateral, epicondyle; 'on diazepam or methadone' -> diazepam, methadone), and
    whether that complement coordinates alternatives (a conjunction inside it)."""
    words, coordinated = set(), False
    for child in token.children:
        phrases = [child] if child.dep_ in ('dobj', 'obj', 'attr', 'oprd') else (
            [grand for grand in child.children if grand.dep_ == 'pobj'] if child.dep_ in ('prep', 'agent') else [])
        for phrase in phrases:
            for t in phrase.subtree:
                if t.pos_ in CONTENT and _lemma(t) != 'patient':
                    words.add(_lemma(t))
                coordinated = coordinated or t.dep_ == 'conj'
    return frozenset(words), coordinated


def _negates(token):
    """A word's own negation: a 'not'/'never' dependent, a 'no' determiner, or 'no longer' / 'not any more' (the pinned
    parser hangs that 'no' on 'longer': 'She no longer smokes.')."""
    return any(child.dep_ == 'neg' or (child.dep_ == 'det' and _fold(child.text) == 'no')
               or (child.dep_ == 'advmod' and _fold(child.text) in ('longer', 'more', 'anymore')
                   and (_fold(child.text) == 'anymore'
                        or any(g.dep_ == 'neg' or _fold(g.text) in ('no', 'not', 'any') for g in child.children)))
               for child in token.children)


def _predicates(root):
    """What a statement asserts or denies, one record per predicate: (head keys, negated, tense, complement keys,
    coordinated). A copula's predicates are its adjectival or nominal complements and its prepositional phrases (the
    preposition is the head: 'is on methadone', 'is off methadone'); any other clause's is its head word (a verb, or the
    noun of a noun-read statement). Negation is the clause's or the predicate's own (`_negates`) or the 'no' of its
    object ('has no allergies'); a conjunct joined by 'but' or 'yet' does not inherit it ('not psychotic but suicidal'
    asserts suicidal). Used only to HOLD (`generation.v3_relation_causes`)."""
    clauses = [root] + [child for child in root.children if child.dep_ == 'conj' and child.pos_ in ('VERB', 'AUX')]
    records = []
    for clause in clauses:
        negated = _negates(clause)
        tense = _tense(clause)
        extra = frozenset()
        if _lemma(clause) == 'be':
            items = [(child, _lemma(child)) for child in clause.children if child.dep_ in ('acomp', 'attr')]
            preps = [child for child in clause.children if child.dep_ == 'prep']
            if items:
                # 'is tender over the lateral epicondyle': the copula's prepositional phrase completes its complement.
                extra = frozenset(_lemma(t) for prep in preps for grand in prep.children if grand.dep_ == 'pobj'
                                  for t in grand.subtree if t.pos_ in CONTENT and _lemma(t) != 'patient')
            else:
                items = [(child, _fold(child.text)) for child in preps]
        else:
            items = [(clause, _lemma(clause))]
        for token, head in items:
            if token.dep_ == 'prep':
                words = {_lemma(t) for grand in token.children if grand.dep_ == 'pobj' for t in grand.subtree
                         if t.pos_ in CONTENT and _lemma(t) != 'patient'}
                coordinated = any(t.dep_ == 'conj' for grand in token.children for t in grand.subtree)
                records.append((frozenset({head}), negated, tense, frozenset(words), coordinated))
                continue
            own = negated or (token is not clause and _negates(token))
            # 'has no allergies', 'takes no medication': the object's 'no' denies the predicate's claim about it.
            own = own or any(child.dep_ in ('dobj', 'attr') and any(grand.dep_ == 'det' and _fold(grand.text) == 'no'
                                                                  for grand in child.children)
                             for child in token.children)
            chain = [(token, own)]
            contrast = any(child.dep_ == 'cc' and _fold(child.text) in ('but', 'yet') for child in token.children)
            for conj in (child for child in token.children if child.dep_ == 'conj'):
                chain.append((conj, _negates(conj) or (own and not contrast)))
            for item, item_negated in chain:
                complement, coordinated = _complement(item)
                records.append((keys({_lemma(item)}), item_negated, tense, complement | extra, coordinated))
    return tuple(records)


def _denied(words, root):
    """What a statement denies by a word rather than by 'not': the whole of a verbless denial ('No MAPPA involvement.',
    'No known drug allergies.'), and the object of 'denies' / 'deny' ('She denies smoking.', 'The patient denies low
    mood.'): the keys of their content words; empty otherwise. Used only to HOLD."""
    found = set()
    if root.pos_ not in ('VERB', 'AUX') and any(child.dep_ == 'neg' or (child.dep_ == 'det' and _fold(child.text) == 'no')
                                                for child in root.children):
        found |= {_lemma(t) for t in root.subtree if t.pos_ in CONTENT}
    for token in words:
        if token.pos_ == 'VERB' and _lemma(token) == 'deny':
            found |= {_lemma(t) for child in token.children if child.dep_ in ('dobj', 'xcomp', 'ccomp')
                      for t in child.subtree if t.pos_ in CONTENT}
    return keys(found - {'patient'})


def _floor_reading(words, root, lem=None, txt=None):
    """The rest of what the relation floors read of one parsed unit (`generation.v3_relation_causes`); each only HOLDS.

      'quantified_denial': a denial by a quantifier, of a thing not set apart from what was said ('She takes no
          medicines.', 'She has never smoked.'; not 'no other medication'), or a negated reference to the patient ('Her
          husband takes warfarin, not her.'): its class may cover another statement's topic (CLASS DENIAL);
      'ceased_keys': what a cessation ends ('Methadone was stopped.', 'She stopped the methadone.', 'The pain resolved
          yesterday.', 'The patient came off warfarin.'); 'bare_cessation': a cessation naming nothing but the patient or
          a pronoun ('The patient quit five years ago.', 'Stopped last month.', 'It was stopped.'), which leans on another
          line for what it ends (DEPENDS);
      'topic_denial_keys': the modifiers of what a negated clause denies having when nothing more specific follows
          ('She has never had an allergic reaction.': allergic), read against a labelled answer's label;
      'surface_keys': every word of the value by its spelling and lemma but light verbs and 'patient' (which printed
          question a class denial names);
      'intention': a future modal, 'going to', an intention word (`INTENTION_WORDS`) or a pending-status phrase
          (`PENDING_PHRASES` under on/in/under/at)."""
    # Every cessation in the statement, wherever the parser puts it: a verb ending its subject or object ('Methadone was
    # stopped.', 'She stopped the methadone.'), a participle the parser hangs on the noun it ends ('The pain resolved
    # yesterday.' parses as the noun 'pain' with 'resolved' modifying it), a copula's complement ('The pain is
    # resolved.'), or a phrasal verb by its particle ('came off warfarin', 'gave up smoking').
    # each word's lemma and folded spelling, read once (`lem`, `txt`: the caller's, by token index)
    lem = lem if lem is not None else {t.i: _lemma(t) for t in words}
    txt = txt if txt is not None else {t.i: _fold(t.text) for t in words}
    cessation, ended = False, set()
    for t in words:
        phrasal = CESSATION_PARTICLES.get(lem[t.i]) if t.pos_ in ('VERB', 'AUX') else None
        particle = [c for c in t.children if c.dep_ in ('prt', 'prep') and _fold(c.text) == phrasal] if phrasal else []
        if not ((t.pos_ in ('VERB', 'ADJ', 'AUX') and (lem[t.i] in CESSATION_VERBS or txt[t.i] in CESSATION_FORMS))
                or particle):
            continue
        cessation = True
        for child in t.children:
            if child.dep_ in ('nsubj', 'nsubjpass', 'dobj', 'obj', 'xcomp', 'ccomp'):
                ended |= {_lemma(x) for x in child.subtree if x.pos_ in CONTENT}
        for child in particle:
            ended |= {_lemma(x) for grand in child.children if grand.dep_ == 'pobj' for x in grand.subtree
                      if x.pos_ in CONTENT}
        if t.dep_ in ('acl', 'relcl', 'amod') and t.head.i != t.i:
            inner = {x.i for x in t.subtree}
            ended |= {_lemma(x) for x in t.head.subtree if x.i not in inner and x.pos_ in CONTENT}
        if t.dep_ in ('acomp', 'attr', 'oprd') and t.head.i != t.i:
            ended |= {_lemma(x) for c in t.head.children if c.dep_ in ('nsubj', 'nsubjpass') for x in c.subtree
                      if x.pos_ in CONTENT}
    ended -= {'patient'}
    # A CLASS denial denies by a quantifier ('takes no anticoagulants', 'has had no pain', 'has never smoked', 'none',
    # 'nothing'), unless the quantified thing is set apart from what was already said ('no other medication', 'nothing
    # else', 'no further pain'); a plain 'not' denies its own predicate, which OPPOSED reads with its object, time and
    # person ('is not responsive to medication' / 'is responsive to physiotherapy'). A negated reference to the patient
    # re-attributes a statement to somebody else ('Her husband takes warfarin, not her.'), whatever it shares.
    def set_apart(t):
        near = [t.head] + list(t.head.children) + list(t.children) + ([t.head.head] if t.dep_ == 'det' else [])
        return any(txt.get(x.i, _fold(x.text)) in SET_APART_WORDS for x in near)
    quantifiers = [t for t in words if ((t.dep_ == 'det' and txt[t.i] in QUANTIFIED_DENIALS)
                                        or txt[t.i] in QUANTIFIED_DENIAL_WORDS) and not set_apart(t)]
    reattribution = any((_personal(t) or this_patient(t)) and (
        any(c.dep_ == 'neg' for c in t.children) or (t.i > 0 and _fold(t.doc[t.i - 1].text) in ('not', 'never')))
        for t in words)
    quantified = bool(quantifiers) or reattribution
    # what a quantifier denies: the thing it quantifies ('no anticoagulants') and the predicate governing it ('takes'),
    # or for 'never' / 'nothing' / 'none' the predicate it hangs on ('has never smoked')
    denial_nouns, denial_heads = set(), set()
    for q in quantifiers:
        if q.dep_ == 'det' and q.head.i != q.i:
            # the noun phrase's own head ('no relationship changes' parses 'no' onto 'relationship', a modifier)
            noun = q.head
            while noun.dep_ in ('compound', 'amod', 'nmod') and noun.head.i != noun.i and noun.head.pos_ in ('NOUN', 'PROPN'):
                noun = noun.head
            denial_nouns.add(_lemma(noun))
            if noun.head.i != noun.i:
                denial_heads.add(_lemma(noun.head))
        elif q.head.i != q.i:
            denial_heads.add(_lemma(q.head))
    # (read only for a class denial: which printed question it names)
    surface = {w for t in words if t.is_alpha and not t.is_stop and lem[t.i] not in LIGHT_VERBS
               and lem[t.i] != 'patient' for w in (lem[t.i], txt[t.i])} if quantified else set()
    # INTENTION is read on the statement's own predicate - each head of the value's clause (a labelled line's value
    # included) and its conjoined verbs, their clausal complements one step down, and a copula's complements - never on
    # a word modifying something inside it ('... staff also confirm attendance at planned visits.' states no plan).
    inside = {t.i for t in words}
    heads = [t for t in words if t.head.i == t.i or t.head.i not in inside]
    heads += [c for h in list(heads) for c in h.children if c.dep_ == 'conj' and c.pos_ in ('VERB', 'AUX')]
    clauses = heads + [c for h in heads for c in h.children if c.dep_ in ('xcomp', 'ccomp') and c.i in inside]
    # A dosing idiom ('She takes ibuprofen as needed.', 'as required', 'as directed') states how a current medicine is
    # taken, not an intention.
    dosing = {t.i for t in words if t.dep_ == 'advcl' and txt[t.i] in DOSING_WORDS
              and [(_fold(c.text), c.dep_) for c in t.children] == [('as', 'mark')]}

    def intended(h):
        if any(c.tag_ == 'MD' and _fold(c.text) in FUTURE_MODALS for c in h.children) or (
                h.tag_ == 'MD' and txt.get(h.i) in FUTURE_MODALS):
            return True                                                                    # 'will start', 'shall'
        if lem.get(h.i) == 'go' and h.tag_ == 'VBG' and any(
                c.dep_ == 'xcomp' and any(a.dep_ == 'aux' and _fold(a.text) == 'to' for a in c.children)
                for c in h.children):
            return True                                                                    # 'is going to start'
        if h.i not in dosing and (lem.get(h.i) in INTENTION_WORDS or txt.get(h.i) in INTENTION_WORDS):
            return True                                                                    # 'needs', 'is planned'
        for c in h.children:
            if c.dep_ in ('acomp', 'attr', 'oprd') and (_lemma(c) in INTENTION_WORDS or _fold(c.text) in INTENTION_WORDS):
                return True                                                                # 'is due', 'a candidate'
            if c.dep_ == 'prep' and _fold(c.text) in ('on', 'in', 'under', 'at') and any(
                    g.dep_ == 'pobj' and (_lemma(g) in PENDING_PHRASES or _fold(g.text) in PENDING_PHRASES)
                    for g in c.children):
                return True                                                                # 'on the waiting list'
        return False
    intention = any(intended(h) for h in clauses)
    return {'quantified_denial': quantified, 'reattribution': reattribution,
            'denial_nouns': keys(denial_nouns), 'denial_heads': keys(denial_heads) | frozenset(denial_heads),
            'ceased_keys': keys(ended), 'bare_cessation': cessation and not keys(ended),
            'topic_denial_keys': (keys({_lemma(m) for c in root.children if c.dep_ in ('dobj', 'attr')
                                        and not any(g.dep_ == 'prep' for g in c.children)
                                        for m in c.children if m.dep_ in ('amod', 'compound')})
                                  if any(c.dep_ == 'neg' for c in root.children) else frozenset()),
            'surface_keys': keys(surface), 'intention': intention}


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
            'past': True, 'bounded': (0,), 'age': False, 'standalone': False, 'patient_past': True,
            # the relation floors' reading (`_floor_reading`, 2026-09-30): an unread unit may deny, end or plan anything,
            # so it reads as all of them (fail closed); it claims and depends on nothing that could be compared
            'habitual': True, 'past_time': True, 'finite_past': True, 'present_tense': False, 'dependent': False,
            'main_patient': False,
            'other_floor': person,
            'claim_keys': frozenset(), 'negated_keys': frozenset(), 'predicates': (),
            'quantified_denial': True, 'reattribution': True, 'denial_nouns': frozenset(), 'denial_heads': frozenset(),
            'bare_cessation': True, 'ceased_keys': frozenset(),
            'topic_denial_keys': frozenset(), 'surface_keys': frozenset(), 'intention': True}


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
        # 2026-09-30, READ ONLY BY THE RELATION FLOORS: the same reading with the noun an age presentation describes
        # counted as the presented patient too ('This is a 30-year-old woman seen for headaches.': the parser hangs
        # 'seen' on 'woman' as a relative clause, so the reading above calls the opener another person's). Every other
        # person it names still counts ('This is a 12-year-old boy seen with his mother, who has chest pain.').
        other_floor = other
        if other and age:
            described = {t.i for t in doc if _described_by_age(t)}
            presented_age = presented | described
            other_floor = (
                any(names_person(t) and t.i not in presented_age and not (t.i == 0 and age) for t in subjects_tok)
                or other_possessor or other_heading
                or (main is None and not colon.get(uid) and names_person(root) and root.i not in presented_age)
                or (any(names_person(t) and t.i not in presented_age and not this_patient(t) for t in words)
                    and uid not in explicit)
                or len(genders) > 1 or carer_bearer
                or any(names_person(t) and t.i not in presented_age and not this_patient(t)
                       and any(c.dep_ in ('relcl', 'acl') for c in t.children) for t in words)
                or any(t.dep_ == 'appos' and names_person(t) and t.i not in presented_age
                       and (_family(t) or any(c.dep_ == 'poss' for c in t.children)
                            or any(c.dep_ == 'prep' and any(this_patient(g) for g in c.children) for c in t.children))
                       for t in words))
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
        # 2026-09-30, READ ONLY BY THE RELATION FLOORS (`generation.v3_relation_causes`; each only HOLDS): a habit that
        # ended ('used to', 'formerly'); a word dating it to the past; whether it DEPENDS on what came before it (it
        # points back, opens with a connective, has no content word, or is a clause with no complement whose subject is
        # absent or a personal pronoun: 'Stopped last month.', 'She quit last month.'); what it claims and what it
        # negates; whether its main subject is the explicit patient; and `_floor_reading`.
        lem = {t.i: _lemma(t) for t in words}
        txt = {t.i: _fold(t.text) for t in words}
        habitual = (any(lem[t.i] == 'use' and any(c.dep_ == 'xcomp' and any(a.dep_ == 'aux' and _fold(a.text) == 'to'
                                                                           for a in c.children) for c in t.children)
                        for t in words)
                    or any(txt[t.i] in FORMER_WORDS for t in words))
        past_time = any(txt[t.i] in PAST_TIME_WORDS or (t.pos_ == 'NUM' and _YEAR.fullmatch(t.text)) for t in words)
        root_subjects = [c for c in root.children if c.dep_ in ('nsubj', 'nsubjpass', 'expl', 'csubj', 'csubjpass')]
        complete_clause = any(c.dep_ in COMPLEMENT_DEPS for c in root.children)
        dependent = not colon.get(uid) and not age and bool(
            connective or points_back
            or not any(t.pos_ in ('NOUN', 'PROPN', 'VERB', 'ADJ', 'NUM') for t in words)
            or (root.pos_ in ('VERB', 'AUX') and not complete_clause
                and (not root_subjects or (main is not None and _personal(main)))))
        claim = (_claim_lemmas(root) if not colon.get(uid) else
                 {_lemma(t) for t in words if t.pos_ in CONTENT or (t.pos_ == 'VERB' and _lemma(t) not in LIGHT_VERBS)})
        floors = {'habitual': habitual, 'past_time': past_time, 'dependent': dependent,
                  'claim_keys': keys(claim - {'patient'}),
                  'predicates': () if colon.get(uid) else _predicates(root),
                  'negated_keys': frozenset() if colon.get(uid) else _denied(words, root),
                  'finite_past': not colon.get(uid) and _tense(root) == 'past',
                  # a finite present anywhere on the statement's own predicate (a labelled line's value read alone): a
                  # verbless value dated to the past ('Right knee: pain last year.') is not present
                  'present_tense': any(_tense(h) == 'present' for h in
                                       ([t for t in words if t.head.i == t.i or t.head.i not in {w.i for w in words}]
                                        if colon.get(uid) else [root])),
                  'main_patient': bool(main is not None and main.pos_ in ('NOUN', 'PROPN') and this_patient(main)
                                       and not any(c.dep_ in ('poss', 'compound', 'amod', 'appos') for c in main.children)),
                  'other_floor': other_floor, **_floor_reading(words, root, lem, txt)}
        info[uid] = {**floors, 'readable': True, 'kind': kind, 'other': other, 'mentions_other': mentions_other,
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
