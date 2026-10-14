"""Pure, versioned ICD-10-CM Index -> Tabular reference operations.

This module does not infer diagnoses, perform network/DB IO, or accept model
codes. Search returns source-owned Index entries; validation is a separate,
conservative check against the complete official reportable-code dictionary.
"""
from copy import deepcopy
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET


FORMAT = 'icd10cm-index-tabular-v1'
MAX_XML_BYTES = 32 * 1024 * 1024
CODE = re.compile(r'[A-Z][A-Z0-9]{2}(?:\.[A-Z0-9]{1,4}|[A-Z0-9]{0,4})\Z')
_REF_ATOM = r'[A-Z](?:[0-9][A-Z0-9]|[A-Z][0-9])(?:\.[A-Z0-9]{1,4})?'
REFERENCE_CODE = re.compile(
    rf'(?<![A-Za-z0-9]){_REF_ATOM}(?:\.-|-(?:{_REF_ATOM})?)?(?![A-Za-z0-9])')
INSTRUCTION_TAGS = {
    'includes', 'inclusionTerm', 'excludes1', 'excludes2', 'codeFirst',
    'useAdditionalCode', 'codeAlso', 'sevenChrNote', 'sevenChrDef', 'notes',
    'visualImpairment',
}
# Exact normalized official notes, independently compared in FY2026 October,
# FY2026 April and FY2027 XML. These are classification guidance, not patient-specific
# sequencing requirements. New wording/year must be reviewed, not auto-waived.
GENERAL_GUIDANCE_HASHES = {
    'chapter:18': {
        '063df319ddfa7358cc50c18ae92abe4744a13cfaf4366a60d0aec7136824c3fe',
        '8cc5dec5810cd2ea6136145ce937d8ccf71a1d444018b4dd3829330a17808889',
        'f945b1ba8c5a99e2485ec6aa15af09ffa0bbc9015fd81a146eff8fbd3478b015',
        'e3df0429f8f15ffab649ed9834f86dc2e316501f34968ed69a0d6b8caafa7f62',
        '507419d2a99a0cb70a1e623a8edaddc05785d7ad62d12e88fe649555db6f0f3b',
        '7752f1336bb424c20b93b0079827dcce787fe86cf8bc83d68daa579e58000f75',
        'b545413f511edc6149694b030bd22dcf52418f3e888a4d30366971fefafc3f1c',
        'ed10d9bd12f0b9886c79325fb295d201952a200d8fad60831fd7a4b9f2713ca2',
        'ab0718f5b7567458114ea03e8bf25b41f56a075b2c10e5431bdc96ea3e5bf759',
    },
    'chapter:21': {
        '10e65ce93ab08eccb4f6f71f9c1f3bed1fa5f13b6730822fc3faed7f678872f9',
        '773a0e07abd74b543a1fb7bb8056972ea385bd545f8de10a16bbb194b208334b',
        'd515d47395a3a42b5c2b9b7f26181101346f775e5006d189f04a7ba069f4efc8',
    },
    'section:Z00-Z13': {
        '49b44cea7e0155483a83b2eaabef474f509cc1cc9b852f1836a96ca2431e4c99',
    },
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def reference_digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def normalize_code(value):
    if not isinstance(value, str) or not CODE.fullmatch(value.strip().upper()):
        raise ValueError('Invalid ICD-10-CM code syntax.')
    value = value.strip().upper().replace('.', '')
    if not any(c.isdigit() for c in value):
        raise ValueError('Invalid ICD-10-CM code syntax.')
    return value[:3] + ('.' + value[3:] if len(value) > 3 else '')


def _xml(payload, root_name):
    if isinstance(payload, str):
        payload = payload.encode('utf-8')
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_XML_BYTES:
        raise ValueError('Reference XML must be nonempty and at most 32 MiB.')
    if re.search(br'<!\s*(?:DOCTYPE|ENTITY)\b', payload, re.I):
        raise ValueError('DTD/entity declarations are not accepted in reference XML.')
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError('Malformed reference XML.') from exc
    if root.tag != root_name or len(root.findall('version')) != 1:
        raise ValueError('Wrong ICD-10-CM XML document type/version.')
    version = (root.findtext('version') or '').strip()
    if not re.fullmatch(r'20\d\d', version):
        raise ValueError('An explicit ICD-10-CM fiscal-year version is required.')
    return root, version, hashlib.sha256(payload).hexdigest()


def _text(element):
    return ' '.join(''.join(element.itertext()).split()) if element is not None else ''


def _title(element):
    title = element.find('title')
    if len(element.findall('title')) != 1 or title is None or not _text(title):
        raise ValueError('An Index term is missing its title.')
    if any(child.tag != 'nemod' for child in title):
        raise ValueError('Unrecognized Index title markup.')
    modifiers = [_text(n) for n in title.findall('nemod')]
    core = (title.text or '') + ''.join(n.tail or '' for n in title)
    return _text(title), ' '.join(core.split()), modifiers


def _tokens(value):
    value = unicodedata.normalize('NFKC', value).casefold()
    words = re.findall(r'[^\W_]+', value, re.UNICODE)
    # Inflection only, not an invented medical synonym catalogue.
    return [w[:-3] + 'y' if len(w) > 4 and w.endswith('ies') else
            w[:-1] if len(w) > 3 and w.endswith('s') and not w.endswith('ss') else w
            for w in words if w not in {'the', 'a', 'an', 'of', 'and'}]


def _cross_key(value):
    return ' '.join(_tokens(re.sub(r'\([^)]*\)', '', value)))


def _references(text):
    refs = []
    for match in REFERENCE_CODE.finditer(text):
        raw = match.group(0)
        if '-' in raw:
            start, end = raw.split('-', 1)
            refs.append({'raw': raw, 'kind': 'range' if end else 'prefix',
                         'start': start.replace('.', ''), 'end': end.replace('.', '')})
        else:
            refs.append({'raw': raw, 'kind': 'code_or_category',
                         'start': raw.replace('.', ''), 'end': ''})
    return refs


def _instruction_metadata(note, version):
    metadata = {'scope': 'unresolved', 'rule': None, 'condition': None}
    digest = hashlib.sha256(note['text'].encode()).hexdigest()
    if (version in {'2026', '2027'} and note['kind'] == 'notes'
            and digest in GENERAL_GUIDANCE_HASHES.get(note['source_id'], set())):
        metadata.update(scope='general_guidance', rule='chapter_guidance')
    elif (version in {'2026', '2027'} and note['kind'] == 'codeAlso'
          and note['source_id'] == 'section:Z77-Z99'
          and note['text'] == 'any follow-up examination (Z08-Z09)'):
        metadata.update(scope='conditional', rule='post_treatment_follow_up',
                        condition='documented_post_treatment_follow_up',
                        related_codes=['Z08', 'Z09'], guideline='I.C.21.c.8')
    elif (version in {'2026', '2027'} and note['kind'] == 'codeFirst'
          and note['source_id'] == 'Z86'
          and note['text'] == 'any follow-up examination after treatment (Z09)'):
        metadata.update(scope='conditional', rule='post_treatment_follow_up',
                        condition='documented_post_treatment_follow_up',
                        related_codes=['Z09'], guideline='I.C.21.c.8')
    elif (version in {'2026', '2027'} and note['kind'] == 'useAdditionalCode'
          and note['source_id'] == 'Z12'
          and note['text'] == 'code to identify any family history of malignant neoplasm (Z80.-)'):
        metadata.update(scope='conditional', rule='family_history_malignancy',
                        condition='documented_family_history_malignancy',
                        related_codes=['Z80.-'], guideline='I.C.21.c.4')
    elif (version in {'2026', '2027'} and note['kind'] == 'excludes1'
          and note['source_id'] == 'Z12'
          and note['text'] == 'encounter for diagnostic examination-code to sign or symptom'):
        metadata.update(scope='conditional', rule='screening_versus_diagnostic_exam',
                        condition='affirmative_asymptomatic_screening_without_active_symptoms',
                        guideline='I.C.21.c.5')
    elif note['kind'] in {'includes', 'inclusionTerm', 'excludes2', 'sevenChrNote', 'sevenChrDef'}:
        metadata.update(scope='classification_guidance')
    elif note['kind'] == 'excludes1':
        metadata.update(scope='conditional', rule='excludes1_selected_code_conflict')
    return metadata


def _instructions(element, source, version):
    instructions = []
    for child in element:
        if child.tag not in INSTRUCTION_TAGS:
            continue
        if child.tag == 'sevenChrDef':
            extensions = [{'character': n.attrib.get('char', ''), 'text': _text(n)}
                          for n in child.findall('extension')]
            if not extensions or any(not re.fullmatch(r'[A-Z0-9]', e['character'])
                                     or not e['text'] for e in extensions):
                raise ValueError('Malformed seventh-character definition.')
            if len({e['character'] for e in extensions}) != len(extensions):
                raise ValueError('Duplicate seventh-character definition.')
            instructions.append({'kind': child.tag, 'text': _text(child),
                                 'source_id': source, 'extensions': extensions,
                                 'references': []})
            continue
        notes = child.findall('note')
        for note in notes or [child]:
            text = _text(note)
            instructions.append({'kind': child.tag, 'text': text, 'source_id': source,
                                 'references': _references(text), 'empty_source_note': not bool(text)})
    for ordinal, note in enumerate(instructions):
        note['id'] = 'instruction:' + reference_digest({'version': version, 'ordinal': ordinal, **note})
        note.update(_instruction_metadata(note, version))
    return instructions


def _governing_node(nodes, code):
    raw = code.replace('.', '')
    for length in range(len(raw), 2, -1):
        prefix = raw[:length]
        candidate = prefix[:3] + ('.' + prefix[3:] if length > 3 else '')
        if candidate in nodes and nodes[candidate]['kind'] == 'diag':
            return candidate
    return None


def parse_reference(index_xml, tabular_xml, code_dictionary):
    """Parse full official XML; dictionary is code -> official long description.

    XML leaf count is NOT code count: the codes file contains required seventh
    character expansions that do not have a separate Tabular XML leaf.
    """
    index_root, version, index_sha = _xml(index_xml, 'ICD10CM.index')
    tab_root, tab_version, tab_sha = _xml(tabular_xml, 'ICD10CM.tabular')
    if version != tab_version:
        raise ValueError('Index and Tabular fiscal-year versions differ.')
    if (any(n.tag not in {'version', 'title', 'letter'} for n in index_root)
            or any(n.tag not in {'version', 'introduction', 'chapter'} for n in tab_root)
            or any(n.tag not in {'title', 'mainTerm'}
                   for letter in index_root.findall('letter') for n in letter)):
        raise ValueError('Unrecognized reference document structure.')
    if not isinstance(code_dictionary, dict) or not code_dictionary:
        raise ValueError('A complete reportable-code dictionary is required.')
    codes = {}
    for raw_code, description in code_dictionary.items():
        code = normalize_code(raw_code)
        if code in codes:
            raise ValueError('Duplicate normalized code in dictionary.')
        if (not isinstance(description, str) or not description.strip()
                or len(description) > 500 or any(unicodedata.category(c).startswith('C')
                                                for c in description)):
            raise ValueError('Invalid dictionary description.')
        codes[code] = description

    entries = []
    seen_ids = set()
    path_ids = {}

    def index_term(element, path, core_path, parent_id, locator):
        title, core, modifiers = _title(element)
        full_path, full_core = path + [title], core_path + [core]
        if len(full_path) > 32:
            raise ValueError('Index hierarchy exceeds its bounded depth.')
        identifier = 'idx:' + reference_digest({'version': version, 'path': full_path,
                                                'locator': locator})
        if identifier in seen_ids:
            raise ValueError('Duplicate Index entry identity.')
        seen_ids.add(identifier)
        code = element.findtext('code')
        code = code.strip() if code else None
        entry = {'id': identifier, 'path': full_path, 'title': title, 'term': core,
                 'nonessential_modifiers': modifiers, 'parent_id': parent_id,
                 'children': [], 'code': code, 'default_code': code,
                 'see': [_text(n) for n in element.findall('see')],
                 'see_also': [_text(n) for n in element.findall('seeAlso')],
                 'see_category': [_text(n) for n in element.findall('seecat')],
                 'manifestation': [_text(n) for n in element.findall('manif')],
                 'subcategory': [_text(n) for n in element.findall('subcat')],
                 'cross_references': [], 'search_tokens': sorted(set(_tokens(' '.join(full_path)))),
                 'head_tokens': sorted(set(_tokens(core)))}
        allowed = {'title', 'code', 'see', 'seeAlso', 'seecat', 'manif', 'subcat', 'term'}
        if any(n.tag not in allowed for n in element):
            raise ValueError('Unrecognized Index structure must be reviewed before import.')
        if len(element.findall('code')) > 1:
            raise ValueError('Multiple default codes on one Index entry.')
        entries.append(entry)
        path_ids.setdefault(_cross_key(', '.join(full_core)), []).append(identifier)
        for ordinal, child in enumerate(element.findall('term')):
            child_id = index_term(child, full_path, full_core, identifier, locator + [ordinal])
            entry['children'].append(child_id)
        return identifier

    for letter_no, letter in enumerate(index_root.findall('letter')):
        for term_no, term in enumerate(letter.findall('mainTerm')):
            index_term(term, [], [], None, [letter_no, term_no])
    if not entries:
        raise ValueError('Index contains no main terms.')
    for entry in entries:
        for kind in ['see', 'see_also', 'see_category']:
            for target in entry[kind]:
                matches = path_ids.get(_cross_key(target), [])
                entry['cross_references'].append({'kind': kind, 'target': target,
                                                  'resolved_ids': matches,
                                                  'resolved': len(matches) == 1})
        # A mandatory See directs the caller to the target entry. A See also is
        # advisory when this entry already supplies the applicable code (I.A.17).
        entry['requires_review'] = bool(
            entry['see'] or entry['see_category'] or entry['manifestation']
            or entry['subcategory'] or not entry['code'])

    nodes = {}

    def tabular_node(element, parent=None):
        kind = element.tag
        if kind == 'diag':
            identifier = normalize_code(element.findtext('name') or '')
        elif kind == 'chapter':
            identifier = 'chapter:' + (element.findtext('name') or '')
        else:
            identifier = 'section:' + element.attrib.get('id', '')
        if identifier in nodes or identifier.endswith(':'):
            raise ValueError('Missing or duplicate Tabular identity.')
        node = {'id': identifier, 'kind': kind, 'description': _text(element.find('desc')),
                'parent': parent, 'children': [], 'instructions': _instructions(element, identifier, version)}
        allowed = {'name', 'desc', 'chapter', 'section', 'diag', 'sectionIndex'} | INSTRUCTION_TAGS
        if any(child.tag not in allowed for child in element):
            raise ValueError('Unrecognized Tabular structure must be reviewed before import.')
        nodes[identifier] = node
        for child in element:
            if child.tag in {'section', 'diag'}:
                node['children'].append(tabular_node(child, identifier))
        return identifier

    for chapter in tab_root.findall('chapter'):
        tabular_node(chapter)
    if not nodes:
        raise ValueError('Tabular contains no chapters.')
    for code in codes:
        if _governing_node(nodes, code) is None:
            raise ValueError(f'Dictionary code {code} has no governing Tabular node.')
    tabular = {'format': FORMAT, 'version': version, 'codes': codes, 'nodes': nodes,
               'dictionary_sha256': reference_digest(codes),
               'index_xml_sha256': index_sha, 'tabular_xml_sha256': tab_sha,
               'introduction': ET.tostring(tab_root.find('introduction'), encoding='unicode')
               if tab_root.find('introduction') is not None else ''}
    return {'index': entries, 'tabular': tabular}


def _parts(reference):
    if isinstance(reference, dict):
        index, tabular = reference.get('index'), reference.get('tabular')
    else:
        index, tabular = getattr(reference, 'index', None), getattr(reference, 'tabular', None)
    if not isinstance(index, list) or not isinstance(tabular, dict) or tabular.get('format') != FORMAT:
        raise ValueError('Unsupported or absent coding reference.')
    return index, tabular


def search_index(reference, terms, limit=30):
    """Lexical search of Index paths ONLY; never model codes/descriptions.

    Exact Index heads with a default code are kept alongside qualified children.
    Family/personal/screening query qualifiers cannot disappear during search.
    Cross-reference targets are exposed only when the exact path resolves.
    """
    index, _ = _parts(reference)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Search limit must be an integer from 1 through 100.')
    if isinstance(terms, str):
        terms = [terms]
    if (not isinstance(terms, (list, tuple)) or not 1 <= len(terms) <= 20
            or any(not isinstance(t, str) or len(t) > 300 for t in terms)):
        raise ValueError('Search terms must be short clinical terms.')
    queries = [set(_tokens(t)) for t in terms
               if not (CODE.fullmatch(t.strip().upper()) and any(c.isdigit() for c in t))]
    queries = [q for q in queries if q]
    scored = []
    for entry in index:
        words, head = set(entry['search_tokens']), set(entry['head_tokens'])
        best = None
        for query in queries:
            qualifiers = query & {'family', 'personal', 'screening', 'history'}
            if not qualifiers <= words or not query <= words:
                continue
            exact = query == head
            score = (int(exact), len(query & head), -len(words - query), -len(entry['path']))
            best = max(best, score) if best is not None else score
        if best is not None:
            scored.append((best, entry['id'], entry))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    result = [deepcopy(row[2]) for row in scored[:limit]]
    # The returned target is itself an authoritative selectable entry, not a
    # fabricated code attached to the alias. Unresolved references stay visible.
    ids = {entry['id'] for entry in result}
    by_id = {entry['id']: entry for entry in index}
    for entry in list(result):
        for cross in entry['cross_references']:
            if cross['resolved'] and len(result) < limit:
                target = cross['resolved_ids'][0]
                if target not in ids:
                    result.append(deepcopy(by_id[target])); ids.add(target)
    return result


def _matches(raw_code, ref):
    code = raw_code.replace('.', '')
    if ref['kind'] in {'prefix', 'code_or_category'}:
        return code.startswith(ref['start'])
    start, end = ref['start'], ref['end']
    length = min(len(start), len(end))
    return start[:length] <= code[:length] <= end[:length]


def validate_code(reference, code, selected_codes=None):
    """Return deterministic reportability and *all* inherited instructions.

    This cannot decide clinical relevance or satisfy prose sequencing/etiology
    conditions. Such requirements are explicitly held for review, even when a
    referenced code happens to be among the selections.
    """
    _, tabular = _parts(reference)
    result = {'valid': False, 'code': code if isinstance(code, str) else '',
              'description': '', 'reportable': False, 'instructions': [],
              'errors': [], 'requires_review': False, 'review_instruction_ids': [],
              'unresolved_instructions': [], 'governing_node': None}
    try:
        code = normalize_code(code)
    except ValueError:
        result['errors'].append('invalid_code_syntax'); return result
    result['code'] = code
    if code not in tabular['codes']:
        result['errors'].append('not_reportable_in_release'); return result
    result['reportable'] = True
    result['description'] = tabular['codes'][code]
    nodes = tabular['nodes']; current = _governing_node(nodes, code)
    result['governing_node'] = current
    if current is None:
        result['errors'].append('missing_tabular_binding'); return result
    chain, seen = [], set()
    while current is not None:
        if current in seen or current not in nodes or len(seen) > 32:
            result['errors'].append('invalid_tabular_ancestry'); return result
        seen.add(current); chain.append(nodes[current]); current = nodes[current]['parent']
    instructions = [deepcopy(note) for node in reversed(chain) for note in node['instructions']]
    result['instructions'] = instructions
    selected = None
    if selected_codes is not None:
        if not isinstance(selected_codes, (list, tuple, set)) or len(selected_codes) > 1000:
            result['errors'].append('invalid_selected_code_set'); return result
        try:
            selected = [normalize_code(c) for c in selected_codes]
        except ValueError:
            result['errors'].append('invalid_selected_code_set'); return result
        if any(c not in tabular['codes'] for c in selected):
            result['errors'].append('selected_code_not_reportable'); return result
    for note in instructions:
        kind = note['kind']; note['requires_review'] = False
        # Recompute classification from exact source text, not a caller-supplied
        # scope flag. Context-dependent resolution belongs to the coding engine.
        note.update(_instruction_metadata(note, tabular['version']))
        if note.get('empty_source_note'):
            note['requires_review'] = True
        elif note['scope'] == 'general_guidance':
            pass
        elif kind in {'codeFirst', 'useAdditionalCode', 'codeAlso', 'notes', 'visualImpairment'}:
            note['requires_review'] = True
        elif kind == 'excludes1':
            if selected is None or not note['references']:
                note['requires_review'] = True
            elif any(other != code and _matches(other, ref)
                     for other in selected for ref in note['references']):
                result['errors'].append('excludes1_selected_code_conflict')
                note['requires_review'] = True
        elif kind not in {'includes', 'inclusionTerm', 'excludes2', 'sevenChrNote', 'sevenChrDef'}:
            note['requires_review'] = True
        result['requires_review'] |= note['requires_review']
        if note['requires_review']:
            result['review_instruction_ids'].append(note['id'])
            result['unresolved_instructions'].append(deepcopy(note))
    definitions = [n for n in instructions if n['kind'] == 'sevenChrDef']
    if definitions:
        extensions = {v['character'] for v in definitions[-1]['extensions']}
        raw = code.replace('.', '')
        if len(raw) != 7 or raw[-1] not in extensions:
            result['errors'].append('seventh_character_definition_mismatch')
    result['errors'] = sorted(set(result['errors']))
    result['valid'] = not result['errors']
    return result
