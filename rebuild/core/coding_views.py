"""Tenant-scoped coding endpoints. Observation never queues work."""
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import coding_service as service
from .models import CodingRun, Encounter
from .security import scoped


def encounter_for(request, pk):
    return get_object_or_404(scoped(Encounter, request.user).select_for_update(of=('self',)), pk=pk)


def unique(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValidationError('Duplicate coding form field.')
        value[key] = item
    return value


def payload(request):
    if len(request.body) > 64000:
        raise ValidationError('The coding form is too large.')
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body, object_pairs_hook=unique,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValidationError('Invalid coding form.') from exc
        if type(data) is not dict:
            raise ValidationError('Invalid coding form.')
        return data
    if any(len(request.POST.getlist(k)) != 1 for k in request.POST):
        raise ValidationError('Duplicate coding form field.')
    return request.POST.dict()


def response(request, encounter, error='', status=200):
    coding = service.snapshot(encounter, request.user)
    if request.content_type != 'application/json' and request.headers.get('Accept') != 'application/json' and not error:
        return redirect('/encounters/' + str(encounter.pk) + '/?tab=coding')
    html = render_to_string('coding_panel.html', {'encounter': encounter, 'coding': coding}, request=request)
    result = JsonResponse({'encounter_id': str(encounter.pk), 'version': coding['version'],
        'state': coding['state'], 'state_label': coding['state_label'], 'pending': coding['pending'],
        'html': html, 'error': error}, status=status)
    result['Cache-Control'] = 'no-store'
    return result


@require_GET
@never_cache
@transaction.atomic
def status(request, pk):
    return response(request, encounter_for(request, pk))


@require_POST
@transaction.atomic
def request_run(request, pk):
    e = encounter_for(request, pk)
    try:
        data = payload(request)
        latest = service.displayed_run(e)
        service.verify_display(e, request.user, data.get('display_token', ''), latest)
        if service.ensure_run(e, request.user) is None:
            raise ValidationError('Save the completed document and wait for its current request before coding.')
        return response(request, e)
    except ValidationError as exc:
        return response(request, e, '; '.join(exc.messages), 409)


@require_POST
@transaction.atomic
def context(request, pk):
    e = encounter_for(request, pk)
    try:
        data = payload(request)
        latest = service.displayed_run(e)
        service.verify_display(e, request.user, data.get('display_token', ''), latest)
        values = data.get('context')
        if values is None:
            values = {key: data.get(key, default) for key, default in service.CONTEXT_DEFAULTS.items()}
            for key, default in service.CONTEXT_DEFAULTS.items():
                if type(default) is bool:
                    values[key] = data.get(key) == 'true'
        service.update_context(e, request.user, values)
        return response(request, e)
    except ValidationError as exc:
        return response(request, e, '; '.join(exc.messages), 409)


def run_for(request, e, run_pk):
    return get_object_or_404(CodingRun, pk=run_pk, encounter=e)


@require_POST
@transaction.atomic
def selections(request, pk, run_pk):
    e = encounter_for(request, pk)
    run = run_for(request, e, run_pk)
    try:
        data = payload(request)
        service.verify_display(e, request.user, data.get('display_token', ''), run)
        value = data.get('selections')
        revision = data.get('selection_revision')
        if request.content_type != 'application/json':
            selected, overrides = [], {}
            for item in run.result.get('suggestions', []):
                key = item['id']
                if data.get('select_' + key) == 'include':
                    selected.append(key)
                if data.get('code_' + key, '').strip():
                    overrides[key] = {'code': data['code_' + key].strip(), 'reason': data.get('reason_' + key, '').strip()}
            value = {'selected_ids': selected, 'overrides': overrides}
            try:
                revision = int(revision)
            except (TypeError, ValueError):
                raise ValidationError('The selection revision is invalid.')
        service.update_selection(run, request.user, value, revision)
        return response(request, e)
    except ValidationError as exc:
        return response(request, e, '; '.join(exc.messages), 409)


@require_POST
@transaction.atomic
def approval(request, pk, run_pk):
    e = encounter_for(request, pk)
    run = run_for(request, e, run_pk)
    try:
        data = payload(request)
        service.verify_display(e, request.user, data.get('display_token', ''), run)
        service.approve(run, request.user, data.get('input_digest', ''), data.get('selection_digest', ''))
        return response(request, e)
    except ValidationError as exc:
        return response(request, e, '; '.join(exc.messages), 409)
