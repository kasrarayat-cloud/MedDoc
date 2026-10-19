"""Bridge selected Corti predictions into the existing revision-bound review.

The retained offline adapter remains unchanged. This layer independently checks
dated reference membership, source assertions and applicable local coding rules.
Provider candidates/alternatives never become clinician replacement choices.
"""
from copy import deepcopy
from datetime import date
import hashlib
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

from . import coding_engine as engine, coding_terminology, corti_prediction
from .corti_response import CatalogRelease, DatedTerminology, adapt_response
from .coding_licensing import cpt_status
from .models import Code, CodeSet
from . import corti_semantics

CONTRACT = 'corti-selected-dated-review-v1'
DIAGNOSTIC_CONTRACT = 'source-route-diagnostics-v1'
SYSTEMS = {'icd10cm-outpatient': 'ICD-10-CM', 'cpt': 'CPT'}


def identity_blockers(run):
    """Source identity without an additional inference call or registry filling.

    Use existing validated answer identity facts when present. Generic notes
    accept only finite, complete source name frames; everything else requires
    the existing explicit synthetic identity review, never silent substitution.
    """
    from . import source_assertion_coding as shared
    if shared.enabled(run):
        return shared.identity_blockers(run)
    from .semantic_generation import _complete_patient_identity, person_name_value, patient_name_check
    notes = run.inputs['notes']
    names = []
    pattern = re.compile(r'(?:^|[.!?;]\s*|\n\s*)(?:Patient(?:\x27s)?(?: full)? name:\s*)?'
        r'(?P<name>[A-Z][\w\x27’-]*(?: [A-Z][\w\x27’-]*){1,5})'
        r'(?P<age>, age [0-9]{1,3},)?(?=\s+(?:attends|attended|presents|presented|reports|reported|has|had|is|was)\b)')
    for match in pattern.finditer(notes):
        name = match['name']
        span = {'start': match.start('name'), 'end': match.end('name'), 'quote': name}
        complete = _complete_patient_identity(notes, {'value_evidence': span})
        if match['age']:
            # An age apposition is allowed only in an explicit visit frame.
            # Removing that apposition must still pass the original ownership
            # grammar (e.g. "attends her patient's visit" is not this patient).
            without_age = notes[:match.start('age')] + notes[match.end('age'):]
            complete = (bool(re.match(r'\s+(?:attends|attended|presents|presented)\b[^.!?\n]*\bvisit\b', notes[match.end():]))
                and _complete_patient_identity(without_age, {'value_evidence': span}))
        if person_name_value(name) and complete:
            names.append((name, notes[match.start('name'):match.end()]))
    blockers = engine.identity_blockers(run, {})
    # Inventory explicit labelled slots independently of the provider and the
    # finite leading-name frame. An omitted competing name is still a conflict.
    inventory = patient_name_check(notes, {'scope': {'subject': 'patient'},
        'value_type': 'person_name'}, {}, [])
    for span in inventory['unrepresented_source_names']:
        if person_name_value(span['quote']) and _complete_patient_identity(notes, {'value_evidence': span}):
            names.append((span['quote'], span['quote']))
        else:
            blockers.append('An explicit patient-name source slot has unresolved boundaries. Clarify the source identity before coding approval.')
    for name, quotation in names:
        blockers.extend(engine.identity_blockers(run, {'documented_patient_name': name, 'patient_name_evidence': quotation}))
    bridge_names = [name for row in engine.checked_patient_name_evidence(run.inputs) for name in row['names']]
    if not names and not bridge_names:
        reviewed = run.context.get('identity_review_reason', '').strip()
        from django.conf import settings
        if not (settings.SYNTHETIC_ONLY and len(reviewed) >= 12):
            blockers.append('The source patient identity is unresolved for direct coding. Review the synthetic identity explicitly before approving; registry details cannot supply an undocumented name.')
    return list(dict.fromkeys(blockers))


