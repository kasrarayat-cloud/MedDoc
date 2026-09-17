"""Terminology suggestions from explicit documented codes, with licensed-release gating."""
import re
from datetime import date
from django.conf import settings
from django.utils import timezone
from .models import Code,CodeSuggestion
from .security import audit

def suggest(encounter,user):
    today=timezone.localdate()
    releases={'ICD-10-CM'}
    if settings.CPT_LICENSE_ID and settings.CPT_LICENSE_EXPIRY and date.fromisoformat(settings.CPT_LICENSE_EXPIRY)>=today:releases.add('CPT')
    # No diagnosis inference: recommend only codes explicitly documented in notes.
    tokens=set(re.findall(r'\b(?:[A-Z][0-9A-Z]{2}(?:\.[0-9A-Z]{1,4})?|[0-9]{5}|[0-9]{4}[FTU])\b',encounter.notes.upper()))
    count=0
    for code in Code.objects.filter(code__in=tokens,release__system__in=releases,release__effective_from__lte=today,release__effective_until__gte=today).select_related('release'):
        if code.release.system=='CPT' and code.release.license_reference!=settings.CPT_LICENSE_ID:continue
        evidence=next((line for line in encounter.notes.splitlines() if re.search(r'(?<![\w.])'+re.escape(code.code)+r'(?![\w.])',line,re.I)),None)
        if not evidence:continue
        _,created=CodeSuggestion.objects.get_or_create(encounter=encounter,terminology=code,defaults={'evidence':evidence,'explanation':f'Code explicitly documented in source notes; validated against {code.release.system} {code.release.version}. Clinician must confirm context and billing suitability.'})
        count+=int(created)
    audit(user,'coding.suggest',encounter.pk,department=encounter.department,count=count)
    return count
