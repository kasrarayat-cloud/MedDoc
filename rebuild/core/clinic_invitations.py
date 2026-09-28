"""Clinic-owner invitations: how a new clinic joins when self-service registration is closed.

With QUILLMD_REGISTRATION=invite, /register/ answers 404, so a new organization cannot come into
being by itself. A platform administrator (staff, MFA-verified) records an invitation from the
console; accepting it creates the organization, its first department and the owner membership —
the same three rows email verification creates for a self-registered account — plus the one-time
welcome credit, exactly as every other verified account receives it.

The token is 7 days, stored only as a sha256, and single use, as department invitations are. An
invitation cannot outlive its issuer's authority: acceptance re-checks that the administrator who
issued it is still an active administrator.

Kept out of core/views.py deliberately: that file is edited by several workstreams.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .billing import welcome_credit, welcome_credit_label
from .forms import RegisterForm
from .models import ClinicInvitation, Department, Membership, Organization, User
from .security import audit, digest, token

LIFETIME = timedelta(days=7)


def issue(actor, email, organization_name, department_name):
    """Record an invitation and return (invitation, raw token). The raw token exists only in the email."""
    raw = token()
    invitation = ClinicInvitation.objects.create(
        email=email.strip().lower(), organization_name=organization_name.strip(),
        department_name=department_name.strip(), token_hash=digest(raw),
        expires_at=timezone.now() + LIFETIME, invited_by=actor)
    # No recipient address and no clinic name in the audit record: the invitation row holds them.
    audit(actor, 'admin.clinic_invitation_created', invitation.pk)
    return invitation, raw


def issuer_still_authorised(invitation):
    issuer = invitation.invited_by
    return issuer.is_active and issuer.is_staff


@require_http_methods(['GET', 'POST'])
def accept(request, raw):
    if settings.ADMIN_SITE:
        raise Http404
    invitation = get_object_or_404(ClinicInvitation, token_hash=digest(raw), expires_at__gt=timezone.now(),
                                   accepted_at__isnull=True, revoked_at__isnull=True)
    existing_account = User.objects.filter(email__iexact=invitation.email).exists()
    form = RegisterForm(request.POST or None, initial={'email': invitation.email})
    if request.method == 'POST':
        existing = request.user if request.user.is_authenticated else None
        if existing and existing.email.lower() != invitation.email:
            raise PermissionDenied
        if existing or form.is_valid():
            if not existing and form.cleaned_data['email'] != invitation.email:
                form.add_error('email', 'Use the invited email address.')
            else:
                with transaction.atomic():
                    invitation = ClinicInvitation.objects.select_for_update().get(pk=invitation.pk)
                    if invitation.accepted_at or invitation.revoked_at or invitation.expires_at <= timezone.now():
                        raise Http404
                    if not issuer_still_authorised(invitation):
                        return HttpResponse('This invitation is no longer valid. Ask QuillMD for a new one.',
                                            status=409, content_type='text/plain')
                    if existing:
                        # FOR NO KEY UPDATE: welcome_credit locks this account's wallet next, and the account's own
                        # in-flight requests take FOR KEY SHARE on this row at commit (core.retention, RF-R1).
                        user = User.objects.select_for_update(no_key=True).get(pk=existing.pk)
                    else:
                        user = form.save(commit=False)
                        user.username = invitation.email
                        user.verified_at = timezone.now()
                        user.save()
                    # Possession of the emailed high-entropy token verifies this mailbox.
                    if not user.verified_at:
                        user.verified_at = timezone.now()
                        user.save(update_fields=['verified_at'])
                    organization = Organization.objects.create(name=invitation.organization_name)
                    department = Department.objects.create(organization=organization, name=invitation.department_name)
                    Membership.objects.create(user=user, department=department, role='owner')
                    welcome_credit(user)
                    invitation.accepted_at = timezone.now()
                    invitation.accepted_by = user
                    invitation.organization = organization
                    invitation.save(update_fields=['accepted_at', 'accepted_by', 'organization'])
                    audit(user, 'clinic.invitation_accepted', invitation.pk, department=department)
                label = welcome_credit_label()
                messages.success(request, f'{invitation.organization_name} is ready. Your {label} personal welcome credit is available.'
                                 if label else f'{invitation.organization_name} is ready.')
                return redirect('login')
    return render(request, 'clinic_invite.html', {'form': form, 'clinic_invitation': invitation,
                                                  'existing_invited_account': existing_account})
