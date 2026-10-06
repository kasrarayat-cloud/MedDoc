"""Explicit note-only recovery into a fresh reviewed mapping; historical work stays bound."""
import hashlib
import json
from uuid import UUID

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from documents import DocumentError

from . import batch_jobs, destination_roles, import_binding, v3_mapping
from .models import AuditEvent, Encounter, GenerationBatch, Job, Template, TemplateVersion
from .security import audit, membership, private_path, scoped

ACTION = 'encounter.recovered'
TERMINAL_JOBS = ('succeeded', 'failed', 'cancelled')
TERMINAL_BATCHES = ('succeeded', 'not_adopted', 'failed', 'cancelled')


def source_sha256(notes):
    return hashlib.sha256(notes.encode()).hexdigest()


def require_source(source, user):
    membership(user, source.department, roles=['owner', 'clinician'])
    if source.status not in ('draft', 'review') or source.finalized_at or source.export_path:
        raise ValidationError('Only an unfinished document can be recovered. Its original record remains unchanged.')
    if (batch_jobs.pending(source)
            or Job.objects.filter(encounter=source).exclude(state__in=TERMINAL_JOBS).exists()
            or GenerationBatch.objects.filter(encounter=source).exclude(state__in=TERMINAL_BATCHES).exists()):
        raise ValidationError('Resolve pending or unknown requests on this document before recovering it. Nothing was created or sent.')
    if not source.notes.strip():
        raise ValidationError('This document has no saved source notes to recover. Use the reviewed form to start a new document.')


def linked_target(source, version):
    lineage = version.import_manifest.get('reinspection') or {}
    original = source.template_version.template
    return (isinstance(lineage, dict) and version.template_id != original.pk
            and str(lineage.get('source_template_id')) == str(original.pk)
            and lineage.get('source_sha256') == original.sha256 == version.template.sha256
            and version.template.department_id == source.department_id
            and version.template.format.lower() == 'docx')


def target_versions(source, user):
    """Latest mappings of linked fresh copies only; no other patient's notes or answers."""
    templates = scoped(Template, user).filter(department_id=source.department_id,
        versions__import_manifest__reinspection__source_template_id=str(source.template_version.template_id)).distinct()
    found = []
    for template in templates.order_by('-created_at'):
        version = template.versions.order_by('-number').first()
        if version and linked_target(source, version) and not version.needs_confirmation:
            found.append(version)
    return found


def verify_target(source, version):
    if not linked_target(source, version) or version.needs_confirmation:
        raise ValidationError('Choose a freshly rechecked copy of this original whose current mapping a clinician has confirmed.')
    if version.template.versions.order_by('-number').first().pk != version.pk:
        raise ValidationError('That form mapping changed. Review its current mapping before recovering this document.')
    import_binding.verify(version)
    original = private_path(version.template.original_path)
    if hashlib.sha256(original.read_bytes()).hexdigest() != version.template.sha256:
        raise ValidationError('The rechecked original could not be verified. Nothing was created or sent.')
    if v3_mapping.is_v3_version(version):
        import_binding.verify_review_places(version)
    roles = destination_roles.report(version) or {}
    if roles.get('legacy_unresolved_actions'):
        raise ValidationError('This form still has unresolved human signing locations. Review its mapping before recovery.')
    refusal = v3_mapping.generation_refusal(version)
    if refusal:
        raise ValidationError(refusal)


def recovery_key(source, version):
    identity = {'source_id': str(source.pk), 'source_revision': source.revision,
        'source_version_id': str(source.template_version_id), 'source_sha256': source_sha256(source.notes),
        'patient_id': str(source.patient_id), 'service_date': source.service_date.isoformat(),
        'mapping_version_id': str(version.pk), 'original_sha256': version.template.sha256}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest(), identity


def recover(source, version_id, user, expected_revision):
    """Lock the old work and current form; the audit key serializes retry without a schema change."""
    from .disposition_execution import lock_available
    with transaction.atomic():
        source = lock_available(source.pk)
        require_source(source, user)
        if str(source.revision) != str(expected_revision):
            raise ValidationError('The saved document changed. Reload its source notes before recovering it.')
        try:
            selected = UUID(str(version_id))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError('Choose a confirmed rechecked mapping for this original.') from None
        version = get_object_or_404(TemplateVersion.objects.select_related('template'), pk=selected,
                                   template__department_id=source.department_id)
        Template.objects.select_for_update().get(pk=version.template_id)
        verify_target(source, version)
        key, identity = recovery_key(source, version)
        prior = AuditEvent.objects.filter(action=ACTION, department=source.department,
                                          details__recovery_key=key).order_by('created_at').first()
        if prior:
            existing = scoped(Encounter, user).filter(pk=prior.target, department=source.department).first()
            if not existing:
                raise ValidationError('The earlier recovered document is unavailable. Ask an administrator to check its history; nothing was duplicated.')
            return existing, False
        new = Encounter(department=source.department, patient=source.patient, template_version=version,
                        created_by=user, service_date=source.service_date, notes=source.notes)
        new.full_clean(exclude=['notes', 'answers', 'finalized_at', 'finalized_by', 'export_path', 'export_sha256'])
        new.save()
        audit(user, ACTION, new.pk, department=source.department, recovery_key=key, **identity,
              new_encounter_id=str(new.pk), answers_copied=False, transcript_context_copied=False,
              source_review_required=True)
        return new, True


def recovery_notice(encounter):
    event = AuditEvent.objects.filter(action=ACTION, target=str(encounter.pk),
                                     department_id=encounter.department_id).order_by('created_at').first()
    return {'source_id': event.details['source_id']} if event else None


@require_http_methods(['GET', 'POST'])
def page(request, pk):
    if settings.ADMIN_SITE:
        raise Http404
    source = get_object_or_404(scoped(Encounter, request.user).select_related(
        'department', 'patient', 'template_version__template'), pk=pk)
    # Authority precedes rendering saved clinical notes, including on refused recovery pages.
    membership(request.user, source.department, roles=['owner', 'clinician'])
    error = ''
    try:
        require_source(source, request.user)
        if request.method == 'POST':
            if request.POST.get('review_recovery') != 'on':
                raise ValidationError('Review the saved source notes and acknowledge what the new draft will contain.')
            new, created = recover(source, request.POST.get('mapping_version'), request.user,
                                   request.POST.get('revision'))
            messages.info(request, ('New draft created from the saved source notes. ' if created else
                                    'The existing recovered document was reopened. Nothing was duplicated. ')
                          + 'Check the notes for this patient and service date before generating. Previous answers, '
                            'code acceptances and reviewed transcript context were not copied; the earlier document is unchanged.')
            return redirect('encounter_detail', pk=new.pk)
    except (ValidationError, DocumentError, OSError) as exc:
        error = '; '.join(exc.messages) if isinstance(exc, ValidationError) else (
            'The preserved original or current answer locations could not be verified. Nothing was created or sent; review the form or ask an administrator to check it.')
    choices = target_versions(source, request.user) if source.status in ('draft', 'review') else []
    return render(request, 'encounter_recovery.html', {'source': source, 'mapping_versions': choices,
        'recovery_error': error}, status=400 if error else 200)
