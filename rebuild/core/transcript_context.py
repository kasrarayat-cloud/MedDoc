"""Explicit default subject for one reviewed transcript; never permission to adopt answers.

The clinician supplies WHO for otherwise subjectless statements. Source bytes,
model relations, time, negation, laterality and every clinical floor remain binding.
"""
import hashlib
import re

from django.core import signing
from django.core.exceptions import ValidationError

CONTRACT='reviewed-transcript-patient-context-v1'
SALT='quillmd.reviewed-transcript-patient-context.v1'
INSTRUCTIONS=(
    'A clinician explicitly confirmed patient_default_context for the bounded reviewed transcript span. '
    'Within that span only, otherwise subjectless statements refer to this encounter patient. '
    'This supplies a default subject only: explicit relatives, other people, quoted speech, denials, uncertainty, '
    'time, laterality, medication discontinuation, corrections and contradictions keep their complete meaning. '
    'It does not confirm any proposed field answer, consent, signature or attestation. ')

def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()

def token_for(review):
    return signing.dumps({'contract':CONTRACT,'review':str(review.pk),'job':str(review.job_id),
        'actor':str(review.reviewed_by_id),'source_revision':review.source_revision,
        'notes_sha256':review.source_sha256,'raw_sha256':review.raw_sha256,
        'result_sha256':review.result_sha256,'reviewed_sha256':review.reviewed_sha256,
        'start':review.span_start,'end':review.span_end},salt=SALT,compress=True)

def verified(notes,token):
    if not isinstance(token,str) or not token or len(token)>5000:return None
    try:
        value=signing.loads(token,salt=SALT)
        if (not isinstance(value,dict) or set(value)!={'contract','review','job','actor','source_revision',
                'notes_sha256','raw_sha256','result_sha256','reviewed_sha256','start','end'}
                or value['contract']!=CONTRACT or value['notes_sha256']!=digest(notes)
                or type(value['start']) is not int or type(value['end']) is not int
                or not 0<=value['start']<value['end']<=len(notes)
                or digest(notes[value['start']:value['end']])!=value['reviewed_sha256']):return None
        return value
    except (signing.BadSignature,KeyError,TypeError,ValueError):return None

def current(encounter):
    """A current context requires the same source edit version, even after edit-and-revert."""
    from .models import AuditEvent,TranscriptReview
    saved=AuditEvent.objects.filter(target=str(encounter.pk),action='encounter.notes_saved').order_by('-created_at','-pk').first()
    if saved is None:return ''
    review=TranscriptReview.objects.filter(encounter=encounter,patient_context=True,
        source_revision=saved.details.get('revision'),source_sha256=digest(encounter.notes)).order_by('-created_at').first()
    return review.context_token if review and verified(encounter.notes,review.context_token) else ''

def admitted(config,encounter):
    """Only the server's current review can enter a job; a supplied quote token cannot grant context."""
    config={k:v for k,v in config.items() if k!='patient_default_context'}
    if config.get('ordinary_field_contract') and (token:=current(encounter)):
        config['patient_default_context']=token
    return config

def payload(notes,token):
    proof=verified(notes,token)
    if not proof:raise ValidationError('The reviewed transcript context changed; no request was sent.')
    return {'contract':CONTRACT,'start':proof['start'],'end':proof['end'],
            'reviewed_sha256':proof['reviewed_sha256'],'default_subject':'encounter_patient'}

