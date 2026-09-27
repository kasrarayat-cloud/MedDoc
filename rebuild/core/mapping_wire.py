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
    values=[value for group in groups.values() for value in group]
    if len(values)!=count or set(values)!=set(range(count)):
        raise ValidationError(f'Mapping {name} IDs must form one complete, disjoint request-bound set.')

def expand(payload,response):
    """Validate the compact envelope, then restore the stable-source review contract."""
    body=Proposal.model_validate(response).model_dump()
    _partition(body['f'],len(payload['fields']),'field')
    _partition(body['s'],len(payload['slots']),'slot')
    refs=payload['text_refs']
    if refs!=catalog(payload):raise ValidationError('Mapping source catalog differs from its bound request.')
    if sum((len(change)-7)//3 for change in body['x'])>MAX_OPTIONS:
        raise ValidationError('Mapping option-reference capacity exceeded; no proposal was adopted.')
    replacements={};additions=[]
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
        return text[start:end]
    for change in body['x']:
        if (len(change)-7)%3:raise ValidationError('Incomplete mapping option span triple.')
        fid,sid,kind,ref,start,end,glyph=change[:7]
        if not (-1<=fid<len(payload['fields']) and 0<=sid<len(payload['slots']) and 0<=kind<len(KINDS) and -1<=glyph<=199):
            raise ValidationError('Unknown mapping change destination, kind, field or glyph.')
        if fid!=-1 and (fid not in body['f']['r'] or fid in replacements):
            raise ValidationError('Replacement does not uniquely own a replace verdict.')
        if fid!=-1 and not v3_mapping.is_mapped(payload['slots'][sid]['slot'],payload['fields'][fid]['slots']):
            raise ValidationError('Replacement target belongs to another field destination.')
        target={'slot':payload['slots'][sid]['slot'],'kind':KINDS[kind],
                'label':span(ref,start,end,sid,fid,True),'glyph':None if glyph==-1 else glyph,
                'options':[span(*change[n:n+3],sid,fid,False) for n in range(7,len(change),3)]}
        if fid==-1:additions.append(target)
        else:replacements[fid]=target
    if set(replacements)!=set(body['f']['r']):raise ValidationError('A replacement verdict lacks its bound change.')
    fields=[];slots=[]
    for code,verdict in [('k','keep'),('r','replace'),('n','not_answer'),('u','uncertain')]:
        fields.extend({'key':payload['fields'][fid]['key'],'verdict':verdict,'target':replacements.get(fid)} for fid in body['f'][code])
    for code,verdict in [('c','covered'),('n','not_answer'),('u','uncertain')]:
        slots.extend({'slot':payload['slots'][sid]['slot'],'verdict':verdict} for sid in body['s'][code])
    fields.sort(key=lambda row:next(n for n,f in enumerate(payload['fields']) if f['key']==row['key']))
    slots.sort(key=lambda row:next(n for n,s in enumerate(payload['slots']) if s['slot']==row['slot']))
    return {'fields':fields,'slots':slots,'additions':additions},body['e']

def fixture(payload):
    mapped={slot for field in payload['fields'] for slot in field['slots']}
    return {'f':{'k':list(range(len(payload['fields']))),'r':[],'n':[],'u':[]},
            's':{'c':[n for n,row in enumerate(payload['slots']) if row['slot'] in mapped],
                 'n':[],'u':[n for n,row in enumerate(payload['slots']) if row['slot'] not in mapped]},'x':[],'e':False}
