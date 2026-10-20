"""Prospective signing protection bound to an inline marker's printed source.

The physical field mapping remains unchanged. A generic token cannot authorize
AI text in a signing area; uncertain source ownership is held before a request.
"""
import re
import unicodedata

if __package__:
    from .engine import DocumentFailure, TOKEN, W_NS, docx_inspect, structure
else:
    from engine import DocumentFailure, TOKEN, W_NS, docx_inspect, structure

LEGACY_CONTEXT = 'documented-consent-facts-v1'
CONTEXT = 'source-owned-signing-v2'
CONFIG_KEY = 'word_signing_context'
W = '{' + W_NS + '}'
_CLINICIAN = ('physician', 'provider', 'surgeon', 'clinician', 'attending', 'resident',
    'doctor', 'md', 'do', 'np', 'pa', 'author')
_OTHER_ROLES = ('patient', 'witness', 'guardian', 'parent', 'interpreter', 'relative',
    'family', 'next of kin', 'carer')
_ACTOR = r'(?:' + '|'.join(re.escape(role) for role in (*_CLINICIAN, *_OTHER_ROLES)
    if len(role) != 2) + r'|(?-i:MD|DO|NP|PA))'
_ATOM = r'(?:the\s+)?' + _ACTOR + r"(?:['’]s)?"
_ACTORS = _ATOM + r'(?:\s*(?:,\s*(?:(?:and|or)\s+)?|\band\b|\bor\b|/|&)\s*' + _ATOM + r')*'
_DELIMITER = r'[:：\-–—]'
_ACTOR_WORD = re.compile(r'\b' + _ACTOR + r'\b', re.I)
_SIGNER_OBJECT = re.compile(r'\b(?:signatures?|signed|signing|sign)\b(?:\s+(?:by|of)\b\s*(?:'
    + _DELIMITER + r'\s*)?|\s*' + _DELIMITER + r'\s*|(?=\s*\())(?P<object>.*)\Z', re.I | re.S)
_SIGNER_SUBJECT = re.compile(r'(?P<subject>.*?)\b(?:signatures?|signed|signing|sign)\b(?P<tail>.*)\Z', re.I | re.S)
_TIME_FACET = r'(?:date\s*(?:and|&|/)\s*time|time\s*(?:and|&|/)\s*date|date|time)'
_EVENT = r'(?:signature|signing|attestation|certification|consent)'
_OWNED_EVENT = r'(?:(?:' + _ACTORS + r')\s+)?' + _EVENT
_EVENT_TIME = re.compile(r'(?P<before>' + _TIME_FACET + r')\s+of\s+(?:the\s+)?(?P<event_before>'
    + _OWNED_EVENT + r')|(?P<event_after>' + _OWNED_EVENT + r')\s+(?P<after>' + _TIME_FACET
    + r')|(?P<event_parenthetical>' + _OWNED_EVENT + r')\s*\(\s*(?P<parenthetical>' + _TIME_FACET + r')\s*\)', re.I)


def _normalized(text):
    return ''.join(char for char in unicodedata.normalize('NFKC', text)
        if unicodedata.category(char) != 'Cf')


def documented_event_time_request(text):
    """A complete nominal time question asks for an event fact, not an act.

    Only the new source policy uses this decision. Coordinated autograph/date
    destinations and sentences containing an attestation body do not fullmatch.
    """
    normalized = ' '.join(_normalized(text).split()).strip().rstrip(':：.?')
    match = _EVENT_TIME.fullmatch(normalized)
    if not match:
        return None
    facet = next(match[name] for name in ('before', 'after', 'parenthetical') if match[name])
    event = next(match[name] for name in ('event_before', 'event_after', 'event_parenthetical') if match[name])
    return {'intent': 'documented_event_time', 'event': event,
        'facets': sorted(set(re.findall(r'\b(?:date|time)\b', facet.casefold()))),
        'evidence': {'quote': text, 'complete_question': True}}


def _actor_list(text):
    text = ' '.join(text.split()).strip().rstrip(':：;.!?').strip()
    if text.startswith('(') and text.endswith(')'):
        text = text[1:-1].strip()
    if not text:
        return set(), False
    if not re.fullmatch(_ACTORS, text, re.I):
        return set(), True
    return {'clinician' if actor.group().casefold() in _CLINICIAN else actor.group().casefold()
        for actor in _ACTOR_WORD.finditer(text)}, False


