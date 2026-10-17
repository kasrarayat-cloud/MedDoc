from django.conf import settings
from django.urls import path
from core import views as v
from core import recovery
from core import preview_access
from core import preparation_views as preparation
from core.doctor_guide import doctor_guide
urlpatterns=[path('doctor-guide/',doctor_guide,name='doctor_guide')]
urlpatterns+=[path('preview/sign-in/',preview_access.sign_in,name='preview_sign_in'),path('preview/sign-out/',preview_access.sign_out,name='preview_sign_out')]
urlpatterns+=[path('recovery/',recovery.recovery_request,name='recovery_request'),path('recovery/confirm/<uidb64>/<token>/',recovery.RecoveryConfirmView.as_view(),name='recovery_confirm'),path('recovery/complete/',recovery.recovery_complete,name='recovery_complete'),path('verification/resend/',recovery.verification_resend,name='verification_resend')]
urlpatterns += [
    path('templates/preview-frame/',preparation.preview_frame,name='docx_preview_frame'),
    path('templates/<uuid:pk>/preparation/',preparation.detail,name='template_preparation'),
    path('templates/<uuid:pk>/preparation/status/',preparation.status,name='template_preparation_status'),
    path('templates/<uuid:pk>/preparation/corrections/',preparation.corrections,name='template_preparation_correct'),
    path('templates/<uuid:pk>/preparation/continue-review/',preparation.continue_review,name='template_preparation_continue'),
    path('templates/<uuid:pk>/preparation/approve/',preparation.approval,name='template_preparation_approve'),
    path('templates/<uuid:pk>/preparation/preview/<str:kind>/',preparation.preview_bytes,name='template_preparation_preview'),
    path('templates/<uuid:pk>/preparation/download/',preparation.prepared_download,name='template_preparation_download'),
]
urlpatterns+=[path('health/',v.health,name='health'),path('login/',v.login_view,name='login'),path('logout/',v.logout_view,name='logout'),path('register/',v.register,name='register'),path('mfa/',v.mfa_setup,name='mfa_setup'),path('verify/<str:raw>/',v.verify,name='verify'),path('invite/<str:raw>/',v.invite_accept,name='invite_accept'),path('billing/webhook/',v.webhook,name='webhook')]
urlpatterns += [path('console/',v.admin_dashboard,name='admin_dashboard'),path('console/audit/',v.audit_view,name='audit'),path('console/accounts/<uuid:pk>/',v.admin_account,name='admin_account'),path('console/usage/<uuid:pk>/reconcile/',v.admin_reconcile_usage,name='admin_reconcile_usage'),path('console/platform-costs/',v.admin_platform_cost,name='admin_platform_cost'),path('console/jobs/<uuid:pk>/resolve/',v.admin_resolve_job,name='admin_resolve_job')]
urlpatterns += [path('',v.admin_dashboard if settings.ADMIN_SITE else v.dashboard,name='dashboard'),path('templates/upload/',v.template_upload,name='template_upload'),path('templates/<uuid:pk>/',v.template_detail,name='template_detail'),path('templates/<uuid:pk>/original/',v.template_original,name='template_original'),path('encounters/new/',v.encounter_new,name='encounter_new'),path('encounters/<uuid:pk>/',v.encounter_detail,name='encounter_detail'),path('encounters/<uuid:pk>/generate/',v.generate_view,name='generate'),path('encounters/<uuid:pk>/save/',v.save_answers,name='save_answers'),path('encounters/<uuid:pk>/finalize/',v.finalize,name='finalize'),path('encounters/<uuid:pk>/export/',v.export,name='export'),path('encounters/<uuid:pk>/voice/',v.voice,name='voice'),path('encounters/<uuid:pk>/voice/approve/',v.voice_approve,name='voice_approve'),path('encounters/<uuid:pk>/coding/',v.coding,name='coding'),path('encounters/<uuid:pk>/coding/<uuid:code_pk>/accept/',v.accept_code,name='accept_code'),path('patients/',v.patients,name='patients'),path('team/',v.team,name='team'),path('team/departments/',v.create_department,name='create_department'),path('team/membership/<uuid:pk>/',v.membership_update,name='membership_update'),path('billing/',v.billing,name='billing'),path('billing/checkout/',v.checkout,name='checkout'),path('api/patients/',v.api_patients,name='api_patients'),path('api/encounters/<uuid:pk>/',v.api_encounter,name='api_encounter')]
urlpatterns += [path('encounters/<uuid:pk>/notes/',v.encounter_notes,name='encounter_notes'),path('encounters/<uuid:pk>/jobs/<uuid:job_pk>/cancel/',v.job_cancel,name='job_cancel')]
urlpatterns += [path('jobs/<uuid:pk>/result/',v.job_result,name='job_result')]
urlpatterns += [path('encounters/<uuid:pk>/status/',v.encounter_status,name='encounter_status')]
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
]

from core import semantic_preparation_views as definitions
urlpatterns += [
    path('templates/<uuid:pk>/definitions/start/',definitions.start,name='template_definitions_start'),
    path('definition-preparations/<uuid:pk>/',definitions.detail,name='template_definitions'),
    path('definition-preparations/<uuid:pk>/status/',definitions.status,name='template_definitions_status'),
    path('definition-preparations/<uuid:pk>/corrections/',definitions.corrections,name='template_definitions_correct'),
    path('definition-preparations/<uuid:pk>/approve/',definitions.approval,name='template_definitions_approve'),
]

from core.document_review import submit as document_review_submit
urlpatterns += [path('encounters/<uuid:pk>/review/',document_review_submit,name='document_review')]
from core.semantic_revalidation_views import submit as semantic_revalidation_submit
urlpatterns += [path('encounters/<uuid:pk>/recheck-retained/',semantic_revalidation_submit,name='semantic_revalidation')]

from core import coding_views
from core.coding_export import export_with_codes
from core.coding_draft_export import export_synthetic_coding_draft
urlpatterns += [
    path('encounters/<uuid:pk>/export-with-codes/', export_with_codes, name='export_with_codes'),
    path('encounters/<uuid:pk>/export-coding-draft/', export_synthetic_coding_draft, name='export_synthetic_coding_draft'),
    path('encounters/<uuid:pk>/coding/status/', coding_views.status, name='coding_status'),
    path('encounters/<uuid:pk>/coding/request/', coding_views.request_run, name='coding_request'),
    path('encounters/<uuid:pk>/coding/context/', coding_views.context, name='coding_context'),
    path('encounters/<uuid:pk>/coding/runs/<uuid:run_pk>/selections/', coding_views.selections, name='coding_selections'),
    path('encounters/<uuid:pk>/coding/runs/<uuid:run_pk>/approve/', coding_views.approval, name='coding_approval'),
    path('encounters/<uuid:pk>/coding/runs/<uuid:run_pk>/output-decision/', coding_views.output_decision, name='coding_output_decision'),
]
