"""Exhaustive descriptive links to independently evaluated source findings.

These relations neither discover diagnoses nor assign codes. A complete report
must have one parse and one evaluated target for every atom before any link is
returned. Callers retain their ordinary source and authoritative route checks.
"""
from copy import deepcopy
import re


CONTRACT = 'source-compound-descriptor-v1'
DIARRHEA_AUTHORITY = 'https://www.niddk.nih.gov/health-information/digestive-diseases/diarrhea/definition-facts'
PAIN_AUTHORITY = 'https://medlineplus.gov/ency/article/003120.htm'
_ONES = ('zero one two three four five six seven eight nine ten eleven twelve '
         'thirteen fourteen fifteen sixteen seventeen eighteen nineteen').split()
_TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
         'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90}
_NUMBER = (r'(?:0|[1-9][0-9]{0,2}|' + '|'.join(_ONES) + r'|(?:'
           + '|'.join(_TENS) + r')(?:[ -](?:' + '|'.join(_ONES[1:10]) + r'))?)')
_QUANTITY = (r'(?:between\s+' + _NUMBER + r'\s+and\s+' + _NUMBER + r'|'
             + _NUMBER + r'(?:(?:\s+to\s+|\s*[-–—]\s*)' + _NUMBER + r')?)')
_FREQUENCIES = {'intermittent', 'recurrent', 'persistent', 'constant', 'ongoing', 'current'}
_SEVERITIES = {'mild', 'moderate', 'severe'}
_PREFIX = r'(?P<prefix>(?:(?:' + '|'.join(sorted(_FREQUENCIES | _SEVERITIES)) + r')\s+)*)'
_DAILY = r'(?:daily|per\s+day|a\s+day|each\s+day|every\s+day)'
_RELIEF = (r'(?P<relief>\s+(?:that|which)\s+(?P<effect>improves|is\s+relieved)'
           r'\s+after\s+(?:a|each)\s+bowel\s+movement)?')
_TAIL = r'(?P<timing>\s+(?:today|currently|now|' + _DAILY + r'))?' + _RELIEF
# Only anatomical regions, not diagnostic modifiers such as acute/postoperative.
# The location must also occur literally in the independent abdominal-pain item.
_LOCATION = re.compile(r'(?:periumbilical|umbilical|epigastric|hypogastric|suprapubic|'
    r'(?:right|left)\s+(?:upper|lower)\s+quadrant|(?:right|left)\s+(?:iliac|lumbar|hypochondriac)'
    r'(?:\s+region)?|(?:right|left)\s+iliac\s+fossa)', re.I)
_SEPARATOR = re.compile(r'(?:\s*,\s*(?:(?:and|with)\s+)?|\s+(?:and|with)\s+)', re.I)


def _literal(value):
    return r'\s+'.join(re.escape(word) for word in value.split())


def _normalized(value):
    """Only case/spacing, never erase numeric or anatomical punctuation."""
    return ' '.join(value.casefold().split())


def _integer(value):
    value = _normalized(value)
    if value.isascii() and value.isdecimal():
        return int(value)
    if value in _ONES:
        return _ONES.index(value)
    parts = re.split('[ -]', value)
    if parts[0] in _TENS and (len(parts) == 1 or len(parts) == 2 and parts[1] in _ONES[1:10]):
        return _TENS[parts[0]] + (_ONES.index(parts[1]) if len(parts) == 2 else 0)
    return None


def _quantity(value):
    single = _integer(value)
    if single is not None:
        return {'minimum': single, 'maximum': single, 'unit': 'stools_per_day'} if single >= 3 else None
    between = re.fullmatch(r'between\s+(' + _NUMBER + r')\s+and\s+(' + _NUMBER + r')', value, re.I)
    ranged = re.fullmatch(r'(' + _NUMBER + r')(?:\s+to\s+|\s*[-–—]\s*)(' + _NUMBER + r')', value, re.I)
    pair = between or ranged
    lower, upper = map(_integer, pair.groups()) if pair else (None, None)
    if lower is None or upper is None or not 3 <= lower <= upper:
        return None
    return {'minimum': lower, 'maximum': upper, 'unit': 'stools_per_day'}


