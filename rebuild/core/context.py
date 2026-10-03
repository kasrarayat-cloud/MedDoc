import os
from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone
from .models import Membership, CodeSet
from .billing import stripe_key_configured,welcome_credit_label
from .coding import cpt_license_current, cpt_licensed

def common(request):
    return {'synthetic_only':settings.SYNTHETIC_ONLY,'is_admin_site':settings.ADMIN_SITE,'admin_surface':settings.ADMIN_SITE,'current_memberships':Membership.objects.filter(user=request.user,active=True).select_related('department__organization') if request.user.is_authenticated else [],'integrations':integration_status(),
            'registration_open':settings.QUILLMD_REGISTRATION=='open','clinic_invitations_enabled':settings.QUILLMD_REGISTRATION=='invite',
            'mfa_required_all':settings.QUILLMD_MFA_REQUIRED_ALL,'welcome_credit_label':welcome_credit_label()}

def icd_configuration():
    """Release metadata only: no clinical records or code descriptions are read.

    Today's coverage is an operational warning, not the release choice for an
    encounter. The coding workflow continues to use its date of service.
    """
    row = {'name':'ICD-10-CM terminology', 'severity':'warning'}
    review = 'Each encounter uses its date of service. Suggestions require clinician review.'
    try:
        releases = list(CodeSet.objects.filter(system='ICD-10-CM').order_by('effective_from', 'version')
                        .values('version', 'effective_from', 'effective_until'))
    except DatabaseError:
        return {**row, 'status':'Release metadata unavailable', 'severity':'error',
                'detail':'Loaded diagnosis releases could not be read. '+review}
    today = timezone.localdate()
    current = [item for item in releases if item['effective_from'] <= today <= item['effective_until']]
    history = f'{len(releases)} loaded release(s). '
    if len(current) == 1:
        item = current[0]
        return {**row, 'status':'Current release: '+item['version'], 'severity':'success',
                'detail':f"Effective {item['effective_from'].isoformat()} through {item['effective_until'].isoformat()}. "
                         +history+review+' Release metadata does not verify code-file integrity.'}
    if current:
        return {**row, 'status':'Overlapping current releases', 'severity':'error',
                'detail':'Diagnosis release metadata overlaps today; inspect the imported effective periods. '+history+review}
    return {**row, 'status':'No release covers today',
            'detail':f'No diagnosis release covers {today.isoformat()}. '+history
                     +'Historical visits can still use their applicable release. '+review}

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
    payments = stripe_key_configured(settings.STRIPE_SECRET_KEY)
    live_payments = settings.QUILLMD_STRIPE_MODE == 'live'
    licensed = cpt_licensed()
    return [
      {'name':'Answer generation','status':'Live API configured' if settings.AI_MODE=='live' else 'Synthetic fixture','severity':'success' if settings.AI_MODE=='live' else 'warning','detail':settings.AI_MODEL if settings.AI_MODE=='live' else 'Exact labelled-note extraction; no provider cost.'},
      {'name':'Transcription','status':('Configured; synthetic audio only' if settings.SYNTHETIC_ONLY else 'Configured') if transcription else 'Unavailable','severity':'success' if transcription else 'error','detail':'Recorded audio is sent only on your explicit request.'},
      {'name':'Payments','status':('Stripe live key configured' if live_payments else 'Stripe sandbox key configured') if payments else 'Not connected','severity':'success' if payments else 'error','detail':'Configuration alone does not verify payments. No subscriptions or automatic top-ups.'},
      icd_configuration(),
      # A current environment licence without the product-use rights recorded in code (core.coding.CPT_PRODUCT_USE_RIGHTS)
      # is locked, not licensed: said so rather than reported as a configured feed.
      {'name':'CPT terminology','status':'Licensed feed configured' if licensed else ('Locked: no product-use rights recorded' if cpt_license_current() else ('License expired' if settings.CPT_LICENSE_ID else 'License required')),'severity':'success' if licensed else ('error' if settings.CPT_LICENSE_ID else 'warning'),'detail':'CPT suggestions remain disabled without a licensed, dated release.'},
      {'name':'Account email','status':('Provider configured' if settings.RESEND_API_KEY else 'Provider key absent') if settings.QUILLMD_EMAIL_MODE=='resend' else 'Private file outbox','severity':('success' if settings.RESEND_API_KEY else 'error') if settings.QUILLMD_EMAIL_MODE=='resend' else 'warning','detail':'Verification, recovery and invitation links are delivered here. Configuration is not delivery: the Services page counts actual outcomes.'},
      {'name':'Patient data','status':'Synthetic only','severity':'warning','detail':'Patient-data agreements and processing controls have not been verified.'} if settings.SYNTHETIC_ONLY else
      {'name':'Patient data','status':'Real patient data','severity':'success','detail':'QUILLMD_DATA_MODE=real: the production settings were checked when this process started. Agreements with processors are recorded outside the application.'},
    ]
