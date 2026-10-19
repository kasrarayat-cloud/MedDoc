"""V22 complete narrative capabilities and source-first relation obligations.

Only exhaustive affirmative meanings gain capabilities. Recognized instructions
about documentation preserve scope; unknown prose cannot supply permission.
Nothing here edits a definition, fact, answer, time annotation or source span.
"""
import re

from . import soap_destination_contracts as prior


_PRESERVATION = (
    r'do not add (?:negatives|findings) that are not documented',
    r'do not add undocumented (?:findings|negatives)',
    r'leave undocumented components blank',
    r'include only documented items',
    r'include only documented activities and times',
    r'keep intended and actual status distinct; do not state a result unless documented',
    r'preserve documented uncertainty and negation; do not infer undocumented details',
)


def _body(d):
    """Consume a finite preservation suffix, never an arbitrary prohibition."""
    clauses = re.split(r'\.\s+', prior._text(d['meaning']))
    if any(not any(re.fullmatch(pattern, clause) for pattern in _PRESERVATION)
           for clause in clauses[1:]):
        return None
    return clauses[0]


def _definition(d, meaning):
    return {**d, 'meaning': meaning}


def complete_denial_destination(d):
    if prior.complete_denial_destination(d):
        return True
    body = _body(d)
    if body is None:
        return False
    body = re.sub(r'^narrative (?:listing |description )?of ', '', body)
    # These phrases describe the same explicit absence and scope requirement.
    body = re.sub(r'\(symptoms the patient is documented as not having\)',
                  '(symptoms documented as absent)', body)
    body = re.sub(r' scope such as timing or context$', ' scope', body)
    return prior.complete_denial_destination(_definition(d, body))


def complete_exam_destination(d):
    if prior.complete_exam_destination(d):
        return True
    body = _body(d)
    if body is None:
        return False
    body = re.sub(r'^narrative (?:description )?of ', '', body)
    body = re.sub(r' with their documented scope$', '', body)
    return prior.complete_exam_destination(_definition(d, body))


def restricted_exam_destination(d):
    if complete_exam_destination(d):
        return False
    return (prior.restricted_exam_destination(d)
        or bool(re.match(r'(?:concise )?narrative\b', prior._text(d['meaning']))
                and re.search(r'\b(?:exam(?:ination)?|objective)\b', d['meaning'], re.I)))


def historical_medicine_with_current_nonuse(d):
    if prior.historical_medicine_with_current_nonuse(d):
        return True
    body = _body(d)
    if body is None:
        return False
    body = re.sub(r'^narrative (?:description )?of ', '', body)
    body = re.sub(r'explicit documentation that it is not being used now',
                  'explicit statement of non-use now', body)
    return prior.historical_medicine_with_current_nonuse(_definition(d, body))


def _support_definition(d):
    body = _body(d)
    if body is None:
        return None
    body = re.sub(r'^(?:concise )?narrative (?:description )?of ', '', body)
    body = re.sub(r'^(?:the )?investigation ordered:\s*', 'investigation ordered, ', body)
    body = re.sub(r'the actual status today of collection, performance and result$',
                  'actual collection, performance and result status today', body)
    body = re.sub(r'^documented exclusions from counted time:\s*', '', body)
    body = re.sub(r'(?:any )?separately reported service that is excluded',
                  'separately reported service exclusion', body)
    parsed = _definition(d, body)
    if d.get('scope', {}).get('polarity') == 'positive':
        positive = {**parsed, 'scope': {**d['scope'], 'polarity': 'any'}}
        components = prior._support_components(positive)
        if components == {'time_basis', 'time_total', 'time_included', 'service_date'}:
            return positive  # Routing only; original positive fact scope is still enforced.
    return parsed


def support_obligation_requested(d, kind, source_text):
    parsed = _support_definition(d)
    if parsed is None:
        return None
    return prior.support_obligation_requested(parsed, kind, source_text)