def resolve_report(objects, *, objects_start, report, targets, max_atoms=64):
    """Return a complete source-only proof, or None without partial links.

    targets are inventory items with separate current evaluation evidence. The
    report's ownership/current scope is checked by the inventory caller first.
    """
    if not objects or len(objects) > 8192:
        return None

    def span(start, end):
        return {'start': objects_start + start, 'end': objects_start + end, 'quote': objects[start:end]}

    def attribute(match, name, kind, **values):
        return {'kind': kind, 'span': span(*match.span(name)), **values}

    def matches(position):
        found = []
        for target in targets:
            evaluations = [value for value in target['current_evaluation_evidence'] if value['start'] != report['start']]
            if not evaluations:
                continue
            term = target['condition_text']
            variants = [('exact_nominal', _PREFIX + r'(?P<finding>' + _literal(term) + r')' + _TAIL, None)]
            if _normalized(term) == 'diarrhea':
                variants.append(('daily_loose_stool_description', _PREFIX + r'(?P<quantity>' + _QUANTITY + r')\s+'
                    r'(?P<quality>loose(?:\s+(?:or|and)\s+watery)?|watery(?:\s+(?:or|and)\s+loose)?)\s+'
                    r'(?P<finding>stools)\s+(?P<daily>' + _DAILY + r')' + _RELIEF, DIARRHEA_AUTHORITY))
            located = re.fullmatch(r'(.+)\s+abdominal\s+pain', term, re.I)
            if located and _LOCATION.fullmatch(located[1]):
                variants.append(('same_location_abdominal_cramping', _PREFIX + r'(?P<location>'
                    + _literal(located[1]) + r')\s+(?P<finding>cramping)' + _TAIL, PAIN_AUTHORITY))
            for relation, grammar, authority in variants:
                match = re.compile(grammar, re.I).match(objects, position)
                if not match or match.end() < len(objects) and not _SEPARATOR.match(objects, match.end()):
                    continue
                attributes, seen = [], set()
                prefixes = [(match['prefix'], match.start('prefix'))]
                if relation == 'exact_nominal':
                    # The literal evaluated target can itself begin with an
                    # ordinary modifier. It shares the same conflict budget as
                    # an extra report prefix, including duplicate kinds inside
                    # the target. Keep the actual report offsets and spelling.
                    embedded = re.match(_PREFIX, match['finding'], re.I)['prefix']
                    prefixes.append((embedded, match.start('finding')))
                modifiers = [(modifier, offset) for prefix, offset in prefixes
                             for modifier in re.finditer(r'\S+', prefix)]
                for modifier, offset in modifiers:
                    value = modifier.group().casefold()
                    kind = 'frequency' if value in _FREQUENCIES else 'severity'
                    if kind in seen:
                        break
                    seen.add(kind)
                    attributes.append({'kind': kind, 'value': value, 'span': span(offset + modifier.start(), offset + modifier.end())})
                else:
                    groups = match.groupdict()
                    attributes.append(attribute(match, 'finding', 'literal_finding', value=match['finding']))
                    if groups.get('quantity'):
                        quantity = _quantity(match['quantity'])
                        if quantity is None:
                            continue
                        attributes.extend([attribute(match, 'quantity', 'quantity', **quantity),
                            attribute(match, 'quality', 'stool_consistency', values=re.findall(r'loose|watery', match['quality'], re.I)),
                            attribute(match, 'daily', 'frequency', value='daily')])
                    if groups.get('location'):
                        attributes.append(attribute(match, 'location', 'literal_anatomical_location', value=match['location']))
                    if groups.get('timing'):
                        attributes.append(attribute(match, 'timing', 'current_timing_or_frequency', value=match['timing'].strip()))
                    if groups.get('relief'):
                        attributes.append(attribute(match, 'relief', 'symptom_modification',
                            effect=_normalized(match['effect']), trigger='after_bowel_movement', infers_etiology=False))
                    found.append({'span': span(position, match.end()), 'attributes': attributes,
                        'target_id': target['id'], 'target_text': term,
                        'relation': {'kind': relation, 'authority': authority, 'independent_evaluation': deepcopy(evaluations)}})
        return found

    atoms, separators, position = [], [], 0
    while position < len(objects) and len(atoms) < max_atoms:
        choices = matches(position)
        if len(choices) != 1:
            return None
        atom = choices[0]
        atoms.append(atom)
        position = atom['span']['end'] - objects_start
        if position == len(objects):
            return {'contract': CONTRACT, 'report': deepcopy(report),
                'objects': span(0, len(objects)), 'atoms': atoms, 'separators': separators,
                'exhaustive': True, 'establishes_diagnosis_or_code': False}
        separator = _SEPARATOR.match(objects, position)
        if not separator or separator.end() == len(objects):
            return None
        separators.append(span(position, separator.end()))
        position = separator.end()
    return None
