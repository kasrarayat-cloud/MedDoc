"""Prospective content obligations, distinct from a SOAP storage location.

Required groups and optional source context are separate. Exact exclusion
evidence stays available even when it names no coarse clinical domain.
"""
from copy import deepcopy
import re

CONTRACT = 'approved-field-requirements-v2'
SCOPE_CONTRACT = 'positioned-clinical-requirements-v26'
INSTRUCTIONS = (' Required content groups are a union, distinct from the SOAP storage heading and optional source context. '
    'Do not require demographics, remote history or billing/time metadata merely because it shares a section. '
    'Only a complete independently bound intake/regimen primitive is optional intake context; a medicine or quantity '
    'inside a reported clinical event, response or precipitant never replaces that event role or its qualifiers. '
    'Clinical management and physician-time accounting are separate requested groups. Preserve explicit content-level '
    'exclusions even when they name no broad section. A nominal attribute/head exclusion and a source head/copular '
    'attribute expression require a scoped interpretation check; do not silently include or discard an unresolved '
    'equivalent expression. Negated and uncertain predicates retain their distinct polarity. '
    'The approved polarity scopes source obligations as well as assignment: independently positioned opposite-polarity '
    'predicates are not required in a restricted field. When compiled polarity restricts required content, a mixed '
    'predicate that cannot be partitioned stays an explicit scope interpretation hold; do not discard its qualifications. '
    'Unrestricted all-polarity requirements may retain complete mixed or conditional statements without that '
    'partition-only hold; all source-governance, fact and uncertainty safety checks still apply. '
    'Selected evidence can be visibly present but held by a genuine polarity, uncertainty, subject, time or '
    'source-governance finding; report the finding without calling that text missing.')
GROUPS = {
    'patient_name': r'\bpatient(?:[\x27’]s)?\s+(?:full\s+)?name\b|\bpatient\s+identity\b',
    'reported_symptoms': r'\b(?:patient[- ]reported|reported)\s+symptoms?\b|\bsymptom\s+(?:history|negatives?)\b|\bpertinent\s+negatives\b',
    'examination': r'\bobjective\b|\b(?:physical\s+)?exam(?:ination)?\b|\bobservations?\b',
    'assessment': r'\bassessment\b|\bimpression\b|\bdiagnos(?:is|es|tic)\b|\bclinical\s+interpretation\b',
    'management': r'\bplan\b|\bmanagement\b|\btreatment\b|\binvestigations?\b|\breferrals?\b|\badvice\b|\bfollow[- ]?up\b',
    'time_account': r'\b(?:physician|clinician)\s+time\b|\bE\s*/\s*M\b|\btime\s+(?:account|basis|activities|exclusions)\b',
}


def _correction_surface(source):
    from .generation import erratum_points, readings, REFRAMED_SCOPE, QUOTED_SOURCE, SCOPE_POINTER
    if any(SCOPE_POINTER.search(reading) or REFRAMED_SCOPE.search(reading)
            or QUOTED_SOURCE.search(reading) for reading in readings(source['quote'])):
        return None
    markers = list(erratum_points(source['quote']))
    if len(markers) != 1:
        return None
    marker = re.match(r'corrections?\b',source['quote'][markers[0]:],re.I)
    if marker is None:
        return None
    low,high = markers[0],markers[0]+marker.end()
    return low,high,source['quote'][:low]+' '*(high-low)+source['quote'][high:]


