"""Private, synthetic doctor walkthrough; reading it creates no clinical work."""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET


@login_required
@require_GET
def doctor_guide(request):
    if settings.ADMIN_SITE or not settings.SYNTHETIC_ONLY:
        raise Http404
    return render(request, 'doctor_guide.html')
