"""Finite source checks, independent of provider labels and substring validity.

These checks do not identify a code, supply terminology, establish permission or
record clinician approval. Dated selection rules are applied by the caller.
"""
import re

CLASSIFICATION_SOURCE = 'https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system'
REQUIRED_TIME_FACTS = ('setting', 'patient_status', 'time_minutes', 'time_same_day',
    'time_qualified_clinician', 'time_excludes_staff', 'time_excludes_separately_reported', 'em_basis')


def classify_selected(row):
    """Classify code syntax independently; syntax never proves dated membership.

    ICD identifiers overlap HCPCS shapes after removing their dot, so an ICD
    label is still verified against its bound official release by the bridge.
    A procedure label cannot turn a leading-letter HCPCS shape into CPT.
    """
    code = row.get('code', '') if type(row) is dict else ''
    code = code.strip().upper() if type(code) is str else ''
    declared = row.get('system') if type(row) is dict else None
    if declared == 'icd10cm-outpatient':
        system = 'ICD-10-CM'
    elif re.fullmatch(r'[A-Z][0-9]{4}', code):
        system = 'HCPCS Level II'
    elif re.fullmatch(r'(?:[0-9]{5}|[0-9]{4}[FTUM])', code):
        system = 'CPT'
    else:
        system = 'unknown'
    return {'system': system, 'provider_system': declared, 'basis': 'code_syntax',
            'source': CLASSIFICATION_SOURCE, 'dated_membership': 'not_established_by_syntax',
            'mismatch': declared == 'cpt' and system != 'CPT'}


def checked_spans(raw, notes):
    spans = []
    if type(raw) is not list:
        return spans, 'missing' if raw is None else 'invalid'
    for item in raw:
        item = item if type(item) is dict else {}
        ci, start, end, text = (item.get(k) for k in ('contextIndex', 'start', 'end', 'text'))
        valid = (ci == 0 and type(ci) is int and type(start) is int and type(end) is int
                 and type(text) is str and 0 <= start < end <= len(notes) and notes[start:end] == text)
        spans.append({'context_index': ci, 'start': start, 'end': end, 'text': text,
                      'status': 'valid' if valid else 'invalid',
                      'reason': 'Source substring integrity only; clinical support is a separate check.'})
    return spans, ('valid' if all(s['status'] == 'valid' for s in spans) else 'invalid') if spans else 'missing'


def _sentences(notes):
    # Preserve CRLF and source offsets. Decimal points are not sentence ends.
    for match in re.finditer(r'[^\r\n]+', notes):
        text = match.group()
        at = 0
        for boundary in re.finditer(r'[.!?](?=\s|$)', text):
            end = boundary.end()
            left = at + len(text[at:end]) - len(text[at:end].lstrip())
            if left < end:
                yield match.start()+left, match.start()+end, text[left:end]
            at = end
        left = at + len(text[at:]) - len(text[at:].lstrip())
        if left < len(text):
            yield match.start()+left, match.end(), text[left:]


def _unsafe(notes, start, text):
    # A fictional-patient banner is provenance, not a quoted clinical example.
    # Actual examples, another patient's facts, and historical/future service
    # frames still require clarification rather than silently filling context.
    preceding = notes[:start].rstrip('\r\n ')
    heading = preceding.rsplit('\n', 1)[-1] if preceding else ''
    context = (heading + ' ' if heading.endswith(':') else '') + text
    return bool(re.search(r'[“”"]|\b(?:example|hypothetical|quoted|quotation|template text|'
        r'another patient|other patient|mother|father|sister|brother|yesterday|tomorrow|'
        r'last (?:week|month|year)|next (?:week|month|year)|would|will|might)\b', context, re.I))


