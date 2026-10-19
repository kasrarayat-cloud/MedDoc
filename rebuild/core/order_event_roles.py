"""Literal roles in a complete order with an explicitly future test event.

Recognition supplies no fact, owner, encounter, destination or performed-service
permission. Callers must retain the whole value and independently enforce those
gates. The extractor's current/future timing annotation is never rewritten.
"""
import re

from .clinical_assertions_v4 import _nominal, family_history_order_frame
from .soap_clinical_literals import _bounded_nominal


_EXTRA_SCOPE = re.compile(
    r'\b(?:for|from|to|in|on|at|per|according|regarding|concerning|about|as|with|'
    r'under|during|via|of|unknown|pending|awaiting|unconfirmed|recalled|disputed|'
    r'disregard|ignore|following|above|below|listed|historical|previously|later)\b', re.I)
# These words govern whether/when an order exists, rather than naming its test
# or indication. This local restriction cannot change the historical v4 reader.
_EVENT_GOVERNOR = re.compile(
    r'\b(?:assume|assumes|assumed|assuming|assumption|pretend|pretends|pretended|pretending|'
    r'suppose|supposes|supposed|supposing|supposition|imagine|imagines|imagined|imagining|imaginary|'
    r'fictitious|fictional|hypothetical|counterfactual|simulated|simulation|'
    r'last|ago|former|formerly|old|past|future|next|once|historically|'
    r'cancelled|canceled)\b', re.I)
_PASSIVE = re.compile(
    r'(?P<placement>(?P<test>(?:a|an|the)\s+.+?)\s+is\s+ordered)\s+for\s+'
    r'(?P<event>(?:collection|performance)\s+at\s+a\s+laboratory\s+after\s+this\s+visit)'
    r'\s+as\s+part\s+of\s+the\s+(?P<indication>.+?)\s+evaluation', re.I)
_ACTIVE = re.compile(
    r'(?P<placement>I\s+(?:have\s+)?ordered\s+(?P<test>.+?))\s+to\s+evaluate\s+'
    r'(?:for\s+)?(?P<indication>.+?),\s*with\s+'
    r'(?P<event>(?:collection|performance)\s+planned\s+(?:tomorrow|after\s+this\s+visit))', re.I)


def _object(text):
    return (_bounded_nominal(text, _nominal) and not _EXTRA_SCOPE.search(text)
            and not _EVENT_GOVERNOR.search(text))


def order_event_frame(text):
    """Return exact whole-value and event-role spans, or no permission.

    ``order_placement`` includes the test and asserted ordering predicate;
    ``future_event`` includes its explicit future collection/performance phrase.
    These are role metadata, never independently selectable clinical values.
    Surrounding section, ownership and qualification remain caller obligations.
    """
    if type(text) is not str:
        return None
    value = text.strip().removesuffix('.').strip()
    if not value or any(char in value for char in '\r\n'):
        return None
    offset = text.index(value)
    family = family_history_order_frame(text)
    if family is not None:
        # Delegate the full old grammar, without changing its module or result.
        # Only this new wrapper admits either intact annotation for two events.
        if not all(_object(text[start:end]) for start, end in (family['test'], family['indication'])):
            return None
        placement = re.match(r'(?:I\s+(?:have\s+)?ordered\s+.+?|(?:a|an|the)\s+.+?\s+is\s+ordered)'
            r'(?=\s+for\s+family\s+history\s+of\s+)', value, re.I)
        if placement is None:
            return None
        result = {key: item for key, item in family.items() if key != 'required_timing'}
        result['roles'] = {'order_placement': (offset, offset + placement.end()),
                           'future_event': family['collection']}
    else:
        match = _PASSIVE.fullmatch(value) or _ACTIVE.fullmatch(value)
        if match is None or not all(_object(match[key]) for key in ('test', 'indication')):
            return None
        span = lambda key: (offset + match.start(key), offset + match.end(key))
        result = {'kind': 'investigation_order', 'values': [(offset, offset + len(value))],
                  'test': span('test'), 'indication': span('indication'),
                  'roles': {'order_placement': span('placement'), 'future_event': span('event')},
                  'required_subject': 'patient', 'required_polarity': 'affirmed',
                  'required_section': 'plan'}
    result['allowed_timings'] = ('current', 'future')
    return result