def terminology(run):
    when = date.fromisoformat(run.inputs['service_date'])
    cpt = cpt_status(when)
    releases = []
    for bound in run.releases:
        release = CodeSet.objects.get(pk=bound['id'])
        if (release.sha256 != bound['sha256'] or release.version != bound['version']
                or release.effective_from.isoformat() != bound['effective_from']
                or release.effective_until.isoformat() != bound['effective_until']):
            raise ValidationError('The bound coding reference release changed.')
        if release.system == 'ICD-10-CM':
            url = urlsplit(release.source_url)
            if url.scheme != 'https' or url.hostname not in ('ftp.cdc.gov', 'www.cdc.gov', 'www.cms.gov'):
                continue
            system, authority = 'icd10cm-outpatient', release.source_url
        elif release.system == 'CPT' and cpt['available'] and cpt['release_id'] == str(release.pk):
            system, authority = 'cpt', release.license_reference
        else:
            continue
        descriptions = dict(Code.objects.filter(release=release).values_list('code', 'description'))
        if descriptions:
            releases.append(CatalogRelease(system, release.version, release.effective_from,
                release.effective_until, release.source_url, release.sha256, descriptions, authority))
    return DatedTerminology(releases, unavailable_reasons={'cpt':
        'CPT descriptor and service-date release are unverified. ' + cpt.get('reason', '')}), cpt


def _route_diagnostics(run, reference, proposal):
    from . import source_assertion_coding as shared
    return {'contract': DIAGNOSTIC_CONTRACT, 'proposal_id': proposal['id'],
        'code': proposal['code'], 'source_sha256': hashlib.sha256(run.inputs['notes'].encode()).hexdigest(),
        'source_contract': run.config.get('clinical_source_contract'),
        'source_profile': shared.graph.CONTRACT if shared.enabled(run) else engine.source_profile(run.config.get('clinical_source_contract')),
        'reference': {'release_id': str(reference.release_id),
            'version': reference.release.version, 'coding_digest': reference.digest},
        'attempts': [], 'outcome': None, 'initiating_failure': None}


def _diagnostic_attempt(diagnostics, notes, *, entry=None, term=None, span=None, clause=None):
    if diagnostics is None:
        return None
    witnesses = []
    if clause is not None:
        from .generation import source_units
        from .clinical_source_context import source_context, owned_current
        units, _ = source_units(notes, [])
        context = source_context(notes, units, profile=diagnostics['source_profile'])
        for match in re.finditer(re.escape(clause), notes):
            witnesses.append({'start': match.start(), 'end': match.end(), 'quote': clause,
                'units': [{'source': deepcopy(unit), 'context': deepcopy(context['units'][unit['start']]),
                           'owned_current': owned_current(context, unit)}
                    for unit in units if unit['start'] < match.end() and match.start() < unit['end']],
                'context_issues': deepcopy(context['issues'])})
    row = {'ordinal': len(diagnostics['attempts']) + 1,
        'entry_id': entry.get('id') if entry else None, 'term': term,
        'provider_span': deepcopy(span), 'expanded_source': witnesses,
        'gates': [], 'failures': [], 'outcome': None}
    diagnostics['attempts'].append(row)
    return row


def _diagnostic_gate(attempt, gate, status, detail):
    if attempt is None:
        return
    event = {'gate': gate, 'status': status, 'detail': deepcopy(detail)}
    attempt['gates'].append(event)
    if status == 'failed':
        attempt['failures'].append(deepcopy(event))


def _diagnostic_finish(diagnostics, result):
    if diagnostics is not None:
        diagnostics['outcome'] = 'eligible' if result[1] else 'held'
        if not result[1]:
            diagnostics['initiating_failure'] = next((
                {'attempt_ordinal': row['ordinal'], **deepcopy(row['failures'][0])}
                for row in diagnostics['attempts'] if row['failures']), None)
    return result


