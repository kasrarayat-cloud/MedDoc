"""Complete prospective condition predicates within positioned source scope.

This module supplies presence only. It supplies no clinical condition, code,
subtype, owner or approval; those remain independent source and dated gates.
"""
import re

_COUNT = (r'(?:\d{1,4}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|'
          r'thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|'
          r'thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?')
_DURATION = _COUNT + r'\s+(?:minutes?|hours?|days?|weeks?|months?|years?)'
_SITE = (r'(?:the\s+)?(?:(?:left|right|upper|lower|central|mid)\s+){0,2}'
         r'(?:breastbone|sternum|chest|abdomen|stomach|back|neck|throat|head|arm|leg|hand|foot|eye|ear)')
_QUALITY = r'(?:burning|aching|stabbing|cramping|sharp|dull|pressure|tightness|soreness|tingling|numbness)'


def nonassertion_frame(text):
    """A complete no-code/attribute predicate, never proof of a finding.

    Keep its explicit objects, polarity and clinical time separate. Unknown
    tails do not receive a frame and remain ordinary unresolved review gaps.
    """
    value = re.sub(r'\s+', ' ', text.strip().removesuffix('.')).casefold()
    nominal = r'[a-z][a-z /-]*[a-z]|[a-z]'
    unsafe = re.compile(r'\b(?:is|are|was|were|has|have|had|may|might|could|but|if|unless|'
        r'patient|he|she|they|not|no|never|possible|probable|suspected)\b')
    def objects(values):
        return bool(values and all(re.fullmatch(nominal, v) and not unsafe.search(v) for v in values))
    uncertain = re.fullmatch(r'(?P<object>.+?)\s+is\s+a\s+possibility,?\s+but\s+'
        r'(?:it\s+has\s+not\s+been|is\s+not)\s+(?:established|diagnosed|confirmed)', value)
    if uncertain and objects([uncertain['object']]):
        return {'kind':'unestablished_diagnosis', 'polarity':'uncertain', 'clinical_timing':'current',
            'objects':[uncertain['object']]}
    denied = re.fullmatch(r'no\s+diagnosis\s+of\s+(.+?)\s+(?:was\s+made|has\s+been\s+made|is\s+established)'
        r'\s+(?:today|at\s+this\s+encounter)', value)
    if denied:
        values = re.split(r'\s*,\s*(?:(?:or|and)\s+)?|\s+(?:or|and)\s+', denied[1])
        if objects(values):
            return {'kind':'negative_diagnosis', 'polarity':'negated', 'clinical_timing':'current', 'objects':values}
    history = re.fullmatch(r'(?:he|she|they|the\s+patient)\s+(?:has|have)\s+a\s+history\s+of\s+(.+?),\s+'
        r'currently\s+inactive;\s+(?:that|this|the)\s+condition\s+was\s+not\s+(?:evaluated|assessed|addressed)'
        r'\s+or\s+treated\s+at\s+this\s+(?:visit|encounter)', value)
    if history and objects([history[1]]):
        return {'kind':'inactive_unevaluated_history', 'polarity':'affirmed', 'clinical_timing':'past',
            'objects':[history[1]], 'current_evaluation':False}
    distinct = re.fullmatch(r'(?:the\s+)?(.+?)\s+and\s+(?:the\s+)?(.+?)\s+are\s+separate\s+'
        r'(?:concerns|symptoms|findings|problems)', value)
    if distinct and objects([distinct[1],distinct[2]]):
        return {'kind':'distinct_concerns', 'polarity':'affirmed', 'clinical_timing':'current',
            'objects':[distinct[1],distinct[2]], 'relation':'distinct'}
    unspecified = re.fullmatch(r'(?P<object>.+?)\s+is\s+unspecified:\s+(.+)', value)
    if unspecified and objects([unspecified['object']]):
        attribute = r'(?:cause|etiology|aetiology|subtype|type|severity|grade|stage|laterality|site|location)'
        target = re.escape(unspecified['object'])
        missing = re.fullmatch(r'neither\s+(?:its|the)\s+('+attribute+r')\s+nor\s+'
            r'(?:(?:a|an|the)\s+)?(?:'+target+r'\s+)?('+attribute+r')\s+has\s+been\s+established', unspecified[2])
        if missing:
            return {'kind':'unspecified_attributes', 'polarity':'negated', 'clinical_timing':'current',
                'objects':[unspecified['object']], 'attributes':[missing[1],missing[2]]}
    return None


