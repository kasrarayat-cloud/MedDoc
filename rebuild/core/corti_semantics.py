"""Finite source checks, independent of provider labels and substring validity.

These checks do not identify a code, supply terminology, establish permission or
record clinician approval. Dated selection rules are applied by the caller.
"""
import re
from datetime import datetime
from decimal import Decimal

CLASSIFICATION_SOURCE = 'https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system'
REQUIRED_TIME_FACTS = ('setting', 'patient_status', 'time_minutes', 'time_same_day',
    'time_qualified_clinician', 'time_excludes_staff', 'time_excludes_separately_reported', 'em_basis')
SOAP_TIME_CONTRACT = 'source-bound-clinical-coding-v6'
QUALIFIED_TIME_CONTRACT = 'source-bound-clinical-coding-v7'
DOCUMENTED_TIME_CONTRACT = 'source-bound-clinical-coding-v8'
_SOAP_TIME_CONTRACTS = (SOAP_TIME_CONTRACT, QUALIFIED_TIME_CONTRACT, DOCUMENTED_TIME_CONTRACT)
_SOURCE_TIME_CONTRACTS = ('source-bound-clinical-coding-v2', 'source-bound-clinical-coding-v3',
    'source-bound-clinical-coding-v4', 'source-bound-clinical-coding-v5', *_SOAP_TIME_CONTRACTS)
_MODERN_TIME_CONTRACTS = _SOURCE_TIME_CONTRACTS[2:]
_COMPLETE_TIME_CONTRACTS = _SOURCE_TIME_CONTRACTS[3:]


def time_contract(config):
    """A separate immutable CPT time policy never upgrades old clinical runs."""
    contract = config.get('clinical_source_contract')
    if 'cpt_time_source_contract' not in config:
        return contract
    if config['cpt_time_source_contract'] != DOCUMENTED_TIME_CONTRACT or contract != QUALIFIED_TIME_CONTRACT:
        raise ValueError('Unknown CPT time-source contract.')
    return DOCUMENTED_TIME_CONTRACT


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
        r'(?:previous|prior|earlier) (?:visit|encounter)|'
        r'last (?:week|month|year)|next (?:week|month|year)|would|will|might|'
        r'planned|scheduled|future|hypothetically)\b', context, re.I))


def office_time_facts(notes, *, contract=None):
    """Return documented facts with exact provenance, or explicit blockers.

    No code or time threshold appears here. A symptom episode, copied example,
    conflicting total, missing exclusion or missing service date cannot supply
    a same-day practitioner time fact.
    """
    if contract in _SOURCE_TIME_CONTRACTS:
        return _source_time_analysis(notes, modern=contract in _MODERN_TIME_CONTRACTS,
            complete=contract in _COMPLETE_TIME_CONTRACTS, soap=contract in _SOAP_TIME_CONTRACTS,
            documented=contract == DOCUMENTED_TIME_CONTRACT)[0]
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
        if re.search(r'\b(?:office (?:visit|consultation|encounter)|outpatient (?:office )?visit)\b', low) and not negative:
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


def confirmed_time_context(context, notes, facts):
    """Saved context confirms source facts; UI checkboxes cannot create evidence."""
    values = {fact['key']: fact['value'] for fact in facts}
    errors = []
    for key in ('setting', 'patient_status', 'em_basis'):
        if context.get(key) != values.get(key):
            errors.append('The saved ' + key.replace('_', ' ') + ' conflicts with the complete source.')
    if str(context.get('time_minutes', '')) != str(values.get('time_minutes', '')):
        errors.append('Saved physician minutes do not match the documented total.')
    if any(context.get(key) is not True for key in
           ('time_same_day', 'time_qualified_clinician', 'time_excludes_separately_reported')):
        errors.append('Confirm all three documented physician-time conditions in coding context.')
    evidence = context.get('time_evidence', '')
    time = next((fact for fact in facts if fact['key'] == 'time_minutes'), None)
    if (not isinstance(evidence, str) or not evidence or evidence not in notes or time is None
            or not any(at <= time['start'] and at + len(evidence) >= time['end']
                       for at in (m.start() for m in re.finditer(re.escape(evidence), notes)))):
        errors.append('Saved time evidence must quote the complete physician-time assertion.')
    return errors


