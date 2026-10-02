"""Terminology suggestions from explicit documented codes, with licensed-release gating."""
import re
from collections import namedtuple
from datetime import date
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from .models import Code,CodeSet,CodeSuggestion
from .security import audit

Suggestions=namedtuple('Suggestions','count covered versions omitted unmatched cpt_withheld dotless unlabelled touching',
                       defaults=(0,0,0,0,0,0))

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
#: ⚠️ A CODE WRITTEN WITHOUT ITS DOT IS NEVER READ AS A DIAGNOSIS (refutation F4 of dc33e094). 'R079' would be R07.9, but a
#: letter followed by four digits is also a HCPCS Level II code: reading G0439 (annual wellness visit) as G04.39
#: (encephalopathy) suggested a diagnosis the notes never documented. Such a token is counted and said, never looked up.
#: Its shape is the ICD-10-CM one without the dot: a letter, a digit, a digit OR a letter (the categories C4A, C7A, C7B,
#: D3A, I5A, M1A, O9A, Z3A: refutation C1 of 4cfa4301 found Z3A20, O9A211 and M1A0710 dropped silently by a shape that
#: demanded two digits), then one to four letters or digits; 4 to 7 characters, which no code written with its dot can be.
#: The categories whose SECOND character is a letter have a digit third (FY2026's QA0.*: refutation R3C-3 of 75d11c09).
CATEGORY_SHAPE=r'[A-Z](?:[0-9][0-9A-Z]|[A-Z][0-9])'
DOTLESS=re.compile(r'\b'+CATEGORY_SHAPE+r'[0-9A-Z]{1,4}\b')
#: ⚠️ ...AND IT IS COUNTED ONLY WHEN ITS FIRST THREE CHARACTERS ARE A CATEGORY OF THE RELEASE IN EFFECT. Lab, gene and dose
#: names have the shape too (G6PD, H1N1, C282Y, H63D, q12h): those whose first three characters name no category are not
#: counted (refutation C3). A variant or dose whose first three characters happen to be a real category (V600E: V60;
#: G12C: G12; q12h: Q12) is still counted, and the sentence says such an entry "looks like" a code written without its dot,
#: which it does: telling the two apart needs knowledge of variants no release carries, and an undercount drops a mistyped
#: code silently, which F4's rule forbids. Nothing of this shape is ever suggested.
#: A diagnosis code written WITH its dot that no applicable release holds: counted and said. A category's second or third
#: character is a digit (CATEGORY_SHAPE), so words joined by a dot (SOB.Has, Vit.D, CBC.BMP) are not counted (refutation C2
#: of 4cfa4301), and a mistyped QA0.* code is (refutation R3C-3 of 75d11c09: 'a digit second' dropped it silently).
DOTTED=re.compile(CATEGORY_SHAPE+r'\.[0-9A-Z]{1,4}')
#: Separators of a list of codes after one label: ', ' '; ' ' / ' '&' '+' ' and ' ' or ' and ', and ' (each needs a mark or a
#: word, so a code followed by an unrelated number is not read into the list; '&' and '+': refutation R3C-5).
LIST_SEPARATOR=r'(?:\s*[,;/&+]\s*(?:(?:AND|OR)\s+)?|\s+(?:AND|OR)\s+)'
CPT_SHAPE=r'(?:[0-9]{5}|[0-9]{4}[FTU])\b'
#: The CPT codes the notes NAME as such: after 'CPT', 'CPT®', 'CPT-4', 'CPT code(s)', with ':' '#' '-' or spaces, and every
#: code of a list after one label ('CPT 99213, 99214 and 36415': refutation C4 of 4cfa4301 counted one, and nothing for
#: 'CPT® 99213'). Any unlabelled five-digit number (10000 units, ZIP 90210) is not counted: only a named code is said to have
#: been withheld while CPT content is locked.
CPT_NAMED=re.compile(r'\bCPT(?:\u00ae|\(R\))?(?:[\s-]*4\b)?(?:\s*CODES?)?[\s:#-]*('+CPT_SHAPE+'(?:'+LIST_SEPARATOR+CPT_SHAPE+')*)')
#: ⚠️ A THREE-CHARACTER CODE IS SUGGESTED ONLY WHERE A CODE LABEL NAMES IT (refutation C10 of 4cfa4301). An undotted
#: three-character token was looked up in the case-folded notes, so 'p53 wild-type' (an immunostain) was suggested as P53,
#: hemorrhagic disease of newborn, "explicitly documented", and accepted. Lab, gene and stain names have this shape (p53,
#: B12, A1C, CO2), and telling them apart from a code by their surroundings fails open. So it fails CLOSED: a
#: three-character code is suggested only when the line that FIRST documents it puts it after a code label ('ICD-10: I10',
#: 'ICD-10-CM code I10', 'ICD10 I10', 'ICD: R51 and I10', 'Dx code I10', 'diagnosis codes R51; I10'); otherwise, when a
#: release in effect holds it, it is counted and the doctor is told how to write it, never suggested. A code with its dot
#: (R07.9) is unchanged: the dot already says it is a code.
#: ⚠️ AND A LABEL NAMES THE CODE RIGHT AFTER IT, AND ONLY THE LATER ITEMS OF ITS LIST THAT ARE WRITTEN AS CODES (refutation
#: R3C-1 of 75d11c09): a list that took every code-shaped word after a separator absorbed the stain or gene name next to a
#: labelled code on a synoptic line ('ICD-10 C18.7, p53 wild-type' suggested P53; 'ICD-10: M51.26; L45 herniation'
#: suggested L45, a spine level). A later item is read as a code only when it is written in capitals, as codes are printed,
#: AND ends its item: a separator, a closing mark ('.', ')', ']') or the end of the line. The cost, said to the doctor: in
#: 'ICD-10: R51, I10 hypertension' only R51 is labelled, and I10 is counted and said with how to write it. The residual: an
#: upper-case non-code standing alone as an item of a labelled code list ('ICD-10: C18.7, P53, ...') is read as a code,
#: because the label says it is one.
#: A code inside a labelled list has TOKEN's shape (the label, not the shape, says it is a code; the lookup decides).
CODE_SHAPE=r'[A-Z][0-9A-Z]{2}(?:\.[0-9A-Z]{1,4})?(?![0-9A-Z])'
ICD_LABEL=re.compile(r'\b(?:ICD(?:[\s-]*10(?:[\s-]*CM)?)?|(?:DX|DIAGNOSIS)\s*CODES?)(?:\s*CODES?)?[\s:#-]*')
FIRST_CODE=re.compile(CODE_SHAPE)
LATER_CODE=re.compile(LIST_SEPARATOR+'('+CODE_SHAPE+r')(?=\s*(?:[,;/&+.)\]]|(?:AND|OR)\b|$))')
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