def condition_reference_finding(before, after, context=None):
    """Qualify the selected condition as the grammatical assertion subject.

    The caller binds current-account ownership separately. A relative named in
    a copied-record predicate is its origin, not this condition's new subject.
    Attribute heads and other-person possessives cannot enter this reader.
    """
    if not condition_reference_subject(before, context):
        return None
    predicate = after.strip()
    copula = r'(?:(?:is|was|are|were|remains?)\s+)'
    if re.match(r'(?:(?:has|have|had|is|was|are|were)\s+)?never\s+(?:been\s+)?'
            r'(?:present|experienced|established|diagnosed)\b', predicate):
        return {'kind':'negated_presence', 'polarity':'negated'}
    if (re.match(copula+r'(?:(?:only|merely|just)\s+)?(?:(?:a|an|the)\s+)?'
            r'(?:fabricated|fictional|hypothetical|illustrative|invented|erroneous|incorrect|invalid)\b', predicate)
            or re.match(r'(?:(?:is|was|are|were|has\s+been|have\s+been)\s+)'
                r'(?:recorded|documented|entered|copied|reported|included)\s+(?:for|about|from)\s+'
                r'(?:(?:another|a\s+different|the\s+other)\s+patient|'
                r'(?:(?:her|his|their|the)\s+)?(?:mother|father|sister|brother|spouse|relative)(?:\s+s)?\s+'
                r'(?:note|record|account|visit))\b', predicate)):
        return {'kind':'source_assertion_governance', 'polarity':'unestablished'}
    if (re.match(copula+r'(?:(?:a|an|the)\s+)?(?:tentative|questionable|unproven|unverified)\b', predicate)
            or re.match(r'(?:remains?\s+to\s+be|(?:has|have|had)\s+yet\s+to\s+be)\s+'
                r'(?:confirmed|established|diagnosed|verified)\b', predicate)):
        return {'kind':'uncertain_presence', 'polarity':'uncertain'}
    return None


def reporting_reference_prefix(before, context=None):
    """Unwrap complete current-patient reporting predicates, never their object."""
    name = ' '.join(re.findall(r'[a-z0-9]+', ((context or {}).get('patient_name') or '').casefold()))
    subject = r'(?:he|she|they|the\s+patient|patient' + ('|'+re.escape(name) if name else '') + r')'
    prefix, attributed = before, False
    for _ in range(3):
        report = re.fullmatch(subject+r'\s+(?:says?|said|states?|stated|reports?|reported|notes?|noted|'
            r'explains?|explained)\s+(?:that\s+)?(?P<object>.*)', prefix, re.I)
        if report is None:
            break
        prefix, attributed = report['object'], True
    return prefix, attributed


def condition_reference_subject(before, context=None):
    """The condition itself is the subject, rather than a predicate's object."""
    prefix, attributed = reporting_reference_prefix(before, context)
    if re.fullmatch(r'\s*(?:(?:the|this|that|his|her|their)\s+)?'
            r'(?:(?:reported|documented|recorded|described|noted|mentioned|stated)\s+)?', prefix):
        return True
    if attributed:
        from .clinical_source_context import PERSON
        # A relative inside the embedded subject is distinct from a relative
        # introduced later as an assertion's origin or beneficiary.
        return re.search(r'\b'+PERSON+r'\b', prefix, re.I) is None
    return False


