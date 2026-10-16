"""A narrowly bound API-output review, independent of CPT catalogue entitlement.

Only an operator-installed assessment of one retained synthetic result can enter
this path. It does not predict, repair terminology, update context, or approve
anything on read. The original provider result and prior decisions remain intact.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction

from . import coding_service as service
from .models import CodingDecision, CodingOutputDecision, CodingRun
from .security import audit, membership

CONTRACT = 'synthetic-api-output-review-v1'
DESCRIPTION_STATUS = 'withheld_defective_provider_text'
REFERENCE_CONTRACT = 'synthetic-api-output-reference-v2'
FACT_LABELS = {'setting':'Setting', 'patient_status':'Patient status', 'time_minutes':'Total physician minutes',
    'time_same_day':'Time on date of service', 'time_qualified_clinician':'Physician time',
    'time_excludes_staff':'Staff time excluded',
    'time_excludes_separately_reported':'Separately reported services excluded', 'em_basis':'Selection basis'}


def need(condition, message):
    if not condition:
        raise ValidationError(message)


def assessment():
    path = getattr(settings, 'CORTI_OUTPUT_REVIEW_FILE', '')
    need(getattr(settings, 'SYNTHETIC_ONLY', False) and path,
         'No bounded synthetic output assessment is installed.')
    try:
        raw = Path(path).read_bytes()
        need(hashlib.sha256(raw).hexdigest() == getattr(settings, 'CORTI_OUTPUT_REVIEW_SHA256', ''),
             'The output assessment failed its integrity check.')
        value = json.loads(raw)
    except (OSError, ValueError, TypeError) as exc:
        raise ValidationError('The bounded output assessment is unavailable.') from exc
    need(type(value) is dict and value.get('contract') == CONTRACT, 'Unknown output assessment contract.')
    return value



def live_assessment(encounter, run):
    """Apply a small dated source assessment to a new selected API output.

    The bundle is an integrity-pinned internal synthetic evaluation scope. It
    does not provide or import a CPT catalogue, predict codes or waive review.
    """
    from . import corti_prediction
    from .corti_response import adapt_response
    from .corti_semantics import classify_selected, office_time_facts, citation_adequacy
    path = getattr(settings, 'CORTI_OUTPUT_REFERENCE_FILE', '')
    need(getattr(settings, 'SYNTHETIC_ONLY', False) and path,
         'No dated synthetic output reference is installed.')
    try:
        raw = Path(path).read_bytes()
        need(hashlib.sha256(raw).hexdigest() == getattr(settings, 'CORTI_OUTPUT_REFERENCE_SHA256', ''),
             'The synthetic output reference failed its integrity check.')
        bundle = json.loads(raw)
    except (OSError, ValueError, TypeError) as exc:
        raise ValidationError('The dated synthetic output reference is unavailable.') from exc
    need(type(bundle) is dict and bundle.get('contract') == REFERENCE_CONTRACT,
         'Unknown synthetic output reference contract.')
    need(bundle.get('review_execution') == 'agent_executed_synthetic',
         'This dedicated synthetic campaign must identify its automated review execution.')
    bounded = bundle.get('scope', {})
    need(type(bounded) is dict, 'The synthetic source scope is malformed.')
    need(str(encounter.created_by_id) in bounded.get('actor_ids', [])
         and str(run.user_id) in bounded.get('actor_ids', [])
         and hashlib.sha256(encounter.notes.encode()).hexdigest() in bounded.get('notes_sha256', [])
         and encounter.service_date.isoformat() in bounded.get('service_dates', []),
         'This actor, source note or service date is outside the authorized synthetic assessment.')
    need(run.config.get('provider') == 'corti' and run.config.get('mode') == 'live'
         and run.result.get('replay') is False and not run.result.get('global_blockers')
         and run.state in ('succeeded', 'needs_detail') and encounter.status == 'finalized',
         'Only a finalized supported synthetic direct-prediction result is covered.')
    need(len(run.requests) == 1, 'The synthetic result must have one retained prediction receipt.')
    receipt = run.requests[0]
    request = corti_prediction.payload(run)
    envelope = receipt.get('envelope') or {}
    need(type(envelope) is dict and envelope.get('protocol') == corti_prediction.PROTOCOL
         and envelope.get('identity') == corti_prediction.receipts._identity(run)
         and envelope.get('config') == run.config and envelope.get('payload') == request
         and receipt.get('request_sha256') == hashlib.sha256(corti_prediction.receipts.encode(request)).hexdigest()
         and receipt.get('stage') == corti_prediction.STAGE and receipt.get('attempt') == 1
         and receipt.get('provider') == 'corti',
         'The retained request does not match this source, date, coding systems and immutable run identity.')
    response = receipt.get('raw_response') or {}
    body = response.get('body', '')
    need(receipt.get('state') == 'succeeded' and receipt.get('sent') is True
         and receipt.get('simulated') is False and response.get('redacted') is False
         and type(body) is str and hashlib.sha256(body.encode()).hexdigest() == receipt.get('response_sha256'),
         'The live selected output has no intact successful provider receipt.')
    try:
        provider_response = json.loads(body)
        selected = provider_response['codes']
        adapted = adapt_response(provider_response, request, service_date=encounter.service_date)
    except (ValueError, KeyError, TypeError) as exc:
        raise ValidationError('The retained selected-code collection is unavailable.') from exc
    need(type(selected) is list, 'The retained selected-code collection is malformed.')
    support = office_time_facts(encounter.notes)
    need(support['status'] == 'documented', '; '.join(support['blockers']) or 'Office time support is unresolved.')
    facts = [{**fact, 'label': FACT_LABELS[fact['key']]} for fact in support['facts']]
    values = {fact['key']:fact['value'] for fact in facts}
    entries = bundle.get('entries', [])
    need(type(entries) is list and all(type(e) is dict for e in entries)
         and len({e.get('code') for e in entries}) == len(entries),
         'The bounded source entries are missing or duplicated.')
    matches = []
    for row in run.result.get('suggestions', []):
        identifier = row.get('id', '')
        if row.get('system') != 'CPT' or not re.fullmatch(r'selected:[0-9]+', identifier):
            continue
        index = int(identifier.split(':')[1])
        if index >= len(selected) or type(selected[index]) is not dict:
            continue
        actual = selected[index]
        classification = classify_selected(actual)
        if (classification['system'] != 'CPT' or classification['mismatch']
                or actual.get('system') != 'cpt' or actual.get('code', '').strip() != row.get('code')):
            continue
        if sum(type(item) is dict and item.get('system') == 'cpt'
               and type(item.get('code')) is str and item['code'].strip() == row['code'] for item in selected) != 1:
            continue
        original = next((p for p in adapted['proposed_selections'] if p['id'] == identifier), None)
        if original is None:
            continue
        original_spans, integrity = original['evidence'], original['evidence_status']
        keys = ('context_index', 'start', 'end', 'text', 'status')
        if (integrity != 'valid' or [{key: span.get(key) for key in keys} for span in original_spans]
                != [{key: span.get(key) for key in keys} for span in row.get('evidence_spans', [])]):
            continue
        entry = next((e for e in entries if e.get('code') == row['code'] and e.get('system') == 'CPT'), None)
        if entry is None or encounter.service_date.isoformat() not in entry.get('service_dates', []):
            continue
        criteria = entry.get('criteria', {})
        if (criteria.get('basis') != 'documented_total_time'
                or type(criteria.get('minimum_minutes')) is not int or type(criteria.get('maximum_minutes')) is not int
                or type(values.get('time_minutes')) is not int
                or not criteria['minimum_minutes'] <= values['time_minutes'] <= criteria['maximum_minutes']
                or any(values.get(key) != criteria.get(key) for key in ('setting', 'patient_status', 'em_basis'))):
            continue
        matches.append((row, entry, criteria))
    need(len(matches) == 1, 'No unique provider-selected code meets the bounded dated source criteria.')
    row, entry, criteria = matches[0]
    need(entry.get('description_status') == DESCRIPTION_STATUS,
         'This source route cannot verify or reproduce the provider description.')
    scope = {'encounter_id': str(encounter.pk), 'patient_id': str(encounter.patient_id),
             'run_id': str(run.pk), 'input_digest': run.input_digest,
             'result_digest': service.digest(run.result), 'requests_digest': service.digest(run.requests),
             'notes_sha256': hashlib.sha256(encounter.notes.encode()).hexdigest(),
             'service_date': encounter.service_date.isoformat()}
    return {'contract': CONTRACT, 'binding_kind': 'live_synthetic_reference',
        'reference_digest': service.digest(bundle), 'authorized_actor_ids': bounded['actor_ids'],
        'review_execution': bundle['review_execution'],
        'scope': scope, 'identifier': row['id'], 'response_sha256': receipt['response_sha256'],
        'selection': {'status':'supported', 'code':row['code'], **criteria},
        'description_status': DESCRIPTION_STATUS, 'facts': facts,
        'coverage': {**entry['coverage'], 'service_date': encounter.service_date.isoformat()},
        'sources': entry['sources'], 'permission': bundle.get('permission', {}),
        'source_summary': bundle['source_summary'], 'permission_summary': bundle['permission_summary'],
        'provider_citation_adequacy': citation_adequacy(row.get('evidence_spans', []), facts),
        'evidence_origin': 'independently_checked_saved_note_time_facts'}

def reviewed(encounter, run, base_decision=None):
    """Validate every binding again on display, decision and download."""
    need(run is not None and run.encounter_id == encounter.pk, 'No retained result belongs to this encounter.')
    service.assert_current(run, encounter)
    live = run.config.get('mode') == 'live'
    a = live_assessment(encounter, run) if live else assessment()
    scope = a.get('scope', {})
    need(scope == {'encounter_id': str(encounter.pk), 'patient_id': str(encounter.patient_id),
                   'run_id': str(run.pk), 'input_digest': run.input_digest,
                   'result_digest': service.digest(run.result),
                   'requests_digest': service.digest(run.requests),
                   'notes_sha256': hashlib.sha256(encounter.notes.encode()).hexdigest(),
                   'service_date': encounter.service_date.isoformat()},
         'This assessment does not cover the current patient, note, date and retained result.')
    if not live:
        need(run.config.get('provider') == 'corti' and run.config.get('mode') == 'replay'
             and run.result.get('replay') is True and not run.result.get('global_blockers')
             and encounter.status == 'finalized', 'Only the finalized, supported synthetic replay is covered.')
    need(len(run.requests) == 1 and run.requests[0].get('response_sha256') == a.get('response_sha256'),
         'The retained response does not match the assessed output.')
    rows = [r for r in run.result.get('suggestions', []) if r.get('id') == a.get('identifier')]
    need(len(rows) == 1, 'The assessed selected output is missing or ambiguous.')
    row = rows[0]
    selection = a.get('selection', {})
    need(row.get('system') == 'CPT' and row.get('code') == selection.get('code')
         and selection.get('status') == 'supported' and selection.get('basis') == 'documented_total_time'
         and row.get('evidence_status') == 'valid', 'This selected code lacks a supported assessment.')
    need(a.get('description_status') == DESCRIPTION_STATUS, 'The descriptor remains withheld, never verified by this route.')
    coverage = a.get('coverage', {})
    need(coverage.get('service_date') == encounter.service_date.isoformat()
         and coverage.get('status') == 'dated_code_presence_and_case_criteria'
         and coverage.get('cms_code_status') == 'A'
         and all(coverage.get(k) for k in ('cms_release', 'cms_release_date', 'criteria_source', 'date_limit')),
         'Dated code presence or applicable case criteria are unresolved.')
    permission = a.get('permission', {})
    need(permission.get('status') == 'bounded_api_output' and permission.get('scope') == 'internal_fictional_review'
         and permission.get('terms_version') == '4' and permission.get('sections') == ['2.6.1.1', '2.6.2', '2.7']
         and permission.get('contradictory_restriction') is None and permission.get('source_url')
         and permission.get('record_sha256'), 'The bounded API-output permission basis is unavailable or restricted.')
    sources = a.get('sources', [])
    need({s.get('role') for s in sources} == {'dated_code_presence', 'em_rules', 'code_specific_time'}
         and all(s.get('url') and s.get('evidence_sha256') and s.get('edition') for s in sources),
         'Required source provenance is incomplete.')
    facts = a.get('facts', [])
    required = {'setting', 'patient_status', 'time_minutes', 'time_same_day', 'time_qualified_clinician',
                'time_excludes_staff', 'time_excludes_separately_reported', 'em_basis'}
    need(len(facts) == len(required) and {f.get('key') for f in facts} == required,
         'The documented time-review facts are incomplete.')
    values = {f['key']: f.get('value') for f in facts}
    need(values['setting'] == 'outpatient_office' and values['patient_status'] == 'established'
         and values['em_basis'] == 'time' and type(values['time_minutes']) is int
         and type(selection.get('minimum_minutes')) is int and type(selection.get('maximum_minutes')) is int
         and selection['minimum_minutes'] <= values['time_minutes'] <= selection['maximum_minutes']
         and all(values[k] is True for k in required if k.startswith('time_') and k != 'time_minutes'),
         'Documented facts do not meet the assessed selection criteria.')
    for f in facts:
        start, end = f.get('start'), f.get('end')
        need(f.get('source') == 'saved note' and type(start) is int and type(end) is int
             and 0 <= start < end <= len(encounter.notes) and encounter.notes[start:end] == f.get('quote'),
             'A review fact has no exact provenance in the saved note.')
    spans = row.get('evidence_spans', [])
    need(bool(spans), 'Supporting provider evidence is missing.')
    contexts = [encounter.notes]
    if live:
        from .corti_prediction import payload
        contexts = [c['text'] for c in payload(run)['context']]
    for span in spans:
        start, end, context_index = span.get('start'), span.get('end'), span.get('context_index')
        need(span.get('status') == 'valid' and type(context_index) is int and 0 <= context_index < len(contexts)
             and type(start) is int and type(end) is int and 0 <= start < end <= len(contexts[context_index])
             and contexts[context_index][start:end] == span.get('text'), 'Supporting provider evidence is invalid.')
    provider_spans = copy.deepcopy(spans)
    if live:
        # Source-substring validity is only an integrity check. The appendix
        # carries the separately established complete note facts, including the
        # time and exclusions omitted by inadequate provider citations.
        spans = []
        for fact in facts:
            span = {'context_index':0, 'start':fact['start'], 'end':fact['end'],
                    'text':fact['quote'], 'status':'valid', 'source':'independently_checked_saved_note'}
            if span not in spans: spans.append(span)
    decisions = list(CodingDecision.objects.filter(run=run)[:2])
    need(len(decisions) == 1, 'The prior coding decision must remain unambiguous.')
    base = decisions[0]
    need(base.input_digest == run.input_digest and base.selections == run.selection
         and base.selection_digest == service.selection_digest(run)
         and (base_decision is None or base_decision.pk == base.pk), 'The prior coding decision changed.')
    need(a['identifier'] not in base.selections.get('selected_ids', []),
         'The supplemental output must not duplicate a prior accepted code.')
    review = {'contract': CONTRACT, 'assessment_digest': service.digest(a), 'scope': scope,
              'base_decision_id': str(base.pk), 'base_selection_digest': base.selection_digest,
              'identifier': a['identifier'], 'code': row['code'], 'system': 'CPT',
              'selection': selection, 'description_status': DESCRIPTION_STATUS,
              'coverage': coverage, 'sources': sources, 'permission': permission,
              'facts': facts, 'evidence_spans': spans}
    if live:
        review.update(reference_digest=a['reference_digest'], authorized_actor_ids=a['authorized_actor_ids'],
            evidence_origin=a['evidence_origin'], provider_evidence_spans=provider_spans,
            provider_citation_adequacy=a['provider_citation_adequacy'], provider_mode='live',
            review_execution=a['review_execution'])
    return a, review, base


def review_binding(review, user):
    return {'actor': str(user.pk), 'review_digest': service.digest(review)}


def view(encounter, run, user):
    if not (getattr(settings, 'CORTI_OUTPUT_REVIEW_FILE', '')
            or getattr(settings, 'CORTI_OUTPUT_REFERENCE_FILE', '')):
        return None
    try:
        a, review, base = reviewed(encounter, run)
    except ValidationError as exc:
        return {'available': False, 'reason': '; '.join(exc.messages)}
    key = service.digest(review)
    decision = CodingOutputDecision.objects.filter(run=run, review_digest=key).select_related('user').first()
    if decision and (decision.review != review or decision.base_decision_id != base.pk
                     or (decision.outcome == 'accepted' and not decision.facts_confirmed)):
        return {'available': False, 'reason': 'The supplemental decision failed its binding check.'}
    can_edit = (membership(user, encounter.department).role in ('owner', 'clinician')
        and ('authorized_actor_ids' not in review or str(user.pk) in review['authorized_actor_ids']))
    return {'available': True, 'reason': '', 'code': review['code'], 'identifier': review['identifier'],
            'selection_status': 'supported', 'description_status': DESCRIPTION_STATUS,
            'permission_status': 'bounded_api_output', 'state': decision.outcome if decision else 'pending',
            'facts': review['facts'], 'evidence_spans': review['evidence_spans'],
            'provider_citation_adequacy': review.get('provider_citation_adequacy'),
            'review_execution': review.get('review_execution', 'clinician_recorded'),
            'evidence_origin': review.get('evidence_origin', 'retained_provider_spans'),
            'source_summary': a['source_summary'], 'sources': a['sources'],
            'permission_summary': a['permission_summary'], 'review_digest': key,
            'display_token': signing.dumps(review_binding(review, user), salt=CONTRACT, compress=True),
            'can_decide': can_edit and decision is None, 'decision': decision}


@transaction.atomic
def decide(encounter, run, user, display_token, outcome, confirmed):
    e = service.locked_encounter(encounter, user, clinician=True)
    run = CodingRun.objects.select_for_update().get(pk=run.pk, encounter=e)
    _, review, base = reviewed(e, run)
    need('authorized_actor_ids' not in review or str(user.pk) in review['authorized_actor_ids'],
         'This account is outside the bounded synthetic output review.')
    try:
        binding = signing.loads(display_token, salt=CONTRACT, max_age=12 * 60 * 60)
    except signing.BadSignature as exc:
        raise ValidationError('The output review expired. Reopen the saved review.') from exc
    need(binding == review_binding(review, user), 'The output review changed; nothing was saved.')
    need(outcome in ('accepted', 'rejected'), 'Choose accept or reject explicitly.')
    need(type(confirmed) is bool and (outcome == 'rejected' or confirmed),
         'Confirm the displayed documented facts before accepting this code number.')
    key = service.digest(review)
    previous = CodingOutputDecision.objects.filter(run=run, review_digest=key).first()
    if previous:
        need(previous.review == review and previous.outcome == outcome, 'This review already has a saved decision.')
        return previous
    decision = CodingOutputDecision.objects.create(run=run, base_decision=base, user=user,
        review_digest=key, outcome=outcome, review=copy.deepcopy(review), facts_confirmed=confirmed)
    audit(user, 'coding.output_decided', decision.pk, department=e.department,
          run_id=str(run.pk), review_digest=key, outcome=outcome, facts_confirmed=confirmed,
          review_execution=review.get('review_execution', 'clinician_recorded'))
    return decision


def accepted_output_rows(encounter, run, base_decision):
    decisions = list(CodingOutputDecision.objects.filter(run=run, outcome='accepted'))
    if not decisions:
        return []
    _, review, base = reviewed(encounter, run, base_decision)
    matches = [d for d in decisions if d.review_digest == service.digest(review) and d.review == review
               and d.base_decision_id == base.pk and d.facts_confirmed]
    need(len(matches) == 1 and len(decisions) == 1, 'The accepted output review no longer matches its source assessment.')
    return [{'system': 'CPT', 'code': review['code'], 'description': '',
             'description_status': DESCRIPTION_STATUS, 'evidence_spans': copy.deepcopy(review['evidence_spans']),
             'selection_support': review['selection'], 'sources': review['sources'],
             'permission_basis': review['permission'], 'review_digest': matches[0].review_digest,
             'review_execution': review.get('review_execution', 'clinician_recorded'),
             'provider_mode': review.get('provider_mode', 'replay'),
             'output_decision_id': str(matches[0].pk), 'coverage': review['coverage']}]
