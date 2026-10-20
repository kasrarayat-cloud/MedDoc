"""Finite blank-form inventory and ZIP-part preserving candidate writer.

Runs in the document sandbox. AI sees question/anchor IDs and visible source text,
never locators or XML. The original package is always the authority.
"""
from copy import deepcopy
import hashlib
import json
import re
import unicodedata
from zipfile import ZipFile
from lxml import etree

if __package__:
    from .engine import validate_docx, docx_inspect, DocumentFailure, TOKEN, W_NS, constraint_from_context
    from .sdk_service import WM_IOV_SHA256
    from .question_context import CONTEXT as QUESTION_CONTEXT, project_fields, validate_context
else:
    from engine import validate_docx, docx_inspect, DocumentFailure, TOKEN, W_NS, constraint_from_context
    from sdk_service import WM_IOV_SHA256
    from question_context import CONTEXT as QUESTION_CONTEXT, project_fields, validate_context

NS = {'w': W_NS}
W = '{'+W_NS+'}'
PROTOCOL = 'blank-word-preparation-v1'
TYPED_PROTOCOL = 'blank-word-preparation-v2'
WM_SOURCE_REVIEW_CONTEXT = 'qualified-wm-stories-v1'
# This projection binds the complete original package, canonical answer
# destinations and original assertion/signing associations. It excludes only
# the separately enforced clinical variant definitions and historical state.
WM_SOURCE_REVIEW_SHA256 = 'dd2b10ebca490f30dd7b4814c7d30205d5e4349034b650dcac15a2ecce9d9e1b'
WM_REQUIREMENT_SOURCE_KEYS = ('key', 'label', 'kind', 'body_paragraph', 'text',
                              'text_sha256', 'control_keys', 'original_text',
                              'original_text_sha256')
SIGNING = re.compile(r'\b(?:signatures?|signed|signing|attest(?:ation|ed|ing)?|certif(?:ication|ied|y)|consent(?:ed|ing)?)\b'
                     r'|\bsign\s+(?:here|below|above|by|and\s+date)\b'
                     r'|\b(?:please|patient|clinician|physician|doctor|provider|digital|electronic)\s+sign\b', re.I)
# Unknown singular signing language is guided, never made writable. Plural
# clinical signs and embedded words do not match this word-boundary predicate.
AMBIGUOUS_SIGNING = re.compile(r'\bsign\b', re.I)
# A clinical noun phrase is different from an instruction to sign. Recognize
# adjectival and possessive noun modifiers, rather than exempting one printed
# question. Classification is per occurrence: an actor or instruction elsewhere
# in a clinical question does not turn its noun into a signing verb.
CLINICAL_SIGN_NOUN = re.compile(
    r"(?<!\w)(?:[\w-]+(?:al|ic|ary|ory|ous|ive)|[\w-]+['’]s)\s+sign\b", re.I)
SIGNING_CONTEXT = 'documented-consent-facts-v1'
# A retrospective question asks for evidence of an event; it does not grant
# consent. Unknown wording and every explicit signature/attestation stay guided.
CONSENT_FACT = re.compile(
    r'(?:(?:what|which)\s+(?:(?:informed|verbal|written|telephone|video|telehealth|patient|procedure|surgical)\s+){0,4}'
    r'consent\s+(?:was|is|has\s+been)\s+(?:documented|recorded)\s*\?'
    r'|describe\s+the\s+consent\s+discussion\s+(?:documented|recorded)\s+for\s+this\s+visit\s*[.?]?)'
    r'(?:\s*for\s+(?:telephone|video|telehealth|in-person)(?:\s+or\s+(?:telephone|video|telehealth|in-person))?\s+visits\s+only\.)?'
    r'(?:\s*leave\s+blank\s+for\s+(?:telephone|video|telehealth|in-person)\s+visits\.)?', re.I)


def signing_protected(label, context=None):
    if context not in (None, SIGNING_CONTEXT):
        raise DocumentFailure('Unsupported signing classification policy.', 'invalid_proposal')
    if context is None:
        return bool(SIGNING.search(label))
    normalized = ''.join(c for c in unicodedata.normalize('NFKC', label)
                         if unicodedata.category(c) != 'Cf')
    normalized = ' '.join(normalized.split())
    if CONSENT_FACT.fullmatch(normalized):
        return False
    return bool(SIGNING.search(normalized))


