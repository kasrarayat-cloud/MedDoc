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
import functools
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


@functools.lru_cache(maxsize=1 << 16)
def _fold_text(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).casefold()


def _fold(text):
    # memoized on the string (a pure function of it): the single-patient reading folds every word of every unit
    return _fold_text(str(text))


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
    # stopped.', 'She stopped the methadone.'), or a phrasal verb by its particle ('came off warfarin', 'gave up
    # smoking'). One whose ended thing the parse does not attach to it ('The pain resolved yesterday.' parses as the
    # noun 'pain' with 'resolved' modifying it) names nothing, so it holds as a bare cessation (DEPENDS).
    # each word's lemma and folded spelling, read once (`lem`, `txt`: the caller's, by token index)
    lem = lem if lem is not None else {t.i: _lemma(t) for t in words}
    txt = txt if txt is not None else {t.i: _fold(t.text) for t in words}
    cessation, ended = False, set()
    for t in words:
        phrasal = CESSATION_PARTICLES.get(lem[t.i]) if t.pos_ in ('VERB', 'AUX') else None
        particle = [c for c in t.children if c.dep_ in ('prt', 'prep') and _fold(c.text) == phrasal] if phrasal else []
        if not ((t.pos_ in ('VERB', 'ADJ', 'AUX') and lem[t.i] in CESSATION_VERBS) or particle):
            continue
        cessation = True
        for child in t.children:
            if child.dep_ in ('nsubj', 'nsubjpass', 'dobj', 'obj', 'xcomp', 'ccomp'):
                ended |= {_lemma(x) for x in child.subtree if x.pos_ in CONTENT}
        for child in particle:
            ended |= {_lemma(x) for grand in child.children if grand.dep_ == 'pobj' for x in grand.subtree
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
            noun = q.head
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
    # (a dosing idiom, 'She takes ibuprofen as needed.', is an adverbial clause, never one of these)

    def intended(h):
        if any(c.tag_ == 'MD' and _fold(c.text) in FUTURE_MODALS for c in h.children) or (
                h.tag_ == 'MD' and txt.get(h.i) in FUTURE_MODALS):
            return True                                                                    # 'will start', 'shall'
        if lem.get(h.i) == 'go' and h.tag_ == 'VBG' and any(
                c.dep_ == 'xcomp' and any(a.dep_ == 'aux' and _fold(a.text) == 'to' for a in c.children)
                for c in h.children):
            return True                                                                    # 'is going to start'
        if lem.get(h.i) in INTENTION_WORDS or txt.get(h.i) in INTENTION_WORDS:
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


# ─── 2026-10-01: A POSITIVELY ESTABLISHED SINGLE-PATIENT SCOPE (`sole_patient`) ─────────────────────────────────────────
# Read ONLY by the ordinary field-relations reader (`v3_field_relations.read`) and its floors, for a unit the relation
# reader would otherwise refuse for want of patient evidence ('She takes ibuprofen as needed.'). The three earlier
# designs read a pronoun, a thing or an implicit subject as the patient's from the ABSENCE of a listed danger (a person
# noun, a time word), and every one was refuted by a person or a time the lists missed ('The patient employs a
# housekeeper. She takes warfarin.', 'The patient visits JANE daily.', 'On admission she is on warfarin.'). This reading
# is the opposite polarity: a note is one patient's only when EVERY nominal word in it is POSITIVELY known to name no
# person and no animal (`SOLE_NOUNS`; anything else, an unknown drug name included, fails closed), its first unit
# presents the patient, all its personal pronouns are one gender that agrees, no unit is fronted by a frame ('On
# admission ...', 'Then ...'), it names at most one side and states nothing uncertain outside an assessment. A word
# missing from a list here only HOLDS. Nothing here is read by the default path.
#: Nouns (lemmas, casefolded) that positively name no person and no animal: parts of the body, symptoms and conditions,
#: generic drug names, clinical things, measures and times. Words that can stand for a person by metonymy are not here,
#: or are in `SOLE_RESTRICTED`; given names, brand names and agent nouns ('-er', '-ist') are never here.
#: Each word's TOPIC CLASS (`SOLE_CLASSES`) is what the release's independence check compares (`sole_released`): a
#: neighbour about the same topic, or one that denies, ends, corrects or restricts it, holds the answer. 'body', 'meta'
#: and 'time' words name no topic of their own.
SOLE_LEXICON = {
    'body': 'head face eye eyes ear nose mouth throat neck shoulder arm forearm elbow wrist finger thumb chest breast '
            'abdomen stomach belly back spine hip groin leg thigh knee shin ankle foot feet toe heel skin joint muscle '
            'bone lung liver kidney bladder bowel brain blood vein artery meniscus ligament tendon cartilage lymph node '
            'gland scalp jaw tooth teeth gum tongue lip pelvis rib buttock side area region site',
    'symptom': 'pain ache headache migraine cough fever temperature rash itch itching swelling tightness stiffness '
               'weakness numbness tingling dizziness vertigo nausea vomiting diarrhoea diarrhea constipation fatigue '
               'tiredness breathlessness wheeze breath palpitation bleeding bruising bruise cramp spasm change '
               'disturbance symptom problem complaint aura spot flash zigzag line band vision hearing appetite sleep '
               'mood lump tenderness',
    'finding': 'effusion tenderness swelling lesion ulcer wound murmur rash bruise reflex power sensation tone gait '
               'pulse pressure rate rhythm saturation temperature range motion movement reading level score weight',
    'condition': 'hypertension hypotension diabetes asthma angina arthritis osteoarthritis depression anxiety insomnia '
                 'eczema psoriasis acne dermatitis cancer tumour tumor seizure epilepsy infection inflammation disease '
                 'disorder illness condition attack glucose cholesterol',
    'injury': 'injury fracture sprain strain tear fall trauma',
    'medication': 'ibuprofen paracetamol acetaminophen aspirin codeine morphine tramadol naproxen diclofenac '
                  'amitriptyline nortriptyline gabapentin pregabalin sertraline citalopram fluoxetine mirtazapine '
                  'diazepam lorazepam methadone buprenorphine warfarin apixaban rivaroxaban heparin clopidogrel '
                  'atorvastatin simvastatin rosuvastatin pravastatin lisinopril ramipril enalapril amlodipine bisoprolol '
                  'atenolol metoprolol losartan furosemide bendroflumethiazide metformin gliclazide insulin '
                  'levothyroxine omeprazole lansoprazole salbutamol beclometasone prednisolone prednisone hydrocortisone '
                  'amoxicillin penicillin flucloxacillin doxycycline clarithromycin erythromycin trimethoprim '
                  'nitrofurantoin cetirizine loratadine medication medicine drug tablet pill capsule injection inhaler '
                  'cream dose mg mcg ml puff',
    'allergy': 'allergy anaphylaxis reaction latex peanut shellfish',
    'smoking': 'smoking cigarette tobacco vaping',
    'alcohol': 'alcohol',
    'test': 'test scan x-ray xray ultrasound stress exercise',
    'therapy': 'physiotherapy therapy treatment management follow-up procedure operation removal excision suture stitch '
               'dressing anaesthesia anesthesia anaesthetic',
    'care': 'clinic attendance community order consent',
    'meta': 'examination exam assessment plan diagnosis impression finding result benefit status type tension',
    'time': 'day week month year morning evening night hour minute time bedtime',
}
SOLE_CLASSES = {}
for _topic, _words in SOLE_LEXICON.items():
    for _word in _words.split():
        SOLE_CLASSES.setdefault(_word, set()).add(_topic)
SOLE_CLASSES = {word: frozenset(found - {'body', 'meta', 'time'}) for word, found in SOLE_CLASSES.items()}
SOLE_NOUNS = frozenset(SOLE_CLASSES)
#: Words that DENY ('not', 'no', 'denies', 'without', 'pain free'): an answer may itself be a denial.
SOLE_NEGATION = frozenset(('not', "n't", 'no', 'never', 'none', 'nothing', 'nil', 'without', 'free', 'deny', 'negative',
                           'absent', 'lack', 'neither', 'nor', 'nkda'))
#: Classes of the words outside the nouns that name a topic ('smokes', 'a nonsmoker', 'allergic').
SOLE_WORD_CLASSES = {'smoke': frozenset({'smoking'}), 'vape': frozenset({'smoking'}), 'smoker': frozenset({'smoking'}),
                     'nonsmoker': frozenset({'smoking'}), 'non-smoker': frozenset({'smoking'}),
                     'ex-smoker': frozenset({'smoking'}), 'vaper': frozenset({'smoking'}),
                     'drink': frozenset({'alcohol'}), 'drinker': frozenset({'alcohol'}),
                     'nondrinker': frozenset({'alcohol'}), 'allergic': frozenset({'allergy'}),
                     'referral': frozenset({'therapy'}), 'sugar': frozenset({'condition'}), 'hand': frozenset(),
                     'attend': frozenset({'care'}),
                     # 'NKDA' (no known drug allergies) is an allergy answer AND its negation (`SOLE_NEGATION`)
                     'nkda': frozenset({'allergy'})}
#: Words that are NOT a topic and change nothing ('takes', 'normal', 'as needed'): any other word in a single-patient
#: note that is neither a known noun, a known operator nor one of these makes the note's release fail closed - an
#: unknown word may deny, end or correct ('She is not anticoagulated.', 'She was misheard.').
SOLE_NEUTRAL_WORDS = frozenset((
    # verbs
    'be have take use attend present see notice describe report start begin follow show reveal demonstrate appear occur '
    'examine tolerate discuss obtain close excise need require direct know feel get complain experience suffer measure '
    'perform do apply tick make seem look radiate worsen improve smoke vape drink '
    # adjectives
    'visual neurological normal small large medial lateral tight mild moderate severe acute chronic local general known '
    'clinical physical upper lower bad worse better good tender swollen red warm sharp dull constant intermittent '
    'regular stable subject well unremarkable clear soft central superficial deep minor major new old year-old '
    'right left daily weekly nightly monthly present medical past current chief tension-type '
    # adverbs and particles
    'as up out very much currently twice once there to'
).split())
#: OPERATORS - what lets one line change another: their REACH. 'global': a correction or a pointer to another line ('The
#: previous line is incorrect.', 'She was misheard.', 'Sorry, ...') holds every release in the note; 'class': a denial,
#: an ending, a restriction, an uncertainty or a condition ('She takes no medicines.', 'The patient used to smoke.',
#: 'The patient is allergic to latex only.', 'She may need warfarin.') holds a release about the same topic class;
#: 'key': a contraindication ('She is allergic to amitriptyline.', 'Amitriptyline is contraindicated.') holds a release
#: sharing its word. A word missing here is UNKNOWN (`SOLE_NEUTRAL_WORDS`), which fails closed.
SOLE_OPERATORS = {
    'global': frozenset((
        'sorry mean incorrect wrong error mistake misheard misspoke mistyped correction correct corrected scratch strike '
        'disregard ignore retract retracted delete amend amended erroneous previous above below following aforementioned '
        'latter preceding typo misdiagnosed oops actually').split()),
    'class': frozenset((
        'not n\'t no never none nothing nil without free deny negative absent lack neither nor stop discontinue cease '
        'quit resolve subside withdraw wean taper switch change replace swap substitute hold withhold reduce increase '
        'decrease adjust titrate halve double avoid until till used formerly former ex previously anymore longer finish '
        'complete only also except instead rather alone solely just but however although though unless if when apart '
        'besides other may might could would should possible possibly probable probably suspected suspect query unsure '
        'unclear uncertain unknown unconfirmed likely unlikely maybe perhaps questionable presumed presumably '
        'differential ruled exclude excluded whereas while otherwise yet nevertheless nonetheless despite cannot or '
        'either risk option alternatively').split()),
    'key': frozenset((
        'allergic allergy intolerant intolerance sensitive sensitivity reaction anaphylaxis contraindicated '
        'contraindication caution').split()),
}
#: Nouns that can stand for a person by metonymy ('the referral' for the person referred, 'the head of department'):
#: positively no person only where they cannot be one - never a subject, a possessor, an appositive, or the object of
#: with / by / from / for / to / of a person.
SOLE_RESTRICTED = frozenset(('referral', 'head', 'hand', 'sugar'))
#: Lexicon words that can name a group of people (`_sole_noun_ok`).
SOLE_COLLECTIVE = frozenset(('band', 'community', 'order', 'clinic', 'care', 'team'))
#: Status nouns ('smoker', 'nonsmoker'): a person, so only as a printed label ('Smoker: No.') or predicated of the
#: patient ('She is a nonsmoker.'), never as somebody else ('The patient lives with a smoker.').
SOLE_STATUS = frozenset(('smoker', 'nonsmoker', 'non-smoker', 'drinker', 'nondrinker', 'vaper', 'ex-smoker'))
#: Initialisms that name a test (an initialism can be a role: 'CPN', 'GP'; anything else fails closed).
SOLE_INITIALISMS = frozenset(('mri', 'ct', 'ecg', 'ekg', 'eeg'))
#: Plain answer words ('Smoker: No.', 'Allergies: none.').
SOLE_ANSWERS = frozenset(('yes', 'no', 'none', 'nil', 'nkda'))
#: The patient's own presented noun, in the presenting unit only ('This is a 30-year-old female ...').
SOLE_PRESENTED = frozenset(('man', 'woman', 'male', 'female', 'boy', 'girl', 'child', 'patient'))
#: Pronouns that cannot be another person ('it', 'this', 'there', 'none'); personal pronouns are read apart.
SOLE_PRONOUNS = frozenset(('it', 'its', 'itself', 'this', 'that', 'these', 'those', 'there', 'none', 'nothing', 'all',
                           'both', 'which', 'what'))
SOLE_PERSONAL = frozenset(('he', 'she', 'him', 'her', 'his', 'hers', 'himself', 'herself'))
#: Pronouns that can stand for a GROUP of people ('Both have asthma.', 'All take warfarin.', 'These ...'): a thing only
#: where nothing can act or bear - never a subject, possessor, agent or apposition (refutation round 4, R2-F5).
SOLE_GROUP_PRONOUNS = frozenset(('all', 'both', 'these', 'those'))
SOLE_REFLEXIVE = frozenset(('himself', 'herself'))
#: Dependencies that make a word nominal whatever the tagger called it ('lives with Will': a name read as a verb).
SOLE_NOMINAL_DEPS = frozenset(('nsubj', 'nsubjpass', 'dobj', 'obj', 'iobj', 'dative', 'pobj', 'attr', 'oprd', 'appos',
                               'npadvmod', 'poss', 'agent', 'compound', 'nmod'))
#: Prepositions whose object can be a companion, agent, source or beneficiary (where a restricted noun fails).
SOLE_PERSON_PREPS = frozenset(('with', 'by', 'from', 'for', 'to', 'of', 'at', 'beside', 'alongside'))
#: Words that leave a statement uncertain ('possible', 'unsure', '?'); allowed only in an assessment's own line.
SOLE_UNCERTAIN = frozenset(('possible', 'possibly', 'probable', 'probably', 'suspected', 'suspect', 'query', 'unsure',
                            'unclear', 'uncertain', 'unknown', 'unconfirmed', 'likely', 'unlikely', 'maybe', 'perhaps',
                            'questionable', 'presumed', 'presumably', 'differential', 'ruled', 'exclude', 'excluded'))
#: Words that DENY a diagnosis ('asthma excluded', 'ruled out'): uncertain for the scope (`SOLE_UNCERTAIN`) but never a
#: DOUBT (`_sole_reading` 'doubt_only'): an assessment excluding something is not a probable diagnosis (round 4).
SOLE_EXCLUSION = frozenset(('ruled', 'exclude', 'excluded'))
SOLE_DOUBT = SOLE_UNCERTAIN - SOLE_EXCLUSION
#: (round 5, R1/R2) The clinical topic classes: a symptom, a finding, a condition and an injury may be one thing in other
#: words ('fever' / 'temperature', 'swelling' / 'effusion', 'wheeze' / 'asthma'), so none can be told apart from another
#: by its word.
SOLE_CLINICAL = frozenset(('symptom', 'finding', 'condition', 'injury'))
#: What an answer that DENIES, ENDS or CONTRAINDICATES something of a class may be contradicted by (`sole_bears_on`): the
#: topic classes a statement elsewhere in the note can bear on it through ('She takes no medicines.' beside 'bleeding on
#: warfarin', 'diabetes on insulin' or 'on treatment'; 'She has no allergies.' beside a drug, a rash or a test). A class
#: not listed here bears on every class (fail closed).
SOLE_BEARS_ON = {
    'smoking': frozenset(('smoking',)),
    'alcohol': frozenset(('alcohol',)),
    'medication': frozenset(('medication', 'therapy', 'condition', 'allergy')),
    'allergy': SOLE_CLINICAL | frozenset(('allergy', 'medication', 'therapy', 'test')),
    **{name: SOLE_CLINICAL | frozenset(('allergy', 'medication', 'therapy', 'test')) for name in SOLE_CLINICAL},
}
#: Words outside the nouns that state NO clinical state of their own ('takes', 'attends', 'daily', 'medial'): any other
#: adjective, verb or adverb ('normal', 'swollen', 'tender', 'worse', 'improves') may describe the state a denial denies
#: ('There is no swelling.' beside 'The knee is swollen.'), so a line carrying one is not positively apart from it
#: (`_sole_reading` 'descriptive'). A word missing here only HOLDS.
SOLE_INERT = frozenset((
    'be have take use attend present see notice describe report start begin follow show reveal demonstrate appear occur '
    'examine discuss obtain need require direct know get do make apply tick perform seem look measure smoke vape drink '
    'complain experience suffer feel close excise '
    'as up out very much currently twice once there to '
    'medical past current chief known general clinical physical year-old daily weekly nightly monthly present upper '
    'lower medial lateral central local').split())


#: Every topic class a word can name.
SOLE_EVERY_CLASS = frozenset().union(*SOLE_CLASSES.values(), *SOLE_WORD_CLASSES.values())


def sole_bears_on(classes):
    """The topic classes a statement must name none of to be positively apart from an answer of `classes` that denies,
    ends or contraindicates (`SOLE_BEARS_ON`; an unlisted class bears on all)."""
    return frozenset().union(*(SOLE_BEARS_ON.get(name, SOLE_EVERY_CLASS) for name in classes))
SOLE_SIDES = {'left': 'left', 'lt': 'left', 'l': 'left', 'right': 'right', 'rt': 'right', 'r': 'right',
              'bilateral': 'both', 'both': 'both'}
#: Words of time: in an answer to a question about what is so NOW, each must sit in a frequency phrase.
SOLE_TIME_WORDS = (GENERIC_WORDS | PAST_TIME_WORDS | frozenset((
    'january february march april may june july august september october november december monday tuesday wednesday '
    'thursday friday saturday sunday admission admit admitted discharge discharged then when whenever while during '
    'before after since until till from between recent soon later next earlier initially originally already anymore '
    'longer yet again now today tonight tomorrow yesterday weekend holiday season spring summer autumn winter last '
    'first').split())) - {'weekly', 'daily', 'nightly', 'monthly', 'yearly', 'annually', 'hourly'}
#: Frequency adverbs and nouns a current answer may carry ('daily', 'every week', 'at night', 'as needed').
SOLE_FREQUENCY_ADVERBS = frozenset(('daily', 'weekly', 'nightly', 'monthly', 'fortnightly', 'hourly', 'currently'))
SOLE_FREQUENCY_NOUNS = frozenset(('day', 'week', 'month', 'night', 'morning', 'evening', 'hour', 'bedtime'))
#: Verbs a current answer may be stated with, in the present ('She takes ...', 'She attends ...', 'She is a ...').
SOLE_CURRENT_VERBS = frozenset(('be', 'have', 'take', 'use', 'attend', 'smoke', 'drink', 'vape', 'see', 'notice', 'feel',
                                'experience', 'get', 'report', 'describe', 'deny', 'complain', 'suffer'))
_DATE_LIKE = re.compile(r'(?:\d{4}|\d{1,2}[/.\-]\d{1,4}(?:[/.\-]\d{2,4})?|\d{1,2}:\d{2}|\d+(?:st|nd|rd|th))', re.I)
#: The presenting opener with an article ('A 45-year-old man presents with cough.'): the deterministic age grammar
#: (`generation.AGE_PATIENT_PRESENTATION`) without it is unchanged on the default path.
SOLE_OPENER = re.compile(r'(?:an?\s+)?\d{1,3}-year-old (?:man|woman|male|female|boy|girl|child|patient) '
                         r'(?:(?:presents|presented) (?:with|for)|(?:was )?seen for)\b', re.I)


def _misread(token):
    """A word the tagger put in a CLOSED class (preposition, determiner, conjunction, particle, auxiliary) that is not one
    of that class's words: the pinned model reads drug names and names that way ('She will start amitriptyline ...':
    'amitriptyline' ADP). The single-patient reading treats it as the noun it is."""
    return (token.pos_ in ('ADP', 'SCONJ', 'PART', 'DET', 'CCONJ', 'AUX') and token.is_alpha and not token.is_stop
            and _fold(token.text) not in ("n't", 'nt'))


def _the_patient(token):
    """'the patient', 'this patient' or a bare 'Patient': THIS note's patient by the noun alone (refutation round 4,
    2026-10-01) - singular, no determiner but 'the' or 'this', and nothing else said of the noun (no modifier, possessor,
    number, apposition, clause, preposition or conjunct). A plural ('Some patients', 'All patients'), an indefinite ('A
    patient'), a possessor ('Her patient'), an age or any other modifier ('The male patient', 'The older patient', 'The
    70-year-old patient') may be somebody else, so it fails closed. Read only by the single-patient scope."""
    if _lemma(token) != 'patient' or _fold(token.text) != 'patient':
        return False
    return all((child.dep_ == 'det' and _fold(child.text) in ('the', 'this')) or child.dep_ in ('case', 'punct')
               for child in token.children)


def _sole_noun_ok(token, *, anchor_nouns, label_end):
    """Whether one nominal token positively names no person or animal (`SOLE_NOUNS` and friends)."""
    text, lemma = _fold(token.text), _lemma(token)
    if token.idx < label_end:                                    # a printed label's own words ('Smoker:', 'Allergies:')
        return lemma in SOLE_NOUNS or text in SOLE_NOUNS or lemma in SOLE_STATUS or text in SOLE_STATUS
    if token.i in anchor_nouns:
        return True
    if token.pos_ == 'NUM' and token.dep_ not in ('nsubj', 'nsubjpass'):
        return True
    if lemma == 'patient':
        return _the_patient(token)
    if (token.pos_ in ('ADJ', 'ADV', 'VERB', 'AUX', 'ADP', 'DET', 'CCONJ', 'SCONJ', 'PART', 'INTJ') and not _misread(token)
            and token.dep_ not in ('nsubj', 'nsubjpass', 'dobj', 'obj', 'iobj', 'dative', 'pobj', 'appos', 'poss', 'agent')):
        return True
    if text in SOLE_ANSWERS:
        return True
    if token.text.isupper() and len(token.text) <= 5 and text in SOLE_INITIALISMS:
        return True
    if (lemma in SOLE_STATUS or text in SOLE_STATUS) and token.dep_ in ('attr', 'oprd') and _lemma(token.head) == 'be':
        subject = next((c for c in token.head.children if c.dep_ in ('nsubj', 'nsubjpass')), None)
        return subject is not None and (_fold(subject.text) in ('he', 'she') or _the_patient(subject))
    if lemma in SOLE_RESTRICTED or text in SOLE_RESTRICTED:
        if token.dep_ in ('nsubj', 'nsubjpass', 'poss', 'appos', 'agent', 'conj') or any(
                c.dep_ in ('relcl', 'acl', 'appos') for c in token.children):
            return False
        return not (token.dep_ == 'pobj' and _fold(token.head.text) in SOLE_PERSON_PREPS
                    and _fold(token.head.text) != 'of')
    if lemma not in SOLE_NOUNS and text not in SOLE_NOUNS:
        return False
    # A noun standing ALONE as a subject or a possessor may be a name the lexicon happens to know, WHATEVER its verb
    # ('Spot has a rash.', 'Spot is allergic to penicillin.' - round 4, R2-F5; 'Spot is in pain.', 'Flash is with
    # fever.', 'Spot itches.', "Spot's knee ..." - round 5, R3): positively a thing there only with a determiner, a
    # possessor, a number or a modifier ('The rash has spread.', 'Her knee has an effusion.', 'Knee pain is worse.'), or
    # as a printed question's own heading word ('Assessment is ...', 'Examination is normal.', 'Plan is ...'). A bare
    # 'Pain is worse at night.' is held with it (fail closed: the base holds it too).
    if (token.dep_ in ('nsubj', 'nsubjpass', 'poss')
            and not any(c.dep_ in ('det', 'poss', 'nummod', 'amod', 'compound') for c in token.children)
            and lemma not in SOLE_HEADING_WORDS and text not in SOLE_HEADING_WORDS):
        return False
    # A word that can name a GROUP of people ('her band', 'the community', 'the clinic' for its staff): positively no
    # person only where a group cannot act or accompany - never a subject, possessor, appositive or agent, never the
    # object of with / by / from / beside.
    if lemma in SOLE_COLLECTIVE or text in SOLE_COLLECTIVE:
        if token.dep_ in ('nsubj', 'nsubjpass', 'poss', 'appos', 'agent') or any(
                c.dep_ in ('relcl', 'acl', 'appos') and not _initialism_of_run(c) for c in token.children):
            return False
        if token.dep_ == 'pobj' and _fold(token.head.text) in ('with', 'by', 'from', 'beside', 'alongside'):
            return False
    # A capitalized word in the middle of a sentence may be a name ('lives with Pain'): only inside a run of capitalized
    # known words ('Community Treatment Order').
    if token.text[:1].isupper() and token.i > token.sent.start and not token.text.isupper():
        neighbours = [t for t in (token.doc[token.i - 1] if token.i > 0 else None,
                                  token.doc[token.i + 1] if token.i + 1 < len(token.doc) else None) if t is not None]
        if not any(t.text[:1].isupper() and (_lemma(t) in SOLE_NOUNS or _fold(t.text) in SOLE_NOUNS)
                   and t.pos_ in ('NOUN', 'PROPN') for t in neighbours):
            return False
    return True


#: The printed questions' own heading words a bare subject may be ('Assessment is ...', 'Examination is normal.'): a
#: name is never written so (`_sole_noun_ok`, round 5).
SOLE_HEADING_WORDS = frozenset(('examination', 'exam', 'assessment', 'plan', 'diagnosis', 'impression'))


def _initialism_of_run(token):
    """An initialism in parentheses spelling the capitalized known words right before it: 'Community Treatment Order
    (CTO)'. Nothing else: an initialism can be a role ('her CPN')."""
    doc = token.doc
    if not (token.text.isalpha() and token.text.isupper() and 2 <= len(token.text) <= 6):
        return False
    if not (token.i >= 2 and doc[token.i - 1].text == '(' and token.i + 1 < len(doc) and doc[token.i + 1].text == ')'):
        return False
    run, at = [], token.i - 2
    while at >= 0 and doc[at].text[:1].isupper() and doc[at].is_alpha and len(run) < len(token.text):
        run.insert(0, doc[at]); at -= 1
    return (len(run) == len(token.text) and ''.join(t.text[0] for t in run) == token.text
            and all(_lemma(t) in SOLE_NOUNS or _fold(t.text) in SOLE_NOUNS for t in run))


#: The words that are NOT descriptive (`_sole_reading` 'descriptive', round 5): a noun names its topic through its class,
#: an operator reaches through its reach, a word of time, frequency or side is read apart; only `SOLE_INERT` among the
#: rest states no clinical state. Built once.
_SOLE_NOT_DESCRIPTIVE = (SOLE_INERT | SOLE_NOUNS | SOLE_STATUS | SOLE_RESTRICTED | SOLE_PRESENTED | SOLE_ANSWERS
                         | SOLE_INITIALISMS | SOLE_TIME_WORDS | SOLE_FREQUENCY_ADVERBS | SOLE_FREQUENCY_NOUNS
                         | frozenset(SOLE_SIDES) | frozenset(SOLE_WORD_CLASSES) | SOLE_UNCERTAIN | SOLE_NEGATION
                         | {'patient'} | frozenset().union(*SOLE_OPERATORS.values()))
#: An age written as one word ('45-year-old', '4 years old'): its parts describe no state (`_sole_reading` 'descriptive').
_AGE_WORDS = re.compile(r'\b\d{1,3}[- ]years?[- ]old\b', re.I)
#: Every word the single-patient reading knows (`_sole_reading` 'unknown'); built once.
_SOLE_KNOWN = (SOLE_NOUNS | SOLE_STATUS | SOLE_RESTRICTED | SOLE_NEUTRAL_WORDS | SOLE_PRESENTED | SOLE_ANSWERS
               | SOLE_INITIALISMS | SOLE_TIME_WORDS | SOLE_FREQUENCY_ADVERBS | SOLE_FREQUENCY_NOUNS | frozenset(SOLE_SIDES)
               | frozenset(SOLE_WORD_CLASSES) | SOLE_UNCERTAIN | {'patient'}
               | frozenset().union(*SOLE_OPERATORS.values()))


def _sole_reading(doc, root, *, value_start, colon, age, opener, explicit):
    """One unit's part of the single-patient scope (`sole_patient`). Every value only decides whether the unit may join
    a positively established single-patient note; nothing here releases a unit by itself."""
    label_end = value_start if colon else 0
    tokens = [t for t in doc if not t.is_space]
    anchor_nouns = set()
    anchor = None
    main = next((c for c in root.children if c.dep_ in ('nsubj', 'nsubjpass')), None)
    if age or opener:
        # The presenting unit presents exactly ONE person (refutation round 4, 2026-10-01): the one noun an age
        # describes, a presented noun ('A 45-year-old man ...', 'This is a 30-year-old female ...'). A second
        # age-described noun is a second person ('A 4-year-old girl presents with a 30-year-old man.'), whatever its
        # gender: no anchor, and it then fails the positive noun check below like any other person.
        described = [t for t in doc if _described_by_age(t)]
        if len(described) == 1 and _lemma(described[0]) in SOLE_PRESENTED:
            anchor_nouns = {described[0].i}
        anchor = 'age' if anchor_nouns else None
    elif explicit and main is not None and this_patient(main) and not any(
            c.dep_ in ('compound', 'amod', 'poss', 'appos') for c in main.children):
        anchor = 'explicit'
    nouns_ok = True
    for t in tokens:
        if t.is_punct:
            continue
        if t.pos_ == 'PRON':
            continue
        nominal = t.pos_ in ('NOUN', 'PROPN', 'X') or t.dep_ in SOLE_NOMINAL_DEPS or _misread(t)
        if not nominal:
            continue
        if _initialism_of_run(t):
            continue
        if not _sole_noun_ok(t, anchor_nouns=anchor_nouns, label_end=label_end):
            nouns_ok = False
            break
    genders, bad_pronoun = set(), False
    for t in tokens:
        if t.pos_ != 'PRON' and _fold(t.text) not in SOLE_PERSONAL:
            continue
        text = _fold(t.text)
        if text in SOLE_PERSONAL:
            gender = 'Masc' if text in ('he', 'him', 'his', 'himself') else 'Fem'
            genders.add(gender)
            if text not in SOLE_REFLEXIVE and t.dep_ in ('dobj', 'obj', 'iobj', 'dative', 'pobj', 'attr', 'appos'):
                bad_pronoun = True          # 'She gives her ibuprofen.': a non-reflexive object is somebody else
        elif not (text in SOLE_PRONOUNS or (anchor == 'age' and text == 'this' and t.dep_ == 'nsubj')):
            bad_pronoun = True
        elif text in SOLE_GROUP_PRONOUNS and t.dep_ in ('nsubj', 'nsubjpass', 'poss', 'agent', 'appos'):
            bad_pronoun = True
    # A frame fronted before the subject ('On admission she is on warfarin.', 'Then she ...', 'When asked, ...').
    fronted = False
    if not colon:
        subject = next((c for c in root.children if c.dep_ in ('nsubj', 'nsubjpass', 'expl', 'csubj')), None)
        frontier = subject.i if subject is not None else root.i
        fronted = any(c.i < frontier and c.dep_ in ('prep', 'advmod', 'npadvmod', 'advcl', 'tmod', 'obl', 'mark', 'cc',
                                                     'intj', 'dep', 'meta', 'parataxis', 'ccomp', 'pcomp', 'prt')
                      for c in root.children)
        # ... or opening with a preposition, a subordinator or an adverb whatever the parse made of it ('At the time of
        # the fracture she takes warfarin.' parses with 'At' as its root), or a parse whose root is not its verb.
        opening = next((t for t in tokens if not t.is_punct), None)
        fronted = fronted or bool(opening is not None and opening.pos_ in ('ADP', 'SCONJ', 'ADV', 'CCONJ', 'INTJ'))
        fronted = fronted or (root.pos_ not in ('VERB', 'AUX') and any(
            t.pos_ in ('VERB', 'AUX') and 'Fin' in t.morph.get('VerbForm') for t in tokens))
    sides = {SOLE_SIDES[_fold(t.text)] for t in tokens if _fold(t.text) in SOLE_SIDES
             and (len(t.text) > 1 or t.text in ('L', 'R'))}
    uncertain = '?' in doc.text or any(_fold(t.text) in SOLE_UNCERTAIN or _lemma(t) in SOLE_UNCERTAIN for t in tokens)
    # CURRENT: the unit read as an answer to a question about what is so now. One present-tense clause with a
    # current verb, no modal, every word of time inside a frequency phrase, no subordinate clause but 'as needed' (a
    # bounding clause is returned in `advcl` for the reader to set aside only when it states the destination's own
    # printed time).
    current, advcl = not colon, []
    if current:
        heads = [root] + [c for c in root.children if c.dep_ == 'conj' and c.pos_ in ('VERB', 'AUX')]
        for head in heads:
            finite = [t for t in [head] + [c for c in head.children if c.dep_ in ('aux', 'auxpass')]
                      if 'Fin' in t.morph.get('VerbForm')]
            if (_lemma(head) not in SOLE_CURRENT_VERBS or head.pos_ not in ('VERB', 'AUX')
                    or not finite or any('Past' in t.morph.get('Tense') for t in finite)
                    or any(c.dep_ == 'auxpass' for c in head.children)
                    or any(_lemma(c) in ('have',) and c.dep_ == 'aux' for c in head.children)):
                current = False
            # 'is on warfarin' states a current medication; 'is in line for insulin', 'is under review' do not.
            if _lemma(head) == 'be' and any(
                    c.dep_ == 'prep' and not (_fold(c.text) == 'on' and any(
                        g.dep_ == 'pobj' and (SOLE_CLASSES.get(_lemma(g), frozenset()) & {'medication', 'therapy'}
                                              or (_lemma(g) in ('examination', 'exam') and c.i < head.i))
                        for g in c.children))
                    for c in head.children):
                current = False
        if root.dep_ != 'ROOT' or (main is None and not any(c.dep_ == 'expl' for c in root.children)):
            current = False
        bounding = set()                    # the tokens of a before/after clause the reader judges (`advcl`)
        for t in tokens:
            if t.tag_ == 'MD':
                current = False
            if t.dep_ in ('ccomp', 'xcomp', 'csubj', 'relcl', 'acl', 'parataxis'):
                current = False
            if t.dep_ == 'advcl':
                mark = next((c for c in t.children if c.dep_ == 'mark'), None)
                if mark is not None and _fold(mark.text) == 'as' and _lemma(t) in ('need', 'require', 'direct') \
                        and t.tag_ == 'VBN' and not list(c for c in t.children if c.dep_ not in ('mark', 'punct')):
                    continue
                if (mark is not None and _fold(mark.text) in ('before', 'after') and t.head.i == root.i
                        and not any(c.dep_ == 'advcl' for c in t.children)):
                    advcl.append(mark.idx)
                    bounding |= {x.i for x in t.subtree}
                    continue
                current = False
        for t in tokens:
            text, lemma = _fold(t.text), _lemma(t)
            if t.i in bounding:
                continue                    # inside a bounding clause the reader judges against the destination
            if t.pos_ == 'NUM' and _DATE_LIKE.fullmatch(t.text):
                current = False
            if text in SOLE_FREQUENCY_ADVERBS and t.dep_ == 'advmod':
                continue
            if text not in SOLE_TIME_WORDS and lemma not in SOLE_TIME_WORDS:
                continue
            if lemma in SOLE_FREQUENCY_NOUNS and (
                    any(_fold(c.text) in ('every', 'each', 'a', 'per') and c.dep_ == 'det' for c in t.children)
                    or (t.dep_ == 'pobj' and _fold(t.head.text) == 'at' and lemma in ('night', 'bedtime'))
                    or (t.dep_ == 'pobj' and _fold(t.head.text) == 'in' and lemma in ('morning', 'evening')
                        and any(_fold(c.text) == 'the' for c in t.children))):
                continue
            current = False
    # TOPIC, OPERATORS AND UNKNOWN WORDS (`sole_released`'s independence check). A label's own words count for its
    # topic ('Smoker: No.' is about smoking, 'Allergies: none.' about allergy); a compound or adjectival modifier does
    # not ('drug allergies' is about allergy, 'joint line tenderness' about tenderness).
    classes, reach, unknown, content, doubts, operators = set(), set(), False, set(), set(), set()
    topics = []
    descriptive = False                     # (round 5) a word that may describe a clinical state (`SOLE_INERT`)
    ages = [m.span() for m in _AGE_WORDS.finditer(doc.text)]   # '45-year-old': an age, not a state
    negated = any(_fold(t.text) in SOLE_NEGATION or _lemma(t) in SOLE_NEGATION
                  or (_fold(t.text).startswith('non') and len(t.text) > 5) for t in tokens)
    known = _SOLE_KNOWN
    for t in tokens:
        if t.is_punct or t.is_space or not any(c.isalpha() for c in t.text):
            continue
        text, lemma = _fold(t.text), _lemma(t)
        words = {text, lemma}
        topic_word = t.dep_ not in ('compound', 'amod') and (t.pos_ in ('NOUN', 'PROPN', 'VERB', 'ADJ')
                                                             or t.dep_ in SOLE_NOMINAL_DEPS or _misread(t)
                                                             or bool(words & SOLE_NOUNS))
        if topic_word:
            found = frozenset().union(*(SOLE_CLASSES.get(word, frozenset()) | SOLE_WORD_CLASSES.get(word, frozenset())
                                        for word in words))
            classes |= found
            if found:
                topics.append(found)
            if text.startswith('non') and len(text) > 5:
                classes |= SOLE_CLASSES.get(text[3:].lstrip('-'), frozenset()) | SOLE_WORD_CLASSES.get(text[3:].lstrip('-'), frozenset())
        if ((t.pos_ in ('NOUN', 'PROPN', 'VERB', 'ADJ') or t.dep_ in SOLE_NOMINAL_DEPS or _misread(t)
             or words & SOLE_NOUNS) and t.idx >= label_end
                and lemma != 'patient' and lemma not in SOLE_NEUTRAL_WORDS
                and (t.pos_ not in ('PRON', 'DET', 'NUM') or _misread(t))):
            content.add(lemma)
        if words & SOLE_OPERATORS['key']:
            reach.add('key')
        if (t.idx >= label_end and (t.pos_ in ('ADJ', 'VERB', 'ADV') or _misread(t))
                and not words & _SOLE_NOT_DESCRIPTIVE and not (text.startswith('non') and len(text) > 5)
                and not any(low <= t.idx < high for low, high in ages)):
            descriptive = True
        noun_topic = t.pos_ in ('NOUN', 'PROPN') and bool(words & SOLE_NOUNS)
        # A pronoun standing for something said elsewhere ('She denies this.', 'That was years ago.', 'None of this is
        # current.') points at another line: it may change any of them. Not the presenting 'This is a ...', not a
        # relative pronoun ('a rash that itches').
        if (t.pos_ == 'PRON' and text in ('it', 'its', 'itself', 'this', 'that', 'these', 'those')
                and t.head.dep_ != 'relcl' and not (anchor == 'age' and text == 'this' and t.dep_ == 'nsubj')):
            reach.add('global')
        if not noun_topic:
            if words & SOLE_OPERATORS['global']:
                reach.add('global')
            if text in ('or', 'either') and negated:
                pass                        # 'denies nausea or weakness': a negated list, not a choice
            elif words & SOLE_OPERATORS['class'] or words & SOLE_UNCERTAIN or (text.startswith('non') and len(text) > 5):
                reach.add('class')
                operators.add('negation' if (words & SOLE_NEGATION or (text.startswith('non') and len(text) > 5))
                              else 'other')
                doubts.add(bool(words & SOLE_DOUBT) and not words & (SOLE_OPERATORS['class'] - SOLE_DOUBT)
                           and not (text.startswith('non') and len(text) > 5))
        if t.tag_ == 'MD' and text not in ('will', "'ll", 'wo', 'shall', 'can', 'ca'):
            reach.add('class'); doubts.add(False); operators.add('other')
        if (t.idx < label_end or (t.pos_ in ('PRON', 'NUM', 'DET', 'ADP', 'CCONJ', 'SCONJ', 'PART', 'AUX', 'SYM')
                                  and not _misread(t))
                or t.i in anchor_nouns or _initialism_of_run(t)):
            continue
        if not words & known and not (text.startswith('non') and text[3:].lstrip('-') in known):
            unknown = True
    # A dictated correction ('Make that aspirin.', 'Make it 20 mg.', 'Change that to ibuprofen.') replaces a word of a
    # line it does not name: it may change any answer of the note (self-refutation round 2, 2026-10-01).
    lead = [t for t in tokens if not (t.is_punct or t.is_space)][:2]
    if len(lead) == 2 and _lemma(lead[0]) in ('make', 'change') and _fold(lead[1].text) in ('that', 'it', 'this'):
        reach.add('global')
    # A line that names no topic of its own but negates, ends, restricts, doubts, contrasts or sides something ('Not in
    # the morning.', 'Worse at night instead.', 'Bilateral.', 'Left side.', 'The right knee is also swollen.', 'None.')
    # qualifies a line it does not name: it may change any answer of the note (self-refutation round 2, 2026-10-01).
    # So does an unlabelled line naming no topic, whatever its words: a fragment ('Worse at night.', 'Last week.',
    # 'Every day.', 'Severe.': round 3) and - refutation round 6, L1:F4 - a whole clause ('She has twenty a day.',
    # 'She feels better.'): nothing in it shows what it is about. A labelled value is its label's, and the presenting
    # line is the note's anchor.
    if not classes and (reach & {'class', 'key'} or sides or not (colon or age or opener)):
        reach.add('global')
    # (refutation round 6, L1:F4) A number standing for a noun it does not name ('She has twenty a day.', 'She takes
    # one every morning.', 'She has two every morning with her inhaler.'): what it counts is elided, so the line may be
    # about any answer whatever else it names - its topic is UNKNOWN, fail closed. A number counting its own noun ('20
    # mg', 'twenty cigarettes': the parser's 'nummod'), a date or year ('in 2019') and an age ('30-year-old') name what
    # they count.
    if any(t.idx >= label_end and (t.pos_ == 'NUM' or t.like_num) and t.dep_ not in ('nummod', 'quantmod', 'compound')
           and not _DATE_LIKE.fullmatch(t.text) and not any(low <= t.idx < high for low, high in ages)
           for t in tokens):
        unknown = True
    return {'nouns_ok': nouns_ok, 'genders': frozenset(genders), 'bad_pronoun': bad_pronoun, 'fronted': fronted,
            'classes': frozenset(classes), 'reach': frozenset(reach), 'unknown': unknown, 'descriptive': descriptive,
            'doubt_only': doubts == {True},
            # only a negation among its own operators ('She denies nausea.', 'She does not smoke.', 'a nonsmoker')
            'negation_only': operators <= {'negation'},
            # two topics no one word covers ('He has hypertension and takes lisinopril.': condition and medication)
            # (an allergen is a drug or a substance: allergy with medication is one topic)
            'multi_topic': any(not (a & b) and not ({'allergy'} <= (a | b) and (a | b) <= {'allergy', 'medication'})
                               for i, a in enumerate(topics) for b in topics[i + 1:]),
            # a statement that is whole on its own though it has no object ('She smokes.', 'He drinks.'): an intransitive
            # habit verb with a personal pronoun subject, nothing else in it
            'self_contained': bool(root.pos_ == 'VERB' and _lemma(root) in ('smoke', 'vape', 'drink')
                                   and all(c.dep_ in ('nsubj', 'punct', 'neg', 'aux') for c in root.children)),
            'keys': keys(content),
            'sides': frozenset(sides), 'uncertain': uncertain, 'anchor': anchor,
            'anchor_gender': next(iter({_noun_gender(doc[i]) for i in anchor_nouns} - {None}), None)
                             if len({_noun_gender(doc[i]) for i in anchor_nouns} - {None}) == 1 else None,
            'current': current, 'advcl': tuple(advcl),
            # a presenting line (the age grammar or the opener), whether or not it presents exactly one person
            'presenting': bool(age or opener)}


def sole_patient(units, info, *, subjects, parsed, colon):
    """The unit ids of a note whose single-patient scope is POSITIVELY established (empty otherwise): every unit read,
    the first one presenting the patient (`_sole_reading` 'anchor'), no unit naming or implying anyone else (every
    nominal word known to name no person, no other pronoun, no non-reflexive personal object, no actor reading another
    person), every personal pronoun one gender agreeing with the presented patient, no frame fronted before a subject
    (but a printed question's own subject line: 'On examination there is ...'), at most one side named in the note, and
    nothing uncertain outside an assessment's own line. Read ONLY by the ordinary field-relations reader."""
    if not units:
        return frozenset()
    readings = []
    for unit in units:
        found = info.get(unit['id']) or {}
        sole = found.get('sole')
        if not found.get('readable') or sole is None:
            return frozenset()
        readings.append((unit, found, sole))
    first = readings[0]
    if first[2]['anchor'] is None:
        return frozenset()
    genders, sides = set(), set()
    for index, (unit, found, sole) in enumerate(readings):
        if not sole['nouns_ok'] or sole['bad_pronoun']:
            return frozenset()
        # (self-refutation of round 4) a later line presenting somebody ('50-year-old woman presents with cough.') is a
        # second patient, whatever the actor run made of it: only the first line presents the note's patient
        if index > 0 and sole['presenting']:
            return frozenset()
        # (the presenting opener reads 'A 45-year-old man' as a person; the positive noun check above is what says
        # the note names nobody else, so the presenting unit itself is not refused for it)
        if (found['other_floor'] or found['other']) and not (index == 0 and sole['anchor'] == 'age'):
            return frozenset()
        if sole['fronted'] and not subjects.get(unit['id']):
            return frozenset()
        own = parsed.get(unit['id'])
        topic = (own[0] if own else None) or subjects.get(unit['id'])
        if sole['uncertain'] and topic not in ('assessment', 'impression', 'diagnosis'):
            return frozenset()
        genders |= sole['genders']; sides |= sole['sides']
    anchor_gender = first[2]['anchor_gender']
    if len(genders) > 1 or (anchor_gender and genders and genders != {anchor_gender}) or len(sides) > 1:
        return frozenset()
    return frozenset(unit['id'] for unit in units)


@functools.lru_cache(maxsize=512)
def neutral_field(label, context):
    """Whether a printed question names nobody but the patient: every nominal word of its label and context known to
    name no person (`SOLE_NOUNS`, `SOLE_STATUS`, `SOLE_FIELD_NOUNS`), no personal pronoun but 'you' / 'your'. A question
    under 'Family history', 'Mother' or 'Carer' is not neutral, so no single-patient release answers it."""
    from . import v3_syntax
    text = ' '.join(part for part in (str(label or ''), str(context or '')) if part.strip())
    if not text.strip():
        return True
    parsed = v3_syntax.docs([text[:v3_syntax.MAX_CHARACTERS]])
    if not parsed or parsed[0] is None or len(text) > v3_syntax.MAX_CHARACTERS:
        return False
    history_label = bool(re.fullmatch(r'(?:past (?:medical|surgical) history|history of present illness|history)',
                                      ' '.join(str(label or '').casefold().split()).rstrip(':?')))
    for t in parsed[0]:
        word, lemma = _fold(t.text), _lemma(t)
        if not any(c.isalpha() for c in t.text):
            continue                        # '>', '(', '?': a separator names nobody
        # A question framed in another time ('Previous visit > Medications', 'On admission', 'Discharge medications')
        # does not ask what is so now; only a printed history question names the past as its own subject.
        if ({word, lemma} & SOLE_FIELD_FRAMES) and not (history_label and t.idx < len(str(label or ''))):
            return False
        # (refutation round 4) a content word of time frames the question in another time or a part of the day ('Old
        # medications', 'Night medications', 'Daily medications'): only 'current' / 'present' name the now it reads
        if t.pos_ in ('ADJ', 'ADV', 'VERB', 'NOUN', 'PROPN', 'X') and {word, lemma} & SOLE_FIELD_TIME:
            return False
        # ... and so does a verb that is past, a participle, modal or infinitival ('Medications to start', 'Medications
        # given', 'Medications needed', 'What would ...'): only a present-tense question asks what is so now
        if (t.pos_ in ('VERB', 'AUX') and word not in SOLE_SIDES
                and (t.tag_ in ('VBD', 'VBN', 'MD') or any(c.tag_ == 'TO' for c in t.children))):
            return False
        if t.pos_ == 'PRON':
            if word not in ('you', 'your', 'yours', 'yourself', 'it', 'this', 'that', 'anything', 'all', 'which', 'what',
                            'none', 'nothing', 'there', 'these', 'those'):
                return False
            continue
        if t.pos_ in ('NOUN', 'PROPN', 'X') or t.dep_ in ('nsubj', 'nsubjpass', 'dobj', 'pobj', 'appos', 'poss'):
            if t.is_punct or t.pos_ in ('NUM', 'DET', 'ADP', 'AUX', 'CCONJ', 'SCONJ', 'PART', 'ADJ', 'ADV', 'VERB'):
                pass
            elif not ({word, lemma} & (SOLE_NOUNS | SOLE_STATUS | SOLE_FIELD_NOUNS)) and not _initialism_of_run(t):
                return False
            else:
                continue
        # (refutation round 4, R2-F6) every other content word too: a modifier or verb the lexicons do not know may
        # name somebody else or another time ('Maternal conditions', 'Paternal medications', 'Discontinued
        # medications', 'Declined treatment') - the question is then not positively about the patient now.
        # ('the patient' the parse tags as a modifier, 'Does the patient smoke?', names the patient)
        if (t.pos_ in ('ADJ', 'ADV', 'VERB', 'NOUN', 'PROPN', 'X') and not ({word, lemma} & SOLE_FIELD_KNOWN)
                and not (word == 'patient' and t.i > 0 and _fold(parsed[0][t.i - 1].text) in ('the', 'this'))):
            return False
    return True


#: Words that frame a printed question in another time or encounter (`neutral_field`).
SOLE_FIELD_FRAMES = frozenset((
    'previous previously prior past former formerly earlier initial baseline admission admitted discharge discharged '
    'last pre post historical history ago yesterday future planned intended'
).split())
#: Words of a printed question that name no person ('Clinic visit record', 'History of present illness').
SOLE_FIELD_NOUNS = frozenset((
    'record visit review history illness complaint details information form section question medication medications '
    'allergies allergy other symptoms symptom chief current findings finding care tick notes note summary description '
    'mental health state lifestyle ideation self wellbeing'
).split())
#: Content words that frame a printed question in a time of its own (`neutral_field`, round 4): words of time and
#: frequency, and 'old' / 'new'.
SOLE_FIELD_TIME = ((SOLE_TIME_WORDS | SOLE_FREQUENCY_ADVERBS | SOLE_FREQUENCY_NOUNS
                    | frozenset(SOLE_LEXICON['time'].split()) | frozenset(('old', 'new', 'recent', 'recently')))
                   - frozenset(('current', 'currently', 'present')))
#: Every word a printed question may carry and still be positively about the patient now (`neutral_field`, round 4).
SOLE_FIELD_KNOWN = (SOLE_NOUNS | SOLE_STATUS | SOLE_FIELD_NOUNS | SOLE_NEUTRAL_WORDS | SOLE_FREQUENCY_ADVERBS
                    | frozenset(SOLE_WORD_CLASSES))


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
            'topic_denial_keys': frozenset(), 'surface_keys': frozenset(), 'intention': True, 'sole': None}


