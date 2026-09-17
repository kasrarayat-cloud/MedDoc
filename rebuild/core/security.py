import hashlib
import secrets
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .models import AuditEvent, Department, Membership, LoginAttempt

def audit(actor,action,target='',department=None,**details):
    # Only metadata belongs in audit records. Clinical text and credentials never do.
    return AuditEvent.objects.create(actor=actor if actor and actor.is_authenticated else None,action=action,target=str(target),department=department,organization=department.organization if department else None,details=details)

def departments(user):
    return Department.objects.filter(membership__user=user,membership__active=True)

def scoped(model,user):
    return model.objects.filter(department__in=departments(user))

def membership(user,department,roles=None):
    m=Membership.objects.filter(user=user,department=department,active=True,user__is_active=True,user__verified_at__isnull=False).first()
    if not m or not user.is_active or not user.verified_at or (roles and m.role not in roles): raise PermissionDenied('You do not have permission for this department.')
    return m

def token(): return secrets.token_urlsafe(32)
def digest(value): return hashlib.sha256(value.encode()).hexdigest()

def private_path(relative):
    root=settings.MEDIA_ROOT.resolve()
    path=(root/relative).resolve()
    if not path.is_relative_to(root) or path==root: raise ValidationError('Invalid private file location.')
    return path

def store_upload(upload,category='originals',max_bytes=15*1024*1024):
    if upload.size>max_bytes: raise ValidationError('File exceeds the 15 MB upload limit.')
    suffix=Path(upload.name).suffix.lower()
    if suffix not in ('.docx','.pdf','.wav','.webm','.mp3','.m4a'): raise ValidationError('Unsupported file type.')
    relative=f'{category}/{secrets.token_hex(24)}{suffix}'
    path=private_path(relative)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    count=0
    try:
        with path.open('xb') as f:
            path.chmod(0o600)
            for chunk in upload.chunks():
                count+=len(chunk)
                if count>max_bytes: raise ValidationError('File exceeds upload limit.')
                f.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return relative

@transaction.atomic
def rate_limit(key,limit=8,seconds=600):
    hashed=digest(key)
    row,_=LoginAttempt.objects.get_or_create(key=hashed,defaults={'window_start':timezone.now()})
    row=LoginAttempt.objects.select_for_update().get(pk=row.pk)
    if row.window_start<timezone.now()-timedelta(seconds=seconds): row.count=0; row.window_start=timezone.now()
    row.count+=1
    row.save(update_fields=['count','window_start'])
    return row.count<=limit