def ambiguous_signing(label, context=None):
    """Keep uncertain signing language closed without holding clinical nouns.

    Explicit signatures and attestations always take precedence, including a
    clinical question followed by a signing directive. Each singular occurrence
    must have a noun modifier; a second unexplained ``sign`` remains guided.
    """
    if signing_protected(label, context):
        return False
    normalized = ' '.join(unicodedata.normalize('NFKC', label).split())
    occurrences = list(AMBIGUOUS_SIGNING.finditer(normalized))
    if not occurrences:
        return False
    nouns = list(CLINICAL_SIGN_NOUN.finditer(normalized))
    return any(not any(noun.start() <= item.start() and item.end() <= noun.end()
                       for noun in nouns) for item in occurrences)

BLANK = re.compile(r'_{3,}')
UNSUPPORTED = {'sdt', 'txbxContent', 'fldChar', 'fldSimple', 'instrText', 'del', 'ins'}

def source_bound_candidate_fields(path, value):
    """Annotate only newly inserted literal blanks, without changing old fields."""
    _, paragraphs, _, fields, _ = docx_inspect(path)
    questions = {question['id']: question for question in value['questions']}
    identities = {}
    per_part = {}
    for index, paragraph in enumerate(paragraphs):
        part = str(paragraph.part.partname).lstrip('/')
        position = per_part.get(part, 0)
        identities[index] = (part, position)
        per_part[part] = position + 1
    for anchor in value['anchors']:
        if anchor['kind'] != 'literal_blank':
            continue
        question = questions[anchor['question_id']]
        location = anchor['locator']
        matches = [field for field in fields if field['label'] == question['text']
                   and identities.get(field['locator'].get('paragraph')) ==
                   (location['part'], location['paragraph'])]
        if len(matches) != 1:
            raise DocumentFailure('A prepared constraint lost its original answer location.', 'wrong_placement')
        field = matches[0]
        paragraph = paragraphs[field['locator']['paragraph']].text
        actual = constraint_from_context(paragraph[:field['locator']['start']],
                                         paragraph[field['locator']['end']:])
        if actual != question['answer_constraints']:
            raise DocumentFailure('A prepared constraint differs from the original form.', 'content_changed')
        field['answer_constraints'] = deepcopy(actual)
    return fields


def typed_source_fields(path, fields, *, signing_context=None, question_context=None):
    """Opt-in semantics for a new preparation; existing approvals are untouched."""
    if __package__:
        from .table_constraints import with_table_constraints
    else:
        from table_constraints import with_table_constraints
    result = with_table_constraints(path, fields)
    _, paragraphs, _, inspected, _ = docx_inspect(path)
    source = {field['key']: field for field in inspected}
    for field in result:
        location = source[field['key']]['locator']
        if signing_protected(source[field['key']]['label'], signing_context):
            continue
        if 'paragraph' in location and 'token' in location:
            text = paragraphs[location['paragraph']].text
            constraint = constraint_from_context(text[:location['start']], text[location['end']:])
            if constraint['data_type'] != 'text' or 'answer_constraints' in field:
                if field.get('answer_constraints', constraint) != constraint:
                    raise DocumentFailure('The paragraph constraint differs from its source.', 'content_changed')
                field['answer_constraints'] = deepcopy(constraint)
    if question_context is not None:
        result = project_fields(path, result, question_context, signing_context=signing_context)
    return result

def occupied(cell):
    return bool(''.join(cell.xpath('.//w:t/text()',namespaces=NS)).strip() or
                cell.xpath('.//w:drawing | .//w:pict | .//w:br | .//w:sym | .//w:object | .//w:fldChar | .//w:fldSimple | .//w:sdt',namespaces=NS))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def unmapped_multi_column_rows(path):
    # Reuse the installed inspector's exact row semantics, not a substring or a
    # guessed count. These row identities are internal and never sent to AI.
    if __package__:
        from .engine import Document,docx_parts,answerable_row,multi_column_answers
    else:
        from engine import Document,docx_parts,answerable_row,multi_column_answers
    result=[]
    for part in docx_parts(Document(path)):
        for index,row in enumerate(part.element.iter(W+'tr')):
            cells=row.findall(W+'tc')
            if (len(cells)!=2 and not any(cell.xpath('.//w:vMerge | .//w:gridSpan | .//w:tbl') for cell in cells)
                    and not multi_column_answers(cells) and answerable_row(cells)):
                result.append({'part':str(part.partname).lstrip('/'),'row':index})
    return result