def governance_relations(notes, units, facts, context, corrections):
    """Resolve only exact, independently bound governor/target relations.

    This runs after ordinary correction validation. A proposed supersedes link
    alone is never scope evidence. Unknown or compound remaining governors and
    whole-account findings retain their original authority.
    """
    from .generation import (erratum_points, governed_context, heading_governance,
        readings, recognized_labels, REFRAMED_SCOPE, QUOTED_SOURCE, SCOPE_POINTER)
    source_units = {unit['id']: unit for unit in units}
    proofs = []
    if context is not None and not context['issues']:
        for finding in context['findings']:
            source = finding['source_evidence']
            row = context['units'].get(source['start'])
            targets = finding['target_unit_ids']
            if (finding['kind'] != 'source_account_governance'
                    or not set(finding['domains']) or not set(finding['domains']) <= {'assessment','time','clinical'}
                    or finding['subject'] != 'patient' or finding['encounter_timing'] != 'current'
                    or row is None or row['subject'] != 'patient' or row['section_timing'] != 'current'
                    or any(issue != 'A later source statement retracts, reassigns or retimes this clinical account.'
                        for issue in row['issues'])
                    or not targets or any(target not in source_units for target in targets)
                    or notes[source['start']:source['end']] != source['quote']):
                continue
            proofs.append({'contract': CONTRACT, 'kind':'source_account_governance',
                'domains':deepcopy(finding['domains']), 'subject':'patient', 'encounter_timing':'current',
                'source_evidence':deepcopy(source), 'target_unit_ids':deepcopy(targets)})
        from .clinical_semantics import assertion_frames
        from .semantic_generation import SOURCE_NUMBER_PATTERN
        frames = assertion_frames(notes,units,context,requirements_contract=CONTRACT)
        targets = [frame['source_unit_id'] for frame in frames if 'time_account' in frame['content_roles']
            and frame['subject'] == 'patient' and frame['encounter_timing'] == 'current']
        for frame in frames:
            source = frame['source_evidence']
            surface = _correction_surface(source)
            if (surface is None or frame['subject'] != 'patient' or frame['encounter_timing'] != 'current'
                    or frame['clinical_timing'] != 'current' or not frame['time_account']
                    or frame['actor'] != 'clinician' or not frame['account_clinician']
                    or len(context['clinicians']) != 1
                    or any(issue != 'A later source statement retracts, reassigns or retimes this clinical account.'
                        for issue in frame['issues'])
                    or any(finding['kind'] != 'source_account_governance'
                        or not set(finding['domains']) <= {'time'} for finding in frame['governance_findings'])):
                continue
            low,high,remaining = surface
            if source['quote'][:low].strip():
                continue
            claim = re.fullmatch(r'\s*:\s*(?:(?:the|current|documented|total)\s+){0,3}'
                r'(?:physician|clinician)\s+time\s+(?:is|was|(?:may|might|could)\s+(?:not\s+)?be)\s+'
                r'(?:(?:not|never)\s+)?'
                r'(?P<quantity>'+SOURCE_NUMBER_PATTERN+r')\s+(?:minutes?|hours?|seconds?)\s*[.!?]?\s*',
                source['quote'][high:],re.I)
            if claim is None:
                continue
            quantity = {'start':source['start']+high+claim.start('quantity'),
                'end':source['start']+high+claim.end('quantity'),'quote':claim['quantity']}
            residual = heading_governance(remaining,recognized_labels([]),lexical=True,per_sentence=True)
            if governed_context(residual,remaining,[{**quantity,'start':quantity['start']-source['start'],
                    'end':quantity['end']-source['start']}]):
                continue
            proofs.append({'contract':CONTRACT,'kind':'scoped_time_correction_claim','domains':['time'],
                'subject':'patient','actor':'clinician','encounter_timing':'current',
                'source_evidence':deepcopy(source),'target_unit_ids':targets,
                'clinician_evidence':deepcopy(context['clinicians'][0]['source']),
                'quantity_evidence':quantity,'retires_facts':False,'establishes_time_eligibility':False})
    for relation in corrections:
        replacement, old = facts[relation['correction_fact_id']], facts[relation['target_fact_id']]
        if replacement['issues'] or any(issue != 'A later source statement retracts, reassigns or retimes this clinical account.'
                for issue in old['issues']):
            continue
        source = next(unit for unit in units if unit['start'] <= replacement['value_evidence']['start']
            < replacement['value_evidence']['end'] <= unit['end'])
        frame = replacement.get('source_assertion') or {}
        old_frame = old.get('source_assertion') or {}
        if (frame.get('subject') != 'patient' or frame.get('encounter_timing') != 'current'
                or frame.get('clinical_timing') != 'current' or frame.get('uncertainty_evidence')
                or frame.get('issues') or replacement['polarity'] not in ('affirmed','negated')
                or replacement['timing']['kind'] != 'current' or replacement['timing']['kind'] != old['timing']['kind']
                or old_frame.get('subject') != 'patient' or old_frame.get('encounter_timing') != 'current'
                or old_frame.get('clinical_timing') != 'current'):
            continue
        surface = _correction_surface(source)
        if surface is None:
            continue
        # Erase only the already-validated erratum word for a residual scope
        # check. A second heading, denial, ownership or unknown pointer in this
        # same source unit still governs; the original source is never edited.
        low,high,remaining = surface
        residual = heading_governance(remaining, recognized_labels([]), lexical=True, per_sentence=True)
        local_value = {**replacement['value_evidence'],
            'start':replacement['value_evidence']['start']-source['start'],
            'end':replacement['value_evidence']['end']-source['start']}
        if governed_context(residual, remaining, [local_value]):
            continue
        proofs.append({'contract':CONTRACT, 'kind':'validated_fact_correction',
            'subject':replacement['subject']['kind'], 'encounter_timing':frame['encounter_timing'],
            'correction_fact_id':replacement['id'], 'target_fact_ids':[old['id']],
            'source_evidence':{key:source[key] for key in ('start','end','quote')},
            'marker_evidence':{'start':source['start']+low, 'end':source['start']+high,
                'quote':source['quote'][low:high]}})
    return proofs


