"""Bounded v4 source forms; these helpers never establish clinical ownership.

Returned spans cover the complete assertion. Callers must independently bind
patient, section, encounter, polarity and any declared immediate antecedent.
No old profile imports this module and no clinical vocabulary is inferred.
"""
from datetime import datetime
import re

from .clinical_assertions import _MONTH, _SUBJECT


_OBJECT_SCOPE = re.compile(
    r'\b(?:I|we|you|me|us|my|our|your|he|she|they|it|his|her|their|patient|mother|father|family|grandmother|'
    r'grandfather|aunt|uncle|cousin|niece|nephew|sibling|brother|sister|daughter|'
    r'son|child|husband|wife|partner|spouse|friend|relative|another|other|'
    r'is|are|was|were|has|have|had|does|do|did|can|will|would|may|might|could|'
    r'should|must|not|no|never|without|only|if|unless|except|although|despite|'
    r'because|when|until|before|after|and|or|but|that|which|who|whose|'
    r'reported|reportedly|unverified|uncertain|unclear|possible|possibly|probable|probably|'
    r'apparent|apparently|alleged|allegedly|suspected|assumed|presumed|'
    r'confirmed|unconfirmed|retracted|withdrawn|incorrect|invalid|hypothetical|'
    r'suppose|assuming|imagine|previous|prior|earlier|yesterday|tomorrow|today|currently|'
    r'now|sometimes|occasionally|states?|says?|reports?|belongs?|refers?)\b', re.I)


def _bounded_nominal(text, nominal):
    """A complete object must also satisfy the caller's nominal grammar."""
    value = re.sub(r'^(?:a|an|the)\s+', '', text.strip(), flags=re.I)
    return bool(re.fullmatch(r'[A-Za-z][A-Za-z-]*(?:\s+[A-Za-z][A-Za-z-]*){0,7}', value)
        and not _OBJECT_SCOPE.search(value)
        and not re.match(r'(?:for|from|to|in|on|at|per|according|regarding|concerning|about|as|with|under|during|via)\b', value, re.I)
        and not re.search(r'\b[A-Za-z]+ly\b', value, re.I)
        and nominal(value))


def family_history_order(text, nominal):
    """One complete present order whose indication is a family history.

    The indication is neither a beneficiary nor a patient diagnosis. Only the
    whole order is a selectable value: its test, relationship and collection
    plan cannot be separated into a performed service or confirmed disease.
    Source ownership, current encounter and Plan section remain caller gates.
    """
    value = text.strip().removesuffix('.').strip()
    if not value or any(char in value for char in '\r\n'):
        return None
    match = re.fullmatch(r'(?:I\s+(?:have\s+)?ordered\s+(?P<active>.+?)|'
        r'(?P<passive>.+?)\s+is\s+ordered)\s+for\s+'
        r'(?P<relationship>family\s+history)\s+of\s+(?P<indication>.+?),\s*'
        r'with\s+(?P<collection>collection\s+planned\s+(?:tomorrow|after\s+this\s+visit))',
        value, re.I)
    if not match:
        return None
    object_group = 'active' if match['active'] else 'passive'
    # No embedded attribution, modifier of truth, second predicate or scope
    # adjunct may hide inside an otherwise nominal test/indication phrase.
    extra_scope = r'\b(?:for|from|to|in|on|at|per|according|regarding|concerning|about|as|with|under|during|via|of|unknown|pending|awaiting|unconfirmed|recalled|disputed|disregard|ignore|following|above|below|listed)\b'
    for phrase in (match[object_group], match['indication']):
        if not _bounded_nominal(phrase, nominal) or re.search(extra_scope, phrase, re.I):
            return None
    offset = text.index(value)
    span = lambda group: (offset + match.start(group), offset + match.end(group))
    return {'kind': 'family_history_order', 'values': [(offset, offset + len(value))],
        'required_subject': 'patient', 'required_polarity': 'affirmed',
        'required_timing': 'current', 'required_section': 'plan',
        'test': span(object_group), 'relationship': span('relationship'),
        'indication': span('indication'), 'collection': span('collection')}


