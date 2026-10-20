"""Prospective, positioned clinical meaning shared by generation and coding.

An assertion's evidence, owner, encounter, clinical time and modality are separate
axes. Field requirements are compiled from the whole approved meaning, including
exclusions. Neither a review tick nor a matching keyword supplies source truth.
Historical generation contracts do not call this module.
"""
from copy import deepcopy
import hashlib
import json
import re

CONTRACT = 'positioned-clinical-semantics-v25'
CONTEXT_PROFILE = 'positioned-source-meaning-v1'
REQUIREMENTS_CONTRACT = 'approved-field-requirements-v1'
INSTRUCTIONS = (
    ' Use the positioned clinical meaning contract. approved_field_requirements is the same complete-meaning '
    'interpretation used for assignment, completeness and repair: excluded topics never create requirements. '
    'source_assertions describes original source scope, not invented facts. Preserve complete relevant narrative '
    'predicates with their temporal qualifiers, negatives, uncertainty and conditions in the VALUE quote itself. '
    'A timing annotation does not replace visible wording such as a baseline or previous/current distinction. '
    'A source_projections proof may restore an independently bound leading temporal adjunct to an otherwise '
    'complete predicate using one unchanged literal source span. Judge that derived visible value and its proof; '
    'the raw extraction remains unchanged. A projection cannot remove a source hold or add another assertion. '
    'A conditional instruction is an instruction about future action; its antecedent is not a present diagnosis. '
    'An uncertain assessment may be reproduced literally, retaining that uncertainty; it is never a confirmed disease. '
    'For a complete narrative retain every documented relevant assertion, including actual nonperformance and '
    'results absence, medication history, time-account activities and exclusions where requested. An order today '
    'and its future performance are distinct. Do not move a current order or not-performed status into the future. '
    'Keep genuinely undocumented values blank. Exact evidence, subject, encounter timing, actual contradictions '
    'and retractions remain authoritative; review cannot waive them. Do not manufacture a fact to repair extraction.')

_DOMAINS = {
    'subjective': r'\bsubjective\b|\bpatient[- ]reported\s+symptoms?\b|\breported\s+symptoms?\b|\bsymptom\s+history\b',
    'objective': r'\bobjective\b|\bobservations?\b|\b(?:physical\s+)?exam(?:ination)?\b|\b(?:measured|test)\s+results?\b',
    'assessment': r'\bassessment\b|\bimpression\b|\bdiagnos(?:is|es|tic)\b|\bclinical\s+interpretation\b',
    'plan': r'\bplan\b|\bmanagement\b|\bfollow[- ]?up\b|\breferrals?\b|\badvice\b',
    'history': r'\bhistory\b|\bprevious\b|\bprior\b|\bbaseline\b',
    'medication': r'\bmedicin(?:e|es)\b|\bmedications?\b|\ballerg(?:y|ies)\b|\btreatment\b',
    'investigation': r'\binvestigations?\b|\btests?\b|\bprocedures?\b|\bcollection\b|\bperformance\b|\bresults?\b',
    'time': r'\bphysician\s+time\b|\bclinician\s+time\b|\bE\s*/\s*M\b|\btime\s+(?:account|basis|activities|exclusions)\b',
    'identity': r'\bpatient\s+(?:full\s+)?name\b|\bidentity\b',
}
_SECTION_DOMAIN = {'subjective': 'subjective', 'history': 'subjective',
    'history of present illness': 'subjective', 'review of systems': 'subjective',
    'objective': 'objective', 'examination': 'objective', 'physical examination': 'objective',
    'assessment': 'assessment', 'impression': 'assessment', 'plan': 'plan'}
_RETRACTION = 'A later source statement retracts, reassigns or retimes this clinical account.'
_NEGATIVE = re.compile(r'\b(?:no|not|never|neither|nothing|without|denies?|denied|absent|absence|non[- ]?tender|nontender|non[- ]?distended)\b', re.I)
_UNCERTAIN = re.compile(r'\b(?:possible|possibly|possibility|possibilities|suspected|uncertain|unclear|unknown|may|might|could|unestablished)\b', re.I)
_PAST = re.compile(r'\b(?:previously|formerly|used\s+to|last\s+(?:week|month|year)|at\s+baseline|'
    r'(?:at|during|in|from|on)\s+(?:(?:the|her|his|their|a|an)\s+)?'
    r'(?:previous|prior|past|earlier|last)\s+(?:visit|encounter|consultation|appointment)|'
    r'(?:before|prior\s+to)\s+(?:this|that|these|those|the\s+(?:current|recent|latest))\s+'
    r'(?:[^,;.!?\s]+\s+){0,5}?[^,;.!?\s]+(?=\s*[,;.!?]|\s+(?:he|she|they|the\s+patient)\b|$))', re.I)
_CURRENT = re.compile(r'\b(?:currently|now|today|at\s+present)\b', re.I)
_SECTION_WORDS = frozenset(('subjective objective assessment plan section soap note narrative of include includes '
    'the a an and or patient patients clinician clinicians documented reported symptoms symptom negatives '
    'positive negative pertinent current previous history complete all full observations observation examination '
    'physical exam findings finding measured test results result impression diagnosis clinical interpretation '
    'condition treatment investigations investigation referrals referral advice follow up followup '
    'name identity retaining retain preserving preserve qualifiers qualifier uncertainty negation '
    'at for this encounter visit as stated in source descriptive content only any is are kept relative '
    'text not converted into calendar date with their its scope from on use recorded such including').split())


def _span(text, start, end):
    return {'start': start, 'end': end, 'quote': text[start:end]}


def _domains(text):
    return {key for key, pattern in _DOMAINS.items() if re.search(pattern, text, re.I)}


