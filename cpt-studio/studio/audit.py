"""Append-only audit trail. Events carry ids and counts, never note text."""
from .models import AuditEvent


def record(workspace, event, *, encounter=None, actor=None, **data):
    actor_kind = getattr(actor, 'actor_kind', None) or 'system'
    return AuditEvent.objects.create(
        workspace=workspace, encounter=encounter, actor=actor, actor_kind=actor_kind, event=event, data=data)