def restricted_support_destination(d):
    parsed = _support_definition(d)
    if parsed is not None and prior._support_components(parsed) is not None:
        return False
    return (prior.restricted_support_destination(d)
        or bool(re.match(r'(?:concise )?narrative\b', prior._text(d['meaning']))
                and re.search(r'\b(?:time|tests?|investigations?|procedures?)\b', d['meaning'], re.I)))


def _history_topic(d, nominal):
    if not prior._narrative(d, subjects=('patient',), polarities=('any', 'positive')):
        return None
    body = _body(d)
    if body is None:
        return None
    match = re.fullmatch(r"narrative (?:description )?of (?:the patient['’]s )?"
        r'(?:documented )?(?P<topic>.+?) history:\s*(?P<attributes>.+)', body)
    if not match or not nominal(match['topic']):
        return None
    # Attribute lists authorize only a completeness obligation. They cannot
    # make a fact valid or add a different source topic to a destination.
    attribute = (r'duration|onset|severity|location|timing|frequency|sensation and location|'
        r'episode length|timing relative to meals|aggravating and relieving factors|'
        r'(?:previous|current|previous and current) (?:bowel |symptom )?frequency|'
        r'stool features|straining|passage of gas|associated symptoms|'
        r'aggravating factors|relieving factors|course|response')
    item = '(?:' + attribute + ')'
    if not re.fullmatch(item + r'(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+)' + item + r')*', match['attributes']):
        return None
    return match['topic']


def _unresolved_history_candidate(d, unit, candidate, markers, nominal):
    """Literal candidate discovery cannot depend on the permission grammar.

    Unknown wording supplies no capability. Matching mentions in a patient
    narrative history meaning retain a whole unresolved source obligation.
    Definition offsets and source offsets belong to different texts.
    """
    meaning = d['meaning']
    history = re.search(r'\bhistory\b', meaning, re.I)
    if (not prior._narrative(d, subjects=('patient',), polarities=('any', 'positive'))
            or not history or not markers):
        return None
    # Candidate identity comes from the first history header, independently of
    # its permission grammar. Instruction tails cannot add another topic.
    header_start = max(meaning.rfind(char, 0, history.start()) for char in '.\r\n:') + 1
    ends = [meaning.find(char, history.end()) for char in '.\r\n:']
    header_end = min([end for end in ends if end >= 0], default=len(meaning))
    header = meaning[header_start:header_end]
    if re.match(r"\s*(?:do not|don't|don’t|omit|exclude)\b", header, re.I):
        return None
    complete = (candidate and nominal(candidate['first']) and nominal(candidate['second'])
        and candidate['predicate'].casefold() in ('is', 'remains'))
    if complete:
        # A known complete relation concerns its first topic. An unrelated
        # second-topic history cannot acquire an obligation through fallback.
        terms = [candidate['first']]
    else:
        words = list(re.finditer(r'[A-Za-z][A-Za-z-]*', header))
        terms = set()
        for start in range(len(words)):
            for end in range(start, min(start + 6, len(words))):
                term = header[words[start].start():words[end].end()]
                if nominal(term):
                    terms.add(term)
    source_mentions, definition_mentions, occupied = [], [], []
    for term in sorted(terms, key=lambda value: (-len(value), value.casefold(), value)):
        pattern = r'(?<![\w-])' + re.escape(term) + r'(?![\w-])'
        definitions = list(re.finditer(pattern, header, re.I))
        if not definitions:
            continue
        for match in re.finditer(pattern, unit['quote'], re.I):
            if (any(match.start() < mark.end() and mark.start() < match.end() for mark in markers)
                    or any(match.start() < end and start < match.end() for start, end in occupied)):
                continue
            occupied.append(match.span())
            source_mentions.append({'start': unit['start'] + match.start(),
                'end': unit['start'] + match.end(), 'quote': match[0]})
            for mention in definitions:
                span = {'start': header_start + mention.start(), 'end': header_start + mention.end(), 'quote': mention[0]}
                if span not in definition_mentions:
                    definition_mentions.append(span)
    if not source_mentions:
        return None
    return {'kind': 'separate_concern', 'source': {k: unit[k] for k in ('start', 'end', 'quote')},
        'topic_mentions': source_mentions, 'definition_mentions': definition_mentions,
        'definition_history_header': {'start': header_start, 'end': header_end, 'quote': header},
        'definition_meaning': {'start': 0, 'end': len(meaning), 'quote': meaning},
        'relation_markers': [{'start': unit['start'] + m.start(), 'end': unit['start'] + m.end(),
            'quote': m[0]} for m in markers], 'definition_unresolved': True,
        'unresolved': True, 'polarities': ['affirmed']}


