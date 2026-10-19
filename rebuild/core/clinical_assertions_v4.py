"""Prospective SOAP syntax additions; original source spans remain authoritative.

These readers classify complete source statements. They supply no facts,
clinical conclusions, missing data, billing criteria or approval authority.
The v3 functions remain unchanged for retained jobs.
"""
import re

from .clinical_assertions import _COUNT, _QUALIFIER

PROFILE = 'source-soap-assertions-v4'
SOAP_HEADINGS = {'S': 'subjective', 'O': 'objective', 'A': 'assessment', 'P': 'plan'}


def soap_heading(text):
    """Only an entire uppercase heading may establish a SOAP section."""
    return SOAP_HEADINGS.get(text.strip().removesuffix(':').strip())


def explicit_order(text):
    """Detect an asserted order for completeness; never grant clinical truth."""
    return bool(re.match(r'\s*I\s+(?:have\s+)?ordered\b',text,re.I)
        or re.match(r'\s*(?:a\s+|an\s+|the\s+)?[^.!?;]+?\s+(?:is|was|has\s+been)\s+ordered\b',text,re.I))


def foreign_order_beneficiary(text):
    """An explicit other recipient is local to this order, not the next unit."""
    # Imported only at runtime so both readers share the same person-role
    # vocabulary without an initialization cycle. An indication's family
    # history is not itself a recipient.
    from .clinical_source_context import PERSON
    relative=r'(?!family\s+history\b)(?:'+PERSON+r'|parents?)'
    possessive=r"(?:her|his|their|my|your|(?:the\s+)?patient['’]s)"
    return bool(explicit_order(text) and re.search(r'\b(?:for|to|on|from)\s+(?:'
        +possessive+r'\s+'+relative+r'|(?:another|different|other)\s+patient)\b',text,re.I))


def _nominal(text):
    # Bound noun phrases cannot swallow a finite proposition or attribution.
    words = text.strip().split()
    return (1 <= len(words) <= 8
        and bool(re.fullmatch(r'[A-Za-z][A-Za-z-]*(?:\s+[A-Za-z][A-Za-z-]*){0,7}', text.strip()))
        and not re.search(r'\b(?:he|she|they|it|is|are|was|were|has|have|had|may|might|could|would|'
            r'if|unless|except|and|or|but|because|when|until|before|after|not|never|only|'
            r'states?|says?|reports?|belongs?|refers?|incorrect|invalid|retracted|withdrawn)\b', text, re.I))


def family_history_order_frame(text):
    from .soap_clinical_literals import family_history_order
    return family_history_order(text, _nominal)


def follow_up_frame(text):
    """Scheduled follow-up with a complete coordinated conditional safety net."""
    value = text.strip().removesuffix('.').strip()
    match = re.fullmatch(r'(?:follow-up|followup|review)\s+is\s+planned\s+'
        r'(?P<interval>in\s+' + _COUNT + r'\s+(?:days?|weeks?|months?))\s+'
        r'to\s+(?:discuss|review)\s+(?P<objects>.+?),\s*'
        r'with\s+earlier\s+contact\s+if\s+(?P<conditions>.+)', value, re.I)
    if not match or _QUALIFIER.search(value):
        return None
    objects = re.split(r'\s+and\s+', match['objects'], flags=re.I)
    if not 1 <= len(objects) <= 4 or not all(_nominal(obj) for obj in objects):
        return None
    conditions = re.split(r'\s+(?:and|or)\s+', match['conditions'], flags=re.I)
    if not 1 <= len(conditions) <= 4:
        return None
    for condition in conditions:
        clause = re.fullmatch(r'(?P<subject>.+?)\s+'
            r'(?:worsens?|persists?|recurs?|continues?|appears?|develops?)'
            r'(?:\s+(?:in|on)\s+(?P<location>.+))?', condition, re.I)
        if not clause or not _nominal(clause['subject']) or (clause['location'] and not _nominal(clause['location'])):
            return None
    offset = text.index(value)
    # The condition is retained as part of the whole instruction; it never
    # becomes a current finding. Only the explicit interval is an atomic value.
    return {'kind': 'conditional_follow_up', 'values': [(offset, offset + len(value)),
        (offset + match.start('interval'), offset + match.end('interval'))]}