def _signing_owners(text):
    text = _normalized(text).strip(' \t\r\n;:：')
    if documented_event_time_request(text):
        return set(), False
    # A signing object's complete remainder belongs to the claim. Never accept
    # a recognized role prefix while discarding a coordinated or unknown owner.
    object_match = _SIGNER_OBJECT.search(text)
    owners, unknown = _actor_list(object_match['object']) if object_match else (set(), False)
    match = _SIGNER_SUBJECT.fullmatch(text)
    if not match:
        return owners, unknown
    subject = match['subject'].strip().rstrip(':：-–—').strip()
    subject = re.sub(r'\s+to\s*$', '', subject, flags=re.I)
    if not subject or subject.casefold() in ('please', 'do', 'electronic', 'digital'):
        return owners, unknown
    subject_owners, subject_unknown = _actor_list(subject)
    if not object_match and match['tail'].strip(' \t\r\n:：;,.!?'):
        subject_unknown = True
    if owners and subject_owners and owners != subject_owners:
        unknown = True
    return owners | subject_owners, unknown or subject_unknown


def validate_context(context):
    if type(context) is not str or context not in (LEGACY_CONTEXT, CONTEXT):
        raise DocumentFailure('Unsupported signing classification policy.', 'invalid_proposal')
    return context


def validate_binding(inventory, config):
    """Only the new policy gains a new immutable approval/config binding."""
    config = config or {}
    if CONFIG_KEY in config:
        validate_context(config[CONFIG_KEY])
    if config.get(CONFIG_KEY) != CONTEXT and inventory.get('signing_context') != CONTEXT:
        return
    if (config.get(CONFIG_KEY) != CONTEXT or inventory.get('signing_context') != CONTEXT
            or inventory.get('protocol') != 'blank-word-preparation-v2'
            or inventory.get('document_backend')):
        raise DocumentFailure('The source-owned signing policy changed.', 'stale_inventory')


def _paragraph_text(paragraph):
    result = []
    for node in paragraph.iter():
        if node is not paragraph and node.tag in (W + 'p', W + 'tc', W + 'tbl'):
            raise DocumentFailure('Inline question text has unresolved source ownership.', 'guided_signing')
        if node.tag in {W + name for name in ('sym', 'drawing', 'pict', 'object', 'fldChar',
                'fldSimple', 'instrText', 'del', 'ins', 'sdt', 'txbxContent')}:
            raise DocumentFailure('Inline question text has unsupported visible context.', 'guided_signing')
        if node.tag == W + 't':
            result.append(node.text or '')
        elif node.tag == W + 'tab':
            result.append('\t')
        elif node.tag in (W + 'br', W + 'cr'):
            result.append('\n')
    return ''.join(result)


