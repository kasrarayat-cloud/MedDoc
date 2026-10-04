"""Prepared two-child ordinary-form qualification through the standing QA door.

No import performs credential reads, database access or requests. Every actual
child uses the existing standing attempt ledger, capture and transport guard.
This supplemental case never replaces the historical notes or voice plans.
"""
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from decimal import Decimal
import hashlib
import json

try:
    from . import provider_campaign as pc, sonnet5_qa as sq, sonnet5_stages as stages
except ImportError:
    import provider_campaign as pc, sonnet5_qa as sq, sonnet5_stages as stages

BASE = Path(__file__).resolve().parent
FORM = 'ordinary-batch-101-v1'
MANIFEST = BASE / 'fixtures' / (FORM + '.json')
MANIFEST_SHA = '32a57c72f26096c5ce6f76a7ccaec7654b0a9a06ada879b14b84c7cd2b191672'
ORIGINAL_SHA = 'a1d10b321d523a0932070003e4ffaf1020515efaf0a919392c4e6f195a1ad59a'
FIRST = 'ordinary_batch:part-1'
SECOND = 'ordinary_batch:part-2'
PATHS = ('ordinary_batch_first', 'ordinary_batch_second')
PRICING = 'ordinary_notes_field_relations'
require = pc.require


def runner_files():
    try:
        from .standing_qa import watched_hashes
    except ImportError:
        from standing_qa import watched_hashes
    return watched_hashes()


def frozen_inputs():
    raw = MANIFEST.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA, 'The supplemental batch fixture manifest changed.')
    manifest = json.loads(raw)
    original = (MANIFEST.parent / (FORM + '.docx')).read_bytes()
    require(hashlib.sha256(original).hexdigest() == ORIGINAL_SHA == manifest['original_sha256'],
            'The project-authored original changed.')
    require(hashlib.sha256(manifest['notes'].encode()).hexdigest() == manifest['notes_sha256'],
            'The supplemental source notes changed.')
    return {'batch': manifest, 'freeze': {'manifest_sha256': MANIFEST_SHA,
            'frozen_files': {str(MANIFEST): MANIFEST_SHA}, 'supplemental_previously_exposed': False}}


def original_bytes():
    frozen_inputs()
    return (MANIFEST.parent / (FORM + '.docx')).read_bytes()


def plan_sends(inputs=None):
    inputs = frozen_inputs() if inputs is None else inputs
    require(inputs.get('batch') == frozen_inputs()['batch'], 'Only the exact frozen supplemental source is eligible.')
    return [stages.Send(i + 1, identity, 'generation', FORM, PATHS[i], 'ordinary_batch', FORM, PRICING)
            for i, identity in enumerate((FIRST, SECOND))]


def send_inputs(send, inputs):
    require(send in plan_sends(inputs), 'Only the two exact supplemental child identities are eligible.')
    return {'form_sha256': ORIGINAL_SHA, 'notes_sha256': inputs['batch']['notes_sha256']}


def build_forms(target, inputs):
    target = pc.private_directory(target)
    data = original_bytes()
    file = target / (FORM + '.docx')
    if file.exists():
        require(not file.is_symlink() and file.read_bytes() == data, 'An existing batch original changed.')
    else:
        pc.write_new(file, data, raw=True)
    return {FORM: data}


def compiled_plan(inputs, fields):
    from core import generation as g, generation_batch as b
    require(len(fields) == 101 and [f['label'] for f in fields] ==
            ['Current symptoms'] + [f'Clinical detail {i:03d}' for i in range(2, 101)] + ['Plan'],
            'The actual original must identify all 101 destinations without correction.')
    version = SimpleNamespace(pk=UUID(int=2), contract='v3', fields=fields, review_requirements=[],
        template=SimpleNamespace(sha256=ORIGINAL_SHA), generation_constraints=None)
    encounter = SimpleNamespace(pk=UUID(int=1), revision=0, notes=inputs['batch']['notes'], template_version=version)
    config = g.configuration(fields)
    require(config.get('ordinary_field_contract') == inputs['batch']['ordinary_contract']
            and config.get('generation_batch_contract') is None and config['model'] == inputs['batch']['model']
            and config['request_profile']['max_output_tokens'] == 20000,
            'The supplemental case requires the exact ordinary-v4 Sonnet5.5 profile with generic batches off.')
    plan = b.plan_for(encounter, config)
    require(b.needed(fields, encounter.notes, config)
            and [len(p['field_ids']) for p in plan['parts']] == [100, 1],
            'The frozen physical catalogue must produce exactly two bounded children.')
    return plan