_TIME_COUNT = (r'(?:[0-9]{1,3}(?:\.[0-9]+)?|one|two|three|four|five|six|seven|eight|nine|ten|'
    r'eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|'
    r'(?:twenty|thirty|forty|fifty|sixty)(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?)')
_TIME_UNIT = r'(?:minutes?|mins?|hours?|hrs?|seconds?|secs?)'
_PRIOR_DAY = r'(?:\s+(?:performed\s+)?on\s+the\s+(?:preceding|previous|prior)\s+day)?'
_STAFF_TIME = (r'(?:(?:clinical\s+)?staff|nursing)\s+'
    r'(?:time|work|(?:intake|rooming)(?:\s+work)?)' + _PRIOR_DAY)
_CLINICIAN_TIME = (r'(?:physician|clinician)\s+'
    r'(?:time|record\s+review|preparation|documentation)' + _PRIOR_DAY)
_SEPARATE_SERVICE = (r'(?:time(?:\s+spent)?\s+(?:for|on)\s+)?'
    r'(?:(?:any|an?\s+additional|an?)\s+)?separately\s+(?:reported|billed)\s+(?:services?|procedures?)')
_EXCLUDED_ITEM = (r'(?:(?:any|all)\s+)?(?:' + _TIME_COUNT + r'\s+' + _TIME_UNIT + r'\s+of\s+)?'
    r'(?:' + _STAFF_TIME + r'|' + _CLINICIAN_TIME + r'|' + _SEPARATE_SERVICE + r')')
_EXCLUDED_LIST = _EXCLUDED_ITEM + r'(?:(?:,\s*(?:and\s+)?|\s+and\s+)' + _EXCLUDED_ITEM + r'){0,7}'
# The enclosing account binder compares explicit totals in minutes only.
# Other units are safe inside excluded objects, never as an unbound total.
_EXCLUSION_SUBJECT = (r'(?:(?:this|the)\s+total|the\s+' + _TIME_COUNT
    + r'\s+minutes|they|(?:these|those)\s+minutes)')
_STRICT_EXCLUSION = re.compile(r'(?:'
    + _EXCLUSION_SUBJECT + r'\s+(?:also\s+)?(?:excludes?|does\s+not\s+(?:include|count))\s+'
    + _EXCLUDED_LIST + r'|'
    + _EXCLUDED_LIST + r'\s+(?:is|was|are|were)\s+(?:also\s+)?excluded\s+from\s+(?:this|the)\s+total|'
    + r'I\s+excluded\s+' + _EXCLUDED_LIST + r'\s+from\s+(?:this|the)\s+total)', re.I)


def strict_exclusion(text):
    """Recognize a whole exclusion statement, never an exclusion prefix.

    Only explicitly parsed time/service noun phrases may follow the exclusion
    predicate. Coordination joins those objects, not arbitrary propositions.
    Unknown wording therefore cannot exempt a later qualification, attribution
    or retraction from the source integrity checks. This classifies syntax only;
    the caller must still bind the statement to its total, owner and encounter.
    """
    value = text.strip().removesuffix('.').strip()
    return not any(char in value for char in '\r\n') and bool(_STRICT_EXCLUSION.fullmatch(value))


def time_kind(text):
    """Complete wording variants; callers still bind owner, date and total."""
    value = text.strip().removesuffix('.').strip()
    if re.fullmatch(r'(?:office\s+)?(?:E\s*/?\s*M|evaluation\s+and\s+management)\s+'
            r'(?:selection|level)\s+(?:is|was)\s+based\s+on\s+the\s+treating\s+'
            r'(?:physician|clinician)[\x27’]s\s+total\s+time\s+on\s+the\s+'
            r'(?:service\s+date|encounter\s+date|date\s+of\s+service)', value, re.I):
        return 'basis'
    if re.fullmatch(r'all\s+' + _COUNT + r'\s+activities\s+were\s+performed\s+by\s+the\s+'
            r'(?:physician|clinician)\s+on\s+the\s+(?:encounter\s+date|date\s+of\s+service)', value, re.I):
        return 'qualification'
    if re.fullmatch(r'time\s+for\s+(?:any\s+)?separately\s+reported\s+services?\s+'
            r'(?:is|was)\s+also\s+excluded\s+from\s+(?:this|the)\s+total', value, re.I):
        return 'exclusion'
    return None
