"""Prospective destination capabilities from complete affirmative definitions.

This module never uses a field label, patient facts or an answer to authorize a
destination. It recognizes compositional topic/attribute lists in the approved
meaning. Unknown or restrictive prose supplies no new capability. A routing
result of None means retain the existing completeness check, not drop it.
Source ownership, complete values, polarity and antecedent checks remain with
the caller. These helpers must be called only for the v21 scope contract.
"""
import re


def _text(value):
    return ' '.join(value.casefold().replace('\u2011', '-').replace('\u2013', '-').split()).strip().removesuffix('.')


def _narrative(d, *, subjects=('patient', 'encounter'), times=('any', 'current'), polarities=('any',)):
    scope = d.get('scope', {})
    return (d.get('value_type') == 'text' and d.get('answer_mode') == 'narrative'
        and scope.get('subject') in subjects and scope.get('temporality') in times
        and scope.get('polarity') in polarities)


def complete_denial_destination(d):
    if not _narrative(d, subjects=('patient',), polarities=('any', 'negative')):
        return False
    text = _text(d['meaning'])
    lead = r'(?:(?:document|record|list|describe|summarize)\s+)?(?:the\s+)?(?:all|complete|full)\s+(?:documented\s+|reported\s+)?'
    topic = r'(?:symptom\s+negatives|negative\s+symptoms|denied\s+symptoms|pertinent\s+negatives)'
    explanation = r'(?:\s*\(symptoms\s+(?:documented|recorded|reported)\s+as\s+(?:absent|denied)\))?'
    preservation = (r'(?:,\s*(?:each|every\s+(?:symptom|negative))\s+with\s+(?:its|the)\s+'
        r'(?:(?:exact|documented|original)\s+)*scope|,\s*(?:preserving|retaining)\s+(?:the\s+)?'
        r'(?:(?:exact|documented|original)\s+)*scope\s+of\s+(?:each|every)\s+(?:symptom|negative)|\s+as\s+documented)?')
    return bool(re.fullmatch(lead+topic+explanation+preservation, text))


def complete_exam_destination(d):
    if not _narrative(d):
        return False
    lead = r'(?:(?:document|record|describe|summarize)\s+)?(?:the\s+)?(?:complete|full|all)\s+(?:documented\s+|current\s+)?'
    topic = r'(?:(?:physical\s+)?(?:examination|exam)(?:\s+(?:findings|observations))?|objective\s+(?:findings|observations)\s+from\s+(?:physical\s+)?examination)'
    both = (r'(?:,\s*(?:including|retaining)\s+(?:both\s+)?(?:positive\s+and\s+negative|'
        r'negative\s+and\s+positive|normal\s+and\s+abnormal|abnormal\s+and\s+normal)\s+(?:findings|observations))?')
    return bool(re.fullmatch(lead+topic+both, _text(d['meaning'])))


def restricted_exam_destination(d):
    """A complete mixed examination cannot satisfy an explicit restriction.

    This is a prospective veto on broad rendering, not on inventory detection.
    It does not decide which narrower examination components are appropriate.
    """
    text = _text(d['meaning'])
    topic = r'\b(?:(?:physical\s+)?exam(?:ination)?(?:\s+(?:findings|observations))?|objective\s+(?:findings|observations))\b'
    restriction = (r'\b(?:only|alone|omit\w*|exclud\w*|except|without|restricted|limited|optional|'
                   r'ignore\w*|discard\w*|other\s+than|apart\s+from|'
                   r'(?:do|must|should)\s+not\s+(?:include|record|document|retain)|'
                   r"don['’]t\s+(?:include|record|document|retain))\b")
    return bool(re.search(topic, text) and re.search(restriction, text))


