"""Scoped drafts for new inline Word definitions; layout and approval stay separate."""
from copy import deepcopy
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect,render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from documents.semantic_preparation_roles import DefinitionError,digest,protected_field,validate_definitions
from . import component_review as editor,word_contract,template_review
from .models import TemplatePreparation
from .security import membership,audit,private_path
from .template_source import approval_binding
from .save_recovery import recoverable_save, binding as save_binding

SALT='inline-field-components-review-v1'
EDITABLE=('review','guided')

def binding(prep,actor,field_key):
    return {'contract':SALT,'actor':str(actor.pk),'template':str(prep.template_id),
        'preparation':str(prep.pk),'field':field_key,'revision':prep.revision,
        'source_sha256':prep.template.sha256,'original_path':prep.template.original_path,
        'candidate_path':prep.candidate_path,'preparation_sha256':approval_binding(prep),
        'config_sha256':digest(prep.config)}

def token_for(prep,actor,field_key):
    return signing.dumps(binding(prep,actor,field_key),salt=SALT,compress=True)

def verify_token(prep,actor,field_key,token):
    try:value=signing.loads(token,salt=SALT,max_age=12*60*60)
    except signing.BadSignature as exc:
        raise ValidationError('This component review expired. Reopen the current preparation before saving.')from exc
    if value!=binding(prep,actor,field_key):
        raise ValidationError('The form changed after this component review opened. Reopen it; nothing was saved.')

def current_field(prep,field_key):
    if prep.config.get(word_contract.CONFIG_KEY)!=word_contract.GRAPH_PROFILE:
        raise Http404()
    try:version=word_contract.definition_version(prep.config)
    except ValidationError as exc:raise Http404()from exc
    if version!=4 or not word_contract.eligible(prep.inventory):
        raise Http404()
    fields={f['key']:f for f in prep.inventory['fields']}
    if field_key not in fields or protected_field(fields[field_key]):
        raise Http404()
    return fields[field_key]

@transaction.atomic
def correct_components(prep_id,actor,field_key,token,definition,reason):
    prep=TemplatePreparation.objects.select_for_update().select_related('template').get(pk=prep_id)
    membership(actor,prep.template.department,roles=['owner','clinician'])
    verify_token(prep,actor,field_key,token)
    field=current_field(prep,field_key)
    if prep.state not in EDITABLE or prep.inventory['issues'] or not prep.candidate_path:
        raise ValidationError('Review components in the current unapproved Word preparation.')
    if not isinstance(reason,str)or not 12<=len(reason.strip())<=1000:
        raise ValidationError('Explain the component correction in 12 to 1000 characters.')
    from documents.preparation import validate_inventory
    from documents.preparation_service import read_original
    from .preparation import read_retained_role,role_payload
    import hashlib
    validate_inventory(prep.inventory)
    if (prep.inventory['source_sha256']!=prep.template.sha256
            or hashlib.sha256(read_original(private_path(prep.template.original_path))).hexdigest()!=prep.template.sha256
            or hashlib.sha256(read_original(private_path(prep.candidate_path))).hexdigest()!=prep.candidate_sha256):
        raise ValidationError('The original or prepared Word source changed; no draft was saved.')
    receipts=list(prep.receipts.order_by('role'))
    if len(receipts)!=2 or {r.role for r in receipts}!={'proposer','checker'}:
        raise ValidationError('Both retained independent preparation results are required.')
    for receipt in receipts:
        expected=prep.proposal if receipt.role=='proposer'else prep.checker
        payload=role_payload(prep.inventory,receipt.role,prep.proposal if receipt.role=='checker'else None,config=prep.config)
        if (receipt.state!='succeeded'or receipt.finished_at is None or receipt.computed_cost is None
                or receipt.request_sha256!=digest(payload)
                or digest(read_retained_role(receipt,prep.config['mode']))!=digest(expected)):
            raise ValidationError('The retained preparation evidence changed; no draft was saved.')
    values=word_contract.proposed(prep);values[field_key]=deepcopy(definition)
    try:validate_definitions(prep.inventory['fields'],values)
    except DefinitionError as exc:raise ValidationError(str(exc))from exc
    if any(d['version']!=4 or d['component_contract']['contract']!=word_contract.component_contract(prep.config)for d in values.values()):
        raise ValidationError('The component draft must retain this preparation’s complete scope contract.')
    # This is one scoped draft, never an exhaustive field/location adjudication.
    prep.corrections={**deepcopy(prep.corrections),'answer_definitions':values}
    prep.revision+=1;prep.state='guided'
    prep.correction_history.append({'revision':prep.revision,'actor_id':str(actor.pk),
        'at':timezone.now().isoformat(),'reason':reason.strip(),'review_scope':'field_components',
        'component_reviewed_field':field_key,'reviewed_fields':[],
        'definition_sha256':digest(definition),'answer_definitions':deepcopy(values)})
    prep.save(update_fields=['corrections','revision','state','correction_history'])
    audit(actor,'template.preparation_components_corrected',prep.pk,department=prep.template.department,
        revision=prep.revision,field_key=field_key,definition_sha256=digest(definition))
    return prep