def scoped_governors(entries, fact, units, proofs):
    """Apply the immutable proof set without depending on fact iteration order."""
    own = next(unit for unit in units if unit['start'] <= fact['value_evidence']['start']
        < fact['value_evidence']['end'] <= unit['end'])
    result, applied = [], []
    for entry in entries:
        matching = [proof for proof in proofs if all(entry.get(key) == proof['source_evidence'][key]
            for key in ('start','end','quote'))]
        if (not matching or any(fact['id'] in proof.get('target_fact_ids', [])
                or own['id'] in proof.get('target_unit_ids', []) for proof in matching)):
            result.append(entry)
            continue
        applied.extend(proof for proof in matching if proof not in applied)
    return result, applied


def compile_requirements(definition, base):
    result = deepcopy(base)
    result['contract'] = CONTRACT
    required, excluded, consumed_group_words = set(), set(), set()
    group_evidence, content_exclusions = [], []
    for clause in base['clauses']:
        text = clause['evidence']['quote']
        # A section heading describes placement. Content after its colon is
        # the request; an explicit union must never be replaced by that heading.
        positive = re.sub(r'^\s*(?:Subjective|Objective|Assessment|Plan)(?:\s+section(?:\s+of\s+the\s+SOAP\s+note)?)?\s*:\s*', '', text, flags=re.I)
        groups = {key for key, pattern in GROUPS.items() if re.search(pattern, positive, re.I)}
        if clause['role'] == 'required':
            required.update(groups)
            for pattern in GROUPS.values():
                for match in re.finditer(pattern, positive, re.I):
                    consumed_group_words.update(re.findall(r'[^\W\d_]+', match[0].casefold()))
        elif clause['role'] == 'excluded':
            topic = re.sub(r'^\s*(?:(?:do|must|should)\s+not\s+(?:include|record|document)|exclud(?:e|es|ing)|omit(?:s|ting)?|without|except(?:\s+for)?|apart\s+from)\s+', '', text, flags=re.I)
            topic = re.sub(r'\s+(?:is|are|must\s+be|should\s+be)\s+(?:excluded|omitted|not\s+included).*$', '', topic, flags=re.I)
            # Every coordinated object keeps its own exclusion. A broad
            # domain in one object cannot consume a different literal object.
            for item in re.split(r'\s*,\s*(?:(?:and|or)\s+)?|\s+(?:and|or)\s+', topic):
                topic = re.sub(r'^(?:the|a|an)\s+', '', item.strip(), flags=re.I)
                item_groups = {key for key, pattern in GROUPS.items() if re.fullmatch(pattern, topic, re.I)}
                if item_groups:
                    excluded.update(item_groups)
                    continue
                tokens = re.findall(r"[\w]+(?:['’][\w]+)?", topic.casefold())
                if tokens:
                    content_exclusions.append({'tokens': tokens, 'evidence': deepcopy(clause['evidence']),
                        'polarity_scope':'unspecified',
                        'nominal_candidates':[{'attribute_tokens':tokens[:at], 'head_tokens':tokens[at:]}
                            for at in range(1,len(tokens))]})
        group_evidence.append({'role': clause['role'], 'groups': sorted(groups), 'evidence': deepcopy(clause['evidence'])})
    # A bare section still has its ordinary content meaning. It does not make
    # billing metadata a clinical management action or demographics a symptom.
    if not required and base['primary_domain'] and not base['unconsumed_topic_words']:
        required.add({'subjective':'reported_symptoms', 'objective':'examination',
            'assessment':'assessment', 'plan':'management'}[base['primary_domain']])
    strict = any(clause['role'] == 'required' and re.search(
        r'\b(?:only|solely|exclusively|restricted\s+to|limited\s+to)\b',clause['evidence']['quote'],re.I)
        for clause in base['clauses'])
    result.update(required_groups=sorted(required-excluded), excluded_groups=sorted(excluded),
        content_exclusions=content_exclusions, group_evidence=group_evidence,
        strict_content_scope=strict,
        allowed_context_sections=([base['primary_domain']] if base['primary_domain'] and not strict else []))
    # Explicit recognized group unions retain section completeness. Unknown
    # positive clinical topics continue through the existing narrow proof gate.
    result['coverage_mode'] = ('section' if required and not (
        set(base['unconsumed_topic_words']) - consumed_group_words) else base['coverage_mode'])
    return result


