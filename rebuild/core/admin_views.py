"""Administration-console views added beside the existing dashboard.

They live in their own module for two reasons. `core/views.py` is a hot file that other work
touches constantly, and every view here repeats the SAME access gate rather than inheriting one:
`is_staff` AND `is_verified()` (django_otp — administrator MFA), raising Http404 so the surface
never advertises itself to a signed-in clinician. The middleware enforces the same thing for any
`/console/` path; the duplication is deliberate, so a route that is ever mounted elsewhere is
still closed.
"""
import csv

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import admin_console
from .admin_queries import page_for, searched
from django.utils import timezone

from django.conf import settings
from django_otp.plugins.otp_totp.models import TOTPDevice

from .forms import ClinicInvitationForm, MfaResetForm
from .models import (AuditEvent, ClinicInvitation, Department, Invitation, Membership, Organization, Usage,
                     User, Wallet)
from .security import audit, rate_limit


def gate(request):
    """The one access rule, stated once and called by every view in this module."""
    if not request.user.is_staff or not request.user.is_verified():
        raise Http404


def back_to(request, default):
    """Return to where the administrator was, not to the top of a 6000-pixel page.

    A console action that discards the operator's search and page number makes them re-find the
    row they were working on, which is how a second row gets changed by mistake.
    """
    target = request.POST.get('back') or ''
    return target if target.startswith('/console/') and '\n' not in target and '\r' not in target else default


# --------------------------------------------------------------------------------------
# One account, everything about it
# --------------------------------------------------------------------------------------

def admin_account_page(request, pk):
    gate(request)
    account = get_object_or_404(User, pk=pk)
    context = admin_console.account_detail(account)
    events = AuditEvent.objects.filter(
        models.Q(actor=account) | models.Q(target=str(account.pk))
    ).select_related('actor', 'department').order_by('-created_at', 'pk')
    navigation = page_for(request, events, anchor='account-audit', size=25)
    context.update(audit_events=navigation['page'], event_navigation=navigation,
                   refunded=admin_console.refunded_cents([p.pk for p in context['payments']]))
    if settings.QUILLMD_MFA_REQUIRED_ALL:
        context['mfa_reset_form'] = MfaResetForm()
    audit(request.user, 'admin.account_read', account.pk)
    return render(request, 'admin_account.html', context)


@require_POST
@transaction.atomic
def admin_revoke_sessions(request, pk):
    """Sign an account out everywhere WITHOUT changing whether it may sign back in.

    Until now the only way to invalidate a session was to disable the account, which conflates
    'this laptop was left on a train' with 'this person no longer works here'.
    """
    gate(request)
    account = get_object_or_404(User.objects.select_for_update(), pk=pk)
    if account.is_staff and account.pk != request.user.pk:
        raise PermissionDenied('Another administrator cannot be signed out from this screen.')
    account.session_version += 1
    account.save(update_fields=['session_version'])
    audit(request.user, 'admin.sessions_revoked', account.pk, still_enabled=account.is_active)
    messages.success(request, 'Signed out of every session. The account can sign in again; its access was not changed.')
    return redirect(back_to(request, f'/console/accounts/{account.pk}/'))


# --------------------------------------------------------------------------------------
# Organizations, departments, memberships, invitations
# --------------------------------------------------------------------------------------

