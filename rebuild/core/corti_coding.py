"""Bridge selected Corti predictions into the existing revision-bound review.

The retained offline adapter remains unchanged. This layer independently checks
dated reference membership, source assertions and applicable local coding rules.
Provider candidates/alternatives never become clinician replacement choices.
"""
from copy import deepcopy
from datetime import date
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

from . import coding_engine as engine, coding_terminology, corti_prediction
from .corti_response import CatalogRelease, DatedTerminology, adapt_response
from .coding_licensing import cpt_status
from .models import Code, CodeSet
from . import corti_semantics

CONTRACT = 'corti-selected-dated-review-v1'
SYSTEMS = {'icd10cm-outpatient': 'ICD-10-CM', 'cpt': 'CPT'}


def identity_blockers(run):
    """Source identity without an additional inference call or registry filling.

    Use existing validated answer identity facts when present. Generic notes
    accept only finite, complete source name frames; everything else requires
    the existing explicit synthetic identity review, never silent substitution.
    """
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


def _icd_source(run, reference, proposal, selected_codes):
    """Bind the selected code to dated lexical routes and the complete source.

    New runs recognize reference-owned head vocabulary and specific Tabular
    phrases. Historical runs retain their original route contract. Neither
    branch promotes a provider alternative or treats membership as eligibility.
    """
    lookup = engine.index_lookup(reference)
    notes = run.inputs['notes']
    contract = run.config.get('clinical_source_contract') if hasattr(run, 'config') else None
    modern = contract == engine.SOURCE_CONTRACT
    matching = [entry for entry in reference.index if entry.get('code') == proposal['code']
                and not entry.get('requires_review')]
    for entry in matching:
        head = entry
        while head.get('parent_id') in lookup:
            head = lookup[head['parent_id']]
        description = proposal['terminology']['description']
        terms = (engine.index_head_terms(head, description) if modern else
                 [re.sub(r'\(s\)$', '', head.get('term', ''), flags=re.I)])
        for term in terms:
            if not term or engine.norm(term) in engine.TAXONOMY_HEADS:
                continue
            for span in proposal['evidence']:
                if span['status'] != 'valid' or span['context_index'] != 0:
                    continue
                if not engine.affirmative_word(span['text'], term):
                    continue
                for clause in engine.enclosing_clauses(notes, span['text']):
                    anchor = description if engine.affirmative_word(span['text'], description) else term
                    concept = dict(id=proposal['id'], term=anchor, index_terms=[anchor], evidence=clause,
                        kind='symptom' if proposal['code'].startswith('R') else 'diagnosis',
                        certainty='confirmed', temporality='current', subject='patient', relevant=True,
                        missing_detail='', integral_to='')
                    if modern and engine.current_source_scope_errors(notes, concept):
                        continue
                    subtypes = engine.index_subtypes(reference, concept, source_contract=contract)
                    qualifiers = [item['qualifier'] for item in subtypes]
                    assertion = engine.assertion_concept(concept, subtypes)
                    disposition, reason = engine.source_disposition(assertion, notes, qualifiers=qualifiers)
                    check = engine.contextual_validation(run, reference, proposal['code'], concept, selected_codes)
                    errors = (engine.index_route_errors(entry, concept, lookup, code_description=description,
                                  source_contract=contract)
                              + engine.specificity_errors(concept, proposal['code'], description))
                    if (disposition != 'eligible' or errors or not check['valid'] or check.get('requires_review')
                            or engine.more_specific_source_routes(entry, concept, notes, reference, subtypes)):
                        continue
                    candidate = dict(code=proposal['code'], system='ICD-10-CM', entry_id=entry['id'],
                        description=description, path=entry.get('path', []),
                        release_id=str(reference.release_id), release_version=reference.release.version,
                        instructions=check.get('instructions', []))
                    return concept, candidate, {'disposition': disposition, 'reason': reason,
                        'index_scope_entry_ids': [row['entry']['id'] for row in subtypes]}
    return None, None, None


