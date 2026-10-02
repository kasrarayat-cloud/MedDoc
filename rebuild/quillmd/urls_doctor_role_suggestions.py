"""The doctor surface's URLconf while QUILLMD_ROLE_SUGGESTIONS is on: every route of quillmd.urls_doctor and the act that
enters a role suggestion as the clinician's own answer (core.views.accept_role_suggestion).

core.middleware.AccessMiddleware resolves doctor-surface requests against this list only while the setting is on, and
against quillmd.urls_doctor otherwise. With the setting off the act is therefore routable by no request at all - not
even by CommonMiddleware's slash redirect, which tests path + '/' against the request's URLconf and named the route
while it was mounted everywhere and refused inside its view (refutation round 2, I2-1/A2). The setting off is exactly
the deployment without the feature. The patterns are the SAME objects as quillmd.urls_doctor's, not copies.
"""
from django.urls import path

from core import views
from quillmd.urls_doctor import urlpatterns as _doctor

urlpatterns = _doctor + [path('encounters/<uuid:pk>/role-suggestion/', views.accept_role_suggestion,
                              name='accept_role_suggestion')]
