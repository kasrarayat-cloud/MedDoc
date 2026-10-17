"""Prospective source ownership for complete, literal clinical assertions.

This module reads original source structure, never extracted fact annotations.
Medical vocabulary is not an ownership test. Foreign people, quoted material,
other encounters and unresolved source attribution retain their own scope.
"""
import re


PERSON = (r'(?:(?:another|other)\s+patient|family(?:\s+(?:history|member))?|'
    r'(?:(?:maternal|paternal)\s+)?(?:mother|father|grandmother|grandfather|grandparent|'
    r'aunt|uncle|cousin|niece|nephew|sibling|brother|sister|daughter|son|child|'
    r'husband|wife|partner|spouse|friend|relative))')
SECTION = (r'(?:(?:medical|clinical)\s+)?history|'
    r'(?:encounters?|visits?|consultations?)(?:\s+(?:history|notes?|records?))?|notes?|records?')
CLINICAL_HEADINGS = r'Subjective|History|History of present illness|Review of systems|Objective|Examination|Physical examination|Assessment|Impression|Plan'
NUMBER = r'(?:\d+(?:\.\d+)?|[A-Za-z]+(?:[- ][A-Za-z]+)?)'


def _normal(text):
    return ' '.join(text.strip().removesuffix('.').split()).casefold()


def clinician_matches(context, name):
    """Only an explicit treating role can bind a named physician-time claim."""
    value = re.sub(r'^(?:dr\.?|doctor)\s+', '', _normal(name))
    return sum(value in clinician['aliases'] for clinician in context['clinicians']) == 1


def _account_preamble(text):
    """Recognize complete scope/adverbial frames; unknown outer claims qualify."""
    value=text.strip().strip(',').strip()
    if not value:
        return {'current_owned':True,'qualified':False}
    person=r"(?:(?:the\s+)?patient['’]s\s+|(?:his|her|their|the)\s+)?"+PERSON
    foreign=(r'(?:for|regarding|about|concerning)\s+(?:'+person
        +r"(?:['’]s)?(?:\s+(?:history|account|record|visit|encounter))?|(?:another|the\s+other)\s+clinician)")
    past=r'(?:(?:during|in|at|for)\s+(?:a\s+|the\s+)?(?:prior|previous|earlier|past|different|another)\s+(?:visit|encounter|appointment)|yesterday)'
    if re.fullmatch(foreign+'|'+past,value,re.I):
        return {'current_owned':False,'qualified':False}
    if re.fullmatch(r'(?:(?:do\s+not\s+)?(?:disregard|ignore)|do\s+not\s+use|now|currently|today|at\s+present)',value,re.I):
        return {'current_owned':True,'qualified':False}
    # Unrecognized preparatory phrases may govern the embedded proposition
    # (for example an assumption or verification). Their vocabulary alone
    # cannot establish an independent assertion, so retain the qualification.
    return {'current_owned':True,'qualified':True}


