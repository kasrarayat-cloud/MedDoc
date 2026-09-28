"""Literal source/destination scope guards; these never establish clinical meaning."""
import re
import unicodedata


_SIDE = re.compile(r'\b(?:left(?!\s+(?:blank|empty|unchanged|before|after|the\s+(?:clinic|room|hospital))\b)'
                   r'|right(?!\s+(?:for|after|before|away|now|here|there|to(?!\s+left\b))\b)|lt|rt|bilateral|bil)\b'
                   r'|\(([LR])\)', re.I)


def sides(text):
    """Only the explicit side vocabulary already recognized on printed forms.

    The same compatibility-normalized reading is used for source and destination.
    A recognized token can withhold an answer; it never grants anatomical identity.
    """
    found = set()
    for match in _SIDE.finditer(unicodedata.normalize('NFKC', str(text or ''))):
        token = (match[1] or match[0]).casefold()
        found.update({'left', 'right'} if token in ('bilateral', 'bil') else
                     {'left' if token in ('left', 'lt', 'l') else 'right'})
    return found


def side_warnings(field, selected):
    """Keep unknown/mixed/opposite source scope held for a side-specific field.

    Full original context matters even when the short label is only 'Findings'.
    No source sentence is shortened to rescue an answer containing another side.
    """
    required = sides(str(field.get('context') or '') + ' ' + str(field.get('label') or ''))
    if not required:
        return []
    return [unit for unit in selected if len(required) != 1 or sides(unit['quote']) != required]


_PATIENT_REPORT = re.compile(r'^(?:the\s+)?patient\s+(?:reports?|reported|says?|said|states?|stated|writes?|wrote)\b', re.I)
_DOCUMENT = r'(?:(?:the|this|that|their|his|her)\s+)?(?:(?:entire|complete)\s+)?(?P<object>report|form|document|application)'
_REVIEW_ACTION = r'(?:(?:has|had)\s+)?(?:read|reviewed|seen|had\s+sight\s+of)'
_COMMENT_ACTION = r'(?:(?:has|had)\s+)?(?:had|was\s+given)\s+(?:an?\s+)?opportunity\s+to\s+(?:add\s+(?:(?:their|his|her|my)\s+)?)?comments?'
_REVIEW_CLAUSE = re.compile(_REVIEW_ACTION + r'\s+' + _DOCUMENT, re.I)
_COMMENT_CLAUSE = re.compile(_COMMENT_ACTION + r'(?:\s+(?:on|about)\s+' + _DOCUMENT + r')?', re.I)
_QUALIFIED_REVIEW = re.compile(r'\b(?:not|never|no|denies?|uncertain|unsure|possibly|maybe|might|may|could|would|will|if|unless|but)\b|\?', re.I)


def review_requirements(source):
    """Read the printed object's identity and its literal AND/OR requirement.

    The anchored question, never the editable display label, sets the obligation.
    Unrecognized clauses stay held instead of falling back to a generic OR.
    """
    text = re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', source)).strip().rstrip('.?')
    text = re.sub(r'^please\s+', '', text, flags=re.I)
    prefix = re.match(r'confirm\s+(?:that\s+)?(?:the\s+)?patient\s+', text, re.I)
    if not prefix: return None
    body = text[prefix.end():]
    body = re.sub(r',\s*if appropriate or necessary$', '', body, flags=re.I)
    pieces = re.split(r'\s+(and/or|and|or)\s+', body, flags=re.I)
    if len(pieces) not in (1, 3): return None
    claims = []; objects = set()
    for part in pieces[::2]:
        match = _REVIEW_CLAUSE.fullmatch(part)
        kind = 'review'
        if match is None: match = _COMMENT_CLAUSE.fullmatch(part); kind = 'opportunity'
        if match is None: return None
        claims.append(kind)
        if match['object']: objects.add(match['object'].casefold())
    if len(objects) != 1 or len(set(claims)) != len(claims): return None
    return objects.pop(), set(claims), len(pieces) == 3 and pieces[1].casefold() == 'and'


