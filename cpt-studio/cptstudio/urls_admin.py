"""The admin host's URLs (admin.quillmd.com; owner direction 2026-11-23, DECISIONS D396): the operator sign-in and the
console, and nothing of the doctor app or its API. studio.hosts chooses this urlconf by the request's host.

The console's routes are the full urlconf's own ops/ routes, taken from it so the two hosts can never drift apart, each
wrapped by studio.hosts.signed_out_to_sign_in; operator_view inside every one of them stays the security gate."""
from django.urls import path

from cptstudio import urls as customer_urls
from studio import second_factor_views, views
from studio.hosts import signed_out_to_sign_in

# every other route here is a console route (tests pin it); release 1 adds the account and session routes both hosts
# have and the second factor's, the admin host's alone (RELEASE-1-SPEC 3.4)
OPEN_ROUTES = ('', 'health/', 'login/', 'logout/', 'ops', 'account/', 'logout/everywhere', 'session/activity',
               'login/second-factor', 'login/second-factor/options', 'login/enrol', 'login/enrol/options',
               'login/recovery')

urlpatterns = [
    path('', views.admin_home),
    path('health/', views.health),
    path('login/', views.admin_login_view),
    path('logout/', views.logout_view),
    path('ops', views.admin_ops_slash),
    # release 1's routes (RELEASE-1-SPEC 3.4): the account and session routes (B4, B5) and the second factor (B2)
    path('account/', views.account_security),
    path('logout/everywhere', views.logout_everywhere),
    path('session/activity', views.activity_ping),
    path('login/second-factor', second_factor_views.second_factor),
    path('login/second-factor/options', second_factor_views.second_factor_options),
    path('login/enrol', second_factor_views.enrol),
    path('login/enrol/options', second_factor_views.enrol_options),
    path('login/recovery', second_factor_views.recovery),
] + [
    path(str(pattern.pattern), signed_out_to_sign_in(pattern.callback))
    for pattern in customer_urls.urlpatterns if str(pattern.pattern).startswith('ops/')
]
