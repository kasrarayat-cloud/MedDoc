"""Keep source-grounded form mismatches held for an explicit doctor correction."""
from documents.engine import answer_constraint_error


def hold_constraint_mismatches(fields, answers):
    result = {key: dict(answer) for key, answer in answers.items()}
    for field in fields:
        answer = result.get(field['key'])
        if not answer:
            continue
        error = answer_constraint_error(field, answer.get('text', ''))
        if error:
            # Preserve the original selected text and evidence. A review tick or
            # suggestion acceptance cannot waive the source form's constraint.
            answer.update(status='conflict', text='', reviewed=False,
                          constraint_rejected_text=answer.get('text', ''),
                          constraint_error=error, accepted_suggestion=False)
    return result