Plan=namedtuple('Plan','notes releases found unmatched cpt_withheld dotless unlabelled touching',defaults=(0,0,0,0,0))

def same_length_upper(line):
    """The line in upper case, character for character (a character whose upper case is longer, as 'ß', is kept), so a
    position in it is the same position in the line."""
    return ''.join(character.upper() if len(character.upper())==1 else character for character in line)

def labelled_codes(line):
    """The codes a code label names on one line, upper-cased: every label (ICD_LABEL), the code right after it
    (FIRST_CODE), then each later item of its list that is written in capitals and ends its item (LATER_CODE). Each label is
    found on its own, so a list never swallows the next label ('ICD' has a code's shape); a list stops at its first item
    that is not written as a code, so the lists overlap by at most one token and the scan stays linear in the line."""
    upper=same_length_upper(line);found=set()
    for label in ICD_LABEL.finditer(upper):
        first=FIRST_CODE.match(upper,label.end())
        if not first:continue
        found.add(first.group());position=first.end()
        while (later:=LATER_CODE.match(upper,position)) and line[later.start(1):later.end(1)]==later.group(1):
            found.add(later.group(1));position=later.end(1)
    return found

def named_cpt(upper):
    """The distinct CPT codes the upper-cased notes name as CPT codes (CPT_NAMED), every code of a labelled list."""
    return {code for match in CPT_NAMED.finditer(upper) for code in re.findall(CPT_SHAPE,match.group(1))}

def release_categories(releases,wanted):
    """Which of `wanted` (three-character prefixes) is the category of a code in an applicable ICD-10-CM release. Read to
    decide whether a dotless token is counted; never to suggest one."""
    icd=[release.pk for release in releases if release.system=='ICD-10-CM']
    if not icd or not wanted:return set()
    from django.db.models.functions import Substr
    return set(Code.objects.filter(release_id__in=icd).annotate(category=Substr('code',1,3)).filter(
        category__in=wanted).values_list('category',flat=True).distinct())

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
    # No diagnosis inference: recommend only codes explicitly documented in notes, exactly as written.
    tokens=set(TOKEN.findall(upper))
    locked=not cpt_licensed()
    codes=[code for code in Code.objects.filter(code__in=tokens,release__in=releases).select_related('release')
           if code.release.system=='ICD-10-CM' or not locked]
    evidence=evidence_lines(encounter.notes,{code.code for code in codes})
    # A three-character diagnosis code counts only where its evidence line (the first line documenting it) labels it.
    labels={}                           # evidence line -> the codes labelled on it, read once per distinct line
    def labelled(code):
        line=evidence[code.code][1]
        if line not in labels:labels[line]=labelled_codes(line)
        return code.code in labels[line]
    unlabelled={code.code for code in codes if code.code in evidence and len(code.code)==3
                and code.release.system=='ICD-10-CM' and not labelled(code)}
    documented=sorted((code for code in codes if code.code in evidence and code.code not in unlabelled),
                      key=lambda code:evidence[code.code][0])
    # Said, never looked up and never dropped silently: a code written with its dot that no applicable release holds, a
    # code-shaped token written without a dot, an unlabelled three-character code, and (while CPT is locked) a CPT code the
    # notes name as one.
    known={code.code for code in codes}
    unmatched=len({token for token in tokens if DOTTED.fullmatch(token)}-known)
    shaped=set(DOTLESS.findall(upper))
    categories=release_categories(releases,{token[:3] for token in shaped})
    dotless=sum(token[:3] in categories for token in shaped)
    cpt_withheld=len(named_cpt(upper)) if locked else 0
    # ⚠️ A code the release holds that the evidence reading refuses ('1.R07.9', 'R07.9.Plan': it touches the characters
    # around it) reached no counter: found, never suggested, never said (refutation R3C-2 of 75d11c09). Counted and said.
    touching=len(known-set(evidence))
    return Plan(encounter.notes,releases,[(code,evidence[code.code][1]) for code in documented],unmatched,cpt_withheld,dotless,
                len(unlabelled),touching)

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
          cpt_withheld=planned.cpt_withheld,written_without_dot=planned.dotless,three_character_unlabelled=planned.unlabelled,
          written_touching=planned.touching)
    return Suggestions(len(new),covered,versions,omitted,planned.unmatched,planned.cpt_withheld,planned.dotless,
                       planned.unlabelled,planned.touching)
