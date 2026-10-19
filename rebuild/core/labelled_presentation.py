"""Prospective, source-bound presentation of approved labelled components.

Labels are literal definition metadata, never new clinical quotations. The
closed reader deliberately separates an unrecognized label obligation from
the absence of one. Fact order and provider-supplied concept names grant no
role. Unknown requirements or source associations remain unresolved.
"""
import hashlib
import json
import re

from .clinical_source_context import owned_current, source_date


CONTRACT = 'approved-labelled-components-v1'
_LABEL = r'label(?:l)?ed'
_ROLES = (
    ('age_sex', r'(?:patient\s+)?age\s+and\s+sex'),
    ('service_date', r'(?:service\s+date|date\s+of\s+service|encounter\s+date)'),
    ('clinician', r'treating\s+(?:clinician|physician|doctor)'),
    ('country', r'country'), ('setting', r'setting'), ('modality', r'modality'),
    ('patient_status', r'(?:whether\s+(?:the\s+)?patient\s+is\s+(?:established\s+or\s+new|new\s+or\s+established)|'
                       r'(?:established\s+or\s+new|new\s+or\s+established)\s+(?:patient\s+)?status|patient\s+status)'),
)
_VITALS = (('blood_pressure', r'blood\s+pressure'), ('pulse', r'pulse|heart\s+rate'),
           ('temperature', r'(?:body\s+)?temperature'), ('weight', r'(?:body\s+)?weight'),
           ('height', r'height'), ('respiratory_rate', r'respiratory\s+rate'),
           ('oxygen_saturation', r'oxygen\s+saturation'))
_QUALIFIED = re.compile(r'\b(?:not|never|no|possibly|possible|maybe|apparently|reportedly|allegedly|'
    r'presumed|assumed|hypothetical|uncertain|unverified|unconfirmed|unknown|prior|previous|past|'
    r'future|planned|cancelled|canceled|except|unless|only|instead|mother|father|relative|other)\b', re.I)
