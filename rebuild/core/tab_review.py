"""Explicit clinician identity for a signature answer area, wherever it sits on the form."""
import re

from django.core.exceptions import ValidationError

# The same normalised labels the tab inspector recognises. Kept here so the rule belongs to
# the REVIEW contract rather than to one importer, and so a second importer cannot acquire a
# signature field without the protection that is supposed to travel with it.
#: Trailing punctuation a form author may type after a question. Stripped as one class rather
#: than in a fixed order: `rstrip(':')` then `strip()` handled `'Electronically signed by :'`,
#: and nothing handled a FULL-WIDTH colon or a trailing period. Both were measured unprotected.
#: ⚠️ KEPT CHARACTER-FOR-CHARACTER IN STEP WITH `documents/tab_form.py`'s copy. The two
#: diverged on `,` and `;`, and the agreement test only checked one direction.
TRAILING = ':：.,;· \t'

_ROLE = r"(?:physician|provider|surgeon|clinician|attending|resident|doctor|md|do|np|pa|author)"
#: A signature answer area names a PERSON. Enumerated deliberately rather than by "contains
#: signature", because `Signature date` and `Date of signature` are DATE questions — refusing to
#: finalize them unless they equal the clinician's name would be a false rejection, and this
#: file has already shipped one of those.
#: ⚠️ ANY PARENTHETICAL KEEPS A SIGNATURE LINE THE FINALIZER'S, UNLESS IT NAMES SOMEBODY ELSE (`NOT_THE_CLINICIAN`,
#: below) OR A DATE (`QUALIFIER`). The identity check FAILS CLOSED: a parenthetical that names no one it knows is read
#: as the finalizer's. A narrowing to parentheticals naming a clinician-role word (2026-09-30) was refuted the same day:
#: `Signed (Consultant)`, `Signature (GP)`, `Signed (print name)`, `Electronically signed by (print name)` all stopped
#: being identity rows - generation filled a consultant's signature line from the notes and finalization accepted
#: another clinician's name. The persons that are NOT the finalizer are the exclusion list, and a miss there costs a
#: signature line left for the hand (never a name written that the finalizer did not sign).
SIGNATURE_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r"(?:electronically |digitally |e[- ])?sign(?:ed|ature)(?: by| of)?(?: ?\([^)]*\))?",
    rf"{_ROLE}'?s? sign(?:ature|ed)(?: by)?",
    rf"sign(?:ature|ed)(?: by| of)? (?:the )?{_ROLE}",
    r"signature ?/ ?date",
))


#: ⚠️ A SIGNATURE THAT IS EXPLICITLY SOMEBODY ELSE'S IS NOT THE CLINICIAN'S, and calling it
#: one is a FALSE REFUSAL: `validate_identity` would then demand the finalizing clinician's own
#: name in a witness or patient signature line and refuse the document until it got it.
#: `Signed by (witness)` matched the qualifier arm and did exactly that. Measured.
#: `participant`, `mother`, `father` and `donor` were measured missing (`Signature (participant)` demanded the
#: finalizer's own name in a research participant's signature place).
NOT_THE_CLINICIAN = re.compile(
    r'\b(?:patient|witness|guardian|parent|interpreter|relative|family|next of kin|carer|participant|mother|father|'
    r'donor)\b')


#: ⚠️ THE QUALIFIER ARM IS CONTENT-BLIND, AND THAT REOPENED THE BOUND THIS FILE CLAIMS.
#: `(?: ?\([^)]*\))?` accepts any parenthetical, so `Signature (date)` and
#: `Signature (date and time)` matched and would have demanded the finalizer's own name in a
#: DATE question — the exact false-refusal class the declaration says it bounded, arriving by
#: another spelling. Checked on the parenthetical ALONE, deliberately: a blanket date test would
#: also reject `Signature/Date`, which IS a signature line and is correctly recognised.
QUALIFIER = re.compile(r'\(([^)]*)\)')
DATE_QUESTION = re.compile(r'\b(?:date|dated|time|day)\b')