def _account_reference(text, *, include_unowned=False):
    """Separate the named account from its predicate and its objects."""
    number = r'(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)'
    modifier = r'(?:stated|documented|reported|physician|clinical|above|preceding|entire|whole|earlier|last|'+number+r')'
    reference = r'\b(?:the|this|these|those|that)\s+(?:'+modifier+r'[ -]+)*(?:assessment|time|total|minutes|entries|documentation|record|account|text|paragraph|material|note|findings)\b'
    match = re.search(reference, text, re.I)
    if not match:
        return None
    tail = text[match.start():]
    predicate = re.search(r'\b(?:is|are|was|were|does|do|did|has|have|had|belongs?|refers?|relates?|concerns?|describes?|pertains?|includes?|excludes?|remains?|represents?|counts?|must|should|cannot|can)\b', tail, re.I)
    prefix = tail[:predicate.start()] if predicate else tail
    prefix = re.sub(r'\b(?:actually|also|now|still)\s*$', '', prefix, flags=re.I)
    # A named foreign/past account does not refer to this patient's account.
    preamble = _account_preamble(text[:match.start()])
    foreign_or_past = (re.search(r'\b(?:'+PERSON+r'|yesterday|prior|previous|earlier|other\s+clinician)\b', prefix, re.I)
        or not preamble['current_owned'])
    if foreign_or_past and not include_unowned:
        return None
    domains = set()
    if re.search(r'\bassessment\b', prefix, re.I):
        domains.add('assessment')
    if re.search(r'\b(?:time|minutes)\b', prefix, re.I):
        domains.add('time')
    elif re.search(r'\btotal(?:\s+(?:account|calculation|figures?))?\s*[.!?]?$', prefix, re.I):
        # A bare deictic total may refer to physician time; a named different
        # account, such as total fluid intake, is not a physician-time total.
        domains.add('time')
    if not domains and re.search(r'\bfindings\b', prefix, re.I):
        domains.add('clinical')
    if not domains and re.search(r'\blast\s+paragraph\b', prefix, re.I):
        domains.add('paragraph')
    return {'match': match, 'tail': tail, 'prefix': prefix, 'domains': domains,
        'predicate': tail[predicate.start():] if predicate else None,
        'current_owned': not bool(foreign_or_past), 'qualified': preamble['qualified']}


def account_reference(text):
    """Clause metadata for shared consumers; outer source ownership still gates.

    None means no recognized account reference. An explicit foreign or prior
    account instead returns current_owned=False, so consumers need not infer
    ownership again from the predicate's words or an intervening preamble.
    """
    reference = _account_reference(text, include_unowned=True)
    if reference is None:
        return None
    return {'current_owned': reference['current_owned'], 'qualified': reference['qualified'],
        'domains': set(reference['domains']), 'tail': reference['tail'],
        'predicate': reference['predicate'], 'subject': reference['prefix'],
        'start': reference['match'].start()}


def account_clauses(text):
    """Split predicates only when a conjunction introduces a new named account.

    A coordinated subject (assessment and physician time) stays together;
    a new subject after an existing predicate owns its own qualification.
    """
    clauses, start = [], 0
    for boundary in re.finditer(r'(?:;\s*|\s*,?\s+(?:but|and|while|whereas)\s+)', text, re.I):
        left = _account_reference(text[start:boundary.start()], include_unowned=True)
        right = _account_reference(text[boundary.end():], include_unowned=True)
        predicate = left and (left['predicate'] or re.search(r'\b(?:disregard|ignore|use)\b', text[start:boundary.start()][:left['match'].start()], re.I))
        if predicate and right:
            clauses.append(text[start:boundary.start()].strip())
            start = boundary.end()
    clauses.append(text[start:].strip())
    return clauses


def _integrity_assertion(text):
    return all(_clause_integrity_assertion(clause) for clause in account_clauses(text))


def _clause_integrity_assertion(text):
    """A complete negated invalidation affirms the source account's integrity."""
    reference = _account_reference(text)
    if not reference or reference['qualified']:
        return False
    prefix = text[:reference['match'].start()]
    if re.fullmatch(r'\s*do\s+not\s+(?:disregard|ignore)\s+', prefix, re.I):
        account_words = r'(?:the|this|these|those|that|above|preceding|physician|clinical|stated|documented|reported|time|assessment|account|calculation|figures?|entries|minutes|total|and)'
        return bool(re.fullmatch(r'(?:'+account_words+r'[ ,]+)*'+account_words+r'\.?', reference['tail'], re.I))
    predicate = reference['predicate']
    if not predicate:
        return False
    return bool(re.fullmatch(r'(?:is|are|was|were)\s+not\s+(?:(?:wrong|erroneous|incorrect|invalid)(?:\s+or\s+(?:wrong|erroneous|incorrect|invalid))*|copied\s+from\s+(?:(?!\band\b|\bbut\b)[A-Za-z -])+|(?:for|about)\s+(?:(?!\band\b|\bbut\b)[A-Za-z -])+|withdrawn|retracted)\s*\.?', predicate, re.I)
        or re.fullmatch(r'(?:do|does|did)\s+not\s+(?:belong|refer|relate|concern|pertain)\b(?:(?!\band\b|\bbut\b)[A-Za-z -])+\.?', predicate, re.I))