def benign_reference_predicate(clause, after, context, names):
    """Resolve complete attributes/actions without asserting condition presence.

    Recognition is per clinical predicate role. Every unknown tail remains a
    condition-specific review obligation; another positive sentence cannot
    supply the missing interpretation. None of these roles selects a code.
    """
    from .coding_completeness import _supporting_reference
    from .coding_engine import SHARED_SOURCE_CONTRACT
    frame = nonassertion_frame(clause)
    if frame and frame['kind'] in ('unspecified_attributes', 'distinct_concerns'):
        return True
    if _supporting_reference(clause, names, source_contract=SHARED_SOURCE_CONTRACT):
        return True
    predicate = after.strip()
    if re.fullmatch(r'(?:is|was|are|were|remains?|(?:may|might|could)\s+be)\s+'
            r'(?:mild|moderate|severe|slight|marked)', predicate):
        return True
    action = re.fullmatch(r'(?:may|might|could|should|must)\s+be\s+'
        r'(?:treated|managed|monitored|reviewed|reassessed)'
        r'(?:\s+with\s+(?P<object>[a-z][a-z -]*)|\s+(?:daily|weekly|regularly))?', predicate)
    if action and not re.search(r'\b(?:and|or|but|if|unless|except|not|no|never|another|different)\b',
            action['object'] or ''):
        return True
    # An onset is a temporal attribute of an independently present condition.
    # It cannot establish current presence by itself. Absolute and relative
    # dates, when both supplied, must describe the same past calendar day.
    from .clinical_source_context import source_date, _number
    from datetime import date, timedelta
    value = re.sub(r'\s+', ' ', clause.strip().removesuffix('.'))
    onset = re.fullmatch(r'.+?\s+(?:started|began)\s+(?P<relative>'+_COUNT+r'\s+(?:days?|weeks?)\s+ago|'
        r'yesterday|last\s+(?:week|month|year))?(?:\s*,?\s*on\s+(?P<date>.+))?', value, re.I)
    if not onset or not (onset['relative'] or onset['date']):
        return False
    absolute = source_date(onset['date']) if onset['date'] else None
    service = context.get('service_date')
    if onset['date'] and (absolute is None or service is not None and absolute > service):
        return False
    relative = re.fullmatch(r'('+_COUNT+r')\s+(days?|weeks?)\s+ago', onset['relative'] or '', re.I)
    if relative and absolute and service:
        count = _number(relative[1])
        if count is None or int(count) != count:
            return False
        delta = int(count) * (7 if relative[2].lower().startswith('week') else 1)
        if (date.fromisoformat(service)-timedelta(days=delta)).isoformat() != absolute:
            return False
    return True


def _description(tail):
    """A complete sensation/site description cannot carry a hidden qualifier."""
    return bool(re.fullmatch(r'(?:,\s*)?(?:described\s+as|characteri[sz]ed\s+by|felt\s+as)\s+'
        + _QUALITY + r'(?:\s+(?:behind|in|over|around|at)\s+' + _SITE + r')?'
        r'(?:\s+(?:without|with\s+no)\s+(?:radiation|spread))?', tail))


def current_presence(clause, before, after, subject, modifiers, row):
    """Read the complete predicate; unknown tails remain explicit holds.

    A duration introduced before a present patient report does not retime the
    encounter. A clinical assessment of evaluated findings uses its own current
    encounter time. The source-scope caller independently rejects foreign,
    historical, conditional, retracted or uncertain assertions.
    """
    from .coding_engine import _complete_presence_tail, norm
    duration_report = re.fullmatch(r'(?:for\s+' + _DURATION + r'\s*,?\s+)?' + subject +
        r'\s+(?:(?:has|have)\s+)?(?:noticed|notices|experienced|experiences|felt|feels)\s*' + modifiers, before)
    if duration_report:
        return True if _complete_presence_tail(after) or _description(after) else None
    # The same complete description may accompany an ordinary present report.
    described_report = re.fullmatch(subject + r'\s+(?:has|have|reports?|describes?|experiences?)\s*' + modifiers, before)
    if described_report and _description(after):
        return True
    if row['section'] in ('assessment', 'impression'):
        evaluated = re.fullmatch(r'(?P<findings>[a-z][a-z ,/-]*)\s+(?:was|were)\s+(?:both\s+)?'
            r'(?:evaluated|assessed|addressed|managed)(?:\s+and\s+discussed)?\s+'
            r'(?:today|at\s+this\s+encounter|during\s+this\s+encounter)', norm(clause))
        # The selected condition must itself be a complete coordinated object.
        # A condition nested inside "options for X" is an object of education
        # or planning, not an asserted finding. Check both edges of this exact
        # mention, in addition to the entire coordinated nominal list.
        separator = r'(?:,\s*(?:and\s+)?|\s*and\s+)'
        nominal = r'[a-z][a-z /-]*'
        before_object = re.fullmatch(r'(?:' + nominal + separator + r')*' + modifiers, before)
        after_object = re.fullmatch(r'(?:' + separator + nominal + r')*\s*(?:was|were)\s+(?:both\s+)?'
            r'(?:evaluated|assessed|addressed|managed)(?:\s+and\s+discussed)?\s+'
            r'(?:today|at\s+this\s+encounter|during\s+this\s+encounter)', after)
        if (evaluated and before_object and after_object and not re.search(
                r'\b(?:patient|he|she|they|whether|if|risk|possibility|question|screening|'
                r'possible|potential|probable|suspected|unconfirmed|uncertain|prior|previous|past|'
                r'resolved|negated|denied|options?|prevention|education|counseling|counselling|'
                r'prophylaxis|for|of|about|concerning|regarding)\b', evaluated['findings'])):
            return True
        if evaluated:
            # The old reader has a broader evaluation shortcut. An explicitly
            # rejected object cannot fall through and regain that permission.
            return None
    return False