def office_service_eligibility(notes, service_date=None, *, contract=None):
    """Veto full-source contradictions and require an actual evaluated service.

    This bounded reader supports explicit current office documentation. It does
    not infer an encounter from a numeric time quote or a scheduled appointment.
    Unrecognized competing practitioner totals require clarification.
    """
    if contract in _SOURCE_TIME_CONTRACTS:
        soap = contract in _SOAP_TIME_CONTRACTS
        support, errors = _source_time_analysis(notes, modern=contract in _MODERN_TIME_CONTRACTS,
            complete=contract in _COMPLETE_TIME_CONTRACTS, soap=soap,
            documented=contract == DOCUMENTED_TIME_CONTRACT)
        if service_date is not None:
            for raw_date in _service_dates(notes, soap=soap):
                parsed = None
                for format in ('%Y-%m-%d', '%d %B %Y', '%B %d, %Y'):
                    try:
                        parsed = datetime.strptime(raw_date.strip(), format).date()
                        break
                    except ValueError:
                        pass
                if parsed != service_date:
                    errors.append('The source service date is unresolved or conflicts with the saved encounter date.')
        return list(dict.fromkeys(errors))
    errors, evaluated = [], False
    if service_date is not None:
        for raw_date in re.findall(r'(?im)^\s*date of service\s*:\s*([^\r\n]+)', notes):
            parsed = None
            for format in ('%Y-%m-%d', '%d %B %Y', '%B %d, %Y'):
                try:
                    parsed = datetime.strptime(raw_date.strip(), format).date()
                    break
                except ValueError:
                    pass
            if parsed != service_date:
                errors.append('The source service date is unresolved or conflicts with the saved encounter date.')
    total = r'\b(?:total\s+)?(?:physician|practitioner|qualified health care professional)\s+(?:total\s+)?time\b'
    for start, _end, text in _sentences(notes):
        low = text.casefold()
        # A retraction can refer to a prior/copied statement. Inspect it before
        # discarding foreign/historical fact scope, or the retraction itself
        # disappears while the original assertion survives as a false positive.
        service = r'\b(?:time|minutes|encounter|visit|appointment|consultation|evaluation|examination)\b'
        retracted = r'\b(?:copied|incorrect\w*|erroneous|invalid|unreliable|mistake|wrong|retract\w*|disregard\w*)\b'
        if (re.search(service, low) and (re.search(retracted, low)
                or re.search(r'\b(?:must|should|can)\s+not\s+(?:be\s+)?(?:used|counted|relied)\b', low))):
            errors.append('The complete source retracts or questions the documented service or time.')
        if (re.search(r'\b(?:encounter|visit|appointment|consultation)\b[^.;]*'
                      r'\b(?:did not|didn.t|never)\s+(?:occur|take place|happen)\b', low)
                or re.search(r'\b(?:did not|didn.t|never)\s+(?:see|evaluate|examine)\b[^.;]*\bpatient\b', low)
                or re.search(r'\bpatient\b[^.;]*\b(?:was not|wasn.t|not)\s+(?:seen|evaluated|examined)\b', low)):
            errors.append('The complete source denies that the patient encounter or evaluation occurred.')
        if (re.search(r'\b(?:(?:clinical )?staff|separately reported services)\b', low)
                and (re.search(r'\b(?:is|are|was|were)\s+(?:(?:also|already)\s+)?(?:included|counted)\b', low)
                     or re.search(r'\b(?:minutes|time)\b[^.;]*\b(?:spent|provided|performed)\s+by\b', low)
                     or re.search(r'\bof (?:these|the)\s+[^.;]*\bminutes\b', low))):
            errors.append('A component of the documented total includes staff time or separately reported services.')
        if _unsafe(notes, start, text):
            continue
        if (re.search(total, low) or re.search(r'\b(?:physician|practitioner)\s+(?:spent|provided)\b', low)
                or re.search(r'\b(?:correction|corrected|amended|actual|actually)\b', low)) and re.search(r'\b(?:minutes?|hours?)\b', low):
            if not re.match(r'total (?:physician|practitioner|qualified health care professional) time'
                            r'(?: on (?:the )?date of service)?\s*(?:was|is|:)\s*\d+\s+minutes\b', low):
                errors.append('A competing or qualified practitioner-time statement requires clarification.')
        # This finite contract recognizes the complete total, its explicit
        # exclusions, and the E/M basis. An additional assertion about that same
        # total must not disappear merely because its number is written in words
        # or the author uses an anaphor instead of repeating "physician time".
        linked_time = re.search(total + r'|\b(?:this|the|documented) total(?: time)?\b|\btime (?:above|below)\b', low)
        known_time = (re.match(r'total (?:physician|practitioner|qualified health care professional) time'
                              r'(?: on (?:the )?date of service)?\s*(?:was|is|:)\s*\d+\s+minutes\b', low)
            or re.match(r'(?:this|the) total\s+(?:excludes?|does not include)\b', low)
            or re.search(r'\be/m\s+selection\b.*\bbased on total (?:physician )?time\b', low))
        if linked_time and not known_time:
            errors.append('An additional assertion about the practitioner total requires clarification.')
        if (re.search(r'\b(?:no|not|never|without)\b[^.;]*\b(?:office (?:visit|consultation)|evaluation|examination)\b', low)
                or re.search(r'\b(?:office (?:visit|consultation)|evaluation|examination)\b[^.;]*'
                             r'\b(?:not (?:performed|completed|provided)|cancelled|canceled)\b', low)
                or re.search(r'\b(?:appointment|visit|consultation)\b[^.;]*\b(?:cancelled|canceled|did not occur)\b', low)
                or re.search(r'\bno (?:office )?(?:visit|consultation|appointment)\b', low)):
            errors.append('The complete source also denies a completed office evaluation or examination.')
        # A clinical assertion about the encounter, or the qualifying activities
        # of its same-day total, establishes that a service actually occurred.
        if (re.search(r'\b(?:examined|history (?:was )?obtained|examination (?:was )?performed)\b[^.;]*'
                      r'\b(?:this (?:encounter|visit)|today)\b', low)
                or re.search(r'\bincluding\b[^.;]*\b(?:obtaining (?:the )?history|performing (?:the )?examination)\b', low)):
            if not re.search(r'\b(?:no|not|never|without|denies?)\b', low):
                evaluated = True
    if not evaluated:
        errors.append('The complete source must document evaluation with history or examination during this encounter.')
    return list(dict.fromkeys(errors))