def _duration_qualification(notes, frame, earlier_frames):
    source = frame['source_evidence']
    reference = re.match(r'\s*(?:this|that|these|those|the)\s+'
        r'(?P<modifiers>(?:[\w-]+\s+){0,3}?)(?:durations?|lengths?|intervals?|times?)\s+'
        r'(?:describes?|represents?|refers?\s+to|means?)\b',source['quote'],re.I)
    if reference is None:
        return None
    from .semantic_generation import SOURCE_NUMBER_PATTERN
    quantity = re.compile(r'(?<!\w)(?:'+SOURCE_NUMBER_PATTERN+r')\s+'
        r'(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b',re.I)
    candidates = [earlier for earlier in earlier_frames
        if set(earlier['content_roles']) & {'reported_symptoms','time_account'}
        and earlier['subject'] == frame['subject'] == 'patient'
        and earlier['encounter_timing'] == frame['encounter_timing'] == 'current'
        and not earlier['issues'] and not re.search(r'\n\s*\n',
            notes[earlier['source_evidence']['end']:source['start']])
        and quantity.search(earlier['source_evidence']['quote'])]
    antecedent = candidates[-1] if candidates and not frame['issues'] else None
    modifiers = {word.casefold().rstrip('s') for word in re.findall(r'[\w-]+',reference['modifiers'])}
    if not antecedent or not modifiers <= {word.casefold().rstrip('s') for word in re.findall(
            r'[\w-]+',antecedent['source_evidence']['quote'])}:
        return {'issue':'The source duration modifier lacks a uniquely bound time antecedent in the same paragraph and current patient encounter.'}
    target = antecedent['source_evidence']; amount = quantity.search(target['quote'])
    role = 'time_account' if 'time_account' in antecedent['content_roles'] else 'reported_symptoms'
    return {'role':role,'relation':{'kind':'qualifies','target_unit_id':antecedent['source_unit_id'],
        'source_evidence':deepcopy(source),'target_evidence':{
            'start':target['start']+amount.start(),'end':target['start']+amount.end(),'quote':amount[0]}}}


