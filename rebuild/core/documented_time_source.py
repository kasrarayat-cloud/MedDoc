"""Finite v8 time wording; recognition never supplies owner, date or code authority."""
import re
from datetime import datetime

CONTRACT = 'source-bound-clinical-coding-v8'
_COUNT = r'(?:\d{1,4}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)'
_DATE = r'(?:\d{1,2} [A-Za-z]+ \d{4}|[A-Za-z]+ \d{1,2}, \d{4}|\d{4}-\d{2}-\d{2})'
_ACCOUNT_NUMBER = (r'(?:\d+(?:\.\d+)?|(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|'
    r'eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|'
    r'forty|fifty|sixty|seventy|eighty|ninety|hundred)(?:[- ](?:one|two|three|four|five|six|seven|eight|nine|hundred))*)')
_REFERENCE_MODIFIER = (r'(?:above|preceding|following|earlier|prior|previous|current|documented|recorded|'
    r'stated|reported|correct|corrected|actual|revised|amended|updated|new|final|true|listed|noted|'
    r'included|qualifying|same-day|physician[\x27’]s?|practitioner[\x27’]s?|physician|practitioner)')
_DISCOURSE_PREFIX = re.compile(r'(?:(?:however|actually|in fact|on review)(?:,\s*|\s+)'
    r'|(?:correction|amendment|addendum|update):\s*)', re.I)
_PREDICATE = (r'(?:(?:actually|also|now|still|indeed|apparently|possibly|reportedly)\s+)*'
    r'(?:is|are|was|were|should|must|may|might|remains?|includes?|excludes?|does|do|did|has|have|had|'
    r'will|would|belongs?|refers?|relates?|concerns?|pertains?|contains?|comprises?|overlapped|'
    r'overlaps?|occurred|happened|qualifies?|qualified|took)\b')
_ACCOUNT_SUBJECT = (r'(?P<quantifier>(?:all|some|no|none|any|each|every|both|only|part|portion)'
    r'(?:\s+of)?\s+)?(?P<article>(?:the|this|that|these|those)\s+)?'
    r'(?P<modifiers>(?:'+_REFERENCE_MODIFIER+r'\s+)*)'
    r'(?P<account>time(?:\s+for\s+separately\s+reported\s+services?)?|total|'
    r'(?:'+_ACCOUNT_NUMBER+r'\s+)?activities|work|'+_ACCOUNT_NUMBER+r'[ -]+minutes?(?:[ -]+total)?)')


def _separate_subject(prefix, subject=''):
    """Explicit other ownership governs a subject, not words in its predicate.

    An unknown preamble does not suppress a named current account. A bounded
    prior/foreign frame must finish immediately before that subject; an earlier
    clause cannot silently own a newly introduced current subject.
    """
    from .clinical_source_context import PERSON
    if re.search(r'\b(?:prior|previous|historical|past)\s+(?:visit|encounter|consultation)\b', subject, re.I):
        return True
    owner = r'(?:(?:his|her|their|the\s+patient[\x27’]s|the)\s+)?'+PERSON+r'(?:[\x27’]s)?'
    if re.search(r'\b'+owner+r'\s*$', prefix, re.I):
        return True
    prior = (r'(?:at|during|in|for)\s+(?:an?\s+|the\s+)?(?:unrelated\s+)?'
             r'(?:prior|previous|earlier|past|different|another)\s+(?:visit|encounter|consultation)')
    foreign = r'(?:for|regarding|about|concerning)\s+'+owner+r'(?:\s+(?:visit|encounter|account|record|time|total))?'
    return bool(re.search(r'\b(?:'+prior+'|'+foreign+r')\s*[,،:]\s*'
                          r'(?:(?:another|a different)\s+)?$', prefix, re.I))


def discourse_body(text):
    """Remove up to four anchored frames; None means unresolved prefix scope."""
    value = text.strip()
    for unused in range(4):
        prefix = _DISCOURSE_PREFIX.match(value)
        if prefix is None:
            return value
        value = value[prefix.end():].lstrip()
    return None if _DISCOURSE_PREFIX.match(value) else value