_NUMBERS = {word: value for value, word in enumerate(('zero', 'one', 'two', 'three', 'four',
    'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen',
    'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'))}
_NUMBER = r'(?:\d{1,4}|' + '|'.join(_NUMBERS) + r')'
_ROLE = r'(?:physician|practitioner|qualified health care professional)'
_DAY = r'(?:on (?:the )?(?:date of service|encounter date)|today|on the same day)'
_WORK = (r'(?:review(?:ing)? (?:of )?(?:(?:the|available|prior|medical) )*(?:records|chart)(?: before (?:the )?visit)?'
    r'|(?:obtaining|taking) (?:the )?history|performing (?:the )?examination'
    r'|examining(?: (?:the patient|him|her))?|counsel(?:ing|ling)(?: (?:the patient|patient|him|her))?'
    r'|entering orders|document(?:ing|ation)(?: (?:the )?visit)?)')
_STAFF = r'(?:(?:clinical )?staff (?:time|work|rooming(?: work)?)|nursing (?:time|work|rooming(?: work)?))'
_STAFF_CURRENT = r'(?:(?:clinical )?staff|nursing) (?:time|work|(?:intake|rooming|triage)(?: work)?)'
_CALENDAR_DAY = r'(?:\d{4}-\d{2}-\d{2}|\d{1,2} [A-Za-z]+ \d{4}|[A-Za-z]+ \d{1,2}, \d{4})'


def _calendar_day(value):
    for pattern in ('%Y-%m-%d', '%d %B %Y', '%B %d, %Y'):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            pass
    return None


def _new_patient_service_history(text, scope):
    """Check the qualifying history without negating its heading's label.

    This returns a veto, never a new-patient fact. An affirmative or unresolved
    service history involving the treating clinician/same group must not be
    hidden by an explicit new-patient label elsewhere. External prior care is
    not automatically established-patient care in this practice.
    """
    from .clinical_source_context import clinician_matches
    low = text.casefold()
    history_label = bool(re.match(r'new[ -]patient history\s*:', low))
    aliases = [alias for row in scope['clinicians'] for alias in row['aliases']]
    actor = r'(?:(?:dr\.?|doctor)\s+(?:' + '|'.join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r')|the treating (?:clinician|physician|doctor))'
    same_clinician = bool(aliases and re.search(r'\b' + actor + r'(?!\w)', low))
    relevant = (history_label or same_clinician
                or bool(re.search(r'\bsame (?:group|specialty|subspecialty|practice)\b', low)))
    if not relevant:
        return None
    # Only a complete, explicitly remote encounter can be excluded from the
    # three-year window. Unknown dates remain unresolved rather than silently
    # counting as old care. A year means its full possible interval.
    def outside_window(when):
        current = scope.get('service_date')
        if isinstance(current, str):
            current = _calendar_day(current)
        if not current:
            return False
        years = re.fullmatch(r'(' + _NUMBER + r') years? ago', when)
        if years:
            count = int(years[1]) if years[1].isdigit() else _NUMBERS[years[1]]
            return count > 3
        year = re.fullmatch(r'in ((?:19|20)\d\d)', when)
        if year:
            return int(year[1]) < current.year - 3
        exact = re.fullmatch(r'on (.+)', when)
        value = _calendar_day(exact[1]) if exact else None
        return bool(value and (value.year, value.month, value.day) < (current.year - 3, current.month, current.day))
    patient = r'(?:she|he|they|the patient|' + re.escape(scope.get('patient_name','').casefold()) + r')'
    visit = re.fullmatch(patient + r' (?:saw|was seen by|was evaluated by|was treated by) '
        + actor + r' (?P<when>.+?)\.?', low)
    if visit and outside_window(visit['when'].rstrip('.')):
        return None
    # Different specialty/subspecialty care in the group does not establish
    # this physician's new-patient relationship. Require the complete claim.
    different = re.fullmatch(patient + r' received professional services from a [a-z]+ '
        r'of a different specialty and subspecialty in (?:this|the) same group practice '
        r'(?:last (?:month|year|week)|on ' + _CALENDAR_DAY + r')\.?', text, re.I)
    if different and not same_clinician:
        return None
    if (re.search(r'\bestablished patient\b', low)
            or same_clinician and re.search(r'\b(?:saw|seen|evaluated|treated|visited|consulted)\b', low)):
        return 'A documented prior treating-clinician relationship conflicts with or leaves new-patient status unresolved.'
    if not re.search(r'\bprofessional services\b', low):
        return None
    value = re.sub(r'^new[ -]patient history\s*:\s*', '', text, flags=re.I).strip().rstrip('.')
    # The bounded negative assertion covers the entire professional-service
    # predicate. Exceptions and additional predicates are not swallowed.
    match = re.fullmatch(r'(?:During|In|Over) the (?:preceding|previous|past|last) (?:three|3) years,? '
        r'(?:she|he|they|the patient) (?:has|have) received no professional services from '
        r'(?P<clinician>Dr\. [A-Z][A-Za-z -]+?) or from any (?:physician|doctor) or '
        r'qualified (?:health|health care|healthcare) professional of the same specialty and subspecialty '
        r'in (?:this|the) same group practice', value, re.I)
    if match and clinician_matches(scope, match['clinician']):
        return None
    return 'The qualifying professional-service history conflicts with or does not establish new-patient status.'


