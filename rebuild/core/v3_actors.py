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

⚠️ 2026-09-30, THE ONE PLACE THIS READING RELEASES: the ordinary field-relations contract (the Sonnet 5 ordinary-notes
contract) reads a resolution to the patient as positive patient evidence (`generation.v3_actor_candidates`,
`generation.v3_actor_evidence`, read by `v3_field_relations.read`) - and since refutation round 1 only a CLOSED one
(`_closed_reading`): one settled clause, and for a pronoun or a thing nothing earlier in the note (or in itself) that
could be somebody else, read by structure rather than by the absence of a listed danger. There, the model's per-unit
relations say what else is independent, and `generation.v3_relation_causes` keeps this module's holds for the unit.
The default path reads it exactly as before (its run reads an age opener with its article as another person; the
relation path's run, `relation_units`, reads it as the patient).

STATED RESIDUALS (none of them releases anything on the default path): a sentence whose subject is the EXPLICIT patient
and that names another person only as an object or beneficiary ('The patient takes warfarin for her husband.') is not
held by this reader; a person noun outside the lexicon and a given name without a title read as things when they stand
alone ('The sherpa takes warfarin.', 'Jane is subject to a CTO.'). On the relation path the closed reading withholds
the evidence of both (a thing must name its question or the complaint; a capitalized name or an unlisted subject
leaves every later pronoun unresolved); its own residual is a given name written in lower case without a determiner as
the object of a verb ('She visits jane daily. She takes warfarin.'), which the pinned tagger reads as a common noun, like
a medicine ('takes lisinopril'), and English subject continuity reads as the patient.

Refutation round 2 (2026-09-30): who a later pronoun may stand for is read by what is SAFE ('antecedents': every noun but
a bare, plural, time, patient or institution noun, `_referring`), the relation path's evidence must be a SETTLED
predicate (`_settled_predicate`), and only the note's FIRST age presentation presents the patient on the relation path.
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


# ─── 2026-09-30: readings for the ordinary field-relations contract (`generation.v3_actor_candidates`,
# `generation.v3_relation_causes`). Like everything above, each only ever HOLDS: a word below may keep a unit from
# counting as the patient's, or make it hold another unit; none of them makes anything an answer.
#: Words that hedge the statement they are in ('The patient possibly has right knee pain.').
HEDGES = frozenset(('possible possibly probable probably likely unlikely maybe perhaps suspect suspected query queried '
                    'questionable presumed presumably apparent apparently seemingly uncertain unclear unsure '
                    'unconfirmed potential potentially').split())
#: Modal auxiliaries that make a statement hypothetical ('She may take ibuprofen.'); 'will' and 'can' do not.
HEDGE_MODALS = frozenset(('may', 'might', 'could', 'would', 'should'))
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

# ─── 2026-09-30, refutation round 1: the CLOSED reading of the ordinary field-relations contract ───────────────────
# The relation path's NEW patient evidence (a pronoun, a thing, an article opener, a statement carrying a word the
# UNSETTLED list names) is POSITIVE: `generation.v3_actor_candidates` gives it only where the structure read below
# establishes it, never because a list of dangers found nothing in the sentence. A given name, a person noun outside
# `PERSON_NOUNS`, a seeming verb, a condition word outside `BOUNDING_MARKERS` all read as NOTHING to such a list, and
# each one was measured releasing another person's statement, an intention or a condition (round 1: L1:F1-F6). So each
# list below names what is SAFE, and whatever it does not name withholds the evidence: an over-hold costs a retype, a
# miss costs a wrong record. None of it is read by the default path.
#: Adverbs a settled statement may carry. Anything else ('apparently', 'reportedly', 'previously', 'no longer', 'now',
#: 'before' in 'has taken methadone before') withholds the evidence.
SETTLED_ADVERBS = frozenset(('ago', 'currently', 'daily', 'twice', 'weekly', 'monthly', 'nightly', 'annually', 'also',
                             'very', 'mildly', 'moderately', 'severely', 'slightly', 'markedly'))
#: Dosing idioms an 'as' clause may state ('She takes ibuprofen as needed.'): with a before/after clause stating the
#: destination's own printed time (decided per destination), the only adverbial clause a settled statement may carry.
DOSING_CLAUSES = frozenset(('needed', 'required', 'directed', 'prescribed'))
#: Dependencies a settled statement never has: a clausal complement ('is going to be placed', 'appears to be allergic',
#: 'Provided her INR is stable, ...'), a relative clause, and the parser's unattached or loose relations.
UNSETTLED_DEPS = frozenset(('xcomp', 'ccomp', 'csubj', 'csubjpass', 'parataxis', 'relcl', 'dep', 'intj', 'meta',
                            'preconj'))
#: The only modals a settled statement may carry, and only for a Plan ('She will follow up in six weeks.').
FUTURE_MODALS = frozenset(('will', 'shall'))
#: Prepositions of place, part and source: an object after one is not a candidate for whom a pronoun stands for
#: ('pain in her right knee', 'tenderness over the lateral epicondyle', 'removal of the sutures').
LOCATIVE_PREPS = frozenset(('in', 'on', 'over', 'at', 'under', 'around', 'near', 'above', 'below', 'behind', 'across',
                            'along', 'within', 'through', 'into', 'onto', 'of', 'from', 'beside', 'between', 'inside',
                            'outside'))
#: Words that bound a statement in time as a preposition or an adverb ('took warfarin before her move', 'has taken
#: methadone before'). Only a presentation opener's own time ('... for three weeks after a fall') and a before/after
#: CLAUSE stating the destination's printed time (decided per destination) are settled.
TEMPORAL_WORDS = frozenset(('before', 'after', 'since', 'until', 'till', 'prior', 'during', 'following'))
#: Capitalized words that are dates, not names.
CALENDAR_WORDS = frozenset(('january february march april may june july august september october november december '
                            'monday tuesday wednesday thursday friday saturday sunday').split())
#: Words by which a statement denies, ends or changes what it names (besides a 'not'/'no' dependency and a 'non-' or
#: 'ex-' word). HOLD-ONLY (`generation.v3_relation_causes`, SAME TOPIC, POLARITY): a statement carrying one and
#: sharing a word with a pronoun or thing answer holds it, whichever way round.
POLARITY_WORDS = frozenset(('no', 'not', 'never', 'none', 'nothing', 'nil', 'without', 'nkda', 'deny', 'denies',
                            'denied', 'stop', 'stopped', 'quit', 'cease', 'ceased', 'discontinue', 'discontinued',
                            'withdraw', 'withdrawn', 'switch', 'switched', 'former', 'formerly', 'previously', 'anymore',
                            'longer', 'negative', 'absent', 'resolved', 'ex', 'error', 'wrong', 'incorrect', 'ignore',
                            'disregard', 'unconfirmed', 'amended', 'amendment', 'correction', 'corrected'))
#: Verbs by which a statement ends what it names ('Methadone was stopped.'): HOLD-ONLY, read against a labelled answer's
#: value (`generation.v3_relation_causes`, L2:R2-6).
CESSATION_VERBS = frozenset(('stop', 'discontinue', 'cease', 'withdraw', 'quit', 'halt', 'suspend'))
#: Verbs presenting the patient's complaint and the prepositions introducing it ('presents with cough', 'seen for
#: headaches', 'complains of pain'). A noun there without 'the', 'this', 'that' or a possessive is the complaint.
PRESENTATION_VERBS = {'present': ('with', 'for'), 'see': ('for',), 'complain': ('of',)}
#: 'Community Treatment Order (CTO)': capitalized words spelled out by the initialism after them name an institution.
_INITIALISM = re.compile(r"((?:[A-Z][A-Za-z]*[ -]){1,7}[A-Z][A-Za-z]*) \(([A-Z]{2,})\)")

# ─── 2026-09-30, refutation round 2: what the closed reading still read as NOTHING, now read by what is SAFE ────────
# Round 2 (L1:RR1-1, RR1-2, RR1-5) found the round-1 reading still listing DANGERS in two places: who a later pronoun may
# stand for was a list of reference shapes ('a newborn', 'the house of the au pair', 'her childminder' and a misparsed
# 'the housekeeper weekly' were none of them), and the closed clause admitted any verb ('She needs insulin.', 'She is due
# a flu vaccine.', 'A community treatment order is planned.'). Both are inverted here; each list names what is SAFE.
#: Determiners by which a noun REFERS to somebody or something particular ('a newborn', 'the housekeeper'); with a
#: possessive ('her childminder') such a noun may be whom a later pronoun stands for. 'No' refers to nothing.
REFERRING_DETERMINERS = frozenset('a an the this that these those another some any each every either neither'.split())
#: Prepositions of the presentation's own time ('... presents with right knee pain after a twisting injury'): the noun
#: they govern directly (with its compounds) is an event, not somebody; a phrase inside it is read as it is.
PRESENTATION_TIME_PREPS = frozenset(('after', 'since', 'following', 'during'))
#: Verbs whose present statement about the patient is SETTLED - a state or a habit ('takes', 'has', 'is', 'attends',
#: 'denies', 'Examination shows ...'). Any other verb ('needs', 'requests', 'declines', 'starts ... on Monday',
#: 'restarts') withholds the evidence: it may state an intention, a request or a change.
SETTLED_STATE_VERBS = frozenset(('be have take use smoke drink vape deny attend show reveal demonstrate complain '
                                 'experience suffer feel describe see wake').split())
#: Verbs of an event, settled only in the past ('The headaches started two months ago.') or, for a Plan, with 'will'
#: ('She will follow up in six weeks.', decided per destination).
SETTLED_EVENT_VERBS = frozenset('start begin follow return develop occur'.split())
#: Prepositions an adjective complement of a settled copula may take ('allergic to penicillin', 'worse in the morning',
#: 'tender over the epicondyle'); anything else ('due a flu vaccine', 'ready for discharge', 'eligible for') withholds.
SETTLED_COMPLEMENT_PREPS = frozenset(('to', 'in', 'on', 'at', 'of', 'with', 'over', 'around'))
#: Prepositions a copula may take as its own predicate ('is on warfarin', 'On examination there is ...').
SETTLED_COPULA_PREPS = frozenset(('on', 'in', 'at'))
#: Determiners and words by which a statement denies a whole CLASS ('no medicines', 'any blood thinners', 'never').
QUANTIFIED_DENIALS = frozenset(('no', 'any', 'neither'))
QUANTIFIED_DENIAL_WORDS = frozenset(('never', 'none', 'nothing', 'nobody', 'nil', 'nowhere', 'nor'))
#: Endings of a noun naming whoever DOES something ('smoker', 'babysitter', 'visitor', 'therapist', 'physician'): such
#: a subject is never set aside as a printed question's name.
AGENTIVE_ENDINGS = ('er', 'or', 'ist', 'ian')


def _referring(token):
    """Whether a noun refers to somebody or something particular: a referring determiner or a possessive on it or, for
    a compound or modifier ('the housekeeper weekly' parsed as a compound of 'weekly'), on the noun it modifies."""
    node = token
    while True:
        if any((child.dep_ == 'det' and _fold(child.text) in REFERRING_DETERMINERS) or child.dep_ == 'poss'
               or (child.dep_ == 'nummod' and _fold(child.text) == 'one') for child in node.children):
            return True
        if node.dep_ in ('compound', 'amod', 'nmod') and node.head.i != node.i:
            node = node.head
            continue
        return False


def _settled_predicate(root, words):
    """The SETTLED predicate of the relation path's new evidence (refutation round 2, L1:RR1-5): no passive ('is
    planned', 'are reproduced here'), no date by the calendar ('on Monday'), no past-time word in a present statement
    ('She is on warfarin in 2019.'), and every clause head a settled verb: a state verb (`SETTLED_STATE_VERBS`, a copula
    only with an attribute, an adjective whose only phrases are `SETTLED_COMPLEMENT_PREPS` ones, or its own
    `SETTLED_COPULA_PREPS` phrase) or an event verb in the past or with 'will'/'shall' (`SETTLED_EVENT_VERBS`)."""
    if any(t.dep_ in ('auxpass', 'nsubjpass', 'csubjpass') for t in words):
        return False
    if any(_fold(t.text) in CALENDAR_WORDS or _lemma(t) in CALENDAR_WORDS for t in words if t.pos_ != 'AUX'):
        return False
    past_word = any(_fold(t.text) in PAST_TIME_WORDS or (t.pos_ == 'NUM' and _YEAR.fullmatch(t.text)) for t in words)
    if past_word and _tense(root) != 'past':
        return False
    clauses = [root] + [child for child in root.children if child.dep_ == 'conj' and child.pos_ in ('VERB', 'AUX')]
    for clause in clauses:
        if clause.pos_ not in ('VERB', 'AUX'):
            # A noun-read clause ('She has epilepsy.' parses 'epilepsy' as the head, 'has' as its auxiliary) is settled
            # only through a settled state auxiliary.
            helpers = [c for c in clause.children if c.dep_ in ('aux', 'auxpass') and c.tag_ != 'MD']
            if not helpers or any(_lemma(c) not in SETTLED_STATE_VERBS for c in helpers):
                return False
            continue
        lemma = _lemma(clause)
        if lemma == 'be':
            for child in clause.children:
                if child.dep_ == 'acomp' and any(
                        grand.dep_ not in ('advmod', 'prep', 'conj', 'cc', 'punct')
                        or (grand.dep_ == 'prep' and _fold(grand.text) not in SETTLED_COMPLEMENT_PREPS)
                        for grand in child.children):
                    return False
                if child.dep_ == 'prep' and _fold(child.text) not in SETTLED_COPULA_PREPS:
                    return False
                if child.dep_ in ('dobj', 'dative', 'oprd', 'npadvmod', 'agent'):
                    return False
            continue
        if lemma in SETTLED_STATE_VERBS:
            continue
        will = any(child.tag_ == 'MD' and _fold(child.text) in FUTURE_MODALS for child in clause.children)
        if lemma in SETTLED_EVENT_VERBS and (_tense(clause) == 'past' or will):
            continue
        return False
    return True


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
    verbless or noun-read statement: 'The patient smokes.' parses as a noun phrase)."""
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


def _predicates(root):
    """What a statement asserts or denies, one record per predicate: (head keys, negated, tense, complement keys,
    coordinated). A copula's predicates are its adjectival or nominal complements and its prepositional phrases (the
    preposition is the head: 'is on methadone', 'is off methadone'); any other clause's is its head word (a verb, or the
    noun of a noun-read statement). Negation is the clause's or the predicate's own 'not'/'never' or a 'no' determiner; a
    conjunct joined by 'but' or 'yet' does not inherit it ('not psychotic but suicidal' asserts suicidal). Used only to
    HOLD (`generation.v3_relation_causes`)."""
    clauses = [root] + [child for child in root.children if child.dep_ == 'conj' and child.pos_ in ('VERB', 'AUX')]
    records = []
    for clause in clauses:
        negated = any(child.dep_ == 'neg' or (child.dep_ == 'det' and _fold(child.text) == 'no')
                      for child in clause.children)
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
            own = negated or any(child.dep_ == 'neg' or (child.dep_ == 'det' and _fold(child.text) == 'no')
                                 for child in token.children if token is not clause)
            # 'has no allergies', 'takes no medication': the object's 'no' denies the predicate's claim about it.
            own = own or any(child.dep_ in ('dobj', 'attr') and any(grand.dep_ == 'det' and _fold(grand.text) == 'no'
                                                                  for grand in child.children)
                             for child in token.children)
            chain = [(token, own)]
            contrast = any(child.dep_ == 'cc' and _fold(child.text) in ('but', 'yet') for child in token.children)
            for conj in (child for child in token.children if child.dep_ == 'conj'):
                chain.append((conj, any(child.dep_ == 'neg' for child in conj.children) or (own and not contrast)))
            for item, item_negated in chain:
                complement, coordinated = _complement(item)
                records.append((keys({_lemma(item)}), item_negated, tense, complement | extra, coordinated))
    return tuple(records)


#: Words a complete statement never ends on (read with the parser's own tag: 'The patient is subject to the.').
DANGLING_WORDS = frozenset('the a an to of and or but with for in on at by from into than as nor'.split())


def _dangling(words):
    """Whether a statement stops on a function word (by its tag or its spelling): it is not complete. Only HOLDS."""
    last = next((t for t in reversed(words) if not t.is_punct and not t.is_space), None)
    return last is None or last.pos_ in ('CCONJ', 'SCONJ', 'ADP', 'DET', 'AUX', 'PART') or _fold(last.text) in DANGLING_WORDS


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


def _under_denial(token):
    """Whether a coordination sits inside what a statement denies: under a word with a 'not'/'no' dependent, or inside
    the object of 'deny' ('She denies visual changes, nausea, or weakness.'; 'is not on diazepam or methadone')."""
    node = token
    while True:
        if any(child.dep_ == 'neg' or (child.dep_ == 'det' and _fold(child.text) == 'no') for child in node.children):
            return True
        if node.dep_ in ('dobj', 'xcomp', 'ccomp') and _lemma(node.head) == 'deny':
            return True
        if node.head.i == node.i:
            return False
        node = node.head


def _name_token(token, institutions):
    """A capitalized proper noun that may name a person ('Jane', 'Tom Brown', 'Maria'): the tagger's PROPN, spelled
    with a capital and then a small letter, not a date word and not inside an institution spelled out by its initialism
    ('a Community Treatment Order (CTO)'). The pinned tagger also tags 'lisinopril', 'zigzag' and 'MRI' PROPN; lower-case
    and all-capital spellings are not read as names here."""
    text = token.text
    return (token.pos_ == 'PROPN' and len(text) > 1 and text[0].isupper() and text[1].islower()
            and _fold(text) not in CALENDAR_WORDS and not any(low <= token.idx < high for low, high in institutions))


def _closed_reading(unit, doc, root, words, main, subjects_tok, age, presented):
    """The CLOSED reading of one parsed unit (2026-09-30, refutation round 1; see `SETTLED_ADVERBS` and what follows it).
    Read only by the ordinary field-relations contract (`generation.v3_actor_candidates`, `v3_actor_evidence`,
    `v3_relation_causes`); none of it releases anything by itself.

      'closed': one settled clause - no clausal complement or relative clause (`UNSETTLED_DEPS`), no adverbial clause
          but a dosing 'as needed' or a before/after clause of the root (decided per destination), no subordinating
          word outside those, no modal but 'will'/'shall', no adverb outside `SETTLED_ADVERBS`, no infinitival 'to', no
          'or' outside a denial, no complex preposition ('in the event of a relapse', 'for removal of'), and no
          temporal preposition or adverb (`TEMPORAL_WORDS`) except a presentation opener's own time;
      'bound_markers': offsets of the before/after markers of the root's adverbial clauses;
      'future': a 'will'/'shall' modal (decided per destination);
      'refs': who else a later pronoun or thing may stand for - (kind, keys) for a capitalized name ('name'), a singular
          noun subject ('subject'), a singular object of 'with' or 'by' ('companion'), and a singular noun with 'the',
          'this', 'that' or a possessive outside a place or part phrase ('definite'); never the patient, the presented
          age noun or a personal pronoun (form words, time words and the complaint are set aside by the caller);
      'subject_keys': the main subject's head noun's keys; 'complaint_keys': the keys of a presentation's complaint
          ('seen for headaches', 'presents with right knee pain'), a noun there with no article, demonstrative or
          possessive (the presentation's own complaint nouns are never 'refs');
      'polar': a word that denies, ends or changes what the statement names (`POLARITY_WORDS`, a 'not'/'no'
          dependency, a 'non-'/'ex-' word); 'coordinated': two verbs of one clause ('has hypertension and takes
          lisinopril'); 'fragment': no subject and no expletive; 'no_denial_keys': the head noun's keys of a verbless
          'No ...' denial ('No known drug allergies.');
      'ceased_keys': what a cessation verb stops ('Methadone was stopped.', 'She stopped the methadone.');
          'topic_denial_keys': the modifiers of what a negated clause denies having when nothing more specific follows
          it ('She has never had an allergic reaction.': allergic). Both only HOLD a labelled answer (L2:R2-6)."""
    marks = [t for t in words if t.dep_ == 'mark']
    bound_markers = {t.i for t in marks if _fold(t.text) in ('before', 'after') and t.head.dep_ == 'advcl'
                     and t.head.head.i == root.i}
    dosing = {t.i for t in words if t.dep_ == 'advcl' and _fold(t.text) in DOSING_CLAUSES and t.head.i == root.i
              and [(_fold(c.text), c.dep_) for c in t.children] == [('as', 'mark')]}
    presentation = age or (main is not None and this_patient(main) and _lemma(root) in PRESENTATION_VERBS)
    loose_or = any(t.dep_ == 'cc' and _fold(t.text) in ('or', 'nor') and not _under_denial(t.head) for t in words)
    complex_prep = any(t.dep_ == 'prep' and _fold(t.text) != 'of'
                       and any(g.dep_ == 'pobj' and any(c.dep_ == 'prep' and _fold(c.text) == 'of' for c in g.children)
                               for g in t.children) for t in words)
    temporal = any(_fold(t.text) in TEMPORAL_WORDS and t.i not in bound_markers for t in words) and not presentation
    closed = not (
        any(t.dep_ in UNSETTLED_DEPS for t in words)
        or any(t.dep_ == 'advcl' and t.i not in dosing and not any(c.i in bound_markers for c in t.children)
               for t in words)
        or any(t.i not in bound_markers and t.head.i not in dosing for t in marks)
        or any(t.tag_ == 'MD' and _fold(t.text) not in FUTURE_MODALS for t in words)
        or any(t.dep_ == 'advmod' and _fold(t.text) not in SETTLED_ADVERBS for t in words)
        or any(t.tag_ == 'TO' and t.dep_ == 'aux' for t in words)
        or loose_or or complex_prep or temporal)
    institutions = [(m.start(1), m.end(1)) for m in _INITIALISM.finditer(unit['quote'])
                    if ''.join(w[0] for w in re.split(r'[ -]', m.group(1)) if w).upper() == m.group(2)]
    # The presentation's complaint ('seen for headaches', 'presents with right knee pain', 'presents with a rash'): its
    # nouns are this unit's complaint, not somebody a pronoun may stand for. Only a BARE one (no article, demonstrative
    # or possessive) is the complaint a later thing may name ('The headaches started ...'): 'presents with an au pair'
    # and then 'The au pair reports a cough.' must not read the au pair as the complaint.
    complaint, complaint_tokens = set(), set()
    for verb in words:
        allowed = PRESENTATION_VERBS.get(_lemma(verb)) if verb.pos_ in ('VERB', 'AUX') else None
        if not allowed or not presentation:
            continue
        for prep in verb.children:
            if prep.dep_ != 'prep' or _fold(prep.text) not in allowed:
                continue
            for obj in (g for g in prep.children if g.dep_ == 'pobj'):
                for t in obj.subtree:
                    if (t.pos_ in ('NOUN', 'PROPN') and not names_person(t) and not names_carer(t)
                            and not _name_token(t, institutions)):
                        complaint_tokens.add(t.i)
                        if not any(c.dep_ in ('det', 'poss') for c in t.children):
                            complaint.add(_lemma(t))
    refs = []
    for t in words:
        if (t.i in presented or t.i in complaint_tokens or t.pos_ not in ('NOUN', 'PROPN') or this_patient(t)
                or t.is_stop or not t.text[:1].isalpha()):
            continue
        key = keys({_lemma(t), _fold(t.text)})
        if _name_token(t, institutions):
            refs.append(('name', key))
            continue
        if 'Plur' in t.morph.get('Number') or not key:
            continue
        if t.dep_ in ('nsubj', 'nsubjpass') or (t.dep_ == 'conj' and t.head.dep_ in ('nsubj', 'nsubjpass')):
            refs.append(('subject', key))
        elif t.dep_ == 'pobj' and _fold(t.head.text) in ('with', 'by'):
            refs.append(('companion', key))
        elif (any((c.dep_ == 'det' and _fold(c.text) in ('the', 'this', 'that')) or c.dep_ == 'poss' for c in t.children)
              and not (t.dep_ == 'pobj' and _fold(t.head.text) in LOCATIVE_PREPS)):
            refs.append(('definite', key))
    # Refutation round 2 (L1:RR1-1, RR1-2): WHO A LATER PRONOUN OR THING MAY STAND FOR, read by what is SAFE. Every noun
    # of the unit's value is somebody a later pronoun may stand for, unless it is the patient or the noun an age
    # presentation describes, a plural (never 'he' or 'she'), a word of time, inside an institution spelled out by its
    # initialism, the direct object of the presentation's own time phrase ('after a twisting injury'), or BARE - no
    # referring determiner or possessive on it or on the noun it modifies ('She denies nausea or weakness.', 'She takes
    # ibuprofen.'). A capitalized name, a singular subject and an object of 'with'/'by' are someone whatever their
    # article. So 'a newborn', 'the housekeeper', 'the house of the au pair', 'from the babysitter' and the presentation's
    # 'her childminder' (and, over-holding, its 'a rash') are all someone. (kind, keys, agentive) each.
    time_tokens = set()
    if presentation:
        for verb in words:
            if verb.pos_ not in ('VERB', 'AUX') or _lemma(verb) not in PRESENTATION_VERBS:
                continue
            for prep in (c for c in verb.children if c.dep_ == 'prep' and _fold(c.text) in PRESENTATION_TIME_PREPS):
                for obj in (g for g in prep.children if g.dep_ == 'pobj'):
                    time_tokens.add(obj.i)
                    time_tokens.update(t.i for t in obj.subtree if t.dep_ in ('compound', 'amod', 'det', 'nummod')
                                       and t.head.i in time_tokens | {obj.i})
    antecedents = []
    for t in words:
        if (t.pos_ not in ('NOUN', 'PROPN') or t.i in presented or this_patient(t) or t.is_stop
                or not t.text[:1].isalpha() or t.i in time_tokens or (age and _described_by_age(t))
                or any(low <= t.idx < high for low, high in institutions)):
            continue
        key = keys({_lemma(t), _fold(t.text)})
        agentive = _fold(t.text).endswith(AGENTIVE_ENDINGS) or _lemma(t).endswith(AGENTIVE_ENDINGS)
        if _name_token(t, institutions):
            antecedents.append(('name', key, agentive))
            continue
        if 'Plur' in t.morph.get('Number') or not key:
            continue
        # A copula's attribute is its own subject again ('She is a nonsmoker.'), unless the subject is an expletive
        # ('There is a housekeeper ...' names somebody new).
        if (t.dep_ == 'attr' and _lemma(t.head) == 'be'
                and any(c.dep_ in ('nsubj', 'nsubjpass') for c in t.head.children)):
            continue
        if t.dep_ in ('nsubj', 'nsubjpass') or (t.dep_ == 'conj' and t.head.dep_ in ('nsubj', 'nsubjpass')):
            antecedents.append(('subject', key, agentive))
        elif t.dep_ == 'pobj' and _fold(t.head.text) in ('with', 'by'):
            antecedents.append(('companion' if t.i not in complaint_tokens or _referring(t) else 'bare', key, agentive))
        elif _referring(t):
            antecedents.append(('object', key, agentive))
    antecedents = tuple(entry for entry in antecedents if entry[0] != 'bare')
    # A thing's own subject modified by a phrase naming somebody ('The headaches of the au pair ...', 'The cough in the
    # housekeeper ...'): a referring or named noun under a preposition inside its subject (or an existential's pivot).
    pivot = main if main is not None else next((c for c in root.children if c.dep_ == 'attr'), None)
    subject_modifiers = bool(pivot is not None and any(
        t.pos_ in ('NOUN', 'PROPN') and t.i != pivot.i and (_referring(t) or _name_token(t, institutions))
        and any(a.dep_ == 'prep' for a in t.ancestors if a.i in {s.i for s in pivot.subtree})
        for t in pivot.subtree))
    polar = any(t.dep_ == 'neg' or (t.dep_ == 'det' and _fold(t.text) == 'no')
                or _fold(t.text) in POLARITY_WORDS or _lemma(t) in POLARITY_WORDS
                or (_fold(t.text).startswith('non') and len(t.text) >= 6 and _fold(t.text) not in ('none', 'nonsense'))
                or _fold(t.text).startswith('ex-') for t in words)
    # The subject's HEAD only: 'The clinic cleaner attends every week.' names a cleaner, not the clinic.
    subject_keys = keys({_lemma(main)}) if main is not None else frozenset()
    # Every word of the value by its spelling and lemma, whatever the tagger calls it ('She will start amitriptyline'
    # tags the drug a preposition), but light verbs; and its TOPIC words - nouns and words the tagger could not place.
    # Both only HOLD (`generation.v3_relation_causes`, SAME TOPIC).
    surface = {w for t in words if t.is_alpha and not t.is_stop and _lemma(t) not in LIGHT_VERBS
               and _lemma(t) != 'patient' for w in (_lemma(t), _fold(t.text))}
    topic = {w for t in words if t.is_alpha and not t.is_stop and _lemma(t) != 'patient'
             and t.pos_ in ('NOUN', 'PROPN', 'X', 'ADP', 'SYM') for w in (_lemma(t), _fold(t.text))}
    return {'closed': closed, 'bound_markers': frozenset(t.idx for t in doc if t.i in bound_markers),
            'future': any(t.tag_ == 'MD' and _fold(t.text) in FUTURE_MODALS for t in words),
            'antecedents': antecedents, 'subject_modifiers': subject_modifiers,
            # a denial by a quantifier or a negation ('She takes no medicines.', 'She has had no pain for a month.',
            # 'She is not anticoagulated.', 'She has never smoked.'): it may cover another statement's topic by its class
            'quantified_denial': any((t.dep_ == 'det' and _fold(t.text) in QUANTIFIED_DENIALS) or t.dep_ == 'neg'
                                     or _fold(t.text) in QUANTIFIED_DENIAL_WORDS for t in words),
            # a cessation with nothing named as what ends ('The patient quit five years ago.', 'She gave up.'): it
            # leans on another line for what it stops
            'bare_cessation': bool((_lemma(root) in CESSATION_VERBS or (_lemma(root) == 'give' and any(
                c.dep_ == 'prt' and _fold(c.text) == 'up' for c in root.children)))
                and not any(c.dep_ in ('dobj', 'obj', 'xcomp', 'ccomp', 'nsubjpass') for c in root.children)),
            'settled': _settled_predicate(root, words), 'surface_keys': keys(surface), 'topic_keys': keys(topic),
            'passive': any(t.dep_ in ('auxpass', 'nsubjpass', 'csubjpass') for t in words),
            'refs': tuple(refs),
            'subject_keys': subject_keys, 'complaint_keys': keys(complaint), 'polar': polar,
            'coordinated': any(child.dep_ == 'conj' and child.pos_ in ('VERB', 'AUX') for child in root.children),
            'fragment': main is None and not any(t.dep_ == 'expl' for t in doc),
            'ceased_keys': (keys({_lemma(t) for c in root.children if c.dep_ in ('nsubj', 'nsubjpass', 'dobj')
                                  for t in c.subtree if t.pos_ in CONTENT})
                            if _lemma(root) in CESSATION_VERBS else frozenset()),
            'topic_denial_keys': (keys({_lemma(m) for c in root.children if c.dep_ in ('dobj', 'attr')
                                        and not any(g.dep_ == 'prep' for g in c.children)
                                        for m in c.children if m.dep_ in ('amod', 'compound')})
                                  if any(c.dep_ == 'neg' for c in root.children) else frozenset()),
            # a verbless 'No ...' denial ('No known drug allergies.'): its head noun's keys, which may name a question
            'no_denial_keys': (keys({_lemma(root)} | {_lemma(c) for c in root.children if c.dep_ == 'compound'})
                               if main is None and root.pos_ in ('NOUN', 'PROPN')
                               and any(c.dep_ == 'det' and _fold(c.text) == 'no' for c in root.children)
                               else frozenset())}


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
            'hedged': True, 'habitual': True, 'past_time': True, 'dependent': False, 'claim_keys': frozenset(),
            'negated_keys': frozenset(), 'main_patient': False, 'predicates': (),
            'dangling': True, 'nominal_keys': frozenset(), 'main_lemma': None, 'finite_past': True,
            # the closed reading (`_closed_reading`): an unread unit is never settled, and it is a fragment
            'closed': False, 'bound_markers': frozenset(), 'future': False,
            'refs': (('unread', frozenset()),), 'subject_keys': frozenset(), 'complaint_keys': frozenset(),
            'antecedents': (('unread', frozenset(), False),), 'subject_modifiers': True, 'settled': False,
            'quantified_denial': True, 'passive': True, 'bare_cessation': True,
            'surface_keys': frozenset(), 'topic_keys': frozenset(),
            'polar': True, 'coordinated': False, 'fragment': True, 'no_denial_keys': frozenset(),
            'ceased_keys': frozenset(), 'topic_denial_keys': frozenset()}


def read(units, groups, *, colon, parsed, subjects, explicit, ages, relation_ages=frozenset()):
    """Per-unit and note-wide actor reading. `explicit`: unit ids whose text opens with an explicit patient subject by
    the deterministic source grammar (`EXPLICIT_PATIENT_SUBJECT`, the age presentation `ages`). `groups` (paragraphs)
    is accepted for the caller's signature and NOT used: the run is the note's. Returns {'units': {id: info},
    'resolved': {id: state}, 'gender': the note's patient gender (None, 'Masc', 'Fem' or 'conflict')}, and the same
    three for the ordinary field-relations contract ('relation_units', 'relation_resolved', 'relation_gender'), where the
    units in `relation_ages` (an age opener with its article, 'A 45-year-old man presents with cough.') present the
    patient too. Without such a unit they are the very same objects; the parse is shared either way (2026-09-30,
    L3:R3-4: the default path keeps reading that opener's noun as another person, exactly as on 43fcf214)."""
    from . import v3_syntax
    texts = [unit['quote'] for unit in units]
    parsed_docs = v3_syntax.docs(texts) if len(units) <= MAX_UNITS else None

    def unit_info(index, unit, explicit, ages):
        uid = unit['id']
        doc = parsed_docs[index] if parsed_docs is not None else None
        if doc is None or len(list(doc.sents)) == 0:
            return _unread(parsed_docs is None, unit['quote'])
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
        # 2026-09-30 (hold-only; `generation.v3_actor_candidates`, `generation.v3_relation_causes`): a hedge or a
        # hypothetical modal in the statement; a habit that ended ('used to', 'formerly'); a word dating it to the past;
        # whether it DEPENDS on what came before it (it points back, opens with a connective, has no content word, or
        # is a clause with no complement whose subject is absent or a personal pronoun: 'Stopped last month.', 'She quit
        # last month.'); what it claims and what it negates; whether its main subject is the explicit patient.
        hedged = (any(_lemma(t) in HEDGES or _fold(t.text) in HEDGES or (t.tag_ == 'MD' and _fold(t.text) in HEDGE_MODALS)
                      for t in words) or unit['quote'].rstrip().endswith('?'))
        habitual = (any(_lemma(t) == 'use' and any(c.dep_ == 'xcomp' and any(a.dep_ == 'aux' and _fold(a.text) == 'to'
                                                                            for a in c.children) for c in t.children)
                        for t in words)
                    or any(_fold(t.text) in FORMER_WORDS for t in words))
        past_time = any(_fold(t.text) in PAST_TIME_WORDS or (t.pos_ == 'NUM' and _YEAR.fullmatch(t.text)) for t in words)
        root_subjects = [c for c in root.children if c.dep_ in ('nsubj', 'nsubjpass', 'expl', 'csubj', 'csubjpass')]
        complete_clause = any(c.dep_ in COMPLEMENT_DEPS for c in root.children)
        dependent = not colon.get(uid) and not age and bool(
            connective or points_back
            or not any(t.pos_ in ('NOUN', 'PROPN', 'VERB', 'ADJ', 'NUM') for t in words)
            or (root.pos_ in ('VERB', 'AUX') and not complete_clause
                and (not root_subjects or (main is not None and _personal(main)))))
        claim = (_claim_lemmas(root) if not colon.get(uid) else
                 {_lemma(t) for t in words if t.pos_ in CONTENT or (t.pos_ == 'VERB' and _lemma(t) not in LIGHT_VERBS)})
        found = {'readable': True, 'kind': kind, 'other': other, 'mentions_other': mentions_other,
                     'content': frozenset(content), 'core': frozenset(core), 'nominal': frozenset(nominal),
                     'keys': keys(content | nominal), 'core_keys': keys(core),
                     'gender': gender, 'pronoun_genders': pronoun_genders,
                     'embedded': embedded if kind == 'patient' else frozenset(),
                     'cues': frozenset(cues - {None}), 'past': _past(root), 'age': age,
                     'standalone': (kind in ('patient', 'labelled', 'label_is', 'thing', 'other') and not connective
                                    and not points_back),
                     'patient_past': kind == 'patient' and _past(root),
                     'bounded': tuple(token.idx for token in words if token.dep_ in ('mark', 'advmod')
                                      and _fold(token.text) in BOUNDING_MARKERS and token.head.dep_ == 'advcl'),
                     'hedged': hedged, 'habitual': habitual, 'past_time': past_time, 'dependent': dependent,
                     'claim_keys': keys(claim - {'patient'}),
                     'predicates': () if colon.get(uid) else _predicates(root),
                     'negated_keys': frozenset() if colon.get(uid) else _denied(words, root),
                     'dangling': _dangling(words),
                     'nominal_keys': keys(nominal),
                     'main_lemma': _lemma(main) if main is not None else None,
                     'finite_past': not colon.get(uid) and _tense(root) == 'past',
                     'main_patient': bool(main is not None and main.pos_ in ('NOUN', 'PROPN') and this_patient(main)
                                          and not any(c.dep_ in ('poss', 'compound', 'amod', 'appos') for c in main.children))}
        found.update(_closed_reading(unit, doc, root, words, main, subjects_tok, age, presented))
        return found

    info = {unit['id']: unit_info(index, unit, explicit, ages) for index, unit in enumerate(units)}
    resolved, note_gender = _resolve(units, info)
    # Refutation round 2 (L1:RR1-4): on the relation path ONLY the note's first age presentation presents the patient
    # (`relation_ages`, with or without its article); a later one ('A 30-year-old woman presents for review. A 4-year-old
    # girl presents with her.') presents somebody else, read like any other person.
    relation_ages = frozenset(relation_ages)
    changed = relation_ages ^ frozenset(ages)
    if not changed:
        return {'units': info, 'resolved': resolved, 'gender': note_gender,
                'relation_units': info, 'relation_resolved': resolved, 'relation_gender': note_gender}
    relation_explicit = (frozenset(explicit) - (frozenset(ages) - relation_ages)) | relation_ages
    relation_info = {unit['id']: (unit_info(index, unit, relation_explicit, relation_ages)
                                  if unit['id'] in changed else info[unit['id']]) for index, unit in enumerate(units)}
    relation_resolved, relation_gender = _resolve(units, relation_info)
    return {'units': info, 'resolved': resolved, 'gender': note_gender,
            'relation_units': relation_info, 'relation_resolved': relation_resolved, 'relation_gender': relation_gender}


def _resolve(units, info):
    """The note's one actor run over `info` (see the module docstring): {id: state} and the note's patient gender."""
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
    return resolved, note_gender