def exclusion(text):
    """Whole explicit exclusions only; unknown objects and predicates stay held."""
    value = text.strip().removesuffix('.').strip()
    active = re.fullmatch(r'The (?P<total>\d{1,4}) minutes exclude '+_COUNT+
        r' minutes of staff intake and '+_COUNT+r' minutes of physician chart review on (?P<date>'+_DATE+r')', value, re.I)
    if active:
        day = None
        for pattern in ('%d %B %Y', '%B %d, %Y', '%Y-%m-%d'):
            try:
                day = datetime.strptime(active['date'], pattern).date()
                break
            except ValueError:
                pass
        if day is not None:
            return {'named_total': int(active['total']), 'prior_day': day,
                    'staff': True, 'separately_reported': False}
        return None
    # These complete predicates have the same exclusion polarity. Unknown
    # negations, exceptions or additional predicates cannot enter this arm.
    passive = re.fullmatch(r'(?:Time for separately reported services? is excluded from|'
        r'No time for separately reported services? is included in) the '
        r'(?P<total>\d{1,4})-minute total', value, re.I)
    if passive:
        return {'named_total': int(passive['total']), 'prior_day': None,
                'staff': False, 'separately_reported': True}
    return None


def qualification(text):
    return bool(re.fullmatch(r'(?:These activities were all|All (?:three|3) activities were) '
                             r'completed by the (?:treating )?physician on the service date\.?',
                             text.strip(), re.I))


def separate_exclusion(text):
    """A complete foreign/prior frame owns only a complete exclusion body.

    Reuse the source scope grammar, then consume the entire predicate. Merely
    starting with a family member cannot exempt a later current-account claim,
    an unknown qualifier or a second predicate in the same source unit.
    """
    from .clinical_source_context import _account_preamble
    value = discourse_body(text)
    if value is None:
        return False
    frame = re.fullmatch(r'(?P<owner>[^,،:;\r\n]+)[,،:]\s*(?P<body>[^\r\n]+)', value)
    if frame is None:
        return False
    scope = _account_preamble(frame['owner'])
    return (not scope['current_owned'] and not scope['qualified']
            and exclusion(frame['body']) is not None)


def unrelated_account(text):
    """Complete separate volume, patient-waiting or prior-service accounts."""
    value = discourse_body(text)
    if value is None:
        return False
    if separate_exclusion(text):
        return True
    # A separate account cannot exempt an additional current claim in the
    # same original unit. Its complete predicate must finish the unit.
    if linked_claim(text, established=True):
        return False
    fluid = re.search(r'\bThe total fluid intake (?:is|was) \d+(?:\.\d+)? mL\.?$', value, re.I)
    waiting = re.search(r'\b(?:The patient|He|She|They)\s+spent\s+'+_ACCOUNT_NUMBER+
        r'\s+minutes\s+(?:in the waiting room|waiting(?: in the waiting room)?)'
        r'(?:\s+before\s+(?:this|the)\s+(?:encounter|visit))?\.?$', value, re.I)
    prior = re.search(r'\b(?:At|During|In)\s+(?:an?\s+|the\s+)?(?:unrelated\s+)?'
        r'(?:prior|previous|earlier|past|different)\s+(?:encounter|visit|consultation),\s+'
        r'(?:(?:another|a different|the|his|her|their)\s+(?:physician|clinician|practitioner)|'
        r'(?:Dr\.?|Doctor)\s+[A-Za-z][A-Za-z \x27’\-]{0,80})\s+(?:personally\s+)?spent\s+'
        +_ACCOUNT_NUMBER+r'\s+minutes\s+[^.;]+\.?$', value, re.I)
    return bool(fluid or waiting or prior)


def account_subjects(text):
    """Find complete nominal subjects before their finite predicates.

    Quantifiers and referential modifiers compose independently of the claim's
    predicate. An unconsumed owner or object (patient's work, household
    activities, total fluid intake) cannot become practitioner-account scope.
    """
    for match in re.finditer(r'\b'+_ACCOUNT_SUBJECT+r'\s+(?P<predicate>'+_PREDICATE+r')', text, re.I):
        if _separate_subject(text[:match.start()], match[0]):
            continue
        qualified = bool(re.search(r'\b(?:physician|practitioner)\b', match['modifiers'], re.I))
        referential = bool(match['quantifier'] or match['article'] or match['modifiers'])
        yield {'qualified_practitioner': qualified, 'referential': referential}