def _work_list(text, minutes, *, modern=False, soap=False):
    """Recognize complete work lists and reconcile explicit allocated minutes.

    Unrecognized words, service performance, another person and partial sums
    cannot hide inside an accepted total. This checks the recorded allocation;
    it does not calculate a billable total from independent activities.
    """
    text = text.strip().rstrip('.!?').strip()
    if not text:
        return True, False
    text = re.sub(r'^(?:,\s*(?:including|comprising)|:\s*)\s*', '', text)
    quantities = list(re.finditer(r'\b(' + _NUMBER + r')\s+minutes?\b', text, re.I))
    if quantities:
        if sum(int(m[1]) if m[1].isdigit() else _NUMBERS[m[1].lower()] for m in quantities) != minutes:
            return False, False
        text = re.sub(r'\b' + _NUMBER + r'\s+minutes?\s+(?:for\s+)?', '', text, flags=re.I)
    # Same-day direct contact is an activity qualifier, not a second total.
    # Other recipients or days are not removed by this grammar.
    text = re.sub(r'\bdirectly with the patient\s+', '', text, flags=re.I)
    evaluated = bool(re.search(r'\b(?:obtaining|taking) (?:the )?history|performing (?:the )?examination\b|\bexamining\b', text, re.I))
    work = _WORK
    if modern:
        # Qualify administrative physician activities, not procedure delivery.
        # Every word remains covered by this finite grammar, including adjuncts.
        work = work.replace('available|prior|medical', 'available|outside|prior|medical')
        work = work.replace('entering orders', r'entering (?:the )?(?:(?:investigation|test|imaging|laboratory|medication) )?orders?')
        work = work.replace('(?:the )?visit', '(?:the )?(?:visit|encounter)')
    if soap:
        # Order entry is administrative work. This complete phrase does not
        # authorize collecting a sample or performing the ordered service.
        work = '(?:' + work + r'|placing (?:the )?(?:(?:laboratory|investigation|test|imaging|medication) )?orders?)'
    residue = re.sub(work, '', text, flags=re.I)
    residue = re.sub(r'\band\b|[\s,;]', '', residue, flags=re.I)
    return not residue, evaluated


def _time_statement(text, scope, *, modern=False, service_date=None, soap=False):
    from .clinical_source_context import clinician_matches
    low = text.casefold()
    day = r'(?:' + _DAY + r'|on (?P<calendar>' + _CALENDAR_DAY + r'))' if modern else _DAY
    match = re.match(r'total ' + _ROLE + r' time(?: ' + day + r')?\s*(?:was|is|:)\s*'
                     r'(?P<minutes>\d{1,4})\s+minutes\b', low)
    if match is None:
        match = re.match(r'(?P<performer>.+?)\s+(?:personally\s+)?spent\s+(?P<minutes>\d{1,4})'
                         r'\s+minutes\s+' + day + r'\b', text, re.I)
        if match and not (re.fullmatch(r'(?:the )?' + _ROLE, match['performer'], re.I)
                          or clinician_matches(scope, match['performer'])):
            return None
    if match is None:
        return None
    calendar = match.groupdict().get('calendar')
    if calendar and (service_date is None or _calendar_day(calendar) != service_date):
        return None
    minutes = int(match['minutes'])
    valid_work, evaluated = _work_list(text[match.end():], minutes, modern=modern, soap=soap)
    if not valid_work:
        return None
    return {'minutes': minutes, 'same_day': bool(calendar or re.search(_DAY, low)), 'evaluated': evaluated}


def _evaluation_denied(text, scope):
    """Explicit lack of clinician participation is a source contradiction.

    These are service predicates and actor roles, independent of any code,
    symptom, template or expected answer. A relative's or other clinician's
    nonparticipation cannot veto the treating clinician's documented service.
    """
    from .clinical_source_context import clinician_matches
    low = text.casefold()
    action = r'(?:history|examination|clinical evaluation)'
    if re.search(r'\bno\s+' + action + r'(?:\s+or\s+' + action + r')?\s+'
                 r'(?:(?:was|were|is|has been)\s+)?(?:obtained|taken|performed|completed|occurred|provided)\b', low):
        return True
    if (re.search(r'\b(?:administrative|chart review)\b[^.;]*\bonly\b', low)
            and re.search(r'\b(?:this|visit|encounter|consultation|service)\b', low)):
        return True
    staff_actor = r'(?:nursing staff|(?:clinical )?staff|nurses?(?! practitioners?))'
    patient_action = r'(?:saw|seen|evaluated|examined|assessed|obtained (?:the )?history|contact)'
    if (re.search(r'\b(?:only|solely|exclusively)\s+' + staff_actor + r'\b[^.;]*\b' + patient_action + r'\b', low)
            or re.search(r'\b' + patient_action + r'\b[^.;]*\b(?:only|solely|exclusively)\s+(?:by\s+)?' + staff_actor + r'\b', low)):
        return True
    for clause in re.split(r';\s*', text):
        denial = re.search(r'(?P<actor>.+?)\s+(?:did not|does not|never)\s+'
            r'(?:participate|see|evaluate|examine|assess|provide|perform|obtain)\b', clause, re.I)
        if not denial:
            continue
        actor = re.sub(r'^(?:and|but)\s+', '', denial['actor'].strip(), flags=re.I)
        if re.fullmatch(r'(?:the\s+)?(?:physician|doctor|clinician|practitioner|qualified health care professional)', actor, re.I) or clinician_matches(scope, actor):
            return True
    return False


