"""Explicit normal-dashboard submission of one retained-answer check."""
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Encounter
from .security import scoped, membership


@require_POST
def submit(request, pk):
    from . import semantic_revalidation
    encounter = get_object_or_404(scoped(Encounter, request.user), pk=pk)
    membership(request.user, encounter.department, roles=['owner', 'clinician'])
    try:
        if request.POST.get('confirm_revalidation') != 'on':
            raise ValidationError('Confirm the single independent check before submitting.')
        revision = int(request.POST.get('revision', ''))
        semantic_revalidation.enqueue(encounter, request.user,
            display_token=request.POST.get('display_token', ''), expected_revision=revision)
    except (ValidationError, ValueError) as exc:
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'The reviewed source revision is invalid.'
        return HttpResponse(message, status=409, content_type='text/plain')
    return redirect('encounter_detail', pk=encounter.pk)