def field_requirements(definition, *, contract=REQUIREMENTS_CONTRACT):
    """Record inclusion, exclusion and optionality with their exact evidence.

    Negation scopes over a coordinated content list, including articles. A
    prohibition on inference, registry substitution or omission is a source
    preservation rule, not a prohibition on documenting the clinical content.
    Unknown prose remains in the model; no unmatched tail grants a capability.
    """
    meaning = definition['meaning']
    clauses, requested, excluded, optional, excluded_scopes = [], set(), set(), set(), []
    for sentence in re.finditer(r'[^.;\r\n]+[.;]?', meaning):
        text = sentence[0].strip().rstrip('.;')
        offset = sentence.start() + len(sentence[0]) - len(sentence[0].lstrip())
        if not text:
            continue
        # A negative content tail has its own scope; it cannot reverse the
        # affirmative head or count as an additional request for its topics.
        splits = list(re.finditer(r'\b(?:not\s+(?:an?\s+)?(?:restatement|patient[- ]reported|assessment|impression|plan)|'
            r'(?:does?\s+not\s+include|excludes?|excluding|omits?|omitting|without|except(?:\s+for)?|apart\s+from)\b|'
            r'(?:with\s+)?no\s+(?!omission\b|exclusion\b)'
            r'(?:(?:an?\s+)?(?:assessment|impression|plan|diagnosis|subjective|objective|history|medication)\b)|'
            r'(?:do|must|should)\s+not\s+(?:include|record|document)\b)', text, re.I))
        protect_content = bool(re.match(r'\s*(?:do|must|should)\s+not\s+(?:omit|exclude|discard)\b', text, re.I))
        boundaries = [(m.start(),'excluded') for m in splits] if not protect_content else []
        boundaries += [(m.end(),'required') for m in re.finditer(r'\bbut\s+(?:also\s+)?',text,re.I)]
        start, role, pieces = 0, 'required', []
        for boundary, next_role in sorted(boundaries):
            if boundary > start:
                pieces.append((start,boundary,role))
            start, role = boundary, next_role
        pieces.append((start,len(text),role))
        passive = re.fullmatch(r'(?P<content>.+?)\s+(?:is|are|must\s+be|should\s+be|to\s+be)\s+'
            r'(?:excluded|omitted|not\s+(?:included|recorded|documented))'
            r'(?:\s+(?:from|in)\s+.+)?', text, re.I)
        if passive:
            # The destination in "assessment is excluded from Objective" is
            # an argument of the exclusion, not another excluded content head.
            pieces = [(passive.start('content'),passive.end('content'),'excluded'),
                (passive.end('content'),len(text),'preservation')]
        for low, high, role in pieces:
            fragment = text[low:high].strip(' ,')
            if not fragment:
                continue
            low += len(text[low:high])-len(text[low:high].lstrip(' ,'))
            if (re.search(r'\b(?:not\s+(?:required|needed)|optional|need\s+not)\b', fragment, re.I)
                    or re.fullmatch(r'no\s+.+?\s+(?:is\s+)?(?:required|needed)',fragment,re.I)):
                role = 'optional'
            if not protect_content and re.match(r'\s*(?:do\s+not\s+(?:infer|invent|add)|never\s+(?:infer|fill|substitute)|'
                    r'(?:use|include)\s+only\s+(?:the\s+)?(?:clinical\s+source|documented)|'
                    r'leave\s+undocumented|preserve\s+documented|retain\s+documented)\b', fragment, re.I):
                role = 'preservation'
            domains = _domains(fragment)
            clauses.append({'role': role, 'domains': sorted(domains),
                'evidence': _span(meaning, offset+low, offset+low+len(fragment))})
            if role == 'required': requested.update(domains)
            elif role == 'excluded':
                partial_medication = ('medication' in domains and re.search(
                    r'\b(?:stopped|discontinued|ceased|past|historical|prior|previous)\b', fragment, re.I))
                if partial_medication:
                    excluded_scopes.append({'domain':'medication', 'clinical_timing':'past',
                        'medicine_status':'discontinued', 'evidence':clauses[-1]['evidence']})
                excluded.update(domains-({'medication'} if partial_medication else set()))
            elif role == 'optional': optional.update(domains)
    # The leading section/topic is independent of exclusions naming that topic
    # elsewhere. A conflict is explicit rather than silently selecting a side.
    primary = next((name for name in ('subjective','objective','assessment','plan')
        if re.match(r'\s*'+name+r'\b', meaning, re.I)), None)
    if primary:
        requested.add(primary)
    # A complete generic section declaration supplies broad section scope.
    # Unconsumed clinical topics (urinary, chest, swallowing, a drug, etc.)
    # make it a narrow/unknown destination; vocabulary resemblance cannot
    # grant broad permission. Narrow typed readers below retain authority.
    positive_text = ' '.join(clause['evidence']['quote'] for clause in clauses if clause['role'] == 'required')
    words = set(re.findall(r'[^\W\d_]+', positive_text.casefold().replace('’s','s').replace("'s",'s')))
    broad = ([primary] if primary and primary not in excluded and words <= _SECTION_WORDS else [])
    polarity = definition['scope']['polarity']
    allowed_polarities = ['affirmed','negated','uncertain','mixed'] if polarity == 'any' else [
        'affirmed' if polarity == 'positive' else 'negated']
    for word, literal in (('positive','affirmed'),('negative','negated')):
        if re.search(r'\b(?:only\s+'+word+r'|'+word+r'(?:\s+(?:findings|observations|symptoms))?\s+only)\b',positive_text,re.I):
            allowed_polarities = [literal]
            broad = []
    result = {'contract': REQUIREMENTS_CONTRACT,
        'definition_sha256': hashlib.sha256(json.dumps(definition, sort_keys=True,
            ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
        'scope': deepcopy(definition['scope']), 'answer_mode': definition.get('answer_mode','atomic'),
        'value_type': definition['value_type'], 'primary_domain': primary,
        'required_domains': sorted(requested-excluded-optional), 'excluded_domains': sorted(excluded),
        'excluded_scopes': excluded_scopes,
        'optional_domains': sorted(optional), 'conflicting_domains': sorted(requested & excluded),
        'broad_sections': broad, 'unconsumed_topic_words': sorted(words-_SECTION_WORDS),
        'coverage_mode': ('section' if primary and primary not in excluded and words <= _SECTION_WORDS
            else 'typed_components'),
        'allowed_fact_polarities': allowed_polarities,
        'clauses': clauses}
    if contract != REQUIREMENTS_CONTRACT:
        from .clinical_field_scope import CONTRACT as current, compile_requirements
        if contract != current:
            raise ValueError('Unknown approved field requirements contract.')
        return compile_requirements(definition, result)
    return result


def conditional_instruction(text, section):
    """Separate a conditional future action from its hypothetical antecedent.

    The entire instruction must survive as one source value. This classifies
    grammatical action/modality, never the medical truth of the condition.
    """
    if section != 'plan' or not re.search(r'\b(?:if|unless|when)\b', text, re.I):
        return False
    # Explicit deontic modal + action: arbitrary clinical objects are retained,
    # while nested asserted diagnoses, attribution and record retractions do
    # not acquire an instruction exemption.
    action = re.search(r'\b(?:he|she|they|the\s+patient)\s+(?:should|must|is\s+advised\s+to|was\s+asked\s+to)\s+'
        r'(?:contact|call|return|seek|attend|arrange|continue|stop|take|avoid|report|notify|go)\b', text, re.I)
    scheduled = re.match(r'\s*(?:follow[- ]?up|review|return|contact)\b', text, re.I) and re.search(
        r'\b(?:(?:is|was)\s+(?:planned|scheduled|arranged|recommended|requested)|in|after|within|before)\b', text, re.I)
    if action is None and not scheduled:
        return False
    return not re.search(r'[“”"]|\b(?:reported|allegedly|hypothetical|suppose|imagine|copied|invalid|retracted|withdrawn)\b', text, re.I)


def _subject_reference(text):
    """An account reference must be a nominal subject, not a predicate object."""
    from .clinical_source_context import account_reference
    reference = account_reference(text)
    if reference is None:
        return None
    prefix = text[:reference['start']]
    directive = re.search(r'\b(?:disregard|ignore|do\s+not\s+use)\s*$', prefix, re.I)
    if not directive and (not reference['predicate'] or re.search(
            r'\b(?:describes?|represents?|includes?|excludes?|is|are|was|were|spent|lasts?|belongs?|refers?)\b', prefix, re.I)):
        return None
    return reference


def bare_patient_identity(text):
    """The complete named patient predicate already accepted by identity proof.

    No demographics or extraction annotation supplies this source identity.
    Titles, relatives and named clinicians cannot open a bare patient frame.
    """
    match = re.fullmatch(r"(?P<name>.+?)\s+"
        r'(?:reports?|reported|presents?|presented|attended|attends|visited|visits|'
        r'arrived|arrives|came|comes|rates|rated|states|stated|requests?|requested|'
        r'(?:is|was)\s+(?=(?:the|this)\s+patient\b|referred\b|born\b|\d+\s+years?\s+old\b))\b[^\r\n]+', text)
    if match is None:
        return None
    if match['name'].split()[0].casefold() in {'he','she','they','it','i','we','you','the','this','that','these','those','patient'}:
        return None
    from .semantic_generation import person_name_value
    if not person_name_value(match['name']):
        return None
    from .clinical_source_context import PERSON
    if re.search(r'\b(?:'+PERSON+r'|Dr|Doctor|Prof|Professor|clinician|physician)\b', match['name'], re.I):
        return None
    return {'name': match['name'], 'current': False}


def source_context(notes, units, *, time_exclusion_contract=None, record_identity=None):
    from . import clinical_source_context as prior
    context = prior.source_context(notes, units, profile=prior.SOAP_ASSERTION_PROFILE,
        identity_contract=CONTEXT_PROFILE, time_exclusion_contract=time_exclusion_contract,
        record_identity=record_identity)
    # Recompute account findings against real subject/predicate relationships.
    # The historical reader searched references inside predicate objects too.
    for row in context['units'].values():
        row['issues'] = [issue for issue in row['issues'] if issue != _RETRACTION]
    findings = []
    previous_row = None
    first_identity = min((unit['start'] for unit in units if re.fullmatch(prior.PATIENT_IDENTITY_HEADING,
        unit['quote'].strip(), re.I) or bare_patient_identity(unit['quote'].strip())), default=len(notes))
    for index, unit in enumerate(units):
        row = context['units'][unit['start']]
        if conditional_instruction(unit['quote'], row['section']):
            row['issues'] = [issue for issue in row['issues']
                if issue != 'Quoted or hypothetical source is not a current patient assertion.']
        whole = prior._whole_account_governance(unit['quote'])
        local_retraction = re.search(r'\b(?:this|that|it|the\s+(?:preceding|above)\s+statement)\s+'
            r'(?:is|was|has\s+been|may\s+be|might\s+be|could\s+be)\s+(?:(?:recorded|documented|entered)\s+)?'
            r'(?:in\s+error|incorrect(?:ly)?|wrong(?:ly)?|erroneous(?:ly)?|invalid|inaccurate|unverified|retracted|withdrawn|'
            r'(?:for|about)\s+(?:another|a\s+different)\s+patient)\b', unit['quote'], re.I)
        # A reassignment changes its own row's owner. It still governs the
        # account owned immediately before that statement; a foreign/past
        # section cannot acquire current-patient authority this way.
        inherited_current = (previous_row is not None and previous_row['subject'] == 'patient'
            and previous_row['section_timing'] == 'current')
        pre_identity = (unit['start'] < first_identity and context.get('patient_name') is not None
            and (previous_row is None or previous_row['subject'] != 'foreign'
                and previous_row['section_timing'] == 'current'))
        previous_row = row
        if not (row['subject'] == 'patient' and row['section_timing'] == 'current'
                or (whole or local_retraction) and (inherited_current or pre_identity)):
            continue
        if local_retraction:
            row['issues'].append(_RETRACTION)
            target_ids = [unit['id']]
            if index and not unit['quote'][:local_retraction.start()].strip():
                previous_unit = units[index-1]
                previous = context['units'][previous_unit['start']]
                gap = notes[previous_unit['end']:unit['start']]
                if (not gap.strip() and not re.search(r'\r?\n\s*\r?\n',gap)
                        and previous['subject'] == 'patient' and previous['section_timing'] == 'current'
                        and previous['section'] == row['section']):
                    previous['issues'].append(_RETRACTION)
                    target_ids.append(previous_unit['id'])
            findings.append({'kind':'source_assertion_retraction', 'domains':['clinical'],
                'subject':'patient', 'encounter_timing':'current', 'target_unit_ids':target_ids,
                'source_evidence':_span(notes,unit['start']+local_retraction.start(),unit['start']+local_retraction.end())})
        references = []
        if whole and not whole['integrity']:
            references.append(({'all'}, whole['direction']))
        for clause in prior.account_clauses(unit['quote']):
            ref = _subject_reference(clause)
            if ref is None or not ref['current_owned']:
                continue
            domains = prior._retracted_clause_domains(clause, {'assessment','time'}, profile=prior.SOAP_ASSERTION_PROFILE,
                time_exclusion_contract=time_exclusion_contract)
            if domains:
                references.append((domains, 'before' if re.search(r'\b(?:above|preceding)\b', clause, re.I) else 'all'))
        for domains, direction in references:
            targets = []
            local_list = (direction == 'after' and unit['quote'].rstrip().endswith(':')
                and re.search(r'\b(?:findings|assertions|statements)\b', unit['quote'], re.I)
                and not re.search(r'\b(?:record|note|account|documentation|entire|whole)\b', unit['quote'], re.I))
            next_section = min((other['start'] for other in units if other['start'] > unit['start']
                and re.fullmatch(r'\s*(?:[SOAP]\s*[-–:]\s*)?(?:[SOAP]|Subjective|Objective|Assessment|Plan)\s*:?',
                    other['quote'])), default=len(notes)) if local_list else len(notes)
            for other in units:
                target = context['units'][other['start']]
                if target['subject'] != 'patient' or target['section_timing'] != 'current':
                    continue
                if direction == 'before' and other['start'] >= unit['start'] or direction == 'after' and other['start'] <= unit['start']:
                    continue
                if local_list and other['start'] >= next_section:
                    continue
                target_domain = _SECTION_DOMAIN.get(target['section'])
                time_account = bool(re.search(r'\b(?:physician|clinician|total)\s+time\b|\b(?:Dr\.?|Doctor)\s+.+\bspent\b', other['quote'], re.I))
                if ('all' in domains or 'clinical' in domains and target_domain
                        or 'assessment' in domains and target_domain == 'assessment'
                        or 'time' in domains and time_account):
                    target['issues'].append(_RETRACTION)
                    targets.append(other['id'])
            findings.append({'kind': 'source_account_governance', 'domains': sorted(domains),
                'subject': 'patient', 'encounter_timing': 'current', 'target_unit_ids': targets,
                'source_evidence': {k: unit[k] for k in ('start','end','quote')}})
    context.update(profile=CONTEXT_PROFILE, findings=findings)
    return context


def current_document_identity(text, source_name):
    """Bind the visible name to its actual role in the current saved document.

    The record owner comes only from a separately validated source identity.
    It supplies no document text or name occurrence. Literal name slots and
    complete patient predicates must still have current patient ownership;
    negation, another beneficiary, prior sections and retractions remain holds.
    """
    from .generation import source_units
    from .semantic_generation import _complete_patient_identity
    units, _ = source_units(text, [])
    context = source_context(text, units, record_identity=source_name)
    result = {'contract': 'current-saved-name-assertions-v1',
        'document_sha256': hashlib.sha256(text.encode()).hexdigest(),
        'source_name': source_name, 'assertions': [], 'issues': list(context['issues'])}
    pattern = r"(?<![\w'’\-])" + re.escape(source_name) + r"(?![\w'’\-])"
    for match in re.finditer(pattern, text):
        unit = next(unit for unit in units if unit['start'] <= match.start() < match.end() <= unit['end'])
        row = context['units'][unit['start']]
        evidence = _span(text, match.start(), match.end())
        issues = list(row['issues'])
        if row['subject'] != 'patient' or row['section_timing'] != 'current' or row['timing'] != 'current':
            issues.append('The visible name is not an assertion of the current patient identity.')
        # Narrative renderers may separate independently selected literal values
        # with semicolons. Keep the full unit for governance, while checking the
        # name's own complete slot/predicate without joining unrelated clauses.
        left = text.rfind(';', unit['start'], match.start()) + 1
        left = max(left, unit['start'])
        right = text.find(';', match.end(), unit['end'])
        right = unit['end'] if right < 0 else right
        clause = text[left:right]
        local_name = {'start': match.start()-left, 'end': match.end()-left, 'quote': source_name}
        standalone = bool(re.fullmatch(r'(?:Name\s*:\s*)?'+re.escape(source_name)+r'\.?',
            clause.strip(), re.I))
        named_report = bool(not clause[:local_name['start']].strip() and re.match(
            r'\s+(?:denies|endorses)\s+(?!being\b|identity\b|(?:the\s+)?patient\b|name\b).+',
            clause[local_name['end']:],re.I))
        if not standalone and not named_report and not _complete_patient_identity(clause, {'value_evidence':local_name}):
            issues.append('The visible name has no complete affirmative patient-identity slot or predicate.')
        proposed = {'value_evidence': evidence, 'polarity':'affirmed',
            'kind':'identity', 'subject':{'kind':'patient'}}
        issues.extend(local_fact_issues(proposed, units))
        assertion = {'name_evidence': evidence, 'source_unit_evidence': {k:unit[k] for k in ('start','end','quote')},
            'subject': row['subject'], 'encounter_timing': row['section_timing'],
            'polarity':'affirmed' if not issues else 'unresolved', 'issues':list(dict.fromkeys(issues))}
        result['assertions'].append(assertion)
        result['issues'].extend(issues)
    if not result['assertions']:
        result['issues'].append('The complete source patient name is absent from the current saved document.')
    # An identity-specific correction may omit the name it corrects. Unknown
    # predicates on the current record's name/identity cannot be waived by a
    # separate valid name slot elsewhere in the answer.
    identity_head = (r'(?:(?:the\s+)?patient(?:[\x27’]s)?(?:\s+full)?\s+(?:name|identity)|'
        r'(?:(?:the|this|that|documented|recorded)\s+)?(?:name|identity))')
    for unit in units:
        row = context['units'][unit['start']]
        if row['subject'] != 'patient' or row['section_timing'] != 'current':
            continue
        for clause in re.split(r';\s*', unit['quote']):
            if not re.match(r'\s*'+identity_head+r'\s+(?:is|was|remains?|has|may|might|could)\b', clause, re.I):
                continue
            literal_slot = bool(re.fullmatch(identity_head+r'\s+is\s+'+re.escape(source_name)+r'\.?',clause.strip(),re.I))
            integrity = bool(re.fullmatch(identity_head+r'\s+(?:is|was|remains?)\s+'
                r'(?:correct|confirmed|verified|not\s+(?:incorrect|wrong|erroneous|retracted|withdrawn))\.?',
                clause.strip(), re.I))
            if not literal_slot and not integrity:
                result['issues'].append('The current saved document has an unresolved identity qualification: '+clause)
    result['issues'] = list(dict.fromkeys(result['issues']))
    return result


def assertion_frames(notes, units, context=None, *, requirements_contract=REQUIREMENTS_CONTRACT):
    context = context or source_context(notes, units)
    rows = []
    for unit in units:
        row = context['units'][unit['start']]
        text = unit['quote']
        conditional = conditional_instruction(text, row['section'])
        time_account = bool(re.search(r'\b(?:physician|clinician)\s+(?:time|record\s+review)|'
            r'\b(?:Dr\.?|Doctor)\s+.+?\bspent\s+.+?\bminutes\b|\bE\s*/\s*M\b|'
            r'\b(?:staff\s+intake|separately\s+(?:billed|reported)\s+(?:work|services?))\b', text, re.I))
        actor = 'clinician' if time_account and re.search(r'\b(?:physician|clinician|Dr\.?|Doctor)\b',text,re.I) else None
        clinical_timing = 'past' if _PAST.search(text) and not _CURRENT.search(text) else row['timing']
        time_issues = []
        if time_account:
            from .clinical_source_context import source_date
            dated = re.search(r'\bspent\s+.+?\bminutes\s+on\s+(?P<date>.+?)(?=\s*[:;]|$)',text,re.I)
            if dated:
                day = source_date(dated['date'].rstrip(' .'))
                service_day = context.get('service_date')
                if day is None or service_day is None:
                    time_issues.append('The physician-time assertion lacks a complete, bound source service date.')
                elif day != service_day:
                    clinical_timing = 'past' if day < service_day else 'future'
        rows.append({'source_unit_id': unit['id'], 'source_evidence': {k: unit[k] for k in ('start','end','quote')},
            'subject': row['subject'], 'encounter_timing': row['section_timing'],
            'clinical_timing': clinical_timing, 'actor': actor, 'time_account': time_account,
            'account_clinician': (context['clinicians'][0]['name'] if time_account
                and len(context['clinicians']) == 1 else None),
            'section': row['section'], 'domain': _SECTION_DOMAIN.get(row['section']),
            'negative_evidence': [_span(notes, unit['start']+m.start(), unit['start']+m.end()) for m in _NEGATIVE.finditer(text)],
            'uncertainty_evidence': [_span(notes, unit['start']+m.start(), unit['start']+m.end()) for m in _UNCERTAIN.finditer(text)],
            'temporal_qualifiers': [_span(notes, unit['start']+m.start(), unit['start']+m.end()) for m in _PAST.finditer(text)],
            'conditional_instruction': conditional,
            'governance_findings': [deepcopy(finding) for finding in context['findings']
                if unit['id'] in finding['target_unit_ids']],
            'issues': list(dict.fromkeys(row['issues']+time_issues))})
    if requirements_contract != REQUIREMENTS_CONTRACT:
        from .clinical_field_scope import CONTRACT as current, source_roles
        if requirements_contract != current:
            raise ValueError('Unknown approved field requirements contract.')
        return source_roles(notes, rows, context)
    return rows


def local_fact_issues(fact, contexts):
    """Local polarity/modality and literal qualifiers; no whole-note veto."""
    value = fact['value_evidence']
    own = next(c for c in contexts if c['start'] <= value['start'] < value['end'] <= c['end'])
    before = own['quote'][:value['start']-own['start']]
    clause = re.split(r';|\b(?:but|whereas|while)\b|\band\s+(?=(?:he|she|they|the\s+patient|reports?|denies?|has|have|is|are)\b)', before, flags=re.I)[-1]
    selected = value['quote']
    if re.search(r'\band\s*$',before,re.I) and re.match(r'\s*(?:reports?|has|have|is|are)\b',selected,re.I):
        clause = ''
    relevant = clause + selected
    negative = bool(_NEGATIVE.search(relevant))
    # A negative qualifier does not negate its affirmative predicate (pain
    # without radiation, soft without guarding). A selected embedded object
    # still inherits the preceding denial that governs it.
    negative_head = bool(re.match(r'\s*(?:(?:he|she|they|the\s+patient|there)\s+)?'
        r'(?:(?:has|have|had|does|did|is|are|was|were)\s+)?'
        r'(?:no|not|never|neither|nothing|denies?|denied|without)\b', selected, re.I))
    inherited_negative = bool(_NEGATIVE.search(clause) and not re.search(
        r'\b(?:he|she|they|the\s+patient)\s+(?:has|have|had|is|are|reports?)\b', selected, re.I))
    from .clinical_assertions import calendar_mask
    uncertain = bool(_UNCERTAIN.search(calendar_mask(relevant)))
    negative_head = negative_head or bool(re.match(r'\s*(?:(?!\b(?:because|and|or|but|if|although|though|when)\b)[^,;.!?]){1,120}?\b'
        r'(?:is|are|was|were|has|have|had|does|do|did)\s+(?:not|no|never)\b', selected, re.I))
    reported_negative = bool(re.match(r'\s*(?:(?!\b(?:because|and|or|but|if|although|though|when)\b)[^,;.!?]){1,120}?\b'
        r'(?:reports?|reported|describes?|described|notes?|noted|states?|stated)\s+'
        r'(?:no|not|never|(?:(?:an?|the)\s+)?absence\s+of)\b',selected,re.I))
    passive_negative = bool(re.match(r'\s*(?:(?!\b(?:because|and|or|but|if|although|though|when)\b)[^,;.!?]){1,120}?\b'
        r'(?:is|are|was|were|has\s+been|have\s+been)\s+(?:reportedly\s+)?(?:absent|denied)\b',selected,re.I))
    negative_head = negative_head or reported_negative or passive_negative
    issues = []
    if (negative_head or inherited_negative) and fact['polarity'] == 'affirmed':
        issues.append('The source contains a local negation not preserved by this fact.')
    if not negative and fact['polarity'] in ('negated','mixed'):
        issues.append('The proposed negation is not explicitly grounded in its source clause.')
    if uncertain and fact['polarity'] not in ('uncertain','mixed'):
        issues.append('The source contains uncertainty not preserved by this fact.')
    if fact['polarity'] == 'uncertain' and not uncertain:
        issues.append('The proposed uncertainty is not explicitly grounded in its source clause.')
    if re.search(r'\b(?:not\s+deny|not\s+without|never\s+denies?|does\s+not\s+report)\b', relevant, re.I):
        issues.append('Nested reporting or negation requires explicit source interpretation.')
    if fact['subject']['kind'] == 'uncertain':
        issues.append('The subject is unresolved.')
    if not re.fullmatch(r'[\d.]+', selected) and fact['kind'] in ('reason','finding','history','assessment'):
        qualifier = r'(?:left|right|bilateral|unilateral|mild|moderate|severe|slight|marked|acute|chronic|distal|proximal|lateral|medial|anterior|posterior|upper|lower)'
        if re.search(r'\b'+qualifier+r'(?:\s+[^\W\d_]+){0,5}\s+$', clause, re.I):
            issues.append('The selected value omits an adjacent documented clinical qualifier.')
    return issues


def validate_source_facts(notes, units, facts):
    context = source_context(notes, units)
    frames = {row['source_unit_id']: row for row in assertion_frames(notes, units, context)}
    for fact in facts.values():
        value = fact['value_evidence']
        own = next(unit for unit in units if unit['start'] <= value['start'] < value['end'] <= unit['end'])
        frame = frames[own['id']]
        fact['source_assertion'] = deepcopy(frame)
        fact['issues'].extend(frame['issues'])
        for finding in frame['governance_findings']:
            evidence = finding['source_evidence']
            if evidence not in fact['evidence']:
                fact['evidence'].append(deepcopy(evidence))
        if frame['subject'] != 'patient' and fact['subject']['kind'] == 'patient':
            fact['issues'].append('The positioned source does not establish this patient as the assertion owner.')
        if frame['domain'] == 'plan':
            from .clinical_source_context import PERSON
            if re.search(r"\b(?:for|to|on)\s+(?:(?:her|his|their|the\s+patient['’]s)\s+"
                    +PERSON+r'|(?:another|different|other)\s+patient)\b', own['quote'], re.I):
                fact['issues'].append('The planned action explicitly names another beneficiary; it is not a patient-owned instruction.')
        if fact['subject']['kind'] == 'clinician':
            from .clinical_source_context import source_clinician_bound, clinician_matches
            if (not source_clinician_bound(context, own['quote'])
                    or fact['subject'].get('name_evidence') and not clinician_matches(context, fact['subject']['name_evidence']['quote'])):
                fact['issues'].append('The source does not bind this assertion to the documented treating clinician.')
        if frame['encounter_timing'] != 'current' and fact['timing']['kind'] != frame['encounter_timing']:
            fact['issues'].append('The assertion belongs to a different encounter time.')
        if frame['clinical_timing'] in ('past','future') and fact['timing']['kind'] == 'current':
            fact['issues'].append('A non-current source assertion was presented as current.')
        if frame['conditional_instruction']:
            # A complete conditional instruction is affirmed future advice.
            # An embedded condition remains hypothetical and cannot be a finding.
            full = value['quote'].strip().rstrip('.') == own['quote'].strip().rstrip('.')
            if not full or fact['kind'] not in ('plan','follow_up') or fact['timing']['kind'] != 'future':
                fact['issues'].append('A conditional instruction must retain its complete condition and future action; it cannot assert a present finding.')
            else:
                fact['issues'] = [issue for issue in fact['issues'] if issue in frame['issues'] or issue not in (
                    'The source contains uncertainty not preserved by this fact.',
                    'The proposed uncertainty is not explicitly grounded in its source clause.')]
        elif re.search(r'\b(?:if|unless|suppose|imagine|hypothetical)\b', own['quote'], re.I):
            fact['issues'].append('Conditional or hypothetical source is not an established current finding.')
        name = fact['subject'].get('name_evidence')
        if fact['subject']['kind'] == 'patient' and name and name['quote'].casefold() != (context['patient_name'] or '').casefold():
            fact['issues'].append('The fact names a different or unresolved source patient.')
        fact['issues'] = list(dict.fromkeys(fact['issues']))
    return context


def _eligible_domains(requirements, frame):
    # A narrow/unknown meaning cannot acquire every assertion in a coarse SOAP
    # domain. Its existing typed component proofs remain independent below.
    if requirements['coverage_mode'] != 'section':
        return False
    if requirements['contract'] != REQUIREMENTS_CONTRACT:
        from .clinical_field_scope import required
        return required(requirements, frame)
    domains = set(requirements['required_domains'])
    primary = requirements['primary_domain']
    if primary:
        return frame['domain'] == primary
    if frame['domain'] in domains:
        return True
    return (frame['domain'] == 'subjective' and bool(domains & {'history','medication'})
        or frame['domain'] == 'plan' and bool(domains & {'investigation','medication','time'}))


def temporal_projection(notes, definition, fact):
    """Restore only a leading temporal adjunct on one complete literal body.

    The provider's selected value and annotations remain immutable. Expansion
    cannot cross an assertion boundary, add a missing predicate or change the
    source owner, time or modality. Atomic destinations never use projections.
    """
    frame = fact.get('source_assertion') or {}
    if (definition.get('answer_mode') != 'narrative' or definition['value_type'] != 'text'
            or fact['issues'] or frame.get('issues') or frame.get('subject') != 'patient'
            or frame.get('encounter_timing') != 'current' or frame.get('clinical_timing') != 'past'
            or fact['timing']['kind'] != 'past' or fact['kind'] == 'identity'):
        return None
    source, value = frame['source_evidence'], fact['value_evidence']
    qualifiers = frame['temporal_qualifiers']
    if len(qualifiers) != 1 or qualifiers[0]['start'] != source['start']:
        return None
    qualifier = qualifiers[0]
    if not (qualifier['end'] < value['start'] < value['end'] <= source['end']):
        return None
    if not re.fullmatch(r'[\s,]*', notes[qualifier['end']:value['start']]):
        return None
    if not re.fullmatch(r'[\s.!?]*', notes[value['end']:source['end']]):
        return None
    projected = _span(notes, source['start'], value['end'])
    return {'contract':'source-temporal-projection-v1', 'fact_id':fact['id'],
        'source_sha256':hashlib.sha256(notes.encode()).hexdigest(),
        'definition_sha256':field_requirements(definition)['definition_sha256'],
        'raw_value_evidence':deepcopy(value), 'temporal_evidence':deepcopy(qualifier),
        'rendered_evidence':projected, 'rendered_value':' '.join(projected['quote'].split())}


def assignment_issues(notes, definition, picked, units, context, *, requirements_contract=REQUIREMENTS_CONTRACT):
    requirements = field_requirements(definition, contract=requirements_contract)
    current = requirements_contract != REQUIREMENTS_CONTRACT
    if definition.get('answer_mode') != 'narrative' or definition['value_type'] != 'text':
        return []
    issues = []
    if requirements['conflicting_domains']:
        issues.append('The approved meaning contains conflicting inclusion and exclusion requirements; clarify its complete scope.')
    frames = assertion_frames(notes, units, context, requirements_contract=requirements_contract)
    from . import semantic_generation as semantic
    typed_obligations = []
    if requirements['coverage_mode'] == 'typed_components':
        typed_definition = definition
        if requirements['primary_domain'] == 'plan' and definition['scope']['temporality'] == 'future':
            typed_definition = {**definition, 'scope':{**definition['scope'],'temporality':'current'}}
        typed_obligations = (semantic._source_governance_inventory(notes, {'destination':definition},
            semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT)
            + semantic._clinical_context_inventory(notes, {'destination':typed_definition},
                scope_contract=semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT))
    for fact in picked:
        frame = fact.get('source_assertion')
        if not frame:
            continue
        if current:
            frame = next(item for item in frames if item['source_unit_id'] == frame['source_unit_id'])
        if fact['polarity'] not in requirements['allowed_fact_polarities']:
            issues.append('The selected assertion polarity is excluded by the complete approved field meaning.')
        # A model's affirmative annotation cannot erase a negative examination
        # predicate inside the selected literal (soft and nontender; soft
        # without guarding). This is a destination restriction, not a denial of
        # the entire observation: an unrestricted examination keeps it intact.
        value = fact['value_evidence']
        if (requirements['allowed_fact_polarities'] == ['affirmed'] and frame['domain'] == 'objective'
                and any(value['start'] <= negative['start'] < negative['end'] <= value['end']
                    for negative in frame['negative_evidence'])):
            issues.append('The selected examination assertion contains a documented negative predicate excluded by this positive-only field meaning.')
        outside = (requirements['coverage_mode'] == 'section' and not _eligible_domains(requirements, frame)
            and fact['kind'] != 'identity')
        if current:
            if requirements['strict_content_scope'] and fact['kind'] == 'identity' and not _eligible_domains(requirements, frame):
                outside = True
            outside = outside and frame['domain'] not in requirements['allowed_context_sections']
            from .clinical_field_scope import exclusion_spans
            literal_exclusions = [span for span in exclusion_spans(requirements, frame['source_evidence'])
                if span['resolution'] == 'excluded']
            if (set(frame['content_roles']) & set(requirements['excluded_groups'])
                    or any(span['start'] < fact['value_evidence']['end'] and fact['value_evidence']['start'] < span['end']
                        for span in literal_exclusions)):
                issues.append('The selected assertion contains content explicitly excluded by the complete approved field meaning.')
        if frame['domain'] in requirements['excluded_domains'] or outside:
            issues.append('The selected assertion is outside the complete approved field requirements.')
        own = next(unit for unit in units if unit['id'] == frame['source_unit_id'])
        nonuse = bool(re.search(r'\b(?:no\s+longer\s+(?:taking|using)|not\s+(?:taking|using)|stopped|discontinued)\b', own['quote'], re.I))
        if requirements['excluded_scopes'] and nonuse:
            issues.append('The approved current-medicine destination excludes this discontinued therapy and its non-use statement.')
        objects = semantic._scoped_denial_objects(fact, own, semantic.SOAP_ASSERTION_SCOPE_CONTRACT)
        typed_permission = bool(objects is not None and semantic._denial_destination(
            definition, objects, scope_contract=semantic.SOAP_ASSERTION_SCOPE_CONTRACT))
        if objects is not None and 'subjective' not in requirements['broad_sections'] and not semantic._denial_destination(
                definition, objects, scope_contract=semantic.SOAP_ASSERTION_SCOPE_CONTRACT):
            issues.append('The complete approved meaning does not authorize these reported negative topics; narrow or unknown topics cannot grant broad symptom scope.')
        stable = semantic._stable_state_frame(own['quote'])
        typed_permission = typed_permission or bool(stable and semantic._stable_state_destination(
            definition, stable['objects'], complete=True))
        if stable and 'subjective' not in requirements['broad_sections'] and not semantic._stable_state_destination(
                definition, stable['objects'], complete=True):
            issues.append('The complete approved meaning does not authorize the selected stable-state topic.')
        if fact['polarity'] == 'mixed' and frame['domain'] == 'objective' and 'objective' not in requirements['broad_sections']:
            if (not semantic._mixed_observation_destination(definition, scope_contract=semantic.SOAP_ASSERTION_SCOPE_CONTRACT)
                    or not semantic._observation_matches_destination(own['quote'], definition, semantic.SOAP_ASSERTION_SCOPE_CONTRACT)):
                issues.append('The complete mixed observation requires a matching unrestricted examination destination.')
            else:
                typed_permission = True
        historical_medicine_with_current_nonuse = semantic._destination_contracts(
            semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT).historical_medicine_with_current_nonuse
        typed_permission = typed_permission or bool((semantic._historical_cessation_destination(definition)
            or historical_medicine_with_current_nonuse(definition)) and 'medication' in requirements['required_domains'])
        value = fact['value_evidence']
        typed_permission = typed_permission or any(
            obligation['source']['start'] <= value['start'] < value['end'] <= obligation['source']['end']
            and semantic._clinical_context_covered(notes, obligation, picked, context)
            for obligation in typed_obligations)
        if requirements['coverage_mode'] == 'typed_components' and not typed_permission:
            issues.append('The current answer definition does not establish a verified scope for this narrative assertion. '
                'Review explicit components against the original question before using it.')
        # A temporal qualifier cited only as metadata still must be visible.
        value = fact['value_evidence']
        projection = temporal_projection(notes, definition, fact)
        if projection is not None:
            value = projection['rendered_evidence']
        for qualifier in frame['temporal_qualifiers']:
            if not (value['start'] <= qualifier['start'] and qualifier['end'] <= value['end']):
                issues.append('The narrative value omits its source temporal qualifier: '+qualifier['quote'])
    obligation_frames = frames
    if current:
        from .clinical_field_scope import obligation_frames as scoped_obligations
        obligation_frames = scoped_obligations(requirements, frames)
    for frame in obligation_frames:
        if current:
            from .clinical_field_scope import applicable
            if not applicable(requirements, frame):
                continue
            if frame.get('source_polarity') == 'unresolved':
                if (_eligible_domains(requirements, frame)
                        or 'reported_symptoms' in requirements['required_groups']
                        and 'unclassified_subjective' in frame['content_roles']):
                    issues.append('The source predicate polarity cannot be independently partitioned for the '
                        'complete approved field scope; review this assertion without discarding its qualifiers: '
                        + frame['source_evidence']['quote'])
                continue
        if (current and (frame['domain'] == requirements['primary_domain']
                or frame['domain'] in requirements['required_domains'])
                and frame['subject'] == 'patient' and frame['encounter_timing'] == 'current'):
            issues.extend(frame.get('relation_findings', []))
        if (current and 'reported_symptoms' in requirements['required_groups']
                and 'unclassified_subjective' in frame['content_roles'] and not frame['issues']):
            from .clinical_assertions_v4 import soap_heading
            heading = frame['source_evidence']['quote'].strip().rstrip('.:')
            source = frame['source_evidence']
            spans = [(projection['rendered_evidence'] if (projection:=temporal_projection(notes, definition, fact)) else fact['value_evidence'])
                for fact in picked if fact['value_evidence']['start'] < source['end']
                and fact['value_evidence']['end'] > source['start']]
            incomplete = any(not any(span['start'] <= source['start']+word.start()
                and source['start']+word.end() <= span['end'] for span in spans)
                for word in re.finditer(r"[\w]+(?:['’][\w]+)?",source['quote']))
            if (not soap_heading(heading) and not re.fullmatch(
                    r'(?:[SOAP]\s*[-–:]\s*)?(?:Subjective|History|Objective|Assessment|Plan|Review of systems)',heading,re.I) and incomplete):
                issues.append('The source role is unresolved for this approved reported-symptom requirement; review its scope: '
                    + frame['source_evidence']['quote'])
        if not _eligible_domains(requirements, frame) or frame['issues']:
            continue
        source = frame['source_evidence']
        if current:
            from .clinical_field_scope import exclusion_spans
            for span in exclusion_spans(requirements, source):
                if span['resolution'] == 'requires_review':
                    issues.append('A source expression may match content explicitly excluded by the '
                        'complete approved meaning; its polarity or attribute/head interpretation remains unresolved: '
                        + source['quote'] + ' Exclusion: ' + span['exclusion_evidence']['quote'])
        if current and set(requirements['required_groups']) & set(frame['content_roles']) == {'patient_name'}:
            source = frame['content_evidence']['patient_name']
        text = source['quote'].strip().rstrip('.:')
        from .clinical_assertions_v4 import soap_heading
        if (soap_heading(text) or re.fullmatch(r'(?:[SOAP]\s*[-–:]\s*)?(?:Subjective|History|Objective|Assessment|Plan|Review of systems)', text, re.I)):
            continue
        present = [fact for fact in picked if fact['value_evidence']['start'] < source['end']
            and fact['value_evidence']['end'] > source['start']]
        spans = [(projection['rendered_evidence'] if (projection:=temporal_projection(notes, definition, fact)) else fact['value_evidence']) for fact in present
            if current or not fact['issues']]
        if not spans:
            issues.append('The answer omits a documented assertion required by the complete field meaning: '+source['quote'])
            continue
        # Complete source coverage may use several extracted facts. Function
        # words can be grammatical scaffolding; content and timing cannot.
        omitted = []
        exclusions = []
        if current:
            from .clinical_field_scope import exclusion_spans
            exclusions = [span for span in exclusion_spans(requirements, source) if span['resolution'] == 'excluded']
        for word in re.finditer(r"[\w]+(?:['’][\w]+)?", source['quote']):
            start, end = source['start']+word.start(), source['start']+word.end()
            if any(span['start'] <= start and end <= span['end'] for span in spans):
                continue
            if any(span['start'] <= start and end <= span['end'] for span in exclusions):
                continue
            scaffolding = {'he','she','they','it','his','her','their','the','a','an','is','are','was','were','and','or','but', 'patient'}
            if current:
                scaffolding |= {'with'}
            if word[0].casefold() not in scaffolding:
                omitted.append(word[0])
        if omitted:
            issues.append('The answer omits part of a source assertion or qualifier required by the complete field meaning: '+source['quote'])
        elif current and any(fact['issues'] for fact in present):
            causes = list(dict.fromkeys(issue for fact in present for issue in fact['issues']))
            issues.append('The required source assertion is present in the selected text but remains held: '
                + source['quote'] + ' Causes: ' + '; '.join(causes))
    # A narrow historical medicine field can explicitly request a present
    # non-use attribute. Retain the existing typed antecedent/date/completeness
    # proof; a generic medication mention cannot grant that scope.
    if 'medication' in requirements['required_domains'] and not requirements['broad_sections']:
        from . import semantic_generation as semantic
        for obligation in semantic._source_governance_inventory(notes, {'destination':definition},
                semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT):
            if obligation['kind'] not in ('medication_absence','medication_response','historical_stopping_details','historical_cessation_support'):
                continue
            if not semantic._clinical_context_covered(notes, obligation, picked, context):
                issues.append('The historical medicine narrative omits complete requested source support ('
                    +obligation['kind']+'): '+obligation['source']['quote'])
    return list(dict.fromkeys(issues))


def timing_compatible(definition, fact):
    timing = definition['scope']['temporality']
    if timing == 'any' or timing == fact['timing']['kind']:
        return True
    frame = fact.get('source_assertion') or {}
    # A plan's prospective event does not retime its current decision or actual
    # not-performed/results status. Past encounters never enter this bridge.
    return (timing == 'future' and field_requirements(definition)['primary_domain'] == 'plan'
        and frame.get('domain') == 'plan' and frame.get('encounter_timing') == 'current'
        and fact['timing']['kind'] == 'current')


def subject_compatible(definition, fact):
    """Record beneficiary and performer are distinct source participants."""
    scope = definition['scope']['subject']
    if scope not in ('patient','clinician','other') or fact['subject']['kind'] == scope:
        return True
    frame = fact.get('source_assertion') or {}
    requirements = field_requirements(definition)
    return (scope == 'patient' and fact['subject']['kind'] == 'clinician'
        and frame.get('subject') == 'patient' and frame.get('encounter_timing') == 'current'
        and frame.get('time_account') and frame.get('account_clinician') and not fact['issues']
        and ('time' in requirements['required_domains'] or 'plan' in requirements['broad_sections']))


def positioned_governors(entries, value, units):
    """Structural headings end at explicit section boundaries.

    Account-wide source findings have their own explicit targets and are not
    removed here. This prevents a local negative list from contaminating the
    next SOAP section while preserving its effect inside its own section.
    """
    from .clinical_assertions_v4 import soap_heading
    def section(unit):
        text = unit['quote'].strip().rstrip(':')
        return bool(soap_heading(text) or re.fullmatch(r'(?:[SOAP]\s*[-–:]\s*)?'
            r'(?:Subjective|History|History of present illness|Review of systems|Objective|'
            r'Examination|Physical examination|Assessment|Impression|Plan)', text, re.I))
    result = []
    for entry in entries:
        heading = next((unit for unit in units if unit['start'] == entry['start']
            and unit['end'] == entry['end']), None)
        if heading and section(heading):
            continue
        if entry['start'] < value['start'] and any(entry['end'] <= unit['start'] < value['start']
                and section(unit) for unit in units):
            continue
        result.append(entry)
    return result