def _current_account_clauses(text):
    """Use shared account ownership after the enclosing unit is checked."""
    from .clinical_source_context import account_clauses, account_reference
    for clause in account_clauses(text):
        reference = account_reference(clause)
        if reference is None:
            yield clause
        elif reference['current_owned']:
            # An outer assertion such as "it is false that" cannot disappear
            # while its embedded negated error is treated as a complete fact.
            yield clause if reference['qualified'] else reference['tail']


def _affirmed_time_retraction(text):
    """Bind each error predicate to its own explicit account subject."""
    from .clinical_source_context import account_reference
    pattern = (r'\b(?:copied|incorrect\w*|erroneous|invalid|unreliable|mistake|wrong|retract\w*|disregard\w*)\b|'
        r'\b(?:must|should|can)\s+not\s+(?:be\s+)?(?:used|counted|relied)\b')
    for clause in _current_account_clauses(text):
        reference = account_reference(clause)
        if reference and reference['qualified'] and 'time' in reference['domains']:
            return True
        if not re.search(r'\b(?:time|minutes|total|encounter|visit|consultation|evaluation|examination)\b', clause, re.I):
            continue
        if any(not re.search(r'\b(?:not|never)\s+(?:(?:actually|considered|deemed)\s+)?$', clause[:match.start()], re.I)
               for match in re.finditer(pattern, clause, re.I)):
            return True
    return False


def _time_integrity_assertion(text):
    """A complete denial of error adds no minutes or competing time claim.

    Require the whole predicate. A negated copying statement cannot hide a
    second assertion that assigns the minutes to staff or a different day.
    """
    # Shared splitting requires a new explicit subject and predicate. A
    # different account's error cannot qualify the time account, while unknown
    # trailing qualifications of the same subject remain in the whole clause.
    clauses = [clause for clause in _current_account_clauses(text)
               if re.search(r'\b(?:time|total|minutes)\b', clause, re.I)]
    return bool(clauses) and all(re.fullmatch(r'\s*(?:(?:the|this|that|stated|documented|reported|physician|practitioner|time|total)\s+)*'
        r'(?:time|total|\d+\s+minutes)\s+(?:is|was|are|were)\s+(?:not|never)\s+(?:actually\s+)?'
        r'(?:erroneous|incorrect|invalid|unreliable|wrong|copied(?:\s+from\s+'
        r'(?:(?:an?|the|another|earlier|prior|previous)\s+)*(?:visit|encounter|note|record))?)\s*[.!?]?\s*', clause, re.I)
        for clause in clauses)


def _service_dates(notes, *, soap=False):
    label = r'(?:date of service|service date)' if soap else r'date of service'
    return re.findall(r'(?im)^\s*' + label + r'\s*:\s*([^\r\n]+)', notes)


def _soap_exclusion_total(text):
    """An explicit referenced total must equal its adjacent physician total."""
    from .clinical_assertions_v4 import _TIME_COUNT
    from .clinical_source_context import _number
    match = re.match(r'\s*the\s+(?P<total>'+_TIME_COUNT+r')\s+minutes\b', text, re.I)
    if match is None:
        return None
    raw = match['total']
    return Decimal(raw) if re.fullmatch(r'\d+(?:\.\d+)?', raw) else Decimal(_number(raw))


