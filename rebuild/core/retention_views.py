"""MFA-protected preservation API. No clinical body, filename or purge endpoint."""
import json
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect,render
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from .admin_views import gate
from . import retention
from .retention_forms import HoldForm,ReleaseForm
from .models import RetentionHold
from .admin_queries import page_for
from .security import audit


@require_http_methods(['GET','POST'])
def page(request):
    gate(request)
    action=request.POST.get('action') if request.method=='POST' else None
    create_form=HoldForm(request.POST if action=='create' else None)
    release_form=ReleaseForm(request.POST if action=='release' else None)
    form=create_form if action=='create' else release_form if action=='release' else None
    if form and form.is_valid():
        try:
            data=form.cleaned_data
            if action=='create':
                retention.create_hold(request.user,data['scope'],data['target'],data['authority_sha256'],data['request_key'])
                messages.success(request,'Preservation hold recorded. Clinical corrections keep their prior values as protected evidence.')
            else:
                retention.release_hold(request.user,data['hold'],data['authority_sha256'])
                messages.success(request,'Hold released. Preserved evidence remains retained; no data was deleted.')
            return redirect('retention_holds')
        except ValidationError as error:form.add_error(None,error)
    rows=RetentionHold.objects.select_related('created_by','release__created_by').order_by('-created_at','pk')
    navigation=page_for(request,rows,anchor='holds',size=25)
    audit(request.user,'retention.holds_read')
    return render(request,'retention_holds.html',{'create_form':create_form,'release_form':release_form,'rows':navigation['page'],'navigation':navigation})


def body(request,expected):
    if len(request.body)>2048:raise ValidationError('Preservation request is too large.')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValidationError('Duplicate preservation property.')
            result[key]=value
        return result
    try:data=json.loads(request.body,object_pairs_hook=pairs)
    except (ValueError,UnicodeError):raise ValidationError('Invalid preservation request.')
    if not isinstance(data,dict) or set(data)!=set(expected):raise ValidationError('Invalid preservation properties.')
    return data


@require_POST
def create(request):
    gate(request)
    try:
        data=body(request,('scope','target','authority_sha256','request_key'))
        row=retention.create_hold(request.user,data['scope'],data['target'],data['authority_sha256'],data['request_key'])
    except ValidationError:return JsonResponse({'error':'Preservation instruction rejected.'},status=400)
    return JsonResponse({'id':str(row.pk),'released':hasattr(row,'release'),'purge_authorized':False})


@require_POST
def release(request,pk):
    gate(request)
    try:
        data=body(request,('authority_sha256',))
        row=retention.release_hold(request.user,pk,data['authority_sha256'])
    except ValidationError:return JsonResponse({'error':'Preservation release rejected.'},status=400)
    return JsonResponse({'id':str(row.hold_id),'released':True,'purge_authorized':False})
