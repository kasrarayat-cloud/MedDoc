from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect
from django.contrib.auth.views import redirect_to_login
from .security import audit
class AccessMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        path=request.path
        public=path in ('/preview/sign-in/','/preview/sign-out/','/login/','/register/','/health/','/billing/webhook/','/verification/resend/') or path.startswith(('/verify/','/invite/','/static/','/recovery/'))
        if not public:
            if not request.user.is_authenticated:
                # Restore only the page location. Never replay an expired form submission.
                return redirect_to_login(path if request.method == 'GET' else '/', '/login/')
            if not request.user.verified_at: return HttpResponseForbidden('Verify your email before accessing the application.')
            admin_surface=settings.ADMIN_SITE or path.startswith('/console/')
            if admin_surface and not request.user.is_staff: return HttpResponseNotFound()
            if request.user.is_staff and path not in ('/mfa/','/logout/') and not request.user.is_verified(): return redirect('mfa_setup')
        response=self.get_response(request)
        # media-src blob: lets the doctor play back a browser recording before sending it; without it the
        # default-src fallback blocked the preview the page asks them to listen to (measured in Chromium).
        response['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://checkout.stripe.com; object-src 'none'"
        response['X-Frame-Options']='DENY'
        if request.resolver_match and request.resolver_match.url_name=='docx_preview_frame' and response.status_code==200:
            origin=request.scheme+'://'+request.get_host()
            # Only this opaque, script-only frame may render Word's generated inline
            # styles. It has no network, cookies/storage, forms or navigation allowance.
            response['Content-Security-Policy']=("default-src 'none'; script-src "+origin+"; style-src "+origin+" 'unsafe-inline'; "
                "img-src data: blob:; font-src data: blob:; connect-src 'none'; object-src 'none'; "
                "frame-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'; sandbox allow-scripts")
            response['X-Frame-Options']='SAMEORIGIN'
        response['Permissions-Policy']='microphone=(self), camera=(), geolocation=()'
        if not path.startswith('/static/'): response['Cache-Control']='no-store, private'
        return response
    def process_exception(self,request,exception):
        from django.core.exceptions import ValidationError
        from django.http import HttpResponseBadRequest
        if isinstance(exception,ValidationError):
            # Response text is escaped by HttpResponse's plain text type.
            return HttpResponseBadRequest('; '.join(exception.messages),content_type='text/plain')