def _intake_context(text, patient_name, prior, paragraph_continuation):
    """Only a complete matrix intake is optional intake/background context.

    A medicine mentioned inside a symptom's causal adjunct does not supply the
    role of that symptom. A quantity does not identify a medicine. Unknown
    tails and additional event predicates never disappear into an object.
    """
    from .semantic_generation import SOURCE_NUMBER_PATTERN
    from .clinical_assertions import _DATE, _MONTH
    from .soap_clinical_literals import _bounded_nominal
    actor = r'(?:he|she|they|the\s+patient' + ('|'+re.escape(patient_name) if patient_name else '') + ')'
    match = re.fullmatch(r'\s*'+actor+r'\s+(?P<body>.+?)\s*\.?\s*',text,re.I)
    if match is None:
        return None
    body = re.sub(r'^(?:reports?|reported|denies?|denied)\s+', '', match['body'], flags=re.I)
    body = re.sub(r'^(?:is|are|was|were|has\s+been|have\s+been|had\s+been)\s+', '', body, flags=re.I)
    amount = r'(?:'+SOURCE_NUMBER_PATTERN+r')'
    date = (r'(?:on\s+'+_DATE+r'|in\s+(?:'+_MONTH+r')\s+\d{4}|'
        +amount+r'\s+(?:days?|weeks?|months?|years?)\s+ago|yesterday|now)')
    dates = date+r'(?:,?\s*'+date+r'){0,2}'
    prior_object = (prior or {}).get('context_role_evidence',{}).get('object')
    cessation = (r'(?:stopped|discontinued)\s+(?:it|this|that)\s+'+dates
        +r',?\s+and\s+(?:is|are)\s+not\s+(?:taking|using)\s+'
        +re.escape(prior_object)+r'\s+now') if prior_object else None
    if (paragraph_continuation and prior and prior.get('context_kind') in ('therapy','intake_regimen','therapy_continuation')
            and (re.fullmatch(r'(?:began|started|stopped|discontinued)\s+(?:it|this|that)'
                r'(?:\s+'+dates+r')?(?:,?\s+for\s+(?:the\s+)?[A-Za-z-]+)?',body,re.I)
                or cessation and re.fullmatch(cessation,body,re.I))):
        return {'kind':'therapy_continuation','object':prior_object}
    intake = re.fullmatch(r'(?:taking|using|took|used|tried|(?:stopped|discontinued)(?:\s+(?:taking|using))?)\s+(?P<object>.+)',body,re.I)
    if intake is None:
        return None
    frequency = r'(?:once\s+daily|daily|nightly|(?:each|every)\s+(?:morning|evening)|'+amount+r'\s+times\s+daily)'
    generic = (r'(?:(?:a|an|the|her|his|their)\s+)?(?:(?:documented|prescribed|current|daily)\s+){0,2}'
        r'(?:medicin(?:e|es)|medications?|drugs?|therap(?:y|ies)|treatments?|tablets?|capsules?)')
    if re.fullmatch(generic+r'(?:\s+'+frequency+r')?(?:\s+'+dates+r')?',intake['object'],re.I):
        return {'kind':'therapy','object':intake['object']}
    nominal = r'[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z][A-Za-z0-9-]*){0,3}'
    regimen = re.fullmatch(r'(?P<name>'+nominal+r')\s+'+amount+r'\s+(?:mcg|mg|g|mL|units?)'
        r'(?:\s+mixed\s+in\s+'+amount+r'\s+mL\s+of\s+(?P<vehicle>'+nominal+r'))?'
        r'\s+(?:by\s+mouth|orally)(?:\s+'+frequency+r')?'
        r'(?:\s+starting\s+'+date+r')?',intake['object'],re.I)
    if (regimen and _bounded_nominal(regimen['name'],lambda value:True)
            and (not regimen['vehicle'] or _bounded_nominal(regimen['vehicle'],lambda value:True))):
        return {'kind':'intake_regimen','object':regimen['name']}
    return None


def source_roles(notes, frames, context):
    from .documented_time_source import positioned_qualification, positioned_linked_claim
    result, prior = [], None
    patient_name = context.get('patient_name')
    for frame in frames:
        frame = deepcopy(frame)
        source = frame['source_evidence']; text = source['quote']
        frame['predicate_scopes'] = predicate_scopes(source)
        paragraph_continuation = bool(prior and not re.search(r'\n\s*\n', notes[prior['source_evidence']['end']:source['start']]))
        if source['start'] in context.get('time_heading_units',[]):
            frame.update(content_roles=['source_scope_heading'],content_evidence={})
            result.append(frame);prior=frame
            continue
        roles = set()
        time = (frame['time_account'] or positioned_qualification(text, context)
            or positioned_linked_claim(text, established=bool(prior and 'time_account' in prior['content_roles'])) == 'time')
        qualification = _duration_qualification(notes, frame, result)
        if qualification:
            # The referenced quantity supplies its role. A physician-time
            # object inside a symptom qualifier cannot retag its subject.
            time = qualification.get('role') == 'time_account'
        if time:
            roles.add('time_account')
        elif frame['domain'] in ('objective', 'assessment', 'plan'):
            roles.add({'objective':'examination','assessment':'assessment','plan':'management'}[frame['domain']])
        name_match = re.search(r'(?<!\w)'+re.escape(patient_name)+r'(?!\w)', text, re.I) if patient_name else None
        if name_match:
            roles.add('patient_name')
        if frame['domain'] == 'subjective' and not time:
            intake = _intake_context(text,patient_name,prior,paragraph_continuation)
            background = bool(re.search(r'\b(?:has|have)\s+(?:a\s+)?history\s+of\b|\bwas\s+removed\b|\bpreviously\s+caused\b', text, re.I))
            meta = bool(re.search(r'\b(?:is\s+an?\s+(?:established|new)\s+patient|attending\s+an?\b|professional\s+office\s+evaluation)\b', text, re.I))
            actor = r'(?:he|she|they|the\s+patient' + ('|'+re.escape(patient_name) if patient_name else '') + ')'
            explicit_report = bool(re.search(r'\b'+actor+r'\s+(?:(?:has|have|had)\s+)?'
                r'(?:reports?|reported|denies?|denied|notices?|noticed|describes?|described|complains?)\b',text,re.I))
            report = (explicit_report
                or re.match(r'\s*(?!it\b|she\b|he\b|they\b)[^.;]+?\s+(?:started|began)\b',text,re.I)
                or re.match(r'\s*'+actor+r'\s+(?:has|have)\b',text,re.I))
            inherited = bool(paragraph_continuation and prior and 'reported_symptoms' in prior['content_roles'])
            if not intake and (report or inherited) and (explicit_report or not (background or meta)):
                roles.add('reported_symptoms')
            elif intake or background or meta:
                roles.add('optional_source_context')
                frame['context_kind'] = intake['kind'] if intake else 'background' if background else 'encounter'
                if intake:
                    frame['context_role_evidence'] = {**intake,'source_evidence':deepcopy(source),
                        'complete_primitive':True}
            elif 'patient_name' not in roles:
                roles.add('unclassified_subjective')
        if qualification:
            if 'role' in qualification:
                roles -= {'reported_symptoms','time_account','optional_source_context','unclassified_subjective'}
                roles.add(qualification['role'])
                frame['source_relations'] = [qualification['relation']]
            else:
                roles -= {'reported_symptoms','optional_source_context','management','examination','assessment'}
                roles.add('unclassified_subjective')
                frame['relation_findings'] = [qualification['issue']]
        frame['content_roles'] = sorted(roles)
        frame['content_evidence'] = {role: deepcopy(source) for role in roles}
        if name_match:
            frame['content_evidence']['patient_name'] = {'start':source['start']+name_match.start(),
                'end':source['start']+name_match.end(),'quote':name_match[0]}
        result.append(frame); prior = frame
    return result


