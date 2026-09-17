from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect
from django.contrib.auth.views import redirect_to_login
from .security import audit
class AccessMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        path=request.path
        public=path in ('/login/','/register/','/health/','/billing/webhook/','/verification/resend/') or path.startswith(('/verify/','/invite/','/static/','/recovery/'))
        if not public:
            if not request.user.is_authenticated:
                # Restore only the page location. Never replay an expired form submission.
                return redirect_to_login(path if request.method == 'GET' else '/', '/login/')
            if not request.user.verified_at: return HttpResponseForbidden('Verify your email before accessing the application.')
            admin_surface=settings.ADMIN_SITE or path.startswith('/console/')
            if admin_surface and not request.user.is_staff: return HttpResponseNotFound()
            if request.user.is_staff and path not in ('/mfa/','/logout/') and not request.user.is_verified(): return redirect('mfa_setup')
        response=self.get_response(request)
        response['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://checkout.stripe.com; object-src 'none'"
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
