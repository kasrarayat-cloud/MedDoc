"""Bounded source frames for the v5 referral-attribution contract.

Unknown wording never establishes patient ownership. These complete frames
supplement the semantic checker and preserve all original source evidence.
Older contracts do not import or invoke this recognizer.
"""
from dataclasses import dataclass
import re

def alternatives(*items):
    # Raw-source guards and normalized frame parsing must accept the same
    # whitespace. Regex matching still reports offsets in the untouched source.
    return '(?:'+'|'.join(re.escape(v).replace(r'\ ', r'\s+')
                        for v in sorted(items,key=len,reverse=True))+')'
def listing(item):
    item='(?:'+item+')'
    return item+r'(?:,\s*'+item+r')*(?:,?\s+and\s+'+item+r')?'
NUMBER=r'(?:[0-9]{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|twenty-five|thirty|thirty-five|forty|sixty)'
DURATION=NUMBER+r'\s+(?:days?|weeks?|months?|years?)'
SPECIALTY=alternatives('gastroenterology','gastrointestinal','GI','cardiology','neurology','primary care')
DIAGNOSIS=alternatives('seasonal allergic rhinitis','allergic rhinitis','migraine','asthma','hypertension','irritable bowel syndrome','colon polyps','functional bloating','gastroesophageal reflux disease','type 2 diabetes','appendicitis')
PROCEDURE=alternatives('appendectomy','cholecystectomy','colonoscopy','endoscopy')
DRUG=alternatives('amoxicillin','penicillin','ibuprofen','acetaminophen','aspirin','omeprazole')
REACTION=alternatives('hives','rash','anaphylaxis','nausea','vomiting')
SYMPTOM=alternatives('heartburn','painful swallowing','difficulty swallowing','nausea','vomiting','abdominal pain','diarrhea','constipation','vomiting blood','black stools','blood in the stool','rectal bleeding','unintentional weight loss','any change in appetite','bloating','fever','cough','wheezing','chest pain','normal bowel movements')
SYMPTOMS=listing(SYMPTOM)
# These categories cover only this recognizer's finite literal symptom slots.
# They do not infer diagnoses or classify unfamiliar clinical wording.
SYMPTOM_DOMAINS={
    'gastrointestinal': frozenset(('heartburn','painful swallowing','difficulty swallowing','nausea',
        'vomiting','abdominal pain','diarrhea','constipation','vomiting blood','black stools',
        'blood in the stool','rectal bleeding','unintentional weight loss','any change in appetite','bloating')),
    'respiratory': frozenset(('cough','wheezing')),
    'cardiac': frozenset(('chest pain',)),
    'constitutional': frozenset(('fever','unintentional weight loss','any change in appetite')),
    'systemic': frozenset(('fever','unintentional weight loss','any change in appetite')),
}
PATIENT_SYMPTOM_REPORT=(r'.+?\s+reports\s+(?:(?:intermittent|persistent|mild|moderate|severe)\s+)?'
    r'(?P<symptom>'+SYMPTOM+r')(?:\s+for\s+'+DURATION+r')?(?:\s+and\s+denies\s+'+SYMPTOMS+r')?\.?')