def apply(reading,token):
    """Only subjectless, locally complete patient topics gain a default actor.

    Explicit other-person runs remain other-person runs until an explicit patient
    statement resets them. A personal pronoun never becomes subjectless here.
    """
    proof=verified(reading['source']['quote'],token)
    if not proof:return reading
    from . import v3_actors as a,v3_syntax
    units=reading['units'];docs=v3_syntax.docs(u['quote'] for u in units)
    if docs is None:return reading
    prefix='The patient '
    augmented=v3_syntax.docs(prefix+u['quote'][0].lower()+u['quote'][1:] for u in units)
    eligible=set();blocked=False
    for index,(unit,doc) in enumerate(zip(units,docs)):
        uid=unit['id'];info=reading['actors'][uid]
        if info.get('kind')=='patient' and not info.get('other_floor'):blocked=False
        if info.get('other_floor') or reading['resolved'][uid].get('self_other'):blocked=True
        if (blocked or doc is None or not proof['start']<=unit['start']<unit['end']<=proof['end']
                or not info.get('readable') or info.get('kind')=='pronoun'
                or info.get('habitual') or info.get('past_time')):continue
        sole=info.get('sole') or {}
        # A parser often calls subjectless "Reports left ankle pain" a nominal
        # Reports + past-tense left. The explicit default actor resolves that
        # grammatical ambiguity only for a regularly inflected present verb in
        # the pinned lexicon. This alternate parse supplies syntax, never source
        # words or a new clinical claim; a named subject cannot enter this arm.
        first=next((t for t in doc if not t.is_punct and not t.is_space),None)
        word=a._fold(first.text) if first else ''
        bases={word[:-1],word[:-2],word[:-3]+'y'} if re.fullmatch('[a-z]+s',word) else set()
        def inflect(base):
            if base.endswith('y') and len(base)>1 and base[-2] not in 'aeiou':return base[:-1]+'ies'
            return base+('es' if base.endswith(('s','x','z','ch','sh','o')) else 's')
        regular=any(base in v3_syntax._verbs() and inflect(base)==word for base in bases)
        alternate=augmented[index] if augmented is not None else None
        root=next((t for t in alternate if t.dep_=='ROOT'),None) if alternate is not None else None
        syntax=bool(regular and root is not None and root.idx==len(prefix)
                    and root.tag_=='VBZ' and root.pos_=='VERB'
                    and not any(t.dep_ in ('nsubj','nsubjpass') and t.text!='patient' for t in alternate))
        if syntax:
            sole=a._sole_reading(alternate,root,value_start=0,colon=False,age=False,opener=False,explicit=True)
        if not sole.get('nouns_ok') or sole.get('bad_pronoun') or sole.get('fronted'):continue
        if info.get('finite_past') and not syntax:continue
        # An explicit subject belongs to its own clause. A matching printed-label
        # wrapper supplies a question, rather than somebody whose finding to infer.
        own=reading['parsed'].get(uid)
        value=[t for t in doc if not own or t.idx>=len(unit['quote'])-len(own[1])]
        # An otherwise subjectless command or modal is not evidence of a current
        # medication/finding. Confirmation supplies a subject, never an order,
        # possibility or future action as an established current fact.
        if any(t.tag_=='MD' for t in value):continue
        if not syntax and any(t.dep_ in ('nsubj','nsubjpass','csubj','csubjpass','expl') for t in value):continue
        if any(t.pos_=='PRON' and a._fold(t.text) in a.PERSONAL for t in value):continue
        # Unknown nominal subjects/objects and quoted speakers fail closed through
        # nouns_ok; quotation is never a subjectless clinician declaration.
        if any(t.text in ('"','“','”','‘','’') for t in doc):continue
        if info.get('bare_cessation') or info.get('ceased_keys') or info.get('intention'):continue
        if info.get('dependent') or info.get('bounded'):continue
        nominal=bool(not own and not any(t.pos_ in ('VERB','AUX') for t in value)
            and sole.get('classes') & {'symptom','finding','injury','condition','medication'}
            and not sole.get('unknown')
            and first is not None and first.pos_ in ('ADJ','NUM')
            and any(t.dep_ in ('amod','compound','prep','nummod') for t in value))
        if not own and not syntax and not nominal and not any(t.pos_=='VERB' and t.tag_ in ('VBP','VBZ') for t in value):continue
        eligible.add(uid)
    return {**reading,'confirmed_patient':frozenset(eligible)}
