"""Append-only audit trail. Events carry ids and counts, never note text.

Every row also records the request that caused it (release 1, C1 item 7): the client's address, the sign-in reference
(it leads to the sign-in's LoginAttempt row and is never the session key) and nginx's request id - read from the request
SessionPolicyMiddleware binds while it is served (studio.request_meta.request_fields). Rows the worker or a management
command writes are made outside any request and leave them empty (NULL), as an older release's rows do."""
from . import request_meta
from .models import AuditEvent


def record(workspace, event, *, encounter=None, actor=None, **data):
    actor_kind = getattr(actor, 'actor_kind', None) or 'system'
    fields = request_meta.request_fields()
    return AuditEvent.objects.create(
        workspace=workspace, encounter=encounter, actor=actor, actor_kind=actor_kind, event=event, data=data,
        client=fields['client'] or None, sign_in_ref=fields['sign_in_ref'], request_id=fields['request_id'] or None)
