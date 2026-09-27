import os
from django.conf import settings
from .models import Membership, CodeSet
from .billing import stripe_test_key_configured,welcome_credit_label
from .coding import cpt_licensed

def common(request):
    return {'synthetic_only':settings.SYNTHETIC_ONLY,'is_admin_site':settings.ADMIN_SITE,'admin_surface':settings.ADMIN_SITE,'current_memberships':Membership.objects.filter(user=request.user,active=True).select_related('department__organization') if request.user.is_authenticated else [],'integrations':integration_status(),
            'registration_open':settings.QUILLMD_REGISTRATION=='open','clinic_invitations_enabled':settings.QUILLMD_REGISTRATION=='invite',
            'welcome_credit_label':welcome_credit_label()}

def integration_status():
    """What is CONFIGURED. Deliberately not a health report — see the console Services page.

    Each row now carries a `severity` ('success' | 'warning' | 'error') because the template
    previously wrote the whole status SENTENCE into the CSS class
    (`class="badge {{ integration.status }}"`). No sentence matches a badge variant, so every row
    rendered in the same neutral grey: 'Not connected' and 'Unavailable' were visually identical
    to 'Licensed feed configured'. A status panel whose only job is to be scanned returned no
    signal at all.

    The `status` and `detail` STRINGS are unchanged — two of them are pinned by tests
    (`test_stripe_credentials`, `test_code_release_dates`) and they are the words an operator
    reads. Only the badge colour is new.
    """
    transcription = bool(os.getenv('DEEPGRAM_API_KEY'))
    payments = stripe_test_key_configured(settings.STRIPE_SECRET_KEY)
    licensed = cpt_licensed()
    return [
      {'name':'Answer generation','status':'Live API configured' if settings.AI_MODE=='live' else 'Synthetic fixture','severity':'success' if settings.AI_MODE=='live' else 'warning','detail':settings.AI_MODEL if settings.AI_MODE=='live' else 'Exact labelled-note extraction; no provider cost.'},
      {'name':'Transcription','status':('Configured; synthetic audio only' if settings.SYNTHETIC_ONLY else 'Configured') if transcription else 'Unavailable','severity':'success' if transcription else 'error','detail':'Recorded audio is sent only on your explicit request.'},
      {'name':'Payments','status':'Stripe sandbox key configured' if payments else 'Not connected','severity':'success' if payments else 'error','detail':'Configuration alone does not verify payments. No subscriptions or automatic top-ups.'},
      {'name':'CPT terminology','status':'Licensed feed configured' if licensed else ('License expired' if settings.CPT_LICENSE_ID else 'License required'),'severity':'success' if licensed else ('error' if settings.CPT_LICENSE_ID else 'warning'),'detail':'CPT suggestions remain disabled without a licensed, dated release.'},
      {'name':'Account email','status':('Provider configured' if settings.RESEND_API_KEY else 'Provider key absent') if settings.QUILLMD_EMAIL_MODE=='resend' else 'Private file outbox','severity':('success' if settings.RESEND_API_KEY else 'error') if settings.QUILLMD_EMAIL_MODE=='resend' else 'warning','detail':'Verification, recovery and invitation links are delivered here. Configuration is not delivery: the Services page counts actual outcomes.'},
      {'name':'Patient data','status':'Synthetic only','severity':'warning','detail':'Patient-data agreements and processing controls have not been verified.'} if settings.SYNTHETIC_ONLY else
      {'name':'Patient data','status':'Real patient data','severity':'success','detail':'QUILLMD_DATA_MODE=real: the production settings were checked when this process started. Agreements with processors are recorded outside the application.'},
    ]