def _retracted_domains(text, established=()):
    return set().union(*(_retracted_clause_domains(clause, established)
        for clause in account_clauses(text)))


def _retracted_clause_domains(text, established=()):
    """Resolve account references; unknown relevant qualifications stay held.

    A later source-owned reference to an established account cannot disappear
    merely because its predicate is outside the literal rendering grammar.
    """
    reference = _account_reference(text)
    if not reference or _integrity_assertion(text):
        return set()
    tail, domains = reference['tail'], reference['domains']
    # This permission recognizes the complete source predicate, not an
    # embedded tail stripped of an unknown outer qualification.
    if time_kind(text):
        return set()
    if reference['qualified']:
        return domains or ({'all'} if not re.search(r'\btotal\b', reference['prefix'], re.I) else set())
    directive = re.search(r'\b(?:disregard|ignore|do\s+not\s+use)\s*$', text[:reference['match'].start()], re.I)
    if directive or re.match(r'\s*retraction\s*:', text, re.I):
        return domains or {'all'}
    relation = re.search(r'\b(?:belongs?|refers?|relates?|concerns?|describes?|pertains?|(?:was|were|is|are)\s+(?:for|about))\b', tail, re.I)
    error = re.search(r'\b(?:erroneous|wrong|incorrect|invalid|retracted|withdrawn|copied|must\s+not\s+be\s+used)\b', tail, re.I)
    other_scope = r'\b(?:'+PERSON+r'|yesterday|preceding\s+day|previous\s+day|(?:earlier|different|another|previous)\s+(?:visit|encounter|appointment)|different\s+patient)\b'
    if error or relation and re.search(other_scope, tail[relation.end():], re.I):
        return domains or ({'all'} if not re.search(r'\btotal\b', reference['prefix'], re.I) else set())
    return domains if domains.intersection(established) else set()


