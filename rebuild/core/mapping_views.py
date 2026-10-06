"""Small mapping-operation surface; all source fields remain on the existing mapping review page."""
from decimal import Decimal
from django.contrib import messages
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from . import generation, mapping_assistance as mapping, mapping_jobs, v3_mapping
from .models import Template, TemplateVersion, Job
from .security import scoped, membership, audit

def shown_area(row):
    from .field_location import part_name
    part=row.get('slot','').partition('#')[0]
    location=part_name(part)+' · '+v3_mapping.PLACE_KINDS.get(row.get('kind'),'answer area')
    if type(row.get('row')) is int and type(row.get('column')) is int:
        location+=f' · row {row["row"]+1}, column {row["column"]+1}'
    return {**row,'location':location}

@require_http_methods(['GET','POST'])
def review(request,pk):
    if not mapping_jobs.enabled():raise Http404
    template=get_object_or_404(scoped(Template,request.user),pk=pk)
    membership(request.user,template.department,roles=['owner','clinician','manager'])
    version=template.versions.order_by('-number').first()
    if version.contract!='v3':raise Http404
    error='';quote=None;approval='';status=200
    if request.method=='POST':
        try:
            if request.POST.get('action')=='cancel':
                from .jobs import cancel
                job=get_object_or_404(Job,mapping_version__template=template,kind='mapping',pk=request.POST.get('job'))
                cancel(job,request.user)
                messages.info(request,'Queued mapping cancelled; held funds released.')
                return redirect('mapping_assistance',pk=pk)
            if request.POST.get('action')=='resolve':
                resolve(request,template,version)
                return redirect('template_detail',pk=pk)
            if request.POST.get('action')!='queue':raise ValidationError('Choose a mapping action.')
            data=signing.loads(request.POST.get('approval',''),salt='mapping-quote',max_age=600)
            if data['user']!=str(request.user.pk) or data['version']!=str(version.pk):
                raise ValidationError('This quote belongs to another user or mapping version.')
            if request.POST.get('blank_only')!='on':raise ValidationError('Confirm this is a blank form with no patient information.')
            job=mapping_jobs.enqueue(version,request.user,data['config'],data['request_sha256'])
            messages.info(request,'Mapping operation '+job.state+'. Review its result on this page before confirming the mapping.')
            return redirect('mapping_assistance',pk=pk)
        except (ValidationError,ValueError,KeyError,signing.BadSignature) as exc:
            error='; '.join(exc.messages) if isinstance(exc,ValidationError) else 'The mapping request or quote is invalid or expired.'
            status=400
    try:
        config=generation.configuration()
        mapping_jobs.permission(config)
        compiled=mapping.compile_request(version,config)
        quote={'limit':Decimal(compiled['maximum_cost'])*Decimal('1.5') if config['mode']=='live' else Decimal(0),
               'simulated':config['mode']!='live','bytes':len(mapping.canonical(compiled['request']).encode())}
        approval=signing.dumps({'user':str(request.user.pk),'version':str(version.pk),'config':config,
                               'request_sha256':compiled['request_sha256']},salt='mapping-quote')
    except (ValidationError,ValueError) as exc:
        if not error:error='; '.join(exc.messages) if isinstance(exc,ValidationError) else 'This form cannot be prepared for mapping assistance.'
    areas={row['slot']:shown_area(row) for row in version.assistance.get('areas',[])}
    unresolved=[{**areas.get(row['slot'],shown_area(row)),**row} for row in version.assistance.get('unresolved',[])]
    from .jobs import deliverable
    operations=list(Job.objects.filter(mapping_version__template=template).order_by('-created_at')[:20])
    # A charged operation's stored provider output, under views.job_result's rule (RR2-L1).
    for job in operations:job.deliverable=bool(job.result_path) and deliverable(job)
    return render(request,'mapping_assistance.html',{'template':template,'version':version,'error':error,'quote':quote,
        'approval':approval,'operations':operations,
        'unresolved':unresolved,'areas':list(areas.values()),'record':version.assistance},status=status)

@transaction.atomic
def resolve(request,template,version):
    """The clinician's decision on every unresolved assistance area, saved as a new assisted version.

    ⚠️ REMOVALS FIRST, THEN EVERY DECISION IS JUDGED AGAINST THE MAPPING THAT WILL BE SAVED. A 'mapped' decision was
    checked before the same submission removed the field that mapped it, and a key-less 'not an answer' on an area a
    field still writes to removed nothing and was saved. The resulting mapping is then validated as a whole (overlaps,
    keys, boxes and the original's destination roles, read now) before anything is saved."""
    template=Template.objects.select_for_update().get(pk=template.pk)
    latest=template.versions.order_by('-number').first()
    if latest.pk!=version.pk or request.POST.get('mapping_version')!=str(version.pk):
        raise ValidationError('The mapping changed. Review the latest version.')
    unresolved=version.assistance.get('unresolved',[])
    if not unresolved:raise ValidationError('No unresolved assistance areas remain.')
    posted=[]
    for number,row in enumerate(unresolved):
        decision=request.POST.get('resolution_'+str(number))
        if decision not in ('mapped','not_answer'):raise ValidationError('Review every unresolved area before saving.')
        posted.append((row,decision))
    removed={row['key'] for row,decision in posted if decision=='not_answer' and row.get('key')}
    fields=[f for f in version.fields if f['key'] not in removed]
    mapped=v3_mapping.mapped_slots(fields);decisions=[]
    for row,decision in posted:
        slot=row.get('slot') or ''
        if decision=='mapped' and not v3_mapping.is_mapped(slot,mapped):
            raise ValidationError('Add this missed area on the mapping page before marking it mapped.')
        if decision=='not_answer' and not row.get('key') and slot and v3_mapping.is_mapped(slot,mapped):
            raise ValidationError('A field of this mapping still writes to an area you marked not an answer. Remove that '
                                  'field on the mapping page first, or mark the area mapped. Nothing was saved.')
        decisions.append({'slot':slot,'key':row.get('key',''),'decision':decision})
    from .views import v3_outline
    mapping.validate_mapping(version,fields,v3_outline(template))
    from .import_binding import for_mapping
    new=TemplateVersion.objects.create(template=template,number=version.number+1,fields=fields,contract='v3',
        import_manifest=for_mapping(version.import_manifest,fields),
        created_by=request.user,review_requirements=version.review_requirements,
        assistance={**version.assistance,'unresolved':[],'assisted':True,'resolutions':decisions},
        corrections={'base_version':version.number,'removed':[f for f in version.fields if f['key'] in removed],
                     'added':[],'kind_changed':{},'renamed':[]})
    audit(request.user,'mapping.areas_reviewed',new.pk,department=template.department,areas=len(decisions),assisted=True)
    messages.success(request,'Area decisions saved as a new assisted mapping version. Check and confirm it on the mapping page.')
