"""The member's answer to a date asked only because its header block runs into the body (refutation phase 2, P2DATES).

Rule 1 reads a labelled date as the note's own only when it stands in a header block that a blank line ends, and a
digital PDF's or a Word document's extracted text keeps no blank line: such a document's labelled date is asked, and
the member answers it with that date. Tests whose subject is not the date (page joins, sections, wording) read such a
document with that answer, as a member would give it. Nothing is supplied for a date asked for any other reason - a
qualifier, a title, an unread or invalid form, two different dates - so those readings stay exactly as they were.
"""
from studio.gi import context as gi_context

_OTHER_NOTES = (gi_context.UNPLACED_DATE_NOTE, gi_context.UNREAD_DATE_NOTE, gi_context.INVALID_DATE_NOTE)


def answered(facts):
    """``facts`` with the member's answer when the service date is asked by rule 1 alone and its evidence states one
    date; otherwise ``facts`` unchanged."""
    fact = facts['service_date']
    note = str(fact.note or '')
    if fact.origin != 'missing' or gi_context.HEADER_DATE_NOTE not in note or any(n in note for n in _OTHER_NOTES):
        return facts
    readings = gi_context._date_readings(fact.evidence)
    if not readings or len(readings) != 1:
        return facts
    return gi_context.merge_user_values(facts, {'service_date': next(iter(readings))})


def answered_context(text):
    return answered(gi_context.extract_context(text))