def review_claims(text, required_object):
    """Only complete assertions by the same explicit patient establish events.

    A second coordinated comment clause can inherit the first clause's document.
    No title, summary, partial object, future or negative qualifier is discarded.
    """
    if _QUALIFIED_REVIEW.search(text) or not text.endswith('.'): return None
    prefix = re.match(r'^(?:the\s+)?patient\s+', text, re.I)
    if not prefix: return None
    body = text[prefix.end():-1]
    reported = re.match(r'(?:reports?|reported|states?|stated|says?|said)\s+'
        r'(?:having|that\s+(?:(?:he|she|they)\s+(?:has|have|had)|I\s+(?:have|had)))\s+', body, re.I)
    if reported: body = body[reported.end():]
    pieces = re.split(r'\s+and\s+', body, flags=re.I)
    if len(pieces) > 2: return None
    claims = set(); inherited = None
    for part in pieces:
        match = _REVIEW_CLAUSE.fullmatch(part)
        kind = 'review'
        if match is None: match = _COMMENT_CLAUSE.fullmatch(part); kind = 'opportunity'
        if match is None or kind in claims: return None
        actual_object = (match['object'] or inherited or '').casefold()
        if actual_object != required_object: return None
        inherited = actual_object; claims.add(kind)
    return claims


def explicit_patient_report(text):
    return bool(_PATIENT_REPORT.search(text) and text.rstrip().endswith('.'))


def policy_warnings(field, selected):
    """Source-printed role/attestation requirements cannot be model permissions.

    These narrow literal prerequisites do not qualify model relevance. They keep
    clinical observations from becoming patient statements or review attestations.
    Unknown policy shapes require an explicit clinician decision.
    """
    policy = field.get('answer_policy')
    if not isinstance(policy, dict): return []
    def anchor(name):
        source = policy.get(name)
        return (isinstance(source, dict) and set(source) == {'part', 'slot', 'fingerprint', 'text'} and
                all(isinstance(value, str) and value.strip() for value in source.values()) and
                re.fullmatch('[0-9a-f]{64}', source['fingerprint']))
    valid = (set(policy) <= {'source_author', 'attestation', 'source', 'attestation_source'} and
             bool(set(policy) & {'source_author', 'attestation'}) and
             ('source_author' not in policy or anchor('source')) and
             ('attestation' not in policy or anchor('attestation_source')) and
             ('source' not in policy or 'source_author' in policy) and
             ('attestation_source' not in policy or 'attestation' in policy) and
             policy.get('source_author', 'patient') == 'patient' and
             policy.get('attestation', 'document_review') == 'document_review')
    if not valid: return list(selected)
    # Additional preserved instructions may qualify the printed attestation.
    # This narrow reader cannot grant authority from the left question alone.
    if 'attestation' in policy and field.get('source_instructions'): return list(selected)
    requirements = review_requirements(policy['attestation_source']['text']) if 'attestation' in policy else None
    if 'attestation' in policy and requirements is None: return list(selected)
    warnings = []; supplied = set()
    for unit in selected:
        text = unicodedata.normalize('NFKC', unit['quote']).strip()
        if 'source_author' in policy and not _PATIENT_REPORT.search(text): warnings.append(unit)
        if requirements:
            claims = review_claims(text, requirements[0])
            if not claims or not claims & requirements[1]: warnings.append(unit)
            else: supplied.update(claims)
    if requirements and (not requirements[1] & supplied or requirements[2] and not requirements[1] <= supplied):
        return list(selected)
    return warnings



_TEMPORAL = re.compile(r'\b(before|after|prior\s+to|following|preceding)\s+'
    r'(?:(?:the|an?|your|their|his|her|this|that|any)\s+)*([a-z][a-z-]*)', re.I)


def word_roots(word):
    """Literal inflection/agent-noun matching, never synonym or topic inference."""
    word = word.casefold()
    forms = {word}
    for suffix in ('s', 'es', 'er', 'ing'):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            forms.add(word[:-len(suffix)])
    if word.endswith('ies'): forms.add(word[:-3] + 'y')
    return {value.rstrip('e') for value in forms if len(value) >= 3}


def temporal_scopes(text):
    return [('before' if relation.casefold() in ('before', 'prior to', 'preceding') else 'after', word_roots(event))
            for relation, event in _TEMPORAL.findall(unicodedata.normalize('NFKC', str(text or '')))]


def temporal_warnings(field, selected):
    """A printed event-relative question requires that relation in its source.

    Source without the requested time remains ambiguous; a model cannot assign
    current symptoms to an explicitly pre-event question by destination ID alone.
    Full selected statements and every explicit temporal qualifier are retained.
    """
    required = temporal_scopes(str(field.get('context') or '') + ' ' + str(field.get('label') or ''))
    if not required or not selected: return []
    warnings = []
    for unit in selected:
        offered = temporal_scopes(unit['quote'])
        if (any(not any(direction == actual and event & actual_event for actual, actual_event in offered)
                for direction, event in required) or
                any(not any(direction == actual and event & actual_event for direction, event in required)
                    for actual, actual_event in offered)):
            warnings.append(unit)
    return warnings


