"""Prospective complete assertion frames, with exact source-relative spans.

These syntactic relations retain the original assertion and all of its objects.
They do not supply a diagnosis, medication identity, date, or billing decision.
The caller separately checks patient, encounter, section and antecedent scope.
"""
from datetime import datetime
import re


PROFILE = 'source-complete-assertions-v3'
_MONTH = (r'January|February|March|April|May|June|July|August|September|October|November|December')
_DATE = r'(?:\d{1,2}\s+(?:' + _MONTH + r')\s+\d{4}|(?:' + _MONTH + r')\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})'
_COUNT = r'(?:[1-9][0-9]{0,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)'
_SUBJECT = r'(?:he|she|they|the\s+patient)'
_QUALIFIER = re.compile(r'\b(?:not|never|unless|except|without|only|reported|unverified|uncertain|possibly|maybe|'
    r'hypothetical|suppose|imagine|previous|prior|yesterday|tomorrow|mother|father|family|another|other\s+patient)\b', re.I)


def calendar_mask(text):
    """Mask only valid complete calendar dates in a lexical modality reading."""
    visible = list(text)
    for match in re.finditer(r'(?<![\w/-])' + _DATE + r'(?![\w/-])', text, re.I):
        for fmt in ('%d %B %Y', '%B %d, %Y', '%Y-%m-%d'):
            try:
                datetime.strptime(match[0], fmt)
            except ValueError:
                continue
            visible[match.start():match.end()] = ' ' * len(match[0])
            break
    return ''.join(visible)


def follow_up_frame(text):
    """An entire scheduled instruction; its conditional safety net stays literal."""
    value = text.strip().removesuffix('.').strip()
    noun = r'(?:[A-Za-z-]+(?:al|ic|ous|ive|ed|en)\s+){0,2}[A-Za-z][A-Za-z-]*'
    objects = noun + r'(?:\s+and\s+' + noun + r')?'
    match = re.fullmatch(r'(?:follow-up|followup|review)\s+is\s+planned\s+'
        r'(?P<interval>in\s+' + _COUNT + r'\s+(?:days?|weeks?|months?))\s+'
        r'to\s+(?:discuss|review)\s+(?P<objects>' + objects + r'),\s*'
        r'with\s+earlier\s+contact\s+if\s+(?P<condition>' + noun + r')\s+'
        r'(?:worsen|worsens|persist|persists|recur|recurs|continue|continues)', value, re.I)
    if not match or _QUALIFIER.search(value):
        return None
    # A noun object cannot absorb a second finite predicate or attribution.
    if re.search(r'\b(?:he|she|they|it|is|are|was|were|has|have|may|might|could|would|if)\b',
            match['objects'] + ' ' + match['condition'], re.I):
        return None
    offset = text.index(value)
    return {'kind': 'conditional_follow_up', 'values': [(offset, offset + len(value)),
        (offset + match.start('interval'), offset + match.end('interval'))]}


def named_medication_trial(text, number_pattern):
    """A complete named trial, never a prefix of a qualified/retracted account."""
    partial_date = r'\d{1,2}\s+(?:' + _MONTH + r')(?:\s+\d{4})?'
    name = r'[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z][A-Za-z0-9-]*){0,3}'
    regimen = (number_pattern + r'\s+(?:tablets?|capsules?)\s+'
        r'(?:(?:chewed|swallowed|by\s+mouth|orally)\s+)?'
        r'(?:daily|nightly|each\s+(?:morning|evening)|as\s+needed)'
        r'(?:\s+for\s+(?:the\s+)?[A-Za-z-]+(?:\s+[A-Za-z-]+){0,5})?')
    match = re.fullmatch(_SUBJECT + r'\s+previously\s+(?:tried|took|used)\s+'
        r'(?P<medicine>' + name + r')\s+' + number_pattern + r'\s+(?:mg|g|mcg|mL)'
        r'(?:,\s*' + regimen + r')?(?:,?\s+from\s+(?P<first>' + partial_date + r')'
        r'\s+through\s+(?P<last>' + partial_date + r'))?\.?', text.strip(), re.I)
    if not match or _QUALIFIER.search(match['medicine']):
        return None
    for group in ('first', 'last'):
        value = match[group]
        if value:
            try:
                datetime.strptime(value if re.search(r'\d{4}$',value) else value+' 2000', '%d %B %Y')
            except ValueError:
                return None
    # Regimen objects are nominal indications, not hidden additional predicates.
    if re.search(r'\b(?:but|although|however|withdrawn|retracted|uncertain|unverified|another|other|'
                 r'actually|report|reported|is|are|was|were|not|never)\b', text, re.I):
        return None
    return match['medicine']


