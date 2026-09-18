"""Terminology suggestions from explicit documented codes, with licensed-release gating."""
import re
from collections import namedtuple
from datetime import date
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from .models import Code,CodeSet,CodeSuggestion
from .security import audit

Suggestions=namedtuple('Suggestions','count covered versions')

def cpt_licensed():
    """A CPT release is usable only while the licence itself is current.

    Deliberately judged against TODAY, not against the encounter's date of service: the
    licence governs whether this product may display the content now, which is a different
    question from which fiscal year's codes apply to the visit.
    """
    if not settings.CPT_LICENSE_ID or not settings.CPT_LICENSE_EXPIRY:return False
    try:expiry=date.fromisoformat(settings.CPT_LICENSE_EXPIRY)
    except ValueError:return False
    return expiry>=timezone.localdate()

def applicable_releases(encounter):
    """The releases in effect on the encounter's date of service or discharge.

    This is the ONE place the applicable version is decided. Suggestion and
    acceptance both read it, so a fiscal-year boundary cannot mean one thing on
    the way in and another on the way out.
    """
    covering=CodeSet.objects.filter(effective_from__lte=encounter.service_date,
                                    effective_until__gte=encounter.service_date)
    if cpt_licensed():
        return covering.filter(Q(system='ICD-10-CM')|Q(system='CPT',license_reference=settings.CPT_LICENSE_ID))
    return covering.filter(system='ICD-10-CM')

def suggest(encounter,user):
    releases=list(applicable_releases(encounter))
    # No diagnosis inference: recommend only codes explicitly documented in notes.
    tokens=set(re.findall(r'\b(?:[A-Z][0-9A-Z]{2}(?:\.[0-9A-Z]{1,4})?|[0-9]{5}|[0-9]{4}[FTU])\b',encounter.notes.upper()))
    count=0
    for code in Code.objects.filter(code__in=tokens,release__in=releases).select_related('release'):
        # The trailing dot of a sentence is not part of the code, but a dot followed by another
        # code character is: refusing every following dot dropped 'documented as M25.532.' entirely.
        evidence=next((line for line in encounter.notes.splitlines() if re.search(r'(?<![\w.])'+re.escape(code.code)+r'(?!\w)(?!\.[0-9A-Za-z])',line,re.I)),None)
        if not evidence:continue
        _,created=CodeSuggestion.objects.get_or_create(encounter=encounter,terminology=code,defaults={'evidence':evidence,'explanation':f'Code explicitly documented in source notes; validated against {code.release.system} {code.release.version}, the release in effect for the {encounter.service_date.isoformat()} date of service. Clinician must confirm context and billing suitability.'})
        count+=int(created)
    versions=sorted(f'{r.system} {r.version}' for r in releases)
    # icd_covered answers ONE question: was a diagnosis release in force on that date. It is not
    # 'did anything happen' — a licensed CPT release can answer while no ICD release does.
    covered=any(r.system=='ICD-10-CM' for r in releases)
    audit(user,'coding.suggest',encounter.pk,department=encounter.department,count=count,
          service_date=encounter.service_date.isoformat(),releases=versions,icd_covered=covered)
    return Suggestions(count,covered,versions)