_QUESTION_WORDS = frozenset('a an the do does is are you your patient any have has there status'.split())
_PREDICATE = re.compile(r'^(?:the\s+)?patient\s+(?:'
    r'(?P<does>does\s+(?:(?P<does_not>not|never)\s+)?)|'
    r'(?P<copula>is\s+(?:(?P<is_not>not|never)\s+)?(?:an?\s+)?)|'
    r'(?P<has>has\s+(?:(?P<has_no>no)\s+)?(?:an?\s+)?)|'
    r'(?P<denies>denies\s+)|(?P<reports>reports\s+(?:(?P<reports_no>no)\s+)?))?'
    r'(?P<predicate>[a-z][a-z -]*)\.$', re.I)
_UNCERTAIN_PREDICATE = re.compile(r'\b(?:not|no|never|sometimes|usually|occasionally|daily|formerly|previously|currently|'
                                 r'but|and|or|if|may|might|could|would|will|stopped|ceased|quit|denied|denies|without)\b', re.I)


def predicate_polarity(field, unit):
    """A small exact current-predicate reader; unknown is not a negative.

    Match the original question's words to the complete explicit patient clause,
    allowing regular inflections (smoker/smoke, pain/pains). No lexical overlap
    with a neighbouring topic or a qualified tail establishes an answer.
    """
    from . import generation as g
    quote = unicodedata.normalize('NFKC', unit['quote']).strip()
    own = g.tab_source_value(quote, g.recognized_labels([field]))
    if own and own[0] == g.question_key(field['label']):
        literal = g.without_closing_stop(own[1]).casefold()
        if literal in ('yes', 'no', 'true', 'false', 'present', 'absent'):
            return literal in ('yes', 'true', 'present')
        return None
    match = _PREDICATE.fullmatch(quote)
    if match is None: return None
    predicate = match['predicate'].strip().casefold()
    if _UNCERTAIN_PREDICATE.search(predicate): return None
    question = str(field['label']).casefold()
    if not any(match[name] for name in ('does', 'copula', 'has', 'denies', 'reports')):
        # A bare verb can name an action question or its agent noun (smoker),
        # but noun overlap cannot assert a condition ("patient toes" → Toes).
        if not re.match(r'^(?:do|does)\b', question) and not re.fullmatch(r'[a-z]+er[?:]?', question.strip()):
            return None
    if re.search(r'\b(?:not|no|non|without|never)\b', question): return None
    wanted = [word_roots(w) for w in re.findall('[a-z]+', question) if w not in _QUESTION_WORDS]
    actual = [word_roots(w) for w in predicate.split()]
    negative = any(match[name] for name in ('does_not', 'is_not', 'has_no', 'denies', 'reports_no'))
    # The longstanding literal nonsmoker relation remains available.
    if len(actual) == 1 and predicate.startswith('non'):
        if negative: return None
        actual = [word_roots(predicate[3:])]; negative = True
    if not wanted or len(wanted) != len(actual): return None
    if not all(left & right for left, right in zip(wanted, actual)): return None
    return not negative


def option_warnings(field, all_units, selected, option_texts):
    """A binary option needs matching explicit source polarity, never model assent.

    Other option vocabularies still require qualification by the model contract.
    This guard closes the explicit-predicate binary family without pretending to
    prove open-ended clinical equivalence.
    """
    from documents.word_v3 import printed_options
    from . import generation as g
    labels = [g.without_closing_stop(o).casefold() for o in printed_options(field)]
    if field.get('kind') == 'checkbox' and selected:
        if any(predicate_polarity(field, unit) is not True for unit in selected): return list(selected)
        return [unit for unit in all_units if predicate_polarity(field, unit) is False]
    pairs = ({'yes', 'no'}, {'true', 'false'}, {'present', 'absent'})
    if len(labels) != 2 or set(labels) not in pairs or not selected: return []
    chosen = [g.without_closing_stop(o).casefold() for o in option_texts]
    if len(chosen) != 1 or chosen[0] not in labels: return list(selected)
    expected = chosen[0] in ('yes', 'true', 'present')
    if any(predicate_polarity(field, unit) is not expected for unit in selected): return list(selected)
    if any((value := predicate_polarity(field, unit)) is not None and value is not expected for unit in all_units):
        return list(selected)
    return []
