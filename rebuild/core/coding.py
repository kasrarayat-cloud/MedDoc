"""Terminology suggestions from explicit documented codes, with licensed-release gating."""
import re
from collections import namedtuple
from datetime import date
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from .models import Code,CodeSet,CodeSuggestion
from .security import audit

Suggestions=namedtuple('Suggestions','count covered versions omitted unmatched cpt_withheld',defaults=(0,0,0))

#: ⚠️ THE CPT LOCK IS CODE, NOT CONFIGURATION. The right to use CPT content in THIS product (the licence holder, the
#: agreement and its scope) is a reviewed release decision, recorded here by a code change. While it is None, CPT content
#: and every CPT function stay disabled in every data, AI and payment mode, whatever CPT_LICENSE_ID/CPT_LICENSE_EXPIRY say:
#: no CPT code is imported, suggested, displayed, accepted or exported. The environment licence stays a second, dated gate.
CPT_PRODUCT_USE_RIGHTS=None

def cpt_license_current():
    """The environment's CPT licence is configured and current (the second gate; never sufficient on its own).

    Deliberately judged against TODAY, not against the encounter's date of service: the
    licence governs whether this product may display the content now, which is a different
    question from which fiscal year's codes apply to the visit.
    """
    if not settings.CPT_LICENSE_ID or not settings.CPT_LICENSE_EXPIRY:return False
    try:expiry=date.fromisoformat(settings.CPT_LICENSE_EXPIRY)
    except ValueError:return False
    return expiry>=timezone.localdate()

def cpt_licensed():
    """A CPT release is usable only with recorded product-use rights AND a current environment licence."""
    return CPT_PRODUCT_USE_RIGHTS is not None and cpt_license_current()

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

#: A code as the notes document it: an ICD-10-CM code (a letter, two characters, and up to four after a dot) or a CPT code
#: (five digits, or four and F, T or U), read from the upper-cased notes.
TOKEN=re.compile(r'\b(?:[A-Z][0-9A-Z]{2}(?:\.[0-9A-Z]{1,4})?|[0-9]{5}|[0-9]{4}[FTU])\b')
#: An ICD-10-CM code written without its dot ('R079' for R07.9, 'S72001A' for S72.001A): a letter, a digit, then two to
#: five more characters. Read as the dotted code it names; never suggested unless that code is in the release in effect.
DOTLESS=re.compile(r'\b[A-Z][0-9][0-9A-Z]{2,5}\b')
ICD_SHAPE=re.compile(r'[A-Z][0-9A-Z]{2}(?:\.[0-9A-Z]{1,4})?')
RUN=re.compile(r'[\w.]+')
SHORTEST_CODE,LONGEST_CODE=3,8      # 'R00' .. 'A00.0000'; every TOKEN match is 3 to 8 characters
ASCII_UPPER='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
ASCII_ALNUM='0123456789'+ASCII_UPPER
#: ⚠️ A DOCUMENT HOLDS AT MOST THIS MANY CODE SUGGESTIONS. Each carries its whole evidence line, written under the encounter's
#: lock and read on every page view: 12,000 codes on one 48,000-character line wrote 576 MB and held the lock 29 s even
#: after the scan became linear (refutation round 4, R4-2). That is far more codes than one claim carries; the codes beyond
#: it, the last the notes document, are counted, audited and said, never dropped silently. Bounded so, one pass writes at
#: most 100 evidence lines of at most 50,000 characters.
MAX_SUGGESTIONS=100

Plan=namedtuple('Plan','notes releases found unmatched cpt_withheld',defaults=(0,0))

def evidence_lines(notes,wanted):
    """For each code in `wanted`, the first line of `notes` on which it stands whole, as (the order the codes were first
    documented in, that line), in ONE pass over the notes.

    It answers exactly what `re.search(r'(?<![\\w.])'+re.escape(code)+r'(?!\\w)(?!\\.[0-9A-Za-z])',line,re.I)` answered
    line by line for each code — a code is preceded by neither a word character nor a dot, and followed by neither a word
    character nor a dot and a letter or digit, so 'documented as M25.532.' holds M25.532 and 'M25.5320' does not — but
    that search rescanned the notes once per code: 12,000 codes in 48,000 characters held the encounter's lock for 70.6 s
    (refutation round 4, R4-2). Here each maximal run of word characters and dots is visited once: a whole code can only
    be a 3-8 character prefix of one (nothing may precede it), so at most six prefixes are compared per run — at the
    50,000-character notes limit, at most 300,000 comparisons of at most 8 characters, whatever the number of codes.
    `re.I` matches four non-ASCII letters to ASCII ones (KELVIN SIGN to K, LONG S to S, DOTLESS I and CAPITAL I WITH DOT
    to I, on Python 3.12); each character is folded by asking `re` itself, once per distinct character, so the two
    readings cannot drift."""
    folds={}
    def fold(character):
        if character not in folds:
            folds[character]=(character.upper() if character.isascii() else
                              next((letter for letter in ASCII_UPPER if re.fullmatch(letter,character,re.I)),character))
        return folds[character]
    found={}                            # code -> (the order it was first documented in, its line)
    for line in notes.splitlines():
        for run in RUN.finditer(line):
            text=run.group()
            for length in range(SHORTEST_CODE,min(LONGEST_CODE,len(text))+1):
                if length<len(text) and (text[length]!='.' or (length+1<len(text) and fold(text[length+1]) in ASCII_ALNUM)):
                    continue            # a word character follows, or a dot and a letter or digit: not a whole code
                code=''.join(fold(character) for character in text[:length])
                if code in wanted and code not in found:found[code]=(len(found),line)
        if len(found)==len(wanted):break
    return found