def inventory(path, known=None, *, protocol=PROTOCOL, signing_context=None, question_context=None):
    if protocol not in {PROTOCOL, TYPED_PROTOCOL}:
        raise DocumentFailure('Unsupported preparation protocol.', 'invalid_proposal')
    if (signing_context is not None and (signing_context != SIGNING_CONTEXT
            or protocol != TYPED_PROTOCOL or known)):
        raise DocumentFailure('Unsupported signing classification policy.', 'invalid_proposal')
    if question_context is not None:
        validate_context(question_context)
        if protocol != TYPED_PROTOCOL or known:
            raise DocumentFailure('Source-question context requires an ordinary typed Word form.', 'invalid_proposal')
    validate_docx(path, inventory_only=True)
    source_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if known and known.get('sha256') != source_sha:
        raise DocumentFailure('The mapping is not bound to this original.', 'stale_mapping')
    stories, parts, options, anchors, questions, issues = [], {}, [], [], [], []
    qualified = bool(known and known.get('backend') == 'wm-iov-foss-v2')
    if known:
        if not qualified or source_sha != WM_IOV_SHA256:
            raise DocumentFailure('Only the exact qualified WM original may use the advanced mapping.', 'stale_mapping')
    fields = deepcopy(known.get('fields', [])) if known else []
    warnings = []
    mapped_cells=set()
    if not known:
        try:
            _, _, cells, fields, warnings = docx_inspect(path)
            mapped_cells={(str(part.partname).lstrip('/'),cell.getroottree().getpath(cell)) for cell,part in cells}
        except DocumentFailure as exc:
            if exc.code not in {'no_fields', 'unsupported_structure', 'overflow_risk'}:
                raise
            if exc.code != 'no_fields':
                issues.append({'code': exc.code, 'message': str(exc)})
    if protocol == TYPED_PROTOCOL and not known and fields:
        fields = typed_source_fields(path, fields, signing_context=signing_context, question_context=question_context)
    for field in fields:
        if ambiguous_signing(field['label'], signing_context):
            issues.append({'code':'guided_signing','message':field['label']+': clarify whether this is a clinical answer or a signing area before preparation.'})
        qid, aid = 'q'+str(len(questions)+1), 'a'+str(len(anchors)+1)
        questions.append({'id': qid, 'text': field['label'], 'story': 'mapped',
                          'protected_signing': signing_protected(field['label'], signing_context)})
        if protocol == TYPED_PROTOCOL and not questions[-1]['protected_signing']:
            constraint = field.get('answer_constraints')
            # Qualified WM metadata is bound to the exact original and its
            # existing controlled inspector, rather than a model inference.
            if known and field.get('kind') == 'choice':
                constraint = {'version': 1, 'data_type': 'choice', 'options': deepcopy(field['options'])}
            elif known and field.get('locator', {}).get('unit'):
                constraint = {'version': 1, 'data_type': 'number', 'unit': field['locator']['unit']}
            if constraint is not None:
                questions[-1]['answer_constraints'] = deepcopy(constraint)
        anchors.append({'id': aid, 'question_id': qid, 'kind': 'existing',
                        'protected_signing': signing_protected(field['label'], signing_context),
                        'field_key': field['key'], 'locator': None})
    with ZipFile(path) as package:
        for part in package.infolist():
            raw = package.read(part)
            parts[part.filename] = hashlib.sha256(raw).hexdigest()
            if not part.filename.startswith('word/') or not part.filename.endswith('.xml'):
                continue
            tree = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True))
            visible = [node.text or '' for node in tree.iter(W+'t')]
            choices = [{'display': n.get(W+'displayText', ''), 'value': n.get(W+'value', '')}
                       for n in tree.iter(W+'listItem')]
            options.extend({'story': part.filename, **item} for item in choices)
            stories.append({'part': part.filename, 'texts': visible, 'choices': choices,
                            'text_sha256': digest(visible)})
            # Safe unmerged expanding rows with multiple possible answer cells need an
            # explicit doctor placement decision. No automatic choice is made from units
            # or neighbouring pre-filled columns.
            if not qualified:
                for row_index,row in enumerate(tree.iter(W+'tr')):
                    cells=row.findall(W+'tc')
                    label=''.join(cells[0].xpath('.//w:t/text()',namespaces=NS)).strip() if cells else ''
                    raw_empty=[c for c in cells[1:] if not ''.join(c.xpath('.//w:t/text()',namespaces=NS)).strip()]
                    blanks=[(i,c) for i,c in enumerate(cells[1:],1) if not occupied(c)]
                    if blanks and all((part.filename,c.getroottree().getpath(c)) in mapped_cells for _,c in blanks):continue
                    row_texts=[''.join(c.xpath('.//w:t/text()',namespaces=NS)).strip() for c in cells]
                    if len(cells)>2 and any(row_texts) and any(not occupied(c) for c in cells) and (not label or len(label)>120 or not TOKEN.fullmatch('{{'+label+'}}')):
                        issues.append({'code':'guided_layout','message':'A wide row with an unsupported question label contains an answer blank. Retain the complete question and give it a supported answer area.'});continue
                    if label and raw_empty and (len(blanks)!=len(raw_empty) or len(cells)<=2):
                        issues.append({'code':'guided_layout','message':label+': an unmapped answer region contains unsupported content.'});continue
                    if label and blanks and row.xpath('.//w:vMerge | .//w:gridSpan | .//w:tbl | ./w:trPr/w:trHeight[@w:hRule="exact"]',namespaces=NS):
                        issues.append({'code':'guided_layout','message':label+': merged, nested or fixed-height answer row needs assisted setup.'});continue
                    if ambiguous_signing(label, signing_context) and blanks:
                        issues.append({'code':'guided_signing','message':label+': clarify whether this is a clinical answer or a signing area before preparation.'});continue
                    if not label or len(label)>120 or not blanks or signing_protected(label, signing_context) or not TOKEN.fullmatch('{{'+label+'}}'):continue
                    other_text=[''.join(c.xpath('.//w:t/text()',namespaces=NS)).strip() for c in cells[1:] if occupied(c)]
                    units={'°C','°F','mm','cm','m','ms','s','mL','ml','L','kg','g','mg','%','bpm','mmHg','mm Hg','µm','μm','m/s'}
                    if len(other_text)>1 or any(t not in units for t in other_text):
                        issues.append({'code':'guided_layout','message':label+': neighbouring text may be another question; give every question its own labelled anchor.'});continue
                    qid,aid='q'+str(len(questions)+1),'a'+str(len(anchors)+1)
                    questions.append({'id':qid,'text':label,'story':part.filename,'protected_signing':False})
                    anchors.append({'id':aid,'question_id':qid,'kind':'choose_cell','protected_signing':False,
                        'field_key':None,'locator':{'part':part.filename,'row':row_index},
                        'choices':[{'id':'c'+str(i),'column':i,'description':'Original row '+str(row_index+1)+', answer column '+str(i+1)} for i,_ in blanks]})
            if not qualified and any(etree.QName(n).localname in UNSUPPORTED for n in tree.iter()):
                issues.append({'code': 'guided_layout', 'message':
                               'This original story contains controls or text boxes and needs assisted setup.'})
            for p_index, paragraph in enumerate(tree.iter(W+'p')):
                texts = list(paragraph.iter(W+'t'))
                complete = ''.join(n.text or '' for n in texts)
                # Plain one-line label + one literal blank. Never modify a cell, SDT,
                # drawing, field, line break or signing/consent area through this route.
                blank_count = len(BLANK.findall(complete))
                if not blank_count:
                    continue
                if ambiguous_signing(complete, signing_context):
                    issues.append({'code':'guided_signing','message':'Clarify whether Sign is a clinical answer or a signing area before preparation.'});continue
                protected = signing_protected(complete, signing_context)
                if protected:
                    qid, aid = 'q'+str(len(questions)+1), 'a'+str(len(anchors)+1)
                    questions.append({'id':qid,'text':complete,'story':part.filename,'protected_signing':True})
                    anchors.append({'id':aid,'question_id':qid,'kind':'protected_blank',
                                    'protected_signing':True,'field_key':None,'locator':None})
                    continue
                plain = all(etree.QName(n).localname in {'p', 'pPr', 'pStyle', 'spacing', 'ind',
                            'jc', 'keepNext', 'keepLines', 'r', 'rPr', 'b', 'i', 'u', 'sz',
                            'szCs', 'rFonts', 'color', 'lang', 't', 'proofErr'} for n in paragraph.iter())
                eligible = (blank_count == 1 and plain and not protected
                            and not any(n.tag in {W+'tc', W+'sdt', W+'txbxContent'}
                                        for n in paragraph.iterancestors()))
                match = BLANK.search(complete)
                label = complete[:match.start()].strip().rstrip(':').strip()
                eligible = eligible and bool(label) and bool(TOKEN.fullmatch('{{'+label+'}}'))
                node_index = next((i for i, n in enumerate(texts) if BLANK.search(n.text or '')), None)
                eligible = eligible and node_index is not None
                if node_index is not None:
                    local_match=BLANK.search(texts[node_index].text or '')
                    prefix=sum(len(n.text or '') for n in texts[:node_index])
                    eligible=eligible and (prefix+local_match.start()==match.start()
                                            and prefix+local_match.end()==match.end())
                if not eligible:
                    issues.append({'code': 'unresolved_blank', 'message': complete[:300],
                                   'protected_signing': protected, 'story': part.filename})
                    continue
                qid, aid = 'q'+str(len(questions)+1), 'a'+str(len(anchors)+1)
                questions.append({'id': qid, 'text': label, 'story': part.filename,
                                  'protected_signing': False,
                                  'answer_constraints': constraint_from_context(
                                      complete[:match.start()], complete[match.end():])})
                anchors.append({'id': aid, 'question_id': qid, 'kind': 'literal_blank',
                                'protected_signing': False, 'field_key': None,
                                'locator': {'part': part.filename, 'paragraph': p_index,
                                            'text': node_index, 'original': texts[node_index].text}})
    if not anchors:
        issues.append({'code': 'no_anchors', 'message': 'No safely writable answer areas were found.'})
    if len(anchors) > 100 or sum(len(x) for s in stories for x in s['texts']) > 80000:
        raise DocumentFailure('Split this form: preparation supports 100 answer areas and 80,000 visible characters.',
                              'preparation_limit')
    manual_rows=unmapped_multi_column_rows(path) if not qualified else []
    covered={(a['locator']['part'],a['locator']['row']) for a in anchors if a['kind']=='choose_cell'}
    uncovered=[row for row in manual_rows if (row['part'],row['row']) not in covered]
    if uncovered:
        issues.append({'code':'guided_layout','message':'A wide answer row has no complete labelled placement decision. Give every question and blank its own supported answer area.'})
    if manual_rows and not uncovered:
        if __package__:
            from .engine import UNMAPPED_NOTES
        else:
            from engine import UNMAPPED_NOTES
        exact=UNMAPPED_NOTES['multi_column'].format(count=len(manual_rows))
        warnings=[w for w in warnings if w!=exact]
    issues.extend({'code': 'mapping_warning', 'message': w} for w in warnings)
    result = {'protocol': protocol, 'source_sha256': source_sha, 'parts': parts,
              'stories': stories, 'options': options, 'questions': questions, 'anchors': anchors,
              'issues': issues, 'fields': fields, 'manual_rows':manual_rows,
              'review_requirements': deepcopy(known.get('review_requirements', [])) if known else [],
              'document_backend': {k: known[k] for k in ('backend', 'source_sha256', 'mapping_digest')}
                                  if qualified else {}}
    if signing_context is not None:
        result['signing_context'] = signing_context
    if question_context is not None:
        result['question_context'] = question_context
    result['inventory_sha256'] = digest(result)
    return result