def source_context(notes, units=None):
    if units is None:
        from .generation import source_units
        units, _ = source_units(notes, [])
    identities, clinicians = [], []
    events = {}
    clinical = re.compile(r'\s*(?:[SOAP]\s*[-–:]\s*)?('+CLINICAL_HEADINGS+r')\s*:?\s*', re.I)
    person = r"(?:(?:the\s+)?patient['’]s\s+|(?:the|her|his|their)\s+)?"+PERSON
    foreign = (r'(?:'+person+r"(?:['’]s)?(?:\s+(?:(?:previous|prior|current|past)\s+)?(?:"+SECTION+r'))?|'
        r'(?:'+SECTION+r')\s+(?:of|for)\s+(?:the\s+)?'+person+r')')
    encounter = r'(?:(?:encounters?|visits?|consultations?)(?:\s+(?:history|notes?|records?))?|notes?|records?)'
    for unit in units:
        text, start = unit['quote'].strip(), unit['start']
        identity = re.fullmatch(r"(?:(?P<current>current|today['’]s)\s+)?patient(?:\s+(?:full\s+)?name)?\s*:\s*(?P<name>.+?)\s*\.?", text, re.I)
        clinician = re.fullmatch(r'(?:treating|attending|examining)\s+(?:clinician|physician|doctor)\s*:\s*(?:Dr\.?\s+|Doctor\s+)?(?P<name>[A-Za-z][A-Za-z\s\x27’.-]+?)\s*\.?', text, re.I)
        if identity:
            name = identity['name'].strip().removesuffix('.')
            identities.append(name)
            events[start] = ('patient', _normal(name), bool(identity['current']))
        elif clinician:
            name = clinician['name'].strip().removesuffix('.')
            clinicians.append({'name': name, 'aliases': [_normal(name), _normal(name.split()[-1])], 'source': unit})
        elif re.fullmatch(foreign+r'(?:\s*:\s*[^\r\n]*)?\s*\.?', text, re.I):
            events[start] = ('foreign',)
        elif re.fullmatch(r'(?:the\s+)?(?:previous|prior|historical|past|earlier|old|last|future|upcoming|next|planned)\s+(?:(?:office|clinical)\s+)?'+encounter+r'(?:\s*:\s*[^\r\n]*)?\s*\.?', text, re.I):
            events[start] = ('time', 'future' if re.match(r'(?:the\s+)?(?:future|upcoming|next|planned)\b', text, re.I) else 'past')
        elif re.fullmatch(encounter+r'\s+(?:from\s+)?'+NUMBER+r'\s+(?:days?|weeks?|months?|years?)\s+ago\s*:?\s*\.?', text, re.I):
            events[start] = ('time', 'past')
        elif re.fullmatch(r"(?:the\s+)?(?:current|present|today['’]s)\s+(?:office\s+)?(?:encounter|visit|consultation)\s*:?\s*\.?", text, re.I):
            events[start] = ('time', 'current')
        elif re.search(r'\b(?:quoted|quotation|hypothetical|example|vignette|copied|transcribed)\b', text, re.I) and not _integrity_assertion(text):
            events[start] = ('ambiguous',)
        elif re.fullmatch(r'[Pp]atient\s+(?:[-–—]\s*)?[A-Z][A-Za-z\x27’\-]*(?:\s+[A-Z][A-Za-z\x27’\-]*){0,5}(?:\s+(?:'+SECTION+r'))?\s*:?\s*', text):
            events[start] = ('foreign',)
        elif re.search(r'\b(?:belongs?\s+to|(?:describes?|concerns?)\s+(?:another|a\s+different)|not\s+(?:this|the)\s+patient|(?:mother|father|sibling|spouse)[\x27’]s\s+(?:record|visit|note))\b', text, re.I) and not _integrity_assertion(text):
            events[start] = ('ambiguous',)
    unique = {_normal(name) for name in identities}
    issues = ([] if len(unique) == 1 else
        ['The source does not establish one explicit patient identity.'])
    initial = next(iter(unique), None) if len(unique) == 1 else None
    owner, encounter_time, section = 'ambiguous', 'current', None
    rows, retracted, established = {}, [], set()
    for unit in units:
        text, start = unit['quote'].strip(), unit['start']
        event = events.get(start)
        if owner=='patient' and encounter_time=='current':
            for clause in account_clauses(text):
                domains=_retracted_clause_domains(clause,established)
                if domains:
                    begin,end=0,start if re.search(r'\b(?:above|preceding)\b',clause,re.I) else None
                    if 'paragraph' in domains:
                        preceding=notes[:start].rstrip();breaks=list(re.finditer(r'\r?\n[ \t]*\r?\n',preceding))
                        begin=breaks[-1].end() if breaks else 0;end=len(preceding);domains={'all'}
                    retracted.append((domains,begin,end))
        if event:
            if event[0] == 'patient':
                owner = 'patient' if event[1] == initial else 'ambiguous'
                if event[2]: encounter_time = 'current'
            elif event[0] in ('foreign', 'ambiguous'):
                owner = event[0]
            elif event[0] == 'time':
                encounter_time = event[1]
        heading = clinical.fullmatch(text)
        if heading: section = heading[1].casefold()
        row_issues = list(issues)
        if (re.search(r'[“”"]|\b(?:suppose|imagine|hypothetical)\b', text, re.I)
                or re.search(r'\bif\b',text,re.I) and literal_kind(text,section)!='conditional_plan'):
            row_issues.append('Quoted or hypothetical source is not a current patient assertion.')
        if re.match(r'\s*(?:his|her|their|the\s+patient[\x27’]s)\s+'+PERSON+r'\b', text, re.I):
            row_issues.append('This statement introduces a different person.')
        row_time = encounter_time
        # Earlier-visit narration does not turn later current medication or SOAP
        # assertions historical; an explicit historical SECTION does persist.
        if encounter_time == 'current' and re.match(r'\s*(?:(?:he|she|they|the\s+patient)\s+previously\s+(?:saw|visited|attended)|at\s+that\s+visit)\b', text, re.I):
            row_time = 'past'
        rows[start] = {'subject': owner, 'timing': row_time, 'section_timing': encounter_time,
            'section': section, 'issues': row_issues}
        if owner=='patient' and encounter_time=='current' and not row_issues and not heading:
            if section in ('assessment','impression'):established.add('assessment')
            if time_kind(text):established.add('time')
    for unit in units:
        row=rows[unit['start']]
        if row['subject']!='patient' or row['section_timing']!='current':continue
        if any(begin<=unit['start'] and (end is None or unit['start']<end) and ('all' in domains
                or 'clinical' in domains and row['section'] is not None
                or 'assessment' in domains and row['section'] in ('assessment','impression')
                or 'time' in domains and re.search(r'\b(?:time|minutes|total)\b',unit['quote'],re.I)) for domains,begin,end in retracted):
            row['issues'].append('A later source statement retracts, reassigns or retimes this clinical account.')
    # Role labels are assertions with the same owner/day boundaries as facts.
    # A foreign or historical treating-clinician header cannot authorize a
    # similarly named performer after a current-patient reset.
    clinicians = [clinician for clinician in clinicians
        if (row := rows[clinician['source']['start']])['subject'] == 'patient'
        and row['section_timing'] == 'current' and not row['issues']]
    return {'patient_name': identities[0] if len(unique) == 1 else None,
        'clinicians': clinicians, 'units': rows, 'issues': issues}