def plan(encounter):
    """Which suggestions the notes support, read without writing: `suggest` records them under the encounter's lock."""
    releases=list(applicable_releases(encounter))
    upper=encounter.notes.upper()
    # No diagnosis inference: recommend only codes explicitly documented in notes.
    tokens=set(TOKEN.findall(upper))
    # A dotless ICD-10-CM code is read as the dotted code it names, never dropped silently (inventory 7A, coding).
    dotless={token[:3]+'.'+token[3:]:token for token in DOTLESS.findall(upper)}
    locked=not cpt_licensed()
    codes=[code for code in Code.objects.filter(code__in=tokens|set(dotless),release__in=releases).select_related('release')
           if code.release.system=='ICD-10-CM' or not locked]
    written={code.code:(code.code if code.code in tokens else dotless[code.code]) for code in codes}
    evidence=evidence_lines(encounter.notes,set(written.values()))
    documented=sorted((code for code in codes if written[code.code] in evidence),key=lambda code:evidence[written[code.code]][0])
    # What the notes write as a code but no applicable release holds, counted and said rather than dropped silently.
    known={code.code for code in codes}
    shaped={token for token in tokens if ICD_SHAPE.fullmatch(token) and any(c.isdigit() for c in token)}|set(dotless)
    unmatched=len({token for token in shaped if token not in known and token not in dotless.values()}
                  |{dotted for dotted in dotless if dotted not in known and dotless[dotted] not in known})
    cpt_withheld=len({token for token in tokens if token[0].isdigit()}) if locked else 0
    return Plan(encounter.notes,releases,[(code,evidence[written[code.code]][1]) for code in documented],unmatched,cpt_withheld)

def suggest(encounter,user,planned=None):
    """Records a plan's new suggestions and audits them. The caller holds the encounter's row lock and has checked that the
    notes are the ones planned from; every suggestion is written by this function, so the ones already recorded are
    exactly those read here, and the rest are inserted in batches rather than one query pair per code."""
    planned=planned or plan(encounter)
    recorded=set(CodeSuggestion.objects.filter(encounter=encounter).values_list('terminology_id',flat=True))
    candidates=[(code,evidence) for code,evidence in planned.found if code.pk not in recorded]
    # Each suggestion carries its release's identity (the imported file's sha256), checked by the database (0034).
    new=[CodeSuggestion(encounter=encounter,terminology=code,evidence=evidence,release_sha256=code.release.sha256,explanation=f'Code explicitly documented in source notes; validated against {code.release.system} {code.release.version}, the release in effect for the {encounter.service_date.isoformat()} date of service. Clinician must confirm context and billing suitability.')
         for code,evidence in candidates[:max(0,MAX_SUGGESTIONS-len(recorded))]]
    CodeSuggestion.objects.bulk_create(new,batch_size=200)
    omitted=len(candidates)-len(new)
    versions=sorted(f'{r.system} {r.version}' for r in planned.releases)
    # icd_covered answers ONE question: was a diagnosis release in force on that date. It is not
    # 'did anything happen' — a licensed CPT release can answer while no ICD release does.
    covered=any(r.system=='ICD-10-CM' for r in planned.releases)
    audit(user,'coding.suggest',encounter.pk,department=encounter.department,count=len(new),
          service_date=encounter.service_date.isoformat(),releases=versions,icd_covered=covered,not_suggested_over_limit=omitted,
          release_sha256=sorted(r.sha256 for r in planned.releases),not_in_release=planned.unmatched,
          cpt_withheld=planned.cpt_withheld)
    return Suggestions(len(new),covered,versions,omitted,planned.unmatched,planned.cpt_withheld)