def admin_organizations(request):
    """The organization tree, in a bounded number of queries and a bounded number of rows.

    ⚠️ The first version looped organizations -> departments -> memberships -> invitations and
    queried per level: 3 + 2·organizations + 2·departments queries, measured at 1213 queries and
    2.5 seconds for 102 organizations with 503 departments and no members at all. Four grouped
    queries and a page of organizations replace it; the page size also bounds the HTML, which was
    876 KB in that same measurement.

    ⚠️ AND `active_owners` COUNTS VERIFIED ACCOUNTS ONLY. `core.security.membership` requires an
    active membership AND an enabled AND **verified** account, so an unverified owner cannot
    exercise the role at all — counting one let the last-active-owner guard leave a department
    whose only owner is unable to invite, create a patient, or restore anyone's access.
    """
    gate(request)
    page = page_for(request, Organization.objects.order_by('name', 'pk'), anchor='', size=20)
    listed = list(page['page'])
    departments = list(Department.objects.filter(organization__in=listed)
                       .select_related('organization').order_by('name', 'pk'))
    members = (Membership.objects.filter(department__in=departments)
               .select_related('user', 'department').order_by('role', 'user__email'))
    invitations = (Invitation.objects.filter(department__in=departments, accepted_at__isnull=True)
                   .select_related('invited_by', 'department').order_by('-created_at', 'pk'))
    wallets = Wallet.objects.filter(organization__in=listed).select_related('organization')
    by_department, invites_by_department, wallets_by_organization = {}, {}, {}
    for membership in members:
        by_department.setdefault(membership.department_id, []).append(membership)
    for invitation in invitations:
        invites_by_department.setdefault(invitation.department_id, []).append(invitation)
    for wallet in wallets:
        wallets_by_organization.setdefault(wallet.organization_id, []).append(wallet)
    departments_by_organization = {}
    for department in departments:
        rows = by_department.get(department.pk, [])
        departments_by_organization.setdefault(department.organization_id, []).append({
            'department': department,
            'memberships': rows,
            'active_owners': sum(1 for m in rows if m.active and m.role == 'owner'
                                 and m.user.is_active and m.user.verified_at),
            'invitations': invites_by_department.get(department.pk, []),
        })
    audit(request.user, 'admin.organizations_read')
    return render(request, 'admin_organizations.html', {
        'may_change_payer': admin_console.may_change_payer(request.user),
        'payer_restriction': admin_console.payer_restriction_note(),
        'organizations': [{'organization': organization,
                           'departments': departments_by_organization.get(organization.pk, []),
                           'wallets': wallets_by_organization.get(organization.pk, [])}
                          for organization in listed],
        'navigation': page, 'roles': Membership.ROLES})


@require_POST
@transaction.atomic
def admin_membership(request, pk):
    """Change a role or department access from the console.

    Two refusals, and both are invariants rather than manners:

    * a STAFF account's membership is not edited here, matching `admin_account`'s refusal to
      change another administrator through a screen with no second pair of eyes;
    * a department is never left with no active owner. `create_department` and `invite_accept`
      both assume an owner exists; removing the last one orphans every patient and template in
      it with no route in the product to restore access.
    """
    gate(request)
    # `of=('self',)` — a bare select_for_update() beside select_related() emits
    # `... INNER JOIN core_user ... FOR UPDATE`, locking the member's user row and the department
    # row as well as the membership actually being written.
    target = get_object_or_404(
        Membership.objects.select_for_update(of=('self',)).select_related('user', 'department'), pk=pk)
    if target.user.is_staff:
        raise PermissionDenied('Administrator memberships are not changed through this screen.')
    role = request.POST.get('role', target.role)
    if role not in dict(Membership.ROLES):
        raise ValidationError('Unknown role.')
    active = request.POST.get('active') == 'on'
    was = (target.role, target.active)
    # Verified too — an unverified owner cannot exercise the role (core.security.membership).
    remaining_owners = (Membership.objects.filter(department=target.department, active=True, role='owner',
                                                  user__is_active=True, user__verified_at__isnull=False)
                        .exclude(pk=target.pk).count())
    if target.role == 'owner' and target.active and not remaining_owners and (role != 'owner' or not active):
        raise ValidationError('This is the department\'s last active owner. Give another member the owner role first; '
                              'a department with no owner cannot invite, create patients or restore access.')
    target.role, target.active = role, active
    target.save(update_fields=['role', 'active'])
    audit(request.user, 'admin.membership_update', target.pk, department=target.department,
          account=target.user.email, role_from=was[0], role_to=role, active_from=was[1], active_to=active)
    messages.success(request, f'{target.user.email} in {target.department.name}: role {role}, '
                              f'access {"enabled" if active else "disabled"}.')
    return redirect(back_to(request, '/console/organizations/'))


