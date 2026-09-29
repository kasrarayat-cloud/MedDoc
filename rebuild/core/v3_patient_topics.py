"""Literal source-actor relations. These establish no clinical write destination.

Every unit in this small source grammar must be accounted for. An unknown
subject, clause or relationship invalidates the additional relation; normal
source governance then applies. Original quotations and offsets are untouched.
"""
import re


WORD = r'[A-Za-z]+(?:-[A-Za-z]+)*'
NOMINAL = re.compile(WORD + r'(?: ' + WORD + r'){0,7}')
NUMBER = r'(?:[0-9]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)'
DURATION = NUMBER + r' (?:days?|weeks?|months?|years?)'
RELATION = re.compile(r"\b(?:he|she|they|his|her|their|him|them|who|whose|that|for|of|by|from|with|and|or|as|"
                      r"at|on|in|to|about|regarding|concerning|under|over|per)\b|['’]", re.I)
TAKES = re.compile(r'(?P<actor>He|She) takes (?P<object>[A-Za-z0-9 /-]+?)(?P<as_needed> as needed)?\.')
DENIES = re.compile(r'(?P<actor>He|She) denies (?P<object>[A-Za-z ,\-]+)\.')
NONSMOKER = re.compile(r'(?P<actor>He|She) is a nonsmoker\.')
FOLLOWUP = re.compile(r'(?P<actor>He|She) will follow up in ' + DURATION + r'\.')
PLAN = re.compile(r'(?:Plan|Treatment plan|Management plan) is (?P<to>to) (?:start|increase) '
                  r'(?P<object>[A-Za-z0-9 /-]+?)(?: at (?:night|bedtime))?\.')
TOPIC_END = re.compile(r'\b(?:with|for) (?P<topic>' + WORD + r'(?: ' + WORD + r'){0,7})\.$')
NAMED = frozenset(('allergies', 'examination', 'assessment', 'medications', 'plan', 'treatment plan', 'management plan'))


def patient_relations(units, patients, subjects, parsed, *, finite, denial, acceptable, shape_holds):
    """Return a complete actor chain plus exact local qualifier spans, or no grant.

`acceptable` and `shape_holds` reuse the application's existing withholding
rules. This grammar never supplies a field, rewrites a value, or interprets a
medicine. The original patient-history block must still be selected completely.
"""
    empty = {'units': {}, 'qualifiers': {}, 'boundaries': set(), 'separators': set(), 'topic': frozenset()}
    if not units or not patients.get(units[0]['id']):
        return empty
    anchor = units[0]
    match = TOPIC_END.search(anchor['quote'])
    if not match:
        return empty
    topic = match.group('topic')
    if RELATION.search(topic) or finite.search(topic) or not acceptable(topic, ()):
        return empty
    repeated = re.compile(r'The ' + re.escape(topic) + r' started (?P<time>' + DURATION + r' (?P<ago>ago))'
                          r'(?: and (?:is|are) ' + WORD + r' in the (?:morning|afternoon|evening|night))?\.', re.I)
    tokens = {word.casefold().removesuffix('s') for word in topic.split()}
    ledger, qualifiers, boundaries, separators = {}, {}, set(), set()
    pronoun, prior_relation = None, None
    for index, unit in enumerate(units):
        text = unit['quote']
        # No compatibility conversion can establish ownership. Unsupported
        # punctuation, hidden source and sentence-splitting ambiguity stay held.
        if not text.isascii() or shape_holds(unit):
            return empty
        spans, actor, relation = [], None, None
        if index == 0:
            relation = 'explicit_patient'
        elif (match := repeated.fullmatch(text)):
            relation = 'literal_patient_topic'
            spans = [(match.start('ago'), match.end('ago'))]
        elif (match := TAKES.fullmatch(text)):
            value = match.group('object')
            if RELATION.search(value) or finite.search(value) or denial.search(value):
                return empty
            relation, actor = 'patient_statement', match.group('actor')
        elif (match := DENIES.fullmatch(text)):
            value = match.group('object')
            # A final nominal-list "or" stays inside this complete denial. A
            # clause, second predicate or denial of the anchor's literal topic
            # retains context rather than becoming a harmless topic boundary.
            items = value.split(', ')
            if len(items) < 2 or not items[-1].startswith('or '):
                return empty
            items[-1] = items[-1][3:]
            if any(not NOMINAL.fullmatch(item) or RELATION.search(item) or finite.search(item)
                   or denial.search(item) for item in items):
                return empty
            if tokens & {word.casefold().removesuffix('s') for item in items for word in item.split()}:
                return empty
            start = match.start('object') + value.rfind('or ')
            spans = [(start, start + 2)]
            relation, actor = 'complete_patient_denial', match.group('actor')
        elif (match := NONSMOKER.fullmatch(text)):
            relation, actor = 'complete_patient_state', match.group('actor')
            start = text.index('nonsmoker')
            spans = [(start, start + len('nonsmoker'))]
            # Separate the source from a preceding allergy declaration. This
            # does not turn its wording into a printed Smoker option.
            boundaries.add(unit['id']); separators.add(unit['id'])
        elif (match := PLAN.fullmatch(text)) and subjects.get(unit['id']) in NAMED:
            value = match.group('object')
            if RELATION.search(value) or finite.search(value) or denial.search(value):
                return empty
            spans = [(match.start('to'), match.end('to'))]
            relation = 'complete_named_plan'
        elif (match := FOLLOWUP.fullmatch(text)) and prior_relation == 'complete_named_plan':
            relation, actor = 'same_patient_plan_followup', match.group('actor')
        elif subjects.get(unit['id']) in NAMED:
            own = parsed.get(unit['id'])
            value = own[1] if own else text
            # An arbitrary field heading is not a patient reset. Relations in
            # its value can introduce another source subject and stop this chain.
            if RELATION.search(value):
                return empty
            relation = 'existing_named_source'
        else:
            return empty
        if actor:
            if pronoun is not None and actor != pronoun:
                return empty
            pronoun = actor
        if index and not acceptable(text, spans):
            return empty
        qualifiers[unit['id']] = [(unit['start'] + low, unit['start'] + high) for low, high in spans]
        ledger[unit['id']] = {'anchor': anchor['id'], 'relation': relation,
                              'start': unit['start'], 'end': unit['end']}
        prior_relation = relation
    # 'topic': the anchor's literal topic words (casefolded, one closing s removed), so a reader can tell a ledger
    # unit restating that topic ('The headaches started ...') from one naming something else.
    return {'units': ledger, 'qualifiers': qualifiers, 'boundaries': boundaries, 'separators': separators,
            'topic': frozenset(tokens)}