def historical_medicine_with_current_nonuse(d):
    if not _narrative(d, subjects=('patient',), times=('past',)):
        return False
    clauses = re.split(r'\.\s+', _text(d['meaning']))
    head, separator, attributes = clauses[0].partition(':')
    medicine = r'(?:medicine|medication|therapy|treatment)'
    if not separator or not re.fullmatch(r'(?:a\s+|the\s+)?(?:(?:stopped|discontinued|historical|past|prior|previous)\s+)+'
            +medicine+r'(?:\s+(?:trial|course|history))?(?:\s+as\s+documented)?', head):
        return False
    # This explicit restriction applies to the medicine trial. It cannot erase
    # the separately requested current non-use attribute or change its timing.
    for clause in clauses[1:]:
        if not re.fullmatch(r'(?:restricted\s+to\s+'+medicine+r'\s+used\s+before\s+the\s+(?:target|current)\s+encounter;\s*)?'
                r'documented\s+absence\s+is\s+(?:allowed|acceptable)', clause):
            return False
    current = r'(?:(?:explicit|documented)\s+)?(?:statement\s+of\s+)?(?:non[- ]?use\s+now|current\s+(?:non[- ]?use|cessation|absence))'
    ordinary = r'name|dose|dosage|route|frequency|indication|purpose|dates|trial\s+dates|response|benefit|outcome|stopping\s+reason|reason\s+for\s+stopping'
    items = re.split(r'\s*,\s*(?:and\s+)?|\s+and\s+', attributes.strip())
    return (len(items) >= 2 and all(re.fullmatch(r'(?:'+ordinary+'|'+current+r')', item) for item in items)
        and any(re.fullmatch(current, item) for item in items))


def _support_components(d):
    """Closed compositional lists of support topics and their attributes.

    It is safe to narrow an obligation only after every clause is accounted
    for. A topic mention in a prohibition, an unknown tail, or a partial status
    list therefore returns None and cannot remove a legacy obligation.
    """
    if not _narrative(d):
        return None
    text = _text(d['meaning'])
    text = re.sub(r'evaluation\s+and\s+management', 'e/m', text)
    clauses = re.split(r'\.\s+', text)
    if len(clauses) > 2:
        return None
    if len(clauses) == 2 and not re.fullmatch(
            r'retain\s+(?:documented\s+)?not-yet-done\s+or\s+not-resulted\s+status', clauses[1]):
        return None
    if re.search(r'\b(?:only|alone|not|never|without|except|excluding|omit\w*|restricted|limited|optional)\b', clauses[0]):
        return None
    components = set()
    for group in re.split(r'\s*,\s*(?:and\s+)?', clauses[0]):
        excluded_group = bool(re.match(r'\s*(?:the\s+)?excluded\s+', group))
        for item in re.split(r'\s+and\s+', group):
            item = re.sub(r'^(?:(?:the|documented|any|each|its|their)\s+)+', '', item.strip())
            minutes = r'(?:\s+with\s+(?:(?:its|their)\s+)?minutes)?'
            if re.fullmatch(r'(?:office\s+)?e/?m\s+selection\s+basis', item):
                components.add('time_basis')
            elif re.fullmatch(r'total\s+(?:physician|clinician)\s+time', item):
                components.add('time_total')
            elif re.fullmatch(r'(?:service\s+date|date\s+of\s+service|encounter\s+date)', item):
                components.add('service_date')
            elif re.fullmatch(r'included\s+activit(?:y|ies)'+minutes, item):
                components.add('time_included')
            elif re.fullmatch(r'(?:excluded\s+)?staff\s+time'+minutes, item) and excluded_group:
                components.add('time_excluded_staff')
            elif re.fullmatch(r'(?:excluded\s+)?prior-day\s+(?:physician|clinician)\s+time'+minutes, item) and excluded_group:
                components.add('time_excluded_prior')
            elif re.fullmatch(r'(?:excluded\s+time(?:\s+activities)?|time\s+(?:activity\s+)?exclusions)'+minutes, item):
                components.add('time_excluded')
            elif re.fullmatch(r'separately\s+reported\s+service\s+exclusion', item):
                components.add('time_excluded_service')
            elif re.fullmatch(r'(?:investigations?|tests?)\s+(?:ordered|planned)', item):
                components.add('investigation')
            elif re.fullmatch(r'evaluation\s+purpose', item):
                components.add('investigation_purpose')
            elif re.fullmatch(r'intended\s+(?:collection|performance)\s+timing', item):
                components.add('investigation_timing')
            elif re.fullmatch(r'(?:actual\s+)?collection(?:\s+status)?', item):
                components.add('investigation_collection')
            elif re.fullmatch(r'(?:actual\s+)?performance(?:\s+status)?', item):
                components.add('investigation_performance')
            elif re.fullmatch(r'results?\s+status(?:\s+(?:today|at\s+this\s+encounter))?', item):
                components.add('investigation_results')
            elif re.fullmatch(r'(?:procedure|procedural)\s+(?:performance\s+)?status(?:\s+(?:today|at\s+this\s+encounter))?', item):
                components.add('procedure')
            else:
                return None
    investigation_status = {'investigation_collection', 'investigation_performance', 'investigation_results'}
    if components & {'investigation', *investigation_status} and not {'investigation', *investigation_status} <= components:
        return None
    if components & {'investigation_purpose', 'investigation_timing'} and 'investigation' not in components:
        return None
    if components & {'time_basis', 'time_total', 'time_included', 'service_date'} and not {
            'time_basis', 'time_total', 'time_included', 'service_date'} <= components:
        return None
    exclusion_parts = {'time_excluded_staff', 'time_excluded_prior', 'time_excluded_service'}
    if components & exclusion_parts:
        # The current source obligation groups all time exclusions. A partial
        # destination must not gain that complete group merely by mentioning
        # one exclusion. Unknown/subset lists keep the existing gate.
        if 'time_excluded' not in components and not exclusion_parts <= components:
            return None
        components.add('time_excluded')
    return components or None


