from django.conf import settings
from django.urls import path
from core import views as v
from core import recovery
from core import preview_access
from core import mapping_views
from core import retention_views
from core import soap_views
urlpatterns_soap = [path('templates/soap/', soap_views.start, name='soap_start')]
urlpatterns_retention=[
    path('console/retention/',retention_views.page,name='retention_holds'),
    path('console/retention/holds/',retention_views.create,name='retention_hold_create'),
    path('console/retention/holds/<uuid:pk>/release/',retention_views.release,name='retention_hold_release'),
]
urlpatterns=[path('preview/sign-in/',preview_access.sign_in,name='preview_sign_in'),path('preview/sign-out/',preview_access.sign_out,name='preview_sign_out')]
urlpatterns+=urlpatterns_retention
urlpatterns+=urlpatterns_soap
urlpatterns += [path('templates/<uuid:pk>/assistance/',mapping_views.review,name='mapping_assistance')]
urlpatterns+=[path('recovery/',recovery.recovery_request,name='recovery_request'),path('recovery/confirm/<uidb64>/<token>/',recovery.RecoveryConfirmView.as_view(),name='recovery_confirm'),path('recovery/complete/',recovery.recovery_complete,name='recovery_complete'),path('verification/resend/',recovery.verification_resend,name='verification_resend')]
urlpatterns+=[path('health/',v.health,name='health'),path('health/ready/',v.health_ready,name='health_ready'),path('login/',v.login_view,name='login'),path('logout/',v.logout_view,name='logout'),path('register/',v.register,name='register'),path('mfa/',v.mfa_setup,name='mfa_setup'),path('verify/<str:raw>/',v.verify,name='verify'),path('invite/<str:raw>/',v.invite_accept,name='invite_accept'),path('billing/webhook/',v.webhook,name='webhook')]
urlpatterns += [path('console/',v.admin_dashboard,name='admin_dashboard'),path('console/audit/',v.audit_view,name='audit'),path('console/accounts/<uuid:pk>/',v.admin_account,name='admin_account'),path('console/usage/<uuid:pk>/reconcile/',v.admin_reconcile_usage,name='admin_reconcile_usage'),path('console/platform-costs/',v.admin_platform_cost,name='admin_platform_cost'),path('console/jobs/<uuid:pk>/resolve/',v.admin_resolve_job,name='admin_resolve_job')]
urlpatterns += [path('',v.admin_dashboard if settings.ADMIN_SITE else v.dashboard,name='dashboard'),path('templates/upload/',v.template_upload,name='template_upload'),path('templates/<uuid:pk>/',v.template_detail,name='template_detail'),path('templates/<uuid:pk>/original/',v.template_original,name='template_original'),path('encounters/new/',v.encounter_new,name='encounter_new'),path('encounters/<uuid:pk>/',v.encounter_detail,name='encounter_detail'),path('encounters/<uuid:pk>/generate/',v.generate_view,name='generate'),path('encounters/<uuid:pk>/save/',v.save_answers,name='save_answers'),path('encounters/<uuid:pk>/finalize/',v.finalize,name='finalize'),path('encounters/<uuid:pk>/export/',v.export,name='export'),path('encounters/<uuid:pk>/voice/',v.voice,name='voice'),path('encounters/<uuid:pk>/voice/approve/',v.voice_approve,name='voice_approve'),path('encounters/<uuid:pk>/coding/',v.coding,name='coding'),path('encounters/<uuid:pk>/coding/<uuid:code_pk>/accept/',v.accept_code,name='accept_code'),path('encounters/<uuid:pk>/coding/<uuid:code_pk>/withdraw/',v.withdraw_code,name='withdraw_code'),path('patients/',v.patients,name='patients'),path('team/',v.team,name='team'),path('team/departments/',v.create_department,name='create_department'),path('team/membership/<uuid:pk>/',v.membership_update,name='membership_update'),path('billing/',v.billing,name='billing'),path('billing/checkout/',v.checkout,name='checkout'),path('api/patients/',v.api_patients,name='api_patients'),path('api/encounters/<uuid:pk>/',v.api_encounter,name='api_encounter')]
urlpatterns += [path('encounters/<uuid:pk>/notes/',v.encounter_notes,name='encounter_notes'),path('encounters/<uuid:pk>/clear-review/',v.clear_review,name='clear_review'),path('encounters/<uuid:pk>/jobs/<uuid:job_pk>/cancel/',v.job_cancel,name='job_cancel')]
urlpatterns += [path('jobs/<uuid:pk>/result/',v.job_result,name='job_result')]
urlpatterns += [path('team/invitations/<uuid:pk>/revoke/',v.invitation_revoke,name='invitation_revoke')]

urlpatterns += [path('console/jobs/<uuid:pk>/',v.admin_job_detail,name='admin_job_detail'),path('billing/jobs/<uuid:pk>/',v.billing_job_detail,name='billing_job_detail')]

# Administration console, added 2026-09-21. New views live in core/admin_views.py so that
# core/views.py — a file several parallel workstreams edit — takes the smallest possible diff.
from core import admin_views as a
urlpatterns += [
    path('console/accounts/<uuid:pk>/detail/', a.admin_account_page, name='admin_account_page'),
    path('console/accounts/<uuid:pk>/sessions/', a.admin_revoke_sessions, name='admin_revoke_sessions'),
    path('console/organizations/', a.admin_organizations, name='admin_organizations'),
    path('console/memberships/<uuid:pk>/', a.admin_membership, name='admin_membership'),
    path('console/departments/<uuid:pk>/payer/', a.admin_department_payer, name='admin_department_payer'),
    path('console/invitations/<uuid:pk>/revoke/', a.admin_invitation_revoke, name='admin_invitation_revoke'),
    path('console/services/', a.admin_services, name='admin_services'),
    path('console/usage.csv', a.admin_usage_export, name='admin_usage_export'),
    path('console/clinic-invitations/', a.admin_clinic_invitations, name='admin_clinic_invitations'),
    path('console/clinic-invitations/<uuid:pk>/revoke/', a.admin_clinic_invitation_revoke, name='admin_clinic_invitation_revoke'),
    path('console/accounts/<uuid:pk>/mfa-reset/', a.admin_mfa_reset, name='admin_mfa_reset'),
]

# Clinic-owner invitation acceptance (QUILLMD_REGISTRATION=invite). Public through the '/invite/' prefix, like
# department invitations; the str converter cannot match '/', so it never shadows 'invite/<raw>/'.
from core import clinic_invitations
urlpatterns += [path('invite/clinic/<str:raw>/', clinic_invitations.accept, name='clinic_invite_accept')]

from core import disposition_views
urlpatterns += [path('console/disposition/',disposition_views.page,name='disposition_review'),path('console/restore-preparation/',disposition_views.restore,name='restore_preparation')]

from core import disposition_execution_views
urlpatterns += [path('console/disposition-execution/', disposition_execution_views.page, name='disposition_execution')]