def linked_claim(text, *, established=False, service_established=None, status_established=None):
    """Bind current account/service subjects within the original bounded unit.

    This identifies a claim which the caller must consume completely or hold.
    The caller checks enclosing source ownership and encounter scope first.
    Foreign and historical objects do not make a current-account reassignment
    harmless: "these activities were performed yesterday" still names these
    activities. An unrelated past/foreign subject does not match these heads.
    """
    if service_established is None:
        service_established = established
    if status_established is None:
        status_established = service_established
    # Search complete subject/predicate frames, not an allowlist of possible
    # preparatory phrases. Prefixes never hide an explicit current account.
    value = text.strip()
    if separate_exclusion(value):
        return None
    for subject in account_subjects(value):
        if subject['qualified_practitioner'] or established and subject['referential']:
            return 'time'
    explicit = (r'(?:(?:(?:the|this|that)\s+)?(?:(?:correct|corrected|actual|revised|amended|additional)\s+)*'
        r'(?:physician|practitioner)\s+(?:time|total)\b|'
        r'(?:(?:the|this)\s+)?E\s*/\s*M\s+(?:time\s+)?selection\b)')
    quantified = (_ACCOUNT_NUMBER+r'[ -]+minutes?(?:[ -]+total\b|\s+(?:exclude|include|reviewing|'
        r'obtaining|examining|counseling|counselling|placing|documenting)\b)')
    quantified_work = r'(?:the|these|those)\s+'+quantified
    for pattern in (explicit, quantified_work if established else r'(?!)'):
        for match in re.finditer(pattern, value, re.I):
            if not _separate_subject(value[:match.start()]):
                return 'time'
    actor = r'(?:the\s+)?(?:physician|doctor|clinician|practitioner)'
    for match in re.finditer(r'\b'+actor+r'\s+[^.;]*?\b(?:complete|completed|perform|performed|provide|provided)\b'
                            r'[^.;]*\b(?:these|those|the|above)\s+activities\b', value, re.I):
        if not _separate_subject(value[:match.start()]):
            return 'time'
    # Additional explicit performer time cannot disappear because "additional"
    # occurs between the performer and the ordinary spent/quantity grammar.
    performer = r'(?:(?:Dr\.?|Doctor)\s+[A-Za-z][A-Za-z .\x27’\-]{0,80}|(?:(?:another|a different)\s+)?'+actor+r')'
    for match in re.finditer(r'\b'+performer+r'\s+(?:personally\s+|additionally\s+)?spent\b[^.;]*\bminutes?\b', value, re.I):
        if not _separate_subject(value[:match.start()]):
            return 'time'
    # A documented visit/status binds service qualifications independently of
    # a later physician-time total. Generic activities/work still need that
    # separate time antecedent above.
    article = r'(?:this|that|these|those|no|his|her|their|today[\x27’]s'+(r'|the' if service_established else '')+r')'
    service = (article+r'\s+(?:(?:'+_REFERENCE_MODIFIER+r'|office|clinical)\s+)*'
               r'(?P<service>visits?|encounters?|services?|consultations?|evaluations?|examinations?)\s+'+_PREDICATE)
    for match in re.finditer(r'\b'+service, value, re.I):
        if _separate_subject(value[:match.start()], match[0]):
            continue
        tail = value[match.end():]
        if (match['service'].casefold() not in ('evaluation', 'evaluations', 'examination', 'examinations')
                or re.search(r'\b(?:perform|performed|completed|provided|conducted|held|only|solely|by|'
                             r'cancelled|canceled|unverified|uncertain|not|never)\b', tail, re.I)):
            return 'service'
    if status_established:
        patient = r'(?:the\s+patient|he|she|they)\s+'+_PREDICATE+r'[^.;]*?'
        for match in re.finditer(r'\b'+patient+r'\b(?:new|established)(?:[- ]patient\b|'
                r'\s+to\s+(?:this|the|our|same)\s+(?:practice|specialty|group)\b|(?=\s*[.;]?\s*$))', value, re.I):
            if not _separate_subject(value[:match.start()]):
                return 'service'
    if discourse_body(text) is None:
        return 'time'
    return None
