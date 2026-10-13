"""One explicit approval of an exact ordinary semantic document revision.

This does not manufacture individual review events. Generated proofs remain
canonical; only actual edits/blank decisions enter individual answer history.
"""
from copy import deepcopy
import hashlib
import secrets

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Encounter, Job
from .security import audit, membership, private_path, scoped
from .semantic_generation import digest
from .semantic_review import definitions_for, save_answer, validate_answer

CONTRACT = 'document-approval-v1'
PENDING = ('queued', 'running', 'reconciliation')


def applies(encounter, definitions=None):
    return not encounter.template_version.document_backend and bool(
        definitions if definitions is not None else definitions_for(encounter.template_version))


def binding(encounter, actor, definitions):
    version = encounter.template_version
    return {'contract': CONTRACT, 'actor': str(actor.pk), 'encounter': str(encounter.pk),
        'patient': str(encounter.patient_id), 'department': str(encounter.department_id),
        'revision': encounter.revision, 'template_version': str(version.pk),
        'fields_sha256': digest(version.fields), 'definitions_sha256': digest(definitions),
        'original_sha256': version.template.sha256, 'prepared_sha256': version.prepared_sha256,
        'notes_sha256': hashlib.sha256(encounter.notes.encode()).hexdigest(),
        'service_date': str(encounter.service_date), 'answers_sha256': digest(encounter.answers),
        'review_sha256': digest(encounter.template_review)}


def review_token(encounter, actor, definitions):
    return signing.dumps(binding(encounter, actor, definitions), salt=CONTRACT, compress=True)


def verify_token(encounter, actor, definitions, token):
    try:
        previous = signing.loads(token, salt=CONTRACT, max_age=12*60*60)
    except signing.BadSignature as exc:
        raise ValidationError('This review has expired or could not be verified. Reopen the document before approving.') from exc
    if previous != binding(encounter, actor, definitions):
        raise ValidationError('The document changed after this review opened. Reopen it and review the current answers; nothing was saved or approved.')
    return previous


def single(post, key):
    values = post.getlist(key)
    if len(values) != 1:
        raise ValidationError('The review form is incomplete or repeated. Reopen it; nothing was saved or approved.')
    return values[0]


def proposed_answers(encounter, actor, definitions, post):
    fields = encounter.template_version.fields
    permitted = {'csrfmiddlewaretoken', 'review_token', 'intent'} | {
        prefix + f['key'] for f in fields for prefix in ('answer_', 'decision_')}
    if set(post) - permitted:
        raise ValidationError('This review form is out of date. Reopen the document; nothing was saved or approved.')
    answers = {}
    for field in fields:
        key = field['key']
        value = single(post, 'answer_'+key).replace('\r\n', '\n').replace('\r', '\n')
        decision = single(post, 'decision_'+key)
        if decision not in ('keep', 'blank'):
            raise ValidationError('Choose a valid answer decision.')
        previous = encounter.answers.get(key, {})
        blank = decision == 'blank' or previous.get('status') == 'left_blank' and not value.strip()
        previous_control = previous.get('text', '').replace('\r\n', '\n').replace('\r', '\n')
        if value == previous_control and not (blank and previous.get('status') != 'left_blank'):
            answer = deepcopy(previous)
            validate_answer(encounter, field, answer, definitions)
        else:
            answer = save_answer(encounter, field, previous, value, actor, False, blank,
                                 encounter.revision+1, definitions, document_level=True)
        answers[key] = answer
    return answers