def wm_source_review_context(value, mode):
    """Finite source evidence, never a verdict or permission to write/approve.

    This is explicitly opted into by a NEW preparation's immutable config.
    Original inventories and old role payloads are not upgraded in place.
    The exact package/mapping projection was independently checked against the
    tracked blank original, including its 28 linked glossary definitions.
    """
    validate_inventory(value)
    try:
        projection = {key: value[key] for key in ('protocol', 'source_sha256',
            'document_backend', 'parts', 'stories', 'fields', 'questions',
            'anchors', 'issues', 'manual_rows')}
        projection['review_requirements'] = [{key: row[key] for key in WM_REQUIREMENT_SOURCE_KEYS}
                                             for row in value['review_requirements']]
        valid = (type(mode) is str and mode == WM_SOURCE_REVIEW_CONTEXT
                 and value['protocol'] == TYPED_PROTOCOL
                 and value['source_sha256'] == WM_IOV_SHA256
                 and value['document_backend'] == {'backend': 'wm-iov-foss-v2',
                     'source_sha256': WM_IOV_SHA256,
                     'mapping_digest': '0fcc5e36dfe589a190a726f059c45b10364f3d02f312aea5fc8935d16ea05072'}
                 and digest(projection) == WM_SOURCE_REVIEW_SHA256)
    except (KeyError, TypeError):
        valid = False
    if not valid:
        raise DocumentFailure('The explicit WM source-review context is not bound to the qualified original.',
                              'stale_inventory')
    stories = {row['part']: 's'+str(index+1) for index, row in enumerate(value['stories'])}
    body_story, glossary_story = stories['word/document.xml'], stories['word/glossary/document.xml']
    by_key = {field['key']: anchor['id'] for field, anchor in zip(value['fields'], value['anchors'])}
    destinations, placeholders = [], []
    for field, anchor in zip(value['fields'], value['anchors']):
        locator = field['locator']
        if field['kind'] == 'choice':
            area = {'kind': 'original_dropdown', 'placeholder_definition': 'g'+str(len(placeholders)+1)}
            placeholders.append({'id': area['placeholder_definition'], 'body_anchor_id': anchor['id'],
                                 'original_text': 'Choose an item.'})
        elif 'body_paragraph' in locator:
            area = {'kind': 'original_labelled_body_blank'}
        elif field['kind'] == 'measurement':
            area = {'kind': 'original_measurement_cell', 'printed_unit': locator['unit']}
        else:
            area = {'kind': 'original_location_marker', 'printed_marker': locator['marker']}
        destinations.append({'anchor_id': anchor['id'], 'question_id': anchor['question_id'],
                             'original_label': field['label'], 'source_area': area})
    requirements = [{'id': 'r'+str(index+1), 'label': row['label'], 'kind': row['kind'],
                     'original_text': row['original_text'],
                     'original_text_sha256': row['original_text_sha256'],
                     'answer_anchor_ids': [by_key[key] for key in row['control_keys']],
                     'handling': ('explicit_clinician_evidence_and_review_each_use' if row['kind'] == 'assertion'
                                  else 'actual_finalization_time_only' if row['kind'] == 'signature'
                                  else 'actual_authenticated_signer_only')}
                    for index, row in enumerate(value['review_requirements'])]
    return {'protocol': mode, 'source_sha256': value['source_sha256'],
            'source_context_sha256': digest(projection),
            'body': {'story_id': body_story, 'answer_destinations': destinations,
                     'preserved_review_requirements': requirements},
            'glossary': {'story_id': glossary_story, 'kind': 'referenced_dropdown_placeholder_definitions',
                         'definitions': placeholders, 'operation': 'retain_unchanged'},
            'approval_policy': {'explicit_doctor_template_approval_required': True,
                                'clinical_statement_review_required_each_use': True,
                                'models_cannot_approve_or_write_documents': True}}