def _icd_source(run, reference, proposal, selected_codes, *, diagnostics=None):
    """Bind the selected code to dated lexical routes and the complete source.

    New runs recognize reference-owned head vocabulary and specific Tabular
    phrases. Historical runs retain their original route contract. Neither
    branch promotes a provider alternative or treats membership as eligibility.
    """
    from . import source_assertion_coding as shared
    if shared.enabled(run):
        return shared.icd_source(run, reference, proposal, selected_codes, diagnostics=diagnostics)
    lookup = engine.index_lookup(reference)
    notes = run.inputs['notes']
    contract = run.config.get('clinical_source_contract') if hasattr(run, 'config') else None
    modern = contract in engine.SOURCE_CONTRACTS
    matching = [entry for entry in reference.index if entry.get('code') == proposal['code']
                and not entry.get('requires_review')]
    if not matching:
        attempt = _diagnostic_attempt(diagnostics, notes)
        _diagnostic_gate(attempt, 'index_candidate', 'failed', {
            'reason': 'No admissible Index entry for this selected code.',
            'review_required_entry_ids': [entry['id'] for entry in reference.index
                if entry.get('code') == proposal['code'] and entry.get('requires_review')]})
        if attempt is not None:
            attempt['outcome'] = 'held'
    for entry in matching:
        head = entry
        while head.get('parent_id') in lookup:
            head = lookup[head['parent_id']]
        description = proposal['terminology']['description']
        terms = (engine.index_head_terms(head, description) if modern else
                 [re.sub(r'\(s\)$', '', head.get('term', ''), flags=re.I)])
        for term in terms:
            if not term or engine.norm(term) in engine.TAXONOMY_HEADS:
                attempt = _diagnostic_attempt(diagnostics, notes, entry=entry, term=term)
                _diagnostic_gate(attempt, 'index_term', 'not_applicable', {'reason': 'Empty or taxonomy-only Index head.'})
                if attempt is not None:
                    attempt['outcome'] = 'not_applicable'
                continue
            for span in proposal['evidence']:
                if span['status'] != 'valid' or span['context_index'] != 0:
                    attempt = _diagnostic_attempt(diagnostics, notes, entry=entry, term=term, span=span)
                    _diagnostic_gate(attempt, 'provider_span', 'failed', {
                        'reason': 'The provider span is not a valid span in the clinical source.'})
                    if attempt is not None:
                        attempt['outcome'] = 'held'
                    continue
                if not engine.affirmative_word(span['text'], term):
                    attempt = _diagnostic_attempt(diagnostics, notes, entry=entry, term=term, span=span)
                    _diagnostic_gate(attempt, 'source_lexical_link', 'not_applicable', {
                        'reason': 'This provider span does not contain the literal Index head.'})
                    if attempt is not None:
                        attempt['outcome'] = 'not_applicable'
                    continue
                for clause in engine.enclosing_clauses(notes, span['text']):
                    attempt = _diagnostic_attempt(diagnostics, notes, entry=entry, term=term, span=span, clause=clause)
                    anchor = description if engine.affirmative_word(span['text'], description) else term
                    concept = dict(id=proposal['id'], term=anchor, index_terms=[anchor], evidence=clause,
                        kind='symptom' if proposal['code'].startswith('R') else 'diagnosis',
                        certainty='confirmed', temporality='current', subject='patient', relevant=True,
                        missing_detail='', integral_to='')
                    nec = None
                    if contract in engine.GOVERNANCE_SOURCE_CONTRACTS:
                        from .coding_nec import prove
                        nec = prove(reference, entry, concept, notes, source_contract=contract)
                        if nec:
                            concept = nec[0]
                    subtypes = engine.index_subtypes(reference, concept, source_contract=contract)
                    qualifiers = [item['qualifier'] for item in subtypes]
                    scope_errors = (engine.current_source_scope_errors(notes, concept, source_contract=contract,
                        qualifiers=qualifiers) if modern else [])
                    _diagnostic_gate(attempt, 'source_scope', 'failed' if scope_errors else
                        'passed' if modern else 'not_applicable', {'errors': scope_errors})
                    if scope_errors:
                        for gate in ('source_disposition', 'contextual_validation', 'index_route',
                                     'specificity', 'more_specific_source_routes'):
                            _diagnostic_gate(attempt, gate, 'not_evaluated', {'blocked_by': 'source_scope'})
                        if attempt is not None:
                            attempt['outcome'] = 'held'
                        continue
                    assertion = engine.assertion_concept(concept, subtypes)
                    disposition, reason = (('eligible', 'Current source-bound narrower clinical concept and complete NEC route verified.')
                        if nec else engine.source_disposition(assertion, notes, qualifiers=qualifiers,
                            source_contract=contract))
                    _diagnostic_gate(attempt, 'source_disposition', 'passed' if disposition == 'eligible' else 'failed',
                        {'disposition': disposition, 'reason': reason, 'nec_proof': deepcopy(nec[1]) if nec else None})
                    check = engine.contextual_validation(run, reference, proposal['code'], concept, selected_codes)
                    _diagnostic_gate(attempt, 'contextual_validation',
                        'passed' if check['valid'] and not check.get('requires_review') else 'failed', check)
                    index_errors = ([] if nec else engine.index_route_errors(entry, concept, lookup,
                        code_description=description, source_contract=contract))
                    _diagnostic_gate(attempt, 'index_route', 'not_applicable' if nec else
                        'failed' if index_errors else 'passed', {'errors': index_errors,
                            'reason': 'Complete NEC proof substitutes this check.' if nec else ''})
                    specificity_errors = engine.specificity_errors(concept, proposal['code'], description)
                    _diagnostic_gate(attempt, 'specificity', 'failed' if specificity_errors else 'passed',
                        {'errors': specificity_errors})
                    errors = index_errors + specificity_errors
                    blocked = disposition != 'eligible' or errors or not check['valid'] or check.get('requires_review')
                    if blocked:
                        _diagnostic_gate(attempt, 'more_specific_source_routes', 'not_evaluated',
                            {'reason': 'Earlier failed requirement short-circuits this check.'})
                    else:
                        more_specific = engine.more_specific_source_routes(entry, concept, notes, reference, subtypes,
                            source_contract=contract)
                        _diagnostic_gate(attempt, 'more_specific_source_routes', 'failed' if more_specific else 'passed',
                            {'routes': more_specific})
                        blocked = more_specific
                    if blocked:
                        if attempt is not None:
                            attempt['outcome'] = 'held'
                        continue
                    candidate = dict(code=proposal['code'], system='ICD-10-CM', entry_id=entry['id'],
                        description=description, path=entry.get('path', []),
                        release_id=str(reference.release_id), release_version=reference.release.version,
                        instructions=check.get('instructions', []))
                    if nec:
                        candidate['clinical_specificity'] = nec[1]
                    if attempt is not None:
                        attempt['outcome'] = 'eligible'
                    return _diagnostic_finish(diagnostics, (concept, candidate, {'disposition': disposition, 'reason': reason,
                        'index_scope_entry_ids': nec[1]['index_family_ids'] if nec else [row['entry']['id'] for row in subtypes]}))
    if contract in engine.COMPLETE_SOURCE_CONTRACTS:
        from .coding_completeness import selected_qualified_route
        result = selected_qualified_route(run, reference, proposal, selected_codes)
        attempt = _diagnostic_attempt(diagnostics, notes)
        _diagnostic_gate(attempt, 'qualified_source_fallback', 'passed' if result[1] else 'failed',
            {'reason': 'Qualified source fallback returned a route.' if result[1] else
                'Qualified source fallback returned no verified route.', 'internal_checks': 'not_instrumented',
                'source_check': result[2]})
        if attempt is not None:
            attempt['outcome'] = 'eligible' if result[1] else 'held'
        return _diagnostic_finish(diagnostics, result)
    return _diagnostic_finish(diagnostics, (None, None, None))


