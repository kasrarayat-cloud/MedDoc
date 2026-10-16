"""A narrowly bound API-output review, independent of CPT catalogue entitlement.

Only an operator-installed assessment of one retained synthetic result can enter
this path. It does not predict, repair terminology, update context, or approve
anything on read. The original provider result and prior decisions remain intact.
"""
import copy
import hashlib
import json
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


def reviewed(encounter, run, base_decision=None):
    """Validate every binding again on display, decision and download."""
    a = assessment()
    need(run is not None and run.encounter_id == encounter.pk, 'No retained result belongs to this encounter.')
    service.assert_current(run, encounter)
    scope = a.get('scope', {})
    need(scope == {'encounter_id': str(encounter.pk), 'patient_id': str(encounter.patient_id),
                   'run_id': str(run.pk), 'input_digest': run.input_digest,
                   'result_digest': service.digest(run.result),
                   'requests_digest': service.digest(run.requests),
                   'notes_sha256': hashlib.sha256(encounter.notes.encode()).hexdigest(),
                   'service_date': encounter.service_date.isoformat()},
         'This assessment does not cover the current patient, note, date and retained result.')
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
    for span in spans:
        start, end = span.get('start'), span.get('end')
        need(span.get('status') == 'valid' and span.get('context_index') == 0
             and type(start) is int and type(end) is int and 0 <= start < end <= len(encounter.notes)
             and encounter.notes[start:end] == span.get('text'), 'Supporting provider evidence is invalid.')
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
    return a, review, base


def review_binding(review, user):
    return {'actor': str(user.pk), 'review_digest': service.digest(review)}


def view(encounter, run, user):
    if not getattr(settings, 'CORTI_OUTPUT_REVIEW_FILE', ''):
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
    can_edit = membership(user, encounter.department).role in ('owner', 'clinician')
    return {'available': True, 'reason': '', 'code': review['code'], 'identifier': review['identifier'],
            'selection_status': 'supported', 'description_status': DESCRIPTION_STATUS,
            'permission_status': 'bounded_api_output', 'state': decision.outcome if decision else 'pending',
            'facts': review['facts'], 'evidence_spans': review['evidence_spans'],
            'source_summary': a['source_summary'], 'sources': a['sources'],
            'permission_summary': a['permission_summary'], 'review_digest': key,
            'display_token': signing.dumps(review_binding(review, user), salt=CONTRACT, compress=True),
            'can_decide': can_edit and decision is None, 'decision': decision}


@transaction.atomic
def decide(encounter, run, user, display_token, outcome, confirmed):
    e = service.locked_encounter(encounter, user, clinician=True)
    run = CodingRun.objects.select_for_update().get(pk=run.pk, encounter=e)
    _, review, base = reviewed(e, run)
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
          run_id=str(run.pk), review_digest=key, outcome=outcome, facts_confirmed=confirmed)
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
             'output_decision_id': str(matches[0].pk), 'coverage': review['coverage']}]
