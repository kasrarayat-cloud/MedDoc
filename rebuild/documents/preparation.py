"""Finite blank-form inventory and ZIP-part preserving candidate writer.

Runs in the document sandbox. AI sees question/anchor IDs and visible source text,
never locators or XML. The original package is always the authority.
"""
from copy import deepcopy
import hashlib
import json
import re
from zipfile import ZipFile
from lxml import etree

if __package__:
    from .engine import validate_docx, docx_inspect, DocumentFailure, TOKEN, W_NS
else:
    from engine import validate_docx, docx_inspect, DocumentFailure, TOKEN, W_NS

NS = {'w': W_NS}
W = '{'+W_NS+'}'
PROTOCOL = 'blank-word-preparation-v1'
SIGNING = re.compile(r'\b(?:signatures?|signed|signing|attest(?:ation|ed|ing)?|certif(?:ication|ied|y)|consent(?:ed|ing)?)\b'
                     r'|\bsign\s+(?:here|below|above|by|and\s+date)\b'
                     r'|\b(?:please|patient|clinician|physician|doctor|provider)\s+sign\b', re.I)
# Unknown singular signing language is guided, never made writable. Plural
# clinical signs and embedded words do not match this word-boundary predicate.
AMBIGUOUS_SIGNING = re.compile(r'\bsign\b', re.I)
BLANK = re.compile(r'_{3,}')
UNSUPPORTED = {'sdt', 'txbxContent', 'fldChar', 'fldSimple', 'instrText', 'del', 'ins'}

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


def inventory(path, known=None):
    validate_docx(path, inventory_only=True)
    source_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if known and known.get('sha256') != source_sha:
        raise DocumentFailure('The mapping is not bound to this original.', 'stale_mapping')
    stories, parts, options, anchors, questions, issues = [], {}, [], [], [], []
    qualified = bool(known and known.get('backend') == 'wm-iov-foss-v2')
    if known:
        if __package__:
            from .sdk_service import WM_IOV_SHA256
        else:
            from sdk_service import WM_IOV_SHA256
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
    for field in fields:
        if AMBIGUOUS_SIGNING.search(field['label']) and not SIGNING.search(field['label']):
            issues.append({'code':'guided_signing','message':field['label']+': clarify whether this is a clinical answer or a signing area before preparation.'})
        qid, aid = 'q'+str(len(questions)+1), 'a'+str(len(anchors)+1)
        questions.append({'id': qid, 'text': field['label'], 'story': 'mapped',
                          'protected_signing': bool(SIGNING.search(field['label']))})
        anchors.append({'id': aid, 'question_id': qid, 'kind': 'existing',
                        'protected_signing': bool(SIGNING.search(field['label'])),
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
                    if AMBIGUOUS_SIGNING.search(label) and not SIGNING.search(label) and blanks:
                        issues.append({'code':'guided_signing','message':label+': clarify whether this is a clinical answer or a signing area before preparation.'});continue
                    if not label or len(label)>120 or not blanks or SIGNING.search(label) or not TOKEN.fullmatch('{{'+label+'}}'):continue
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
                if AMBIGUOUS_SIGNING.search(complete) and not SIGNING.search(complete):
                    issues.append({'code':'guided_signing','message':'Clarify whether Sign is a clinical answer or a signing area before preparation.'});continue
                protected = bool(SIGNING.search(complete))
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
                                  'protected_signing': False})
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
    result = {'protocol': PROTOCOL, 'source_sha256': source_sha, 'parts': parts,
              'stories': stories, 'options': options, 'questions': questions, 'anchors': anchors,
              'issues': issues, 'fields': fields, 'manual_rows':manual_rows,
              'review_requirements': deepcopy(known.get('review_requirements', [])) if known else [],
              'document_backend': {k: known[k] for k in ('backend', 'source_sha256', 'mapping_digest')}
                                  if qualified else {}}
    result['inventory_sha256'] = digest(result)
    return result


def model_inventory(value):
    """Closed public schema: paths, XML and internal locators never reach a model."""
    return {'protocol': PROTOCOL, 'inventory_sha256': value['inventory_sha256'],
            'stories': [{'id': 's'+str(i+1), 'texts': row['texts'], 'choices': row['choices'],
                         'content_sha256':digest({'texts':row['texts'],'choices':row['choices']})}
                        for i, row in enumerate(value['stories'])],
            'questions': [{k: q[k] for k in ('id', 'text', 'protected_signing')} for q in value['questions']],
            'anchors': [{k: a[k] for k in ('id', 'question_id', 'kind', 'protected_signing')}
                        for a in value['anchors']], 'issues': [{k:issue[k] for k in ('code','message','protected_signing') if k in issue}
                                                              for issue in value['issues']]}


def validate_role(value, response, role):
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
        if not isinstance(row, dict) or set(row) != keys or row.get('anchor_id') not in expected or row['anchor_id'] in seen:
            raise DocumentFailure('The AI returned an unknown or duplicate answer area.', 'invalid_proposal')
        anchor = expected[row['anchor_id']]
        if row['question_id'] != anchor['question_id']:
            raise DocumentFailure('The proposed answer would move to a different question.', 'wrong_placement')
        choice = row.get('decision') if role == 'proposer' else row.get('verdict')
        if choice not in ({'map', 'needs_review'} if role == 'proposer' else {'pass', 'unresolved'}):
            raise DocumentFailure('The AI result has an unsupported state.', 'invalid_proposal')
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
    if (not isinstance(value,dict) or value.get('protocol')!=PROTOCOL
            or value.get('inventory_sha256')!=digest({k:v for k,v in value.items() if k!='inventory_sha256'})):
        raise DocumentFailure('The original inventory changed.', 'stale_inventory')
    return value

def validate_candidate_fields(value,fields):
    from collections import Counter
    questions={q['id']:q for q in value['questions']}
    expected=[questions[a['question_id']]['text'] for a in value['anchors'] if a['kind']!='protected_blank']
    if len(fields)!=len(expected) or Counter(f['label'] for f in fields)!=Counter(expected):
        raise DocumentFailure('The candidate omitted or changed an original question mapping.', 'incomplete_proposal')
    return fields


def candidate(path, output, expected, selected,placements=None):
    # Re-derive against current immutable bytes; a stored/model-supplied locator has no authority.
    validate_inventory(expected)
    known = None
    if expected.get('document_backend'):
        known = {**expected['document_backend'], 'sha256': expected['source_sha256'],
                 'fields': expected['fields'], 'review_requirements': expected['review_requirements']}
    actual = inventory(path, known)
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
    return {'changes': changes, 'source_sha256': actual['source_sha256'],
            'inventory_sha256': actual['inventory_sha256'], 'parts_preserved': True,
            'reviewed_multi_column_rows':remaining_rows}