def integral_holds(rows, notes, *, source_contract=None):
    concepts = [row['concept'] for row in rows if row.get('concept') and row.get('eligible')]
    dispositions = {concept['id']: 'eligible' for concept in concepts}
    held = {concept['id']: parent for concept in concepts
            if (parent := engine.integral_parent(concept, concepts, dispositions, notes))}
    # The cause need not have been selected (or returned) by Corti. Treat causal
    # language in the original source as a veto requiring review, without
    # inventing a diagnosis concept or promoting a candidate code. Ambiguous or
    # negated causal wording is deliberately held rather than interpreted here.
    for concept in concepts:
        if concept['kind'] != 'symptom' or concept['id'] in held:
            continue
        for clause, _, _ in engine.mention_clauses(notes, concept):
            if (source_contract == engine.QUALIFIED_SOURCE_CONTRACT
                    and engine.unknown_cause_attribute(clause, concept)
                    and not engine.current_source_scope_errors(notes, {**concept, 'evidence': clause},
                        source_contract=source_contract)):
                continue
            text = engine.norm(clause)
            for symptom in engine.anchors(concept):
                token = r'\b' + re.escape(symptom) + r'\b'
                if (re.search(r'\b(?:causes?|causing|manifested by|produces?)\b.{0,50}' + token, text)
                        or re.search(token + r'.{0,50}\b(?:due to|caused by|secondary to)\b\s+\w', text)):
                    held[concept['id']] = 'source-causal-wording'
    return held


