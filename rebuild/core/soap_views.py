"""A department's reusable SOAP original; the existing document workflow owns every later step."""
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ScopedForm
from .models import Department, Template, TemplateVersion
from .retention import cleanup_file
from .security import audit, membership, private_path, store_upload
from .soap_document import LABELS, ORIGINAL_NAME, original_bytes


class SoapForm(ScopedForm):
    department = forms.ModelChoiceField(queryset=Department.objects.none())


def department_template(user, department):
    """Serialize the one-time original creation and preserve all later mapping versions on reuse."""
    from documents import DocumentError, inspect_template
    from documents.service import word_engine
    from . import v3_mapping

    membership(user, department, roles=['owner', 'clinician'])
    data = original_bytes()
    original_hash = sha256(data).hexdigest()
    template_id = uuid5(NAMESPACE_URL, 'quillmd:soap-original:v1:' + str(department.pk))
    relative = None
    try:
        with transaction.atomic():
            Department.objects.select_for_update().get(pk=department.pk)
            membership(user, department, roles=['owner', 'clinician'])
            existing = Template.objects.filter(pk=template_id).first()
            if existing:
                if (existing.department_id != department.pk or existing.format != 'docx'
                        or existing.sha256 != original_hash
                        or sha256(private_path(existing.original_path).read_bytes()).hexdigest() != original_hash
                        or not existing.versions.exists()):
                    raise ValidationError('The saved SOAP original could not be verified. Ask your administrator to '
                                          'check its private file; your existing documents were preserved.')
                return existing, False
            relative = store_upload(SimpleUploadedFile(ORIGINAL_NAME, data))
            info = inspect_template(private_path(relative), engine=word_engine())
            fields = info['fields']
            if (info['format'] != 'docx' or info['sha256'] != original_hash or info.get('backend')
                    or tuple(field['label'] for field in fields) != LABELS
                    or any(field.get('kind', 'text') not in ('text', 'long_text') for field in fields)):
                raise ValidationError('The configured Word processor did not identify all four SOAP answer areas. '
                                      'No form was saved; upload your own supported SOAP original instead.')
            contract = v3_mapping.CONTRACT if info.get('contract') == v3_mapping.CONTRACT else ''
            template = Template.objects.create(pk=template_id, department=department, name='SOAP note', format='docx',
                                               original_name=ORIGINAL_NAME, original_path=relative,
                                               sha256=original_hash, warnings=info.get('warnings', []), created_by=user)
            TemplateVersion.objects.create(template=template, number=1, fields=fields, contract=contract,
                                           review_requirements=info.get('review_requirements', []),
                                           import_manifest=info.get('import_manifest', {}), created_by=user)
            audit(user, 'template.upload', template.pk, department=department, sha256=original_hash,
                  field_count=len(fields), contract=contract, builtin='soap-v1')
            return template, True
    except (ValidationError, DocumentError, OSError):
        if relative:
            cleanup_file(private_path(relative))
        raise


@require_http_methods(['GET', 'POST'])
def start(request):
    # Administrative access does not grant clinical access, even to an administrator with a clinic membership.
    if settings.ADMIN_SITE:
        raise Http404
    form = SoapForm(request.POST or None, user=request.user)
    form.fields['department'].queryset = form.fields['department'].queryset.filter(
        membership__user=request.user, membership__active=True, membership__role__in=['owner', 'clinician']).distinct()
    if request.method == 'POST' and form.is_valid():
        from documents import DocumentError
        try:
            template, _ = department_template(request.user, form.cleaned_data['department'])
        except (ValidationError, DocumentError, OSError) as exc:
            text = '; '.join(exc.messages) if isinstance(exc, ValidationError) else (
                'The SOAP original could not be prepared. Try again or upload your own supported blank form.')
            form.add_error(None, text)
        else:
            messages.info(request, 'Review the four SOAP answer destinations, then use this form with your documented '
                          'notes. Assessment and plan require your documented clinical judgment; missing information '
                          'is left for review.')
            return redirect('template_detail', pk=template.pk)
    return render(request, 'soap_start.html', {'form': form, 'has_departments': form.fields['department'].queryset.exists()})