def restricted_support_destination(d):
    """Explicit restrictive instructions cannot use broad support fallback.

    'Excluded staff time' and 'service exclusion' name affirmative requested
    content; they are deliberately different from 'exclude/omit this content'.
    This only identifies a conflict requiring review, never edits a meaning.
    """
    if not _narrative(d):
        return False
    text = _text(d['meaning'])
    topic = (r'\b(?:investigations?|tests?|procedures?|procedural|e/?m|evaluation\s+and\s+management|'
             r'(?:physician|clinician|staff)\s+time|time\s+exclusions)\b')
    restriction = (r'\b(?:only|alone|omit\w*|exclude|excludes|excluding|except|without|restricted|limited|optional|'
                   r'ignore\w*|discard\w*|other\s+than|apart\s+from|'
                   r'(?:do|must|should)\s+not\s+(?:include|record|document|retain)|'
                   r"don['’]t\s+(?:include|record|document|retain))\b")
    return bool(re.search(topic, text) and re.search(restriction, text))


def _nonperformance_domains(source_text):
    """Account for every source object before narrowing a nonperformance row.

    An unknown coordinated object may be a procedure even when its neighbor
    explicitly says test. A keyword in one part cannot classify the whole row.
    The caller retains its old obligation whenever this complete parse fails.
    """
    text = _text(source_text)
    time = r'(?:\s+(?:today|during\s+this\s+encounter|at\s+this\s+encounter|from\s+this\s+visit))?'
    action = r'(?:collected|obtained|performed|done)'
    patterns = (
        r'no\s+(?P<object>.+?)\s+(?:was|were)\s+'+action+time,
        r'(?:the\s+)?(?P<object>.+?)\s+(?:was|were|has\s+been|have\s+been)\s+not\s+'+action+time,
        r'no\s+(?P<object>.+?)\s+(?:is|are)\s+(?:available|recorded)'+time,
        r'there\s+(?:is|are)\s+no\s+(?P<object>.+?)'+time,
        r'no\s+(?P<object>.+?)\s+(?:occurred|took\s+place)'+time,
        r'(?:the\s+)?(?P<object>.+?)\s+(?:has|have)\s+no\s+(?P<absent>results?)'+time,
    )
    domains = set()
    clauses = re.split(r'(?:\s*,\s*(?:and\s+)?|\s+and\s+)(?=(?:no|the|neither|it|there)\b)', text)
    for clause in clauses:
        match = next((m for p in patterns if (m := re.fullmatch(p, clause))), None)
        if match is None:
            return None
        objects = [match['object']]
        if match.groupdict().get('absent'):
            objects.append(match['absent'])
        for group in objects:
            for item in re.split(r'\s*,\s*(?:(?:and|or)\s+)?|\s+(?:and|or)\s+', group):
                item = re.sub(r'^(?:(?:the|a|an|any)\s+)+', '', item)
                if (not re.fullmatch(r'[a-z][a-z-]*(?:\s+[a-z][a-z-]*){0,7}', item)
                        or re.search(r'\b(?:not|only|unless|if|except|but|without|for|from|of|after|before|with|who|that|which|where|no)\b', item)):
                    return None
                head = item.split()[-1]
                if re.fullmatch(r'tests?|investigations?|samples?|specimens?|laborator(?:y|ies)|results?', head):
                    domain = 'investigation'
                elif re.fullmatch(r'procedures?|operations?|surger(?:y|ies)', head):
                    domain = 'procedure'
                else:
                    return None
                # A different domain embedded inside the same nominal is
                # ambiguous (e.g. procedure results), not a safe exclusion.
                if domain == 'investigation' and re.search(r'\b(?:procedures?|operations?|surger(?:y|ies))\b', item):
                    return None
                if domain == 'procedure' and re.search(r'\b(?:tests?|investigations?|samples?|specimens?|results?)\b', item):
                    return None
                domains.add(domain)
    return domains or None


