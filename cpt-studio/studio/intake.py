"""Creating an encounter from an upload or pasted text — the one place it happens.

The API and the evaluation command both call this, so the synthetic
attestation, immutable original storage and pipeline start cannot diverge.
"""
import hashlib
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import audit, jobs, models
from .storage import media_type_for, store_original

# P5 FLOW: a repeated POST of one upload attempt (the page's client_key) within this window answers with the encounter
# the first made; a key older than that, or one a member used for another document, is refused, never reused.
UPLOAD_KEY_WINDOW = timedelta(hours=24)
KEY_USED = 'This upload was already received. Open it from your documents.'
KEY_OTHER_DOCUMENT = 'This upload key was already used for a different document. Reload the page and upload again.'


class UploadKeyRefused(Exception):
    """A client_key that names an earlier upload this request cannot be (the API answers 409 with the message)."""


class DuplicateUpload(Exception):
    """The upload attempt's encounter already exists (made by a concurrent POST of the same attempt)."""

    def __init__(self, encounter):
        super().__init__(str(encounter.pk))
        self.encounter = encounter


def _same_document(encounter, data, text):
    first = encounter.revisions.select_related('source_file').order_by('number').first()
    if first is None:
        return False
    if data is not None:
        return first.source_file is not None and first.source_file.sha256 == hashlib.sha256(data).hexdigest()
    return first.source_file is None and first.pasted_text == text


def find_upload(*, user, workspace, client_key, data=None, text=''):
    """The encounter an earlier POST of this same upload attempt made - the member's own, in this workspace, within
    UPLOAD_KEY_WINDOW, of the same file (sha256) or pasted text - or None when the key is new (or None). A key that names
    an encounter this request cannot be (another document, another workspace, or past the window) is refused
    (UploadKeyRefused): a retried upload never makes a second encounter, and a key is never reused for another one."""
    if client_key is None:
        return None
    encounter = models.Encounter.objects.filter(created_by=user, client_key=client_key).first()
    if encounter is None:
        return None
    if encounter.workspace_id != workspace.pk or encounter.created_at < timezone.now() - UPLOAD_KEY_WINDOW:
        raise UploadKeyRefused(KEY_USED)
    if not _same_document(encounter, data, text):
        raise UploadKeyRefused(KEY_OTHER_DOCUMENT)
    return encounter


def create_encounter(*, membership, user, title, service_date='', data=None, filename='', text='', client_key=None):
    """Create encounter + revision 1 and start the pipeline after commit.

    Exactly one of (data, filename) or text. Raises ValidationError with a
    member-readable message for anything invalid. The caller has already
    obtained the member's explicit synthetic attestation. ``client_key``: the
    upload attempt's key (P5 FLOW); a concurrent POST of the same attempt that
    made the encounter first is DuplicateUpload (find_upload's checks apply).
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
    try:
        return _create(membership, user, title, service_date, data, filename, text, media_type, now, client_key)
    except IntegrityError:
        # the database's one row per member and key (Encounter.client_key's unique index): the first POST of this
        # attempt committed while this one ran; its encounter is the answer, and nothing of this one was stored
        existing = find_upload(user=user, workspace=membership.workspace, client_key=client_key, data=data, text=text)
        if existing is None:
            raise
        raise DuplicateUpload(existing) from None


def _create(membership, user, title, service_date, data, filename, text, media_type, now, client_key):
    with transaction.atomic():
        encounter = models.Encounter.objects.create(
            workspace=membership.workspace, title=title, created_by=user, client_key=client_key,
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