# (refutation round 6, 2026-10-01) round 5's three readings for the default path's own holds (D30) are withdrawn with the
# releases they fed, and the default path is the base's again: a line's own present frame (OWN_FRAME: an earlier past
# event may fall inside 'this admission' / 'this reporting period'), a PLAIN pair of lines (`_plain`: any noun passed -
# 'The warfarin is recorded for discontinuation.'), and the parser's syntax-only completeness for a thing subject or the
# patient as object (`_thing_subject`, `_patient_object`: 'The warfarin belongs to the dog.', 'The physiotherapy ended
# last year.' as a plan, 'The apixaban replaces the warfarin.' were adopted). Each was the meaning of a line, which only
# a reader of meaning could supply.


def read(units, groups, *, colon, parsed, subjects, explicit, ages, openers=frozenset()):
    """Per-unit and note-wide actor reading. `openers` (2026-10-01): units opening with the presenting opener with an
    article (`SOLE_OPENER`); read ONLY for the relation floors' `other_floor` and the single-patient scope (`sole`). `explicit`: unit ids whose text opens with an explicit patient subject by
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
        opener = uid in openers
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
                  'other_floor': other_floor, **_floor_reading(words, root, lem, txt),
                  # 2026-10-01: the single-patient scope's reading of this unit (`sole_patient`), relation path only
                  'sole': _sole_reading(doc, root, value_start=value_start, colon=bool(colon.get(uid)),
                                        age=age, opener=opener, explicit=uid in explicit)}
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