def price_sends(sends, inputs, state_dir, declaration, limits):
    from django.test import override_settings
    from documents.service import inspect_template
    build_forms(Path(state_dir) / 'forms', inputs)
    path = Path(state_dir) / 'forms' / (FORM + '.docx')
    with override_settings(**stages.steps.PATH_FLAGS['field_relations']):
        inspected = inspect_template(path, engine='v3')
        plan = compiled_plan(inputs, inspected['fields'])
    result = {}
    for send in sends:
        send_inputs(send, inputs)
        part = plan['parts'][0 if send.id == FIRST else 1]
        config = plan['config']
        require(config['pricing_version'] == declaration.pricing_version(PRICING), 'The batch price changed.')
        require(stages.within_bounds(config['request_profile'], declaration.expect(limits)),
                'The actual child profile exceeds the declared technical bounds.')
        maximum = Decimal(part['maximum_cost'])
        result[send.id] = {'maximum_cost': maximum, 'bound': pc.attempt_bound(maximum),
            'pricing_version': config['pricing_version'], 'max_output_tokens': 20000,
            'timeout_seconds': config['request_profile']['timeout_seconds'],
            'request_sha256': part['request_sha256'], 'parts': 2}
    return result


def usefulness(fields, answers, manifest):
    """Fixed actual-source expectations; missing answers never become assertions."""
    expected = manifest['desired_supported']
    outcomes = {}
    for field in fields:
        row = answers.get(field['key'], {})
        if field['label'] in expected:
            if row.get('status') == 'supported' and row.get('text') == expected[field['label']]:
                outcomes[field['key']] = 'supported_correct'
            elif row.get('status') == 'supported':
                outcomes[field['key']] = 'unsupported_accepted'
            else:
                outcomes[field['key']] = 'held_unadjudicated'
        elif row.get('status') == 'missing' and not row.get('text'):
            outcomes[field['key']] = 'missing'
        elif row.get('status') == 'supported' or row.get('text'):
            outcomes[field['key']] = 'unsupported_accepted'
        else:
            outcomes[field['key']] = 'held_unadjudicated'
    return outcomes


def child_class(state, receipt, usage, captured, deadline):
    if deadline:
        return 'uncertain'
    if receipt and usage and state in ('staged', 'succeeded', 'failed'):
        return 'completed'
    return 'reconciliation' if state == 'reconciliation' else 'uncertain'


def provider_message(parsed, received):
    """Read the product's retained envelope before the independent HTTP fallback."""
    message = parsed.get('provider_output', parsed) if isinstance(parsed, dict) else {}
    message = message if isinstance(message, dict) else {}
    if not message and (received or {}).get('status_code') == 200:
        body = received.get('body_json')
        message = body if isinstance(body, dict) else {}
    return message


def mapping_admission(manifest, fields):
    """Require an unchanged complete physical catalogue, then human confirmation.

    V3 deliberately records automatic_complete=False even when no omission is
    observed. That status is retained and never turned into Word qualification.
    """
    from documents.import_selection import digest
    coverage = manifest.get('coverage', {})
    require(len(fields) == 101 and manifest.get('engine') == 'v3'
            and manifest.get('source_sha256') == ORIGINAL_SHA
            and manifest.get('mapping_sha256') == manifest.get('initial_mapping_sha256') == digest(fields),
            'The batch requires the original automatic physical mapping, without correction.')
    require(coverage.get('block_generation') is False
            and all(coverage.get(key) == [] for key in
                    ('legacy_omissions', 'legacy_unmapped', 'v3_uncovered_legacy_places'))
            and not coverage.get('selected_engine_issues'),
            'An omitted or unsupported destination cannot qualify the supplemental batch.')
    return coverage


def staged_audit_problems(report, job_id, expected):
    """A known staged child and its one unsent sibling are expected mid-batch.

    Every financial check still passes; no foreign or unresolved send is hidden.
    The unmodified report and this exact expected state are retained separately.
    """
    problems = []
    if not report.get('all_checks_pass'):
        problems.append('the billing audit does not pass')
    for key in ('unsettled_provider_receipts', 'durable_receipt_gaps'):
        if report.get(key):
            problems.append('the billing audit lists ' + key)
    rows = report.get('unresolved_jobs', [])
    observed = {str(row['id']): (row['kind'], row['state']) for row in rows}
    if len(observed) != len(rows) or observed != expected:
        problems.append('the active jobs differ from the exact staged child and unsent sibling')
    mine = [row for row in report.get('rows', []) if row.get('job_id') == str(job_id)]
    if len(mine) != 1 or not mine[0].get('checks') or not all(mine[0]['checks'].values()):
        problems.append('the staged child usage fails its complete accounting checks')
    return problems


