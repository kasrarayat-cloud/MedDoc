"""One exact current-state option relation; no history, pronoun or synonym inference."""

STATEMENTS = frozenset(('The patient is a nonsmoker.', 'Patient is a nonsmoker.'))


def current_nonsmoker(field, text, notes, evidence):
    """Return literal No only for the whole, otherwise empty source and unscoped binary Smoker field.

    The caller has already applied duplicate-field and source-context guards, and calls only for a supported
    answer, never a held candidate or suggestion. Additional source requires a separately reviewed relationship;
    its words are not classified or discarded here. Preserve the exact original evidence and printed option.
    """
    if (field.get('label') != 'Smoker' or field.get('kind') != 'choice' or field.get('context')
            or (field.get('locator') or {}).get('contract') != 'v3'):
        return None
    options = field.get('options') or []
    from documents.word_v3 import printed_options
    printed = printed_options(field)
    if options not in (['Yes', 'No'], ['No', 'Yes']) or printed not in (['Yes', 'No'], ['No', 'Yes']):
        return None
    if not isinstance(text, str) or text not in STATEMENTS or len(evidence) != 1 or not isinstance(evidence[0], dict):
        return None
    entry = evidence[0]
    start, end = entry.get('start'), entry.get('end')
    if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(notes)
            or entry.get('quote') != text or notes[start:end] != text
            or notes[:start].strip() or notes[end:].strip()):
        return None
    return 'No'


def evidence_needs_review(notes, fields, evidence):
    """A stored literal relation must satisfy exactly the same proof as generation, even after other text appears.

    Only these two exact source statements opt into this rule; existing labelled options and other field types
    retain their current readers. Returning true keeps every source unit visible as context, not an offer.
    """
    if not any(field.get('kind') == 'choice' for field in fields):
        return False
    if not any(isinstance(entry, dict) and isinstance(entry.get('quote'), str)
               and entry['quote'] in STATEMENTS for entry in evidence):
        return False
    return (len(fields) != 1 or len(evidence) != 1
            or current_nonsmoker(fields[0], evidence[0].get('quote'), notes, evidence) is None)