def model_inventory(value, *, source_review_context=None):
    """Closed public schema: paths, XML and internal locators never reach a model."""
    result = {'protocol': value['protocol'], 'inventory_sha256': value['inventory_sha256'],
            'stories': [{'id': 's'+str(i+1), 'texts': row['texts'], 'choices': row['choices'],
                         'content_sha256':digest({'texts':row['texts'],'choices':row['choices']})}
                        for i, row in enumerate(value['stories'])],
            'questions': [{k: q[k] for k in ('id', 'text', 'protected_signing', 'answer_constraints') if k in q}
                          for q in value['questions']],
            'anchors': [{**{k: a[k] for k in ('id', 'question_id', 'kind', 'protected_signing')},
                         **({'destinations': [{'id': item['id'], 'description': item['description']}
                                             for item in a['choices']]}
                            if value['protocol'] == TYPED_PROTOCOL and a['kind'] == 'choose_cell' else {})}
                        for a in value['anchors']], 'issues': [{k:issue[k] for k in ('code','message','protected_signing') if k in issue}
                                                              for issue in value['issues']]}
    if source_review_context is not None:
        result['source_review_context'] = wm_source_review_context(value, source_review_context)
    return result


def validate_role(value, response, role):
    validate_inventory(value)
    if role not in {'proposer','checker'}:
        raise DocumentFailure('Unsupported preparation role.', 'invalid_proposal')
    required = {'inventory_sha256', 'anchors','stories'}
    if not isinstance(response, dict) or set(response) != required or response['inventory_sha256'] != value['inventory_sha256']:
        raise DocumentFailure('The AI result is not bound to the complete original inventory.', 'invalid_proposal')
    rows = response['anchors']
    if not isinstance(rows, list) or len(rows) != len(value['anchors']):
        raise DocumentFailure('Every answer area needs a result; none can be omitted.', 'incomplete_proposal')
    expected = {a['id']: a for a in value['anchors']}
    seen = set()
    for row in rows:
        keys = {'anchor_id', 'question_id', 'decision'} if role == 'proposer' else {'anchor_id', 'question_id', 'verdict'}
        if value['protocol'] == TYPED_PROTOCOL:
            keys.add('metadata')
        if not isinstance(row, dict) or set(row) != keys or row.get('anchor_id') not in expected or row['anchor_id'] in seen:
            raise DocumentFailure('The AI returned an unknown or duplicate answer area.', 'invalid_proposal')
        anchor = expected[row['anchor_id']]
        if row['question_id'] != anchor['question_id']:
            raise DocumentFailure('The proposed answer would move to a different question.', 'wrong_placement')
        choice = row.get('decision') if role == 'proposer' else row.get('verdict')
        if choice not in ({'map', 'needs_review'} if role == 'proposer' else {'pass', 'unresolved'}):
            raise DocumentFailure('The AI result has an unsupported state.', 'invalid_proposal')
        if value['protocol'] == TYPED_PROTOCOL:
            if __package__:
                from .preparation_roles import validate_metadata_row
            else:
                from preparation_roles import validate_metadata_row
            validate_metadata_row(value, anchor, row)
        seen.add(row['anchor_id'])
    story_rows=response['stories']
    expected_stories=model_inventory(value)['stories']
    if not isinstance(story_rows,list) or len(story_rows)!=len(expected_stories):
        raise DocumentFailure('Every original story needs a preservation check.', 'incomplete_proposal')
    by_id={s['id']:s for s in expected_stories};seen=set()
    for row in story_rows:
        if (not isinstance(row,dict) or set(row)!={'story_id','content_sha256','verdict'}
                or row.get('story_id') not in by_id or row['story_id'] in seen
                or row['content_sha256']!=by_id[row['story_id']]['content_sha256']
                or row['verdict'] not in {'retain','unresolved'}):
            raise DocumentFailure('The complete original content was not checked.', 'incomplete_proposal')
        seen.add(row['story_id'])
    return response