MEDICATION=alternatives('a daily multivitamin','a multivitamin','omeprazole','acetaminophen','ibuprofen')
OCCUPATION=alternatives('architect','teacher','engineer','nurse','physician','accountant','student','retired')
RELATION=alternatives('mother','father','brother','sister','son','daughter')
SOCIAL=listing(alternatives('has never used tobacco','has never smoked','never used tobacco','never smoked','does not drink alcohol','does not use recreational drugs','is married','is single','is divorced')+r'|works as an?\s+'+OCCUPATION)
# Clinical slots contain complete bounded propositions, never arbitrary names or clauses.
SYMPTOM_STATE=r'(?:no|without)\s+(?:(?:current|active|ongoing|new)\s+)?(?:(?P<symptom_domain>gastrointestinal|respiratory|cardiac|neurologic|neurological|urinary|constitutional|systemic|musculoskeletal)\s+)?(?:symptoms?|complaints?)'
FAMILY_HISTORY=r'(?:(?:colon|colorectal)\s+(?:polyps|cancer)|irritable\s+bowel\s+syndrome|inflammatory\s+bowel\s+disease)'
MIXED_ASSESSMENT=SYMPTOM_STATE+r'\s+and\s+a\s+family\s+history\s+of\s+'+FAMILY_HISTORY
REPORTED_ASSESSMENT=r"(?:my|the\s+(?:clinician|physician|doctor)['’]s)\s+(?:documented\s+)?(?:impression|assessment)\s+(?:is|was)\s+"
IMPRESSION=r'(?:'+MIXED_ASSESSMENT+r'|'+DIAGNOSIS+r')'
RECORDS=r'(?:the\s+)?(?:(?:prior|previous|outside)\s+)?(?:'+SPECIALTY+r'\s+)?records'
PURPOSE=r'to\s+(?:review|obtain)\s+'+RECORDS
MODALITY=alternatives('in-person','telephone','video','telehealth','video telehealth')
VISIT=MODALITY+r'\s+(?:'+SPECIALTY+r'\s+)?(?:visit|follow-up|consultation)'
PLAN=r'(?:to obtain\s+'+RECORDS+r'\s+and arrange follow-up after reviewing them|a food and symptom diary and follow-up in\s+'+DURATION+r'|follow-up in\s+'+DURATION+r')'
WORK=alternatives('preparation and chart review','chart review','obtaining and reviewing separately obtained history','the examination and evaluation','the video consultation','independent interpretation and communication of prior test results without separate reporting','documentation in the EHR on the same day','documentation')
HEAD=r'(?:the\s+)?head\s+(?:was|is)\s+normocephalic and atraumatic'
PUPILS=r'pupils\s+(?:were|are)\s+equal'
ORAL=r'there\s+(?:was|is)\s+no scleral icterus and the oropharynx\s+(?:was|is)\s+clear'
NECK=r'(?:the\s+)?neck\s+(?:was|is)\s+supple'
CHEST=r'lungs\s+(?:were|are)\s+clear to auscultation bilaterally,?\s+and the heart\s+(?:had|has)\s+a regular rate and rhythm'
ABDOMEN=r'bowel sounds\s+(?:were|are)\s+present;\s+the abdomen\s+(?:was|is)\s+soft,\s+non-tender and non-distended,\s+without rebound or guarding'
LIMBS=r'extremities\s+(?:were|are)\s+warm and well perfused,\s+without edema'
EXAM_SIMPLE=r'(?:the\s+)?(?:abdomen|chest|neck|oropharynx|lungs|heart|breathing)\s+(?:was|were|is|are)\s+'+alternatives('clear','normal','soft','supple','non-tender','non-distended','non tender','non distended')
EXAM=r'(?:'+r'|'.join([HEAD+r';\s*'+PUPILS+r',\s*'+ORAL,ORAL,NECK,CHEST,ABDOMEN,LIMBS,EXAM_SIMPLE,r'bowel sounds\s+(?:were|are)\s+(?:normal|present)',r'the rectal examination\s+(?:was|is)\s+deferred',r'neurologic observation shows clear speech and normal orientation'])+r')'

@dataclass(frozen=True)
class Context:
    full_name: str
    aliases: tuple=()
    referrers: tuple=()
    def __post_init__(self):
        tokens=self.full_name.split()
        if not tokens: raise ValueError('A bound full target name is required.')
        # This prototype supports an explicitly declared given-first name format.
        # Synthetic is a fixture marker, not the given name. No nicknames inferred.
        given=tokens[1] if tokens[0].casefold()=='synthetic' and len(tokens)>2 else tokens[0]
        if len(self.aliases)>1 or any(alias!=given for alias in self.aliases):
            raise ValueError('Only the exact given token of the bound full identity is eligible.')
        if any(alias.casefold() in ref.casefold().split() for alias in self.aliases for ref in self.referrers):
            raise ValueError('A target short reference collides with the explicit referrer identity.')

@dataclass(frozen=True)
class Frame:
    kind: str
    ownership: str
    explicit_reference: str|None=None
    def to_dict(self):
        return {'kind':self.kind,'ownership':self.ownership,'explicit_reference':self.explicit_reference}