def _normal(label):
    return re.sub(r'\s+', ' ', str(label or '')).strip().rstrip(TRAILING).strip().casefold()


def signature_line(label):
    """Whether a label prints a SIGNATURE LINE, whoever signs it: SIGNATURE_PATTERNS with the date-qualifier exclusion,
    BEFORE the not-the-clinician exclusion. `signature_label` is this reading less `NOT_THE_CLINICIAN`, unchanged."""
    text = _normal(label)
    inner = QUALIFIER.search(text)
    if inner and DATE_QUESTION.search(inner.group(1)):
        return False
    return any(pattern.fullmatch(text) for pattern in SIGNATURE_PATTERNS)


def signature_label(label):
    if NOT_THE_CLINICIAN.search(_normal(label)):
        return False
    return signature_line(label)


def another_signers_line(field):
    """A signature line the label names as somebody else's (`NOT_THE_CLINICIAN`): not the finalizer's identity row, and
    never generated from notes either - it is signed by hand by the person it names.

    ⚠️ THE EXCLUSION LIST DECIDES WHOSE SIGNATURE IT IS, NEVER WHETHER IT IS ONE (refutation of a32243eb, RR1-10).
    Widening `NOT_THE_CLINICIAN` by 'participant', 'mother', 'father' and 'donor' correctly stopped demanding the
    finalizer's own name in those lines, but it also took them out of the only hold 43fcf214 gave them (identity), and
    a date word the identity qualifier does not know ('dd/mm/yyyy', 'DOB', 'born') took them out of the role reader:
    'Signature (participant, dd/mm/yyyy)' and 'Signed (mother, DOB)' were generated and exported. This reads the SAME
    patterns as identity - no new wording - and holds from generation exactly the lines 43fcf214 held (plus the
    exclusion list's own persons, whose lines are signing places too); a clinician's typed value still exports."""
    label = (field or {}).get('label')
    return bool(NOT_THE_CLINICIAN.search(_normal(label))) and signature_line(label)


def clinician_identity(field):
    """A signature answer area, identified by its POLICY or by its label.

    ⚠️ THIS USED TO REQUIRE `tab_form` IN THE LOCATOR, and only the tab inspector ever sets
    `answer_policy`. A signature row in an ordinary two-column table therefore had neither
    guard: generation would fill it from the notes, and `validate_identity` skipped it at
    finalization, so the name never had to match the clinician signing. Measured on
    `Electronically signed by | ____`: status `supported`, text taken straight from the notes.

    ⚠️ AND THE FIRST REPAIR KEPT A SHORT-CIRCUIT THAT DEFEATED ITSELF. It read
    "a tab field is judged by its policy alone", which is false whenever the inspector did not
    set one — a heading-continuation signature (`Electronically signed by:` as a Word heading
    over a blank underlined line) came through with NO policy, and `signature_label` said True
    about a label this function never consulted. Measured end to end: another clinician's name
    finalized, on a document whose inline-label twin was correctly protected.

    There is no short-circuit now. Policy OR label, for every field, so the protection travels
    with the QUESTION rather than with the importer that happened to produce it.
    """
    return field.get('answer_policy') == 'clinician_identity' or signature_label(field.get('label'))


def validate_identity(fields, answers, actor):
    """Never infer a signature from notes, labels, dates, or another clinician.

    An explicitly reviewed blank stays blank. A supplied signature must be the
    authenticated finalizer's identity, following the existing Word review rule.
    Dates of dictation/transcription remain documented answers, not signing time.
    """
    name = ' '.join((actor.get_full_name() or actor.email).split())
    for field in fields:
        if not clinician_identity(field):
            continue
        answer = answers.get(field['key'], {})
        value = answer.get('text', '')
        if value.strip() and (answer.get('reviewed') is not True or answer.get('reviewed_by') != str(actor.pk)):
            raise ValidationError('Review your own signature field before finalizing this document.')
        if value.strip() and (not name or ' '.join(value.split()) != name):
            raise ValidationError('The reviewed signature must match your signed-in clinician name. Enter your account name or leave this field unanswered; another name in the notes cannot authorize signing.')