def office_time_facts(notes):
    """Return documented facts with exact provenance, or explicit blockers.

    No code or time threshold appears here. A symptom episode, copied example,
    conflicting total, missing exclusion or missing service date cannot supply
    a same-day practitioner time fact.
    """
    found = {key: [] for key in REQUIRED_TIME_FACTS}
    blockers = []
    if re.search(r'(?im)^\s*(?:quoted )?example(?: note)?\s*:', notes):
        blockers.append('A quoted/example section requires source-scope clarification.')

    def add(key, value, start, end, quote):
        found[key].append({'key': key, 'value': value, 'source': 'saved note',
                           'start': start, 'end': end, 'quote': quote})

    for start, end, text in _sentences(notes):
        low = text.casefold()
        if _unsafe(notes, start, text):
            continue
        negative = bool(re.search(r'\b(?:no|not|never|denies?|without)\b', low))
        if re.search(r'\boffice visit\b', low) and not negative:
            add('setting', 'outpatient_office', start, end, text)
        if re.search(r'\b(?:new|established) patient\b', low):
            if negative:
                blockers.append('The documented patient-status assertion is negated or qualified.')
            else:
                for status in ('new', 'established'):
                    if re.search(r'\b'+status+r' patient\b', low):
                        add('patient_status', status, start, end, text)
        if re.search(r'\b(?:inpatient|emergency department)\b', low) and not negative:
            blockers.append('A non-office encounter setting is also documented.')
        timing = re.match(r'total (?:physician|practitioner|qualified health care professional) time'
            r'(?: on (?:the )?date of service)?\s*(?:was|is|:)\s*(?P<minutes>[0-9]{1,4})\s+minutes\b', low)
        if timing:
            # The complete time predicate must end here or continue with a
            # documented activity/exclusion list. A prefix match before "for
            # Jane Doe" is not this encounter's physician-time assertion.
            continuation = low[timing.end():]
            complete = bool(re.fullmatch(r'\s*[.!?]?', continuation)
                or re.match(r'\s*,\s*(?:including|excluding)\b', continuation))
            if negative or not complete:
                blockers.append('The physician-time assertion is negated or qualified.')
            else:
                add('time_minutes', int(timing['minutes']), start, end, text)
                add('time_qualified_clinician', True, start, end, text)
                if re.search(r'\b(?:on (?:the )?date of service|same day|today)\b', low):
                    add('time_same_day', True, start, end, text)
        if re.search(r'\b(?:office\s+)?e/m\s+selection\b.*\bbased on total (?:physician )?time\b', low) and not negative:
            add('em_basis', 'time', start, end, text)
        if re.search(r'\be/m\s+selection\b.*\b(?:not based on|medical decision making|mdm)\b', low):
            blockers.append('A conflicting E/M selection basis is documented.')
        actions = list(re.finditer(r'\b(?:does not include|excludes?|excluding|includes?|including)\b', low))
        for index, action in enumerate(actions):
            # A later inclusion predicate cannot inherit the prior exclusion.
            # Likewise "including review ... excluding staff" does not make
            # staff part of the included activity list.
            stop = actions[index+1].start() if index+1 < len(actions) else len(low)
            tail = re.split(r'\b(?:but|however|whereas)\b|[.;]', low[action.end():stop], maxsplit=1)[0]
            is_exclusion = action.group().startswith(('exclud', 'does not'))
            negated = bool(re.search(r'\bnot\s*$', low[:action.start()]))
            if is_exclusion and re.search(r'\b(?:neither|nor|except)\b', tail):
                blockers.append('The time-exclusion assertion is negated or qualified.')
                continue
            includes_ineligible = False
            for key, noun in (('time_excludes_staff', r'(?:clinical )?staff time'),
                              ('time_excludes_separately_reported', r'separately reported services')):
                if re.search(r'\b'+noun+r'\b', tail):
                    if is_exclusion and not negated:
                        add(key, True, start, end, text)
                    elif not is_exclusion and not negated:
                        includes_ineligible = True
            if includes_ineligible:
                blockers.append('The documented total includes staff time or separately reported services.')
        if (re.search(r'\bnot exclude\b', low)
                or re.search(r'\b(?:staff time|separately reported services)\b[^.;]*\bnot excluded\b', low)):
            blockers.append('The documented total includes staff time or separately reported services.')
    facts = []
    for key, candidates in found.items():
        values = {str(row['value']) for row in candidates}
        if len(values) != 1:
            blockers.append(('Conflicting' if values else 'Missing') + ' documented ' + key.replace('_', ' ') + '.')
        else:
            facts.append(candidates[0])
    return {'status': 'documented' if not blockers else 'requires_clarification',
            'facts': facts, 'blockers': list(dict.fromkeys(blockers)), 'clinician_confirmed': False}


def citation_adequacy(spans, facts):
    """Provider spans must cover each fact, not merely appear in the input."""
    covered = [f['key'] for f in facts if any(s.get('status') == 'valid' and s.get('context_index') == 0
               and s['start'] <= f['start'] and s['end'] >= f['end'] for s in spans)]
    missing = [key for key in REQUIRED_TIME_FACTS if key not in covered]
    return {'status': 'complete_for_time_review' if not missing else 'insufficient_for_time_review',
            'missing_facts': missing,
            'reason': 'Provider source spans do not independently establish all time-selection facts.' if missing
                      else 'Source spans cover the documented time facts; dated criteria and clinician confirmation remain separate.'}
