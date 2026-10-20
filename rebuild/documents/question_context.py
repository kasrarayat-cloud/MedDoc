"""Opt-in question text from real Word boundaries at qualified answer cells.

The physical inspector and its constraint contract remain unchanged. A styled
run is not a word boundary; a paragraph, tab or explicit break is. No model or
stored label can establish the association between a question and its answer.
"""
from copy import deepcopy

if __package__:
    from .engine import DocumentFailure, docx_inspect, structure, W_NS
else:
    from engine import DocumentFailure, docx_inspect, structure, W_NS

CONTEXT = 'source-question-boundaries-v1'
CONFIG_KEY = 'word_question_context'
W = '{' + W_NS + '}'


def validate_context(context):
    if type(context) is not str or context != CONTEXT:
        raise DocumentFailure('Unsupported explicit source-question context.', 'invalid_proposal')
    return context


def validate_binding(inventory, config):
    """An explicit policy must match both immutable preparation surfaces."""
    config = config or {}
    if CONFIG_KEY not in config and 'question_context' not in inventory:
        return
    validate_context(config.get(CONFIG_KEY))
    validate_context(inventory.get('question_context'))
    if inventory.get('protocol') != 'blank-word-preparation-v2' or inventory.get('document_backend'):
        raise DocumentFailure('Source-question context requires an ordinary typed Word form.', 'invalid_proposal')


def _question_text(cell):
    # Read actual source nodes. Adjacent runs and hyperlinks remain adjacent;
    # only Word's explicit text boundaries supply whitespace. Block wrappers
    # may contain paragraphs, so direct-child traversal would omit source text.
    text_tags = {W + 't', W + 'tab', W + 'br', W + 'cr'}
    source_nodes = [node for node in cell.iter() if node.tag in text_tags]
    covered_nodes = []
    paragraphs = []
    for paragraph in cell.iter(W + 'p'):
        for ancestor in paragraph.iterancestors():
            if ancestor is cell:
                break
            if ancestor.tag in (W + 'p', W + 'tc', W + 'tbl'):
                raise DocumentFailure('Question text has ambiguous nested paragraph ownership.', 'unsupported_structure')
        text = []
        for node in paragraph.iter():
            if node.tag in text_tags:
                covered_nodes.append(node)
            if node.tag == W + 't':
                text.append(node.text or '')
            elif node.tag == W + 'tab':
                text.append('\t')
            elif node.tag in (W + 'br', W + 'cr'):
                text.append('\n')
        paragraphs.append(''.join(text))
    # Identity and order matter: equal strings cannot conceal an omitted node,
    # duplicate coverage or text outside any independently owned paragraph.
    if len(source_nodes) != len(covered_nodes) or any(
            source is not covered for source, covered in zip(source_nodes, covered_nodes)):
        raise DocumentFailure('Question text is not completely bound to ordered source paragraphs.', 'unsupported_structure')
    return '\n'.join(paragraphs).strip()


def project_fields(path, fields, context, *, signing_context=None):
    """Change labels only, after proving each original physical destination."""
    validate_context(context)
    if __package__:
        from .preparation import SIGNING, signing_protected
        from .table_constraints import _printed_constraint
    else:
        from preparation import SIGNING, signing_protected
        from table_constraints import _printed_constraint
    _, _, cells, inspected, _ = docx_inspect(path)
    actual = {field['key']: field for field in inspected if 'cell' in field['locator']}
    supplied = [field for field in fields if 'cell' in field.get('locator', {})]
    if len(supplied) != len(actual) or {field['key'] for field in supplied} != set(actual):
        raise DocumentFailure('Question context lost an original answer cell.', 'wrong_placement')
    result = deepcopy(fields)
    for field in result:
        if 'cell' not in field.get('locator', {}):
            continue
        source = actual[field['key']]
        binding = {key: value for key, value in field.items() if key != 'answer_constraints'}
        index = field['locator']['cell']
        if (type(index) is not int or not 0 <= index < len(cells)
                or structure([binding]) != structure([source])):
            raise DocumentFailure('Question context changed an original answer destination.', 'wrong_placement')
        answer, _ = cells[index]
        row = answer.getparent()
        siblings = row.findall(W + 'tc') if row.tag == W + 'tr' else []
        position = next((i for i, cell in enumerate(siblings) if cell is answer), -1)
        if position < 1 or position % 2 != 1 or len(siblings) % 2:
            raise DocumentFailure('Question context has no exact preceding question cell.', 'wrong_placement')
        question = siblings[position - 1]
        flattened = ''.join(question.xpath('.//w:t/text()')).strip()
        if flattened != source['label']:
            raise DocumentFailure('Question context differs from the original question cell.', 'content_changed')
        projected = _question_text(question)
        if not projected or field['label'] not in (flattened, projected):
            raise DocumentFailure('Question context changed the original printed text.', 'content_changed')
        # Export rederives physical constraints through the unchanged inspector.
        # A new boundary must not silently change their meaning. Such a form
        # needs a separately supported physical constraint contract.
        old_constraint = None if SIGNING.search(flattened) else _printed_constraint(flattened)
        new_constraint = None if SIGNING.search(projected) else _printed_constraint(projected)
        if old_constraint != new_constraint:
            raise DocumentFailure('Question boundaries make the printed answer constraints ambiguous.', 'guided_layout')
        # Removing a concatenation must never remove an existing protection.
        if signing_protected(flattened, signing_context) and not signing_protected(projected, signing_context):
            raise DocumentFailure('Question boundaries changed the original signing protection.', 'guided_layout')
        field['label'] = projected
    return result