def source_scopes(path, fields):
    """Resolve each inline anchor independently from exact current source nodes.

    Each marker owns its printed prefix since the previous marker. Only the
    final marker owns the paragraph suffix. A lone marker also owns its cell's
    question (or an adjacent printed heading over a marker-only paragraph).
    Ambiguous signing between several markers remains explicit and held.
    """
    if __package__:
        from .preparation import ambiguous_signing, signing_protected
        from .question_context import _question_text
    else:
        from preparation import ambiguous_signing, signing_protected
        from question_context import _question_text
    _, paragraphs, _, inspected, _ = docx_inspect(path)
    actual = {field['key']: field for field in inspected}
    if len(fields) != len(actual) or {field['key'] for field in fields} != set(actual):
        raise DocumentFailure('Signing context lost an original answer area.', 'wrong_placement')
    for field in fields:
        physical = {key: value for key, value in field.items() if key != 'answer_constraints'}
        if structure([physical]) != structure([actual[field['key']]]):
            raise DocumentFailure('Signing context changed an original answer location.', 'wrong_placement')
    by_paragraph = {}
    for field in inspected:
        if 'paragraph' in field['locator'] and 'token' in field['locator']:
            by_paragraph.setdefault(field['locator']['paragraph'], []).append(field)
    result = []
    for index, inline in by_paragraph.items():
        paragraph = paragraphs[index]
        text = _paragraph_text(paragraph._p)
        if text != paragraph.text:
            raise DocumentFailure('Inline question text is not completely bound to its source.', 'guided_signing')
        inline.sort(key=lambda field: field['locator']['start'])
        for position, field in enumerate(inline):
            location = field['locator']
            if text[location['start']:location['end']] != location['token']:
                raise DocumentFailure('An inline answer marker changed.', 'wrong_placement')
            start = inline[position - 1]['locator']['end'] if position else 0
            prefix = text[start:location['start']]
            suffix = text[location['end']:] if position == len(inline) - 1 else ''
            contexts = [prefix + suffix]
            uncertain = False
            if len(inline) > 1:
                # A directive between markers without a separate colon-labelled
                # question may belong to either answer. Do not guess an owner.
                uncertain = bool(position and not prefix.rstrip().endswith(':')
                    and (signing_protected(prefix, CONTEXT) or ambiguous_signing(prefix, CONTEXT)))
                uncertain = uncertain or bool(suffix.strip()
                    and (signing_protected(suffix, CONTEXT) or ambiguous_signing(suffix, CONTEXT)))
            cell = next((parent for parent in paragraph._p.iterancestors() if parent.tag == W + 'tc'), None)
            if cell is not None:
                cell_fields = [item for item in inspected if 'paragraph' in item['locator']
                    and any(parent is cell for parent in paragraphs[item['locator']['paragraph']]._p.iterancestors())]
                if len(cell_fields) == 1:
                    contexts.append(TOKEN.sub('', _question_text(cell)))
                    row = cell.getparent()
                    siblings = row.findall(W + 'tc') if row.tag == W + 'tr' else []
                    cell_position = next((i for i, item in enumerate(siblings) if item is cell), -1)
                    if cell_position >= 1 and cell_position % 2 and len(siblings) % 2 == 0:
                        contexts.append(_question_text(siblings[cell_position - 1]))
                else:
                    owned = {paragraphs[item['locator']['paragraph']]._p for item in cell_fields}
                    outside = '\n'.join(_paragraph_text(item) for item in cell.iter(W + 'p') if item not in owned)
                    row = cell.getparent()
                    siblings = row.findall(W + 'tc') if row.tag == W + 'tr' else []
                    cell_position = next((i for i, item in enumerate(siblings) if item is cell), -1)
                    if cell_position >= 1 and cell_position % 2 and len(siblings) % 2 == 0:
                        outside += '\n' + _question_text(siblings[cell_position - 1])
                    uncertain = uncertain or signing_protected(outside, CONTEXT) or ambiguous_signing(outside, CONTEXT)
            elif len(inline) == 1 and text.strip() == location['token']:
                previous = paragraph._p.getprevious()
                if previous is not None and previous.tag == W + 'p':
                    preceding = _paragraph_text(previous)
                    if not TOKEN.search(preceding):
                        contexts.append(preceding)
            protected = any(signing_protected(value, CONTEXT) for value in contexts)
            ambiguous = any(ambiguous_signing(value, CONTEXT) for value in contexts)
            named = signing_protected(field['label'], CONTEXT) or ambiguous_signing(field['label'], CONTEXT)
            source_owners = set()
            for context in contexts:
                if not (signing_protected(context, CONTEXT) or ambiguous_signing(context, CONTEXT)):
                    continue
                owners, unknown = _signing_owners(context)
                source_owners.update(owners); uncertain = uncertain or unknown
            named_owners, named_unknown = _signing_owners(field['label']) if named else (set(), False)
            uncertain = uncertain or named_unknown or bool(named and any(documented_event_time_request(value) for value in contexts))
            if source_owners and named and source_owners != named_owners:
                uncertain = True
            result.append({'field_key': field['key'], 'protected_signing': protected,
                'ambiguous_signing': ambiguous, 'ownership_unresolved': bool(uncertain),
                'named_signing': bool(named), 'source_signing_owners': sorted(source_owners),
                'named_signing_owners': sorted(named_owners)})
    return result


def require_source_protection(path, fields, context):
    if context is not None:
        validate_context(context)
    if context != CONTEXT:
        return
    for scope in source_scopes(path, fields):
        if scope['ownership_unresolved'] or ((scope['protected_signing'] or scope['ambiguous_signing'])
                and not scope['named_signing']):
            raise DocumentFailure('A printed signing instruction is attached to an inline answer marker '
                'whose manual protection cannot be established. Preparation is held for review; no AI request was sent.',
                'guided_signing')