def approval_blockers(encounter, answers, definitions, actor):
    from .tab_review import clinician_identity
    name = ' '.join((actor.get_full_name() or actor.email).split())
    for field in encounter.template_version.fields:
        answer = answers[field['key']]
        validate_answer(encounter, field, answer, definitions)
        if answer.get('status') not in ('supported', 'missing', 'edited', 'left_blank', 'conflict', 'ambiguous'):
            raise ValidationError('This answer has no recognized review state. Reopen and review its evidence.')
        if answer.get('status') == 'missing' and (answer.get('text') or answer.get('value') is not None
                or answer.get('fact_ids') or answer.get('independent_check', {}).get('verdict') not in ('missing', 'pass')
                or answer.get('independent_check', {}).get('fact_ids')):
            raise ValidationError('Undocumented information has an inconsistent retained check. Review its evidence before approval.')
        if answer.get('status') in ('conflict', 'ambiguous'):
            raise ValidationError('"'+field['label']+'" needs your decision. Correct the answer or explicitly choose to leave it blank after reviewing its evidence.')
        if clinician_identity(field) and answer.get('text', '').strip():
            if ' '.join(answer['text'].split()) != name:
                raise ValidationError('The signing name must match your signed-in clinician name, or remain blank.')
        # An existing importer may require a value; absence never supplies it.
        if field.get('required') is True and not answer.get('text', '').strip():
            raise ValidationError('"'+field['label']+'" is required and remains undocumented.')


@require_POST
def submit(request, pk):
    from documents import fill_template, DocumentError
    from .template_source import source_for_version
    from .views import document_refusal
    out = None
    try:
        with transaction.atomic():
            encounter = get_object_or_404(scoped(Encounter, request.user).select_related(
                'template_version__template', 'department').select_for_update(of=('self',)), pk=pk)
            membership(request.user, encounter.department, roles=['owner', 'clinician'])
            if encounter.status == 'finalized':
                return redirect('encounter_detail', pk=pk)
            definitions = definitions_for(encounter.template_version)
            if not applies(encounter, definitions):
                raise ValidationError('This document requires its original form-specific review.')
            if Job.objects.filter(encounter=encounter, state__in=PENDING).exists():
                raise ValidationError('Wait until the pending generation or transcription is resolved before reviewing these answers.')
            intent = single(request.POST, 'intent')
            if intent not in ('save', 'approve'):
                raise ValidationError('Choose Save changes or Approve and create Word explicitly.')
            baseline = verify_token(encounter, request.user, definitions, single(request.POST, 'review_token'))
            answers = proposed_answers(encounter, request.user, definitions, request.POST)
            changed = answers != encounter.answers
            if intent == 'approve':
                approval_blockers(encounter, answers, definitions, request.user)
            if changed:
                encounter.answers = answers
                encounter.revision += 1
                encounter.template_review = {}
            if intent == 'approve':
                version = encounter.template_version
                original = source_for_version(version)
                relative = f'exports/{secrets.token_hex(24)}.{version.template.format.lower()}'
                out = private_path(relative)
                out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                fill_template(original, version.fields, {k: v['text'] for k, v in answers.items()}, out,
                              expected_sha256=version.prepared_sha256 or version.template.sha256)
                out.chmod(0o600)
                at = timezone.now()
                encounter.export_path = relative
                encounter.export_sha256 = hashlib.sha256(out.read_bytes()).hexdigest()
                encounter.finalized_at = at
                encounter.finalized_by = request.user
                encounter.status = 'finalized'
                receipt = {'contract': CONTRACT, 'actor': str(request.user.pk), 'at': at.isoformat(),
                    'reviewed_baseline': baseline, 'approved_revision': encounter.revision,
                    'template_version': str(version.pk), 'answers_sha256': digest(answers),
                    'notes_sha256': hashlib.sha256(encounter.notes.encode()).hexdigest(),
                    'definitions_sha256': digest(definitions), 'export_sha256': encounter.export_sha256}
                encounter.template_review = {**encounter.template_review, 'document_approval': receipt}
                audit(request.user, 'encounter.document_approve', encounter.pk, department=encounter.department, approval=receipt)
                audit(request.user, 'encounter.finalize', encounter.pk, department=encounter.department,
                      export_sha256=encounter.export_sha256, mapping_version=version.number, approval_contract=CONTRACT)
            if changed or intent == 'approve':
                encounter.save()
            if changed:
                audit(request.user, 'encounter.answers_save', encounter.pk, department=encounter.department,
                      revision=encounter.revision, review_contract=CONTRACT, document_approved=intent == 'approve')
    except (ValidationError, DocumentError) as exc:
        if out is not None:
            out.unlink(missing_ok=True)
        return document_refusal(request, encounter, '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc), 409)
    except BaseException:
        if out is not None:
            out.unlink(missing_ok=True)
        raise
    return redirect('encounter_detail', pk=pk)
