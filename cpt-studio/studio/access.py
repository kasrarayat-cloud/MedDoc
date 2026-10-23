"""Workspace scoping. Every read and write goes through these helpers.

A user sees only workspaces where they hold an ACTIVE membership. Anything
outside that answers 404 — never 403 — so the existence of another
workspace's records is not disclosed.
"""
from django.http import Http404

from .models import Encounter, Membership


def active_membership(user, workspace_id=None):
    """The user's active membership (in ``workspace_id`` if given), else 404."""
    if not getattr(user, 'is_authenticated', False) or not user.is_active:
        raise Http404()
    memberships = Membership.objects.select_related('workspace', 'workspace__category').filter(user=user, active=True)
    if workspace_id is not None:
        memberships = memberships.filter(workspace_id=workspace_id)
    membership = memberships.order_by('created_at').first()
    if membership is None:
        raise Http404()
    return membership


def scoped_encounter(user, encounter_id, *, for_update=False):
    """(encounter, membership) when the user is an active member of its workspace, else 404."""
    queryset = Encounter.objects.select_related('workspace', 'workspace__category')
    if for_update:
        queryset = queryset.select_for_update()
    try:
        encounter = queryset.get(pk=encounter_id)
    except (Encounter.DoesNotExist, ValueError, TypeError):
        raise Http404()
    membership = active_membership(user, encounter.workspace_id)
    return encounter, membership


class SecurityHeadersMiddleware:
    """Headers the approved design relied on, plus no-index and no-store for data."""

    CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
           "script-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; "
           "object-src 'none'; base-uri 'self'; form-action 'self'")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault('Content-Security-Policy', self.CSP)
        response.headers.setdefault('X-Robots-Tag', 'noindex, nofollow')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        if not request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-store'
        return response