def support_obligation_requested(d, kind, source_text):
    """True=requested, False=explicit different scope, None=keep legacy rule.

    Callers may use True to add the declared obligation to this destination,
    including an exclusions-only destination. False is never an authorization
    to render the source into that destination. Ownership and coverage checks
    still govern every obligation that remains or is added.
    """
    components = _support_components(d)
    if components is None:
        return None
    included = {'time_basis', 'time_total', 'time_included', 'service_date'} <= components
    if kind == 'physician_time_exclusions':
        return 'time_excluded' in components
    if kind in ('physician_time_basis', 'physician_time_activities', 'physician_time_qualification'):
        return included
    if kind == 'investigation_order':
        # The caller supplies a source-owned complete order sentence. This
        # routing decision adds an obligation, never permission to render it.
        # A partly specified investigation destination remains unknown rather
        # than treating its missing requested attributes as a different topic.
        investigation = {'investigation', 'investigation_purpose', 'investigation_timing',
                         'investigation_collection', 'investigation_performance', 'investigation_results'}
        if components & investigation:
            return True if investigation <= components else None
        return False
    if kind in ('nonperformance', 'linked_nonperformance'):
        domains = _nonperformance_domains(source_text)
        if not domains:
            return None
        return bool(domains & components)
    return None


def compound_components(d):
    """Finite affirmative component lists in the approved meaning, never labels.

    A match adds omission checks only. It cannot create a source value, relax
    its scope, or authorize rendering into a different destination.
    """
    if not _narrative(d, subjects=('patient',), polarities=('any', 'positive')):
        return set()
    from documents.semantic_preparation_roles import affirmative_answer_components
    components = affirmative_answer_components(d['meaning'])
    components = {'name:patient' if item == 'name:unspecified' else item for item in components}
    supported = {'name:patient', 'reference', 'blood_pressure', 'pulse', 'temperature',
                 'weight', 'height', 'respiratory_rate', 'oxygen_saturation'}
    return components if len(components) > 1 and components <= supported else set()


