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

#: The signer named by the label: one to three words, by STRUCTURE rather than a list of roles ('Consultant signature',
#: 'Signature of examining clinician', 'Signed by the reviewing nurse'). A word that asks a date or time question (the
#: DATE_QUESTION words below) is never part of it - `Signature date` and `Date of signature` are DATE questions, and
#: refusing to finalize them unless they equal the clinician's name would be a false rejection, which this file has
#: already shipped once - and nor is a preposition or conjunction, which would make the phrase something else than one
#: noun phrase ('Place of signature', 'Signature and date'). Somebody else's signature is refused by NOT_THE_CLINICIAN.
_NOT_A_SIGNER = r"(?:date|dated|time|day|of|by|for|and|or|at|in|on|to)\b"
_WORD = rf"(?!{_NOT_A_SIGNER})[a-z][a-z'.-]*"
_SIGNER = rf"{_WORD}(?: {_WORD}){{0,2}}"
#: A signature answer area names a PERSON.
SIGNATURE_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r"(?:electronically |digitally |e[- ])?sign(?:ed|ature)(?: by| of)?(?: ?\([^)]*\))?",
    rf"{_SIGNER}'?s? sign(?:ature|ed)(?: by)?",
    rf"sign(?:ature|ed)(?: by| of)? (?:the )?{_SIGNER}",
    r"signature ?/ ?date",
))


#: ⚠️ A SIGNATURE THAT IS EXPLICITLY SOMEBODY ELSE'S IS NOT THE CLINICIAN'S, and calling it
#: one is a FALSE REFUSAL: `validate_identity` would then demand the finalizing clinician's own
#: name in a witness or patient signature line and refuse the document until it got it.
#: `Signed by (witness)` matched the qualifier arm and did exactly that. Measured.
NOT_THE_CLINICIAN = re.compile(
    r'\b(?:patient|witness|guardian|parent|interpreter|relative|family|next of kin|carer)\b')


#: ⚠️ THE QUALIFIER ARM IS CONTENT-BLIND, AND THAT REOPENED THE BOUND THIS FILE CLAIMS.
#: `(?: ?\([^)]*\))?` accepts any parenthetical, so `Signature (date)` and
#: `Signature (date and time)` matched and would have demanded the finalizer's own name in a
#: DATE question — the exact false-refusal class the declaration says it bounded, arriving by
#: another spelling. Checked on the parenthetical ALONE, deliberately: a blanket date test would
#: also reject `Signature/Date`, which IS a signature line and is correctly recognised.
QUALIFIER = re.compile(r'\(([^)]*)\)')
DATE_QUESTION = re.compile(r'\b(?:date|dated|time|day)\b')


def signature_label(label):
    text = re.sub(r'\s+', ' ', str(label or '')).strip().rstrip(TRAILING).strip().casefold()
    if NOT_THE_CLINICIAN.search(text):
        return False
    inner = QUALIFIER.search(text)
    if inner and DATE_QUESTION.search(inner.group(1)):
        return False
    return any(pattern.fullmatch(text) for pattern in SIGNATURE_PATTERNS)


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