@recoverable_save('inline')
@require_http_methods(['GET','POST'])
def edit(request,pk,field_key):
    from .preparation_views import selected
    template,prep=selected(request,pk)
    if membership(request.user,template.department).role not in ('owner','clinician'):
        raise Http404()
    field=current_field(prep,field_key);current=word_contract.proposed(prep)[field_key]
    error,token_valid='',False;display_definition=deepcopy(current);display_parts=editor.parts_for(field,current)
    if request.method=='POST':
        try:
            token=editor.one(request.POST,'component_token');verify_token(prep,request.user,field_key,token);token_valid=True
            definition=editor.posted_definition(prep,field,current,request.POST)
            correct_components(prep.pk,request.user,field_key,token,definition,editor.one(request.POST,'reason'))
            return redirect('template_preparation',pk=template.pk)
        except (ValidationError,DefinitionError)as exc:
            error='; '.join(exc.messages)if isinstance(exc,ValidationError)else str(exc)
            if token_valid:
                # Preserve attempted controls only for redisplay; none become proof.
                prefix='field_'+field_key+'_'
                for name in ('meaning','value_type','answer_mode','patient_name_requirement','unit'):
                    if len(request.POST.getlist(prefix+name))==1:display_definition[name]=request.POST[prefix+name]
                for name in ('subject','temporality','polarity'):
                    if len(request.POST.getlist(prefix+name))==1:display_definition['scope'][name]=request.POST[prefix+name]
                for name in editor.CONSTRAINT_KEYS:
                    if len(request.POST.getlist(prefix+name))==1:display_definition['constraints'][name]=request.POST[prefix+name]or None
                if len(request.POST.getlist(prefix+'choices'))==1:display_definition['choices']=request.POST[prefix+'choices'].splitlines()
                if len(request.POST.getlist('rendering'))==1:display_definition['component_contract']['rendering']=request.POST['rendering']
                for part in display_parts:
                    base='part_'+str(part['index'])+'_'
                    for name in editor.part_controls(current):
                        if len(request.POST.getlist(base+name))==1:
                            if name in ('subject','temporality','polarity'):part['scope'][name]=request.POST[base+name]
                            else:part[name]=request.POST[base+name]
                    part['remove']=request.POST.getlist(base+'remove')==['on'];part['add']=request.POST.getlist(base+'add')==['on']
    row=template_review.rows([{'field':field,'definition':display_definition,'state':''}])[0]
    return render(request,'template_component_review.html',{'preparation':prep,'template':template,'row':row,
        'parts':display_parts,'definition_version':4,'component_editing':True,
        'component_token':token_for(prep,request.user,field_key),'renderings':editor.RENDERINGS,
        'save_binding':save_binding(prep,'inline'),
        'component_encounter_scopes':editor.ENCOUNTER_SCOPE_LABELS,
        'unit_requirements':[('none','No unit required'),('documented','Keep the documented unit and scale'),('printed','Use the exact unit printed on the form')],
        'component_types':list(template_review.TYPE_LABELS.items()),'subjects':list(template_review.SUBJECT_LABELS.items()),
        'temporalities':list(template_review.TIMING_LABELS.items()),'polarities':list(template_review.POLARITY_LABELS.items()),
        'editable':prep.state in EDITABLE,'reason':request.POST.get('reason','')if token_valid else'',
        'component_back_url':reverse('template_preparation',args=[template.pk]),'error':error},status=409 if error else 200)