def assertion_frame(text, nominal):
    """Return only complete bounded syntax; unknown suffixes never disappear."""
    value = text.strip().removesuffix('.').strip()
    offset = text.index(value) if value else 0
    def frame(kind, spans=None, **metadata):
        return {'kind': kind, 'values': [(offset + a, offset + b) for a,b in
            (spans or [(0, len(value))])], **metadata}
    follow = follow_up_frame(text)
    if follow:
        return follow
    history = re.fullmatch(_SUBJECT + r'\s+reports?\s+(?P<objects>no\s+.+)', value, re.I)
    if history:
        parts = re.split(r',\s*(?:and\s+)?(?=no\b)|\s+and\s+(?=no\b)', history['objects'], flags=re.I)
        spans = []
        cursor = history.start('objects')
        for part in parts:
            match = re.fullmatch(r'no\s+(?:(?:previous|prior)\s+(?:(?:diagnosis|history)\s+of\s+)?'
                r'|(?:known\s+)?history\s+of\s+)(?P<object>.+)', part, re.I)
            def history_object(item):
                if nominal(item):
                    return True
                category = re.fullmatch(r'(?P<name>.+)\s+(?:disease|syndrome|disorder|condition)', item, re.I)
                return bool(category and nominal(category['name']))
            if not match or not all(history_object(item) for item in re.split(r'\s+(?:and|or)\s+|,\s*', match['object'], flags=re.I)):
                return None
            start = value.index(part, cursor); cursor = start + len(part)
            spans.append((start, cursor))
        return frame('documented_absence', [(0, len(value)), *spans],
            parts=[(offset + a, offset + b) for a,b in spans])
    if re.fullmatch(r'(?:their|its|the)\s+cause\s+has\s+not\s+been\s+(?:established|determined)', value, re.I):
        return frame('diagnostic_limit', antecedent='assessed_findings')
    possible = re.fullmatch(r'(?P<objects>.+?)\s+are\s+possible\s+(?:explanations|causes|diagnoses);\s*'
        r'(?P<quantifier>neither|none)\s+(?:is|are)\s+(?:a\s+)?(?:confirmed|established)\s+diagnos(?:is|es)', value, re.I)
    if possible:
        objects = re.split(r'\s*,\s*|\s+and\s+', possible['objects'], flags=re.I)
        if len(objects) >= 2 and (possible['quantifier'].casefold() != 'neither' or len(objects) == 2) and all(nominal(item) for item in objects):
            return frame('uncertainty')
    stopped = re.fullmatch(_SUBJECT + r'\s+(?:stopped|ceased|discontinued)\s+(?:it|(?P<prior>.+?))\s+'
        r'on\s+(?P<date>\d{1,2}\s+(?:' + _MONTH + r')(?:\s+\d{4})?)\s+'
        r'because\s+it\s+was\s+not\s+helping\s+and\s+'
        r'(?P<current>(?:is|are)\s+no\s+longer\s+(?:taking|using)\s+(?P<medicine>.+))', value, re.I)
    if (stopped and re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z][A-Za-z0-9-]*){0,3}', stopped['medicine'])
            and not re.search(r'\b(?:and|or|for|with|without|if|unless|except|because|when|until|since|before|after|'
                r'not|never|sometimes|occasionally|tomorrow|yesterday)\b', stopped['medicine'], re.I)
            and (stopped['prior'] is None or stopped['prior'].casefold() == stopped['medicine'].casefold())):
        date = stopped['date']
        try:
            datetime.strptime(date if re.search(r'\d{4}$', date) else date + ' 2000', '%d %B %Y')
        except ValueError:
            return None
        return frame('medication_absence', [(stopped.start('current'), stopped.end('current'))],
            medicine=stopped['medicine'], antecedent='named_medication_trial')
    return None