def _soap_office_visit(text, scope, *, documented=False):
    """Complete patient attendance wording, without inferred setting or owner."""
    name = scope.get('patient_name') or ''
    ordinary = re.sub(r'^synthetic\s+', '', name, flags=re.I)
    aliases = {name, ordinary, ordinary.split()[0] if ordinary else ''} - {''}
    patient = r'(?:he|she|they|the\s+patient' + ''.join('|'+re.escape(n) for n in sorted(aliases)) + r')'
    attendance = (r'(?:is\s+an?\s+\d{1,3}-year-old\s+(?:woman|man|person)\s+attending|'
                  r'(?:is\s+)?attending|attends)')
    specialty = (r'primary\s+care|family\s+medicine|internal\s+medicine|'
        r'gastroenterology|cardiology|dermatology|neurology|orthopedic|orthopaedic|psychiatry|'
        r'pediatric|paediatric|oncology|endocrinology|rheumatology|pulmonology|urology|'
        r'gynecology|gynaecology|obstetric|surgical')
    office_description = r'(?:(?:medical|clinical|outpatient|'+specialty+r')\s+)?'
    if documented:
        # A facility descriptor and one specialty compose in v8; arbitrary
        # modifiers or two competing specialties still fail the whole frame.
        # Earlier contracts retain their exact single-descriptor grammar.
        office_description = r'(?:(?:medical|clinical|outpatient)\s+)?(?:(?:'+specialty+r')\s+)?'
        # Convert this whole, literal attendance clause to the already bounded
        # medical-office frame; no partial match or unknown tail is discarded.
        text = re.sub(r'^(?P<patient>'+patient+r')\s+is\s+an?\s+(?P<age>\d{1,3})-year-old\s+'
            r'(?P<sex>woman|man|person)\s+seen\s+in\s+person\s+in\s+',
            lambda m: m['patient']+' is a '+m['age']+'-year-old '+m['sex']+' attending an in-person visit in ',
            text, flags=re.I)
    if re.search(r'\b(?:possible|possibly|uncertain|unverified|unconfirmed|maybe|apparently|'
                 r'presumed|tentative|cancelled|canceled|not|never|only)\b', text, re.I):
        return False
    return bool(re.fullmatch(patient+r'\s+'+attendance+r'\s+(?:a|an|the)\s+'
        r'(?:(?:new|established)[ -]patient,?\s+)?in-person\s+(?:visit|consultation)\s+'
        r'in\s+(?:a|an|the)\s+(?:(?:u\.s\.|us|united\s+states)\s+)?'
        +office_description+r'office\s*\.?', text, re.I))