class BatchRun(stages.Run):
    """Two sequential immutable child attempts; a separate local complete-union finish."""

    def run_send(self, send):
        from django.test import override_settings
        with override_settings(**stages.steps.PATH_FLAGS['field_relations']):
            return self._run_child(send)

    def context(self, send):
        context = super().context(send)
        context['runner']['files'] = runner_files()
        return context

    def audit(self, job, evidence):
        if job.state != 'staged':
            return super().audit(job, evidence)
        from core.management.commands.audit_billing import audit_report
        self.batch.refresh_from_db()
        parts = list(self.batch.parts.select_related('job').order_by('ordinal'))
        expected = {str(p.job_id): ('generation_part', 'staged' if p.ordinal == 1 else 'queued') for p in parts}
        report = audit_report()
        pc.write_new(evidence / 'audit-billing.json', report)
        pc.write_new(evidence / 'audit-expected-intermediate.json', {'batch': str(self.batch.pk), 'jobs': expected})
        problems = staged_audit_problems(report, job.pk, expected)
        if len(parts) != 2 or job.pk != parts[0].job_id or self.batch.state != 'running':
            problems.append('an intermediate audit requires this exact first child in a running two-child batch')
        return [{'code': 'audit_failure', 'why': problem} for problem in problems]

    def _admit_form(self):
        from core.models import Encounter, GenerationBatch, Job
        from core.security import private_path
        from django.utils import timezone
        self.pace_generation()
        raw = self.forms[FORM]
        opened = self.campaign.runs.current()
        require(opened is not None and type(opened.get('run')) is int and opened['run'] > 0,
                'Batch admission belongs to an existing normal standing run.')
        admission = pc.private_directory(self.root / 'batch-admission' / f"run-{opened['run']:04d}")
        pc.write_new(admission / 'original.docx', raw, raw=True)
        pc.write_new(admission / 'notes.txt', self.inputs['batch']['notes'], raw=True)
        template, version = self.upload(raw, 'SYNTHETIC ordinary batch 101', FORM + '.docx')
        pc.write_new(admission / 'initial-mapping.json', {'template': str(template.pk), 'version': str(version.pk),
            'original_sha256': template.sha256, 'fields': version.fields, 'import_manifest': version.import_manifest})
        require(template.sha256 == ORIGINAL_SHA and private_path(template.original_path).read_bytes() == raw,
                'The uploaded immutable original differs.')
        compiled_plan(self.inputs, version.fields)
        coverage = mapping_admission(version.import_manifest or {}, version.fields)
        response = self.world.client.post(f'/templates/{template.pk}/', {'action': 'v3_confirm',
            'mapping_version': str(version.pk), 'checked_every_field': 'on'})
        pc.write_new(admission / 'mapping-confirm-response.body', response.content, raw=True)
        pc.write_new(admission / 'mapping-confirm-response.json', {'status': response.status_code,
            'location': response.get('Location', ''), 'automatic_mapping_corrections': 0, 'coverage': coverage})
        version.refresh_from_db()
        require(response.status_code == 302 and not version.needs_confirmation, 'Actual mapping confirmation failed.')
        before = set(Encounter.objects.values_list('pk', flat=True))
        response = stages.steps.create_encounter(self.world.client, self.world.patient.pk, version.pk,
                                                 self.inputs['batch']['notes'], timezone.localdate().isoformat())
        created = Encounter.objects.exclude(pk__in=before)
        pc.write_new(admission / 'encounter-create-response.body', response.content, raw=True)
        pc.write_new(admission / 'encounter-create-response.json', {'status': response.status_code,
            'location': response.get('Location', ''), 'created_encounters': [str(pk) for pk in created.values_list('pk', flat=True)]})
        require(response.status_code == 302 and created.count() == 1, 'Actual encounter creation failed.')
        encounter = created.get()
        self.version, self.template, self.encounter = version, template, encounter
        token, revision, shown, quoted = sq.page_quote(self.world.client, encounter)
        pc.write_new(admission / 'page-quote.json', {'revision': revision, 'shown': str(shown), 'configuration': quoted})
        require(quoted['pricing_version'] == self.declaration.pricing_version(PRICING), 'The shown batch price changed.')
        response = stages.steps.request_generation(self.world.client, encounter.pk, token, revision)
        batches = GenerationBatch.objects.filter(encounter=encounter)
        pc.write_new(admission / 'generation-response.body', response.content, raw=True)
        pc.write_new(admission / 'generation-response.json', {'status': response.status_code,
            'location': response.get('Location', ''), 'batches': [str(pk) for pk in batches.values_list('pk', flat=True)]})
        if batches.count() == 1:
            self.batch = batches.get()
        require(response.status_code == 302 and batches.count() == 1, 'Generate must admit one actual complete batch.')
        parts = list(self.batch.parts.select_related('job').order_by('ordinal'))
        require([len(p.field_ids) for p in parts] == [100, 1] and all(p.job.state == 'queued' for p in parts)
                and self.batch.maximum_charge == shown and not encounter.answers,
                'Admission must persist both child holds before the first request and adopt no partial output.')

    def _stop_remaining(self, reason):
        from core import batch_jobs
        if getattr(self, 'batch', None) is not None:
            batch_jobs.stop(self.batch.pk, reason)

    def abort_remaining(self, reason, evidence=None):
        try:
            self._stop_remaining(reason)
            if getattr(self, 'batch', None) is None:
                return {'batch_admitted': False}
            self.batch.refresh_from_db()
            return {'batch': str(self.batch.pk), 'state': self.batch.state,
                    'children': list(self.batch.parts.order_by('ordinal').values('ordinal', 'job__state'))}
        except Exception as error:
            detail = {'class': type(error).__name__, 'message': str(error).replace(self.secret, '[redacted]')[:1000],
                      'recorded_at': pc.now(), 'no_retry': True}
            if evidence is not None:
                path = evidence / 'batch-abort-error.json'
                if not path.exists():
                    pc.write_new(path, detail)
            return {'error': detail, 'batch_admitted': getattr(self, 'batch', None) is not None}

    def _run_child(self, send):
        from core import batch_jobs, generation_batch as b
        from core.models import GenerationBatch, Job, Reservation
        send_inputs(send, self.inputs)
        self.require_not_stopped()
        maximum = self.planned[send.id]
        bound = self.admit(maximum)
        if send.id == FIRST:
            require(not hasattr(self, 'batch'), 'The first child is admitted once.')
            self._admit_form()
        else:
            require(hasattr(self, 'batch') and len(self.sends) == 1 and self.sends[0]['send']['id'] == FIRST
                    and self.sends[0]['stops_stage'] is False,
                    'The second child needs its clean first attempt in this same run.')
        plan = batch_jobs.current_plan(self.batch)
        ordinal = 1 if send.id == FIRST else 2
        part = self.batch.parts.select_related('job').get(ordinal=ordinal)
        job = part.job
        require(job.state == 'queued' and not part.events.filter(kind='send_intent').exists(),
                'A consumed or unresolved child is never attempted again.')
        require(list(GenerationBatch.objects.filter(state__in=b.ACTIVE).values_list('pk', flat=True)) == [self.batch.pk]
                and not Job.objects.filter(state__in=['queued', 'running']).exclude(generation_part__batch=self.batch).exists(),
                'Another active operation prevents the batch worker from claiming this child.')
        held = sum(Reservation.objects.filter(job=job, state='held').values_list('amount', flat=True), Decimal(0))
        require(Decimal(plan['parts'][ordinal-1]['maximum_cost']) == maximum
                and held == part.maximum_charge == maximum * Decimal('1.5'), 'The exact child quote and hold changed.')
        stages.require_price(self.declaration, job.config, send)
        number = len(self.ledger.rows()) + 1
        evidence = sq.private_evidence(self.root, number)
        case = pc.private_directory(evidence / 'case')
        pc.write_new(case / 'form.docx', self.forms[FORM], raw=True)
        pc.write_new(case / 'notes.txt', self.encounter.notes, raw=True)
        pc.write_new(case / 'mapping.json', self.version.fields)
        pc.write_new(evidence / 'batch-plan.json', plan)
        wire = b.request(plan, ordinal)
        pc.write_new(evidence / 'compiled-child-request.json', wire)
        attempt = self.attempt(send, job, maximum, bound, held, held, {'form_sha256': ORIGINAL_SHA,
            'notes_sha256': self.inputs['batch']['notes_sha256'], 'batch': str(self.batch.pk),
            'ordinal': ordinal, 'batch_plan_sha256': self.batch.plan_sha256, 'request_sha256': part.request_sha256,
            'request_profile': job.config['request_profile'], 'aggregate_shown_maximum_charge': str(self.batch.maximum_charge),
            'batch_runner_files': runner_files(), 'mapping_coverage': self.version.import_manifest.get('coverage', {}),
            'automatic_mapping_corrections': 0, 'mapping_confirmation': str(self.version.confirmed.pk)})
        try:
            outcome, message, findings = self.send_child(attempt, job, evidence, maximum, wire)
            self.encounter.refresh_from_db()
            pc.write_new(evidence / 'answers-after-child.json', {'answers': self.encounter.answers,
                'status': self.encounter.status, 'revision': self.encounter.revision})
            if self.encounter.answers:
                findings.append({'code': 'validator_failure', 'why': 'A child adopted partial answers before complete finish.'})
            fields, extra = {}, {'part_staged': job.state == 'staged', 'complete_union_adopted': False}
            if not findings and ordinal == 2:
                require(batch_jobs.finish(self.batch.pk), 'The separate local complete-union finish did not complete.')
                self.batch.refresh_from_db();self.encounter.refresh_from_db()
                require(self.batch.state == 'succeeded' and self.batch.parts.filter(job__state='succeeded').count() == 2,
                        'The batch is not fully adopted with both known children.')
                from core.models import ProviderReceipt, Usage
                jobs = [p.job_id for p in self.batch.parts.order_by('ordinal')]
                pc.write_new(evidence / 'aggregate-state.json', {'batch': str(self.batch.pk), 'state': self.batch.state,
                    'plan_sha256': self.batch.plan_sha256, 'original_sha256': self.template.sha256,
                    'version': str(self.version.pk), 'maximum_charge': str(self.batch.maximum_charge),
                    'children': [{'ordinal': p.ordinal, 'job': str(p.job_id), 'state': p.job.state,
                        'request_sha256': p.request_sha256, 'maximum_charge': str(p.maximum_charge)}
                        for p in self.batch.parts.select_related('job').order_by('ordinal')],
                    'receipts': [{'job': str(r.job_id), 'provider_request_id': r.provider_request_id,
                        'provider_resource_id': r.provider_resource_id, 'actual_cost': str(r.actual_cost),
                        'simulated': r.simulated} for r in ProviderReceipt.objects.filter(job_id__in=jobs)],
                    'usage': [{'job': str(u.job_id), 'actual_cost': str(u.actual_cost),
                        'charged_cost': str(u.charged_cost), 'simulated': u.simulated}
                        for u in Usage.objects.filter(job_id__in=jobs)],
                    'reservations': [{'job': str(r.job_id), 'amount': str(r.amount), 'state': r.state}
                        for r in Reservation.objects.filter(job_id__in=jobs)]})
                adopted = stages.steps.field_outcomes(self.encounter.answers)
                fields = usefulness(self.version.fields, adopted, self.inputs['batch'])
                pc.write_new(evidence / 'answers-adopted.json', {'answers': self.encounter.answers,
                    'status': self.encounter.status, 'revision': self.encounter.revision})
                if sum(v == 'supported_correct' for v in fields.values()) != 2 or sum(v == 'missing' for v in fields.values()) != 99:
                    findings.append({'code': 'validator_failure', 'why': 'The batch did not supply both fixed useful answers and 99 honest missing answers.'})
                if not findings:
                    _, _, more, exported = self.review_and_export(self.encounter, self.version, adopted, self.forms[FORM], evidence)
                    findings += more;extra['export'] = exported
                extra.update(complete_union_adopted=True, supported=sum(v == 'supported_correct' for v in fields.values()),
                             missing=sum(v == 'missing' for v in fields.values()))
            if findings:
                aborted = self.abort_remaining('Supplemental qualification stopped; no partial form is adopted.', evidence)
                if aborted.get('error'):
                    findings.append({'code': 'reconciliation', 'why': 'Batch cleanup failed; retained error requires operator reconciliation.'})
            return self.finish(send, attempt, evidence, outcome, findings, fields, extra)
        except BaseException as error:
            try:
                return self.interrupted(send, attempt, evidence, error)
            finally:
                self.abort_remaining('Supplemental attempt failed or needs reconciliation; never automatically resend.', evidence)

    def send_child(self, attempt, job, evidence, maximum, wire):
        from core import batch_jobs
        from core.models import ProviderReceipt, Reservation, Usage
        number = attempt['number'];before = ProviderReceipt.objects.count()
        pc.CURRENT_ATTEMPT.update(number=number, evidence_dir=str(evidence), secret=self.secret)
        timer = stages.Deadline(self.deadline)
        try:
            with timer: worked = batch_jobs.run_one()
        except stages.SendDeadline: worked = None
        finally: pc.CURRENT_ATTEMPT.clear()
        job.refresh_from_db()
        captured = (evidence / 'request.json').exists()
        receipt = ProviderReceipt.objects.filter(job=job).first();usage_row = Usage.objects.filter(job=job).first()
        received = pc.received_response(evidence);data, parsed = sq.raw_result(job)
        if data is not None: pc.write_new(evidence / 'product-result.json', data, raw=True)
        message = provider_message(parsed, received)
        pc.write_new(evidence / 'provider-result.json', {'provider_output': message})
        units = message.get('usage') if isinstance(message.get('usage'), dict) else None
        cost = None
        if units is not None:
            try: cost = pc.usage_cost(units, self.rates, unknown_geography_margin=False)
            except (KeyError, ValueError, TypeError): pass
        cls = ('not_sent' if stages.unsent(job, receipt, captured)
               else child_class(job.state, receipt, usage_row, captured, timer.fired))
        outcome = {'class': cls, 'job': str(job.pk), 'job_kind': job.kind, 'job_state': job.state,
            'worker_ran': worked, 'job_error': job.error, 'deadline': timer.fired, 'usage': units,
            'served_model': message.get('model'), 'stop_reason': message.get('stop_reason'),
            'request_captured': captured, 'sends_at_transport': pc.SENT.get(number, 0),
            'computed_cost_metered_geography': str(cost) if cost is not None else None,
            'computed_cost': str(cost) if cost is not None else None,
            'provider_request_id': job.provider_request_id, 'provider_resource_id': job.provider_resource_id,
            'settlement': {'receipt_actual_cost': str(receipt.actual_cost) if receipt else None,
                'usage_actual_cost': str(usage_row.actual_cost) if usage_row else None,
                'charged_cost': str(usage_row.charged_cost) if usage_row else None,
                'reservations': sorted(Reservation.objects.filter(job=job).values_list('state', flat=True))},
            'recorded_at': pc.now()}
        outcome['exposure'] = format(pc.exposure(attempt, outcome, self.rates), 'f')
        self.ledger.write_outcome(number, outcome)
        findings = []
        def fail(code, why): findings.append({'code': code, 'why': why})
        if timer.fired or cls in ('uncertain', 'reconciliation'):
            fail('uncertain_outcome', 'The child has no known completed outcome; it is never resent.')
        if job.state != 'staged' or not worked: fail('validator_failure', 'The exact child did not stage successfully.')
        receipt_count = ProviderReceipt.objects.count() - before
        if pc.SENT.get(number, 0) > 1 or receipt_count > 1:
            fail('more_than_one_request', 'More than one transport request or immutable receipt exists for this child.')
        if pc.SENT.get(number, 0) != 1 or receipt_count != 1:
            fail('validator_failure', 'The child lacks its one exact request and immutable receipt.')
        if not captured: fail('request_not_captured', 'The outbound child was not captured.')
        elif pc.read_json(evidence / 'request.json').get('body_json') != wire:
            fail('settlement_mismatch', 'The actual SDK body differs from the quoted hash-bound child request.')
        if not received: fail('response_not_captured', 'The exact provider response was not captured.')
        if message.get('model') != self.declaration.model: fail('wrong_served_model', 'The provider returned another model.')
        if message.get('stop_reason') != 'end_turn': fail('stop_reason_not_end_turn', 'The child is incomplete.')
        tokens = (units or {}).get('output_tokens')
        if type(tokens) is not int or not 0 <= tokens < stages.OUTPUT_SHARE_LIMIT * wire['max_tokens']:
            fail('output_over_70_percent', 'The response does not fit the qualified output margin.')
        if not self.declaration.inference_geo and (units or {}).get('inference_geo') == 'us':
            fail('metered_us_while_unset', 'The provider metered US inference despite the unset declaration.')
        if cost is None or cost > maximum or not receipt or not usage_row or receipt.actual_cost != usage_row.actual_cost or cost != receipt.actual_cost:
            fail('settlement_mismatch', 'The child settlement does not match actual provider usage and its quoted maximum.')
        if receipt and usage_row and (receipt.simulated or usage_row.simulated):
            fail('settlement_mismatch', 'Simulated rows cannot qualify a live provider child.')
        return outcome, message, findings