def required(requirements, frame):
    return bool(set(requirements['required_groups']) & set(frame['content_roles']))


def predicate_scopes(evidence):
    """Keep polarity on complete positioned predicates, not a whole sentence.

    Only an independent finite predicate can open a new scope. A denial list,
    nominal continuation or negative adjunct is never split into an invented
    affirmative observation. Unresolved mixed scope grants no omission.
    """
    from .clinical_semantics import _NEGATIVE, _UNCERTAIN
    from .clinical_assertions import calendar_mask
    from .soap_clinical_literals import _bounded_nominal
    text = evidence['quote']
    finite = (r'(?:is|are|was|were|has|have|had|appears?|seems?|remains?|'
        r'reports?|reported|denies?|denied|describes?|described|notices?|noticed|may|might|could)')
    actor = r'(?:he|she|they|it|there|the\s+patient)'
    def matrix_predicate(value):
        # Bind the FIRST finite predicate. Searching past an invalid prefix
        # could turn a relative clause into the matrix or absorb an earlier
        # predicate/coordinator into a fabricated nominal subject.
        match=re.match(r'\s*(?P<subject>[A-Za-z][A-Za-z-]*(?:\s+[A-Za-z][A-Za-z-]*){0,7}?)\s+'
            r'(?P<predicate>'+finite+r')\b(?P<tail>.*)',value,re.I)
        if match is None:
            return None
        head=match['subject']
        nominal=re.sub(r'^(?:no|his|her|their)\s+','',head,flags=re.I)
        if not re.fullmatch(actor,head,re.I) and not _bounded_nominal(nominal,lambda value:True):
            return None
        return match
    spans, start = [], 0
    for boundary in re.finditer(r'\s*;\s*|\s*,?\s+\b(?:and|but|whereas|while)\b\s+',text,re.I):
        if matrix_predicate(text[boundary.end():]) is not None:
            spans.append((start,boundary.start()));start=boundary.end()
    spans.append((start,len(text)))
    result=[]
    for low,high in spans:
        while low < high and text[low].isspace(): low+=1
        while high > low and text[high-1].isspace(): high-=1
        if low == high: continue
        quote=text[low:high]
        matrix=matrix_predicate(quote)
        negatives=list(_NEGATIVE.finditer(quote));uncertain=list(_UNCERTAIN.finditer(calendar_mask(quote)))
        # A negative head or complete negative copula governs its own object;
        # 'soft without guarding' has a separate positive predicate and a
        # negative adjunct, and cannot be reduced to either polarity here.
        negative_head = re.match(r'\s*(?:'+actor+r'\s+)?(?:(?:has|have|had|is|are|was|were)\s+)?'
            r'(?:no|not|never|nothing|neither|denies?|denied|without)\b',quote,re.I)
        reported_negative = re.match(r'\s*'+actor+r'\s+(?:reports?|reported|describes?|described|notes?|noted|states?|stated)\s+'
            r'(?:no|not|never|(?:(?:an?|the)\s+)?absence\s+of)\b',quote,re.I)
        negative_copula = bool(matrix and re.fullmatch(r'is|are|was|were|has|have|had',matrix['predicate'],re.I)
            and re.match(r'\s+(?:not|never|no|absent|nontender|non[- ]tender|non[- ]distended)\b',matrix['tail'],re.I))
        uncertain_head = re.match(r'\s*(?:(?:possible|possibly|suspected|uncertain|unknown)\b|'
            +actor+r'\s+(?:reports?|reported|describes?|described)\s+(?:possible|suspected|uncertain)\b)',quote,re.I)
        uncertain_head = uncertain_head or bool(matrix and (
            re.fullmatch(r'may|might|could',matrix['predicate'],re.I)
                and re.match(r'\s+(?:not\s+)?(?:be|have)\b',matrix['tail'],re.I)
            or re.fullmatch(r'is|are|was|were|remains?',matrix['predicate'],re.I)
                and re.match(r'\s+(?:possible|suspected|uncertain|unclear|unknown|unestablished)\b',matrix['tail'],re.I)))
        mixed_finite = re.search(r'\b(?:and|or|but|whereas|while)\s+(?:'+actor+r'\s+)?'+finite+r'\b',quote,re.I)
        nested_actor = bool(negatives and re.search(r'\b'+actor+r'\s+'+finite+r'\b',quote[negatives[0].end():],re.I))
        # A local qualifier can carry a different predicate scope (pain with
        # possible radiation; absence of tenderness with pain elsewhere).
        # Without an independently complete partition, it cannot remove the
        # affirmative event from a positive destination's obligations.
        qualified_scope = bool((negatives or uncertain) and re.search(
            r'\b(?:with|without|after|before|since|because|when|although)\b',quote,re.I))
        if re.search(r'[“”"]|\b(?:if|unless|whether)\b',quote,re.I) or mixed_finite or nested_actor:
            polarity='unresolved'
        elif uncertain:
            polarity='uncertain' if uncertain_head and not qualified_scope else 'unresolved'
        elif not negatives:
            polarity='affirmed'
        elif (negative_head or reported_negative or negative_copula) and not qualified_scope and not re.search(r'\b(?:but|whereas|while)\b|;',quote,re.I):
            polarity='negated'
        else:
            polarity='unresolved'
        def positioned(match):
            return {'start':evidence['start']+low+match.start(),
                'end':evidence['start']+low+match.end(),'quote':match[0]}
        def matrix_evidence(group):
            start,end=matrix.span(group)
            return {'start':evidence['start']+low+start,'end':evidence['start']+low+end,
                'quote':quote[start:end]}
        result.append({'polarity':polarity,'source_evidence':{
            'start':evidence['start']+low,'end':evidence['start']+high,'quote':quote},
            'matrix_evidence':({'subject':matrix_evidence('subject'),'predicate':matrix_evidence('predicate')}
                if matrix is not None else None),
            'negative_evidence':[positioned(match) for match in negatives],
            'uncertainty_evidence':[positioned(match) for match in uncertain]})
    return result


