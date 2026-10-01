"""Compact, request-bound mapping decisions. Source wording is never model-authored.

Array positions identify the immutable request's fields, slots and text references.
All offsets are Python/Unicode code points, not UTF-8 bytes or UTF-16 units.
"""
from typing import Annotated
from django.core.exceptions import ValidationError
from documents.mapping_limits import MAX_MAPPING_LABEL
from pydantic import BaseModel, ConfigDict, Field
from . import v3_mapping

MAX_CHANGES=100
MAX_OPTIONS=400
KINDS=('text','long_text','date','time','choice','checkbox','signature','initials')
FieldID=Annotated[int,Field(strict=True,ge=0,lt=200)]
SlotID=Annotated[int,Field(strict=True,ge=0,lt=1200)]
Number=Annotated[int,Field(strict=True,ge=-1,le=400000)]

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)

class FieldGroups(Strict):
    k:list[FieldID]=Field(max_length=200)
    r:list[FieldID]=Field(max_length=200)
    n:list[FieldID]=Field(max_length=200)
    u:list[FieldID]=Field(max_length=200)

class SlotGroups(Strict):
    c:list[SlotID]=Field(max_length=1200)
    n:list[SlotID]=Field(max_length=1200)
    u:list[SlotID]=Field(max_length=1200)

class Proposal(Strict):
    f:FieldGroups
    s:SlotGroups
    x:list[Annotated[list[Number],Field(min_length=7,max_length=307)]]=Field(max_length=MAX_CHANGES)
    e:bool

INSTRUCTIONS=(' Array positions are request-bound numeric IDs. Return f groups k=keep, r=replace, '
 'n=not_answer, u=uncertain; s groups c=covered, n=not_answer, u=uncertain. Each field/slot ID '
 'must occur exactly once in its groups. x contains at most 100 combined changes: '
 '[prior field ID (-1 for addition), target slot ID, kind code, label text-reference ID, '
 'label start, label end, glyph index (-1 if absent), then zero or more option text-reference/start/end triples]. '
 'Kind codes are 0=text,1=long_text,2=date,3=time,4=choice,5=checkbox,6=signature,7=initials. '
 'There may be at most 400 option triples total and 100 per change. text_refs entries are '
 '[owner ID, role code, option index]: roles 0=slot text,1=slot heading,2=slot row_label,3=slot options[index],'
 '4=existing field label. Use only target-owned slot references; role4 is only for that same field replacement '
 'at its existing destination. Spans use Unicode code-point offsets, end exclusive, never byte offsets; '
 f'labels 1..{MAX_MAPPING_LABEL} characters and options 1..200 characters. Never shorten source text to fit. '
 'Every r field needs exactly one change. When more changes/options are needed than the envelope permits, '
 'set e=true and mark remaining affected fields/slots uncertain; all slots still require verdicts.')

def catalog(payload):
    """Reference metadata only; full original strings remain once in the source catalog."""
    refs=[]
    for sid,row in enumerate(payload['slots']):
        for role,name in enumerate(('text','heading','row_label')):
            if row.get(name):refs.append([sid,role,0])
        refs.extend([sid,3,n] for n,_ in enumerate(row.get('options',[])))
    refs.extend([fid,4,0] for fid,_ in enumerate(payload['fields']))
    return refs

def _partition(groups,count,name):
    """The request-bound IDs the response OMITTED. A duplicated ID, or one the request does not contain, refuses the
    whole response (the model contradicts itself or names something that does not exist). An omitted ID is not a
    contradiction: the caller holds it `uncertain` for the clinician (campaign attempt 24 left eleven checkbox slots
    of one form unclassified, and refusing the whole proposal for it discarded every decision it did make)."""
    values=[value for group in groups.values() for value in group]
    if len(values)!=len(set(values)) or any(value>=count for value in values):
        raise ValidationError(f'Mapping {name} IDs must form one disjoint request-bound set.')
    return sorted(set(range(count))-set(values))