def named_medication_trial(text, number_pattern):
    """Return the exact drug name from a complete dated oral-dose trial.

    This establishes syntax only. The caller must bind the trial to the same
    patient/section and must not skip unknown units to supply an antecedent.
    """
    date = r'\d{1,2}\s+(?:' + _MONTH + r')(?:\s+\d{4})?'
    medicine = r'[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z][A-Za-z0-9-]*){0,3}'
    match = re.fullmatch(_SUBJECT + r'\s+previously\s+(?:took|tried|used)\s+'
        r'(?P<medicine>' + medicine + r')\s+(?P<dose>' + number_pattern + r')\s+(?:mg|g|mcg|mL)\s+'
        r'(?:by\s+mouth|orally)\s+(?:each\s+(?:morning|evening)|once\s+daily|daily|nightly)'
        r'(?:\s+for\s+(?P<indication>.+?))?\s+from\s+(?P<first>' + date + r')'
        r'\s+through\s+(?P<last>' + date + r')\.?', text.strip(), re.I)
    if not match or _OBJECT_SCOPE.search(match['medicine']):
        return None
    if match['indication'] and not _bounded_nominal(match['indication'], lambda value: True):
        return None
    if re.match(r'[+\-\u2212]', match['dose']):
        return None
    dates = []
    for field in ('first', 'last'):
        value = match[field]
        try:
            dates.append(datetime.strptime(value if re.search(r'\d{4}$', value)
                else value + ' 2000', '%d %B %Y'))
        except ValueError:
            return None
    if all(re.search(r'\d{4}$', match[field]) for field in ('first', 'last')) and dates[0] > dates[1]:
        return None
    return match['medicine']


def _iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        return None


def _trial_range_dates(text):
    """Internal dates for comparison only; no reconstructed source evidence."""
    markers = re.findall(r'\b(?:from|through)\b', text, re.I)
    if [word.casefold() for word in markers] != ['from', 'through']:
        return None

    def date_pattern(prefix):
        return (r'(?P<' + prefix + r'_day>\d{1,2})\s+(?P<' + prefix + r'_month>' + _MONTH
            + r')(?:\s+(?P<' + prefix + r'_year>\d{4}))?')

    match = re.search(r'\bfrom\s+' + date_pattern('first') + r'\s+through\s+'
        + date_pattern('last') + r'\s*\.?\s*$', text, re.I)
    if not match or not (match['first_year'] or match['last_year']):
        return None
    dates = []
    for prefix, other in (('first', 'last'), ('last', 'first')):
        year = match[prefix + '_year'] or match[other + '_year']
        value = ' '.join((match[prefix + '_day'], match[prefix + '_month'], year))
        try:
            dates.append(datetime.strptime(value, '%d %B %Y'))
        except ValueError:
            return None
    return tuple(dates) if dates[0] <= dates[1] else None


def trial_temporally_bound(text, service_date):
    """Check an already recognized trial against a canonical service date.

    This prospective check supplies no output date. An explicit range needs
    at least one source year; a single shared year is usable only for an ordered
    range within that calendar year. A historical trial with no range retains
    its separately recognized relative timing, provided the service date exists.
    """
    encounter = _iso_date(service_date)
    if not isinstance(text, str) or encounter is None:
        return False
    if not re.search(r'\b(?:from|through)\b', text, re.I):
        return True  # Syntax and explicit historical ownership are caller gates.
    dates = _trial_range_dates(text)
    return bool(dates and dates[1] <= encounter)


def stopping_temporally_bound(text, trial_text, service_date):
    """Bind a complete current-nonuse continuation to trial end and encounter.

    An omitted stopping year is usable only when the original trial range and
    service date admit exactly one calendar date. No output date is supplied.
    The caller separately verifies the same medicine, patient and source scope.
    """
    from .clinical_assertions import assertion_frame as legacy_frame
    encounter = _iso_date(service_date)
    if not isinstance(text, str) or not isinstance(trial_text, str) or encounter is None:
        return False
    trial = _trial_range_dates(trial_text)
    if not trial or trial[1] > encounter:
        return False
    frame = legacy_frame(text, lambda value: False)
    if not frame or frame['kind'] != 'medication_absence' or frame.get('antecedent') != 'named_medication_trial':
        return False
    match = re.search(r'\bon\s+(?P<day>\d{1,2})\s+(?P<month>' + _MONTH
        + r')(?:\s+(?P<year>\d{4}))?\s+because\b', text, re.I)
    if not match:
        return False
    years = [int(match['year'])] if match['year'] else range(trial[1].year, encounter.year + 1)
    candidates = 0
    for year in years:
        try:
            stopped = datetime.strptime(' '.join((match['day'], match['month'], str(year).zfill(4))), '%d %B %Y')
        except ValueError:
            continue
        if trial[1] <= stopped <= encounter:
            candidates += 1
            if candidates > 1:
                return False
    return candidates == 1