def obligation_frames(requirements, frames):
    """A restricted destination receives only independently scoped predicates."""
    if set(requirements['allowed_fact_polarities']) == {'affirmed','negated','uncertain','mixed'}:
        return frames
    result=[]
    for frame in frames:
        for predicate in frame['predicate_scopes']:
            result.append({**frame,'source_evidence':predicate['source_evidence'],
                'source_polarity':predicate['polarity'],'polarity_scope':predicate})
    return result


def applicable(requirements, frame):
    """A field's content obligation cannot acquire another owner or time."""
    subject = requirements['scope']['subject']
    if subject == 'patient' and frame['subject'] != 'patient':
        return False
    if subject == 'clinician' and not (frame['subject'] == 'patient'
            and frame['actor'] == 'clinician' and frame['time_account'] and frame['account_clinician']):
        return False
    if subject == 'other' and frame['subject'] not in ('other','foreign'):
        return False
    polarity=frame.get('source_polarity')
    if polarity and polarity != 'unresolved' and polarity not in requirements['allowed_fact_polarities']:
        return False
    timing = requirements['scope']['temporality']
    if timing == 'any':
        return True
    encounter, clinical = frame['encounter_timing'],frame['clinical_timing']
    if timing == 'current':
        return encounter == 'current' and clinical == 'current'
    if timing == 'past':
        return encounter == 'past' or clinical == 'past'
    # A current decision/order and its prospective performance are separate,
    # as in the existing compatible timing rule for a future Plan destination.
    return timing == 'future' and encounter == 'current' and (
        clinical == 'future' or clinical == 'current' and frame['domain'] == 'plan')