def expand(payload,response):
    """Validate the compact envelope, then restore the stable-source review contract.

    ENVELOPE violations refuse the WHOLE response: the schema, a duplicated or unknown field/slot ID, a change
    naming a field the request does not contain, an incomplete option triple, the source catalog differing from the
    bound request, and the option capacity. A field or slot the response OMITS is held `uncertain`. An individually
    INVALID CHANGE never refuses the rest and is never adopted: a
    replacement leaves its field `uncertain` with no target (the prior field is preserved), an addition is dropped, and
    each is returned in `rejected` with its change index, wire array, field key, proposed slot and reason. `sources` maps
    each surviving change to its index and records the text references each change quoted (a dependence reading)."""
    body=Proposal.model_validate(response).model_dump()
    omitted_fields=_partition(body['f'],len(payload['fields']),'field')
    omitted_slots=_partition(body['s'],len(payload['slots']),'slot')
    refs=payload['text_refs']
    if refs!=catalog(payload):raise ValidationError('Mapping source catalog differs from its bound request.')
    for change in body['x']:
        if (len(change)-7)%3:raise ValidationError('Incomplete mapping option span triple.')
        if not -1<=change[0]<len(payload['fields']):
            raise ValidationError('A mapping change names a field the request does not contain; no proposal was adopted.')
    if sum((len(change)-7)//3 for change in body['x'])>MAX_OPTIONS:
        raise ValidationError('Mapping option-reference capacity exceeded; no proposal was adopted.')
    used=[]
    def span(ref,start,end,sid,fid,label):
        if not 0<=ref<len(refs):raise ValidationError('Unknown source text reference.')
        owner,role,index=refs[ref]
        if role==4:
            # An original label cannot be moved into an unrelated destination.
            if not label or owner!=fid or not v3_mapping.is_mapped(payload['slots'][sid]['slot'],payload['fields'][fid]['slots']):
                raise ValidationError('Prior label does not own this replacement destination.')
            text=payload['fields'][owner]['label']
        else:
            if owner!=sid:raise ValidationError('Source text belongs to another destination.')
            row=payload['slots'][owner]
            text=row.get('options',[])[index] if role==3 else row.get(('text','heading','row_label')[role],'')
        if not 0<=start<end<=len(text) or end-start>(MAX_MAPPING_LABEL if label else 200):
            raise ValidationError('Invalid Unicode source span; source text was not truncated.')
        used.append([ref,start,end])
        return text[start:end]
    owners={}
    for change in body['x']:
        if change[0]!=-1:owners[change[0]]=owners.get(change[0],0)+1
    def target(change):
        fid,sid,kind,ref,start,end,glyph=change[:7]
        if not (0<=sid<len(payload['slots']) and 0<=kind<len(KINDS) and -1<=glyph<=199):
            raise ValidationError('Unknown mapping change destination, kind or glyph.')
        if fid!=-1 and (fid not in body['f']['r'] or owners[fid]!=1):
            raise ValidationError('Replacement does not uniquely own a replace verdict.')
        if fid!=-1 and not v3_mapping.is_mapped(payload['slots'][sid]['slot'],payload['fields'][fid]['slots']):
            raise ValidationError('Replacement target belongs to another field destination.')
        return {'slot':payload['slots'][sid]['slot'],'kind':KINDS[kind],
                'label':span(ref,start,end,sid,fid,True),'glyph':None if glyph==-1 else glyph,
                'options':[span(*change[n:n+3],sid,fid,False) for n in range(7,len(change),3)]}
    replacements={};additions=[];rejected=[];sources={'fields':{},'additions':[],'refs':{}}
    def reject(number,change,fid,sid,reason):
        rejected.append({'change':number,'wire':None if change is None else list(change),
                         'type':'addition' if fid==-1 else 'replacement',
                         'key':payload['fields'][fid]['key'] if 0<=fid<len(payload['fields']) else '',
                         'slot':payload['slots'][sid]['slot'] if 0<=sid<len(payload['slots']) else '','reason':reason})
    for number,change in enumerate(body['x']):
        fid,sid=change[0],change[1]
        used.clear()
        try:built=target(change)
        except ValidationError as exc:
            reject(number,change,fid,sid,' '.join(exc.messages));continue
        finally:sources['refs'][number]=[list(row) for row in used]
        if fid==-1:additions.append(built);sources['additions'].append(number)
        else:replacements[fid]=built;sources['fields'][payload['fields'][fid]['key']]=number
    for fid in body['f']['r']:
        if fid not in replacements and not any(row['key']==payload['fields'][fid]['key'] for row in rejected):
            reject(None,None,fid,-1,'A replacement verdict lacks its bound change.')
    held={row['key'] for row in rejected if row['key']}
    fields=[];slots=[]
    for code,verdict in [('k','keep'),('r','replace'),('n','not_answer'),('u','uncertain')]:
        for fid in body['f'][code]:
            key=payload['fields'][fid]['key']
            # A field touched by a rejected change is held for review; it never carries a target.
            fields.append({'key':key,'verdict':'uncertain' if key in held else verdict,
                           'target':None if key in held else replacements.get(fid)})
    # An omitted field or slot is held for review: never adopted, never a target.
    fields.extend({'key':payload['fields'][fid]['key'],'verdict':'uncertain','target':None} for fid in omitted_fields)
    for code,verdict in [('c','covered'),('n','not_answer'),('u','uncertain')]:
        slots.extend({'slot':payload['slots'][sid]['slot'],'verdict':verdict} for sid in body['s'][code])
    slots.extend({'slot':payload['slots'][sid]['slot'],'verdict':'uncertain'} for sid in omitted_slots)
    fields.sort(key=lambda row:next(n for n,f in enumerate(payload['fields']) if f['key']==row['key']))
    slots.sort(key=lambda row:next(n for n,s in enumerate(payload['slots']) if s['slot']==row['slot']))
    return {'fields':fields,'slots':slots,'additions':additions,'rejected':rejected,'sources':sources},body['e']

def fixture(payload):
    mapped={slot for field in payload['fields'] for slot in field['slots']}
    return {'f':{'k':list(range(len(payload['fields']))),'r':[],'n':[],'u':[]},
            's':{'c':[n for n,row in enumerate(payload['slots']) if row['slot'] in mapped],
                 'n':[],'u':[n for n,row in enumerate(payload['slots']) if row['slot'] not in mapped]},'x':[],'e':False}
