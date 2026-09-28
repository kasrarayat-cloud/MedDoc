"""MFA custodian actions; policy keys and signing secrets never enter this UI."""
import uuid

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from . import disposition as d, disposition_execution as x, disposition_journal as journal, disposition_policy as policy, models as m
from .admin_queries import page_for
from .admin_views import gate
from .disposition_views import Fingerprint
from .security import audit


class SignedEnvelope(forms.CharField):
    def __init__(self, **kwargs):
        super().__init__(max_length=65536, widget=forms.Textarea(attrs={
            'rows': 5, 'spellcheck': 'false', 'autocomplete': 'off'}), **kwargs)

    def clean(self, value):
        return policy.decode(super().clean(value).encode('utf-8'))


class CheckpointForm(forms.Form):
    checkpoint = SignedEnvelope(label='Independently signed journal checkpoint')


class PolicyForm(forms.Form):
    policy = SignedEnvelope(label='Signed prospective policy')
    confirmed = forms.BooleanField(label='I checked the approved policy and its exact department and prospective dates.')


class PrepareForm(forms.Form):
    admission = forms.UUIDField(label='Policy admission ID')
    target = forms.UUIDField(label='Empty draft ID')
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)


class ApproveForm(forms.Form):
    instruction = forms.UUIDField(label='Instruction ID')
    digest = Fingerprint(label='Exact draft SHA-256')
    confirmed = forms.BooleanField(label='I checked this exact target and digest. I am a different custodian from its preparer.')


class ExecuteForm(CheckpointForm):
    instruction = forms.UUIDField(label='Approved instruction ID')
    target = forms.UUIDField(label='Empty draft ID to delete')
    confirmed = forms.BooleanField(label='Delete this approved empty draft. Its patient, template and retained history must remain.')


class ReplayForm(CheckpointForm):
    confirmed = forms.BooleanField(label='Import suppression instructions into this quarantined target. Keep restored content and quarantine in place.')


@require_http_methods(['GET', 'POST'])
def page(request):
    gate(request); d.retention.custodian(request.user)
    quarantined = d.quarantined()
    definitions = ({'replay': ReplayForm} if quarantined else {
        'initialize': CheckpointForm, 'admit': PolicyForm, 'prepare': PrepareForm,
        'approve': ApproveForm, 'execute': ExecuteForm,
    } if getattr(settings, 'DISPOSITION_ENABLED', False) else {})
    action = request.POST.get('action') if request.method == 'POST' else None
    if request.method == 'POST' and action not in definitions:
        return HttpResponseBadRequest('This disposition action is unavailable.')
    forms_by_name = {k: cls(request.POST if action == k else None, prefix=k) for k, cls in definitions.items()}
    form = forms_by_name.get(action)
    if form and form.is_valid():
        values = form.cleaned_data
        try:
            if action == 'initialize':
                x.enabled(); d.require_processing(); journal.initialize(values['checkpoint'])
                audit(request.user, 'disposition.journal_initialized')
                message = 'The journal checkpoint was verified.'
            elif action == 'admit':
                row = x.admit(request.user, values['policy'])
                message = f'Policy admission recorded: {row.pk}.'
            elif action == 'prepare':
                row = x.prepare(request.user, values['admission'], values['target'], values['request_key'])
                message = f'Instruction prepared: {row.pk}. A distinct custodian must review it.'
            elif action == 'approve':
                x.approve(request.user, values['instruction'], values['digest'])
                message = 'Exact instruction approved. No draft has been deleted.'
            elif action == 'execute':
                row = m.DispositionInstruction.objects.get(pk=values['instruction'])
                if row.target_id != values['target']:
                    raise ValidationError('The draft ID does not match this instruction. Check both IDs.')
                x.execute(request.user, row.pk, values['checkpoint'])
                message = 'The approved empty draft is deleted locally. Its retained history remains.'
            else:
                result = x.replay(request.user, values['checkpoint'])
                message = f"{result['tombstones']} suppression instructions verified. Restored content and quarantine remain."
            messages.success(request, message)
            return redirect('disposition_execution')
        except ObjectDoesNotExist:
            form.add_error(None, 'The required record or distinct approval was not found. Check the IDs and review state.')
        except ValidationError as error:
            form.add_error(None, error)
    rows = m.DispositionInstruction.objects.select_related('policy', 'created_by', 'approval__created_by').order_by('-created_at', 'pk')
    navigation = page_for(request, rows, anchor='instructions', size=25)
    displayed = list(navigation['page'])
    completed = set(m.DispositionCompletion.objects.filter(tombstone__instruction_id__in=[r.pk for r in displayed])
                    .values_list('tombstone__instruction_id', flat=True))
    for row in displayed:
        row.completed = row.pk in completed
    audit(request.user, 'disposition.execution_records_read')
    return render(request, 'disposition_execution.html', {
        'forms': forms_by_name, 'quarantined': quarantined, 'enabled': bool(definitions),
        'instructions': displayed, 'navigation': navigation,
        'admissions': m.DispositionPolicyAdmission.objects.select_related('created_by').order_by('-created_at', 'pk')[:25],
    })