@require_POST
@transaction.atomic
def admin_department_payer(request, pk):
    """Set who pays for a department's work.

    `Department.organization_pays` selects the paid wallet at reservation time
    (`billing.payer_wallets`) and is stamped onto each job as `Job.payer`. It decides who is
    billed, it was displayed nowhere in the console, and it could not be changed anywhere in the
    product after the department was created.

    Already-settled work is untouched: `Job.payer` is written at reserve() and never re-read from
    the department, so this changes future requests only. That is stated on the screen, because
    an administrator who believes this is retrospective will reach the wrong conclusion about a
    charge they are explaining to a customer.
    """
    gate(request)
    # ⚠️ ENFORCED HERE, NOT BY HIDING THE FORM. A control that is merely absent from the template
    # is not an authorization boundary; the route is what an ordinary administrator can reach.
    if not admin_console.may_change_payer(request.user):
        raise PermissionDenied(admin_console.payer_restriction_note())
    department = get_object_or_404(
        Department.objects.select_for_update(of=('self',)).select_related('organization'), pk=pk)
    pays = request.POST.get('organization_pays') == 'on'
    reason = (request.POST.get('reason') or '').replace('\x00', '').strip()[:240]
    if len(reason) < 12:
        raise ValidationError('Record why the payer is changing (at least 12 characters). '
                              'It is kept with the audit entry and is the only account of the decision.')
    if request.POST.get('confirm') != 'on':
        raise ValidationError('Confirm that you have read which balance will be billed from now on.')
    was = department.organization_pays
    if pays == was:
        messages.info(request, f'{department.name} already bills to {"the organization" if pays else "each user"}. Nothing changed.')
        return redirect(back_to(request, '/console/organizations/'))
    department.organization_pays = pays
    department.save(update_fields=['organization_pays'])
    if pays:
        Wallet.objects.get_or_create(organization=department.organization, kind='paid')
    audit(request.user, 'admin.department_payer', department.pk, department=department,
          organization_pays_from=was, organization_pays_to=pays, reason=reason)
    messages.success(request, f'{department.name} now bills to '
                              f'{"the organization paid balance" if pays else "each user’s own paid balance"}, '
                              'for requests made from now on. Charges already settled keep the payer recorded on them.')
    return redirect(back_to(request, '/console/organizations/'))


@require_POST
@transaction.atomic
def admin_invitation_revoke(request, pk):
    gate(request)
    invite = get_object_or_404(
        Invitation.objects.select_for_update(of=('self',)).select_related('department'), pk=pk)
    if invite.accepted_at:
        return HttpResponse('Invitation already accepted. Change department membership to revoke access.', status=409)
    invite.expires_at = timezone.now()
    invite.save(update_fields=['expires_at'])
    # No recipient address in the audit record — core/email_delivery.py states the house rule
    # ("store no recipient, body, raw token, error text, or provider response in audit") and the
    # clinician-side equivalent records only the invitation's own id.
    audit(request.user, 'admin.invitation_revoked', invite.pk, department=invite.department)
    messages.success(request, 'Invitation revoked. The link no longer grants access.')
    return redirect(back_to(request, '/console/organizations/'))


# --------------------------------------------------------------------------------------
# Clinic-owner invitations (QUILLMD_REGISTRATION=invite)
# --------------------------------------------------------------------------------------

def admin_clinic_invitations(request):
    """'Invite clinic owner': the only way a NEW organization comes into being in invite mode.

    Creating is available only when QUILLMD_REGISTRATION=invite, the setting that closed self-service
    registration. Listing and revoking stay available in either mode, so an invitation issued before the
    setting changed back can still be withdrawn.
    """
    gate(request)
    invite_mode = settings.QUILLMD_REGISTRATION == 'invite'
    form = ClinicInvitationForm(request.POST or None) if invite_mode else None
    if request.method == 'POST':
        if not invite_mode:
            raise Http404
        if form.is_valid():
            if not rate_limit('clinic-invite:' + str(request.user.pk), limit=30):
                return HttpResponse('Invitation limit reached. Try again later.', status=429)
            from .clinic_invitations import issue
            from .email_delivery import deliver_account_email
            with transaction.atomic():
                invitation, raw = issue(request.user, form.cleaned_data['email'],
                                        form.cleaned_data['organization_name'], form.cleaned_data['department_name'])
            delivery = deliver_account_email(request.user, invitation.pk, invitation.email, 'owner_invitation', raw)
            if delivery.status == 'outbox':
                messages.success(request, 'Clinic owner invitation saved in the private development outbox.')
            elif delivery.status == 'accepted':
                messages.success(request, 'Clinic owner invitation submitted to the email provider. Inbox delivery is not yet confirmed.')
            else:
                messages.warning(request, 'Invitation saved, but email delivery could not be confirmed. Revoke it and send a new one after delivery is repaired.')
            return redirect('admin_clinic_invitations')
    navigation = page_for(request, ClinicInvitation.objects.select_related('invited_by', 'organization')
                          .order_by('-created_at', 'pk'), anchor='clinic-invitations', size=25)
    now = timezone.now()
    audit(request.user, 'admin.clinic_invitations_read')
    return render(request, 'admin_clinic_invitations.html', {
        'form': form, 'invite_mode': invite_mode, 'navigation': navigation,
        'rows': [{'invitation': row, 'status': row.status(now)} for row in navigation['page']]})