def validate_inventory(value):
    if (not isinstance(value,dict) or value.get('protocol') not in {PROTOCOL, TYPED_PROTOCOL}
            or value.get('inventory_sha256')!=digest({k:v for k,v in value.items() if k!='inventory_sha256'})):
        raise DocumentFailure('The original inventory changed.', 'stale_inventory')
    if 'signing_context' in value and (value['signing_context'] != SIGNING_CONTEXT
            or value['protocol'] != TYPED_PROTOCOL or value.get('document_backend')):
        raise DocumentFailure('Unsupported signing classification policy.', 'stale_inventory')
    if 'question_context' in value and (value['question_context'] != QUESTION_CONTEXT
            or type(value['question_context']) is not str
            or value['protocol'] != TYPED_PROTOCOL or value.get('document_backend')):
        raise DocumentFailure('Unsupported explicit source-question context.', 'stale_inventory')
    return value

def validate_candidate_fields(value,fields,*,constraints=False):
    from collections import Counter
    questions={q['id']:q for q in value['questions']}
    expected=[questions[a['question_id']]['text'] for a in value['anchors'] if a['kind']!='protected_blank']
    if len(fields)!=len(expected) or Counter(f['label'] for f in fields)!=Counter(expected):
        raise DocumentFailure('The candidate omitted or changed an original question mapping.', 'incomplete_proposal')
    if constraints:
        expected_constraints = Counter((questions[a['question_id']]['text'],
                                         digest(questions[a['question_id']].get('answer_constraints')))
                                        for a in value['anchors'] if a['kind'] != 'protected_blank')
        actual_constraints = Counter((field['label'], digest(field.get('answer_constraints'))) for field in fields)
        if expected_constraints != actual_constraints:
            raise DocumentFailure('The candidate omitted or changed an original answer constraint.', 'incomplete_proposal')
    return fields