def generate(run):
    if run.inputs.get('engine_contract') != CONTRACT:
        raise ValidationError('Corti requires its exact immutable engine contract.')
    request = corti_prediction.payload(run)
    response = corti_prediction.execute(run, request)
    return retained_result(run, request, response, run.requests[0]['response_sha256'])


def retained_result(run, request, response, response_sha256):
    """Validate provider output without sending or manufacturing a receipt."""
    if run.inputs.get('engine_contract') != CONTRACT:
        raise ValidationError('Corti requires its exact immutable engine contract.')
    if request != corti_prediction.payload(run):
        raise ValidationError('The retained prediction belongs to a different source payload.')
    diagnostic_contract = run.config.get('coding_diagnostic_contract')
    if diagnostic_contract not in (None, DIAGNOSTIC_CONTRACT):
        raise ValidationError('Unknown coding diagnostic contract.')
    from . import source_assertion_coding as shared
    if shared.enabled(run): shared.source(run)
    terms, cpt = terminology(run)
    replay = run.config['mode'] == 'replay'
    if replay:
        from django.conf import settings
        original_verdict = settings.CORTI_REPLAY_FIXTURE['original_verdict']
    else:
        original_verdict = 'NOT_EVALUATED'
    parsed = adapt_response(response, request, service_date=date.fromisoformat(run.inputs['service_date']),
        terminology=terms, original_verdict=original_verdict,
        source_response_sha256=response_sha256)
    icds = [p['code'] for p in parsed['proposed_selections'] if p['system'] == 'icd10cm-outpatient']
    reference = engine.reference_for(run, prediction_codes=icds)
    result = dict(contract=CONTRACT, suggestions=[], candidates={}, source_checks={},
        questions=[], excluded=[], global_blockers=identity_blockers(run),
        cpt=cpt, adapter=parsed, provider_request=request, replay=replay,
        original_verdict=original_verdict, claims_submitted=False,
        diagnostics_summary={'candidate_count': len(response.get('candidates', [])),
            'alternative_count': sum(len(r.get('alternatives', [])) for r in response['codes'] if isinstance(r, dict)),
            'rejected_selected_count': len(parsed['diagnostics']['rejected_selected'])})
    if diagnostic_contract:
        result['source_diagnostics'] = {'contract': diagnostic_contract, 'icd_routes': {}}
    if run.context.get('setting') != 'outpatient_office':
        result['global_blockers'].append('Confirm the US outpatient office setting before coding approval.')
    quarantined = []
    for rejected in parsed['diagnostics']['rejected_selected']:
        raw = rejected.get('raw')
        classification = corti_semantics.classify_selected(raw)
        if classification['system'] != 'HCPCS Level II':
            continue
        spans, status = corti_semantics.checked_spans(raw.get('evidences'), run.inputs['notes'])
        reason = ('Provider-labelled CPT selection has HCPCS Level II syntax. Dated HCPCS membership and '
                  'applicable service/quality-measure denominator, exclusions and reporting requirements '
                  'are unverified. A matching blood-pressure span alone does not establish quality-measure eligibility.')
        quarantined.append(dict(id=rejected['id'], system='HCPCS Level II', code=raw['code'].strip().upper(),
            description='', terminology={'status':'unavailable', 'reason':reason},
            provider_display=raw.get('display'), evidence_spans=spans, evidence_status=status,
            evidence=next((s['text'] for s in spans if s['status']=='valid'), ''), eligible=False,
            instructions=[], explanation=reason, hold_reasons=[reason], release_id='', release_version='',
            classification=classification, semantic_support={'status':'unverified_quality_or_service_eligibility'}))
    quarantined_ids = {r['id'] for r in quarantined}
    if any(r['id'] not in quarantined_ids for r in parsed['diagnostics']['rejected_selected']):
        result['global_blockers'].append('Malformed or duplicate provider selections require diagnostic review.')
    for proposal in parsed['proposed_selections']:
        term, system = proposal['terminology'], SYSTEMS[proposal['system']]
        row = dict(id=proposal['id'], system=system, code=proposal['code'],
            description=term.get('description') or '', terminology=deepcopy(term),
            provider_display=proposal['provider_display'], evidence_spans=deepcopy(proposal['evidence']),
            evidence=next((s['text'] for s in proposal['evidence'] if s['status'] == 'valid'), ''),
            evidence_status=proposal['evidence_status'], eligible=False, instructions=[],
            explanation='Selected by Corti. The provider returned source spans without a narrative explanation.',
            hold_reasons=[], release_id='', release_version=term.get('version') or '')
        row['classification'] = corti_semantics.classify_selected({'code':proposal['code'], 'system':proposal['system']})
        if row['classification']['mismatch']:
            row['hold_reasons'].append('The selected procedure identifier does not have supported CPT syntax.')
        if system == 'CPT':
            support = (shared.office_time_facts(run) if shared.enabled(run) else
                corti_semantics.office_time_facts(run.inputs['notes'], contract=run.config.get('clinical_source_contract')))
            row['semantic_support'] = {'status':'requires_dated_criteria', 'documented_time_facts':support,
                'provider_citation_adequacy':corti_semantics.citation_adequacy(row['evidence_spans'], support['facts'])}
        if proposal['evidence_status'] != 'valid':
            row['hold_reasons'].append('Supporting evidence is ' + proposal['evidence_status'] + '.')
        if term['status'] != 'verified':
            row['hold_reasons'].append(term['reason'])
        diagnostics = None
        if diagnostic_contract and system == 'ICD-10-CM':
            diagnostics = _route_diagnostics(run, reference, proposal)
            result['source_diagnostics']['icd_routes'][row['id']] = diagnostics
            if row['hold_reasons']:
                attempt = _diagnostic_attempt(diagnostics, run.inputs['notes'])
                _diagnostic_gate(attempt, 'provider_preconditions', 'failed', {
                    'evidence_status': proposal['evidence_status'], 'terminology': term,
                    'classification': row['classification'], 'reasons': row['hold_reasons']})
                _diagnostic_gate(attempt, 'icd_source_route', 'not_evaluated',
                    {'blocked_by': 'provider_preconditions'})
                attempt['outcome'] = 'held'
                _diagnostic_finish(diagnostics, (None, None, None))
        if not row['hold_reasons']:
            if system == 'ICD-10-CM':
                concept, candidate, source_check = _icd_source(run, reference, proposal, icds,
                    diagnostics=diagnostics)
                if candidate:
                    row.update(concept=concept, release_id=candidate['release_id'],
                        instructions=candidate['instructions'], evidence=concept['evidence'],
                        index_entry_id=candidate['entry_id'], index_path=candidate['path'], eligible=True,
                        explanation=('Checked source assertion: “'+concept['evidence']+'” Dated Index route: '
                            +' → '.join(candidate['path'])+'.' if shared.enabled(run) else
                            engine.source_explanation(run.inputs['notes'], concept, candidate)))
                    # This is an independently checked route for the SAME selected
                    # code, never a provider candidate or nested alternative.
                    result['candidates'][row['id']] = [candidate]
                    result['source_checks'][row['id']] = source_check
                else:
                    failure = diagnostics.get('initiating_failure') if diagnostics else None
                    if failure:
                        detail = failure['detail']
                        reasons = ([detail['reason']] if detail.get('reason') else
                                   detail.get('errors') or detail.get('reasons') or [])
                        row['hold_reasons'].append('The first attempted route was held at '
                            + failure['gate'] + ': ' + ' '.join(reasons)
                            + ' Review the retained route diagnostics; no alternative was promoted.')
                    else:
                        row['hold_reasons'].append('The selected code lacks a locally verified source-to-Index-to-Tabular route. Clarify the documentation; no alternative was promoted.')
            else:
                from .coding_cpt import validate_cpt_selection
                check = (validate_cpt_selection(run, row['code'], row['evidence'],evidence_spans=row['evidence_spans'])
                    if shared.enabled(run) else validate_cpt_selection(run,row['code'],row['evidence']))
                if check['valid'] and not check.get('requires_review'):
                    row.update(eligible=True, release_id=cpt['release_id'], instructions=check.get('instructions', []))
                else:
                    row['hold_reasons'].extend(check.get('errors') or ['Applicable licensed CPT instructions remain unresolved.'])
        if row['hold_reasons']:
            result['questions'].append({'id': row['id'], 'system': system, 'blocking': False,
                'question': 'Held ' + row['code'] + ': ' + ' '.join(row['hold_reasons'])})
        result['suggestions'].append(row)
    result['suggestions'].extend(quarantined)
    result['suggestions'].sort(key=lambda row: int(row['id'].split(':')[1]))
    for row in quarantined:
        result['questions'].append({'id':row['id'], 'system':row['system'], 'blocking':False,
            'question':'Held '+row['code']+': '+row['explanation']})
    held = (shared.integral_holds(run,result['suggestions']) if shared.enabled(run) else
        integral_holds(result['suggestions'], run.inputs['notes'],source_contract=run.config.get('clinical_source_contract')))
    for key, parent in held.items():
        row = next(row for row in result['suggestions'] if row['id'] == key)
        row['eligible'] = False
        reason = ('Source causal wording requires review before this symptom can be accepted separately; no cause code was promoted.'
            if parent == 'source-causal-wording' else 'Documented symptom is integral to the established diagnosis; not separately eligible.')
        row['hold_reasons'].append(reason)
        result['questions'].append({'id': key, 'system': 'ICD-10-CM', 'blocking': False, 'question': reason})
        result['source_checks'][key].update(disposition='integral', parent=parent)
    if diagnostic_contract:
        for row in result['suggestions']:
            diagnostics = result['source_diagnostics']['icd_routes'].get(row['id'])
            if diagnostics is not None:
                diagnostics['selection_outcome'] = 'eligible' if row['eligible'] else 'held'
                diagnostics['selection_hold_reasons'] = deepcopy(row['hold_reasons'])
    return result


