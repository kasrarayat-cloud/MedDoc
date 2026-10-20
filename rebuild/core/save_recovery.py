"""Same-endpoint form saves with append-only, revision-bound reconciliation.

The ordinary view still validates every control and permission. This transport
never retries a mutation. Its GET observes an attempt; it cannot approve or save.
"""
from functools import wraps
import hashlib
import json
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse

from .models import AuditEvent
from .security import audit, membership

CONTRACT = 'revision-bound-form-save-v1'
ACTION = 'template.save_attempt'
HEADER = 'X-QuillMD-Save'


def binding(prep, kind):
    if kind == 'inline':
        from .template_source import approval_binding
    elif kind == 'definitions':
        from .semantic_preparation import approval_binding
    else:
        raise ValueError('Unknown save parent.')
    return approval_binding(prep)


def controls_sha256(post):
    values = [[key, [v.replace('\r\n', '\n').replace('\r', '\n') for v in post.getlist(key)]]
              for key in sorted(post) if key != 'csrfmiddlewaretoken']
    raw = json.dumps(values, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > 512 * 1024:
        raise ValidationError('The form exceeds its save bound; nothing was saved.')
    return hashlib.sha256(raw).hexdigest()


def _identity(request):
    attempt = request.headers.get(HEADER+'-Attempt', '')
    digest = request.headers.get(HEADER+'-Digest', '')
    baseline = request.headers.get(HEADER+'-Binding', '')
    revision = request.headers.get(HEADER+'-Revision', '')
    if (not re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}', attempt)
            or not re.fullmatch(r'[a-f0-9]{64}', digest)
            or not re.fullmatch(r'[a-f0-9]{64}', baseline)
            or not re.fullmatch(r'0|[1-9][0-9]{0,9}', revision)):
        raise ValidationError('The save identity is invalid. Check the current saved page.')
    return {'attempt': attempt, 'digest': digest, 'base_binding': baseline, 'base_revision': int(revision)}


def _parent(request, pk, kind):
    if kind == 'inline':
        from .preparation_views import selected
        template, prep = selected(request, pk)
    else:
        from .semantic_preparation_views import selected
        prep, _ = selected(request, pk)
        template = prep.source_version.template
    membership(request.user, template.department, roles=['owner', 'clinician'])
    # Same lock as the ordinary save: an admitted earlier mutation finishes
    # before this read. A late request is still guarded by this attempt+revision.
    prep = type(prep).objects.select_for_update().get(pk=prep.pk)
    return prep, template.department


def _reply(state, prep, kind, identity, **extra):
    response = JsonResponse({'contract': CONTRACT, 'state': state, **identity,
        'current_revision': prep.revision, 'current_binding': binding(prep, kind), **extra})
    response['Cache-Control'] = 'no-store'
    return response


def _receipt(request, prep, kind, identity):
    rows = list(AuditEvent.objects.filter(action=ACTION, target=str(prep.pk), actor=request.user,
        details__kind=kind, details__attempt=identity['attempt']).order_by('created_at')[:2])
    if len(rows) > 1:
        raise ValidationError('The save record is ambiguous; no retry was made.')
    if not rows:
        return None
    detail = rows[0].details
    if (detail.get('contract') != CONTRACT or detail.get('path') != request.path
            or any(detail.get(key) != value for key, value in identity.items())):
        raise ValidationError('This save identity belongs to different controls; nothing was saved.')
    return detail


def _observed(request, prep, kind, identity, receipt):
    if receipt:
        if receipt.get('result') == 'committed':
            current = (prep.revision == receipt['saved_revision']
                       and binding(prep, kind) == receipt['saved_binding'])
            return _reply('committed' if current else 'committed_then_changed', prep, kind, identity,
                saved_revision=receipt['saved_revision'], redirect_url=receipt['redirect_url'])
        return _reply('rejected', prep, kind, identity, http_status=receipt['http_status'])
    unchanged = (prep.revision == identity['base_revision']
                 and binding(prep, kind) == identity['base_binding'])
    # Absence at a read is not proof a delayed network request can never arrive.
    # An explicit retry MUST reuse this identity and the original signed tokens.
    return _reply('not_recorded_at_read' if unchanged else 'changed', prep, kind, identity)


def recoverable_save(kind):
    """Opt-in transport; native forms and all existing authorization stay intact."""
    def decorate(view):
        @wraps(view)
        def wrapped(request, pk, *args, **kwargs):
            marker = request.headers.get(HEADER)
            if marker is None:
                return view(request, pk, *args, **kwargs)
            if marker != CONTRACT or request.method not in ('GET', 'POST'):
                return JsonResponse({'state': 'refused', 'message': 'Unsupported save transport.'}, status=409)
            try:
                identity = _identity(request)
                with transaction.atomic():
                    prep, department = _parent(request, pk, kind)
                    receipt = _receipt(request, prep, kind, identity)
                    if request.method == 'GET':
                        return _observed(request, prep, kind, identity, receipt)
                    if controls_sha256(request.POST) != identity['digest']:
                        raise ValidationError('The save controls changed; nothing was saved.')
                    if receipt:
                        # This is a read of a prior result, never another save.
                        return _observed(request, prep, kind, identity, receipt)
                    if prep.revision != identity['base_revision'] or binding(prep, kind) != identity['base_binding']:
                        response = _reply('changed', prep, kind, identity)
                        response.status_code = 409
                        return response
                    response = view(request, pk, *args, **kwargs)
                    prep.refresh_from_db()
                    if response.status_code in (302, 303):
                        location = response['Location']
                        parsed = urlsplit(location)
                        if (prep.revision != identity['base_revision'] + 1 or parsed.scheme or parsed.netloc
                                or not location.startswith('/') or location.startswith('//') or len(location) > 500):
                            raise ValidationError('The save result could not be bound; no change was committed.')
                        evidence = {'result': 'committed', 'saved_revision': prep.revision,
                                    'saved_binding': binding(prep, kind), 'redirect_url': location}
                    elif response.status_code in (400, 403, 409, 422):
                        if prep.revision != identity['base_revision'] or binding(prep, kind) != identity['base_binding']:
                            raise ValidationError('The refused save changed state; no change was committed.')
                        evidence = {'result': 'rejected', 'http_status': response.status_code}
                    else:
                        raise ValidationError('The save response was unexpected; no change was committed.')
                    audit(request.user, ACTION, prep.pk, department=department,
                          contract=CONTRACT, kind=kind, path=request.path, **identity, **evidence)
                    if evidence['result'] == 'committed':
                        return _observed(request, prep, kind, identity, evidence)
                    response['X-QuillMD-Save-State'] = 'rejected'
                    response['Cache-Control'] = 'no-store'
                    return response
            except ValidationError:
                # Do not stringify validation data into an audit or log. The
                # ordinary view supplies its own safe validation response above.
                return JsonResponse({'contract': CONTRACT, 'state': 'refused',
                    'message': 'The save conflicts with its current revision or controls. Your edits are kept; check the saved page.'}, status=409)
        return wrapped
    return decorate