def assertion_frame(text, nominal):
    """Recognize complete literal negatives/uncertainty, with owner metadata.

    ``values`` never exposes a condition name, an affirmative prefix, or a
    negative fragment independently. Metadata is a requirement for callers;
    recognition alone cannot clear a fact's existing holds.
    """
    value = text.strip().removesuffix('.').strip()
    if not value:
        return None
    offset = text.index(value)

    def frame(kind, polarity, **metadata):
        return {'kind': kind, 'values': [(offset, offset + len(value))],
            'required_polarity': polarity, 'required_subject': 'patient', **metadata}

    if ';' in value:
        parts = value.split(';')
        if not 2 <= len(parts) <= 4 or any(not part.strip() for part in parts):
            return None
        assertions, cursor = [], 0
        for part in parts:
            child = assertion_frame(part, nominal)
            if not child or child['kind'] not in ('diagnostic_limit', 'uncertainty'):
                return None
            assertions.append({**child, 'values': [(offset + cursor + start, offset + cursor + end)
                for start, end in child['values']]})
            cursor += len(part) + 1
        # The group has no polarity or whole-sentence value. Consumers must
        # select the exact child and enforce that child's own qualifications.
        return {'kind': 'diagnostic_qualifications',
            'values': [span for child in assertions for span in child['values']],
            'assertions': assertions}

    if re.fullmatch(r'It\s+(?:gave|provided)\s+no\s+(?:meaningful\s+)?(?:relief|benefit)', value, re.I):
        return frame('medication_response', 'negated', required_timing='past',
            antecedent='named_medication_trial', antecedent_distance=1)

    cause = re.fullmatch(r'The\s+cause\s+of\s+(?P<object>.+?)\s+'
        r'(?:is\s+not|has\s+not\s+been)\s+(?:established|determined)', value, re.I)
    if cause and _bounded_nominal(cause['object'], nominal):
        return frame('diagnostic_limit', 'negated', object=cause['object'],
            limits=['cause'], required_section='assessment')

    possible = re.fullmatch(r'(?P<object>.+?)\s+is\s+a\s+possibility\s+but\s+'
        r'(?:is\s+)?not\s+diagnosed', value, re.I)
    if possible and _bounded_nominal(possible['object'], nominal):
        return frame('uncertainty', 'uncertain', object=possible['object'],
            diagnosis_not_established=True, required_section='assessment')

    subtype = re.fullmatch(r'(?P<object>.+?)\s+is\s+documented\s+without\s+an?\s+'
        r'established\s+(?P<limits>subtype\s+or\s+cause|cause\s+or\s+subtype|subtype|cause)', value, re.I)
    if subtype and _bounded_nominal(subtype['object'], nominal):
        return frame('diagnostic_limit', 'negated', object=subtype['object'],
            limits=re.split(r'\s+or\s+', subtype['limits'].casefold()),
            documented_object=True, required_section='assessment')

    absent = re.fullmatch(r'(?P<objects>.+?)\s+are\s+not\s+diagnosed\s+today', value, re.I)
    if absent:
        objects = re.split(r'\s*,\s*(?:and\s+)?|\s+and\s+', absent['objects'], flags=re.I)
        if 2 <= len(objects) <= 8 and all(_bounded_nominal(item, nominal) for item in objects):
            return frame('diagnostic_limit', 'negated', objects=objects,
                diagnosis_not_established=True, required_timing='current', required_section='assessment')
    return None