@require_POST
@transaction.atomic
def admin_clinic_invitation_revoke(request, pk):
    gate(request)
    invitation = get_object_or_404(ClinicInvitation.objects.select_for_update(of=('self',)), pk=pk)
    if invitation.accepted_at:
        return HttpResponse('Invitation already accepted. Change the organization\'s memberships to remove access.', status=409)
    if not invitation.revoked_at:
        now = timezone.now()
        invitation.revoked_at = now
        invitation.expires_at = min(invitation.expires_at, now)
        invitation.save(update_fields=['revoked_at', 'expires_at'])
        audit(request.user, 'admin.clinic_invitation_revoked', invitation.pk)
    messages.success(request, 'Clinic owner invitation revoked. The link no longer grants access.')
    return redirect(back_to(request, '/console/clinic-invitations/'))


# --------------------------------------------------------------------------------------
# Multi-factor reset (QUILLMD_MFA_REQUIRED_ALL)
# --------------------------------------------------------------------------------------

@require_POST
@transaction.atomic
def admin_mfa_reset(request, pk):
    """Remove a clinical account's authenticators so its holder enrols again at the next sign-in.

    Only while QUILLMD_MFA_REQUIRED_ALL is on: that setting is what makes a clinical account's authenticator
    a sign-in requirement, and so what makes a lost phone a lock-out. Never for an administrator, matching every
    other screen here that refuses to change another administrator. Every live session is invalidated in the
    same transaction, so a session opened with the old device does not outlive it. The reason is recorded with
    the audit entry because it is the only record of how the holder's identity was checked.
    """
    gate(request)
    if not settings.QUILLMD_MFA_REQUIRED_ALL:
        raise Http404
    account = get_object_or_404(User.objects.select_for_update(), pk=pk)
    if account.is_staff:
        raise PermissionDenied('Administrator authenticators are not reset through this screen.')
    form = MfaResetForm(request.POST)
    if not form.is_valid():
        raise ValidationError('Record how the account holder\'s identity was checked (at least 12 characters) '
                              'and confirm the reset.')
    removed, _ = TOTPDevice.objects.filter(user=account).delete()
    account.session_version += 1
    account.save(update_fields=['session_version'])
    audit(request.user, 'admin.mfa_reset', account.pk, devices_removed=removed, sessions_invalidated=True,
          reason=form.cleaned_data['reason'].replace('\x00', '').strip())
    messages.success(request, f'{removed} authenticator(s) removed and every session signed out. '
                              'The account holder sets up a new authenticator after their next password sign-in.')
    return redirect(back_to(request, f'/console/accounts/{account.pk}/detail/'))


# --------------------------------------------------------------------------------------
# Services, configuration and published operations status
# --------------------------------------------------------------------------------------

def admin_services(request):
    gate(request)
    from .context import integration_status
    audit(request.user, 'admin.services_read')
    return render(request, 'admin_services.html', {
        'configured': integration_status(),
        'configuration': admin_console.configuration_rows(),
        'email': admin_console.email_delivery(),
        'processing': admin_console.processing_health(),
        'published': admin_console.published_operations(),
    })


# --------------------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------------------

class _Echo:
    def write(self, value):
        return value


def admin_usage_export(request):
    """Stream the CURRENTLY FILTERED usage as CSV — the same rows the page is showing.

    Built from the same `searched()` + date-window predicates as the Costs section, so the file
    an accountant receives matches the screen the administrator was looking at. Identifiers and
    money only; no clinical column exists in Usage to leak.
    """
    gate(request)
    # A NUL byte cannot exist in a PostgreSQL text column; psycopg raises DataError out of
    # the view, so it must never reach either the LIKE predicate or the audit record.
    query = request.GET.get('q', '').replace('\x00', '').strip()[:100]
    window = admin_console.date_window(request)
    rows = Usage.objects.filter(**admin_console.window_filters(window)).order_by('-created_at', 'pk')
    rows = searched(rows, query, ['user__email', 'department__name', 'organization__name', 'provider',
                                  'provider_request_id', 'provider_resource_id', 'payer'])
    audit(request.user, 'admin.usage_export', query=query, window=window['label'], rows=rows.count())
    writer = csv.writer(_Echo())
    stamp = (window['from'] or 'all') + '_' + (window['to'] or 'all')
    response = StreamingHttpResponse((writer.writerow(row) for row in admin_console.export_rows(rows)),
                                     content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="quillmd-usage-{stamp}.csv"'
    return response
