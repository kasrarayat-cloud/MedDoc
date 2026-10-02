from django.conf import settings
from django.core.handlers.exception import response_for_exception
from django.http import Http404, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect
from django.contrib.auth.views import redirect_to_login
from .security import audit
#: The doctor surface resolves against a URLconf that mounts no console route (quillmd/urls_doctor.py).
DOCTOR_URLCONF='quillmd.urls_doctor'
#: ... and, only while QUILLMD_ROLE_SUGGESTIONS is on, against the same routes plus the role-suggestion act.
ROLE_SUGGESTIONS_URLCONF='quillmd.urls_doctor_role_suggestions'
def role_act_routed(request):
    """Whether THIS request resolves against the URLconf that mounts the role-suggestion act: the one decision the page
    reads to offer a suggestion and its act (core.views.encounter_detail), so the page and the route cannot disagree.
    (Refutation round 3, RS3A-1: the page read the setting, the route exists only on the doctor surface, and the
    administration surface - the root URLconf - rendered the act and raised NoReverseMatch.)"""
    return getattr(request,'urlconf',None)==ROLE_SUGGESTIONS_URLCONF
def console_path(path_info):
    return path_info=='/console' or path_info.startswith('/console/')
class AccessMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        # Every decision here is on PATH_INFO, the path Django resolves. request.path is SCRIPT_NAME + PATH_INFO, and
        # SCRIPT_NAME is a client header gunicorn honours: '/x' made '/x/console/' of a console request and the doctor
        # surface served the console (refutation R1).
        path=request.path_info
        if not settings.ADMIN_SITE:
            from .destination_roles import suggestions_enabled
            request.urlconf=ROLE_SUGGESTIONS_URLCONF if suggestions_enabled() else DOCTOR_URLCONF
            # The console exists on the administration surface only. On the doctor host every /console path answers the
            # application's own 404 page to every caller — signed out, clinician or administrator, before the MFA
            # redirect and before CommonMiddleware's slash redirect (which named the route: refutation R2), exactly as
            # production nginx answers it (inventory 7A, F1).
            if console_path(path): return self.secured(request,response_for_exception(request,Http404()))
        public=path in ('/preview/sign-in/','/preview/sign-out/','/login/','/register/','/health/','/billing/webhook/','/verification/resend/') or path.startswith(('/verify/','/invite/','/static/','/recovery/'))
        if not public:
            if not request.user.is_authenticated:
                # Restore only the page location. Never replay an expired form submission. (The location the browser
                # asked for, request.path, as before: it is where to return, not a decision.)
                return redirect_to_login(request.path if request.method == 'GET' else '/', '/login/')
            if not request.user.verified_at: return HttpResponseForbidden('Verify your email before accessing the application.')
            if settings.ADMIN_SITE and not request.user.is_staff: return HttpResponseNotFound()
            if (request.user.is_staff or settings.QUILLMD_MFA_REQUIRED_ALL) and path not in ('/mfa/','/logout/') and not request.user.is_verified(): return redirect('mfa_setup')
        return self.secured(request,self.get_response(request))
    def secured(self,request,response):
        path=request.path_info
        # media-src blob: lets the doctor play back a browser recording before sending it; without it the
        # default-src fallback blocked the preview the page asks them to listen to (measured in Chromium).
        response['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://checkout.stripe.com; object-src 'none'"
        response['X-Frame-Options']='DENY'
        response['Permissions-Policy']='microphone=(self), camera=(), geolocation=()'
        if not path.startswith('/static/'): response['Cache-Control']='no-store, private'
        return response
    def process_exception(self,request,exception):
        from django.core.exceptions import ValidationError
        from django.http import HttpResponseBadRequest
        if isinstance(exception,ValidationError):
            # Response text is escaped by HttpResponse's plain text type.
            return HttpResponseBadRequest('; '.join(exception.messages),content_type='text/plain')