def _source_time_analysis(notes, *, modern=False, complete=False, soap=False, documented=False):
    """One source-bound interpretation shared by review and export checks.

    Only the prospective coding contract calls this reader. Source ownership,
    section timing and treating-clinician names come from the same literal
    context inventory used by clinical extraction. Old reviews retain their
    exact eight facts, quotations and hashes under the original reader.
    """
    from .clinical_source_context import source_context, SOURCE_GOVERNANCE_PROFILE, COMPLETE_ASSERTION_PROFILE, SOAP_ASSERTION_PROFILE, time_kind
    from .generation import source_units
    units, _ = source_units(notes, [])
    profile = SOAP_ASSERTION_PROFILE if soap else COMPLETE_ASSERTION_PROFILE if complete else SOURCE_GOVERNANCE_PROFILE if modern else None
    scope = source_context(notes, units, profile=profile,
        time_exclusion_contract=DOCUMENTED_TIME_CONTRACT if documented else None)
    found = {key: [] for key in REQUIRED_TIME_FACTS}
    blockers, service_errors, evaluated = list(scope['issues']), [], False
    service_date = None
    if modern:
        dates = [_calendar_day(raw) for raw in _service_dates(notes, soap=soap)]
        if dates and None not in dates and len(set(dates)) == 1:
            service_date = dates[0]
        elif dates:
            blockers.append('The source service date is unresolved or contradictory.')
    totals = []
    exclusions = []
    new_patient_history = []
    active_total, previous_end = None, None

    def add(key, value, unit):
        found[key].append({'key': key, 'value': value, 'source': 'saved note',
            'start': unit['start'], 'end': unit['end'], 'quote': unit['quote']})

    for unit in units:
        text, low = unit['quote'], unit['quote'].casefold()
        if previous_end is None or re.search(r'\r?\n\s*\r?\n', notes[previous_end:unit['start']]):
            active_total = None
        previous_end = unit['end']
        time_low = ' '.join(_current_account_clauses(text)).casefold()
        time_reference = re.search(r'\b(?:' + _ROLE + r')\s+(?:total\s+)?time\b|'
            r'\b(?:personally\s+)?spent\b[^.;]*\bminutes?\b|\b(?:this|that|the|documented) total(?: time)?\b|'
            r'\b(?:these|those|the|documented)\s+' + _NUMBER + r'\s+minutes?\b|'
            r'\bminutes?\b[^.;]*\b(?:date of service|encounter date)\b|\btime (?:above|below)\b', time_low)
        integrity = _time_integrity_assertion(text)
        local = scope['units'].get(unit['start'], {})
        # Qualifying prior care is deliberately historical. Its bearing on
        # current new-patient status cannot be discarded with old time facts.
        if (modern and local.get('subject') == 'patient' and local.get('section_timing') == 'current'
                and not local.get('issues')):
            history_error = _new_patient_service_history(text, scope)
            if history_error:
                new_patient_history.append(history_error)
        if local.get('subject') != 'patient' or local.get('timing') != 'current' or local.get('issues'):
            # Ambiguous practitioner-time material cannot supply or silently
            # qualify an earlier total. Explicit foreign/past sections retain
            # their own scope; shared backward-reference checks handle actual
            # reassignment of the current patient's earlier time statement.
            if local.get('subject') == 'ambiguous' and time_reference and not integrity:
                service_errors.append('A practitioner-time assertion has unresolved source ownership.')
            active_total = None
            continue
        complete_exclusion = False
        documented_exclusion = None
        documented_claim = None
        if soap:
            from .clinical_assertions_v4 import strict_exclusion
            complete_exclusion = strict_exclusion(text)
        if documented:
            from .documented_time_source import exclusion as documented_exclusion_for, qualification, linked_claim, unrelated_account, separate_exclusion
            if separate_exclusion(text):
                # This complete separate account supplies no current facts and
                # cannot connect a patient's total to a later exclusion.
                active_total = None
                continue
            documented_exclusion = documented_exclusion_for(text)
            documented_claim = linked_claim(text, established=bool(totals),
                service_established=bool(found['setting'] or found['patient_status']),
                status_established=bool(found['patient_status']))
            if unrelated_account(text):
                time_reference = None
            complete_exclusion = complete_exclusion or documented_exclusion is not None
        if _affirmed_time_retraction(text) and not complete_exclusion:
            service_errors.append('The complete source retracts or questions the documented service or time.')
        if _unsafe(notes, unit['start'], text):
            if documented_claim and not integrity and not complete_exclusion:
                blockers.append('A current time-account or service qualification requires complete source review.')
                service_errors.append('A current time-account or service qualification requires complete source review.')
            if time_reference and not integrity:
                service_errors.append('A competing or qualified practitioner-time statement requires clarification.')
            active_total = None
            continue
        if _evaluation_denied(text, scope):
            service_errors.append('The complete source denies participation in the documented physician evaluation.')
        negative = bool(re.search(r'\b(?:no|not|never|denies?|without)\b', low))
        office = re.search(r'\b(?:office (?:visit|consultation|encounter)|outpatient (?:office )?(?:visit|consultation))\b', low)
        if modern and not office:
            office = re.fullmatch(r'(?:encounter|visit type' + ('|visit' if complete else '') + r')\s*:\s*(?:(?:new|established)[ -]patient,?\s*)?'
                r'(?:in-person\s+)?(?:visit|consultation)\s+in\s+(?:a|an|the)\s+'
                r'(?:(?:u\.s\.|us|united states)\s+)?(?:[a-z]+\s+){0,3}office\.?', low)
        if soap and not office:
            office = _soap_office_visit(text, scope, documented=documented)
        if office and not negative:
            add('setting', 'outpatient_office', unit)
        status_text = re.sub(r'^(?:new|established)[ -]patient history\s*:', '', low) if modern else low
        for status in ('new', 'established'):
            if re.search(r'\b' + status + r'[ -]patient\b', status_text):
                if negative:
                    blockers.append('The documented patient-status assertion is negated or qualified.')
                else:
                    add('patient_status', status, unit)
        if re.search(r'\b(?:inpatient|emergency department)\b', low) and not negative:
            blockers.append('A non-office encounter setting is also documented.')
        timing = _time_statement(text, scope, modern=modern, service_date=service_date, soap=soap)
        if timing:
            totals.append(timing['minutes'])
            active_total = timing['minutes']
            add('time_minutes', timing['minutes'], unit)
            add('time_qualified_clinician', True, unit)
            if timing['same_day']:
                add('time_same_day', True, unit)
            evaluated |= timing['evaluated']
        basis = bool(re.search(r'\b(?:office\s+)?e/m\s+selection\b.*\bbased on total (?:physician )?time\b', low))
        if soap and time_kind(text, profile=profile) == 'basis':
            basis = True
        if basis and not negative:
            add('em_basis', 'time', unit)
        if re.search(r'\be/m\s+selection\b.*\b(?:not based on|medical decision making|mdm)\b', low):
            blockers.append('A conflicting E/M selection basis is documented.')
        exclusion = re.match(r'(?:(?:this|the) (?:(?P<total>\d+) minutes|total(?: time)?)|they)\s+(?:also\s+)?'
                             r'(?P<action>excludes?|does not include)\b(?P<tail>.*)', low)
        if documented_exclusion is not None:
            if (documented_exclusion['prior_day'] is not None
                    and (service_date is None or documented_exclusion['prior_day'] >= service_date)):
                blockers.append('Excluded prior-day work must name a valid date before the service date.')
            if active_total is None or documented_exclusion['named_total'] != active_total:
                blockers.append('The time exclusion has no adjacent source-bound physician total.')
            else:
                exclusions.append((documented_exclusion['named_total'], unit))
                if documented_exclusion['staff']:
                    add('time_excludes_staff', True, unit)
                if documented_exclusion['separately_reported']:
                    add('time_excludes_separately_reported', True, unit)
            exclusion = True
        elif exclusion:
            tail = exclusion['tail']
            if active_total is None or exclusion['total'] and int(exclusion['total']) != active_total:
                blockers.append('The time exclusion has no adjacent source-bound physician total.')
            elif (re.search(r'\b(?:neither|nor|except|but|however|some|part|portion|includes?|including|not excluded)\b', tail)
                    or re.search(r'\b(?:not|never)\s+(?:exclude|excluding)\b', low)):
                blockers.append('The time-exclusion assertion is negated or qualified.')
            else:
                exclusions.append((int(exclusion['total']) if exclusion['total'] else None, unit))
                if re.search(r'\b' + (_STAFF_CURRENT if modern else _STAFF) + r'\b', tail):
                    add('time_excludes_staff', True, unit)
                if re.search(r'\bseparately reported services' + ('?' if soap else '') + r'\b', tail):
                    add('time_excludes_separately_reported', True, unit)
        if soap and not exclusion:
            if complete_exclusion:
                exclusion = True
                named_total = _soap_exclusion_total(text)
                if active_total is None or named_total is not None and named_total != active_total:
                    blockers.append('The time exclusion has no adjacent source-bound physician total.')
                else:
                    exclusions.append((named_total, unit))
                    if re.search(r'\b' + _STAFF_CURRENT + r'\b', low):
                        add('time_excludes_staff', True, unit)
                    if re.search(r'\bseparately reported services?\b', low):
                        add('time_excludes_separately_reported', True, unit)
        staff = _STAFF_CURRENT if modern else _STAFF
        ineligible = bool(re.search(r'\b(?:' + staff + r'|separately reported services|preceding day|previous day|prior day)\b', low))
        if ineligible and not exclusion and (
                re.search(r'\b(?:includes?|including|included|counted|spent by|performed by)\b', low)
                or re.search(r'\b(?:not exclude|not excluded|does not exclude)\b', low)
                or re.search(r'\b(?:minutes?|time)\s+(?:is|are|was|were)\s+(?:all\s+)?(?:' + staff + r')\b', low)
                or re.search(r'\bof (?:these|the)\s+[^.;]*\bminutes\b', low)):
            blockers.append('The documented total includes ineligible staff, other-day or separately reported time.')
        if time_reference and not timing and not exclusion and not basis and not integrity:
            service_errors.append('A competing or qualified practitioner-time statement requires clarification.')
        if (re.search(r'\b(?:encounter|visit|appointment|consultation)\b[^.;]*\b(?:did not|never)\s+(?:occur|take place|happen)\b', low)
                or re.search(r'\b(?:did not|never)\s+(?:see|evaluate|examine)\b[^.;]*\bpatient\b', low)
                or re.search(r'\bpatient\b[^.;]*\b(?:was not|not)\s+(?:seen|evaluated|examined)\b', low)
                or re.search(r'\bno\s+(?:office\s+)?(?:evaluation|examination)\s+(?:(?:was|is)\s+)?(?:performed|completed|occurred|provided)\b', low)
                or re.search(r'\b(?:visit|encounter|consultation|evaluation|examination|appointment)\b[^.;]*\b(?:not (?:performed|completed|provided)|cancelled|canceled)\b', low)
                or re.search(r'\bno (?:(?:office|clinic|outpatient) )?(?:visit|consultation|appointment|encounter)\b', low)):
            service_errors.append('The complete source denies a completed office evaluation or examination.')
        if re.search(r'\b(?:examined|history (?:was )?obtained|examination (?:was )?performed)\b[^.;]*\b(?:this (?:encounter|visit)|today)\b', low) and not negative:
            evaluated = True
        work_qualification = modern and re.fullmatch(
            r'(?:these|those) are all ' + _ROLE + r' activities ' + _DAY + r'\.?', low)
        if complete and time_kind(text, profile=profile) == 'qualification':
            work_qualification = True
        if documented and qualification(text):
            work_qualification = True
        if documented_claim and not (timing or exclusion or basis or work_qualification or integrity):
            blockers.append('A current time-account or service qualification requires complete source review.')
            service_errors.append('A current time-account or service qualification requires complete source review.')
        if work_qualification and active_total is None:
            blockers.append('The physician-work qualification has no adjacent source-bound total.')
        if not timing and not exclusion and not basis and not work_qualification:
            active_total = None
    if any(total is not None and set(totals) != {total} for total, _unit in exclusions):
        blockers.append('The exclusion statement belongs to a different or unresolved physician total.')
    if modern and any(row['value'] == 'new' for row in found['patient_status']):
        blockers.extend(new_patient_history)
    facts = []
    for key, candidates in found.items():
        values = {str(row['value']) for row in candidates}
        if len(values) != 1:
            blockers.append(('Conflicting' if values else 'Missing') + ' documented ' + key.replace('_', ' ') + '.')
        else:
            facts.append(candidates[0])
    if not evaluated:
        service_errors.append('The complete source must document evaluation with history or examination during this encounter.')
    blockers = list(dict.fromkeys(blockers))
    return ({'status': 'documented' if not blockers else 'requires_clarification', 'facts': facts,
             'blockers': blockers, 'clinician_confirmed': False}, list(dict.fromkeys(service_errors)))


def citation_adequacy(spans, facts):
    """Provider spans must cover each fact, not merely appear in the input."""
    covered = [f['key'] for f in facts if any(s.get('status') == 'valid' and s.get('context_index') == 0
               and s['start'] <= f['start'] and s['end'] >= f['end'] for s in spans)]
    missing = [key for key in REQUIRED_TIME_FACTS if key not in covered]
    return {'status': 'complete_for_time_review' if not missing else 'insufficient_for_time_review',
            'missing_facts': missing,
            'reason': 'Provider source spans do not independently establish all time-selection facts.' if missing
                      else 'Source spans cover the documented time facts; dated criteria and clinician confirmation remain separate.'}