def owned_current(context, unit, *, historical_support=False):
    row = context['units'].get(unit['start'])
    return bool(row and not row['issues'] and row['subject'] == 'patient'
        and row['section_timing'] == 'current'
        and (historical_support or row['timing'] == 'current'))


def literal_kind(text, section=None):
    """Complete source predicates, with no disease/drug/test allowlist."""
    value = text.strip().removesuffix('.').strip()
    if section in ('assessment', 'impression'):
        if re.fullmatch(r'(?:the\s+)?(?:cause|etiology)(?:\s+of\s+(?:these|the)\s+symptoms)?\s+(?:remains?|is)\s+(?:uncertain|unknown|unclear)', value, re.I):
            return 'uncertainty'
        if re.fullmatch(r'[A-Za-z][A-Za-z ,/-]{0,250}\s+(?:causes|etiologies|diagnoses|conditions)\s+(?:remain|are)\s+(?:possibilities|possible|uncertain)(?:\s*;\s*(?:neither|none)\s+(?:has|have)\s+been\s+(?:established|confirmed|diagnosed))?', value, re.I):
            return 'uncertainty'
        if re.fullmatch(r'no\s+(?:definitive\s+)?(?:underlying\s+)?(?:disease|diagnosis|condition)\s+(?:is|was|has\s+been)\s+(?:diagnosed|established|confirmed)\s+(?:at|during)\s+this\s+encounter', value, re.I):
            return 'diagnostic_limit'
    if re.fullmatch(r'(?:he|she|they|the\s+patient)\s+(?:(?:is|are)\s+no\s+longer\s+|(?:has|have)\s+(?:stopped|ceased|discontinued)\s+)(?:taking|using)\s+[A-Za-z][A-Za-z0-9 ,/()-]{0,160}', value, re.I):
        return 'medication_absence'
    if re.fullmatch(r'(?:he|she|they|the\s+patient)\s+(?:has|have)\s+never\s+had\s+[A-Za-z][A-Za-z -]{0,100}',value,re.I):
        return 'documented_absence'
    if section=='review of systems' and re.fullmatch(r'there\s+(?:are|were)\s+no\s+additional\s+findings\s+beyond\s+[^\r\n]+\s+described\s+above',value,re.I):
        return 'negative_summary'
    if section in ('objective','examination','physical examination') and re.match(r'(?:(?:he|she|they)\s+|(?:his|her|their|the)\s+(?:head|neck|chest|abdomen|extremities|patient)\s+|(?:heart\s+rhythm|lungs)\s+)',value,re.I) and re.search(r'\b(?:no|not|without)\b',value,re.I):
        return 'negative_observation'
    if section=='plan' and re.fullmatch(r'[A-Za-z][A-Za-z -]{0,100}\s+is\s+(?:requested|ordered|planned)\s+for\s+a\s+later\s+date\s+if\s+[A-Za-z][A-Za-z -]{0,80}\s+(?:persist|persists|worsen|worsens|recur|recurs|continue|continues)',value,re.I):
        return 'conditional_plan'
    if section in ('plan', 'objective', 'examination', 'physical examination') and re.fullmatch(
            r'no\s+[A-Za-z][A-Za-z ,/-]{0,200}\s+(?:(?:was|were)\s+(?:collected|performed)|took\s+place)\s+(?:today|(?:at|during)\s+(?:this\s+(?:encounter|visit)|today[\x27’]s\s+visit))'
            r'(?:\s*,\s*neither\s+test\s+was\s+performed\s+today\s+and\s+no\s+results\s+are\s+available)?', value, re.I):
        return 'nonperformance'
    if section=='plan' and re.fullmatch(r'[A-Za-z][A-Za-z -]{0,100}\s+was\s+not\s+performed\s+today,\s+no\s+[A-Za-z][A-Za-z -]{0,80}\s+was\s+obtained\s+and\s+there\s+are\s+no\s+(?:investigation\s+)?results\s+from\s+this\s+visit',value,re.I):
        return 'nonperformance'
    return None