def exclusion_spans(requirements, evidence):
    words = list(re.finditer(r"[\w]+(?:['’][\w]+)?", evidence['quote']))
    normalized = [word[0].casefold() for word in words]
    spans = []
    for exclusion in requirements['content_exclusions']:
        tokens = exclusion['tokens']
        for index in range(len(words)-len(tokens)+1):
            if normalized[index:index+len(tokens)] == tokens:
                low,high = words[index].start(),words[index+len(tokens)-1].end()
                before,after = evidence['quote'][:low],evidence['quote'][high:]
                negative = re.search(r'\b(?:no|not|without|denies?|denied)\s*$',before,re.I)
                uncertain = re.search(r'\b(?:possible|possibly|suspected|uncertain)\s*$',before,re.I)
                qualified = re.match(r'\s+(?:is|are|was|were)\s+(?:not|never)\b',after,re.I)
                modal = re.match(r'\s+(?:may|might|could)\s+be\b',after,re.I)
                polarity = 'negated' if negative else 'uncertain' if uncertain or modal else 'unresolved' if qualified else 'affirmed'
                polarity_evidence = []
                for marker,offset in ((negative,0),(uncertain,0),(qualified,high),(modal,high)):
                    if marker:
                        polarity_evidence.append({'start':evidence['start']+offset+marker.start(),
                            'end':evidence['start']+offset+marker.end(),'quote':marker[0]})
                spans.append({'start': evidence['start']+words[index].start(),
                    'end': evidence['start']+words[index+len(tokens)-1].end(),
                    'match_kind':'literal', 'polarity':polarity,
                    'resolution':'excluded' if polarity == 'affirmed' else 'requires_review',
                    'polarity_evidence':polarity_evidence,
                    'exclusion_polarity_scope':exclusion['polarity_scope'],
                    'exclusion_evidence': deepcopy(exclusion['evidence'])})
        for candidate in exclusion.get('nominal_candidates',[]):
            head = r'[ \t-]+'.join(re.escape(token) for token in candidate['head_tokens'])
            attribute = r'[ \t-]+'.join(re.escape(token) for token in candidate['attribute_tokens'])
            pattern = (r"(?<![\w'’])(?P<head>"+head+r')\s+'
                r'(?P<copula>is|are|was|were|(?:may|might|could)\s+be)\s+'
                r'(?P<negative>(?:not|never)\s+)?'
                r'(?P<attribute>'+attribute+r")(?![\w'’])")
            for match in re.finditer(pattern,evidence['quote'],re.I):
                def selected(group):
                    low,high = match.span(group)
                    return {'start':evidence['start']+low, 'end':evidence['start']+high,
                        'quote':evidence['quote'][low:high]}
                # Ordered grammatical roles establish a possible nominal
                # equivalence, never an arbitrary word-bag or medical fact.
                # Unknown nominal partition semantics remain a review hold;
                # they cannot authorize discarding required source content.
                spans.append({'start':evidence['start']+match.start(),
                    'end':evidence['start']+match.end(), 'match_kind':'attribute_predicate_candidate',
                    'polarity':'negated' if match['negative'] else 'uncertain' if re.match(r'(?:may|might|could)\b',match['copula'],re.I) else 'affirmed',
                    'uncertainty':bool(re.match(r'(?:may|might|could)\b',match['copula'],re.I)),
                    'head_evidence':selected('head'), 'attribute_evidence':selected('attribute'),
                    'copula_evidence':selected('copula'), 'resolution':'requires_review',
                    'negative_evidence':selected('negative') if match['negative'] else None,
                    'exclusion_polarity_scope':exclusion['polarity_scope'],
                    'exclusion_evidence':deepcopy(exclusion['evidence'])})
    return spans