def candidate(path, output, expected, selected,placements=None):
    # Re-derive against current immutable bytes; a stored/model-supplied locator has no authority.
    validate_inventory(expected)
    known = None
    if expected.get('document_backend'):
        known = {**expected['document_backend'], 'sha256': expected['source_sha256'],
                 'fields': expected['fields'], 'review_requirements': expected['review_requirements']}
    actual = inventory(path, known, protocol=expected['protocol'], signing_context=expected.get('signing_context'),
                       question_context=expected.get('question_context'))
    if actual != expected or not isinstance(selected, list) or len(set(selected)) != len(selected):
        raise DocumentFailure('The candidate request uses a stale inventory.', 'stale_inventory')
    if actual['issues']:
        raise DocumentFailure('Resolve every original answer area before creating a candidate.', 'guided_layout')
    allowed = {a['id']: a for a in actual['anchors']}
    if set(selected) != set(allowed):
        raise DocumentFailure('All answer areas must be covered before a candidate is prepared.', 'incomplete_proposal')
    placements=placements or {}
    placeable={a['id']:a for a in actual['anchors'] if a['kind']=='choose_cell'}
    if not isinstance(placements,dict) or set(placements)!=set(placeable) or any(
            placements[k] not in {c['id'] for c in a['choices']} for k,a in placeable.items()):
        raise DocumentFailure('Choose an exact original answer cell for each ambiguous question.', 'placement_required')
    questions = {q['id']: q for q in actual['questions']}
    replacements = {}
    changes = []
    for anchor in actual['anchors']:
        if anchor['kind'] not in {'literal_blank','choose_cell'}:
            continue
        location = anchor['locator']
        replacements.setdefault(location['part'], []).append(anchor)
        changes.append({'anchor_id': anchor['id'], 'question': questions[anchor['question_id']]['text'],
                        'change': ('Insert an answer anchor in the explicitly selected empty cell; retain every other cell.'
                                   if anchor['kind']=='choose_cell' else 'Replace this literal blank with a reusable answer anchor.'),
                        'placement':next((c['description'] for c in anchor.get('choices',[]) if c['id']==placements.get(anchor['id'])), '')})
    if not replacements:
        output.write_bytes(path.read_bytes())
    else:
        with ZipFile(path) as incoming, ZipFile(output, 'w') as outgoing:
            outgoing.comment=incoming.comment
            for part in incoming.infolist():
                raw = incoming.read(part)
                if part.filename in replacements:
                    tree = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True))
                    paragraphs = list(tree.iter(W+'p'))
                    whole=tree.getroottree()
                    before = etree.tostring(whole, method='c14n')
                    undo = []
                    for anchor in replacements[part.filename]:
                        loc = anchor['locator']
                        label = questions[anchor['question_id']]['text']
                        if anchor['kind']=='choose_cell':
                            row=list(tree.iter(W+'tr'))[loc['row']]
                            column=next(c['column'] for c in anchor['choices'] if c['id']==placements[anchor['id']])
                            cell=row.findall(W+'tc')[column]
                            if occupied(cell):raise DocumentFailure('The selected answer cell is no longer blank.', 'stale_inventory')
                            p=cell.find(W+'p');run=etree.SubElement(p,W+'r');node=etree.SubElement(run,W+'t')
                            node.text='{{'+label+'}}';undo.append((run,None,None))
                        else:
                            node = list(paragraphs[loc['paragraph']].iter(W+'t'))[loc['text']]
                            old = node.text;node.text = BLANK.sub('{{'+label+'}}', old, count=1)
                            undo.append((node, old, node.text))
                    raw = etree.tostring(whole, xml_declaration=True, encoding='UTF-8', standalone=True)
                    # Prove every XML node/attribute/text outside the exact blank substitutions stayed.
                    for node, old, _ in undo:
                        if old is None:node.getparent().remove(node)
                        else:node.text = old
                    if etree.tostring(whole, method='c14n') != before:
                        raise DocumentFailure('Candidate preparation changed protected document content.', 'content_changed')
                outgoing.writestr(part, raw)
    # Complete ZIP population and every untouched part must stay byte-identical.
    with ZipFile(path) as original, ZipFile(output) as prepared:
        if original.namelist() != prepared.namelist() or any(original.read(n) != prepared.read(n)
                         for n in original.namelist() if n not in replacements):
            raise DocumentFailure('Candidate preparation changed an unrelated document part.', 'content_changed')
    remaining_rows=unmapped_multi_column_rows(output) if not known else []
    reviewed={(a['locator']['part'],a['locator']['row']) for a in placeable.values()}
    if any((row['part'],row['row']) not in reviewed for row in remaining_rows):
        raise DocumentFailure('An unreviewed answer-shaped row remains in the candidate.', 'incomplete_proposal')
    fields = deepcopy(actual['fields']) if known else source_bound_candidate_fields(output, actual)
    if actual['protocol'] == TYPED_PROTOCOL and not known:
        fields = typed_source_fields(output, fields, signing_context=actual.get('signing_context'),
                                     question_context=actual.get('question_context'))
    # The qualified WM writer already enforces its pinned choices and units.
    # Its original mapping stays byte-for-byte compatible with older approvals.
    validate_candidate_fields(actual, fields, constraints=not (known and actual['protocol'] == TYPED_PROTOCOL))
    return {'changes': changes, 'source_sha256': actual['source_sha256'], 'prepared_fields': fields,
            'inventory_sha256': actual['inventory_sha256'], 'parts_preserved': True,
            'reviewed_multi_column_rows':remaining_rows}
