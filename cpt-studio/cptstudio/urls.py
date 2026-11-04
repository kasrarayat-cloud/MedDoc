from django.urls import path

from studio import api, operator, views

urlpatterns = [
    path('', views.index, name='index'),
    path('health/', views.health, name='health'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # The customer API (studio.customer_api's allowlist). The administrative trace and the reconciliation of an unknown
    # outcome are no longer here: they are a platform operator's, under /ops/ (CORE-UX-DESIGN.md 5).
    path('api/session', api.session),
    path('api/encounters', api.encounters),
    path('api/encounters/<uuid:encounter_id>', api.encounter_detail),
    path('api/encounters/<uuid:encounter_id>/decisions', api.decisions),
    path('api/encounters/<uuid:encounter_id>/clarifications/<uuid:clarification_id>/confirm',
         api.confirm_finding),
    path('api/encounters/<uuid:encounter_id>/addenda', api.addenda),
    path('api/encounters/<uuid:encounter_id>/context', api.context),
    path('api/encounters/<uuid:encounter_id>/stop', api.stop),
    path('api/encounters/<uuid:encounter_id>/resume', api.resume),
    path('api/encounters/<uuid:encounter_id>/second-review', api.second_review),
    path('api/encounters/<uuid:encounter_id>/reports', api.create_report),
    path('api/encounters/<uuid:encounter_id>/original', api.original),
    path('api/reports/<uuid:report_id>/download', api.download_report),
    # Platform-operator diagnostics (studio.operator): every URL answers Django's 404 to anyone without an operator grant.
    path('ops/', operator.index),
    path('ops/assets/ops.js', operator.script),
    path('ops/assets/ops.css', operator.stylesheet),
    path('ops/api/session', operator.session),
    path('ops/api/encounters', operator.encounters),
    path('ops/api/encounters/<uuid:encounter_id>', operator.encounter_detail),
    path('ops/api/encounters/<uuid:encounter_id>/trace', operator.trace),
    path('ops/api/encounters/<uuid:encounter_id>/reports', operator.encounter_reports),
    path('ops/api/encounters/<uuid:encounter_id>/original', operator.original),
    path('ops/api/encounters/<uuid:encounter_id>/reconcile', operator.reconcile),
    path('ops/api/reports/<uuid:report_id>/download', operator.download_report),
]