def literal_segments(text):
    """Explicit present cessation can follow a separately timed prior trial."""
    result=[]
    for match in re.finditer(r';\s*(?P<clause>(?:he|she|they|the\s+patient)\s+(?:is|are)\s+no\s+longer\s+(?:taking|using)\s+[^;\r\n]+)\s*$',text,re.I):
        prefix=text[:match.start()]
        if re.search(r'\b'+PERSON+r'\b',prefix,re.I):continue
        if not re.match(r'\s*(?:(?:an?|the)\s+[^;]{0,120}\btrial\b|(?:he|she|they|the\s+patient)\s+)',prefix,re.I):continue
        clause=match['clause'].strip().removesuffix('.')
        if literal_kind(clause)=='medication_absence':result.append((match.start('clause'),match.start('clause')+len(clause),'medication_absence'))
    # Each negative predicate retains its full coordinated object list.
    social=re.fullmatch(r'\s*(?:he|she|they|the\s+patient)\s+(?P<first>has\s+never\s+smoked)\s+and\s+(?P<second>does\s+not\s+use\s+[A-Za-z][A-Za-z -]{0,100})\s*\.?',text,re.I)
    if social:
        for group in ('first','second'):result.append((social.start(group),social.end(group),'social_absence'))
    return result


def requirement_kind(text, section=None):
    """Detect omissions more broadly than permission to render a statement.

    Unrecognized wording with explicit qualification cues stays an obligation;
    extracting nothing must not turn an uncertain interpretation into a pass.
    """
    literal=literal_kind(text,section)
    if literal:return literal
    if section in ('assessment','impression') and not re.fullmatch(r'\s*(?:[SOAP]\s*[-–:]\s*)?(?:Assessment|Impression)\s*:?',text,re.I):
        return 'assessment_content'
    if re.search(r'\b(?:no\s+longer|stopped|ceased|discontinued|not\s+(?:taking|using))\b',text,re.I) and re.search(r'\b(?:taking|using|medication|medicine|drug)\b',text,re.I):
        return 'medication_absence'
    if section in ('plan','objective','examination','physical examination') and re.search(r'\b(?:no|not|neither|none|without)\b',text,re.I) and re.search(r'\b(?:tests?|procedures?|investigations?|samples?|collected|performed|collection|results?)\b',text,re.I):
        return 'nonperformance'
    return None