def separation_inventory(notes, definitions, units, context, nominal):
    """Retain owned present separation claims even when extraction omits them.

    Topics and evidence remain literal. A qualified/unknown separation claim
    is an unresolved obligation, never permission to infer a relation.
    """
    from .clinical_source_context import owned_current, source_clinician_bound
    topics = {key: topic for key, d in definitions.items()
              if (topic := _history_topic(d, nominal)) is not None}
    rows = []
    for unit in units:
        if not owned_current(context, unit) or not source_clinician_bound(context, unit['quote']):
            continue
        text = unit['quote'].strip().removesuffix('.')
        candidate = re.fullmatch(r'(?:the\s+)?(?P<first>.+?)\s+'
            r'(?P<predicate>(?:is|remains|may be|might be|is not))\s+'
            r'a separate (?:concern|problem) from (?:the\s+)?(?P<second>.+)', text, re.I)
        offset = unit['start'] + unit['quote'].index(text)
        span = lambda name: {'start': offset + candidate.start(name),
            'end': offset + candidate.end(name), 'quote': candidate[name]}
        markers = list(re.finditer(r'\bseparate\s+(?:concern|problem)\s+from\b', unit['quote'], re.I))
        for key, topic in topics.items():
            if candidate and nominal(candidate['first']) and topic.casefold() == candidate['first'].casefold():
                complete = (nominal(candidate['second'])
                    and candidate['predicate'].casefold() in ('is', 'remains'))
                rows.append({'field_key': key, 'kind': 'separate_concern',
                    'source': {'start': offset, 'end': offset + len(text), 'quote': text},
                    'first': span('first'), 'second': span('second'),
                    'predicate': span('predicate'), 'unresolved': not complete,
                    'polarities': ['affirmed']})
                continue
            if (candidate and nominal(candidate['first']) and nominal(candidate['second'])
                    and candidate['predicate'].casefold() in ('is', 'remains')):
                continue  # A fully parsed relation keeps its existing first-topic destination.
            # Detection must not share the permission parser's blind spots.
            # A modifier/preamble cannot erase a relevant source obligation.
            # These are literal mentions, not parsed participants or a claim
            # that the relationship is affirmative, current or clinically true.
            mentions = list(re.finditer(r'(?<![\w-])' + re.escape(topic) + r'(?![\w-])', unit['quote'], re.I))
            if not markers or not mentions:
                continue
            evidence = lambda match: {'start': unit['start'] + match.start(),
                'end': unit['start'] + match.end(), 'quote': match[0]}
            rows.append({'field_key': key, 'kind': 'separate_concern',
                'source': {k: unit[k] for k in ('start', 'end', 'quote')},
                'topic_mentions': [evidence(match) for match in mentions],
                'relation_markers': [evidence(match) for match in markers],
                'unresolved': True, 'polarities': ['affirmed']})
        for key, definition in definitions.items():
            if key in topics:
                continue
            obligation = _unresolved_history_candidate(definition, unit, candidate, markers, nominal)
            if obligation is not None:
                rows.append({'field_key': key, **obligation})
    return rows