def parse_unit(text, context=None):
    """Return a complete recognized frame or None; never partial-match a unit."""
    # Whitespace normalization changes parsing only, never source or output evidence.
    value=' '.join(text.split())
    def matches(pattern):return re.fullmatch(pattern+r'\.?',value,re.I)
    full=re.escape(context.full_name) if context is not None else r'(?!)'
    target=alternatives(context.full_name,*context.aliases) if context is not None else r'(?!)'
    references=r'(?P<target>'+target+r'|the patient)'
    if context is not None and context.referrers:
        referral=(full+r'\s+(?:is\s+'+NUMBER+r'\s+years? old and\s+)?(?:was|is) referred by\s+(?:(?:Dr\.?|Doctor)\s+)?'
                  +alternatives(*context.referrers)+r'(?:\s+for\s+an?\s+'+VISIT+r'\s+'+PURPOSE+r')?')
        if matches(referral):return Frame('patient_referral','target',context.full_name)
    # All patient-predicate alternatives consume the complete predicate, including lists.
    predicate=(r'(?:(?:currently\s+)?feels well|reports\s+(?:(?:intermittent|persistent|mild|moderate|severe)\s+)?'+SYMPTOM+
               r'(?:\s+for\s+'+DURATION+r')?(?:\s+and denies\s+'+SYMPTOMS+r')?|denies\s+'+SYMPTOMS+
               r'|takes\s+'+MEDICATION+r'|'+SOCIAL+r'|is an?\s+'+OCCUPATION+
               r'|is cooperative|was pleasant and interactive|gave verbal consent for this\s+'+MODALITY+r'\s+consultation'+
               r'|(?:is|was)\s+(?:alert, oriented and\s+)?in no acute distress|appears alert and comfortable'+
               r'|was oriented to person, place, time and situation, moved all extremities spontaneously and had a nonfocal neurologic exam)')
    match=matches(r'(?:(?:On examination|On video),\s+)?'+references+r'\s+'+predicate)
    if match:return Frame('explicit_patient_statement','target',match['target'])
    patterns=[
      ('past_medical_history',r'Past medical history\s+(?:is|includes)\s+'+DIAGNOSIS),
      ('past_surgical_history',r'Past surgical history\s+(?:is|includes)\s+'+PROCEDURE+r'(?:\s+in\s+[0-9]{4})?'),
      ('allergy_record',DRUG+r'\s+causes\s+'+REACTION),
      ('encounter_reconciliation',r'The clinician reviewed and reconciled the medications in the EHR during this visit'),
      ('family_history_record',r'(?:'+target+r'|the patient)[\x27\u2019]s\s+'+RELATION+r'\s+(?:had\s+'+DIAGNOSIS+r'\s+diagnosed at age\s+'+NUMBER+r'|has\s+'+DIAGNOSIS+r')'),
      ('review_of_systems',r'A\s+'+NUMBER+r'-point review of systems was performed, with no additional concerns'),
      ('review_of_systems',r'No\s+'+NUMBER+r'-point review of systems was performed'),
      ('exam_finding',EXAM),
      ('encounter_modality',r'This was an?\s+(?:'+VISIT+r'|in-person\s+(?:'+SPECIALTY+r'\s+)?(?:visit|follow-up|consultation);\s+no telephone or telehealth encounter occurred)'),
      ('reported_impression',REPORTED_ASSESSMENT+IMPRESSION),
      ('documented_plan',r'The (?:documented\s+)?plan\s+(?:was|is)\s+'+PLAN),
      ('encounter_medication_action',r'No medication changes were made'),
      ('direct_encounter_time',NUMBER+r'\s+minutes were spent directly with the patient'),
      ('total_encounter_time',r'(?:Total time on today[\x27\u2019]s encounter|The total encounter time) was\s+'+NUMBER+r'\s+minutes(?:,\s+including\s+'+listing(WORK)+r')?'),
    ]
    for kind,pattern in patterns:
        if matches(pattern):return Frame(kind,'preserve_target')
    return None

