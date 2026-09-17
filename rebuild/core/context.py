import os
from django.conf import settings
from .models import Membership, CodeSet
from .billing import stripe_test_key_configured

def common(request):
    return {'synthetic_only':settings.SYNTHETIC_ONLY,'is_admin_site':settings.ADMIN_SITE,'admin_surface':settings.ADMIN_SITE,'current_memberships':Membership.objects.filter(user=request.user,active=True).select_related('department__organization') if request.user.is_authenticated else [],'integrations':integration_status()}

def integration_status():
    return [
      {'name':'Answer generation','status':'Live API configured' if settings.AI_MODE=='live' else 'Synthetic fixture','detail':settings.AI_MODEL if settings.AI_MODE=='live' else 'Exact labelled-note extraction; no provider cost.'},
      {'name':'Transcription','status':'Configured; synthetic audio only' if os.getenv('DEEPGRAM_API_KEY') else 'Unavailable','detail':'Recorded audio is sent only on your explicit request.'},
      {'name':'Payments','status':'Stripe sandbox key configured' if stripe_test_key_configured(settings.STRIPE_SECRET_KEY) else 'Not connected','detail':'Configuration alone does not verify payments. No subscriptions or automatic top-ups.'},
      {'name':'CPT terminology','status':'Licensed feed configured' if settings.CPT_LICENSE_ID else 'License required','detail':'CPT suggestions remain disabled without a licensed, dated release.'},
      {'name':'Patient data','status':'Synthetic only','detail':'Patient-data agreements and processing controls have not been verified.'},
    ]
