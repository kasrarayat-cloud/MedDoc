from django.urls import path

from studio import api, operator, views
from studio.interpretation.readers import web_scope

# Every view runs in a sentinel scope (Gemini migration; design/FINAL.md 10.3): one whose URL names an encounter - or a
# report of one - is labelled by that encounter (new_path for a new-path encounter, legacy_record for a legacy one), and
# every other runs under 'other'. studio.interpretation.readers.web_scope.
NAMES = {'': 'index', 'health/': 'health', 'login/': 'login', 'logout/': 'logout'}
urlpatterns = [path(route, web_scope(view), name=NAMES.get(route)) for route, view in (
    ('', views.index),
    ('health/', views.health),
    ('login/', views.login_view),
    ('logout/', views.logout_view),
    # The customer API (studio.customer_api's allowlist). The administrative trace and the reconciliation of an unknown
    # outcome are no longer here: they are a platform operator's, under /ops/ (CORE-UX-DESIGN.md 5).
    ('api/session', api.session),
    ('api/encounters', api.encounters),
    ('api/encounters/<uuid:encounter_id>', api.encounter_detail),
    ('api/encounters/<uuid:encounter_id>/decisions', api.decisions),
    ('api/encounters/<uuid:encounter_id>/clarifications/<uuid:clarification_id>/confirm', api.confirm_finding),
    ('api/encounters/<uuid:encounter_id>/addenda', api.addenda),
    ('api/encounters/<uuid:encounter_id>/context', api.context),
    ('api/encounters/<uuid:encounter_id>/details', api.details),
    ('api/encounters/<uuid:encounter_id>/details/<uuid:answer_id>/revoke', api.revoke_detail),
    ('api/encounters/<uuid:encounter_id>/stop', api.stop),
    ('api/encounters/<uuid:encounter_id>/resume', api.resume),
    # the recorded retry of a failed reading (FINAL 11.3): an owner or a reviewer, beside resume
    ('api/encounters/<uuid:encounter_id>/retry-reading', api.retry_reading),
    ('api/encounters/<uuid:encounter_id>/second-review', api.second_review),
    ('api/encounters/<uuid:encounter_id>/reports', api.create_report),
    ('api/encounters/<uuid:encounter_id>/original', api.original),
    ('api/reports/<uuid:report_id>/download', api.download_report),
    # Platform-operator diagnostics (studio.operator): every URL answers Django's 404 to anyone without an operator grant.
    ('ops/', operator.index),
    ('ops/assets/ops.js', operator.script),
    ('ops/assets/ops.css', operator.stylesheet),
    ('ops/api/session', operator.session),
    ('ops/api/encounters', operator.encounters),
    ('ops/api/encounters/<uuid:encounter_id>', operator.encounter_detail),
    ('ops/api/encounters/<uuid:encounter_id>/trace', operator.trace),
    ('ops/api/encounters/<uuid:encounter_id>/reports', operator.encounter_reports),
    ('ops/api/encounters/<uuid:encounter_id>/original', operator.original),
    ('ops/api/encounters/<uuid:encounter_id>/reconcile', operator.reconcile),
    # the operator's retry of a failed reading (FINAL 11.3, C5: the recorded override of a cut-off answer is theirs)
    ('ops/api/encounters/<uuid:encounter_id>/retry-reading', operator.retry_reading),
    # the interpreter hold (FINAL 11.2): its state, and its recorded release
    ('ops/api/interpreter', operator.interpreter),
    ('ops/api/reports/<uuid:report_id>/download', operator.download_report),
)]