def validate_selection(run, selections):
    from . import source_assertion_coding as shared
    if identity_blockers(run):
        raise ValidationError('The source patient identity requires review before code acceptance or export.')
    if (type(selections) is not dict or set(selections) != {'selected_ids', 'overrides'}
            or type(selections['selected_ids']) is not list or type(selections['overrides']) is not dict
            or selections['overrides']):
        raise ValidationError('Only Corti-selected, verified codes can be accepted; diagnostic alternatives are not selections.')
    ids = selections['selected_ids']
    if any(type(x) is not str for x in ids) or len(ids) != len(set(ids)):
        raise ValidationError('Invalid or duplicate Corti selection.')
    rows = {r['id']: r for r in run.result.get('suggestions', [])}
    held = (shared.integral_holds(run,list(rows.values())) if shared.enabled(run) else
        integral_holds(list(rows.values()),run.inputs['notes'],source_contract=run.config.get('clinical_source_contract')))
    if set(ids).intersection(held):
        raise ValidationError('An integral symptom cannot be accepted separately from its documented cause.')
    terms, _ = terminology(run)
    raw = run.result.get('adapter', {}).get('diagnostics', {}).get('provider_response')
    parsed = adapt_response(raw, run.result['provider_request'],
        service_date=date.fromisoformat(run.inputs['service_date']), terminology=terms)
    selected = {p['id']: p for p in parsed['proposed_selections']}
    for key in ids:
        row, proposal = rows.get(key), selected.get(key)
        if (not row or not proposal or row.get('eligible') is not True or row['code'] != proposal['code']
                or row['system'] != SYSTEMS[proposal['system']] or proposal['evidence_status'] != 'valid'
                or proposal['terminology']['status'] != 'verified'
                or row['description'] != proposal['terminology']['description']):
            raise ValidationError('A held, unsupported or unverified code cannot be accepted or exported.')
    # Reuse the same source, Index, Tabular and CPT entitlement/rule checks as
    # the existing workflow at BOTH approval and export boundaries.
    icd_ids = [key for key in ids if rows[key]['system'] == 'ICD-10-CM']
    if (shared.enabled(run) or run.config.get('clinical_source_contract') in engine.COMPLETE_SOURCE_CONTRACTS) and icd_ids:
        reference = engine.reference_for(run, prediction_codes=[rows[key]['code'] for key in icd_ids])
        codes = [rows[key]['code'] for key in icd_ids]
        for key in icd_ids:
            concept, candidate, checked = _icd_source(run, reference, selected[key], codes)
            if (not candidate or concept != rows[key].get('concept')
                    or candidate not in run.result.get('candidates', {}).get(key, [])
                    or checked != run.result.get('source_checks', {}).get(key)):
                raise ValidationError('The selected source and authoritative route proof changed.')
    if not shared.enabled(run):
        engine.validate_selection(run, {'selected_ids': icd_ids, 'overrides': {}})
    for key in ids:
        if rows[key]['system'] == 'CPT':
            from .coding_cpt import validate_cpt_selection
            checked = (validate_cpt_selection(run,rows[key]['code'],rows[key]['evidence'],evidence_spans=selected[key]['evidence'])
                if shared.enabled(run) else validate_cpt_selection(run, rows[key]['code'], rows[key]['evidence']))
            if not checked['valid'] or checked.get('requires_review') or checked.get('errors'):
                raise ValidationError('CPT eligibility, rights or dated selection criteria are unresolved.')
    codes = [(rows[key]['system'], rows[key]['code']) for key in ids]
    if len(codes) != len(set(codes)):
        raise ValidationError('Duplicate selected codes cannot be approved.')
    return {'selected_ids': sorted(ids), 'overrides': {}}
