"""Explicit clinician identity for the ordinary tab-form signature location."""
from django.core.exceptions import ValidationError


def clinician_identity(field):
    return (field.get('answer_policy') == 'clinician_identity'
            and isinstance(field.get('locator'), dict)
            and 'tab_form' in field['locator'])


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