def observation_qualifier_inventory(units):
    """Bind literal modality to its source assertion without granting ownership.

    Only direct observation predicates belong to this contract: a video history
    of medication use, symptoms or occupation does not acquire an examination
    qualifier. Recognizing a complete predicate and name shape does not establish
    the subject's identity. Admission must bind that subject independently.
    Unknown continuations remain held. All positions refer to untouched source.
    """
    rows = []
    # These complete predicates mirror only the direct observations in the old
    # parser, without changing its historical grammar or constructing a Context
    # from an arbitrary captured clause. The wider lead catches unfamiliar or
    # compound observations conservatively; it never authorizes their content.
    complete = (r'(?:is\s+cooperative|was\s+pleasant\s+and\s+interactive'
                r'|(?:is|was)\s+(?:alert,\s+oriented\s+and\s+)?in\s+no\s+acute\s+distress'
                r'|appears\s+alert\s+and\s+comfortable'
                r'|was\s+oriented\s+to\s+person,\s+place,\s+time\s+and\s+situation,\s+'
                r'moved\s+all\s+extremities\s+spontaneously\s+and\s+had\s+a\s+nonfocal\s+neurologic\s+exam)')
    lead = (r'(?:(?:appears|appeared|looks|looked|seems|seemed)\b'
            r'|(?:is|are|was|were|remains|remained)\s+'
            r'(?:alert|oriented|cooperative|pleasant|interactive|in\s+no\s+acute\s+distress)\b)')
    qualifier = r'(?:(?:On|By|Via|Over)\s+'+MODALITY+r'|In\s+person)'
    pattern = (r'\s*(?P<qualifier>'+qualifier+r')(?!\w)\s*(?:[:,]\s*)?'
               r'(?P<subject>.+?)\s+(?P<observation>'+lead+r'.*?)\s*\.?\s*')
    for unit in units:
        match = re.fullmatch(pattern, unit['quote'], re.I | re.S)
        if match is None:
            continue
        subject = ' '.join(match['subject'].split())
        # This is syntax only. In particular, neither a relative noun phrase
        # nor a clause containing another predicate can masquerade as a name.
        tokens = subject.split()
        name_shape = (1 <= len(tokens) <= 3 and all(
            token[0].isupper() and re.fullmatch(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", token)
            for token in tokens))
        complete_subject = subject.casefold() == 'the patient' or name_shape
        def span(group):
            start, end = match.span(group)
            return {'start': unit['start']+start, 'end': unit['start']+end,
                    'quote': unit['quote'][start:end]}
        rows.append({'source_unit_id': unit['id'],
                     'source': {key: unit[key] for key in ('start', 'end', 'quote')},
                     'subject': span('subject'), 'observation': span('observation'),
                     'qualifiers': [{'kind': 'observation_modality', **span('qualifier')}],
                     'recognized_complete_assertion': complete_subject
                         and re.fullmatch(complete, match['observation'], re.I) is not None})
    return rows


def consent_qualifier_inventory(units):
    """Locate consent heads and their literal purposes, without granting ownership.

    The complete positive frame is the existing verbal-consent assertion. A
    consent noun in unfamiliar, conditional or compound syntax still creates a
    review obligation; a failed full match must not erase it. Purpose-only
    values (for example a separately selected modality) do not overlap a head.
    One row per unit bounds repeated-head evidence without duplicating a long
    source sentence for each occurrence. All offsets address untouched source.
    """
    from .generation import ABBREVIATION
    # Canonical sentence splitting can cut a numbered parenthesis at "1.".
    # Track literal open groups across those exact units; an unfinished group
    # cannot terminate a type attachment. This never admits unknown syntax.
    open_groups = []
    unfinished_groups = set()
    closing = {')':'(', ']':'[', '}':'{'}
    for unit in units:
        for char in unit['quote']:
            if char in '([{':
                open_groups.append(char)
            elif char in closing and open_groups and open_groups[-1] == closing[char]:
                open_groups.pop()
        if open_groups:
            unfinished_groups.add(unit['id'])
    def terminal(unit):
        quote = unit['quote'].rstrip()
        # Local continuation-only abbreviations and list markers supplement
        # canonical segmentation; the shared historical splitter is unchanged.
        unfinished_label = re.search(r'\b(?:no|viz)\.$|(?:^|[:;])\s*[0-9]+\.$', quote, re.I)
        return bool(re.search(r'[.!?]$', quote)
            and not ABBREVIATION.search(quote) and not unfinished_label
            and unit['id'] not in unfinished_groups)
    types = r'\b(?:verbal|written|oral|informed|explicit)\b'
    heads = (r'\b(?:(?:verbal|written|oral|informed|explicit)[\W_]+)*consent\b')
    complete = (r'\s*(?P<subject>.+?)\s+gave\s+'
                r'(?P<consent>verbal\s+consent)\s+'
                r'(?P<purpose>for\s+this\s+'+MODALITY+r'\s+consultation)\s*\.?\s*')
    rows = []
    for index, unit in enumerate(units):
        found = list(re.finditer(heads, unit['quote'], re.I))
        if not found:
            continue
        def span(start, end):
            return {'start': unit['start']+start, 'end': unit['start']+end,
                    'quote': unit['quote'][start:end]}
        match = re.fullmatch(complete, unit['quote'], re.I | re.S)
        subject = consent = purpose = None
        recognized = False
        if match is not None:
            subject, consent, purpose = (span(*match.span(group))
                for group in ('subject', 'consent', 'purpose'))
            words = ' '.join(subject['quote'].split()).split()
            name_shape = (1 <= len(words) <= 3 and all(
                re.fullmatch(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", word)
                for word in words))
            recognized = (' '.join(words).casefold() == 'the patient' or name_shape)
            # A literal Consent token may also occur in the source subject's
            # name. Syntax separates that position; admission still has to
            # establish the subject independently before ignoring name tokens.
            predicate_heads = [span(*head.span()) for head in found
                if not subject['start'] <= unit['start']+head.start() < unit['start']+head.end() <= subject['end']]
            recognized = recognized and predicate_heads == [consent]
        trigger_heads = [span(*head.span()) for head in found]
        # Unknown coordination or a postposed type must not detach the type
        # from consent: both "verbal and informed consent" and "consent
        # (verbal)" still govern the selected "verbal".
        # These extra spans are obligations only, never positive admissions.
        # Canonical units already account for abbreviation periods. Splitting
        # them a second time at any period would detach "i.e. verbal".
        for token in re.finditer(types, unit['quote'], re.I):
            exact = span(*token.span())
            if not any(head['start'] <= exact['start'] and exact['end'] <= head['end'] for head in trigger_heads):
                trigger_heads.append(exact)
        # Canonical source units split at newlines. Retain type tokens from an
        # unfinished preceding unit as unresolved continuation evidence, rather
        # than synthesizing a joined source span or dropping the obligation.
        continuation = []
        continuation_types = []
        for previous in reversed(units[:index]):
            if (terminal(previous)
                    or re.search(heads, previous['quote'], re.I)
                    or parse_unit(previous['quote']) is not None):
                break
            continuation.append({'source_unit_id': previous['id'],
                **{key: previous[key] for key in ('start', 'end', 'quote')}})
            for token in re.finditer(types, previous['quote'], re.I):
                continuation_types.append({'start': previous['start']+token.start(),
                    'end': previous['start']+token.end(), 'quote': token.group()})
        # Postposed types can continue after a canonical newline too. Stop at
        # a sentence boundary, another consent head, or a complete independent
        # frame; preserve the original positions instead of joining source.
        if not continuation_types:
            continuation = []
        following_sources = []
        following_types = []
        prior = unit
        for following in units[index+1:]:
            if (terminal(prior)
                    or re.search(heads, following['quote'], re.I)
                    or parse_unit(following['quote']) is not None):
                break
            following_sources.append({'source_unit_id': following['id'],
                **{key: following[key] for key in ('start', 'end', 'quote')}})
            for token in re.finditer(types, following['quote'], re.I):
                following_types.append({'start': following['start']+token.start(),
                    'end': following['start']+token.end(), 'quote': token.group()})
            prior = following
        trigger_heads.extend(continuation_types+following_types)
        # Missing punctuation alone does not make the next complete assertion
        # incomplete. These positions only attach an actually retained type;
        # source ownership still decides whether the complete unit is usable.
        if not following_types:
            following_sources = []
        rows.append({'source_unit_id': unit['id'],
            'source': {key: unit[key] for key in ('start', 'end', 'quote')},
            'consent_heads': sorted(trigger_heads, key=lambda head: (head['start'],head['end'])),
            'continuation_sources': list(reversed(continuation))+following_sources,
            'subject': subject, 'consent': consent, 'purpose': purpose,
            'recognized_complete_assertion': recognized})
    return rows


def evaluate(units,context):
    """Track uninterrupted target scope from the bound leading referral.

    Unknown source closes scope for the remainder of the note. Even a later
    full name cannot resolve an unparsed introduction of another patient with
    that same name. This recognizer never repairs such ambiguity by guessing.
    """
    active=False;anchor=None;rows=[]
    for index,unit in enumerate(units):
        frame=parse_unit(unit['quote'],context)
        prior=active
        if frame is None:
            active=False;allowed=False;reason='unrecognized_complete_source_unit'
        elif frame.ownership=='target':
            leading_target = (index == 0 and frame.kind == 'patient_referral'
                and frame.explicit_reference.casefold() == context.full_name.casefold())
            if leading_target or active:
                active=True;anchor=unit['id'];allowed=True;reason='complete_explicit_target_frame'
            else:
                allowed=False;reason='patient_reference_does_not_resolve_unknown_prior_scope'
        else:
            allowed=active;reason='complete_frame_with_active_target' if active else 'no_unambiguous_target_scope'
        rows.append({'unit_id':unit['id'],'frame':None if frame is None else frame.to_dict(),'scope_before':prior,'scope_after':active,'latest_target_anchor':anchor,'ownership_admitted':allowed,'reason':reason})
    return rows
