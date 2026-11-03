from django.urls import path

from studio import api, views

urlpatterns = [
    path('', views.index, name='index'),
    path('health/', views.health, name='health'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('api/session', api.session),
    path('api/encounters', api.encounters),
    path('api/encounters/<uuid:encounter_id>', api.encounter_detail),
    path('api/encounters/<uuid:encounter_id>/trace', api.trace),
    path('api/encounters/<uuid:encounter_id>/decisions', api.decisions),
    path('api/encounters/<uuid:encounter_id>/clarifications/<uuid:clarification_id>/confirm',
         api.confirm_finding),
    path('api/encounters/<uuid:encounter_id>/addenda', api.addenda),
    path('api/encounters/<uuid:encounter_id>/context', api.context),
    path('api/encounters/<uuid:encounter_id>/stop', api.stop),
    path('api/encounters/<uuid:encounter_id>/resume', api.resume),
    path('api/encounters/<uuid:encounter_id>/reconcile', api.reconcile),
    path('api/encounters/<uuid:encounter_id>/second-review', api.second_review),
    path('api/encounters/<uuid:encounter_id>/reports', api.create_report),
    path('api/encounters/<uuid:encounter_id>/original', api.original),
    path('api/reports/<uuid:report_id>/download', api.download_report),
]
