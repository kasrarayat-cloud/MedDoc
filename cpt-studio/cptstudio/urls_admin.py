"""The admin host's URLs (admin.quillmd.com; owner direction 2026-11-23, DECISIONS D396): the operator sign-in and the
console, and nothing of the doctor app or its API. studio.hosts chooses this urlconf by the request's host.

The console's routes are the full urlconf's own ops/ routes, taken from it so the two hosts can never drift apart, each
wrapped by studio.hosts.signed_out_to_sign_in; operator_view inside every one of them stays the security gate."""
from django.urls import path

from cptstudio import urls as customer_urls
from studio import views
from studio.hosts import signed_out_to_sign_in

OPEN_ROUTES = ('', 'health/', 'login/', 'logout/', 'ops')  # every other route here is a console route (tests pin it)

urlpatterns = [
    path('', views.admin_home),
    path('health/', views.health),
    path('login/', views.admin_login_view),
    path('logout/', views.logout_view),
    path('ops', views.admin_ops_slash),
] + [
    path(str(pattern.pattern), signed_out_to_sign_in(pattern.callback))
    for pattern in customer_urls.urlpatterns if str(pattern.pattern).startswith('ops/')
]