def integral_holds(rows, notes):
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
    reference = engine.reference_for(run)
    result = dict(contract=CONTRACT, suggestions=[], candidates={}, source_checks={},
        questions=[], excluded=[], global_blockers=identity_blockers(run),
        cpt=cpt, adapter=parsed, provider_request=request, replay=replay,
        original_verdict=original_verdict, claims_submitted=False,
        diagnostics_summary={'candidate_count': len(response.get('candidates', [])),
            'alternative_count': sum(len(r.get('alternatives', [])) for r in response['codes'] if isinstance(r, dict)),
            'rejected_selected_count': len(parsed['diagnostics']['rejected_selected'])})
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
    icds = [p['code'] for p in parsed['proposed_selections'] if p['system'] == 'icd10cm-outpatient']
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
            support = corti_semantics.office_time_facts(run.inputs['notes'],
                contract=run.config.get('clinical_source_contract'))
            row['semantic_support'] = {'status':'requires_dated_criteria', 'documented_time_facts':support,
                'provider_citation_adequacy':corti_semantics.citation_adequacy(row['evidence_spans'], support['facts'])}
        if proposal['evidence_status'] != 'valid':
            row['hold_reasons'].append('Supporting evidence is ' + proposal['evidence_status'] + '.')
        if term['status'] != 'verified':
            row['hold_reasons'].append(term['reason'])
        if not row['hold_reasons']:
            if system == 'ICD-10-CM':
                concept, candidate, source_check = _icd_source(run, reference, proposal, icds)
                if candidate:
                    row.update(concept=concept, release_id=candidate['release_id'],
                        instructions=candidate['instructions'], evidence=concept['evidence'],
                        index_entry_id=candidate['entry_id'], index_path=candidate['path'], eligible=True,
                        explanation=engine.source_explanation(run.inputs['notes'], concept, candidate))
                    # This is an independently checked route for the SAME selected
                    # code, never a provider candidate or nested alternative.
                    result['candidates'][row['id']] = [candidate]
                    result['source_checks'][row['id']] = source_check
                else:
                    row['hold_reasons'].append('The selected code lacks a locally verified source-to-Index-to-Tabular route. Clarify the documentation; no alternative was promoted.')
            else:
                from .coding_cpt import validate_cpt_selection
                check = validate_cpt_selection(run, row['code'], row['evidence'])
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
    for key, parent in integral_holds(result['suggestions'], run.inputs['notes']).items():
        row = next(row for row in result['suggestions'] if row['id'] == key)
        row['eligible'] = False
        reason = ('Source causal wording requires review before this symptom can be accepted separately; no cause code was promoted.'
            if parent == 'source-causal-wording' else 'Documented symptom is integral to the established diagnosis; not separately eligible.')
        row['hold_reasons'].append(reason)
        result['questions'].append({'id': key, 'system': 'ICD-10-CM', 'blocking': False, 'question': reason})
        result['source_checks'][key].update(disposition='integral', parent=parent)
    return result


def validate_selection(run, selections):
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
    if set(ids).intersection(integral_holds(list(rows.values()), run.inputs['notes'])):
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
    engine.validate_selection(run, {'selected_ids': icd_ids, 'overrides': {}})
    for key in ids:
        if rows[key]['system'] == 'CPT':
            from .coding_cpt import validate_cpt_selection
            checked = validate_cpt_selection(run, rows[key]['code'], rows[key]['evidence'])
            if not checked['valid'] or checked.get('requires_review') or checked.get('errors'):
                raise ValidationError('CPT eligibility, rights or dated selection criteria are unresolved.')
    codes = [(rows[key]['system'], rows[key]['code']) for key in ids]
    if len(codes) != len(set(codes)):
        raise ValidationError('Duplicate selected codes cannot be approved.')
    return {'selected_ids': sorted(ids), 'overrides': {}}