def time_kind(text):
    value = text.strip().removesuffix('.').strip()
    if re.fullmatch(r'(?:office\s+)?(?:E\s*/?\s*M|evaluation\s+and\s+management)\s+(?:selection|level)\s+(?:is|was)\s+based\s+on\s+(?:total\s+)?(?:physician|clinician)\s+time(?:\s+on\s+the\s+(?:date\s+of\s+service|encounter\s+date))?', value, re.I):
        return 'basis'
    total = re.fullmatch(r'(?:total\s+(?:physician|clinician)\s+time\s+(?:on\s+the\s+date\s+of\s+service\s+)?(?:was|is|:)\s*'
        r'|(?P<actor>(?:Dr\.?\s+|Doctor\s+)[A-Za-z][A-Za-z .\x27’\-]{0,80}|the\s+(?:physician|clinician))\s+(?:personally\s+)?spent\s+)'
        r'(?P<total>'+NUMBER+r')\s+minutes(?:\s+on\s+(?:the\s+(?:encounter\s+date|date\s+of\s+service)|today))?'
        r'(?P<activities>\s*[:,;]\s*(?:including\s+)?[^\r\n]+)', value, re.I)
    if total: return 'total'
    if re.fullmatch(r'(?:this\s+total|the\s+total|the\s+'+NUMBER+r'\s+minutes|they|(?:these|those)\s+minutes)\s+(?:also\s+)?(?:excludes?|does\s+not\s+(?:include|count))\s+[^\r\n]+', value, re.I):
        return 'exclusion'
    if re.fullmatch(r'(?:time\s+[^\r\n]+\s+(?:is|was)\s+excluded\s+from\s+(?:this|the)\s+total|I\s+excluded\s+[^\r\n]+\s+from\s+(?:this|the)\s+total)',value,re.I):
        return 'exclusion'
    return None


def source_clinician_bound(context, text):
    """A provider annotation cannot replace a different named source actor."""
    actor = re.search(r'(?:Dr\.?\s+|Doctor\s+)([A-Za-z][A-Za-z .\x27’\-]{0,80}?)(?=\s+(?:personally\s+)?spent\b|\s*,|\s+in\s+this\s+same\b)', text, re.I)
    return not actor or clinician_matches(context, actor[1])


def _number(text):
    value = text.casefold().replace('-', ' ').strip()
    if re.fullmatch(r'\d+(?:\.\d+)?', value): return float(value)
    words = dict(zip(('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen').split(), range(20)))
    words.update(dict(zip(('twenty thirty forty fifty sixty seventy eighty ninety').split(), range(20,100,10))))
    parts=value.split()
    return sum(words[p] for p in parts) if parts and all(p in words for p in parts) else None


def time_blocks(notes, units, context):
    """Only adjacent source-owned time statements share a deictic total."""
    result, group = [], []
    def finish():
        kinds = [kind for _,kind in group]
        if 'basis' not in kinds or 'total' not in kinds:
            return
        totals = [unit for unit,kind in group if kind == 'total']
        total_match = re.search(r'('+NUMBER+r')\s+minutes\b', totals[0]['quote'], re.I)
        total_value = _number(total_match[1]) if total_match else None
        valid = len(totals)==1 and total_value is not None and source_clinician_bound(context,totals[0]['quote'])
        total_seen = False
        for unit, kind in group:
            if kind == 'total': total_seen = True
            if kind in ('basis','total') or kind in ('exclusion','qualification') and total_seen:
                reference = re.match(r'the\s+('+NUMBER+r')\s+minutes\b',unit['quote'],re.I) if kind=='exclusion' else None
                result.append({'source':unit,'kind':kind,'binding_valid':valid and (not reference or _number(reference[1])==total_value)})
    previous = None
    for unit in units:
        owned=owned_current(context,unit)
        kind = time_kind(unit['quote']) if owned else None
        gap = notes[previous['end']:unit['start']] if previous else ''
        if (owned and not kind and any(k=='total' for _,k in group)
                and not re.search(r'\r?\n\s*\r?\n',gap)
                and not _integrity_assertion(unit['quote'])
                and re.search(r'\b(?:time|minutes|total|exclud\w*|count\w*)\b',unit['quote'],re.I)):
            kind='qualification'
        if not kind or gap.strip() or re.search(r'\r?\n\s*\r?\n',gap) and kind not in ('exclusion','qualification'):
            finish(); group=[]
        if kind: group.append((unit,kind))
        previous=unit
    finish()
    return result