def compound_component_inventory(notes, definitions, units, context):
    """Documented current components remain obligations even if unextracted.

    Only complete source-owned header values and explicitly labelled vital
    measurements are recognized here. A genuinely undocumented component
    contributes no value or obligation. Existing fact validation remains the
    authority for qualifiers, units, polarity, timing and ownership.
    """
    from .clinical_source_context import owned_current, PATIENT_IDENTITY_HEADING
    destinations = {key: compound_components(d) for key, d in definitions.items()}
    destinations = {key: values for key, values in destinations.items() if values}
    if not destinations:
        return []
    labels = {'blood_pressure': r'blood\s+pressure', 'pulse': r'pulse|heart\s+rate',
              'temperature': r'(?:body\s+)?temperature', 'weight': r'(?:body\s+)?weight',
              'height': r'height', 'respiratory_rate': r'respiratory\s+rate',
              'oxygen_saturation': r'oxygen\s+saturation'}
    pattern = re.compile(r'\b(?P<label>'+'|'.join('(?:'+p+')' for p in labels.values())
        +r')(?:(?:\s+is)|\s*:)?\s*(?=[+-]?\d)', re.I)
    rows = []

    def add(component, unit, start, end, *, unresolved=False):
        source = {'start': unit['start']+start, 'end': unit['start']+end,
                  'quote': unit['quote'][start:end], 'source_unit_id': unit['id']}
        rows.extend({'field_key': key, 'kind': 'compound_'+component,
                     'component': component, 'source': source, 'polarities': ['affirmed'],
                     'unresolved': unresolved}
                    for key, requested in destinations.items() if component in requested)

    for unit in units:
        if not owned_current(context, unit):
            continue
        text = unit['quote'].rstrip().removesuffix('.')
        name = re.fullmatch(PATIENT_IDENTITY_HEADING, text.strip(), re.I)
        if name and name['name'].casefold() == (context.get('patient_name') or '').casefold():
            offset = len(text)-len(text.lstrip())
            add('name:patient', unit, *(position+offset for position in name.span('name')))
        reference = re.fullmatch(r'\s*(?:(?:clinic|patient|medical)\s+record(?:\s+'
            r'(?:number|reference|identifier))?|record\s+(?:number|reference|identifier)|mrn)'
            r'(?:\s*:\s*|\s+is\s+)(?P<value>.*?)\s*', text, re.I)
        if reference:
            value = reference['value']
            absent = re.fullmatch(r'(?:not\s+(?:documented|recorded|provided|available)|unknown|unavailable)?', value, re.I)
            if not absent:
                known = bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]*', value))
                add('reference', unit, *reference.span('value'), unresolved=not known)
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        prefix_known = bool(re.fullmatch(r'\s*(?:(?:vitals?|measurements)\s*(?::|\s+(?:are|were))\s*)?',
            text[:matches[0].start()], re.I))
        for index, match in enumerate(matches):
            end = matches[index+1].start() if index+1 < len(matches) else len(text)
            # Remove only the list separator before the next labelled value;
            # every unknown trailing qualification stays in this obligation.
            if index+1 < len(matches):
                separator = re.search(r'\s*(?:,\s*(?:and\s+)?|;\s*|\s+and\s+)$', text[match.end():end], re.I)
                if separator is not None:
                    end = match.end()+separator.start()
            while end > match.start() and text[end-1].isspace():
                end -= 1
            component = next(key for key, label in labels.items() if re.fullmatch(label, match['label'], re.I))
            # Unknown lead-ins cannot make a documented requested component
            # disappear. They require clarification; no selected value can
            # bypass that unresolved ownership/qualification boundary. An
            # unknown separator stays verbatim at the end of its component.
            add(component, unit, match.start() if prefix_known else 0,
                end if prefix_known else len(text), unresolved=not prefix_known)
    return rows
