"""Source constraints for newly reviewed, already qualified table answer cells.

This helper has no version-selection authority. Callers opt in only for new
preparations, and rederive these constraints for that version's export. Existing
approved mappings do not acquire new semantics merely by installing this module.
"""
from copy import deepcopy
import re

if __package__:
    from .engine import DocumentFailure, PRINTED_UNITS, constraint_from_context, docx_inspect, structure
else:
    from engine import DocumentFailure, PRINTED_UNITS, constraint_from_context, docx_inspect, structure


def _printed_constraint(label):
    declarations = []

    def retain(item):
        if item['data_type'] != 'text' and item not in declarations:
            declarations.append(item)

    retain(constraint_from_context(label, ''))
    # A literal declaration still applies when followed by an instruction.
    # Normalize only a complete printed bracket group for the shared reader;
    # the original document and question label remain unchanged.
    for printed in re.findall(r'\([^()]*\)|\[[^\[\]]*\]', label):
        canonical = '(' + printed[1:-1].strip() + ')'
        item = constraint_from_context(canonical, '')
        if re.fullmatch(r'\((?:integer|number)\)', canonical, re.I):
            item = constraint_from_context('', canonical)
        retain(item)
    if declarations:
        # A second, literally printed terminal unit can contradict an explicit
        # declaration. It only removes certainty; it never infers a constraint
        # from nearby prose or supplies a unit for an otherwise unknown label.
        units = '|'.join(re.escape(unit) for unit in sorted(PRINTED_UNITS, key=len, reverse=True))
        terminal = re.search(r'(?:^|\s)(' + units + r')\s*[.:]?\s*$', label)
        if terminal:
            retain(constraint_from_context('', terminal.group(1)))
    # Conflicting declarations remain uncertain even when agents agree.
    return declarations[0] if len(declarations) == 1 else None


def with_table_constraints(path, fields):
    """Copy a complete mapping, grounding table constraints in its source cells.

    Labels remain editable application metadata. The actual original printed
    question supplies every constraint, after the existing inspector proves its
    answer-cell association. Non-table fields are unchanged; signing areas and
    uncertain declarations receive no new constraint. Present table constraints
    must equal the rederived value, so this also verifies stored new-version maps.
    """
    if __package__:
        from .preparation import SIGNING
    else:
        from preparation import SIGNING

    if (not isinstance(fields, list)
            or any(not isinstance(field, dict) or not isinstance(field.get('key'), str)
                   or not isinstance(field.get('locator'), dict) for field in fields)):
        raise DocumentFailure('The table mapping is not a complete field list.', 'invalid_mapping')
    _, _, cells, inspected, _ = docx_inspect(path)
    actual = {field['key']: field for field in inspected if 'cell' in field.get('locator', {})}
    supplied = [field for field in fields if 'cell' in field.get('locator', {})]
    if len(supplied) != len(actual) or {field.get('key') for field in supplied} != set(actual):
        raise DocumentFailure('The table mapping omitted or repeated an original answer cell.', 'incomplete_proposal')
    copied = deepcopy(fields)
    for field in copied:
        if 'cell' not in field.get('locator', {}):
            continue
        source = actual[field['key']]
        binding = {key: value for key, value in field.items() if key != 'answer_constraints'}
        cell_index = field['locator']['cell']
        if (type(cell_index) is not int or not 0 <= cell_index < len(cells)
                or structure([binding]) != structure([source])):
            raise DocumentFailure('A table constraint lost its original answer cell.', 'wrong_placement')
        # No surrounding row, nearby unit, mutable label, or model-supplied path
        # can establish a constraint for this original inspector-qualified cell.
        constraint = None if SIGNING.search(source['label']) else _printed_constraint(source['label'])
        if 'answer_constraints' in field and field['answer_constraints'] != constraint:
            raise DocumentFailure('A table constraint differs from the original printed question.', 'content_changed')
        if constraint is not None:
            field['answer_constraints'] = constraint
    return copied
