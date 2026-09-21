"""Explicit clinician identity for a signature answer area, wherever it sits on the form."""
import re

from django.core.exceptions import ValidationError

# The same normalised labels the tab inspector recognises. Kept here so the rule belongs to
# the REVIEW contract rather than to one importer, and so a second importer cannot acquire a
# signature field without the protection that is supposed to travel with it.
#: Trailing punctuation a form author may type after a question. Stripped as one class rather
#: than in a fixed order: `rstrip(':')` then `strip()` handled `'Electronically signed by :'`,
#: and nothing handled a FULL-WIDTH colon or a trailing period. Both were measured unprotected.
TRAILING = ':：.,;· \t'

_ROLE = r"(?:physician|provider|surgeon|clinician|attending|resident|doctor|md|do|np|pa|author)"
#: A signature answer area names a PERSON. Enumerated deliberately rather than by "contains
#: signature", because `Signature date` and `Date of signature` are DATE questions — refusing to
#: finalize them unless they equal the clinician's name would be a false rejection, and this
#: file has already shipped one of those.
SIGNATURE_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r"(?:electronically |digitally |e[- ])?sign(?:ed|ature)(?: by| of)?(?: ?\([^)]*\))?",
    rf"{_ROLE}'?s? sign(?:ature|ed)(?: by)?",
    rf"sign(?:ature|ed)(?: by| of)? (?:the )?{_ROLE}",
    r"signature ?/ ?date",
))


def signature_label(label):
    text = re.sub(r'\s+', ' ', str(label or '')).strip().rstrip(TRAILING).strip().casefold()
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
