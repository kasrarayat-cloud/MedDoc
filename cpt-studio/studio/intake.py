"""Creating an encounter from an upload or pasted text — the one place it happens.

The API and the evaluation command both call this, so the synthetic
attestation, immutable original storage and pipeline start cannot diverge.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from . import audit, jobs, models
from .storage import media_type_for, store_original


def create_encounter(*, membership, user, title, service_date='', data=None, filename='', text=''):
    """Create encounter + revision 1 and start the pipeline after commit.

    Exactly one of (data, filename) or text. Raises ValidationError with a
    member-readable message for anything invalid. The caller has already
    obtained the member's explicit synthetic attestation.
    """
    if (data is None) == (not text.strip()):
        raise ValidationError('Provide either a file or pasted text.')
    media_type = None
    if data is not None:
        if len(data) > settings.MAX_UPLOAD_BYTES:
            raise ValidationError(f'The file is larger than {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.')
        media_type = media_type_for(filename, data[:8])
    elif len(text) > settings.MAX_PASTE_CHARS:
        raise ValidationError(f'Pasted text is longer than {settings.MAX_PASTE_CHARS} characters.')
    now = timezone.now()
    with transaction.atomic():
        encounter = models.Encounter.objects.create(
            workspace=membership.workspace, title=title, created_by=user,
            user_values={'service_date': service_date} if service_date else {})
        source_file = None
        if data is not None:
            storage_name, digest, size = store_original(membership.workspace_id, data, filename)
            source_file = models.SourceFile.objects.create(
                encounter=encounter, original_name=filename[:255], media_type=media_type, size=size,
                sha256=digest, storage_name=storage_name, uploaded_by=user)
        revision = models.SourceRevision.objects.create(
            encounter=encounter, number=1,
            kind=models.SourceRevision.UPLOAD if source_file else models.SourceRevision.PASTE,
            source_file=source_file, pasted_text='' if source_file else text,
            synthetic_attested_by=user, synthetic_attested_at=now, created_by=user)
        encounter.current_revision = revision
        encounter.save(update_fields=['current_revision', 'updated_at'])
        audit.record(membership.workspace, 'encounter.created', encounter=encounter, actor=user, kind=revision.kind,
                     sha256=source_file.sha256 if source_file else None, media_type=media_type or 'text/plain')
        # Queued in the same transaction: the encounter is never visible without its pipeline.
        jobs.start_pipeline(revision, user)
    return encounter
