from django.urls import path

from studio import api, operator, views

urlpatterns = [
    path('', views.index, name='index'),
    path('health/', views.health, name='health'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # The customer API (BUILD-SPEC 6; studio.api, its payloads studio.customer's).
    path('api/session', api.session),
    path('api/encounters', api.encounters),
    path('api/encounters/<uuid:encounter_id>', api.encounter_detail),
    path('api/encounters/<uuid:encounter_id>/answers', api.answers),
    path('api/encounters/<uuid:encounter_id>/decisions', api.decide),
    path('api/encounters/<uuid:encounter_id>/stop', api.stop),
    path('api/encounters/<uuid:encounter_id>/resume', api.resume),
    path('api/encounters/<uuid:encounter_id>/retry', api.retry),
    path('api/encounters/<uuid:encounter_id>/reports', api.create_report),
    path('api/encounters/<uuid:encounter_id>/original', api.original),
    path('api/reports/<uuid:report_id>/download', api.download_report),
    # The platform-operator console (BUILD-SPEC 9; studio.operator): every URL answers Django's 404 to anyone without an
    # operator grant.
    path('ops/', operator.index),
    path('ops/encounters/<uuid:encounter_id>', operator.encounter_page),
    path('ops/encounters/<uuid:encounter_id>/original', operator.original),
    path('ops/encounters/<uuid:encounter_id>/reconcile', operator.reconcile),
    path('ops/encounters/<uuid:encounter_id>/retry', operator.retry),
    path('ops/holds/release', operator.release_holds),
]