_CANDIDATE_HEADERS = (
    ('age_sex', r'age|sex|gender'),
    ('service_date', r'(?:service|encounter|visit|consultation)\s+date|date\s+of\s+service'),
    ('clinician', r'(?:treating|attending|examining)\s+(?:clinician|physician|doctor)'),
    ('country', r'country'), ('setting', r'setting'), ('modality', r'modality'),
    ('patient_status', r'(?:patient|visit|encounter)\s+status'),
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _span(text, start, end):
    return {'start': start, 'end': end, 'quote': text[start:end]}


def _components(meaning, start, end, vocabulary):
    """Consume the entire list and preserve order and literal label offsets."""
    cursor, result = start, []
    while cursor < end:
        matches = [(role, re.match(pattern+r'(?=\s*(?:,|$|\band\b))', meaning[cursor:end], re.I))
                   for role, pattern in vocabulary]
        matches = [(role, match) for role, match in matches if match]
        if len(matches) != 1:
            return None
        role, match = matches[0]
        stop = cursor+match.end()
        result.append({'role': role, 'label': _span(meaning, cursor, stop)})
        if stop == end:
            break
        separator = re.match(r'(?:\s*,\s*(?:and\s+)?|\s+and\s+)', meaning[stop:end], re.I)
        if separator is None:
            return None
        cursor = stop+separator.end()
        if cursor == end:
            return None
    if not result or len({row['role'] for row in result}) != len(result):
        return None
    return result


def requirements(definition):
    meaning = definition['meaning']
    # A failed permission parser must never erase an explicit obligation.
    if not re.search(r'\blabel(?:l)?(?:ed|ing|s)?\b', meaning, re.I):
        return None
    unresolved = {'state': 'unresolved', 'components': [],
                  'reason': 'The complete approved labelled-component requirement is unsupported or ambiguous.'}
    scope = definition['scope']
    if (definition['value_type'] != 'text' or definition.get('answer_mode') != 'narrative'
            or scope['subject'] not in ('patient', 'encounter')
            or scope['temporality'] not in ('current', 'any') or scope['polarity'] not in ('any', 'positive')):
        return unresolved
    summary = re.fullmatch(r'\s*(?:A\s+)?narrative\s+(?:encounter|visit)\s+summary\s+with\s+each\s+'
        r'documented\s+component\s+'+_LABEL+r'\s*:\s*(?P<parts>[^.;]+?)\s*\.?'
        r'(?:\s+Include\s+only\s+documented\s+facts;\s+leave\s+undocumented\s+components\s+blank\.?)?\s*', meaning, re.I)
    vital = re.fullmatch(r'\s*Narrative\s+of\s+the\s+documented\s+vital\s+signs\s+for\s+this\s+'
        r'encounter\s+as\s+complete\s+'+_LABEL+r'\s+measurement\s+phrases\s*:\s*'
        r'(?P<parts>[^.;]+?),\s+each\s+with\s+its\s+documented\s+unit\s+and\s+scale\.\s+'
        r'No\s+common\s+unit\s+or\s+normal\s+range\s+is\s+implied;\s+bare\s+numbers\s+are\s+not\s+sufficient\.\s*', meaning, re.I)
    match = summary or vital
    if match is None:
        return unresolved
    components = _components(meaning, *match.span('parts'), _ROLES if summary else _VITALS)
    if components is None:
        return unresolved
    return {'state': 'parsed', 'mode': 'metadata_labels' if summary else 'source_labels',
            'components': components}


def _candidate_roles(text, patient):
    """Discovery is broader than permission; candidates never supply a value.

    A role-bearing header or patient-governed metadata statement cannot become
    an undocumented blank just because its complete grammar is unsupported.
    Ordinary symptom/time prose mentioning a visit is not such a statement.
    """
    result = set()
    # A complete action clause has a different grammatical subject from a
    # metadata header. This exclusion consumes the whole clause; unknown tails
    # cannot turn a role obligation into an undocumented blank.
    if re.fullmatch(r'Setting\s+(?:goals|priorities|limits|boundaries)\s+'
                    r'(?:is|was|can\s+be)\s+(?:helpful|useful|difficult|beneficial|important)'
                    r'(?:\s+(?:to|for)\s+(?:her|him|them|the\s+patient))?\.?', text, re.I):
        return result
    prefix = (r'(?:the\s+)?(?:(?:current|prior|previous|future|unverified|unknown|'
              r'apparent|reported|apparently|reportedly|possibly|unconfirmed|'
              r'patient[\x27’]?s?|visit|encounter|consultation|her|his|their)\s+){0,4}')
    heading = text.split(':', 1)[0] if ':' in text else None
    if heading is None and (predicate := re.search(r'\s+(?:is|was|are|were|remains?|may\s+be|will\s+be)\b', text, re.I)):
        heading = text[:predicate.start()]
    if heading is not None:
        result.update(role for role, pattern in _CANDIDATE_HEADERS
                      if re.fullmatch(prefix+r'(?:'+pattern+r')\s*', heading, re.I))
    # The role prefix establishes an obligation independently of any value
    # grammar. Every unconsumed qualifier, unknown value or coordinated tail
    # belongs to that whole source obligation; none supplies render permission.
    result.update(role for role, pattern in _CANDIDATE_HEADERS
                  if re.match(prefix+r'(?:'+pattern+r')(?=\s|:|$)', text, re.I))

    # Read the direct complement of the patient's predicate, not remote words
    # in its objects. "She is worried about a woman" does not state her sex;
    # a scheduled follow-up in an office does not describe this encounter.
    governed = re.search(r'\b'+patient+r'\s+(?:is|was|are|were|may\s+be|will\s+be)\s+', text, re.I)
    complement = text[governed.end():] if governed else ''
    qualification = r'(?:(?:not|possibly|reportedly|apparently|allegedly|approximately|roughly)\s+)*'
    adjective = r'(?!(?:about|for|from|of|to|with|in|on|at|a|an|the|who|that|and|or)\b)[A-Za-z-]+'
    direct_age = re.match(qualification+r'(?:'
        r'(?:an?\s+)?\d{1,3}(?:-year-old|\s+years?\s+old)(?:\s+(?:woman|man|person))?'
        r'|aged\s+[^,;.]{1,40}'
        r'|(?:an?\s+(?:'+adjective+r'\s+){0,3})?(?:woman|man|female|male))\b', complement, re.I)
    if direct_age:
        result.add('age_sex')
    if re.search(r'\b'+patient+r'\s+(?:has|had)\s+(?:an?\s+)?(?:age\s+of|sex\s+of|gender\s+of)\b', text, re.I):
        result.add('age_sex')
    if re.search(r'\b(?:his|her|their|the\s+patient[\x27’]s)\s+(?:age|sex|gender)\b', text, re.I):
        result.add('age_sex')
    if re.match(qualification+r'(?:an?\s+)?(?:established|new)[ -]patient\b', complement, re.I):
        result.add('patient_status')
    attendance = complement[direct_age.end():].lstrip() if direct_age else complement
    if match := re.match(r'attending\s+', attendance, re.I):
        frame = attendance[match.end():]
    elif match := re.search(r'\b'+patient+r'\s+attends?\s+', text, re.I):
        frame = text[match.end():]
    elif match := re.search(r'\b(?:the|this|current|today[\x27’]s)\s+(?:visit|encounter|consultation)\s+'
                            r'(?:is|was|may\s+be)\s+', text, re.I):
        frame = text[match.end():]
    else:
        frame = ''
    if frame:
        if re.search(r'\b(?:established|new)[ -]patient\b', frame, re.I):
            result.add('patient_status')
        if re.search(r'\b(?:in-person|video|telephone)\b', frame, re.I):
            result.add('modality')
        if re.search(r'\b(?:in|at)\s+[^;\n]{0,100}\b(?:office|clinic|hospital|home)\b', frame, re.I):
            result.add('setting')
            if re.search(r'\b(?:in|at)\s+(?:an?\s+)?(?-i:(?:[A-Z]\.){2,3}|[A-Z]{2,3})\s+', frame, re.I):
                result.add('country')
    return result


def _source_roles(notes, units, context):
    """Complete current source frames, with exact role spans and no concept use."""
    roles = {role: [] for role, _ in _ROLES}
    uncertain, candidates = set(), []
    name = context.get('patient_name') or ''
    ordinary = re.sub(r'^Synthetic\s+', '', name, flags=re.I)
    aliases = {name, ordinary, ordinary.split()[0] if ordinary else ''} - {''}
    patient = r'(?:the\s+patient|he|she|they'+''.join('|'+re.escape(x) for x in sorted(aliases))+r')'
    # An uppercase country abbreviation is a literal source value, not an ISO
    # lookup. Spelled-out countries remain available through explicit headers.
    country = r'(?-i:(?:[A-Z]\.){2,3}|[A-Z]{2,3})'
    visit = re.compile(patient+r'\s+is\s+an?\s+(?P<age_sex>\d{1,3}-year-old\s+(?:woman|man|person))\s+'
        r'attending\s+an?\s+(?P<patient_status>established[ -]patient|new[ -]patient),\s*'
        r'(?P<modality>in-person|video|telephone)\s+(?:visit|consultation)\s+in\s+an?\s+'
        r'(?P<country>'+country+r')\s+(?P<setting>[A-Za-z][A-Za-z-]*(?:\s+[A-Za-z][A-Za-z-]*){0,3}\s+(?:office|clinic))\s*\.?', re.I)
    age = re.compile(patient+r'\s+is\s+an?\s+(?P<age_sex>\d{1,3}-year-old\s+(?:woman|man|person))\s*\.?', re.I)
    headers = (
        ('service_date', r'(?:Service\s+date|Date\s+of\s+service|Encounter\s+date)', r'.+?'),
        ('clinician', r'Treating\s+(?:clinician|physician|doctor)', r'(?:Dr\.\s+|Doctor\s+)?(?P<name>[A-Za-z][A-Za-z\x27’.-]*(?:\s+[A-Za-z][A-Za-z\x27’.-]*){1,5})'),
        ('age_sex', r'(?:Patient\s+)?age\s+and\s+sex', r'\d{1,3}-year-old\s+(?:woman|man|person)'),
        ('country', r'(?:Visit\s+)?country', r'[A-Za-z][A-Za-z .-]{0,60}'),
        ('setting', r'(?:Visit\s+)?setting', r'[A-Za-z][A-Za-z -]{0,80}'),
        ('modality', r'(?:Visit\s+)?modality', r'in-person|video|telephone'),
        ('patient_status', r'Patient\s+status', r'established(?:[ -]patient)?|new(?:[ -]patient)?'),
    )

    def add(role, unit, start, end, subject):
        roles[role].append({'value': _span(notes, unit['start']+start, unit['start']+end),
                            'source': _span(notes, unit['start'], unit['end']), 'subject': subject})

    for unit in units:
        text = unit['quote']
        offset = len(text)-len(text.lstrip())
        body = text.strip()
        discovered = _candidate_roles(body, patient)
        row = context['units'].get(unit['start'])
        # Only positive other-scope evidence permits exclusion. An unresolved
        # date/owner is a hold, even after a later current-encounter heading.
        other_scope = (row and not row['issues'] and (row['subject'] == 'foreign'
                       or row['section_timing'] in ('past', 'future')))
        if other_scope:
            continue
        if discovered:
            candidates.append({'source': _span(notes, unit['start'], unit['end']),
                               'roles': sorted(discovered), 'scope': row})
        if not owned_current(context, unit):
            uncertain.update(discovered)
            continue
        matched_header = False
        consumed = set()
        for role, label, value in headers:
            if not re.match(r'\s*'+label+r'\s*:', text, re.I):
                continue
            matched_header = True
            consumed.add(role)
            match = re.fullmatch(r'\s*'+label+r'\s*:\s*(?P<value>'+value+r')\s*\.?\s*', text, re.I)
            if match is None or _QUALIFIED.search(match['value']):
                uncertain.add(role)
                continue
            group = 'name' if role == 'clinician' else 'value'
            start, end = match.span(group)
            while end > start and text[end-1].isspace():
                end -= 1
            if role == 'clinician' and text[end-1:end] == '.':
                end -= 1
            if role == 'service_date' and source_date(text[start:end].removesuffix('.')) is None:
                uncertain.add(role)
                continue
            if role == 'service_date' and text[end-1:end] == '.':
                end -= 1
            add(role, unit, start, end, 'clinician' if role == 'clinician' else 'patient')
        if matched_header:
            uncertain.update(discovered-consumed)
            continue
        match = visit.fullmatch(body)
        if match and not _QUALIFIED.search(body):
            for role in ('age_sex', 'patient_status', 'modality', 'country', 'setting'):
                start, end = match.span(role)
                add(role, unit, offset+start, offset+end, 'patient')
                consumed.add(role)
        elif (match := age.fullmatch(body)) and not _QUALIFIED.search(body):
            start, end = match.span('age_sex')
            add('age_sex', unit, offset+start, offset+end, 'patient')
            consumed.add('age_sex')
        uncertain.update(discovered-consumed)
    return roles, uncertain, candidates


def _clean_fact(notes, fact, role, source):
    value = fact['value_evidence']
    return (not fact['issues'] and fact['subject']['kind'] == source['subject']
            and fact['polarity'] == 'affirmed' and fact['timing']['kind'] == 'current'
            and fact['unit'] is None and fact['scale'] is None
            and value == source['value'] and value['quote'] == notes[value['start']:value['end']]
            and source['source'] in fact['evidence'])


def derive(notes, field, definition, facts, selected_ids, rendered_values, separator, units, context):
    """Return no obligation, or a rederivable presentation and explicit holds."""
    requirement = requirements(definition)
    if requirement is None:
        return None
    original = separator.join(rendered_values)
    proof = {'contract': CONTRACT, 'field_key': field['key'], 'definition_sha256': digest(definition),
             'question_sha256': digest({'label': field['label'], 'locator': field['locator']}),
             'source_sha256': hashlib.sha256(notes.encode()).hexdigest(), 'requirement': requirement,
             'parts': [], 'state': 'unresolved'}
    errors = []
    if requirement['state'] == 'unresolved':
        return {'text': original, 'proof': proof, 'errors': [requirement['reason']]}
    if requirement['mode'] == 'source_labels':
        # These full clinical phrases already carry their labels. The original
        # rendering and proof shape stay unchanged when every role is covered.
        used = set()
        for component in requirement['components']:
            pattern = dict(_VITALS)[component['role']]
            documented = [unit for unit in units if owned_current(context, unit)
                          and re.search(r'\b(?:'+pattern+r')\b', unit['quote'], re.I)]
            matches = []
            for identity in selected_ids:
                fact = facts[identity]
                value = fact['value_evidence']
                own = [u for u in units if u['start'] <= value['start'] < value['end'] <= u['end']]
                if (re.match(r'(?:'+pattern+r')\b', value['quote'], re.I) and not fact['issues']
                        and fact['subject']['kind'] == 'patient' and fact['timing']['kind'] == 'current'
                        and fact['polarity'] == 'affirmed' and len(own) == 1 and owned_current(context, own[0])
                        and value['quote'] == notes[value['start']:value['end']]):
                    matches.append(identity)
            if not documented and not matches:
                continue
            if len(matches) != 1:
                errors.append('A complete source-labelled measurement needs one uniquely bound selected phrase: '+component['label']['quote'])
            else:
                used.add(matches[0])
        if used != set(selected_ids):
            errors.append('The source-labelled measurement selection has an unbound or repeated component.')
        return {'text': original, 'proof': proof if errors else None, 'errors': errors}
    roles, uncertain, candidates = _source_roles(notes, units, context)
    requested = {component['role'] for component in requirement['components']}
    proof['source_candidates'] = [candidate for candidate in candidates if requested.intersection(candidate['roles'])]
    rendered = dict(zip(selected_ids, rendered_values))
    used, parts = set(), []
    for component in requirement['components']:
        role, label = component['role'], component['label']
        sources = roles[role]
        part = {'role': role, 'label': label, 'fact_id': None, 'source_role': None, 'rendered_value': ''}
        if role in uncertain or len(sources) > 1:
            errors.append('The labelled component has ambiguous or unsupported source context: '+label['quote'])
        elif sources:
            source = sources[0]
            matches = [identity for identity in selected_ids if _clean_fact(notes, facts[identity], role, source)]
            if len(matches) != 1:
                errors.append('A documented labelled component lacks one exact selected source role: '+label['quote'])
            else:
                identity = matches[0]
                used.add(identity)
                part.update(fact_id=identity, source_role=source, rendered_value=rendered[identity])
                parts.append(label['quote']+': '+rendered[identity])
        proof['parts'].append(part)
    if used != set(selected_ids):
        errors.append('A selected fact has no unique approved labelled component association.')
    if errors:
        return {'text': original, 'proof': proof, 'errors': list(dict.fromkeys(errors))}
    proof['state'] = 'resolved'
    proof['text_sha256'] = hashlib.sha256('; '.join(parts).encode()).hexdigest()
    return {'text': '; '.join(parts), 'proof': proof, 'errors': []}
